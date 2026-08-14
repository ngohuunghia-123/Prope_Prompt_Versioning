"""Development-only operator session bootstrap.

This module is intentionally invoked only by the composition root when an
operator configured ``ADMIN_SESSION_TOKEN`` and declared a development
environment.  The token remains a normal database-backed session: it can never
be enabled in production, and all ordinary route authentication still goes
through ``authenticate_session``.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from prope.access_control import passwords
from prope.db.session import workspace_transaction

DEVELOPMENT_ADMIN_USER_ID = "usr_development_admin"
DEVELOPMENT_ADMIN_WORKSPACE_ID = "wsp_development_admin"
DEVELOPMENT_ADMIN_EMAIL = "admin@development.local"
DEVELOPMENT_ADMIN_SLUG = "prope-development-admin"
DEVELOPMENT_SESSION_LIFETIME = timedelta(days=3650)
DEVELOPMENT_ROLES = ("Owner", "Reviewer", "Admin")

INSERT_USER = text(
    """
    INSERT INTO access."user" (id, email, display_name, password_hash, must_change_password, status)
    VALUES (:user_id, :email, 'Development Administrator', :password_hash, false, 'active')
    ON CONFLICT (id) DO UPDATE
       SET status = 'active', must_change_password = false
    """
)
INSERT_WORKSPACE = text(
    """
    INSERT INTO access.workspace (id, name, slug, created_by)
    VALUES (:workspace_id, 'Development', :slug, :user_id)
    ON CONFLICT (id) DO NOTHING
    """
)
INSERT_MEMBERSHIP = text(
    """
    INSERT INTO access.workspace_member (workspace_id, user_id, added_by, status)
    VALUES (:workspace_id, :user_id, :user_id, 'active')
    ON CONFLICT (workspace_id, user_id) DO UPDATE SET status = 'active'
    """
)
INSERT_ROLE = text(
    """
    INSERT INTO access.role_binding (workspace_id, user_id, role, granted_by)
    VALUES (:workspace_id, :user_id, :role, :user_id)
    ON CONFLICT (workspace_id, user_id, role) DO NOTHING
    """
)
UPSERT_SESSION = text(
    """
    INSERT INTO access.session (id, user_id, workspace_id, created_at, expires_at, last_seen_at)
    VALUES (:token, :user_id, :workspace_id, :now, :expires_at, :now)
    ON CONFLICT (id) DO UPDATE
       SET expires_at = EXCLUDED.expires_at,
           last_seen_at = EXCLUDED.last_seen_at
     WHERE access.session.user_id = :user_id
       AND access.session.workspace_id = :workspace_id
    RETURNING id
    """
)


class DevelopmentBootstrapError(RuntimeError):
    """The configured development credential is invalid or already belongs elsewhere."""


def require_development_environment(environment: str) -> None:
    """Keep the fixed operator credential out of every non-development process."""
    if environment.lower() != "development":
        raise DevelopmentBootstrapError(
            "ADMIN_SESSION_TOKEN is permitted only when APP_ENV=development"
        )


def validate_development_token(token: str) -> None:
    """Reject values that cannot be normal session credentials before any SQL runs."""
    if not token.startswith("ses_") or len(token) <= len("ses_"):
        raise DevelopmentBootstrapError("ADMIN_SESSION_TOKEN must start with ses_")


async def ensure_development_admin_session(
    sessionmaker: async_sessionmaker,
    token: str,
) -> None:
    """Create or renew the stable local operator session through normal access tables."""
    validate_development_token(token)
    now = datetime.now(UTC)
    values = {
        "user_id": DEVELOPMENT_ADMIN_USER_ID,
        "workspace_id": DEVELOPMENT_ADMIN_WORKSPACE_ID,
        "email": DEVELOPMENT_ADMIN_EMAIL,
        "slug": DEVELOPMENT_ADMIN_SLUG,
    }

    async with workspace_transaction(sessionmaker, DEVELOPMENT_ADMIN_WORKSPACE_ID) as db:
        await db.execute(
            INSERT_USER,
            {**values, "password_hash": passwords.hash_password(token)},
        )
        await db.execute(INSERT_WORKSPACE, values)
        await db.execute(INSERT_MEMBERSHIP, values)
        for role in DEVELOPMENT_ROLES:
            await db.execute(INSERT_ROLE, {**values, "role": role})
        session_id = await db.scalar(
            UPSERT_SESSION,
            {
                **values,
                "token": token,
                "now": now,
                "expires_at": now + DEVELOPMENT_SESSION_LIFETIME,
            },
        )
    if session_id is None:
        raise DevelopmentBootstrapError(
            "ADMIN_SESSION_TOKEN is already assigned to another session"
        )
