"""The money contract: exact decimal, ten decimal places, banker's rounding.

The whole finding, in one sentence: **quantise at the column's scale, never at
the currency's minor units.** A representative call is a few hundred tokens at a
price of order 0.00015 per 1k, which is about 0.00007. Rounded to two decimal
places that is 0.00 — the row now records a cost of zero, ROADMAP success
criterion 2 forbids it in as many words, and ``ck_call_record_cost_is_never_zero``
would then turn a rounding decision into a write-path outage.

The last test does not assert in Python. It sends a VND-scale figure through
``ledger.call_record.cost`` and reads it back, because "``numeric(20,10)`` is
wide enough" is a claim about the column, and the column is the only thing that
can answer it.
"""

from decimal import Decimal

import pytest
from sqlalchemy import text

from prope.call_ledger.domain import CostStatus, PriceRow, UsageStatus
from prope.call_ledger.pricing import COST_SCALE, compute_cost
from prope.db.session import workspace_transaction
from tests.unit import (
    INPUT_PRICE,
    OUTPUT_PRICE,
    PROVIDER_CONFIG,
    UPSTREAM_MODEL,
    VERSION_ID,
    WORKSPACE_A,
    day,
    seed_price_row,
)

PRICE = PriceRow(
    price_row_id="prc_01J000000000000000000000X",
    input_price_per_1k=INPUT_PRICE,
    output_price_per_1k=OUTPUT_PRICE,
    currency="USD",
    effective_from=day(1),
)

#: A VND-scale price (A-107 allows VND alongside USD and forbids conversion).
VND_PRICE = PriceRow(
    price_row_id="prc_01J000000000000000000000V",
    input_price_per_1k=Decimal("1000"),
    output_price_per_1k=Decimal("3000"),
    currency="VND",
    effective_from=day(1),
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
        :input_tokens, :output_tokens, :usage_status,
        :cost, :currency, :price_row_id, :cost_status,
        :created_at
    )
    """
)

READ_COST = text("SELECT cost FROM ledger.call_record WHERE call_id = :call_id")


def test_a_sub_cent_call_stores_a_strictly_positive_cost():
    """300 input + 150 output tokens at 0.00015 / 0.0006 per 1k.

    (300/1000)*0.00015 + (150/1000)*0.0006 = 0.000045 + 0.00009 = 0.000135.
    Quantised to the column's ten places that is 0.0001350000 — strictly
    positive. Quantised to USD's minor units it would be 0.00.
    """
    cost = compute_cost(300, 150, PRICE)

    assert isinstance(cost, Decimal)
    assert cost > 0, "a realistic sub-cent call rounded away to zero"
    assert cost == Decimal("0.0001350000")
    assert cost.as_tuple().exponent == -10, "the quantum is the column's scale, not the currency's"


def test_one_token_at_the_cheapest_realistic_price_is_still_positive():
    """The floor of the ten-decimal scale sits well below the smallest figure
    the system can produce: one token at 0.00002 per 1k is 2e-8."""
    cheapest = PriceRow(
        price_row_id="prc_01J000000000000000000000C",
        input_price_per_1k=Decimal("0.00002"),
        output_price_per_1k=Decimal("0.00002"),
        currency="USD",
        effective_from=day(1),
    )

    cost = compute_cost(1, 0, cheapest)

    assert cost > 0
    assert cost == Decimal("0.0000000200")


def test_the_same_inputs_produce_a_byte_identical_cost():
    """ADR-0019's figure must be re-derivable years later. Equal value is not
    enough — the exponent has to match too, or the two spell different strings
    into the column."""
    first = compute_cost(1234, 5678, PRICE)
    second = compute_cost(1234, 5678, PRICE)

    assert first == second
    assert first.as_tuple() == second.as_tuple()
    assert str(first) == str(second)


def test_compute_cost_returns_a_decimal_and_refuses_a_binary_price():
    """Handed a binary floating-point price, it raises rather than coercing.

    Coercion is the dangerous branch: it would succeed, produce a plausible
    number, and make the figure non-reproducible in its last places — which is
    precisely the property ADR-0019 needs.
    """
    assert isinstance(compute_cost(10, 10, PRICE), Decimal)

    inexact = PriceRow(
        price_row_id="prc_01J000000000000000000000F",
        input_price_per_1k=0.00015,  # deliberately not a Decimal
        output_price_per_1k=OUTPUT_PRICE,
        currency="USD",
        effective_from=day(1),
    )

    with pytest.raises(TypeError):
        compute_cost(300, 150, inexact)


def test_banker_s_rounding_is_applied_at_the_eleventh_place():
    """Half-even, not half-up, asserted on the only inputs where they differ.

    One input token at 0.00000005 per 1k is exactly 0.00000000005 — a tie at the
    eleventh place. Half-even keeps the even tenth digit, so it goes down to
    zero; three tokens give 0.00000000015, whose tie resolves UP to the even
    0.0000000002. A half-up implementation agrees with half-even on essentially
    every other input, which is why this pair is asserted rather than a
    representative one.
    """
    tie = PriceRow(
        price_row_id="prc_01J000000000000000000000T",
        input_price_per_1k=Decimal("0.00000005"),
        output_price_per_1k=Decimal("0"),
        currency="USD",
        effective_from=day(1),
    )

    rounds_down = compute_cost(1, 0, tie)
    rounds_up = compute_cost(3, 0, tie)

    assert rounds_down == Decimal("0"), "half-up would have produced 0.0000000001 here"
    assert rounds_down.as_tuple().exponent == -10
    assert rounds_up == Decimal("0.0000000002")
    assert COST_SCALE == Decimal("0.0000000001")


#: A flat per-request tariff of one cent, with the same per-1k rates as ``PRICE``
#: so the two can be compared on the same inputs. Migration 0017.
FLOORED = PriceRow(
    price_row_id="prc_01J000000000000000000000M",
    input_price_per_1k=INPUT_PRICE,
    output_price_per_1k=OUTPUT_PRICE,
    currency="USD",
    effective_from=day(1),
    minimum_charge_per_request=Decimal("0.01"),
)


def test_a_call_pricing_below_the_minimum_is_charged_the_minimum():
    """The same 300/150 call as the first test in this file.

    Unfloored it is 0.000135. With a floor of 0.01 it is 0.01 — and the point of
    the floor is that this is what the provider will actually invoice.
    """
    assert compute_cost(300, 150, PRICE) == Decimal("0.0001350000")

    cost = compute_cost(300, 150, FLOORED)

    assert cost == Decimal("0.0100000000")
    assert cost.as_tuple().exponent == -10, (
        "the floor is a Decimal with exponent -2; returning it unquantised would make "
        "str() of the same money depend on whether the floor or the sum won"
    )


def test_a_call_pricing_above_the_minimum_keeps_its_own_cost():
    """A floor floors and does nothing else. 3,000,000 input tokens at 0.00015
    per 1k is 0.45, well clear of the one-cent minimum, and must come back
    byte-identical to the unfloored arithmetic."""
    floored = compute_cost(3_000_000, 0, FLOORED)
    plain = compute_cost(3_000_000, 0, PRICE)

    assert floored == Decimal("0.4500000000")
    assert floored.as_tuple() == plain.as_tuple()


def test_the_minimum_floors_the_whole_call_and_not_each_half():
    """A per-*request* minimum, charged once. Input and output each price to
    0.000045 here; flooring the two halves separately would return 0.02 for one
    call, which is the shape of the bug this test exists to catch."""
    assert compute_cost(300, 75, FLOORED) == Decimal("0.0100000000")


def test_a_zero_minimum_is_the_identity_and_is_what_pre_0017_rows_mean():
    """``minimum_charge_per_request`` defaults to zero on the column and on
    ``PriceRow``, so every row written before 0017 prices exactly as it did."""
    assert PRICE.minimum_charge_per_request == Decimal(0)
    assert compute_cost(1234, 5678, PRICE).as_tuple() == compute_cost(
        1234,
        5678,
        PriceRow(
            price_row_id=PRICE.price_row_id,
            input_price_per_1k=INPUT_PRICE,
            output_price_per_1k=OUTPUT_PRICE,
            currency="USD",
            effective_from=day(1),
            minimum_charge_per_request=Decimal("0"),
        ),
    ).as_tuple()


def test_a_binary_minimum_is_refused_like_a_binary_price():
    """The floor goes through the same Decimal gate the two rates do. It reaches
    the same stored column and would make the same figure non-reproducible."""
    inexact = PriceRow(
        price_row_id="prc_01J000000000000000000000B",
        input_price_per_1k=INPUT_PRICE,
        output_price_per_1k=OUTPUT_PRICE,
        currency="USD",
        effective_from=day(1),
        minimum_charge_per_request=0.01,  # deliberately not a Decimal
    )

    with pytest.raises(TypeError):
        compute_cost(300, 150, inexact)


def test_a_minimum_rescues_the_zero_cost_that_would_discard_a_batch():
    """A call that reports zero tokens prices to zero, and ``write_records``
    raises on a zero cost rather than storing one
    (``ck_call_record_cost_is_never_zero``). Under a floor it prices to the
    floor, which is the honest figure for a provider that bills per request —
    the batch survives because the cost is real, not because the check moved.
    """
    assert compute_cost(0, 0, PRICE) == Decimal("0")
    assert compute_cost(0, 0, FLOORED) == Decimal("0.0100000000")


async def test_a_vnd_scale_cost_round_trips_through_the_numeric_column(
    app_sessionmaker, migrate_engine
):
    """``numeric(20,10)`` is wide enough for a VND price — asserted against the
    column, not against Python.

    A-107 keeps the currency explicit and forbids conversion, so the same column
    holds a USD figure of order 1e-4 and a VND figure of order 1e6. Ten integer
    digits and ten fractional digits span both; if this ever overflows, the fix
    is to widen the column, never to narrow the quantum.
    """
    price_row_id = await seed_price_row(
        migrate_engine,
        price_row_id=VND_PRICE.price_row_id,
        input_price_per_1k=VND_PRICE.input_price_per_1k,
        output_price_per_1k=VND_PRICE.output_price_per_1k,
        currency="VND",
    )

    cost = compute_cost(1_000_000, 500_000, VND_PRICE)
    assert cost == Decimal("2500000.0000000000")

    call_id = "cal_01J000000000000000000000V"
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await session.execute(
            INSERT_PRICED_CALL,
            {
                "call_id": call_id,
                "workspace_id": WORKSPACE_A,
                "version_id": VERSION_ID,
                "provider_config_id": PROVIDER_CONFIG,
                "upstream_model": UPSTREAM_MODEL,
                "input_tokens": 1_000_000,
                "output_tokens": 500_000,
                "usage_status": UsageStatus.REPORTED.value,
                "cost": cost,
                "currency": "VND",
                "price_row_id": price_row_id,
                "cost_status": CostStatus.PRICED.value,
                "created_at": day(5),
            },
        )

    async with migrate_engine.begin() as control:
        stored = (await control.execute(READ_COST, {"call_id": call_id})).scalar_one()

    assert stored == cost
    assert stored.as_tuple().exponent == -10
