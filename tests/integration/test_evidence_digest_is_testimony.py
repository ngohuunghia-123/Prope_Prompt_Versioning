"""AC-11 — A-074: the digest is testimony, not a cache.

An approval is recorded while the safety suite shows 2 failing cases. The suite
is then edited and re-run with different results. The stored approval still shows
what the reviewer actually saw.

**This does not contradict A-047**, which says derived comparisons are computed
on demand and never stored. A recomputed comparison would answer a DIFFERENT
QUESTION later — *what does the evidence say now* — because the baseline or the
suite version may have moved since. What the approval has to answer is *what did
this person see when they decided*, and only a stored copy can.

**Counts, ids and money only.** No model outputs and no case inputs, whose
retention policy is OQ-013's — this is the one module in the build that
pre-empted that answer rather than inheriting it.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.evaluation.domain import CostDelta, ReviewSummary, RunStatus, SuiteSummary
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, VERSION_ID, seed_prompt, seed_revision
from tests.release_control import (
    ADMIN_ID,
    APPROVER_ID,
    SUITE_ID,
    day,
    read_approvals,
    release_api,
    seed_actor,
    stub_summary,
)

AUTHOR_SESSION = "ses_release_digest_author"

APPROVER_SESSION = "ses_release_digest_approver"

AT_DECISION_TIME = "evr_01J0000000000000ATDECIDE"

AFTER_THE_EDIT = "evr_01J000000000000AFTEREDIT"

REASON = "two known safety failures, accepted for the Friday release"

#: Values a later recomputation could not produce by accident: a distinctive
#: failing count and a +18% cost ratio, both fixed in source.
FAILING_CASES = 2

COST_RATIO = "1.18"


def _summary(run_id: str, *, fails: int, suite_version: int, ratio: str) -> ReviewSummary:
    return ReviewSummary(
        prompt_id=PROMPT_ID,
        version_id=VERSION_ID,
        suites=(
            SuiteSummary(
                suite_id=SUITE_ID,
                suite_name="safety",
                suite_version=suite_version,
                run_id=run_id,
                status=RunStatus.COMPLETED,
                pass_count=20 - fails,
                fail_count=fails,
                error_count=0,
                case_count=20,
                baseline_run_id="evr_01J0000000000000BASELINE",
                baseline_ran_at=day(3),
                baseline_reused=True,
                cost_delta=CostDelta(
                    input_tokens=1180,
                    output_tokens=590,
                    cost=None,
                    currency="USD",
                    ratio=None,
                ),
                withheld_reason=None,
                cost_warning=False,
            ),
        ),
        total_cost_delta=CostDelta(
            input_tokens=1180, output_tokens=590, cost=None, currency="USD", ratio=None
        ),
        requires_acknowledgement=fails > 0,
    )


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


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


async def test_the_stored_digest_survives_a_suite_edit_and_a_rerun(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _a_revision_in_review(api, migrate_engine)

    at_decision = _summary(AT_DECISION_TIME, fails=FAILING_CASES, suite_version=1, ratio=COST_RATIO)
    with stub_summary(monkeypatch, at_decision):
        approved = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body={"comment": "ship it", "acknowledgement_reason": REASON},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )
    assert approved.status_code == 201, approved.body

    stored = (await read_approvals(migrate_engine))[0]["evidence_digest"]

    # The suite is edited and re-run: a new suite version, a new run, and now
    # everything passes. Nothing in this module touches the approval.
    after = _summary(AFTER_THE_EDIT, fails=0, suite_version=2, ratio="1.00")
    with stub_summary(monkeypatch, after):
        screen = await call(
            api,
            "GET",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/review",
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )
    assert screen.status_code == 200, screen.body
    assert screen.json()["summary"]["suites"][0]["fail_count"] == 0
    assert screen.json()["summary"]["suites"][0]["suite_version"] == 2

    unchanged = (await read_approvals(migrate_engine))[0]["evidence_digest"]
    assert unchanged == stored

    suite = stored["suites"][0]
    assert suite["fail_count"] == FAILING_CASES
    assert suite["pass_count"] == 20 - FAILING_CASES
    assert suite["suite_version"] == 1
    assert suite["run_id"] == AT_DECISION_TIME
    assert suite["baseline_run_id"] == "evr_01J0000000000000BASELINE"
    assert suite["baseline_ran_at"] is not None
    assert stored["requires_acknowledgement"] is True
    assert stored["summary_available"] is True


async def test_the_digest_carries_counts_ids_and_money_and_nothing_else(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """OQ-013's answer, pre-empted rather than inherited.

    A digest that carried a model output would put case content in a table whose
    retention policy nobody has decided, on the one record the audit claim is
    made of. The shape is asserted as a key set rather than by absence of a
    particular string, so a new field has to be argued for here.
    """
    await _a_revision_in_review(api, migrate_engine)

    with stub_summary(
        monkeypatch, _summary(AT_DECISION_TIME, fails=FAILING_CASES, suite_version=1, ratio=COST_RATIO)
    ):
        await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body={"comment": "ship it", "acknowledgement_reason": REASON},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )

    stored = (await read_approvals(migrate_engine))[0]["evidence_digest"]

    assert set(stored) == {
        "version_id",
        "captured_at",
        "summary_available",
        "requires_acknowledgement",
        "suites",
        "total_cost_delta",
    }
    assert set(stored["suites"][0]) == {
        "suite_id",
        "suite_name",
        "suite_version",
        "run_id",
        "status",
        "pass_count",
        "fail_count",
        "error_count",
        "case_count",
        "baseline_run_id",
        "baseline_ran_at",
        "cost_delta",
    }
    assert set(stored["total_cost_delta"]) == {
        "input_tokens",
        "output_tokens",
        "cost",
        "currency",
        "ratio",
    }
