"""AC-1 — the ordinary path, end to end, with two different people on it.

A submits a Draft revision; B — not the author, holding ``revision.approve`` —
approves it. Three things must be true afterwards and they live in three
different modules: the revision's status is ``Approved`` in ``registry``, an
approval row with B as reviewer is in ``release``, and a ``revision_approved``
event is in ``history``. That spread is the point rather than an inconvenience:
this module owns exactly one of the three tables and moves the other two by
command and by append.

**The status move is asserted against the registry's own table**, not against
this module's response, because ADR-0008's whole content is that release-control
decides *whether* to ask and prompt-registry decides whether the ask is legal.
A response echoing "Approved" would be true about what this module intended.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, VERSION_ID, seed_prompt, seed_revision
from tests.release_control import (
    ADMIN_ID,
    APPROVER_ID,
    passing_summary,
    read_approvals,
    read_review_tasks,
    release_api,
    seed_actor,
    stub_summary,
)

AUTHOR_SESSION = "ses_release_submit_author"

APPROVER_SESSION = "ses_release_submit_approver"

REVISION_STATUS = text("SELECT status FROM registry.revision WHERE version_id = :version_id")

HISTORY_ACTIONS = text(
    """
    SELECT action, target_id, actor_id
    FROM   history.history_event
    WHERE  scope_prompt_id = :prompt_id
    ORDER  BY seq
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


async def _a_draft_authored_by_a_and_a_reviewer_who_is_not_a(
    migrate_engine: AsyncEngine,
) -> None:
    await seed_actor(migrate_engine, AUTHOR_SESSION, roles=("Owner",), user_id=ADMIN_ID)
    await seed_actor(
        migrate_engine,
        APPROVER_SESSION,
        roles=("Reviewer",),
        user_id=APPROVER_ID,
        seed_the_workspace=False,
    )
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, author_id=ADMIN_ID)


async def _status(migrate_engine: AsyncEngine, version_id: str = VERSION_ID) -> str:
    async with migrate_engine.begin() as connection:
        return str(await connection.scalar(REVISION_STATUS, {"version_id": version_id}))


async def _actions(migrate_engine: AsyncEngine) -> list[tuple[str, str, str]]:
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(HISTORY_ACTIONS, {"prompt_id": PROMPT_ID})).all()
    return [(row[0], row[1], row[2]) for row in rows]


async def test_a_submits_and_b_approves(api, migrate_engine: AsyncEngine, monkeypatch) -> None:
    await _a_draft_authored_by_a_and_a_reviewer_who_is_not_a(migrate_engine)

    submitted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )
    assert submitted.status_code == 201, submitted.body
    assert submitted.json()["status"] == "open"
    assert submitted.json()["kind"] == "review"
    assert await _status(migrate_engine) == "In review"

    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, VERSION_ID)):
        approved = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body={"comment": "reads well"},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )

    assert approved.status_code == 201, approved.body
    assert await _status(migrate_engine) == "Approved"

    approvals = await read_approvals(migrate_engine)
    assert len(approvals) == 1
    assert approvals[0]["decision"] == "approved"
    assert approvals[0]["reviewer_id"] == APPROVER_ID
    assert approvals[0]["self_approved"] is False

    actions = await _actions(migrate_engine)
    assert ("revision_submitted", VERSION_ID, ADMIN_ID) in actions
    assert ("revision_approved", VERSION_ID, APPROVER_ID) in actions


async def test_the_decision_closes_the_review_task_it_answered(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """The queue is a work list, and a decided item leaves it.

    An ordinary review task's exit is the decision itself — there is nothing for
    a human to close afterwards, and leaving it open would put every decided
    revision in the reviewer's queue forever. ``POST /review-tasks/{id}/close``
    exists for the break-glass follow-up (A-073), which has no decision to point
    at.
    """
    await _a_draft_authored_by_a_and_a_reviewer_who_is_not_a(migrate_engine)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )
    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, VERSION_ID)):
        await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body={"comment": "reads well"},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )

    tasks = await read_review_tasks(migrate_engine)
    assert [task["status"] for task in tasks] == ["closed"]
    assert tasks[0]["closed_by"] == APPROVER_ID


async def test_an_author_without_the_approve_permission_is_refused(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """The Owner role holds ``revision.submit`` and not ``revision.approve``.

    NFR-01's separation as data rather than as a rule in this module: A can open
    the review and cannot answer it, and the refusal names the permission because
    A can see the prompt (A-116).
    """
    await _a_draft_authored_by_a_and_a_reviewer_who_is_not_a(migrate_engine)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )

    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, VERSION_ID)):
        refused = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body={"comment": "looks fine to me"},
            headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
        )

    assert refused.status_code == 403, refused.body
    assert refused.code == "permission_denied"
    assert refused.json()["error"]["details"]["permission"] == "revision.approve"
    assert await read_approvals(migrate_engine) == []


async def test_request_changes_returns_the_revision_to_draft_with_a_reason(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """A-066, and the mandatory comment that ADR-0024 enforces at the append.

    The comment is not politeness: ``revision_changes_requested`` carries
    ``requires_reason: true`` in the action registry, so an append with no reason
    is refused by ``property_history`` before any SQL is issued — which means a
    changes-requested decision with nothing written down cannot be recorded at
    all, in either table.
    """
    await _a_draft_authored_by_a_and_a_reviewer_who_is_not_a(migrate_engine)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )

    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, VERSION_ID)):
        answered = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/request-changes",
            json_body={"comment": "the refund window is wrong"},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )

    assert answered.status_code == 201, answered.body
    assert await _status(migrate_engine) == "Draft"

    approvals = await read_approvals(migrate_engine)
    assert [row["decision"] for row in approvals] == ["changes_requested"]

    actions = await _actions(migrate_engine)
    assert ("revision_changes_requested", VERSION_ID, APPROVER_ID) in actions


async def test_a_blank_comment_is_refused_before_anything_is_written(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """``"   "`` satisfies a NOT NULL and is not a reason."""
    await _a_draft_authored_by_a_and_a_reviewer_who_is_not_a(migrate_engine)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )

    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, VERSION_ID)):
        refused = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/request-changes",
            json_body={"comment": "   "},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )

    assert refused.status_code == 422, refused.body
    assert refused.code == "release_reason_required"
    assert await read_approvals(migrate_engine) == []
    assert await _status(migrate_engine) == "In review"
