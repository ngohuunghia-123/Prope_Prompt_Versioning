# Chat orchestrator: latency, memory, multi-intent, clarification (A–E)

## Evidence (Langfuse traces, 2026-08-24 session)
- Router: ~3.3k tok in, 55–90 tok out, **5–57s** (gateway TTFT spikes + `num_retries=3`)
- Responder: ~1.15k tok in, 8–25s — pure overhead on write-only turns
- Body-writing call (drafter/conversion): 80s / 2.8k out — legitimate, not targeted
- Memory loss: router history = person's messages only (1200 chars); created entity IDs never fed back
- Multi-intent: `_execute` ends the plan at the first write proposal (orchestrator.py:716); remaining steps discarded after settle
- Ambiguity: only prompt targets have candidate resolution; folders and missing args surface as `error`, not questions

## A — Per-program model + router fail-fast
Files: `src/prope/app_agent/dspy_runtime.py`, `src/prope/chat_orchestrator/dspy_program.py`, `.env.example`
- Extend `build_lm(*, max_tokens, temperature=0.0, model=None, num_retries=3, timeout=None)` — backward compatible.
- New env constants next to `MAX_ROUTER_TOKENS`:
  - `CHAT_ROUTER_MODEL` / `CHAT_REPLY_MODEL` / `CHAT_DRAFT_MODEL` (default `APP_AGENT_MODEL`)
  - `CHAT_ROUTER_NUM_RETRIES` default `1`; `CHAT_ROUTER_TIMEOUT_SECONDS` default `12`
- `build_router_lm()` passes model override + retries/timeout; reply/draft pass model overrides only.
- `.env.example`: document all five vars.

## B — Skip responder LLM on proposal-only turns
Files: `src/prope/chat_orchestrator/orchestrator.py`
- Condition: a proposal is pending AND no read-tool evidence AND no degraded flags → deterministic templated reply instead of the responder call.
- Reply text comes from an i18n-style constant on the FE side already rendered with the card; backend emits short neutral text key `chat.proposal_pending_reply` via existing code path (TurnResult.code unchanged).
- Saves 8–25s per write turn. Trace records `respond` step as `detail={"skipped": "proposal_only"}`.
- Keep responder for turns that mix reads + writes or produce errors.

## C — Thread state (`thread_state`)
Files: `src/prope/chat_orchestrator/{domain,schemas,api,repository}.py` (+ models if persistence needed), FE `types.ts`
- Prope-written trusted record per thread, last 5 entity outcomes:
  `{kind: prompt|folder|key|provider, id, title, namespace_name?, folder?, status: created|updated|confirmed_pending}`
- Written when tools succeed or proposals settle (same seam as decided_actions / pending actions).
- Router: new InputField `thread_state` (TRUSTED, like `recent_actions`) so demonstratives ("prompt ấy") resolve to IDs.
- `_step_update_prompt` / move/rename steps prefer `thread_state` latest prompt ID when arguments lack one.
- Responder `situation` gains one line per recent creation.

## D — Pending-plan queue (auto-sequence cards)
Files: `src/prope/chat_orchestrator/{orchestrator,domain,api}.py`
- When a write proposal truncates the plan, persist remaining `{tool, arguments}` steps alongside the pending action (reuse pending-action storage; no migration expected).
- After settle:
  - approve → continuation turn executes the NEXT queued step directly (no router call), producing its own card; loop continues until queue empty → final turn summarizes.
  - reject → clear remaining queue; continuation explains what was skipped.
- Dedup backstop still applies to queued writes.
- Continuation TurnRequest carries `remaining_steps` (like `decision` marker today).

## E — Clarifying questions (`needs_input`)
Files: `tools_registry.py`, `tools.py`/`tools_access.py` (folder resolution), orchestrator, FE chips
- New ToolResult outcome `needs_input` + reason `chat_tool_needs_input`; options carried as evidence entries (kind=`option`).
- Add `resolve_folder_candidates(context, query)`: exact slug/name → resolved; multiple matches above similarity floor or missing required argument → needs_input with top 5 folder options (or `[create new]` hint).
- Missing title/name on rename/create → needs_input asking for the value (no LLM guess).
- Responder renders the question deterministically from situation; FE shows option chips from evidence items (new optional `options[]` on evidence in `types.ts`, chip row under agent bubble).

## Verification
- Unit tests: build_lm overrides; router fail-fast env parsing; thread_state recording/injection; queue sequencing logic; folder candidates.
- Integration tests (test_chat_api): multi-write message sequences cards across continuations; rejection cancels queue; ambiguous folder asks instead of failing; proposal-only turn has no responder generation.
- FE: tsc/lint/build; render chips + no regressions in decide() flow.
- Targeted suites only per user preference (they run full suites themselves).

## Order
A → B (independent latency wins) → C → D → E → tests.
