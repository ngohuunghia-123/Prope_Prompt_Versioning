---
gsd_state_version: 1.0
current_phase: 02
current_phase_name: seams-enqueue-the-broker-drain-and-the-ceiling
status: executing
stopped_at: Completed 02-04-PLAN.md
last_updated: "2026-08-10T09:44:28.876Z"
last_activity: 2026-08-10
last_activity_desc: Plan 01-01 complete — foundation and tenancy tracer
progress:
  total_phases: 24
  completed_phases: 1
  total_plans: 9
  completed_plans: 8
  percent: 4
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-09)

**Core value:** No prompt reaches production without a recorded human approval, and every call can be traced back to the exact revision that served it.
**Current focus:** Phase 02 — seams-enqueue-the-broker-drain-and-the-ceiling

## Current Position

Phase: 02 (seams-enqueue-the-broker-drain-and-the-ceiling) — EXECUTING
Plan: 5 of 5
Status: Ready to execute
Last activity: 2026-08-10 — Phase 02 execution started

Progress: [█████████░] 89%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 2h | 4 tasks | 21 files |
| Phase 01 P02 | 1h | 2 tasks | 8 files |
| Phase 01 P03 | ~25m | 2 tasks | 10 files |
| Phase 01 P04 | ~45m | 2 tasks | 5 files |
| Phase 02 P01 | 105min | 3 tasks | 19 files |
| Phase 02 P02 | 65m | 3 tasks | 13 files |
| Phase 02 P03 | 14min | 2 tasks | 6 files |
| Phase 02 P04 | 23min | 3 tasks | 8 files |

## Accumulated Context

### Decisions

Full log in PROJECT.md Key Decisions (54 ADRs + 13 high-blast-radius assumptions). The ones that constrain phase 1 most directly:

- **ADR-0019**: Cost is priced once, at write time — a price row added later never moves an existing call
- **ADR-0045**: Every table is tenant-scoped unless declared global; the coverage test walks all eight schemas
- **ADR-0018**: The body store has no read path in the MVP — call-ledger is a sink with no edge to access-control
- **ADR-0041**: Broker-first with a direct-write fallback — metadata survives a broker outage, only bodies drop

Cross-cutting for every phase: **build database-first.** The migration carries the guarantee (constraint, privilege, policy, grant, trigger); the application code is what the guarantee protects.

- [Phase 01]: OQ-A resolved text-no-cast: workspace_id is text and every RLS predicate compares text to text with no cast (Task 3 gate, phase 01-01). Phases 2-24 inherit the type.
- [Phase 01]: alembic/ddl.py is imported by revisions as a bare 'ddl' via prepend_sys_path, never as 'alembic.ddl' — that dotted name is the installed Alembic package's own dialect submodule.
- [Phase 01]: alembic_version lives in public (version_table_schema), so D-06's coverage walk over the eight module schemas never has to except a bookkeeping table.
- [Phase 01]: ledger.price_table is append-only by database privilege (SELECT, INSERT only for prope_app) — T-006/D-07 landed in Phase 1, asserted live with a visible-row positive control and a mutation test that restores and revokes the grant inside the suite.
- [Phase 01]: EXPECTED_ABSENT_SCHEMAS in tests/architecture/test_tenant_coverage.py is a per-phase constant naming the seven declared schemas not yet built. Phase 7 (access) is the first phase that must shrink it in the same change or inherit a red test.
- [Phase 01]: No separate index over price_table's four UNIQUE columns — the constraint's own index serves the effective-dated lookup, and the planned name exceeded PostgreSQL's 63-byte identifier limit.
- [Phase 01]: A priced cost of exactly zero raises rather than storing a zero or downgrading to unpriced — the encoding has three states and both silent answers would be untrue (01-03)
- [Phase 01]: The retention window is a keyword argument with a 30-day default, not a column (OQ-B); no table outside call-ledger's data.owns was touched (01-03)
- [Phase 01]: GATE-04's 'zero tokens and zero cost' fallback row is pinned as usage_status=unknown / cost_status=not_applicable with NULLs (OQ-E), asserted in a test so Phase 19 inherits it (01-03)
- [Phase 01]: CL-11 left unchecked: its 'unknown count reported alongside the total' clause is get_run_totals, which the ROADMAP puts in Phase 2 (01-03)
- [Phase ?]: FOR UPDATE SKIP LOCKED (A7) was dropped from the retention chunk: a locking select needs the UPDATE privilege and prope_app deliberately holds only SELECT/INSERT/DELETE on call_body. Proven live (permission denied; identical statement without the clause succeeds). The grant was not widened.
- [Phase ?]: CL-08 ticked on the reading that its traced acceptance criterion AC-8 is met in full; no scheduler and no cross-tenant sweep ship (OQ-C), and that is stated rather than implied.
- [Phase ?]: 02-01: prope.call_record is a CLASSIC DURABLE queue (Task 1 checkpoint) — reject-publish-dlx is the only overflow mode that both dead-letters AND nacks the publisher, and quorum queues cannot do it at all
- [Phase ?]: 02-01: x-queue-type: classic is declared explicitly rather than left to the broker default, so a drifting default cannot silently produce a queue reject-publish-dlx does not exist on
- [Phase ?]: 02-01: the drain acks per WORKSPACE GROUP after that group's commit, never per window and never multiple=True — the window is N transactions and two workspaces' delivery tags interleave
- [Phase ?]: 02-01: classify_write_failure defaults to PERMANENT (dead-letter) because a classic queue has no x-delivery-limit, so an unclassified requeue is an infinite loop
- [Phase ?]: 02-01: HANDOFF_MAXSIZE=512, WINDOW_SIZE=500, WINDOW_MS=250, prefetch=WINDOW_SIZE — each argued from the stated rate/backlog targets and recorded at the constant
- [Phase ?]: D-09 implemented: ledger.workspace_retention is a sixth table; the deviation from call-ledger.lock.yml data.owns is raised as OQ-018, not patched into the spec
- [Phase ?]: A-055's no-body rule keeps no database guard: migration 0004 records a knowing exception to database-first, and tests/security/test_eval_no_body_boundary.py asserts the absence so a later body reader inherits a recorded boundary
- [Phase ?]: WARN-2 closed by carrying the one-currency invariant into UPSERT_WORKSPACE_SPEND's DO UPDATE ... WHERE; a zero rowcount is the refusal, and the Phase 1 pre-read is kept alongside (the repricing.UPDATE_TO_PRICED both-places posture)
- [Phase ?]: writer.period_month(at) is public and takes an instant, so write_records and plan 02-04's check_spend_ceiling file into the same UTC month by calling one function rather than by agreeing
- [Phase ?]: 02-03: the retention job's scheduler ships in Phase 2 and is work beyond both named requirements (D-12), because no other phase owns it
- [Phase ?]: 02-03: RETENTION_SWEEP_INTERVAL_SECONDS = 300 — the interval cannot BE the ten-minute deadline, since worst observed age is interval + run_time
- [Phase ?]: 02-03: the retention sweep's workspace enumerator is a named seam with a documented Phase 2 stand-in — an unscoped cross-tenant SELECT returns zero rows under ADR-0045, so the literal design would have run cleanly and deleted nothing
- [Phase ?]: 02-03: a supervised job is a name plus a zero-argument coroutine FACTORY and nothing else — the contract ADR-0049's claim loop (Phase 16) and ADR-0051's sweep (Phase 22) inherit
- [Phase ?]: check_spend_ceiling refuses at >= the monthly limit, on INT-020's 'a run that starts UNDER the ceiling finishes' wording
- [Phase ?]: CeilingReason ships as a StrEnum machine code (MONTHLY_CEILING_EXCEEDED), not a human string — ADR-0053's client-renders-the-code rule
- [Phase ?]: A ceiling and a spend total in different currencies is an UNEVALUABLE check: fail open and count, never refuse on a figure that does not exist (A-107)
- [Phase ?]: RunTotals.cost is None rather than Decimal(0) for a run with nothing priced — a zero beside a null currency is a number with no unit
- [Phase ?]: The fail-open branch ships in Phase 2 and CL-07 is NOT ticked; CL-11's second clause is built and its Phase 1 / Pending row is left for the developer

### Pending Todos

None yet.

### Blockers/Concerns

**Nothing blocks the build.** All eight modules are `ready_for_build: true` and no open question carries `blocks_build: true`. Five questions remain open; two gate the pilot.

*Gating the pilot (not the build):*

- **OQ-013** (high, narrowed): PII and redaction for stored call bodies. Residency is answered (ADR-0033, ADR-0039); retention is a setting; there is no reader to permission (ADR-0018). Open: whether a redaction pass runs before storage — real build work that either exists or does not.
- **OQ-006** (high, narrowed): Data classification and retention. Identity is answered (ADR-0029); the role matrix is a seed over a closed vocabulary. Open: policy about what the pilot may hold.
- **A-020 holds the line until both close: no real corporate prompts in the pilot.**

*Gating nothing:*

- **OQ-005** (high, open): The real deadline and team size. A one-person answer triggers the recorded re-scope against prompt-registry (M5).
- **OQ-012** (medium, narrowed): Uptime target and latency budget. A-031's p95 50 ms is an agent placeholder until this closes; the instrumented span exists either way.
- **OQ-008** (medium, open): Is an owner one person or a team, and what happens on transfer? A-051 assumes one person; ADR-0054 answers departure separately.

*Structural gaps carried from the handoff (see `.planning/research/PITFALLS.md`):*

- **16 acceptance criteria are owed and were never written as rows**, and 8 more assert against infrastructure a later decision replaced. Each is catalogued with the phase that should absorb it. Phase plans must use the restated form, not the lock files' literal text.
- **The React SPA and the deployment stack own no milestone.** Both need a user decision before the pilot; neither blocks phase 1.

*Resolved during phase 01:*

- ~~Phase 01 plan 01-01 Task 2: no Docker daemon.~~ **RESOLVED 2026-08-10.** Docker Desktop was already installed; the executor's probe was wrong. `docker info` exits 0, Server 29.6.2, and `docker run --rm postgres:17 postgres --version` prints `postgres (PostgreSQL) 17.10`. The image is pulled and cached. **Standing environment fact every later plan needs: `docker` is NOT on the default bash PATH — shells that drive it must first `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`.** There is no `DOCKER_HOST` to set; this is Docker Desktop over the Windows named pipe, not a WSL engine. testcontainers reaches the daemon without PATH help.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-08-10T09:43:59.711Z
Stopped at: Completed 02-04-PLAN.md
Resume file: None
