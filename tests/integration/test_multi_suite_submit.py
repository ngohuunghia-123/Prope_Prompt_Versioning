"""AC-8 — three suites, three runs, one summary, and the acknowledgement rule.

``get_review_summary()`` is INT-017, the one internal read release-control pulls
in wave 5, so the shape asserted here is the shape another module will depend on.
Three claims:

* a submit against a prompt with three suites creates **three** runs, one each;
* the summary carries three rows **plus a rollup**, not three rows a caller has
  to add up — the rollup is where the withholding rule composes, and a caller
  that summed the rows itself would publish a total the module refused to;
* ``requires_acknowledgement`` is true when **any one** suite has a failing case.

A-058 makes that last flag computed once, here, and enforced without
recomputation in release-control. So the two carve-outs are applied at this
point and nowhere else: an ``error`` is not a ``fail`` (A-057), and an empty
suite is not a pass (A-059).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.evaluation.executor import run_claimed_batch
from prope.evaluation.summary import get_review_summary
from tests.evaluation import (
    PROMPT_ID,
    VERSION_ID,
    WORKSPACE_A,
    StubDispatcher,
    allow_ceiling,
    completion,
    evaluation_api,
    no_pricing,
    seed_bound_revision,
    seed_case,
    seed_owner,
    seed_suite,
    totaller_by_run,
)
from tests.integration._asgi import call
from tests.prompt_registry import seed_prompt

SESSION_ID = "ses_evaluation_multi_suite01"

SUITES = {
    "safety": "evs_01J00000000000000SAFETY1",
    "accuracy": "evs_01J0000000000000ACCURA1",
    "format": "evs_01J00000000000000FORMAT1",
}


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with evaluation_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _three_suites(migrate_engine) -> None:  # noqa: ANN001
    """Three suites of one case each, and NO released revision.

    Nothing is released on purpose: a released revision would make the submit
    create three baseline runs beside the three candidates, and AC-8's count is
    about the candidates.
    """
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine)

    for index, (name, suite_id) in enumerate(SUITES.items(), start=1):
        await seed_suite(migrate_engine, suite_id, name=name, case_count=1)
        await seed_case(
            migrate_engine,
            f"evc_01J0000000000000000CS{index:03d}",
            suite_id=suite_id,
            ordinal=1,
            name=f"the {name} case",
            prompt=f"{name}-case",
            assertions=[{"type": "substring", "value": "in policy"}],
        )


async def _submit_and_run(api, app_sessionmaker, *, failing: str | None) -> list[dict]:  # noqa: ANN001
    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": VERSION_ID},
        headers=_owner(),
    )
    assert accepted.status_code == 202, accepted.body

    by_prompt = (
        {} if failing is None else {f"{failing}-case": completion("out of bounds")}
    )
    await run_claimed_batch(
        app_sessionmaker,
        max_concurrent_runs=3,
        dispatcher=StubDispatcher(default=completion("in policy"), by_prompt=by_prompt),
        ceiling_check=allow_ceiling,
        pricer=no_pricing,
        totaller=totaller_by_run({}),
    )
    return accepted.json()["runs"]


async def test_a_submit_creates_one_run_per_suite(api, migrate_engine) -> None:
    """AC-8's first claim, asserted on the suite ids rather than on a count of 3."""
    await _three_suites(migrate_engine)

    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": VERSION_ID},
        headers=_owner(),
    )

    handles = accepted.json()["runs"]
    assert {handle["suite_id"] for handle in handles} == set(SUITES.values())
    assert {handle["role"] for handle in handles} == {"candidate"}
    assert len({handle["run_id"] for handle in handles}) == 3


async def test_the_review_summary_carries_three_rows_and_a_rollup(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-8's second claim, read through INT-017 rather than through a route.

    ``get_review_summary`` is an in-process call and release-control will make it
    the same way, so the test makes it the same way too — a route would assert
    the serializer instead of the contract.
    """
    await _three_suites(migrate_engine)
    await _submit_and_run(api, app_sessionmaker, failing=None)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        summary = await get_review_summary(db, PROMPT_ID, VERSION_ID)

    assert summary.prompt_id == PROMPT_ID
    assert summary.version_id == VERSION_ID
    assert len(summary.suites) == 3
    assert {row.suite_name for row in summary.suites} == set(SUITES)

    for row in summary.suites:
        assert row.status.value == "completed"
        assert row.case_count == 1
        assert row.baseline_run_id is None
        assert row.baseline_reused is False
        assert row.cost_delta is None
        assert row.withheld_reason.value == "no_baseline"

    assert summary.total_cost_delta is None
    assert summary.withheld_reason.value == "no_baseline"
    assert summary.cost_warning is False


async def test_requires_acknowledgement_is_true_when_any_one_suite_fails(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-8's third claim. ANY, not all — and computed once, here (A-058).

    The ``format`` suite is the one that fails; the other two pass. A rule that
    read "every suite failed" would answer false and let a broken revision reach
    the approve button without a recorded acknowledgement.
    """
    await _three_suites(migrate_engine)
    await _submit_and_run(api, app_sessionmaker, failing="format")

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        summary = await get_review_summary(db, PROMPT_ID, VERSION_ID)

    by_name = {row.suite_name: row for row in summary.suites}
    assert by_name["format"].fail_count == 1
    assert by_name["safety"].fail_count == 0
    assert by_name["accuracy"].fail_count == 0

    assert summary.requires_acknowledgement is True


async def test_requires_acknowledgement_is_false_when_every_suite_passes(
    api, app_sessionmaker, migrate_engine
) -> None:
    """The control for the rule above. Without it, ``return True`` passes."""
    await _three_suites(migrate_engine)
    await _submit_and_run(api, app_sessionmaker, failing=None)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        summary = await get_review_summary(db, PROMPT_ID, VERSION_ID)

    assert all(row.fail_count == 0 for row in summary.suites)
    assert summary.requires_acknowledgement is False
