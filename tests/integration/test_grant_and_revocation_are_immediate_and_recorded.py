"""AC-6 and AC-12. A grant never exists without its event, and a revoke has no TTL.

Two claims that look like one and are not:

* **AC-12** — the grant and its history event share a transaction. There is no
  ordering in which the state change commits and the event does not.
* **AC-6** — the effect of a grant or a revoke is visible on the **next** request,
  with nothing to expire. Nothing in access-control is cached and no caller may
  cache an answer (A-114, ADR-0022), which is what makes this true without a
  footnote about a window.
"""

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control import commands
from prope.access_control.actions import Action
from prope.access_control.api import router as access_control_router
from prope.access_control.bootstrap import authenticate_session
from prope.access_control.domain import AccessLevel, Actor, ActorType, GrantLevel, Subject, SubjectType
from prope.access_control.permissions import may
from prope.db.session import workspace_transaction
from prope.errors import ErrorCode, install_error_envelope
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    ADMIN_ID,
    MEMBER_ID,
    PROMPT_ID,
    WORKSPACE_A,
    day,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call

OWNER_SESSION = "ses_grant_owner_00000000000001"

COUNT_GRANTS = text("SELECT count(*) FROM access.prompt_grant")
COUNT_GRANT_EVENTS = text(
    "SELECT count(*) FROM history.history_event WHERE action IN ('access_granted', 'access_revoked')"
)
READ_GRANT_EVENTS = text(
    "SELECT action, target_id, details::text FROM history.history_event "
    "WHERE action IN ('access_granted', 'access_revoked') ORDER BY seq"
)

#: The prompt's attributes, as the SPA passes them (ADR-0020). This module reads
#: no prompt table and cannot: the edge is forbidden.
OWNED_BY_ADMIN = {"owner_id": ADMIN_ID, "access_level": "private"}


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


async def _owner_and_colleague(migrate_engine) -> None:
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, OWNER_SESSION)
    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(migrate_engine, user_id=MEMBER_ID)


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={OWNER_SESSION}"}


def _grantee_asking(action: Action) -> tuple[Actor, Action, Subject]:
    return (
        Actor(type=ActorType.USER, id=MEMBER_ID, workspace_id=WORKSPACE_A),
        action,
        Subject(
            type=SubjectType.PROMPT,
            id=PROMPT_ID,
            workspace_id=WORKSPACE_A,
            owner_id=ADMIN_ID,
            access_level=AccessLevel.PRIVATE,
        ),
    )


async def _may(app_sessionmaker, action: Action) -> bool:
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        return await may(db, *_grantee_asking(action))


async def test_a_grant_takes_effect_on_the_next_request(
    api, migrate_engine, app_sessionmaker
) -> None:
    """Before, after, and nothing in between."""
    await _owner_and_colleague(migrate_engine)

    assert await _may(app_sessionmaker, Action.PROMPT_READ) is False

    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/grants",
        params=OWNED_BY_ADMIN,
        json_body={"grantee_user_id": MEMBER_ID, "level": "viewer"},
        headers=_owner(),
    )
    assert response.status_code == 201, response.body

    assert await _may(app_sessionmaker, Action.PROMPT_READ) is True


async def test_a_revoke_takes_effect_on_the_next_request_with_no_ttl(
    api, migrate_engine, app_sessionmaker
) -> None:
    """AC-6. There is no cache to invalidate, which is why there is no window."""
    await _owner_and_colleague(migrate_engine)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/grants",
        params=OWNED_BY_ADMIN,
        json_body={"grantee_user_id": MEMBER_ID, "level": "viewer"},
        headers=_owner(),
    )
    assert await _may(app_sessionmaker, Action.PROMPT_READ) is True

    revoke = await call(
        api,
        "DELETE",
        f"/api/v1/prompts/{PROMPT_ID}/grants/{MEMBER_ID}",
        params=OWNED_BY_ADMIN,
        headers=_owner(),
    )
    assert revoke.status_code == 204, revoke.body

    assert await _may(app_sessionmaker, Action.PROMPT_READ) is False


async def test_a_viewer_raised_to_editor_gains_exactly_the_editor_actions(
    api, migrate_engine, app_sessionmaker
) -> None:
    """A-112's ceiling, on both sides of the raise.

    An editor may read and revise. It may **not** submit for review: that is the
    first step of the release path, and A-112 exists so a workspace's separation
    of edit / review / release cannot be dissolved one prompt at a time by an
    owner being helpful.
    """
    await _owner_and_colleague(migrate_engine)

    for level in ("viewer", "editor"):
        response = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/grants",
            params=OWNED_BY_ADMIN,
            json_body={"grantee_user_id": MEMBER_ID, "level": level},
            headers=_owner(),
        )
        assert response.status_code == 201, response.body

        expected_edit = level == "editor"
        assert await _may(app_sessionmaker, Action.PROMPT_READ) is True
        assert await _may(app_sessionmaker, Action.PROMPT_EDIT) is expected_edit
        assert await _may(app_sessionmaker, Action.REVISION_CREATE) is expected_edit
        assert await _may(app_sessionmaker, Action.REVISION_SUBMIT) is False
        assert await _may(app_sessionmaker, Action.REVISION_APPROVE) is False
        assert await _may(app_sessionmaker, Action.RELEASE_CREATE) is False


async def test_the_grant_and_its_event_are_written_together(api, migrate_engine) -> None:
    """AC-12's happy half. The event carries the grantee and the level (D-62)."""
    await _owner_and_colleague(migrate_engine)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/grants",
        params=OWNED_BY_ADMIN,
        json_body={"grantee_user_id": MEMBER_ID, "level": "editor"},
        headers=_owner(),
    )

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_GRANTS)).scalar_one() == 1
        events = (await connection.execute(READ_GRANT_EVENTS)).all()

    assert len(events) == 1
    action, target_id, details = events[0]
    assert action == "access_granted"
    assert target_id == PROMPT_ID
    assert MEMBER_ID in details
    assert "editor" in details


async def test_a_refused_event_takes_the_grant_with_it(
    migrate_engine, app_sessionmaker, monkeypatch
) -> None:
    """AC-12's real half: there is no grant without a trail.

    `append()` raising fails the caller's transaction, and there is no `try`
    anywhere on this path — that raise **is** the mechanism. Simulated by making
    the event builder refuse, which is what an unregistered action or an
    unregistered details key would do in production.
    """
    await _owner_and_colleague(migrate_engine)

    async def refuse(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("the registry refused this event")

    monkeypatch.setattr(commands.events, "access_granted", refuse)

    with pytest.raises(RuntimeError):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            await commands.grant_access(
                db,
                workspace_id=WORKSPACE_A,
                actor_id=ADMIN_ID,
                prompt_id=PROMPT_ID,
                grantee_user_id=MEMBER_ID,
                level=GrantLevel.VIEWER,
                now=day(3),
            )

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_GRANTS)).scalar_one() == 0
        assert (await connection.execute(COUNT_GRANT_EVENTS)).scalar_one() == 0


async def test_the_revocation_event_records_the_level_the_grant_had(
    api, migrate_engine
) -> None:
    """Read before the delete, because the row is gone afterwards.

    Nothing else in the system records what a revoked grant used to confer, so
    without it *"how many editor grants are live"* is unanswerable from the trail
    the moment anything is revoked.
    """
    await _owner_and_colleague(migrate_engine)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/grants",
        params=OWNED_BY_ADMIN,
        json_body={"grantee_user_id": MEMBER_ID, "level": "editor"},
        headers=_owner(),
    )
    await call(
        api,
        "DELETE",
        f"/api/v1/prompts/{PROMPT_ID}/grants/{MEMBER_ID}",
        params=OWNED_BY_ADMIN,
        headers=_owner(),
    )

    async with migrate_engine.begin() as connection:
        events = (await connection.execute(READ_GRANT_EVENTS)).all()

    assert [row.action for row in events] == ["access_granted", "access_revoked"]
    assert "editor" in events[1].details


async def test_a_colleague_who_cannot_see_the_prompt_gets_not_found(
    api, migrate_engine
) -> None:
    """A-116 / BR-01. Private by default, enforced as not-found and never forbidden.

    The grantee holds no role that reads workspace-wide and no grant, so the
    prompt does not exist as far as they are concerned — and the response is
    byte-identical to one for an id that genuinely does not exist.
    """
    await _owner_and_colleague(migrate_engine)
    colleague_session = "ses_grant_colleague_000000001"
    await seed_session(migrate_engine, colleague_session, user_id=MEMBER_ID)
    headers = {"cookie": f"prope_session={colleague_session}"}

    real = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/grants",
        params=OWNED_BY_ADMIN,
        headers=headers,
    )
    imaginary = await call(
        api,
        "GET",
        "/api/v1/prompts/prm_this-one-does-not-exist/grants",
        params=OWNED_BY_ADMIN,
        headers=headers,
    )

    assert real.status_code == imaginary.status_code == 404
    assert real.code == imaginary.code == ErrorCode.NOT_FOUND.value
    assert real.json()["error"]["message"] == imaginary.json()["error"]["message"]
