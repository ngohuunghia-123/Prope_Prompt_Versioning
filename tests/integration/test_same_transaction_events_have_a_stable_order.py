"""PH-04 / A-125: two events with byte-identical timestamps still have an order.

**Two events read back in the order they were written look correct even when
the order is an accident of the planner.** So this file removes every other
possible source of ordering: the two events share ``occurred_at`` exactly, and
every read-back is ``ORDER BY seq`` through ``migrate_engine``, the owner role,
which is subject to no policy.

The case this exists for is A-076's: approve-and-release is one request
writing two rows in one transaction, and the lock file's own failure-mode row
says the wrong order shows "roughly half the time, for exactly the two-event
cases that matter most" when the tiebreak is a timestamp two events can share.

What this file deliberately does not assert: no absolute ``seq`` value
(``tests/conftest.py``'s ``TRUNCATE ... RESTART IDENTITY`` only makes small
values stable *within a run*), and no ordering property across concurrent
transactions — inside one transaction ``seq`` is exact, but assignment order
is not commit order, and that hazard is Phase 5's cursor pagination to handle.
"""

import pytest
from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.property_history.append import record_event
from prope.property_history.domain import ActorType, HistoryAppendRejected, HistoryEventDraft
from tests.property_history import (
    ACTOR_ID,
    EVENT_ID,
    OTHER_EVENT_ID,
    SCOPE_PROMPT_ID,
    TARGET_ID,
    THIRD_EVENT_ID,
    WORKSPACE_A,
    day,
    load_registry,
)

SELECT_ORDERED = text(
    "SELECT id, seq, occurred_at FROM history.history_event ORDER BY seq"
)


class _AbandonedError(Exception):
    """Raised to abandon a transaction on purpose, after its INSERT reached the engine."""


def draft(**overrides) -> HistoryEventDraft:
    values = {
        "id": EVENT_ID,
        "workspace_id": WORKSPACE_A,
        "actor_type": ActorType.USER,
        "actor_id": ACTOR_ID,
        "action": "revision_approved",
        "target_type": "revision",
        "target_id": TARGET_ID,
        "scope_prompt_id": SCOPE_PROMPT_ID,
        # datetime.now(UTC) called twice would occasionally produce two
        # different instants; the shared literal is what removes the timestamp
        # as a possible source of the ordering under test.
        "occurred_at": day(5),
    }
    values.update(overrides)
    return HistoryEventDraft(**values)


async def test_approval_precedes_release_when_their_timestamps_are_identical(
    app_sessionmaker, migrate_engine
):
    registry = await load_registry(app_sessionmaker)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        approval_id = await record_event(
            session, draft(id=EVENT_ID, action="revision_approved"), registry
        )
        release_id = await record_event(
            session,
            draft(id=OTHER_EVENT_ID, action="revision_released", reason="scheduled release"),
            registry,
        )

    async with migrate_engine.begin() as control:
        rows = (await control.execute(SELECT_ORDERED)).all()

    assert [row.id for row in rows] == [approval_id, release_id]

    approval_row = next(row for row in rows if row.id == approval_id)
    release_row = next(row for row in rows if row.id == release_id)
    assert approval_row.seq < release_row.seq

    # The positive control: the timestamps really are identical, so the
    # ordering above cannot be coming from a tiebreak on occurred_at.
    assert len({row.occurred_at for row in rows}) == 1


async def test_three_events_in_one_transaction_order_fully(app_sessionmaker, migrate_engine):
    """A two-element comparison passes half the time under a coin flip; a
    three-element chain passes an eighth of the time, which is what turns a
    lucky pass into an unlikely one."""
    registry = await load_registry(app_sessionmaker)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        first = await record_event(session, draft(id=EVENT_ID), registry)
        second = await record_event(session, draft(id=OTHER_EVENT_ID), registry)
        third = await record_event(session, draft(id=THIRD_EVENT_ID), registry)

    async with migrate_engine.begin() as control:
        rows = (await control.execute(SELECT_ORDERED)).all()

    by_id = {row.id: row.seq for row in rows}
    assert by_id[first] < by_id[second] < by_id[third]


async def test_a_gap_in_seq_is_not_a_missing_event(app_sessionmaker, migrate_engine):
    """``nextval`` and ``setval`` are never rolled back, so an INSERT that
    reached the engine consumes a sequence value whether or not its
    transaction survives. PH-05's own transaction test produces exactly this
    shape: a valid event written, then a refusal, then the caller's rollback
    stranding the value the valid INSERT already took.

    A **validation** refusal is the other mechanism and it must NOT produce a
    gap: ``check_event`` raises before ``record_event`` issues any statement,
    so ``nextval`` is never called and the two survivors take consecutive
    values. Asserting only the gap would leave the false, looser version of
    the claim equally consistent with the evidence.

    If this test starts failing because the gap closed, do not "fix" the gap —
    investigate what started reusing sequence values, because that would break
    distinctness before it broke anything else.
    """
    registry = await load_registry(app_sessionmaker)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        first = await record_event(session, draft(id=EVENT_ID), registry)

    with pytest.raises(_AbandonedError):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await record_event(session, draft(id=OTHER_EVENT_ID), registry)
            raise _AbandonedError

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        second = await record_event(session, draft(id=THIRD_EVENT_ID), registry)

    async with migrate_engine.begin() as control:
        seqs = {row.id: row.seq for row in (await control.execute(SELECT_ORDERED)).all()}

    difference = seqs[second] - seqs[first]
    assert difference > 1, (
        f"expected a gap greater than 1 (the abandoned INSERT reached the engine and "
        f"consumed a value that was never returned), got a difference of {difference}"
    )


async def test_a_validation_refusal_between_two_writes_leaves_no_gap(
    app_sessionmaker, migrate_engine
):
    """The sibling case: ``check_event`` raises before ``record_event`` issues
    any statement, so ``nextval`` is never called and the two survivors take
    consecutive values. Asserted separately from the rolled-back-INSERT gap
    above so the two mechanisms differing is exercised, not merely stated —
    the plan's first draft had them confused.
    """
    registry = await load_registry(app_sessionmaker)
    before_id = "hev_01J0000000000000000000004"
    after_id = "hev_01J0000000000000000000005"

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        before_validation = await record_event(session, draft(id=before_id), registry)

    with pytest.raises(HistoryAppendRejected):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await record_event(
                session,
                draft(id=OTHER_EVENT_ID, action="action_that_is_not_registered"),
                registry,
            )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        after_validation = await record_event(session, draft(id=after_id), registry)

    async with migrate_engine.begin() as control:
        seqs = {row.id: row.seq for row in (await control.execute(SELECT_ORDERED)).all()}

    difference = seqs[after_validation] - seqs[before_validation]
    assert difference == 1, (
        "a validation refusal issues no SQL, so it must leave no gap; got a difference of "
        f"{difference}"
    )


async def test_two_transactions_in_sequence_also_order_by_seq(app_sessionmaker, migrate_engine):
    """Holds because this test is single-threaded and the second transaction
    begins after the first commits. **Not a guarantee across concurrent
    transactions**: assignment order is not commit order, and a reader between
    two commits can see seq 6 with no 5. That lands on Phase 5's cursor
    pagination — a "what is new since seq > N" poll would permanently skip a
    row; INT-007 paginates seq DESC, the safer direction.
    """
    registry = await load_registry(app_sessionmaker)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        first = await record_event(session, draft(id=EVENT_ID), registry)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        second = await record_event(session, draft(id=OTHER_EVENT_ID), registry)

    async with migrate_engine.begin() as control:
        rows = (await control.execute(SELECT_ORDERED)).all()

    by_id = {row.id: row.seq for row in rows}
    assert by_id[first] < by_id[second]
