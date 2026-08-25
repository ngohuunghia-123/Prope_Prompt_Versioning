from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from prope.agent_run.domain import LifecyclePhase, NextAction
from prope.evaluation.seams import latest_candidate_run
from prope.prompt_improvement.seams import open_finding_count
from prope.prompt_readiness.seams import count_frozen_findings
from prope.prompt_registry.domain import PromptRow, RevisionStatus
from prope.release_control.seams import latest_decision


async def lifecycle_summary(
    db: AsyncSession, *, prompt: PromptRow, version_id: str, revision_status: RevisionStatus,
) -> dict[str, Any]:
    eval_row = await latest_candidate_run(db, prompt_id=prompt.id, version_id=version_id)
    approval = await latest_decision(db, prompt_id=prompt.id, version_id=version_id)
    finding_count = await open_finding_count(
        db, workspace_id=prompt.workspace_id, prompt_id=prompt.id
    )
    readiness_count = await count_frozen_findings(
        db, workspace_id=prompt.workspace_id, version_id=version_id
    )

    live = prompt.released_version_id == version_id
    eval_finished = eval_row is not None and eval_row.status in {"completed", "refused", "interrupted"}
    has_eval_failure = eval_finished and eval_row is not None and (
        eval_row.status in {"interrupted", "refused"}
        or eval_row.fail_count > 0
        or eval_row.error_count > 0
    )

    if live and finding_count:
        phase, next_action = LifecyclePhase.ATTENTION, NextAction.VIEW_IMPROVEMENTS
    elif live:
        phase, next_action = LifecyclePhase.LIVE, NextAction.VIEW_ACTIVITY
    elif not eval_finished:
        phase, next_action = LifecyclePhase.DRAFT, NextAction.RUN_EVALUATION
    elif has_eval_failure:
        phase, next_action = LifecyclePhase.ATTENTION, NextAction.EDIT_PROMPT
    elif revision_status is RevisionStatus.DRAFT:
        phase, next_action = LifecyclePhase.EVALUATED, NextAction.SUBMIT_REVIEW
    elif revision_status is RevisionStatus.IN_REVIEW:
        phase, next_action = LifecyclePhase.WAITING_REVIEW, NextAction.VIEW_RELEASE
    else:
        phase, next_action = LifecyclePhase.APPROVED, NextAction.RELEASE

    last_eval = None
    if eval_row is not None:
        total = eval_row.pass_count + eval_row.fail_count + eval_row.error_count
        last_eval = {
            "run_id": eval_row.run_id, "status": eval_row.status,
            "passed": eval_row.pass_count, "failed": eval_row.fail_count,
            "errors": eval_row.error_count, "total": total,
            "finished_at": eval_row.finished_at,
        }

    return {
        "prompt_id": prompt.id, "version_id": version_id, "phase": phase,
        "live_version_id": prompt.released_version_id, "last_eval": last_eval,
        "approval_status": str(approval or revision_status.value),
        "open_finding_count": finding_count,
        "readiness_attention_count": None if readiness_count is None else int(readiness_count),
        "next_action": next_action,
    }
