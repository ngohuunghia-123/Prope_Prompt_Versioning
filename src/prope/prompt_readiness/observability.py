"""The seven metrics `prompt-readiness.lock.yml` declares. All defined at import.

D-40's rule. ``REGISTRY.get_sample_value`` answers ``None`` — not ``0.0`` — for a
metric nothing has touched, so a counter that is *supposed* to sit at zero and is
defined lazily is indistinguishable from one that was never wired up. Two of the
counters below are exactly that kind: ``findings_suppressed_total`` is the number
that proves the Usage Profile earns its migration, and it is only meaningful if a
reading of zero means zero rather than *not instrumented*.

**No label anywhere carries a prompt id, a version id, an actor id or a
workspace id.** ADR-0030 bounds label cardinality on purpose, deck 6 slide 54
says why, and Coinbase's $65M bill is the cited example. Every label below draws
from a set enumerated in ``domain.py``: ``rule_id`` from :class:`RuleId`,
``severity`` from :class:`Severity`, ``result`` from :class:`ProbeOutcome`. The
one hand-written label, ``trigger``, has three values and they are in this file.

**``dismissals_total{rule_id}`` is the honest metric.** A rule dismissed 80% of
the time is a rule to RETIRE, not to tune — deck 6 slide 64's alert-fatigue
prescription applied to findings instead of pages. It is a counter here and a
question in OQ-157, which owns the threshold and the decider; what is settled is
that the number exists before anybody needs to argue about it.

**``drafter_cost_usd_total`` is PROPE's meter and never a cost delta.** Lane B
calls the app-owned ``APP_OPENAI_*`` model, exactly as conversion and search do.
It is not a ``ledger.call_record``, and putting it inside a delta would make a
revision look more expensive because somebody pressed a button.
"""

from prometheus_client import Counter, Gauge

__all__ = [
    "TRIGGERS",
    "dismissals_total",
    "drafter_circuit_open",
    "drafter_cost_usd_total",
    "findings_suppressed_total",
    "findings_total",
    "lane_b_cache_hits_total",
    "probe_cases_total",
    "probe_runs_total",
]

#: The three trigger points from the lock's flow. Written out so the label's
#: value set is enumerable from source rather than from whatever the call sites
#: happen to pass.
TRIGGERS = ("import", "edit", "submit")

findings_total = Counter(
    "prope_readiness_findings_total",
    "Findings that survived the profile filter and reached a card.",
    ("rule_id", "severity", "trigger"),
)

#: **The proof metric.** Counted where the drop happens, which is AFTER
#: generation — a filter that skipped the rule instead would leave this at zero
#: and look identical to a profile nobody had declared. AC-1 asserts over this
#: counter and not over the returned list, for that reason.
findings_suppressed_total = Counter(
    "prope_readiness_findings_suppressed_total",
    "Findings generated and then dropped because the declared profile does not admit them.",
    ("rule_id", "axis"),
)

dismissals_total = Counter(
    "prope_readiness_dismissals_total",
    "Findings a person dismissed, by rule. The retirement signal — see OQ-157.",
    ("rule_id",),
)

probe_runs_total = Counter(
    "prope_readiness_probe_runs_total",
    "Probe runs, by how they ended.",
    ("outcome",),
)

#: ``result`` is ``refused | leaked | error`` and the third is not folded into
#: either of the first two. A provider timeout is not a guardrail win, and a
#: dashboard that showed it as one would report an outage as a perfect score.
probe_cases_total = Counter(
    "prope_readiness_probe_cases_total",
    "Individual probe cases dispatched, by outcome.",
    ("result",),
)

drafter_cost_usd_total = Counter(
    "prope_readiness_drafter_cost_usd_total",
    "US dollars spent on Prope's own model drafting cases and non-runnable findings.",
)

lane_b_cache_hits_total = Counter(
    "prope_readiness_lane_b_cache_hits_total",
    "Lane B reads served from the fingerprint cache without calling a model.",
)

#: A gauge rather than a counter, for evaluation's drafter's reason: what an
#: operator needs on a dashboard is *is it open right now*, and a counter of
#: openings answers a different question badly.
drafter_circuit_open = Gauge(
    "prope_readiness_drafter_circuit_open",
    "1 while the Lane B drafting circuit is open.",
)
