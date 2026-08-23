from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

READ = text("""
    SELECT call_id, verdict, categories, correction, note
      FROM registry.call_annotation
     WHERE workspace_id = :workspace_id AND call_id = ANY(:call_ids)
""")
UPSERT = text("""
    INSERT INTO registry.call_annotation
        (workspace_id, call_id, prompt_id, verdict, categories, correction, note,
         annotated_by, created_at, updated_at)
    VALUES
        (:workspace_id, :call_id, :prompt_id, :verdict, :categories, :correction,
         :note, :actor_id, :now, :now)
    ON CONFLICT (workspace_id, call_id) DO UPDATE SET
        verdict = EXCLUDED.verdict, categories = EXCLUDED.categories,
        correction = EXCLUDED.correction, note = EXCLUDED.note,
        annotated_by = EXCLUDED.annotated_by, updated_at = EXCLUDED.updated_at
""")


async def read_annotations(
    db: AsyncSession, workspace_id: str, call_ids: list[str]
) -> dict[str, dict[str, Any]]:
    if not call_ids:
        return {}
    rows = (
        (
            await db.execute(
                READ, {"workspace_id": workspace_id, "call_ids": call_ids}
            )
        )
        .mappings()
        .all()
    )
    return {str(row["call_id"]): dict(row) for row in rows}


async def upsert_annotation(
    db: AsyncSession,
    *,
    workspace_id: str,
    call_id: str,
    prompt_id: str,
    verdict: str,
    categories: list[str],
    correction: str,
    note: str,
    actor_id: str,
    now: datetime,
) -> None:
    await db.execute(
        UPSERT,
        {
            "workspace_id": workspace_id,
            "call_id": call_id,
            "prompt_id": prompt_id,
            "verdict": verdict,
            "categories": categories,
            "correction": correction,
            "note": note,
            "actor_id": actor_id,
            "now": now,
        },
    )
