"""The D-02 test rig: a real PostgreSQL 17, three role-scoped engines.

Every guarantee this phase ships — a policy returning zero rows, the T-006
revokes refusing an update, effective-dated selection at a timestamp boundary —
is observable only against a live engine. A CI-service-container / local-compose
split was rejected because two provisioning paths drift, and the first drift
reads as green CI over a broken local run.

Four decisions here are load-bearing:

**Migrations run on their own engine, which is then disposed** (the async
``env.py`` recipe already uses ``NullPool``). The application engines are built
only after ``upgrade head`` completes. A pooled connection that outlives a DDL
change is asyncpg's ``InvalidCachedStatementError``, which shows up as "the
first test after a schema change fails and the second passes".

**Role passwords are set here, out of band.** The migration bakes none (D-05,
ADR-0032), so the rig issues ``ALTER ROLE ... WITH PASSWORD`` as the container
superuser after the upgrade, purely so the two role-scoped engines can connect.
These are test-only credentials for a container that lives for one session.

**Isolation is truncate-between-tests, not transaction rollback** (A10). The
rollback pattern is the conventional one and would silently break every
cross-tenant test: it turns the seam's ``session.begin()`` into a savepoint,
and the transaction-local tenant setting survives a savepoint, so tenant A's
context contaminates tenant B inside the same test.

**Every engine uses NullPool.** Beyond the DDL-cache reason above, pytest-asyncio
gives each test its own event loop, and an asyncpg connection is bound to the
loop that opened it. With no pool, nothing is carried across loops. The one
place the reused-connection path genuinely matters is asserted by holding a
single connection open across two transactions, explicitly, rather than by
hoping the pool hands the same one back.

Phase 2 adds a real RabbitMQ beside the real PostgreSQL (D-22), and three more
decisions come with it:

**The broker is real, and a fake at the aio-pika seam was rejected by name.**
A publisher confirm arriving, a redelivery after an unacknowledged consumer
restart, and a queue holding the arguments that were declared are all properties
of the broker. A fake would assert the fake. A fast-fake default with a
skippable real-broker smoke test was rejected as the same two-provisioning-paths
split D-02 already refused.

**The image tag is pinned to the minor, ``rabbitmq:4.3-management``.**
``RabbitMqContainer``'s own default is ``rabbitmq:latest``, which drifts — the
same reason the Postgres fixture pins ``postgres:17``. The ``-management``
variant is not decoration: D-23 requires reading the declared arguments back
*from the broker*, and the management HTTP API on port 15672 is what makes that
a read rather than a re-derivation.

**Isolation is a per-test PURGE, not a delete-and-redeclare.** The queues'
arguments are one-way (A-149, D-23); a redeclare whose arguments do not match
answers with ``PRECONDITION_FAILED`` (406), which surfaces in an unrelated test
as an unrelated failure. Purging empties the queues and leaves the declaration —
the thing under test — untouched. Same posture as ``truncate_owned_tables``, for
the same reason.

Phase 4 adds the ``history`` schema, and with it the eighth decision:

**The truncate fixture spans two schemas and excludes
``history.history_action_registry`` by name** (D-48). That table is written by
the migration and by nothing else; truncating it destroys the closed vocabulary
after test one, and the failure surfaces as "every test after the first says the
action is unregistered" — which points at the validator, not at a fixture two
directories away. **Re-seeding it inside the fixture is refused by name**: that
is a second provisioning path for the vocabulary, the split D-02 rejected, and
it would let the suite pass against a registry the migration never wrote, which
is the one failure AC-6 exists to catch. Two consequences follow. ``CASCADE``
"automatically truncate[s] all tables that have foreign-key references to any of
the named tables", so naming the registry would drag ``history_event`` in
anyway; and ``RESTART IDENTITY`` resets ``history_event.seq`` between tests,
which makes per-test ``seq`` values small and predictable and is why the
ordering tests assert the *relation* between two values rather than the values.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

# `testcontainers.community.rabbitmq`, NOT `testcontainers.rabbitmq` — the
# latter is a deprecation shim that emits a DeprecationWarning. Matches the
# `testcontainers.community.postgres` import above.
from testcontainers.community.rabbitmq import RabbitMqContainer

from alembic import command
from prope.broker.connection import build_connection
from prope.broker.topology import DLQ, WORK_QUEUE, declare_topology
from prope.call_ledger.enqueue import reset_handoff
from prope.db.engine import build_engine, build_sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Test-only passwords for a container that is destroyed at session end. The
#: migration deliberately bakes none (D-05).
TEST_ROLE_PASSWORDS = {
    "prope_migrate": "test-only-migrate",
    "prope_app": "test-only-app",
    "prope_report": "test-only-report",
}

#: Discovered rather than listed, so a later plan can add a table without
#: editing the rig. The one exclusion is D-48's, argued in the module docstring.
LIST_TRUNCATABLE_TABLES = text(
    "SELECT quote_ident(schemaname) || '.' || quote_ident(tablename) "
    "FROM pg_tables WHERE schemaname IN ('ledger', 'history') "
    "AND NOT (schemaname = 'history' AND tablename = 'history_action_registry')"
)


def _role_url(container: PostgresContainer, role: str) -> str:
    """A connection URL for one of the three roles created by revision 0001."""
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5432)
    password = TEST_ROLE_PASSWORDS[role]
    return f"postgresql+asyncpg://{role}:{password}@{host}:{port}/{container.dbname}"


def _upgrade_to_head(container: PostgresContainer) -> None:
    """Run the whole chain as the container superuser.

    Revision 0001 needs a superuser for ``CREATE ROLE ... BYPASSRLS`` (flagged
    assumption A9). Alembic builds and disposes its own NullPool engine.
    """
    os.environ["PROPE_DATABASE_URL"] = container.get_connection_url()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.upgrade(config, "head")


async def _set_test_role_passwords(container: PostgresContainer) -> None:
    engine = build_engine(container.get_connection_url(), poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            for role, password in TEST_ROLE_PASSWORDS.items():
                await connection.execute(text(f"ALTER ROLE {role} WITH PASSWORD '{password}'"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """A pristine PostgreSQL 17 with the chain applied, for the whole session."""
    with PostgresContainer("postgres:17", driver="asyncpg") as container:
        _upgrade_to_head(container)
        asyncio.run(_set_test_role_passwords(container))
        yield container


@pytest.fixture(scope="session")
def migrate_engine(postgres_container: PostgresContainer) -> Iterator[AsyncEngine]:
    """The owner role. RLS-exempt by owner bypass — every positive control."""
    engine = build_engine(_role_url(postgres_container, "prope_migrate"), poolclass=NullPool)
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(scope="session")
def app_engine(postgres_container: PostgresContainer) -> Iterator[AsyncEngine]:
    """The runtime role. Subject to the tenant policy — the thing under test."""
    engine = build_engine(_role_url(postgres_container, "prope_app"), poolclass=NullPool)
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(scope="session")
def app_sessionmaker(app_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """What ``workspace_transaction`` is handed everywhere in the project."""
    return build_sessionmaker(app_engine)


@pytest.fixture(scope="session")
def report_engine(postgres_container: PostgresContainer) -> Iterator[AsyncEngine]:
    """The BYPASSRLS reporting role (ADR-0037). A full-read credential."""
    engine = build_engine(_role_url(postgres_container, "prope_report"), poolclass=NullPool)
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(autouse=True)
async def truncate_owned_tables(migrate_engine: AsyncEngine) -> AsyncIterator[None]:
    """Empty every owned table between tests, as the owner (A10).

    Two schemas since Phase 4, minus ``history.history_action_registry`` — see
    the module docstring's eighth paragraph for why that one is excluded and why
    re-seeding it here is refused rather than merely not done.
    """
    yield
    async with migrate_engine.begin() as connection:
        tables = (await connection.execute(LIST_TRUNCATABLE_TABLES)).scalars().all()
        if tables:
            await connection.execute(
                text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE")
            )


@pytest.fixture(scope="session")
def rabbitmq_container() -> Iterator[RabbitMqContainer]:
    """A real RabbitMQ 4.3 for the whole session (D-22).

    5672 is AMQP; 15672 is the management HTTP API, which is what D-23's
    read-back test reads the declared arguments from. Both are exposed here
    because ``RabbitMqContainer`` exposes only 5672 by default.
    """
    container = RabbitMqContainer("rabbitmq:4.3-management")
    container.with_exposed_ports(5672, 15672)
    with container as running:
        yield running


@pytest.fixture(scope="session")
def amqp_url(rabbitmq_container: RabbitMqContainer) -> str:
    """The AMQP URL, derived the same way ``_role_url`` derives a database URL."""
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


@pytest.fixture(scope="session")
def management_url(rabbitmq_container: RabbitMqContainer) -> str:
    """The management HTTP API root. Credentials are the container defaults."""
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(15672)
    return f"http://{host}:{port}"


@pytest.fixture(autouse=True)
async def purge_queues(request: pytest.FixtureRequest) -> AsyncIterator[None]:
    """Empty both queues between broker tests, and reset the handoff buffer.

    **Purge, never delete-and-redeclare.** The declared arguments are one-way
    (D-23); a redeclare with different arguments answers ``PRECONDITION_FAILED``
    (406), which reads in an unrelated test as an unrelated failure. Purging
    leaves the declaration — the thing under test — exactly as it was.

    Opt-in by fixture graph rather than unconditional: a test that never asked
    for ``amqp_url`` should not pay for a broker container it does not use.
    """
    yield

    reset_handoff()

    if "amqp_url" not in request.fixturenames:
        return

    connection = await build_connection(request.getfixturevalue("amqp_url"))
    async with connection:
        channel = await connection.channel()
        await declare_topology(channel)
        for name in (WORK_QUEUE, DLQ):
            queue = await channel.get_queue(name)
            await queue.purge()
