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

import structlog
from fastapi import APIRouter, Depends, Path, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from prope.access_control.seams import Actor, ActorType, SubjectType, visible_subject_filter
from prope.agent_run import repository as agent_run_repository
from prope.agent_run.domain import PlanBasis, RunKind
from prope.chat_orchestrator import observability, repository, tools_registry
from prope.chat_orchestrator.domain import TOOLS, Intent
from prope.chat_orchestrator.orchestrator import (
    TurnRequest,
    confirm_action,
    decision_message,
    run_queued_step,
    run_turn,
    unique_import_identity,
)
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

logger = structlog.get_logger(__name__)

#: `intent -> the catalogue key the client renders as the thread's title`. The
#: thread list must not carry a title derived from what somebody typed, so it
#: carries what the assistant decided the thread was about instead.
_TITLE_CODES = {
    Intent.SEARCH: "chat.thread.search",
    Intent.DUPLICATE_CHECK: "chat.thread.duplicate_check",
    Intent.IMPORT_PROMPT: "chat.thread.import_prompt",
    Intent.DOCS_QUESTION: "chat.thread.docs_question",
    Intent.MANAGE_PROMPT: "chat.thread.manage_prompt",
    Intent.MANAGE_FOLDER: "chat.thread.manage_folder",
    Intent.MANAGE_KEYS: "chat.thread.manage_keys",
    Intent.MANAGE_PROVIDERS: "chat.thread.manage_providers",
    Intent.RUN_EVALUATION: "chat.thread.run_evaluation",
    Intent.CHECK_STATUS: "chat.thread.check_status",
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
    return Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id)


def _not_found() -> ManagementRefusal:
    return ManagementRefusal(status_code=404, code=ErrorCode.NOT_FOUND, message="no such conversation")


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
        id=row["id"],
        tool=row["tool"],
        summary=row["summary"],
        preview=row["preview"] or {},
        run_id=row.get("run_id"),
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
    agent_run_id: str | None = None

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)

        conversation_id = payload.conversation_id
        history: list[str] = []
        decided_actions: list[dict[str, Any]] = []
        resume_source: dict[str, str] | None = None
        thread_entities: list[dict[str, str]] = []
        if conversation_id is not None:
            thread = await repository.load_conversation(db, conversation_id, actor_id=session.user_id)
            if thread is None:
                raise _not_found()
            history, decided_actions, resume_source, thread_entities = await _thread_context(
                db, conversation_id=conversation_id, actor_id=session.user_id, visible=visible
            )
        run_kind = RunKind.IMPORT if payload.attachment is not None else RunKind.CHAT
        agent_run_id = await agent_run_repository.create_run(
            db,
            workspace_id=session.workspace_id,
            requested_by=session.user_id,
            kind=run_kind,
            plan_basis=PlanBasis.LLM,
            idempotency_key=f"chat-{run_kind.value}:{ULID()}",
        )
        await agent_run_repository.start_inline_run(
            db,
            workspace_id=session.workspace_id,
            run_id=agent_run_id,
        )

    if agent_run_id is not None and activity is not None:
        activity("run.accepted", {"run_id": agent_run_id, "status": "queued"})
        activity("run.updated", {"run_id": agent_run_id, "status": "running"})

    def open_db():  # noqa: ANN202 - an inline factory, see TurnRequest.open_db
        return workspace_transaction(sessionmaker, session.workspace_id)

    try:
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
                decided_actions=decided_actions,
                thread_entities=thread_entities,
                carried_attachment=(
                    resume_source["attachment"] if resume_source is not None and payload.attachment is None else None
                ),
                carried_attachment_format=(
                    (resume_source.get("format") or "txt")
                    if resume_source is not None and payload.attachment is None
                    else "txt"
                ),
                activity=activity,
            )
        )
    except Exception:
        async with workspace_transaction(sessionmaker, session.workspace_id) as db:
            await agent_run_repository.fail_inline_run(
                db,
                workspace_id=session.workspace_id,
                run_id=agent_run_id,
            )
        raise

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
        message_id, pending_read = await _persist_turn(
            db,
            result=result,
            conversation_id=conversation_id,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            now=now,
            user_text=payload.text,
            run_id=agent_run_id,
        )
        if agent_run_id is not None:
            await agent_run_repository.finish_inline_run(
                db,
                workspace_id=session.workspace_id,
                run_id=agent_run_id,
                evidence_refs=(f"message:{message_id}",),
                waiting_for_user=result.pending is not None,
            )

    return _turn_read(
        result=result,
        conversation_id=conversation_id,
        message_id=message_id,
        pending_read=pending_read,
        run_id=agent_run_id,
    )


def _sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"


async def _thread_context(
    db: Any,
    *,
    conversation_id: str,
    actor_id: str,
    visible: Any = None,
) -> tuple[list[str], list[dict[str, Any]], dict[str, str] | None, list[dict[str, str]]]:
    """What a turn resumes from: history, decided writes, carried source, entities.

    `visible` (the turn's visibility filter) enables the fourth item — the
    workspace's recently touched prompts and folders. Without it only the
    conversation-scoped context loads.
    """
    history = await repository.recent_user_messages(db, conversation_id, actor_id=actor_id)
    decided_actions = await repository.recent_decided_actions(db, conversation_id, actor_id=actor_id)
    resume_source = await repository.load_resume_source(db, conversation_id, actor_id=actor_id)
    thread_entities: list[dict[str, str]] = []
    if visible is not None:
        thread_entities = await tools_registry.thread_entities(
            db, actor_id=actor_id, visible=visible
        )
    return history, decided_actions, resume_source, thread_entities


async def _persist_turn(
    db: Any,
    *,
    result: Any,
    conversation_id: str,
    workspace_id: str,
    actor_id: str,
    now: datetime,
    user_text: str | None,
    run_id: str | None,
) -> tuple[str, PendingActionRead | None]:
    """Store one settled turn: optional user line, any proposal, the agent reply.

    Shared by the message route and the decision continuation — the difference
    is entirely in what came *before* the agent spoke, so that is the part this
    helper takes as a flag rather than re-implementing.
    """
    if user_text is not None:
        await repository.append_message(
            db,
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            actor_id=actor_id,
            role="user",
            body=user_text,
            now=now,
            run_id=run_id,
        )

    pending_read: PendingActionRead | None = None
    if result.pending is not None:
        action_id = await repository.propose_action(
            db,
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            actor_id=actor_id,
            tool=result.pending.tool,
            summary=result.pending.summary,
            preview=result.pending.preview,
            arguments=result.pending.arguments,
            now=now,
            run_id=run_id,
            resume_attachment=result.pending.resume_attachment,
            resume_attachment_format=result.pending.resume_attachment_format,
            remaining_steps=result.pending.remaining_steps,
        )
        pending_read = PendingActionRead(
            id=action_id,
            tool=result.pending.tool,
            summary=result.pending.summary,
            preview=result.pending.preview,
            run_id=run_id,
        )
        observability.pending_action_total.labels(decision="proposed").inc()

    message_id = await repository.append_message(
        db,
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        actor_id=actor_id,
        role="agent",
        body=result.reply,
        intent=result.intent,
        now=now,
        trace=[asdict(entry) | {"status": str(entry.status)} for entry in result.trace],
        citations=[asdict(citation) for citation in result.citations],
        directives=[asdict(directive) for directive in result.directives],
        run_id=run_id,
    )
    return message_id, pending_read


def _turn_read(
    *,
    result: Any,
    conversation_id: str,
    message_id: str,
    pending_read: PendingActionRead | None,
    run_id: str | None,
) -> TurnRead:
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
        run_id=run_id,
    )


#: Which proposal fields a person may correct on the card, per tool. Closed on
#: purpose: `body`, `access_level` and every other argument stay exactly as
#: proposed, because the review is about those, not a chance to rewrite them.
_EDITABLE_FIELDS: Final[dict[str, frozenset[str]]] = {
    "create_prompt": frozenset({"title", "name"}),
}


async def _apply_action_edits(
    db: Any,
    *,
    action_id: str,
    actor_id: str,
    action: dict[str, Any],
    edits: dict[str, str],
) -> None:
    """Fold a person's card corrections into the proposal before it runs.

    Whitelisted per tool; anything else — another tool, an unknown field, an
    empty title — refuses rather than guessing. The name is re-slugged with the
    same deterministic function that built the original and re-checked against
    the registry (with the `-2`, `-3`… walk), so an edited approval lands on a
    free identity or a *named* refusal instead of a 409 after the fact. The
    patch persists inside the settle transaction, keeping approved == executed.
    """
    from prope.chat_orchestrator import tools

    tool = str(action["tool"])
    allowed = _EDITABLE_FIELDS.get(tool)
    if allowed is None or not set(edits) <= allowed:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.CHAT_ACTION_EDIT_NOT_ALLOWED,
            message="these fields are not editable",
            details={"tool": tool, "editable": sorted(allowed) if allowed else []},
        )

    arguments = dict(action["arguments"] or {})
    preview = dict(action["preview"] or {})

    title = str(edits.get("title") or arguments.get("title") or "").strip()[:200]
    raw_name = str(edits.get("name") or "").strip()
    if not title or (edits.get("name") is not None and not raw_name):
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.CHAT_ACTION_EDIT_NOT_ALLOWED,
            message="an editable field was empty",
            details={"fields": sorted(edits)},
        )

    namespace = str(arguments.get("namespace", "imported"))
    slug = tools.slugify(raw_name) if raw_name else tools.slugify(title)

    identity = await unique_import_identity(db, namespace=namespace, slug=slug, title=title)
    if identity is None:
        raise ManagementRefusal(
            status_code=409,
            code=ErrorCode.REGISTRY_MODEL_NAME_TAKEN,
            message="every suggested prompt name is taken",
            details={"namespace": namespace},
        )
    final_slug, final_title = identity

    arguments["name"], arguments["title"] = final_slug, final_title
    preview["name"], preview["title"] = final_slug, final_title

    persisted = await repository.update_pending_action_payload(
        db, action_id, actor_id=actor_id, arguments=arguments, preview=preview
    )
    if not persisted:
        raise ManagementRefusal(
            status_code=409,
            code=ErrorCode.CHAT_ACTION_ALREADY_DECIDED,
            message="this action has already been decided",
        )
    action["arguments"], action["preview"] = arguments, preview


async def _complete_queued_turn(
    *,
    step: dict[str, Any],
    remaining: list[dict[str, Any]],
    action: dict[str, Any],
    session: Session,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> TurnRead:
    """Run the next queued write of a multi-write plan and persist its card.

    Deterministic by design: the tool and arguments were fixed when the router
    planned the task, so the continuation executes rather than re-asks. The
    card it stages carries whatever queue is left, which is how "rename it and
    put it in a new folder" finishes in two approvals without a second request.
    """
    conversation_id = str(action["conversation_id"])

    def open_db():  # noqa: ANN202 - an inline factory, see TurnRequest.open_db
        return workspace_transaction(sessionmaker, session.workspace_id)

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)
        thread_entities = await tools_registry.thread_entities(
            db, actor_id=session.user_id, visible=visible
        )

    result = await run_queued_step(
        open_db=open_db,
        workspace_id=session.workspace_id,
        actor_id=session.user_id,
        visible=visible,
        conversation_id=conversation_id,
        step=step,
        remaining=remaining,
        thread_entities=thread_entities,
    )
    observability.continuation_total.inc()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        message_id, pending_read = await _persist_turn(
            db,
            result=result,
            conversation_id=conversation_id,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            now=datetime.now(UTC),
            user_text=None,
            run_id=None,
        )

    return _turn_read(
        result=result,
        conversation_id=conversation_id,
        message_id=message_id,
        pending_read=pending_read,
        run_id=None,
    )


async def _complete_decision_turn(
    *,
    action: dict[str, Any],
    approve: bool,
    written: dict[str, Any] | None,
    session: Session,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> TurnRead:
    """The automatic turn that picks the task back up after a human decision.

    **Why it exists.** A write proposal ends its plan by design — the card is
    the answer — and everything the plan still owed ("…then run the eval suite")
    used to die there. The person's approve/reject is itself an instruction to
    carry on, so the settle commits and this runs: routing on a trusted
    HUMAN_DECISION marker plus the thread's freshly updated `decided_actions`
    (which is also what keeps the continuation from repeating the write — the
    deterministic suppression in the orchestrator handles the rest). It opens
    its own transactions exactly like a message turn; nothing here shares a
    transaction with the settle.
    """
    conversation_id = str(action["conversation_id"])
    marker = decision_message(tool=str(action["tool"]), approve=approve, written=written)

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)
        history, decided_actions, resume_source, thread_entities = await _thread_context(
            db, conversation_id=conversation_id, actor_id=session.user_id, visible=visible
        )

    def open_db():  # noqa: ANN202 - an inline factory, see TurnRequest.open_db
        return workspace_transaction(sessionmaker, session.workspace_id)

    result = await run_turn(
        TurnRequest(
            open_db=open_db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            visible=visible,
            conversation_id=conversation_id,
            message=marker,
            history=history,
            decided_actions=decided_actions,
            thread_entities=thread_entities,
            carried_attachment=(resume_source["attachment"] if resume_source is not None else None),
            carried_attachment_format=((resume_source.get("format") or "txt") if resume_source is not None else "txt"),
            trigger="decision",
            decision={"tool": str(action["tool"]), "approve": approve},
            activity=None,
        )
    )
    observability.continuation_total.inc()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        message_id, pending_read = await _persist_turn(
            db,
            result=result,
            conversation_id=conversation_id,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            now=datetime.now(UTC),
            user_text=None,
            run_id=None,
        )

    return _turn_read(
        result=result,
        conversation_id=conversation_id,
        message_id=message_id,
        pending_read=pending_read,
        run_id=None,
    )


@router.post(
    "/chat/messages/stream",
    dependencies=[Depends(declares_action(ManagementAction.CHAT_MESSAGE_SEND_STREAM))],
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
            if turn.run_id is not None:
                emit(
                    "run.waiting_for_user" if turn.pending is not None else "run.completed",
                    {
                        "run_id": turn.run_id,
                        "status": "waiting_for_user" if turn.pending is not None else "succeeded",
                    },
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

    **The continuation runs after that transaction commits**, never inside it:
    it opens its own transactions and makes model calls, and holding the settle's
    pooled connection across those would starve every other route. A decision
    response therefore answers twice — what the decision did, then what the agent
    did about it — which is exactly the shape of the work.
    """
    response.headers["Cache-Control"] = "no-store"
    now = datetime.now(UTC)

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        action = await repository.load_pending_action(db, action_id, actor_id=session.user_id)
        if action is None:
            raise ManagementRefusal(status_code=404, code=ErrorCode.NOT_FOUND, message="no such action")
        if action["status"] != "pending":
            raise ManagementRefusal(
                status_code=409,
                code=ErrorCode.CHAT_ACTION_ALREADY_DECIDED,
                message="this action has already been decided",
                details={"status": action["status"]},
            )

        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)

        if payload.edits:
            await _apply_action_edits(db, action_id=action_id, actor_id=session.user_id, action=action, edits=payload.edits)

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
                code=(ErrorCode.PERMISSION_DENIED if outcome.code == "permission_denied" else ErrorCode.NOT_FOUND),
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
        if action.get("run_id") is not None:
            await agent_run_repository.finish_inline_run(
                db,
                workspace_id=session.workspace_id,
                run_id=str(action["run_id"]),
                evidence_refs=(f"action:{action_id}",),
                waiting_for_user=False,
            )

    written: dict[str, Any] | None = None
    if payload.approve:
        written = {
            key: value
            for key, value in (
                ("prompt_id", outcome.prompt_id),
                ("version_id", outcome.version_id),
            )
            if value
        }

    continuation: TurnRead | None = None
    try:
        queue = [step for step in (action.get("remaining_steps") or []) if isinstance(step, dict)]
        if payload.approve and queue:
            # The approved proposal was one card in a multi-write plan. Run the
            # next queued step directly — no router, no re-derivation — with the
            # rest of the queue attached to its own card.
            continuation = await _complete_queued_turn(
                step=queue[0],
                remaining=queue[1:],
                action=action,
                session=session,
                sessionmaker=sessionmaker,
            )
        else:
            continuation = await _complete_decision_turn(
                action=action,
                approve=payload.approve,
                written=written,
                session=session,
                sessionmaker=sessionmaker,
            )
    except Exception:  # noqa: BLE001 - the settlement stands even if its follow-up fell
        logger.exception("chat_orchestrator.continuation_failed")

    return ActionDecisionRead(
        id=action_id,
        status=outcome.status,
        code=outcome.code,
        prompt_id=outcome.prompt_id,
        version_id=outcome.version_id,
        secret_once=outcome.secret_once,
        directives=[asdict(directive) for directive in outcome.directives],
        continuation=continuation,
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
        thread = await repository.load_conversation(db, conversation_id, actor_id=session.user_id)
        if thread is None:
            raise _not_found()

        messages = await repository.load_messages(db, conversation_id, actor_id=session.user_id)
        open_action = await repository.open_pending_action(db, conversation_id, actor_id=session.user_id)

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
                run_id=row.get("run_id"),
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
