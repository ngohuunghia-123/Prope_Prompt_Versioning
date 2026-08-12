from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft

__all__ = [
    "RELEASE_TARGET_TYPE",
    "REVIEW_TASK_TARGET_TYPE",
    "REVISION_TARGET_TYPE",
    "release_withdrawn",
    "review_task_closed",
    "revision_approved",
    "revision_break_glass_released",
    "revision_changes_requested",
    "revision_released",
    "revision_restored",
    "revision_submitted",
]

REVISION_TARGET_TYPE = "revision"

RELEASE_TARGET_TYPE = "release"

REVIEW_TASK_TARGET_TYPE = "review_task"


async def _append(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    prompt_id: str,
    occurred_at: datetime,
    reason: str | None = None,
    details: dict[str, object] | None = None,
) -> str:
    return await append(
        db,
        HistoryEventDraft(
            workspace_id=workspace_id,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            scope_prompt_id=prompt_id,
            reason=reason,
            details={} if details is None else details,
            occurred_at=occurred_at,
        ),
    )


async def revision_submitted(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    version_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="revision_submitted",
        target_type=REVISION_TARGET_TYPE,
        target_id=version_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def revision_approved(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    version_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="revision_approved",
        target_type=REVISION_TARGET_TYPE,
        target_id=version_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def revision_changes_requested(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    version_id: str,
    reason: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="revision_changes_requested",
        target_type=REVISION_TARGET_TYPE,
        target_id=version_id,
        prompt_id=prompt_id,
        reason=reason,
        occurred_at=occurred_at,
    )


async def revision_released(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    version_id: str,
    previous_version_id: str | None,
    break_glass: bool,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="revision_released",
        target_type=REVISION_TARGET_TYPE,
        target_id=version_id,
        prompt_id=prompt_id,
        details={
            "version_id": version_id,
            "previous_version_id": previous_version_id,
            "break_glass": break_glass,
        },
        occurred_at=occurred_at,
    )


async def revision_restored(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    version_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="revision_restored",
        target_type=REVISION_TARGET_TYPE,
        target_id=version_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def revision_break_glass_released(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    version_id: str,
    reason: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="revision_break_glass_released",
        target_type=REVISION_TARGET_TYPE,
        target_id=version_id,
        prompt_id=prompt_id,
        reason=reason,
        occurred_at=occurred_at,
    )


async def release_withdrawn(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    release_id: str,
    reason: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="release_withdrawn",
        target_type=RELEASE_TARGET_TYPE,
        target_id=release_id,
        prompt_id=prompt_id,
        reason=reason,
        occurred_at=occurred_at,
    )


async def review_task_closed(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    task_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="review_task_closed",
        target_type=REVIEW_TASK_TARGET_TYPE,
        target_id=task_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )
