# Adopted-unconfirmed decisions — phases 3–24

> Every one-way or costly decision this orchestration made **on the user's behalf** because
> `mode: yolo` was set and the run does not stop at blocking checkpoints. See
> `.planning/ORCHESTRATION.md` §6.
>
> **This is the adjudication list.** Each row is a decision a human would normally have made at a
> `checkpoint:decision` gate. The reasoning lives in the named plan file; this table exists so the
> user does not have to find twenty-two of them.
>
> Status: `UNCONFIRMED` until the user confirms or reverses. A reversal is real work, sized by the
> reversibility rating.

| # | Phase | Plan | Decision | Rejected alternative | Reversibility | Status |
|---|-------|------|----------|----------------------|---------------|--------|
| — | — | — | *(none yet — phase 3 planning in flight)* | — | — | — |

## Prior unconfirmed adoptions inherited from phases 1–2

| # | Phase | Plan | Decision | Status |
|---|-------|------|----------|--------|
| P2-a | 02 | 02-05 | `POST /api/v1/prices` refuses a `(0, 0)` price row (`ErrorCode.PRICE_BOTH_PRICES_ARE_ZERO`, `api.py:407`). Adopted against a Phase 1 human-verification item that is still open. | UNCONFIRMED |

## Standing items the user owes a decision on (not orchestration adoptions)

These predate this run and block the pilot, not the build. Recorded so they stay visible.

| Item | Effect |
|---|---|
| **OQ-006** (data classification and retention) and **OQ-013** (PII/redaction for stored call bodies) | A-020 holds the line: **no real corporate prompts in the pilot** until both close. |
| **OQ-005** (real deadline and team size) | A one-person answer triggers the recorded re-scope against prompt-registry (M5). |
| **OQ-012** (uptime target / latency budget) | A-031's p95 50 ms is an agent placeholder until this closes. |
| **OQ-008** (is an owner one person or a team) | A-051 assumes one person; ADR-0054 answers departure separately. |
| **OQ-018 – OQ-021** | Four declared spec deviations from phase 2, raised rather than absorbed. |
| **The React SPA has no milestone** (PITFALLS gap 3) | Eight milestones build eight backends and no UI. Three success metrics can only be measured through it. |
| **The deployment stack has no milestone** (PITFALLS gap 4) | 7 services, 2 images, Caddy, GHCR→SSH deploy, the `.env` holding the KEK, nightly `pg_dump`, Prometheus/Grafana. Owned by no module. |
