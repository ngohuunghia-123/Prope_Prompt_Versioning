"""The tracer: an event through ``append()`` on a caller's transaction and back out through ``read()``.

Every event here is written through ``append()`` on a session from
``workspace_transaction``, never by raw SQL. The point is the path — a test that
seeded rows directly would prove the statement and not the seam.

**Not wrapped in an outer transaction that is rolled back.** ``tests/conftest.py``
refuses that pattern at length: it turns ``session.begin()`` into a savepoint and
a transaction-local tenant setting survives a savepoint, so tenant A's context
contaminates tenant B inside one test. It matters most in exactly this file, which
opens transactions itself and reads across two workspaces.
"""

from datetime import timedelta

import pytest
from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.property_history.append import EVENT_ID_PREFIX, append
from prope.property_history.domain import ActorType, HistoryEventDraft, PromptScope
from prope.property_history.read import read
from tests.property_history import (
    ACTOR_ID,
    SCOPE_PROMPT_ID,
    TARGET_ID,
    WORKSPACE_A,
    WORKSPACE_B,
    day,
)

OTHER_SCOPE_PROMPT_ID = "prm_01J0000000000000000000002"

COUNT_BY_ID = text("SELECT count(*) FROM history.history_event WHERE id = :id")


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


async def test_an_appended_event_comes_back_by_the_id_append_returned(app_sessionmaker):
    """D-67's assertion: the id ``append`` returns is the id of the row it wrote."""
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        returned = await append(session, draft())

    assert returned.startswith(EVENT_ID_PREFIX)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        events = await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID))

    assert len(events) == 1
    event = events[0]
    assert event.id == returned
    assert event.action == "revision_approved"
    assert event.scope_prompt_id == SCOPE_PROMPT_ID
    assert event.actor_type is ActorType.USER
    assert event.occurred_at.tzinfo is not None
    assert event.seq > 0
    assert event.details == {}

    with pytest.raises(TypeError):
        event.details["mutated"] = True  # type: ignore[index]


async def test_two_events_in_one_transaction_come_back_newest_seq_first_against_the_clock(
    app_sessionmaker,
):
    """``seq`` is the SORT KEY, not merely a tiebreak.

    PH-04's test asserts *identical* timestamps, which proves ``seq`` breaks a
    tie. This asserts *inverted* ones: A is written first carrying the LATER
    ``occurred_at``, so an implementation sorting by ``occurred_at DESC`` would
    return A then B. Both are needed and neither implies the other.
    """
    later = day(5) + timedelta(hours=1)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        first_written = await append(session, draft(occurred_at=later))
        second_written = await append(session, draft(occurred_at=day(5)))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        events = await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID))

    assert [event.id for event in events] == [second_written, first_written]
    # The clock says the opposite, which is what makes the order above load-bearing.
    assert events[0].occurred_at < events[1].occurred_at
    assert events[0].seq > events[1].seq


async def test_another_prompt_and_another_workspace_do_not_appear(app_sessionmaker):
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        wanted = await append(session, draft())
        await append(session, draft(scope_prompt_id=OTHER_SCOPE_PROMPT_ID))
        await append(session, draft(scope_prompt_id=None))

    # Its OWN transaction: prope_app cannot write a row for a workspace it has no
    # tenant context for — the policy's WITH CHECK refuses it.
    async with workspace_transaction(app_sessionmaker, WORKSPACE_B) as session:
        await append(session, draft(workspace_id=WORKSPACE_B))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        events = await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID))

    assert [event.id for event in events] == [wanted]


async def test_read_leaves_the_callers_transaction_open(app_sessionmaker, migrate_engine):
    """The read-side mirror of Phase 4's abandoned-transaction test.

    If ``read()`` had committed, or opened a session of its own, the append that
    follows it inside the SAME transaction would not be part of the same commit.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID)) == ()
        appended = await append(session, draft())

    async with migrate_engine.begin() as control:
        landed = (await control.execute(COUNT_BY_ID, {"id": appended})).scalar_one()

    assert landed == 1
