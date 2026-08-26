from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import AccessLevel, Actor, ActorType, Subject, SubjectType, may
from prope.agent_run import repository
from prope.agent_run.domain import RunKind, RunStatus
from prope.agent_run.lifecycle import lifecycle_summary
from prope.agent_run.schemas import AgentRunCreate, AgentRunRead, LifecycleSummaryRead
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.prompt_registry.seams import get_prompt, get_revision
from prope.session_auth import ManagementAction, ManagementRefusal, Session, declares_action, require_session

router = APIRouter(prefix="/api/v1")


def _not_found() -> ManagementRefusal:
    return ManagementRefusal(status_code=404, code=ErrorCode.NOT_FOUND, message="no such resource")


async def _visible_prompt(db: AsyncSession, session: Session, prompt_id: str, action: Action = Action.PROMPT_READ):
    prompt = await get_prompt(db, prompt_id)
    if prompt is None:
        raise _not_found()
    allowed = await may(
        db,
        Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id),
        action,
        Subject(
            type=SubjectType.PROMPT, id=prompt.id, workspace_id=prompt.workspace_id,
            owner_id=prompt.owner_id, access_level=AccessLevel(prompt.access_level),
            namespace=prompt.namespace,
        ),
    )
    if not allowed:
        raise _not_found()
    return prompt


@router.post(
    "/agent-runs", response_model=AgentRunRead, status_code=202,
    dependencies=[Depends(declares_action(ManagementAction.AGENT_RUN_CREATE))],
)
async def create_agent_run(
    payload: AgentRunCreate,
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> AgentRunRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        if payload.prompt_id is not None:
            permission = {
                RunKind.CHAT: Action.PROMPT_READ,
                RunKind.IMPORT: Action.REVISION_CREATE,
                RunKind.EVALUATION: Action.RUN_START,
                RunKind.PRODUCTION_ANALYSIS: Action.PROMPT_READ,
                RunKind.IMPROVEMENT: Action.REVISION_CREATE,
            }[payload.kind]
            prompt = await _visible_prompt(db, session, payload.prompt_id, permission)
            if payload.version_id is not None:
                revision = await get_revision(db, payload.version_id)
                if revision is None or revision.prompt_id != prompt.id:
                    raise _not_found()
        else:
            allowed = await may(
                db,
                Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id),
                Action.PROMPT_CREATE,
                Subject(type=SubjectType.WORKSPACE, id=session.workspace_id, workspace_id=session.workspace_id),
            )
            if not allowed:
                raise ManagementRefusal(status_code=403, code=ErrorCode.PERMISSION_DENIED, message="permission denied")
        active_run_id = None
        if payload.kind is RunKind.IMPROVEMENT and payload.prompt_id is not None:
            await repository.lock_improvement_scope(
                db, workspace_id=session.workspace_id,
                requested_by=session.user_id, prompt_id=payload.prompt_id,
            )
            active_run_id = await repository.active_improvement_run(
                db, workspace_id=session.workspace_id,
                requested_by=session.user_id, prompt_id=payload.prompt_id,
            )
        run_id = active_run_id or await repository.create_run(
            db, workspace_id=session.workspace_id, requested_by=session.user_id,
            kind=payload.kind, plan_basis=payload.plan_basis,
            idempotency_key=payload.idempotency_key, prompt_id=payload.prompt_id,
            version_id=payload.version_id,
            source_refs=(
                (
                    f"selected_revision:{payload.version_id}",
                    f"live_revision:{prompt.released_version_id or ''}",
                    f"usage_profile:{prompt.audience},{prompt.untrusted_input},{prompt.acts},{prompt.sensitivity}",
                )
                if payload.kind is RunKind.IMPROVEMENT and payload.version_id is not None
                else ()
            ),
        )
        row = await repository.read_run(
            db, workspace_id=session.workspace_id, requested_by=session.user_id, run_id=run_id,
        )
    if row is None:
        raise _not_found()
    return AgentRunRead.model_validate(row)


@router.get(
    "/agent-runs", response_model=list[AgentRunRead],
    dependencies=[Depends(declares_action(ManagementAction.AGENT_RUN_LIST))],
)
async def list_agent_runs(
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    status: Annotated[RunStatus | None, Query()] = None,
    kind: Annotated[RunKind | None, Query()] = None,
    prompt_id: Annotated[str | None, Query(max_length=64)] = None,
    version_id: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AgentRunRead]:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        rows = await repository.list_runs(
            db, workspace_id=session.workspace_id, requested_by=session.user_id,
            status=status, limit=limit,
            kind=kind, prompt_id=prompt_id, version_id=version_id,
        )
    return [AgentRunRead.model_validate(row) for row in rows]


@router.get(
    "/agent-runs/{run_id}", response_model=AgentRunRead,
    dependencies=[Depends(declares_action(ManagementAction.AGENT_RUN_READ))],
)
async def read_agent_run(
    run_id: Annotated[str, Path(max_length=64)],
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> AgentRunRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await repository.read_run(
            db, workspace_id=session.workspace_id, requested_by=session.user_id, run_id=run_id,
        )
    if row is None:
        raise _not_found()
    return AgentRunRead.model_validate(row)


@router.post(
    "/agent-runs/{run_id}/acknowledge", response_model=AgentRunRead,
    dependencies=[Depends(declares_action(ManagementAction.AGENT_RUN_ACKNOWLEDGE))],
)
async def acknowledge_agent_run(
    run_id: Annotated[str, Path(max_length=64)],
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> AgentRunRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        acknowledged = await repository.acknowledge(
            db, workspace_id=session.workspace_id, requested_by=session.user_id, run_id=run_id,
        )
        if not acknowledged:
            raise _not_found()
        row = await repository.read_run(
            db, workspace_id=session.workspace_id, requested_by=session.user_id, run_id=run_id,
        )
    if row is None:
        raise _not_found()
    return AgentRunRead.model_validate(row)


@router.get(
    "/prompts/{prompt_id}/lifecycle-summary", response_model=LifecycleSummaryRead,
    dependencies=[Depends(declares_action(ManagementAction.LIFECYCLE_SUMMARY_READ))],
)
async def read_lifecycle_summary(
    prompt_id: Annotated[str, Path(max_length=64)],
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    version_id: Annotated[str, Query(max_length=64)],
) -> LifecycleSummaryRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        prompt = await _visible_prompt(db, session, prompt_id)
        revision = await get_revision(db, version_id)
        if revision is None or revision.prompt_id != prompt.id:
            raise _not_found()
        result = await lifecycle_summary(
            db, prompt=prompt, version_id=version_id, revision_status=revision.status,
        )
    return LifecycleSummaryRead.model_validate(result)
