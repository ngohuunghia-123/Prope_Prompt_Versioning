# 02 — Model selection

Steps from `00-shape.md` D1. Only two steps call a model (`triage`, `draft`); everything else is
deterministic code. Both call the **App Agent** (operator-configured via `APP_AGENT_MODEL`,
shared `app_agent` client + `dspy_runtime.build_lm`), on Prope's meter — decided at intake.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | Tier per step | `read_evidence`–`record_findings`: none (deterministic). `triage`: **small/mid** (ranking + one evidence sentence — the existing triage program). `draft`: **mid** (full-body editing generation; the whole point of this feature). `validate_rails`/`gate`/`persist`: none (pure code + probes). Both LLM steps resolve to `APP_AGENT_MODEL` today; the tier table exists so a future split (e.g. `APP_IMPROVEMENT_DRAFT_MODEL`) is a config change, not a redesign |
| D2 | Cheap-first policy | **Not used.** Traffic is one run per human click, rate-capped to one open proposal per prompt — a cascade's 40–60% savings are irrelevant at this volume and would add an escalation signal to measure. Revisit if triggers become automatic (shape D2's event-driven future) |
| D3/D4/D5 | Routing | n/a (no cascade). Recorded so the absence is a decision |
| D6 | Generation parameters | `temperature=0` (the `build_lm` default, existing). `max_tokens` set on **every** call: triage 1200 (existing), draft **6000** default via `IMPROVEMENT_DRAFT_MAX_OUTPUT_TOKENS` (full canonical body + bounded rationale). Rationale additionally length-bounded in the output schema (≤500 chars) |
| D7 | Structured output | DSPy signature + **pydantic model at the boundary** (`ProposedEdit{body, rationale, addressed}`), validated before rails run. No provider constrained-decoding path is used (matches the existing drafter/triage programs); the compensating controls are boundary validation + bounded re-prompt with the validation error as feedback (shape D5/D7) and typed degradation |
| D8 | Prompt caching | Off as a *managed lever*: `build_lm` runs with `cache=False` as a **security setting** (no prompt bodies on disk — existing rule, keeps holding). Provider-side prefix caching may still fire; hit rate not measured at this traffic. Revisit only if triggers automate |
| D9 | Batching | n/a — single-item manual runs; the gate probe already runs on `priority=batch` provider dispatch (existing) |
| D10 | Output discipline | The draft prompt asks for the edited body and *only* a short rationale; the rationale bound is enforced in the schema. No prose wrappers around the XML body |
| D11 | Fallback chain | `draft`/`triage`: **App Agent → degraded**. There is no second provider configured, so the honest chain member is degradation, not a silent same-provider retry: the run records `termination_reason="drafter_unavailable"`, findings stay open, the person can click again (the existing `DrafterUnavailableError` → 503 pattern, moved onto the run). The shared `CircuitBreaker` (module-owned instance) stops repeated clicks from hammering a downed provider |
| D12 | Eval parity across the chain | n/a (no alternate model member). The **gate** is the semantic parity check that matters here: any draft, from any model version, must clear the same suites — that is the design's centre of gravity |
| D13 | Self-hosting | Not required; `APP_OPENAI_BASE_URL` already allows a private endpoint if residency demands it — an operator concern, unchanged |
| D14 | Pinning | `APP_AGENT_MODEL` is operator config and **must be pinned to an exact version** (documented in `.env.example`); no floating `latest` in a deployed env. The served model id, token counts, and computed cost are recorded on the `improvement_draft` node's detail and on the cost metric — M2's queryable field |
| D15 | Migration protocol | Swapping `APP_AGENT_MODEL` is a regression event, not an edit: re-run the rails unit suite + the gate-discard integration test + a handful of seeded prompts, and expect the redraft rate to move. Written into the ADR's operational notes |
| D16 | Fine-tuning | No. Prompting + evidence-parameterized context + the closed rails cover this task; volume is far below any repayment arithmetic |

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Provider down | Breaker opens → typed `drafter_unavailable`; findings remain; retry is a click |
| Silent model swap by operator | Served model recorded per run node; unpinned alias flagged in ops docs; gate + rails suite is model-agnostic and runs in CI |
| Runaway generation | `max_tokens` on both call paths; token-per-run distribution visible via cost metric |
| Malformed model output | Pydantic boundary → typed rails failure → bounded redraft with the error as feedback → degradation, never garbage persisted |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| M1 | blocker | Pinned versions, no floating alias | operator config rule + `.env.example` note |
| M2 | blocker | Served model recorded per request | draft node detail: model id, tokens, cost |
| M3 | high | Tier per step in configuration | `APP_AGENT_MODEL` + documented split point |
| M4/M5 | high | Router/chain evals | n/a — no cascade, no alternate member |
| M6 | high | `max_tokens` on every call | triage 1200 / draft 6000, env-tunable |
| M7 | med | Cache hit rate measured | skipped at this traffic; `cache=False` is a security rule |
| M8 | med | Batch for latency-tolerant work | gate probe uses batch priority (existing) |
| M9 | med | Migration protocol written | D15, into the ADR |
| M10 | med | Cost attributed per step | `improvement_draft_cost_usd_total` + node detail |
| M11 | low | Self-hosting named | n/a (base-url escape hatch documented) |
