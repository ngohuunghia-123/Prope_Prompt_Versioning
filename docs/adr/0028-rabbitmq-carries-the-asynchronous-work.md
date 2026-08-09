# ADR-0028 — RabbitMQ carries the asynchronous work, and the worker is a second process from the same image

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — per-module rows record only whether a module publishes or consumes
**Related**: A-012, A-037, A-054, A-087, A-099, A-106, A-130, ADR-0018, ADR-0026, ADR-0033

## Context

A-012 and A-037 both state that Prope has no message broker. A-012: *"No managed cluster, no message
broker, no separate worker fleet, no service mesh, no component that requires its own runbook."*
A-037: *"the gateway forwards and responds first, then hands the call record to an in-process
background writer through a bounded queue. No external message broker."* Both are `decided_by: agent`,
and A-012's is pending OQ-005, which has never been answered.

Three workloads are asynchronous in the current design:

1. **Call-record writing** (A-037, A-087, A-099) — enqueued *after the response is flushed*. Since the
   p95 span is defined as *"request arrival to upstream dispatch, plus upstream completion to response
   flush"*, everything after the flush is outside the latency budget by construction.
2. **Eval runs** (A-054) — asynchronous in-process at concurrency 5, client polls, a sweeper reaps runs
   that stop advancing.
3. **Body retention deletion** (A-106) — a periodic job over `expires_at`.

The agent recommendation was **no broker**: PostgreSQL already participates in the writer's transaction,
A-099's caller-generated `call_id` with an upsert already provides idempotency, and A-054 already has a
restart story. The user decided otherwise on 2026-08-09 and chose a dedicated broker, then chose
RabbitMQ over Kafka and NATS.

## Decision

**RabbitMQ 4.x is the message broker. A `worker` service, built from the same image as `app` with a
different command, consumes from it.**

- **Workload assignment is per-module** and is recorded in each module's pass. This ADR fixes the
  product and the topology, not the queue list.
- **A-099 becomes load-bearing rather than merely prudent.** RabbitMQ delivers at least once, so a
  redelivered call record must not double-count spend. The caller-generated `call_id` and the
  `INSERT … ON CONFLICT (call_id)` upsert are the mechanism, and they are now protecting against a
  routine broker behaviour rather than a crash-recovery edge case.
- **Every consumer is idempotent or explicitly documented as not needing to be.** Where a consumer's
  work is not naturally idempotent, it takes the same shape as the call-record writer: a caller-supplied
  identifier and a uniqueness constraint that makes the second delivery a no-op.
- **Dead-letter queues are configured from the start**, one per work queue. A message that fails
  repeatedly lands somewhere inspectable rather than cycling; that visibility is most of what a broker
  buys over a database table.
- `app` publishes and never consumes. `worker` consumes and never serves HTTP. Both are the same build
  artefact, which keeps ADR-0026's one-image property intact.
- **Durability is configured, not assumed**: durable queues, persistent messages, publisher confirms on
  the call-record path. A broker that loses the metadata A-037 calls durable would be strictly worse
  than the in-process buffer it replaced.

## Alternatives rejected

**No broker — PostgreSQL as the durable queue.** This was the recommendation and it lost to the user's
decision. Its case was real and is recorded here because a future reader will re-derive it: the
call-record enqueue sits outside the p95 budget by construction, the durable store is already in the
transaction, A-099 already supplies idempotency, and A-054 already handles restart by reaping. What it
costs is that retry curves, dead-lettering, backoff, and consumer concurrency all become code that
someone in this project writes and maintains, rather than configuration in a product that already has
them. With three genuinely asynchronous workloads rather than one, that reimplementation is no longer
trivial, and the failure mode of a hand-rolled queue is discovered in production rather than in a
management UI.

**Apache Kafka in KRaft mode.** Rejected on cost against benefit on this specific host. Its real
advantage here is replay — `00_context.md#scope` names *"Langfuse export is a later integration
(A-039)"*, and a replayable log would make that export a backfill rather than a migration. But no MVP
consumer wants to rewind, the feature it would serve is explicitly out of scope, and Kafka would be the
largest single tenant on a VM also running PostgreSQL, the application, and the observability stack —
1–2 GB against RabbitMQ's ~250 MB, with the most intricate configuration in the compose file.

**NATS JetStream.** Rejected as the least-proven of the three at the moment it matters. It is the
lightest by a wide margin and does both work-queue and stream semantics, but its Python client and
operational literature are thinner than RabbitMQ's, and A-012's real currency is *"debuggable by one
person"* — at 3am, ecosystem depth is the feature.

**Redis as a queue.** Rejected because its other two plausible jobs in Prope are already forbidden: the
resolution cache is a bounded in-process LRU (A-080) and *"nothing in access-control is cached, by this
module or by its callers"* (A-114, ADR-0022). It would therefore exist solely as a queue, without
RabbitMQ's delivery guarantees, acknowledgement semantics, or dead-lettering.

## Consequences

- **A-012 and A-037 are amended**: the "no broker, no separate worker fleet" clause of each is
  superseded by this ADR. The `ops_capacity` row in `00_context.md#constraints` is amended to state the
  real service count.
- **A-054 must change at evaluation's per-module pass.** *"Asynchronously in-process at concurrency 5"*
  described a system with one process. With a worker container, the run executor moves to the consumer,
  and the sweeper's assumptions about what "this process" means need restating. The run model itself is
  unaffected — A-054 already put run state in the database *"rather than in the worker"*, which is why
  this is an amendment and not a redesign.
- **The revisit condition named while rejecting no-broker is now live on day one.** An in-process
  executor either double-runs or starves once more than one process can claim work; the broker is what
  makes that safe, and it is the reason A-054's change is required rather than optional.
- The operational surface grows by two services (`rabbitmq`, `worker`) and gains a management UI on
  :15672, which is genuinely the most useful debugging surface added by this baseline.
- A broker outage now degrades call-record persistence and eval execution. It does **not** affect the
  gateway's response path: A-087 enqueues after the flush, and a publish failure there is counted and
  dropped rather than raised, exactly as A-037 already specified for body drops.
