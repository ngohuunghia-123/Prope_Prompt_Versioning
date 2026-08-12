"""INT-016 / A-091 — discovered, refreshable, manually extensible, and priceless."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.provider_access.domain import CatalogueEntry, CatalogueSource
from prope.provider_access.observability import catalogue_refresh_total

__all__ = [
    "MODEL_ID_PREFIX",
    "add_manual_model",
    "get_model_catalogue",
    "store_discovered",
]

MODEL_ID_PREFIX = "mdl_"

LIST_CATALOGUE = text(
    """
    SELECT model_id, display_name, supports_streaming, available, source
    FROM   provider.model_catalogue
    WHERE  provider_config_id = :provider_config_id
    ORDER  BY model_id
    """
)

UPSERT_MODEL = text(
    """
    INSERT INTO provider.model_catalogue (
        id, workspace_id, provider_config_id, model_id, display_name, source,
        supports_streaming, available, first_seen_at, last_seen_at
    ) VALUES (
        :id, :workspace_id, :provider_config_id, :model_id, :display_name, :source,
        :supports_streaming, true, :now, :now
    )
    ON CONFLICT (provider_config_id, model_id) DO UPDATE
       SET display_name = coalesce(EXCLUDED.display_name, provider.model_catalogue.display_name),
           available    = true,
           last_seen_at = EXCLUDED.last_seen_at
    """
)

INSERT_MANUAL_MODEL = text(
    """
    INSERT INTO provider.model_catalogue (
        id, workspace_id, provider_config_id, model_id, display_name, source,
        supports_streaming, available, first_seen_at, last_seen_at
    ) VALUES (
        :id, :workspace_id, :provider_config_id, :model_id, :display_name, 'manual',
        :supports_streaming, true, :now, :now
    )
    ON CONFLICT (provider_config_id, model_id) DO NOTHING
    """
)

MARK_MISSING_UNAVAILABLE = text(
    """
    UPDATE provider.model_catalogue
       SET available = false
     WHERE provider_config_id = :provider_config_id
       AND source = 'discovered'
       AND NOT (model_id = ANY(:model_ids))
    """
)


async def get_model_catalogue(
    db: AsyncSession, provider_config_id: str
) -> tuple[CatalogueEntry, ...]:
    rows = (await db.execute(LIST_CATALOGUE, {"provider_config_id": provider_config_id})).all()
    return tuple(
        CatalogueEntry(
            model_id=row.model_id,
            display_name=row.display_name,
            supports_streaming=row.supports_streaming,
            available=row.available,
            source=CatalogueSource(row.source),
        )
        for row in rows
    )


async def store_discovered(
    db: AsyncSession,
    *,
    workspace_id: str,
    provider_config_id: str,
    models: Sequence[CatalogueEntry],
    now: datetime,
) -> int:
    for entry in models:
        await db.execute(
            UPSERT_MODEL,
            {
                "id": f"{MODEL_ID_PREFIX}{ULID()}",
                "workspace_id": workspace_id,
                "provider_config_id": provider_config_id,
                "model_id": entry.model_id,
                "display_name": entry.display_name,
                "source": CatalogueSource.DISCOVERED.value,
                "supports_streaming": entry.supports_streaming,
                "now": now,
            },
        )

    await db.execute(
        MARK_MISSING_UNAVAILABLE,
        {
            "provider_config_id": provider_config_id,
            "model_ids": [entry.model_id for entry in models],
        },
    )
    catalogue_refresh_total.labels(result="ok" if models else "empty").inc()
    return len(models)


async def add_manual_model(
    db: AsyncSession,
    *,
    workspace_id: str,
    provider_config_id: str,
    model_id: str,
    display_name: str | None,
    supports_streaming: bool,
    now: datetime,
) -> bool:
    result = await db.execute(
        INSERT_MANUAL_MODEL,
        {
            "id": f"{MODEL_ID_PREFIX}{ULID()}",
            "workspace_id": workspace_id,
            "provider_config_id": provider_config_id,
            "model_id": model_id,
            "display_name": display_name,
            "supports_streaming": supports_streaming,
            "now": now,
        },
    )
    return result.rowcount > 0
