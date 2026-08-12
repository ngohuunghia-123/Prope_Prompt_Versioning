"""D-08 / ADR-0035: a missing tenant filter returns zero rows, not everything.

The tracer's end-to-end assertion. One call record travels the whole stack —
hand-written migration, ``prope_migrate``-owned schema, CHECK-constrained
table, RLS policy, grant matrix, async engine, tenant seam — and is provably
invisible to every other tenant and to a caller who forgot the filter.

Every "zero rows" assertion here is paired with a ``prope_migrate`` positive
control, because an empty table returns zero rows too, and a test that cannot
tell those apart proves nothing about the policy.

The pristine and reused connection paths are asserted separately and on
purpose. On a connection where the setting was never touched,
``current_setting('app.workspace_id', true)`` yields NULL. Once any transaction
on that connection has set it, the transaction-local value reverts at
transaction end to the *session* value, which for a never-SET custom setting is
the empty string. Both yield zero rows, by different routes. A test exercising
only one does not prove the other.
"""

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from prope.db.session import workspace_transaction
from tests.security import (
    COUNT_CALL_RECORDS,
    INSERT_CALL_RECORD,
    READ_TENANT_GUC,
    SELECT_CALL_IDS,
    WORKSPACE_A,
    WORKSPACE_B,
    WORKSPACE_WITH_QUOTE,
    call_record_values,
)


async def test_record_written_through_the_seam_is_readable_in_that_transaction(app_sessionmaker):
    """The happy path the other four tests are the negative space of."""
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await session.execute(INSERT_CALL_RECORD, call_record_values(call_id="cal_seam_ok"))
        call_ids = (await session.execute(SELECT_CALL_IDS)).scalars().all()

    assert call_ids == ["cal_seam_ok"]


async def test_pristine_connection_without_tenant_context_returns_zero_rows(
    app_sessionmaker, migrate_engine
):
    """No tenant context ever set on this backend: the setting is NULL."""
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await session.execute(INSERT_CALL_RECORD, call_record_values(call_id="cal_pristine"))

    async with app_sessionmaker() as session, session.begin():
        # Proves this really is the pristine path and not the reused one.
        assert (await session.execute(READ_TENANT_GUC)).scalar() is None
        assert (await session.execute(SELECT_CALL_IDS)).all() == []

    # Positive control: the row is there, and the POLICY is what hid it.
    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_CALL_RECORDS)).scalar_one() == 1


async def test_reused_connection_whose_tenant_setting_reverted_returns_zero_rows(
    app_engine, migrate_engine
):
    """Same backend, second transaction: the setting reverted to the empty string."""
    async with app_engine.connect() as connection:
        async with connection.begin():
            await connection.execute(
                text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": WORKSPACE_A}
            )
            await connection.execute(INSERT_CALL_RECORD, call_record_values(call_id="cal_reused"))

        async with connection.begin():
            # The reused path yields '' where the pristine path yields NULL.
            assert (await connection.execute(READ_TENANT_GUC)).scalar() == ""
            assert (await connection.execute(SELECT_CALL_IDS)).all() == []

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_CALL_RECORDS)).scalar_one() == 1


async def test_insert_carrying_another_tenants_workspace_id_is_refused(
    app_sessionmaker, migrate_engine
):
    """ADR-0040's realistic leak: a denormalised, mis-stamped workspace_id.

    WITH CHECK makes it a refused insert rather than another workspace's
    traffic in someone's spend total.
    """
    try:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await session.execute(
                INSERT_CALL_RECORD,
                call_record_values(call_id="cal_mis_stamped", workspace_id=WORKSPACE_B),
            )
    except DBAPIError as error:
        assert "row-level security" in str(error).lower()
    else:
        raise AssertionError("the cross-workspace insert was written, not refused")

    # Nothing was written — refused, not silently swallowed.
    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_CALL_RECORDS)).scalar_one() == 0


async def test_workspace_id_containing_a_quote_round_trips_unchanged(app_sessionmaker):
    """The tenant identifier is bound as a parameter, never assembled into SQL.

    A single quote is what breaks a string-assembled statement. Here it reaches
    the setting intact, matches the policy predicate, and comes back out of the
    column byte-for-byte.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_WITH_QUOTE) as session:
        assert (await session.execute(READ_TENANT_GUC)).scalar() == WORKSPACE_WITH_QUOTE

        await session.execute(
            INSERT_CALL_RECORD,
            call_record_values(call_id="cal_quoted", workspace_id=WORKSPACE_WITH_QUOTE),
        )
        stored = (
            await session.execute(text("SELECT workspace_id FROM ledger.call_record"))
        ).scalar_one()

    assert stored == WORKSPACE_WITH_QUOTE
