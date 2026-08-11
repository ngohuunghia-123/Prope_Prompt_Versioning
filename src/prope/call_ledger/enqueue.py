"""INT-018's publish side: a bounded handoff, a publisher, and ADR-0041's fallback.

**``enqueue()`` never raises into its caller. Ever.** That is INT-018's whole
contract and it is why this module exists as something other than a call to
``exchange.publish``. The caller is the gateway's response path; a record that
cannot be recorded must not become a request that fails. Every branch below —
a full buffer, a handoff that has been shut down, an unroutable publish, a nacked
confirm, a confirm that never arrives, a broker that is not running at all —
returns normally.

**The caller's span is a ``put_nowait`` and nothing else** (D-25). Awaiting the
confirm inline was rejected: it puts a broker round trip inside a budget that is
achievable on a healthy loopback and not on a struggling broker. A background
task drains the handoff, publishes, awaits the confirm, and classifies what came
back.

**What this module now guarantees, and what it still does not.** Every failure
site in :func:`publish_record` calls an injected ``FallbackWriter`` (CL-01,
ADR-0041, D-26), so a record the broker would not take is written straight to
PostgreSQL with its body dropped and counted, and
``prope_call_ledger_metadata_dropped_total`` means what ADR-0041 says it means:
**both** stores were gone. What has NOT changed is the handoff's bound — 512
records, and a full handoff is still the one place inside this module where a
record is genuinely lost. What is still missing is the idempotent upsert on
``call_id`` that makes a REDELIVERED record safe: a timed-out confirm means the
broker did receive the message and the fallback wrote it anyway, so the same
record arrives twice and the second arrival raises an ``IntegrityError`` the
drain dead-letters. That is CL-02 and plan 03-02, and until it lands a timed-out
confirm is survivable rather than safe.

**The database is never imported here, and that is a property rather than a
preference** (D-26). This module's contract is *never raises, never blocks*, and
a ``workspace_transaction`` import sitting in it is an invitation to put a write
inside ``enqueue()`` — which is CL-12's budget. The fallback arrives as a
callable bound at the composition root; ``prope.call_ledger.fallback`` is what
holds the session factory.

**A-046.** No request body, response body, prompt body, fallback answer or
provider credential reaches a log line or a metric label from this module. The
log lines below carry a ``call_id``, a ``workspace_id``, a ``reason`` from a
closed set and — on the shutdown line — a ``group_size``, every one of them a
member of ``prope.observability.LOGGABLE_FIELDS``, and the envelope's body fields
are never read here at all. Redaction is that allow-list, positive; there is no
deny-list of field names anywhere in this module, because a deny-list passes the
first time a body travels on a field nobody thought to forbid.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial

import structlog
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractExchange
from aio_pika.exceptions import DeliveryError, PublishError
from pamqp.commands import Basic

from prope.broker.topology import WORK_QUEUE
from prope.call_ledger.domain import CallRecordDraft
from prope.call_ledger.envelope import CallRecordEnvelope
from prope.observability import (
    BODY_DROP_REASON_OVERSIZE,
    body_dropped_total,
    enqueue_duration_seconds,
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

#: How long a job body waits on an empty handoff before checking ``stopping``
#: again. Not a tuning parameter — it is the shutdown latency of an idle
#: publisher, and it is short because an idle publisher is what a deploy
#: interrupts.
HANDOFF_POLL_SECONDS = 0.1

#: D-31's stop deadline: how long :func:`drain_handoff_on_stop` will spend
#: emptying the handoff before it counts whatever is left.
#:
#: **``app.PUBLISHER_STOP_TIMEOUT_SECONDS`` is DERIVED from this**, and the
#: derivation is the load-bearing half. ``_stop_publisher`` does
#: ``asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)`` and
#: then cancels; if the inner deadline ever equalled or exceeded the outer wait,
#: the cancel would land while the drain was still working and the remainder
#: count would never run — which reproduces CR-02 with more machinery. The
#: relationship is invisible from either file, and a comment in one module about a
#: constant in another is the definition of a fact nobody maintains. The import
#: direction settles which is primary: ``app`` already imports this module and the
#: reverse would be a cycle.
#:
#: **The arithmetic, stated on the branch that actually runs.** The ordinary
#: composition is the PUBLISH branch: ``run_publisher`` binds
#: :func:`publish_record`, which awaits ``exchange.publish(...,
#: timeout=PUBLISH_TIMEOUT_SECONDS)`` — **5.0 s**. A broker that has accepted the
#: connection and stopped answering confirms therefore holds ONE record for longer
#: than this whole 3.0 s deadline and longer than ``app``'s whole 5.0 s outer wait,
#: and a full 512-record handoff for up to ``512 × 5.0 s`` ≈ **43 minutes**. The
#: fallback branch is unbounded in kind rather than merely slow:
#: ``build_fallback_writer``'s ``workspace_transaction`` + ``write_records`` has no
#: timeout at all, and a degraded database during shutdown is exactly the state in
#: which records are still sitting in the buffer. D-27's 1.5 ms-per-record figure —
#: 512 records in roughly 0.77 s — prices the fallback branch against a HEALTHY
#: local PostgreSQL; it is the good day, and an earlier revision of this paragraph
#: quoted it as if it were the bound. It is not.
#:
#: **Which is why the deadline is enforced PER ITEM and not only between items**
#: (CR-03). ``while loop.time() < deadline`` gates entry to an iteration; it does
#: not interrupt one, so on its own it bounds when the loop stops TAKING work and
#: not when it RETURNS — and an item taken at 2.99 s may return at any later time
#: whatsoever. :func:`drain_handoff_on_stop` therefore wraps each item in
#: ``asyncio.wait_for(..., timeout=remaining_budget)``. With that bound the loop
#: returns inside this deadline whatever the broker and the database are doing,
#: which is what makes ``app``'s +2.0 s margin a margin rather than a hope.
#:
#: **The honest failure mode** is truncation, not a missed count: whatever the
#: deadline could not reach is counted on ``metadata_dropped_total`` and named on
#: ``call_ledger.handoff_abandoned``, which is the correct behaviour rather than a
#: silent loss. And because that count lives in a ``finally``, a cancel that lands
#: mid-drain anyway — the outcome this derivation exists to prevent — counts the
#: remainder rather than skipping it. The derivation is necessary; it is not what
#: the guarantee rests on.
#:
#: A tunable judgement, not a repo decision, recorded so that changing it is a
#: visible act. Unvalidated at real scale, like every number of this kind here.
HANDOFF_DRAIN_DEADLINE_SECONDS = 3.0

#: D-29's per-body cap: 256 KiB over the request and response pair together,
#: enforced inside :func:`enqueue` before the ``put_nowait``.
#:
#: **What it is derived from.** ADR-0033 sizes the host against *"roughly 10 KB
#: per call"*, so 256 KiB is twenty-six times the stated average and about 64k
#: tokens of UTF-8 — above the context window of the models a pilot will use,
#: which makes a body above it an asset or a base64 blob rather than a
#: conversation. The lock file's eighth failure mode requires a cap and states no
#: number anywhere, so the number is argued here.
#:
#: **The arithmetic that matters is disk, not memory.** The work queue's declared
#: bound is 1,000,000 *messages* with **no byte bound at all**, so the real ceiling
#: on broker disk is the 24-hour TTL: 24 hours of ADR-0033's stated 10k calls/day
#: at the cap is at most 2.5 GB, inside an 80 GB host that already carries
#: ``call_body`` at roughly 3 GB/month.
#:
#: **What it does not bind.** It bounds ONE MESSAGE, not the queue and not the
#: handoff. A-149's message-count bound is the queue's, ``HANDOFF_MAXSIZE`` is the
#: buffer's, and neither becomes a byte bound because of this constant. That
#: residue — a queue of a million capped messages is still 256 GB on paper — is
#: ``OQ-025``'s subject.
#:
#: **Rejected: 64 KiB.** Roughly 16k tokens is inside an ordinary long response,
#: so ``body_dropped_total{reason="oversize"}`` would become a normal-traffic
#: counter rather than an anomaly signal. **Rejected: no cap.** Nothing else on
#: the path bounds bytes, and ``x-max-length-bytes`` cannot be added to the queue
#: now without D-23's delete-and-redeclare in every environment that has run.
#:
#: A tunable judgement, not a repo decision, recorded so that changing it is a
#: visible act. Unvalidated at real scale, like every number of this kind here.
MAX_BODY_BYTES = 256 * 1024


@dataclass(frozen=True, slots=True)
class HandoffItem:
    """One record and the instant its caller handed it over.

    A frozen dataclass rather than a tuple. A tuple is one character shorter and
    turns every unpack site into a positional guess, and this pair now travels to
    three places — the publisher, ``CallRecordEnvelope.from_draft``, and the
    fallback — which is one more than a tuple survives comfortably.

    ``occurred_at`` is stamped in :func:`enqueue` (D-41) and not in
    :func:`publish_record`, so ``prope_call_ledger_write_lag_seconds`` measures
    the interval it is declared to measure.
    """

    draft: CallRecordDraft
    occurred_at: datetime


#: What a fallback must look like: awaited with ONE POSITIONAL ARGUMENT, the
#: :class:`HandoffItem` that failed to publish — the draft AND the ``occurred_at``
#: stamped when the caller handed it over, because the direct write is also an
#: "enqueue -> durable" interval and observes the same ``write_lag_seconds``.
#:
#: **It never raises.** INT-018's contract reaches this far: this runs inside the
#: publisher task, and a raise here is what D-32's supervision exists to survive
#: rather than what it exists to expect.
#:
#: The one-positional-argument sentence is not decoration. ``drain.py``'s
#: ``RetentionResolver`` and ``worker.py``'s ``WorkspaceEnumerator`` both spend a
#: paragraph on the last time a resolver's arity was got wrong at a composition
#: root, and that precedent is exactly what D-26's *required keyword argument with
#: no default* is guarding against.
#:
#: Declared HERE and imported by ``prope.call_ledger.fallback``, so the dependency
#: between the two modules runs one way only. It is also the more honest home: an
#: alias for what this module REQUIRES of its caller belongs to this module.
FallbackWriter = Callable[[HandoffItem], Awaitable[None]]

_handoff: asyncio.Queue[HandoffItem] | None = None


def handoff() -> asyncio.Queue[HandoffItem]:
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
    """Drop the handoff so the next call builds a fresh one.

    **The production caller is ``prope.app``'s lifespan, in its ``finally``,
    after the publisher has stopped.** That is not a test seam creeping into
    production: :func:`drain_handoff_on_stop` calls ``queue.shutdown()``, which is
    one-way for the queue object, and ``handoff()`` caches in a module global —
    so without this call every ``enqueue()`` after a lifespan ends would take the
    ``QueueShutDown`` branch and count a drop, forever. The handoff belongs to a
    process's *serving lifetime*, and a lifespan that ends is that boundary.

    It is also the test seam it has always been: a process-wide buffer that
    survives between tests is a test reading the previous test's backlog.
    """
    global _handoff
    _handoff = None


def _sized_or_dropped(record: CallRecordDraft) -> CallRecordDraft:
    """Apply D-29's byte cap. Returns the record to enqueue. **Never raises.**

    The size is computed HERE, from bytes this module encodes itself, and it
    **overwrites** ``CallBodyDraft.byte_size`` — which is caller-supplied and
    ``int | None``. A cap enforced from a figure the capped party supplies is not
    a cap.

    Enforced in ``enqueue()`` rather than in the publisher because the handoff's
    own docstring says the growth is *"in units of payload, not units of
    pointer"*: a cap applied in the background publisher lets 512 unbounded bodies
    into memory first.

    **Over the cap, the record continues with ``body=None``.** It is never
    dropped for its body's sake — metadata is the thing this phase exists to keep
    (D-29) — so this is a count-and-log, not one of ``writer.py``'s refusals.

    ``CallRecordDraft`` and ``CallBodyDraft`` are both frozen, so
    ``dataclasses.replace`` is the tool and mutation would raise.
    """
    body = record.body
    if body is None:
        return record

    try:
        size = len((body.request_body or "").encode("utf-8")) + len(
            (body.response_body or "").encode("utf-8")
        )
    except Exception:
        # A ``str.encode()`` on a caller-supplied string is exactly the failure
        # nobody predicted that ``enqueue()``'s bare handler is written for — a
        # lone surrogate is the reachable case. A body whose size cannot be
        # computed cannot be admitted under a byte cap, so it takes the cap's own
        # branch and the cap's own reason rather than inventing a third value one
        # line away from the second.
        body_dropped_total.labels(reason=BODY_DROP_REASON_OVERSIZE).inc()
        log.warning(
            "call_ledger.body_unmeasurable",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason=BODY_DROP_REASON_OVERSIZE,
        )
        return replace(record, body=None)

    if size > MAX_BODY_BYTES:
        body_dropped_total.labels(reason=BODY_DROP_REASON_OVERSIZE).inc()
        log.warning(
            "call_ledger.body_oversize",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason=BODY_DROP_REASON_OVERSIZE,
        )
        return replace(record, body=None)

    return replace(record, body=replace(body, byte_size=size))


def enqueue(record: CallRecordDraft) -> None:
    """Hand a call record off to be published. Returns immediately. Never raises.

    This is the whole of the caller's span (D-25): a body sizing, a clock read,
    one ``put_nowait`` and a return. It is deliberately **synchronous** — there is
    nothing to await, and a coroutine would invite a caller to await something.
    The whole of it is timed onto
    ``prope_call_ledger_enqueue_duration_seconds{source}``, because CL-12's claim
    is about what the caller waits for and a measurement that excluded the encode
    would exclude the largest term in it. ``perf_counter`` rather than
    ``monotonic`` for unambiguity rather than for resolution: Python 3.13 moved
    ``monotonic()`` on Windows to ``QueryPerformanceCounter``, so the classic
    15.6 ms-resolution objection is obsolete on the pinned interpreter, and the
    remaining reason to prefer ``perf_counter`` is that its contract says
    "highest available resolution" out loud.

    **This function reads a clock, and it is call-ledger's THIRD sanctioned clock
    site.** The convention it is breaking is real and is written down in four
    places — ``retention.py`` (*"``now`` is an argument and never a clock read"*),
    ``writer.py`` (*"Nothing in this module reads a clock"*), and ``worker._utc_now``
    / ``api._utc_now`` (both *"the one clock read in this process/module, in the
    one place that may read it"*). The reason is
    ``prope_call_ledger_write_lag_seconds``, which is declared *"enqueue ->
    durable"*: stamping ``occurred_at`` at the publish moment instead would put
    the handoff dwell — the one interval the fallback exists to protect — outside
    the one metric named after it, and the record's own ``created_at`` is not the
    alternative, because that is the call's time, before the response was even
    flushed. The cost is on the order of a hundred nanoseconds inside a 1 ms
    budget.

    **``occurred_at`` is a registered field and its MEANING moves with the
    stamp.** ``interfaces.md`` lists it under INT-018's *"Envelope carries (A-142
    §5)"*. Its shape does not change — same name, same type, same presence, so
    A-142's additive-only rule is untouched and no other module's code moves — but
    it now means *"when the caller handed the record over"* rather than *"when the
    publisher published it"*, and INT-018 is *"the only shape in Prope that can be
    in flight across a deploy"*. Phases 19–21's gateway inherits that meaning, so
    it is written down here rather than left to be inferred from a diff.

    A full buffer is counted and dropped, not blocked on and not grown. Both
    ``prope_call_ledger_metadata_dropped_total`` and
    ``prope_call_ledger_enqueued_total{outcome="dropped"}`` increment: the
    second says a record was offered and refused, the first says it will never
    reach ``ledger.call_record``. A buffer-full drop is not one of
    ``publish_failed_total``'s three reasons — nothing was published — so that
    counter is untouched here.
    """
    started = time.perf_counter()
    try:
        record = _sized_or_dropped(record)
        item = HandoffItem(draft=record, occurred_at=datetime.now(UTC))

        try:
            handoff().put_nowait(item)
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
        except asyncio.QueueShutDown:
            # The door is shut: ``drain_handoff_on_stop`` has run and this process
            # is stopping. Its own branch rather than the bare handler below,
            # because ``QueueShutDown`` derives from ``Exception`` and would
            # otherwise log ``reason="handoff_failed"`` — which reads as a bug
            # rather than as a deploy. The record is genuinely lost either way, so
            # it is counted exactly like the full-buffer case.
            metadata_dropped_total.inc()
            enqueued_total.labels(source=str(record.source), outcome="dropped").inc()
            log.warning(
                "call_ledger.handoff_shut_down",
                call_id=record.call_id,
                workspace_id=record.workspace_id,
                reason="shutting_down",
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
    finally:
        enqueue_duration_seconds.labels(source=str(record.source)).observe(
            time.perf_counter() - started
        )


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


async def publish_record(
    exchange: AbstractExchange,
    item: HandoffItem,
    *,
    fallback: FallbackWriter,
) -> bool:
    """Publish one record and await its confirm. Returns whether it was acked.

    Persistent (ADR-0028) and ``mandatory=True``: without ``mandatory`` an
    unroutable publish is acked and discarded, and ``unroutable`` would be an
    unreachable label.

    **ADR-0041's direct-write fallback is on the failure branches below, and this
    function is where it belongs.** Not beside it, not in the caller: at the point
    where this function has established that this specific record did not reach
    the broker. All three ``return False`` sites call it, which is D-26's four
    failure cases — ``unroutable``, ``nacked`` and ``timeout`` through
    :func:`_classify_publish_failure`, plus the bare ``except Exception`` that
    catches a closed channel, a dead connection or a broker that was never
    running. **That last one is the mundane case**, the one an ordinary
    ``docker compose up -d`` produces and the one ADR-0041 was written about;
    omitting it would build the fallback for the rare failures and not for the
    ordinary one.

    ``fallback`` is a **required keyword argument with no default** (D-26). An
    optional parameter defaulting to ``None`` means a process composed without a
    fallback loses records silently, and there is exactly one composition root, so
    there is nothing to make it optional for.

    **The fallback is injected rather than imported**, and the reason is at the
    top of this module: this module gains no database import, because its contract
    is *never raises, never blocks* and a ``workspace_transaction`` import sitting
    in it is an invitation to write inside ``enqueue()``.

    ``metadata_dropped_total`` is **not** incremented at any of the three sites
    any more. The record is no longer lost, it is falling back; the counter that
    says a record exists nowhere is the fallback's own, on the branch where the
    database refused it too.
    """
    record = item.draft
    envelope = CallRecordEnvelope.from_draft(record, occurred_at=item.occurred_at)
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
        log.warning(
            "call_ledger.publish_failed",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason=reason,
            queue=WORK_QUEUE,
        )
        await fallback(item)
        return False
    except Exception:
        # A closed channel, a dead connection, a broker that was never running.
        # Not one of the three declared reasons — nothing was confirmed or
        # refused, so ``publish_failed_total`` stays untouched and its label set
        # stays closed at three. The record is not lost: it falls back.
        log.warning(
            "call_ledger.publish_unavailable",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason="broker_unavailable",
            queue=WORK_QUEUE,
        )
        await fallback(item)
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
        log.warning(
            "call_ledger.publish_failed",
            call_id=record.call_id,
            workspace_id=record.workspace_id,
            reason=reason,
            queue=WORK_QUEUE,
        )
        await fallback(item)
        return False

    return True


async def publish_or_fall_back(
    item: HandoffItem,
    publish: Callable[[HandoffItem], Awaitable[bool]] | None,
    fallback: FallbackWriter,
) -> None:
    """One item's whole handling, with the catch that lets nothing out.

    ``publish`` is ``None`` on the fallback-only branch — the process started
    against a broker that was not there, so there is no exchange and nothing to
    try first. Otherwise it is a bound :func:`publish_record`, which has already
    called ``fallback`` and counted by the time it returns ``False``; the return
    value is therefore information and not an instruction.

    **The catch is here, once, rather than three times inside
    :func:`publish_record`**, and the reason is that one catch covering the
    publish and the fallback together is one place a future reader must keep
    correct. The fallback's own internal handler already counts the ordinary
    refusal — a database that would not answer — so this outer catch is for the
    failure nobody predicted, and it is D-30's second surviving
    ``metadata_dropped_total`` site.

    ``run_publisher``'s promise is that nothing raised by a single record's
    publish escapes its loop: a publisher that dies on one bad record takes the
    whole handoff with it, which would turn a one-record loss into an outage.
    ``BaseException`` is deliberately not caught — a shutdown must still cancel
    this task rather than being counted as a durability failure.
    """
    try:
        if publish is None:
            await fallback(item)
        else:
            await publish(item)
    except Exception as error:
        metadata_dropped_total.inc()
        log.warning(
            "call_ledger.publish_abandoned",
            call_id=item.draft.call_id,
            workspace_id=item.draft.workspace_id,
            reason=type(error).__name__,
        )


async def drain_handoff_on_stop(
    publish: Callable[[HandoffItem], Awaitable[bool]] | None,
    fallback: FallbackWriter,
) -> None:
    """CR-02: close the door, empty the room, count what would not fit.

    Written once and reached from two job bodies — ``run_publisher`` on the
    success branch and ``app``'s fallback-only job on the failure branch. The most
    literal reading of D-31 ("after ``run_publisher``'s loop") would leave a
    process that started against a dead broker with no shutdown drain at all,
    which is CR-02 reopened on the exact branch SC1 calls the most ordinary
    provocation.

    **``queue.shutdown()`` closes a hole that counting alone would leave open.**
    Python 3.13's ``shutdown(immediate=False)`` makes ``put`` raise at once while
    letting ``get`` keep returning until the queue is empty. Without it, every
    record ``enqueue()`` accepted between ``stopping.set()`` and the publisher's
    last ``get`` would be a record that will never be published *and* is not in
    the remainder count, because it arrived after the count was taken.

    **This runs at most once per process.** ``shutdown()`` is one-way for the
    queue object and ``handoff()`` caches in a module global, so a second call
    would drain an already-shut queue. It is guarded by its callers' ``while not
    stopping.is_set()`` loops, which end exactly once — and ``prope.app``'s
    lifespan calls :func:`reset_handoff` afterwards, so the next serving lifetime
    starts with a fresh buffer rather than a shut one.

    Whatever the deadline could not reach is counted once per record and named in
    **one** log line. ``reason`` and ``group_size`` are both already members of
    ``prope.observability.LOGGABLE_FIELDS``, so no new log field is introduced.

    **The count is STRUCTURAL, not positional** (CR-03). It lives in a ``finally``
    because the caller cancels this task when its own wait expires —
    ``_stop_publisher`` does ``asyncio.wait_for(publisher, timeout=...)``, which
    cancels — and a ``CancelledError`` is a ``BaseException`` rather than an
    ``Exception``, so it is caught by nothing on the way out.
    :func:`publish_or_fall_back` deliberately does not catch it. A count that sat
    after the loop was therefore a count that a cancel skipped, which reproduced
    CR-02 *inside the function written to close it*: twenty records buffered,
    nineteen still in the queue, ``metadata_dropped_total`` unmoved at zero.

    **Each item is bounded by the REMAINING budget**, for the reason
    ``HANDOFF_DRAIN_DEADLINE_SECONDS`` now argues at length: the loop's own
    deadline gates entry to an iteration and does not interrupt one, so without a
    per-item bound it says when the loop stops TAKING work and not when it
    RETURNS — and a single publish is bounded at ``PUBLISH_TIMEOUT_SECONDS``
    (5.0 s, longer than both this deadline and ``app``'s outer wait) while the
    fallback's transaction is bounded by nothing at all.
    """
    queue = handoff()
    queue.shutdown()

    loop = asyncio.get_running_loop()
    deadline = loop.time() + HANDOFF_DRAIN_DEADLINE_SECONDS
    # Records this loop took out of the queue and did not finish — at most the one
    # in flight when a cancel arrives. ``qsize()`` cannot see it, and a record that
    # left the buffer without reaching either store is exactly what
    # ``metadata_dropped_total`` means.
    in_flight_unaccounted = 0
    try:
        while True:
            budget = deadline - loop.time()
            if budget <= 0:
                break

            try:
                item = queue.get_nowait()
            except (asyncio.QueueEmpty, asyncio.QueueShutDown):
                # Empty, either way. ``get_nowait`` raises ``QueueShutDown`` rather
                # than ``QueueEmpty`` once the queue is both shut down and drained.
                break

            accounted = False
            try:
                await asyncio.wait_for(
                    publish_or_fall_back(item, publish, fallback), timeout=budget
                )
                accounted = True
            except TimeoutError:
                # This record alone ate the rest of the stop budget. It is named
                # individually because there IS a name here — the group line below
                # covers the records that were never taken out of the buffer and so
                # have no identity to report.
                metadata_dropped_total.inc()
                accounted = True
                log.warning(
                    "call_ledger.handoff_abandoned",
                    call_id=item.draft.call_id,
                    workspace_id=item.draft.workspace_id,
                    reason="stop_deadline",
                )
            finally:
                queue.task_done()
                if not accounted:
                    in_flight_unaccounted += 1
    finally:
        remaining = queue.qsize() + in_flight_unaccounted
        if remaining:
            metadata_dropped_total.inc(remaining)
            log.warning(
                "call_ledger.handoff_abandoned",
                reason="stop_deadline",
                group_size=remaining,
            )


async def run_publisher(
    exchange: AbstractExchange,
    stopping: asyncio.Event,
    *,
    fallback: FallbackWriter,
) -> None:
    """Drain the handoff onto the broker until ``stopping`` is set, then drain it.

    ``stopping`` is a directly-settable ``asyncio.Event`` rather than a signal
    handler, because ``loop.add_signal_handler`` is not implemented on Windows
    and the development host is Windows. ``prope.app`` supervises this job
    (D-32) and sets the event from its lifespan; this shape is drivable from a
    test on any platform.

    Nothing raised by a single record's publish escapes this loop — see
    :func:`publish_or_fall_back`, which owns that catch for both job bodies.

    **This function returns only when ``stopping`` is set**, and that matters to
    the supervisor: ``run_with_restart`` restarts a job that returns *cleanly*, so
    its own ``while not stopping.is_set()`` is what ends the loop immediately
    afterwards. That is correct **only because** this function observes the same
    event. A future ``run_publisher`` that returned for any other reason would be
    restarted in a tight loop against a handoff that has already been shut down.
    """
    queue = handoff()
    publish = partial(publish_record, exchange, fallback=fallback)

    while not stopping.is_set():
        try:
            item = await asyncio.wait_for(queue.get(), timeout=HANDOFF_POLL_SECONDS)
        except TimeoutError:
            continue

        try:
            await publish_or_fall_back(item, publish, fallback)
        finally:
            queue.task_done()

    await drain_handoff_on_stop(publish, fallback)
