"""The declared alerts, checked against the registry rather than against prose.

Same template as `test_prompt_registry_alert_rules.py`. The read-back is over
metric FAMILIES, not samples: a labelled counter that nothing has incremented
emits no sample, so a sample-based check would call every rule broken on a fresh
process — which is exactly the state a "must stay 0" alert is written for.

**Eleven metrics where the lock declares ten**, and the eleventh exists because
of an alert rather than in spite of one. `EvalPricingStalled`'s condition is
stated as *"completed runs with priced_at NULL older than 15 min"* and no metric
in the declared list carries it, so the rule would have been true on paper and
unreadable by Prometheus — the same shape prompt-registry hit with
`RegistryUnapprovedPointer`, whose condition the lock states as a SQL query.
`prope_evaluation_unpriced_run_total` is what makes it a real series.
"""

import re
from pathlib import Path

import yaml
from prometheus_client import REGISTRY

import prope.evaluation.observability  # noqa: F401  (defines the families read below)

RULES_FILE = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "prometheus"
    / "rules"
    / "evaluation.rules.yml"
)

METRIC_NAME = re.compile(r"prope_evaluation_[a-z0-9_]+")

DECLARED_ALERTS = frozenset(
    {
        "EvalRunDurationHigh",
        "EvalCaseErrorRateHigh",
        "EvalRunsInterrupted",
        "EvalPricingStalled",
        "EvalQueueBacklog",
        "EvalModalityMismatch",
    }
)

#: Every metric this module defines, as the exposition renders it. A histogram
#: family named ``x`` is scraped as ``x_bucket``, ``x_sum`` and ``x_count``, and
#: a rule reading a p95 names ``x_bucket`` — so the read-back has to know the
#: suffixes rather than compare bare family names.
HISTOGRAM_SUFFIXES = ("_bucket", "_sum", "_count")

COUNTER_SUFFIXES = ("_total", "_created")


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    groups = document["groups"]
    assert [group["name"] for group in groups] == ["evaluation"]
    return [rule for group in groups for rule in group["rules"]]


def _declared_series() -> set[str]:
    series: set[str] = set()
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prope_evaluation_"):
            continue
        series.add(metric.name)
        for suffix in (*HISTOGRAM_SUFFIXES, *COUNTER_SUFFIXES):
            series.add(f"{metric.name}{suffix}")
    return series


def test_the_rules_file_parses_and_declares_exactly_the_lock_files_alerts() -> None:
    """Both directions fail. A rule that disappears and a rule that arrives
    undeclared are the same defect: a file nothing reads, drifting."""
    names = {rule["alert"] for rule in _rules()}

    assert names == DECLARED_ALERTS


def test_every_metric_a_rule_names_is_one_this_module_declares() -> None:
    """The read-back, and the only thing that stops this file rotting.

    Nothing in this repository wires a running Prometheus — the deployment stack
    owns no milestone — so a rule referencing a renamed metric would keep
    parsing and simply never fire. The second source here is the CLIENT REGISTRY:
    the metric objects `prope.evaluation.observability` defines at import.
    """
    declared = _declared_series()
    assert declared, "the registry walk found no prope_evaluation_* families at all"

    referenced = {
        name for rule in _rules() for name in METRIC_NAME.findall(str(rule["expr"]))
    }
    assert referenced, "no metric names were extracted from any expr — the regex is wrong"

    unknown = sorted(referenced - declared)
    assert unknown == [], f"rules name metrics this module does not declare: {unknown}"


def test_every_rule_carries_a_severity_and_an_annotation_pair() -> None:
    """An alert with no summary is a page with no first sentence."""
    for rule in _rules():
        assert rule["labels"]["severity"] in {"page", "ticket"}, rule["alert"]
        assert rule["annotations"]["summary"].strip(), rule["alert"]
        assert len(rule["annotations"]["description"].strip()) > 200, rule["alert"]


def test_the_must_stay_zero_alerts_fire_on_any_movement() -> None:
    """Two of the six have a threshold of zero, and it is not an oversight.

    `EvalModalityMismatch` means a suite is pointed at a target returning a shape
    it cannot assert on — every text assertion failing at once, which a reviewer
    reads as a catastrophic regression rather than as the configuration mistake
    it is. `EvalRunsInterrupted` means a run was reaped and re-running it costs
    the workspace real money (A-054). Neither has a healthy non-zero rate to
    tolerate, so neither gets a ``> 0.01``-shaped threshold that would let one
    through.
    """
    by_name = {rule["alert"]: rule for rule in _rules()}

    for name in ("EvalModalityMismatch", "EvalRunsInterrupted"):
        assert "> 0" in by_name[name]["expr"], name


def test_the_pricing_alert_reads_the_eleventh_metric_and_says_so() -> None:
    """The deviation is asserted, not merely written in a docstring.

    The lock declares ten metrics and this module ships eleven. The eleventh is
    not a nice-to-have: `EvalPricingStalled` is declared as an alert on completed
    runs whose `priced_at` is still NULL, Prometheus cannot run that query, and
    an alert with no series behind it is true on paper and silent in practice.
    """
    by_name = {rule["alert"]: rule for rule in _rules()}

    assert "prope_evaluation_unpriced_run_total" in by_name["EvalPricingStalled"]["expr"]
    assert "prope_evaluation_unpriced_run_total" in _declared_series()
