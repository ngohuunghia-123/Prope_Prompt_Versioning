"""D-72: a cross-workspace read is a refusal with a name, never an empty Activity.

The lock says the read API scopes every query by ``workspace_id`` at the function
boundary *"so a caller cannot construct a cross-workspace read even by supplying
the wrong ids"*. Under RLS alone that sentence is true about **rows returned**
and false about **reads constructed** — the caller does construct one and gets a
plausible answer back. These four tests are what make it true as written.

Every refusal here carries the positive control this repository requires of one
(``test_tenant_isolation.py`` is the register): the same scope, inside its own
workspace's transaction, returns the rows. Without that a refusal is
indistinguishable from an empty table.
"""

import pytest

from prope.db.session import workspace_transaction
from prope.property_history.domain import HistoryScopeMismatch, PromptScope
from prope.property_history.read import read
from tests.property_history import (
    EVENT_ID,
    OTHER_EVENT_ID,
    SCOPE_PROMPT_ID,
    WORKSPACE_A,
    WORKSPACE_B,
    counting_statements,
    seed_history_event,
)

EMPTY_SCOPE_PROMPT_ID = "prm_01J0000000000000000000009"


async def test_a_scope_naming_another_workspace_is_refused(app_sessionmaker, migrate_engine):
    """The refusal names both ids, and the positive control proves the rows were there."""
    await seed_history_event(migrate_engine, id=EVENT_ID, workspace_id=WORKSPACE_B)
    scope = PromptScope(WORKSPACE_B, SCOPE_PROMPT_ID)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        with pytest.raises(HistoryScopeMismatch) as excinfo:
            await read(session, scope)

    message = str(excinfo.value)
    assert WORKSPACE_A in message
    assert WORKSPACE_B in message

    async with workspace_transaction(app_sessionmaker, WORKSPACE_B) as session:
        events = await read(session, scope)

    assert [event.id for event in events] == [EVENT_ID]


async def test_a_session_with_no_tenant_is_refused(app_sessionmaker, migrate_engine):
    """The mistake this refusal is worth the most against.

    A plain session returns zero rows for every scope, forever, and looks exactly
    like an audit log with nothing in it. The message names the seam that fixes
    it rather than the setting that is missing.
    """
    await seed_history_event(migrate_engine, id=EVENT_ID, workspace_id=WORKSPACE_A)
    scope = PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID)

    async with app_sessionmaker() as session:
        with pytest.raises(HistoryScopeMismatch) as excinfo:
            await read(session, scope)

    assert "workspace_transaction" in str(excinfo.value)
    assert excinfo.value.session_workspace_id is None

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert [event.id for event in await read(session, scope)] == [EVENT_ID]


async def test_a_genuinely_empty_scope_returns_empty(app_sessionmaker, migrate_engine):
    """The vacuity guard, and what stops the refusal becoming a blanket one.

    Correct workspace, correct tenant, a prompt with no events: still ``()``,
    still no exception. A test suite that only asserted the two refusals would
    pass against a ``read()`` that raised on every empty result.
    """
    await seed_history_event(migrate_engine, id=EVENT_ID, workspace_id=WORKSPACE_A)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert await read(session, PromptScope(WORKSPACE_A, EMPTY_SCOPE_PROMPT_ID)) == ()


async def test_a_populated_read_issues_one_statement_and_an_empty_one_issues_two(
    app_sessionmaker, app_engine, migrate_engine
):
    """The adoption's whole refinement, asserted rather than described.

    "The diagnosis runs on the empty path" is a claim about where two lines sit
    in a function, and somebody can move them. This is what notices.
    """
    await seed_history_event(migrate_engine, id=OTHER_EVENT_ID, workspace_id=WORKSPACE_A)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        with counting_statements(app_engine) as populated:
            assert len(await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID))) == 1

        with counting_statements(app_engine) as empty:
            assert await read(session, PromptScope(WORKSPACE_A, EMPTY_SCOPE_PROMPT_ID)) == ()

    assert len(populated) == 1, populated
    assert len(empty) == 2, empty
    assert "current_setting" in empty[1]
