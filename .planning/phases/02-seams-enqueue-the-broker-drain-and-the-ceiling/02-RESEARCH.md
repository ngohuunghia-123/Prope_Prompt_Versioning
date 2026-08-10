# Phase 2: Seams: enqueue, the broker drain, and the ceiling — Research

**Researched:** 2026-08-10
**Domain:** RabbitMQ 4.x consumer/publisher semantics over aio-pika; FastAPI management surface; RLS-scoped batched writes; a two-process runtime born in this phase
**Confidence:** HIGH on the broker facts and the in-repo state; MEDIUM on the drain-window numbers (arithmetic given, not measured); LOW on nothing that is load-bearing

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

*Copied verbatim from `.planning/phases/02-seams-enqueue-the-broker-drain-and-the-ceiling/02-CONTEXT.md` § Implementation Decisions. Numbering continues from Phase 1's D-01…D-08.*

**The retention setting**

- **D-09:** The retention window lives in a **sixth table, `ledger.workspace_retention`**
  (`workspace_id` PK, the window, `updated_by`, `updated_at`), not as a column on `spend_ceiling` and
  not in a generic key/value settings table. A ceiling and a retention window are two policies with
  different owners and different lifecycles, and sharing `spend_ceiling`'s row means a
  `PUT /spend-ceiling` that writes the whole row can clobber retention. The new table is picked up
  automatically by D-06's coverage walk and by the tenant policy, so it inherits RLS rather than
  retrofitting it. **This is a declared deviation from the lock file's `data.owns`, which names five
  tables** — an `OQ-NNN` must be raised against `docs/modules/call-ledger.lock.yml` `data.owns`
  naming the field and the conflict. Per `.planning/BSP-LINK.md` the spec is not edited to agree.
  — **Reversibility:** costly.
- **D-10:** `expires_at` is **stamped once at write and never rewritten**. Shortening a workspace's
  window applies only to bodies written after the change; existing rows keep the expiry they were
  given. This is A-106 read literally and it needs no grant change — `call_body` holds
  `SELECT, INSERT, DELETE` and deliberately **no `UPDATE`**. The consequence to state in the plan: a
  workspace tightening its policy waits up to the old window, and `oldest_body_age_seconds` reads
  above the new window meanwhile. Neither a backfilling `UPDATE` nor a delete-on-shorten side effect
  is built. — **Reversibility:** costly.
- **D-11:** **The drain reads the setting; `write_records` does not.** The drain's batch is already
  grouped per workspace, so it reads one indexed row per group and passes `retention_window` in.
  `write_records` stays a pure function of its arguments, and Phase 3's direct-write fallback
  inherits no settings query. The 30-day constant remains the default when no row exists;
  **absence of a row is the default, not an error**. That two callers must both remember to read it
  is answered by a test, not by discipline.
- **D-12:** **The retention job's scheduler lands in this phase**, inside `worker`. `worker` is born
  here and `deployment_target` names both the drain and the retention job as its residents.
  **The plan must state out loud that this is work beyond this phase's two named requirements.**

**The two processes**

- **D-13:** **Explicit central composition.** `src/prope/app.py` imports call-ledger's router and
  includes it; `src/prope/worker.py` imports the drain and the retention job and runs them. Adding a
  module means editing two files by hand. Neither `register()` hooks over a declared module list nor
  auto-discovery by filename convention is used. `Makefile run` already targets `prope.app:app`.
  — **Reversibility:** costly.
- **D-14:** **An `asyncio.TaskGroup` supervisor runs the worker's jobs.** One event loop, one
  process; the supervisor starts each job as a task, restarts a crashed one with backoff, and drains
  cleanly on `SIGTERM`. Timer jobs are plain interval loops. No scheduler library is added. Separate
  per-job container commands are rejected (ADR-0033 fixes 7 services / 2 images). Accepted cost:
  restart, backoff and graceful shutdown become code this project writes and tests. The supervisor
  must accommodate evaluation's claim loop (ADR-0049, Phase 16) and release-control's overdue sweep
  (ADR-0051, Phase 22) without being redesigned. — **Reversibility:** costly.
- **D-15:** The drain forms a batch on a **size-or-time window**: accumulate up to N messages or T
  milliseconds, group by `workspace_id`, one `workspace_transaction` per group, ack the whole window
  **after commit**. Prefetch is set to the window size. **N and T are open** — the plan must justify
  them against the ≥500 records/sec drain target and the p95 < 2 s enqueue-to-durable lag, not pick
  round numbers. One-message-per-transaction is rejected; a greedy full-queue drain is rejected.
- **D-16:** `/readyz` on `app` **ships its final semantics now**: the database alone. A broker
  outage is a separate counted-degraded signal, never un-readiness. **The plan must name the
  resulting Phase 2 gap explicitly**: for one phase there is a window where the broker is down,
  readiness is green, and records genuinely are lost — CL-01 is what closes it.
- **D-17:** `worker` exposes **no HTTP endpoint**, including no `/healthz` or `/readyz`; its compose
  healthcheck is process-level. **Derived from ADR-0028**, not chosen by the user. If a planner
  disagrees, this is an OQ, not a quiet reversal.

**The seams**

- **D-18:** **`enqueue` and `price_usage` are two named functions**, both over the one
  `write_records`. The lock's `apis.exposes` is treated as an **omission**, because the two failure
  contracts are opposite and one function cannot hold both: `enqueue` **never raises into the
  caller, ever** (INT-018), while `price_usage` **raises, and evaluation records a run error**
  (INT-019). Raise an `OQ-NNN` naming `docs/modules/call-ledger.lock.yml` `apis.exposes`.
  — **Reversibility:** one-way.
- **D-19:** **call-ledger's seams open their own transactions.** `price_usage` opens its own
  `workspace_transaction` and either commits or raises; it does not take evaluation's session. The
  property-history pattern (ADR-0023) is deliberately not copied. Accepted cost: an eval run's state
  change and its usage write are two transactions, and a crash between them is possible. The upsert
  on `call_id` (Phase 3) is what makes the retry safe.
- **D-20:** **`get_run_totals` takes the workspace: `get_run_totals(workspace_id, run_id)`.** INT-021
  registers a one-argument signature, but with D-19's own-transaction shape RLS needs a tenant set
  before any read. A fifth `SECURITY DEFINER` resolver is refused. **Rides the same OQ as D-18.**
  — **Reversibility:** one-way.
- **D-21:** On a failed or nacked publisher confirm in Phase 2, `enqueue` **counts and drops**:
  `publish_failed_total` increments, a log line is written **with no body in it** (A-046), and
  nothing raises. The direct-write fallback is **not** pulled forward from Phase 3. **The plan must
  state plainly that this leaves a known-lossy window for one phase and that CL-01 closes it.**

**The broker**

- **D-22:** **A real RabbitMQ testcontainer joins the Postgres one**, session-scoped. It is the only
  way to observe a publisher confirm arriving, redelivery behaviour on an unacknowledged consumer
  restart, and the queue holding the arguments that were declared. A fake at the aio-pika seam is
  rejected; a fast-fake default with a skippable real-broker smoke test is rejected as the
  two-provisioning-paths split D-02 refused by name. — **Reversibility:** costly.
- **D-23:** **The queue is declared with A-149's full arguments in this phase, and a test reads them
  back from the broker and asserts them.** `prope.call_record`: 24 h message TTL, 1,000,000
  max-length. `prope.call_record.dlq`: 30-day TTL, 100,000 max-length. Overflow **dead-letters**
  rather than drops. RabbitMQ refuses to redeclare a queue with different arguments, so adding them
  in Phase 3 would mean deleting and redeclaring the queue in every environment that has run.
  T-005's full security sweep (including the `dlq_depth` gauge and its alert rule) still lands in
  Phase 3. — **Reversibility:** one-way in any environment that has run.
- **D-24:** **Both processes declare, from one shared definition.** A single declaration module in
  `call_ledger` holds the queue, the DLQ, the arguments and the bindings; `app` declares on publisher
  startup and `worker` declares on consumer startup, calling the same code. A worker-declares-only
  shape is rejected; a separate deploy-time init command is rejected.
- **D-25:** **`enqueue` hands off; a background task publishes and awaits the confirm.** The caller's
  span is a bounded in-process handoff, comfortably inside the p95 < 1 ms measured in the caller's
  process; the background task publishes, awaits confirms, and counts failures — and in Phase 3 does
  the direct write at that same failure site. Awaiting the confirm inline is rejected. Accepted and
  to be stated: this is a bounded in-process buffer with its own full-buffer behaviour, and a hard
  kill loses what is in it, which A-139 already accepts. **This is not the spill file.**
  — **Reversibility:** costly.

### Claude's Discretion

*Copied verbatim. These are **open, not decided** — resolve them from the lock file, the interfaces
registry and the phase's success criteria, and state the resolution in the plan.*

- **The drain window's numbers** (D-15's N and T), and the prefetch that follows from them, argued
  against ≥500 records/sec and p95 < 2 s rather than chosen.
- **The in-process handoff's bound and full-buffer behaviour** (D-25) — the ceiling, what happens at
  it, and which counter reads it.
- **Management-route authentication before access-control exists.** INT-028 says route-level session
  auth (INT-005) is the boundary and there is no INT-001 call here; access-control ships in Phase 7.
  What Phase 2's routes do in the interim, and how AC-10's "every route declares an action from the
  vocabulary" obligation is not silently defaulted to unauthenticated.
- **The six routes' request and response shapes** against A-045's conventions — the one error
  envelope, cursor pagination, `prc_` ULIDs, and INT-028's `422` on a price row with an ambiguous
  effective range.
- **`check_spend_ceiling`'s `reason`** — a machine `code` the client translates per ADR-0053, or a
  literal string. The refusal must carry no figure under any branch, including refused.
- **What `get_run_totals` does with a run spanning two currencies** — A-107 forbids conversion, so a
  sum across two is a number with no unit; `write_records` already raises on a mixed-currency batch.
- **How many OQs the three deviations become** — D-09, D-18 and D-20 are three conflicts with two
  upstream files. One OQ or three is a planner call; all three must be raised.
- **Broker connection management in `app`** — one long-lived robust connection with a
  confirm-mode channel, or a pool. Bounded by D-25's handoff shape.
- **Whether Phase 2 wires any Prometheus/structlog at all**, given the full metric set is Phase 3's,
  or only the counters D-16, D-21 and D-23 name as their own controls.
- **`prope_report` read grants** on `ledger.workspace_retention`, carried forward from Phase 1's
  identical open item.

### Deferred Ideas (OUT OF SCOPE)

*Copied verbatim.*

None — discussion stayed within phase scope.

Recorded so a planner does not mistake them for gaps, they are fixed ROADMAP boundaries rather than
omissions:

- The **direct-write fallback**, the **idempotent upsert on `call_id`**, the **no-body-read-path
  route-table assertion**, the **17-metric observability set**, and the **50 rps load targets** belong
  to **Phase 3** (CL-01, CL-02, CL-07, CL-10, CL-12).
- The **gateway** that will call `enqueue` is Phases 19–21; the **evaluation** module that will call
  `price_usage`, `check_spend_ceiling` and `get_run_totals` is Phases 16–18.
- The **React SPA** that consumes INT-028's five routes and the **deployment stack** own no milestone
  (PITFALLS §3 and §4). Both need a user decision; neither blocks this phase.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **CL-06** | "A workspace over its monthly ceiling has eval runs refused with a reason and no spend figure, while its gateway traffic continues to be recorded normally" [VERIFIED: .planning/REQUIREMENTS.md:27] | § *The three internal contracts* → `check_spend_ceiling`; § *Don't Hand-Roll* row on the refusal shape; § *Pitfall 8* (the month-boundary read); the `pk_workspace_spend PRIMARY KEY (workspace_id, period_month)` row shape is the whole read |
| **CL-09** | "An eval-case usage row is priced and counted toward workspace spend with no body stored" [VERIFIED: .planning/REQUIREMENTS.md:30] | § *The three internal contracts* → `price_usage`; § *Pitfall 4* — `ck_call_record_eval_calls_carry_run` requires `case_id`, and the no-body rule has **no** database constraint behind it today |

**Also touched but not owed by this phase** — state it, do not tick it:

- **CL-11** clause 2 (`get_run_totals` reports the unknown count alongside the total) is ROADMAP
  Phase 2 Success Criterion 3, while its REQUIREMENTS.md row reads `CL-11 | M1 | Phase 1 | … | Pending`
  [VERIFIED: .planning/REQUIREMENTS.md:176]. Phase 1 left this open as human-verification item 2.
  The Phase 2 plan builds clause 2 whether or not the bookkeeping is resolved.
- **CL-07** (fail-open) is Phase 3 [VERIFIED: .planning/REQUIREMENTS.md:181]. INT-020 and A-142 §2
  make fail-open part of the seam's *contract*, so the branch should exist now; the *claim* is
  Phase 3's.
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

Extracted from `./.claude/CLAUDE.md`. Treat with the same authority as CONTEXT.md's locked decisions.

| Directive | Bearing on this phase |
|---|---|
| Python 3.13.x pinned; FastAPI + uvicorn + pydantic v2 | `pyproject.toml:8` is `requires-python = ">=3.13,<3.14"`; all four are already pinned and unused |
| SQLAlchemy 2.0 async over asyncpg; **Alembic carries RLS policies, constraints, triggers** | `ledger.workspace_retention` arrives as migration `0004` with its policy and grants in the same revision |
| PostgreSQL 17, schema per module, RLS deny-by-default, `SET LOCAL app.workspace_id` | Every drain group opens `workspace_transaction`; a missing filter is zero rows, not an error |
| **RabbitMQ 4.x, exactly one queue `prope.call_record` plus its DLQ. A second broker queue was proposed twice and rejected — do not plan one** | The DLQ is not a second *work* queue; it is INT-018's declared dead-letter target |
| call-ledger is a SINK: forbidden edge call-ledger → anything | The six routes call no module; `check_spend_ceiling` reads its own aggregate row |
| History rows are never deleted at the database privilege level | `price_table` holds `SELECT, INSERT` only; `POST /prices` inserts and never updates |
| Refusal shapes carry security weight; `check_spend_ceiling` must refuse with a reason and **no figure** | Assert it under **every** branch including refused — the lock's `test_plan.security` says so in as many words |
| Vietnamese-only behind an i18n layer; the API returns a machine `code` the client translates | Bears directly on the discretion item for `reason`. ADR-0053:39-40: *"ADR-0003's envelope already carries a stable machine `code` beside a human `message`. **The client renders the `code`, not the `message`.**"* |
| **GSD workflow enforcement**: no direct repo edits outside a GSD workflow | Applies to execution, not to this document |
| **Do not edit `docs/`** (BSP-LINK.md § Out of bounds) | Three known conflicts (D-09, D-18, D-20) become `OQ-018`+ files, not spec patches |

---

## Summary

Phase 1 shipped a database and a pure writer. Phase 2 gives call-ledger the two processes it will
live in for the remaining 22 phases, and everything it builds is a *seam* — nothing in this phase has
a real caller yet, so every contract is proven from call-ledger's own tests. The work divides cleanly
into four independent tracks that a wave plan can parallelise: (1) migration `0004` +
`ledger.workspace_retention`; (2) the broker declaration module, `enqueue`'s handoff-and-confirm, and
the `worker` drain; (3) the three in-process seams over the existing `write_records`; (4) the six
FastAPI routes and the `prope.app` / `prope.worker` entrypoints.

The broker research produced one finding that changes a design choice the CONTEXT could not have
anticipated. **A-149's "overflow dead-letters rather than drops" is only satisfiable on a *classic*
queue**, because RabbitMQ's own documentation states that quorum queues *"do not support
`reject-publish-dlx` configurations"* [CITED: rabbitmq.com/docs/quorum-queues]. That is the one
overflow mode that both dead-letters and `basic.nack`s the publisher — and the nack is precisely the
signal D-21 counts and ADR-0041's Phase 3 fallback consumes. A classic durable queue is also the
right shape for a single-node host (ADR-0033) where Raft replication buys nothing. The cost is
explicit and must be planned for: classic queues have no `x-delivery-limit`, so **poison-message
dead-lettering is the drain's job**, not the broker's.

The second finding is sharper and is a correctness trap rather than a choice. `call_record`'s primary
key is `call_id` alone [VERIFIED: alembic/versions/0002_call_record.py:90 — `CONSTRAINT
pk_call_record PRIMARY KEY (call_id),`] and `write_records` issues a plain `INSERT INTO
ledger.call_record` [VERIFIED: src/prope/call_ledger/writer.py:64-86]. **The upsert that makes a
redelivery safe is Phase 3's, and at-least-once delivery starts in Phase 2.** Any redelivery of an
already-written record raises a unique violation that fails the whole grouped transaction — the
"poison batch forever" the Phase 1 verifier named by hand [VERIFIED:
.planning/phases/01-data-model-pricing-and-retention/01-UAT.md:20]. The plan needs an explicit,
boundary-respecting answer before it writes a line of drain code.

**Primary recommendation:** declare `prope.call_record` as a **classic durable queue** with
`x-message-ttl`, `x-max-length`, `x-overflow: reject-publish-dlx`, `x-dead-letter-exchange: ""` and an
explicit `x-dead-letter-routing-key`; drain it with `aio-pika==9.6.2` using
`channel.set_qos(prefetch_count=N)` and an async queue iterator with `no_ack=False`; **commit and ack
per workspace group, not per window**; classify every write failure as permanent (→ `reject(requeue=False)`
→ DLQ, counted) or transient (→ redeliver, back off); and treat the unique-violation-on-redelivery case
as a named, stated Phase 2 gap that CL-02 closes.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `enqueue(call_record)` handoff | **API / Backend (`app`)** | — | ADR-0028: *"`app` publishes and never consumes"*. The caller's span must stay in-process (D-25) |
| Publish + confirm + failure counting | **API / Backend (`app`)**, background task | Broker | D-25 puts the confirm off the caller's span; the counters are the control |
| Queue + DLQ declaration | **Both processes**, one shared definition | Broker | D-24. Idempotent, order-independent |
| Drain: consume → group → write | **Worker (`worker`)** | Database | ADR-0028: *"`worker` consumes and never serves HTTP"*; ADR-0040 groups by `workspace_id` |
| Per-workspace tenant scoping | **Database (RLS policy)** | Application (`workspace_transaction`) | ADR-0035/ADR-0045. A missing filter is zero rows *at the engine*, not a code review finding |
| Pricing, `expires_at`, aggregate | **Database + `write_records`** (already built) | — | Phase 1. Neither `enqueue` nor `price_usage` writes SQL of its own |
| `price_usage`, `check_spend_ceiling`, `get_run_totals` | **API / Backend, in-process library** | Database | A-142 §1: an in-process seam is a Python call in whichever container the caller runs in — these run in `worker` when evaluation calls them |
| Six management routes | **API / Backend (`app`)** | — | INT-028. Served from `app`; `worker` serves no HTTP (D-17) |
| Retention window storage | **Database (`ledger.workspace_retention`)** | Route (`PUT /retention`) | D-09. Policy and grants in migration `0004`, not in a service |
| Retention job scheduling | **Worker (`worker`) supervisor** | — | D-12/D-14. `deployment_target` names both residents of `worker` |
| `/healthz`, `/readyz` | **API / Backend (`app`) only** | Database (`/readyz`) | INT-030 + D-16/D-17 |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `aio-pika` | **9.6.2** (see note) | The RabbitMQ client for both the publisher and the drain | Named by the lock file itself: *"aio-pika (RabbitMQ, ADR-0028) — durable queue, persistent messages, publisher confirms, one DLQ"* [VERIFIED: docs/modules/call-ledger.lock.yml:291]. It is an asyncio-native wrapper over `aiormq` with publisher confirms, robust auto-reconnect and full type hints [CITED: docs.aio-pika.com] |
| `fastapi` | 0.141.1 *(already pinned)* | The six management routes | ADR-0026. `pyproject.toml:21` — pinned in Phase 1 with the comment *"no route is built until phase 2"* [VERIFIED: pyproject.toml:17-22] |
| `uvicorn[standard]` | 0.52.1 *(already pinned)* | `prope.app:app` | `Makefile:8` already targets it [VERIFIED: Makefile:7-8] |
| `pydantic` / `pydantic-settings` | 2.13.4 / 2.15.0 *(already pinned)* | Route models, the broker envelope model, `Settings` | The envelope schema is *"generated from call-ledger's pydantic model at build time"* [CITED: docs/architecture/interfaces.md:704-705] |
| `python-ulid` | 4.0.1 *(already pinned)* | `prc_` price-row ids | A-045 / ADR-0003 |
| `structlog`, `prometheus-client` | 26.1.0 / 0.26.0 *(already pinned)* | The counters D-16/D-21/D-23 name as their own controls | ADR-0030 |

> **Version note — this is a real decision, not a formality.** PyPI's current `aio-pika` is **10.0.1**,
> published 2026-07-09 [VERIFIED: pypi.org/pypi/aio-pika/json]. Its only substantive change is
> *"Update aiormq to the latest version 7"* [VERIFIED: github.com/mosquito/aio-pika releases,
> tag 10.0.0]; `aiormq 7.0.0` was published the same day [VERIFIED: pypi.org/pypi/aiormq/json]. That
> is a one-month-old major bump of the low-level protocol library, on the one code path in Prope whose
> whole purpose is durability. **9.6.2** (2026-03-22) pins `aiormq<7,>=6.8`, declares
> `requires_python = "<4,>=3.10"` and carries `Programming Language :: Python :: 3.13` and `:: 3.14`
> classifiers [VERIFIED: pypi.org/pypi/aio-pika/9.6.2/json]. It also contains the two fixes this
> phase depends on most: *"Fixed callback-based consumers not resuming after connection reconnection"*
> and *"Fixed queue iterators raising StopAsyncIteration on channel reconnection"*, both in 9.6.0
> [VERIFIED: aio-pika CHANGELOG.md]. **Recommend `aio-pika==9.6.2`**, with the reasoning written at
> the pin the way `pyproject.toml` already writes its reasoning. If the planner prefers 10.0.1, say
> why in the same place.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `testcontainers[postgresql,rabbitmq]` | 4.15.0 *(already pinned; extra is new)* | D-22's session-scoped broker container | The `rabbitmq` extra resolves to `RabbitMqContainer` in `testcontainers.community.rabbitmq` — `testcontainers.rabbitmq` is a deprecation shim that emits a `DeprecationWarning` [VERIFIED: testcontainers-4.15.0-py3-none-any.whl, `testcontainers/rabbitmq.py`] |
| `pika` | `>=1` (transitive, dev-only) | Nothing you write. It is what `RabbitMqContainer.readiness_probe` uses | `Requires-Dist: pika>=1; extra == 'rabbitmq'` [VERIFIED: testcontainers-4.15.0 METADATA]. **A sync AMQP client enters the dev group** — record it so a later reader does not think two clients are in play |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Classic durable queue | **Quorum queue** (`x-queue-type: quorum`) | Gets `x-delivery-limit` (default **20** in RabbitMQ 4.0+) and at-least-once dead-lettering for free. Loses `reject-publish-dlx` entirely, so overflow can only `drop-head` — which dead-letters the *oldest* record and never nacks the publisher, so ADR-0041's fallback never fires on overflow. Also pays Raft overhead for n=1 (ADR-0033) |
| `aio-pika` queue iterator | `queue.consume(callback)` | The callback form processes messages concurrently under `prefetch_count`, which is exactly wrong for a windowed batch drain — you want one accumulator, not N concurrent handlers |
| `asyncio.TaskGroup` supervisor | APScheduler / `arq` / Celery beat | Refused by D-14 and by A-012's surviving *debuggable by one person* clause. Two interval jobs do not pay for misfire semantics |
| Real broker in tests | Fake at the aio-pika seam | Refused by D-22 by name: a fake cannot prove a confirm arrived, a redelivery happened, or an argument was declared |
| `x-arguments` on declare | RabbitMQ **policies** (`max-length`, `message-ttl`, `dead-letter-exchange`) | The docs *"strongly recommend against"* hardcoded x-arguments because *"they cannot be updated without redeploying applications and deleting the queue"* [CITED: rabbitmq.com/docs/dlx]. D-23 locks x-arguments anyway and names that irreversibility as its own argument — but see Pitfall 2, because the DLQ TTL is declared to *inherit OQ-013*, and OQ-013 is unresolved |

**Installation:**

```bash
uv add "aio-pika==9.6.2"
uv add --dev "testcontainers[postgresql,rabbitmq]==4.15.0"
```

---

## Package Legitimacy Audit

Run against the seam: `gsd-tools query package-legitimacy check --ecosystem pypi aio-pika pika testcontainers`.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `aio-pika` | PyPI | latest release 2026-07-09; project since 2016 | seam reports `null` (PyPI has no download field) | github.com/mosquito/aio-pika | **SUS** (`unknown-downloads` only) | **Approved.** Named explicitly by `docs/modules/call-ledger.lock.yml:291` — an authoritative in-repo spec, not a search result |
| `pika` | PyPI | latest release 2026-08-06 | `null` | github.com/pika/pika | **SUS** (`too-new`, `unknown-downloads`) | **Approved, dev-only, transitive.** Not chosen by us: it is `testcontainers[rabbitmq]`'s own declared dependency. `too-new` reflects a fresh point release of a 2009 project, not a new package |
| `testcontainers` | PyPI | latest release 2026-07-24 | `null` | github.com/testcontainers/testcontainers-python | **SUS** (`too-new`, `unknown-downloads`) | **Approved.** Already pinned at 4.15.0 in `pyproject.toml:35` and in use by the Phase 1 rig; only the `rabbitmq` extra is new |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** all three, in every case for `unknown-downloads` — the PyPI
JSON API exposes no download counter, so this signal fires for every PyPI package and carries no
information. No `postinstall` equivalent exists on PyPI wheels; none of the three ships a build hook.
**No `checkpoint:human-verify` task is warranted for `aio-pika` or `testcontainers`** — both are named
by in-repo authoritative specs. `pika` is a transitive dev dependency the planner should merely *name*
in the plan so its appearance in `uv.lock` is expected rather than surprising.

---

## Architecture Patterns

### System Architecture Diagram

```
                          ┌──────────────────────────── process: app (uvicorn) ───────────────────────────┐
                          │                                                                               │
  gateway (Ph.19-21) ───► │  enqueue(call_record)          ┌──────────────────────┐                       │
  [no caller in Ph.2]     │      │ put_nowait, never blocks│  bounded handoff     │                       │
                          │      └────────────────────────►│  asyncio.Queue(max=B)│                       │
                          │                                └──────────┬───────────┘                       │
                          │        full ──► count + drop              │ background publisher task         │
                          │                                           ▼                                   │
  SPA (no milestone) ───► │  FastAPI router                  publish(persistent, mandatory)               │
                          │   POST|GET /api/v1/prices                 │  await confirm                    │
                          │   GET  /api/v1/prices/unpriced            ├─ Basic.Ack   ► done               │
                          │   PUT  /workspaces/{id}/spend-ceiling     ├─ Basic.Nack  ► publish_failed{nacked}
                          │   PUT  /workspaces/{id}/retention         ├─ DeliveryError ► {unroutable}     │
                          │   GET  /healthz  (liveness, touches nothing)                                  │
                          │   GET  /readyz   (DATABASE ONLY — D-16)   └─ TimeoutError  ► {timeout}         │
                          │        │                                          │                           │
                          │        │  declare_topology() ◄── shared module ───┤ (D-24)                    │
                          └────────┼──────────────────────────────────────────┼───────────────────────────┘
                                   │                                          ▼
                                   │                        ┌───────── RabbitMQ 4.x ──────────┐
                                   │                        │ prope.call_record (classic,     │
                                   │                        │   durable, x-message-ttl 24h,   │
                                   │                        │   x-max-length 1_000_000,       │
                                   │                        │   x-overflow reject-publish-dlx,│
                                   │                        │   DLX "" ► routing key .dlq)    │
                                   │                        │            │ overflow / TTL /   │
                                   │                        │            ▼ reject(requeue=F)  │
                                   │                        │ prope.call_record.dlq (30d TTL, │
                                   │                        │   x-max-length 100_000)         │
                                   │                        └────────────┬────────────────────┘
                                   │                                     │ prefetch = N
                          ┌────────┼─────────────────────── process: worker ─┼──────────────────────────┐
                          │  declare_topology() (same code)                  ▼                          │
                          │                                    ┌──────────────────────────────┐         │
  evaluation (Ph.16-18)──►│  price_usage(run_id, rows) ──┐     │ drain: accumulate N msgs      │        │
  [no caller in Ph.2]     │  check_spend_ceiling(ws)     │     │ OR T ms, whichever first      │        │
                          │  get_run_totals(ws, run_id)  │     └───────────────┬──────────────┘         │
                          │        (in-process, D-19)    │                     │ group by workspace_id  │
                          │                              │                     ▼                        │
                          │   asyncio.TaskGroup supervisor (D-14)   for each workspace group:            │
                          │     ├─ drain job                          read workspace_retention (D-11)    │
                          │     └─ retention interval job ──┐         workspace_transaction(ws)          │
                          │          delete_expired_bodies  │           write_records(session, grp, rw)   │
                          │        SIGTERM ► graceful drain │         COMMIT ──► ack that group's tags   │
                          └─────────────────────────────────┼─────────────────┬───────────────────────────┘
                                                            ▼                 ▼
                                              ┌────────────── PostgreSQL 17 (RLS) ──────────────┐
                                              │ ledger.call_record  ledger.call_body            │
                                              │ ledger.price_table  ledger.workspace_spend      │
                                              │ ledger.spend_ceiling                            │
                                              │ ledger.workspace_retention  ◄── NEW, mig 0004   │
                                              └─────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/prope/
├── app.py                      # NEW. FastAPI(); include_router(call_ledger.api.router). D-13
├── worker.py                   # NEW. asyncio.run(supervisor(...)). D-13
├── supervisor.py               # NEW. TaskGroup + restart-with-backoff + SIGTERM. D-14
├── broker/
│   ├── topology.py             # NEW. THE single declaration (queue, DLQ, args, bindings). D-24
│   └── connection.py           # NEW. connect_robust + confirm-mode channel lifecycle
├── db/                         # unchanged (engine.py, session.py, metadata.py)
└── call_ledger/
    ├── api.py                  # NEW. APIRouter — the six routes. INT-028
    ├── schemas.py              # NEW. pydantic v2 request/response models + the broker envelope
    ├── enqueue.py              # NEW. handoff + background publisher + confirm classification. D-25
    ├── drain.py                # NEW. window → group → workspace_transaction → write_records. D-15
    ├── seams.py                # NEW. price_usage / check_spend_ceiling / get_run_totals. D-18..D-20
    ├── retention_settings.py   # NEW. read/write ledger.workspace_retention. D-09, D-11
    ├── writer.py               # unchanged — every write still lands here
    ├── pricing.py repricing.py domain.py models.py retention.py   # unchanged
alembic/versions/
└── 0004_workspace_retention.py # NEW. table + tenant policy + grants, one revision. D-04's chain
tests/
├── conftest.py                 # EXTEND: session-scoped rabbitmq_container + amqp_url fixtures
├── broker/                     # NEW. declared-arguments assertion, redelivery, confirms
├── integration/                # NEW: drain, eval usage, ceiling, run totals, routes
└── architecture/               # unchanged — the coverage walk picks up table 6 by itself
```

> **The structure claim worth checking:** `tests/architecture/test_tenant_coverage.py` has
> `GLOBAL_TABLES: dict[str, str] = {}` and discovers tables from `pg_class`
> [VERIFIED: tests/architecture/test_tenant_coverage.py:37, 57-65]. `tests/conftest.py`'s
> `LIST_LEDGER_TABLES` likewise reads `pg_tables WHERE schemaname = 'ledger'`
> [VERIFIED: tests/conftest.py:63-66] and its docstring says it is *"Discovered rather than listed, so
> the later plans in this phase can add tables without editing the rig"* [VERIFIED:
> tests/conftest.py:61-62]. **`ledger.workspace_retention` therefore needs no rig edit and no test
> edit — and if migration `0004` forgets the policy, the walk goes red on its own.** That is D-09's
> "picked up automatically" claim, confirmed against the code.

### Pattern 1: One declaration module, called by both processes (D-24)

**What:** a single `declare_topology(channel)` coroutine that declares the DLQ first, then the work
queue with its dead-letter arguments pointing at the DLQ.
**When to use:** on publisher startup in `app` and on consumer startup in `worker`. Idempotent.

```python
# src/prope/broker/topology.py  — Source: rabbitmq.com/docs/dlx + docs.aio-pika.com/apidoc.html
from aio_pika.abc import AbstractChannel, AbstractQueue

WORK_QUEUE = "prope.call_record"          # A-142 §5: the ONLY queue in Prope
DLQ = f"{WORK_QUEUE}.dlq"                 # A-142 §5: "DLQ naming is <queue>.dlq"

#: A-149. Milliseconds, because x-message-ttl is documented in milliseconds.
WORK_QUEUE_ARGUMENTS = {
    "x-message-ttl": 24 * 60 * 60 * 1000,   # 24 h
    "x-max-length": 1_000_000,
    # The one overflow mode that BOTH dead-letters and basic.nacks the publisher.
    # Not available on quorum queues — see the queue-type note in RESEARCH.
    "x-overflow": "reject-publish-dlx",
    # "" is the default exchange; the routing key is then the destination queue
    # NAME. It MUST be set: without it the message keeps its own routing key,
    # which is this queue, and RabbitMQ's cycle detector drops it.
    "x-dead-letter-exchange": "",
    "x-dead-letter-routing-key": DLQ,
}

DLQ_ARGUMENTS = {
    "x-message-ttl": 30 * 24 * 60 * 60 * 1000,   # 30 days — A-149 ties this to A-040 / OQ-013
    "x-max-length": 100_000,
    # No DLX on the DLQ: a dead-letter of a dead-letter has nowhere honest to go.
}


async def declare_topology(channel: AbstractChannel) -> AbstractQueue:
    """Declare the DLQ, then the work queue. Order matters only for clarity —
    RabbitMQ does not require the DLX target to exist at declare time, but a
    missing one silently drops dead-lettered messages."""
    await channel.declare_queue(DLQ, durable=True, arguments=DLQ_ARGUMENTS)
    return await channel.declare_queue(
        WORK_QUEUE, durable=True, arguments=WORK_QUEUE_ARGUMENTS
    )
```

**Anti-pattern this replaces:** declaring in the worker only. D-24 rejects it because it *"turns
deploy ordering into a data-loss question on the one path that must never raise"*.

### Pattern 2: Hand off, publish in the background, classify the confirm (D-25, D-21)

The `prope_call_ledger_publish_failed_total` metric is declared with `labels: reason = unroutable |
nacked | timeout` [VERIFIED: docs/modules/call-ledger.lock.yml:372-373 — `# labels: reason =
unroutable | nacked | timeout`]. aio-pika's documented confirm-handling pattern produces **exactly
those three** failure shapes and no others:

```python
# Source: docs.aio-pika.com/rabbitmq-tutorial/7-publisher-confirms.html (Strategy #3)
from aio_pika import Message, DeliveryMode
from aio_pika.abc import AbstractExchange
from aio_pika.exceptions import DeliveryError
from pamqp.commands import Basic

async def publish_and_handle_confirm(exchange: AbstractExchange, body: bytes) -> None:
    try:
        confirmation = await exchange.publish(
            Message(body, delivery_mode=DeliveryMode.PERSISTENT),   # ADR-0028: persistent
            routing_key=WORK_QUEUE,
            mandatory=True,
            timeout=5.0,
        )
    except DeliveryError:                       # returned mandatory message
        publish_failed.labels(reason="unroutable").inc()
    except TimeoutError:                        # no confirm inside the timeout
        publish_failed.labels(reason="timeout").inc()
    else:
        if not isinstance(confirmation, Basic.Ack):   # Basic.Nack / Basic.Reject
            publish_failed.labels(reason="nacked").inc()
```

**`enqueue` itself never awaits this.** It does `queue.put_nowait(record)` inside a
`try/except asyncio.QueueFull`, and returns. That is the whole of the caller's span.

### Pattern 3: The window, the grouping, and where the ack goes (D-15, ADR-0040)

```python
# Sketch. The load-bearing parts are the per-group commit and the per-group ack.
await channel.set_qos(prefetch_count=WINDOW_SIZE)    # per-consumer in RabbitMQ, see Pitfall 6
queue = await declare_topology(channel)

async with queue.iterator() as it:
    while True:
        window = await collect_window(it, size=WINDOW_SIZE, timeout_ms=WINDOW_MS)
        if not window:
            continue
        for workspace_id, group in group_by_workspace(window):
            retention = await read_retention_window(sessionmaker, workspace_id)   # D-11
            try:
                async with workspace_transaction(sessionmaker, workspace_id) as session:
                    await write_records(session, drafts_of(group), retention_window=retention)
            except PermanentWriteError:
                await reject_each(group)         # → DLQ, reason "rejected". Counted.
            except TransientWriteError:
                await nack_each(group, requeue=True)   # redelivered; back off
            else:
                await ack_each(group)            # AFTER commit — D-15's "ack after commit"
```

> **Read D-15's "ack the whole window after commit" as "ack each group after *its* commit".** The
> window is not one transaction — ADR-0040 makes it N transactions, one per distinct workspace. If
> group 3 fails and groups 1–2 have already committed, acking the *window* is impossible without
> either acking committed-and-failed work together or redelivering committed work. Per-group acking
> is the only shape that preserves both halves. `IncomingMessage.ack(multiple=True)` treats the
> delivery tag as *"up to and including"* [CITED: docs.aio-pika.com/apidoc.html], which is a
> per-window optimisation that becomes unsafe the moment groups can fail independently — do not
> reach for it here.

### Pattern 4: The supervisor (D-14)

```python
# src/prope/supervisor.py — sketch. Python 3.13, asyncio.TaskGroup.
async def supervise(jobs: Mapping[str, Callable[[], Awaitable[None]]], stopping: asyncio.Event):
    async with asyncio.TaskGroup() as tg:
        for name, job in jobs.items():
            tg.create_task(_run_with_restart(name, job, stopping), name=name)

async def _run_with_restart(name, job, stopping, *, base=1.0, cap=60.0):
    delay = base
    while not stopping.is_set():
        try:
            await job()
            delay = base                      # a clean return resets the backoff
        except asyncio.CancelledError:
            raise                             # never swallow cancellation
        except Exception:
            log.exception("job_crashed", job=name)   # A-046: no body in the line
            await _sleep_or_stop(stopping, delay)
            delay = min(delay * 2, cap)
```

**Two traps in `TaskGroup` that the plan should name rather than discover:** (1) the *first*
unhandled exception in any child cancels every sibling and the group re-raises an `ExceptionGroup` —
which is why each job is individually wrapped and the group itself must never see an exception in
normal operation; (2) `SIGTERM` is not delivered to `asyncio` by default — install
`loop.add_signal_handler(signal.SIGTERM, stopping.set)` (POSIX only; the containers are Linux under
ADR-0033, but the developer's machine is Windows, so the handler installation needs a guard or the
worker cannot be run locally at all).

### Anti-Patterns to Avoid

- **Awaiting the confirm inside `enqueue`.** Rejected by D-25 by name. It puts a broker round-trip
  inside a 1 ms budget that is achievable on a healthy loopback and not on a struggling broker.
- **One transaction per message.** Rejected by D-15: it makes ADR-0040's grouping a no-op and turns
  ≥500/sec into a per-record round-trip budget.
- **A greedy full-queue drain.** Rejected by D-15: an unbounded window turns a post-outage backlog
  into one enormous transaction against the largest table in the system — the shape A-132 forbade.
- **`reject(requeue=True)` on a permanent failure.** Requeue-on-error is the aio-pika `message.process()`
  default (`requeue: bool = False` on `process`, but `requeue=True` in several tutorial snippets) —
  a permanently-failing record requeued is an infinite loop with no delivery limit on a classic queue.
- **Reading the retention window inside `write_records`.** D-11 forbids it; Phase 3's fallback runs
  when the broker is already down and must inherit no settings query.
- **A `SECURITY DEFINER` resolver to turn a `run_id` into a workspace.** Refused by D-20; a test
  asserts the sanctioned set is exactly four.
- **Auto-discovering routers by filename.** Refused by D-13; AC-10 asserts a property of the
  *assembled* route table and a route that appears because of a filename is what that test exists to
  refuse.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reliable publish | A retry loop with your own ack bookkeeping | `publisher_confirms=True` (aio-pika's **default**) + the three-branch classification above | The default already awaits the confirm and raises on nack/timeout; the tutorial pattern maps 1:1 onto the declared metric labels |
| Reconnect after a broker restart | Your own reconnect loop over `connect()` | `aio_pika.connect_robust()` | *"transparent auto-reconnects with full state recovery"* [CITED: docs.aio-pika.com]; 9.6.0 specifically fixed consumers and queue iterators not resuming after reconnection |
| Poison-message limits | A `redelivery_count` header you maintain | `x-delivery-limit` **if** you take a quorum queue; otherwise an explicit `reject(requeue=False)` on a classified permanent failure | Classic queues have no delivery limit. Do not invent a header — classify the exception instead |
| Pricing, `expires_at`, the monthly aggregate | Anything at all | `write_records(session, records, *, retention_window)` | Its own docstring: *"There is one implementation of it on purpose"* [VERIFIED: src/prope/call_ledger/writer.py:4-7] |
| Setting the tenant | `SET LOCAL app.workspace_id = '…'` built by interpolation | `workspace_transaction(sessionmaker, workspace_id)` | *"That would be an injection site on a value which, from phase 2 onward, arrives inside a broker payload"* [VERIFIED: src/prope/db/session.py:11-14]. **This module's docstring was written for this phase** |
| The unpriced worklist query | A new aggregate | `writer.UNPRICED_WORKLIST` | Already written, already indexed by `ix_call_record_unpriced_worklist`, with the comment *"Phase 1 owes the encoding, the index and this query. Phase 2 owes the route"* [VERIFIED: src/prope/call_ledger/writer.py:142-143] |
| The retention delete | A new DELETE | `delete_expired_bodies(...)` | Shipped in Phase 1 with its integration test. D-12 supplies only the *scheduler* |
| A ceiling aggregate | `SUM()` over `call_record` | `ledger.workspace_spend`, keyed `(workspace_id, period_month)` | *"It exists so check_spend_ceiling reads one row instead of aggregating an unbounded table before every eval run"* [CITED: docs/modules/call-ledger.lock.yml:216-219] |
| A retry/backoff scheduler | APScheduler, arq, Celery | `asyncio.TaskGroup` + an interval loop | D-14, A-012 |
| Cursor pagination, the error envelope, ULID prefixes | New conventions for `GET /prices` | A-045 / ADR-0003 (`limit` default 50, max 200; `{error: {code, message, details?, request_id}}`) | Deciding them per module means eight dialects [CITED: docs/brainstorm/assumptions/A-045.md] |

**Key insight:** almost nothing in this phase is new logic. The novel surface is *plumbing* — a
window, a grouping, an ack decision, a supervisor, and six thin routes over queries that already
exist. Every place the plan is tempted to write SQL, `write_records` or an existing constant is
already there; every place it is tempted to write reliability machinery, aio-pika or RabbitMQ has it.
The genuinely new *decisions* are the queue type, the ack boundary, and the failure classification.

---

## Common Pitfalls

### Pitfall 1: The redelivery that has no upsert behind it yet

**What goes wrong:** at-least-once delivery begins the moment the drain runs. `write_records` issues
`INSERT INTO ledger.call_record (...)` with no `ON CONFLICT`
[VERIFIED: src/prope/call_ledger/writer.py:64-86], and `call_id` is the primary key
[VERIFIED: alembic/versions/0002_call_record.py:90 — `CONSTRAINT pk_call_record PRIMARY KEY (call_id),`].
A redelivered record therefore raises `UniqueViolationError`, which fails the whole grouped
transaction, which fails again on every redelivery.
**Why it happens:** the upsert is CL-02, and CL-02 is Phase 3
[VERIFIED: .planning/REQUIREMENTS.md:180]. The Phase 1 verifier saw this coming and wrote it down:
Phase 2 is *"the first whose drain will re-deliver a poison batch forever"*
[VERIFIED: .planning/phases/01-data-model-pricing-and-retention/01-UAT.md:20].
**How to avoid:** three options, in order of how much of Phase 3 they absorb —
 (a) **classify a unique violation as a permanent failure** → `reject(requeue=False)` → DLQ, counted.
 Absorbs nothing from Phase 3, keeps the drain live, and puts the record somewhere inspectable. Costs:
 an ordinary consumer restart dead-letters real records for one phase. **Recommended, because it is
 the shape that is honest about the gap D-21 and D-16 already commit to stating.**
 (b) treat a unique violation as "already written → ack". Minimal, but it *is* CL-02's guarantee
 arriving early under another name; if the planner takes it, say so and do not tick CL-02.
 (c) pull the upsert forward. Explicitly out of scope per CONTEXT § Deferred.
**Warning signs:** the same delivery tag appearing in the log repeatedly; DLQ depth rising after a
worker restart rather than after a genuine bad record.

### Pitfall 2: The queue arguments are one-way, and one of the numbers is not settled

**What goes wrong:** RabbitMQ refuses to redeclare an existing queue with different arguments
(`PRECONDITION_FAILED`, channel error 406) — the aio-pika tutorial states it plainly: *"RabbitMQ
doesn't allow you to redefine an existing queue with different parameters and will return an error to
any program that tries to do that"* [CITED: docs.aio-pika.com/rabbitmq-tutorial/2-work-queues.html].
D-23 accepts that. What D-23 does **not** resolve is that A-149 writes the DLQ's 30-day TTL *as
inheriting OQ-013*, and OQ-013 is unresolved and rated Critical
[VERIFIED: docs/modules/call-ledger.lock.yml:736-746].
**Why it happens:** a number declared as "the same window A-040 gives `call_body`" is a number that
moves when OQ-013 answers, and moving it means deleting a queue with messages in it.
**How to avoid:** the plan must state, at the declaration site, that changing either TTL after any
environment has run requires a queue delete-and-redeclare, and RabbitMQ's own docs recommend
**policies** exactly to avoid that: *"Hardcoded x-arguments are strongly recommended against since
they cannot be updated without redeploying applications and deleting the queue before it can be
redeclared"* [CITED: rabbitmq.com/docs/dlx]. D-23 is locked on x-arguments; this is a consequence to
record, not a decision to reopen. If the planner wants to *keep* D-23's assertion property while
buying updatability, the hybrid is: declare with x-arguments (so the assertion test has something to
read back) and note that an operator may later add a same-valued policy — but note also that when
both are set, *"the minimum of the two values specified is used"* for length limits
[CITED: rabbitmq.com/docs/maxlength] and *"the one specified in arguments overrules the one specified
in policy"* for DLX [CITED: rabbitmq.com/docs/dlx]. Those two rules disagree in direction; do not
leave a reader to discover that.

### Pitfall 3: A dead-letter cycle that silently eats the message

**What goes wrong:** setting `x-dead-letter-exchange: ""` (the default exchange) without
`x-dead-letter-routing-key` re-publishes the message with **its own** routing key, which is the queue
it just came from. RabbitMQ's cycle detector then **drops it**: *"this can happen when a queue
'dead-letters' messages to the default exchange without specifying a dead-letter routing key. To
prevent automatic infinite message looping within RabbitMQ, RabbitMQ will detect a cycle and drop the
message if there was no rejection in the entire cycle"* [CITED: rabbitmq.com/docs/dlx].
**How to avoid:** always set `x-dead-letter-routing-key` to `prope.call_record.dlq`. Assert it in the
D-23 read-back test alongside the TTLs, since it is the argument whose absence loses data silently.
**Also:** *"the exchange does not have to be declared when the queue is declared but it should exist
by the time messages need to be dead-lettered. If it is missing then, the messages are silently
dropped"* [CITED: rabbitmq.com/docs/dlx] — the default exchange always exists, which is a second
argument for using it rather than a named DLX.

### Pitfall 4: `source = eval` has two constraints and neither one is the one you expect

**What goes wrong:** the phase's success criterion 2 says an eval usage row *"arrives with
`source = eval`, `run_id` and `version_id`"* and *"creates no `call_body` row"*. The database
constraint is:

```
    CONSTRAINT ck_call_record_eval_calls_carry_run
        CHECK (
            source <> 'eval'
            OR (run_id IS NOT NULL AND case_id IS NOT NULL AND consumer_key_id IS NULL)
        )
```
[VERIFIED: alembic/versions/0002_call_record.py:143-147]

So the engine requires **`case_id`**, which neither INT-019 nor the success criterion mentions, and it
does **not** require `version_id` for eval — that requirement is gateway-only:
`CHECK (source <> 'gateway' OR version_id IS NOT NULL)`
[VERIFIED: alembic/versions/0002_call_record.py:140-141].
**And there is no database constraint at all keeping `call_body` absent for an eval record.** The
only enforcement is in Python:

```python
        if draft.source == Source.EVAL and draft.body is not None:
            raise ValueError(
                f"{draft.call_id} is source=eval and carries a body; no call_body row will ever "
                "exist for an eval call (A-055)"
            )
```
[VERIFIED: src/prope/call_ledger/writer.py:205-209]

**Why it matters:** the project's stated pattern is *"build database-first — the migration carries the
guarantee"* [VERIFIED: .planning/STATE.md, Cross-cutting note]. A-055's no-body rule is the one
guarantee in this module that lives only in application code, and CL-09 is the requirement that
depends on it.
**How to avoid:** `price_usage`'s row model must require `case_id` (or the insert is refused at the
engine with a constraint name the caller cannot act on), and the plan should decide explicitly whether
migration `0004` adds a database-level guard for the no-body rule — a `BEFORE INSERT` trigger on
`call_body` that refuses when the referenced `call_record.source = 'eval'` is the only shape that
works, since a `CHECK` cannot reach another table. If it does not, record that as a knowing exception
to the database-first pattern rather than an oversight.

### Pitfall 5: The `(0,0)` price row — a Phase 1 finding that becomes live in this phase

**What goes wrong:** `ck_price_table_prices_are_non_negative` is
`CHECK (input_price_per_1k >= 0 AND output_price_per_1k >= 0)`
[VERIFIED: alembic/versions/0003_ledger_tables.py:136-137], so a free-tier `(0, 0)` row is legal.
`write_records` then raises on the resulting zero cost
[VERIFIED: src/prope/call_ledger/writer.py:237-250] and **discards the whole batch**.
**Why it matters now:** Phase 1's verifier routed this as **CR-01**, a named human-decision item whose
recommended disposition is *"accept as a Phase 2 blocking pre-condition on `POST /api/v1/prices`"*
with two named tests: *"a `(0,0)` row refused at insert; one unpriceable record not discarding its
batch-mates"* [VERIFIED: .planning/phases/01-data-model-pricing-and-retention/01-VERIFICATION.md,
Recommendation]. Phase 2 is the first phase that lets a human insert a price row **and** the first
whose drain re-delivers a failing batch.
**How to avoid:** the plan must carry CR-01 as an explicit pre-condition on the price-write route, and
the drain's failure classification (Pitfall 1) is where "one unpriceable record not discarding its
batch-mates" actually gets built. **Check `.planning/phases/01-.../01-UAT.md` for the recorded
disposition before planning** — the file's `awaiting: user response` may since have been answered.

### Pitfall 6: Prefetch is per-consumer, and the window is what bounds memory

**What goes wrong:** RabbitMQ *"deviates from the AMQP 0-9-1 specification: the prefetch limit is
applied separately to each new consumer on the channel"* [CITED: rabbitmq.com/docs/consumer-prefetch].
`prefetch_count=0` means **infinite**. Two consumers on one channel each get N in flight, so D-15's
"the broker never hands over more than one window of unacknowledged work" holds only for a single
consumer — which is also what the lock file's throughput row assumes: *"batched inserts, bodies
included, **single writer**"* [CITED: docs/modules/call-ledger.lock.yml:319].
**How to avoid:** one drain consumer, one channel, `set_qos(prefetch_count=N)`, and a test that the
worker starts exactly one. Also size N against memory, not only throughput: the envelope carries
request and response bodies (INT-018), so N unacked messages is N × body size resident in the process.

### Pitfall 7: The one-currency-per-workspace invariant becomes a race the moment a drain exists

**What goes wrong:** `write_records` reads `workspace_spend.currency` and then upserts
[VERIFIED: src/prope/call_ledger/writer.py:322-339]. The Phase 1 verifier logged this as **WARN-2**:
*"a read-then-write race: two concurrent drains can produce a USD-labelled total containing VND, which
the CHECK cannot see … Becomes live the moment Phase 2's worker runs more than one consumer. The fix
(move the invariant into the `ON CONFLICT ... WHERE`) belongs with the drain"*
[VERIFIED: .planning/phases/01-.../01-VERIFICATION.md § Warnings].
**How to avoid:** either keep strictly one consumer *and assert it* (which also satisfies Pitfall 6),
or move the invariant into the upsert's `WHERE` clause as WARN-2 prescribes. Do not do neither.

### Pitfall 8: The month boundary is the record's own, and the ceiling read must use the same clock

**What goes wrong:** `write_records` derives `period_month` from *the record's own `created_at`*,
never wall clock: *"A drain catching up across a month boundary must not file September's calls under
August"* [VERIFIED: src/prope/call_ledger/writer.py:160-168]. `check_spend_ceiling` has no record — it
must pick a month itself. If it reads `date.today()` in local time while the writer files by UTC, the
two disagree for up to a day each month, and the disagreement is invisible.
**How to avoid:** `check_spend_ceiling` computes `period_month` as the first of the current **UTC**
month, by the same helper the writer uses; and the *helper*, not the caller, is what a test pins. The
lock's own AC-6 phrasing — *"a workspace with a monthly ceiling that its gateway traffic alone has
already exceeded"* — is testable only if both sides file traffic into the same month.

### Pitfall 9: `delete_expired_bodies(chunk_size=0)` spins forever, and D-12 is what wires an operator value

**What goes wrong:** WARN-1: *"`delete_expired_bodies(chunk_size=0)` loops forever, opening a
transaction per iteration (`0 < 0` is false, `max_chunks` defaults to `None`) … Fix before Phase 2
wires an operator-supplied value"* [VERIFIED: .planning/phases/01-.../01-VERIFICATION.md § Warnings].
Confirmed against the loop [VERIFIED: src/prope/call_ledger/retention.py:147-169].
**How to avoid:** two lines of validation in `delete_expired_bodies`, in the same plan that adds D-12's
scheduler.

### Pitfall 10: `/readyz` that touches the broker, and `/healthz` that touches anything

**What goes wrong:** the obvious readiness check includes the broker. D-16 and INT-030 both forbid it:
call-ledger is ready when *"the database is reachable"*, and *"a broker outage is
degraded-and-counted, not un-ready"* [CITED: docs/architecture/interfaces.md:1186]. And
*"`/healthz` … must never touch the database, the broker, or another module"*
[CITED: docs/architecture/interfaces.md:1176-1177].
**How to avoid:** two tests — `/healthz` returns 200 with the database container stopped; `/readyz`
returns 503 naming the failed check with the database stopped and 200 with the broker stopped.
The second one is the assertion D-16 exists for, and it needs the D-22 broker fixture to be
stoppable, which argues for a function-scoped "broker down" helper beside the session-scoped
container.

### Pitfall 11: The management routes have no authentication story yet, and defaulting is the failure

**What goes wrong:** INT-028 says *"Route-level session auth (INT-005) is the boundary; there is no
INT-001 call here"* [CITED: docs/architecture/interfaces.md:1096], and A-142 §8 puts the management
API behind a *"server-side session row via HttpOnly Secure SameSite=Lax same-origin cookie"*.
access-control ships in Phase 7. Six routes mounted with no dependency is six routes that are
unauthenticated by default, and nothing in the repo will say so.
**How to avoid:** a single placeholder dependency (`require_session`) that every route declares and
that currently refuses with a recorded, testable behaviour, so Phase 7 replaces an implementation
rather than adding a decorator to six call sites. Whatever the planner chooses, the discretion item
demands it be **stated**, and a test that enumerates the router and asserts every route carries the
dependency is what stops the next module inheriting the gap.

---

## Code Examples

### Reading back the declared arguments (D-23's assertion)

Two approaches; both are AMQP-only or management-API-only, and the choice affects the container image.

**(a) Management HTTP API — direct, needs the `-management` image and port 15672 exposed.**

```python
# conftest.py — the container must expose 15672 as well as 5672
container = (RabbitMqContainer("rabbitmq:4.3-management")
             .with_exposed_ports(5672, 15672))
# the test then GETs /api/queues/%2F/prope.call_record and reads response["arguments"]
```

**(b) Pure AMQP: assert by refusal.** A `passive=True` declare checks existence only and ignores
arguments, so it cannot verify them. A *non-passive* redeclare with a different value raises
`PRECONDITION_FAILED` (406) — which proves the stored value differs from the one offered. Declaring
with the exact expected arguments succeeds. Together those two pin every value.

```python
# Each failed declare closes the CHANNEL, so every attempt needs a fresh one.
for argument, wrong_value in [("x-message-ttl", 1), ("x-max-length", 1),
                              ("x-overflow", "drop-head"),
                              ("x-dead-letter-routing-key", "nope")]:
    async with connection.channel() as ch:
        with pytest.raises(ChannelPreconditionFailed):
            await ch.declare_queue(WORK_QUEUE, durable=True,
                                   arguments={**WORK_QUEUE_ARGUMENTS, argument: wrong_value})
```

Recommendation: **(a)** for the positive assertion (it is literally "reads them back from the broker",
which is D-23's wording) and **(b)** for one negative control, so the test cannot pass by reading a
dict it constructed itself.

### The RabbitMQ testcontainer fixture (D-22)

```python
# tests/conftest.py — joins the existing session-scoped Postgres rig
from testcontainers.community.rabbitmq import RabbitMqContainer   # NOT testcontainers.rabbitmq

@pytest.fixture(scope="session")
def rabbitmq_container() -> Iterator[RabbitMqContainer]:
    # Pin the minor. The class default is "rabbitmq:latest", which drifts;
    # the Postgres fixture pins "postgres:17" for the same reason.
    with RabbitMqContainer("rabbitmq:4.3-management").with_exposed_ports(5672, 15672) as c:
        yield c

@pytest.fixture(scope="session")
def amqp_url(rabbitmq_container: RabbitMqContainer) -> str:
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"
```

Verified against the module's own source: `RabbitMqContainer.__init__` defaults
`image: str = "rabbitmq:latest"`, defaults user/password to `guest`/`guest` from
`RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS`, exposes only `self.port` (5672), and its
`start()` runs a `pika.BlockingConnection` readiness probe
[VERIFIED: testcontainers-4.15.0-py3-none-any.whl, `testcontainers/community/rabbitmq/__init__.py`].

> **Isolation, carried over from Phase 1.** The existing rig truncates every `ledger` table between
> tests rather than rolling back, because *"the transaction-local tenant setting survives a savepoint,
> so tenant A's context contaminates tenant B inside the same test"*
> [VERIFIED: tests/conftest.py:22-26]. The broker needs the equivalent: a session-scoped container
> with a **per-test purge** of both queues, or every drain test inherits the previous test's backlog.
> Purge, do not delete-and-redeclare — a redeclare with matching arguments is fine but a mismatch is
> a 406 that reads as an unrelated failure.

### The three seams' shapes

```python
# src/prope/call_ledger/seams.py

async def price_usage(sessionmaker, run_id: str, usage_rows: Sequence[EvalUsageRow]) -> None:
    """INT-019. RAISES — evaluation records a run error (A-142 §2). D-19: opens its OWN transaction."""
    # every row: call_id (caller-generated), workspace_id, run_id, case_id (see Pitfall 4),
    # version_id, provider_config_id, upstream_model, tokens, outcome, created_at, body=None

async def check_spend_ceiling(sessionmaker, workspace_id: str) -> CeilingDecision:
    """INT-020. Returns {allowed: bool, reason?}. NEVER a figure, under ANY branch.
    Fails OPEN and counts (A-104) — the branch exists now; CL-07 proves it in Phase 3."""

async def get_run_totals(sessionmaker, workspace_id: str, run_id: str) -> RunTotals:
    """INT-021 + D-20. {input_tokens, output_tokens, cost, currency,
    unpriced_count, unknown_usage_count}. The two counts are part of the answer."""
```

`get_run_totals`'s query has an index waiting for it, added in Phase 1 with a comment naming this
phase: *"get_run_totals lands in phase 2; cheap to add now, awkward to add later on what becomes the
largest table in the system"* over
`CREATE INDEX ix_call_record_workspace_id_run_id ON ledger.call_record (workspace_id, run_id) WHERE run_id IS NOT NULL`
[VERIFIED: alembic/versions/0002_call_record.py:164-170]. **That index leads with `workspace_id`,
which is independent corroboration for D-20's two-argument signature** — the one-argument form in
INT-021 could not use it.

The two counts should be computed from the stored encoding, matching `WriteResult`'s documented
contract: *"so Phase 2's `get_run_totals` can compute the same number with a
`count(*) FILTER (WHERE usage_status = 'unknown')` and get the same answer"*
[VERIFIED: src/prope/call_ledger/domain.py:188-192]. Note the asymmetry the plan must not smooth
over: `unpriced_count` filters `cost_status = 'unpriced'`, while `unknown_usage_count` filters
`usage_status = 'unknown'` — and a record with unknown usage has `cost_status = 'not_applicable'`
[VERIFIED: src/prope/call_ledger/writer.py:215-218], so the two counts do not overlap and neither is
derivable from the other.

**On a run spanning two currencies** (a discretion item): `write_records` refuses a mixed-currency
*batch* with *"a sum across two of them would be a number with no unit"*
[VERIFIED: src/prope/call_ledger/writer.py:309-313], but two batches written at different times can
still put two currencies under one `run_id` if a price row's currency changed mid-run.
**Recommendation: raise**, matching INT-021's declared failure semantics (*"raises → run error at
evaluation, and no delta"*) and matching the module's established posture of refusing rather than
inventing. Returning `cost=None` is the alternative and is defensible, but it makes "no cost" and "two
currencies" indistinguishable to the review screen, which is the exact information INT-021 says the
counts exist to preserve.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Classic mirrored queues for HA | Quorum queues / streams | RabbitMQ 4.0 — *"Classic queue mirroring was removed starting with RabbitMQ 4.0"* [CITED: rabbitmq.com/docs/quorum-queues] | Irrelevant at n=1 (ADR-0033), but it is why "classic queue" no longer implies "mirrored" and carries no deprecation smell |
| No delivery limit anywhere | Quorum queues default `x-delivery-limit` to **20** | RabbitMQ 4.0 [CITED: rabbitmq.com/docs/quorum-queues] | Free poison-message dead-lettering — but only if you take a quorum queue, and a quorum queue cannot do `reject-publish-dlx` |
| `x-arguments` at declare time | **Policies**, updatable at runtime | Current docs *"strongly recommend against"* hardcoded x-arguments [CITED: rabbitmq.com/docs/dlx] | Directly in tension with D-23; see Pitfall 2 |
| `testcontainers.rabbitmq` | `testcontainers.community.rabbitmq` | testcontainers-python 4.x | The old path is a shim that raises `DeprecationWarning`; the repo's Postgres fixture already uses the `community` path [VERIFIED: tests/conftest.py:46] |
| aio-pika 9.x on aiormq 6.x | aio-pika 10.x on aiormq 7 | 2026-07-09 | One month old at the time of writing. See the Standard Stack version note |
| `asyncio.gather` for supervision | `asyncio.TaskGroup` | Python 3.11 | The aio-pika docs themselves note *"In Python 3.11 a `TaskGroup` can be used instead of the `list` with `asyncio.gather`"* [CITED: docs.aio-pika.com/rabbitmq-tutorial/7-publisher-confirms.html] — D-14 is current practice, not a bet |

**Deprecated/outdated in this repo:**
- **Root `Dockerfile` and `docker-compose.yml` are boilerplate from another project.** The Dockerfile
  reads `FROM python:3.11-slim` and `COPY requirements.txt` (a file that does not exist); the compose
  file declares a single `backend` service with a `/health` healthcheck. Both contradict ADR-0026
  (3.13), ADR-0033 (7 services, 2 images) and INT-030 (`/healthz`). PITFALLS §4 assigns the deployment
  stack to no milestone, so **this phase does not own fixing them** — but D-13 and D-17 both describe
  compose-shaped facts, and a planner reading the repo will find these files. Record them in
  `deferred-items.md` so they read as known, not as the shape to extend.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `x-overflow: reject-publish-dlx` on a **classic** queue is the shape that satisfies A-149's "overflow dead-letters rather than drops" *and* composes with ADR-0041's fallback | Summary, Pattern 1 | The docs verify the mechanics of each mode; the *choice between them* is my reasoning, not a spec instruction. If the project prefers quorum, `drop-head` + DLX also literally dead-letters, and the plan changes rather than breaks |
| A2 | `aio-pika==9.6.2` over `10.0.1` | Standard Stack | Judgement about a one-month-old `aiormq` major on a durability path. Both versions are current and supported; this is a risk posture, not a fact |
| A3 | Per-**group** ack rather than per-window ack is the correct reading of D-15 | Pattern 3 | If a reviewer reads D-15 literally, the plan owes an OQ rather than a reinterpretation. The reasoning (groups commit independently) is stated so it can be disagreed with |
| A4 | Recommending option (a) for Pitfall 1 (unique violation → DLQ) | Pitfall 1 | Dead-letters real records on an ordinary restart for one phase. Option (b) is cheaper operationally but absorbs CL-02 early |
| A5 | Suggested window figures: **T ≈ 250 ms, N ≈ 500, prefetch = N** | Environment / arithmetic below | Arithmetic against stated targets, not measurement. D-15 requires the plan to *argue* the numbers; this is the argument, not the answer |
| A6 | `check_spend_ceiling`'s `reason` should be a machine `code` | Project Constraints | ADR-0053 §5 states the API stays machine-readable and the client renders the `code`. Applying a *management-API envelope* convention to an *in-process seam* is my extension of it |
| A7 | `require_session` placeholder dependency on all six routes | Pitfall 11 | A shape decision in a phase where access-control does not exist. Any shape works provided it is declared and tested; this one minimises Phase 7's diff |
| A8 | Migration `0004` should consider a `BEFORE INSERT` trigger for A-055's no-body rule | Pitfall 4 | Adds a trigger the spec never asked for. The alternative — recording a knowing exception to database-first — is equally defensible and cheaper |
| A9 | `rabbitmq:4.3-management` as the pinned test image | Code Examples | The tag exists and is current [VERIFIED: hub.docker.com rabbitmq tags, `4.3.4-management` / `4.3-management`, updated 2026-08-07]; whether to pin `4.3` or `4` is style, matching `postgres:17`'s major-only pin would argue for `4` |
| A10 | The i18n obligation reaches `check_spend_ceiling`'s reason at all | Project Constraints | ADR-0053 governs *user-facing strings in the SPA* and the API envelope. An in-process seam has no UI; the reason only becomes user-facing when evaluation surfaces it in Phase 17 |

---

## Open Questions (RESOLVED)

**Status: all six closed during planning. None of these is open at execution time.**

These were open *to the researcher*, at the moment this document was written. Every one of them was
answered in the plans, and each item below carries the answer that was adopted, so this heading cannot
be mistaken for unfinished work. Genuinely unsettled questions leave this document entirely and become
`docs/brainstorm/open_questions/OQ-NNN.md` files against the upstream spec — items 1 and the two
signature conflicts it names are exactly that, and they are recorded as OQ-018, OQ-019 and OQ-020
(plus OQ-021, raised later in planning, on the shared session dependency's ownership). An `OQ-NNN` file
is the only place a Phase 2 question is still open.

1. **How many `OQ-NNN` files do D-09, D-18 and D-20 become, and starting at which number?**
   - **ADOPTED: three files — OQ-018, OQ-019, OQ-020**, the recommendation below, one per blocked
     upstream field. OQ-018 lands in plan 02-02; OQ-019 and OQ-020 in plan 02-04. All three
     `blocks_build: false`. *(A fourth, OQ-021, was raised in plan 02-05 for a question that surfaced
     after this document was written.)*
   - What we know: the highest existing is `OQ-017` [VERIFIED: `ls docs/brainstorm/open_questions/`
     returns `OQ-001.md` … `OQ-017.md`], so the next free id is **OQ-018**. The file format is YAML
     frontmatter (`id`, `severity`, `status`, `research`, `discussion`, `owner`, `created`, `blocks:`)
     followed by a `#` heading and prose [VERIFIED: docs/brainstorm/open_questions/OQ-017.md:1-16].
   - What's unclear: one file naming three conflicts, or three files. CONTEXT calls it a planner call.
   - Recommendation: **three files (OQ-018, OQ-019, OQ-020)**, because each `blocks:` a different
     upstream field — `call-ledger.lock.yml` `data.owns`, `call-ledger.lock.yml` `apis.exposes`, and
     `interfaces.md` INT-021's signature — and a resolver can accept one without accepting the others.
     `blocks_build: false` for all three; the code ships either way.

2. **Is CR-01's disposition already recorded?**
   - **ADOPTED: no — it was still `awaiting: user response` when the planner read it, and the plans
     treat that absence as an absence.** Option (a) is implemented on both halves: plan 02-05 refuses a
     `(0,0)` price row at `POST /api/v1/prices`, and plan 02-01 makes one unpriceable record dead-letter
     alone without discarding its batch-mates. The disposition is carried forward as a `<human-check>`
     in plan 02-05's verification rather than assumed.
   - What we know: `01-UAT.md` frontmatter reads `status: testing` with test 1 `awaiting: user
     response` [VERIFIED: .planning/phases/01-data-model-pricing-and-retention/01-UAT.md:1-20].
   - Recommendation: the planner reads that file first. If it is still open, carry CR-01 as a named
     pre-condition on the price-route plan exactly as the verifier recommended, and do not treat the
     absence of an answer as an answer.

3. **Does Phase 2 wire Prometheus at all, and where does a full handoff buffer get counted?**
   - **ADOPTED: the recommendation, in full.** Plan 02-01 defines four counters in
     `src/prope/observability.py` and increments **both** `metadata_dropped_total` and
     `enqueued_total{outcome=…}` on a buffer-full drop, and `metadata_dropped_total` on a failed confirm
     as well. **No paging alert rule is written** — that is Phase 3's T-005 sweep — and no `/metrics`
     endpoint ships this phase.
   - What we know: `prope_call_ledger_publish_failed_total` has closed labels `unroutable | nacked |
     timeout` [VERIFIED: docs/modules/call-ledger.lock.yml:372-373]; `prope_call_ledger_enqueued_total`
     has `labels: source, outcome` [VERIFIED: docs/modules/call-ledger.lock.yml:355-356]; and
     `prope_call_ledger_metadata_dropped_total` carries the note `# must stay 0 — see the failure mode`
     [VERIFIED: docs/modules/call-ledger.lock.yml:365-366].
   - What's unclear: a D-25 buffer-full drop is not one of `publish_failed`'s three reasons. It is,
     honestly, a metadata drop.
   - Recommendation: increment **both** `metadata_dropped_total` and the appropriate
     `enqueued_total{outcome=…}` on a buffer-full drop, and — because Phase 2 has no fallback —
     increment `metadata_dropped_total` on a failed confirm too. That makes D-21's known-lossy window
     *measurable* rather than merely stated, which is the difference the lock's own risk section calls
     *"an incident and a lie"*. Do **not** wire the paging alert rule; that is Phase 3's T-005 sweep.

4. **What is `enqueue`'s buffer bound?**
   - **ADOPTED: `HANDOFF_MAXSIZE = 512`**, in plan 02-01, sitting just above the arithmetic's 100-record
     two-second figure with headroom for a burst, and bounded rather than unbounded for the reason
     below. The constant carries the arithmetic in a `#:` comment at its definition.
   - Arithmetic to argue it with: the enqueue-to-durable target is p95 < 2 s at 50 rps
     [VERIFIED: docs/modules/call-ledger.lock.yml:324-328]. A buffer that holds more than a couple of
     seconds of traffic at that rate is a buffer whose contents a hard kill loses (A-139) without
     bounding anything useful. 50 rps × 2 s = 100 records. A bound of a few hundred is defensible;
     an unbounded `asyncio.Queue` is not, because it converts a broker outage into memory growth in
     the process serving the gateway's response path.

5. **Do the drain window numbers survive contact with the targets?** *(D-15's explicit demand)*
   - **ADOPTED: `WINDOW_MS = 250`, `WINDOW_SIZE = 500`, `prefetch_count = WINDOW_SIZE`**, in plan 02-01,
     with the arithmetic below written at the constants and Pitfall 6's per-consumer memory caveat named
     beside them. Plan 02-03's single-consumer assertion is what keeps the prefetch bound true.
   - Targets: drain ≥ 500 records/sec sustained [VERIFIED: docs/modules/call-ledger.lock.yml:317-323];
     enqueue→durable p95 < 2 s, p99 < 10 s at 50 rps [VERIFIED: …:324-329]; a 60 s backlog at 50 rps
     (3,000 messages) drained within 60 s [VERIFIED: …:342-349].
   - The arithmetic: sustained throughput ≈ `N / (T + write_time_per_window)`. Batching adds at most
     `T` to a record's lag. **At 50 rps, T dominates and N is irrelevant** — a 250 ms window holds
     ~12 messages, so the steady-state lag is ~T plus the write, decades inside 2 s. **N only matters
     during a backlog**, where the window fills instantly and throughput is `N / write_time`. For
     ≥500/sec with a 250 ms floor per window you need `N ≥ 500 × 0.25 = 125` before accounting for
     write time at all; `N = 500` gives roughly 4× headroom and clears the 3,000-message backlog in
     ~6 windows.
   - Recommendation: **T = 250 ms, N = 500, `prefetch_count = 500`** — stated as an argued starting
     point with the memory caveat from Pitfall 6, and with a test that measures rather than asserts
     the numbers. The lock file says the margin *is* the point: *"a writer that merely keeps up has no
     capacity to clear a backlog after a stall"* [CITED: docs/modules/call-ledger.lock.yml:322-323].

6. **`prope_report` grants on `ledger.workspace_retention`** *(carried from Phase 1's identical item)*
   - **ADOPTED: take the default — `report_select: True`**, in plan 02-02's migration `0004`, matching
     every Phase 1 table rather than introducing a per-table exception on a policy row.
   - What we know: `grant_table` defaults `report_select: bool = True` and every Phase 1 table took the
     default [VERIFIED: alembic/ddl.py:97-123, 252-262].
   - Recommendation: take the default. A retention window is a policy setting, not a body; ADR-0037
     already records `prope_report` as a full-read credential.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker daemon | D-22's two testcontainers | ✓ | Server 29.6.2 (STATE.md, resolved 2026-08-10) | none — D-02/D-22 refuse a second provisioning path |
| `postgres:17` image | existing rig | ✓ | pulled and cached | — |
| `rabbitmq:4.3-management` image | D-22 | ✗ (not yet pulled) | 4.3.4 current [VERIFIED: hub.docker.com] | first test run pulls it; add a warm-up step so the first CI run's timeout is not the surprise |
| `uv` | build/test | ✓ | Makefile uses `uv run` throughout | — |
| Network egress to PyPI | `aio-pika`, the `rabbitmq` extra | ✓ | — | — |

**Standing environment fact, carried from Phase 1 and still true:** `docker` is **not** on the default
bash PATH — a shell driving it must first
`export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`. testcontainers reaches the daemon
without PATH help [VERIFIED: .planning/STATE.md § Resolved during phase 01].

**Second environment fact this phase adds:** the development host is **Windows**
(`Platform: win32`), and `loop.add_signal_handler` is **not implemented on Windows**. D-14's graceful
`SIGTERM` drain cannot be exercised locally without a guard. The plan needs either a
`sys.platform`-guarded handler installation plus a directly-callable `stop()` for the test, or a
`KeyboardInterrupt`/`asyncio.CancelledError` path that the test drives instead. Discovering this while
writing `worker.py` costs an hour; naming it now costs a line.

**Missing dependencies with no fallback:** none.

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high`
[VERIFIED: .planning/config.json].

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | **partly** | Session auth is INT-005 in Phase 7. Phase 2's obligation is not to *default* to unauthenticated silently — see Pitfall 11 |
| V3 Session Management | no (this phase) | ADR-0029/ADR-0043 land in Phase 7 |
| V4 Access Control | **yes, as tenancy** | Postgres RLS, deny-by-default, `workspace_transaction`. call-ledger performs no permission check by design (ADR-0018) |
| V5 Input Validation | **yes** | pydantic v2 on the six routes **and on the broker envelope** — the envelope is untrusted input that reaches `SET LOCAL app.workspace_id` via `set_config`'s bound parameter. INT-028's `422` on an ambiguous effective range is a validation rule, not a database one |
| V6 Cryptography | no | *"This module holds no credential and never sees one"* [CITED: docs/modules/call-ledger.lock.yml:443-444] |
| V7 Error Handling & Logging | **yes** | A-046: no body, prompt body, fallback answer or variable value in any log line or metric label — **including the publish-failure log D-21 specifies** |
| V8 Data Protection | **yes** | The broker is a second body store (T-005). A-149's TTLs are the mitigation and D-23 is where they land |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **T-005 — the DLQ is a body store with no policy** (HIGH, from the lock) | Information disclosure (B8) | A-149's four arguments, declared **and asserted** in this phase (D-23). The `dlq_depth` gauge and its alert are Phase 3 |
| A body reaching a log line from the publish-failure path | Information disclosure | D-21 says the line carries no body. Assert it: a test that provokes a failed confirm and greps the captured log record for the body string |
| SQL injection via `workspace_id` from a broker payload | Tampering (B4) | `set_config('app.workspace_id', :ws, true)` — bound, never interpolated [VERIFIED: src/prope/db/session.py:41]. **WR-06 from Phase 1 is live here**: the docstring claims *"a source gate asserts it"* and no such gate exists. This phase is the one where the value starts arriving from outside the process; write the gate or delete the sentence |
| A mis-stamped `workspace_id` writing into another tenant | Tampering / elevation (B4) | The policy's `WITH CHECK`, written out explicitly [VERIFIED: alembic/ddl.py:81-93]. It is the guard that earns most exactly on this write path (ADR-0040) |
| Forged call record moving a workspace's spend | Spoofing (B8) | **T-007, MEDIUM, accepted**: *"anything able to publish already holds the `.env` that also holds the KEK"* [CITED: docs/modules/call-ledger.lock.yml:477-478]. Do not re-mitigate |
| `check_spend_ceiling` leaking a billing position | Information disclosure | No figure under **any** branch including refused — the lock's `test_plan.security` requires this assertion by name |
| Broker credentials | — | From the single `.env` (ADR-0032), never in CI. The test rig's `guest:guest` is a container that lives for one session, matching the Phase 1 precedent for role passwords [VERIFIED: tests/conftest.py:53-59] |
| A new route quietly returning a body | Information disclosure | AC-10 asserts the *assembled* route table and **cannot run before Phase 23** [VERIFIED: .planning/research/PITFALLS.md:98]. D-13's explicit composition is what keeps it writable. Phase 2's contribution is not to add a route that would fail it |

---

## Sources

### Primary (HIGH confidence)

- **In-repo, read this session** — `docs/modules/call-ledger.lock.yml`,
  `docs/architecture/interfaces.md` (INT-018/019/020/021/024/028/030),
  `docs/adr/0028`, `0040`, `0041`, `0033` (grep), `0053` (grep), `0030` (grep),
  `docs/brainstorm/assumptions/A-142.md`, `A-045.md`, `.planning/BSP-LINK.md`,
  `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/research/PITFALLS.md`,
  `.planning/config.json`, `.planning/phases/01-*/01-VERIFICATION.md`, `01-UAT.md`,
  `deferred-items.md`, and the whole of `src/prope/`, `alembic/`, `tests/`, `pyproject.toml`,
  `Makefile`, `ruff.toml`, `Dockerfile`, `docker-compose.yml`
- `https://www.rabbitmq.com/docs/maxlength` — `x-max-length`, `x-overflow` values, and the exact
  sentence *"the difference between `reject-publish` and `reject-publish-dlx` is that
  `reject-publish-dlx` also dead-letters rejected messages"*
- `https://www.rabbitmq.com/docs/dlx` — the four dead-letter events, `x-dead-letter-exchange` /
  `x-dead-letter-routing-key`, the default-exchange cycle trap, the policies-over-x-arguments warning
- `https://www.rabbitmq.com/docs/quorum-queues` — *"do not support `reject-publish-dlx`"*,
  `x-delivery-limit` default 20 from RabbitMQ 4.0, classic mirroring removed in 4.0, classic is the
  default queue type
- `https://www.rabbitmq.com/docs/ttl` — `x-message-ttl` in milliseconds; expired messages dead-letter
- `https://www.rabbitmq.com/docs/consumer-prefetch` — prefetch is per-consumer; 0 is infinite
- `https://docs.aio-pika.com/` , `/apidoc.html`, `/quick-start.html`,
  `/rabbitmq-tutorial/2-work-queues.html`, `/rabbitmq-tutorial/7-publisher-confirms.html` —
  `connect_robust`, `set_qos`, `declare_queue(arguments=…)`, `publisher_confirms=True` default,
  `Basic.Ack` / `DeliveryError` / `TimeoutError`, `ack(multiple=…)`, `process()` semantics
- `https://pypi.org/pypi/aio-pika/json`, `/9.6.2/json`, `https://pypi.org/pypi/aiormq/json` —
  versions, `requires_python`, dependency pins
- `https://api.github.com/repos/mosquito/aio-pika/releases` +
  `https://raw.githubusercontent.com/mosquito/aio-pika/master/CHANGELOG.md` — 10.0.0/10.0.1 contents,
  the 9.6.0 reconnection fixes
- The `testcontainers-4.15.0` wheel itself — `testcontainers/community/rabbitmq/__init__.py` and
  `METADATA`, read from the downloaded artifact rather than from documentation
- `https://hub.docker.com/v2/repositories/library/rabbitmq/tags` — available 4.x tags

### Secondary (MEDIUM confidence)

- `gsd-tools query package-legitimacy check --ecosystem pypi …` — three `SUS` verdicts, all
  attributable to PyPI exposing no download counter

### Tertiary (LOW confidence)

- WebSearch summarisation of aio-pika confirm semantics — superseded by the primary tutorial page and
  not relied on

---

## Metadata

**Confidence breakdown:**

- **Standard stack: HIGH** — every package is either already pinned in `pyproject.toml` or named by
  `call-ledger.lock.yml`; versions and Python compatibility read from PyPI this session. The one
  judgement (9.6.2 vs 10.0.1) is flagged as A2.
- **Architecture: HIGH** — the shape is fixed by D-13…D-25, ADR-0028, ADR-0040 and ADR-0041, and the
  in-repo assets it composes over were read line by line. The one place I extend rather than transmit
  is the per-group ack boundary (A3), and the reasoning is written out.
- **Broker semantics: HIGH** — every argument name, value and behaviour is quoted from
  rabbitmq.com/docs at version 4.3, and the quorum-queue exclusion that drives the queue-type
  recommendation is a direct quotation.
- **Pitfalls: HIGH** — nine of eleven are grounded in file-and-line facts from this repository,
  including three that Phase 1's own verifier logged as explicitly Phase-2-owned (CR-01, WARN-1,
  WARN-2).
- **The window numbers: MEDIUM** — arithmetic against stated targets, offered as the argument D-15
  demands rather than as a measurement.
- **The management routes' shapes: MEDIUM** — A-045 and INT-028 fix the conventions; the concrete
  request/response models remain a discretion item the plan must settle.

**Research date:** 2026-08-10
**Valid until:** 2026-09-09 (30 days). Re-check sooner if `aio-pika` publishes 10.1.x, or if OQ-013
resolves — the DLQ TTL is declared to inherit its answer and the argument is one-way once declared.
