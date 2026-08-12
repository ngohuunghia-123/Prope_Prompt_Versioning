"""CL-04: a missing price row is a value. It is not a zero, and it is not silent.

ADR-0019 rejects "treat a missing price as zero" and says why it is the most
dangerous of the alternatives: "it produces a working system. A zero is a number
a reviewer will act on — a revision that looks free is a revision that looks
better than its baseline... An absent figure asks a question; a wrong figure
answers it."

So this file asserts two halves that only mean something together. The first is
that the writer stores the absence: real tokens, NULL cost, NULL currency, NULL
``price_row_id``, ``cost_status = 'unpriced'``. The second is that the absence
is *actionable* — the pair appears on the unpriced worklist with a count and a
``since``, which is the only spend-shaped operational surface in the MVP.

The middle test is the one that stops the first from being self-congratulatory.
It bypasses the writer entirely and shows the engine refusing a zero cost on a
direct insert, with the identical insert at a positive cost as its control. The
never-zero rule is the database's, not the writer's; a writer that stopped
enforcing it would still be caught.
"""

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from prope.call_ledger.domain import CostStatus, UsageStatus
from prope.call_ledger.writer import UNPRICED_WORKLIST, write_records
from prope.db.session import workspace_transaction
from tests.unit import (
    OTHER_UPSTREAM_MODEL,
    PROVIDER_CONFIG,
    UPSTREAM_MODEL,
    VERSION_ID,
    WORKSPACE_A,
    day,
    gateway_draft,
    seed_price_row,
)

READ_CALL_RECORD = text(
    """
    SELECT input_tokens, output_tokens, usage_status,
           cost, currency, price_row_id, cost_status
    FROM   ledger.call_record
    WHERE  call_id = :call_id
    """
)

INSERT_PRICED_CALL = text(
    """
    INSERT INTO ledger.call_record (
        call_id, workspace_id, source, version_id, outcome,
        pinned, fallback, streaming,
        provider_config_id, upstream_model,
        input_tokens, output_tokens, usage_status,
        cost, currency, price_row_id, cost_status,
        created_at
    ) VALUES (
        :call_id, :workspace_id, 'gateway', :version_id, 'ok',
        false, false, false,
        :provider_config_id, :upstream_model,
        300, 150, 'reported',
        :cost, 'USD', :price_row_id, 'priced',
        :created_at
    )
    """
)


def _priced_insert_values(*, call_id: str, price_row_id: str, cost: Decimal) -> dict:
    return {
        "call_id": call_id,
        "workspace_id": WORKSPACE_A,
        "version_id": VERSION_ID,
        "provider_config_id": PROVIDER_CONFIG,
        "upstream_model": UPSTREAM_MODEL,
        "cost": cost,
        "price_row_id": price_row_id,
        "created_at": day(5),
    }


async def test_a_call_with_no_price_row_keeps_its_tokens_and_records_no_cost(
    app_sessionmaker, migrate_engine
):
    """CL-04's storage half. Nothing was seeded, so no price is in force."""
    draft = gateway_draft()

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await write_records(session, [draft])

    assert result.unpriced == 1
    assert result.priced == 0

    async with migrate_engine.begin() as control:
        row = (
            await control.execute(READ_CALL_RECORD, {"call_id": draft.call_id})
        ).mappings().one()

    # The tokens are real and are kept — the gap is in the money, not the usage.
    assert row["input_tokens"] == 300
    assert row["output_tokens"] == 150
    assert row["usage_status"] == UsageStatus.REPORTED.value
    # The absence, stored as an absence.
    assert row["cost"] is None
    assert row["currency"] is None
    assert row["price_row_id"] is None
    assert row["cost_status"] == CostStatus.UNPRICED.value


async def test_a_price_row_that_is_not_yet_effective_is_unpriced_on_the_same_footing(
    app_sessionmaker, migrate_engine
):
    """A row exists for exactly this key and does not apply yet.

    Stored identically to "no row at all" — same NULLs, same status. Asserted
    here at the writer level as well as at the resolver level because this is
    the case where someone is most tempted to reach for the earliest row.
    """
    await seed_price_row(migrate_engine, effective_from=day(10))
    draft = gateway_draft(created_at=day(5))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await write_records(session, [draft])

    assert result.unpriced == 1

    async with migrate_engine.begin() as control:
        row = (
            await control.execute(READ_CALL_RECORD, {"call_id": draft.call_id})
        ).mappings().one()

    assert row["cost"] is None
    assert row["cost_status"] == CostStatus.UNPRICED.value


async def test_zero_refused_by_the_engine_not_merely_by_the_writer(
    app_sessionmaker, migrate_engine
):
    """``ck_call_record_cost_is_never_zero``, asserted around the writer.

    ROADMAP success criterion 2 says "no row anywhere records a cost of zero".
    *Anywhere* is a table-level statement, so it is a table-level constraint —
    and this test proves that by writing directly to the table.

    The positive control is the same statement with a positive cost. Without it,
    a refusal caused by a typo in the column list would read as the guarantee
    holding.
    """
    price_row_id = await seed_price_row(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await session.execute(
            INSERT_PRICED_CALL,
            _priced_insert_values(
                call_id="cal_01J0000000000000000000P1",
                price_row_id=price_row_id,
                cost=Decimal("0.0001350000"),
            ),
        )

    async with migrate_engine.begin() as control:
        assert (
            await control.execute(
                text("SELECT count(*) FROM ledger.call_record WHERE cost > 0")
            )
        ).scalar_one() == 1

    with pytest.raises(DBAPIError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await session.execute(
                INSERT_PRICED_CALL,
                _priced_insert_values(
                    call_id="cal_01J0000000000000000000P2",
                    price_row_id=price_row_id,
                    cost=Decimal("0"),
                ),
            )

    message = str(excinfo.value).lower()
    assert "ck_call_record_cost_is_never_zero" in message, message


async def test_the_unpriced_worklist_returns_the_pair_with_its_count_and_since(
    app_sessionmaker, migrate_engine
):
    """CL-04's actionable half — derivable from the stored encoding by a query.

    Phase 1 owes the encoding, the partial index and this query. Phase 2 owes
    ``GET /api/v1/prices/unpriced``; no route is built here.

    Two calls on one unpriced pair and one on another, plus a priced call that
    must NOT appear — a worklist that lists everything is not a worklist.
    """
    price_row_id = await seed_price_row(migrate_engine, effective_from=day(1))

    drafts = [
        gateway_draft(
            call_id="cal_01J0000000000000000000W1",
            upstream_model=OTHER_UPSTREAM_MODEL,
            created_at=day(7),
        ),
        gateway_draft(
            call_id="cal_01J0000000000000000000W2",
            upstream_model=OTHER_UPSTREAM_MODEL,
            created_at=day(4),
        ),
        gateway_draft(
            call_id="cal_01J0000000000000000000W3",
            upstream_model="claude-haiku-4",
            created_at=day(9),
        ),
        # Priced: this pair HAS a row in force, so it is not on the worklist.
        gateway_draft(call_id="cal_01J0000000000000000000W4", created_at=day(5)),
    ]

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await write_records(session, drafts)

    assert result.priced == 1
    assert result.unpriced == 3
    assert price_row_id

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        worklist = (await session.execute(UNPRICED_WORKLIST)).mappings().all()

    by_model = {row["upstream_model"]: row for row in worklist}

    assert set(by_model) == {OTHER_UPSTREAM_MODEL, "claude-haiku-4"}, (
        "the priced pair leaked onto the worklist, or an unpriced one is missing"
    )
    assert by_model[OTHER_UPSTREAM_MODEL]["provider_config_id"] == PROVIDER_CONFIG
    assert by_model[OTHER_UPSTREAM_MODEL]["unpriced_calls"] == 2
    # ``since`` is the EARLIEST of the two, not the most recent: the question it
    # answers is "how long has this been going unpriced".
    assert by_model[OTHER_UPSTREAM_MODEL]["since"] == day(4)
    assert by_model["claude-haiku-4"]["unpriced_calls"] == 1
    assert by_model["claude-haiku-4"]["since"] == day(9)
