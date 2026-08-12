"""ADR-0035 on ``history_event``: the policy, exercised rather than catalogued.

``tests/architecture/test_tenant_coverage.py`` proves the policy *exists* and
``tests/integration/test_migration_chain.py`` snapshots its text. Neither would
notice a policy rewritten to ``USING (true)`` by hand. Non-negotiable #4 rests on
this table, so the behaviour is asserted here, in the shape
``test_tenant_isolation.py`` established for ``ledger.call_record``.

**The ``WITH CHECK`` half matters more on this table than on that one.**
``append()`` binds ``workspace_id`` straight from the draft and ``check_event``
never compares it to the session's tenant, so a writing module that builds a
draft for one workspace and opens its transaction on another is stopped by the
policy and by nothing else. That is verbatim ADR-0040's denormalised-and-
mis-stamped leak.

Every zero here carries a ``prope_migrate`` positive control: an empty table
returns zero rows too, and a test that cannot tell those apart proves nothing.
The pristine (NULL) and reverted (``''``) tenant paths are separate tests for
``test_tenant_isolation.py``'s reason — both yield zero rows, by different
routes.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from prope.db.session import workspace_transaction
from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft
from tests.property_history import (
    ACTOR_ID,
    COUNT_HISTORY_EVENTS,
    EVENT_ID,
    OTHER_EVENT_ID,
    SCOPE_PROMPT_ID,
    TARGET_ID,
    WORKSPACE_A,
    WORKSPACE_B,
    day,
    seed_history_event,
)

SELECT_EVENT_IDS = text("SELECT id FROM history.history_event ORDER BY id")
READ_TENANT_GUC = text("SELECT current_setting('app.workspace_id', true)")


def draft(**overrides) -> HistoryEventDraft:
    """A registered ``(action, target_type)`` pair, so the FK is never the refusal."""
    values = {
        "workspace_id": WORKSPACE_A,
        "actor_type": ActorType.USER,
        "actor_id": ACTOR_ID,
        "action": "revision_approved",
        "target_type": "revision",
        "target_id": TARGET_ID,
        "occurred_at": day(5),
    }
    values.update(overrides)
    return HistoryEventDraft(**values)


async def test_an_event_written_for_another_tenant_is_invisible(app_sessionmaker, migrate_engine):
    await seed_history_event(migrate_engine, id=EVENT_ID, workspace_id=WORKSPACE_A)
    await seed_history_event(migrate_engine, id=OTHER_EVENT_ID, workspace_id=WORKSPACE_B)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        seen = (await session.execute(SELECT_EVENT_IDS)).scalars().all()
    assert seen == [EVENT_ID]

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 2


async def test_a_pristine_connection_with_no_tenant_sees_nothing(app_sessionmaker, migrate_engine):
    """The setting was never touched on this backend, so it reads NULL."""
    await seed_history_event(migrate_engine, id=EVENT_ID, workspace_id=WORKSPACE_A)

    async with app_sessionmaker() as session, session.begin():
        assert (await session.execute(READ_TENANT_GUC)).scalar() is None
        assert (await session.execute(SELECT_EVENT_IDS)).all() == []

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 1


async def test_a_reused_connection_whose_tenant_reverted_sees_nothing(app_engine, migrate_engine):
    """Same backend, second transaction: the setting reverted to the empty string."""
    await seed_history_event(migrate_engine, id=EVENT_ID, workspace_id=WORKSPACE_A)

    async with app_engine.connect() as connection:
        async with connection.begin():
            await connection.execute(
                text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": WORKSPACE_A}
            )
            assert len((await connection.execute(SELECT_EVENT_IDS)).all()) == 1

        async with connection.begin():
            assert (await connection.execute(READ_TENANT_GUC)).scalar() == ""
            assert (await connection.execute(SELECT_EVENT_IDS)).all() == []

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 1


async def test_appending_a_draft_stamped_for_another_tenant_is_refused_by_with_check(
    app_sessionmaker, migrate_engine
):
    """ADR-0040 on this table: ``WITH CHECK`` is the whole defence.

    ``append()`` takes ``workspace_id`` from the draft and the session's tenant
    comes from a separate argument, so nothing in Python compares the two.
    """
    with pytest.raises(DBAPIError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await append(session, draft(workspace_id=WORKSPACE_B))

    assert "row-level security" in str(excinfo.value).lower()

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 0


async def test_the_same_append_inside_its_own_tenant_succeeds(app_sessionmaker, migrate_engine):
    """The vacuity guard: the refusal above is the mis-stamp, not ``append()``."""
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        event_id = await append(session, draft(scope_prompt_id=SCOPE_PROMPT_ID))

    async with migrate_engine.begin() as control:
        stored = (
            await control.execute(
                text("SELECT workspace_id FROM history.history_event WHERE id = :id"),
                {"id": event_id},
            )
        ).scalar_one()
    assert stored == WORKSPACE_A
