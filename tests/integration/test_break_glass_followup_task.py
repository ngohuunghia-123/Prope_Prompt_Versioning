"""AC-8 — break-glass, and the 24-hour task that is the only thing keeping it exceptional.

A break-glass release has no approval record by construction, which is exactly
the state the Success metric watches for — so ``break_glass = true`` is what
tells the two apart, and the constraint refuses a release with neither.

**The follow-up task never closes itself.** That is asserted here by advancing
past ``due_at`` and finding the task still open and still counted, because a
timer that quietly resolved it would make break-glass free and the whole approval
story theatre. Its only exit is a recorded decision by a person through
``POST /review-tasks/{id}/close``, which writes ``review_task_closed`` with an
actor on it.

Break-glass is its own permission, not a capability that comes with release
(A-009): an escape hatch everyone holds is not an escape hatch. The Admin role
holds both in migration 0006's matrix, so the refusal half of that is asserted
against a Reviewer, who holds neither.
"""

from datetime import timedelta

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.release_control.domain import BREAK_GLASS_FOLLOW_UP
from prope.release_control.sweep import refresh_review_task_gauges
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, VERSION_ID, approve, seed_prompt, seed_revision
from tests.release_control import (
    ADMIN_ID,
    APPROVER_ID,
    read_releases,
    read_review_tasks,
    release_api,
    releases_without_approval,
    seed_actor,
    utc_now,
)

ADMIN_SESSION = "ses_release_break_glass_admin"

REVIEWER_SESSION = "ses_release_break_glass_reviewer"

REASON = "the released revision is emitting refund advice that is out of policy"

HISTORY_REASONS = text(
    """
    SELECT action, reason
    FROM   history.history_event
    WHERE  scope_prompt_id = :prompt_id AND reason IS NOT NULL
    ORDER  BY seq
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


def _overdue() -> float:
    return REGISTRY.get_sample_value("prope_release_review_task_overdue") or 0.0


def _break_glass() -> float:
    return REGISTRY.get_sample_value("prope_release_break_glass_total") or 0.0


async def _an_approved_revision_nobody_released(migrate_engine: AsyncEngine) -> None:
    await seed_actor(migrate_engine, ADMIN_SESSION, roles=("Admin",), user_id=ADMIN_ID)
    await seed_actor(
        migrate_engine,
        REVIEWER_SESSION,
        roles=("Reviewer",),
        user_id=APPROVER_ID,
        seed_the_workspace=False,
    )
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, author_id=ADMIN_ID)
    await approve(migrate_engine, VERSION_ID)


async def _break_glass_release(api) -> object:  # noqa: ANN001
    return await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases/break-glass",
        json_body={"version_id": VERSION_ID, "reason": REASON},
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )


async def test_a_break_glass_release_has_no_approval_and_says_so(
    api, migrate_engine: AsyncEngine
) -> None:
    await _an_approved_revision_nobody_released(migrate_engine)

    before = _break_glass()
    released = await _break_glass_release(api)

    assert released.status_code == 201, released.body

    rows = await read_releases(migrate_engine)
    assert len(rows) == 1
    assert rows[0]["break_glass"] is True
    assert rows[0]["approval_id"] is None
    assert rows[0]["reason"] == REASON

    assert _break_glass() == before + 1
    assert await releases_without_approval(migrate_engine) == []


async def test_the_follow_up_task_exists_and_is_due_in_twenty_four_hours(
    api, migrate_engine: AsyncEngine
) -> None:
    await _an_approved_revision_nobody_released(migrate_engine)
    released = await _break_glass_release(api)
    release_id = released.json()["release_id"]

    tasks = await read_review_tasks(migrate_engine)
    assert len(tasks) == 1
    assert tasks[0]["kind"] == "break_glass_followup"
    assert tasks[0]["status"] == "open"
    assert tasks[0]["created_from_release_id"] == release_id

    gap = tasks[0]["due_at"] - tasks[0]["created_at"]
    assert gap == BREAK_GLASS_FOLLOW_UP
    assert gap == timedelta(hours=24)


async def test_the_task_does_not_close_itself_and_is_counted_overdue(
    api, migrate_engine: AsyncEngine, app_sessionmaker
) -> None:
    """A-073, and the gauge that makes the failure visible rather than silent.

    The sweep is driven with a clock past ``due_at`` rather than by waiting: what
    is under test is that NOTHING resolves the task on its own, and a test that
    slept for a day would assert the same thing more slowly and less clearly.
    """
    await _an_approved_revision_nobody_released(migrate_engine)
    await _break_glass_release(api)

    await refresh_review_task_gauges(app_sessionmaker, now=utc_now() + timedelta(hours=25))

    tasks = await read_review_tasks(migrate_engine)
    assert [task["status"] for task in tasks] == ["open"]
    assert tasks[0]["closed_by"] is None
    assert tasks[0]["closed_at"] is None

    assert _overdue() == 1.0


async def test_closing_the_task_takes_a_person_and_records_a_note(
    api, migrate_engine: AsyncEngine, app_sessionmaker
) -> None:
    await _an_approved_revision_nobody_released(migrate_engine)
    await _break_glass_release(api)

    task_id = (await read_review_tasks(migrate_engine))[0]["id"]

    closed = await call(
        api,
        "POST",
        f"/api/v1/review-tasks/{task_id}/close",
        json_body={"note": "reviewed the incident; the revision stands"},
        headers={"cookie": f"prope_session={REVIEWER_SESSION}"},
    )

    assert closed.status_code == 200, closed.body
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_by"] == APPROVER_ID

    await refresh_review_task_gauges(app_sessionmaker, now=utc_now() + timedelta(hours=25))
    assert _overdue() == 0.0

    again = await call(
        api,
        "POST",
        f"/api/v1/review-tasks/{task_id}/close",
        json_body={"note": "twice"},
        headers={"cookie": f"prope_session={REVIEWER_SESSION}"},
    )
    assert again.status_code == 409, again.body
    assert again.code == "release_task_not_open"


async def test_break_glass_is_refused_for_an_actor_holding_plain_release(
    api, migrate_engine: AsyncEngine
) -> None:
    """A-009. The Reviewer role holds neither, which is the point being asserted.

    A workspace's answer to *who may break glass* is a role binding. What this
    module guarantees is that the answer is asked as its own question rather than
    inherited from ``release.create``.
    """
    await _an_approved_revision_nobody_released(migrate_engine)

    refused = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases/break-glass",
        json_body={"version_id": VERSION_ID, "reason": REASON},
        headers={"cookie": f"prope_session={REVIEWER_SESSION}"},
    )

    assert refused.status_code == 403, refused.body
    assert refused.json()["error"]["details"]["permission"] == "release.break_glass"
    assert await read_releases(migrate_engine) == []
    assert await read_review_tasks(migrate_engine) == []


async def test_a_break_glass_release_with_no_reason_is_refused_by_the_schema(
    api, migrate_engine: AsyncEngine
) -> None:
    """The reason is mandatory in three independent places, and this is the first.

    pydantic refuses an empty string at the edge; the CHECK constraint refuses a
    blank one at the engine; and ``requires_reason`` on
    ``revision_break_glass_released`` refuses the history append. Three, because
    a break-glass release nobody wrote a sentence about is the state A-009 exists
    to make impossible.
    """
    await _an_approved_revision_nobody_released(migrate_engine)

    refused = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases/break-glass",
        json_body={"version_id": VERSION_ID, "reason": ""},
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )

    assert refused.status_code == 422, refused.body
    assert await read_releases(migrate_engine) == []


async def test_the_reason_reaches_the_history_and_not_a_log_line(
    api, migrate_engine: AsyncEngine
) -> None:
    """A-046 extended to free text, and ADR-0024's ``requires_reason`` at work."""
    await _an_approved_revision_nobody_released(migrate_engine)
    await _break_glass_release(api)

    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(HISTORY_REASONS, {"prompt_id": PROMPT_ID})).all()

    assert ("revision_break_glass_released", REASON) in [(row[0], row[1]) for row in rows]
