"""Prompt-search alert rules name real metrics and match the locked alert set."""

from pathlib import Path

import yaml
from prometheus_client import REGISTRY

from prope.prompt_search import observability  # noqa: F401

RULES = Path("deploy/prometheus/rules/prompt_search.rules.yml")
EXPECTED_ALERTS = {
    # The three the lock file declares.
    "PromptSearchLatencyHigh",
    "PromptSearchIndexFailureRate",
    "PromptSearchAgentCircuitOpen",
    # The five the extraction agent added. Listed here rather than allowed
    # implicitly, so that deleting an alert is a failing test and not a quiet
    # loss of coverage.
    "PromptSearchExtractionQualityDropped",
    "PromptSearchExtractionInvalidRate",
    "PromptSearchExtractionPromptFallback",
    "PromptSearchExtractionDailyCostHigh",
    "PromptSearchExtractionTruncationHigh",
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
        "prompt_search_extraction_quality",
        "prompt_search_extraction_total",
        "prompt_search_extraction_prompt_fallback_total",
        "prompt_search_extraction_cost_usd_total",
        "prompt_search_extraction_body_truncated_total",
    }
    assert required <= metric_names
    assert all(name in expressions for name in required)


def test_every_extraction_metric_label_has_a_closed_value_set() -> None:
    """ADR-0030: no unbounded label on anything the extraction agent added.

    The three older `index_*` counters are excluded and the exclusion is the
    point — they carry `workspace_id`, and `index_triggered_total` also carries
    `prompt_id`, because `docs/modules/prompt-search.lock.yml` declares those
    labels. That debt is documented at the top of
    `src/prope/prompt_search/observability.py`. This test stops it spreading.
    """
    allowed = {"outcome", "direction"}

    for name, collector in REGISTRY._names_to_collectors.items():  # noqa: SLF001
        if not name.startswith("prompt_search_extraction"):
            continue
        labels = set(getattr(collector, "_labelnames", ()))  # noqa: SLF001
        assert labels <= allowed, f"{name} declares an unapproved label: {labels - allowed}"


def test_no_extraction_alert_pages_a_human() -> None:
    """Indexing is on-demand and async, and quick search works with no index at all.

    Nothing here is worth waking somebody for, so every extraction alert is
    `ticket`. Asserted because severity is the field most likely to be copied
    from another file without being reconsidered.
    """
    for rule in _rules():
        if "Extraction" in rule["alert"]:
            assert rule["labels"]["severity"] == "ticket", rule["alert"]
