"""The two routes ADR-0052's SPA needs, and the one setting that lets it reach them.

`GET /api/v1/auth/session` and `POST /api/v1/auth/register` exist for the client
rather than for the domain, which is exactly why they are worth asserting
separately: neither is reachable from the module's own vocabulary, so a
refactoring that broke one would break only the browser.

**Registration is the first door.** Prope has no outbound channel, so before this
route an install with no accounts could not be signed into: `POST /api/v1/workspaces`
authenticates, and nothing could issue the session it wanted.
`test_registration_is_the_only_door_into_an_empty_install` asserts that property
directly, against a database with no rows in it.

**What registration no longer does is create a workspace** (ADR-0056). It issues a
*lobby* session — one whose `workspace_id` is NULL — and the person chooses on the
next screen whether to create a workspace or join one. The founder roles moved with
it: they are bound by `POST /api/v1/workspaces`, where the workspace they name comes
into existence, and a session that names no workspace reports no roles because roles
are per-workspace facts and it is in none.
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
    """No rows seeded. A person, a live lobby session, and no workspace at all.

    This is the assertion the route was added for. Everything else in the product
    authenticates, so a database with no accounts in it had no reachable path to
    its first one. What it does *not* do is pick a workspace on the person's
    behalf: the session it issues names none, and the SPA sends them to the
    chooser (ADR-0056).
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
    # A lobby session is in no workspace, so it holds no roles. Roles are a fact
    # about a membership; there is no membership yet to hold one.
    assert payload["user"]["roles"] == []
    assert payload["user"]["workspace_id"] is None
    assert payload["user"]["workspace_name"] is None

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
    assert read.json()["user"]["workspace_id"] is None


async def test_a_lobby_session_is_refused_by_a_workspace_route(api, migrate_engine) -> None:
    """The positive control for the test above, and the whole point of the split.

    `require_actor` authenticates; `require_session` is what insists on a
    workspace. A route that needed a tenant must refuse a session that names
    none — with its own code, not a `401`, because the person *is* signed in and
    the SPA has somewhere specific to send them.
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
    refused = await call(
        api,
        "GET",
        "/api/v1/permissions",
        headers={"cookie": f"{SESSION_COOKIE}={_cookie_from(registered)}"},
    )

    assert refused.status_code == 403
    assert refused.code == ErrorCode.WORKSPACE_REQUIRED.value


async def test_creating_the_first_workspace_binds_the_founder_roles(api, migrate_engine) -> None:
    """Where the founder bindings went when registration stopped making a workspace.

    All three working roles, sorted by the session query's `ORDER BY rb.role`.
    Admin alone is what a workspace with no reachable first prompt looks like:
    `prompt.create` is Owner's and no other role's. Reviewer joined them on
    2026-08-16 so a self-registered founder can complete the release path without
    a hand-written role binding — see `FOUNDER_ROLES`, which records what that
    trades away. Viewer is absent because it confers nothing Owner does not
    already hold.
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
    cookie = _cookie_from(registered)

    created = await call(
        api,
        "POST",
        "/api/v1/workspaces",
        json_body={"name": "Tiếp thị"},
        headers={"cookie": f"{SESSION_COOKIE}={cookie}"},
    )
    assert created.status_code == 201, created.body

    entered = await call(
        api,
        "POST",
        f"/api/v1/auth/workspaces/{created.json()['workspace_id']}/enter",
        headers={"cookie": f"{SESSION_COOKIE}={cookie}"},
    )

    assert entered.status_code == 200, entered.body
    payload = entered.json()
    assert payload["user"]["workspace_id"] == created.json()["workspace_id"]
    assert payload["user"]["workspace_name"] == "Tiếp thị"
    assert payload["user"]["roles"] == [
        Role.ADMIN.value,
        Role.OWNER.value,
        Role.REVIEWER.value,
    ]

    # Entering reissues: the cookie the lobby session was carried on is gone, and
    # a cross-tenant `UPDATE ... SET workspace_id` was never available to us —
    # the old tenant's WITH CHECK refuses the new value and the new tenant's
    # USING cannot see the row (ADR-0056).
    assert _cookie_from(entered) != cookie
    stale = await call(
        api,
        "GET",
        "/api/v1/auth/session",
        headers={"cookie": f"{SESSION_COOKIE}={cookie}"},
    )
    assert stale.status_code == 401


async def test_switching_between_two_workspaces_leaves_no_live_session_behind(
    api, migrate_engine
) -> None:
    """The one a policy nearly hid. **A tenant-scoped delete cannot reach another tenant's row.**

    `access.session` is tenant-policied, so `DELETE ... WHERE id = :id` issued
    inside the *target* workspace's transaction matches zero rows when the session
    belongs to the workspace being left — silently, because a policy filters
    rather than refuses. That is the same *"a missing filter returns zero rows"*
    property that makes the tenant seam safe (ADR-0045), working against a delete:
    the switch would look correct from the browser, which gets a new cookie, while
    the previous session stayed live for its full lifetime.

    So this asserts the old cookie is dead rather than that the new one works —
    the second is what the happy path already covers.
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
    lobby = _cookie_from(registered)
    headers = {"cookie": f"{SESSION_COOKIE}={lobby}"}

    first = await call(api, "POST", "/api/v1/workspaces", json_body={"name": "Một"}, headers=headers)
    second = await call(api, "POST", "/api/v1/workspaces", json_body={"name": "Hai"}, headers=headers)
    assert first.status_code == 201, first.body
    assert second.status_code == 201, second.body

    entered_first = await call(
        api,
        "POST",
        f"/api/v1/auth/workspaces/{first.json()['workspace_id']}/enter",
        headers=headers,
    )
    assert entered_first.status_code == 200, entered_first.body
    inside_first = _cookie_from(entered_first)

    entered_second = await call(
        api,
        "POST",
        f"/api/v1/auth/workspaces/{second.json()['workspace_id']}/enter",
        headers={"cookie": f"{SESSION_COOKIE}={inside_first}"},
    )
    assert entered_second.status_code == 200, entered_second.body
    assert entered_second.json()["user"]["workspace_id"] == second.json()["workspace_id"]

    # The credential that named the first workspace is gone, not merely replaced
    # in the browser. A live row here is a second live credential for one person's
    # one browser, which is what the delete exists to prevent.
    stale = await call(
        api,
        "GET",
        "/api/v1/auth/session",
        headers={"cookie": f"{SESSION_COOKIE}={inside_first}"},
    )
    assert stale.status_code == 401


async def test_the_workspace_list_is_what_the_chooser_draws(api, migrate_engine) -> None:
    """`GET /auth/workspaces` on a lobby session, which is the one read it must serve.

    The chooser is drawn *before* a tenant is chosen, so this route cannot be
    tenant-scoped. It walks `access.list_workspaces()` — one of the four
    sanctioned `SECURITY DEFINER` functions, which returns identifiers only —
    and reads each membership under that workspace's own tenant context.
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
    cookie = _cookie_from(registered)
    headers = {"cookie": f"{SESSION_COOKIE}={cookie}"}

    empty = await call(api, "GET", "/api/v1/auth/workspaces", headers=headers)
    assert empty.status_code == 200, empty.body
    assert empty.json() == {"items": [], "current_workspace_id": None}

    first = await call(
        api, "POST", "/api/v1/workspaces", json_body={"name": "Tiếp thị"}, headers=headers
    )
    second = await call(
        api, "POST", "/api/v1/workspaces", json_body={"name": "Sản phẩm"}, headers=headers
    )
    assert first.status_code == 201, first.body
    assert second.status_code == 201, second.body

    listed = await call(api, "GET", "/api/v1/auth/workspaces", headers=headers)

    assert listed.status_code == 200, listed.body
    body = listed.json()
    assert [entry["name"] for entry in body["items"]] == ["Tiếp thị", "Sản phẩm"]
    assert all(entry["status"] == "active" for entry in body["items"])
    assert body["current_workspace_id"] is None


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


async def test_two_people_naming_a_workspace_the_same_both_get_one(api, migrate_engine) -> None:
    """The derived slug carries entropy, so the second person is not refused.

    A slug taken from the name alone would make the second "Marketing" a `409`
    about a field the person never sent — and a required slug field on the form
    would make its refusal a read of what other workspaces exist. A caller who
    *does* send one gets the collision named, which is a disclosure an Admin can
    have and a stranger cannot.
    """
    cookies = []
    for email in ("one@example.test", "two@example.test"):
        registered = await call(
            api,
            "POST",
            "/api/v1/auth/register",
            json_body={"display_name": "Marketing", "email": email, "password": NEW_PASSWORD},
        )
        assert registered.status_code == 201, registered.body
        cookies.append(_cookie_from(registered))

    first, second = [
        await call(
            api,
            "POST",
            "/api/v1/workspaces",
            json_body={"name": "Marketing"},
            headers={"cookie": f"{SESSION_COOKIE}={cookie}"},
        )
        for cookie in cookies
    ]

    assert first.status_code == 201, first.body
    assert second.status_code == 201, second.body
    assert first.json()["workspace_id"] != second.json()["workspace_id"]
    assert first.json()["slug"] != second.json()["slug"]


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
