---
phase: 01-data-model-pricing-and-retention
plan: 04
subsystem: call-ledger
tags: [repricing, retention, adr-0019, adr-0018, adr-0040, oq-c, oq-d, a7, rls, privileges]
status: complete

requires:
  - "01-01 — the Alembic chain, the three roles, workspace_transaction(), the testcontainers rig, ix_call_record_unpriced_worklist"
  - "01-02 — ledger.call_body with its (workspace_id, expires_at) index and its SELECT/INSERT/DELETE grant, ledger.price_table"
  - "01-03 — resolve_price, compute_cost, write_records, the three cost states, tests/unit's draft builders and fixture calendar"
provides:
  - "`prope.call_ledger.repricing.reprice_unpriced` — CL-05: fills only rows whose cost_status is unpriced, resolving each at its own created_at through the writer's own cost path"
  - "`prope.call_ledger.repricing.RepriceResult` — repriced / still_unpriced, so 'repriced 0' and 'found nothing to look at' are different answers"
  - "`prope.call_ledger.retention.delete_expired_bodies` — CL-08: the bounded-chunk delete, one workspace_transaction per chunk, cut-off passed in"
  - "`prope.call_ledger.retention.DELETE_CHUNK` / `.DEFAULT_CHUNK_SIZE` / `.ChunkObserver`"
  - "14 new tests against a live PostgreSQL 17, five guarantees mutation-verified"
affects:
  - "Phase 2's worker — delete_expired_bodies is the callable a timer will invoke; it takes one workspace id and enumerates nothing"
  - "Phase 2/3's operational surface — reprice_unpriced is the callable behind whatever route exposes repricing; no route is built here"
  - "Phase 7 (access schema) — the cross-tenant sweep still has no mechanism; OQ-C is carried forward unanswered"
  - "Any later phase that revisits call_body grants — A7's concurrency-safety property is unbought, and the reason is a deliberate missing UPDATE privilege"

tech-stack:
  added: []
  patterns:
    - "A guarantee lives in a status predicate carried by BOTH the selection and the update's own where clause; the second copy is load-bearing and was shown to be so"
    - "`now` is a parameter, in Python and in the SQL. No clock is read on either side of the retention predicate"
    - "A production signature carries one optional observation seam (`on_chunk`, default None) because the property it proves — one transaction per chunk — is invisible once the call has returned"
    - "A privilege refusal discovered during implementation is reported and designed around, never resolved by widening the grant that produced it"
    - "Every retention assertion is a direct query as prope_migrate; an application session in the wrong tenant returns zero rows whether or not the delete worked"

key-files:
  created:
    - .planning/phases/01-data-model-pricing-and-retention/.plan-04-base-sha
    - src/prope/call_ledger/repricing.py
    - src/prope/call_ledger/retention.py
    - tests/integration/test_reprice_only_unpriced.py
    - tests/integration/test_body_retention_delete.py
  modified: []
  deleted: []

decisions:
  - "`FOR UPDATE SKIP LOCKED` (A7) is NOT in the chunk statement. A locking select requires the UPDATE privilege, and prope_app holds SELECT/INSERT/DELETE on call_body and deliberately not UPDATE. Proven live: the statement with the clause returns `permission denied for table call_body`; the identical statement without it succeeds. A7 makes the lock optional, so it was dropped rather than bought by widening a grant that exists to keep stored bodies immutable to the runtime role."
  - "The bind parameter for the cut-off is named `cut_off_at`, not `cut_off`. The plan's own source gate refuses the two-character sequence f-quote, and `\"cut_off\"` contains it. A name ending in `f` before a quote is unspellable in this module."
  - "CL-08 is ticked on the reading that its traced acceptance criterion AC-8 is met in full. No scheduler and no cross-tenant sweep ship (OQ-C); that is stated in the requirements section rather than implied, so a reviewer can disagree with the reading."
  - "The explicit `workspace_id` predicate in DELETE_CHUNK is a plan-shape device, not the tenant guarantee. Mutation E removed it and the cross-tenant test still passed, because the RLS policy is the enforcement. This is recorded rather than glossed: no behavioural test in this phase proves the predicate, only the acceptance-criterion grep does."
  - "Repricing raises on a candidate that prices to zero, matching the writer's 01-03 refusal. Neither storing the zero nor leaving the row on the worklist would be true."

metrics:
  duration: ~45m
  completed: 2026-08-10

actuals:
  tokens: 11700
  tasks: 2
  commits: 2
---

# Phase 01 Plan 04: Repricing and body retention — Summary

A price row added after the fact gives a previously-unpriced call the cost it
was owed and leaves an already-priced call byte-identical — proved by handing
the reprice run a newly-applicable, ten-times-dearer row and comparing the
priced call's whole tuple across it. Bodies past their retention window are gone
from `ledger.call_body` by direct query as the owner role while all seventeen
`call_record` rows stand unchanged, and the delete releases its locks between
chunks — proved from **inside** a running loop, not after it returned.

## What was built

**`repricing.py` — one predicate, carried twice.** `reprice_unpriced(session, *,
workspace_id, provider_config_id=None, upstream_model=None)` selects rows whose
`cost_status` is the unpriced value, resolves each at **that row's own
`created_at`** through the writer's `resolve_price`, and computes with the
writer's `compute_cost`. The same predicate is repeated inside the update's
`WHERE`, so a row that changed state between the select and the update is not
overwritten with a second opinion; the count returned is `rowcount`, i.e. what
the engine says changed rather than what a branch intended. The two optional
narrowing parameters each appear once, inside a `COALESCE` against their own
column, so "do not narrow" needs no second statement and no type cast.

**`retention.py` — one transaction per chunk, and a seam to prove it.**
`delete_expired_bodies(sessionmaker, workspace_id, *, now, chunk_size=5000,
max_chunks=None, on_chunk=None)`. Each iteration opens its **own**
`workspace_transaction`, runs one chunk, commits, and only then awaits
`on_chunk` — outside any open transaction, which is the entire point. The loop
ends on a short chunk or on `max_chunks`. `DELETE_CHUNK` projects `ctid` and
nothing else, so the one statement in the MVP that touches this table for
anything but an insert cannot become its reader; its `workspace_id` predicate is
bound, never assembled.

## Verification — what actually ran

Every row is the output of a command executed in this session.

| Check | Result |
|-------|--------|
| `uv run pytest tests/integration/test_write_path.py -q` (Task 1 precondition) | **12 passed** |
| `docker info` (Task 1 precondition) | exit 0 |
| `uv run pytest tests/integration/test_reprice_only_unpriced.py -x -q` | **6 passed** |
| `uv run pytest tests/integration/test_body_retention_delete.py -q` | **8 passed** |
| `-k no_zero_survives_repricing` | **1 passed, 5 deselected** — exactly one |
| `-k chunking` | 1 passed, 7 deselected |
| `-k per_chunk` | **1 passed, 7 deselected** — exactly one |
| `-k default_path` | 1 passed, 7 deselected |
| `uv run pytest -q` (whole suite) | **81 passed** — Waves 1–3's 67 among them |
| `uv run ruff check src/ tests/ alembic/` | All checks passed |
| `grep -c 'unpriced' src/prope/call_ledger/repricing.py` | 16 (≥ 2 required) |
| `grep -nE 'cost IS NULL\|cost is None' repricing.py` | no match (exit 1) |
| `grep -nE 'request_body\|response_body' retention.py repricing.py` | no match (exit 1) |
| `grep -nE 'CURRENT_TIMESTAMP\|datetime\.now\(' retention.py` | no match (exit 1) |
| `grep -rnE 'list_workspaces\|prosecdef\|CREATE FUNCTION\|APScheduler\|celery\|crontab' retention.py` | no match (exit 1) |
| `grep -nE 'f"\|f'"'"'\|%s\|\.format(\|\+ workspace_id' retention.py` | no match (exit 1) — **after renaming the bind parameter**, see deviations |
| `grep -c 'workspace_id' retention.py` | 5 (≥ 1 required) |
| `inspect.getsource` gate — `compute_cost` and `resolve_price` in repricing | exit 0 |
| `inspect.signature` gate — `now`/`chunk_size`/`max_chunks`/`on_chunk`, `on_chunk` default `None` | exit 0 |
| `inspect.getsource` gate — `workspace_transaction` inside `delete_expired_bodies` | exit 0 |
| `git cat-file -e "$(cat …/.plan-04-base-sha)^{commit}"` | exit 0 (`33e24f9`) |
| `docs/` since the fixed phase base `b27b58a` | 0 committed, 0 uncommitted, 0 untracked |
| `alembic/versions/` since **this plan's** base `33e24f9` | 0 committed, 0 uncommitted, 0 untracked |
| zero `SECURITY DEFINER` routines in `ledger` | asserted by the pre-existing `tests/architecture/test_schema_invariants.py`, green in the 81 |

### The mutation checks — because both task's tests passed on first run

Both files got a genuine RED, but only `ModuleNotFoundError` — an import error I
watched rather than a behavioural failure. So five guarantees were broken on
purpose and the failures observed. Both modules were restored from backups and
`diff -q` confirmed byte-identical restoration before the final suite run.

| # | Mutation | Result |
|---|----------|--------|
| A | repricing's selection filtered on the cost column being absent instead of on the status | `test_a_not_applicable_call_is_still_not_applicable_after_repricing` and `test_no_zero_survives_repricing_of_a_mixed_batch` **both failed** — `ValueError: cal_…X3 reprices to 0E-10 … None input and None output tokens`. The widened filter reaches the not_applicable rows exactly as ADR-0019's reasoning predicts |
| B1 | status predicate removed from the **select only**, kept in the update | Tests 3 and 6 failed as above — but `test_an_already_priced_call_is_unchanged_field_for_field` **still passed**. The update's own copy of the predicate is genuinely a second line of defence, not decoration |
| B2 | status predicate removed from **both** statements | `test_an_already_priced_call_is_unchanged_field_for_field` failed: `assert 2 == 1 … RepriceResult(repriced=2)`. The already-priced row was rewritten, and the test caught it |
| C | retention's loop wrapped in **one** transaction across all chunks | `-k per_chunk` failed with **`got [12, 12, 12]`** — the exact signature the plan predicted, and it failed loudly rather than hanging |
| D | `expires_at <= :cut_off_at` weakened to `<` | `test_a_body_expiring_exactly_at_the_cut_off_goes_and_a_microsecond_later_stays` failed: `assert 0 == 1` |
| E | explicit `workspace_id` predicate removed from `DELETE_CHUNK`, policy untouched | `-k another_workspaces` **still passed**. Reported, not hidden: the RLS policy is the tenant enforcement and the explicit predicate is the index-scan device. See the caveat below |

Mutation C is the most valuable result here. It is the only evidence in the
phase that OQ-D's adopted reading holds, and it discriminates the two loop
shapes exactly as designed — a post-return check after `max_chunks=1` would
have passed under both.

### The must-have truths, and what proves each

| Truth | Proved by |
|-------|-----------|
| A newly-added earlier price row gives a previously-unpriced call its cost, currency, `price_row_id` and `priced` status | `test_a_previously_unpriced_call_gains_a_cost_when_a_price_row_arrives` — cost compared against `compute_cost`'s own answer, not a number typed into the test |
| An already-priced call that a new row supersedes is **byte-identical** — the whole tuple, not the cost column | `test_an_already_priced_call_is_unchanged_field_for_field`: the day-3 row is ten times dearer and *would* apply to a day-5 call; a second call **is** repriced in the same run, so "nothing moved" cannot be explained by "nothing ran". Mutation-verified (B2) |
| A not_applicable call is still not_applicable after repricing | `test_a_not_applicable_call_is_still_not_applicable_after_repricing` — whole-tuple comparison, with a price row seeded so the row is visibly not skipped for want of one. Mutation-verified (A) |
| The filter is the status, never a test on the cost column | Source gate (`! grep 'cost IS NULL\|cost is None'`) plus mutation A, which shows what the wider filter actually does |
| A repriced cost is byte-identical to what the writer would have produced | `assert after["cost"] == compute_cost(300, 150, PRICE_FOR_CHECK) == EXPECTED_COST` — the same `compute_cost` the writer calls, imported not restated (`inspect.getsource` gate) |
| Expired bodies are gone by direct query as `prope_migrate`; their `call_record` rows are intact and unchanged | `test_expired_bodies_are_gone_and_their_call_records_are_intact` — the 12 records read whole **before** and **after** and compared, the 5 unexpired bodies named by id, all 17 records still counted |
| The chunk loop terminates on a short chunk and honours `max_chunks` | `test_chunking_runs_three_chunks_and_a_bounded_run_stops_early` — `max_chunks=1` returns 5 and leaves 7; the unbounded remainder records chunks `[5, 2]` |
| Each chunk runs in its own transaction, observed from OUTSIDE an IN-FLIGHT run | `test_per_chunk_transactions_are_visible_outside_the_running_loop` — `on_chunk` opens a fresh `migrate_engine` connection and records `[7, 2, 0]`. Mutation-verified (C): the loop-wide shape records `[12, 12, 12]` |
| `on_chunk` is genuinely optional | `inspect.signature` gate (`default is None`) plus `test_default_path_without_a_callback_deletes_exactly_the_same_rows`, which asserts the same unbounded run with no callback returns 12 and leaves exactly the named survivors |
| Another workspace's equally-expired body survives | `test_another_workspaces_equally_expired_body_is_untouched` — B seeded first, so a tenant-blind delete would take it. **Caveat below:** this proves the policy, not the explicit predicate |
| The cut-off is an argument and no clock is read | Source gate on `retention.py`; every date in the tests is fixture-calendar arithmetic. No time-travel library entered the build |
| Workspace-scoped, enumerating nothing; no fifth definer-privilege routine | Source gate refusing the enumerator, routine-creation and timer-library names; `test_schema_invariants.py`'s existing zero-`prosecdef` assertion green in the full suite |
| The prohibition: no read path for `ledger.call_body` | `DELETE_CHUNK` projects `ctid`; source gate refuses either body column's name in **both** new modules; no route, accessor, repository helper or cross-module join was added anywhere |

## Deviations from Plan

### 1. [Rule 3 — Blocking issue, and a real finding] `FOR UPDATE SKIP LOCKED` was removed, and the grant was NOT widened

- **Found during:** Task 2, first run. `asyncpg.exceptions.InsufficientPrivilegeError:
  permission denied for table call_body`.
- **Diagnosis, run rather than assumed.** A throwaway probe (since deleted)
  established three facts on the live engine: `prope_app`'s grants on
  `ledger.call_body` are exactly `['DELETE', 'INSERT', 'SELECT']`; the chunk
  statement **with** the locking clause raises `InsufficientPrivilegeError`; the
  byte-identical statement **without** it succeeds. PostgreSQL requires the
  `UPDATE` privilege for a locking select, and this table withholds it so that
  the role serving traffic cannot alter a stored body.
- **Fix:** the locking clause was dropped. A7 states the lock is "a safety
  improvement, not a requirement", so this is a plan-sanctioned removal rather
  than an invention. The grant was **not** widened — that is exactly the move
  the carry-forward warned against, and granting `UPDATE` on `call_body` to buy
  a concurrency nicety would trade an immutability guarantee for it.
- **What was lost, stated plainly:** two concurrent runs of this job can now
  contend on the same rows instead of stepping around each other, and the lock
  file's chaos plan (running the delete during peak writes) loses the property
  that would have made it trivially safe. Nothing in the MVP runs two — there is
  no scheduler — so the loss is latent. Restoring it is a grant decision for a
  later phase, recorded in the module's own comment beside the statement.
- **Files modified:** `src/prope/call_ledger/retention.py`
- **Commit:** `b79d3ab`

### 2. The cut-off bind parameter is `cut_off_at`, not `cut_off`

The plan's own source gate refuses the two-character sequence *f* followed by a
quote, in order to ban f-strings. `{"cut_off": …}` contains it, because the word
ends in `f`. The parameter was renamed rather than the gate weakened; any
identifier ending in `f` immediately before a quote is unspellable in this
module, which is worth knowing before the next edit.

### 3. Eight retention tests and six repricing tests, not the six-and-six minimum

Two extras, both discriminators the plan's list would not have produced:
`test_a_second_run_with_no_new_price_rows_reprices_nothing` (idempotence at the
repricing end) and `test_the_default_chunk_size_is_the_documented_five_thousand`
(A6 is a flagged, tunable judgement, so pinning the number makes changing it a
visible act).

### 4. A caveat on the explicit tenant predicate, surfaced rather than glossed

Mutation E removed `workspace_id = :ws` from `DELETE_CHUNK` and the cross-tenant
test **still passed**, because the RLS policy is the enforcement and the session
carries exactly one workspace. That is the correct architecture — defence in
depth, with the policy load-bearing — but it means **no behavioural test in this
phase proves the explicit predicate exists.** Only the acceptance-criterion grep
does. The predicate's stated purpose is the `(workspace_id, expires_at)` index
scan, and that purpose is unasserted here: no `EXPLAIN` is run, and at 17 seeded
rows the planner would sequential-scan regardless. Recorded so a reviewer does
not read the passing cross-tenant test as covering it.

No architectural change was needed and no checkpoint was reached.

## Requirements — what was ticked and what was not

**Ticked: CL-05 and CL-08.**

- **CL-05** — "Repricing gives a previously unpriced call its cost and leaves an
  already-priced call untouched." Both clauses are code, both are asserted
  separately, and both are mutation-verified. The second clause is the one worth
  defending: it is proved against a reprice run that had a newly-applicable,
  ten-times-dearer price row available to it and that demonstrably did work in
  the same pass, so "unchanged" cannot be satisfied by "nothing happened".
- **CL-08** — "Call bodies past their retention window are deleted while their
  call records stay intact." Both halves are asserted by direct query as
  `prope_migrate`: the bodies are absent to a connection that can see
  everything, and the records are compared whole before and after. **The tick
  rests on the reading that CL-08's traced acceptance criterion — call-ledger
  AC-8 in the traceability table — is met in full**, and every clause of AC-8 is
  testable and tested against a single seeded workspace. What is **not** built,
  stated so a reviewer can disagree with the tick: there is no scheduler (the
  `worker` process arrives in Phase 2) and no cross-tenant sweep (OQ-C — the
  enumerator ADR-0051 designates lives in a schema that does not exist until
  Phase 7). Nothing in the running system calls this function today.

**Not ticked: CL-11**, and it is not this plan's. Its outstanding clause — "the
unknown count is reported alongside the total" — is `get_run_totals`, which the
ROADMAP assigns to Phase 2. 01-03 declined to tick it for the same reason and
nothing here changes that; the storage shape that makes the count computable was
already delivered and asserted in Wave 3.

## Open questions — status after this plan

- **OQ-D — answered, and answered behaviourally.** One transaction per chunk,
  each carrying exactly one workspace's tenant context. Established by a single
  test observing an unbounded three-chunk run from a connection the loop does
  not hold, and mutation-verified against the loop-wide shape it was designed to
  discriminate. The ADR was not edited.
- **OQ-C — untouched and still open.** No enumerator, no scheduler, no fifth
  definer-privilege routine. `delete_expired_bodies` takes one workspace id.
  Carried upstream exactly as the plan directs.
- **OQ-B** — unchanged; the retention window is still the writer's keyword
  argument. Retention reads no window at all: it takes the cut-off instant.
- **OQ-A** — still holding. No `::uuid` cast entered any SQL here.
- **OQ-E** — untouched.

**One new question, raised by implementation rather than by planning:** the
retention job cannot take the row lock A7 proposed without an `UPDATE` privilege
on `ledger.call_body` that the grant matrix deliberately withholds. Whether the
concurrency-safety property is worth a narrowed grant (for example `UPDATE` on
no columns, or a separate role for the job) is a real decision, and it is
recorded in `retention.py` beside the statement rather than resolved here.

## Known Stubs

None. Both functions are wired and exercised against a live engine.
`delete_expired_bodies` has no caller in the running system — that is its
correct Phase 1 form, stated as the tick's caveat above and assigned to Phase
2's `worker` by the ROADMAP, not a stub: fourteen tests execute it and assert
against the data it leaves behind.

## Threat Flags

None. Every threat in the plan's register is addressed as dispositioned, with
one qualification recorded rather than hidden:

- **T-01-20** (repricing widening its filter) — status predicate in both
  statements, source gate refusing the cost-absence test, whole-tuple comparison
  of the priced row, not_applicable row asserted unchanged. Mutations A, B1, B2.
- **T-01-21** (the retention statement becoming a body reader) — `ctid` only;
  source gate refuses either body column's name in both new modules; no
  accessor, route, whole-row projection or cross-module join created.
- **T-01-22** (an unbounded delete) — bounded chunks, default 5,000; one short
  transaction per chunk, mutation-verified (C). **Qualification:** the
  `SKIP LOCKED` half of this mitigation is not shipped — see deviation 1. Locks
  are still released between chunks, which is the load-bearing half; what is
  missing is the property that made concurrent runs step around each other.
- **T-01-23** (a fifth definer-privilege routine) — none created; source gate
  plus the existing live zero-`prosecdef` assertion, green in the full suite.
- **T-01-24** (a job that runs cleanly and deletes nothing) — every assertion is
  a direct query as `prope_migrate`, never through a session that could filter.
- **T-01-25** (a cross-tenant delete) — one workspace per transaction, the
  policy's `USING` clause, and an explicit bound predicate beside it. The test
  proves the policy; the predicate is proved only by the grep (deviation 4).

No file created here introduces network surface, an auth path, file access, or a
trust-boundary schema change outside that register. **No migration was added**
and no file under `docs/` was touched — both verified against fixed bases.

## Notes for the next plan

- **`delete_expired_bodies` has no caller.** Phase 2's `worker` owns the timer.
  It takes one workspace id; whoever adds the sweep needs OQ-C answered first,
  and the answer is not a fifth definer-privilege routine.
- **`reprice_unpriced` does not commit**, like `write_records`. The caller's
  `workspace_transaction()` owns the boundary, which is what makes a raise
  part-way through leave the whole pass unapplied.
- **Repricing is a Python loop with one `resolve_price` per candidate**, served
  by the partial unpriced index. Correct and clear at Phase 1 volumes; the batch
  `DISTINCT ON` form is in the research if a later phase needs it.
- **`prope_app` has no `UPDATE` on `call_body` and no `DELETE` on
  `call_record`.** Both were confirmed live this session. Anything that wants to
  lock a body row, or to remove a call record, is blocked by design and should
  be surfaced rather than granted around.
- **The fixture calendar now carries a retention cut-off**, `day(66)`, chosen so
  expired bodies sit 31 days past it with the writer's default 30-day window.

## Self-Check: PASSED

All 5 created files verified present on disk. Both commits (`ef214dd`,
`b79d3ab`) verified present in `git log --oneline --all`.
