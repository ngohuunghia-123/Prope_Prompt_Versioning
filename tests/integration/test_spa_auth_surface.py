"""The two routes ADR-0052's SPA needs, and the one setting that lets it reach them.

`GET /api/v1/auth/session` and `POST /api/v1/auth/register` exist for the client
rather than for the domain, which is exactly why they are worth asserting
separately: neither is reachable from the module's own vocabulary, so a
refactoring that broke one would break only the browser.

**Registration is the first door.** A-071 forbids invitations and Prope has no
outbound channel, so before this route an install with no accounts could not be
signed into: `POST /api/v1/workspaces` authenticates, and nothing could issue the
session it wanted. `test_registration_is_the_only_door_into_an_empty_install`
asserts that property directly, against a database with no rows in it.
"""

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.access_control.api import router as access_control_router
from prope.access_control.bootstrap import authenticate_session
from prope.access_control.commands import derive_workspace_slug
from prope.access_control.domain import Role
from prope.db.engine import Settings
from prope.errors import ErrorCode, install_error_envelope
from prope.session_auth import (
    PASSWORD_CHANGE_EXEMPT_ACTIONS,
    SESSION_COOKIE,
    ManagementAction,
    install_session_authenticator,
    reset_session_authenticator,
)
from tests.access_control import (
    ADMIN_ID,
    PASSWORD,
    seed_member,
    seed_role,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call

KNOWN_EMAIL = f"{ADMIN_ID}@example.test"
NEW_EMAIL = "founder@example.test"
NEW_PASSWORD = "a-perfectly-fine-passphrase"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    """The router mounted with its session authenticator wired, as `prope.app` does.

    `GET /auth/session` declares `require_session`, so a fixture that skipped
    `install_session_authenticator` would exercise the refuse-everything default
    and assert nothing. Torn down after each test because the authenticator is a
    module global that closes over this test's sessionmaker.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(access_control_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    yield application
    reset_session_authenticator()


def _cookie_from(response) -> str:
    return response.headers["set-cookie"].split(f"{SESSION_COOKIE}=", 1)[1].split(";", 1)[0]


async def _seed_account(migrate_engine: AsyncEngine) -> None:
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, role=Role.ADMIN.value)


# ---------------------------------------------------------------------------
# GET /api/v1/auth/session
# ---------------------------------------------------------------------------


async def test_the_session_read_answers_what_the_sign_in_answered(api, migrate_engine) -> None:
    """One shape for both routes, so the SPA has one session store and not two.

    A client that had to reconcile a login body with a session body would be a
    client with two chances to render a stale name — which is the failure the
    shared `SessionRead` exists to make unavailable.
    """
    await _seed_account(migrate_engine)

    signed_in = await call(
        api, "POST", "/api/v1/auth/login", json_body={"email": KNOWN_EMAIL, "password": PASSWORD}
    )
    assert signed_in.status_code == 200, signed_in.body

    read = await call(
        api,
        "GET",
        "/api/v1/auth/session",
        headers={"cookie": f"{SESSION_COOKIE}={_cookie_from(signed_in)}"},
    )

    assert read.status_code == 200, read.body
    assert read.json() == signed_in.json()
    assert read.json()["user"]["roles"] == [Role.ADMIN.value]


async def test_the_session_read_refuses_without_a_cookie(api, migrate_engine) -> None:
    """A `401`, which is what the SPA renders the sign-in screen on.

    Not an error the client shows: `getSession()` treats a `401` as "nobody is
    signed in" and every other status as a fault. A `403` here would put the
    signed-out state into the SPA's error path.
    """
    await _seed_account(migrate_engine)

    read = await call(api, "GET", "/api/v1/auth/session")

    assert read.status_code == 401
    assert read.code == "session_required"


async def test_the_session_read_survives_the_forced_password_change(api, migrate_engine) -> None:
    """A-110 must not lock the SPA out of the screen it is sending somebody to.

    `require_session` refuses every route while `must_change_password` is set,
    except the three in `PASSWORD_CHANGE_EXEMPT_ACTIONS`. The change-password
    screen draws the person's name and workspace from this route, so a refusal
    here would send the client somewhere it cannot render.
    """
    await _seed_account(migrate_engine)
    async with migrate_engine.begin() as connection:
        await connection.execute(
            text('UPDATE access."user" SET must_change_password = true WHERE id = :id'),
            {"id": ADMIN_ID},
        )

    signed_in = await call(
        api, "POST", "/api/v1/auth/login", json_body={"email": KNOWN_EMAIL, "password": PASSWORD}
    )
    read = await call(
        api,
        "GET",
        "/api/v1/auth/session",
        headers={"cookie": f"{SESSION_COOKIE}={_cookie_from(signed_in)}"},
    )

    assert read.status_code == 200, read.body
    assert read.json()["must_change_password"] is True

    # The exemption is asserted as a set membership rather than only through the
    # request above, so removing the action from the frozenset fails here too —
    # where the reason is written down.
    assert ManagementAction.AUTH_SESSION.value in PASSWORD_CHANGE_EXEMPT_ACTIONS


async def test_a_route_that_is_not_exempt_still_refuses_during_a_forced_change(
    api, migrate_engine
) -> None:
    """The positive control for the test above. Without it the exemption proves nothing."""
    await _seed_account(migrate_engine)
    async with migrate_engine.begin() as connection:
        await connection.execute(
            text('UPDATE access."user" SET must_change_password = true WHERE id = :id'),
            {"id": ADMIN_ID},
        )

    signed_in = await call(
        api, "POST", "/api/v1/auth/login", json_body={"email": KNOWN_EMAIL, "password": PASSWORD}
    )
    refused = await call(
        api,
        "GET",
        "/api/v1/permissions",
        headers={"cookie": f"{SESSION_COOKIE}={_cookie_from(signed_in)}"},
    )

    assert refused.status_code == 403
    assert refused.code == "password_change_required"


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


async def test_registration_is_the_only_door_into_an_empty_install(api, migrate_engine) -> None:
    """No rows seeded. A person, a workspace, their founder roles, and a live session.

    This is the assertion the route was added for. Everything else in the product
    authenticates, so a database with no accounts in it had no reachable path to
    its first one.
    """
    registered = await call(
        api,
        "POST",
        "/api/v1/auth/register",
        json_body={
            "display_name": "Người sáng lập",
            "email": NEW_EMAIL,
            "password": NEW_PASSWORD,
        },
    )

    assert registered.status_code == 201, registered.body
    payload = registered.json()
    assert payload["user"]["email"] == NEW_EMAIL
    # All three working roles, sorted by the session query's `ORDER BY rb.role`.
    # Admin alone is what a workspace with no reachable first prompt looks like:
    # `prompt.create` is Owner's and no other role's. Reviewer joined them on
    # 2026-08-16 so a self-registered founder can complete the release path
    # without a hand-written role binding — see `FOUNDER_ROLES`, which records
    # what that trades away. Viewer is absent because it confers nothing Owner
    # does not already hold.
    assert payload["user"]["roles"] == [
        Role.ADMIN.value,
        Role.OWNER.value,
        Role.REVIEWER.value,
    ]
    assert payload["user"]["workspace_name"] == "Người sáng lập"

    # A-110's flag is about a credential an Admin read out loud, and this person
    # chose their own. Setting it here would send them from the sign-up form
    # straight to a change-password screen.
    assert payload["must_change_password"] is False

    # The session is live, not merely issued: the cookie authenticates on the very
    # next request, which is what makes sign-up-then-work one flow instead of two.
    read = await call(
        api,
        "GET",
        "/api/v1/auth/session",
        headers={"cookie": f"{SESSION_COOKIE}={_cookie_from(registered)}"},
    )
    assert read.status_code == 200, read.body
    assert read.json()["user"]["id"] == payload["user"]["id"]


async def test_registration_refuses_an_email_that_is_already_registered(
    api, migrate_engine
) -> None:
    """The disclosure `commands.register_account` records under OQ-139, asserted.

    It is a real enumeration oracle and it is written down rather than argued
    away — this test exists so that a later attempt to "fix" it by answering
    `201` fails loudly, because answering `201` would hand back a session for an
    account the caller cannot use.
    """
    await _seed_account(migrate_engine)

    refused = await call(
        api,
        "POST",
        "/api/v1/auth/register",
        json_body={"display_name": "Kẻ mạo danh", "email": KNOWN_EMAIL, "password": NEW_PASSWORD},
    )

    assert refused.status_code == 409
    assert refused.code == ErrorCode.EMAIL_ALREADY_REGISTERED.value
    assert "set-cookie" not in refused.headers


async def test_a_failed_registration_cannot_lock_the_real_owner_out(api, migrate_engine) -> None:
    """`record_source_failure`, and why registration may not touch the email window.

    Counting a refused sign-up against the email bucket would hand anybody who can
    reach the port an account-lockout primitive: five attempts to register an
    address a real person owns would fill their sign-in window. So the refusals
    below must not cost the owner their next sign-in.
    """
    await _seed_account(migrate_engine)

    for _ in range(6):
        refused = await call(
            api,
            "POST",
            "/api/v1/auth/register",
            json_body={"display_name": "Kẻ mạo danh", "email": KNOWN_EMAIL, "password": NEW_PASSWORD},
        )
        assert refused.status_code == 409

    signed_in = await call(
        api, "POST", "/api/v1/auth/login", json_body={"email": KNOWN_EMAIL, "password": PASSWORD}
    )

    assert signed_in.status_code == 200, signed_in.body


async def test_two_people_with_the_same_name_both_get_a_workspace(api, migrate_engine) -> None:
    """The derived slug carries entropy, so the second person is not refused.

    A slug taken from the display name alone would make the second "Marketing" a
    `409` about a field the person never sent — and a slug field on the form would
    make its refusal a read of what other workspaces exist.
    """
    first = await call(
        api,
        "POST",
        "/api/v1/auth/register",
        json_body={"display_name": "Marketing", "email": "one@example.test", "password": NEW_PASSWORD},
    )
    second = await call(
        api,
        "POST",
        "/api/v1/auth/register",
        json_body={"display_name": "Marketing", "email": "two@example.test", "password": NEW_PASSWORD},
    )

    assert first.status_code == 201, first.body
    assert second.status_code == 201, second.body
    assert first.json()["user"]["workspace_id"] != second.json()["user"]["workspace_id"]


def test_a_derived_slug_is_always_legal() -> None:
    """`ck_workspace_slug_format` is `^[a-z0-9][a-z0-9-]{1,62}$`, and it is a CHECK.

    A display name of nothing but punctuation, or one in a script with no ASCII in
    it at all, must still produce a slug the engine accepts — otherwise sign-up
    fails with a constraint violation the person cannot act on. Vietnamese is the
    MVP's only interface language (ADR-0053), so the third case is the ordinary one
    rather than the exotic one.
    """
    import re

    pattern = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
    for display_name in ("Marketing", "!!!", "Người sáng lập", "-leading-dash", "x" * 300):
        assert pattern.match(derive_workspace_slug(display_name)), display_name


# ---------------------------------------------------------------------------
# PROPE_COOKIE_SECURE
# ---------------------------------------------------------------------------


def test_the_cookie_is_secure_unless_somebody_says_otherwise(monkeypatch) -> None:
    """The default is the production value, so forgetting the key cannot drop `Secure`.

    The setting exists because ADR-0033's stated development target is a laptop,
    where the ingress listens on `:80` and a browser silently discards a `Secure`
    cookie — a failure that looks like a successful sign-in followed by `401`s with
    nothing in any log. That is worth a setting; it is not worth a default that
    fails open.
    """
    monkeypatch.setenv("PROPE_DATABASE_URL", "postgresql+asyncpg://prope_app:x@localhost/prope")
    monkeypatch.setenv("PROPE_BROKER_URL", "amqp://guest:guest@localhost/")
    monkeypatch.delenv("PROPE_COOKIE_SECURE", raising=False)

    assert Settings(_env_file=None).cookie_secure is True
    monkeypatch.setenv("PROPE_COOKIE_SECURE", "false")
    assert Settings(_env_file=None).cookie_secure is False
