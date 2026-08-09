# ADR-0019 — Cost is priced once at write time; a price is superseded, never edited

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-100, A-101, A-102, A-107)
**Module**: call-ledger, evaluation, release-control (written while locking call-ledger)
**Related**: A-006, A-030, A-055, A-057, BR-07, ADR-0004, ADR-0013

## Context

BR-07 makes it non-negotiable that cost is measured from actual runs and never inferred from prompt
length. A-030 adds effective-dated prices with a stated reason: "without them, yesterday's approved
cost comparison silently changes when someone edits a price today."

That reason is doing more work than it looks. A cost delta is shown to a reviewer *before* an approve
decision, and the approval record is testimony about what the reviewer saw (A-074). If the number can
change afterwards, the record describes something that no longer exists — and the change is silent,
because nothing about a price edit touches the approval.

So there are two separate questions hiding in "how do we price a call": **when** is the arithmetic
done, and **what happens to history** when a price changes.

## Decision

**Priced once, at write time, with provenance. Prices are append-only.**

- The writer computes cost when it persists the record, using the price row in force at the **call's
  own `created_at`** — not at wall-clock write time, which differs after a spill replay or a backlog.
- The resulting `cost`, `currency`, and the `price_row_id` that produced it are stored on the record.
  "Why is this number this number" has an answer years later without reconstructing anything.
- `price_table` is **append-only and effective-dated**. A price is never updated and never deleted; a
  change is a new row with a later `effective_from`. This is also call-ledger's audit trail, since it
  has no edge to property-history and a spend ceiling is not a state change on a prompt property.
- **A missing price row is `unpriced`, never zero.** Tokens are still stored. `get_run_totals` returns
  the unpriced count alongside the total, so evaluation can withhold a delta the way A-057 already
  withholds one on error.
- **A missing usage object is `unknown`, never zero.** Token counts are null, and cost is
  `not_applicable` rather than 0.
- **Repricing fills only previously-unpriced rows.** A row that already has a cost is never recomputed
  — that is the rule that makes history stable.
- A price row carries an explicit currency; a workspace uses one currency and there is no conversion
  (A-107).

## Alternatives rejected

**Compute cost at read time from the price table.** Rejected as the thing A-030 names by hand. Editing
a price would retroactively change every stored figure, including the ones behind approvals already
granted, and nothing would report it. It also makes every read of a comparison a join against an
effective-dated table, which is slower for no benefit.

**Reprice everything whenever a price changes.** Rejected: it is read-time pricing with extra steps
and a batch job. The history still changes; it just changes at a different moment, which is worse
because now there is a job someone can blame instead of an obvious design property.

**Store the cost with no price provenance.** Rejected on the question that actually gets asked in six
months: "why did this run cost that?" Without `price_row_id`, answering it means guessing which row
was in force and hoping nobody has added one since. One column removes the guess.

**Treat a missing price as zero.** Rejected, and it is the most dangerous of these because it produces
a working system. A zero is a number a reviewer will act on — a revision that looks free is a revision
that looks better than its baseline, and the cost delta exists specifically to inform that comparison.
An absent figure asks a question; a wrong figure answers it. Same argument ADR-0013 made about
estimating tokens: an estimate that looks like a measurement is worse than an honest gap.

**Mutable prices with an `updated_at`, on the grounds that a typo needs fixing.** Rejected: a typo is
fixed by superseding it with a corrected row, and the corrected row's effective date makes the fix
auditable. Allowing an in-place edit to serve the typo case allows it for every case, and the two are
indistinguishable in the schema.

**Store cost in a single normalised currency, converting at write time.** Rejected as out of scope
(A-107). It needs an FX rate table with its own effective dating — a second version of this exact
problem — and it would make every stored figure depend on a rate nobody reviewed. A workspace using
one currency needs none of it.

## Consequences

- `price_row_id` is on `call_record` from day one. Adding it later would leave every existing row
  unexplainable, which is the migration this ADR exists to avoid.
- A record is priced by its own timestamp, so a spill replay, a writer backlog, and a normal write all
  produce the same number. This is asserted directly (AC-3: made on day 5, written on day 12).
- The unpriced worklist becomes a real operational surface — the only spend-shaped screen in the MVP —
  because unpriced calls are now a visible, actionable list rather than silent zeros.
- Evaluation's `get_run_totals` returns two gap counts, not just a total. A cost delta computed over a
  partly unpriced run is not a delta, and this is what lets the review screen say so instead of
  showing a confident wrong number.
- Superseded price rows are never removed, so the table grows monotonically. It grows by one row per
  price change, which at any realistic rate is nothing.
