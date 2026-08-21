from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aio_pika.abc import AbstractChannel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import (
    AccessLevel,
    Actor,
    ActorType,
    Subject,
    SubjectType,
    VisibleFilter,
    may,
    visible_subject_filter,
)
from prope.db.session import workspace_transaction
from prope.prompt_conversion.domain import InvalidAgentOutputError, InvalidSourceError
from prope.prompt_conversion.service import AgentUnavailableError, ConversionContext, convert_source
from prope.prompt_ingestion import repository
from prope.prompt_ingestion.domain import LEASE_DURATION, MAX_AUTOMATIC_ATTEMPTS, STAGING_RETENTION
from prope.prompt_registry import commands as registry_commands
from prope.prompt_registry import repository as registry_repository
from prope.prompt_registry.domain import RevisionDraft
from prope.prompt_registry.seams import get_prompt_by_model_name
from prope.prompt_search.seams import enqueue_index_job

DUPLICATE_LIMIT = 3
DUPLICATE_FLOOR = 0.55


def actor_for(workspace_id: str, actor_id: str) -> Actor:
    return Actor(type=ActorType.USER, id=actor_id, workspace_id=workspace_id)


def workspace_subject(workspace_id: str) -> Subject:
    return Subject(type=SubjectType.WORKSPACE, id=workspace_id, workspace_id=workspace_id)


def prompt_subject(row: Any) -> Subject:
    return Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
    )


async def may_create_batch(db: AsyncSession, *, workspace_id: str, actor_id: str) -> bool:
    return await may(db, actor_for(workspace_id, actor_id), Action.PROMPT_CREATE, workspace_subject(workspace_id))


async def _visible_target(db: AsyncSession, *, workspace_id: str, actor_id: str, prompt: Any) -> bool:
    return await may(db, actor_for(workspace_id, actor_id), Action.PROMPT_READ, prompt_subject(prompt))


async def _resolve_target(db: AsyncSession, item: dict[str, Any]) -> tuple[Any | None, str | None]:
    target = None
    if item["target_prompt_id"]:
        target = await registry_repository.load_prompt(db, item["target_prompt_id"])
    else:
        target = await get_prompt_by_model_name(db, item["namespace"], item["name"])
    if target is None:
        return None, None
    if not await _visible_target(
        db,
        workspace_id=item["workspace_id"],
        actor_id=item["actor_id"],
        prompt=target,
    ):
        raise PermissionError("ingestion_target_not_found")
    latest = await registry_repository.load_latest_revision(db, target.id)
    return target, None if latest is None else latest.version_id


async def _semantic_matches(
    db: AsyncSession,
    *,
    item: dict[str, Any],
    visible: VisibleFilter,
) -> list[dict[str, Any]]:
    from prope.prompt_search.agent.search import semantic_search

    results = await semantic_search(
        db=db,
        query=item["canonical_body"],
        workspace_id=item["workspace_id"],
        visible=visible,
        actor_id=item["actor_id"],
        cursor=None,
        limit=DUPLICATE_LIMIT,
    )
    return [
        {
            "prompt_id": result.prompt_id,
            "title": result.title,
            "purpose": result.purpose,
            "similarity": result.similarity,
        }
        for result in results
        if result.similarity is not None and result.similarity >= DUPLICATE_FLOOR
    ]


async def process_one_item(
    sessionmaker: async_sessionmaker[AsyncSession], workspace_id: str
) -> bool:
    now = datetime.now(UTC)
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        item = await repository.claim_item(
            db,
            now=now,
            lease_until=now + LEASE_DURATION,
            max_attempts=MAX_AUTOMATIC_ATTEMPTS,
        )
    if item is None:
        return False

    # The actor is persisted on the batch rather than duplicated on each item.
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        batch = await repository.load_batch_internal(db, item["batch_id"])
    if batch is None:
        return True
    item["actor_id"] = batch["actor_id"]

    try:
        body, model, schema_version = await convert_source(
            item["source_text"],
            item["source_format"],
            context=ConversionContext(
                workspace_id=workspace_id,
                actor_id=batch["actor_id"],
                prompt_id=item["target_prompt_id"],
            ),
        )
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            await repository.set_converted(
                db,
                item["id"],
                body=body,
                model=model,
                schema_version=schema_version,
                now=datetime.now(UTC),
            )
            item = await repository.load_item(db, item["batch_id"], item["id"])
            assert item is not None
            item["actor_id"] = batch["actor_id"]
            target, base_version_id = await _resolve_target(db, item)
            visible = await visible_subject_filter(
                db,
                actor_for(workspace_id, batch["actor_id"]),
                SubjectType.PROMPT,
            )
            matches = [] if target is not None else await _semantic_matches(db, item=item, visible=visible)
            await repository.set_ready(
                db,
                item["id"],
                matches=matches,
                target_prompt_id=None if target is None else target.id,
                base_version_id=base_version_id,
                now=datetime.now(UTC),
            )
            await repository.touch_batch(db, item["batch_id"], now=datetime.now(UTC))
            await repository.refresh_batch(db, item["batch_id"], now=datetime.now(UTC))
    except (InvalidSourceError, InvalidAgentOutputError) as error:
        await _fail_item(sessionmaker, workspace_id, item, type(error).__name__, terminal=True)
    except PermissionError as error:
        await _fail_item(sessionmaker, workspace_id, item, str(error), terminal=True)
    except AgentUnavailableError:
        await _fail_item(sessionmaker, workspace_id, item, "conversion_agent_unavailable")
    except Exception:
        await _fail_item(sessionmaker, workspace_id, item, "ingestion_processing_unavailable")
    return True


async def _fail_item(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    item: dict[str, Any],
    code: str,
    *,
    terminal: bool = False,
) -> None:
    state = "failed" if terminal or item["attempts"] >= MAX_AUTOMATIC_ATTEMPTS else "retryable"
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await repository.set_failure(db, item["id"], state=state, error_code=code, now=datetime.now(UTC))
        await repository.touch_batch(db, item["batch_id"], now=datetime.now(UTC))
        await repository.refresh_batch(db, item["batch_id"], now=datetime.now(UTC))


async def process_available_items(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    from prope.access_control.seams import list_workspace_ids

    processed = 0
    for workspace_id in await list_workspace_ids(sessionmaker):
        while await process_one_item(sessionmaker, workspace_id):
            processed += 1
    return processed


async def purge_expired_staging(
    sessionmaker: async_sessionmaker[AsyncSession], *, now: datetime | None = None
) -> int:
    from prope.access_control.seams import list_workspace_ids

    cutoff = now or datetime.now(UTC)
    deleted = 0
    for workspace_id in await list_workspace_ids(sessionmaker):
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            deleted += await repository.purge_expired(db, now=cutoff)
    return deleted


async def commit_proposal(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace_id: str,
    actor_id: str,
    proposal: dict[str, Any],
    channel: AbstractChannel | None,
) -> tuple[int, int]:
    committed = 0
    conflicts = 0
    now = datetime.now(UTC)
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        started = await repository.start_batch_commit(
            db,
            proposal["batch_id"],
            review_version=proposal["expected_review_version"],
            now=now,
        )
        if not started:
            await repository.settle_proposal(
                db, proposal["id"], actor_id=actor_id, status="stale", now=now
            )
            raise ValueError("ingestion_stale_proposal")
        await repository.settle_proposal(
            db, proposal["id"], actor_id=actor_id, status="confirmed", now=now
        )

    indexed: list[tuple[str, str]] = []
    for snapshot in proposal["item_snapshot"]:
        result = await _commit_item(
            sessionmaker,
            workspace_id=workspace_id,
            actor_id=actor_id,
            snapshot=snapshot,
        )
        if result is None:
            conflicts += 1
        else:
            committed += 1
            indexed.append(result)

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        completed_at = datetime.now(UTC)
        await repository.finalize_batch(
            db,
            proposal["batch_id"],
            now=completed_at,
            expires_at=completed_at + STAGING_RETENTION,
        )

    for prompt_id, version_id in indexed:
        await enqueue_index_job(
            sessionmaker,
            channel,
            prompt_id=prompt_id,
            version_id=version_id,
            workspace_id=workspace_id,
            created_by=actor_id,
            role="latest",
        )
    return committed, conflicts


async def _commit_item(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace_id: str,
    actor_id: str,
    snapshot: dict[str, Any],
) -> tuple[str, str] | None:
    now = datetime.now(UTC)
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        item = await repository.start_item_commit(db, snapshot, now=now)
        if item is None or not item["canonical_body"]:
            return None

        actor = actor_for(workspace_id, actor_id)
        if snapshot["resolution"] == "create":
            exact = await get_prompt_by_model_name(db, item["namespace"], item["name"])
            if exact is not None or not await may(
                db, actor, Action.PROMPT_CREATE, workspace_subject(workspace_id)
            ):
                await repository.set_failure(db, item["id"], state="needs_attention", error_code="ingestion_commit_conflict", now=now)
                return None
            batch = await repository.load_batch_internal(db, item["batch_id"])
            assert batch is not None
            access_level = batch["default_access_level"]
            if access_level == "workspace" and not await may(
                db, actor, Action.PROMPT_GRANT, workspace_subject(workspace_id)
            ):
                await repository.set_failure(db, item["id"], state="needs_attention", error_code="permission_denied", now=now)
                return None
            prompt = await registry_commands.create_prompt(
                db,
                workspace_id=workspace_id,
                actor_id=actor_id,
                namespace=item["namespace"],
                name=item["name"],
                title=item["title"],
                purpose=item["purpose"],
                owner_id=actor_id,
                access_level=access_level,
                tags=list(item["tags"]),
                now=now,
            )
        else:
            prompt = await registry_repository.load_prompt(db, snapshot["target_prompt_id"])
            if prompt is None or not await may(
                db, actor, Action.REVISION_CREATE, prompt_subject(prompt)
            ):
                await repository.set_failure(db, item["id"], state="needs_attention", error_code="permission_denied", now=now)
                return None
            latest = await registry_repository.load_latest_revision(db, prompt.id)
            latest_id = None if latest is None else latest.version_id
            if latest_id != snapshot["base_version_id"]:
                await repository.set_failure(db, item["id"], state="needs_attention", error_code="ingestion_base_version_changed", now=now)
                return None

        revision = await registry_commands.create_revision(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt.id,
            draft=RevisionDraft(
                body=item["canonical_body"],
                change_summary=item["change_summary"],
                original_body=item["source_text"],
                original_format="markdown" if item["source_format"] == "md" else item["source_format"],
                original_filename=item["source_filename"],
                conversion_model=item["conversion_model"],
                conversion_schema_version=item["conversion_schema_version"],
                tags=list(item["tags"]),
            ),
            now=now,
        )
        await repository.mark_committed(
            db,
            item["id"],
            prompt_id=prompt.id,
            version_id=revision.version_id,
            now=now,
        )
        return prompt.id, revision.version_id
