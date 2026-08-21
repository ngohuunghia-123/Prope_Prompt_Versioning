"""Chat transport, history, human decisions, feedback, and pipeline inspection.

**Why the write is a second request and not a flag on the first.** It is the
difference between an assistant that asked and an assistant that told you
afterwards. Deck 5 (p53-54) puts *irreversible action* at the top of the
escalate-to-a-human table and matches it to `human-in-the-loop` — agent proposes,
human approves *before*. A `confirm: true` field on `POST /chat/messages` would
satisfy the letter of that and none of it: the approval and the thing approved
would arrive in the same breath, from the same client state, with nothing between
them for a person to read. Here the proposal is a row, the card renders what that
row says, and the decision is an HTTP request carrying a person's `approve`.

**The turn's transaction boundaries.** Three, deliberately, and none of them
spans a model call:

1. load the thread and the person's recent turns;
2. inside `run_turn`, one transaction around the tool phase;
3. persist the two messages and any proposal.

The alternative — one transaction for the whole handler — holds a pooled
connection across two multi-second model calls, which starves every other route
in the process while doing no database work. `TurnRequest.open_db` exists for
this and nothing else.

**A conversation the actor does not own is `not_found`.** Not `forbidden`, for
BR-01's reason one level up from prompts: the two answers must be
indistinguishable, or the route becomes an oracle for which threads exist.
"""

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, Path, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import Actor, ActorType, SubjectType, visible_subject_filter
from prope.chat_orchestrator import repository
from prope.chat_orchestrator.domain import TOOLS, Intent
from prope.chat_orchestrator.orchestrator import TurnRequest, confirm_action, run_turn
from prope.chat_orchestrator.schemas import (
    ActionDecisionCreate,
    ActionDecisionRead,
    ChatMessageCreate,
    ConversationListRead,
    ConversationRead,
    ConversationTranscriptRead,
    FeedbackCreate,
    FeedbackRead,
    MessageRead,
    PendingActionRead,
    PipelineEdgeRead,
    PipelineNodeRead,
    PipelineRead,
    TurnRead,
)
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

router = APIRouter(prefix="/api/v1")

#: `intent -> the catalogue key the client renders as the thread's title`. The
#: thread list must not carry a title derived from what somebody typed, so it
#: carries what the assistant decided the thread was about instead.
_TITLE_CODES = {
    Intent.SEARCH: "chat.thread.search",
    Intent.DUPLICATE_CHECK: "chat.thread.duplicate_check",
    Intent.IMPORT_PROMPT: "chat.thread.import_prompt",
    Intent.DOCS_QUESTION: "chat.thread.docs_question",
    Intent.SMALLTALK: "chat.thread.general",
    Intent.REFUSED: "chat.thread.general",
}


#: The stage a worker sits at. Named rather than inlined because three separate
#: places below have to agree about it, and a graph whose edges disagree with its
#: columns is worse than no graph.
_WORKER_STAGE: Final = 2


def _build_pipeline() -> PipelineRead:
    """Every node a turn could visit, derived from the tool catalogue.

    **The workers are read from `TOOLS`; only the four fixed stages are written
    here.** `domain.TOOLS` calls itself "the only place a tool comes into
    existence", and a hand-kept second list in this module — or worse, in
    TypeScript — would make that false the first time somebody adds a seventh
    tool: it would run, and the graph would quietly never draw it. Nothing fails
    loudly in that story, which is why the list is not written twice.

    **Workers are drawn as alternatives at one stage, not as a chain.** They do
    execute in order (`orchestrator._execute`), so a literal graph would need an
    edge for every ordered pair — thirty of them, to describe a plan of at most
    three steps. The stacked column says the true and useful thing instead: after
    routing, any of these six may run, and whatever ran feeds the answer.

    A constant, built once at import. It reads no row, depends on no request, and
    is byte-identical for every actor in every workspace.
    """
    nodes = [
        PipelineNodeRead(
            id="guardrail.input",
            agent="guardrail.input",
            kind="guardrail",
            label_code="chat.graph.node.guardrail_input",
            stage=0,
        ),
        PipelineNodeRead(
            id="supervisor.route",
            agent="supervisor",
            # `agent` alone is ambiguous — the supervisor also answers. See
            # `PipelineNodeRead` for why the disambiguator lives on the node.
            action="route",
            kind="supervisor",
            label_code="chat.graph.node.supervisor_route",
            stage=1,
        ),
    ]
    nodes.extend(
        PipelineNodeRead(
            id=f"worker.{name}",
            agent=f"worker.{name}",
            kind="worker",
            label_code=f"chat.graph.node.worker_{name}",
            stage=_WORKER_STAGE,
            writes=spec.writes,
        )
        for name, spec in TOOLS.items()
    )
    nodes.extend(
        [
            PipelineNodeRead(
                id="supervisor.respond",
                agent="supervisor",
                action="respond",
                kind="supervisor",
                label_code="chat.graph.node.supervisor_respond",
                stage=3,
            ),
            PipelineNodeRead(
                id="guardrail.output",
                agent="guardrail.output",
                kind="guardrail",
                label_code="chat.graph.node.guardrail_output",
                stage=4,
            ),
        ]
    )

    workers = [node.id for node in nodes if node.kind == "worker"]
    edges = [
        PipelineEdgeRead(source="guardrail.input", target="supervisor.route"),
        # Small talk and a refused-at-the-rail turn both route straight to the
        # answer with an empty plan, so this edge is not a shortcut — it is the
        # commonest path through the graph.
        PipelineEdgeRead(source="supervisor.route", target="supervisor.respond"),
        *(PipelineEdgeRead(source="supervisor.route", target=worker) for worker in workers),
        *(PipelineEdgeRead(source=worker, target="supervisor.respond") for worker in workers),
        PipelineEdgeRead(source="supervisor.respond", target="guardrail.output"),
    ]

    return PipelineRead(nodes=nodes, edges=edges)


_PIPELINE: Final = _build_pipeline()


def _actor(session: Session) -> Actor:
    return Actor(
        type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id
    )


def _not_found() -> ManagementRefusal:
    return ManagementRefusal(
        status_code=404, code=ErrorCode.NOT_FOUND, message="no such conversation"
    )


def _conversation(row: dict[str, Any]) -> ConversationRead:
    return ConversationRead(
        id=row["id"],
        title_code=row["title_code"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        message_count=row["message_count"],
    )


def _pending(row: dict[str, Any] | None) -> PendingActionRead | None:
    if row is None:
        return None
    return PendingActionRead(
        id=row["id"], tool=row["tool"], summary=row["summary"], preview=row["preview"] or {}
    )


@router.post(
    "/chat/messages",
    response_model=TurnRead,
    dependencies=[Depends(declares_action(ManagementAction.CHAT_MESSAGE_SEND))],
)
async def send_chat_message(
    payload: ChatMessageCreate,
    response: Response,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> TurnRead:
    """One turn: route it, run it, answer it, store it."""
    response.headers["Cache-Control"] = "no-store"
    return await _complete_chat_turn(
        payload=payload,
        session=session,
        sessionmaker=sessionmaker,
    )


async def _complete_chat_turn(
    *,
    payload: ChatMessageCreate,
    session: Session,
    sessionmaker: async_sessionmaker[AsyncSession],
    activity: Any = None,
) -> TurnRead:
    """Shared turn implementation for JSON and event-stream transports."""
    now = datetime.now(UTC)

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)

        conversation_id = payload.conversation_id
        history: list[str] = []
        if conversation_id is not None:
            thread = await repository.load_conversation(
                db, conversation_id, actor_id=session.user_id
            )
            if thread is None:
                raise _not_found()
            history = await repository.recent_user_messages(
                db, conversation_id, actor_id=session.user_id
            )

    def open_db():  # noqa: ANN202 - an inline factory, see TurnRequest.open_db
        return workspace_transaction(sessionmaker, session.workspace_id)

    result = await run_turn(
        TurnRequest(
            open_db=open_db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            visible=visible,
            conversation_id=conversation_id or "",
            message=payload.text,
            history=history,
            attachment=payload.attachment,
            attachment_format=payload.attachment_format,
            activity=activity,
        )
    )

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        if conversation_id is None:
            conversation_id = await repository.create_conversation(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                title_code=_TITLE_CODES.get(result.intent, "chat.thread.general"),
                now=now,
            )

        # The person's turn is stored even when the rails refused it, and that is
        # the point rather than an oversight: a thread that silently drops what
        # somebody typed reads as the product having lost it, and the refusal
        # beside it is what makes the reason legible.
        await repository.append_message(
            db,
            conversation_id=conversation_id,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            role="user",
            body=payload.text,
            now=now,
        )

        pending_read: PendingActionRead | None = None
        if result.pending is not None:
            action_id = await repository.propose_action(
                db,
                conversation_id=conversation_id,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                tool=result.pending.tool,
                summary=result.pending.summary,
                preview=result.pending.preview,
                arguments=result.pending.arguments,
                now=now,
            )
            pending_read = PendingActionRead(
                id=action_id,
                tool=result.pending.tool,
                summary=result.pending.summary,
                preview=result.pending.preview,
            )
            from prope.chat_orchestrator import observability

            observability.pending_action_total.labels(decision="proposed").inc()

        message_id = await repository.append_message(
            db,
            conversation_id=conversation_id,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            role="agent",
            body=result.reply,
            intent=result.intent,
            now=now,
            trace=[asdict(entry) | {"status": str(entry.status)} for entry in result.trace],
            citations=[asdict(citation) for citation in result.citations],
            directives=[asdict(directive) for directive in result.directives],
        )

    return TurnRead(
        conversation_id=conversation_id,
        message_id=message_id,
        intent=result.intent,
        reply=result.reply,
        code=result.code,
        outcome=result.outcome,
        degraded=result.degraded,
        trace=[asdict(entry) | {"status": str(entry.status)} for entry in result.trace],
        citations=[asdict(citation) for citation in result.citations],
        directives=[asdict(directive) for directive in result.directives],
        pending=pending_read,
    )


def _sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"


@router.post(
    "/chat/messages/stream",
    dependencies=[Depends(declares_action(ManagementAction.CHAT_MESSAGE_STREAM))],
)
async def stream_chat_message(
    payload: ChatMessageCreate,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> StreamingResponse:
    """One turn as content-free activity events followed by the stored answer."""
    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    def emit(event: str, data: dict[str, Any]) -> None:
        queue.put_nowait((event, data))

    async def complete() -> None:
        emit("turn.started", {"status": "running"})
        try:
            turn = await _complete_chat_turn(
                payload=payload,
                session=session,
                sessionmaker=sessionmaker,
                activity=emit,
            )
            emit("turn.completed", turn.model_dump(mode="json"))
        except Exception:  # noqa: BLE001 - the stream must end with a safe terminal event
            emit("turn.failed", {"code": "chat_agent_unavailable"})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(complete())

    async def events():  # noqa: ANN202 - StreamingResponse consumes the async iterator
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield _sse(*item)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/chat/actions/{action_id}",
    response_model=ActionDecisionRead,
    dependencies=[Depends(declares_action(ManagementAction.CHAT_ACTION_DECIDE))],
)
async def decide_chat_action(
    payload: ActionDecisionCreate,
    response: Response,
    session: Annotated[Session, Depends(require_session)],
    action_id: Annotated[str, Path(max_length=64)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ActionDecisionRead:
    """Approve or discard a proposed write. The only path in this module that writes.

    **One transaction for the settle and the write**, so that a confirmed
    proposal and the prompt it created commit together. The alternative leaves a
    row saying `confirmed` beside a registry that never heard about it, which is
    the audit trail lying in the one place it must not.

    The `AND status = 'pending'` in the settle statement is what makes a double
    click a no-op: the second request changes zero rows, sees it, and answers
    `already_decided` rather than creating a second prompt.
    """
    response.headers["Cache-Control"] = "no-store"
    now = datetime.now(UTC)

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        action = await repository.load_pending_action(db, action_id, actor_id=session.user_id)
        if action is None:
            raise ManagementRefusal(
                status_code=404, code=ErrorCode.NOT_FOUND, message="no such action"
            )
        if action["status"] != "pending":
            raise ManagementRefusal(
                status_code=409,
                code=ErrorCode.CHAT_ACTION_ALREADY_DECIDED,
                message="this action has already been decided",
                details={"status": action["status"]},
            )

        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)

        outcome = await confirm_action(
            db=db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            visible=visible,
            action=action,
            approve=payload.approve,
        )

        if outcome.status == "failed":
            # The proposal stays open on a refusal. The person may be given the
            # permission and try again, and closing it would make the second
            # attempt a fresh conversation rather than a retry.
            raise ManagementRefusal(
                status_code=403 if outcome.code == "permission_denied" else 404,
                code=(
                    ErrorCode.PERMISSION_DENIED
                    if outcome.code == "permission_denied"
                    else ErrorCode.NOT_FOUND
                ),
                message="this action cannot be performed",
            )

        settled = await repository.settle_pending_action(
            db,
            action_id,
            actor_id=session.user_id,
            status="confirmed" if payload.approve else "rejected",
            now=now,
            result_prompt_id=outcome.prompt_id,
            result_version_id=outcome.version_id,
        )
        if not settled:  # pragma: no cover - the status check above wins the race
            raise ManagementRefusal(
                status_code=409,
                code=ErrorCode.CHAT_ACTION_ALREADY_DECIDED,
                message="this action has already been decided",
            )

    return ActionDecisionRead(
        id=action_id,
        status=outcome.status,
        code=outcome.code,
        prompt_id=outcome.prompt_id,
        version_id=outcome.version_id,
        directives=[asdict(directive) for directive in outcome.directives],
    )


@router.post(
    "/chat/messages/{message_id}/feedback",
    response_model=FeedbackRead,
    dependencies=[Depends(declares_action(ManagementAction.CHAT_MESSAGE_FEEDBACK))],
)
async def save_chat_feedback(
    payload: FeedbackCreate,
    response: Response,
    session: Annotated[Session, Depends(require_session)],
    message_id: Annotated[str, Path(max_length=64)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> FeedbackRead:
    """Create or replace feedback on an assistant message owned by the actor."""
    response.headers["Cache-Control"] = "no-store"
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        saved = await repository.upsert_message_feedback(
            db,
            message_id=message_id,
            actor_id=session.user_id,
            rating=payload.rating,
            reason=payload.reason,
            now=datetime.now(UTC),
        )
    if not saved:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such assistant message",
        )
    return FeedbackRead(message_id=message_id, rating=payload.rating, reason=payload.reason)


@router.get(
    "/chat/conversations",
    response_model=ConversationListRead,
    dependencies=[Depends(declares_action(ManagementAction.CHAT_CONVERSATION_LIST))],
)
async def list_chat_conversations(
    session: Annotated[Session, Depends(require_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ConversationListRead:
    """The actor's own threads. Never anybody else's, inside the workspace or not."""
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        rows = await repository.list_conversations(db, actor_id=session.user_id, limit=limit)

    return ConversationListRead(conversations=[_conversation(row) for row in rows])


@router.get(
    "/chat/conversations/{conversation_id}",
    response_model=ConversationTranscriptRead,
    dependencies=[Depends(declares_action(ManagementAction.CHAT_CONVERSATION_READ))],
)
async def read_chat_conversation(
    session: Annotated[Session, Depends(require_session)],
    conversation_id: Annotated[str, Path(max_length=64)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ConversationTranscriptRead:
    """One transcript, with its trace and its open proposal if it has one."""
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        thread = await repository.load_conversation(
            db, conversation_id, actor_id=session.user_id
        )
        if thread is None:
            raise _not_found()

        messages = await repository.load_messages(
            db, conversation_id, actor_id=session.user_id
        )
        open_action = await repository.open_pending_action(
            db, conversation_id, actor_id=session.user_id
        )

    return ConversationTranscriptRead(
        conversation=_conversation(thread),
        messages=[
            MessageRead(
                id=row["id"],
                role=row["role"],
                text=row["body"],
                intent=row["intent"],
                created_at=row["created_at"],
                trace=row["trace"] or [],
                citations=row["citations"] or [],
                directives=row["directives"] or [],
            )
            for row in messages
        ],
        pending=_pending(open_action),
    )


@router.get(
    "/chat/pipeline",
    response_model=PipelineRead,
    dependencies=[Depends(declares_action(ManagementAction.CHAT_PIPELINE_READ))],
)
async def read_chat_pipeline(
    session: Annotated[Session, Depends(require_session)],
) -> PipelineRead:
    """The shape of the assistant, so the client can draw what a turn did *not* do.

    Signed in, and that is the whole check. There is no `workspace_transaction`
    and no sessionmaker in the signature because there is no row: the response is
    `_PIPELINE`, built once at import from `domain.TOOLS`. The session dependency
    stays because the tool catalogue names what the assistant can do to prompts,
    and that is not a thing to hand an anonymous caller.
    """
    return _PIPELINE
