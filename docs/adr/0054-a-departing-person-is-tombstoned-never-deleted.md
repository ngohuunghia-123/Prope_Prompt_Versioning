# ADR-0054 — A departing person is tombstoned, never deleted; `actor_id` survives as an opaque value

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: access-control (owns `user`, performs the tombstone) and property-history (records it, and
is the reason the question exists)
**Related**: A-020, A-046, A-108, A-110, A-121, A-122, A-124, A-146, A-151, ADR-0022, ADR-0025,
ADR-0027, ADR-0036, ADR-0044, ADR-0045, ADR-0053, OQ-017, OQ-006

## Context

OQ-017 was raised by the step-6 sweep, pass 2 — the one finding in that sweep the pack refused to
decide, because an erasure obligation is regulated. Two tables hold personal data and they have
opposite lifecycles: `access.user` carries `email` and `display_name` and is an ordinary deletable row,
while `history.history_event` carries `actor_id` on every one of its events forever and cannot be
deleted by the application at all — ADR-0025 withholds `UPDATE` and `DELETE` from `prope_app` at the
database privilege level, and ADR-0027's `prope_migrate` is a deployment credential that never enters
the running process.

The tension is real in both directions. Erasure obligations exist for staff personal data; audit trails
are the standard exemption, and an approval trail with people removed from it is not an approval trail.

**The user decided on 2026-08-09: tombstone the `user` row, keep `actor_id`.**

## Decision

**The audit trail is exempt. The account is not.**

1. **`access.user` is tombstoned, never deleted.** The row survives with its `id`; `email`,
   `display_name` and `password_hash` are cleared, `status` becomes `tombstoned`, and `tombstoned_at`
   and `tombstoned_by` are set. The parameters are [[A-151]].
2. **The row is kept rather than deleted so the identifier stays reserved.** A deleted row leaves an id
   that resolves to nothing *and* is free to be re-issued by a future import or a restore; a tombstoned
   row resolves to a stated absence and can never be confused with a new person. This is the difference
   between the two halves of OQ-017's option 1, and it is why the user's wording — *tombstone*, not
   *delete* — is the stronger half.
3. **`history_event` is not touched, at all.** No row is deleted, no `actor_id` is nulled, blanked,
   re-pointed, or anonymised after the fact. A-121 stands unqualified and ADR-0025's privilege is not
   spent. property-history's existing security requirement — *"an event's actor is recorded as it was at
   the time"* — was written before this question was asked and survives it unchanged.
4. **This is free because `actor_id` is a value and not a foreign key** ([[A-122]]). Nothing cascades,
   no query breaks, no join is invalidated. The same is true of every other stored actor id in the
   build: `created_by`, `added_by`, `granted_by`, `granted_to`. The schema already implemented this
   decision before the decision was taken.
5. **An unresolvable id is what erasure means here, and that is a claim about re-linking.** Inside a
   running Prope there is no path from a tombstoned `actor_id` back to a name: the `user` row no longer
   holds one, `history_event.details` may not carry one ([[A-124]]'s allow-list, which no action's
   registration includes), and no log line or metric label carries one ([[A-046]], ADR-0030). The paths
   that *do* survive are named in Consequences, because a residual risk stated is a residual risk that
   can be managed.
6. **The tombstone is itself recorded** — one `user_tombstoned` history event per workspace the person
   was ever a member of, so a reader of that workspace's trail can tell why an `actor_id` in it no
   longer resolves. `workspace_member` rows are retained with a `status`, so those workspaces are known
   without scanning the history.
7. **`user_tombstoned` carries no reason, deliberately** — the only registered action of consequence
   that does not. `requires_reason` is how the pack normally makes a rare action accountable, and here
   it would be the exact mechanism by which the erased name walks back into the append-only table a
   human sentence at a time. *"John Smith left the company"* is a free-text reason nobody would flag in
   review, written into the one table from which nothing can ever be removed. The accountability that
   `requires_reason` usually provides comes instead from `tombstoned_by`, which is an id.
8. **It is irreversible inside Prope.** Nothing un-tombstones a row, no endpoint restores a name, and
   the operation is permission-gated on a new action in the closed vocabulary (A-115), assigned to
   Admin in A-007's placeholder seed and subject to OQ-006's matrix like every other action.

## Consequences

- **The build does not change shape.** No table moves, no seam moves, no module boundary moves — as
  OQ-017 predicted for every one of its options. What is added is two columns, one route, one
  permission action, one history action, and the tests for them.
- **The action vocabulary grows from 30 to 31.** A-120 closes it at a count and AC-6 asserts the
  registry and the lock files are one list, so the count is updated everywhere it is stated rather than
  left to drift. ADR-0038 already established that adding an action is safe by construction: the
  registry cache is process-lifetime, and ADR-0031 migrates before it restarts.
- **The tombstone does not reach the backups, and this is the sharpest residual.** ADR-0036 keeps
  nightly `pg_dump` archives for 30 days, so a person's name survives in every dump taken before the
  tombstone. **Erasure is therefore complete only after the retention window has passed**, and a
  restore from a dump older than the tombstone brings the name back into the running system. That
  restore must re-apply the tombstone as a documented step in the recovery runbook — the same shape as
  ADR-0044's session-table exclusion and [[A-133]]'s rule that **a restore is not the running system**.
  A-151 carries the step.
- **A tombstoned person's prompts, approvals and releases are unaffected.** They keep their author and
  their approver as ids. This is the point: the record of who approved a production change remains
  complete, which is the exemption the decision rests on.
- **The pilot's data baseline now has an answer to give.** OQ-017 was part of what A-020 holds the line
  against; that part is now answered, and what remains under A-020 is OQ-013 and OQ-006.

## Alternatives rejected

**Delete the `user` row (OQ-017 option 1's other half).** Cheapest, and it frees the id — which is
exactly the problem. An id that can be re-issued makes a historical `actor_id` ambiguous rather than
merely unresolvable, and ambiguity in an audit trail is worse than absence.

**Erase from the history too (option 3).** Requires a documented `prope_migrate` procedure against the
one table the product's central claim rests on. It spends the append-only guarantee every time it runs,
and it needs a written trigger nobody has asked for. It remains available if a regulator ever compels
it, and it should remain deliberate, visible and outside the application when it does — which is the
shape ADR-0027 designed for a *"genuine correction"*.

**No erasure path; record the position (option 4).** Defensible for an internal pilot under A-020, and
strictly weaker than a mechanism that costs two columns and a route.
