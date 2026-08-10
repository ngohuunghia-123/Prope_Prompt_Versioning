---
phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
plan: 04
subsystem: backend
tags: [postgres, rls, sqlalchemy, pricing, decimal, prometheus, structlog, security, tenancy]

# Dependency graph
requires:
  - phase: 01-data-model-pricing-and-retention
    provides: "write_records (the one write path), resolve_price/compute_cost, workspace_transaction, CallRecordDraft/WriteResult, ledger.spend_ceiling and ledger.workspace_spend, ix_call_record_workspace_id_run_id, and the session-scoped PostgreSQL 17 rig"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 01
    provides: "prope.observability — the counter module, LOGGABLE_FIELDS, and the four Phase 2 counters this plan adds a fifth to"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 02
    provides: "writer.period_month(at) — the promoted public month helper check_spend_ceiling calls; UPSERT_WORKSPACE_SPEND's one-currency invariant; the asserted absence of a database guard behind A-055"
provides:
  - "prope.call_ledger.seams.price_usage — INT-019, the seam that RAISES, over the one write path"
  - "prope.call_ledger.seams.check_spend_ceiling — INT-020, the refusal that carries no figure and the one seam in Prope that fails open"
  - "prope.call_ledger.seams.get_run_totals — INT-021, the two counts alongside the totals"
  - "EvalUsageRow — an eval body made unrepresentable in the input type (A-055's third line)"
  - "CeilingDecision (exactly two fields) and CeilingReason (a StrEnum machine code)"
  - "RunTotals — INT-021's six registered fields"
  - "prope_call_ledger_ceiling_failed_open_total — AC-7's counter, the control on the fail-open branch"
  - "LOGGABLE_FIELDS gains \"job\" — plan 02-03's handoff, closed"
  - "docs/brainstorm/open_questions/OQ-019.md and OQ-020.md — the two declared deviations from the two upstream files"
affects: [02-05-management-routes, 03-fallback-and-upsert, 16-18-evaluation, 22-release-control]

actuals:
  tokens: 71000
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "A value object whose ABSENT field is the guarantee — an eval body is unrepresentable rather than refused"
    - "A security property asserted over the SERIALIZED form and every captured log record, not field by field"
    - "Fail open and count, where the counter and not the branch is the mitigation"
    - "One shared derivation (period_month) called by both sides of a comparison, asserted as behaviour rather than as a unit test of the helper"
    - "Two disjoint counts filtered from two DIFFERENT stored status columns, with the asymmetry stated at the statement rather than smoothed over"
    - "A deviation from a registered interface raised as its own OQ, one per blocked upstream field"

key-files:
  created:
    - src/prope/call_ledger/seams.py
    - tests/integration/test_eval_usage_priced_without_body.py
    - tests/integration/test_ceiling_refuses_evals_only.py
    - tests/integration/test_run_totals.py
    - docs/brainstorm/open_questions/OQ-019.md
    - docs/brainstorm/open_questions/OQ-020.md
  modified:
    - src/prope/observability.py
    - tests/unit/__init__.py

key-decisions:
  - "check_spend_ceiling refuses at >= the limit, not > it — INT-020's own words are 'a run that starts UNDER the ceiling ... finishes', and at exactly the limit a workspace is not under it. Allowing there would guarantee crossing, because ck_call_record_cost_is_never_zero says no priced call costs nothing"
  - "CeilingReason ships as a StrEnum machine code (MONTHLY_CEILING_EXCEEDED) rather than a human string — ADR-0053's client-renders-the-code rule, with the honest caveat recorded that an in-process seam has no UI until Phase 17"
  - "A ceiling and a spend total in different currencies, or a limit with no currency at all, is treated as an UNEVALUABLE check: fail open and count, not refuse. A-107 forbids conversion, so refusing would be refusing on a figure that does not exist"
  - "RunTotals.cost is None rather than Decimal(0) for a run with nothing priced — a zero beside a null currency is a number with no unit, the shape ck_workspace_spend_total_cost_carries_currency refuses one table over, and it would make 'cost nothing' indistinguishable from 'nothing priced'"
  - "price_usage refuses a row whose run_id disagrees with its run_id argument, and a batch spanning two workspaces — both before a transaction opens. Neither is in the plan; both are silent-corruption paths (Rule 2)"
  - "EvalUsageRow requires version_id, which the ENGINE requires only for source=gateway. The phase's success criterion names it for eval, so the model requires what the criterion requires and says out loud that the database does not"
  - "The fail-open BRANCH ships in this plan and CL-07 is NOT ticked — CL-07 is Phase 3's, and the split is stated at the counter, at the function, and here"

patterns-established:
  - "A no-figure security property is asserted by searching the serialized decision AND every captured log record for the workspace's actual digit runs, under every branch including the one where the helpful message would be added"
  - "An unevaluable-input case raises a private Exception subclass so it takes the same fail-open path as a database that would not answer, counter included"
  - "A month-agreement property is asserted through behaviour — an instant whose local and UTC months differ, written by one side and read by the other — rather than by unit-testing the shared helper twice"

requirements-completed: [CL-06, CL-09]

coverage:
  - id: D1
    description: "An eval-case usage row written through price_usage carries source=eval, run_id, case_id and version_id, is priced at its own created_at, contributes to the workspace's monthly spend on the same footing as a gateway call, and creates no call_body row"
    requirement: CL-09
    verification:
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_an_eval_row_is_priced_stored_and_carries_no_body"
        status: pass
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_the_eval_row_lands_on_the_same_spend_total_as_a_gateway_call"
        status: pass
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_an_eval_row_is_priced_at_the_row_in_force_on_its_own_day"
        status: pass
    human_judgment: false
  - id: D2
    description: "Unpriced and unknown are the answers — no zero, no average, no inferred cost or token count"
    requirement: CL-09
    verification:
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_an_eval_row_with_no_price_row_is_unpriced_and_its_cost_is_null"
        status: pass
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_an_eval_row_with_no_usage_object_is_unknown_with_null_tokens"
        status: pass
    human_judgment: false
  - id: D3
    description: "price_usage raises rather than absorbing a failure, and after a raise nothing is written — both before a transaction opens and after"
    requirement: CL-09
    verification:
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_a_row_without_a_case_id_is_refused_and_nothing_is_written"
        status: pass
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_a_refusal_inside_the_transaction_leaves_the_whole_batch_unwritten"
        status: pass
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_a_row_belonging_to_another_run_is_refused"
        status: pass
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_a_batch_spanning_two_workspaces_is_refused_before_a_transaction_opens"
        status: pass
    human_judgment: false
  - id: D4
    description: "price_usage opens its own workspace_transaction, never takes evaluation's session, and writes no SQL of its own"
    verification:
      - kind: integration
        ref: "tests/integration/test_eval_usage_priced_without_body.py::test_price_usage_takes_a_sessionmaker_and_writes_no_sql_of_its_own"
        status: pass
    human_judgment: false
  - id: D5
    description: "check_spend_ceiling refuses an eval run for a workspace whose gateway traffic alone has already exceeded its monthly ceiling, with a reason; both ceilings default off"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_gateway_traffic_alone_over_the_ceiling_refuses_with_a_reason"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_a_workspace_with_no_ceiling_row_is_allowed"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_a_disabled_ceiling_allows_however_far_over_the_spend_is"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_a_workspace_under_its_ceiling_is_allowed"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_spend_exactly_at_the_limit_refuses"
        status: pass
    human_judgment: false
  - id: D6
    description: "The serialized form of a ceiling decision contains no spend figure, no limit, no remaining amount and no currency, under every branch including refused — in the return value and in every log record"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_no_figure_reaches_the_decision_or_a_log_line_under_either_branch"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_the_decision_has_exactly_two_fields_and_a_typed_reason"
        status: pass
    human_judgment: false
  - id: D7
    description: "Gateway traffic for a workspace over its ceiling is recorded normally — the ceiling refuses eval runs and never gateway traffic"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_gateway_traffic_keeps_being_recorded_after_the_refusal"
        status: pass
    human_judgment: false
  - id: D8
    description: "A ceiling check that cannot be evaluated returns allowed and increments a counter rather than raising into evaluation"
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_an_unevaluable_check_allows_and_counts_and_does_not_raise"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_a_ceiling_and_a_spend_in_different_currencies_fail_open"
        status: pass
    human_judgment: false
    rationale: "The branch is built and asserted here; the CLAIM is CL-07 and CL-07 is Phase 3's. This plan does not tick it."
  - id: D9
    description: "check_spend_ceiling and write_records derive the same period_month for the same instant"
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_the_ceiling_reads_the_same_month_write_records_files_into"
        status: pass
    human_judgment: false
  - id: D10
    description: "get_run_totals returns the unpriced count and the unknown-usage count alongside the token and cost totals, computed from the stored encoding rather than from intent, and the two counts are disjoint"
    verification:
      - kind: integration
        ref: "tests/integration/test_run_totals.py::test_a_fully_priced_run_returns_its_totals_and_two_zero_counts"
        status: pass
      - kind: integration
        ref: "tests/integration/test_run_totals.py::test_one_unpriced_row_and_one_unknown_row_report_one_and_one"
        status: pass
      - kind: integration
        ref: "tests/integration/test_run_totals.py::test_unpriced_rows_are_counted_and_contribute_nothing_to_the_cost"
        status: pass
      - kind: integration
        ref: "tests/integration/test_run_totals.py::test_unknown_usage_rows_are_counted_and_contribute_no_tokens"
        status: pass
      - kind: integration
        ref: "tests/integration/test_run_totals.py::test_the_unknown_count_equals_what_write_records_reported"
        status: pass
      - kind: integration
        ref: "tests/integration/test_run_totals.py::test_both_counts_are_computed_from_the_stored_encoding"
        status: pass
    human_judgment: false
  - id: D11
    description: "get_run_totals raises on a run spanning two currencies rather than returning a sum with no unit, and a run_id alone is not an identity"
    verification:
      - kind: integration
        ref: "tests/integration/test_run_totals.py::test_a_run_spanning_two_currencies_raises_naming_both"
        status: pass
      - kind: integration
        ref: "tests/integration/test_run_totals.py::test_a_run_belonging_to_another_workspace_is_invisible_and_returns_zeroes"
        status: pass
      - kind: integration
        ref: "tests/integration/test_run_totals.py::test_a_run_with_no_rows_returns_zeroed_totals_and_raises_nothing"
        status: pass
    human_judgment: false
  - id: D12
    description: "The reason ships as a machine code rather than a literal string, and building the fail-open branch here while leaving CL-07's claim to Phase 3 is the intended split"
    verification: []
    human_judgment: true
    rationale: "The plan's own first <human-check>. Whether a code is the right shape for a value with no UI yet, and whether a branch may ship a phase ahead of its requirement, are judgements about posture rather than properties a test can assert. The mechanical halves — CeilingReason IS a StrEnum, its only member IS monthly_ceiling_exceeded, and the counter DOES increment — are asserted."
  - id: D13
    description: "CL-11's second clause ships in this plan while its REQUIREMENTS.md row still reads Phase 1 / Pending; the traceability disposition must be settled before the phase seals"
    verification: []
    human_judgment: true
    rationale: "The plan's second <human-check>. Splitting CL-11 into two IDs, remapping the row to both phases, or accepting a permanently-pending Phase 1 row is a bookkeeping decision the developer owns. The code half is built and asserted (D10)."

# Metrics
duration: 23min
completed: 2026-08-10
status: complete
---

# Phase 02 Plan 04: Seams — enqueue, the broker drain, and the ceiling Summary

**All three of the phase's success criteria now hold in one file: a workspace over its monthly
ceiling has eval runs refused with a machine reason and no figure of any kind while its gateway
traffic keeps landing; an eval-case usage row is priced at its own timestamp, counted on the same
`workspace_spend` row as a gateway call, and creates no `call_body` row; and `get_run_totals`
returns the unpriced and unknown-usage counts alongside the totals, computed from the stored
encoding. All three are proved from call-ledger's own tests against the real engine, because
evaluation — their only caller — does not exist for another fourteen phases.**

## Performance

- **Duration:** ~23 min
- **Tasks:** 3, each executed test-first (RED commit, then GREEN commit)
- **Files created/modified:** 8
- **Test suite:** **236 passed**, 0 failed (199 at the 02-03 baseline; +37)

## Which half of CL-09 this plan closed

Stated plainly, because plan 02-02 asked for it by name.

CL-09 is *"an eval-case usage row is priced and counted toward workspace spend with no body
stored"*, and it is **jointly satisfied by 02-02 and 02-04**:

| Half | Plan | What was built |
|------|------|----------------|
| **no body stored** | 02-02 | `write_records`' A-055 refusal, its whole-batch behaviour, and the asserted **absence** of any database guard behind the rule (`tests/security/test_eval_no_body_boundary.py`) |
| **priced and counted** | **02-04 (this plan)** | `price_usage`, and the assertions that an eval row is priced at its own `created_at`, lands on the same monthly `workspace_spend` row as a gateway call, and leaves `ledger.call_body` untouched for its `call_id` |

**This plan closed the priced-and-counted half.** It also added a third line in front of 02-02's
two: `EvalUsageRow` has **no body field at all**, so an eval body is unrepresentable in this seam's
input type rather than refused by it. That matters precisely because 02-02 established there is no
constraint underneath — the guarantee holds as far as `write_records` reaches and no further, so
the cheapest available reinforcement is a type a body cannot be put into.

The same joint reading applies to **CL-06**: plans 02-01 and 02-03 built the *"gateway traffic
continues to be recorded normally"* clause at the write path and at the process level; this plan
built the **refusal** — `check_spend_ceiling` — and re-asserted the recorded-normally clause against
a workspace that is actually over its ceiling.

## The fail-open branch ships; CL-07 is not ticked

The plan's `<output>` requires this to be said, so it is said here in full.

`check_spend_ceiling` is **the one seam in Prope that fails open**. A check it cannot evaluate
returns `allowed = True` with no reason and increments
`prope_call_ledger_ceiling_failed_open_total`; it does not raise into evaluation. The branch exists
because INT-020 and A-142 §2 make it part of the seam's contract, and a seam shipped without its own
failure contract is a seam that would have to be reopened.

**CL-07 — *"a spend-ceiling check that cannot be evaluated returns allowed, counts the failure, and
never raises into evaluation"* — is Phase 3's, and this plan does not tick it.** Its
`REQUIREMENTS.md` row still reads Phase 3 / Pending and was not touched. Phase 3's T-005 sweep owns
the `/metrics` endpoint, the alert rule and the paging threshold; without those the counter is
observable from tests and from nothing else, which is exactly the state A-104 warns about — *an
open-failing check nobody watches is an off switch*. The branch is built and asserted here so that
Phase 3 verifies a claim someone built, rather than inheriting one.

The split is written at three places, not one: at the counter in `observability.py`, at the
`except` handler in `seams.py`, and here.

## CL-11's second clause is built here and its row is not moved

`get_run_totals` is ROADMAP Phase 2's third success criterion and it is **CL-11's second clause** —
*"the unknown count is reported alongside the total"*. CL-11's `REQUIREMENTS.md` row reads
**Phase 1 / Pending** and this plan did not change it.

That is deliberate. The traceability question — split CL-11 into two IDs, remap the row across both
phases, or accept a permanently-pending Phase 1 row — is **Phase 1 human-verification item 2** and
is the developer's to settle. Building the code and quietly re-pointing the row would settle it by
accident. The clause is built, asserted (D10 above), and claimed nowhere.

## What was built

**`src/prope/call_ledger/seams.py`** — three functions, four value objects, two SQL constants, and
a module docstring carrying the argument the file exists for.

**`price_usage(sessionmaker, run_id, usage_rows) -> None`** (INT-019). Converts each `EvalUsageRow`
to a `CallRecordDraft` and calls `write_records`. It contains **no `text(` call at all** — pricing at
the record's own `created_at`, the three cost states, the `expires_at` stamp and the monthly
aggregate all already live in one implementation, and a second statement here would be a second
place for the eval path and the gateway path to drift. That absence is asserted, not described.

`EvalUsageRow` requires `case_id` (the engine's `ck_call_record_eval_calls_carry_run`), requires
`run_id`, requires `version_id` — **which the engine requires only for `source = 'gateway'`**, an
asymmetry the docstring states rather than hides — and carries no `consumer_key_id` field, so the
constraint's third clause is satisfied by construction.

**`check_spend_ceiling(sessionmaker, workspace_id, *, now) -> CeilingDecision`** (INT-020). One
`LEFT JOIN` over `ledger.spend_ceiling` and `ledger.workspace_spend` keyed
`(workspace_id, period_month)`. The `LEFT JOIN` is load-bearing: a workspace with a ceiling and no
traffic this month has no `workspace_spend` row, and an inner join would collapse "configured but
quiet" into "not configured", which are opposite states.

`CeilingDecision` has exactly two fields and says at the class why it must never grow a third.
`CeilingReason` is a `StrEnum` with one member.

**`get_run_totals(sessionmaker, workspace_id, run_id) -> RunTotals`** (INT-021). One projection over
the stored encoding in `UNPRICED_WORKLIST`'s shape, served by Phase 1's
`ix_call_record_workspace_id_run_id` — the index whose **leading column is `workspace_id`**, which
is the mechanical half of D-20's argument.

**`src/prope/observability.py`** — `prope_call_ledger_ceiling_failed_open_total`, unlabelled for
`metadata_dropped_total`'s reason, plus `"job"` on `LOGGABLE_FIELDS`.

**`OQ-019` and `OQ-020`** — the two deviations, raised rather than absorbed. `git status --porcelain
docs/modules docs/architecture docs/adr` produces no output.

## The 02-03 handoff, accepted

Plan 02-03 asked this plan to add `"job"` to `LOGGABLE_FIELDS`, having deliberately not edited
`src/prope/observability.py` because this plan declares it. Its reasoning is in
`deferred-items.md`: `supervisor.job_crashed` already emits `job`, and its values are the two
job-name constants fixed in `worker.py`'s source — a closed set of two, bounded by construction per
ADR-0030, and never a body, an identifier or a credential.

**Done, in `b568dae`, with 02-03's reasoning restated at the entry.** This is an accepted cross-plan
handoff and not an unrequested change: `src/prope/observability.py` is in this plan's declared
`files_modified`, and an allow-list with a field outside it is an allow-list somebody has already
stopped believing.

## Discretion items the plan directed be resolved

**The ceiling reason** — resolved as a machine `code`, `CeilingReason.MONTHLY_CEILING_EXCEEDED`, on
ADR-0053's rule that the client renders the `code` and not a `message` the server wrote, and on
`domain.py`'s established position that a stored or transmitted status is a fact rather than a label.
The caveat is recorded at the enum rather than left implicit: ADR-0053 governs user-facing strings in
the SPA and the API envelope, and an in-process seam has no UI. This reason only becomes user-facing
when evaluation surfaces it in Phase 17 — and choosing a code *now*, before there is a screen to
argue about, is what stops that phase inheriting an untranslatable English sentence.

**Mixed currency in `get_run_totals`** — resolved by **raising**, naming the run and every currency
code, in the module's established refusal voice. Both alternative answers are false: a sum across two
currencies is a number with no unit (A-107 forbids conversion, and an exchange rate would be a second
effective-dated table), and a null cost would make "two currencies" indistinguishable from "nothing
priced" to the review screen — which is exactly the information INT-021 says the counts exist to
preserve. This matches INT-021's declared failure semantics: raises, run error at evaluation, no
delta.

The test had to find the only reachable shape for the case, which is worth recording: `write_records`
already refuses a mixed-currency *batch*, and `UPSERT_WORKSPACE_SPEND`'s one-currency invariant
(plan 02-02) refuses a second currency in the same `(workspace, month)`. **A run crossing a month
boundary while a price row's currency changes is what is left** — and it is still a run, so this
function has to answer for it.

## Two boundaries the plan left open, decided and argued

**Spend exactly equal to the limit refuses.** The plan's flagged-assumption section named this
boundary and left it unresolved. INT-020's own words settle it: *"a run that starts **under** the
ceiling and crosses it mid-run finishes"*. At exactly the limit a workspace is not under it, and
allowing there would guarantee crossing, because every run costs money and
`ck_call_record_cost_is_never_zero` says no priced call costs nothing. Asserted by
`test_spend_exactly_at_the_limit_refuses`.

**`RunTotals.cost` is `None`, not `Decimal(0)`, for a run with nothing priced.** The plan's behaviour
line says "zeroed totals" for an empty run; the token totals *are* zeroed, and cost is the one field
where a zero would be a lie. A zero cost beside a NULL currency is a number with no unit — the exact
shape `ck_workspace_spend_total_cost_carries_currency` refuses one table over — and it would make
"this run cost nothing" indistinguishable from "nothing in this run was priced", which is the
distinction the two counts exist to keep. Written at `RunTotals` and asserted in two tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] `price_usage` accepted rows belonging to another run**

- **Found during:** Task 1
- **Issue:** `run_id` is both the function's argument and a column on every row, and the plan
  specified no check that they agree. A caller that built one batch from two runs would have its rows
  written under the wrong run and `get_run_totals` would report the run it *thinks* it wrote as one
  case smaller — an undercount that reads as a legitimately smaller run, on the exact number a
  reviewer is about to act on. Silent, and unrecoverable once written.
- **Fix:** refused before any transaction opens, with a message naming the stray run ids and why the
  disagreement is invisible.
- **Files modified:** `src/prope/call_ledger/seams.py`,
  `tests/integration/test_eval_usage_priced_without_body.py`
- **Verification:** `test_a_row_belonging_to_another_run_is_refused`
- **Commit:** `84b5a50`

**2. [Rule 2 — Missing critical functionality] `price_usage` had no defined behaviour for a batch
spanning two workspaces**

- **Found during:** Task 1
- **Issue:** The function opens its own `workspace_transaction`, which carries exactly one workspace
  (ADR-0040). Nothing in the plan says which workspace it should pick from a mixed batch. Taking
  `usage_rows[0]`'s silently would have written some rows under a tenant they do not belong to — or,
  more likely, met the policy's `WITH CHECK` mid-batch and produced a half-written refusal.
- **Fix:** refused whole, before a transaction opens, in `write_records`' own voice for the same
  situation.
- **Files modified:** `src/prope/call_ledger/seams.py`,
  `tests/integration/test_eval_usage_priced_without_body.py`
- **Verification:** `test_a_batch_spanning_two_workspaces_is_refused_before_a_transaction_opens`
- **Commit:** `84b5a50`

**3. [Rule 2 — Missing critical functionality] A ceiling and a spend total in different currencies
had no defined answer**

- **Found during:** Task 2
- **Issue:** `ledger.spend_ceiling` carries its own `currency` column and so does
  `ledger.workspace_spend`, and both may be NULL. Comparing a VND limit against a USD total — or a
  limit with no currency at all against any total — is comparing two numbers with different units.
  A naive `total_cost >= monthly_limit` would refuse or allow on a figure that does not exist, and
  the plan's behaviour block does not name the case.
- **Fix:** treated as an **unevaluable check**, which is a state INT-020 already defines: a private
  `_UnevaluableCeilingError` raised into the same handler as a database that would not answer, so it
  fails open **and increments the counter**. Refusing would refuse on a phantom figure; allowing
  silently would be the off switch A-104 names.
- **Files modified:** `src/prope/call_ledger/seams.py`,
  `tests/integration/test_ceiling_refuses_evals_only.py`
- **Verification:** `test_a_ceiling_and_a_spend_in_different_currencies_fail_open`
- **Commit:** `b568dae`

**4. [Rule 3 — Blocking] The price-row fixture collided with `uq_price_table_workspace_id`**

- **Found during:** Task 2
- **Issue:** The test helper seeded one price row per gateway call, and the "gateway traffic keeps
  being recorded after the refusal" test writes two calls into the same workspace — a duplicate
  `(workspace_id, provider_config_id, upstream_model, effective_from)`, which is the uniqueness that
  makes effective-dated resolution deterministic (ADR-0019).
- **Fix:** the helper takes `seed_price=False` for a second call in the same workspace, with the
  constraint named at the parameter.
- **Files modified:** `tests/integration/test_ceiling_refuses_evals_only.py`
- **Commit:** `b568dae`

### Authentication Gates

None.

---

**Total deviations:** 4 auto-fixed (3 × Rule 2, 1 × Rule 3). **No architectural change:** no new
table, no new migration, no new library, no new database routine, no new role, no forbidden edge, and
**no fifth `SECURITY DEFINER` function** — `tests/architecture/test_schema_invariants.py::test_the_ledger_schema_contains_no_security_definer_function`
still passes unchanged.

## A note on where the `case_id` refusal actually fires

The plan's acceptance criterion reads *"`price_usage` raises on a missing `case_id`"*, and its
behaviour block reads *"refused before it reaches the engine, with a message naming `case_id`"*. Both
are true, and it is worth being precise about which line does it, because a later reader will look
for a guard inside the function and not find one.

The refusal lives in **`EvalUsageRow.__post_init__`**, which is strictly earlier than any
transaction, any session and any round trip. From the caller's seat —
`await price_usage(sm, RUN, [eval_row(case_id=None)])` — the call raises `ValueError` naming
`case_id` and writes nothing, which is what INT-019 promises. No duplicate guard was added inside
`price_usage`: it would be unreachable by construction, and an unreachable guard is dead code that
reads like a live one. Both halves are asserted —
`test_a_row_without_a_case_id_is_refused_and_nothing_is_written` for the caller-visible behaviour,
`test_case_id_is_a_required_field_with_no_default` for the type-level property.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest -q` (whole suite) | **236 passed** (199 at the 02-03 baseline) |
| `uv run pytest tests/integration/test_eval_usage_priced_without_body.py -q` | 13 passed |
| `uv run pytest tests/integration/test_ceiling_refuses_evals_only.py -q` | 12 passed |
| `uv run pytest tests/integration/test_run_totals.py -q` | 11 passed |
| `uv run pytest tests/architecture -q` | 37 passed — the `SECURITY DEFINER` set is still exactly four |
| `uv run ruff check src/ tests/ alembic/` | clean |
| `git status --porcelain docs/modules docs/architecture docs/adr` | no output |
| `seams.py` carries the two-failure-contracts argument, D-19, D-20, the fail-open split and the mixed-currency reasoning at the code | confirmed by reading |
| `uv run ruff format --check src/ tests/ alembic/` | **known-failing, pre-existing** — see below |

**On `ruff format --check`.** It now reports 38 files would be reformatted, 27 already formatted
(34/27 at plan 02-03). The cause is unchanged and systemic, and it is **not this plan's to fix**:
`ruff.toml` sets `line-length = 120` while the whole repo — Phase 1 included — is hand-wrapped to
roughly 100, so every hunk is the formatter joining a wrapped call back onto one line. `uv run ruff
check` — the linter, which is what CI would gate on today — is clean and stays clean; `E501` is
explicitly ignored. This plan's four new files are written in the house ~100 style so they read like
their neighbours, which is why the count moved by four. Satisfying this line needs the repo-wide
line-length decision recorded in `deferred-items.md`.

## Human Verification Required

The plan's `<verification>` block carries two `<human-check>`s. Both are postures rather than tests.

> **1.** Confirm that `check_spend_ceiling`'s reason ships as a machine `code`
> (`MONTHLY_CEILING_EXCEEDED`) rather than a literal string, and that building the fail-open branch
> here while leaving CL-07's claim to Phase 3 is the intended split.

Both halves are implemented as described and argued at the code. The reversal cost is small in one
direction and not in the other: swapping the code for a literal string later means finding every
place it was persisted or transmitted, whereas translating a code at the Phase 17 edge is additive.

> **2.** CL-11's second clause ships in this plan while its `REQUIREMENTS.md` row still reads
> Phase 1 / Pending (Phase 1 human-verification item 2). Confirm the traceability disposition —
> split CL-11 into two IDs, remap the row to both phases, or accept a permanently-pending Phase 1
> row — before this phase seals.

Unchanged and untouched by this plan, deliberately. See "CL-11's second clause is built here and its
row is not moved" above.

A third item is worth an explicit decision even though the plan did not ask for it: **spend exactly
equal to the limit refuses**. It is argued from INT-020's own wording and it is a product decision as
much as a technical one.

## Flagged Assumptions Carried to Verification

Both of the plan's flagged rows are carried forward unchanged, because building the code does not
answer either of them:

- **CL-06 — `unclassified` / `unresolved`.** The deterministic edge probe proposed no edge
  predicates. The boundary conditions this requirement genuinely has — no ceiling row, a row with
  `enabled` false, spend exactly equal to the limit, an instant on a month boundary in a non-UTC
  offset, and an unevaluable aggregate — are **all five now asserted**, by
  `test_ceiling_refuses_evals_only.py`, from the plan's authored truths rather than from probe
  output. **The assumption to confirm at verification is that the `unclassified` verdict was a
  classification miss and not an edge-free requirement** — and having found five real edges by hand,
  the evidence points at "miss".
- **CL-09 — `unclassified` / `unresolved`.** Same shape. Its five boundary conditions — no price
  row, no usage object, missing `case_id`, a body, and a row written across a price change — are all
  asserted by `test_eval_usage_priced_without_body.py`. Same caveat, same evidence.

## Known Stubs

None. Every symbol this plan created is driven by a test in this plan.

The three functions have **no production caller and will not have one until Phase 16/17** — that is
the plan's premise, not a stub: they are registered contracts (INT-019, INT-020, INT-021) built
ahead of their consumer on purpose, so that evaluation is written against a seam that already works
rather than one it has to shape. Each is proved against the real engine, and none returns a
placeholder, raises `NotImplementedError`, or reports a hardcoded value.

## Threat Flags

None. Every security-relevant surface this plan introduces was in the plan's `<threat_model>`, and
each is mitigated and asserted rather than intended:

| Threat | Where it is asserted |
|--------|----------------------|
| T-02-21 (a figure leaking through `CeilingDecision`) | `test_no_figure_reaches_the_decision_or_a_log_line_under_either_branch` — the *serialized* form and every captured log record, under both branches |
| T-02-22 (cross-tenant read via `get_run_totals`) | `test_a_run_belonging_to_another_workspace_is_invisible_and_returns_zeroes` — the rows proved to exist through `migrate_engine`, and zeroes read through the other context |
| T-02-23 (a fifth `SECURITY DEFINER` function) | `test_the_ledger_schema_contains_no_security_definer_function`, unchanged and still green |
| T-02-24 (eval text reaching `ledger.call_body`) | `test_the_input_type_cannot_carry_a_body_at_all` plus `test_an_eval_row_is_priced_stored_and_carries_no_body`, on top of 02-02's two |
| T-02-25 (the ceiling check aggregating `call_record`) | `test_the_ceiling_read_does_not_aggregate_call_record` — asserted over the statement, because the module's prose says the words the statement must not contain |
| T-02-26 (a ceiling check that silently always allows) | `test_an_unevaluable_check_allows_and_counts_and_does_not_raise` — the counter is the assertion, not the branch |
| T-02-27 (a delta computed over an incomplete run) | `test_one_unpriced_row_and_one_unknown_row_report_one_and_one` and `test_a_run_spanning_two_currencies_raises_naming_both` |

**No new network surface. No new table, migration, role or privilege.**

## Notes for the next plans

- **`prope.app` still does not exist.** Plan 02-05 builds it; `configure_logging()` gains its second
  production caller there, and D-24's "both processes declare the topology from one definition"
  becomes fully asserted only then.
- **These three seams have no route and must not get one.** INT-028 lists five management routes and
  none of them is a ceiling check or a run total. `check_spend_ceiling`'s no-figure property would be
  a very different problem behind HTTP.
- **`price_usage` is not idempotent yet.** INT-019 says *idempotent on `call_id`*, which is CL-02 in
  Phase 3. Until the upsert lands, a retried batch meets a unique violation — loud, which is the
  right failure for this window, but Phase 16/17's retry logic must not be written against the
  assumption that a repeat is free.
- **The fail-open counter has no scraper.** Phase 3's T-005 sweep owns `/metrics` and the alert rule.
  Until then `prope_call_ledger_ceiling_failed_open_total` is exactly the unwatched control A-104
  warns about, and that is a one-phase gap on the same footing as the broker's loss window.
- **`WORKSPACE_C` and `eval_row` are in `tests/unit/__init__.py`** beside `gateway_draft` and
  `eval_draft`. New eval fixtures belong there, not in a local factory per module.

## Self-Check: PASSED

- All six created files exist on disk; both modified files carry this plan's changes.
- All six commits are present in `git log`: `08ad233`, `84b5a50`, `3a1e671`, `b568dae`, `2ad2485`,
  `dcccda5`.
- `src/prope/call_ledger/seams.py` defines `async def price_usage(`, `async def check_spend_ceiling(`
  and `async def get_run_totals(`, plus `EvalUsageRow`, `CeilingDecision`, `CeilingReason` and
  `RunTotals`.
- `src/prope/observability.py` defines `ceiling_failed_open_total` and carries `"job"` on
  `LOGGABLE_FIELDS`.
- `docs/brainstorm/open_questions/OQ-019.md` and `OQ-020.md` exist, both `status: open`, blocking
  `apis.exposes` and INT-021 respectively.
- `uv run pytest -q` → **236 passed**. `uv run ruff check src/ tests/ alembic/` → clean.
- No commit in this plan deleted a tracked file.

---
*Phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling*
*Completed: 2026-08-10*
