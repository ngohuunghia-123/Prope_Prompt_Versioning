"""This module's inbound seams. **It had none until 2026-08-20, and that changed.**

The original form of this file said readiness was a leaf — *"it reads five modules
and is read by none"* — and exported types and no behaviour. That was true when it
was written and it is not true now: ADR-0068 gives readiness a consumer, and this
docstring is corrected rather than left standing as a sentence that used to be
accurate.

**What `prompt-improvement` takes, and why it takes it rather than building it.**
`run_probe` dispatches the shipped guardrail sets against a revision and scores
them with the same deterministic assertions a hand-written suite uses. The
scheduled re-probe asks the identical question of a revision that is already
LIVE — *did this guardrail become bypassable?* — and a second dispatch loop over
there would be a second definition of *"refused 11 of 12"*, with the one that
drifted being the one nobody was reading. `latest_probe_run` is the other half:
`probe_leak_appeared` compares two completed runs, and without a read there is
nothing to compare.

**A second consumer arrived on 2026-08-25, and it takes a number.**
`agent_run.lifecycle` renders the readiness attention count beside the release
and evaluation state on one card. It held `SELECT jsonb_array_length(...) FROM
readiness.report` to get it — an undeclared edge that imports nothing, passes
every dependency test, and reads this module's table anyway. `frozen_finding_count`
is that read, named, and it is deliberately the count rather than the report: a
caller holding `rendered_findings` holds every finding's text in a module with no
surface to present one on.

**The one edge that could exist still must not.** `release-control` is forbidden
in BOTH directions (ADR-0067): nothing here is an input to a release decision and
nothing here may be consulted by one. A `readiness_summary_for(version_id)`
exported from this file would be entirely reasonable code and would turn the card
into a gate wearing a panel's clothes — *nothing blocks* defeated by composition
rather than by argument. The absence of that function is the control, and adding
a consumer does not soften it: `prompt-improvement` is forbidden the same edge,
in the same words, for the same reason.

Nor does `frozen_finding_count` soften it, and the reason is not its return type.
The objection is about a CONSUMER: a release decision that can read this module
can be composed into a gate. That consumer is impossible by test rather than by
an empty file — `tests/architecture/test_release_control_depends_on_four_modules.py`
carries an allow-list of nine packages and `prope.prompt_readiness` is not among
them. `agent_run` decides nothing; it draws a card.

**Nothing here checks a permission**, for `prompt_registry.seams`'s reason. The
caller has authorised at its own edge — a route through `may()`, the sweep through
the schedule its workspace opted into — and a second check on this side is a
second answer that can disagree with the first.
"""

from prope.prompt_readiness.domain import (
    Acts,
    Audience,
    Finding,
    ProbeOutcome,
    RuleId,
    Sensitivity,
    Severity,
    UntrustedInput,
    UsageProfile,
)
from prope.prompt_readiness.probe import ProbeRefused, ProbeTarget, run_probe
from prope.prompt_readiness.repository import count_frozen_findings, latest_probe_run

__all__ = [
    "Acts",
    "Audience",
    "Finding",
    "ProbeOutcome",
    "ProbeRefused",
    "ProbeTarget",
    "RuleId",
    "Sensitivity",
    "Severity",
    "UntrustedInput",
    "UsageProfile",
    "count_frozen_findings",
    "latest_probe_run",
    "run_probe",
]
