---
status: testing
phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
source: [02-VERIFICATION.md]
started: 2026-08-10T00:00:00Z
updated: 2026-08-10T00:00:00Z
---

## Current Test

number: 1
name: Adjudicate the 14 judgment-tier prohibitions carried by the five plans
expected: |
  Each prohibition confirmed as genuinely upheld. The verifier's non-authoritative reading finds
  all 14 upheld by passing tests or by structure — evidence cited per prohibition in the
  Prohibitions table of 02-VERIFICATION.md — but a judgment-tier prohibition is never green on an
  agent's say-so.
awaiting: user response

## Tests

### 1. Adjudicate the 14 judgment-tier prohibitions carried by the five plans (all marked `status: resolved`, `verification: judgment`)
expected: Each prohibition confirmed as genuinely upheld. Evidence is cited per prohibition in the Prohibitions table of 02-VERIFICATION.md. Judgment-tier prohibitions have no mechanical enforcement, and the four non-negotiables in CLAUDE.md make these the security-weight items of the phase.
result: [pending]

### 2. Exercise the five `/api/v1` management routes by hand once a session store exists
expected: POST/GET `/prices`, GET `/prices/unpriced`, PUT `/spend-ceiling`, PUT `/retention` behave as INT-028 registers, with the A-045 error envelope on refusal. `require_session` unconditionally raises 401 until Phase 7 (fail-closed interim posture), so every route is proven through the ASGI test rig and the assembled route table but none can be driven by hand this phase. Untestable-until-Phase-7, not a gap.
result: [pending]

### 3. Confirm or reverse the `POST /api/v1/prices` refusal of a (0,0) price row, adopted unconfirmed by plan 02-05
expected: A decision recorded on the still-open Phase 1 human-verification item that this refusal was adopted against. Plan 02-05 shipped the refusal (`api.py:407`, `ErrorCode.PRICE_BOTH_PRICES_ARE_ZERO`) while its authorising decision is still open — the code is correct against the reviewer's reasoning but the decision is not yet the developer's.
result: [pending]

### 4. Resolve OQ-018, OQ-019, OQ-020, OQ-021 — four declared spec deviations raised rather than absorbed
expected: Each open question resolved against `docs/modules/call-ledger.lock.yml` / `docs/architecture/interfaces.md`, or accepted as a standing deviation. Per `.planning/BSP-LINK.md` a spec that disagrees with code is recorded, never edited into agreement. All four files exist with the required content.
result: [pending]

### 5. Decide the disposition of CR-01 (unbounded `retention_days`) and CR-02 (uncounted shutdown drop)
expected: Either fixed in a follow-up, or accepted with the reasoning recorded. Both are real defects confirmed independently in code, but neither falsifies a Phase 2 must-have truth. CR-01 must be fixed before Phase 7 opens the route. Whether they block shipping Phase 2 is a risk-tolerance call, not a verification result.
result: [pending]

### 6. Settle CL-11's traceability
expected: `get_run_totals` is ROADMAP Phase 2 SC3 and CL-11's second clause, but CL-11's REQUIREMENTS.md row reads Phase 1 / Pending. Split the ID, remap the row across two phases, or accept a permanently-pending Phase 1 row. Named as Phase 1 human-verification item 2 and still open; `seams.py` builds the function and deliberately claims no requirement for it.
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
