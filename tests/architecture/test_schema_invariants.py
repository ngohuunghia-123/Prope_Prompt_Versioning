"""Invariants that are cheap to assert now and expensive to discover late.

Each of these is a rule stated somewhere in prose — an ADR, a lock file, a
research pitfall — and each becomes false the moment a later revision breaks it
without anyone noticing. Written as a query over the *live* catalogue rather
than as a reading of the migration source: reading the source proves the source
says so, not that the database does.
"""

from sqlalchemy import text

from prope.call_ledger import models

SCHEMA = "ledger"

#: The sanctioned project-wide set is exactly these four (CLAUDE.md), and none
#: belongs to call-ledger. OQ-C's cross-tenant enumeration gap is the obvious
#: place a fifth would be invented; that is a designed-in failure, so the module
#: asserts zero rather than asserting "not more than before".
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
    "monthly_limit",
    "per_run_limit",
]


async def test_the_ledger_schema_contains_no_security_definer_function(migrate_engine):
    """T-01-11. Four are sanctioned project-wide and none of them is here."""
    async with migrate_engine.begin() as connection:
        functions = (
            await connection.execute(SECURITY_DEFINER_FUNCTIONS, {"schema": SCHEMA})
        ).scalars().all()

    assert functions == [], (
        "a SECURITY DEFINER function appeared in ledger. The sanctioned set is exactly "
        "access.lookup_session, access.lookup_api_key, evaluation.claim_next_run() and "
        "access.list_workspaces(); a fifth is a designed-in failure, not a fix."
    )


async def test_no_native_enum_type_exists_in_the_ledger_schema(migrate_engine):
    """Pitfall 4. Adding a value to a native enum cannot run inside a
    transaction block, and removing one is impossible at any price. Vocabularies
    are ``text`` plus a named CHECK."""
    async with migrate_engine.begin() as connection:
        enums = (await connection.execute(NATIVE_ENUM_TYPES, {"schema": SCHEMA})).scalars().all()

    assert enums == []


async def test_no_foreign_key_leaves_the_ledger_schema(migrate_engine):
    """T-01-09. PostgreSQL documents that referential-integrity checks always
    bypass row security, so a foreign key from a tenant-scoped table to another
    schema's table is a covert channel across tenants — quite apart from being
    the way a sink module quietly acquires an outbound edge."""
    async with migrate_engine.begin() as connection:
        escaping = (
            await connection.execute(FOREIGN_KEYS_LEAVING_SCHEMA, {"schema": SCHEMA})
        ).scalars().all()

    assert escaping == [], f"foreign keys leaving ledger: {escaping}"


async def test_every_timestamp_column_carries_a_time_zone(migrate_engine):
    """A-003 / Pitfall 7. ``timestamp without time zone`` silently discards the
    offset, and AC-3's day-5/day-12/day-20 arithmetic then passes or fails by
    geography."""
    async with migrate_engine.begin() as connection:
        columns = (await connection.execute(TIME_COLUMNS, {"schema": SCHEMA})).all()

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
                MONEY_COLUMNS, {"schema": SCHEMA, "names": MONEY_COLUMN_NAMES}
            )
        ).all()

    assert len(columns) == 6, f"expected six money columns across ledger, found {columns}"
    wrong = [
        f"{table}.{column} is numeric({precision},{scale})"
        for table, column, precision, scale in columns
        if (precision, scale) != (20, 10)
    ]
    assert wrong == []


async def test_no_column_in_ledger_has_a_floating_point_type(migrate_engine):
    """Pitfall 5. Float arithmetic makes a cost non-reproducible, and ADR-0019's
    whole point is a figure that can be re-derived years later."""
    async with migrate_engine.begin() as connection:
        floats = (
            await connection.execute(FLOATING_POINT_COLUMNS, {"schema": SCHEMA})
        ).all()

    assert floats == []


async def test_created_at_has_no_default_while_written_at_does(migrate_engine):
    """The single easiest way to get CL-03 subtly wrong. A default on
    ``created_at`` prices a backlogged record at drain time, so a call made on
    day 5 and written on day 12 is priced at day 12 — and the test passes on an
    idle machine and fails under load."""
    async with migrate_engine.begin() as connection:
        defaults = dict(
            (await connection.execute(CALL_RECORD_TIMESTAMP_DEFAULTS, {"schema": SCHEMA})).all()
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
        rows = (await connection.execute(LIVE_COLUMNS, {"schema": SCHEMA})).all()

    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)

    declared = [table for table in models.metadata.tables.values() if table.schema == SCHEMA]
    assert len(declared) == 5

    drift = []
    for table in declared:
        if table.name not in live:
            drift.append(f"{table.name}: declared in models, absent from the database")
            continue
        missing = {column.name for column in table.columns} - live[table.name]
        if missing:
            drift.append(f"{table.name}: columns declared but not live: {sorted(missing)}")

    assert drift == [], "; ".join(drift)
