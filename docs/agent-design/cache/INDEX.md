# INDEX — App-Agent LLM call cache

Design pack run, 2026-08-30. Front door: `pad-design` → intake → shape → `pad-shape-workflow`.
Governing ADR: **none new** (a cache layer, not a new authority); supersedes nothing; `cache=False`
on the DSPy LM stays. This file is regenerated from the chapters, never hand-edited.

## Shape

**`cache`** — a fixed pipeline: key → read → miss → call → gate → store → return. The model
never picks a step.
> Considered `agent`, chose `cache` because the three decisions that matter — what goes in the
> key, what may be served, and what may be stored — are all made by code before the model is
> asked anything.

First consumer: the eval dataset suggester (`suggest_datasets`, the "recommend eval set" button)
— inputs are a closed catalogue block plus title/body, output is a pure function of those
inputs, and a second click has never needed a different answer.

## Intake decisions (sources)

| Decision | Value | Source |
|---|---|---|
| Scope | App-Agent DSPy calls only; workspace provider dispatch excluded | codebase (two HTTP stacks) |
| Storage | Per-workspace row + RLS, write-once, TTL 24h | codebase (readiness lane_b_cache precedent) |
| Key | Content hash over (body, title, catalogue, schema_version, model, extra_body) | inferred |
| Stored content | Gated model output + tokens only; never the body | codebase (A-020/A-046) |
| Gate | Re-run on every read; a poisoned row is dropped, never served | codebase (existing `_gated`) |
| Cache seam | `Cache` protocol, `NoOpCache` default, per-caller injection | inferred |
| Failure mode | Read failure = miss; write failure = return fresh; never raises | inferred |

## Chapter roll-up

| Chapter | Decisions | Tripwires fired | Blockers open |
|---|---|---|---|
| 00-shape | D1–D13: scope, content-addressed key, per-workspace row, gate-on-read, TTL 24h, no body stored, seam shape, fault isolation, metrics, caller contract, gate idempotence, conflict arbiter, follow-ups | `untrusted_content` (→ guardrails) | none |
| 01-orchestration | D1–D16: one write-once row, ON CONFLICT + re-read, four termination outcomes, no cache retry, no budget change, no partial-failure gap, TTL-at-read, content-address growth bound | `cost_ceiling` (→ reliability) | none |
| 02-model-selection | D1–D10: model in the key, extra_body in the key, schema-version bump protocol, catalogue-version invalidation, transport settings excluded | `traffic` | none |
| 03-guardrails | D1–D11: body hashed never stored, RLS tenant boundary, no prompt id, gate on read, JSON-array CHECK, TTL, grants, no egress, no telemetry content, module map | `untrusted_content` | none |
| 04-hitl | D1–D5: cache is not a decision record, no auto-act, no confidence routing, nothing to audit, TTL is the safe default | — | none |
| 05-evaluation | D1–D6: gate is the only judge, stored = what a person would have seen, no judges, gate-bug needs no purge, hit-rate quality signal, drafter is a follow-up | `has_eval_set` | none |
| 06-observability | D1–D16: no trace, closed-enum labels, content off, hit-rate SLI + error ticket, cost-saved on Prope's meter from stored tokens, one dashboard panel | `multi_tenant` (→ cardinality rules) | none |
| 07-reliability-cost | D1–D18: no cache timeout, no cache retry, read path outside the breaker, no serve-stale rung, no added spend, crash-loss accepted, no new alarm | `latency_budget`, `cost_ceiling` | none |

## Skipped concerns, with reasons

| Concern | Reason |
|---|---|
| pad-knowledge-base | the cache is a keyed store, not a corpus |
| pad-retrieval | no retrieval step — a content hash is the lookup |
| pad-context-memory | no conversation, no cross-item state; a row is a leaf |
| pad-tools-mcp | tool_count = 0 — the pipeline is code around one gated call |
| Serve-stale-on-error rung | a cache that answers on failure is a cache that became a dependency (07-D11) |
| Cache the per-workspace provider dispatch | workspace money; the latency is the product (00-D1) |
| Cache the eval-case drafter in v1 | its output is a draft a person edits; a stale draft costs more than a stale suggestion (05-D6) |
| In-process memo cache | the DB row is the checkpointer; a process-global memo would duplicate state across workers and would be the one cache not governed by RLS (00-D7) |

## Readiness gate

**DESIGNED — implementation pending.** This pack is the design; the build is the handoff table
below. The two invariants that must survive into code are: (a) the gate re-runs on every read,
and (b) a cache failure never raises to the caller.

- [x] Design: key semantics (02), storage + RLS (03), gate-on-read (05), fault isolation (07)
- [x] Design: metrics closed-enum, content-free (06)
- [ ] Migration `0055` `evaluation.llm_cache` applied
- [ ] `app_agent/cache.py` seam (`Cache` protocol, `NoOpCache`, `PostgresCache`)
- [ ] `suggest_datasets` wired with the seam; existing tests green
- [ ] Fault-injection tests: read-failure-is-a-miss, write-failure-returns-fresh
- [ ] `pnpm tsc --noEmit`, `pnpm lint`, `pnpm build`, pytest green, `docker compose up -d --build`

## Handoff table — what to build

| Slice | Builds | Chapters feeding it |
|---|---|---|
| 1 | Migration `0055`: `evaluation.llm_cache` (workspace_id, cache_key, program, model, findings jsonb, tokens, created_at), PK, JSON-array CHECK, RLS, grants | 00, 01, 03 |
| 2 | Seam: `app_agent/cache.py` — `Cache` protocol, `NoOpCache`, `PostgresCache`, `compute_key`, `PROGRAM_SCHEMA_VERSION` | 00, 02 |
| 3 | Suggester wiring: `suggest_datasets(..., cache=...)`, read → gate → store → return, metrics | 00, 01, 05, 06, 07 |
| 4 | Repository: `evaluation` cache read/write statements (Text SQL, bound params, no cross-schema) | 01, 03 |
| 5 | Metrics: `llm_cache_total`, `llm_cache_put_total`, `llm_cache_errors_total`, `llm_cache_cost_saved_usd_total` | 06 |
| 6 | Tests: key-equality, gate-on-read, poison-drop, read/write fault-injection, tenant-coverage walks the new table, log-scan fixture covers new lines | 01, 03, 05, 07 |
| 7 | (Follow-up, not blocker) eval-case drafter wired through the same seam | 05-D6, 00-D13 |

Done = `pnpm tsc --noEmit`, `pnpm lint`, `pnpm build`, pytest green, `docker compose up -d --build`,
and the suggester verified: click once (miss), click again (hit, zero spend), edit the body
(new key → miss).
