---
phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
plan: 03
subsystem: backend
tags: [property-history, seq, ordering, overriding-system-value, architecture-gate, ph-04]

# Dependency graph
requires:
  - phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
    plan: 01
    provides: "alembic/versions/0005 — history.history_event with seq bigint GENERATED ALWAYS AS IDENTITY (CACHE 1), and the revision's seventh docstring paragraph naming the OVERRIDING SYSTEM VALUE boundary"
  - phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
    plan: 02
    provides: "src/prope/property_history/append.py's record_event/check_event and tests/property_history/load_registry(app_sessionmaker)"
provides:
  - "tests/integration/test_same_transaction_events_have_a_stable_order.py — PH-04 proven with a positive control that the compared timestamps are byte-identical"
  - "tests/security/test_history_seq_cannot_be_supplied.py — both halves of the identity guarantee: the engine refusal, and the OVERRIDING SYSTEM VALUE escape hatch proven to work"
  - "tests/architecture/test_no_overriding_system_value.py — the source gate over src/prope/ and alembic/, ALLOWED empty by construction"
affects: [04-04, 04-VERIFICATION, 05-property-history-read-path, 06-property-history-observability]

actuals:
  tokens: 46000
  tasks: 3
  commits: 0

tech-stack:
  added: []
  patterns:
    - "A gap-in-seq test provoked through a statement that reached the engine (an INSERT inside an abandoned transaction), never through a validation refusal, which issues no SQL and must leave no gap — asserted as two separate tests rather than one test with two id-reusing halves"
    - "A source gate walking two roots (src/prope/ and alembic/) with one shared ALLOWED frozenset keyed on (root_name, relative_path, lineno), because the rule is about a token breaking a total order rather than about runtime values reaching SQL"
    - "An AST-based token gate that exempts every module/class/function docstring by node identity, so a file's own explanation of the forbidden token does not fail the gate that forbids it"

key-files:
  created:
    - tests/integration/test_same_transaction_events_have_a_stable_order.py
    - tests/security/test_history_seq_cannot_be_supplied.py
    - tests/architecture/test_no_overriding_system_value.py
  modified: []

key-decisions:
  - "The post-OVERRIDING collision case: the determinate outcome asserted is 'the next engine-assigned seq is LOWER than the supplied one, and a read ordered by seq returns the later-written event first' — NOT the uq_history_event_seq collision the plan's first draft predicted. A supplied seq does not advance the sequence, so the next value stays below it; the collision branch is real in principle but unreachable in this rig because tests/conftest.py's TRUNCATE ... RESTART IDENTITY resets the sequence before every test and SUPPLIED_SEQ (9_000_000_000) is far above anything it has issued."
  - "Task 1's gap test and its validation-refusal sibling were split into two separate test functions rather than one test with two back-to-back sections, as the plan's prose suggested. Sharing one test would have required reusing EVENT_ID/OTHER_EVENT_ID/THIRD_EVENT_ID across both halves and colliding on history_event's primary key within the same test run; two tests with distinct local id literals for the second half avoid the collision and keep each assertion's positive control legible on its own."
  - "The source gate's ALLOWED frozenset carries a three-tuple (root_name, relative_path, lineno) rather than the two-tuple test_no_sql_interpolation.py uses, because this gate walks two roots and a bare relative path could collide between src/prope/ and alembic/. It ships empty, as the plan requires, because the one legitimate use of the token lives under tests/, outside both walked roots."
  - "ORCHESTRATION §12 applied: no per-column or per-constraint comment lists were written. Each file carries one module docstring stating the boundary/argument a reader cannot reconstruct from the code, plus targeted one-line notes at the SUPPLIED_SEQ constant, the ALLOWED frozenset, and the two 'do not fix this' test docstrings. No comment narrates visible code."

patterns-established:
  - "A test asserting 'a gap in seq is normal' provokes the gap through an INSERT that reached the engine inside an abandoned caller transaction (the same _AbandonedError shape plan 04-02 established), never through a validator refusal — and the sibling case (validation refusal, no gap) is a SEPARATE test so the two mechanisms differing is exercised rather than merely asserted in one place."

requirements-completed: [PH-04]

coverage:
  - id: T1
    description: "Two events written through record_event in one transaction, sharing occurred_at exactly, come back ordered by seq in write order, with a positive control that the compared occurred_at values really are identical"
    requirement: PH-04
    verification:
      - kind: integration
        ref: "tests/integration/test_same_transaction_events_have_a_stable_order.py::test_approval_precedes_release_when_their_timestamps_are_identical"
        status: pass
    human_judgment: false
  - id: T2
    description: "Three events written in one transaction order fully by seq"
    requirement: PH-04
    verification:
      - kind: integration
        ref: "tests/integration/test_same_transaction_events_have_a_stable_order.py::test_three_events_in_one_transaction_order_fully"
        status: pass
    human_judgment: false
  - id: T3
    description: "An INSERT that reached the engine and was then abandoned leaves a gap greater than one between the surrounding committed events' seq values"
    verification:
      - kind: integration
        ref: "tests/integration/test_same_transaction_events_have_a_stable_order.py::test_a_gap_in_seq_is_not_a_missing_event"
        status: pass
    human_judgment: false
  - id: T4
    description: "A validation refusal between two writes leaves a difference of exactly one — the two mechanisms (rolled-back INSERT vs. validation refusal) are distinguished, not conflated"
    verification:
      - kind: integration
        ref: "tests/integration/test_same_transaction_events_have_a_stable_order.py::test_a_validation_refusal_between_two_writes_leaves_no_gap"
        status: pass
    human_judgment: false
  - id: T5
    description: "Events written in two transactions in a single-threaded test also come back in write order, with the docstring naming this as single-threaded-only"
    verification:
      - kind: integration
        ref: "tests/integration/test_same_transaction_events_have_a_stable_order.py::test_two_transactions_in_sequence_also_order_by_seq"
        status: pass
    human_judgment: false
  - id: T6
    description: "An INSERT naming seq with a value, attempted as prope_app, raises DBAPIError whose lowercased message contains 'generated always', corroborated by SQLSTATE 428C9 where the driver exposes it"
    requirement: PH-04
    verification:
      - kind: security
        ref: "tests/security/test_history_seq_cannot_be_supplied.py::test_an_insert_naming_seq_is_refused_by_the_engine"
        status: pass
    human_judgment: false
  - id: T7
    description: "The identical INSERT with seq omitted lands one row whose seq is not null — the positive control"
    verification:
      - kind: security
        ref: "tests/security/test_history_seq_cannot_be_supplied.py::test_the_same_insert_without_seq_succeeds"
        status: pass
    human_judgment: false
  - id: T8
    description: "OVERRIDING SYSTEM VALUE succeeds as prope_app with no privilege change, the stored seq is the supplied value, the next record_event succeeds with a LOWER seq, and a seq-ordered read returns the later-written event first"
    requirement: PH-04
    verification:
      - kind: security
        ref: "tests/security/test_history_seq_cannot_be_supplied.py::test_overriding_system_value_is_accepted_and_that_is_the_recorded_boundary"
        status: pass
    human_judgment: false
  - id: T9
    description: "No statement under src/prope/ or alembic/ (outside a docstring) contains OVERRIDING SYSTEM VALUE / OVERRIDING USER VALUE"
    requirement: PH-04
    verification:
      - kind: architecture
        ref: "tests/architecture/test_no_overriding_system_value.py::test_no_module_supplies_its_own_seq"
        status: pass
    human_judgment: false
  - id: T10
    description: "The gate found modules to check in both roots, and append.py is among the walked modules"
    verification:
      - kind: architecture
        ref: "tests/architecture/test_no_overriding_system_value.py::test_the_walk_actually_found_modules_to_check"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_no_overriding_system_value.py::test_the_append_path_is_covered_by_this_walk"
        status: pass
    human_judgment: false
  - id: T11
    description: "The gate is committed as a proof over a snippet, not a temporary local edit: it catches a non-docstring occurrence and exempts a module docstring carrying the same token"
    verification:
      - kind: architecture
        ref: "tests/architecture/test_no_overriding_system_value.py::test_the_gate_ignores_docstrings_but_catches_a_non_docstring_constant"
        status: pass
    human_judgment: false
  - id: T12
    description: "The whole targeted subset is green and ruff check is clean"
    verification:
      - kind: command
        ref: "uv run pytest tests/architecture/ tests/integration/test_same_transaction_events_have_a_stable_order.py tests/security/test_history_seq_cannot_be_supplied.py -q -> 134 passed"
        status: pass
      - kind: command
        ref: "uv run ruff check src/ tests/ alembic/ -> All checks passed!"
        status: pass
    human_judgment: false

# Metrics
duration: 38min
completed: 2026-08-11
status: complete
---

# Phase 04 Plan 03: Ordering, the identity boundary, and the source gate — Summary

**PH-04 holds.** Two events written through `record_event` in one caller-opened transaction, carrying
byte-identical `occurred_at` values, come back ordered approval-then-release by `seq`, and a positive
control (`len({row.occurred_at ...}) == 1`) proves the timestamps really are identical — so the ordering
is demonstrably not a timestamp tiebreak. A three-event chain orders fully. Both halves of the identity
guarantee are recorded: the engine refuses a hand-written `INSERT` naming `seq` (`generated always` in the
message, `428C9` where the driver exposes it), and `OVERRIDING SYSTEM VALUE` **succeeds** with no
privilege change — the honest, checked boundary the plan calls for rather than a belief.

## The determinate outcome after `OVERRIDING`, stated as the plan's `<output>` requires

**A supplied `seq` does not advance the sequence.** After `INSERT_WITH_OVERRIDING_SYSTEM_VALUE` supplies
`seq = 9_000_000_000`, the next ordinary `record_event` takes a value far **lower** than that — it
succeeds, and a `SELECT ... ORDER BY seq` returns the later-written event *first*. That is the assertion
`test_overriding_system_value_is_accepted_and_that_is_the_recorded_boundary` makes. The other possibility
the plan's first draft predicted — a `uq_history_event_seq` collision refusing the next append — is real in
principle and **unreachable in this rig**: `tests/conftest.py`'s `TRUNCATE ... RESTART IDENTITY` resets the
identity sequence before every test, and the supplied value sits far above anything it could plausibly
issue. The test names that unreachability explicitly rather than asserting a branch it cannot provoke.

## The two inferences nothing may make from `seq`, in this plan's own words

1. **A gap in `seq` is not evidence an event was deleted.** `nextval` and `setval` are never rolled back:
   a statement that *reached the engine* consumes a value whether or not its transaction survives.
   `test_a_gap_in_seq_is_not_a_missing_event` provokes the gap the correct way — a valid `INSERT` inside a
   transaction the caller then abandons by raising a sentinel — and asserts the difference is `> 1`. Its
   sibling, `test_a_validation_refusal_between_two_writes_leaves_no_gap`, proves the other mechanism: a
   *validation* refusal (`check_event` raising `HistoryAppendRejected` before any SQL is issued) leaves a
   difference of exactly `1`, because `nextval` is never called. Asserting only the gap would leave the
   loose, false version of the claim ("refusals cause gaps") equally consistent with the evidence — this
   is why the two are two tests, not one.
2. **Assignment order is not commit order — and this is stated, not tested.** Inside one transaction `seq`
   is exact (that is everything the first four tests prove). Across concurrent transactions it is not: two
   transactions can take 5 and 6 and commit 6 first, so a reader between the two commits sees 6 with no 5.
   `test_two_transactions_in_sequence_also_order_by_seq`'s docstring names this and hands it to
   **Phase 5's cursor pagination** — a `seq > N` poll would permanently skip a row; INT-007 paginates
   `seq DESC`, the safer direction. Nothing here exercises two genuinely concurrent transactions, which the
   plan's own `<threat_model>` flags as the honest gap in this plan (T-04-23, accepted and handed forward).

## Task 3's decision, and why it stands as adopted

Built, as the plan's own argument concludes: a property whose only defence is "nobody would do that" is a
property nobody is defending, and the gate is cheap — a walk over source, reversible by deleting one file.
`ALLOWED` ships empty; the one legitimate occurrence of the token
(`INSERT_WITH_OVERRIDING_SYSTEM_VALUE` in Task 2's file) lives under `tests/`, outside both roots this gate
walks, by construction — the docstring says so rather than leaving the empty set to look like an oversight.

## One structural deviation from the plan's literal prose, with an identical end state

The plan's Task 1 prose describes the gap test and its validation-refusal sibling as two sections of *"the
same test or a sibling one."* They are written as **two separate test functions**
(`test_a_gap_in_seq_is_not_a_missing_event` and `test_a_validation_refusal_between_two_writes_leaves_no_gap`)
rather than one function with two back-to-back sections. Reason: `history_event`'s primary key is `id`, and
the shared fixture package exports exactly three id constants (`EVENT_ID`, `OTHER_EVENT_ID`,
`THIRD_EVENT_ID`). A single test using all three for the gap half and then reusing any of them for the
validation half collides on the primary key within the same test's transaction history. Splitting into two
tests with two fresh local id literals for the second half (`hev_...0004`, `hev_...0005`) avoids the
collision while asserting exactly what the plan's `<behavior>` block requires. Both mechanisms are still
distinguished in the same file, which is the property the plan cares about; no OQ is owed (ORCHESTRATION
§5 — spelling difference, byte-identical guarantee, no behavioural change).

## No source, migration, or dependency change

This plan wrote only the three files in `files_modified`. `git status --porcelain src/ alembic/ docs/
pyproject.toml uv.lock` shows modifications to `src/prope/app.py`, `src/prope/call_ledger/enqueue.py`,
`src/prope/observability.py`, and new files under `alembic/versions/`, `src/prope/property_history/` and
`docs/brainstorm/open_questions/` — none of these are this plan's; they belong to plans 04-01, 04-02 and
other concurrent wave-3/4 work sharing this tree. `uv run alembic heads` reports `0005 (head)`, matching
what plan 04-01 shipped; this plan created no revision.

## The gate, observed (targeted subset — see note below)

```
uv run ruff check src/ tests/ alembic/
All checks passed!
```

```
uv run pytest tests/architecture/ tests/integration/test_same_transaction_events_have_a_stable_order.py \
              tests/security/test_history_seq_cannot_be_supplied.py -q
134 passed, 1 warning in 36.79s
```

The warning is the pre-existing `testcontainers` RabbitMQ deprecation notice, unrelated to this plan.

**The whole-suite `uv run pytest -q` was deliberately NOT run by this executor**, per the plan's own
acceptance criterion: plan 04-04 is `wave: 3` alongside this plan, and two concurrent full suite runs on
one Windows Docker host is more containers than the host reliably tolerates. Gate reported as `not_run`
below for that reason — this plan's own targeted subset (134 tests across the three new files plus the
whole `tests/architecture/` package) is green, and the orchestrator's wave-gate run covers the rest.

## Ledger entries owed

### deferred-items.md

- No new deviation is owed an OQ. The one structural deviation (two test functions instead of one) is a
  spelling/structuring difference with an identical asserted guarantee — recorded above, no OQ under
  ORCHESTRATION §5.
- **Confirms, does not add**: T-04-23 (assignment order is not commit order, accepted and handed to
  Phase 5) is exactly the threat row this plan's `<threat_model>` already names; nothing new to log.

### ORCHESTRATION-DECISIONS.md

No new one-way or costly decision was made on the user's behalf in this plan. The `OVERRIDING SYSTEM
VALUE` boundary itself was already adopted in plan 04-01 (D-53's OQ, owed and unallocated) — this plan
only proves the boundary plan 04-01 recorded; it makes no new adoption.

### WINDOWS.md (broken windows)

- No new broken window is opened by this plan.
