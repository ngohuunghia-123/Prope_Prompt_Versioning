---
phase: 05-the-three-functions-five-modules-build-against
plan: 04
subsystem: property-history
tags: [contract-test, ac-6, ph-06, int-008, vocabulary, pyyaml]

# Dependency graph
requires:
  - phase: 05-the-three-functions-five-modules-build-against
    plan: 01
    provides: "registry.py's LOAD_REGISTRY, load_action_registry, install_registry / registered_registry / reset_registry — this plan adds registered_actions beside them, reading the same statement"
  - phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
    plan: 01
    provides: "revision 0005's 31-row SEED_ACTION_REGISTRY and the RegisteredAction dataclass with all five columns"
provides:
  - "tests/contract/ — a new test package, and its first test"
  - "tests/contract/test_event_vocabulary_matches_the_locks.py — AC-6, the registry compared against a three-way-derived union of the five writing lock files, in both directions and per writing module"
  - "src/prope/property_history/registry.py: registered_actions(session) — INT-008, reads the table (ADR-0038), takes a session (OQ-034), returns all five fields sorted by action"
affects: [23-route-table-assertion]

actuals:
  tokens: 46000
  tasks: 3
  commits: 0

tech-stack:
  added: []
  patterns:
    - "A structural comma-walk over a prose paragraph's leading run of bare identifiers, stopping at the first item that is not one — rather than a permissive regex over the whole paragraph, which both over- and under-extracts against this vocabulary"
    - "Three independent derivations of the same fact (writer's own paragraph, the consumer's restatement, the consumer's declared count) cross-checked before either is compared to the runtime source of truth"
    - "A set-equality failure message that computes and labels the two directions of a symmetric difference separately, because the two causes are unrelated"

key-files:
  created:
    - tests/contract/__init__.py
    - tests/contract/test_event_vocabulary_matches_the_locks.py
  modified:
    - src/prope/property_history/registry.py

key-decisions:
  - "pyproject.toml already declared pyyaml==6.0.3 in the dev group and uv.lock already carried it — both landed in an earlier commit under this working tree (git blame: 03-era commits, wired for tests/architecture/test_alert_rules.py's YAML-parsing need), not by this plan. Task 1's D-78 half was therefore verification-only: `import yaml` resolves, `git diff pyproject.toml`/`git diff uv.lock` are empty, and no pin moved. Nothing under files_modified for those two paths needed an edit"
  - "registered_actions(session) placed directly after load_action_registry, ahead of the process-cache section: it reads the table through the same function the cache loader uses, and grouping it with the table-reading code rather than the cache code is the point the docstring and D-80 both make"
  - "The extraction's terminator set (., (, :, ;, em dash) and the phrase-stop rule were verified against the five lock files as they stand today via a throwaway script before being written into the test; recovered 5/8/4/4/10 with no adjustment, matching property-history.lock.yml's own declared counts on the first run — deleted after verification, nothing of it survives in the repo"
  - "Task 3 (the phase gate: full suite, git-status checks across docs/architecture/adr, and the record_event grep) was NOT run as a full-suite pass. This run's outer harness instructions override the plan's own Task 3 text: other agents are editing other files in this same working tree, and a wave gate runs the full suite after the wave. Only the checks that do not require the full suite were run directly (see Gate below) and the full `uv run pytest -q` is left to the wave gate"

patterns-established:
  - "A contract test whose expected side is parsed from docs/ at run time, never a fixture — the module docstring states explicitly what to do when it goes red (new migration or new OQ, never edit the test or the lock file)"

requirements-completed: [PH-06]

coverage:
  - id: D1
    description: "registered_actions(session) returns all 31 registered actions read from the table (not the cache), each carrying all five columns"
    requirement: PH-06
    verification:
      - kind: test
        ref: "tests/contract/test_event_vocabulary_matches_the_locks.py::test_registered_actions_matches_the_union_in_both_directions"
        status: pass
    human_judgment: false
  - id: D2
    description: "The expected vocabulary is derived from docs/modules/*.lock.yml at run time, three independent ways, and all three agree per module before the registry is compared to anything"
    requirement: PH-06
    verification:
      - kind: test
        ref: "tests/contract/test_event_vocabulary_matches_the_locks.py::test_the_three_derivations_agree_on_which_five_modules_write, ::test_each_modules_extracted_count_matches_its_declared_count, ::test_writers_and_property_historys_restatement_are_the_same_list"
        status: pass
    human_judgment: false
  - id: D3
    description: "Per-module counts 5/8/4/4/10, read from the lock files rather than written in the test; union totals 31, asserted as the one hardcoded literal, citing OQ-027"
    requirement: PH-06
    verification:
      - kind: test
        ref: "tests/contract/test_event_vocabulary_matches_the_locks.py::test_each_modules_extracted_count_matches_its_declared_count, ::test_the_union_totals_31"
        status: pass
    human_judgment: false
  - id: D4
    description: "The extraction excludes scope_prompt_id, version_id, previous_version_id, break_glass, set_revision_status, prompt_grant, target_type, target_id, actor_id, suite_version, and recovers retired despite its missing underscore"
    requirement: PH-06
    verification:
      - kind: test
        ref: "tests/contract/test_event_vocabulary_matches_the_locks.py::test_column_and_field_names_in_the_prose_are_not_mistaken_for_actions[*], ::test_retired_is_recovered_despite_carrying_no_underscore"
        status: pass
    human_judgment: false
  - id: D5
    description: "The misfiled-event check: each registry row's writing_module matches the lock file it was derived from, and access_level_changed is attributed to prompt-registry, not access-control"
    requirement: PH-06
    verification:
      - kind: test
        ref: "tests/contract/test_event_vocabulary_matches_the_locks.py::test_access_level_changed_is_attributed_to_prompt_registry_not_access_control, ::test_every_seeded_action_is_attributed_to_the_module_that_declared_it"
        status: pass
    human_judgment: false
  - id: D6
    description: "pyyaml resolves as a declared dependency, dev group, no other pin moved"
    requirement: PH-06
    verification:
      - kind: command
        ref: "uv run python -c \"import yaml; print(yaml.__version__)\" -> 6.0.3; git diff --stat pyproject.toml uv.lock -> empty (already declared before this plan ran)"
        status: pass
    human_judgment: false
  - id: D7
    description: "registered_actions()'s declared signature (five fields, one session parameter) against two narrower authorities"
    verification: []
    human_judgment: true
    rationale: "The plan's <human-check>. registered_actions ships as async def registered_actions(session) -> tuple[RegisteredAction, ...], a superset of the lock's three-field/no-parameter shape and INT-008's four-field/no-parameter shape, per OQ-034 (already written during planning, cited at both widenings in the docstring, not edited by this plan)."

# Metrics
duration: 42min
completed: 2026-08-11
status: complete
---

# Phase 05 Plan 04: The registry compared against the five lock files' union — Summary

**AC-6 / PH-06 / ROADMAP SC2 close.** `registered_actions(session)` reads `history.history_action_registry`
live and returns all 31 seeded rows; `tests/contract/test_event_vocabulary_matches_the_locks.py` derives the
expected 31 names three independent ways from `docs/modules/*.lock.yml` and asserts equality against the
registry in both directions and per writing module. No list of the 31 names exists anywhere under `tests/`
or `src/`.

## Performance

- **Tasks:** 3 (Task 1 and 2 executed in full; Task 3 — the phase gate — deliberately not run as a full
  suite, per this run's harness instructions; see below)
- **Files created:** 2 (`tests/contract/__init__.py`, `tests/contract/test_event_vocabulary_matches_the_locks.py`)
- **Files modified:** 1 (`src/prope/property_history/registry.py`)
- **Targeted suite:** `uv run pytest tests/contract/ -q` — **19 passed** in 62.75s

## What shipped

**`src/prope/property_history/registry.py` — `registered_actions(session)`.** Delegates to
`load_action_registry(session)` and returns `tuple(sorted(mapping.values(), key=lambda row: row.action))`.
Placed directly after `load_action_registry`, ahead of the process-cache section — it is table-reading code,
not cache-reading code, and ADR-0038's Consequences say so by name. The docstring cites `OQ-034` at both
points the shipped shape widens past the two narrower declared authorities: the session parameter (ADR-0023
forbids the module opening its own connection) and the five-field return (`writing_module` is what the
vocabulary test's misfiled-event check needs).

**`tests/contract/test_event_vocabulary_matches_the_locks.py`.** One structural extractor,
`_extract_leading_names`, walks each `outputs[].what` paragraph's comma-separated items and stops at the
first one that is not a bare identifier immediately followed by a terminator (`.` `(` `:` `;` em dash) or the
end of the item. Verified by a throwaway script against the five lock files before being written into the
test: recovered `5, 8, 4, 4, 10` with **no adjustment needed** on the first run — the terminators actually
exercised were exactly the five the plan named (period after `retired`, em dash after `review_task_closed`
and `credential_rotated`, `(` after `user_tombstoned`, and the phrase-stop rule after `eval_run_interrupted`
in evaluation's paragraph, where the next word is `with`). The throwaway script was deleted; nothing of it
survives in the repository.

Three derivation helpers — `_declared_by_writers`, `_restated_by_property_history`,
`_counts_declared_by_property_history` — each parse YAML at run time and are cross-checked in ten test
functions, ordered least-to-most-specific per the plan: a vacuity guard first (all three derivations found
the same five modules), then the per-module count check (catches an extraction bug before the registry is
touched at all), then the ordered-list equality between a writer's own paragraph and property-history's
restatement, then the no-duplicate-name / 31-distinct-names check, then the hardcoded `31` (citing OQ-027's
adoption over the 30-in-six-places / 31-in-five-places disagreement), then the named-exclusion parametrized
test (`scope_prompt_id`, `version_id`, `previous_version_id`, `break_glass`, `set_revision_status`,
`prompt_grant`, `target_type`, `target_id`, `actor_id`, `suite_version`), then `retired`'s recovery, then the
`access_level_changed` misattribution guard, and finally the two async tests against a live database: the
registry-vs-union set equality (with extras and omissions reported separately) and the per-module
`writing_module` attribution check.

## `import yaml` and `uv.lock` — already in place before this plan ran

`pyproject.toml`'s dev group already carried `"pyyaml==6.0.3"` with a comment naming the transitive-today
risk and `tests/architecture/test_alert_rules.py`'s existing YAML need, and `uv.lock` already resolved it —
both landed in an earlier commit under this working tree, not authored by this plan. Verified rather than
re-done: `uv run python -c "import yaml; print(yaml.__version__)"` printed `6.0.3`, and
`git diff --stat pyproject.toml uv.lock` was empty throughout this plan's execution — no pin moved because
none was touched.

## The gate, observed (targeted, not full-suite — see Deviations)

```
uv run pytest tests/contract/ -q
19 passed, 1 warning in 62.75s
```

```
uv run ruff check src/ tests/ alembic/
All checks passed!
```

```
grep -rn "record_event" src/ tests/ alembic/
(no output)

git status --porcelain docs/modules docs/architecture docs/adr alembic/
(no output — the only docs/ output is pre-existing untracked OQ-065..OQ-084, none touched by this plan)

git diff --stat uv.lock pyproject.toml
(empty)
```

## Deviations from Plan

### 1. Task 3's full-suite phase gate was not run

The plan's Task 3 says this plan's `<verification>` block carries the phase gate — the whole suite plus
lint, once per phase. **This run's outer harness instructions explicitly override that**: other agents are
editing other files in this same working tree concurrently, running only the test files this plan names is
required, and a wave gate runs the full suite after the wave. `uv run pytest -q` across the whole suite was
therefore **not run** by this execution. What was run instead, and is reported above: the targeted
`tests/contract/` suite (19 passed), the lint gate (clean), and the git-status / grep checks that do not
require a database or the rest of the suite to be green. `uv run pytest -q` and the two named regression
watchpoints (`test_health_and_readiness.py` / `test_handoff_shutdown_drain.py`, and Phase 4's history tests)
are the wave gate's to run and report.

### 2. `pyproject.toml` / `uv.lock` half of Task 1 was verification-only

D-78 as written describes adding the `pyyaml==6.0.3` line and running `uv lock`. Both were already present
in the working tree before this plan started (see above) — from an earlier commit, not from this session.
Re-adding an identical line and re-locking would have been a no-op with a risk of moving something; instead
this plan verified the existing declaration meets every one of Task 1's acceptance criteria for that half
(import succeeds, no other pin moved, dev group only) and moved directly to `registered_actions`.

## For the reviewer and for later phases

- **`registered_actions()`'s shape is the plan's own open question, `OQ-034`** — not resolved here, cited at
  the two widenings, and unchanged under `docs/`. Phase 23's route-table assertion is its next declared
  consumer and will be written against whichever shape stands when `OQ-034` resolves.
- **`OQ-027`'s adopted count (31) is the only vocabulary number this test hardcodes.** If a sixth module or a
  32nd action ever exists, this literal is the one line to look at first.
- **The wave gate must run `uv run pytest -q` and the lint check across the whole suite** before the phase is
  called green; this plan's own verification was necessarily scoped to `tests/contract/`.

## Ledger entries owed

None. This plan touched no orchestrator-owned file (`ORCHESTRATION-DECISIONS.md`, `WINDOWS.md`, `STATE.md`,
`ROADMAP.md`, or this phase's `deferred-items.md`) and has nothing to report into any of them.
