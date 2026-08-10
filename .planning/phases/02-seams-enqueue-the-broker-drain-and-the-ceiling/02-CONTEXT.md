# Phase 2: Seams: enqueue, the broker drain, and the ceiling - Context

**Gathered:** 2026-08-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Call-ledger stops being a schema and becomes **two running processes**. The internal contracts other
modules build against exist, the management surface is served, and the `worker`'s drain consumes
`prope.call_record` and writes batches grouped per workspace through the Phase 1 writer.

**Delivers:**
- `enqueue(call_record)` — the publish side, in `app`. Publisher confirms, never raises into the
  caller, never applies backpressure
- `price_usage(run_id, usage_rows)` — the in-process eval seam (INT-019), **not** the broker
- `check_spend_ceiling(workspace_id)` — refuses eval runs with a reason and no figure, never gateway
  traffic
- `get_run_totals(workspace_id, run_id)` — totals plus the unpriced and unknown-usage counts, which
  are part of the answer rather than diagnostics
- The management routes: `POST|GET /api/v1/prices`, `GET /api/v1/prices/unpriced`,
  `PUT /api/v1/workspaces/{id}/spend-ceiling`, `PUT /api/v1/workspaces/{id}/retention`, `/healthz`,
  `/readyz`
- The `worker` drain: consume, group by `workspace_id`, one `workspace_transaction` per group, ack
  after commit
- The two process entrypoints — `prope.app` and `prope.worker` — and the supervisor 22 later phases
  inherit
- `ledger.workspace_retention` and the scheduling of the Phase 1 retention delete inside `worker`

**Fixed out of scope by ROADMAP (do not absorb):**
- The direct-write fallback on a failed confirm, the idempotent upsert on `call_id`, the
  no-body-read-path route-table assertion (AC-10), and the 50 rps load targets — **Phase 3**
  (CL-01, CL-02, CL-07, CL-10, CL-12)
- The full observability set (17 metrics, 6 alerts) and the chaos suite — **Phase 3**
- The gateway that will call `enqueue` (Phase 19–21) and the evaluation module that will call the
  other three seams (Phase 16–18). This phase builds the seams and proves them from its own tests
- The 7-service runtime, Caddy, GHCR/CI deploy — owns no milestone (PITFALLS gap 4)

**Requirements:** CL-06, CL-09.

</domain>

<decisions>
## Implementation Decisions

Numbering continues from Phase 1's D-01…D-08. The project numbers continuously and never restarts.

### The retention setting

- **D-09:** The retention window lives in a **sixth table, `ledger.workspace_retention`**
  (`workspace_id` PK, the window, `updated_by`, `updated_at`), not as a column on `spend_ceiling` and
  not in a generic key/value settings table. A ceiling and a retention window are two policies with
  different owners and different lifecycles, and sharing `spend_ceiling`'s row means a
  `PUT /spend-ceiling` that writes the whole row can clobber retention. The new table is picked up
  automatically by D-06's coverage walk and by the tenant policy, so it inherits RLS rather than
  retrofitting it. **This is a declared deviation from the lock file's `data.owns`, which names five
  tables** — an `OQ-NNN` must be raised against `docs/modules/call-ledger.lock.yml` `data.owns`
  naming the field and the conflict. Per `.planning/BSP-LINK.md` the spec is not edited to agree.
  — **Reversibility:** costly — a table with rows in it, plus the migration and the coverage-walk
  entry, plus whatever the OQ resolves to.
- **D-10:** `expires_at` is **stamped once at write and never rewritten**. Shortening a workspace's
  window applies only to bodies written after the change; existing rows keep the expiry they were
  given. This is A-106 read literally ("the deletion job is an index scan on one column rather than
  a join against a settings table that may have changed since") and it needs no grant change —
  `call_body` holds `SELECT, INSERT, DELETE` and deliberately **no `UPDATE`**
  (`alembic/versions/0003_ledger_tables.py:251`, "bodies are written once and deleted"). The
  consequence to state in the plan: a workspace tightening its policy waits up to the old window,
  and `oldest_body_age_seconds` reads above the new window meanwhile. Neither a backfilling `UPDATE`
  (which would need the withheld grant) nor a delete-on-shorten side effect is built.
  — **Reversibility:** costly — reversing it means widening `prope_app`'s grant on the largest table
  in the system, which Phase 1 withheld on stated reasoning.
- **D-11:** **The drain reads the setting; `write_records` does not.** The drain's batch is already
  grouped per workspace, so it reads one indexed row per group and passes `retention_window` in.
  `write_records` stays a pure function of its arguments, and Phase 3's direct-write fallback — the
  path that runs when the broker is already down — inherits no settings query. The 30-day constant
  remains the default when no row exists; call-ledger has no workspace lifecycle to hook and may not
  read one, so **absence of a row is the default, not an error**. That two callers must both
  remember to read it is answered by a test, not by discipline.
- **D-12:** **The retention job's scheduler lands in this phase**, inside `worker`. `worker` is born
  here and `deployment_target` names both the drain and the retention job as its residents.
  Otherwise the invocation is owned by no phase at all: CL-08 was ticked in Phase 1 on the explicit
  reading that no scheduler ships (OQ-C), and Phase 3's requirements are CL-01, CL-02, CL-07, CL-10
  and CL-12 — none of them is the scheduler. **The plan must state out loud that this is work beyond
  this phase's two named requirements.**

### The two processes

- **D-13:** **Explicit central composition.** `src/prope/app.py` imports call-ledger's router and
  includes it; `src/prope/worker.py` imports the drain and the retention job and runs them. Adding a
  module means editing two files by hand. Neither `register()` hooks over a declared module list nor
  auto-discovery by filename convention is used: AC-10 and prompt-registry's route-uniqueness rule
  both assert properties of the *assembled* route table, and a route that can appear because a file
  was named a certain way is the shape those tests exist to refuse. `Makefile run` already targets
  `prope.app:app` and starts working when this lands.
  — **Reversibility:** costly — the shape is inherited by seven more modules' routers and three more
  worker jobs.
- **D-14:** **An `asyncio.TaskGroup` supervisor runs the worker's jobs.** One event loop, one
  process; the supervisor starts each job as a task, restarts a crashed one with backoff, and drains
  cleanly on `SIGTERM`. Timer jobs are plain interval loops. No scheduler library is added — two
  interval jobs do not pay for APScheduler's misfire semantics, and A-012's surviving
  *debuggable by one person* clause is the standing test. Separate per-job container commands are
  rejected: ADR-0033 fixes the runtime at 7 services and 2 images, and that shape grows the service
  count for every job any module adds. Accepted cost, stated rather than hidden: restart, backoff
  and graceful shutdown become code this project writes and tests. The supervisor must accommodate
  evaluation's claim loop (ADR-0049, Phase 16) and release-control's overdue sweep (ADR-0051,
  Phase 22) without being redesigned.
  — **Reversibility:** costly — four jobs across three later modules are written against it.
- **D-15:** The drain forms a batch on a **size-or-time window**: accumulate up to N messages or T
  milliseconds, group by `workspace_id`, one `workspace_transaction` per group, ack the whole window
  **after commit**. Prefetch is set to the window size so the broker never hands over more than one
  window of unacknowledged work. **N and T are open** — the plan must justify them against the
  ≥500 records/sec drain target and the p95 < 2 s enqueue-to-durable lag, not pick round numbers.
  One-message-per-transaction is rejected because it makes ADR-0040's grouping a no-op and turns
  ≥500/sec into a per-record round-trip budget; a greedy full-queue drain is rejected because an
  unbounded window turns a post-outage backlog into one enormous transaction against the largest
  table in the system — the exact shape A-132 forbade for the retention job.
- **D-16:** `/readyz` on `app` **ships its final semantics now**: the database alone. A broker
  outage is a separate counted-degraded signal, never un-readiness. Nothing is written twice and
  Phase 3 does not have to delete a readiness rule it inherited. **The plan must name the resulting
  Phase 2 gap explicitly**: for one phase there is a window where the broker is down, readiness is
  green, and records genuinely are lost — CL-01 is what closes it.
- **D-17:** `worker` exposes **no HTTP endpoint**, including no `/healthz` or `/readyz`; its compose
  healthcheck is process-level. **Derived from ADR-0028** ("`worker` consumes and never serves
  HTTP"), not chosen by the user during discussion — recorded here so a planner does not read it as
  a settled preference. INT-030's "every module with a process" reads against the *module*'s
  process, which for call-ledger is `app`. If a planner disagrees, this is an OQ, not a quiet
  reversal.

### The seams

- **D-18:** **`enqueue` and `price_usage` are two named functions**, both over the one
  `write_records`. The lock file's `apis.exposes` lists three internal seams and omits
  `price_usage`; `interfaces.md` INT-019 registers it, and the lock's own `inputs` block cites
  INT-019 as evaluation's contract. The lock's `apis.exposes` is treated as an **omission**, because
  the two failure contracts are opposite and one function cannot hold both: `enqueue` **never raises
  into the caller, ever** (INT-018 — the gateway's p95 depends on it), while `price_usage` **raises,
  and evaluation records a run error** (INT-019). Raise an `OQ-NNN` naming
  `docs/modules/call-ledger.lock.yml` `apis.exposes`.
  — **Reversibility:** one-way — INT-019 is a registered contract that evaluation builds against in
  Phase 17.
- **D-19:** **call-ledger's seams open their own transactions.** `price_usage` opens its own
  `workspace_transaction` and either commits or raises; it does not take evaluation's session. The
  property-history pattern (ADR-0023, write inside the caller's transaction) is deliberately not
  copied here: INT-019 requires that a raise leaves evaluation able to record a run error, which it
  could not do inside a transaction that just rolled back — and call-ledger is a sink whose design
  forbids reaching into a module that is doing work. Accepted cost: an eval run's state change and
  its usage write are two transactions, and a crash between them is possible. The upsert on
  `call_id` (Phase 3) is what makes the retry safe.
- **D-20:** **`get_run_totals` takes the workspace: `get_run_totals(workspace_id, run_id)`.** INT-021
  registers a one-argument signature, but with D-19's own-transaction shape RLS needs a tenant set
  before any read, and a `run_id` alone cannot supply one — the lookup that would resolve it returns
  zero rows without the context first. The caller passes the workspace it already holds, which is
  the same posture as `check_spend_ceiling` and the same rule access-control lives by ("callers
  supply the subject"). A fifth `SECURITY DEFINER` resolver is refused: exactly four are sanctioned
  and a test asserts the set is those four. **Rides the same OQ as D-18** — it is a second deviation
  from a registered interface signature.
  — **Reversibility:** one-way — a registered contract evaluation builds against in Phase 17.
- **D-21:** On a failed or nacked publisher confirm in Phase 2, `enqueue` **counts and drops**:
  `publish_failed_total` increments, a log line is written **with no body in it** (A-046), and
  nothing raises. The direct-write fallback is **not** pulled forward from Phase 3. **The plan must
  state plainly that this leaves a known-lossy window for one phase and that CL-01 closes it** —
  Phase 3 then both builds the fallback and proves it, rather than verifying a claim it did not
  build.

### The broker

- **D-22:** **A real RabbitMQ testcontainer joins the Postgres one**, session-scoped. It is the only
  way to observe the three things this phase actually claims — a publisher confirm arriving,
  redelivery behaviour on an unacknowledged consumer restart, and the queue holding the arguments
  that were declared. This extends D-02's reasoning rather than reopening it. A fake at the aio-pika
  seam is rejected because those three properties are exactly what a fake cannot prove; a fast-fake
  default with a skippable real-broker smoke test is rejected as the two-provisioning-paths split
  D-02 refused by name.
  — **Reversibility:** costly — the fixture shape is inherited by every later phase that touches the
  broker.
- **D-23:** **The queue is declared with A-149's full arguments in this phase, and a test reads them
  back from the broker and asserts them.** `prope.call_record`: 24 h message TTL, 1,000,000
  max-length. `prope.call_record.dlq`: 30-day TTL, 100,000 max-length. Overflow **dead-letters**
  rather than drops. The declaration is unavoidably this phase's work — RabbitMQ refuses to
  redeclare a queue with different arguments, so adding them in Phase 3 would mean deleting and
  redeclaring the queue in every environment that has run, with whatever is sitting in it. Asserting
  what was declared, in the same phase, costs about twenty lines; leaving the arguments correct by
  intention rather than by assertion is the exact posture T-006 was written about. T-005's full
  security sweep (including the `dlq_depth` gauge and its alert rule) still lands in Phase 3.
  — **Reversibility:** one-way in any environment that has run — see above.
- **D-24:** **Both processes declare, from one shared definition.** A single declaration module in
  `call_ledger` holds the queue, the DLQ, the arguments and the bindings; `app` declares on publisher
  startup and `worker` declares on consumer startup, calling the same code. Idempotent and
  order-independent, and a mismatch between the two is structurally impossible because there is one
  definition. A worker-declares-only shape is rejected because it turns deploy ordering into a
  data-loss question on the one path that must never raise; a separate deploy-time init command is
  rejected because the testcontainer rig would have to run it too — a second provisioning path.
- **D-25:** **`enqueue` hands off; a background task publishes and awaits the confirm.** The caller's
  span is a bounded in-process handoff, comfortably inside the p95 < 1 ms measured in the caller's
  process; the background task publishes, awaits confirms, and counts failures — and in Phase 3 does
  the direct write at that same failure site. This is what A-139 already assumes when it records the
  loss window as "the enqueue span, p95 < 1 ms". Awaiting the confirm inline is rejected: it puts a
  broker network round-trip inside a 1 ms budget, achievable on a healthy loopback broker and not
  achievable on a struggling one — precisely when it matters. Accepted and to be stated: this is a
  bounded in-process buffer with its own full-buffer behaviour, and a hard kill loses what is in it,
  which A-139 already accepts and records. **This is not the spill file** — ADR-0041 deleted a
  durable on-disk store and its replay, not an in-process handoff.
  — **Reversibility:** costly — Phase 3's fallback is placed at this task's failure site.

### Claude's Discretion

The user was asked and chose to leave these to the researcher and planner. They are **open, not
decided** — resolve them from the lock file, the interfaces registry and the phase's success
criteria, and state the resolution in the plan:

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

These are authoritative and read-only. Per `.planning/BSP-LINK.md`: do not edit anything under
`docs/`. A spec that disagrees with the code is information — raise an `OQ-NNN` naming the exact
lock-file or interfaces field and the conflict; do not patch the spec to agree. **Three such
conflicts are already known and are D-09, D-18 and D-20 above.**

### The module spec and the seam registry — read first
- `docs/modules/call-ledger.lock.yml` — `apis.exposes` (the three internal seams **and the
  `price_usage` omission**, the six routes, the amended `/readyz` clause), `events.subscribes`
  (queue `prope.call_record`), `inputs` (gateway and evaluation), `data.owns` (**five tables — see
  D-09**), `performance_requirements`, `acceptance_criteria` AC-6, AC-9, `test_plan`, `risks`
- `docs/architecture/interfaces.md` — **INT-018** (`prope.call_record`: at-least-once, publisher
  confirms, the failure table, the DLQ, A-139's honest loss window), **INT-019** (`price_usage`,
  in-process not the broker, both sides in `worker`), **INT-020** (`check_spend_ceiling`, the one
  seam in Prope that fails open), **INT-021** (`get_run_totals`, the two counts as part of the
  answer), **INT-028** (the management API, append-only prices, no body read path), **INT-030**
  (readiness differs per module)
- `.planning/BSP-LINK.md` — the phase → spec index and the "Out of bounds" rules

### The broker and the two processes
- `docs/adr/0028-rabbitmq-carries-the-asynchronous-work.md` — RabbitMQ 4.x; `app` publishes and
  never consumes, `worker` consumes and never serves HTTP, both from one image; durable queues,
  persistent messages, publisher confirms; DLQs from the start; every consumer idempotent
- `docs/adr/0041-broker-first-with-a-direct-write-fallback.md` — what the fallback is, and that the
  spill file, its replay, its readiness clause and three metrics are **deleted**
- `docs/adr/0040-the-ledger-writer-batches-per-workspace.md` — the drain groups by `workspace_id`,
  one transaction per group; `call_body` carries `workspace_id`
- `docs/adr/0033-one-vm-docker-compose-and-caddy.md` — 7 services, 2 images; the constraint D-14's
  rejection of per-job containers rests on
- `docs/adr/0049-the-eval-executor-claims-run-rows-rather-than-consuming-messages.md` — the second job
  the D-14 supervisor must accommodate (Phase 16)
- `docs/adr/0051-the-cross-tenant-sweep-enumerates-workspaces.md` — release-control's timer sweep,
  the third such job (Phase 22)

### Pricing, the ceiling, and retention
- `docs/adr/0019-cost-is-priced-once-at-write-time.md` — priced at the call's own `created_at`;
  missing price = `unpriced`, missing usage = `unknown`, **never zero**; no cache, by decision
- `docs/adr/0018-body-store-has-no-read-path-in-the-mvp.md` — why this module exposes nothing needing
  a permission check, and why the routes have no INT-001 call
- `docs/adr/0039-call-bodies-are-excluded-from-the-backup.md` — the argument D-23 reruns in the
  transport channel: a body's lifecycle is a property of every place it can rest

### Tenancy and the enforcement pattern
- `docs/adr/0035-tenant-isolation-is-a-database-policy.md` — RLS deny-by-default,
  `SET LOCAL app.workspace_id` per transaction; why D-20 needs a workspace argument
- `docs/adr/0045-every-table-is-tenant-scoped-unless-declared-global.md` — the coverage walk that
  picks up `ledger.workspace_retention` for free
- `docs/adr/0053-the-ui-ships-one-locale-behind-an-i18n-layer.md` — the machine `code` the client
  translates; bears on `check_spend_ceiling`'s `reason`

### Known gaps this phase must plan around
- `.planning/research/PITFALLS.md` §2 — call-ledger **AC-1 and AC-2 are stated against an in-process
  queue and a spill file, neither of which exists.** Both land in **Phase 3**; do not plan against
  the lock file's literal AC-1/AC-2 text anywhere
- `.planning/research/PITFALLS.md` §5 — the cross-module route-table assertions (AC-10 among them)
  **cannot run before Phase 23**, when every module is mounted. D-13's explicit composition is what
  keeps that test writable when it arrives
- `.planning/phases/01-data-model-pricing-and-retention/01-CONTEXT.md` — D-01 through D-08, and the
  Claude's-Discretion list Phase 1 left open
- `.planning/phases/01-data-model-pricing-and-retention/deferred-items.md` — the `scripts/` lint
  exclusions, unrelated to this phase but recorded

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/prope/call_ledger/writer.py` — **`write_records(session, records, *, retention_window)`.** Its
  own docstring states it is what the drain calls once per workspace group and what Phase 3's
  fallback calls with a single record; there is one implementation on purpose. It refuses a batch
  spanning two workspaces or two currencies, refuses an `eval` record carrying a body (A-055), and
  maintains `workspace_spend` in the same transaction (A-103). **`enqueue` and `price_usage` both
  land here** — neither writes SQL of its own.
- `src/prope/db/session.py` — **`workspace_transaction(sessionmaker, workspace_id)`.** The only place
  a tenant identifier reaches SQL. Bound via `set_config`, never interpolated (a source gate asserts
  it), transaction opened first, workspace a constructor argument with no setter. Its module note
  already anticipates this phase: *"a value which, from phase 2 onward, arrives inside a broker
  payload."*
- `src/prope/call_ledger/retention.py` — the bounded-chunk body delete, shipped in Phase 1 with its
  integration test and **no scheduler**. D-12 supplies the scheduler.
- `src/prope/call_ledger/pricing.py`, `repricing.py`, `domain.py`, `models.py` — effective-dated
  price resolution, exact-decimal cost, the three cost states, and the five tables as Core objects.
- `src/prope/call_ledger/writer.py:UNPRICED_WORKLIST` — the `GET /api/v1/prices/unpriced` query
  already exists, served by `ix_call_record_unpriced_worklist`. Phase 1 wrote the query and said in
  a comment that **Phase 2 owes the route**. It does.
- `tests/conftest.py` and the four test packages — the session-scoped Postgres testcontainer rig,
  Alembic run as `prope_migrate`, a `prope_app` connection handed to tests, truncate-between-tests
  isolation (**not** an outer rollback — that would turn `session.begin()` into a savepoint and leak
  tenant context between tests). D-22's broker container joins this rig.
- `pyproject.toml` — FastAPI, uvicorn, pydantic v2, pydantic-settings, structlog, prometheus-client
  and python-ulid are **already pinned and unused**, with a comment saying no route is built until
  phase 2. **`aio-pika` is the one dependency this phase must add.**
- `Makefile` — `run` already targets `prope.app:app` with a comment saying the module arrives in
  phase 2. `lint` scopes to `src/ tests/ alembic/`. There is no `typecheck` target and mypy is
  deliberately absent.

### Established Patterns

- **Build database-first.** The migration carries the guarantee — constraint, privilege, policy,
  grant, trigger — and the application code is what the guarantee protects. `ledger.workspace_retention`
  follows this: policy and grants in the migration, not in a service.
- **Assert against the live engine, not the driver.** D-07's REVOKE test, D-08's zero-rows test and
  D-06's coverage walk all do this. D-22 extends it to the broker.
- **Alembic is one linear hand-written chain** (D-04); autogenerate output is never trusted, because
  it cannot see RLS policies, grants or triggers. Migrations `0001`–`0003` exist; this phase adds
  `0004`.
- **Never zero, and no fourth state.** `write_records` has no default branch and raises rather than
  inventing a figure. New code inherits this: a refusal names what is missing rather than
  substituting a value.
- **The alert measures the data, not the job** (`oldest_body_age_seconds`, not job success). D-12's
  scheduler must not be verified by "the job ran".
- Module docstrings carry the *why* at length — the reasoning that would otherwise be lost is in the
  file, not only in the ADR. Match that density.

### Integration Points

- **`ledger.workspace_retention` is the first table added since Phase 1's five**, and the first test
  of D-06's coverage walk noticing a new table without being told to.
- **`prope.app` and `prope.worker` are created here and never again.** Seven more modules mount
  routers into the first; three more jobs join the second. `EXPECTED_ABSENT_SCHEMAS` in
  `tests/architecture/test_tenant_coverage.py` is untouched by this phase — Phase 7 is still the
  first that must shrink it.
- **No inbound or outbound module edges, still.** `dependencies: []` and `outputs: []` hold. The
  gateway and evaluation are the callers these seams are built for and neither exists yet; the
  contracts are proven from call-ledger's own tests.
- **`workspace_id` remains a value, not a foreign key.** The `access` schema does not exist until
  Phase 7 and call-ledger may not reference it even then.
- **Standing environment fact:** `docker` is not on the default bash PATH — shells driving it must
  first `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`. testcontainers reaches
  the daemon without PATH help. D-22 adds a second container to that daemon.

</code_context>

<specifics>
## Specific Ideas

- **The two failure contracts are opposite, and that is the whole argument for two seams.** `enqueue`
  never raises, ever, because the gateway's p95 depends on it; `price_usage` raises, because
  evaluation must be able to record a run error. A single function with a `source` flag would have to
  pick one and quietly break the other caller. This is the reason D-18 treats `apis.exposes` as an
  omission rather than as the authority.
- **Declare it right the first time, because RabbitMQ will not let you change your mind.** A queue
  cannot be redeclared with different arguments. D-23's TTLs and max-lengths are therefore not a
  Phase 3 nicety — they are a one-way decision that Phase 2 makes whether it thinks about it or not.
- **Assert what you declare, in the phase you declare it.** T-006 exists because `price_table` was
  declared append-only with nothing enforcing it. A queue declared with A-149's arguments and no test
  reading them back is the same defect in a different medium.
- **Name the gaps rather than closing them early.** D-16 and D-21 both leave a real, one-phase window
  where a broker outage loses records. Writing that down is what makes Phase 3's CL-01 a claim
  someone builds and proves, instead of one it inherits and merely verifies.
- **`worker` is born here, so what runs in it is decided here.** D-14's supervisor is not a
  call-ledger concern — it is the thing evaluation's claim loop and release-control's sweep will be
  written against, and getting it wrong is discovered in Phase 16 and Phase 22.
- **The retention setting must actually do something.** A `PUT` that persists a window the writer
  never reads would be a route that lies for a phase; D-11 is why the read lands with the write.

</specifics>

<deferred>
## Deferred Ideas

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

</deferred>

---

*Phase: 2-seams-enqueue-the-broker-drain-and-the-ceiling*
*Context gathered: 2026-08-10*
