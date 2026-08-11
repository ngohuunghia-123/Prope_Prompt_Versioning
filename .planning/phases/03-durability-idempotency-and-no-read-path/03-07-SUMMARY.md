---
phase: 03-durability-idempotency-and-no-read-path
plan: 07
subsystem: backend
tags: [performance, pricing, adr-0019, n-plus-one, sqlalchemy, postgres, load]

# Dependency graph
requires:
  - phase: 01-data-model-pricing-and-retention
    provides: "pricing.PRICE_IN_FORCE and resolve_price — the effective-dated rule stated in SQL, and uq_price_table_workspace_id, whose column order IS the lookup order"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 02
    provides: "write_records' idempotent upsert on call_id with RETURNING, and the recorded sort_by_parameter_order sentinel trap this plan must not reintroduce"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 06
    provides: "The measurement and the localisation — 212 and 189 records/sec end to end, 494 isolated, and 0.710 s of a priced 500-record window spent in 500 resolve_price round trips"
provides:
  - "pricing.PRICE_ROWS_FOR_KEYS — every price row for a batch's distinct keys, in ONE statement, joined pairwise against an unnest of two text arrays"
  - "pricing.PriceBook / PriceBook.price_at — the same half-open effective-dated rule applied per record, in Python, against that record's own created_at"
  - "pricing.load_price_book — the loader, with the empty-key guard that keeps an all-unknown batch at zero price reads"
  - "write_records reading ledger.price_table ONCE per batch instead of once per reported record"
  - "tests/integration/test_price_resolution_is_batched.py — the round-trip count as a function of the distinct keys and not of the batch length, COUNTED, with the recorder calibrated first"
  - "tests/unit/test_effective_dated_pricing.py::test_the_batch_resolver_and_resolve_price_agree — the control that stands in for the two resolvers being one function"
affects: [03-VERIFICATION, 05-property-history, 16-18-evaluation, 19-21-gateway]

actuals:
  tokens: 62000
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns:
    - "A pairwise key list bound as two parallel text[] arrays and joined with unnest, so M lookups are one round trip and no fragment is interpolated"
    - "An effective-dated range derived by POSITION in an ordered list, never stored — the list counterpart of lead(effective_from)"
    - "A performance property asserted by COUNTING statements at the engine rather than by timing them"
    - "The counting instrument calibrated in its own test, by issuing the shape the code used to issue and requiring the old number"
    - "Two implementations of one rule held equal by an equivalence test, with a delete-together instruction written at both"

key-files:
  created:
    - tests/integration/test_price_resolution_is_batched.py
  modified:
    - src/prope/call_ledger/pricing.py
    - src/prope/call_ledger/writer.py
    - src/prope/call_ledger/repricing.py
    - tests/unit/test_effective_dated_pricing.py
    - tests/load/test_fifty_rps_for_ten_minutes.py
    - .planning/phases/03-durability-idempotency-and-no-read-path/deferred-items.md

key-decisions:
  - "D-280: one statement per batch, joined pairwise against unnest of the distinct (provider_config_id, upstream_model) pairs. Rejected: one statement per pair, because M is unbounded in a 500-record window and the worst case is the N+1 being removed. Rejected: a memo keyed on the resolved created_at instant, which would report a perfect number in a load run whose 30,000 drafts share day(5) and buy nothing in production"
  - "D-281: effective dating moves to bisect_right(rows, at) - 1 over the key's ascending rows, which selects exactly what effective_from <= :at ORDER BY effective_from DESC LIMIT 1 selects. The interval stays half-open and the supersession range stays DERIVED — by position here, by lead(effective_from) in api.PRICE_ROWS — because a stored effective_to needs the UPDATE A-102 / T-006 forbid"
  - "D-282: no upper bound on effective_from. Bounding the fetch by the batch's latest created_at is a correct optimisation and puts an instant back into the query, one refactor from the memo D-280 refused"
  - "D-283: resolve_price and PRICE_IN_FORCE survive unchanged and the drift is closed by an equivalence TEST rather than by collapsing them. Rejected: delegation — PRICE_IN_FORCE is named in prose in api.py (twice), schemas.py and test_management_routes.py as the statement of the half-open interval, and repricing's statement would change in a plan about the writer"
  - "D-284: the book is loaded BEFORE pass 1, which also makes the batch see ONE snapshot of ledger.price_table instead of N under READ COMMITTED. The cost — one SELECT before a structurally invalid batch raises — is stated at the code"
  - "D-285: an empty key set executes nothing, so an all-unknown-usage batch still costs zero price reads. The guard is in load_price_book, so all three callers of write_records get it"
  - "The >= 500 records/sec assertion in tests/load/test_fifty_rps_for_ten_minutes.py was NOT lowered, relaxed, marked or moved. Only two comments in that file changed, both describing behaviour this plan made stale"

patterns-established:
  - "Calibrate a counting instrument in its own test by issuing the shape the code used to issue: 20 sequential resolve_price calls must be recorded as 20, or no small count in the file means anything"
  - "State a batch-level optimisation's CORRECTNESS argument, not only its speed one — one statement is one READ COMMITTED snapshot, and N statements are N"
  - "Name the test-passing device the change could have been, at the code, in the terms that make it obviously wrong (all 30,000 drafts share one timestamp)"

# No REQUIREMENTS.md id is completed here. CL-12 was closed by 03-06; this plan
# closes the `performance_requirements` clause 03-06 left red — partially, and
# the residue is OQ-085.
requirements-completed: []

open-questions-raised: [OQ-085]

coverage:
  - id: D1
    description: "A batch of N records over M distinct (provider_config_id, upstream_model) pairs issues exactly ONE statement against ledger.price_table — counted, for N=200/M=1, N=200/M=4 and N=20/M=4"
    verification:
      - kind: integration
        ref: "tests/integration/test_price_resolution_is_batched.py::test_one_statement_serves_a_whole_batch_whatever_its_length"
        status: pass
    human_judgment: false
  - id: D2
    description: "The statement recorder counts one per round trip — 20 sequential resolve_price calls are recorded as 20 — so every small count in the file is a fact about the writer and not about the listener"
    verification:
      - kind: integration
        ref: "tests/integration/test_price_resolution_is_batched.py::test_the_recorder_counts_one_statement_per_round_trip"
        status: pass
    human_judgment: false
  - id: D3
    description: "One round trip still prices every record from ITS OWN key — 200 rows read back through migrate_engine, each carrying the price_row_id seeded for its pair"
    verification:
      - kind: integration
        ref: "tests/integration/test_price_resolution_is_batched.py::test_every_record_in_the_spread_batch_is_priced_from_its_own_key"
        status: pass
    human_judgment: false
  - id: D4
    description: "A batch with no reported usage issues ZERO price statements, and a single-record batch (03-01's direct-write fallback) issues exactly one — the same count it issued before"
    verification:
      - kind: integration
        ref: "tests/integration/test_price_resolution_is_batched.py::test_a_batch_with_no_reported_usage_never_reads_the_price_table"
        status: pass
      - kind: integration
        ref: "tests/integration/test_price_resolution_is_batched.py::test_a_single_record_batch_still_costs_exactly_one_price_statement"
        status: pass
    human_judgment: false
  - id: D5
    description: "ADR-0019 inside ONE batch: three records sharing a key and a transaction, at day 5, exactly on day 10's effective_from, and day 12, resolve to two different price rows with two different costs"
    verification:
      - kind: integration
        ref: "tests/integration/test_price_resolution_is_batched.py::test_records_either_side_of_a_price_change_get_different_prices"
        status: pass
    human_judgment: false
  - id: D6
    description: "The SQL resolver and the batch resolver return equal PriceRows at six instants including one microsecond either side of a supersession, and a book answers None for a key it was not loaded for"
    verification:
      - kind: unit
        ref: "tests/unit/test_effective_dated_pricing.py::test_the_batch_resolver_and_resolve_price_agree"
        status: pass
      - kind: unit
        ref: "tests/unit/test_effective_dated_pricing.py::test_the_batch_resolver_answers_nothing_for_a_key_it_was_not_given"
        status: pass
    human_judgment: false
  - id: D7
    description: "performance_requirements' writer drain throughput >= 500 records/sec sustained, re-measured at ROADMAP SC5's literal condition after the fix"
    verification:
      - kind: load
        ref: "tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes"
        status: fail
      - kind: manual
        ref: "write_records(500 priced, bodies attached) through the pooled sessionmaker — the lock file's own stated condition"
        status: pass
    human_judgment: false
    rationale: "TWO measurements of one requirement, and they disagree. Under performance_requirements' stated condition — batched inserts, bodies included, single writer — write_records measures 1,984-2,004 records/sec after this change against 469 before, four times the target. Derived from the load run's recovery leg it measures 450 and 448 across two independent full-length runs, against 500, and that is the assertion that exists and it is RED. The recovery leg also contains the broker, the drain's 250 ms per-window collection floor, the publisher on the same event loop, and the test's own count(*) poll every 100 ms. The number was NOT lowered and the assertion was NOT weakened; the conflict is raised as OQ-085 with the question of which measurement the requirement is about."
  - id: D8
    description: "Everything 03-06 proved is still proven — 30,000 of 30,000 rows, enqueue p95 under 1 ms, zero metadata dropped, a full 60 s stall whose backlog clears, AC-12's write-lag clause over the steady windows, and 5,000 expired bodies swept under load"
    verification:
      - kind: load
        ref: "tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes"
        status: pass
    human_judgment: false

# Metrics
duration: 95min
completed: 2026-08-11
# `blocked`, on the same convention 03-06 used: the marked run's
# `performance_requirements` assertion is still red, at 450 and 448 against 500.
# The N+1 it was raised for is gone and the writer measures four times the target
# under the lock file's own stated condition; the residue is OQ-085's question of
# which of the two measurements the requirement means. Nothing is blocked from
# proceeding — the suite is green and the code ships — but a reader scanning this
# frontmatter must not see `complete` beside a red gate.
status: blocked
---

# Phase 03 Plan 07: Resolve prices per batch, not per record

**Plan `03-06` halted phase 3 on a measured finding and localised it precisely; this plan removes the
cause and re-runs the gate.** `write_records` issued one `resolve_price` round trip for every draft
whose `usage_status` was `reported` — an **N+1 inside the one write path in the system** — and issued
it whether or not a price row existed. It now issues **one** statement per batch, joined pairwise
against the batch's distinct `(provider_config_id, upstream_model)` pairs, and applies the same
half-open effective-dated rule per record in Python, **against each record's own `created_at`**.

ADR-0019 is preserved exactly, and the supersession range is still derived rather than stored.

**The outcome in one line, before any of the argument below.** `write_records` went from **469 to
1,984–2,004 records/sec** under `performance_requirements`' own stated condition — *batched inserts,
bodies included, single writer* — which is four times the required 500. The load run's **end-to-end
recovery leg went from 189/212 to 450/448**, and **the assertion is still red**, reproduced across two
independent full-length runs. The number was not lowered, the assertion was not weakened, and the
conflict between the two measurements is raised as **`OQ-085`**.

## Performance

- **Tasks:** 3 · **Files created:** 1 · **modified:** 5 (three source, two test) plus this phase's
  two standing artifacts
- **Suite:** 406 passed + 1 skipped before this plan; **414 passed + 1 skipped** after. Eight tests
  added, none changed, none removed

## What shipped

**`src/prope/call_ledger/pricing.py`** gains three public names and loses none.

- **`PRICE_ROWS_FOR_KEYS`** — every price row for a list of keys, in one statement. It is
  `PRICE_IN_FORCE` with the `LIMIT 1` removed and the single key replaced by a list, joined **pairwise**
  against `unnest(CAST(:provider_config_ids AS text[]), CAST(:upstream_models AS text[]))`. Two
  independent `= ANY(...)` predicates would be a cross product and would price a call from another
  provider's row; `unnest` of two arrays walks them in step, which is the only shape that expresses
  *these exact pairs*. The access path is unchanged — `uq_price_table_workspace_id` over
  `(workspace_id, provider_config_id, upstream_model, effective_from)`, whose own DDL comment says the
  column order **is** the lookup order — so this is **M index lookups inside one round trip** rather
  than M round trips.
- **`PriceBook` / `PriceBook.price_at`** — the same half-open rule over a list.
  `bisect_right(rows, at, key=effective_from) - 1` selects the last row at or before `at`, which is
  exactly what `effective_from <= :at ORDER BY effective_from DESC LIMIT 1` selects. A call landing
  exactly on an `effective_from` gets the **new** row; ties are impossible rather than broken, because
  `uq_price_table_workspace_id` refuses a second row for the same key and instant.
- **`load_price_book`** — the loader, with the empty-key guard, the de-duplicating `sorted(set(...))`,
  and the grouping that takes the statement's order rather than re-sorting.

**`src/prope/call_ledger/writer.py`** loads one book before pass 1 and calls
`prices.price_at(..., at=draft.created_at)` inside it. Nothing else moved: the five `ValueError`
refusals fire in the same order with the same messages, the mixed-currency refusal is still decided
over the whole batch in pass 1, `UPSERT_CALL_RECORD` still has `sort_by_parameter_order` **absent**
with its paragraph intact, the `RETURNING`-derived `inserted` set still builds the month buckets, and
`WriteResult`'s five counts are unchanged.

**`tests/integration/test_price_resolution_is_batched.py`** — six tests, no marker, no skip, 6-10 s.

**`tests/unit/test_effective_dated_pricing.py`** — two tests added, none changed.

## Why one query and not M, and why the pair and not the instant

Both alternatives were available and both are recorded at the code, because a reader who meets only
the answer will re-propose the question.

**One statement per distinct pair (M round trips)** satisfies the same *"a function of M and not of
N"* property and is simpler to write. It is refused because **M is unbounded**: a drain window is 500
records and nothing says they share a model, so its worst case is exactly the N+1 being removed.

**A memo keyed on `(pair, created_at)`** is the obvious first attempt and it is the one that had to be
named rather than merely avoided. Every one of the load run's thirty thousand drafts carries the
fixture calendar's `day(5)` — `03-06`'s own `deferred-items` entry says so — so an instant-keyed cache
would report a **perfect** number in the very test this plan re-runs and would buy **nothing** in
production, where every record has a timestamp of its own. That is a test-passing device and not a
fix, and the sentence saying so sits at the call site in `writer.py`.

**The batch resolution is also more faithful to ADR-0019, not less.** This is `READ COMMITTED`: every
statement takes its own snapshot, so N per-record lookups can see N different views of
`ledger.price_table` inside one batch if somebody commits a price row part-way through it. One lookup
gives the batch one view.

## The two tests that make it a fix rather than a coincidence

**The round-trip count is counted, never timed.** A timing assertion on a developer host re-measures
the host every morning; the property actually claimed is *"the number of round trips is a function of
the batch's distinct keys and not of its length"*, and that is countable exactly. A
`before_cursor_execute` listener on `app_engine.sync_engine` records every statement, and the count
under test is how many name `ledger.price_table`.

**The instrument is calibrated before anything is believed.** Every assertion in that file says a
number is *small*, and a broken counter produces small numbers for free — so
`test_the_recorder_counts_one_statement_per_round_trip` issues twenty sequential `resolve_price`
calls, which is exactly the shape `03-06` measured, and requires the recorder to report **twenty**. It
is also the last executable record of the old behaviour: if a per-record lookup is ever reintroduced,
that test still passes and the three counting tests go red, which is the direction the failure should
point.

**Effective dating is proven inside a single batch that no one price can serve.**
`test_records_either_side_of_a_price_change_get_different_prices` seeds a day-1 row and a day-10 row
at ten times the price, then writes **one** batch containing records at day 5, exactly on day 10, and
day 12. The three share a key and a transaction and differ only in `created_at`; they resolve to two
different `price_row_id`s with two different costs, read back through `migrate_engine`. The day-10
record is the half-open boundary, inside the batch. A whole-batch memo of any kind fails here
whatever its round-trip count says.

**And the two resolvers are held equal rather than assumed equal.**
`test_the_batch_resolver_and_resolve_price_agree` runs `resolve_price` and `PriceBook.price_at` over
the same rows at six instants — before every row, on the first, one microsecond either side of a
supersession, exactly on it, and after the last — and requires equal `PriceRow`s field for field.

## The measurements

All figures are on the same development host, against the same session containers, through the same
pooled sessionmaker `prope.app` builds. The isolated harness is the one plan 03-06 describes; it was
re-run **against unchanged code before any edit** so the before/after pair is measured today rather
than quoted, and deleted afterwards (`git status --porcelain` carries nothing of it).

### `write_records` in isolation — `performance_requirements`' own stated condition

*"batched inserts, bodies included, single writer"*, 500 priced gateway drafts each carrying a body.

**Before**, on unchanged code:

```
  500 sequential resolve_price   0.737 s (1.47 ms each)
  write_records(500 priced+body)  1.067 s -> 469 records/sec
  write_records(500 unknown)      0.125 s -> 4013 records/sec
  empty workspace_transaction        3.85 ms
```

That reproduces plan 03-06's localisation a third time: 0.737 s of the priced window's 1.067 s — **69%**
— is one `resolve_price` round trip per record, and the same 500 records with no price lookup write in
0.125 s.

**After**, three consecutive executions:

```
  500 sequential resolve_price   0.685 s (1.37 ms each)
  write_records(500 priced+body)  0.250 s -> 2004 records/sec
  write_records(500 unknown)      0.104 s -> 4790 records/sec
  empty workspace_transaction        4.31 ms
```

```
  500 sequential resolve_price   0.913 s (1.83 ms each)
  write_records(500 priced+body)  0.571 s -> 875 records/sec
  write_records(500 unknown)      0.345 s -> 1450 records/sec
  empty workspace_transaction        5.17 ms
```

```
  500 sequential resolve_price   0.739 s (1.48 ms each)
  write_records(500 priced+body)  0.252 s -> 1984 records/sec
  write_records(500 unknown)      0.110 s -> 4543 records/sec
  empty workspace_transaction        3.63 ms
```

**469 → 1,984–2,004 records/sec, a factor of about 4.2, and four times the required 500.** The middle
execution is host noise and not a property of this code: its **unknown-usage control** — which issues
no price statement before or after — fell from ~4,700 to 1,450 in the same run, so the whole machine
was three times slower for that minute. All three readings are printed rather than the best one.

The priced window is now within a factor of 2.4 of the unknown-usage window that does no pricing at
all, where it was a factor of 8.5 before.

### The gate `03-06` left red — `PROPE_RUN_LOAD=1 uv run pytest -m load -q -s`

Executed **twice at full length**, in the background, with nothing else touching Docker while either
ran. The first execution's output was captured through a `tail`, which discarded the printed report
above the traceback, so it was executed again in full; the two are reported as a pair rather than the
better of them, which is the posture 03-06 set.

**Run 1 — 622.73 s:**

```
E       AssertionError: the recovery cleared 3367 rows in 7.48 s = 450 records/sec, against 500. A writer that merely keeps up has no capacity to clear a backlog after a stall, so every stall becomes permanent pressure. One measurement on one host, with the publisher and the drain sharing its event loop: investigate it, never lower the number
E       assert 449.9931632312737 >= 500.0

tests\load\test_fifty_rps_for_ten_minutes.py:688: AssertionError
FAILED tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes
1 failed, 414 deselected, 1 warning in 622.73s (0:10:22)
```

**Run 2 — 620.56 s, with the printed report:**

```
  wall time            600.7 s for 30000 records
  enqueue span over 30000 calls: p50 0.1994 ms, p95 0.5081 ms, p99 0.6891 ms (CL-12's budget is 1.000 ms)
  rows (WORKSPACE_A)   30000 of 30000
  stall                60.0 s, backlog target 18003, reached 18366
  recovery             3368 rows in 7.51 s = 448 records/sec
  write lag <= 2.0 s  steady windows 26617/26617, whole run 26718/30000
  retention sweep      5000 bodies deleted under load
```

```
E       assert 448.3249339853321 >= 500.0

tests\load\test_fifty_rps_for_ten_minutes.py:688: AssertionError
FAILED tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes
1 failed, 414 deselected, 1 warning in 620.56s (0:10:20)
```

### Read against 03-06's two runs, clause by clause

| Clause | 03-06 run 1 | 03-06 run 2 | 03-07 run 1 | 03-07 run 2 |
|---|---|---|---|---|
| CL-12, enqueue p95 (budget 1 ms) | 0.4555 ms | 0.4814 ms | — | **0.5081 ms** — passed |
| CL-12, metadata dropped | 0 | 0 | passed | **0** — passed |
| SC5, rows through the owner role | 30000/30000 | 30000/30000 | passed | **30000/30000** — passed |
| `test_plan.load`, stall duration | 60.0 s | 60.0 s | passed | **60.0 s** — passed |
| `test_plan.load`, backlog clears | 18512 ≥ 18018 | 18367 ≥ 18014 | passed | **18366 ≥ 18003** — passed |
| AC-12, write lag ≤ 2.0 s, steady windows | 26171/26484 = 98.8% | 26038/26625 = 97.8% | passed | **26617/26617 = 100.0%** — passed |
| `test_plan.chaos` cl. 5, bodies swept | 5000 | 5000 | passed | **5000** — passed |
| **Recovery wall time, ~3,360 rows** | **16.53 s** | **17.79 s** | **7.48 s** | **7.51 s** |
| **`performance_requirements`, rec/sec** | **212** | **189** | **450** | **448** — **FAILED** |

Both 03-07 runs reached the last assertion, which — by the ordering 03-06 established for exactly this
reason — means **every correctness assertion above it executed and passed.**

**Two things moved and one did not.** The recovery is **2.4× faster** (17.79 s → 7.51 s for the same
backlog), and AC-12's write-lag clause went from 97.8% to **100.0% of steady-state observations at or
below the 2.0 s edge** — every one of 26,617, where 03-06 had 587 above it. And the throughput figure
is **still under 500**: 450 and 448, reproduced to within half a percent across two independent
full-length runs, which is not a flake.

## The blocker, and why it is a different blocker from 03-06's

**The N+1 is gone and the requirement is still red end to end.** Those are both true, and the reason
they can both be true is that **there are now two measurements of one requirement and they disagree.**

`performance_requirements`' `condition` is *"batched inserts, bodies included, single writer"*. That is
`write_records`, and measured there it is **1,984–2,004 records/sec — four times the target**. Its
`source` argues the margin from backlog recovery, and the load run derives the figure from the
recovery leg, where it is **448**. The recovery leg is not only the writer: it contains the broker, the
drain's `WINDOW_MS = 250` collection floor (~1.75 s of the 7.51 s across seven windows), the publisher
sharing one event loop with the drain, and the test's own backlog poll — a `count(*)` over a table
holding up to 35,000 rows, every 100 ms, through a `NullPool` engine, on that same loop. **At 189
records/sec that overhead was noise. At 448 it is not.**

**`docs/brainstorm/open_questions/OQ-085.md` is created** and states the conflict, the measured
ceiling, what was tried, what remains, and the question for a human: *is the 500 figure right, or is
the architecture* — and specifically, **which of the two measurements the requirement is about.** It is
the only `docs/` write this plan made, and it edits no spec.

**Three things were refused, and each would have made the number go green.**

- **Lowering `RECOVERY_RECORDS_PER_SECOND`.** It is `performance_requirements`', not the test's.
- **Fixing the instrument in the same change as the thing it measures.** Reading the backlog through a
  pooled engine, polling less often, or deriving the figure from `prope_call_ledger_written_total`
  instead of a `count(*)` would each move the number without touching the writer. All three are named
  in OQ-085 and none was applied, because changing the instrument alongside the subject is how a
  measurement stops being one.
- **Reporting the isolated 2,004 as *the* answer.** It is the figure that matches the lock file's
  stated `condition` and it is reported first — but the assertion that exists reads the recovery leg,
  and it is red, and this summary says so in the same breath.

## The gate, observed

```
uv run pytest tests/integration/test_price_resolution_is_batched.py -q
6 passed, 1 warning in 9.81s
```

```
uv run pytest -q
414 passed, 1 skipped, 1 warning in 205.84s (0:03:25)
```

```
uv run ruff check src/ tests/ alembic/
All checks passed!
```

**406 passed + 1 skipped before this plan, 414 passed + 1 skipped after** — eight tests added, none
changed, none removed, and the one `s` is still the marked run. `uv run ruff format --check` is not
run: it fails repo-wide on the pre-existing 120-vs-100 column disagreement recorded as Broken Window
#1, it is not a gate, and it is not this plan's to fix.

```
git status --porcelain docs/modules docs/architecture docs/adr
```

produces no output. The only `docs/` write is the newly created
`docs/brainstorm/open_questions/OQ-085.md`.

## Deviations from Plan

### 1. `src/prope/call_ledger/repricing.py` was edited outside `files_modified`

**Declared drift, closed by rewriting a paragraph. No code changed in that file** — `git diff` shows
the module docstring only. Its *"One cost function, not two"* paragraph said `resolve_price` and
`compute_cost` are *"imported from the module the writer uses"*, which after D-280 reads as a claim
that the writer still calls `resolve_price`. It does not. The paragraph now says what is true, and
adds why the per-candidate resolver stays in the reprice job: that job is operator-initiated and rare
rather than on the write path, and no `performance_requirements` row governs it.

This is the **fourth** instance of a rule phase 3 has now recorded three times (`state.publisher` in
03-01, `occurred_at` in 03-02, `ceiling_failed_open_total` in 03-03): *a plan that retires or
re-routes a symbol should grep for the symbol's name in prose as well as in code before writing
`files_modified`.* The standing grep list gains `grep -rn "resolve_price" src/ tests/`.

### 2. Two comments in `tests/load/test_fifty_rps_for_ten_minutes.py`

The file's `files_modified` entry exists **only** for these. `git diff` on it shows changes inside a
docstring and a comment and nothing else: `RECOVERY_RECORDS_PER_SECOND = 500.0` is untouched, the
assertion at the end of the test is untouched, and no threshold, constant or assertion in that file
moved. Both comments described the per-record lookup as a live fact.

## What did not go as planned

**Nothing surprised, and that is worth one sentence rather than a section.** The `unnest`-of-two-arrays
join was spiked against the real container before the plan was written, because a plan written around
a statement that does not run is worse than no plan; asyncpg binds a Python `list[str]` to a
`CAST(... AS text[])` parameter without help, and the rows came back grouped and ascending as the
`ORDER BY` says. The three counting tests, the effective-dating test and the equivalence test were all
green on their first execution.

**The one thing worth recording is host noise, because it is visible in the numbers above.** The
isolated measurement was taken three times after the change and read 2,004, 875 and 1,984 records/sec.
The middle reading is not a property of this code: the **unknown-usage** control in the same run —
which issues no price statement at all, before or after — fell from ~4,700 to 1,450 in exactly the
same execution, so the whole host was three times slower for that minute. The median is reported
beside the spread rather than the best figure alone.

## For the reviewer and for later phases

- **`pricing.py` now holds two implementations of one rule**, deliberately (D-283), and
  `test_the_batch_resolver_and_resolve_price_agree` is what stands in for them being one function. The
  delete-together instruction is written at **both**. Collapsing them costs one plan and stays
  available; `deferred-items.md` Part 11 says exactly what that plan would have to touch.
- **`repricing.reprice_unpriced` still issues one round trip per candidate** — the same N+1 shape,
  deliberately not fixed here. `load_price_book` takes a set of keys and the candidate rows already
  carry theirs, so the fix is small whenever somebody measures that job.
- **`tests/architecture/test_no_sql_interpolation.py` was not touched in either direction.** The
  `text()` count under `src/prope` **rose** from 17 to 18 — this change adds a statement rather than
  removing one — so there was no pressure on the `found >= 5` floor and `ALLOWED` is still
  `frozenset()`. The prohibition against raising that floor to compensate never came up.
- **A future test asserting "a structurally invalid batch issues no statement at all" would now be
  false**, by D-284, and the reason it is a gain rather than a regression is written at the call site:
  one statement is one `READ COMMITTED` snapshot for the whole batch, where N statements were N.
- **Do not simplify `unnest(a, b)` into two `= ANY(...)` predicates.** It is a cross product and it
  would price a call from another provider config's row — plausibly, silently, and with a stored cost
  nobody would question.
