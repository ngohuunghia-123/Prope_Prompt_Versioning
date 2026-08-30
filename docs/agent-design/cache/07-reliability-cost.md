# 07 — Reliability and cost: the cache must never be a dependency

The cache sits in front of the existing breaker-wrapped provider call. It must not add a
failure mode to that call, must not re-pay on a crash, and must never spend money it was not
asked to spend.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | Timeouts | The cache adds no timeout of its own. A Postgres read/write under the caller's existing DB session has the session's own bounds; a hung cache read is a hung transaction, and `workspace_transaction` already owns that. No new wall-clock knob |
| D2 | First-token timeout | n/a — the cache is not a streaming surface; a hit is one row read, a miss is the existing call |
| D3 | Retryable errors | The cache never retries. A failed read is a miss (shape D8), a failed write is a returned-fresh (shape D8). The provider call keeps its SDK-only retry allowlist (429/5xx), unchanged. The redraft loop is untouched and is not a retry of the cache |
| D4 | Backoff | None new. The provider SDK's jittered exponential backoff is unchanged |
| D5 | Retry counts | Unchanged per caller. The cache adds zero retries; a write that failed once is not retried once (the fresh answer is already in hand) |
| D6 | `Retry-After` | Honoured by the SDK (unchanged) |
| D7 | Retry/hedge budget | The cache structurally removes work rather than adding it: a hit is one SELECT, a miss is the existing one call. There is no retry volume to budget |
| D8 | Hedged requests | Off (unchanged) — the cache is not latency-sensitive; it is *cost*-sensitive |
| D9 | Circuit breaker | The cache sits **inside** the breaker wrap for the miss path (the existing `_breaker.call` is unchanged) and **outside** it for the read path: a cache read failure must not open the breaker, because the breaker protects the provider call, not the cache. A repeated cache-read failure is `llm_cache_errors_total{op="read"}` + ticket (06-D10), never an open breaker |
| D10 | Half-open | Unchanged (existing breaker behaviour) |
| D11 | Fallback ladder | One rung, unchanged: App Agent → typed degradation. The cache is not a rung — a miss falls through to the existing call, and a cache outage is indistinguishable from the pre-cache product (06-D9). There is no "serve stale on cache error" rung in v1: TTL expiry and content-address already bound staleness, and serving stale-on-error would make the cache a dependency the moment it failed |
| D12 | Degraded mode | A cache read/write failure is a miss/fresh-return, logged (shape D8), counted (`llm_cache_errors_total`). The person sees the same answer either way; there is no degraded UX to define |
| D13 | Fallback parity | n/a — no second model rung; the cache is keyed per model (02-D4) |
| D14 | Load shedding | Nothing to shed: traffic is human-rate (one click per person per prompt) and the cache *reduces* provider load. The DB read load of a hit is a single indexed PK lookup |
| D15 | Cost caps | **Before the spend, in code, unchanged**: a miss spends exactly the existing `max_tokens`-bounded call. The cache cannot exceed the ceiling because it does not add a call. The one new cost number is the **avoided** cost (`llm_cache_cost_saved_usd_total`), which is not spend and is on Prope's meter (06-D11) |
| D16 | Cap shape | n/a — a hit costs zero and a miss costs the pre-existing per-attempt call; there is no tenant cliff the cache introduces |
| D17 | Cost alarms | The existing per-meter cost view is unchanged. The cache's contribution is the cost-saved counter on the evaluation view (06-D16); no new alarm — a cache that stopped saving money degrades to the pre-cache product, which is not an incident |
| D18 | Telemetry degradation | In-process counters cannot fail the request; the cache's DB access is the one new dependency and it degrades by design (D11/D12) |

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Cache read failure opens the breaker | read path is outside the breaker wrap (D9) |
| Cache write failure re-pays | write failure returns the fresh answer; no retry (D3/D5) |
| Cache outage becomes a dependency | no serve-stale-on-error rung; a miss is the pre-cache product (D11) |
| Crash between call and store re-pays | accepted: losing an optimization is not corruption (01-D4); the next identical ask either hits or pays once |
| Cost ceiling exceeded by the cache | the cache adds no call (D15) |
| Serve-stale rung sneaks in | D11 written as a refusal, not an option |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| L1 | blocker | Cache failure never raises to the caller | D3/D12 + fault-injection test |
| L2 | blocker | Read path outside the breaker; miss path inside | D9 + test |
| L3 | blocker | No serve-stale-on-error rung in v1 | D11 |
| L4 | blocker | Cache adds no provider call; spend unchanged on a miss | D15 |
| L5 | high | No cache-initiated retry anywhere | D3/D5 |
| L6 | high | Cost-saved is avoided spend, on Prope's meter, never a delta | D15 + 06-D11 |
| L7 | med | Crash-between-call-and-store documented as accepted loss | 01-D4 |
| L8 | med | No new timeout/backoff/hedge surface | D1/D4/D8 |
