"""Chat-orchestrator alert rules name real metrics and match the locked alert set."""

from pathlib import Path

import yaml
from prometheus_client import REGISTRY

from prope.chat_orchestrator import observability  # noqa: F401

RULES = Path("deploy/prometheus/rules/chat_orchestrator.rules.yml")

#: Written out rather than derived, so that deleting an alert is a failing test
#: and not a quiet loss of coverage.
EXPECTED_ALERTS = {
    "ChatAgentCircuitOpen",
    "ChatTurnLatencyHigh",
    "ChatOutputRailFiring",
    "ChatInjectionAttemptsRising",
    "ChatGroundingDropped",
    "ChatRetrievalDegraded",
    "ChatPromptFallback",
    "ChatProposalsNeverConfirmed",
    "ChatDailyCostHigh",
    "ChatDirectivesDropped",
}


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    return document["groups"][0]["rules"]


def test_chat_orchestrator_declares_exactly_the_locked_alerts() -> None:
    assert {rule["alert"] for rule in _rules()} == EXPECTED_ALERTS


def test_every_chat_alert_names_a_real_metric() -> None:
    expressions = "\n".join(rule["expr"] for rule in _rules())
    metric_names = set(REGISTRY._names_to_collectors)  # noqa: SLF001
    required = {
        "chat_agent_circuit_open",
        "chat_turn_duration_seconds",
        "chat_output_rail_total",
        "chat_input_refused_total",
        "chat_grounding_score",
        "chat_retrieval_dense_unavailable_total",
        "chat_prompt_fallback_total",
        "chat_pending_action_total",
        "chat_cost_usd_total",
        "chat_directive_dropped_total",
    }

    assert required <= metric_names
    assert all(name in expressions for name in required)


def test_no_chat_alert_pages_anybody() -> None:
    """The assistant accelerates surfaces that all work without it.

    Search, the import screen and the documentation are each reachable with the
    chat panel closed, so nobody woken at 03:00 could do anything they could not
    do at 09:00. The alert that would justify a page — a guardrail failing open —
    is asserted in the test suite before deploy, where it can still be prevented.
    """
    assert {rule["labels"]["severity"] for rule in _rules()} == {"ticket"}


def test_every_chat_metric_label_has_a_closed_value_set() -> None:
    """ADR-0030, with no inherited debt.

    `prompt_search.observability` records three counters that carry `workspace_id`
    and `prompt_id` because its lock file declares those labels. Nothing here
    inherits that: every label below is a token from a closed vocabulary fixed in
    source, and no model-supplied string ever becomes one.
    """
    allowed = {"outcome", "intent", "tool", "reason", "rail", "decision", "direction", "program"}

    for name, collector in REGISTRY._names_to_collectors.items():  # noqa: SLF001
        if not name.startswith("chat_"):
            continue
        labels = set(getattr(collector, "_labelnames", ()))  # noqa: SLF001
        assert labels <= allowed, f"{name} declares an unapproved label: {labels - allowed}"
