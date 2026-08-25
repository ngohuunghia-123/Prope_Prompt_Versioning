"""The rig every live journey shares: a workspace, a turn, an approval.

Nothing here is stubbed. The router is the real DSPy program over the real
managed instruction, the responder writes real Vietnamese, `convert_prompt`
really converts, and the database is the same PostgreSQL 17 with the same RLS
policies every other integration test runs against. That is the point: the
failure this lane exists to catch — a request the agent understood and then did
not carry out — lives in the seam between those parts, and a suite that fakes
either half cannot see it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.access_control import (
    ADMIN_ID,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import seed_prompt, seed_revision
from tests.unit import WORKSPACE_A

SESSION_ID = "ses_live_chat_000000000001"
MESSAGES = "/api/v1/chat/messages"
ACTIONS = "/api/v1/chat/actions"

#: Real prompts, from the folder the person pointed at. They are public system
#: prompts published on the internet, which is what makes them usable here:
#: A-020 forbids real corporate prompts in the pilot, and a fixture that is
#: already public is not one.
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "playgrounds" / "prompts"

INSERT_FOLDER = text(
    """
    INSERT INTO registry.folder (workspace_id, slug, name, description, color)
    VALUES (:workspace_id, :slug, :name, :description, '#4f46e5')
    """
)


def playground(stem: str) -> str:
    """One published prompt from `playgrounds/prompts`, verbatim."""
    return (PROMPTS_DIR / f"{stem}.txt").read_text(encoding="utf-8")


def cookie() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def seed_person(migrate_engine: AsyncEngine, *, role: str = "Owner") -> None:
    """One workspace with one Owner in it, holding a live session cookie."""
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, role)
    await seed_session(migrate_engine, SESSION_ID)


async def seed_folder(migrate_engine: AsyncEngine, slug: str, name: str, description: str = "") -> None:
    async with migrate_engine.begin() as connection:
        await connection.execute(
            INSERT_FOLDER,
            {
                "workspace_id": WORKSPACE_A,
                "slug": slug,
                "name": name,
                "description": description,
            },
        )


async def seed_registered_prompt(
    migrate_engine: AsyncEngine,
    *,
    prompt_id: str,
    namespace: str,
    name: str,
    title: str,
    purpose: str,
    body: str,
    version_id: str | None = None,
) -> str:
    """A prompt property and its first revision — what a registered prompt is."""
    await seed_prompt(
        migrate_engine,
        prompt_id=prompt_id,
        namespace=namespace,
        name=name,
        title=title,
        purpose=purpose,
        owner_id=ADMIN_ID,
    )
    await seed_revision(
        migrate_engine,
        version_id=version_id or f"rev_{prompt_id[4:]}"[:40],
        prompt_id=prompt_id,
        body=body,
    )
    return prompt_id


# ---------------------------------------------------------------------------
# One turn, and one approval
# ---------------------------------------------------------------------------


async def say(
    api: Any,
    message: str,
    *,
    attachment: str | None = None,
    attachment_format: str = "txt",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """One person's turn through the real route, and the `TurnRead` it answered."""
    body: dict[str, Any] = {"text": message}
    if attachment is not None:
        body["attachment"] = attachment
        body["attachment_format"] = attachment_format
    if conversation_id is not None:
        body["conversation_id"] = conversation_id

    response = await call(api, "POST", MESSAGES, json_body=body, headers=cookie())
    assert response.status_code == 200, response.body
    return dict(response.json())


async def approve(api: Any, action_id: str, *, edits: dict[str, str] | None = None) -> dict[str, Any]:
    """The second request the HITL gate requires. Returns `ActionDecisionRead`."""
    body: dict[str, Any] = {"approve": True}
    if edits:
        body["edits"] = edits
    response = await call(api, "POST", f"{ACTIONS}/{action_id}", json_body=body, headers=cookie())
    assert response.status_code == 200, response.body
    return dict(response.json())


async def reject(api: Any, action_id: str) -> dict[str, Any]:
    response = await call(api, "POST", f"{ACTIONS}/{action_id}", json_body={"approve": False}, headers=cookie())
    assert response.status_code == 200, response.body
    return dict(response.json())


# ---------------------------------------------------------------------------
# Reading a turn
# ---------------------------------------------------------------------------


def tools_ran(turn: dict[str, Any]) -> tuple[str, ...]:
    """The workers that executed, in order, from the turn's own trace."""
    return tuple(
        entry["agent"].removeprefix("worker.")
        for entry in turn.get("trace", ())
        if entry["agent"].startswith("worker.") and entry["action"] == "execute"
    )


def refused(turn: dict[str, Any], tool: str) -> str:
    """The reason this tool gave for not answering, or `""` if it answered.

    A read journey that asserts only "the tool ran" reports a pass for a tool
    that ran and found nothing — `list_versions` returning
    `chat_tool_not_found` scored `ok` on a real run, beside a reply that had no
    versions in it. Ran and answered are different claims and the table should
    not conflate them.
    """
    for why in refusals(turn):
        name, _, reason = why.partition("=")
        if name == tool:
            return reason
    return ""


def card(turn: dict[str, Any]) -> str | None:
    """The tool on the confirmation card this turn staged, if any."""
    pending = turn.get("pending")
    return None if pending is None else str(pending["tool"])


def refusals(turn: dict[str, Any]) -> tuple[str, ...]:
    """Every non-empty `reason` a worker put in the trace, as `tool=reason`.

    A write step that runs and stages nothing is the interesting failure, and
    `pending: null` alone does not say why. The orchestrator already records the
    reason code on each worker's trace entry (`chat_tool_no_target`,
    `chat_tool_ambiguous_target`, `chat_tool_crashed`, ...); this pulls it back
    out so the table names the cause instead of the symptom.
    """
    found: list[str] = []
    for entry in turn.get("trace", ()):
        if not entry["agent"].startswith("worker.") or entry["action"] != "execute":
            continue
        reason = str(entry.get("detail", {}).get("reason") or "")
        if reason:
            found.append(f"{entry['agent'].removeprefix('worker.')}={reason}")
    return tuple(found)


def action_id(turn: dict[str, Any]) -> str:
    pending = turn.get("pending")
    assert pending is not None, (
        f"no confirmation card: code={turn.get('code')} "
        f"why={'|'.join(refusals(turn)) or 'nothing refused'} reply={turn.get('reply', '')[:120]}"
    )
    return str(pending["id"])


async def queued_behind(migrate_engine: AsyncEngine, pending_id: str) -> tuple[str, ...]:
    """The writes riding on `chat.pending_action.remaining_steps` (migration 0044)."""
    async with migrate_engine.begin() as connection:
        row = (
            await connection.execute(
                text("SELECT remaining_steps FROM chat.pending_action WHERE id = :id"),
                {"id": pending_id},
            )
        ).scalar_one_or_none()
    if not row:
        return ()
    return tuple(str(step.get("tool", "")) for step in row)


# ---------------------------------------------------------------------------
# Reading the database
# ---------------------------------------------------------------------------


async def one(migrate_engine: AsyncEngine, statement: str, **params: Any) -> Any:
    async with migrate_engine.begin() as connection:
        return (await connection.execute(text(statement), params)).mappings().first()


async def rows(migrate_engine: AsyncEngine, statement: str, **params: Any) -> list[Any]:
    async with migrate_engine.begin() as connection:
        return list((await connection.execute(text(statement), params)).mappings().all())


PROMPT_ROW = "SELECT namespace, name, title, purpose, status FROM registry.prompt_property WHERE id = :id"
FOLDER_ROWS = "SELECT slug, name FROM registry.folder ORDER BY slug"
REVISION_ROWS = (
    "SELECT revision_number, status, change_summary, body FROM registry.revision "
    "WHERE prompt_id = :id ORDER BY revision_number"
)
PROMPT_COUNT = "SELECT count(*) AS n FROM registry.prompt_property"
