---
phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
plan: 03
subsystem: infra
tags: [asyncio, taskgroup, supervisor, worker, rabbitmq, aio-pika, retention, rls, scheduling, structlog]

# Dependency graph
requires:
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 01
    provides: "run_drain with its keyword-only retention_for resolver, declare_topology, build_connection, the four counters and configure_logging, and the D-22 RabbitMQ testcontainer rig"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 02
    provides: "ledger.workspace_retention (migration 0004), read_retention_window / set_retention_window, and delete_expired_bodies' argument guards"
  - phase: 01-data-model-pricing-and-retention
    provides: "delete_expired_bodies and its bounded-chunk loop, write_records, workspace_transaction, DEFAULT_RETENTION_WINDOW, Settings/build_engine/build_sessionmaker"
provides:
  - "prope.supervisor — D-14's asyncio.TaskGroup supervisor: supervise, run_with_restart, interval_job, install_stop_handlers, and the two backoff constants. The contract Phases 16 and 22 are written against"
  - "prope.worker — D-13's explicit central composition: run_worker, main, and the two named jobs call-ledger.lock.yml's deployment_target lists"
  - "prope.worker.build_retention_resolver — where D-11 becomes true in the running system; the functools.partial that closes drain.py's one-argument / retention_settings' two-argument mismatch"
  - "prope.worker.sweep_expired_bodies — D-12's scheduler body, one bounded-chunk pass per enumerated workspace"
  - "prope.worker.ObservedWorkspaces + WorkspaceEnumerator — the named seam ADR-0051's access.list_workspaces() fills in Phase 7"
  - "Settings.retention_chunk_size (PROPE_RETENTION_CHUNK_SIZE) — the operator override plan 02-02's WARN-1 guard exists for"
affects: [02-04-seams-and-ceiling, 02-05-management-routes, 03-fallback-and-upsert, 07-access-control, 16-18-evaluation, 22-release-control]

actuals:
  tokens: 17227
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "A job is a name plus a zero-argument coroutine factory, and the supervisor knows nothing else about it"
    - "Every wait in a supervised process goes through an interruptible sleep, never a bare asyncio.sleep"
    - "An observation seam (on_backoff) for a property that is unobservable once the call has returned — third use, after on_chunk and on_window"
    - "A cross-process arity mismatch closed at the composition root with functools.partial, argued at the binding rather than styled"
    - "A capability that does not exist yet is a NAMED PARAMETER with a documented stand-in, so the later phase replaces an argument rather than editing a job"
    - "Assert BOTH halves of a known gap, so the boundary is fixed in place and a test fails when somebody moves it"

key-files:
  created:
    - src/prope/supervisor.py
    - src/prope/worker.py
    - tests/unit/test_supervisor.py
    - tests/integration/test_worker_jobs.py
  modified:
    - src/prope/db/engine.py
    - .planning/phases/02-seams-enqueue-the-broker-drain-and-the-ceiling/deferred-items.md

key-decisions:
  - "The retention job's scheduler ships in this phase and is work beyond BOTH named requirements (CL-06 and CL-09), stated out loud as D-12 requires — it is here because otherwise it is owned by no phase at all"
  - "RETENTION_SWEEP_INTERVAL_SECONDS = 300 — the interval cannot BE the ten-minute deadline, because worst observed age is interval + run_time; five minutes splits the budget and leaves 3 s per chunk against the stated 500,000-row / 100-chunk worst case"
  - "The retention sweep's workspace enumerator is prope.worker.ObservedWorkspaces, a documented Phase 2 stand-in — a SELECT DISTINCT workspace_id would return ZERO ROWS under ADR-0045's deny-by-default policy, and building the sweep on it would produce exactly the runs-cleanly-deletes-nothing lie the plan prohibits"
  - "The drain job opens its own channel per run, so a crash-restart gets a clean one and the queue's consumer count returns to zero when the worker stops"
  - "A workspace that raises during a sweep pass takes the pass down rather than being caught and skipped — the supervisor restarts the job and the next pass retries every workspace with a fresh cut-off"
  - "The clean-return restart path carries one asyncio.sleep(0), because a job that returns without suspending would starve the loop and the stop event could then never be set by anyone"
  - "install_stop_handlers is guarded by sys.platform AND catches NotImplementedError — the guard is a claim about a platform, the exception is the platform's own answer"
  - "Settings.retention_chunk_size is deliberately unvalidated at the settings object; delete_expired_bodies' WARN-1 guard is where every caller meets it, and a second check would be a second place for the two to disagree"

patterns-established:
  - "A supervised job is a coroutine FACTORY, never a coroutine — a coroutine object can be awaited once, so a supervisor taking one could never restart anything"
  - "A log field that is not yet on LOGGABLE_FIELDS is recorded in deferred-items with the reason it qualifies, rather than added to a file another plan in the same wave owns"
  - "A test that asserts the ABSENCE of a capability names the condition under which it should be deleted"

requirements-completed: [CL-06]

coverage:
  - id: D1
    description: "worker runs the drain and the retention job in one process on one event loop, and a crash in either restarts that job alone without taking the other down"
    requirement: CL-06
    verification:
      - kind: unit
        ref: "tests/unit/test_supervisor.py::test_a_crashing_job_does_not_stop_its_sibling"
        status: pass
      - kind: unit
        ref: "tests/unit/test_supervisor.py::test_a_crash_backs_off_exponentially_and_stops_doubling_at_the_cap"
        status: pass
      - kind: unit
        ref: "tests/unit/test_supervisor.py::test_a_clean_return_restarts_the_job_and_resets_the_backoff"
        status: pass
    human_judgment: false
  - id: D2
    description: "worker exposes no HTTP endpoint of any kind, including no /healthz and no /readyz"
    verification:
      - kind: unit
        ref: "tests/integration/test_worker_jobs.py::test_worker_imports_no_web_framework"
        status: pass
      - kind: unit
        ref: "tests/integration/test_worker_jobs.py::test_worker_exposes_no_asgi_application_object"
        status: pass
    human_judgment: false
  - id: D3
    description: "worker starts exactly one drain consumer, so the prefetch bound and the one-currency invariant both hold as stated"
    verification:
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_the_running_worker_holds_exactly_one_consumer_on_the_queue"
        status: pass
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_the_consumer_is_gone_after_the_worker_stops"
        status: pass
    human_judgment: false
  - id: D4
    description: "The drain running inside worker resolves each workspace group's retention window from ledger.workspace_retention through a resolver bound to a sessionmaker; invoking that bound object with a workspace_id alone returns that workspace's window"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_the_resolver_worker_builds_takes_the_workspace_id_alone"
        status: pass
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_the_resolver_is_built_by_binding_the_sessionmaker"
        status: pass
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_two_workspaces_get_two_different_expiries_through_the_composed_worker"
        status: pass
    human_judgment: false
  - id: D5
    description: "A stop signal drains the current window to completion and commits it before the process exits, rather than abandoning unacknowledged work"
    verification:
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_a_stop_mid_window_commits_that_window_before_the_worker_returns"
        status: pass
      - kind: unit
        ref: "tests/unit/test_supervisor.py::test_the_stop_event_returns_every_job_and_leaves_nothing_pending"
        status: pass
      - kind: unit
        ref: "tests/unit/test_supervisor.py::test_the_stop_event_interrupts_a_backoff_sleep"
        status: pass
    human_judgment: false
  - id: D6
    description: "The retention job's health is judged by the age of the oldest surviving body, not by whether the job returned without raising"
    verification:
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_a_sweep_pass_removes_the_expired_bodies_of_every_enumerated_workspace"
        status: pass
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_the_composed_worker_sweeps_a_workspace_its_drain_has_seen"
        status: pass
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_a_workspace_the_enumerator_omits_keeps_its_expired_bodies"
        status: pass
    human_judgment: false
    rationale: "The plan marked this verification: backstop. It is confirmed by POSITIVE evidence: every assertion is a row count read through migrate_engine after the sweep, and no test reads the job's return value. The gauge itself (oldest_body_age_seconds) is Phase 3's; the data-shaped property it would measure is asserted here."
  - id: D7
    description: "Shipping the retention scheduler in this phase — work beyond CL-06 and CL-09 — and the retention-sweep interval and single-consumer constraint are the intended operational posture"
    verification: []
    human_judgment: true
    rationale: "The plan's own <human-check>. Whether five minutes is the right sweep interval and whether absorbing an unowned scheduler here is acceptable are judgements about operational posture, not properties a test can assert. The mechanical halves — the interval is a documented constant, exactly one consumer, and the scheduler exists at all — ARE asserted."

# Metrics
duration: 14min
completed: 2026-08-10
status: complete
---

# Phase 02 Plan 03: Seams — enqueue, the broker drain, and the ceiling Summary

**Prope has a second process. `worker` runs the broker drain and the expired-body deletion job on one
event loop under an `asyncio.TaskGroup` supervisor, resolves each workspace group's retention window
from `ledger.workspace_retention` through a `functools.partial`-bound resolver, holds exactly one
consumer on `prope.call_record` as the broker itself reports it, commits the window in flight before a
stop signal returns, and serves no HTTP of any kind.**

## Performance

- **Duration:** ~14 min
- **Tasks:** 2 (Task 1 executed test-first; Task 2 executed)
- **Files created/modified:** 6
- **Test suite:** **199 passed**, 0 failed (176 before this plan; +23)

## The retention job's scheduler is work beyond CL-06 and CL-09 — stated out loud

D-12 requires this to be said rather than absorbed, and this section is the saying.

**Neither of this phase's named requirements asks for a scheduler.** CL-06 is the spend ceiling
refusing eval runs while gateway traffic continues to be recorded normally; CL-09 is an eval-case usage
row priced and counted with no body stored. Neither mentions a timer, an interval, or a process that
runs one.

The scheduler is here because the alternative is that it is owned by **no phase at all**:

- Phase 1 ticked CL-08 on the explicit reading that no scheduler ships (OQ-C, recorded in
  `retention.py`'s docstring: *"The `worker` process that would host a timer arrives in Phase 2"*).
- Phase 3's requirements are CL-01, CL-02, CL-07, CL-10 and CL-12. None of them is a scheduler.
- `docs/modules/call-ledger.lock.yml`'s `deployment_target` names both the drain **and** the retention
  job as `worker`'s residents, and `worker` is born in this plan and never again.

So `delete_expired_bodies` — shipped complete in Phase 1 with its integration test and no invocation —
acquires one here. That is one interval constant, one enumeration seam, and one loop.

## The supervisor's shape, as the contract Phases 16 and 22 inherit

`src/prope/supervisor.py` is not a call-ledger concern even though call-ledger is its first caller.
**Four jobs across three modules will be written against it** — the drain and the retention sweep now,
evaluation's claim loop (ADR-0049, Phase 16) and release-control's reconciliation query and
overdue-gauge sweep (ADR-0051, Phase 22) later — and D-14 requires that it accommodate them **without
being redesigned**. So the contract is deliberately narrow:

> **A job is a name and a zero-argument coroutine factory. The supervisor knows nothing else about it.**
> It opens no connection, reads no setting, and imports no module. Everything a job needs is bound into
> it by the composition in `prope.worker` before it arrives.

Five properties are fixed by this plan and should be treated as inherited rather than re-litigated:

| Property | What it means for a Phase 16 / Phase 22 job |
|----------|---------------------------------------------|
| A job is a **factory**, not a coroutine | A coroutine object can be awaited once; a supervisor taking one could never restart anything |
| A crash restarts **that job alone**, with capped exponential backoff | The `TaskGroup`'s own default — first exception cancels every sibling — is neutralised by wrapping each job individually |
| `asyncio.CancelledError` is **re-raised untouched** | A job must not treat cancellation as a failure to recover from |
| Every wait is **interruptible by the stop event** | A job may take a long interval without making shutdown long |
| `stopping` is a plain `asyncio.Event` | Anything can drive the graceful path — a signal handler, a test, or a Windows entrypoint that has no signal handler available |

`RESTART_BACKOFF_BASE_SECONDS = 1.0` and `RESTART_BACKOFF_CAP_SECONDS = 60.0`, both with the reasoning
at the constant in `retention.py`'s tuning-constant voice.

**Both `TaskGroup` traps and the Windows constraint are stated at the code**, and that is asserted
mechanically rather than left as a reading task: `test_the_module_names_both_taskgroup_traps_and_the_windows_constraint`
fails if `ExceptionGroup` or `add_signal_handler` stops appearing in the module docstring.

### The third trap, found while building

The plan named two `TaskGroup` traps. A third turned up in the restart loop and is now documented at the
code: **a job that returns without ever suspending starves the event loop.** `while not stopping.is_set(): await job()` where `job` never awaits anything is a tight loop that never yields, so nothing else
— including whatever would set the stop event — ever runs, and the process hangs rather than restarting
anything. One `await asyncio.sleep(0)` on the clean-return path makes such a job merely wasteful instead
of fatal. Recorded because it is exactly the class of thing a Phase 16 author would otherwise rediscover.

## D-11 becomes true in the running system, in one function

`build_retention_resolver` is the whole of it, and the mismatch it closes is the one plan 02-01 wrote
down at the parameter and plan 02-02 wrote down at the function:

- `drain.py` declares `retention_for: Callable[[str], Awaitable[timedelta]]` and calls it
  `await retention_for(workspace_id)` — **one** positional argument.
- `read_retention_window(sessionmaker, workspace_id)` takes **two**.

Passing the bare function is not a type error any annotation catches at import time. It is a
`TypeError` raised on the **first workspace group**, inside the consumer, on the path whose whole purpose
is not losing records. The `functools.partial(read_retention_window, sessionmaker)` at the composition
root is what prevents it, and the reasoning is written at the binding so the `partial` reads as
load-bearing rather than as a style choice.

**D-11's own stated risk is that "two callers must both remember to read it", and the answer is a test
rather than discipline.** Three of them:

- `test_the_resolver_worker_builds_takes_the_workspace_id_alone` invokes the object `worker.py` builds
  with a single positional `workspace_id` and asserts it returns that workspace's stored window — so a
  regression to the unbound form fails there rather than at runtime. It also asserts the negative:
  calling `read_retention_window(WORKSPACE_A)` raises `TypeError`.
- `test_the_resolver_is_built_by_binding_the_sessionmaker` asserts the returned object *is* a
  `functools.partial` whose `.func` is the real reader and whose `.args` is the sessionmaker — so a
  look-alike wrapper that happened to work cannot pass for the binding.
- `test_two_workspaces_get_two_different_expiries_through_the_composed_worker` proves it end to end: a
  workspace holding a stored 7-day window gets its body stamped at `created_at + 7 days` and a workspace
  with no row at `+ 30 days`, both read through `migrate_engine`.

## Exactly one consumer, asserted against the broker

`prefetch_count` is applied by RabbitMQ **per consumer**, not per channel, so `drain.WINDOW_SIZE`'s
"never more than one window of unacknowledged work" bound — and the envelope carries request and
response bodies — holds only while there is exactly one. The lock file's throughput row assumes the same
thing in different words (*"batched inserts, bodies included, single writer"*), and plan 02-01's closing
note named this plan as the place the assertion had to land.

It lands as a **passive queue declare**, which answers from the queue's current state, rather than the
management HTTP API, whose statistics refresh on an interval and would have the test racing a scheduler.
The count is sampled three times a beat apart, so a second consumer appearing late does not slip past a
single sample, and a companion test asserts the count returns to **zero** after the worker stops — which
is what makes the drain job's own channel (opened per run, closed on exit) observable rather than merely
described.

Together with plan 02-02's `ON CONFLICT ... WHERE` one-currency invariant, that is **both** halves of
WARN-2 rather than neither (T-02-18), which is what Pitfall 7's "do not do neither" asked for.

## The stop path, and how it is made deterministic

The requirement is that a stop arriving mid-window commits that window rather than abandoning
unacknowledged work (T-02-19). Sleeping and hoping would make that test flaky, so it is arranged by
construction instead:

`ObservedWorkspaces.note()` is called by the retention resolver, which the drain awaits **after** it has
collected and grouped a window and **before** it opens the write transaction. A test subclass that sets
the stop event from `note()` is therefore setting it at the exact instant a window is in flight. The
assertion is then a row count through `migrate_engine` after `run_worker` returns.

This matters in Phase 2 more than it will later: a redelivered record hits the `call_id` unique violation
and dead-letters until CL-02 lands, so abandoning a window at shutdown would make *deploying* a cause of
dead-lettered records.

## The retention sweep interval, argued rather than picked

The lock file's target is *"one day's expired bodies removed within 10 min"* at *"up to 500,000 body rows
in a batch, deleted in bounded chunks"*.

**The interval cannot be the deadline.** A body expiring one second after a pass starts waits a full
interval before the next pass even begins, so the worst observed age of a surviving expired body is
`interval + run_time`. Ten minutes misses a ten-minute target by however long the run takes, every time.

**`RETENTION_SWEEP_INTERVAL_SECONDS = 300` splits the budget in half.** 300 s of the 600 s target goes to
waiting and 300 s is left for the run. Against the stated worst case — 500,000 rows at
`DEFAULT_CHUNK_SIZE = 5_000`, which is 100 chunks — that is 3 s per chunk before the target is missed,
and a chunk is one indexed `DELETE` over `(workspace_id, expires_at)` in its own short transaction.

It also changes the shape of the steady state: a normal pass clears five minutes of expiries, not a day's.
The 500,000-row batch becomes what a pass looks like **after an outage**, which is the only time A-132's
chunking is load-bearing at all.

`PROPE_RETENTION_CHUNK_SIZE` is the operator override, added as `Settings.retention_chunk_size`. It is
**deliberately not validated at the settings object** — `delete_expired_bodies`' WARN-1 guard (plan
02-02) is where every caller meets it, and a second check here would be a second place for the two to
disagree. The type refuses `"large"`; the function refuses `0`. This is the override path plan 02-02's
guard was landed ahead of, now real.

## The one thing the plan asked for that could not be built as written

**The plan's Task 2 says: *"The job enumerates the workspaces it must sweep from the ledger itself; it
may not read a workspace table."* The first half of that is not available in Phase 2, and building it as
literally written would have produced the exact lie the plan's own prohibition forbids.**

Under ADR-0045 the tenant policy is `workspace_id = current_setting('app.workspace_id', true)`. A
`prope_app` query issued with **no** workspace set matches nothing and returns **zero rows** — the policy
working exactly as designed. Every one of the six `ledger` tables carries that policy. So a
`SELECT DISTINCT workspace_id FROM ledger.call_body` in the sweep would return an empty list forever, and
the job built on it would run cleanly, delete nothing, and look healthy. That is precisely the failure the
plan prohibits by name: *"MUST NOT judge the retention job healthy because it returned without raising —
a job that runs cleanly and deletes nothing looks identical to a working one."*

ADR-0051 answers this for the general case with `access.list_workspaces()`, a `SECURITY DEFINER` function
returning identifiers and nothing else. **It does not exist yet.** The `access` schema arrives in Phase 7,
call-ledger is forbidden an outbound edge to it, and inventing a fifth privilege-escalating routine here
would break the test asserting the sanctioned set is exactly four. Phase 1 hit the identical wall and
recorded it as OQ-C, carrying it upstream rather than improvising.

**What was built instead**, and why it is a seam rather than a shortcut:

- `WorkspaceEnumerator = Callable[[], Awaitable[Sequence[str]]]` is a **named parameter** of
  `sweep_expired_bodies`, and `run_worker` takes the enumerator as an argument. **Phase 7 replaces an
  argument; it does not edit the job.** The stand-in's `current()` is a coroutine returning a sorted
  tuple precisely so that `access.list_workspaces()` — a round trip returning `SETOF text` — drops in
  without a rewrite.
- `ObservedWorkspaces` fills it today with the workspaces the drain has resolved a retention window for
  since this process started. **That is not a side channel.** D-11 already has the drain reading the
  window once per workspace group, so "workspaces this process has resolved a window for" *is*
  "workspaces this process has written records for", read from the place D-11 already put it.

**The gap, stated exactly.** A workspace that has sent no traffic since this process started is not
swept, so its already-expired bodies survive until it sends something. A workspace that stops sending
traffic permanently is never swept again. It is bounded, and it is measurable by the thing that should
measure it: Phase 3's `oldest_body_age_seconds` reads above the window for exactly those workspaces —
the alert measuring the data rather than the job.

**Both halves are asserted, because an exception that is only written down is a belief** (plan 02-02's
posture, second use). `test_a_sweep_pass_removes_the_expired_bodies_of_every_enumerated_workspace` proves
an enumerated workspace is swept; `test_a_workspace_the_enumerator_omits_keeps_its_expired_bodies` proves
an unenumerated one is not, and its failure message says the boundary has moved and the test is stale.
`test_the_composed_worker_sweeps_a_workspace_its_drain_has_seen` proves the composition closes the loop:
the drain notes a workspace, and the scheduled sweep clears its expired bodies while leaving the
unexpired ones — including the body the drain itself just wrote.

## Files Created/Modified

**Created**

- `src/prope/supervisor.py` — `supervise`, `run_with_restart`, `interval_job`, `install_stop_handlers`,
  `_sleep_or_stop`, `Job`, `BackoffObserver`, and the two backoff constants. The module docstring carries
  D-14's rejected alternatives (APScheduler under A-012, per-job containers under ADR-0033), all three
  traps, the accepted cost, and the forward constraint from ADR-0049 and ADR-0051.
- `src/prope/worker.py` — `run_worker`, `main`, `_amain`, `build_retention_resolver`,
  `sweep_expired_bodies`, `ObservedWorkspaces`, `WorkspaceEnumerator`, the two job-name constants and
  `RETENTION_SWEEP_INTERVAL_SECONDS`. Every resident is imported by name; there is no dynamic import, no
  module-list iteration and no filename convention.
- `tests/unit/test_supervisor.py` — 11 tests covering every line of the plan's `<behavior>` block.
- `tests/integration/test_worker_jobs.py` — 12 tests. Every data assertion goes through `migrate_engine`;
  every broker assertion goes through the broker.

**Modified**

- `src/prope/db/engine.py` — `retention_chunk_size: int | None = None` on the existing `Settings` class.
  Still exactly one `BaseSettings` subclass under `src/prope/`.
- `.planning/phases/02-…/deferred-items.md` — three entries (see below).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] The retention sweep's workspace enumeration as specified would have returned zero
rows forever**

- **Found during:** Task 2
- **Issue:** The plan's action text says the job *"enumerates the workspaces it must sweep from the
  ledger itself"*. Under ADR-0045's deny-by-default tenant policy, a `prope_app` query with no
  `app.workspace_id` set returns **zero rows** from every `ledger` table. The literal implementation
  would have produced a sweep that ran cleanly, deleted nothing and reported itself healthy — the exact
  outcome the plan's second prohibition forbids.
- **Fix:** The enumeration is a named parameter (`WorkspaceEnumerator`) with a documented Phase 2
  stand-in (`ObservedWorkspaces`) fed from the resolver call D-11 already makes per workspace group.
  Phase 7 supplies an `access.list_workspaces()`-backed enumerator as an argument.
- **Files modified:** `src/prope/worker.py`, `tests/integration/test_worker_jobs.py`,
  `.planning/phases/02-…/deferred-items.md`
- **Verification:** both halves of the resulting gap asserted; the sweep proven to delete through
  `migrate_engine`.
- **Committed in:** `ff2baa2`

**2. [Rule 2 — Missing critical functionality] The supervisor's clean-return path could starve the event
loop**

- **Found during:** Task 1
- **Issue:** `while not stopping.is_set(): await job()` with a job that returns without suspending never
  yields to the event loop, so nothing — including whatever would set the stop event — can run. The
  process hangs rather than restarting anything. Not in the plan's `<behavior>` block and not in
  RESEARCH's Pattern 4 sketch.
- **Fix:** one `await asyncio.sleep(0)` on the clean-return path, documented at the code as the third
  trap alongside the two the plan named.
- **Files modified:** `src/prope/supervisor.py`
- **Commit:** `c8f8caa`

**3. [Rule 3 — Blocking] `src/prope/db/engine.py` is not in this plan's `files_modified`**

- **Found during:** Task 2
- **Issue:** The plan's *Artifacts this phase produces* section names *"Possible new `Settings` field: a
  retention chunk-size override (env `PROPE_RETENTION_CHUNK_SIZE`)"*, and its action text makes the
  override path *"exactly why plan 02-02's argument guard landed first"*. The field has to live on the
  one `Settings` class, which is in `engine.py`.
- **Fix:** one optional field appended to the existing class, with its `#:` comment. Nothing else in the
  file touched; plan 02-01 had already extended the same class the same way. No plan in wave 2 or 3
  declares `engine.py`.
- **Files modified:** `src/prope/db/engine.py`
- **Commit:** `ff2baa2`

**4. [Rule 3 — Blocking] `deferred-items.md` already existed**

- **Found during:** Task 2
- **Issue:** Task 2 asks for the file to be *created* recording the root `Dockerfile` and
  `docker-compose.yml`. Plan 02-01 created it and already recorded both.
- **Fix:** extended rather than rewritten. The existing entry gains two specifics that only became
  visible once the second process existed (a single-`backend` compose file would give `worker` an HTTP
  healthcheck by inheritance, which is the surface D-17 refuses; `python:3.11-slim` cannot run code that
  pins 3.13), plus two new entries — the `LOGGABLE_FIELDS` `job` field and the enumerator stand-in.
- **Files modified:** `.planning/phases/02-…/deferred-items.md`
- **Commit:** `ff2baa2`

### Authentication Gates

None.

---

**Total deviations:** 4 auto-fixed (1 × Rule 1, 1 × Rule 2, 2 × Rule 3). No architectural change: no new
table, no new library, no new database routine, no new role, no forbidden edge.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest -q` (whole suite) | **199 passed** (176 before this plan) |
| `uv run pytest tests/unit/test_supervisor.py -q` | 11 passed |
| `uv run pytest tests/integration/test_worker_jobs.py -q` | 12 passed |
| `uv run ruff check src/ tests/ alembic/` | clean |
| `uv run python -c "import prope.worker, fastapi, starlette"` + no-ASGI-attribute assertion | exit 0 |
| `src/prope/worker.py` — every resident imported by name, no dynamic import | confirmed by reading |
| `src/prope/supervisor.py` — both traps and the Windows constraint at the code | asserted by test, not only read |
| `uv run ruff format --check src/ tests/ alembic/` | **known-failing, pre-existing** — see below |

**On `ruff format --check`.** It now reports 34 files would be reformatted, 27 already formatted (31/26
at plan 02-02). The cause is unchanged and systemic: `ruff.toml` sets `line-length = 120` while the whole
repo is hand-wrapped to roughly 100, so every hunk is the formatter joining a wrapped call back onto one
line. `uv run ruff check` — the linter, which is what CI would gate on today — is clean and stays clean;
`E501` is explicitly ignored. This plan's three new files are written in the house ~100 style so they read
like their neighbours, which is why the count moved by three. Satisfying this line requires the repo-wide
line-length decision recorded in `deferred-items.md`, and it is not this plan's to make.

## Human Verification Required

The plan's `<verification>` block carries one `<human-check>`, restated because it is a posture rather
than a test:

> Confirm the retention-sweep interval and the drain's single-consumer constraint are the intended
> operational posture, and that shipping the retention scheduler in this phase — work beyond CL-06 and
> CL-09 — is accepted rather than absorbed silently.

Three specific things to accept or reject:

1. **Five minutes** as the sweep interval, on the arithmetic above.
2. **Exactly one drain consumer**, which is a throughput ceiling as well as a correctness property:
   scaling the drain horizontally is not available until CL-02's upsert and a per-consumer prefetch
   review land.
3. **The scheduler shipping here at all** — work beyond both named requirements, absorbed on D-12's
   reasoning that no other phase owns it.

A fourth thing is worth an explicit decision even though the plan did not ask for it: **the enumerator
stand-in and its gap** (see above). Its replacement point is a parameter, so closing it in Phase 7 is an
argument change; leaving it means cold workspaces are not swept until Phase 7.

## Flagged Assumption Carried to Verification

**CL-06 — `unclassified` / `unresolved`.** The deterministic edge probe proposed no edge predicates for
this requirement. This plan addresses the clause *"its gateway traffic continues to be recorded
normally"* at the **process** level: the drain is actually invoked, by something, in a process that
survives a crash in its sibling. The boundary conditions the clause genuinely has — a stop mid-window, a
crashing sibling, a workspace with no retention row — are covered by this plan's derived truths and by
the tests above, not by probe output. **The assumption to confirm at verification is that the absence of
probe-derived edges for CL-06 reflects a classification miss, not an edge-free requirement.**

Also carried forward from plan 02-01: CL-06 is marked complete, and `check_spend_ceiling` — the *refusal*
half of the clause — is plan **02-04**'s. This plan built the recorded-normally half at the process
level.

## Known Stubs

**One, and it is documented as a seam with a named replacement point rather than hidden:**
`prope.worker.ObservedWorkspaces` is a Phase 2 stand-in for ADR-0051's `access.list_workspaces()`. It is
not a placeholder that returns empty or raises `NotImplementedError` — it is a working enumerator with a
stated, asserted, bounded gap (cold workspaces are not swept), a documented reason it cannot be better in
Phase 2 (the `access` schema does not exist and a fifth `SECURITY DEFINER` routine is refused), and a
parameter-shaped replacement point. Recorded here, in `deferred-items.md`, and at the class.

Nothing else. `supervise`, `interval_job`, `install_stop_handlers`, `build_retention_resolver`,
`sweep_expired_bodies` and `run_worker` are all wired to a caller inside this plan or to a test that
drives them, and `main` is the process entrypoint a compose file will call.

## Threat Flags

None. Every security-relevant surface this plan touches was in the plan's `<threat_model>`, and each is
mitigated and asserted rather than intended:

| Threat | Where it is asserted |
|--------|----------------------|
| T-02-15 (an HTTP surface on `worker`) | `test_worker_imports_no_web_framework`, `test_worker_exposes_no_asgi_application_object` |
| T-02-16 (one crashing job taking the process down) | `test_a_crashing_job_does_not_stop_its_sibling` |
| T-02-17 (the retention delete against the largest table) | bounded chunks + plan 02-02's guard; the interval argued against the ten-minute target |
| T-02-18 (two drain consumers racing on `workspace_spend`) | `test_the_running_worker_holds_exactly_one_consumer_on_the_queue`, plus 02-02's `ON CONFLICT ... WHERE` |
| T-02-19 (work abandoned unacknowledged at shutdown) | `test_a_stop_mid_window_commits_that_window_before_the_worker_returns` |
| T-02-20 (`job_crashed` log lines) | the line carries the job name and the exception CLASS only — no message, no traceback, no argument value |

**No new network surface was created. `worker` opens no port.**

## Notes for the next plans

- **`LOGGABLE_FIELDS` should gain `"job"`.** `supervisor.job_crashed` carries `job` (a closed set of two
  names fixed in `worker.py`) and `reason` (already on the list). `src/prope/observability.py` belongs to
  **plan 02-04**, so this plan did not edit it; the reasoning is in `deferred-items.md`.
- **`configure_logging()` now has one production caller** — `prope.worker.main`. Plan 02-05's `app` is the
  second.
- **`prope.app` does not exist yet.** `Makefile run` still targets `prope.app:app` and starts working when
  plan 02-05 lands. `python -m prope.worker` works today.
- **D-24 is half-proved.** `worker` declares the topology at startup from the shared definition; plan
  02-05's `app` is the other caller, and "both declare from one definition" is only fully asserted once it
  exists.
- **The supervisor is the shape Phases 16 and 22 inherit.** A job is a name and a zero-argument coroutine
  factory. Anything else a job needs — a session factory, a broker channel, an enumerator — is bound into
  it by `prope.worker` at composition time.

## Self-Check: PASSED

- All four created files exist on disk; both modified files carry this plan's changes.
- All three commits are present in `git log`: `abadcec` (test), `c8f8caa` (feat), `ff2baa2` (feat).
- `src/prope/supervisor.py` contains `TaskGroup` and defines `supervise`, `interval_job` and
  `install_stop_handlers`; `tests/unit/test_supervisor.py` contains `CancelledError`.
- `src/prope/worker.py` contains `declare_topology` (3 occurrences) and exactly one
  `functools.partial(read_retention_window, sessionmaker)`.
- `.planning/phases/02-…/deferred-items.md` names both `Dockerfile` and `docker-compose.yml`.
- `uv run pytest -q` → **199 passed**. `uv run ruff check src/ tests/ alembic/` → clean.
- The commit introduced no file deletions (`git diff --diff-filter=D HEAD~1 HEAD` is empty).

---
*Phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling*
*Completed: 2026-08-10*
