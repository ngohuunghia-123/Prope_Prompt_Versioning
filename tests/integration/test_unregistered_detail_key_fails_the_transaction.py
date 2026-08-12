"""PH-05: the refusal, the caller's rollback, and the counter that survives it.

**A test that asserts only "no history row" proves nothing.** It passes
identically against a module that opened and rolled back *its own* transaction —
which is call-ledger's D-19 shape and the one arrangement ADR-0023 forbids. So
every test here **is** the caller, and the rollback assertions give the caller
something to lose: a valid event written in the same transaction before the
poisoned one, asserted gone afterwards through the owner role, outside RLS.

**This file deviates from the lock's ``test_ref``**, which names
``tests/unit/test_unregistered_detail_key_fails_the_transaction``. The
transaction half is not observable without a database and ``tests/unit/`` here
means pure Python; both halves of AC-5 are asserted, which is more than the
single named file would have delivered. Recorded in the plan and in
``deferred-items.md``; no OQ is owed.

**Not wrapped in an outer transaction that is rolled back.** ``tests/conftest.py``
refuses that pattern at length — it turns ``session.begin()`` into a savepoint and
a transaction-local tenant setting survives a savepoint. It matters more here
than anywhere, because these tests open the transaction themselves.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.property_history.append import EVENT_ID_PREFIX, append
from prope.property_history.domain import (
    ActorType,
    HistoryAppendRejected,
    HistoryEventDraft,
    RejectionReason,
)
from tests.property_history import (
    ACTOR_ID,
    COUNT_HISTORY_EVENTS,
    SCOPE_PROMPT_ID,
    TARGET_ID,
    WORKSPACE_A,
    day,
)

#: The offending VALUE, distinctive so "it never reaches the message" cannot pass
#: by coincidence.
LEAKED_VALUE = "sk-live-do-not-log-me-9f3a"

COUNT_ONE_EVENT = text("SELECT count(*) FROM history.history_event WHERE id = :id")

#: One of the three seeded actions whose registry row requires a reason. Used so
#: the ``missing_reason`` case exercises the seeded vocabulary, not a fixture.
REASONED_ACTION = "revision_break_glass_released"


class _AbandonedError(Exception):
    """The caller's own failure, raised to abandon a transaction on purpose."""


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


def rejected_total(reason: str) -> float:
    """A DELTA source. The registry is process-global and outlives every test."""
    value = REGISTRY.get_sample_value(
        "prope_property_history_append_rejected_total", {"reason": reason}
    )
    return value or 0.0


async def test_a_valid_event_is_written_inside_the_callers_transaction(
    app_sessionmaker, migrate_engine
):
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        returned = await append(session, draft())
        # Read back INSIDE the transaction, BY THE RETURNED ID: this is what
        # proves the write happened on the caller's connection rather than on one
        # of the module's, and — since D-67 — that the id came back at all.
        visible = (await session.execute(COUNT_ONE_EVENT, {"id": returned})).scalar_one()

    assert returned.startswith(EVENT_ID_PREFIX)
    assert visible == 1

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 1


async def test_an_abandoned_caller_transaction_leaves_no_event(app_sessionmaker, migrate_engine):
    """ADR-0023's central property.

    If ``append`` had owned and committed its own transaction, the row would be
    there.
    """
    with pytest.raises(_AbandonedError):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await append(session, draft())
            raise _AbandonedError

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 0


async def test_an_unregistered_detail_key_rolls_the_callers_transaction_back(
    app_sessionmaker, migrate_engine
):
    before = {reason.value: rejected_total(reason.value) for reason in RejectionReason}

    with pytest.raises(HistoryAppendRejected) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            # The stand-in state change. Any row the caller writes in the same
            # transaction would do; a second history event is the honest choice
            # because it is the only table this phase may write to.
            await append(session, draft())
            await append(session, draft(details={"not_registered": LEAKED_VALUE}))

    assert excinfo.value.reason is RejectionReason.UNKNOWN_DETAIL_KEY
    assert excinfo.value.detail_key == "not_registered"
    assert LEAKED_VALUE not in str(excinfo.value)

    # As the owner, outside RLS: BOTH rows are gone, including the one that
    # succeeded — the half a count-of-zero on the failing row cannot see.
    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 0

    assert rejected_total("unknown_detail_key") == before["unknown_detail_key"] + 1
    assert rejected_total("unknown_action") == before["unknown_action"]
    assert rejected_total("missing_reason") == before["missing_reason"]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"action": "action_that_is_not_registered"}, RejectionReason.UNKNOWN_ACTION),
        ({"action": REASONED_ACTION}, RejectionReason.MISSING_REASON),
    ],
    ids=["unknown_action", "missing_reason"],
)
async def test_an_unregistered_action_and_a_missing_reason_each_roll_back_and_count(
    app_sessionmaker, migrate_engine, overrides, expected
):
    before = {reason.value: rejected_total(reason.value) for reason in RejectionReason}

    with pytest.raises(HistoryAppendRejected) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await append(session, draft())
            await append(session, draft(**overrides))

    assert excinfo.value.reason is expected

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 0

    for reason in RejectionReason:
        delta = 1 if reason is expected else 0
        assert rejected_total(reason.value) == before[reason.value] + delta
