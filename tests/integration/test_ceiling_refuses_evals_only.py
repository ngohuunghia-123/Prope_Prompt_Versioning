"""AC-6 / CL-06: the ceiling refuses an eval run, carries no figure, and that is all.

``check_spend_ceiling`` is the one seam in Prope that fails open, and it is also
the one seam whose *return value* is a security surface. Both properties are
asserted here, and each one is shaped against a failure that looks like a pass.

**A ceiling that always allows is indistinguishable from a working one until
somebody goes over.** So no test here asserts only an allow. Every allow is
paired with a refusal that must come back different, and the refusal is produced
by **real gateway traffic through ``write_records``** rather than by a
hand-inserted ``workspace_spend`` row — AC-6's clause is "a workspace whose
gateway traffic alone has already exceeded its monthly ceiling", and seeding the
aggregate by hand would assert the arithmetic of this test file instead of the
arithmetic of the write path.

**A leaked figure is invisible in a field-by-field assertion.** A-056 says the
ceiling is a boolean surface: no spend, no limit, no remaining budget, no
percentage, no currency, in the return value *or in a log line*. Checking
``decision.figure is None`` would pass against a type that grew a differently
named field tomorrow. So the assertion is over the **serialized form** — the
repr and the ``asdict`` — plus every captured log record, searched for the exact
digit runs of this workspace's spend, its limit, its remainder and its currency
code. The lock file's ``test_plan.security`` requires this under *every* branch
including refused, which is why both branches are built in one test.

**An open-failing check nobody watches is an off switch** (A-104). The fail-open
branch is contractual, so the assertion is not that it fails open — it is that
it *counts* when it does. ``prope_call_ledger_ceiling_failed_open_total`` is
read before and after.

Every assertion about stored state goes through ``migrate_engine``, the owner
role, subject to no policy.
"""

import inspect
from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import structlog
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.call_ledger.seams import (
    CEILING_READ,
    CeilingDecision,
    CeilingReason,
    check_spend_ceiling,
)
from prope.call_ledger.writer import period_month, write_records
from prope.db.session import workspace_transaction
from tests.unit import WORKSPACE_A, WORKSPACE_B, WORKSPACE_C, day, gateway_draft, seed_price_row

INSERT_CEILING = text(
    """
    INSERT INTO ledger.spend_ceiling (
        workspace_id, monthly_limit, per_run_limit, currency, enabled, updated_by
    ) VALUES (:ws, :monthly_limit, NULL, :currency, :enabled, :updated_by)
    """
)
COUNT_RECORDS_FOR = text("SELECT count(*) FROM ledger.call_record WHERE workspace_id = :ws")
READ_SPEND = text(
    """
    SELECT currency, total_cost, call_count FROM ledger.workspace_spend
    WHERE  workspace_id = :ws AND period_month = :month
    """
)

ACTOR = "usr_01J000000000000000000001"

#: One ``gateway_draft`` at the fixture prices: 300 input and 150 output tokens
#: at 0.00015 / 0.0006 per 1k. Every limit below is placed either side of it.
GATEWAY_COST = Decimal("0.000135")

#: Deliberately distinctive digit runs, so the no-figure search below cannot be
#: satisfied by accident and cannot collide with a fixture identifier. ``42`` is
#: under one gateway call, ``99999`` is over it.
LIMIT_BELOW_SPEND = Decimal("0.0000420000")
LIMIT_ABOVE_SPEND = Decimal("0.0009999900000")

#: The spend, the two limits, the remainder in each direction, and the currency.
#: These are the strings A-056 forbids in a decision or a log line, under every
#: branch. Both whole figures and their distinctive runs, because a leak that
#: rounded or truncated would be a leak.
FORBIDDEN_STRINGS = (
    "0.000135",
    "0.0001350000",
    "135",
    "0.000042",
    "0.0000420000",
    "42",
    "0.000093",
    "93",
    "0.00099999",
    "0.0009999900000",
    "99999",
    "0.00086499",
    "86499",
    "USD",
    "usd",
)


class _ExplodingSessionmaker:
    """Raises the instant anything asks it for a session.

    ``workspace_transaction`` calls ``sessionmaker()`` as its very first act, so
    this makes the spend read unevaluable without needing a broken database.
    """

    def __call__(self):
        raise RuntimeError("the aggregate read cannot be evaluated")


def _failed_open_count() -> float:
    return REGISTRY.get_sample_value("prope_call_ledger_ceiling_failed_open_total") or 0.0


async def _seed_ceiling(
    migrate_engine: AsyncEngine,
    workspace_id: str,
    *,
    monthly_limit: Decimal | None,
    enabled: bool,
    currency: str | None = "USD",
) -> None:
    async with migrate_engine.begin() as connection:
        await connection.execute(
            INSERT_CEILING,
            {
                "ws": workspace_id,
                "monthly_limit": monthly_limit,
                "currency": currency,
                "enabled": enabled,
                "updated_by": ACTOR,
            },
        )


async def _spend_one_gateway_call(
    app_sessionmaker,
    migrate_engine: AsyncEngine,
    workspace_id: str,
    *,
    call_id: str,
    created_at: datetime | None = None,
) -> None:
    """Move ``workspace_spend`` the way production does — through the write path."""
    await seed_price_row(
        migrate_engine,
        price_row_id=f"prc_{call_id[4:]}",
        workspace_id=workspace_id,
    )
    draft = gateway_draft(
        call_id=call_id,
        workspace_id=workspace_id,
        **({"created_at": created_at} if created_at is not None else {}),
    )
    async with workspace_transaction(app_sessionmaker, workspace_id) as session:
        await write_records(session, [draft])


async def _scalar(migrate_engine: AsyncEngine, statement, params):
    async with migrate_engine.connect() as connection:
        return (await connection.execute(statement, params)).scalar_one()


async def _spend_row(migrate_engine: AsyncEngine, workspace_id: str, month):
    async with migrate_engine.connect() as connection:
        row = (
            (await connection.execute(READ_SPEND, {"ws": workspace_id, "month": month}))
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


NOW = day(5)


async def test_a_workspace_with_no_ceiling_row_is_allowed(app_sessionmaker) -> None:
    """Both ceilings default off (A-029), and "off" is the absence of a row."""
    decision = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=NOW)

    assert decision.allowed is True
    assert decision.reason is None


async def test_a_disabled_ceiling_allows_however_far_over_the_spend_is(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """``enabled`` is the switch, and it is checked before the figure is."""
    await _seed_ceiling(
        migrate_engine, WORKSPACE_A, monthly_limit=LIMIT_BELOW_SPEND, enabled=False
    )
    await _spend_one_gateway_call(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_01J0000000000000000000401"
    )

    decision = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=NOW)

    assert decision.allowed is True
    assert decision.reason is None


async def test_gateway_traffic_alone_over_the_ceiling_refuses_with_a_reason(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """AC-6's first clause, and the reason is a machine code (ADR-0053)."""
    await _seed_ceiling(migrate_engine, WORKSPACE_A, monthly_limit=LIMIT_BELOW_SPEND, enabled=True)
    await _spend_one_gateway_call(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_01J0000000000000000000402"
    )

    decision = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=NOW)

    assert decision.allowed is False
    assert decision.reason is CeilingReason.MONTHLY_CEILING_EXCEEDED
    assert str(decision.reason) == "monthly_ceiling_exceeded"


async def test_gateway_traffic_keeps_being_recorded_after_the_refusal(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """AC-6's second clause: the ceiling governs eval runs and never gateway traffic.

    A ceiling that quietly throttled the ledger would break the very number it
    is computed from, and the failure would look like a quiet month.
    """
    await _seed_ceiling(migrate_engine, WORKSPACE_A, monthly_limit=LIMIT_BELOW_SPEND, enabled=True)
    await _spend_one_gateway_call(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_01J0000000000000000000403"
    )

    refused = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=NOW)
    assert refused.allowed is False, "the fixture must actually be over, or this proves nothing"

    await _spend_one_gateway_call(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_01J0000000000000000000404"
    )

    assert await _scalar(migrate_engine, COUNT_RECORDS_FOR, {"ws": WORKSPACE_A}) == 2
    spend = await _spend_row(migrate_engine, WORKSPACE_A, period_month(day(5)))
    assert spend is not None
    assert spend["call_count"] == 2
    assert spend["total_cost"] == GATEWAY_COST * 2


async def test_a_workspace_under_its_ceiling_is_allowed(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    await _seed_ceiling(migrate_engine, WORKSPACE_A, monthly_limit=LIMIT_ABOVE_SPEND, enabled=True)
    await _spend_one_gateway_call(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_01J0000000000000000000405"
    )

    decision = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=NOW)

    assert decision.allowed is True
    assert decision.reason is None


async def test_spend_exactly_at_the_limit_refuses(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """INT-020: "a run that starts UNDER the ceiling ... finishes".

    At exactly the limit the workspace is not under it. Allowing there would
    guarantee crossing, because every run costs money and no run costs zero —
    ``ck_call_record_cost_is_never_zero`` says so in the schema.
    """
    await _seed_ceiling(migrate_engine, WORKSPACE_A, monthly_limit=GATEWAY_COST, enabled=True)
    await _spend_one_gateway_call(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_01J0000000000000000000406"
    )

    decision = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=NOW)

    assert decision.allowed is False
    assert decision.reason is CeilingReason.MONTHLY_CEILING_EXCEEDED


async def test_no_figure_reaches_the_decision_or_a_log_line_under_either_branch(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """A-056, asserted over the serialized form rather than field by field.

    Both branches in one test, because the lock file's ``test_plan.security``
    line requires the property under every branch **including refused**, and
    refused is the branch where a helpful "you are $X over" would be added.
    """
    await _seed_ceiling(migrate_engine, WORKSPACE_A, monthly_limit=LIMIT_BELOW_SPEND, enabled=True)
    await _spend_one_gateway_call(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_01J0000000000000000000407"
    )
    await _seed_ceiling(migrate_engine, WORKSPACE_B, monthly_limit=LIMIT_ABOVE_SPEND, enabled=True)
    await _spend_one_gateway_call(
        app_sessionmaker, migrate_engine, WORKSPACE_B, call_id="cal_01J0000000000000000000408"
    )

    with structlog.testing.capture_logs() as captured:
        refused = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=NOW)
        allowed = await check_spend_ceiling(app_sessionmaker, WORKSPACE_B, now=NOW)

    assert refused.allowed is False and allowed.allowed is True, "both branches must be real"
    assert captured, "the refusal must log SOMETHING, or this assertion is vacuous"

    serialized = [repr(refused), str(asdict(refused)), repr(allowed), str(asdict(allowed))]
    serialized.extend(repr(record) for record in captured)

    for rendered in serialized:
        for forbidden in FORBIDDEN_STRINGS:
            assert forbidden not in rendered, (
                f"{forbidden!r} — a spend, limit, remaining or currency value — reached "
                f"{rendered!r}. A-056: the ceiling is a boolean surface"
            )


async def test_an_unevaluable_check_allows_and_counts_and_does_not_raise() -> None:
    """A-104: fail open is contractual, so the counter is the control, not the branch."""
    before = _failed_open_count()

    decision = await check_spend_ceiling(_ExplodingSessionmaker(), WORKSPACE_A, now=NOW)

    assert decision.allowed is True
    assert decision.reason is None
    assert _failed_open_count() == before + 1


async def test_a_ceiling_and_a_spend_in_different_currencies_fail_open(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """A-107 forbids conversion, so an unmatched pair is unevaluable, not exceeded.

    Comparing a VND ceiling to a USD total is comparing two numbers with
    different units. Refusing on it would be a refusal computed from a figure
    that does not exist; allowing silently would be the off switch A-104 warns
    about. Fail open **and count** is the only answer that is neither.
    """
    await _seed_ceiling(
        migrate_engine,
        WORKSPACE_A,
        monthly_limit=LIMIT_BELOW_SPEND,
        enabled=True,
        currency="VND",
    )
    await _spend_one_gateway_call(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_01J0000000000000000000409"
    )
    before = _failed_open_count()

    decision = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=NOW)

    assert decision.allowed is True
    assert decision.reason is None
    assert _failed_open_count() == before + 1


async def test_the_ceiling_reads_the_same_month_write_records_files_into(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """Pitfall 8, as behaviour rather than as a unit test of the helper.

    The instant is 00:30 on 1 September in a +07:00 offset, which is 17:30 on 31
    August in UTC. A ceiling read that derived its month locally would look for
    September, find no ``workspace_spend`` row, and allow — while
    ``write_records`` filed the traffic under August. Both sides would be
    internally consistent and simply looking at different rows, which is why the
    disagreement is invisible and why one shared helper is the answer.
    """
    instant = datetime(2026, 9, 1, 0, 30, tzinfo=timezone(timedelta(hours=7)))
    assert period_month(instant) == datetime(2026, 8, 1, tzinfo=UTC).date()
    assert instant.month == 9, "the fixture only works if local and UTC disagree"

    await _seed_ceiling(migrate_engine, WORKSPACE_C, monthly_limit=LIMIT_BELOW_SPEND, enabled=True)
    await _spend_one_gateway_call(
        app_sessionmaker,
        migrate_engine,
        WORKSPACE_C,
        call_id="cal_01J0000000000000000000410",
        created_at=instant,
    )

    decision = await check_spend_ceiling(app_sessionmaker, WORKSPACE_C, now=instant)

    assert decision.allowed is False, (
        "the ceiling read a different month from the one write_records filed into"
    )


async def test_the_decision_has_exactly_two_fields_and_a_typed_reason() -> None:
    """The type is the mitigation. A third field carrying a number is the leak."""
    names = [field.name for field in fields(CeilingDecision)]
    assert names == ["allowed", "reason"]

    annotations = {field.name: field.type for field in fields(CeilingDecision)}
    assert "CeilingReason" in str(annotations["reason"])
    assert issubclass(CeilingReason, str)
    assert [member.value for member in CeilingReason] == ["monthly_ceiling_exceeded"]


async def test_the_ceiling_read_does_not_aggregate_call_record() -> None:
    """T-02-25: the aggregate exists so this is one row read, not a table scan.

    ``ledger.workspace_spend`` is maintained inside ``write_records``' own
    transaction (A-103) precisely so that a check running before every eval run
    reads one row keyed ``(workspace_id, period_month)`` instead of aggregating
    the largest and fastest-growing table in the system. The assertion is over
    the statement rather than over the module, because the module's prose says
    the words the statement must not contain.
    """
    statement = CEILING_READ.text

    assert "SUM(" not in statement.upper()
    assert "call_record" not in statement
    assert "ledger.workspace_spend" in statement
    assert "ledger.spend_ceiling" in statement
    assert "check_spend_ceiling" in inspect.getsource(check_spend_ceiling)
