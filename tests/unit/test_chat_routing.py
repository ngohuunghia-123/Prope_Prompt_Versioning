"""The supervisor's decision layer: what the router may decide, and what it may not.

The property under test is the Action-Selector pattern (deck 5, p40) holding
under a hostile model. `routing_of` is the boundary between *what a language
model emitted* and *what this system will run*, so every test below assumes the
model is wrong on purpose and asserts that being wrong is survivable.

Nothing here calls a model.
"""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from prope.chat_orchestrator import dspy_program
from prope.chat_orchestrator.domain import (
    MAX_PLAN_STEPS,
    TOOLS,
    WRITE_TOOLS,
    HitlModel,
    Intent,
    ToolName,
)
from prope.chat_orchestrator.dspy_program import routing_of

MODULE_ROOT = Path(__file__).resolve().parents[2] / "src" / "prope" / "chat_orchestrator"


def _prediction(**overrides: object) -> SimpleNamespace:
    base = {"intent": "search", "tools": ["search_prompts"], "query": "hoàn tiền", "rationale": "ok"}
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------


def test_the_catalogue_holds_no_outbound_capability() -> None:
    """The lethal trifecta (deck 5, p41) broken by construction, not by policy.

    Private data and untrusted content are irreducible here — the assistant reads
    the workspace's own prompts, and a prompt body is untrusted by definition. So
    the third leg must be absent, and *absent* means no tool whose name or
    description implies sending, posting, fetching or emailing.

    Asserted over the catalogue rather than trusted to review, because the day
    somebody adds `share_prompt` this is the test that should stop them.
    """
    forbidden = ("send", "email", "post", "fetch", "http", "url", "webhook", "upload", "export")

    for name, spec in TOOLS.items():
        assert not any(word in name.lower() for word in forbidden), name
        assert not any(word in spec.description.lower() for word in forbidden), name


def test_the_catalogue_cannot_reach_the_approval_chain() -> None:
    """No tool submits, approves, releases, or breaks glass.

    Prope's first non-negotiable is that no prompt reaches production without a
    recorded human approval. An assistant that could approve would not violate
    that in letter — a human asked it to — and would gut it in substance.

    Destructive acts (`retire`, `delete`, `revoke`) ARE in the catalogue by
    decision, but only ever as HITL proposals: the assertion below pins them to
    `writes=True` so none of them can ever execute without a person's recorded
    confirmation.
    """
    forbidden_verbs = ("submit", "approve", "break_glass", "withdraw")
    destructive = ("retire", "delete", "revoke")

    for name, spec in TOOLS.items():
        if not spec.writes:
            continue
        # Reads may REPORT on the chain (`get_release_status`); no WRITE may act
        # on it. `release` is forbidden even as a substring of a write name.
        assert "release" not in name.lower(), name
        assert not any(word in name.lower() for word in forbidden_verbs), name

    for name, spec in TOOLS.items():
        if any(word in name.lower() for word in destructive):
            assert spec.writes, f"{name} must be a confirmed write"


def test_every_write_tool_requires_a_person_and_every_read_tool_does_not() -> None:
    for name, spec in TOOLS.items():
        expected = HitlModel.IN_THE_LOOP if spec.writes else HitlModel.ON_THE_LOOP
        assert spec.hitl == expected, name

    assert WRITE_TOOLS == {
        ToolName.CREATE_PROMPT,
        ToolName.CREATE_REVISION,
        ToolName.UPDATE_PROMPT,
        ToolName.RETIRE_PROMPT,
        ToolName.CREATE_FOLDER,
        ToolName.RENAME_FOLDER,
        ToolName.DELETE_FOLDER,
        ToolName.CREATE_API_KEY,
        ToolName.REVOKE_API_KEY,
        ToolName.SET_API_KEY_SCOPE,
        ToolName.UPDATE_PROVIDER,
        ToolName.DELETE_PROVIDER,
        ToolName.START_EVAL_RUN,
    }


def test_every_tool_names_a_permission_the_vocabulary_actually_has() -> None:
    """`ToolSpec.permission` is a string so this module keeps no import edge to
    access-control. This is what stops the string drifting from the enum."""
    from prope.access_control.actions import Action

    values = {action.value for action in Action}
    for name, spec in TOOLS.items():
        assert spec.permission in values, f"{name} names {spec.permission!r}"


def test_the_catalogue_the_router_sees_is_generated_from_the_catalogue_that_runs() -> None:
    """Otherwise the router keeps choosing something that no longer executes."""
    rendered = dspy_program.catalogue_text()

    for name, spec in TOOLS.items():
        assert name in rendered
        assert spec.description.split(".")[0] in rendered


# ---------------------------------------------------------------------------
# routing_of
# ---------------------------------------------------------------------------


def test_a_clean_decision_survives_intact() -> None:
    decision = routing_of(_prediction())

    assert decision.intent == Intent.SEARCH
    assert decision.tools == (ToolName.SEARCH_PROMPTS,)
    assert decision.query == "hoàn tiền"


def test_an_intent_nobody_declared_becomes_a_refusal() -> None:
    """Default-deny at the vocabulary level. An unknown intent must not fall
    through to a branch nobody wrote, because every such failure is silent in the
    permissive direction."""
    decision = routing_of(_prediction(intent="exfiltrate", tools=["search_prompts"]))

    assert decision.intent == Intent.REFUSED
    assert decision.tools == ()


def test_a_tool_outside_the_catalogue_is_dropped() -> None:
    decision = routing_of(_prediction(tools=["send_email", "search_prompts", "os.system"]))

    assert decision.tools == (ToolName.SEARCH_PROMPTS,)


def test_the_intent_gates_the_tool_and_not_only_the_catalogue() -> None:
    """**The router proposes and the table disposes.**

    A model talked into emitting `create_prompt` on a documentation question is
    the realistic shape of this attack — the tool name is legitimate, the
    catalogue admits it, and only the intent says it does not belong. This is the
    second half of Action-Selector and the reason `_INTENT_TOOLS` exists.
    """
    decision = routing_of(_prediction(intent="docs_question", tools=["create_prompt"]))

    assert decision.intent == Intent.DOCS_QUESTION
    assert decision.tools == ()


def test_small_talk_and_refusal_reach_no_tool_at_all() -> None:
    for intent in ("smalltalk", "refused"):
        assert routing_of(_prediction(intent=intent, tools=list(TOOLS))).tools == ()


def test_a_write_keeps_only_ordered_import_prerequisites() -> None:
    """Conversion state must exist before a write proposal can be constructed."""
    decision = routing_of(
        _prediction(
            intent="import_prompt",
            tools=["create_prompt", "find_duplicates", "convert_prompt"],
        )
    )

    assert decision.tools == (
        ToolName.CONVERT_PROMPT,
        ToolName.FIND_DUPLICATES,
        ToolName.CREATE_PROMPT,
    )


def test_a_plan_is_capped_and_duplicates_collapse() -> None:
    decision = routing_of(
        _prediction(
            intent="import_prompt",
            tools=["convert_prompt", "convert_prompt", "find_duplicates", "convert_prompt"],
        )
    )

    assert decision.tools == (ToolName.CONVERT_PROMPT, ToolName.FIND_DUPLICATES)
    assert len(decision.tools) <= MAX_PLAN_STEPS


@pytest.mark.parametrize("tools", [None, "search_prompts", 42, [None, 7], {}])
def test_a_structurally_wrong_tools_field_yields_an_empty_plan(tools: object) -> None:
    """Fixed, never rejected: a turn with no plan still answers the person."""
    assert routing_of(_prediction(tools=tools)).tools == ()


def test_the_rationale_is_bounded_so_it_cannot_become_a_content_channel() -> None:
    """It is written into the trace, which is stored and returned."""
    decision = routing_of(_prediction(rationale="x" * 5_000))

    assert len(decision.rationale) <= 240


def test_the_query_is_bounded_too() -> None:
    assert len(routing_of(_prediction(query="q" * 5_000)).query) <= 500


def test_a_prediction_missing_every_field_still_produces_a_decision() -> None:
    decision = routing_of(SimpleNamespace())

    assert decision.intent == Intent.REFUSED
    assert decision.tools == ()
    assert decision.query == ""


# ---------------------------------------------------------------------------
# reply_of and history
# ---------------------------------------------------------------------------


def test_citation_tags_are_normalised_and_deduplicated() -> None:
    reply, cited = dspy_program.reply_of(
        SimpleNamespace(reply="  Tìm thấy 2 prompt.  ", cited=["[E1]", "e1", "E2", "", None])
    )

    assert reply == "Tìm thấy 2 prompt."
    assert cited == ("E1", "E2")


def test_history_drops_the_oldest_turn_when_the_budget_bites(monkeypatch) -> None:
    """Never the newest. A history that dropped the most recent message would
    route the turn before last, which is the least obvious way to be wrong."""
    monkeypatch.setattr(dspy_program, "MAX_HISTORY_CHARACTERS", 30)

    rendered = dspy_program.truncate_history(["oldest turn here", "middle turn", "newest"])

    assert rendered.endswith("newest")
    assert "oldest turn here" not in rendered


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------


def test_no_module_here_labels_a_langfuse_prompt_except_the_bootstrap() -> None:
    """The same governance rule the other two agents carry.

    Labelling a version `production` is a release. Only `bootstrap_prompt.py` may
    do it, and only because the text it labels is the compiled-in fallback the
    module would have run anyway.
    """
    offenders: list[str] = []

    for path in MODULE_ROOT.rglob("*.py"):
        if path.name == "bootstrap_prompt.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "labels":
                    offenders.append(f"{path.name}:{node.lineno}")

    assert offenders == [], f"a non-bootstrap module labels a prompt version: {offenders}"


def test_neither_program_uses_chain_of_thought() -> None:
    """A rationale field on the responder would put retrieved prompt content in a
    second place the telemetry layer then has to keep clean, for no gain the
    grounding rules do not already buy."""
    source = (MODULE_ROOT / "dspy_program.py").read_text(encoding="utf-8")

    assert "ChainOfThought" not in source.replace("No `ChainOfThought`", "")


def test_the_instructions_carry_both_named_injection_defences() -> None:
    """Spotlighting and instruction hierarchy (deck 5, p38), in the text itself.

    Asserted because both are prose, and prose is what gets tidied away. The
    `SECURITY BOUNDARY` marker is doubly load-bearing: `scrub_reply` treats its
    appearance in a REPLY as a leak, so deleting it here would silently disarm
    that rail too.
    """
    from prope.chat_orchestrator.prompting import (
        FALLBACK_RESPONDER_PROMPT,
        FALLBACK_ROUTER_PROMPT,
    )

    for text in (FALLBACK_ROUTER_PROMPT, FALLBACK_RESPONDER_PROMPT):
        assert "SECURITY BOUNDARY" in text
        assert "UNTRUSTED DATA" in text
        assert "precedence" in text.lower()


# ---------------------------------------------------------------------------
# The improvement flow: drafting and research in the catalogue
# ---------------------------------------------------------------------------


def test_manage_prompt_reaches_the_revision_proposal_and_docs_reaches_research() -> None:
    """An instruction-shaped body change is a manage-prompt act, so the intent
    that names the prompt must be able to propose its revision; technique
    questions may add one research leg beside the documentation answer."""
    from prope.chat_orchestrator.dspy_program import _INTENT_TOOLS

    assert ToolName.CREATE_REVISION in _INTENT_TOOLS[Intent.MANAGE_PROMPT]
    assert ToolName.RESEARCH_TOPIC in _INTENT_TOOLS[Intent.DOCS_QUESTION]


def test_the_research_tool_is_a_read_that_never_runs_uninvited() -> None:
    spec = TOOLS[ToolName.RESEARCH_TOPIC]
    assert not spec.writes
    assert spec.hitl == HitlModel.ON_THE_LOOP


def test_the_drafter_program_exists_and_parses_its_fields() -> None:
    """A drafter whose output fields drifted from `draft_of` would stage
    empty bodies — validated here against the signature, not a model."""
    prediction = SimpleNamespace(drafted_body="<prompt><system>x</system></prompt>",
                                 change_summary="  thêm   rào chặn ")
    body, summary = dspy_program.draft_of(prediction)
    assert body.startswith("<prompt>")
    # The summary is collapsed; the body never is.
    assert summary == "thêm rào chặn"


def test_a_drafted_plan_keeps_its_single_write_without_import_prerequisites() -> None:
    """The import cap (convert + duplicates before the write) must not demand
    those prerequisites of a drafted revision: there is no source to convert."""
    decision = routing_of(
        _prediction(intent="manage_prompt", tools=["get_prompt", "create_revision"], query="3d")
    )
    assert tuple(decision.tools) == ("get_prompt", "create_revision")
