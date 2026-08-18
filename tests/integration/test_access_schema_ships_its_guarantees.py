"""Revision 0006's guarantees that are neither privileges nor generic invariants.

Sibling of `test_history_schema_ships_its_guarantees.py`, shaped against the same
failure: a migration that creates eight tables and silently seeds nothing looks
healthy, and the first symptom is a permission matrix that denies everything.

Three things are asserted here and nowhere else:

* **`access.workspace`'s policy really is on `id`.** It is the tenancy root, so
  its policy compares `id` rather than a `workspace_id` column — and
  `test_tenant_coverage.py` lists it in `GLOBAL_TABLES` and `continue`s past it
  (OQ-031), so without this the one table whose policy is written differently is
  the one table nothing checks.
* **The three `SECURITY DEFINER` functions return identifiers and nothing else**,
  are owned by `prope_migrate`, have an empty `search_path`, and are `REVOKE`d
  from `PUBLIC`.
* **`prope_app` with no tenant set reads zero rows** from every policied table.
"""

from sqlalchemy import text

from tests.access_control import (
    ADMIN_ID,
    MEMBER_ID,
    WORKSPACE_A,
    seed_api_key,
    seed_grant,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)

READ_WORKSPACE_POLICY = text(
    """
    SELECT qual, with_check
    FROM   pg_policies
    WHERE  schemaname = 'access' AND tablename = 'workspace'
    """
)

READ_DEFINER_FUNCTIONS = text(
    """
    SELECT p.proname,
           pg_get_userbyid(p.proowner) AS owner,
           p.proconfig,
           p.provolatile,
           has_function_privilege('public', p.oid, 'EXECUTE') AS public_may_execute,
           has_function_privilege('prope_app', p.oid, 'EXECUTE') AS app_may_execute
    FROM   pg_proc p
    JOIN   pg_namespace n ON n.oid = p.pronamespace
    WHERE  n.nspname = 'access' AND p.prosecdef
    ORDER  BY p.proname
    """
)

READ_APP_PRIVILEGES = text(
    """
    SELECT table_name, privilege_type
    FROM   information_schema.role_table_grants
    WHERE  table_schema = 'access' AND grantee = 'prope_app'
    ORDER  BY table_name, privilege_type
    """
)

COUNT_MATRIX = text("SELECT count(*) FROM access.role_permission")

COUNT_ADMIN_PERMISSIONS = text("SELECT count(*) FROM access.role_permission WHERE role = 'Admin'")

TOMBSTONE_HOLDERS = text(
    "SELECT count(*) FROM access.role_permission WHERE action = 'user.tombstone'"
)

#: A-115's separation-of-duties invariant, as one query. No role may hold two of
#: `prompt.edit`, `revision.approve`, `release.create` — the third non-negotiable,
#: read off the running matrix rather than off the seed literal.
SEPARATION_OF_DUTIES = text(
    """
    SELECT role, count(*)
    FROM   access.role_permission
    WHERE  action IN ('prompt.edit', 'revision.approve', 'release.create')
    GROUP  BY role
    ORDER  BY role
    """
)

POLICIED_TABLES = ("session", "workspace_member", "role_binding", "prompt_grant", "api_key")

#: The privileges 0006 withholds, and each absence is a decision:
#: no `UPDATE` on `workspace` (a tenancy root's id is not editable), no `DELETE`
#: on `"user"` (ADR-0054 tombstones), no `DELETE` on `workspace_member` (A-151
#: retains the row so a tombstone knows which workspaces to write into), no
#: `DELETE` on `api_key` (it would orphan the `api_key_revoked` event), and
#: `SELECT` only on `role_permission` (the matrix is a migration's to change).
EXPECTED_APP_PRIVILEGES = {
    "api_key": {"SELECT", "INSERT", "UPDATE"},
    "prompt_grant": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "role_binding": {"SELECT", "INSERT", "DELETE"},
    "role_permission": {"SELECT"},
    "session": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "user": {"SELECT", "INSERT", "UPDATE"},
    "workspace": {"SELECT", "INSERT"},
    # ADR-0057. No DELETE: an invitation is revoked by stamping `revoked_at`, so
    # the row that says who invited whom survives the revocation.
    "workspace_invite": {"SELECT", "INSERT", "UPDATE"},
    "workspace_member": {"SELECT", "INSERT", "UPDATE"},
}

EXPECTED_DEFINER_FUNCTIONS = ("list_workspaces", "lookup_api_key", "lookup_session")


async def test_the_tenancy_roots_policy_is_written_on_id(migrate_engine) -> None:
    """ADR-0042. `access.workspace` has no `workspace_id` column; `id` is the tenant."""
    async with migrate_engine.begin() as connection:
        policies = (await connection.execute(READ_WORKSPACE_POLICY)).all()

    assert len(policies) == 1, "one policy, or the tenancy root has grown a second"
    qual, with_check = policies[0]
    # The setting NAME contains "workspace_id", so the comparison's left-hand
    # side is what is checked rather than a substring of the whole predicate.
    assert qual.startswith("(id = current_setting("), qual
    assert with_check is not None, "no WITH CHECK — a row could be inserted into another tenant"


async def test_the_definer_functions_are_owned_locked_down_and_stable(migrate_engine) -> None:
    """ADR-0042's template, asserted property by property rather than by name."""
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(READ_DEFINER_FUNCTIONS)).all()

    assert tuple(row.proname for row in rows) == EXPECTED_DEFINER_FUNCTIONS

    for row in rows:
        assert row.owner == "prope_migrate", row.proname
        assert row.proconfig == ['search_path=""'], (row.proname, row.proconfig)
        # asyncpg returns "char" as bytes.
        assert row.provolatile == b"s", f"{row.proname} is not STABLE"
        assert not row.public_may_execute, f"{row.proname} is executable by PUBLIC"
        assert row.app_may_execute, f"{row.proname} is not executable by prope_app"


async def test_prope_app_holds_exactly_the_declared_privileges(migrate_engine) -> None:
    """The withheld privileges are the decisions; both directions fail."""
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(READ_APP_PRIVILEGES)).all()

    held: dict[str, set[str]] = {}
    for table, privilege in rows:
        held.setdefault(table, set()).add(privilege)

    assert held == EXPECTED_APP_PRIVILEGES


async def test_the_permission_matrix_landed_and_keeps_its_separations(app_sessionmaker) -> None:
    """OQ-006's placeholder, read on the role and with the tenant the endpoint uses.

    `access.role_permission` is global, so this read sets no tenant — which is
    also how `GET /api/v1/permissions` reads it.
    """
    async with app_sessionmaker() as session:
        assert (await session.execute(COUNT_MATRIX)).scalar_one() == 37
        assert (await session.execute(COUNT_ADMIN_PERMISSIONS)).scalar_one() == 16
        # ADR-0054: erasing an account is Admin-only and is not folded into
        # workspace.manage_members.
        assert (await session.execute(TOMBSTONE_HOLDERS)).scalar_one() == 1

        overlaps = (await session.execute(SEPARATION_OF_DUTIES)).all()

    doubled = [(role, count) for role, count in overlaps if count > 1]
    assert doubled == [], (
        f"{doubled} holds more than one of prompt.edit / revision.approve / release.create. "
        "Edit, review and release are separate permissions — the third non-negotiable."
    )


async def test_the_app_role_reads_zero_rows_with_no_tenant_set(
    migrate_engine, app_sessionmaker
) -> None:
    """ADR-0035's inversion: a missing filter is zero rows, never another tenant's.

    Seeded as the owner so the rows genuinely exist — a zero over an empty table
    distinguishes no hypothesis from any other.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_role(migrate_engine, "Admin")
    await seed_grant(migrate_engine, "viewer")
    await seed_session(migrate_engine, "ses_0123456789abcdef")
    await seed_api_key(migrate_engine)

    async with migrate_engine.begin() as control:
        for table in POLICIED_TABLES:
            seeded = (
                await control.execute(text(f"SELECT count(*) FROM access.{table}"))  # noqa: S608
            ).scalar_one()
            assert seeded >= 1, f"{table} was not seeded; the zero below would be vacuous"

    async with app_sessionmaker() as session:
        for table in (*POLICIED_TABLES, "workspace"):
            visible = (
                await session.execute(text(f"SELECT count(*) FROM access.{table}"))  # noqa: S608
            ).scalar_one()
            assert visible == 0, f"{table} returned {visible} rows with no tenant set"

        # The global tables answer, which is what makes the zeros above a
        # statement about the policies rather than about the connection.
        assert (await session.execute(COUNT_MATRIX)).scalar_one() == 37
        assert (
            await session.execute(text('SELECT count(*) FROM access."user"'))
        ).scalar_one() == 2


async def test_the_definer_lookups_answer_across_the_tenant_boundary(
    migrate_engine, app_sessionmaker
) -> None:
    """The bootstrap's whole point: these two answer where the policy does not.

    The tests above prove `prope_app` sees zero session rows with no tenant set.
    Every authenticated request in Prope starts there, so `lookup_session` must
    answer anyway — and it returns identifiers only, never the row.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_session(migrate_engine, "ses_0123456789abcdef")

    async with app_sessionmaker() as session:
        row = (
            await session.execute(
                text("SELECT user_id, workspace_id FROM access.lookup_session(:id)"),
                {"id": "ses_0123456789abcdef"},
            )
        ).one()

    assert (row.user_id, row.workspace_id) == (ADMIN_ID, WORKSPACE_A)


async def test_list_workspaces_enumerates_identifiers_only(
    migrate_engine, app_sessionmaker
) -> None:
    """ADR-0051. The tombstone needs every tenant; it gets ids and reads each under policy."""
    await seed_workspace(migrate_engine)

    async with app_sessionmaker() as session:
        ids = (await session.execute(text("SELECT access.list_workspaces()"))).scalars().all()

    assert list(ids) == [WORKSPACE_A]
