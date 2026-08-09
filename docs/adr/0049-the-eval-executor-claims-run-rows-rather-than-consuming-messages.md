# ADR-0049 — The eval executor claims run rows rather than consuming messages

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: evaluation — rewrites A-054, restates A-063, confirms ADR-0046's dependency
**Related**: A-012, A-029, A-053, A-054, A-057, A-062, A-063, A-088, A-093, A-134, A-137, A-138,
ADR-0004, ADR-0016, ADR-0026, ADR-0028, ADR-0033, ADR-0035, ADR-0041, **ADR-0042**, ADR-0045, ADR-0046,
OQ-012, OQ-013

## Context

A-054 was written on 2026-08-08 and says eval runs execute *"asynchronously in-process at concurrency
5"*. Its rationale opens by quoting the premise it was built on: *"A-012 forbids a broker and a separate
worker fleet: one `docker-compose up` has to bring the whole system up for a team with no ops."*

**ADR-0028 removed that premise during Stage 1.** It introduced RabbitMQ and a `worker` service — the
same image, a different command — and A-054 has carried a rewrite flag ever since. ADR-0046 then built
on the outcome before it was decided, recording in writing: *"This depends on evaluation's pass landing
batch dispatch in `worker`. A-054's rewrite is where that is confirmed. If evaluation decides otherwise,
this ADR is re-opened with it."*

That is this pass. Two things had to be settled: **where the executor runs**, and — once it moved —
**what happens to A-063's concurrency bound**, which was written as a bound sitting *above*
provider-access's admission gate and, after the move, sits beside it in the same process.

The non-obvious part is that having bought a broker, the obvious use of it is wrong here.

## Decision

### 1. `worker` claims `queued` run rows; there is no broker message

`POST /eval-runs` validates, writes one `queued` row per suite, and returns 202 with one run id each,
inside its 200 ms budget. `worker` runs a claim loop on a **1 s** interval:

```sql
BEGIN;
SELECT * FROM evaluation.eval_run r
 WHERE r.status = 'queued'
   AND (SELECT count(*) FROM evaluation.eval_run r2
         WHERE r2.workspace_id = r.workspace_id
           AND r2.status = 'running') < :max_concurrent_runs
 ORDER BY r.created_at
   FOR UPDATE SKIP LOCKED
 LIMIT 1;
UPDATE evaluation.eval_run SET status = 'running', started_at = now() WHERE id = :id;
COMMIT;
-- the row lock is released here; the run then executes for up to 120 s
```

- **The admission decision and the state change are one transaction**, so two claim loops cannot start
  the same run and cannot both see the last free slot. `SKIP LOCKED` makes a contended claim skip to the
  next candidate rather than block.
- **The lock is not held for the run.** A 120 s transaction would pin a connection, hold a snapshot
  against autovacuum, and make every crash a lock-timeout question. Liveness is the sweeper's job, as it
  already was.
- **The claim query requires `eval_run.workspace_id`** — the column ADR-0045's coverage walk adds in this
  same pass. Without it the admission count joins back through `prompt_property` on every tick. The
  security rule and the scheduler arrived at the same column independently.
- **Evaluation publishes and subscribes to nothing.** It is the first module to run in `worker` without
  touching RabbitMQ. `aio-pika` is not a dependency of this module.

### 2. A-063 becomes a run-admission bound; its dispatch clause is deleted

A-063 said *"at most 5 cases … within one run and at most 10 across all runs of one workspace at any
moment."* The second half is superseded by ADR-0046's `batch_concurrency` (8, per provider config,
A-134), which now holds a semaphore in the same process. For a workspace with one provider config, 8
binds before 10 ever does; the outer bound is dead code in the common case, and two dispatch-level
semaphores in one process is the ADR-0016 defect rebuilt deliberately.

**What survives is `max_concurrent_runs = 2` per workspace, configurable, checked at claim time.** The
per-run concurrency of 5 is unchanged.

The reason it survives is **measurement, not throughput.** Total wall-clock is identical either way —
the same dispatches through the same 8-slot bottleneck. `00_context.md#success` states the 120 s target
**per suite**, and `prope_evaluation_run_duration_seconds` is labelled per run. Five interleaved runs
each record the full submit's duration and miss the stated metric on all five, while two-at-a-time makes
two hit it and the rest queue visibly. That is exactly what the lock's derived row already promises —
*"120 s × ceil(N_suites / 2)"*, *"Stated so the queue is expected rather than reported as a hang"* —
and it is what `prope_evaluation_run_queue_depth` counts.

So the two bounds now do two different jobs and neither duplicates the other:

| Bound | Owner | Unit | Purpose |
|---|---|---|---|
| `max_concurrent_runs` = 2 | A-063, this ADR | runs, per workspace | scheduling — per-suite wall-clock and a visible queue |
| `batch_concurrency` = 8 | ADR-0046, A-134 | dispatches, per provider config | resource — the workspace's own BYOK key |
| per-run concurrency = 5 | A-054 | dispatches, within one run | four waves for a 20-case suite |

### 3. The claim is a `SECURITY DEFINER` function — the third sanctioned policy bypass in Prope

Found while writing this decision rather than while grilling it, and it is load-bearing: **the claim loop
is a cross-tenant read.** Under `prope_app` and ADR-0045's deny-by-default policy, a `SELECT … WHERE
status = 'queued'` spanning every workspace returns zero rows. **A queued run's workspace is not known
until the claim, because the claim is what produces it** — which is ADR-0042's justification for
`lookup_session` and `lookup_api_key`, word for word.

`evaluation.claim_next_run()` follows ADR-0042's shape exactly:

- owned by `prope_migrate`, `SECURITY DEFINER`, empty `search_path`
- `REVOKE EXECUTE FROM PUBLIC`, `GRANT EXECUTE TO prope_app`
- the `SKIP LOCKED` select, the `max_concurrent_runs` predicate and the `status = 'running'` update all
  happen **inside** it, so the bypass is one call rather than a window the caller holds open
- it returns **only an identity tuple** — `(run_id, workspace_id, prompt_id, version_id, suite_id)`. No
  prompt text, no eval case input, no output content crosses the boundary
- `worker` then issues `SET LOCAL app.workspace_id` from that tuple, and **everything after the claim
  runs under ordinary RLS**: reading the revision, dispatching, pricing, writing `case_result`

**ADR-0042's enumeration goes from two to three.** Its test asserts the exact set of `SECURITY DEFINER`
objects in the database; the set stays enumerated and closed, and the third entry gets read the way the
first two are. That the count moved at all is worth stating plainly rather than burying — ADR-0042
called those two *"the ONLY sanctioned bypass of the tenant policy anywhere in Prope"*, and this is the
first addition since.

The alternative considered and rejected was a `evaluation.run_queue` table declared in `GLOBAL_TABLES`
with a written reason — three identifier columns, no tenant content, and it would have put the escape in
the file ADR-0045 made security-relevant rather than in the mechanism ADR-0042 capped. Rejected because
it reintroduces **a second representation of the queue**, which is the precise thing this ADR rejects the
broker for. A row that must be deleted in the same transaction that sets `status = 'running'` is
derived state that can drift, and being inside one database rather than across two makes it likelier to
be trusted, not less likely to diverge.

### 4. ADR-0046 is confirmed, not reopened

Batch dispatch lands in `worker` as it assumed. *"The processes are now the priority classes"* holds:
`app` dispatches interactive, `worker` dispatches batch, and no eval work executes in the container
serving the gateway's p95.

## Alternatives rejected

**Consume a RabbitMQ message per run in `worker`.** The obvious option, and cheap — ADR-0028 already
bought the broker, `aio-pika` is already a dependency, and `worker` already consumes for call-ledger's
drain. Rejected because **the broker's headline property is a liability in this workload.** A run's queue
already exists as `eval_run.status`; a message alongside it is a second queue for one workload, and the
two can disagree in both directions (a message with no row, a `queued` row with no message). Worse, an
unacked message on a worker crash **redelivers**, and redelivery here means re-dispatching every case a
second time — spending the workspace's own bring-your-own key on a run nobody asked for. AC-7 asserts
*"no case is dispatched twice"*, and A-054 chose the opposite behaviour explicitly: an interrupted run
keeps its partial results and *"Re-running is one click and costs a new run."* The escape — ack on
receipt — turns the broker into a fire-and-forget notification and forfeits the durability, retry and
dead-lettering it was chosen for, leaving only the second queue. A-063's *"start as slots free"* has no
message-level expression either: a consumer holding a message it cannot yet run either nack-requeues in
a loop or blocks a prefetch slot.

This is a workload-specific rejection, not a reversal of ADR-0028. Call-ledger's drain has the opposite
shape — a write that must not be lost, is idempotent on `call_id` (A-099), and costs nothing to repeat —
which is why redelivery is a feature there and a bill here.

**Leave the executor in `app` as an `asyncio` background task (A-054 as written).** Zero migration; the
run model is untouched. Rejected on two counts, either sufficient. It puts batch eval load — up to 5
concurrent dispatches per run, plus response parsing and assertion evaluation — directly into the
process holding the gateway's p95 budget, alongside argon2id and ~~Jinja rendering~~ A-047's diff
computation (A-130 — *amended 2026-08-09: ADR-0052 moves rendering to the browser, so the co-tenants are
argon2id and the `difflib` diff; the objection is unchanged*). And it
**reopens ADR-0046**, whose two per-process caps are a real gate only because the two priority classes
sit in different containers; held in one process they bound nothing, and 24 + 8 becomes 32 in flight from
`app` with no separation at all.

**Keep A-063 verbatim and raise `batch_concurrency` above 10** so the outer bound is the binding one.
Rejected because A-134 records 24 / 8 as a placeholder — *"no real provider rate-limit figure exists,
and OQ-012 has not supplied a load number either"* — sized so the sum stays at ADR-0016's original 32.
Raising batch either drifts the sum upward against an unmeasured provider limit, or cuts the gateway's
interactive headroom to fund batch work, which is the direction ADR-0016 exists to prevent. Trading a
real budget to preserve a redundant bound is the wrong side of that trade.

## Consequences

- **A-054's rewrite is complete and the run model is unchanged**, which is what A-054 predicted about
  itself: *"the run's state lives in the database rather than in the worker."* The 202-and-poll contract,
  the per-run concurrency of 5, the `interrupted` state and the sweeper's 5-minute no-progress rule all
  survive verbatim. Only *where the loop runs* changed.
- **The sweeper runs in `worker`** and its startup sweep now reaps rows left by the previous `worker`
  process. If `worker` is down entirely nothing sweeps — and nothing needs to, because nothing can reach
  `running` without a claim.
- **AC-10 must be restated.** It reads *"given a prompt with 5 suites and a global concurrency bound of
  10 … then at most 10 upstream dispatches are in flight at any moment"* — an assertion against a number
  this ADR deletes. The replacement asserts `max_concurrent_runs` holds at the claim and
  `batch_concurrency` holds at the provider seam, independently. Same shape as ADR-0046's AC-6. Recorded
  as owed to the step-6 sweep.
- **AC-9's refusal and A-029's spend-ceiling check move to claim time**, and a 202 now precedes both. The
  refusal is still *"before any case is dispatched"* as AC-9 requires, but the reviewer sees a 202
  followed by `status=refused` rather than a synchronous error. Both are therefore checked **twice**: at
  `POST` for a fast advisory refusal, and at claim as the authoritative one — a queued run may sit behind
  others that consume the budget while it waits. Only the claim-time result writes `status=refused`.
- **A queued run's start latency gains up to 1 s** of poll interval, against a 120 s budget. A wake-up
  nudge over the broker would remove it and reintroduce the second queue; not worth 0.8%.
- **`prope_evaluation_run_queue_depth` keeps its meaning and its alert changes character.**
  `EvalQueueBacklog` (>10 for 15 min) was written against a bound of 10 dispatches; under a bound of 2
  runs, a depth of 10 is five waiting submits. The threshold stands, its interpretation is now
  *"submissions are arriving faster than two-at-a-time drains"*, and its remedy is `max_concurrent_runs`
  rather than anything at the provider seam.
- **A second `worker` replica would break the admission bound** the way ADR-0028 broke ADR-0016 — two
  claim loops each counting `running` rows would still be correct, because the count is a database
  predicate inside the claim transaction rather than a process-local semaphore. That is a property worth
  naming: **this bound survives replication and ADR-0046's does not.** What would not survive is
  `batch_concurrency`, which stays process-local. A-138 records the unbounded cross-workspace case.
- **The `SECURITY DEFINER` count moves for the first time since ADR-0042.** Two becomes three, the set
  stays enumerated by a test, and the pattern that produced the third is worth naming: **a background
  worker that discovers work across tenants needs the same escape an authentication bootstrap needs, for
  the same reason.** Any future scheduled or queued job in `worker` that must find its own work will hit
  this, and the answer is a fourth named function returning identifiers — not a wider policy, not a
  BYPASSRLS role, and not a mode the executor runs in.
- The lock's `events:` block keeps `publishes: []` and `subscribes: []`. Its comment — *"No broker
  exists (A-012)"* — is replaced. A broker exists; this module declines it, and now the file says why.
