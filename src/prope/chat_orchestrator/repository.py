"""Every read and write for chat-orchestrator. Raw SQL, bound parameters only.

Two rules from elsewhere in the project apply here without amendment.

**Ownership filtering lives in this module, not in a handler** (A-118, T-019).
Every statement below that reads a conversation, a message, or a pending action
carries `actor_id = :actor_id` in its `WHERE`. Row-level security already answers
*which workspace*; this answers *whose thread*, and a workspace-mate reading
somebody else's conversation with the assistant is a disclosure the tenant policy
would happily permit. Nothing here takes a "skip the owner check" flag.

**No interpolation of any kind**, per `prope.db.session`'s module docstring and
the source gate that enforces it: every `text(...)` argument in this file is a
plain string constant and every value arrives as a bound parameter.
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

__all__ = [
    "ACTION_ID_PREFIX",
    "CONVERSATION_ID_PREFIX",
    "MESSAGE_ID_PREFIX",
    "append_message",
    "create_conversation",
    "load_conversation",
    "load_messages",
    "load_pending_action",
    "list_conversations",
    "open_pending_action",
    "propose_action",
    "recent_tool_activity",
    "recent_user_messages",
    "settle_pending_action",
    "upsert_message_feedback",
]

CONVERSATION_ID_PREFIX = "cnv_"
MESSAGE_ID_PREFIX = "msg_"
ACTION_ID_PREFIX = "pac_"


INSERT_CONVERSATION = text(
    """
    INSERT INTO chat.conversation
        (id, workspace_id, actor_id, title_code, created_at, updated_at, message_count)
    VALUES
        (:id, :workspace_id, :actor_id, :title_code, :now, :now, 0)
    """
)

TOUCH_CONVERSATION = text(
    """
    UPDATE chat.conversation
    SET    updated_at = :now,
           message_count = message_count + :added
    WHERE  id = :id AND actor_id = :actor_id
    """
)

SELECT_CONVERSATION = text(
    """
    SELECT id, workspace_id, actor_id, title_code, created_at, updated_at, message_count
    FROM   chat.conversation
    WHERE  id = :id AND actor_id = :actor_id
    """
)

LIST_CONVERSATIONS = text(
    """
    SELECT id, title_code, created_at, updated_at, message_count
    FROM   chat.conversation
    WHERE  actor_id = :actor_id
    ORDER  BY updated_at DESC, id DESC
    LIMIT  :limit
    """
)

INSERT_MESSAGE = text(
    """
    INSERT INTO chat.message
        (id, conversation_id, workspace_id, actor_id, role, body, intent,
         trace, citations, directives, attachment_format, run_id, created_at)
    VALUES
        (:id, :conversation_id, :workspace_id, :actor_id, :role, :body, :intent,
         CAST(:trace AS jsonb), CAST(:citations AS jsonb), CAST(:directives AS jsonb),
         :attachment_format, :run_id, :now)
    """
)

SELECT_MESSAGES = text(
    """
    SELECT m.id, m.role, m.body, m.intent, m.trace, m.citations, m.directives,
           m.attachment_format, m.run_id, m.created_at
    FROM   chat.message m
    JOIN   chat.conversation c ON c.id = m.conversation_id
    WHERE  m.conversation_id = :conversation_id AND c.actor_id = :actor_id
    ORDER  BY m.created_at, m.id
    LIMIT  :limit
    """
)

#: The router's context window over the thread. **Only the person's own turns.**
#: Including the agent's replies would feed the model its own output as history,
#: which is how a single early misrouting becomes the theme of a conversation —
#: and the agent's reply adds nothing the router needs to resolve "that one".
SELECT_RECENT_USER_MESSAGES = text(
    """
    SELECT body
    FROM   (
        SELECT m.body, m.created_at, m.id
        FROM   chat.message m
        JOIN   chat.conversation c ON c.id = m.conversation_id
        WHERE  m.conversation_id = :conversation_id
          AND  c.actor_id = :actor_id
          AND  m.role = 'user'
        ORDER  BY m.created_at DESC, m.id DESC
        LIMIT  :limit
    ) AS recent
    ORDER BY recent.created_at, recent.id
    """
)

#: The thread's decided proposals, oldest first. This is how a follow-up turn
#: knows what already happened: "continue" after a confirmed folder creation
#: must finish the import, not ask for the folder twice.
SELECT_RECENT_DECIDED_ACTIONS = text(
    """
    SELECT tool, arguments, status, decided_at, result_prompt_id
    FROM   (
        SELECT tool, arguments, status, decided_at, result_prompt_id, created_at, id
        FROM   chat.pending_action
        WHERE  conversation_id = :conversation_id
          AND  actor_id = :actor_id
          AND  status IN ('confirmed', 'rejected')
        ORDER  BY created_at DESC, id DESC
        LIMIT  :limit
    ) AS recent
    ORDER BY recent.created_at, recent.id
    """
)

#: The traces of this thread's recent agent turns, oldest first. Unlike the two
#: fields above this is the only memory of a *read*: `recent_decided_actions`
#: carries writes and only the confirmed ones, and the history field carries the
#: person's own words. What tool ran last turn — `search_prompts`, a
#: `delete_folder` that a card approved — lives only in `chat.message.trace`,
#: which is otherwise read back solely to draw the client's timeline. A follow-up
#: turn that runs no tool of its own ("what did you just do?") has nothing to
#: answer from without it. The trace was already reduced to counts and
#: identifiers by `observability.safe_detail` before it was stored, so nothing
#: content-bearing rides back out here.
SELECT_RECENT_AGENT_TRACES = text(
    """
    SELECT trace
    FROM   (
        SELECT m.trace, m.created_at, m.id
        FROM   chat.message m
        JOIN   chat.conversation c ON c.id = m.conversation_id
        WHERE  m.conversation_id = :conversation_id
          AND  c.actor_id = :actor_id
          AND  m.role = 'agent'
        ORDER  BY m.created_at DESC, m.id DESC
        LIMIT  :limit
    ) AS recent
    ORDER BY recent.created_at, recent.id
    """
)

#: The source body the most recently confirmed proposal carried, when it did.
#: A follow-up turn with no attachment of its own resumes from here rather than
#: asking the person to paste what they already gave.
SELECT_LAST_RESUME_SOURCE = text(
    """
    SELECT resume_attachment AS attachment, resume_attachment_format AS format
    FROM   chat.pending_action
    WHERE  conversation_id = :conversation_id
      AND  actor_id = :actor_id
      AND  status = 'confirmed'
      AND  resume_attachment IS NOT NULL
    ORDER  BY decided_at DESC NULLS LAST, created_at DESC, id DESC
    LIMIT  1
    """
)

INSERT_PENDING_ACTION = text(
    """
    INSERT INTO chat.pending_action
        (id, conversation_id, workspace_id, actor_id, tool, summary,
         preview, arguments, status, run_id, created_at,
         resume_attachment, resume_attachment_format, remaining_steps)
    VALUES
        (:id, :conversation_id, :workspace_id, :actor_id, :tool, :summary,
         CAST(:preview AS jsonb), CAST(:arguments AS jsonb), 'pending', :run_id, :now,
         :resume_attachment, :resume_attachment_format, CAST(:remaining_steps AS jsonb))
    """
)

SELECT_PENDING_ACTION = text(
    """
    SELECT id, conversation_id, workspace_id, actor_id, tool, summary,
           preview, arguments, status, created_at, decided_at,
           result_prompt_id, result_version_id, run_id,
           resume_attachment, resume_attachment_format, remaining_steps
    FROM   chat.pending_action
    WHERE  id = :id AND actor_id = :actor_id
    """
)

SELECT_OPEN_PENDING_ACTION = text(
    """
    SELECT id, tool, summary, preview, arguments, run_id
    FROM   chat.pending_action
    WHERE  conversation_id = :conversation_id
      AND  actor_id = :actor_id
      AND  status = 'pending'
    ORDER  BY created_at DESC, id DESC
    LIMIT  1
    """
)

#: **`AND status = 'pending'` is what makes a double confirmation a no-op.**
#: Two clicks on one card race, and without this clause the second would settle
#: an already-settled row and the caller would run the write twice. The statement
#: reports how many rows it changed, and zero means somebody else got there
#: first — which is a fact the handler must see rather than a silent success.
SETTLE_PENDING_ACTION = text(
    """
    UPDATE chat.pending_action
    SET    status = :status,
           decided_at = :now,
           result_prompt_id = :result_prompt_id,
           result_version_id = :result_version_id
    WHERE  id = :id AND actor_id = :actor_id AND status = 'pending'
    """
)

#: The person corrected an editable proposal on its card (an import's title or
#: name). Persisted **before** execution inside the settle transaction, so the
#: audit trail — arguments, preview, what ran — stays byte-identical to what was
#: approved. Same `AND status = 'pending'` race guard as the settle.
UPDATE_PENDING_ACTION_PAYLOAD = text(
    """
    UPDATE chat.pending_action
    SET    arguments = CAST(:arguments AS jsonb),
           preview = CAST(:preview AS jsonb)
    WHERE  id = :id AND actor_id = :actor_id AND status = 'pending'
    """
)

UPSERT_MESSAGE_FEEDBACK = text(
    """
    INSERT INTO chat.message_feedback
        (message_id, workspace_id, actor_id, rating, reason, created_at, updated_at)
    SELECT m.id, m.workspace_id, :actor_id, :rating, :reason, :now, :now
    FROM   chat.message m
    JOIN   chat.conversation c ON c.id = m.conversation_id
    WHERE  m.id = :message_id
      AND  m.role = 'agent'
      AND  c.actor_id = :actor_id
    ON CONFLICT (message_id, actor_id) DO UPDATE
    SET rating = EXCLUDED.rating,
        reason = EXCLUDED.reason,
        updated_at = EXCLUDED.updated_at
    RETURNING message_id
    """
)


async def create_conversation(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    title_code: str,
    now: datetime,
) -> str:
    """Open a thread and return its id."""
    conversation_id = f"{CONVERSATION_ID_PREFIX}{ULID()}"
    await db.execute(
        INSERT_CONVERSATION,
        {
            "id": conversation_id,
            "workspace_id": workspace_id,
            "actor_id": actor_id,
            "title_code": title_code,
            "now": now,
        },
    )
    return conversation_id


async def load_conversation(
    db: AsyncSession, conversation_id: str, *, actor_id: str
) -> dict[str, Any] | None:
    """One thread the actor owns, or `None`.

    `None` covers both "no such thread" and "somebody else's thread", and the
    caller turns both into the same 404 — BR-01's shape, one layer up from
    prompts: a distinguishable refusal is a confirmation that the thread exists.
    """
    row = (
        await db.execute(SELECT_CONVERSATION, {"id": conversation_id, "actor_id": actor_id})
    ).mappings().first()
    return dict(row) if row else None


async def list_conversations(
    db: AsyncSession, *, actor_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    """The actor's threads, newest activity first."""
    rows = (
        await db.execute(LIST_CONVERSATIONS, {"actor_id": actor_id, "limit": limit})
    ).mappings().all()
    return [dict(row) for row in rows]


async def append_message(
    db: AsyncSession,
    *,
    conversation_id: str,
    workspace_id: str,
    actor_id: str,
    role: str,
    body: str,
    now: datetime,
    intent: str | None = None,
    trace: list[dict[str, Any]] | None = None,
    citations: list[dict[str, Any]] | None = None,
    directives: list[dict[str, Any]] | None = None,
    attachment_format: str | None = None,
    run_id: str | None = None,
) -> str:
    """Write one turn and move the thread's clock forward."""
    message_id = f"{MESSAGE_ID_PREFIX}{ULID()}"
    await db.execute(
        INSERT_MESSAGE,
        {
            "id": message_id,
            "conversation_id": conversation_id,
            "workspace_id": workspace_id,
            "actor_id": actor_id,
            "role": role,
            "body": body,
            "intent": intent,
            "trace": json.dumps(trace or []),
            "citations": json.dumps(citations or []),
            "directives": json.dumps(directives or []),
            "attachment_format": attachment_format,
            "run_id": run_id,
            "now": now,
        },
    )
    await db.execute(
        TOUCH_CONVERSATION,
        {"id": conversation_id, "actor_id": actor_id, "now": now, "added": 1},
    )
    return message_id


async def load_messages(
    db: AsyncSession, conversation_id: str, *, actor_id: str, limit: int = 100
) -> list[dict[str, Any]]:
    """The transcript, oldest first."""
    rows = (
        await db.execute(
            SELECT_MESSAGES,
            {"conversation_id": conversation_id, "actor_id": actor_id, "limit": limit},
        )
    ).mappings().all()
    return [dict(row) for row in rows]


async def recent_user_messages(
    db: AsyncSession, conversation_id: str, *, actor_id: str, limit: int = 4
) -> list[str]:
    """The person's last few turns, oldest first — the router's only history."""
    rows = (
        await db.execute(
            SELECT_RECENT_USER_MESSAGES,
            {"conversation_id": conversation_id, "actor_id": actor_id, "limit": limit},
        )
    ).scalars().all()
    return list(rows)


async def recent_decided_actions(
    db: AsyncSession, conversation_id: str, *, actor_id: str, limit: int = 6
) -> list[dict[str, Any]]:
    """This thread's decided proposals, oldest first — the supervisor's memory."""
    rows = (
        await db.execute(
            SELECT_RECENT_DECIDED_ACTIONS,
            {"conversation_id": conversation_id, "actor_id": actor_id, "limit": limit},
        )
    ).mappings().all()
    return [dict(row) for row in rows]


#: How much prior tool activity a follow-up turn is shown. Enough to answer
#: "what did you just do" across a couple of turns without letting the block grow
#: without bound: the last four agent turns, then their newest dozen executions.
_TOOL_ACTIVITY_TURN_LIMIT = 4
_TOOL_ACTIVITY_ENTRY_LIMIT = 12


async def recent_tool_activity(
    db: AsyncSession,
    conversation_id: str,
    *,
    actor_id: str,
    turn_limit: int = _TOOL_ACTIVITY_TURN_LIMIT,
    entry_limit: int = _TOOL_ACTIVITY_ENTRY_LIMIT,
) -> list[dict[str, str]]:
    """Which tools ran on this thread's earlier turns, oldest first.

    Distilled from the persisted, already-sanitised message traces — never their
    prose — to one record per executed worker: ``{"tool", "outcome"}``. A trace
    entry qualifies only when its agent is ``worker.<tool>`` and its action is
    ``execute``; the router, guardrail and responder spans are not tool calls and
    are skipped. This is the only channel that remembers a read, so it is what a
    turn running no tool of its own answers "what did you just do?" from.
    """
    rows = (
        await db.execute(
            SELECT_RECENT_AGENT_TRACES,
            {"conversation_id": conversation_id, "actor_id": actor_id, "limit": turn_limit},
        )
    ).scalars().all()

    activity: list[dict[str, str]] = []
    for trace in rows:
        # jsonb comes back decoded; a driver that hands back the raw string is
        # tolerated rather than trusted, since a malformed trace must never fail
        # a turn — the memory is a convenience, not a correctness invariant.
        if isinstance(trace, str):
            try:
                trace = json.loads(trace)
            except ValueError:
                continue
        for entry in trace or []:
            if not isinstance(entry, dict):
                continue
            agent = str(entry.get("agent", ""))
            if not agent.startswith("worker.") or entry.get("action") != "execute":
                continue
            detail = entry.get("detail") if isinstance(entry.get("detail"), dict) else {}
            activity.append(
                {
                    "tool": str(detail.get("tool") or agent[len("worker.") :]),
                    "outcome": str(detail.get("outcome") or entry.get("status") or ""),
                }
            )
    return activity[-entry_limit:]


async def load_resume_source(
    db: AsyncSession, conversation_id: str, *, actor_id: str
) -> dict[str, str] | None:
    """The import source a confirmed proposal carried forward, if one exists."""
    row = (
        await db.execute(
            SELECT_LAST_RESUME_SOURCE,
            {"conversation_id": conversation_id, "actor_id": actor_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def propose_action(
    db: AsyncSession,
    *,
    conversation_id: str,
    workspace_id: str,
    actor_id: str,
    tool: str,
    summary: str,
    preview: dict[str, Any],
    arguments: dict[str, Any],
    now: datetime,
    run_id: str | None = None,
    resume_attachment: str | None = None,
    resume_attachment_format: str | None = None,
    remaining_steps: list[dict[str, Any]] | None = None,
) -> str:
    """Record a write the agent wants to make, and return its single-use id."""
    action_id = f"{ACTION_ID_PREFIX}{ULID()}"
    await db.execute(
        INSERT_PENDING_ACTION,
        {
            "id": action_id,
            "conversation_id": conversation_id,
            "workspace_id": workspace_id,
            "actor_id": actor_id,
            "tool": tool,
            "summary": summary,
            "preview": json.dumps(preview),
            "arguments": json.dumps(arguments),
            "run_id": run_id,
            "now": now,
            "resume_attachment": resume_attachment,
            "resume_attachment_format": (
                resume_attachment_format if resume_attachment is not None else None
            ),
            "remaining_steps": json.dumps(remaining_steps or []),
        },
    )
    return action_id


async def load_pending_action(
    db: AsyncSession, action_id: str, *, actor_id: str
) -> dict[str, Any] | None:
    """One proposal, if it was made to this actor."""
    row = (
        await db.execute(SELECT_PENDING_ACTION, {"id": action_id, "actor_id": actor_id})
    ).mappings().first()
    return dict(row) if row else None


async def open_pending_action(
    db: AsyncSession, conversation_id: str, *, actor_id: str
) -> dict[str, Any] | None:
    """The thread's undecided proposal, if it has one.

    At most one is offered at a time. A thread holding two confirmation cards is
    a thread where a person can approve the wrong one, and there is no product
    reason to allow it.
    """
    row = (
        await db.execute(
            SELECT_OPEN_PENDING_ACTION,
            {"conversation_id": conversation_id, "actor_id": actor_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def update_pending_action_payload(
    db: AsyncSession,
    action_id: str,
    *,
    actor_id: str,
    arguments: dict[str, Any],
    preview: dict[str, Any],
) -> bool:
    """Persist a person's corrections to an editable proposal. `False` if settled."""
    result = await db.execute(
        UPDATE_PENDING_ACTION_PAYLOAD,
        {
            "id": action_id,
            "actor_id": actor_id,
            "arguments": json.dumps(arguments),
            "preview": json.dumps(preview),
        },
    )
    return bool(result.rowcount)


async def settle_pending_action(
    db: AsyncSession,
    action_id: str,
    *,
    actor_id: str,
    status: str,
    now: datetime,
    result_prompt_id: str | None = None,
    result_version_id: str | None = None,
) -> bool:
    """Close a proposal. `False` when it was already closed by somebody else."""
    result = await db.execute(
        SETTLE_PENDING_ACTION,
        {
            "id": action_id,
            "actor_id": actor_id,
            "status": status,
            "now": now,
            "result_prompt_id": result_prompt_id,
            "result_version_id": result_version_id,
        },
    )
    return bool(result.rowcount)


async def upsert_message_feedback(
    db: AsyncSession,
    *,
    message_id: str,
    actor_id: str,
    rating: str,
    reason: str | None,
    now: datetime,
) -> bool:
    """Record or replace the actor's feedback when they own the agent message."""
    row = (
        await db.execute(
            UPSERT_MESSAGE_FEEDBACK,
            {
                "message_id": message_id,
                "actor_id": actor_id,
                "rating": rating,
                "reason": reason,
                "now": now,
            },
        )
    ).scalar_one_or_none()
    return row is not None
