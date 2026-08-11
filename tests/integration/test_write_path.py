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

Phase 3 adds a fourth, and it is the one CL-02 is about: **the monthly aggregate
is built from the rows the insert RETURNED, never from the rows offered.**
``ledger.call_record``'s primary key is ``call_id`` alone, so a duplicate row was
always impossible; what a redelivery corrupts is ``ledger.workspace_spend``. The
tests below therefore assert the *unchanged total* and never only the row count —
"the record appears once" is satisfied by a writer with no idempotency in it at
all. Every one of them also asserts ``duplicate_call_id_total`` moved, because a
writer that silently did nothing passes every other assertion in the file.

The last test carries the phase's headline claim, and it carries a positive
control with it. ``tests/conftest.py``'s function-scoped autouse
``truncate_owned_tables`` empties every owned table between tests, so a
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
from prometheus_client import REGISTRY
from sqlalchemy import text

from prope.call_ledger.domain import CostStatus, PriceRow, UsageStatus
from prope.call_ledger.pricing import compute_cost
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from tests.unit import (
    INPUT_PRICE,
    OTHER_UPSTREAM_MODEL,
    OUTPUT_PRICE,
    PROVIDER_CONFIG,
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


def _counter(name: str, labels: dict[str, str] | None = None) -> float:
    """One metric's current value, or ``0.0`` if nothing has touched it.

    **Read as a DELTA at every call site, never as an absolute.**
    ``prometheus_client``'s default ``REGISTRY`` is process-global and the suite
    shares one process, so an absolute assertion passes alone and fails after its
    neighbour. Same shape and same reason as
    ``tests/broker/_helpers.py::counter_value``; defined locally rather than
    imported so an integration module that touches no broker does not import the
    broker package, which is the precedent
    ``test_ceiling_refuses_evals_only.py`` already set.
    """
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


def _duplicates_counter() -> float:
    return _counter("prope_call_ledger_duplicate_call_id_total")


async def _spend_rows(migrate_engine, workspace_id=WORKSPACE_A):
    """``ledger.workspace_spend`` read as the OWNER — never through the writer."""
    async with migrate_engine.begin() as control:
        return (await control.execute(READ_SPEND, {"workspace_id": workspace_id})).mappings().all()


async def _row_count(migrate_engine) -> int:
    async with migrate_engine.begin() as control:
        return (await control.execute(COUNT_RECORDS)).scalar_one()


def _five_priced_drafts() -> list:
    """Five distinct, cost-bearing gateway calls in one month.

    Five and not one, deliberately: ``sort_by_parameter_order`` would make
    SQLAlchemy select ``call_id`` as a client-side sentinel and raise on the first
    conflicting row, and a redelivery test written with a single record is exactly
    the one that would not notice (RESEARCH Pitfall 1).
    """
    return [
        gateway_draft(call_id=f"cal_01J00000000000000000IDP{index}", created_at=day(5))
        for index in range(5)
    ]


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
    — ``truncate_owned_tables`` runs between tests — and return 0 for free.
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

    duplicates_before = _duplicates_counter()
    result = await _write(app_sessionmaker, drafts)

    assert result.duplicates == 0, "nothing in this batch was already present"
    assert _duplicates_counter() == duplicates_before

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
    ``truncate_owned_tables`` leaves behind between tests. That is Pitfall 8, and it
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


# ---------------------------------------------------------------------------
# CL-02: the aggregate is built from the rows the insert RETURNED
# ---------------------------------------------------------------------------


async def test_rewriting_the_same_batch_leaves_the_workspace_total_exactly_where_it_was(
    app_sessionmaker, migrate_engine
):
    """CL-02's claim, asserted on the aggregate rather than on the row count.

    Three assertions have to appear together, because any two of them pass
    against a writer that did nothing at all: the row count is unchanged, the
    ``workspace_spend`` figures are unchanged, **and**
    ``duplicate_call_id_total`` moved by exactly five — which is what says the
    second write actually reached the statement.

    Everything is read back through ``migrate_engine``: the owner role, subject
    to no policy, never the code under test.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    drafts = _five_priced_drafts()

    first = await _write(app_sessionmaker, drafts)
    assert (first.priced, first.duplicates) == (5, 0)

    before = await _spend_rows(migrate_engine)
    assert len(before) == 1
    assert before[0]["call_count"] == 5
    assert before[0]["total_cost"] == EXPECTED_COST * 5

    duplicates_before = _duplicates_counter()

    # The same five again. This is what a redelivery after an unacknowledged
    # consumer restart produces, and the writer cannot tell the difference.
    second = await _write(app_sessionmaker, drafts)

    assert second.duplicates == 5
    assert second.priced == 5, "every offered record was still priced and counted"
    assert second.bodies_written == 0, "no body follows a record that was already there"
    assert _duplicates_counter() == duplicates_before + 5

    assert await _row_count(migrate_engine) == 5
    after = await _spend_rows(migrate_engine)
    assert len(after) == 1
    assert after[0]["call_count"] == before[0]["call_count"]
    assert after[0]["total_cost"] == before[0]["total_cost"]
    assert after[0]["currency"] == before[0]["currency"]


async def test_a_batch_of_five_duplicates_and_two_new_records_adds_exactly_two(
    app_sessionmaker, migrate_engine
):
    """The regression test RESEARCH Pitfall 1 asks for, named for the trap.

    Five, then the same five plus two new ones. ``call_count`` must move by
    exactly two — which is simultaneously CL-02's partial-duplicate case and the
    assertion that fails loudly if anybody ever passes
    ``sort_by_parameter_order`` to the upsert's ``returning()``. With that flag
    SQLAlchemy makes ``call_id`` a client-side sentinel and raises
    ``InvalidRequestError`` on the first conflicting row, so this would not
    merely fail — it would fail with an exception out of the write path whose
    whole job is to survive a redelivery.

    A test that passes with one record and fails with five is the shape this
    guards against, which is why the batch is five and not one.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    drafts = _five_priced_drafts()

    await _write(app_sessionmaker, drafts)

    newcomers = [
        gateway_draft(call_id=f"cal_01J00000000000000000NEW{index}", created_at=day(5))
        for index in range(2)
    ]
    duplicates_before = _duplicates_counter()

    result = await _write(app_sessionmaker, [*drafts, *newcomers])

    assert result.duplicates == 5
    assert _duplicates_counter() == duplicates_before + 5

    assert await _row_count(migrate_engine) == 7
    spend = await _spend_rows(migrate_engine)
    assert len(spend) == 1
    assert spend[0]["call_count"] == 7, "exactly the two new records, and not the five duplicates"
    assert spend[0]["total_cost"] == EXPECTED_COST * 7


async def test_a_body_arriving_for_an_already_written_record_is_not_stored(
    app_sessionmaker, migrate_engine
):
    """D-34, and the case ADR-0041 creates on purpose.

    A confirm that **timed out** rather than being refused means the broker did
    get the message; the direct-write fallback wrote the record without its body
    (D-28), and the broker later delivers the same record *with* its body.
    Letting that body land would recover real data — and would break AC-1's
    stated equality, "body_dropped_total equals the number missing from
    call_body", because the drop was already counted.

    The second batch carries a fresh record with a body as its positive control:
    without it, "no body row appeared" would also be true of a writer that had
    stopped writing bodies entirely.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    already_written = gateway_draft(call_id="cal_01J0000000000000000000E1", body=None)

    first = await _write(app_sessionmaker, [already_written])
    assert first.bodies_written == 0

    redelivered_with_its_body = gateway_draft(call_id="cal_01J0000000000000000000E1")
    newcomer = gateway_draft(call_id="cal_01J0000000000000000000E2")

    result = await _write(app_sessionmaker, [redelivered_with_its_body, newcomer])

    assert result.duplicates == 1
    assert result.bodies_written == 1, "the newcomer's body, and only the newcomer's"

    async with migrate_engine.begin() as control:
        bodies = (await control.execute(COUNT_BODIES)).scalar_one()
        orphan = (
            await control.execute(READ_CALL_BODY, {"call_id": "cal_01J0000000000000000000E1"})
        ).mappings().all()
        control_row = (
            await control.execute(READ_CALL_BODY, {"call_id": "cal_01J0000000000000000000E2"})
        ).mappings().all()

    assert bodies == 1
    assert orphan == [], "a body was recovered for a record whose drop was already counted"
    assert len(control_row) == 1, (
        "positive control: with no body written at all the assertion above is free"
    )


async def test_mixing_currencies_is_refused_even_when_the_second_currency_is_a_duplicate(
    app_sessionmaker, migrate_engine
):
    """RESEARCH Pitfall 2: the refusal stayed in pass 1, over the whole batch.

    If the mixed-currency check had moved into pass 2 with the month buckets, a
    batch whose second-currency records are all duplicates would be silently
    **accepted** — a property that changed with no test going red, because the
    existing mixed-currency test offers two fresh records.
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

    in_vnd = gateway_draft(
        call_id="cal_01J0000000000000000000F2", upstream_model=OTHER_UPSTREAM_MODEL
    )
    await _write(app_sessionmaker, [in_vnd])
    assert await _row_count(migrate_engine) == 1

    in_usd = gateway_draft(call_id="cal_01J0000000000000000000F1")

    with pytest.raises(ValueError, match="currenc") as refusal:
        await _write(app_sessionmaker, [in_usd, in_vnd])

    assert "USD" in str(refusal.value)
    assert "VND" in str(refusal.value)
    assert await _row_count(migrate_engine) == 1, "the USD record was written before the refusal"


async def test_two_currencies_in_two_different_months_are_still_accepted(
    app_sessionmaker, migrate_engine
):
    """The pre-split behaviour, asserted so the split cannot tighten it unnoticed.

    The refusal is keyed on ``period_month(created_at)`` and consults only
    records that carry a cost — it always was. A batch-wide
    ``{r.currency for r in records}`` set would be the natural way to write the
    pass-1 check, and it would silently turn this batch into a refusal.
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
        gateway_draft(call_id="cal_01J0000000000000000000G1", created_at=day(5)),
        # 2026-09-04 — the next month, and the other currency.
        gateway_draft(
            call_id="cal_01J0000000000000000000G2",
            created_at=day(35),
            upstream_model=OTHER_UPSTREAM_MODEL,
        ),
    ]

    result = await _write(app_sessionmaker, drafts)

    assert result.priced == 2
    assert await _row_count(migrate_engine) == 2

    spend = await _spend_rows(migrate_engine)
    assert [row["period_month"] for row in spend] == [date(2026, 8, 1), date(2026, 9, 1)]
    assert [row["currency"] for row in spend] == ["USD", "VND"]


async def test_a_gateway_record_with_no_version_id_is_refused_by_name(
    app_sessionmaker, migrate_engine
):
    """D-40: the counter whose whole job is to be zero gets a way to move.

    Before this, such a record died as an ``IntegrityError`` under
    ``ck_call_record_gateway_calls_carry_version_id`` and dead-lettered under a
    CONSTRAINT's name rather than under this counter's — so the counter could
    never move, and a control that can never move is not a control.
    """
    before = _counter("prope_call_ledger_missing_version_id_total")

    with pytest.raises(ValueError, match="version_id") as refusal:
        await _write(
            app_sessionmaker,
            [gateway_draft(call_id="cal_01J0000000000000000000H1", version_id=None)],
        )

    assert "ck_call_record_gateway_calls_carry_version_id" in str(refusal.value)
    assert _counter("prope_call_ledger_missing_version_id_total") == before + 1
    assert await _row_count(migrate_engine) == 0


async def test_unpriced_and_unknown_usage_are_counted_for_every_record_offered(
    app_sessionmaker, migrate_engine
):
    """The two counters describe what the CALLER sent, not what the table gained.

    Only the spend aggregate is built from the inserted set, because only the
    spend aggregate is money. A redelivered unpriced record is still an unpriced
    record whose price row nobody has fixed, so the second write moves both
    counters again while ``workspace_spend`` does not move at all.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))

    unpriced_labels = {
        "provider_config_id": PROVIDER_CONFIG,
        "upstream_model": OTHER_UPSTREAM_MODEL,
    }
    unknown_labels = {"source": "gateway"}
    drafts = [
        gateway_draft(
            call_id="cal_01J0000000000000000000J1", upstream_model=OTHER_UPSTREAM_MODEL
        ),
        gateway_draft(
            call_id="cal_01J0000000000000000000J2", input_tokens=None, output_tokens=None
        ),
    ]

    unpriced_before = _counter("prope_call_ledger_unpriced_total", unpriced_labels)
    unknown_before = _counter("prope_call_ledger_unknown_usage_total", unknown_labels)

    first = await _write(app_sessionmaker, drafts)
    assert (first.unpriced, first.unknown) == (1, 1)
    assert _counter("prope_call_ledger_unpriced_total", unpriced_labels) == unpriced_before + 1
    assert _counter("prope_call_ledger_unknown_usage_total", unknown_labels) == unknown_before + 1

    spend_before = await _spend_rows(migrate_engine)

    second = await _write(app_sessionmaker, drafts)

    assert second.duplicates == 2
    assert (second.unpriced, second.unknown) == (1, 1)
    assert _counter("prope_call_ledger_unpriced_total", unpriced_labels) == unpriced_before + 2
    assert _counter("prope_call_ledger_unknown_usage_total", unknown_labels) == unknown_before + 2
    assert await _spend_rows(migrate_engine) == spend_before, (
        "a redelivery moved the aggregate that the two counters above are allowed to move"
    )


async def test_an_unknown_usage_record_stores_null_tokens_through_the_core_upsert(
    app_sessionmaker, migrate_engine
):
    """CL-11 clause 1, re-asserted through the Core upsert rather than the text().

    ``unknown`` tokens are NULL and never zero (BR-07, A-101, ADR-0019). Phase 1
    asserted it against ``INSERT_CALL_RECORD``; the statement that writes every
    call record in the system is now a different construct, and a column omitted
    from a Core insert falls to its column default rather than to the value the
    writer intended. ``is None`` and not ``== 0``, because those are exactly the
    two answers that must never be confused.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    draft = gateway_draft(
        call_id="cal_01J0000000000000000000K1",
        created_at=day(5),
        input_tokens=None,
        output_tokens=None,
    )

    result = await _write(app_sessionmaker, [draft])
    assert result.unknown == 1

    async with migrate_engine.begin() as control:
        row = (
            await control.execute(READ_CALL_RECORD, {"call_id": draft.call_id})
        ).mappings().one()

    assert row["usage_status"] == UsageStatus.UNKNOWN.value
    assert row["cost_status"] == CostStatus.NOT_APPLICABLE.value
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None
    assert row["cost"] is None
    # ``written_at`` still defaults at the engine: the Core construct omits the
    # column entirely, which is what lets the DDL default keep meaning "when the
    # database saw this".
    assert row["written_at"] > row["created_at"]
