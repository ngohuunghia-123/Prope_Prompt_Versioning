"""AC-11 / INT-021: the two counts are part of the answer, not diagnostics.

``get_run_totals`` is what evaluation subtracts a baseline from to produce a cost
delta, and the counts are what let it **withhold** the delta instead of
publishing a wrong one. So the failure this file is shaped against is not a
wrong total — it is a *plausible* total.

**A partly unpriced run returns a smaller number, and a smaller number is not an
error.** A delta computed over it would be confidently wrong and would look
exactly like a cheaper revision, which is the sentence a reviewer is about to
act on. Every test here therefore asserts the counts alongside the totals, and
the mixed run asserts that the unpriced rows contributed *nothing* to the cost
rather than contributing a zero.

**The two counts do not overlap and neither is derivable from the other.**
``unpriced_count`` filters ``cost_status`` and ``unknown_usage_count`` filters
``usage_status``, and a record whose provider returned no usage object carries
``cost_status = 'not_applicable'`` — so it is counted once, by the second filter,
and never by the first. A run holding one of each reports 1 and 1. An
implementation that collapsed them would report 2 and 0, or 1 and 0, and both
are a number a review screen would believe.

**A ``run_id`` alone is not an identity, and that is asserted rather than
implied.** Under ADR-0045 a read issued in workspace A's context cannot see
workspace B's rows, so the same ``run_id`` in two workspaces is two runs. The
test that writes a run into one workspace and reads it from another is the
companion invariant for D-20's promotion of ``workspace_id`` to the leading
identity component — it is what a future one-argument convenience wrapper would
have to break.

Every assertion about stored state goes through ``migrate_engine``.
"""

import inspect
from dataclasses import fields
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.call_ledger.seams import RunTotals, get_run_totals, price_usage
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from tests.unit import (
    OTHER_UPSTREAM_MODEL,
    RUN_ID,
    WORKSPACE_A,
    WORKSPACE_B,
    day,
    eval_draft,
    eval_row,
    seed_price_row,
)

COUNT_RECORDS_FOR_RUN = text("SELECT count(*) FROM ledger.call_record WHERE run_id = :run_id")

OTHER_RUN_ID = "run_01J000000000000000000002"

#: One ``eval_row``: 200 input and 100 output tokens at 0.00015 / 0.0006 per 1k.
EVAL_COST = Decimal("0.00009")

FIRST_PRICE_ROW = "prc_01J0000000000000000000001"


def _rows(count: int, *, first: int = 1, **overrides):
    """``count`` eval rows with distinct call ids, otherwise identical."""
    return [
        eval_row(call_id=f"cal_01J000000000000000000{500 + first + index:04d}", **overrides)
        for index in range(count)
    ]


async def _count_for_run(migrate_engine: AsyncEngine, run_id: str) -> int:
    async with migrate_engine.connect() as connection:
        return (await connection.execute(COUNT_RECORDS_FOR_RUN, {"run_id": run_id})).scalar_one()


async def test_a_fully_priced_run_returns_its_totals_and_two_zero_counts(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)
    await price_usage(app_sessionmaker, RUN_ID, _rows(5))
    assert await _count_for_run(migrate_engine, RUN_ID) == 5

    totals = await get_run_totals(app_sessionmaker, WORKSPACE_A, RUN_ID)

    assert totals.input_tokens == 1000
    assert totals.output_tokens == 500
    assert totals.cost == EVAL_COST * 5
    assert totals.currency == "USD"
    assert totals.unpriced_count == 0
    assert totals.unknown_usage_count == 0


async def test_unpriced_rows_are_counted_and_contribute_nothing_to_the_cost(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """A missing price is a value. The cost is the priced rows' cost, and no more."""
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)
    priced = _rows(2, first=10)
    unpriced = _rows(3, first=20, upstream_model=OTHER_UPSTREAM_MODEL)
    await price_usage(app_sessionmaker, RUN_ID, [*priced, *unpriced])

    totals = await get_run_totals(app_sessionmaker, WORKSPACE_A, RUN_ID)

    assert totals.unpriced_count == 3
    assert totals.unknown_usage_count == 0
    assert totals.cost == EVAL_COST * 2, "an unpriced row must not contribute a zero"
    assert totals.currency == "USD"
    # The tokens WERE reported for the unpriced rows — only the price is absent —
    # so all five rows contribute to the token totals.
    assert totals.input_tokens == 1000
    assert totals.output_tokens == 500


async def test_unknown_usage_rows_are_counted_and_contribute_no_tokens(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)
    priced = _rows(2, first=30)
    unknown = _rows(2, first=40, input_tokens=None, output_tokens=None)
    await price_usage(app_sessionmaker, RUN_ID, [*priced, *unknown])

    totals = await get_run_totals(app_sessionmaker, WORKSPACE_A, RUN_ID)

    assert totals.unknown_usage_count == 2
    assert totals.unpriced_count == 0, (
        "an unknown-usage row carries cost_status = 'not_applicable', never 'unpriced'"
    )
    assert totals.input_tokens == 400
    assert totals.output_tokens == 200
    assert totals.cost == EVAL_COST * 2


async def test_one_unpriced_row_and_one_unknown_row_report_one_and_one(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """The counts do not overlap, and neither is derivable from the other.

    2 and 0 would be a single "incomplete" count wearing two names; 1 and 0
    would be one filter doing both jobs. Both are numbers a review screen would
    accept.
    """
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)
    await price_usage(
        app_sessionmaker,
        RUN_ID,
        [
            *_rows(1, first=50),
            *_rows(1, first=60, upstream_model=OTHER_UPSTREAM_MODEL),
            *_rows(1, first=70, input_tokens=None, output_tokens=None),
        ],
    )

    totals = await get_run_totals(app_sessionmaker, WORKSPACE_A, RUN_ID)

    assert (totals.unpriced_count, totals.unknown_usage_count) == (1, 1)


async def test_the_unknown_count_equals_what_write_records_reported(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """``WriteResult.unknown`` and this projection must be the same number.

    ``domain.WriteResult``'s docstring commits to it: the write-side count comes
    from ``usage_status`` rather than from asking whether a token column is
    NULL, precisely so that a ``count(*) FILTER (WHERE usage_status = 'unknown')``
    computed later gets the same answer. Two ways of counting the same thing is
    how they come to disagree.
    """
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)
    drafts = [
        eval_draft(call_id="cal_01J0000000000000000000801"),
        eval_draft(call_id="cal_01J0000000000000000000802", input_tokens=None, output_tokens=None),
        eval_draft(call_id="cal_01J0000000000000000000803", input_tokens=None, output_tokens=None),
    ]
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await write_records(session, drafts)

    totals = await get_run_totals(app_sessionmaker, WORKSPACE_A, RUN_ID)

    assert result.unknown == 2
    assert totals.unknown_usage_count == result.unknown
    assert totals.unpriced_count == result.unpriced


async def test_a_run_with_no_rows_returns_zeroed_totals_and_raises_nothing(
    app_sessionmaker,
) -> None:
    totals = await get_run_totals(app_sessionmaker, WORKSPACE_A, OTHER_RUN_ID)

    assert totals.input_tokens == 0
    assert totals.output_tokens == 0
    assert totals.unpriced_count == 0
    assert totals.unknown_usage_count == 0
    # NOT ``Decimal(0)``. A zero cost beside a NULL currency is a number with no
    # unit, and ``ck_workspace_spend_total_cost_carries_currency`` refuses that
    # shape one table over. "Nothing priced" is an absence, and the token totals
    # above are where the zeroes honestly belong.
    assert totals.cost is None
    assert totals.currency is None


async def test_a_run_belonging_to_another_workspace_is_invisible_and_returns_zeroes(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """D-20's companion invariant: a ``run_id`` alone is not an identity.

    The rows exist — asserted through ``migrate_engine``, which is subject to no
    policy — and this workspace's context cannot see them. A one-argument
    convenience wrapper added later would have to break this test, which is the
    point of writing it.
    """
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW, workspace_id=WORKSPACE_B)
    await price_usage(app_sessionmaker, RUN_ID, _rows(3, first=80, workspace_id=WORKSPACE_B))
    assert await _count_for_run(migrate_engine, RUN_ID) == 3, "the rows must really exist"

    theirs = await get_run_totals(app_sessionmaker, WORKSPACE_B, RUN_ID)
    assert theirs.input_tokens == 600

    ours = await get_run_totals(app_sessionmaker, WORKSPACE_A, RUN_ID)

    assert ours.input_tokens == 0
    assert ours.output_tokens == 0
    assert ours.cost is None
    assert ours.unpriced_count == 0
    assert ours.unknown_usage_count == 0


async def test_a_run_spanning_two_currencies_raises_naming_both(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """A-107: no conversion, so a sum across two currencies is a number with no unit.

    The two rows are written in two ``price_usage`` calls and two months, which
    is the only reachable shape: ``write_records`` already refuses a
    mixed-currency *batch*, and ``UPSERT_WORKSPACE_SPEND``'s one-currency
    invariant refuses a second currency in the same ``(workspace, month)``. A run
    that crosses a month boundary while a price row's currency changes is exactly
    what is left, and it is a run, so this function has to answer for it.
    """
    await seed_price_row(migrate_engine, price_row_id=FIRST_PRICE_ROW)
    await seed_price_row(
        migrate_engine,
        price_row_id="prc_01J0000000000000000000002",
        upstream_model=OTHER_UPSTREAM_MODEL,
        currency="VND",
    )

    await price_usage(app_sessionmaker, RUN_ID, _rows(1, first=90))
    await price_usage(
        app_sessionmaker,
        RUN_ID,
        _rows(1, first=95, upstream_model=OTHER_UPSTREAM_MODEL, created_at=day(40)),
    )

    with pytest.raises(ValueError) as raised:
        await get_run_totals(app_sessionmaker, WORKSPACE_A, RUN_ID)

    message = str(raised.value)
    assert "USD" in message
    assert "VND" in message
    assert RUN_ID in message


async def test_run_totals_has_exactly_the_six_registered_fields() -> None:
    """INT-021's return shape, field for field and in order."""
    assert [field.name for field in fields(RunTotals)] == [
        "input_tokens",
        "output_tokens",
        "cost",
        "currency",
        "unpriced_count",
        "unknown_usage_count",
    ]


async def test_the_signature_takes_the_workspace_before_the_run() -> None:
    """D-20. ``workspace_id`` leads, matching ``ix_call_record_workspace_id_run_id``."""
    parameters = list(inspect.signature(get_run_totals).parameters)
    assert parameters[:3] == ["sessionmaker", "workspace_id", "run_id"]


async def test_both_counts_are_computed_from_the_stored_encoding() -> None:
    """The statement filters the two status columns, not the token columns.

    Counting unknown usage as "input_tokens IS NULL" would be a second
    definition of the same fact, sitting beside ``usage_status``, free to drift
    from it the first time a column is allowed to be NULL for another reason.
    """
    from prope.call_ledger.seams import RUN_TOTALS

    statement = RUN_TOTALS.text
    assert "FILTER (WHERE cost_status = 'unpriced')" in statement
    assert "FILTER (WHERE usage_status = 'unknown')" in statement
