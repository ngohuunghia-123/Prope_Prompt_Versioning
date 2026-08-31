# 03 — Guardrails: the cache is a governed store, not a body dump

The security posture of the existing agent calls is A-020/A-046: prompt bodies never reach
disk and never reach telemetry. `cache=False` on the DSPy LM is what keeps bodies off DSPy's
own disk cache. **This design adds a governed store and must not become the thing that
reintroduces the leak the `cache=False` setting exists to prevent.**

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | Untrusted-content map | The **prompt body and title** are untrusted data and are **hashed, never stored** (A-020). The **stored suggestion text** is the model's gated output — a bounded set of `{dataset_id, reason, confidence}` entries — which is product data the gate already owns. There is no other content in the system |
| D2 | The key is not a body copy | The cache key is a SHA-256 content hash. A row leaks nothing about the body that produced it; the hash is not reversible and is useless without the workspace's own body to recompute it |
| D3 | RLS is the tenant boundary | The row is scoped by `workspace_id` and policied exactly like every evaluation table (`enable_tenant_rls`, the `current_setting('app.workspace_id', true)` predicate, `WITH CHECK`). A cross-workspace read returns zero rows, not somebody else's suggestion |
| D4 | No prompt id in the key or the row | The key carries no `prompt_id` (a content hash is the identity); the row carries `workspace_id` only. There is no column a cross-tenant query could pivot on to enumerate a workspace's prompts |
| D5 | Gate on every read | A stored prediction is re-run through the same `_gated` coercion on every hit. A poisoned or tampered row either fails the gate (dropped, counted `miss_stale`) or is byte-identical to what the gate would have produced fresh. The cache never widens the gate |
| D6 | Storage-side CHECK | `findings` must be a JSON array (`jsonb_typeof(findings) = 'array'`), the same shape `readiness.lane_b_cache` carries. An unbounded or non-array value is refused by the database |
| D7 | Retention / TTL | 24h TTL enforced at read (a row older than the TTL is a miss, and the stale row is deletable). No content is long-lived; a body's hash and a bounded gated answer expire together |
| D8 | Grants | `SELECT`, `INSERT`, `UPDATE`, `DELETE` for `prope_app` on the cache table — DELETE because an operator must be able to evict a row (the only manual invalidation surface in v1, shape D5). `prope_report` gets SELECT (a report role may read metrics-shaped data; a cache row is derived, not a decision record) |
| D9 | No egress | The cache adds no outbound edge. It is a Postgres table, not a service; there is no new network surface, no new credential, no new dependency |
| D10 | No telemetry content | Metrics carry `{feature, result}` and `{feature, op}` closed enums only (shape D9, ADR-0030). Logs carry counts and the program name, never the body, never a suggestion row, never the cache key — the key is a hash but a hash is still content-derived and stays out of logs under A-046's rule |
| D11 | Module map | The cache lives in `app_agent` (shared runtime, already reached by every agent module on the same terms). `evaluation` keeps its own `llm_cache` repository; it does not read another module's table (test_no_cross_schema_sql stays green) |

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Body written to the cache | no body/title columns exist (D1); asserted by a row-content test |
| Cross-tenant read | RLS (D3) + no prompt-id column (D4) |
| Tampered row surfaced to a person | gate re-run on every read (D5) |
| Unbounded content stored | JSON-array CHECK (D6) + bounded gated fields |
| Body-derived value in telemetry | key is a hash and is excluded from logs (D10) |
| New outbound edge | none — a table, not a service (D9) |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| G1 | blocker | No body/title columns; row-content test | D1 |
| G2 | blocker | RLS policy present; tenant-coverage test walks the table | D3 |
| G3 | blocker | Gate re-run on read; poisoned row dropped | D5 |
| G4 | blocker | JSON-array CHECK in the migration | D6 |
| G5 | high | No prompt id in key or row | D4 |
| G6 | high | TTL enforced at read | D7 |
| G7 | high | Grants: app full CRUD, report SELECT-only | D8 |
| G8 | med | No content in logs; metrics closed-enum | D10 |
