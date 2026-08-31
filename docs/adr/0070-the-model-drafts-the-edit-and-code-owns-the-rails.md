# ADR-0070 — For eval-evidence findings, the model drafts the edit and code owns the rails

**Status**: Accepted
**Date**: 2026-08-29
**Decision**: user
**Module**: prompt-improvement (amendment to the fourteenth lock) / evaluation (a second reader of
the advisor, this one a writer of findings) / agent-run (two new plan nodes)
**Supersedes**: ADR-0068 §3, in part — the closed anomaly→family catalogue is no longer the only
author of candidate bodies. **Amends**: ADR-0068 §4, narrowly — see §5 below. **Leaves intact**:
ADR-0068 §1 (metadata arithmetic), §2 (gate-before-person, no-suite-no-edit), §5 (no egress),
§6 (Tier 3 non-goal), §7 (two meters); ADR-0002, ADR-0025, ADR-0035, ADR-0045, ADR-0053, ADR-0055,
ADR-0066.
**Related**: A-108, A-113, A-114, A-145, A-162, A-163, ADR-0005, ADR-0049, ADR-0067, ADR-0068,
INT-045 … INT-050, `docs/agent-design/` (the production-agent design pack run: 00-shape through
07-reliability-cost, plus `negative-surface.md`).

## Context

ADR-0068 built `prompt-improvement` around production **drift**: eleven detectors over ledger
metadata, remedies drawn from a closed catalogue of three clause families, because drift's remedy
space is small and.statable — a leaked probe tightens a refusal block; truncation gets a length
rule; drift gets a brevity clause. The catalogue made the round-trip guarantee assertable, and
§3's ban on free-form rewriting was the honest consequence.

The eval-run analysis (`POST /prompts/{id}/eval-runs/analysis`) opens a second evidence source,
and its remedy space is not small. *"17 of 42 cases violate the JSON schema"*, *"5 answers missed
a required phrase"*, *"8 answers matched a forbidden pattern"* — the fix for each depends on the
prompt's own text and the assertion's own payload: which fields the schema demands, which phrase
is missing, what the pattern is trying to forbid. Sometimes the fix is a clause; sometimes it is
restructuring an instruction block; sometimes the honest answer is that editing cannot fix it and
the dataset is wrong. Three responses were considered:

1. **Grow the catalogue** — one parameterized family per assertion type, clause text templated on
   the assertion's payload. Rejected: it stamps instruction text next to failures rather than
   addressing them, and the family count grows one migration at a time forever.
2. **Refuse the feature** — declare eval evidence out of scope for edits, notes only. Rejected by
   the product decision this ADR records: the person standing on the analysis screen asked for a
   fix, and the deterministic advisor already tells them *what* kind of fix.
3. **Let the model draft the edit, and bound it with code instead of a catalogue.** Accepted.

The decision is the user's, and it is deliberately narrow: it applies to **eval-evidence findings
only**. Drift findings keep the closed catalogue, because for drift the catalogue's premises still
hold.

## Decision

### 1. The model authors candidate bodies for eval-evidence findings, under a remedy family named for it.

A new `remedy_family = 'llm_edit'` joins the three drift families. The candidate body is written
by the App Agent (`APP_AGENT_MODEL`, temperature 0, bounded output tokens, cost on **Prope's**
meter — ADR-0068 §7's rule, unchanged and now covering the drafter too). The drafter's context is
spotlighted and bounded: the current body, the failing groups with the advisor's fixed advice, and
at most three failing samples truncated to the evidence rail — SR-9's rule, applied to the new
input.

### 2. Code owns the rails. The catalogue's guarantee is rebuilt as predicates over the output.

ADR-0068 §3's real promise was not the catalogue; it was the round-trip: *a remedy may not break
what a release depends on*. That promise is restated as seven pure, fail-closed checks every
authored body must clear before the gate spends anything: canonical XML, an unchanged
`{{variable}}` set, the interpolation-block rule, bounded diff (changed-block count and length
ratio), a non-empty delta, no spotlighting-marker echo, a bounded rationale. Every failure is a
typed code fed back into a bounded redraft loop (three attempts total, no-progress stop) — and a
candidate that cannot clear the rails is discarded, never rendered. The rails are unit-tested per
code and red-teamed with injection fixtures in CI.

### 3. The gate is unchanged in kind and stricter in degree.

ADR-0068 §2 stands word for word: no suite means no edit proposal; a regressed candidate is
discarded, counted, and never rendered; the probe is not an eval run and its spend is not a cost
delta. One condition is **added** for `llm_edit`: the finding's own failed count on the target
suite must strictly decrease. An authored edit that fixes nothing is not an improvement, and
"did not regress" is not the claim this evidence source licenses. Deltas are raw case counts —
no percentages, no intervals, at suite-sized N.

### 4. The trigger is a person's click, and the rate cap is still the database's.

Findings open from the analysis on demand (`any failed group` opens — the advisor's severity
stays informational, not gating); drafting and gating spend nothing until somebody asks from the
analysis brief. One open proposal per prompt, fourteen-day TTL, single-active-run lock — all
inherited unchanged. Automatic triggers are a future ADR's question, not a config flag.

### 5. What reaches a person is still an evidence card. ADR-0068 §4 is amended by one demotion.

The card remains the diff and the gate delta — the literal payload, never a paraphrase. The
drafter's rationale is **stored** (bounded, on the proposal row, in the audit record) and
**disclosed** as a collapsed, clearly-machine-attributed note beside the card — present because
an authored edit without any stated intent is harder to review than one with, secondary because
ADR-0068 §4's reasoning stands: the model's story about its own edit is a claim, not evidence.
The accept-rate alarm is the new rubber-stamp control: authored edits are more persuasive than
catalogue stamps, so an accept share approaching ~100% pages a human, not a threshold.

### 6. The audit record grows, because the accepter's decision now weighs more.

Two columns join `improvement.proposal`: `draft_rationale` (bounded text) and `rails_report`
(JSONB — which rails ran, which fired on which attempt). A reader reconstructing *why was this
accepted* months later gets what the candidate survived, not just what it claims.

## Consequences

**A migration widens two CHECKs and adds two columns** (`remedy_family` learns `llm_edit`;
`ck_improvement_proposal_an_edit_is_gated` is untouched — an `llm_edit` proposal still carries
body, family, gate run, and delta). The finding table learns eval-backed detectors, one per
assertion type, so dedupe stays per-type.

**Two plan nodes join the manual run** (`improvement_draft`, `improvement_gate`), and the run
records a typed termination reason among seven outcomes — five of which are *not errors*, which
is the point of complete-what-succeeded.

**The model swap gains a regression protocol.** `APP_AGENT_MODEL` changes re-run the rails suite,
the injection fixtures, and the golden set (seeded prompt fixtures across finding types, plus an
unfixable slice whose correct outcome is a discard with a reason). Redraft rate and rails-failure
distribution are the leading indicators, on the module's dashboards beside
`prope_improvement_gate_rejected_total`.

**Cost ceilings stay structural**: draft spend is bounded by `max_tokens` on the call; probe
spend by a per-run case cap checked before dispatch. Nothing is discovered after the money.

**The design pack's chapters** (`docs/agent-design/00`–`07`) carry the operational detail this
ADR deliberately does not: orchestration's four stops, guardrails' untrusted-content map, HITL's
gate mapping, evaluation's two levels, observability's metric set, reliability's timeouts and
ladder. Where this ADR and a chapter disagree, this ADR wins and the chapter is wrong.

## Alternatives rejected

**Parameterized catalogue families** (the recommendation this ADR's author made first): cheaper
and provable, but it stamps clauses beside failures rather than fixing them, and its growth path
is a migration per assertion shape. Recorded as the fallback if `llm_edit` accept quality
disappoints: the rails, gate, and HITL surfaces are shared.

**Free-form rewriting with the suite as the only bound.** ADR-0068 rejected this and this ADR
does not adopt it: the suite is a floor, and §2's rails exist precisely so the floor stays
load-bearing.

**Automatic proposals on run settlement.** Rejected: spend follows a person's request, and the
overwhelming-HITL attack begins with a queue nobody asked to fill.

**Showing the rationale as the card.** Rejected in §5; the demotion is the amendment's whole
width.
