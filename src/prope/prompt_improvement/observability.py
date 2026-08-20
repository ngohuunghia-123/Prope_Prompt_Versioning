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
    "findings_total",
    "gate_rejected_total",
    "prompts_scanned_total",
    "proposals_total",
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
