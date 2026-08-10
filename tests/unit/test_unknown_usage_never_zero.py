"""CL-11: a provider that returned no usage object records NULL, never zero.

ADR-0019: "A missing usage object is `unknown`, never zero. Token counts are
null, and cost is `not_applicable` rather than 0."

The third test is the one worth reading twice. Gateway's GATE-04 describes a
pre-first-byte fallback recorded "with zero tokens and zero cost". Under this
encoding that row does not exist: it is ``usage_status='unknown'`` /
``cost_status='not_applicable'`` with NULL tokens and a NULL cost, and
``ck_call_record_unknown_usage_is_null`` refuses the literal reading. The two
documents use different words for the same row, which is why OQ-E is carried
upstream — and why the reading is pinned in a test here, so the Phase 19 gateway
work inherits it rather than inventing a zero.

CL-11 also requires that "the unknown count is reported alongside the total".
The reporting half is ``get_run_totals``, which the ROADMAP puts in Phase 2.
What Phase 1 owes is a *storage* shape that makes the count computable without
inspecting NULLs ambiguously, and the last assertion below shows it: counting on
``usage_status`` gives the same answer as counting on the token columns, so
Phase 2 can use the status and never has to guess what a NULL means.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from prope.call_ledger.domain import CostStatus, Outcome, UsageStatus
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from tests.unit import (
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

COUNT_UNKNOWN_BY_STATUS = text(
    "SELECT count(*) FROM ledger.call_record WHERE usage_status = 'unknown'"
)
COUNT_UNKNOWN_BY_NULL_TOKENS = text(
    "SELECT count(*) FROM ledger.call_record WHERE input_tokens IS NULL"
)

INSERT_UNKNOWN_USAGE_CALL = text(
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
        :input_tokens, :output_tokens, 'unknown',
        NULL, NULL, NULL, 'not_applicable',
        :created_at
    )
    """
)


def _unknown_insert_values(*, call_id: str, input_tokens, output_tokens) -> dict:
    return {
        "call_id": call_id,
        "workspace_id": WORKSPACE_A,
        "version_id": VERSION_ID,
        "provider_config_id": PROVIDER_CONFIG,
        "upstream_model": UPSTREAM_MODEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "created_at": day(5),
    }


async def test_a_call_with_no_usage_object_stores_nulls_rather_than_zeros(
    app_sessionmaker, migrate_engine
):
    """A price row IS in force here, and the call is still not priced.

    That is the point of seeding it: ``not_applicable`` is not a synonym for
    "no price available". There are no tokens, so there is nothing to price, and
    multiplying an absent count by a known price would produce a confident zero.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    draft = gateway_draft(input_tokens=None, output_tokens=None)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await write_records(session, [draft])

    assert result.unknown == 1
    assert result.priced == 0
    assert result.unpriced == 0

    async with migrate_engine.begin() as control:
        row = (
            await control.execute(READ_CALL_RECORD, {"call_id": draft.call_id})
        ).mappings().one()

    assert row["input_tokens"] is None, "an absent token count became a zero"
    assert row["output_tokens"] is None, "an absent token count became a zero"
    assert row["usage_status"] == UsageStatus.UNKNOWN.value
    assert row["cost"] is None
    assert row["currency"] is None
    assert row["price_row_id"] is None
    assert row["cost_status"] == CostStatus.NOT_APPLICABLE.value


async def test_zero_tokens_refused_by_the_engine_when_usage_is_unknown(
    app_sessionmaker, migrate_engine
):
    """``ck_call_record_unknown_usage_is_null``, asserted around the writer.

    The positive control comes first: the identical statement with NULL token
    counts lands. So the refusal below is about the zeros and not about the
    statement.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await session.execute(
            INSERT_UNKNOWN_USAGE_CALL,
            _unknown_insert_values(
                call_id="cal_01J0000000000000000000U1",
                input_tokens=None,
                output_tokens=None,
            ),
        )

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_UNKNOWN_BY_STATUS)).scalar_one() == 1

    with pytest.raises(DBAPIError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await session.execute(
                INSERT_UNKNOWN_USAGE_CALL,
                _unknown_insert_values(
                    call_id="cal_01J0000000000000000000U2",
                    input_tokens=0,
                    output_tokens=0,
                ),
            )

    message = str(excinfo.value).lower()
    assert "ck_call_record_unknown_usage_is_null" in message, message


async def test_the_gateway_pre_first_byte_fallback_is_unknown_not_a_zero(
    app_sessionmaker, migrate_engine
):
    """OQ-E. GATE-04's "zero tokens and zero cost" row, as this encoding has it.

    A pre-first-byte failure: the provider was reached, nothing came back, and
    there is no usage object to record. ``outcome`` carries the failure;
    ``usage_status`` and ``cost_status`` carry the absence. Nothing carries a
    zero.
    """
    await seed_price_row(migrate_engine, effective_from=day(1))
    fallback = gateway_draft(
        call_id="cal_01J0000000000000000000E1",
        outcome=Outcome.UPSTREAM_ERROR,
        error_class="upstream_timeout",
        input_tokens=None,
        output_tokens=None,
        body=None,
    )
    served = gateway_draft(call_id="cal_01J0000000000000000000E2")

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await write_records(session, [fallback, served])

    assert result.unknown == 1
    assert result.priced == 1

    async with migrate_engine.begin() as control:
        row = (
            await control.execute(READ_CALL_RECORD, {"call_id": fallback.call_id})
        ).mappings().one()
        zeros = (
            await control.execute(
                text(
                    "SELECT count(*) FROM ledger.call_record "
                    "WHERE cost = 0 OR input_tokens = 0 OR output_tokens = 0"
                )
            )
        ).scalar_one()
        by_status = (await control.execute(COUNT_UNKNOWN_BY_STATUS)).scalar_one()
        by_nulls = (await control.execute(COUNT_UNKNOWN_BY_NULL_TOKENS)).scalar_one()
        total = (
            await control.execute(text("SELECT count(*) FROM ledger.call_record"))
        ).scalar_one()

    assert row["usage_status"] == UsageStatus.UNKNOWN.value
    assert row["cost_status"] == CostStatus.NOT_APPLICABLE.value
    assert row["input_tokens"] is None and row["output_tokens"] is None
    assert row["cost"] is None

    assert total == 2, "positive control: without rows, the zero count below is free"
    assert zeros == 0

    # CL-11's reporting half is Phase 2's. What Phase 1 owes is a shape whose
    # unknown count is computable from the status alone — counting on the token
    # columns must not be needed, and must not disagree.
    assert by_status == 1
    assert by_status == by_nulls
