---
phase: 01-data-model-pricing-and-retention
verified: 2026-08-10T04:32:16Z
status: human_needed
score: 42/42 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: null
  note: "Initial verification — no prior 01-VERIFICATION.md existed"
deferred:
  - truth: "CL-11 clause 2 — the unknown-usage count is reported alongside the total"
    addressed_in: "Phase 2"
    evidence: "ROADMAP Phase 2 Success Criterion 3: '`get_run_totals` returns the unpriced and unknown-usage counts alongside the totals.' Phase 1's own ROADMAP SC 3 covers only clause 1 ('stores null token counts with usage_status = unknown, never zeros'), which is VERIFIED. REQUIREMENTS.md correctly leaves CL-11 unchecked and its traceability row Pending."
  - truth: "The cross-tenant retention sweep that visits every workspace (OQ-C)"
    addressed_in: "Phase 2 / Phase 7"
    evidence: "Phase 2 introduces the `worker` process that would host a timer; ADR-0051's enumerator lives in the `access` schema, created in Phase 7. `retention.py:40-48` records the carry-forward. CL-08 is satisfied in full for one workspace at a time, which is what Phase 1's SC 4 asks."
human_verification:
  - test: "Decide the disposition of CR-01 (a legal `(0,0)` price row produces a zero cost that `write_records` refuses, discarding the whole batch). Options: (a) accept as a Phase 2 blocking pre-condition on `POST /api/v1/prices` — the verifier's recommendation; (b) re-open Phase 1 with a follow-up plan adding the tightened CHECK plus a per-record exception; (c) accept as-is with a recorded override."
    expected: "A recorded decision. If (a), CR-01 must be entered as a named pre-condition on the Phase 2 plan that builds the price-row write route, because Phase 2 is the first phase that lets a human insert a price row and the first phase whose drain will re-deliver a poison batch forever."
    why_human: "This is a scope/priority judgement between phases, not a fact about the code. The verifier confirmed the mechanism is real (see Behavioural Spot-Checks) and that no Phase 1 truth fails because of it; whether it blocks the phase boundary is the developer's call."
  - test: "Decide how CL-11 is tracked. It is listed in Phase 1's `Requirements:` line in ROADMAP.md and in two plans' `requirements:` frontmatter, but its second clause is assigned by ROADMAP to Phase 2 and its REQUIREMENTS.md row reads 'Phase 1 / Pending'. Either (a) split CL-11 into two IDs, (b) remap its traceability row to 'Phase 1, Phase 2', or (c) leave it and accept a permanently-Pending Phase 1 requirement."
    expected: "REQUIREMENTS.md and ROADMAP.md agree about which phase owes CL-11, so no future audit reads Phase 1 as having left a requirement unfinished."
    why_human: "A traceability-bookkeeping decision. The code is correct either way; only the planning documents disagree with themselves."
  - test: "Verify revision 0001 against a deploy-shaped database — a non-superuser `prope_migrate` on a real PostgreSQL 17 host, not the testcontainers superuser. Run `alembic upgrade head` and confirm the write to `public.alembic_version` succeeds."
    expected: "The chain reaches head. If it fails with `permission denied for schema public`, WR-04 is confirmed and revision 0001 needs `GRANT USAGE, CREATE ON SCHEMA public TO prope_migrate`."
    why_human: "Structurally unverifiable in this phase's rig: the testcontainers connection IS a superuser, so the rig cannot observe the failure. `alembic/versions/0001_roles_and_schemas.py:9-15` flags it as assumption A9 and `alembic/ddl.py:37-39` half-notices it. It needs a real host or a deliberately de-privileged container."
  - test: "Confirm the ten-decimal-place cost quantum (`COST_SCALE = 0.0000000001`) and the 30-day default retention window are the figures the business actually wants, against a real provider price list and the pilot's data-retention posture."
    expected: "Both figures confirmed, or changed before Phase 2 makes them observable through a route."
    why_human: "`compute_cost`'s scale and `DEFAULT_RETENTION_WINDOW` are internally consistent and asserted, but their correctness is a product judgement against A-040 and a real price sheet, not a property of the code."
---

# Phase 1: Data model, pricing, and retention — Verification Report

**Phase Goal:** The `ledger` schema exists with all five tables, and a call's usage is priced correctly and irreversibly at write time.
**Verified:** 2026-08-10T04:32:16Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Verdict

The phase goal is achieved. Both clauses hold under adversarial reading:

- **"the `ledger` schema exists with all five tables"** — `call_record` (revision 0002), `call_body`, `price_table`, `workspace_spend`, `spend_ceiling` (revision 0003). All five carry `workspace_id`, all five have row security enabled with exactly one policy each, verified against the live catalogue by a walk over all eight declared module schemas.
- **"priced correctly and irreversibly at write time"** — pricing resolves at each record's own `created_at` (never a clock read anywhere in `src/`); cost is exact decimal quantised at the column's scale; a priced cost is never recomputed; and `price_table` is append-only by *privilege*, proven by a live-engine mutation test that restores the grant, observes the refusal stop holding, and revokes it back.

All four ROADMAP Success Criteria were re-run by this verifier against a live `postgres:17` container, not taken from the SUMMARYs. All nine spot-check tests passed.

**Nothing here is a blocker.** The code review's CR-01 is a real defect and I confirmed its mechanism in-process, but it does not falsify the phase goal — see "The CR-01 judgement" below. It is routed to a human decision as a Phase 2 pre-condition.

---

## Goal Achievement

### ROADMAP Success Criteria (the contract)

Each was executed by this verifier against a live Postgres 17 container.

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | A call made on day 5 and written on day 12 is priced at the day-5 price row, and adding a day-20 price does not move it. | ✓ VERIFIED | `tests/unit/test_effective_dated_pricing.py::test_a_day_20_price_row_does_not_move_a_call_made_on_day_5` — **run by verifier, passed**. `pricing.py:56` binds `effective_from <= :at` where `at` is the draft's own `created_at`; `writer.py:225` passes `at=draft.created_at`. No `now()`, `clock_timestamp()` or `utcnow` appears on any pricing path. |
| 2 | A call with no price row stores its tokens with `cost_status = unpriced` and appears on the unpriced worklist; no row anywhere records a cost of zero. | ✓ VERIFIED | `tests/unit/test_missing_price_is_unpriced_not_zero.py::test_the_unpriced_worklist_returns_the_pair_with_its_count_and_since` and `tests/integration/test_write_path.py::test_no_zero_anywhere_in_a_mixed_batch_of_all_three_cost_states` — **both run by verifier, passed**. "No row anywhere" is a *table-level* constraint (`ck_call_record_cost_is_never_zero`, `0002:106-107`), not a writer guard. |
| 3 | A call whose provider returned no usage object stores null token counts with `usage_status = unknown`, never zeros. | ✓ VERIFIED | `tests/unit/test_unknown_usage_never_zero.py::test_a_call_with_no_usage_object_stores_nulls_rather_than_zeros` — **run by verifier, passed**. `ck_call_record_unknown_usage_is_null` (`0002:112-119`) refuses the zero encoding at the engine; `test_zero_tokens_refused_by_the_engine_when_usage_is_unknown` asserts the refusal names that constraint, with a NULL-token positive control first. |
| 4 | Bodies older than the retention window are gone by any query while their call records remain. | ✓ VERIFIED | `tests/integration/test_body_retention_delete.py::test_expired_bodies_are_gone_and_their_call_records_are_intact` — **run by verifier, passed**. "By any query" is honoured literally: the survivor count is taken on a fresh `prope_migrate` (owner, RLS-exempt) connection, not through an app session that could be filtering. The 17 call records survive and the 12 whose bodies went are compared field for field. |

### Observable Truths — Plan 01-01 (toolchain, tenancy tracer)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Python is the 3.13 ADR-0026 pin, not the machine's 3.14 | ✓ VERIFIED | `pyproject.toml:8` — `requires-python = ">=3.13,<3.14"`; `uv run python` reports `(3, 13, 14)`. |
| 2 | `postgres:17` is reachable | ✓ VERIFIED | `tests/conftest.py:102` pins `PostgresContainer("postgres:17")`; the verifier's own two spot-check runs started it and completed in 45.9 s and 21.8 s. |
| 3 | A SELECT outside `workspace_transaction()` on a **pristine** connection returns zero rows; the same query as `prope_migrate` returns the seeded row | ✓ VERIFIED | `test_pristine_connection_without_tenant_context_returns_zero_rows`. The inversion rests on `current_setting('app.workspace_id', true)` — the **two-argument** form (`ddl.py:87`), which returns NULL instead of raising. |
| 4 | The same SELECT on a **reused** pooled connection whose GUC reverted also returns zero rows | ✓ VERIFIED | `test_reused_connection_whose_tenant_setting_reverted_returns_zero_rows` — asserted separately from the pristine path, by holding one connection across two transactions rather than hoping a pool hands the same one back (`conftest.py:28-33`). |
| 5 | An INSERT through `workspace_transaction(A)` carrying `workspace_id = B` is refused by `WITH CHECK` | ✓ VERIFIED | `test_insert_carrying_another_tenants_workspace_id_is_refused`. `WITH CHECK` is written out explicitly rather than left to default (`ddl.py:81-85, 93`) because a mis-stamped `workspace_id` is this module's realistic leak. |
| 6 | A `workspace_id` containing a single quote is bound and round-trips unchanged | ✓ VERIFIED | `test_workspace_id_containing_a_quote_round_trips_unchanged`. Verifier read the seam directly: `session.py:41` is `text("SELECT set_config('app.workspace_id', :ws, true)")` — a bound parameter, not an interpolated `SET LOCAL`. A tree-wide grep for `f"`, `.format(`, `%s` in `src/` returns **only** error-message construction, never SQL. *(See WR-07 — the regression gate this docstring claims does not exist.)* |
| 7 | An INSERT with `cost = 0` is refused by the live engine | ✓ VERIFIED | `test_a_cost_of_zero_is_refused_by_the_engine`; `ck_call_record_cost_is_never_zero`. |
| 8 | An INSERT with `usage_status = 'unknown'` and `input_tokens = 0` is refused by the live engine | ✓ VERIFIED | `test_unknown_usage_with_zero_tokens_is_refused`, `test_zero_tokens_refused_by_the_engine_when_usage_is_unknown`. |
| 9 | `call_record.created_at` has no column default | ✓ VERIFIED | `test_created_at_has_no_column_default`, `test_created_at_has_no_default_while_written_at_does`. Confirmed in the DDL (`0002:81-88`): `created_at` has none, `written_at` defaults to `now()`. This is the single easiest way to get CL-03 subtly wrong, and it is asserted against the live catalogue rather than the migration source. |

### Observable Truths — Plan 01-02 (the four remaining tables, T-006)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All five tables exist in `ledger`, each with `workspace_id`, RLS enabled, exactly one policy | ✓ VERIFIED | `test_every_table_in_every_declared_schema_is_tenant_scoped` — **run by verifier, passed**. "Exactly one" confirmed structurally: `enable_tenant_rls` is called exactly once per table (`0002:182`, `0003:243-244` looping four tables), each call issuing one `CREATE POLICY {table}_tenant`. *(The coverage walk asserts ≥1 policy; only `call_record` has an `== ["call_record_tenant"]` assertion — see WARN-3.)* |
| 2 | `UPDATE` on `price_table` as `prope_app` refused, with a **visible row** positive control | ✓ VERIFIED | `test_update_on_price_table_is_refused_by_the_engine`. `_refusal_text` (`test_append_only_privilege.py:121-135`) asserts the seeded row is visible *inside the same transaction* as the attempt, so the refusal cannot be an empty-table false pass. |
| 3 | `DELETE` on `price_table` refused, same positive control | ✓ VERIFIED | `test_delete_on_price_table_is_refused_by_the_engine`. |
| 4 | Restoring the T-006 grant makes the refusal stop holding; revoked back in a `finally` | ✓ VERIFIED | `test_the_append_only_refusal_has_teeth` — **run by verifier, passed**. This is a genuine mutation check, not a procedure nobody runs: it asserts `has_table_privilege` is False, GRANTs, asserts True, executes the very statement the refusal tests expect to fail and asserts `rowcount == 1`, then REVOKEs in `finally` and re-asserts False. |
| 5 | `DELETE` on `call_record` refused; `DELETE` on `call_body` succeeds | ✓ VERIFIED | `test_delete_on_call_record_is_refused_by_the_engine`, `test_delete_on_call_body_succeeds_because_retention_must_have_it`. The latter verifies by direct owner query, and asserts the call record survives — the one privilege whose *presence* is the guarantee. |
| 6 | The tenant-coverage walk enumerates all **eight** declared schemas; an absent schema is reported, not skipped | ✓ VERIFIED | `test_tenant_coverage.py:23-32` names all eight; `EXPECTED_ABSENT_SCHEMAS` (`:47-55`) is a per-phase constant whose owner is documented, and `test_declared_schemas_that_do_not_exist_are_reported_not_skipped` fails if a schema silently appears or vanishes. `assert tables` guards against a walk that found nothing passing every assertion below it. |
| 7 | `alembic upgrade head` on a pristine cluster works; a second run is a byte-identical no-op | ✓ VERIFIED | `test_an_empty_cluster_reaches_head_and_yields_a_working_database`, `test_running_the_chain_a_second_time_is_a_no_op`, `test_the_revision_chain_has_exactly_one_head`. |
| 8 | No foreign key on any `ledger` table references outside `ledger` | ✓ VERIFIED | `test_no_foreign_key_leaves_the_ledger_schema`. The two FKs created are both intra-schema (`fk_call_body_call_id`, `fk_call_record_price_row_id`). *(See WARN-4 — intra-schema FKs still bypass RLS.)* |
| 9 | The `ledger` schema contains zero `SECURITY DEFINER` functions | ✓ VERIFIED | `test_the_ledger_schema_contains_no_security_definer_function`; tree-wide grep for `SECURITY DEFINER` in `alembic/` and `src/` returns nothing. The project-wide sanctioned set is exactly four and none belongs to this module. |
| 10 | Every price/cost column is `numeric(20,10)`, every timestamp `timestamptz`, no float anywhere in `ledger` | ✓ VERIFIED | `test_every_money_column_is_numeric_20_10`, `test_every_timestamp_column_carries_a_time_zone`, `test_no_column_in_ledger_has_a_floating_point_type` — all against the live catalogue. `models.py:44,47` mirrors it (`MONEY = Numeric(20,10)`, `TIMESTAMPTZ = DateTime(timezone=True)`). |
| 11 | `UNIQUE (workspace_id, provider_config_id, upstream_model, effective_from)` makes an effective-date tie impossible to insert | ✓ VERIFIED | `uq_price_table_workspace_id`, `0003:133-134`, declared inside `CREATE TABLE` — a named constraint in a `CREATE TABLE` that succeeded is enforced by the engine with no code path able to bypass it, and the chain is proven to reach head. Column order matches the lookup order in `PRICE_IN_FORCE`, so the same index serves the resolution. *(No negative test attempts a duplicate — INFO-2.)* |

**Prohibition (01-02):** *MUST NOT create a second resting place for a call body.* — ✓ HELD. `call_body` has no soft-delete flag, tombstone or status column (`0003:57-90`); the schema holds exactly five tables and no archive/audit/shadow copy; `src/` contains **no logging, structlog, print or logger of any kind** (verified by grep), so no log line or metric label can carry a body; the only committed body fixtures are the synthetic strings `"a request"` / `"a response"` (`tests/unit/__init__.py:124`).

### Observable Truths — Plan 01-03 (pricing, cost, `write_records`)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Day-5 call written on day 12 is priced at the day-1 row, stores its `price_row_id`, and a day-20 row leaves it byte-identical | ✓ VERIFIED | ROADMAP SC 1 — **run by verifier**. |
| 2 | A call landing exactly on an `effective_from` is priced at THAT (new) row — half-open interval | ✓ VERIFIED | `test_the_boundary_instant_belongs_to_the_newer_row`; predicate is `effective_from <= :at` with `ORDER BY effective_from DESC LIMIT 1`. |
| 3 | A call earlier than every price row is unpriced, on the same footing as a call with no price row at all | ✓ VERIFIED | `test_not_yet_effective_and_no_rows_at_all_are_indistinguishable`, `test_a_price_row_that_is_not_yet_effective_is_unpriced_on_the_same_footing`. `pricing.py:88-91,105` returns `None` for both, deliberately indistinguishable. |
| 4 | Cost is exact decimal, quantised at ten places with banker's rounding, reproducible byte-for-byte | ✓ VERIFIED | `test_the_same_inputs_produce_a_byte_identical_cost`, `test_banker_s_rounding_is_applied_at_the_eleventh_place` (asserted on the only inputs where half-even and half-up differ), `test_compute_cost_returns_a_decimal_and_refuses_a_binary_price`. `compute_cost` raises `TypeError` rather than coercing a non-`Decimal` price (`pricing.py:117-125`). |
| 5 | A realistic sub-cent call (300 + 150 tokens at ~0.00015/1k) stores a strictly positive cost | ✓ VERIFIED | `test_a_sub_cent_call_stores_a_strictly_positive_cost`, `test_one_token_at_the_cheapest_realistic_price_is_still_positive`, `test_a_vnd_scale_cost_round_trips_through_the_numeric_column`. |
| 6 | No price row → real tokens, `cost`/`currency`/`price_row_id` NULL, `cost_status = unpriced`, pair on the worklist | ✓ VERIFIED | ROADMAP SC 2 — **run by verifier**. |
| 7 | No usage object → `usage_status = unknown`, tokens NULL, `cost_status = not_applicable`, NULL cost — GATE-04's "zero tokens and zero cost" fallback is this row shape (OQ-E) | ✓ VERIFIED | ROADMAP SC 3 — **run by verifier**; plus `test_the_gateway_pre_first_byte_fallback_is_unknown_not_a_zero`, which asserts `SELECT count(*) ... WHERE cost = 0 OR input_tokens = 0 OR output_tokens = 0` is 0 with a `total == 2` positive control so the zero-count is not free. |
| 8 | `expires_at` = the record's **own** `created_at` + `retention_window`, default 30 days, never wall-clock | ✓ VERIFIED | `test_expires_at_is_the_records_own_created_at_plus_the_default_window`, `test_expires_at_honours_a_custom_retention_window`. `writer.py:296` — `draft.created_at + retention_window`. |
| 9 | `workspace_spend` upserted in the writer's own transaction; `period_month` from the record's own `created_at` in UTC; `call_count` counts every record; `total_cost` sums only priced | ✓ VERIFIED | `test_call_count_counts_every_record_and_total_cost_only_the_priced_ones`, `test_a_second_month_creates_a_second_spend_row`, `test_a_second_batch_accumulates_onto_the_same_month_row`. `_period_month` (`writer.py:160-168`) derives from `draft.created_at.astimezone(UTC)`. *(See WARN-2 — the one-currency invariant is a read-then-write race.)* |
| 10 | A `source=eval` record writes no `call_body` row and contributes to the same `workspace_spend` row as a gateway record | ✓ VERIFIED | `test_an_eval_draft_writes_no_body_and_still_moves_workspace_spend`, `test_an_eval_draft_carrying_a_body_is_refused` (`writer.py:205-209`). |
| 11 | *(backstop)* The unknown and unpriced counts are computable from the stored encoding alone — from `cost_status`/`usage_status`, never from whether a cost or token column is NULL | ✓ VERIFIED | Explicit evidence, so the backstop does not abstain: `test_the_gateway_pre_first_byte_fallback_is_unknown_not_a_zero` asserts `by_status == 1` **and** `by_status == by_nulls`, where `by_status` is a `count(*) FILTER (WHERE usage_status = 'unknown')`. `WriteResult.unknown` (`domain.py:183-202`) is derived from the `cost_status` tally, and `repricing.py:61-73` selects on `cost_status = 'unpriced'` rather than `cost IS NULL`. This is exactly the shape Phase 2's `get_run_totals` needs. |

**Prohibition (01-03):** *MUST NOT estimate, infer, default, or back-fill a cost or a token count.* — ✓ HELD. `write_records` has three branches and **no default branch** (`writer.py:215-250`); a missing price sets `UNPRICED` rather than a zero; a missing usage object sets `NOT_APPLICABLE` with tokens left NULL. No `round(x, 2)`, no `float` on any money path, no average, no nearest-row fallback, no prompt-length inference anywhere in `src/`.

### Observable Truths — Plan 01-04 (repricing, retention)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A price row predating existing calls gives a previously-unpriced call its cost, currency, `price_row_id` and `cost_status = priced` | ✓ VERIFIED | `test_a_previously_unpriced_call_gains_a_cost_when_a_price_row_arrives`. The cost is compared to `compute_cost`'s own answer, not to a number typed into the test file. |
| 2 | An already-priced call is **byte-identical** after repricing — whole tuple compared | ✓ VERIFIED | `test_an_already_priced_call_is_unchanged_field_for_field` — **run by verifier, passed**. The setup is genuinely adversarial: a *dearer* day-3 row that would supersede the day-1 row for a day-5 call is inserted first, and a second call in the same workspace *is* repriced by the run, so "nothing changed" cannot be explained by "nothing ran". `assert after == before` on the full row dict. |
| 3 | A `not_applicable` call is still `not_applicable` after repricing | ✓ VERIFIED | `test_a_not_applicable_call_is_still_not_applicable_after_repricing`. |
| 4 | Repricing selects on `cost_status = 'unpriced'`, never on `cost IS NULL` | ✓ VERIFIED | `repricing.py:66` and `:89` — the predicate appears in **both** the selection and the update's own `WHERE`, so a row priced by a concurrent writer between the two simply does not match rather than being overwritten with a second opinion. `rowcount` is what is counted (`:194`), never the branch that intended to change it. |
| 5 | A repriced cost is byte-identical to what the writer would have produced — one cost function, not two | ✓ VERIFIED | `repricing.py:48` imports `compute_cost` and `resolve_price` from `prope.call_ledger.pricing` — the same module `writer.py:56` imports. There is no second implementation in the tree. Asserted in test 1 above. |
| 6 | Bodies at/before the cut-off are gone when queried **directly as `prope_migrate`**; their call records are intact and unchanged | ✓ VERIFIED | ROADMAP SC 4 — **run by verifier**. Also `test_a_body_expiring_exactly_at_the_cut_off_goes_and_a_microsecond_later_stays`. |
| 7 | The chunk loop terminates on a short chunk and honours `max_chunks`; a set larger than `chunk_size` takes more than one chunk and still ends empty | ✓ VERIFIED | `test_chunking_runs_three_chunks_and_a_bounded_run_stops_early` — `chunks == [5, 2]`, and `max_chunks=1` deletes exactly 5 and leaves 7. *(See WARN-1 — `chunk_size=0` is an unguarded infinite loop.)* |
| 8 | Each chunk runs in its own transaction, one workspace each — proven from **outside an in-flight** multi-chunk run: residuals 7, then 2, then 0 (OQ-D) | ✓ VERIFIED | `test_per_chunk_transactions_are_visible_outside_the_running_loop` — **run by verifier, passed**. This is the strongest test in the phase. The `on_chunk` callback opens a genuinely fresh `prope_migrate` (NullPool) connection each time and counts survivors; `assert observed == [7, 2, 0]`. A loop-wide single transaction would record `[12, 12, 12]`. The test's own docstring names and rejects the worthless `max_chunks=1` version. `test_default_path_without_a_callback_deletes_exactly_the_same_rows` proves `on_chunk` is an observation seam and not a behaviour change. |
| 9 | Another workspace's equally-expired body is never deleted by a call scoped to this one | ✓ VERIFIED | `test_another_workspaces_equally_expired_body_is_untouched`. |
| 10 | `delete_expired_bodies` takes the cut-off as an argument and reads no clock | ✓ VERIFIED | `retention.py:114-122` — `now: datetime` is keyword-only and required; `DELETE_CHUNK` binds `:cut_off_at`. No `now()` or `clock_timestamp()` in the statement. |
| 11 | Workspace-scoped, enumerates nothing: no scheduler, no cross-tenant sweep, no fifth `SECURITY DEFINER` function (OQ-C) | ✓ VERIFIED | The function takes one `workspace_id`. No timer library in `pyproject.toml`. `test_the_ledger_schema_contains_no_security_definer_function` confirms the count. |

**Prohibition (01-04):** *MUST NOT introduce any read path for `ledger.call_body`.* — ✓ HELD. The only statement touching the table outside the writer's INSERT is `DELETE_CHUNK`, and its inner `SELECT` projects `ctid` — the physical row locator — and **no stored column** (`retention.py:93-107`). No route, no exported accessor, no repository helper, no whole-row projection, no cross-module join. Grep of `src/` for `call_body` returns only the model declaration, the writer's INSERT, and the retention DELETE. *(INFO-3 notes a test-side body projection.)*

---

## Deferred Items

Not met in Phase 1, but explicitly addressed by later milestone phases. These are **not** actionable gaps.

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | CL-11 clause 2 — "the unknown count is reported alongside the total" | Phase 2 | ROADMAP Phase 2 SC 3: "`get_run_totals` returns the unpriced and unknown-usage counts alongside the totals." Phase 1's SC 3 covers only clause 1. |
| 2 | The cross-tenant retention sweep (OQ-C) | Phase 2 (`worker`) / Phase 7 (`access` schema) | `retention.py:40-48`; ADR-0051's enumerator lives in a schema that does not exist until Phase 7. CL-08 and AC-8 are satisfied in full for one workspace at a time. |
| 3 | `GET /api/v1/prices/unpriced` route | Phase 2 | ROADMAP Phase 2 Spec names `/prices/unpriced` in `apis.exposes`. Phase 1 ships the encoding, the partial index and the `UNPRICED_WORKLIST` query, and a test executes it. Not a stub. |

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.phase-base-sha`, `.plan-03-base-sha`, `.plan-04-base-sha` | one commit SHA each | ✓ VERIFIED | All three present, 41 bytes each. |
| `alembic/versions/0001_roles_and_schemas.py` | three roles (idempotent DO block, no passwords), `CREATE SCHEMA ledger AUTHORIZATION prope_migrate` | ✓ VERIFIED | 77 lines. Contains `pg_roles`. `AUTHORIZATION prope_migrate` is what ADR-0035's owner bypass rests on. *(WARN-5.)* |
| `alembic/versions/0002_call_record.py` | `call_record` + every CHECK, index, policy, grant | ✓ VERIFIED | 201 lines, contains `call_record_tenant`. 9 named CHECKs, 3 indexes, 1 policy, grants `SELECT, INSERT, UPDATE` (no DELETE). |
| `alembic/versions/0003_ledger_tables.py` | the four remaining tables + T-006 REVOKEs + deferred FK | ✓ VERIFIED | 276 lines, contains `price_table`. `grant_table("ledger","price_table", app_privileges=["SELECT","INSERT"])` at `:256` is the phase's irreversibility claim. |
| `alembic/ddl.py` | `enable_tenant_rls`, `grant_table`, `assume_migrate_role` | ✓ VERIFIED | All three exported and used by both revisions. `reset_role` also present. |
| `src/prope/db/session.py` | `workspace_transaction()` | ✓ VERIFIED | 59 lines, exports `workspace_transaction`. Transaction opened before the tenant is set. |
| `src/prope/db/metadata.py` | shared `MetaData`, no default schema, naming convention | ✓ VERIFIED | 31 lines. |
| `src/prope/call_ledger/models.py` | five declarative tables | ✓ VERIFIED | 144 lines. All five declare `schema="ledger"` explicitly. Drift caught by `test_every_declared_model_matches_a_live_table`. |
| `src/prope/call_ledger/domain.py` | 4 StrEnums + 4 value objects | ✓ VERIFIED | 203 lines. All declared exports present. Enum values byte-identical to the DB CHECK sets. |
| `src/prope/call_ledger/pricing.py` | `resolve_price`, `compute_cost` | ✓ VERIFIED | 132 lines. Both exported and imported by *both* `writer.py` and `repricing.py`. |
| `src/prope/call_ledger/writer.py` | `write_records` | ✓ VERIFIED | 347 lines. Three cost states, no default branch. |
| `src/prope/call_ledger/repricing.py` | `reprice_unpriced` | ✓ VERIFIED | 197 lines. |
| `src/prope/call_ledger/retention.py` | `delete_expired_bodies`, `DELETE_CHUNK` | ✓ VERIFIED | 171 lines. Both exported. |
| `tests/conftest.py` | postgres:17 container, `upgrade head`, three role-scoped engines, truncate isolation | ✓ VERIFIED | 147 lines, contains `PostgresContainer`. Truncate-between-tests, not rollback — correctly, since a savepoint would not reset the transaction-local tenant setting. |
| `tests/security/test_tenant_isolation.py` | live-engine zero-rows proof | ✓ VERIFIED | 125 lines (min 60). 5 tests. |
| `tests/security/test_append_only_privilege.py` | T-006 with visible-row control + mutation test | ✓ VERIFIED | 252 lines (min 50). 5 tests. |
| `tests/integration/test_migration_chain.py` | pristine → head, second run no-op | ✓ VERIFIED | 150 lines (min 30). 3 tests. |
| `tests/architecture/test_tenant_coverage.py` | eight-schema walk with `GLOBAL_TABLES` | ✓ VERIFIED | 171 lines, contains `GLOBAL_TABLES` and `pg_policies`. |
| `tests/unit/test_effective_dated_pricing.py` | day-5/12/20, boundary, not-yet-effective | ✓ VERIFIED | 195 lines (min 70). 8 tests. |
| `tests/unit/test_cost_arithmetic.py` | exact decimal, 10dp banker's, sub-cent guard | ✓ VERIFIED | 214 lines (min 40). 6 tests. |
| `tests/integration/test_reprice_only_unpriced.py` | three CL-05 properties separately | ✓ VERIFIED | 359 lines (min 60). 6 tests. |
| `tests/integration/test_body_retention_delete.py` | CL-08 by direct owner query + chunking | ✓ VERIFIED | 360 lines (min 60). 8 tests. |

No artifact is MISSING, STUB or ORPHANED. Every source module is imported and exercised.

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/prope/db/session.py` | `alembic/versions/0002_call_record.py` | `set_config('app.workspace_id', :ws, true)` sets the GUC the policy predicate reads | ✓ WIRED | `session.py:41` sets it; `ddl.py:87` builds the predicate `workspace_id = current_setting('app.workspace_id', true)`. Same GUC name (`ddl.py:24` `TENANT_GUC`). Proven behaviourally by the tenant-isolation suite. |
| `tests/conftest.py` | `alembic/env.py` | the fixture runs `alembic upgrade head` before any session opens | ✓ WIRED | `conftest.py:77-86` builds an Alembic `Config` and calls `command.upgrade(config, "head")` inside the session fixture, before the app engines are constructed. |
| `alembic/versions/0003_ledger_tables.py` | `alembic/ddl.py` | every policy is an `enable_tenant_rls()` call, every grant a `grant_table()` call | ✓ WIRED | `0003:46` imports both; `:244` and `:252-262`. No raw `CREATE POLICY` or `GRANT` bypasses the helpers, so the guarantee is greppable by helper name. |
| `tests/architecture/test_tenant_coverage.py` | `pg_policies` | the walk reads `pg_class` and `pg_policies` for each of the eight declared schemas | ✓ WIRED | `LIST_TABLES` reads `pg_class`/`pg_namespace`; `LIST_POLICIES` reads `pg_policies`. |
| `src/prope/call_ledger/writer.py` | `src/prope/call_ledger/pricing.py` | the writer resolves a price at each draft's **own** `created_at` | ✓ WIRED | `writer.py:56` imports `resolve_price`; `:220-226` calls it with `at=draft.created_at`. Not wall-clock. |
| `src/prope/call_ledger/writer.py` | `src/prope/db/session.py` | the writer accepts only a session from `workspace_transaction()` | ✓ WIRED | `write_records(session: AsyncSession, ...)` opens no transaction and does not commit; `:190-196` refuses a batch spanning two workspaces before writing any of it. |
| `src/prope/call_ledger/repricing.py` | `src/prope/call_ledger/pricing.py` | repricing calls the same `resolve_price`/`compute_cost` the writer calls | ✓ WIRED | `repricing.py:48` — identical import. **One cost function, not two**, verified by grep: no second `compute_cost` exists in the tree. |
| `src/prope/call_ledger/retention.py` | `src/prope/db/session.py` | each chunk opens its own `workspace_transaction()` | ✓ WIRED | `retention.py:62` imports it; `:148` opens one **inside** the `while True` loop. Proven behaviourally by the `[7, 2, 0]` test. |

---

## Data-Flow Trace (Level 4)

| Value | Source | Flows | Status |
|-------|--------|-------|--------|
| `call_record.cost` | `compute_cost(tokens, resolve_price(...))` — a real `SELECT` against `ledger.price_table` | Yes — asserted equal to `compute_cost`'s own output on a live read-back | ✓ FLOWING |
| `call_record.price_row_id` | `price.price_row_id` from the resolved row; FK-enforced against `price_table` since `0003` | Yes | ✓ FLOWING |
| `workspace_spend.total_cost` | accumulated from priced costs, upserted with a real `ON CONFLICT DO UPDATE` | Yes — read back and asserted across two batches and two months | ✓ FLOWING |
| `WriteResult.unknown / .priced / .unpriced` | `counts[cost_status]` tallied per record | Yes — cross-checked against a live `count(*) FILTER (WHERE usage_status='unknown')` | ✓ FLOWING |
| `UNPRICED_WORKLIST` rows | `GROUP BY` over `ledger.call_record WHERE cost_status='unpriced'` | Yes — test executes the statement and asserts projection, count and `since` | ✓ FLOWING |
| `RepriceResult.repriced` | `result.rowcount` from the engine | Yes — counted from what the engine reports, not from the intending branch | ✓ FLOWING |
| `delete_expired_bodies` return | `result.rowcount` per chunk | Yes — anchored to a direct owner-connection survivor count | ✓ FLOWING |

No hardcoded literal, static return, or mock terminates any chain.

---

## Behavioural Spot-Checks

Run by the verifier in its own process. The container is `postgres:17` via testcontainers.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Per-chunk transaction commits observable mid-run (OQ-D) | `pytest tests/integration/test_body_retention_delete.py::test_per_chunk_transactions_are_visible_outside_the_running_loop` | passed | ✓ PASS |
| T-006 refusal has teeth (grant / observe / revoke mutation) | `pytest tests/security/test_append_only_privilege.py::test_the_append_only_refusal_has_teeth` | passed | ✓ PASS |
| ROADMAP SC 1 — day-20 row does not move a day-5 call | `pytest tests/unit/test_effective_dated_pricing.py::test_a_day_20_price_row_does_not_move_a_call_made_on_day_5` | passed | ✓ PASS |
| CL-05 — already-priced call byte-identical, whole tuple | `pytest tests/integration/test_reprice_only_unpriced.py::test_an_already_priced_call_is_unchanged_field_for_field` | passed (4 passed in 45.87 s) | ✓ PASS |
| ROADMAP SC 4 — expired bodies gone, records intact | `pytest tests/integration/test_body_retention_delete.py::test_expired_bodies_are_gone_and_their_call_records_are_intact` | passed | ✓ PASS |
| ROADMAP SC 2a — unpriced worklist returns the pair + count + `since` | `pytest tests/unit/test_missing_price_is_unpriced_not_zero.py::test_the_unpriced_worklist_returns_the_pair_with_its_count_and_since` | passed | ✓ PASS |
| ROADMAP SC 3 — no usage object → NULLs, not zeros | `pytest tests/unit/test_unknown_usage_never_zero.py::test_a_call_with_no_usage_object_stores_nulls_rather_than_zeros` | passed | ✓ PASS |
| ROADMAP SC 2b — no zero anywhere across all three cost states | `pytest tests/integration/test_write_path.py::test_no_zero_anywhere_in_a_mixed_batch_of_all_three_cost_states` | passed | ✓ PASS |
| Eight-schema tenancy coverage walk | `pytest tests/architecture/test_tenant_coverage.py::test_every_table_in_every_declared_schema_is_tenant_scoped` | passed (5 passed in 21.83 s) | ✓ PASS |
| **CR-01 mechanism** — a legal `(0,0)` price row prices to exactly zero | `uv run python -c "compute_cost(300,150, PriceRow(0,0))"` | `Decimal('0E-10')`, `cost <= 0` → `True` | ✓ CONFIRMED (defect is real) |
| Python pin | `uv run python -c "sys.version_info"` | `(3, 13, 14)` | ✓ PASS |

**Suite integrity:** the verifier counted **81 declared test functions** across the four test packages, which matches the orchestrator's independent `pytest -q` → *81 passed* exactly. There are **zero skips** — every live-database test genuinely ran.

---

## Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| — | — | No `scripts/*/tests/probe-*.sh` exists and no PLAN or SUMMARY declares one. | N/A — SKIPPED |

---

## Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| **CL-03** | 01-02, 01-03 | A call is priced at the price row in force at the call's own timestamp, and a price row added later never changes it | ✓ SATISFIED | ROADMAP SC 1 verified by verifier-run test; `resolve_price` binds `at=draft.created_at`; the day-20 row leaves cost and `price_row_id` byte-identical. REQUIREMENTS.md `[x]`, row **Complete**. |
| **CL-04** | 01-01, 01-03 | A call with no price row stores its tokens with cost `unpriced` — never zero — and appears on the unpriced worklist | ✓ SATISFIED | ROADMAP SC 2 verified by two verifier-run tests; `ck_call_record_cost_is_never_zero` + `ck_call_record_cost_state_is_coherent`; `ix_call_record_unpriced_worklist` partial index; `UNPRICED_WORKLIST` executed by test. REQUIREMENTS.md `[x]`, row **Complete**. |
| **CL-05** | 01-02, 01-04 | Repricing gives a previously unpriced call its cost and leaves an already-priced call untouched | ✓ SATISFIED | Both halves asserted separately; the already-priced half compares the **whole tuple** under an adversarially-seeded dearer superseding row, with a positive control proving the run did real work. REQUIREMENTS.md `[x]`, row **Complete**. |
| **CL-08** | 01-02, 01-04 | Call bodies past their retention window are deleted while their call records stay intact | ✓ SATISFIED | ROADMAP SC 4 verified by verifier-run test, checked on a direct `prope_migrate` connection. Chunking, bounding, cross-tenant safety and the exact-cut-off boundary each asserted. REQUIREMENTS.md `[x]`, row **Complete**. |
| **CL-11** | 01-01, 01-03 | A call whose provider returned no usage object records unknown tokens as null — never zero — **and the unknown count is reported alongside the total** | ⚠️ PARTIAL — clause 1 SATISFIED, clause 2 DEFERRED to Phase 2 | Clause 1: ROADMAP SC 3 verified by verifier-run test + `ck_call_record_unknown_usage_is_null` refusing the zero encoding at the engine. Clause 2 is `get_run_totals`, which ROADMAP assigns to **Phase 2 SC 3**. Phase 1 built and asserted the enabling encoding (`by_status == by_nulls`). REQUIREMENTS.md correctly `[ ]`, row **Pending**. |

**Orphaned requirements:** none. Every ID that REQUIREMENTS.md maps to Phase 1 (CL-03, CL-04, CL-05, CL-08, CL-11) is claimed by at least one plan's `requirements:` frontmatter, and no plan claims an ID outside that set.

### The CL-11 judgement — stated plainly

**Phase 1 IS goal-complete with CL-11 outstanding.** This is a deferral, not a gap. Three independent reasons:

1. **The ROADMAP splits CL-11 itself.** Phase 1 SC 3 is clause 1 verbatim, with the reporting clause absent. Phase 2 SC 3 is clause 2 verbatim, naming `get_run_totals`. The requirement was pre-split by the roadmap author across two phases; the plans did not descope anything.
2. **The phase goal does not include reporting.** "The `ledger` schema exists with all five tables, and a call's usage is priced correctly and irreversibly at write time" contains no read or reporting obligation. `get_run_totals` is a seam, and seams are Phase 2's stated subject ("Seams: enqueue, the broker drain, and the ceiling").
3. **Phase 1 delivered the part that makes clause 2 cheap, and asserted it.** The truth was carried as a `backstop`, and there is explicit evidence: the test asserts `count(*) FILTER (WHERE usage_status = 'unknown')` equals the null-token count and equals 1, so Phase 2's `get_run_totals` can compute the unknown count from the status column alone and cannot get a different answer. Had Phase 1 encoded a zero here, clause 2 would be unbuildable in Phase 2; it did not.

The executors were honest about this rather than papering over it — `01-03-SUMMARY.md:245-250` and `01-04-SUMMARY.md:242` both refuse to tick CL-11 and say why. That is the correct behaviour and the verifier confirms it against the ROADMAP.

**The one real problem is bookkeeping, not code.** REQUIREMENTS.md maps CL-11 to "Phase 1" and marks it "Pending", which means Phase 1 will look permanently unfinished to any future milestone audit. That is routed to human verification item 2.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | `TBD` / `FIXME` / `XXX` | — | **None found** in `src/`, `tests/`, `alembic/`, `Makefile`, `pyproject.toml`, `ruff.toml`, `alembic.ini`. The debt-marker gate passes. |
| — | — | `TODO` / `HACK` / `PLACEHOLDER` / "not yet implemented" / "coming soon" | — | **None found.** |
| — | — | Empty implementations, console-log-only bodies, hardcoded empty returns | — | **None found.** Every `return None` on a pricing path is a documented, tested semantic (`None` = unpriced), not a stub. |
| `src/prope/db/session.py` | 13-14 | Documented control that does not exist | ⚠️ Warning | See WARN-6. |
| `src/prope/call_ledger/retention.py` | 114-170 | Unvalidated public parameter → unbounded loop | ⚠️ Warning | See WARN-1. |

Working tree is clean apart from `.planning/config.json` and two untracked cache directories. All four plans are committed with conventional-commit messages and the review report is committed.

---

## The CR-01 judgement — stated plainly

**CR-01 is a real defect. It is NOT a Phase 1 goal gap. It IS a Phase 2 blocking pre-condition.**

I confirmed the mechanism independently rather than taking the review's word:

- `ck_price_table_prices_are_non_negative` (`0003:136-137`) is `>= 0 AND >= 0`, so `(0, 0)` is a legal row.
- `compute_cost(300, 150, PriceRow(0, 0))` returns `Decimal('0E-10')` — I ran it in-process; `cost <= 0` is `True`.
- `writer.py:237-250` raises `ValueError` on that record, and because the batch is all-or-nothing under the caller's transaction, **every record in the batch is discarded**.
- `repricing.py:172-180` behaves identically for the whole pass.
- The project's own `tests/unit/test_cost_arithmetic.py:158-161` already asserts `compute_cost(1, 0, tie) == Decimal("0")` for a *legal, non-zero* price of `0.00000005/1k`, so the hole is wider than the free-tier case.

**Why it does not falsify the phase goal.** The goal has two clauses and CR-01 breaks neither:

- *"priced correctly"* — no incorrect figure is ever stored. The failure mode is a **loud refusal**, not a silent zero. This is precisely the behaviour ADR-0019 asks for ("an absent figure asks a question, a wrong figure answers it"); the objection is that it asks the question by taking down the batch, which is an availability property, not a correctness one. ROADMAP SC 2's literal claim — "no row anywhere records a cost of zero" — is *upheld* by the very raise that CR-01 complains about.
- *"irreversibly at write time"* — untouched. Price rows remain append-only by privilege, proven by a live mutation test; a stored cost is never recomputed, proven by a whole-tuple comparison under an adversarial superseding row.

**Two corrections to the review's framing**, which matter to the severity:

1. *"the row can never be corrected or removed"* is true of `prope_app` only. `prope_migrate` owns `ledger` (`0001:62` `CREATE SCHEMA ledger AUTHORIZATION prope_migrate`, plus `assume_migrate_role()` before every `CREATE TABLE`), and RLS is `ENABLE`, never `FORCE`, so the owner bypasses the policy and holds implicit full privilege. A bad price row is removable by an out-of-band DBA action. That is unpleasant, not irrecoverable.
2. The **triggering state is unreachable through anything Phase 1 ships.** There is no route, no CLI and no exported helper that inserts a price row — `POST /api/v1/prices` is Phase 2's (`apis.exposes`). Only direct SQL as `prope_app` or `prope_migrate` can create the poison row today, and there is no drain yet to re-deliver a poison batch forever.

**Why it must not be forgotten.** Both halves of the exposure arrive together in Phase 2: the route that lets a human type `0` into a price field, and the broker drain that will re-deliver the same failing batch indefinitely. Fixing it then is a new revision plus a per-record exception — cheap, because T-006 makes *data* irreversible, not *DDL*. Fixing it after Phase 2 ships is expensive.

**Recommendation:** accept for Phase 1; enter CR-01 as a named, blocking pre-condition on the Phase 2 plan that builds `POST /api/v1/prices`, with the two tests the review specifies (a `(0,0)` row refused at insert; one unpriceable record not discarding its batch-mates). Routed to human verification item 1 because the phase-boundary call is the developer's, not the verifier's.

---

## Warnings (non-blocking, carried forward)

| # | Finding | Where | Why it is a warning and not a blocker |
|---|---------|-------|---------------------------------------|
| **WARN-1** | `delete_expired_bodies(chunk_size=0)` loops forever, opening a transaction per iteration (`0 < 0` is false, `max_chunks` defaults to `None`) | `retention.py:114-170` | A caller-error guard on a public keyword argument. No shipped call site passes 0 — there is no scheduler yet. Two lines of validation. Fix before Phase 2 wires an operator-supplied value. |
| **WARN-2** | The one-currency-per-workspace invariant is a read-then-write race: two concurrent drains can produce a USD-labelled total containing VND, which the CHECK cannot see | `writer.py:322-339` | Unreachable in Phase 1 — nothing invokes `write_records` concurrently, because there is no drain. Becomes live the moment Phase 2's worker runs more than one consumer. The fix (move the invariant into the `ON CONFLICT ... WHERE`) belongs with the drain. |
| **WARN-3** | "Exactly one policy" is asserted only for `call_record`; the coverage walk checks ≥1 for the other four tables | `test_tenant_coverage.py:125-127` vs `test_call_record_guarantees.py:170` | The property **holds** — `enable_tenant_rls` is called exactly once per table and issues exactly one `CREATE POLICY` — so no truth fails. What is missing is the regression gate: PostgreSQL ORs permissive policies, so a future second policy on `call_body` would widen access silently. Extend the walk to assert one policy per table. |
| **WARN-4** | Intra-schema FKs bypass RLS. `fk_call_body_call_id` permits a workspace-B body referencing a workspace-A record — invisible to A and never swept by A's retention. `pk_call_record` is `(call_id)` alone, so a caller-supplied duplicate id leaks a cross-tenant existence oracle | `0003:88-89, 222-226`; `domain.py:114-127` | No Phase 1 code can create such a row — the writer stamps body and record from the same draft. The exposure arrives with Phase 3's caller-supplied ids and the refusal-shape rules. The schema principle as tested ("no FK leaves `ledger`") is narrower than the principle as stated ("an FK bypasses row security"); the test should assert every FK on a tenant-scoped table carries `workspace_id`. |
| **WARN-5** | Revision 0001's `REVOKE ALL ON SCHEMA public FROM PUBLIC` removes `USAGE`, and nothing grants `prope_migrate` any privilege on `public`, where `env.py` pins `alembic_version` | `0001:68` | **Structurally unverifiable in this rig** — the testcontainers connection is a superuser, so the failure cannot be observed here. `0001:9-15` flags it as assumption A9. Routed to human verification item 3. |
| **WARN-6** | `session.py:13-14` claims "a source gate asserts it" for the no-interpolation property. **No such gate exists** — grep for `getsource`/`inspect.` returns nothing in the suite | `src/prope/db/session.py:13-14` | The property itself is TRUE — I read the module and grepped `src/`: every f-string is error-message construction and no runtime value reaches SQL. But a shipped docstring naming a control that does not exist is worse than no claim, because the next reader will trust it. Either write the four-line gate or delete the sentence. |
| **WARN-7** | Token counts have no non-negativity constraint in the schema or in `CallRecordDraft.__post_init__`; `compute_cost` type-guards the price rigorously but applies `Decimal()` to whatever token value it is handed | `0002:70-71`; `domain.py:162-173` | A negative `input_tokens` passes every current check and can understate a stored cost while still satisfying `cost > 0`. Not reachable from any Phase 1 caller, since Phase 1 has no untrusted input path. Add the CHECK where "no row anywhere" is already stated. |
| **WARN-8** | `make check` runs `ruff format` (in-place, always exit 0), so the verification target mutates the tree it verifies and can never fail on formatting | `Makefile:16-22` | Affects CI hygiene, not the phase goal. Split `format` from `format-check`. |
| **WARN-9** | `reprice_unpriced` is unbounded: no `LIMIT`, `.all()` materialised, one round trip per candidate, all inside one caller transaction | `repricing.py:138-196` | Correctness is fine; this is the exact hazard `retention.py:20-29` argues against at length for the delete path, and repricing was not given the same shape. Chunking costs nothing in correctness because the status predicate makes it idempotent. |

---

## Info

- **INFO-1** — `RepriceResult.examined` under-reports when an `UPDATE` matches nothing (the concurrent-repricing case). Cosmetic.
- **INFO-2** — `uq_price_table_workspace_id` has no negative test attempting a duplicate insert. The constraint is declared inside a `CREATE TABLE` that provably succeeded, so enforcement is definitional; a test would still document the intent.
- **INFO-3** — `tests/integration/test_write_path.py:69` projects `request_body, response_body`. This is a test assertion over synthetic strings on an owner connection, not a module surface, so the 01-04 prohibition holds. Flagged so Phase 3's no-read-path enumeration does not mistake it for one, and does not skip it either.
- **INFO-4** — Eight pre-existing lint violations in `scripts/` are excluded via `ruff.toml` and itemised in `deferred-items.md`. All pre-date the phase; the `.ai-log` tooling is a scaffold remnant, not Prope code. Correctly recorded rather than silently dropped.
- **INFO-5** — A stale `tests/integration/__pycache__/test_zz_scratch_privilege_probe.*.pyc` exists with no source file — the remnant of a deleted scratch probe. Harmless; `__pycache__` is not tracked.
- **INFO-6** — Implementation decisions D-01 through D-08 from `01-CONTEXT.md` were each verified honoured. D-07's wording ("REVOKE UPDATE, DELETE ON ledger.price_table") was implemented in the equivalent positive-grant form (grant only `SELECT, INSERT` after `REVOKE ALL FROM PUBLIC`); `ddl.py:106-110` documents the choice and the end state is identical.
- **INFO-7** — OQ-A (uncast text RLS predicate), OQ-C (no cross-tenant sweep), OQ-D (one transaction per chunk) and OQ-E (unknown, not a zero) were each decided in code, each documented at the decision site, and each carried upstream unedited rather than silently patching the ADR. The `::uuid` absence is asserted against `pg_policies`, not merely against prose.

---

## Gaps Summary

**No gaps.** No must-have truth failed, no artifact is missing or a stub, no key link is unwired, no data-flow chain terminates in a mock or a literal, and no debt marker was introduced. The phase goal — the `ledger` schema with all five tables, and correct, irreversible write-time pricing — is achieved and was re-proven by this verifier against a live PostgreSQL 17 rather than read off the SUMMARYs.

What holds this report at `human_needed` rather than `passed` is four decisions that belong to a person:

1. **CR-01's disposition.** A real defect, confirmed in-process, that does not falsify the goal but becomes live the moment Phase 2 ships a price-row route and a drain. It needs to be *entered somewhere*, and only the developer can decide where.
2. **CL-11's traceability.** The code is right; REQUIREMENTS.md and ROADMAP.md disagree with each other about who owes clause 2.
3. **Revision 0001 against a non-superuser deploy path.** Structurally unobservable in a rig whose container connection is a superuser.
4. **The cost quantum and the retention window** as business figures rather than as internally-consistent constants.

The engineering quality here is unusually high and the verifier wants that on the record, because it is the reason the report is short on findings rather than the report being lenient: nearly every negative assertion carries a positive control; `test_the_append_only_refusal_has_teeth` is a genuine mutation check that would catch the refusal tests passing for the wrong reason; and `test_per_chunk_transactions_are_visible_outside_the_running_loop` proves a transaction-boundary property from outside an in-flight loop — with a docstring that names and rejects the easier, worthless version of the same test. Those are the two places a phase like this usually lies to itself, and neither one does.

---

_Verified: 2026-08-10T04:32:16Z_
_Verifier: Claude (gsd-verifier)_
