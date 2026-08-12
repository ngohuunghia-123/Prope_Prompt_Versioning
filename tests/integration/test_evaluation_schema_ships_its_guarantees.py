"""What revision 0009 promised, read back from the live catalogue.

Every assertion here is a sentence in prose somewhere — ADR-0042, ADR-0045,
ADR-0049, the lock file's ``data.owns`` — that becomes false the moment a later
revision breaks it without anybody noticing. Written as a query over what the
database actually holds rather than as a reading of the migration: reading the
migration proves the migration says so, not that the database does.

Four groups, and the fourth is the one this module is unusual for:

* **RLS on all four tables**, with a ``WITH CHECK`` written out rather than
  defaulted, so a mis-stamped insert is refused as well as a foreign read;
* **no ``DELETE`` anywhere**, on any table, for ``prope_app`` — a run's case
  results are the evidence behind an approval and there is no path that removes
  them;
* **append-only by privilege** on ``eval_suite`` and ``eval_case``: ``SELECT``
  and ``INSERT`` only, plus a COLUMN-level ``UPDATE`` on the one derived counter;
* **the fourth sanctioned ``SECURITY DEFINER`` function**, owned by
  ``prope_migrate``, with an empty ``search_path``, revoked from ``PUBLIC`` and
  granted to ``prope_app`` alone.
"""

from sqlalchemy import text

APP_TABLE_PRIVILEGES = text(
    """
    SELECT table_name, privilege_type
    FROM   information_schema.table_privileges
    WHERE  table_schema = 'evaluation' AND grantee = 'prope_app'
    ORDER  BY table_name, privilege_type
    """
)

APP_COLUMN_PRIVILEGES = text(
    """
    SELECT column_name
    FROM   information_schema.column_privileges
    WHERE  table_schema = 'evaluation' AND grantee = 'prope_app'
      AND  privilege_type = 'UPDATE' AND table_name = 'eval_suite'
    ORDER  BY column_name
    """
)

LIST_POLICIES = text(
    """
    SELECT tablename, policyname, qual, with_check
    FROM   pg_policies
    WHERE  schemaname = 'evaluation'
    ORDER  BY tablename
    """
)

LIST_TABLES = text(
    """
    SELECT tablename, rowsecurity
    FROM   pg_tables
    WHERE  schemaname = 'evaluation'
    ORDER  BY tablename
    """
)

LIST_INDEXES = text(
    "SELECT indexname FROM pg_indexes WHERE schemaname = 'evaluation' ORDER BY indexname"
)

CLAIM_FUNCTION = text(
    """
    SELECT p.prosecdef,
           p.proconfig,
           pg_get_userbyid(p.proowner) AS owner,
           pg_get_function_result(p.oid) AS result
    FROM   pg_proc AS p
    JOIN   pg_namespace AS n ON n.oid = p.pronamespace
    WHERE  n.nspname = 'evaluation' AND p.proname = 'claim_next_run'
    """
)

CLAIM_FUNCTION_ACL = text(
    """
    SELECT p.proacl::text
    FROM   pg_proc AS p
    JOIN   pg_namespace AS n ON n.oid = p.pronamespace
    WHERE  n.nspname = 'evaluation' AND p.proname = 'claim_next_run'
    """
)

LIST_CHECKS = text(
    """
    SELECT c.conname
    FROM   pg_constraint AS c
    JOIN   pg_class AS t ON t.oid = c.conrelid
    JOIN   pg_namespace AS n ON n.oid = t.relnamespace
    WHERE  n.nspname = 'evaluation' AND c.contype = 'c'
    ORDER  BY c.conname
    """
)

EXPECTED_TABLES = ["case_result", "eval_case", "eval_run", "eval_suite"]


async def test_all_four_tables_carry_row_level_security_with_a_policy(
    migrate_engine,
) -> None:
    """ADR-0045's enumeration, and it must hold for every table, not most.

    ``eval_case`` and ``case_result`` are reachable only through their parents,
    which is exactly the argument that left ``registry.revision`` without a
    tenant column for five module passes. Both carry ``workspace_id`` here for
    that reason, and both have the policy to make it mean something.
    """
    async with migrate_engine.begin() as connection:
        tables = (await connection.execute(LIST_TABLES)).all()
        policies = (await connection.execute(LIST_POLICIES)).all()

    assert [name for name, _ in tables] == EXPECTED_TABLES
    assert all(row_security for _, row_security in tables)

    assert [table for table, _, _, _ in policies] == EXPECTED_TABLES
    for _, _, using, with_check in policies:
        assert "workspace_id" in using
        assert "current_setting" in using
        assert with_check is not None


async def test_prope_app_holds_no_delete_on_any_table(migrate_engine) -> None:
    """The evidence behind an approval has no removal path in the MVP.

    Asserted as an absence across the whole schema rather than table by table, so
    a fifth table added later without thinking about it fails here.
    """
    async with migrate_engine.begin() as connection:
        grants = {
            (table, privilege)
            for table, privilege in (await connection.execute(APP_TABLE_PRIVILEGES)).all()
        }

    assert not [pair for pair in grants if pair[1] == "DELETE"]

    for table in EXPECTED_TABLES:
        assert (table, "SELECT") in grants
        assert (table, "INSERT") in grants


async def test_suites_and_cases_are_append_only_but_the_counter_may_move(
    migrate_engine,
) -> None:
    """ADR-0025's shape, with the one exception written as a COLUMN grant.

    A suite version is immutable once saved — editing one creates the next
    version — so ``UPDATE`` is not granted at the table level. ``case_count`` is
    derived from rows written in the same transaction and is the single column a
    command may move, so it is granted by name. The list below is the whole
    exception: if it grows, this test says so.
    """
    async with migrate_engine.begin() as connection:
        grants = {
            (table, privilege)
            for table, privilege in (await connection.execute(APP_TABLE_PRIVILEGES)).all()
        }
        updatable = (await connection.execute(APP_COLUMN_PRIVILEGES)).scalars().all()

    assert ("eval_suite", "UPDATE") not in grants
    assert ("eval_case", "UPDATE") not in grants
    assert ("case_result", "UPDATE") not in grants
    assert ("eval_run", "UPDATE") in grants

    assert list(updatable) == ["case_count"]


async def test_the_claim_function_is_definer_owned_with_an_empty_search_path(
    migrate_engine,
) -> None:
    """ADR-0042's template, and ADR-0049's reason for spending the fourth slot.

    A claim has to see rows in every workspace at once, before it knows which
    workspace it is about — there is no ``app.workspace_id`` to set yet. The
    empty ``search_path`` is what stops a schema on the caller's path resolving
    a name inside the definer's body.
    """
    async with migrate_engine.begin() as connection:
        row = (await connection.execute(CLAIM_FUNCTION)).one()

    assert row.prosecdef is True
    assert row.owner == "prope_migrate"
    assert "search_path=" in "".join(row.proconfig)

    for column in ("run_id", "workspace_id", "prompt_id", "version_id", "suite_id"):
        assert column in row.result


async def test_the_claim_function_is_revoked_from_public_and_granted_to_the_app(
    migrate_engine,
) -> None:
    """The privilege half. A ``SECURITY DEFINER`` left executable by ``PUBLIC``
    is a privilege escalation available to every role in the cluster, including
    ``prope_report`` — which is BYPASSRLS and has no business claiming work."""
    async with migrate_engine.begin() as connection:
        acl = await connection.scalar(CLAIM_FUNCTION_ACL)

    assert acl is not None
    assert "prope_app=X/prope_migrate" in acl

    # PostgreSQL writes the ``PUBLIC`` grantee as the EMPTY string, so a
    # still-public EXECUTE appears as an entry whose left-hand side is missing:
    # ``{=X/prope_migrate,...}``. Matched positionally rather than by searching
    # for ``=X/``, which every named grantee's entry also contains.
    entries = acl.strip("{}").split(",")
    assert not [entry for entry in entries if entry.startswith("=")]


async def test_the_run_table_carries_the_index_the_claim_loop_reads(
    migrate_engine,
) -> None:
    """The claim loop runs once a second forever; it is the hottest read here."""
    async with migrate_engine.begin() as connection:
        indexes = (await connection.execute(LIST_INDEXES)).scalars().all()

    assert "ix_eval_run_workspace_id_status" in indexes
    assert "ix_eval_run_suite_id_version_id" in indexes
    assert "ix_case_result_run_id_created_at" in indexes


async def test_the_vocabularies_are_constraints_and_not_conventions(
    migrate_engine,
) -> None:
    """The status, role and outcome sets live in ``CHECK``s, not in Python.

    ``domain.py``'s enums are byte-identical to these by rule, and the rule is
    only enforceable if the database is the one holding the authoritative copy.
    """
    async with migrate_engine.begin() as connection:
        checks = set((await connection.execute(LIST_CHECKS)).scalars().all())

    assert "ck_eval_run_status_values" in checks
    assert "ck_eval_run_role_values" in checks
    assert "ck_case_result_outcome_values" in checks
    assert "ck_eval_suite_output_modality_values" in checks

    assert "ck_eval_run_refused_reason_belongs_to_refused" in checks
    assert "ck_case_result_error_carries_a_code" in checks
    assert "ck_eval_run_cost_carries_currency" in checks
