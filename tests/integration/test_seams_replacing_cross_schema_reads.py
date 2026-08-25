"""The seams that replaced SQL reaching across a schema boundary.

Every one of these existed as a `SELECT` inside a module that owns neither the
table nor an import of the module that does — the failure
`tests/architecture/test_no_cross_schema_sql.py` was written to catch, and which
its own docstring describes for the `access."user"` case: imports nothing,
passes every dependency test, and still reads another module's table.

Moving a query is not free, and the architecture test cannot tell a correct move
from a broken one — it only sees that the schema name left the file. These are
what say the answers did not change. None of them had runtime coverage before
this file: `agent_run.lifecycle` and `agent_run.repository` are reached only
through `test_worker_jobs`, which needs RabbitMQ.

**`release_control.seams.latest_decision` is deliberately not here.** It is the
one move that carried its SQL across verbatim — same columns, same predicates,
same `ORDER BY decided_at DESC, id DESC` — into the module that owns the table.
The others each changed something worth an assertion: a `workspace_id` predicate
added, a `prompt_id` predicate dropped, a row mapping turned into a dataclass, a
`COALESCE` turned into a Python branch. Testing a copied string would assert that
copying works.
"""

from datetime import UTC, datetime

from prope.access_control.seams import roles_held
from prope.call_ledger.retention_settings import set_observability_content_access
from prope.call_ledger.seams import content_access_enabled
from prope.db.session import workspace_transaction
from prope.evaluation.seams import latest_candidate_run, run_progress
from prope.prompt_improvement.domain import Anomaly, DetectorId
from prope.prompt_improvement.repository import open_or_bump_finding
from prope.prompt_improvement.seams import open_finding_count
from prope.prompt_readiness.domain import Finding, RuleId, Severity, UsageProfile
from prope.prompt_readiness.repository import freeze_report
from prope.prompt_readiness.seams import count_frozen_findings
from tests.access_control import (
    ADMIN_ID,
    seed_member,
    seed_role,
    seed_user,
    seed_workspace,
)
from tests.evaluation import (
    PROMPT_ID,
    RUN_ID,
    SUITE_ID,
    VERSION_ID,
    seed_run,
    seed_suite,
)
from tests.prompt_registry import seed_prompt, seed_revision
from tests.unit import WORKSPACE_A

#: A second prompt in the same workspace, to prove a per-prompt count is one.
OTHER_PROMPT_ID = "prm_01J0000000000000000OTHER"

# ---------------------------------------------------------------------------
# access_control.seams.roles_held
# ---------------------------------------------------------------------------


async def test_roles_held_answers_with_the_names_and_not_a_verdict(
    migrate_engine, app_sessionmaker
) -> None:
    """prompt-registry used to ask this as `EXISTS(... role IN ('Owner', ...))`.

    The policy — which roles may see redacted request content — stayed with the
    route that owns it (ADR-0060); what moved is the read.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Reviewer")

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        held = await roles_held(session, workspace_id=WORKSPACE_A, user_id=ADMIN_ID)

    assert held == frozenset({"Reviewer"})


async def test_roles_held_is_empty_for_somebody_with_no_binding(
    migrate_engine, app_sessionmaker
) -> None:
    """Empty, never `None` — the caller intersects, and `None & set()` raises."""
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        held = await roles_held(session, workspace_id=WORKSPACE_A, user_id=ADMIN_ID)

    assert held == frozenset()


# ---------------------------------------------------------------------------
# call_ledger.seams.content_access_enabled
# ---------------------------------------------------------------------------


async def test_a_workspace_that_never_configured_retention_has_not_opted_in(
    migrate_engine, app_sessionmaker
) -> None:
    """**The absent row and the false column are the same answer.**

    This is the half of the old query that `COALESCE(..., false)` was carrying,
    and it is the half worth a test: a workspace with no `workspace_retention`
    row is the state every workspace starts in, and a seam that answered `None`
    would be coerced to the safe value by luck rather than by contract.
    """
    await seed_workspace(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert await content_access_enabled(session, workspace_id=WORKSPACE_A) is False


async def test_the_opt_in_is_read_back_both_ways(migrate_engine, app_sessionmaker) -> None:
    """Written through the module that owns the column, read through the seam.

    The write goes via `set_observability_content_access` rather than an INSERT
    of this file's own, so what is being asserted is that the two agree — a seam
    that read a column the setter does not write would pass a test that seeded
    the row itself.
    """
    await seed_workspace(migrate_engine)

    for enabled in (True, False, True):
        await set_observability_content_access(
            app_sessionmaker,
            WORKSPACE_A,
            enabled,
            updated_by=ADMIN_ID,
            now=datetime(2026, 8, 25, 12, 0, tzinfo=UTC),
        )
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            assert await content_access_enabled(session, workspace_id=WORKSPACE_A) is enabled


# ---------------------------------------------------------------------------
# evaluation.seams.latest_candidate_run
# ---------------------------------------------------------------------------


async def _a_prompt_with_a_revision(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_prompt(migrate_engine, prompt_id=PROMPT_ID, owner_id=ADMIN_ID)
    await seed_revision(
        migrate_engine,
        version_id=VERSION_ID,
        prompt_id=PROMPT_ID,
        body="<instructions>x</instructions>",
    )


async def test_a_revision_with_no_run_answers_none(migrate_engine, app_sessionmaker) -> None:
    """`agent_run.lifecycle` renders DRAFT / RUN_EVALUATION from exactly this."""
    await _a_prompt_with_a_revision(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        found = await latest_candidate_run(session, prompt_id=PROMPT_ID, version_id=VERSION_ID)

    assert found is None


async def test_the_newest_candidate_run_wins_and_a_baseline_is_not_one(
    migrate_engine, app_sessionmaker
) -> None:
    """`role = 'candidate'` and `ORDER BY id DESC` are both load-bearing.

    A baseline run is the same prompt and the same revision; reading it as the
    candidate would report the OLD body's result as this one's.
    """
    await _a_prompt_with_a_revision(migrate_engine)
    await seed_suite(migrate_engine, SUITE_ID, case_count=3)
    await seed_run(migrate_engine, RUN_ID, status="completed", pass_count=3)
    await seed_run(
        migrate_engine,
        "evr_01J00000000000000000BASE",
        role="baseline",
        status="completed",
        fail_count=9,
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        found = await latest_candidate_run(session, prompt_id=PROMPT_ID, version_id=VERSION_ID)

    assert found is not None
    assert found.run_id == RUN_ID
    assert (found.pass_count, found.fail_count, found.error_count) == (3, 0, 0)
    assert found.status == "completed"


# ---------------------------------------------------------------------------
# evaluation.seams.run_progress
# ---------------------------------------------------------------------------


async def test_no_runs_costs_no_round_trip_and_answers_zero() -> None:
    """A run with no eval steps is the ordinary case, so it must not query."""

    class _Explodes:
        async def execute(self, *_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
            raise AssertionError("an empty run list must not reach the database")

    progress = await run_progress(_Explodes(), [])

    assert (progress.run_count, progress.total_cases, progress.interrupted) == (0, 0, False)


async def test_progress_counts_the_suites_cases_as_the_denominator(
    migrate_engine, app_sessionmaker
) -> None:
    """The denominator is the SUITE's `case_count`, not the results written so far.

    That join is the reason this query belongs in evaluation rather than in the
    caller assembling the progress bar.
    """
    await _a_prompt_with_a_revision(migrate_engine)
    await seed_suite(migrate_engine, SUITE_ID, case_count=4)
    await seed_run(migrate_engine, RUN_ID, status="running")

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        progress = await run_progress(session, [RUN_ID])

    assert progress.run_count == 1
    assert progress.finished_count == 0
    assert progress.total_cases == 4
    assert progress.completed_cases == 0
    assert progress.interrupted is False


async def test_an_interrupted_run_is_reported_as_interrupted(
    migrate_engine, app_sessionmaker
) -> None:
    """`agent_run` turns this one flag straight into `RunStatus.FAILED`."""
    await _a_prompt_with_a_revision(migrate_engine)
    await seed_suite(migrate_engine, SUITE_ID, case_count=2)
    await seed_run(migrate_engine, RUN_ID, status="interrupted", fail_count=1)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        progress = await run_progress(session, [RUN_ID])

    assert progress.interrupted is True
    assert progress.fail_count == 1


async def test_a_refused_run_counts_as_finished(migrate_engine, app_sessionmaker) -> None:
    """`refused` is terminal. Counting it as unfinished hangs the progress bar."""
    await _a_prompt_with_a_revision(migrate_engine)
    await seed_suite(migrate_engine, SUITE_ID, case_count=2)
    await seed_run(migrate_engine, RUN_ID, status="refused")

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        progress = await run_progress(session, [RUN_ID])

    assert (progress.run_count, progress.finished_count) == (1, 1)


# ---------------------------------------------------------------------------
# prompt_improvement.seams.open_finding_count
# ---------------------------------------------------------------------------


async def test_a_recurrence_bumps_a_finding_and_does_not_add_one(
    migrate_engine, app_sessionmaker
) -> None:
    """One row per open (prompt, detector) — so the count is prompts, not events.

    `agent_run.lifecycle` turns a non-zero count straight into ATTENTION and
    points a person at the improvements tab. If a recurrence opened a second row,
    a single degrading prompt would read as a worsening workspace.
    """
    await _a_prompt_with_a_revision(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert await open_finding_count(
            session, workspace_id=WORKSPACE_A, prompt_id=PROMPT_ID
        ) == 0

    for _ in range(3):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await open_or_bump_finding(
                session,
                workspace_id=WORKSPACE_A,
                prompt_id=PROMPT_ID,
                anomaly=Anomaly(detector_id=DetectorId.TRUNCATION_RISING),
                evidence_line=None,
            )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert await open_finding_count(
            session, workspace_id=WORKSPACE_A, prompt_id=PROMPT_ID
        ) == 1


async def test_the_count_is_scoped_to_the_prompt_that_was_asked_about(
    migrate_engine, app_sessionmaker
) -> None:
    """A workspace-wide count here would name a prompt the reader cannot see.

    `prompt_improvement.repository`'s own docstring makes the point for the
    inbox — *"a prompt the reader cannot see contributes NOTHING — not a redacted
    row, not a count"* — and the seam has no visibility filter of its own, so the
    `prompt_id` predicate is the whole of what keeps that true here.
    """
    await _a_prompt_with_a_revision(migrate_engine)
    await seed_prompt(
        migrate_engine,
        prompt_id=OTHER_PROMPT_ID,
        owner_id=ADMIN_ID,
        name="dispute-classifier",
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await open_or_bump_finding(
            session,
            workspace_id=WORKSPACE_A,
            prompt_id=OTHER_PROMPT_ID,
            anomaly=Anomaly(detector_id=DetectorId.TRUNCATION_RISING),
            evidence_line=None,
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert await open_finding_count(
            session, workspace_id=WORKSPACE_A, prompt_id=PROMPT_ID
        ) == 0
        assert await open_finding_count(
            session, workspace_id=WORKSPACE_A, prompt_id=OTHER_PROMPT_ID
        ) == 1


# ---------------------------------------------------------------------------
# prompt_readiness.seams.count_frozen_findings
# ---------------------------------------------------------------------------


async def test_no_report_is_none_and_a_clean_report_is_zero(
    migrate_engine, app_sessionmaker
) -> None:
    """**The distinction the whole return type exists for.**

    `None` means nobody has opened the readiness card for this revision; `0`
    means somebody did and it was clean. `agent_run.lifecycle` passes the value
    through as `readiness_attention_count`, so coalescing the two would tell a
    reviewer "nothing to see" about a revision nothing has looked at.
    """
    await _a_prompt_with_a_revision(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert await count_frozen_findings(
            session, workspace_id=WORKSPACE_A, version_id=VERSION_ID
        ) is None

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await freeze_report(
            session,
            workspace_id=WORKSPACE_A,
            prompt_id=PROMPT_ID,
            version_id=VERSION_ID,
            profile=UsageProfile(),
            findings=[],
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert await count_frozen_findings(
            session, workspace_id=WORKSPACE_A, version_id=VERSION_ID
        ) == 0


async def test_the_count_is_the_frozen_copys_and_not_a_recount(
    migrate_engine, app_sessionmaker
) -> None:
    """`freeze_report` is write-once (SR-1), and the count has to inherit that.

    A reviewer's card is frozen evidence. A second freeze with different findings
    must not change the number beside it, or two people reading the same revision
    would see two different cards while both believing it is frozen.
    """
    await _a_prompt_with_a_revision(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await freeze_report(
            session,
            workspace_id=WORKSPACE_A,
            prompt_id=PROMPT_ID,
            version_id=VERSION_ID,
            profile=UsageProfile(),
            findings=[
                Finding(rule_id=RuleId.PROBE_INCOMPLETE, severity=Severity.WARNING),
                Finding(rule_id=RuleId.PROBE_INJECTION_LEAKED, severity=Severity.WARNING),
            ],
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await freeze_report(
            session,
            workspace_id=WORKSPACE_A,
            prompt_id=PROMPT_ID,
            version_id=VERSION_ID,
            profile=UsageProfile(),
            findings=[],
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        assert await count_frozen_findings(
            session, workspace_id=WORKSPACE_A, version_id=VERSION_ID
        ) == 2
