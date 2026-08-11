"""D-13: the ASGI application, composed by hand, INT-030's two health routes, and
the exposition surface.

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
bring-up is bounded by a timeout, and a failure is logged and survived.

**A broker that was never reachable starts a fallback-only job, not nothing**
(CL-01, ADR-0041). Until Phase 3 this file caught the bring-up failure and
returned with no task at all, so ``enqueue()`` filled the 512-record handoff and
then dropped — with no publish attempt and therefore no fallback call, in exactly
the scenario ADR-0041 was written about. The composition root now chooses between
two job bodies instead: a publisher on the success branch, and a job that reads
the handoff and writes every record straight to PostgreSQL on the failure branch.
Choosing between two job bodies is what a composition root is for; the rejected
alternative was starting the publisher anyway with a nullable exchange, which
would put the degraded case inside the function that handles the healthy one and
make an ``AttributeError`` caught by a bare ``except`` the mechanism.

**``app`` acquires a database write path it did not have**, and ADR-0041 names
that consequence explicitly. ``app.state.sessionmaker`` existed already and was
used only by the management routes through ``get_sessionmaker``;
:func:`prope.call_ledger.fallback.build_fallback_writer` binds it into the
publisher here. Every record this process writes carries a ``workspace_id`` that
decides which tenant's rows the transaction may touch, and the write goes through
``workspace_transaction`` unchanged for that reason.

**Both job bodies are supervised, and neither is a bare ``create_task``** (D-32).
A publisher started as a bare task ends silently when an exception escapes it:
every later ``enqueue`` fills the handoff and then drops, with no crash, no
restart and nothing in ``/readyz``, which is the database alone by decision. The
fallback makes that reachable, because a fallback can raise where
``publish_record`` previously could not. ``prope.supervisor.supervise`` already
restarts a crashed job with backoff and drains on stop, and D-14 built it *"to
accommodate later jobs without being redesigned"* — this is its first host outside
``worker``. A job made **entirely** of fallback calls is the one that needs the
restart most, which is why the degraded branch goes through ``supervise`` too.
Rejected: a bare ``try/except`` loop inside ``run_publisher``; it handles the
raise this phase can imagine and not the one it cannot, and it duplicates backoff
the project already owns and tests.

**INT-030, and D-16's final form.** ``/healthz`` is process liveness and touches
nothing — no database, no broker, no module. ``/readyz`` is **the database
alone**, and that is its final semantics from the first line it was written:
Phase 3 built the fallback that rule already assumed and deleted no part of it.
The consequence for this phase is written at :func:`readyz` rather than only in a
plan: a broker outage now costs bodies and nothing else, and the loss window that
survives is A-139's — a hard kill loses whatever is in the 512-record handoff,
which a graceful stop drains.

**``/metrics`` is the eighth path, and it is a ROUTE rather than a mount**
(D-39, ADR-0030). A metric no scraper can reach is an alert rule that is true on
paper, so the registry is served from the process that serves HTTP. The reason it
is not ``app.mount(make_asgi_app())`` is written at :func:`create_app`'s
``metrics`` handler at length, because it is the kind of decision a later reader
would otherwise "simplify" into a mount: a ``Mount`` is invisible to
``prope.session_auth.assembled_routes``, and therefore to every route assertion in
this repository. **Two consequences ride along and both are recorded rather than
absorbed:** twelve of the eighteen metrics are absent or partial here, because
``prometheus_client``'s registry is per process and ``worker`` serves no HTTP
(``OQ-026``); and ``call-ledger.lock.yml``'s ``apis.exposes`` block does not
declare this path, which ``interfaces.md`` itself says it should have gained
during step 6 (``OQ-026``, second clause).

**The action registry is read into an immutable mapping at startup** (ADR-0038).
No TTL, no invalidation: the safety argument is a deploy ordering — ADR-0031
migrates before it restarts — so *adding* an action is safe by construction, and
*removing* one is already a coordinated multi-file change under A-120's closed
vocabulary.

It is eager rather than lazy on first use. A lazy load would satisfy the deploy
ordering too, and it would make the cache's contents a function of *when the
first append happened* rather than of when the process started — which is exactly
the variable ADR-0038's one named sharp edge turns on.

**A database that is unreachable at startup fails startup here, where a broker
that is unreachable does not, and the asymmetry is deliberate.** A process with
no registry cannot record a state change and has no path back to one: every
append would fail with ``unknown_action`` and page a module for somebody else's
composition bug, while ``/readyz`` answered 200. A crash loop is the louder
failure and the better-behaved one — it names the real dependency and it heals
when the dependency returns. Adopted UNCONFIRMED; see plan 05-01 Task 3 for the
option that was refused.

**This is not a route.** ``prope.property_history`` mounts nothing, and this line
does not change that. The only two symbols this file takes from that package are
``load_action_registry`` and ``install_registry``, and
``tests/architecture/test_history_registry_is_installed_at_process_start.py``
asserts the set is exactly those two.

**A-046.** The log lines here carry an event name and, at most, an exception's
class. An application that logged its settings would log ``PROPE_DATABASE_URL``
and ``PROPE_BROKER_URL``, both of which carry credentials.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_PLAIN_0_0_4, REGISTRY, generate_latest
from sqlalchemy import text

from prope.broker.connection import build_connection, publisher_channel
from prope.broker.topology import declare_topology
from prope.call_ledger.api import router as call_ledger_router
from prope.call_ledger.enqueue import (
    HANDOFF_DRAIN_DEADLINE_SECONDS,
    HANDOFF_POLL_SECONDS,
    drain_handoff_on_stop,
    handoff,
    publish_or_fall_back,
    reset_handoff,
    run_publisher,
)
from prope.call_ledger.fallback import build_fallback_writer
from prope.call_ledger.schemas import install_error_envelope
from prope.db.engine import Settings, build_engine, build_sessionmaker
from prope.observability import configure_logging
from prope.property_history.registry import install_registry, load_action_registry
from prope.supervisor import supervise

log = structlog.get_logger(__name__)

#: The two job bodies this process may run, named. Exactly one of them runs, and
#: which one is decided once, at broker bring-up. The names are the supervisor's
#: task names and the ``job`` field on a ``supervisor.job_crashed`` line, so they
#: are a closed set fixed in source — which is what keeps that field safe as a log
#: field under A-046. ``prope.worker`` names its own two the same way; the closed
#: set across the two processes is four.
JOB_CALL_RECORD_PUBLISHER = "call_record_publisher"
JOB_CALL_RECORD_FALLBACK = "call_record_fallback"

#: How long the lifespan will wait for the broker before serving without it.
#:
#: It exists because the alternative to a bound is an unbounded one: a broker
#: whose host resolves and does not answer would hold startup open indefinitely,
#: and a process that never finishes starting is worse than one that starts
#: degraded — the compose healthcheck cannot tell them apart, and ``/readyz``
#: never gets a chance to say the database is fine.
BROKER_CONNECT_TIMEOUT_SECONDS = 10.0

#: How long shutdown waits for the supervised publisher to finish stopping.
#:
#: **DERIVED, not chosen.** See ``enqueue.HANDOFF_DRAIN_DEADLINE_SECONDS``, which
#: carries the whole argument: the stop path now DRAINS the handoff before it
#: returns, so if the inner deadline ever equalled or exceeded this wait, the
#: ``cancel()`` below would land while the drain was still working and the
#: remainder count would never run — which reproduces CR-02 with more machinery.
#: The relationship is invisible from either file, so it is arithmetic rather than
#: two literals with a comment; ``tests/broker/test_handoff_shutdown_drain.py``
#: asserts the inequality so a future "simplification" back to two numbers fails
#: loudly.
#:
#: The +2.0 s margin covers ``wait_for``'s own overhead and the
#: ``AsyncExitStack`` unwinding of channel and connection that follows.
PUBLISHER_STOP_TIMEOUT_SECONDS = HANDOFF_DRAIN_DEADLINE_SECONDS + 2.0

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
    """Open the connection and channel, declare the topology, start a job.

    Everything it builds is put on ``app.state`` behind one ``AsyncExitStack``,
    so shutdown unwinds in the reverse order it was built rather than in
    whatever order somebody remembers.

    **A failure here is survived rather than raised** — see the module
    docstring. The exception's class reaches the log and its message does not: at
    this depth the message is liable to contain the broker URL, which carries
    credentials (A-046).

    **Both branches start a supervised job, and ``application.state.publisher``
    holds the ``supervise`` task either way** — so ``_stop_publisher`` needs no
    branch of its own. ``supervise()`` blocks until every job it runs has
    returned, and a lifespan cannot block because it yields, which is why it is
    wrapped in ``create_task`` rather than awaited.
    """
    # Bound before the broker is even attempted, because both branches need it:
    # the publisher passes it to every failure site, and the degraded job IS it.
    fallback = build_fallback_writer(application.state.sessionmaker)

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
        log.warning("app.broker_unavailable", reason=type(error).__name__)

        async def fallback_only_job() -> None:
            """Every record straight to PostgreSQL. There is no exchange.

            The degraded half of Task 1's adopted shape. It is the publisher loop
            with the publish removed rather than a second mechanism: same poll,
            same per-item catch, and the same shared stop drain, so CR-02 is
            closed on this branch as well as on the healthy one.

            **The consequence a human is being asked to rule on, written where it
            happens:** a process that starts against a dead broker never publishes
            at all until it is restarted, because ``connect_robust``'s recovery is
            attached to a connection that was never established. Records are
            durable throughout — that is the point — but the work queue stays
            empty and the drain has nothing to do.
            """
            queue = handoff()
            while not stopping.is_set():
                try:
                    item = await asyncio.wait_for(
                        queue.get(), timeout=HANDOFF_POLL_SECONDS
                    )
                except TimeoutError:
                    continue

                try:
                    await publish_or_fall_back(item, None, fallback)
                finally:
                    queue.task_done()

            await drain_handoff_on_stop(None, fallback)

        application.state.publisher = asyncio.create_task(
            supervise({JOB_CALL_RECORD_FALLBACK: fallback_only_job}, stopping)
        )
        return

    application.state.broker = stack

    async def publisher_job() -> None:
        """D-14's shape: a name and a zero-argument coroutine factory."""
        await run_publisher(channel.default_exchange, stopping, fallback=fallback)

    application.state.publisher = asyncio.create_task(
        supervise({JOB_CALL_RECORD_PUBLISHER: publisher_job}, stopping)
    )
    log.info("app.broker_ready")


async def _stop_publisher(application: FastAPI) -> None:
    """Stop the publisher task, then close the channel and the connection.

    **The cancel is in the ``except`` clause and not after the wait** (WR-14,
    CR-03). On the clean path ``wait_for`` returns and there is nothing to cancel;
    the trailing ``if not publisher.done(): publisher.cancel()`` it replaces was a
    branch that could not be taken, and a safety net that reads as if it were doing
    something is worse than no net, because it is what a later reader trusts. On
    the two branches below it is reachable in the way that matters: ``wait_for``
    requests a cancel it may not be able to complete — the task may catch and
    ignore it, which is CPython's own stated reason for keeping a second cancel
    available — and an outer ``CancelledError`` can arrive with the publisher still
    pending. Leaving a supervised publisher running behind a lifespan that has
    ended is the outcome this refuses.

    Both exceptions stay swallowed, as before: the caller's ``finally`` must reach
    ``reset_handoff()``, whose omission poisons every later ``enqueue()`` in the
    process.
    """
    publisher = getattr(application.state, "publisher", None)
    if publisher is not None:
        try:
            await asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)
        except (TimeoutError, asyncio.CancelledError):
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

    # ADR-0038: eager, immutable, and a failure here fails startup.
    async with application.state.sessionmaker() as session:
        install_registry(await load_action_registry(session))

    stopping = asyncio.Event()
    application.state.stopping = stopping
    await _start_publisher(application, settings.broker_url, stopping)

    log.info("app.started")
    try:
        yield
    finally:
        stopping.set()
        await _stop_publisher(application)
        # The handoff belongs to a process's SERVING LIFETIME, and a lifespan
        # that ends is that boundary. ``drain_handoff_on_stop`` shut the queue
        # down, which is one-way for the queue object, and ``handoff()`` caches in
        # a module global — so without this every later ``enqueue()`` in this
        # process would take the ``QueueShutDown`` branch and count a drop,
        # forever. Harmless in a container that exits; not harmless in a test
        # process, or in any future in-process restart.
        reset_handoff()
        await engine.dispose()
        log.info("app.stopped")


def create_app() -> FastAPI:
    """The one assembled application. Every route it serves is named below.

    ``docs_url``, ``redoc_url`` and ``openapi_url`` are all ``None``. INT-028's
    spec line is *"generated from FastAPI + pydantic v2 -> OpenAPI"* — generated,
    from the code, at build time — and nothing says the schema is **served**. An
    unauthenticated ``/docs`` behind Caddy's single ingress would be a route
    nobody decided to have, and it would also be the ninth, tenth and eleventh
    paths in a table this phase asserts holds eight. ``app.openapi()`` still
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
        this module: the process can still record every call through ADR-0041's
        inline fallback, so withholding readiness would take the gateway out of
        service to protect a path that is working — and readiness that cascades
        converts one module's outage into every module's, on a host with no HA.
        Phase 3 did not rewrite this rule; it built the fallback the rule always
        assumed.

        **The Phase 3 consequence, at the code rather than only in a plan.**
        CL-01 is closed. A broker outage now costs **bodies and nothing else**:
        every record the broker refuses is written straight to
        ``ledger.call_record`` with its ``version_id``, its body dropped and
        counted on ``prope_call_ledger_body_dropped_total``, and
        ``prope_call_ledger_metadata_dropped_total`` means what ADR-0041 says it
        means — **both** the broker and the database were unavailable. So this
        endpoint answering 200 during a broker outage is now a true statement
        about durability rather than a knowing gap.

        **What survives, named rather than implied.** The remaining loss window is
        A-139's: a hard kill loses whatever is in the 512-record handoff, which a
        graceful stop drains (CR-02) and counts whatever it could not reach. And
        until CL-02's idempotent upsert lands, a record whose confirm timed out is
        written by the fallback and then redelivered by the broker, where the
        second arrival dead-letters rather than being absorbed.

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

    @application.get("/metrics", response_class=Response, include_in_schema=True)
    async def metrics() -> Response:
        """The Prometheus exposition of the default registry. ADR-0030, D-39.

        **Unversioned and sessionless, and both halves have a reason.** A-045
        puts operational surfaces outside ``/api/v1``, which is where
        ``/healthz`` and ``/readyz`` already sit; this route joins them for a
        different reason than they did — an operator has no session, and a
        *scraper* has no session and never will. It also declares no
        ``ManagementAction``, because call-ledger **cannot** check a permission:
        ADR-0018 forbids this module an outbound edge to access-control, so
        there is nothing here to authorise against. And, following
        :func:`readyz`, the body is **not** the A-045 envelope — a Prometheus
        exposition is not a management-API refusal, and wrapping it in one would
        make it unparseable by the only client it has.

        **A plain route, never ``app.mount(make_asgi_app())``, and that
        is a decision rather than a mounting detail.** A mounted ASGI app is a
        Starlette ``Mount``, which carries neither ``effective_route_contexts``
        nor a ``dependant`` — and
        :func:`prope.session_auth.assembled_routes` appends a route only if it
        has one of those two. So a mount is skipped by the helper, and therefore
        absent from **both** the assembled route table and ``app.openapi()``.
        Nothing in the suite would notice: the count assertions compare a table
        built *from* ``assembled_routes`` against a literal list, and the
        raw-``app.routes`` walk asserts only that ``/docs``, ``/redoc`` and
        ``/openapi.json`` are absent. **A served, unauthenticated path that
        every route assertion in the repository is blind to is exactly the shape
        AC-10 exists to refuse** — the same class of hole Broken Window #4
        records, one layer out: a route the *helper* cannot see rather than one
        the *test* cannot see. Mounting at ``/metrics`` also serves ``/metrics/``
        with a 307 in front of it, which is the smaller second reason.

        **``CONTENT_TYPE_PLAIN_0_0_4``, not ``CONTENT_TYPE_LATEST``.** In
        ``prometheus-client`` 0.26.0 ``CONTENT_TYPE_LATEST`` is
        ``text/plain; version=1.0.0; charset=utf-8`` while ``generate_latest``
        emits the 0.0.4 text format; the library's own ``choose_encoder`` pairs
        this function with ``CONTENT_TYPE_PLAIN_0_0_4`` and reaches for the
        1.0.0 label only when a client explicitly asked for it. The constant's
        name says "latest"; its value is a **format claim**, and labelling this
        payload 1.0.0 would be a claim the payload does not honour. Written here
        so a later reader does not "modernise" it. Content negotiation through
        ``choose_encoder`` is available and is deliberately not used: negotiation
        is a feature nothing in this deployment asks for, and the one-line form
        is what the library itself defaults to.

        **What is readable here, and what is not (``OQ-026``).**
        ``prometheus_client``'s registry is **per process** and Prope runs two.
        ``worker`` serves no HTTP by D-17 — derived from ADR-0028 rather than
        chosen, and so not this phase's to reverse. Eight metrics therefore exist
        only in ``worker`` and are absent from this response entirely:
        ``written_total``, ``write_lag_seconds``, ``queue_depth``,
        ``dlq_depth``, ``redelivered_total``, ``retention_deleted_total``,
        ``oldest_body_age_seconds`` and ``ceiling_check_total``. Four more —
        ``unpriced_total``, ``unknown_usage_total``, ``missing_version_id_total``
        and ``duplicate_call_id_total`` — are incremented in **both** processes,
        so what is served here is a **partial** count of each. Three of the
        declared alerts (``LedgerWriteLagHigh``, ``LedgerRetentionOverdue``,
        ``LedgerDuplicateCallIds``) read metrics on that list.
        ``docs/brainstorm/open_questions/OQ-026.md`` carries the whole list and
        the four rejected answers; it is raised rather than absorbed.

        **``include_in_schema=True`` is load-bearing rather than incidental.**
        Excluding it would make the served table and the OpenAPI schema
        disagree, which is the exact hole
        ``test_the_openapi_schema_agrees_with_the_route_table`` says it exists to
        close.
        """
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_PLAIN_0_0_4)

    return application


#: The ASGI application ``Makefile``'s ``run`` target and the compose command
#: name: ``uvicorn prope.app:app``. Built at import so ``prope.app:app`` resolves;
#: everything that needs an environment is read in the lifespan instead.
app = create_app()
