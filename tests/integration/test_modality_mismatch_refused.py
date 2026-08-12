"""AC-9 — a suite that declares ``text`` against a target that returns an asset.

Without this check every assertion in the suite fails at once, and twenty red
cases read as "this revision is much worse" when what actually happened is that
the suite and the target are measuring different things. So the run is
**refused**, with the mismatch named, rather than completed with a wall of
failures.

**The refusal asserted here is the CLAIM-TIME one**, per ADR-0049's restatement
of this criterion. ``POST /eval-runs`` answers ``202`` and the run is queued;
only the claim-time result writes ``status=refused``, because a queued run may
sit behind others that consume the budget while it waits.

**One deviation from AC-9's wording, recorded in OQ-145.** AC-9 says "refused
before any case is dispatched". The returned *shape* is not knowable without a
call — nothing in the revision declares it — so the executor dispatches case 1 as
a probe, checks the shape it came back with, and refuses. The property AC-9 is
really about survives intact and is what the assertions below read: **no case
result is written and no upstream call is billed**, because the refusal happens
before ``price_usage`` is ever reached.
"""

import pytest
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.evaluation.executor import run_claimed_batch
from tests.evaluation import (
    PROMPT_ID,
    VERSION_ID,
    StubDispatcher,
    allow_ceiling,
    completion,
    evaluation_api,
    seed_bound_revision,
    seed_case,
    seed_owner,
    seed_suite,
    totaller_by_run,
)
from tests.integration._asgi import call
from tests.prompt_registry import seed_prompt

SESSION_ID = "ses_evaluation_modality0001"

SUITE = "evs_01J00000000000000TEXTSU1"

CASE_COUNT = 5

#: What the target returns instead of prose. ``returned_shape`` classifies this
#: as ``asset_reference`` on its scheme, which is the half of the message the
#: reviewer needs in order to know it is the SUITE that is wrong.
ASSET_REFERENCE = "https://cdn.example/generated/0001.png"


class RecordingPricer:
    """A ``pricer=`` that records rather than prices.

    AC-9's "no upstream call is billed" is asserted as *this was never called*.
    A stub that quietly accepted the rows would make the criterion untestable —
    the ledger is the only place the billing would show up, and evaluation may
    not read it back (``ledger.call_record`` is a sink).
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def __call__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.calls.append(args)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with evaluation_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _a_text_suite_against_an_asset_returning_target(migrate_engine) -> None:  # noqa: ANN001
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine)

    await seed_suite(
        migrate_engine, SUITE, name="safety", output_modality="text", case_count=CASE_COUNT
    )
    for ordinal in range(1, CASE_COUNT + 1):
        await seed_case(
            migrate_engine,
            f"evc_01J0000000000000000CS{ordinal:03d}",
            suite_id=SUITE,
            ordinal=ordinal,
            name=f"case {ordinal}",
            prompt=f"case-{ordinal:03d}",
            assertions=[{"type": "substring", "value": "policy"}],
        )


async def _submit(api) -> str:  # noqa: ANN001
    accepted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/eval-runs",
        json_body={"version_id": VERSION_ID},
        headers=_owner(),
    )
    assert accepted.status_code == 202, accepted.body
    return accepted.json()["runs"][0]["run_id"]


async def test_the_claim_refuses_the_run_and_names_the_reason(
    api, app_sessionmaker, migrate_engine
) -> None:
    """The status transition AC-9 is about, read through the run's own route."""
    await _a_text_suite_against_an_asset_returning_target(migrate_engine)
    run_id = await _submit(api)

    queued = await call(api, "GET", f"/api/v1/eval-runs/{run_id}", headers=_owner())
    assert queued.json()["status"] == "queued"
    assert queued.json()["refused_reason"] is None

    await run_claimed_batch(
        app_sessionmaker,
        dispatcher=StubDispatcher(default=completion(ASSET_REFERENCE)),
        ceiling_check=allow_ceiling,
        pricer=RecordingPricer(),
        totaller=totaller_by_run({}),
    )

    refused = await call(api, "GET", f"/api/v1/eval-runs/{run_id}", headers=_owner())
    assert refused.json()["status"] == "refused"
    assert refused.json()["refused_reason"] == "modality_mismatch"
    assert refused.json()["finished_at"] is not None


async def test_no_case_result_is_written_and_nothing_is_billed(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-9's consequence, which is the part that costs money if it regresses.

    One dispatch — the probe — and then nothing: no per-case rows, and
    ``price_usage`` never called. A refusal that had happened *after* the run
    would show five dispatches and five priced rows here.
    """
    await _a_text_suite_against_an_asset_returning_target(migrate_engine)
    run_id = await _submit(api)

    dispatcher = StubDispatcher(default=completion(ASSET_REFERENCE))
    pricer = RecordingPricer()

    await run_claimed_batch(
        app_sessionmaker,
        dispatcher=dispatcher,
        ceiling_check=allow_ceiling,
        pricer=pricer,
        totaller=totaller_by_run({}),
    )

    assert len(dispatcher.calls) == 1
    assert pricer.calls == []

    cases = await call(api, "GET", f"/api/v1/eval-runs/{run_id}/cases", headers=_owner())
    assert cases.json() == []


async def test_the_refusal_names_the_declared_modality_and_the_returned_shape(
    api, app_sessionmaker, migrate_engine
) -> None:
    """AC-9's "naming both", asserted on the log line rather than on the API.

    ``refused_reason`` is a value from a closed vocabulary and stays that way —
    ADR-0053 makes it the thing the client translates. The two shapes that make
    the refusal diagnosable travel on the structured log line instead, where
    A-046 allows them: both are machine values, neither is content.
    """
    await _a_text_suite_against_an_asset_returning_target(migrate_engine)
    run_id = await _submit(api)

    with structlog.testing.capture_logs() as captured:
        await run_claimed_batch(
            app_sessionmaker,
            dispatcher=StubDispatcher(default=completion(ASSET_REFERENCE)),
            ceiling_check=allow_ceiling,
            pricer=RecordingPricer(),
            totaller=totaller_by_run({}),
        )

    mismatch = next(
        entry for entry in captured if entry["event"] == "evaluation.modality_mismatch"
    )
    assert mismatch["run_id"] == run_id
    assert mismatch["suite_id"] == SUITE
    assert mismatch["outcome"] == "asset_reference"

    refusal = next(entry for entry in captured if entry["event"] == "evaluation.run_refused")
    assert refusal["reason"] == "modality_mismatch"

    assert not any(ASSET_REFERENCE in str(entry) for entry in captured)


async def test_a_text_target_against_a_text_suite_is_not_refused(
    api, app_sessionmaker, migrate_engine
) -> None:
    """The control. A check that refused everything would pass every test above."""
    await _a_text_suite_against_an_asset_returning_target(migrate_engine)
    run_id = await _submit(api)

    await run_claimed_batch(
        app_sessionmaker,
        dispatcher=StubDispatcher(default=completion("this request is in policy")),
        ceiling_check=allow_ceiling,
        pricer=RecordingPricer(),
        totaller=totaller_by_run({}),
    )

    completed = await call(api, "GET", f"/api/v1/eval-runs/{run_id}", headers=_owner())
    assert completed.json()["status"] == "completed"
    assert completed.json()["pass_count"] == CASE_COUNT
