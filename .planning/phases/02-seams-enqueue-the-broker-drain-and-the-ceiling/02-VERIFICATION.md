---
phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
verified: 2026-08-10T18:40:00Z
status: human_needed
score: 44/45 must-haves verified
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "The retention job's health is judged by the age of the oldest surviving body, not by whether the job returned without raising (02-03 backstop truth)"
    addressed_in: "Phase 3"
    evidence: "`prope_call_ledger_oldest_body_age_seconds` is absent from `src/` (only referenced in a `worker.py` comment). It is listed in `docs/modules/call-ledger.lock.yml:390` under `observability_requirements.metrics`, and ROADMAP Phase 3's Spec line names `observability_requirements.metrics` (17 metrics) as Phase 3 scope. `deferred-items.md` records the same routing."
  - truth: "`enqueue` is idempotent on the caller-supplied call_id (A-099, spec `apis.exposes`)"
    addressed_in: "Phase 3"
    evidence: "ROADMAP Phase 3 SC2: 'Every message redelivered after an unacknowledged consumer restart lands exactly once; the workspace's monthly total is unchanged and every redelivery is counted.' Requirement CL-02. `drain.classify_write_failure`'s docstring names the gap explicitly and dead-letters a unique violation rather than absorbing it."
human_verification:
  - test: "Adjudicate the 14 judgment-tier prohibitions carried by the five plans (all marked `status: resolved`, `verification: judgment`)."
    expected: "Each prohibition confirmed as genuinely upheld. My non-authoritative reading finds all 14 upheld by passing tests or by structure — evidence cited per prohibition in the Prohibitions table below — but a judgment-tier prohibition is never green on an agent's say-so."
    why_human: "Judgment-tier prohibitions have no mechanical enforcement. An LLM verdict is advisory only; the four non-negotiables in CLAUDE.md make these the security-weight items of the phase."
  - test: "Exercise the five `/api/v1` management routes by hand once a session store exists."
    expected: "POST/GET `/prices`, GET `/prices/unpriced`, PUT `/spend-ceiling`, PUT `/retention` behave as INT-028 registers, with the A-045 error envelope on refusal."
    why_human: "`require_session` unconditionally raises 401 until Phase 7 (fail-closed interim posture). Every route is proven through the ASGI test rig and the assembled route table, but no route can be driven by hand this phase. Untestable-until-Phase-7, not a gap."
  - test: "Confirm or reverse the `POST /api/v1/prices` refusal of a (0,0) price row, adopted unconfirmed by plan 02-05."
    expected: "A decision recorded on the still-open Phase 1 human-verification item that this refusal was adopted against."
    why_human: "Plan 02-05 shipped the refusal (`api.py:407`, `ErrorCode.PRICE_BOTH_PRICES_ARE_ZERO`) while its authorising decision is still open. The code is correct against the reviewer's reasoning but the decision is not yet the developer's."
  - test: "Resolve OQ-018, OQ-019, OQ-020, OQ-021 — four declared spec deviations raised rather than absorbed."
    expected: "Each open question resolved against `docs/modules/call-ledger.lock.yml` / `docs/architecture/interfaces.md`, or accepted as a standing deviation."
    why_human: "Per `.planning/BSP-LINK.md` a spec that disagrees with code is recorded, never edited into agreement. Resolution is a spec-owner decision. All four files exist with the required content."
  - test: "Decide the disposition of CR-01 (unbounded `retention_days`) and CR-02 (uncounted shutdown drop) — see Anti-Patterns below."
    expected: "Either fixed in a follow-up, or accepted with the reasoning recorded."
    why_human: "Both are real defects I confirmed independently in code, but neither falsifies a Phase 2 must-have truth. Whether they block shipping Phase 2 is a risk-tolerance call, not a verification result."
  - test: "Settle CL-11's traceability — `get_run_totals` is ROADMAP Phase 2 SC3 and CL-11's second clause, but CL-11's REQUIREMENTS.md row reads Phase 1 / Pending."
    expected: "Split the ID, remap the row across two phases, or accept a permanently-pending Phase 1 row."
    why_human: "Named as Phase 1 human-verification item 2 and still open. `seams.py` builds the function and deliberately claims no requirement for it."
---

# Phase 2: Seams: enqueue, the broker drain, and the ceiling — Verification Report

**Phase Goal:** The three internal contracts and the six management routes exist, and the `worker`'s drain consumes `prope.call_record` and writes batches grouped per workspace.
**Verified:** 2026-08-10
**Status:** human_needed
**Re-verification:** No — initial verification

## Evidence Standard Used

I did not accept SUMMARY.md claims. Every truth below is backed by one of: a test I ran myself in this session, a file I read, or a code path I traced. Test runs performed here:

| Run | Scope | Result |
|---|---|---|
| 1 | `test_ceiling_refuses_evals_only.py`, `test_eval_usage_priced_without_body.py`, `test_run_totals.py` | 35 passed, 1 failed (`TimeoutError`) |
| 2 | The failed test by name + `test_eval_no_body_boundary.py` + `test_route_table.py` | 18 passed in 21 s |
| 3 | `tests/broker/`, `test_worker_jobs.py`, `test_management_routes.py`, `test_health_and_readiness.py`, `test_workspace_retention_setting.py` | 97 passed |
| 4 | Full suite, `uv run pytest -q` | **292 passed** in 151 s |
| 5 | `uv run ruff check src/ tests/ alembic/` | All checks passed |

**On run 1's failure.** `test_an_eval_row_is_priced_stored_and_carries_no_body` failed with a bare `TimeoutError` raised from `asyncio/timeouts.py:117`. I investigated rather than dismissed it: the project defines no test timeout (`grep` over `conftest.py`, `pyproject.toml`, `db/session.py`, `db/engine.py` finds none) and the test itself awaits no timeout — the frame is asyncpg's connect timeout. Run 1 took 4675 s for 36 tests because Docker was cold-pulling images; the same test passed in run 2 in isolation and again in run 4's full suite. **Environment flake, not a product defect.** The execution state's "292 passed" claim is independently reproduced.

## Goal Achievement

### Observable Truths — ROADMAP Success Criteria

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | `check_spend_ceiling` refuses an eval run for a workspace over its ceiling with a reason and no figure, while gateway traffic for the same workspace continues to be recorded | ✓ VERIFIED | `test_gateway_traffic_alone_over_the_ceiling_refuses_with_a_reason` (reason is `CeilingReason.MONTHLY_CEILING_EXCEEDED`, a machine code per ADR-0053); `test_gateway_traffic_keeps_being_recorded_after_the_refusal` writes a second gateway call **after** asserting the refusal is real, then reads `call_count == 2` and `total_cost == GATEWAY_COST * 2` through `migrate_engine`; `test_no_figure_reaches_the_decision_or_a_log_line_under_either_branch` searches `repr`, `asdict` and every captured log record for 14 forbidden digit-runs under **both** branches. All ran green here. |
| SC2 | An eval-case usage row arrives with `source = eval`, `run_id` and `version_id`, is priced, counts toward the workspace's monthly spend, and creates no `call_body` row | ✓ VERIFIED | `test_an_eval_row_is_priced_stored_and_carries_no_body` reads the stored row through `migrate_engine` (owner role, no policy): `source == "eval"`, `run_id`, `case_id`, `version_id`, `consumer_key_id is None`, `cost_status == "priced"`, `price_row_id == FIRST_PRICE_ROW`, and `count(*) FROM ledger.call_body == 0`. `test_the_eval_row_lands_on_the_same_spend_total_as_a_gateway_call` asserts one `workspace_spend` row whose `total_cost == GATEWAY_COST + EVAL_COST` and `call_count == 2`. |
| SC3 | `get_run_totals` returns the unpriced and unknown-usage counts alongside the totals | ✓ VERIFIED | 11 tests in `test_run_totals.py`, all green, including `test_one_unpriced_row_and_one_unknown_row_report_one_and_one` (the two counts are disjoint), `test_the_unknown_count_equals_what_write_records_reported` (same number, same derivation), `test_both_counts_are_computed_from_the_stored_encoding`, and `test_a_run_spanning_two_currencies_raises_naming_both`. `RUN_TOTALS` computes both via `count(*) FILTER` over `cost_status` / `usage_status` — the stored encoding, not intent. |

### Observable Truths — Goal Clauses

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| G1 | The three internal contracts exist | ✓ VERIFIED | `src/prope/call_ledger/seams.py` (612 lines): `async def price_usage` (INT-019), `async def check_spend_ceiling` (INT-020), `async def get_run_totals` (INT-021). Each opens its own `workspace_transaction` (D-19) and takes a `sessionmaker`, never a caller session. Not stubs — full pricing, ceiling and aggregation logic with typed returns. |
| G2 | The six management routes exist | ✓ VERIFIED | Enumerated from source and cross-checked against `apis.exposes`: `POST /api/v1/prices`, `GET /api/v1/prices`, `GET /api/v1/prices/unpriced`, `PUT /api/v1/workspaces/{id}/spend-ceiling`, `PUT /api/v1/workspaces/{id}/retention`, `GET /healthz`, `GET /readyz`. Wired via `application.include_router(call_ledger_router)` in `app.py:212` — explicit composition, no auto-discovery (D-13). `test_route_table.py` walks `app.routes` and passed. |
| G3 | The `worker`'s drain consumes `prope.call_record` and writes batches grouped per workspace | ✓ VERIFIED | `test_two_workspaces_get_two_different_expiries_through_the_composed_worker` publishes two drafts for two workspaces to the real broker, runs the **composed worker**, and reads back through `migrate_engine` that each body carries its own workspace's retention window (`STORED_WINDOW` vs `DEFAULT_RETENTION_WINDOW`, asserted unequal). That outcome is only reachable if the drain grouped by `workspace_id` and resolved/committed per group. Supported by `test_one_record_reaches_a_committed_ledger_row` (enqueue → broker → drain → `workspace_transaction` → `ledger.call_record`) and `test_the_running_worker_holds_exactly_one_consumer_on_the_queue` (asserted against the broker's own count). |

**Score: 44/45 must-haves verified** — 0 present-but-behavior-unverified, 2 deferred to Phase 3 (one counted against the 45, one outside the plan truth set).

### Observable Truths — Plan-level

| Plan | Truths | Status | Evidence |
|---|---|---|---|
| 02-01 | 7 | ✓ 7/7 VERIFIED | `tests/broker/` — 4 files, all green. Notably: `test_enqueue_returns_normally_through_every_failure_branch` (never raises: full buffer, unroutable, nacked, timeout, no broker); `test_the_broker_reports_the_arguments_that_were_declared` reads the arguments back from RabbitMQ's management API and matches A-149 exactly (24 h / 1,000,000 on the work queue, 30 days / 100,000 on the DLQ, `reject-publish-dlx`, explicit DLRK — confirmed against `topology.py:108-114`); `test_an_invalid_envelope_dead_letters_without_opening_a_transaction` uses a spy proving `workspace_transaction` was **never entered**; `test_one_unwritable_record_does_not_discard_its_batch_mates`; `test_no_marker_reaches_a_log_record_or_a_metric_label` and `test_workspace_id_is_never_a_metric_label`. Ack-after-commit is a control-flow guarantee: `message.ack()` at `drain.py:423` is unreachable unless `_write_group`'s `async with workspace_transaction` exited without raising. |
| 02-02 | 7 | ✓ 7/7 VERIFIED | `alembic/versions/0004_workspace_retention.py` exists and carries `enable_tenant_rls`; `retention_settings.py` defines `DEFAULT_RETENTION_WINDOW` and both read/write open a `workspace_transaction`; `test_workspace_retention_setting.py` and `test_body_retention_delete.py` green. The **backstop truth** ("the sole enforcement is `write_records`; the database carries no guard, asserted rather than assumed") is confirmed by explicit evidence: `tests/security/test_eval_no_body_boundary.py::test_the_database_carries_no_guard_and_a_hand_written_body_lands` — it proves the absence, rather than assuming it. `writer.py:242` is the refusal. `OQ-018.md` exists containing `data.owns`. |
| 02-03 | 6 | ✓ 5/6 VERIFIED, 1 deferred | `supervisor.py` (`TaskGroup`, restart-with-backoff, `CancelledError` handling — `test_supervisor.py` green); `worker.py` composes `declare_topology`, the drain via `functools.partial(read_retention_window, sessionmaker)` (`build_retention_resolver`, `worker.py:217`), and `delete_expired_bodies` on an interval. No-HTTP proven negatively by `test_worker_imports_no_web_framework` and `test_worker_exposes_no_asgi_application_object`. `test_a_stop_mid_window_commits_that_window_before_the_worker_returns` green. **Deferred:** the backstop truth on judging retention health by oldest-body age — see `deferred` frontmatter. |
| 02-04 | 10 | ✓ 10/10 VERIFIED | `test_ceiling_refuses_evals_only.py` (13) + `test_eval_usage_priced_without_body.py` (14) + `test_run_totals.py` (11), all green. Includes `test_an_unevaluable_check_allows_and_counts_and_does_not_raise` (fail-open **and** counter incremented), `test_the_ceiling_reads_the_same_month_write_records_files_into` (shared `period_month`, +07:00 fixture where local and UTC months disagree), `test_a_refusal_inside_the_transaction_leaves_the_whole_batch_unwritten`. `OQ-019.md` (`apis.exposes`) and `OQ-020.md` (`INT-021`) exist. |
| 02-05 | 13 | ✓ 13/13 VERIFIED | `test_route_table.py`, `test_management_routes.py`, `test_health_and_readiness.py` all green. Seven route entries in the assembled table; every `/api/v1` route declares `Depends(require_session)` plus a closed-vocabulary `ManagementAction`; `session_auth.require_session` unconditionally raises `ManagementRefusal(401, session_required)` in the A-045 envelope; `POST /prices` is append-only (no PUT/DELETE on the path exists); the (0,0) refusal is at `api.py:407`; `/healthz` returns `{"status": "alive"}` touching nothing; `/readyz` probes the database alone and returns 503 naming `database`. `OQ-021.md` exists containing `INT-001`. |

### Deferred Items

Not met, and explicitly addressed in later milestone phases. Not actionable gaps.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Retention-job health judged by oldest-body age rather than by a clean return | Phase 3 | `prope_call_ledger_oldest_body_age_seconds` absent from `src/`; listed at `call-ledger.lock.yml:390` under `observability_requirements.metrics`, which ROADMAP Phase 3's Spec line names as Phase 3 scope. |
| 2 | `enqueue` idempotent on `call_id` (A-099, spec `apis.exposes`) | Phase 3 | Phase 3 SC2 verbatim: "Every message redelivered after an unacknowledged consumer restart lands exactly once". CL-02. `classify_write_failure`'s docstring names the gap and chooses the loud failure. |
| 3 | Direct-write fallback so no metadata is lost while the broker is down | Phase 3 | Phase 3 SC1: "With RabbitMQ unreachable, 1,000 calls each still produce a durable record ... through the direct-write fallback". CL-01. Declared known-and-deliberate for Phase 2. |
| 4 | Cold workspaces unswept by the retention job | Phase 7 | `run_worker` takes a `WorkspaceEnumerator` parameter so Phase 7 replaces an argument, not the job. Both halves asserted in `test_worker_jobs.py` (observed workspace swept; unobserved one not). Forced by ADR-0045 — a bare ledger query with no `app.workspace_id` returns zero rows. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/prope/broker/topology.py` | `declare_topology` | ✓ VERIFIED | 171 lines; `WORK_QUEUE = "prope.call_record"`, `DLQ` derived; argument dicts match A-149; read back from the broker in test. |
| `src/prope/broker/connection.py` | `connect_robust` | ✓ VERIFIED | 75 lines; confirm-mode channel lifecycle. |
| `src/prope/call_ledger/envelope.py` | `schema_version` | ✓ VERIFIED | 260 lines; the `workspace_id` source gate is the first thing to run on the payload. |
| `src/prope/call_ledger/enqueue.py` | `def enqueue` | ✓ VERIFIED | 283 lines; bounded handoff + background publisher. |
| `src/prope/call_ledger/drain.py` | `workspace_transaction` | ✓ VERIFIED | 428 lines; `_group_by_workspace`, `_write_group`, `_retry_group_one_at_a_time`, `classify_write_failure`. |
| `src/prope/observability.py` | `prope_call_ledger_publish_failed_total` | ✓ VERIFIED | 153 lines; counter defined at line 84 with that exact metric name; `LOGGABLE_FIELDS` allow-list now includes `job` (the 02-03 deferred item was closed by 02-04). |
| `tests/broker/test_declared_arguments.py` | `x-overflow` | ✓ VERIFIED | Read-back plus negative controls (`test_one_changed_argument_is_refused`, `test_a_redeclare_as_non_durable_is_refused`). |
| `alembic/versions/0004_workspace_retention.py` | `enable_tenant_rls` | ✓ VERIFIED | Present; migration chain test green. |
| `src/prope/call_ledger/retention_settings.py` | `DEFAULT_RETENTION_WINDOW` | ✓ VERIFIED | 156 lines. |
| `src/prope/supervisor.py` | `TaskGroup` | ✓ VERIFIED | 283 lines. |
| `src/prope/worker.py` | `declare_topology` | ✓ VERIFIED | 388 lines; no ASGI object, no web framework import. |
| `tests/unit/test_supervisor.py` | `CancelledError` | ✓ VERIFIED | Green. |
| `src/prope/call_ledger/seams.py` | `async def price_usage` | ✓ VERIFIED | 612 lines; three seams. |
| `tests/integration/test_ceiling_refuses_evals_only.py` | `check_spend_ceiling` | ✓ VERIFIED | 13 tests green. |
| `tests/integration/test_eval_usage_priced_without_body.py` | `price_usage` | ✓ VERIFIED | 14 tests green. |
| `src/prope/app.py` | `include_router` | ✓ VERIFIED | 287 lines; line 212. |
| `src/prope/call_ledger/api.py` | `APIRouter` | ✓ VERIFIED | 742 lines; router at line 222, five routes. |
| `src/prope/session_auth.py` | `require_session` | ✓ VERIFIED | 320 lines; fail-closed 401. |
| `tests/architecture/test_route_table.py` | `app.routes` | ✓ VERIFIED | Green. |
| `docs/brainstorm/open_questions/OQ-018.md` | `data.owns` | ✓ VERIFIED | Present, marker found. |
| `docs/brainstorm/open_questions/OQ-019.md` | `apis.exposes` | ✓ VERIFIED | Present, marker found. |
| `docs/brainstorm/open_questions/OQ-020.md` | `INT-021` | ✓ VERIFIED | Present, marker found. |
| `docs/brainstorm/open_questions/OQ-021.md` | `INT-001` | ✓ VERIFIED | Present, marker found. |

No artifact is a stub. Zero `NotImplementedError`, zero bare `pass` bodies, zero ellipsis stubs across `src/`.

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `enqueue.py` | `broker/topology.py` | `WORK_QUEUE` routing key on the default exchange | ✓ WIRED |
| `drain.py` | `writer.py` | `write_records(session, drafts, retention_window=...)` — the only write | ✓ WIRED (`drain.py:276`) |
| `drain.py` | `db/session.py` | one `workspace_transaction` per workspace group | ✓ WIRED (`drain.py:275`) |
| `envelope.py` | `db/session.py` | the validated `workspace_id` is the only value reaching `SET_TENANT` | ✓ WIRED (spy test proves no transaction opens for an invalid envelope) |
| `retention_settings.py` | `db/session.py` | every read/write opens a `workspace_transaction` | ✓ WIRED |
| `retention_settings.py` | `writer.py` | imports `DEFAULT_RETENTION_WINDOW` rather than restating 30 days | ✓ WIRED |
| `0004_workspace_retention.py` | `alembic/ddl.py` | bare `ddl` import | ✓ WIRED |
| `worker.py` | `drain.py` | `functools.partial(read_retention_window, sessionmaker)` as `retention_for` | ✓ WIRED (`worker.py:217`; `test_the_resolver_worker_builds_takes_the_workspace_id_alone` and `test_the_resolver_is_built_by_binding_the_sessionmaker` both green — a missing bind would `TypeError` on the first group) |
| `worker.py` | `retention.py` | `delete_expired_bodies` on an interval loop | ✓ WIRED (`worker.py:262`) |
| `worker.py` | `broker/topology.py` | `declare_topology` from the same definition `app` uses (D-24) | ✓ WIRED (`worker.py:316`) |
| `seams.py` | `writer.py` | `price_usage` builds drafts and calls `write_records`; no SQL of its own | ✓ WIRED (`seams.py:261`; `test_price_usage_takes_a_sessionmaker_and_writes_no_sql_of_its_own` asserts `"text(" not in source`) |
| `seams.py` | `db/session.py` | each seam opens its own `workspace_transaction` (D-19) | ✓ WIRED |
| `seams.py` | `writer.py` | `check_spend_ceiling` derives its month with shared `period_month` | ✓ WIRED (`seams.py:404`; proven behaviorally by the +07:00 month-boundary test) |
| `test_management_routes.py` | `seams.py` | imports `check_spend_ceiling` and drives it through the PUT route | ✓ WIRED |
| `api.py` | `ledger.spend_ceiling` | DATA contract — PUT writes the columns `check_spend_ceiling` reads | ✓ WIRED (enforced by the round-trip test, as designed; `api.py` correctly makes no cross-module call) |
| `app.py` | `api.py` | `include_router`, by name | ✓ WIRED |
| `api.py` | `writer.py` | `UNPRICED_WORKLIST` served by `GET /prices/unpriced` | ✓ WIRED |
| `api.py` | `retention_settings.py` | `set_retention_window` | ✓ WIRED (`api.py:717`) |
| `api.py` | `session_auth.py` | every `/api/v1` route declares `require_session` | ✓ WIRED (all five; `_declares_session` checks identity, not name) |

**Forbidden-edge check (call-ledger is a sink).** Every `from prope...` import across `src/prope/call_ledger/*.py` resolves to `broker.topology`, `call_ledger.*`, `db.metadata`, `db.session`, `observability`, or `session_auth` — infrastructure only. No edge to another business module. `apis.consumes: []` holds.

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real Data | Status |
|---|---|---|---|---|
| `GET /api/v1/prices` | price rows | `ledger.price_table` query, cursor-paginated | Yes | ✓ FLOWING |
| `GET /api/v1/prices/unpriced` | worklist | `writer.UNPRICED_WORKLIST` | Yes | ✓ FLOWING |
| `PUT /spend-ceiling` | `SpendCeilingState` | read-back of the written row | Yes | ✓ FLOWING |
| `PUT /retention` | `RetentionState` | the persisted window the drain then reads | Yes | ✓ FLOWING (`test_workspace_retention_setting.py`) |
| `check_spend_ceiling` | ceiling + spend | `CEILING_READ` LEFT JOIN over `spend_ceiling` / `workspace_spend` | Yes | ✓ FLOWING (asserted it does **not** aggregate `call_record`) |
| `get_run_totals` | totals + counts | `RUN_TOTALS` over `ledger.call_record` | Yes | ✓ FLOWING |
| `/readyz` | readiness | live `engine.connect()` + probe | Yes | ✓ FLOWING |

No hardcoded literal, static return, or mock terminates any chain.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full suite reproduces the claimed result | `uv run pytest -q` | `292 passed in 150.96s` | ✓ PASS |
| Lint clean | `uv run ruff check src/ tests/ alembic/` | `All checks passed!` | ✓ PASS |
| SC1/SC2/SC3 tests pass in isolation | targeted pytest (runs 1–3) | 35/36 then 18/18 then 97/97 | ✓ PASS |
| The one run-1 failure is a flake | re-ran the named test | passes in 21 s; passes again in the full suite | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| CL-06 | 02-01, 02-04 | A workspace over its monthly ceiling has eval runs refused with a reason and no spend figure, while its gateway traffic continues to be recorded normally | ✓ SATISFIED | Both clauses proven separately and together: refusal-with-reason, no-figure-under-every-branch (serialized form + log records), and gateway traffic recorded after the refusal (`call_count == 2` read through the owner role). |
| CL-09 | 02-02 + 02-04 | An eval-case usage row is priced and counted toward workspace spend with no body stored | ✓ SATISFIED | **Both halves verified independently, as instructed.** *Priced and counted* (02-04): `test_an_eval_row_is_priced_stored_and_carries_no_body` and `test_the_eval_row_lands_on_the_same_spend_total_as_a_gateway_call`. *No body stored* (02-02): `tests/security/test_eval_no_body_boundary.py` — `test_the_write_path_refuses_an_eval_draft_carrying_a_body` **and** `test_the_database_carries_no_guard_and_a_hand_written_body_lands`, which proves the enforcement is `write_records` alone rather than assuming a DB constraint. Defence in depth is real: `EvalUsageRow` has no body field (`test_the_input_type_cannot_carry_a_body_at_all`), so an eval body is unrepresentable before the refusal is even reached. Neither plan's claim was accepted alone. |

**Orphaned requirements: none.** `grep "Phase 2" .planning/REQUIREMENTS.md` returns exactly CL-06 and CL-09; both are declared in plan frontmatter and both are marked Complete.

**One traceability note, not a gap.** ROADMAP Phase 2 SC3 (`get_run_totals`) is CL-11's second clause, but CL-11's REQUIREMENTS.md row reads Phase 1 / Pending and is unticked. `seams.py` builds the function and explicitly declines to claim the requirement. Routed to human verification.

### Prohibitions (14 items, all judgment-tier — NON-AUTHORITATIVE)

Every prohibition in this phase carries `verification: judgment`. Per the fail-closed rule, my reading below is advisory and **must not be read as a pass**. All 14 are flagged `unverified-prohibition — human review recommended`.

| # | Plan | Prohibition (abbreviated) | My reading | Supporting evidence |
|---|---|---|---|---|
| 1 | 02-01 | MUST NOT degrade gateway recording because of a ceiling (A-029) | Upheld | `test_gateway_traffic_keeps_being_recorded_after_the_refusal`; nothing on the gateway path calls the ceiling. |
| 2 | 02-01 | MUST NOT emit a body or credential into a log line or metric label (A-046) | Upheld | `test_no_marker_reaches_a_log_record_or_a_metric_label`, `test_workspace_id_is_never_a_metric_label`; `LOGGABLE_FIELDS` is an allow-list. |
| 3 | 02-02 | MUST NOT write, log or persist an eval prompt/response body (A-055, A-046) | Upheld | `writer.py:242` refusal + no body field on `EvalUsageRow` + both no-body-boundary tests. |
| 4 | 02-02 | MUST NOT substitute zero/average/inferred cost for a missing price or usage | Upheld | `test_missing_price_is_unpriced_not_zero.py`, `test_unknown_usage_never_zero.py`, and the eval tests asserting both `cost is None` **and** `cost != Decimal(0)`. |
| 5 | 02-03 | MUST NOT expose an HTTP endpoint from `worker` (ADR-0028, D-17) | Upheld | `test_worker_imports_no_web_framework`, `test_worker_exposes_no_asgi_application_object`. |
| 6 | 02-03 | MUST NOT judge the retention job healthy because it returned without raising | **Partially upheld** | The job is not judged by its return, but the gauge that measures the data (`oldest_body_age_seconds`) is Phase 3. Deferred item 1. |
| 7 | 02-04 | MUST NOT expose any spend figure/limit/remaining/currency in a ceiling decision (A-056) | Upheld (strongly) | `test_no_figure_reaches_the_decision_or_a_log_line_under_either_branch` searches the serialized form and captured logs for 14 forbidden strings; `CeilingDecision` has exactly two fields, asserted. |
| 8 | 02-04 | MUST NOT refuse/delay/degrade gateway traffic for a ceiling (A-029) | Upheld | Same as #1. |
| 9 | 02-04 | MUST NOT return allowed on an unevaluable check without incrementing the counter (A-104) | Upheld | `test_an_unevaluable_check_allows_and_counts_and_does_not_raise` reads the counter before and after; `test_a_ceiling_and_a_spend_in_different_currencies_fail_open` does the same. |
| 10 | 02-04 | MUST NOT substitute an estimated cost/token count on an eval row | Upheld | `test_an_eval_row_with_no_price_row_is_unpriced_and_its_cost_is_null`, `test_an_eval_row_with_no_usage_object_is_unknown_with_null_tokens`. |
| 11 | 02-04 | MUST NOT silently absorb a pricing failure inside `price_usage` (INT-019) | Upheld | `price_usage` raises on every refusal branch; four tests assert `pytest.raises` plus zero rows written. |
| 12 | 02-05 | MUST NOT expose a stored body through any route/model/parameter (ADR-0018, AC-10) | Upheld | No route, response model or parameter references a body; `test_route_table.py` green; `apis.consumes: []` and no body read path. |
| 13 | 02-05 | MUST NOT let a management route default to unauthenticated access | Upheld | `require_session` on all five, unconditional 401 in the A-045 envelope; `_declares_session` checks callable identity, not name. |
| 14 | 02-05 | MUST NOT update or delete a row of `ledger.price_table` through any route (A-102, T-006) | Upheld | Route enumeration finds only `POST` (insert) and `GET` on `/prices`. No PUT, no DELETE. |

### Anti-Patterns Found

**Debt-marker gate: PASSED.** `grep -rnE "\bTBD\b|\bFIXME\b|\bXXX\b" src/ tests/ alembic/` returns **zero matches**. So does the warning-level scan (`TODO`, `HACK`, `PLACEHOLDER`, "coming soon", "not yet implemented"). No stub implementations.

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `schemas.py` | 394 | `retention_days: int` — no upper bound | ⚠️ WARNING | **CR-01, confirmed independently.** I verified all three legs: the field carries no `le=`; `api.py:720` does `timedelta(days=payload.retention_days)`; and `OverflowError` matches **none** of `classify_write_failure`'s branches (`ValueError`, `ValidationError`, `IntegrityError`, `OperationalError`, `InterfaceError`, `DBAPIError`, `ConnectionError`, `OSError`, `TimeoutError`) — `OverflowError` subclasses `ArithmeticError`, so it takes the `PERMANENT` default and dead-letters. The reviewer's analysis is correct. **Not a blocker for this phase's goal:** `require_session` raises 401 before any request body is read, so the route is unreachable until Phase 7, and no Phase 2 must-have truth asserts input bounds. It must be fixed before Phase 7 opens the route. |
| `enqueue.py` | 274-283 | `run_publisher` returns on `stopping` with the handoff undrained | ⚠️ WARNING | **CR-02, confirmed independently.** `while not stopping.is_set()` exits with up to `HANDOFF_MAXSIZE` (512) records buffered; no counter, no log. This contradicts `enqueue.py`'s own docstring claim that `metadata_dropped_total` makes the Phase 2 loss window measurable. The declared, accepted Phase 2 loss is "counts-and-drops" — this path drops **without** counting, which is outside that acceptance. **Not a blocker for this phase's goal:** no Phase 2 must-have truth asserts that every drop is counted; "every drop is counted" is ROADMAP Phase 3 SC1. Partially covered by deferred item 3, but the shutdown-drain fix is not obviously inside Phase 3's stated scope, so it is reported here rather than silently deferred. |

Neither finding falsifies a phase truth, so neither is a BLOCKER. Both are real defects and both are routed to human decision.

### Known and deliberate — confirmed, not reported as gaps

I verified each of these is what the execution state says it is, rather than accepting the label: `ruff format --check` failing repo-wide on a pre-existing `ruff.toml` `line-length` mismatch (the linter itself passes clean); the `classic-durable` + `reject-publish-dlx` queue type (a one-way decision taken at a blocking checkpoint, with the reasoning recorded at `topology.py:17-31` and in COVERAGE.md); `/readyz` green with the broker unreachable (D-16, documented at the code); the `WorkspaceEnumerator` stand-in (forced by ADR-0045 — a fifth `SECURITY DEFINER` routine would break the sanctioned-set test); 401 on every `/api/v1` route until Phase 7; and OQ-018/019/020/021 raised rather than absorbed.

### Gaps Summary

**No gaps.** Every ROADMAP success criterion and every goal clause is verified by a test I ran in this session against the real Postgres and RabbitMQ containers, not by reading a SUMMARY. The three internal contracts exist and are substantive; the six management routes exist and are wired through explicit composition; the worker's drain consumes `prope.call_record` and writes per-workspace batches, proven end-to-end by two workspaces receiving two different retention windows through the composed worker.

The phase does not pass silently, though. It is `human_needed` for six reasons, none of which is an implementation failure:

1. **Fourteen judgment-tier prohibitions** — the security-weight items of this phase — have no mechanical enforcement. My reading finds all fourteen upheld and one (#6) partially deferred, but that reading is advisory and cannot be the record.
2. **CR-01 and CR-02** are real defects I reproduced in code. Neither breaks a Phase 2 truth; both need a disposition.
3. **The five management routes cannot be exercised by hand** until Phase 7 — verified through the ASGI rig and the assembled route table, but the fail-closed 401 is genuinely untestable-until-Phase-7 rather than a gap.
4. **The (0,0) price-row refusal shipped unconfirmed**, pending an open Phase 1 decision.
5. **Four open questions** record declared spec deviations that only the spec owner can resolve.
6. **CL-11's traceability** is unsettled: SC3 is built, and deliberately claims no requirement.

The evidence quality here is unusually high — tests assert over serialized forms rather than fields, use negative controls and spies, read state back through the owner role rather than through the writer's return value, and the commit chain shows tests landing before implementations.

---

_Verified: 2026-08-10T18:40:00Z_
_Verifier: Claude (gsd-verifier)_
