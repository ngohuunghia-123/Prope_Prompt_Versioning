"""D-13: the worker process, composed by hand, and its three residents.

``worker`` is born here and never again. Six more jobs across three later modules
join it — evaluation's claim loop (ADR-0049, Phase 16), release-control's
reconciliation query and overdue-gauge sweep (ADR-0051, Phase 22), and
prompt-improvement's daily detector pass and re-probe scheduler (ADR-0068) — and
each of them joins by somebody editing this file. That is D-13's **explicit
central composition**, and it is a decision rather than an absence of one.

**Two of the ten spend the workspace's money**, which is new as of ADR-0068 and
worth meeting at the top of the file rather than at a constant. ``improvement_sweep``
runs a gate dispatch against a prompt's own suite; ``improvement_reprobe`` runs a
guardrail probe against what is live. Both are ceiling-checked before their first
dispatch, both are opt-in on the re-probe side, and neither is a broker consumer —
a redelivered message would re-run work somebody has already been billed for.

**Two of the three residents are ``deployment_target``'s and the third is Phase
3's.** ``docs/modules/call-ledger.lock.yml``'s ``deployment_target`` names
exactly two — *"The retention job (A-040, A-106) and the drain both run in
``worker``"* — and the depth-gauge job (D-42) is absent from it. The discrepancy
is recorded here, at the constants below, and in the test that asserts the set,
because a spec sentence that has quietly stopped being complete is worse than one
that never claimed to be.

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
from prometheus_client import Gauge
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.broker.connection import build_connection
from prope.broker.topology import DLQ, WORK_QUEUE, declare_topology
from prope.call_ledger.drain import RetentionResolver, run_drain
from prope.call_ledger.retention import DEFAULT_CHUNK_SIZE, delete_expired_bodies
from prope.call_ledger.retention_settings import read_retention_window
from prope.db.engine import Settings, build_engine, build_sessionmaker
from prope.db.session import workspace_transaction
from prope.evaluation.claim import refresh_queue_depth
from prope.evaluation.executor import run_claimed_batch
from prope.evaluation.sweeper import sweep_interrupted_runs
from prope.observability import (
    configure_logging,
    dlq_depth,
    oldest_body_age_seconds,
    queue_depth,
    retention_deleted_total,
)
from prope.prompt_improvement.schedule import run_scheduled_probes
from prope.prompt_improvement.sweep import sweep_all_workspaces
from prope.prompt_search.worker import run_indexing_consumer
from prope.property_history.registry import install_registry, load_action_registry
from prope.release_control.sweep import (
    reconcile_released_pointers,
    refresh_review_task_gauges,
)
from prope.supervisor import install_stop_handlers, interval_job, supervise

log = structlog.get_logger(__name__)

#: The three residents, named. The names are the supervisor's task names and the
#: ``job`` field on a ``supervisor.job_crashed`` line, so they are a closed set
#: fixed in source — which is what makes that field safe as a log field under
#: A-046.
#:
#: **``docs/modules/call-ledger.lock.yml``'s ``deployment_target`` names exactly
#: the first two** — *"The retention job (A-040, A-106) and the drain both run in
#: ``worker``"*. The third is Phase 3's (D-42) and the lock file does not carry
#: it. That is stated here rather than left for a reader to notice, because the
#: sentence used to say ``deployment_target`` *"names exactly these"* and the day
#: a third arrived that sentence became false.
#:
#: **Three names, and three places that change together:** these constants, the
#: module docstring's paragraph about which jobs live here, and
#: ``tests/integration/test_worker_jobs.py``'s
#: ``test_the_worker_runs_exactly_the_three_jobs_this_file_composes``, whose name
#: moves with its assertion.
JOB_CALL_RECORD_DRAIN = "call_record_drain"
JOB_PROMPT_SEARCH_INDEX = "prompt_search_index"
JOB_EXPIRED_BODY_DELETION = "expired_body_deletion"
JOB_QUEUE_DEPTH_GAUGES = "queue_depth_gauges"

#: Evaluation's two, added in phase 16 (ADR-0049). **Neither is a broker
#: consumer**, and this module is the first place that sentence is observable
#: rather than only written down: ``eval_run.status`` is already a queue, and a
#: RabbitMQ message beside it would redeliver on a crash — re-dispatching every
#: paid case of a run nobody asked for.
JOB_EVAL_CLAIM_LOOP = "eval_claim_loop"
JOB_EVAL_SWEEPER = "eval_sweeper"

#: Release-control's two, added in phase 22 (ADR-0051). **Neither touches the
#: broker either**, which makes release-control the second module resident here
#: with no queue at all — it runs in ``worker`` for a timer.
#:
#: Both exist because ADR-0045's deny-by-default policy answers an unscoped
#: query with ZERO ROWS. Computed the obvious way — one query from ``app`` —
#: ``prope_release_review_task_overdue`` would read 0 forever,
#: ``BreakGlassTaskOverdue`` would never fire, and nothing would indicate that
#: the only control keeping break-glass exceptional was dead. So each pass
#: enumerates workspaces through ``access.list_workspaces()`` and reads every
#: one under its own policy.
JOB_RELEASE_TASK_GAUGES = "release_task_gauges"
JOB_RELEASE_RECONCILIATION = "release_pointer_reconciliation"

#: prompt-improvement's two, added 2026-08-20 (ADR-0068). **Neither touches the
#: broker either**, and the reason is sharper here than for release-control's
#: pair: both jobs SPEND MONEY. A RabbitMQ message beside a timer would redeliver
#: on a crash and re-run a sweep whose gate dispatches the workspace already paid
#: for — ``eval_run.status`` is a queue for the same reason (ADR-0049).
#:
#: Both enumerate workspaces through ``access.list_workspaces()`` and read each
#: one under its own policy — ADR-0051's shape rule, and its reason: an unscoped
#: query under ADR-0045 returns ZERO ROWS, so a sweep written the obvious way
#: would run cleanly, find nothing, and look healthy forever.
JOB_IMPROVEMENT_SWEEP = "improvement_sweep"
JOB_IMPROVEMENT_REPROBE = "improvement_reprobe"

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

#: How often the depth-gauge pass runs, argued against the scrape it feeds rather
#: than picked as a round number (D-42).
#:
#: **Against the scrape.** Prometheus's conventional ``scrape_interval`` is 15 s.
#: A gauge refreshed *less* often than the scrape produces a staircase Prometheus
#: cannot smooth — every other sample repeats the previous one — and an alert
#: that fires one interval late. Refreshed *more* often it burns AMQP round trips
#: producing samples nothing reads. Matching the two is the only value that costs
#: nothing on either side.
#:
#: **Against the round-trip cost.** One pass is two channel-open + passive-declare
#: + close cycles — a channel each, for the reason at :func:`read_queue_depths` —
#: which is single-digit milliseconds on a compose network. At 15 s that is a duty
#: cycle around 0.05%.
#:
#: **Rejected: 5 s.** Three times the round trips for a series nothing samples
#: that often. **Rejected: 60 s.** A dead-lettered record would be invisible for
#: up to a minute, and ``dlq_depth > 0`` is T-005's HIGH mitigation and the only
#: signal that says a record is genuinely absent from ``ledger.call_record``.
#:
#: **The honest caveat.** The scrape interval is a **deployment** setting and the
#: deployment stack owns no milestone (``.planning/research/PITFALLS.md`` §4), so
#: this number is matched to a *convention* rather than to a configured value. If
#: a Prometheus is ever configured with a different one, this constant is what
#: moves with it.
#:
#: A tunable judgement, not a repo decision, recorded so that changing it is a
#: visible act. Unvalidated at real scale, like every number of this kind here.
DEPTH_GAUGE_INTERVAL_SECONDS = 15.0

#: ADR-0049's claim interval, quoted rather than chosen: *"``worker`` runs a
#: claim loop on a **1 s** interval"*. The consequence the ADR already accepted
#: is that a queued run's start latency gains up to one second against a 120 s
#: budget — 0.8%, and the alternative was a broker wake-up nudge that
#: reintroduces the second queue this module exists without.
EVAL_CLAIM_INTERVAL_SECONDS = 1.0

#: A-054's sweeper cadence. The 5-minute no-progress rule it applies is
#: ``evaluation.domain.SWEEP_NO_PROGRESS_SECONDS``; this is only how often the
#: rule is evaluated, and the two are separate numbers because a shorter timer
#: must not shorten the grace period.
EVAL_SWEEP_INTERVAL_SECONDS = 60.0

#: `release-control.lock.yml`'s `deployment_target`, quoted rather than chosen:
#: *"the review-task gauges ... refreshed every 60 s"*.
RELEASE_GAUGE_INTERVAL_SECONDS = 60.0

#: The same block's other half: *"the released-pointer reconciliation query, at
#: startup and hourly"*. ``interval_job`` runs the body first and waits after,
#: so the startup pass is this job's first call rather than a separate one.
RELEASE_RECONCILE_INTERVAL_SECONDS = 3600.0

#: The daily detector pass. Twenty-four hours because the window it compares is
#: twenty-four hours (``domain.WINDOW``) — a pass more often than its own window
#: would compare overlapping periods and report the same anomaly as a new one,
#: and a pass less often would leave a day of degradation unlooked-at.
#:
#: ``interval_job`` runs the body first and waits after, so a deploy triggers a
#: pass immediately. That is right here: the sweep is idempotent by construction
#: — findings dedupe on ``(prompt, detector)`` and bump a count — so an extra
#: pass costs a metadata read per prompt and nothing else.
IMPROVEMENT_SWEEP_INTERVAL_SECONDS = 86_400.0

#: How often the re-probe scheduler CHECKS. Not how often it probes — that is
#: ``improvement.schedule.cadence_days``, per workspace, defaulting to seven.
#: Hourly, so a workspace that enables the schedule sees its first run within the
#: hour rather than at whatever time of day the worker happened to start.
IMPROVEMENT_REPROBE_INTERVAL_SECONDS = 3600.0

#: The (queue, gauge) pairs one depth pass reads. A tuple rather than two lines
#: inside the loop so a test can provoke the missing-queue branch against a name
#: that is not one of ours — see :func:`read_queue_depths`.
DEPTH_GAUGES: tuple[tuple[str, Gauge], ...] = (
    (WORK_QUEUE, queue_depth),
    (DLQ, dlq_depth),
)

#: The oldest surviving body in ONE workspace. Served by
#: ``ix_call_body_workspace_id_created_at`` (``0003_ledger_tables.py``), which
#: exists for exactly this gauge and says so at its own creation.
#:
#: **``created_at`` and not ``expires_at``, and the choice is semantic rather
#: than a performance one** — both columns are indexed. Three reasons point the
#: same way. The metric is named ``oldest_body_AGE_seconds`` and an age is
#: ``now - created_at``. ``LedgerRetentionOverdue`` compares *"age exceeds the
#: workspace's retention window plus one day"*, which only type-checks if the
#: gauge is an age. And D-10 is decisive: ``expires_at`` is stamped once and
#: never rewritten, so for a workspace that **shortened** its window
#: ``min(expires_at)`` reflects the OLD policy and would read healthy against the
#: new one — which is precisely the "looks healthy and is not" failure this alert
#: exists to catch.
#:
#: **The workspace predicate is written out, alongside the tenant policy rather
#: than instead of it**, exactly as ``retention.DELETE_CHUNK`` is: the policy is
#: the enforcement, and the explicit predicate is what makes the index scan a
#: property of the statement rather than of a planner choice. Bound, never
#: assembled.
OLDEST_BODY_CREATED_AT = text(
    """
    SELECT min(created_at)
    FROM   ledger.call_body
    WHERE  workspace_id = :ws
    """
)

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
    That is a real retention gap and it is bounded.

    **What Phase 3's gauge does and does not do about it — corrected here,
    because the earlier form of this paragraph promised more than shipped.** This
    class used to say that ``oldest_body_age_seconds`` *"reads above the window
    for exactly those workspaces"*, and it does not: :func:`observe_oldest_body_age`
    walks **this same enumerator**, so the gauge measures the data for every
    workspace it can see and **inherits this blind spot instead of catching it**
    (D-43). The alert genuinely measures the data rather than the job — that half
    is true and is the whole reason ``LedgerRetentionOverdue`` reads a gauge — but
    it measures the data of enumerated workspaces only. Leaving the old sentence
    standing would have been a lie in the most load-bearing prose in this module,
    and a lie of the exact kind this job exists to refuse: something that reports
    healthy because it looked at nothing.

    **Closing the other half needs ``access.list_workspaces()`` in Phase 7**, and
    :func:`run_worker` already takes the enumerator as a parameter — so Phase 7
    **replaces an argument** rather than editing this job or the gauge. There is
    no fifth ``SECURITY DEFINER`` function to invent in the meantime: exactly four
    are sanctioned and a test asserts the set is those four.

    ``tests/integration/test_worker_jobs.py`` asserts **all three halves** — that
    an observed workspace is swept, that an unobserved one is not, and that the
    age gauge is unmoved by an ancient body in an unobserved workspace — because
    an exception that is only written down is a belief. When Phase 7 closes the
    gap, those three assertions, this paragraph and
    :func:`observe_oldest_body_age`'s reduction are deleted together.
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
        deleted += await delete_expired_bodies(sessionmaker, workspace_id, now=now, chunk_size=chunk_size)
    return deleted


async def read_queue_depths(
    connection: AbstractRobustConnection,
    *,
    gauges: tuple[tuple[str, Gauge], ...] = DEPTH_GAUGES,
) -> None:
    """One pass: passive-declare both queues and set both depth gauges. D-42.

    **This is its own supervised job and not a read inside the drain's window
    loop, and the reason is a property rather than a preference.** A depth gauge
    published by the consumer whose backlog it measures **goes silent exactly
    when the backlog matters**: a wedged or crashed drain stops reporting, and
    Prometheus sees a stale series rather than a rising one — which is
    indistinguishable from a healthy queue on every graph an operator would look
    at. A job of its own also reports honestly when there is no traffic at all,
    which is the state ``LedgerWriteLagHigh`` and ``LedgerDlqNonEmpty`` care about
    most.

    **``passive=True``, never a full redeclare.** A passive declare checks
    existence and reports the counts **without comparing arguments**, so it can
    never answer ``406 PRECONDITION_FAILED``. That matters because D-23's queue
    arguments are one-way: a gauge job that could 406 would turn an argument
    drift into an outage of the very thing that would have shown it.

    **A fresh channel per queue, per pass.** A passive declare of a queue that
    does not exist is an AMQP **channel-level** error
    (``aio_pika.exceptions.ChannelNotFoundEntity``, a ``ChannelClosed``
    subclass), and the channel is gone with it. A long-lived job holding one
    channel would read ``queue_depth``, fail on ``dlq_depth``, and then be dead
    for every subsequent pass. ``tests/broker/_helpers.py`` already reads depths
    this way and already says why; this adopts that shape rather than inventing a
    second one.

    **What the gauge means is narrower than its name suggests.** RabbitMQ defines
    queue length as *"the number of messages **ready for delivery**"*, and a
    message is in one of two states — ready, or delivered-but-unacknowledged. The
    drain sets ``prefetch_count = WINDOW_SIZE`` (500), so **up to 500 messages can
    be unacknowledged and therefore invisible here at any moment.** Two
    consequences, both worth carrying: ``failure_modes`` row 1's detection
    narrative (*"``queue_depth`` rises"*) understates a small backlog completely;
    and **any test asserting that a backlog cleared must assert the durable side —
    rows in ``ledger.call_record`` — rather than this gauge.** The gauge is a
    graph; the table is the fact.

    ``gauges`` is a **test seam and nothing else**: it is keyword-only, it
    defaults to the real pair, and the production composition below passes
    nothing. It exists so the missing-queue branch above can be provoked against
    a name that is not one of ours, because the correct behaviour there — the job
    crashes, the supervisor logs ``supervisor.job_crashed`` and restarts it — is
    what the supervision buys and is therefore worth asserting once.
    """
    for queue_name, gauge in gauges:
        async with connection.channel() as channel:
            queue = await channel.declare_queue(queue_name, passive=True)
            gauge.set(queue.declaration_result.message_count or 0)


async def observe_oldest_body_age(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspaces: WorkspaceEnumerator,
    *,
    now: datetime,
) -> None:
    """Set ``oldest_body_age_seconds`` from the data. D-43, and the alert's series.

    **It cannot be one query, and the reason is the failure the alert exists to
    catch, one layer up.** Under ADR-0045 a ``prope_app`` read issued with no
    ``app.workspace_id`` set matches nothing and returns **zero rows** — so a bare
    ``SELECT min(created_at) FROM ledger.call_body`` would report a healthy gauge
    forever. That is the tenant policy working exactly as designed, and it is the
    same shape as the retention job that runs cleanly and deletes nothing, which
    is the shape ``LedgerRetentionOverdue`` was written against.

    So: one indexed read per enumerated workspace, inside that workspace's own
    transaction, reduced to the **maximum** age. ``max`` rather than ``min``
    because the alert asks *"is any body older than it should be"* and the worst
    workspace is the answer.

    **Zero when there are no bodies at all** — not "unset". ``REGISTRY`` renders
    an untouched gauge as ``0`` anyway, but the point is the reduction: an absent
    series and a healthy one are indistinguishable to a rule that compares against
    a threshold, so this job always sets a value. The clamp at zero is for the
    same reason: an age below zero is not a state this gauge can report
    meaningfully, and "nothing is overdue" is the truthful reading of it.

    **Unlabelled, and that is D-43 rather than an omission.** A per-workspace
    label here is exactly the cardinality ADR-0030's rule and this repository's
    own registry walk refuse — ``metadata_dropped_total``'s sentence, applied to a
    gauge. The consequence rides ``OQ-022`` clause 4: the alert's threshold is
    *per workspace* and this series is not, so a rules file can only compare
    against the default window.

    **The blind spot, stated rather than hidden.** This covers only the workspaces
    the enumerator returns, and today that is :class:`ObservedWorkspaces` — the
    workspaces this process has drained a record for since it started. **A
    workspace that has sent no traffic since process start is invisible to the
    gauge that exists to notice its unswept bodies.** That is a genuine partial
    close of Broken Window #3; reporting it as a full one would be the same shape
    as the job that runs cleanly and deletes nothing. Phase 7 closes it by passing
    an enumerator backed by ``access.list_workspaces()`` into :func:`run_worker` —
    **a replaced argument, not an edited job** — and there is no fifth
    ``SECURITY DEFINER`` function to be invented here in the meantime.

    **An exception propagates**, the same rule :func:`sweep_expired_bodies`
    states: a failing age read takes the pass down, the supervisor logs it and
    restarts, and the next pass starts from the top with a fresh ``now``.
    """
    oldest: float | None = None

    for workspace_id in await workspaces():
        async with workspace_transaction(sessionmaker, workspace_id) as session:
            created_at = (await session.execute(OLDEST_BODY_CREATED_AT, {"ws": workspace_id})).scalar_one()

        if created_at is None:
            continue

        age = (now - created_at).total_seconds()
        oldest = age if oldest is None else max(oldest, age)

    oldest_body_age_seconds.set(0.0 if oldest is None else max(0.0, oldest))


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
    depth_interval_seconds: float = DEPTH_GAUGE_INTERVAL_SECONDS,
    eval_claim_interval_seconds: float = EVAL_CLAIM_INTERVAL_SECONDS,
    eval_sweep_interval_seconds: float = EVAL_SWEEP_INTERVAL_SECONDS,
    release_gauge_interval_seconds: float = RELEASE_GAUGE_INTERVAL_SECONDS,
    release_reconcile_interval_seconds: float = RELEASE_RECONCILE_INTERVAL_SECONDS,
    improvement_sweep_interval_seconds: float = IMPROVEMENT_SWEEP_INTERVAL_SECONDS,
    improvement_reprobe_interval_seconds: float = IMPROVEMENT_REPROBE_INTERVAL_SECONDS,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    clock: Callable[[], datetime] = _utc_now,
) -> None:
    """Declare the topology, then supervise the drain, the sweep and the gauges.

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

    **The depth-gauge job is a third resident and not a read inside the drain**
    (D-42) — see :func:`read_queue_depths` for the property that makes it one. Its
    ``interval_job`` runs the body first and waits after, which is right here for
    the same reason it is right for the sweep: a worker that has just started
    after an outage is the case that matters, and a gauge that waited fifteen
    seconds before its first read would report nothing during the window an
    operator is watching.

    **The action registry is installed here and not in :func:`_amain`**, for the
    same reason every parameter below ``stopping`` exists: ``_amain`` is driven by
    nothing, so the worker's half of ADR-0038 would be exercised by nothing. A
    second ``install_registry`` in one process replaces the first with an equal
    immutable mapping, which is what keeps this function drivable twice in one
    test process — the property ``reset_handoff()`` buys the publisher, argued the
    same way. A failure to load raises out of here and fails startup; see
    ``prope.app``'s module docstring for the asymmetry against the broker.

    Every parameter after ``stopping`` exists so this composition is drivable
    from a test on the machine it was written on: ``stopping`` is a plain event
    (``loop.add_signal_handler`` is unimplemented on Windows), ``clock`` is the
    cut-off source, the two intervals are the schedules, and ``workspaces`` is the
    enumerator seam Phase 7 replaces. None of them changes what the process does
    with its defaults.
    """
    observed = workspaces if workspaces is not None else ObservedWorkspaces()
    retention_for = build_retention_resolver(sessionmaker, observing=observed)

    async with connection.channel() as startup_channel:
        await declare_topology(startup_channel)

    # A startup step of declare_topology's kind: idempotent in effect, ordered
    # before anything that could need it, and cheap (ADR-0038).
    async with sessionmaker() as session:
        install_registry(await load_action_registry(session))

    async def call_record_drain_job() -> None:
        # EXACTLY ONE consumer — see the module docstring. One job, one channel,
        # one `queue.consume` inside `run_drain`, and `prefetch_count` is
        # per-consumer in RabbitMQ.
        async with connection.channel() as channel:
            await run_drain(channel, sessionmaker, stopping=stopping, retention_for=retention_for)

    async def prompt_search_index_job() -> None:
        async with connection.channel() as channel:
            await run_indexing_consumer(channel, sessionmaker, stopping)

    async def expired_body_sweep() -> None:
        # One clock read per pass, BY THE CALLER, shared by the delete and the
        # gauge below — `sweep_expired_bodies`' stated property, extended to the
        # second reader rather than quietly given a second `now`.
        now = clock()
        deleted = await sweep_expired_bodies(sessionmaker, observed.current, now=now, chunk_size=chunk_size)
        # The return value used to be discarded here. It is the only place that
        # knows how many rows a pass actually removed, which is what
        # `retention_deleted_total` means.
        retention_deleted_total.inc(deleted)
        # D-43's gauge is composed HERE and deliberately not folded into
        # `sweep_expired_bodies`: that function returns `int`, its signature has
        # callers in `tests/integration/test_worker_jobs.py`, and it has been kept
        # free of metric side effects. A second enumeration pass costs one indexed
        # read per workspace once per sweep interval, against a function whose
        # docstring already accepts N+1 transactions per pass at pilot scale —
        # cheaper than a changed signature or a side effect in a pure function.
        await observe_oldest_body_age(sessionmaker, observed.current, now=now)

    async def expired_body_deletion_job() -> None:
        await interval_job(expired_body_sweep, retention_interval_seconds, stopping)

    async def queue_depth_gauge_job() -> None:
        await interval_job(
            functools.partial(read_queue_depths, connection),
            depth_interval_seconds,
            stopping,
        )

    async def eval_claim_pass() -> None:
        # The gauge is refreshed by the loop that would drain the queue, and
        # that is deliberate here where it was refused for `read_queue_depths`:
        # a queue nothing is claiming from IS the condition `EvalQueueBacklog`
        # watches for, so a gauge that went silent with the claim loop would
        # hide exactly the state it exists to show. It stays live because a
        # crashed job is restarted by `supervise` rather than left dead.
        await refresh_queue_depth(sessionmaker)
        await run_claimed_batch(sessionmaker)

    async def eval_claim_loop_job() -> None:
        await interval_job(eval_claim_pass, eval_claim_interval_seconds, stopping)

    async def eval_sweep_pass() -> None:
        # `interval_job` runs the body first and waits after, so the startup
        # sweep A-054 asks for is this call rather than a separate one: a
        # `worker` coming back from a crash reaps the runs its predecessor left
        # in `running` before it claims anything new.
        await sweep_interrupted_runs(sessionmaker, clock=clock)

    async def eval_sweeper_job() -> None:
        await interval_job(eval_sweep_pass, eval_sweep_interval_seconds, stopping)

    async def release_gauge_pass() -> None:
        # `clock()` rather than a read inside the sweep, for the reason
        # `sweep_expired_bodies` already states: a cut-off that advanced
        # mid-pass would make "what this pass counted" depend on how long the
        # pass took, and this one decides whether a break-glass follow-up is
        # overdue.
        await refresh_review_task_gauges(sessionmaker, now=clock())

    async def release_task_gauge_job() -> None:
        await interval_job(release_gauge_pass, release_gauge_interval_seconds, stopping)

    async def release_reconciliation_job() -> None:
        await interval_job(
            functools.partial(reconcile_released_pointers, sessionmaker),
            release_reconcile_interval_seconds,
            stopping,
        )

    async def improvement_sweep_pass() -> None:
        # `clock()` rather than a read inside the sweep, for `release_gauge_pass`'s
        # reason: a window boundary that advanced mid-pass would make "what this
        # pass measured" depend on how long the pass took, and every detector here
        # is a comparison between two windows whose edges must be fixed.
        await sweep_all_workspaces(sessionmaker, now=clock())

    async def improvement_sweep_job() -> None:
        await interval_job(improvement_sweep_pass, improvement_sweep_interval_seconds, stopping)

    async def improvement_reprobe_pass() -> None:
        await run_scheduled_probes(sessionmaker, now=clock())

    async def improvement_reprobe_job() -> None:
        await interval_job(
            improvement_reprobe_pass, improvement_reprobe_interval_seconds, stopping
        )

    await supervise(
        {
            JOB_CALL_RECORD_DRAIN: call_record_drain_job,
            JOB_PROMPT_SEARCH_INDEX: prompt_search_index_job,
            JOB_EXPIRED_BODY_DELETION: expired_body_deletion_job,
            JOB_QUEUE_DEPTH_GAUGES: queue_depth_gauge_job,
            JOB_EVAL_CLAIM_LOOP: eval_claim_loop_job,
            JOB_EVAL_SWEEPER: eval_sweeper_job,
            JOB_RELEASE_TASK_GAUGES: release_task_gauge_job,
            JOB_RELEASE_RECONCILIATION: release_reconciliation_job,
            JOB_IMPROVEMENT_SWEEP: improvement_sweep_job,
            JOB_IMPROVEMENT_REPROBE: improvement_reprobe_job,
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
