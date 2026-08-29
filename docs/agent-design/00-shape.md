# 00 — Shape: workflow

System: **Prope eval-analysis improvement flow** — from a deterministic eval-run analysis,
draft an LLM-authored prompt edit, validate it against rails, gate it against the same suites
the analysis read, and hand a gated proposal to a human who accepts or dismisses it.

Artifact path: `docs/agent-design/` · Repository: `E:\Projects\P-113` · Language: English.

## Shape reason

A fixed DAG the author enumerated: read evidence → analyze → record findings → triage →
draft → validate rails → gate → persist proposal → HITL pause. The model fills in two steps
(triage, draft); it never picks the next step. **Considered `agent`, chose `workflow` because
the ten steps are known in advance and the only iteration (re-draft on rails failure) is a
bounded, author-enumerated retry.** Considered `multi-agent`, rejected: one drafter role,
everything else is deterministic code.

## Intake (recorded)

| Item | Answer | Source |
|---|---|---|
| Existing system | Full improvement loop ships (`src/prope/prompt_improvement/`, ADR-0068): detectors → LLM triage → code-authored candidate → gate probe → rate-capped proposal → HITL accept/dismiss | codebase |
| New in this design | (a) eval-run analysis as an evidence source; (b) LLM-authored candidate bodies (supersedes ADR-0068's authoring rule → new ADR); (c) remedy family `llm_edit` | user |
| Actions / undo | Agent writes findings + proposals only. Revision creation, approval, release stay human (ADR-0066). Accept returns `candidate_body`, writes no revision | codebase |
| Liability | The owner who accepts the proposal and saves the revision; release gate (evidence digest + cost delta) unchanged | codebase |
| Trigger | Manual "propose fix" action on the eval analysis brief; async agent-run | user |
| Threshold | Any failed assertion group (≥1 failed) opens a finding; proposing is still a person's click | user |
| Model / meter | App Agent (`APP_AGENT_MODEL`), temperature 0, cost on Prope's meter; gate probes on the workspace's meter | user |
| Traffic | Low: one run per person per click; DB-enforced one-open-proposal-per-prompt rate cap | codebase |
| Untrusted content | YES — the prompt body under edit and failing case outputs fed to the drafter are both injection surfaces | inferred |

## Decisions

| # | Decision | Value | Overturned when |
|---|---|---|---|
| D1 | Step list | (below, verbatim — passed to every concern chapter) | — |
| D2 | Trigger | Request-driven: a person clicks "propose fix" on the analysis brief → `POST /api/v1/agent-runs` (existing route, `RunKind.IMPROVEMENT` extended with `source=eval_analysis`). No spend without a person asking | If findings must open without a click → add the event-driven intake as a separate workflow, do not widen this one |
| D3 | Idempotency | Every step keyed by agent-run id + step name. `record_findings` and `persist_proposal` are idempotent by DB constraint (`ON CONFLICT` dedupe + one-open-per-prompt partial unique). `draft` pays nothing on retry-discard. `gate` is a paid probe → **1 attempt, no retry, no re-pay** | Never for `gate` |
| D4 | Partial failure | Complete what succeeded, report the rest: findings open even when triage/draft/gate fail (the existing sweep degradation pattern). A run that opens findings but produces no proposal is a *partial success* with a reason, not an error | Only `read_evidence` + `analyze` failing fails the run wholesale |
| D5 | Retry boundary | Per step. `draft`/`validate_rails`: ≤2 redrafts, each carrying the rails error as feedback. Transport retries live in the shared client (max 3). `gate`: 1 attempt. Exponential backoff with jitter where a second attempt is cheaper than a failure | `gate` — cost makes retry worse than failure |
| D6 | Batch or per-item | Per item: one run targets one revision of one prompt. No batch arm | — |
| D7 | Output contract | Pydantic model at the drafter boundary (`ProposedEdit`: `body`, `rationale`, `addressed`). Malformed output → rails failure → re-prompt with the validation error (bounded by D5). Server-side validation is pydantic + SQL CHECKs (Zod is frontend-only in this repo) | Never free text |
| D8 | Dead-letter | The `agent_run` table is the durable record: per-node status, failure reason, run id. Rejections additionally counted on metrics (`rails_rejected_total{rail}`, `gate_rejected_total`). No log-and-move-on | — |
| D9 | Promotion trigger | This becomes an `agent` if the model ever chooses which evidence to gather next (running new eval suites mid-loop, iterating without a step cap, or branching whose next step depends on the previous result). Written so drift is a decision, not an accident |

## D1 — the step list (verbatim)

1. `read_evidence` — load settled (terminal) eval runs + case results for the revision (read-only; existing repository functions)
2. `analyze` — `analyze_runs` → failed assertion groups, deterministic (existing)
3. `record_findings` — `open_or_bump_finding` per assertion-type group (idempotent, DB dedupe)
4. `triage` — LLM ranks findings, picks the target (existing triage pattern, extended to eval findings; degrades to untriaged, never raises)
5. `draft` — LLM authors the candidate body + rationale (NEW; App Agent, Prope's meter)
6. `validate_rails` — canonical-XML round-trip, variable set unchanged, interpolation rule, bounded diff, non-empty delta (pure functions; failure → bounded redraft)
7. `gate` — `score_body_against_suite` probe against the attached suites; strict regression semantics; **regressed candidates are discarded, never rendered** (existing invariant)
8. `persist_proposal` — `open_proposal` (rate-capped by partial unique index; `ON CONFLICT DO NOTHING`)
9. `report` — agent-run plan nodes carry per-step status to the SPA (existing polling)
10. — HITL pause (outside the DAG): existing accept/dismiss routes; accept returns `candidate_body` and writes no revision

## Workflow failure modes owned here

- **Silent no-op:** a run over a revision whose runs are all passing must surface "nothing failed — nothing proposed" as an explicit outcome on the run, distinct from failure (S3).
- **Retry storms:** draft retries + provider retries are bounded per step; the gate cannot be retried at all (S4; `reliability-cost` chapter owns the breaker).
- **Schema drift:** the drafter's output model is validated at the boundary; drift lands as rails failures on a metric, not as silent garbage (S5).

## Rails (output validation, decided at intake)

The candidate body must: parse as canonical XML (same predicate `remedies.py` enforces), keep
the `{{variable}}` set byte-identical, respect the interpolation-block rule, stay within diff
bounds (length ratio and changed-block count), and differ from the current body. All are pure,
unit-testable functions; failures carry a typed code into the redraft feedback.

## Supersession note

ADR-0068's "the model never writes the body" is superseded by a new ADR ("the model drafts the
body, code owns the rails"). Everything else in ADR-0068 stands: gate-before-person,
accept-writes-no-revision, rate cap, TTL, no egress (SR-5), metadata-only reads (SR-1).
