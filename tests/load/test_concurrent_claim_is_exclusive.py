"""AC-13 — two claim loops, one queued run, exactly one transition.

This is the case a second ``worker`` replica creates (A-138), and it is why
``FOR UPDATE SKIP LOCKED``, the admission predicate and the ``UPDATE`` all live
inside **one** transaction rather than being three steps a caller composes. Split
across two round trips, the sequence is a textbook read-modify-write race: both
loops see ``queued``, both dispatch every case, and the workspace pays twice for
the same run with no error anywhere.

Two claims:

* exactly one of two concurrent claims wins a single queued run, and the loser
  answers ``None`` rather than raising or blocking;
* with several runs queued, concurrent claims **partition** them — no run is
  handed out twice, and the losers move on to the next candidate rather than
  contending for the one that is taken.

The second is what ``SKIP LOCKED`` buys over plain ``FOR UPDATE``: plain
``FOR UPDATE`` would make every loop queue behind the same row and the fleet
would serialise on its own first candidate.
"""

import asyncio

from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.evaluation import commands
from prope.evaluation.claim import claim_next_run
from prope.evaluation.domain import RunRole
from tests.evaluation import (
    ADMIN_ID,
    PROMPT_ID,
    VERSION_ID,
    WORKSPACE_A,
    day,
    seed_bound_revision,
    seed_case,
    seed_owner,
    seed_suite,
)
from tests.prompt_registry import seed_prompt

SESSION_ID = "ses_evaluation_claim_race01"

SUITE_COUNT = 4

#: More loops than runs on purpose. The losers are the assertion: a claim that
#: blocked instead of skipping would leave them awaiting a lock that the winner
#: only releases at commit, and the test would hang rather than fail.
LOOP_COUNT = 8

COUNT_BY_STATUS = text(
    "SELECT status, count(*) FROM evaluation.eval_run GROUP BY status ORDER BY status"
)


def _suite_id(index: int) -> str:
    return f"evs_01J0000000000000000SU{index:03d}"


async def _suites_and_queued_runs(migrate_engine, app_sessionmaker, count: int) -> tuple[str, ...]:  # noqa: ANN001
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine)

    for index in range(1, count + 1):
        suite_id = _suite_id(index)
        await seed_suite(migrate_engine, suite_id, name=f"suite-{index}", case_count=1)
        await seed_case(
            migrate_engine,
            f"evc_01J000000000000000S{index:02d}C1",
            suite_id=suite_id,
            ordinal=1,
            name=f"suite {index} case 1",
            prompt=f"s{index}-c1",
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        return await commands.create_runs(
            db,
            workspace_id=WORKSPACE_A,
            actor_id=ADMIN_ID,
            prompt_id=PROMPT_ID,
            version_id=VERSION_ID,
            suite_ids=[_suite_id(index) for index in range(1, count + 1)],
            role=RunRole.CANDIDATE,
            now=day(1),
        )


async def test_two_concurrent_claims_produce_exactly_one_transition(
    app_sessionmaker, migrate_engine
) -> None:
    """AC-13 as written: one queued run, two loops, one winner."""
    queued = await _suites_and_queued_runs(migrate_engine, app_sessionmaker, 1)
    assert len(queued) == 1

    results = await asyncio.gather(
        claim_next_run(app_sessionmaker, max_concurrent_runs=4),
        claim_next_run(app_sessionmaker, max_concurrent_runs=4),
    )

    winners = [claimed for claimed in results if claimed is not None]
    assert len(winners) == 1
    assert winners[0].run_id == queued[0]

    async with migrate_engine.begin() as connection:
        counts = dict((await connection.execute(COUNT_BY_STATUS)).all())

    assert counts == {"running": 1}


async def test_concurrent_claims_partition_the_queue_and_never_double_hand_a_run(
    app_sessionmaker, migrate_engine
) -> None:
    """``SKIP LOCKED``'s actual benefit: contention becomes distribution.

    Eight loops, four queued runs, one call each. Every run is handed to exactly
    one loop and the four extra loops answer ``None`` — none of them blocks, and
    none of them is handed a run somebody else already has.

    The admission bound is set above the queue depth here on purpose. This test
    is about exclusivity, and a bound of two would make four of the ``None``s
    admission refusals rather than losses, which is a different property with a
    test of its own.
    """
    queued = await _suites_and_queued_runs(migrate_engine, app_sessionmaker, SUITE_COUNT)

    results = await asyncio.gather(
        *(
            claim_next_run(app_sessionmaker, max_concurrent_runs=LOOP_COUNT)
            for _ in range(LOOP_COUNT)
        )
    )

    claimed = [run.run_id for run in results if run is not None]

    assert len(claimed) == len(set(claimed))
    assert set(claimed) <= set(queued)
    assert len(claimed) == SUITE_COUNT

    async with migrate_engine.begin() as connection:
        counts = dict((await connection.execute(COUNT_BY_STATUS)).all())

    assert counts == {"running": SUITE_COUNT}
