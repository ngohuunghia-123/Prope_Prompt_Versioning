"""D-44: the alert rules file, and the only thing that stops it rotting.

**Nothing else will ever read `deploy/prometheus/rules/call_ledger.rules.yml`.**
The deployment stack owns no milestone (`.planning/research/PITFALLS.md` §4), so
no phase of this roadmap wires it into a running Prometheus. A rules file with no
consumer decays in one specific way: a metric is renamed or retired, the rule
keeps referencing the old name, the file keeps parsing, and the alert simply never
fires. That is what this file is against.

**Its analog is `tests/broker/test_declared_arguments.py`, which reads the
queue's arguments back from the broker rather than re-deriving them — and the
analogy has to be stated carefully, because there is no running Prometheus here to
read anything back from.** The other side of the comparison is the **registry**:
the eighteen metric objects `prope.observability` defines at import. So the claim
is *"every metric a rule names is a metric this application actually declares"*,
which is a real read-back against a real second source, and it is the whole of
what is claimed.

**What this cannot prove, stated at the top so no reader infers more.** Parsing
with PyYAML proves the file is well-formed YAML and lets the assertions below
extract every metric name an `expr` mentions. It does **not** prove the file is a
valid Prometheus *rules* file — the schema is Prometheus's, not YAML's — and it
does not prove a single PromQL expression parses. That is `promtool check rules`,
which needs a binary this repository does not have and PITFALLS §4 gives no home
to. A rule whose `expr` is grammatical nonsense over real metric names passes
everything here.
"""

import re
from pathlib import Path

import yaml
from prometheus_client import REGISTRY

from prope.observability import queue_depth, written_total

#: The file under assertion. Resolved from this module rather than from the
#: working directory, so the test does not depend on where pytest was invoked.
RULES_FILE = (
    Path(__file__).resolve().parents[2] / "deploy" / "prometheus" / "rules" / "call_ledger.rules.yml"
)

#: Any `prope_call_ledger_*` name appearing in a PromQL expression. Deliberately
#: greedy over `[a-z0-9_]`, which is exactly the character set every metric and
#: every rendered suffix in this project uses, and which stops at the `[` of a
#: range selector and at the `{` of a label matcher.
METRIC_NAME = re.compile(r"prope_call_ledger_[a-z0-9_]+")

#: **Written out rather than derived**, in `EXPECTED_ROUTES`' posture: a set
#: computed from the file would pass whatever the file happened to contain, which
#: is the failure this list exists to catch. Both directions fail — a rule that
#: disappears and a rule that arrives undeclared are the same defect here.
#:
#: **Eight, not seven, and the difference is a correction to the plan rather than
#: an addition to the spec.** `docs/modules/call-ledger.lock.yml`'s
#: `observability_requirements.alerts` block declares SEVEN — the first seven
#: below, `LedgerDuplicateCallIds` included — and `security_requirements` T-005
#: requires the eighth, `LedgerDlqNonEmpty`, which the alerts block omits
#: (`OQ-022` clause 3). Plan 03-04's own table listed six of the seven and dropped
#: `LedgerDuplicateCallIds`, while its objective names that alert as declared. The
#: lock file is the authority, so all eight ship.
DECLARED_ALERTS = frozenset(
    {
        "LedgerMetadataDropped",
        "LedgerPublishFailing",
        "LedgerWriteLagHigh",
        "LedgerBodyDropRateHigh",
        "LedgerPriceMissing",
        "LedgerRetentionOverdue",
        "LedgerDuplicateCallIds",
        "LedgerDlqNonEmpty",
    }
)

#: The suffixes `prometheus_client` appends when it renders a family into samples.
#: `_total` is deliberately absent: PromQL refers to a counter AS `x_total`, so
#: stripping it would make every counter rule fail for the wrong reason.
RENDERED_SUFFIXES = ("_bucket", "_sum", "_count", "_created")


def _rules() -> list[dict]:
    """Every rule in the file, flattened across groups."""
    document = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    return [rule for group in document["groups"] for rule in group["rules"]]


def _registered_names() -> set[str]:
    """Every metric name PromQL may legitimately use against this registry.

    **Derived from the collected FAMILIES, not from their samples, and that is
    load-bearing.** A labelled counter with no child — `unpriced_total`,
    `body_dropped_total`, `ceiling_check_total`, all of them — renders **zero
    samples** until something increments it with a label value. A sample-based
    set would therefore hold whatever the tests that ran earlier in this shared
    process happened to touch, which is the worst shape an assertion can have: it
    would pass in a full run and fail alone, or the reverse. The family exists
    from import (D-40), which is exactly the property D-40 was taken for.

    The expansion per family is `prometheus_client`'s own rendering rule: a
    counter named `x_total` collects as family `x` and renders `x_total` and
    `x_created`; a histogram renders `_bucket`, `_sum`, `_count` and `_created`;
    a gauge renders itself.
    """
    names: set[str] = set()
    for metric in REGISTRY.collect():
        if metric.type == "counter":
            names.update({f"{metric.name}_total", f"{metric.name}_created"})
        elif metric.type == "histogram":
            names.add(metric.name)
            names.update(f"{metric.name}{suffix}" for suffix in RENDERED_SUFFIXES)
        elif metric.type == "summary":
            names.add(metric.name)
            names.update({f"{metric.name}_sum", f"{metric.name}_count"})
        else:
            names.add(metric.name)
    return names


def test_the_rules_file_parses_and_holds_exactly_the_declared_alerts() -> None:
    """The other direction: a rules file that lost a rule still parses.

    Compared against the literal frozenset above, so a removed rule and an
    invented one both fail. The count is asserted separately from the set because
    a duplicated `alert:` name would collapse into the set silently and is a real
    mistake — two rules with one name is a rule somebody edited twice.
    """
    rules = _rules()
    names = [rule["alert"] for rule in rules]

    assert set(names) == set(DECLARED_ALERTS)
    assert len(names) == len(DECLARED_ALERTS), f"a rule name appears twice: {sorted(names)}"


def test_every_metric_named_by_a_rule_exists_in_the_registry() -> None:
    """D-44's whole purpose, and the failure it exists to catch, named.

    A rule referencing `prope_call_ledger_spill_bytes` — a metric ADR-0041 deleted
    — would parse fine, satisfy the test above, and **alert never**. Nothing else
    in this repository would notice, because nothing else reads this file.

    The comparison is one-directional on purpose: every name a rule uses must
    exist, but not every metric needs a rule. Eighteen metrics and eight alerts is
    the correct ratio, not a gap.
    """
    registered = _registered_names()

    named = {
        name for rule in _rules() for name in METRIC_NAME.findall(rule["expr"])
    }
    assert named, "no metric names were extracted at all; the regex or the file shape changed"

    unknown = named - registered
    assert unknown == set(), f"rules name metrics that do not exist: {sorted(unknown)}"


def test_the_name_expansion_matches_what_prometheus_client_actually_renders() -> None:
    """**Assert the helper, so the normalisation is not what swallows the test.**

    `_registered_names` is the only thing standing between a rule that names a
    real metric and a rule that names nothing. If its expansion were wrong in the
    permissive direction — say it also emitted the bare counter name — the test
    above would pass on a rule that PromQL could not evaluate; if it were wrong in
    the strict direction, every counter rule would fail for the wrong reason.

    So it is checked against one known counter, one known gauge, one known
    histogram, and one name that is deliberately not real.
    """
    registered = _registered_names()

    # A counter: PromQL says `x_total`, and `x_created` rides along.
    assert written_total._name == "prope_call_ledger_written"
    assert "prope_call_ledger_written_total" in registered
    assert "prope_call_ledger_written_created" in registered

    # A gauge: the family name IS the series name, no suffix at all.
    assert queue_depth._name == "prope_call_ledger_queue_depth"
    assert "prope_call_ledger_queue_depth" in registered
    assert "prope_call_ledger_queue_depth_total" not in registered

    # A histogram: the base name and its four rendered suffixes.
    for suffix in ("", "_bucket", "_sum", "_count", "_created"):
        assert f"prope_call_ledger_write_lag_seconds{suffix}" in registered

    # The negative control. ADR-0041 deleted the spill file and its three
    # metrics; if this name were ever in the set, the assertion above would be
    # incapable of failing.
    assert "prope_call_ledger_spill_bytes" not in registered


def test_a_rule_naming_a_metric_that_does_not_exist_is_reported() -> None:
    """The negative control for the file-level assertion, over a synthetic rule.

    The real file is left alone — a test that edited the artifact it audits is a
    test that can leave the artifact edited. Instead the same extraction and the
    same registry set are run against a document shaped exactly like the file, so
    what is proved is that the *mechanism* fails rather than that some other
    mechanism would.
    """
    rotten = yaml.safe_load(
        """
        groups:
          - name: call_ledger
            rules:
              - alert: LedgerSpillWriteFailed
                expr: prope_call_ledger_spill_bytes > 0
        """
    )

    named = {
        name
        for group in rotten["groups"]
        for rule in group["rules"]
        for name in METRIC_NAME.findall(rule["expr"])
    }

    assert named == {"prope_call_ledger_spill_bytes"}
    assert named - _registered_names() == {"prope_call_ledger_spill_bytes"}


def test_every_rule_carries_a_severity_and_a_reason() -> None:
    """The reasons ARE the artifact, since nothing will ever evaluate the `expr`.

    A rule with a threshold and no argument for it is a number somebody will
    change without knowing what it cost. The floor on the description length is
    crude on purpose — it refuses a one-line restatement of the summary, which is
    the shape an empty reason actually takes.
    """
    for rule in _rules():
        assert rule["labels"]["severity"] in {"page", "ticket"}, rule["alert"]
        assert rule["annotations"]["summary"].strip(), rule["alert"]
        description = rule["annotations"]["description"].strip()
        assert len(description) > 200, f"{rule['alert']}'s description is a restatement"


def test_the_two_alerts_that_page_are_the_two_that_mean_data_is_gone() -> None:
    """Exactly two rules wake somebody, and which two is a decision.

    `LedgerMetadataDropped` means a record exists nowhere. `LedgerRetentionOverdue`
    means a body has outlived a policy commitment. Everything else is a ticket,
    including the DLQ gauge — because a page that fires on one malformed envelope
    is a page people learn to close, and that would cost the only two that are
    genuinely worth having.
    """
    paging = {
        rule["alert"] for rule in _rules() if rule["labels"]["severity"] == "page"
    }

    assert paging == {"LedgerMetadataDropped", "LedgerRetentionOverdue"}


def test_publish_failing_reads_both_counters_and_says_why() -> None:
    """`OQ-022` clause 5, pinned so the `or` cannot be tidied away.

    The lock file's own detection line for the broker-outage scenario names
    `publish_failed_total` alone, and that counter cannot rise in that scenario:
    its `reason` set is closed at three values that all mean the broker ANSWERED
    and refused, while an ordinary outage produces a closed channel that
    `publish_record` absorbs without touching it. On that counter alone the rule
    is silent for the exact failure it was written for.

    So both counters are named, and the reason is in the description rather than
    in a plan nobody will read at 3 a.m. If somebody ever "simplifies" the
    expression back to the lock file's literal text, this fails.
    """
    rule = next(r for r in _rules() if r["alert"] == "LedgerPublishFailing")

    assert "prope_call_ledger_fallback_direct_write_total" in rule["expr"]
    assert "prope_call_ledger_publish_failed_total" in rule["expr"]
    assert " or " in rule["expr"]
    assert "OQ-022" in rule["annotations"]["description"]


def test_retention_overdue_names_both_of_the_caveats_it_ships_with() -> None:
    """The rule that pages against a series it does not perfectly match.

    Two mismatches ride on this one alert, and neither is fixable inside
    call-ledger: the threshold is per-workspace while the gauge is unlabelled and
    reduced (`OQ-022` clause 4), and the gauge covers only enumerated workspaces
    until Phase 7 replaces the enumerator (D-43). Both belong in the annotation a
    responder reads, not only in an open question they will not have open.
    """
    description = next(
        r for r in _rules() if r["alert"] == "LedgerRetentionOverdue"
    )["annotations"]["description"]

    assert "OQ-022" in description
    assert "unlabelled" in description
    assert "enumerated" in description
