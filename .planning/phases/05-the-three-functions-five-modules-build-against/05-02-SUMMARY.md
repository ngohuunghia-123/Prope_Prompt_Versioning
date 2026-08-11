---
phase: 05-the-three-functions-five-modules-build-against
plan: 02
subsystem: backend
tags: [property-history, int-007, sc3, adr-0024, adr-0035, adr-0045, a-045, a-119, a-125, pagination, explain, rls]

# Dependency graph
requires:
  - phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
    plan: 01
    provides: "revision 0005 — history.history_event, the four indexes (three of which this plan reads on), the tenant policy and the grant matrix"
  - phase: 05-the-three-functions-five-modules-build-against
    plan: 01
    provides: "read(session, PromptScope, *, limit) with READ_BY_PROMPT and its before_seq parameter already in the statement; PromptScope with KIND; HistoryEvent; DEFAULT_LIMIT / MAX_LIMIT; tests/property_history's factories; the conftest registry fixture"
provides:
  - "src/prope/property_history/read.py — INT-007 complete: three scopes dispatched with `match`, keyset pagination on an opaque event id, the limit guard, and the two read refusals"
  - "TargetScope, ActorScope and the `Scope` union in domain.py, each carrying the KIND value Phase 6's scope_kind label reads"
  - "HistoryCursorUnknown and HistoryScopeMismatch — neither a RejectionReason member, neither a ValueError"
  - "tests/property_history.seed_history_events (bulk corpus seeder through the owner) and counting_statements (a statement recorder plan 05-03 also uses)"
  - "tests/architecture/test_property_history_depends_on_nothing.py — `dependencies: []` as an ast import walk that runs on every suite run"
  - "tests/integration/test_history_read_is_ordered_by_seq_not_time.py — the inverted-clock case and the two-concurrent-transaction case Phase 4 handed forward"
  - "tests/integration/test_history_read_uses_its_declared_indexes.py — EXPLAIN (FORMAT JSON) against the planner for all three scopes"
  - "tests/security/test_history_read_refuses_a_foreign_workspace.py — the cross-workspace and no-tenant refusals, each with its positive control"
affects: [05-03, 05-04, 06-property-history-atomicity, 13-registry, 22-release-control]

actuals:
  tokens: 84000
  tasks: 4
  commits: 0

tech-stack:
  added: []
  patterns:
    - "A union of frozen scope dataclasses dispatched with `match`, where the `case _` arm is a TypeError naming the object rather than a silently-chosen branch"
    - "A cursor that is an opaque identifier resolved to a sort position in its own workspace-scoped statement, so an unresolvable one is a named refusal instead of an empty page"
    - "Diagnosis on the empty path only — a returned row is itself the proof that the tenant matched, so the populated read pays nothing for a guard the empty read needs"
    - "EXPLAIN (FORMAT JSON) walked for the index NAME anywhere in the plan tree, never for a node type, plus a no-predicate control that must name no index"
    - "A statement counter as a `before_cursor_execute` listener on engine.sync_engine, registered and removed inside a context manager, yielding the statements rather than a count"
    - "An ast import walk with a closed allow-list, whose teeth are proven by pointing the same helper at a synthetic module written into tmp_path"

key-files:
  created:
    - tests/integration/test_history_read_scopes_and_pagination.py
    - tests/integration/test_history_read_is_ordered_by_seq_not_time.py
    - tests/integration/test_history_read_uses_its_declared_indexes.py
    - tests/security/test_history_read_refuses_a_foreign_workspace.py
    - tests/architecture/test_property_history_depends_on_nothing.py
  modified:
    - src/prope/property_history/read.py
    - src/prope/property_history/domain.py
    - tests/property_history/__init__.py

key-decisions:
  - "D-72 adopted UNCONFIRMED as Option B with the diagnosis on the EMPTY PATH ONLY. A returned row proves the tenant matched — the policy would not have let it through — so a populated cursorless read is one statement and only an empty one pays for `SELECT current_setting('app.workspace_id', true)`. Asserted, not described: test_a_populated_read_issues_one_statement_and_an_empty_one_issues_two counts both and inspects the second statement's text, so 'the diagnosis is on the empty path' cannot quietly stop being true"
  - "The tenant guard treats NULL and the empty string identically as *no tenant context*. tests/security/test_tenant_isolation.py already proves both routes exist — NULL on a pristine backend, '' on a reused one — so a guard checking only for NULL would pass a reused connection straight through, which is the more common shape in a pooled process"
  - "D-71 executed: the cursor is the opaque hev_ event id, resolved by its own statement scoped to the caller's workspace. The workspace_id term in RESOLVE_CURSOR is what makes a cursor non-portable across tenants, and it is asserted as a refusal with a positive control rather than as an empty page"
  - "A cursor naming an event in this workspace under a DIFFERENT scope is accepted, deliberately. The cursor is a position in seq, not a claim about the scope, and the page statement re-applies the scope — so a replayed cursor can only move the window inside data the caller could already read (T-05-16, accepted)"
  - "D-73 executed as three module-level statements, not one statement with three self-switching-off predicates. PRICE_ROWS' shape earns its place where two reads differ only in a predicate; here they differ in WHICH INDEX they are written for, and the access path is the thing being specified"
  - "The limit guard raises ValueError and does NOT collide with D-63's no-ValueError rule. That rule is about the append path, where five modules call from inside code that validates its own request bodies and an `except ValueError` would swallow the audit log's refusal. A read has no such hazard, and HistoryEventDraft already raises ValueError from __post_init__ for this class of caller mistake"
  - "The concurrency test takes its seq control on each transaction's OWN session rather than through migrate_engine as the plan wrote it. It cannot be otherwise: event A is uncommitted when the control has to be taken, so no other connection can see its row. The assertion is unchanged — the FIRST-written event must hold the LOWER seq, with a failure message saying the test proves nothing if it does not"
  - "The EXPLAIN vacuity control runs through migrate_engine rather than the app session. As the owner there is no policy predicate, so the no-WHERE plan is unambiguously a sequential scan; on the app session the RLS predicate leaves the planner a choice and the control would be asserting the planner's mood"
  - "ANALYZE is kept although a probe showed all three EXPLAIN tests pass without it at 3,000 rows. Without ANALYZE the plan depends on whether autovacuum has visited yet, which is a race this file should not be running"
  - "OQ-036 was NOT written. All three read scopes matched the index Phase 4 shipped for them, so there is no index-versus-read-shape conflict to raise. The id is released back to the orchestrator rather than consumed — an OQ written to use up an allocation is worse than an unused id"
  - "COMMENT-DENSITY OVERRIDE applied (ORCHESTRATION §12). The plan's mandated per-class and per-statement essays were written as pointers: each scope class gets two or three lines naming its INT-007 shape and its index, each statement gets a short `#:` naming the index, and the four arguments <verification> asks to see at the code are one- or two-line `# WHY:` notes rather than paragraphs"

patterns-established:
  - "Pay for a diagnosis only on the path where the answer is ambiguous, and assert the statement count so the placement is a property rather than a habit"
  - "Prove an index is USED, not that it exists — EXPLAIN with real parameters, matched on the index name anywhere in the plan, with a control that must find none"
  - "Give an architecture walk teeth by running the same helper over a synthetic violating module written in the test"
  - "Take a concurrency control inside the transaction that owns the uncommitted row, and make the control's failure message say the test proves nothing without it"

requirements-completed: []

coverage:
  - id: D1
    description: "read() accepts all three of INT-007's scope shapes and dispatches each to its own statement; a scope of no declared shape is a TypeError"
    verification:
      - kind: test
        ref: "tests/integration/test_history_read_scopes_and_pagination.py::test_each_scope_returns_its_own_events_and_not_the_others"
        status: pass
      - kind: test
        ref: "tests/integration/test_history_read_scopes_and_pagination.py::test_a_scope_object_of_no_declared_shape_is_a_type_error"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each of the three statements orders by seq DESC, and occurred_at appears in no ORDER BY clause anywhere under src/prope/property_history/"
    verification:
      - kind: command
        ref: "grep -n 'ORDER' src/prope/property_history/read.py -> three hits, all `ORDER  BY seq DESC`"
        status: pass
      - kind: test
        ref: "tests/integration/test_history_read_is_ordered_by_seq_not_time.py::test_the_clock_does_not_decide_the_order"
        status: pass
    human_judgment: false
  - id: D3
    description: "read() takes no actor, permission or subject, and src/prope/property_history/ imports no prope module outside {prope.db, prope.property_history}"
    verification:
      - kind: test
        ref: "tests/architecture/test_property_history_depends_on_nothing.py::test_no_module_imports_a_prope_package_outside_the_allow_list (7 modules)"
        status: pass
      - kind: test
        ref: "tests/architecture/test_property_history_depends_on_nothing.py::test_the_walk_refuses_a_module_that_reaches_another_bounded_context"
        status: pass
      - kind: test
        ref: "tests/integration/test_history_read_is_ordered_by_seq_not_time.py::test_read_asserts_nothing_about_an_actor"
        status: pass
    human_judgment: false
  - id: D4
    description: "fastapi is imported at no depth under the package, and src/prope/observability.py is not imported either"
    verification:
      - kind: test
        ref: "tests/architecture/test_property_history_depends_on_nothing.py::test_fastapi_is_imported_at_no_depth (7 modules)"
        status: pass
      - kind: test
        ref: "tests/architecture/test_property_history_depends_on_nothing.py::test_the_shared_observability_module_is_not_imported"
        status: pass
    human_judgment: false
  - id: D5
    description: "A cursor is an opaque hev_ event id; one naming an event that does not exist in this workspace raises HistoryCursorUnknown rather than returning an empty page"
    verification:
      - kind: test
        ref: "tests/integration/test_history_read_scopes_and_pagination.py::test_a_cursor_naming_no_event_is_refused"
        status: pass
      - kind: test
        ref: "tests/integration/test_history_read_scopes_and_pagination.py::test_a_cursor_from_another_workspace_is_refused"
        status: pass
    human_judgment: false
  - id: D6
    description: "A scope whose workspace_id disagrees with the session tenant raises HistoryScopeMismatch, and a session with no tenant at all raises it too — each with a positive control"
    verification:
      - kind: test
        ref: "tests/security/test_history_read_refuses_a_foreign_workspace.py::test_a_scope_naming_another_workspace_is_refused"
        status: pass
      - kind: test
        ref: "tests/security/test_history_read_refuses_a_foreign_workspace.py::test_a_session_with_no_tenant_is_refused"
        status: pass
      - kind: test
        ref: "tests/security/test_history_read_refuses_a_foreign_workspace.py::test_a_genuinely_empty_scope_returns_empty"
        status: pass
    human_judgment: false
  - id: D7
    description: "limit 0, -1 and 201 each raise ValueError naming the value and A-045's bound; 200 is accepted"
    verification:
      - kind: test
        ref: "tests/integration/test_history_read_scopes_and_pagination.py::test_a_limit_outside_a_045s_bound_is_refused[0|-1|201]"
        status: pass
      - kind: test
        ref: "tests/integration/test_history_read_scopes_and_pagination.py::test_the_largest_legal_limit_is_accepted"
        status: pass
    human_judgment: false
  - id: D8
    description: "A cursorless read that returns rows issues exactly ONE statement; an empty one issues two, the second being the tenant diagnosis"
    verification:
      - kind: test
        ref: "tests/security/test_history_read_refuses_a_foreign_workspace.py::test_a_populated_read_issues_one_statement_and_an_empty_one_issues_two"
        status: pass
    human_judgment: false
  - id: D9
    description: "Each of the three scope statements uses the index it was written for, proven with EXPLAIN over 3,000 rows plus ANALYZE, with a no-predicate control that names none"
    verification:
      - kind: test
        ref: "tests/integration/test_history_read_uses_its_declared_indexes.py::test_the_prompt_scope_is_read_on_its_own_index"
        status: pass
      - kind: test
        ref: "tests/integration/test_history_read_uses_its_declared_indexes.py::test_the_target_scope_is_read_on_its_own_index"
        status: pass
      - kind: test
        ref: "tests/integration/test_history_read_uses_its_declared_indexes.py::test_the_actor_scope_is_read_on_its_own_index"
        status: pass
      - kind: test
        ref: "tests/integration/test_history_read_uses_its_declared_indexes.py::test_a_statement_with_no_predicate_names_no_index"
        status: pass
    human_judgment: false
  - id: D10
    description: "Two events in two CONCURRENT transactions, the higher seq committing first, are both returned across two descending pages — the lower seq is not skipped"
    verification:
      - kind: test
        ref: "tests/integration/test_history_read_is_ordered_by_seq_not_time.py::test_a_late_committing_lower_seq_is_not_skipped"
        status: pass
    human_judgment: false
  - id: D11
    description: "Paging with limit=1 visits every event exactly once in strictly decreasing seq, and the page after the last returns empty with no error"
    verification:
      - kind: test
        ref: "tests/integration/test_history_read_scopes_and_pagination.py::test_paging_with_limit_one_visits_every_event_exactly_once"
        status: pass
      - kind: test
        ref: "tests/integration/test_history_read_scopes_and_pagination.py::test_a_cursorless_page_is_the_newest_events_and_the_next_page_follows_it"
        status: pass
    human_judgment: false
  - id: D12
    description: "The whole suite is green and no spec file, migration, dependency or index moved"
    verification:
      - kind: command
        ref: "uv run pytest -q -> 570 passed, 1 skipped in 322.82s"
        status: pass
      - kind: command
        ref: "git status --porcelain docs/modules docs/architecture docs/adr alembic/ pyproject.toml uv.lock -> no output"
        status: pass
    human_judgment: false
  - id: D13
    description: "Task 2's adopted-UNCONFIRMED refusal, and MAX_LIMIT = 200 as a product-visible cap on an audit screen"
    verification: []
    human_judgment: true
    rationale: "The plan's two <human-check> items. Both are built and asserted; what is owed is a ruling, not work."

# Metrics
duration: 70min
completed: 2026-08-11
status: complete
---

# Phase 05 Plan 02: `read()` reaches INT-007's whole surface — Summary

**All three of INT-007's declared scope shapes now exist as types a caller cannot half-fill, each read
on the index Phase 4 shipped for it, with a cursor that is a position rather than a number, and with the
two ways a caller can be wrong about the tenant turned from empty screens into named refusals.** ROADMAP
SC3 holds in all three clauses: `seq` is the sort key against a clock that runs backwards *and* against
two transactions committing out of assignment order, and *no permission check* is proven by there being
nothing in the package to check with — on a walk that runs every time the suite does.

Gate: `uv run ruff check src/ tests/ alembic/` clean; `uv run pytest -q` → **570 passed, 1 skipped** in
5:22 (the skip is the `load`-marked test, which skips by default). 05-01 left the suite at 530 passed;
this plan adds 40.

## The exact signature, and every refusal it can raise

```python
async def read(
    session: AsyncSession,
    scope: Scope,                       # PromptScope | TargetScope | ActorScope
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,         # 50; MAX_LIMIT is 200
) -> tuple[HistoryEvent, ...]
```

`cursor` and `limit` are keyword-only. The lock spells the parameters `read(scope, cursor, limit)`, and
both `read(session, scope, 50, None)` and `read(session, scope, None, 50)` look plausible while one of
them is silently wrong.

Four refusals, in the order the function can reach them:

| Raised | When | Why not an empty tuple |
|---|---|---|
| `ValueError` | `limit` outside `1..200` | A page of zero renders an empty Activity from a caller bug; a page above the cap turns a 50,000-event workspace into one response. Refused with a sentence naming the value and A-045's bound, never clamped |
| `TypeError` | `scope` is not one of the three classes | `Scope` is a closed union. A `dict` or a half-built scope meets a name instead of a full-workspace scan |
| `HistoryCursorUnknown` | the cursor resolves to no event **in this workspace** | An empty page reads as *the trail ended here* on the one table whose product claim is that it does not. Also the containment: a cursor is not portable across tenants |
| `HistoryScopeMismatch` | the scope's `workspace_id` disagrees with the session's `app.workspace_id`, **or** the session carries none | See below |

`HistoryCursorUnknown` and `HistoryScopeMismatch` are ordinary `Exception` subclasses. Neither is a
`RejectionReason` member — that enum is the closed label set of
`prope_property_history_append_rejected_total`, whose alert pages on **every** increment, and a read
refusal is not an append refusal. Neither subclasses `ValueError`, for the reason `HistoryAppendRejected`
records one file over.

## Task 2's adopted-UNCONFIRMED decision, and what a human is being asked to rule on

**Option B is adopted: a scope naming a workspace the session is not in raises `HistoryScopeMismatch`,
and so does a session with no tenant context at all. `adopted: UNCONFIRMED`.**

The refinement is the whole of the adoption and it is what makes it affordable: **the diagnosis runs on
the empty path only.** A returned row proves the tenant matched — the policy would not have let it
through otherwise — so a populated cursorless read costs exactly one statement and pays nothing. Only an
empty read runs `SELECT current_setting('app.workspace_id', true)` and decides between three answers:
absent → refuse, naming `workspace_transaction`; different → refuse, naming both ids; the same → return
`()`, which now means what it says.

That is asserted rather than described.
`test_a_populated_read_issues_one_statement_and_an_empty_one_issues_two` counts the statements through
a `before_cursor_execute` listener and inspects the second one's text, so a later edit that hoists the
guard to the top of the function goes red.

**The consequence to rule on:** prompt-registry's Activity route now has one more failure mode to
translate into an HTTP status, and a caller who supplies the wrong `workspace_id` meets a 5xx rather
than an empty list. The alternative is the state Option A leaves: a caller who forgot
`workspace_transaction` sees an audit log with nothing in it, forever, which the lock's own
`failure_modes` rate as the only failure here that is *silent in the direction that matters*. Reversal
is one function and one exception class, no data consequence.

**The second `<human-check>`: `MAX_LIMIT = 200`** is A-045's number and it is now a product-visible cap
on an audit screen. `limit=201` is a `ValueError`, not a clamp. Confirm it or name the number that
replaces it for this read.

## The corpus that actually tipped the planner

The plan's starting point was *~3,000 rows over ~60 prompts, ~60 targets and ~30 actors, plus
`ANALYZE`*. **That configuration worked on the first run and was not raised.** Concretely: 3,000 rows
seeded in one `executemany` through the owner, `scope_prompt_id` cycling over 60 values, `target_id`
over 60 and `actor_id` over 30, then `ANALYZE history.history_event`. All three `EXPLAIN (FORMAT JSON)`
plans name the index the statement was written for.

I then probed whether `ANALYZE` was load-bearing: with the `ANALYZE` removed, **all three tests still
passed**. It is kept anyway, and the reason is written at the code — without it the plan depends on
whether autovacuum has visited yet, which is a race a test asserting a plan shape should not be running.
`enable_seqscan = off` was never used and the file says why: it would prove the index *can* be used
rather than that it *is*.

The vacuity control runs the no-`WHERE` statement through `migrate_engine` rather than the app session.
As the owner there is no policy predicate, so the plan is unambiguously a sequential scan; on the app
session the RLS predicate leaves the planner a real choice and the control would be asserting its mood
rather than the walker's honesty.

## OQ-036: released, not written

Task 3 allocated `OQ-036` **conditionally** — only if the EXPLAIN work found that one of Phase 4's four
indexes is not the one a declared read shape needs. It did not. All three read scopes matched:

| Scope | Index |
|---|---|
| `PromptScope` | `ix_history_event_workspace_id_scope_prompt_id_seq` |
| `TargetScope` | `ix_history_event_workspace_id_target_type_target_id_seq` |
| `ActorScope` | `ix_history_event_workspace_id_actor_id_seq` |

The fourth index, `(workspace_id, action, seq)` **ascending**, backs A-126's hand-run Success SQL and
matches no `read()` scope — which is what Phase 4 declared it for, so it is not a conflict. **No file was
written to `docs/brainstorm/open_questions/`.** The id is owed back to the orchestrator; see *Ledger
entries owed*.

## Where this plan departed from the plan text, and why

Two mechanisms differ. Both are named rather than absorbed:

1. **The concurrency control is taken on each transaction's own session, not through `migrate_engine`.**
   The plan says *"read the two rows through `migrate_engine` by id and assert `seq(A) < seq(B)`"* before
   anything else. That is not possible: event A is deliberately **uncommitted** at that moment, so no
   other connection can see its row. The control is taken inside T1 (which sees its own uncommitted row)
   and inside T2, before T2 commits. The assertion and its failure message are exactly what the plan
   asked for — *the FIRST-written event must hold the LOWER seq, and the test proves nothing if it does
   not.* Behavioural end state identical; no OQ owed.

2. **The EXPLAIN vacuity control runs as the owner**, for the reason above. Same reasoning.

One test in `test_each_scope_returns_its_own_events_and_not_the_others` is stronger than the plan's
sketch: the third seeded event shares its `actor_id` and `target_id` with the first but differs in
`target_type` and `scope_prompt_id`, so `TargetScope` must separate it out *and* `ActorScope` must keep
it. A corpus where every event either matched all three scopes or none would not have caught a statement
that dropped the `target_type` predicate.

## The comment-density override, applied

ORCHESTRATION §12 overrode this plan's comment instructions and I took it, as 05-01 did. Specifically
**not** written: the multi-sentence docstrings the plan mandates at each new scope class (two or three
lines each, naming the INT-007 shape, the index and — for `ActorScope` — why it exists with no consumer
screen); the four-point `#:` blocks at each statement (one short block each, naming the index); and the
paragraph-length arguments at the cursor and the tenant guard.

The four things `<verification>` asks to see argued **at the code** are present as one- or two-line
notes: why the diagnosis runs on the empty path (at the `if rows:` return), why the cursor is an id and
not a `seq` (at `RESOLVE_CURSOR`), why the cursor gets its own statement (same block, `# WHY` form), and
why descending is the safe direction across concurrent commits (the module docstring, which now names
the test file that proves it rather than a plan number).

Nothing that records a decision was lost — the full arguments are in `05-02-PLAN.md` verbatim, and every
refused alternative is restated in `key-decisions` above.

Measured after writing: `read.py` is 228 lines, 44 comment lines and 32 docstring lines — **33%**, at
§12's budget and unchanged in posture from what 05-01 left. `domain.py`
grew by the two scope classes and the two exceptions; its prose share is essentially unchanged and its
pre-existing overage is still the phase 4 remediation agent's, per §12's known-backlog table.

## Verification

```
uv run ruff check src/ tests/ alembic/                          -> All checks passed!
uv run pytest -q                                                -> 570 passed, 1 skipped in 322.82s
git status --porcelain docs/modules docs/architecture docs/adr alembic/ pyproject.toml uv.lock
                                                                -> no output
```

Targeted runs, each green before the full suite:
`tests/security/test_history_read_refuses_a_foreign_workspace.py` (4),
`tests/integration/test_history_read_scopes_and_pagination.py` (11),
`tests/integration/test_history_read_uses_its_declared_indexes.py` (5),
`tests/integration/test_history_read_is_ordered_by_seq_not_time.py` (3),
`tests/architecture/` (151, of which 17 are the new import-walk file).

**Nothing was written outside `files_modified`.** The only declared path not written is
`docs/brainstorm/open_questions/OQ-036.md`, deliberately, per Task 3's condition. Files that show as
modified in `git status` and are **not** this plan's footprint — `src/prope/app.py`,
`src/prope/property_history/{__init__,append,registry}.py`, `src/prope/worker.py`,
`src/prope/call_ledger/enqueue.py`, `tests/conftest.py` and six other test modules — carried uncommitted
work from plan 05-01 and Phase 3 CR-03 before this plan started.

## Deliberate gaps this plan leaves

- **No metric.** `prope_property_history_read_duration_seconds` and
  `prope_property_history_events_returned` are Phase 6's. The `scope_kind` label vocabulary is fixed here
  as `KIND` on each of the three scope classes — `prompt`, `target`, `actor` — so Phase 6 reads it rather
  than re-deriving it.
- **`ActorScope` has no consumer module.** It is built because the lock's `apis.exposes` declares it,
  because Phase 4 shipped its index, and because AC-9 (Phase 6) is unanswerable without it. That no
  module's `outputs` names a screen for it is an observation, not a conflict between authorities; it is
  owed to `deferred-items.md` below.
- **PH-03's ten-event lifecycle is plan 05-03's; AC-6 is plan 05-04's.** This plan owns no requirement
  id, deliberately.

## Ledger entries owed

### deferred-items.md

- **Phase 4 §5's *assignment order is not commit order* row is DISCHARGED.**
  `tests/integration/test_history_read_is_ordered_by_seq_not_time.py::test_a_late_committing_lower_seq_is_not_skipped`
  drives two genuinely concurrent transactions through an `AsyncExitStack`, with the higher `seq`
  committing first, and asserts the lower one lands on the next descending page rather than being
  skipped.
- **OQ-036 was ALLOCATED to this phase and LEFT UNCONSUMED.** No index-versus-read-shape conflict was
  found — all three read scopes matched the index Phase 4 shipped for them. The id is free to reassign.
- **05-01's forward-reference item is discharged.**
  `tests/architecture/test_property_history_depends_on_nothing.py` now exists and `read.py`'s module
  docstring names it, along with `tests/integration/test_history_read_is_ordered_by_seq_not_time.py`. If
  either file is renamed, the docstring must move with it.
- **`MAX_LIMIT` is no longer unused.** 05-01 recorded it as defined-and-unused pending this plan; the
  guard exists.
- **New:** `ActorScope` is a declared read shape with no consumer module. INT-007 names three consumers
  and none of them uses it; its declared in-repository consumer is AC-9 in Phase 6. Recorded rather than
  raised — an unowned read shape is not a conflict between authorities.
- **New:** `tests/property_history.counting_statements` is written here and plan 05-03 is expected to use
  it for its *"in one query"* assertion. It lives in the shared package precisely so there is one place
  the listener is registered and removed.
- **New (test-mechanism deviation, no OQ owed):** the concurrency test takes its `seq` control on each
  transaction's own session rather than through `migrate_engine` as 05-02-PLAN's Task 4 wrote it, because
  the row whose `seq` is being checked is deliberately uncommitted at that moment. Behavioural end state
  identical.

### ORCHESTRATION-DECISIONS.md

| Phase | Plan | Decision | Rejected alternative | Reversibility |
|---|---|---|---|---|
| 05 | 02 | **D-72 / Option B** — a scope whose `workspace_id` disagrees with the session's tenant, or a session carrying no tenant at all, raises `HistoryScopeMismatch`. The diagnosing statement runs **only on the empty path**, so a populated read still costs one statement; the placement is asserted by a statement count, not documented. | **Option A** — return an empty tuple and let RLS be the whole answer. Rejected because an empty Activity screen is indistinguishable from *nothing has happened*, which on a table that keeps every event forever (A-121) is the worst available lie; and because it leaves the lock's *"cannot construct a cross-workspace read even by supplying the wrong ids"* as a claim about rows returned rather than reads constructed. | **cheap** — one function, one exception class, no data consequence |
| 05 | 02 | **D-71** — the pagination cursor is the opaque `hev_` event **id**, resolved to a `seq` by its own workspace-scoped statement; an unresolvable one raises `HistoryCursorUnknown`. | **`str(seq)` as the cursor**: `seq` is one global identity sequence, so a decimal cursor rendered into an Activity URL from Phase 15 tells its holder roughly how many events the whole installation has written and how fast — a cross-tenant volume oracle on a table that never shrinks. Also rejected: **resolving the cursor as a scalar subquery inside the page statement**, where an unknown id makes the comparison NULL and returns zero rows *silently*. | **costly** — the cursor becomes a value in a rendered URL from Phase 15 on |
| 05 | 02 | **A-045's `MAX_LIMIT = 200` is refused with a sentence, never clamped**, and becomes a product-visible cap on an audit screen. | Clamping `limit=201` to 200: silently answers a different question than the one asked, which is the trade `PageRequest` already refuses one module over. | **cheap** |

### WINDOWS.md (broken windows)

- **No new window opened.** `tests/architecture/test_no_sql_interpolation.py`'s `ALLOWED` is still empty;
  all five `text()` calls in `read.py` take plain string constants. No index was added, no dependency
  moved, no migration was written.
- **Still open, unchanged by this plan:** the prose-density overage 05-01 recorded against
  `src/prope/property_history/{append,domain,registry}.py`. This plan edited `domain.py` and added to it
  under §12's budget; it did not trim the Phase 4 bulk, which §12's known-backlog table assigns to the
  phase 4 remediation agent.
