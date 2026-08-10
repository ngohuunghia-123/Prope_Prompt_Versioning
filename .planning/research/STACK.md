# Stack: Prope

> Transcribed from `docs/build/gsd_handoff.md` section 2. Not researched by GSD — these are
> decisions already made and traceable to `docs/adr/`.
> Do not revise here; revise upstream and re-run the handoff.

Locked at BSP step 4. Full rationale and rejected alternatives in `docs/architecture/tech_stack.md`.

## Baseline

Inherited by every module unless that module's own row in `tech_stack.md` says `Deviated`.

| Concern | Choice | ADR |
|---------|--------|-----|
| Language | Python, pinned 3.13.x | ADR-0026 |
| Web framework | FastAPI + uvicorn + pydantic v2 | ADR-0026 |
| Database | PostgreSQL 17, one instance, one database, **schema per module**; roles `prope_app` / `prope_migrate` / `prope_report` | ADR-0027, ADR-0037 |
| Tenant isolation | Postgres row-level security, deny-by-default, `SET LOCAL app.workspace_id`; a missing filter returns **zero rows** | ADR-0035, ADR-0045 |
| Message broker | RabbitMQ 4.x; one queue, `prope.call_record`, plus its DLQ | ADR-0028 |
| Identity | Local — `user` table, argon2id, **server-side session rows**, HttpOnly same-origin cookie. No JWT | ADR-0029, ADR-0043 |
| Observability | Prometheus + Grafana; `structlog` JSON to stdout; bounded metric label cardinality | ADR-0030 |
| CI/CD | GitHub Actions → GHCR → deploy over SSH; the host pulls, never builds | ADR-0031 |
| Secrets | One `.env` on the VM, `0600`, git-ignored. Holds the KEK. Never enters CI | ADR-0032 |
| Runtime | Docker + docker-compose on one group-controlled Linux VM; **Caddy single ingress**, 7 services, 2 images | ADR-0033 |
| Frontend | React 19 + TypeScript SPA built by Vite, Tailwind 4; **Node in CI only**, baked into a `caddy:2` image | ADR-0052 |
| Interface language | **Vietnamese only in the MVP**, behind an i18n layer: keyed catalogue, no literal display strings. Statuses stay literal; the API returns a machine `code` the client translates | ADR-0053 |
| ORM / migrations | SQLAlchemy 2.0 async over asyncpg; Alembic. Alembic also carries RLS policies, constraints, extensions, triggers | A-128 |
| ML stack | `n/a` — Prope trains and serves no models | — |

## Deployment shape

**Seven services**: `caddy`, `app`, `worker`, `postgres`, `rabbitmq`, `prometheus`, `grafana`.

**Two images**:
1. The Python app image — run as `app` and as `worker` with different commands
2. The `caddy:2`-based image with the built SPA baked in

## Sanctioned privilege escalations

**Four `SECURITY DEFINER` functions are sanctioned** and a test asserts the set is exactly these four:

- `access.lookup_session`
- `access.lookup_api_key`
- `evaluation.claim_next_run()`
- `access.list_workspaces()`

Each returns identifiers only, never rows. Each must be `REVOKE`d from `PUBLIC` with an empty `search_path` (an owed acceptance criterion — see `PITFALLS.md`, coverage gaps).

## Notable rejections

- **Next.js** — rejected at ADR-0034. ADR-0034 is superseded by ADR-0052 (React SPA + Vite + Caddy), but Next.js itself remains rejected and ADR-0034's reasons survive the reversal.
- **Kubernetes, Vault, Keycloak, Kafka, Loki, distributed tracing** — all rejected by the A-012 *debuggable by one person* clause.
- **JWT** — rejected in favour of server-side session rows (ADR-0029, ADR-0043), because revocation must take effect on the very next request.
- **A second broker queue and broker-based cache invalidation** — proposed twice, rejected twice on merit. The gateway's 30 s resolution cache **expires**; nothing invalidates it (ADR-0012).
- **`tsvector` full-text search** — substring semantics (`'thentic'` matches `authentication`) are a required property; ADR-0048 uses a trigram index over a trigger-maintained document column.

## Sources

- `docs/architecture/tech_stack.md` — per-module rows, `Inherited` vs `Deviated`, rejected alternatives
- `docs/adr/` — 54 ADRs; `docs/adr/adr_index.md` is the index
- `docs/brainstorm/assumptions/A-128.md` — the ORM and migration choice
