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
    assert lines[1] == "folder academic = \"Academic\""


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
        message="xin chào",
    )
    await orchestrator.run_turn(request)

    assert "(prm_1)" in seen["thread_state"]


# ---------------------------------------------------------------------------
# D: the pending-plan queue
# ---------------------------------------------------------------------------


def _decision(tools_: tuple[str, ...], arguments: dict[str, str] | None = None):
    return dspy_program.RoutingDecision(
        intent="manage_prompt", tools=tools_, query="x", rationale="", arguments=arguments or {}
    )


def test_the_queue_holds_the_writes_behind_the_card() -> None:
    decision = _decision(("create_folder", "update_prompt"), {"name": "Academic", "title": "Ponytail"})
    proposal = tools.Proposal(tool=ToolName.CREATE_FOLDER, summary="academic", preview={}, arguments={})

    queued = _remaining_plan(decision, [], proposal, [])

    assert queued == [{"tool": "update_prompt", "arguments": {"name": "Academic", "title": "Ponytail"}}]


def test_reads_and_confirmed_repeats_never_queue() -> None:
    decision = _decision(("create_folder", "get_prompt", "update_prompt"), {"slug": "academic"})
    proposal = tools.Proposal(tool=ToolName.CREATE_FOLDER, summary="academic", preview={}, arguments={})
    decided = [
        {
            "tool": "update_prompt",
            "status": "confirmed",
            "arguments": {"prompt_id": "prm_1", "title": "Ponytail"},
        }
    ]

    queued = _remaining_plan(decision, [], proposal, decided)

    # The read never queues; the write matches an already-confirmed action only
    # when its identity fields do — different title, so it stays.
    assert queued and queued[0]["tool"] == "update_prompt"


def test_an_uninterrupted_plan_queues_nothing() -> None:
    assert _remaining_plan(_decision(("get_prompt",)), [], None, []) == []


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
    assert not any(entry.agent.startswith("supervisor") and entry.action == "route" and "queued" not in (entry.detail or {}) for entry in result.trace if entry.detail)


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


# ---------------------------------------------------------------------------
# G2: move_prompt — folder and slug change as one governed write
# ---------------------------------------------------------------------------


def _async(value: Any):
    async def call(*_args: Any, **_kwargs: Any) -> Any:
        return value

    return call


def _prompt_row_full():
    return SimpleNamespace(
        id="prm_1", workspace_id="wsp_1", owner_id="usr_1", access_level="private",
        namespace="imported", name="prompt-da-nhap-2", title="Ponytail Lazy Senior Dev Architect",
        purpose="", status="active",
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
    decision = SimpleNamespace(arguments={"prompt_id": "prm_1", "namespace": "Designer", "name": "AdaptiveLearningDesinger"}, query="")
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
        db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None,
        attachment="# Adaptive Learning Designer\n\nYou design lessons.",
        converted_xml="<prompt><system>x</system></prompt>",
    )
    result = await orchestrator._step_create_prompt(context, SimpleNamespace(query=""), [])

    assert result.proposal is not None
    assert result.proposal.arguments["title"] == "Adaptive Learning Designer"
