"""The seven metrics `prompt-improvement.lock.yml` declares. All defined at import.

D-40's rule. ``REGISTRY.get_sample_value`` answers ``None`` — not ``0.0`` — for a
metric nothing has touched, so a counter that is *supposed* to sit at zero and is
defined lazily is indistinguishable from one that was never wired up. **That
matters more here than anywhere else in this product**, because
:data:`gate_rejected_total` reading zero is the module's own alarm condition, and
an alarm that cannot tell *nothing was rejected* from *nothing is instrumented*
is not an alarm.

**Two meters, and they are two metric NAMES rather than two labels on one.**
:data:`scheduled_probe_cost_usd_total` is the WORKSPACE's money, spent on its own
credential, appearing as ``ledger.call_record`` rows with ``source='probe'``.
:data:`triage_cost_usd_total` is PROPE's, spent on the app-owned model, never a
``call_record`` and never inside a cost delta. Separate names so no dashboard can
add them up by accident — a delta compares what two revisions cost to SERVE, and
a convenience feature's bill inside that number would make a revision look more
expensive because somebody enabled a schedule.

**No label carries a prompt id, a version id, an actor id or a workspace id.**
ADR-0030 bounds label cardinality on purpose, deck 6 slide 54 says why, and
Coinbase's $65M bill is the cited example. Every label below draws from a set
enumerated in ``domain.py``.
"""

from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "draft_attempts",
    "draft_circuit_open",
    "draft_cost_usd_total",
    "findings_total",
    "gate_rejected_total",
    "prompts_scanned_total",
    "proposals_open",
    "proposals_total",
    "rails_rejected_total",
    "runs_total",
    "scheduled_probe_cost_usd_total",
    "sweep_duration_seconds",
    "triage_circuit_open",
    "triage_cost_usd_total",
]

sweep_duration_seconds = Histogram(
    "prope_improvement_sweep_duration_seconds",
    "Wall time of one workspace's daily detector pass.",
)

#: **How the sweep proves it looked at something.** ADR-0051's failure mode is a
#: cross-tenant job that reads under no tenant, gets zero rows from a
#: deny-by-default policy, and reports healthy. A pass that scanned nothing and a
#: pass that found nothing produce the same empty inbox and different values here,
#: which is the whole difference between the two.
prompts_scanned_total = Counter(
    "prope_improvement_prompts_scanned_total",
    "Prompts a detector pass computed a window for.",
)

findings_total = Counter(
    "prope_improvement_findings_total",
    "Findings opened, by detector and severity. A recurrence bumps a row, not this.",
    ("detector_id", "severity"),
)

#: ``disposition`` is ``opened | accepted | dismissed | expired``. Opened is
#: counted here as well as on ``findings_total`` because a finding and a proposal
#: are different objects with different rates — most findings never get one.
proposals_total = Counter(
    "prope_improvement_proposals_total",
    "Proposals, by remedy family and what became of them.",
    ("remedy_family", "disposition"),
)

#: **The module's own smoke alarm.** If this is zero for a month the gate is not
#: working — either nothing is being proposed, or everything proposed is passing,
#: and the second is not credible. That deserves an alert about the MODULE rather
#: than about a prompt, and it is the reason this counter is defined at import
#: instead of on first rejection.
gate_rejected_total = Counter(
    "prope_improvement_gate_rejected_total",
    "Candidate edits discarded because they regressed on the prompt's own suite.",
    ("remedy_family",),
)

#: The WORKSPACE's meter. Scheduled probes spend its provider credit.
scheduled_probe_cost_usd_total = Counter(
    "prope_improvement_scheduled_probe_cost_usd_total",
    "US dollars the workspace spent on scheduled re-probes of released revisions.",
)

#: PROPE's meter. Never a `call_record`, never a cost delta. The rule
#: `prope_evaluation_drafter_cost_usd_total` already carries.
triage_cost_usd_total = Counter(
    "prope_improvement_triage_cost_usd_total",
    "US dollars Prope spent on its own model ranking anomalies and writing evidence lines.",
)

#: A gauge rather than a counter, for evaluation's drafter's reason: what an
#: operator needs on a dashboard is *is it open right now*, and a counter of
#: openings answers a different question badly.
triage_circuit_open = Gauge(
    "prope_improvement_triage_circuit_open",
    "1 while the triage circuit is open. The sweep still opens findings while it is.",
)

# --- ADR-0070: the authored-edit additions -----------------------------------
#
# Every label below draws from a closed enum in `domain.py` — the same
# cardinality rule the seven original metrics carry, and the red-team set's
# rails fixtures assert the codes cannot grow without a locale key noticing.

#: PROPE's meter for the drafter, beside triage's. A separate name so the two
#: model calls stay attributable per step (model-selection chapter, cost
#: attribution); never a `call_record`, never a cost delta.
draft_cost_usd_total = Counter(
    "prope_improvement_draft_cost_usd_total",
    "US dollars Prope spent on its own model drafting authored candidate bodies.",
)

#: The redraft loop's visibility. A distribution pushed against 3 is a drafter
#: that usually needs its feedback loop; one pushed against 1 with a rising
#: rails rejection rate is a model swap that stopped understanding the rails.
draft_attempts = Histogram(
    "prope_improvement_draft_attempts",
    "Draft attempts consumed per run, including refused ones.",
    buckets=(1, 2, 3),
)

#: Every rail firing, by its typed code. The quality funnel's first stage: a
#: step change here is either an injection attempt or a model regression, and
#: the alarm reads the code off the label.
rails_rejected_total = Counter(
    "prope_improvement_rails_rejected_total",
    "Authored candidates refused by a rail, by typed code.",
    ("rail_code",),
)

#: Every run's typed outcome, seven closed reasons. Five are not errors —
#: complete-what-succeeded is only visible if the reasons are counted apart.
runs_total = Counter(
    "prope_improvement_runs_total",
    "Eval-evidence improvement runs, by typed termination reason.",
    ("termination_reason",),
)

#: Queue age made visible: expiry is the safe default (OQ-158), and an open
#: proposal nobody decides on is only a problem worth seeing if somebody can
#: see it. A gauge, refreshed by the passes that open and decide proposals.
proposals_open = Gauge(
    "prope_improvement_proposals_open",
    "Open improvement proposals across workspaces this process has touched.",
)

#: 1 while the drafting circuit is open — triage's gauge, for the drafter's
#: own instance, so an operator can tell a ranking outage from a drafting one.
draft_circuit_open = Gauge(
    "prope_improvement_draft_circuit_open",
    "1 while the drafting circuit is open. Findings stay open while it is.",
)
