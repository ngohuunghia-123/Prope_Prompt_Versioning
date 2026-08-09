# API Coverage — Phase 1: Data model, pricing, and retention

> Deterministic detector result (`bin/lib/api-coverage.cjs --json` over the ROADMAP phase scope):
> `{"detected": false, "signals": []}`.

No external API integration: this phase creates a PostgreSQL 17 schema, an Alembic migration chain,
and in-process Python functions (`resolve_price`, `compute_cost`, `write_records`,
`reprice_unpriced`, `delete_expired_bodies`). It integrates no external API, SDK, or service —
call-ledger has `external_services: []` and `dependencies: []`, and "No internet egress. It stores
what it is handed" is the module's stated property (`docs/modules/call-ledger.lock.yml:233-238`).

The module's own six management routes (`POST /api/v1/prices`, `GET /api/v1/prices`,
`GET /api/v1/prices/unpriced`, `PUT /api/v1/workspaces/{id}/spend-ceiling`,
`PUT /api/v1/workspaces/{id}/retention`, `/healthz` + `/readyz`) are **exposed** surfaces owned by
this project, not a third-party API being consumed, and the ROADMAP places all of them in Phase 2.
The RabbitMQ broker seam (INT-018) is Phase 2's; `aio-pika` is deliberately absent from this phase's
dependency set.
