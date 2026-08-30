# 04 — HITL: the cache is not a decision record

The cache stores **no human decision**. Nothing in it is a proposal, an approval, a dismissal
or a review. A cached suggestion is an offer that a person acts on (ticks a dataset) exactly
like a fresh suggestion — the cache only changes whether the offer cost a model call.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | What the cache is not | Not a `improvement.proposal`, not a `readiness.report`, not a `history_event`. It is derived, disposable, TTL'd data. It carries no actor, no status, no decision field |
| D2 | What a person still does | Unchanged: the suggestion is advice; the tick that attaches a dataset is the write, and it is a person's own act. The cache never auto-attaches, never auto-runs, never auto-releases (SR-6 posture inherited) |
| D3 | No confidence routing | A cached suggestion is served with the same confidence field the gate produced. There is no "this came from cache" downgrade, no confidence-based branching — the answer is byte-identical, so routing on provenance would be theatre |
| D4 | Audit trail | There is nothing to audit. A cache row is not a decision a reviewer needs; the proposal/inbox and history paths are untouched. `llm_cache_total` is a metric, not an audit log |
| D5 | TTL is the safe default | A 24h-expired suggestion simply disappears and the next click is a fresh call. Expiry is not a decision and needs no human action, the same way `readiness.lane_b_cache`'s 30-day retention needs none |

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Cache row read as a decision record | no decision columns exist (D1); schema-invariant test |
| Cached answer auto-attaches a dataset | the attach is a person's tick, unchanged (D2) |
| "Cached" confidence treated differently | byte-identical answer, no provenance branch (D3) |
| Expiry looks like data loss | TTL is the designed default (D5) |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| H1 | blocker | Cache is write-once derived; no status/actor/decision columns | D1 |
| H2 | blocker | No auto-act on a hit | D2 |
| H3 | med | No provenance-based confidence branch | D3 |
| H4 | med | TTL expiry requires no human action | D5 |
