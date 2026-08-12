"""CL-08: expired bodies are gone by any query, and their call records remain.

Two failure modes shape every test here, and neither one looks like a failure
from the job's side.

**A retention job that runs cleanly and deletes nothing looks healthy.** So
nothing in this file asks the job what it did and believes the answer. Every
assertion is a direct query against ``ledger.call_body`` through
``migrate_engine`` — the owner role, which is subject to no policy. Checking
emptiness through an application session in the wrong tenant would return zero
rows whether or not the delete worked, and the lock file's security test plan
requires exactly this distinction: "retention delete verified by direct query
rather than through an API that could be filtering".

**A loop that holds one transaction across every chunk is indistinguishable
from a correct one once it has returned.** Both must commit before returning or
nothing would persist, so any observation taken after the call is blind to where
the transaction boundaries were. The ``per_chunk`` test therefore observes the
loop while the loop is still running, through the ``on_chunk`` seam, from a
connection the loop does not hold. That is the only assertion in this phase that
establishes OQ-D's adopted reading, and a bounded single-chunk run cannot
substitute for it.

The cut-off is passed in, always. AC-8's "bodies written 31 days ago with a
30-day retention window" is arithmetic on the fixture calendar, with no clock to
freeze — and ``freezegun`` could not have moved the server's clock anyway.
"""

from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.call_ledger.retention import DEFAULT_CHUNK_SIZE, delete_expired_bodies
from prope.call_ledger.writer import DEFAULT_RETENTION_WINDOW, write_records
from prope.db.session import workspace_transaction
from tests.unit import WORKSPACE_A, WORKSPACE_B, day, gateway_draft

COUNT_BODIES_FOR = text("SELECT count(*) FROM ledger.call_body WHERE workspace_id = :ws")
COUNT_RECORDS_FOR = text("SELECT count(*) FROM ledger.call_record WHERE workspace_id = :ws")
LIST_SURVIVING_BODY_IDS = text(
    "SELECT call_id FROM ledger.call_body WHERE workspace_id = :ws ORDER BY call_id"
)
READ_WHOLE_RECORD = text("SELECT * FROM ledger.call_record WHERE call_id = :call_id")

#: 12 expired and 5 unexpired — AC-8's shape, and a count that takes three
#: chunks at ``chunk_size=5`` so the loop's termination on a short chunk is
#: exercised rather than assumed.
EXPIRED = 12
UNEXPIRED = 5

#: The instant handed to the job. Every ``expires_at`` below is placed relative
#: to it, so "31 days past its window" is arithmetic and not a date to decode.
CUT_OFF = day(66)


def _expiring_at(call_id: str, expires_at, **overrides):
    """A gateway draft whose body will be stamped to expire at ``expires_at``.

    The stamp is produced by the real write path — ``created_at`` plus the
    writer's retention window — rather than written into ``call_body`` by hand,
    so this test cannot pass against a writer that stamps something else.
    """
    return gateway_draft(
        call_id=call_id,
        created_at=expires_at - DEFAULT_RETENTION_WINDOW,
        **overrides,
    )


async def _write(app_sessionmaker, drafts, *, workspace_id=WORKSPACE_A):
    async with workspace_transaction(app_sessionmaker, workspace_id) as session:
        return await write_records(session, drafts)


async def _seed(app_sessionmaker, *, workspace_id=WORKSPACE_A, prefix="a"):
    """``EXPIRED`` bodies 31 days past the cut-off and ``UNEXPIRED`` a day short.

    Returns the two id lists, so a test can name exactly which rows it expects
    to survive rather than counting and hoping.
    """
    expired_ids = [f"cal_{prefix}_expired_{index:03d}" for index in range(EXPIRED)]
    kept_ids = [f"cal_{prefix}_kept_{index:03d}" for index in range(UNEXPIRED)]

    drafts = [
        _expiring_at(call_id, CUT_OFF - timedelta(days=31), workspace_id=workspace_id)
        for call_id in expired_ids
    ] + [
        _expiring_at(call_id, CUT_OFF + timedelta(days=1), workspace_id=workspace_id)
        for call_id in kept_ids
    ]

    result = await _write(app_sessionmaker, drafts, workspace_id=workspace_id)
    assert result.bodies_written == EXPIRED + UNEXPIRED
    return expired_ids, kept_ids


async def _count_bodies(migrate_engine: AsyncEngine, workspace_id=WORKSPACE_A) -> int:
    """Counted as the owner, on its own connection. Never through the app role."""
    async with migrate_engine.begin() as control:
        return (await control.execute(COUNT_BODIES_FOR, {"ws": workspace_id})).scalar_one()


async def test_expired_bodies_are_gone_and_their_call_records_are_intact(
    app_sessionmaker, migrate_engine
):
    """AC-8, both halves, each proved separately.

    The body being gone is not evidence that the record survived, and the record
    surviving is not evidence that the body went. ``fk_call_body_call_id`` has
    no ``ON DELETE`` in either direction precisely so that dropping the body
    leaves the metadata standing — which is the whole reason these are two
    tables — and this test is what makes that a fact rather than an intention.
    """
    expired_ids, kept_ids = await _seed(app_sessionmaker)

    async with migrate_engine.begin() as control:
        before = {
            call_id: dict(
                (await control.execute(READ_WHOLE_RECORD, {"call_id": call_id})).mappings().one()
            )
            for call_id in expired_ids
        }
        assert (
            await control.execute(COUNT_BODIES_FOR, {"ws": WORKSPACE_A})
        ).scalar_one() == EXPIRED + UNEXPIRED, "positive control: the bodies must exist first"

    deleted = await delete_expired_bodies(app_sessionmaker, WORKSPACE_A, now=CUT_OFF)

    assert deleted == EXPIRED

    async with migrate_engine.begin() as control:
        surviving = [
            row[0]
            for row in (
                await control.execute(LIST_SURVIVING_BODY_IDS, {"ws": WORKSPACE_A})
            ).all()
        ]
        records = (await control.execute(COUNT_RECORDS_FOR, {"ws": WORKSPACE_A})).scalar_one()
        after = {
            call_id: dict(
                (await control.execute(READ_WHOLE_RECORD, {"call_id": call_id})).mappings().one()
            )
            for call_id in expired_ids
        }

    # The body half: none of the 12 is findable by a query that can see
    # everything, and the 5 unexpired ones are untouched.
    assert surviving == sorted(kept_ids)

    # The record half: all 17 records still there, and the 12 whose bodies were
    # deleted are unchanged field for field.
    assert records == EXPIRED + UNEXPIRED
    assert after == before


async def test_chunking_runs_three_chunks_and_a_bounded_run_stops_early(
    app_sessionmaker, migrate_engine
):
    """``chunk_size=5`` over 12 rows is three chunks: 5, 5, then a short 2 that
    ends the loop without a ``max_chunks`` guard. And ``max_chunks=1`` stops
    after the first, deleting 5 and leaving 7 — the bound is real, not advisory.
    """
    await _seed(app_sessionmaker)

    bounded = await delete_expired_bodies(
        app_sessionmaker, WORKSPACE_A, now=CUT_OFF, chunk_size=5, max_chunks=1
    )
    assert bounded == 5
    assert await _count_bodies(migrate_engine) == EXPIRED + UNEXPIRED - 5

    chunks: list[int] = []

    async def count_chunks(deleted_in_chunk: int, deleted_total: int) -> None:
        chunks.append(deleted_in_chunk)

    rest = await delete_expired_bodies(
        app_sessionmaker, WORKSPACE_A, now=CUT_OFF, chunk_size=5, on_chunk=count_chunks
    )

    assert rest == EXPIRED - 5
    assert chunks == [5, 2], "the loop must end on the short chunk, with no guard needed"
    assert await _count_bodies(migrate_engine) == UNEXPIRED


async def test_per_chunk_transactions_are_visible_outside_the_running_loop(
    app_sessionmaker, migrate_engine
):
    """OQ-D, proved behaviourally, from **inside** an unbounded multi-chunk run.

    ADR-0040 read literally puts every chunk in one transaction, which holds
    every row lock and the whole snapshot for the duration and delivers none of
    the benefit chunking exists for. The adopted reading is one transaction per
    chunk, each still carrying exactly one workspace's tenant context — and this
    is the assertion that establishes it.

    The callback opens a **fresh** ``prope_migrate`` connection each time it
    fires — not the seeding connection, not anything the loop holds — and counts
    the survivors. Over 12 expired bodies at ``chunk_size=5`` a per-chunk
    implementation records 7, then 2, then 0: chunk 1's deletions are already
    visible to an outside connection at a moment when chunks 2 and 3 have not
    run.

    A loop-wide single transaction records 12, 12, 12 instead, because nothing
    it deleted becomes visible to another connection until the whole loop
    commits — and a plain count on that other connection takes no locks, so the
    wrong shape fails loudly here rather than hanging.

    The obvious version of this test is worthless and is deliberately not
    written: with ``max_chunks=1`` there is exactly one chunk, a loop-wide
    transaction must also commit before returning, and both shapes leave the
    same 7 rows for the same fresh connection to find.
    """
    await _seed(app_sessionmaker)

    observed: list[int] = []

    async def observe_from_outside(deleted_in_chunk: int, deleted_total: int) -> None:
        # A new connection from migrate_engine (NullPool, so genuinely new).
        # What it can see is what any other session in the cluster can see.
        async with migrate_engine.begin() as outsider:
            remaining = (
                await outsider.execute(COUNT_BODIES_FOR, {"ws": WORKSPACE_A})
            ).scalar_one()
        observed.append(remaining - UNEXPIRED)

    deleted = await delete_expired_bodies(
        app_sessionmaker,
        WORKSPACE_A,
        now=CUT_OFF,
        chunk_size=5,
        on_chunk=observe_from_outside,
    )

    assert deleted == EXPIRED
    assert len(observed) == 3, "three chunks, so three commit boundaries to observe"
    assert observed == [7, 2, 0], (
        "the expired bodies still visible to an outside connection after each "
        "chunk committed. [12, 12, 12] means the whole loop ran in one "
        f"transaction and released nothing between chunks; got {observed}"
    )

    # Anchor the mid-run observations to a real completed delete.
    assert await _count_bodies(migrate_engine) == UNEXPIRED


async def test_default_path_without_a_callback_deletes_exactly_the_same_rows(
    app_sessionmaker, migrate_engine
):
    """``on_chunk`` is an observation seam and nothing else.

    The same unbounded ``chunk_size=5`` run with no callback returns the same 12
    and empties the same rows, so the production call path — which supplies no
    callback — is the loop it would have been without the parameter.
    """
    _, kept_ids = await _seed(app_sessionmaker)

    deleted = await delete_expired_bodies(
        app_sessionmaker, WORKSPACE_A, now=CUT_OFF, chunk_size=5
    )

    assert deleted == EXPIRED

    async with migrate_engine.begin() as control:
        surviving = [
            row[0]
            for row in (
                await control.execute(LIST_SURVIVING_BODY_IDS, {"ws": WORKSPACE_A})
            ).all()
        ]

    assert surviving == sorted(kept_ids)


async def test_another_workspaces_equally_expired_body_is_untouched(
    app_sessionmaker, migrate_engine
):
    """B4: a cross-tenant sweep is the natural shape of this job, and is exactly
    where a workspace scope gets lost.

    Workspace B's bodies are expired by the same cut-off and are seeded first,
    so if the delete were tenant-blind they would go. The call is scoped to A.
    """
    await _seed(app_sessionmaker, workspace_id=WORKSPACE_B, prefix="b")
    await _seed(app_sessionmaker, workspace_id=WORKSPACE_A, prefix="a")

    assert await _count_bodies(migrate_engine, WORKSPACE_B) == EXPIRED + UNEXPIRED

    deleted = await delete_expired_bodies(app_sessionmaker, WORKSPACE_A, now=CUT_OFF)

    assert deleted == EXPIRED
    assert await _count_bodies(migrate_engine, WORKSPACE_A) == UNEXPIRED
    assert await _count_bodies(migrate_engine, WORKSPACE_B) == EXPIRED + UNEXPIRED, (
        "a workspace this call was not scoped to lost bodies"
    )


async def test_a_repeat_run_after_everything_expired_is_gone_deletes_nothing(
    app_sessionmaker, migrate_engine
):
    """Idempotent, and it says so honestly: 0, in exactly one chunk.

    A job that cannot tell "nothing left" from "did not look" is the repudiation
    failure this phase verifies against the data rather than against the job.
    """
    await _seed(app_sessionmaker)
    assert await delete_expired_bodies(app_sessionmaker, WORKSPACE_A, now=CUT_OFF) == EXPIRED

    chunks: list[int] = []

    async def count_chunks(deleted_in_chunk: int, deleted_total: int) -> None:
        chunks.append(deleted_in_chunk)

    again = await delete_expired_bodies(
        app_sessionmaker, WORKSPACE_A, now=CUT_OFF, on_chunk=count_chunks
    )

    assert again == 0
    assert chunks == [0], "one chunk, which found nothing and ended the loop"
    assert await _count_bodies(migrate_engine) == UNEXPIRED


async def test_a_body_expiring_exactly_at_the_cut_off_goes_and_a_microsecond_later_stays(
    app_sessionmaker, migrate_engine
):
    """The predicate is at-or-before, so the cut-off instant belongs to the
    deleted side. Asserting the microsecond neighbour is what makes that a
    decision rather than an accident of whichever comparison got typed."""
    exactly = "cal_boundary_exactly_at_cut_off"
    later = "cal_boundary_one_microsecond_later"

    await _write(
        app_sessionmaker,
        [
            _expiring_at(exactly, CUT_OFF),
            _expiring_at(later, CUT_OFF + timedelta(microseconds=1)),
        ],
    )

    deleted = await delete_expired_bodies(app_sessionmaker, WORKSPACE_A, now=CUT_OFF)

    assert deleted == 1

    async with migrate_engine.begin() as control:
        surviving = [
            row[0]
            for row in (
                await control.execute(LIST_SURVIVING_BODY_IDS, {"ws": WORKSPACE_A})
            ).all()
        ]

    assert surviving == [later]


async def test_the_default_chunk_size_is_the_documented_five_thousand():
    """A6 is a flagged, tunable judgement against a stated target — one day's
    expired bodies, up to 500,000 rows, removed within ten minutes, which is 100
    chunks at this size. Pinning it here means changing the number is a visible
    decision rather than a silent one."""
    assert DEFAULT_CHUNK_SIZE == 5_000
