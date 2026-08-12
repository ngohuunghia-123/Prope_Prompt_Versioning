"""ROADMAP SC2: a redelivery lands exactly once and moves no workspace's total.

**This file asserts the RESTATED AC-2, not the lock file's literal text.**
`.planning/research/PITFALLS.md` §2 records that ``call-ledger.lock.yml``'s AC-2
is written against a spill file and an in-process queue that ADR-0041 deleted, so
the literal clause names machinery that does not exist. The restated form — the
ROADMAP's SC2, and the one asserted here — is *"every message redelivered after
an unacknowledged consumer restart lands exactly once; the workspace's monthly
total is unchanged and every redelivery is counted"*, **including records the
direct-write fallback already wrote directly**. The stale clause is raised as
``OQ-024`` by plan 03-01 rather than patched into the spec.

**The subject is ``ledger.workspace_spend``, not ``ledger.call_record``.**
``call_record``'s primary key is ``call_id`` alone, so a duplicate row was
impossible before this phase and asserting "the record appears once" proves
nothing about CL-02. What a redelivery corrupted is the monthly aggregate
maintained inside the writer's own transaction (A-103), because it was
incremented from the rows *offered*. Every test below therefore asserts the
**unchanged total**, and asserts ``duplicate_call_id_total`` moved as well —
otherwise a drain that silently did nothing passes.

**Two mechanisms, two tests, and neither proves the other.**

1. **Re-publishing** the identical envelopes is deterministic and is the better
   shape for the idempotency claim: the same ``call_id``s are exactly what a
   redelivery after an unacknowledged consumer restart produces, and the drain
   cannot tell the difference — which is the property under test. Killing a
   consumer mid-flight is not deterministic and would make the *idempotency*
   assertion flaky for a reason that has nothing to do with idempotency.
2. **Re-publishing cannot exercise ``redelivered_total`` at all.** That counter
   reads ``AbstractIncomingMessage.redelivered``, the broker's own flag, and a
   re-published message is a new message with ``redelivered=False``. So the
   counter needs a test that really does leave messages unacknowledged. The two
   are two tests on purpose; **do not simplify them into one.**

**The ordering inside mechanism 2 is the whole of its value.** "The workspace
total is unchanged" needs a prior state to be unchanged *from*. A version that
merely consumed-without-acking on a raw consumer, dropped the connection and
consumed again would have **no row committed** at the moment of redelivery: the
upsert would see no conflict, ``duplicate_call_id_total`` would never move, and
"lands exactly once" would be satisfied by a code path with no idempotency in it
at all — a test that passes *before* the change it exists to guard. So the rows
are made durable **while the messages are still unacknowledged**, through
``workspace_transaction`` + ``write_records``, which is exactly what plan 03-01's
fallback does after a timed-out confirm.

Every assertion is read back through ``migrate_engine`` — the owner role, subject
to no policy — and never through the code under test.
"""

from dataclasses import replace

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.broker.connection import build_connection
from prope.broker.topology import DLQ, WORK_QUEUE, declare_topology
from prope.call_ledger.domain import CallRecordDraft
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from tests.broker._helpers import counter_value, drain_until, publish_drafts, queue_depth
from tests.unit import WORKSPACE_A, WORKSPACE_B, day, gateway_draft, seed_price_row

COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")
COUNT_BODIES = text("SELECT count(*) FROM ledger.call_body")
READ_SPEND = text(
    """
    SELECT period_month, currency, total_cost, call_count
    FROM   ledger.workspace_spend
    WHERE  workspace_id = :workspace_id
    ORDER  BY period_month
    """
)

#: Five, and never one. ``sort_by_parameter_order`` on the upsert's
#: ``returning()`` would make ``call_id`` a client-side sentinel and raise
#: ``InvalidRequestError`` on the first conflicting row — and a redelivery test
#: written with a single record is precisely the one that would not notice.
BATCH = 5


def _drafts(prefix: str, count: int = BATCH, **overrides) -> list[CallRecordDraft]:
    """``count`` distinct, cost-bearing gateway calls in one month."""
    return [
        gateway_draft(call_id=f"cal_{prefix}{index:022d}", created_at=day(5), **overrides)
        for index in range(count)
    ]


async def _row_count(migrate_engine: AsyncEngine) -> int:
    async with migrate_engine.begin() as control:
        return (await control.execute(COUNT_RECORDS)).scalar_one()


async def _body_count(migrate_engine: AsyncEngine) -> int:
    async with migrate_engine.begin() as control:
        return (await control.execute(COUNT_BODIES)).scalar_one()


async def _spend(migrate_engine: AsyncEngine, workspace_id: str) -> list[dict]:
    async with migrate_engine.begin() as control:
        rows = (await control.execute(READ_SPEND, {"workspace_id": workspace_id})).mappings().all()
    return [dict(row) for row in rows]


async def _dlq_depth(amqp_url: str) -> int:
    connection = await build_connection(amqp_url)
    async with connection:
        return await queue_depth(connection, DLQ)


def _duplicates() -> float:
    return counter_value("prope_call_ledger_duplicate_call_id_total")


def _redeliveries() -> float:
    return counter_value("prope_call_ledger_redelivered_total")


async def test_republishing_the_same_envelopes_leaves_every_workspace_total_unmoved(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """Mechanism 1 — the idempotency claim, and the cross-workspace claim with it.

    All four assertions are in one test on purpose: **any three of them pass
    against a drain that silently did nothing.** The row count is still five, the
    spend row is identical on ``call_count`` and ``total_cost``,
    ``duplicate_call_id_total`` moved by exactly five — which is what says the
    second delivery actually reached the statement — and the DLQ is empty, which
    is what says the redelivery was *acknowledged* rather than dead-lettered.

    Workspace B costs one more envelope and pins the aggregate to the right row:
    a duplicate arriving for A must not move B's total, and B's total must be
    exactly what its own record put there — asserted as a relation against A's
    five identical records rather than against a copied constant.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    await seed_price_row(
        migrate_engine,
        price_row_id="prc_01J00000000000000000000B",
        workspace_id=WORKSPACE_B,
        effective_from=day(1),
    )

    for_a = _drafts("aaa")
    for_b = _drafts("bbb", count=1, workspace_id=WORKSPACE_B)

    await publish_drafts(amqp_url, [*for_a, *for_b])
    landed = await drain_until(
        amqp_url, app_sessionmaker, lambda: _rows_reach(migrate_engine, BATCH + 1)
    )
    assert landed, "the first delivery never committed"

    before_a = await _spend(migrate_engine, WORKSPACE_A)
    before_b = await _spend(migrate_engine, WORKSPACE_B)
    assert before_a[0]["call_count"] == BATCH
    assert before_b[0]["call_count"] == 1

    duplicates_before = _duplicates()

    # The same five call_ids again — the shape a redelivery after an
    # unacknowledged consumer restart produces, and the drain cannot tell the
    # difference. Workspace B's record is NOT re-published: its row is the
    # control that a duplicate for A moves nothing that is not A's.
    await publish_drafts(amqp_url, for_a)
    duplicated = await drain_until(
        amqp_url, app_sessionmaker, lambda: _duplicates_reach(duplicates_before + BATCH)
    )
    assert duplicated, "the re-delivered records never reached the writer"

    assert await _row_count(migrate_engine) == BATCH + 1
    assert _duplicates() == duplicates_before + BATCH

    assert await _spend(migrate_engine, WORKSPACE_A) == before_a
    assert await _spend(migrate_engine, WORKSPACE_B) == before_b
    assert before_a[0]["total_cost"] == before_b[0]["total_cost"] * BATCH, (
        "workspace B's total is exactly its own one record's cost, and A's is exactly five of them"
    )

    assert await _dlq_depth(amqp_url) == 0, (
        "a redelivery must be acknowledged, not dead-lettered — that was the Phase 2 gap"
    )


async def test_a_redelivery_of_records_the_fallback_already_wrote_moves_nothing(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """Mechanism 2 — SC2's real shape: the record is already durable and the
    message comes back anyway.

    This is ``failure_modes`` row 3 and PITFALLS §2's *"including records the
    fallback already wrote directly"*. Step 3 below is what makes it that rather
    than a broker test wearing an SC2 name: with nothing committed at the moment
    of redelivery, the upsert would see no conflict at all and the whole test
    would pass against a writer with no idempotency in it.

    The drafts are written with ``body=None``, because that is what
    ``fallback.build_fallback_writer`` does (D-28) — so the redelivered envelopes
    arrive carrying bodies for records that already exist, which is the exact case
    D-34 decides. The surviving ``ledger.call_body`` count of zero is that
    decision asserted end to end: a body lost to a timed-out confirm is lost
    permanently, so that ``body_dropped_total`` stays reconcilable against the
    table.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    drafts = _drafts("ccc")

    # 1. Publish five cost-bearing gateway envelopes.
    await publish_drafts(amqp_url, drafts)

    duplicates_before = _duplicates()
    redeliveries_before = _redeliveries()

    # 2. Consume all five on a RAW consumer and acknowledge none, holding the
    #    connection open. The broker now considers them delivered-and-unacked.
    raw = await build_connection(amqp_url)
    async with raw:
        channel = await raw.channel()
        await channel.set_qos(prefetch_count=10)
        queue = await declare_topology(channel)
        held = 0
        async with queue.iterator() as messages:
            async for _message in messages:
                held += 1
                if held == BATCH:
                    break

        assert held == BATCH, "the raw consumer did not take the whole batch"

        # 3. With those messages still unacknowledged, make the same five records
        #    durable through the real write path — one transaction, one workspace,
        #    ``body=None``: what the fallback does after a timed-out confirm.
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            written = await write_records(
                session, [replace(draft, body=None) for draft in drafts]
            )
        assert written.duplicates == 0, "the fallback's own write must be the first one"

        snapshot_rows = await _row_count(migrate_engine)
        snapshot_spend = await _spend(migrate_engine, WORKSPACE_A)
        assert snapshot_rows == BATCH
        assert snapshot_spend[0]["call_count"] == BATCH

    # 4. The raw consumer's connection is now dropped, so the broker redelivers
    #    all five with ``redelivered=True``.
    # 5. Let the REAL drain take the redelivery — the second consumer here is
    #    ``run_drain``, so ``_parse`` really runs and ``redelivered_total`` really
    #    moves. (The raw-consumer test in
    #    ``test_drain_failure_classification.py`` deliberately does NOT assert
    #    that counter: its consumers never reach ``_parse``.)
    redelivered = await drain_until(
        amqp_url, app_sessionmaker, lambda: _duplicates_reach(duplicates_before + BATCH)
    )
    assert redelivered, "the redelivered records never reached the writer"

    assert await _row_count(migrate_engine) == snapshot_rows
    assert await _spend(migrate_engine, WORKSPACE_A) == snapshot_spend
    assert _duplicates() == duplicates_before + BATCH
    assert _redeliveries() == redeliveries_before + BATCH
    assert await _dlq_depth(amqp_url) == 0, (
        "a redelivery is acknowledged, not dead-lettered — before CL-02 this was five DLQ messages"
    )

    assert await _body_count(migrate_engine) == 0, (
        "D-34: a body arriving for a record the fallback already wrote is discarded, so "
        "body_dropped_total stays reconcilable against ledger.call_body"
    )


async def test_the_upsert_and_not_the_error_handler_is_what_absorbs_a_duplicate(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """The negative control for both tests above: the guarantee is the STATEMENT.

    Neither test can distinguish "the upsert skipped the row" from "something
    caught an ``IntegrityError`` and carried on", and the difference matters —
    the second would be CL-02's guarantee arriving under another name, and would
    put the batch's other records at the mercy of a rolled-back transaction.

    So: write one record, then offer the same ``call_id`` **through the raw
    ``INSERT`` the writer no longer issues**, and watch PostgreSQL refuse it.
    That is the failure ``write_records`` used to hand the drain, proved still to
    exist — which is what makes "``write_records`` raises nothing" a statement
    about the statement rather than about the error handling around it.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    draft = gateway_draft(call_id="cal_control0000000000000000", created_at=day(5))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await write_records(session, [draft])

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        again = await write_records(session, [draft])
    assert again.duplicates == 1, "the upsert absorbed it"

    raised = False
    try:
        async with migrate_engine.begin() as control:
            await control.execute(
                text(
                    "INSERT INTO ledger.call_record "
                    "(call_id, workspace_id, source, outcome, pinned, fallback, streaming, "
                    " usage_status, cost_status, created_at) "
                    "VALUES (:call_id, :workspace_id, 'gateway', 'ok', false, false, false, "
                    " 'unknown', 'not_applicable', :created_at)"
                ),
                {
                    "call_id": draft.call_id,
                    "workspace_id": WORKSPACE_A,
                    "created_at": day(5),
                },
            )
    except IntegrityError:
        raised = True

    assert raised, (
        "the primary key no longer refuses a second row, so the assertions above prove nothing"
    )
    assert await _row_count(migrate_engine) == 1


async def _rows_reach(migrate_engine: AsyncEngine, expected: int) -> bool:
    return await _row_count(migrate_engine) >= expected


async def _duplicates_reach(expected: float) -> bool:
    return _duplicates() >= expected


def test_the_work_queue_name_is_the_one_the_drain_consumes() -> None:
    """A one-line guard on the two module constants these tests lean on.

    ``publish_drafts`` routes to ``WORK_QUEUE`` and ``_dlq_depth`` reads ``DLQ``;
    if either name drifted, both tests above would assert against an empty queue
    and pass for the wrong reason.
    """
    assert WORK_QUEUE == "prope.call_record"
    assert DLQ == "prope.call_record.dlq"
