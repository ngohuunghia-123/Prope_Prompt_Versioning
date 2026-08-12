"""The seven declared alerts, checked against the registry rather than against prose.

Same template as `test_access_control_alert_rules.py`. The read-back is over
metric families, not samples: a labelled counter that nothing has incremented
emits no sample, so a sample-based check would call every rule broken on a fresh
process — which is exactly the state a "must stay 0" alert is written for.
"""

import re
from pathlib import Path

import yaml
from prometheus_client import REGISTRY

import prope.provider_access.observability  # noqa: F401  (defines the families read below)

RULES_FILE = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "prometheus"
    / "rules"
    / "provider_access.rules.yml"
)

METRIC_NAME = re.compile(r"prope_provider_access_[a-z0-9_]+")

DECLARED_ALERTS = frozenset(
    {
        "ProviderKekUnavailable",
        "ProviderCredentialRejected",
        "ProviderModelUnavailable",
        "ProviderUsageMissing",
        "ProviderBatchStarved",
        "ProviderInteractiveShed",
        "ProviderVerificationFailing",
    }
)

RENDERED_SUFFIXES = ("_bucket", "_sum", "_count", "_created")


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    return [rule for group in document["groups"] for rule in group["rules"]]


def _registered_names() -> set[str]:
    names: set[str] = set()
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prope_provider_access_"):
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
    assert [group["name"] for group in document["groups"]] == ["provider_access"]


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


def test_the_three_alerts_that_page_are_the_three_a_fallback_would_otherwise_hide() -> None:
    """A missing key, a rejected credential, and Prope shedding its own live
    traffic. All three are invisible from outside — the gateway serves canned
    answers and nothing looks broken — which is what makes them pages rather
    than tickets.

    The other four are tickets: a retired model and a silent usage object are
    already covered by a fallback and a NULL, batch shedding is the designed
    direction of the trade (ADR-0016), and a failing probe refused at the
    dashboard has not reached production at all.
    """
    paging = {rule["alert"] for rule in _rules() if rule["labels"]["severity"] == "page"}

    assert paging == {
        "ProviderKekUnavailable",
        "ProviderCredentialRejected",
        "ProviderInteractiveShed",
    }


def test_the_kek_alert_reads_a_gauge_and_not_a_counter() -> None:
    """It is a state, not an event: a process that comes up with no key is in
    that condition continuously, and an `increase()` over it would fire once
    and then go quiet while the outage continued."""
    rule = next(r for r in _rules() if r["alert"] == "ProviderKekUnavailable")

    assert "increase(" not in rule["expr"]
    assert "prope_provider_access_kek_unavailable" in rule["expr"]


def test_the_two_shed_alerts_are_separated_by_priority() -> None:
    """One number for both would page on the case ADR-0016 designed for and
    stay quiet on the case it created."""
    batch = next(r for r in _rules() if r["alert"] == "ProviderBatchStarved")
    interactive = next(r for r in _rules() if r["alert"] == "ProviderInteractiveShed")

    assert 'priority="batch"' in batch["expr"]
    assert 'priority="interactive"' in interactive["expr"]
    assert batch["labels"]["severity"] == "ticket"
    assert interactive["labels"]["severity"] == "page"


def test_the_usage_alert_watches_the_series_that_must_stay_zero() -> None:
    """ADR-0013's closing obligation, discharged here rather than at the gateway."""
    rule = next(r for r in _rules() if r["alert"] == "ProviderUsageMissing")

    assert "prope_provider_access_usage_missing_total" in rule["expr"]
    assert "> 0" in rule["expr"]
