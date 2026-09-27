# 00 — Shape: cache

System: **App-Agent LLM call cache** — a per-workspace, deterministic, gated-answer cache in
front of every DSPy program call on Prope's own meter, with the eval dataset suggester as the
first consumer.

Artifact path: `docs/agent-design/cache/` · Repository: project root · Language: English.

## Shape reason

A fixed pipeline: key → read → miss → call → gate → store → return. The model never chooses a
step; there is no tool, no loop and no memory. **Considered `agent`, chose `cache` (a
pipeline, not an agent)** because the three decisions that matter — what goes in the key, what
may be served, and what may be stored — are all made by code before the model is asked anything.

The one consumer this design ships is the eval dataset suggester (`evaluation/advisor.py` →
`suggest_program.py`), the "recommend eval set" button: its inputs are exactly the closed
catalogue block plus a prompt title/body, its output is a pure function of those inputs, and
nobody has ever reported a case where the *suggestion* needed to be different on the second
click. That is the definition of a cacheable LLM call.

## Intake (recorded)

| Item | Answer | Source |
|---|---|---|
| Existing system | Every DSPy program call goes through `build_lm()` with **`cache=False`** (a security setting: DSPy's on-disk cache would write corporate prompt bodies into `~/.dspy_cache`); no LLM answer caching exists anywhere; `readiness.lane_b_cache` is the one DB fingerprint cache for model output | codebase |
| New in this design | (a) a shared, dependency-injected cache seam; (b) a deterministic content-addressed key; (c) per-workspace row + RLS; (d) `evaluation.llm_cache` table + migration `0055`; (e) suggester wired, with the drafter as a recorded follow-up | user |
| Actions / undo | The cache is write-once derived data. No person acts on it; an operator can `DELETE` a row (granted) or bump the schema version. Nothing about a suggestion is a write a person owns | inferred |
| Liability | None beyond the existing suggestion gate: a cached suggestion is byte-identical to the answer the gate would have produced. The gate is applied to cached rows too | inferred |
| Trigger | Request-driven: a person clicks "recommend eval set" → `suggest_datasets` → cache read → miss → one model call → gate → store → return | codebase |
| Threshold | n/a — the cache never degrades an answer; it only makes the second identical ask free | inferred |
| Model / meter | App Agent (`APP_AGENT_MODEL`), temperature 0; cache hit = zero spend on Prope's meter | codebase |
| Traffic | Low (one click per person per prompt), but the whole point is to make repeat clicks cost nothing and cut an availability dependency | inferred |
| Untrusted content | YES — the prompt body is untrusted data (A-020, A-046) and is hashed, never stored. The **stored** suggestion text is the model's gated output | inferred |

## Decisions

| # | Decision | Value | Overturned when |
|---|---|---|---|
| D1 | Scope | App-Agent DSPy calls only (the `app_agent` runtime): conversion, extraction, comparison, chat router/responder/drafter, eval drafter/suggester, improvement triage/draft, readiness Lane B. **Not** the per-workspace provider dispatch (gateway serving / eval runs / playground) — that is workspace money and the latency is the product | A workspace-owned call becomes pure-function-of-inputs AND the workspace asks to cache it |
| D2 | Cache key | Deterministic content hash of `(prompt_body, prompt_title, catalogue, program_schema_version, app_agent_model, extra_body)`. `program_schema_version` starts `1` and is a single constant, bumped on any signature/instruction edit so old answers are never served for new questions | Never — an LLM's output is not a pure function of its inputs unless the key says exactly what the question was |
| D3 | Storage | **One row per (workspace_id, cache_key)**, never per tenant-less global. `evaluation.llm_cache` (schema `evaluation`), write-once with `ON CONFLICT DO NOTHING` + re-read (the readiness freeze pattern, SR-1), tenant RLS (ADR-0035/0045) | A cross-workspace hit leaks whose prompt produced the suggestion — never |
| D4 | What may be served | Only the gated answer, re-run through the same gate as a fresh call. A row stores the raw model prediction fields; a hit re-coerces and re-gates so a gate bug fix invalidates nothing and a poisoned row cannot surface | Never |
| D5 | TTL / invalidation | TTL 24h (env `LLM_CACHE_TTL_HOURS`, default `24`), plus content-address (an edited body is a new key). No manual invalidation surface in v1; an operator `DELETE`s a row (granted) | A fresh suggestion must reflect a catalogue that moved — see `catalogue_version` in the key |
| D6 | What may be stored | Only the model's structured output fields after the gate, with `model`, `input_tokens`, `output_tokens`, `created_at`; **never the prompt body or the prompt title** (A-020 / A-046) | Never — this is the security rule the whole cache exists to keep |
| D7 | Cache-seam shape | `Cache` protocol in `app_agent/cache.py` with `async get(key) -> str | None` and `async put(key, value, meta)`. `NoOpCache` is the default; `PostgresCache` is created only when a caller opts in. Per-module injection, never a process-wide global | A global cache would silently cache a module nobody audited |
| D8 | Fault isolation | A cache read/write failure is **never** a failed suggestion. Read failure → miss; write failure → the fresh answer is returned and the miss is logged. The cache is an optimization, not a dependency | The cache becomes a data store a person relies on |
| D9 | Metrics | `llm_cache_total{feature, result}` (`hit`/`miss`), `llm_cache_put_total{feature, result}` (`stored`/`write_failed`), `llm_cache_errors_total{feature, op}`, `llm_cache_cost_saved_usd_total{feature}`. Closed enums only (ADR-0030); no prompt/workspace labels | — |
| D10 | Caller contract | A caller (e.g. `suggest_datasets`) passes the cache as a parameter (or `None`); the seam defaults to `NoOpCache` and every existing caller is byte-identical until it opts in | A caller needs caching and cannot name its inputs |
| D11 | Gate idempotence | `_gated()` is pure and already re-runs on a hit (D4). The cache stores the raw prediction so a **fresh gate** runs on read — this is what makes the cache safe | The gate becomes stateful |
| D12 | Concurrency | `ON CONFLICT DO NOTHING` + re-read is the arbiter; two simultaneous misses result in two calls and one stored row, and the second reader re-reads the winner's bytes (SR-1) | — |
| D13 | Follow-ups (not blockers) | Wire the eval-case drafter (`draft_cases`) — same shape, same seam; a later pass can wire conversion/extraction/readiness. A retention sweep on `created_at` if the table grows. Each is a separate change | — |

## D1 — the step list (verbatim, passed to every concern chapter)

1. `compute_key` — content hash over `(prompt_body, prompt_title, catalogue, program_schema_version, app_agent_model, extra_body)`
2. `read_cache` — one `SELECT` by `(workspace_id, cache_key)`; read failure → treated as a miss
3. `call` — the existing breaker-wrapped `program.aforward` (unchanged)
4. `gate` — the existing pure gate (`_gated`) over the fresh prediction
5. `store` — write the **gated** suggestion rows + model + tokens, `ON CONFLICT DO NOTHING`; write failure → the fresh answer is still returned
6. `return` — the gated suggestion tuple

## Cache failure modes owned here

- **Silent stale-answer:** a body edit produces a new key (content-address), a signature edit bumps `program_schema_version`, a catalogue move bumps `catalogue_version` — three independent invalidation axes, each in the key (S2).
- **Poisoned row:** a stored prediction that later fails the gate is dropped and the row is **not** served (D4) (S3).
- **Cross-tenant leak:** impossible by construction — the key is content-hashed, the row carries `workspace_id`, and the RLS predicate is the same one every evaluation table carries (S4).
- **Cache-is-the-dependency:** a cache outage never fails a suggestion; read failure is a miss, write failure is a logged miss (D8) (S5).

## Rails (output validation, decided at intake)

The cache carries no new rails beyond the existing suggestion gate, re-run on every read (D4/D11).
The one storage-side rail is a CHECK: `findings` (the stored suggestion JSON) must be a JSON
array, enforced in the migration — the same `jsonb_typeof = 'array'` shape `readiness.lane_b_cache`
uses.

## Supersession note

No ADR is superseded. `cache=False` on the DSPy LM **stays**: the new cache is Prope's own,
governed, per-workspace, gated and TTL'd — it is not DSPy's on-disk cache, and the security
reason for keeping prompt bodies off disk is unchanged. This design layers a governed cache in
front of the ungoverned one that was deliberately disabled.
