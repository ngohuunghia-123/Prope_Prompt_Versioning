---
phase: 03-durability-idempotency-and-no-read-path
plan: 05
subsystem: backend
tags: [security, no-read-path, ac-10, rls, privileges, postgres, ast, inspect, tenancy]

# Dependency graph
requires:
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 03
    provides: "prope.session_auth.assembled_routes — the walk that sees an included router's effective routes (Broken Window #4), and prope.app itself"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 05
    provides: "tests/architecture/test_route_table.py — FORBIDDEN_FIELD_NAMES, EXPECTED_ROUTES, and the OpenAPI walk this file states a dependency on rather than duplicating"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 02
    provides: "writer.UPSERT_CALL_BODY as a Core construct over models.call_body — one of the four body-table sites layer 3 enumerates"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 04
    provides: "worker.OLDEST_BODY_CREATED_AT — D-43's age gauge, the fourth body-table site and the only SELECT on ledger.call_body in src/; EXPECTED_ROUTES grown to eight"
provides:
  - "tests/security/test_no_body_read_path.py — AC-10's full claim at three layers, each with its own positive control"
  - "BODY_NAMING_EXEMPT_TYPES (4) and BODY_NAMING_EXEMPT_PARAMETERS (3) — entries with reasons and asserted sizes, proved necessary AND sufficient"
  - "BODY_TABLE_WRITERS (4) — every file in src/ that may name ledger.call_body, asserted in both directions"
  - "tests/security/test_report_role_can_read_bodies.py — the fourth reader, asserted deliberately; report_engine's first consumer"
  - "docs/brainstorm/open_questions/OQ-025.md clause 2 — prope_report's BYPASSRLS SELECT on ledger.call_body, with both readings and the class-level question"
affects: [03-VERIFICATION, 07-access-control, 23-cross-module-route-table]

actuals:
  tokens: 61000
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns:
    - "An absence proved by enumerating what is present, failing in BOTH directions — a declared file that stopped naming the table fails as loudly as an undeclared one that started"
    - "An exemption list proved necessary AND sufficient: the walk is re-run with every hatch closed and its output compared against a literal enumeration"
    - "A public-surface walk keyed on the DEFINITION site, so a re-export exempts the same type rather than opening a second hole"
    - "Annotation resolution asserted rather than assumed — an unresolvable return annotation is reported, because a walk comparing strings passes silently"
    - "A security exposure asserted by a test that PROVES it, with the disposition, the ADRs on both sides and the open question named in the docstring"

key-files:
  created:
    - tests/security/test_no_body_read_path.py
    - tests/security/test_report_role_can_read_bodies.py
  modified:
    - docs/brainstorm/open_questions/OQ-025.md
    - .planning/phases/03-durability-idempotency-and-no-read-path/deferred-items.md

key-decisions:
  - "BODY_TABLE_WRITERS ships with FOUR entries, not the plan's three. src/prope/worker.py's OLDEST_BODY_CREATED_AT (D-43, landed by plan 03-04 after this plan was written) is the fourth site and the only SELECT on ledger.call_body anywhere in src/. Declared with its reason and bounded by its own assertion — the statement must name min(created_at) and no body column"
  - "The internal walk judges a public name at its DEFINITION site and skips anything defined outside the prope package. A body-naming type re-exported into a second module is still the same type and stays exempt; pydantic.BaseModel, which every schema module imports, is a tool rather than part of this module's surface and asserting over it would make the test fail on somebody else's release"
  - "The return-annotation half carries NO exemption list at all. The exemptions are inputs; AC-10 is about outputs, and the half that matters cannot be satisfied by growing a list"
  - "Unresolvable return annotations are collected and asserted empty rather than skipped. No module in src/ uses `from __future__ import annotations` today; the walk says so the day one does instead of going quiet"
  - "Layer 1 asserts route paths, path-parameter names and request-body MODEL FIELDS — never the request-body parameter NAME, which is `payload` on three handlers and is a member of FORBIDDEN_FIELD_NAMES. A parameter named payload on a route handler is not the failure CL-10 is about"
  - "Task 3 adopted assert-and-record (UNCONFIRMED): prope_report keeps its SELECT on ledger.call_body, the exposure is asserted by a named test with a negative control, and the class-level question about grant_table's report_select default goes to OQ-025 clause 2"

patterns-established:
  - "An exemption set is verified in three ways at once: its size is written out, its members are each proved to name a body, and the walk with the hatch closed is compared against a literal enumeration — so growing it, shrinking it, and letting an entry go stale all fail"
  - "A test whose job is to prove an exposure names the disposition, the ADRs on both sides, the open question and the instruction for the day it goes red, in its own docstring"

requirements-completed: [CL-10]

coverage:
  - id: D1
    description: "No route path, path parameter or request-body model field in the assembled table names a stored body, asserted over the served route objects rather than over the generated spec, with the route count and the number of resolved body models both checked first"
    requirement: CL-10
    verification:
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_no_route_path_parameter_or_request_body_field_names_a_stored_body"
        status: pass
    human_judgment: false
  - id: D2
    description: "No public callable in prope.call_ledger takes a parameter in FORBIDDEN_FIELD_NAMES and no non-exempt public dataclass or pydantic model declares a field in it, across every module the package walk discovers"
    requirement: CL-10
    verification:
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_no_public_callable_or_model_in_the_module_names_a_body"
        status: pass
    human_judgment: false
  - id: D3
    description: "No public callable in the package returns a type whose fields name a body — the direction AC-10 is actually about, with no exemption list and with annotation resolution asserted"
    requirement: CL-10
    verification:
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_no_public_callable_returns_a_type_that_names_a_body"
        status: pass
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_the_read_side_types_name_no_body"
        status: pass
    human_judgment: false
  - id: D4
    description: "The two exemption lists are sized at four and three, every entry is proved to name a body, and no entry is stale — the walk with both hatches closed reports exactly eleven names"
    requirement: CL-10
    verification:
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_the_exemption_lists_are_exactly_what_names_a_body"
        status: pass
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_the_walk_would_have_found_one"
        status: pass
    human_judgment: false
  - id: D5
    description: "The internal walk is non-vacuous — the package walk finds at least ten modules, twenty public callables and fifteen public models, counted at their definition sites"
    requirement: CL-10
    verification:
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_the_internal_walk_inspected_the_package_it_claims_to_cover"
        status: pass
    human_judgment: false
  - id: D6
    description: "The set of files under src/ that name ledger.call_body in a SQL context is exactly the four declared writers, asserted in both directions, with a non-empty file list and a floor on matching sites"
    requirement: CL-10
    verification:
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_only_the_declared_writers_name_the_body_table"
        status: pass
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_the_body_table_walk_found_statements_to_check"
        status: pass
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_the_age_gauge_selects_no_body_column"
        status: pass
    human_judgment: false
  - id: D7
    description: "prope_app holds SELECT on ledger.call_body and the grant is load-bearing — a body written through the real write path is read back on the runtime credential inside a tenant transaction, with a migrate_engine read first as the positive control"
    requirement: CL-10
    verification:
      - kind: security
        ref: "tests/security/test_no_body_read_path.py::test_prope_app_can_read_a_body_and_that_is_the_point"
        status: pass
    human_judgment: false
  - id: D8
    description: "prope_report reads every stored body in every workspace with no tenant context set, prope_app in the same table reads exactly one, and the two facts behind the exposure — BYPASSRLS and the SELECT grant — are asserted separately"
    verification:
      - kind: security
        ref: "tests/security/test_report_role_can_read_bodies.py::test_the_reporting_credential_reads_every_body_in_every_workspace"
        status: pass
      - kind: security
        ref: "tests/security/test_report_role_can_read_bodies.py::test_the_runtime_credential_sees_only_its_own_tenant"
        status: pass
      - kind: security
        ref: "tests/security/test_report_role_can_read_bodies.py::test_the_two_facts_behind_the_exposure_are_still_true"
        status: pass
    human_judgment: false
  - id: D9
    description: "Whether a database role falls inside AC-10 at all, and whether grant_table's report_select default should be False for a table declared to have no reader"
    verification: []
    human_judgment: true
    rationale: "Task 3's checkpoint, adopted UNCONFIRMED as assert-and-record. The mechanical halves are asserted (D8) and the question is written out with both readings in OQ-025 clause 2, deferred-items.md Part 1 item 5, and this summary. The disposition itself is the developer's."

# Metrics
duration: 41min
completed: 2026-08-11
status: complete
---

# Phase 03 Plan 05: Durability, idempotency, and no-read-path Summary

**CL-10 is closed by enumeration rather than by assertion.** AC-10's words are *"the module's entire
HTTP **and internal** surface"*, and Phase 2 asserted the first third of that and said so in its own
docstring. This plan wrote the two layers it could not reach, plus the third that stands in for a
grant, and then named the one reader none of the three can see — a `BYPASSRLS` database credential
that reads every stored body in every workspace, left in place deliberately and asserted on purpose so
that *"we looked and decided not to"* and *"nobody looked"* are different artifacts a year from now.

## Performance

- **Duration:** ~41 min
- **Tasks:** 3 (two auto, one decision checkpoint)
- **Files created:** 2 · **modified:** 2 (one of them an open question, one a planning artifact)
- **Test suite:** **402 passed**, 0 failed — 360 at the 03-04 baseline, **+42**: 39 in the three-layer
  file (37 of them the two walks parametrized over 15 discovered modules) and 3 in the report-role file

## Which two layers Phase 2 could not reach, and why each is the one at risk

Stated in this plan's own words, because the `<output>` block asks for it.

**Layer 2 — the internal Python surface.** `tests/architecture/test_route_table.py` walks the
assembled table and the OpenAPI schema. `get_run_totals` is neither: it is a **function**, and
evaluation calls it in process with no HTTP in between. A body reaching a caller through a returned
dataclass would satisfy every route-table assertion in this repository and would keep satisfying them
for twenty-one more phases, because the module that would notice does not exist until Phase 16. This
is the layer AC-10's word *internal* was written for, and it is the one where the assertion has to be
about **outputs** — which is why the return-annotation half of layer 2 carries no exemption list at
all. The exemptions are all inputs; a hatch on the output direction would be a hatch on the claim.

**Layer 3 — the statements.** `prope_app`'s privileges on `ledger.call_body` are
`SELECT, INSERT, DELETE`, and **the `SELECT` is load-bearing**: the retention
`DELETE ... WHERE expires_at <= $1` reads a column, and since D-34 the body upsert's `ON CONFLICT`
reads one too — every form of `ON CONFLICT` requires `SELECT` on the columns it reads, which
`writer.py:135-138` already spells out. `0003_ledger_tables.py:246-252` said so to this phase by name:
*"Revoking SELECT here in the name of 'no read path' would break the retention job. AC-10's
no-read-path guarantee is a property of the ROUTE TABLE (Phase 3), not of the grant matrix."*

**So the grant matrix is deliberately not the guarantee, and the plan refused to make it one.**
`prope_app`'s grants were not narrowed. What stands in for a privilege is an enumeration: the set of
files under `src/` that can issue a statement against the table, asserted as a set that fails in both
directions. A file naming the table and not in the map is an offender — that is the arrival the test
exists to catch. A file in the map that no longer names it is stale bookkeeping, and a map describing
a file that stopped mattering is how the next entry gets waved through.

And the uncomfortable half is asserted rather than implied: `test_prope_app_can_read_a_body_and_that_
is_the_point` writes a body through the real write path and reads it back on the runtime credential
inside a tenant transaction. It carries the repository's standing framing for tests of this shape —
**if this test starts failing, do not "fix" it** — with the migration comment cited, because a failure
there means somebody narrowed a grant retention and the idempotent write both need.

## What shipped

### `tests/security/test_no_body_read_path.py` — 39 tests, three layers, three positive controls

**Layer 1** walks `assembled_routes(app)` — never the raw route list, because `include_router` appends
one lazy `_IncludedRouter` and a naive walk asserts vacuously (Broken Window #4) — and checks route
paths, path-parameter names and **request-body model fields**. It deliberately does **not** check the
request-body parameter *name*: three handlers take `payload`, which is a member of
`FORBIDDEN_FIELD_NAMES`, and a parameter named `payload` on a route handler is not the failure CL-10
is about. Two positive controls run before anything is read: the operation count against
`EXPECTED_ROUTES` (imported, so the number eight lives in exactly one place in the repository), and a
floor of three on the number of request-body models actually resolved, so a walk that resolved none
cannot report an empty offender list.

The OpenAPI-schema walk is **not duplicated here.** `test_route_table.py::test_no_schema_property_or_
parameter_exposes_a_stored_body` already does it, and duplicating it would give Phase 23 two tests to
extend instead of one.

**Layer 2** discovers the package with `pkgutil.walk_packages` — never a written-down module list, for
`test_no_sql_interpolation.py`'s stated reason — and is parametrized over the discovered modules with
`ids=lambda m: m.__name__`, so a failure names the offending module. Three properties, each its own
test: no public parameter or field names a body (exempted), no public return annotation resolves to a
type that does (**not** exempted), and the read-side types are named individually because a reviewer
reads names — `RunTotals`' six INT-021 fields, `CeilingDecision`, `WriteResult`, and `EvalUsageRow`,
which carries no body field at all on purpose.

**Layer 3** is an AST walk over `src/prope/**/*.py` matching three shapes — a `text()` argument
carrying the name, a Core construct reaching `models.call_body`, and the binding of the `Table` object
— compared as a set against `BODY_TABLE_WRITERS`. **Nine modules under `src/` mention `call_body` in
prose**, because ADR-0018 is discussed where it binds; a grep would report all nine and the question
is which modules can issue a statement, which is an AST question.

### `tests/security/test_report_role_can_read_bodies.py` — the fourth reader, named

Three tests. The exposure itself (two workspaces seeded through the real write path, both bodies read
back on `prope_report` with `app.workspace_id` unset and asserted unset); the negative control
(`prope_app` reads exactly one row from the same table, which is what makes the first test about a
*role* rather than about a table anybody can read); and the two facts behind it asserted separately at
`pg_roles.rolbypassrls` and `has_table_privilege`, so a future `REVOKE` and a future
`ALTER ROLE ... NOBYPASSRLS` are distinguishable failures rather than one red test with two possible
causes.

`report_engine` has existed in `tests/conftest.py` since Phase 1 with **no consumer**. This is its
first.

### `docs/brainstorm/open_questions/OQ-025.md` — clause 2 appended

The three verified facts, the one-statement exploit, both readings of whether a database role falls
inside AC-10, the three possible answers including the class-level one, what Phase 3 did and why, and
the note that OQ-013's answer changes `call_body`'s retention and therefore how long the exposure
lasts. Two entries added to `blocks`: the lock file's first `security_requirements` clause and
ADR-0037. `blocks_build` stays false. **No upstream spec file was edited** — `git status --porcelain
src alembic pyproject.toml docs/modules docs/architecture docs/adr` produces no output.

The file's H1 was widened from *"no bound in this repository reaches"* to *"no bound and no assertion
in this repository reaches"*, because clause 1 is about a bound and clause 2 is about an assertion, and
the file's own introduction already named the shared subject. Nothing quotes that title.

## Task 3's adopted decision, and the exact exposure a human is being asked to rule on

**Adopted: `assert-and-record`. Status: UNCONFIRMED.**

`prope_report` is created `LOGIN BYPASSRLS` (`alembic/versions/0001_roles_and_schemas.py:47`);
`grant_table`'s `report_select` defaults to `True` (`alembic/ddl.py:103, 122-123`); and
`0003_ledger_tables.py:252` took that default for `ledger.call_body`. **So
`SELECT request_body, response_body FROM ledger.call_body` on the reporting credential returns every
stored body in every workspace, RLS bypassed by role attribute.** That statement is now executed by a
test, and it returns both workspaces' bodies.

The three grounds, in order of weight: **scope** — ROADMAP SC4 is *"no route, parameter, or function"*
and a database role is none of the three, so the phase closes what it was given and hands the excess
upstream (ORCHESTRATION §5); **level** — `report_select` defaults to `True` for every table in the
system, so revoking it here fixes one table and leaves the pattern that produced it in place;
**reversibility** — leaving it and revoking later costs one migration, while revoking now against an
unbuilt restore rehearsal (ADR-0036) and an ADR that records the opposite (ADR-0037) costs a claim
every later module inherits, in a phase that may not amend either document.

**What the human is being asked.** Two things, both carried on `deferred-items.md` Part 1 item 5 and
owed a numbered row on `03-UAT.md`:

1. Confirm the disposition, or direct the `REVOKE` — one migration either way.
2. Decide the class-level question, which is the one that outlives this table: **should
   `grant_table`'s `report_select` default be `False` for a table declared to have no reader?** Every
   future body-bearing column inherits whichever way this goes.

And the closure this replaces: the carried-forward `prope_report` discretion item from Phases 1 and 2
asks *"what grants does `prope_report` get on the new table"*. **This phase creates no table, so as
phrased it is vacuous**, and Phase 2 already took `grant_table`'s default for
`ledger.workspace_retention` — a retention window is a policy row, not a body. Confirming that closure
is the second `<human-check>` in the plan.

## Deviations from Plan

### 1. [Drift — the tree moved under the plan] `BODY_TABLE_WRITERS` has four entries, not three

- **Found during:** Task 2.
- **What the plan said:** three files may name `ledger.call_body` — `writer.py`, `retention.py`,
  `models.py` — with the map written out in the action block.
- **What is true:** there are **four**. `src/prope/worker.py` carries `OLDEST_BODY_CREATED_AT`, a
  `SELECT min(created_at) FROM ledger.call_body WHERE workspace_id = :ws`, added by **plan 03-04** for
  D-43's `oldest_body_age_seconds` gauge — after this plan was written and reviewed. It is the only
  `SELECT` on the body table anywhere in `src/`.
- **Why it is not a violation of the objective:** the statement reads an **age**, never a body column,
  and D-43's whole argument is that the alert must measure the data rather than the job. But the
  plan's own words are that an entry is *"a claim that a THIRD statement needs to touch the body
  table, which is a claim ADR-0018 should be asked about"* — so it was declared with its reason
  **and bounded by its own assertion** rather than waved through on the reason alone:
  `test_the_age_gauge_selects_no_body_column` requires the statement to name `min(created_at)` and to
  name neither `request_body` nor `response_body`. The moment the gauge grows a body column, the
  statement that measures the data becomes the statement that reads it, and that test is what says so.
- **Files:** `tests/security/test_no_body_read_path.py`.

### 2. [Drift — a plan criterion vs. a repository habit] `grep -c "app.routes"` and the docstring

- **Found during:** Task 1 verification.
- **Issue:** the plan's acceptance criterion is `grep -c "app.routes" … returns 0`. The first draft's
  layer-1 docstring named the refused spelling in prose — *"`assembled_routes`, never `app.routes`"* —
  which is exactly the habit `deferred-items.md` records for
  `test_metrics_is_a_route_the_table_can_see_and_not_a_mount` (*"the docstrings name the refused shape
  on purpose, at the places a reader meets the decision"*), and it made the criterion unsatisfiable.
- **Fix:** the sentence now says *"never the raw `routes` list on the application object"*, which
  carries the same meaning and the same Broken Window #4 citation, and states in the docstring why the
  spelling is avoided. The assertion itself never changed — the walk has always called
  `assembled_routes`. No test was weakened.
- **Files:** `tests/security/test_no_body_read_path.py`.

### 3. [Judgement the plan left to the executor] The internal walk's scoping rule

- **Issue:** the plan says *"for every public name in each module's namespace"* and does not say what
  to do with a name the module **imported**. Taken literally, the walk inspects `pydantic.BaseModel`
  (imported by every schema module) and `dataclasses.dataclass`, which would put a third party's field
  names inside CL-10's claim and would inflate the floors with names this module does not own.
- **Resolution, written at the helper:** a public name is judged at its **definition site**, and
  anything defined outside the `prope` package is skipped. Both halves are deliberate — a body-naming
  type this package re-exports is reachable from `prope.call_ledger` and is exactly the shape AC-10
  refuses, so re-exports are covered and exempted as the same type rather than as a second entry;
  `pydantic.BaseModel` is a tool, and asserting over it would make this test fail on somebody else's
  release.

### 4. [Strengthening within the plan's objective] Three additions the plan did not name

None of these relaxes anything; each closes a way the assertion could have been vacuous.

- **The exemption lists are proved *sufficient* as well as *necessary*.** The plan asks for the sizes
  and for one positive control on `CallBodyDraft`. `test_the_exemption_lists_are_exactly_what_names_a_
  body` additionally re-runs the whole walk with **both hatches closed** and compares its output
  against a literal eleven-name enumeration, so a stale entry — a type that stopped naming a body —
  fails as loudly as a missing one.
- **Return-annotation resolution is asserted.** `typing.get_type_hints` first, and an annotation that
  could not be resolved is collected and asserted empty rather than skipped. No module in `src/` uses
  `from __future__ import annotations` today (`grep -rn "from __future__" src/` is empty); the day one
  does, this test says so instead of quietly comparing strings.
- **Layer 1 floors the number of request-body models it resolved** at three, so the body-field half of
  that walk cannot pass by resolving none.

### Authentication Gates

None.

---

**Total deviations:** 1 drift from the tree (declared and bounded), 1 wording change to satisfy a
mechanical criterion, 1 executor judgement recorded, 3 strengthenings. **No architectural change:** no
source file, no migration, no dependency, no new role and no grant change. This plan is tests and one
open question.

## Mutation checks — the assertions were proved able to fail

Every escape hatch was closed in a temporary local edit, the suite run, and the edit reverted. The
file on disk is byte-identical to the pre-mutation copy apart from deviation 2's docstring wording.

| Mutation | Result |
|---|---|
| `BODY_NAMING_EXEMPT_TYPES = frozenset()` | **7 failed, 32 passed** — six parametrized modules plus the exemption test |
| `BODY_NAMING_EXEMPT_PARAMETERS = frozenset()` | **2 failed, 37 passed** — `prope.call_ledger.api` plus the exemption test |
| A fourth file (`src/prope/_mutation_probe.py`) with `text("SELECT request_body FROM ledger.call_body")` | **1 failed, 38 passed** — `test_only_the_declared_writers_name_the_body_table` |

The probe file was deleted; `git status --porcelain src alembic` is empty.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest -q` (whole suite) | **402 passed, 1 warning in 192.94s (0:03:12)** |
| `uv run pytest tests/security/ -q` | **63 passed** |
| `uv run pytest tests/security/test_no_body_read_path.py -q` | **39 passed** |
| `uv run pytest tests/security/test_report_role_can_read_bodies.py -q` | **3 passed** |
| `uv run ruff check src/ tests/ alembic/` | **All checks passed!** (exit 0) |
| `git status --porcelain src alembic pyproject.toml docs/modules docs/architecture docs/adr` | no output |
| `grep -c "FORBIDDEN_FIELD_NAMES = " tests/security/test_no_body_read_path.py` | `0` — imported, never re-declared |
| `grep -rn "FORBIDDEN_FIELD_NAMES = " --include=*.py .` | one site: `tests/architecture/test_route_table.py:93` |
| `grep -c "app.routes" tests/security/test_no_body_read_path.py` | `0` |
| `grep -c "CallBodyPayload" tests/security/test_no_body_read_path.py` | `0` — the type is `CallRecordPayload` and no such name exists in `src/` |
| `uv run ruff format --check` | **not run, not a gate.** Broken Window #1, repo-wide and pre-existing |

The literal tail of the full run:

```
402 passed, 1 warning in 192.94s (0:03:12)
```

## The agent measurement this file's floors rest on

Recorded as a measurement and **labelled as one**, because no detector exists in this environment
(ORCHESTRATION §0) and none was run. The package was enumerated with `pkgutil` + `inspect` against
`FORBIDDEN_FIELD_NAMES` this session, against this tree, after plans 03-01 through 03-04 landed:

- **15 modules** in `prope.call_ledger` (the plan's calibration said 13, before `fallback.py` and the
  package `__init__`).
- **34 public callables** and **23 public dataclasses / pydantic models**, counted at their definition
  sites under the scoping rule in deviation 3. The plan's calibration said 27 and 21.
- **The offender set is still exactly the plan's seven**, split four types / three callables. Nothing
  landed in plans 03-01 through 03-04 that names a body outside them — `HandoffItem` carries a
  `CallRecordDraft` under the field name `draft`, and `fallback.py` exports one builder that takes a
  sessionmaker.

Floors were set at 10 / 20 / 15, comfortably below, with a comment saying they are floors and not
targets.

## Notes for the verifier and for later phases

- **Phase 23 extends `test_no_body_read_path.py`, it does not replace it.** Layer 1 uses
  `assembled_routes` and imports `EXPECTED_ROUTES` and `FORBIDDEN_FIELD_NAMES` from
  `tests/architecture/test_route_table.py`, so the cross-module form is a change of scope rather than
  a new file. Layer 2's package walk is parametrized over `prope.call_ledger` alone and would become a
  walk over eight packages; the exemption lists are the part to re-argue, not to copy.
- **`FORBIDDEN_FIELD_NAMES` has exactly one declaration site in the repository** and this plan added a
  second consumer rather than a second copy. An eleventh name goes in `test_route_table.py:93`.
- **`BODY_TABLE_WRITERS` will grow when a phase writes a body reader**, and the point is that it has
  to be an entry with a reason. Phase 23's cross-module form does not touch it — layer 3 is already
  repository-wide, because it walks `src/prope/**/*.py` and not just the one package.
- **The `MINIMUM_BODY_TABLE_SITES = 4` floor equals today's count**, which is tight on purpose: the
  set equality already fails on a removal, and the floor's separate job is to catch a matcher that
  stopped matching. **Lowering it belongs with the removal of a map entry; raising it to make a
  failure pass is refused**, in `test_no_sql_interpolation.py`'s own words.
- **`report_engine` now has a consumer.** A later phase that adds a table with a body-shaped column
  inherits `grant_table`'s `report_select=True` default silently. That is OQ-025 clause 2's
  class-level question and it is not this phase's to answer.
- **CL-10's `REQUIREMENTS.md` row was not ticked.** It still reads `Pending`, untouched, matching
  plans 03-01 through 03-04 — the tick is the phase gate's, on evidence the verifier gathers itself
  (ORCHESTRATION §9.1).
- **`03-UAT.md` owes two numbered rows from this plan:** Task 3's adopted disposition (with the
  class-level default question), and the closure of the carried-forward `prope_report` discretion item
  as vacuous-as-phrased.

## Known Stubs

None. Every symbol this plan created is a test or a constant a test reads, and every test drives a
real object — the assembled application, the imported package, the parsed source tree, or the live
engine through three credentials.

## Threat Flags

None new. Every row in the plan's `<threat_model>` is mitigated and asserted, or accepted with a name
on it:

| Threat | Disposition | Where |
|--------|-------------|-------|
| T-03-33 (a body returned through a function rather than a route) | mitigated | Layer 2's three tests, discovered walk, no exemption on the return direction |
| T-03-34 (a body through a schema property or parameter) | mitigated (carried) | `test_route_table.py`, stated as a dependency and not duplicated |
| T-03-35 (a new `SELECT` on `ledger.call_body` arriving unnoticed in `src/`) | mitigated | Layer 3's set equality, both directions, plus the site floor — and it caught one already (deviation 1) |
| T-03-36 (a body read on the reporting credential, RLS bypassed) | **accepted, declared** | `test_report_role_can_read_bodies.py`, OQ-025 clause 2, `deferred-items.md` Part 1 item 5, `03-UAT.md` owed |
| T-03-37 (the sweep weakened to make a failure pass) | mitigated | Three hatches, each an entry with a reason and an asserted size, all three proved able to fail |
| T-03-38 (a vacuous assertion that inspected nothing) | mitigated | Five positive controls: route count, resolved body models, package floors, `CallBodyDraft`'s fields, the site floor and non-empty file list |
| T-03-39 (narrowing `prope_app`'s grant in the name of "no read path") | refused, and asserted in the opposite direction | `test_prope_app_can_read_a_body_and_that_is_the_point` |

**No new network surface. No new table, migration, role or privilege. No source file changed.**

## Self-Check: PASSED

- Both created files exist on disk and are driven by the commands in the table above.
- `docs/brainstorm/open_questions/OQ-025.md` carries clause 2, contains `BYPASSRLS`, keeps
  `status: open`, and gained two `blocks` entries.
- `BODY_NAMING_EXEMPT_TYPES` (4), `BODY_NAMING_EXEMPT_PARAMETERS` (3) and `BODY_TABLE_WRITERS` (4) are
  literal declarations with a written reason per entry, and every size is asserted.
- The string `CallBodyPayload` appears nowhere; the transport type is `CallRecordPayload`.
- No file under `src/` or `alembic/` was modified. No lock file, interfaces file or ADR was touched.
- `uv run pytest -q` → **402 passed**. `uv run ruff check src/ tests/ alembic/` → clean.
- No commit in this plan deleted a tracked file.

---
*Phase: 03-durability-idempotency-and-no-read-path*
*Completed: 2026-08-11*
