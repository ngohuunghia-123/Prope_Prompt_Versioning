"""Unit tests — one function's scope, still against a live PostgreSQL 17.

"Unit" here names the *scope* of the assertion, not the absence of a database
(D-02). Effective-dated selection at a timestamp boundary, a `numeric(20,10)`
round-trip and a CHECK refusal are properties of the engine; asserting them
against a mocked driver would assert the mock.

The seeding helpers below exist so every test in this package builds price rows
and call records the same way. Each takes overrides, so a test that wants a
refusal changes exactly the one field that should cause it and the constraint
named in the error is the constraint under test.

All datetimes here are timezone-aware UTC, without exception. A naive value
compared against a `timestamptz` column is interpreted against the *server's*
time zone, which would make the day-5/day-12/day-20 arithmetic pass or fail by
geography (Pitfall 7).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.call_ledger.domain import CallBodyDraft, CallRecordDraft, Outcome, Source

WORKSPACE_A = "wsp_01J0000000000000000000AAA"
WORKSPACE_B = "wsp_01J0000000000000000000BBB"

PROVIDER_CONFIG = "prv_01J000000000000000000001"
OTHER_PROVIDER_CONFIG = "prv_01J000000000000000000002"

UPSTREAM_MODEL = "gpt-4o-mini"
OTHER_UPSTREAM_MODEL = "gpt-4o"

VERSION_ID = "ver_01J0000000000000000000001"
CREATED_BY = "usr_01J000000000000000000001"

#: Day 1 of the fixture calendar. Every other instant in these tests is this
#: value plus a number of days, so "day 5" and "day 20" are arithmetic rather
#: than a date somebody has to decode.
DAY_1 = datetime(2026, 8, 1, tzinfo=UTC)


def day(n: int, **offset: int) -> datetime:
    """Day ``n`` of the fixture calendar, tz-aware UTC. ``day(1)`` is DAY_1."""
    return DAY_1 + timedelta(days=n - 1, **offset)


#: A realistic pair of per-1k prices: fractions of a US cent per thousand
#: tokens. Quantising a cost derived from these to a currency's minor units
#: stores 0.00, which is the failure the whole cost path is shaped to avoid.
INPUT_PRICE = Decimal("0.00015")
OUTPUT_PRICE = Decimal("0.0006")


INSERT_PRICE_ROW = text(
    """
    INSERT INTO ledger.price_table (
        price_row_id, workspace_id, provider_config_id, upstream_model,
        input_price_per_1k, output_price_per_1k, currency,
        effective_from, created_by
    ) VALUES (
        :price_row_id, :workspace_id, :provider_config_id, :upstream_model,
        :input_price_per_1k, :output_price_per_1k, :currency,
        :effective_from, :created_by
    )
    """
)


def price_row_values(**overrides: Any) -> dict[str, Any]:
    """The simplest price row `price_table`'s CHECK set accepts."""
    values: dict[str, Any] = {
        "price_row_id": "prc_01J0000000000000000000001",
        "workspace_id": WORKSPACE_A,
        "provider_config_id": PROVIDER_CONFIG,
        "upstream_model": UPSTREAM_MODEL,
        "input_price_per_1k": INPUT_PRICE,
        "output_price_per_1k": OUTPUT_PRICE,
        "currency": "USD",
        "effective_from": DAY_1,
        "created_by": CREATED_BY,
    }
    values.update(overrides)
    return values


async def seed_price_row(migrate_engine: AsyncEngine, **overrides: Any) -> str:
    """Seed one price row as the owner and return its id.

    Seeded as ``prope_migrate`` rather than through the application session so
    the seeding path does not depend on the grant matrix the security tests are
    separately asserting.
    """
    values = price_row_values(**overrides)
    async with migrate_engine.begin() as connection:
        await connection.execute(INSERT_PRICE_ROW, values)
    return str(values["price_row_id"])


def gateway_draft(**overrides: Any) -> CallRecordDraft:
    """A gateway call with reported usage and a body.

    ``version_id`` is set because ``ck_call_record_gateway_calls_carry_version_id``
    requires it — the "100% of gateway calls record a version ID" success metric
    is a constraint, not a hope.
    """
    values: dict[str, Any] = {
        "call_id": "cal_01J0000000000000000000001",
        "workspace_id": WORKSPACE_A,
        "source": Source.GATEWAY,
        "outcome": Outcome.OK,
        "created_at": day(5),
        "version_id": VERSION_ID,
        "prompt_id": "prm_01J0000000000000000000001",
        "revision_number": 3,
        "consumer_key_id": "key_01J000000000000000000001",
        "provider_config_id": PROVIDER_CONFIG,
        "upstream_model": UPSTREAM_MODEL,
        "input_tokens": 300,
        "output_tokens": 150,
        "body": CallBodyDraft(request_body="a request", response_body="a response", byte_size=18),
    }
    values.update(overrides)
    return CallRecordDraft(**values)


def eval_draft(**overrides: Any) -> CallRecordDraft:
    """An eval call: ``run_id`` and ``case_id`` set, no consumer key, no body.

    ``ck_call_record_eval_calls_carry_run`` enforces the first two; A-055 is why
    there is never a ``call_body`` row for one of these.
    """
    values: dict[str, Any] = {
        "call_id": "cal_01J0000000000000000000009",
        "workspace_id": WORKSPACE_A,
        "source": Source.EVAL,
        "outcome": Outcome.OK,
        "created_at": day(5),
        "run_id": "run_01J000000000000000000001",
        "case_id": "cas_01J000000000000000000001",
        "provider_config_id": PROVIDER_CONFIG,
        "upstream_model": UPSTREAM_MODEL,
        "input_tokens": 200,
        "output_tokens": 100,
    }
    values.update(overrides)
    return CallRecordDraft(**values)
