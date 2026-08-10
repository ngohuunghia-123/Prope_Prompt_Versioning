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

**A-046.** No request body, response body, prompt body, fallback answer or
provider credential reaches a log line or a metric label from this module. Every
log call below carries only members of ``prope.observability.LOGGABLE_FIELDS``,
and the envelope's body fields are never read here — they travel from
``to_draft()`` into ``write_records`` and stop at ``ledger.call_body``.
"""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from datetime import timedelta

import structlog
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.broker.topology import declare_topology
from prope.call_ledger.envelope import CallRecordEnvelope
from prope.call_ledger.writer import DEFAULT_RETENTION_WINDOW, write_records
from prope.db.session import workspace_transaction
from prope.observability import metadata_dropped_total, written_total

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

#: What ``retention_for`` must look like: awaited with ONE POSITIONAL ARGUMENT,
#: the ``workspace_id``, returning that workspace's retention window.
RetentionResolver = Callable[[str], Awaitable[timedelta]]

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
    """
    parsed: list[tuple[AbstractIncomingMessage, CallRecordEnvelope]] = []
    for message in window:
        try:
            envelope = CallRecordEnvelope.model_validate_json(message.body)
        except ValidationError:
            metadata_dropped_total.inc()
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
    """
    retention_window = await retention_for(workspace_id)
    drafts = [envelope.to_draft() for _, envelope in group]

    async with workspace_transaction(sessionmaker, workspace_id) as session:
        await write_records(session, drafts, retention_window=retention_window)
    # The transaction is committed here, and the next one has not opened. This
    # is where D-15's "ack after commit" lands — the caller acks this group's
    # deliveries next, and nothing else's.

    for draft in drafts:
        written_total.labels(source=str(draft.source)).inc()


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
                except Exception:
                    # Task 3 replaces this with the permanent/transient
                    # classification and the per-record batch-mate retry. Until
                    # then the safe default is the permanent one: reject without
                    # requeue, so the record dead-letters instead of looping on
                    # a queue that has no delivery limit.
                    for message, envelope in group:
                        metadata_dropped_total.inc()
                        log.warning(
                            "call_ledger.group_rejected",
                            call_id=envelope.call_id,
                            workspace_id=workspace_id,
                            reason="write_refused",
                            group_size=len(group),
                        )
                        await message.reject(requeue=False)
                    continue

                for message, _ in group:
                    await message.ack()

            if on_window is not None:
                await on_window(len(window))
    finally:
        await queue.cancel(consumer_tag)
