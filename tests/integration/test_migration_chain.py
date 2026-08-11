"""D-05: a pristine cluster reaches head, and a second upgrade changes nothing.

The rig gets an empty ``postgres:17`` on every run, so ``alembic upgrade head``
against an empty cluster *is* the provisioning path — not a convenience. Any
second path (a hand-run bootstrap script, a compose init file) would drift from
this one, and the first drift reads as green CI over a broken deploy. That is
the drift D-02 rejected, and this file is what makes the rejection checkable.

The container here is deliberately **not** the session-scoped one from
``conftest``. That one has already been upgraded, so running the chain against
it would prove only that a second run is quiet — never that an empty cluster
reaches a working database.
"""

import asyncio
import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

from prope.db.engine import build_engine
from tests.conftest import PROJECT_ROOT, _upgrade_to_head

#: Alphabetical within each schema, because the query below orders by both.
#: ``workspace_retention`` joins at revision 0004 (D-09) and the two ``history``
#: tables at 0005 — a deliberately explicit list, so a table appearing or
#: vanishing from a pristine upgrade is an edit somebody made rather than a
#: count that quietly moved.
SCHEMA_TABLES = {
    "history": ("history_action_registry", "history_event"),
    "ledger": (
        "call_body",
        "call_record",
        "price_table",
        "spend_ceiling",
        "workspace_retention",
        "workspace_spend",
    ),
}

#: Two-schema literals rather than ``= ANY(:schemas)``: ``_query_all`` below
#: takes its statements as varargs and executes them with no parameter dict, so
#: binding would mean changing a shared test utility in the same change as a
#: migration. Literals also match how this file already writes SQL.
LIST_OWNED_TABLES = text(
    "SELECT schemaname, tablename FROM pg_tables "
    "WHERE schemaname IN ('history', 'ledger') ORDER BY schemaname, tablename"
)

LIST_ROLES = text(
    "SELECT rolname, rolbypassrls FROM pg_roles "
    "WHERE rolname LIKE 'prope\\_%' ORDER BY rolname"
)

READ_ALEMBIC_VERSION = text("SELECT version_num FROM public.alembic_version")

#: Everything a second upgrade could plausibly disturb: column shapes, defaults,
#: nullability, and every policy predicate.
SNAPSHOT_COLUMNS = text(
    """
    SELECT table_schema, table_name, column_name, ordinal_position, data_type,
           is_nullable, column_default, numeric_precision, numeric_scale
    FROM   information_schema.columns
    WHERE  table_schema IN ('history', 'ledger')
    ORDER  BY table_schema, table_name, ordinal_position
    """
)

SNAPSHOT_POLICIES = text(
    """
    SELECT schemaname, tablename, policyname, permissive, roles::text, cmd, qual, with_check
    FROM   pg_policies
    WHERE  schemaname IN ('history', 'ledger')
    ORDER  BY schemaname, tablename, policyname
    """
)

#: What this can catch, and what it cannot. It CANNOT catch a double-apply of
#: revision 0005: the test below re-runs ``alembic upgrade head`` against a
#: cluster already stamped at head, so no revision body executes. What it is for
#: is the NEXT migration — one that re-seeds, back-fills or widens the
#: vocabulary moves this count, and the snapshot turns that into a red test at
#: the moment it is written rather than a discovery in production.
SNAPSHOT_REGISTRY_COUNT = text("SELECT count(*) FROM history.history_action_registry")


def _alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return config


@pytest.fixture(scope="module")
def pristine_container() -> Iterator[PostgresContainer]:
    """An empty ``postgres:17``, upgraded to head exactly once.

    ``_upgrade_to_head`` sets ``PROPE_DATABASE_URL`` process-wide, so the prior
    value is restored on the way out rather than left pointing at a container
    that no longer exists.
    """
    previous = os.environ.get("PROPE_DATABASE_URL")
    with PostgresContainer("postgres:17", driver="asyncpg") as container:
        _upgrade_to_head(container)
        try:
            yield container
        finally:
            if previous is None:
                os.environ.pop("PROPE_DATABASE_URL", None)
            else:
                os.environ["PROPE_DATABASE_URL"] = previous


async def _query_all(url: str, *statements):
    """Read from a container over its own superuser URL, then dispose."""
    engine = build_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            return [(await connection.execute(statement)).all() for statement in statements]
    finally:
        await engine.dispose()


async def test_an_empty_cluster_reaches_head_and_yields_a_working_database(pristine_container):
    """The roles, the bypass attribute, all eight tables, and the recorded head."""
    (versions, roles, tables) = await _query_all(
        pristine_container.get_connection_url(),
        READ_ALEMBIC_VERSION,
        LIST_ROLES,
        LIST_OWNED_TABLES,
    )

    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()

    assert [row[0] for row in versions] == [head]
    assert [(row[0], row[1]) for row in roles] == [
        ("prope_app", False),
        ("prope_migrate", False),
        # ADR-0037's reporting credential reads across workspaces, which is an
        # attribute of the ROLE and cannot be granted by a non-superuser
        # (Pitfall 12). If this is False the migration ran without one.
        ("prope_report", True),
    ]
    assert [(row[0], row[1]) for row in tables] == [
        (schema, table) for schema in sorted(SCHEMA_TABLES) for table in SCHEMA_TABLES[schema]
    ]


async def test_running_the_chain_a_second_time_is_a_no_op(pristine_container):
    """Not merely "exits 0": byte-identical column, policy and seed catalogues."""
    url = pristine_container.get_connection_url()

    before = await _query_all(
        url, READ_ALEMBIC_VERSION, SNAPSHOT_COLUMNS, SNAPSHOT_POLICIES, SNAPSHOT_REGISTRY_COUNT
    )

    # In a worker thread on purpose. Alembic's `command.upgrade` is synchronous,
    # and this project's async `env.py` drives it with `asyncio.run` — which
    # refuses to start while this test's own event loop is running. The fixture
    # above escapes this by being a sync fixture; here the escape has to be
    # explicit.
    await asyncio.to_thread(_upgrade_to_head, pristine_container)

    after = await _query_all(
        url, READ_ALEMBIC_VERSION, SNAPSHOT_COLUMNS, SNAPSHOT_POLICIES, SNAPSHOT_REGISTRY_COUNT
    )

    assert before[1], "the column snapshot is empty — the comparison would be vacuous"
    assert before[2], "the policy snapshot is empty — the comparison would be vacuous"
    assert before[3] == [(31,)], "the vocabulary seed did not land, so its count proves nothing"
    assert after == before


def test_the_revision_chain_has_exactly_one_head():
    """D-04. Eight schemas, one linear hand-written history, one
    ``alembic upgrade head`` per deploy. A second head would make cross-schema
    ordering — roles before any policy — inexpressible in the chain, and no
    container is needed to notice it."""
    heads = ScriptDirectory.from_config(_alembic_config()).get_heads()

    assert len(heads) == 1, f"the chain branched: {heads}"
