"""AC-5 — retiring a prompt with an active release is refused, and names the release.

A-052, and the reason the guard is in the statement's ``WHERE`` clause rather
than in a preceding ``if``: a release landing between a check and an update would
retire a prompt the gateway is still serving. The refusal reads the pointer
*afterwards*, only to say which release blocked it.

INT-014 is the only way to clear that pointer, and this module cannot issue it on
its own behalf — which is A-041 and ADR-0001 in the one place somebody would be
tempted to work around them.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.prompt_registry import commands
from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import (
    PROMPT_ID,
    VERSION_ID,
    approve,
    registry_api,
    release,
    seed_prompt,
    seed_revision,
)
from tests.unit import WORKSPACE_A

SESSION_ID = "ses_registry_retire_000000001"

READ_STATUS = text("SELECT status FROM registry.prompt_property WHERE id = :id")

COUNT_RETIRED_EVENTS = text(
    "SELECT count(*) FROM history.history_event WHERE action = 'retired'"
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _released_prompt(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)
    await approve(migrate_engine)
    await release(migrate_engine)


async def _status(migrate_engine) -> str:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        return await connection.scalar(READ_STATUS, {"id": PROMPT_ID})


async def test_retire_is_refused_while_a_release_is_active(api, migrate_engine) -> None:
    """AC-5 verbatim: refused, naming the release, and the status is unchanged."""
    await _released_prompt(migrate_engine)

    response = await call(
        api, "POST", f"/api/v1/prompts/{PROMPT_ID}/retire", headers=_owner()
    )

    assert response.status_code == 409, response.body
    assert response.code == "registry_active_release"

    details = response.json()["error"]["details"]
    assert details["released_version_id"] == VERSION_ID
    assert details["model_name"] == "support/refund-classifier"

    assert await _status(migrate_engine) == "active"

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_RETIRED_EVENTS) == 0


async def test_retire_succeeds_once_the_release_is_withdrawn(
    api, migrate_engine, app_sessionmaker
) -> None:
    """INT-014 unblocks it, and nothing else does.

    The withdrawal goes through the command rather than through SQL, because the
    claim under test is that INT-014 is *the* way through — a test that cleared
    the pointer by hand would prove the guard reads the column and nothing about
    the seam.
    """
    await _released_prompt(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await commands.clear_released_revision(
            db, prompt_id=PROMPT_ID, release_id="rel_01J00000000000000000001"
        )

    response = await call(
        api, "POST", f"/api/v1/prompts/{PROMPT_ID}/retire", headers=_owner()
    )

    assert response.status_code == 200, response.body
    assert response.json()["status"] == "retired"
    assert await _status(migrate_engine) == "retired"

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_RETIRED_EVENTS) == 1


async def test_a_retired_prompt_keeps_every_revision(api, migrate_engine) -> None:
    """A-049. ``Retired`` is a status, not a removal, and nothing here deletes.

    The revisions are the asset; the status is a label on the shelf they sit on.
    ``prope_app`` holds no DELETE on either table, which is what makes this a
    privilege rather than a promise — but the visible half is that the chain is
    still readable afterwards.
    """
    await _released_prompt(migrate_engine)
    await seed_revision(
        migrate_engine, version_id="rev_01J000000000000000000REV2", revision_number=2
    )

    async with migrate_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE registry.prompt_property "
                "SET released_version_id = NULL, released_at = NULL WHERE id = :id"
            ),
            {"id": PROMPT_ID},
        )

    retire = await call(
        api, "POST", f"/api/v1/prompts/{PROMPT_ID}/retire", headers=_owner()
    )
    assert retire.status_code == 200, retire.body

    revisions = await call(
        api, "GET", f"/api/v1/prompts/{PROMPT_ID}/revisions", headers=_owner()
    )
    assert revisions.status_code == 200
    assert [row["revision_number"] for row in revisions.json()] == [2, 1]
