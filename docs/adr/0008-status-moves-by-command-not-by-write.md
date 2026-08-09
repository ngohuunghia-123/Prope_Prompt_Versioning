# ADR-0008 — Release-control writes no table it does not own; revision status moves by command

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-064, A-065)
**Module**: release-control, prompt-registry (written while locking release-control)
**Related**: A-002, A-041, A-064, A-065, ADR-0001, ADR-0002, BR-03

## Context

`prompt-registry.lock.yml` was locked first, and its `revision` table note reads: *"No UPDATE and no
DELETE reach this table (A-002, A-049, ADR-0002); `status` is the one exception and is written only by
release-control's approval flow."*

Read literally, that sentence puts a second writer on a table prompt-registry owns. It is the single
failure mode the module-lock procedure calls out by name, and it would have been carried into this
module's lock as a `writes_tables_it_does_not_own` entry — the point at which a module map is usually
discovered to be wrong.

The system already has the correct shape for exactly this problem one field away. The released pointer
lives on `prompt_property`, is written only by prompt-registry, and moves when release-control issues
`set_released_revision` (A-041, ADR-0001). Nothing about revision status is different in kind.

## Decision

Release-control writes no table outside its own three (`approval`, `release`, `review_task`).

Revision status moves through a command on prompt-registry's surface:
`set_revision_status(version_id, status, decision_id)`. Release-control decides; prompt-registry
performs the write, validates the transition, and owns the invariant. `decision_id` names the approval
or release row that authorised it, so a status with no decision behind it is a detectable defect rather
than an untraceable one.

Two supporting rulings, recorded as assumptions:

- **The stored statuses are Draft, In review, and Approved** (A-065). *In use* is derived — a revision
  is In use exactly when `prompt_property.released_version_id` equals its version ID. Storing it would
  create a second answer to "what is released", and a second answer can disagree with the first. That
  is the same reasoning ADR-0001 used to put the pointer in one place; it would be strange to undo it
  one table over. *Retired* is a prompt-property status and belongs to prompt-registry (A-049).
- **Changes requested returns the revision to Draft** (A-066), because the listed status vocabulary is
  fixed by a non-negotiable constraint and contains no rejected state. The decision itself is not lost:
  it is an `approval` row with `decision = changes_requested`, and the author's fix is a new immutable
  revision (A-002), not an edit to the rejected one.

## Alternatives rejected

**Let release-control write `revision.status` directly**, as prompt-registry's lock implied. Rejected:
two writers on one table means the transition rules live in whichever module remembered them, and the
`Approved` value is load-bearing for the product's most important guarantee — the registry's database
constraint refuses a released pointer whose target is not Approved (BR-03). A module that can write the
value the constraint checks can defeat the constraint by writing it first. Keeping the write inside the
module that owns the constraint is what makes the guarantee mean anything.

**Move `status` out of `revision` into a release-control-owned table** — a status projection this module
owns outright. Rejected: the gateway's hot path and the registry's own listing both need a revision's
status, and both would then have to cross a module boundary to render a badge. It solves the ownership
problem by making the read path worse for every consumer, to serve one writer.

**Derive status entirely from the approval and release logs** — no stored column at all. Genuinely
attractive, and rejected on the strength of the constraint that depends on it: BR-03's enforcement is a
database constraint on the pointer write, and a database constraint cannot call a derivation. Deriving
the status would demote the strongest guarantee in the system to application code. The append-only
decision log remains the source of truth for *why*; the column is the materialised answer the constraint
can check.

## Consequences

- `prompt-registry.lock.yml` is amended: the `revision` table note now says status is written by
  prompt-registry on a command, and `set_revision_status` joins the two commands already on its API.
- Release-control's `writes_tables_it_does_not_own` is `none`, and the same is now true of every module
  locked so far.
- A status transition and its decision row commit in one transaction. A rollback leaves neither — no
  Approved revision without an approval, and no approval against a revision that is still In review.
- Invalid transitions are refused by the owner of the table, so a bug in release-control produces an
  error rather than a corrupt lifecycle.
- The derived *In use* rule means the review and registry screens must join to `released_version_id` to
  render that badge. Cheaper than the alternative: two stored answers that drift.

---

## Amendment, 2026-08-09 (step 4, release-control's stack pass) — this was a seam; it is now a checked convention

**The rule is unchanged and every consequence above still holds.** Release-control still writes no table
outside its own three, status still moves through `set_revision_status`, the transition rules still live
in the module that owns the table, and a status change and its decision row still commit together.

What changed is **what makes it true**. This ADR was written against a service boundary, where "issue a
command" meant a call across a seam that a module physically could not go around. Step 4 removed that
seam twice over:

- **ADR-0026** puts all eight modules in **one process**. `set_revision_status` is a Python function
  call, and the caller can reach `registry`'s models by importing them.
- **ADR-0027** gives the runtime **one role**. `prope_app` holds `UPDATE` on `registry.revision`
  regardless of which module's code is executing, so the database cannot tell release-control's write
  from prompt-registry's.

This ADR named its own stakes, and they are exactly what the amendment has to answer:

> "A module that can write the value the constraint checks can defeat the constraint by writing it first.
> Keeping the write inside the module that owns the constraint is what makes the guarantee mean
> anything."

BR-03 is the guarantee — *"Only revisions in status `Approved` may be released or resolved by the
gateway"*, non-negotiable in `00_context.md#constraints`, enforced as a database constraint on the
pointer write. Under one process and one role, release-control could set `status = 'Approved'` and then
move the pointer legitimately past a constraint that saw nothing wrong. **This is the ninth
application-maintained invariant in the build and the first that could not be pushed into the database.**
The other eight were: ADR-0025's privilege, BR-03's constraint, ADR-0035 and ADR-0045's policy, ADR-0048's
trigger, ADR-0049's claim transaction, ADR-0050's application object, ADR-0040's per-workspace batching,
and ADR-0042's named functions.

### What enforces it now

**A layering contract in CI** (`import-linter`, in the job ADR-0031 already runs): each module package may
import only its own table models, plus the declared interface modules of the modules it depends on.
`prope.release_control` importing `prope.registry.models` fails the build. This is the same move as
ADR-0045's coverage test, ADR-0025's grant test, A-123's empty route table and A-124's payload allow-list
— four step-3 promises ADR-0031 already turns into build failures rather than intentions.

**Its honest limit**: it constrains imports, so it catches the ORM path — which is how this drift actually
happens, because writing another module's table by accident means constructing that module's mapped class.
It does not catch a hand-written `session.execute(text("UPDATE registry.revision …"))`. A-128 helps by
keeping raw SQL to a short named list (the gateway resolve, `visible_subject_filter`, ADR-0049's claim,
and ADR-0051's sweep), but the gap is real and is not closed by the contract.

**The runtime detector for that gap is release-control's reconciliation query** — prompt properties whose
`released_version_id` has no matching release row, run at startup and hourly by ADR-0051's sweep. That
query was originally specified as a tripwire for a distributed-transaction failure that ADR-0026 and
ADR-0027 have since made impossible; it survives with a different job. **CI catches the shape; the sweep
catches the instance.**

### Why per-module database roles were not the answer

ADR-0027 listed *"role per module"* as *"right idea, 8 pools, adoptable later without moving data"*, which
made it the obvious candidate here. It is blocked by a decision older than either: **a transaction lives
on one connection under one role**, and ADR-0023 puts property-history's `append()` on the *caller's*
connection inside the *caller's* open transaction, while this ADR puts the status write and the decision
row in that same transaction. A nested `release-control → prompt-registry → property-history` chain would
need `SET ROLE` save-and-restore discipline in application code, with RLS policies re-evaluating
mid-transaction — an application-maintained invariant with no failure signal, which is precisely the thing
being solved. The idea is not dead; it becomes available if Prope is ever split into processes, which is
also when ADR-0023's own outbox note comes due.
