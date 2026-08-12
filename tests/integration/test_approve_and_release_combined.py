"""AC-12 — A-076: one request, two rows, one transaction, two history events.

The tables are NOT merged and the reason is the Success metric. It is a join
between ``approval`` and ``release``, and merging them turns that query into a
tautology returning 100% whether or not anybody reviewed anything —
restore-without-re-approval (A-028) and break-glass (A-009) depend on the same
separability.

So the friction was a UI problem and it is solved in the UI: one click for the
human, two rows and two events for the record. **Never a third kind of decision**
— every rule of the separate actions applies unchanged, and the state it produces
is asserted field by field against the state the two separate calls produce.

The refusal half is the one that matters most: an actor holding only ``approve``
gets a refusal naming ``release.create``, and **no approval row is written
either**. A build that recorded the approval and then failed on the release would
leave a revision Approved that its reviewer believed they had released.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, seed_prompt, seed_revision
from tests.release_control import (
    ADMIN_ID,
    APPROVER_ID,
    failing_summary,
    passing_summary,
    read_approvals,
    read_releases,
    release_api,
    releases_without_approval,
    seed_actor,
    stub_summary,
)

AUTHOR_SESSION = "ses_release_combined_author"

BOTH_SESSION = "ses_release_combined_both"

APPROVE_ONLY_SESSION = "ses_release_combined_approve_only"

BOTH_ID = "usr_01J000000000000000000BOTH"

COMBINED_VERSION = "rev_01J00000000000000COMBINE"

SEPARATE_VERSION = "rev_01J0000000000000SEPARATE"

REASON = "known failure in the safety suite, accepted for this release"

RELEASED_POINTER = text(
    "SELECT released_version_id FROM registry.prompt_property WHERE id = :prompt_id"
)

HISTORY_ACTIONS = text(
    """
    SELECT action
    FROM   history.history_event
    WHERE  scope_prompt_id = :prompt_id
    ORDER  BY seq
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


async def _a_prompt_and_two_actors(migrate_engine: AsyncEngine) -> None:
    await seed_actor(migrate_engine, AUTHOR_SESSION, roles=("Owner",), user_id=ADMIN_ID)
    await seed_actor(
        migrate_engine,
        BOTH_SESSION,
        roles=("Reviewer", "Admin"),
        user_id=BOTH_ID,
        seed_the_workspace=False,
    )
    await seed_actor(
        migrate_engine,
        APPROVE_ONLY_SESSION,
        roles=("Reviewer",),
        user_id=APPROVER_ID,
        seed_the_workspace=False,
    )
    await seed_prompt(migrate_engine)


async def _submit(api, version_id: str) -> None:  # noqa: ANN001
    submitted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{version_id}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )
    assert submitted.status_code == 201, submitted.body


async def _actions(migrate_engine: AsyncEngine) -> list[str]:
    async with migrate_engine.begin() as connection:
        return list(
            (await connection.execute(HISTORY_ACTIONS, {"prompt_id": PROMPT_ID})).scalars().all()
        )


async def test_one_request_writes_both_rows_and_the_acknowledgement_still_applies(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _a_prompt_and_two_actors(migrate_engine)
    await seed_revision(migrate_engine, COMBINED_VERSION, revision_number=1, author_id=ADMIN_ID)
    await _submit(api, COMBINED_VERSION)

    with stub_summary(monkeypatch, failing_summary(PROMPT_ID, COMBINED_VERSION)):
        refused = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{COMBINED_VERSION}/approve-and-release",
            json_body={"comment": "ship it"},
            headers={"cookie": f"prope_session={BOTH_SESSION}"},
        )
    assert refused.status_code == 422, refused.body
    assert refused.code == "release_acknowledgement_required"
    assert await read_approvals(migrate_engine) == []
    assert await read_releases(migrate_engine) == []

    with stub_summary(monkeypatch, failing_summary(PROMPT_ID, COMBINED_VERSION)):
        done = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{COMBINED_VERSION}/approve-and-release",
            json_body={"comment": "ship it", "acknowledgement_reason": REASON},
            headers={"cookie": f"prope_session={BOTH_SESSION}"},
        )

    assert done.status_code == 201, done.body

    approvals = await read_approvals(migrate_engine)
    releases = await read_releases(migrate_engine)
    assert len(approvals) == 1
    assert len(releases) == 1
    assert releases[0]["approval_id"] == approvals[0]["id"]
    assert approvals[0]["acknowledgement_reason"] == REASON

    async with migrate_engine.begin() as connection:
        pointer = await connection.scalar(RELEASED_POINTER, {"prompt_id": PROMPT_ID})
    assert pointer == COMBINED_VERSION

    assert await releases_without_approval(migrate_engine) == []

    actions = await _actions(migrate_engine)
    assert "revision_approved" in actions
    assert "revision_released" in actions


async def test_an_actor_holding_only_approve_is_refused_and_writes_nothing(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _a_prompt_and_two_actors(migrate_engine)
    await seed_revision(migrate_engine, COMBINED_VERSION, revision_number=1, author_id=ADMIN_ID)
    await _submit(api, COMBINED_VERSION)

    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, COMBINED_VERSION)):
        refused = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{COMBINED_VERSION}/approve-and-release",
            json_body={"comment": "ship it"},
            headers={"cookie": f"prope_session={APPROVE_ONLY_SESSION}"},
        )

    assert refused.status_code == 403, refused.body
    assert refused.json()["error"]["details"]["permission"] == "release.create"

    assert await read_approvals(migrate_engine) == []
    assert await read_releases(migrate_engine) == []
    assert "revision_approved" not in await _actions(migrate_engine)


async def test_the_combined_call_produces_the_same_state_as_the_two_separate_ones(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """A-076's real claim, asserted field by field rather than by inspection.

    Two prompts would be cleaner and would compare two different histories; one
    prompt and two revisions compares the two paths against the SAME prompt, the
    same actor and the same summary, so any difference is the path and nothing
    else. The fields deliberately excluded from the comparison are the ones that
    are supposed to differ: the ids, the version, and the timestamps.
    """
    await _a_prompt_and_two_actors(migrate_engine)
    await seed_revision(migrate_engine, SEPARATE_VERSION, revision_number=1, author_id=ADMIN_ID)
    await seed_revision(migrate_engine, COMBINED_VERSION, revision_number=2, author_id=ADMIN_ID)

    await _submit(api, SEPARATE_VERSION)
    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, SEPARATE_VERSION)):
        await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{SEPARATE_VERSION}/approve",
            json_body={"comment": "ship it"},
            headers={"cookie": f"prope_session={BOTH_SESSION}"},
        )
    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={"version_id": SEPARATE_VERSION, "kind": "release"},
        headers={"cookie": f"prope_session={BOTH_SESSION}"},
    )

    await _submit(api, COMBINED_VERSION)
    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, COMBINED_VERSION)):
        await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{COMBINED_VERSION}/approve-and-release",
            json_body={"comment": "ship it", "expected_current_version_id": SEPARATE_VERSION},
            headers={"cookie": f"prope_session={BOTH_SESSION}"},
        )

    approvals = await read_approvals(migrate_engine)
    releases = await read_releases(migrate_engine)
    assert len(approvals) == 2
    assert len(releases) == 2

    compared = ("decision", "reviewer_id", "comment", "acknowledgement_reason", "self_approved")
    assert {key: approvals[0][key] for key in compared} == {
        key: approvals[1][key] for key in compared
    }

    compared = ("kind", "break_glass", "reason", "released_by")
    assert {key: releases[0][key] for key in compared} == {
        key: releases[1][key] for key in compared
    }
    assert releases[1]["previous_version_id"] == SEPARATE_VERSION
    assert releases[1]["approval_id"] == approvals[1]["id"]
