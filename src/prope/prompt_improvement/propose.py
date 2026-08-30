"""The eval-evidence pipeline: analysis → findings → authored draft → rails → gate.

**ADR-0070's run.** A person clicks "propose a fix" on the analysis brief; this
is what runs. The DAG is fixed and the steps are enumerated in the design
pack's shape chapter — the model fills in one step (the draft) and never picks
the next one.

**SR-3's order holds exactly as the sweep holds it**: suite before candidate,
candidate before gate, gate before person. A prompt with nothing gateable
degrades to a CASE proposal — *these are the cases that would make a future
edit gateable at all* — which is the one shape that turns the precondition
into something a person can act on.

**The gate is stricter here than the drift path's.** Non-regression alone is
not the claim eval evidence licenses: an authored edit that fixes nothing is
discarded too. ``failed_after < failed_before`` on the target suite, raw case
counts, and the delta carries both numbers so the card can render
``5/12 → 2/12`` with the N visible.

**No resolution of absent findings.** The sweep closes drift findings whose
detectors stopped firing; this path opens eval findings and resolves nothing,
because it does not know whether the drift detectors still fire — resolving
here would close a production-degradation finding on the strength of an
unrelated evidence source having been read.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.evaluation.seams import (
    CandidateRevision,
    RevisionFinding,
    SpendCeilingReached,
    analyze_revision_runs,
    score_body_against_suite,
    suites_for_prompt,
)
from prope.prompt_improvement import repository
from prope.prompt_improvement.domain import (
    MAX_DRAFT_ATTEMPTS,
    PROBE_CASE_CAP,
    PROPOSAL_TTL,
    Anomaly,
    RemedyFamily,
    RemedyKind,
    Severity,
    TerminationReason,
    bounded_evidence,
    detector_for_assertion,
)
from prope.prompt_improvement.drafter import DrafterUnavailableError, draft_edit
from prope.prompt_improvement.observability import (
    draft_attempts,
    gate_rejected_total,
    proposals_open,
    proposals_total,
    rails_rejected_total,
    runs_total,
)
from prope.prompt_improvement.rails import FEEDBACK, RailCode, RailsReport, check_candidate
from prope.prompt_registry.commands import create_revision
from prope.prompt_registry.domain import MAX_CHANGE_SUMMARY_CHARACTERS, PromptRow, RevisionDraft
from prope.prompt_registry.seams import get_prompt, get_revision

log = structlog.get_logger(__name__)

__all__ = ["JOB_NAME", "run_eval_improvement"]

JOB_NAME = "improvement_eval"


def _finding_anomaly(finding: RevisionFinding) -> Anomaly:
    """One advisor group as an ``Anomaly`` — the arithmetic, re-expressed.

    ``params`` carries the group's figures so the card renders counts without
    re-reading a run that has since moved, the way every other detector's
    params do. Severity is the advisor's own arithmetic (share >= 0.1 is
    warning), carried on the override the domain provides because a static map
    cannot hold a ratio.
    """
    share = finding.failed / finding.total if finding.total else 0.0
    return Anomaly(
        detector_id=detector_for_assertion(finding.assertion_type),
        params={
            "suite_name": finding.suite_name,
            "suite_id": finding.suite_id,
            "assertion_type": finding.assertion_type,
            "failed": finding.failed,
            "total": finding.total,
            "share": round(share, 4),
        },
        severity_override=(
            Severity.WARNING if finding.severity == str(Severity.WARNING) else Severity.ADVICE
        ),
    )


def _evidence_line(anomaly: Anomaly) -> str:
    """The deterministic vi sentence. No model writes this one.

    Eval findings are arithmetic the advisor already worded — ``issue`` is a
    reviewed constant — so the evidence line is composed from it and bounded
    here, BEFORE storage (SR-9), rather than bought from a triage call whose
    prompt is about production traffic.
    """
    params = anomaly.params
    return bounded_evidence(
        f"{params.get('assertion_type', '')}: {params.get('failed', 0)}/{params.get('total', 0)} "
        f"trong bộ «{params.get('suite_name', '')}»"
    )


def _terminate(reason: TerminationReason, **extra: str) -> dict[str, str]:
    runs_total.labels(termination_reason=str(reason)).inc()
    return {"kind": _ACTION_KIND[reason], "reason": str(reason), **extra}


#: Seven reasons, three action kinds. Everything that is not an open proposal
#: or a clean nothing is `limited_evidence` — WARNING on the run — because in
#: every one of those cases findings ARE open and a draft is NOT: exactly the
#: shape "limited evidence" was minted for.
_ACTION_KIND: dict[TerminationReason, str] = {
    TerminationReason.PROPOSAL_OPENED: "open_improvement",
    TerminationReason.NOTHING_FAILED: "no_change",
    TerminationReason.RATE_CAPPED: "no_change",
    TerminationReason.DRAFTER_UNAVAILABLE: "limited_evidence",
    TerminationReason.RAILS_EXHAUSTED: "limited_evidence",
    TerminationReason.RAILS_NO_PROGRESS: "limited_evidence",
    TerminationReason.GATE_REJECTED: "limited_evidence",
}


async def run_eval_improvement(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    *,
    prompt_id: str,
    version_id: str,
    now: datetime | None = None,
    on_phase: Callable[[int], Awaitable[None]] | None = None,
    actor_id: str | None = None,
) -> dict[str, str]:
    """One revision's eval evidence, through to a gated DRAFT the person edits.

    Complete-what-succeeded, always: findings opened on the way to a failed
    draft stay open, and the run's typed reason says which of the seven ends
    it reached — five of which are not errors.

    A candidate that clears the gate no longer stops at an inbox proposal: it
    lands as a real registry revision in ``Draft`` status, derived from the
    selected revision (same model binding, parameters, tags), authored by the
    person who clicked the button. The proposal still opens beside it, so the
    inbox keeps the gate delta and the audit trail, but the thing a person
    reviews is now a version in the rail — the outcome of the run is an
    editable draft, not a suggestion somebody must retype.
    """
    at = now or datetime.now(UTC)
    started = time.perf_counter()

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        prompt = await get_prompt(db, prompt_id)
        selected = await get_revision(db, version_id)
        if prompt is None or selected is None or selected.prompt_id != prompt.id:
            raise ValueError("eval improvement scope no longer exists")
        analysis = await analyze_revision_runs(
            db, prompt_id=prompt_id, version_id=version_id
        )
        anomalies = [_finding_anomaly(finding) for finding in analysis.findings]

    if on_phase is not None:
        await on_phase(1)

    if not anomalies:
        # The explicit no-op outcome. Distinct from every failure by construction
        # (orchestration S3): a run that found nothing says so on the run.
        return _terminate(TerminationReason.NOTHING_FAILED, drafted="false")

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        opened: list[tuple[Anomaly, str]] = []
        for anomaly in anomalies:
            finding_id, _occurrences = await repository.open_or_bump_finding(
                db,
                workspace_id=workspace_id,
                prompt_id=prompt.id,
                anomaly=anomaly,
                evidence_line=_evidence_line(anomaly),
                now=at,
            )
            opened.append((anomaly, finding_id))

    # The gateable target: the first finding whose suite still exists, has
    # cases, and fits under the probe cap. Advisor order is worst-first.
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        suites = await suites_for_prompt(db, prompt.id)

    target: tuple[Anomaly, str] | None = None
    target_suite: Any = None
    for anomaly, finding_id in opened:
        suite = next(
            (s for s in suites if s.id == anomaly.params.get("suite_id") and s.case_count),
            None,
        )
        if suite is not None and suite.case_count <= PROBE_CASE_CAP:
            target = (anomaly, finding_id)
            target_suite = suite
            break

    if target is None:
        # SR-3, degraded: no gateable suite means no edit, and the offer becomes
        # the cases that would make one gateable — the sweep's exact shape.
        return await _open_case(sessionmaker, workspace_id, prompt, opened[0][1], at)

    if on_phase is not None:
        await on_phase(3)

    drafted = await _draft_and_rail(prompt, selected.body, [anomaly for anomaly, _ in opened])

    if on_phase is not None:
        await on_phase(4)

    if isinstance(drafted, dict):
        # The draft step RAN and degraded — the node executed, whatever the
        # model did, so the plan shows it attempted rather than skipped.
        return _terminate(
            TerminationReason(drafted["reason"]),  # type: ignore[arg-type]
            drafted="true",
        )

    candidate_body, rationale, report = drafted

    try:
        result = await score_body_against_suite(
            sessionmaker,
            workspace_id=workspace_id,
            prompt_id=prompt.id,
            version_id=selected.version_id,
            suite_id=target_suite.id,
            candidate=CandidateRevision(
                body=candidate_body,
                provider_config_id=selected.provider_config_id,
                upstream_model=selected.upstream_model,
                parameters=selected.parameters,
            ),
            now=at,
        )
    except SpendCeilingReached:
        log.info("improvement.eval.gate.skipped", workspace_id=workspace_id)
        return await _open_case(sessionmaker, workspace_id, prompt, target[1], at)

    if result is None:
        # *The gate did not happen* — treated as a rejection, never as a pass.
        gate_rejected_total.labels(remedy_family=str(RemedyFamily.LLM_EDIT)).inc()
        return _terminate(TerminationReason.GATE_REJECTED, drafted="true")

    failed_before = result.case_count - result.baseline_pass
    failed_after = result.case_count - result.candidate_pass

    if result.regressed or failed_after >= failed_before:
        # ADR-0070 §3: non-regression AND strict improvement, both raw counts.
        # The log line carries a closed-vocabulary reason plus the two counts
        # — numbers, never case content — so an operator can tell *broke
        # something* from *fixed nothing* without opening a trace.
        gate_rejected_total.labels(remedy_family=str(RemedyFamily.LLM_EDIT)).inc()
        log.info(
            "improvement.eval.gate.rejected",
            reason="regressed" if result.regressed else "no_improvement",
            failed_before=failed_before,
            failed_after=failed_after,
        )
        return _terminate(TerminationReason.GATE_REJECTED, drafted="true")

    delta = dict(result.as_delta())
    delta["failed_before"] = failed_before
    delta["failed_after"] = failed_after

    # The gated candidate becomes a registry revision in Draft status — the
    # run's visible outcome. Authored by the requester (a person clicked the
    # button; an actor the run cannot name would put an unresolvable byline on
    # the version), bound to the selected revision's model binding so the gate
    # result describes the draft as it will actually run.
    draft_version_id = await _materialize_draft(
        sessionmaker, workspace_id,
        prompt=prompt, selected=selected,
        candidate_body=candidate_body, rationale=rationale,
        actor_id=actor_id, now=at,
    )

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        proposal_id = await repository.open_proposal(
            db,
            workspace_id=workspace_id,
            prompt_id=prompt.id,
            finding_id=target[1],
            remedy_kind=RemedyKind.EDIT,
            remedy_family=RemedyFamily.LLM_EDIT,
            candidate_body=candidate_body,
            gate_run_id=result.baseline_run_id,
            gate_delta=delta,
            draft_rationale=rationale,
            rails_report=report.as_json(),
            expires_at=at + PROPOSAL_TTL,
            now=at,
        )

    proposals_total.labels(
        remedy_family=str(RemedyFamily.LLM_EDIT),
        disposition="opened" if proposal_id else "rate_capped",
    ).inc()

    if proposal_id is None:
        # The proposal hit its cap, but the DRAFT exists — the person has the
        # edit in their version tree. Reporting `no_change` here told the UI
        # "nothing was found" over a run that had just produced a gated edit;
        # open_improvement is the truthful kind: something awaits a decision.
        # The reason keeps the cap on record.
        runs_total.labels(termination_reason=str(TerminationReason.RATE_CAPPED)).inc()
        return {
            "kind": _ACTION_KIND[TerminationReason.PROPOSAL_OPENED],
            "reason": str(TerminationReason.RATE_CAPPED),
            "finding_id": target[1],
            "drafted": "true",
            "draft_version_id": draft_version_id,
        }

    proposals_open.inc()

    log.info(
        "improvement.eval.proposed",
        attempt_count=len(report.attempts),
        draft_version_id=draft_version_id,
        duration_seconds=round(time.perf_counter() - started, 3),
    )
    return _terminate(
        TerminationReason.PROPOSAL_OPENED,
        finding_id=target[1],
        proposal_id=proposal_id,
        drafted="true",
        draft_version_id=draft_version_id,
    )


async def _materialize_draft(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    *,
    prompt: PromptRow,
    selected: Any,
    candidate_body: str,
    rationale: str,
    actor_id: str | None,
    now: datetime,
) -> str:
    """Write the gated candidate as the prompt's next revision, in Draft status.

    Returns the new version id. The summary is the drafter's rationale, redacted
    and capped to the registry's change-summary limit — a gate-passing edit with
    a story the column cannot hold must not crash the run that earned it.
    """
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        created = await create_revision(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id or "propai",
            prompt_id=prompt.id,
            draft=RevisionDraft(
                body=candidate_body,
                change_summary=bounded_evidence(rationale)[:MAX_CHANGE_SUMMARY_CHARACTERS],
                original_body=selected.body,
                provider_config_id=selected.provider_config_id,
                upstream_model=selected.upstream_model,
                fallback_answer=selected.fallback_answer,
                parameters=dict(selected.parameters),
                tags=tuple(selected.tags),
            ),
            now=now,
        )
    return created.version_id


async def _draft_and_rail(
    prompt: PromptRow, body: str, anomalies: list[Anomaly]
) -> tuple[str, str, RailsReport] | dict[str, str]:
    """The bounded redraft loop. A refusal-shaped dict on every non-outcome.

    Three attempts, no-progress stop: the SAME typed code twice in a row means
    the feedback is not being acted on, and a third identical refusal is the
    definition of cheap-and-infinite (orchestration D9). Findings are already
    open at this point, so every return here is complete-what-succeeded.
    """
    report = RailsReport(passed=False)
    previous_code: RailCode | None = None
    feedback = ""

    for attempt in range(1, MAX_DRAFT_ATTEMPTS + 1):
        try:
            candidate_body, rationale = await draft_edit(
                prompt_title=prompt.title,
                prompt_body=body,
                failing_groups=anomalies,
                previous_error=feedback,
            )
        except DrafterUnavailableError:
            # Not counted as a rail firing: the model was not reached, and a
            # rails metric that mixes transport failures with validation
            # refusals is a metric nobody can tune.
            return {"reason": str(TerminationReason.DRAFTER_UNAVAILABLE)}

        code = check_candidate(body, candidate_body, rationale)
        if code is None:
            # RailsReport is frozen (it is stored on the proposal verbatim), so
            # a pass is a NEW report — assigning `report.passed` here used to
            # raise FrozenInstanceError *after* the model had already produced
            # a valid draft, crashing every run that should have succeeded.
            report = RailsReport(
                passed=True,
                attempts=[*report.attempts, {"attempt": attempt, "code": "passed"}],
            )
            draft_attempts.observe(attempt)
            return candidate_body, rationale, report

        rails_rejected_total.labels(rail_code=str(code)).inc()
        report.attempts.append({"attempt": attempt, "code": str(code)})

        if code == previous_code:
            draft_attempts.observe(attempt)
            return {"reason": str(TerminationReason.RAILS_NO_PROGRESS)}
        previous_code = code
        feedback = FEEDBACK[code]

    draft_attempts.observe(MAX_DRAFT_ATTEMPTS)
    return {"reason": str(TerminationReason.RAILS_EXHAUSTED)}


async def _open_case(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    prompt: PromptRow,
    finding_id: str,
    now: datetime,
) -> dict[str, str]:
    """The SR-3 degrade, and the rate cap answered the same way the sweep's is."""
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        proposal_id = await repository.open_proposal(
            db,
            workspace_id=workspace_id,
            prompt_id=prompt.id,
            finding_id=finding_id,
            remedy_kind=RemedyKind.CASE,
            remedy_family=None,
            candidate_body=None,
            gate_run_id=None,
            gate_delta=None,
            draft_rationale=None,
            rails_report=None,
            expires_at=now + PROPOSAL_TTL,
            now=now,
        )
    proposals_total.labels(
        remedy_family="note" if proposal_id is None else "case",
        disposition="opened" if proposal_id else "rate_capped",
    ).inc()
    if proposal_id is None:
        return _terminate(
            TerminationReason.RATE_CAPPED, finding_id=finding_id, drafted="false"
        )
    proposals_open.inc()
    return _terminate(
        TerminationReason.PROPOSAL_OPENED,
        finding_id=finding_id,
        proposal_id=proposal_id,
        drafted="false",
    )
