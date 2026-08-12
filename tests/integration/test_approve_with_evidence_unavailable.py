"""AC-5 — A-070: unknown evidence is treated like FAILING evidence, never like passing.

Evaluation is the one soft dependency in this module's list. When
``get_review_summary`` raises, the review screen still renders — the diff, the
decision controls and the history all work — and the eval panel says the evidence
could not be loaded.

**The reason this is worth its own file** is what the alternative silently does.
Left alone, the approve button behaves exactly as it would on a fully passing
suite, converting *"we do not know"* into *"it is fine"* with nothing in the
record saying which one happened. So the acknowledgement reason becomes
mandatory, the counter moves, and the digest stored on the approval says
``summary_available: false`` — which is what makes an approval taken blind
distinguishable from one taken over a green suite, forever.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, VERSION_ID, seed_prompt, seed_revision
from tests.release_control import (
    ADMIN_ID,
    APPROVER_ID,
    read_approvals,
    release_api,
    seed_actor,
    stub_summary,
    unavailable_summary,
)

AUTHOR_SESSION = "ses_release_blind_author"

APPROVER_SESSION = "ses_release_blind_approver"

REASON = "evidence panel is down and the fix cannot wait"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


def _unavailable() -> float:
    return REGISTRY.get_sample_value("prope_release_summary_unavailable_total") or 0.0


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


async def test_the_review_screen_renders_and_says_the_evidence_is_missing(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _a_revision_in_review(api, migrate_engine)

    before = _unavailable()
    with stub_summary(monkeypatch, unavailable_summary()):
        screen = await call(
            api,
            "GET",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/review",
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )

    assert screen.status_code == 200, screen.body
    body = screen.json()
    assert body["summary"] is None
    assert body["summary_available"] is False
    assert body["acknowledgement_required"] is True
    assert body["revision"]["version_id"] == VERSION_ID
    assert body["history"], "the decision trail still renders without evaluation"

    assert _unavailable() == before + 1


async def test_approving_blind_without_a_reason_is_refused(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _a_revision_in_review(api, migrate_engine)

    with stub_summary(monkeypatch, unavailable_summary()):
        refused = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body={"comment": "looks fine"},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )

    assert refused.status_code == 422, refused.body
    assert refused.code == "release_acknowledgement_required"
    assert refused.json()["error"]["details"]["summary_available"] is False
    assert await read_approvals(migrate_engine) == []


async def test_approval_still_succeeds_with_a_reason_and_the_digest_says_it_was_blind(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """ADR-0005 again: never blocked, and never frictionless on an unknown.

    The digest is what makes this readable a year later. ``summary_available:
    false`` and an empty ``suites`` list is a different sentence from a green
    suite, and the approval carries it rather than the log.
    """
    await _a_revision_in_review(api, migrate_engine)

    with stub_summary(monkeypatch, unavailable_summary()):
        approved = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body={"comment": "looks fine", "acknowledgement_reason": REASON},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )

    assert approved.status_code == 201, approved.body

    approvals = await read_approvals(migrate_engine)
    assert len(approvals) == 1
    assert approvals[0]["acknowledgement_reason"] == REASON

    digest = approvals[0]["evidence_digest"]
    assert digest["summary_available"] is False
    assert digest["requires_acknowledgement"] is True
    assert digest["suites"] == []
