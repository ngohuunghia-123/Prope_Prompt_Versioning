"""ADR-0041's inline direct write: the broker refused, so PostgreSQL takes it.

**The decision this module implements, in the ADR's own words:** on a failed
publish, *"write the metadata row directly to PostgreSQL inline"*. That is CL-01,
and after it the durability claim moves from the broker to the pair — losing a
record requires losing two stores at once, and
``prope_call_ledger_metadata_dropped_total`` is the counter that says so.

**One record, one transaction** (D-27). This writes the single record that just
failed to publish and returns. It does not drain the handoff, does not group and
does not batch. The arithmetic agrees with the ADR's wording rather than merely
permitting it: a single-record transaction against a local PostgreSQL costs on
the order of 1.5 ms, so this sustains roughly 650 records/sec against a
steady-state 50 rps — thirteen times the rate it has to absorb. That is why the
handoff does not fill during a broker outage, and why SC1's thousand calls need
no faster shape.

**Rejected: draining and batching by workspace, the way the drain does.** It buys
throughput the arithmetic says is not needed, and it costs a duplicate of
``drain._retry_group_one_at_a_time`` inside ``app`` — because ``write_records`` is
all-or-nothing, so a batched fallback needs the same one-at-a-time retry ladder.
**That is ADR-0041's own argument against the spill file, turned on this module:
the mechanism most likely to be wrong is the one exercised least, and this one
only ever runs during an incident.** One record per transaction also means one
record's refusal loses exactly that record, so ``metadata_dropped_total``
increments by exactly one and needs no reconciliation.

**It writes no SQL of its own**, exactly like ``seams.price_usage``: take a
sessionmaker, open the tenant transaction yourself, convert nothing, call
``write_records``. There is one implementation of the write path on purpose —
pricing at the record's own ``created_at``, the three cost states, the
``expires_at`` stamp and the monthly aggregate cannot be allowed to drift between
the drain and this module. ADR-0040 is obeyed for free: a single record is a
single workspace.

**Metadata only, and therefore no settings query — structurally, not by
discipline** (D-28). The draft is rebuilt with ``body=None`` **before** it reaches
``write_records``. ``expires_at`` is stamped only when a ``call_body`` row is
built, so a path that writes no body never consults ``ledger.workspace_retention``
and ``write_records``' ``retention_window`` default is never exercised here. That
is what makes D-11's promise — *"Phase 3's direct-write fallback inherits no
settings query"* — a property of the code rather than a rule somebody has to
remember. Any plan that reaches for the retention resolver in ``app`` has taken a
wrong turn upstream.

**It never raises.** INT-018's contract reaches this far: this runs inside the
supervised publisher task, and a raise here is what D-32's supervision exists to
survive rather than what it exists to expect. A refusal by the database is caught,
counted on ``metadata_dropped_total`` and logged once.

**This module reads a clock, and it is the one place in it that may.** The
repository's convention is that ``now`` is an argument (``retention.py``,
``writer.py``) and that a module with a genuine need names its single site
(``worker._utc_now``, ``api._utc_now``). The need here is
``prope_call_ledger_write_lag_seconds``, which is declared *"enqueue -> durable"*
— the direct write IS a durable moment, so it observes the same interval the drain
does, from the ``occurred_at`` its caller stamped.

**A-046.** This module handles a body-carrying record and logs a drop, so it needs
the declaration more than most. No request body, response body, prompt body,
fallback answer or provider credential reaches a log line or a metric label from
here. The one log line carries a ``call_id``, a ``workspace_id`` and an
exception's **class** — never its message, which at this depth can quote a row or
a connection string.
"""

from dataclasses import replace
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.enqueue import FallbackWriter, HandoffItem
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from prope.observability import (
    BODY_DROP_REASON_FALLBACK,
    body_dropped_total,
    fallback_direct_write_total,
    metadata_dropped_total,
    write_lag_seconds,
)

log = structlog.get_logger(__name__)


def build_fallback_writer(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> FallbackWriter:
    """Bind ADR-0041's direct write to a session factory. Returns the callable.

    Built once, at the composition root (D-26), and handed to ``run_publisher``
    and ``publish_record`` as a required keyword argument. The consequence
    ADR-0041 names explicitly: **``app`` acquires a database write path it did not
    have**, and every record it writes carries a ``workspace_id`` that decides
    which tenant's rows the transaction may touch — which is why the write goes
    through ``workspace_transaction`` unchanged, with its bound ``set_config`` and
    the policy's ``WITH CHECK`` refusing a mis-stamped row at the engine.
    """

    async def write_directly(item: HandoffItem) -> None:
        record = item.draft

        # D-28: metadata only, rebuilt BEFORE the write rather than after. The
        # order is what makes "this path never reads a setting" structural: with
        # no body there is nothing for a retention window to be applied to.
        # ``CallRecordDraft`` is frozen, so ``replace`` is the tool and mutation
        # would raise ``FrozenInstanceError``.
        had_body = record.body is not None
        metadata_only = replace(record, body=None) if had_body else record

        try:
            async with workspace_transaction(
                sessionmaker, metadata_only.workspace_id
            ) as session:
                await write_records(session, [metadata_only])
        except Exception as error:
            # The broker was gone AND the database was gone. **This is the event
            # ADR-0041 says ``metadata_dropped_total`` now means**, and the only
            # page in this module. ``Exception`` and never ``BaseException``: a
            # shutdown must still cancel this task rather than being counted as a
            # durability failure.
            metadata_dropped_total.inc()
            log.warning(
                "call_ledger.fallback_failed",
                call_id=record.call_id,
                workspace_id=record.workspace_id,
                reason=type(error).__name__,
            )
            return

        fallback_direct_write_total.inc()

        # Clamped, and the clamp is not defensive tidiness: ``occurred_at`` is
        # stamped in ``app`` and this clock is read wherever the fallback runs.
        # ``prometheus_client`` accepts a negative observation without complaint,
        # decrementing ``_sum`` while incrementing ``_count``, which makes
        # ``rate(_sum[5m])`` negative and any average-latency panel built on it
        # nonsense. Stated positively: this metric is only meaningful because
        # ``app`` and ``worker`` share a host (ADR-0033).
        lag = (datetime.now(UTC) - item.occurred_at).total_seconds()
        write_lag_seconds.observe(max(0.0, lag))

        if had_body:
            # Once per RECORD, never once per body field: AC-1's stated equality
            # is "body_dropped_total equals the number missing from call_body",
            # and one increment per dropped pair is what makes that hold.
            body_dropped_total.labels(reason=BODY_DROP_REASON_FALLBACK).inc()

    return write_directly
