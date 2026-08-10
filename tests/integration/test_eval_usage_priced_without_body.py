"""AC-9 / CL-09: an eval usage row priced at its own instant, counted, bodyless.

This is the *priced and counted* half of CL-09. Plan 02-02 built and asserted the
*no body stored* half (``tests/security/test_eval_no_body_boundary.py``), and the
two together are the whole requirement.

Three failure modes shape every test here, and not one of them looks like a
failure from inside ``price_usage``.

**A row that is written but not counted looks like a pass.** ``write_records``
returns a ``WriteResult`` and ``price_usage`` returns nothing at all, so there is
no return value here worth believing. Every assertion is a direct query through
``migrate_engine`` — the owner role, subject to no policy — against
``ledger.call_record``, ``ledger.call_body`` and ``ledger.workspace_spend``.
Reading the same rows back through an application session would prove the tenant
context was set, not what the columns hold.

**A row that is counted but priced at the wrong instant looks identical to a
correct one until a price changes.** ADR-0019 prices at the record's own
``created_at``, and a drain or an eval run catching up across a price change is
exactly when "priced at wall clock" and "priced at its own timestamp" diverge. So
the effective-dating test seeds *two* price rows and asserts the stored
``price_row_id``, not the cost — a cost can coincide, an id cannot.

**"On the same footing as a gateway call" is a claim about a shared total, so it
cannot be asserted from an eval row alone.** The footing test writes a gateway
call through ``write_records`` and an eval row through ``price_usage`` into the
same workspace and the same month, and asserts one ``workspace_spend`` row whose
``total_cost`` is the sum of both and whose ``call_count`` covers both. A-098's
"one table, one spend total" is a property of the pair.
"""

import inspect
from dataclasses import MISSING, fields
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.call_ledger.seams import EvalUsageRow, price_usage
from prope.call_ledger.writer import period_month, write_records
from prope.db.session import workspace_transaction
from tests.unit import (
    OTHER_UPSTREAM_MODEL,
    RUN_ID,
    WORKSPACE_A,
    WORKSPACE_B,
    day,
    eval_row,
    gateway_draft,
    seed_price_row,
)

READ_RECORD = text(
    """
    SELECT source, version_id, run_id, case_id, consumer_key_id,
           input_tokens, output_tokens, usage_status,
           cost, currency, price_row_id, cost_status, created_at
    FROM   ledger.call_record WHERE call_id = :call_id
    """
)
COUNT_BODIES_FOR_CALL = text("SELECT count(*) FROM ledger.call_body WHERE call_id = :call_id")
COUNT_RECORDS_FOR = text("SELECT count(*) FROM ledger.call_record WHERE workspace_id = :ws")
READ_SPEND = text(
    """
    SELECT currency, total_cost, call_count FROM ledger.workspace_spend
    WHERE  workspace_id = :ws AND period_month = :month
    """
)

#: ``eval_row``'s 200 input and 100 output tokens at the fixture prices:
#: (200/1000)*0.00015 + (100/1000)*0.0006. Written out rather than computed with
#: ``compute_cost``, which would make this test agree with the implementation by
#: construction instead of by arithmetic.
EVAL_COST = Decimal("0.00009")

#: ``gateway_draft``'s 300 input and 150 output tokens at the same prices.
GATEWAY_COST = Decimal("0.000135")

#: The second price row in the effective-dating test: double the fixture prices,
#: in force from day 8.
LATER_INPUT_PRICE = Decimal("0.0003")
LATER_OUTPUT_PRICE = Decimal("0.0012")

FIRST_PRICE_ROW = "prc_01J0000000000000000000001"
SECOND_PRICE_ROW = "prc_01J0000000000000000000002"


async def _record(migrate_engine: AsyncEngine, call_id: str) -> dict | None:
    async with migrate_engine.connect() as connection:
        row = (await connection.execute(READ_RECORD, {"call_id": call_id})).mappings().first()
    return dict(row) if row is not None else None


async def _scalar(migrate_engine: AsyncEngine, statement, params) -> object:
    async with migrate_engine.connect() as connection:
        return (await connection.execute(statement, params)).scalar_one()


async def _spend(migrate_engine: AsyncEngine, workspace_id: str, month) -> dict | None:
    async with migrate_engine.connect() as connection:
        row = (
            (await connection.execute(READ_SPEND, {"ws": workspace_id, "month": month}))
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


async def test_an_eval_row_is_priced_stored_and_carries_no_body(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """AC-9's whole first clause, read off the stored row rather than a return value."""
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)

    row = eval_row()
    await price_usage(app_sessionmaker, RUN_ID, [row])

    stored = await _record(migrate_engine, row.call_id)
    assert stored is not None, "price_usage returned without writing a call_record row"
    assert stored["source"] == "eval"
    assert stored["run_id"] == RUN_ID
    assert stored["case_id"] == row.case_id
    assert stored["version_id"] == row.version_id
    # ck_call_record_eval_calls_carry_run requires this to be NULL for eval, and
    # EvalUsageRow has no field that could set it. Asserted rather than assumed,
    # because "unrepresentable in the input type" is a claim about the type and
    # this is the claim about what reached the table.
    assert stored["consumer_key_id"] is None
    assert stored["usage_status"] == "reported"
    assert stored["cost_status"] == "priced"
    assert stored["cost"] == EVAL_COST
    assert stored["currency"] == "USD"
    assert stored["price_row_id"] == FIRST_PRICE_ROW

    bodies = await _scalar(migrate_engine, COUNT_BODIES_FOR_CALL, {"call_id": row.call_id})
    assert bodies == 0, "an eval call must never have a call_body row (A-055)"


async def test_the_eval_row_lands_on_the_same_spend_total_as_a_gateway_call(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """A-098: one table, one price path, one answer to "what did this workspace spend"."""
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)

    gateway = gateway_draft()
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await write_records(session, [gateway])

    row = eval_row()
    await price_usage(app_sessionmaker, RUN_ID, [row])

    month = period_month(row.created_at)
    assert period_month(gateway.created_at) == month, "the fixture must put both in one month"

    spend = await _spend(migrate_engine, WORKSPACE_A, month)
    assert spend is not None
    assert spend["currency"] == "USD"
    assert spend["total_cost"] == GATEWAY_COST + EVAL_COST
    assert spend["call_count"] == 2, "the eval row counts as traffic, exactly like the gateway call"


async def test_an_eval_row_is_priced_at_the_row_in_force_on_its_own_day(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """Created day 5, written "on day 12", price changed day 8 — the day-5 price wins.

    The stored ``price_row_id`` is the assertion, not the cost. Two price rows
    could in principle produce the same figure; they cannot share an id, and
    ADR-0019 stores the cost *with the row that produced it* precisely so the
    number stays explicable years later.
    """
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)
    await seed_price_row(
        migrate_engine,
        price_row_id=SECOND_PRICE_ROW,
        input_price_per_1k=LATER_INPUT_PRICE,
        output_price_per_1k=LATER_OUTPUT_PRICE,
        effective_from=day(8),
    )

    backlogged = eval_row(call_id="cal_01J0000000000000000000101", created_at=day(5))
    fresh = eval_row(call_id="cal_01J0000000000000000000102", created_at=day(10))
    await price_usage(app_sessionmaker, RUN_ID, [backlogged, fresh])

    stored_backlogged = await _record(migrate_engine, backlogged.call_id)
    assert stored_backlogged is not None
    assert stored_backlogged["price_row_id"] == FIRST_PRICE_ROW
    assert stored_backlogged["cost"] == EVAL_COST

    # The positive control. Without it this test would also pass against an
    # implementation that always resolved the earliest price row in the table.
    stored_fresh = await _record(migrate_engine, fresh.call_id)
    assert stored_fresh is not None
    assert stored_fresh["price_row_id"] == SECOND_PRICE_ROW
    assert stored_fresh["cost"] == EVAL_COST * 2


async def test_an_eval_row_with_no_price_row_is_unpriced_and_its_cost_is_null(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """A missing price is a value, never a zero (BR-07, A-101, ADR-0019)."""
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)

    row = eval_row(upstream_model=OTHER_UPSTREAM_MODEL)
    await price_usage(app_sessionmaker, RUN_ID, [row])

    stored = await _record(migrate_engine, row.call_id)
    assert stored is not None
    assert stored["cost_status"] == "unpriced"
    assert stored["usage_status"] == "reported", "the tokens were reported; only the price is absent"
    assert stored["input_tokens"] == 200
    # Two assertions rather than one. ``is None`` is the property; the second
    # line is what fails loudly if a later change substitutes a zero, because
    # ``Decimal(0) is None`` and ``Decimal(0) == 0`` disagree.
    assert stored["cost"] is None
    assert stored["cost"] != Decimal(0)
    assert stored["currency"] is None
    assert stored["price_row_id"] is None


async def test_an_eval_row_with_no_usage_object_is_unknown_with_null_tokens(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """No usage object is not zero tokens, and not-applicable is not unpriced."""
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)

    row = eval_row(input_tokens=None, output_tokens=None)
    await price_usage(app_sessionmaker, RUN_ID, [row])

    stored = await _record(migrate_engine, row.call_id)
    assert stored is not None
    assert stored["usage_status"] == "unknown"
    assert stored["input_tokens"] is None
    assert stored["output_tokens"] is None
    # A price row DID exist for this key. not_applicable rather than unpriced is
    # what says "there was nothing to price", which is a different sentence from
    # "there was no price".
    assert stored["cost_status"] == "not_applicable"
    assert stored["cost"] is None


async def test_a_row_without_a_case_id_is_refused_and_nothing_is_written(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """The refusal names ``case_id``, not ``ck_call_record_eval_calls_carry_run``.

    The refusal fires while ``price_usage``'s arguments are being built — the
    input type is where an eval row without a case is unrepresentable, which is
    strictly earlier than any transaction and earlier than the engine. From the
    caller's seat the call raises ``ValueError`` and writes nothing, which is
    what INT-019 promises; where inside the call it happened is what makes the
    message actionable.
    """
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)

    with pytest.raises(ValueError, match="case_id"):
        await price_usage(app_sessionmaker, RUN_ID, [eval_row(case_id=None)])

    written = await _scalar(migrate_engine, COUNT_RECORDS_FOR, {"ws": WORKSPACE_A})
    assert written == 0


async def test_the_input_type_cannot_carry_a_body_at_all(app_sessionmaker) -> None:
    """A-055's strongest available form: not refused, unrepresentable.

    ``write_records`` refuses an eval draft carrying a body and plan 02-02
    asserted both that refusal and the *absence* of any database constraint
    behind it. This seam adds the line in front of both: there is no field on
    ``EvalUsageRow`` that a body could arrive on, so the refusal has nothing to
    catch.
    """
    names = {field.name for field in fields(EvalUsageRow)}
    assert not names & {"body", "request_body", "response_body", "byte_size"}
    assert not any("body" in name for name in names)


async def test_case_id_is_a_required_field_with_no_default(app_sessionmaker) -> None:
    """Required in the dataclass sense, so omitting it cannot reach the engine."""
    case_id = next(field for field in fields(EvalUsageRow) if field.name == "case_id")
    assert case_id.default is MISSING
    assert case_id.default_factory is MISSING


async def test_a_refusal_inside_the_transaction_leaves_the_whole_batch_unwritten(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """The transaction ``price_usage`` opened rolled back — not "most of it landed".

    The second row has a price row and zero tokens, which prices to zero, which
    ``ck_call_record_cost_is_never_zero`` forbids and ``write_records`` refuses
    by name. That refusal happens *after* the transaction is open, which is the
    branch this test exists for; the ``case_id`` refusal above happens before one
    is opened and proves a different thing.
    """
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)

    good = eval_row(call_id="cal_01J0000000000000000000201")
    zero_cost = eval_row(
        call_id="cal_01J0000000000000000000202", input_tokens=0, output_tokens=0
    )

    with pytest.raises(ValueError):
        await price_usage(app_sessionmaker, RUN_ID, [good, zero_cost])

    written = await _scalar(migrate_engine, COUNT_RECORDS_FOR, {"ws": WORKSPACE_A})
    assert written == 0, "the legal batch-mate must not survive its neighbour's refusal"


async def test_a_row_belonging_to_another_run_is_refused(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """``run_id`` is the argument AND a column; the two disagreeing is a caller bug.

    Left unchecked it is invisible: the row lands, and ``get_run_totals`` for the
    run the caller thinks it wrote simply reports one fewer case — an
    undercount that reads as a legitimately smaller run.
    """
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)

    with pytest.raises(ValueError, match="run_01J000000000000000000099"):
        await price_usage(
            app_sessionmaker, RUN_ID, [eval_row(run_id="run_01J000000000000000000099")]
        )

    written = await _scalar(migrate_engine, COUNT_RECORDS_FOR, {"ws": WORKSPACE_A})
    assert written == 0


async def test_a_batch_spanning_two_workspaces_is_refused_before_a_transaction_opens(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """ADR-0040: one transaction carries exactly one workspace, so a batch does too."""
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)

    with pytest.raises(ValueError, match="workspace"):
        await price_usage(
            app_sessionmaker,
            RUN_ID,
            [
                eval_row(call_id="cal_01J0000000000000000000301"),
                eval_row(call_id="cal_01J0000000000000000000302", workspace_id=WORKSPACE_B),
            ],
        )

    for workspace_id in (WORKSPACE_A, WORKSPACE_B):
        written = await _scalar(migrate_engine, COUNT_RECORDS_FOR, {"ws": workspace_id})
        assert written == 0


async def test_an_empty_batch_writes_nothing_and_raises_nothing(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """A run with no cases is a run, not an error."""
    await price_usage(app_sessionmaker, RUN_ID, [])

    written = await _scalar(migrate_engine, COUNT_RECORDS_FOR, {"ws": WORKSPACE_A})
    assert written == 0


async def test_price_usage_takes_a_sessionmaker_and_writes_no_sql_of_its_own() -> None:
    """D-19's shape, and the "one implementation of the write path" rule.

    The first parameter is a ``sessionmaker`` rather than a session, which is
    what lets this seam own its own transaction boundary and therefore raise
    without taking evaluation's transaction down with it. And the body contains
    no ``text(`` call: pricing, the ``expires_at`` stamp, the three cost states
    and the monthly aggregate all live in ``write_records``, and a second SQL
    statement here would be a second place for them to drift.
    """
    parameters = list(inspect.signature(price_usage).parameters)
    assert parameters[0] == "sessionmaker"

    source = inspect.getsource(price_usage)
    assert "text(" not in source
    assert "write_records" in source
