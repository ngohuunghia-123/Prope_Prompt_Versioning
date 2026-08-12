"""The six declared alerts, checked against the registry rather than against prose.

Same template as `test_property_history_alert_rules.py`. The read-back is over
metric **families**, not samples: a labelled counter that nothing has incremented
emits no sample, so a sample-based check would call every rule broken on a fresh
process — which is exactly the state a "must stay 0" alert is written for.
"""

import re
from pathlib import Path

import yaml
from prometheus_client import REGISTRY

import prope.access_control.observability  # noqa: F401  (defines the families read below)

RULES_FILE = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "prometheus"
    / "rules"
    / "access_control.rules.yml"
)

METRIC_NAME = re.compile(r"prope_access_control_[a-z0-9_]+")

DECLARED_ALERTS = frozenset(
    {
        "AccessControlUnknownAction",
        "AccessControlCheckError",
        "AccessControlAdminCountZero",
        "AccessControlLoginBruteForce",
        "AccessControlKeyScopeRefusals",
        "AccessControlCheckLatencyHigh",
    }
)

RENDERED_SUFFIXES = ("_bucket", "_sum", "_count", "_created")


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    return [rule for group in document["groups"] for rule in group["rules"]]


def _registered_names() -> set[str]:
    names: set[str] = set()
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prope_access_control_"):
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
    """`prometheus.yml` glob-loads `rules/*.yml`, so the group name is the only
    thing keeping two modules' alerts apart in the UI."""
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    assert [group["name"] for group in document["groups"]] == ["access_control"]


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


def test_the_three_alerts_that_page_are_the_three_that_break_the_product() -> None:
    """An unanswerable oracle, a vocabulary that has drifted, and a frozen workspace.

    The other three are tickets: the limiter is already absorbing the brute force,
    a scope refusal is already refusing, and a slow check is still a correct one.
    """
    paging = {rule["alert"] for rule in _rules() if rule["labels"]["severity"] == "page"}

    assert paging == {
        "AccessControlUnknownAction",
        "AccessControlCheckError",
        "AccessControlAdminCountZero",
    }


def test_the_brute_force_rule_watches_the_limiter_as_well_as_the_failures() -> None:
    """The half that is easy to forget, pinned so a "simplification" fails.

    A-144's limiter rejects before the hash, so its rejections never reach
    `login_total` — an alert on failed passwords alone goes quiet at exactly the
    moment an attack is being absorbed.
    """
    rule = next(r for r in _rules() if r["alert"] == "AccessControlLoginBruteForce")

    assert "prope_access_control_login_total" in rule["expr"]
    assert "prope_access_control_login_rate_limited_total" in rule["expr"]


def test_the_latency_rule_asserts_a_bucket_edge() -> None:
    """5 ms is an edge in `CHECK_DURATION_BUCKETS`, not a bucket interior.

    `histogram_quantile` interpolates inside the bucket holding the quantile, so a
    threshold that is not an edge can only ever be answered to that bucket's
    width — and a metric that cannot fail its own target is not a measurement.
    """
    from prope.access_control.observability import CHECK_DURATION_BUCKETS

    rule = next(r for r in _rules() if r["alert"] == "AccessControlCheckLatencyHigh")

    assert "> 0.005" in rule["expr"]
    assert 0.005 in CHECK_DURATION_BUCKETS
