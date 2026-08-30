# 01 — Orchestration: state, concurrency, termination

Stack: **custom** (FastAPI app + Prope worker, Postgres with RLS). Shape: cache (pipeline).
Step list from `00-shape.md` D1, verbatim.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | State schema | The cache row is the whole state: `(workspace_id, cache_key, program, model, findings jsonb, input_tokens, output_tokens, created_at)`. No separate header/child tables — a cache row is a leaf, not a run. `program` is the string program name (`suggest_datasets`, later `draft_cases`) so the same table serves every future caller without a per-module table |
| D2 | Merge rules | None. The row is write-once; `ON CONFLICT DO NOTHING` is the whole merge. A hit is a read, a miss is a read-then-insert; there is no second writer to a row |
| D3 | Graph | Linear, no branches. `compute_key → read_cache → (hit: return) / (miss: call → gate → store → return)`. The only "edge" is the read-failure-is-a-miss and write-failure-is-returned-fresh degradation |
| D4 | Persistence | Postgres is the store. A crash between call and store loses the fresh answer (the caller still returns it), and a crash before the store means the next identical ask pays again — which is correct: the cache is an optimization, and losing an optimization is not a corruption |
| D5 | Resume semantics | n/a — there is no long-running graph to resume. A retried request recomputes the same key and either hits or pays once more; `ON CONFLICT DO NOTHING` prevents double-storage |
| D6 | Termination set | Four outcomes, all counted: **hit** (served from cache), **miss_fresh** (called and returned), **miss_stale** (a stored row existed but failed the gate on read, so it was dropped and the call ran — the poisoned-row path), **miss_degraded** (cache read/write failed and the call ran). Only the first is a "cache success" |
| D7 | Max iterations | One. There is no retry loop in the cache; the underlying provider call keeps its existing SDK retries (3) and circuit breaker. The cache never retries a store |
| D8 | Budget caps | A hit costs zero. A miss costs exactly the existing one call's `max_tokens`-bounded spend. The cache adds no new spend surface; `llm_cache_cost_saved_usd_total` is the *avoided* spend, computed from the stored token counts of a hit |
| D9 | No-progress detector | n/a — no loop. A poisoned row (gate fails on read) is dropped and counted (`miss_stale`), never served and never retried into a loop |
| D10 | Retry placement | The cache itself never retries. Provider retries live in the shared client (unchanged); the breaker is unchanged. A cache write that fails is logged and the fresh answer is returned (D8 of shape) |
| D11 | Partial failure | Complete-what-succeeded: a failed store still returns the fresh gated answer; a failed read is a miss. The cache never sits between the caller and a correct answer |
| D12 | Pause and resume | n/a — no HITL, no proposal, no TTL-survives-restart concern beyond the row's own `created_at` (a TTL read filters on it; a restarted process recomputes the same key) |
| D13 | Reflection | Off. The cached answer is not re-judged on read beyond the gate (shape D11) — re-judging would make the cache a second model call |
| D14 | — | n/a (D13 off) |
| D15 | Event volume | Bounded: one row per (workspace, key); a key is content-addressed, so edits mint new keys; TTL bounds growth. `findings` is the gated suggestion JSON array (≤ `SUGGESTION_CAP` entries) |
| D16 | Concurrency | Two simultaneous misses of the same key: two calls, one stored row (`ON CONFLICT DO NOTHING`), the loser re-reads the winner's bytes. No locks, no advisory locks, no queue |

## D3 — the graph

```mermaid
flowchart LR
    suggest["suggest_datasets<br/>(existing)"] --> key["compute_key<br/>(content hash)"]
    key --> read["read_cache<br/>SELECT by (workspace_id, cache_key)"]
    read -->|"hit, gate passes"| hit["return gated suggestions<br/>cost = 0"]
    read -->|"hit, gate fails"| drop["drop row, count miss_stale"]
    drop --> call
    read -->|"miss / read error"| call["call aforward<br/>(breaker, unchanged)"]
    call --> gate["gate (existing _gated)"]
    gate --> store["store ON CONFLICT DO NOTHING"]
    store -->|"write ok / write failed"| fresh["return fresh gated suggestions"]
```

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Stale answer after a body edit | content-address: a new body is a new key (shape S2) |
| Stale answer after a signature/instruction edit | `program_schema_version` in the key, bumped in the same commit (shape S2) |
| Stale answer after a catalogue move | `catalogue_version` in the key (shape S2) |
| Poisoned row served | gate re-run on every read; a row that fails is dropped and counted `miss_stale` (shape S3) |
| Cache outage blocks suggestions | read error = miss; write error = return fresh; logged, never raised (shape S5) |
| Cross-tenant read | key is a content hash (no prompt id in the key), row is tenant-scoped by RLS (shape S4) |
| Unbounded growth | TTL + content-address; a retention sweep is a recorded follow-up (shape D13) |

## Build handoff rows (Prope-specific)

| Must exist in code | Proven by |
|---|---|
| `app_agent/cache.py`: `Cache` protocol + `NoOpCache` + `PostgresCache` | unit test: `NoOpCache` returns `None`; `PostgresCache` round-trips |
| `evaluation.llm_cache` table (migration `0055`) | migration applies; tenant-coverage + schema-invariant tests walk it |
| `compute_key` in `app_agent/cache.py` (or `evaluation/`) | unit test: two equal inputs → equal keys; any changed input → different key |
| `suggest_datasets` accepts `cache` param, defaults to `NoOpCache` | existing tests pass unmodified; a cache test injects a fake |
| Store only gated output + tokens; never body/title | row-content test asserts no body/title columns exist |
| Read failure is a miss; write failure returns fresh | fault-injection tests on `PostgresCache` |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| O1 | blocker | Four termination outcomes counted | metrics (D6) |
| O2 | blocker | `ON CONFLICT DO NOTHING` + re-read is the only arbiter | migration + repository |
| O3 | blocker | Gate re-run on every read; poisoned row dropped, never served | D4/D11 + test |
| O4 | blocker | Cache failure never raises to the caller | D8/D11 + fault-injection test |
| O5 | high | Key covers every input the program reads | D2 + key test |
| O6 | high | TTL enforced at read, not at write | repository predicate |
| O7 | high | No prompt id in the key; row tenant-scoped | D2 + RLS test |
| O8 | med | No process-global cache; per-caller injection | D7 + module-map test |
| O9 | med | Cost-saved is computed from stored tokens, never guessed | D8 + metric test |
| O10 | med | Retention sweep is a recorded follow-up, not a silent gap | D13 + this table |
