"""Revision 0007's whole stack, end to end on one applied migration.

Three tables, three policies, one grant matrix, and the separation that makes
"the credential is never returned by a read API" structural rather than
remembered: the ciphertext lives in its own table, so every configuration read
path is incapable of returning it even under SELECT *.
"""

import pytest
from sqlalchemy import text

from prope.db.session import workspace_transaction
from tests.provider_access import (
    CONFIG_ID,
    SECRET,
    seed_catalogue_entry,
    seed_credential,
    seed_provider_config,
)
from tests.unit import WORKSPACE_A, WORKSPACE_B

TABLES = ("provider_config", "credential", "model_catalogue")

LIST_POLICIES = text(
    "SELECT tablename, policyname, qual FROM pg_policies WHERE schemaname = 'provider' "
    "ORDER BY tablename"
)

LIST_GRANTS = text(
    """
    SELECT table_name, grantee, privilege_type
    FROM   information_schema.role_table_grants
    WHERE  table_schema = 'provider'
    ORDER  BY table_name, grantee, privilege_type
    """
)

ROW_SECURITY = text(
    """
    SELECT c.relname, c.relrowsecurity
    FROM   pg_class c
    JOIN   pg_namespace n ON n.oid = c.relnamespace
    WHERE  n.nspname = 'provider' AND c.relkind = 'r'
    ORDER  BY c.relname
    """
)

COUNT_CONFIGS = text("SELECT count(*) FROM provider.provider_config")
COUNT_CREDENTIALS = text("SELECT count(*) FROM provider.credential")
COUNT_MODELS = text("SELECT count(*) FROM provider.model_catalogue")

SELECT_STAR = text("SELECT * FROM provider.provider_config WHERE id = :id")

CHECK_CONSTRAINTS = text(
    """
    SELECT con.conname
    FROM   pg_constraint con
    JOIN   pg_class c  ON c.oid = con.conrelid
    JOIN   pg_namespace n ON n.oid = c.relnamespace
    WHERE  n.nspname = 'provider' AND con.contype = 'c'
    """
)


async def test_all_three_tables_carry_row_security_and_a_tenant_policy(migrate_engine) -> None:
    async with migrate_engine.begin() as connection:
        secured = dict((await connection.execute(ROW_SECURITY)).all())
        policies = (await connection.execute(LIST_POLICIES)).all()

    assert set(secured) == set(TABLES)
    assert all(secured.values()), secured
    assert {table for table, _, _ in policies} == set(TABLES)
    for _, _, predicate in policies:
        assert "app.workspace_id" in predicate
        assert "workspace_id" in predicate


async def test_another_tenant_sees_zero_rows_rather_than_an_error(
    migrate_engine, app_sessionmaker
) -> None:
    """ADR-0035's inversion, on the highest-liability table in the system."""
    await seed_provider_config(migrate_engine)
    await seed_credential(migrate_engine)
    await seed_catalogue_entry(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await db.scalar(COUNT_CONFIGS) == 1
        assert await db.scalar(COUNT_CREDENTIALS) == 1
        assert await db.scalar(COUNT_MODELS) == 1

    async with workspace_transaction(app_sessionmaker, WORKSPACE_B) as db:
        assert await db.scalar(COUNT_CONFIGS) == 0
        assert await db.scalar(COUNT_CREDENTIALS) == 0
        assert await db.scalar(COUNT_MODELS) == 0


async def test_a_session_with_no_tenant_reads_nothing_at_all(migrate_engine, app_sessionmaker):
    """A query written without the filter answers zero rows rather than another
    tenant's — which is what makes a forgotten filter a bug that shows up as an
    empty screen rather than as a leak."""
    await seed_provider_config(migrate_engine)

    async with app_sessionmaker() as db:
        assert await db.scalar(COUNT_CONFIGS) == 0


async def test_select_star_on_a_configuration_returns_no_ciphertext(
    migrate_engine, app_sessionmaker
) -> None:
    """T-028. The separation is the mechanism: no reviewer has to notice an
    omitted column, because there is no column to omit."""
    await seed_provider_config(migrate_engine)
    await seed_credential(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        row = (await db.execute(SELECT_STAR, {"id": CONFIG_ID})).mappings().one()

    assert "ciphertext" not in row
    assert "wrapped_dek" not in row
    assert SECRET not in " ".join(str(value) for value in row.values())


async def test_the_grant_matrix_withholds_what_it_is_supposed_to(migrate_engine) -> None:
    """`prope_report` carries BYPASSRLS, so it is deliberately given no read of
    the ciphertext table at all: the reporting credential exists for figures,
    and no figure is computed from an encrypted third-party secret (T-027)."""
    async with migrate_engine.begin() as connection:
        grants = (await connection.execute(LIST_GRANTS)).all()

    app_privileges = {
        (table, privilege) for table, grantee, privilege in grants if grantee == "prope_app"
    }
    report_tables = {table for table, grantee, _ in grants if grantee == "prope_report"}

    for table in TABLES:
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert (table, privilege) in app_privileges, (table, privilege)

    assert "credential" not in report_tables
    assert {"provider_config", "model_catalogue"} <= report_tables


async def test_the_vocabularies_are_check_constraints_and_not_native_enums(
    migrate_engine,
) -> None:
    """Pitfall 4, per table: adding a value to a native enum cannot run inside a
    transaction block, and removing one is impossible at any price."""
    async with migrate_engine.begin() as connection:
        names = set((await connection.execute(CHECK_CONSTRAINTS)).scalars().all())

    assert "ck_provider_config_status_values" in names
    assert "ck_provider_config_adapter_values" in names
    assert "ck_provider_config_verification_status_values" in names
    assert "ck_model_catalogue_source_values" in names


async def test_the_base_url_column_refuses_a_non_https_value(migrate_engine) -> None:
    """The engine's half of ADR-0047's scheme allow-list. The application
    refuses it first and this is what survives a hand-written UPDATE."""
    with pytest.raises(Exception) as failure:
        await seed_provider_config(migrate_engine, base_url="http://provider.example/v1")

    assert "ck_provider_config_base_url_scheme" in str(failure.value)


async def test_one_configuration_holds_at_most_one_credential(migrate_engine) -> None:
    """A-025: rotation replaces the record rather than appending a readable
    copy, so no history of a secret can accumulate even by an INSERT."""
    await seed_provider_config(migrate_engine)
    await seed_credential(migrate_engine)

    with pytest.raises(Exception) as failure:
        await seed_credential(migrate_engine, credential_id="crd_01J0000000000000000CRD2")

    assert "uq_credential_provider_config_id" in str(failure.value)


async def test_deleting_a_configuration_takes_its_credential_and_catalogue_with_it(
    migrate_engine, app_sessionmaker
) -> None:
    """An orphaned ciphertext is a secret nothing can reach and nothing will
    ever rotate."""
    await seed_provider_config(migrate_engine)
    await seed_credential(migrate_engine)
    await seed_catalogue_entry(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await db.execute(
            text("DELETE FROM provider.provider_config WHERE id = :id"), {"id": CONFIG_ID}
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await db.scalar(COUNT_CREDENTIALS) == 0
        assert await db.scalar(COUNT_MODELS) == 0
