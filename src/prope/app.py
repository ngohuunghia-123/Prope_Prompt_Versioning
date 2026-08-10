"""D-13: the ASGI application, composed by hand, and INT-030's two health routes.

``prope.app:app`` is what ``Makefile``'s ``run`` target has pointed at since
Phase 1, with a comment saying the module arrives in phase 2. It starts working
here.

**Why not a ``register()`` hook over a declared module list, and why not
auto-discovery by filename.** The same words ``prope.worker`` uses, because it is
the same decision on the other process. AC-10 and prompt-registry's
route-uniqueness rule both assert properties of the *assembled* route table —
what is mounted, in total, once every module has had its say — and **a route that
can appear because a file was named a certain way is precisely the shape those
tests exist to refuse**: the assertion would be checking a list the discovery
mechanism also produced. Here the list is the import block below, and a route
nobody wrote a line for cannot be served. Seven more modules mount their routers
by somebody editing this file. The cost is the mechanism.

**Both processes declare the broker topology, from one definition** (D-24). This
lifespan calls ``declare_topology`` on publisher startup and ``prope.worker``
calls the same function on consumer startup. It is idempotent and
order-independent, and a mismatch between the two is structurally impossible
because there is one definition rather than two agreeing ones. The
worker-declares-only shape was rejected on a specific ground: it makes deploy
ordering a **data-loss** question on the one path that must never raise — start
``app`` first and every publish before the worker's first boot is unroutable.

**One long-lived robust connection with a single confirm-mode channel, not a
pool.** This resolves the CONTEXT discretion item at the composition root rather
than at a call site. D-25 puts exactly **one** background publisher task on this
channel, so a pool would be idle capacity bought with a lifecycle to get wrong,
and ``connect_robust`` already supplies the transparent reconnection a pool is
usually reached for. ``prope.broker.connection`` states the same and is the
module that changes if a second publisher ever appears.

**A broker that is not there does not stop this process from serving**, and that
is D-16 applied at startup rather than only at ``/readyz``. Readiness says a
broker outage is degraded-and-counted and never un-readiness; a lifespan that
raised on a failed broker connect would defeat that by refusing to come up at
all, taking the gateway down to protect a path that is working. So the broker
bring-up is bounded by a timeout, and a failure is logged, counted by the
existing publish counters when records start dropping, and survived.

**INT-030, and D-16's final form.** ``/healthz`` is process liveness and touches
nothing — no database, no broker, no module. ``/readyz`` is **the database
alone**, and that is its final semantics from the first line it is written:
nothing in Phase 3 deletes a readiness rule it inherited from here. The
consequence for *this* phase is written at :func:`readyz` rather than only in the
plan, because it is a real gap: ADR-0041's inline fallback does not exist yet, so
there is a window in which the broker is down, readiness is green, and records
genuinely are lost. ``prope_call_ledger_metadata_dropped_total`` is what makes it
measurable, and CL-01 is what closes it.

**A-046.** The log lines here carry an event name and, at most, an exception's
class. An application that logged its settings would log ``PROPE_DATABASE_URL``
and ``PROPE_BROKER_URL``, both of which carry credentials.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager, suppress

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from prope.broker.connection import build_connection, publisher_channel
from prope.broker.topology import declare_topology
from prope.call_ledger.api import router as call_ledger_router
from prope.call_ledger.enqueue import run_publisher
from prope.call_ledger.schemas import install_error_envelope
from prope.db.engine import Settings, build_engine, build_sessionmaker
from prope.observability import configure_logging

log = structlog.get_logger(__name__)

#: How long the lifespan will wait for the broker before serving without it.
#:
#: It exists because the alternative to a bound is an unbounded one: a broker
#: whose host resolves and does not answer would hold startup open indefinitely,
#: and a process that never finishes starting is worse than one that starts
#: degraded — the compose healthcheck cannot tell them apart, and ``/readyz``
#: never gets a chance to say the database is fine.
BROKER_CONNECT_TIMEOUT_SECONDS = 10.0

#: How long shutdown waits for the background publisher to notice ``stopping``.
#: ``run_publisher`` polls the handoff on a 0.1 s timeout, so this is generous by
#: an order of magnitude and exists only so a wedged task cannot hang a deploy.
PUBLISHER_STOP_TIMEOUT_SECONDS = 5.0

#: How long ``/readyz`` waits for the database before calling it unreachable.
#:
#: A readiness probe that hangs is reported unhealthy anyway, by the
#: healthcheck's own timeout, with a reason nobody can read. Answering ``503``
#: with the failed check named is strictly more information than timing out.
READINESS_TIMEOUT_SECONDS = 2.0

#: The cheapest statement that proves a connection was established and the
#: server answered. Not a table read: ``/readyz`` must not depend on the tenant
#: policy, on a grant, or on any row existing.
READINESS_PROBE = text("SELECT 1")


async def _start_publisher(
    application: FastAPI, broker_url: str, stopping: asyncio.Event
) -> None:
    """Open the connection and channel, declare the topology, start the publisher.

    Everything it builds is put on ``app.state`` behind one ``AsyncExitStack``,
    so shutdown unwinds in the reverse order it was built rather than in
    whatever order somebody remembers.

    **A failure here is survived rather than raised** — see the module
    docstring. The exception's class reaches the log and its message does not: at
    this depth the message is liable to contain the broker URL, which carries
    credentials (A-046).
    """
    stack = AsyncExitStack()
    try:
        connection = await asyncio.wait_for(
            build_connection(broker_url), timeout=BROKER_CONNECT_TIMEOUT_SECONDS
        )
        await stack.enter_async_context(connection)
        channel = await stack.enter_async_context(publisher_channel(connection))
        # D-24: the same function ``prope.worker`` calls, from the same
        # definition. Idempotent, so both declaring costs nothing and neither
        # depending on the other is the point.
        await declare_topology(channel)
    except Exception as error:
        await stack.aclose()
        application.state.broker = None
        application.state.publisher = None
        log.warning("app.broker_unavailable", reason=type(error).__name__)
        return

    application.state.broker = stack
    application.state.publisher = asyncio.create_task(
        run_publisher(channel.default_exchange, stopping)
    )
    log.info("app.broker_ready")


async def _stop_publisher(application: FastAPI) -> None:
    """Stop the publisher task, then close the channel and the connection."""
    publisher = getattr(application.state, "publisher", None)
    if publisher is not None:
        with suppress(TimeoutError, asyncio.CancelledError):
            await asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)
        if not publisher.done():
            publisher.cancel()
        application.state.publisher = None

    stack = getattr(application.state, "broker", None)
    if stack is not None:
        await stack.aclose()
        application.state.broker = None


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Build the runtime objects, serve, then take them down in reverse.

    ``Settings()`` is read **here** and not at import: importing this module must
    not require an environment, or the route-table test could not import the
    application it asserts about and ``prope.app:app`` could not be inspected by
    anything that is not already deployed.

    ``configure_logging()`` gets its second production caller here, after
    ``prope.worker.main``.
    """
    configure_logging()
    settings = Settings()

    engine = build_engine(settings.database_url)
    application.state.engine = engine
    application.state.sessionmaker = build_sessionmaker(engine)

    stopping = asyncio.Event()
    application.state.stopping = stopping
    await _start_publisher(application, settings.broker_url, stopping)

    log.info("app.started")
    try:
        yield
    finally:
        stopping.set()
        await _stop_publisher(application)
        await engine.dispose()
        log.info("app.stopped")


def create_app() -> FastAPI:
    """The one assembled application. Every route it serves is named below.

    ``docs_url``, ``redoc_url`` and ``openapi_url`` are all ``None``. INT-028's
    spec line is *"generated from FastAPI + pydantic v2 -> OpenAPI"* — generated,
    from the code, at build time — and nothing says the schema is **served**. An
    unauthenticated ``/docs`` behind Caddy's single ingress would be a route
    nobody decided to have, and it would also be the sixth, seventh and eighth
    paths in a table this phase asserts holds seven. ``app.openapi()`` still
    builds the schema, which is what the route-table test walks.
    """
    application = FastAPI(
        title="Prope",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    install_error_envelope(application)
    application.include_router(call_ledger_router)

    @application.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Process liveness. Touches nothing, and that is the whole contract.

        INT-030: *"``/healthz`` is process liveness everywhere ... and must never
        touch the database, the broker, or another module"*. A ``/healthz`` that
        checked the database would restart the process every time the database
        blinked, because it is ``/healthz`` and not ``/readyz`` that owns
        restarts — turning one dependency's outage into a crash loop that
        outlives it.

        Unversioned, outside ``/api/v1``, per A-045. No session dependency: a
        health check the operator cannot reach is not a health check.
        """
        return {"status": "alive"}

    @application.get("/readyz")
    async def readyz(request: Request) -> JSONResponse:
        """The database alone. **This is its final form** (D-16, INT-030).

        A **broker outage is degraded-and-counted, never un-readiness**. The
        reasoning is INT-030's and it is about blast radius rather than about
        this module: the process can still record every call once ADR-0041's
        inline fallback exists, so withholding readiness would take the gateway
        out of service to protect a path that is working — and readiness that
        cascades converts one module's outage into every module's, on a host
        with no HA. Nothing in Phase 3 rewrites this rule; Phase 3 builds the
        fallback the rule already assumes.

        **The Phase 2 consequence, at the code rather than only in a plan.** The
        fallback does **not** exist yet. ``enqueue()`` counts and drops on a full
        handoff and on every failed publisher confirm, and there is no idempotent
        upsert on ``call_id`` either. So for one phase there is a window in which
        the broker is down, **this endpoint answers 200, and records genuinely
        are lost**. That is a knowing gap, not an oversight:
        ``prope_call_ledger_metadata_dropped_total`` makes it measurable rather
        than merely admitted, and CL-01 and CL-02 are what close it.

        ``503`` names the failed check and **does not restart the process** —
        it removes the container from the compose healthcheck's healthy set, and
        ``/healthz`` owns restarts.

        The body is not the A-045 envelope, deliberately: INT-030's contract is
        *"the status code and the per-module table"* with no schema, and a
        readiness answer is not a management-API refusal. The failed check is
        named and the driver's message is not — at this depth it can quote the
        connection string.
        """
        engine = getattr(request.app.state, "engine", None)
        if engine is not None:
            try:
                async with engine.connect() as connection:
                    await asyncio.wait_for(
                        connection.execute(READINESS_PROBE),
                        timeout=READINESS_TIMEOUT_SECONDS,
                    )
            except Exception as error:
                log.warning("app.not_ready", reason=type(error).__name__)
            else:
                return JSONResponse(
                    status_code=200, content={"status": "ready", "checks": ["database"]}
                )

        return JSONResponse(
            status_code=503, content={"status": "not_ready", "failed_check": "database"}
        )

    return application


#: The ASGI application ``Makefile``'s ``run`` target and the compose command
#: name: ``uvicorn prope.app:app``. Built at import so ``prope.app:app`` resolves;
#: everything that needs an environment is read in the lifespan instead.
app = create_app()
