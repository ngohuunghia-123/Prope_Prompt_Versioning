# ADR-0025 — Append-only is a database privilege, not a convention

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent
**Module**: property-history (written while locking property-history)
**Related**: A-012, A-014, A-044, A-102, A-121, ADR-0002, ADR-0023, ADR-0024, BR-03, NFR-02

## Context

Every document in this project calls the history log append-only. `00_context.md#glossary` defines
property history as "the append-only log of every state change". A-014 says every state change writes an
append-only event. Five lock files repeat it.

Nothing so far makes it true. In every one of those places "append-only" describes an intention held by
the application code, and application code that intends not to update a table is one ORM call away from
updating it. The realistic route is not malice: it is a data-repair script during the pilot, a backfill
that fixes a mis-stamped `scope_prompt_id`, or a developer correcting a typo in a `reason` string as a
kindness to the person who wrote it.

Prope already has one precedent for this exact judgement. BR-03 — only Approved revisions may be released
— is enforced by a **database constraint**, not by application code, and that was decided because the
rule is the product. The audit trail is the same class of claim: `00_context.md#success` asserts that
100% of non-break-glass releases carry an approval record, and `positioning.md`'s whole argument is that
Prope can say who changed what and when. A log that the application can edit supports a weaker sentence
than the one being sold.

The counter-pressure is real and worth naming: A-012 caps the operational budget at one
`docker-compose up`, and anything requiring a second runbook loses.

## Decision

**`history_event` is append-only at the database privilege level. The application's database role holds
`INSERT` and `SELECT` on it and does not hold `UPDATE` or `DELETE`.**

- The grant is part of the schema migration, so it ships with the table and cannot be forgotten when a
  new environment is created.
- A correction to a written event is a new event, never an edit — the same rule ADR-0002 applies to
  revisions and A-102 applies to the price table. Prope now enforces this shape in three places, and this
  is the one where it is enforced by the database rather than by the schema's shape.
- Migrations run as a separate role that does hold the privileges, which is where a genuine schema change
  or an emergency correction goes: visible, deliberate, and outside the application.
- The privilege is asserted by a test that attempts an `UPDATE` and an `UPDATE`-free `DELETE` against the
  application role and requires both to be refused by the database — not by an application guard, which
  is the thing being distrusted.
- Combined with A-121 (no retention, no expiry job), there is no code path in Prope that removes a history
  row. The absence of a deletion job is part of the guarantee, not an omission.

## Alternatives rejected

**Application-level convention: a repository class with no update method.** Rejected as the status quo
that prompted the ADR. It is defeated by any code that does not go through the repository, which during a
pilot means the psql session someone opens to fix bad data. It also cannot be tested for — you can assert
the method does not exist, which proves nothing about the table.

**A `BEFORE UPDATE OR DELETE` trigger that raises.** Rejected as strictly weaker for the same effort. A
trigger is owned by the same role that owns the table, so the actor it is meant to stop can drop it, and
it is disabled wholesale by `ALTER TABLE ... DISABLE TRIGGER` — a command that reads like routine
maintenance. A privilege revocation is enforced by the engine's authorisation layer rather than by
something running inside the transaction it is policing.

**A hash chain: each event carries the hash of its predecessor, making tampering detectable.** Rejected
as the wrong guarantee at the wrong price. It detects tampering after the fact and prevents nothing,
which is backwards for a log whose realistic threat is a well-meaning repair script, not a forger.
Verifying it needs a job, an alert, and a documented response — a second runbook, which A-012 rules out —
and the response to a broken chain is unspecifiable, because there is no untampered copy to restore from.
Worth revisiting only if a customer requires tamper-evidence contractually, which is an OQ-006 question,
not a build one.

**Write-once storage or an external append-only log.** Rejected under A-012 and
`00_context.md#scope` — a second datastore with its own runbook, for a table expected to hold a few
thousand rows during a pilot.

**Accept mutability and rely on the modules' good behaviour.** Rejected on what the product claims. The
distinguishing feature against a Google Sheet is that the record cannot be quietly rewritten; a log the
application can rewrite is a Sheet with better indexing. The cost of the alternative is one `REVOKE` in a
migration, which is the cheapest guarantee in this document.

## Consequences

- One line in a migration, one test, and no runtime cost. This is the least expensive decision in Prope
  relative to what it protects.
- Mistakes become visible instead of erasable: a wrongly-stamped event is corrected by a compensating
  event, and both are in the trail. That is the correct behaviour for an audit log and will occasionally
  be annoying, which is the trade.
- A schema change to `history_event` needs the migration role, so it is a deployment action rather than
  something an application can do to itself.
- Prope now enforces "the record is not editable" three ways for three different reasons: revisions are
  immutable by shape (ADR-0002), prices are superseded rather than updated (A-102, ADR-0019), and history
  is append-only by privilege (here). Any fourth place with the same claim should say which of the three
  it is using.
