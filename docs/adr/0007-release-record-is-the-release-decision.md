# ADR-0007 — The release record is the release decision; there is no separate release-approval object

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-072, A-075)
**Module**: release-control (written while locking release-control)
**Related**: OQ-002, A-023, A-041, A-072, A-075, ADR-0001, BR-03, BR-04

## Context

`00_context.md#constraints` carries a non-negotiable row from the user's own answer to OQ-002:
*"Approval attaches to both the revision and the release: a revision is approved once, and each release
is a second recorded decision."* OQ-002's resolution note went one step further and wrote down two
object names — `revision_approval` and `release_approval` — as the consequence of that answer.

`module_map.md` lists this context's owned data as `approval`, `release`, `review_task`. So the
schema question was left open in exactly the place it matters: is the release decision a row of its
own that a release then consumes, or is the release row itself the decision?

The constraint is about **recording**, not about a workflow. It says each release must be a decision
somebody made and that is written down. It does not say the decision and the act are two steps.

## Decision

There are two decision objects, and they are `approval` and `release`.

- `approval` holds the decision about a **revision**: approve or request changes, by any actor holding
  the approve permission (A-008, ADR-0010), with a comment, a conditional-mandatory acknowledgement
  reason (ADR-0005), and the evidence digest as it stood at decision time (A-074).
- `release` holds the decision about a **release**: this actor, holding the release permission, put
  this Approved revision into production at this time, in place of that one. The row is the decision.
  There is no state in which a release has been approved but not performed.

Both are append-only. A changed mind is a new row.

The two recorded decisions the constraint requires are therefore the `approval` row and the `release`
row — different tables, different permissions, different timestamps, and separately queryable. The
headline success metric falls out as one join: `release` rows with a NULL `approval_id` and
`break_glass = false` must be zero.

## Alternatives rejected

**A separate `release_approval` row that a subsequent release consumes.** This is the literal reading
of OQ-002's note, and it is rejected because it creates a state the MVP cannot act on: "this release
is approved but has not happened". With one environment and a single released pointer (A-023), and with
multi-level approval explicitly out of scope, nothing ever sits in that state on purpose — it exists
only as a way for a workflow to be abandoned halfway. It doubles the audit objects while telling the
same story, and it makes the Success-metric query a three-way join over a table whose rows are almost
always immediately consumed. It becomes the right shape the moment staged environments or a second
approver arrive, and at that point it is a migration that adds a table, not one that splits a table.

**One polymorphic `approval` table with a `kind` discriminator (revision | release).** Rejected because
the two decisions do not share a shape. A revision approval carries a reviewer, an acknowledgement
reason, and an evidence digest; a release carries a previous version ID, a break-glass flag, and a kind
of its own (release / restore / withdraw). A shared table would be half-null in both directions, and
every query would filter on `kind` before it could mean anything — which is a table pretending to be
two tables.

**Make the release a bare pointer write with no record at all**, relying on the property-history event
for the trail. Rejected outright: it violates the non-negotiable constraint, and it makes the product's
central claim unqueryable. History is an append-only narrative; the release log is a set of rows the
Success metric counts. Deriving one from the other means the audit answer depends on parsing an event
stream, and BR-04 is not something to reconstruct.

## Consequences

- The release permission is checked at `POST /releases`, and that check *is* the second decision. There
  is no earlier gate to hold and no later one to forget.
- **Who may release is not required to differ from who approved** (A-075). The constraint separates
  permissions, not people. Requiring distinct humans would deadlock a small team and push everything
  through break-glass, which is strictly worse. Both acts stay separately recorded, so a workspace that
  wants stricter separation can see whether it is happening.
  *Amended 2026-08-08*: this bullet originally carved out one person-level rule — the author may not
  approve their own revision. The user overturned it; there is now no person-level rule at all, and
  eligibility is answered by access-control alone (A-008, ADR-0010). The decision this ADR records is
  unaffected.
- `restore` and `withdraw` are kinds of release rather than separate entities (A-010, A-069), so one
  log answers "what has been in production, and when" without a union.
- The pointer write and the release row commit together, under a compare-and-set on the previous
  version ID (A-072). That is a local transaction only while A-012 holds — one process, one database.
  A reconciliation query is specified in the lock file as the tripwire for when step 4 changes that.
- If OQ-002's remaining half is answered "a restore does need a fresh approval", this shape absorbs it:
  a restore then requires an `approval_id`, exactly as an ordinary release does. No table changes.
