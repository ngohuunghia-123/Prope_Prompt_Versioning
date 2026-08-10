"""D-12/D-13/D-17: the composed worker, asserted rather than described.

**Assert the composition, not the parts.** ``run_drain`` has its own tests and so
does ``delete_expired_bodies``. What has no test until this file is the wiring:
that the drain running inside ``worker`` reads the **real** per-workspace
retention window rather than the module default, that exactly one consumer
exists, that a stop signal commits the window in flight, and that no HTTP surface
came along for the ride.

**A drain that acks and writes nothing looks healthy, and a retention job that
runs cleanly and deletes nothing looks healthy.** Both failure modes are silent
from the job's own side, so this file follows
``tests/integration/test_body_retention_delete.py``'s posture exactly: **every
assertion is a direct query through ``migrate_engine``** — the owner role,
subject to no policy — or a read of the broker's own view of the queue. Nothing
here asks the code under test what it did and believes the answer.

The one thing asserted about the *process* rather than the data is the absence of
an HTTP surface (D-17), and even that is an AST walk plus an attribute scan
rather than a comment saying so.

Every instant below is on the fixture calendar and the cut-off is pinned by the
``clock`` parameter, so nothing here depends on the day the suite is run.
"""

import ast
import asyncio
import functools
from datetime import timedelta
from pathlib import Path

import pytest
from aio_pika.abc import AbstractRobustConnection
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

import prope.worker
from prope.broker.connection import build_connection
from prope.broker.topology import WORK_QUEUE
from prope.call_ledger.retention_settings import read_retention_window, set_retention_window
from prope.call_ledger.writer import DEFAULT_RETENTION_WINDOW, write_records
from prope.db.session import workspace_transaction
from prope.worker import (
    JOB_CALL_RECORD_DRAIN,
    JOB_EXPIRED_BODY_DELETION,
    ObservedWorkspaces,
    build_retention_resolver,
    run_worker,
    sweep_expired_bodies,
)
from tests.broker._helpers import publish_drafts
from tests.unit import WORKSPACE_A, WORKSPACE_B, day, gateway_draft

#: The stored window for the workspace that has one. Seven days, so it is
#: unmistakably not the 30-day default and the difference is 23 days rather than
#: a rounding.
STORED_WINDOW = timedelta(days=7)

#: The cut-off handed to every sweep in this file. Pinned, never ``now()``: a
#: retention test whose result depends on the calendar date the suite runs on is
#: a test that starts failing on its own.
CUT_OFF = day(66)

#: An interval long enough that the sweep runs once at startup and then stays out
#: of the way, for the tests that are about the drain.
SWEEP_NEVER_AGAIN = 3600.0

COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")
COUNT_BODIES_FOR = text("SELECT count(*) FROM ledger.call_body WHERE workspace_id = :ws")
READ_BODY_TIMES = text(
    """
    SELECT b.created_at, b.expires_at
    FROM   ledger.call_body b
    WHERE  b.call_id = :call_id
    """
)


async def _count(migrate_engine: AsyncEngine, statement, **params) -> int:
    async with migrate_engine.begin() as connection:
        return int((await connection.execute(statement, params)).scalar_one())


async def _consumer_count(connection: AbstractRobustConnection, queue_name: str) -> int:
    """The broker's own count of consumers on ``queue_name``, right now.

    A **passive** declare rather than the management HTTP API: the management
    API's statistics refresh on an interval, so a test reading a consumer count
    from it would be racing a scheduler. A passive declare answers from the
    queue's current state, and it touches no argument, so it cannot disturb the
    one-way declaration it is reading past.

    Its own channel each time — a failed declare closes the channel it was issued
    on, and a shared one would take the next assertion down with it.
    """
    async with connection.channel() as channel:
        queue = await channel.declare_queue(queue_name, passive=True)
        return queue.declaration_result.consumer_count or 0


async def _run_worker_until(app_sessionmaker, amqp_url, predicate, *, timeout=45.0, **kwargs):
    """Run the REAL composed worker until ``predicate`` holds, then stop it.

    Returns ``(satisfied, connection_was_used)``. The stop signal is a
    directly-settable ``asyncio.Event`` — the shape the whole worker takes
    because ``loop.add_signal_handler`` is unimplemented on Windows — so this is
    drivable on any platform.
    """
    stopping = asyncio.Event()
    connection = await build_connection(amqp_url)
    loop = asyncio.get_running_loop()

    async with connection:
        worker = asyncio.create_task(
            run_worker(
                app_sessionmaker,
                connection,
                stopping=stopping,
                clock=lambda: CUT_OFF,
                **kwargs,
            )
        )
        deadline = loop.time() + timeout
        try:
            while loop.time() < deadline:
                if worker.done():
                    await worker
                    break
                if await predicate(connection):
                    return True
                await asyncio.sleep(0.05)
            return False
        finally:
            stopping.set()
            await asyncio.wait_for(worker, timeout=20)


async def _seed_stored_window(app_sessionmaker) -> None:
    async with asyncio.timeout(30):
        await set_retention_window(
            app_sessionmaker,
            WORKSPACE_A,
            STORED_WINDOW,
            updated_by="usr_01J000000000000000000001",
            now=day(1),
        )


# --------------------------------------------------------------------------
# D-11, end to end: the drain inside `worker` reads the REAL window
# --------------------------------------------------------------------------


async def test_the_resolver_worker_builds_takes_the_workspace_id_alone(
    app_sessionmaker,
) -> None:
    """The regression this whole binding exists to prevent, caught here.

    ``drain.py`` calls ``await retention_for(workspace_id)`` — ONE positional
    argument — and ``read_retention_window(sessionmaker, workspace_id)`` takes
    two. The assertion below calls the object ``worker.py`` builds, not the bare
    import, so a regression to the unbound form fails here rather than at runtime
    inside the consumer on the first workspace group.
    """
    await _seed_stored_window(app_sessionmaker)

    resolver = build_retention_resolver(app_sessionmaker)

    assert await resolver(WORKSPACE_A) == STORED_WINDOW
    assert await resolver(WORKSPACE_B) == DEFAULT_RETENTION_WINDOW

    # And the bare two-argument function is genuinely not assignable — the thing
    # the partial exists to fix, stated as a failing call rather than a comment.
    with pytest.raises(TypeError):
        await read_retention_window(WORKSPACE_A)  # type: ignore[call-arg]


async def test_the_resolver_is_built_by_binding_the_sessionmaker(app_sessionmaker) -> None:
    """It is a ``functools.partial`` over the real reader, not a look-alike."""
    resolver = build_retention_resolver(app_sessionmaker)

    assert isinstance(resolver, functools.partial)
    assert resolver.func is read_retention_window
    assert resolver.args == (app_sessionmaker,)


async def test_two_workspaces_get_two_different_expiries_through_the_composed_worker(
    app_sessionmaker, migrate_engine, amqp_url
) -> None:
    """D-11 proved end to end, which is the only thing that stops drift.

    A workspace holding a stored 7-day window gets its body stamped at
    ``created_at + 7 days``; a workspace with no row gets 30. Both read through
    ``migrate_engine``, never through the writer's return value.
    """
    await _seed_stored_window(app_sessionmaker)

    stored = gateway_draft(
        call_id="cal_worker_stored_window_0001",
        workspace_id=WORKSPACE_A,
        created_at=CUT_OFF,
    )
    defaulted = gateway_draft(
        call_id="cal_worker_default_window_001",
        workspace_id=WORKSPACE_B,
        created_at=CUT_OFF,
    )
    await publish_drafts(amqp_url, [stored, defaulted])

    async def both_bodies_written(_connection) -> bool:
        written = await _count(migrate_engine, COUNT_BODIES_FOR, ws=WORKSPACE_A)
        written += await _count(migrate_engine, COUNT_BODIES_FOR, ws=WORKSPACE_B)
        return written == 2

    assert await _run_worker_until(
        app_sessionmaker,
        amqp_url,
        both_bodies_written,
        retention_interval_seconds=SWEEP_NEVER_AGAIN,
    ), "the composed worker did not write both bodies"

    async with migrate_engine.begin() as connection:
        stored_times = (
            await connection.execute(READ_BODY_TIMES, {"call_id": stored.call_id})
        ).one()
        defaulted_times = (
            await connection.execute(READ_BODY_TIMES, {"call_id": defaulted.call_id})
        ).one()

    assert stored_times.expires_at - stored_times.created_at == STORED_WINDOW
    assert defaulted_times.expires_at - defaulted_times.created_at == DEFAULT_RETENTION_WINDOW
    assert stored_times.expires_at != defaulted_times.expires_at


# --------------------------------------------------------------------------
# Exactly one consumer (Pitfall 6, WARN-2's other half, T-02-18)
# --------------------------------------------------------------------------


async def test_the_running_worker_holds_exactly_one_consumer_on_the_queue(
    app_sessionmaker, amqp_url
) -> None:
    """Asserted against the BROKER's count, not by counting objects in-process.

    Counting consumer objects here would assert what this process believes.
    ``prefetch_count`` is applied by the broker, per consumer, so the broker's
    own count is the only number the memory bound actually rests on.
    """
    seen: list[int] = []

    async def one_consumer_is_registered(connection) -> bool:
        count = await _consumer_count(connection, WORK_QUEUE)
        if count > 0:
            seen.append(count)
            # Look twice, a beat apart: a second consumer that appears late
            # would otherwise slip past a single sample.
            return len(seen) >= 3
        return False

    assert await _run_worker_until(
        app_sessionmaker,
        amqp_url,
        one_consumer_is_registered,
        retention_interval_seconds=SWEEP_NEVER_AGAIN,
    ), "the worker never registered a consumer on the queue"

    assert seen == [1, 1, 1], f"the broker reported consumer counts {seen}, expected exactly one"


async def test_the_consumer_is_gone_after_the_worker_stops(app_sessionmaker, amqp_url) -> None:
    """The drain's channel closes on exit, so the queue is left with no consumer."""

    async def a_consumer_exists(connection) -> bool:
        return await _consumer_count(connection, WORK_QUEUE) == 1

    assert await _run_worker_until(
        app_sessionmaker,
        amqp_url,
        a_consumer_exists,
        retention_interval_seconds=SWEEP_NEVER_AGAIN,
    )

    connection = await build_connection(amqp_url)
    async with connection:
        assert await _consumer_count(connection, WORK_QUEUE) == 0


# --------------------------------------------------------------------------
# The stop path commits the window in flight (T-02-19)
# --------------------------------------------------------------------------


class _StopOnFirstSighting(ObservedWorkspaces):
    """Sets the stop event at the exact moment a window is in flight.

    ``note`` is called by the retention resolver, which the drain awaits **after**
    it has collected and grouped a window and **before** it opens the write
    transaction. So a stop set from here is a stop arriving mid-window by
    construction rather than by sleeping and hoping.
    """

    def __init__(self, stopping: asyncio.Event) -> None:
        super().__init__()
        self._stopping = stopping

    def note(self, workspace_id: str) -> None:
        super().note(workspace_id)
        self._stopping.set()


async def test_a_stop_mid_window_commits_that_window_before_the_worker_returns(
    app_sessionmaker, migrate_engine, amqp_url
) -> None:
    records = 3
    drafts = [
        gateway_draft(
            call_id=f"cal_worker_inflight_{index:010d}",
            workspace_id=WORKSPACE_A,
            created_at=CUT_OFF,
        )
        for index in range(records)
    ]
    await publish_drafts(amqp_url, drafts)

    stopping = asyncio.Event()
    connection = await build_connection(amqp_url)
    async with connection:
        await asyncio.wait_for(
            run_worker(
                app_sessionmaker,
                connection,
                stopping=stopping,
                workspaces=_StopOnFirstSighting(stopping),
                retention_interval_seconds=SWEEP_NEVER_AGAIN,
                clock=lambda: CUT_OFF,
            ),
            timeout=60,
        )

    # Through the owner role: the drain's own return value would say nothing
    # about whether the transaction committed.
    assert await _count(migrate_engine, COUNT_RECORDS) == records


# --------------------------------------------------------------------------
# D-12: the retention job actually deletes, and the gap in its enumerator
# --------------------------------------------------------------------------


async def _seed_bodies(app_sessionmaker, workspace_id: str, prefix: str) -> tuple[int, int]:
    """Three bodies expired at the cut-off and two a day short of it.

    Written through the REAL write path — ``created_at`` plus the window — so
    this cannot pass against a writer that stamps something else.
    """
    expired = [
        gateway_draft(
            call_id=f"cal_{prefix}_expired_{index:03d}",
            workspace_id=workspace_id,
            created_at=CUT_OFF - timedelta(days=31) - DEFAULT_RETENTION_WINDOW,
        )
        for index in range(3)
    ]
    kept = [
        gateway_draft(
            call_id=f"cal_{prefix}_kept_{index:03d}",
            workspace_id=workspace_id,
            created_at=CUT_OFF + timedelta(days=1) - DEFAULT_RETENTION_WINDOW,
        )
        for index in range(2)
    ]
    async with workspace_transaction(app_sessionmaker, workspace_id) as session:
        await write_records(session, expired + kept)
    return len(expired), len(kept)


async def test_a_sweep_pass_removes_the_expired_bodies_of_every_enumerated_workspace(
    app_sessionmaker, migrate_engine
) -> None:
    """The job is judged by the data it left behind, not by returning cleanly."""
    _, kept_a = await _seed_bodies(app_sessionmaker, WORKSPACE_A, "swpa")
    _, kept_b = await _seed_bodies(app_sessionmaker, WORKSPACE_B, "swpb")

    async def both() -> tuple[str, ...]:
        return (WORKSPACE_A, WORKSPACE_B)

    await sweep_expired_bodies(app_sessionmaker, both, now=CUT_OFF, chunk_size=2)

    assert await _count(migrate_engine, COUNT_BODIES_FOR, ws=WORKSPACE_A) == kept_a
    assert await _count(migrate_engine, COUNT_BODIES_FOR, ws=WORKSPACE_B) == kept_b


async def test_a_workspace_the_enumerator_omits_keeps_its_expired_bodies(
    app_sessionmaker, migrate_engine
) -> None:
    """The Phase 2 gap, asserted rather than merely written down.

    ``ObservedWorkspaces`` cannot see a workspace this process has drained nothing
    for, because ADR-0045 makes an unscoped cross-tenant read return zero rows and
    ADR-0051's ``access.list_workspaces()`` does not exist until Phase 7. This
    test fixes the boundary in place: if it ever starts failing, somebody closed
    the gap, and this test and ``ObservedWorkspaces``' docstring should be deleted
    together.
    """
    expired_a, kept_a = await _seed_bodies(app_sessionmaker, WORKSPACE_A, "gapa")
    expired_b, kept_b = await _seed_bodies(app_sessionmaker, WORKSPACE_B, "gapb")

    observed = ObservedWorkspaces()
    observed.note(WORKSPACE_A)

    await sweep_expired_bodies(app_sessionmaker, observed.current, now=CUT_OFF, chunk_size=2)

    assert await _count(migrate_engine, COUNT_BODIES_FOR, ws=WORKSPACE_A) == kept_a
    assert (
        await _count(migrate_engine, COUNT_BODIES_FOR, ws=WORKSPACE_B) == expired_b + kept_b
    ), "the unobserved workspace was swept; the Phase 2 gap has moved and this test is stale"
    assert expired_a > 0


async def test_the_composed_worker_sweeps_a_workspace_its_drain_has_seen(
    app_sessionmaker, migrate_engine, amqp_url
) -> None:
    """D-12's scheduler, end to end: the drain notes a workspace, the sweep clears it."""
    _, kept = await _seed_bodies(app_sessionmaker, WORKSPACE_A, "e2e")
    expired_before = await _count(migrate_engine, COUNT_BODIES_FOR, ws=WORKSPACE_A)
    assert expired_before > kept

    # Created AT the cut-off, so this record's own body is 30 days from expiring
    # and the sweep must leave it alone.
    await publish_drafts(
        amqp_url,
        [
            gateway_draft(
                call_id="cal_worker_sweep_trigger_01",
                workspace_id=WORKSPACE_A,
                created_at=CUT_OFF,
            )
        ],
    )

    async def only_unexpired_bodies_remain(_connection) -> bool:
        # kept + the one the drain just wrote
        return await _count(migrate_engine, COUNT_BODIES_FOR, ws=WORKSPACE_A) == kept + 1

    assert await _run_worker_until(
        app_sessionmaker,
        amqp_url,
        only_unexpired_bodies_remain,
        retention_interval_seconds=0.2,
        chunk_size=2,
    ), "the scheduled sweep never removed the expired bodies of the drained workspace"


# --------------------------------------------------------------------------
# D-17: no HTTP surface
# --------------------------------------------------------------------------


def test_worker_imports_no_web_framework() -> None:
    """An AST walk, not a string search — the docstring names ``/healthz`` on purpose.

    Grepping the source for ``fastapi`` or ``/healthz`` would fail on the module
    docstring, which states D-17 at length precisely so a reader finds it. The
    walk asks the only question that matters: does this module import a thing
    that can serve HTTP?
    """
    source = Path(prope.worker.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden = {"fastapi", "starlette", "uvicorn", "http", "socket", "socketserver"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert not (imported & forbidden), f"prope.worker imports {sorted(imported & forbidden)}"


def test_worker_exposes_no_asgi_application_object() -> None:
    """No attribute of the module is an app, a router or anything callable as one.

    ``fastapi`` and ``starlette`` are installed and importable — the assertion is
    not "the package is absent", it is "this module produced no object of those
    types". That is the form that survives the day some other module in the
    process does import them.
    """
    import fastapi
    import starlette.applications
    import starlette.routing

    asgi_types = (
        fastapi.FastAPI,
        fastapi.APIRouter,
        starlette.applications.Starlette,
        starlette.routing.Router,
    )

    offenders = [
        name for name, value in vars(prope.worker).items() if isinstance(value, asgi_types)
    ]
    assert offenders == [], f"prope.worker exposes ASGI objects: {offenders}"


def test_the_two_supervised_jobs_are_the_lock_files_two_residents() -> None:
    """``deployment_target`` names the drain and the retention job. Exactly those."""
    assert JOB_CALL_RECORD_DRAIN == "call_record_drain"
    assert JOB_EXPIRED_BODY_DELETION == "expired_body_deletion"
