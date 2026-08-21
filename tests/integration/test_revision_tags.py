"""Revision tags are stamped at save and relabelled without a new revision.

Tags are the one part of a revision that is not immutable, and the two halves of
that claim are asserted against the real routes: a save carries its labels into
the row, and a later ``PATCH`` moves the labels while the body, the change
summary and the revision number stay exactly where they were.

The relabel is checked against the *stored* row rather than against the response
alone. ``prope_app`` holds a column-level ``UPDATE`` grant on this table — status
and tags and nothing else — so a statement that reached one column too far would
be refused by the engine, and reading the row back is what makes that refusal
visible here instead of in production.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.access_control import (
    ADMIN_ID,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, registry_api, seed_prompt

SESSION_ID = "ses_registry_author_000000001"

BODY = "<system>Bạn là trợ lý nội bộ của ACME.</system>"

READ_REVISION = text(
    """
    SELECT revision_number, body, change_summary, tags
    FROM   registry.revision
    WHERE  version_id = :version_id
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _author() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _workspace_with_an_author(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, SESSION_ID)


async def _stored(migrate_engine, version_id: str) -> tuple:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        row = (await connection.execute(READ_REVISION, {"version_id": version_id})).one()
    return tuple(row)


async def test_a_save_carries_its_tags_into_the_row(api, migrate_engine) -> None:
    await _workspace_with_an_author(migrate_engine)
    await seed_prompt(migrate_engine)

    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions",
        json_body={
            "body": BODY,
            "change_summary": "Đăng ký prompt lần đầu.",
            "tags": ["hỗ-trợ", "nội-bộ"],
        },
        headers=_author(),
    )

    assert response.status_code == 201, response.body
    created = response.json()
    assert created["tags"] == ["hỗ-trợ", "nội-bộ"]
    assert created["author_email"] == f"{ADMIN_ID}@example.test"

    _, _, _, stored_tags = await _stored(migrate_engine, created["version_id"])
    assert stored_tags == ["hỗ-trợ", "nội-bộ"]


async def test_a_save_without_tags_is_labelled_with_none(api, migrate_engine) -> None:
    """The column is ``NOT NULL DEFAULT '{}'``, and an unlabelled save says so."""
    await _workspace_with_an_author(migrate_engine)
    await seed_prompt(migrate_engine)

    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions",
        json_body={"body": BODY, "change_summary": "Đăng ký prompt lần đầu."},
        headers=_author(),
    )

    assert response.status_code == 201, response.body
    created = response.json()
    assert created["tags"] == []
    assert (await _stored(migrate_engine, created["version_id"]))[3] == []


async def test_relabelling_moves_the_tags_and_nothing_else(api, migrate_engine) -> None:
    """A-002 survives the one mutable column: the authored content is untouched."""
    await _workspace_with_an_author(migrate_engine)
    await seed_prompt(migrate_engine)

    created = (
        await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions",
            json_body={
                "body": BODY,
                "change_summary": "Đăng ký prompt lần đầu.",
                "tags": ["nháp"],
            },
            headers=_author(),
        )
    ).json()
    version_id = created["version_id"]
    before = await _stored(migrate_engine, version_id)

    response = await call(
        api,
        "PATCH",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{version_id}/tags",
        json_body={"tags": ["đã-duyệt", "nội-bộ"]},
        headers=_author(),
    )

    assert response.status_code == 200, response.body
    assert response.json()["tags"] == ["đã-duyệt", "nội-bộ"]

    after = await _stored(migrate_engine, version_id)
    assert after[:3] == before[:3]
    assert after[3] == ["đã-duyệt", "nội-bộ"]


async def test_relabelling_an_unknown_revision_is_not_found(api, migrate_engine) -> None:
    """The version id is checked against the prompt in the path, not trusted from it."""
    await _workspace_with_an_author(migrate_engine)
    await seed_prompt(migrate_engine)

    response = await call(
        api,
        "PATCH",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/rev_01J000000000000000000099/tags",
        json_body={"tags": ["nội-bộ"]},
        headers=_author(),
    )

    assert response.status_code == 404, response.body
