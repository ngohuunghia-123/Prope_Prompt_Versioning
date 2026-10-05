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

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.evaluation.advisor import analyze_runs
from prope.evaluation.domain import (
    CaseOutcome,
    CaseResultRow,
    CaseRow,
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
from prope.evaluation.improvement_evidence import (
    IMPROVEMENT_SAMPLE_CAP,
    RevisionAssertionEvidence,
    RevisionFailureSample,
    failure_sample,
)
from prope.evaluation.repository import (
    latest_completed_run,
    list_case_results,
    list_cases,
    list_current_suites,
    list_runs_for_prompt,
)
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


#: One failed assertion group from a revision's settled runs, carrying the
#: ``suite_id`` the analysis endpoint deliberately leaves out (its screen groups
#: by NAME; prompt-improvement's gate needs the row). Improvement opts into a
#: current-suite baseline and at most three redacted failure samples in total.
@dataclass(frozen=True, slots=True)
class RevisionFinding:
    suite_id: str | None
    suite_name: str
    assertion_type: str
    failed: int
    total: int
    issue: str
    advice: str
    severity: str
    baseline_run_id: str | None = None
    baseline_error_count: int = 0
    failing_samples: tuple[RevisionFailureSample, ...] = ()


@dataclass(frozen=True, slots=True)
class RevisionAnalysis:
    """The advisor's answer for one revision, in the shape a consumer needs.

    ``brief`` is the advisor's Vietnamese summary; ``findings`` are the failed
    groups, ordered worst-first by the advisor's own sort;
    ``runs_considered`` is how many terminal runs fed the arithmetic. The
    improvement pipeline maps each group onto a detector and opens one finding
    per group — the same evidence a person reads on the analysis screen,
    re-expressed as rows.
    """

    brief: str
    runs_considered: int
    findings: tuple[RevisionFinding, ...]


async def analyze_revision_runs(
    db: AsyncSession,
    *,
    prompt_id: str,
    version_id: str,
    latest_only: bool = False,
    redact_sample: Callable[[str], str] | None = None,
    sample_case_cap: int | None = None,
) -> RevisionAnalysis:
    """The deterministic analysis of one revision's settled runs, as a seam.

    This is `POST .../eval-runs/analysis`'s read, factored out for the one
    consumer that acts on the answer instead of rendering it (ADR-0070). Same
    terminal-runs filter, same grouping, same fixed advice — one definition of
    *"what failed on this revision"*, because a second one next door is a
    second one that drifts.

    ``latest_only`` is for improvement: only the latest COMPLETED run of each
    current suite ID supplies findings and case samples. Historical failures
    cannot trigger a draft after the current baseline passes, and a previous
    suite version cannot be mistaken for the current one through its name.
    Case content is included only when the consumer supplies its evidence
    redactor; an omitted redactor returns metadata without raw case samples.
    ``sample_case_cap`` limits samples to the first failing current suite the
    consumer can gate, so an oversized suite cannot spend the target's budget.

    In the default historical analysis, ``suite_id`` resolves by name against
    the prompt's CURRENT suites: a group
    from a suite that has since been renamed or removed carries ``None``, and
    the caller treats it as evidence without a gateable target — a note, not an
    edit — rather than gating the wrong suite.
    """
    if latest_only:
        return await _analyze_latest_revision_runs(
            db, prompt_id, version_id, redact_sample, sample_case_cap
        )

    listings = await list_runs_for_prompt(db, prompt_id, version_id=version_id)
    settled = [
        listing
        for listing in listings
        if listing.run.status
        in (RunStatus.COMPLETED, RunStatus.INTERRUPTED, RunStatus.REFUSED)
    ]

    run_rows: list[tuple[str, str, int, int, int]] = []
    case_rows: list[tuple[str, list[tuple[bool, str, bool]]]] = []
    for listing in settled:
        run = listing.run
        suite_name = listing.suite_name or ""
        run_rows.append(
            (suite_name, run.status.value, run.pass_count, run.fail_count, run.error_count)
        )
        if run.status is not RunStatus.COMPLETED:
            continue
        per_case: list[tuple[bool, str, bool]] = []
        for result in await list_case_results(db, run.id):
            errored = result.outcome is CaseOutcome.ERROR
            for assertion in result.assertion_results:
                per_case.append((assertion.passed, assertion.type.value, errored))
        case_rows.append((suite_name, per_case))

    brief, groups = analyze_runs(run_rows, case_rows)

    suites = await list_current_suites(db, prompt_id)
    suite_ids = {suite.name: suite.id for suite in suites}

    return RevisionAnalysis(
        brief=brief,
        runs_considered=len(run_rows),
        findings=tuple(
            RevisionFinding(
                suite_id=suite_ids.get(group.suite_name),
                suite_name=group.suite_name,
                assertion_type=group.assertion_type,
                failed=group.failed,
                total=group.total,
                issue=group.issue,
                advice=group.advice,
                severity=group.severity,
            )
            for group in groups
        ),
    )


async def _analyze_latest_revision_runs(
    db: AsyncSession,
    prompt_id: str,
    version_id: str,
    redact_sample: Callable[[str], str] | None,
    sample_case_cap: int | None,
) -> RevisionAnalysis:
    suites = await list_current_suites(db, prompt_id)
    suite_by_id = {suite.id: suite for suite in suites}
    baseline_ids: dict[str, str] = {}
    baseline_errors: dict[str, int] = {}
    results_by_suite: dict[str, tuple[CaseResultRow, ...]] = {}
    run_rows: list[tuple[str, str, int, int, int]] = []
    case_rows: list[tuple[str, list[tuple[bool, str, bool]]]] = []
    for suite in suites:
        run = await latest_completed_run(db, version_id, suite.id)
        if run is None:
            continue
        baseline_ids[suite.id] = run.id
        baseline_errors[suite.id] = run.error_count
        run_rows.append(
            (suite.id, run.status.value, run.pass_count, run.fail_count, run.error_count)
        )
        results = await list_case_results(db, run.id)
        results_by_suite[suite.id] = results
        case_rows.append(
            (
                suite.id,
                [
                    (assertion.passed, assertion.type.value, result.outcome is CaseOutcome.ERROR)
                    for result in results
                    for assertion in result.assertion_results
                ],
            )
        )

    # The advisor still owns arithmetic and advice. Its grouping key is an ID
    # here; human-readable names are applied only after groups are established.
    brief, _ = analyze_runs(run_rows, case_rows)
    groups = [
        group
        for run_row, case_row in zip(run_rows, case_rows, strict=True)
        for group in analyze_runs([run_row], [case_row])[1]
    ]
    groups.sort(key=lambda group: group.failed, reverse=True)
    for suite in suites:
        brief = brief.replace(f"“{suite.id}”", f"“{suite.name}”")
    findings = [
        RevisionFinding(
            suite_id=group.suite_name,
            suite_name=suite_by_id[group.suite_name].name,
            assertion_type=group.assertion_type,
            failed=group.failed,
            total=group.total,
            issue=group.issue,
            advice=group.advice,
            severity=group.severity,
            baseline_run_id=baseline_ids[group.suite_name],
            baseline_error_count=baseline_errors[group.suite_name],
        )
        for group in groups
    ]

    sample_suite_id: str | None = None
    if sample_case_cap is not None:
        sample_suite_id = next(
            (
                finding.suite_id
                for finding in findings
                if finding.suite_id is not None
                and 0 < suite_by_id[finding.suite_id].case_count <= sample_case_cap
            ),
            None,
        )

    remaining = IMPROVEMENT_SAMPLE_CAP
    sampled_case_ids: set[str] = set()
    cases_by_suite: dict[str, dict[str, CaseRow]] = {}
    for ordinal, finding in enumerate(findings):
        if not remaining or finding.suite_id is None or redact_sample is None:
            break
        if sample_case_cap is not None and finding.suite_id != sample_suite_id:
            continue
        suite_id = finding.suite_id
        if suite_id not in cases_by_suite:
            cases_by_suite[suite_id] = {
                case.id: case for case in await list_cases(db, suite_id)
            }
        samples: list[RevisionFailureSample] = []
        for result in results_by_suite[suite_id]:
            if (
                result.outcome is not CaseOutcome.FAIL
                or result.case_id in sampled_case_ids
                or not any(
                    not assertion.passed and assertion.type.value == finding.assertion_type
                    for assertion in result.assertion_results
                )
            ):
                continue
            case = cases_by_suite[suite_id].get(result.case_id)
            if case is None:
                continue
            samples.append(failure_sample(case, result, redact_sample))
            sampled_case_ids.add(case.id)
            remaining -= 1
            if not remaining:
                break
        findings[ordinal] = replace(finding, failing_samples=tuple(samples))

    return RevisionAnalysis(brief, len(run_rows), tuple(findings))


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
    "RevisionAnalysis",
    "RevisionAssertionEvidence",
    "RevisionFailureSample",
    "RevisionFinding",
    "ReviewSummary",
    "RunProgress",
    "RunStatus",
    "SpendCeilingReached",
    "SuiteRow",
    "SuiteSummary",
    "WithheldReason",
    "analyze_revision_runs",
    "analyze_runs",
    "get_review_summary",
    "latest_candidate_run",
    "run_progress",
    "score_body_against_suite",
    "suites_for_prompt",
]
