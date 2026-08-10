---
phase: 01-data-model-pricing-and-retention
plan: 01
subsystem: call-ledger / project foundation
tags: [alembic, postgresql-17, rls, tenancy, testcontainers, python-313]
status: complete

requires: []
provides:
  - "The Alembic chain: one linear hand-written history, version table in `public`"
  - "`alembic/ddl.py` — enable_tenant_rls / grant_table / assume_migrate_role, reused by every later revision"
  - "Roles `prope_migrate` / `prope_app` / `prope_report`, and the `ledger` schema"
  - "`ledger.call_record` with its CHECK set, indexes, RLS policy and grant matrix"
  - "`prope.db.session.workspace_transaction()` — the tenant seam all eight modules are written against"
  - "`prope.db.metadata.metadata` — the shared MetaData and naming convention 23 phases inherit"
  - "`tests/conftest.py` — the testcontainers rig and three role-scoped engines"
affects:
  - "Every later Alembic revision in the project (chain shape, helper API, ownership convention)"
  - "Every repository signature in all eight modules (workspace_transaction)"
  - "Every phase's test suite (the fixture shape)"

tech-stack:
  added:
    - "Python 3.13.14 via uv (ADR-0026 pin)"
    - "SQLAlchemy 2.0.51 [asyncio] + asyncpg 0.31.0 + greenlet 3.5.4"
    - "Alembic 1.19.1"
    - "pydantic 2.13.4 + pydantic-settings 2.15.0"
    - "fastapi 0.141.1 + uvicorn[standard] 0.52.1 (pinned, no routes built)"
    - "python-ulid 4.0.1, structlog 26.1.0, prometheus-client 0.26.0"
    - "pytest 9.1.1 + pytest-asyncio 1.4.0 + testcontainers[postgresql] 4.15.0 + ruff 0.16.2"
    - "hatchling as the build backend, src-layout"
  patterns:
    - "The migration carries the guarantee; application code is what the guarantee protects"
    - "text + named CHECK for every vocabulary, never a native PostgreSQL enum"
    - "Two-argument current_setting in every policy predicate, no cast"
    - "RLS ENABLED, never FORCED — the owner bypass is load-bearing"
    - "`now` is a parameter, never a call: created_at has no column default"
    - "Truncate between tests, never outer-transaction rollback"
    - "Grant only what is needed rather than GRANT ALL then REVOKE"

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - alembic.ini
    - alembic/env.py
    - alembic/ddl.py
    - alembic/script.py.mako
    - alembic/versions/0001_roles_and_schemas.py
    - alembic/versions/0002_call_record.py
    - src/prope/__init__.py
    - src/prope/db/__init__.py
    - src/prope/db/metadata.py
    - src/prope/db/engine.py
    - src/prope/db/session.py
    - src/prope/call_ledger/__init__.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/security/__init__.py
    - tests/security/test_tenant_isolation.py
    - tests/security/test_call_record_guarantees.py
    - .planning/phases/01-data-model-pricing-and-retention/.phase-base-sha
    - .planning/phases/01-data-model-pricing-and-retention/deferred-items.md
  modified:
    - ruff.toml
    - Makefile
  deleted:
    - requirements.txt

decisions:
  - "OQ-A resolved `text-no-cast`: workspace_id is text and the policy predicate compares text to text. Confirmed at the Task 3 gate."
  - "Alembic layout: one revision per slice, guarantee-per-helper. Per-kind greppability lives in alembic/ddl.py, not in the chain."
  - "alembic_version lives in `public` via version_table_schema, so D-06's coverage walk never has to except it."
  - "Revision 0001 runs as the bootstrap superuser (A9, BYPASSRLS); every revision from 0002 opens with assume_migrate_role() and closes with reset_role()."
  - "alembic/ddl.py is imported by revisions as a bare `ddl`, never as `alembic.ddl` — that dotted name is the installed package's own submodule."
  - "Every test engine uses NullPool; the reused-connection path is asserted by holding one connection across two transactions rather than by relying on a pool."

metrics:
  duration: ~2h
  completed: 2026-08-10

actuals:
  tokens: 41000
  tasks: 4
  commits: 4
---

# Phase 01 Plan 01: Data model foundation and the tenancy tracer — Summary

Stood up Prope's Python/Alembic/testcontainers foundation on the pinned 3.13
interpreter and proved the tenancy contract end to end against a live
PostgreSQL 17: one `ledger.call_record` row written through
`workspace_transaction()` is readable inside that transaction and returns zero
rows to every caller without the tenant context — on both a pristine and a
reused connection, each with a `prope_migrate` positive control.

## What was built

**The chain.** Two hand-written revisions in one linear history (D-04).
`0001_roles_and_schemas` creates `prope_migrate`, `prope_app` and
`prope_report` (the last with `BYPASSRLS`) through an idempotent `DO` block
guarded on `pg_roles`, with no passwords baked in, then
`CREATE SCHEMA ledger AUTHORIZATION prope_migrate`.
`0002_call_record` carries one table's entire guarantee stack: 28 columns, 10
named `CHECK` constraints, 3 indexes, the RLS policy and the grant matrix.
`alembic/ddl.py` holds the three emitters — `assume_migrate_role`,
`enable_tenant_rls`, `grant_table` (plus `reset_role`) — so a reviewer greps a
helper name rather than a revision file.

**The seam.** `workspace_transaction(sessionmaker, workspace_id)` opens the
session, opens a real transaction *first*, then binds the tenant through
`set_config('app.workspace_id', :ws, true)`. There is no interpolation of any
kind in `src/prope/db/session.py`, asserted by a source gate and by a test that
round-trips a workspace id containing a single quote.

**The rig.** A session-scoped `postgres:17` testcontainer; `alembic upgrade
head` on its own `NullPool` engine which is then disposed before any
application engine is built; role passwords set out of band as the container
superuser; truncate-between-tests isolation discovered from `pg_tables` so the
remaining three plans in this phase can add tables without editing the rig.

## Verification — what actually ran

Every claim below is the output of a command executed in this session, not a
reading of the migration source.

| Check | Result |
|-------|--------|
| `uv run python -c "…sys.version_info[:2]"` | `(3, 13)` |
| `docker run --rm postgres:17 postgres --version` | `postgres (PostgreSQL) 17.10 (Debian 17.10-1.pgdg13+1)` |
| `uv run alembic upgrade head` vs. a pristine container | exit 0; re-run is a no-op |
| `uv run alembic heads` | `0002 (head)` |
| `uv run pytest tests/security/test_tenant_isolation.py -x -q` | **5 passed** |
| `uv run pytest -q` | **14 passed** |
| `uv run ruff check .` | All checks passed |
| `alembic_version` location | `public.alembic_version`, `version_num = 0002` |
| `docs/` modified since the fixed phase base | 0 committed, 0 uncommitted |
| `Dockerfile` / `docker-compose.yml` | byte-identical |

Direct queries against the pristine container:

| Property | Observed |
|----------|----------|
| `ledger.call_record` owner | `prope_migrate` |
| policies on the table | exactly 1, `call_record_tenant` |
| `relrowsecurity, relforcerowsecurity` | `true, false` — enabled, never forced |
| policies whose predicate casts to uuid | `0`; qual is `(workspace_id = current_setting('app.workspace_id'::text, true))` |
| `created_at` column default | NULL (and `written_at` does default) |
| CHECK constraints | 10 |
| `prope_app` grants | `INSERT, SELECT, UPDATE` — no DELETE (T-006) |
| `prope_report` grants | `SELECT`; `rolbypassrls = t` |
| `PUBLIC` grants | none |
| indexes | `pk_call_record`, `ix_call_record_workspace_id_created_at`, `ix_call_record_unpriced_worklist`, `ix_call_record_workspace_id_run_id` |

### The must-have truths, and the test that proves each

| Truth | Proved by |
|-------|-----------|
| Interpreter is 3.13, not the machine's 3.14 | `uv run python -c …` → `(3, 13)` |
| `postgres:17` served by a reachable daemon | `docker run --rm postgres:17 postgres --version` |
| Zero rows on a **pristine** connection; positive control as `prope_migrate` | `test_pristine_connection_without_tenant_context_returns_zero_rows` — also asserts the setting reads NULL, so the path is genuinely the pristine one |
| Zero rows on a **reused** connection whose setting reverted to `''` | `test_reused_connection_whose_tenant_setting_reverted_returns_zero_rows` — asserts the setting reads `''`, distinguishing it from the pristine path |
| Cross-workspace INSERT refused by `WITH CHECK`, not written | `test_insert_carrying_another_tenants_workspace_id_is_refused` — refusal names row-level security, and a `prope_migrate` control confirms the table is empty afterwards |
| A workspace id with a single quote is bound and round-trips | `test_workspace_id_containing_a_quote_round_trips_unchanged` |
| `cost = 0` refused by the live engine | `test_a_cost_of_zero_is_refused_by_the_engine` → names `ck_call_record_cost_is_never_zero` |
| `usage_status='unknown'` with `input_tokens = 0` refused | `test_unknown_usage_with_zero_tokens_is_refused` → names `ck_call_record_unknown_usage_is_null` |
| `created_at` has no column default | `test_created_at_has_no_column_default` (and `written_at` asserted to have one) |

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 — Blocking] `src/prope/__init__.py` created in Task 1 rather than Task 4**
- **Found during:** Task 1
- **Issue:** `pyproject.toml` declares a src-layout `prope` package. With no
  package directory on disk, hatchling cannot build the editable install and
  *every* `uv run` fails before doing anything — including Task 1's own
  `uv run alembic heads` acceptance criterion.
- **Fix:** created the minimal package root only. Task 4 still created `db/`
  and `call_ledger/` as planned.
- **Commit:** `468b97f`

**2. [Rule 3 — Blocking] `ruff.toml` excludes `scripts/`**
- **Found during:** Task 1
- **Issue:** `uv run ruff check .` failed on 8 violations, all pre-existing and
  all in the `.ai-log` course-logging tooling. None was introduced by the
  py311 → py313 bump (`UP017` fires from py311 onward; `I001`/`N806`/`F541` are
  target-version independent). CONTEXT.md names that directory as a scaffold
  remnant, and the Makefile's `lint` target already scopes to
  `src/ tests/ alembic/`.
- **Fix:** excluded the directory with a written reason so `ruff check .` gates
  on Prope's own code. The 8 violations are itemised in `deferred-items.md`,
  not silently dropped.
- **Commit:** `468b97f`

**3. [Rule 1 — Bug] Revisions import the emitters as `ddl`, not `alembic.ddl`**
- **Found during:** Task 4
- **Issue:** the plan specifies `alembic/ddl.py`, but `alembic.ddl` already
  resolves to the *installed* Alembic package's dialect-DDL submodule. The
  literal import failed with `cannot import name 'assume_migrate_role' from
  'alembic.ddl'`. Revision scripts are loaded by file path rather than as
  members of a package, so there is no relative-import route either.
- **Fix:** the file stays at `alembic/ddl.py` with the required exports;
  revisions import it as a bare `ddl`, and `alembic.ini`'s `prepend_sys_path`
  puts the directory on the path. It had to be the ini rather than `env.py`,
  because `alembic heads` and `alembic history` load revision files **without
  ever running `env.py`** — a version that only patched `env.py` made
  `upgrade head` pass while `heads` crashed. `path_separator` moved from `os`
  to `newline` so the two-entry list is not Windows-only.
- **Commit:** `5bcda35`

**4. [Rule 1 — Bug] `testcontainers.postgres` is deprecated**
- **Found during:** Task 4
- **Issue:** importing it emitted a `DeprecationWarning` pointing at
  `testcontainers.community.postgres`.
- **Fix:** import from the non-deprecated module. Same `PostgresContainer`
  class; verified both paths export it before switching.
- **Commit:** `5bcda35`

### Additions

**5. [Rule 2 — Missing verification] `tests/security/test_call_record_guarantees.py`**
- **Why:** nine of Task 4's acceptance criteria are database properties
  (`created_at` has no default, `relforcerowsecurity` is false, no policy casts
  to uuid, `cost = 0` is refused, …). Checking them once in a shell leaves
  nothing that fails if a later revision regresses one. They are now executed
  tests. `test_tenant_isolation.py` was kept at **exactly the five tests the
  plan specifies** so its acceptance criterion still reads literally.
- **Commit:** `5bcda35`

**6. `app_engine` fixture and `reset_role()` helper**
- `app_engine` is exposed alongside `app_sessionmaker` because the
  reused-connection proof needs a connection held across two transactions, and
  deriving one from a sessionmaker's internals would be worse than naming it.
- `reset_role()` pairs with `assume_migrate_role()`. Without it the role switch
  is still in force when Alembic writes `public.alembic_version`, which
  `prope_migrate` has no privilege to touch — `upgrade head` fails on the
  version bookkeeping rather than on any DDL.

## Checkpoints

| Task | Type | Outcome |
|------|------|---------|
| 2 | human-action | Docker Desktop was already installed; the binary is simply not on the default bash PATH. My initial probe reported it absent and was wrong. Cleared after the coordinator supplied the path; re-verified independently before use. **Every shell driving docker must first `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`.** There is no `DOCKER_HOST` — this is Docker Desktop over the Windows named pipe, not a WSL engine. |
| 3 | decision | **`text-no-cast` selected.** `workspace_id text NOT NULL`; predicate `workspace_id = current_setting('app.workspace_id', true)`, no cast. Now asserted in the database, not only in prose. |
| 1 (`human-check`) | package legitimacy | **All 15 packages approved, none removed.** Zero `[SLOP]`; every `[SUS]` was `unknown-downloads` (PyPI's JSON API exposes no download counts) or `too-new` (the heuristic reads latest-release date, not package age); every package is named by an in-repo specification (A-128, ADR-0026, ADR-0030, ADR-0033, `call-ledger.lock.yml:297`) rather than discovered by search. All 15 resolved and installed at their exact pins. |

## Open questions carried upstream (unedited, as instructed)

- **OQ-A** — `docs/adr/0035-…:43` and `docs/adr/0045-…:89-90` write the policy
  predicate with a `::uuid` cast that would raise against a `wsp_`-prefixed
  ULID. Adopted reading implemented; the ADR wording still needs upstream
  correction.
- **OQ-B** — the per-workspace retention window has no home in `data.owns`.
  Untouched here; Phase 2 needs the answer.
- **OQ-C** — the retention job's cross-tenant enumeration. **No fifth
  `SECURITY DEFINER` function was created**; this phase adds none at all.
- **OQ-D** — ADR-0040's "bounded chunks inside that workspace's transaction".
  Untouched by this plan; plan 01-04 implements the adopted reading.
- **OQ-E** — GATE-04's "zero tokens and zero cost" versus this phase's
  never-zero encoding. The never-zero reading is now enforced by
  `ck_call_record_cost_is_never_zero` and `ck_call_record_unknown_usage_is_null`
  and asserted by two tests, so Phase 19 inherits it rather than inventing a
  zero.

## Known Stubs

None. Nothing in this plan renders a placeholder or returns a hardcoded empty
value. `Makefile`'s `run` target points at `prope.app:app`, which does not
exist yet — that is a phase-2 module (D-03), named as such in a comment beside
the target, and it is a deliberately-not-yet-servable entry point rather than a
stub in shipped code.

## Threat Flags

None. No file created here introduces network surface, an auth path, file
access, or a trust-boundary schema change outside the plan's `<threat_model>`.
`T-01-01` through `T-01-05` are mitigated and asserted; `T-01-06` (A9 — the
superuser migration connection) remains `accept`, and is named in revision
0001's module docstring as required.

## Notes for the next plan

- Import the emitters as `from ddl import …`. Never `from alembic.ddl import …`.
- Open every revision from 0003 onward with `assume_migrate_role()` and close
  it with `reset_role()`.
- `tests/conftest.py` discovers `ledger` tables from `pg_tables`, so new tables
  are truncated between tests with no edit to the rig.
- Reuse `tests/security/__init__.py`'s `call_record_values()` builder rather
  than re-deriving a valid row; the CHECK set is strict enough that hand-built
  rows are usually refused for the wrong reason.
- `price_row_id` exists on `call_record` as plain `text`. Revision 0003 adds
  its in-schema FK once `ledger.price_table` exists.

## Self-Check: PASSED

All 21 created files verified present on disk. All 4 commits
(`468b97f`, `72bfaf2`, `ba672e6`, `5bcda35`) verified present in
`git log --oneline --all`.
