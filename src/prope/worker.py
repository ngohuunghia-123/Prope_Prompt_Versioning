"""D-13: the worker process, composed by hand, and its two residents.

``worker`` is born here and never again. Three more jobs across two later modules
join it — evaluation's claim loop (ADR-0049, Phase 16) and release-control's
reconciliation query and overdue-gauge sweep (ADR-0051, Phase 22) — and each of
them joins by somebody editing this file. That is D-13's **explicit central
composition**, and it is a decision rather than an absence of one.

**Why not a ``register()`` hook over a declared module list, and why not
auto-discovery by filename.** AC-10 and prompt-registry's route-uniqueness rule
both assert properties of the *assembled* surface: what is mounted, in total,
once every module has had its say. A job or a route that can appear because a
file was named a certain way is precisely the shape those tests exist to refuse —
the assertion would be checking a list that the discovery mechanism also
produced. Here the list is the import block at the top of this file, and a job
nobody wrote a line for cannot run. The cost is that adding a module means
editing two files by hand (this one and ``prope.app``); that cost is the
mechanism.

**``worker`` exposes NO HTTP endpoint. Not ``/healthz``, not ``/readyz``, not a
metrics port** (D-17). This is derived from ADR-0028 — *"``app`` publishes and
never consumes, ``worker`` consumes and never serves HTTP"* — rather than chosen
in discussion, and it is written here so a later reader does not mistake it for a
preference that a preference could reverse. INT-030's *"every module with a
process exposes readiness"* reads against the **module's** process, and
call-ledger's is ``app``: the readiness question "can this module serve" is a
question about the thing that serves. ``worker``'s compose healthcheck is
process-level. Prometheus scrapes ``app``.

A port opened here would be reachable from every other container on the compose
network (T-02-15), and it would be a surface nobody decided to have. The absence
is asserted by ``tests/integration/test_worker_jobs.py`` rather than left to
review — this module imports no ASGI framework at all, and an AST walk over it
says so.

**One drain consumer, and that is a correctness property rather than a capacity
choice.** RabbitMQ applies ``prefetch_count`` **per consumer** rather than per
channel (and ``0`` means infinite), so ``drain.WINDOW_SIZE``'s "the broker never
hands over more than one window of unacknowledged work" bound holds only while
there is exactly one consumer. Two consumers would silently double the resident
envelope memory — and the envelope carries request and response bodies. The lock
file's throughput row assumes the same thing in different words: *"batched
inserts, bodies included, single writer"*. Together with plan 02-02's
``ON CONFLICT ... WHERE`` one-currency invariant on ``workspace_spend``, that is
**both** halves of WARN-2 rather than neither (T-02-18). The consumer count is
asserted against the broker's own view, not by counting objects in this process.

**A-046.** The two log lines here carry an event name and nothing else. A worker
that logged its settings would log ``PROPE_DATABASE_URL`` and
``PROPE_BROKER_URL``, both of which carry credentials.
"""

import asyncio
import functools
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta

import structlog
from aio_pika.abc import AbstractRobustConnection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.broker.connection import build_connection
from prope.broker.topology import WORK_QUEUE, declare_topology
from prope.call_ledger.drain import RetentionResolver, run_drain
from prope.call_ledger.retention import DEFAULT_CHUNK_SIZE, delete_expired_bodies
from prope.call_ledger.retention_settings import read_retention_window
from prope.db.engine import Settings, build_engine, build_sessionmaker
from prope.observability import configure_logging
from prope.supervisor import install_stop_handlers, interval_job, supervise

log = structlog.get_logger(__name__)

#: The two residents, named. ``docs/modules/call-ledger.lock.yml``'s
#: ``deployment_target`` names exactly these: *"The retention job (A-040, A-106)
#: and the drain both run in ``worker``"*. The names are the supervisor's task
#: names and the ``job`` field on a ``supervisor.job_crashed`` line, so they are
#: a closed set fixed in source — which is what makes that field safe as a log
#: field under A-046.
JOB_CALL_RECORD_DRAIN = "call_record_drain"
JOB_EXPIRED_BODY_DELETION = "expired_body_deletion"

#: How often the expired-body sweep runs, argued against the lock file's target
#: rather than picked as a round number.
#:
#: The target is *"one day's expired bodies removed within 10 min"* at
#: *"up to 500,000 body rows in a batch, deleted in bounded chunks"*. Two things
#: follow, and they pull in opposite directions.
#:
#: **The interval cannot be the deadline.** A body that expires one second after
#: a pass starts waits a full interval before the next pass even begins, so the
#: worst observed age of a surviving expired body is ``interval + run_time``. An
#: interval of ten minutes therefore misses a ten-minute target by however long
#: the run takes, every time.
#:
#: **Five minutes splits the budget in half.** The interval spends 300 s of the
#: 600 s target and leaves 300 s for the run. Against the stated worst case —
#: 500,000 rows at ``DEFAULT_CHUNK_SIZE`` of 5,000, which is 100 chunks — that is
#: 3 s per chunk before the target is missed, and a chunk is one indexed
#: ``DELETE`` over ``(workspace_id, expires_at)`` in its own short transaction.
#: Ample, and the headroom is the point.
#:
#: **It also changes the shape of the steady state.** At five minutes a normal
#: pass clears five minutes of expiries, not a day's; the 500,000-row batch is
#: what a pass looks like *after an outage*, which is the only time A-132's
#: chunking is load-bearing. Shorter still buys nothing and multiplies the N+1
#: transactions below.
#:
#: A tunable judgement, not a repo decision, recorded so that changing it is a
#: visible act. Unvalidated at real scale, like every number of this kind here.
RETENTION_SWEEP_INTERVAL_SECONDS = 300.0

#: What a workspace enumerator must look like: awaited with nothing, returning
#: the workspace ids one sweep pass must visit.
#:
#: **This is the seam ADR-0051's ``access.list_workspaces()`` fills in Phase 7**,
#: and it is a named parameter rather than a hard-coded query for exactly that
#: reason. See :class:`ObservedWorkspaces` for what fills it today and for the
#: gap that leaves.
WorkspaceEnumerator = Callable[[], Awaitable[Sequence[str]]]


class ObservedWorkspaces:
    """The workspaces this process has drained a record for since it started.

    **This is a stand-in with a real gap in it, and the gap is stated here
    rather than discovered from a retention alert.**

    A cross-tenant sweep needs a list of tenants, and under ADR-0045 there is no
    way for ``prope_app`` to produce one from the ledger: the tenant policy is
    ``workspace_id = current_setting('app.workspace_id', true)``, so a query
    issued with no workspace set matches nothing and returns **zero rows**. That
    is the policy working exactly as designed. A ``SELECT DISTINCT workspace_id``
    written here would therefore return an empty list forever, and the sweep
    built on it would run cleanly, delete nothing, and look healthy — which is
    the one failure mode this whole job is shaped against.

    ADR-0051 answers this for the general case with
    ``access.list_workspaces()``, a ``SECURITY DEFINER`` function returning
    identifiers and nothing else. **It does not exist yet**: the ``access``
    schema arrives in Phase 7, call-ledger is forbidden an outbound edge to it,
    and inventing a fifth privilege-escalating routine here would break the test
    that asserts the sanctioned set is exactly four. ``retention.py`` recorded
    exactly this as OQ-C in Phase 1 and carried it upstream rather than
    improvising; this class is the smallest thing that makes the *scheduler*
    real without pre-empting that answer.

    **What it does.** The drain resolves a retention window once per workspace
    group (D-11), so the set of workspaces it has resolved a window for **is**
    the set of workspaces this process has written records for. That is not a
    side channel — it is the same fact read from the place D-11 already put it.
    See :func:`build_retention_resolver`.

    **What it misses, exactly.** A workspace that has sent no traffic since this
    process started is not swept, so its already-expired bodies survive until it
    sends something or until the process restarts into a period when it does.
    A workspace that stops sending traffic permanently is never swept again.
    That is a real retention gap, it is bounded and it is measurable: Phase 3's
    ``oldest_body_age_seconds`` gauge reads above the window for exactly those
    workspaces, which is the alert measuring the data rather than the job.
    Phase 7 closes it by passing an enumerator backed by
    ``access.list_workspaces()`` into :func:`run_worker`, and this class stops
    being the default.

    ``tests/integration/test_worker_jobs.py`` asserts **both halves** — that an
    observed workspace is swept, and that an unobserved one is not — because an
    exception that is only written down is a belief.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def note(self, workspace_id: str) -> None:
        """Record that this process has handled a record for ``workspace_id``."""
        self._seen.add(workspace_id)

    async def current(self) -> tuple[str, ...]:
        """The workspaces to sweep, sorted so a pass has a stable order.

        A coroutine, and sorted, because this is the seam ADR-0051's function
        fills: that one is a database round trip returning a ``SETOF text``, and
        a synchronous stand-in would have to be rewritten rather than replaced.
        """
        return tuple(sorted(self._seen))


def build_retention_resolver(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    observing: ObservedWorkspaces | None = None,
) -> RetentionResolver:
    """The drain's ``retention_for``, with the sessionmaker bound. D-11, closed here.

    **The two signatures do not match, and the mismatch is closed in this file
    rather than assumed away.** ``prope.call_ledger.drain`` declares
    ``retention_for: Callable[[str], Awaitable[timedelta]]`` and calls it as
    ``await retention_for(workspace_id)`` — one positional argument. Plan 02-02's
    real reader is ``read_retention_window(sessionmaker, workspace_id)``, which
    takes **two**. Passing the bare function is not a type error any annotation
    catches at import time: it is a ``TypeError`` raised on the **first workspace
    group**, inside the consumer, on the one path in this system whose whole
    purpose is not losing records. So the sessionmaker is bound here, at
    composition time, with ``functools.partial`` — and the ``partial`` below is
    load-bearing rather than stylistic.

    **This is where D-11 becomes true in the running system.** D-11's own risk is
    that "two callers must both remember to read it"; the answer to that is a
    test rather than discipline, and the test is in
    ``tests/integration/test_worker_jobs.py``: it invokes the object this
    function returns with a single positional ``workspace_id`` and asserts it
    returns that workspace's stored window, so a regression to the unbound form
    fails there rather than at runtime in the consumer.

    ``observing`` is how the retention sweep learns which workspaces exist —
    see :class:`ObservedWorkspaces`. When it is ``None`` the bound reader is
    returned untouched, which is the object the acceptance test calls.
    """
    read_window = functools.partial(read_retention_window, sessionmaker)

    if observing is None:
        return read_window

    async def resolve(workspace_id: str) -> timedelta:
        # Called once per workspace group, before the write transaction opens.
        # The drain has, by this point, parsed and grouped a validated envelope
        # for this workspace — so this is the earliest honest moment to say the
        # process has seen it.
        observing.note(workspace_id)
        return await read_window(workspace_id)

    return resolve


async def sweep_expired_bodies(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspaces: WorkspaceEnumerator,
    *,
    now: datetime,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> int:
    """One pass of the retention job: every workspace, in bounded chunks. D-12.

    ``now`` is read **once per pass by the caller** and passed in, never read
    inside the loop — the rule ``prope.call_ledger.retention`` states for itself,
    extended to the thing that schedules it. A cut-off that advanced mid-pass
    would make "what this pass deleted" depend on how long the pass took, which
    is the kind of answer that is impossible to reproduce from a log line.

    **N+1 transactions per pass, one per workspace, unbounded in workspace
    count.** A-140 records the same shape for release-control's sweep and accepts
    it at the pilot's scale. Recorded here rather than guessed at.

    **An exception propagates and is not swallowed.** A workspace that fails
    takes the pass down, the supervisor logs it and restarts the job after its
    backoff, and the next pass starts from the top with a fresh ``now`` — so
    every workspace is retried rather than skipped. Catching per workspace and
    continuing would produce a pass that reports itself complete while having
    done part of the work, which is the shape that makes a broken retention job
    indistinguishable from a working one.
    """
    deleted = 0
    for workspace_id in await workspaces():
        deleted += await delete_expired_bodies(
            sessionmaker, workspace_id, now=now, chunk_size=chunk_size
        )
    return deleted


def _utc_now() -> datetime:
    """The one clock read in this process, in the one place that may read it."""
    return datetime.now(UTC)


async def run_worker(
    sessionmaker: async_sessionmaker[AsyncSession],
    connection: AbstractRobustConnection,
    *,
    stopping: asyncio.Event,
    workspaces: ObservedWorkspaces | None = None,
    retention_interval_seconds: float = RETENTION_SWEEP_INTERVAL_SECONDS,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    clock: Callable[[], datetime] = _utc_now,
) -> None:
    """Declare the topology, then supervise the drain and the retention sweep.

    Returns when ``stopping`` is set and both jobs have returned. **The in-flight
    window is committed before that happens**: ``run_drain`` tests ``stopping``
    between windows rather than inside one, so a window that has already taken
    its first message is collected, grouped, written, committed and acked before
    the loop comes round to notice. Abandoning it would leave the records
    unacknowledged — recoverable, because the broker redelivers, but in Phase 2 a
    redelivered record dead-letters on the ``call_id`` unique violation until
    CL-02 lands. Draining the window is what keeps that from being an ordinary
    consequence of a deploy (T-02-19).

    ``declare_topology`` is called here, at startup, on a channel of its own —
    the same function ``app`` calls, from the same definition (D-24). It is
    idempotent, and ``run_drain`` declares again on its own channel; both
    declaring is free and neither depending on the other is the point. Deploy
    ordering must not be a data-loss question on the publish path.

    **The drain job opens its own channel each time it runs**, so a restart after
    a crash gets a clean one rather than inheriting whatever state closed the
    last one, and the channel closes on exit — which is what returns the queue's
    consumer count to zero when the worker stops.

    Every parameter after ``stopping`` exists so this composition is drivable
    from a test on the machine it was written on: ``stopping`` is a plain event
    (``loop.add_signal_handler`` is unimplemented on Windows), ``clock`` is the
    cut-off source, and ``workspaces`` is the enumerator seam Phase 7 replaces.
    None of them changes what the process does with its defaults.
    """
    observed = workspaces if workspaces is not None else ObservedWorkspaces()
    retention_for = build_retention_resolver(sessionmaker, observing=observed)

    async with connection.channel() as startup_channel:
        await declare_topology(startup_channel)

    async def call_record_drain_job() -> None:
        # EXACTLY ONE consumer — see the module docstring. One job, one channel,
        # one `queue.consume` inside `run_drain`, and `prefetch_count` is
        # per-consumer in RabbitMQ.
        async with connection.channel() as channel:
            await run_drain(channel, sessionmaker, stopping=stopping, retention_for=retention_for)

    async def expired_body_sweep() -> None:
        await sweep_expired_bodies(
            sessionmaker, observed.current, now=clock(), chunk_size=chunk_size
        )

    async def expired_body_deletion_job() -> None:
        await interval_job(expired_body_sweep, retention_interval_seconds, stopping)

    await supervise(
        {
            JOB_CALL_RECORD_DRAIN: call_record_drain_job,
            JOB_EXPIRED_BODY_DELETION: expired_body_deletion_job,
        },
        stopping,
    )


async def _amain() -> None:
    """Read the settings, build everything, run until stopped, dispose."""
    settings = Settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)

    stopping = asyncio.Event()
    installed = install_stop_handlers(asyncio.get_running_loop(), stopping)
    # Two event names rather than one line carrying a value: an event name is a
    # closed set fixed in source, which is the property A-046 asks of anything
    # that reaches a log line from here.
    if installed:
        log.info("worker.signal_handlers_installed")
    else:
        log.info("worker.signal_handlers_unavailable")

    chunk_size = settings.retention_chunk_size or DEFAULT_CHUNK_SIZE

    connection = await build_connection(settings.broker_url)
    try:
        async with connection:
            log.info("worker.started")
            await run_worker(sessionmaker, connection, stopping=stopping, chunk_size=chunk_size)
    finally:
        log.info("worker.stopped")
        await engine.dispose()


def main() -> None:
    """The process entrypoint. ``python -m prope.worker``, or the compose command.

    There is no ``uvicorn`` here and no ASGI application to hand one (D-17). The
    queue this process consumes is named in the import block above —
    ``prope.broker.topology.WORK_QUEUE`` — and that is the whole of its inbound
    surface.
    """
    configure_logging()
    asyncio.run(_amain())


#: Referenced so the queue this process exists to consume is greppable from the
#: entrypoint that consumes it, rather than only from the drain two modules away.
CONSUMES = WORK_QUEUE


if __name__ == "__main__":
    main()
