"""PH-02 / T-04-01: ``history.history_event`` is append-only by privilege.

ADR-0025's whole argument is that append-only belongs in the authorisation layer,
so the product's central claim is proven or disproven here rather than in any
application code — there is none for this schema yet, by design.

**Two failure modes shape this file.** ``history_event`` is RLS-scoped, so a
session with no tenant context sees zero rows and an ``UPDATE`` matching zero
rows is indistinguishable from an ``UPDATE`` the engine refused. Privilege is
checked *before* row security, so a row that is provably visible inside the
attempting transaction isolates the privilege from the policy — which is also
why the refusal reads ``permission denied for table history_event`` rather than
as a policy violation.

**The mutation check is the second.** A guarantee nobody can execute is not a
guarantee, and this run is autonomous, so it is a test rather than a procedure
written down for someone who is not there.

The seeded event names a **registered** ``(action, target_type)`` pair, because
``fk_history_event_action`` is real even for the owner. That is a second,
independent reason D-48's exclusion of the registry from the truncate fixture is
not optional: truncate it and every test in this file fails at its own seeding.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from prope.db.session import workspace_transaction
from tests.property_history import (
    COUNT_HISTORY_EVENTS,
    EVENT_ID,
    WORKSPACE_A,
    seed_history_event,
)

# Three mechanical rules, all three of which change what the assertions mean.
# The table name is SCHEMA-QUALIFIED in every probe, because an unqualified name
# resolves through the connection's search_path and two roles can have different
# ones. UPDATE and DELETE are probed SEPARATELY and never as 'UPDATE, DELETE',
# because the multi-privilege form answers "any of these" — the wrong question,
# in the direction that hides a bug. And has_table_privilege answers "does this
# role have this privilege" INCLUDING privileges held via PUBLIC and via role
# membership, so grant_table's `REVOKE ALL ... FROM PUBLIC` is what keeps the
# answer clean and must be present for these to mean what they look like.
APP_MAY_UPDATE_HISTORY_EVENT = text(
    "SELECT has_table_privilege('prope_app', 'history.history_event', 'UPDATE')"
)
APP_MAY_DELETE_HISTORY_EVENT = text(
    "SELECT has_table_privilege('prope_app', 'history.history_event', 'DELETE')"
)
APP_MAY_SELECT_HISTORY_EVENT = text(
    "SELECT has_table_privilege('prope_app', 'history.history_event', 'SELECT')"
)
APP_MAY_INSERT_HISTORY_EVENT = text(
    "SELECT has_table_privilege('prope_app', 'history.history_event', 'INSERT')"
)

APP_MAY_SELECT_REGISTRY = text(
    "SELECT has_table_privilege('prope_app', 'history.history_action_registry', 'SELECT')"
)
APP_MAY_INSERT_REGISTRY = text(
    "SELECT has_table_privilege('prope_app', 'history.history_action_registry', 'INSERT')"
)
APP_MAY_UPDATE_REGISTRY = text(
    "SELECT has_table_privilege('prope_app', 'history.history_action_registry', 'UPDATE')"
)
APP_MAY_DELETE_REGISTRY = text(
    "SELECT has_table_privilege('prope_app', 'history.history_action_registry', 'DELETE')"
)

REPORT_MAY_SELECT_HISTORY_EVENT = text(
    "SELECT has_table_privilege('prope_report', 'history.history_event', 'SELECT')"
)
REPORT_MAY_INSERT_HISTORY_EVENT = text(
    "SELECT has_table_privilege('prope_report', 'history.history_event', 'INSERT')"
)
REPORT_MAY_UPDATE_HISTORY_EVENT = text(
    "SELECT has_table_privilege('prope_report', 'history.history_event', 'UPDATE')"
)
REPORT_MAY_DELETE_HISTORY_EVENT = text(
    "SELECT has_table_privilege('prope_report', 'history.history_event', 'DELETE')"
)
REPORT_MAY_SELECT_REGISTRY = text(
    "SELECT has_table_privilege('prope_report', 'history.history_action_registry', 'SELECT')"
)
REPORT_MAY_INSERT_REGISTRY = text(
    "SELECT has_table_privilege('prope_report', 'history.history_action_registry', 'INSERT')"
)
REPORT_MAY_UPDATE_REGISTRY = text(
    "SELECT has_table_privilege('prope_report', 'history.history_action_registry', 'UPDATE')"
)
REPORT_MAY_DELETE_REGISTRY = text(
    "SELECT has_table_privilege('prope_report', 'history.history_action_registry', 'DELETE')"
)

UPDATE_HISTORY_EVENT = text(
    "UPDATE history.history_event SET reason = 'tidied up' WHERE id = :id"
)
DELETE_HISTORY_EVENT = text("DELETE FROM history.history_event WHERE id = :id")

GRANT_UPDATE_ON_HISTORY_EVENT = text("GRANT UPDATE ON history.history_event TO prope_app")
REVOKE_UPDATE_ON_HISTORY_EVENT = text("REVOKE UPDATE ON history.history_event FROM prope_app")


async def _refusal_text(app_sessionmaker, *, statement, parameters) -> str:
    """Attempt ``statement`` as ``prope_app`` where the seeded row IS visible.

    The visibility assertion runs inside the same transaction as the attempt.
    Without it, this whole file would pass against an empty table.
    """
    with pytest.raises(DBAPIError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            seen = (await session.execute(COUNT_HISTORY_EVENTS)).scalar_one()
            assert seen == 1, (
                "positive control failed: the seeded row is not visible to prope_app, "
                "so a refusal below would be indistinguishable from an empty table"
            )
            await session.execute(statement, parameters)
    return str(excinfo.value).lower()


async def test_update_on_history_event_is_refused_by_the_engine(app_sessionmaker, migrate_engine):
    """A correction is a new event, never an edit.

    ADR-0025 rejects a ``BEFORE UPDATE`` trigger by name — "a trigger is owned
    by the same role that owns the table, so the actor it is meant to stop can
    drop it" — and rejects a hash chain because it "detects tampering after the
    fact and prevents nothing, which is backwards for a log whose realistic
    threat is a well-meaning repair script, not a forger".
    """
    await seed_history_event(migrate_engine)

    message = await _refusal_text(
        app_sessionmaker, statement=UPDATE_HISTORY_EVENT, parameters={"id": EVENT_ID}
    )

    assert "permission denied" in message
    assert "history_event" in message


async def test_delete_on_history_event_is_refused_by_the_engine(app_sessionmaker, migrate_engine):
    """The half A-121's never-deleted guarantee rests on.

    The ``history`` counterpart of ``test_delete_on_call_record_is_refused_by_the_engine``
    with a stronger claim behind it: ``call_record`` retains ``UPDATE`` for the
    repricing path, and ``history_event`` retains neither.
    """
    await seed_history_event(migrate_engine)

    message = await _refusal_text(
        app_sessionmaker, statement=DELETE_HISTORY_EVENT, parameters={"id": EVENT_ID}
    )

    assert "permission denied" in message
    assert "history_event" in message


async def test_prope_app_holds_select_and_insert_on_history_event(migrate_engine):
    """The privileges whose *presence* is the guarantee.

    Without ``INSERT`` there is no append at all. Without ``SELECT`` the tenant
    policy's predicate cannot be evaluated — PostgreSQL requires ``SELECT`` on
    every column a statement references and the predicate references
    ``workspace_id`` — and Phase 5's ``read()`` cannot work. Asserted so a later
    "tighten the grants" pass cannot break the module silently.
    """
    async with migrate_engine.begin() as connection:
        assert (await connection.execute(APP_MAY_SELECT_HISTORY_EVENT)).scalar_one() is True
        assert (await connection.execute(APP_MAY_INSERT_HISTORY_EVENT)).scalar_one() is True
        assert (await connection.execute(APP_MAY_UPDATE_HISTORY_EVENT)).scalar_one() is False
        assert (await connection.execute(APP_MAY_DELETE_HISTORY_EVENT)).scalar_one() is False


async def test_the_registry_is_select_only_for_the_application_role(migrate_engine):
    """D-51, derived from ADR-0038 rather than chosen.

    It is what makes a process-lifetime cache with no invalidation safe: the
    only writer is ``prope_migrate``, the only write is a migration, and
    ADR-0031 restarts the application after migrating.
    """
    async with migrate_engine.begin() as connection:
        assert (await connection.execute(APP_MAY_SELECT_REGISTRY)).scalar_one() is True
        assert (await connection.execute(APP_MAY_INSERT_REGISTRY)).scalar_one() is False
        assert (await connection.execute(APP_MAY_UPDATE_REGISTRY)).scalar_one() is False
        assert (await connection.execute(APP_MAY_DELETE_REGISTRY)).scalar_one() is False


async def test_prope_report_reads_both_tables_and_writes_neither(migrate_engine):
    """ADR-0037's argument, not ``grant_table``'s default.

    A-126's cross-workspace Success SQL reads ``history_event``; withholding
    ``SELECT`` here would send that query back to ``prope_migrate`` — the only
    role that can delete a history row, and precisely the outcome ADR-0037
    exists to prevent.
    """
    async with migrate_engine.begin() as connection:
        assert (await connection.execute(REPORT_MAY_SELECT_HISTORY_EVENT)).scalar_one() is True
        assert (await connection.execute(REPORT_MAY_SELECT_REGISTRY)).scalar_one() is True

        for probe in (
            REPORT_MAY_INSERT_HISTORY_EVENT,
            REPORT_MAY_UPDATE_HISTORY_EVENT,
            REPORT_MAY_DELETE_HISTORY_EVENT,
            REPORT_MAY_INSERT_REGISTRY,
            REPORT_MAY_UPDATE_REGISTRY,
            REPORT_MAY_DELETE_REGISTRY,
        ):
            assert (await connection.execute(probe)).scalar_one() is False


async def test_the_append_only_refusal_has_teeth(app_sessionmaker, migrate_engine):
    """The mutation check, as a test rather than as a procedure nobody runs.

    ``UPDATE`` rather than ``DELETE`` is mutation-tested because ``UPDATE`` is
    the one a well-meaning repair script actually reaches for — ADR-0025 names
    the realistic threat as "a data-repair script during the pilot, a backfill
    correcting a mis-stamped scope, or a developer fixing a typo in a reason
    string as a kindness". ``DELETE``'s absence is covered by the plain refusal
    above plus this test proving the probe is pointed at the right object at
    all: a test asserting ``is False`` against a mis-*targeted* table would also
    pass, and only the grant/observe/revoke cycle distinguishes a real absence
    from a typo.

    The ``finally`` is what stops a failure inside the granted window from
    leaving ``prope_app`` holding ``UPDATE`` on the audit log for every test that
    follows in the session.
    """
    await seed_history_event(migrate_engine)

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(APP_MAY_UPDATE_HISTORY_EVENT)).scalar_one() is False

    try:
        async with migrate_engine.begin() as connection:
            await connection.execute(GRANT_UPDATE_ON_HISTORY_EVENT)

        async with migrate_engine.begin() as connection:
            assert (await connection.execute(APP_MAY_UPDATE_HISTORY_EVENT)).scalar_one() is True

        # A fresh transaction: privilege is re-checked per statement, but the
        # committed grant has to be visible to the statement that tests it.
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            assert (await session.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 1
            result = await session.execute(UPDATE_HISTORY_EVENT, {"id": EVENT_ID})
            assert result.rowcount == 1, (
                "with UPDATE granted the write should land; if it did not, the "
                "refusal tests above may be passing for some other reason"
            )
    finally:
        async with migrate_engine.begin() as connection:
            await connection.execute(REVOKE_UPDATE_ON_HISTORY_EVENT)

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(APP_MAY_UPDATE_HISTORY_EVENT)).scalar_one() is False
