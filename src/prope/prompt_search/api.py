"""FastAPI routes for prompt-search (INT-024 pattern).

Endpoints:
  - GET  /api/v1/prompts/search?q={query}&type={quick|ai}&cursor={cursor}
  - GET  /api/v1/prompts/{prompt_id}/index
  - POST /api/v1/prompts/{prompt_id}/index
  - GET  /api/v1/prompts/{prompt_id}/index/preview
  - DELETE /api/v1/prompts/{prompt_id}/index
  - GET  /api/v1/prompt-search/jobs/{job_id}

Every search and index request resolves permission through access-control.
"""

import base64
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from prope.access_control.actions import Action
from prope.access_control.seams import (
    AccessLevel,
    Actor,
    ActorType,
    Subject,
    SubjectType,
    may,
    visible_subject_filter,
)
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.prompt_registry.domain import PromptStatus
from prope.prompt_registry.repository import load_prompt
from prope.prompt_search import repository
from prope.prompt_search.agent import get_openai_client, preview_extraction, semantic_search
from prope.prompt_search.events import publish_event
from prope.prompt_search.schemas import (
    IndexDeindexResponse,
    IndexPreviewResponse,
    IndexStatusResponse,
    IndexTriggerResponse,
    JobStatusResponse,
    SearchResponse,
    SearchResultItem,
)
from prope.prompt_search.seams import publish_indexing_job
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")


def _actor(session: Session) -> Actor:
    return Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id)


def _subject(session: Session, row) -> Subject:
    return Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
    )


def _not_found() -> ManagementRefusal:
    return ManagementRefusal(status_code=404, code=ErrorCode.NOT_FOUND, message="no such prompt")


def _forbidden(action: Action) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=403,
        code=ErrorCode.PERMISSION_DENIED,
        message=f"this action requires the {action.value} permission",
        details={"permission": action.value, "subject_type": SubjectType.PROMPT.value},
    )


async def _require_write_permission(db: AsyncSession, session: Session, prompt_id: str):
    """Load prompt and verify write permission."""
    row = await load_prompt(db, prompt_id)
    if row is None:
        raise _not_found()

    actor = _actor(session)
    subject = _subject(session, row)

    if await may(db, actor, Action.PROMPT_EDIT, subject):
        return row

    if await may(db, actor, Action.PROMPT_READ, subject):
        raise _forbidden(Action.PROMPT_EDIT)

    raise _not_found()


async def _require_read_permission(db: AsyncSession, session: Session, prompt_id: str):
    row = await load_prompt(db, prompt_id)
    if row is None:
        raise _not_found()
    if not await may(db, _actor(session), Action.PROMPT_READ, _subject(session, row)):
        raise _not_found()
    return row


def _offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
        if not decoded.startswith("prompt-search:"):
            raise ValueError
        offset = int(decoded.removeprefix("prompt-search:"))
        if offset < 0:
            raise ValueError
    except (UnicodeError, ValueError):
        raise ManagementRefusal(
            status_code=400,
            code=ErrorCode.VALIDATION_FAILED,
            message="invalid search cursor",
        ) from None
    return offset


def _cursor(offset: int) -> str:
    value = f"prompt-search:{offset}".encode("ascii")
    return base64.urlsafe_b64encode(value).decode("ascii")


@router.get(
    "/prompts/search",
    response_model=SearchResponse,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_SEARCH))],
)
async def search_prompts(
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    q: Annotated[str | None, Query(max_length=500)] = None,
    type: Annotated[str, Query(pattern=r"^(quick|ai)$")] = "quick",
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SearchResponse:
    """Search prompts with either quick (keyword) or AI (semantic) search.

    - type=quick: keyword search across all prompts (indexed or not)
    - type=ai: semantic similarity over indexed prompts only
    """
    if not q:
        return SearchResponse(prompts=[], search_type=type)

    offset = _offset(cursor)
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)

        if type == "quick":
            results = await repository.list_prompts_for_quick_search(
                db,
                workspace_id=session.workspace_id,
                keyword=q,
                visible=visible,
                actor_id=session.user_id,
                cursor=str(offset),
                limit=limit + 1,
            )
        else:
            # AI search uses the app-owned embedding service and pgvector.
            results = await semantic_search(
                db=db,
                query=q,
                workspace_id=session.workspace_id,
                visible=visible,
                actor_id=session.user_id,
                cursor=str(offset),
                limit=limit + 1,
            )

    has_more = len(results) > limit
    results = results[:limit]
    return SearchResponse(
        prompts=[
            SearchResultItem(
                prompt_id=r.prompt_id,
                title=r.title,
                purpose=r.purpose,
                similarity=r.similarity,
                keywords=r.keywords if isinstance(r.keywords, list) else list(r.keywords or []),
                topics=r.topics if isinstance(r.topics, list) else list(r.topics or []),
                entities=list(r.entities),
                variations=r.variations.to_dict(),
                language=list(r.language),
                matched_fields=list(r.matched_fields),
                is_indexed=r.is_indexed,
            )
            for r in results
        ],
        search_type=type,
        next_cursor=_cursor(offset + limit) if has_more else None,
    )


@router.get(
    "/prompts/{prompt_id}/index",
    response_model=IndexStatusResponse,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_INDEX_READ))],
)
async def get_index_status(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> IndexStatusResponse:
    """Get the index status for a prompt."""
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _require_read_permission(db, session, prompt_id)

        # Get index record
        index = await repository.get_index_by_prompt(db, prompt_id)

        if index is None:
            return IndexStatusResponse(is_indexed=False)

        # Check if stale
        from prope.prompt_search.agent.base import APP_EMBEDDING_MODEL

        is_stale = (
            not row.released_version_id
            or index.version_id != row.released_version_id
            or index.embedding_model != APP_EMBEDDING_MODEL
        )
        nearest_neighbor = None
        if index.nearest_neighbor_id:
            neighbor = await load_prompt(db, index.nearest_neighbor_id)
            if neighbor is not None and await may(
                db,
                _actor(session),
                Action.PROMPT_READ,
                _subject(session, neighbor),
            ):
                nearest_neighbor = {
                    "prompt_id": neighbor.id,
                    "title": neighbor.title,
                    "similarity": index.nearest_neighbor_similarity,
                }

        return IndexStatusResponse(
            is_indexed=not is_stale,
            is_stale=is_stale,
            indexed_at=index.indexed_at,
            indexed_by=index.indexed_by,
            version_id=index.version_id,
            nearest_neighbor=nearest_neighbor,
        )


@router.post(
    "/prompts/{prompt_id}/index",
    response_model=IndexTriggerResponse,
    status_code=202,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_INDEX_TRIGGER))],
)
async def trigger_indexing(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    request: Request,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> IndexTriggerResponse:
    """Trigger async indexing for a prompt.

    Returns 202 Accepted with job_id. The extraction runs async via RabbitMQ.
    """
    job_id = f"psj_{ULID()}"
    channel = getattr(request.app.state, "broker_channel", None)
    if channel is None:
        raise ManagementRefusal(
            status_code=503,
            code=ErrorCode.INTERNAL_ERROR,
            message="indexing is temporarily unavailable",
        )

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        # Verify permission and get prompt data
        row = await _require_write_permission(db, session, prompt_id)

        # Only index approved prompts
        if row.status != PromptStatus.ACTIVE:
            raise ManagementRefusal(
                status_code=400,
                code=ErrorCode.VALIDATION_FAILED,
                message="only active prompts can be indexed",
            )

        # Get the latest released revision
        from prope.prompt_registry.repository import load_released_revision

        revision = await load_released_revision(db, prompt_id)

        if revision is None:
            raise ManagementRefusal(
                status_code=400,
                code=ErrorCode.VALIDATION_FAILED,
                message="prompt has no released revision to index",
            )

        version_id = revision.version_id

        # Create job record
        await repository.create_job_record(
            db,
            job_id=job_id,
            prompt_id=prompt_id,
            version_id=version_id,
            workspace_id=session.workspace_id,
            created_by=session.user_id,
        )

    try:
        await publish_indexing_job(
            channel,
            job_id=job_id,
            prompt_id=prompt_id,
            version_id=version_id,
            workspace_id=session.workspace_id,
            created_by=session.user_id,
        )
    except Exception as error:
        async with workspace_transaction(sessionmaker, session.workspace_id) as db:
            await repository.update_job_failed(db, job_id, "broker unavailable")
        log.warning(
            "prompt_search.publish_failed",
            job_id=job_id,
            prompt_id=prompt_id,
            workspace_id=session.workspace_id,
            reason=type(error).__name__,
        )
        raise ManagementRefusal(
            status_code=503,
            code=ErrorCode.INTERNAL_ERROR,
            message="indexing is temporarily unavailable",
        ) from error
    from prope.prompt_search.observability import index_triggered_total

    index_triggered_total.labels(prompt_id=prompt_id, workspace_id=session.workspace_id).inc()

    return IndexTriggerResponse(job_id=job_id)


@router.get(
    "/prompts/{prompt_id}/index/preview",
    response_model=IndexPreviewResponse,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_INDEX_PREVIEW))],
)
async def preview_index(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> IndexPreviewResponse:
    """Preview what would be indexed without storing.

    Dry-run: extracts metadata and shows duplicate warnings.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _require_write_permission(db, session, prompt_id)

        # Get released revision
        from prope.prompt_registry.repository import load_released_revision

        revision = await load_released_revision(db, prompt_id)

        if revision is None:
            raise ManagementRefusal(
                status_code=400,
                code=ErrorCode.VALIDATION_FAILED,
                message="prompt has no released revision to preview",
            )

        # Preview extraction
        metadata = await preview_extraction(
            body=revision.body,
            purpose=row.purpose,
            title=row.title,
        )

        # Check for duplicates
        from prope.prompt_search.agent.base import APP_EMBEDDING_MODEL, call_app_service

        client = await get_openai_client()
        response = await call_app_service(
            lambda: client.embeddings.create(
                model=APP_EMBEDDING_MODEL,
                input=row.purpose,
            )
        )
        embedding = response.data[0].embedding

        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)

        neighbors = await repository.find_nearest_neighbors(
            db,
            workspace_id=session.workspace_id,
            embedding=embedding,
            exclude_prompt_id=prompt_id,
            visible=visible,
            actor_id=session.user_id,
        )

        duplicate_warning = None
        if neighbors:
            nearest = neighbors[0]
            if nearest.get("similarity", 0) >= repository.DUPLICATE_SIMILARITY_THRESHOLD:
                neighbor_prompt = await load_prompt(db, nearest["prompt_id"])
                if neighbor_prompt is None:
                    raise RuntimeError("visible nearest neighbor no longer exists")
                duplicate_warning = {
                    "prompt_id": nearest["prompt_id"],
                    "title": neighbor_prompt.title,
                    "similarity": nearest["similarity"],
                }

        return IndexPreviewResponse(
            keywords=list(metadata.keywords),
            topics=list(metadata.topics),
            entities=list(metadata.entities),
            variations=metadata.variations.to_dict(),
            language=list(metadata.language),
            duplicate_warning=duplicate_warning,
        )


@router.delete(
    "/prompts/{prompt_id}/index",
    response_model=IndexDeindexResponse,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_INDEX_DELETE))],
)
async def deindex_prompt(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    request: Request,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> IndexDeindexResponse:
    """Remove index for a prompt. Does not delete the prompt."""
    channel = getattr(request.app.state, "broker_channel", None)
    if channel is None:
        raise ManagementRefusal(
            status_code=503,
            code=ErrorCode.INTERNAL_ERROR,
            message="de-indexing is temporarily unavailable",
        )
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        # Verify permission
        await _require_write_permission(db, session, prompt_id)

        # Delete index record
        deleted = await repository.delete_index_record(db, prompt_id)
        if deleted:
            await publish_event(
                channel,
                "prope.prompt_deindexed",
                {"prompt_id": prompt_id, "deindexed_by": session.user_id},
            )

        log.info(
            "prompt_search.deindexed",
            prompt_id=prompt_id,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
        )

    return IndexDeindexResponse(success=deleted)


@router.get(
    "/prompt-search/jobs/{job_id}",
    response_model=JobStatusResponse,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_INDEX_JOB_READ))],
)
async def get_job_status(
    job_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> JobStatusResponse:
    """Get the status of an indexing job."""
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        job = await repository.get_job_status(db, job_id)

        if job is None:
            raise _not_found()
        await _require_read_permission(db, session, job.prompt_id)

        from prope.prompt_search.observability import observe_terminal_job

        observe_terminal_job(
            job.job_id,
            session.workspace_id,
            job.status.value,
            job.error,
            job.result_json,
        )

        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status.value,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error=job.error,
        )
