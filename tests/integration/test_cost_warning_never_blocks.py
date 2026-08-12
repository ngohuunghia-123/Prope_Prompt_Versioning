"""AC-5 — a 25% more expensive candidate warns, and warns is all it does.

OQ-009 is resolved this way: **warn at ≥ +20%, never block**, with the threshold
and the blocking flag left as configuration. The reasoning is that a prompt that
costs more may be the right prompt, and a module that refused it would be making
a product decision on the reviewer's behalf using a number it cannot interpret.

So this file asserts a warning is raised AND that nothing downstream of it
changes: the run still completes, the comparison still carries its delta, and
``requires_acknowledgement`` — the one flag that does gate the decision — stays
false, because it is about failing cases and not about money.

``COST_WARNING_BLOCKS`` is asserted as a constant beside the behaviour rather
than only as a name, because a later change that flips it would otherwise leave
this file green while inverting the resolution of OQ-009.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.evaluation.domain import COST_WARNING_BLOCKS, COST_WARNING_THRESHOLD
from prope.evaluation.executor import run_claimed_batch
from prope.evaluation.summary import get_review_summary
from tests.evaluation import (
    PROMPT_ID,
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
    totals,
)
from tests.integration._asgi import call
from tests.prompt_registry import approve, release, seed_prompt

SESSION_ID = "ses_evaluation_cost_warning1"

RELEASED_VERSION = "rev_01J000000000000000RELEAS"

CANDIDATE_VERSION = "rev_01J000000000000000CANDID"

SUITE = "evs_01J0000000000000000SAFE1"

BASELINE_COST = Decimal("1.00")

#: +25%, which is above the +20% threshold and below anything that could be
#: mistaken for a unit error. The point of the exact figure is that it is the one
#: AC-5 names.
CANDIDATE_COST = Decimal("1.25")


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with evaluation_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _a_released_prompt_with_one_suite(migrate_engine) -> None:  # noqa: ANN001
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine, RELEASED_VERSION, revision_number=1)
    await seed_bound_revision(migrate_engine, CANDIDATE_VERSION, revision_number=2)
    await approve(migrate_engine, RELEASED_VERSION)
    await release(migrate_engine, PROMPT_ID, RELEASED_VERSION)

    await seed_suite(migrate_engine, SUITE, name="safety", case_count=2)
    for ordinal in (1, 2):
        await seed_case(
            migrate_engine,
            f"evc_01J0000000000000000CS{ordinal:03d}",
            suite_id=SUITE,
            ordinal=ordinal,
            prompt=f"case-{ordinal:03d}",
            assertions=[{"type": "substring", "value": "policy"}],
        )


async def _submit_and_run(api, app_sessionmaker, *, candidate_cost: Decimal) -> dict[str, str]:  # noqa: ANN001
    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": CANDIDATE_VERSION},
        headers=_owner(),
    )
    assert accepted.status_code == 202, accepted.body
    by_role = {handle["role"]: handle["run_id"] for handle in accepted.json()["runs"]}

    await run_claimed_batch(
        app_sessionmaker,
        dispatcher=StubDispatcher(default=completion("this request is in policy")),
        ceiling_check=allow_ceiling,
        pricer=no_pricing,
        totaller=totaller_by_run(
            {
                by_role["candidate"]: totals(cost=candidate_cost, currency="USD"),
                by_role["baseline"]: totals(cost=BASELINE_COST, currency="USD"),
            }
        ),
    )
    return by_role


async def test_a_twenty_five_percent_increase_raises_the_warning(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-5's first half, with the delta and the ratio both readable beside it."""
    await _a_released_prompt_with_one_suite(migrate_engine)
    await _submit_and_run(api, app_sessionmaker, candidate_cost=CANDIDATE_COST)

    comparison = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/comparison",
        params={"candidate": CANDIDATE_VERSION},
        headers=_owner(),
    )
    block = comparison.json()[0]

    assert block["cost_warning"] is True
    assert block["withheld_reason"] is None
    assert Decimal(str(block["cost_delta"]["cost"])) == Decimal("0.25")
    assert Decimal(str(block["cost_delta"]["ratio"])) == Decimal("1.25")


async def test_the_warning_changes_nothing_else_about_the_run(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-5's second half. The run completes; nothing is refused, nothing gated.

    ``requires_acknowledgement`` is the flag that does gate the decision in
    release-control, and it stays false here — it is A-058's any-suite-fails
    rule and has nothing to do with money. A warning that set it would turn
    "this costs more" into "somebody must sign for this", which is the blocking
    OQ-009 refused.
    """
    await _a_released_prompt_with_one_suite(migrate_engine)
    by_role = await _submit_and_run(
        api, app_sessionmaker, candidate_cost=CANDIDATE_COST
    )

    run = await call(api, "GET", f"/api/v1/eval-runs/{by_role['candidate']}", headers=_owner())
    assert run.json()["status"] == "completed"
    assert run.json()["refused_reason"] is None
    assert run.json()["fail_count"] == 0

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        summary = await get_review_summary(db, PROMPT_ID, CANDIDATE_VERSION)

    assert summary.cost_warning is True
    assert summary.requires_acknowledgement is False
    assert summary.total_cost_delta is not None
    assert summary.withheld_reason is None


async def test_a_cheaper_candidate_raises_no_warning(
    api, app_sessionmaker, migrate_engine
) -> None:
    """The control, and the threshold read from the constant rather than retyped."""
    await _a_released_prompt_with_one_suite(migrate_engine)
    await _submit_and_run(api, app_sessionmaker, candidate_cost=Decimal("0.90"))

    comparison = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/comparison",
        params={"candidate": CANDIDATE_VERSION},
        headers=_owner(),
    )
    block = comparison.json()[0]

    assert block["cost_warning"] is False
    assert Decimal(str(block["cost_delta"]["cost"])) == Decimal("-0.10")

    assert COST_WARNING_THRESHOLD == Decimal("0.20")
    assert COST_WARNING_BLOCKS is False
