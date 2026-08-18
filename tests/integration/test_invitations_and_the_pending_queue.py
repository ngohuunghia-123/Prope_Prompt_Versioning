"""ADR-0057 end to end: a code, a knock, a decision — and the email seat.

**The property this file exists to assert is that a code confers nothing.** The
user's requirement was *"if join by invite code, an Admin must approve before they
can see or watch anything"*, and the mechanism is `workspace_member.status =
'pending'` rather than an active member with no roles: `permissions`'
`WORKSPACE_VISIBLE_ACTIONS` grants `prompt.read`, `suite.read` and `run.read` to
**any** member of the workspace when a prompt's `access_level` is `workspace`, so
a role-less active member would already be reading prompts. `test_a_pending_member_sees_nothing`
is the assertion; everything else here is the flow around it.

**Every refusal on the redemption path is the same refusal.** A code that never
existed, one that expired, one that was revoked, one that is exhausted and one
presented past the rate limit all answer `404 invite_not_redeemable`. That is
asserted as an equality between responses rather than described, because the whole
value of a single code is that nothing tells them apart.
"""

import json

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.access_control import api as access_control_api
from prope.access_control.api import router as access_control_router
from prope.access_control.bootstrap import authenticate_session
from prope.access_control.domain import Role
from prope.access_control.limiter import REDEEM_ATTEMPTS, LoginLimiter
from prope.access_control.observability import invite_redeem_rate_limited_total
from prope.errors import ErrorCode, install_error_envelope
from prope.session_auth import (
    SESSION_COOKIE,
    install_session_authenticator,
    reset_session_authenticator,
)
from tests.access_control import (
    ADMIN_ID,
    PASSWORD,
    WORKSPACE_A,
    WORKSPACE_B,
    seed_member,
    seed_role,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call

ADMIN_EMAIL = f"{ADMIN_ID}@example.test"
JOINER_EMAIL = "joiner@example.test"
JOINER_PASSWORD = "a-perfectly-fine-passphrase"

COUNT_EVENTS = text(
    "SELECT count(*) FROM history.history_event WHERE action = :action"
)

LOAD_EVENT_DETAILS = text(
    "SELECT details FROM history.history_event WHERE action = :action ORDER BY seq DESC LIMIT 1"
)

#: `ck_workspace_invite_expires_after_creation` refuses an expiry before its
#: creation, so both timestamps move. An `expires_at` alone in the past would be
#: refused by the engine, which is the constraint doing its job.
EXPIRE_INVITE = text(
    """
    UPDATE access.workspace_invite
       SET created_at = now() - interval '2 hours',
           expires_at = now() - interval '1 hour'
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession], monkeypatch):
    """The router, wired, with a **private** redemption limiter.

    `limiter.redeem_limiter` is a process-wide singleton and the source-address
    window is shared by every caller — so one test filling it deliberately would
    refuse the next test's first redemption, which is a failure with no
    relationship to what that test asserts. A per-test instance keeps the
    behaviour under test and the accounting out of the way.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(access_control_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    monkeypatch.setattr(
        access_control_api,
        "redeem_limiter",
        LoginLimiter(
            per_email=REDEEM_ATTEMPTS,
            per_source=REDEEM_ATTEMPTS,
            refusal_counter=invite_redeem_rate_limited_total,
        ),
    )
    yield application
    reset_session_authenticator()


def _without_request_id(response) -> str:
    """The refusal body with its correlation id removed.

    `request_id` differs per request by construction, so a byte-for-byte
    comparison of two refusals compares the one field that is *supposed* to
    differ. Everything else — status, code, message, details — must be identical,
    and that is what this leaves behind.
    """
    payload = response.json()
    payload["error"].pop("request_id", None)
    return json.dumps(payload, sort_keys=True)


def _cookie_from(response) -> str:
    return response.headers["set-cookie"].split(f"{SESSION_COOKIE}=", 1)[1].split(";", 1)[0]


async def _seed_admin(migrate_engine: AsyncEngine) -> None:
    """An Admin in workspace A, holding `workspace.manage_members`."""
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, role=Role.ADMIN.value)


async def _admin_cookie(api) -> str:
    signed_in = await call(
        api, "POST", "/api/v1/auth/login", json_body={"email": ADMIN_EMAIL, "password": PASSWORD}
    )
    assert signed_in.status_code == 200, signed_in.body
    return _cookie_from(signed_in)


async def _register_joiner(api, email: str = JOINER_EMAIL) -> tuple[str, str]:
    """A brand-new account with no membership anywhere: a lobby session."""
    registered = await call(
        api,
        "POST",
        "/api/v1/auth/register",
        json_body={"display_name": "Người mới", "email": email, "password": JOINER_PASSWORD},
    )
    assert registered.status_code == 201, registered.body
    assert registered.json()["user"]["workspace_id"] is None
    return _cookie_from(registered), registered.json()["user"]["id"]


async def _create_code(api, admin_cookie: str, **body) -> dict:
    created = await call(
        api,
        "POST",
        f"/api/v1/workspaces/{WORKSPACE_A}/invites",
        json_body=body,
        headers={"cookie": f"{SESSION_COOKIE}={admin_cookie}"},
    )
    assert created.status_code == 201, created.body
    return created.json()


# ---------------------------------------------------------------------------
# The code path
# ---------------------------------------------------------------------------


async def test_a_code_admits_somebody_to_the_queue_and_nothing_else(api, migrate_engine) -> None:
    """Redeem, appear as `pending`, and hold no roles until an Admin says so."""
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)
    invite = await _create_code(api, admin_cookie, roles=[Role.VIEWER.value])

    assert invite["code"] is not None
    assert len(invite["code"]) == 6
    assert invite["invited_email"] is None

    joiner_cookie, joiner_id = await _register_joiner(api)
    redeemed = await call(
        api,
        "POST",
        "/api/v1/auth/invites/redeem",
        json_body={"code": invite["code"]},
        headers={"cookie": f"{SESSION_COOKIE}={joiner_cookie}"},
    )

    assert redeemed.status_code == 200, redeemed.body
    assert redeemed.json()["status"] == "pending"
    assert redeemed.json()["workspace_name"] == "Acme"

    # The chooser shows it, marked pending, with no roles — because roles are
    # bound at approval and there has been none.
    listed = await call(
        api,
        "GET",
        "/api/v1/auth/workspaces",
        headers={"cookie": f"{SESSION_COOKIE}={joiner_cookie}"},
    )
    assert listed.status_code == 200, listed.body
    assert [(row["status"], row["roles"]) for row in listed.json()["items"]] == [("pending", [])]


async def test_a_pending_member_sees_nothing(api, migrate_engine) -> None:
    """**The requirement, asserted.** Entering is refused, so no screen is reachable.

    `enter_workspace` checks for an *active* membership and answers not-found
    otherwise — the same answer a workspace that does not exist gets. A pending
    person therefore cannot obtain a session naming the workspace at all, which
    is what makes "sees nothing" a property of the session rather than a rule
    every read route has to remember.

    This is why `pending` is a status and not an active member with an empty role
    set: `permissions.WORKSPACE_VISIBLE_ACTIONS` grants `prompt.read` to **any**
    member for a workspace-visible prompt, so the role-less version of this
    person would be reading prompts.
    """
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)
    invite = await _create_code(api, admin_cookie)

    joiner_cookie, joiner_id = await _register_joiner(api)
    await call(
        api,
        "POST",
        "/api/v1/auth/invites/redeem",
        json_body={"code": invite["code"]},
        headers={"cookie": f"{SESSION_COOKIE}={joiner_cookie}"},
    )

    entered = await call(
        api,
        "POST",
        f"/api/v1/auth/workspaces/{WORKSPACE_A}/enter",
        headers={"cookie": f"{SESSION_COOKIE}={joiner_cookie}"},
    )

    assert entered.status_code == 404
    assert entered.code == ErrorCode.NOT_FOUND.value


async def test_approval_binds_the_roles_the_admin_chose(api, migrate_engine) -> None:
    """The invitation's roles pre-fill; the approver's roles bind.

    The code below promises `Viewer` and the Admin grants `Reviewer`. What the
    person ends up holding is the second, because an hour can pass between
    creating a code and finding out who used it.
    """
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)
    admin_headers = {"cookie": f"{SESSION_COOKIE}={admin_cookie}"}
    invite = await _create_code(api, admin_cookie, roles=[Role.VIEWER.value])

    joiner_cookie, joiner_id = await _register_joiner(api)
    await call(
        api,
        "POST",
        "/api/v1/auth/invites/redeem",
        json_body={"code": invite["code"]},
        headers={"cookie": f"{SESSION_COOKIE}={joiner_cookie}"},
    )

    pending = await call(
        api,
        "GET",
        f"/api/v1/workspaces/{WORKSPACE_A}/members",
        params={"status": "pending"},
        headers=admin_headers,
    )
    assert pending.status_code == 200, pending.body
    assert [row["email"] for row in pending.json()["items"]] == [JOINER_EMAIL]
    joiner_id = pending.json()["items"][0]["user_id"]

    approved = await call(
        api,
        "POST",
        f"/api/v1/workspaces/{WORKSPACE_A}/members/{joiner_id}/approve",
        json_body={"roles": [Role.REVIEWER.value]},
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.body
    assert approved.json()["roles"] == [Role.REVIEWER.value]

    # And now the session can name the workspace, which is the whole difference.
    entered = await call(
        api,
        "POST",
        f"/api/v1/auth/workspaces/{WORKSPACE_A}/enter",
        headers={"cookie": f"{SESSION_COOKIE}={joiner_cookie}"},
    )
    assert entered.status_code == 200, entered.body
    assert entered.json()["user"]["roles"] == [Role.REVIEWER.value]


async def test_rejection_leaves_the_request_in_the_trail(api, migrate_engine) -> None:
    """A rejected person is a removed person, and both facts survive.

    `member_join_requested` and `member_join_rejected` are two rows in a table
    with no `DELETE` privilege, so the pattern worth seeing — the same person
    knocking repeatedly — cannot be tidied away.
    """
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)
    admin_headers = {"cookie": f"{SESSION_COOKIE}={admin_cookie}"}
    invite = await _create_code(api, admin_cookie)

    joiner_cookie, joiner_id = await _register_joiner(api)
    await call(
        api,
        "POST",
        "/api/v1/auth/invites/redeem",
        json_body={"code": invite["code"]},
        headers={"cookie": f"{SESSION_COOKIE}={joiner_cookie}"},
    )

    rejected = await call(
        api,
        "POST",
        f"/api/v1/workspaces/{WORKSPACE_A}/members/{joiner_id}/reject",
        headers=admin_headers,
    )
    assert rejected.status_code == 204, rejected.body

    async with migrate_engine.begin() as connection:
        requested = await connection.scalar(COUNT_EVENTS, {"action": "member_join_requested"})
        turned_away = await connection.scalar(COUNT_EVENTS, {"action": "member_join_rejected"})
        details = await connection.scalar(
            LOAD_EVENT_DETAILS, {"action": "member_join_requested"}
        )

    assert (requested, turned_away) == (1, 1)
    # The one detail key that makes the chain joinable: which invitation admitted
    # them, and therefore who created it.
    assert details == {"invite_id": invite["invite_id"]}

    # A second approval attempt finds nothing pending. Rejection is final for
    # this request; the person may redeem a fresh code and knock again.
    again = await call(
        api,
        "POST",
        f"/api/v1/workspaces/{WORKSPACE_A}/members/{joiner_id}/approve",
        json_body={"roles": []},
        headers=admin_headers,
    )
    assert again.status_code == 404


async def test_re_redeeming_is_not_an_error(api, migrate_engine) -> None:
    """A reload must not read as a failure, and must not spend a second use."""
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)
    invite = await _create_code(api, admin_cookie, max_uses=1)

    joiner_cookie, joiner_id = await _register_joiner(api)
    headers = {"cookie": f"{SESSION_COOKIE}={joiner_cookie}"}
    body = {"code": invite["code"]}

    first = await call(api, "POST", "/api/v1/auth/invites/redeem", json_body=body, headers=headers)
    second = await call(api, "POST", "/api/v1/auth/invites/redeem", json_body=body, headers=headers)

    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json() == second.json()

    listed = await call(
        api,
        "GET",
        f"/api/v1/workspaces/{WORKSPACE_A}/invites",
        headers={"cookie": f"{SESSION_COOKIE}={admin_cookie}"},
    )
    assert listed.json()[0]["use_count"] == 1


# ---------------------------------------------------------------------------
# One refusal, five ways to earn it
# ---------------------------------------------------------------------------


async def test_every_way_of_failing_answers_identically(api, migrate_engine) -> None:
    """Unknown, expired, revoked and exhausted are one response, byte for byte.

    Asserted as an equality between bodies rather than as four separate status
    checks: the value of a single `invite_not_redeemable` is precisely that a
    guesser cannot tell *"wrong code"* from *"right code, an hour too late"* —
    the second would confirm a workspace exists behind that string.
    """
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)
    admin_headers = {"cookie": f"{SESSION_COOKIE}={admin_cookie}"}
    joiner_cookie, joiner_id = await _register_joiner(api)
    headers = {"cookie": f"{SESSION_COOKIE}={joiner_cookie}"}

    async def redeem(code: str):
        return await call(
            api, "POST", "/api/v1/auth/invites/redeem", json_body={"code": code}, headers=headers
        )

    unknown = await redeem("ZZZZZZ")

    revoked_invite = await _create_code(api, admin_cookie)
    dropped = await call(
        api,
        "DELETE",
        f"/api/v1/workspaces/{WORKSPACE_A}/invites/{revoked_invite['invite_id']}",
        headers=admin_headers,
    )
    assert dropped.status_code == 204, dropped.body
    revoked = await redeem(revoked_invite["code"])

    exhausted_invite = await _create_code(api, admin_cookie, max_uses=1)
    spender, _ = await _register_joiner(api, email="spender@example.test")
    spent = await call(
        api,
        "POST",
        "/api/v1/auth/invites/redeem",
        json_body={"code": exhausted_invite["code"]},
        headers={"cookie": f"{SESSION_COOKIE}={spender}"},
    )
    assert spent.status_code == 200, spent.body
    exhausted = await redeem(exhausted_invite["code"])

    expired_invite = await _create_code(api, admin_cookie)
    async with migrate_engine.begin() as connection:
        await connection.execute(EXPIRE_INVITE)
    expired = await redeem(expired_invite["code"])

    for refusal in (unknown, revoked, exhausted, expired):
        assert refusal.status_code == 404, refusal.body
        assert refusal.code == ErrorCode.INVITE_NOT_REDEEMABLE.value
    assert (
        _without_request_id(unknown)
        == _without_request_id(revoked)
        == _without_request_id(exhausted)
        == _without_request_id(expired)
    )


async def test_the_limiter_answers_the_same_refusal(api, migrate_engine) -> None:
    """A rate-limited attempt is indistinguishable from a wrong code (ADR-0043's rule).

    Ten guesses a quarter hour is what makes six characters survivable; a
    distinguishable refusal would tell a script how much budget it had left,
    which is the first thing it would read.
    """
    await _seed_admin(migrate_engine)
    joiner_cookie, joiner_id = await _register_joiner(api)
    headers = {"cookie": f"{SESSION_COOKIE}={joiner_cookie}"}

    refusals = []
    for _ in range(REDEEM_ATTEMPTS + 1):
        refusals.append(
            await call(
                api,
                "POST",
                "/api/v1/auth/invites/redeem",
                json_body={"code": "ZZZZZZ"},
                headers=headers,
            )
        )

    assert all(refusal.status_code == 404 for refusal in refusals)
    assert len({_without_request_id(refusal) for refusal in refusals}) == 1


# ---------------------------------------------------------------------------
# The email seat
# ---------------------------------------------------------------------------


async def test_an_address_with_no_account_is_a_seat_that_waits(api, migrate_engine) -> None:
    """The user's requirement: invite an address, and it lands when they sign up.

    A membership cannot exist before its user does — `workspace_member.user_id` is
    a foreign key — so the reservation lives on the invitation and is claimed at
    registration. It grants outright, unlike a code: an Admin naming one person is
    the same decision `POST /members` records, and the pending queue exists for
    the case where the workspace does not know who is knocking.
    """
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)

    reserved = await call(
        api,
        "POST",
        f"/api/v1/workspaces/{WORKSPACE_A}/invites",
        json_body={"email": "Newcomer@Example.test", "roles": [Role.OWNER.value]},
        headers={"cookie": f"{SESSION_COOKIE}={admin_cookie}"},
    )
    assert reserved.status_code == 201, reserved.body
    assert reserved.json()["code"] is None
    # Folded on the invitation and only there — `access."user".email` keeps what
    # the person typed, because the sign-in limiter is keyed on that string.
    assert reserved.json()["invited_email"] == "newcomer@example.test"

    registered = await call(
        api,
        "POST",
        "/api/v1/auth/register",
        json_body={
            "display_name": "Người mới",
            "email": "newcomer@example.test",
            "password": JOINER_PASSWORD,
        },
    )

    assert registered.status_code == 201, registered.body
    # Straight in, not the chooser: registration claims before it issues the
    # session, so exactly one active membership binds it.
    assert registered.json()["user"]["workspace_id"] == WORKSPACE_A
    assert registered.json()["user"]["roles"] == [Role.OWNER.value]


async def test_a_seat_reserved_for_an_existing_account_arrives_at_next_sign_in(
    api, migrate_engine
) -> None:
    """The other half of the same feature, and the reason the claim runs twice.

    An Admin inviting somebody who **already has an account** would otherwise
    write a row nothing ever looks at: registration is the only other claim site
    and that person will never register again. So sign-in claims too — after the
    session is issued rather than before, because `sign_in` counts memberships to
    decide where to land and `sessions` cannot import `commands`. The visible
    consequence is asserted here: they arrive on the chooser with the workspace on
    it, one click from where they were going.
    """
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)
    joiner_cookie, joiner_id = await _register_joiner(api)

    reserved = await call(
        api,
        "POST",
        f"/api/v1/workspaces/{WORKSPACE_A}/invites",
        json_body={"email": JOINER_EMAIL, "roles": [Role.VIEWER.value]},
        headers={"cookie": f"{SESSION_COOKIE}={admin_cookie}"},
    )
    assert reserved.status_code == 201, reserved.body

    # Nothing has changed for them yet: the claim happens at the door.
    before = await call(
        api,
        "GET",
        "/api/v1/auth/workspaces",
        headers={"cookie": f"{SESSION_COOKIE}={joiner_cookie}"},
    )
    assert before.json()["items"] == []

    signed_in = await call(
        api,
        "POST",
        "/api/v1/auth/login",
        json_body={"email": JOINER_EMAIL, "password": JOINER_PASSWORD},
    )
    assert signed_in.status_code == 200, signed_in.body

    after = await call(
        api,
        "GET",
        "/api/v1/auth/workspaces",
        headers={"cookie": f"{SESSION_COOKIE}={_cookie_from(signed_in)}"},
    )
    assert [(row["workspace_id"], row["status"], row["roles"]) for row in after.json()["items"]] == [
        (WORKSPACE_A, "active", [Role.VIEWER.value])
    ]


# ---------------------------------------------------------------------------
# Who may do any of this
# ---------------------------------------------------------------------------


async def test_a_member_without_manage_members_may_not_invite(api, migrate_engine) -> None:
    """**`Owner` is a prompt-authoring role and holds no member administration.**

    This is the terminology collision in the request that produced this feature:
    *"Admin or Owner must approve"*. Prope's `Owner` owns prompts (A-007), and
    giving it `workspace.manage_members` would let any prompt author approve a
    member and assign them `Admin` — self-promotion in two clicks, and the end of
    the edit/review/release separation NFR-01 requires. The person who creates a
    workspace already holds `Admin` through `FOUNDER_ROLES`, so the intended user
    of that request is unaffected.
    """
    await _seed_admin(migrate_engine)
    author_id = "usr_01J00000000000000AUTHOR1"
    await seed_user(migrate_engine, user_id=author_id, email="author@example.test")
    await seed_member(migrate_engine, user_id=author_id)
    await seed_role(migrate_engine, role=Role.OWNER.value, user_id=author_id)

    signed_in = await call(
        api,
        "POST",
        "/api/v1/auth/login",
        json_body={"email": "author@example.test", "password": PASSWORD},
    )
    assert signed_in.status_code == 200, signed_in.body

    refused = await call(
        api,
        "POST",
        f"/api/v1/workspaces/{WORKSPACE_A}/invites",
        json_body={},
        headers={"cookie": f"{SESSION_COOKIE}={_cookie_from(signed_in)}"},
    )

    assert refused.status_code == 403
    assert refused.code == ErrorCode.PERMISSION_DENIED.value
    assert refused.json()["error"]["details"]["permission"] == "workspace.manage_members"


async def test_an_invitation_is_invisible_to_another_workspace(api, migrate_engine) -> None:
    """RLS, not a `WHERE` clause. A second workspace's Admin lists none of these.

    The invitation table is tenant-policied like every other one, so the
    cross-tenant answer is an empty list rather than a refusal — a missing filter
    returns zero rows (ADR-0035, ADR-0045), which is the property that makes the
    absence structural.
    """
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)
    await _create_code(api, admin_cookie)

    other_admin = "usr_01J000000000000000OTHER1"
    await seed_workspace(migrate_engine, workspace_id=WORKSPACE_B, slug="wsp-b")
    await seed_user(migrate_engine, user_id=other_admin, email="other@example.test")
    await seed_member(migrate_engine, workspace_id=WORKSPACE_B, user_id=other_admin)
    await seed_role(migrate_engine, role=Role.ADMIN.value, workspace_id=WORKSPACE_B, user_id=other_admin)

    signed_in = await call(
        api,
        "POST",
        "/api/v1/auth/login",
        json_body={"email": "other@example.test", "password": PASSWORD},
    )
    listed = await call(
        api,
        "GET",
        f"/api/v1/workspaces/{WORKSPACE_B}/invites",
        headers={"cookie": f"{SESSION_COOKIE}={_cookie_from(signed_in)}"},
    )

    assert listed.status_code == 200, listed.body
    assert listed.json() == []


async def test_an_expired_invitation_still_lists(api, migrate_engine) -> None:
    """`status` is derived, and this module runs no scheduled work to move it.

    *"I made a code and nobody used it"* is what the screen is usually open to
    answer, so expired and revoked rows are returned rather than filtered.
    """
    await _seed_admin(migrate_engine)
    admin_cookie = await _admin_cookie(api)
    await _create_code(api, admin_cookie)
    async with migrate_engine.begin() as connection:
        await connection.execute(EXPIRE_INVITE)

    listed = await call(
        api,
        "GET",
        f"/api/v1/workspaces/{WORKSPACE_A}/invites",
        headers={"cookie": f"{SESSION_COOKIE}={admin_cookie}"},
    )

    assert [row["status"] for row in listed.json()] == ["expired"]
