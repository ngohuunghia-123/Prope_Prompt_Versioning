"""AC-1 — a save creates the next revision and leaves every earlier one byte-identical.

A-002's whole content, driven through the real route rather than through the
command, because the claim is about what a *save* does and the route is what
authors reach.

**Byte-identical is asserted as bytes**, not as "the body still looks right":
the earlier revisions' rows are read straight from the database as the owner,
before and after, and compared as whole tuples. A revision whose ``created_at``
moved by a microsecond would fail this, which is correct — ADR-0002 says the row
does not change, not that it mostly does not.
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
from tests.prompt_registry import PROMPT_ID, registry_api, seed_prompt, seed_revision

SESSION_ID = "ses_registry_author_000000001"

READ_ALL_REVISIONS = text(
    """
    SELECT version_id, revision_number, body, change_summary, author_id, status, created_at
    FROM   registry.revision
    WHERE  prompt_id = :prompt_id
    ORDER  BY revision_number
    """
)

COUNT_REVISION_EVENTS = text(
    "SELECT count(*) FROM history.history_event WHERE action = 'revision_created'"
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


async def _revisions(migrate_engine) -> list[tuple]:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        return [
            tuple(row)
            for row in (
                await connection.execute(READ_ALL_REVISIONS, {"prompt_id": PROMPT_ID})
            ).all()
        ]


async def test_a_fourth_revision_is_created_and_the_first_three_are_untouched(
    api, migrate_engine
) -> None:
    """AC-1 verbatim: three revisions, one save, four revisions, 1-3 unchanged."""
    await _workspace_with_an_author(migrate_engine)
    await seed_prompt(migrate_engine)
    for number in (1, 2, 3):
        await seed_revision(
            migrate_engine,
            version_id=f"rev_01J00000000000000000000{number}",
            revision_number=number,
            body=f"body {number}",
            change_summary=f"summary {number}",
        )

    before = await _revisions(migrate_engine)
    assert len(before) == 3

    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions",
        json_body={"body": "body 4", "change_summary": "the fourth"},
        headers=_author(),
    )

    assert response.status_code == 201, response.body
    created = response.json()
    assert created["revision_number"] == 4
    assert created["author_id"] == ADMIN_ID
    assert created["status"] == "Draft"
    assert created["created_at"]

    after = await _revisions(migrate_engine)
    assert len(after) == 4
    assert after[:3] == before


async def test_the_revision_and_its_history_event_share_a_transaction(
    api, migrate_engine
) -> None:
    """ADR-0023: the append is in the caller's transaction, so neither exists alone."""
    await _workspace_with_an_author(migrate_engine)
    await seed_prompt(migrate_engine)

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_REVISION_EVENTS) == 0

    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions",
        json_body={"body": "the first body", "change_summary": "first"},
        headers=_author(),
    )
    assert response.status_code == 201, response.body

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_REVISION_EVENTS) == 1
        scoped = await connection.scalar(
            text(
                "SELECT scope_prompt_id FROM history.history_event "
                "WHERE action = 'revision_created'"
            )
        )
        target = await connection.scalar(
            text(
                "SELECT target_id FROM history.history_event WHERE action = 'revision_created'"
            )
        )

    # A-119: the event is ABOUT the revision and SCOPED to the prompt. Both are
    # needed — the first makes the revision's own trail readable, the second is
    # what makes the Activity screen one indexed read.
    assert scoped == PROMPT_ID
    assert target == response.json()["version_id"]


async def test_a_rejected_body_creates_neither_a_revision_nor_an_event(
    api, migrate_engine
) -> None:
    """A-050 at the edge, and the rollback that follows it.

    The author sees a limit message with the current size rather than a truncated
    save — truncating a prompt body silently would corrupt the asset the product
    exists to protect. Asserted with the counts, because a validation refusal
    that had already written the event would be the audit trail describing a
    revision that does not exist.
    """
    await _workspace_with_an_author(migrate_engine)
    await seed_prompt(migrate_engine)

    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions",
        json_body={"body": "x" * 32769, "change_summary": "too big"},
        headers=_author(),
    )

    assert response.status_code == 422
    assert response.code == "validation_failed"

    assert await _revisions(migrate_engine) == []
    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_REVISION_EVENTS) == 0


async def test_a_change_summary_is_required(api, migrate_engine) -> None:
    """A-050. Not optional and not defaulted, because a field that may be skipped
    is a field that is skipped — and the summaries are what make the search
    corpus recover *which prompt did we change for the refund thing*."""
    await _workspace_with_an_author(migrate_engine)
    await seed_prompt(migrate_engine)

    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions",
        json_body={"body": "a body"},
        headers=_author(),
    )

    assert response.status_code == 422
    assert response.code == "validation_failed"
