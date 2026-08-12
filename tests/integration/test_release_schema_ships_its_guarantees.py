"""What revision 0010 promised, read back from the live catalogue.

Written as a query over what the database actually holds rather than as a reading
of the migration: reading the migration proves the migration says so, not that
the database does.

**T-032 is the reason this file exists.** ``approval`` and ``release`` are
declared append-only — *a changed mind is a new row, never an UPDATE* — and the
step-6 sweep found that of the four tables Prope declares append-only, exactly
ONE was actually enforced as such. An edited approval is a forged decision on the
two tables the product's central claim is made of, and the Success metric reads
them. So ``prope_app`` gets ``SELECT`` and ``INSERT`` and nothing else on both.

``review_task`` KEEPS ``UPDATE``, and that is asserted too rather than left as an
absence — closing a task is an update by design (A-073), and a future blanket
REVOKE across the schema would break the review workflow silently.

**No fifth SECURITY DEFINER function.** The two ``worker`` sweeps read across
every workspace and do it by calling ``access.list_workspaces()``, which already
exists, returns tenant IDENTIFIERS, and leaves every subsequent read under
ordinary RLS. A function returning ROWS would have performed the read inside the
bypass — ADR-0051's rule about shape, asserted here as a count of zero.
"""

import pytest
from sqlalchemy import text

SCHEMA = "release"

APP_TABLE_PRIVILEGES = text(
    """
    SELECT table_name, privilege_type
    FROM   information_schema.table_privileges
    WHERE  table_schema = 'release' AND grantee = 'prope_app'
    ORDER  BY table_name, privilege_type
    """
)

LIST_TABLES = text(
    """
    SELECT tablename, rowsecurity
    FROM   pg_tables
    WHERE  schemaname = 'release'
    ORDER  BY tablename
    """
)

LIST_POLICIES = text(
    """
    SELECT tablename, policyname, qual, with_check
    FROM   pg_policies
    WHERE  schemaname = 'release'
    ORDER  BY tablename
    """
)

LIST_INDEXES = text(
    "SELECT indexname FROM pg_indexes WHERE schemaname = 'release' ORDER BY indexname"
)

LIST_CHECKS = text(
    """
    SELECT c.conname
    FROM   pg_constraint AS c
    JOIN   pg_class AS t ON t.oid = c.conrelid
    JOIN   pg_namespace AS n ON n.oid = t.relnamespace
    WHERE  n.nspname = 'release' AND c.contype = 'c'
    ORDER  BY c.conname
    """
)

SECURITY_DEFINER = text(
    """
    SELECT p.proname
    FROM   pg_proc AS p
    JOIN   pg_namespace AS n ON n.oid = p.pronamespace
    WHERE  n.nspname = 'release' AND p.prosecdef
    """
)

TABLE_OWNERS = text(
    """
    SELECT tablename, tableowner
    FROM   pg_tables
    WHERE  schemaname = 'release'
    ORDER  BY tablename
    """
)

REPORT_PRIVILEGES = text(
    """
    SELECT DISTINCT privilege_type
    FROM   information_schema.table_privileges
    WHERE  table_schema = 'release' AND grantee = 'prope_report'
    ORDER  BY privilege_type
    """
)


async def _rows(migrate_engine, statement) -> list[tuple]:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        return [tuple(row) for row in (await connection.execute(statement)).all()]


async def test_the_three_tables_exist_and_all_carry_row_security(migrate_engine) -> None:  # noqa: ANN001
    rows = await _rows(migrate_engine, LIST_TABLES)

    assert rows == [("approval", True), ("release", True), ("review_task", True)]


async def test_every_policy_reads_the_tenant_setting_in_both_directions(migrate_engine) -> None:  # noqa: ANN001
    """ADR-0040: ``WITH CHECK`` is written out, not defaulted.

    ``USING`` alone refuses a foreign READ. What refuses a mis-stamped WRITE is
    ``WITH CHECK``, and every row in these three tables carries a ``workspace_id``
    this module denormalises from the caller's session.
    """
    rows = await _rows(migrate_engine, LIST_POLICIES)

    assert [row[0] for row in rows] == ["approval", "release", "review_task"]
    for table, policy, qual, with_check in rows:
        assert policy == f"{table}_tenant"
        assert "current_setting('app.workspace_id'::text, true)" in qual, table
        assert with_check == qual, table


async def test_the_two_decision_tables_are_append_only_by_privilege(migrate_engine) -> None:  # noqa: ANN001
    """T-032, which is a HIGH the sweep found unmitigated on four tables.

    Following ADR-0025's precedent for ``history_event``: the privilege is not
    granted rather than granted and revoked, because the positive form is the one
    a reviewer can read.
    """
    rows = await _rows(migrate_engine, APP_TABLE_PRIVILEGES)
    by_table: dict[str, set[str]] = {}
    for table, privilege in rows:
        by_table.setdefault(table, set()).add(privilege)

    assert by_table["approval"] == {"SELECT", "INSERT"}
    assert by_table["release"] == {"SELECT", "INSERT"}

    assert "UPDATE" not in by_table["approval"]
    assert "DELETE" not in by_table["approval"]
    assert "UPDATE" not in by_table["release"]
    assert "DELETE" not in by_table["release"]


async def test_review_task_keeps_update_and_still_has_no_delete(migrate_engine) -> None:  # noqa: ANN001
    """Closing a task IS an update (A-073), and nothing removes one."""
    rows = await _rows(migrate_engine, APP_TABLE_PRIVILEGES)
    privileges = {privilege for table, privilege in rows if table == "review_task"}

    assert privileges == {"SELECT", "INSERT", "UPDATE"}
    assert "DELETE" not in privileges


async def test_prope_app_cannot_update_or_delete_an_approval(migrate_engine, app_engine) -> None:  # noqa: ANN001
    """The live engine's answer, not the catalogue's.

    An application-level test alone would pass against a build whose grants had
    drifted, so this issues the statements as ``prope_app`` and asserts the engine
    refuses them.
    """
    import sqlalchemy.exc

    async with app_engine.begin() as connection:
        for statement in (
            "UPDATE release.approval SET comment = 'edited'",
            "DELETE FROM release.approval",
            "UPDATE release.release SET reason = 'edited'",
            "DELETE FROM release.release",
        ):
            with pytest.raises(sqlalchemy.exc.ProgrammingError):
                async with connection.begin_nested():
                    await connection.execute(text(statement))


async def test_the_schema_adds_no_security_definer_function(migrate_engine) -> None:  # noqa: ANN001
    """ADR-0051's rule about shape, as a count of zero.

    Four are sanctioned project-wide and all four already exist. This module's
    two cross-tenant sweeps need a tenant LIST, which ``access.list_workspaces()``
    already supplies; a fifth returning rows would perform the read inside the
    bypass, which is exactly what the rule refuses.
    """
    assert await _rows(migrate_engine, SECURITY_DEFINER) == []


async def test_at_most_one_open_review_task_per_prompt_is_a_unique_index(
    migrate_engine,  # noqa: ANN001
) -> None:
    """A-067 held by the engine rather than by this module's ``if``.

    The ``if`` produces the readable refusal and the partial unique index is what
    holds when two submissions race. Both are needed and neither is the other's
    substitute.
    """
    indexes = [row[0] for row in await _rows(migrate_engine, LIST_INDEXES)]

    assert "uq_review_task_one_open_review_per_prompt" in indexes
    assert "ix_approval_workspace_id_version_id" in indexes
    assert "ix_release_workspace_id_prompt_id" in indexes
    assert "ix_review_task_workspace_id_status" in indexes


async def test_the_constraints_that_carry_the_product_claim_exist(migrate_engine) -> None:  # noqa: ANN001
    """The Success metric's shape, as CHECKs rather than as application code."""
    checks = {row[0] for row in await _rows(migrate_engine, LIST_CHECKS)}

    assert "ck_release_approval_absent_only_for_break_glass" in checks
    assert "ck_release_break_glass_carries_no_approval" in checks
    assert "ck_release_mandatory_reason" in checks
    assert "ck_release_withdraw_has_no_target" in checks
    assert "ck_release_withdraw_names_what_it_removed" in checks
    assert "ck_approval_changes_requested_carries_a_comment" in checks
    assert "ck_review_task_break_glass_followup_is_due" in checks
    assert "ck_approval_id_prefix" in checks
    assert "ck_release_id_prefix" in checks
    assert "ck_review_task_id_prefix" in checks


async def test_a_release_with_neither_an_approval_nor_break_glass_is_refused(
    migrate_engine,  # noqa: ANN001
) -> None:
    """The Success metric, enforced rather than merely measured.

    The gauge and its alert say when the invariant broke. This says it cannot
    break through an INSERT at all — which is the difference between a metric and
    a guarantee.
    """
    import sqlalchemy.exc

    async with migrate_engine.begin() as connection:
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            async with connection.begin_nested():
                await connection.execute(
                    text(
                        """
                        INSERT INTO release.release (
                            id, workspace_id, prompt_id, version_id, kind,
                            previous_version_id, approval_id, break_glass, reason,
                            released_by, released_at
                        ) VALUES (
                            'rel_forged', 'wsp_x', 'prm_x', 'rev_x', 'release',
                            NULL, NULL, false, NULL, 'usr_x', now()
                        )
                        """
                    )
                )


async def test_the_tables_are_owned_by_the_migration_role_and_readable_by_report(
    migrate_engine,  # noqa: ANN001
) -> None:
    """ADR-0035's owner bypass, and ADR-0036's backup claim.

    ``prope_migrate`` owning every table is what keeps the migration role exempt
    from the tenant policy; ``prope_report``'s SELECT is what makes these three
    tables readable by the audit query BR-04 promises. Neither role is ever a
    runtime credential — ``prope.app.refuse_a_privileged_credential`` refuses to
    start against either.
    """
    owners = await _rows(migrate_engine, TABLE_OWNERS)
    assert {owner for _, owner in owners} == {"prope_migrate"}

    assert await _rows(migrate_engine, REPORT_PRIVILEGES) == [("SELECT",)]
