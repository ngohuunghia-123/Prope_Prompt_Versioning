"""D-14: one event loop, one process, and the shape three later modules inherit.

``worker`` runs more than one job and will run more than two. This module is
what starts them, keeps them started, and stops them together. It is not a
call-ledger concern even though call-ledger is its first caller: evaluation's
claim loop (ADR-0049, Phase 16) and release-control's overdue sweep (ADR-0051,
Phase 22) are written against this same shape, so **a job here is a name, a
zero-argument coroutine factory, and nothing else**. The supervisor knows no
module, opens no connection, and reads no setting. Anything a job needs is
bound into it by the composition in ``prope.worker`` before it arrives.

**No scheduler library, and the reason is A-012 rather than taste.** Two
interval jobs do not pay for APScheduler's misfire semantics, its job store or
its own executor, and A-012's surviving *debuggable by one person* clause is the
standing test every dependency in this project is measured against. Separate
per-job container commands were the other alternative and are rejected by
ADR-0033, which fixes the runtime at 7 services and 2 images: that shape grows
the service count by one for every job any of the eight modules ever adds.

**The accepted cost, stated rather than hidden (D-14).** Restart, backoff and
graceful shutdown become code this project writes and tests. That code is below
and its tests are ``tests/unit/test_supervisor.py``; the cost is about ninety
lines and it is paid once.

Three traps live here. Two are ``asyncio.TaskGroup``'s and one is the
platform's, and all three are named rather than left to be discovered:

**Trap 1 — the first unhandled exception in any child cancels every sibling.**
``TaskGroup`` is not a supervisor. On the first child exception it cancels the
remaining children, waits for them, and re-raises an ``ExceptionGroup``. For a
process whose whole purpose is that a crash in the retention sweep does not stop
the drain, that default is exactly backwards. The answer is that **every job is
individually wrapped** by :func:`run_with_restart`, which catches everything a
job body can raise. **The group must therefore never see an exception in normal
operation**, and if it ever does, the bug is in this module rather than in the
job.

**Trap 2 — the backoff sleep must be interruptible.** A bare
``asyncio.sleep(delay)`` in the restart loop means a ``SIGTERM`` arriving one
second into a sixty-second backoff waits fifty-nine more seconds before the
process exits, and a container runtime that gives a stopping container ten
seconds kills it instead. Every wait in this module goes through
:func:`_sleep_or_stop`, which returns the moment the stop event is set.

**Trap 3 — ``loop.add_signal_handler`` is not implemented on Windows.**
The containers are Linux under ADR-0033, but the development host for this
project is Windows, and a worker that cannot be started locally is a worker
whose shutdown path is never exercised by the person writing it. So
:func:`install_stop_handlers` is guarded by a ``sys.platform`` check and returns
the handlers it actually installed, and ``stopping`` is a plain
``asyncio.Event`` that a test — or a Windows entrypoint — sets directly. That is
the same reason ``prope.call_ledger.drain.run_drain`` takes an event rather than
installing a handler of its own.

**A-046.** The one log line this module emits carries the job's name and the
exception's class name and nothing else. No traceback, no exception message, no
argument value: a job body is handed a session factory and a broker channel, and
an exception message from that depth can quote a row, a body or a connection URL
carrying credentials. The name of the job that failed and the type of the
failure are what an operator needs to act; the rest belongs in a debugger
attached to a process that is not serving traffic.

``job`` is a new log field beside ``prope.observability.LOGGABLE_FIELDS``'s
current set. It qualifies on the same rule the allow-list exists to express —
its values are the job names fixed in ``prope.worker``'s source, a closed set of
two — and it is recorded in this phase's ``deferred-items.md`` so the module that
owns the allow-list adds it rather than this one editing a file it does not own.
"""

import asyncio
import signal
import sys
from collections.abc import Awaitable, Callable, Mapping

import structlog

log = structlog.get_logger(__name__)

#: What a job is: a zero-argument coroutine factory. Called again on every
#: restart, which is why it is a factory rather than a coroutine — a coroutine
#: object can only be awaited once, so a supervisor that took one could never
#: restart anything.
Job = Callable[[], Awaitable[None]]

#: What ``on_backoff`` must look like: awaited with the job's name and the delay
#: that is ABOUT TO BE SLEPT, before the sleep starts.
#:
#: An observation seam and nothing else — keyword-only, defaulting to ``None``,
#: and when it is ``None`` the branch is not taken, so the production call path
#: behaves exactly as it would without the parameter. It exists because a
#: restart is unobservable once the supervisor has returned: a supervisor that
#: restarted a job four times and one that restarted it once are indistinguishable
#: from the outside, and the exponent is the property most worth asserting.
BackoffObserver = Callable[[str, float], Awaitable[None]]

#: The first delay after a crash. One second, because the two failure causes
#: this is actually shaped against — a database that is restarting and a broker
#: that is reconnecting — both resolve on the order of seconds, and a first
#: retry that waits a minute would turn a two-second blip into a minute of
#: stopped work.
#:
#: A tunable judgement, not a repo decision, recorded so that changing it is a
#: visible act.
RESTART_BACKOFF_BASE_SECONDS = 1.0

#: The ceiling on the doubling. Sixty seconds: a job that has failed six times
#: in a row is failing for a reason a seventh immediate attempt will not fix,
#: and one attempt a minute is enough to notice the recovery without making the
#: log line the loudest thing in the system. It also bounds nothing about
#: shutdown, because the sleep is interruptible (Trap 2).
RESTART_BACKOFF_CAP_SECONDS = 60.0


async def _sleep_or_stop(stopping: asyncio.Event, seconds: float) -> bool:
    """Wait up to ``seconds``. Returns ``True`` if the stop event ended the wait.

    Trap 2, as a function. Every wait in this module goes through here so that
    shutdown latency is bounded by the current iteration rather than by whatever
    delay the backoff happened to have reached.
    """
    try:
        await asyncio.wait_for(stopping.wait(), timeout=seconds)
    except TimeoutError:
        return False
    return True


async def run_with_restart(
    name: str,
    job: Job,
    stopping: asyncio.Event,
    *,
    base: float = RESTART_BACKOFF_BASE_SECONDS,
    cap: float = RESTART_BACKOFF_CAP_SECONDS,
    on_backoff: BackoffObserver | None = None,
) -> None:
    """Run ``job`` until ``stopping`` is set, restarting it if it crashes.

    **A job is expected to run until ``stopping`` is set**, and the two callers
    in this phase both do: ``run_drain`` loops on the event, and
    :func:`interval_job` waits on it. A job that returns before then is restarted
    immediately — that is what "a clean return resets the backoff" means — and a
    job that returns *instantly* and forever is therefore a busy loop. The
    ``asyncio.sleep(0)`` on that path is what keeps such a job merely wasteful
    rather than fatal: without a yield point, a coroutine that never suspends
    would starve the event loop, and the stop event could never be set by anyone.

    ``asyncio.CancelledError`` is re-raised untouched. It is not a crash and must
    never be counted as one: it means somebody is tearing this task down, and a
    supervisor that swallowed it and restarted the job would defeat the
    cancellation while reporting itself healthy. It also inherits from
    ``BaseException`` rather than ``Exception`` in Python 3.13, so the ``except
    Exception`` below would not catch it — the explicit clause is written out
    anyway, because "it happens not to be caught" and "it is deliberately
    re-raised" read the same in a stack trace and only one of them survives a
    refactor.
    """
    delay = base

    while not stopping.is_set():
        try:
            await job()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # A-046: the job's name and the exception's CLASS. Not the message,
            # which at this depth can quote a row, a body or a broker URL.
            log.warning(
                "supervisor.job_crashed",
                job=name,
                reason=type(error).__name__,
            )
            if on_backoff is not None:
                await on_backoff(name, delay)
            if await _sleep_or_stop(stopping, delay):
                return
            delay = min(delay * 2, cap)
        else:
            delay = base
            # See the docstring: the one yield point that keeps a
            # instantly-returning job from starving the loop it shares.
            await asyncio.sleep(0)


async def supervise(
    jobs: Mapping[str, Job],
    stopping: asyncio.Event,
    *,
    base: float = RESTART_BACKOFF_BASE_SECONDS,
    cap: float = RESTART_BACKOFF_CAP_SECONDS,
    on_backoff: BackoffObserver | None = None,
) -> None:
    """Run every job until ``stopping`` is set, then return when all have stopped.

    One ``asyncio.TaskGroup``, one task per job, each task NAMED after its job —
    so a leaked task is findable by name in ``asyncio.all_tasks()`` rather than
    by counting anonymous ones, and so a traceback says which job it came from.

    Returns only when every job has returned. Because each job is wrapped by
    :func:`run_with_restart`, which catches everything, this coroutine raising an
    ``ExceptionGroup`` means a defect in this module rather than in a job — see
    Trap 1 in the module docstring.
    """
    async with asyncio.TaskGroup() as group:
        for name, job in jobs.items():
            group.create_task(
                run_with_restart(name, job, stopping, base=base, cap=cap, on_backoff=on_backoff),
                name=name,
            )


async def interval_job(
    body: Callable[[], Awaitable[None]],
    every: float,
    stopping: asyncio.Event,
) -> None:
    """Run ``body``, wait ``every`` seconds, run it again. Return when stopping.

    D-14's "timer jobs are plain interval loops", literally. There is no misfire
    policy, no catch-up, no jitter and no coalescing, because there is nothing
    here to misfire: this is a loop, and if a tick is late the next one is simply
    late. A scheduler's value is in the semantics around *missed* fires, and a
    job whose work is "delete whatever has expired by now" has no missed fire —
    the next run does the previous run's work as well.

    **The body runs FIRST and the wait comes after.** A worker that has just
    started after an outage is the case that matters: whatever expired during the
    outage should go on the first pass, not one interval later.

    The wait is interruptible (Trap 2), so a stop event set during it ends the
    job without running the body a second time. That property is what lets the
    interval be long — a ten-minute sweep interval does not become a ten-minute
    shutdown.

    An exception from ``body`` propagates. This function does not catch it,
    deliberately: :func:`run_with_restart` is what handles a crash, and a second
    handler here would mean a failing timer job silently kept its schedule while
    doing nothing.
    """
    while not stopping.is_set():
        await body()
        if await _sleep_or_stop(stopping, every):
            return


def install_stop_handlers(
    loop: asyncio.AbstractEventLoop,
    stopping: asyncio.Event,
) -> tuple[str, ...]:
    """Set ``stopping`` on ``SIGTERM`` and ``SIGINT``. Returns what was installed.

    Trap 3. ``asyncio``'s ``add_signal_handler`` is POSIX-only: on Windows the
    proactor event loop raises ``NotImplementedError``, and on the development
    host for this project that would make ``prope.worker`` unstartable — so the
    graceful-shutdown path would never be exercised on the machine it is written
    on. The ``sys.platform`` guard is the primary control and the
    ``NotImplementedError`` catch is the belt beside it, because the guard is a
    claim about a platform and the exception is the platform's own answer.

    **The fallback on Windows is that there is none, and that is stated rather
    than papered over.** Nothing installs a ``SIGINT`` handler there; a
    ``KeyboardInterrupt`` propagates out of ``asyncio.run`` and the process ends
    without draining. That is acceptable because Windows is a development host
    only (ADR-0033 puts the runtime on one Linux VM under docker-compose), and
    because ``stopping`` is a plain event: a test — or anything else that wants
    the graceful path locally — sets it directly, which is exactly what
    ``tests/unit/test_supervisor.py`` does.

    Returns the signal NAMES that were installed, so a caller can log what it got
    and a test can assert the guard fired. An empty tuple on Windows is the
    correct answer and not a failure.
    """
    if sys.platform == "win32":
        return ()

    installed: list[str] = []
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:
            continue
        installed.append(sig.name)
    return tuple(installed)
