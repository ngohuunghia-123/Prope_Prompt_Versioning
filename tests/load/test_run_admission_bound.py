"""AC-10, restated per ADR-0049 — two bounds, asserted independently.

The criterion as written names "a global concurrency bound of 10", a number
ADR-0049 deletes: there is no global counter any more, because a global counter
is process state and a second ``worker`` replica would have its own copy of it.
What survives are two bounds that are each enforced somewhere durable, and they
are asserted separately here because they hold in different places:

* **at most ``max_concurrent_runs`` (2) runs in ``running`` per workspace**,
  enforced by the admission predicate INSIDE ``evaluation.claim_next_run()`` —
  a database predicate, so it survives a second replica;
* **at most ``PER_RUN_CONCURRENCY`` (5) dispatches in flight within one run**,
  enforced by the semaphore in ``execute_run``.

The third claim is the one that makes the bounds usable rather than merely safe:
**the remaining runs sit in ``queued`` and every one of them eventually
completes.** A bound that dropped the excess would satisfy both assertions above
and lose work.
"""

from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.evaluation import commands
from prope.evaluation.claim import claim_next_run
from prope.evaluation.domain import MAX_CONCURRENT_RUNS, PER_RUN_CONCURRENCY, RunRole
from prope.evaluation.executor import execute_run, run_claimed_batch
from tests.evaluation import (
    ADMIN_ID,
    PROMPT_ID,
    VERSION_ID,
    WORKSPACE_A,
    StubDispatcher,
    allow_ceiling,
    completion,
    day,
    no_pricing,
    seed_bound_revision,
    seed_case,
    seed_owner,
    seed_suite,
    totaller_by_run,
)
from tests.prompt_registry import seed_prompt

SESSION_ID = "ses_evaluation_admission001"

SUITE_COUNT = 5

WIDE_SUITE = "evs_01J00000000000000WIDESU1"

WIDE_CASE_COUNT = 20

COUNT_BY_STATUS = text(
    "SELECT status, count(*) FROM evaluation.eval_run GROUP BY status ORDER BY status"
)


def _suite_id(index: int) -> str:
    return f"evs_01J0000000000000000SU{index:03d}"


async def _queue_runs(app_sessionmaker, suite_ids: list[str]) -> tuple[str, ...]:  # noqa: ANN001
    """Queue one run per suite through the command, not through a fixture INSERT.

    ``create_runs`` is what the API calls, so a run queued here carries the same
    id shape, the same ``queued`` status and the same history event a real submit
    would — and the claim under test reads the same rows either way.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        return await commands.create_runs(
            db,
            workspace_id=WORKSPACE_A,
            actor_id=ADMIN_ID,
            prompt_id=PROMPT_ID,
            version_id=VERSION_ID,
            suite_ids=suite_ids,
            role=RunRole.CANDIDATE,
            now=day(1),
        )


async def _five_suites_each_with_two_cases(migrate_engine) -> None:  # noqa: ANN001
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine)

    for index in range(1, SUITE_COUNT + 1):
        suite_id = _suite_id(index)
        await seed_suite(migrate_engine, suite_id, name=f"suite-{index}", case_count=2)
        for ordinal in (1, 2):
            await seed_case(
                migrate_engine,
                f"evc_01J000000000000000S{index:02d}C{ordinal}",
                suite_id=suite_id,
                ordinal=ordinal,
                name=f"suite {index} case {ordinal}",
                prompt=f"s{index}-c{ordinal}",
            )


async def _one_suite_with_twenty_cases(migrate_engine) -> None:  # noqa: ANN001
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine)
    await seed_suite(migrate_engine, WIDE_SUITE, name="wide", case_count=WIDE_CASE_COUNT)

    for ordinal in range(1, WIDE_CASE_COUNT + 1):
        await seed_case(
            migrate_engine,
            f"evc_01J0000000000000000W{ordinal:03d}",
            suite_id=WIDE_SUITE,
            ordinal=ordinal,
            name=f"case {ordinal}",
            prompt=f"wide-{ordinal:03d}",
        )


async def test_the_claim_admits_at_most_two_runs_per_workspace(
    app_sessionmaker, migrate_engine
) -> None:
    """The first surviving bound, asserted at the claim rather than at the worker.

    Five runs are queued and the claim is asked six times. It answers twice and
    then stops — not because a counter in this process says so, but because the
    predicate inside the function counts ``running`` rows in the database.
    """
    await _five_suites_each_with_two_cases(migrate_engine)
    await _queue_runs(app_sessionmaker, [_suite_id(index) for index in range(1, SUITE_COUNT + 1)])

    claimed = []
    for _ in range(SUITE_COUNT + 1):
        found = await claim_next_run(app_sessionmaker, max_concurrent_runs=MAX_CONCURRENT_RUNS)
        if found is None:
            break
        claimed.append(found)

    assert len(claimed) == MAX_CONCURRENT_RUNS
    assert len({run.run_id for run in claimed}) == MAX_CONCURRENT_RUNS

    async with migrate_engine.begin() as connection:
        counts = dict((await connection.execute(COUNT_BY_STATUS)).all())

    assert counts == {
        "running": MAX_CONCURRENT_RUNS,
        "queued": SUITE_COUNT - MAX_CONCURRENT_RUNS,
    }


async def test_the_remaining_runs_stay_queued_and_eventually_complete(
    app_sessionmaker, migrate_engine
) -> None:
    """The claim admits in batches; nothing is dropped and nothing starves.

    The loop below is the ``worker``'s claim loop with the sleep taken out. Three
    passes drain five runs at two per pass, which is the arithmetic the bound
    implies — and the assertion is on the FINAL state, so a pass that quietly
    skipped a run would leave it queued and fail here.
    """
    await _five_suites_each_with_two_cases(migrate_engine)
    queued = await _queue_runs(
        app_sessionmaker, [_suite_id(index) for index in range(1, SUITE_COUNT + 1)]
    )

    executed = 0
    for _ in range(SUITE_COUNT):
        executed += await run_claimed_batch(
            app_sessionmaker,
            dispatcher=StubDispatcher(default=completion("ok")),
            ceiling_check=allow_ceiling,
            pricer=no_pricing,
            totaller=totaller_by_run({}),
        )
        if executed >= len(queued):
            break

    assert executed == SUITE_COUNT

    async with migrate_engine.begin() as connection:
        counts = dict((await connection.execute(COUNT_BY_STATUS)).all())

    assert counts == {"completed": SUITE_COUNT}


async def test_dispatches_within_one_run_never_exceed_the_per_run_bound(
    app_sessionmaker, migrate_engine
) -> None:
    """The second surviving bound, measured rather than read from the source.

    Twenty cases with injected latency, so every case would genuinely be in
    flight at the same time if nothing held them back. ``max_in_flight`` is
    recorded around the ``await`` inside the stub, so the number is what actually
    happened and not what the semaphore was constructed with.

    The probe case is dispatched alone before the gate opens, which is why the
    observed maximum is the bound itself and not the bound plus one.
    """
    await _one_suite_with_twenty_cases(migrate_engine)
    await _queue_runs(app_sessionmaker, [WIDE_SUITE])

    claimed = await claim_next_run(app_sessionmaker)
    assert claimed is not None

    dispatcher = StubDispatcher(default=completion("ok"), latency_seconds=0.05)
    status = await execute_run(
        app_sessionmaker,
        claimed,
        dispatcher=dispatcher,
        ceiling_check=allow_ceiling,
        pricer=no_pricing,
        totaller=totaller_by_run({}),
    )

    assert status.value == "completed"
    assert len(dispatcher.calls) == WIDE_CASE_COUNT
    assert dispatcher.max_in_flight <= PER_RUN_CONCURRENCY
    assert dispatcher.max_in_flight > 1


async def test_a_lower_bound_is_honoured_when_the_caller_asks_for_one(
    app_sessionmaker, migrate_engine
) -> None:
    """The bound is a parameter of the claim, not a constant baked into the SQL.

    ``worker`` passes ``MAX_CONCURRENT_RUNS``; a deployment that wanted one run
    at a time would pass 1. Asserted because a function that ignored its
    argument would pass every other test in this file.
    """
    await _five_suites_each_with_two_cases(migrate_engine)
    await _queue_runs(app_sessionmaker, [_suite_id(index) for index in range(1, SUITE_COUNT + 1)])

    first = await claim_next_run(app_sessionmaker, max_concurrent_runs=1)
    second = await claim_next_run(app_sessionmaker, max_concurrent_runs=1)

    assert first is not None
    assert second is None
