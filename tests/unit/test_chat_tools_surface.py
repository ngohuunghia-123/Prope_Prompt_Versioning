"""The expanded catalogue: routing, directives, proposals and the secret-once rule.

Nothing here calls a model or touches a database. What is asserted is the
boundary behaviour the full-surface extension must keep: at most one write per
plan, directives derived from what ran, destructive acts pinned behind a person's
confirmation, and every navigation target being a page the product actually has.
"""

from types import SimpleNamespace
from typing import Any

import pytest

from prope.chat_orchestrator import guardrails, orchestrator, tools, tools_access, tools_registry
from prope.chat_orchestrator.domain import ToolName
from prope.chat_orchestrator.dspy_program import routing_of

MODULE_ROOT = "src/prope-fe/features/prompt-lifecycle/PromptLifecycleRoutes.tsx"


def _prediction(**overrides: object) -> SimpleNamespace:
    base = {
        "intent": "manage_prompt",
        "tools": ["get_prompt"],
        "query": "hoàn tiền",
        "rationale": "ok",
        "changes": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _context() -> tools.ToolContext:
    return tools.ToolContext(db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None)


def _result(tool: str, evidence: tuple = (), payload: dict | None = None) -> tools.ToolResult:
    return tools.ToolResult(tool=tool, outcome="ok", evidence=evidence, payload=payload or {})


# ---------------------------------------------------------------------------
# routing_of with write arguments
# ---------------------------------------------------------------------------


def test_changes_become_bounded_arguments() -> None:
    decision = routing_of(
        _prediction(changes={"title": "  New title  ", "tags": ["a", "b"], "junk": {"n": 1}})
    )

    assert decision.arguments["title"] == "New title"
    assert decision.arguments["tags"] == ["a", "b"]
    assert "junk" not in decision.arguments


def test_a_structurally_wrong_changes_field_yields_no_arguments() -> None:
    for changes in (None, "title=New", [1, 2], 42):
        decision = routing_of(_prediction(changes=changes))
        assert decision.arguments == {}, changes


def test_only_one_write_survives_and_reads_precede_it() -> None:
    from prope.chat_orchestrator.domain import TOOLS

    decision = routing_of(_prediction(tools=["update_prompt", "retire_prompt"], query="x"))

    writes = [name for name in decision.tools if TOOLS[name].writes]
    assert len(writes) == 1
    assert decision.tools[-1] == writes[0]


def test_a_non_import_write_travels_with_prior_reads() -> None:
    from prope.chat_orchestrator.domain import TOOLS

    decision = routing_of(
        _prediction(tools=["list_versions", "retire_prompt", "create_folder"])
    )

    writes = [name for name in decision.tools if TOOLS[name].writes]
    assert writes == [ToolName.RETIRE_PROMPT]
    assert decision.tools.index(ToolName.LIST_VERSIONS) < decision.tools.index(
        ToolName.RETIRE_PROMPT
    )


def test_the_import_write_keeps_its_prerequisites_in_order() -> None:
    decision = routing_of(
        _prediction(intent="import_prompt", tools=["create_prompt", "find_duplicates", "convert_prompt"])
    )

    assert decision.tools == (
        ToolName.CONVERT_PROMPT,
        ToolName.FIND_DUPLICATES,
        ToolName.CREATE_PROMPT,
    )


# ---------------------------------------------------------------------------
# Directives for the new intents — derived, never generated
# ---------------------------------------------------------------------------


def _kinds(directives: list[dict]) -> dict[str, dict]:
    """`_directives_for` returns flat dicts: `{"kind": ..., **arguments}`."""
    return {d["kind"]: {k: v for k, v in d.items() if k != "kind"} for d in directives}


def test_key_intents_land_on_the_keys_screen() -> None:
    directives = orchestrator._directives_for("manage_keys", [_result("list_api_keys")], None)
    kinds = _kinds(directives)

    assert kinds["navigate"] == {"to": "/app/settings/keys"}
    assert kinds["highlight"] == {"target": "keys-list"}


def test_provider_reads_land_on_the_providers_screen() -> None:
    evidence = (
        tools.Evidence(tag="E1", kind="provider", reference="prv_1", label="OpenRouter", text=""),
    )
    directives = orchestrator._directives_for(
        "manage_providers", [_result("list_providers", evidence)], None
    )
    kinds = _kinds(directives)

    assert kinds["navigate"] == {"to": "/app/settings/providers"}


def test_a_folder_read_with_a_winner_opens_that_folder() -> None:
    evidence = (
        tools.Evidence(tag="E1", kind="folder", reference="marketing", label="Marketing", text=""),
    )
    directives = orchestrator._directives_for(
        "manage_folder", [_result("list_folders", evidence)], None
    )

    assert any(
        d["kind"] == "navigate" and d["to"] == "/app/prompts/folder/marketing"
        for d in directives
    )


def test_a_pending_key_proposal_navigates_before_asking() -> None:
    proposal = tools.Proposal(
        tool=ToolName.CREATE_API_KEY, summary="mobile", preview={}, arguments={}
    )
    directives = orchestrator._directives_for("manage_keys", [], proposal)

    assert directives[0] == {"kind": "navigate", "to": "/app/settings/keys"}


def test_a_pending_eval_run_proposal_opens_the_run_page() -> None:
    proposal = tools.Proposal(
        tool=ToolName.START_EVAL_RUN,
        summary="v3",
        preview={},
        arguments={"prompt_id": "prm_1", "version_id": "ver_9"},
    )
    directives = orchestrator._directives_for("run_evaluation", [], proposal)

    assert any(
        d["kind"] == "navigate" and d["to"] == "/app/prompts/prm_1/evaluation/run"
        for d in directives
    )


def test_status_checks_open_the_prompt_on_the_evaluation_tab() -> None:
    result = _result("get_eval_results", payload={"prompt_id": "prm_7", "run_ids": []})
    directives = orchestrator._directives_for("check_status", [result], None)

    kinds = _kinds(directives)
    assert kinds["navigate"] == {"to": "/app/prompts/prm_7"}
    assert kinds["select_tab"] == {"tab": "evaluation"}


# ---------------------------------------------------------------------------
# Target resolution helpers
# ---------------------------------------------------------------------------


def test_targets_resolve_against_evidence_labels_not_model_invention() -> None:
    evidence = (
        tools.Evidence(tag="E1", kind="api_key", reference="key_9", label="staging key", text=""),
    )
    results = [_result("list_api_keys", evidence)]

    assert orchestrator._target_from_evidence(results, ("api_key",), "staging") == "key_9"
    assert orchestrator._target_from_evidence(results, ("api_key",), "") == "key_9"
    assert orchestrator._target_from_evidence(results, ("api_key",), "production") == ""


def test_csv_parses_scope_fields() -> None:
    assert orchestrator._csv("a, b ,c") == ["a", "b", "c"]
    assert orchestrator._csv(["x", "y"]) == ["x", "y"]
    assert orchestrator._csv("") is None
    assert orchestrator._csv(None) is None


def test_an_update_without_any_change_refuses_rather_than_writes() -> None:
    result = tools_registry.propose_update_prompt(_context(), prompt_id="prm_1")

    assert result.outcome == "error"
    assert result.reason == "chat_tool_nothing_to_change"


def test_a_key_proposal_cleans_and_bounds_its_scopes() -> None:
    result = tools_access.propose_create_api_key(
        _context(),
        name=" mobile ",
        scope_model_names=["  m1  ", "", "m1"],
        scope_namespaces=[123],
    )

    assert result.outcome == "ok"
    arguments = result.proposal.arguments
    assert arguments["name"] == "mobile"
    assert arguments["scope_model_names"] == ["m1"]
    assert arguments["scope_namespaces"] == []


# ---------------------------------------------------------------------------
# The confirmation route: secret-once and navigation
# ---------------------------------------------------------------------------


async def test_a_confirmed_key_returns_its_secret_exactly_once(monkeypatch) -> None:
    async def executor(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"key_id": "key_1", "secret_once": "pk_live_demo_value", "last_four": "alue"}

    monkeypatch.setattr(orchestrator, "CONFIRMED_EXECUTORS", {"create_api_key": executor})

    outcome = await orchestrator.confirm_action(
        db=None,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        action={"tool": "create_api_key", "arguments": {}},
        approve=True,
    )

    assert outcome.status == "confirmed"
    assert outcome.secret_once == "pk_live_demo_value"
    assert outcome.key_id == "key_1"
    kinds = {d.kind: d.arguments for d in outcome.directives}
    assert kinds["navigate"] == {"to": "/app/settings/keys"}
    assert kinds["highlight"] == {"target": "keys-list"}
    # The decision was taken in the chat rail; navigating without carrying the
    # panel along would hide the minted key's only showing.
    assert kinds["open_panel"] == {"panel": "chat"}


async def test_a_rejection_writes_nothing_and_leaks_nothing(monkeypatch) -> None:
    ran: list[str] = []

    async def executor(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
        ran.append("ran")
        return {}

    monkeypatch.setattr(orchestrator, "CONFIRMED_EXECUTORS", {"delete_folder": executor})

    outcome = await orchestrator.confirm_action(
        db=None,
        workspace_id="wsp_1",
        actor_id="usr_1",
        visible=None,
        action={"tool": "delete_folder", "arguments": {}},
        approve=False,
    )

    assert outcome.status == "rejected"
    assert ran == []


# ---------------------------------------------------------------------------
# The navigation allow-list and its frontend twin
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "/app/settings/keys",
        "/app/settings/providers",
        "/app/settings/workspace",
        "/app/prompts/prm_1/evaluation/run",
        "/app/prompts/folder/marketing",
    ],
)
def test_new_action_pages_are_navigable(target: str) -> None:
    assert guardrails.sanitise_directives([{"kind": "navigate", "to": target}]), target


@pytest.mark.parametrize("target", ["/app/calls", "/app/providers", "/app/settings/keys?x=1"])
def test_routes_that_do_not_exist_or_carry_payloads_are_dropped(target: str) -> None:
    assert guardrails.sanitise_directives([{"kind": "navigate", "to": target}]) == []


def test_every_static_allow_list_route_exists_in_the_frontend_router() -> None:
    """`guardrails.NAVIGATION_ALLOW_LIST` promises this sync in its own comment.

    Dynamic routes (`{id}`) are covered by their literal prefix; only the static
    ones can be asserted mechanically, and those are exactly the ones a rename in
    either codebase would silently orphan.
    """
    source = open(MODULE_ROOT, encoding="utf-8").read()
    frontend_paths = {
        match.strip().strip('"')
        for match in source.split('path="')[1:]
    }

    required = {
        "/app/prompts": {"prompts"},
        "/app/prompts/new": {"prompts/new"},
        "/app/prompts/new/wizard": {"prompts/new/wizard"},
        "/app/search": {"search"},
        "/app/reviews": {"reviews"},
        "/app/datasets": {"datasets"},
        "/app/imports/new": {"imports/new"},
        "/app/settings/providers": {"settings/providers"},
        "/app/settings/keys": {"settings/keys"},
        "/app/settings/workspace": {"settings/workspace"},
    }
    missing = {
        route: literal
        for route, literals in required.items()
        for literal in literals
        if literal not in frontend_paths and f'{literal}"' not in source.replace('path="', '"')
    }
    assert missing == {}
