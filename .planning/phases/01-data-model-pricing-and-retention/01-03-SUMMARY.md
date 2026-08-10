---
phase: 01-data-model-pricing-and-retention
plan: 03
subsystem: call-ledger
tags: [pricing, effective-dating, exact-decimal, adr-0019, a-103, a-106, oq-b, oq-e, rls]
status: complete

requires:
  - "01-01 — the Alembic chain, the three roles, the ledger schema, ledger.call_record with its CHECK set, workspace_transaction(), the testcontainers rig"
  - "01-02 — ledger.price_table (append-only by privilege), ledger.call_body, ledger.workspace_spend, the partial unpriced index, and prope.call_ledger.models"
provides:
  - "`prope.call_ledger.domain` — CostStatus / UsageStatus / Source / Outcome as StrEnum, byte-identical to the database CHECK sets; PriceRow, CallRecordDraft, CallBodyDraft, WriteResult"
  - "`prope.call_ledger.pricing.resolve_price` — the effective-dated lookup at a BOUND instant, half-open [effective_from, next effective_from), returning None for both shapes of unpriced"
  - "`prope.call_ledger.pricing.compute_cost` / `.COST_SCALE` — exact decimal quantised at the column's ten places with banker's rounding"
  - "`prope.call_ledger.writer.write_records` — the Phase 1 callable write-path seam Phase 2's drain and Phase 3's fallback both call"
  - "`prope.call_ledger.writer.UNPRICED_WORKLIST` — CL-04's operational surface as a projection over the stored encoding"
  - "The three cost states as real rows: priced / unpriced / not_applicable, with no fourth and no default branch"
  - "33 new tests against a live PostgreSQL 17, including three mutation-verified guarantees"
affects:
  - "Phase 2's drain — calls write_records once per workspace group; the transaction boundary is now fixed and must not be re-cut"
  - "Phase 2's GET /api/v1/prices/unpriced — the projection exists; only the route is owed"
  - "Phase 2's get_run_totals — the unknown count is computable from usage_status alone, asserted equal to the NULL-token count"
  - "Phase 2's PUT /workspaces/{id}/retention — retention_window is a keyword argument today (OQ-B); wiring a stored window changes a call site, not the writer"
  - "Phase 19's gateway GATE-04 fallback — its row shape is pinned as unknown/not_applicable with NULLs (OQ-E), so it inherits the reading rather than inventing a zero"

tech-stack:
  added: []
  patterns:
    - "`now` is never called; it is passed. The resolver takes `at`, the writer takes `retention_window`, and neither module contains a clock read"
    - "A cost is quantised at the COLUMN's scale, never at a currency's minor units — asserted by a sub-cent test and by a source gate refusing any float on a money path"
    - "Absence has one representation per kind and the two shapes of an absence are asserted INDISTINGUISHABLE, not merely both handled"
    - "A no-zeros claim ships beside row counts in the same test, because truncate_ledger makes a post-suite table scan return 0 for free"
    - "A guarantee that passed on its first run is mutation-checked: break it, watch the test fail, restore, diff against the backup"

key-files:
  created:
    - .planning/phases/01-data-model-pricing-and-retention/.plan-03-base-sha
    - src/prope/call_ledger/domain.py
    - src/prope/call_ledger/pricing.py
    - src/prope/call_ledger/writer.py
    - tests/unit/__init__.py
    - tests/unit/test_effective_dated_pricing.py
    - tests/unit/test_cost_arithmetic.py
    - tests/unit/test_missing_price_is_unpriced_not_zero.py
    - tests/unit/test_unknown_usage_never_zero.py
    - tests/integration/test_write_path.py
  modified: []
  deleted: []

decisions:
  - "A priced record whose cost works out to exactly zero raises rather than storing a zero or downgrading to unpriced. The plan names three states and no fourth; both silent answers would be untrue, so the writer surfaces it."
  - "`workspace_spend.updated_at` is the one clock reading in the writer, via `clock_timestamp()` in the upsert's DO UPDATE. It means 'when the database saw this' — the same thing its column default means — and no pricing or retention value is derived from it."
  - "The writer also compares the batch's currency against the currency already stored for that (workspace, month), not only within the batch. Two batches in one month can disagree; A-107 forbids summing them either way."
  - "The draft builders and the fixture calendar live in tests/unit/__init__.py and are imported by tests/integration/test_write_path.py. One definition of what a draft looks like, so a unit assertion and an integration assertion cannot disagree about the thing they both describe."
  - "CL-11 was NOT marked complete. Its second clause — 'the unknown count is reported alongside the total' — is get_run_totals, which the ROADMAP puts in Phase 2."

metrics:
  duration: ~25m
  completed: 2026-08-10

actuals:
  tokens: 21400
  tasks: 2
  commits: 2
---

# Phase 01 Plan 03: Priced at its own timestamp, in exact decimal — Summary

A call made on day 5 and written on day 12 is priced at the day-1 price row, and
a price row added on day 20 leaves it byte-identical — asserted by asking the
same question twice with the day-20 row inserted in between. The three cost
states are now rows rather than intentions: `priced` with a strictly positive
sub-cent figure, `unpriced` with real tokens and a NULL cost, `not_applicable`
with NULL tokens, and a mixed batch of all three that holds no zero anywhere.

## What was built

**`domain.py` — the vocabulary, with no float and no naive datetime.** The four
`StrEnum`s carry values byte-identical to `0002`'s CHECK sets. `CallRecordDraft`
deliberately does **not** carry `cost`, `currency`, `price_row_id` or
`cost_status`: those four are the writer's answer, and a caller able to supply
them is a caller able to supply a zero. `usage_status` is derived from whether
the token fields are present rather than declared, so it cannot contradict them.
`__post_init__` refuses a naive `created_at` and refuses half a usage object.

**`pricing.py` — the resolver and the arithmetic, kept separate.**
`PRICE_IN_FORCE` selects at a **bound** `at` with `effective_from <= :at`,
ordered descending, limited to one — a backward scan on
`uq_price_table_workspace_id`'s own index. It contains no server-clock call, and
a source gate asserts that. `compute_cost` divides in exact decimal, sums, and
quantises to `COST_SCALE` (ten places, `ROUND_HALF_EVEN`) — the **column's**
scale, never a currency's minor units. Handed a non-`Decimal` price it raises.

**`writer.py` — one seam, three states, no fourth.** `write_records(session,
records, *, retention_window=timedelta(days=30))`. It opens no transaction,
switches no workspace, and refuses a batch spanning two workspaces or two
currencies **whole** rather than in part. Each draft is priced at its own
`created_at`; each body's `expires_at` is that same timestamp plus the window
argument; `workspace_spend` is upserted in the caller's transaction with
`period_month` from the record's own month in UTC. `UNPRICED_WORKLIST` is the
projection Phase 2's route will serve.

## Verification — what actually ran

Every row is the output of a command executed in this session.

| Check | Result |
|-------|--------|
| `uv run pytest tests/unit/test_effective_dated_pricing.py tests/unit/test_cost_arithmetic.py -x -q` | **14 passed** (8 + 6) |
| `uv run pytest tests/unit/test_missing_price_is_unpriced_not_zero.py -x -q` | **4 passed** |
| `uv run pytest tests/unit/test_unknown_usage_never_zero.py -x -q` | **3 passed** |
| `uv run pytest tests/integration/test_write_path.py -x -q` | **12 passed** |
| `-k boundary` | 1 passed, 7 deselected |
| `-k not_yet_effective` | 2 passed, 6 deselected |
| `-k sub_cent` | 1 passed, 5 deselected |
| `-k zero_refused` | 1 passed, 3 deselected |
| `-k zero_tokens_refused` | 1 passed, 2 deselected |
| `-k no_zero_anywhere` | **1 passed, 11 deselected** — exactly one, as required |
| `uv run pytest -q` (whole suite) | **67 passed** — Waves 1–2's 34 among them |
| `uv run ruff check src/ tests/ alembic/` | All checks passed |
| inline `compute_cost(300,150,…)` gate | printed `0.0001350000`, exit 0 |
| `inspect.signature(write_records)` gate | `retention_window: datetime.timedelta = datetime.timedelta(days=30)`, exit 0 |
| `grep -rnE ': *float\|float(\|Numeric(asdecimal=False' src/prope/call_ledger/` | no match (exit 1) |
| `grep -rn 'utcnow' src/prope/ tests/` | no match (exit 1) |
| `grep -c 'effective_from' src/prope/call_ledger/pricing.py` | 8 |
| `grep -nE 'now()\|CURRENT_TIMESTAMP' src/prope/call_ledger/pricing.py` | no match (exit 1) |
| `grep -nE 'CURRENT_TIMESTAMP\|datetime.now(' src/prope/call_ledger/writer.py` | no match (exit 1) |
| `git cat-file -e "$(cat …/.plan-03-base-sha)^{commit}"` | exit 0 |
| `docs/` since the fixed phase base `b27b58a` | 0 committed, 0 uncommitted, 0 untracked |
| `alembic/versions/` since **this plan's** base `44c7e02` | 0 committed, 0 uncommitted, 0 untracked |

### The mutation check — because Task 2 passed on its first run

Task 1's tests were observed RED (`ModuleNotFoundError: No module named
'prope.call_ledger.domain'`) before `domain.py` and `pricing.py` existed.
**Task 2's did not get a RED run**: the tests and the writer were both written
before pytest was invoked again, so the only failure they would have shown is an
import error I did not watch. Rather than assert they have teeth, three
guarantees were broken on purpose and the failures observed:

| Mutation | Test that failed |
|----------|------------------|
| `effective_from <= :at` → `< :at` | `test_the_boundary_instant_belongs_to_the_newer_row` — "the boundary instant resolved to the superseded row" |
| `expires_at` ignores the `retention_window` argument | `test_expires_at_honours_a_custom_retention_window` |
| the `unpriced` branch substitutes `cost = 0` | `test_no_zero_anywhere_in_a_mixed_batch_of_all_three_cost_states` — **`IntegrityError` from the engine**, not from the assertion |

Both files were restored from backups and `diff -q` confirmed byte-identical
restoration before the final suite run. The third mutation is the most useful
result in this document: it shows the never-zero rule is the *database's*, so a
writer that stopped enforcing it would still be caught.

### The must-have truths, and what proves each

| Truth | Proved by |
|-------|-----------|
| Day-5 call, day-12 write, day-20 row added — cost and `price_row_id` unmoved | `test_a_day_20_price_row_does_not_move_a_call_made_on_day_5`: resolves, inserts the day-20 row, resolves again, asserts the two `PriceRow`s are **equal field for field** |
| A call exactly on an `effective_from` resolves to the NEW row | `test_the_boundary_instant_belongs_to_the_newer_row` — asserts both microsecond neighbours too; mutation-verified |
| Not-yet-effective is unpriced on the same footing as no row at all | `test_not_yet_effective_and_no_rows_at_all_are_indistinguishable` asserts the *equality* of the two answers, plus `test_a_price_row_that_is_not_yet_effective_is_unpriced_on_the_same_footing` at the writer level |
| Exact decimal, ten places, banker's rounding, byte-identical across runs | `test_the_same_inputs_produce_a_byte_identical_cost` compares `as_tuple()` and `str()`, not just value; `test_banker_s_rounding_is_applied_at_the_eleventh_place` asserts a tie going **down** and another going **up** |
| A realistic sub-cent call stores a strictly positive cost | `test_a_sub_cent_call_stores_a_strictly_positive_cost` — `0.0001350000`, exponent −10; `test_one_token_at_the_cheapest_realistic_price_is_still_positive` covers the floor at 2×10⁻⁸ |
| No price row ⇒ tokens intact, cost/currency/price_row_id NULL, `unpriced`, and on the worklist | `test_a_call_with_no_price_row_keeps_its_tokens_and_records_no_cost` + `test_the_unpriced_worklist_returns_the_pair_with_its_count_and_since` (which also asserts the **priced** pair does not leak onto the list) |
| No usage object ⇒ `unknown`, NULL tokens, `not_applicable`, NULL cost (OQ-E) | `test_a_call_with_no_usage_object_stores_nulls_rather_than_zeros` — with a price row **seeded**, so `not_applicable` is visibly not a synonym for "no price available"; `test_the_gateway_pre_first_byte_fallback_is_unknown_not_a_zero` names GATE-04 |
| `expires_at` = the record's own `created_at` + window, defaulting to 30 days | `test_expires_at_is_the_records_own_created_at_plus_the_default_window` and `…honours_a_custom_retention_window`; mutation-verified |
| `workspace_spend` upserted in the same transaction; `call_count` counts all, `total_cost` sums priced only | `test_call_count_counts_every_record_and_total_cost_only_the_priced_ones` — 3 records, 1 priced, `call_count == 3` |
| `period_month` from each record's own `created_at`; a second month is a second row | `test_a_second_month_creates_a_second_spend_row` — one batch straddling 2026-08/2026-09; `test_a_second_batch_accumulates_onto_the_same_month_row` proves the upsert adds rather than replaces |
| An eval record writes no body and still moves spend | `test_an_eval_draft_writes_no_body_and_still_moves_workspace_spend` — the join-count assertion is **inside** the test, beside `eval_records > 0`; `test_an_eval_draft_carrying_a_body_is_refused` makes the absence a rule |
| The unknown count is computable from the encoding alone | `test_the_gateway_pre_first_byte_fallback_…` asserts `count(*) WHERE usage_status='unknown'` equals `count(*) WHERE input_tokens IS NULL` — Phase 2 can count on the status and never guess what a NULL means |
| The prohibition: nothing estimates, infers, defaults or back-fills | No branch in `writer.py` produces a figure from anything but reported usage and a stored price row. `test_no_zero_anywhere_…` writes all three states and asserts zero rows with `cost = 0 OR input_tokens = 0 OR output_tokens = 0`, beside four positive controls |

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 2 — Missing critical functionality] A priced cost of exactly zero had no defined answer**
- **Found during:** Task 2, reading `ck_call_record_cost_is_never_zero` against
  `ck_call_record_unknown_usage_is_null`. Reported usage of `0` tokens is
  *permitted* by the CHECK set, and a price row of `0` is permitted by
  `ck_price_table_prices_are_non_negative`. Either produces `cost = 0` on a
  `priced` row, which the engine then refuses — turning a data edge into an
  opaque write-path outage mid-batch.
- **Fix:** `write_records` raises `ValueError` naming the call, the price row,
  the token counts and the two per-1k prices. It does **not** store the zero and
  does **not** downgrade to `unpriced`: the encoding has three states and both
  silent answers would be untrue. Documented in the module docstring.
- **Files modified:** `src/prope/call_ledger/writer.py`
- **Commit:** `d53f003`

**2. [Rule 2] The currency check extended to the already-stored row**
- The plan asks that a currency mismatch *within a batch* raise. A second batch
  in the same month can disagree with the first, and the upsert would have
  summed them under whichever currency arrived first.
- **Fix:** before each month's upsert the writer reads the stored `currency` and
  raises on a mismatch. `COALESCE(existing, excluded)` keeps the first one
  otherwise.
- **Commit:** `d53f003`

### Departures from the plan text

**3. `PRICE_IN_FORCE` selects `effective_from` as a fifth column**
- The plan lists four. `PriceRow` carries `effective_from` (the plan's own
  artifact spec says so), and `PriceRow(**row)` needs it. A superset of the
  listed columns, at no cost — the index entry already holds it.

**4. `resolve_price` short-circuits a NULL key**
- A draft with no `provider_config_id` or no `upstream_model` cannot match any
  row, so the function returns `None` without a round trip. Same answer, one
  fewer query per such record. Named here because it is a branch the plan text
  does not describe.

**5. Two tests beyond the plan's list, both positive controls**
- `test_a_call_after_the_second_row_resolves_to_the_second_row` — without it,
  a resolver that always returned the oldest row would pass the day-5 test.
- `test_an_eval_draft_carrying_a_body_is_refused` — makes the no-body property
  a rule rather than an accident of the fixture.
- Plus `test_a_second_batch_accumulates_onto_the_same_month_row`, which
  distinguishes an upsert that adds from one that replaces.

**6. `workspace_spend.updated_at` uses `clock_timestamp()` in the DO UPDATE**
- The plan says the writer reads no clock. This one column means "when the
  database saw this", which is exactly what its own DDL default means, and no
  pricing, retention or aggregation value is derived from it. Recorded rather
  than buried: it is the single clock reading in the module, and the source gate
  (`CURRENT_TIMESTAMP|datetime\.now\(`) does not catch it, so this line is the
  record.

No architectural change was needed and no checkpoint was reached.

## Requirements — what was ticked and what was not

**Ticked: CL-03 and CL-04.**

- **CL-03** — "priced at the price row in force at the call's own timestamp, and
  a price row added later never changes it". Both clauses are code and both are
  asserted, the second by inserting the later row *between* two resolutions.
  Nothing recomputes: there is no repricing path in this plan and
  `price_table` cannot be edited (T-006, plan 01-02).
- **CL-04** — "stores its tokens with cost `unpriced` — never zero — and appears
  on the unpriced worklist". The storage half is asserted, the never-zero half is
  asserted **at the engine**, and the pair demonstrably appears on the worklist
  with its count and `since`. The `GET /api/v1/prices/unpriced` **route** is
  Phase 2's and is not built here; the worklist itself — the query, the encoding
  and the partial index that serves it — is complete and tested. That is the
  reading this tick rests on, stated so a reviewer can disagree with it.

**Not ticked: CL-11**, despite being in this plan's frontmatter. Its first
clause ("records unknown tokens as null — never zero") is fully delivered and
engine-enforced. Its second — "**and the unknown count is reported alongside the
total**" — is `get_run_totals`, which the ROADMAP puts in Phase 2 and which this
plan's own must-have list marks as a backstop. What Phase 1 owed is the storage
shape that makes the count computable, and that is asserted. Ticking CL-11 now
would put a false tick in a traceability table nothing downstream would revisit.

**Not ticked and not claimed: CL-09** ("an eval-case usage row is priced and
counted toward workspace spend with no body stored"). This plan proves that
property end to end in `test_an_eval_draft_writes_no_body_and_still_moves_
workspace_spend` — but the entry point evaluation calls (`price_usage(run_id,
usage_rows)`, INT-019) does not exist, and a requirement is not met by the
capability its future caller will use. Recorded so Phase 2 finds the work
already half done rather than re-deriving it.

**CL-05 and CL-08** remain 01-04's, untouched here. **CL-01, CL-02, CL-06,
CL-07, CL-10, CL-12** are Phase 2/3.

## Open questions — status after this plan

- **OQ-B** — the retention window is a **keyword argument with a 30-day
  default**, asserted by an `inspect.signature` gate. No table outside
  `data.owns` was touched. Phase 2 still owns where the per-workspace setting
  lives; wiring one changes a call site, not the writer.
- **OQ-E** — **answered in a test, still open upstream.** GATE-04's "zero tokens
  and zero cost" row is written here as `usage_status='unknown'` /
  `cost_status='not_applicable'` with NULL tokens and a NULL cost, in a test
  named for the pre-first-byte fallback. `ck_call_record_unknown_usage_is_null`
  refuses the literal reading, so Phase 19 will inherit this shape rather than
  invent a zero. The two documents still use different words for the same row;
  nothing under `docs/` was edited.
- **OQ-A** — untouched and still holding: no `::uuid` cast entered any SQL here.
- **OQ-C, OQ-D** — untouched; both belong to retention (01-04 / Phase 3).

No new open question arose.

## Known Stubs

None. Every function created here is wired and exercised against a live engine.
`UNPRICED_WORKLIST` is a module-level statement with no route — that is its
correct Phase 1 form (the ROADMAP puts the route in Phase 2), and it is not a
stub: a test executes it and asserts its projection, count and `since`.

The prohibition held. No branch in this plan estimates, infers, defaults or
back-fills a cost or a token count. Grep-checkable consequences: no `float` on
any money path, no `utcnow`, no server-clock call in the resolver or the writer,
and no `round(x, 2)` anywhere. The one place a zero could have been introduced
silently — a priced cost computing to zero — raises instead, and the deviation
above says why.

## Threat Flags

None. Every threat in the plan's register is addressed as dispositioned:

- **T-01-14** (rounding) — quantised at the column's scale, `TypeError` on a
  non-`Decimal` price, sub-cent test, source gate refusing floats.
- **T-01-15** (an absence becoming a zero) — three states, no default branch,
  `no_zero_anywhere` with four positive controls, and mutation C showing the
  engine refuse a substituted zero.
- **T-01-16** (priced at write time) — `at` is bound, both modules are
  clock-free by source gate, and the day-5/day-12/day-20 test is
  mutation-verified at the boundary.
- **T-01-17** (mis-stamped `workspace_id`) — the batch is refused before any
  write, asserted with a `count(*) == 0` afterwards.
- **T-01-18** (a body in a log line) — this module emits no log and no metric at
  all; the one place a body is written is `ledger.call_body`.
- **T-01-19** (spend by aggregating `call_record`) — the aggregate is an upsert
  on the composite key inside the caller's transaction.

No file created here introduces network surface, an auth path, file access, or a
trust-boundary schema change outside that register. **No migration was added**
and no file under `docs/` was touched — both verified against fixed bases.

## Notes for the next plan

- **`write_records` does not commit.** The caller's `workspace_transaction()`
  owns the boundary, which is what makes "refused whole, not written in part"
  true. Do not add a commit inside it.
- **There is no upsert on `call_id` yet.** A-099's idempotency is Phase 3's
  (CL-02); `INSERT_CALL_RECORD` is a plain insert today and a redelivery would
  violate `pk_call_record`.
- **The batch is a Python loop with one `resolve_price` per record.** Correct and
  clear at Phase 1 volumes. The batch `DISTINCT ON` form is in the research if
  Phase 2's drain needs it; nothing about the seam's contract changes.
- **`tests/unit/__init__.py` now holds the shared fixture calendar and the two
  draft builders** (`gateway_draft`, `eval_draft`). Reuse them rather than
  hand-rolling a draft — they encode which CHECK constraints each `source`
  requires.
- **Repricing (CL-05) must filter on `cost_status = 'unpriced'`**, not on
  `cost IS NULL`. A `not_applicable` row also has a NULL cost and has no tokens
  to price; the wider filter would give it one.

## Self-Check: PASSED

All 10 created files verified present on disk. Both commits (`6102786`,
`d53f003`) verified present in `git log --oneline --all`.
