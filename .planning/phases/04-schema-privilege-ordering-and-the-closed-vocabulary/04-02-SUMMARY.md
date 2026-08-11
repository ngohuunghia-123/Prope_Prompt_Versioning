---
phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
plan: 02
subsystem: backend
tags: [property-history, vocabulary, registry, append-path, adr-0023, adr-0038, ph-05, a-046, metrics]

# Dependency graph
requires:
  - phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
    plan: 01
    provides: "alembic/versions/0005 — the history schema, both tables, the grant matrix and the 31-row seed; tests/property_history/__init__.py's factories and count constants; the two-schema test rig"
  - phase: 01-data-model-pricing-and-retention
    plan: 01
    provides: "src/prope/db/session.py's workspace_transaction and src/prope/db/metadata.py's one shared MetaData"
  - phase: 01-data-model-pricing-and-retention
    plan: 02
    provides: "tests/conftest.py's role-scoped engines and the autouse truncate fixture; tests/architecture/test_schema_invariants.py's drift-guard shape"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 01
    provides: "src/prope/observability.py — LOGGABLE_FIELDS and the Counter declaration pattern this plan extends"
provides:
  - "src/prope/property_history/ — the module's first source: the vocabulary, the registry loader, the validating write path and one counter, with no FastAPI import at any depth"
  - "load_action_registry(session) — ADR-0038's immutable MappingProxyType, loaded on a session with no tenant context, raising RuntimeError on an empty table"
  - "record_event(session, event, registry) — D-64's write path on the CALLER's session; never a sessionmaker, never commit/rollback/begin"
  - "check_event(event, registry) — D-62's single validation site: unknown_action, then unknown_detail_key, then missing_reason"
  - "HistoryAppendRejected — the one increment site for prope_property_history_append_rejected_total and the one site that emits property_history.append_rejected"
  - "LOGGABLE_FIELDS grown 9 -> 18, with `reason` reserved to call-ledger's meaning and property-history's token renamed `rejection_reason`"
  - "tests/property_history/load_registry(app_sessionmaker) — the one way every history test in phases 4-6 obtains record_event's registry argument"
  - "A history drift guard in tests/architecture/test_schema_invariants.py, pinned at 2 declared tables"
affects: [04-03, 04-04, 04-VERIFICATION, 05-property-history-read-path, 06-property-history-observability, 07-access-control]

actuals:
  tokens: 78000
  tasks: 3
  commits: 0

tech-stack:
  added: []
  patterns:
    - "A per-module observability.py holding only that module's metrics, while LOGGABLE_FIELDS stays project-wide in src/prope/observability.py"
    - "The counter and the log line inside the exception's __init__, so the label value can only be an enum member and a swallowed refusal still leaves a trace"
    - "A library function that takes an AsyncSession and never a sessionmaker — the inverse of call-ledger's D-19, and the shape ADR-0023 requires"
    - "MappingProxyType returned over a local dict that is dropped, so 'immutable after load' is a fact about the object rather than about a name"
    - "A drift guard per schema with its own pinned count, rather than a parameterisation of the ledger one"
    - "An integration test that IS the caller: it opens the transaction, writes a valid row first, and asserts through the owner role that the valid row went too"

key-files:
  created:
    - src/prope/property_history/__init__.py
    - src/prope/property_history/domain.py
    - src/prope/property_history/observability.py
    - src/prope/property_history/models.py
    - src/prope/property_history/registry.py
    - src/prope/property_history/append.py
    - tests/integration/test_action_registry_loads_without_a_tenant.py
    - tests/unit/test_details_allow_list.py
    - tests/integration/test_unregistered_detail_key_fails_the_transaction.py
  modified:
    - src/prope/observability.py
    - tests/architecture/test_schema_invariants.py
    - tests/property_history/__init__.py

key-decisions:
  - "ORCHESTRATION §12 overrides this plan's comment-density instructions and was applied. The plan prescribes six module docstrings carrying multi-paragraph arguments plus a `#:` block per LOGGABLE_FIELDS entry. What was kept: the arguments a reader cannot reconstruct from the code — the caller-owns-the-transaction posture, the not-a-ValueError reason, the two-enforcement-layers seam, the seq-is-absent note, the jsonb-cast note, the check-order argument, and the LOGGABLE_FIELDS decision — each at a fraction of the prescribed length. What was cut: every restatement of an ADR, every narration of visible code, and the plan's instruction to re-argue ADR-0038 and ADR-0023 in full at three separate files"
  - "Task 1's checkpoint resolved as adopted-UNCONFIRMED and NOT re-opened: `reason` keeps call-ledger's meaning exclusively; property-history's classification token travels as `rejection_reason`; the user-authored `reason` string gets no allow-list name at all. Nine names added (rejection_reason, detail_key, event_id, action, target_type, target_id, scope_prompt_id, actor_id, writing_module), 9 -> 18 counted in the process, not copied. The decision is argued in place at the block, and src/prope/observability.py's opening sentence now scopes the COUNTERS to Phase 2 while stating LOGGABLE_FIELDS is project-wide"
  - "HistoryEventDraft.__post_init__ raises ValueError and that does NOT violate the plan's ValueError prohibition. The prohibition and its acceptance criterion both name the APPEND path; __post_init__ runs at the caller's own construction time, before check_event exists in the frame, and it is the exact shape call_ledger.seams.EvalUsageRow uses. HistoryAppendRejected subclasses Exception directly, and check_event/record_event raise nothing else"
  - "The four validation rules in __post_init__ are id-prefix, tz-aware occurred_at, actor_id-unless-system and reason length. The last three mirror the engine (ck_history_event_actor_id_present_unless_system, ck_history_event_reason_length) deliberately, so a caller meets a sentence naming the field rather than a constraint name it cannot act on. The model is nowhere weaker than the engine"
  - "The empty-registry test builds its own owner sessionmaker with build_sessionmaker(migrate_engine) and drives the DELETE + rollback on ONE session without session.begin(), so the AsyncSession's autobegin is what opens the transaction and an explicit rollback ends it. Using `async with session.begin()` would have committed the DELETE and destroyed the seed for every later test; the test also asserts the 31 rows survive afterwards, which is the vacuity guard"
  - "models.py declares the two tables for the drift guard and for nothing else, and no code in src/prope/property_history/ selects through them — both statements the module issues are raw text(), which is what keeps them inside tests/architecture/test_no_sql_interpolation.py's walk (ALLOWED is still empty)"
  - "The history drift guard is a NEW test with its own pinned count of 2 rather than a parameterisation of test_every_declared_model_matches_a_live_table, whose count of six is call-ledger's. prope.property_history.models is imported under an alias and USED in the assertion rather than imported for its side effect, so ruff cannot flag it and a reader cannot delete it as unused"
  - "min(unregistered) picks the offending key for a deterministic message and not for meaning; (event.reason or '').strip() refuses a whitespace-only reason where the engine cannot. Both carry a one-line WHY at the code"
  - "record_event binds json.dumps(dict(event.details)) rather than json.dumps(event.details) — `details` is typed Mapping, and json.dumps does not accept every Mapping. A one-word difference from the plan's literal, with an identical end state"

patterns-established:
  - "A module's own observability.py declares only that module's metrics and never re-declares configure_logging; the project-wide log-field allow-list stays in src/prope/observability.py and grows by addition, never by redefinition"
  - "Where two bounded contexts want one log field name for two different kinds of value, the second context renames its own side and the forbidden value is expressed as an ABSENCE from the allow-list rather than as a subtraction rule"
  - "A refusal type increments its counter and emits its log line in __init__, so there is one site, the label cannot drift, and a caller that swallows the exception still leaves a countable trace"
  - "A test that claims 'the caller's transaction rolled back' must itself be the caller and must write a valid row first, then assert that row is gone through the owner role"
  - "A registry loader that finds zero rows raises RuntimeError naming the table, not the module's own refusal type: an empty vocabulary is an environment fault, and under Phase 5's process-start load it becomes a startup failure"

requirements-completed: [PH-05]

coverage:
  - id: D1
    description: "load_action_registry, on a session with NO tenant context, returns an immutable mapping of 31 RegisteredAction rows whose detail_keys are frozensets"
    requirement: PH-05
    verification:
      - kind: integration
        ref: "tests/integration/test_action_registry_loads_without_a_tenant.py::test_the_registry_loads_on_a_session_with_no_tenant_context"
        status: pass
      - kind: integration
        ref: "tests/integration/test_action_registry_loads_without_a_tenant.py::test_two_known_rows_round_trip_with_their_declared_types"
        status: pass
    human_judgment: false
  - id: D2
    description: "The returned mapping cannot be mutated — assigning into it raises TypeError"
    verification:
      - kind: integration
        ref: "tests/integration/test_action_registry_loads_without_a_tenant.py::test_the_loaded_mapping_cannot_be_mutated"
        status: pass
    human_judgment: false
  - id: D3
    description: "An empty registry raises RuntimeError naming history.history_action_registry, proven through the owner role inside a transaction that deletes the rows and is then rolled back"
    verification:
      - kind: integration
        ref: "tests/integration/test_action_registry_loads_without_a_tenant.py::test_an_empty_registry_raises_naming_the_table"
        status: pass
    human_judgment: false
  - id: D4
    description: "record_event opens no transaction, commits nothing and rolls nothing back; its first parameter is an AsyncSession and the module contains no sessionmaker"
    requirement: PH-05
    verification:
      - kind: integration
        ref: "tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_a_valid_event_is_written_inside_the_callers_transaction"
        status: pass
      - kind: command
        ref: "grep -n 'sessionmaker\\|session.commit\\|session.rollback\\|session.begin' src/prope/property_history/append.py -> no output"
        status: pass
    human_judgment: false
  - id: D5
    description: "A valid event written on a caller-opened transaction that the caller then abandons leaves no row, read through the owner role outside RLS"
    requirement: PH-05
    verification:
      - kind: integration
        ref: "tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_an_abandoned_caller_transaction_leaves_no_event"
        status: pass
    human_judgment: false
  - id: D6
    description: "An unregistered action raises HistoryAppendRejected with reason unknown_action, before any SQL is issued"
    requirement: PH-05
    verification:
      - kind: unit
        ref: "tests/unit/test_details_allow_list.py::test_an_unregistered_action_is_refused"
        status: pass
      - kind: integration
        ref: "tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_an_unregistered_action_and_a_missing_reason_each_roll_back_and_count[unknown_action]"
        status: pass
    human_judgment: false
  - id: D7
    description: "An unregistered details key raises with unknown_detail_key, and the message names the offending KEY and never the offending value"
    requirement: PH-05
    verification:
      - kind: unit
        ref: "tests/unit/test_details_allow_list.py::test_the_refusal_message_names_the_key_and_never_the_value"
        status: pass
      - kind: integration
        ref: "tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_an_unregistered_detail_key_rolls_the_callers_transaction_back"
        status: pass
    human_judgment: false
  - id: D8
    description: "An action whose registry row requires a reason, called with None or whitespace only, raises with missing_reason"
    requirement: PH-05
    verification:
      - kind: unit
        ref: "tests/unit/test_details_allow_list.py::test_a_missing_reason_is_refused_where_the_registry_requires_one"
        status: pass
      - kind: unit
        ref: "tests/unit/test_details_allow_list.py::test_a_whitespace_only_reason_is_refused"
        status: pass
      - kind: integration
        ref: "tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_an_unregistered_action_and_a_missing_reason_each_roll_back_and_count[missing_reason]"
        status: pass
    human_judgment: false
  - id: D9
    description: "A refused append leaves the caller's whole transaction unwritten, including a valid event written in the same transaction before it — asserted through the owner role"
    requirement: PH-05
    verification:
      - kind: integration
        ref: "tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_an_unregistered_detail_key_rolls_the_callers_transaction_back"
        status: pass
    human_judgment: false
  - id: D10
    description: "prope_property_history_append_rejected_total increments by exactly one on the matching reason label and by zero on the other two, and the increment survives the rollback"
    requirement: PH-05
    verification:
      - kind: integration
        ref: "tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_an_unregistered_detail_key_rolls_the_callers_transaction_back"
        status: pass
      - kind: integration
        ref: "tests/integration/test_unregistered_detail_key_fails_the_transaction.py::test_an_unregistered_action_and_a_missing_reason_each_roll_back_and_count"
        status: pass
    human_judgment: false
  - id: D11
    description: "RejectionReason has exactly three members, byte-identical to the label set the lock file declares"
    verification:
      - kind: unit
        ref: "tests/unit/test_details_allow_list.py::test_rejection_reason_has_exactly_the_three_declared_label_values"
        status: pass
    human_judgment: false
  - id: D12
    description: "The three checks run in the order unknown_action, unknown_detail_key, missing_reason, and a draft failing two reports the earlier one"
    verification:
      - kind: unit
        ref: "tests/unit/test_details_allow_list.py::test_an_earlier_check_wins_when_a_draft_fails_two"
        status: pass
    human_judgment: false
  - id: D13
    description: "src/prope/property_history/ imports FastAPI at no depth and touches neither src/prope/app.py nor src/prope/worker.py"
    verification:
      - kind: command
        ref: "grep -rn 'fastapi' --include=*.py src/prope/property_history/ -> exit 1, no matches"
        status: pass
      - kind: command
        ref: "git diff src/prope/worker.py -> empty; src/prope/app.py's modification predates this plan (see 'What is NOT this plan's')"
        status: pass
    human_judgment: false
  - id: D14
    description: "The two declared history tables match live columns; the drift guard is non-vacuous because the module is imported and used"
    verification:
      - kind: architecture
        ref: "tests/architecture/test_schema_invariants.py::test_every_declared_history_model_matches_a_live_table"
        status: pass
    human_judgment: false
  - id: D15
    description: "The whole suite is green and ruff check is clean"
    verification:
      - kind: command
        ref: "uv run pytest -q -> 457 passed, 1 skipped, 1 warning in 291.07s"
        status: pass
      - kind: command
        ref: "uv run ruff check src/ tests/ alembic/ -> All checks passed!"
        status: pass
    human_judgment: false
  - id: D16
    description: "The LOGGABLE_FIELDS resolution and the record_event naming cost are the intended readings"
    verification: []
    human_judgment: true
    rationale: "The plan's two <human-check> items. Both are adjudications rather than properties a test can assert; every mechanical half is built and asserted, and both are rows already sitting in deferred-items.md §2 owed to ORCHESTRATION-DECISIONS.md."

# Metrics
duration: 54min
completed: 2026-08-11
status: complete
---

# Phase 04 Plan 02: The module, the registry and the validating write path — Summary

**PH-05 holds, and the test that says so is the caller.** An append carrying an unregistered `details`
key raises `HistoryAppendRejected`, the caller's transaction rolls back with **no partial state** —
proven by a *valid* event written in the same transaction beforehand that is also gone when read through
`prope_migrate` outside RLS — and `prope_property_history_append_rejected_total` increments by exactly
one on `unknown_detail_key` and by zero on the other two labels. The counter survives the rollback
because a `prometheus_client` counter is process state, which is the whole reason it is the right
instrument for a failure whose signature is that the transaction did not happen.

The naive version of that test — `SELECT count(*) FROM history.history_event` is zero — is not what was
written, because it passes identically against a module that opened and rolled back *its own*
transaction. That is call-ledger's D-19 shape and the one arrangement ADR-0023 forbids.

## What Phase 4 ships under a name no downstream spec uses

`record_event` is D-64's deliberate compromise and it is stated here rather than left to be discovered.
`docs/modules/property-history.lock.yml` `apis.exposes` names exactly three internal functions —
`append(event)`, `read(scope, cursor, limit)`, `registered_actions()` — and `record_event` is none of
them. ROADMAP puts `append()` in Phase 5 while `.planning/REQUIREMENTS.md` routes PH-05 to Phase 4, and
PH-05 is not observable without a write path. **Phase 5 renames or wraps `record_event` as INT-006's
`append()`, and `record_event` must not survive as a public name past Phase 5.**

Three capabilities are deliberately absent, each with the phase that owns it:

| Absent | Owner | Why not here |
|---|---|---|
| `scope_prompt_id` as a contract, and the A-119 guard on a prompt-scoped action arriving without one | **Phase 6** | The lock routes the guard to `null_scope_prompt_total`, a metric, and the six other metrics are Phase 6's |
| `read()` and its cursor semantics | **Phase 5** | Nothing yet reads a history row back through the module |
| The process-start registry global, and its wiring into `app` / `worker` | **Phase 5** | Nothing here is a module global, deliberately, so Phase 5 introduces one rather than inheriting a mutable one somebody already reached for |

AC-6 — the registry equalling the union of five lock files' event lists — is likewise Phase 5's, and the
loader test says so in its own docstring so the omission reads as a boundary rather than as a gap.

## The `LOGGABLE_FIELDS` resolution, adopted UNCONFIRMED

Task 1's checkpoint was resolved as the plan adopted it and was **not** re-opened (ORCHESTRATION §6: a
decision the plan already made and argued is not a new adoption).

**`reason` keeps call-ledger's meaning exclusively.** For call-ledger it is a closed-vocabulary token
(`unroutable | nacked | timeout`, `envelope_invalid`, `CeilingReason`); for property-history it would be
user-authored Vietnamese free text the lock file forbids logging at all. property-history's
classification token is therefore promoted to its own name, **`rejection_reason`**, and the
user-authored `reason` string gets **no allow-list name at all** — an absence needs no maintenance where
a subtraction rule needs somebody to keep believing it.

Nine names were added — `rejection_reason`, `detail_key`, `event_id`, `action`, `target_type`,
`target_id`, `scope_prompt_id`, `actor_id`, `writing_module` — taking the set from **9 to 18**, counted
in the file rather than copied from the plan. The decision itself is argued **in place**, in the `"job"`
entry's register, and `src/prope/observability.py`'s opening sentence now says that the **counters**
there are Phase 2's while `LOGGABLE_FIELDS` is project-wide and Phase 4 is the first phase to extend it
from a second module. **This is a cross-phase edit into a Phase 2 file, and it is the shape seven more
modules inherit** — it is the plan's first `<human-check>` and it belongs in front of a person.

No AST gate was built. Whether A-046 becomes enforced rather than conventional is plan 04-04's
checkpoint.

## Three deviations, recorded without an OQ

All three were declared by the plan and are already rows in `deferred-items.md` §3.

1. **`pydantic`'s scope is narrowed and this module ships frozen dataclasses.** The lock's
   `libraries_frameworks` says pydantic validates the `details` payload against the allow-list, and
   concedes in the same field that it was chosen because it is the baseline's validation library rather
   than for a property of this module. The check is `frozenset(details) - registered.detail_keys` — one
   line. Expressing it in pydantic means thirty-one `create_model(…, extra="forbid")` models built from
   registry rows, which turns one clear refusal into a `ValidationError` that then has to be translated
   back into a three-member vocabulary — **a fourth failure mode on the path whose entire point is that
   it has exactly three.** `RegisteredAction` and `HistoryEventDraft` are `@dataclass(frozen=True,
   slots=True)`, matching `call_ledger/domain.py`. End state identical. **A deviation in mechanism**, on
   D-50's footing.
2. **AC-5's `test_ref` path moves** from `tests/unit/` to `tests/integration/`. "The caller's transaction
   rolls back with no partial state" is not observable without a database, and `tests/unit/` here means
   pure Python. **Both halves of AC-5 are asserted**, which is more than the single named file would have
   delivered. A `test_ref` names a file, not a guarantee.
3. **`HistoryEventDraft` carries an eleventh field, `id`, that INT-006's ten-field envelope does not
   name.** Unlike `seq`, it is not declared database-assigned either, because A-045 / ADR-0003 make it
   the provider's to mint. It is carried with a `hev_`-prefixed default factory so `record_event` can
   return a value the caller already holds. **Handed to Phase 5**, which owns INT-006's signature and
   must reconcile the two. `__post_init__` closes the cheap half meanwhile: an `id` without the prefix
   is refused.

## ORCHESTRATION §12 was applied over this plan's comment instructions

The plan prescribes six module docstrings carrying multi-paragraph arguments and a `#:` block per
`LOGGABLE_FIELDS` entry. §12 outranks all of it, and the plan's own header says so.

**What was kept**, because a competent reader cannot reconstruct it from the code: the
caller-owns-the-transaction posture and its inverse relationship to `call_ledger/seams.py:37-48`; why
`HistoryAppendRejected` is not a `ValueError` and why its name deliberately reads wrong inside an
`except`; the two-enforcement-layers seam between `fk_history_event_action` and `check_event`; the
`seq`-is-absent note; the jsonb-cast note; the check-order argument; the empty-registry `RuntimeError`
posture; and the `reason` / `rejection_reason` decision. Each is one to four lines, not the paragraph the
plan prescribed. The per-entry `LOGGABLE_FIELDS` comments were kept at one line each because the
acceptance criterion names them and because each argues *why the name is not content*, which is the
A-046 argument rather than a restatement.

**What was cut**: every re-argument of ADR-0023, ADR-0024 and ADR-0038 the plan asked for at three
separate files, every narration of visible code, and the plan's instruction to state six "load-bearing
absences" as prose in `__init__.py` (three are stated; the other three are visible in the source and in
this document).

## The `seq` grep, named rather than left to be found

The plan's acceptance criterion says *"the token `seq` does not appear anywhere in `append.py`"*, while
the same plan's `<action>` **instructs** the `#:` block above `INSERT_HISTORY_EVENT` to say that `seq` is
absent from the column list and why. The two cannot both hold. The comment was kept — it is exactly the
kind of surprising absence §12 asks to be commented — so `grep seq src/prope/property_history/append.py`
returns **one prose hit and no code hit**. Identical to how plan 04-01 handled `ON DELETE` and
`REVOKE UPDATE` in revision 0005, and named here so a verifier's grep reads as known rather than as a
gap. The substantive property — `INSERT_HISTORY_EVENT` names exactly eleven columns and `seq` is not one
of them — holds.

The same shape applies to `grep -ri fastapi src/prope/property_history/`: the case-**sensitive** grep
for the import spelling returns nothing, and the only hit under `-i` is the `__init__.py` sentence the
plan instructed be written (`**Nothing here imports FastAPI, at any depth**`).

## What did not go as planned

**Nothing failed.** Every intermediate gate and the full suite were green on first execution, with no
test disabled, no assertion weakened and no existing assertion changed in meaning. Four things were
verified rather than assumed:

- **`ruff` N818 fires on test code too.** The sentinel exception the abandoned-transaction test raises
  had to be `_AbandonedError`, not `_Abandoned`. Caught by the lint gate before the suite ran.
- **`min(unregistered)` on a `frozenset` of one is the whole message contract.** `detail_key` is
  asserted equal to `"not_registered"` in the integration test and `"gamma"` in the unit test, so the
  determinism claim is exercised rather than stated.
- **The empty-registry test must not use `session.begin()`.** That context manager commits at exit,
  which would have committed a `DELETE` of the seeded vocabulary and broken every later test in the
  session with `unknown_action` — Pitfall 10's symptom arriving from a different direction. The test
  relies on the `AsyncSession`'s autobegin and ends with an explicit `rollback()`, then asserts the 31
  rows survive.
- **`json.dumps` does not accept every `Mapping`.** `details` is typed `Mapping[str, object]`, so
  `record_event` binds `json.dumps(dict(event.details))`. One word away from the plan's literal, with an
  identical end state.

## What is NOT this plan's

`git status --porcelain src/prope/app.py` reports the file **modified**. That change is **not this
plan's**: its content is the publisher-stop `except`-clause rework (WR-14 / CR-03), its mtime precedes
this execution by roughly forty minutes, and this plan neither imports from nor writes to `app.py`.
`src/prope/worker.py`, `docs/`, `pyproject.toml` and `uv.lock` are all clean.

## The gate, observed

```
uv run ruff check src/ tests/ alembic/
All checks passed!
```

```
uv run pytest -q
457 passed, 1 skipped, 1 warning in 291.07s (0:04:51)
```

The one `s` is Phase 3's `PROPE_RUN_LOAD`-gated load test, unchanged. Twenty tests are new: ten in
`tests/unit/test_details_allow_list.py`, four in
`tests/integration/test_action_registry_loads_without_a_tenant.py`, five in
`tests/integration/test_unregistered_detail_key_fails_the_transaction.py` (four functions, one
parameterised twice) and one drift guard. `uv run ruff format --check` was not run: it fails repo-wide
on Broken Window #1, it is not the gate, and it is not this plan's to fix. `make check` was not run
because its `format` target writes.

Intermediate gates, both green before the full run:

```
uv run pytest tests/unit/test_details_allow_list.py -q                              -> 10 passed
uv run pytest tests/integration/test_action_registry_loads_without_a_tenant.py \
              tests/integration/test_unregistered_detail_key_fails_the_transaction.py \
              tests/architecture/ -q                                                -> 91 passed
```

`tests/architecture/test_no_sql_interpolation.py`'s `ALLOWED` is still `frozenset()` — nothing this
module writes needs an exception.

## Ledger entries owed

### `.planning/phases/04-.../deferred-items.md`

- **§3, confirmed by execution.** All three declared deviations were implemented exactly as §3 describes
  them: pydantic narrowed in favour of frozen dataclasses, AC-5's `test_ref` moved to
  `tests/integration/`, and `HistoryEventDraft`'s eleventh field with `__post_init__` refusing a
  non-`hev_` id. No OQ was raised for any of them and none is owed.
- **NEW — §3.** *The plan's acceptance criterion "the token `seq` does not appear anywhere in
  `append.py`" is satisfied modulo one prose hit*: the `#:` block above `INSERT_HISTORY_EVENT` states the
  absence, which the same plan's `<action>` instructs. No code names `seq`. Same shape as plan 04-01's
  `ON DELETE` / `REVOKE UPDATE` prose hits; recorded so a verifier's grep miss reads as known.
- **NEW — §3.** *`grep -ri fastapi src/prope/property_history/` returns one hit*, in the `__init__.py`
  sentence the plan instructed. The case-sensitive grep for the import spelling returns nothing, which is
  the property the prohibition is about.
- **NEW — §5, handed forward.** *`record_event` binds `json.dumps(dict(event.details))`.* If Phase 5's
  `append()` widens `details` to a type whose `dict()` is expensive or lossy, this is the line that
  cares. Owner: **Phase 5**.
- **§5, still owed and unchanged.** The shared prefixed-ULID helper trigger (**Phase 7**) — this plan
  added the third instance, `EVENT_ID_PREFIX = "hev_"`, with the reason written at the constant, and
  introduced no helper.

### `.planning/ORCHESTRATION-DECISIONS.md`

Rows 6 and 7 of `deferred-items.md` §2 both land in this plan and are both now **built and asserted**:

| Phase | Plan | Decision | Rejected alternative | Reversibility |
|---|---|---|---|---|
| 04 | 02 | **D-64** — the validating write path ships in Phase 4 under the name `record_event`, which no downstream spec uses; Phase 5 renames or wraps it as INT-006's `append()`. **A tension between two authorities**, not a preference: ROADMAP puts `append()` in Phase 5 while REQUIREMENTS routes PH-05 to Phase 4 | Putting `append()` entirely in Phase 5, which makes this phase's third success criterion unprovable (forbidden by ORCHESTRATION §9) | cheap — the rename costs one module |
| 04 | 02 | **`LOGGABLE_FIELDS` on `reason`** — `reason` keeps call-ledger's meaning exclusively; property-history's token is renamed `rejection_reason`; the user-authored `reason` string has **no allow-list name at all**. The set grows 9 → 18 and the file's scope sentence is edited in the same change | A per-module allow-list (ships two frozensets nobody reads unless an AST checker is built with them, and makes A-046 a property a module can forget to assert — ADR-0045's own argument against); a floor-and-subtract rule (a deny-list wearing an allow-list's clothes, which that file's own docstring refuses) | **costly — seven more modules inherit the shape** |

Also newly adopted and reportable:

| Phase | Plan | Decision | Rejected alternative | Reversibility |
|---|---|---|---|---|
| 04 | 02 | **An empty action registry raises `RuntimeError` at load**, naming the table and saying the migration has not been applied | Returning an empty mapping (thirty-one identical `unknown_action` refusals at append time); raising `HistoryAppendRejected` (mis-classifies an environment fault as a caller bug, and pages) | cheap now, **one-way in effect once Phase 5 loads at process start** — it becomes a startup failure |
| 04 | 02 | **`HistoryEventDraft.__post_init__` mirrors three engine constraints in Python** (tz-aware `occurred_at`, `actor_id`-unless-system, `reason` ≤ 500 **characters**) and adds a fourth the engine has no counterpart for (the `hev_` prefix) | Leaving all four to the engine, which gives the caller a constraint name it cannot act on instead of a sentence naming the field | reversible |

### `.planning/WINDOWS.md` (broken windows)

- **No new broken window is opened by this plan.** Broken Window #1 (`ruff format --check` fails
  repo-wide on the 120-vs-100 disagreement) is unchanged and was worked around by writing every new file
  in the house ~100 style; `ruff check src/ tests/ alembic/` is green.
- **Not opened here, and it is plan 04-04's to record**: `request_id` is logged at
  `src/prope/call_ledger/schemas.py:442` and is not in `LOGGABLE_FIELDS`. This plan **grew** that set by
  nine names and deliberately did not add `request_id` — it is a Phase 2 omission in a Phase 2 file, and
  `deferred-items.md` §5 already names plan 04-04's executor as the recorder.
