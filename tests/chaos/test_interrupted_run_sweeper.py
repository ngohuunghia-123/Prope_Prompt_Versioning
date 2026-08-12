"""AC-7 — a worker that died mid-run leaves a row, and the sweeper is what reads it.

ADR-0049 declines the broker for this module on the grounds that ``eval_run.status``
is already a queue. The cost of that decision is exactly this: there is no
redelivery, so a process that dies between claiming a run and finishing it leaves
a row in ``running`` that nothing will ever move. The sweeper is the whole
compensation, and it is why declining the broker is affordable.

Three claims:

* a ``running`` run with no case-result progress for longer than the no-progress
  window is marked ``interrupted``;
* its **completed case results remain readable** — a partial run is evidence of
  what did happen, and deleting it would be both a lie and, at the privilege
  level, impossible;
* **no case is dispatched twice.** The sweeper reaps; it does not requeue. A
  sweeper that moved the row back to ``queued`` would re-dispatch every case the
  dead worker had already paid for, which is the failure ADR-0049 names as the
  reason redelivery was refused in the first place.
"""

import pytest
from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.evaluation import repository
from prope.evaluation.claim import claim_next_run
from prope.evaluation.domain import SWEEP_NO_PROGRESS_SECONDS, RunStatus
from prope.evaluation.sweeper import sweep_interrupted_runs
from tests.evaluation import (
    PROMPT_ID,
    RUN_ID,
    WORKSPACE_A,
    day,
    frozen_clock,
    seed_bound_revision,
    seed_case,
    seed_case_result,
    seed_owner,
    seed_run,
    seed_suite,
)
from tests.prompt_registry import seed_prompt

SESSION_ID = "ses_evaluation_sweeper00001"

HEALTHY_RUN = "evr_01J00000000000000HEALTH1"

FIRST_CASE = "evc_01J0000000000000000CS001"

SECOND_CASE = "evc_01J0000000000000000CS002"

#: The worker died here. Six minutes before ``NOW``, which is past the five
#: minute no-progress window by a margin no clock skew explains.
DIED_AT = day(2)

NOW = day(2, minutes=6)

READ_HISTORY = text(
    """
    SELECT action, target_id
    FROM   history.history_event
    WHERE  scope_prompt_id = :prompt_id
    ORDER  BY seq
    """
)


@pytest.fixture
def clock():
    return frozen_clock(NOW)


async def _a_run_whose_worker_died_halfway(migrate_engine) -> None:  # noqa: ANN001
    """One run in ``running``, one of its two cases already recorded.

    The recorded result is stamped at ``DIED_AT``, so it is the progress marker
    the sweeper measures against — a sweeper that measured against ``started_at``
    alone would reap a slow but healthy run.
    """
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine)

    await seed_suite(migrate_engine, case_count=2)
    await seed_case(migrate_engine, FIRST_CASE, ordinal=1, prompt="case-001")
    await seed_case(migrate_engine, SECOND_CASE, ordinal=2, prompt="case-002")

    await seed_run(migrate_engine, status="running", started_at=DIED_AT)
    await seed_case_result(
        migrate_engine,
        "evcr_01J0000000000000RESULT1",
        case_id=FIRST_CASE,
        outcome="pass",
        created_at=DIED_AT,
    )


async def test_the_sweeper_marks_a_stalled_run_interrupted(
    app_sessionmaker, migrate_engine, clock
) -> None:
    """AC-7's first claim, at the exact window ``SWEEP_NO_PROGRESS_SECONDS`` names."""
    await _a_run_whose_worker_died_halfway(migrate_engine)

    reaped = await sweep_interrupted_runs(app_sessionmaker, clock=clock)
    assert reaped == 1

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        run = await repository.load_run(db, RUN_ID)

    assert run is not None
    assert run.status is RunStatus.INTERRUPTED
    assert run.finished_at == NOW


async def test_the_partial_results_remain_readable(
    app_sessionmaker, migrate_engine, clock
) -> None:
    """AC-7's second claim. A partial run is evidence, not garbage to collect.

    ``prope_app`` holds no ``DELETE`` on ``case_result`` at all, so this is a
    guarantee of the grant matrix as much as of the sweeper's code — which is the
    right place for it, because a future sweeper that tried to tidy up would be
    refused by the database rather than reviewed by a person.
    """
    await _a_run_whose_worker_died_halfway(migrate_engine)
    await sweep_interrupted_runs(app_sessionmaker, clock=clock)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        results = await repository.list_case_results(db, RUN_ID)

    assert [result.case_id for result in results] == [FIRST_CASE]
    assert results[0].outcome.value == "pass"


async def test_the_interrupted_run_is_never_claimed_again(
    app_sessionmaker, migrate_engine, clock
) -> None:
    """AC-7's third claim, and the reason the sweeper reaps rather than requeues.

    The claim looks for ``status = 'queued'``. An ``interrupted`` run is
    terminal, so the second case — the one the dead worker never reached — is
    never dispatched by anybody. That is a deliberate choice of "one paid
    dispatch and a visible gap" over "two paid dispatches and a tidy row", and
    the assertion is that the claim finds nothing.
    """
    await _a_run_whose_worker_died_halfway(migrate_engine)
    await sweep_interrupted_runs(app_sessionmaker, clock=clock)

    assert await claim_next_run(app_sessionmaker) is None


async def test_a_run_that_is_still_making_progress_is_left_alone(
    app_sessionmaker, migrate_engine
) -> None:
    """The control, and the property that stops the sweeper eating live work.

    A sweeper with no lower bound reaps everything, and the failure looks exactly
    like a flaky provider. The window is read from the constant so the two cannot
    drift apart.
    """
    await _a_run_whose_worker_died_halfway(migrate_engine)

    just_inside = day(2, seconds=int(SWEEP_NO_PROGRESS_SECONDS) - 30)
    reaped = await sweep_interrupted_runs(app_sessionmaker, clock=frozen_clock(just_inside))

    assert reaped == 0

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        run = await repository.load_run(db, RUN_ID)

    assert run is not None
    assert run.status is RunStatus.RUNNING


async def test_the_reaping_is_recorded_in_property_history(
    app_sessionmaker, migrate_engine, clock
) -> None:
    """A run that ends without a person ending it is still a state change.

    The event is appended in the same transaction as the status move, with a
    ``NULL`` actor because no user did this — A-119's ``scope_prompt_id`` is what
    puts it on the prompt's activity feed beside the run that started it.
    """
    await _a_run_whose_worker_died_halfway(migrate_engine)
    await sweep_interrupted_runs(app_sessionmaker, clock=clock)

    async with migrate_engine.begin() as connection:
        events = (await connection.execute(READ_HISTORY, {"prompt_id": PROMPT_ID})).all()

    assert ("eval_run_interrupted", RUN_ID) in [
        (action, target_id) for action, target_id in events
    ]


async def test_a_healthy_run_in_another_state_is_not_swept(
    app_sessionmaker, migrate_engine, clock
) -> None:
    """Only ``running`` is sweepable. ``queued`` is not late; it is waiting.

    A sweeper that reaped ``queued`` rows would delete the backlog every time the
    workers were busy, and the deployment would look healthy while quietly
    running nothing.
    """
    await _a_run_whose_worker_died_halfway(migrate_engine)
    await seed_run(migrate_engine, HEALTHY_RUN, status="queued")

    await sweep_interrupted_runs(app_sessionmaker, clock=clock)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        healthy = await repository.load_run(db, HEALTHY_RUN)

    assert healthy is not None
    assert healthy.status is RunStatus.QUEUED
