"""Invariants that are cheap to assert now and expensive to discover late.

Each of these is a rule stated somewhere in prose — an ADR, a lock file, a
research pitfall — and each becomes false the moment a later revision breaks it
without anyone noticing. Written as a query over the *live* catalogue rather
than as a reading of the migration source: reading the source proves the source
says so, not that the database does.
"""

import pytest
from sqlalchemy import text

# A drift guard only sees tables whose module has been IMPORTED. Without these
# imports the access and history walks find an empty declaration set and pass
# vacuously — the failure shape test_tenant_coverage.py and
# test_no_sql_interpolation.py both exist to refuse.
from prope.access_control import models as access_models
from prope.call_ledger import models
from prope.chat_orchestrator import models as chat_models  # noqa: F401
from prope.evaluation import models as evaluation_models
from prope.prompt_registry import models as registry_models
from prope.prompt_search import models as search_models
from prope.property_history import models as history_models
from prope.provider_access import models as provider_models
from prope.release_control import models as release_models  # noqa: F401

#: The five tests below this constant are project rules, not ledger rules, so
#: they run against every schema that exists. Copying them into a
#: history-specific file was refused on D-06's grounds: a rule asserted in two
#: files drifts, and the copy that stops being maintained is invisible. There is
#: deliberately no module-level ``SCHEMA``; the three ledger-specific tests
#: carry their own literal, because a module constant beside a parameter is how
#: the two drift.
GENERIC_SCHEMAS = (
    "access",
    "chat",
    "evaluation",
    "history",
    "ledger",
    # prompt-observation, added with ADR-0060. Two tables, both tenant-scoped,
    # neither exempt — and this is the schema where a missing policy would cost
    # the most: every row in it is a customer's production system prompt that
    # arrived without anybody choosing to submit it.
    "observation",
    "provider",
    "registry",
    "release",
    "search",
)

#: **Per schema, as a literal**, because "zero everywhere" stopped being true in
#: revision 0006 and the honest replacement is a named set rather than a skip.
#:
#: The sanctioned project-wide set is exactly four (CLAUDE.md), and as of
#: phase 16 all four exist. Two answer the bootstrap problem — a session and an
#: API key must be resolved *before* a tenant is known, so they cannot run under
#: the policy they produce. ``list_workspaces`` enumerates tenants for the
#: tombstone, which is by definition cross-tenant. And ``claim_next_run``
#: answers the same shape one layer out (ADR-0049): a queued eval run's
#: workspace is not known until the claim, **because the claim is what produces
#: it** — ADR-0042's own justification word for word, which is why the count
#: moving from three to four was a review rather than a new argument. It returns
#: five identifiers and no content, and every read after it runs under ordinary
#: RLS from the workspace that tuple named.
#:
#: A fifth is a designed-in failure, not a fix.
EXPECTED_SECURITY_DEFINER = {
    "access": ["list_workspaces", "lookup_api_key", "lookup_session"],
    "evaluation": ["claim_next_run"],
    "history": [],
    "ledger": [],
    #: Prompt-observation adds NONE, for release-control's reason below. The one
    #: read that could have tempted a fifth function — *which namespaces does this
    #: workspace use*, which the gateway needs before it can decide to forward —
    #: is answered by INT-036 in prompt-registry under ordinary RLS, on an edge
    #: that already runs the right way. ADR-0062 records why it is not in
    #: access-control, and this empty list is the other half of that decision.
    "observation": [],
    "provider": [],
    "registry": [],
    #: Release-control adds NONE, and that is the point of ADR-0051's rule about
    #: shape. Its two `worker` sweeps must read across every workspace, and they
    #: do it by calling `access.list_workspaces()` — an EXISTING sanctioned
    #: function returning tenant IDENTIFIERS — then issuing `SET LOCAL
    #: app.workspace_id` per workspace and running ordinary policied queries. A
    #: fifth function returning ROWS would have performed the read inside the
    #: bypass, which is exactly what ADR-0051 refuses by name.
    "release": [],
    "chat": [],
    "search": [],
}

#: ``schema.table.constraint -> the written reason it is allowed to leave its
#: schema``. Same escape-hatch shape as ``test_tenant_coverage.GLOBAL_TABLES``,
#: and for the same reason: an exemption should be a sentence somebody signed
#: rather than a silent hole in the walk below.
SANCTIONED_CROSS_SCHEMA_FOREIGN_KEYS: dict[str, str] = {
    "registry.revision.fk_revision_provider_config_id": (
        "INT-016 names this foreign key as the MECHANISM, not as an implementation detail: "
        "'DELETE /api/v1/providers/{id} is refused while a revision binds the configuration, and "
        "that refusal comes from the foreign key revision.provider_config_id, NOT from "
        "provider-access asking prompt-registry. That edge does not exist.' The shipped "
        "`delete_provider` command already relies on it — `ErrorCode.PROVIDER_BOUND_BY_REVISIONS` "
        "is raised from the IntegrityError this constraint produces. Removing it would require "
        "either a cross-module read (provider-access querying registry.revision, which its own "
        "import allow-list forbids) or the forbidden reverse edge. "
        "THE COST, STATED RATHER THAN WAVED AWAY: referential-integrity checks bypass row "
        "security, so an INSERT naming another workspace's provider_config_id succeeds where a "
        "nonexistent one raises — an existence oracle over `prv_` ULIDs. It is narrow (the caller "
        "must guess a 26-character ULID, and RLS still returns zero rows for every read of the "
        "referenced table) and it is the price INT-016's stated direction charges."
    ),
}
SECURITY_DEFINER_FUNCTIONS = text(
    """
    SELECT p.proname
    FROM   pg_proc p
    JOIN   pg_namespace n ON n.oid = p.pronamespace
    WHERE  n.nspname = :schema AND p.prosecdef
    """
)

NATIVE_ENUM_TYPES = text(
    """
    SELECT t.typname
    FROM   pg_type t
    JOIN   pg_namespace n ON n.oid = t.typnamespace
    WHERE  n.nspname = :schema AND t.typtype = 'e'
    """
)

#: Joined through pg_namespace and compared by ``nspname``. Deliberately NOT
#: ``confrelid::regclass::text``: regclass omits the schema qualifier whenever
#: that schema is on the connection's search_path, so a correct intra-ledger key
#: renders as bare ``call_record`` on some connections and as ``ledger.call_record``
#: on others — and a text test flips to a false result depending on who is
#: connected.
FOREIGN_KEYS_LEAVING_SCHEMA = text(
    """
    SELECT c.relname || '.' || con.conname || ' -> ' || rn.nspname || '.' || rc.relname
    FROM   pg_constraint con
    JOIN   pg_class     c  ON c.oid  = con.conrelid
    JOIN   pg_namespace n  ON n.oid  = c.relnamespace
    JOIN   pg_class     rc ON rc.oid = con.confrelid
    JOIN   pg_namespace rn ON rn.oid = rc.relnamespace
    WHERE  n.nspname = :schema AND con.contype = 'f' AND rn.nspname <> :schema
    """
)

TIME_COLUMNS = text(
    """
    SELECT table_name, column_name, data_type
    FROM   information_schema.columns
    WHERE  table_schema = :schema
      AND  (column_name LIKE '%\\_at' OR column_name LIKE '%\\_from')
    """
)

MONEY_COLUMNS = text(
    """
    SELECT table_name, column_name, numeric_precision, numeric_scale
    FROM   information_schema.columns
    WHERE  table_schema = :schema AND column_name = ANY(:names)
    """
)

FLOATING_POINT_COLUMNS = text(
    """
    SELECT table_name, column_name, data_type
    FROM   information_schema.columns
    WHERE  table_schema = :schema AND data_type IN ('double precision', 'real')
    """
)

CALL_RECORD_TIMESTAMP_DEFAULTS = text(
    """
    SELECT column_name, column_default
    FROM   information_schema.columns
    WHERE  table_schema = :schema AND table_name = 'call_record'
      AND  column_name IN ('created_at', 'written_at')
    """
)

LIVE_COLUMNS = text(
    """
    SELECT table_name, column_name
    FROM   information_schema.columns
    WHERE  table_schema = :schema
    """
)

MONEY_COLUMN_NAMES = [
    "cost",
    "total_cost",
    "input_price_per_1k",
    "output_price_per_1k",
    # Migration 0017. The same scale as `cost` on purpose: it is compared
    # against one in `compute_cost`, and a floor at a coarser scale would be a
    # figure the comparison had to widen.
    "minimum_charge_per_request",
    "monthly_limit",
    "per_run_limit",
]


@pytest.mark.parametrize("schema", GENERIC_SCHEMAS)
async def test_the_schema_contains_no_security_definer_function(migrate_engine, schema):
    """T-01-11. Exactly the sanctioned set, per schema, in both directions."""
    async with migrate_engine.begin() as connection:
        functions = (
            await connection.execute(SECURITY_DEFINER_FUNCTIONS, {"schema": schema})
        ).scalars().all()

    assert sorted(functions) == EXPECTED_SECURITY_DEFINER[schema], (
        f"the SECURITY DEFINER set in {schema} moved. The sanctioned set is exactly "
        "access.lookup_session, access.lookup_api_key, access.list_workspaces() and "
        "evaluation.claim_next_run(); a fifth is a designed-in failure, not a fix."
    )


@pytest.mark.parametrize("schema", GENERIC_SCHEMAS)
async def test_no_native_enum_type_exists_in_the_schema(migrate_engine, schema):
    """Pitfall 4. Adding a value to a native enum cannot run inside a
    transaction block, and removing one is impossible at any price. Vocabularies
    are ``text`` plus a named CHECK."""
    async with migrate_engine.begin() as connection:
        enums = (await connection.execute(NATIVE_ENUM_TYPES, {"schema": schema})).scalars().all()

    assert enums == []


@pytest.mark.parametrize("schema", GENERIC_SCHEMAS)
async def test_no_foreign_key_leaves_the_schema(migrate_engine, schema):
    """T-01-09. PostgreSQL documents that referential-integrity checks always
    bypass row security, so a foreign key from a tenant-scoped table to another
    schema's table is a covert channel across tenants — quite apart from being
    the way a sink module quietly acquires an outbound edge.

    One exemption exists and it is declared rather than skipped — see
    :data:`SANCTIONED_CROSS_SCHEMA_FOREIGN_KEYS`, which carries the argument for
    it and the cost it charges.
    """
    async with migrate_engine.begin() as connection:
        escaping = (
            await connection.execute(FOREIGN_KEYS_LEAVING_SCHEMA, {"schema": schema})
        ).scalars().all()

    undeclared = [
        edge
        for edge in escaping
        if f"{schema}.{edge.split(' -> ')[0]}" not in SANCTIONED_CROSS_SCHEMA_FOREIGN_KEYS
    ]

    assert undeclared == [], f"foreign keys leaving {schema}: {undeclared}"


def test_every_cross_schema_foreign_key_exemption_carries_a_written_reason() -> None:
    """The escape hatch cannot be used blank, exactly as ``GLOBAL_TABLES``' cannot.

    This dict is where a reviewer looks to find every foreign key in Prope that
    crosses a bounded context, so an entry with no argument attached defeats the
    only purpose it has.
    """
    blank = [
        name
        for name, reason in SANCTIONED_CROSS_SCHEMA_FOREIGN_KEYS.items()
        if not reason.strip()
    ]

    assert blank == [], f"cross-schema foreign keys with no written reason: {blank}"


@pytest.mark.parametrize("schema", GENERIC_SCHEMAS)
async def test_every_timestamp_column_carries_a_time_zone(migrate_engine, schema):
    """A-003 / Pitfall 7. ``timestamp without time zone`` silently discards the
    offset, and AC-3's day-5/day-12/day-20 arithmetic then passes or fails by
    geography."""
    async with migrate_engine.begin() as connection:
        columns = (await connection.execute(TIME_COLUMNS, {"schema": schema})).all()

    # Per-schema and intentional: `history` passes because `occurred_at`
    # matches. A later schema with no _at column at all trips this, which is the
    # correct behaviour and not a bug to fix by weakening the guard.
    assert columns, "no _at / _from columns found — the query, not the schema, is wrong"
    naive = [
        f"{table}.{column} is {data_type}"
        for table, column, data_type in columns
        if data_type != "timestamp with time zone"
    ]
    assert naive == []


async def test_every_money_column_is_numeric_20_10(migrate_engine):
    """Wide enough for a USD price of order 0.00002 per 1k tokens and a VND
    price of order 1000. The same scale on prices and on costs so the arithmetic
    never widens or narrows."""
    async with migrate_engine.begin() as connection:
        columns = (
            await connection.execute(
                MONEY_COLUMNS, {"schema": "ledger", "names": MONEY_COLUMN_NAMES}
            )
        ).all()

    assert len(columns) == 7, f"expected seven money columns across ledger, found {columns}"
    wrong = [
        f"{table}.{column} is numeric({precision},{scale})"
        for table, column, precision, scale in columns
        if (precision, scale) != (20, 10)
    ]
    assert wrong == []


@pytest.mark.parametrize("schema", GENERIC_SCHEMAS)
async def test_no_column_has_a_floating_point_type(migrate_engine, schema):
    """Pitfall 5. Float arithmetic makes a cost non-reproducible, and ADR-0019's
    whole point is a figure that can be re-derived years later."""
    async with migrate_engine.begin() as connection:
        floats = (
            await connection.execute(FLOATING_POINT_COLUMNS, {"schema": schema})
        ).all()

    assert floats == []


async def test_created_at_has_no_default_while_written_at_does(migrate_engine):
    """The single easiest way to get CL-03 subtly wrong. A default on
    ``created_at`` prices a backlogged record at drain time, so a call made on
    day 5 and written on day 12 is priced at day 12 — and the test passes on an
    idle machine and fails under load."""
    async with migrate_engine.begin() as connection:
        defaults = dict(
            (await connection.execute(CALL_RECORD_TIMESTAMP_DEFAULTS, {"schema": "ledger"})).all()
        )

    assert defaults["created_at"] is None
    assert defaults["written_at"] is not None


async def test_every_declared_model_matches_a_live_table(migrate_engine):
    """A drift guard, not a schema definition.

    ``prope.call_ledger.models`` exists for the application to query and is
    never the source of truth for DDL — the migration is (D-04). That split only
    stays safe if something notices when the two disagree, so: every column the
    models declare must exist live, with the live table free to carry more.
    """
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(LIVE_COLUMNS, {"schema": "ledger"})).all()

    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)

    declared = [table for table in models.metadata.tables.values() if table.schema == "ledger"]
    # Six since revision 0004. The lock file's ``data.owns`` names five; the
    # sixth is D-09's declared deviation, raised as OQ-018 rather than absorbed.
    # The count is pinned rather than derived so that adding a table to the
    # module is a visible edit here, which is the whole point of a drift guard.
    assert len(declared) == 6

    drift = []
    for table in declared:
        if table.name not in live:
            drift.append(f"{table.name}: declared in models, absent from the database")
            continue
        missing = {column.name for column in table.columns} - live[table.name]
        if missing:
            drift.append(f"{table.name}: columns declared but not live: {sorted(missing)}")

    assert drift == [], "; ".join(drift)


async def test_every_declared_search_model_matches_a_live_table(migrate_engine):
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(LIVE_COLUMNS, {"schema": "search"})).all()

    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)

    declared = [
        table for table in search_models.metadata.tables.values() if table.schema == "search"
    ]
    assert len(declared) == 2
    drift = []
    for table in declared:
        if table.name not in live:
            drift.append(f"{table.name}: declared in models, absent from the database")
            continue
        missing = {column.name for column in table.columns} - live[table.name]
        if missing:
            drift.append(f"{table.name}: columns declared but not live: {sorted(missing)}")
    assert drift == [], "; ".join(drift)


async def test_every_declared_access_model_matches_a_live_table(migrate_engine):
    """The same drift guard over ``access``, pinned at nine."""
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(LIVE_COLUMNS, {"schema": "access"})).all()

    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)

    declared = [
        table for table in access_models.metadata.tables.values() if table.schema == "access"
    ]
    assert len(declared) == 9

    drift = []
    for table in declared:
        if table.name not in live:
            drift.append(f"{table.name}: declared in models, absent from the database")
            continue
        missing = {column.name for column in table.columns} - live[table.name]
        if missing:
            drift.append(f"{table.name}: columns declared but not live: {sorted(missing)}")

    assert drift == [], "; ".join(drift)


async def test_every_declared_history_model_matches_a_live_table(migrate_engine):
    """The same drift guard over ``history``, with its own pinned count.

    Not a parameterisation of the test above: that one's count of six is
    call-ledger's, and pinning a count is what makes adding a table a visible
    edit here.
    """
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(LIVE_COLUMNS, {"schema": "history"})).all()

    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)

    declared = [
        table for table in history_models.metadata.tables.values() if table.schema == "history"
    ]
    assert len(declared) == 2

    drift = []
    for table in declared:
        if table.name not in live:
            drift.append(f"{table.name}: declared in models, absent from the database")
            continue
        missing = {column.name for column in table.columns} - live[table.name]
        if missing:
            drift.append(f"{table.name}: columns declared but not live: {sorted(missing)}")

    assert drift == [], "; ".join(drift)


async def test_every_declared_provider_model_matches_a_live_table(migrate_engine):
    """The same drift guard over ``provider``, pinned at three."""
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(LIVE_COLUMNS, {"schema": "provider"})).all()

    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)

    declared = [
        table for table in provider_models.metadata.tables.values() if table.schema == "provider"
    ]
    assert len(declared) == 3

    drift = []
    for table in declared:
        if table.name not in live:
            drift.append(f"{table.name}: declared in models, absent from the database")
            continue
        missing = {column.name for column in table.columns} - live[table.name]
        if missing:
            drift.append(f"{table.name}: columns declared but not live: {sorted(missing)}")

    assert drift == [], "; ".join(drift)


async def test_every_declared_registry_model_matches_a_live_table(migrate_engine):
    """The same drift guard over ``registry``, pinned at two.

    ``prompt_property.released_revision_status`` is live and is deliberately
    ABSENT from the declared model: it is a STORED generated column carrying
    BR-03's half of ``fk_prompt_property_released_version_id``, and a column no
    statement may ever name is a column the application should not be able to
    name. The guard runs one-directionally — declared columns must be live, the
    live table may carry more — which is what makes that omission expressible.
    """
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(LIVE_COLUMNS, {"schema": "registry"})).all()

    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)

    declared = [
        table for table in registry_models.metadata.tables.values() if table.schema == "registry"
    ]
    # `prompt_property`, `revision`, and `folder` since 0016.
    assert len(declared) == 3

    drift = []
    for table in declared:
        if table.name not in live:
            drift.append(f"{table.name}: declared in models, absent from the database")
            continue
        missing = {column.name for column in table.columns} - live[table.name]
        if missing:
            drift.append(f"{table.name}: columns declared but not live: {sorted(missing)}")

    assert drift == [], "; ".join(drift)

    assert "released_revision_status" in live["prompt_property"]
    assert "released_revision_status" not in {
        column.name for column in registry_models.prompt_property.columns
    }


async def test_every_declared_evaluation_model_matches_a_live_table(migrate_engine):
    """The same drift guard over ``evaluation``, pinned at seven.

    The original four gained ``workspace_id`` under ADR-0045 in the same pass —
    the first module where NONE of its tables had it, and the one that took that
    rule's running tally to eight tables in six passes. The count is pinned
    rather than derived so that a new table is a visible edit here, and steps 4a
    and 4b are those edits: ``dataset_attachment`` (0018) joins the reusable
    library to the per-prompt suite, and ``dataset`` / ``dataset_case`` (0019)
    are the workspace's own half of that library. All three carried
    ``workspace_id`` from birth — ADR-0045's rule is now old enough that a new
    table arrives already obeying it rather than being discovered by CI.

    ``dataset`` and ``dataset_case`` are the only tables in this schema holding
    an UPDATE or DELETE grant, and that asymmetry is the module's central claim:
    a dataset is the library object somebody edits, a suite is the immutable
    copy a run measured with, and the second can stay append-only only because
    the first is not.
    """
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(LIVE_COLUMNS, {"schema": "evaluation"})).all()

    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)

    declared = [
        table
        for table in evaluation_models.metadata.tables.values()
        if table.schema == "evaluation"
    ]
    assert len(declared) == 7

    drift = []
    for table in declared:
        if table.name not in live:
            drift.append(f"{table.name}: declared in models, absent from the database")
            continue
        missing = {column.name for column in table.columns} - live[table.name]
        if missing:
            drift.append(f"{table.name}: columns declared but not live: {sorted(missing)}")

    assert drift == [], "; ".join(drift)
