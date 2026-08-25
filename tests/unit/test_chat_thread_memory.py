"""Thread memory, queued plans, folder disambiguation, and router fail-fast.

Four fixes for what the Langfuse traces showed: the router burning a minute on
sixty tokens, a follow-up request losing its referent ("đổi tên prompt ấy"),
a multi-write message dropping its second half at the first confirmation card,
and a near-miss folder name forking the workspace instead of asking. No model
is called, no database is touched, no socket leaves the process.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from prope.app_agent.dspy_runtime import build_lm
from prope.chat_orchestrator import dspy_program, orchestrator, tools, tools_registry
from prope.chat_orchestrator.domain import ToolName
from prope.chat_orchestrator.orchestrator import (
    TurnResult,
    _remaining_plan,
    run_queued_step,
)

# ---------------------------------------------------------------------------
# A: per-program models and fail-fast routing
# ---------------------------------------------------------------------------


def test_the_router_lm_fails_fast() -> None:
    """One visible attempt bounded by a timeout: a slow proxy must surface as
    `chat_agent_unavailable` in seconds, not as a silent 57s route step."""
    lm = dspy_program.build_router_lm()

    assert lm.num_retries == dspy_program.ROUTER_NUM_RETRIES
    assert lm.kwargs["timeout"] == pytest.approx(dspy_program.ROUTER_TIMEOUT_SECONDS)


def test_the_shared_lm_takes_a_per_program_model_override() -> None:
    lm = build_lm(max_tokens=16, model="fast-mini")

    assert lm.model == "openai/fast-mini"


def test_unset_model_overrides_keep_the_app_model(monkeypatch) -> None:
    monkeypatch.delenv("CHAT_ROUTER_MODEL", raising=False)
    assert dspy_program.ROUTER_MODEL == __import__("prope.app_agent.client", fromlist=["x"]).APP_AGENT_MODEL


# ---------------------------------------------------------------------------
# C: thread state
# ---------------------------------------------------------------------------


def test_thread_entities_render_newest_first_with_ids() -> None:
    text = dspy_program.render_thread_entities(
        [
            {"kind": "prompt", "id": "prm_9", "ref": "imported/x (prm_9)", "label": "Prompt đã nhập"},
            {"kind": "folder", "ref": "academic", "label": "Academic"},
        ]
    )

    lines = text.splitlines()
    assert 'prompt imported/x (prm_9) = "Prompt đã nhập"' in lines[0]
    assert lines[1] == 'folder academic = "Academic"'


def test_thread_entity_rendering_is_capped() -> None:
    entities = [{"kind": "prompt", "ref": f"p{i}", "label": ""} for i in range(20)]

    text = dspy_program.render_thread_entities(entities)

    assert len(text.splitlines()) <= dspy_program.MAX_THREAD_ENTITIES


def test_decided_actions_carry_what_they_created() -> None:
    text = dspy_program.render_decided_actions(
        [{"tool": "create_prompt", "arguments": {"title": "X"}, "status": "confirmed", "result_prompt_id": "prm_7"}]
    )

    assert "[created prm_7]" in text


async def test_the_router_sees_the_thread_state(monkeypatch) -> None:
    seen: dict[str, Any] = {}

    class _Router:
        async def acall(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(intent="smalltalk", tools=[], query="", rationale="", changes={})

    class _Responder:
        async def acall(self, **kwargs):
            return SimpleNamespace(reply="ok", cited=[])

    monkeypatch.setattr(dspy_program, "build_router_program", lambda _: _Router())
    monkeypatch.setattr(dspy_program, "build_reply_program", lambda _: _Responder())

    request = SimpleNamespace(
        open_db=None,
        workspace_id="wsp",
        actor_id="usr",
        visible=None,
        conversation_id="cnv",
        history=[],
        decided_actions=[],
        thread_entities=[{"kind": "prompt", "ref": "a/b (prm_1)", "label": "T"}],
        attachment=None,
        attachment_format="txt",
        carried_attachment=None,
        carried_attachment_format="txt",
        trigger="message",
        decision=None,
        activity=None,
        message="prompt trong thread còn hoạt động chứ",
    )
    await orchestrator.run_turn(request)

    assert "(prm_1)" in seen["thread_state"]


# ---------------------------------------------------------------------------
# D: the pending-plan queue
# ---------------------------------------------------------------------------


def _routed(tool_names: list[str], changes: dict[str, str] | None = None, *, intent: str = "manage_prompt"):
    """A decision the way production makes one — through `routing_of`.

    **Built from a prediction, never by hand.** The previous tests here
    constructed `RoutingDecision(tools=("create_folder", "update_prompt"))`
    directly, which asserted against a state `routing_of` cannot emit: it puts
    the surviving write last and removes the rest. So the queue looked tested
    while being unreachable on every real turn, and the fixture was doubly
    impossible — `create_folder` is not even reachable from `manage_prompt`.
    Going through `routing_of` is what makes these tests mean something.
    """
    return dspy_program.routing_of(
        SimpleNamespace(
            intent=intent,
            tools=tool_names,
            query="hỗ trợ khách hàng",
            changes=changes or {},
            rationale="",
        )
    )


def _decision(tools_: tuple[str, ...], arguments: dict[str, str] | None = None):
    """A minimal stand-in for the step functions, which read only two fields.

    Deliberately NOT used for `_remaining_plan`: that one has to see what
    `routing_of` really produces, so it gets `_routed` above. A step function
    takes `arguments` and `query` and never looks at the plan, so a stub is
    honest here and a lie there.
    """
    return dspy_program.RoutingDecision(
        intent="manage_folder", tools=tools_, query="", rationale="", arguments=arguments or {}
    )


def _card(tool: str, **arguments: str) -> tools.Proposal:
    return tools.Proposal(tool=tool, summary="s", preview={}, arguments=dict(arguments))


def test_the_second_write_survives_the_card_that_interrupted_it() -> None:
    """ "Đổi tên rồi chuyển vào thư mục Marketing" keeps its second half.

    The turn runs the rename and stages its card; the move queues behind it and
    runs on the next approval. One card at a time is the HITL invariant — both
    writes reaching the person at once is what `PendingAction` exists to stop —
    but one card at a time is not the same as dropping the second request.
    """
    decision = _routed(
        ["search_prompts", "update_prompt", "move_prompt"],
        {"title": "Trợ lý hoàn tiền", "namespace": "marketing"},
    )

    # What `routing_of` actually emits: the read, then one write, and the rest
    # of the writes set aside rather than deleted.
    assert tuple(decision.tools) == ("search_prompts", "update_prompt")
    assert tuple(decision.deferred) == ("move_prompt",)

    queued = _remaining_plan(decision, [], _card("update_prompt", prompt_id="prm_1"), [])

    assert [step["tool"] for step in queued] == ["move_prompt"]


def test_the_queue_targets_the_row_the_card_resolved() -> None:
    """The router names the prompt the way the person did; the card has its id.

    Re-resolving "hỗ trợ khách hàng" on the continuation would run a semantic
    search against a workspace the approval it is queued behind has just
    renamed — so the id the first write already settled on rides along instead.
    """
    decision = _routed(
        ["update_prompt", "move_prompt"],
        {"title": "Trợ lý hoàn tiền", "namespace": "marketing"},
    )

    queued = _remaining_plan(decision, [], _card("update_prompt", prompt_id="prm_1"), [])

    assert queued[0]["arguments"]["prompt_id"] == "prm_1"
    # The router's own arguments still ride along: the steps read disjoint keys
    # out of one flat `changes`, and `move_prompt` needs `namespace` from it.
    assert queued[0]["arguments"]["namespace"] == "marketing"


def test_a_proposal_with_no_row_yet_carries_no_identity() -> None:
    """`create_prompt`'s row does not exist until somebody confirms it."""
    decision = _routed(["convert_prompt", "create_prompt"], {"namespace": "imported"}, intent="import_prompt")
    queued = _remaining_plan(decision, [], _card("create_prompt", namespace="imported"), [])

    assert all("prompt_id" not in step["arguments"] for step in queued)


def test_a_confirmed_repeat_never_queues() -> None:
    """Deduplicated against the step as it will run, identity included.

    `move_prompt` is identified by `(prompt_id, namespace)`, and the id only
    exists once the card resolved it — so a queue deduplicated before that is
    comparing an empty id against a confirmed one and matching nothing.
    """
    decision = _routed(
        ["update_prompt", "move_prompt"],
        {"title": "Trợ lý hoàn tiền", "namespace": "marketing"},
    )
    decided = [
        {
            "tool": "move_prompt",
            "status": "confirmed",
            "arguments": {"prompt_id": "prm_1", "namespace": "marketing"},
        }
    ]

    assert _remaining_plan(decision, [], _card("update_prompt", prompt_id="prm_1"), decided) == []


def test_the_same_move_on_a_different_prompt_still_queues() -> None:
    """Identity, not tool name: deduplication must not swallow a real request."""
    decision = _routed(
        ["update_prompt", "move_prompt"],
        {"title": "Trợ lý hoàn tiền", "namespace": "marketing"},
    )
    decided = [
        {
            "tool": "move_prompt",
            "status": "confirmed",
            "arguments": {"prompt_id": "prm_OTHER", "namespace": "marketing"},
        }
    ]

    queued = _remaining_plan(decision, [], _card("update_prompt", prompt_id="prm_1"), decided)

    assert [step["tool"] for step in queued] == ["move_prompt"]


def test_reads_after_the_write_never_queue() -> None:
    """A read re-runs cheaply next turn; only a dropped write is a lost request."""
    decision = _routed(["update_prompt", "move_prompt", "get_prompt"], {"namespace": "marketing"})

    queued = _remaining_plan(decision, [], _card("update_prompt", prompt_id="prm_1"), [])

    assert all(step["tool"] != "get_prompt" for step in queued)


def test_an_uninterrupted_plan_queues_nothing() -> None:
    """No card, nothing to queue behind."""
    assert _remaining_plan(_routed(["get_prompt"]), [], None, []) == []


def test_a_single_write_plan_queues_nothing() -> None:
    decision = _routed(["update_prompt"], {"title": "Ponytail"})

    assert not decision.deferred
    assert _remaining_plan(decision, [], _card("update_prompt", prompt_id="prm_1"), []) == []


@asynccontextmanager
async def _open_db():
    yield object()


async def test_a_queued_write_runs_without_a_model(monkeypatch) -> None:
    calls: list[str] = []

    async def step(context, decision, results):  # noqa: ANN001, ARG001
        calls.append("ran")
        return tools.ToolResult(
            tool=ToolName.UPDATE_PROMPT,
            outcome="ok",
            detail={"steps": 1},
            proposal=tools.Proposal(
                tool=ToolName.UPDATE_PROMPT, summary="prm_1", preview={"title": "New"}, arguments={"prompt_id": "prm_1"}
            ),
        )

    monkeypatch.setitem(orchestrator._TOOL_STEPS, ToolName.UPDATE_PROMPT, step)

    result = await run_queued_step(
        open_db=_open_db,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        conversation_id="cnv_1",
        step={"tool": "update_prompt", "arguments": {"prompt_id": "prm_1", "title": "New"}},
        remaining=[{"tool": "retire_prompt", "arguments": {}}],
    )

    assert calls == ["ran"]
    assert result.pending is not None
    assert result.code == "chat_proposal_pending"
    assert result.pending.remaining_steps == [{"tool": "retire_prompt", "arguments": {}}]
    assert not any(
        entry.agent.startswith("supervisor") and entry.action == "route" and "queued" not in (entry.detail or {})
        for entry in result.trace
        if entry.detail
    )


async def test_a_failed_queued_step_stops_the_chain(monkeypatch) -> None:
    async def step(context, decision, results):  # noqa: ANN001, ARG001
        return tools.ToolResult(tool=ToolName.UPDATE_PROMPT, outcome="error", reason="chat_tool_not_found")

    monkeypatch.setitem(orchestrator._TOOL_STEPS, ToolName.UPDATE_PROMPT, step)

    result = await run_queued_step(
        open_db=_open_db,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        conversation_id="cnv_1",
        step={"tool": "update_prompt", "arguments": {}},
        remaining=[{"tool": "retire_prompt", "arguments": {}}],
    )

    assert result.pending is None
    assert result.outcome == "degraded"
    assert result.degraded == ["tool_failed"]


async def test_an_unknown_queued_tool_refuses_to_run() -> None:
    result = await run_queued_step(
        open_db=_open_db,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        conversation_id="cnv_1",
        step={"tool": "deploy_to_production", "arguments": {}},
        remaining=[],
    )

    assert isinstance(result, TurnResult)
    assert result.pending is None


# ---------------------------------------------------------------------------
# E: folders ask instead of guessing
# ---------------------------------------------------------------------------


def _folder(slug: str, name: str):
    return SimpleNamespace(slug=slug, name=name, updated_at=None)


async def test_an_exact_folder_match_resolves_alone(monkeypatch) -> None:
    async def rows(context):  # noqa: ANN001, ARG001
        return (_folder("academic", "Academic"), _folder("marketing", "Marketing"))

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", rows)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    found = await tools_registry.resolve_folder_candidates(context, "Academic")

    assert [row.slug for row in found] == ["academic"]


async def test_a_near_miss_folder_name_offers_the_existing_one(monkeypatch) -> None:
    async def rows(context):  # noqa: ANN001, ARG001
        return (_folder("academic", "Academic"),)

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", rows)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    result = await orchestrator._step_create_folder(context, _decision((), {"name": "Âcdemic"}), [])

    assert result.proposal is None
    assert result.reason == "chat_tool_ambiguous_target"
    assert [item.reference for item in result.evidence] == ["academic"]


async def test_a_genuinely_new_folder_proposes_without_asking(monkeypatch) -> None:
    async def rows(context):  # noqa: ANN001, ARG001
        return (_folder("marketing", "Marketing"),)

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", rows)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    result = await orchestrator._step_create_folder(context, _decision((), {"name": "Zephyr"}), [])

    assert result.proposal is not None
    assert result.proposal.arguments["slug"] == "zephyr"


async def test_rename_resolves_before_it_proposes(monkeypatch) -> None:
    async def rows(context):  # noqa: ANN001, ARG001
        return (_folder("academic", "Academic"),)

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", rows)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    result = await orchestrator._step_rename_folder(
        context, _decision((), {"slug": "academic", "name": "Học thuật"}), []
    )

    assert result.proposal is not None
    assert result.proposal.arguments["slug"] == "academic"


async def test_a_delete_named_by_its_label_lands_on_the_real_slug(monkeypatch) -> None:
    """ "Xoá thư mục Nháp" must delete `nhap`, not `Nháp`.

    `delete_folder` used to be a bare lambda handing the router's string
    straight to the executor. `commands.delete_folder` counts prompts in that
    namespace (zero, because no such namespace exists), issues
    ``DELETE ... WHERE slug = 'Nháp'``, removes no rows and reports success —
    so the person is told the folder is gone while it is still there. Nothing
    raises and nothing logs; it is the silent failure mode, which is the worst
    of the family to leave in a tool whose whole job is destructive.
    """

    async def rows(context):  # noqa: ANN001, ARG001
        return (_folder("nhap", "Nháp"),)

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", rows)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    result = await orchestrator._step_delete_folder(context, _decision((), {"slug": "Nháp"}), [])

    assert result.proposal is not None
    assert result.proposal.arguments["slug"] == "nhap"
    # The card is what the person reads before approving a delete. It must name
    # the folder that will actually go, not the string the model happened to use.
    assert result.proposal.preview["slug"] == "nhap"


async def test_a_delete_of_something_unresolvable_asks_instead_of_guessing(monkeypatch) -> None:
    """No match means a question listing what the person can see — never a
    proposal built on a slug nobody confirmed exists."""

    async def rows(context):  # noqa: ANN001, ARG001
        return (_folder("academic", "Academic"), _folder("marketing", "Marketing"))

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", rows)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    result = await orchestrator._step_delete_folder(context, _decision((), {"slug": "Zephyr"}), [])

    assert result.proposal is None
    assert [item.reference for item in result.evidence] == ["academic", "marketing"]


async def test_a_delete_with_no_reference_at_all_refuses_cleanly(monkeypatch) -> None:
    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    result = await orchestrator._step_delete_folder(context, _decision((), {}), [])

    assert result.proposal is None
    assert result.reason == "chat_tool_missing_argument"


async def test_rename_and_delete_resolve_through_the_same_path(monkeypatch) -> None:
    """The two folder acts guard against one failure, so they share one guard.

    Asserted rather than assumed: the bug was that `delete_folder` never got the
    hardening `rename_folder` was given, and nothing in the suite noticed the
    two had diverged.
    """

    async def rows(context):  # noqa: ANN001, ARG001
        return (_folder("nhap", "Nháp"),)

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", rows)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    renamed = await orchestrator._step_rename_folder(context, _decision((), {"slug": "Nháp", "name": "X"}), [])
    deleted = await orchestrator._step_delete_folder(context, _decision((), {"slug": "Nháp"}), [])

    assert renamed.proposal is not None and deleted.proposal is not None
    assert renamed.proposal.arguments["slug"] == deleted.proposal.arguments["slug"] == "nhap"


# ---------------------------------------------------------------------------
# G2: move_prompt — folder and slug change as one governed write
# ---------------------------------------------------------------------------


def _async(value: Any):
    async def call(*_args: Any, **_kwargs: Any) -> Any:
        return value

    return call


def _prompt_row_full():
    return SimpleNamespace(
        id="prm_1",
        workspace_id="wsp_1",
        owner_id="usr_1",
        access_level="private",
        namespace="imported",
        name="prompt-da-nhap-2",
        title="Ponytail Lazy Senior Dev Architect",
        purpose="",
        status="active",
    )


async def test_a_move_proposes_old_and_new_identity(monkeypatch) -> None:
    monkeypatch.setattr(tools_registry, "resolve_prompt", _async(_prompt_row_full()))

    async def folders(context):  # noqa: ANN001, ARG001
        return (_folder("designer", "Designer"),)

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", folders)

    async def candidates(context, reference):  # noqa: ANN001, ARG001
        return [_folder("designer", "Designer")]

    monkeypatch.setattr(tools_registry, "resolve_folder_candidates", candidates)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    decision = SimpleNamespace(
        arguments={"prompt_id": "prm_1", "namespace": "Designer", "name": "AdaptiveLearningDesinger"}, query=""
    )
    result = await orchestrator._step_move_prompt(context, decision, [])

    proposal = result.proposal
    assert proposal is not None and proposal.tool == ToolName.MOVE_PROMPT
    assert proposal.arguments["namespace"] == "designer"
    assert proposal.arguments["name"] == "adaptivelearningdesinger"
    assert proposal.preview["from"] == "imported/prompt-da-nhap-2"
    assert proposal.preview["to"].startswith("designer/")


async def test_a_move_without_a_destination_asks_with_visible_folders(monkeypatch) -> None:
    monkeypatch.setattr(tools_registry, "resolve_prompt", _async(_prompt_row_full()))

    async def folders(context):  # noqa: ANN001, ARG001
        return (_folder("academic", "Academic"), _folder("marketing", "Marketing"))

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", folders)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    decision = SimpleNamespace(arguments={"prompt_id": "prm_1"}, query="")
    result = await orchestrator._step_move_prompt(context, decision, [])

    assert result.proposal is None
    assert result.reason == "chat_tool_missing_argument"
    assert [item.reference for item in result.evidence] == ["academic", "marketing"]


async def test_an_ambiguous_destination_offers_the_candidates(monkeypatch) -> None:
    monkeypatch.setattr(tools_registry, "resolve_prompt", _async(_prompt_row_full()))

    async def candidates(context, reference):  # noqa: ANN001, ARG001
        return [_folder("academic", "Academic"), _folder("academy", "Academy")]

    monkeypatch.setattr(tools_registry, "resolve_folder_candidates", candidates)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    decision = SimpleNamespace(arguments={"prompt_id": "prm_1", "namespace": "acade"}, query="")
    result = await orchestrator._step_move_prompt(context, decision, [])

    assert result.proposal is None
    assert result.reason == "chat_tool_ambiguous_target"


async def test_a_slug_change_with_no_folder_renames_in_place(monkeypatch) -> None:
    """ "Đổi slug thành X" names no destination, and that is an answer.

    The router returns `move_prompt` with `{prompt_id, name}` and no
    `namespace` — correctly, because the person asked to rename and not to
    move. Reading the empty namespace as *unanswered* made this step reply with
    the folder list, which left the only write that can change a slug
    unreachable unless the person also relocated the prompt.
    """
    monkeypatch.setattr(tools_registry, "resolve_prompt", _async(_prompt_row_full()))

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    decision = SimpleNamespace(arguments={"prompt_id": "prm_1", "name": "tro-ly-hoan-tien"}, query="")
    result = await orchestrator._step_move_prompt(context, decision, [])

    proposal = result.proposal
    assert proposal is not None and proposal.tool == ToolName.MOVE_PROMPT
    assert proposal.arguments["name"] == "tro-ly-hoan-tien"
    # The folder is unchanged, which is the whole point: only the slug moved.
    assert proposal.arguments["namespace"] == "imported"
    assert proposal.preview["from"] == "imported/prompt-da-nhap-2"
    assert proposal.preview["to"] == "imported/tro-ly-hoan-tien"


async def test_a_rename_in_place_never_resolves_the_folder_it_is_staying_in(monkeypatch) -> None:
    """The current namespace comes off the row, not out of a folder lookup.

    Folders are the *declared* half of a namespace, so a prompt can sit in one
    that has no `registry.folder` row — and `resolve_folder_candidates` falls
    back to a `SequenceMatcher` ratio, which will happily score a different
    folder above the floor. Resolving here would turn a rename into "which
    folder did you mean?" for a move nobody asked for.
    """
    monkeypatch.setattr(tools_registry, "resolve_prompt", _async(_prompt_row_full()))

    consulted: list[str] = []

    async def candidates(context, reference):  # noqa: ANN001, ARG001
        consulted.append(reference)
        return [_folder("imported-old", "Imported Old")]

    async def folders(context):  # noqa: ANN001, ARG001
        consulted.append("<listing>")
        return (_folder("imported-old", "Imported Old"),)

    monkeypatch.setattr(tools_registry, "resolve_folder_candidates", candidates)
    monkeypatch.setattr(tools_registry, "run_list_folders_rows", folders)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    decision = SimpleNamespace(arguments={"prompt_id": "prm_1", "name": "ten-moi"}, query="")
    result = await orchestrator._step_move_prompt(context, decision, [])

    assert consulted == [], f"the rename consulted the folder table: {consulted}"
    assert result.proposal is not None
    assert result.proposal.arguments["namespace"] == "imported"


async def test_neither_a_destination_nor_a_slug_still_asks(monkeypatch) -> None:
    """The one case with genuinely nothing to propose keeps asking."""
    monkeypatch.setattr(tools_registry, "resolve_prompt", _async(_prompt_row_full()))

    async def folders(context):  # noqa: ANN001, ARG001
        return (_folder("academic", "Academic"),)

    monkeypatch.setattr(tools_registry, "run_list_folders_rows", folders)

    context = tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)
    decision = SimpleNamespace(arguments={"prompt_id": "prm_1"}, query="")
    result = await orchestrator._step_move_prompt(context, decision, [])

    assert result.proposal is None
    assert result.reason == "chat_tool_missing_argument"


# ---------------------------------------------------------------------------
# G1: imports are titled by their content
# ---------------------------------------------------------------------------


def test_a_markdown_heading_becomes_the_title() -> None:
    source = "\n\n```text\nnoise\n```\n\n# Ponytail Lazy Senior Dev Architect\nbody"

    assert orchestrator._title_from_source(source) == "Ponytail Lazy Senior Dev Architect"


def test_a_short_first_line_stands_in_when_there_is_no_heading() -> None:
    source = "You are a helpful refund assistant.\n\nMore prose follows."

    assert orchestrator._title_from_source(source) == "You are a helpful refund assistant."


def test_urls_and_separators_are_never_titles() -> None:
    source = "---\nhttps://github.com/some/prompt\n=================\nReal title line here"

    assert orchestrator._title_from_source(source) == "Real title line here"


async def test_the_import_step_titles_from_the_attachment(monkeypatch) -> None:
    from prope.prompt_registry import repository as registry_repository

    async def load(db, namespace, name):  # noqa: ANN001, ARG001
        return None

    monkeypatch.setattr(registry_repository, "load_prompt_by_model_name", load)

    context = tools.ToolContext(
        db=None,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        attachment="# Adaptive Learning Designer\n\nYou design lessons.",
        converted_xml="<prompt><system>x</system></prompt>",
    )
    result = await orchestrator._step_create_prompt(context, SimpleNamespace(query="", arguments={}), [])

    assert result.proposal is not None
    assert result.proposal.arguments["title"] == "Adaptive Learning Designer"


# ---------------------------------------------------------------------------
# The import honours the destination folder the person named
# ---------------------------------------------------------------------------


async def test_an_import_into_an_unheard_of_folder_becomes_that_namespace(monkeypatch) -> None:
    from prope.prompt_registry import repository as registry_repository

    async def load(db, namespace, name):  # noqa: ANN001, ARG001
        return None

    monkeypatch.setattr(registry_repository, "load_prompt_by_model_name", load)

    async def candidates(context, reference):  # noqa: ANN001, ARG001
        return []

    monkeypatch.setattr(tools_registry, "resolve_folder_candidates", candidates)

    context = tools.ToolContext(
        db=None,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        attachment="You design lessons.",
        converted_xml="<prompt><system>x</system></prompt>",
    )
    decision = SimpleNamespace(query="", arguments={"namespace": "3d"})
    result = await orchestrator._step_create_prompt(context, decision, [])

    proposal = result.proposal
    assert proposal is not None and proposal.tool == ToolName.CREATE_PROMPT
    # "vào thư mục mới tên 3d" — the folder does not exist yet; the import's
    # own write creates it. Falling back to Imported would be a silent refusal
    # of what was asked.
    assert proposal.arguments["namespace"] == "3d"


async def test_an_import_with_an_ambiguous_folder_asks_instead(monkeypatch) -> None:
    async def candidates(context, reference):  # noqa: ANN001, ARG001
        return [_folder("academic", "Academic"), _folder("academy", "Academy")]

    monkeypatch.setattr(tools_registry, "resolve_folder_candidates", candidates)

    context = tools.ToolContext(
        db=None,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        attachment="You design lessons.",
        converted_xml="<prompt><system>x</system></prompt>",
    )
    decision = SimpleNamespace(query="", arguments={"namespace": "acade"})
    result = await orchestrator._step_create_prompt(context, decision, [])

    assert result.proposal is None
    assert result.reason == "chat_tool_ambiguous_target"
    assert [item.reference for item in result.evidence] == ["academic", "academy"]


async def test_an_import_without_a_named_folder_stays_in_the_default(monkeypatch) -> None:
    from prope.prompt_registry import repository as registry_repository

    async def load(db, namespace, name):  # noqa: ANN001, ARG001
        return None

    monkeypatch.setattr(registry_repository, "load_prompt_by_model_name", load)

    context = tools.ToolContext(
        db=None,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        attachment="You design lessons.",
        converted_xml="<prompt><system>x</system></prompt>",
    )
    decision = SimpleNamespace(query="", arguments={})
    result = await orchestrator._step_create_prompt(context, decision, [])

    proposal = result.proposal
    assert proposal is not None
    assert proposal.arguments["namespace"] == "imported"
