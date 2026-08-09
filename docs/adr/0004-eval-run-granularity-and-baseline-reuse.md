# ADR-0004 — An eval run measures one revision; a comparison pairs two runs and the baseline is reused

**Status**: Accepted
**Date**: 2026-08-08
**Module**: evaluation (written while locking it)
**Related**: A-004, A-006, A-030, A-047, A-053, A-057, A-060, BR-07

## Context

`00_context.md#scope` defines the cost delta as candidate versus current released revision, and A-006
fixes the unit as one full eval-suite run on each. That leaves an unstated question with real money and
real wall-clock behind it: is "a run" the measurement of one revision, or the measurement of the pair?

The success metric says the suite completes in ≤ 120 s at p95 for 10–20 cases. Under a paired model,
every review re-measures the released revision as well — 40 upstream calls instead of 20, on a
bring-your-own key (OQ-004), for a revision whose text has not changed since the last time it was
measured with the same suite version.

## Decision

An `eval_run` measures **one** revision against **one** suite version. `role` distinguishes `candidate`
from `baseline`. A comparison is not a stored object: it is computed on demand from two run rows,
following the same reasoning that keeps the registry's diff underived (A-047).

The pairing rule is explicit and pinned by identity, not by time: the baseline is the most recent
`completed` run whose `version_id` equals the prompt's current `released_version_id` **and** whose
`suite_id` equals the candidate run's `suite_id`. If such a run exists it is reused; otherwise a
baseline run is dispatched before the comparison renders.

Two consequences are load-bearing and are enforced rather than documented:

- Any change to the released pointer, or any new suite version, invalidates the pairing by construction.
  There is no staleness window to tune and no cache to expire.
- The baseline run's timestamp is displayed next to every delta. A reused baseline is visible on the
  screen, never implied by its absence.

Where there is no released revision — the first release of a new prompt — there is no baseline, the
candidate run is reported absolutely, and the cost delta is omitted rather than shown as +100% (A-060).

## Alternatives rejected

**One run measures both revisions.** Rejected: it doubles the token spend and the wall-clock on every
review of an unchanged baseline, against a 120 s p95 target and someone else's API key. It also couples
two measurements into one row, so a baseline dispatch failure destroys a candidate result that was
already valid.

**Reuse the baseline on a time window (e.g. 24 hours).** Rejected: a time window is a guess about how
often the released pointer changes, and it is wrong in exactly the case that matters — a restore
(A-010) changes what production runs in under 5 minutes, and a 24-hour window would compare a candidate
against a revision that stopped being released two hours ago. Pinning on `(released_version_id,
suite_id)` needs no threshold and cannot drift.

**Store the computed comparison as a row.** Rejected for the reason ADR-0002 rejects storing the diff:
it is derived data with no independent truth, and the moment the pairing rule or the delta arithmetic
changes, every stored comparison is silently wrong. Two run rows and a query are cheap.

**Always re-run the baseline, and treat reuse as a correctness risk.** Rejected, but it is the strongest
alternative and it deserves the honest statement: at a non-zero temperature, re-running the baseline
would produce a different number, so a reused baseline is not merely cheaper — it is *more* comparable,
because it holds one side of the comparison genuinely fixed. What re-running would buy is protection
against provider-side model drift behind a stable model name, which this build cannot detect anyway
(scheduled drift monitoring is explicitly out of scope). The timestamp on screen is the mitigation.

## Consequences

- Baseline runs accumulate one row per (released revision × suite version), which is bounded and small.
- A reviewer can be shown a baseline measured weeks ago. This is intended, and it is disclosed.
- Re-measuring the released revision on demand is a later feature — one button, one new run row, no
  schema change — if drift becomes a real complaint.
- `prope_evaluation_baseline_reused_total{reused|recomputed}` makes the reuse rate observable, so the
  trade-off can be re-argued with a number instead of an intuition.
