"""D-15's window and ADR-0040's grouping: the consumer half of INT-018.

One window of messages, grouped by ``workspace_id``, one
``workspace_transaction`` per group, ``write_records`` inside it, and **that
group's** deliveries acked after **that group's** transaction has committed.

**Why the ack is per group and not per window.** D-15 says "ack the whole window
after commit", and read literally that is impossible, because the window is not
one transaction — ADR-0040 makes it N transactions, one per distinct workspace.
If group three fails after groups one and two have committed, acking the window
either acks work that failed or redelivers work that committed. There is no
third option and no ordering that avoids the choice. Acking per group is the
only shape that preserves both halves, so that is the adopted reading, and it is
written here so it can be disagreed with rather than discovered.

**``multiple=True`` is not used, deliberately.** ``IncomingMessage.ack(multiple=
True)`` acks every delivery tag up to and including the one given. That is a
per-window optimisation and it becomes unsafe the moment groups can fail
independently: the tags of two workspaces interleave arbitrarily in a window, so
"up to and including group two's last tag" sweeps up group three's earlier ones.
Each delivery is acked by itself.

**One consumer, one channel.** RabbitMQ applies ``prefetch_count`` PER CONSUMER
on a channel rather than per channel, and ``prefetch_count=0`` means infinite.
So the memory bound below — ``WINDOW_SIZE`` multiplied by envelope size, and the
envelope carries request and response bodies — holds only while there is exactly
one drain consumer. Plan 02-03's supervisor is where "exactly one" is asserted;
this module is where the assumption is written down.

**A dead-letter is not a drop, and this module used to say it was** (D-30). Phase
2 incremented ``prope_call_ledger_metadata_dropped_total`` at the two sites where
this module dead-letters a message — an invalid envelope in :func:`_parse` and a
refused write in :func:`_retry_group_one_at_a_time`. Both increments are gone.
After ADR-0041's fallback that counter means *both the broker and the database
were unavailable* and ``LedgerMetadataDropped`` pages immediately on it, while a
dead-lettered record is sitting in ``prope.call_record.dlq`` with a 30-day TTL
and an alert of its own on any non-zero depth. **This module now moves no
``metadata_dropped_total`` at all.** The reason and its limit are written at both
removal sites rather than only here.

**This module reads a clock, and :func:`_write_group` is the one place in it that
may.** The repository's convention is that ``now`` is an argument
(``retention.py``, ``writer.py``) and that a module with a genuine need names its
single site (``worker._utc_now``, ``api._utc_now``, ``enqueue()``,
``fallback.write_directly``). The need here is
``prope_call_ledger_write_lag_seconds``, declared *"enqueue -> durable"* — the
commit inside ``_write_group`` **is** the durable moment, so the interval can be
closed nowhere else.

**A-046.** No request body, response body, prompt body, fallback answer or
provider credential reaches a log line or a metric label from this module. Every
log call below carries only members of ``prope.observability.LOGGABLE_FIELDS``,
and the envelope's body fields are never read here — they travel from
``to_draft()`` into ``write_records`` and stop at ``ledger.call_body``.
"""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import structlog
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.broker.topology import declare_topology
from prope.call_ledger.envelope import CallRecordEnvelope
from prope.call_ledger.writer import DEFAULT_RETENTION_WINDOW, write_records
from prope.db.session import workspace_transaction
from prope.observability import redelivered_total, write_lag_seconds, written_total

log = structlog.get_logger(__name__)

#: D-15's N, argued rather than picked. The full argument, because D-15 demands
#: one:
#:
#: Sustained throughput is approximately ``N / (T + write_time_per_window)``, and
#: batching adds at most ``T`` to any single record's lag.
#:
#: **At the steady-state rate, T dominates and N is irrelevant.** At 50 rps a
#: 250 ms window holds about twelve messages, so a record's lag is the window
#: plus one write — far inside the p95 < 2 s enqueue-to-durable target, and the
#: window size never binds.
#:
#: **N only matters during a backlog**, where the window fills instantly and
#: throughput is ``N / write_time``. Clearing the stated 500 records/sec against
#: a 250 ms floor per window needs ``N >= 500 * 0.25 = 125`` before write time is
#: counted at all. 500 gives roughly four times that headroom and clears the
#: stated 3,000-message backlog in about six windows.
#:
#: Unvalidated at real scale, like every number of this kind in this codebase.
#: Changing it is meant to be a visible act.
WINDOW_SIZE = 500

#: D-15's T, in milliseconds. The floor on a record's added lag and, during a
#: backlog, the floor on how often a window can turn over. See ``WINDOW_SIZE``
#: for the arithmetic the two share.
WINDOW_MS = 250

#: How long the collector waits for the FIRST message of a window before
#: checking ``stopping`` again. Not a tuning parameter — it is the shutdown
#: latency of an idle drain, and it is short because an idle drain is what a
#: deploy interrupts.
IDLE_POLL_SECONDS = 0.05

#: How long to wait before letting a requeued transient failure come round
#: again. Flat rather than exponential: the drain has one consumer and a
#: requeued message goes back to the head of the queue, so the only thing a
#: growing delay would buy is a longer outage after the database returns.
TRANSIENT_BACKOFF_SECONDS = 1.0

#: PostgreSQL SQLSTATEs that mean "ask again later", not "this record is
#: unwritable". 40001 serialization failure, 40P01 deadlock detected, 57P01
#: admin shutdown, 53300 too many connections, and the 08xxx connection class.
#: Every one of them is a property of the moment rather than of the record.
TRANSIENT_SQLSTATES = frozenset(
    {"40001", "40P01", "57P01", "53300", "08000", "08003", "08006", "08007", "08P01"}
)

#: What ``retention_for`` must look like: awaited with ONE POSITIONAL ARGUMENT,
#: the ``workspace_id``, returning that workspace's retention window.
RetentionResolver = Callable[[str], Awaitable[timedelta]]


class WriteFailure(StrEnum):
    """What kind of failure a write raised, and therefore what to do with it.

    Two values and no third. A failure this module cannot classify is
    ``PERMANENT``, and that default is the load-bearing half — see
    :func:`classify_write_failure`.
    """

    PERMANENT = "permanent"
    TRANSIENT = "transient"


def classify_write_failure(error: BaseException) -> WriteFailure:
    """Permanent (dead-letter it) or transient (requeue it and back off).

    **Permanent** means the record can never be written AS IT IS, so redelivery
    cannot help:

    - the five ``ValueError`` refusals ``write_records`` raises — a batch
      spanning two workspaces, a batch mixing two currencies in one month, an
      ``eval`` record carrying a body, a priced record whose cost works out to
      zero, and a ``source=gateway`` record with no ``version_id`` (D-40)
    - a ``ValidationError`` from the envelope (pydantic's derives from
      ``ValueError``, so the first branch covers it)
    - an ``IntegrityError``: **a CHECK the record violates**, and after CL-02
      nothing else. ``ck_call_record_cost_state_is_coherent`` and
      ``ck_call_record_eval_calls_carry_run`` are the likely ones. Phase 2's
      version of this bullet named a **unique-key violation on ``call_id``** as
      the case that mattered and called it *"a named Phase 2 gap, not an
      accident"*: ``call_record``'s primary key is ``call_id`` alone and
      ``write_records`` issued a plain ``INSERT``, so an ordinary consumer
      restart dead-lettered records that were already written. **That gap is
      closed.** ``write_records`` now issues ``ON CONFLICT (call_id) DO
      NOTHING … RETURNING call_id`` (D-33), so a redelivered record cannot raise
      here at all — it is skipped by the statement, counted on
      ``duplicate_call_id_total``, and adds nothing to the workspace's spend. An
      ``IntegrityError`` reaching this classifier therefore means a genuinely
      different constraint, and the branch stays ``PERMANENT`` for the original
      reason: a record the encoding cannot represent is not made representable by
      being delivered again.

    **Transient** means the moment was wrong, not the record: a serialization
    failure, a deadlock, a lost or refused database connection.

    **The default is PERMANENT, and that is deliberate.** A classic queue has no
    ``x-delivery-limit`` (the accepted cost of the queue-type decision), so a
    permanently-failing record that is requeued is an infinite loop with nothing
    to stop it — T-02-06. An unrecognised error dead-letters, which loses one
    record into a place somebody can look at; the opposite default loses the
    drain.
    """
    if isinstance(error, (ValueError, ValidationError)):
        return WriteFailure.PERMANENT
    if isinstance(error, IntegrityError):
        return WriteFailure.PERMANENT
    if isinstance(error, (OperationalError, InterfaceError)):
        return WriteFailure.TRANSIENT
    if isinstance(error, DBAPIError):
        sqlstate = getattr(getattr(error, "orig", None), "sqlstate", None)
        if sqlstate in TRANSIENT_SQLSTATES:
            return WriteFailure.TRANSIENT
        return WriteFailure.PERMANENT
    if isinstance(error, (ConnectionError, OSError, asyncio.TimeoutError)):
        return WriteFailure.TRANSIENT
    return WriteFailure.PERMANENT

#: What ``on_window`` must look like: awaited with the number of messages in the
#: window just processed. An observation seam and nothing else.
WindowObserver = Callable[[int], Awaitable[None]]


async def default_retention_window(workspace_id: str) -> timedelta:
    """The 30-day default (A-040). Absence of a setting is the default, not an error.

    ``workspace_id`` is accepted and ignored, so that this function has the same
    shape as the real resolver and swapping one for the other is a change of
    argument rather than a change of call site.
    """
    return DEFAULT_RETENTION_WINDOW


def _group_by_workspace(
    parsed: Sequence[tuple[AbstractIncomingMessage, CallRecordEnvelope]],
) -> dict[str, list[tuple[AbstractIncomingMessage, CallRecordEnvelope]]]:
    """ADR-0040's grouping. Insertion order is preserved within each group."""
    groups: dict[str, list[tuple[AbstractIncomingMessage, CallRecordEnvelope]]] = defaultdict(list)
    for message, envelope in parsed:
        groups[envelope.workspace_id].append((message, envelope))
    return dict(groups)


async def _collect_window(
    inbox: asyncio.Queue[AbstractIncomingMessage],
    stopping: asyncio.Event,
) -> list[AbstractIncomingMessage]:
    """Up to ``WINDOW_SIZE`` messages, or ``WINDOW_MS`` after the first, whichever first.

    The clock starts at the FIRST message, not at the call: a window that timed
    out from the moment it was asked for would spend most of an idle drain's
    life expiring empty windows, and would give a lone message a lag of up to
    ``WINDOW_MS`` chosen by when the loop happened to come round.
    """
    loop = asyncio.get_running_loop()
    window: list[AbstractIncomingMessage] = []

    while not stopping.is_set():
        try:
            window.append(await asyncio.wait_for(inbox.get(), timeout=IDLE_POLL_SECONDS))
            break
        except TimeoutError:
            continue

    if not window:
        return []

    deadline = loop.time() + (WINDOW_MS / 1000)
    while len(window) < WINDOW_SIZE:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            window.append(await asyncio.wait_for(inbox.get(), timeout=remaining))
        except TimeoutError:
            break

    return window


async def _parse(
    window: Sequence[AbstractIncomingMessage],
) -> list[tuple[AbstractIncomingMessage, CallRecordEnvelope]]:
    """Validate each message. An envelope that fails is dead-lettered here.

    **Dead-lettered BEFORE any transaction opens**, which is the whole point of
    doing it in its own pass: a ``workspace_id`` that failed the envelope's
    gate must never reach ``set_config('app.workspace_id', ...)``, and the only
    way to be sure of that is for the code that opens the transaction to have
    nothing but validated envelopes to work from (T-02-01).

    ``reject(requeue=False)`` rather than ``nack``: a malformed envelope is
    permanently malformed, and a classic queue has no delivery limit, so a
    requeue here is an infinite loop.

    **``redelivered_total`` is counted here** (D-35), because this is the first
    place every message is individually handled and it runs before any
    transaction opens — the same reason the envelope gate lives here.
    """
    parsed: list[tuple[AbstractIncomingMessage, CallRecordEnvelope]] = []
    for message in window:
        if message.redelivered:
            # The BROKER's own view of what it re-sent, and deliberately a
            # DIFFERENT counter from ``duplicate_call_id_total``, which is the
            # DATABASE's view of what was already there. ``LedgerDuplicateCallIds``
            # reads the two TOGETHER — "duplicates that track redeliveries are the
            # broker working, and duplicates that exceed them are a caller
            # generating ids badly" — and that comparison becomes uncomputable the
            # moment either side is derived from the other.
            #
            # Counted whether or not the envelope validates below: the broker
            # re-sent it either way, and that is what this counter is about.
            redelivered_total.inc()

        try:
            envelope = CallRecordEnvelope.model_validate_json(message.body)
        except ValidationError:
            # **D-30: no counter here, and that is the change rather than an
            # omission.** ``metadata_dropped_total`` means a record exists
            # NOWHERE and ``LedgerMetadataDropped`` pages immediately on it; this
            # record is about to be in ``prope.call_record.dlq``, which A-149
            # gives a 30-day TTL and T-005 gives an alert on any non-zero depth.
            # A page that fires on one malformed envelope is a page people learn
            # to close, and losing that page would cost the one alert in this
            # module genuinely worth waking somebody for.
            #
            # The trade, stated out loud: a dead-lettered record IS absent from
            # ``ledger.call_record``, so the "100% of calls record a version ID"
            # claim is false for it. The signal that says so is ``dlq_depth > 0``
            # rather than a second page for the same event.
            #
            # **And the limit of that substitution** (RESEARCH Pitfall 13):
            # ``dlq_depth`` is a GAUGE and the DLQ's TTL is 30 days, so it answers
            # "is there anything in the DLQ right now" and can never answer "how
            # many have ever gone there" — after 30 days the message expires and
            # the gauge returns to zero with no record it was ever non-zero. The
            # durable record of this event is the log line below, and container
            # logs are capped by ADR-0030. **Do not close that gap with a
            # nineteenth metric**; the metric set is the lock file's, and the
            # phase that owns the deployment stack is who needs to know that DLQ
            # history lives in bounded logs.
            log.warning(
                "call_ledger.envelope_rejected",
                reason="envelope_invalid",
                delivery_tag=message.delivery_tag,
            )
            await message.reject(requeue=False)
            continue
        parsed.append((message, envelope))
    return parsed


async def _write_group(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    group: Sequence[tuple[AbstractIncomingMessage, CallRecordEnvelope]],
    retention_for: RetentionResolver,
) -> None:
    """One workspace, one transaction, one ``write_records``. Raises on refusal.

    The retention window is resolved BEFORE the transaction opens, so a settings
    read never sits inside the transaction that holds the write's locks.

    **``write_lag_seconds`` is closed here, on the production path**, per record,
    immediately after the commit. It is deliberately NOT behind ``on_window``:
    ``retention.py``'s rule for an observation seam is that *"when it is ``None``
    the branch is not taken — the production call path supplies no callback and
    behaves exactly as it would without the parameter"*, and **a metric is not an
    observation seam.** Behind the hook it would be absent in production, which
    is the only place ``LedgerWriteLagHigh`` reads it.
    """
    retention_window = await retention_for(workspace_id)
    drafts = [envelope.to_draft() for _, envelope in group]

    async with workspace_transaction(sessionmaker, workspace_id) as session:
        await write_records(session, drafts, retention_window=retention_window)
    # The transaction is committed here, and the next one has not opened. This
    # is where D-15's "ack after commit" lands — the caller acks this group's
    # deliveries next, and nothing else's.

    durable_at = datetime.now(UTC)
    for _, envelope in group:
        # ``occurred_at`` is stamped in ``enqueue()`` (D-41), in the ``app``
        # process, while ``durable_at`` is read here in ``worker``. **Clamped, and
        # the clamp is not defensive tidiness:** ``prometheus_client`` accepts a
        # negative observation without complaint — it decrements ``_sum`` while
        # incrementing ``_count``, which makes ``rate(_sum[5m])`` negative and any
        # average-latency panel built on it nonsense. Stated positively: this
        # metric is only meaningful because ``app`` and ``worker`` share a host
        # (ADR-0033), so the clamp guards against a topology change rather than
        # against today.
        write_lag_seconds.observe(
            max(0.0, (durable_at - envelope.occurred_at).total_seconds())
        )

    for draft in drafts:
        written_total.labels(source=str(draft.source)).inc()


async def _retry_group_one_at_a_time(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    group: Sequence[tuple[AbstractIncomingMessage, CallRecordEnvelope]],
    retention_for: RetentionResolver,
) -> None:
    """CR-01's second named test, as code: one poison record does not take its batch.

    ``write_records`` is all-or-nothing by design — it refuses a batch this
    encoding cannot represent BEFORE writing any of it — which is correct and is
    also why a single unwritable record would otherwise discard four innocent
    ones. So when a group has already failed, it is retried a record at a time,
    each in **its own** ``workspace_transaction``. Every record that commits is
    acked; only the records that raise are dead-lettered.

    **This path runs only after a group has already failed**, so the healthy
    case pays nothing for it — no extra transaction, no extra round trip, not
    even a branch taken.
    """
    for message, envelope in group:
        try:
            await _write_group(sessionmaker, workspace_id, [(message, envelope)], retention_for)
        except Exception as error:
            if classify_write_failure(error) is WriteFailure.TRANSIENT:
                # The retry hit a bad moment rather than a bad record. Requeue
                # it; the record itself has not been judged.
                await message.nack(requeue=True)
                continue
            # **D-30: no ``metadata_dropped_total`` here either.** Same argument
            # as :func:`_parse`'s removal, and same limit: this record is about to
            # be on ``prope.call_record.dlq``, whose depth gauge is the signal and
            # whose 30-day TTL is why the log line below is the only durable
            # record that the event happened. What survives on
            # ``metadata_dropped_total`` is the three events ADR-0041 means by it
            # — a refusing handoff, a direct write that did not land, and a stop
            # deadline that expired with records still buffered — and a
            # dead-letter is not a fourth.
            log.warning(
                "call_ledger.record_dead_lettered",
                call_id=envelope.call_id,
                workspace_id=workspace_id,
                reason="write_refused",
            )
            # reject(requeue=False), never nack(requeue=True): a classic queue
            # has no delivery limit, so requeueing a permanently-failing record
            # is an infinite loop (T-02-06).
            await message.reject(requeue=False)
        else:
            await message.ack()


async def run_drain(
    channel: AbstractChannel,
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    stopping: asyncio.Event,
    retention_for: RetentionResolver = default_retention_window,
    on_window: WindowObserver | None = None,
) -> None:
    """Consume ``prope.call_record`` until ``stopping`` is set.

    ``retention_for`` **takes exactly one positional argument, the
    ``workspace_id``.** The drain has no sessionmaker to hand it and must not
    acquire one: reading a setting is D-11's job for the drain and nobody
    else's, and a resolver that reached for a session would be a second place
    the tenant is set. The call site is ``await retention_for(workspace_id)``
    and nothing more.

    **Plan 02-02's real reader is ``read_retention_window(sessionmaker,
    workspace_id)``, a TWO-argument function, and is therefore NOT directly
    assignable to this parameter.** Plan 02-03 binds the sessionmaker with
    ``functools.partial`` before passing it in. That is recorded here, by name,
    because passing the bare two-argument function type-checks under a loose
    annotation and then raises ``TypeError`` on the first workspace group at
    runtime — inside a consumer, on the path whose whole purpose is not losing
    records.

    ``stopping`` is a directly-settable ``asyncio.Event`` rather than a signal
    handler: ``loop.add_signal_handler`` is not implemented on Windows and the
    development host is Windows. The signal wiring lands with the supervisor in
    plan 02-03.

    ``on_window`` is an observation seam and nothing else. It is keyword-only,
    defaults to ``None``, and when it is ``None`` the branch is not taken. It is
    awaited after a window's groups have all been committed and acked, because
    "one transaction per workspace group" is unobservable once the call has
    returned.
    """
    await channel.set_qos(prefetch_count=WINDOW_SIZE)
    queue = await declare_topology(channel)

    inbox: asyncio.Queue[AbstractIncomingMessage] = asyncio.Queue()

    async def _receive(message: AbstractIncomingMessage) -> None:
        # The callback does exactly one thing, which is what makes the
        # concurrency question moot: aio-pika's callback consumer would run
        # handlers concurrently up to the prefetch count, and a windowed batch
        # drain wants ONE accumulator rather than N concurrent handlers. This
        # callback IS the accumulator's inbox and nothing else.
        await inbox.put(message)

    consumer_tag = await queue.consume(_receive, no_ack=False)

    try:
        while not stopping.is_set():
            window = await _collect_window(inbox, stopping)
            if not window:
                continue

            parsed = await _parse(window)
            for workspace_id, group in _group_by_workspace(parsed).items():
                try:
                    await _write_group(sessionmaker, workspace_id, group, retention_for)
                except Exception as error:
                    if classify_write_failure(error) is WriteFailure.TRANSIENT:
                        # Nothing is wrong with these records. Put the whole
                        # group back and let the database recover.
                        log.warning(
                            "call_ledger.group_requeued",
                            workspace_id=workspace_id,
                            reason="transient",
                            group_size=len(group),
                        )
                        for message, _ in group:
                            await message.nack(requeue=True)
                        await asyncio.sleep(TRANSIENT_BACKOFF_SECONDS)
                        continue

                    # Permanent. At least one record in this group is
                    # unwritable — but ``write_records`` is all-or-nothing, so
                    # which one is not yet known and the innocent ones have not
                    # been written. Sort it out a record at a time.
                    log.warning(
                        "call_ledger.group_refused",
                        workspace_id=workspace_id,
                        reason="permanent",
                        group_size=len(group),
                    )
                    await _retry_group_one_at_a_time(
                        sessionmaker, workspace_id, group, retention_for
                    )
                    continue

                for message, _ in group:
                    # Per delivery, never ``multiple=True`` — see the module
                    # docstring. Two workspaces' tags interleave in a window.
                    await message.ack()

            if on_window is not None:
                await on_window(len(window))
    finally:
        await queue.cancel(consumer_tag)
