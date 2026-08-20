"""ADR-0045 / D-06: every table is tenant-scoped unless declared global.

The walk covers **all eight declared module schemas from day one**, not the one
schema Phase 1 happens to build. Scoping it to ``ledger`` and widening it per
module was rejected on the ADR's own grounds: the "walks all eight" property
would then be asserted nowhere, and a module that forgets to widen it is
invisible — "the rule selecting for its own blind spot", which is the exact
failure ADR-0045 was written about after the third instance in three passes.

The inversion is the point. The rule is not "these tables need a policy"; it is
"every table needs one, and an exemption is an entry in ``GLOBAL_TABLES`` with a
written reason a reviewer can disagree with".
"""

from sqlalchemy import text

#: The eight schemas ADR-0027 provisions, one per bounded context. Confirmed
#: against docs/architecture/tech_stack.md, which names each module's schema in
#: its Database row: history (l.162), ledger (l.186), access (l.212),
#: provider (l.250), registry (l.289), evaluation (l.359), release (l.521), and
#: gateway (l.480 — "A `gateway` schema is created and left empty").
DECLARED_SCHEMAS = (
    "access",
    # chat-orchestrator, added with the assistant. Three tables, all three
    # tenant-scoped, none of them exempt: a conversation is additionally filtered
    # to its own actor in the repository, which is ownership on top of tenancy
    # rather than instead of it.
    "chat",
    "evaluation",
    "gateway",
    "history",
    "ledger",
    # prompt-observation, added with ADR-0060. Two tables, both tenant-scoped,
    # neither exempt — and this is the schema where a missing policy would cost
    # the most: every row in it is a customer's production system prompt that
    # arrived without anybody choosing to submit it.
    "observation",
    "provider",
    # prompt-readiness, added with ADR-0067. Five tables, all five tenant-scoped,
    # none exempt. `readiness.report` is the one where a missing policy would be
    # worst: it is the reviewer's frozen evidence, and a card leaking across
    # workspaces would disclose the findings of a prompt the reader cannot see —
    # which is BR-01's private-by-default rule broken through a side door.
    "readiness",
    # prompt-improvement, added with ADR-0068. Four tables, all four
    # tenant-scoped, none exempt. `improvement.finding` is the one where a
    # missing policy would be worst: it names every prompt in a workspace that
    # is degrading, which is the inventory BR-01 closes as not-found.
    "improvement",
    "registry",
    "release",
    "search",
)

#: Fully-qualified table name -> the written reason it is not tenant-scoped.
#: The escape hatch exists so an exemption is a sentence somebody signed rather
#: than a silent skip, and the test below refuses a blank one. OQ-031: the walk
#: currently ``continue``s past an entry where ADR-0045's own pseudocode
#: asserts against it, so an exemption buys no check at all — Phase 4 closes
#: that from the other side, in
#: ``tests/integration/test_history_schema_ships_its_guarantees.py``.
GLOBAL_TABLES: dict[str, str] = {
    "history.history_action_registry": (
        "the action vocabulary is closed install-wide, not per workspace (A-120, ADR-0024); "
        "tenant-scoping it would return zero rows to registered_actions()'s only consumer — a CI "
        "test with no tenant context — and AC-6 would compare two empty sets and pass forever. "
        "Seeded by migration, SELECT-only for prope_app, never written at runtime (ADR-0038). "
        "Declared global by ADR-0045, which names this table."
    ),
    "access.workspace": (
        "IS the tenancy root — policied on `id`, not on `workspace_id` (ADR-0042, ADR-0045, "
        "A-109). This is the entry ADR-0045 was written to replace a bolted-on second clause "
        "with, and it is the one entry here that is NOT unpolicied: revision 0006 calls "
        "enable_tenant_rls('access', 'workspace', column='id'), and "
        "tests/integration/test_access_schema_ships_its_guarantees.py asserts that policy "
        "exists and reads `id`. Without that companion assertion this entry would buy the "
        "table an exemption rather than a different check, which is OQ-031's whole complaint."
    ),
    "access.user": (
        "a person is not a tenant's property; unique(email) is install-wide (ADR-0042, "
        "ADR-0045). A workspace_id here would make one human being one row per workspace, "
        "which is a different product — and it would make `email` unique per tenant, so the "
        "same person could be registered twice with two passwords. Named by ADR-0045. "
        "prope_app holds SELECT/INSERT/UPDATE and no DELETE, which is how ADR-0054's "
        "'tombstoned, never deleted' is enforced instead."
    ),
    "access.role_permission": (
        "the (role, action) matrix is one table for the whole install (ADR-0045). "
        "Per-workspace rows would make the separation of edit / review / release negotiable "
        "per tenant, and 00_context.md#constraints calls that separation non-negotiable. "
        "Seeded by migration 0006 and SELECT-only for prope_app, so GET /api/v1/permissions "
        "renders the RUNNING matrix rather than an editable copy — which is the whole "
        "mechanism by which OQ-006's answer is a re-seed and not a release."
    ),
}

#: THIS LIST IS A PER-PHASE CONSTANT, NOT A PERMANENT FACT. It names the
#: declared schemas that do not exist *yet*. The phase that creates one owns
#: removing it here, in the same change — Phase 4 creating `history` is the
#: first such case, and Phase 7 creating `access` is the next. If it does not
#: update this list it inherits a red test it did not write, which is
#: deliberate: a schema that silently fails to appear must not pass as coverage.
EXPECTED_ABSENT_SCHEMAS = ("gateway",)

#: Ordinary and partitioned tables. Views, sequences and indexes carry no rows
#: of their own and are not what the rule is about.
LIST_TABLES = text(
    """
    SELECT n.nspname, c.relname, c.relrowsecurity
    FROM   pg_class c
    JOIN   pg_namespace n ON n.oid = c.relnamespace
    WHERE  n.nspname = ANY(:schemas) AND c.relkind IN ('r', 'p')
    ORDER  BY n.nspname, c.relname
    """
)

LIST_EXISTING_SCHEMAS = text(
    "SELECT nspname FROM pg_namespace WHERE nspname = ANY(:schemas) ORDER BY nspname"
)

LIST_TENANT_COLUMNS = text(
    """
    SELECT table_schema, table_name
    FROM   information_schema.columns
    WHERE  table_schema = ANY(:schemas) AND column_name = 'workspace_id'
    """
)

LIST_POLICIES = text(
    "SELECT schemaname, tablename, policyname FROM pg_policies WHERE schemaname = ANY(:schemas)"
)

LOCATE_ALEMBIC_VERSION = text(
    """
    SELECT n.nspname
    FROM   pg_class c
    JOIN   pg_namespace n ON n.oid = c.relnamespace
    WHERE  c.relname = 'alembic_version'
    """
)


async def test_every_table_in_every_declared_schema_is_tenant_scoped(migrate_engine):
    """Carries ``workspace_id``, has row security enabled, and has a policy —
    or is exempted in ``GLOBAL_TABLES`` with a reason."""
    schemas = list(DECLARED_SCHEMAS)

    async with migrate_engine.begin() as connection:
        tables = (await connection.execute(LIST_TABLES, {"schemas": schemas})).all()
        tenant_columns = {
            f"{schema}.{table}"
            for schema, table in (
                await connection.execute(LIST_TENANT_COLUMNS, {"schemas": schemas})
            ).all()
        }
        policied = {
            f"{schema}.{table}"
            for schema, table, _ in (
                await connection.execute(LIST_POLICIES, {"schemas": schemas})
            ).all()
        }

    # A walk that found nothing would pass every assertion below. Phase 1 builds
    # five ledger tables, so an empty result is a broken walk, not clean code.
    assert tables, "the coverage walk found no tables at all in any declared schema"

    uncovered = []
    for schema, table, row_security in tables:
        qualified = f"{schema}.{table}"
        if qualified in GLOBAL_TABLES:
            continue
        if qualified not in tenant_columns:
            uncovered.append(f"{qualified}: no workspace_id column")
        elif not row_security:
            uncovered.append(f"{qualified}: row security not enabled")
        elif qualified not in policied:
            uncovered.append(f"{qualified}: row security enabled but no policy")

    assert uncovered == [], (
        "tables reachable by prope_app with no tenant isolation: " + "; ".join(uncovered)
    )


async def test_declared_schemas_that_do_not_exist_are_reported_not_skipped(migrate_engine):
    """A schema silently failing to appear must not pass as coverage.

    See ``EXPECTED_ABSENT_SCHEMAS`` above: this list shrinks as later phases
    build their schemas, and the phase that builds one owns the edit.
    """
    async with migrate_engine.begin() as connection:
        existing = (
            await connection.execute(LIST_EXISTING_SCHEMAS, {"schemas": list(DECLARED_SCHEMAS)})
        ).scalars().all()

    absent = tuple(schema for schema in DECLARED_SCHEMAS if schema not in existing)

    assert absent == EXPECTED_ABSENT_SCHEMAS, (
        "the set of declared-but-absent schemas changed. If a phase just created one, "
        "remove it from EXPECTED_ABSENT_SCHEMAS in this file, in that same change."
    )
    # Alphabetical, because LIST_EXISTING_SCHEMAS carries ORDER BY nspname.
    assert tuple(existing) == (
        "access",
        "chat",
        "evaluation",
        "history",
        "improvement",
        "ledger",
        "observation",
        "provider",
        "readiness",
        "registry",
        "release",
        "search",
    )


def test_every_global_table_exemption_carries_a_written_reason():
    """The escape hatch cannot be used blank. ``GLOBAL_TABLES`` is where a
    reviewer looks to find every table in Prope that is not tenant-scoped, so an
    entry with no argument attached defeats the file's only purpose."""
    blank = [name for name, reason in GLOBAL_TABLES.items() if not reason.strip()]

    assert blank == [], f"GLOBAL_TABLES entries with no written reason: {blank}"


async def test_alembic_version_lives_in_public_and_in_no_declared_schema(migrate_engine):
    """Pitfall 9. Inside a module schema the walk above would fail it for
    carrying no ``workspace_id``, and the "fix" would be a ``GLOBAL_TABLES``
    entry that dilutes a security-relevant file with a bookkeeping table."""
    async with migrate_engine.begin() as connection:
        schemas = (await connection.execute(LOCATE_ALEMBIC_VERSION)).scalars().all()

    assert schemas == ["public"]
    assert not set(schemas) & set(DECLARED_SCHEMAS)
