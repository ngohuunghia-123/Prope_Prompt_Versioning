"""AC-13 / A-151. What `POST /api/v1/users/{id}/tombstone` erases, and what it keeps.

ADR-0054's shape in one table. Every column below is either cleared or retained
on purpose, and the two CHECK constraints revision 0006 installs make the
half-applied version unreachable rather than merely unlikely.
"""

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.api import router as access_control_router
from prope.access_control.bootstrap import authenticate_session
from prope.errors import ErrorCode, install_error_envelope
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    ADMIN_ID,
    KEY_ID,
    MEMBER_ID,
    PROMPT_ID,
    seed_api_key,
    seed_grant,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call

ADMIN_SESSION = "ses_tombstone_admin_00000000001"
LEAVER_SESSION = "ses_tombstone_leaver_0000000001"

READ_USER = text(
    'SELECT email, display_name, password_hash, must_change_password, status, '
    'tombstoned_at, tombstoned_by, last_login_at FROM access."user" WHERE id = :id'
)
COUNT_SESSIONS = text("SELECT count(*) FROM access.session WHERE user_id = :id")
COUNT_ROLE_BINDINGS = text("SELECT count(*) FROM access.role_binding WHERE user_id = :id")
COUNT_GRANTS = text("SELECT count(*) FROM access.prompt_grant WHERE grantee_user_id = :id")
READ_MEMBERSHIP = text("SELECT status FROM access.workspace_member WHERE user_id = :id")
COUNT_KEYS = text("SELECT count(*) FROM access.api_key WHERE created_by = :id")
COUNT_TOMBSTONE_EVENTS = text(
    "SELECT count(*) FROM history.history_event "
    "WHERE action = 'user_tombstoned' AND target_id = :id"
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(access_control_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


async def _workspace_with_a_leaver(migrate_engine, *, leaver_is_active: bool = False) -> None:
    """An Admin who will act, and a colleague who is on their way out."""
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Admin")
    await seed_session(migrate_engine, ADMIN_SESSION)

    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(
        migrate_engine,
        user_id=MEMBER_ID,
        status="active" if leaver_is_active else "removed",
    )
    await seed_session(migrate_engine, LEAVER_SESSION, user_id=MEMBER_ID)
    await seed_grant(migrate_engine, "editor")
    await seed_api_key(migrate_engine, created_by=MEMBER_ID)


def _admin() -> dict[str, str]:
    return {"cookie": f"prope_session={ADMIN_SESSION}"}


async def test_the_identity_columns_are_cleared_and_the_row_survives(api, migrate_engine) -> None:
    """The id stays reserved, which is the whole reason the row is kept."""
    await _workspace_with_a_leaver(migrate_engine)

    response = await call(
        api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin()
    )
    assert response.status_code == 204, response.body

    async with migrate_engine.begin() as connection:
        row = (await connection.execute(READ_USER, {"id": MEMBER_ID})).one()

    assert row.email is None
    assert row.display_name is None
    assert row.password_hash is None
    assert row.must_change_password is False
    assert row.status == "tombstoned"
    assert row.tombstoned_at is not None
    assert row.tombstoned_by == ADMIN_ID


async def test_every_session_role_binding_and_grant_is_gone(api, migrate_engine) -> None:
    """Authority ends at once. Their next request is a `401`, not a `403`."""
    await _workspace_with_a_leaver(migrate_engine)

    await call(api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin())

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_SESSIONS, {"id": MEMBER_ID})).scalar_one() == 0
        assert (await connection.execute(COUNT_ROLE_BINDINGS, {"id": MEMBER_ID})).scalar_one() == 0
        assert (await connection.execute(COUNT_GRANTS, {"id": MEMBER_ID})).scalar_one() == 0


async def test_the_membership_row_and_the_consumer_key_are_retained(api, migrate_engine) -> None:
    """Two deliberate absences from the erasure.

    The `workspace_member` row is how this operation knows which workspaces to
    write an event into, and revision 0006 withholds `DELETE` on the table so the
    retention is a privilege rather than a habit. The API key belongs to the
    **workspace**, not to whoever created it (A-113) — revoking a departing
    person's keys on an HR event would break a consuming product's traffic
    silently, which is the failure nobody would connect to the leaving.
    """
    await _workspace_with_a_leaver(migrate_engine)

    await call(api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin())

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(READ_MEMBERSHIP, {"id": MEMBER_ID})).scalar_one() == (
            "removed"
        )
        assert (await connection.execute(COUNT_KEYS, {"id": MEMBER_ID})).scalar_one() == 1


async def test_one_event_is_written_per_workspace_the_person_belonged_to(
    api, migrate_engine
) -> None:
    """Including workspaces they had only ever been removed from.

    A reader of any workspace's trail has to be able to tell why an `actor_id` in
    it no longer resolves.
    """
    await _workspace_with_a_leaver(migrate_engine)

    await call(api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin())

    async with migrate_engine.begin() as connection:
        assert (
            await connection.execute(COUNT_TOMBSTONE_EVENTS, {"id": MEMBER_ID})
        ).scalar_one() == 1


async def test_an_active_membership_refuses_the_whole_operation(api, migrate_engine) -> None:
    """A refusal, not a cleanup (A-151).

    Each removal writes its own `member_removed` event in its own workspace, and
    the tombstone is the account-level act that follows. Collapsing the two would
    put *"left this workspace"* and *"erased from Prope"* into one ambiguous event.
    """
    await _workspace_with_a_leaver(migrate_engine, leaver_is_active=True)

    response = await call(
        api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin()
    )

    assert response.status_code == 409, response.body
    assert response.code == ErrorCode.USER_STILL_HAS_MEMBERSHIP.value

    async with migrate_engine.begin() as connection:
        row = (await connection.execute(READ_USER, {"id": MEMBER_ID})).one()
        assert row.status == "active"
        assert row.email is not None
        # Nothing partial: the identity clear runs before the per-workspace
        # writes and the whole thing is one transaction.
        assert (await connection.execute(COUNT_SESSIONS, {"id": MEMBER_ID})).scalar_one() == 1


async def test_a_second_tombstone_is_a_not_found_rather_than_a_second_set_of_events(
    api, migrate_engine
) -> None:
    """`WHERE status = 'active'` is what decides, and it runs before any write."""
    await _workspace_with_a_leaver(migrate_engine)

    first = await call(api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin())
    second = await call(api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin())

    assert first.status_code == 204
    assert second.status_code == 404
    assert second.code == ErrorCode.NOT_FOUND.value

    async with migrate_engine.begin() as connection:
        assert (
            await connection.execute(COUNT_TOMBSTONE_EVENTS, {"id": MEMBER_ID})
        ).scalar_one() == 1


async def test_the_grant_it_deleted_belonged_to_the_leaver_and_not_to_the_prompt(
    api, migrate_engine
) -> None:
    """Only the departing person's grants go. Everybody else keeps theirs."""
    await _workspace_with_a_leaver(migrate_engine)
    await seed_grant(migrate_engine, "viewer", grantee_user_id=ADMIN_ID)

    await call(api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin())

    async with migrate_engine.begin() as connection:
        remaining = (
            await connection.execute(
                text(
                    "SELECT grantee_user_id FROM access.prompt_grant WHERE prompt_id = :prompt"
                ),
                {"prompt": PROMPT_ID},
            )
        ).scalars().all()

    assert list(remaining) == [ADMIN_ID]


async def test_the_leavers_session_stops_working_immediately(api, migrate_engine) -> None:
    """No TTL to wait out: the session was a row and the row is gone (ADR-0022)."""
    await _workspace_with_a_leaver(migrate_engine)
    leaver = {"cookie": f"prope_session={LEAVER_SESSION}"}

    before = await call(api, "GET", "/api/v1/permissions", headers=leaver)
    assert before.status_code == 200, before.body

    await call(api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin())

    after = await call(api, "GET", "/api/v1/permissions", headers=leaver)
    assert after.status_code == 401, after.body


async def test_the_api_key_it_left_behind_still_authenticates(migrate_engine, api) -> None:
    """A-113 restated on the wire: the workspace's consumer traffic is untouched."""
    await _workspace_with_a_leaver(migrate_engine)

    await call(api, "POST", f"/api/v1/users/{MEMBER_ID}/tombstone", headers=_admin())

    async with migrate_engine.begin() as connection:
        revoked = (
            await connection.execute(
                text("SELECT revoked_at FROM access.api_key WHERE id = :id"), {"id": KEY_ID}
            )
        ).scalar_one()

    assert revoked is None
