"""AC-3 — a release moves the pointer, carries its approval, and the Success SQL is empty.

The headline metric of the whole product, asserted as the query the context file
states it as: *release rows with a NULL ``approval_id`` and ``break_glass``
false* must return zero rows. That query is one scan rather than a join across
modules, and the table shape is what makes it so — which is the reason
``approval`` and ``release`` were NOT merged when approve-and-release arrived
(A-076). Merging them turns this assertion into a tautology returning 100%
whether or not anybody reviewed anything.

The pointer is read back from ``registry.prompt_property``, not from this
module's response, for ADR-0008's reason: what this module returns is what it
intended, and A-041 makes the pointer a field only the registry writes.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, VERSION_ID, seed_prompt, seed_revision
from tests.release_control import (
    ADMIN_ID,
    APPROVER_ID,
    passing_summary,
    read_releases,
    release_api,
    releases_without_approval,
    seed_actor,
    stub_summary,
)

AUTHOR_SESSION = "ses_release_carries_author"

APPROVER_SESSION = "ses_release_carries_approver"

RELEASER_SESSION = "ses_release_carries_releaser"

RELEASER_ID = "usr_01J00000000000000RELEASER"

RELEASED_POINTER = text(
    """
    SELECT released_version_id, released_at
    FROM   registry.prompt_property
    WHERE  id = :prompt_id
    """
)

RELEASE_EVENT_DETAILS = text(
    """
    SELECT details
    FROM   history.history_event
    WHERE  scope_prompt_id = :prompt_id AND action = 'revision_released'
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


def _releases(kind: str) -> float:
    return REGISTRY.get_sample_value("prope_release_total", {"kind": kind}) or 0.0


async def _an_approved_revision(api, migrate_engine: AsyncEngine, monkeypatch) -> None:  # noqa: ANN001
    await seed_actor(migrate_engine, AUTHOR_SESSION, roles=("Owner",), user_id=ADMIN_ID)
    await seed_actor(
        migrate_engine,
        APPROVER_SESSION,
        roles=("Reviewer",),
        user_id=APPROVER_ID,
        seed_the_workspace=False,
    )
    await seed_actor(
        migrate_engine,
        RELEASER_SESSION,
        roles=("Admin",),
        user_id=RELEASER_ID,
        seed_the_workspace=False,
    )
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, author_id=ADMIN_ID)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )
    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, VERSION_ID)):
        approved = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body={"comment": "reads well"},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )
    assert approved.status_code == 201, approved.body


async def _pointer(migrate_engine: AsyncEngine) -> tuple:
    async with migrate_engine.begin() as connection:
        row = (
            await connection.execute(RELEASED_POINTER, {"prompt_id": PROMPT_ID})
        ).mappings().one()
    return row["released_version_id"], row["released_at"]


async def test_the_pointer_moves_and_the_release_names_its_approval(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _an_approved_revision(api, migrate_engine, monkeypatch)

    before = _releases("release")
    released = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={"version_id": VERSION_ID, "kind": "release"},
        headers={"cookie": f"prope_session={RELEASER_SESSION}"},
    )

    assert released.status_code == 201, released.body

    version_id, released_at = await _pointer(migrate_engine)
    assert version_id == VERSION_ID
    assert released_at is not None

    rows = await read_releases(migrate_engine)
    assert len(rows) == 1
    assert rows[0]["kind"] == "release"
    assert rows[0]["break_glass"] is False
    assert rows[0]["approval_id"] is not None
    assert rows[0]["released_by"] == RELEASER_ID

    assert _releases("release") == before + 1


async def test_the_success_metric_sql_returns_zero_rows(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _an_approved_revision(api, migrate_engine, monkeypatch)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={"version_id": VERSION_ID, "kind": "release"},
        headers={"cookie": f"prope_session={RELEASER_SESSION}"},
    )

    assert await releases_without_approval(migrate_engine) == []


async def test_the_released_event_carries_the_three_registered_details(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """A-124's allow-list, and what makes the restore trail readable.

    ``revision_released`` is the ONE event this module writes with a details
    payload, and its three registered keys are ``version_id``,
    ``previous_version_id`` and ``break_glass``. A fourth key would be refused by
    ``property_history.append`` before any SQL is issued.
    """
    await _an_approved_revision(api, migrate_engine, monkeypatch)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={"version_id": VERSION_ID, "kind": "release"},
        headers={"cookie": f"prope_session={RELEASER_SESSION}"},
    )

    async with migrate_engine.begin() as connection:
        details = (
            await connection.execute(RELEASE_EVENT_DETAILS, {"prompt_id": PROMPT_ID})
        ).scalars().one()

    assert details == {
        "version_id": VERSION_ID,
        "previous_version_id": None,
        "break_glass": False,
    }


async def test_an_actor_holding_only_approve_cannot_release(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """Edit / review / release are three permissions, and this is the third gate.

    The Reviewer role holds ``revision.approve`` and not ``release.create``. The
    refusal names the missing permission because the reviewer can see the prompt
    (A-116), and nothing is written.
    """
    await _an_approved_revision(api, migrate_engine, monkeypatch)

    refused = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={"version_id": VERSION_ID, "kind": "release"},
        headers={"cookie": f"prope_session={APPROVER_SESSION}"},
    )

    assert refused.status_code == 403, refused.body
    assert refused.json()["error"]["details"]["permission"] == "release.create"
    assert await read_releases(migrate_engine) == []
    assert (await _pointer(migrate_engine))[0] is None


async def test_a_revision_that_is_not_approved_cannot_be_released(
    api, migrate_engine: AsyncEngine
) -> None:
    """BR-03 at this module's edge. The database enforces it independently.

    Defence in depth, and the ORDER matters: this check is the one that produces
    a readable refusal, and ``fk_prompt_property_released_version_id`` is the one
    that holds if this check is ever removed. The database half is asserted
    against direct SQL in
    ``tests/integration/test_released_pointer_constraint.py``, deliberately
    bypassing every service function, because an application-level test alone
    would pass against a build that had lost the constraint.
    """
    await seed_actor(migrate_engine, RELEASER_SESSION, roles=("Admin",), user_id=RELEASER_ID)
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, author_id=ADMIN_ID)

    refused = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={"version_id": VERSION_ID, "kind": "release"},
        headers={"cookie": f"prope_session={RELEASER_SESSION}"},
    )

    assert refused.status_code == 409, refused.body
    assert refused.code == "release_revision_not_approved"
    assert refused.json()["error"]["details"]["status"] == "Draft"
    assert await read_releases(migrate_engine) == []
