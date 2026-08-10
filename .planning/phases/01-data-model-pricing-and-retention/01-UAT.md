---
status: testing
phase: 01-data-model-pricing-and-retention
source: [01-VERIFICATION.md]
started: 2026-08-10T04:45:00Z
updated: 2026-08-10T04:45:00Z
---

## Current Test

number: 1
name: Decide the disposition of CR-01 — a legal `(0,0)` price row produces a zero cost that `write_records` refuses, discarding the whole batch
expected: |
  A recorded decision between:
    (a) accept as a Phase 2 blocking pre-condition on `POST /api/v1/prices` — the verifier's recommendation
    (b) re-open Phase 1 with a follow-up plan adding the tightened CHECK plus a per-record exception
    (c) accept as-is with a recorded override

  If (a), CR-01 must be entered as a named pre-condition on the Phase 2 plan that builds
  the price-row write route — Phase 2 is the first phase that lets a human insert a price
  row, and the first whose drain will re-deliver a poison batch forever.
awaiting: user response

## Tests

### 1. CR-01 disposition — the free-tier price row

expected: A recorded decision: (a) Phase 2 blocking pre-condition (recommended), (b) re-open Phase 1 with a follow-up plan, or (c) accept with a recorded override.
why_human: A scope/priority judgement between phases, not a fact about the code. The verifier confirmed the mechanism is real and that no Phase 1 truth fails because of it; whether it blocks the phase boundary is the developer's call.
context: |
  `ck_price_table_prices_are_non_negative` is `>= 0`, so a `(0,0)` free-tier price row is
  legal. `compute_cost(300, 150, PriceRow(0,0))` returns `Decimal('0E-10')`, and
  `writer.py:237` raises on it — discarding the whole batch. `repricing.py:172` aborts
  identically.

  Two corrections the verifier made to the code review's framing, both of which lower the
  severity:
    - "can never be corrected or removed" holds for `prope_app` only. `prope_migrate` owns
      the `ledger` schema (`0001:62`) and RLS is `ENABLE`, never `FORCE` — the owner
      bypasses the policy. Recoverable by DBA action, not permanently trapped.
    - The triggering state is unreachable through anything Phase 1 ships. `POST /api/v1/prices`
      is Phase 2's, and there is no drain yet to re-deliver a poison batch.

  Neither phase-goal clause breaks: no wrong figure is ever stored (the failure is a loud
  refusal, which upholds SC 2's "no row anywhere records a cost of zero"), and irreversibility
  is proven by a live mutation test. Both halves of the exposure arrive together in Phase 2.
result: [pending]

### 2. CL-11 traceability — which phase owes it

expected: REQUIREMENTS.md and ROADMAP.md agree about which phase owes CL-11, so no future audit reads Phase 1 as having left a requirement unfinished.
why_human: A traceability-bookkeeping decision. The code is correct either way; only the planning documents disagree with themselves.
context: |
  CL-11 is listed in Phase 1's `Requirements:` line in ROADMAP.md and in two plans'
  frontmatter, but ROADMAP assigns its second clause to Phase 2, and its REQUIREMENTS.md
  row reads "Phase 1 / Pending".

  The verifier's finding: the ROADMAP already splits CL-11 itself — Phase 1 SC 3 is clause 1
  verbatim ("records unknown tokens as null, never zero"), Phase 2 SC 3 is clause 2 verbatim
  (`get_run_totals`). Phase 1 built and asserted the encoding that makes clause 2 buildable:
  `test_the_gateway_pre_first_byte_fallback_is_unknown_not_a_zero` asserts
  `count(*) FILTER (WHERE usage_status='unknown')` equals both 1 and the null-token count.
  Had Phase 1 stored a zero here, Phase 2 could not recover the number.

  Options: (a) split CL-11 into two IDs, (b) remap its traceability row to "Phase 1, Phase 2",
  or (c) leave it and accept a permanently-Pending Phase 1 requirement.
result: [pending]

### 3. Revision 0001 against a deploy-shaped database

expected: |
  Run `alembic upgrade head` as a non-superuser `prope_migrate` on a real PostgreSQL 17 host
  and confirm the write to `public.alembic_version` succeeds. The chain must reach head.

  If it fails with `permission denied for schema public`, WR-04 is confirmed and revision 0001
  needs `GRANT USAGE, CREATE ON SCHEMA public TO prope_migrate`.
why_human: |
  Structurally unverifiable in this phase's rig. `0001:68` revokes `USAGE` on schema `public`
  — where `alembic_version` lives — and nothing grants `prope_migrate` back. The testcontainers
  connection IS a superuser, so the rig cannot observe the failure even if it exists.
  `0001_roles_and_schemas.py:9-15` flags this as assumption A9 and `alembic/ddl.py:37-39`
  half-notices it. Needs a real host or a deliberately de-privileged container.
result: [pending]

### 4. Cost quantum and retention window as business figures

expected: The ten-decimal-place cost quantum (`COST_SCALE = 0.0000000001`) and the 30-day `DEFAULT_RETENTION_WINDOW` are confirmed against a real provider price list and the pilot's data-retention posture — or changed before Phase 2 makes them observable through a route.
why_human: Both figures are internally consistent and asserted, but their correctness is a product judgement against A-040 and a real price sheet, not a property of the code.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
