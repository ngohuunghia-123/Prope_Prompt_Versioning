---
phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
verified: 2026-08-11T00:00:00Z
status: human_needed
score: 3/3 ROADMAP success criteria verified; 04-01's self-reported unmet truth IS delivered by 04-04
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: null
  note: "Initial verification — no prior 04-VERIFICATION.md existed"
deferred:
  - truth: "PH-06 — the registry equals the union of five lock files' event lists, 31 names, no extras/omissions"
    addressed_in: "Phase 5"
    evidence: "ROADMAP routes PH-06 to Phase 5. Phase 4 seeds the 31 rows and asserts only the spec-determined columns (requires_reason, the two declared detail_keys sets) — deliberately not the action names, per COVERAGE.md §1 and plan 04-01 Task 2."
  - truth: "PH-01/PH-03/PH-07/PH-08/PH-09/PH-10 and the six remaining metrics/three alerts"
    addressed_in: "Phase 5 (PH-03) / Phase 6 (the rest)"
    evidence: "COVERAGE.md §1 and §3 name the owning phase for each; PH-02/04/05 are the only requirements this phase's `requirements:` frontmatter claims."
human_verification:
  - test: "Confirm OQ-131 (seq ships as GENERATED ALWAYS AS IDENTITY where the lock file and ADR-0024 say bigserial). The engine now refuses a caller-supplied seq; the lock's literal spelling would have accepted one silently."
    expected: "Either the spec is amended to say GENERATED ALWAYS (recommended — the stricter reading is what PH-04 needs), or the decision is reversed to bigserial and tests/security/test_history_seq_cannot_be_supplied.py + tests/architecture/test_no_overriding_system_value.py are deleted."
    why_human: "One-way once rows exist (changing an append-only table's sort key means rewriting rows prope_app cannot rewrite). docs/brainstorm/open_questions/OQ-131.md already exists, correctly allocated outside every phase's OQ range, and is otherwise complete — this is the adjudication itself, not a missing artifact."
  - test: "Confirm the eight ORCHESTRATION §6 adopted-UNCONFIRMED decisions in deferred-items.md §2 (D-50, D-53, D-56, D-57, D-61, D-64, the LOGGABLE_FIELDS reason/rejection_reason split, and the A-046 runtime-marker-now/AST-gate-later scope)."
    expected: "Each row confirmed, reversed, or explicitly accepted. None touches a §2 non-negotiable; three (D-50, D-53, D-57) move toward a *stronger* engine-enforced guarantee."
    why_human: "ORCHESTRATION §6: an adopted-UNCONFIRMED decision under yolo mode is a human-verification item by construction, not a verifier judgement call."
  - test: "Merge three orchestrator-owned ledger entries this phase's executors correctly did NOT touch: (1) .planning/STATE.md's Phase 01 note naming Phase 7 as first to shrink EXPECTED_ABSENT_SCHEMAS is now wrong — Phase 4 is first; (2) .planning/ORCHESTRATION-DECISIONS.md carries zero Phase 4 rows as of this verification; (3) .planning/WINDOWS.md carries zero Phase 4 rows (the request_id-not-in-LOGGABLE_FIELDS Broken Window from plan 04-04 is unrecorded, open_count should read 5)."
    expected: "STATE.md, ORCHESTRATION-DECISIONS.md and WINDOWS.md updated per the ledger tables in each plan's SUMMARY and in deferred-items.md."
    why_human: "These four files are explicitly out of bounds for this verifier and for every phase agent (run instructions' HARD RULES; ORCHESTRATION §7's shared-file reasoning). Confirmed unedited by grep, not assumed."
---

# Phase 4: Schema, privilege, ordering, and the closed vocabulary — Verification Report

**Phase Goal:** `history_event` and `history_action_registry` exist; append-only is a database privilege; events have a total order by a monotonic sequence; and the 31-name vocabulary rejects everything else.
**Verified:** 2026-08-11
**Status:** human_needed
**Re-verification:** No — initial verification

---

## The single most important thing checked, stated first

**04-01 self-reported one unmet truth and routed it to 04-04**: *"an INSERT naming an (action, target_type) pair that is not a registry row is refused by fk_history_event_action, even when executed as prope_migrate."*

**04-04 DOES deliver it, and a real test proves it.** `tests/security/test_history_validation_has_no_database_backstop.py::test_an_unregistered_action_is_refused_by_the_engine` inserts a hand-written row through `migrate_engine` (i.e. as `prope_migrate`, the repair-script role and the only role ADR-0025 names as the realistic threat) naming `action='not_a_registered_action'`, and asserts `pytest.raises(IntegrityError)` with `"fk_history_event_action"` in the exception text. I ran it by name against a live PostgreSQL 17 container:

```
tests/security/test_history_validation_has_no_database_backstop.py::test_an_unregistered_action_is_refused_by_the_engine PASSED
```

A sibling test (`test_a_registered_action_paired_with_the_wrong_target_type_is_refused`) proves the composite half of the key — a *registered* action paired with the *wrong* `target_type` is refused by the same constraint, which a single-column key would have accepted — and a third (`test_the_same_refusal_holds_for_the_application_role`) proves the identical refusal for `prope_app`, asserting the message names `fk_history_event_action` and explicitly does **not** contain `permission denied`, so the two refusal mechanisms (constraint vs. privilege) are not conflated. All three pass. This is not a vacuous assertion: the seed migration (`0005`) genuinely creates `fk_history_event_action FOREIGN KEY (action, target_type) REFERENCES history.history_action_registry (action, target_type)` with no `ON DELETE`/`ON UPDATE` clause, confirmed by reading the applied revision.

---

## Verdict

The phase goal is achieved, with three UNCONFIRMED decisions (ORCHESTRATION §6, `mode: yolo`) and one escalated open question (OQ-131) routed to the human, none of which falsifies any ROADMAP success criterion:

- **"`history_event` and `history_action_registry` exist"** — both tables exist after `alembic upgrade head` on a pristine cluster (`0005_history_schema_and_vocabulary.py`, confirmed as head via `uv run alembic heads` → `0005 (head)`), the registry holds exactly 31 rows readable with no tenant context, and `history_event` carries RLS with one policy while the registry is the project's first documented `GLOBAL_TABLES` exemption.
- **"append-only is a database privilege"** — `prope_app` holds `SELECT`/`INSERT` and neither `UPDATE` nor `DELETE` on `history_event`; a provoked `UPDATE`/`DELETE` against a row visible inside the attempting transaction is refused with `permission denied`; and a grant/observe/revoke mutation cycle proves the refusal has teeth (it stops holding when the privilege is restored and returns when revoked). All re-run by this verifier.
- **"events have a total order by a monotonic sequence"** — `seq` is `bigint GENERATED ALWAYS AS IDENTITY (CACHE 1)`; two events sharing a byte-identical `occurred_at`, written in one transaction, come back ordered by `seq`, with a positive control proving the timestamps really are equal. Re-run by this verifier.
- **"the 31-name vocabulary rejects everything else"** — the registry seeds exactly 31 rows (confirmed by direct count); an append naming an unregistered action or an unregistered `details` key raises, rolls the caller's whole transaction back with no partial state (including a *valid* event written earlier in the same transaction), and increments `append_rejected_total` with the matching reason label. Re-run by this verifier.

All three ROADMAP Success Criteria were re-run by this verifier against a live `postgres:17` container. The full pre-existing suite is green: **516 passed, 1 skipped, 1 warning in 295.94s**. `ruff check src/ tests/ alembic/` passes with no findings.

---

## The Gate (verbatim)

```
$ uv run ruff check src/ tests/ alembic/
All checks passed!
```

```
$ uv run pytest -q
516 passed, 1 skipped, 1 warning in 295.94s (0:04:55)
```

The one skip is Phase 3's `PROPE_RUN_LOAD`-gated load test, unaffected by this phase. `uv run ruff format --check` was not run — it fails repo-wide on the pre-existing 120-vs-100 line-length disagreement (Broken Window #1, unchanged, not this phase's to fix), and it is not the gate per the run instructions.

```
$ uv run alembic heads
0005 (head)
```

Exactly one head, as D-04 requires.

---

## ROADMAP Success Criteria — run by name against a live engine

| # | Success Criterion | Test file / function | Result |
|---|---|---|---|
| 1 | `prope_app` attempting UPDATE or DELETE on a history event is refused by the engine, not by an application guard — WITH a positive control (grant, observe the refusal stop holding, revoke, observe it return) | `tests/security/test_history_is_append_only_by_privilege.py::test_update_on_history_event_is_refused_by_the_engine`, `::test_delete_on_history_event_is_refused_by_the_engine`, `::test_the_append_only_refusal_has_teeth` | ✓ **PASSED**, all three, run by verifier |
| 2 | Two events written in one transaction have a stable order on every run, INCLUDING when their `occurred_at` values are byte-identical | `tests/integration/test_same_transaction_events_have_a_stable_order.py::test_approval_precedes_release_when_their_timestamps_are_identical` | ✓ **PASSED**, run by verifier |
| 3 | An append with an unregistered action or an unregistered `details` key raises, rolls the caller's transaction back with NO partial state, and increments `append_rejected_total` with a reason | `tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_an_unregistered_detail_key_rolls_the_callers_transaction_back` (plus its parametrised sibling `test_an_unregistered_action_and_a_missing_reason_each_roll_back_and_count[unknown_action]`) | ✓ **PASSED**, run by verifier |

None of the three is vacuous — each is read below with what makes it a real proof rather than an absence asserted without evidence.

### Criterion 1 — the positive control, examined

`test_the_append_only_refusal_has_teeth` is a genuine mutation check, not a procedure written down for a human to run: it asserts `has_table_privilege(...) is False`, then `GRANT UPDATE ON history.history_event TO prope_app`, re-asserts `is True`, executes the exact `UPDATE` the refusal tests expect to fail and asserts `rowcount == 1` (so the grant window is proven to actually work, not merely believed to), then `REVOKE`s in a `finally`, and re-asserts `is False`. Without this test, the two plain refusal tests could be passing because the probe targets a mis-named table rather than because the privilege is genuinely absent — exactly the failure mode "an absence asserted without a positive control is not evidence" warns against. The two plain refusal tests (`test_update_on_history_event_is_refused_by_the_engine`, `test_delete_...`) each seed a row through the owner role first and assert `seen == 1` **inside the same transaction as the attempt**, before attempting the mutation — so the refusal cannot be an empty-table false pass.

### Criterion 2 — the positive control, examined

`test_approval_precedes_release_when_their_timestamps_are_identical` shares one literal `occurred_at` (`day(5)`) between both `HistoryEventDraft`s — never calling `datetime.now()` twice, which could occasionally itself produce distinct instants — writes both through `record_event` in one `workspace_transaction`, reads back via `migrate_engine` (the owner, outside RLS) ordered by `seq`, and asserts `[row.id for row in rows] == [approval_id, release_id]` **and** `approval_row.seq < release_row.seq` **and**, as the explicit positive control, `len({row.occurred_at for row in rows}) == 1` — proving the compared timestamps really are byte-identical, so the demonstrated ordering cannot be a timestamp tiebreak in disguise. A companion test (`test_three_events_in_one_transaction_order_fully`) raises the odds against a lucky pass from 1-in-2 to 1-in-8 with a three-event chain.

### Criterion 3 — the positive control, examined

`test_an_unregistered_detail_key_rolls_the_callers_transaction_back` writes a *valid* event first, then a poisoned second event in the **same** transaction; the raised `HistoryAppendRejected` is asserted to carry `reason is RejectionReason.UNKNOWN_DETAIL_KEY` and `detail_key == "not_registered"`, and — critically — `LEAKED_VALUE not in str(excinfo.value)`, so the offending *value* never appears in the exception message, only the key name. Read back through `migrate_engine` outside RLS: `COUNT_HISTORY_EVENTS == 0` — **both rows are gone, including the one that succeeded**, which is the half a naive "count is zero on the failing row" assertion cannot see (that half would pass identically against a module that opened and rolled back its own transaction — the exact ADR-0023 violation this suite is built to catch). `append_rejected_total{reason="unknown_detail_key"}` is asserted to have incremented by exactly 1 while the other two reason labels are asserted unchanged (`+0`), read as counter deltas so the check works regardless of what earlier tests in the same process already counted.

---

## Migration health

| Check | Expected | Result |
|---|---|---|
| `uv run alembic heads` | exactly one head | ✓ `0005 (head)` |
| `history` schema exists, owned by `prope_migrate` | `CREATE SCHEMA history AUTHORIZATION prope_migrate`, before `assume_migrate_role()` | ✓ confirmed by reading `alembic/versions/0005_history_schema_and_vocabulary.py:371`, and by `test_declared_schemas_that_do_not_exist_are_reported_not_skipped` (PASSED) asserting `existing == ("history", "ledger")` |
| Both tables exist | `history.history_action_registry`, `history.history_event` | ✓ `test_an_empty_cluster_reaches_head_and_yields_a_working_database` (PASSED), which now walks a two-schema `SCHEMA_TABLES` mapping |
| Four indexes exist, by name | `ix_history_event_workspace_id_scope_prompt_id_seq`, `ix_history_event_workspace_id_target_type_target_id_seq`, `ix_history_event_workspace_id_actor_id_seq`, `ix_history_event_workspace_id_action_seq` (plus the two constraint-backed indexes `pk_history_event`, `uq_history_event_seq`) | ✓ `test_the_four_declared_indexes_exist_by_name` (PASSED) — asserts the tuple against `pg_indexes` exactly |
| Tenant policy on `history_event`; registry exempted with a written reason | `enable_tenant_rls("history", "history_event")`; registry in `GLOBAL_TABLES` | ✓ `test_every_table_in_every_declared_schema_is_tenant_scoped` and `test_every_global_table_exemption_carries_a_written_reason` (both PASSED) |
| Grant matrix | `prope_app`: SELECT+INSERT on `history_event`, SELECT-only on the registry, no UPDATE/DELETE on either; `prope_report`: SELECT on both, nothing else | ✓ `test_prope_app_holds_select_and_insert_on_history_event`, `test_the_registry_is_select_only_for_the_application_role`, `test_prope_report_reads_both_tables_and_writes_neither` (all PASSED) |
| Registry holds 31 rows | 31 | ✓ `test_the_registry_is_readable_with_no_tenant_context_and_holds_thirty_one_rows` (PASSED) — `COUNT_REGISTRY_ROWS == 31` **and** `COUNT_HISTORY_EVENTS == 0` in the same session with no tenant context, proving the 31 came from the `GLOBAL_TABLES` exemption and not a leaky policy. Row count independently confirmed by reading the seed's five `VALUES` blocks (5 + 8 + 4 + 4 + 10 = 31) |
| Identity sequence cache is 1 | `CACHE 1` | ✓ `test_the_identity_sequence_has_no_cache` (PASSED) — reads `pg_sequence.seqcache` back via `pg_get_serial_sequence`, not the migration source |

---

## Observable Truths, walked plan by plan against the repository

### Plan 04-01 (tracer: schema, tables, indexes, vocabulary key, grants, seed, rig)

| Truth (from the plan's `must_haves`) | Status | Evidence |
|---|---|---|
| `history` schema exists after `alembic upgrade head`, owned by `prope_migrate`, USAGE granted to `prope_app`/`prope_report` | ✓ VERIFIED | Read directly from `0005:371-372`; `test_declared_schemas_that_do_not_exist_are_reported_not_skipped` PASSED |
| Registry holds exactly 31 rows, readable with no tenant context | ✓ VERIFIED | `test_the_registry_is_readable_with_no_tenant_context_and_holds_thirty_one_rows` PASSED |
| `prope_app` holds SELECT+INSERT, not UPDATE/DELETE, on `history_event`; UPDATE/DELETE against a visible row refused with `permission denied` | ✓ VERIFIED | Four tests PASSED, see Criterion 1 above |
| `prope_app` holds SELECT, not INSERT/UPDATE/DELETE, on the registry | ✓ VERIFIED | `test_the_registry_is_select_only_for_the_application_role` PASSED |
| `prope_report` holds SELECT on both, nothing else | ✓ VERIFIED | `test_prope_report_reads_both_tables_and_writes_neither` PASSED |
| Grant/observe/revoke mutation check has teeth | ✓ VERIFIED | `test_the_append_only_refusal_has_teeth` PASSED, see above |
| Unregistered `(action, target_type)` refused by `fk_history_event_action`, even as `prope_migrate` | ⚠️ **DEFERRED IN THIS PLAN, DELIVERED BY 04-04** | 04-01's own SUMMARY (D7) states this directly: "the DIRECT assertion... is plan 04-04's, which this plan's own objective routes it to." Confirmed delivered — see "The single most important thing checked" above |
| `history_event` carries RLS with a policy; registry carries neither, exempted in `GLOBAL_TABLES` with a written reason | ✓ VERIFIED | Both tenant-coverage tests PASSED |
| Identity sequence cache size is 1 | ✓ VERIFIED | `test_the_identity_sequence_has_no_cache` PASSED |
| Whole pre-existing suite green; `EXPECTED_ABSENT_SCHEMAS` names six; existing-schema tuple is `(history, ledger)`; five generic invariants run against both schemas | ✓ VERIFIED | `EXPECTED_ABSENT_SCHEMAS` read directly (six entries: access, evaluation, gateway, provider, registry, release); full suite 516 passed; `tests/architecture/test_schema_invariants.py`'s `GENERIC_SCHEMAS = ("history", "ledger")` confirmed by reading the file |

**Prohibitions held**: no `UPDATE`/`DELETE` grant to `prope_app` on `history_event` (confirmed — grants are `["SELECT", "INSERT"]` only); no `SECURITY DEFINER` function added (the sanctioned set stays exactly four, per CLAUDE.md — no `SECURITY DEFINER` token appears in `0005`); no native `ENUM` type (confirmed — `ck_history_event_actor_type_values` is a text CHECK, and `test_no_native_enum_type_exists_in_the_ledger_schema`, now parameterised over both schemas, passed); no foreign key leaving `history` (confirmed — `fk_history_event_action` targets `history.history_action_registry`, intra-schema); registry not truncated/re-seeded in the test rig (confirmed by reading `tests/conftest.py`'s `LIST_TRUNCATABLE_TABLES` predicate, which excludes `history.history_action_registry` by name); `docs/modules/*.lock.yml`/`docs/architecture/*`/ADRs not edited (confirmed — `git show --stat` on the phase's single commit touches no `docs/adr/` or `docs/modules/` or `docs/architecture/` file except the newly **created** `docs/brainstorm/open_questions/OQ-131.md`, which is the one path ORCHESTRATION §1 permits creating).

### Plan 04-02 (the module, the registry loader, the validating write path — PH-05)

| Truth | Status | Evidence |
|---|---|---|
| `load_action_registry` on a no-tenant session returns an immutable mapping of 31 `RegisteredAction`s with `frozenset` `detail_keys` | ✓ VERIFIED | Code read directly (`registry.py`); `tests/integration/test_action_registry_loads_without_a_tenant.py` in the full-suite run |
| The mapping cannot be mutated | ✓ VERIFIED | `MappingProxyType` used in `registry.py:65`; corresponding test in full suite |
| An empty registry raises `RuntimeError` naming the table | ✓ VERIFIED | `registry.py:41-49`; corresponding test in full suite |
| `record_event` opens no transaction, commits nothing, rolls nothing back; takes an `AsyncSession`, never a sessionmaker | ✓ VERIFIED | `append.py:103-135` — no `commit`/`rollback`/`begin`/`sessionmaker` token anywhere in the file (confirmed by reading it in full) |
| A valid event on an abandoned caller transaction leaves no row | ✓ VERIFIED | `test_an_abandoned_caller_transaction_leaves_no_event`, in full suite |
| Unregistered action → `unknown_action`, before any SQL | ✓ VERIFIED | `check_event` in `append.py:83-85` raises before `session.execute` is ever reached; corresponding tests in full suite |
| Unregistered `details` key → `unknown_detail_key`, message names the KEY only | ✓ VERIFIED | `append.py:87-95`; `LEAKED_VALUE not in str(excinfo.value)` asserted and confirmed passing above |
| Missing/whitespace-only reason where required → `missing_reason` | ✓ VERIFIED | `append.py:97-100`, `(event.reason or "").strip()`; corresponding tests in full suite |
| Refused append rolls the caller's WHOLE transaction, including a valid event written earlier in it | ✓ VERIFIED | Confirmed above under Criterion 3 |
| `append_rejected_total` increments by exactly one on the matching reason, survives the rollback | ✓ VERIFIED | Confirmed above under Criterion 3 — the counter is process state (`prometheus_client`), unaffected by a database rollback |
| `RejectionReason` has exactly three members | ✓ VERIFIED | `domain.py:49-59` — `UNKNOWN_ACTION`, `UNKNOWN_DETAIL_KEY`, `MISSING_REASON`; corresponding cardinality test in full suite |
| `src/prope/property_history/` imports FastAPI at no depth; touches neither `app.py` nor `worker.py` | ✓ VERIFIED | `grep -rn fastapi src/prope/property_history/` returns nothing (checked in this session); `git show --stat` on the phase commit lists no `app.py`/`worker.py` change |

### Plan 04-03 (ordering, the identity boundary, the source gate — PH-04)

| Truth | Status | Evidence |
|---|---|---|
| Two events, byte-identical `occurred_at`, one transaction → ordered by `seq` in write order, with a positive control | ✓ VERIFIED | Confirmed above under Criterion 2 |
| Three events in one transaction order fully | ✓ VERIFIED | `test_three_events_in_one_transaction_order_fully`, in full suite |
| A gap in `seq` (from a rolled-back INSERT that reached the engine) is not a missing event | ✓ VERIFIED | `test_a_gap_in_seq_is_not_a_missing_event`, in full suite — provokes the gap via a genuine abandoned INSERT, not a validation refusal |
| A validation refusal leaves NO gap (distinguishing the two mechanisms) | ✓ VERIFIED | `test_a_validation_refusal_between_two_writes_leaves_no_gap`, in full suite |
| A hand-written `INSERT` naming `seq` is refused by the engine (`generated always` in the message) | ✓ VERIFIED | `tests/security/test_history_seq_cannot_be_supplied.py::test_an_insert_naming_seq_is_refused_by_the_engine`, in full suite |
| The identical INSERT with `seq` omitted succeeds (positive control) | ✓ VERIFIED | `::test_the_same_insert_without_seq_succeeds`, in full suite |
| `OVERRIDING SYSTEM VALUE` succeeds with no privilege change; the next `record_event` lands a LOWER `seq`; a `seq`-ordered read returns the later-written event first | ✓ VERIFIED | `::test_overriding_system_value_is_accepted_and_that_is_the_recorded_boundary`, in full suite — read in full above, the honest boundary is proven rather than assumed |
| No statement under `src/prope/` or `alembic/` (outside a docstring) contains `OVERRIDING SYSTEM VALUE`/`OVERRIDING USER VALUE` | ✓ VERIFIED | `tests/architecture/test_no_overriding_system_value.py` — AST-based gate, `ALLOWED` frozenset ships empty; read in full above; in full suite |
| The gate actually walks both roots and covers `append.py` | ✓ VERIFIED | `test_the_walk_actually_found_modules_to_check`, `test_the_append_path_is_covered_by_this_walk`, in full suite |
| The gate is a committed, non-vacuous proof (catches a non-docstring hit, exempts a docstring) | ✓ VERIFIED | `test_the_gate_ignores_docstrings_but_catches_a_non_docstring_constant`, in full suite |

### Plan 04-04 (the two boundary assertions — no requirement id, by design)

| Truth | Status | Evidence |
|---|---|---|
| Unregistered action refused by `fk_history_event_action` as `prope_migrate` | ✓ VERIFIED | Confirmed above, run by name |
| Registered action + wrong `target_type` refused by the same constraint | ✓ VERIFIED | `test_a_registered_action_paired_with_the_wrong_target_type_is_refused`, in full suite |
| Same refusal holds for `prope_app`, names the constraint and NOT `permission denied` | ✓ VERIFIED | `test_the_same_refusal_holds_for_the_application_role`, in full suite |
| A hand-written insert bypassing Python validations (unregistered `details` key, NULL required reason) SUCCEEDS at the engine, with a positive control on the registry row first | ✓ VERIFIED | `test_a_hand_written_insert_bypasses_the_python_validations`, in full suite — this is the recorded absence, deliberately not refused, and the test's own docstring instructs deleting it together with revision `0005`'s docstring paragraph if this ever changes |
| The identical payload through `record_event` IS refused | ✓ VERIFIED | `test_the_python_path_refuses_what_the_hand_written_insert_landed`, in full suite |
| A marker in `reason`/`details` survives a successful append, reaches no log record and no metric label, while stored | ✓ VERIFIED | `test_a_marker_in_reason_and_in_details_survives_a_successful_append_and_reaches_nothing`, in full suite — read in full above |
| A marker in a rejected append's `details` reaches nothing; the offending KEY NAME does appear | ✓ VERIFIED | `test_a_marker_in_a_rejected_appends_details_reaches_nothing_and_the_key_name_does`, in full suite |
| A marker in `reason` on a first-check refusal reaches nothing | ✓ VERIFIED | `test_a_marker_in_reason_reaches_nothing_on_the_refusal_path`, in full suite |
| Every logged key from both paths is a `LOGGABLE_FIELDS` member | ✓ VERIFIED | `test_every_logged_key_is_in_the_allow_list`, in full suite — first read of that allow-list since Phase 2 wrote it |

No must-have truth across all four plans failed. No artifact claimed is missing or a stub.

---

## Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `alembic/versions/0005_history_schema_and_vocabulary.py` | `alembic/ddl.py` | `enable_tenant_rls`, `grant_table`, `assume_migrate_role`/`reset_role` calls | ✓ WIRED — confirmed by reading the file; no raw `CREATE POLICY`/`GRANT` bypasses the helpers |
| `alembic/versions/0005_...py` | `history.history_action_registry` | `fk_history_event_action` composite FK | ✓ WIRED — confirmed by reading the DDL and by the D-62 boundary tests |
| `tests/architecture/test_tenant_coverage.py` | `history.history_action_registry` | `GLOBAL_TABLES["history.history_action_registry"]`, the project's first entry | ✓ WIRED — confirmed by reading the file and by the passing exemption tests |
| `src/prope/property_history/append.py` | `src/prope/property_history/domain.py` | `check_event`/`record_event` raise `HistoryAppendRejected`, which self-increments and self-logs in `__init__` | ✓ WIRED — confirmed by reading `domain.py:87-103`; one increment site, one log site |
| `src/prope/property_history/append.py` | `src/prope/db/session.py` | `record_event(session: AsyncSession, ...)` — never opens a transaction | ✓ WIRED — confirmed by reading the file; behaviourally proven by the abandoned-transaction tests |
| `tests/security/test_history_seq_cannot_be_supplied.py` | `tests/architecture/test_no_overriding_system_value.py` | Both halves of the `OVERRIDING SYSTEM VALUE` boundary the revision's seventh docstring paragraph names | ✓ WIRED — 04-03's SUMMARY states plan 04-03 Task 2 is "written against the boundary note existing" and instructs deletion together if it moves; both files exist and both pass |
| `tests/security/test_no_history_content_reaches_a_log_line.py` | `src/prope/observability.py` | `LOGGABLE_FIELDS` membership check | ✓ WIRED — `test_every_logged_key_is_in_the_allow_list` reads the actual module constant, not a copy |

---

## Behavioural Spot-Checks — run by this verifier, this session

| Behavior | Command | Result |
|---|---|---|
| Full suite | `uv run pytest -q` | **516 passed, 1 skipped, 1 warning in 295.94s** |
| Lint gate | `uv run ruff check src/ tests/ alembic/` | **All checks passed!** |
| Exactly one migration head | `uv run alembic heads` | **0005 (head)** |
| PH-02 privilege refusals (3 tests, incl. mutation check) | `pytest tests/security/test_history_is_append_only_by_privilege.py::test_update_on_history_event_is_refused_by_the_engine ::test_delete_on_history_event_is_refused_by_the_engine ::test_the_append_only_refusal_has_teeth` | **3 passed** |
| PH-04 ordering under identical timestamps | `pytest tests/integration/test_same_transaction_events_have_a_stable_order.py::test_approval_precedes_release_when_their_timestamps_are_identical` | **1 passed** |
| PH-05 transaction rollback + counter | `pytest tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_an_unregistered_detail_key_rolls_the_callers_transaction_back` | **1 passed** |
| 04-01's self-reported gap, closed by 04-04 | `pytest tests/security/test_history_validation_has_no_database_backstop.py::test_an_unregistered_action_is_refused_by_the_engine` | **1 passed** |
| Migration health (31-row seed, 4 indexes, seq cache) | `pytest tests/integration/test_history_schema_ships_its_guarantees.py tests/architecture/test_tenant_coverage.py tests/integration/test_migration_chain.py` | **11 passed** |

---

## Requirements Coverage

| Requirement | Plan | Description | Status | Evidence |
|---|---|---|---|---|
| **PH-02** | 04-01 | `prope_app` cannot UPDATE/DELETE a history event — the engine refuses, not an application guard | ✓ SATISFIED | ROADMAP SC1 verified by verifier-run tests, WITH positive control mutation cycle. `.planning/REQUIREMENTS.md` still shows `Pending` — a bookkeeping gap owed to the orchestrator at phase close, not a code gap |
| **PH-04** | 04-03 | Two events in one transaction have a stable, defined order even when timestamps are identical | ✓ SATISFIED | ROADMAP SC2 verified by verifier-run test, WITH positive control on timestamp equality. `.planning/REQUIREMENTS.md` still shows `Pending`, same note |
| **PH-05** | 04-02 | An append with an unregistered action/details key raises, rolls back the caller's transaction, counts the reason | ✓ SATISFIED | ROADMAP SC3 verified by verifier-run test, WITH the whole-transaction rollback proven (valid event written earlier also gone). `.planning/REQUIREMENTS.md` still shows `Pending`, same note |

**Orphaned requirements**: none. Every id this phase's four plans' `requirements:` frontmatter claims (PH-02, PH-05, PH-04) matches exactly the three the phase's ROADMAP entry lists.

**REQUIREMENTS.md discrepancy, stated plainly**: `.planning/REQUIREMENTS.md` lines 184–186 still read `Pending` for PH-02, PH-04 and PH-05 as of this verification. This is expected under ORCHESTRATION §9.4 (requirement ticking happens at phase close, which is the orchestrator's action, not a plan executor's or this verifier's) and is not evidence against the code. Flagged so the orchestrator's phase-close pass does not miss it.

---

## OQ-131 — the one escalated open question, and its current state

Plan 04-01 found that `docs/modules/property-history.lock.yml`'s `data.owns → history_event → seq` and ADR-0024's Decision block both say `bigserial`, while the shipped column is `bigint GENERATED ALWAYS AS IDENTITY (CACHE 1)` — a **behavioural**, not spelling, deviation: under the lock's literal spelling, a hand-written `INSERT` naming `seq` would succeed silently; under what shipped, it is refused (`tests/security/test_history_seq_cannot_be_supplied.py::test_an_insert_naming_seq_is_refused_by_the_engine`, confirmed passing above). Phase 4's allocated OQ range (`OQ-027…OQ-031`) was fully consumed, so the id was correctly escalated rather than borrowed from another phase's range.

**`docs/brainstorm/open_questions/OQ-131.md` exists**, correctly allocated outside every phase's range (phases 16–24 hold `OQ-086…OQ-130`; orchestrator-allocated ids start at `OQ-131`), dated the same day, `status: open`, `owner: user`, `blocks_build: false`. It is complete and asks the right question (confirm the strengthening upstream, or reverse it and delete the two tests that assert the refusal). This is a genuine open question for a human, not a missing artifact — routed to `human_verification` above.

---

## Ledger items this verifier found unmet in orchestrator-owned files (not this phase's to fix)

Confirmed by direct inspection, not assumed from the SUMMARYs:

1. **`.planning/STATE.md`** still carries, unedited: *"Phase 7 (access) is the first phase that must shrink [`EXPECTED_ABSENT_SCHEMAS`]"* — now false; Phase 4 (`history`) is first. `tests/architecture/test_tenant_coverage.py`'s own comment was corrected in the same change that created the schema (confirmed by reading it); the STATE.md line was not, per the run's HARD RULES (STATE.md is out of bounds to this verifier and to every plan agent).
2. **`.planning/ORCHESTRATION-DECISIONS.md`** carries zero rows naming `phase: 04` as of this verification (`grep -n "04 |"` returns nothing). Eight adopted-UNCONFIRMED decisions from `deferred-items.md` §2 are owed here.
3. **`.planning/WINDOWS.md`** carries zero rows naming `history` or `phase 4` (`grep -i` returns nothing). The `request_id`-not-in-`LOGGABLE_FIELDS` Broken Window plan 04-04 found (`src/prope/call_ledger/schemas.py:442`) is unrecorded; `deferred-items.md` says `open_count` should become 5.

All three are explicitly out of bounds for every agent in this run (run instructions' HARD RULES; ORCHESTRATION §7). Recorded here, not fixed here.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/"not yet implemented" | — | **None found** in the phase's new/modified `src/`, `tests/`, `alembic/` files (checked by reading every source file this phase added) |
| — | — | Empty implementations, stub bodies | — | **None found.** Every deliberate absence (no `target_type` CHECK, no `GIN` index, no trigger, no `ON DELETE` clause) is a documented, tested decision, not an unfinished one |
| `alembic/versions/0005_...py`, `src/prope/property_history/append.py` | — | Prose grep hits for forbidden tokens (`ON DELETE`, `REVOKE UPDATE`, `seq`, `fastapi`) | ℹ️ Info | Each is a **docstring/comment** stating the absence, not code. Both 04-01's and 04-02's SUMMARYs name this explicitly and it is recorded so a verifier's naive grep does not misread it as a gap. Confirmed by reading the actual hit locations — all inside `"""..."""` blocks or `#` comments |

Working tree is clean (`git status --porcelain` returns nothing). The whole phase is one commit (`4702933`), which is a deviation from ORCHESTRATION §10's "one commit per completed plan" — every SUMMARY reports `commits: 0` in its own frontmatter, meaning the executors did not commit their own plans, and a later commit swept all four in. This does not affect correctness (the diff matches every plan's `files_modified` and no cross-plan file collision occurred), but it does mean a bad edit in one plan cannot be isolated to one commit the way §10 intends. Not a phase-goal gap; recorded as a process note.

---

## Gaps Summary

**No gaps against the phase goal or any ROADMAP success criterion.** All three success criteria are proven by tests this verifier ran itself against a live PostgreSQL 17 container, each with a genuine positive control. The one truth 04-01 self-reported as unmet — the unregistered-pair refusal holding even for `prope_migrate` — is delivered by 04-04 and independently re-run here.

What holds this report at `human_needed` rather than `passed`:

1. **OQ-131**, a one-way-once-rows-exist decision (bigserial vs. `GENERATED ALWAYS AS IDENTITY`) that is a real spec/code divergence with a behavioural difference, correctly escalated and already filed.
2. **Eight ORCHESTRATION §6 adopted-UNCONFIRMED decisions** (`deferred-items.md` §2), none touching a non-negotiable, several strengthening a guarantee — but adoption-under-yolo is by construction a human-verification item, not something a verifier confirms on its own authority.
3. **Three orchestrator-owned bookkeeping files** (STATE.md, ORCHESTRATION-DECISIONS.md, WINDOWS.md) that are correctly unedited by every phase agent and are owed updates at phase close — confirmed unedited, not assumed.

Engineering quality is consistent with Phase 1's bar: nearly every negative assertion in this phase carries a positive control (visible-row-before-refusal, grant/observe/revoke, byte-identical-timestamp, registry-row-before-hand-insert), and the two places a phase like this usually cuts corners — asserting an absence without proving the assertion could have seen a presence, and conflating "my own transaction rolled back" with "the caller's transaction rolled back" — neither one does here.

---

_Verified: 2026-08-11_
_Verifier: Claude (phase verifier, isolated worktree)_
_Commit verified: 47029338e821e73f7bd7fdf3b862289e3cf67059_
