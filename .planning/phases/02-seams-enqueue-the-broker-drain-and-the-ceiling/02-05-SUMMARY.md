---
phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
plan: 05
subsystem: api
tags: [fastapi, pydantic, asgi, uvicorn, routing, pagination, decimal, rls, security, health-checks]

# Dependency graph
requires:
  - phase: 01-data-model-pricing-and-retention
    provides: "ledger.price_table and its ck_price_row_not_both_zero / uq collision constraints, ledger.spend_ceiling, set_retention_window/read_retention_window, workspace_transaction, build_engine/build_sessionmaker, Settings, and the WR-06 no-interpolation source gate this plan had to satisfy"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 01
    provides: "prope.observability — configure_logging and the counters; the refused HTTP-client dependency that sent this plan's tests to a hand-built ASGI caller"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 02
    provides: "writer.UNPRICED_WORKLIST — served unchanged by GET /api/v1/prices/unpriced; declare_topology, build_connection, publisher_channel and run_publisher — the four the lifespan composes"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 04
    provides: "check_spend_ceiling — the seam the PUT /spend-ceiling round-trip test drives, which is what turns a data contract into an assertion"
provides:
  - "prope.app:app — D-13's explicit central composition, the ASGI application Makefile run has targeted since Phase 1"
  - "GET /healthz and GET /readyz — INT-030, with readiness the database alone (D-16) in its final form"
  - "prope.call_ledger.api — INT-028's five management routes on four paths"
  - "prope.call_ledger.schemas — the one A-045 error envelope, install_error_envelope, and the Money serializer that puts ten fixed places on the wire"
  - "prope.session_auth — require_session (fail-closed until Phase 7), ManagementRefusal, Session, the closed ManagementAction vocabulary, and assembled_routes/declared_action/declares_session, the route-table readers Phase 23's AC-10 extends"
  - "tests/integration/_asgi.py — a dependency-free ASGI caller that runs the app on the test's own event loop"
  - "docs/brainstorm/open_questions/OQ-021.md — who owns the shared session dependency's file"
affects: [03-fallback-and-upsert, 07-identity-and-sessions, 17-gateway, 22-release-control, 23-architecture-tests]

actuals:
  tokens: 41000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "An interim boundary that is DECLARED and refuses, rather than omitted — the Phase 7 replacement changes one function body and no route"
    - "A closed action vocabulary as a StrEnum whose membership is checked at import time, so an unregistered action is a startup error"
    - "Assertions over the ASSEMBLED route table rather than over the source, with an explicit expansion step because app.routes is not the table"
    - "One plain-literal SQL statement with self-disabling CAST(:p AS text) IS NULL filters, serving two reads without composition"
    - "A supersession range derived at read time by a window function, so no write ever touches an existing row"
    - "A test transport built from the ASGI spec rather than a package, because the app and the database must share one event loop"

key-files:
  created:
    - src/prope/app.py
    - src/prope/call_ledger/api.py
    - src/prope/call_ledger/schemas.py
    - src/prope/session_auth.py
    - tests/integration/_asgi.py
    - tests/integration/test_management_routes.py
    - tests/integration/test_health_and_readiness.py
    - tests/architecture/test_route_table.py
    - docs/brainstorm/open_questions/OQ-021.md
  modified: []

key-decisions:
  - "CR-01 is disposed of as option (a) — POST /api/v1/prices refuses a (0,0) row as a blocking pre-condition. Phase 1's human-verification item 1 was still `awaiting: user response` at both planning and execution time, so this is the verifier's recommended option adopted UNCONFIRMED and re-raised as this plan's first human-check"
  - "require_session ships fail-closed: with no session store in existence every /api/v1 route answers 401 session_required in the one envelope. An undeclared boundary is the failure mode; a route that defaults to unauthenticated because Phase 7 has not happened is the one thing worse than a route nobody can call yet"
  - "docs_url, redoc_url and openapi_url are all None. INT-028's spec is generated from the code by the tests, not served — and three unauthenticated routes would also make the assembled table ten paths where seven are asserted"
  - "A failed broker connect at startup is logged and survived rather than raised. A lifespan that raised would defeat D-16 by refusing to come up at all, which is a harder failure than the un-readiness D-16 already refuses"
  - "The price supersession range is DERIVED by lead(effective_from) at read time rather than stored and closed by an UPDATE. A-102/T-006 say a price is superseded by a new row; a stored effective_to would need exactly the UPDATE the prohibition forbids"
  - "SpendCeilingSet.enabled carries no default. A ceiling that arms itself because a field was omitted is a spend control set by accident"
  - "The workspace in the path is compared against the session's workspace and mismatch is not_found, never forbidden — the fourth non-negotiable's refusal shape, held one phase before RLS has a session to derive the workspace from"
  - "422 validation details carry field locations and messages only. pydantic's `input` echoes the offending value, which on POST /api/v1/prices is a price and on any future route could be worse"

patterns-established:
  - "The one error envelope: {error: {code, message, details?, request_id}} with `code` a machine StrEnum the client renders (ADR-0053) and `message` never a driver's words"
  - "Money crosses the wire as a fixed-point STRING with all ten places, via a PlainSerializer on an annotated Decimal — JSON floats cannot carry numeric(20,10)"
  - "Constraint-name recovery walks error.orig AND error.orig.__cause__, because SQLAlchemy's asyncpg dialect wraps its own IntegrityError around the real asyncpg exception"
  - "A route-table architecture test enumerates paths against a literal frozenset, so an EXTRA route fails as loudly as a missing one"

requirements-completed: [CL-06]

coverage:
  - id: D1
    description: "The assembled route table holds exactly seven paths — INT-028's five /api/v1 routes on four paths plus INT-030's /healthz and /readyz — all served from prope.app:app, which imports and includes the router by name with no discovery"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/architecture/test_route_table.py#test_the_assembled_table_is_exactly_the_seven_paths"
        status: pass
      - kind: integration
        ref: "tests/architecture/test_route_table.py#test_the_application_is_composed_by_hand_and_not_discovered"
        status: pass
      - kind: integration
        ref: "tests/architecture/test_route_table.py#test_the_assembled_table_holds_no_route_this_phase_did_not_declare"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every /api/v1 route declares the session dependency and one action from a closed vocabulary, asserted over the assembled table; each action is declared exactly once and an action outside the vocabulary is a startup error"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/architecture/test_route_table.py#test_every_versioned_route_declares_a_session_and_an_action"
        status: pass
      - kind: integration
        ref: "tests/architecture/test_route_table.py#test_every_registered_action_is_declared_exactly_once"
        status: pass
      - kind: unit
        ref: "tests/architecture/test_route_table.py#test_declares_action_refuses_an_action_outside_the_vocabulary"
        status: pass
    human_judgment: false
  - id: D3
    description: "With no session store in existence every /api/v1 route refuses with 401 in the one error envelope, and the refusal quotes no part of the cookie"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_every_route_refuses_without_a_session"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_the_refusal_quotes_no_part_of_the_session_cookie"
        status: pass
    human_judgment: true
    rationale: "The assertion proves the boundary refuses; it cannot prove fail-closed is the INTENDED interim posture for a phase in which the five routes therefore cannot be exercised by hand. Plan human-check 2."
  - id: D4
    description: "POST /api/v1/prices appends and never updates or deletes; a superseding row leaves the earlier row byte-identical; a colliding effective range is 422 in the envelope with details and no constraint name"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_a_superseding_row_leaves_the_earlier_row_byte_identical"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_a_colliding_row_is_refused_with_details_and_no_constraint_name"
        status: pass
      - kind: unit
        ref: "tests/integration/test_management_routes.py#test_the_router_issues_no_update_and_no_delete_against_the_price_table"
        status: pass
    human_judgment: false
  - id: D5
    description: "POST /api/v1/prices refuses a (0,0) price row — CR-01's disposition (a) — while one zero price beside a non-zero one is accepted"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_a_free_tier_price_row_is_refused_and_nothing_is_inserted"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_one_zero_price_beside_a_non_zero_one_is_accepted"
        status: pass
    human_judgment: true
    rationale: "The BEHAVIOUR is proven; the DISPOSITION is not. Phase 1 human-verification item 1 was still `awaiting: user response`, so option (a) was adopted unconfirmed. Plan human-check 1 — confirm (a), or say whether (b) re-open Phase 1 or (c) accept with a recorded override applies."
  - id: D6
    description: "GET /api/v1/prices returns superseded rows with derived effective ranges, cursor-paginated at a default of 50 and a maximum of 200, with money as a ten-place string"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_superseded_rows_are_returned_with_their_derived_ranges"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_the_page_defaults_to_fifty_and_pages_with_a_cursor"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_a_limit_above_the_maximum_is_refused_rather_than_clamped"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_money_crosses_the_wire_as_a_string_with_all_ten_places"
        status: pass
    human_judgment: false
  - id: D7
    description: "A monthly ceiling set through PUT /spend-ceiling is the ceiling check_spend_ceiling then reads; clearing it allows again with the recorded spend byte-identical; a disabled row and no row both allow and are told apart"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_a_ceiling_set_below_recorded_spend_makes_the_seam_refuse"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_clearing_the_limit_allows_again_and_leaves_the_spend_untouched"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_a_disabled_row_and_no_row_both_allow_and_are_told_apart"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_enabled_has_no_default_so_a_ceiling_cannot_be_set_unarmed"
        status: pass
    human_judgment: false
  - id: D8
    description: "PUT /workspaces/{id}/retention persists a window the drain actually reads, refuses a non-positive one, and a workspace the session cannot see is not-found rather than forbidden"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_a_window_written_by_the_route_is_the_one_the_drain_reads"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_a_non_positive_window_is_refused_and_stores_nothing"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_a_workspace_the_session_cannot_see_is_not_found_never_forbidden"
        status: pass
    human_judgment: false
  - id: D9
    description: "/healthz answers 200 with the database unreachable and with no engine on app.state at all; /readyz is the database alone — 503 naming the failed check and quoting no credential, 200 with the broker unreachable, and the app starts with no broker"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_health_and_readiness.py#test_healthz_answers_200_with_no_engine_at_all"
        status: pass
      - kind: integration
        ref: "tests/integration/test_health_and_readiness.py#test_readyz_answers_503_naming_the_database_when_it_is_unreachable"
        status: pass
      - kind: integration
        ref: "tests/integration/test_health_and_readiness.py#test_readyz_answers_200_with_the_broker_unreachable"
        status: pass
    human_judgment: false
  - id: D10
    description: "No route, response model, parameter or generated schema exposes a stored request or response body — ADR-0018/AC-10, the module has no body read path in the MVP"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/architecture/test_route_table.py#test_no_schema_property_or_parameter_exposes_a_stored_body"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py#test_the_unpriced_worklist_carries_counts_and_no_figure"
        status: pass
    human_judgment: false

# Metrics
duration: 34min
completed: 2026-08-10
status: complete
---

# Phase 02 Plan 05: Management Routes and the First ASGI Application Summary

**`prope.app:app` now exists and assembles exactly seven paths — INT-028's five management routes on four paths behind a declared, fail-closed session boundary, plus INT-030's `/healthz` and `/readyz` with readiness the database alone — all served through one hand-written composition with no discovery anywhere in it.**

## Performance

- **Duration:** 34 min
- **Started:** 2026-08-10T09:56:53Z
- **Completed:** 2026-08-10T10:31:32Z
- **Tasks:** 3
- **Files created:** 9 (0 modified)
- **Tests:** 236 → 292 (+56); `uv run ruff check src/ tests/ alembic/` clean

## Accomplishments

- **The project has an application.** `Makefile run` has targeted `prope.app:app` since Phase 1 with a comment saying the module arrives in phase 2. It starts working now. The composition is D-13's explicit kind: one router imported by name and included, no `importlib`, no `pkgutil`, no module-list iteration, no `register()` hook — and that absence is asserted structurally rather than left as a habit.
- **Five management routes on four paths**, counted the way the plan insisted: `POST|GET /api/v1/prices` is one bullet line and two paths, so five route objects across four distinct paths, plus two health paths, for seven in the assembled table. The architecture test compares against a literal frozenset, so an extra route fails as loudly as a missing one.
- **The session boundary is declared, not deferred.** `require_session` exists, every `/api/v1` route depends on it, and until Phase 7 gives it a session store it raises `401 session_required` in the one envelope. Phase 7 replaces a function body and touches no route.
- **A closed action vocabulary** (`ManagementAction`, five `call_ledger.`-prefixed machine codes) attached to each route through a dependency, checked at import time, and asserted declared-exactly-once over the assembled table. INT-001's closure becomes a startup error rather than a review comment.
- **The ceiling round trip is proven end to end**, not asserted twice from two sides: the test drives `PUT /spend-ceiling` and then calls Phase 04's real `check_spend_ceiling`, which is what converts a data contract (`api.py` writes columns the seam reads; it never imports it, because call-ledger is a sink) into a single failing test if either side drifts.
- **`/readyz` reached its final form** and the Phase 2 consequence is written at the route rather than discovered later: the broker being down is degraded-and-counted, never un-readiness, so there is a window where readiness is green and records are dropped-and-counted. CL-01 closes it.
- **OQ-021 raised rather than absorbed** — the shared session dependency had to live somewhere and no module's lock file claims the file.

## Task Commits

1. **Task 1: the error envelope, the session boundary, the action vocabulary** — `381b317` (feat)
2. **Task 2: INT-028's five management routes** — `6fbbb79` (feat)
3. **Task 3: `prope.app`, the health routes, and the assembled route table** — `913b6ba` (feat)

## Files Created

- `src/prope/session_auth.py` — `require_session` (fail-closed), `Session`, `ManagementRefusal`, `SESSION_REQUIRED`, the `ManagementAction` vocabulary and `declares_action`, plus `assembled_routes` / `declared_action` / `declares_session`: the route-table readers, sited here so Phase 23's AC-10 extends a test rather than writing one.
- `src/prope/call_ledger/schemas.py` — the wire types, the `ErrorCode` StrEnum, `ErrorEnvelope`, `install_error_envelope`, and the `Money` annotation that serializes a `Decimal` as a fixed-point string with all ten places.
- `src/prope/call_ledger/api.py` — the `APIRouter`, the four SQL statements, `path_workspace` (the not-found refusal shape), `_constraint_name`, and the five handlers.
- `src/prope/app.py` — `create_app`, the lifespan (engine, sessionmaker, bounded broker bring-up, `declare_topology` from the same definition `worker` uses, background publisher), `/healthz`, `/readyz`, and `app`.
- `tests/integration/_asgi.py` — an ASGI caller built from the spec: scope, receive, send, awaited on the test's own loop.
- `tests/integration/test_management_routes.py` — 26 tests (several parametrized) over the five routes.
- `tests/integration/test_health_and_readiness.py` — 6 tests, two of which run the real lifespan.
- `tests/architecture/test_route_table.py` — 15 tests over the assembled table, the composition, and the generated schema.
- `docs/brainstorm/open_questions/OQ-021.md` — who owns the shared session dependency's file.

## Decisions Made

Recorded in full in `key-decisions` above. The four that will be argued with:

**CR-01 is disposed of as option (a).** `POST /api/v1/prices` refuses a row whose input and output prices are both zero, because such a row makes every call it prices refuse at write time (`ck_call_record_cost_is_never_zero`). Phase 1's human-verification item 1 was still `awaiting: user response` at planning time and **still was at execution time** — this is the verifier's recommended option adopted unconfirmed, and it is re-raised as a human-check below rather than quietly settled by having been built.

**Fail-closed is the interim posture.** Every `/api/v1` route answers 401 until Phase 7. The consequence is honest and worth stating: the five routes cannot be exercised by hand this phase, and the SPA has nothing to call yet. The alternative — open-with-a-warning — makes the boundary a comment.

**A failed broker connect is logged and survived.** The bring-up is bounded by a timeout; on failure the exit stack unwinds, `state.broker` and `state.publisher` are `None`, and startup continues. A lifespan that raised would make a broker outage prevent the process from coming up at all, which is a strictly harder failure than the un-readiness D-16 already refuses. Asserted by running the real lifespan against a closed port.

**The supersession range is derived, not stored.** `lead(effective_from) OVER (PARTITION BY workspace_id, provider_config_id, upstream_model ORDER BY effective_from)` computes `effective_to` at read time. A stored `effective_to` would need an `UPDATE` to close the previous row — exactly the statement the plan's third prohibition forbids, and exactly what makes a recorded cost stop being explicable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `app.routes` is not the assembled route table in FastAPI 0.141**

- **Found during:** Task 3 (the route-table test)
- **Issue:** `include_router` in FastAPI 0.141.1 appends a single lazy `_IncludedRouter` entry to `app.routes` rather than flattening the router's routes into it. A naive walk over `app.routes` finds the two health routes and **zero** `/api/v1` routes — so every "every versioned route declares a session and an action" assertion would have passed **vacuously over an empty set**. This is the worst possible failure of an architecture test: green, and proving nothing.
- **Fix:** `assembled_routes(application)` in `session_auth.py` expands `effective_route_contexts()` where present and otherwise takes routes carrying a `dependant`. The vacuity risk is written into its docstring, and `test_every_versioned_route_declares_a_session_and_an_action` asserts the counts (5 route objects, 4 distinct paths) before it asserts anything about them.
- **Files:** `src/prope/session_auth.py`, `tests/architecture/test_route_table.py`
- **Committed in:** `913b6ba`

**2. [Rule 3 - Blocking] The price-row SQL tripped Phase 1's WR-06 no-interpolation gate**

- **Found during:** Task 2
- **Issue:** The paged read and the single-row read shared a ranged sub-select composed into two `text()` calls by f-string. `tests/architecture/test_no_sql_interpolation.py` correctly flagged the `JoinedStr` at `api.py:160`. That gate explicitly discourages adding `ALLOWED` entries.
- **Fix:** Collapsed all three statements into **one** plain-literal `PRICE_ROWS` serving both reads, with two self-disabling filters (`CAST(:price_row_id AS text) IS NULL OR ...`). The right answer to a no-interpolation gate is a statement that needs no composition, not an exemption.
- **Files:** `src/prope/call_ledger/api.py`, `tests/integration/test_management_routes.py`
- **Committed in:** `913b6ba`

**3. [Rule 1 - Bug] Constraint-name recovery read only one link of the exception chain**

- **Found during:** Task 2 (four tests returning 500 where 422 was expected)
- **Issue:** `_constraint_name` read `error.orig.constraint_name`. SQLAlchemy's asyncpg dialect wraps its own `AsyncAdapt_asyncpg_dbapi.IntegrityError` as `error.orig` and chains the real `asyncpg.exceptions.UniqueViolationError` / `CheckViolationError` as `error.orig.__cause__`, so the name was never found and both refusals fell through to the 500 handler.
- **Fix:** Walk `error.orig` and `error.orig.__cause__`. Probed against a live Postgres container rather than guessed; the finding is written into the function's docstring because the next person will hit it too.
- **Files:** `src/prope/call_ledger/api.py`
- **Committed in:** `6fbbb79`

**4. [Rule 1 - Bug] The append-only source gate matched its own prose**

- **Found during:** Task 2
- **Issue:** A raw AST string scan for `UPDATE`/`DELETE` near `ledger.price_table` matched **docstrings** explaining why neither statement exists — a test that fails on its own explanation.
- **Fix:** Inspect the compiled `TextClause` module attributes, plus an AST assertion that no `text()` call sits inside a function (so no statement can be built at call time and escape the module-attribute scan).
- **Files:** `tests/integration/test_management_routes.py`
- **Committed in:** `6fbbb79`

### Declared, not auto-fixed

**5. No HTTP client was installed.** The tests needed a transport. `httpx` is not a dependency, and adding one is excluded from auto-fix — plan 02-01 had already refused an HTTP-client dependency. There is also a technical reason the easy path was wrong: `TestClient` runs the app on another event loop in a worker thread, which conflicts with asyncpg connections bound to the test's loop. `tests/integration/_asgi.py` (127 lines, no dependencies) builds the scope and awaits the app directly.

---

**Total deviations:** 4 auto-fixed (2 × Rule 3 blocking, 2 × Rule 1 bug), 1 declared refusal.
**Impact on plan:** No scope creep. Deviations 1 and 4 are the notable ones — both were tests that would have passed while proving nothing, which is the failure mode an architecture suite exists to avoid.

## Issues Encountered

- **`Path(alias="id")` and `Annotated[PageRequest, Query()]`** were verified against FastAPI 0.141.1 with a throwaway probe before the router was written, rather than assumed from an older version's behaviour.
- **A live end-to-end check** was run under uvicorn with both the database and the broker pointed at closed ports: `healthz=200`, `readyz=503 {"status":"not_ready","failed_check":"database"}`, `docs=404`, and the log line `{"reason": "AMQPConnectionError", "event": "app.broker_unavailable"}` followed by `{"event": "app.started"}` — the broker is not a startup dependency, in the running process and not only in a test.
- **`ruff format --check`** still fails repo-wide (~38 pre-existing files; `ruff.toml` sets `line-length = 120` against a repo hand-wrapped to ~100). Known-failing and deferred from Phase 1; not touched here. `uv run ruff check` is clean.

## Human Checks

Both are the plan's own `<human-check>` items, carried forward unanswered:

1. **CR-01 disposition.** Phase 1 human-verification item 1 was still `awaiting: user response`. This plan built option (a) — a blocking pre-condition on `POST /api/v1/prices` refusing a `(0,0)` row. Confirm (a) is the disposition, or say whether (b) re-open Phase 1 or (c) accept with a recorded override applies instead. If the answer is not (a), the change is one refusal branch in `create_price_row` and two tests.
2. **The interim session boundary.** Every `/api/v1` route refuses with 401 until Phase 7 replaces `require_session`'s implementation, so the five routes cannot be exercised by hand this phase. Confirm fail-closed is the intended interim posture rather than an open-with-a-warning one.

## Open Questions Raised

- **OQ-021 — which module owns the shared session dependency's file?** `require_session` is consumed by call-ledger now and by every management surface later; access-control builds the real one in Phase 7 but must not be imported by its consumers' modules under the forbidden-edge rule. The file is sited at `src/prope/session_auth.py`, outside every module's package, and the OQ recommends naming it in access-control's lock file. A different answer costs an import-path rewrite at five sites and one architecture test — and no behaviour.

## User Setup Required

None.

## Next Phase Readiness

**Ready.** `prope.app:app` is the composition point every later module's router will be included into, and the route-table test is the gate that makes an unregistered route fail. `session_auth.require_session` is the seam Phase 7 fills; `ManagementAction` is the vocabulary later modules extend.

**Carried into Phase 3:** the one-phase readiness gap is real and now written down at the route — with the broker down, readiness is green and `enqueue()` fills its bounded handoff and then counts-and-drops. `prope_call_ledger_metadata_dropped_total` measures it; CL-01's inline fallback closes it. `tests/integration/test_health_and_readiness.py::test_readyz_answers_200_with_the_broker_unreachable` documents the gap in its docstring — if that test ever has to change, D-16 changed.

**Concern for Phase 7:** the five management routes have never been exercised with a real session, only with `dependency_overrides`. The override is applied at the `require_session` object, so the wiring is proven; the session store's behaviour is not, and cannot be until it exists.

## Self-Check: PASSED

All 9 created source/doc files and the SUMMARY exist on disk; all 4 commits (`381b317`, `6fbbb79`, `913b6ba`, `1555244`) resolve in the log.

---
*Phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling*
*Completed: 2026-08-10*
