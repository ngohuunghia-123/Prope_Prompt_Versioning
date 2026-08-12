"""CL-05: adding a price row after the fact fills only what was never priced.

ADR-0019: "Repricing fills only previously-unpriced rows. A row that already has
a cost is never recomputed — that is the rule that makes history stable."

The three properties are asserted **separately** on purpose. A single
reprice-and-check test can pass while two of them are broken: it is entirely
possible to write a repricing pass that gives the unpriced call its cost *and*
quietly rewrites the priced one, and the obvious test — "did the unpriced row
change?" — is green either way. So:

- one test watches a previously-unpriced row gain a cost;
- one test compares an **already-priced** row's whole tuple before and after a
  run that had a newly-applicable price row available to it, so the run had
  every opportunity to move the figure and did not;
- one test watches a ``not_applicable`` row stay ``not_applicable``, which the
  status predicate already guarantees and which is asserted anyway, because the
  predicate is one "improvement" away from being widened to a test on the cost
  column being absent — and that wider filter would start pricing calls that
  have no token counts at all.

Every assertion is made through ``migrate_engine`` by direct query. The owner
role bypasses no policy it is subject to (it is subject to none), so a row the
test expects to see cannot be masked by a tenant predicate the test forgot.
"""

from decimal import Decimal

from sqlalchemy import text

from prope.call_ledger.domain import CostStatus, PriceRow, UsageStatus
from prope.call_ledger.pricing import compute_cost
from prope.call_ledger.repricing import reprice_unpriced
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from tests.unit import (
    INPUT_PRICE,
    OTHER_UPSTREAM_MODEL,
    OUTPUT_PRICE,
    WORKSPACE_A,
    day,
    gateway_draft,
    seed_price_row,
)

#: The whole row, so "unchanged" means the tuple and not the cost column.
READ_WHOLE_RECORD = text("SELECT * FROM ledger.call_record WHERE call_id = :call_id")

COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")
COUNT_ZEROS = text(
    "SELECT count(*) FROM ledger.call_record "
    "WHERE cost = 0 OR input_tokens = 0 OR output_tokens = 0"
)
COUNT_INCOHERENT_NOT_APPLICABLE = text(
    "SELECT count(*) FROM ledger.call_record "
    "WHERE cost_status = 'not_applicable' AND (cost IS NOT NULL OR input_tokens IS NOT NULL)"
)

#: A second price row for the same key, an order of magnitude dearer. Whatever
#: repricing would have computed against this row is nothing like what the day-1
#: row produced, so "the priced call is unchanged" is a claim with teeth.
DEARER_INPUT_PRICE = Decimal("0.0015")
DEARER_OUTPUT_PRICE = Decimal("0.006")

#: 300 input + 150 output tokens at the day-1 fixture prices.
EXPECTED_COST = Decimal("0.0001350000")

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


async def _reprice(app_sessionmaker, *, workspace_id=WORKSPACE_A, **kwargs):
    async with workspace_transaction(app_sessionmaker, workspace_id) as session:
        return await reprice_unpriced(session, workspace_id=workspace_id, **kwargs)


async def _read(migrate_engine, call_id):
    async with migrate_engine.begin() as control:
        return dict(
            (await control.execute(READ_WHOLE_RECORD, {"call_id": call_id})).mappings().one()
        )


async def test_a_previously_unpriced_call_gains_a_cost_when_a_price_row_arrives(
    app_sessionmaker, migrate_engine
):
    """AC-5's remedy. The call was made on day 5 with no price row anywhere; the
    row someone adds afterwards is effective from day 1, so it *was* in force at
    the call's own timestamp all along.

    The cost is compared against ``compute_cost``'s own answer, not against a
    number typed into this file: one cost function serves the writer and
    repricing, and a repriced figure that merely looks right is the failure this
    comparison exists to catch.
    """
    draft = gateway_draft(created_at=day(5))
    result = await _write(app_sessionmaker, [draft])
    assert result.unpriced == 1, "positive control: the call must start unpriced"

    before = await _read(migrate_engine, draft.call_id)
    assert before["cost_status"] == CostStatus.UNPRICED.value
    assert before["cost"] is None
    assert before["input_tokens"] == 300

    price_row_id = await seed_price_row(migrate_engine, effective_from=day(1))

    repriced = await _reprice(app_sessionmaker)

    assert repriced.repriced == 1
    assert repriced.still_unpriced == 0

    after = await _read(migrate_engine, draft.call_id)
    assert after["cost_status"] == CostStatus.PRICED.value
    assert after["currency"] == "USD"
    assert after["price_row_id"] == price_row_id
    assert after["cost"] == compute_cost(300, 150, PRICE_FOR_CHECK) == EXPECTED_COST
    assert after["cost"] > 0

    # The tokens, the timestamps and the identity are untouched: repricing
    # answers one question and rewrites nothing else.
    assert after["input_tokens"] == before["input_tokens"]
    assert after["output_tokens"] == before["output_tokens"]
    assert after["created_at"] == before["created_at"]
    assert after["usage_status"] == before["usage_status"]


async def test_an_already_priced_call_is_unchanged_field_for_field(
    app_sessionmaker, migrate_engine
):
    """The property that makes history stable, asserted the only way that means
    anything: the priced row is compared as a **whole tuple** before and after a
    run that had every opportunity to move it.

    The setup is deliberately adversarial. A second price row for the same key
    is inserted with an ``effective_from`` of day 3, which supersedes the day-1
    row for a call made on day 5 — so a repricing pass that recomputed a priced
    row would resolve this newer, ten-times-dearer row and store a different
    figure. And the run is not a no-op: a second call in the same workspace *is*
    repriced by it, so "nothing changed" cannot be explained by "nothing ran".
    """
    await seed_price_row(migrate_engine, effective_from=day(1))

    priced_draft = gateway_draft(call_id="cal_01J0000000000000000000P1", created_at=day(5))
    unpriced_draft = gateway_draft(
        call_id="cal_01J0000000000000000000P2",
        created_at=day(5),
        upstream_model=OTHER_UPSTREAM_MODEL,
    )
    result = await _write(app_sessionmaker, [priced_draft, unpriced_draft])
    assert (result.priced, result.unpriced) == (1, 1)

    before = await _read(migrate_engine, priced_draft.call_id)
    assert before["cost_status"] == CostStatus.PRICED.value
    assert before["cost"] == EXPECTED_COST

    # The row that would move the figure if anything recomputed it.
    await seed_price_row(
        migrate_engine,
        price_row_id="prc_01J00000000000000000DEAR",
        input_price_per_1k=DEARER_INPUT_PRICE,
        output_price_per_1k=DEARER_OUTPUT_PRICE,
        effective_from=day(3),
    )
    # And the row that gives the other call a price, so the run does real work.
    await seed_price_row(
        migrate_engine,
        price_row_id="prc_01J000000000000000000OTH",
        upstream_model=OTHER_UPSTREAM_MODEL,
        effective_from=day(1),
    )

    repriced = await _reprice(app_sessionmaker)
    assert repriced.repriced == 1, (
        "positive control: the run must have repriced the other call, or "
        "'the priced row did not move' is satisfied by the run doing nothing"
    )

    after = await _read(migrate_engine, priced_draft.call_id)

    assert after == before, (
        "an already-priced call changed under repricing; a figure a reviewer "
        f"already acted on was rewritten. before={before} after={after}"
    )
    # Named separately so a failure says which field, not just "the dict".
    assert after["cost"] == EXPECTED_COST
    assert after["price_row_id"] == "prc_01J0000000000000000000001"
    assert after["currency"] == "USD"
    assert after["cost_status"] == CostStatus.PRICED.value

    # And the other call really did get the price it was owed.
    other = await _read(migrate_engine, unpriced_draft.call_id)
    assert other["cost_status"] == CostStatus.PRICED.value
    assert other["price_row_id"] == "prc_01J000000000000000000OTH"


async def test_a_not_applicable_call_is_still_not_applicable_after_repricing(
    app_sessionmaker, migrate_engine
):
    """A call whose provider returned no usage object has no tokens, so there is
    nothing to price — and a price row being available does not change that.

    The status predicate already excludes this row. Asserting it anyway is what
    turns a later widening of that filter into a failing test rather than into
    a table of calls priced on token counts nobody reported.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))

    draft = gateway_draft(created_at=day(5), input_tokens=None, output_tokens=None)
    result = await _write(app_sessionmaker, [draft])
    assert result.unknown == 1

    before = await _read(migrate_engine, draft.call_id)
    assert before["cost_status"] == CostStatus.NOT_APPLICABLE.value
    assert before["usage_status"] == UsageStatus.UNKNOWN.value

    repriced = await _reprice(app_sessionmaker)
    assert repriced.repriced == 0
    assert repriced.still_unpriced == 0

    after = await _read(migrate_engine, draft.call_id)
    assert after == before
    assert after["cost_status"] == CostStatus.NOT_APPLICABLE.value
    assert after["usage_status"] == UsageStatus.UNKNOWN.value
    assert after["cost"] is None
    assert after["currency"] is None
    assert after["price_row_id"] is None
    assert after["input_tokens"] is None
    assert after["output_tokens"] is None


async def test_a_price_row_that_is_still_not_yet_effective_leaves_the_call_unpriced(
    app_sessionmaker, migrate_engine
):
    """Repricing resolves by the same half-open rule the writer uses.

    A row added with an ``effective_from`` of day 10 was not in force for a call
    made on day 5, and "close enough" is not an answer this module has. The call
    stays unpriced and stays on the worklist.
    """
    draft = gateway_draft(created_at=day(5))
    await _write(app_sessionmaker, [draft])

    before = await _read(migrate_engine, draft.call_id)
    await seed_price_row(migrate_engine, effective_from=day(10))

    repriced = await _reprice(app_sessionmaker)

    assert repriced.repriced == 0
    assert repriced.still_unpriced == 1, (
        "positive control: the candidate must have been examined and left alone, "
        "not skipped by a selection that never saw it"
    )

    after = await _read(migrate_engine, draft.call_id)
    assert after == before
    assert after["cost_status"] == CostStatus.UNPRICED.value
    assert after["cost"] is None


async def test_a_second_run_with_no_new_price_rows_reprices_nothing(
    app_sessionmaker, migrate_engine
):
    """Repricing is not a pass that keeps finding work. Once a call is priced it
    is no longer a candidate, so the second run has nothing to do and says so."""
    draft = gateway_draft(created_at=day(5))
    await _write(app_sessionmaker, [draft])
    await seed_price_row(migrate_engine, effective_from=day(1))

    first = await _reprice(app_sessionmaker)
    assert first.repriced == 1

    after_first = await _read(migrate_engine, draft.call_id)

    second = await _reprice(app_sessionmaker)

    assert second.repriced == 0
    assert second.still_unpriced == 0
    assert await _read(migrate_engine, draft.call_id) == after_first


async def test_no_zero_survives_repricing_of_a_mixed_batch(app_sessionmaker, migrate_engine):
    """The phase's headline claim carried across the repricing path, with the
    positive control that makes it mean something.

    Three cost states go in — one call that the newly added price row will
    price, one already priced, one with no usage object — repricing runs, and
    then, as ``prope_migrate`` and **inside this test**, the table is asked
    three questions at once: does it hold rows at all, does any row record a
    zero cost or a zero token count, and does any ``not_applicable`` row carry a
    cost or a token count.

    The row count is not decoration. ``truncate_owned_tables`` empties every ledger
    table between tests, so the same two zero-counts run after the suite read an
    empty table and return 0 whether the guarantee holds or not (Pitfall 8).
    """
    await seed_price_row(migrate_engine, effective_from=day(1))

    drafts = [
        # Priced now, and must still be priced at exactly this figure after.
        gateway_draft(call_id="cal_01J0000000000000000000X1", created_at=day(5)),
        # Unpriced now — no row for this model yet.
        gateway_draft(
            call_id="cal_01J0000000000000000000X2",
            created_at=day(5),
            upstream_model=OTHER_UPSTREAM_MODEL,
        ),
        # No usage object at all.
        gateway_draft(
            call_id="cal_01J0000000000000000000X3",
            created_at=day(5),
            input_tokens=None,
            output_tokens=None,
        ),
    ]
    result = await _write(app_sessionmaker, drafts)
    assert (result.priced, result.unpriced, result.unknown) == (1, 1, 1)

    await seed_price_row(
        migrate_engine,
        price_row_id="prc_01J000000000000000000MIX",
        upstream_model=OTHER_UPSTREAM_MODEL,
        effective_from=day(1),
    )

    repriced = await _reprice(app_sessionmaker)
    assert repriced.repriced == 1

    async with migrate_engine.begin() as control:
        total = (await control.execute(COUNT_RECORDS)).scalar_one()
        zeros = (await control.execute(COUNT_ZEROS)).scalar_one()
        incoherent = (await control.execute(COUNT_INCOHERENT_NOT_APPLICABLE)).scalar_one()

    assert total > 0, (
        "positive control: against an empty table both counts below are 0 for free"
    )
    assert total == 3

    assert zeros == 0, (
        "a row records a zero cost or a zero token count after repricing — an "
        "absence became a number a reviewer would act on"
    )
    assert incoherent == 0, (
        "a not_applicable row carries a cost or a token count — the status "
        "predicate was widened and a call with no reported usage was priced"
    )

    # The already-priced row still holds the sub-cent figure the writer gave it.
    priced_row = await _read(migrate_engine, "cal_01J0000000000000000000X1")
    assert priced_row["cost"] == EXPECTED_COST < Decimal("0.01")
