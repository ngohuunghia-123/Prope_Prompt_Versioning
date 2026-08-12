"""AC-4 — saving a suite creates a version; it never edits one.

Four claims, and each is a different way the same mistake would show up:

* saving version 4 of ``safety`` produces version **5**, as a new row;
* a run already in flight still reports against version 4, because the run
  carries a ``suite_id`` and a ``suite_id`` names one VERSION;
* the sibling suite ``accuracy`` is untouched — versioning is per suite name, not
  per prompt, so an edit to one must not renumber the other;
* a comparison whose two runs were measured at different suite versions is
  **refused**, not computed.

The last is the reason the first three matter. If a suite could be edited in
place, an in-flight run would silently change what it was measuring; and if two
suite versions could be compared, the delta would report a difference the
revisions did not cause.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.evaluation import comparison, repository
from prope.evaluation.domain import SuiteVersionMismatch
from tests.evaluation import (
    PROMPT_ID,
    VERSION_ID,
    WORKSPACE_A,
    evaluation_api,
    seed_bound_revision,
    seed_case,
    seed_owner,
    seed_run,
    seed_suite,
)
from tests.integration._asgi import call
from tests.prompt_registry import seed_prompt

SESSION_ID = "ses_evaluation_suite_pinning1"

SAFETY_V4 = "evs_01J00000000000000SAFE004"

ACCURACY_V1 = "evs_01J00000000000000ACCU001"

IN_FLIGHT_RUN = "evr_01J00000000000000INFLIGH"

BASELINE_RUN = "evr_01J00000000000000BASE001"

OTHER_VERSION = "rev_01J0000000000000000OTHER"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with evaluation_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


def _edit() -> dict:
    return {
        "output_modality": "text",
        "cases": [
            {
                "name": "refuses an out-of-policy refund",
                "input_messages": [{"role": "user", "content": "case-001"}],
                "assertions": [{"type": "substring", "value": "policy"}],
            },
            {
                "name": "a case the fourth version never had",
                "input_messages": [{"role": "user", "content": "case-002"}],
                "assertions": [],
            },
        ],
    }


async def _two_suites_and_a_run_in_flight(migrate_engine) -> None:  # noqa: ANN001
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine)
    await seed_bound_revision(migrate_engine, OTHER_VERSION, revision_number=2)

    await seed_suite(migrate_engine, SAFETY_V4, name="safety", suite_version=4, case_count=1)
    await seed_case(
        migrate_engine, "evc_01J00000000000000SAFE001", suite_id=SAFETY_V4, ordinal=1
    )

    await seed_suite(migrate_engine, ACCURACY_V1, name="accuracy", suite_version=1, case_count=1)
    await seed_case(
        migrate_engine,
        "evc_01J00000000000000ACCU001",
        suite_id=ACCURACY_V1,
        ordinal=1,
        name="answers the question asked",
    )

    await seed_run(migrate_engine, IN_FLIGHT_RUN, suite_id=SAFETY_V4, status="running")


async def test_saving_creates_version_five_and_leaves_version_four_alone(
    api, migrate_engine
) -> None:
    """AC-4's first claim. A ``PUT`` that answers ``201`` is the shape of it."""
    await _two_suites_and_a_run_in_flight(migrate_engine)

    saved = await call(
        api, "PUT", f"/api/v1/eval-suites/{SAFETY_V4}", json_body=_edit(), headers=_owner()
    )
    assert saved.status_code == 201, saved.body
    assert saved.json()["suite_version"] == 5
    assert saved.json()["suite_id"] != SAFETY_V4
    assert saved.json()["name"] == "safety"

    original = await call(api, "GET", f"/api/v1/eval-suites/{SAFETY_V4}", headers=_owner())
    assert original.status_code == 200
    assert original.json()["suite_version"] == 4
    assert original.json()["case_count"] == 1
    assert [case["name"] for case in original.json()["cases"]] == [
        "refuses an out-of-policy refund"
    ]

    versions = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/eval-suites/safety/versions",
        headers=_owner(),
    )
    assert [row["suite_version"] for row in versions.json()] == [5, 4]


async def test_the_in_flight_run_still_reports_against_version_four(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-4's second claim, and the reason ``eval_run`` carries ``suite_id``.

    Not the suite's NAME, and not a ``(prompt_id, name)`` pair resolved at read
    time — either of those would make a run's yardstick change under it while it
    is still measuring.
    """
    await _two_suites_and_a_run_in_flight(migrate_engine)

    await call(
        api, "PUT", f"/api/v1/eval-suites/{SAFETY_V4}", json_body=_edit(), headers=_owner()
    )

    run = await call(api, "GET", f"/api/v1/eval-runs/{IN_FLIGHT_RUN}", headers=_owner())
    assert run.json()["suite_id"] == SAFETY_V4
    assert run.json()["status"] == "running"

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        suite = await repository.load_suite(db, run.json()["suite_id"])

    assert suite is not None
    assert suite.suite_version == 4


async def test_the_sibling_suite_is_untouched(api, migrate_engine) -> None:
    """AC-4's third claim. Versioning is per NAME, and the counter is per name.

    A shared counter would renumber ``accuracy`` every time ``safety`` was saved,
    and the reviewer would be told the accuracy suite changed when nobody
    touched it.
    """
    await _two_suites_and_a_run_in_flight(migrate_engine)

    await call(
        api, "PUT", f"/api/v1/eval-suites/{SAFETY_V4}", json_body=_edit(), headers=_owner()
    )

    accuracy = await call(api, "GET", f"/api/v1/eval-suites/{ACCURACY_V1}", headers=_owner())
    assert accuracy.json()["suite_version"] == 1
    assert accuracy.json()["case_count"] == 1
    assert [case["name"] for case in accuracy.json()["cases"]] == ["answers the question asked"]

    current = await call(
        api, "GET", f"/api/v1/prompts/{PROMPT_ID}/eval-suites", headers=_owner()
    )
    by_name = {row["name"]: row["suite_version"] for row in current.json()}
    assert by_name == {"safety": 5, "accuracy": 1}


async def test_a_comparison_across_two_suite_versions_is_refused(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-4's fourth claim, and the only one that raises rather than returning.

    ``cost_delta`` refuses the pair outright instead of answering ``None`` with a
    withheld reason, because a mismatched pairing is a caller error and not a
    property of the data: answering it softly would let a caller keep asking.
    """
    await _two_suites_and_a_run_in_flight(migrate_engine)

    saved = await call(
        api, "PUT", f"/api/v1/eval-suites/{SAFETY_V4}", json_body=_edit(), headers=_owner()
    )
    suite_v5 = saved.json()["suite_id"]

    await seed_run(
        migrate_engine,
        BASELINE_RUN,
        suite_id=suite_v5,
        version_id=OTHER_VERSION,
        role="baseline",
        status="completed",
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        candidate = await repository.load_run(db, IN_FLIGHT_RUN)
        baseline = await repository.load_run(db, BASELINE_RUN)

    assert candidate is not None
    assert baseline is not None
    assert candidate.version_id == VERSION_ID

    with pytest.raises(SuiteVersionMismatch):
        comparison.cost_delta(comparison.measure(candidate), comparison.measure(baseline))
