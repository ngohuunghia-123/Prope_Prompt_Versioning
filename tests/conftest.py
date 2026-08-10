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

from alembic import command
from prope.db.engine import build_engine, build_sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Test-only passwords for a container that is destroyed at session end. The
#: migration deliberately bakes none (D-05).
TEST_ROLE_PASSWORDS = {
    "prope_migrate": "test-only-migrate",
    "prope_app": "test-only-app",
    "prope_report": "test-only-report",
}

#: Discovered rather than listed, so the later plans in this phase can add
#: tables without editing the rig.
LIST_LEDGER_TABLES = text(
    "SELECT quote_ident(schemaname) || '.' || quote_ident(tablename) "
    "FROM pg_tables WHERE schemaname = 'ledger'"
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
async def truncate_ledger(migrate_engine: AsyncEngine) -> AsyncIterator[None]:
    """Empty every ledger table between tests, as the owner (A10)."""
    yield
    async with migrate_engine.begin() as connection:
        tables = (await connection.execute(LIST_LEDGER_TABLES)).scalars().all()
        if tables:
            await connection.execute(
                text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE")
            )
