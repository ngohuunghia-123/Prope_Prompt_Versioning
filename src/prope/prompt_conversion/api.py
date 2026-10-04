"""Authenticated, explicitly-triggered prompt source conversion API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import (
    AccessLevel,
    Actor,
    ActorType,
    Subject,
    SubjectType,
    may,
)
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.prompt_conversion.domain import InvalidAgentOutputError, InvalidSourceError
from prope.prompt_conversion.schemas import PromptConversionCreate, PromptConversionRead
from prope.prompt_conversion.service import (
    AgentBillingError,
    AgentUnavailableError,
    ConversionContext,
    convert_source,
)
from prope.prompt_registry import repository
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

router = APIRouter(prefix="/api/v1")


def _forbidden(action: Action) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=403,
        code=ErrorCode.PERMISSION_DENIED,
        message=f"this action requires the {action.value} permission",
        details={"permission": action.value},
    )


async def _authorize(
    db: AsyncSession, session: Session, prompt_id: str | None
) -> None:
    actor = Actor(
        type=ActorType.USER,
        id=session.user_id,
        workspace_id=session.workspace_id,
    )
    if prompt_id is None:
        subject = Subject(
            type=SubjectType.WORKSPACE,
            id=session.workspace_id,
            workspace_id=session.workspace_id,
        )
        if not await may(db, actor, Action.PROMPT_CREATE, subject):
            raise _forbidden(Action.PROMPT_CREATE)
        return

    row = await repository.load_prompt(db, prompt_id)
    if row is None:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such prompt",
        )
    subject = Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        # ADR-0061. Read off the same row the other two come from, and required
        # for the same reason ADR-0020 requires them: a namespace grant is the
        # fifth source `may()` unions, and a subject that omitted its namespace
        # would silently skip it — which reads as "the grant does not work"
        # rather than as a missing field.
        namespace=row.namespace,
    )
    if not await may(db, actor, Action.REVISION_CREATE, subject):
        if await may(db, actor, Action.PROMPT_READ, subject):
            raise _forbidden(Action.REVISION_CREATE)
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such prompt",
        )


@router.post(
    "/prompt-conversions",
    response_model=PromptConversionRead,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_CONVERT))],
)
async def create_prompt_conversion(
    payload: PromptConversionCreate,
    response: Response,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> PromptConversionRead:
    response.headers["Cache-Control"] = "no-store"
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _authorize(db, session, payload.prompt_id)

    try:
        xml_body, model, schema_version = await convert_source(
            payload.source_text,
            payload.source_format,
            context=ConversionContext(
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=payload.prompt_id,
            ),
        )
    except InvalidSourceError as error:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.CONVERSION_INVALID_SOURCE,
            message=str(error),
        ) from error
    except InvalidAgentOutputError as error:
        raise ManagementRefusal(
            status_code=502,
            code=ErrorCode.CONVERSION_INVALID_AGENT_OUTPUT,
            message="prompt conversion returned an invalid result",
        ) from error
    except AgentBillingError as error:
        raise ManagementRefusal(
            status_code=503,
            code=ErrorCode.CONVERSION_BILLING_REQUIRED,
            message="prompt conversion provider requires billing attention",
        ) from error
    except AgentUnavailableError as error:
        raise ManagementRefusal(
            status_code=503,
            code=ErrorCode.CONVERSION_AGENT_UNAVAILABLE,
            message="prompt conversion service is unavailable",
        ) from error

    return PromptConversionRead(
        xml_body=xml_body,
        model=model,
        schema_version=schema_version,
    )
