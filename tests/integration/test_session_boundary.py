"""INT-005 with a real implementation behind it, for the first time.

`tests/integration/test_management_routes.py` proves the boundary is *declared*
and refuses when nothing is installed — Phase 2's assertion, kept. This proves
what the installed authenticator actually answers, over the four failures that
share one response and the two that do not.

**A live row read, never a token verification** (ADR-0022, ADR-0029). Every case
below is the same request differing only in what is in the database, which is the
property a JWT could not have.
"""

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.access_control.api import router as access_control_router
from prope.access_control.bootstrap import authenticate_session
from prope.errors import ErrorCode, install_error_envelope
from prope.session_auth import (
    PASSWORD_CHANGE_REQUIRED,
    SESSION_REQUIRED,
    install_session_authenticator,
    reset_session_authenticator,
)
from tests.access_control import (
    ADMIN_ID,
    WORKSPACE_A,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call

SESSION_ID = "ses_0123456789abcdefghijklmn"

#: `ck_session_expires_after_creation` refuses an expiry before its creation, so
#: the whole row moves into the past rather than only its deadline.
EXPIRE_SESSION = text(
    "UPDATE access.session "
    "SET created_at = now() - interval '13 hours', expires_at = now() - interval '1 second' "
    "WHERE id = :id"
)
DELETE_SESSION = text("DELETE FROM access.session WHERE id = :id")
REQUIRE_PASSWORD_CHANGE = text(
    'UPDATE access."user" SET must_change_password = true WHERE id = :id'
)

#: A route that is neither of the two `PASSWORD_CHANGE_EXEMPT_ACTIONS`, so the
#: A-110 refusal is reachable through it.
GATED = ("GET", f"/api/v1/workspaces/{WORKSPACE_A}/members")


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    """The router with the REAL authenticator installed — nothing overridden.

    `install_session_authenticator` is the composition root's call, made here for
    the same reason `prope.app`'s lifespan makes it: this file's subject is what
    that wiring produces, so overriding `require_session` would test the override.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(access_control_router)
    application.state.sessionmaker = app_sessionmaker

    install_session_authenticator(
        lambda cookie: authenticate_session(app_sessionmaker, cookie)
    )
    try:
        yield application
    finally:
        reset_session_authenticator()


async def _seed_live_session(migrate_engine: AsyncEngine) -> None:
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Admin")
    await seed_session(migrate_engine, SESSION_ID)


def _cookie(value: str) -> dict[str, str]:
    return {"cookie": f"prope_session={value}"}


async def test_a_live_session_reaches_the_handler(api, migrate_engine) -> None:
    """The positive control. Without it every refusal below is true vacuously."""
    await _seed_live_session(migrate_engine)

    response = await call(api, *GATED, headers=_cookie(SESSION_ID))

    assert response.status_code == 200, response.body
    assert [item["user_id"] for item in response.json()["items"]] == [ADMIN_ID]


@pytest.mark.parametrize(
    "case", ["absent", "unknown", "expired", "signed_out", "tombstoned_owner"]
)
async def test_the_five_ways_a_session_fails_are_one_response(
    api, migrate_engine, case: str
) -> None:
    """Absent, unknown, expired, deleted, and owner-no-longer-active — one `401`.

    INT-005's failure line is *"null -> 401 in the A-045 envelope, and the SPA
    routes to sign-in"*. The client may distinguish none of the five and does not
    need to; distinguishing them would be an oracle for which session ids and
    accounts exist.
    """
    await _seed_live_session(migrate_engine)

    headers = _cookie(SESSION_ID)
    async with migrate_engine.begin() as connection:
        if case == "absent":
            headers = {}
        elif case == "unknown":
            headers = _cookie("ses_this-id-was-never-issued")
        elif case == "expired":
            await connection.execute(EXPIRE_SESSION, {"id": SESSION_ID})
        elif case == "signed_out":
            await connection.execute(DELETE_SESSION, {"id": SESSION_ID})
        elif case == "tombstoned_owner":
            await connection.execute(
                text(
                    'UPDATE access."user" SET email = NULL, display_name = NULL, '
                    "password_hash = NULL, must_change_password = false, "
                    "status = 'tombstoned', tombstoned_at = now(), tombstoned_by = :actor "
                    "WHERE id = :id"
                ),
                {"id": ADMIN_ID, "actor": ADMIN_ID},
            )

    response = await call(api, *GATED, headers=headers)

    assert response.status_code == 401, response.body
    assert response.code == SESSION_REQUIRED
    envelope = response.json()["error"]
    assert set(envelope) == {"code", "message", "details", "request_id"}
    assert envelope["details"] is None


async def test_the_refusal_quotes_no_part_of_the_cookie(api, migrate_engine) -> None:
    """A-046. A session cookie is the whole of a person's authority."""
    await _seed_live_session(migrate_engine)
    secret = "ses_a-value-that-must-not-be-echoed"

    response = await call(api, *GATED, headers=_cookie(secret))

    assert response.status_code == 401
    assert secret not in response.body.decode()


async def test_an_account_owing_a_password_change_is_refused_with_403(
    api, migrate_engine
) -> None:
    """A-110, enforced at the boundary rather than on the sign-in response alone.

    `403` and not `401`: the person **is** authenticated, and a `401` would send
    the SPA to sign-in, where signing in again would succeed and change nothing.
    """
    await _seed_live_session(migrate_engine)
    async with migrate_engine.begin() as connection:
        await connection.execute(REQUIRE_PASSWORD_CHANGE, {"id": ADMIN_ID})

    response = await call(api, *GATED, headers=_cookie(SESSION_ID))

    assert response.status_code == 403, response.body
    assert response.code == PASSWORD_CHANGE_REQUIRED


@pytest.mark.parametrize("path", ["/api/v1/auth/logout", "/api/v1/auth/password"])
async def test_the_two_exempt_routes_stay_reachable_while_a_change_is_owed(
    api, migrate_engine, path: str
) -> None:
    """Fewer than two exemptions locks somebody out of the only door that clears it.

    Neither call is asserted to succeed — the password change below sends a wrong
    current password on purpose. What is asserted is that the answer is **not**
    `password_change_required`, which is the only thing the exemption controls.
    """
    await _seed_live_session(migrate_engine)
    async with migrate_engine.begin() as connection:
        await connection.execute(REQUIRE_PASSWORD_CHANGE, {"id": ADMIN_ID})

    body = (
        None
        if path.endswith("logout")
        else {"current_password": "not-the-right-one", "new_password": "a-new-passphrase"}
    )
    response = await call(api, "POST", path, json_body=body, headers=_cookie(SESSION_ID))

    assert response.code != PASSWORD_CHANGE_REQUIRED, response.body


async def test_a_workspace_the_session_cannot_see_is_not_found(api, migrate_engine) -> None:
    """A-116 at `path_workspace`, now with live values on both sides of the compare."""
    await _seed_live_session(migrate_engine)

    response = await call(
        api,
        "GET",
        "/api/v1/workspaces/wsp_01J0000000000000000000BBB/members",
        headers=_cookie(SESSION_ID),
    )

    assert response.status_code == 404, response.body
    assert response.code == ErrorCode.NOT_FOUND.value
