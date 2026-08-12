"""WARN-2 / T-02-13: a spend total is never labelled with a currency it does not contain.

``ledger.workspace_spend`` holds one ``(workspace_id, period_month)`` row with
one ``currency`` and one ``total_cost``. A-107 forbids conversion, so a total
summing USD and VND is a number with no unit — and the row's own CHECK cannot
see it, because ``ck_workspace_spend_currency_format`` validates the *shape* of
the label and knows nothing about what the total is made of.

Phase 1 enforced the invariant by reading the stored currency and then upserting.
Its verifier logged that as WARN-2: **unreachable in Phase 1 because nothing ran
``write_records`` concurrently, and live the moment a drain exists.** Two drains
that both read "no row yet" and then both write are exactly the interleave the
read cannot see.

The fix carries the invariant into the statement — ``ON CONFLICT ... DO UPDATE
... WHERE`` — so a conflicting currency makes the row not match, the update is
skipped, and ``rowcount`` is 0. This file proves three separate things, because
one of them alone would not be enough:

1. **The engine refuses**, deterministically, at the statement. Without this the
   two tests below could pass on the pre-read alone, which is the mechanism
   WARN-2 says is insufficient.
2. **A matching currency still updates.** A ``WHERE`` that is always false would
   satisfy (1) and break every ordinary write, and the ordinary-write tests live
   in another file where this change would read as unrelated.
3. **The race itself**, reproduced against the live engine — once with the
   interleave pinned by hand, and once with two genuinely overlapping
   transactions.

Every assertion about what was stored goes through ``migrate_engine``. Asking the
writer what it wrote would be asking the code under test to grade itself.
"""

import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.call_ledger.writer import (
    READ_SPEND_CURRENCY,
    UPSERT_WORKSPACE_SPEND,
    period_month,
    write_records,
)
from prope.db.session import workspace_transaction
from tests.unit import (
    OTHER_PROVIDER_CONFIG,
    OTHER_UPSTREAM_MODEL,
    WORKSPACE_A,
    day,
    gateway_draft,
    seed_price_row,
)

#: Both calls are made on the same day, so both file into the same
#: ``(workspace_id, period_month)`` row — which is the row the two currencies
#: have to fight over. Anything else and there is no conflict to observe.
CREATED_AT = day(5)
MONTH = period_month(CREATED_AT)

#: A VND price of order 1000 per 1k tokens, against a USD price of order 0.00015.
#: That four-orders-of-magnitude gap is the whole reason ``numeric(20,10)`` is
#: the money type, and it makes a mislabelled total obvious rather than subtle.
VND_INPUT_PRICE = Decimal("1000")
VND_OUTPUT_PRICE = Decimal("2000")

USD_CALL = "cal_01J000000000000000000USD"
VND_CALL = "cal_01J000000000000000000VND"

READ_SPEND_ROW = text(
    "SELECT currency, total_cost, call_count FROM ledger.workspace_spend "
    "WHERE workspace_id = :ws AND period_month = :month"
)
COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")
LIST_RECORD_CURRENCIES = text(
    "SELECT call_id, currency FROM ledger.call_record ORDER BY call_id"
)


async def _seed_two_currencies(migrate_engine: AsyncEngine) -> None:
    """A USD price and a VND price, on two different provider/model keys.

    Two keys rather than two ``effective_from`` values on one key:
    ``uq_price_table_workspace_id`` would accept the second row, but the
    effective-dated resolver returns only the latest, so both calls would price
    in the same currency and there would be nothing to test.
    """
    await seed_price_row(migrate_engine, price_row_id="prc_01J00000000000000000USD", currency="USD")
    await seed_price_row(
        migrate_engine,
        price_row_id="prc_01J00000000000000000VND",
        currency="VND",
        provider_config_id=OTHER_PROVIDER_CONFIG,
        upstream_model=OTHER_UPSTREAM_MODEL,
        input_price_per_1k=VND_INPUT_PRICE,
        output_price_per_1k=VND_OUTPUT_PRICE,
    )


def _usd_draft():
    return gateway_draft(call_id=USD_CALL, created_at=CREATED_AT)


def _vnd_draft():
    return gateway_draft(
        call_id=VND_CALL,
        created_at=CREATED_AT,
        provider_config_id=OTHER_PROVIDER_CONFIG,
        upstream_model=OTHER_UPSTREAM_MODEL,
    )


async def _write(app_sessionmaker, drafts):
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        return await write_records(session, drafts)


async def _spend_row(migrate_engine: AsyncEngine):
    async with migrate_engine.begin() as control:
        return (
            await control.execute(READ_SPEND_ROW, {"ws": WORKSPACE_A, "month": MONTH})
        ).mappings().first()


async def test_the_upsert_statement_itself_refuses_a_conflicting_currency(
    app_sessionmaker, migrate_engine
):
    """(1) The invariant is in the statement, not only in the read above it.

    Driven directly rather than through ``write_records``, because
    ``write_records``' pre-read would catch this case first and the point is that
    the engine catches it too. A zero ``rowcount`` here is the refusal the writer
    turns into a raise.
    """
    await _seed_two_currencies(migrate_engine)
    await _write(app_sessionmaker, [_usd_draft()])

    assert (await _spend_row(migrate_engine))["currency"] == "USD", "positive control"

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await session.execute(
            UPSERT_WORKSPACE_SPEND,
            {
                "workspace_id": WORKSPACE_A,
                "period_month": MONTH,
                "currency": "VND",
                "total_cost": Decimal("450"),
                "call_count": 1,
            },
        )
        assert result.rowcount == 0, (
            "the upsert updated a USD-labelled row with a VND total; the DO UPDATE "
            "branch's WHERE is missing or does not compare the currencies"
        )

    row = await _spend_row(migrate_engine)
    assert row["currency"] == "USD"
    assert row["call_count"] == 1, "the skipped row must not have had its call_count bumped either"


async def test_a_matching_currency_still_updates_the_row(app_sessionmaker, migrate_engine):
    """(2) The negative control for the ``WHERE``.

    An always-false predicate would pass the test above and silently stop every
    ordinary second write to a month. Here the currencies agree, so the row must
    match and the counts must accumulate.
    """
    await _seed_two_currencies(migrate_engine)
    await _write(app_sessionmaker, [_usd_draft()])

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await session.execute(
            UPSERT_WORKSPACE_SPEND,
            {
                "workspace_id": WORKSPACE_A,
                "period_month": MONTH,
                "currency": "USD",
                "total_cost": Decimal("0.0000500000"),
                "call_count": 1,
            },
        )
        assert result.rowcount == 1

    row = await _spend_row(migrate_engine)
    assert row["currency"] == "USD"
    assert row["call_count"] == 2


async def test_a_null_currency_batch_still_accumulates_against_a_labelled_row(
    app_sessionmaker, migrate_engine
):
    """A batch that prices nothing carries no currency and conflicts with none.

    ``call_count`` counts every record including unpriced ones, so this path has
    to keep working — and it is the disjunct most easily lost when the ``WHERE``
    is written as a plain equality.
    """
    await _seed_two_currencies(migrate_engine)
    await _write(app_sessionmaker, [_usd_draft()])

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await session.execute(
            UPSERT_WORKSPACE_SPEND,
            {
                "workspace_id": WORKSPACE_A,
                "period_month": MONTH,
                "currency": None,
                "total_cost": None,
                "call_count": 3,
            },
        )
        assert result.rowcount == 1

    row = await _spend_row(migrate_engine)
    assert row["currency"] == "USD"
    assert row["call_count"] == 4


async def test_the_warn_2_interleave_is_refused_at_the_write_not_at_the_read(
    app_sessionmaker, migrate_engine
):
    """(3a) WARN-2's race, with the interleave pinned by hand.

    The sequence the read-then-write shape cannot survive, executed exactly:

    1. A writer opens its transaction and reads the currency for the month. There
       is no row, so it reads ``None`` — the same answer ``write_records`` gets,
       and the answer that would license it to write anything.
    2. Another transaction commits a USD total for that same month.
    3. The first writer now writes. Its read is stale by one commit.

    Step 3 must not relabel or contaminate the total. The row does not match, the
    update is skipped, and the writer has a zero ``rowcount`` to raise on. Driven
    by hand rather than by two racing tasks because the interleave is the
    assertion — a scheduler that happened to order them differently would make
    the test pass without exercising the case.
    """
    await _seed_two_currencies(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as stale:
        seen = (
            await stale.execute(
                READ_SPEND_CURRENCY, {"workspace_id": WORKSPACE_A, "period_month": MONTH}
            )
        ).scalar_one_or_none()
        assert seen is None, "positive control: the stale reader must see no row"

        # The world moves underneath it: a separate connection commits USD.
        await _write(app_sessionmaker, [_usd_draft()])

        refused = await stale.execute(
            UPSERT_WORKSPACE_SPEND,
            {
                "workspace_id": WORKSPACE_A,
                "period_month": MONTH,
                "currency": "VND",
                "total_cost": Decimal("450"),
                "call_count": 1,
            },
        )

    assert refused.rowcount == 0, (
        "the stale writer's VND total was folded into a USD-labelled row — this is "
        "WARN-2 exactly, and the ON CONFLICT WHERE is what is supposed to stop it"
    )

    row = await _spend_row(migrate_engine)
    assert row["currency"] == "USD"
    assert row["call_count"] == 1


async def test_two_overlapping_writers_end_with_one_committed_and_one_refused(
    app_sessionmaker, migrate_engine
):
    """(3b) Two genuinely overlapping transactions, through the real seam.

    Both call ``write_records`` in their own ``workspace_transaction`` against the
    live engine. Which one wins is the scheduler's business and is deliberately
    not asserted; what is asserted is that the pair cannot end any other way than
    one committed and one refused, and that the refusal names both currencies and
    quotes no figure it made up.

    A refusal may arrive from either half of the defence — the pre-read if the
    other transaction committed first, the upsert's zero ``rowcount`` if it did
    not — and both are correct outcomes. The message shape is the same either
    way, which is why it can be asserted without knowing which fired.
    """
    await _seed_two_currencies(migrate_engine)

    outcomes = await asyncio.gather(
        _write(app_sessionmaker, [_usd_draft()]),
        _write(app_sessionmaker, [_vnd_draft()]),
        return_exceptions=True,
    )

    failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    successes = [outcome for outcome in outcomes if not isinstance(outcome, BaseException)]

    assert len(successes) == 1 and len(failures) == 1, (
        f"exactly one of the two must commit and one must be refused; got {outcomes}"
    )

    failure = failures[0]
    assert isinstance(failure, ValueError), f"refused by {type(failure).__name__}: {failure}"

    message = str(failure)
    assert "USD" in message and "VND" in message, "the refusal must name both currencies"
    assert WORKSPACE_A in message
    assert str(MONTH) in message

    row = await _spend_row(migrate_engine)
    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_RECORDS)).scalar_one() == 1, (
            "the refused batch left call records behind; the raise must roll the "
            "whole transaction back"
        )
        stored_currency = (
            await control.execute(LIST_RECORD_CURRENCIES)
        ).all()[0][1]

    # The label on the total is the currency of the records the total is made of.
    # That equality is the whole invariant, stated once.
    assert row["currency"] == stored_currency
    assert row["call_count"] == 1


@pytest.mark.parametrize("second", ["USD", "VND"])
async def test_a_second_batch_in_the_stored_currency_is_accepted_and_another_is_not(
    app_sessionmaker, migrate_engine, second
):
    """The sequential path, both ways, so neither outcome is an accident.

    The same workspace and month written twice: in the stored currency it
    accumulates, in the other it is refused with a message naming both. This is
    the case the Phase 1 pre-read already handled, kept green so the WARN-2 fix
    is a strengthening rather than a replacement.
    """
    await _seed_two_currencies(migrate_engine)
    await _write(app_sessionmaker, [_usd_draft()])

    if second == "USD":
        await _write(app_sessionmaker, [gateway_draft(call_id="cal_usd_2", created_at=CREATED_AT)])
        row = await _spend_row(migrate_engine)
        assert row["currency"] == "USD"
        assert row["call_count"] == 2
    else:
        with pytest.raises(ValueError) as excinfo:
            await _write(app_sessionmaker, [_vnd_draft()])
        assert "USD" in str(excinfo.value) and "VND" in str(excinfo.value)

        row = await _spend_row(migrate_engine)
        assert row["currency"] == "USD"
        assert row["call_count"] == 1
