"""CR-02: a graceful stop drains the handoff, and counts only what it could not.

Phase 2's ``run_publisher`` returned the moment ``stopping`` was set, with up to
512 records still buffered, **with no counter and no log line**
(``02-VERIFICATION.md`` gathered the evidence). Phase 3 closes that by draining
first and counting second, and this module asserts both halves — because either
one alone is a worse product than the pair. A deploy that counts 512 drops is a
correct counter over lost data; a deploy that drains without counting the
remainder is silent about the records the deadline could not reach.

**The door and the room are two different properties.** ``queue.shutdown()``
closes the door: every ``enqueue()`` after it raises ``QueueShutDown`` at the
producer, which is counted where it happens. Without it, every record accepted
between ``stopping.set()`` and the publisher's last ``get`` would be a record that
will never be published *and* is not in the remainder count, because it arrived
after the count was taken. So there is a test for each.

**Every stop signal here is a directly-settable ``asyncio.Event``** — the shape
this repository takes precisely because ``loop.add_signal_handler`` is
unimplemented on Windows, which is the development host.
"""

import ast
import asyncio
import inspect
from pathlib import Path

import pytest
import structlog
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

import prope.call_ledger.enqueue as enqueue_module
from prope.app import (
    JOB_CALL_RECORD_PUBLISHER,
    PUBLISHER_STOP_TIMEOUT_SECONDS,
    _start_publisher,
    _stop_publisher,
    create_app,
    lifespan,
)
from prope.broker.connection import build_connection
from prope.broker.topology import declare_topology
from prope.call_ledger.enqueue import (
    HANDOFF_DRAIN_DEADLINE_SECONDS,
    drain_handoff_on_stop,
    enqueue,
    handoff,
    reset_handoff,
    run_publisher,
)
from prope.supervisor import supervise
from tests.broker._helpers import counter_value, fallback_writer, pooled_sessionmaker
from tests.unit import gateway_draft

#: Small on purpose. Every record here goes through a single-record transaction
#: on an unpooled test engine, and the properties under test are "all of them" and
#: "exactly the remainder" — neither of which gets truer at 512.
BUFFERED = 20

#: A port nothing listens on, so ``_start_publisher`` takes its failure branch.
DEAD_BROKER_URL = "amqp://guest:guest@127.0.0.1:1/"

COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")

ENQUEUE_SOURCE = Path(enqueue_module.__file__).read_text(encoding="utf-8")


async def _committed(migrate_engine: AsyncEngine) -> int:
    """Rows in ``ledger.call_record``, read as the OWNER — never via the fallback."""
    async with migrate_engine.begin() as connection:
        return (await connection.execute(COUNT_RECORDS)).scalar_one()


async def _wait_for_rows(migrate_engine: AsyncEngine, wanted: int, *, timeout: float) -> int:
    deadline = asyncio.get_running_loop().time() + timeout
    written = 0
    while asyncio.get_running_loop().time() < deadline:
        written = await _committed(migrate_engine)
        if written >= wanted:
            return written
        await asyncio.sleep(0.1)
    return written


def test_the_stop_timeout_is_derived_from_the_drain_deadline() -> None:
    """Three lines, and they are the whole of D-31's relationship between two files.

    ``_stop_publisher`` waits ``PUBLISHER_STOP_TIMEOUT_SECONDS`` and then cancels.
    If the inner deadline ever equalled or exceeded the outer wait, the cancel
    would land while the drain was still working and the remainder count would
    never run — which reproduces CR-02 with more machinery. Derivation makes drift
    impossible; this test makes a future "simplification" back to two literals
    fail loudly.
    """
    assert PUBLISHER_STOP_TIMEOUT_SECONDS > HANDOFF_DRAIN_DEADLINE_SECONDS


def _functions_that_shut_the_queue_down() -> list[str]:
    """Every function in ``enqueue.py`` whose BODY calls ``.shutdown()``.

    An AST walk rather than a grep, for the reason
    ``test_no_sql_interpolation.py`` gives about its own walk: the docstrings in
    that module explain ``queue.shutdown()`` at length, so a substring count would
    be a count of prose. This counts calls.
    """
    callers: list[str] = []
    for node in ast.walk(ast.parse(ENQUEUE_SOURCE)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Attribute)
                and inner.func.attr == "shutdown"
            ):
                callers.append(node.name)
                break
    return callers


def test_the_door_is_shut_in_one_place_and_both_job_bodies_reach_it() -> None:
    """The shared helper, asserted as shared.

    The most literal reading of D-31 — "after ``run_publisher``'s loop" — would
    leave a process that started against a dead broker with **no shutdown drain at
    all**, which is CR-02 reopened on the exact branch SC1 calls the most ordinary
    provocation. So the property is not "``shutdown()`` appears once in the file":
    that would refuse the correct implementation. It is "``shutdown()`` is called
    in exactly one FUNCTION, and both job bodies call that function".
    """
    assert _functions_that_shut_the_queue_down() == ["drain_handoff_on_stop"]

    assert "drain_handoff_on_stop(" in inspect.getsource(run_publisher)
    assert "drain_handoff_on_stop(None, fallback)" in inspect.getsource(_start_publisher)


async def test_a_graceful_stop_publishes_or_falls_back_what_is_buffered(
    amqp_url: str,
    app_engine: AsyncEngine,
    migrate_engine: AsyncEngine,
) -> None:
    """CR-02's first half: nothing buffered is abandoned, and nothing is counted lost.

    The publisher is "paused" by starting it with ``stopping`` already set, which
    is the only deterministic way to guarantee the records were drained by the
    STOP path rather than by the running loop. Its channel is closed, so each
    record takes the fallback — which is what puts a row in ``ledger.call_record``
    where ``migrate_engine`` can read it without a drain.
    """
    reset_handoff()
    dropped_before = counter_value("prope_call_ledger_metadata_dropped_total")

    for index in range(BUFFERED):
        enqueue(gateway_draft(call_id=f"cal_{index:026d}"))
    assert handoff().qsize() == BUFFERED, "the positive control: they really are buffered"

    stopping = asyncio.Event()
    stopping.set()

    connection = await build_connection(amqp_url)
    async with pooled_sessionmaker(app_engine) as sessionmaker, connection:
        channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
        await declare_topology(channel)
        await channel.close()

        await run_publisher(
            channel.default_exchange,
            stopping,
            fallback=fallback_writer(sessionmaker),
        )

    assert await _committed(migrate_engine) == BUFFERED
    assert counter_value("prope_call_ledger_metadata_dropped_total") == dropped_before, (
        "a graceful stop drains rather than counting; the counter is for what it cannot reach"
    )


async def test_a_truncated_drain_counts_exactly_the_remainder_and_names_it_once(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CR-02's second half. The deadline expires; every survivor is counted, once.

    The deadline is patched to zero rather than to "small", so the remainder is
    exactly ``BUFFERED`` rather than whatever the machine managed in the time
    allowed — a partially-drained remainder is a race, and the property under test
    is *the remainder is counted exactly*, not *how many got through*. The test
    above is the positive control that proves the same setup drains everything
    when the deadline is real.
    """
    reset_handoff()
    monkeypatch.setattr("prope.call_ledger.enqueue.HANDOFF_DRAIN_DEADLINE_SECONDS", 0.0)
    dropped_before = counter_value("prope_call_ledger_metadata_dropped_total")

    for index in range(BUFFERED):
        enqueue(gateway_draft(call_id=f"cal_{index:026d}"))

    with structlog.testing.capture_logs() as captured:
        await drain_handoff_on_stop(None, fallback_writer(app_sessionmaker))

    assert counter_value("prope_call_ledger_metadata_dropped_total") == (
        dropped_before + BUFFERED
    )

    abandoned = [
        record for record in captured if record["event"] == "call_ledger.handoff_abandoned"
    ]
    assert len(abandoned) == 1, "one line for the whole remainder, not one per record"
    assert abandoned[0]["group_size"] == BUFFERED
    assert abandoned[0]["reason"] == "stop_deadline"


async def test_enqueue_after_the_door_is_shut_returns_normally_and_counts(
    app_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """The door. ``QueueShutDown`` gets its own branch, its own reason, and a count.

    ``QueueShutDown`` derives from ``Exception``, so without its own branch it
    would land in the bare handler and log ``reason="handoff_failed"`` — which
    reads as a bug rather than as a deploy. The record is genuinely lost either
    way, so it is counted exactly like the full-buffer case.
    """
    reset_handoff()
    await drain_handoff_on_stop(None, fallback_writer(app_sessionmaker))

    dropped_before = counter_value("prope_call_ledger_metadata_dropped_total")
    offered_before = counter_value(
        "prope_call_ledger_enqueued_total", {"source": "gateway", "outcome": "dropped"}
    )

    with structlog.testing.capture_logs() as captured:
        assert enqueue(gateway_draft()) is None, "INT-018 holds on this branch too"

    assert counter_value("prope_call_ledger_metadata_dropped_total") == dropped_before + 1
    assert (
        counter_value(
            "prope_call_ledger_enqueued_total", {"source": "gateway", "outcome": "dropped"}
        )
        == offered_before + 1
    )
    reasons = [record.get("reason") for record in captured]
    assert "shutting_down" in reasons
    assert "handoff_failed" not in reasons, "a deploy is not a bug and must not read as one"


async def test_the_fallback_only_branch_also_drains_on_stop(
    app_engine: AsyncEngine,
    migrate_engine: AsyncEngine,
) -> None:
    """The branch the shared helper exists for: a process that never had a broker.

    The records are offered in one synchronous burst immediately followed by
    ``stopping.set()``, with no ``await`` between them, so the running loop gets at
    most one of them and the stop drain gets the rest. If the fallback-only job did
    not call ``drain_handoff_on_stop``, ``BUFFERED - 1`` records would be abandoned
    uncounted — which is exactly CR-02, reopened on the branch SC1 cares about most.
    """
    reset_handoff()
    dropped_before = counter_value("prope_call_ledger_metadata_dropped_total")

    application = FastAPI()
    stopping = asyncio.Event()

    async with pooled_sessionmaker(app_engine) as sessionmaker:
        application.state.sessionmaker = sessionmaker
        await _start_publisher(application, DEAD_BROKER_URL, stopping)
        assert application.state.publisher is not None

        # ``_start_publisher`` hands the job to ``create_task``, which has not run
        # yet. Without this the supervisor's own ``while not stopping.is_set()``
        # would see the event already set and never call the job at all — the
        # test would pass or fail on a scheduling accident rather than on the
        # drain.
        await asyncio.sleep(0.2)

        for index in range(BUFFERED):
            enqueue(gateway_draft(call_id=f"cal_{index:026d}"))
        stopping.set()

        await _stop_publisher(application)

        assert await _wait_for_rows(migrate_engine, BUFFERED, timeout=30.0) == BUFFERED

    assert counter_value("prope_call_ledger_metadata_dropped_total") == dropped_before


async def test_two_consecutive_lifespans_in_one_process_both_enqueue(
    app_engine: AsyncEngine,
    migrate_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``reset_handoff()`` in the lifespan's ``finally``, asserted as behaviour.

    ``queue.shutdown()`` is one-way for the queue object and ``handoff()`` caches
    in a module global, so without the reset every ``enqueue()`` after the first
    lifespan would take the ``QueueShutDown`` branch and count a drop **forever**.
    In the suite that is masked by ``purge_queues`` resetting at teardown, which is
    why this test drives two lifespans inside ONE test rather than trusting two
    tests to notice.

    The broker URL is dead on purpose: this exercises the fallback-only branch end
    to end through the real ``lifespan``, which is the composition an operator
    actually runs.
    """
    monkeypatch.setenv(
        "PROPE_DATABASE_URL", app_engine.url.render_as_string(hide_password=False)
    )
    monkeypatch.setenv("PROPE_BROKER_URL", DEAD_BROKER_URL)
    reset_handoff()

    application = create_app()

    for round_number in range(2):
        async with lifespan(application):
            enqueue(gateway_draft(call_id=f"cal_{round_number:026d}"))
            assert await _wait_for_rows(
                migrate_engine, round_number + 1, timeout=30.0
            ) == round_number + 1

    assert await _committed(migrate_engine) == 2, "the second lifespan was not poisoned"


async def test_an_exception_out_of_the_publisher_job_restarts_it_and_is_logged() -> None:
    """D-32: a publisher that dies is restarted and says so, rather than ending silently.

    Before this, ``app`` started the publisher as a bare ``asyncio.create_task``,
    so an exception escaping ``run_publisher`` ended it with no crash, no restart
    and nothing in ``/readyz`` — which is the database alone by decision. The
    fallback makes that reachable, because a fallback can raise where
    ``publish_record`` could not.

    The job body here is a stand-in rather than the real publisher: the restart
    ladder itself is already asserted in ``tests/unit/test_supervisor.py``, and
    what this asserts is that ``app``'s own job NAME travels on the crash line —
    which is what makes ``job`` safe as a log field under A-046, since its values
    are a closed set fixed in source.
    """
    stopping = asyncio.Event()
    runs: list[int] = []

    async def crashing_publisher() -> None:
        runs.append(len(runs))
        if len(runs) == 1:
            raise RuntimeError("the fallback raised where publish_record could not")
        await asyncio.wait_for(stopping.wait(), timeout=10)

    with structlog.testing.capture_logs() as captured:
        supervisor = asyncio.create_task(
            supervise({JOB_CALL_RECORD_PUBLISHER: crashing_publisher}, stopping)
        )
        deadline = asyncio.get_running_loop().time() + 15
        while len(runs) < 2 and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)
        stopping.set()
        await asyncio.wait_for(supervisor, timeout=15)

    assert len(runs) >= 2, "the publisher ran again after it died"

    crashes = [record for record in captured if record["event"] == "supervisor.job_crashed"]
    assert crashes, "a job that died silently is the failure D-32 exists to refuse"
    assert crashes[0]["job"] == JOB_CALL_RECORD_PUBLISHER
    assert crashes[0]["reason"] == "RuntimeError", "the CLASS, never the message (A-046)"
