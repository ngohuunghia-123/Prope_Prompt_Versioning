"""Thread memory, queued plans, folder disambiguation, and router fail-fast.

Four fixes for what the Langfuse traces showed: the router burning a minute on
sixty tokens, a follow-up request losing its referent ("đổi tên prompt ấy"),
a multi-write message dropping its second half at the first confirmation card,
and a near-miss folder name forking the workspace instead of asking. No model
is called, no database is touched, no socket leaves the process.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from prope.app_agent.dspy_runtime import build_lm
from prope.chat_orchestrator import dspy_program, orchestrator, repository, tools, tools_registry
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


class _Row:
    def __init__(self, **fields: Any) -> None:
        self.__dict__.update(fields)


def _registry(monkeypatch, prompts: list[Any], folders: list[Any]) -> None:
    """Stand in for `prompt_registry.repository`, which `thread_entities` imports."""
    import prope.prompt_registry.repository as registry_repository

    async def list_prompts(_db, *, actor_id, visible, limit):  # noqa: ANN001, ANN202
        return prompts[:limit]

    async def list_folders(_db, *, actor_id, visible):  # noqa: ANN001, ANN202
        return folders

    monkeypatch.setattr(registry_repository, "list_prompts", list_prompts)
    monkeypatch.setattr(registry_repository, "list_folders", list_folders)


def _prompt_row(index: int, day: int) -> Any:
    return _Row(
        id=f"prm_{index}",
        namespace="support",
        name=f"p{index}",
        title=f"Prompt {index}",
        updated_at=datetime(2026, 1, day, tzinfo=UTC),
    )


def _folder_row(slug: str, day: int) -> Any:
    return _Row(slug=slug, name=slug.title(), updated_at=datetime(2026, 1, day, tzinfo=UTC))


async def test_a_busy_workspace_still_shows_the_router_its_folders(monkeypatch) -> None:
    """**Recency across kinds is the wrong tie-break, and this is what it cost.**

    Four prompts touched today and a folder made last week is an ordinary state
    for an active workspace. Sorted by recency into four slots, the folder loses
    every time — so "Đổi tên thư mục Marketing thành Tăng trưởng" reached the
    router describing a workspace that appears to contain no folders at all, and
    a model with no reason to believe the folder exists reasonably plans
    `list_folders` to go and find out. The person gets a list and has to say it
    again.
    """
    _registry(
        monkeypatch,
        [_prompt_row(index, day=20) for index in range(4)],
        [_folder_row("marketing", day=2), _folder_row("nhap", day=1)],
    )

    entities = await tools_registry.thread_entities(None, actor_id="usr_1", visible=None)

    kinds = [entity["kind"] for entity in entities]
    assert kinds.count("folder") == tools_registry.FOLDER_SHARE, kinds
    assert len(entities) == 4
    assert "marketing" in {entity["ref"] for entity in entities}


async def test_the_kind_that_is_short_gives_its_slack_to_the_other(monkeypatch) -> None:
    """A workspace with no folders shows four prompts, exactly as before."""
    _registry(monkeypatch, [_prompt_row(index, day=20 - index) for index in range(6)], [])

    entities = await tools_registry.thread_entities(None, actor_id="usr_1", visible=None)

    assert [entity["kind"] for entity in entities] == ["prompt"] * 4


async def test_a_workspace_of_only_folders_fills_the_slots_with_them(monkeypatch) -> None:
    _registry(monkeypatch, [], [_folder_row(f"f{index}", day=10 - index) for index in range(6)])

    entities = await tools_registry.thread_entities(None, actor_id="usr_1", visible=None)

    assert [entity["kind"] for entity in entities] == ["folder"] * 4


async def test_everything_thread_state_offers_survives_the_render_cap(monkeypatch) -> None:
    """Reserving a folder slot is pointless if the renderer then truncates it."""
    _registry(
        monkeypatch,
        [_prompt_row(index, day=20) for index in range(4)],
        [_folder_row("marketing", day=2)],
    )

    entities = await tools_registry.thread_entities(None, actor_id="usr_1", visible=None)
    text = dspy_program.render_thread_entities(entities)

    assert len(entities) <= dspy_program.MAX_THREAD_ENTITIES
    assert "folder marketing" in text


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
        prior_activity=[],
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


def _wire_narrator(monkeypatch, *, reply: str = "Sẽ đổi tên prompt này.", error: Exception | None = None):
    """Stand in for the responder a queued step narrates its card with."""
    from prope.chat_orchestrator.prompting import ManagedPrompt

    class _Narrator:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def acall(self, **kwargs):
            self.calls.append(kwargs)
            if error is not None:
                raise error
            return SimpleNamespace(reply=reply, cited=[])

    narrator = _Narrator()
    monkeypatch.setattr(
        orchestrator,
        "load_responder_prompt",
        lambda: ManagedPrompt(text="responder", managed_prompt=None, version=1, is_fallback=False),
    )
    monkeypatch.setattr(dspy_program, "build_reply_program", lambda _: narrator)
    return narrator


def _queued_step(monkeypatch) -> list[str]:
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
    return calls


async def test_a_queued_step_narrates_its_card_without_a_router(monkeypatch) -> None:
    """No router, one narrator. The continuation stays deterministic — the tool
    and its arguments were fixed when the plan was made — but the card it
    stages used to arrive under an identical catalogue line every time, which
    read as "nothing happened" to the person approving their way through a
    chain. The settle marker is the narrator's question, and what it says is
    stored as the turn's reply."""
    calls = _queued_step(monkeypatch)
    narrator = _wire_narrator(monkeypatch, reply="Bước tiếp theo: đổi tên prompt.")

    result = await run_queued_step(
        open_db=_open_db,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        conversation_id="cnv_1",
        step={"tool": "update_prompt", "arguments": {"prompt_id": "prm_1", "title": "New"}},
        remaining=[{"tool": "retire_prompt", "arguments": {}}],
        question="HUMAN_DECISION confirmed create_folder. Continue the remaining task with tools, or acknowledge.",
        decided_actions=[{"tool": "create_folder", "status": "confirmed", "arguments": {"slug": "marketing"}}],
    )

    assert calls == ["ran"]
    assert result.reply == "Bước tiếp theo: đổi tên prompt."
    assert result.pending is not None
    assert result.code == "chat_proposal_pending"
    assert result.pending.remaining_steps == [{"tool": "retire_prompt", "arguments": {}}]
    # The narrator saw the settled action and the marker, never a routed plan.
    assert len(narrator.calls) == 1
    assert "HUMAN_DECISION" in narrator.calls[0]["question"]
    assert "already_confirmed=create_folder" in narrator.calls[0]["situation"]
    assert not any(
        entry.agent.startswith("supervisor") and entry.action == "route" and "queued" not in (entry.detail or {})
        for entry in result.trace
        if entry.detail
    )


async def test_a_dead_narrator_never_keeps_the_card_from_shipping(monkeypatch) -> None:
    """The continuation's product is the staged write; prose is decoration."""
    _queued_step(monkeypatch)
    _wire_narrator(monkeypatch, error=RuntimeError("responder down"))

    result = await run_queued_step(
        open_db=_open_db,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        conversation_id="cnv_1",
        step={"tool": "update_prompt", "arguments": {"prompt_id": "prm_1", "title": "New"}},
        remaining=[],
    )

    assert result.pending is not None
    assert result.pending.tool == ToolName.UPDATE_PROMPT
    assert result.reply == ""
    assert any(
        entry.detail.get("reason") == "responder_error"
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


# ---------------------------------------------------------------------------
# E: one sentence, two subjects
# ---------------------------------------------------------------------------
#
# "Tạo thư mục Marketing rồi chuyển prompt hoàn tiền vào đó" is one request
# with one point, and until these tests it was the request the product was
# worst at: five different models over the same live suite all planned it
# correctly and all five produced a folder and an unmoved prompt. The cause was
# never in the models — `_INTENT_TOOLS` deleted whichever half did not match
# the single intent the router had to declare, and `deferred` is computed from
# what survives that deletion, so the second half did not even reach the queue
# that exists to carry it.


def test_a_folder_turn_keeps_the_move_that_was_the_point_of_the_folder() -> None:
    """The folder exists in order to hold the prompt; both halves survive."""
    decision = _routed(
        ["create_folder", "move_prompt"],
        {"name": "Marketing", "prompt_id": "prm_1"},
        intent="manage_folder",
    )

    assert tuple(decision.tools) == ("create_folder",)
    assert tuple(decision.deferred) == ("move_prompt",)
    assert tuple(decision.dropped) == ()


def test_a_prompt_turn_keeps_the_folder_it_was_asked_to_create() -> None:
    """The same seam read from the other side: the person's subject is the prompt."""
    decision = _routed(
        ["move_prompt", "create_folder"],
        {"namespace": "Marketing", "prompt_id": "prm_1"},
        intent="manage_prompt",
    )

    assert tuple(decision.tools) == ("move_prompt",)
    assert tuple(decision.deferred) == ("create_folder",)


def test_the_queued_move_lands_in_the_folder_the_card_declared() -> None:
    """**The destination is the card's slug, never the router's flat `name`.**

    This is the bug the widening above would otherwise have created. The router
    writes one `changes` object for the whole turn, and `name` means the
    folder's label to `create_folder` and the prompt's *new slug* to
    `move_prompt`. Carried whole, the queued move reads `name="Marketing"` with
    no namespace and re-identifies the prompt as `marketing` in the folder it
    was already in — a silent rename, on a card whose summary reads like the
    move that was asked for.
    """
    decision = _routed(
        ["create_folder", "move_prompt"],
        {"name": "Marketing", "prompt_id": "prm_1"},
        intent="manage_folder",
    )

    queued = _remaining_plan(decision, [], _card("create_folder", slug="marketing", name="Marketing"), [])

    assert [step["tool"] for step in queued] == ["move_prompt"]
    assert queued[0]["arguments"]["namespace"] == "marketing"
    assert "name" not in queued[0]["arguments"], "the folder's label is not the prompt's new slug"


def test_the_queued_folder_takes_its_name_from_the_move_that_named_it() -> None:
    """The mirror image: the move went first and named a namespace nothing backs."""
    decision = _routed(
        ["move_prompt", "create_folder"],
        {"namespace": "Marketing", "prompt_id": "prm_1"},
        intent="manage_prompt",
    )

    queued = _remaining_plan(
        decision, [], _card("move_prompt", prompt_id="prm_1", namespace="marketing", name="refund"), []
    )

    assert [step["tool"] for step in queued] == ["create_folder"]
    # The person's own spelling, not the slug the move derived from it.
    assert queued[0]["arguments"]["name"] == "Marketing"


def test_a_tool_the_intent_refuses_is_recorded_instead_of_vanishing() -> None:
    """A refusal nobody can see is indistinguishable from success.

    The gate's verdict is unchanged — `retire_prompt` does not run on a
    documentation question and never reaches a card. What changed is that the
    turn now knows it said no. Before this, the responder saw only the half
    that succeeded and wrote a reply saying the whole request had been carried
    out, which is the one failure mode a person cannot recover from: they stop
    asking.
    """
    decision = dspy_program.routing_of(
        SimpleNamespace(
            intent="docs_question",
            tools=["answer_from_docs", "retire_prompt"],
            query="",
            changes={},
            rationale="",
        )
    )

    assert tuple(decision.tools) == ("answer_from_docs",)
    assert tuple(decision.dropped) == ("retire_prompt",)


def test_the_responder_is_told_which_write_did_not_happen() -> None:
    from prope.chat_orchestrator.orchestrator import _situation

    situation = _situation([], None, [], [], [], ("retire_prompt",))

    assert "not_attempted=retire_prompt" in situation


def test_the_situation_names_what_a_confirmed_action_did() -> None:
    """A bare tool name left "bạn vừa làm gì?" answered with "nothing happened"
    — the model held the fact of a confirmation and no way to say what."""
    from prope.chat_orchestrator.orchestrator import _situation

    situation = _situation(
        [],
        None,
        [],
        [
            {
                "tool": "delete_folder",
                "status": "confirmed",
                "arguments": {"slug": "3d", "backup_to": "backup"},
                "result_prompt_id": None,
            },
            {"tool": "move_prompt", "status": "rejected", "arguments": {"prompt_id": "prm_1"}},
        ],
        [],
    )

    assert 'already_confirmed=delete_folder({"backup_to": "backup", "slug": "3d"})' in situation
    # A rejection wrote nothing, so it is memory of a decision, not a fact.
    assert "already_confirmed=move_prompt" not in situation


def test_an_action_that_created_a_row_says_so() -> None:
    """The referent a follow-up ("rename that prompt") has to resolve against."""
    from prope.chat_orchestrator.orchestrator import _situation

    situation = _situation(
        [],
        None,
        [],
        [{"tool": "create_prompt", "status": "confirmed", "arguments": {"title": "X"}, "result_prompt_id": "prm_7"}],
        [],
    )

    assert "already_confirmed=create_prompt" in situation
    assert "[created prm_7]" in situation


def test_the_pending_line_carries_the_cards_exact_target() -> None:
    """On a proposal-only turn there is no evidence; these arguments are where
    a narration learns which folder or key it must name."""
    from prope.chat_orchestrator.orchestrator import _situation

    situation = _situation([], _card("delete_folder", slug="3d", backup_to="backup"), [])

    assert 'awaiting_confirmation=delete_folder({"backup_to": "backup", "slug": "3d"})' in situation


def test_a_refused_read_is_not_worth_the_reply_s_attention() -> None:
    """A read the gate refused cost the person nothing and claimed nothing."""
    from prope.chat_orchestrator.orchestrator import _situation

    assert "not_attempted" not in _situation([], None, [], [], [], ("list_folders",))


def test_a_second_write_with_no_card_to_queue_behind_is_still_named() -> None:
    """The first write asked a question; the second had nowhere to go.

    `_remaining_plan` correctly returns nothing — a write cannot queue behind a
    confirmation card that was never staged. What was missing is that the person
    was never told. "Tạo thư mục Marketing rồi chuyển prompt X vào đó" against a
    workspace that already has a Marketing folder answers "did you mean that
    one?", and the move disappears between the question and the answer.
    """
    decision = _routed(
        ["create_folder", "move_prompt"],
        {"name": "Marketing", "prompt_id": "prm_1"},
        intent="manage_folder",
    )

    assert tuple(decision.deferred) == ("move_prompt",)
    assert _remaining_plan(decision, [], None, []) == []

    from prope.chat_orchestrator.orchestrator import _situation

    assert "not_attempted=move_prompt" in _situation([], None, [], [], [], tuple(decision.deferred))


def test_a_card_with_a_refusal_beside_it_still_gets_a_reply() -> None:
    """The proposal-only fast path must not swallow the half that was refused.

    A card on its own skips the responder, which is right when the card is the
    whole answer. It is wrong when part of the sentence was declined: the person
    approves what they were shown and never learns the rest was not going to
    happen.
    """
    from prope.chat_orchestrator.orchestrator import _card_speaks_for_itself

    card = _card("create_folder", slug="marketing")

    assert _card_speaks_for_itself(card, {}, [], ())
    assert not _card_speaks_for_itself(card, {}, [], ("move_prompt",))
    # The cases that already skipped the responder keep skipping it.
    assert not _card_speaks_for_itself(None, {}, [], ())
    assert not _card_speaks_for_itself(card, {}, ["tool_failed"], ())


# ---------------------------------------------------------------------------
# H: the thread remembers what its tools did on earlier turns
# ---------------------------------------------------------------------------
#
# A follow-up turn that runs no tool of its own — "what did you just do?" — used
# to route to nothing, hit `no_tool_ran`, and, per the responder's grounding
# rule, answer that it could not say what happened: the delete a card had
# approved and the search it had run were both invisible the moment the turn that
# made them ended. `chat.message.trace` held the record all along, read back only
# to draw the client's timeline; `recent_tool_activity` is what puts it in front
# of the responder as `earlier=<tool>:<outcome>`.


def test_the_responder_is_told_what_earlier_turns_ran() -> None:
    from prope.chat_orchestrator.orchestrator import _situation

    situation = _situation(
        [], None, [], [], [], (),
        prior_activity=[{"tool": "delete_folder", "outcome": "ok"}, {"tool": "search_prompts", "outcome": "ok"}],
    )

    assert "earlier=delete_folder:ok" in situation
    assert "earlier=search_prompts:ok" in situation


def test_no_tool_this_turn_does_not_erase_what_earlier_turns_did() -> None:
    """The two facts coexist: nothing ran now, and the delete did happen before."""
    from prope.chat_orchestrator.orchestrator import _situation

    situation = _situation([], None, [], [], [], (), prior_activity=[{"tool": "delete_folder", "outcome": "ok"}])

    assert "no_tool_ran" in situation
    assert "earlier=delete_folder:ok" in situation


def test_prior_activity_is_optional_and_changes_nothing_when_empty() -> None:
    """Every existing caller that omits it must render exactly as before."""
    from prope.chat_orchestrator.orchestrator import _situation

    assert _situation([], None, [], [], [], ("retire_prompt",)) == _situation(
        [], None, [], [], [], ("retire_prompt",), prior_activity=[]
    )


class _ScalarResult:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[Any]:
        return list(self._values)


class _FakeDB:
    """The one call `recent_tool_activity` makes: `execute(...).scalars().all()`."""

    def __init__(self, traces: list[Any]) -> None:
        self._traces = traces

    async def execute(self, _statement: Any, _params: Any) -> _ScalarResult:
        return _ScalarResult(self._traces)


async def test_recent_tool_activity_keeps_only_tool_executions() -> None:
    """A turn's trace is mostly supervisor and guardrail spans; only the worker
    executions are what a tool did, and only their tool and outcome ride back."""
    trace = [
        {"agent": "guardrail.input", "action": "inspect", "status": "ok", "detail": {}},
        {"agent": "supervisor", "action": "route", "status": "ok", "detail": {"intent": "manage_folder"}},
        {"agent": "worker.delete_folder", "action": "execute", "status": "ok", "detail": {"tool": "delete_folder", "outcome": "ok"}},
        {"agent": "supervisor", "action": "respond", "status": "ok", "detail": {}},
    ]

    activity = await repository.recent_tool_activity(_FakeDB([trace]), "cnv_1", actor_id="usr_1")

    assert activity == [{"tool": "delete_folder", "outcome": "ok"}]


async def test_recent_tool_activity_reads_the_outcome_of_a_failed_tool() -> None:
    trace = [
        {"agent": "worker.search_prompts", "action": "execute", "status": "error", "detail": {"tool": "search_prompts", "outcome": "error"}},
    ]

    activity = await repository.recent_tool_activity(_FakeDB([trace]), "cnv_1", actor_id="usr_1")

    assert activity == [{"tool": "search_prompts", "outcome": "error"}]


async def test_recent_tool_activity_falls_back_to_the_agent_name_and_status() -> None:
    """An older trace whose detail lost `tool`/`outcome` still names the tool: the
    agent field is `worker.<tool>` and the entry's own status stands in."""
    trace = [{"agent": "worker.list_folders", "action": "execute", "status": "ok", "detail": {}}]

    activity = await repository.recent_tool_activity(_FakeDB([trace]), "cnv_1", actor_id="usr_1")

    assert activity == [{"tool": "list_folders", "outcome": "ok"}]


async def test_recent_tool_activity_tolerates_a_stringified_trace() -> None:
    """A malformed or string-encoded trace must never fail the turn it feeds."""
    import json

    good = json.dumps([{"agent": "worker.get_prompt", "action": "execute", "status": "ok", "detail": {"tool": "get_prompt", "outcome": "ok"}}])

    activity = await repository.recent_tool_activity(_FakeDB([good, "{not json", None]), "cnv_1", actor_id="usr_1")

    assert activity == [{"tool": "get_prompt", "outcome": "ok"}]


async def test_recent_tool_activity_caps_the_number_of_lines() -> None:
    """The block is bounded so a long thread cannot grow every later turn's input."""
    trace = [
        {"agent": "worker.get_prompt", "action": "execute", "status": "ok", "detail": {"tool": "get_prompt", "outcome": "ok"}}
        for _ in range(30)
    ]

    activity = await repository.recent_tool_activity(_FakeDB([trace]), "cnv_1", actor_id="usr_1", entry_limit=5)

    assert len(activity) == 5
