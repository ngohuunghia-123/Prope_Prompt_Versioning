---
phase: 05-the-three-functions-five-modules-build-against
plan: 03
subsystem: backend
tags: [property-history, ph-03, int-006, int-007, a-119, a-124, oq-033, d-76, d-77]

requires:
  - phase: 05-the-three-functions-five-modules-build-against
    plan: 01
    provides: "append(session, event) -> str; the registry cache; PromptScope"
  - phase: 05-the-three-functions-five-modules-build-against
    plan: 02
    provides: "read()'s tenant guard, counting_statements, tests/property_history's shared factories"
provides:
  - "tests/integration/test_activity_spans_four_modules_in_one_query.py — property-history.lock.yml's AC-3 test_ref, proving PH-03 / ROADMAP SC1"
affects: [05-04, 06-property-history-atomicity]

actuals:
  tokens: 34000
  tasks: 1
  commits: 0

tech-stack:
  added: []
  patterns:
    - "A lifecycle written as a module-level (action, target_type, target_id) tuple list with the writing module named beside each row, so a four-module claim is legible in source and not only in prose"
    - "counting_statements entered AFTER workspace_transaction's own __aenter__, so the tenant set_config is excluded from the 'one statement' claim about the read itself"

key-files:
  created:
    - tests/integration/test_activity_spans_four_modules_in_one_query.py
  modified: []

key-decisions:
  - "D-76 adopted as written: registration mints TWO events (property_created + revision_created for revision 1), closing AC-3's arithmetic at ten. This plan did not re-derive the reading — OQ-033 already recorded it during planning — it wrote the ten actions OQ-033 names and cited the id in the docstring."
  - "counting_statements(app_engine) is opened INSIDE the workspace_transaction block, after the session is already entered, not around the whole `async with workspace_transaction(...)` statement. workspace_transaction's own __aenter__ issues `SELECT set_config('app.workspace_id', ...)`, which is a real statement and would make every populated read count as two — not because read() issued two statements, but because the counter was watching the tenant handshake too. The plan's text did not spell out where to open the context manager; this is the one placement under which 'the read issues exactly one statement' is actually a claim about read()."
  - "COMMENT-DENSITY OVERRIDE (ORCHESTRATION §12) applied to the docstring. The plan's <action> block describes three things the module docstring must carry (the AC-3 arithmetic + OQ-033 citation, the submission-order reading, and why append() and not raw SQL) — these are substantive content the must_haves and the plan's own text require, not decorative per-column commentary, so they are written in full but kept to one short paragraph each. Everything else in the file follows the pointer rule: decoy comments are one line each naming the failure the decoy would prove, LIFECYCLE's writing-module names are inline trailing comments, and no per-field commentary was added to _draft or the assertions."

patterns-established:
  - "A statement counter is entered after the tenant handshake, not around it, whenever the claim under test is about the read and not about opening the session."

requirements-completed: [PH-03]

coverage:
  - id: D1
    description: "Ten append() calls for one prompt come back from one read(session, PromptScope(...)) call, named individually and in order, not counted"
    verification:
      - kind: test
        ref: "tests/integration/test_activity_spans_four_modules_in_one_query.py::test_a_prompts_whole_lifecycle_comes_back_from_one_read"
        status: pass
    human_judgment: false
  - id: D2
    description: "The returned actions are the exact reverse of LIFECYCLE_ACTIONS, and the returned ids are the exact reverse of what append() returned"
    verification:
      - kind: test
        ref: "same test, lines asserting `[event.action for event in events] == list(reversed(LIFECYCLE_ACTIONS))` and the id equivalent"
        status: pass
    human_judgment: false
  - id: D3
    description: "The ten events span exactly four target_types: property, revision, eval_suite, prompt_grant"
    verification:
      - kind: test
        ref: "same test, `{event.target_type for event in events} == {...}`"
        status: pass
    human_judgment: false
  - id: D4
    description: "revision_released carries all three registered detail keys and is accepted"
    verification:
      - kind: test
        ref: "same test, `dict(released.details) == RELEASE_DETAILS`"
        status: pass
    human_judgment: false
  - id: D5
    description: "Four decoys — another prompt same workspace, same prompt id in WORKSPACE_B, a null-scope workspace_created, and a null-scope revision_created about this prompt's own revision — are each proven present via migrate_engine before being proven absent from the read"
    verification:
      - kind: test
        ref: "same test, the migrate_engine vacuity-guard loop, then the decoy-absence loop"
        status: pass
    human_judgment: false
  - id: D6
    description: "The lifecycle read issues exactly one statement, and READ_BY_PROMPT names history.history_event exactly once and contains no JOIN"
    verification:
      - kind: test
        ref: "same test, `len(statements) == 1`, `\"JOIN\" not in READ_BY_PROMPT.text.upper()`, `READ_BY_PROMPT.text.count(...) == 1`"
        status: pass
    human_judgment: false
  - id: D7
    description: "read() on the decoy prompt's own scope returns exactly its one event, proving the filter is a filter and not a fixed answer"
    verification:
      - kind: test
        ref: "same test, final block reading PromptScope(WORKSPACE_A, OTHER_PROMPT_ID)"
        status: pass
    human_judgment: false
  - id: D8
    description: "The gate is green for the targeted file and ruff is clean repo-wide"
    verification:
      - kind: command
        ref: "uv run pytest tests/integration/test_activity_spans_four_modules_in_one_query.py -q -> 1 passed"
        status: pass
      - kind: command
        ref: "uv run ruff check src/ tests/ alembic/ -> All checks passed!"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-08-11
status: complete
---

# Phase 05 Plan 03: The ten-event lifecycle, the four decoys, and the one query — Summary

**One file, exactly as the plan sized it.** Ten `append()` calls for one prompt — spanning
`property_created`, three `revision_created`s, `revision_submitted`, `revision_approved`,
`revision_released` (with all three of its registered detail keys), `eval_suite_updated`,
`access_granted`, `revision_restored` — come back from one `read(session, PromptScope(...))` call in
the exact reverse of write order, with four decoys (another prompt, the same prompt id in a different
workspace, a null-scope `workspace_created`, and a null-scope `revision_created` naming this prompt's
own revision) each proven present through `migrate_engine` and then proven absent from the result. The
read issues exactly one statement.

## The ten events, as actually written

| # | action | target_type | target | writing module (per OQ-033 / D-76) |
|---|---|---|---|---|
| 1 | `property_created` | `property` | the prompt | prompt-registry |
| 2 | `revision_created` | `revision` | revision 1 (the tenth event, D-76) | prompt-registry |
| 3 | `revision_created` | `revision` | revision 2 | prompt-registry |
| 4 | `revision_created` | `revision` | revision 3 | prompt-registry |
| 5 | `revision_submitted` | `revision` | revision 3 | release-control |
| 6 | `revision_approved` | `revision` | revision 3 | release-control |
| 7 | `revision_released` | `revision` | revision 3, `{version_id, previous_version_id, break_glass}` | release-control |
| 8 | `eval_suite_updated` | `eval_suite` | the suite | evaluation |
| 9 | `access_granted` | `prompt_grant` | the grant | access-control |
| 10 | `revision_restored` | `revision` | revision 2 | release-control |

All ten action names were accepted by `fk_history_event_action` on the first run — the registered
`(action, target_type)` pairs in `alembic/versions/0005_history_schema_and_vocabulary.py`'s seed match
this table exactly, including `revision_released`'s three-key allow-list. **Nothing in the seeded
registry disagreed with the ten names this plan chose.**

## Which decoys were written, and how each was proven present before being proven absent

Four, all written through `append()` on real transactions, never by raw SQL:

1. `property_created` for `OTHER_PROMPT_ID`, same workspace (`WORKSPACE_A`), same transaction as
   decoys 3 and 4.
2. `property_created` for **the same `PROMPT_ID`**, written inside `workspace_transaction(...,
   WORKSPACE_B)` — its own tenant transaction, proving `prope_app` really can write this row when it
   holds `WORKSPACE_B`'s context.
3. `workspace_created`, `target_type=workspace`, `scope_prompt_id=None`.
4. `revision_created` targeting revision 2 of `PROMPT_ID` itself, `scope_prompt_id=None` — D-77's
   silent-failure decoy.

All four ids were read back through `migrate_engine` by id (`COUNT_BY_ID`) and found present — `landed
== 1` for each, with a failure message naming the decoy if the write had silently failed — **before**
any assertion that they are absent from `read()`'s result. A second vacuity guard reads
`PromptScope(WORKSPACE_A, OTHER_PROMPT_ID)` at the end and asserts it returns exactly decoy 1, proving
the read is a filter and not a fixed answer.

## The exact statement count, and the one placement decision this plan made

**Exactly one statement.** `counting_statements(app_engine)` is opened *inside* the
`workspace_transaction(...)` block — after the session's own `__aenter__` has already issued
`SELECT set_config('app.workspace_id', ...)` — rather than around the whole context-manager
statement. The first attempt wrapped the outer `async with`, which counted the tenant `set_config` as
a second statement and failed `len(statements) == 1` (`2 == 1`). This is a mechanical placement the
plan's `<action>` text did not spell out; the fix is the one placement under which "the read issues
exactly one statement" is a claim about `read()` and not about the session handshake. No behavioural
surprise: `read()` itself was never in question, and the fix touches no source file.

`READ_BY_PROMPT.text` was also asserted to contain no `JOIN` and to name `history.history_event`
exactly once.

## OQ-033: read, cited, not rewritten

`docs/brainstorm/open_questions/OQ-033.md` was read and its adopted reading (D-76) is quoted in the
test's module docstring by id. The file itself was not touched — `git status --porcelain docs/` shows
no change to it from this plan.

## Comment-density override applied

ORCHESTRATION §12 overrides the plan's comment instructions. The module docstring keeps the three
things the plan's `<action>` block requires (the AC-3 arithmetic + `OQ-033` citation, the
submission-order reading, and why `append()` and not raw SQL) but each is one short paragraph, not the
"deliverable" prose the plan file's own body describes at length. Everywhere else: each decoy carries
one line naming the failure its presence would prove, `LIFECYCLE`'s writing-module names are inline
trailing comments, and no per-field commentary exists on `_draft`, `RELEASE_DETAILS`, or any assertion.
Measured: the file is 182 lines with roughly a fifth comments/docstring, under §12's budget.

## Verification

```
uv run pytest tests/integration/test_activity_spans_four_modules_in_one_query.py -q  -> 1 passed
uv run ruff check src/ tests/ alembic/                                                -> All checks passed!
grep -c "revision_break_glass_released\|user_tombstoned\|api_key_created" \
     tests/integration/test_activity_spans_four_modules_in_one_query.py               -> 0
git status --porcelain docs/ .planning/ROADMAP.md alembic/ pyproject.toml uv.lock     -> no output from this plan
                                                                                          (pre-existing
                                                                                          modifications to
                                                                                          src/ and
                                                                                          ROADMAP.md from
                                                                                          other in-flight
                                                                                          work were present
                                                                                          before this plan
                                                                                          started and were
                                                                                          not touched)
```

Only the file this plan's `files_modified` names was written. The full suite was **not** run — this
plan ran only its own named test file, per the run's instruction that a wave gate runs the full suite
separately. Gate is reported `not_run` for the whole-suite sense; the targeted test and the lint gate
are both green.

## Ledger entries owed

### deferred-items.md

- No new item. This plan consumed no OQ allocation (`OQ-033` was pre-existing, read only) and left no
  gap of its own — `append()`, `read()`, `PromptScope`, and the registry all shipped in 05-01/05-02.

### ORCHESTRATION-DECISIONS.md

- No one-way or costly decision was made on the user's behalf in this plan. The one design choice
  recorded above (where to open `counting_statements`) is a test-mechanism placement with no source
  change and no data consequence — not a reportable adoption under §6.

### WINDOWS.md (broken windows)

- No new window opened. This plan added no new source module; the pre-existing prose-density windows
  on `append.py`, `domain.py`, and `registry.py` (recorded by 05-01/05-02) are unchanged — this plan
  did not open any of those three files.
