"""AC-4 — ADR-0005's whole content: a failing case WARNS, it never blocks.

The two halves are inseparable and both are asserted here. Approving over a
failing suite with no reason is refused with the failing suites named; approving
with a reason succeeds, stores it, and puts it in the property history where a
person can read it later.

**Neither half is the interesting one on its own.** A build that blocked the
approval would satisfy "the reviewer was stopped" and would have deleted the
decision ADR-0005 made — that a human may knowingly ship over a failure, on the
record. A build that let it through silently would have deleted the record.

The reason travels to the history event and NOT to a log line or a metric label
(A-046). ``acknowledgement_reason`` is a free-text human sentence and can name a
customer or an incident.
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
    failing_summary,
    read_approvals,
    release_api,
    seed_actor,
    stub_summary,
)

AUTHOR_SESSION = "ses_release_ack_author"

APPROVER_SESSION = "ses_release_ack_approver"

REASON = "shipping over the two known safety failures for the Friday incident"

REVISION_STATUS = text("SELECT status FROM registry.revision WHERE version_id = :version_id")


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


def _acknowledged() -> float:
    return REGISTRY.get_sample_value("prope_release_acknowledged_total") or 0.0


async def _a_revision_in_review(api, migrate_engine: AsyncEngine) -> None:  # noqa: ANN001
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
    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )


async def _approve(api, monkeypatch, body: dict) -> object:  # noqa: ANN001
    with stub_summary(monkeypatch, failing_summary(PROMPT_ID, VERSION_ID)):
        return await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body=body,
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )


async def test_approving_over_a_failing_suite_without_a_reason_is_refused(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _a_revision_in_review(api, migrate_engine)

    refused = await _approve(api, monkeypatch, {"comment": "ship it"})

    assert refused.status_code == 422, refused.body
    assert refused.code == "release_acknowledgement_required"
    assert refused.json()["error"]["details"]["failing_suites"] == ["safety"]
    assert refused.json()["error"]["details"]["summary_available"] is True

    assert await read_approvals(migrate_engine) == []
    async with migrate_engine.begin() as connection:
        status = await connection.scalar(REVISION_STATUS, {"version_id": VERSION_ID})
    assert status == "In review"


async def test_a_blank_reason_is_not_a_reason(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """``"   "`` satisfies every schema constraint and answers nothing."""
    await _a_revision_in_review(api, migrate_engine)

    refused = await _approve(
        api, monkeypatch, {"comment": "ship it", "acknowledgement_reason": "   "}
    )

    assert refused.status_code == 422, refused.body
    assert refused.code == "release_acknowledgement_required"
    assert await read_approvals(migrate_engine) == []


async def test_approving_with_a_reason_succeeds_and_stores_it(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _a_revision_in_review(api, migrate_engine)

    before = _acknowledged()
    approved = await _approve(
        api, monkeypatch, {"comment": "ship it", "acknowledgement_reason": REASON}
    )

    assert approved.status_code == 201, approved.body
    assert approved.json()["acknowledgement_reason"] == REASON

    approvals = await read_approvals(migrate_engine)
    assert len(approvals) == 1
    assert approvals[0]["acknowledgement_reason"] == REASON
    assert approvals[0]["decision"] == "approved"

    async with migrate_engine.begin() as connection:
        status = await connection.scalar(REVISION_STATUS, {"version_id": VERSION_ID})
    assert status == "Approved"

    assert _acknowledged() == before + 1


async def test_the_acknowledgement_is_not_the_break_glass_reason(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """ADR-0005 keeps the two apart and they are never merged.

    ``acknowledgement_reason`` lives on the approval — a decision taken over
    failing evidence, with an approval record. ``release.reason`` lives on the
    release — an act taken with no approval record at all. Merging them would
    make ``prope_release_acknowledged_total`` and
    ``prope_release_break_glass_total`` count the same thing, and
    ``AcknowledgementRateHigh`` would then fire on incidents rather than on
    reviewers rubber-stamping.
    """
    await _a_revision_in_review(api, migrate_engine)
    await _approve(api, monkeypatch, {"comment": "ship it", "acknowledgement_reason": REASON})

    approvals = await read_approvals(migrate_engine)
    assert approvals[0]["acknowledgement_reason"] == REASON
    assert "reason" not in approvals[0]
