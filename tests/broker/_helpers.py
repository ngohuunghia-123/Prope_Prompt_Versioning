"""Shared broker-test helpers. Import from here rather than redefining per module.

Three things live here: a management-API reader, a queue-depth reader, and the
small constructors Phase 3's fallback needs at eight call sites. The first two
answer the same kind of question by two different routes on purpose — the
management API is what D-23's "reads them back from the broker" means, and a
passive declare is what gives an immediate message count, because the management
API's statistics refresh on an interval and a test that read depth from it would
be racing a scheduler.
"""

import asyncio
import base64
import json
import urllib.request
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractRobustConnection
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.broker.connection import build_connection
from prope.broker.topology import WORK_QUEUE, declare_topology
from prope.call_ledger.domain import CallRecordDraft
from prope.call_ledger.drain import run_drain
from prope.call_ledger.enqueue import FallbackWriter, HandoffItem
from prope.call_ledger.envelope import CallRecordEnvelope
from prope.call_ledger.fallback import build_fallback_writer
from prope.db.engine import build_engine, build_sessionmaker

#: The default vhost, ``/``, percent-encoded for a URL path segment. ``%2F``
#: rather than a bare slash: the vhost name is one path segment and a raw slash
#: would split it.
DEFAULT_VHOST = quote("/", safe="")

#: ``RabbitMqContainer``'s defaults, from ``RABBITMQ_DEFAULT_USER`` /
#: ``RABBITMQ_DEFAULT_PASS``. Test-only, for a container that lives one session.
MANAGEMENT_USER = "guest"
MANAGEMENT_PASSWORD = "guest"


def handoff_item(draft: CallRecordDraft) -> HandoffItem:
    """The pair ``publish_record`` takes, built the way ``enqueue()`` builds it.

    ``publish_record``'s second positional is a ``HandoffItem`` and not a
    ``CallRecordDraft`` (D-41): ``occurred_at`` is stamped when the CALLER hands
    the record over, so ``write_lag_seconds`` measures the interval it is declared
    to measure. Stamping it here rather than at each call site keeps the eight
    sites from each inventing their own instant.
    """
    return HandoffItem(draft=draft, occurred_at=datetime.now(UTC))


def fallback_writer(sessionmaker: async_sessionmaker[AsyncSession]) -> FallbackWriter:
    """ADR-0041's REAL direct write, bound the way ``prope.app`` binds it.

    Deliberately not a stub. ``fallback_direct_write_total`` only moves on a
    committed row, so a test that passed a no-op here would assert against a
    fallback that did nothing — and the whole claim CL-01 makes is about the row.
    """
    return build_fallback_writer(sessionmaker)


@asynccontextmanager
async def pooled_sessionmaker(
    app_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """The ``prope_app`` role again, over a POOL, for the length of one test.

    **This is what ``prope.app`` actually builds** — ``build_sessionmaker(
    build_engine(url))`` with SQLAlchemy's default pool — so a fallback measured
    over it is measured against the production shape, and D-27's *"roughly 1.5 ms
    per single-record transaction"* is arithmetic about a pooled connection rather
    than about a fresh TCP handshake per record.

    The session fixtures use ``NullPool`` for a reason that still holds and is not
    contradicted here: pytest-asyncio gives every test its own event loop and an
    asyncpg connection is bound to the loop that opened it, so nothing may be
    carried across tests. This engine is created and disposed **inside one test**,
    on one loop, which is why it is a context manager and not a fixture.

    Measured on the development host: 1,000 fallback writes take 17 s pooled and
    188 s unpooled. That difference is not a detail for the shutdown drain — the
    drain has a 3.0 s deadline, and 20 unpooled writes land within a few hundred
    milliseconds of it, which would make a durability assertion a timing race.
    """
    engine = build_engine(app_engine.url.render_as_string(hide_password=False))
    try:
        yield build_sessionmaker(engine)
    finally:
        await engine.dispose()


def counter_value(name: str, labels: dict[str, str] | None = None) -> float:
    """One metric's current value, or ``0.0`` if nothing has touched it.

    **Read as a DELTA at every call site, never as an absolute.**
    ``prometheus_client``'s default ``REGISTRY`` is process-global and the suite
    shares one process, so a test asserting an absolute count passes alone and
    fails after its neighbour — which is the worst failure shape a suite can have.
    Snapshot before, snapshot after, assert on the difference.

    There is deliberately **no autouse registry-reset fixture**: it would hide
    every counter's cross-test behaviour, which is the one thing these counters
    exist to make visible.
    """
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


def _get_json(url: str) -> Any:
    """One authenticated GET against the management API, via the standard library.

    ``urllib.request`` rather than an HTTP client dependency: this is the only
    HTTP call in the test suite, and adding a runtime dependency for it would
    put a package in ``uv.lock`` that no production code imports.
    """
    credentials = f"{MANAGEMENT_USER}:{MANAGEMENT_PASSWORD}".encode()
    request = urllib.request.Request(url)  # noqa: S310 — fixed http:// container URL
    request.add_header("Authorization", "Basic " + base64.b64encode(credentials).decode())
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read())


async def read_queue_from_management_api(management_url: str, queue_name: str) -> dict:
    """The broker's OWN view of a queue, as the management API reports it.

    This is what makes the read-back assertion a read-back: the ``arguments``
    object in the response is the broker's record of what was declared, and a
    test comparing against it cannot pass by reading a dict it built itself.

    Run in a thread because ``urllib`` blocks and the caller is a coroutine.
    """
    url = f"{management_url}/api/queues/{DEFAULT_VHOST}/{quote(queue_name, safe='')}"
    return await asyncio.to_thread(_get_json, url)


async def queue_depth(connection: AbstractRobustConnection, queue_name: str) -> int:
    """How many messages are sitting in ``queue_name``, right now.

    A **passive** declare, which checks existence and reports the counts without
    touching the declaration — the one safe use of ``passive=True``, and
    deliberately not the one D-23 needs, because a passive declare ignores
    arguments entirely and so can never verify them.

    Its own channel each time: a failed declare closes the channel it was issued
    on, and a shared one would take the next assertion down with it.
    """
    async with connection.channel() as channel:
        queue = await channel.declare_queue(queue_name, passive=True)
        return queue.declaration_result.message_count or 0


async def publish_bodies(amqp_url: str, bodies: list[bytes]) -> None:
    """Put raw bytes on the work queue, bypassing ``enqueue`` entirely.

    Deliberately raw: several tests need a message the publish path would never
    produce — a malformed envelope, an unknown ``schema_version`` — and building
    one through ``enqueue`` is impossible by construction, which is the point of
    the envelope model.
    """
    connection = await build_connection(amqp_url)
    async with connection:
        async with connection.channel(publisher_confirms=True) as channel:
            await declare_topology(channel)
            for body in bodies:
                await channel.default_exchange.publish(
                    Message(body, delivery_mode=DeliveryMode.PERSISTENT),
                    routing_key=WORK_QUEUE,
                )


async def publish_drafts(amqp_url: str, drafts: list[CallRecordDraft]) -> None:
    """Put well-formed envelopes for ``drafts`` on the work queue, in order."""
    now = datetime.now(UTC)
    await publish_bodies(
        amqp_url,
        [
            CallRecordEnvelope.from_draft(draft, occurred_at=now).model_dump_json().encode()
            for draft in drafts
        ],
    )


async def drain_until(
    amqp_url: str,
    sessionmaker: async_sessionmaker[AsyncSession],
    predicate: Callable[[], Awaitable[bool]],
    *,
    timeout: float = 30.0,
    **drain_kwargs: Any,
) -> bool:
    """Run the REAL drain until ``predicate`` holds, then stop it. Returns whether it did.

    The stop signal is a directly-settable ``asyncio.Event`` — the shape the
    drain takes precisely because ``loop.add_signal_handler`` is unimplemented
    on Windows, so this is drivable from a test on any platform.
    """
    stopping = asyncio.Event()
    connection = await build_connection(amqp_url)

    async with connection:
        channel = await connection.channel()
        drain = asyncio.create_task(
            run_drain(channel, sessionmaker, stopping=stopping, **drain_kwargs)
        )
        deadline = asyncio.get_running_loop().time() + timeout
        try:
            while asyncio.get_running_loop().time() < deadline:
                if await predicate():
                    return True
                await asyncio.sleep(0.1)
            return False
        finally:
            stopping.set()
            await asyncio.wait_for(drain, timeout=15)
