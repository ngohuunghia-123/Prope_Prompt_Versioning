"""INT-018's publish side: a bounded handoff, and a background publisher (D-25, D-21).

**``enqueue()`` never raises into its caller. Ever.** That is INT-018's whole
contract and it is why this module exists as something other than a call to
``exchange.publish``. The caller is the gateway's response path; a record that
cannot be recorded must not become a request that fails. Every branch below —
a full buffer, an unroutable publish, a nacked confirm, a confirm that never
arrives, a broker that is not running at all — returns normally.

**The caller's span is a ``put_nowait`` and nothing else** (D-25). Awaiting the
confirm inline was rejected: it puts a broker round trip inside a budget that is
achievable on a healthy loopback and not on a struggling broker. A background
task drains the handoff, publishes, awaits the confirm, and classifies what came
back.

**The Phase 2 gap this module creates deliberately, stated at the site.** On a
full handoff and on every failed confirm, this module COUNTS AND DROPS. There is
no direct-write fallback (CL-01, Phase 3) and no idempotent upsert on ``call_id``
(CL-02, Phase 3). ``/readyz`` ships its final semantics — the database alone
(D-16) — so for one phase there is a window in which the broker is down,
readiness is green, and records genuinely are lost.
``prope_call_ledger_metadata_dropped_total`` is what makes that window
measurable rather than merely admitted, and it will be non-zero in Phase 2.
:func:`_classify_publish_failure` is the exact line Phase 3's direct write goes
on.

**A-046.** No request body, response body, prompt body, fallback answer or
provider credential reaches a log line or a metric label from this module. The
log lines below carry a ``call_id``, a ``workspace_id`` and a ``reason`` from a
closed set — every one of them a member of
``prope.observability.LOGGABLE_FIELDS`` — and the envelope's body fields are
never read here at all. Redaction is that allow-list, positive; there is no
deny-list of field names anywhere in this module, because a deny-list passes the
first time a body travels on a field nobody thought to forbid.
"""

import asyncio
from datetime import UTC, datetime

import structlog
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractExchange
from aio_pika.exceptions import DeliveryError, PublishError
from pamqp.commands import Basic

from prope.broker.topology import WORK_QUEUE
from prope.call_ledger.domain import CallRecordDraft
from prope.call_ledger.envelope import CallRecordEnvelope
from prope.observability import (
    enqueued_total,
    metadata_dropped_total,
    publish_failed_total,
)

log = structlog.get_logger(__name__)

#: D-25's bound, and the arithmetic that chose it rather than a round number.
#:
#: The enqueue-to-durable target is p95 < 2 s at 50 rps, so two seconds of
#: traffic is 100 records. 512 sits comfortably above that — roughly ten seconds
#: of headroom at the stated rate — while still bounding what a hard kill loses
#: (A-139 already accepts that loss) and, more importantly, bounding memory.
#:
#: **Unbounded is refused, and the reason is not tidiness.** An unbounded
#: ``asyncio.Queue`` converts a broker outage into unbounded memory growth
#: inside the process serving the gateway's response path — the envelope carries
#: request and response bodies, so the growth is in units of payload, not units
#: of pointer. A bounded buffer that drops loudly is a worse day than a buffer
#: that holds everything; an unbounded one is a worse day than both, later.
HANDOFF_MAXSIZE = 512

#: The publish timeout. Long enough that a busy-but-alive broker is not called
#: dead, short enough that the handoff does not back up behind one stuck record.
PUBLISH_TIMEOUT_SECONDS = 5.0

_handoff: asyncio.Queue[CallRecordDraft] | None = None


def handoff() -> asyncio.Queue[CallRecordDraft]:
    """The process-wide handoff buffer, created on first use.

    Lazy rather than constructed at import: the queue belongs to a running
    event loop's process, and a module-level construction would bind it at
    import time in whichever context imported first.
    """
    global _handoff
    if _handoff is None:
        _handoff = asyncio.Queue(maxsize=HANDOFF_MAXSIZE)
    return _handoff


def reset_handoff() -> None:
    """Drop the handoff so the next call builds a fresh one. Test seam only.

    Nothing on the production path calls this. It exists because a
    process-wide buffer that survives between tests is a test reading the
    previous test's backlog.
    """
    global _handoff
    _handoff = None


def enqueue(record: CallRecordDraft) -> None:
    """Hand a call record off to be published. Returns immediately. Never raises.

    This is the whole of the caller's span (D-25): one ``put_nowait`` and a
    return. It is deliberately **synchronous** — there is nothing to await, and
    a coroutine would invite a caller to await something.

    A full buffer is counted and dropped, not blocked on and not grown. Both
    ``prope_call_ledger_metadata_dropped_total`` and
    ``prope_call_ledger_enqueued_total{outcome="dropped"}`` increment: the
    second says a record was offered and refused, the first says it will never
    reach ``ledger.call_record``. A buffer-full drop is not one of
    ``publish_failed_total``'s three reasons — nothing was published — so that
    counter is untouched here.
    """
    try:
        handoff().put_nowait(record)
    except asyncio.QueueFull:
        metadata_dropped_total.inc()
        enqueued_total.labels(source=str(record.source), outcome="dropped").inc()
        log.warning(
            "call_ledger.handoff_full",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason="handoff_full",
        )
        return
    except Exception:
        # INT-018 says never, and never includes the failure nobody predicted.
        # A raise here would surface inside the gateway's response path, which
        # is the one outcome this module exists to make impossible.
        metadata_dropped_total.inc()
        log.warning(
            "call_ledger.handoff_failed",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason="handoff_failed",
        )
        return

    enqueued_total.labels(source=str(record.source), outcome="accepted").inc()


def _classify_publish_failure(error: BaseException) -> str:
    """One of ``unroutable`` | ``nacked`` | ``timeout``. The set is closed.

    The lock file declares exactly these three values for
    ``prope_call_ledger_publish_failed_total``'s ``reason`` label, and this
    function is the only place a value is chosen, so a fourth cannot appear by
    accident.

    **The mapping is against aiormq's real behaviour, not against the shape the
    plan sketched.** A returned mandatory message surfaces as ``PublishError``,
    whose constructor asserts ``message.delivery`` is a ``Basic.Return`` — that
    is ``unroutable``. A ``basic.nack`` surfaces as its PARENT class,
    ``DeliveryError``, carrying the ``Basic.Nack`` frame — that is ``nacked``.
    Both are ``DeliveryError`` by ``isinstance``, so the subclass has to be
    tested first; classifying every ``DeliveryError`` as ``unroutable`` would
    silently label every overflow rejection as a routing problem, and overflow
    rejection is the exact signal ``x-overflow: reject-publish-dlx`` was chosen
    to produce.
    """
    if isinstance(error, PublishError):
        return "unroutable"
    if isinstance(error, DeliveryError):
        return "nacked"
    return "timeout"


async def publish_record(exchange: AbstractExchange, record: CallRecordDraft) -> bool:
    """Publish one record and await its confirm. Returns whether it was acked.

    Persistent (ADR-0028) and ``mandatory=True``: without ``mandatory`` an
    unroutable publish is acked and discarded, and ``unroutable`` would be an
    unreachable label.

    **Phase 3's direct-write fallback goes on the failure branch below.** Not
    beside it, not in the caller: at the point where this function has
    established that this specific record did not reach the broker and knows
    which of the three reasons applies. CL-01 replaces the ``return False`` with
    a write through ``write_records``, and CL-02's upsert is what makes that
    write safe against a confirm that was lost rather than refused.
    """
    envelope = CallRecordEnvelope.from_draft(record, occurred_at=datetime.now(UTC))
    message = Message(
        envelope.model_dump_json().encode("utf-8"),
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type="application/json",
    )

    try:
        confirmation = await exchange.publish(
            message,
            routing_key=WORK_QUEUE,
            mandatory=True,
            timeout=PUBLISH_TIMEOUT_SECONDS,
        )
    except (DeliveryError, TimeoutError) as error:
        reason = _classify_publish_failure(error)
        publish_failed_total.labels(reason=reason).inc()
        metadata_dropped_total.inc()
        log.warning(
            "call_ledger.publish_failed",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason=reason,
            queue=WORK_QUEUE,
        )
        return False
    except Exception:
        # A closed channel, a dead connection, a broker that was never running.
        # Not one of the three declared reasons — nothing was confirmed or
        # refused, so ``publish_failed_total`` stays untouched and its label set
        # stays closed at three. The record is still lost, so the drop counter
        # is not.
        metadata_dropped_total.inc()
        log.warning(
            "call_ledger.publish_unavailable",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason="broker_unavailable",
            queue=WORK_QUEUE,
        )
        return False

    if not isinstance(confirmation, Basic.Ack):
        # Defence in depth, and it earns its place. On a channel opened by
        # ``publisher_channel`` this branch is unreachable: confirms raise, so
        # a return here is an ack. On a channel opened WITHOUT
        # ``on_return_raises=True`` — aio-pika's default — an unroutable
        # publish resolves successfully carrying a ``DeliveredMessage`` whose
        # ``delivery`` is a ``Basic.Return``, and a publisher that only caught
        # exceptions would count it as delivered. So the shape is inspected
        # rather than assumed, and a returned message is classified as what it
        # is.
        reason = (
            "unroutable"
            if isinstance(getattr(confirmation, "delivery", None), Basic.Return)
            else "nacked"
        )
        publish_failed_total.labels(reason=reason).inc()
        metadata_dropped_total.inc()
        log.warning(
            "call_ledger.publish_failed",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason=reason,
            queue=WORK_QUEUE,
        )
        return False

    return True


async def run_publisher(
    exchange: AbstractExchange,
    stopping: asyncio.Event,
) -> None:
    """Drain the handoff onto the broker until ``stopping`` is set.

    ``stopping`` is a directly-settable ``asyncio.Event`` rather than a signal
    handler, because ``loop.add_signal_handler`` is not implemented on Windows
    and the development host is Windows. The signal wiring lands with the
    supervisor in plan 02-03; this shape is drivable from a test on any
    platform.

    Nothing raised by a single record's publish escapes this loop. A publisher
    that dies on one bad record takes the whole handoff with it, which would
    turn a one-record loss into an outage.
    """
    queue = handoff()
    while not stopping.is_set():
        try:
            record = await asyncio.wait_for(queue.get(), timeout=0.1)
        except TimeoutError:
            continue

        try:
            await publish_record(exchange, record)
        finally:
            queue.task_done()
