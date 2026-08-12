"""The guarantees revision 0002 carries, asserted against the live engine.

These are the task's acceptance criteria written as tests rather than as
one-off shell checks. Reading them out of the migration source would prove that
the source says so, not that the database does — and "the migration says it" is
exactly the gap the enforcement pattern exists to close.

Each refusal test overrides exactly one field of an otherwise-valid row, so the
constraint named in the error is the constraint under test, and the assertion
is on the *name* rather than on "something went wrong".
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from prope.db.session import workspace_transaction
from tests.security import INSERT_CALL_RECORD, WORKSPACE_A, call_record_values


async def _refused_insert(app_sessionmaker, **overrides) -> str:
    """Insert as prope_app inside a workspace transaction; return the error text."""
    with pytest.raises(IntegrityError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await session.execute(INSERT_CALL_RECORD, call_record_values(**overrides))
    return str(excinfo.value)


async def test_a_cost_of_zero_is_refused_by_the_engine(app_sessionmaker):
    """CL-04 boundary. Zero is not a cost state — an absent figure asks a
    question, a wrong figure answers it (ADR-0019)."""
    message = await _refused_insert(
        app_sessionmaker,
        call_id="cal_zero_cost",
        cost_status="priced",
        cost=0,
        currency="USD",
        price_row_id="prc_01J0000000000000000000001",
    )
    assert "ck_call_record_cost_is_never_zero" in message


async def test_unknown_usage_with_zero_tokens_is_refused(app_sessionmaker):
    """CL-11 boundary. Unknown means NULL, never zero."""
    message = await _refused_insert(
        app_sessionmaker,
        call_id="cal_unknown_zero",
        usage_status="unknown",
        input_tokens=0,
        output_tokens=None,
        cost_status="not_applicable",
    )
    assert "ck_call_record_unknown_usage_is_null" in message


async def test_gateway_call_without_a_version_id_is_refused(app_sessionmaker):
    """"A database constraint here, not a hope" (call-ledger.lock.yml:162-164).

    The "100% of gateway calls record a version ID" success metric.
    """
    message = await _refused_insert(
        app_sessionmaker, call_id="cal_no_version", version_id=None
    )
    assert "ck_call_record_gateway_calls_carry_version_id" in message


async def test_created_at_has_no_column_default(migrate_engine):
    """A default would price a backlogged record at drain time, and CL-03 would
    pass on an idle machine and fail under load. written_at does default,
    because it genuinely means "when the database saw this"."""
    async with migrate_engine.begin() as connection:
        defaults = dict(
            (
                await connection.execute(
                    text(
                        "SELECT column_name, column_default FROM information_schema.columns "
                        "WHERE table_schema = 'ledger' AND table_name = 'call_record' "
                        "AND column_name IN ('created_at', 'written_at')"
                    )
                )
            ).all()
        )

    assert defaults["created_at"] is None
    assert defaults["written_at"] is not None


async def test_timestamps_are_timestamptz_and_money_is_exact_decimal(migrate_engine):
    """A-003 — UTC with an explicit offset; the naive type discards it. Money is
    numeric(20,10) and never a float."""
    async with migrate_engine.begin() as connection:
        types = dict(
            (
                await connection.execute(
                    text(
                        "SELECT column_name, data_type FROM information_schema.columns "
                        "WHERE table_schema = 'ledger' AND table_name = 'call_record' "
                        "AND column_name IN ('created_at', 'written_at')"
                    )
                )
            ).all()
        )
        precision, scale = (
            await connection.execute(
                text(
                    "SELECT numeric_precision, numeric_scale FROM information_schema.columns "
                    "WHERE table_schema = 'ledger' AND table_name = 'call_record' "
                    "AND column_name = 'cost'"
                )
            )
        ).one()

    assert types == {
        "created_at": "timestamp with time zone",
        "written_at": "timestamp with time zone",
    }
    assert (precision, scale) == (20, 10)


async def test_no_native_enum_type_and_no_stale_resolution_column(migrate_engine):
    """Vocabularies are text + named CHECK. Adding a value to a native enum
    cannot run inside a transaction block and removing one is impossible at any
    price. stale_resolution was removed from the field list on 2026-08-09 with a
    written reason."""
    async with migrate_engine.begin() as connection:
        enum_types = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM pg_type "
                    "WHERE typtype = 'e' AND typnamespace = 'ledger'::regnamespace"
                )
            )
        ).scalar_one()
        stale_resolution = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema = 'ledger' AND table_name = 'call_record' "
                    "AND column_name = 'stale_resolution'"
                )
            )
        ).scalar_one()

    assert enum_types == 0
    assert stale_resolution == 0


async def test_row_level_security_is_enabled_and_never_forced(migrate_engine):
    """ADR-0035 depends on the owner bypass. FORCE would subject prope_migrate
    to its own policy and break every migration, backfill and rig setup path."""
    async with migrate_engine.begin() as connection:
        enabled, forced = (
            await connection.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE oid = 'ledger.call_record'::regclass"
                )
            )
        ).one()
        policies = (
            await connection.execute(
                text(
                    "SELECT policyname FROM pg_policies "
                    "WHERE schemaname = 'ledger' AND tablename = 'call_record'"
                )
            )
        ).scalars().all()

    assert (enabled, forced) == (True, False)
    assert policies == ["call_record_tenant"]


async def test_no_policy_predicate_casts_the_tenant_setting_to_uuid(migrate_engine):
    """OQ-A, decided text-no-cast. The reading is in the database, not only in
    prose: a ::uuid cast would raise on a wsp_-prefixed ULID where ADR-0045
    requires a missing filter to return zero rows."""
    async with migrate_engine.begin() as connection:
        casts = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM pg_policies WHERE schemaname = 'ledger' "
                    "AND (qual LIKE '%::uuid%' OR with_check LIKE '%::uuid%')"
                )
            )
        ).scalar_one()

    assert casts == 0


async def test_alembic_version_lives_in_public(migrate_engine):
    """Pitfall 9. Inside ledger it would fail D-06's coverage walk for carrying
    no workspace_id, and the fix would be a GLOBAL_TABLES entry that dilutes a
    security-relevant file with a bookkeeping table."""
    async with migrate_engine.begin() as connection:
        schemas = (
            await connection.execute(
                text(
                    "SELECT n.nspname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.relname = 'alembic_version'"
                )
            )
        ).scalars().all()

    assert schemas == ["public"]
