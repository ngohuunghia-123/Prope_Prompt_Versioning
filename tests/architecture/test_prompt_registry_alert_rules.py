"""The declared alerts, checked against the registry rather than against prose.

Same template as `test_provider_access_alert_rules.py`. The read-back is over
metric FAMILIES, not samples: a labelled counter that nothing has incremented
emits no sample, so a sample-based check would call every rule broken on a fresh
process — which is exactly the state a "must stay 0" alert is written for.

**Four alerts where the lock declares three.** The fourth,
`RegistryResolveMissNoRelease`, reads the label ADR-0009 asked for and that
nothing else consumes: the two resolve misses are one 404 to the caller and two
lines in the metric, and that line is the only place a withdrawal is visible as a
withdrawal rather than as a typo. A label added for an alert nobody wrote is a
label that gets removed in a tidy-up.
"""

import re
from pathlib import Path

import yaml
from prometheus_client import REGISTRY

import prope.prompt_registry.observability  # noqa: F401  (defines the families read below)

RULES_FILE = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "prometheus"
    / "rules"
    / "prompt_registry.rules.yml"
)

METRIC_NAME = re.compile(r"prope_registry_[a-z0-9_]+")

DECLARED_ALERTS = frozenset(
    {
        "RegistryUnapprovedPointer",
        "RegistryUnfilteredQuery",
        "RegistryResolveLatencyHigh",
        "RegistryResolveMissNoRelease",
    }
)

#: The three the lock's ``observability_requirements.alerts`` block names. Held
#: separately from the four above so that dropping one is a visible edit rather
#: than a set that happens to shrink.
REQUIRED_BY_THE_LOCK = frozenset(
    {"RegistryResolveLatencyHigh", "RegistryUnfilteredQuery", "RegistryUnapprovedPointer"}
)

#: ``_total`` is here where `test_provider_access_alert_rules.py` does not need
#: it, and the difference is a real property of ``prometheus_client`` rather than
#: a copy that drifted. A Counter's FAMILY is named without the suffix, and the
#: ``_total`` name appears only on a SAMPLE — so an unlabelled counter is
#: readable either way on a fresh process, and a LABELLED one that nothing has
#: incremented emits no samples at all. ``resolve_miss_total`` is labelled by
#: ``reason``, and its whole job is to be zero.
RENDERED_SUFFIXES = ("_bucket", "_sum", "_count", "_created", "_total")


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    return [rule for group in document["groups"] for rule in group["rules"]]


def _registered_names() -> set[str]:
    names: set[str] = set()
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prope_registry_"):
            continue
        names.add(metric.name)
        for sample in metric.samples:
            names.add(sample.name)
            for suffix in RENDERED_SUFFIXES:
                if sample.name.endswith(suffix):
                    names.add(sample.name.removesuffix(suffix))
    return names


def test_the_rules_file_parses_and_declares_the_expected_alerts() -> None:
    assert {rule["alert"] for rule in _rules()} == set(DECLARED_ALERTS)


def test_every_alert_the_lock_requires_is_present() -> None:
    """The subset assertion, stated separately from the equality above.

    The equality would also pass if somebody renamed one of the lock's three and
    added a fourth of their own; this fails on exactly that.
    """
    assert REQUIRED_BY_THE_LOCK <= {rule["alert"] for rule in _rules()}


def test_every_metric_a_rule_names_exists_in_the_registry() -> None:
    """An alert on a series nothing defines is an alert that is true on paper.

    D-40's rule is what makes this checkable: all seven metrics are defined at
    import even where nothing has incremented them, so the family exists on a
    process that has served no traffic at all.
    """
    registered = _registered_names()

    missing: list[str] = []
    for rule in _rules():
        for name in METRIC_NAME.findall(rule["expr"]):
            bare = name
            for suffix in RENDERED_SUFFIXES:
                bare = bare.removesuffix(suffix)
            if bare not in registered:
                missing.append(f"{rule['alert']} -> {name}")

    assert missing == [], f"alerts naming metrics nothing defines: {missing}"


def test_the_two_must_stay_zero_alerts_page_rather_than_warn() -> None:
    """Both symptoms are invisible from outside, which is what earns the page.

    An unapproved released pointer means production is serving text nobody
    approved and everything still looks fine; an unfiltered query means a private
    prompt is showing to somebody with no grant and the endpoint still returns
    200. Neither has a user-visible symptom, so neither can be a ticket somebody
    reads on Monday.
    """
    severities = {rule["alert"]: rule["labels"]["severity"] for rule in _rules()}

    assert severities["RegistryUnapprovedPointer"] == "page"
    assert severities["RegistryUnfilteredQuery"] == "page"


def test_the_latency_alert_reads_the_locks_own_number() -> None:
    """``> 0.01`` — the lock's ``resolve p95 > 10 ms for 5 min``, and a BUCKET EDGE.

    ``histogram_quantile`` interpolates linearly inside the bucket holding the
    quantile, so a threshold that fell in a bucket's interior could only ever be
    answered to that bucket's width. 0.01 is an edge in ``RESOLVE_BUCKETS``,
    which is what lets this expression fail at all.
    """
    rule = next(item for item in _rules() if item["alert"] == "RegistryResolveLatencyHigh")

    assert "0.95" in rule["expr"]
    assert "> 0.01" in rule["expr"]
    assert rule["for"] == "5m"

    assert 0.01 in prope.prompt_registry.observability.RESOLVE_BUCKETS


def test_every_alert_carries_a_summary_and_a_description() -> None:
    """An alert whose page says only its own name is a page nobody can act on."""
    for rule in _rules():
        annotations = rule["annotations"]
        assert annotations["summary"].strip()
        assert len(annotations["description"].strip()) > 120, rule["alert"]
