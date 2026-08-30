# 02 — Model selection: the key is the model

Runs on **App Agent only** (shape D1): `APP_AGENT_MODEL` via `build_lm()`, temperature 0, cost
on Prope's own meter. The per-workspace provider dispatch (gateway / eval runs / playground)
is out of scope — that is workspace money and the latency is the product.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | The one model | `APP_AGENT_MODEL` (default `gpt-4o-mini`), exactly as every DSPy program builds it today. The cache is keyed on the model name (D4) so a model swap invalidates rather than silently serves a different model's answer |
| D2 | Temperature | `0.0` — the existing setting, and the reason caching is sound: a deterministic call's answer is a pure function of its inputs, which is the property the cache keys on. A non-zero temperature would make the cache serve a *sample*, not the answer |
| D3 | `extra_body` in the key | The reasoning tier's thinking setting changes what the model returns (the `dspy_runtime.build_lm` docstring documents a 26-pair measurement where it changed the latency tail without changing routing output — but it *can* change output on a reasoning model). `extra_body` is therefore part of the key (shape D2) |
| D4 | Model name in the key | `app_agent_model` is a key component. `APP_AGENT_MODEL` is env-configured per process; two deployments with different models must never share a cache row. On a shared database this is what keeps a `gpt-4o-mini` answer from being served to a `gemini-2.5-flash` deployment |
| D5 | `num_retries` / `timeout` not in the key | They change transport, not semantics. Two callers with different timeouts asking the same question get the same answer; keying on them would fragment the cache for no correctness gain |
| D6 | `max_tokens` not in the key | A higher ceiling does not change what the model *says* for a bounded answer; the stored answer is the gated output regardless of the ceiling that produced it. Keying on it would double rows for identical answers |
| D7 | Migration protocol | Bumping `program_schema_version` (a single constant in `app_agent/cache.py`) is the documented way to invalidate on a signature/instruction edit. It is bumped in the same commit as the edit; no other invalidation mechanism exists in v1 |
| D8 | Catalogue moves | `catalogue_version` is a module constant that the caller includes in the key (the suggester's catalogue block is built from `catalogue.list_builtin_datasets()` + workspace rows; a version constant is added beside it). Bumping it invalidates every suggestion that could have changed because the library moved |
| D9 | Pinning + served model | The stored row carries `model` (the configured `APP_AGENT_MODEL`) and the hit re-gates without re-calling. A silent model swap shows up in the metrics (`llm_cache_total{result="hit"}` continuing while `APP_AGENT_MODEL` changed) and in the key, not as a wrong answer |
| D10 | Degradation ladder | One rung: App Agent → cache miss (the cache is never a rung that "answers"; a miss is just the existing uncached call). The ladder is unchanged from today; the cache only removes repeat rungs |

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Model swap serves yesterday's model's answer | model name in the key (D4) |
| Reasoning-tier `extra_body` changes output | `extra_body` in the key (D3) |
| Signature edit serves old answers | `program_schema_version` bumped in the same commit (D7) |
| Catalogue edit serves stale suggestions | `catalogue_version` in the key (D8) |
| Two deployments share a database and a cache | model name + schema version in the key (D4/D7) |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| M1 | blocker | Model name in the key | D4 + key test |
| M2 | blocker | `extra_body` in the key | D3 + key test |
| M3 | blocker | Schema-version bump protocol documented and tested | D7 + key test |
| M4 | high | Temperature 0 documented as the caching precondition | D2 (this chapter) |
| M5 | high | Catalogue-version invalidation wired for the suggester | D8 + key test |
| M6 | med | Transport settings excluded from the key, with the reason written | D5/D6 (this chapter) |
