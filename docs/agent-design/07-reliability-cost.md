# 07 — Reliability and cost

Runs last: the breakers fire on 06's signals and the ladder is 02's models. Prope already owns
most of this concern at the client layer (`app_agent/client.py` + `circuit.py` + `build_lm`);
this chapter inherits it and names what the draft step changes.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | Timeouts | Every call explicit — **except the draft, which must NOT inherit the shared client's 5.0s**: a 6000-token body edit needs its own wall clock. Draft calls pass `timeout=120` (env-tunable, `IMPROVEMENT_DRAFT_TIMEOUT_SECONDS`) through `build_lm`; triage keeps its existing setting. Never an SDK default |
| D2 | First-token timeout | n/a — no streaming in this pipeline (batch JSON prediction); the total-call timeout is the whole story |
| D3 | Retryable errors | The OpenAI SDK's built-in policy (429/5xx only) is the allowlist; 4xx never retries. The **redraft loop is not a retry** — it fires only on typed validation failures with the error as feedback, never on transport errors (those go straight to the breaker → degradation) |
| D4 | Backoff | SDK jittered exponential (existing); nothing new to add — and the pipeline adds no synchronous retry of its own |
| D5 | Retry counts | Draft path: 3 SDK attempts within 120s (background context — a person is polling a run, tolerance is minutes); triage unchanged |
| D6 | `Retry-After` | Honoured by the SDK (existing) |
| D7 | Retry/hedge budget | Retry volume is structurally bounded: one run per human click, single-active-run lock, one open proposal per prompt. A token bucket would guard a load that cannot exist; recorded instead of built |
| D8 | Hedged requests | Off (default) — and pointless here: no latency-sensitive surface |
| D9 | Circuit breaker | The improvement module owns its **own `CircuitBreaker` instance** around the draft + triage calls (same class the dataset drafter uses: ≥10 samples, >50% failure, 30s cooldown) — one breaker per feature, which in a single-provider system is the per-(provider, model) granularity that exists. Repeated clicking during an outage hits an open breaker, not the provider |
| D10 | Half-open | Existing breaker behaviour (cooldown expiry = single probe) — sufficient at this traffic |
| D11 | Fallback ladder | One rung: **App Agent → typed degradation.** No second provider is configured; pretending otherwise with a same-provider "fallback" would be the default mistake. The ladder ends in something a person reads: the run's `drafter_unavailable` outcome with a retry action, findings intact |
| D12 | Degraded mode | Defined per surface: run card shows "drafting unavailable — findings kept, retry when ready"; no fabricated proposal, no silent no-op (the run's termination reason makes inaction visible — orchestration's silent-no-op rule) |
| D13 | Fallback parity | n/a — no alternate model rung (02-D12); the gate suite runs model-agnostically and would evaluate any future rung as a condition of adding it |
| D14 | Load shedding | Nothing to shed: traffic is human-rate, lock-capped, proposal-capped. Written down so the absence is a decision |
| D15 | Cost caps | **Before the spend, in code**: draft spend bounded by `max_tokens` on the call (6000) — the ceiling cannot be exceeded because the call cannot exceed it; probe spend bounded by the per-run case cap (40) checked **before probe dispatch**, and per-workspace probe budgeting follows the module's existing probe-cost pattern. Nothing is checked after the money |
| D16 | Cap shape | No tenant cliff exists: the per-run caps are per-attempt and tiny; a run that hits a cap degrades to a typed outcome, and the *workspace's* existing spend-ceiling UX (acknowledgement-gated, not cut-off) governs anything larger |
| D17 | Cost alarms | On 06's cost view: daily thresholds at 50/80/100% of the improvement draft budget, plus a **per-run outlier alarm** (single run > N× median draft cost — the loop-bug detector that infrastructure graphs cannot see) |
| D18 | Telemetry degradation | In-process counters and pure-function rails cannot fail a request; the provider call is the only dependency and it degrades by design (D11/D12) |

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Retry storm | SDK retries only, breaker above them, click-rate traffic |
| Compounded default timeouts | explicit 120s draft timeout (D1) — the shared 5s client default explicitly overridden |
| Provider outage | breaker opens → typed degradation → retry button; findings survive |
| Loop-bug spend | per-run outlier alarm (D17) + max_tokens + case caps |
| Gate re-paid on crash | orchestration D4: gate result persisted on the node before the proposal write |
| Breaker wraps everything globally | module-owned instance, per feature (D9) |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| L1 | blocker | Explicit timeout on every call; draft overrides the 5s default | D1 |
| L2 | blocker | Retryable allowlist; 4xx never retries | SDK policy + redraft≠retry (D3) |
| L3 | blocker | Jittered backoff | SDK (existing) |
| L4 | blocker | Cost caps enforced before spend | max_tokens + pre-dispatch case cap (D15) |
| L5 | high | Breaker per feature with numeric thresholds | module instance (D9) |
| L6 | high | Ladder named, ordered, user-readable end | one rung + typed degradation (D11/D12) |
| L7 | high | Ladder parity | n/a — no second rung; condition written (D13) |
| L8 | high | Retry/hedge budget | structurally bounded (D7), recorded |
| L9 | high | Telemetry/guardrail failure never fails the run | in-process (D18) |
| L10 | med | First-token timeout | n/a — no streaming |
| L11 | med | Multi-threshold + outlier cost alarms | D17 on the cost view |
| L12 | med | Load-shedding priorities written | D14 |
| L13 | med | Progressive cap, no cliff | D16 |
| L14 | low | Breaker exercised | CI kill-provider test |
