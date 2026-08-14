"""Prompt-search alert rules name real metrics and match the locked alert set."""

from pathlib import Path

import yaml
from prometheus_client import REGISTRY

from prope.prompt_search import observability  # noqa: F401

RULES = Path("deploy/prometheus/rules/prompt_search.rules.yml")
EXPECTED_ALERTS = {
    "PromptSearchLatencyHigh",
    "PromptSearchIndexFailureRate",
    "PromptSearchAgentCircuitOpen",
}


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    return document["groups"][0]["rules"]


def test_prompt_search_declares_exactly_the_locked_alerts() -> None:
    assert {rule["alert"] for rule in _rules()} == EXPECTED_ALERTS


def test_every_prompt_search_alert_names_a_real_metric() -> None:
    expressions = "\n".join(rule["expr"] for rule in _rules())
    metric_names = set(REGISTRY._names_to_collectors)  # noqa: SLF001
    required = {
        "prompt_search_ai_duration_seconds",
        "prompt_search_index_failed_total",
        "prompt_search_index_triggered_total",
        "prompt_search_agent_circuit_open",
    }
    assert required <= metric_names
    assert all(name in expressions for name in required)
