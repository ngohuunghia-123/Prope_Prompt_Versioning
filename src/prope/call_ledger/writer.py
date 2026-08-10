"""The Phase 1 write-path seam. One writer, three cost states, no fourth.

``write_records`` is what Phase 2's broker drain calls once per workspace group
and what Phase 3's direct-write fallback calls with a single record. There is
one implementation of it on purpose: the lock file requires that pricing and
``expires_at`` stamping cannot drift between those two callers, and two
functions that both "write a call record" is exactly how they would.

**The session is handed in and carries exactly one workspace.** It comes from
``workspace_transaction()``, which opened the transaction and set the tenant for
its duration (D-08, ADR-0040). This function therefore opens no transaction,
switches no workspace, and refuses a batch containing a second ``workspace_id``
before writing any of it. The policy's ``WITH CHECK`` would refuse a mis-stamped
row at the engine, but a half-written batch is not an acceptable way to discover
the mistake.

**Every record is priced at its OWN ``created_at``.** Not at wall-clock write
time, which differs after a backlog or a redelivery (ADR-0019). Nothing in this
module reads a clock: ``expires_at`` is the record's own ``created_at`` plus the
``retention_window`` argument, and ``period_month`` is the record's own
``created_at`` in UTC. ``written_at`` and ``updated_at`` are left to their column
defaults, which is the one place a server clock is the correct answer, because
those two columns mean "when the database saw this".

**Three states, and nothing may invent a fourth.**

    reported usage + a resolved price   -> priced,         cost > 0, currency, price_row_id
    reported usage + no resolved price  -> unpriced,       cost/currency/price_row_id NULL
    no usage object                     -> not_applicable, tokens NULL as well

There is no default branch. A missing price is never a zero price, a missing
usage object is never zero tokens, and no path here substitutes an average, the
nearest price row, or a figure inferred from prompt length. ``ck_call_record_
cost_state_is_coherent`` and ``ck_call_record_cost_is_never_zero`` say the same
thing in the schema; this module is what makes sure they are never asked to.

**No body reaches a log line or a metric label** (A-046). This module writes a
body to exactly one place — ``ledger.call_body`` — and it emits no log and no
metric at all.
"""

from collections.abc import Sequence
from datetime import UTC, date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.call_ledger.domain import (
    CallRecordDraft,
    CostStatus,
    Source,
    UsageStatus,
    WriteResult,
)
from prope.call_ledger.pricing import compute_cost, resolve_price

#: A-040: 30 days, the default retention window. It is a PARAMETER for this
#: phase and deliberately not a column read (OQ-B) — no table outside
#: call-ledger's ``data.owns`` is touched to satisfy it. Phase 2 owns the
#: storage decision when ``PUT /workspaces/{id}/retention`` arrives.
DEFAULT_RETENTION_WINDOW = timedelta(days=30)

INSERT_CALL_RECORD = text(
    """
    INSERT INTO ledger.call_record (
        call_id, workspace_id, source, prompt_id, version_id, revision_number,
        run_id, case_id, consumer_key_id, actor_id,
        provider_config_id, upstream_model, outcome,
        pinned, fallback, streaming,
        input_tokens, output_tokens, usage_status,
        cost, currency, price_row_id, cost_status,
        added_latency_ms, upstream_duration_ms, error_class,
        created_at
    ) VALUES (
        :call_id, :workspace_id, :source, :prompt_id, :version_id, :revision_number,
        :run_id, :case_id, :consumer_key_id, :actor_id,
        :provider_config_id, :upstream_model, :outcome,
        :pinned, :fallback, :streaming,
        :input_tokens, :output_tokens, :usage_status,
        :cost, :currency, :price_row_id, :cost_status,
        :added_latency_ms, :upstream_duration_ms, :error_class,
        :created_at
    )
    """
)

INSERT_CALL_BODY = text(
    """
    INSERT INTO ledger.call_body (
        call_id, workspace_id, request_body, response_body, byte_size,
        expires_at, created_at
    ) VALUES (
        :call_id, :workspace_id, :request_body, :response_body, :byte_size,
        :expires_at, :created_at
    )
    """
)

#: A-103: the monthly aggregate is maintained inside the writer's own
#: transaction, so ``check_spend_ceiling`` reads one row instead of aggregating
#: the largest and fastest-growing table in the system. The composite primary
#: key is what makes this a single conflict-target upsert.
#:
#: ``call_count`` adds every record written for the month, including unpriced
#: and not-applicable ones. ``total_cost`` adds only priced costs, and stays
#: NULL until a priced record arrives — ``ck_workspace_spend_total_cost_carries_
#: currency`` requires a currency beside any total, and a total of zero standing
#: in for "nothing priced yet" would be the same lie this whole module refuses.
UPSERT_WORKSPACE_SPEND = text(
    """
    INSERT INTO ledger.workspace_spend (
        workspace_id, period_month, currency, total_cost, call_count
    ) VALUES (
        :workspace_id, :period_month, :currency, :total_cost, :call_count
    )
    ON CONFLICT (workspace_id, period_month) DO UPDATE SET
        call_count = ledger.workspace_spend.call_count + EXCLUDED.call_count,
        total_cost = CASE
            WHEN EXCLUDED.total_cost IS NULL THEN ledger.workspace_spend.total_cost
            ELSE COALESCE(ledger.workspace_spend.total_cost, 0) + EXCLUDED.total_cost
        END,
        currency   = COALESCE(ledger.workspace_spend.currency, EXCLUDED.currency),
        -- The one clock reading in this module, and the correct one: updated_at
        -- means "when the database saw this", the same thing its column default
        -- means. No pricing or retention value is derived from it.
        updated_at = clock_timestamp()
    """
)

READ_SPEND_CURRENCY = text(
    """
    SELECT currency FROM ledger.workspace_spend
    WHERE  workspace_id = :workspace_id AND period_month = :period_month
    """
)

#: CL-04's operational surface, as a projection over the stored encoding rather
#: than a second table. Served by ``ix_call_record_unpriced_worklist``, the
#: partial index over ``cost_status = 'unpriced'``.
#:
#: Phase 1 owes the encoding, the index and this query. Phase 2 owes the route
#: (``GET /api/v1/prices/unpriced``); none is built here. The tenant policy
#: supplies the workspace restriction, so there is no ``workspace_id`` predicate
#: to forget.
UNPRICED_WORKLIST = text(
    """
    SELECT provider_config_id,
           upstream_model,
           count(*)       AS unpriced_calls,
           min(created_at) AS since
    FROM   ledger.call_record
    WHERE  cost_status = 'unpriced'
    GROUP  BY provider_config_id, upstream_model
    ORDER  BY unpriced_calls DESC, upstream_model
    """
)


def _period_month(draft: CallRecordDraft) -> date:
    """The first day of the record's own month, in UTC.

    From the record's ``created_at``, never from wall clock — same reasoning as
    pricing. A drain catching up across a month boundary must not file
    September's calls under August.
    """
    at_utc = draft.created_at.astimezone(UTC)
    return date(at_utc.year, at_utc.month, 1)


async def write_records(
    session: AsyncSession,
    records: Sequence[CallRecordDraft],
    *,
    retention_window: timedelta = DEFAULT_RETENTION_WINDOW,
) -> WriteResult:
    """Price, stamp, insert and aggregate one workspace's batch. All or nothing.

    ``session`` must come from ``workspace_transaction()``. This function does
    not commit; the caller's context manager owns the transaction boundary, so a
    raise anywhere below leaves nothing written.

    Raises ``ValueError`` for a batch this encoding cannot represent: more than
    one workspace, more than one currency, an ``eval`` record carrying a body,
    or a priced record whose cost works out to zero.
    """
    if not records:
        return WriteResult()

    workspaces = {record.workspace_id for record in records}
    if len(workspaces) > 1:
        raise ValueError(
            f"batch spans {len(workspaces)} workspaces {sorted(workspaces)}; ADR-0040 groups by "
            "workspace and the session carries exactly one, so this batch is refused whole "
            "rather than written in part"
        )

    record_rows: list[dict] = []
    body_rows: list[dict] = []
    #: period_month -> [count, priced total or None, currency or None]
    months: dict[date, dict] = {}
    counts = {CostStatus.PRICED: 0, CostStatus.UNPRICED: 0, CostStatus.NOT_APPLICABLE: 0}

    for draft in records:
        if draft.source == Source.EVAL and draft.body is not None:
            raise ValueError(
                f"{draft.call_id} is source=eval and carries a body; no call_body row will ever "
                "exist for an eval call (A-055)"
            )

        cost: Decimal | None = None
        currency: str | None = None
        price_row_id: str | None = None

        if draft.usage_status is UsageStatus.UNKNOWN:
            # No usage object. There is nothing to price — not "nothing to
            # charge". The tokens stay NULL and the cost is not_applicable.
            cost_status = CostStatus.NOT_APPLICABLE
        else:
            price = await resolve_price(
                session,
                workspace_id=draft.workspace_id,
                provider_config_id=draft.provider_config_id,
                upstream_model=draft.upstream_model,
                at=draft.created_at,
            )
            if price is None:
                # No price in force at this call's own timestamp — whether
                # because no row exists or because every row is later. The two
                # are the same absence and are stored the same way.
                cost_status = CostStatus.UNPRICED
            else:
                cost_status = CostStatus.PRICED
                cost = compute_cost(draft.input_tokens or 0, draft.output_tokens or 0, price)
                currency = price.currency
                price_row_id = price.price_row_id
                if cost <= 0:
                    # Unrepresentable, and deliberately loud. A priced record
                    # with a zero cost is refused by
                    # ck_call_record_cost_is_never_zero, and the two honest
                    # answers here — a zero, or a silent downgrade to unpriced
                    # — are both a figure the encoding does not have. Surfacing
                    # it is the only option that does not invent one.
                    raise ValueError(
                        f"{draft.call_id} prices to {cost} against price row {price_row_id}: "
                        f"{draft.input_tokens} input and {draft.output_tokens} output tokens at "
                        f"{price.input_price_per_1k}/{price.output_price_per_1k} per 1k. A priced "
                        "record cannot record a cost of zero, and neither a zero nor a downgrade "
                        "to unpriced would be true"
                    )

        counts[cost_status] += 1

        record_rows.append(
            {
                "call_id": draft.call_id,
                "workspace_id": draft.workspace_id,
                "source": str(draft.source),
                "prompt_id": draft.prompt_id,
                "version_id": draft.version_id,
                "revision_number": draft.revision_number,
                "run_id": draft.run_id,
                "case_id": draft.case_id,
                "consumer_key_id": draft.consumer_key_id,
                "actor_id": draft.actor_id,
                "provider_config_id": draft.provider_config_id,
                "upstream_model": draft.upstream_model,
                "outcome": str(draft.outcome),
                "pinned": draft.pinned,
                "fallback": draft.fallback,
                "streaming": draft.streaming,
                "input_tokens": draft.input_tokens,
                "output_tokens": draft.output_tokens,
                "usage_status": str(draft.usage_status),
                "cost": cost,
                "currency": currency,
                "price_row_id": price_row_id,
                "cost_status": str(cost_status),
                "added_latency_ms": draft.added_latency_ms,
                "upstream_duration_ms": draft.upstream_duration_ms,
                "error_class": draft.error_class,
                "created_at": draft.created_at,
            }
        )

        if draft.body is not None:
            body_rows.append(
                {
                    "call_id": draft.call_id,
                    "workspace_id": draft.workspace_id,
                    "request_body": draft.body.request_body,
                    "response_body": draft.body.response_body,
                    "byte_size": draft.body.byte_size,
                    # From the record's OWN created_at. A backlogged record must
                    # not get a shorter life than a fresh one (A-106).
                    "expires_at": draft.created_at + retention_window,
                    "created_at": draft.created_at,
                }
            )

        bucket = months.setdefault(
            _period_month(draft), {"call_count": 0, "total_cost": None, "currency": None}
        )
        bucket["call_count"] += 1
        if cost is not None:
            if bucket["currency"] is None:
                bucket["currency"] = currency
            elif bucket["currency"] != currency:
                raise ValueError(
                    f"batch mixes currencies {bucket['currency']} and {currency}; a workspace uses "
                    "one currency and there is no conversion (A-107), so a sum across two of them "
                    "would be a number with no unit"
                )
            bucket["total_cost"] = (bucket["total_cost"] or Decimal(0)) + cost

    workspace_id = records[0].workspace_id

    await session.execute(INSERT_CALL_RECORD, record_rows)
    if body_rows:
        await session.execute(INSERT_CALL_BODY, body_rows)

    for period_month, bucket in months.items():
        if bucket["currency"] is not None:
            stored = (
                await session.execute(
                    READ_SPEND_CURRENCY,
                    {"workspace_id": workspace_id, "period_month": period_month},
                )
            ).scalar_one_or_none()
            if stored is not None and stored != bucket["currency"]:
                raise ValueError(
                    f"{workspace_id} already has spend recorded in {stored} for {period_month} and "
                    f"this batch is priced in {bucket['currency']}; A-107 forbids conversion, so "
                    "the two cannot be summed"
                )
        await session.execute(
            UPSERT_WORKSPACE_SPEND,
            {"workspace_id": workspace_id, "period_month": period_month, **bucket},
        )

    return WriteResult(
        priced=counts[CostStatus.PRICED],
        unpriced=counts[CostStatus.UNPRICED],
        unknown=counts[CostStatus.NOT_APPLICABLE],
        bodies_written=len(body_rows),
    )
