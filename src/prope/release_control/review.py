from dataclasses import dataclass, field
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from prope.evaluation.seams import CostDelta, ReviewSummary, get_review_summary
from prope.prompt_registry.seams import (
    DiffResult,
    PromptRow,
    RevisionRead,
    get_diff,
    get_revision,
    list_revision_chain,
)
from prope.property_history.domain import HistoryEvent, PromptScope
from prope.property_history.read import read as read_history
from prope.release_control import repository
from prope.release_control.domain import (
    ApprovalRow,
    CostEvidence,
    EvidenceDigest,
    ReviewTaskRow,
    SuiteEvidence,
)
from prope.release_control.observability import summary_unavailable_total

log = structlog.get_logger(__name__)

__all__ = [
    "HISTORY_PAGE",
    "ReviewScreen",
    "acknowledgement_is_required",
    "capture_evidence",
    "compose_review",
    "pull_review_summary",
]

HISTORY_PAGE = 20


@dataclass(frozen=True, slots=True)
class ReviewScreen:
    prompt: PromptRow
    revision: RevisionRead
    diff: DiffResult | None
    diff_against_version_id: str | None
    summary: ReviewSummary | None
    summary_available: bool
    acknowledgement_required: bool
    self_authored: bool
    released_version_id: str | None
    latest_revision_number: int
    revisions_since: int
    approvals: tuple[ApprovalRow, ...] = field(default_factory=tuple)
    review_task: ReviewTaskRow | None = None
    history: tuple[HistoryEvent, ...] = field(default_factory=tuple)


async def pull_review_summary(
    db: AsyncSession, prompt_id: str, version_id: str
) -> tuple[ReviewSummary | None, bool]:
    try:
        summary = await get_review_summary(db, prompt_id, version_id)
    except Exception as error:
        summary_unavailable_total.inc()
        log.warning(
            "release_control.summary_unavailable",
            prompt_id=prompt_id,
            version_id=version_id,
            reason=type(error).__name__,
        )
        return None, False
    return summary, True


def capture_evidence(
    *, version_id: str, summary: ReviewSummary | None, available: bool, now: datetime
) -> EvidenceDigest:
    if summary is None:
        return EvidenceDigest(
            version_id=version_id,
            captured_at=now,
            summary_available=available,
            requires_acknowledgement=True,
        )

    return EvidenceDigest(
        version_id=version_id,
        captured_at=now,
        summary_available=available,
        requires_acknowledgement=summary.requires_acknowledgement,
        suites=tuple(
            SuiteEvidence(
                suite_id=suite.suite_id,
                suite_name=suite.suite_name,
                suite_version=suite.suite_version,
                run_id=suite.run_id,
                status=str(suite.status),
                pass_count=suite.pass_count,
                fail_count=suite.fail_count,
                error_count=suite.error_count,
                case_count=suite.case_count,
                baseline_run_id=suite.baseline_run_id,
                baseline_ran_at=suite.baseline_ran_at,
                cost_delta=_cost(suite.cost_delta),
            )
            for suite in summary.suites
        ),
        total_cost_delta=_cost(summary.total_cost_delta),
    )


def acknowledgement_is_required(summary: ReviewSummary | None, available: bool) -> bool:
    if not available or summary is None:
        return True
    return summary.requires_acknowledgement


async def compose_review(
    db: AsyncSession,
    *,
    actor_id: str,
    prompt: PromptRow,
    revision: RevisionRead,
) -> ReviewScreen:
    summary, available = await pull_review_summary(db, prompt.id, revision.version_id)

    baseline, diff = await _diff_against(db, prompt=prompt, revision=revision)

    chain = await list_revision_chain(db, prompt.id, limit=1)
    latest_revision_number = chain[0].revision_number if chain else revision.revision_number

    approvals = await repository.list_approvals(db, revision.version_id)
    task = await repository.open_review_task(db, prompt.id)
    history = await read_history(
        db,
        PromptScope(workspace_id=prompt.workspace_id, scope_prompt_id=prompt.id),
        limit=HISTORY_PAGE,
    )

    return ReviewScreen(
        prompt=prompt,
        revision=revision,
        diff=diff,
        diff_against_version_id=None if baseline is None else baseline.version_id,
        summary=summary,
        summary_available=available,
        acknowledgement_required=acknowledgement_is_required(summary, available),
        self_authored=revision.author_id == actor_id,
        released_version_id=prompt.released_version_id,
        latest_revision_number=latest_revision_number,
        revisions_since=max(0, latest_revision_number - revision.revision_number),
        approvals=approvals,
        review_task=task if task is not None and task.version_id == revision.version_id else None,
        history=history,
    )


async def _diff_against(
    db: AsyncSession, *, prompt: PromptRow, revision: RevisionRead
) -> tuple[RevisionRead | None, DiffResult | None]:
    baseline: RevisionRead | None = None

    if (
        prompt.released_version_id is not None
        and prompt.released_version_id != revision.version_id
    ):
        baseline = await get_revision(db, prompt.released_version_id)

    if baseline is None:
        preceding = await list_revision_chain(
            db, prompt.id, cursor=revision.revision_number, limit=1
        )
        baseline = preceding[0] if preceding else None

    if baseline is None:
        return None, None

    return baseline, get_diff(baseline, revision)


def _cost(delta: CostDelta | None) -> CostEvidence | None:
    if delta is None:
        return None
    return CostEvidence(
        input_tokens=delta.input_tokens,
        output_tokens=delta.output_tokens,
        cost=delta.cost,
        currency=delta.currency,
        ratio=delta.ratio,
    )
