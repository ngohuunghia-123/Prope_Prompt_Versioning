---
phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
plan: 04
subsystem: backend
tags: [security, a-046, d-62, observability, logging, verification]

# Dependency graph
requires:
  - phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
    plan: 01
    provides: "alembic/versions/0005 — fk_history_event_action, the 31-row seed; tests/property_history/__init__.py's factories (seed_history_event, load_registry, WORKSPACE_A, day, ACTOR_ID, TARGET_ID, SCOPE_PROMPT_ID, COUNT_HISTORY_EVENTS)"
  - phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
    plan: 02
    provides: "src/prope/property_history/{append,domain}.py — record_event, check_event, HistoryAppendRejected, RejectionReason, HistoryEventDraft, ActorType; src/prope/observability.py's LOGGABLE_FIELDS grown to 18 names"
provides:
  - "tests/security/test_history_validation_has_no_database_backstop.py — D-62's owed pair: fk_history_event_action refuses an unregistered action and a mispaired target_type even as prope_migrate and as prope_app, while an unregistered details key and a missing required reason land by hand as prope_migrate and only there"
  - "tests/security/test_no_history_content_reaches_a_log_line.py — A-046 for property-history: markers in reason and in details reach no captured log record and no metric label on the successful path and on both refusal paths, and LOGGABLE_FIELDS acquires its first reader"
affects: [04-VERIFICATION, 06-property-history-observability]

actuals:
  tokens: 34000
  tasks: 3
  commits: 0

tech-stack:
  added: []
  patterns:
    - "A security test file whose docstring states, before the first test, that half of what it asserts is a refusal and half is a deliberate success, with a do-not-fix instruction naming the artifact to delete alongside the test if the boundary ever moves"
    - "Whole-record marker assertions (repr the captured structlog record, not one field) plus a positive allow-list membership check, giving LOGGABLE_FIELDS a consumer for the first time since Phase 2"

key-files:
  created:
    - tests/security/test_history_validation_has_no_database_backstop.py
    - tests/security/test_no_history_content_reaches_a_log_line.py
  modified: []

key-decisions:
  - "Task 1's checkpoint was resolved as adopted-UNCONFIRMED, exactly as the plan's <adopted> block argues, and was NOT re-opened (ORCHESTRATION §6): the runtime marker assertion ships here, over the paths this module exercises; the AST gate over src/prope/ is routed to Phase 6, which owns AC-8. The request_id omission at src/prope/call_ledger/schemas.py:442 is recorded as a Broken Window rather than fixed here — it is a Phase 2 omission in a Phase 2 file and importing a fix into this phase's verification would make a green Phase 4 depend on a judgement about call-ledger's error envelope"
  - "Local INSERT_EVENT_BY_HAND text() constant, not the production INSERT_HISTORY_EVENT or the test factory's SEED_HISTORY_EVENT: each row in the backstop file is deliberately wrong in one specific way, and reusing a factory that produces the simplest acceptable row would hide the wrongness one edit later, per test_eval_no_body_boundary.py's precedent"
  - "The hand-written-insert-succeeds test uses revision_break_glass_released/revision — the one registered pair with requires_reason=true and detail_keys=() among the three requires_reason=true rows — with a positive-control SELECT against history_action_registry run BEFORE the insert, so the success is attributable to the missing Python-only backstop and not to a mis-chosen action"
  - "The prope_app refusal test asserts the message contains fk_history_event_action AND does not contain 'permission denied', distinguishing an engine-constraint refusal from a privilege refusal — the same two facts test_history_is_append_only_by_privilege.py keeps separate for UPDATE/DELETE"
  - "The refusal-path marker tests use two different unregistered inputs to reach two different check_event branches: an unregistered details key (UNKNOWN_DETAIL_KEY, second check) and an unregistered action (UNKNOWN_ACTION, first check) — both issue no SQL, since check_event runs before session.execute in record_event either way, but the plan's stated reason for the second test (the action-refusal case) is that it is the branch with the least room for a naive whole-draft log to hide in"
  - "capture_logs()'s own injected keys (event, log_level) are excluded from the LOGGABLE_FIELDS membership check by an explicit named frozenset (CAPTURE_LOGS_OWN_KEYS), not a silent filter"

patterns-established:
  - "A do-not-fix-this test names, in its own docstring, both the alembic revision docstring paragraph and the test itself that must be deleted together if the database ever acquires the guard — the same shape test_eval_no_body_boundary.py established in Phase 3"
  - "A-046 marker tests run in pairs: one marker per forbidden column, asserted absent from every captured record's whole repr AND from every current metric label value, each preceded by two vacuity guards (the operation actually happened; something was actually logged)"

requirements-completed: []

coverage:
  - id: D1
    description: "An INSERT naming an unregistered action is refused by fk_history_event_action as prope_migrate, with the repair-script path (ADR-0025) exercised directly and the module not involved"
    verification:
      - kind: security
        ref: "tests/security/test_history_validation_has_no_database_backstop.py::test_an_unregistered_action_is_refused_by_the_engine"
        status: pass
    human_judgment: false
  - id: D2
    description: "A registered action paired with the wrong target_type is refused by the same constraint"
    verification:
      - kind: security
        ref: "tests/security/test_history_validation_has_no_database_backstop.py::test_a_registered_action_paired_with_the_wrong_target_type_is_refused"
        status: pass
    human_judgment: false
  - id: D3
    description: "The same refusal holds as prope_app, names fk_history_event_action and not permission denied, with a valid row visible as the positive control"
    verification:
      - kind: security
        ref: "tests/security/test_history_validation_has_no_database_backstop.py::test_the_same_refusal_holds_for_the_application_role"
        status: pass
    human_judgment: false
  - id: D4
    description: "A hand-written insert as prope_migrate carrying an unregistered details key and a NULL reason on an action whose registry row requires one SUCCEEDS, with a positive control reading requires_reason/detail_keys from the registry first"
    verification:
      - kind: security
        ref: "tests/security/test_history_validation_has_no_database_backstop.py::test_a_hand_written_insert_bypasses_the_python_validations"
        status: pass
    human_judgment: false
  - id: D5
    description: "The same payload through record_event raises HistoryAppendRejected"
    verification:
      - kind: security
        ref: "tests/security/test_history_validation_has_no_database_backstop.py::test_the_python_path_refuses_what_the_hand_written_insert_landed"
        status: pass
    human_judgment: false
  - id: D6
    description: "A marker in reason and in details survives a successful append, reaches no log record and no metric label, and is confirmed present in the stored row"
    verification:
      - kind: security
        ref: "tests/security/test_no_history_content_reaches_a_log_line.py::test_a_marker_in_reason_and_in_details_survives_a_successful_append_and_reaches_nothing"
        status: pass
    human_judgment: false
  - id: D7
    description: "A marker in a rejected append's details reaches no log record and no metric label, while the offending key NAME does appear in a captured record"
    verification:
      - kind: security
        ref: "tests/security/test_no_history_content_reaches_a_log_line.py::test_a_marker_in_a_rejected_appends_details_reaches_nothing_and_the_key_name_does"
        status: pass
    human_judgment: false
  - id: D8
    description: "A marker in reason on an append refused at the first check reaches no log record and no metric label"
    verification:
      - kind: security
        ref: "tests/security/test_no_history_content_reaches_a_log_line.py::test_a_marker_in_reason_reaches_nothing_on_the_refusal_path"
        status: pass
    human_judgment: false
  - id: D9
    description: "Every key in every captured record from a successful and a refused append is a member of LOGGABLE_FIELDS, excluding only capture_logs' own injected keys"
    verification:
      - kind: security
        ref: "tests/security/test_no_history_content_reaches_a_log_line.py::test_every_logged_key_is_in_the_allow_list"
        status: pass
    human_judgment: false
  - id: D10
    description: "The A-046 enforcement decision (marker assertion now, AST gate routed to Phase 6) and the accepted database-backstop boundary are the intended readings"
    verification: []
    human_judgment: true
    rationale: "The plan's two <human-check> items. Both are adjudications rather than properties a test can assert; every mechanical half is built and asserted."

# Metrics
duration: 38min
completed: 2026-08-11
status: complete
---

# Phase 04 Plan 04: Two boundary assertions — Summary

**This plan owns no requirement id, deliberately.** PH-02, PH-04 and PH-05 belong to plans 04-01, 04-03
and 04-02 respectively, and each is proven there. This plan asserts the two seams that make those proofs
mean what they claim: where the closed-vocabulary check actually lives, and what never leaves the
process.

## The D-62 boundary, in one sentence a reviewer could disagree with

**`fk_history_event_action` refuses an unregistered `(action, target_type)` pair even as `prope_migrate`
and even as `prope_app`, and refuses nothing else — an unregistered `details` key and a `NULL` `reason`
on an action whose registry row requires one both land by hand, as `prope_migrate`, with the module not
involved at all.** `tests/security/test_history_validation_has_no_database_backstop.py` proves both
halves: three tests show the engine refusing (unregistered action, mispaired `target_type`, the same
refusal as the application role — asserted by constraint name and explicitly **not** by
`permission denied`), and two tests show the recorded absence (a hand-written insert with two Python-only
violations succeeds, with a registry-row positive control proving the chosen action really requires a
reason and declares no detail keys; the identical payload through `record_event` is then refused,
closing the pair in one file). The file carries `test_eval_no_body_boundary.py`'s do-not-fix instruction:
if the hand-written insert ever starts failing, delete the test and the recorded absence in revision
`0005`'s docstring together — that would mean a database guard was added, which is a real change in what
later phases inherit.

## The A-046 decision, and that it is UNCONFIRMED

Task 1's checkpoint resolved exactly as the plan's `<adopted>` block argues, and was not reopened
(ORCHESTRATION §6 — a decision the plan already made and argued is not a new adoption): the **runtime
marker assertion** ships here, over the paths this module exercises, and the **AST gate** that would make
A-046 a source-level property is routed to **Phase 6**, which owns AC-8 (the full-corpus content
assertion). `tests/security/test_no_history_content_reaches_a_log_line.py` plants a distinct marker in
`reason` and a distinct marker in a `details` value, asserts both absent from the whole `repr` of every
captured `structlog` record and from every metric label value currently in the registry — on the
successful path and on two different refusal branches (`UNKNOWN_DETAIL_KEY`, `UNKNOWN_ACTION`) — each
behind two vacuity guards (the operation really happened; something was really logged). The refusal test
also asserts the offending **key name** does appear in a captured record, so the absence assertions
cannot pass against a module that logs nothing at all. A fourth test reads every captured key from both
paths against `prope.observability.LOGGABLE_FIELDS`, excluding only `capture_logs`'s own injected
`event`/`log_level` keys by a named set — **the first time anything in the project reads that allow-list
since Phase 2 wrote it.**

**This decision is UNCONFIRMED.** Per ORCHESTRATION §6 it is surfaced here for the orchestrator to carry
into `.planning/ORCHESTRATION-DECISIONS.md`.

## Two items handed forward

1. **The `request_id` Broken Window.** `src/prope/call_ledger/schemas.py:442` logs `request_id=request_id`
   and `request_id` is not a member of `LOGGABLE_FIELDS`. Not fixed here — it is a Phase 2 omission in a
   Phase 2 file, and this phase has no requirement asking for that edit. Recorded in the ledger below for
   the orchestrator to append to `.planning/WINDOWS.md`.
2. **The AST gate over `src/prope/`**, routed to Phase 6 by name, with its two known properties recorded
   so that phase does not rediscover them: it goes red on arrival at `schemas.py:442` until `request_id`
   is added to `LOGGABLE_FIELDS`, and it cannot see a dynamically-built `**fields` log payload.

## The gate, observed

```
uv run ruff check src/ tests/ alembic/
All checks passed!
```

```
uv run pytest tests/security/test_history_validation_has_no_database_backstop.py \
              tests/security/test_no_history_content_reaches_a_log_line.py -q
9 passed, 1 warning in 12.06s
```

```
uv run pytest tests/security/ -q
81 passed, 1 warning in 32.80s
```

This is a **subset run only** — plan 04-03 shares this wave and both plans touch containers on the same
Windows Docker host, so a full `uv run pytest -q` is deliberately not run here (the plan's own
verification block routes the whole-suite run to the orchestrator, after the wave). Gate reported as
`not_run` in the structured result for that reason; the files actually run are the two named above, plus
the full `tests/security/` package as a sanity check that this plan's additions coexist with plan 04-03's
(`test_history_seq_cannot_be_supplied.py`) in the same directory.

```
git status --porcelain src/ alembic/ docs/ pyproject.toml uv.lock
```
shows only pre-existing changes from plans 04-01/04-02/04-03 (`alembic/versions/0005_...py`,
`src/prope/property_history/`, `src/prope/observability.py`, `src/prope/app.py`,
`src/prope/call_ledger/enqueue.py`, and unrelated `docs/brainstorm/open_questions/` additions) — nothing
from this plan. This plan wrote only the two files under `tests/security/` named above.

## `.planning/WINDOWS.md` — NOT edited here

Per ORCHESTRATION §7 and the explicit run instructions, this executor did **not** edit
`.planning/WINDOWS.md` even though the plan's `files_modified` lists it. The `request_id` entry is
recorded below in "Ledger entries owed" for the orchestrator to merge, with the corrected `open_count`.

## What did not go as planned

Nothing failed. Every test in both new files passed on first execution; no assertion was weakened, no
test was disabled. One thing worth recording: SQLAlchemy's `asyncpg` dialect installs its JSON/JSONB
codec at the DBAPI **connection** level (`setup_asyncpg_jsonb_codec`), not per-statement — confirmed by
reading the installed dialect source — which is what makes a raw `text()` `SELECT reason, details FROM
history.history_event` come back with `details` already decoded to a Python `dict` rather than a JSON
string, and is what the successful-append marker test's stored-value assertion relies on.

## Ledger entries owed

### `.planning/WINDOWS.md` (broken windows)

- **NEW.** `kind: deviation` / `phase: 04` / `file: src/prope/call_ledger/schemas.py` / `line: 442` —
  `request_id=request_id` is logged and `request_id` is not a member of
  `src/prope/observability.py`'s `LOGGABLE_FIELDS`. A Phase 2 omission in a Phase 2 file; `request_id` is
  ADR-0003's error-envelope correlation id (an identifier, plainly loggable, plainly not a body) and the
  fix is one word, but it is a third cross-phase edit into a Phase 2 file that no requirement in this
  phase asks for. Routed instead to the Phase 6 AST gate (AC-8), which will go red on arrival at this line
  until fixed. **`open_count` becomes 5** with this entry added to the existing four.

### `.planning/ORCHESTRATION-DECISIONS.md`

| Phase | Plan | Decision | Rejected alternative | Reversibility |
|---|---|---|---|---|
| 04 | 04 | **A-046 for property-history ships as a runtime marker assertion over exercised paths; the AST gate over `src/prope/` is routed to Phase 6 (AC-8)** rather than built here | Building the AST gate now — it goes red on arrival at `src/prope/call_ledger/schemas.py:442` for a Phase 2 reason this phase has no requirement to fix, would route a mechanism into Phase 6 rather than let that phase choose it, and cannot see a dynamically-built `**fields` payload anyway | reversible — the gate can still be built in Phase 6 or later; the marker tests are not deleted by adding it |

### `.planning/phases/04-.../deferred-items.md`

- No new item beyond the two already routed above. Both are already reflected in this SUMMARY's "Two
  items handed forward" section and in the two ledger tables above; nothing further is owed against this
  plan's own `deferred-items.md` sections.
