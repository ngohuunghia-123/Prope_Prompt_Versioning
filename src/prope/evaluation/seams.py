"""This module's public in-process surface.

**Two shapes, and the second arrived with ADR-0068.** ``get_review_summary`` is
what release-control reads before a decision. ``score_body_against_suite`` is the
machine-side gate prompt-improvement runs before a person is shown a candidate
edit — and it lives here rather than there because compiling assertions and
deciding whether an output passed is this module's job. A second implementation
next door would be a second definition of *"passes the suite"*, and the one that
drifted would be the one nobody was reading.

``suites_for_prompt`` exists for one question and answers only it: **does this
prompt have a suite at all?** ADR-0068 §2 makes that precondition absolute — no
suite, no edit proposal, for every family and every anomaly — so the caller needs
the answer before it spends anything, and it needs it without reaching past this
file into ``evaluation.repository``.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.evaluation.domain import (
    CostDelta,
    ReviewSummary,
    RunStatus,
    SuiteRow,
    SuiteSummary,
    WithheldReason,
)
from prope.evaluation.gate import (
    CandidateRevision,
    CaseVerdict,
    GateResult,
    SpendCeilingReached,
    score_body_against_suite,
)
from prope.evaluation.repository import list_current_suites
from prope.evaluation.summary import get_review_summary


async def suites_for_prompt(db: AsyncSession, prompt_id: str) -> tuple[SuiteRow, ...]:
    """Every current suite for one prompt, on the caller's transaction.

    **No permission check, and it must never grow one.** The caller has already
    read the prompt row and authorised against it (ADR-0020); a second check here
    is a second answer that can disagree with the first.

    A suite with ``case_count == 0`` is still a suite as far as the ROW is
    concerned and is not one as far as the gate is concerned. The caller filters,
    because *"has a suite"* and *"has something to run"* are different questions
    and this seam should not decide which one was asked.
    """
    return await list_current_suites(db, prompt_id)


#: A run's own columns, keyed the way this module names them. Returned as a
#: frozen dataclass rather than a row mapping so that a caller cannot reach a
#: column nobody meant to expose by spelling its name — the same third bound
#: `access_control.labels.key_labels` argues for its `Mapping[str, str]`.
@dataclass(frozen=True, slots=True)
class CandidateRun:
    run_id: str
    status: str
    pass_count: int
    fail_count: int
    error_count: int
    finished_at: Any


LATEST_CANDIDATE_RUN = text(
    """
    SELECT id, status, pass_count, fail_count, error_count, finished_at
    FROM   evaluation.eval_run
    WHERE  prompt_id = :prompt_id AND version_id = :version_id AND role = 'candidate'
    ORDER  BY id DESC
    LIMIT  1
    """
)


async def latest_candidate_run(
    db: AsyncSession, *, prompt_id: str, version_id: str
) -> CandidateRun | None:
    """The newest candidate run for one revision, on the caller's transaction.

    **What a lifecycle summary needs, and only that.** agent_run renders "has
    this revision been evaluated, and did anything fail" beside the release and
    readiness state; it needs the counts and the status, not a run's cases, not
    its cost, and not the suite it ran against.

    This exists so agent_run does not reach across a schema boundary to read it.
    `SELECT ... FROM evaluation.eval_run` inside another module's repository
    imports nothing, passes every dependency test in the suite, and is still an
    undeclared edge — the hole `tests/architecture/test_no_cross_schema_sql.py`
    exists to close, and the shape its docstring already describes for
    `access."user"`.

    No permission check, and it must never grow one: the caller has read and
    authorised the prompt row before it has a `prompt_id` to pass (ADR-0020).
    """
    row = (
        await db.execute(LATEST_CANDIDATE_RUN, {"prompt_id": prompt_id, "version_id": version_id})
    ).mappings().first()
    if row is None:
        return None
    return CandidateRun(
        run_id=row["id"],
        status=row["status"],
        pass_count=row["pass_count"],
        fail_count=row["fail_count"],
        error_count=row["error_count"],
        finished_at=row["finished_at"],
    )


@dataclass(frozen=True, slots=True)
class RunProgress:
    run_count: int
    finished_count: int
    completed_cases: int
    total_cases: int
    fail_count: int
    error_count: int
    interrupted: bool


RUN_PROGRESS = text(
    """
    WITH selected_runs AS (
        SELECT r.id, r.status, r.fail_count, r.error_count, s.case_count
        FROM   evaluation.eval_run r
        JOIN   evaluation.eval_suite s ON s.id = r.suite_id
        WHERE  r.id = ANY(:run_ids)
    )
    SELECT count(*)::integer AS run_count,
           count(*) FILTER (WHERE status IN ('completed', 'refused'))::integer AS finished_count,
           coalesce((SELECT count(*) FROM evaluation.case_result c
                     WHERE c.run_id = ANY(:run_ids)), 0)::integer AS completed_cases,
           coalesce(sum(case_count), 0)::integer AS total_cases,
           coalesce(sum(fail_count), 0)::integer AS fail_count,
           coalesce(sum(error_count), 0)::integer AS error_count,
           coalesce(bool_or(status = 'interrupted'), false) AS interrupted
    FROM   selected_runs
    """
)


async def run_progress(db: AsyncSession, run_ids: Sequence[str]) -> RunProgress:
    """How far a set of runs has got, for a progress bar that spans three tables.

    The three tables are all this module's — `eval_run`, `eval_suite` and
    `case_result` — which is the argument for the query living here: a caller
    assembling it needs to know that a run's denominator is its *suite's*
    `case_count` and that a finished run may still be `refused`, and neither fact
    is agent_run's to hold.

    An empty request is answered without a round trip, like `key_labels`: a run
    with no eval steps is the ordinary case, and `= ANY('{}')` would otherwise
    cost a query to return zeros.
    """
    unique = sorted({run_id for run_id in run_ids if run_id})
    if not unique:
        return RunProgress(0, 0, 0, 0, 0, 0, False)
    row = (await db.execute(RUN_PROGRESS, {"run_ids": unique})).mappings().one()
    return RunProgress(
        run_count=row["run_count"],
        finished_count=row["finished_count"],
        completed_cases=row["completed_cases"],
        total_cases=row["total_cases"],
        fail_count=row["fail_count"],
        error_count=row["error_count"],
        interrupted=bool(row["interrupted"]),
    )


__all__ = [
    "CandidateRevision",
    "CandidateRun",
    "CaseVerdict",
    "CostDelta",
    "GateResult",
    "ReviewSummary",
    "RunProgress",
    "RunStatus",
    "SpendCeilingReached",
    "SuiteRow",
    "SuiteSummary",
    "WithheldReason",
    "get_review_summary",
    "latest_candidate_run",
    "run_progress",
    "score_body_against_suite",
    "suites_for_prompt",
]
