from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import may
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.prompt_ingestion import repository, service
from prope.prompt_ingestion.domain import MAX_UPLOAD_BYTES, STAGING_RETENTION, ImportMode, IngestionError
from prope.prompt_ingestion.parsers import parse_uploads
from prope.prompt_ingestion.schemas import (
    BatchRead,
    CommitProposalCreate,
    CommitProposalRead,
    CommitResultRead,
    ItemListRead,
    ItemRead,
    ItemUpdate,
    ProposalDecision,
    RetryRead,
    RetryRequest,
)
from prope.prompt_registry import repository as registry_repository
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

router = APIRouter(prefix="/api/v1", tags=["prompt-ingestion"])


def _not_found() -> ManagementRefusal:
    return ManagementRefusal(status_code=404, code=ErrorCode.NOT_FOUND, message="no such import resource")


def _forbidden() -> ManagementRefusal:
    return ManagementRefusal(status_code=403, code=ErrorCode.PERMISSION_DENIED, message="permission denied")


def _batch(row: dict[str, Any]) -> BatchRead:
    return BatchRead(
        id=row["id"],
        mode=row["mode"],
        status=row["status"],
        default_namespace=row["default_namespace"],
        default_access_level=row["default_access_level"],
        field_mapping=dict(row["field_mapping"] or {}),
        review_version=row["review_version"],
        item_count=row.get("item_count", 0),
        ready_count=row.get("ready_count", 0),
        committed_count=row.get("committed_count", 0),
        error_count=row.get("error_count", 0),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        expires_at=row["expires_at"],
    )


def _item(row: dict[str, Any]) -> ItemRead:
    return ItemRead(
        id=row["id"],
        batch_id=row["batch_id"],
        ordinal=row["ordinal"],
        source_filename=row["source_filename"],
        source_format=row["source_format"],
        source_hash=row["source_hash"],
        source_text=row["source_text"],
        title=row["title"],
        purpose=row["purpose"],
        namespace=row["namespace"],
        name=row["name"],
        tags=list(row["tags"] or []),
        change_summary=row["change_summary"],
        canonical_body=row["canonical_body"],
        conversion_model=row["conversion_model"],
        conversion_schema_version=row["conversion_schema_version"],
        semantic_matches=list(row["semantic_matches"] or []),
        resolution=row["resolution"],
        target_prompt_id=row["target_prompt_id"],
        base_version_id=row["base_version_id"],
        state=row["state"],
        error_code=row["error_code"],
        attempts=row["attempts"],
        item_version=row["item_version"],
        result_prompt_id=row["result_prompt_id"],
        result_version_id=row["result_version_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _owned_batch(db: AsyncSession, batch_id: str, actor_id: str) -> dict[str, Any]:
    row = await repository.load_batch(db, batch_id, actor_id=actor_id)
    if row is None:
        raise _not_found()
    return row


@router.post(
    "/import-batches",
    response_model=BatchRead,
    status_code=202,
    dependencies=[Depends(declares_action(ManagementAction.INGESTION_BATCH_CREATE))],
)
async def create_import_batch(
    session: Annotated[Session, Depends(require_session)],
    files: Annotated[list[UploadFile], File()],
    mode: Annotated[ImportMode, Form()],
    namespace: Annotated[str, Form(min_length=1, max_length=63)],
    access_level: Annotated[Literal["private", "workspace"], Form()] = "private",
    field_mapping: Annotated[str, Form()] = "{}",
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> BatchRead:
    try:
        mapping_value = json.loads(field_mapping)
        if not isinstance(mapping_value, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in mapping_value.items()
        ):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as error:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.INGESTION_INVALID_UPLOAD,
            message="field_mapping must be an object of string fields",
        ) from error

    uploads: list[tuple[str, bytes]] = []
    total = 0
    for upload in files:
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        total += len(data)
        if total > MAX_UPLOAD_BYTES:
            raise ManagementRefusal(
                status_code=413,
                code=ErrorCode.INGESTION_INVALID_UPLOAD,
                message="upload is too large",
            )
        uploads.append((upload.filename or "prompt.txt", data))
    try:
        candidates = parse_uploads(
            uploads,
            mode=mode,
            namespace=namespace,
            field_mapping=mapping_value,
        )
    except IngestionError as error:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.INGESTION_INVALID_UPLOAD,
            message="the import could not be parsed",
            details={"reason": error.code},
        ) from error

    now = datetime.now(UTC)
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        if not await service.may_create_batch(
            db, workspace_id=session.workspace_id, actor_id=session.user_id
        ):
            raise _forbidden()
        if access_level == "workspace" and not await may(
            db,
            service.actor_for(session.workspace_id, session.user_id),
            Action.PROMPT_GRANT,
            service.workspace_subject(session.workspace_id),
        ):
            raise _forbidden()
        batch_id = await repository.create_batch(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            mode=mode,
            namespace=namespace,
            access_level=access_level,
            mapping=mapping_value,
            candidates=candidates,
            now=now,
            expires_at=now + STAGING_RETENTION,
        )
        row = await repository.load_batch(db, batch_id, actor_id=session.user_id)
        assert row is not None
    return _batch(row)


@router.get(
    "/import-batches/{batch_id}",
    response_model=BatchRead,
    dependencies=[Depends(declares_action(ManagementAction.INGESTION_BATCH_READ))],
)
async def read_import_batch(
    batch_id: Annotated[str, Path(max_length=64)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> BatchRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        return _batch(await _owned_batch(db, batch_id, session.user_id))


@router.get(
    "/import-batches/{batch_id}/items",
    response_model=ItemListRead,
    dependencies=[Depends(declares_action(ManagementAction.INGESTION_ITEM_LIST))],
)
async def list_import_items(
    batch_id: Annotated[str, Path(max_length=64)],
    session: Annotated[Session, Depends(require_session)],
    state: Annotated[str | None, Query(max_length=32)] = None,
    cursor: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ItemListRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _owned_batch(db, batch_id, session.user_id)
        rows = await repository.list_items(db, batch_id, state=state, cursor=cursor, limit=limit)
    return ItemListRead(
        items=[_item(row) for row in rows],
        next_cursor=rows[-1]["ordinal"] if len(rows) == limit else None,
    )


@router.patch(
    "/import-batches/{batch_id}/items/{item_id}",
    response_model=ItemRead,
    dependencies=[Depends(declares_action(ManagementAction.INGESTION_ITEM_UPDATE))],
)
async def update_import_item(
    payload: ItemUpdate,
    batch_id: Annotated[str, Path(max_length=64)],
    item_id: Annotated[str, Path(max_length=64)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ItemRead:
    now = datetime.now(UTC)
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        batch = await _owned_batch(db, batch_id, session.user_id)
        if batch["status"] not in {"processing", "review_ready", "completed_with_errors"}:
            raise ManagementRefusal(status_code=409, code=ErrorCode.INGESTION_NOT_READY, message="batch cannot be edited")
        values = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
        if payload.resolution == "revise" and payload.target_prompt_id:
            prompt = await registry_repository.load_prompt(db, payload.target_prompt_id)
            if prompt is None or not await may(
                db,
                service.actor_for(session.workspace_id, session.user_id),
                Action.REVISION_CREATE,
                service.prompt_subject(prompt),
            ):
                raise _not_found()
            latest = await registry_repository.load_latest_revision(db, prompt.id)
            values["base_version_id"] = None if latest is None else latest.version_id
        row = await repository.update_item(
            db,
            batch_id,
            item_id,
            expected_version=payload.expected_version,
            values=values,
            now=now,
        )
        if row is None:
            raise ManagementRefusal(status_code=409, code=ErrorCode.INGESTION_STALE_PROPOSAL, message="item changed")
        await repository.touch_batch(db, batch_id, now=now)
    return _item(row)


@router.post(
    "/import-batches/{batch_id}/retry",
    response_model=RetryRead,
    dependencies=[Depends(declares_action(ManagementAction.INGESTION_ITEM_RETRY))],
)
async def retry_import_items(
    payload: RetryRequest,
    batch_id: Annotated[str, Path(max_length=64)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> RetryRead:
    now = datetime.now(UTC)
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _owned_batch(db, batch_id, session.user_id)
        retried = await repository.retry_items(db, batch_id, payload.item_ids, now=now)
        await repository.touch_batch(db, batch_id, now=now)
        await repository.refresh_batch(db, batch_id, now=now)
    return RetryRead(retried_item_ids=retried)


@router.post(
    "/import-batches/{batch_id}/commit-proposals",
    response_model=CommitProposalRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.INGESTION_PROPOSAL_CREATE))],
)
async def create_commit_proposal(
    payload: CommitProposalCreate,
    batch_id: Annotated[str, Path(max_length=64)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> CommitProposalRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        batch = await _owned_batch(db, batch_id, session.user_id)
        if batch["status"] != "review_ready" or batch["review_version"] != payload.expected_review_version:
            raise ManagementRefusal(status_code=409, code=ErrorCode.INGESTION_STALE_PROPOSAL, message="batch changed")
        try:
            proposal = await repository.create_proposal(
                db,
                batch=batch,
                actor_id=session.user_id,
                item_ids=payload.item_ids,
                now=datetime.now(UTC),
            )
        except ValueError as error:
            raise ManagementRefusal(status_code=409, code=ErrorCode.INGESTION_NOT_READY, message="selected items are not ready") from error
    return CommitProposalRead(**proposal)


@router.post(
    "/action-proposals/{proposal_id}/decision",
    response_model=CommitResultRead,
    dependencies=[Depends(declares_action(ManagementAction.INGESTION_PROPOSAL_DECIDE))],
)
async def decide_commit_proposal(
    payload: ProposalDecision,
    proposal_id: Annotated[str, Path(max_length=64)],
    request: Request,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> CommitResultRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        proposal = await repository.load_proposal(db, proposal_id, actor_id=session.user_id)
        if proposal is None:
            raise _not_found()
        if proposal["status"] != "pending":
            raise ManagementRefusal(status_code=409, code=ErrorCode.INGESTION_STALE_PROPOSAL, message="proposal was already decided")
        if not payload.approve:
            await repository.settle_proposal(db, proposal_id, actor_id=session.user_id, status="rejected", now=datetime.now(UTC))
            return CommitResultRead(id=proposal_id, status="rejected", batch_id=proposal["batch_id"])

    try:
        committed, conflicts = await service.commit_proposal(
            sessionmaker,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            proposal=proposal,
            channel=getattr(request.app.state, "broker_channel", None),
        )
    except ValueError as error:
        raise ManagementRefusal(status_code=409, code=ErrorCode.INGESTION_STALE_PROPOSAL, message="proposal is stale") from error
    return CommitResultRead(
        id=proposal_id,
        status="confirmed",
        batch_id=proposal["batch_id"],
        committed_count=committed,
        conflict_count=conflicts,
    )
