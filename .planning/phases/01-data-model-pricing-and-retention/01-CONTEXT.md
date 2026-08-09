# Phase 1: Data model, pricing, and retention - Context

**Gathered:** 2026-08-09
**Status:** Ready for planning

<domain>
## Phase Boundary

The `ledger` schema exists as a migration that **carries its own guarantees**, and a call's usage is priced correctly and irreversibly at write time.

**Delivers:**
- All five owned tables — `call_record`, `call_body`, `price_table`, `workspace_spend`, `spend_ceiling` — with RLS, grants, and constraints in the migration rather than in application code
- Write-time pricing against the append-only, effective-dated `price_table`, using the call's **own `created_at`**, storing `cost`, `currency`, and the `price_row_id` that produced it
- The `unpriced` / `unknown` value paths — a missing price row and a missing usage object are values, never zero
- Repricing that fills only previously-unpriced rows and never recomputes a priced one
- The batched body-deletion job driven by `expires_at`
- The project's Python/Alembic/test foundation, because this is the project entry point (`Depends on: Nothing`)

**Fixed out of scope by ROADMAP (do not absorb):**
- `enqueue`, the RabbitMQ drain, `check_spend_ceiling`, `get_run_totals`, and the six management routes — **Phase 2**
- Durability/direct-write fallback, idempotent upsert on `call_id`, the no-body-read-path route-table assertion, and the 50 rps load targets — **Phase 3**
- The 7-service runtime, Caddy, GHCR/CI deploy — owns no milestone yet (PITFALLS gap 4); not this phase's to invent

</domain>

<decisions>
## Implementation Decisions

### Project foundation

- **D-01:** Package tree is `src/prope/<module_id>/` — one installable `prope` package, each bounded context a subpackage (`src/prope/call_ledger/`) with its own internal layering. Mirrors schema-per-module one-to-one and gives release-control's owed import-linter contract real package boundaries to bind to. Horizontal `models/ services/ api/` layering is rejected — the module map states there is no "frontend" or "backend" module because neither owns a journey. — **Reversibility:** costly — a later move rewrites every import in every module and invalidates the import-linter contract.
- **D-02:** Tests run against a **real Postgres 17 via testcontainers-python**. A pytest session fixture starts the container, runs Alembic as `prope_migrate`, and hands tests a `prope_app` connection. Chosen because every Phase 1 guarantee — RLS returning zero rows, the T-006 REVOKEs refusing an UPDATE, effective-dated selection at a timestamp boundary — is only observable against a live engine; mocking the driver proves nothing. Accepted cost: Docker is a hard test dependency. A CI-service-container/local-compose split was rejected specifically because two provisioning paths drift, and the first drift reads as green CI over a broken local run. — **Reversibility:** costly — the fixture shape is inherited by all 24 phases' test suites.
- **D-03:** Phase 1 replaces **dependency and build config only**: a `pyproject.toml` pinning Python 3.13.x, FastAPI + uvicorn + pydantic v2, SQLAlchemy 2.0 + asyncpg, Alembic, pytest + testcontainers, and ruff; LangChain/LangGraph are dropped (Prope's ML stack is `n/a`); Makefile targets are repointed off `src.main:app`. `Dockerfile` and `docker-compose.yml` are **left untouched** — the real runtime is ADR-0033's and belongs to work that owns no milestone yet.
- **D-04:** **One linear Alembic chain, hand-written.** A single `alembic/versions/` history for all eight schemas, run as `prope_migrate`, one `alembic upgrade head` per deploy. Autogenerate may be used to draft a table diff but its output is never trusted or committed unreviewed: it cannot see RLS policies, grants, or triggers, and the first autogenerate after a policy lands proposes dropping what it cannot see. Branch-per-module was rejected — eight heads on one VM with one deploy, and cross-schema ordering (roles before any policy) stops being expressible in the chain. — **Reversibility:** one-way — restructuring a migration chain after it has run in any environment requires a hand-written reconciliation migration and a stamped history.

### Migration-carried guarantees

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

These are authoritative and read-only. Per `.planning/BSP-LINK.md`: do not edit anything under `docs/`. A spec that disagrees with the code is information — raise an `OQ-NNN` naming the exact lock file field and the conflict; do not patch the spec to agree.

### The module spec — read first
- `docs/modules/call-ledger.lock.yml` — `data.owns` (the five tables and their field lists and notes), `scope.in_scope` / `non_goals`, `security_requirements` (T-005, T-006, retention terms), `failure_modes`, `acceptance_criteria` AC-3, AC-4, AC-5, AC-8, AC-11, `test_plan`
- `docs/architecture/interfaces.md` — INT-018 through INT-021 and INT-028 (registered in Phase 2; read for the shape Phase 1's tables must serve)
- `.planning/BSP-LINK.md` — the phase → spec index and the "Out of bounds" rules

### Pricing and retention
- `docs/adr/0019-cost-is-priced-once-at-write-time.md` — priced at the call's own `created_at`; `price_row_id` stored on the record; append-only effective-dated prices; missing price = `unpriced`, missing usage = `unknown`, **never zero**; repricing fills only previously-unpriced rows
- `docs/adr/0039-call-bodies-are-excluded-from-the-backup.md` — `--exclude-table-data=ledger.call_body`; data only, so a restore yields an empty table rather than a missing one
- `docs/adr/0018-body-store-has-no-read-path-in-the-mvp.md` — why the sink has no reader, and why that is what lets it have no access-control edge

### Tenancy, roles, and the enforcement pattern
- `docs/adr/0027-one-database-one-schema-per-module-two-roles.md` — schema `ledger`; the role split
- `docs/adr/0037-a-third-role-reads-across-workspaces.md` — `prope_report`
- `docs/adr/0035-tenant-isolation-is-a-database-policy.md` — RLS deny-by-default, `SET LOCAL app.workspace_id` per transaction, `USING` + `WITH CHECK`
- `docs/adr/0040-the-ledger-writer-batches-per-workspace.md` — the drain and the retention job both group by `workspace_id`, one transaction each; `call_body` carries `workspace_id`
- `docs/adr/0045-every-table-is-tenant-scoped-unless-declared-global.md` — the coverage test walks every table in all eight schemas; `GLOBAL_TABLES` needs a written reason
- `docs/adr/0025-append-only-is-a-database-privilege-not-a-convention.md` — the precedent T-006's REVOKEs follow

### Stack
- `docs/adr/0026-python-and-fastapi-are-the-one-runtime.md` — Python 3.13.x pinned
- `docs/brainstorm/assumptions/A-128.md` — SQLAlchemy 2.0 async over asyncpg; Alembic also carries policies, constraints, extensions, triggers
- `docs/adr/0032-secrets-live-in-one-env-file-on-the-host.md` — one `.env`, `0600`, never in CI; holds the KEK
- `docs/adr/0033-one-vm-docker-compose-and-caddy.md` — the runtime Phase 1 deliberately does not build

### Known gaps this phase must plan around
- `.planning/research/PITFALLS.md` §2 — call-ledger **AC-1 and AC-2 are stated against an in-process queue and a spill file, neither of which exists**. Restate as "RabbitMQ unreachable" and "every message redelivered after an unacknowledged consumer restart". Both land in **Phase 3**, not here — but do not plan against the lock file's literal AC-1/AC-2 text anywhere.
- `.planning/research/PITFALLS.md` §4 — the deployment stack owns no milestone; this is why D-03 stops at dependency config.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

**None.** `src/` and `tests/` are empty. Treat the build as greenfield against the module specs, not as a brownfield extension.

### Established Patterns

No Prope code patterns exist yet — Phase 1 establishes them, and 23 phases inherit them. The surviving scaffold is boilerplate from a different project and is **not** a pattern to follow:

- `requirements.txt` — pins LangChain, langchain-openai, LangGraph; SQLAlchemy/Alembic/psycopg2 are commented out. Prope's ML stack is `n/a`. Replaced by D-03.
- `docker-compose.yml` — one `backend` service, a `./data` volume, `/health` healthcheck. Nothing to do with ADR-0033's 7 services. Left untouched by D-03.
- `Makefile` — `run` targets `uvicorn src.main:app`, which does not exist. `typecheck` calls mypy, which is not in the dependency set. Retargeted by D-03.
- `Dockerfile`, `eval/`, `presentation/`, `tokens.json`, `asset-spec.md`, `README_boilerplate.md` — boilerplate remnants; out of scope for Phase 1.
- `ruff.toml` — present; the one config worth keeping and building on.

### Integration Points

- **No inbound or outbound module edges.** `dependencies: []` and `outputs: []` are this module's defining property. `workspace_id` is a **value, not a foreign key** — the `access` schema does not exist until Phase 7, and call-ledger may not reference it even when it does.
- `prompt_id`, `version_id`, `revision_number`, `upstream_model`, `provider_config_id` are denormalised values on `call_record` by design, so the audit trail survives independently of the registry's current state.
- The only real integration point Phase 1 creates is the migration chain and the `workspace_transaction()` seam (D-04, D-08) that every later module builds on.

</code_context>

<specifics>
## Specific Ideas

- **Build database-first.** The migration carries the guarantee — constraint, privilege, policy, grant, trigger — and the application code is what the guarantee protects. This is the project's stated spine and it is why D-05, D-06 and D-07 all pull work into the migration rather than into services.
- **Never zero.** A missing price is `unpriced` and a missing usage object is `unknown`. ADR-0019 calls treating a missing price as zero "the most dangerous of these because it produces a working system" — an absent figure asks a question, a wrong figure answers it. Phase 1 success criterion 2 states it as "no row anywhere records a cost of zero", and that is testable as written.
- **Assert against the live engine, not the driver.** Applies to the REVOKEs (D-07), the RLS zero-rows behaviour (D-08), and the ADR-0045 walk (D-06). The lock file says this explicitly for T-006: "asserted against the live engine the way property-history asserts its own privilege, not by mocking the driver."
- **The retention alert measures the data, not the job.** `prope_call_ledger_oldest_body_age_seconds`, not job success — "a deletion job that runs successfully every night and deletes nothing looks healthy from the job's side." Phase 1's deletion work should be verified the same way: by direct query, not through an API that could be filtering.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

Noted but explicitly **not** deferred ideas (they are fixed ROADMAP boundaries, recorded so a planner does not mistake them for gaps): the enqueue seam, the broker drain, `check_spend_ceiling`, `get_run_totals` and the management routes belong to Phase 2; durability, idempotency, the no-body-read-path assertion and the load targets belong to Phase 3.

</deferred>

---

*Phase: 1-data-model-pricing-and-retention*
*Context gathered: 2026-08-09*
