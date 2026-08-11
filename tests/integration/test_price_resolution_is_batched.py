"""D-280: the price read is per BATCH, and effective dating is still per RECORD.

Two claims, one file, because they are the two halves of one change and each is
the other's guard.

**The first claim is counted, never timed.** ``performance_requirements``' *"writer
drain throughput >= 500 records/sec sustained"* went red in plan 03-06 and the
cause was localised precisely: ``write_records`` issued one ``resolve_price``
round trip per draft whose ``usage_status`` was ``reported``, at 1.42 ms each,
which was roughly seventy percent of the cost of writing a priced 500-record
window. A timing assertion would re-measure the developer host every morning and
would go red for reasons that have nothing to do with the code. The property
actually being claimed is *"the number of round trips is a function of the
batch's distinct keys and not of its length"*, and that is countable exactly:
these tests attach a ``before_cursor_execute`` listener to the engine and count
the statements that name ``ledger.price_table``.

**The second claim is what stops the first from being satisfied by cheating.**
The obvious wrong fix — and it is obvious, which is why it is asserted against
rather than merely warned about — is to resolve one price for the whole batch, or
to memoise on the resolved ``created_at`` instant. Both would report exactly the
same round-trip count as the real fix. Both would also be wrong the moment one
batch contains records from either side of a price change, which is what
``test_records_either_side_of_a_price_change_get_different_prices`` writes in a
single batch and reads back through the owner role. ADR-0019's rule is unchanged:
a call is priced at the row in force **at the call's own timestamp**, and a price
row added later never moves it.

**Why the statements are counted at the engine rather than asserted from a
return value.** ``write_records`` reports what it wrote, not how it found out.
The only honest place to see round trips is where they are issued, and the only
way to be sure the listener is looking at the right engine is to require it to
have seen something — every test below asserts the total recorded count is
non-zero, because a listener attached to the wrong engine reports zero
``price_table`` statements and passes.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.call_ledger.domain import CostStatus, PriceRow
from prope.call_ledger.pricing import compute_cost, resolve_price
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from tests.unit import (
    INPUT_PRICE,
    OTHER_PROVIDER_CONFIG,
    OTHER_UPSTREAM_MODEL,
    OUTPUT_PRICE,
    PROVIDER_CONFIG,
    UPSTREAM_MODEL,
    WORKSPACE_A,
    day,
    gateway_draft,
    seed_price_row,
)

#: The four ``(provider_config_id, upstream_model)`` pairs the fixtures can
#: build, which is what ``M`` ranges over below. Two provider configs times two
#: model names: a model name means nothing without the config it was priced
#: under, which is why the key is the pair and never either half.
KEYS = [
    (PROVIDER_CONFIG, UPSTREAM_MODEL),
    (PROVIDER_CONFIG, OTHER_UPSTREAM_MODEL),
    (OTHER_PROVIDER_CONFIG, UPSTREAM_MODEL),
    (OTHER_PROVIDER_CONFIG, OTHER_UPSTREAM_MODEL),
]

#: Deliberately larger than a drain window is wide in records-per-key terms and
#: comfortably larger than ``M``: if the round-trip count were a function of the
#: batch length, two hundred would make it unmistakable against one.
BATCH = 200
SMALL_BATCH = 20

#: The price rows the effective-dating test straddles. The second is priced at
#: ten times the first so the two records' COSTS differ as well as their
#: ``price_row_id``s — a resolution that returned the wrong row but the right
#: price would otherwise pass half of the assertion.
LATER_INPUT_PRICE = INPUT_PRICE * 10
LATER_OUTPUT_PRICE = OUTPUT_PRICE * 10

READ_PRICING = text(
    """
    SELECT call_id, cost, cost_status, price_row_id, provider_config_id, upstream_model
    FROM   ledger.call_record
    WHERE  workspace_id = :ws
    """
)


@contextmanager
def statements_recorded(engine: AsyncEngine) -> Iterator[list[str]]:
    """Every statement the engine executes while the block runs, in order.

    Attached to ``engine.sync_engine`` because that is where SQLAlchemy's DBAPI
    events live — the async engine is a facade over it, and a listener on the
    facade would never fire.

    Removed in a ``finally``: the engine is a **session-scoped** fixture, so a
    listener left attached would keep recording into a dead list for every test
    that follows and would slow the whole suite down for no reason.
    """
    recorded: list[str] = []

    def record(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        recorded.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield recorded
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


def price_statements(recorded: list[str]) -> list[str]:
    """The recorded statements that read ``ledger.price_table``."""
    return [statement for statement in recorded if "ledger.price_table" in statement]


def _price(
    price_row_id: str, input_price: Decimal, output_price: Decimal, effective_from
) -> PriceRow:
    """A ``PriceRow`` for ``compute_cost``, so the expected cost is not written by hand."""
    return PriceRow(
        price_row_id=price_row_id,
        input_price_per_1k=input_price,
        output_price_per_1k=output_price,
        currency="USD",
        effective_from=effective_from,
    )


async def seed_a_price_row_for_every_key(migrate_engine: AsyncEngine) -> dict[tuple, str]:
    """One price row per key, effective from day 1. Returns key -> price_row_id."""
    seeded: dict[tuple, str] = {}
    for index, (provider_config_id, upstream_model) in enumerate(KEYS):
        price_row_id = f"prc_key{index:023d}"
        await seed_price_row(
            migrate_engine,
            price_row_id=price_row_id,
            provider_config_id=provider_config_id,
            upstream_model=upstream_model,
            effective_from=day(1),
        )
        seeded[(provider_config_id, upstream_model)] = price_row_id
    return seeded


def batch_over_keys(size: int, distinct_keys: int, *, prefix: str) -> list:
    """``size`` priced gateway drafts spread round-robin over ``distinct_keys`` keys."""
    drafts = []
    for index in range(size):
        provider_config_id, upstream_model = KEYS[index % distinct_keys]
        drafts.append(
            gateway_draft(
                call_id=f"cal_{prefix}{index:021d}",
                provider_config_id=provider_config_id,
                upstream_model=upstream_model,
            )
        )
    return drafts


async def write_and_count(
    app_engine: AsyncEngine,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    drafts: list,
) -> int:
    """Write one batch and return how many statements read ``ledger.price_table``.

    The positive control lives here rather than at each call site: a listener
    attached to the wrong engine records nothing at all, which would make every
    "zero price statements" assertion below pass for the wrong reason.
    """
    with statements_recorded(app_engine) as recorded:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await write_records(session, drafts)

    assert recorded, (
        "the listener recorded no statements at all, so it is not attached to the engine "
        "write_records ran on and a price-statement count of zero would mean nothing"
    )
    return len(price_statements(recorded))


async def test_the_recorder_counts_one_statement_per_round_trip(
    app_engine, app_sessionmaker, migrate_engine
):
    """Calibrate the instrument before believing what it says.

    Every count below is an assertion that a number is SMALL, and a broken
    counter produces small numbers for free. This test issues the shape the
    writer used to issue — ``SMALL_BATCH`` sequential ``resolve_price`` calls,
    which is exactly the N+1 plan 03-06 measured — and requires the recorder to
    report ``SMALL_BATCH`` price statements. So the recorder demonstrably counts
    one per round trip, and *"one statement for two hundred records"* is a fact
    about the writer rather than about the listener.

    It is also the last executable record of the old behaviour: if a future
    change re-introduces a per-record lookup, this test still passes and the
    three below go red, which is the direction the failure should point.
    """
    await seed_a_price_row_for_every_key(migrate_engine)

    with statements_recorded(app_engine) as recorded:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            for _ in range(SMALL_BATCH):
                await resolve_price(
                    session,
                    workspace_id=WORKSPACE_A,
                    provider_config_id=PROVIDER_CONFIG,
                    upstream_model=UPSTREAM_MODEL,
                    at=day(5),
                )

    assert len(price_statements(recorded)) == SMALL_BATCH, (
        f"{SMALL_BATCH} sequential resolve_price calls were recorded as "
        f"{len(price_statements(recorded))} price statements; the recorder does not count one "
        "per round trip, so no count in this file means anything"
    )


async def test_one_statement_serves_a_whole_batch_whatever_its_length(
    app_engine, app_sessionmaker, migrate_engine
):
    """The claim, as three counts that must be equal to each other and to one.

    Two hundred records over one key, two hundred over four, and twenty over
    four. If the count were a function of the batch length the first two would
    read 200 and the third 20; if it were a function of the distinct keys it
    would read 1, 4 and 4. It reads 1, 1 and 1, because ``PRICE_ROWS_FOR_KEYS``
    joins against an ``unnest`` of the keys and so does M index lookups inside
    one round trip.
    """
    await seed_a_price_row_for_every_key(migrate_engine)

    wide = await write_and_count(
        app_engine, app_sessionmaker, batch_over_keys(BATCH, 1, prefix="onekey")
    )
    spread = await write_and_count(
        app_engine, app_sessionmaker, batch_over_keys(BATCH, len(KEYS), prefix="fourky")
    )
    small = await write_and_count(
        app_engine, app_sessionmaker, batch_over_keys(SMALL_BATCH, len(KEYS), prefix="twenty")
    )

    assert wide == 1, f"{BATCH} records over one key issued {wide} price statements"
    assert spread == 1, f"{BATCH} records over {len(KEYS)} keys issued {spread} price statements"
    assert small == wide == spread, (
        f"the price-statement count moved with the batch: {BATCH}/1 key -> {wide}, "
        f"{BATCH}/{len(KEYS)} keys -> {spread}, {SMALL_BATCH}/{len(KEYS)} keys -> {small}. "
        "It must be a function of the distinct keys and not of the number of records"
    )


async def test_every_record_in_the_spread_batch_is_priced_from_its_own_key(
    app_engine, app_sessionmaker, migrate_engine
):
    """One round trip is worth nothing if it priced the wrong records.

    Read back through ``migrate_engine`` — the owner role, subject to no policy —
    and require every one of the two hundred rows to carry the ``price_row_id``
    of the row seeded for **its own** key. A book that resolved every record
    against the first key it saw would produce exactly one price statement and
    would fail here.
    """
    seeded = await seed_a_price_row_for_every_key(migrate_engine)
    drafts = batch_over_keys(BATCH, len(KEYS), prefix="checks")

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await write_records(session, drafts)

    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(READ_PRICING, {"ws": WORKSPACE_A})).mappings().all()

    assert len(rows) == BATCH
    for row in rows:
        key = (row["provider_config_id"], row["upstream_model"])
        assert row["cost_status"] == str(CostStatus.PRICED)
        assert row["price_row_id"] == seeded[key], (
            f"{row['call_id']} is keyed on {key} and was priced from {row['price_row_id']} "
            f"rather than {seeded[key]}"
        )


async def test_a_batch_with_no_reported_usage_never_reads_the_price_table(
    app_engine, app_sessionmaker, migrate_engine
):
    """Zero, not one. A batch with nothing to price must ask nothing.

    ``usage_status = unknown`` means the provider returned no usage object, so
    there is nothing to multiply by a price and never a zero cost standing in for
    one. That branch cost no round trip before D-280 and must cost none after —
    it is what makes the load run's five thousand seeded bodies cheap.
    """
    await seed_a_price_row_for_every_key(migrate_engine)
    drafts = [
        gateway_draft(call_id=f"cal_unknwn{index:020d}", input_tokens=None, output_tokens=None)
        for index in range(SMALL_BATCH)
    ]

    assert await write_and_count(app_engine, app_sessionmaker, drafts) == 0


async def test_a_single_record_batch_still_costs_exactly_one_price_statement(
    app_engine, app_sessionmaker, migrate_engine
):
    """03-01's direct-write fallback, defended by name.

    ``build_fallback_writer`` calls ``write_records`` with a list of ONE, and it
    is the path that runs when the broker is already down — the worst possible
    moment for the write path to have become more expensive. Before D-280 that
    record cost one ``resolve_price`` round trip; it must still cost one, and not
    two.
    """
    await seed_a_price_row_for_every_key(migrate_engine)
    one = [gateway_draft(call_id="cal_single0000000000000000000")]

    assert await write_and_count(app_engine, app_sessionmaker, one) == 1


async def test_records_either_side_of_a_price_change_get_different_prices(
    app_engine, app_sessionmaker, migrate_engine
):
    """ADR-0019 inside ONE batch: three records, one key, two prices.

    This is the assertion that a whole-batch shortcut cannot survive. The three
    records share a key and a transaction and differ only in ``created_at``:

    - day 5 falls in the day-1 row's interval,
    - day 10 falls exactly on the day-10 row's ``effective_from``, and the
      interval is half-open ``[effective_from, next effective_from)``, so it
      belongs to the NEW row,
    - day 12 falls after it.

    One price cannot serve all three, so a resolution that memoised on anything
    batch-wide — the first record's instant, the last one's, or a single
    ``resolve_price`` hoisted out of the loop — fails here whatever its
    round-trip count says.
    """
    await seed_price_row(
        migrate_engine, price_row_id="prc_early00000000000000000", effective_from=day(1)
    )
    await seed_price_row(
        migrate_engine,
        price_row_id="prc_later00000000000000000",
        effective_from=day(10),
        input_price_per_1k=LATER_INPUT_PRICE,
        output_price_per_1k=LATER_OUTPUT_PRICE,
    )

    drafts = [
        gateway_draft(call_id="cal_day05000000000000000000", created_at=day(5)),
        gateway_draft(call_id="cal_day10000000000000000000", created_at=day(10)),
        gateway_draft(call_id="cal_day12000000000000000000", created_at=day(12)),
    ]

    with statements_recorded(app_engine) as recorded:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await write_records(session, drafts)

    assert len(price_statements(recorded)) == 1, (
        "three records straddling a price change are still one round trip; the whole point is "
        "that the batch is resolved from one read and not that it is resolved once"
    )

    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(READ_PRICING, {"ws": WORKSPACE_A})).mappings().all()
    stored = {row["call_id"]: row for row in rows}

    early_cost = compute_cost(
        300, 150, _price("prc_early00000000000000000", INPUT_PRICE, OUTPUT_PRICE, day(1))
    )
    later_cost = compute_cost(
        300,
        150,
        _price("prc_later00000000000000000", LATER_INPUT_PRICE, LATER_OUTPUT_PRICE, day(10)),
    )

    assert stored["cal_day05000000000000000000"]["price_row_id"] == "prc_early00000000000000000"
    assert stored["cal_day10000000000000000000"]["price_row_id"] == "prc_later00000000000000000", (
        "the boundary instant resolved to the superseded row — the interval is half-open, so "
        "effective_from is inclusive and a call made exactly on it is priced at the NEW row"
    )
    assert stored["cal_day12000000000000000000"]["price_row_id"] == "prc_later00000000000000000"

    assert stored["cal_day05000000000000000000"]["cost"] == early_cost
    assert stored["cal_day10000000000000000000"]["cost"] == later_cost
    assert stored["cal_day12000000000000000000"]["cost"] == later_cost
    assert early_cost != later_cost, (
        "the two price rows are priced the same, so this test could not tell the two "
        "resolutions apart by cost — fix the fixture, not the assertion"
    )
