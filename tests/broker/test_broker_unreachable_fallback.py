"""SC1 / CL-01: with RabbitMQ unreachable, every record is still durable.

**Two provocations, because a broker is unreachable in two different ways and a
plan that covered only one would ship the fallback for the rare failure.** The
first closes the publisher's channel under a running publisher — the broker
answered once and then stopped. The second points the composition root at a port
nothing is listening on — the broker was never there at all, which is the
ordinary form of *"``docker compose up -d`` restarts ``rabbitmq`` while ``app``
keeps serving"* and the one ADR-0041 was actually written about. Only the second
would fail if ``_start_publisher`` returned with no task, which is precisely why
D-45 asks for both.

**Neither provocation touches ``rabbitmq_container``.** It is session-scoped and
shared (``conftest.py``), so stopping it would make every later test in the run
fail for an unrelated reason; and a module-scoped second broker costs a 10–20 s
boot repeated across every pytest run — for a failure a closed channel reproduces
exactly. Build the smallest real thing that produces the identical behaviour,
which is the same rule ``test_publish_confirm_failures.py`` follows for its nack.

**Every assertion is read through ``migrate_engine``** — the owner role, subject
to no policy. A fallback that counted itself and wrote nothing would pass a test
that read its own counters; it fails these.

**Five assertions, not one.** ``metadata_dropped_total`` staying at zero is the
whole claim, and the other four are what stop it passing against a test that did
nothing at all: 1,000 rows, every one carrying its ``version_id``, zero body rows,
and both the fallback counter and the body-drop counter moving by exactly 1,000.

**Counter reads are deltas, never absolutes.** ``prometheus_client``'s default
``REGISTRY`` is process-global and the suite shares one process, so a test
asserting an absolute count passes alone and fails after its neighbour. There is
deliberately no autouse registry-reset fixture: it would hide every counter's
cross-test behaviour, which is the one thing these counters exist to make visible.
"""

import asyncio

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.app import _start_publisher, _stop_publisher
from prope.broker.connection import build_connection
from prope.broker.topology import declare_topology
from prope.call_ledger.enqueue import HANDOFF_MAXSIZE, enqueue, handoff, reset_handoff, run_publisher
from tests.broker._helpers import counter_value, fallback_writer, pooled_sessionmaker
from tests.unit import gateway_draft

#: SC1's own number. One thousand calls, each carrying a body, each of which must
#: produce a durable record with a non-null ``version_id``.
SC1_RECORDS = 1000

#: The closed-port provocation runs a smaller batch on purpose: it is asserting a
#: COMPOSITION property — that the failure branch of ``_start_publisher`` starts a
#: job at all — and a thousand records would pay for a thousand single-record
#: transactions to prove a branch that is already proven at the first row.
CLOSED_PORT_RECORDS = 25

#: A port nothing listens on. ``127.0.0.1`` rather than a hostname so the failure
#: is a refused connection rather than a DNS timeout, which would spend
#: ``BROKER_CONNECT_TIMEOUT_SECONDS`` before reaching the same branch.
DEAD_BROKER_URL = "amqp://guest:guest@127.0.0.1:1/"

#: Below the 512-record bound, so the paced producer below never touches the
#: full-handoff branch. See ``_offer`` for why the pacing is not a workaround.
HANDOFF_HEADROOM = 64

COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")
COUNT_BODIES = text("SELECT count(*) FROM ledger.call_body")
COUNT_MISSING_VERSION = text(
    "SELECT count(*) FROM ledger.call_record WHERE version_id IS NULL"
)


async def _committed(migrate_engine: AsyncEngine) -> int:
    """Rows in ``ledger.call_record``, read as the OWNER — never via the fallback."""
    async with migrate_engine.begin() as connection:
        return (await connection.execute(COUNT_RECORDS)).scalar_one()


async def _offer(count: int) -> None:
    """Hand ``count`` records to ``enqueue()`` at a rate the handoff can hold.

    **This pacing is the arrival rate, not a workaround.** ``enqueue()`` is
    synchronous by design (D-25), so a bare ``for`` loop over a thousand calls
    never yields to the event loop and the publisher never runs — the 513th record
    would take the full-handoff branch and be counted as dropped, which would make
    this test about ``HANDOFF_MAXSIZE`` rather than about the fallback. A gateway
    at the stated 50 rps hands records over one request at a time with the loop
    turning in between, which is what the wait below reproduces.
    """
    for index in range(count):
        while handoff().qsize() >= HANDOFF_MAXSIZE - HANDOFF_HEADROOM:
            await asyncio.sleep(0.01)
        enqueue(gateway_draft(call_id=f"cal_{index:026d}"))


async def _wait_for_rows(migrate_engine: AsyncEngine, wanted: int, *, timeout: float) -> int:
    """Poll the OWNER's row count until it reaches ``wanted``. Returns what it saw."""
    deadline = asyncio.get_running_loop().time() + timeout
    written = 0
    while asyncio.get_running_loop().time() < deadline:
        written = await _committed(migrate_engine)
        if written >= wanted:
            return written
        await asyncio.sleep(0.1)
    return written


async def test_a_thousand_records_survive_a_channel_that_closed_under_the_publisher(
    amqp_url: str,
    app_engine: AsyncEngine,
    migrate_engine: AsyncEngine,
) -> None:
    """SC1's first provocation: the broker answered, then stopped answering."""
    reset_handoff()
    before = {
        "fell_back": counter_value("prope_call_ledger_fallback_direct_write_total"),
        "bodies": counter_value(
            "prope_call_ledger_body_dropped_total", {"reason": "fallback"}
        ),
        "dropped": counter_value("prope_call_ledger_metadata_dropped_total"),
    }

    stopping = asyncio.Event()
    connection = await build_connection(amqp_url)
    async with pooled_sessionmaker(app_engine) as sessionmaker, connection:
        # Not ``publisher_channel``: this channel is going to be closed under the
        # publisher on purpose, and re-entering a context manager that closes it
        # again would be asserting against the teardown rather than the outage.
        channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
        await declare_topology(channel)

        publisher = asyncio.create_task(
            run_publisher(
                channel.default_exchange,
                stopping,
                fallback=fallback_writer(sessionmaker),
            )
        )
        try:
            await channel.close()
            await _offer(SC1_RECORDS)
            written = await _wait_for_rows(migrate_engine, SC1_RECORDS, timeout=180.0)
        finally:
            stopping.set()
            await asyncio.wait_for(publisher, timeout=30)

    assert written == SC1_RECORDS, f"{written} of {SC1_RECORDS} records reached PostgreSQL"

    async with migrate_engine.begin() as connection:
        without_version = (await connection.execute(COUNT_MISSING_VERSION)).scalar_one()
        bodies = (await connection.execute(COUNT_BODIES)).scalar_one()

    assert without_version == 0, "100% of gateway calls record a version ID"
    assert bodies == 0, "the fallback is metadata-only by decision (D-28)"

    fell_back = counter_value("prope_call_ledger_fallback_direct_write_total")
    dropped_bodies = counter_value(
        "prope_call_ledger_body_dropped_total", {"reason": "fallback"}
    )
    assert fell_back == before["fell_back"] + SC1_RECORDS
    assert dropped_bodies == before["bodies"] + SC1_RECORDS, (
        "one increment per RECORD, so the counter equals the rows missing from call_body"
    )
    assert counter_value("prope_call_ledger_metadata_dropped_total") == before["dropped"], (
        "SC1's whole claim: with PostgreSQL reachable, a broker outage loses nothing"
    )


async def test_a_broker_that_was_never_reachable_still_produces_durable_records(
    app_engine: AsyncEngine,
    migrate_engine: AsyncEngine,
) -> None:
    """SC1's second provocation, and Task 1's adopted branch under test.

    This is the one that fails if the composition root returns with no task: on
    that path ``enqueue()`` fills the handoff and drops, with no publish attempt
    and therefore no fallback call. It drives the real ``_start_publisher`` rather
    than a hand-built job, because the property under test belongs to the
    composition and not to ``run_publisher``.
    """
    reset_handoff()
    before = {
        "fell_back": counter_value("prope_call_ledger_fallback_direct_write_total"),
        "dropped": counter_value("prope_call_ledger_metadata_dropped_total"),
    }

    application = FastAPI()
    stopping = asyncio.Event()

    async with pooled_sessionmaker(app_engine) as sessionmaker:
        application.state.sessionmaker = sessionmaker
        await _start_publisher(application, DEAD_BROKER_URL, stopping)

        assert application.state.broker is None, "no connection was established"
        assert application.state.publisher is not None, (
            "a broker that was never there must still leave a job running, or SC1's most "
            "ordinary provocation fills the handoff and drops"
        )

        try:
            await _offer(CLOSED_PORT_RECORDS)
            written = await _wait_for_rows(migrate_engine, CLOSED_PORT_RECORDS, timeout=60.0)
        finally:
            stopping.set()
            await _stop_publisher(application)

    assert written == CLOSED_PORT_RECORDS
    assert (
        counter_value("prope_call_ledger_fallback_direct_write_total")
        == before["fell_back"] + CLOSED_PORT_RECORDS
    )
    assert counter_value("prope_call_ledger_metadata_dropped_total") == before["dropped"]
