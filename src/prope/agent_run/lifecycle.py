from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.agent_run.domain import LifecyclePhase, NextAction
from prope.prompt_registry.domain import PromptRow, RevisionStatus

LATEST_EVAL = text("""
    SELECT id, status, pass_count, fail_count, error_count, finished_at
      FROM evaluation.eval_run
     WHERE prompt_id = :prompt_id AND version_id = :version_id AND role = 'candidate'
     ORDER BY id DESC
     LIMIT 1
""")
LATEST_APPROVAL = text("""
    SELECT decision
      FROM release.approval
     WHERE prompt_id = :prompt_id AND version_id = :version_id
     ORDER BY decided_at DESC, id DESC
     LIMIT 1
""")
OPEN_FINDINGS = text("""
    SELECT count(*)::integer
      FROM improvement.finding
     WHERE prompt_id = :prompt_id AND status = 'open'
""")
READINESS_COUNT = text("""
    SELECT jsonb_array_length(rendered_findings)::integer
      FROM readiness.report
     WHERE prompt_id = :prompt_id AND version_id = :version_id
""")


async def lifecycle_summary(
    db: AsyncSession, *, prompt: PromptRow, version_id: str, revision_status: RevisionStatus,
) -> dict[str, Any]:
    eval_row = (await db.execute(LATEST_EVAL, {
        "prompt_id": prompt.id, "version_id": version_id,
    })).mappings().first()
    approval = (await db.execute(LATEST_APPROVAL, {
        "prompt_id": prompt.id, "version_id": version_id,
    })).scalar_one_or_none()
    finding_count = int(await db.scalar(OPEN_FINDINGS, {"prompt_id": prompt.id}) or 0)
    readiness_count = await db.scalar(READINESS_COUNT, {
        "prompt_id": prompt.id, "version_id": version_id,
    })

    live = prompt.released_version_id == version_id
    eval_finished = eval_row is not None and eval_row["status"] in {"completed", "refused", "interrupted"}
    has_eval_failure = eval_finished and eval_row is not None and (
        eval_row["status"] in {"interrupted", "refused"}
        or eval_row["fail_count"] > 0
        or eval_row["error_count"] > 0
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
        total = eval_row["pass_count"] + eval_row["fail_count"] + eval_row["error_count"]
        last_eval = {
            "run_id": eval_row["id"], "status": eval_row["status"],
            "passed": eval_row["pass_count"], "failed": eval_row["fail_count"],
            "errors": eval_row["error_count"], "total": total,
            "finished_at": eval_row["finished_at"],
        }

    return {
        "prompt_id": prompt.id, "version_id": version_id, "phase": phase,
        "live_version_id": prompt.released_version_id, "last_eval": last_eval,
        "approval_status": str(approval or revision_status.value),
        "open_finding_count": finding_count,
        "readiness_attention_count": None if readiness_count is None else int(readiness_count),
        "next_action": next_action,
    }
