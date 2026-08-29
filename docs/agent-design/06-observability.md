# 06 — Observability

Prope's primitives are not OTel traces — they are **Prometheus counters/gauges on `/metrics`,
the `agent_run` row with per-node `detail`, append-only history events, and Grafana**. This
chapter maps the pack's requirements onto those primitives honestly, rather than proposing a
tracing rollout the repo has no other reason to want. The module already ships
`prompt_improvement/observability.py` with 8 metrics; this design extends it.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | Trace structure | The **run row is the root span**; each plan node (`detector`, `triage`, `improvement_draft`, `improvement_gate`) is a child span with `status`, timing, and a bounded `detail` JSONB (model id, token counts, cost, rails codes, termination reason). The pack's "one span per model call" is satisfied structurally: every LLM call's outcome is a queryable node field under the run id |
| D2/D3 | Convention + insulation | No `gen_ai.*` attributes adopted; the module's own `detail` schema (versioned in `domain.py`) *is* the insulation layer — dashboards read metrics and node fields, never framework telemetry names |
| D4 | Correlation | `run_id` on every node; `proposal_id` ↔ `finding_id` ↔ `detector_id` chain on the proposal row; workspace + actor via the run's existing columns. As **data**, never as metric labels |
| D5 | Content capture | **Off in telemetry**: no candidate bodies, no prompt bodies, no case outputs in metrics, logs, or node details beyond the bounded evidence rail (≤400 chars). The one deliberate content store is `improvement.proposal.candidate_body` — product data behind RLS and the audit requirement (04-D11), not a telemetry leak. The `cache=False` DSPy rule already keeps bodies off disk |
| D6 | Cardinality | Labels are **closed enums only**: `termination_reason` (7), `rail_code` (7), `decision` (3), `detector_id` (~19), `remedy_family` (4). No workspace, user, run, or prompt ids as labels — tenant cost attribution rides the module's existing per-meter cost metrics pattern |
| D7 | SLIs | Health: runs reaching a terminal state, run wall-clock, provider unavailability count (`drafter_unavailable` rate). Quality: **rails rejection rate by code, gate rejection rate, redraft-rate distribution, accept rate** — the LLM-specific additive signals. Cost: draft USD per run (Prope meter) + probe USD per run (workspace meter) |
| D8 | Quality as a continuous signal | The disposition funnel *is* the sampled quality gauge here: draft → rails-pass → gate-pass → accepted, each stage counted. A stage share that moves is the silent-degradation detector (a draft-model swap that quietly doubles rails failures shows up the same day, not in a support ticket). The deeper signal — accepted revisions' future pass-rate retention — is the recorded follow-up (05-D17) |
| D9 | SLOs | One: **"a proposed improvement reaches a decision-ready state"** — 99% of runs end in a terminal outcome (proposal opened or a typed non-error reason) within the wall-clock cap, measured monthly. One SLO because there is one user journey; error budget in minutes, not nines-worship |
| D10 | Burn-rate alerting | Ticket-level, not paging (solo-scale team): fast burn 14.4× over 5m+1h on the terminal-outcome SLI; page only on `drafter_unavailable` sustained >30m (provider effectively down). Rails-rate *spikes* get a ticket, per 03-D14 |
| D11 | Cost attribution | From day one, from actual usage: `improvement_draft_cost_usd_total` (new, Prope's meter, mirroring `triage_cost_usd_total`) and probe spend via the existing `ProbeUsageRow`/`scheduled_probe_cost_usd_total` pattern. Per-run cost is on the node detail (tokens × pinned price table) |
| D12 | Cache accounting | n/a — `cache=False` by security rule (02-D8); nothing to account |
| D13 | Served model | Node detail carries the **actual model id that served** the draft (not just the config value) + tokens — queryable, so an operator's silent swap is visible (02-M2) |
| D14 | Retention | Telemetry metadata (metrics) ~90d via existing Prometheus config; node details live with the run row (bounded); the only long-lived content is the proposal + its body, which the audit requirement (04) *wants* retained. No content tiering problem exists because telemetry carries no content |
| D15 | Tooling | Existing Prometheus + Grafana; no new dependency introduced by this design |
| D16 | Dashboards | Extend the module's Grafana panel into the three-view split: **health** (runs, terminal outcomes, wall-clock, provider unavailability), **quality** (rails/gate rejection by code, redraft histogram, accept rate, proposal age), **cost** (draft + probe USD, per detector/family). One screen each; forty panels is nobody's incident view |

## New metric definitions (slice 5)

```
improvement_draft_cost_usd_total            # Prope's meter, like triage_cost_usd_total
improvement_draft_attempts_bucket{le}       # histogram 1..3 — redraft visibility (05-D2)
improvement_rails_rejected_total{rail_code} # 7 closed codes (03 rail set)
improvement_runs_total{termination_reason}  # 7 closed reasons (01-D6/D11)
improvement_proposals_open                  # gauge; age via improvement_proposal_age_seconds{max}
improvement_proposal_decisions_total{decision}  # accepted|dismissed|expired
```

All labels closed-enum; the existing 8 module metrics unchanged.

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Silent quality degradation (draft model swap) | rails/gate rates + redraft histogram move same-day; served-model on node |
| Rubber-stamp acceptances | accept-rate share approaching 100% (04-D15) on the quality view |
| Run stuck mid-pipeline | terminal-outcome SLI + wall-clock; worker sweep already reaps |
| Cost surprise | per-run cost on both meters, per detector/family, on the cost view |
| Telemetry blocks the pipeline | metrics are in-process counters (existing pattern) — no export in the request path |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| B1 | blocker | Every model call is a node under a common run id | plan-node design (01) |
| B2 | blocker | No content in telemetry; the proposal store is deliberate product data | D5 split, tested by log-scan fixture |
| B3 | blocker | No high-cardinality metric labels | closed enums only (D6) |
| B4 | blocker | Quality signal measured + alarmed | disposition funnel + accept-rate alarm |
| B5 | high | Served model queryable per draft | node detail (D13) |
| B6 | high | Cost per run from actual tokens, both meters | D11 |
| B7 | high | Cache token accounting | n/a — caching off by rule |
| B8 | high | Versioned attribute insulation | `detail` schema versioned in domain |
| B9 | high | One SLO + burn-rate alerting | D9/D10 |
| B10 | high | Telemetry cannot block requests | in-process counters |
| B11–B14 | med/low | Retention split / TTFT / guardrail-rate alarms / three dashboards | n/a TTFT (no streaming); rails alarm exists in D10; dashboards in D16 |
