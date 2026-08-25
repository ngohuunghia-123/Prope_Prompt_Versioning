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
from tests.property_history import REGISTRY_ACTION_COUNT

#: Alphabetical within each schema, because the query below orders by both.
#: ``workspace_retention`` joins at revision 0004 (D-09), the two ``history``
#: tables at 0005, the eight ``access`` tables at 0006, the three ``provider``
#: tables at 0007, the two ``registry`` tables at 0008, the four
#: ``evaluation`` tables at 0009 and the three ``release`` tables at 0010 — a deliberately explicit list, so a table
#: appearing or vanishing from a pristine upgrade is an edit somebody made
#: rather than a count that quietly moved.
#:
#: Later arrivals, each named with the revision that brought it:
#: ``evaluation.dataset_attachment`` at 0018, ``evaluation.dataset`` and
#: ``evaluation.dataset_case`` at 0019, and ``access.workspace_invite`` at 0022
#: (ADR-0057 — the ninth ``access`` table, so the count above reads eight).
SCHEMA_TABLES = {
    "access": (
        "api_key",
        # ADR-0061, revision 0026. `prompt_grant` one scope up, and the only
        # per-subject table in this schema that names a STRING rather than a row
        # id — A-157, which is what lets a grant be written before the folder
        # exists and survive it being deleted.
        "namespace_grant",
        "prompt_grant",
        "role_binding",
        "role_permission",
        "session",
        "user",
        "workspace",
        "workspace_invite",
        "workspace_member",
    ),
    # Revision 0038. The agent run and the trace graph it records.
    "agent": ("edge", "node", "run"),
    # Revision 0015 — which is to say this schema has existed for thirty-one
    # revisions and appeared in no assertion in this file until now. See the
    # note above `LIST_OWNED_TABLES`.
    "chat": ("conversation", "message", "message_feedback", "pending_action"),
    "evaluation": (
        "case_result",
        "dataset",
        "dataset_attachment",
        "dataset_case",
        "eval_case",
        "eval_run",
        "eval_suite",
    ),
    "history": ("history_action_registry", "history_event"),
    # Revision 0033.
    "improvement": ("finding", "proposal", "schedule", "sweep"),
    # Revision 0041.
    "ingestion": ("commit_proposal", "import_batch", "import_item"),
    "ledger": (
        "call_body",
        "call_record",
        "price_table",
        "spend_ceiling",
        "workspace_retention",
        "workspace_spend",
    ),
    # ADR-0060, revision 0040. Its own schema rather than a table in `ledger`,
    # because ADR-0018 gives that schema's bodies no reader and these have one —
    # an inbox, a drift view, a redact route and a person acting on all three.
    "observation": ("observation", "sighting"),
    "provider": ("credential", "model_catalogue", "provider_config"),
    # Revision 0042.
    "readiness": ("dismissal", "lane_b_cache", "probe_case_result", "probe_run", "report"),
    # `call_annotation` at revision 0039.
    "registry": ("call_annotation", "folder", "prompt_property", "revision"),
    "release": ("approval", "release", "review_task"),
    "search": ("embedding_cache", "prompt_search_index", "prompt_search_index_job"),
}

#: Every schema the chain owns, as a SQL literal list, written once. The three
#: queries below used to carry three hand-maintained copies of it, and that is
#: the mechanism by which this file went stale: a migration adds a schema, the
#: author updates none of the copies because nothing tells them to, and the test
#: keeps passing while checking less. Derived from `SCHEMA_TABLES` so the
#: catalogue above is the single place a schema is declared.
SCHEMA_LITERALS = ", ".join(f"'{schema}'" for schema in sorted(SCHEMA_TABLES))

#: **Every non-system schema, not a list of the ones we remembered.** This query
#: used to name nine schemas explicitly, and a schema absent from that list was
#: absent from the assertion — so `chat` (revision 0015), `improvement` (0033),
#: `agent` (0038), `ingestion` (0041) and `readiness` (0042) were created,
#: populated and never once compared against anything here. Seventeen tables in
#: a test whose stated purpose is that "a table appearing or vanishing from a
#: pristine upgrade is an edit somebody made rather than a count that quietly
#: moved". An allow-list cannot catch the thing it was written to catch, because
#: the failure mode IS forgetting to extend the allow-list. Asking the database
#: what it has and comparing that to `SCHEMA_TABLES` turns a new schema into a
#: red test on the migration that introduces it.
#:
#: `public` is excluded because `alembic_version` lives there and is asserted
#: separately, and because an extension may put objects in it.
LIST_OWNED_TABLES = text(
    "SELECT schemaname, tablename FROM pg_tables "
    r"WHERE schemaname NOT LIKE 'pg\_%' "
    "AND schemaname NOT IN ('information_schema', 'public') "
    "ORDER BY schemaname, tablename"
)

LIST_ROLES = text(
    "SELECT rolname, rolbypassrls FROM pg_roles "
    "WHERE rolname LIKE 'prope\\_%' ORDER BY rolname"
)

READ_ALEMBIC_VERSION = text("SELECT version_num FROM public.alembic_version")

#: Everything a second upgrade could plausibly disturb: column shapes, defaults,
#: nullability, and every policy predicate.
SNAPSHOT_COLUMNS = text(
    f"""
    SELECT table_schema, table_name, column_name, ordinal_position, data_type,
           is_nullable, column_default, numeric_precision, numeric_scale
    FROM   information_schema.columns
    WHERE  table_schema IN ({SCHEMA_LITERALS})
    ORDER  BY table_schema, table_name, ordinal_position
    """
)

SNAPSHOT_POLICIES = text(
    f"""
    SELECT schemaname, tablename, policyname, permissive, roles::text, cmd, qual, with_check
    FROM   pg_policies
    WHERE  schemaname IN ({SCHEMA_LITERALS})
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
    with PostgresContainer("pgvector/pgvector:pg17", driver="asyncpg") as container:
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
    """The roles, the bypass attribute, every table the chain owns, and the recorded head."""
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
    # The count and its per-revision derivation live in
    # `tests.property_history.REGISTRY_ACTION_COUNT`, because this literal was
    # written out here and in three other places and the four had drifted to two
    # different values. The FK from `history_event` to this registry is what
    # makes the seed load-bearing rather than documentation: an event written
    # under an unregistered action is refused by the database, so a missing seed
    # is a route that 500s.
    assert before[3] == [(REGISTRY_ACTION_COUNT,)], (
        "the vocabulary seed did not land, so its count proves nothing"
    )
    assert after == before


def test_the_revision_chain_has_exactly_one_head():
    """D-04. Fourteen schemas, one linear hand-written history, one
    ``alembic upgrade head`` per deploy. A second head would make cross-schema
    ordering — roles before any policy — inexpressible in the chain, and no
    container is needed to notice it."""
    heads = ScriptDirectory.from_config(_alembic_config()).get_heads()

    assert len(heads) == 1, f"the chain branched: {heads}"
