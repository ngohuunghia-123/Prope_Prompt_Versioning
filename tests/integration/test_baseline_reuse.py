"""AC-3 — a baseline is pinned by ``(released_version_id, suite_id)``, not by time.

ADR-0004's rule, asserted from both sides. A completed run already exists for the
released revision at suite version 4; a second candidate is submitted while that
revision is still released and the suite is still at version 4. Nothing new is
dispatched for the baseline — the reviewer sees the *existing* run's timestamp,
which is the honest thing to show, because it is the run the numbers came from.

The two halves that make it a rule rather than a coincidence:

* **change the released revision** and the pairing no longer matches, so a fresh
  baseline run is created;
* **change the suite version** and the pairing no longer matches either, because
  two revisions measured with two yardsticks is not a comparison.

Both are asserted below, so a lookup that had quietly degraded to "the most
recent completed run for this suite" would fail here rather than in production
against a baseline measured with a different yardstick.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.evaluation.executor import run_claimed_batch
from tests.evaluation import (
    PROMPT_ID,
    StubDispatcher,
    allow_ceiling,
    completion,
    day,
    evaluation_api,
    no_pricing,
    seed_bound_revision,
    seed_case,
    seed_owner,
    seed_run,
    seed_suite,
    totaller_by_run,
)
from tests.integration._asgi import call
from tests.prompt_registry import approve, release, seed_prompt

SESSION_ID = "ses_evaluation_baseline_reuse"

RELEASED_VERSION = "rev_01J000000000000000RELEAS"

CANDIDATE_VERSION = "rev_01J000000000000000CANDID"

SUITE_V3 = "evs_01J00000000000000SAFE003"

SUITE_V4 = "evs_01J00000000000000SAFE004"

EXISTING_BASELINE = "evr_01J00000000000000BASE001"

CASE_V4 = "evc_01J000000000000000CASE04"

#: The timestamp the review screen must show. A distinctive calendar day rather
#: than "now", so an assertion that it is the REUSED run's timestamp cannot pass
#: by accident against a freshly stamped one.
BASELINE_RAN_AT = day(3)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with evaluation_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _a_prompt_whose_baseline_has_already_been_measured(migrate_engine) -> None:  # noqa: ANN001
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine, RELEASED_VERSION, revision_number=1)
    await seed_bound_revision(migrate_engine, CANDIDATE_VERSION, revision_number=2)
    await approve(migrate_engine, RELEASED_VERSION)
    await release(migrate_engine, PROMPT_ID, RELEASED_VERSION)

    await seed_suite(migrate_engine, SUITE_V3, name="safety", suite_version=3, case_count=1)
    await seed_suite(migrate_engine, SUITE_V4, name="safety", suite_version=4, case_count=1)
    await seed_case(migrate_engine, CASE_V4, suite_id=SUITE_V4, ordinal=1, prompt="case-001")

    await seed_run(
        migrate_engine,
        EXISTING_BASELINE,
        suite_id=SUITE_V4,
        version_id=RELEASED_VERSION,
        role="baseline",
        status="completed",
        started_at=BASELINE_RAN_AT,
        finished_at=BASELINE_RAN_AT,
        pass_count=1,
        input_tokens=10,
        output_tokens=5,
    )


async def test_a_second_candidate_dispatches_no_new_baseline_run(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-3's first half: one run is created, and it is the candidate."""
    await _a_prompt_whose_baseline_has_already_been_measured(migrate_engine)

    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": CANDIDATE_VERSION},
        headers=_owner(),
    )
    assert accepted.status_code == 202, accepted.body

    handles = accepted.json()["runs"]
    assert [handle["role"] for handle in handles] == ["candidate"]
    assert handles[0]["suite_id"] == SUITE_V4
    assert handles[0]["suite_version"] == 4

    dispatcher = StubDispatcher(default=completion("in policy"))
    claimed = await run_claimed_batch(
        app_sessionmaker,
        dispatcher=dispatcher,
        ceiling_check=allow_ceiling,
        pricer=no_pricing,
        totaller=totaller_by_run({}),
    )

    assert claimed == 1
    assert len(dispatcher.calls) == 1


async def test_the_screen_shows_the_reused_baselines_own_timestamp(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-3's second half. The date shown is the date the numbers are from."""
    await _a_prompt_whose_baseline_has_already_been_measured(migrate_engine)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": CANDIDATE_VERSION},
        headers=_owner(),
    )
    await run_claimed_batch(
        app_sessionmaker,
        dispatcher=StubDispatcher(default=completion("in policy")),
        ceiling_check=allow_ceiling,
        pricer=no_pricing,
        totaller=totaller_by_run({}),
    )

    comparison = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/comparison",
        params={"candidate": CANDIDATE_VERSION},
        headers=_owner(),
    )
    block = comparison.json()[0]

    assert block["baseline_run_id"] == EXISTING_BASELINE
    assert block["baseline_ran_at"].startswith(BASELINE_RAN_AT.date().isoformat())


async def test_a_newly_released_revision_invalidates_the_pairing(
    api, migrate_engine
) -> None:
    """ADR-0004's first half, from the other side.

    The baseline is pinned to the revision that is released NOW. Release a
    different one and the existing run stops being the baseline, because it
    measured text nobody is serving any more — so a new baseline run is created
    rather than a stale figure reused.
    """
    await _a_prompt_whose_baseline_has_already_been_measured(migrate_engine)

    await approve(migrate_engine, CANDIDATE_VERSION)
    await release(migrate_engine, PROMPT_ID, CANDIDATE_VERSION)

    third = "rev_01J0000000000000000THIRD"
    await seed_bound_revision(migrate_engine, third, revision_number=3)

    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": third},
        headers=_owner(),
    )

    roles = sorted(handle["role"] for handle in accepted.json()["runs"])
    assert roles == ["baseline", "candidate"]

    baseline = next(
        handle for handle in accepted.json()["runs"] if handle["role"] == "baseline"
    )
    assert baseline["run_id"] != EXISTING_BASELINE


async def test_a_new_suite_version_invalidates_the_pairing(api, migrate_engine) -> None:
    """ADR-0004's second half, and the reason the pairing carries ``suite_id``.

    ``suite_id`` identifies one VERSION of a suite, not the suite by name. Saving
    version 5 leaves the version-4 baseline where it is and stops it counting,
    because comparing a candidate measured at version 5 against a baseline
    measured at version 4 would publish a difference the revisions did not cause.
    """
    await _a_prompt_whose_baseline_has_already_been_measured(migrate_engine)

    suite_v5 = "evs_01J00000000000000SAFE005"
    await seed_suite(migrate_engine, suite_v5, name="safety", suite_version=5, case_count=1)
    await seed_case(
        migrate_engine,
        "evc_01J000000000000000CASE05",
        suite_id=suite_v5,
        ordinal=1,
        prompt="case-001",
    )

    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": CANDIDATE_VERSION},
        headers=_owner(),
    )

    handles = accepted.json()["runs"]
    assert sorted(handle["role"] for handle in handles) == ["baseline", "candidate"]
    assert {handle["suite_id"] for handle in handles} == {suite_v5}
