"""Registry executors: prompts, versions and folders behind the catalogue.

Same contract as `tools.py`: one narrow capability each, stateless between
calls, local failure returned as `outcome="error"` rather than raised. The
visibility gate below is the same one the search box runs behind — **the
assistant cannot see a prompt the person cannot see** — and a prompt that fails
it answers `not_found`, never `forbidden`, so this surface cannot become an
oracle for which prompt ids exist (A-116's shape, applied to reads).
"""

from datetime import UTC, datetime
from typing import Any

from prope.chat_orchestrator import tools
from prope.chat_orchestrator.domain import ToolName

__all__ = [
    "ambiguous_result",
    "execute_create_folder",
    "execute_delete_folder",
    "execute_move_prompt",
    "execute_rename_folder",
    "execute_retire_prompt",
    "execute_update_prompt",
    "propose_create_folder",
    "propose_delete_folder",
    "propose_drafted_revision",
    "propose_move_prompt",
    "propose_rename_folder",
    "propose_retire_prompt",
    "propose_update_prompt",
    "folder_candidates_result",
    "resolve_folder_candidates",
    "resolve_prompt",
    "resolve_prompt_candidates",
    "run_get_prompt",
    "run_get_release_status",
    "run_list_folders",
    "run_list_versions",
    "run_list_folders_rows",
    "thread_entities",
]

#: How many revisions and folders one read reports. Same reasoning as
#: `tools.SEARCH_LIMIT`: the answer is prose, the full page is one navigate away.
VERSIONS_LIMIT = 5
FOLDERS_LIMIT = 5

#: Below this a name-shaped reference ("the refund prompt") stops being treated
#: as resolved by search. Lower than search's own tier because a wrong prompt is
#: worse than an unresolved one here: every downstream act lands on this row.
RESOLVE_SIMILARITY_FLOOR = 0.5


# ---------------------------------------------------------------------------
# The shared gate
# ---------------------------------------------------------------------------


async def _readable(context: tools.ToolContext, row: Any) -> bool:
    """`prompt.read` against the row the caller already read (ADR-0020's shape)."""
    from prope.access_control.actions import Action
    from prope.access_control.seams import (
        AccessLevel,
        Actor,
        ActorType,
        Subject,
        SubjectType,
        may,
    )

    actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
    subject = Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        namespace=row.namespace,
    )
    return bool(await may(context.db, actor, Action.PROMPT_READ, subject))


async def resolve_prompt_candidates(context: tools.ToolContext, reference: str, *, limit: int = 3) -> list[Any]:
    """Every visible prompt the reference could name, best first.

    The disambiguation primitive. An exact id or ``namespace/name`` match is
    unambiguous and returns that one row; anything fuzzier goes through one
    semantic search and keeps every hit above :data:`RESOLVE_SIMILARITY_FLOOR`
    that the person may read — "the 3d prompt" matching three prompts must ask,
    not guess, because every downstream act lands on whichever row wins.
    """
    from prope.prompt_registry import repository as registry_repository

    ref = reference.strip()
    if not ref:
        return []

    row = await registry_repository.load_prompt(context.db, ref)
    if row is not None:
        return [row] if await _readable(context, row) else []

    if "/" in ref:
        namespace, _, name = ref.partition("/")
        if namespace.strip() and name.strip():
            row = await registry_repository.load_prompt_by_model_name(context.db, namespace.strip(), name.strip())
            if row is not None:
                return [row] if await _readable(context, row) else []

    try:
        from prope.prompt_search.agent.search import semantic_search

        results = await semantic_search(
            db=context.db,
            query=ref,
            workspace_id=context.workspace_id,
            visible=context.visible,
            actor_id=context.actor_id,
            cursor=None,
            limit=limit,
        )
    except Exception:
        return []

    rows: list[Any] = []
    for result in results:
        if result.similarity is None or result.similarity < RESOLVE_SIMILARITY_FLOOR:
            continue
        hit = await registry_repository.load_prompt(context.db, result.prompt_id)
        if hit is not None and await _readable(context, hit):
            rows.append(hit)
    return rows


async def resolve_prompt(context: tools.ToolContext, reference: str) -> Any | None:
    """Turn whatever the person called the prompt into its visible row, or `None`.

    Three shapes in priority order: the id itself, the immutable
    ``namespace/name``, then one semantic search whose best hit must clear a
    floor — because every act downstream lands on this row, and a wrong prompt is
    worse than an unresolved one. ``None`` covers "no such prompt", "one you may
    not see", **and now "more than one plausible answer"**: a resolver that
    guessed through ambiguity made every downstream act land on a silent choice.
    Steps that want to *ask* instead of refusing call
    :func:`resolve_prompt_candidates` directly.
    """
    rows = await resolve_prompt_candidates(context, reference)
    return rows[0] if len(rows) == 1 else None


#: How many of the `limit` thread-state slots folders may not be pushed out of.
#: See :func:`thread_entities` — this is the whole reason it does not simply
#: sort by recency.
FOLDER_SHARE = 2


async def thread_entities(
    db: Any, *, actor_id: str, visible: Any, limit: int = 4, folder_share: int = FOLDER_SHARE
) -> list[dict[str, str]]:
    """What this workspace holds, as the router's `thread_state`.

    The newest prompts (visibility-filtered, exactly as the registry list shows
    them) and the newest folders. The chat turn carries this to the router so a
    demonstrative — "đổi tên prompt ấy", "thư mục mới tạo" — resolves to a real
    id instead of sending the model hunting through prose, and so a *named*
    subject — "thư mục Marketing" — is something the model has been shown to
    exist rather than something it has to go and look for. Failures degrade to
    an empty list because a turn without memory is merely dumber, while a turn
    that raises is dead.

    **Each kind gets a reserved share of the slots, which is why this does not
    just sort by recency.** It used to: prompts and folders went into one list,
    newest first, and the top `limit` won. Four prompts touched today therefore
    pushed every folder out, and a workspace only has to be mildly active for
    that to be the normal state — at which point "Đổi tên thư mục Marketing
    thành Tăng trưởng" reaches the router describing a workspace with no
    folders in it, and a model with no reason to believe the folder exists
    plans `list_folders` to find out. The turn answers with a list, the person
    says it again. Recency is the right tie-break *within* a kind and the wrong
    one across kinds, because the kind the person is asking about is not the
    kind that was touched most recently.

    Whichever kind is short gives its slack to the other, so a workspace with no
    folders still shows `limit` prompts.
    """
    def newest(rows: list[tuple[Any, dict[str, str]]]) -> list[dict[str, str]]:
        rows.sort(key=lambda entry: entry[0], reverse=True)
        return [entry[1] for entry in rows]

    try:
        # Inside the `try` with the queries, not above it: the contract this
        # function advertises is that nothing it does can end a turn.
        from prope.prompt_registry import repository as registry_repository

        prompts = [
            (
                row.updated_at,
                {
                    "kind": "prompt",
                    "id": row.id,
                    "ref": f"{row.namespace}/{row.name} ({row.id})",
                    "label": row.title,
                },
            )
            for row in await registry_repository.list_prompts(
                db, actor_id=actor_id, visible=visible, limit=limit
            )
        ]
        folders = [
            (row.updated_at, {"kind": "folder", "ref": row.slug, "label": row.name})
            for row in await registry_repository.list_folders(db, actor_id=actor_id, visible=visible)
            if row.updated_at is not None
        ]
    except Exception:
        return []

    ranked_prompts = newest(prompts)
    ranked_folders = newest(folders)

    kept_folders = ranked_folders[: min(folder_share, limit)]
    kept_prompts = ranked_prompts[: limit - len(kept_folders)]
    # The slack, both ways: a workspace with one folder shows three prompts, and
    # a workspace with no prompts shows four folders.
    kept_folders = ranked_folders[: limit - len(kept_prompts)]
    return [*kept_prompts, *kept_folders]


async def _visible_prompt(context: tools.ToolContext, prompt_id: str) -> Any | None:
    """The prompt row when the person may read it, else ``None``."""
    from prope.prompt_registry import repository as registry_repository

    try:
        row = await registry_repository.load_prompt(context.db, prompt_id)
    except Exception:
        return None
    if row is None:
        return None
    return row if await _readable(context, row) else None


def _not_found(tool: str) -> tools.ToolResult:
    return tools.ToolResult(tool=tool, outcome="error", reason="chat_tool_not_found")


#: Above this difflib similarity a folder reference stops being "new" and
#: becomes "probably that one": creating `Âcdemic` when `academic` exists would
#: fork a workspace's prompts across two near-identical namespaces.
FOLDER_SIMILARITY_FLOOR = 0.75


async def resolve_folder_candidates(context: tools.ToolContext, reference: str) -> list[Any]:
    """Visible folders the reference could mean, best first, exact match alone.

    Deterministic on purpose — folders are few and names short, so a difflib
    ratio over the declared rows answers faster and more stably than another
    embedding call. One exact slug/name hit is unambiguous; several plausible
    hits means the caller asks which one, never guesses, because both create
    and rename land their write on whichever row wins.
    """
    from difflib import SequenceMatcher

    ref = reference.strip().lower()
    if not ref:
        return []
    try:
        rows = list(await run_list_folders_rows(context))
    except Exception:
        return []

    exact = [row for row in rows if ref in (row.slug.lower(), row.name.lower())]
    if exact:
        return exact
    scored = sorted(
        (
            (SequenceMatcher(None, ref, candidate.slug.lower()).ratio(), candidate)
            for candidate in rows
        ),
        key=lambda entry: entry[0],
        reverse=True,
    )
    return [row for score, row in scored[:3] if score >= FOLDER_SIMILARITY_FLOOR]


async def run_list_folders_rows(context: tools.ToolContext) -> tuple[Any, ...]:
    """The raw folder rows behind `run_list_folders`, for resolvers."""
    from prope.prompt_registry import repository as registry_repository

    return await registry_repository.list_folders(
        context.db, actor_id=context.actor_id, visible=context.visible
    )


def folder_candidates_result(
    context: tools.ToolContext, tool: ToolName, rows: list[Any], *, ambiguous: bool = True
) -> tools.ToolResult:
    """"Which folder?" — the candidates ride as evidence, the reply must ask.

    Same shape as :func:`ambiguous_result`: outcome `ok` (a question is not a
    failure, and must not degrade the turn), the reason code tells the
    responder this is a choice to offer rather than a crash to report.
    """
    evidence = tuple(
        tools.Evidence(
            tag=context.tag(),
            kind="folder",
            reference=row.slug,
            label=row.name,
            text=f"{row.name} ({row.slug})",
        )
        for row in rows
    )
    return tools.ToolResult(
        tool=tool,
        outcome="ok",
        evidence=evidence,
        detail={"candidate_count": len(evidence), "ambiguous": ambiguous},
        payload={"candidates": [row.slug for row in rows]},
        reason="chat_tool_ambiguous_target" if ambiguous else "chat_tool_missing_argument",
    )


def ambiguous_result(context: tools.ToolContext, tool: str, rows: list[Any]) -> tools.ToolResult:
    """Several prompts matched what the person named; the reply must ask, not pick.

    The candidates ride as ordinary prompt evidence so the responder can name
    them with citations and the person can answer "the second one". The reason
    code is what tells the responder this is a question turn rather than a
    failure — see the router instruction on `ambiguous_target`.
    """
    evidence = tuple(
        tools.Evidence(
            tag=context.tag(),
            kind="prompt",
            reference=row.id,
            label=row.title,
            text=f"{row.title} — {row.purpose}".strip(" —"),
        )
        for row in rows
    )
    return tools.ToolResult(
        tool=tool,
        outcome="ok",
        evidence=evidence,
        detail={"candidate_count": len(evidence)},
        payload={"candidates": [row.id for row in rows]},
        # `reason` carries even on outcome="ok": it is how the deterministic
        # layer tells the model *why* there is nothing to act on yet.
        reason="chat_tool_ambiguous_target",
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def run_get_prompt(context: tools.ToolContext, *, prompt_id: str) -> tools.ToolResult:
    """One visible prompt's facts. Title and purpose only — never its body."""
    if not prompt_id.strip():
        return _not_found(ToolName.GET_PROMPT)

    try:
        rows = await resolve_prompt_candidates(context, prompt_id)
    except Exception:
        return _not_found(ToolName.GET_PROMPT)
    if len(rows) > 1:
        return ambiguous_result(context, ToolName.GET_PROMPT, rows)
    if not rows:
        return _not_found(ToolName.GET_PROMPT)
    row = rows[0]

    evidence = (
        tools.Evidence(
            tag=context.tag(),
            kind="prompt",
            reference=row.id,
            label=row.title,
            text=f"{row.title} — {row.purpose}".strip(" —"),
        ),
    )
    return tools.ToolResult(
        tool=ToolName.GET_PROMPT,
        outcome="ok",
        evidence=evidence,
        detail={"status": str(row.status)},
        payload={
            "prompt_id": row.id,
            "title": row.title,
            "model_name": row.model_name,
            "status": str(row.status),
            "released_version_id": row.released_version_id or "",
        },
    )


async def run_list_versions(context: tools.ToolContext, *, prompt_id: str) -> tools.ToolResult:
    """One prompt's revision chain, newest first, bounded to five."""
    if not prompt_id.strip():
        return _not_found(ToolName.LIST_VERSIONS)

    try:
        row = await resolve_prompt(context, prompt_id)
        if row is None:
            return _not_found(ToolName.LIST_VERSIONS)
        from prope.prompt_registry import repository as registry_repository

        revisions = await registry_repository.list_revisions(context.db, prompt_id, limit=VERSIONS_LIMIT)
    except Exception:
        return _not_found(ToolName.LIST_VERSIONS)

    evidence = tuple(
        tools.Evidence(
            tag=context.tag(),
            kind="revision",
            reference=revision.version_id,
            label=f"v{revision.revision_number}",
            text=f"v{revision.revision_number} · {revision.change_summary} · {str(revision.status)}",
        )
        for revision in revisions
    )
    return tools.ToolResult(
        tool=ToolName.LIST_VERSIONS,
        outcome="ok",
        evidence=evidence,
        detail={"result_count": len(evidence)},
        payload={
            "prompt_id": prompt_id,
            "version_ids": [item.reference for item in evidence],
            "latest_version_id": evidence[0].reference if evidence else "",
        },
    )


async def run_get_release_status(context: tools.ToolContext, *, prompt_id: str) -> tools.ToolResult:
    """Which revision is serving versus which is newest."""
    if not prompt_id.strip():
        return _not_found(ToolName.GET_RELEASE_STATUS)

    try:
        row = await resolve_prompt(context, prompt_id)
        if row is None:
            return _not_found(ToolName.GET_RELEASE_STATUS)
        from prope.prompt_registry import repository as registry_repository

        released = await registry_repository.load_released_revision(context.db, prompt_id)
        latest = await registry_repository.load_latest_revision(context.db, prompt_id)
    except Exception:
        return _not_found(ToolName.GET_RELEASE_STATUS)

    released_text = f"released v{released.revision_number}" if released is not None else "nothing released"
    latest_text = f"latest v{latest.revision_number}" if latest is not None else "no revision yet"
    evidence = (
        tools.Evidence(
            tag=context.tag(),
            kind="release",
            reference=prompt_id,
            label=row.title,
            text=f"{row.title}: {released_text}, {latest_text}",
        ),
    )
    return tools.ToolResult(
        tool=ToolName.GET_RELEASE_STATUS,
        outcome="ok",
        evidence=evidence,
        detail={},
        payload={
            "prompt_id": prompt_id,
            "released_version_id": released.version_id if released else "",
            "latest_version_id": latest.version_id if latest else "",
        },
    )


async def run_list_folders(context: tools.ToolContext) -> tools.ToolResult:
    """The folder grid as the prompts screen draws it, visibility-filtered."""
    try:
        from prope.prompt_registry import repository as registry_repository

        rows = await registry_repository.list_folders(context.db, actor_id=context.actor_id, visible=context.visible)
    except Exception:
        return tools.ToolResult(tool=ToolName.LIST_FOLDERS, outcome="error", reason="chat_tool_crashed")

    top = rows[:FOLDERS_LIMIT]
    evidence = tuple(
        tools.Evidence(
            tag=context.tag(),
            kind="folder",
            reference=row.slug,
            label=row.name,
            text=f"{row.name} · {row.prompt_count} prompt",
        )
        for row in top
    )
    return tools.ToolResult(
        tool=ToolName.LIST_FOLDERS,
        outcome="ok",
        evidence=evidence,
        detail={"result_count": len(evidence), "total_count": len(rows)},
        payload={"folder_slugs": [row.slug for row in top]},
    )


# ---------------------------------------------------------------------------
# Write proposals — describe the act, perform nothing
# ---------------------------------------------------------------------------


def propose_update_prompt(
    context: tools.ToolContext,
    *,
    prompt_id: str,
    title: str | None = None,
    purpose: str | None = None,
    tags: list[str] | None = None,
) -> tools.ToolResult:
    """Describe the property change that would be made. Writes nothing."""
    cleaned_title = title.strip()[:200] if title and title.strip() else None
    cleaned_purpose = purpose.strip()[:2000] if purpose and purpose.strip() else None
    cleaned_tags = [tag.strip()[:64] for tag in (tags or []) if tag.strip()][:20] or None
    if cleaned_title is cleaned_purpose is None and cleaned_tags is None:
        return tools.ToolResult(tool=ToolName.UPDATE_PROMPT, outcome="error", reason="chat_tool_nothing_to_change")

    preview: dict[str, Any] = {"prompt_id": prompt_id}
    arguments: dict[str, Any] = {"prompt_id": prompt_id}
    for key, value in (("title", cleaned_title), ("purpose", cleaned_purpose), ("tags", cleaned_tags)):
        if value is not None:
            preview[key] = value
            arguments[key] = value

    return tools.ToolResult(
        tool=ToolName.UPDATE_PROMPT,
        outcome="ok",
        detail={"prompt_id": prompt_id, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.UPDATE_PROMPT,
            summary=prompt_id,
            preview=preview,
            arguments=arguments,
        ),
    )


def propose_retire_prompt(context: tools.ToolContext, *, prompt_id: str) -> tools.ToolResult:
    """Describe taking the prompt out of service. Writes nothing.

    Retired means the gateway stops resolving the model name — the honest
    summary the confirmation card must carry, because that is what consumers
    experience the moment the person approves.
    """
    return tools.ToolResult(
        tool=ToolName.RETIRE_PROMPT,
        outcome="ok",
        detail={"prompt_id": prompt_id, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.RETIRE_PROMPT,
            summary=prompt_id,
            preview={"prompt_id": prompt_id, "effect": "gateway_stops_serving"},
            arguments={"prompt_id": prompt_id},
        ),
    )


async def propose_drafted_revision(
    context: tools.ToolContext,
    *,
    reference: str,
    instruction: str,
    results: list[tools.ToolResult],
) -> tools.ToolResult:
    """Draft a revised body from the current revision and stage it for approval.

    The instruction-shaped half of version updates: no pasted source, just a
    target prompt and what to change about it. The body is produced by
    `drafter.draft_revision` from the latest revision plus whatever technique
    notes this plan's research legs (`answer_from_docs`, `research_topic`)
    gathered — evidence flows forward through `results`, never through a model's
    memory. What lands on the confirmation card is exactly what approval writes:
    a full canonical body, its change summary, and the version it was based on.

    Every failure is a named code: ambiguous target (candidates become evidence
    so the reply can ask), missing instruction, prompt with no revision yet,
    drafter unavailable, draft failing the canonical contract.
    """
    from prope.prompt_registry import repository as registry_repository

    if not instruction.strip():
        return tools.ToolResult(tool=ToolName.CREATE_REVISION, outcome="error", reason="chat_tool_missing_instruction")

    try:
        rows = await resolve_prompt_candidates(context, reference)
        latest = await registry_repository.load_latest_revision(context.db, rows[0].id) if len(rows) == 1 else None
    except Exception:
        rows, latest = [], None

    if len(rows) > 1:
        return ambiguous_result(context, ToolName.CREATE_REVISION, rows)
    if not rows:
        return tools.ToolResult(tool=ToolName.CREATE_REVISION, outcome="error", reason="chat_tool_no_target_prompt")
    row = rows[0]
    if latest is None:
        return tools.ToolResult(
            tool=ToolName.CREATE_REVISION,
            outcome="error",
            reason="chat_tool_no_revision_to_draft_from",
        )

    notes: list[str] = []
    for result in results:
        if result.tool not in {ToolName.ANSWER_FROM_DOCS, ToolName.RESEARCH_TOPIC}:
            continue
        if result.outcome != "ok":
            continue
        notes.extend(item.text for item in result.evidence)

    from prope.chat_orchestrator import drafter

    try:
        drafted = await drafter.draft_revision(
            current_body=latest.body,
            current_version_id=latest.version_id,
            instruction=instruction,
            research_notes="\n\n".join(notes),
        )
    except drafter.DraftUnavailableError:
        return tools.ToolResult(
            tool=ToolName.CREATE_REVISION,
            outcome="error",
            reason="chat_tool_drafter_unavailable",
        )
    except drafter.DraftInvalidError:
        return tools.ToolResult(tool=ToolName.CREATE_REVISION, outcome="error", reason="chat_tool_draft_invalid")

    arguments: dict[str, Any] = {
        "prompt_id": row.id,
        "body": drafted.body,
        "change_summary": drafted.change_summary,
        # A drafted revision IS canonical XML natively, so the provenance CHECK
        # wants the `xml` + NULL-conversion-model pairing; the previous body
        # rides along as `original_body` for the audit trail.
        "original_format": "xml",
        "original_body": latest.body,
        "based_on_version_id": drafted.based_on_version_id,
    }
    return tools.ToolResult(
        tool=ToolName.CREATE_REVISION,
        outcome="ok",
        detail={"prompt_id": row.id, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.CREATE_REVISION,
            summary=row.id,
            preview={
                "prompt_id": row.id,
                "title": row.title,
                "instruction": instruction.strip()[:300],
                "change_summary": drafted.change_summary,
                "based_on_version_id": drafted.based_on_version_id,
                "body_characters_before": len(latest.body or ""),
                "body_characters_after": len(drafted.body),
            },
            arguments=arguments,
        ),
    )


def propose_create_folder(context: tools.ToolContext, *, name: str, description: str = "") -> tools.ToolResult:
    """Describe the namespace that would be declared. Writes nothing."""
    if not name or not name.strip():
        return tools.ToolResult(tool=ToolName.CREATE_FOLDER, outcome="error", reason="chat_tool_missing_query")
    slug = tools.slugify(name, fallback="folder")
    return tools.ToolResult(
        tool=ToolName.CREATE_FOLDER,
        outcome="ok",
        detail={"slug": slug, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.CREATE_FOLDER,
            summary=slug,
            preview={"name": name.strip()[:100], "slug": slug},
            arguments={
                "slug": slug,
                "name": name.strip()[:100],
                "description": description.strip()[:500],
            },
        ),
    )


def propose_rename_folder(
    context: tools.ToolContext, *, slug: str, name: str | None = None, description: str | None = None
) -> tools.ToolResult:
    """Describe the relabel. The slug never moves (A-021); writes nothing."""
    clean_name = name.strip()[:100] if name and name.strip() else None
    clean_description = description.strip()[:500] if description and description.strip() else None
    if clean_name is None and clean_description is None:
        return tools.ToolResult(tool=ToolName.RENAME_FOLDER, outcome="error", reason="chat_tool_nothing_to_change")
    arguments: dict[str, Any] = {"slug": slug}
    if clean_name is not None:
        arguments["name"] = clean_name
    if clean_description is not None:
        arguments["description"] = clean_description
    return tools.ToolResult(
        tool=ToolName.RENAME_FOLDER,
        outcome="ok",
        detail={"slug": slug, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.RENAME_FOLDER, summary=slug, preview=arguments.copy(), arguments=arguments
        ),
    )


def propose_delete_folder(context: tools.ToolContext, *, slug: str) -> tools.ToolResult:
    """Describe dropping an empty folder's label. Writes nothing."""
    return tools.ToolResult(
        tool=ToolName.DELETE_FOLDER,
        outcome="ok",
        detail={"slug": slug, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.DELETE_FOLDER,
            summary=slug,
            preview={"slug": slug},
            arguments={"slug": slug},
        ),
    )


# ---------------------------------------------------------------------------
# Confirmed writes — reached only from the confirmation route
# ---------------------------------------------------------------------------


async def _gate_workspace(context: tools.ToolContext, permission: str) -> None:
    """Raise `permission_denied` when the actor lacks a workspace-level grant."""
    from prope.access_control.actions import Action
    from prope.access_control.seams import Actor, ActorType, Subject, SubjectType, may

    actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
    subject = Subject(
        type=SubjectType.WORKSPACE,
        id=context.workspace_id,
        workspace_id=context.workspace_id,
    )
    action = Action(permission)
    if not await may(context.db, actor, action, subject):
        raise tools.WriteRefused("permission_denied")


async def execute_update_prompt(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """PATCH the mutable half of one prompt's properties."""
    from prope.access_control.actions import Action
    from prope.access_control.seams import AccessLevel, Actor, ActorType, Subject, SubjectType, may
    from prope.prompt_registry import commands
    from prope.prompt_registry import repository as registry_repository

    prompt_id = str(arguments["prompt_id"])
    row = await registry_repository.load_prompt(context.db, prompt_id)
    if row is None:
        raise tools.WriteRefused("not_found")

    actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
    subject = Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        namespace=row.namespace,
    )
    if not await may(context.db, actor, Action.PROMPT_EDIT, subject):
        if await may(context.db, actor, Action.PROMPT_READ, subject):
            raise tools.WriteRefused("permission_denied")
        raise tools.WriteRefused("not_found")

    await commands.update_prompt(
        context.db,
        workspace_id=context.workspace_id,
        actor_id=context.actor_id,
        prompt_id=prompt_id,
        title=arguments.get("title"),
        purpose=arguments.get("purpose"),
        owner_id=None,
        access_level=None,
        tags=arguments.get("tags"),
        now=datetime.now(UTC),
    )
    return {"prompt_id": prompt_id}


def propose_move_prompt(
    context: tools.ToolContext,
    *,
    prompt_id: str,
    title: str,
    current_namespace: str,
    current_name: str,
    namespace: str,
    name: str | None = None,
) -> tools.ToolResult:
    """Describe the identity move — folder and/or slug. Writes nothing.

    The card carries both identities because that contrast IS the review: a
    rename nobody can see the before/after of is a rubber stamp waiting to
    happen, and A-021's whole concern was silent renames.
    """
    target_name = tools.slugify(name) if name and name.strip() else current_name
    return tools.ToolResult(
        tool=ToolName.MOVE_PROMPT,
        outcome="ok",
        detail={"prompt_id": prompt_id, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.MOVE_PROMPT,
            summary=f"{current_namespace}/{current_name} → {namespace}/{target_name}",
            preview={
                "prompt": prompt_id,
                "title": title,
                "from": f"{current_namespace}/{current_name}",
                "to": f"{namespace}/{target_name}",
            },
            arguments={
                "prompt_id": prompt_id,
                "namespace": namespace,
                "name": target_name,
            },
        ),
    )


async def execute_move_prompt(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Move one prompt to another folder and/or change its slug."""
    from prope.access_control.actions import Action
    from prope.access_control.seams import AccessLevel, Actor, ActorType, Subject, SubjectType, may
    from prope.prompt_registry import commands
    from prope.prompt_registry import repository as registry_repository
    from prope.session_auth import ManagementRefusal

    prompt_id = str(arguments["prompt_id"])
    row = await registry_repository.load_prompt(context.db, prompt_id)
    if row is None:
        raise tools.WriteRefused("not_found")

    actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
    subject = Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        namespace=row.namespace,
    )
    if not await may(context.db, actor, Action.PROMPT_EDIT, subject):
        if await may(context.db, actor, Action.PROMPT_READ, subject):
            raise tools.WriteRefused("permission_denied")
        raise tools.WriteRefused("not_found")

    try:
        await commands.move_prompt(
            context.db,
            workspace_id=context.workspace_id,
            actor_id=context.actor_id,
            prompt_id=prompt_id,
            namespace=str(arguments["namespace"]),
            name=str(arguments["name"]),
            now=datetime.now(UTC),
        )
    except ManagementRefusal as refusal:
        # The proposal stage already walked suffixes; a collision here means the
        # registry disagreed with what the person approved, so the write refuses
        # by its own name instead of crashing the worker.
        raise tools.WriteRefused(refusal.code.value) from None
    return {"prompt_id": prompt_id}


async def execute_retire_prompt(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Take a prompt out of service, refusing while a release is active."""
    from prope.access_control.actions import Action
    from prope.access_control.seams import AccessLevel, Actor, ActorType, Subject, SubjectType, may
    from prope.prompt_registry import commands
    from prope.prompt_registry import repository as registry_repository
    from prope.session_auth import ManagementRefusal

    prompt_id = str(arguments["prompt_id"])
    row = await registry_repository.load_prompt(context.db, prompt_id)
    if row is None:
        raise tools.WriteRefused("not_found")

    actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
    subject = Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        namespace=row.namespace,
    )
    if not await may(context.db, actor, Action.PROMPT_RETIRE, subject):
        if await may(context.db, actor, Action.PROMPT_READ, subject):
            raise tools.WriteRefused("permission_denied")
        raise tools.WriteRefused("not_found")

    try:
        await commands.retire_prompt(
            context.db,
            workspace_id=context.workspace_id,
            actor_id=context.actor_id,
            prompt_id=prompt_id,
            now=datetime.now(UTC),
        )
    except ManagementRefusal:
        # The command refuses with REGISTRY_ACTIVE_RELEASE while the gateway is
        # still serving it; the card gets a code, not the exception.
        raise tools.WriteRefused("chat_tool_active_release") from None
    return {"prompt_id": prompt_id}


async def execute_create_folder(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Declare a namespace, refusing a slug either use has already claimed."""
    from prope.prompt_registry import commands
    from prope.prompt_registry.domain import FolderSlugTaken

    await _gate_workspace(context, "prompt.create")
    slug = str(arguments["slug"])
    try:
        await commands.create_folder(
            context.db,
            workspace_id=context.workspace_id,
            slug=slug,
            name=str(arguments.get("name") or slug),
            description=str(arguments.get("description") or ""),
            color=None,
            now=datetime.now(UTC),
        )
    except FolderSlugTaken:
        raise tools.WriteRefused("chat_tool_slug_taken") from None
    return {"folder_slug": slug}


async def execute_rename_folder(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Relabel a folder. Declares one when it had no row, exactly like the API."""
    from prope.prompt_registry import commands

    await _gate_workspace(context, "prompt.create")
    slug = str(arguments["slug"])
    await commands.update_folder(
        context.db,
        workspace_id=context.workspace_id,
        slug=slug,
        name=arguments.get("name"),
        description=arguments.get("description"),
        color=None,
        now=datetime.now(UTC),
    )
    return {"folder_slug": slug}


async def execute_delete_folder(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Drop a folder's label, refused while any prompt carries the namespace."""
    from prope.prompt_registry import commands
    from prope.prompt_registry.domain import FolderNotEmpty

    await _gate_workspace(context, "prompt.create")
    slug = str(arguments["slug"])
    try:
        await commands.delete_folder(context.db, slug=slug)
    except FolderNotEmpty:
        raise tools.WriteRefused("chat_tool_folder_not_empty") from None
    return {"folder_slug": slug}
