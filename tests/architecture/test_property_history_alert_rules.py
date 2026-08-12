import re
from pathlib import Path

import yaml
from prometheus_client import REGISTRY

RULES_FILE = Path(__file__).resolve().parents[2] / "deploy" / "prometheus" / "rules" / "property_history.rules.yml"

METRIC_NAME = re.compile(r"prope_property_history_[a-z0-9_]+")

DECLARED_ALERTS = frozenset(
    {
        "PropertyHistoryAppendRejected",
        "PropertyHistoryScopeMissing",
        "PropertyHistoryWriteFailure",
    }
)

RENDERED_SUFFIXES = ("_bucket", "_sum", "_count", "_created")


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    return [rule for group in document["groups"] for rule in group["rules"]]


def _registered_names() -> set[str]:
    names: set[str] = set()
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prope_property_history_"):
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
    rules = _rules()
    names = [rule["alert"] for rule in rules]

    assert set(names) == set(DECLARED_ALERTS)
    assert len(names) == len(DECLARED_ALERTS)


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
        assert len(rule["annotations"]["description"].strip()) > 100, rule["alert"]


def test_the_two_alerts_that_page_are_append_rejected_and_write_failure() -> None:
    paging = {rule["alert"] for rule in _rules() if rule["labels"]["severity"] == "page"}
    assert paging == {"PropertyHistoryAppendRejected", "PropertyHistoryWriteFailure"}
