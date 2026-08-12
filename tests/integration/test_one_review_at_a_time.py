"""AC-9 — A-067: at most one revision per prompt is In review, and a NEWER one supersedes.

Two rules that sound like one and are not. Submitting revision 6 while revision 5
is In review marks 5's task ``superseded`` and returns 5 to Draft, leaving exactly
one open review task. Submitting revision 5 again — or an older revision — is
REFUSED, because that is not a newer submission, it is two people asking for the
same thing.

The engine holds the invariant rather than this module's ``if``: a partial unique
index over ``(workspace_id, prompt_id) WHERE status = 'open' AND kind = 'review'``
means a second open review task cannot exist even if a code path forgot to look.

**No approval already recorded against revision 5 is altered**, which is the half
that would be easiest to break while tidying: ``approval`` is append-only by
privilege — ``prope_app`` holds SELECT and INSERT and neither UPDATE nor DELETE —
so a supersession that tried to rewrite history would be refused by the engine.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, seed_prompt, seed_revision
from tests.release_control import (
    ADMIN_ID,
    APPROVER_ID,
    failing_summary,
    read_approvals,
    read_review_tasks,
    release_api,
    seed_actor,
    stub_summary,
)

AUTHOR_SESSION = "ses_release_one_review_author"

APPROVER_SESSION = "ses_release_one_review_approver"

VERSION_5 = "rev_01J0000000000000000REV05"

VERSION_6 = "rev_01J0000000000000000REV06"

REVISION_STATUS = text("SELECT status FROM registry.revision WHERE version_id = :version_id")


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


def _submits(outcome: str) -> float:
    return REGISTRY.get_sample_value("prope_release_submit_total", {"outcome": outcome}) or 0.0


async def _two_revisions(migrate_engine: AsyncEngine) -> None:
    await seed_actor(migrate_engine, AUTHOR_SESSION, roles=("Owner",), user_id=ADMIN_ID)
    await seed_actor(
        migrate_engine,
        APPROVER_SESSION,
        roles=("Reviewer",),
        user_id=APPROVER_ID,
        seed_the_workspace=False,
    )
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, VERSION_5, revision_number=5, author_id=ADMIN_ID)
    await seed_revision(migrate_engine, VERSION_6, revision_number=6, author_id=ADMIN_ID)


async def _submit(api, version_id: str) -> object:  # noqa: ANN001
    return await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{version_id}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )


async def _status(migrate_engine: AsyncEngine, version_id: str) -> str:
    async with migrate_engine.begin() as connection:
        return str(await connection.scalar(REVISION_STATUS, {"version_id": version_id}))


async def test_a_newer_submission_supersedes_the_open_task(
    api, migrate_engine: AsyncEngine
) -> None:
    await _two_revisions(migrate_engine)

    assert (await _submit(api, VERSION_5)).status_code == 201
    before = _submits("superseded")

    second = await _submit(api, VERSION_6)
    assert second.status_code == 201, second.body

    tasks = await read_review_tasks(migrate_engine)
    by_version = {task["version_id"]: task["status"] for task in tasks}
    assert by_version == {VERSION_5: "superseded", VERSION_6: "open"}

    open_tasks = [task for task in tasks if task["status"] == "open"]
    assert len(open_tasks) == 1

    assert _submits("superseded") == before + 1


async def test_the_superseded_revision_leaves_in_review(
    api, migrate_engine: AsyncEngine
) -> None:
    """A-067's first clause is about the REVISION, not only about the task.

    Leaving revision 5 in ``In review`` with no open task would satisfy "exactly
    one open review task" and break "at most one revision per prompt is In
    review" — two statements of one rule, and a build that honoured only the
    first would show a reviewer a revision waiting for a decision nobody is going
    to make.
    """
    await _two_revisions(migrate_engine)

    await _submit(api, VERSION_5)
    assert await _status(migrate_engine, VERSION_5) == "In review"

    await _submit(api, VERSION_6)

    assert await _status(migrate_engine, VERSION_5) == "Draft"
    assert await _status(migrate_engine, VERSION_6) == "In review"


async def test_resubmitting_the_same_revision_is_refused(
    api, migrate_engine: AsyncEngine
) -> None:
    await _two_revisions(migrate_engine)

    await _submit(api, VERSION_5)
    before = _submits("refused")

    again = await _submit(api, VERSION_5)

    assert again.status_code == 409, again.body
    assert again.code == "release_review_already_open"
    assert again.json()["error"]["details"]["version_id"] == VERSION_5
    assert _submits("refused") == before + 1


async def test_submitting_an_older_revision_is_refused(
    api, migrate_engine: AsyncEngine
) -> None:
    """A supersession runs one way. An older revision arriving is not a newer one."""
    await _two_revisions(migrate_engine)

    await _submit(api, VERSION_6)
    older = await _submit(api, VERSION_5)

    assert older.status_code == 409, older.body
    assert older.code == "release_review_already_open"

    tasks = await read_review_tasks(migrate_engine)
    assert [task["version_id"] for task in tasks if task["status"] == "open"] == [VERSION_6]


async def test_an_approval_recorded_against_the_older_revision_is_untouched(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """The append-only guarantee, exercised across a supersession.

    Revision 5 collects a ``changes_requested`` decision, is put back in review,
    and is then superseded by revision 6. The recorded decision is still there,
    byte for byte, because there is no path in this module or in ``prope_app``'s
    privileges that could edit it.
    """
    await _two_revisions(migrate_engine)

    await _submit(api, VERSION_5)
    with stub_summary(monkeypatch, failing_summary(PROMPT_ID, VERSION_5)):
        answered = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_5}/request-changes",
            json_body={"comment": "the refund window is wrong"},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )
    assert answered.status_code == 201, answered.body

    recorded = await read_approvals(migrate_engine)
    assert len(recorded) == 1

    await _submit(api, VERSION_5)
    await _submit(api, VERSION_6)

    assert await read_approvals(migrate_engine) == recorded
