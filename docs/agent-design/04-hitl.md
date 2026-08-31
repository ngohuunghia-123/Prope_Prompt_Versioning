# 04 — Human in the loop

This chapter inherits a rare luxury: **the gate already exists and has shipped.**
`improvement.proposal` + accept/dismiss routes + history events + the SPA inbox are in
production (ADR-0068). The design work here is mapping the pack's decisions onto that surface
and naming the two things the LLM-authored candidate changes: the diff view (D9) and the
rationale's role.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | Forbidden vs gated | Forbidden = the negative surface (03-guardrails D12): revision create/approve/release, egress, provider calls beyond the probe, re-gating, cap bypass — **absent from the surface, not gated**. Gated = exactly one consequential action: **accepting a proposal** (plus the trivial dismiss finding/proposal) |
| D2 | The gated set | Accept (`IMPROVEMENT_PROPOSAL_ACCEPT` → mapped to `REVISION_CREATE` authority — accepting a proposed *edit* already requires edit-level permission). Dismiss (`→ PROMPT_EDIT`). Reads are ungated (`PROMPT_READ`) |
| D3 | Policy override | Stronger than the default: **no confidence score can route around the gate at all.** Every proposal — even a perfect gate delta — waits for a person. The gate result is *evidence shown*, never an auto-accept signal |
| D4 | Confidence routing | None. `gate_delta` is displayed to the accepter (D9), not consumed by policy. This is a permanent property, not a v1 simplification: a high score measures suite pass, not intent (03-guardrails residual risk) |
| D5 | Reducing prompt volume | Structural, not thresholdal: one open proposal per prompt (DB partial unique), 14-day TTL, manual trigger. Approval volume equals human click volume — there is no queue to flood |
| D6 | Automating the low tier | **Off, permanently.** No auto-accept tier exists; the invariant is gate-before-person, person-before-revision |
| D7 | Circuit breaker | n/a in the attack sense: the pipeline cannot resubmit after a denial (dismissal closes the proposal; a new one needs a fresh human click). The overwhelming-HITL attack is structurally impossible at this volume |
| D8 | Four resolutions | **Approve as-is** = accept → editor opens prefilled with `candidate_body` → human saves (the revision write is still theirs). **Edit then approve** = the same flow, human edits in the editor before saving — the natural shape here, since accept writes no revision. **Reject with feedback** = dismiss, reason 1–500 chars (exists). **Respond directly** = n/a, no conversation |
| D9 | What the UI shows | The **literal payload, always**: candidate body as a before/after diff against the current revision, the per-suite gate delta (pass/fail/cost numbers), the fixed advice text the finding carried, and the drafter's rationale — the rationale is shown *beside* the literal diff, never instead of it. Blocker-severity: no accept button renders without the diff rendered (test asserts the card refuses to render `llm_edit` proposals without a diff view) |
| D10 | Approver identity | A role, not a person on call: whoever holds `REVISION_CREATE`-equivalent permission for the prompt (existing RBAC/grants). No out-of-hours path needed — nothing in Prope blocks on this approval; expiry is the safe default |
| D11 | The audit record | Already strong, one gap closed: `decided_by`, `decided_at`, `candidate_body` (the exact payload), `gate_delta`, `remedy_family`, finding link + params — on the proposal row; disposition as append-only history events (`improvement_proposal_accepted/dismissed/expired`, migration 0034). The **rails report** joins the record (new column from slice 1) so a later reader can see what the candidate survived. Retention: proposals are rows, not traces — they do not expire with sampling |
| D12 | Timeout and expiry | 14-day TTL (existing), sweeper-written `expired` with `actor_type='system'` — the defined outcome is *nothing happens*, the safe default. Queue-age visibility: open-proposal count + age gauge (06-observability) |
| D13 | Durability | The pause is a Postgres row with RLS — survives every restart and deploy by construction |
| D14 | Fatigue monitoring | Volume is structurally capped, but the aggregate signals are still tracked: accept/dismiss/expire rates, median time-to-decide (`decided_at − created_at`), per detector and per family — cheap to derive from the table, owned by 06-observability |
| D15 | Threshold tuning rule | The analog: **if the accept rate for gated proposals approaches ~100%, the gate or the rails are too weak** — people are rubber-stamping. Alarm on it; tune rails thresholds, not human patience |
| D16 | Reviewer disagreement | Single-decider per proposal (one `decided_by`); where stakes rise, the release flow's separate reviewer is the second human. No tie-break needed inside this gate |

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Approval fatigue | structurally impossible volume (D5); rates still monitored (D14) |
| Approval of a paraphrase | the literal diff is the card (D9, test-enforced); rationale is adjacent, never substitutive |
| Pause lost on deploy | pause is a DB row (D13) |
| Pending forever | TTL + expiry sweeper + age gauge (D12) |
| Gate bypassed by generated flow | the pipeline has no path to revision creation at all (D1) — the accept API is the only door and it is a person's |
| Rubber-stamp acceptance | accept-rate alarm (D15); gate_delta displayed numerically (D9) |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| H1 | blocker | Gate unbypassable from generated flow | no revision-write path exists; CI asserts |
| H2 | blocker | UI shows the literal payload (diff), not a paraphrase | diff view + render-refusal test (slice 7) |
| H3 | blocker | Pause survives restart | DB row — existing, tested |
| H4 | blocker | Forbidden actions absent from the surface | negative-surface test (03) |
| H5 | high | Audit record: who/payload/when/decision | proposal row + history; **+ rails_report** (new) |
| H6 | high | Session circuit breaker | n/a — no resubmission path; recorded |
| H7 | high | Expiry with defined outcome + age visibility | TTL existing; age gauge new (slice 7/observability) |
| H8 | high | Aggregate fatigue signals | accept/dismiss/expire rates, time-to-decide |
| H9 | high | All four resolutions | accept / accept-then-edit / dismiss-with-reason / no-op |
| H10–H13 | med | Confidence override / calibration / role / retention | no confidence path (stronger); role-mapped; rows retained |
