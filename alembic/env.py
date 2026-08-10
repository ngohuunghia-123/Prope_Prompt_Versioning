"""Alembic environment for Prope.

D-04: one linear, hand-written chain for all eight module schemas, run as
`prope_migrate`, one `alembic upgrade head` per deploy.

Two settings here are load-bearing rather than cosmetic:

* ``version_table_schema="public"`` — with schema-per-module and
  ``include_schemas=True``, an unpinned ``alembic_version`` lands wherever
  ``search_path`` points. Inside ``ledger`` it would fail D-06's coverage walk
  for carrying no ``workspace_id``, and the "fix" would be a ``GLOBAL_TABLES``
  entry that dilutes a security-relevant file with a bookkeeping table.
* ``poolclass=NullPool`` plus an explicit ``dispose()`` — a pooled connection
  outliving the migration is the source of asyncpg's
  ``InvalidCachedStatementError`` on the first test after a DDL change.

The database URL comes from ``PROPE_DATABASE_URL`` (ADR-0032: one ``.env`` on
the host) and only falls back to ``alembic.ini``.
"""

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# D-04: revisions are hand-written and autogenerate output is never trusted or
# committed — it cannot see RLS policies, grants or triggers, and the first
# autogenerate after a policy lands proposes dropping what it cannot see.
# `prope.db.metadata` does not exist until this phase's tracer task; it is
# repointed there as an explicit step.
target_metadata = None


def database_url() -> str:
    """PROPE_DATABASE_URL first, alembic.ini second, a loud failure third."""
    url = os.environ.get("PROPE_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "No database URL. Set PROPE_DATABASE_URL (ADR-0032 — the .env on the host "
            "holds it) or sqlalchemy.url in alembic.ini."
        )
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well. By skipping the Engine creation we don't
    even need a DBAPI to be available.
    """
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="public",
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema="public",
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an Engine and associate a connection with the context."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
