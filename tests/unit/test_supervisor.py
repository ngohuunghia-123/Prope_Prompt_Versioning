"""D-14: the supervisor's behaviours, proved rather than described.

**A supervisor that never restarts anything looks identical to a healthy one.**
Nothing here asks the supervisor what it did and believes the answer. Every
assertion is a count kept by the *job bodies themselves*, or a wall-clock
measurement taken from outside, or the absence of a task in
``asyncio.all_tasks()``. A restart is observable only from inside a running
supervisor, which is why ``on_backoff`` exists at all — see its definition in
``prope.supervisor``.

**Four jobs across three modules will be written against this shape** —
call-ledger's drain and retention sweep now, evaluation's claim loop (ADR-0049,
Phase 16) and release-control's overdue sweep (ADR-0051, Phase 22) later. The
tests below are the contract those four inherit, so they assert the *shape* (a
job is a zero-argument coroutine factory; the supervisor knows nothing else
about it) as well as the behaviour.

**Every delay in this file is a test-supplied base and cap, never the module
constants.** The production values are 1 s and 60 s; a suite that slept them
would take minutes to assert seconds. The constants themselves are asserted for
their *relationship* — a cap below a base is a backoff that shrinks — and not by
being waited out.

The one test that deliberately uses a LARGE delay is the interruption test:
a 30-second backoff that returns in well under a second is the only way to
prove the sleep is interruptible rather than merely short.
"""

import asyncio
import signal
import sys

import pytest

import prope.supervisor
from prope.supervisor import (
    RESTART_BACKOFF_BASE_SECONDS,
    RESTART_BACKOFF_CAP_SECONDS,
    install_stop_handlers,
    interval_job,
    run_with_restart,
    supervise,
)

#: Short enough that a five-crash sequence costs milliseconds, long enough that
#: the doubling is a real ``asyncio`` sleep rather than a no-op.
BASE = 0.001

#: Deliberately long. A backoff that a stop event cannot interrupt would make
#: the interruption test wait this out, and the timeout would fail it — which is
#: the only way to tell "interrupted" from "short".
UNINTERRUPTED_BACKOFF = 30.0


async def test_a_clean_return_restarts_the_job_and_resets_the_backoff() -> None:
    """Iterations 1, 2 and 4 raise; 3 returns cleanly. The delays say what happened."""
    stopping = asyncio.Event()
    delays: list[float] = []
    iterations = {"n": 0}

    async def sometimes_crashes() -> None:
        iterations["n"] += 1
        if iterations["n"] in (1, 2, 4):
            raise RuntimeError("this iteration fails")

    async def record(job_name: str, delay: float) -> None:
        delays.append(delay)
        if len(delays) == 3:
            stopping.set()

    await asyncio.wait_for(
        run_with_restart(
            "sometimes", sometimes_crashes, stopping, base=BASE, cap=1.0, on_backoff=record
        ),
        timeout=5,
    )

    # 1st crash at base, 2nd at twice base, then the clean return puts it back
    # to base — which is the whole assertion: a job that recovers stops being
    # punished for a fault it no longer has.
    assert delays == pytest.approx([BASE, BASE * 2, BASE])
    assert iterations["n"] == 4


async def test_a_crash_backs_off_exponentially_and_stops_doubling_at_the_cap() -> None:
    stopping = asyncio.Event()
    delays: list[float] = []

    async def always_crashes() -> None:
        raise RuntimeError("this job is broken")

    async def record(job_name: str, delay: float) -> None:
        delays.append(delay)
        if len(delays) == 5:
            stopping.set()

    await asyncio.wait_for(
        run_with_restart(
            "crasher", always_crashes, stopping, base=BASE, cap=BASE * 4, on_backoff=record
        ),
        timeout=5,
    )

    assert delays == pytest.approx([BASE, BASE * 2, BASE * 4, BASE * 4, BASE * 4])


async def test_cancellation_propagates_and_is_never_counted_as_a_crash() -> None:
    """``CancelledError`` escapes. It is not logged, not slept on, not restarted."""
    stopping = asyncio.Event()
    backoffs: list[float] = []

    async def cancelled() -> None:
        raise asyncio.CancelledError

    async def record(job_name: str, delay: float) -> None:
        backoffs.append(delay)

    with pytest.raises(asyncio.CancelledError):
        await run_with_restart(
            "cancelled", cancelled, stopping, base=BASE, cap=BASE, on_backoff=record
        )

    # An empty list is the assertion: a cancellation counted as a crash would
    # have produced a backoff, and a supervisor that swallowed it would have
    # produced a backoff AND kept going.
    assert backoffs == []


async def test_a_crashing_job_does_not_stop_its_sibling() -> None:
    """The ``TaskGroup`` trap, asserted: one child raising does not cancel the others."""
    stopping = asyncio.Event()
    crashes = {"n": 0}
    iterations = {"n": 0}

    async def crasher() -> None:
        crashes["n"] += 1
        raise RuntimeError("this job is broken")

    async def counter_body() -> None:
        iterations["n"] += 1
        if iterations["n"] >= 5:
            stopping.set()

    async def counter() -> None:
        await interval_job(counter_body, 0.005, stopping)

    # Returns cleanly. An ExceptionGroup escaping here is the failure this whole
    # per-job wrapper exists to prevent.
    await asyncio.wait_for(
        supervise({"crasher": crasher, "counter": counter}, stopping, base=BASE, cap=BASE * 2),
        timeout=20,
    )

    assert iterations["n"] >= 5, "the healthy sibling stopped making progress"
    assert crashes["n"] > 1, "the crashing job was not restarted"


async def test_the_stop_event_interrupts_a_backoff_sleep() -> None:
    """Shutdown latency is bounded by the current iteration, never by the cap."""
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()

    async def always_crashes() -> None:
        raise RuntimeError("this job is broken")

    async def stop_immediately(job_name: str, delay: float) -> None:
        assert delay == pytest.approx(UNINTERRUPTED_BACKOFF)
        stopping.set()

    started = loop.time()
    await asyncio.wait_for(
        run_with_restart(
            "crasher",
            always_crashes,
            stopping,
            base=UNINTERRUPTED_BACKOFF,
            cap=UNINTERRUPTED_BACKOFF,
            on_backoff=stop_immediately,
        ),
        timeout=5,
    )
    elapsed = loop.time() - started

    # A bare ``asyncio.sleep(delay)`` would have taken 30 seconds and the
    # ``wait_for`` above would have failed the test at 5.
    assert elapsed < 1.0


async def test_the_stop_event_returns_every_job_and_leaves_nothing_pending() -> None:
    stopping = asyncio.Event()
    ran = {"a": 0, "b": 0}

    async def job_a() -> None:
        async def body() -> None:
            ran["a"] += 1

        await interval_job(body, 0.001, stopping)

    async def job_b() -> None:
        async def body() -> None:
            ran["b"] += 1

        await interval_job(body, 0.001, stopping)

    async def stopper() -> None:
        await asyncio.sleep(0.05)
        stopping.set()

    stop_task = asyncio.create_task(stopper())
    await asyncio.wait_for(supervise({"a": job_a, "b": job_b}, stopping), timeout=20)
    await stop_task

    assert ran["a"] > 0 and ran["b"] > 0
    # The tasks are NAMED after their jobs, so a leaked one is findable by name
    # rather than by counting anonymous tasks and hoping.
    assert [task for task in asyncio.all_tasks() if task.get_name() in {"a", "b"}] == []


async def test_an_interval_job_runs_its_body_waits_the_interval_and_runs_again() -> None:
    stopping = asyncio.Event()
    runs: list[float] = []
    loop = asyncio.get_running_loop()

    async def body() -> None:
        runs.append(loop.time())
        if len(runs) == 3:
            stopping.set()

    await asyncio.wait_for(interval_job(body, 0.01, stopping), timeout=5)

    assert len(runs) == 3
    assert runs[1] - runs[0] >= 0.01
    assert runs[2] - runs[1] >= 0.01


async def test_stopping_during_the_interval_wait_ends_it_without_a_second_body_run() -> None:
    """A 30-second interval that returns at once. Both halves in one assertion."""
    stopping = asyncio.Event()
    runs: list[int] = []

    async def body() -> None:
        runs.append(1)
        stopping.set()

    await asyncio.wait_for(interval_job(body, UNINTERRUPTED_BACKOFF, stopping), timeout=5)

    assert runs == [1]


async def test_install_stop_handlers_is_guarded_and_raises_nothing() -> None:
    """The Windows constraint, asserted on whichever platform is running.

    ``loop.add_signal_handler`` is not implemented on Windows and the
    development host for this project is Windows. Importing and calling this on
    either platform must raise nothing; what differs is the tuple it returns.
    """
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()

    installed = install_stop_handlers(loop, stopping)

    assert isinstance(installed, tuple)
    if sys.platform == "win32":
        assert installed == ()
        assert not stopping.is_set()
    else:
        assert set(installed) == {"SIGTERM", "SIGINT"}
        for name in installed:
            loop.remove_signal_handler(getattr(signal, name))


async def test_the_module_names_both_taskgroup_traps_and_the_windows_constraint() -> None:
    """The plan's verification line, as an assertion rather than a reading task.

    Both traps and the signal-handler constraint have to be stated *at the
    code*. A docstring that stops naming them is a docstring somebody deleted
    the reasoning from, and the next reader rediscovers the trap the expensive
    way.
    """
    docstring = prope.supervisor.__doc__ or ""

    assert "ExceptionGroup" in docstring
    assert "add_signal_handler" in docstring


def test_the_backoff_constants_are_a_backoff() -> None:
    assert RESTART_BACKOFF_BASE_SECONDS > 0
    assert RESTART_BACKOFF_CAP_SECONDS >= RESTART_BACKOFF_BASE_SECONDS
