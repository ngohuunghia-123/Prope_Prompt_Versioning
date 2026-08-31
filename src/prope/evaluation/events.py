from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft

__all__ = [
    "EVAL_RUN_TARGET_TYPE",
    "EVAL_SUITE_TARGET_TYPE",
    "eval_run_completed",
    "eval_run_interrupted",
    "eval_run_started",
    "eval_suite_updated",
]

EVAL_SUITE_TARGET_TYPE = "eval_suite"

EVAL_RUN_TARGET_TYPE = "eval_run"


async def _append(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_type: ActorType,
    actor_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    prompt_id: str,
    occurred_at: datetime,
) -> str:
    return await append(
        db,
        HistoryEventDraft(
            workspace_id=workspace_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            scope_prompt_id=prompt_id,
            occurred_at=occurred_at,
        ),
    )


async def eval_suite_updated(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    suite_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        action="eval_suite_updated",
        target_type=EVAL_SUITE_TARGET_TYPE,
        target_id=suite_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def eval_run_started(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    run_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        action="eval_run_started",
        target_type=EVAL_RUN_TARGET_TYPE,
        target_id=run_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def eval_run_completed(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str | None,
    prompt_id: str,
    run_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_type=ActorType.SYSTEM,
        actor_id=actor_id,
        action="eval_run_completed",
        target_type=EVAL_RUN_TARGET_TYPE,
        target_id=run_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def eval_run_interrupted(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str | None,
    prompt_id: str,
    run_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_type=ActorType.SYSTEM,
        actor_id=actor_id,
        action="eval_run_interrupted",
        target_type=EVAL_RUN_TARGET_TYPE,
        target_id=run_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def eval_run_cancelled(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    run_id: str,
    occurred_at: datetime,
) -> str:
    """A person pressed cancel. The history must say who, not blame the system."""
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        action="eval_run_cancelled",
        target_type=EVAL_RUN_TARGET_TYPE,
        target_id=run_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )
