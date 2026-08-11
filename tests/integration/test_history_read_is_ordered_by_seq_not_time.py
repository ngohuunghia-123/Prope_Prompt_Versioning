"""ROADMAP SC3's ordering half, in the two forms nothing else covers.

Phase 4's ``test_same_transaction_events_have_a_stable_order.py`` asserts that
two events sharing a timestamp come back ``seq``-ordered, which proves ``seq`` is
a **tiebreak**. An implementation ordering ``occurred_at DESC, seq DESC`` passes
that. This file asserts the two cases that separate a tiebreak from a **sort
key**: timestamps running backwards against the write order, and a lower ``seq``
committing after a higher one.

**Not wrapped in an outer transaction that is rolled back** (``tests/conftest.py``
refuses the pattern at length). It matters most here: the second test drives two
overlapping transactions by hand.
"""

import inspect
from contextlib import AsyncExitStack
from datetime import timedelta

from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft, PromptScope
from prope.property_history.read import read
from tests.property_history import ACTOR_ID, SCOPE_PROMPT_ID, TARGET_ID, WORKSPACE_A, day

SELECT_SEQ_BY_ID = text("SELECT seq FROM history.history_event WHERE id = :id")


def draft(**overrides) -> HistoryEventDraft:
    values = {
        "workspace_id": WORKSPACE_A,
        "actor_type": ActorType.USER,
        "actor_id": ACTOR_ID,
        "action": "revision_approved",
        "target_type": "revision",
        "target_id": TARGET_ID,
        "scope_prompt_id": SCOPE_PROMPT_ID,
        "occurred_at": day(5),
    }
    values.update(overrides)
    return HistoryEventDraft(**values)


async def test_the_clock_does_not_decide_the_order(app_sessionmaker):
    """Five events whose timestamps run strictly backwards against the write order.

    An implementation sorting ``occurred_at DESC`` would return them in write
    order; ``seq DESC`` returns the exact reverse. Phase 4's identical-timestamp
    test cannot tell the two apart, and neither test implies the other.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        written = [
            await append(session, draft(occurred_at=day(5) + timedelta(hours=5 - n)))
            for n in range(5)
        ]

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        events = await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID))

    assert [event.id for event in events] == list(reversed(written))
    occurred = [event.occurred_at for event in events]
    assert occurred == sorted(occurred), "the clock runs the OTHER way; that is the point"
    seqs = [event.seq for event in events]
    assert seqs == sorted(seqs, reverse=True)


async def test_a_late_committing_lower_seq_is_not_skipped(app_sessionmaker):
    """Assignment order is not commit order — Phase 4 handed this obligation forward.

    Two overlapping transactions: T1 takes the lower ``seq`` and commits second.
    An ascending ``seq > N`` poll taken between the two commits would return B,
    advance its high-water mark past ``seq(A)``, and **never return A again** — a
    permanently missing event on the one table whose product claim is that
    nothing is missing. INT-007 paginates descending, where a late-committing
    lower ``seq`` simply lands on a later page. That is why the direction is in
    the spec rather than a preference.

    Both transactions run on one event loop, so the interleaving is
    deterministic and needs no synchronisation primitive; ``NullPool`` gives each
    session its own connection, so they genuinely overlap; and the reads happen
    on a THIRD session, because reading inside T1 would see T1's own uncommitted
    row.
    """
    scope = PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID)

    async with AsyncExitStack() as stack:
        first = await stack.enter_async_context(
            workspace_transaction(app_sessionmaker, WORKSPACE_A)
        )
        a_id = await append(first, draft())
        # Read on T1's own session: A is uncommitted, so no other connection can
        # see it yet, and the control has to be taken before T1 commits.
        seq_a = (await first.execute(SELECT_SEQ_BY_ID, {"id": a_id})).scalar_one()

        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as second:
            b_id = await append(second, draft())
            seq_b = (await second.execute(SELECT_SEQ_BY_ID, {"id": b_id})).scalar_one()

        assert seq_a < seq_b, (
            f"the identity sequence handed out {seq_a} after {seq_b}; this test asserts nothing "
            "unless the FIRST-written event holds the LOWER seq"
        )

        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as reader:
            visible = await read(reader, scope, limit=1)

        assert [event.id for event in visible] == [b_id]

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as reader:
        next_page = await read(reader, scope, cursor=b_id, limit=1)

    assert [event.id for event in next_page] == [a_id]


def test_read_asserts_nothing_about_an_actor():
    """INT-007's load-bearing negative, in this repository's own words.

    ``read()`` performs no permission check and has no way to: the caller has
    already answered *may you see this subject* via INT-001 before asking what
    happened to it, and a caller that reaches here without having checked has
    leaked another workspace's decision trail — RLS is the backstop (ADR-0045),
    not the control. **If this test ever fails, the fix is deleting the
    parameter, not updating the test.**
    """
    parameters = list(inspect.signature(read).parameters)

    assert parameters == ["session", "scope", "cursor", "limit"]
    assert not [
        name
        for name in parameters
        if any(term in name for term in ("actor", "permission", "may", "subject", "access"))
    ]
