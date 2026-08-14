"""Development bootstrap session authentication through the real access boundary."""

import pytest

from prope.access_control.bootstrap import authenticate_session
from prope.access_control.dev_bootstrap import (
    DEVELOPMENT_ADMIN_USER_ID,
    DEVELOPMENT_ADMIN_WORKSPACE_ID,
    DevelopmentBootstrapError,
    ensure_development_admin_session,
    require_development_environment,
)
from prope.access_control.domain import Actor, ActorType, Subject, SubjectType
from prope.access_control.permissions import may
from prope.db.session import workspace_transaction


def test_fixed_operator_token_is_rejected_outside_development() -> None:
    with pytest.raises(DevelopmentBootstrapError):
        require_development_environment("production")


@pytest.mark.asyncio
async def test_configured_development_token_authenticates_a_full_test_operator(
    app_sessionmaker,
) -> None:
    """The fixed token has a real, live session and can exercise authoring routes."""
    token = "ses_development_admin_test_token"

    await ensure_development_admin_session(app_sessionmaker, token)

    authenticated = await authenticate_session(app_sessionmaker, token)
    assert authenticated is not None
    session, must_change_password = authenticated
    assert session.user_id == DEVELOPMENT_ADMIN_USER_ID
    assert session.workspace_id == DEVELOPMENT_ADMIN_WORKSPACE_ID
    assert must_change_password is False

    async with workspace_transaction(app_sessionmaker, session.workspace_id) as db:
        assert await may(
            db,
            actor=Actor(
                id=session.user_id,
                workspace_id=session.workspace_id,
                type=ActorType.USER,
            ),
            action="prompt.create",
            subject=Subject(
                type=SubjectType.PROMPT,
                id="prm_development_test",
                workspace_id=session.workspace_id,
            ),
        )
