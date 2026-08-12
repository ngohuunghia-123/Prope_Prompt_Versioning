"""Shared factories for the ``access`` schema's tests.

Same placement argument as ``tests/property_history/``: a per-subject package
named after the module, created when its subject arrived.

Everything here seeds through ``migrate_engine`` — the owner — so the rows a test
needs exist independently of the privileges and policies under test. A test whose
subject is a command writes through the command.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.access_control.passwords import hash_password
from tests.unit import DAY_1, WORKSPACE_A, WORKSPACE_B, day

__all__ = [
    "ADMIN_ID",
    "DAY_1",
    "HASHED_PASSWORD",
    "KEY_ID",
    "MEMBER_ID",
    "PASSWORD",
    "PROMPT_ID",
    "WORKSPACE_A",
    "WORKSPACE_B",
    "day",
    "seed_api_key",
    "seed_grant",
    "seed_member",
    "seed_role",
    "seed_session",
    "seed_user",
    "seed_workspace",
]

ADMIN_ID = "usr_01J00000000000000000ADMIN"
MEMBER_ID = "usr_01J0000000000000000MEMBER"
PROMPT_ID = "prm_01J0000000000000000PROMPT"
KEY_ID = "key_01J000000000000000000KEY1"

#: Thirteen characters, above `schemas.MIN_PASSWORD_LENGTH`.
PASSWORD = "correct-horse"

#: Hashed **once per test session**, not once per seeded user. argon2id at
#: ADR-0043's cost is ~60 ms a call by design, and a factory that paid it per row
#: would put minutes into a suite for no property it asserts. A test whose subject
#: is the hashing pays for its own.
#:
#: Every active row must carry one: `ck_user_active_row_is_whole` refuses an
#: active account with a NULL `password_hash`, which is what makes the
#: half-tombstoned state unreachable.
HASHED_PASSWORD = hash_password(PASSWORD)

INSERT_WORKSPACE = text(
    """
    INSERT INTO access.workspace (id, name, slug, created_by, created_at)
    VALUES (:id, :name, :slug, :created_by, :created_at)
    """
)

INSERT_USER = text(
    """
    INSERT INTO access."user" (id, email, display_name, password_hash,
                               must_change_password, status, created_at)
    VALUES (:id, :email, :display_name, :password_hash,
            :must_change_password, :status, :created_at)
    """
)

INSERT_MEMBER = text(
    """
    INSERT INTO access.workspace_member (workspace_id, user_id, added_by, added_at, status)
    VALUES (:workspace_id, :user_id, :added_by, :added_at, :status)
    """
)

INSERT_ROLE = text(
    """
    INSERT INTO access.role_binding (workspace_id, user_id, role, granted_by, granted_at)
    VALUES (:workspace_id, :user_id, :role, :granted_by, :granted_at)
    """
)

INSERT_GRANT = text(
    """
    INSERT INTO access.prompt_grant (workspace_id, prompt_id, grantee_user_id, level,
                                     granted_by, granted_at)
    VALUES (:workspace_id, :prompt_id, :grantee_user_id, :level, :granted_by, :granted_at)
    """
)

INSERT_SESSION = text(
    """
    INSERT INTO access.session (id, user_id, workspace_id, created_at, expires_at, last_seen_at)
    VALUES (:id, :user_id, :workspace_id, :created_at, :expires_at, :created_at)
    """
)

INSERT_API_KEY = text(
    """
    INSERT INTO access.api_key (id, workspace_id, name, key_hash, last_four,
                                scope_model_names, created_by, created_at)
    VALUES (:id, :workspace_id, :name, :key_hash, :last_four,
            :scope_model_names, :created_by, :created_at)
    """
)


async def _insert(migrate_engine: AsyncEngine, statement, values: dict[str, Any]) -> None:
    async with migrate_engine.begin() as connection:
        await connection.execute(statement, values)


async def seed_workspace(
    migrate_engine: AsyncEngine, workspace_id: str = WORKSPACE_A, **overrides: Any
) -> str:
    values = {
        "id": workspace_id,
        "name": "Acme",
        "slug": workspace_id.removeprefix("wsp_").lower()[:40],
        "created_by": ADMIN_ID,
        "created_at": day(1),
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_WORKSPACE, values)
    return str(values["id"])


async def seed_user(
    migrate_engine: AsyncEngine, user_id: str = ADMIN_ID, **overrides: Any
) -> str:
    """A live account whose password is :data:`PASSWORD`.

    Override `password_hash` directly to seed a different one; a tombstoned row
    is `status="tombstoned"` with the identity columns NULL, and the two CHECKs
    refuse anything in between.
    """
    values = {
        "id": user_id,
        "email": f"{user_id}@example.test",
        "display_name": "A Person",
        "password_hash": HASHED_PASSWORD,
        "must_change_password": False,
        "status": "active",
        "created_at": day(1),
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_USER, values)
    return str(values["id"])


async def seed_member(
    migrate_engine: AsyncEngine,
    workspace_id: str = WORKSPACE_A,
    user_id: str = ADMIN_ID,
    **overrides: Any,
) -> None:
    values = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "added_by": ADMIN_ID,
        "added_at": day(1),
        "status": "active",
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_MEMBER, values)


async def seed_role(
    migrate_engine: AsyncEngine,
    role: str,
    workspace_id: str = WORKSPACE_A,
    user_id: str = ADMIN_ID,
) -> None:
    await _insert(
        migrate_engine,
        INSERT_ROLE,
        {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "role": role,
            "granted_by": ADMIN_ID,
            "granted_at": day(1),
        },
    )


async def seed_grant(
    migrate_engine: AsyncEngine,
    level: str,
    workspace_id: str = WORKSPACE_A,
    prompt_id: str = PROMPT_ID,
    grantee_user_id: str = MEMBER_ID,
) -> None:
    await _insert(
        migrate_engine,
        INSERT_GRANT,
        {
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "grantee_user_id": grantee_user_id,
            "level": level,
            "granted_by": ADMIN_ID,
            "granted_at": day(1),
        },
    )


async def seed_session(
    migrate_engine: AsyncEngine,
    session_id: str,
    workspace_id: str = WORKSPACE_A,
    user_id: str = ADMIN_ID,
    **overrides: Any,
) -> str:
    # A REAL clock, unlike every other factory here. `access.lookup_session`
    # applies `expires_at > now()` inside the function — expiry is a read
    # property because there is no sweeper — so a session stamped with the
    # calendar constants would be expired on arrival and the lookup would
    # correctly find nothing.
    issued = datetime.now(UTC)
    values = {
        "id": session_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "created_at": issued,
        "expires_at": issued + timedelta(hours=12),
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_SESSION, values)
    return str(values["id"])


async def seed_api_key(
    migrate_engine: AsyncEngine,
    key_id: str = KEY_ID,
    *,
    key_hash: str = "0" * 64,
    scope_model_names: tuple[str, ...] = (),
    workspace_id: str = WORKSPACE_A,
    **overrides: Any,
) -> str:
    values: dict[str, Any] = {
        "id": key_id,
        "workspace_id": workspace_id,
        "name": "a consumer",
        "key_hash": key_hash,
        "last_four": "abcd",
        "scope_model_names": list(scope_model_names),
        "created_by": ADMIN_ID,
        "created_at": day(1),
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_API_KEY, values)
    return str(values["id"])
