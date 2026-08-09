# ADR-0027 — One PostgreSQL database, one schema per module, two roles

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — cited as `Inherited` by every module's Database row
**Related**: A-013, A-037, A-048, A-072, A-103, A-118, A-119, A-124, A-125, A-128, ADR-0019,
ADR-0023, ADR-0025, ADR-0035, BR-03

## Context

`00_context.md#constraints` names PostgreSQL in the inherited stack row, but nothing in the repository
implements it: `sqlalchemy`, `alembic` and `psycopg2` are commented out of `requirements.txt` and
`docker-compose.yml` declares no database service. So the engine is chosen here for the first time.

Four decisions already accepted narrow the engine almost to a point:

- **ADR-0025** makes `history_event` append-only *by database privilege* — the application role holds
  `INSERT` and `SELECT` and not `UPDATE` or `DELETE`. That requires a role system.
- **ADR-0023** requires property-history's `append()` to run **on the caller's connection inside the
  caller's open transaction**. Two databases cannot share a transaction.
- **BR-03**, non-negotiable in `00_context.md#constraints` — *"Only revisions in status `Approved` may
  be released or resolved by the gateway"* — is enforced *"by a database constraint, not application
  code"*.
- **A-124, A-119, A-125, A-118, A-103** together need a validated `jsonb` payload, partial indexes on a
  nullable column, a monotonic `bigserial`, a set-returning permission filter evaluated in SQL, and an
  aggregate updated inside the writer's transaction.

A-013 (*"Search is keyword and filter, not semantic"*) means full-text search stays inside the engine
and no second search service is required.

The open question is not the engine but the **boundary**. `module_map.md` forbids specific edges —
`call-ledger → anything`, `access-control → anything but property-history`, `property-history →
anything` — and states plainly why each would be a defect. In a single database with a single schema,
nothing prevents the join those edges forbid. That is the same defect ADR-0025 was written to remove:
a rule everyone agrees to and nothing enforces. This project has now rejected convention-as-enforcement
twice, in BR-03 and in ADR-0025, both times on the grounds that a rule which *is* the product gets
engine-level enforcement.

## Decision

**PostgreSQL 17, one instance, one database, one schema per module, and two roles.**

- **Eight schemas**, named for the module that owns them: `registry`, `evaluation`, `release`,
  `gateway`, `provider`, `ledger`, `access`, `history`. Every table lives in its owner's schema. A
  query that crosses a forbidden edge becomes visible in its own text — `ledger.call_record` sitting
  beside `registry.revision` reads as wrong to a reviewer and is greppable in CI, which is the property
  a shared `public` schema cannot offer.
- **Two roles.** `prope_migrate` owns all schemas and objects and holds DDL rights; `prope_app` is the
  runtime role and holds only DML. **One connection pool**, because the runtime uses one role.
- **ADR-0025's carve-out ships as a migration**: `prope_app` receives `INSERT` and `SELECT` on
  `history.history_event` and is never granted `UPDATE` or `DELETE`. The privilege is asserted by a CI
  test that attempts both against the application role and requires the *database* to refuse.
- **The two-role split is what makes ADR-0035 possible.** `prope_migrate` owns the tables and therefore
  bypasses row-level security; `prope_app` does not own them and is subject to it. Tenant isolation and
  append-only enforcement are the same mechanism applied twice.
- Cross-schema grants are explicit and minimal, and they follow the dependency direction the module map
  already draws — five modules receive `INSERT` on `history.history_event`, three additionally receive
  `SELECT`, and no module receives any privilege on `ledger.*`, which is a sink.
- **A-128** records the access layer: SQLAlchemy 2.0 async with Alembic and asyncpg, with raw SQL for
  the gateway's resolve read and A-118's `visible_subject_filter`.

## Alternatives rejected

**SQLite.** Rejected on three independent counts, any one of which is fatal. It has no role system, so
ADR-0025 cannot be implemented at all and "append-only" reverts to the intention that ADR was written
to replace. Its single-writer locking makes A-037's durable spill contend directly with gateway traffic
writing call records. And its JSON support cannot express A-124's validated payload with the indexes
A-119 requires.

**One database per module.** Rejected by ADR-0023, not by cost. Property-history's append runs inside
the caller's transaction, and a transaction does not span two databases. Adopting this would silently
downgrade five lock files' *"synchronous, same transaction"* promise to *"almost always"* — which is
precisely the failure ADR-0023 exists to prevent. It would also make BR-03's cross-table constraint
unexpressible.

**One shared `public` schema with the same two roles.** Rejected as the cheapest option that keeps the
defect. It satisfies ADR-0025 and nothing further: module boundaries would rest entirely on reviewer
memory, which is the enforcement model this project rejected in BR-03 and again in ADR-0025. It is also
the one alternative that is *expensive* to leave later — retrofitting schemas means `ALTER TABLE SET
SCHEMA` plus rewriting every query in the system, whereas adopting them on day zero costs a prefix.

**Schema per module with a role per module.** Rejected as the right idea at the wrong time. It is the
genuinely enforced version — PostgreSQL refuses a forbidden join outright rather than making it
visible. It costs eight connection pools inside one container against PostgreSQL's default 100-connection
limit, and eight grant matrices that must stay correct as tables are added. That is real weight against
a boundary that has not yet been violated once, and it can be adopted later **without moving any data**,
because the schemas will already exist. This is the asymmetry that decides it: schemas are expensive to
retrofit, roles are not.

**MySQL or MariaDB.** Rejected on capability rather than preference: no `jsonb` with the indexing A-119
needs, weaker partial-index support, and no row-level security, which would leave ADR-0035 with no
mechanism.

## Consequences

- Every module's Database row is `Inherited` citing this ADR. No module gets its own datastore, and a
  module that wants one must supersede this ADR rather than add a container.
- One connection pool for the whole application, which keeps the pool arithmetic simple against
  PostgreSQL's connection limit as `app` and `worker` both scale.
- Schema-qualified names appear in every query and every migration. That is the intended cost: it is
  what makes a forbidden edge legible without a linter.
- A cross-schema join remains *possible*. This ADR makes it visible, not impossible; ADR-0035 makes the
  tenant half of the problem impossible. Choosing role-per-module later closes the remainder.
- `prope_migrate` becomes a deployment credential distinct from the runtime one, which is what lets
  ADR-0031 run migrations as a separate step before the application restarts.

> **Extended 2026-08-09 (step 4, property-history's pass) — the title now says "two roles" and there are
> three.** ADR-0035 made `prope_app` RLS-subject, which means a query spanning workspaces returns zero
> rows. That left `prope_migrate` — the only role that can `UPDATE` or `DELETE` a history row
> (ADR-0025) — as the sole credential able to run A-126's hand-run Success SQL. **ADR-0037 adds
> `prope_report`: `LOGIN`, `BYPASSRLS`, `SELECT` only, used by people and by no application code.**
> Everything above stands unchanged: schema-per-module, the two *application* roles, and the rejection
> of role-per-module (which was about eight credentials and eight pools carried by the application, and
> is not what this adds).
