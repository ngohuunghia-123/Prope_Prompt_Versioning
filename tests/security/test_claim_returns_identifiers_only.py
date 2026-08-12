"""AC-12 and T-010 — the fourth privilege escalation, and what makes it safe.

``evaluation.claim_next_run()`` is the only ``SECURITY DEFINER`` function this
module ships and the fourth in the whole system. It exists because a claim has to
see queued rows in *every* workspace at once, before it knows which workspace the
work belongs to — there is no ``app.workspace_id`` to set yet, and RLS is
deny-by-default, so an ordinary read would answer zero rows forever.

What is asserted here is **the property that makes the bypass safe**, not the
bypass itself:

* the function returns **five identifiers and nothing else** — no prompt body, no
  case input, no output, no money. Everything the executor needs afterwards it
  re-reads under RLS with the claimed run's own ``workspace_id`` set;
* a direct ``SELECT`` on ``evaluation.eval_run`` as ``prope_app`` with no
  ``app.workspace_id`` set returns **zero rows**, so the function is the only
  route in;
* the transition it performs is confined to the claimed row — the other
  workspace's queued run is still queued afterwards.
"""

from sqlalchemy import text

from prope.evaluation.claim import claim_next_run
from tests.access_control import seed_workspace
from tests.evaluation import (
    PROMPT_ID,
    RUN_ID,
    SUITE_ID,
    WORKSPACE_A,
    seed_bound_revision,
    seed_case,
    seed_owner,
    seed_run,
    seed_suite,
)
from tests.prompt_registry import seed_prompt
from tests.unit import WORKSPACE_B

SESSION_ID = "ses_evaluation_claim_only001"

OTHER_WORKSPACE_SUITE = "evs_01J00000000000000OTHERS1"

OTHER_WORKSPACE_RUN = "evr_01J00000000000000OTHERR1"

OTHER_PROMPT = "prm_01J0000000000000000OTHER"

SELECT_EVERY_RUN = text("SELECT id, workspace_id FROM evaluation.eval_run")

SELECT_EVERY_CASE_RESULT = text("SELECT id FROM evaluation.case_result")

READ_STATUS = text("SELECT status FROM evaluation.eval_run WHERE id = :run_id")


async def _queued_runs_in_two_workspaces(migrate_engine) -> None:  # noqa: ANN001
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine)
    await seed_suite(migrate_engine, case_count=1)
    await seed_case(migrate_engine)
    await seed_run(migrate_engine)

    await seed_workspace(migrate_engine, WORKSPACE_B, slug="beta")
    await seed_suite(
        migrate_engine,
        OTHER_WORKSPACE_SUITE,
        workspace_id=WORKSPACE_B,
        prompt_id=OTHER_PROMPT,
        case_count=0,
    )
    await seed_run(
        migrate_engine,
        OTHER_WORKSPACE_RUN,
        workspace_id=WORKSPACE_B,
        prompt_id=OTHER_PROMPT,
        suite_id=OTHER_WORKSPACE_SUITE,
    )


async def test_the_claim_returns_five_identifiers_and_nothing_else(
    app_sessionmaker, migrate_engine
) -> None:
    """T-010's assertion, on the returned object rather than on the SQL.

    ``ClaimedRun`` has exactly five fields, all of them identifiers. The type is
    what stops the function growing a sixth that carries content: adding one
    would mean adding it here, in a file that says why it must not exist.
    """
    await _queued_runs_in_two_workspaces(migrate_engine)

    claimed = await claim_next_run(app_sessionmaker)

    assert claimed is not None
    assert claimed.run_id in {RUN_ID, OTHER_WORKSPACE_RUN}

    fields = set(type(claimed).__slots__)
    assert fields == {"run_id", "workspace_id", "prompt_id", "version_id", "suite_id"}

    for value in (
        claimed.run_id,
        claimed.workspace_id,
        claimed.prompt_id,
        claimed.version_id,
        claimed.suite_id,
    ):
        assert isinstance(value, str)
        assert "_" in value


async def test_a_direct_select_with_no_tenant_set_returns_zero_rows(
    app_engine, migrate_engine
) -> None:
    """AC-12's second half, and the whole reason the function has to exist.

    ``prope_app`` reading ``eval_run`` with no ``app.workspace_id`` set sees
    NOTHING — not an error, which a caller could catch and work around, but zero
    rows (ADR-0035, ADR-0045). The same read as ``prope_migrate`` returns both
    rows, which is what proves the emptiness above is the policy and not an empty
    table.
    """
    await _queued_runs_in_two_workspaces(migrate_engine)

    async with app_engine.begin() as connection:
        runs = (await connection.execute(SELECT_EVERY_RUN)).all()
        results = (await connection.execute(SELECT_EVERY_CASE_RESULT)).all()

    assert runs == []
    assert results == []

    async with migrate_engine.begin() as connection:
        owner_view = (await connection.execute(SELECT_EVERY_RUN)).all()

    assert len(owner_view) == 2


async def test_the_claim_moves_exactly_one_row_and_leaves_the_other_workspace_queued(
    app_sessionmaker, migrate_engine
) -> None:
    """The transition is confined to the claimed row.

    A definer function that saw every workspace at once is one ``WHERE`` clause
    away from moving every workspace at once, and the failure would be silent:
    both runs would go ``running`` and one would never be executed by anybody.
    """
    await _queued_runs_in_two_workspaces(migrate_engine)

    claimed = await claim_next_run(app_sessionmaker)
    assert claimed is not None

    other = OTHER_WORKSPACE_RUN if claimed.run_id == RUN_ID else RUN_ID

    async with migrate_engine.begin() as connection:
        claimed_status = await connection.scalar(READ_STATUS, {"run_id": claimed.run_id})
        other_status = await connection.scalar(READ_STATUS, {"run_id": other})

    assert claimed_status == "running"
    assert other_status == "queued"


async def test_the_claim_answers_none_when_nothing_is_queued(
    app_sessionmaker, migrate_engine
) -> None:
    """An empty queue is ``None``, never an exception and never a stale row.

    The claim loop runs once a second forever, so the empty case is the case it
    is in almost always — and an exception there would be a log line a second
    for the life of the deployment.
    """
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine)
    await seed_suite(migrate_engine, case_count=0)

    assert await claim_next_run(app_sessionmaker) is None


async def test_the_admission_predicate_is_evaluated_per_workspace(
    app_sessionmaker, migrate_engine
) -> None:
    """ADR-0049's bound, and it is per TENANT rather than global.

    Workspace A already holds two runs in ``running``, which is
    ``max_concurrent_runs``; its queued run must wait. Workspace B holds none, so
    its queued run is claimable in the same call — a global counter would starve
    every other tenant behind one busy one.
    """
    await _queued_runs_in_two_workspaces(migrate_engine)

    for index in (1, 2):
        await seed_run(
            migrate_engine,
            f"evr_01J0000000000000RUNNIN{index}",
            suite_id=SUITE_ID,
            status="running",
            prompt_id=PROMPT_ID,
            workspace_id=WORKSPACE_A,
        )

    claimed = await claim_next_run(app_sessionmaker, max_concurrent_runs=2)

    assert claimed is not None
    assert claimed.workspace_id == WORKSPACE_B
    assert claimed.run_id == OTHER_WORKSPACE_RUN
