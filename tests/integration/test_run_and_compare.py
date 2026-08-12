"""AC-1 — the whole journey, from ``POST /eval-runs`` to a comparison with money in it.

A 20-case suite, a released revision, a candidate revision, and one walk through
every seam this module owns: the API accepts the submit, the claim loop picks the
runs up, the executor dispatches each case, the assertions decide pass or fail,
call-ledger prices the usage, and the comparison endpoint renders per-case
outcomes for BOTH revisions plus the token and money delta between them.

**The baseline run is created by the submit, not by the test.** That is the half
of AC-1 most likely to rot: a candidate submitted against a prompt whose released
revision has never been measured has nothing to compare to, so the API creates
the baseline run itself and the claim loop treats it like any other. A test that
seeded the baseline by hand would still pass with that behaviour deleted.

The p95-under-120s half of AC-1 is asserted in ``tests/load/`` against injected
latency, because a stubbed dispatcher answers in microseconds and a timing
assertion here would measure the test rig.
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
)
from tests.integration._asgi import call
from tests.prompt_registry import approve, release, seed_prompt

SESSION_ID = "ses_evaluation_run_compare01"

RELEASED_VERSION = "rev_01J000000000000000RELEAS"

CANDIDATE_VERSION = "rev_01J000000000000000CANDID"

SUITE = "evs_01J0000000000000000SAFE1"

CASE_COUNT = 20

#: Case 7 is the one that fails, in both revisions and for the same reason: the
#: required phrase is absent. A case that failed only in the candidate would make
#: the ``changed`` column true and hide the case where it must be false.
FAILING_ORDINAL = 7


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
            assertions=[{"type": "required_phrase", "value": "in policy"}],
        )


def _dispatcher() -> StubDispatcher:
    """Every case answers "in policy" except the one that does not."""
    return StubDispatcher(
        default=completion("this request is in policy"),
        by_prompt={f"case-{FAILING_ORDINAL:03d}": completion("this request is out of bounds")},
    )


async def test_a_submit_runs_both_revisions_and_the_comparison_carries_both(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-1 end to end: two runs, forty case results, one comparison block."""
    await _a_released_prompt_with_a_twenty_case_suite(migrate_engine)

    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": CANDIDATE_VERSION},
        headers=_owner(),
    )
    assert accepted.status_code == 202, accepted.body

    handles = accepted.json()["runs"]
    by_role = {handle["role"]: handle["run_id"] for handle in handles}
    assert set(by_role) == {"candidate", "baseline"}

    dispatcher = _dispatcher()
    claimed = await run_claimed_batch(
        app_sessionmaker,
        dispatcher=dispatcher,
        ceiling_check=allow_ceiling,
        pricer=no_pricing,
        totaller=totaller_by_run(
            {
                by_role["candidate"]: totals(
                    input_tokens=200, output_tokens=100, cost=Decimal("1.25"), currency="USD"
                ),
                by_role["baseline"]: totals(
                    input_tokens=200, output_tokens=100, cost=Decimal("1.00"), currency="USD"
                ),
            }
        ),
    )

    assert claimed == 2
    assert len(dispatcher.calls) == 2 * CASE_COUNT

    for run_id in by_role.values():
        run = await call(api, "GET", f"/api/v1/eval-runs/{run_id}", headers=_owner())
        assert run.status_code == 200, run.body
        assert run.json()["status"] == "completed"
        assert run.json()["pass_count"] == CASE_COUNT - 1
        assert run.json()["fail_count"] == 1
        assert run.json()["error_count"] == 0

    comparison = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/comparison",
        params={"candidate": CANDIDATE_VERSION},
        headers=_owner(),
    )
    assert comparison.status_code == 200, comparison.body

    blocks = comparison.json()
    assert len(blocks) == 1
    block = blocks[0]

    assert block["candidate_run_id"] == by_role["candidate"]
    assert block["baseline_run_id"] == by_role["baseline"]
    assert block["baseline_ran_at"] is not None

    outcomes = {case["case_id"]: case for case in block["cases"]}
    assert len(outcomes) == CASE_COUNT

    failing = outcomes[_case_id(FAILING_ORDINAL)]
    assert failing["candidate_outcome"] == "fail"
    assert failing["baseline_outcome"] == "fail"
    assert failing["changed"] is False

    passing = outcomes[_case_id(1)]
    assert passing["candidate_outcome"] == "pass"
    assert passing["baseline_outcome"] == "pass"


async def test_the_comparison_carries_the_token_and_money_delta(
    api, app_sessionmaker, migrate_engine
) -> None:
    """The second half of AC-1's "and the token and money delta between them".

    The two runs are priced differently on purpose. A candidate and a baseline
    given the same figure would produce a delta of zero, which is the one value
    indistinguishable from a delta that was never computed at all.
    """
    await _a_released_prompt_with_a_twenty_case_suite(migrate_engine)

    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": CANDIDATE_VERSION},
        headers=_owner(),
    )
    by_role = {handle["role"]: handle["run_id"] for handle in accepted.json()["runs"]}

    await run_claimed_batch(
        app_sessionmaker,
        dispatcher=_dispatcher(),
        ceiling_check=allow_ceiling,
        pricer=no_pricing,
        totaller=totaller_by_run(
            {
                by_role["candidate"]: totals(cost=Decimal("1.10"), currency="USD"),
                by_role["baseline"]: totals(cost=Decimal("1.00"), currency="USD"),
            }
        ),
    )

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
    assert Decimal(str(block["cost_delta"]["cost"])) == Decimal("0.10")
    assert block["cost_delta"]["currency"] == "USD"
    assert Decimal(str(block["cost_delta"]["ratio"])) == Decimal("1.1")
    assert block["cost_delta"]["input_tokens"] == 0
    assert block["cost_delta"]["output_tokens"] == 0
    assert block["cost_warning"] is False


async def test_every_case_result_is_readable_by_its_run(
    api, app_sessionmaker, migrate_engine
) -> None:
    """The per-case rows behind the comparison, read through their own route.

    ``GET /eval-runs/{id}/cases`` is what the review screen paginates; the
    comparison endpoint is a projection over the same rows. Asserting both keeps
    a projection that quietly stopped reading the table from looking healthy.
    """
    await _a_released_prompt_with_a_twenty_case_suite(migrate_engine)

    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": CANDIDATE_VERSION},
        headers=_owner(),
    )
    candidate = next(
        handle["run_id"] for handle in accepted.json()["runs"] if handle["role"] == "candidate"
    )

    await run_claimed_batch(
        app_sessionmaker,
        dispatcher=_dispatcher(),
        ceiling_check=allow_ceiling,
        pricer=no_pricing,
        totaller=totaller_by_run({}),
    )

    cases = await call(api, "GET", f"/api/v1/eval-runs/{candidate}/cases", headers=_owner())
    assert cases.status_code == 200, cases.body

    rows = cases.json()
    assert len(rows) == CASE_COUNT
    assert {row["outcome"] for row in rows} == {"pass", "fail"}
    assert all(row["attempt_count"] == 1 for row in rows)
    assert all(row["error_code"] is None for row in rows)

    failed = next(row for row in rows if row["outcome"] == "fail")
    assert failed["assertion_results"][0]["type"] == "required_phrase"
    assert failed["assertion_results"][0]["passed"] is False
