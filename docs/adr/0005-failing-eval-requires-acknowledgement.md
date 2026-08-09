# ADR-0005 — A failing eval case requires a recorded acknowledgement, not a block

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: user (OQ-014)
**Module**: release-control, evaluation (written while locking evaluation)
**Related**: OQ-014, A-005, A-009, A-016, A-057, A-058, A-059, BR-08

## Context

Evaluation reports per-case pass/fail from deterministic assertions (A-005). What a reviewer may do with
a failing case was never stated. `00_context.md#constraints` forbids any surface claiming the eval
guarantees no quality degradation, and BR-08 restricts blocking to deterministic criteria — permission
to block, not an instruction to. Cost is already settled as warn-only (A-016), but correctness and cost
are different questions and did not have to get the same answer.

The decision is load-bearing because it defines what an approval *means*. It is also not evaluation's to
make: evaluation reports identical numbers under every answer.

## Decision

A failing eval case never blocks approval or release. The approve action on a candidate carrying one or
more `fail` outcomes requires a one-line reason, stored on the approval record and rendered in the
property history and on the release.

The requirement is computed by `evaluation` and published on the review summary as
`requires_acknowledgement`; `release-control` enforces it. The carve-outs stay where the outcomes are
produced: a case in `error` is not a failure (A-057), and an empty suite is not a pass (A-059).

**Acknowledgement and break-glass are different things and must stay separable.** Break-glass is
releasing *without an approval record* (A-009). Acknowledgement is approving *over failing evidence*.
They are separate fields, separate history events, and separate counters — a release may be neither,
either, or both, and collapsing them would let one hide the other in every metric that follows.

## Alternatives rejected

**Warn only — display the failures, leave approve enabled with no friction.** Rejected: it makes the
eval decorative. The survey finding is that 0/11 teams have any approval step today; an approval that
costs nothing to click reproduces the status quo with extra screens, and the product's entire claim is
that a release carries a decision someone made.

**Hard block until every case passes or the suite is edited.** Rejected: it converts a measurement into
a gate while the escape hatch already exists. Break-glass would become the standard route around a
blocked approval at 6pm — trading a documented approval-with-a-reason for a release with no approval at
all, which is strictly worse than the failure the gate was meant to prevent. It also puts pressure on a
worse action: editing the suite until the failure disappears. That is recorded (A-004), but it corrupts
the yardstick, and a corrupted yardstick is harder to notice than a failing case.

**Block on cost as well as on correctness.** Rejected: already settled by A-016 and `BRIEF.md` §5③ as
warn-only, and only 2/11 enterprise respondents have ever experienced an unexpected cost increase. Cost
does not earn a gate that correctness did not get.

## Consequences

- `approval.acknowledgement_reason` is conditional-mandatory. Release-control's lock owns the field, the
  control, and the validation.
- The `revision_approved` history event *(renamed from `approved` by A-120; corrected 2026-08-09, step 6 pass 1)* carries the reason when one was required, so a rubber-stamped approval is
  visible in the audit trail and not only in the database.
- A metric worth watching in the pilot: the share of approvals carrying an acknowledgement, and whether
  the reasons are substantive. A-058's `revisit_when` names one-word entries as the failure signal — if
  acknowledgement becomes a reflex, this decision was wrong and the block deserves reconsidering.
- Reversing to a hard block later changes what previously stored approvals mean, which is why A-058 is
  `reversibility: moderate` rather than cheap.
