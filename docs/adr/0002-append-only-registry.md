# ADR-0002 — Prompt properties and revisions are append-only

**Status**: Accepted
**Date**: 2026-08-08
**Module**: prompt-registry (written while locking it)
**Related**: A-002, A-014, A-047, A-048, A-049, A-052, BR-06, NFR-02

## Context

The product's stated problem is lost provenance: 11/11 surveyed cannot tell which revision is current,
and 5/11 cannot identify which prompt caused a failure (`00_context.md#problem`). Provenance is not a
feature layered on top of a mutable store — it is a property of the store or it is absent. Meanwhile
`00_context.md#success` measures restore latency and review turnaround from history events, and both
queries assume the past is still there to be queried.

## Decision

`revision` rows are never updated and never deleted. An edit creates the next revision; revision numbers
are allocated inside the creating transaction and arbitrated by `unique(prompt_id, revision_number)`, so
numbers are gapless and a failed create allocates nothing (A-048). The single mutable field is
`status`, written only by release-control's approval flow.

A prompt property is never hard-deleted. `Retired` is the terminal status, and retiring is refused while
a release is active (A-052) — a hard dependency of other products' request paths cannot be removed by a
single owner's click.

The diff is computed on demand from two revisions and never stored (A-047).

## Alternatives rejected

**Mutable current-body with a separate history table.** Rejected: it makes the history a copy, and a
copy can drift from the thing it describes. Every provenance question then has two answers.

**Soft-delete flag on revisions.** Rejected. A revision that a release once pointed at is evidence of
what production ran; hiding it makes the audit trail lie by omission. If a body must genuinely be
destroyed — a leaked secret pasted into a prompt — that is a deliberate, recorded redaction, not a
flag, and it is scoped with OQ-013's deletion policy rather than invented here.

**Store the computed diff.** Rejected: it is derived data with no independent truth, it doubles on every
edit, and the moment the diff algorithm improves every stored diff is wrong. Bodies cap at 32 KiB
(A-050), so recomputation is cheap.

**Allow retiring a prompt with an active release, and let the gateway start erroring.** Rejected.
`00_context.md` records Prope as an accepted hard dependency; under that constraint a retire is an
outage in someone else's product. Refusing it forces the release to be withdrawn first, which is a
recorded decision with an owner.

## Consequences

- Storage grows monotonically with edits. At the pilot's scale (1,000 properties × 20 revisions × 32
  KiB ceiling) this is bounded and not worth optimising.
- "Withdraw a release" becomes a required action on `release-control`'s surface, discovered here and to
  be confirmed when that module is locked.
- Reversing this is a migration and a re-litigation of the audit story, not an edit.

> **Extended 2026-08-09 by ADR-0048, which found this decision constraining a place nobody expected:
> the search index.**
>
> The obvious way to make "search the latest revision's body" cheap is to mark the newest row with an
> `is_latest` flag and put a partial index on it. That requires flipping the *previous* row's flag —
> an `UPDATE` on `revision`, which this ADR forbids and which `status` is the sole exception to. So the
> corpus had to be bounded structurally instead, and ADR-0048 chose a denormalised `search_text` column
> on `prompt_property` (which was always mutable) rather than any marker on this table.
>
> **Append-only is untouched by that decision.** The trigger maintaining `search_text` fires on
> `INSERT INTO registry.revision` and writes the **parent**, never this table. `revision` still takes no
> `UPDATE` and no `DELETE` outside the `status` carve-out, and `prompt_property.updated_at` now moving
> on a revision insert is a change to the parent's row, which was already expected to change.
>
> Worth recording as a general observation: this is the second time the append-only choice has decided
> something outside the audit story it was written for. It is doing more work than its title suggests.
