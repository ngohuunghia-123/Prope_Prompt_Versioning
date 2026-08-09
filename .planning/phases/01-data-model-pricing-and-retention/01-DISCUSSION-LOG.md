# Phase 1: Data model, pricing, and retention - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-09
**Phase:** 1-data-model-pricing-and-retention
**Areas discussed:** Project foundation & test rig, Migration-carried guarantees

**Areas offered but not selected:** Pricing semantics & money, Write path & retention job shape — both re-offered at the close and explicitly left to the researcher and planner (see Claude's Discretion).

---

## Gray area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Project foundation & test rig | Package layout, Alembic wiring, and how tests get a real Postgres 17 | ✓ |
| Migration-carried guarantees | Roles, RLS policies, T-006 REVOKEs, ADR-0045 coverage test scope | ✓ |
| Pricing semantics & money | NUMERIC precision/scale, rounding, effective_from boundary, unpriced vs unknown | |
| Write path & retention job shape | The Phase 1 callable seam, workspace_spend updates, deletion-job scheduling | |

---

## Project foundation & test rig

### Q1 — Package tree layout

| Option | Description | Selected |
|--------|-------------|----------|
| `src/prope/<module_id>/` | One installable `prope` package; each bounded context a subpackage with internal layering. Mirrors schema-per-module; gives import-linter concrete contracts | ✓ |
| `src/call_ledger/` at top level | Each module its own top-level package. Flatter imports, no namespace for the import-linter root, PyPI collision risk | |
| `src/prope/` with horizontal layers | Shared `models/ services/ api/` with modules as files. Conventional FastAPI shape — fights the bounded-context decomposition | |

**User's choice:** `src/prope/<module_id>/`
**Notes:** Framed against release-control's owed AC-14 (an import-linter layering contract that fails the build on a cross-module model import) — it needs real package boundaries to bind to. The module map's "no frontend or backend module, because neither owns a journey" ruled out the horizontal option.

### Q2 — How tests get a Postgres 17

| Option | Description | Selected |
|--------|-------------|----------|
| testcontainers-python | Session fixture starts a real postgres:17, runs Alembic as `prope_migrate`, hands tests a `prope_app` connection. Identical locally and in CI; Docker becomes a hard test dependency | ✓ |
| docker-compose `db` service | `make test` assumes it is already up. Matches ADR-0033's runtime; tests inherit prior state, role-privilege isolation is hard | |
| CI service container + local compose | GitHub Actions `services: postgres:17`, local devs use compose. Two provisioning paths that drift | |

**User's choice:** testcontainers-python
**Notes:** Decided on the observation that RLS returning zero rows, the T-006 REVOKEs refusing an UPDATE, and effective-dated selection at a timestamp boundary are only observable against a live engine. The two-path option was rejected because the first drift reads as green CI over a broken local run.

### Q3 — How far to go on the boilerplate scaffold

| Option | Description | Selected |
|--------|-------------|----------|
| Replace dep/build config only | `pyproject.toml` on the real stack, drop LangChain, repoint Makefile. Dockerfile and docker-compose untouched | ✓ |
| Also rewrite Dockerfile + compose | Bring compose to postgres/rabbitmq/app/worker now. Runnable earlier — writes deployment decisions no phase owns; RabbitMQ has no consumer until Phase 2 | |
| Leave scaffold, add alongside | Smallest diff — `make test` / `make run` stay broken for 24 phases and LangChain stays in a project that serves no models | |

**User's choice:** Replace dep/build config only
**Notes:** PITFALLS gap 4 (the deployment stack owns no milestone and needs a user decision) is why the line was drawn at dependency config rather than at the runtime.

### Q4 — Alembic chain shape

| Option | Description | Selected |
|--------|-------------|----------|
| One linear chain, hand-written | Single history for all eight schemas, run as `prope_migrate`. Autogenerate may draft a table diff but is never trusted | ✓ |
| Branch label per module | Eight independent branches. Cleaner ownership — eight heads on one VM, and cross-schema ordering stops being expressible | |
| One chain, autogenerate-first | Autogenerate as the normal workflow with hand-edits after. Fails silently: the first run after a policy lands proposes dropping it | |

**User's choice:** One linear chain, hand-written
**Notes:** A-128 puts RLS policies, constraints, extensions and triggers in Alembic, which is precisely what autogenerate cannot see.

---

## Migration-carried guarantees

### Q1 — Where the three roles are created

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic migration 0001 | Idempotent DO block, first in the chain, no passwords baked in. `alembic upgrade head` against an empty cluster yields a working database | ✓ |
| Separate bootstrap SQL, run once | Clean split of cluster-level from schema-level — two ordered steps that can be run out of order or skipped | |
| Postgres image init script | Zero ordering risk — production and test would then create roles by different mechanisms | |

**User's choice:** Alembic migration 0001
**Notes:** Follows directly from Q2 of the previous area — testcontainers hands the suite a pristine cluster every run, so any second provisioning path reintroduces the drift that ruled out the CI/local split.

### Q2 — Scope of ADR-0045's coverage test

| Option | Description | Selected |
|--------|-------------|----------|
| All eight schemas, absent ones reported | Iterates the eight declared schema names, asserts every table found, prints which declared schemas do not yet exist | ✓ |
| Scoped to `ledger`, widened per module | Smallest Phase 1 surface — the "walks all eight" property is asserted nowhere, and a module that forgets to widen it is invisible | |
| Defer the coverage test | Cheapest now — leaves the guarantee unenforced across all of M1 and M2 | |

**User's choice:** All eight schemas, absent ones reported
**Notes:** ADR-0045 exists because the previous rule "selected for its own blind spot" — a table was invisible to the check precisely when someone had decided its tenant column was unnecessary. A test scoped to today's tables has the same shape of blind spot.

### Q3 — Where T-006's REVOKEs land

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 1, with the engine-level test | Each table's migration carries REVOKE ALL from PUBLIC, explicit GRANTs, then T-006's REVOKEs; a test asserts the engine refuses UPDATE/DELETE on `price_table` as `prope_app` | ✓ |
| Phase 1 REVOKEs, Phase 3 tests | Guarantee in the database from day one — nothing proves it survived a later migration for two phases | |
| Grants only in Phase 1 | Cleanest match to the ROADMAP's filing of `security_requirements` under Phase 3 — leaves "append-only" a convention, the exact defect ADR-0025 fixed for `history_event` | |

**User's choice:** Phase 1, with the engine-level test
**Notes:** This is a deliberate, recorded departure from the ROADMAP's spec line, justified by Phase 1's own goal text ("priced correctly and **irreversibly**") and by CL-03/CL-05 resting on the price table being append-only. `call_body` keeps DELETE — the retention job must have it.

### Q4 — Tenant-context plumbing

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit `workspace_transaction()` | One async context manager takes `workspace_id`, opens the transaction, issues SET LOCAL, yields the session; repositories accept only sessions from it | ✓ |
| SQLAlchemy `after_begin` hook + contextvar | Impossible to forget at a call site — makes the tenant invisible in the writer's code and fails as zero rows rather than as an error | |
| SET LOCAL at each entry point | No abstraction to learn — a forgotten call silently returns zero rows, indistinguishable from an empty result | |

**User's choice:** Explicit `workspace_transaction()`
**Notes:** ADR-0040 makes call-ledger the one writer spanning workspaces, and it needs `workspace_id` to be an explicit grouping key at the call site — which the ambient-contextvar option hides. Paired with a test that the same query outside the manager returns zero rows.

---

## Claude's Discretion

Two gray areas were re-offered at the close and explicitly handed to the researcher and planner rather than decided here:

- **Pricing semantics & money** — NUMERIC precision and scale for prices vs. cost, the rounding rule against a stated currency, the `effective_from` boundary case, and whether "a price row exists but starts after this call" is `unpriced` on the same footing as "no price row at all".
- **Write path & retention job shape** — what is callable in Phase 1 to prove write-time pricing when `enqueue` and the drain arrive in Phase 2; whether the writer already updates `workspace_spend` (A-103); and whether Phase 1 ships a scheduler for the deletion job before the `worker` process exists.

Also left open in the same pass: index strategy for the `expires_at` and effective-dated-price predicates, the NOT NULL / CHECK constraints encoding `usage_status` / `cost_status` / `source` / `outcome` / `version_id`, and whether `prope_report` receives read grants in Phase 1.

## Deferred Ideas

None. Discussion stayed inside the phase boundary; no new capability was proposed.
