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
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from prope.db.metadata import metadata

# Belt and braces for `alembic/ddl.py`. alembic.ini's `prepend_sys_path`
# already puts this directory on the path for every command — including the
# ones that load revision files without running env.py — but a caller that
# builds a Config programmatically without that ini would otherwise fail on the
# revisions' `from ddl import ...`. See the comment in alembic.ini for why the
# emitters cannot be imported as `alembic.ddl`.
_ALEMBIC_DIR = str(Path(__file__).resolve().parent)
if _ALEMBIC_DIR not in sys.path:
    sys.path.insert(0, _ALEMBIC_DIR)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The project's one shared MetaData, with the naming convention every
# constraint name in the database is rendered from.
#
# D-04 still holds: this changes what autogenerate *would* compare against, it
# does not make autogenerate trusted. Revisions are hand-written and
# autogenerate output is never committed — it cannot see RLS policies, grants
# or triggers, and the first autogenerate after a policy lands proposes
# dropping what it cannot see.
target_metadata = metadata


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
