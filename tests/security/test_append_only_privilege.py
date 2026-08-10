"""T-006 / D-07: ``ledger.price_table`` is append-only by privilege.

The phase goal says a call is priced *irreversibly*. Irreversibility is not a
code path — it is the absence of ``UPDATE`` and ``DELETE`` on
``ledger.price_table`` for ``prope_app``. ADR-0025 rejects the alternatives by
name: a ``BEFORE UPDATE`` trigger is droppable by the role it polices, and a
repository convention is not enforcement.

**Every test here carries a positive control, and it is load-bearing rather than
decorative.** An ``UPDATE`` that matched zero rows and an ``UPDATE`` the engine
refused are both "nothing changed" from the test's side (Pitfall 8). So each
test first asserts, inside the very transaction that will attempt the write,
that the seeded row *is* visible. Privilege is checked before row security, so a
visible row isolates the privilege from the policy.

The last test goes one step further and is the reason this file can be trusted:
it restores the grant, observes the refusal stop holding, and revokes it again
in a ``finally``. A guarantee nobody can execute is not a guarantee, and this
plan runs autonomously, so the mutation check is a test rather than a procedure
written down for someone who is not there.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.db.session import workspace_transaction
from tests.security import INSERT_CALL_RECORD, WORKSPACE_A, call_record_values

PRICE_ROW_ID = "prc_01J0000000000000000000001"
BODY_CALL_ID = "cal_01J0000000000000000000001"

EFFECTIVE_FROM = datetime(2026, 8, 1, tzinfo=UTC)
EXPIRES_AT = datetime(2026, 9, 1, tzinfo=UTC)
CREATED_AT = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)

INSERT_PRICE_ROW = text(
    """
    INSERT INTO ledger.price_table (
        price_row_id, workspace_id, provider_config_id, upstream_model,
        input_price_per_1k, output_price_per_1k, currency,
        effective_from, created_by
    ) VALUES (
        :price_row_id, :workspace_id, 'prv_01J000000000000000000001', 'gpt-4o-mini',
        0.0001500000, 0.0006000000, 'USD',
        :effective_from, 'usr_01J000000000000000000001'
    )
    """
)

INSERT_CALL_BODY = text(
    """
    INSERT INTO ledger.call_body (
        call_id, workspace_id, request_body, response_body, byte_size,
        expires_at, created_at
    ) VALUES (
        :call_id, :workspace_id, 'a request', 'a response', 18,
        :expires_at, :created_at
    )
    """
)

COUNT_PRICE_ROWS = text("SELECT count(*) FROM ledger.price_table")
COUNT_CALL_RECORDS = text("SELECT count(*) FROM ledger.call_record")
COUNT_CALL_BODIES = text("SELECT count(*) FROM ledger.call_body")

UPDATE_PRICE_ROW = text(
    "UPDATE ledger.price_table SET input_price_per_1k = 9.9999999999 "
    "WHERE price_row_id = :price_row_id"
)
DELETE_PRICE_ROW = text("DELETE FROM ledger.price_table WHERE price_row_id = :price_row_id")
DELETE_CALL_RECORD = text("DELETE FROM ledger.call_record WHERE call_id = :call_id")
DELETE_CALL_BODY = text("DELETE FROM ledger.call_body WHERE call_id = :call_id")

APP_MAY_UPDATE_PRICE_TABLE = text(
    "SELECT has_table_privilege('prope_app', 'ledger.price_table', 'UPDATE')"
)
GRANT_UPDATE_ON_PRICE_TABLE = text("GRANT UPDATE ON ledger.price_table TO prope_app")
REVOKE_UPDATE_ON_PRICE_TABLE = text("REVOKE UPDATE ON ledger.price_table FROM prope_app")


async def _seed_price_row(migrate_engine: AsyncEngine) -> None:
    """Seed as the owner. ``prope_app`` could insert one too, but the owner path
    keeps the seeding independent of the privilege under test."""
    async with migrate_engine.begin() as connection:
        await connection.execute(
            INSERT_PRICE_ROW,
            {
                "price_row_id": PRICE_ROW_ID,
                "workspace_id": WORKSPACE_A,
                "effective_from": EFFECTIVE_FROM,
            },
        )


async def _seed_call_record(migrate_engine: AsyncEngine) -> None:
    async with migrate_engine.begin() as connection:
        await connection.execute(
            INSERT_CALL_RECORD, call_record_values(call_id=BODY_CALL_ID)
        )


async def _seed_call_body(migrate_engine: AsyncEngine) -> None:
    """A body needs its record: ``fk_call_body_call_id`` is intra-schema and real."""
    await _seed_call_record(migrate_engine)
    async with migrate_engine.begin() as connection:
        await connection.execute(
            INSERT_CALL_BODY,
            {
                "call_id": BODY_CALL_ID,
                "workspace_id": WORKSPACE_A,
                "expires_at": EXPIRES_AT,
                "created_at": CREATED_AT,
            },
        )


async def _refusal_text(app_sessionmaker, *, visible, statement, parameters) -> str:
    """Attempt ``statement`` as ``prope_app`` where the seeded row IS visible.

    The visibility assertion runs inside the same transaction as the attempt.
    Without it, this whole file would pass against an empty table.
    """
    with pytest.raises(DBAPIError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            seen = (await session.execute(visible)).scalar_one()
            assert seen == 1, (
                "positive control failed: the seeded row is not visible to prope_app, "
                "so a refusal below would be indistinguishable from an empty table"
            )
            await session.execute(statement, parameters)
    return str(excinfo.value).lower()


async def test_update_on_price_table_is_refused_by_the_engine(app_sessionmaker, migrate_engine):
    """T-006. A price is never edited — a change is a new row with a later
    ``effective_from``, and the old row stays because a cost recorded under it
    must remain explicable."""
    await _seed_price_row(migrate_engine)

    message = await _refusal_text(
        app_sessionmaker,
        visible=COUNT_PRICE_ROWS,
        statement=UPDATE_PRICE_ROW,
        parameters={"price_row_id": PRICE_ROW_ID},
    )

    assert "permission denied" in message
    assert "price_table" in message


async def test_delete_on_price_table_is_refused_by_the_engine(app_sessionmaker, migrate_engine):
    """The other half of T-006. Deleting the row a cost was derived from would
    make that cost unexplainable, which is the failure ADR-0019 exists to
    prevent."""
    await _seed_price_row(migrate_engine)

    message = await _refusal_text(
        app_sessionmaker,
        visible=COUNT_PRICE_ROWS,
        statement=DELETE_PRICE_ROW,
        parameters={"price_row_id": PRICE_ROW_ID},
    )

    assert "permission denied" in message
    assert "price_table" in message


async def test_delete_on_call_record_is_refused_by_the_engine(app_sessionmaker, migrate_engine):
    """T-008. ``UPDATE`` is retained for A-099's upsert and CL-05 repricing;
    ``DELETE`` is absent because nothing in the module deletes a call record and
    NFR-02's audit trail depends on that staying true."""
    await _seed_call_record(migrate_engine)

    message = await _refusal_text(
        app_sessionmaker,
        visible=COUNT_CALL_RECORDS,
        statement=DELETE_CALL_RECORD,
        parameters={"call_id": BODY_CALL_ID},
    )

    assert "permission denied" in message
    assert "call_record" in message


async def test_delete_on_call_body_succeeds_because_retention_must_have_it(
    app_sessionmaker, migrate_engine
):
    """The one privilege whose *presence* is the guarantee (A-106, CL-08).

    Asserted so a later "tighten the grants" pass cannot break retention
    silently. Verified by direct query as the owner rather than through the
    application session — under RLS an app-session read could return zero rows
    whether or not the delete worked (the lock's security test plan requires
    exactly this).
    """
    await _seed_call_body(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert (await session.execute(COUNT_CALL_BODIES)).scalar_one() == 1
        result = await session.execute(DELETE_CALL_BODY, {"call_id": BODY_CALL_ID})
        assert result.rowcount == 1

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_CALL_BODIES)).scalar_one() == 0
        # A-040: the body goes, the metadata stays. That is why these are two
        # tables and why the foreign key carries no ON DELETE clause.
        assert (await control.execute(COUNT_CALL_RECORDS)).scalar_one() == 1


async def test_the_append_only_refusal_has_teeth(app_sessionmaker, migrate_engine):
    """The mutation check, as a test rather than as a procedure nobody runs.

    Restore the privilege the two refusal tests above depend on, observe that
    the refusal stops holding, then revoke it again. If this passes, those tests
    are asserting the engine's refusal rather than an empty table or a no-op
    update. The ``finally`` is what stops a failure here from leaving the
    privilege matrix loosened for every test that follows in the session.
    """
    await _seed_price_row(migrate_engine)

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(APP_MAY_UPDATE_PRICE_TABLE)).scalar_one() is False

    try:
        async with migrate_engine.begin() as connection:
            await connection.execute(GRANT_UPDATE_ON_PRICE_TABLE)

        async with migrate_engine.begin() as connection:
            assert (await connection.execute(APP_MAY_UPDATE_PRICE_TABLE)).scalar_one() is True

        # A fresh transaction: privilege is re-checked per statement, but the
        # committed grant has to be visible to the statement that tests it.
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            assert (await session.execute(COUNT_PRICE_ROWS)).scalar_one() == 1
            # The very statement tests 1 and 2 expect to be refused.
            result = await session.execute(
                UPDATE_PRICE_ROW, {"price_row_id": PRICE_ROW_ID}
            )
            assert result.rowcount == 1, (
                "with UPDATE granted the write should land; if it did not, the "
                "refusal tests above may be passing for some other reason"
            )
    finally:
        async with migrate_engine.begin() as connection:
            await connection.execute(REVOKE_UPDATE_ON_PRICE_TABLE)

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(APP_MAY_UPDATE_PRICE_TABLE)).scalar_one() is False
