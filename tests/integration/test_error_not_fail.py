"""AC-2 — a dispatch that never happened is not a prompt that got it wrong.

A-057's whole argument in one file. Three of twenty cases end in a transport
error; the other seventeen answer normally. Two things must follow, and the
second is the one that is easy to lose:

* those three record ``outcome=error``, never ``fail`` — a ``fail`` would tell
  the reviewer the prompt is worse than the baseline when what actually happened
  is that the provider was down;
* the cost delta is **withheld with a stated reason**, because seventeen priced
  cases against a baseline's twenty is a smaller number that looks like a cheaper
  revision, which is the most expensive possible way to be wrong here.

The reason is a machine value from a closed vocabulary (``WithheldReason``), not
a sentence, so the SPA can key a catalogue entry on it under ADR-0053.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.evaluation.executor import run_claimed_batch
from tests.evaluation import (
    PROMPT_ID,
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
    transport_error,
)
from tests.integration._asgi import call
from tests.prompt_registry import approve, release, seed_prompt

SESSION_ID = "ses_evaluation_error_notfail"

RELEASED_VERSION = "rev_01J000000000000000RELEAS"

CANDIDATE_VERSION = "rev_01J000000000000000CANDID"

SUITE = "evs_01J0000000000000000SAFE1"

CASE_COUNT = 20

#: Not case 1. The first case is dispatched alone as the modality probe, so
#: failing it would exercise the probe's branch rather than the twenty-case run
#: AC-2 describes.
BROKEN_ORDINALS = (5, 6, 7)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with evaluation_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


def _case_id(ordinal: int) -> str:
    return f"evc_01J0000000000000000CS{ordinal:03d}"


async def _a_released_prompt_with_a_twenty_case_suite(migrate_engine) -> None:  # noqa: ANN001
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine, RELEASED_VERSION, revision_number=1)
    await seed_bound_revision(migrate_engine, CANDIDATE_VERSION, revision_number=2)
    await approve(migrate_engine, RELEASED_VERSION)
    await release(migrate_engine, PROMPT_ID, RELEASED_VERSION)

    await seed_suite(migrate_engine, SUITE, name="safety", case_count=CASE_COUNT)
    for ordinal in range(1, CASE_COUNT + 1):
        await seed_case(
            migrate_engine,
            _case_id(ordinal),
            suite_id=SUITE,
            ordinal=ordinal,
            name=f"case {ordinal}",
            prompt=f"case-{ordinal:03d}",
            assertions=[{"type": "substring", "value": "policy"}],
        )


async def _submit_and_run(api, app_sessionmaker, *, broken: bool) -> dict[str, str]:  # noqa: ANN001
    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": CANDIDATE_VERSION},
        headers=_owner(),
    )
    assert accepted.status_code == 202, accepted.body
    by_role = {handle["role"]: handle["run_id"] for handle in accepted.json()["runs"]}

    by_prompt = (
        {f"case-{ordinal:03d}": transport_error() for ordinal in BROKEN_ORDINALS}
        if broken
        else {}
    )

    await run_claimed_batch(
        app_sessionmaker,
        dispatcher=StubDispatcher(
            default=completion("this request is in policy"), by_prompt=by_prompt
        ),
        ceiling_check=allow_ceiling,
        pricer=no_pricing,
        totaller=totaller_by_run(
            {
                by_role["candidate"]: totals(cost=Decimal("1.00"), currency="USD"),
                by_role["baseline"]: totals(cost=Decimal("1.00"), currency="USD"),
            }
        ),
    )
    return by_role


async def test_three_broken_cases_are_errors_and_not_failures(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-2's first half, read through the route the review screen reads."""
    await _a_released_prompt_with_a_twenty_case_suite(migrate_engine)
    by_role = await _submit_and_run(api, app_sessionmaker, broken=True)

    run = await call(api, "GET", f"/api/v1/eval-runs/{by_role['candidate']}", headers=_owner())
    assert run.status_code == 200, run.body
    assert run.json()["error_count"] == len(BROKEN_ORDINALS)
    assert run.json()["fail_count"] == 0
    assert run.json()["pass_count"] == CASE_COUNT - len(BROKEN_ORDINALS)

    cases = await call(
        api, "GET", f"/api/v1/eval-runs/{by_role['candidate']}/cases", headers=_owner()
    )
    by_case = {row["case_id"]: row for row in cases.json()}

    for ordinal in BROKEN_ORDINALS:
        row = by_case[_case_id(ordinal)]
        assert row["outcome"] == "error"
        assert row["error_code"] == "upstream_unavailable"
        assert row["assertion_results"] == []

    assert {row["outcome"] for row in cases.json()} == {"pass", "error"}


async def test_the_comparison_withholds_the_cost_delta_and_says_why(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-2's second half. Withheld, and withheld for a NAMED reason.

    ``cost_delta`` being ``None`` on its own would be indistinguishable from a
    comparison that had no baseline, from one whose runs are still going, and
    from a pricing round-trip that quietly failed. The reason is what separates
    the four, and it is what the screen renders instead of a number.
    """
    await _a_released_prompt_with_a_twenty_case_suite(migrate_engine)
    await _submit_and_run(api, app_sessionmaker, broken=True)

    comparison = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/comparison",
        params={"candidate": CANDIDATE_VERSION},
        headers=_owner(),
    )
    block = comparison.json()[0]

    assert block["cost_delta"] is None
    assert block["withheld_reason"] == "has_errors"
    assert block["cost_warning"] is False


async def test_the_same_run_without_errors_publishes_the_delta(
    api, app_sessionmaker, migrate_engine
) -> None:
    """The control. Without it, a comparison that withholds EVERYTHING passes.

    Same suite, same revisions, same prices — only the provider behaves. The
    delta appears, which is what makes the withholding above a decision rather
    than the module's only behaviour.
    """
    await _a_released_prompt_with_a_twenty_case_suite(migrate_engine)
    await _submit_and_run(api, app_sessionmaker, broken=False)

    comparison = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/comparison",
        params={"candidate": CANDIDATE_VERSION},
        headers=_owner(),
    )
    block = comparison.json()[0]

    assert block["withheld_reason"] is None
    assert block["cost_delta"] is not None
    assert Decimal(str(block["cost_delta"]["cost"])) == Decimal(0)
