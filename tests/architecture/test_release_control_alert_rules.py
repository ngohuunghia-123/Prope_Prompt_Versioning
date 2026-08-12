"""The declared alerts, checked against the registry rather than against prose.

Same template as `test_evaluation_alert_rules.py`. The read-back is over metric
FAMILIES, not samples: a labelled counter that nothing has incremented emits no
sample, so a sample-based check would call every rule broken on a fresh process
— which is exactly the state a "must stay 0" alert is written for, and four of
this module's six are that shape.

**Fifteen metrics where the lock declares eleven**, and all four extras exist
because of an alert rather than in spite of one. Two of the declared alerts —
`ReleaseWithoutApproval` and `ReleaseUnapprovedRevision` — have their conditions
stated as SQL QUERIES, and Prometheus runs none, so without a series each rule
would be true on paper and silent in practice. That is the same shape
prompt-registry hit with `RegistryUnapprovedPointer` and evaluation with
`EvalPricingStalled`.
"""

import re
from pathlib import Path

import yaml
from prometheus_client import REGISTRY

import prope.release_control.observability  # noqa: F401  (defines the families read below)

RULES_FILE = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "prometheus"
    / "rules"
    / "release_control.rules.yml"
)

METRIC_NAME = re.compile(r"prope_release_[a-z0-9_]+")

DECLARED_ALERTS = frozenset(
    {
        "ReleaseWithoutApproval",
        "ReleaseUnapprovedRevision",
        "BreakGlassTaskOverdue",
        "AcknowledgementRateHigh",
        "ReleaseSummaryUnavailable",
        "ReleasePointerConflict",
    }
)

#: The eleven the lock declares, by the name the exposition renders.
DECLARED_METRICS = frozenset(
    {
        "prope_release_submit_total",
        "prope_release_decision_total",
        "prope_release_acknowledged_total",
        "prope_release_break_glass_total",
        "prope_release_total",
        "prope_release_review_turnaround_seconds",
        "prope_release_pointer_conflict_total",
        "prope_release_self_approval_total",
        "prope_release_summary_unavailable_total",
        "prope_release_review_task_open",
        "prope_release_review_task_overdue",
    }
)

#: ``metric -> the written reason it ships beside the eleven``. Blank entries
#: are refused below, for ``GLOBAL_TABLES``' reason: an exemption should be a
#: sentence somebody signed.
SANCTIONED_EXTRA_METRICS: dict[str, str] = {
    "prope_release_without_approval_rows": (
        "ReleaseWithoutApproval is declared with its condition stated as the Success-metric SQL "
        "— release rows with a NULL approval_id and break_glass false — and Prometheus runs no "
        "SQL. Without this gauge the most important alert in the module reads a series that does "
        "not exist, which is an alert that is true on paper and silent in practice."
    ),
    "prope_release_unapproved_revision_rows": (
        "ReleaseUnapprovedRevision has the same shape: 'a release whose target revision status is "
        "not Approved' is a query, not a counter. The worker sweep answers it per workspace under "
        "ordinary policy, through prompt-registry's seam rather than by joining across module "
        "tables."
    ),
    "prope_release_orphaned_pointer_rows": (
        "the reconciliation query's series. ADR-0008 was downgraded from a seam to a checked "
        "convention when one process and one role made prope_app able to write registry tables "
        "whatever code is executing; CI catches the SHAPE through the import walk and this gauge "
        "catches the INSTANCE — a released pointer with no release row behind it."
    ),
    "prope_release_sweep_pass_total": (
        "the sweep-heartbeat counter the lock records as OWED in its second-to-last risk row. A "
        "sweep that dies quietly leaves both gauges holding their last value in the client "
        "registry rather than dropping to zero, so a stale gauge and a healthy one are "
        "indistinguishable — a control whose failure mode is looking healthy."
    ),
}

HISTOGRAM_SUFFIXES = ("_bucket", "_sum", "_count")

COUNTER_SUFFIXES = ("_total", "_created")


def _rules() -> list[dict]:
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    groups = document["groups"]
    assert [group["name"] for group in groups] == ["release-control"]
    return [rule for group in groups for rule in group["rules"]]


def _families() -> list[tuple[str, str]]:
    """``(family name, type)`` for every metric this module defines.

    **The prefix test is ``prope_release`` and not ``prope_release_``**, and the
    missing underscore is load-bearing rather than sloppy. ``prometheus_client``
    strips the ``_total`` suffix from a counter's FAMILY name, so
    ``prope_release_total`` — the release counter, one of the eleven the lock
    declares — collects as the family ``prope_release`` and is invisible to a
    walk looking for the trailing underscore. A read-back that silently skipped a
    declared metric would be the same class of hole as a rule reading a series
    that does not exist.
    """
    return [
        (metric.name, metric.type)
        for metric in REGISTRY.collect()
        if metric.name.startswith("prope_release")
    ]


def _declared_series() -> set[str]:
    series: set[str] = set()
    for name, _ in _families():
        series.add(name)
        for suffix in (*HISTOGRAM_SUFFIXES, *COUNTER_SUFFIXES):
            series.add(f"{name}{suffix}")
    return series


def _canonical_names() -> set[str]:
    return {
        f"{name}_total" if kind == "counter" else name for name, kind in _families()
    }


def test_the_rules_file_parses_and_declares_exactly_the_lock_files_alerts() -> None:
    """Both directions fail. A rule that disappears and a rule that arrives
    undeclared are the same defect: a file nothing reads, drifting."""
    names = {rule["alert"] for rule in _rules()}

    assert names == DECLARED_ALERTS


def test_every_metric_a_rule_names_is_one_this_module_declares() -> None:
    """The read-back, and the only thing that stops this file rotting.

    Nothing in this repository wires a running Prometheus, so a rule referencing
    a renamed metric would keep parsing and simply never fire. The second source
    here is the CLIENT REGISTRY: the metric objects
    `prope.release_control.observability` defines at import.
    """
    declared = _declared_series()
    assert declared, "the registry walk found no prope_release_* families at all"

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


def test_the_two_product_claim_alerts_page_and_the_rest_do_not() -> None:
    """The severity split is the product's own, not a taste.

    `ReleaseWithoutApproval` and `ReleaseUnapprovedRevision` are the two ways
    the core value fails — a release nobody approved, and production serving
    text nobody approved. Everything else is a control that needs attention
    rather than a claim that has broken.
    """
    by_name = {rule["alert"]: rule for rule in _rules()}

    paging = {name for name, rule in by_name.items() if rule["labels"]["severity"] == "page"}
    assert paging == {"ReleaseWithoutApproval", "ReleaseUnapprovedRevision"}


def test_the_must_stay_zero_alerts_fire_on_any_movement() -> None:
    """Four of the six have a threshold of zero, and none of it is an oversight.

    A release with no approval and a released revision that is not Approved are
    the product's central claim failing. An overdue break-glass follow-up is the
    only control that keeps break-glass exceptional (A-009, A-073). A summary
    that could not be pulled means a reviewer is deciding without evidence
    (A-070). None of the four has a healthy non-zero rate to tolerate, so none
    gets a ``> 0.01``-shaped threshold that would let one through.
    """
    by_name = {rule["alert"]: rule for rule in _rules()}

    for name in (
        "ReleaseWithoutApproval",
        "ReleaseUnapprovedRevision",
        "BreakGlassTaskOverdue",
        "ReleaseSummaryUnavailable",
    ):
        assert "> 0" in by_name[name]["expr"], name


def test_self_approval_is_counted_and_no_alert_reads_it() -> None:
    """ADR-0010, as a property of the rules file.

    `prope_release_self_approval_total` is a FACT counter, not an error counter.
    Approval eligibility is a permission question and nothing else; a workspace
    that wants author-approver separation expresses it by not granting approve
    to authors. An alert here would be this module refusing what ADR-0010 says
    it must record — and the lock says in as many words that nothing alerts on
    it.
    """
    assert "prope_release_self_approval_total" in _declared_series()

    referenced = {
        name for rule in _rules() for name in METRIC_NAME.findall(str(rule["expr"]))
    }
    assert "prope_release_self_approval_total" not in referenced


def test_the_declared_eleven_all_exist_and_the_extras_carry_reasons() -> None:
    """The lock's own list, plus the deviation stated rather than absorbed."""
    declared = _declared_series()

    missing = sorted(name for name in DECLARED_METRICS if name not in declared)
    assert missing == [], f"metrics the lock declares and this module does not define: {missing}"

    extra = sorted(_canonical_names() - DECLARED_METRICS)
    assert extra == sorted(SANCTIONED_EXTRA_METRICS), (
        f"undeclared metrics with no written reason: {sorted(set(extra) - set(SANCTIONED_EXTRA_METRICS))}"
    )

    blank = [name for name, reason in SANCTIONED_EXTRA_METRICS.items() if not reason.strip()]
    assert blank == [], f"sanctioned extra metrics with no written reason: {blank}"


def test_the_two_sql_shaped_alerts_read_the_gauges_that_make_them_real() -> None:
    """The deviation is asserted, not merely written in a docstring."""
    by_name = {rule["alert"]: rule for rule in _rules()}

    assert "prope_release_without_approval_rows" in by_name["ReleaseWithoutApproval"]["expr"]
    assert (
        "prope_release_unapproved_revision_rows" in by_name["ReleaseUnapprovedRevision"]["expr"]
    )
