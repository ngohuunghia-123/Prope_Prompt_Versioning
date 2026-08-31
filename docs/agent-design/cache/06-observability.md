# 06 — Observability: the cache is a metric, not a trace

Prope's primitives are Prometheus counters/gauges on `/metrics` and bounded log lines — not
OTel traces. The cache is a request-path optimization, so its observability is three counters
and one cost-saved counter, plus log lines that carry counts and never content.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | Trace structure | n/a — there is no run row and no node graph for a cache read. The suggestion's existing log line is the only span-like record, and it already carries `suggestion_count`, `dropped`, `input_tokens`, `output_tokens`. A hit adds nothing to it (a hit has no tokens to report; the stored `input_tokens`/`output_tokens` are what the *original* call spent, and they feed the cost-saved metric, not the log) |
| D2/D3 | Convention + insulation | The module's own `llm_cache_*` metric names ARE the insulation; no `gen_ai.*` attributes are adopted. Dashboards read the metric names, never framework telemetry |
| D4 | Correlation | A cache row is correlated by `(workspace_id, cache_key)` — a hash. It is deliberately NOT correlated to a prompt id or run id (guardrails D4). The log line carries the program name and the outcome; that is the whole correlation surface |
| D5 | Content capture | **Off in telemetry**: no body, no title, no suggestion row, no cache key in any metric or log line (guardrails D10, A-046). The stored `findings` JSON is product data behind RLS, not a telemetry leak |
| D6 | Cardinality | Labels are closed enums: `feature` (a fixed set: `suggest_datasets` today; the set is extended in the same commit that wires a caller), `result` (`hit`/`miss`), `op` (`read`/`write`). No workspace, prompt, user or model-name labels (ADR-0030) |
| D7 | SLIs | **Cache efficiency**: hit rate per feature (`llm_cache_total{result="hit"} / total`). **Availability**: `llm_cache_errors_total` — the fault-isolation proof (read failure is a miss, write failure returns fresh) is only visible if errors are counted. **Cost**: `llm_cache_cost_saved_usd_total` (the avoided spend, from stored token counts × the existing price table) |
| D8 | Quality signal | The hit-rate trend is the churn detector (05-D5): a stable catalogue + stable model should drive hit rate up; a drop is the first sign of churn worth a ticket. There is no alarm in v1 — the cache is an optimization and a churn drop degrades to "uncached", which is the state the product shipped in |
| D9 | SLOs | None new. The cache has no SLO because it has no user-visible failure mode: a total cache outage is indistinguishable from the pre-cache product (every call is a miss). Adding an SLO to an optimization would be nines-worship |
| D10 | Burn-rate alerting | A ticket only on a sustained `llm_cache_errors_total` rate — not because the cache matters, but because a cache that *fails* rather than misses is a bug in the seam, and a bug in the seam is the one thing that could make the cache a dependency (shape S5) |
| D11 | Cost attribution | `llm_cache_cost_saved_usd_total` is on **Prope's meter** (the app-owned model's meter), beside `advisor_cost_usd_total`. It is never a cost delta and never a `ledger.call_record` — the same rule every other app-agent cost metric carries |
| D12 | Cache accounting | The whole point of this chapter: a hit's avoided cost is accounted (D7); the stored token counts make the avoided cost real rather than estimated. This is the "cache token accounting" that `cache=False` previously made n/a (06-D12 of the improvement pack) — now it exists, on Prope's meter, from actual tokens |
| D13 | Served model | The stored row carries `model`; the metric does not (cardinality). An operator investigating a hit-rate change reads the row's `model` and the deployment's `APP_AGENT_MODEL` — the key already invalidates on a swap (02-D4) |
| D14 | Retention | Metrics ~90d via existing Prometheus config; cache rows TTL 24h (guardrails D7); the stored suggestion JSON is the only content and it expires with the row |
| D15 | Tooling | Existing Prometheus + Grafana; no new dependency |
| D16 | Dashboards | One panel on the evaluation view: `llm_cache_total{feature="suggest_datasets"}` as hit/miss stacked, plus the cost-saved counter. Forty panels is nobody's incident view |

## New metric definitions

```
llm_cache_total{feature, result}          # result = hit | miss   (miss includes miss_stale, miss_degraded — see 01-D6)
llm_cache_put_total{feature, result}      # result = stored | write_failed
llm_cache_errors_total{feature, op}       # op = read | write
llm_cache_cost_saved_usd_total{feature}   # Prope's meter; a hit's avoided spend, from stored tokens
```

All labels closed-enum; `feature` is extended only in the commit that wires a caller.

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Cache silently never hits | hit-rate SLI (D7) |
| Cache fails instead of missing | `llm_cache_errors_total` + ticket (D10) |
| Cost-saved claimed without tokens | computed from stored tokens (D11/D12) |
| Hit rate drops on catalogue churn | D8 trend, no alarm (degrade = pre-cache state) |
| Body-derived value in telemetry | D5 + log-scan fixture (the existing `test_no_content_reaches_a_log_line_by_construction.py` walks this module) |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| B1 | blocker | No content in telemetry; log-scan fixture covers the new lines | D5 |
| B2 | blocker | No high-cardinality labels | D6 |
| B3 | blocker | Cost-saved from stored tokens on Prope's meter | D7/D11 |
| B4 | high | Cache errors counted (the fault-isolation proof) | D7/D10 |
| B5 | high | Hit/miss per feature visible on one panel | D7/D16 |
| B6 | med | No SLO added (documented why) | D9 |
