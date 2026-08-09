# Phase 1: Data model, pricing, and retention — Research

**Researched:** 2026-08-09
**Domain:** PostgreSQL 17 schema design under row-level security · effective-dated pricing · exact-decimal money · batched retention deletion · Alembic-as-guarantee-carrier · async SQLAlchemy/asyncpg · live-engine testing
**Confidence:** HIGH on everything the repo has already decided and on the PostgreSQL/driver mechanics; MEDIUM on the six areas the user handed to Claude's discretion; four genuine spec gaps are raised as open questions rather than quietly resolved.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

Copied verbatim from `.planning/phases/01-data-model-pricing-and-retention/01-CONTEXT.md` `<decisions>`.

**Project foundation**

- **D-01:** Package tree is `src/prope/<module_id>/` — one installable `prope` package, each bounded context a subpackage (`src/prope/call_ledger/`) with its own internal layering. Mirrors schema-per-module one-to-one and gives release-control's owed import-linter contract real package boundaries to bind to. Horizontal `models/ services/ api/` layering is rejected — the module map states there is no "frontend" or "backend" module because neither owns a journey. — **Reversibility:** costly — a later move rewrites every import in every module and invalidates the import-linter contract.
- **D-02:** Tests run against a **real Postgres 17 via testcontainers-python**. A pytest session fixture starts the container, runs Alembic as `prope_migrate`, and hands tests a `prope_app` connection. Chosen because every Phase 1 guarantee — RLS returning zero rows, the T-006 REVOKEs refusing an UPDATE, effective-dated selection at a timestamp boundary — is only observable against a live engine; mocking the driver proves nothing. Accepted cost: Docker is a hard test dependency. A CI-service-container/local-compose split was rejected specifically because two provisioning paths drift, and the first drift reads as green CI over a broken local run. — **Reversibility:** costly — the fixture shape is inherited by all 24 phases' test suites.
- **D-03:** Phase 1 replaces **dependency and build config only**: a `pyproject.toml` pinning Python 3.13.x, FastAPI + uvicorn + pydantic v2, SQLAlchemy 2.0 + asyncpg, Alembic, pytest + testcontainers, and ruff; LangChain/LangGraph are dropped (Prope's ML stack is `n/a`); Makefile targets are repointed off `src.main:app`. `Dockerfile` and `docker-compose.yml` are **left untouched** — the real runtime is ADR-0033's and belongs to work that owns no milestone yet.
- **D-04:** **One linear Alembic chain, hand-written.** A single `alembic/versions/` history for all eight schemas, run as `prope_migrate`, one `alembic upgrade head` per deploy. Autogenerate may be used to draft a table diff but its output is never trusted or committed unreviewed: it cannot see RLS policies, grants, or triggers, and the first autogenerate after a policy lands proposes dropping what it cannot see. Branch-per-module was rejected — eight heads on one VM with one deploy, and cross-schema ordering (roles before any policy) stops being expressible in the chain. — **Reversibility:** one-way — restructuring a migration chain after it has run in any environment requires a hand-written reconciliation migration and a stamped history.

**Migration-carried guarantees**

- **D-05:** The three roles — `prope_app`, `prope_migrate`, `prope_report` — are created by an **idempotent DO block in Alembic migration 0001**, first in the chain, with no passwords baked in (set out-of-band from the `.env` per ADR-0032). `alembic upgrade head` against an empty cluster must yield a working database, because the testcontainers rig gets a pristine cluster every run and any second provisioning path would reintroduce the drift D-02 rejected. — **Reversibility:** costly — roles are cluster-level; moving their creation later means every environment and the test fixture change together.
- **D-06:** ADR-0045's coverage test is written to walk **all eight declared module schemas from day one**, asserting every table it finds carries `workspace_id` with RLS enabled and a policy (or appears in `GLOBAL_TABLES` with a written reason), and **reporting the declared schemas that do not yet exist** rather than silently passing over them. Scoping it to `ledger` and widening it per module was rejected: the "walks all eight" property would then be asserted nowhere, and a module that forgets to widen it is invisible — the precise failure ADR-0045 was written about ("the rule selecting for its own blind spot"). In Phase 1 no `ledger` table is global; all five carry `workspace_id`.
- **D-07:** T-006's privilege work lands in **Phase 1, with the live-engine test**, not deferred to Phase 3. Each table's creating migration carries its grants: `REVOKE ALL` from `PUBLIC` as the baseline, explicit `GRANT`s to `prope_app`, then `REVOKE UPDATE, DELETE ON ledger.price_table` and `REVOKE DELETE ON ledger.call_record` from `prope_app`; `call_body` keeps `DELETE` because the retention job must have it. A test asserts that an `UPDATE` and a `DELETE` against `ledger.price_table` as `prope_app` are refused **by the live engine**, in the manner property-history asserts its own privilege — not by mocking the driver. Rationale: Phase 1's goal says priced *irreversibly*, and CL-03/CL-05 rest on the price table being append-only; leaving it a convention for two phases is the defect ADR-0025 was written to fix for `history_event`. Phase 3 keeps its broader security surface (no-body-read-path, chaos). — **Reversibility:** one-way — a later REVOKE is blocked by whatever application code has come to depend on the privilege in the interim.
- **D-08:** Tenant context is plumbed through **one explicit async context manager**, `workspace_transaction(workspace_id)`, which opens the transaction, issues `SET LOCAL app.workspace_id`, and yields the session; repositories accept only a session obtained that way. Paired with a test asserting the same query outside it returns zero rows. An ambient-contextvar `after_begin` hook was rejected: it makes the tenant invisible in the writer's code, exactly where ADR-0040 needs it to be an explicit grouping key, and an unset contextvar fails as an empty result set rather than as an error. — **Reversibility:** costly — every repository signature in every module is written against this seam.

### Claude's Discretion

The user reviewed these and chose to leave them to the researcher and planner. They are open, not decided — resolve them from the lock file, ADR-0019, and the phase's success criteria, and state the resolution in the plan:

- **Pricing arithmetic and money representation.** NUMERIC precision and scale for `input_price_per_1k` / `output_price_per_1k` versus `cost`, and the rounding rule against a stated currency (the lock's `test_plan.unit` requires "cost arithmetic and rounding against a stated currency").
- **Effective-date boundary semantics.** A call whose `created_at` falls exactly on a row's `effective_from` (the lock names this case explicitly), and whether "a price row exists but its `effective_from` is later than the call" is `unpriced` on the same footing as "no price row at all". Both must obey ADR-0019's never-zero rule either way.
- **The Phase 1 write-path seam.** What is callable in Phase 1 to prove "priced correctly at write time" when `enqueue` and the drain arrive in Phase 2 — and whether the writer already updates `workspace_spend` inside its own transaction (A-103) or that waits for Phase 2.
- **Retention job shape and scheduling.** Bounded chunks per workspace inside that workspace's transaction is fixed by ADR-0040; open is whether Phase 1 ships a scheduler at all when the `worker` process is introduced in Phase 2, or ships the callable plus its integration test and leaves invocation to Phase 2.
- **Index strategy and column constraints.** Indexes serving the `expires_at` retention predicate and the effective-dated price lookup; the NOT NULL / CHECK constraints encoding `usage_status` (reported | unknown), `cost_status` (priced | unpriced | not_applicable), `source` (gateway | eval), `outcome`, and `version_id NOT NULL for source=gateway` — which the lock calls "a database constraint here, not a hope".
- **Whether `prope_report` receives read grants in Phase 1** or when its first consumer exists.

> Every one of these six is answered with a recommendation in this document — see `## Resolving Claude's Discretion`. Each recommendation states the evidence it rests on and is labelled RECOMMENDED, not decided.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

Noted but explicitly **not** deferred ideas (they are fixed ROADMAP boundaries, recorded so a planner does not mistake them for gaps): the enqueue seam, the broker drain, `check_spend_ceiling`, `get_run_totals` and the management routes belong to Phase 2; durability, idempotency, the no-body-read-path assertion and the load targets belong to Phase 3.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (verbatim, `.planning/REQUIREMENTS.md:24-32`) | Research Support |
|----|-------------|------------------|
| CL-03 | "A call is priced at the price row in force at the call's own timestamp, and a price row added later never changes it" | `## Pattern 2 — Effective-dated price resolution`; `## Pattern 3 — Freezing the price onto the row`; the `created_at`-has-no-default landmine |
| CL-04 | "A call for a provider and model with no price row stores its tokens with cost `unpriced` — never zero — and appears on the unpriced worklist" | `## Pattern 4 — The three cost states as a database constraint`; the partial index serving the worklist |
| CL-05 | "Repricing gives a previously unpriced call its cost and leaves an already-priced call untouched" | `## Pattern 5 — Repricing`; the partial index on `cost_status = 'unpriced'` is what makes it both correct and cheap |
| CL-08 | "Call bodies past their retention window are deleted while their call records stay intact" | `## Pattern 6 — The bounded-chunk retention delete`; grants (`call_body` keeps `DELETE` **and** needs `SELECT`); OQ-C on enumeration |
| CL-11 | "A call whose provider returned no usage object records unknown tokens as null — never zero — and the unknown count is reported alongside the total" | `## Pattern 4`; `usage_status='unknown'` ⇒ tokens NULL ⇒ `cost_status='not_applicable'`, enforced by CHECK |

The reporting half of CL-11 ("the unknown count is reported alongside the total") lands in `get_run_totals`, which the ROADMAP puts in **Phase 2**. Phase 1 owes the *storage* shape that makes it computable — a `cost_status` / `usage_status` encoding that can be counted without inspecting NULLs ambiguously.
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Actionable directives extracted from `./CLAUDE.md` and `./.claude/CLAUDE.md`. Treat these with the same authority as CONTEXT.md's locked decisions.

| # | Directive | Source | Bearing on Phase 1 |
|---|-----------|--------|--------------------|
| C-1 | Python 3.13.x pinned; FastAPI + uvicorn + pydantic v2 | ADR-0026 | The local machine has only 3.14 — see `## Environment Availability` |
| C-2 | PostgreSQL 17, one instance, one database, **schema per module**; roles `prope_app` / `prope_migrate` / `prope_report` | ADR-0027, ADR-0037 | Schema `ledger`; all DDL schema-qualified |
| C-3 | Tenant isolation via RLS, deny-by-default, `SET LOCAL app.workspace_id`; a missing filter returns **zero rows** | ADR-0035, ADR-0045 | Policy on all five tables; the "zero rows" property is a test, not a hope |
| C-4 | SQLAlchemy 2.0 async over asyncpg; **Alembic also carries RLS policies, constraints, extensions, triggers** | A-128 | Every guarantee is DDL, not application code |
| C-5 | History rows are never deleted at the database privilege level | ADR-0054, ADR-0025 | Does **not** reach `ledger` — no ledger table is a history table; `call_body` must keep `DELETE` |
| C-6 | call-ledger is a **sink**: forbidden edge call-ledger → anything; stored bodies have no read path in the MVP | ADR-0018, module map | No import of, and no FK to, any other module's schema |
| C-7 | Only four `SECURITY DEFINER` functions are sanctioned project-wide; none belongs to this module | ADR-0042, ADR-0049, ADR-0051 | Phase 1 must not create a fifth to solve the retention enumeration — see OQ-C |
| C-8 | Four non-negotiables (human approval, Approved-only release, split permissions, private-by-default) | `.claude/CLAUDE.md` | None is implemented by this phase; none may be weakened by it |
| C-9 | Do not edit `docs/modules/*.lock.yml`, `docs/architecture/*`, or any ADR. A spec that disagrees with the code is information — raise an `OQ-NNN` | `.planning/BSP-LINK.md:44-53` | The four open questions below are raised, not patched |
| C-10 | Do not write to a table outside the module's `data.owns[]` | BSP-LINK | Constrains where the retention-window setting can live — see OQ-B |
| C-11 | Interface language Vietnamese behind an i18n layer; statuses stay literal, API returns a machine `code` | ADR-0053 | `cost_status` / `usage_status` / `outcome` values stay literal ASCII in the database — do not translate them |
| C-12 | GSD workflow enforcement: no direct repo edits outside a GSD command | `.claude/CLAUDE.md` | Execution is through `/gsd-execute-phase` |

**Project skills:** `.claude/skills/` contains only the 18 `hyperresearch-*` research-pipeline skills. There is no Prope coding-convention skill and no `.agents/skills/` directory. Nothing in the skill set constrains this phase's implementation.

## Summary

Phase 1 is not "write five `CREATE TABLE` statements". Every success criterion in the ROADMAP is a *database* property, and the repo has already decided that the database — not the application — is where each one is enforced: the price table is append-only by `REVOKE` (ADR-0025's precedent, T-006's mitigation), tenancy is a policy that inverts a forgotten filter into zero rows (ADR-0035, ADR-0045), and "never zero" is a `CHECK` rather than a code path. The single most useful framing for the planner is the one CONTEXT.md already states: *the migration carries the guarantee, the application code is what the guarantee protects*. Correspondingly the highest-value tasks in this phase are the Alembic migration, the grant matrix, and the three live-engine tests — not the repository layer.

The mechanics are all well-documented and none of them is exotic, but four of them are the kind of detail that produces a subtly wrong implementation that passes a naive test. **`SET LOCAL` cannot take a bind parameter** — PostgreSQL's `SET` accepts only literals, so `SET LOCAL app.workspace_id = :ws` fails and the string-interpolated version is an injection vector; the correct parameterised form is `SELECT set_config('app.workspace_id', :ws, true)`. **`current_setting('app.workspace_id')` raises** on a connection where the GUC was never set, so the policy predicate must use the two-argument `current_setting('app.workspace_id', true)` form to get NULL — which is what turns a missing filter into zero rows rather than into an error. **Referential-integrity checks always bypass RLS**, so a foreign key is a documented covert channel across tenants. And **rounding a per-call cost to a currency's minor units produces zero** for realistic token prices, which would violate this phase's own success criterion 2 in the most literal way available.

Four things the repo has *not* decided came out of reading it against itself, and each is raised as an open question rather than resolved silently: the `workspace_id` column type (ADR-0035 and ADR-0045 both write the policy predicate with a `::uuid` cast while ADR-0003 and access-control's lock make every id a prefixed ULID — a `wsp_…` value is not a UUID); the per-workspace retention window has no column in any of the five owned tables; the retention job's cross-tenant workspace enumeration depends on `access.list_workspaces()`, which sits behind a forbidden module edge and does not exist until Phase 7; and ADR-0040's "bounded chunks inside that workspace's transaction" reads as one transaction per workspace, which defeats the purpose of chunking on a 500,000-row batch.

**Primary recommendation:** Build the migration first and the Python second. Write one Alembic revision per logical guarantee (0001 roles + schemas, 0002 `ledger` tables + constraints, 0003 RLS policies, 0004 grants and T-006 REVOKEs) so each guarantee is greppable in the diff; encode `usage_status` / `cost_status` / `source` / `outcome` as `text` + `CHECK` rather than native PostgreSQL `ENUM`; make every timestamp `timestamptz` and every money value `NUMERIC` with no rounding to minor units; pass `now` in as a parameter everywhere instead of calling `now()` in SQL, so AC-3 and AC-8 are testable without freezing a clock; and ship the retention job as a workspace-scoped callable with no scheduler and no enumerator, because the enumerator it is supposed to use does not exist yet.

## Architectural Responsibility Map

Prope is a two-tier system with a broker (ADR-0028, ADR-0033). Phase 1 touches only the two lowest tiers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tenant isolation | **Database (RLS policy)** | Application (`workspace_transaction()`) | ADR-0035: the policy is the enforcement; the app filter aids the planner and expresses intent, it is not the guarantee |
| Price-table immutability | **Database (privilege)** | — | ADR-0025's precedent; T-006's mitigation is a `REVOKE`, and ADR-0025 explicitly rejects both a trigger and a repository convention |
| "Never zero" cost/usage | **Database (CHECK constraint)** | Application (writer sets the status) | Success criterion 2 says "no row anywhere records a cost of zero" — *anywhere* is a table-level statement, so it is a table-level constraint |
| `version_id NOT NULL for source=gateway` | **Database (CHECK constraint)** | — | The lock: "a database constraint here, not a hope" (`call-ledger.lock.yml:162-164`) |
| Effective-dated price resolution | **Database (indexed query)** | Application (calls it once per batch) | ADR-0019 forbids a cache; the price table is read once per drain batch, a batch-scoped snapshot |
| Cost arithmetic | **Application (`decimal.Decimal`) or Database (`NUMERIC`)** | — | Either is exact; the choice is ergonomic. Never floating point |
| Retention deletion | **Application (chunk loop)** | Database (`DELETE` + index) | A-132: an ordinary table, chunked `DELETE`, no partitioning. The loop needs a commit per chunk, which SQL alone cannot do inside a function |
| Workspace enumeration for the sweep | **Database (`SECURITY DEFINER` returning ids)** | — | ADR-0051 — but the function lives in `access`, arriving Phase 7. See OQ-C |
| Monthly spend aggregate | **Database (upsert in the writer's transaction)** | — | A-103: an aggregate maintained by a separate job is wrong exactly when a ceiling is close |
| Migration ordering / role creation | **Database (Alembic chain)** | — | D-04, D-05 |
| HTTP surface (`/prices`, `/retention`, …) | **Not this phase** | — | ROADMAP puts all six management routes in Phase 2 |

## Standard Stack

Every library below is named by an in-repo spec — `docs/architecture/tech_stack.md:197-199`, `docs/modules/call-ledger.lock.yml:281-309`, or `docs/brainstorm/assumptions/A-128.md`. None was discovered by web search. Versions were verified against PyPI on 2026-08-09.

### Core

| Library | Version (verified 2026-08-09) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlalchemy` | 2.0.51 | ORM + Core, async mode | A-128 names it for all eight modules [VERIFIED: `docs/brainstorm/assumptions/A-128.md:14-15` — "All eight modules use SQLAlchemy 2.0 in async mode over asyncpg, with Alembic for migrations."] |
| `asyncpg` | 0.31.0 | PostgreSQL driver | A-128: "a sync driver would block the event loop the gateway's p95 budget depends on" |
| `greenlet` | 3.5.4 | SQLAlchemy async bridge | Hard runtime requirement of SQLAlchemy's asyncio extension; omitting it produces a confusing import-time failure. Not named in the repo — pin it explicitly [ASSUMED] |
| `alembic` | 1.19.1 | Migrations **and** RLS policies, grants, constraints, triggers | A-128: "Alembic is therefore load-bearing infrastructure here, not a convenience" |
| `pydantic` | 2.13.4 | Value objects; later the API models | ADR-0026 baseline |
| `python-ulid` | 4.0.1 | `cal_` and `prc_` identifiers | `call-ledger.lock.yml:297-298`; note the `cal_` id is generated by the **caller**, so Phase 1 generates only `prc_` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 9.1.1 | Test runner | Always |
| `pytest-asyncio` | 1.4.0 | async test support | Set `asyncio_mode = "auto"` in `pyproject.toml` |
| `testcontainers[postgresql]` | 4.15.0 | Real Postgres 17 per session | D-02. Requires a Docker daemon [VERIFIED: pypi.org/project/testcontainers — "Docker is required"] |
| `ruff` | 0.16.2 | Lint + format | Already in the repo (`ruff.toml`); bump `target-version` from `py311` to `py313` |
| `fastapi` | 0.141.1 | Management surface | Phase 2 needs it; D-03 says pin it in Phase 1's `pyproject.toml`, do not build routes |
| `uvicorn[standard]` | 0.52.1 | ASGI server | Same — pinned in Phase 1, used in Phase 2 |
| `pydantic-settings` | 2.15.0 | `.env` loading (ADR-0032) | Phase 1 needs a database URL from the environment |
| `structlog` | 26.1.0 | JSON logs | ADR-0030. Phase 1 need only configure it |
| `prometheus-client` | 0.26.0 | Metrics | ADR-0030. The 17 ledger metrics are **Phase 3** — do not build them here |

### Deliberately absent from Phase 1

| Library | Why not |
|---------|---------|
| `aio-pika` | The broker arrives in Phase 2 (ROADMAP); Phase 1 has no publisher and no consumer |
| `psycopg2` / `psycopg` | A-128 chooses asyncpg. The commented-out `psycopg2-binary` in `requirements.txt` is boilerplate. *Caveat:* if the plan chooses to run Alembic through a sync engine in tests, a sync driver is needed — the async `env.py` recipe avoids that entirely and is recommended |
| APScheduler / Celery / `schedule` | `tech_stack.md:585-586` — "a plain **`asyncio` task**… **no scheduler library enters the build for a third timer**" |
| `langchain`, `langgraph`, `langchain-openai` | A-127 removed them; ML stack is `n/a`. D-03 drops them |
| `httpx` | `tech_stack.md:504` — "**No `httpx`** — every upstream call in Prope is issued by provider-access". Note: the existing `requirements.txt` pins it; drop it |
| `mypy` | The current `Makefile` `typecheck` target calls it and it is not in the dependency set. Either add it or drop the target — do not leave a broken target for 24 phases |
| `freezegun` / `time-machine` | Not needed if `now` is a parameter — see `## Pattern 7` |

**Installation** (D-03 replaces `requirements.txt` with `pyproject.toml`; `uv` is present on this machine):

```bash
uv python install 3.13            # the pin is 3.13.x; only 3.14 is installed locally
uv venv --python 3.13
uv pip install "sqlalchemy[asyncio]==2.0.51" "asyncpg==0.31.0" "alembic==1.19.1" \
  "pydantic==2.13.4" "pydantic-settings==2.15.0" "python-ulid==4.0.1" \
  "fastapi==0.141.1" "uvicorn[standard]==0.52.1" "structlog==26.1.0" "prometheus-client==0.26.0"
uv pip install --group dev "pytest==9.1.1" "pytest-asyncio==1.4.0" \
  "testcontainers[postgresql]==4.15.0" "ruff==0.16.2"
```

## Package Legitimacy Audit

Run 2026-08-09 via `gsd-tools query package-legitimacy check --ecosystem pypi`, cross-checked with `pip index versions`.

| Package | Registry | Latest release | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `sqlalchemy` | PyPI | 2026-06-15 | n/a | sqlalchemy.org | [SUS] | **Approved** — named by A-128 |
| `alembic` | PyPI | 2026-08-08 | n/a | github.com/sqlalchemy/alembic | [SUS] | **Approved** — named by A-128 |
| `asyncpg` | PyPI | 2025-11-24 | n/a | none in metadata | [SUS] | **Approved** — named by A-128 |
| `greenlet` | PyPI | 2026-07-22 | n/a | greenlet.readthedocs.io | [SUS] | **Approved** — transitive requirement of SQLAlchemy asyncio |
| `pydantic` | PyPI | 2026-05-06 | n/a | github.com/pydantic/pydantic | [SUS] | **Approved** — ADR-0026 |
| `pydantic-settings` | PyPI | 2026-08-07 | n/a | github.com/pydantic/pydantic-settings | [SUS] | **Approved** |
| `fastapi` | PyPI | 2026-07-29 | n/a | github.com/fastapi/fastapi | [SUS] | **Approved** — ADR-0026 |
| `uvicorn` | PyPI | 2026-08-01 | n/a | github.com/Kludex/uvicorn | [SUS] | **Approved** — ADR-0026 |
| `python-ulid` | PyPI | 2026-07-20 | n/a | github.com/mdomke/python-ulid | [SUS] | **Approved** — `call-ledger.lock.yml:297` |
| `structlog` | PyPI | 2026-06-06 | n/a | none in metadata | [SUS] | **Approved** — ADR-0030 |
| `prometheus-client` | PyPI | 2026-07-24 | n/a | github.com/prometheus/client_python | [SUS] | **Approved** — ADR-0030 |
| `pytest` | PyPI | 2026-06-19 | n/a | github.com/pytest-dev/pytest | [SUS] | **Approved** |
| `pytest-asyncio` | PyPI | 2026-05-26 | n/a | github.com/pytest-dev/pytest-asyncio | [SUS] | **Approved** |
| `testcontainers` | PyPI | 2026-07-24 | n/a | github.com/testcontainers/testcontainers-python | [SUS] | **Approved** — D-02 |
| `ruff` | PyPI | 2026-08-07 | n/a | docs.astral.sh/ruff | [SUS] | **Approved** — already in repo |

**Reading the verdicts honestly.** *Every* package returned `SUS`, including `pytest` and `ruff`. The reasons were uniformly `unknown-downloads` (PyPI's JSON API does not expose download counts, so the heuristic has nothing to read) and `too-new` (the heuristic reads *latest release date*, not package age — an actively maintained package releases recently by definition). No package returned `SLOP`; every one exists on PyPI, every one resolves to a well-known source, and **every one is named by an in-repo specification rather than discovered by search**, which is the provenance that actually matters here. No `postinstall`-equivalent risk applies on PyPI in the way it does on npm, but note that `asyncpg` and `greenlet` build C extensions — wheels exist for CPython 3.13 on all three platforms.

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS] requiring a human checkpoint:** none — the verdict is a known artefact of PyPI metadata, documented above. A planner should *not* insert 15 `checkpoint:human-verify` tasks on this basis.

## Architecture Patterns

### System Architecture Diagram

Phase 1 builds only the boxes drawn in **bold**. Everything else is shown so the shape of what Phase 1 must serve is legible.

```
                    ┌──────────────────────── Phase 2 / 3 ────────────────────────┐
  gateway ─────────▶│  enqueue()  ──▶  RabbitMQ prope.call_record  ──▶  drain     │
  (Phase 19-21)     │      │                                             │        │
                    │      └── failed confirm ──▶ direct inline write ───┤        │
  evaluation ──────▶│  price_usage(run_id, usage_rows)  ─────────────────┤        │
  (Phase 16-18)     └───────────────────────────────────────────────────┬┴────────┘
                                                                        │
                                             ┌──────────────────────────▼─────────────────────────┐
                                             │  ★ workspace_transaction(workspace_id)             │
                                             │    BEGIN → set_config('app.workspace_id', ws, true)│
                                             └──────────────────────────┬─────────────────────────┘
                                                                        │
       ┌────────────────────────────────────────────────────────────────▼──────────────────┐
       │  ★ WRITER  (src/prope/call_ledger/writer.py)  — the Phase 1 callable seam          │
       │                                                                                   │
       │   for each record:                                                                │
       │     ├─ resolve price: row in force at record.created_at  ──────┐                  │
       │     │        hit ──▶ cost = f(tokens, price)  ──▶ cost_status = priced            │
       │     │        miss ─▶ cost = NULL             ──▶ cost_status = unpriced           │
       │     │   usage missing ─▶ tokens NULL          ──▶ cost_status = not_applicable    │
       │     ├─ stamp expires_at = created_at + retention_window   (bodies only)           │
       │     └─ upsert workspace_spend (workspace_id, period_month)                        │
       └───────┬───────────────┬─────────────────┬─────────────────┬────────────┬──────────┘
               │               │                 │                 │            │
        ┌──────▼─────┐  ┌──────▼─────┐  ┌────────▼────────┐ ┌──────▼──────┐ ┌───▼──────────┐
        │★call_record│  │★ call_body │  │ ★ price_table   │ │★ workspace_ │ │★spend_ceiling│
        │            │  │            │  │  append-only    │ │   spend     │ │              │
        │ SELECT     │  │ SELECT     │  │  SELECT/INSERT  │ │ SELECT/INS/ │ │ SELECT/INS/  │
        │ INSERT     │  │ INSERT     │  │  ── no UPDATE   │ │ UPDATE      │ │ UPDATE       │
        │ UPDATE     │  │ DELETE     │  │  ── no DELETE   │ │             │ │              │
        │ ── no DEL  │  │            │  │                 │ │             │ │              │
        └────────────┘  └──────▲─────┘  └─────────────────┘ └─────────────┘ └──────────────┘
                               │
                     ┌─────────┴────────────────────────────────┐
                     │ ★ delete_expired_bodies(workspace_id, …) │
                     │   loop: DELETE … WHERE ctid IN (         │
                     │           SELECT ctid … expires_at <= T  │
                     │           LIMIT chunk)  ── commit ── repeat
                     └──────────────────────────────────────────┘
                                  ▲
                                  │ (enumeration of workspaces — NOT Phase 1, see OQ-C)
                          access.list_workspaces()   [Phase 7]

  ═══ every arrow into a table crosses the RLS policy ═══
      USING / WITH CHECK: workspace_id = current_setting('app.workspace_id', true)
      unset ⇒ NULL ⇒ predicate never true ⇒ ZERO ROWS
```

### Component Responsibilities

| Component | File (proposed, per D-01) | Responsibility |
|-----------|---------------------------|----------------|
| Migration chain | `alembic/versions/*.py` | Roles, schemas, tables, CHECKs, indexes, RLS policies, grants/REVOKEs. **Every Phase 1 guarantee lives here** |
| Migration helpers | `alembic/ddl.py` | `enable_tenant_rls(schema, table)`, `grant(...)` — so five tables do not repeat forty lines of SQL |
| Tenant seam | `src/prope/db/session.py` | `workspace_transaction(workspace_id)`, engine/sessionmaker construction |
| Domain values | `src/prope/call_ledger/domain.py` | `CostStatus`, `UsageStatus`, `Source`, `Outcome` as `StrEnum`; `CallRecordDraft` |
| Pricing | `src/prope/call_ledger/pricing.py` | `resolve_price(session, ...) -> PriceRow | None`; `compute_cost(tokens, price) -> Decimal` |
| Writer | `src/prope/call_ledger/writer.py` | The Phase 1 callable seam — price, stamp, insert, aggregate |
| Repricing | `src/prope/call_ledger/repricing.py` | CL-05: fills only `cost_status='unpriced'` rows |
| Retention | `src/prope/call_ledger/retention.py` | `delete_expired_bodies(...)` chunk loop |
| Models | `src/prope/call_ledger/models.py` | SQLAlchemy declarative tables under `MetaData(schema="ledger")` — *for the app to query*, never the source of truth for DDL |
| RLS coverage test | `tests/architecture/test_tenant_coverage.py` | D-06 — walks all eight declared schemas |
| Privilege test | `tests/security/test_append_only_privilege.py` | D-07 — T-006 asserted against the live engine |

### Recommended project structure

```
pyproject.toml               # D-03: the real stack, Python 3.13.x
alembic.ini
alembic/
├── env.py                   # async recipe: async_engine_from_config + run_sync
├── ddl.py                   # reusable RLS / grant emitters
└── versions/
    ├── 0001_roles_and_schemas.py
    ├── 0002_ledger_tables.py        # tables + CHECKs + indexes
    ├── 0003_ledger_rls.py           # ENABLE RLS + policies
    └── 0004_ledger_grants.py        # REVOKE ALL, GRANTs, T-006 REVOKEs
src/prope/
├── __init__.py
├── db/
│   ├── engine.py
│   ├── session.py           # workspace_transaction()
│   └── metadata.py          # shared MetaData + naming convention
└── call_ledger/
    ├── domain.py  pricing.py  writer.py  repricing.py  retention.py  models.py
tests/
├── conftest.py              # testcontainers session fixture, three role engines
├── unit/                    # AC-3, AC-4, AC-11 (still against the live engine)
├── integration/             # AC-5, AC-8
├── security/                # T-006 privilege, RLS zero-rows
└── architecture/            # ADR-0045 coverage walk
```

---

### Pattern 1 — The five tables

**What:** DDL derived strictly from `data.owns`. The field lists below are quoted **verbatim** from the lock file; column *types* are the research recommendation, since the lock declares names and semantics but not types.

`call_record` [VERIFIED: `docs/modules/call-ledger.lock.yml:141-145`]:
> `fields: call_id, workspace_id, source, prompt_id, version_id, revision_number, run_id, case_id, consumer_key_id, actor_id, provider_config_id, upstream_model, outcome, pinned, fallback, streaming, input_tokens, output_tokens, usage_status, cost, currency, price_row_id, cost_status, added_latency_ms, upstream_duration_ms, error_class, created_at, written_at`

`call_body` [VERIFIED: `docs/modules/call-ledger.lock.yml:177`]:
> `fields: call_id, workspace_id, request_body, response_body, byte_size, expires_at, created_at`

`price_table` [VERIFIED: `docs/modules/call-ledger.lock.yml:200-201`]:
> `fields: price_row_id, workspace_id, provider_config_id, upstream_model, input_price_per_1k, output_price_per_1k, currency, effective_from, created_by, created_at`

`workspace_spend` [VERIFIED: `docs/modules/call-ledger.lock.yml:215`]:
> `fields: workspace_id, period_month, currency, total_cost, call_count, updated_at`

`spend_ceiling` [VERIFIED: `docs/modules/call-ledger.lock.yml:221`]:
> `fields: workspace_id, monthly_limit, per_run_limit, currency, enabled, updated_by, updated_at`

The value vocabularies, also verbatim [VERIFIED: `docs/modules/call-ledger.lock.yml:157, 161-164, 166`]:
> "`source` is gateway | eval — one table, so there is one price path, one spend total, and one answer to 'what did this workspace spend' (A-098)."
> "`usage_status` is reported | unknown and `cost_status` is priced | unpriced | not_applicable. Both exist so a gap is a value rather than a zero. `version_id` is NOT NULL for source=gateway — the '100% of calls record a version ID' success metric is a database constraint here, not a hope."
> "`outcome` is ok | fallback | truncated | caller_error | upstream_error (ADR-0013)."

And the removed column, so nobody reinstates it [VERIFIED: `docs/modules/call-ledger.lock.yml:169`]:
> "`stale_resolution` IS REMOVED from the field list, 2026-08-09 (step 6, pass 1)."

**Type recommendations** (these are research judgement, not repo decisions):

| Column group | Type | Why |
|---|---|---|
| all `*_id` values | `text` (see OQ-A) | ADR-0003 ids are prefixed ULIDs — `cal_01J…`, `prc_01J…`, `wsp_01J…`. Not UUIDs |
| `created_at`, `written_at`, `expires_at`, `effective_from`, `updated_at` | `timestamptz` | A-003 — RFC 3339 UTC everywhere, storage included |
| `period_month` | `date` (first day of month, UTC) | Sortable, comparable, indexable; `YYYY-MM` text is none of those |
| `input_tokens`, `output_tokens`, `call_count`, `byte_size` | `bigint` | `call_count` is unbounded over the life of a workspace |
| `added_latency_ms`, `upstream_duration_ms` | `integer` | |
| `input_price_per_1k`, `output_price_per_1k`, `monthly_limit`, `per_run_limit` | `numeric(20,10)` | See `## Resolving Claude's Discretion` → money |
| `cost`, `total_cost` | `numeric(20,10)` | Same scale as prices so the arithmetic never widens |
| `currency` | `char(3)` or `text` + `CHECK (currency ~ '^[A-Z]{3}$')` | A-107 — explicit currency, no conversion |
| `source`, `outcome`, `usage_status`, `cost_status` | `text` + `CHECK (… IN (…))` | **Not** a native `ENUM` — see `## Pitfall 4` |
| `pinned`, `fallback`, `streaming`, `enabled` | `boolean NOT NULL` | |
| `request_body`, `response_body` | `text` | They are provider payloads. `jsonb` would reject a malformed body — and a malformed body is exactly the one worth keeping. No index is needed because nothing reads them (ADR-0018) |

**Keys and constraints:**

- `call_record` PK `(call_id)`. This is what A-099's upsert targets, and A-132 records that it is why `call_record` cannot be partitioned.
- `call_body` PK `(call_id)`, FK → `call_record(call_id)` **within the same schema only**. Deleting a body must not touch the record: no `ON DELETE CASCADE` in the body→record direction is needed, and none in the reverse direction should exist.
- `price_table` PK `(price_row_id)`, plus `UNIQUE (workspace_id, provider_config_id, upstream_model, effective_from)` — see `## Pattern 2` for why this is load-bearing rather than hygienic.
- `workspace_spend` PK `(workspace_id, period_month)` — this is what makes A-103's upsert a single `ON CONFLICT` statement.
- `spend_ceiling` PK `(workspace_id)`.
- **No foreign key leaves the `ledger` schema.** Not to `access.workspace`, not to `provider.provider_config`, not to `registry.revision`. `workspace_id`, `provider_config_id`, `prompt_id`, `version_id` are **values, not references** — the lock says so directly [VERIFIED: `docs/modules/call-ledger.lock.yml:445-447` — "A call record is denormalised on purpose — prompt_id, version_id, revision_number, and upstream_model are values, not references — so the audit trail survives independently of the registry's current state."]. Beyond the module-boundary argument, PostgreSQL documents that referential-integrity checks *always bypass row security*, so a cross-tenant FK would be a covert channel [VERIFIED: postgresql.org/docs/17/ddl-rowsecurity.html].
- **`price_row_id` on `call_record` may be an FK to `ledger.price_table`** — same schema, same module, and it makes "why is this number this number" enforceable. Recommended, with `ON DELETE` omitted entirely: `price_table` has no `DELETE` grant, so the case cannot arise.

**Indexes** (all leading with `workspace_id`, as ADR-0035 observes every declared index in Prope already does):

| Index | Serves |
|---|---|
| `price_table (workspace_id, provider_config_id, upstream_model, effective_from DESC)` — the UNIQUE constraint above, declared in this order | The effective-dated lookup as a backward index scan terminating on the first row |
| `call_body (workspace_id, expires_at)` | The retention predicate. ADR-0040: "a per-workspace predicate that uses an index rather than a join" |
| `call_record (workspace_id, provider_config_id, upstream_model) WHERE cost_status = 'unpriced'` | **Both** the unpriced worklist (CL-04) and the repricing scan (CL-05). A partial index over a status that is rare by design is close to free |
| `call_record (workspace_id, created_at DESC)` | Ordinary listing; also the month attribution |
| `call_record (workspace_id, run_id) WHERE run_id IS NOT NULL` | `get_run_totals` in Phase 2 — cheap to add now, awkward to add on a large table later |
| `call_body (workspace_id, created_at)` | `oldest_body_age_seconds` (Phase 3), if the gauge is computed as a `MIN` |

---

### Pattern 2 — Effective-dated price resolution

**What:** "The price row in force at timestamp T" over an append-only table with no end-date column.

**When to use:** Every write. ADR-0019 forbids a cache; the price table is read once per drain batch.

**Half-open interval `[effective_from, next.effective_from)`.** A row is in force from its `effective_from` inclusive until the next row's `effective_from` exclusive. That makes the boundary case the lock names explicitly — a call whose timestamp lands exactly on an `effective_from` — resolve to the **new** row, which is what "effective from" means in every other domain that uses the phrase, and it makes the intervals a partition of the timeline with no gap and no overlap.

Single-row form (AC-3's shape):

```sql
SELECT price_row_id, input_price_per_1k, output_price_per_1k, currency
FROM   ledger.price_table
WHERE  workspace_id        = $1
  AND  provider_config_id  = $2
  AND  upstream_model      = $3
  AND  effective_from     <= $4          -- $4 = the CALL's own created_at, never now()
ORDER  BY effective_from DESC
LIMIT  1;
```

With the composite UNIQUE/index above this is a backward index scan that stops at the first matching entry: no sort, no filter, one heap fetch.

Batch form, for the Phase 2 drain resolving many records against one snapshot:

```sql
SELECT DISTINCT ON (c.call_id) c.call_id, p.price_row_id, p.input_price_per_1k, p.output_price_per_1k, p.currency
FROM   unnest($1::text[], $2::text[], $3::timestamptz[]) AS c(call_id, key, at)
LEFT   JOIN LATERAL (
         SELECT * FROM ledger.price_table p
         WHERE  p.workspace_id = $4 AND (p.provider_config_id || '|' || p.upstream_model) = c.key
           AND  p.effective_from <= c.at
         ORDER  BY p.effective_from DESC LIMIT 1
       ) p ON true;
```

**Ties are made impossible rather than broken.** Two rows sharing `(workspace, provider_config, model, effective_from)` would make `ORDER BY effective_from DESC LIMIT 1` non-deterministic — and non-determinism in a number that ends up on an approval record is exactly what ADR-0019 exists to prevent. The `UNIQUE` constraint refuses the second row at insert time. This costs the ability to enter two prices for the same instant, which is not a capability anyone wants: a typo is corrected by superseding it with a later `effective_from`, which ADR-0019 states directly.

**`effective_from` must be allowed to be in the past.** Nothing in the spec says a price row's effective date must be ≥ now, and CL-05 depends on it not being so: adding a price row *after* calls have accrued is precisely AC-5's scenario, and repricing them requires the new row's `effective_from` to predate those calls. Do **not** add a `CHECK (effective_from >= now())`.

---

### Pattern 3 — Freezing the price onto the row

**What:** Storing `cost`, `currency` and `price_row_id` on `call_record` so a later price row cannot move an existing figure.

ADR-0019 is unambiguous [VERIFIED: `docs/adr/0019-cost-is-priced-once-at-write-time.md:27-30`]:
> "The writer computes cost when it persists the record, using the price row in force at the **call's own `created_at`** — not at wall-clock write time, which differs after a spill replay or a backlog. The resulting `cost`, `currency`, and the `price_row_id` that produced it are stored on the record."

The mechanism that makes "a day-20 price does not move it" true is **not** a constraint. It is the absence of any code path that recomputes. Three things protect it:

1. **`call_record.created_at` has no `DEFAULT now()` and is `NOT NULL`.** The caller supplies it. A default would silently price a backlogged record at drain time, and AC-3 — made on day 5, written on day 12 — would pass on a fast machine and fail under load. `written_at` gets `DEFAULT now()`; `created_at` never does. This is the single easiest way to get CL-03 subtly wrong.
2. **Repricing is filtered to `cost_status = 'unpriced'`** — see Pattern 5.
3. **`price_table` cannot be edited** — T-006's `REVOKE`, D-07.

There is no fourth mechanism and no trigger. ADR-0025 explicitly rejects triggers as an enforcement device ("a trigger is owned by the same role that owns the table, so the actor it is meant to stop can drop it").

---

### Pattern 4 — The three cost states as a database constraint

**What:** Making "no row anywhere records a cost of zero" (ROADMAP success criterion 2) an expression the engine checks.

The three states and their exact obligations, from ADR-0019 and AC-4 / AC-11:

| `cost_status` | `usage_status` | tokens | `cost` | `currency` | `price_row_id` |
|---|---|---|---|---|---|
| `priced` | `reported` | NOT NULL | NOT NULL, **> 0** | NOT NULL | NOT NULL |
| `unpriced` | `reported` | NOT NULL | **NULL** | NULL | NULL |
| `not_applicable` | `unknown` | **NULL** | **NULL** | NULL | NULL |

The constraints (recommended; the encoding is a discretion item, the *never-zero* property is not):

```sql
CONSTRAINT usage_status_values  CHECK (usage_status IN ('reported','unknown')),
CONSTRAINT cost_status_values   CHECK (cost_status  IN ('priced','unpriced','not_applicable')),
CONSTRAINT source_values        CHECK (source       IN ('gateway','eval')),
CONSTRAINT outcome_values       CHECK (outcome IN ('ok','fallback','truncated','caller_error','upstream_error')),

-- the literal expression of success criterion 2
CONSTRAINT cost_is_never_zero   CHECK (cost IS NULL OR cost > 0),

-- unknown usage means NULL tokens, never zeros  (CL-11 / AC-11)
CONSTRAINT unknown_usage_is_null CHECK (
  (usage_status = 'unknown'  AND input_tokens IS NULL     AND output_tokens IS NULL)
  OR
  (usage_status = 'reported' AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL)
),

-- each cost state carries exactly its own fields  (CL-04 / AC-4, AC-11)
CONSTRAINT cost_state_is_coherent CHECK (
  (cost_status = 'priced'         AND cost IS NOT NULL AND currency IS NOT NULL
                                  AND price_row_id IS NOT NULL AND usage_status = 'reported')
  OR
  (cost_status = 'unpriced'       AND cost IS NULL AND currency IS NULL
                                  AND price_row_id IS NULL AND usage_status = 'reported')
  OR
  (cost_status = 'not_applicable' AND cost IS NULL AND currency IS NULL
                                  AND price_row_id IS NULL AND usage_status = 'unknown')
),

-- "a database constraint here, not a hope"  (lock file line 162-164)
CONSTRAINT gateway_calls_carry_version_id CHECK (
  source <> 'gateway' OR version_id IS NOT NULL
),

-- source=eval carries run_id and case_id and no consumer key  (lock file line 158-159)
CONSTRAINT eval_calls_carry_run CHECK (
  source <> 'eval' OR (run_id IS NOT NULL AND case_id IS NOT NULL AND consumer_key_id IS NULL)
)
```

**The unpriced worklist** (`GET /api/v1/prices/unpriced`, Phase 2) is a projection over this encoding, not a separate table:

```sql
SELECT provider_config_id, upstream_model, count(*) AS unpriced_calls, min(created_at) AS since
FROM   ledger.call_record
WHERE  cost_status = 'unpriced'
GROUP  BY provider_config_id, upstream_model;
```
served by the partial index. Phase 1 owes the encoding and the index; Phase 2 owes the route. Phase 1's own test for CL-04 should assert the query returns the pair — proving the worklist is derivable — without building the endpoint.

---

### Pattern 5 — Repricing (CL-05 / AC-5)

**What:** Adding a price row later gives previously-unpriced calls a cost and leaves priced calls alone.

ADR-0019: "**Repricing fills only previously-unpriced rows.** A row that already has a cost is never recomputed — that is the rule that makes history stable."

```sql
UPDATE ledger.call_record c
SET    cost         = <computed>,
       currency     = p.currency,
       price_row_id = p.price_row_id,
       cost_status  = 'priced'
FROM   <resolved price p for c.created_at>
WHERE  c.workspace_id = current_setting('app.workspace_id', true)
  AND  c.cost_status  = 'unpriced'          -- ← the entire guarantee is this line
  AND  ...;
```

Three properties worth asserting separately in the test, because a single "reprice and check" test can pass while two of them are broken:

1. A previously-unpriced call gains a cost.
2. A call already priced under a **superseded** row is byte-identical afterwards — same `cost`, same `price_row_id`. (Fetch the row before and after and compare the whole tuple, not just `cost`.)
3. A row that was `not_applicable` (unknown usage) is **still** `not_applicable`. It has no tokens; there is nothing to price. The `cost_status = 'unpriced'` filter already excludes it, but asserting it stops a later "improvement" that widens the filter to `cost IS NULL`.

`call_record` retains its `UPDATE` grant precisely for this and for the A-099 upsert; `DELETE` is revoked (D-07).

---

### Pattern 6 — The bounded-chunk retention delete (CL-08 / AC-8)

**What:** Deleting expired bodies without holding a long transaction, without an unbounded `DELETE`, and without partitioning (A-132 forbids the last of those for now).

```sql
-- one chunk, one transaction
WITH victims AS (
  SELECT ctid
  FROM   ledger.call_body
  WHERE  workspace_id = current_setting('app.workspace_id', true)
    AND  expires_at  <= $1                 -- $1 is PASSED IN, not now()
  ORDER  BY expires_at
  LIMIT  $2                                -- chunk size, e.g. 5_000
  FOR UPDATE SKIP LOCKED
)
DELETE FROM ledger.call_body b
USING victims v
WHERE b.ctid = v.ctid;
```

Loop in Python until the affected row count is less than the chunk size, or until a `max_chunks` guard trips.

Notes that matter:

- **`ctid` is safe here only because the subselect is re-run every iteration.** Caching ctids across iterations is not safe.
- **A chunked `DELETE` returns space to the table's free list, not to the disk.** A-132 states this and accepts it, with a disk-usage alert beside the oldest-body gauge. Do not "fix" it with `VACUUM FULL` — that takes an exclusive lock on the largest table in the system.
- **`FOR UPDATE SKIP LOCKED`** makes the job safe to run concurrently with itself and with the writer; the lock's chaos plan runs the deletion job during peak writes.
- **`prope_app` needs `SELECT` on `call_body`**, not only `DELETE`. A `DELETE … WHERE expires_at <= …` reads a column, and PostgreSQL requires `SELECT` privilege on every column a statement references. Revoking `SELECT` on `call_body` in the name of "no read path" would break the retention job. **The no-read-path guarantee (AC-10, Phase 3) is a property of the route table, not of the grant matrix** — ADR-0018 says "no endpoint, no export, no admin viewer, no debug route, and no join from another module's query", and asserts it "as a test against the route table itself".
- The target is "one day's expired bodies removed within 10 min … up to 500,000 body rows in a batch, deleted in bounded chunks" [VERIFIED: `docs/modules/call-ledger.lock.yml:337-341`]. At 5,000 rows per chunk that is 100 chunks, which is comfortable.

---

### Pattern 7 — `now` is a parameter, never a call

**What:** Every function that compares against the present takes the present as an argument.

```python
async def delete_expired_bodies(session, workspace_id: str, *, now: datetime, chunk: int = 5000) -> int: ...
async def price_record(session, draft: CallRecordDraft) -> PricedRecord: ...   # uses draft.created_at
```

This is the cheapest correctness decision in the phase and it removes an entire category of test infrastructure. AC-3 ("made on day 5, written on day 12, a day-20 price is added") and AC-8 ("bodies written 31 days ago with a 30-day window") both become plain arithmetic on `datetime` values with no clock to freeze. `freezegun` cannot patch the *server's* `now()` anyway, so a design that calls `now()` inside SQL is not testable without inserting rows with hand-computed timestamps — which is the same work with more moving parts.

Corollary: `DEFAULT now()` is acceptable only on `written_at` and `updated_at`, where the value is genuinely "when the database saw this".

---

### Pattern 8 — RLS: deny-by-default with `USING` and `WITH CHECK`

Per table, in migration 0003:

```sql
ALTER TABLE ledger.call_record ENABLE ROW LEVEL SECURITY;

CREATE POLICY call_record_tenant ON ledger.call_record
  FOR ALL TO prope_app
  USING      (workspace_id = current_setting('app.workspace_id', true))
  WITH CHECK (workspace_id = current_setting('app.workspace_id', true));
```

Why each token is what it is:

| Token | Reason |
|---|---|
| `ENABLE`, not `FORCE` | ADR-0035 depends on owner bypass: "`prope_migrate` owns every table and `prope_app` owns none, so the runtime role is subject to policy and the migration role is not, with no additional grant machinery." `FORCE ROW LEVEL SECURITY` would subject `prope_migrate` to the policy and break migrations, backfills and the test rig's setup path. **Do not add it.** [VERIFIED: postgresql.org/docs/17/ddl-rowsecurity.html — "Table owners normally bypass row security as well, though a table owner can choose to be subject to row security with ALTER TABLE ... FORCE ROW LEVEL SECURITY."] |
| `TO prope_app` | Scopes the policy to the runtime role. Any other non-owner, non-`BYPASSRLS` role gets the default-deny that `ENABLE` with no applicable policy produces [VERIFIED: postgresql.org/docs/17/ddl-rowsecurity.html — "If no policy exists for the table, a default-deny policy is used, meaning that no rows are visible or can be modified."] |
| `FOR ALL` | One policy covering SELECT/INSERT/UPDATE/DELETE. Splitting into four policies is four places to forget `WITH CHECK` |
| explicit `WITH CHECK` | It defaults to the `USING` expression when omitted, but ADR-0040 makes it the load-bearing half here: "A call record's `workspace_id` is supplied by a caller that denormalised it from somewhere else; a mis-stamped one is the realistic cross-tenant leak in this module, and `WITH CHECK` is what makes it a refused insert rather than another workspace's traffic in someone's spend total." Write it out |
| **`current_setting(…, true)`** — two arguments | The one-argument form **raises** when the GUC has never been set on the connection [VERIFIED: postgresql.org/docs/17/functions-admin.html — "`current_setting` throws an error unless *missing_ok* is supplied and is `true` (in which case NULL is returned)"]. NULL makes the predicate NULL, which is not true, which yields zero rows — the exact inversion ADR-0035 is built on. **This detail is the difference between "returns zero rows" and "raises `unrecognized configuration parameter`".** |

`prope_report` bypasses all of this by role attribute (`BYPASSRLS`, ADR-0037) and needs no policy.

**A subtlety the "zero rows" test must cover.** Once `set_config('app.workspace_id', …, true)` has run in *any* transaction on a connection, the GUC placeholder exists on that session; at transaction end the transaction-local value reverts to the session value, which for a never-`SET` custom GUC is the empty string. So on a **reused** connection a forgotten `SET LOCAL` yields `''` — no row matches, zero rows. On a **pristine** connection it yields NULL — also zero rows, but by a different route. Assert both, because a test that only exercises a reused pooled connection does not prove the pristine path, and vice versa.

---

### Pattern 9 — `workspace_transaction()` (D-08)

```python
@asynccontextmanager
async def workspace_transaction(sessionmaker, workspace_id: str) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        async with session.begin():                       # a real transaction, first
            await session.execute(
                text("SELECT set_config('app.workspace_id', :ws, true)"),
                {"ws": workspace_id},
            )
            yield session
```

Three non-obvious requirements:

1. **`set_config(…, true)`, not `SET LOCAL`.** PostgreSQL's `SET` takes "string constants, identifiers, numbers, or comma-separated lists of these" — **not bind parameters** [VERIFIED: postgresql.org/docs/17/sql-set.html]. `text("SET LOCAL app.workspace_id = :ws")` will not bind, and the f-string version is an injection site on a value that arrives from a message payload. `set_config` is an ordinary function call and parameterises normally. Its third argument `true` means "only during the current transaction" [VERIFIED: postgresql.org/docs/17/functions-admin.html].
2. **The transaction must already be open.** `SET LOCAL` "issued outside of a transaction block emits a warning and otherwise has no effect" [VERIFIED: postgresql.org/docs/17/sql-set.html]; `set_config(…, true)` behaves the same way. Open the transaction, then set the variable — never the reverse. This is why the context manager owns both.
3. **One workspace per transaction.** ADR-0040 is explicit that the drain "groups each batch by `workspace_id` and opens one transaction per workspace". Do not add a `set_workspace()` method that can be called twice inside one transaction — make the workspace an argument of the transaction's constructor, which is what D-08 chose.

---

### Pattern 10 — Alembic as the guarantee carrier (D-04, C-4)

**Chain shape.** One linear history. Recommended split — one revision per *kind* of guarantee, so a reviewer reading the diff sees each one:

| Revision | Contents |
|---|---|
| `0001_roles_and_schemas` | Idempotent `DO` block creating `prope_migrate`, `prope_app`, `prope_report` (D-05); `CREATE SCHEMA ledger AUTHORIZATION prope_migrate`; `REVOKE ALL ON SCHEMA public FROM PUBLIC` |
| `0002_ledger_tables` | The five tables, every `CHECK`, every index |
| `0003_ledger_rls` | `ENABLE ROW LEVEL SECURITY` + one policy per table |
| `0004_ledger_grants` | `REVOKE ALL … FROM PUBLIC`; `GRANT USAGE ON SCHEMA`; per-table `GRANT`s; T-006's `REVOKE`s; `prope_report` reads |

**Role creation is transactional.** `CREATE ROLE` runs inside a transaction block in PostgreSQL (unlike `CREATE DATABASE`), so migration 0001 needs no `autocommit_block`. Idempotent form:

```python
op.execute("""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prope_migrate') THEN
    CREATE ROLE prope_migrate LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prope_app') THEN
    CREATE ROLE prope_app LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prope_report') THEN
    CREATE ROLE prope_report LOGIN BYPASSRLS;
  END IF;
END $$;
""")
```

No passwords (ADR-0032 — the `.env` holds them, out of band). `prope_report` gets `BYPASSRLS` here because ADR-0037 defines the role by that attribute; granting `BYPASSRLS` requires a superuser, which the migration connection is in the test container and which the deploy must also be for this one statement — worth naming in the plan.

**`alembic_version` needs a home outside the eight module schemas.** With `include_schemas=True` and schema-per-module, the version table would otherwise land wherever `search_path` points. Put it in `public` explicitly:

```python
context.configure(connection=connection, target_metadata=target_metadata,
                  version_table_schema="public", include_schemas=True)
```

This is not just tidiness: D-06's coverage test walks every table in the eight module schemas and demands `workspace_id` + RLS. An `alembic_version` table inside `ledger` would fail that test, and the fix would be a `GLOBAL_TABLES` entry — polluting a four-entry security-relevant file with a bookkeeping table. `public` avoids the question. **The repo does not state this anywhere; it is a genuine Phase-1 decision.**

**Async `env.py`** [VERIFIED: alembic.sqlalchemy.org cookbook, "Using Asyncio with Alembic"]:

```python
async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()
```
Scaffold it with `alembic init -t async`. `poolclass=NullPool` matters — a pooled connection outliving the migration is a source of the stale-prepared-statement error in Pitfall 6.

**Naming convention.** Set one on the shared `MetaData` so constraint names are deterministic and `op.drop_constraint` is writable:

```python
NAMING = {
  "ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s",
  "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s",
  "pk": "pk_%(table_name)s",
}
metadata = MetaData(schema="ledger", naming_convention=NAMING)
```

**`search_path`.** Keep every identifier schema-qualified in both DDL and queries, per ADR-0027 ("Schema-qualified names appear in every query and every migration. That is the intended cost: it is what makes a forbidden edge legible without a linter."). Do not set a permissive `search_path` on the application connection — a `ledger` on the path is what makes an accidental `registry.revision` join look ordinary.

---

### Pattern 11 — Grants (D-07)

```sql
GRANT USAGE ON SCHEMA ledger TO prope_app;

REVOKE ALL ON ledger.call_record,   ledger.call_body, ledger.price_table,
              ledger.workspace_spend, ledger.spend_ceiling FROM PUBLIC;

GRANT SELECT, INSERT, UPDATE ON ledger.call_record    TO prope_app;  -- UPDATE: A-099 upsert + repricing
GRANT SELECT, INSERT, DELETE ON ledger.call_body      TO prope_app;  -- SELECT is required by the DELETE's WHERE
GRANT SELECT, INSERT         ON ledger.price_table    TO prope_app;  -- T-006: no UPDATE, no DELETE
GRANT SELECT, INSERT, UPDATE ON ledger.workspace_spend TO prope_app; -- A-103 upsert
GRANT SELECT, INSERT, UPDATE ON ledger.spend_ceiling  TO prope_app;  -- "set or clear" is an UPDATE
```

Notes:

- The lock states the target exactly [VERIFIED: `docs/modules/call-ledger.lock.yml:473-476`]: "REVOKE UPDATE, DELETE ON ledger.price_table FROM prope_app. It needs neither — superseding a price is a new row by declaration. Also REVOKE DELETE ON ledger.call_record (the upsert needs UPDATE and keeps it; nothing needs DELETE). `call_body` keeps DELETE, because A-106's retention job is the one thing that must have it."
- Prefer **granting only what is needed** over `GRANT ALL` followed by `REVOKE`. Both end in the same state; the positive form is the one a reviewer can read. If the plan prefers to mirror the lock's `REVOKE` wording literally, do `GRANT ALL` then `REVOKE UPDATE, DELETE` — but then the T-006 test is asserting the net effect either way.
- **No `ALTER DEFAULT PRIVILEGES`.** A future table should arrive with no privileges until somebody writes them — the same deny-by-default inversion ADR-0045 applied to RLS coverage.
- `call_body` gets no `UPDATE`: bodies are written once and deleted.
- **No `GRANT` of any kind on `ledger.*` to any other module's consumer.** ADR-0027: "no module receives any privilege on `ledger.*`, which is a sink."

### Anti-patterns to avoid

- **`SET LOCAL app.workspace_id = '{workspace_id}'` by string interpolation.** Injection on a value that arrives in a broker payload. Use `set_config`.
- **`current_setting('app.workspace_id')` without the second argument** in a policy. Converts "zero rows" into "raises".
- **`FORCE ROW LEVEL SECURITY`** on any `ledger` table. Breaks the owner-bypass ADR-0035 depends on.
- **Native PostgreSQL `ENUM` types** for `cost_status` and friends. See Pitfall 4.
- **`float` / `double precision` / Python `float`** for any money value. See Pitfall 5.
- **`timestamp without time zone`** anywhere. A-003 says UTC with an explicit offset; the naive type silently discards it.
- **`DEFAULT now()` on `call_record.created_at`.** Breaks CL-03 under backlog, and the test passes on an idle machine.
- **Rounding a cost to a currency's minor units.** Produces `0.00` for realistic per-call figures — see Pitfall 5.
- **`SELECT SUM(cost)` to answer the ceiling.** A-103 exists specifically to avoid aggregating "the largest and fastest-growing table in the system".
- **A `BEFORE UPDATE` trigger to enforce append-only.** ADR-0025 rejects it by name — droppable by the role it polices, and disabled wholesale by `ALTER TABLE … DISABLE TRIGGER`.
- **A fifth `SECURITY DEFINER` function** to solve the retention enumeration. A test asserts the set is exactly four; adding one is a designed-in failure (see OQ-C).
- **An `ON DELETE CASCADE` from `call_record` to `call_body`, or any FK leaving `ledger`.**
- **`SELECT *` on `call_body`** anywhere, including in a repository helper. ADR-0018.
- **Autogenerating a migration and committing it.** D-04. The first autogenerate after 0003 lands will propose dropping the policies it cannot see.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tenant filtering | A repository base class that injects `WHERE workspace_id = …` | The RLS policy (Pattern 8) | ADR-0035 rejects application-only filtering by name: "It cannot be tested for in any meaningful way — one can assert that today's queries filter correctly, which says nothing about tomorrow's" |
| Append-only price table | A repository with no `update()`; a `BEFORE UPDATE` trigger | `REVOKE UPDATE, DELETE` (D-07) | ADR-0025 rejects both alternatives explicitly and at length |
| "Cost is never zero" | A guard in the writer | `CHECK (cost IS NULL OR cost > 0)` | The criterion says "no row **anywhere**"; a writer guard covers one code path, a constraint covers the table |
| Money arithmetic | `float`, or integer minor units | `NUMERIC` / `decimal.Decimal` | Per-call costs are 5–8 decimal places below a currency's minor unit; minor-unit integers *are* the rounding bug |
| Effective-dated lookup | Loading the price table into Python and scanning | `ORDER BY effective_from DESC LIMIT 1` on the composite index | ADR-0019 forbids a cache; the indexed query is one backward scan |
| Batched delete | One `DELETE`, or `DELETE … LIMIT` (not valid in PostgreSQL), or partitioning | ctid/PK subselect + `LIMIT` in a Python loop | A-132 decided against partitioning with a numeric revisit trigger; the lock requires bounded chunks |
| Job scheduling | APScheduler, Celery, cron-in-container | A plain `asyncio` task — **and not in Phase 1** | `tech_stack.md:585-586`: "no scheduler library enters the build for a third timer" |
| Test database | A hand-rolled `docker run` in `conftest.py`; a shared dev database | `testcontainers-python` | D-02, and a shared database inherits prior state — the thing that makes an RLS test lie |
| ULID generation | A hand-rolled base32 encoder | `python-ulid` | `call-ledger.lock.yml:297` |
| Migration authoring | `alembic revision --autogenerate` as the workflow | Hand-written revisions, autogenerate as a draft only | D-04 |
| Constraint naming | Letting PostgreSQL name things | A `MetaData` naming convention | Otherwise `op.drop_constraint` needs names nobody can predict |
| Time in tests | `freezegun` / `time-machine` | Pass `now` in (Pattern 7) | Neither library can move the *server's* clock, which is what a `now()` in SQL reads |

**Key insight:** In this module almost every "don't hand-roll" resolves to *the database already does this, and the repo has already decided that the database doing it is the point*. The failure mode of hand-rolling here is not inefficiency — it is a guarantee that reads as satisfied and is not, which is precisely the defect class ADR-0025, ADR-0027, ADR-0035 and ADR-0045 were each written to remove.

## Resolving Claude's Discretion

Six items, each with a recommendation and the evidence it rests on. **These are recommendations for the planner to adopt and record, not decisions already made.**

### 1. Money representation and rounding — RECOMMENDED

- `input_price_per_1k`, `output_price_per_1k`, `monthly_limit`, `per_run_limit`: **`numeric(20,10)`**.
- `cost`, `total_cost`: **`numeric(20,10)`** — same scale, so the arithmetic never needs to widen or narrow.
- Arithmetic: `cost = (input_tokens / 1000) * input_price_per_1k + (output_tokens / 1000) * output_price_per_1k`, evaluated in exact decimal, then **quantised to 10 decimal places, half-even**.
- **Do not round to the currency's minor units.** This is the whole of the finding.

Why the scale. A-107 keeps the currency explicit and allows VND alongside USD, so the value range must cover both a USD price of order `0.00002` per 1k tokens and a VND price of order `1000` per 1k tokens. Ten integer digits and ten fractional digits spans both with room. The smallest non-zero cost the system can produce — one token at the cheapest realistic price — is around `2 × 10⁻⁸`, comfortably above the 10-decimal floor.

Why not minor units. A representative per-call cost is a few hundred tokens at a price of order `$0.00015` per 1k — on the order of `$0.00007`. Rounded to two decimal places that is **`0.00`**, and the row now "records a cost of zero", which ROADMAP success criterion 2 forbids in as many words and which ADR-0019 calls "the most dangerous of these because it produces a working system". The lock's `test_plan.unit` line — "cost arithmetic and rounding against a stated currency" — is best read as *the currency travels with the figure and the arithmetic is exact in it*, not as *round to the currency's smallest coin*. Rounding to display precision belongs in the UI, where A-107 already puts currency rendering. **Recommend a unit test that asserts a realistic sub-cent call stores a non-zero cost** — it is the cheapest guard against this being reintroduced.

Confidence: MEDIUM on the specific `(20,10)`; HIGH on "no minor-unit rounding" and "NUMERIC not float".

### 2. Effective-date boundary semantics — RECOMMENDED

- A call whose `created_at` **equals** a row's `effective_from` is priced at **that row** (half-open `[from, next_from)`, predicate `effective_from <= created_at`).
- "A price row exists but every row's `effective_from` is later than the call" is **`unpriced`, on exactly the same footing as no row at all.**

Evidence: ADR-0019 speaks only of "the price row **in force at** the call's own `created_at`" and of "a missing price row". If no row is in force, there is no price — the distinction between "no rows exist" and "rows exist but none applies yet" is invisible to the writer and should stay invisible, because it is one `if` away from someone deciding the earliest row is "close enough". Both cases store real tokens with `cost_status='unpriced'` and a NULL cost, both appear on the unpriced worklist, and both are repriced when someone adds a row with an earlier `effective_from` — which is exactly AC-5's remedy.

Ties are prevented by the `UNIQUE (workspace_id, provider_config_id, upstream_model, effective_from)` constraint rather than broken by a secondary sort key. Confidence: MEDIUM (the repo is genuinely silent; the reasoning is derived from ADR-0019's language).

### 3. The Phase 1 write-path seam — RECOMMENDED

Ship **one async function** in `src/prope/call_ledger/writer.py`:

```python
async def write_records(
    session: AsyncSession,              # obtained from workspace_transaction(); single workspace
    records: Sequence[CallRecordDraft],
    *, retention_window: timedelta,
) -> WriteResult:                        # counts: priced / unpriced / unknown / bodies_written
```

It prices each draft against the price row in force at *that draft's* `created_at`, stamps `expires_at` on bodies, inserts `call_record` and `call_body`, and **upserts `workspace_spend` in the same transaction**. Phase 2's drain calls it once per workspace group; Phase 3's direct-write fallback calls it with a single record. Phase 1's tests call it directly. That is what "one writer implementation so pricing and `expires_at` stamping cannot drift between them" [VERIFIED: `docs/modules/call-ledger.lock.yml:272-274`] requires.

**Yes, include the `workspace_spend` upsert in Phase 1.** A-103 says the aggregate is "updated inside the same transaction that writes the priced record", and ADR-0040 confirms "A-103's monthly aggregate update was already per-workspace, so it falls inside the same transaction naturally rather than needing its own". Deferring it means Phase 2 rewrites the writer's transaction boundary — the single riskiest edit to make to a function three phases depend on. The table is in Phase 1's `data.owns`; leaving it empty for a phase is how it acquires a second writer later.

Sub-decisions the planner should record:

- `period_month` is derived from the record's **own `created_at`** in UTC, not from wall clock — same reasoning as pricing.
- `call_count` counts **every** written record for that (workspace, month), including `unpriced` and `not_applicable`. `total_cost` sums **only** `priced` costs. Rationale: `call_count` answers "how much traffic", `total_cost` answers "how much money", and conflating them would let unpriced traffic look free.
- `workspace_spend.currency` is set from the first priced record's currency and asserted to match on subsequent ones (A-107 — one currency per workspace). A mismatch should raise, not silently sum. Consider a `CHECK` that `total_cost IS NULL OR currency IS NOT NULL`.

Confidence: HIGH on the seam shape; MEDIUM on the `call_count` semantics (the repo does not state them).

### 4. Retention job shape and scheduling — RECOMMENDED

**Ship the callable and its integration test. Ship no scheduler and no workspace enumerator.**

```python
async def delete_expired_bodies(
    sessionmaker, workspace_id: str, *, now: datetime,
    chunk_size: int = 5000, max_chunks: int | None = None,
) -> int:   # rows deleted
```

Each chunk runs in **its own** `workspace_transaction(workspace_id)`. See OQ-D for why this is a departure from ADR-0040's literal wording and why it is nonetheless the right reading.

Three reasons not to schedule it in Phase 1:

1. The `worker` process does not exist until Phase 2 (ROADMAP), and `tech_stack.md` puts the retention job in `worker`.
2. The cross-tenant workspace enumerator is `access.list_workspaces()`, which ADR-0051 names as *the* mechanism for this job — and it lives in the `access` schema, arriving Phase 7. Phase 1 cannot build the enumeration without either a forbidden edge or a fifth sanctioned bypass. See OQ-C.
3. CL-08 / AC-8 are fully satisfied by the callable: "Given bodies written 31 days ago with a 30-day retention window, when the deletion job runs, then those `call_body` rows no longer exist by any query, their `call_record` rows are intact." Every clause of that is testable against a single seeded workspace.

Verify by **direct query as `prope_migrate`**, not through the application session — the lock's security test plan requires exactly this: "retention delete verified by direct query rather than through an API that could be filtering". Under RLS, an application-session query for a different workspace returns zero rows whether or not the delete worked, so a test that checks emptiness through `prope_app` in the wrong tenant proves nothing.

Confidence: HIGH.

### 5. Index strategy and column constraints — RECOMMENDED

Covered in full by Pattern 1 (indexes) and Pattern 4 (constraints). Two judgement calls worth restating:

- **`text` + `CHECK`, not native `ENUM`.** See Pitfall 4. CONTEXT.md's own phrasing of this discretion item — "the NOT NULL / **CHECK** constraints encoding `usage_status`…" — already leans this way.
- **Every `CHECK` named explicitly** via the naming convention, so the T-006-style tests can assert on constraint names and so a later migration can drop one by name.

Confidence: HIGH on the shapes; MEDIUM on the exact index list (some serve Phase 2/3 consumers and could defensibly wait — though adding an index to `call_record` after it is the largest table in the system is the expensive direction).

### 6. `prope_report` grants in Phase 1 — RECOMMENDED

**Grant them in Phase 1**, in migration 0004:

```sql
GRANT USAGE ON SCHEMA ledger TO prope_report;
GRANT SELECT ON ALL TABLES IN SCHEMA ledger TO prope_report;
```

Reasons: the role is created in 0001 regardless (D-05); ADR-0037 records that "ADR-0036's restore rehearsal now checks that this role exists in the target cluster, because a dump restored without it produces grants referring to a role that is not there" — which only bites if the grants exist, so the grants and the role should ship together; and adding per-module grants later, one module at a time, is precisely the drift ADR-0045 was written about.

**One thing to name explicitly in the plan rather than discover later:** `prope_report` has `BYPASSRLS` and a `SELECT` grant on `ledger.call_body` therefore gives a human credential a read path to raw end-user request and response bodies — the data ADR-0018 says has "the fewest ways to reach it". ADR-0037 already contemplates this in as many words ("`BYPASSRLS` means this credential reads every workspace's prompt bodies, **call bodies**, and history. It is a full-read credential and is handled as one"), so it is settled rather than novel. A defensible narrowing — granting `prope_report` `SELECT` on the other four tables and not on `call_body` — would need an ADR and is **out of scope for this phase**; recorded here so the planner does not invent it, and so a reviewer who notices the tension finds it already answered.

Confidence: MEDIUM (the repo settles the role's capability but not the timing).

## Common Pitfalls

### Pitfall 1 — `SET LOCAL` cannot take a bind parameter

**What goes wrong:** `await session.execute(text("SET LOCAL app.workspace_id = :ws"), {"ws": ws})` fails; the "fix" is an f-string, which is an injection site on a value that arrives from a RabbitMQ payload in Phase 2.
**Why it happens:** PostgreSQL's `SET` grammar accepts "string constants, identifiers, numbers, or comma-separated lists of these" — the value is part of the statement, not a parameter [VERIFIED: postgresql.org/docs/17/sql-set.html].
**How to avoid:** `SELECT set_config('app.workspace_id', :ws, true)`.
**Warning signs:** any f-string or `%` inside a `text()` in `session.py`; a `SyntaxError at or near "$1"` from asyncpg.

### Pitfall 2 — `current_setting()` raises instead of returning zero rows

**What goes wrong:** The policy uses the one-argument form; on a fresh connection with no workspace set, every query raises `unrecognized configuration parameter "app.workspace_id"` instead of returning nothing. The "missing filter returns zero rows" contract (C-3) is silently a different contract, and the D-08 test either fails confusingly or is written to expect the error — cementing the wrong behaviour.
**Why it happens:** `current_setting` "throws an error unless *missing_ok* is supplied and is `true`" [VERIFIED: postgresql.org/docs/17/functions-admin.html].
**How to avoid:** always `current_setting('app.workspace_id', true)` in every policy.
**Warning signs:** the zero-rows test passes on a warm pool and fails as the first test in a fresh session — or vice versa. Assert both connection states.

### Pitfall 3 — `SET LOCAL` scope versus pooling and nested transactions

**What goes wrong (a):** The variable is set before the transaction opens, so it "emits a warning and otherwise has no effect" and then leaks nothing — but also protects nothing, and the next statement sees the previous tenant's value or none.
**What goes wrong (b), and this one bites the test rig:** A test harness that wraps each test in an outer transaction and rolls back at the end turns `session.begin()` inside `workspace_transaction()` into a **savepoint**. `SET LOCAL` / `set_config(…, true)` are scoped to the *transaction*, not the savepoint, so the workspace context set for tenant A persists after that "transaction" ends and contaminates a subsequent call for tenant B — inside the same test. A cross-tenant isolation test then passes for the wrong reason, or fails inexplicably.
**How to avoid:** open the transaction first, then set the variable; and **do not use outer-transaction rollback for test isolation in this project**. Truncate between tests instead (as the container superuser or `prope_migrate`): `TRUNCATE ledger.call_record, ledger.call_body, ledger.price_table, ledger.workspace_spend, ledger.spend_ceiling RESTART IDENTITY CASCADE`. Slower per test, and correct.
**Warning signs:** a test that switches workspaces mid-test; any `join_transaction_mode` / nested-transaction fixture in `conftest.py`.

### Pitfall 4 — PostgreSQL native `ENUM` and Alembic

**What goes wrong:** `cost_status` is declared as a native `ENUM`. Adding a value later requires `ALTER TYPE … ADD VALUE`, which cannot run inside a transaction block and whose new value is unusable in the same transaction; Alembic needs an `autocommit_block`, which breaks the all-or-nothing property of the migration. Removing or reordering a value is impossible at any price. SQLAlchemy's `Enum` type also creates and drops the type implicitly, which interacts badly with hand-written revisions [VERIFIED: alembic/PostgreSQL docs via search].
**Why it happens:** `ENUM` looks like the "typed" choice, and SQLAlchemy makes it one line.
**How to avoid:** `text` column + named `CHECK` constraint. Changing the vocabulary is then `DROP CONSTRAINT` / `ADD CONSTRAINT` inside an ordinary transactional migration. Model the vocabulary in Python as `StrEnum` for type-checking; let the database hold a `CHECK`.
**Warning signs:** `sa.Enum(...)` in a model or `postgresql.ENUM` in a migration; any `autocommit_block` in the chain.

### Pitfall 5 — Money as float, or rounded to minor units

**What goes wrong (a):** `float` arithmetic makes `cost` non-reproducible; two runs of the same repricing disagree in the last places, and ADR-0019's whole point is a figure that can be re-derived years later.
**What goes wrong (b), and this one violates a stated success criterion:** rounding the per-call cost to the currency's minor units yields `0.00` for a typical call, storing a cost of zero — which criterion 2 forbids and which the `cost > 0` CHECK will then reject at insert, turning a rounding decision into a write-path outage.
**How to avoid:** `NUMERIC` end to end; `decimal.Decimal` in Python; quantise at the column's scale, not at the currency's; assert a sub-cent call stores a non-zero cost.
**Warning signs:** `float` in a type hint on a cost; `round(x, 2)`; `Numeric(asdecimal=False)`.

### Pitfall 6 — asyncpg cached statements after a DDL change

**What goes wrong:** `InvalidCachedStatementError: cached statement plan is invalid due to a concurrent DDL statement` — typically in tests, where migrations run against a connection the pool later reuses.
**Why it happens:** asyncpg prepares and caches statements; a migration changes the relation underneath.
**How to avoid:** run migrations on their own engine with `poolclass=NullPool` and `dispose()` it afterwards (the async `env.py` recipe already does this); build the application engine only after `upgrade head` has completed.
**Warning signs:** the first test after a schema change fails and the second passes.

### Pitfall 7 — `timestamptz` versus `timestamp`, and naive datetimes

**What goes wrong:** `timestamp without time zone` silently discards the offset A-003 requires; a naive Python `datetime` compared against a `timestamptz` column is interpreted against the *server's* `TimeZone` setting, so AC-3's day-5/day-12/day-20 arithmetic can be off by hours and the boundary test passes or fails by geography.
**How to avoid:** `timestamptz` on every timestamp column; `datetime.now(UTC)` everywhere in Python; never construct a naive datetime in a test fixture. Consider setting `TimeZone = 'UTC'` on the application connection so an accidental naive value is at least interpreted consistently.
**Warning signs:** `datetime.utcnow()` (naive, and deprecated in 3.12+); `datetime(2026, 8, 9)` with no `tzinfo` in a fixture.

### Pitfall 8 — Testing a privilege or a policy against zero rows

**What goes wrong:** The T-006 test issues `UPDATE ledger.price_table SET …` with no workspace context and no rows present, and "passes" because nothing happened — while the `REVOKE` was never applied. Symmetrically, the RLS zero-rows test passes against an empty table.
**Why it happens:** an `UPDATE` affecting zero rows and an `UPDATE` refused by the engine are both "nothing changed" from the test's side.
**How to avoid:**
- For T-006: seed a real price row (as `prope_migrate`), enter a `workspace_transaction` for that workspace so the row *is* visible, then assert the `UPDATE` raises `InsufficientPrivilegeError` / `permission denied for table price_table`. Privilege is checked before RLS, so this isolates the privilege.
- For RLS: seed as workspace A, read as workspace B, assert zero rows — **and then read the same table as `prope_migrate` and assert the rows are there.** Without that second assertion, an empty table passes.
**Warning signs:** an RLS or privilege test with no positive control.

### Pitfall 9 — `alembic_version` inside a module schema

**What goes wrong:** With `include_schemas=True` and no `version_table_schema`, the version table lands somewhere a reviewer did not choose; if it lands in `ledger`, D-06's coverage walk fails it for having no `workspace_id`, and the "fix" is a `GLOBAL_TABLES` entry that dilutes a four-entry security file.
**How to avoid:** `version_table_schema="public"` explicitly in `env.py`, and have the coverage test walk only the eight declared module schemas.

### Pitfall 10 — Planning against the lock file's literal AC-1 and AC-2

**What goes wrong:** AC-1 and AC-2 are stated against an in-process queue and a spill file, neither of which exists (ADR-0041 deleted them). `.planning/research/PITFALLS.md:74` says to restate them and CONTEXT.md repeats the warning.
**How to avoid:** they belong to **Phase 3**, not here. Phase 1 should not reference them at all, and should not create a `tests/chaos/test_spill_replay_is_idempotent` file to match the lock's `test_ref`.

### Pitfall 11 — `MetaData` schema and cross-module leakage

**What goes wrong:** A single `MetaData(schema="ledger")` shared by all eight modules puts the next module's tables in `ledger`. Or eight independent `MetaData` objects make Alembic's `target_metadata` awkward for a single linear chain.
**How to avoid:** one shared `MetaData` with the naming convention and **no** default schema; each module's tables declare `__table_args__ = {"schema": "ledger"}` explicitly. Phase 1 sets the pattern 23 phases inherit — worth getting right the first time.

### Pitfall 12 — Granting `BYPASSRLS` without superuser

**What goes wrong:** `CREATE ROLE prope_report LOGIN BYPASSRLS` fails with "permission denied" when the migration connection is not a superuser. In the testcontainers rig the default user *is* superuser, so this passes locally and fails on the first real deploy.
**How to avoid:** state in the plan that migration 0001 requires a superuser connection for this one attribute, or split it into a documented out-of-band bootstrap step. Since D-05 requires `alembic upgrade head` against an empty cluster to yield a working database, the superuser path is the consistent one — but it must be *named*, not assumed.

## Code Examples

### Migration helper for RLS (used five times)

```python
# alembic/ddl.py
from alembic import op

def enable_tenant_rls(schema: str, table: str, *, role: str = "prope_app",
                      column: str = "workspace_id") -> None:
    """ADR-0035 / ADR-0045: deny-by-default tenant policy.

    ENABLE, never FORCE: prope_migrate owns the table and must keep its bypass.
    current_setting(..., true): the 2-arg form returns NULL rather than raising,
    which is what turns a missing filter into zero rows.
    """
    op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {table}_tenant ON {schema}.{table}
          FOR ALL TO {role}
          USING      ({column} = current_setting('app.workspace_id', true))
          WITH CHECK ({column} = current_setting('app.workspace_id', true))
    """)
```

### The tenant seam

```python
# src/prope/db/session.py
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

@asynccontextmanager
async def workspace_transaction(sm: async_sessionmaker[AsyncSession], workspace_id: str):
    """D-08. One workspace, one transaction (ADR-0040).

    set_config(..., true) rather than SET LOCAL: PostgreSQL's SET takes literals,
    not bind parameters, and workspace_id arrives from a broker payload.
    """
    async with sm() as session:
        async with session.begin():                       # transaction FIRST
            await session.execute(
                text("SELECT set_config('app.workspace_id', :ws, true)"),
                {"ws": workspace_id},
            )
            yield session
```

### Effective-dated resolution (CL-03)

```python
# src/prope/call_ledger/pricing.py
PRICE_IN_FORCE = text("""
    SELECT price_row_id, input_price_per_1k, output_price_per_1k, currency
    FROM   ledger.price_table
    WHERE  workspace_id       = :workspace_id
      AND  provider_config_id = :provider_config_id
      AND  upstream_model     = :upstream_model
      AND  effective_from    <= :at            -- half-open [from, next_from)
    ORDER  BY effective_from DESC
    LIMIT  1
""")

async def resolve_price(session, *, workspace_id, provider_config_id, upstream_model, at):
    row = (await session.execute(PRICE_IN_FORCE, {...})).mappings().first()
    return PriceRow(**row) if row else None   # None ⇒ unpriced, NEVER a zero price
```

### Cost, exactly (CL-04 / never-zero)

```python
from decimal import Decimal, ROUND_HALF_EVEN
SCALE = Decimal("0.0000000001")   # 10dp, matching numeric(20,10)

def compute_cost(input_tokens: int, output_tokens: int, price: PriceRow) -> Decimal:
    per_1k = Decimal(1000)
    cost = (Decimal(input_tokens)  / per_1k) * price.input_price_per_1k \
         + (Decimal(output_tokens) / per_1k) * price.output_price_per_1k
    return cost.quantize(SCALE, rounding=ROUND_HALF_EVEN)
    # NOT quantised to the currency's minor unit: a sub-cent call would become 0.00,
    # and "no row anywhere records a cost of zero" is a success criterion.
```

### Bounded-chunk retention (CL-08)

```python
DELETE_CHUNK = text("""
    WITH victims AS (
      SELECT ctid FROM ledger.call_body
      WHERE  workspace_id = current_setting('app.workspace_id', true)
        AND  expires_at  <= :now
      ORDER  BY expires_at
      LIMIT  :chunk
      FOR UPDATE SKIP LOCKED
    )
    DELETE FROM ledger.call_body b USING victims v WHERE b.ctid = v.ctid
""")

async def delete_expired_bodies(sm, workspace_id, *, now, chunk_size=5000, max_chunks=None):
    deleted, rounds = 0, 0
    while max_chunks is None or rounds < max_chunks:
        async with workspace_transaction(sm, workspace_id) as s:   # one txn per chunk
            n = (await s.execute(DELETE_CHUNK, {"now": now, "chunk": chunk_size})).rowcount
        deleted += n; rounds += 1
        if n < chunk_size:
            break
    return deleted
```

### The two live-engine assertions the phase is really about

```python
# tests/security/test_append_only_privilege.py  — D-07 / T-006
async def test_price_table_update_is_refused_by_the_engine(migrate_session, app_sm, seeded_price):
    async with workspace_transaction(app_sm, seeded_price.workspace_id) as s:
        visible = (await s.execute(text(
            "SELECT count(*) FROM ledger.price_table"))).scalar()
        assert visible == 1                      # positive control: the row IS visible
        with pytest.raises(DBAPIError) as e:
            await s.execute(text("UPDATE ledger.price_table SET input_price_per_1k = 1"))
        assert "permission denied" in str(e.value).lower()

# tests/security/test_tenant_isolation.py  — D-08 / C-3
async def test_missing_workspace_context_returns_zero_rows(migrate_session, app_sm, seeded_call):
    async with app_sm() as s, s.begin():                     # no set_config
        rows = (await s.execute(text("SELECT * FROM ledger.call_record"))).all()
    assert rows == []
    # positive control: the row exists, the POLICY is what hid it
    assert (await migrate_session.execute(text(
        "SELECT count(*) FROM ledger.call_record"))).scalar() == 1
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact on this phase |
|--------------|------------------|--------------|----------------------|
| In-process queue + spill file for durability | RabbitMQ + direct-write fallback | ADR-0041, 2026-08-09 | Phase 1 must not build a spill file, a replay, or the three spill metrics; lock AC-1/AC-2 read against the deleted mechanism |
| RLS coverage test enumerates tables *carrying* `workspace_id` | It walks **every** table in the eight schemas; each is tenant-scoped or in `GLOBAL_TABLES` with a written reason | ADR-0045, 2026-08-09 (supersedes ADR-0035's enumeration and ADR-0042's patch) | D-06 writes the walk-all-eight version from day one |
| `call_body` reachable by joining `call_record` | `call_body` carries its own `workspace_id` | ADR-0040, 2026-08-09 | Five tables, five policies, no exceptions |
| Two database roles | Three — `prope_report` added | ADR-0037 | Migration 0001 creates three |
| SQLAlchemy 1.x `Query` / sync sessions | 2.0 style, `select()`, `AsyncSession` | SQLAlchemy 2.0 | Do not write `session.query(...)`; it is legacy in 2.0 |
| `datetime.utcnow()` | `datetime.now(datetime.UTC)` | Python 3.12 deprecation | `utcnow()` returns a *naive* datetime — Pitfall 7 |
| PostgreSQL `public` schema writable by all | `CREATE` revoked from `PUBLIC` by default | PostgreSQL 15 | The explicit `REVOKE` in 0001 is belt-and-braces, still worth writing |

**Deprecated / do not use:**
- `psycopg2` for this project — A-128 chose asyncpg; the commented-out pin in `requirements.txt` is boilerplate from a different project.
- LangChain / LangGraph / `langchain-openai` — A-127 removed them; Prope's ML stack is `n/a`.
- `httpx` in this module — `tech_stack.md:504`: every upstream call is issued by provider-access.
- `stale_resolution` as a `call_record` column — removed 2026-08-09 with a written reason.

## Assumptions Log

Claims below are tagged `[ASSUMED]` in the body — training knowledge, not verified against an authoritative source in this session. Each needs confirmation before it becomes a locked decision.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `greenlet` must be pinned explicitly for SQLAlchemy's asyncio extension | Standard Stack | Low — surfaces immediately as an import error at first async use |
| A2 | asyncpg raises or misinterprets naive `datetime` against `timestamptz`; always pass tz-aware | Pitfall 7 | Low — the recommendation (always tz-aware) is correct regardless of which behaviour asyncpg actually has |
| A3 | `numeric(20,10)` is wide enough for both USD-per-1k and VND-per-1k prices and for any realistic cost | Discretion §1 | Medium — a too-narrow scale rounds a small cost to zero, which the `cost > 0` CHECK then rejects at insert. Widen rather than narrow if uncertain |
| A4 | `call_count` in `workspace_spend` includes unpriced and unknown-usage records | Discretion §3 | Medium — changes what the number means; the repo does not state it |
| A5 | `request_body` / `response_body` are `text` rather than `jsonb` | Pattern 1 | Low–Medium — `jsonb` would reject a malformed body, which is arguably the one most worth keeping. Reversing later is a rewrite of the largest table |
| A6 | 5,000 rows is an appropriate retention chunk size | Pattern 6 | Low — tunable; the stated target (500k rows in 10 min) has ample headroom at that size |
| A7 | `FOR UPDATE SKIP LOCKED` in the retention chunk selection | Pattern 6 | Low — a safety improvement, not a requirement; remove it if it complicates the plan |
| A8 | Chunked `DELETE` returning space to the free list rather than the disk is acceptable in Phase 1 | Pattern 6 | Low — A-132 states and accepts this explicitly, so this is really `[VERIFIED]`; listed for visibility |
| A9 | The migration connection is a superuser (needed for `BYPASSRLS`) | Pitfall 12 | Medium — passes in testcontainers, fails on a real deploy where the DBA issued a non-superuser `prope_migrate` |
| A10 | Truncate-between-tests rather than transaction-rollback isolation | Pitfall 3 | Medium — the rollback pattern is the conventional one; adopting it here would silently break cross-tenant tests |

## Open Questions

Four genuine conflicts or gaps between the specs. Per `.planning/BSP-LINK.md:44-53`, these are raised rather than resolved: **do not edit the lock file or any ADR to make them go away.** Each is stated with the exact field in conflict and a recommended interim resolution so Phase 1 is not blocked.

**Resolution status.** OQ-A, OQ-B and OQ-D were put to the developer and answered; their adopted readings are recorded verbatim in `01-01-PLAN.md` § "Adopted readings" and re-stated in every plan that depends on them, and each is marked RESOLVED inline below. **OQ-C and OQ-E remain deliberately open** — carrying them upstream is this phase's own instruction 8, and the upstream corrections they ask for (a `docs/adr/` edit) are out of bounds for Phase 1. Marking them resolved would misreport a spec conflict as settled.

### OQ-A — The `workspace_id` column type: prefixed ULID or UUID? (BLOCKING for the migration) — **RESOLVED (adopted reading recorded in 01-01-PLAN.md)**

- **What we know.** ADR-0003 and A-045 fix identifiers as "ULIDs with typed prefixes". `docs/modules/access-control.lock.yml:208` says of the `workspace` table: "`id prefix wsp_`. The tenancy root (A-109)." So a workspace id is a string like `wsp_01JXXXXXXXXXXXXXXXXXXXXXXX`.
- **What's unclear.** ADR-0035's decision text writes the policy as ``The policy is `workspace_id = current_setting('app.workspace_id')::uuid` `` (`docs/adr/0035-tenant-isolation-is-a-database-policy.md:43`), and ADR-0045's illustrative policy repeats the `::uuid` cast (`docs/adr/0045-…:89-90`). A `wsp_`-prefixed ULID is not a UUID and the cast raises `invalid input syntax for type uuid`.
- **Why it matters now.** Phase 1 writes the first five policies and the first `workspace_id` columns in the project. Every later module inherits the type. Copying ADR-0035 verbatim produces a schema in which **every policy evaluation errors**, and it will be discovered in Phase 1's first test rather than reviewed.
- **Recommendation:** treat the `::uuid` in ADR-0035/ADR-0045 as **illustrative prose written before ADR-0003's id format was applied to the tenancy root**, and implement `workspace_id text` with the policy predicate `workspace_id = current_setting('app.workspace_id', true)` — no cast, text on both sides. This is consistent with ADR-0003, with access-control's own lock, and with `access.list_workspaces() RETURNS SETOF text` in ADR-0051:48, which is the strongest single piece of evidence: **the sanctioned enumerator returns `text`.** Raise the OQ, adopt this, and flag it for the user.

### OQ-B — The per-workspace retention window has no column — **RESOLVED (adopted reading recorded in 01-01-PLAN.md)**

- **What we know.** A-106 makes the body retention window "a per-workspace setting, defaulting to A-040's 30 days", and `apis.exposes` declares `PUT /api/v1/workspaces/{id}/retention` — "A setting from day one so OQ-013's answer is a configuration change, not a migration" (`call-ledger.lock.yml:112-113`).
- **What's unclear.** None of the five tables in `data.owns` carries a retention column. `spend_ceiling` is `workspace_id, monthly_limit, per_run_limit, currency, enabled, updated_by, updated_at`; the other four have no candidate either. The setting has no declared home.
- **Why it matters now.** `expires_at` is stamped at write time "from the workspace's retention window" — a Phase 1 write-path behaviour — and the route that sets the window is Phase 2. Phase 1 must decide where the value lives or the writer has nothing to read.
- **Options:** (i) add `retention_days` (or `body_retention` interval) to `spend_ceiling` — smallest change, but the table's name then describes half its contents; (ii) add a sixth table, e.g. `ledger.workspace_settings` — cleanest, but adds a table not in `data.owns` and therefore needs the lock amended upstream; (iii) keep it out of the database in Phase 1 and pass `retention_window` as a parameter to the writer with the A-040 default of 30 days.
- **Recommendation:** **(iii) for Phase 1** — `write_records(..., retention_window: timedelta = timedelta(days=30))`. It satisfies every Phase 1 criterion (AC-8 only needs the stamp to be correct), touches no table outside `data.owns`, and leaves the storage decision to Phase 2 where the route lives. Raise the OQ naming `docs/modules/call-ledger.lock.yml` → `data.owns` versus `apis.exposes` so the choice between (i) and (ii) is made upstream rather than by whoever writes the Phase 2 route.

### OQ-C — The retention job's workspace enumeration has no Phase-1 mechanism — **OPEN (deliberately carried; Phase 1 ships the workspace-scoped form and adds no fifth `SECURITY DEFINER` function)**

- **What we know.** ADR-0051 decides that a cross-tenant sweep "obtains the tenant list from a `SECURITY DEFINER` function that returns workspace identifiers and nothing else, then issues `SET LOCAL app.workspace_id` per workspace", creates `access.list_workspaces()` for the purpose, and states "**One function, not one per sweep.** Every future cross-tenant background job in Prope reuses this one." It names call-ledger's retention job directly: "a plain `asyncio` task in `worker`, **matching call-ledger's retention job** and evaluation's sweeper" (`docs/adr/0051-…:73-74`).
- **What's unclear.** (a) The `access` schema does not exist until **Phase 7**; Phase 1 cannot call the function. (b) `call-ledger.lock.yml` lists access-control under `forbidden_dependencies`, and `dependencies: []` is described as "this module's defining property" — so whether a `GRANT EXECUTE` on an `access` function counts as the forbidden edge is not settled anywhere. (Reading ADR-0018, the edge exists to stop call-ledger reaching a *permission oracle*; an id enumerator is not one. But that is inference, not a written decision.)
- **Why it matters now.** It determines whether Phase 1 can ship a runnable end-to-end retention job at all.
- **Recommendation:** Phase 1 ships `delete_expired_bodies(workspace_id, ...)` — workspace-scoped, no enumeration, no scheduler — plus its integration test. That fully satisfies CL-08 and AC-8. Raise the OQ so the enumeration question is answered before Phase 7 rather than discovered there, and **do not** solve it in Phase 1 by adding a fifth `SECURITY DEFINER` function: a test asserts the set is exactly four, and `tech_stack.md:135-137` explains why that assertion only means something while the number tracks architecture.

### OQ-D — "Bounded chunks inside that workspace's transaction" — one transaction or one per chunk? — **RESOLVED (adopted reading recorded in 01-01-PLAN.md)**

- **What we know.** ADR-0040: "The retention job does the same: it iterates workspaces and deletes each one's expired bodies in bounded chunks inside that workspace's transaction." The lock's performance row: "up to 500,000 body rows in a batch, deleted in bounded chunks … because a single unbounded DELETE on the largest table in the system is how a retention job takes the writer down with it."
- **What's unclear.** Read literally, "inside that workspace's transaction" (singular) puts every chunk in one transaction — which holds every row lock and the whole snapshot for the duration, and therefore delivers none of the benefit chunking exists for. The chaos plan ("run the deletion job concurrently with peak writes and assert the writer's lag stays inside its target") is only satisfiable with short transactions.
- **Recommendation:** read ADR-0040's requirement as *"each transaction covers exactly one workspace and carries its own `SET LOCAL`"* — which is the property that ADR is actually about (RLS holding on a cross-tenant batched writer) — and implement **one transaction per chunk**. Every transaction is still single-workspace, `WITH CHECK` still applies, and no transaction is long. Raise the OQ against `docs/adr/0040-…` so the wording can be clarified upstream; the Phase 1 plan should state the reading it adopted.

### OQ-E (minor) — Can a `priced` call legitimately cost exactly zero? — **OPEN (deliberately carried; Phase 1 asserts the never-zero reading in a test so Phase 19 inherits it)**

The recommended `CHECK (cost IS NULL OR cost > 0)` refuses a `priced` row with zero cost. That is what success criterion 2 asks for, and every "nothing happened" case has a home (`usage_status='unknown'` ⇒ `cost_status='not_applicable'` ⇒ NULL cost, which is exactly AC-11). But gateway's GATE-04 describes a pre-first-byte fallback as recorded "with zero tokens and zero cost". Under this encoding that call is `unknown`/`not_applicable` with NULL cost and NULL tokens — never a zero. Recommend adopting that reading and asserting it in a Phase 1 unit test so the Phase 19 gateway work inherits it rather than inventing a zero. Low risk; worth naming because the two documents use different words for the same row.

## Environment Availability

Probed on this machine, 2026-08-09.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13.x | ADR-0026 pin, D-03 | ✗ | 3.14.2 only (`C:\Python314`) | **`uv python install 3.13`** — `cpython-3.13.14-windows-x86_64` confirmed downloadable |
| **Docker daemon** | **D-02 (testcontainers)** | **✗** | — | **None.** See below |
| `uv` | dependency management | ✓ | 0.11.26 | `pip` 25.3 |
| `pip` | fallback installer | ✓ | 25.3 | — |
| `git` | version control | ✓ | 2.45.1.windows.1 | — |
| PyPI network access | installing anything | ✓ | verified via `pip index versions` | — |
| PostgreSQL 17 | every guarantee in this phase | via `postgres:17` image | — | requires Docker |
| WSL2 (Ubuntu) | possible Docker Engine host | ✓ present, **Stopped** | WSL 2 | could host Docker Engine natively |

**Missing dependencies with no fallback:**

- **Docker.** `docker` is not on `PATH`; there is no `docker.exe` under `Program Files`; `C:\ProgramData\DockerDesktop` contains only installer logs and `%LOCALAPPDATA%\Docker` is a leftover directory. Docker Desktop appears to have been installed and removed. **testcontainers-python requires a running Docker daemon** [VERIFIED: pypi.org/project/testcontainers]. D-02 accepts this explicitly ("Accepted cost: Docker is a hard test dependency"), so this is not a decision to revisit — it is an environment task. **The phase plan must include a task that installs and starts Docker (Desktop, or Docker Engine inside the existing WSL2 Ubuntu with `DOCKER_HOST` exported), and verifies it with `docker run --rm postgres:17 postgres --version`, before any test task.** Without it, every Phase 1 test — RLS zero-rows, the T-006 REVOKEs, effective-dated boundary, the retention delete — is unrunnable, and those tests *are* the deliverable.

**Missing dependencies with a fallback:**

- **Python 3.13.** `uv` is present and can install the pinned interpreter in one command. Add `uv python install 3.13 && uv venv --python 3.13` as an early task; do not let the project silently build on 3.14 against an ADR that pins 3.13.x. (Note also that `ruff.toml` currently declares `target-version = "py311"` — a third version in play.)

## Validation Architecture

> `.planning/config.json` sets `workflow.nyquist_validation: false`, so this section is not required by the pipeline. It is included because the orchestrator asked for it and the lock file's `test_plan` supports it.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` 9.1.1 + `pytest-asyncio` 1.4.0 (`asyncio_mode = "auto"`) |
| Config file | none yet — **Wave 0**: `[tool.pytest.ini_options]` in the new `pyproject.toml` |
| Fixture rig | none yet — **Wave 0**: `tests/conftest.py` with the testcontainers session fixture and three role-scoped engines |
| Quick run command | `uv run pytest tests/unit -x -q` |
| Full suite command | `uv run pytest -q` |
| Hard prerequisite | a running Docker daemon (see Environment Availability) |

### Phase Requirements → Test Map

| Req ID | Behaviour | Test Type | Automated Command | File Exists? |
|--------|-----------|-----------|-------------------|--------------|
| CL-03 | Day-5 call written day 12 is priced at the day-1 row; a day-20 row does not move it; `price_row_id` is the day-1 row | unit (live engine) | `pytest tests/unit/test_effective_dated_pricing.py -x` | ❌ Wave 0 |
| CL-03 | `created_at` exactly equal to `effective_from` resolves to the **new** row | unit | `pytest tests/unit/test_effective_dated_pricing.py -k boundary` | ❌ Wave 0 |
| CL-03 | A price row whose `effective_from` is later than every call ⇒ `unpriced` | unit | `pytest tests/unit/test_effective_dated_pricing.py -k not_yet_effective` | ❌ Wave 0 |
| CL-04 | No price row ⇒ tokens stored, `cost` NULL, `cost_status='unpriced'`, pair on the worklist query | unit | `pytest tests/unit/test_missing_price_is_unpriced_not_zero.py -x` | ❌ Wave 0 |
| CL-04 | `INSERT … cost = 0` is refused by the engine | unit | `pytest tests/unit/test_missing_price_is_unpriced_not_zero.py -k zero_refused` | ❌ Wave 0 |
| CL-04 | A realistic sub-cent call stores a non-zero cost (the rounding guard) | unit | `pytest tests/unit/test_cost_arithmetic.py -k sub_cent` | ❌ Wave 0 |
| CL-05 | Repricing fills only `unpriced`; a priced row is byte-identical afterwards; `not_applicable` stays | integration | `pytest tests/integration/test_reprice_only_unpriced.py -x` | ❌ Wave 0 |
| CL-08 | Bodies past `expires_at` are gone **by direct `prope_migrate` query**; their `call_record` rows are intact | integration | `pytest tests/integration/test_body_retention_delete.py -x` | ❌ Wave 0 |
| CL-08 | The chunk loop terminates and respects `chunk_size` | integration | `pytest tests/integration/test_body_retention_delete.py -k chunking` | ❌ Wave 0 |
| CL-11 | No usage object ⇒ `usage_status='unknown'`, tokens NULL not 0, `cost_status='not_applicable'` | unit | `pytest tests/unit/test_unknown_usage_never_zero.py -x` | ❌ Wave 0 |
| CL-11 | `INSERT` with `usage_status='unknown'` and `input_tokens = 0` is refused | unit | `pytest tests/unit/test_unknown_usage_never_zero.py -k zero_tokens_refused` | ❌ Wave 0 |
| D-06 | Coverage walk over all eight declared schemas; absent schemas reported, not skipped | architecture | `pytest tests/architecture/test_tenant_coverage.py -x` | ❌ Wave 0 |
| D-07 / T-006 | `UPDATE` and `DELETE` on `ledger.price_table` as `prope_app` are refused **with a visible row present** | security | `pytest tests/security/test_append_only_privilege.py -x` | ❌ Wave 0 |
| D-07 | `DELETE` on `ledger.call_record` refused; `DELETE` on `ledger.call_body` permitted | security | `pytest tests/security/test_append_only_privilege.py -k grants` | ❌ Wave 0 |
| D-08 / C-3 | A query outside `workspace_transaction()` returns zero rows — on a pristine **and** a reused connection — with a `prope_migrate` positive control | security | `pytest tests/security/test_tenant_isolation.py -x` | ❌ Wave 0 |
| D-08 | Insert with a mismatched `workspace_id` is refused by `WITH CHECK` | security | `pytest tests/security/test_tenant_isolation.py -k with_check` | ❌ Wave 0 |
| D-05 | `alembic upgrade head` against a pristine cluster yields a working database; re-running is a no-op | integration | `pytest tests/integration/test_migration_chain.py -x` | ❌ Wave 0 |

Note that even the "unit" rows run against the live engine — D-02's whole argument is that these properties are not observable otherwise. The unit/integration split here is about *scope* (one function vs. the write path), not about whether a database is present.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit -x -q` (single container, reused across the session).
- **Per wave merge:** `uv run pytest -q` — the whole suite including `tests/architecture` and `tests/security`.
- **Phase gate:** full suite green, plus a manual `docker compose`-free `alembic upgrade head` against a fresh container, before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] Docker daemon installed and reachable — **blocks every row above**
- [ ] Python 3.13.x installed (`uv python install 3.13`)
- [ ] `pyproject.toml` with `[tool.pytest.ini_options] asyncio_mode = "auto"` and the dependency set (D-03)
- [ ] `tests/conftest.py` — session-scoped `PostgresContainer("postgres:17")`; `alembic upgrade head`; three engines (container superuser, `prope_migrate`, `prope_app`); truncate-between-tests fixture (not transaction rollback — Pitfall 3)
- [ ] `alembic.ini` + async `alembic/env.py` with `version_table_schema="public"`
- [ ] `tests/architecture/`, `tests/security/`, `tests/unit/`, `tests/integration/` package skeletons
- [ ] `ruff.toml` `target-version` moved `py311` → `py313`
- [ ] `Makefile` `run` / `typecheck` targets repointed or removed (both currently reference things that do not exist)

## Security Domain

`workflow.security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high`.

### Applicable ASVS categories

| ASVS Category | Applies | Standard control in this phase |
|---------------|---------|-------------------------------|
| V1 Architecture | yes | Schema-per-module (ADR-0027); the sink property (no outbound edge, no cross-schema FK) |
| V2 Authentication | no | No identity surface in Phase 1; `access` schema arrives Phase 7 |
| V3 Session Management | no | No sessions here |
| V4 Access Control | **yes** | RLS deny-by-default (Pattern 8); the three-role grant matrix; T-006's `REVOKE` |
| V5 Input Validation | **yes** | CHECK constraints as the last line (Pattern 4); parameterised SQL everywhere; `set_config` instead of interpolated `SET LOCAL` |
| V6 Cryptography | no | This module "holds no credential and never sees one" (`call-ledger.lock.yml:443-444`). The KEK belongs to provider-access |
| V7 Error handling / Logging | partial | A-046: no body, prompt body, fallback answer or variable value in a log line or metric label — applies from the first `structlog` call in this phase |
| V8 Data Protection | **yes** | `call_body` retention (CL-08); ADR-0039's backup exclusion (operational, not this phase); `prope_report`'s full-read reach (Discretion §6) |
| V12 Files / Resources | no | No file handling |
| V13 API | no | No routes in Phase 1 |

### Known threat patterns for this stack

| Pattern | STRIDE | Standard mitigation | Where it lands in Phase 1 |
|---------|--------|---------------------|---------------------------|
| **T-006 — `price_table` declared append-only with nothing enforcing it** | Tampering | `REVOKE UPDATE, DELETE … FROM prope_app`, asserted against the live engine | D-07, migration 0004 + `tests/security/test_append_only_privilege.py` — **HIGH, mitigated in this phase** |
| Cross-tenant read/write through a forgotten filter | Information disclosure / Tampering | RLS `USING` + `WITH CHECK`, deny-by-default | Pattern 8, migration 0003 |
| Mis-stamped `workspace_id` on a denormalised write | Tampering | `WITH CHECK` refuses the insert (ADR-0040's stated reason) | Pattern 8 |
| SQL injection through the tenant identifier | Tampering | `set_config('app.workspace_id', :ws, true)` — parameterised | Pattern 9, Pitfall 1 |
| Covert channel via a cross-tenant foreign key | Information disclosure | No FK leaves `ledger`; RI checks always bypass RLS [VERIFIED: postgresql.org/docs/17/ddl-rowsecurity.html] | Pattern 1 |
| A zero cost read as a real figure by a reviewer | Tampering (of meaning) | `CHECK (cost IS NULL OR cost > 0)` + no minor-unit rounding | Pattern 4, Discretion §1 |
| An unnoticed new table with no tenant policy | Elevation of privilege | ADR-0045's coverage walk over all eight schemas | D-06 |
| Raw end-user bodies reachable through a new surface | Information disclosure | No read path — route-table assertion | **Phase 3 (AC-10)**, not this phase; Phase 1 must not create the surface |
| **T-005 — the broker is a second body store; the DLQ had no policy** | Information disclosure | Queue TTLs and max-lengths (A-149), DLQ depth alert | **Phase 2/3** — no broker exists in Phase 1 |

No HIGH finding is left unmitigated within Phase 1's scope. T-005 is HIGH but belongs to the phase that introduces the broker.

## Sources

### Primary (HIGH confidence)

**In-repo, read this session:**
- `docs/modules/call-ledger.lock.yml` — `data.owns` (lines 139-226), `scope` (22-61), `security_requirements` (429-482), `acceptance_criteria` (579-651), `test_plan` (653-693), `libraries_frameworks` (281-309), `performance_requirements` (311-349)
- `docs/adr/0019-cost-is-priced-once-at-write-time.md` — priced at the call's own `created_at`; append-only prices; never zero; repricing fills only unpriced
- `docs/adr/0035-tenant-isolation-is-a-database-policy.md` — the policy, the session variable, owner bypass, the zero-rows inversion
- `docs/adr/0045-every-table-is-tenant-scoped-unless-declared-global.md` — the coverage walk and `GLOBAL_TABLES`
- `docs/adr/0040-the-ledger-writer-batches-per-workspace.md` — per-workspace transactions; `call_body.workspace_id`; `WITH CHECK`
- `docs/adr/0025-append-only-is-a-database-privilege-not-a-convention.md` — the precedent for T-006, and the rejection of triggers and repository conventions
- `docs/adr/0027-…two-roles.md`, `docs/adr/0037-a-third-role-reads-across-workspaces.md` — the eight schemas, the three roles
- `docs/adr/0018-body-store-has-no-read-path-in-the-mvp.md`, `docs/adr/0039-call-bodies-are-excluded-from-the-backup.md`
- `docs/adr/0051-the-cross-tenant-sweep-enumerates-workspaces.md` — `access.list_workspaces()`, the shape rule, "matching call-ledger's retention job"
- `docs/adr/0003-management-api-conventions.md`, `docs/brainstorm/assumptions/A-045.md` — prefixed ULIDs
- `docs/brainstorm/assumptions/` — A-003, A-103, A-106, A-107, A-128, A-132
- `docs/architecture/tech_stack.md` — baseline conventions (92-143), the call-ledger rows (175-199), the no-scheduler rule (585-586)
- `docs/architecture/interfaces.md` — INT-018 through INT-021, INT-028
- `.planning/` — CONTEXT.md, DISCUSSION-LOG.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, research/PITFALLS.md, config.json
- `docs/modules/access-control.lock.yml:208` — `workspace` `id prefix wsp_`

**External, fetched this session:**
- postgresql.org/docs/17/functions-admin.html — `current_setting` / `set_config` semantics
- postgresql.org/docs/17/ddl-rowsecurity.html — default-deny, owner bypass, `FORCE`, permissive/restrictive, `USING`/`WITH CHECK`, RI checks bypassing RLS
- postgresql.org/docs/17/sql-set.html — `SET` takes literals not parameters; `SET LOCAL` outside a transaction is a no-op
- alembic.sqlalchemy.org cookbook — async migrations recipe, `autocommit_block` for enums
- pypi.org/project/testcontainers — 4.15.0, Docker requirement, `PostgresContainer` usage

### Secondary (MEDIUM confidence)

- Crunchy Data, *Simulating UPDATE or DELETE with LIMIT in Postgres: CTEs to The Rescue!* — the ctid + CTE + `LIMIT` chunked-delete pattern
- shayon.dev, *Using CTID Based Pagination for Data Cleanups in PostgreSQL*
- Crunchy Data, *Row Level Security for Tenants in Postgres*; theroadtoenterprise.com, *Postgres RLS for Multi-Tenant SaaS, the Production Pattern* — `set_config(…, true)` as the pooling-safe tenant context
- GitHub `sqlalchemy/alembic` discussion #1578 and `dw/alembic-autogenerate-enums` — the enum migration problem

### Tertiary (LOW confidence)

- Training knowledge for the items in the Assumptions Log (A1–A10). None is load-bearing for a stated success criterion; each is flagged.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — every library named by an in-repo spec, every version verified against PyPI today
- Schema and constraint design: **HIGH** on the field lists and vocabularies (verbatim from the lock file), **MEDIUM** on the types and index list (the repo declares names and semantics, not types)
- Effective-dated pricing: **HIGH** on the mechanism, **MEDIUM** on the boundary convention (derived from ADR-0019's language, not stated)
- Money representation: **MEDIUM** on `numeric(20,10)`, **HIGH** on "no minor-unit rounding" and "NUMERIC not float"
- RLS mechanics: **HIGH** — every claim traced to the PostgreSQL 17 manual and cross-checked against ADR-0035/0040/0045
- Retention job: **HIGH** on the chunk pattern and the Phase 1 scope; **MEDIUM** on chunk size
- Alembic mechanics: **HIGH** on the async recipe and the enum problem; **MEDIUM** on `version_table_schema="public"` (a genuine new decision)
- Pitfalls: **HIGH** — the four highest-value ones are each backed by an official-docs quote
- Open questions: **HIGH** that the conflicts are real; the recommended resolutions are MEDIUM by construction

**Research date:** 2026-08-09
**Valid until:** 2026-09-08 (30 days). The in-repo decisions are stable — this is a locked spec set. The external material (PostgreSQL 17 semantics, the Alembic async recipe) is stable on a multi-year horizon; only the pinned package versions age.
