# Phase 2: Seams: enqueue, the broker drain, and the ceiling - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-10
**Phase:** 2-seams-enqueue-the-broker-drain-and-the-ceiling
**Areas discussed:** Retention setting's home, app/worker process shape, The eval seam's name, Broker in tests + queue args

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Retention setting's home | `PUT /workspaces/{id}/retention` has to persist somewhere and `data.owns` is fixed at five tables | ✓ |
| app / worker process shape | Both processes are created this phase; 22 later phases inherit the shape | ✓ |
| The eval seam's name | INT-019 registers `price_usage`; the lock's `apis.exposes` omits it | ✓ |
| Broker in tests + queue args | Real RabbitMQ vs. a fake, and A-149's immutable queue arguments | ✓ |

**User's choice:** all four.
**Notes:** Two areas were raised in the preamble and not offered as selectable options — management-route authentication before access-control exists (Phase 7), and the six routes' request/response shapes. Both landed in CONTEXT.md's Claude's Discretion list rather than being decided.

---

## Retention setting's home

### Where the setting lives

| Option | Description | Selected |
|--------|-------------|----------|
| A sixth table | `ledger.workspace_retention`. Clean subject boundary, picked up by the ADR-0045 coverage walk and the tenant policy for free. Costs a declared deviation from `data.owns` plus an OQ raised upstream | ✓ |
| Column on `spend_ceiling` | The only per-workspace settings row that exists. No new table, no deviation. Costs: a table named for spend, and a `PUT /spend-ceiling` writing the whole row can clobber retention | |
| Generic `ledger.setting` table | `workspace_id` + key + value. One home for anything later. Costs: untyped column, no CHECK worth writing, invites undeclared settings | |

**User's choice:** A sixth table.
**Notes:** Recommended on the grounds that a ceiling and a retention window are two policies with different owners and lifecycles, and that sharing one upsert target creates a real clobber bug.

### What a shortened window does to stored bodies

| Option | Description | Selected |
|--------|-------------|----------|
| Nothing — stamped is stamped | Existing rows keep their `expires_at`; only later writes get the new window. A-106 read literally. Needs no grant change | ✓ |
| Backfill `expires_at` on change | Immediate effect. Costs: `prope_app` needs `UPDATE` on `call_body`, a grant Phase 1 withheld deliberately | |
| Delete-on-shorten instead | Immediate effect using the existing `DELETE` grant. Costs: a settings write that destroys data as a side effect | |

**User's choice:** Nothing — stamped is stamped.
**Notes:** Verified before asking: `alembic/versions/0003_ledger_tables.py:251` grants `call_body` `SELECT, INSERT, DELETE` with the comment "No UPDATE: bodies are written once and deleted." The backfill option was a grant change, not a code change, and the question was framed that way.

### Who reads the setting row

| Option | Description | Selected |
|--------|-------------|----------|
| Drain reads, passes in | One indexed read per workspace batch; `write_records` stays a pure function of its arguments; Phase 3's degraded fallback path inherits no settings query | ✓ |
| `write_records` reads it itself | No caller can forget. Costs: a settings read on the fallback path that runs when the broker is already down | |
| Constant only, no read yet | Cheapest now. Costs: a route that persists a setting nothing reads is a lie for a phase | |

**User's choice:** Drain reads, passes in.

### Whether the retention scheduler lands here

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, schedule it now | `worker` is born this phase and `deployment_target` names both jobs as its residents. Otherwise no phase owns the invocation | ✓ |
| No — drain only, defer to Phase 3 | Keeps this phase tight to CL-06 and CL-09. Costs: the promise is kept by no running process for another phase, and Phase 3 has no requirement pointing at it either | |

**User's choice:** Yes, schedule it now.
**Notes:** Flagged at the time as work beyond this phase's two named requirements; CONTEXT.md requires the plan to say so out loud.

---

## app / worker process shape

### How the entrypoints find each module's work

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit central composition | `prope/app.py` and `prope/worker.py` import and wire by hand. Greppable; makes AC-10's route-table assertion an enumeration of one file | ✓ |
| Per-module `register()` hooks | Each context owns its wiring over a declared module list. Costs: an indirection at exactly the place the route-table test must see everything | |
| Auto-discovery by convention | Scan `src/prope/*/api.py`. Zero editing. Costs: a route can appear because a file was named a certain way | |

**User's choice:** Explicit central composition.

### What runs the worker's concurrent jobs

| Option | Description | Selected |
|--------|-------------|----------|
| `asyncio.TaskGroup` supervisor | One loop, one process, backoff on crash, SIGTERM drain. No new dependency. Costs: restart/backoff/shutdown becomes code this project writes | ✓ |
| APScheduler for the timers | Cron-ish declarations instead of hand-written loops. Costs: a dependency whose misfire semantics are one more thing to know at 3am, for two interval jobs | |
| Separate worker commands | Failure isolation per job. Costs: ADR-0033 fixes the runtime at 7 services and 2 images | |

**User's choice:** `asyncio.TaskGroup` supervisor.
**Notes:** Must accommodate evaluation's claim loop (ADR-0049, Phase 16) and release-control's sweep (ADR-0051, Phase 22) without redesign.

### How the drain forms a batch

| Option | Description | Selected |
|--------|-------------|----------|
| Size-or-time window | Up to N messages or T ms, group by `workspace_id`, ack the window after commit, prefetch bounded to the window. N and T justified against ≥500/sec and p95 lag < 2 s | ✓ |
| One message per transaction | Simplest. Costs: ADR-0040's grouping becomes a no-op and ≥500/sec becomes a per-record round-trip budget | |
| Drain the queue greedily | Naturally batches under load. Costs: an unbounded window turns a post-outage backlog into one enormous transaction — the shape A-132 forbade for the retention job | |

**User's choice:** Size-or-time window.

### `/readyz` semantics in this phase

| Option | Description | Selected |
|--------|-------------|----------|
| Ship final semantics now | Database only; broker outage is a separate counted-degraded signal. Nothing written twice. Costs: a one-phase window where readiness is green and records are genuinely lost | ✓ |
| Broker-gated now, narrowed in Phase 3 | Honest at every point in time. Costs: a readiness rule written, tested, then deliberately deleted one phase later | |

**User's choice:** Ship final semantics now.
**Notes:** The question also asked whether `worker` gets a readiness endpoint; the options did not cover it. Resolved in CONTEXT.md as **no HTTP endpoint on `worker`, process-level compose healthcheck**, derived from ADR-0028 rather than chosen — and labelled as such (D-17) so a planner does not read it as a settled preference.

---

## The eval seam's name

### One seam or two

| Option | Description | Selected |
|--------|-------------|----------|
| Two named seams | `enqueue` and `price_usage` over one `write_records`. Their failure contracts are opposite — one may never raise, the other must — so one function would break a caller. Treat `apis.exposes` as an omission and raise an OQ | ✓ |
| One seam with a `source` flag | Matches `apis.exposes` literally. Costs: the never-raises and must-raise guarantees cannot both hold in one function | |
| `price_usage` only | Build for evaluation now; `enqueue` is really the gateway's publish. Costs: ships an unproven publish path under a name no downstream spec uses | |

**User's choice:** Two named seams.
**Notes:** The conflict is between `docs/modules/call-ledger.lock.yml` `apis.exposes` (three seams) and `docs/architecture/interfaces.md` INT-019 (a fourth). The lock's own `inputs` block cites INT-019, and its step-5 change_log entry records INT-019 being registered deliberately — so the omission reading is well supported.

### Who owns `price_usage`'s transaction

| Option | Description | Selected |
|--------|-------------|----------|
| call-ledger opens its own | A raise leaves evaluation able to record a run error, which it could not do inside a transaction that just rolled back. Costs: two transactions, so a crash between them is possible | ✓ |
| Caller's session, like property-history | ADR-0023's pattern; run state and usage commit together. Costs: a pricing failure would roll back the run's own state, and the sink would be reaching into a module doing work | |

**User's choice:** call-ledger opens its own.

### `get_run_totals` and the missing workspace

| Option | Description | Selected |
|--------|-------------|----------|
| Add `workspace_id` to the signature | Caller passes the workspace it already holds — same posture as `check_spend_ceiling`. Costs: deviates from INT-021 as registered; rides the same OQ | ✓ |
| Caller supplies the session | Keeps the registered one-argument signature. Costs: inconsistent with the own-transaction decision one question earlier | |
| A fifth `SECURITY DEFINER` lookup | Resolves `run_id` to its workspace. Costs: exactly four are sanctioned and a test asserts the set | |

**User's choice:** Add `workspace_id` to the signature.
**Notes:** The problem is circular without it — the lookup that would resolve the workspace returns zero rows without a tenant context already set.

### Failed publisher confirm in Phase 2

| Option | Description | Selected |
|--------|-------------|----------|
| Count and drop, name the gap | `publish_failed_total` increments, nothing raises, the plan states the lossy window and that CL-01 closes it | ✓ |
| Pull the fallback forward | No record lost by this phase's code; the delta is small since `write_records` takes a single-record batch. Costs: Phase 3 then verifies a claim it did not build | |

**User's choice:** Count and drop, name the gap.

---

## Broker in tests + queue args

### Real broker or a fake

| Option | Description | Selected |
|--------|-------------|----------|
| Real RabbitMQ testcontainer | The only way to observe publisher confirms, redelivery on an unacked restart, and the declared queue arguments. Costs: a second container and a slower suite | ✓ |
| Fake the aio-pika seam | Fast and deterministic for the drain's logic. Costs: the three load-bearing claims are exactly what a fake cannot prove | |
| Fake by default, real for a smoke test | Middle ground on suite time. Costs: two provisioning paths — the split D-02 rejected by name | |

**User's choice:** Real RabbitMQ testcontainer.

### Queue arguments

| Option | Description | Selected |
|--------|-------------|----------|
| Declare with args + assert them | A-149's TTLs and max-lengths set, overflow dead-letters, and a test reads the arguments back from the broker. T-005's full sweep still lands in Phase 3 | ✓ |
| Declare with args, assert in Phase 3 | Tight test surface now. Costs: for one phase the arguments are correct by intention rather than assertion — the posture T-006 was written about | |
| Declare minimally, add args in Phase 3 | Get it working now. Costs: RabbitMQ refuses a redeclare with different arguments, so this means deleting and redeclaring the queue in every environment that has run | |

**User's choice:** Declare with args + assert them.

### Who declares

| Option | Description | Selected |
|--------|-------------|----------|
| Both, from one shared definition | Idempotent, order-independent, mismatch structurally impossible | ✓ |
| `worker` declares, `app` assumes | One declaring process. Costs: turns deploy ordering into a data-loss question on the path that must never raise | |
| A separate deploy-time step | Matches how schema is treated. Costs: the testcontainer rig has to run it too — a second provisioning path | |

**User's choice:** Both, from one shared definition.

### Whether `enqueue` awaits the confirm

| Option | Description | Selected |
|--------|-------------|----------|
| Hand off, confirm in background | Caller's span is a bounded in-process handoff, inside p95 < 1 ms; a background task publishes, awaits, counts — and in Phase 3 does the direct write at that failure site. What A-139 already assumes | ✓ |
| Await the confirm inline | Failure known synchronously; no in-process buffer. Costs: a broker round-trip inside a 1 ms budget, achievable on a healthy loopback broker and not on a struggling one | |

**User's choice:** Hand off, confirm in background.
**Notes:** Explicitly distinguished from ADR-0041's deleted spill file — that was a durable on-disk store with a replay job, not an in-process handoff.

---

## Claude's Discretion

Left to the researcher and planner, open rather than decided:

- The drain window's N and T, and the prefetch that follows, argued against ≥500/sec and p95 < 2 s
- The in-process handoff's bound, its full-buffer behaviour, and the counter that reads it
- Management-route authentication before access-control exists (Phase 7), and how AC-10's "every route declares an action" obligation is not silently defaulted to unauthenticated
- The six routes' request/response shapes against A-045, including INT-028's `422` on an ambiguous effective range
- `check_spend_ceiling`'s `reason` — an ADR-0053 machine `code` or a literal string
- What `get_run_totals` does with a run spanning two currencies
- Whether the three deviations (D-09, D-18, D-20) become one OQ or three
- Broker connection management in `app` — one robust connection with a confirm-mode channel, or a pool
- Whether any Prometheus/structlog wiring lands this phase, or only the counters D-16, D-21 and D-23 name as their own controls
- `prope_report` read grants on `ledger.workspace_retention`, carried forward from Phase 1's identical open item

## Deferred Ideas

None — discussion stayed within phase scope. The items recorded in CONTEXT.md's `<deferred>` section are fixed ROADMAP boundaries (Phase 3's durability work, the gateway, evaluation, the SPA and the deployment stack), noted so a planner does not mistake them for gaps.
