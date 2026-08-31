# INDEX — Prope eval-analysis improvement flow

Design pack run, 2026-08-29. Front door: `pad-design` → intake → shape → `pad-shape-workflow`.
Governing ADR: **ADR-0070**. This file is regenerated from the chapters, never hand-edited.

## Shape

**`workflow`** — a fixed DAG; the model fills in two steps and never picks the next one.
> Considered `agent`, chose `workflow` because the ten steps are known in advance and the only
> iteration (re-draft on rails failure) is a bounded, author-enumerated retry. Considered
> `multi-agent`, rejected: one drafter role; everything else is deterministic code.

Promotion trigger (00-D9): becomes an `agent` only if the model ever chooses which evidence to
gather next. Written so drift is a decision, not an accident.

## Intake decisions (sources)

| Decision | Value | Source |
|---|---|---|
| Candidate authoring | LLM-authored body under rails (supersedes ADR-0068 §3) | user |
| Trigger | Manual from the analysis brief | user |
| Finding threshold | Any failed group | user |
| Model / meter | App Agent, temperature 0, Prope's meter | user |
| Actions / undo, liability | unchanged — proposals only; the revision, approval and release stay human | codebase (ADR-0066, release-control) |

## Chapter roll-up

| Chapter | Decisions | Tripwires fired | Blockers open |
|---|---|---|---|
| 00-shape | D1–D9: step list, request-driven trigger, idempotency by DB constraint, partial-success-with-reason, per-step retry, pydantic boundary, agent-run as dead-letter, promotion trigger | `untrusted_content` (→ guardrails) | none |
| 01-orchestration | D1–D16: node-per-step persistence, gate persisted pre-proposal, four termination stops, 3-attempt redraft with no-progress detector, per-run caps, pause-is-a-row | `side_effects` (→ hitl), `cost_ceiling` (→ reliability) | none |
| 02-model-selection | D1–D16: tier table (two LLM steps), temp 0, max_tokens everywhere, single rung ladder + typed degradation, pinning + served-model field, migration protocol | `traffic`, `cost_ceiling` | none |
| 03-guardrails | D1–D15: untrusted-content map, trifecta broken (no egress), spotlighting + bounded samples, seven fail-closed rails, negative surface, injection fixtures in CI | `untrusted_content` | none |
| 04-hitl | D1–D16: one gated action (accept → `REVISION_CREATE`), no confidence routing ever, diff-is-the-card (test-enforced), rationale demoted, TTL expiry is the safe default, accept-rate alarm | `side_effects` | none |
| 05-evaluation | Level 1: gate = strict non-regression **+ strict improvement on the target group**, raw counts only, no judges anywhere. Level 2: golden set with unfixable + adversarial slices, 3-run variance, disposition funnel as the quality gauge | `has_eval_set` (resolved: gate labels deterministically) | none |
| 06-observability | Run-row-as-root-span, closed-enum labels only, six new metrics, one SLO with ticket-level burn alerting, three Grafana views | `multi_tenant` (→ cardinality rules) | none |
| 07-reliability-cost | Explicit 120s draft timeout (overriding the 5s client default), SDK-only retries, module breaker, one-rung ladder, spend caps before the money | `latency_budget`, `cost_ceiling` | none |

## Skipped concerns, with reasons

| Concern | Reason |
|---|---|
| pad-knowledge-base | no corpus exists — the drafter reads one prompt and its findings, not a document store |
| pad-retrieval | no retrieval step in the DAG |
| pad-context-memory | single-shot generation; no conversation, no cross-item state |
| pad-tools-mcp | tool_count = 0 — the model selects no tools; the pipeline is code around two model calls |

## Readiness gate

**READY — implementation landed 2026-08-29** (ADR-0070, migration 0050, verified live):

- [x] O1–O4 (01): typed termination reasons, caps in code, gate persisted pre-proposal,
      idempotent writes (`propose.py`, `agent_run/repository.py`)
- [x] G1–G6 (03): negative-surface tests, rails per code, injection fixtures
      (`tests/prompt_improvement/test_rails_reject_injection.py`, `negative-surface.md`)
- [x] H2 (04): the diff is the card — detail read gates the accept render
      (`PropaiFindingDrawer`, `ProposalDetailRead`)
- [x] E1/E3 (05): rails + golden fixtures in pytest; gate reproducible from
      (suite version, revision, probe config)
- [x] B2–B4 (06): no content in telemetry (log allow-list extended only with two integers),
      closed-enum labels, disposition funnel metrics
- [x] L1/L4 (07): 120s draft timeout override; max_tokens + probe-case cap before spend

Live verification: migration 0050 applied (`ck_improvement_proposal_an_llm_edit_carries_its_draft`,
`ck_improvement_proposal_rationale_is_bounded` present); analysis endpoint 200; new
`GET /improvement/proposals/{id}` auth-gated (401/404 shapes); worker sweep + triage green.

Recorded follow-ups (not blockers): k-repeat probe if accept-then-regress appears; retention
analysis once first acceptances exist; `pytest.ini` (asyncio auto) added for the local rig.

## Handoff table — what to build

| Slice | Builds | Chapters feeding it |
|---|---|---|
| 1 | Migration: `llm_edit` family, `draft_rationale`, `rails_report`, eval detectors, RLS/grants | 00, 03 |
| 2 | Evidence intake: `analyze_runs` → findings (any failed group) | 00, 01 |
| 3 | Drafter: DSPy program + boundary model + breaker + cost metric | 02, 03, 07 |
| 4 | Rails: seven pure predicates, typed codes | 03, 05 |
| 5 | Pipeline: nodes, termination reasons, caps, gate predicate (+strict improvement), metrics | 01, 05, 06, 07 |
| 6 | API: trigger rides `agent-runs`; accept path extended with rationale/rails report | 04 |
| 7 | Frontend: propose-fix action, proposal card with diff + collapsed rationale, locales | 04, 06 |
| 8 | Tests: rails, injection, gate-discard, crash-resume, route table, locale contract, golden set | all |

Done = `pnpm tsc --noEmit`, `pnpm lint`, `pnpm build`, pytest green, `docker compose up -d --build`,
and the endpoint verified end-to-end.
