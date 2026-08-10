"""``write_records`` end to end: the Phase 1 seam, against a live PostgreSQL 17.

This is the one write path. Phase 2's broker drain calls it once per workspace
group and Phase 3's direct-write fallback calls it with a single record, because
the lock file requires one writer so pricing and ``expires_at`` stamping cannot
drift between them. Everything asserted here is therefore asserted once for
three callers.

Three properties in this file are easy to get subtly wrong and each has its own
test:

- **``expires_at`` comes from the record's own ``created_at``**, never from the
  clock at write time. A backlogged record must not get a shorter life than a
  fresh one; ADR-0040's deletion job reads one indexed column and cannot
  compensate.
- **``call_count`` and ``total_cost`` mean different things.** The first counts
  every written record, including unpriced and not-applicable ones; the second
  sums only priced costs. Conflating them would let unpriced traffic look free —
  the exact reading a spend ceiling must not be given.
- **A batch is all or nothing.** Two workspaces or two currencies in one batch
  are refused before anything is written, not resolved by preferring one.

The last test carries the phase's headline claim, and it carries a positive
control with it. ``tests/conftest.py``'s function-scoped autouse
``truncate_ledger`` empties every ``ledger`` table between tests, so a
table-wide "no zeros" count run after the suite reads an empty table and returns
0 whether the guarantee holds or not (Pitfall 8). The assertion therefore lives
inside a test, next to the row counts that make it mean something.

The draft builders and the fixture calendar are imported from ``tests.unit``
deliberately: one definition of what a draft looks like, so a unit assertion and
an integration assertion cannot quietly disagree about the thing they are both
describing.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from prope.call_ledger.domain import CostStatus, PriceRow, UsageStatus
from prope.call_ledger.pricing import compute_cost
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from tests.unit import (
    INPUT_PRICE,
    OTHER_UPSTREAM_MODEL,
    OUTPUT_PRICE,
    WORKSPACE_A,
    WORKSPACE_B,
    day,
    eval_draft,
    gateway_draft,
    seed_price_row,
)

READ_CALL_RECORD = text(
    """
    SELECT input_tokens, output_tokens, usage_status,
           cost, currency, price_row_id, cost_status, created_at, written_at
    FROM   ledger.call_record
    WHERE  call_id = :call_id
    """
)

READ_CALL_BODY = text(
    """
    SELECT request_body, response_body, byte_size, expires_at, created_at
    FROM   ledger.call_body
    WHERE  call_id = :call_id
    """
)

READ_SPEND = text(
    """
    SELECT period_month, currency, total_cost, call_count
    FROM   ledger.workspace_spend
    WHERE  workspace_id = :workspace_id
    ORDER  BY period_month
    """
)

COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")
COUNT_BODIES = text("SELECT count(*) FROM ledger.call_body")
COUNT_BY_COST_STATUS = text(
    "SELECT count(*) FROM ledger.call_record WHERE cost_status = :cost_status"
)
COUNT_ZEROS = text(
    "SELECT count(*) FROM ledger.call_record "
    "WHERE cost = 0 OR input_tokens = 0 OR output_tokens = 0"
)
COUNT_EVAL_BODIES = text(
    "SELECT count(*) FROM ledger.call_body b "
    "JOIN ledger.call_record r USING (call_id) WHERE r.source = 'eval'"
)
COUNT_EVAL_RECORDS = text("SELECT count(*) FROM ledger.call_record WHERE source = 'eval'")

#: 300 input + 150 output tokens at the fixture prices.
EXPECTED_COST = Decimal("0.0001350000")

#: The same prices as the seeded row, for re-deriving the figure in Python.
PRICE_FOR_CHECK = PriceRow(
    price_row_id="prc_01J0000000000000000000001",
    input_price_per_1k=INPUT_PRICE,
    output_price_per_1k=OUTPUT_PRICE,
    currency="USD",
    effective_from=day(1),
)


async def _write(app_sessionmaker, drafts, *, workspace_id=WORKSPACE_A, **kwargs):
    async with workspace_transaction(app_sessionmaker, workspace_id) as session:
        return await write_records(session, drafts, **kwargs)


async def test_a_priced_call_stores_the_cost_the_currency_and_the_price_row_id(
    app_sessionmaker, migrate_engine
):
    """ADR-0019: "why is this number this number" is answerable years later
    without reconstructing anything, because the row that produced it is named
    on the record."""
    price_row_id = await seed_price_row(migrate_engine, effective_from=day(1))
    draft = gateway_draft(created_at=day(5))

    result = await _write(app_sessionmaker, [draft])

    assert result.priced == 1
    assert result.bodies_written == 1

    async with migrate_engine.begin() as control:
        row = (
            await control.execute(READ_CALL_RECORD, {"call_id": draft.call_id})
        ).mappings().one()

    assert row["cost_status"] == CostStatus.PRICED.value
    assert row["usage_status"] == UsageStatus.REPORTED.value
    assert row["cost"] == EXPECTED_COST
    assert row["cost"] > 0
    assert row["currency"] == "USD"
    assert row["price_row_id"] == price_row_id
    assert row["created_at"] == day(5)
    # written_at is genuinely "when the database saw this" and does default;
    # created_at never does. They are different instants and both are kept.
    assert row["written_at"] > row["created_at"]


async def test_expires_at_is_the_records_own_created_at_plus_the_default_window(
    app_sessionmaker, migrate_engine
):
    """A-040 / A-106, and OQ-B: the window is a parameter, defaulting to 30 days.

    The record is deliberately dated in the past relative to the write, which is
    the shape a broker backlog produces. Its body still expires 30 days after
    the CALL, not 30 days after the write.
    """
    draft = gateway_draft(created_at=day(5))

    await _write(app_sessionmaker, [draft])

    async with migrate_engine.begin() as control:
        body = (
            await control.execute(READ_CALL_BODY, {"call_id": draft.call_id})
        ).mappings().one()

    assert body["expires_at"] == day(5) + timedelta(days=30)
    assert body["created_at"] == day(5)
    assert body["request_body"] == "a request"
    assert body["byte_size"] == 18


async def test_expires_at_honours_a_custom_retention_window(app_sessionmaker, migrate_engine):
    """The window is an argument, not a column read. Phase 2 owns where the
    per-workspace setting will live; nothing outside ``data.owns`` is touched
    to satisfy it here."""
    draft = gateway_draft(created_at=day(5))

    await _write(app_sessionmaker, [draft], retention_window=timedelta(days=7))

    async with migrate_engine.begin() as control:
        body = (
            await control.execute(READ_CALL_BODY, {"call_id": draft.call_id})
        ).mappings().one()

    assert body["expires_at"] == day(12)


async def test_an_eval_draft_writes_no_body_and_still_moves_workspace_spend(
    app_sessionmaker, migrate_engine
):
    """A-055: no ``call_body`` row will ever exist for ``source=eval``. A-098:
    one table, so there is one spend total.

    The no-body property is asserted INSIDE this test, immediately after its own
    write. Deferring it to a query run after the suite would read an empty table
    — ``truncate_ledger`` runs between tests — and return 0 for free.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))

    result = await _write(app_sessionmaker, [eval_draft(created_at=day(5))])

    assert result.priced == 1
    assert result.bodies_written == 0

    async with migrate_engine.begin() as control:
        eval_records = (await control.execute(COUNT_EVAL_RECORDS)).scalar_one()
        eval_bodies = (await control.execute(COUNT_EVAL_BODIES)).scalar_one()
        spend = (await control.execute(READ_SPEND, {"workspace_id": WORKSPACE_A})).mappings().all()

    assert eval_records > 0, (
        "positive control: with no eval record written, the body count below is 0 for free"
    )
    assert eval_bodies == 0

    assert len(spend) == 1
    assert spend[0]["call_count"] == 1
    assert spend[0]["total_cost"] > 0


async def test_an_eval_draft_carrying_a_body_is_refused(app_sessionmaker):
    """The absence in the test above is a rule, not an accident of the fixture."""
    with pytest.raises(ValueError, match="eval"):
        await _write(app_sessionmaker, [eval_draft(body=gateway_draft().body)])


async def test_call_count_counts_every_record_and_total_cost_only_the_priced_ones(
    app_sessionmaker, migrate_engine
):
    """A-103, and the sub-decision this plan records rather than implies.

    ``call_count`` answers "how much traffic"; ``total_cost`` answers "how much
    money". A batch of three where only one is priced must show 3 and one cost —
    if ``call_count`` counted only priced records, unpriced traffic would look
    like no traffic, and a spend ceiling would be read against a number that
    hides the calls it cannot price.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))

    drafts = [
        gateway_draft(call_id="cal_01J0000000000000000000A1", created_at=day(5)),
        gateway_draft(
            call_id="cal_01J0000000000000000000A2",
            created_at=day(5),
            upstream_model=OTHER_UPSTREAM_MODEL,
        ),
        gateway_draft(
            call_id="cal_01J0000000000000000000A3",
            created_at=day(5),
            input_tokens=None,
            output_tokens=None,
        ),
    ]

    result = await _write(app_sessionmaker, drafts)

    assert (result.priced, result.unpriced, result.unknown) == (1, 1, 1)

    async with migrate_engine.begin() as control:
        spend = (await control.execute(READ_SPEND, {"workspace_id": WORKSPACE_A})).mappings().all()

    assert len(spend) == 1
    assert spend[0]["call_count"] == 3, "unpriced and unknown traffic must still be traffic"
    assert spend[0]["total_cost"] == EXPECTED_COST
    assert spend[0]["currency"] == "USD"


async def test_a_second_month_creates_a_second_spend_row(app_sessionmaker, migrate_engine):
    """``period_month`` comes from each record's own ``created_at`` in UTC.

    One batch, two months: the aggregate follows the calls, not the write. A
    drain catching up across a month boundary must not put September's calls in
    August's bucket.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))

    drafts = [
        gateway_draft(call_id="cal_01J0000000000000000000M1", created_at=day(5)),
        gateway_draft(call_id="cal_01J0000000000000000000M2", created_at=day(20)),
        # 2026-09-04 — the next month.
        gateway_draft(call_id="cal_01J0000000000000000000M3", created_at=day(35)),
    ]

    await _write(app_sessionmaker, drafts)

    async with migrate_engine.begin() as control:
        spend = (await control.execute(READ_SPEND, {"workspace_id": WORKSPACE_A})).mappings().all()

    assert [row["period_month"] for row in spend] == [date(2026, 8, 1), date(2026, 9, 1)]
    assert [row["call_count"] for row in spend] == [2, 1]
    assert spend[0]["total_cost"] == EXPECTED_COST * 2
    assert spend[1]["total_cost"] == EXPECTED_COST


async def test_a_second_batch_accumulates_onto_the_same_month_row(
    app_sessionmaker, migrate_engine
):
    """The upsert adds; it does not replace. Two drain batches in one month are
    two batches of traffic, not the second one's."""
    await seed_price_row(migrate_engine, effective_from=day(1))

    await _write(app_sessionmaker, [gateway_draft(call_id="cal_01J000000000000000000B1")])
    await _write(app_sessionmaker, [gateway_draft(call_id="cal_01J000000000000000000B2")])

    async with migrate_engine.begin() as control:
        spend = (await control.execute(READ_SPEND, {"workspace_id": WORKSPACE_A})).mappings().all()

    assert len(spend) == 1
    assert spend[0]["call_count"] == 2
    assert spend[0]["total_cost"] == EXPECTED_COST * 2


async def test_a_batch_mixing_two_currencies_raises_rather_than_summing(
    app_sessionmaker, migrate_engine
):
    """A-107: a workspace uses one currency and there is no conversion.

    Summing across currencies would produce a number with no unit — and
    ``ck_workspace_spend_total_cost_carries_currency`` exists because a total
    with no currency is a number nobody can act on.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    await seed_price_row(
        migrate_engine,
        price_row_id="prc_01J000000000000000000VND",
        upstream_model=OTHER_UPSTREAM_MODEL,
        input_price_per_1k=Decimal("1000"),
        output_price_per_1k=Decimal("3000"),
        currency="VND",
        effective_from=day(1),
    )

    drafts = [
        gateway_draft(call_id="cal_01J0000000000000000000C1"),
        gateway_draft(call_id="cal_01J0000000000000000000C2", upstream_model=OTHER_UPSTREAM_MODEL),
    ]

    with pytest.raises(ValueError, match="currenc"):
        await _write(app_sessionmaker, drafts)

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_RECORDS)).scalar_one() == 0, (
            "the batch was partly written before the mismatch was noticed"
        )


async def test_a_batch_mixing_two_workspaces_is_rejected_before_anything_is_written(
    app_sessionmaker, migrate_engine
):
    """ADR-0040: one workspace per transaction, and the session already carries
    it. A second ``workspace_id`` in the batch is a mis-stamped record; the
    policy's ``WITH CHECK`` would refuse it at the engine as the second line,
    but a partly-written batch is not an acceptable way to find out.
    """
    drafts = [
        gateway_draft(call_id="cal_01J0000000000000000000D1"),
        gateway_draft(call_id="cal_01J0000000000000000000D2", workspace_id=WORKSPACE_B),
    ]

    with pytest.raises(ValueError, match="workspace"):
        await _write(app_sessionmaker, drafts)

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_RECORDS)).scalar_one() == 0


async def test_write_records_returns_counts_that_match_what_landed(
    app_sessionmaker, migrate_engine
):
    """The returned ``WriteResult`` is checked against the database, not trusted.

    A counter incremented on the branch that *meant* to write is a counter that
    agrees with the code rather than with the table.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))

    drafts = [
        gateway_draft(call_id="cal_01J0000000000000000000R1"),
        gateway_draft(call_id="cal_01J0000000000000000000R2", upstream_model=OTHER_UPSTREAM_MODEL),
        gateway_draft(
            call_id="cal_01J0000000000000000000R3", input_tokens=None, output_tokens=None
        ),
        eval_draft(call_id="cal_01J0000000000000000000R4"),
    ]

    result = await _write(app_sessionmaker, drafts)

    async with migrate_engine.begin() as control:
        priced = (
            await control.execute(COUNT_BY_COST_STATUS, {"cost_status": "priced"})
        ).scalar_one()
        unpriced = (
            await control.execute(COUNT_BY_COST_STATUS, {"cost_status": "unpriced"})
        ).scalar_one()
        not_applicable = (
            await control.execute(COUNT_BY_COST_STATUS, {"cost_status": "not_applicable"})
        ).scalar_one()
        bodies = (await control.execute(COUNT_BODIES)).scalar_one()
        total = (await control.execute(COUNT_RECORDS)).scalar_one()

    assert (result.priced, result.unpriced, result.unknown) == (priced, unpriced, not_applicable)
    assert result.bodies_written == bodies == 3  # the eval draft carries none
    assert result.total == total == 4


async def test_no_zero_anywhere_in_a_mixed_batch_of_all_three_cost_states(
    app_sessionmaker, migrate_engine
):
    """The phase's headline claim, with the positive control that makes it mean
    something.

    A mixed batch is written through ``write_records``: one priced, one unpriced
    (no price row for its model), one unknown-usage. Then, as ``prope_migrate``
    and inside this test, four things are asserted together — the table holds
    rows, each of the three cost states is actually present, and no row has a
    zero cost or a zero token count.

    Without the first three assertions the fourth passes against the empty table
    ``truncate_ledger`` leaves behind between tests. That is Pitfall 8, and it
    is why this assertion is a test rather than a query someone runs afterwards.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))

    drafts = [
        gateway_draft(call_id="cal_01J0000000000000000000Z1", created_at=day(5)),
        gateway_draft(
            call_id="cal_01J0000000000000000000Z2",
            created_at=day(5),
            upstream_model=OTHER_UPSTREAM_MODEL,
        ),
        gateway_draft(
            call_id="cal_01J0000000000000000000Z3",
            created_at=day(5),
            input_tokens=None,
            output_tokens=None,
        ),
    ]

    result = await _write(app_sessionmaker, drafts)
    assert (result.priced, result.unpriced, result.unknown) == (1, 1, 1)

    async with migrate_engine.begin() as control:
        total = (await control.execute(COUNT_RECORDS)).scalar_one()
        priced = (
            await control.execute(COUNT_BY_COST_STATUS, {"cost_status": "priced"})
        ).scalar_one()
        unpriced = (
            await control.execute(COUNT_BY_COST_STATUS, {"cost_status": "unpriced"})
        ).scalar_one()
        not_applicable = (
            await control.execute(COUNT_BY_COST_STATUS, {"cost_status": "not_applicable"})
        ).scalar_one()
        zeros = (await control.execute(COUNT_ZEROS)).scalar_one()
        stored_cost = (
            await control.execute(
                READ_CALL_RECORD, {"call_id": "cal_01J0000000000000000000Z1"}
            )
        ).mappings().one()["cost"]

    # The positive controls. Each one is what stops the last assertion from
    # being satisfied by an absence.
    assert total > 0
    assert priced >= 1
    assert unpriced >= 1
    assert not_applicable >= 1

    assert zeros == 0, (
        "a row records a zero cost or a zero token count — an absence became a "
        "number a reviewer would act on"
    )

    # And the priced row holds the sub-cent figure that a currency's minor units
    # would have rounded to 0.00 — the one zero the CHECK could not have caught,
    # because the writer would never have offered it.
    assert stored_cost == EXPECTED_COST == compute_cost(300, 150, PRICE_FOR_CHECK)
    assert stored_cost < Decimal("0.01")
