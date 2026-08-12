"""The four history events this module writes, appended in the caller's transaction."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft

__all__ = [
    "credential_rotated",
    "provider_configured",
    "provider_disabled",
    "provider_updated",
]

TARGET_TYPE = "provider_config"


async def _append(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    action: str,
    provider_config_id: str,
    occurred_at: datetime,
) -> str:
    return await append(
        db,
        HistoryEventDraft(
            workspace_id=workspace_id,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            action=action,
            target_type=TARGET_TYPE,
            target_id=provider_config_id,
            occurred_at=occurred_at,
        ),
    )


async def provider_configured(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    provider_config_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="provider_configured",
        provider_config_id=provider_config_id,
        occurred_at=occurred_at,
    )


async def provider_updated(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    provider_config_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="provider_updated",
        provider_config_id=provider_config_id,
        occurred_at=occurred_at,
    )


async def provider_disabled(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    provider_config_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="provider_disabled",
        provider_config_id=provider_config_id,
        occurred_at=occurred_at,
    )


async def credential_rotated(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    provider_config_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="credential_rotated",
        provider_config_id=provider_config_id,
        occurred_at=occurred_at,
    )
