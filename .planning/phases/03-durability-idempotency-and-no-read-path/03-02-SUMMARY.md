---
phase: 03-durability-idempotency-and-no-read-path
plan: 02
subsystem: backend
tags: [postgres, sqlalchemy, upsert, idempotency, rabbitmq, prometheus, durability, tenancy]

# Dependency graph
requires:
  - phase: 01-data-model-pricing-and-retention
    provides: "write_records and its four refusals, ledger.call_record's call_id primary key, ledger.call_body's no-UPDATE grant, ledger.workspace_spend's one-currency upsert, models.py's six Core Table declarations, and the session-scoped PostgreSQL 17 rig"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 02
    provides: "prope.call_ledger.drain — the window/group/write loop, classify_write_failure, _parse's envelope gate, and _retry_group_one_at_a_time"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 01
    provides: "all eighteen metrics defined at import (duplicate_call_id_total, redelivered_total, missing_version_id_total, unpriced_total, unknown_usage_total, write_lag_seconds, WRITE_LAG_BUCKETS); HandoffItem.occurred_at stamped in enqueue(); tests/broker/_helpers.py::counter_value"
provides:
  - "writer.UPSERT_CALL_RECORD — INSERT … ON CONFLICT (call_id) DO NOTHING … RETURNING call_id, the first Core construct anywhere in src/"
  - "writer.UPSERT_CALL_BODY — the same clause on ledger.call_body, plus D-34's inserted-set filter"
  - "WriteResult.duplicates — rows offered minus call_ids returned, the fifth count"
  - "duplicate_call_id_total, missing_version_id_total, unpriced_total and unknown_usage_total — four increment sites inside write_records, so all three callers get them for free (INT-019)"
  - "redelivered_total — incremented in drain._parse from AbstractIncomingMessage.redelivered, the broker's own view"
  - "write_lag_seconds observed on the drain's committed path, per record, clamped"
  - "tests/broker/test_redelivery_leaves_the_total_unmoved.py — SC2, over both mechanisms"
affects: [03-04-metrics-route-and-alerts, 03-06-load-and-chaos, 16-18-evaluation, 19-21-gateway]

actuals:
  tokens: 96000
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns:
    - "A statement whose OUTPUT is the control flow: the returned call_id set decides what the aggregate is built from, so idempotency is a property of the SQL rather than of an error handler"
    - "Two passes over one batch, split because validation is about what the caller offered and aggregation is about what the table gained"
    - "The deliberate ABSENCE of an argument documented at the call site, because an absence has no line of its own to read"
    - "A counter removed, with the limit of its substitute signal written at the removal site rather than in a plan"
    - "Two counters at two layers measuring the same phenomenon from opposite ends, neither derived from the other, because the alert reads them together"
    - "A test whose ordering IS the assertion — the rows are made durable BEFORE the redelivery lands, because otherwise the test passes against a writer with no idempotency in it"

key-files:
  created:
    - tests/broker/test_redelivery_leaves_the_total_unmoved.py
  modified:
    - src/prope/call_ledger/writer.py
    - src/prope/call_ledger/domain.py
    - src/prope/call_ledger/drain.py
    - src/prope/call_ledger/envelope.py
    - tests/integration/test_write_path.py
    - tests/broker/test_drain_failure_classification.py

key-decisions:
  - "The mixed-currency refusal stayed in pass 1, keyed on period_month(created_at) and guarded by `cost is not None` — reproducing the OLD keying exactly, because the batch-wide {r.currency} set that reads naturally would have tightened write_records with no test going red"
  - "bodies_written now counts the SURVIVING bodies rather than the bodies built, because the type's own docstring rule is that a count says what it is derived from and the two numbers differ the moment a redelivery arrives carrying a body"
  - "unpriced_total and unknown_usage_total count OFFERED records; only the spend aggregate is built from the inserted set. They describe what the caller sent, and a redelivered unpriced record is still an unpriced record nobody has fixed"
  - "A draft with no provider_config_id renders as the label string \"None\" rather than an invented \"unknown\" — a fourth value one line from the third is how a vocabulary stops being one"
  - "classify_write_failure's ValueError bullet went from four refusals to five (D-40's version_id refusal) and its IntegrityError bullet was rewritten; the body and the PERMANENT default are untouched"
  - "tests/broker/test_drain_failure_classification.py:199-244 was left exactly as it is — its two consumers are raw queue.iterator() consumers that never reach _parse, so a redelivered_total assertion there would fail as written"
  - "src/prope/call_ledger/envelope.py was edited outside files_modified (declared drift): occurred_at's docstring said 'nothing in the write path reads this field' and the drain now does"

patterns-established:
  - "A regression test named for the trap rather than for the API — five records and not one, because sort_by_parameter_order raises only when a batch has a conflicting row and a single-record test would never see it"
  - "A negative control that provokes the refusal the code no longer relies on: the raw INSERT is issued by hand and PostgreSQL still refuses it, which is what makes 'write_records raised nothing' a claim about the STATEMENT rather than about the error handling around it"
  - "A removal asserted with its own positive control — the dead-letter is proved to have happened in the same test that asserts the counter did not move"

requirements-completed: [CL-02]

coverage:
  - id: D1
    description: "Re-writing a batch of records whose call_ids already exist leaves ledger.workspace_spend.call_count and total_cost exactly as they were, adds no rows, and raises nothing"
    requirement: CL-02
    verification:
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_rewriting_the_same_batch_leaves_the_workspace_total_exactly_where_it_was"
        status: pass
      - kind: integration
        ref: "tests/broker/test_redelivery_leaves_the_total_unmoved.py::test_republishing_the_same_envelopes_leaves_every_workspace_total_unmoved"
        status: pass
    human_judgment: false
  - id: D2
    description: "A batch of seven whose first five call_ids already exist adds exactly two to call_count and exactly two records' worth of cost — the assertion that also fails loudly if sort_by_parameter_order is ever reintroduced"
    requirement: CL-02
    verification:
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_a_batch_of_five_duplicates_and_two_new_records_adds_exactly_two"
        status: pass
    human_judgment: false
  - id: D3
    description: "A message redelivered after an unacknowledged consumer restart, for records the fallback already wrote directly, is acknowledged rather than dead-lettered: the DLQ depth is zero across the redelivery"
    requirement: CL-02
    verification:
      - kind: integration
        ref: "tests/broker/test_redelivery_leaves_the_total_unmoved.py::test_a_redelivery_of_records_the_fallback_already_wrote_moves_nothing"
        status: pass
    human_judgment: false
  - id: D4
    description: "prope_call_ledger_duplicate_call_id_total moves by the number of rows offered that were already present, for every caller of write_records"
    requirement: CL-02
    verification:
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_rewriting_the_same_batch_leaves_the_workspace_total_exactly_where_it_was"
        status: pass
      - kind: integration
        ref: "tests/broker/test_redelivery_leaves_the_total_unmoved.py::test_a_redelivery_of_records_the_fallback_already_wrote_moves_nothing"
        status: pass
    human_judgment: false
  - id: D5
    description: "prope_call_ledger_redelivered_total moves by the number the broker re-sent, read from AbstractIncomingMessage.redelivered, when the second consumer is the real drain"
    requirement: CL-02
    verification:
      - kind: integration
        ref: "tests/broker/test_redelivery_leaves_the_total_unmoved.py::test_a_redelivery_of_records_the_fallback_already_wrote_moves_nothing"
        status: pass
    human_judgment: false
  - id: D6
    description: "A body arriving for a call_id whose record was already written is not stored, so body_dropped_total stays reconcilable against the rows missing from ledger.call_body — with a fresh record's body beside it as the positive control"
    requirement: CL-02
    verification:
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_a_body_arriving_for_an_already_written_record_is_not_stored"
        status: pass
      - kind: integration
        ref: "tests/broker/test_redelivery_leaves_the_total_unmoved.py::test_a_redelivery_of_records_the_fallback_already_wrote_moves_nothing"
        status: pass
    human_judgment: false
  - id: D7
    description: "A batch mixing two currencies within one month is refused whole, whether or not its second-currency records are duplicates; a batch whose two currencies fall in two different months is still accepted"
    requirement: CL-02
    verification:
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_mixing_currencies_is_refused_even_when_the_second_currency_is_a_duplicate"
        status: pass
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_two_currencies_in_two_different_months_are_still_accepted"
        status: pass
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_a_batch_mixing_two_currencies_raises_rather_than_summing"
        status: pass
    human_judgment: false
  - id: D8
    description: "A source=gateway record with a NULL version_id is refused by name before the insert, increments prope_call_ledger_missing_version_id_total by exactly one, and leaves ledger.call_record unchanged"
    verification:
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_a_gateway_record_with_no_version_id_is_refused_by_name"
        status: pass
    human_judgment: false
  - id: D9
    description: "unpriced_total and unknown_usage_total move for every record OFFERED, including a redelivered copy, while the spend aggregate does not move at all"
    verification:
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_unpriced_and_unknown_usage_are_counted_for_every_record_offered"
        status: pass
    human_judgment: false
  - id: D10
    description: "prope_call_ledger_metadata_dropped_total does not move when the drain dead-letters a record or rejects an invalid envelope; the dead-letter itself is proved to have happened in the same test"
    verification:
      - kind: integration
        ref: "tests/broker/test_drain_failure_classification.py::test_a_dead_lettered_record_moves_metadata_dropped_total_by_zero"
        status: pass
      - kind: integration
        ref: "tests/broker/test_drain_failure_classification.py::test_an_invalid_envelope_dead_letters_without_opening_a_transaction"
        status: pass
    human_judgment: false
  - id: D11
    description: "write_lag_seconds is observed on the drain's production path — one observation per record after its group committed, with no negative observation reaching the histogram"
    verification:
      - kind: integration
        ref: "tests/broker/test_drain_failure_classification.py::test_write_lag_is_observed_on_the_drains_committed_path"
        status: pass
    human_judgment: false
  - id: D12
    description: "write_records still refuses a batch spanning two workspaces, an eval record carrying a body, and a priced record costing zero, and still writes nothing when it does; classify_write_failure's PERMANENT default is untouched"
    verification:
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_a_batch_mixing_two_workspaces_is_rejected_before_anything_is_written"
        status: pass
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_an_eval_draft_carrying_a_body_is_refused"
        status: pass
      - kind: unit
        ref: "tests/broker/test_drain_failure_classification.py::test_an_unrecognised_failure_defaults_to_permanent"
        status: pass
    human_judgment: false
  - id: D13
    description: "CL-11 clause 1 re-asserted across the restructured writer: an unknown-usage record stores NULL token columns and cost_status='not_applicable', never zero, through the Core upsert"
    verification:
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_an_unknown_usage_record_stores_null_tokens_through_the_core_upsert"
        status: pass
      - kind: integration
        ref: "tests/integration/test_write_path.py::test_no_zero_anywhere_in_a_mixed_batch_of_all_three_cost_states"
        status: pass
    human_judgment: false
  - id: D14
    description: "D-34 means a body arriving after a timed-out confirm — where the fallback already wrote the record without it — is discarded rather than stored, permanently"
    verification: []
    human_judgment: true
    rationale: "The mechanical half IS asserted (no call_body row appears, with a positive control). Whether keeping body_dropped_total reconcilable against ledger.call_body is worth that body is a product judgement, not a property a test can settle. It is the plan's first <human-check>."
  - id: D15
    description: "CL-11's REQUIREMENTS.md row reads 'Phase 1 / Pending' while both clauses are built and green. This plan re-asserts clause 1 and does not touch the row"
    verification: []
    human_judgment: true
    rationale: "Requirement ids are stable (ORCHESTRATION §1) and re-attributing one across two phases is a bookkeeping decision only the developer may take. The recommendation is stated below; the row is untouched. Same posture Phase 1 used for CL-08."

# Metrics
duration: 75min
completed: 2026-08-11
status: complete
---

# Phase 03 Plan 02: Durability, idempotency, and no-read-path Summary

**CL-02 is closed, and it is closed against the thing it was actually about.** Five records written,
then written again, leave `ledger.workspace_spend.call_count` at five and `total_cost` byte-identical —
read back through `migrate_engine`, the owner role, subject to no policy — while
`prope_call_ledger_duplicate_call_id_total` moves by exactly five, which is what says the second write
reached the statement rather than being skipped somewhere earlier. Five records the direct-write
fallback already committed, redelivered by the broker to the real drain after their messages were left
unacknowledged, land exactly once, are **acknowledged rather than dead-lettered**, and move
`redelivered_total` by five and the workspace's total by nothing.

## Performance

- **Duration:** ~75 min
- **Tasks:** 3
- **Files created/modified:** 7 (1 created, 6 modified — one of them undeclared; see Deviations)
- **Test suite:** **326 passed**, 0 failed (312 at the 03-01 baseline; +14)

## Why the aggregate and not the row was the subject of CL-02

The plan's `<output>` requires this in the summary's own words.

`ledger.call_record`'s primary key is `call_id` **alone** (`0002_call_record.py:90`). A second row for
the same `call_id` was therefore impossible before this plan and impossible after it, with or without
an `ON CONFLICT` clause. A test asserting "the record appears once" would have passed against Phase 2's
plain `INSERT` for the same reason it passes now, and would have proved nothing.

What a redelivery actually corrupts is `ledger.workspace_spend` — the monthly aggregate maintained
**inside the writer's own transaction** (A-103) so that `check_spend_ceiling` reads one row instead of
aggregating the largest and fastest-growing table in the system. That aggregate was incremented from
the rows *offered*. So a redelivered batch of five, in the world where the record already existed,
would have added five to `call_count` and five records' worth of cost to a total that had already
counted them — silently, with every row count in the system still correct.

That is why the change is `RETURNING` and not merely `ON CONFLICT`. The conflict clause makes the
insert *survivable*; only the returned `call_id` set makes the aggregate *correct*. `write_records`'
control flow now inverts around it: pass 1 validates and prices the whole batch, the upsert runs, and
pass 2 builds the month buckets and the body rows from the returned set alone. **A plan that stopped at
`ON CONFLICT DO NOTHING` would have shipped a green suite and a broken spend ceiling.**

## What `sort_by_parameter_order` would have done, and how the absence is defended

Passing `sort_by_parameter_order=True` to the upsert's `returning()` makes SQLAlchemy select `call_id`
as a **client-side sentinel** — it is a client-supplied primary key, which is exactly the shape the
sentinel machinery looks for. At execution time the driver builds `rows_by_sentinel` and compares its
length against the batch length. `ON CONFLICT DO NOTHING` guarantees those two differ the first time a
duplicate arrives, and the driver raises:

> `InvalidRequestError: Sentinel-keyed result set did not produce correct number of rows`

**That is CL-02's own scenario turned into an exception, on the path whose entire job is to survive
it** — and it fires on the *first redelivery*, in production, having passed every single-record test.

The defence is three layers, because the absence of an argument has no line of its own to read:

1. **A named paragraph at the statement.** `UPSERT_CALL_RECORD`'s `#:` block says the flag is
   deliberately absent, says what it would do, and says why no ordering is needed — the returned ids
   are consumed as a **set** (month-bucket membership), never positionally, which is why D-33 specifies
   `RETURNING call_id` rather than `RETURNING` an index.
2. **A regression test named for the trap, with five records and not one.**
   `test_a_batch_of_five_duplicates_and_two_new_records_adds_exactly_two` writes five, then the same
   five plus two, and asserts `call_count` moved by exactly two. A single-record version of that test
   would never produce a conflicting row inside a batch and would never see the raise.
3. **A grep-able acceptance criterion.** `grep -c "sort_by_parameter_order=" src/prope/call_ledger/writer.py`
   returns **0**; the string appears only inside the explanatory comment.

## The body D-34 deliberately discards, and what that buys

A `call_body` row is written only for a `call_id` **this transaction inserted**. The case that decides
it is the one ADR-0041 creates on purpose: a publisher confirm that **timed out** rather than being
refused means the broker very likely *did* get the message. The direct-write fallback writes the record
anyway — metadata only, `body=None` by D-28 — and counts one `body_dropped_total{reason="fallback"}`.
Later the broker delivers that same record to the drain, **carrying its body**.

Letting that body land would recover real data. It would also break AC-1's stated equality —
*"`body_dropped_total` equals the number missing from `ledger.call_body`"* — because the drop was
already counted, and no later reconciliation can un-count it.

**A counter that cannot be reconciled against the table is worse than a body that was already declared
best-effort (A-037).** The cost is stated at the statement and asserted end to end: a body lost to a
timed-out confirm is lost **permanently, by decision**.
`test_a_redelivery_of_records_the_fallback_already_wrote_moves_nothing` writes the five records with
`body=None` (what the fallback does) and asserts `ledger.call_body` holds **zero** rows after the
redelivery arrives carrying five of them.

## CL-11's traceability row, untouched, with the recommendation this plan makes

`REQUIREMENTS.md` files **CL-11** under *Phase 1 / Pending* while **both** of its clauses are built and
green:

- **Clause 1** — `unknown` tokens are NULL, never zero — `tests/unit/test_unknown_usage_never_zero.py`
  (Phase 1), and now also
  `tests/integration/test_write_path.py::test_an_unknown_usage_record_stores_null_tokens_through_the_core_upsert`,
  which re-asserts it **across the restructured writer**. That re-assertion is not ceremony: the
  statement that writes every call record in the system is a different construct now, and a column
  omitted from a Core insert falls to its DDL default rather than to the value the writer intended.
- **Clause 2** — the unknown count reported alongside the total —
  `tests/integration/test_run_totals.py` (Phase 2), where `seams.py:569` records that it built the
  function and deliberately claimed no requirement.

**This plan does not split the id and does not remap the row.** Requirement ids are stable
(ORCHESTRATION §1) and re-attributing one across two phases is a bookkeeping decision only the
developer may take.

**The recommendation:** tick CL-11 where it stands, in the Phase 1 row, and record in the same edit
that its second clause was discharged in Phase 2 and both were re-asserted in Phase 3. Splitting the id
would renumber a stable identifier to describe a fact a sentence describes better. It is carried as a
numbered `03-UAT.md` item — the posture Phase 1 used for CL-08.

## What shipped

**`src/prope/call_ledger/writer.py`** — the largest single diff in the phase.

- `INSERT_CALL_RECORD` and `INSERT_CALL_BODY` (both `text()`) are retired in favour of
  `UPSERT_CALL_RECORD` and `UPSERT_CALL_BODY`, `sqlalchemy.dialects.postgresql.insert()` over
  `models.call_record` / `models.call_body`. **This is the first use of the Core layer anywhere in
  `src/`.** `models.py:26-28` said its tables were *"consumed with `select()`"* and nothing consumed
  them; now one statement does, which is why `tests/architecture/test_schema_invariants.py` changed
  from insurance on an unused declaration into the guard on the statement that writes every call
  record in the system. That is written in the writer's module docstring, and `models.py` was
  deliberately **not** opened for a second copy of it.
- The four reasons `DO NOTHING` and never `DO UPDATE` are written at the statement: ADR-0019 prices
  once; `prope_app` holds no `UPDATE` on `ledger.call_body` so `DO UPDATE` would put two idempotency
  semantics in one function; only `RETURNING` over `DO NOTHING` reports which rows were new; and the
  corollary that the `SELECT` grant `0003` justifies solely as *"required alongside DELETE"* is also
  what makes `ON CONFLICT` legal on that table at all — so a future "no read path" tightening would
  break two things rather than one.
- **A zero `rowcount` here means the opposite of what it means at `UPSERT_WORKSPACE_SPEND` fifty lines
  below**, and the statement says so. There, an `ON CONFLICT … WHERE` makes a conflicting row not
  match, so nothing-updated is a genuine refusal (WARN-2 / T-02-13). Here, nothing-inserted means
  *already there*. This statement's outcome is read from the returned set and never from `rowcount`.
- `write_records` is now two passes. **Pass 1 validates the WHOLE batch** — two workspaces, an eval
  record with a body, a zero-cost priced record, the mixed-currency refusal, and D-40's new
  `version_id` refusal. **Pass 2 runs after the upsert** and touches only the returned `call_id`s.
- Four counter increment sites: `duplicate_call_id_total` (offered minus returned),
  `missing_version_id_total`, `unpriced_total{provider_config_id, upstream_model}` and
  `unknown_usage_total{source}`. They live here rather than at the three call sites so the drain, the
  fallback and `price_usage` all get them for free — INT-019's *"the same upsert INT-018's drain
  uses"*, read as an instruction about metrics too.
- The module docstring's *"emits no log and no metric at all"* sentence is replaced with what is now
  true: **four counters and no log**, none of them carrying a body-shaped label, so A-046 still holds.
  The rejected alternative (a typed error raised and counted at three call sites) is recorded in one
  line.

**`src/prope/call_ledger/domain.py`** — `WriteResult.duplicates`, fifth field, default `0`, with the
docstring saying what it is derived **from** (rows offered minus `call_id`s returned) rather than what
it means. `bodies_written` now counts the bodies that survived D-34's filter, for the same rule.

**`src/prope/call_ledger/drain.py`** —

- Both `metadata_dropped_total.inc()` calls removed (`_parse`, `_retry_group_one_at_a_time`), with the
  argument **and its limit** written at both sites: a dead-lettered record is on
  `prope.call_record.dlq`, `dlq_depth > 0` is the substitute signal, and `dlq_depth` is a **gauge**
  behind a 30-day TTL, so it can never answer *"how many have ever gone there"*. The durable record of
  the event is a log line, and ADR-0030 caps container logs. **Do not close that gap with a nineteenth
  metric** is written at the removal.
- `redelivered_total` incremented in `_parse` from `message.redelivered`, before the envelope gate, so
  a message the broker re-sent is counted whether or not its envelope validates. Why it is a
  *different* counter from `duplicate_call_id_total` is written at the increment.
- `classify_write_failure`'s `IntegrityError` bullet rewritten: the unique-violation case it named as
  *"a named Phase 2 gap"* cannot occur any more, so what reaches the branch now is a CHECK the record
  violates. The branch stays `PERMANENT`; **the function body is unchanged** and
  `test_an_unrecognised_failure_defaults_to_permanent` passes unmodified. The `ValueError` bullet went
  from four refusals to five.
- `write_lag_seconds` observed in `_write_group`, per record, immediately after the commit, clamped
  with `max(0.0, …)`. **On the production path and deliberately not behind `on_window`** — a metric is
  not an observation seam, and behind that hook it would be absent in the one process the alert reads
  it from. The module docstring now declares the clock read, which is the convention
  `retention.py`/`writer.py`/`worker.py`/`api.py`/`enqueue.py`/`fallback.py` all follow.

**`tests/broker/test_redelivery_leaves_the_total_unmoved.py` (new)** — four tests. Mechanism 1
re-publishes the identical envelopes (deterministic, and the drain cannot tell the difference) and
asserts all four of: five rows, an identical spend row, `duplicate_call_id_total` +5, and an empty DLQ
— plus workspace B's row as the cross-workspace control. Mechanism 2 is SC2's real shape. A third test
is the **negative control** for both: it issues the raw `INSERT` the writer no longer uses and confirms
PostgreSQL still refuses it, which is what makes *"`write_records` raised nothing"* a statement about
the statement rather than about the error handling around it.

## The ordering inside the redelivery test, and why it is specified rather than convenient

The obvious version of a redelivery test proves nothing, and the plan says so before the executor can
discover it. If the test simply consumes-without-acking on a raw consumer, drops the connection and
consumes again, then **at the moment of redelivery no row exists**: there is no `workspace_spend`
figure to be unchanged from, the upsert sees no conflict, `duplicate_call_id_total` never moves, and
"lands exactly once" is satisfied by a code path with no idempotency in it at all. That test passes
*before* Task 1's change, which is the definition of an assertion that cannot fail.

So the five records are made **durable while their messages are still unacknowledged**, through
`workspace_transaction` + `write_records` with `body=None` — which is exactly what plan 03-01's
fallback does after a timed-out confirm, and is PITFALLS §2's *"including records the fallback already
wrote directly"*. Only then is the raw consumer's connection dropped. `written.duplicates == 0` on that
direct write and `snapshot_rows == 5` before the drain runs are both asserted, so the ordering itself
is proved rather than assumed.

## Deviations from Plan

### Declared drift — a file outside `files_modified`

**1. `src/prope/call_ledger/envelope.py`**

- **Found during:** Task 2, writing the `write_lag_seconds` observation.
- **Issue:** `occurred_at`'s field comment said *"Nothing in the write path reads this field; it exists
  for operators reading a dead-lettered message."* Task 2 makes `_write_group` read it to close
  `write_lag_seconds`, so the sentence became false **in the same change that made it false** — the
  exact staleness this phase spends three paragraphs refusing elsewhere. The plan anticipated the
  observation site but did not list this file.
- **Fix:** the paragraph is rewritten, not deleted. It now names D-41, names the reader, and adds the
  property that is *still* true and is the one the paragraph exists to protect: **no value derived from
  `occurred_at` ever reaches a stored column** — pricing and `expires_at` still come from
  `payload.created_at` alone. No code changed in this file.
- **Verification:** `uv run pytest tests/broker/ -q` — 63 passed; whole suite 326 passed.

### Auto-fixed issues

**2. [Rule 2 — a count that would have stopped agreeing with the table] `bodies_written`**

- **Found during:** Task 1.
- **Issue:** the plan specifies filtering `body_rows` by the inserted set but does not say what
  `WriteResult.bodies_written` should then report. Left at `len(body_rows)` it would count bodies
  *built*, not bodies *written*, and `test_write_records_returns_counts_that_match_what_landed`
  asserts `result.bodies_written == bodies` against `COUNT_BODIES` — so a redelivery carrying a body
  would have made the returned count disagree with the table.
- **Fix:** `bodies_written=len(surviving_bodies)`, with the type's own docstring rule quoted at the
  return. Asserted by `test_a_body_arriving_for_an_already_written_record_is_not_stored`
  (`result.bodies_written == 1` for a two-record batch of which one is a duplicate).

**3. [Rule 2] `classify_write_failure`'s `ValueError` enumeration listed four refusals and there are
now five**

- **Found during:** Task 2.
- **Issue:** D-36 says to rewrite the `IntegrityError` paragraph and *"change nothing else about the
  function"*. The bullet immediately above it enumerates *"the four `ValueError` refusals
  `write_records` raises"*, and D-40 adds a fifth in the same phase.
- **Fix:** the enumeration says five and names the `version_id` refusal. The function **body** is
  untouched, the `PERMANENT` default is untouched, and
  `test_an_unrecognised_failure_defaults_to_permanent` passes unmodified — which is the criterion D-36
  actually protects.

**4. [Rule 2] The `IntegrityError` parametrise case still described a unique violation**

- **Found during:** Task 2.
- **Issue:** `test_every_failure_is_classified`'s comment read *"The unique violation on call_id that
  arrives on ordinary redelivery"* — a case CL-02 makes unreachable.
- **Fix:** the case's exception message and its comment now name
  `ck_call_record_cost_state_is_coherent`, which is what actually reaches the branch. The expected
  classification is unchanged, so the assertion got no weaker.

---

**Total deviations:** 1 declared drift + 3 auto-fixed (3 × Rule 2). **No architectural change:** no new
table, no migration, no new library, no new database routine, no new role, no forbidden edge, no
`text()` interpolation, and **no fifth `SECURITY DEFINER` function**.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest -q` (whole suite) | **326 passed, 1 warning in 180.13s** (312 at the 03-01 baseline) |
| `uv run ruff check src/ tests/ alembic/` | **All checks passed!** |
| Task 1 `<verify>`: `uv run pytest tests/integration/test_write_path.py tests/architecture/test_no_sql_interpolation.py tests/architecture/test_schema_invariants.py -q` | **58 passed, 1 warning in 20.89s** |
| Task 2 `<verify>`: `uv run pytest tests/broker/test_drain_failure_classification.py -q` | **16 passed, 1 warning in 24.19s** |
| Task 3 `<verify>`: `uv run pytest tests/broker/test_redelivery_leaves_the_total_unmoved.py -x -q` | **4 passed, 1 warning in 20.31s** |
| `uv run pytest tests/broker/ -q` | **63 passed, 1 warning in 74.86s** |
| `git status --porcelain docs/modules docs/architecture docs/adr` | no output |
| `grep -c "sort_by_parameter_order=" src/prope/call_ledger/writer.py` | `0` |
| `grep -c "on_conflict_do_nothing" src/prope/call_ledger/writer.py` | `2` |
| `grep -c "on_conflict_do_update" src/prope/call_ledger/writer.py` | `0` |
| `grep -c "metadata_dropped_total\.inc" src/prope/call_ledger/drain.py` | `0` |
| `WriteResult` fields (`dataclasses.fields`) | `['priced', 'unpriced', 'unknown', 'bodies_written', 'duplicates']`, `duplicates` default `0` |
| AST `text()` calls under `src/prope` (same walk `test_no_sql_interpolation.py` runs) | **16**, against a `found >= 5` floor. **The floor was not raised** and `ALLOWED` is still `frozenset()` |
| `uv run ruff format --check` | **not run — not a gate.** Broken Window #1, unsatisfiable repo-wide |

**Literal tail of the final full-suite run:**

```
326 passed, 1 warning in 180.13s (0:03:00)
```

**Literal output of the lint gate:**

```
All checks passed!
```

## Human Verification Required

Two items, both of them the plan's own `<human-check>`s.

> **1.** D-34 means a body that arrives after a timed-out confirm — where the fallback already wrote
> the record without it — is discarded rather than stored, **permanently**. Confirm that keeping
> `body_dropped_total` reconcilable against `ledger.call_body` is worth that body. The mechanical half
> is asserted; the trade is not a property a test can settle.

> **2.** CL-11's `REQUIREMENTS.md` row reads "Phase 1 / Pending" while both clauses are built and
> green. This plan re-asserts clause 1 across the restructured writer and does not touch the row.
> Confirm the disposition — tick it in place with a note (this plan's recommendation), split the id, or
> accept a permanently-pending Phase 1 row.

Item 3 of plan 03-01's list — *"removing `metadata_dropped_total`'s increments changes what an existing
page means"* — is **completed** by this plan on the drain side and is already
`deferred-items.md` Part 1 item 3. It is not re-raised here.

## Flagged Assumptions Carried to Verification

The plan's flagged-assumptions block says no deterministic edge probe exists in this environment and
that CL-02's boundary conditions are an **agent enumeration, labelled as one**. All eight are now
asserted, which is evidence about the enumeration rather than about the probe:

| Enumerated boundary | Asserted by |
|---|---|
| a wholly-duplicate batch | `test_rewriting_the_same_batch_leaves_the_workspace_total_exactly_where_it_was` |
| a partially-duplicate batch | `test_a_batch_of_five_duplicates_and_two_new_records_adds_exactly_two` |
| a duplicate whose body is new | `test_a_body_arriving_for_an_already_written_record_is_not_stored` |
| a duplicate that crosses a month boundary | `test_two_currencies_in_two_different_months_are_still_accepted` (the keying), `test_a_second_month_creates_a_second_spend_row` (the buckets) |
| a duplicate in a batch that also mixes currencies | `test_mixing_currencies_is_refused_even_when_the_second_currency_is_a_duplicate` |
| a duplicate for a different workspace | `test_republishing_the_same_envelopes_leaves_every_workspace_total_unmoved` |
| a batch of one | `test_the_upsert_and_not_the_error_handler_is_what_absorbs_a_duplicate` |
| a record already durable when the message comes back | `test_a_redelivery_of_records_the_fallback_already_wrote_moves_nothing` |

## Known Stubs

None. Every symbol this plan created is driven by a test in this plan.

**Six metrics still have no increment site**, and that is plan 03-03's and 03-04's premise rather than
a stub: `ceiling_check_total` (03-03), and `queue_depth`, `dlq_depth`, `retention_deleted_total`,
`oldest_body_age_seconds` plus the `/metrics` route itself (03-04). Nothing scrapes
`write_lag_seconds`, `duplicate_call_id_total` or `redelivered_total` yet either — they are observable
from tests and nowhere else until 03-04, and `worker`'s registry is not `app`'s, which is `OQ-026`'s
subject.

## Notes for the next plans

- **`written_total` now over-counts on a redelivery, and this plan did not fix it.** `_write_group`
  increments it once per draft in the group, so five redelivered records move a counter documented as
  *"Call records committed to `ledger.call_record` by the drain"* by five while adding zero rows.
  `WriteResult.duplicates` is available at that call site; making the counter exact would need
  `write_records` to report *which* ids inserted, not just how many did not. Neither `drain.py`'s
  counter line nor `observability.py` was in this plan's remit for that change. Recorded in
  `deferred-items.md` Part 6 — **plan 03-04 owns the alerts that read these counters and is the
  cheapest place to decide it.**
- **`write_lag_seconds` is observed for redelivered records too.** For a genuine redelivery that is
  arguably right (the envelope's `occurred_at` is the original hand-over, so the observation includes
  the time the message spent unacknowledged); for a *re-published* envelope it is a fresh stamp and the
  lag is short. Either way the histogram now contains observations for records that were already
  durable. Worth knowing before 03-06 asserts a p95 against it.
- **`writer.py` imports `prope.observability`.** It did not before. Anything that imports the writer
  now transitively constructs the metric objects at import — which is already true of every entry
  point, but it is a new edge in the import graph and `tests/architecture` has no assertion about it.
- **`publish_drafts` in `tests/broker/_helpers.py` stamps a fresh `occurred_at` on every call**, so
  re-publishing the same drafts produces envelopes that are identical except for that field. That is
  what makes mechanism 1 a duplicate-`call_id` test and not a redelivery test, and it is why
  `redelivered_total` needs mechanism 2.
- **The negative control in the new test module issues a raw `INSERT` through `migrate_engine`.** If a
  later phase adds a table-level guard that makes that statement fail for a different reason, the test
  will still pass but will have stopped proving what it says. Its docstring names the property.

## Self-Check: PASSED

- `tests/broker/test_redelivery_leaves_the_total_unmoved.py` exists; all six modified files carry this
  plan's changes.
- `src/prope/call_ledger/writer.py` contains `on_conflict_do_nothing` twice, `on_conflict_do_update`
  zero times, and `sort_by_parameter_order` only inside its explanatory comment.
- `WriteResult` declares exactly five count fields and `duplicates` defaults to `0`.
- `src/prope/call_ledger/drain.py` contains no `metadata_dropped_total.inc` and increments
  `redelivered_total` from `message.redelivered`.
- `tests/broker/test_drain_failure_classification.py`'s raw-consumer redelivery test
  (`test_unacknowledged_messages_are_redelivered_after_a_consumer_restart`) is **unchanged**.
- `tests/architecture/test_no_sql_interpolation.py`'s `ALLOWED` is still `frozenset()` and its
  `found >= 5` floor is untouched.
- `uv run pytest -q` → **326 passed**. `uv run ruff check src/ tests/ alembic/` → clean.
- No file under `docs/modules`, `docs/architecture` or `docs/adr` was modified, and no tracked file was
  deleted.

---
*Phase: 03-durability-idempotency-and-no-read-path*
*Completed: 2026-08-11*
