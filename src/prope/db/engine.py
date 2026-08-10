"""Async engine and sessionmaker construction.

Deliberately thin. The only opinion expressed here is a negative one: no
permissive ``search_path`` is set on the application connection. ADR-0027 makes
schema-qualified names appear in every query and every migration, and calls
that "the intended cost: it is what makes a forbidden edge legible without a
linter". A ``ledger`` on the search path is exactly what would make an
accidental ``registry.revision`` join look ordinary.
"""

from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Settings(BaseSettings):
    """Runtime configuration read from the environment.

    ADR-0032: one ``.env`` on the host, 0600, git-ignored, never in CI. The
    ``PROPE_`` prefix keeps Prope's keys distinguishable from whatever else the
    host's environment carries, and ``extra="ignore"`` means an unrelated key
    in the same file is not an error.
    """

    model_config = SettingsConfigDict(
        env_prefix="PROPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str

    #: ``PROPE_BROKER_URL`` (ADR-0028). It lives on THIS class rather than on a
    #: second ``BaseSettings`` subclass: ADR-0032 gives the host one ``.env``,
    #: and two settings objects reading it is two places to forget a key. That
    #: this module is named for the database and now carries a broker URL is the
    #: cost, and it is smaller than the one it buys.
    broker_url: str


def build_engine(url: str, **kwargs: Any) -> AsyncEngine:
    """An async engine over asyncpg (A-128 — a sync driver would block the
    event loop the gateway's p95 budget depends on)."""
    return create_async_engine(url, **kwargs)


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """A sessionmaker whose sessions survive being read after commit.

    ``expire_on_commit=False`` because an expired attribute would trigger a
    lazy refresh outside the transaction that carried the tenant context — a
    read with no ``app.workspace_id`` set, which under the policy returns
    nothing rather than raising.
    """
    return async_sessionmaker(engine, expire_on_commit=False)
