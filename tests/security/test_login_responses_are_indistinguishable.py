"""T-002 / A-144. Unknown email, wrong password and rate-limited are one response.

The threat is account enumeration, and the failure is quiet: a sign-in endpoint
that answers a fraction differently for a registered address hands an attacker the
workspace's staff list before they have guessed a single password. ADR-0043 closes
it in three places and each is asserted separately below, because each can be
undone on its own.

**The ordering proof is the one that matters and it cannot be timed.** A test that
measured wall time would be a flaky test asserting a property that is true in the
code, so the limiter's *position* is proved structurally instead: the hasher is
monkeypatched to raise, and a rate-limited attempt that still returns a refusal is
an attempt that never reached it.
"""

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.access_control import passwords
from prope.access_control.api import router as access_control_router
from prope.access_control.limiter import PER_EMAIL_FAILURES, LoginLimiter
from prope.access_control.sessions import sign_in
from prope.errors import ErrorCode, install_error_envelope
from tests.access_control import (
    ADMIN_ID,
    MEMBER_ID,
    PASSWORD,
    seed_member,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call

KNOWN_EMAIL = f"{ADMIN_ID}@example.test"
UNKNOWN_EMAIL = "nobody@example.test"
SOURCE = "198.51.100.7"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]) -> FastAPI:
    """`POST /api/v1/auth/login` mounted alone. It declares no session by design."""
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(access_control_router)
    application.state.sessionmaker = app_sessionmaker
    return application


async def _seed_account(migrate_engine: AsyncEngine) -> None:
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)


def _body(email: str, password: str) -> dict[str, str]:
    return {"email": email, "password": password}


async def test_a_correct_sign_in_succeeds_so_the_refusals_below_mean_something(
    api, migrate_engine
) -> None:
    """The positive control. Every assertion in this file is vacuous without it."""
    await _seed_account(migrate_engine)

    response = await call(api, "POST", "/api/v1/auth/login", json_body=_body(KNOWN_EMAIL, PASSWORD))

    assert response.status_code == 200, response.body
    assert response.json()["user"]["id"] == ADMIN_ID
    assert "prope_session=" in response.headers["set-cookie"]


async def test_the_session_id_is_in_the_cookie_and_not_in_the_body(api, migrate_engine) -> None:
    """ADR-0029. A body field would put a bearer credential where a script can read it.

    The response body grew when ADR-0052's SPA landed — it now carries the person,
    their roles and their workspace's name, so the account chip can be drawn
    without a second round trip. **The assertion that matters did not change**: the
    session id is still absent from it. What `id` carries is
    `sessions.public_session_id`'s digest, which is checked below to be neither the
    cookie nor prefixed like one.
    """
    await _seed_account(migrate_engine)

    response = await call(api, "POST", "/api/v1/auth/login", json_body=_body(KNOWN_EMAIL, PASSWORD))
    cookie = response.headers["set-cookie"]
    session_id = cookie.split("prope_session=", 1)[1].split(";", 1)[0]
    payload = response.json()

    assert session_id.startswith("ses_")
    assert session_id not in response.body.decode()

    # The digest is not the credential and does not look like it. A `ses_` prefix
    # here would be the one thing that invites somebody to try it as a cookie.
    assert payload["id"].startswith("sid_")
    assert payload["id"] != session_id

    assert set(payload) == {"id", "expires_at", "must_change_password", "user"}
    assert set(payload["user"]) == {
        "id",
        "display_name",
        "email",
        "roles",
        "workspace_id",
        "workspace_name",
    }
    for attribute in ("HttpOnly", "Secure", "SameSite=lax"):
        assert attribute.lower() in cookie.lower(), cookie


async def test_an_unknown_email_and_a_wrong_password_are_byte_identical(
    api, migrate_engine
) -> None:
    """The enumeration oracle, closed. Status, headers and body — not just status."""
    await _seed_account(migrate_engine)

    unknown = await call(
        api, "POST", "/api/v1/auth/login", json_body=_body(UNKNOWN_EMAIL, "whatever-it-is")
    )
    wrong = await call(
        api, "POST", "/api/v1/auth/login", json_body=_body(KNOWN_EMAIL, "not-the-password")
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.code == wrong.code == ErrorCode.AUTHENTICATION_FAILED.value
    assert "set-cookie" not in unknown.headers
    assert "set-cookie" not in wrong.headers

    # The request_id differs per request by construction, so it is the one field
    # excluded rather than the comparison being loosened to a status check.
    assert _without_request_id(unknown) == _without_request_id(wrong)


async def test_a_tombstoned_account_is_indistinguishable_from_an_unknown_one(
    api, migrate_engine
) -> None:
    """A-151. A departed colleague's address must not answer differently.

    A tombstoned row keeps its id and drops its email, so `LOAD_USER_BY_EMAIL`
    simply does not find it — and the NULL `password_hash` a tombstone leaves
    behind is what `passwords.verify(None, ...)` is written to charge full price
    for.
    """
    await _seed_account(migrate_engine)
    async with migrate_engine.begin() as connection:
        from sqlalchemy import text

        await connection.execute(
            text(
                'UPDATE access."user" SET email = NULL, display_name = NULL, '
                "password_hash = NULL, must_change_password = false, status = 'tombstoned', "
                "tombstoned_at = now(), tombstoned_by = :actor WHERE id = :id"
            ),
            {"id": ADMIN_ID, "actor": ADMIN_ID},
        )

    tombstoned = await call(
        api, "POST", "/api/v1/auth/login", json_body=_body(KNOWN_EMAIL, PASSWORD)
    )
    unknown = await call(
        api, "POST", "/api/v1/auth/login", json_body=_body(UNKNOWN_EMAIL, PASSWORD)
    )

    assert tombstoned.status_code == 401
    assert _without_request_id(tombstoned) == _without_request_id(unknown)


async def test_a_person_with_no_active_membership_signs_in_to_the_lobby(
    api, migrate_engine, app_sessionmaker
) -> None:
    """**This assertion was inverted by ADR-0056, and the reason is worth the note.**

    It used to require that a removed member and a stranger got the same `401`,
    so that nothing leaked *"this person used to work here"* out of a sign-in box.
    That answer was only ever available because a session had to name a tenant:
    with no membership there was no session to issue, and refusing was the sole
    option rather than the chosen one.

    A session may now name no workspace, and the same refusal would lock somebody
    out of the very screen that exists to give them one — including a person who
    registered thirty seconds ago, which is every new account in the product.

    **The oracle is not reopened, because the refusal was never where it lived.**
    Sign-in already answers `200` for an account with a membership, so a `401`
    against a *known* address only ever distinguished *"removed everywhere"* from
    *"still a member"* — and the response body below carries no workspace at all,
    which is byte-identical to what a brand-new account gets. What a caller learns
    from a success here is that they hold the password, which they supplied.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine, MEMBER_ID)

    result = await sign_in(
        app_sessionmaker,
        email=f"{MEMBER_ID}@example.test",
        password=PASSWORD,
        source_address=SOURCE,
        limiter=LoginLimiter(),
    )

    assert result.metric_result == "ok"
    assert result.session is not None
    assert result.session.workspace_id is None


async def test_the_limiter_runs_before_the_hash(
    migrate_engine, app_sessionmaker, monkeypatch
) -> None:
    """ADR-0043's ordering, proved structurally rather than by timing.

    A hasher that raises if it is called turns *"the limiter runs first"* into a
    property with a witness: the rate-limited attempt below returns a refusal, so
    it cannot have reached argon2id. Timing would have made this a flaky test
    about a fact the code already settles.

    This is also the ordering that bounds argon2id's aggregate cost on a 4-vCPU
    host, which ADR-0043 says is the limiter's real job — protecting the password
    is the secondary benefit.
    """
    await _seed_account(migrate_engine)
    private = LoginLimiter()

    for _ in range(PER_EMAIL_FAILURES):
        private.record_failure(email=KNOWN_EMAIL, source_address=SOURCE)

    def explode(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("argon2id ran on a rate-limited attempt")

    monkeypatch.setattr(passwords, "verify", explode)

    result = await sign_in(
        app_sessionmaker,
        email=KNOWN_EMAIL,
        password=PASSWORD,
        source_address=SOURCE,
        limiter=private,
    )

    assert result.session is None
    assert result.metric_result == "rate_limited"


async def test_the_rate_limited_response_is_the_same_as_the_other_two(
    api, migrate_engine, monkeypatch
) -> None:
    """The third failure, on the wire. A distinguishable 429 would reopen the oracle.

    A rate limiter that announces itself tells an attacker they found a real
    account worth throttling, and it tells them exactly when to resume — both of
    which are the enumeration signal this endpoint spends an argon2id verification
    per request to withhold.
    """
    await _seed_account(migrate_engine)

    private = LoginLimiter()
    for _ in range(PER_EMAIL_FAILURES):
        private.record_failure(email=KNOWN_EMAIL, source_address="testclient")
    monkeypatch.setattr("prope.access_control.sessions.process_limiter", private)

    limited = await call(
        api, "POST", "/api/v1/auth/login", json_body=_body(KNOWN_EMAIL, PASSWORD)
    )
    unknown = await call(
        api, "POST", "/api/v1/auth/login", json_body=_body(UNKNOWN_EMAIL, "whatever-it-is")
    )

    assert limited.status_code == 401
    assert "retry-after" not in limited.headers
    assert _without_request_id(limited) == _without_request_id(unknown)


async def test_the_refusal_echoes_neither_the_email_nor_the_password(
    api, migrate_engine
) -> None:
    """A-046. Neither value appears anywhere in the response."""
    await _seed_account(migrate_engine)
    password = "a-password-that-must-not-be-echoed"

    response = await call(
        api, "POST", "/api/v1/auth/login", json_body=_body(KNOWN_EMAIL, password)
    )
    body = response.body.decode()

    assert password not in body
    assert KNOWN_EMAIL not in body


def _without_request_id(response) -> tuple[int, dict[str, str | None]]:
    """The whole envelope but the correlation id, which differs by construction."""
    envelope = dict(response.json()["error"])
    envelope.pop("request_id")
    return response.status_code, envelope
