"""ADR-0038's loader, on a session that carries no tenant context.

Distinct from ``test_history_schema_ships_its_guarantees.py``'s SQL-level
assertion that thirty-seven rows are readable without a tenant: that one proves the
migration and the exemption, this one proves the **loader**.

**Any test of the vocabulary that opens ``workspace_transaction`` is a warning
sign** — if the registry is correct it does not need one, and if it needs one the
registry is wrong (Pitfall 7).

**The full vocabulary equality is Phase 5's AC-6 and is deliberately not asserted
here.** This file spot-checks two rows; comparing all thirty-seven against the five
lock files' event lists is the assertion that belongs beside the derivation.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.engine import build_sessionmaker
from prope.property_history.domain import RegisteredAction
from prope.property_history.registry import load_action_registry
from tests.property_history import COUNT_REGISTRY_ROWS

DELETE_REGISTRY = text("DELETE FROM history.history_action_registry")


async def test_the_registry_loads_on_a_session_with_no_tenant_context(
    app_sessionmaker: async_sessionmaker[AsyncSession],
):
    async with app_sessionmaker() as session:
        registry = await load_action_registry(session)

    assert len(registry) == 39
    assert all(isinstance(row, RegisteredAction) for row in registry.values())
    assert all(isinstance(row.detail_keys, frozenset) for row in registry.values())


async def test_the_loaded_mapping_cannot_be_mutated(
    app_sessionmaker: async_sessionmaker[AsyncSession],
):
    async with app_sessionmaker() as session:
        registry = await load_action_registry(session)

    with pytest.raises(TypeError):
        registry["invented_action"] = registry["revision_approved"]  # type: ignore[index]


async def test_two_known_rows_round_trip_with_their_declared_types(
    app_sessionmaker: async_sessionmaker[AsyncSession],
):
    async with app_sessionmaker() as session:
        registry = await load_action_registry(session)

    break_glass = registry["revision_break_glass_released"]
    assert break_glass.requires_reason is True
    assert break_glass.detail_keys == frozenset()
    assert break_glass.writing_module == "release-control"

    released = registry["revision_released"]
    assert released.requires_reason is False
    assert released.detail_keys == frozenset({"version_id", "previous_version_id", "break_glass"})
    assert released.target_type == "revision"


async def test_an_empty_registry_raises_naming_the_table(migrate_engine):
    """An empty vocabulary is a migration that did not run, not a bad append.

    The session is an OWNER one, built here: ``tests/conftest.py`` exposes an
    engine for ``prope_migrate`` and a sessionmaker for ``prope_app`` only, and
    ``prope_app`` holds no DELETE on the registry — reaching for it would produce
    the privilege refusal instead of the ``RuntimeError`` under test.
    """
    owner_sessionmaker = build_sessionmaker(migrate_engine)

    async with owner_sessionmaker() as session:
        await session.execute(DELETE_REGISTRY)

        with pytest.raises(RuntimeError) as excinfo:
            await load_action_registry(session)

        await session.rollback()

    assert "history.history_action_registry" in str(excinfo.value)

    # The seed survived: without this, the test could be passing because it had
    # already destroyed the vocabulary for every test after it.
    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_REGISTRY_ROWS)).scalar_one() == 39
