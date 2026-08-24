# Plan: Deterministic decision continuations + turn latency (kill the >5s approve, the 9s hello)

## Problem

Approving a simple write (folder creation) takes >5s. Root cause: after the
settle transaction commits (fast, DB-only), `_complete_decision_turn` runs a
full agent turn on the trusted `HUMAN_DECISION` marker:

1. Router LLM call (observed 5–57s) — only to conclude nothing more to do.
2. Responder LLM call (observed 8–25s) — only to narrate "Đã tạo thư mục X".

The HTTP response blocks on both. The settle itself already returns
deterministic navigation directives (`_CONFIRMED_NAVIGATION`), and ADR-0053
already renders non-generated strings client-side from codes.

## Change A — fast path (core)

`src/prope/chat_orchestrator/orchestrator.py`:
- New `_decision_result(request, trace, action, approve, written)` building a
  synthetic `TurnResult`: `code = "chat_action_confirmed" |
  "chat_action_rejected"`, empty reply, directives from
  `_CONFIRMED_NAVIGATION[tool]` via `sanitise_directives`, deterministic trace
  entries (`guardrail.input: decision_continuation`,
  `supervisor.route: skipped=decision_fast_path`).
- In `run_turn` / `_run_turn`: when `request.trigger == "decision"`, return the
  synthetic result before routing. No router, no responder, no rails.
- Keep observability: label a counter `decision_fast_path_total`.

`src/prope/chat_orchestrator/api.py`:
- `_complete_decision_turn` unchanged in shape (still persists the turn via
  `_persist_turn` so the thread shows the ack); it simply gets a cheap result.

Frontend:
- `locales/en.ts` / `vi.ts`: `chat.actionConfirmed`, `chat.actionRejected`.
- Chat rendering: translate `code` like `chat_proposal_pending` already is;
  navigation arrives via existing directive handling.

## Tradeoff (accepted)

The router could previously re-plan follow-ups on an approval ("tạo xong thì
liệt kê"). The queue was writes-only so those were already unreliable. After
this change a decision NEVER re-plans; anything further is a new message.
Multi-write plans keep working through `_complete_queued_turn`.

## Change B — secondary latency wins (all turns)

1. Parallel read-only steps: in `_execute`, run consecutive read-only tool
   steps concurrently (`asyncio.gather`), keep writes sequential.
2. Startup warm-up: ping each configured LM once on app startup to pay
   connection setup before the first user turn.
3. Metrics: per-stage histogram labels already exist; add
   `stage_seconds` emission for route/respond on message turns if missing.

## Change C — "Hello" in 9s (5s route + 4s respond)

A greeting pays the full pipeline: guardrail → router LLM (~5s: ~3.3k input
tokens of catalogue + fallback instructions + dspy scaffolding, non-streaming
completion) → responder LLM (~4s) — for a message that needs zero intelligence.

1. **Small-talk short-circuit** (deterministic, like Change A):
   - `guardrails.py`: new cheap classifier `match_smalltalk(message)` —
     full-message match only, short messages (≤ 6 words) against a closed
     vi/en lexicon of greetings/thanks/bye/ok ("xin chào", "hello hi", "cảm
     ơn", "thanks", "tạm biệt", "ok"…). No regex on prefixes; "hãy tạo
     thư mục" must never match.
   - `orchestrator._run_turn`: after input rails admit, if small-talk matches,
     return a synthetic TurnResult (`code = "chat_smalltalk_greeting"` etc.,
     outcome answered, deterministic trace entry). Router and responder never
     run. New counter `smalltalk_shortcircuit_total`.
   - FE locale keys en/vi for each class (greeting / thanks / farewell).
2. **Router prefill diet**: compress `ToolSpec.description` texts used by
   `catalogue_text()` (currently ~5k chars ≈ half the prompt) to one-line
   imperative forms; keep the routing-critical bits (arguments, HITL rule).
   Same catalogue drives the FE-less API surface only through this text, so
   wording changes are safe.
3. **Config guidance**: `CHAT_ROUTER_MODEL` / `CHAT_REPLY_MODEL` already exist;
   document pointing them at the fastest gateway tier (router needs only
   classification). Measure with the new stage metrics from B3 before/after.

## Out of scope (optional later)

- True token streaming of responder output (perceived latency; larger effort).

## Tests

- Unit: decision trigger returns fast result (no LM built/called — assert
  `build_router_program` not called); rejected path; unknown tool in nav table.
- Unit: small-talk classifier — matches vi/en greetings/thanks/bye, rejects
  tool-ish messages that merely start with a greeting word, rejects long
  messages; orchestrator returns the code without building any LM program.
- Integration: POST /chat/actions approve folder → response contains
  `continuation.code == "chat_action_confirmed"` and no LM call recorded.
- Existing suites must stay green; targeted runs only (user runs full suites).

## Done

`tsc --noEmit`, eslint, ruff pass; targeted pytest green.
