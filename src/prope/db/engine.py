"""Async engine and sessionmaker construction.

Deliberately thin. The only opinion expressed here is a negative one: no
permissive ``search_path`` is set on the application connection. ADR-0027 makes
schema-qualified names appear in every query and every migration, and calls
that "the intended cost: it is what makes a forbidden edge legible without a
linter". A ``ledger`` on the search path is exactly what would make an
accidental ``registry.revision`` join look ordinary.
"""

from typing import Any

from pydantic import Field, SecretStr
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

    #: ``PROPE_RETENTION_CHUNK_SIZE`` (D-12). The operator's override for the
    #: retention sweep's chunk size; ``None`` means
    #: ``prope.call_ledger.retention.DEFAULT_CHUNK_SIZE``.
    #:
    #: **Optional, and deliberately not validated here.** The bound that matters
    #: — a chunk of fewer than one row deletes nothing, never returns short, and
    #: so loops forever opening a transaction per iteration — is WARN-1, and plan
    #: 02-02 put the guard in ``delete_expired_bodies`` itself, where every
    #: caller meets it rather than only the one that reads an environment
    #: variable. A second check here would be a second place for the two to
    #: disagree. The type is what refuses ``"large"``; the function is what
    #: refuses ``0``.
    retention_chunk_size: int | None = None

    #: ``PROPE_COOKIE_SECURE``. Whether the session cookie carries ``Secure``.
    #:
    #: **The default is ``True`` and a test asserts it**, because that is the
    #: only value ADR-0043 and ADR-0052 describe: Caddy terminates TLS and there
    #: is no plaintext origin in production, so a cookie without ``Secure`` is a
    #: session id that a downgrade can read off the wire.
    #:
    #: It is a setting rather than a literal because ADR-0033's own stated
    #: development and demo target is a laptop, where the single ingress listens
    #: on ``:80`` with no domain and therefore no certificate — and a browser
    #: **silently discards** a ``Secure`` cookie sent over plain HTTP. The failure
    #: that produces is the worst-behaved one available: sign-in answers ``200``,
    #: the SPA routes to the workspace, and every request after it is a ``401``
    #: with nothing in any log saying why.
    #:
    #: So the exception is declared, greppable, and false only where somebody
    #: wrote it down. ``.env.example`` ships it commented out with this reasoning
    #: attached; a production ``.env`` that omits the key gets ``Secure``.
    cookie_secure: bool = True

    #: A local-only operator session.  Its alias intentionally lacks the
    #: ``PROPE_`` prefix because Docker Compose and the playground expose this
    #: exact operator-facing name.
    admin_session_token: SecretStr | None = Field(
        default=None, validation_alias="ADMIN_SESSION_TOKEN"
    )

    #: Kept distinct from the application package's environment because the
    #: development token must make production startup fail closed.
    app_env: str = Field(default="production", validation_alias="APP_ENV")


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
