"""The declared alerts, checked against the registry rather than against prose.

Same template as `test_provider_access_alert_rules.py`. The read-back is over
metric families, not samples: a labelled counter that nothing has incremented
emits no sample, so a sample-based check would call every rule broken on a fresh
process — which is exactly the state a "must stay 0" alert is written for, and
two of the seven below are that.

**Seven ship where `gateway.lock.yml` declares six**, and the seventh is
`GatewayAdmissionRefusedSpike`. A-143 names its own metrics and says in as many
words that *"metrics, alerts and an AC for the cap are owed to step 6"*; step 6
ran, wrote T-013 against the cap, and did not add the alert to the
`observability_requirements.alerts` block. The same shape as call-ledger's
eighteenth metric — a mitigation declared in one section and absent from the
other is a mitigation nobody built — so it ships here and the omission is raised
as `OQ-142` rather than absorbed by editing the lock.
"""

import re
from pathlib import Path

import yaml
from prometheus_client import REGISTRY

import prope.gateway.observability  # noqa: F401  (defines the families read below)

RULES_FILE = (
    Path(__file__).resolve().parents[2] / "deploy" / "prometheus" / "rules" / "gateway.rules.yml"
)

METRIC_NAME = re.compile(r"prope_gateway_[a-z0-9_]+")

DECLARED_ALERTS = frozenset(
    {
        "GatewayAddedLatencyHigh",
        "GatewayMissingVersionId",
        "GatewayUsageMissing",
        "GatewayFallbackRateHigh",
        "GatewayNoReleaseSpike",
        "GatewayAuthFailureSpike",
        "GatewayAdmissionRefusedSpike",
    }
)

RENDERED_SUFFIXES = ("_bucket", "_sum", "_count", "_created")


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    return [rule for group in document["groups"] for rule in group["rules"]]


def _registered_names() -> set[str]:
    names: set[str] = set()
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prope_gateway_"):
            continue
        if metric.type == "counter":
            names.update({f"{metric.name}_total", f"{metric.name}_created"})
        elif metric.type == "histogram":
            names.add(metric.name)
            names.update(f"{metric.name}{suffix}" for suffix in RENDERED_SUFFIXES)
        else:
            names.add(metric.name)
    return names


def test_the_rules_file_parses_and_holds_exactly_the_declared_alerts() -> None:
    names = [rule["alert"] for rule in _rules()]

    assert set(names) == set(DECLARED_ALERTS)
    assert len(names) == len(DECLARED_ALERTS)


def test_the_group_is_named_for_the_module() -> None:
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    assert [group["name"] for group in document["groups"]] == ["gateway"]


def test_every_metric_named_by_a_rule_exists_in_the_registry() -> None:
    registered = _registered_names()

    named = {name for rule in _rules() for name in METRIC_NAME.findall(rule["expr"])}
    assert named, "no metric names were extracted at all"

    unknown = named - registered
    assert unknown == set(), f"rules name metrics that do not exist: {sorted(unknown)}"


def test_every_rule_carries_a_severity_and_a_reason() -> None:
    for rule in _rules():
        assert rule["labels"]["severity"] in {"page", "ticket"}, rule["alert"]
        assert rule["annotations"]["summary"].strip(), rule["alert"]
        assert len(rule["annotations"]["description"].strip()) > 200, rule["alert"]


def test_the_two_alerts_that_page_are_the_two_nothing_else_can_see() -> None:
    """One accountability claim failing, and one outage a 200 response hides.

    `GatewayMissingVersionId` is the success metric itself failing — a call the
    consumer received an answer for that Prope cannot trace to an approved
    revision. `GatewayFallbackRateHigh` pages because the fallback answer is a
    perfect disguise: 200, OpenAI-shaped, every SDK happy, and canned text
    reaching real users.

    The other five are tickets on stated grounds. The latency budget is A-031's
    placeholder and OQ-012 owes the real number; a missing usage object degrades
    a figure rather than an answer; a no-release spike is a change somebody made
    on purpose; auth failures are a consuming team's deploy far more often than
    an attack; and an admission refusal is the cap working as designed.
    """
    paging = {rule["alert"] for rule in _rules() if rule["labels"]["severity"] == "page"}

    assert paging == {"GatewayMissingVersionId", "GatewayFallbackRateHigh"}


def test_the_version_id_alert_fires_at_any_non_zero_value() -> None:
    """A must-stay-zero series, and there is no acceptable rate for this one."""
    rule = next(r for r in _rules() if r["alert"] == "GatewayMissingVersionId")

    assert "prope_gateway_record_missing_version_id_total" in rule["expr"]
    assert "> 0" in rule["expr"]
    assert rule["for"] == "0m"


def test_the_latency_alert_reads_a_bucket_edge() -> None:
    """`histogram_quantile` interpolates INSIDE the bucket holding the quantile,
    so a threshold that is not an edge can only be answered to that bucket's
    width — and a metric that cannot fail its own target is not a measurement."""
    rule = next(r for r in _rules() if r["alert"] == "GatewayAddedLatencyHigh")

    assert "prope_gateway_added_latency_seconds_bucket" in rule["expr"]
    assert 0.05 in prope.gateway.observability.ADDED_LATENCY_BUCKETS
    assert "0.05" in rule["expr"]


def test_the_fallback_alert_is_a_share_and_not_a_count() -> None:
    """Five per cent of WHAT is the question, and a bare count cannot answer it.

    A workspace sending ten calls an hour and one sending ten thousand would need
    two different constants, and the number that matters in both is the fraction
    of a product's users being served text no model produced.
    """
    rule = next(r for r in _rules() if r["alert"] == "GatewayFallbackRateHigh")

    assert 'outcome="fallback"' in rule["expr"]
    assert "/" in rule["expr"]
    assert "clamp_min" in rule["expr"], "a quiet period would otherwise divide by zero"


def test_the_no_release_alert_reads_the_label_that_separates_a_withdrawal_from_a_typo() -> None:
    """ADR-0009's blast-radius signal. Without the label a withdrawal is
    indistinguishable from consumers mistyping a model name."""
    rule = next(r for r in _rules() if r["alert"] == "GatewayNoReleaseSpike")

    assert 'reason="no_release"' in rule["expr"]
    assert "unknown_model" not in rule["expr"]
