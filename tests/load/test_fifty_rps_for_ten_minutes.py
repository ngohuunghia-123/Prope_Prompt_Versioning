"""ROADMAP SC5 literally: 50 rps for ten minutes, against a real broker and a real database.

Thirty thousand records, paced at fifty a second for six hundred seconds,
through ``enqueue()`` → the handoff → the real publisher → RabbitMQ → the real
drain → ``write_records`` → committed rows. It is **marked and skipped by
default** and it is what ``make load`` runs.

**Why skipped rather than deselected, and why the choice is not this phase's to
make quietly.** ``addopts = "-m 'not load'"`` would change the default selection
for the whole suite, for every phase from 4 to 24, and ORCHESTRATION §9's gate
is literally ``uv run pytest -q``. A **deselected** test is invisible in the
summary; a **skipped** test prints an ``s`` and, under ``-rs``, its reason and
its invocation. So the marker is registered in ``pyproject.toml``, the skip is
an ordinary ``skipif`` on an environment variable, and no ``addopts`` key
exists.

**Five assertion families, because duration is what buys the last four.**

1. **CL-12's caller span**, sampled throughout rather than only at the start —
   the p95 of thirty thousand timed ``enqueue()`` calls under 1 ms, with p50,
   p95 and p99 all reported, because at this duration the interesting failure is
   *drift* and a bare pass/fail hides it.
2. **CL-12's other half**: ``metadata_dropped_total`` moved by zero.
3. **The durable side**: thirty thousand rows in ``ledger.call_record``, read
   through ``migrate_engine`` — the owner role, subject to no policy. This is
   the assertion ``tests/load/test_enqueue_off_response_path.py`` cannot make,
   and it is what turns *"enqueue was fast"* into *"enqueue was fast and nothing
   was quietly lost"*. It is deliberately **not** written against
   ``prope_call_ledger_queue_depth``: that gauge counts messages **ready for
   delivery**, and the drain's ``prefetch_count`` is 500, so up to one window
   can be unacknowledged and invisible while a "the backlog cleared" assertion
   against the gauge passes. **The gauge is a graph; the table is the fact.**
4. **``test_plan.load``'s stall clause**: the drain is stopped at T+300 s for a
   full sixty seconds while the producer keeps its pace, then a second drain
   starts and the backlog is required to clear at **at least 500 records/sec**,
   derived as rows-written / elapsed across the recovery rather than from a
   synthetic benchmark. The lock file's own reason, worth repeating at the
   number: *a writer that merely keeps up has no capacity to clear a backlog
   after a stall, so every stall becomes permanent pressure.* This one
   assertion is written **last** in the test rather than here in the narrative,
   for the reason given at it: it is the only performance claim in the file and
   a machine-dependent number must not be able to hide a correctness one.
5. **AC-12's write-lag clause and ``test_plan.chaos``' fifth clause**, together,
   for the reason set out under *The write-lag window split* below.

**The write-lag window split, which is a deviation from plan 03-06's literal
instruction and is argued here rather than performed quietly.** AC-12's third
clause is *"write lag p95 stays under 2 s"*, under AC-12's own stated condition
of *"50 rps sustained for 10 minutes"*. Family 4 above deliberately removes the
consumer for sixty seconds, and sixty seconds at fifty a second is **three
thousand records — ten percent of the run** — every one of which is written
between five and sixty-five seconds after it was enqueued, by construction.
A p95 over the union of the two therefore **cannot** be under two seconds: it is
ten percent above target by arithmetic, and it would fail for a reason that has
nothing to do with the writer's performance. Asserting it over the union would
be asserting a claim AC-12 does not make.

So the histogram is snapshotted at four points and the clause is asserted over
the two windows in which AC-12's stated condition actually holds — from the
start to the stall, and from the end of the recovery to the end of the run,
which is **89% of the records and includes the retention sweep**. The stall
window is measured against the clause that does govern it, which is family 4's
recovery throughput. The whole-run share is computed and reported too, so
nothing is hidden. **The clause is asserted, not dropped** — the alternative,
deleting it in an objective paragraph, is exactly what plan 03-06 forbids.

**``test_plan.chaos``' fifth clause** — *"run the deletion job concurrently with
peak writes and assert the writer's lag stays inside its target"* — is one real
retention sweep at T+450 s, over a workspace seeded with genuinely expired
bodies so the ``DELETE`` has rows to remove rather than an index to scan. It
lands inside the second asserted window, so the lag clause covers it. **One pass
under load is not sustained contention**, and this closes the clause as written
and not more than it.

**Why the write-lag clause is readable at all here**: this run drives the drain
**in process**, so ``app``'s ``occurred_at`` stamp and ``worker``'s durable
moment land in the same ``prometheus_client`` registry. ``OQ-026``'s
two-process split — ``worker`` serves no HTTP by D-17, so half the metric set is
unscrapable in production — does not bite inside a test. **If this run is ever
restructured so the drain is out of process, this clause becomes unassertable,
and it must then be named and routed to a phase by name — never deleted.**

**The honest caveat on every number below.** This is one measurement, on one
developer host, executed once. A red result is a signal to investigate; it is
never a licence to lower the number. The thresholds are
``performance_requirements``' and ``acceptance_criteria``' and this file does
not own any of them.

**No bespoke cleanup, deliberately.** ``truncate_ledger`` and ``purge_queues``
are autouse, discover their targets from the catalogue, and already empty
thirty-five thousand rows and two queues at teardown. A test that added its own
would be a second cleanup path to keep correct.
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from aio_pika.abc import AbstractRobustConnection
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.broker.connection import build_connection, publisher_channel
from prope.broker.topology import declare_topology
from prope.call_ledger.drain import RetentionResolver, run_drain
from prope.call_ledger.enqueue import enqueue, reset_handoff, run_publisher
from prope.call_ledger.retention import DEFAULT_CHUNK_SIZE
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from prope.observability import WRITE_LAG_BUCKETS, retention_deleted_total
from prope.worker import (
    ObservedWorkspaces,
    build_retention_resolver,
    observe_oldest_body_age,
    sweep_expired_bodies,
)
from tests.broker._helpers import fallback_writer, pooled_sessionmaker
from tests.load import bucket_edge, counter_value, histogram_totals
from tests.unit import WORKSPACE_A, WORKSPACE_B, day, gateway_draft, seed_price_row

pytestmark = [
    pytest.mark.load,
    pytest.mark.skipif(
        not os.environ.get("PROPE_RUN_LOAD"),
        reason="ROADMAP SC5's stated condition: 30,000 records over 10 minutes. "
        "Run with `make load` or PROPE_RUN_LOAD=1 uv run pytest -m load",
    ),
]

#: ROADMAP SC5's own two numbers. ``RECORDS`` is derived from them rather than
#: written as 30,000, so a run at a different rate or duration cannot silently
#: assert a row count that belongs to this one.
RATE_PER_SECOND = 50
RUN_SECONDS = 600
RECORDS = RATE_PER_SECOND * RUN_SECONDS

#: ``test_plan.load``'s stall clause: *"stall the writer for 60 s and assert the
#: backlog clears rather than growing"*. Placed at the halfway mark so the run
#: has a steady-state window on either side of it — the first is what AC-12's
#: lag clause is asserted over, and the second is what proves the system
#: returned to steady state rather than merely finishing.
STALL_AT_SECONDS = 300.0
STALL_SECONDS = 60.0

#: ``test_plan.chaos`` clause 5's moment: after the recovery has demonstrably
#: completed, so the sweep contends with **peak writes** rather than with a
#: backlog being cleared. Contending with the recovery would measure a different
#: and much louder thing, and would make the lag clause unattributable.
SWEEP_AT_SECONDS = 450.0

#: ``performance_requirements``' drain figure. Derived from the recovery rather
#: than from a synthetic benchmark: rows written divided by elapsed seconds
#: across the interval in which the stall's backlog was cleared.
RECOVERY_RECORDS_PER_SECOND = 500.0

#: CL-12's budget in nanoseconds, and AC-12's write-lag budget in seconds. Both
#: belong to the lock file. ``WRITE_LAG_BUDGET_SECONDS`` is located as an EDGE of
#: ``WRITE_LAG_BUCKETS`` before it is used — see ``tests.load.bucket_edge`` for
#: why a target in a bucket's interior is not a measurable target.
ENQUEUE_BUDGET_NS = 1_000_000
WRITE_LAG_BUDGET_SECONDS = 2.0

#: The share of observations a p95 assertion requires at or below the edge.
QUANTILE = 0.95

#: A floor on how much of the run the write-lag assertion must actually cover,
#: so it cannot pass by measuring almost nothing. The stall removes ~10% of the
#: records from the asserted windows and the recovery a little more; anything
#: below three quarters means the phase boundaries are wrong rather than that
#: the system is slow.
MINIMUM_ASSERTED_SHARE_OF_RUN = 0.75

#: Bodies seeded EXPIRED in a second workspace, so ``test_plan.chaos`` clause
#: 5's sweep deletes rows instead of scanning an index. Five thousand is
#: ``DEFAULT_CHUNK_SIZE``, so the pass runs a full chunk and then a short one —
#: two transactions, which is the shape ``delete_expired_bodies`` is chunked for.
#:
#: A second workspace rather than a prefix within the first: the load run's
#: completion assertion is then a plain equality on ``WORKSPACE_A``'s rows
#: instead of a pattern match, and the two tenants' spend aggregates cannot
#: interfere.
EXPIRED_BODIES = 5_000
SEED_BATCH_SIZE = 500

#: One second, so ``expires_at`` = the draft's own ``created_at`` plus a second,
#: which is comfortably in the past for the fixture calendar's day 5. The sweep
#: therefore has genuinely expired rows without any clock being moved.
EXPIRED_RETENTION_WINDOW = timedelta(seconds=1)

#: How long the recovery and the final catch-up may take before the run is
#: called failed. Generous on purpose: a slow answer here is a real finding and
#: the assertions below are what judge it, so the timeout exists to bound the
#: test rather than to be the threshold.
RECOVERY_TIMEOUT_SECONDS = 180.0
CATCHUP_TIMEOUT_SECONDS = 300.0
DRAIN_STOP_TIMEOUT_SECONDS = 60.0
PUBLISHER_STOP_TIMEOUT_SECONDS = 60.0

#: Poll intervals. The recovery one is tight because the recovery is short and
#: the interval is measurement error on the throughput figure; the catch-up one
#: is loose because it is only waiting.
RECOVERY_POLL_SECONDS = 0.1
CATCHUP_POLL_SECONDS = 0.5

COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record WHERE workspace_id = :ws")
COUNT_BODIES = text("SELECT count(*) FROM ledger.call_body WHERE workspace_id = :ws")


@dataclass
class _Observations:
    """What the run saw, gathered where it happened and asserted where it ends.

    A record rather than a pile of ``nonlocal`` names: the paced producer and
    the chaos schedule run as two concurrent tasks and both write here, and the
    assertions all run after both have finished.

    The four ``lag_*`` pairs are ``(observations at or below the 2 s edge,
    observations in total)`` read from the process registry at four moments —
    which is what makes a window's share computable from a cumulative histogram
    that has no notion of time.
    """

    lag_at_start: tuple[float, float] = (0.0, 0.0)
    lag_before_stall: tuple[float, float] = (0.0, 0.0)
    lag_after_recovery: tuple[float, float] = (0.0, 0.0)
    lag_at_end: tuple[float, float] = (0.0, 0.0)
    stall_seconds: float = 0.0
    recovery_target: int = 0
    recovery_reached: int = 0
    recovery_rows: int = 0
    recovery_seconds: float = 0.0
    swept: int = 0
    samples: list[int] = field(default_factory=list)


class _Drain:
    """The real drain, startable and stoppable, so the run can stall it.

    ``tests/broker/_helpers.py``'s ``drain_until`` is the established shape and
    is not reusable here for one reason: it owns the whole lifetime of one drain
    and returns when a predicate holds. This run needs **two** drains — one
    before the stall and one after — with a producer paced across both, so the
    lifetime has to be the caller's.

    Every ``start`` builds a **fresh connection and channel**, which is what
    *"start a second drain"* means: a restarted consumer that inherits nothing
    from the one that stopped. The stop signal is a directly-settable
    ``asyncio.Event``, the shape ``run_drain`` takes precisely because
    ``loop.add_signal_handler`` is unimplemented on Windows.
    """

    def __init__(
        self,
        url: str,
        sessionmaker: async_sessionmaker[AsyncSession],
        retention_for: RetentionResolver,
    ) -> None:
        self._url = url
        self._sessionmaker = sessionmaker
        self._retention_for = retention_for
        self._stopping = asyncio.Event()
        self._connection: AbstractRobustConnection | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._stopping = asyncio.Event()
        self._connection = await build_connection(self._url)
        channel = await self._connection.channel()
        self._task = asyncio.create_task(
            run_drain(
                channel,
                self._sessionmaker,
                stopping=self._stopping,
                retention_for=self._retention_for,
            )
        )

    async def stop(self) -> None:
        """Set the event, let the in-flight window commit, then drop the connection.

        ``run_drain`` tests ``stopping`` **between** windows and not inside one,
        so a window that has already taken its first message is grouped,
        written, committed and acked before this returns. Abandoning it would
        leave records unacknowledged and turn the stall into a redelivery test.
        """
        if self._task is None:
            return
        task, connection = self._task, self._connection
        self._task, self._connection = None, None
        self._stopping.set()
        try:
            await asyncio.wait_for(task, timeout=DRAIN_STOP_TIMEOUT_SECONDS)
        finally:
            if connection is not None:
                await connection.close()


async def _rows(migrate_engine: AsyncEngine, workspace_id: str) -> int:
    """Committed records for one workspace, read as the OWNER.

    Never through the code under test and never through the ``prope_app`` role:
    a drain that acked everything and wrote nothing passes a test that reads its
    own return value, and a policy-subject read cannot distinguish "no rows" from
    "no tenant set".
    """
    async with migrate_engine.begin() as connection:
        return (await connection.execute(COUNT_RECORDS, {"ws": workspace_id})).scalar_one()


async def _bodies(migrate_engine: AsyncEngine, workspace_id: str) -> int:
    async with migrate_engine.begin() as connection:
        return (await connection.execute(COUNT_BODIES, {"ws": workspace_id})).scalar_one()


async def _wait_for_rows(
    migrate_engine: AsyncEngine,
    wanted: int,
    *,
    timeout: float,
    poll: float,
) -> int:
    """Poll the owner's row count until it reaches ``wanted``. Returns what it saw."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    seen = 0
    while loop.time() < deadline:
        seen = await _rows(migrate_engine, WORKSPACE_A)
        if seen >= wanted:
            return seen
        await asyncio.sleep(poll)
    return seen


async def _sleep_until(when: float) -> None:
    """Sleep to an ABSOLUTE loop time, never for a duration.

    Every schedule in this file is absolute for the same reason the producer's
    is: a sleep that overshoots by a few milliseconds is unremarkable, and a
    thousand of them accumulated against a relative schedule is a run that ends
    minutes late and reports a rate it never sustained.
    """
    loop = asyncio.get_running_loop()
    delay = when - loop.time()
    if delay > 0:
        await asyncio.sleep(delay)


def _lag_totals(edge: float) -> tuple[float, float]:
    """``write_lag_seconds`` at this instant: ``(at or below ``edge``, total)``."""
    return histogram_totals("prope_call_ledger_write_lag_seconds", edge)


def _percentiles(samples: list[int]) -> tuple[int, int, int]:
    """``(p50, p95, p99)`` as order statistics, in nanoseconds."""
    ordered = sorted(samples)
    return (
        ordered[int(0.50 * len(ordered))],
        ordered[int(QUANTILE * len(ordered))],
        ordered[int(0.99 * len(ordered))],
    )


def _span_report(samples: list[int]) -> str:
    p50, p95, p99 = _percentiles(samples)
    return (
        f"enqueue span over {len(samples)} calls: p50 {p50 / 1e6:.4f} ms, "
        f"p95 {p95 / 1e6:.4f} ms, p99 {p99 / 1e6:.4f} ms "
        f"(CL-12's budget is {ENQUEUE_BUDGET_NS / 1e6:.3f} ms)"
    )


async def _seed_expired_bodies(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """Give ``test_plan.chaos`` clause 5's sweep something to actually delete.

    Written through ``write_records`` rather than by hand, so the rows carry the
    encoding the writer produces — including the ``expires_at`` stamp, which is
    the record's own ``created_at`` plus the window and is the only thing the
    retention ``DELETE`` predicates on. The window is one second and the drafts
    are dated to the fixture calendar's day 5, so the rows are expired without
    any clock being moved: ``retention.py``'s whole design is that ``now`` is an
    argument and never a clock read, and moving a clock to test it would be
    testing something else.

    ``input_tokens`` and ``output_tokens`` are both ``None``, which makes these
    ``usage_status = unknown`` records and skips ``resolve_price`` entirely —
    five thousand round trips this seeding does not need to pay for. The bodies
    are what the sweep is for; the pricing is not.
    """
    for start in range(0, EXPIRED_BODIES, SEED_BATCH_SIZE):
        batch = [
            gateway_draft(
                call_id=f"cal_seed{index:022d}",
                workspace_id=WORKSPACE_B,
                created_at=day(5),
                input_tokens=None,
                output_tokens=None,
            )
            for index in range(start, min(start + SEED_BATCH_SIZE, EXPIRED_BODIES))
        ]
        async with workspace_transaction(sessionmaker, WORKSPACE_B) as session:
            await write_records(session, batch, retention_window=EXPIRED_RETENTION_WINDOW)


async def _produce(observations: _Observations, *, started_at: float) -> None:
    """Hand ``RECORDS`` drafts to ``enqueue()`` at ``RATE_PER_SECOND``, timing each.

    **The schedule is absolute and self-correcting**, not ``sleep(0.02)`` in a
    loop: the target for record *n* is ``started_at + n / RATE_PER_SECOND``, so a
    sleep that overshoots is absorbed by the next one firing immediately rather
    than pushing the whole run later. Measured on the development host at 4.990 s
    for 250 records against an ideal of 4.980 s, with a worst-case lateness of
    17 ms — one arrival interval.

    **The timed span is exactly the ``enqueue(draft)`` call.** The draft is built
    before the clock read, because ``CallRecordDraft.__init__`` is not part of
    what the gateway waits for and folding it in would measure this test.

    No backpressure and no headroom check, unlike
    ``tests/broker/test_broker_unreachable_fallback.py``'s producer: there the
    publisher was deliberately broken and the handoff would fill: here the
    broker is up, the publisher drains continuously, and a full handoff would be
    a real finding rather than a test artefact — so it is left to be counted on
    ``metadata_dropped_total``, which is assertion family 2.
    """
    for index in range(RECORDS):
        await _sleep_until(started_at + index / RATE_PER_SECOND)
        draft = gateway_draft(call_id=f"cal_load{index:022d}")
        started = time.perf_counter_ns()
        enqueue(draft)
        observations.samples.append(time.perf_counter_ns() - started)


async def _chaos(
    drain: _Drain,
    migrate_engine: AsyncEngine,
    sessionmaker: async_sessionmaker[AsyncSession],
    observed: ObservedWorkspaces,
    observations: _Observations,
    *,
    started_at: float,
    edge: float,
) -> None:
    """The stall, the recovery and the retention sweep, on their own schedule.

    A task of its own rather than checks folded into the producer's loop:
    ``drain.stop()`` waits for an in-flight window to commit, and a producer
    that awaited it would stop arriving for the duration — which would make the
    stall a gap in the arrival rate instead of a gap in the consumer, and would
    quietly remove the pressure the clause is about.
    """
    loop = asyncio.get_running_loop()

    # --- the stall (test_plan.load) -------------------------------------
    await _sleep_until(started_at + STALL_AT_SECONDS)
    observations.lag_before_stall = _lag_totals(edge)
    await drain.stop()
    stopped_at = loop.time()

    # A full sixty seconds of ACTUAL stall, measured from when the consumer
    # was gone rather than from the schedule: `stop()` waits for the in-flight
    # window, so an absolute restart time would have made the stall shorter
    # than the clause asks for by however long that window took.
    await _sleep_until(stopped_at + STALL_SECONDS)
    observations.stall_seconds = loop.time() - stopped_at

    # Everything enqueued by now must become durable. Read the rows BEFORE the
    # second drain starts, so the throughput below is not credited with work
    # that had already happened.
    observations.recovery_target = len(observations.samples)
    rows_before = await _rows(migrate_engine, WORKSPACE_A)
    await drain.start()
    resumed_at = loop.time()

    observations.recovery_reached = await _wait_for_rows(
        migrate_engine,
        observations.recovery_target,
        timeout=RECOVERY_TIMEOUT_SECONDS,
        poll=RECOVERY_POLL_SECONDS,
    )
    observations.recovery_seconds = loop.time() - resumed_at
    observations.recovery_rows = observations.recovery_reached - rows_before
    observations.lag_after_recovery = _lag_totals(edge)

    # --- the concurrent deletion (test_plan.chaos clause 5) --------------
    await _sleep_until(started_at + SWEEP_AT_SECONDS)
    # One clock read per pass, by the caller, shared by the delete and the gauge
    # — `worker.expired_body_sweep`'s own composition, reproduced here rather
    # than reached for, because that closure is not importable and copying its
    # three lines is honest about what is being exercised.
    now = datetime.now(UTC)
    observations.swept = await sweep_expired_bodies(
        sessionmaker, observed.current, now=now, chunk_size=DEFAULT_CHUNK_SIZE
    )
    retention_deleted_total.inc(observations.swept)
    await observe_oldest_body_age(sessionmaker, observed.current, now=now)


async def test_fifty_records_a_second_for_ten_minutes(
    amqp_url: str,
    app_engine: AsyncEngine,
    migrate_engine: AsyncEngine,
) -> None:
    """SC5, AC-12, ``test_plan.load`` and ``test_plan.chaos`` clause 5, in one run.

    Four clauses in one paced run rather than four ten-minute runs, because the
    provocations are cheap **inside** a run that is already arriving at fifty a
    second and are not reproducible outside one.
    """
    reset_handoff()
    edge = bucket_edge(WRITE_LAG_BUCKETS, WRITE_LAG_BUDGET_SECONDS)
    dropped_before = counter_value("prope_call_ledger_metadata_dropped_total")
    observations = _Observations()

    # A price row in force at the drafts' own `created_at`, so the thirty
    # thousand records take the PRICED path — one `resolve_price` per record and
    # a `workspace_spend` upsert per window. That is the production shape of
    # "peak writes" and the one the drain figure should be measured against.
    await seed_price_row(migrate_engine)

    # The pooled sessionmaker, not `app_sessionmaker`: the session fixtures use
    # NullPool so that no asyncpg connection is carried across event loops, and
    # a run of this length would otherwise pay a fresh TCP handshake per drain
    # window. `prope.app` builds a pooled one, and this measures that.
    async with pooled_sessionmaker(app_engine) as sessionmaker:
        await _seed_expired_bodies(sessionmaker)

        observed = ObservedWorkspaces()
        # The drain's resolver notes WORKSPACE_A on its first window (D-11), so
        # only the seeded tenant has to be introduced by hand. `note` is the
        # class's own API and not a reach into its internals.
        observed.note(WORKSPACE_B)
        retention_for = build_retention_resolver(sessionmaker, observing=observed)

        drain = _Drain(amqp_url, sessionmaker, retention_for)
        publisher_stopping = asyncio.Event()
        connection = await build_connection(amqp_url)

        async with connection, publisher_channel(connection) as channel:
            await declare_topology(channel)
            publisher = asyncio.create_task(
                run_publisher(
                    channel.default_exchange,
                    publisher_stopping,
                    fallback=fallback_writer(sessionmaker),
                )
            )
            await drain.start()

            started_at = asyncio.get_running_loop().time()
            observations.lag_at_start = _lag_totals(edge)
            producer = asyncio.create_task(_produce(observations, started_at=started_at))
            chaos = asyncio.create_task(
                _chaos(
                    drain,
                    migrate_engine,
                    sessionmaker,
                    observed,
                    observations,
                    started_at=started_at,
                    edge=edge,
                )
            )

            try:
                await asyncio.gather(producer, chaos)
                written = await _wait_for_rows(
                    migrate_engine,
                    RECORDS,
                    timeout=CATCHUP_TIMEOUT_SECONDS,
                    poll=CATCHUP_POLL_SECONDS,
                )
                observations.lag_at_end = _lag_totals(edge)
                wall_seconds = asyncio.get_running_loop().time() - started_at
            finally:
                for task in (producer, chaos):
                    task.cancel()
                publisher_stopping.set()
                await asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)
                await drain.stop()

        surviving_expired = await _bodies(migrate_engine, WORKSPACE_B)

    steady_below = (observations.lag_before_stall[0] - observations.lag_at_start[0]) + (
        observations.lag_at_end[0] - observations.lag_after_recovery[0]
    )
    steady_total = (observations.lag_before_stall[1] - observations.lag_at_start[1]) + (
        observations.lag_at_end[1] - observations.lag_after_recovery[1]
    )
    whole_below = observations.lag_at_end[0] - observations.lag_at_start[0]
    whole_total = observations.lag_at_end[1] - observations.lag_at_start[1]
    throughput = observations.recovery_rows / max(observations.recovery_seconds, 1e-9)

    # Printed rather than only asserted: on a green run these are the numbers
    # the criterion is proven WITH, and a passing test that reports nothing
    # leaves the next person to re-run twelve minutes to find them. Visible
    # under `pytest -s`; captured otherwise, and repeated in every assertion
    # message below so a failure carries them regardless.
    print(
        "\n"
        f"  wall time            {wall_seconds:.1f} s for {len(observations.samples)} records\n"
        f"  {_span_report(observations.samples)}\n"
        f"  rows (WORKSPACE_A)   {written} of {RECORDS}\n"
        f"  stall                {observations.stall_seconds:.1f} s, backlog target "
        f"{observations.recovery_target}, reached {observations.recovery_reached}\n"
        f"  recovery             {observations.recovery_rows} rows in "
        f"{observations.recovery_seconds:.2f} s = {throughput:.0f} records/sec\n"
        f"  write lag <= {edge} s  steady windows {steady_below:.0f}/{steady_total:.0f}, "
        f"whole run {whole_below:.0f}/{whole_total:.0f}\n"
        f"  retention sweep      {observations.swept} bodies deleted under load\n"
    )

    # --- 1 and 2: CL-12, the caller's span and the drop counter ----------
    assert len(observations.samples) == RECORDS, "the producer did not finish its schedule"
    _, p95, _ = _percentiles(observations.samples)
    assert p95 < ENQUEUE_BUDGET_NS, _span_report(observations.samples)
    assert counter_value("prope_call_ledger_metadata_dropped_total") == dropped_before, (
        "CL-12's other half: no metadata dropped. A delta, because the default REGISTRY is "
        "process-global"
    )

    # --- 3: the durable side, read through the owner role ----------------
    assert written == RECORDS, (
        f"{written} of {RECORDS} records reached ledger.call_record. This is the assertion the "
        "CI-resident proxy cannot make, and the one that turns a fast enqueue into a safe one"
    )

    # --- 4: test_plan.load's stall, and that the backlog CLEARED ---------
    assert observations.stall_seconds >= STALL_SECONDS, (
        f"the drain was only stopped for {observations.stall_seconds:.1f} s"
    )
    assert observations.recovery_reached >= observations.recovery_target, (
        f"the backlog did not clear: {observations.recovery_reached} rows against a target of "
        f"{observations.recovery_target} after {RECOVERY_TIMEOUT_SECONDS:.0f} s. A backlog that "
        "grows rather than clears is the failure this clause exists to catch"
    )

    # --- 5: AC-12's write lag, over the windows AC-12's condition holds --
    assert steady_total >= RECORDS * MINIMUM_ASSERTED_SHARE_OF_RUN, (
        f"only {steady_total:.0f} of {RECORDS} observations fell inside the asserted windows; the "
        "phase boundaries are wrong, and an assertion over almost nothing is not an assertion"
    )
    assert steady_below / steady_total >= QUANTILE, (
        f"AC-12: {steady_below:.0f} of {steady_total:.0f} steady-state observations at or below "
        f"the {edge} s edge, needing {QUANTILE:.0%}. Whole run including the deliberate 60 s "
        f"consumer outage: {whole_below:.0f} of {whole_total:.0f} — see the module docstring for "
        "why the outage window is measured against the recovery clause instead"
    )

    # --- test_plan.chaos clause 5: the deletion job ran, and it deleted --
    assert observations.swept == EXPIRED_BODIES, (
        f"the sweep removed {observations.swept} of {EXPIRED_BODIES} expired bodies; a deletion "
        "job that deletes nothing is not the deletion job this clause is about"
    )
    assert surviving_expired == 0, "read back through the owner role, not from the sweep's count"

    # --- last, deliberately: performance_requirements' drain figure ------
    #
    # **This assertion is last because it is the only PERFORMANCE claim in the
    # file and every claim above it is a CORRECTNESS one.** An assertion that
    # fails early hides every assertion after it, and a number that is a
    # property of the machine must not be able to hide "thirty thousand records
    # arrived and thirty thousand rows exist". Ordering is the whole of the
    # trick; nothing here is relaxed by it.
    #
    # **The honest caveat, and it does not make the number go away.** This run
    # drives the publisher AND the drain in ONE process on ONE event loop, which
    # is what makes AC-12's write-lag clause readable at all (one registry, see
    # the module docstring). In the deployment shape they are two processes on
    # one host — `app` publishes, `worker` consumes and serves no HTTP (D-17,
    # ADR-0028) — so this figure necessarily UNDERSTATES what the drain can do
    # with a loop to itself. That is a reason to investigate the number, not a
    # reason to accept it: an understated measurement is still the only
    # measurement this repository has.
    assert throughput >= RECOVERY_RECORDS_PER_SECOND, (
        f"the recovery cleared {observations.recovery_rows} rows in "
        f"{observations.recovery_seconds:.2f} s = {throughput:.0f} records/sec, against "
        f"{RECOVERY_RECORDS_PER_SECOND:.0f}. A writer that merely keeps up has no capacity to "
        "clear a backlog after a stall, so every stall becomes permanent pressure. One "
        "measurement on one host, with the publisher and the drain sharing its event loop: "
        "investigate it, never lower the number"
    )
