"""INT-030 and D-16: what liveness touches, and what readiness is allowed to say.

Two assertions carry this file, and each is shaped against an answer that looks
reasonable and is wrong.

**``/healthz`` must answer while the database is unreachable.** The obvious
liveness check queries the database. INT-030 forbids it — *"``/healthz`` is
process liveness everywhere ... and must never touch the database, the broker, or
another module"* — and the reason is that ``/healthz`` owns **restarts**. A
liveness probe that fails when the database blinks restarts the process, and a
restart does not fix a database, so one dependency's outage becomes a crash loop
that outlives it.

**``/readyz`` must answer 200 while the broker is unreachable.** This is D-16 and
it is the one somebody will try to "fix". A broker outage is
degraded-and-counted, never un-readiness: the process can still record every call
once ADR-0041's inline fallback exists, so withholding readiness would take the
gateway out of service to protect a path that is working — and readiness that
cascades converts one module's outage into every module's, on a host with no HA.

**The settings are pointed at unreachable endpoints rather than the containers
being stopped.** The Postgres and RabbitMQ fixtures are session-scoped and shared
with the rest of the suite; stopping either to make a point here would take
everything else down with it.

The broker-unreachable test runs the **real lifespan**, which is the only way to
assert the property that matters underneath D-16: **a broker that is not there
does not stop this process from serving.** A lifespan that raised on a failed
broker connect would defeat the readiness rule by refusing to come up at all.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.app import create_app, lifespan
from prope.db.engine import build_engine, build_sessionmaker
from tests.integration._asgi import call

#: A host/port nothing listens on. Port 1 on the loopback refuses immediately
#: rather than hanging, which keeps these tests fast and keeps what they assert
#: about — the answer, not the timeout — unambiguous.
UNREACHABLE_DATABASE_URL = (
    "postgresql+asyncpg://prope_app:not-a-password@127.0.0.1:1/nothing_listens_here"
)
UNREACHABLE_BROKER_URL = "amqp://guest:guest@127.0.0.1:1/"


@pytest.fixture
def unreachable_database_app():
    """The real application, with its engine pointed at a closed port."""
    application = create_app()
    engine = build_engine(UNREACHABLE_DATABASE_URL)
    application.state.engine = engine
    application.state.sessionmaker = build_sessionmaker(engine)
    return application


async def test_healthz_answers_200_with_the_database_unreachable(
    unreachable_database_app,
) -> None:
    """Liveness is the process, and the process is running."""
    response = await call(unreachable_database_app, "GET", "/healthz")

    assert response.status_code == 200, response.body
    assert response.json() == {"status": "alive"}


async def test_healthz_answers_200_with_no_engine_at_all() -> None:
    """The strongest form: there is nothing on ``app.state`` for it to touch.

    An application whose lifespan has not run has no engine, no sessionmaker and
    no broker. ``/healthz`` still answers, because it reads none of them — which
    is what "touches nothing" means when it is a property rather than a habit.
    """
    response = await call(create_app(), "GET", "/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_readyz_answers_503_naming_the_database_when_it_is_unreachable(
    unreachable_database_app,
) -> None:
    """``503`` with the failed check named, and the driver's words nowhere in it.

    INT-030: *"503 not ready with a body naming the failed check"*. The name is
    the check, not the error — a driver's message at this depth can quote the
    connection string, which carries credentials (A-046).
    """
    response = await call(unreachable_database_app, "GET", "/readyz")

    assert response.status_code == 503, response.body
    assert response.json() == {"status": "not_ready", "failed_check": "database"}

    body = response.body.decode()
    assert "not-a-password" not in body
    assert "127.0.0.1" not in body


async def test_readyz_answers_503_when_the_lifespan_has_not_run() -> None:
    """No engine is not ready. It is also not a crash.

    A ``500`` here would be read by the compose healthcheck as a failing check
    anyway, but it would not name one, and INT-030's whole contract for this
    route is the status code plus the named check.
    """
    response = await call(create_app(), "GET", "/readyz")

    assert response.status_code == 503
    assert response.json()["failed_check"] == "database"


async def test_readyz_answers_200_with_the_broker_unreachable(
    monkeypatch: pytest.MonkeyPatch, app_engine: AsyncEngine
) -> None:
    """**D-16.** The broker is down, readiness is green, and the process serves.

    Run through the real lifespan, because the property has two halves and only
    one of them is about the route:

    1. The application **starts** with no broker. A lifespan that raised here
       would make a broker outage prevent ``app`` from coming up at all, which
       is a harder failure than the un-readiness D-16 refuses.
    2. ``/readyz`` answers ``200`` anyway, because readiness is the database
       alone and the database is fine.

    **The one-phase gap this test used to make visible is closed, and the
    assertion got STRONGER rather than being deleted.** Phase 2 asserted
    ``application.state.publisher is None`` here, and the paragraph beside it said
    that in exactly this state ``enqueue()`` fills its bounded handoff and then
    counts and drops — readiness green, records lost. CL-01 closed that: a broker
    that was never reachable now starts a **fallback-only job**, which writes every
    record straight to PostgreSQL, so readiness being green in this state is a true
    statement about durability rather than a knowing gap.

    So the third half of the property is that **a job is running**. A process that
    started with no broker and no task at all is the shape ADR-0041 was written
    about, and asserting ``is None`` here would now be asserting the bug. If this
    test ever has to change again, D-16 changed.

    **``checks`` is now ``["database", "kek"]``**, and the second entry is the
    one readiness check in Prope that is not about PostgreSQL. provider-access
    added it: a process with no KEK decrypts no credential, so every model call
    fails — in a shape indistinguishable from a provider outage unless readiness
    says otherwise (AC-12). The list is asserted whole rather than by
    membership, so a check appearing or vanishing is an edit somebody made.

    It does **not** weaken the claim above. The broker is still unreachable in
    this test and readiness is still green, which is D-16 exactly; the KEK is
    present because the environment has one, and a provider being *down* never
    makes this module unready either — an unreachable provider is what the
    fallback answer exists for.
    """
    monkeypatch.setenv(
        "PROPE_DATABASE_URL", app_engine.url.render_as_string(hide_password=False)
    )
    monkeypatch.setenv("PROPE_BROKER_URL", UNREACHABLE_BROKER_URL)

    application = create_app()
    async with lifespan(application):
        assert application.state.broker is None, "the broker connect should have failed"
        assert application.state.publisher is not None, (
            "a broker that was never there still leaves a supervised fallback-only job "
            "running, or every record enqueued during the outage is lost (CL-01)"
        )

        response = await call(application, "GET", "/readyz")
        assert response.status_code == 200, response.body
        assert response.json() == {"status": "ready", "checks": ["database", "kek"]}

        assert (await call(application, "GET", "/healthz")).status_code == 200


async def test_the_lifespan_builds_the_sessionmaker_the_routes_read(
    monkeypatch: pytest.MonkeyPatch, app_engine: AsyncEngine
) -> None:
    """The composition wires itself: after startup the routes have a database.

    Asserted through a route rather than by reading ``app.state``, because what
    matters is that ``get_sessionmaker`` finds it. The route answers ``401``
    because ``require_session`` is not overridden here — which is the correct
    answer and proves the request reached the handler stack rather than the
    ``503`` a missing sessionmaker produces.
    """
    monkeypatch.setenv(
        "PROPE_DATABASE_URL", app_engine.url.render_as_string(hide_password=False)
    )
    monkeypatch.setenv("PROPE_BROKER_URL", UNREACHABLE_BROKER_URL)

    application = create_app()
    async with lifespan(application):
        assert application.state.sessionmaker is not None

        response = await call(application, "GET", "/api/v1/prices")
        assert response.status_code == 401, response.body
