from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.prompt_ingestion.domain import ItemSnapshot, ParsedCandidate
from prope.prompt_ingestion.parsers import source_hash

BATCH_PREFIX = "imb_"
ITEM_PREFIX = "imi_"
PROPOSAL_PREFIX = "iap_"

INSERT_BATCH = text(
    """
    INSERT INTO ingestion.import_batch
        (id, workspace_id, actor_id, mode, status, default_namespace,
         default_access_level, field_mapping, review_version, created_at, updated_at, expires_at)
    VALUES
        (:id, :workspace_id, :actor_id, :mode, 'processing', :namespace,
         :access_level, CAST(:mapping AS jsonb), 1, :now, :now, :expires_at)
    """
)
INSERT_ITEM = text(
    """
    INSERT INTO ingestion.import_item
        (id, batch_id, workspace_id, ordinal, source_filename, source_format,
         source_hash, source_text, title, purpose, namespace, name, tags,
         change_summary, target_prompt_id, resolution, state, created_at, updated_at)
    VALUES
        (:id, :batch_id, :workspace_id, :ordinal, :filename, :format,
         :hash, :source, :title, :purpose, :namespace, :name, :tags,
         :summary, :target_prompt_id,
         CASE WHEN :target_prompt_id IS NULL THEN NULL ELSE 'revise' END,
         'parsed', :now, :now)
    """
)
SELECT_BATCH = text(
    """
    SELECT b.*,
           count(i.id)::integer AS item_count,
           count(i.id) FILTER (WHERE i.state = 'ready')::integer AS ready_count,
           count(i.id) FILTER (WHERE i.state = 'committed')::integer AS committed_count,
           count(i.id) FILTER (WHERE i.state IN ('failed', 'needs_attention'))::integer AS error_count
    FROM ingestion.import_batch b
    LEFT JOIN ingestion.import_item i ON i.batch_id = b.id
    WHERE b.id = :id AND b.actor_id = :actor_id
    GROUP BY b.id
    """
)
SELECT_BATCH_INTERNAL = text("SELECT * FROM ingestion.import_batch WHERE id = :id")
LIST_ITEMS = text(
    """
    SELECT * FROM ingestion.import_item
    WHERE batch_id = :batch_id
      AND (:state IS NULL OR state = :state)
      AND (:cursor IS NULL OR ordinal > :cursor)
    ORDER BY ordinal
    LIMIT :limit
    """
)
SELECT_ITEM = text("SELECT * FROM ingestion.import_item WHERE id = :id AND batch_id = :batch_id")
CLAIM_ITEM = text(
    """
    SELECT id
    FROM ingestion.import_item
    WHERE state IN ('parsed', 'retryable')
      AND attempts < :max_attempts
      AND (lease_until IS NULL OR lease_until < :now)
    ORDER BY created_at, ordinal
    FOR UPDATE SKIP LOCKED
    LIMIT 1
    """
)
SET_CLAIMED = text(
    """
    UPDATE ingestion.import_item
    SET state = 'converting', attempts = attempts + 1, lease_until = :lease_until,
        error_code = NULL, item_version = item_version + 1, updated_at = :now
    WHERE id = :id
    RETURNING *
    """
)
SET_CONVERTED = text(
    """
    UPDATE ingestion.import_item
    SET canonical_body = :body, conversion_model = :model,
        conversion_schema_version = :schema_version, state = 'duplicate_check',
        item_version = item_version + 1, updated_at = :now
    WHERE id = :id
    """
)
SET_READY = text(
    """
    UPDATE ingestion.import_item
    SET semantic_matches = CAST(:matches AS jsonb), target_prompt_id = :target_prompt_id,
        base_version_id = :base_version_id,
        resolution = CASE
            WHEN :target_prompt_id IS NOT NULL THEN 'revise'
            WHEN jsonb_array_length(CAST(:matches AS jsonb)) = 0 THEN 'create'
            ELSE resolution
        END,
        state = 'ready', lease_until = NULL, error_code = NULL,
        item_version = item_version + 1, updated_at = :now
    WHERE id = :id
    """
)
SET_FAILURE = text(
    """
    UPDATE ingestion.import_item
    SET state = :state, error_code = :error_code, lease_until = NULL,
        item_version = item_version + 1, updated_at = :now
    WHERE id = :id
    """
)
TOUCH_BATCH = text(
    """
    UPDATE ingestion.import_batch
    SET review_version = review_version + 1, updated_at = :now
    WHERE id = :batch_id
    """
)
REFRESH_BATCH = text(
    """
    UPDATE ingestion.import_batch b
    SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM ingestion.import_item i
                WHERE i.batch_id = b.id
                  AND i.state IN ('parsed', 'converting', 'duplicate_check', 'retryable')
            ) THEN 'processing'
            ELSE 'review_ready'
        END,
        updated_at = :now
    WHERE id = :batch_id AND status NOT IN ('committing', 'completed', 'completed_with_errors', 'expired')
    """
)
UPDATE_ITEM = text(
    """
    UPDATE ingestion.import_item
    SET title = coalesce(:title, title), purpose = coalesce(:purpose, purpose),
        namespace = coalesce(:namespace, namespace), name = coalesce(:name, name),
        tags = coalesce(:tags, tags), change_summary = coalesce(:change_summary, change_summary),
        resolution = coalesce(:resolution, resolution),
        target_prompt_id = CASE WHEN :target_supplied THEN :target_prompt_id ELSE target_prompt_id END,
        base_version_id = CASE WHEN :target_supplied THEN :base_version_id ELSE base_version_id END,
        state = CASE
            WHEN :resolution = 'skip' THEN 'skipped'
            WHEN state = 'skipped' AND :resolution IN ('create', 'revise') THEN 'ready'
            ELSE state
        END,
        item_version = item_version + 1, updated_at = :now
    WHERE id = :id AND batch_id = :batch_id AND item_version = :expected_version
    RETURNING *
    """
)
RETRY_ITEMS = text(
    """
    UPDATE ingestion.import_item
    SET state = 'retryable', attempts = 0, error_code = NULL, lease_until = NULL,
        item_version = item_version + 1, updated_at = :now
    WHERE batch_id = :batch_id AND id = ANY(:item_ids)
      AND state IN ('retryable', 'failed')
    RETURNING id
    """
)
SELECT_PROPOSAL_ITEMS = text(
    """
    SELECT id, item_version, resolution, target_prompt_id, base_version_id,
           title, namespace, name, state
    FROM ingestion.import_item
    WHERE batch_id = :batch_id AND id = ANY(:item_ids)
    ORDER BY ordinal
    """
)
INSERT_PROPOSAL = text(
    """
    INSERT INTO ingestion.commit_proposal
        (id, batch_id, workspace_id, actor_id, expected_review_version,
         item_snapshot, preview, status, created_at)
    VALUES
        (:id, :batch_id, :workspace_id, :actor_id, :version,
         CAST(:snapshot AS jsonb), CAST(:preview AS jsonb), 'pending', :now)
    """
)
SELECT_PROPOSAL = text(
    "SELECT * FROM ingestion.commit_proposal WHERE id = :id AND actor_id = :actor_id"
)
SET_PROPOSAL = text(
    """
    UPDATE ingestion.commit_proposal
    SET status = :status, decided_at = :now
    WHERE id = :id AND actor_id = :actor_id AND status = 'pending'
    RETURNING id
    """
)
SET_BATCH_COMMITTING = text(
    """
    UPDATE ingestion.import_batch
    SET status = 'committing', updated_at = :now
    WHERE id = :id AND review_version = :review_version AND status = 'review_ready'
    RETURNING id
    """
)
SET_ITEM_COMMITTING = text(
    """
    UPDATE ingestion.import_item
    SET state = 'committing', item_version = item_version + 1, updated_at = :now
    WHERE id = :id AND item_version = :item_version AND state = 'ready'
    RETURNING *
    """
)
SET_ITEM_COMMITTED = text(
    """
    UPDATE ingestion.import_item
    SET state = 'committed', result_prompt_id = :prompt_id, result_version_id = :version_id,
        item_version = item_version + 1, updated_at = :now
    WHERE id = :id
    """
)
FINALIZE_BATCH = text(
    """
    UPDATE ingestion.import_batch b
    SET status = CASE WHEN EXISTS (
            SELECT 1 FROM ingestion.import_item i
            WHERE i.batch_id = b.id AND i.state IN ('failed', 'needs_attention', 'ready')
        ) THEN 'completed_with_errors' ELSE 'completed' END,
        completed_at = :now, updated_at = :now, expires_at = :expires_at
    WHERE id = :batch_id
    """
)
PURGE_EXPIRED = text(
    "DELETE FROM ingestion.import_batch WHERE expires_at < :now RETURNING id"
)


async def create_batch(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    mode: str,
    namespace: str,
    access_level: str,
    mapping: dict[str, str],
    candidates: list[ParsedCandidate],
    now: datetime,
    expires_at: datetime,
) -> str:
    batch_id = f"{BATCH_PREFIX}{ULID()}"
    await db.execute(
        INSERT_BATCH,
        {
            "id": batch_id,
            "workspace_id": workspace_id,
            "actor_id": actor_id,
            "mode": mode,
            "namespace": namespace,
            "access_level": access_level,
            "mapping": json.dumps(mapping),
            "now": now,
            "expires_at": expires_at,
        },
    )
    for ordinal, candidate in enumerate(candidates):
        await db.execute(
            INSERT_ITEM,
            {
                "id": f"{ITEM_PREFIX}{ULID()}",
                "batch_id": batch_id,
                "workspace_id": workspace_id,
                "ordinal": ordinal,
                "filename": candidate.source_filename,
                "format": candidate.source_format,
                "hash": source_hash(candidate),
                "source": candidate.source_text,
                "title": candidate.title,
                "purpose": candidate.purpose,
                "namespace": candidate.namespace,
                "name": candidate.name,
                "tags": list(candidate.tags),
                "summary": candidate.change_summary,
                "target_prompt_id": candidate.target_prompt_id,
                "now": now,
            },
        )
    return batch_id


async def load_batch(db: AsyncSession, batch_id: str, *, actor_id: str) -> dict[str, Any] | None:
    row = (await db.execute(SELECT_BATCH, {"id": batch_id, "actor_id": actor_id})).mappings().first()
    return dict(row) if row else None


async def load_batch_internal(db: AsyncSession, batch_id: str) -> dict[str, Any] | None:
    row = (await db.execute(SELECT_BATCH_INTERNAL, {"id": batch_id})).mappings().first()
    return dict(row) if row else None


async def list_items(db: AsyncSession, batch_id: str, *, state: str | None, cursor: int | None, limit: int) -> list[dict[str, Any]]:
    rows = (await db.execute(LIST_ITEMS, {"batch_id": batch_id, "state": state, "cursor": cursor, "limit": limit})).mappings().all()
    return [dict(row) for row in rows]


async def load_item(db: AsyncSession, batch_id: str, item_id: str) -> dict[str, Any] | None:
    row = (await db.execute(SELECT_ITEM, {"batch_id": batch_id, "id": item_id})).mappings().first()
    return dict(row) if row else None


async def claim_item(db: AsyncSession, *, now: datetime, lease_until: datetime, max_attempts: int) -> dict[str, Any] | None:
    item_id = await db.scalar(CLAIM_ITEM, {"now": now, "max_attempts": max_attempts})
    if item_id is None:
        return None
    row = (await db.execute(SET_CLAIMED, {"id": item_id, "now": now, "lease_until": lease_until})).mappings().one()
    return dict(row)


async def set_converted(db: AsyncSession, item_id: str, *, body: str, model: str, schema_version: str, now: datetime) -> None:
    await db.execute(SET_CONVERTED, {"id": item_id, "body": body, "model": model, "schema_version": schema_version, "now": now})


async def set_ready(db: AsyncSession, item_id: str, *, matches: list[dict[str, Any]], target_prompt_id: str | None, base_version_id: str | None, now: datetime) -> None:
    await db.execute(SET_READY, {"id": item_id, "matches": json.dumps(matches), "target_prompt_id": target_prompt_id, "base_version_id": base_version_id, "now": now})


async def set_failure(db: AsyncSession, item_id: str, *, state: str, error_code: str, now: datetime) -> None:
    await db.execute(SET_FAILURE, {"id": item_id, "state": state, "error_code": error_code, "now": now})


async def touch_batch(db: AsyncSession, batch_id: str, *, now: datetime) -> None:
    await db.execute(TOUCH_BATCH, {"batch_id": batch_id, "now": now})


async def refresh_batch(db: AsyncSession, batch_id: str, *, now: datetime) -> None:
    await db.execute(REFRESH_BATCH, {"batch_id": batch_id, "now": now})


async def update_item(db: AsyncSession, batch_id: str, item_id: str, *, expected_version: int, values: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    target_supplied = "target_prompt_id" in values
    parameters = {
        "id": item_id,
        "batch_id": batch_id,
        "expected_version": expected_version,
        "title": values.get("title"),
        "purpose": values.get("purpose"),
        "namespace": values.get("namespace"),
        "name": values.get("name"),
        "tags": values.get("tags"),
        "change_summary": values.get("change_summary"),
        "resolution": values.get("resolution"),
        "target_supplied": target_supplied,
        "target_prompt_id": values.get("target_prompt_id"),
        "base_version_id": values.get("base_version_id"),
        "now": now,
    }
    row = (await db.execute(UPDATE_ITEM, parameters)).mappings().first()
    return dict(row) if row else None


async def retry_items(db: AsyncSession, batch_id: str, item_ids: list[str], *, now: datetime) -> list[str]:
    return list((await db.execute(RETRY_ITEMS, {"batch_id": batch_id, "item_ids": item_ids, "now": now})).scalars().all())


async def create_proposal(db: AsyncSession, *, batch: dict[str, Any], actor_id: str, item_ids: list[str], now: datetime) -> dict[str, Any]:
    rows = (await db.execute(SELECT_PROPOSAL_ITEMS, {"batch_id": batch["id"], "item_ids": item_ids})).mappings().all()
    if len(rows) != len(set(item_ids)):
        raise ValueError("unknown import item")
    snapshots = [
        asdict(
            ItemSnapshot(
                row["id"],
                row["item_version"],
                row["resolution"] or "",
                row["target_prompt_id"],
                row["base_version_id"],
            )
        )
        for row in rows
    ]
    if any(row["state"] != "ready" for row in rows) or any(
        not snapshot["resolution"] or snapshot["resolution"] == "skip"
        for snapshot in snapshots
    ):
        raise ValueError("selected items must be create or revise")
    proposal_id = f"{PROPOSAL_PREFIX}{ULID()}"
    preview = {
        "item_count": len(rows),
        "create_count": sum(row["resolution"] == "create" for row in rows),
        "revise_count": sum(row["resolution"] == "revise" for row in rows),
        "items": [{"id": row["id"], "title": row["title"], "model_name": f"{row['namespace']}/{row['name']}"} for row in rows[:10]],
    }
    await db.execute(INSERT_PROPOSAL, {"id": proposal_id, "batch_id": batch["id"], "workspace_id": batch["workspace_id"], "actor_id": actor_id, "version": batch["review_version"], "snapshot": json.dumps(snapshots), "preview": json.dumps(preview), "now": now})
    return {"id": proposal_id, "batch_id": batch["id"], "status": "pending", "preview": preview, "expected_review_version": batch["review_version"]}


async def load_proposal(db: AsyncSession, proposal_id: str, *, actor_id: str) -> dict[str, Any] | None:
    row = (await db.execute(SELECT_PROPOSAL, {"id": proposal_id, "actor_id": actor_id})).mappings().first()
    return dict(row) if row else None


async def settle_proposal(db: AsyncSession, proposal_id: str, *, actor_id: str, status: str, now: datetime) -> bool:
    return (await db.scalar(SET_PROPOSAL, {"id": proposal_id, "actor_id": actor_id, "status": status, "now": now})) is not None


async def start_batch_commit(db: AsyncSession, batch_id: str, *, review_version: int, now: datetime) -> bool:
    return (await db.scalar(SET_BATCH_COMMITTING, {"id": batch_id, "review_version": review_version, "now": now})) is not None


async def start_item_commit(db: AsyncSession, snapshot: dict[str, Any], *, now: datetime) -> dict[str, Any] | None:
    row = (await db.execute(SET_ITEM_COMMITTING, {"id": snapshot["item_id"], "item_version": snapshot["item_version"], "now": now})).mappings().first()
    return dict(row) if row else None


async def mark_committed(db: AsyncSession, item_id: str, *, prompt_id: str, version_id: str, now: datetime) -> None:
    await db.execute(SET_ITEM_COMMITTED, {"id": item_id, "prompt_id": prompt_id, "version_id": version_id, "now": now})


async def finalize_batch(
    db: AsyncSession, batch_id: str, *, now: datetime, expires_at: datetime
) -> None:
    await db.execute(
        FINALIZE_BATCH,
        {"batch_id": batch_id, "now": now, "expires_at": expires_at},
    )


async def purge_expired(db: AsyncSession, *, now: datetime) -> int:
    return len((await db.execute(PURGE_EXPIRED, {"now": now})).scalars().all())
