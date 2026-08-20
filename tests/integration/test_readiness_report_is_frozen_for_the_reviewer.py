"""AC-7 and SR-1 — what the reviewer approved against does not move afterwards.

**The freeze exists because the card is evidence at review time**, and evidence
that recomputes is not evidence. A reviewer approves a revision having seen four
findings and two dismissals; a rule catalogue corrected the following week must
not rewrite the screen that decision was recorded against. That is
release-control's own posture about approvals, applied to the thing being
approved alongside it.

**The lazy write is the interesting part, and it is a resolution rather than a
convenience.** The lock's flow said *frozen at submit*, and its
``forbidden_dependencies`` make release-control absolute **in both directions** —
so no hook inside ``set_revision_status`` could write this row without the edge
the lock forbids. The freeze therefore happens on the first card read of a
revision past ``Draft``, and what makes that safe is
``uq_readiness_report_version``: two readers racing produce one row, because the
uniqueness is the database's and not an application-level *check then insert*.

**A draft is deliberately NOT frozen.** An author editing a body wants the panel
to follow them, and a card that froze on first sight would be stale by the second
keystroke. The two behaviours are asserted against each other here, because
either one alone is satisfied by an implementation that always does the same
thing.
"""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.prompt_readiness import domain as readiness_domain
from tests.evaluation import PROMPT_ID, seed_owner
from tests.integration._asgi import call
from tests.prompt_readiness import readiness_api
from tests.prompt_registry import seed_prompt, seed_revision

SESSION_ID = "ses_readiness_frozen_0000001"

DRAFT_VERSION = "rev_01J000000000000000DRAFT1"

SUBMITTED_VERSION = "rev_01J0000000000000000SUBM1"

COUNT_REPORTS = text("SELECT count(*) FROM readiness.report WHERE version_id = :version_id")

READ_REPORT = text(
    "SELECT catalogue_version, profile_snapshot, rendered_findings "
    "FROM readiness.report WHERE version_id = :version_id"
)

#: Trips the spotlighting rule, so the card has something on it. A body with no
#: findings would freeze an empty report and every assertion below would hold
#: for an implementation that stored nothing.
BODY = (
    "<system>Bạn là trợ lý hỗ trợ khách hàng của ACME.</system>"
    "<instructions>Trả lời câu hỏi sau: {{cau_hoi}}</instructions>"
)

DECLARED = {
    "audience": "public",
    "untrusted_input": "user_text",
    "acts": "answers_only",
    "sensitivity": "business",
}


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    yield from readiness_api(app_sessionmaker)


def _cookie() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _seed(migrate_engine: AsyncEngine) -> None:
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine, **DECLARED)
    await seed_revision(
        migrate_engine, version_id=DRAFT_VERSION, body=BODY, status="Draft", **DECLARED
    )
    await seed_revision(
        migrate_engine,
        version_id=SUBMITTED_VERSION,
        revision_number=2,
        body=BODY,
        status="In review",
        **DECLARED,
    )


async def _card(api: Any, version_id: str) -> dict[str, Any]:
    response = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{version_id}/readiness",
        headers=_cookie(),
    )
    assert response.status_code == 200, response.body
    return response.json()


async def _reports(migrate_engine: AsyncEngine, version_id: str) -> int:
    async with migrate_engine.begin() as connection:
        return (
            await connection.execute(COUNT_REPORTS, {"version_id": version_id})
        ).scalar_one()


async def test_a_draft_is_recomputed_and_never_frozen(api, migrate_engine) -> None:
    """The author's side. A panel that stopped following the body would be a bug."""
    await _seed(migrate_engine)

    card = await _card(api, DRAFT_VERSION)
    assert card["frozen"] is False
    assert card["findings"], "a draft with a spotlighting problem must still report it"
    assert await _reports(migrate_engine, DRAFT_VERSION) == 0


async def test_the_first_read_past_draft_writes_the_report_once(api, migrate_engine) -> None:
    """SR-1's resolution. No release-control edge, and no second row.

    Read three times, because *idempotent* is the claim and one read cannot make
    it. The uniqueness lives in the database (``uq_readiness_report_version``),
    so this would also hold with two processes doing it at once — which an
    application-level existence check would not.
    """
    await _seed(migrate_engine)
    assert await _reports(migrate_engine, SUBMITTED_VERSION) == 0

    first = await _card(api, SUBMITTED_VERSION)
    assert first["frozen"] is True
    assert await _reports(migrate_engine, SUBMITTED_VERSION) == 1

    for _ in range(2):
        await _card(api, SUBMITTED_VERSION)
    assert await _reports(migrate_engine, SUBMITTED_VERSION) == 1


async def test_a_catalogue_bump_does_not_change_what_the_reviewer_sees(
    api, migrate_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-7 itself. The report explains itself against the catalogue that made it.

    Bumping ``CATALOGUE_VERSION`` after the freeze is the cheapest available
    stand-in for a week of rule edits, and it is the sharp one: the card must
    keep reporting the OLD version, because a report labelled with a catalogue
    that did not produce it is worse than one with no label at all.
    """
    await _seed(migrate_engine)

    before = await _card(api, SUBMITTED_VERSION)
    assert before["catalogue_version"] == readiness_domain.CATALOGUE_VERSION

    monkeypatch.setattr(readiness_domain, "CATALOGUE_VERSION", "99")

    after = await _card(api, SUBMITTED_VERSION)
    assert after["catalogue_version"] == before["catalogue_version"] != "99"
    assert after["findings"] == before["findings"]
    assert after["profile"] == before["profile"]


async def test_the_frozen_card_is_rendered_from_the_row_and_not_recomputed(
    api, migrate_engine
) -> None:
    """The body changes underneath and the card does not. Rules were not re-run.

    ``registry.revision`` is append-only by privilege — ``prope_app`` holds
    ``INSERT`` and ``UPDATE (status)`` and nothing else — so this rewrite goes in
    on the migration role, which is exactly why it is a fair test: it produces a
    state the application cannot reach, and the only implementation that survives
    it is one that never looks at the body again.
    """
    await _seed(migrate_engine)
    before = await _card(api, SUBMITTED_VERSION)
    assert before["findings"]

    async with migrate_engine.begin() as connection:
        await connection.execute(
            text("UPDATE registry.revision SET body = :body WHERE version_id = :version_id"),
            {
                "body": "<system>Trợ lý.</system><instructions>Trả lời.</instructions>",
                "version_id": SUBMITTED_VERSION,
            },
        )

    after = await _card(api, SUBMITTED_VERSION)
    assert after["findings"] == before["findings"]
    assert after["frozen"] is True


async def test_the_stored_row_carries_the_profile_the_decision_was_made_against(
    api, migrate_engine
) -> None:
    """The reviewer's binding record, since the revision's stamp cannot be redone.

    Migration 0008 grants ``UPDATE (status)`` on ``registry.revision`` and
    nothing more, so the axes stamped at create are the axes forever — there is
    no re-stamp at submit and the lock records that correction. This row is what
    stands in for one: it says which declaration the findings were judged under,
    at the moment the reviewer first looked.
    """
    await _seed(migrate_engine)
    await _card(api, SUBMITTED_VERSION)

    async with migrate_engine.begin() as connection:
        row = (
            (await connection.execute(READ_REPORT, {"version_id": SUBMITTED_VERSION}))
            .mappings()
            .one()
        )

    assert row["profile_snapshot"] == DECLARED
    assert row["catalogue_version"] == readiness_domain.CATALOGUE_VERSION
    assert row["rendered_findings"], "an empty report would make AC-7 vacuous"
    for entry in row["rendered_findings"]:
        assert entry["rule_id"] in {str(rule) for rule in readiness_domain.RuleId}
        assert entry["severity"] in {member.value for member in readiness_domain.Severity}
