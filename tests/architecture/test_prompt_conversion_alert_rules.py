"""Prompt-conversion alert rules name real metrics and match the locked alert set.

The failure this file exists to prevent is the quiet one: a metric gets renamed
in a refactor, every rule that mentions it silently stops matching anything, and
Prometheus reports no error because an expression over a series that does not
exist is not an error — it is an empty result, which never fires. An alert that
can never fire looks exactly like an alert that has nothing to report.
"""

from pathlib import Path

import yaml
from prometheus_client import REGISTRY

from prope.prompt_conversion import observability  # noqa: F401

RULES = Path("deploy/prometheus/rules/prompt_conversion.rules.yml")

EXPECTED_ALERTS = {
    "PromptConversionAgentCircuitOpen",
    "PromptConversionInvalidOutputRate",
    "PromptConversionRepairRateHigh",
    "PromptConversionCoverageDropped",
    "PromptConversionDailyCostHigh",
}

#: Every metric an expression above names. Histograms are named by their base,
#: which is what `prometheus_client` registers; the `_bucket` suffix the
#: quantile expressions use is Prometheus's own exposition detail.
REQUIRED_METRICS = {
    "prope_prompt_conversion_agent_circuit_open",
    "prope_prompt_conversion_total",
    "prope_prompt_conversion_repair_total",
    "prope_prompt_conversion_coverage_ratio",
    "prope_prompt_conversion_cost_usd_total",
}


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    return document["groups"][0]["rules"]


def test_prompt_conversion_declares_exactly_the_locked_alerts() -> None:
    assert {rule["alert"] for rule in _rules()} == EXPECTED_ALERTS


def test_every_prompt_conversion_alert_names_a_real_metric() -> None:
    expressions = "\n".join(rule["expr"] for rule in _rules())
    metric_names = set(REGISTRY._names_to_collectors)  # noqa: SLF001

    assert REQUIRED_METRICS <= metric_names
    assert all(name in expressions for name in REQUIRED_METRICS)


def test_every_rule_carries_a_severity_and_something_to_do_about_it() -> None:
    """An alert without a description is an alert nobody can action at 3am."""
    for rule in _rules():
        assert rule["labels"]["severity"] == "ticket", rule["alert"]
        assert rule["annotations"]["summary"], rule["alert"]
        assert len(rule["annotations"]["description"]) > 80, rule["alert"]


def test_the_two_ai_specific_failure_modes_are_both_covered() -> None:
    """An LLM can get expensive without erroring, and worse without erroring.

    Ordinary rate/error/duration alerts see neither. If a future edit drops
    either of these two rules, the module loses the only warning it has for the
    failure that does not raise.
    """
    alerts = {rule["alert"] for rule in _rules()}

    assert "PromptConversionDailyCostHigh" in alerts, "no cost alarm"
    assert "PromptConversionCoverageDropped" in alerts, "no quality alarm"
