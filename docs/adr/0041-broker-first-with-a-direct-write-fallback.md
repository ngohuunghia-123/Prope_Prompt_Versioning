# ADR-0041 — The ledger write path is broker-first with a direct-write fallback, and the spill file is deleted

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: call-ledger, gateway, evaluation — supersedes the spill half of A-037
**Related**: A-012, A-037, A-086, A-087, A-098, A-099, A-103, ADR-0026, ADR-0028, ADR-0031, ADR-0040,
`00_context.md#success`, `00_context.md#constraints`

## Context

A-037 was written for a system with no broker. Its durability mechanism was entirely in-process: a
bounded queue, a local spill file, a spill replay on restart, a `/readyz` clause asserting the spill
directory was writable, and `LedgerSpillWriteFailed` as a page.

ADR-0028 then put RabbitMQ in the stack, and A-037 was amended to match — but the amendment left a
contradiction sitting across two files. It says:

> "A publish failure on this path is counted and dropped, never raised — the same rule this assumption
> already set for body drops, for the same reason."

while the lock file says `prope_call_ledger_metadata_dropped_total` **must stay 0**, pages immediately,
and that a single drop makes *"the 100% of calls record a version ID claim false and measurably so."*
Both cannot be true. `00_context.md#success` states the metric as 100%, and the module's own risk section
concedes the honest version — that an in-process buffer cannot promise it absolutely, so the bound is
made explicit rather than implied.

What the broker changed is which failures are realistic. The exotic ones (disk full, kill -9 mid-batch)
are now the broker's problem and it is better at them than a file. The mundane one is new and
unglamorous: **`docker compose up -d` restarts `rabbitmq` while `app` keeps serving**, or the broker
enters flow control. The gateway is healthy, responses are correct, and the accountability metric goes
quietly false.

## Decision

**Publish to RabbitMQ with publisher confirms. On a failed or nacked confirm, write the metadata row
directly to PostgreSQL inline and count it. Bodies are dropped in the fallback path, as A-037 already
allows. There is no spill file.**

- **Ordering is unchanged.** The publish happens after the response is flushed (A-087), so this path
  stays outside the p95 span by construction. The fallback runs in the same place — after the flush, in
  the degraded case only.
- **The fallback is metadata-only.** Metadata is the accountability claim; bodies are best-effort by
  declaration and were already the first thing dropped under pressure.
- **A-099's upsert absorbs both duplicate shapes**: a broker redelivery of a record already written, and
  a late delivery of a record the fallback already wrote directly. Both resolve to the same `call_id`
  and the second one changes nothing, which is what stops a workspace's spend from moving.
- **The fallback write obeys ADR-0040 for free** — it is a single record for a single workspace, so
  `SET LOCAL app.workspace_id` applies with no grouping.
- **`/readyz` reports on the database only.** A broker outage is *degraded and counted*, not un-ready:
  the process can still record every call, so withholding readiness would take the gateway out of
  service to protect a path that is working.

This **deletes a mechanism rather than adding one**. Gone: the spill file and its format, the replay
job, the spill-directory readiness clause, the disk-full failure mode, and three metrics. Added: one
branch and two counters.

It adds no new failure domain either. PostgreSQL is already a *harder* dependency than RabbitMQ —
nothing in Prope works without it, while the broker only carries deferred work — so "broker down,
database up" is the only gap the fallback needs to cover, and "database down" was never survivable.

## Alternatives rejected

**Keep the spill file, repoint its trigger from queue-full to publish-failed.** Rejected as a third
durability layer. Nothing in the lock's AC-1, AC-2, alerts or chaos tests would have had to change,
which is its real appeal — it is the cheapest option in edit distance. But it leaves the system with
broker, spill, and database all holding the same record, and the spill is the only one of the three with
its own disk-full failure mode, its own replay correctness, and its own readiness check. That is a small
runbook, and A-012's surviving clause after its own amendment is *no component needing its own runbook*.
It also means the mechanism most likely to be wrong is the one exercised least — a spill path that only
runs during an incident is a path nobody has watched work.

**Broker only; count the drop and accept it.** Rejected on what it costs elsewhere. It is defensible in
isolation — the broker sits in the same compose file on the same host under ADR-0033, so "broker
unreachable" is nearly "host unreachable" — but "nearly" is doing the work, and the gap it leaves is not
a rare one. Taking this option honestly would require restating a success metric in `00_context.md` from
100% to something qualified, and downgrading `LedgerMetadataDropped` from a page to a graph, because it
would fire on an ordinary deploy. Changing a product metric to fit a write path is the wrong direction
when the write path can be fixed with a branch.

**An outbox table written in the gateway's own transaction.** Rejected because there is no such
transaction. The gateway's whole design is that the record is handed over *after* the response is
flushed (A-087), so there is nothing left open to write into, and creating one would put a database
write back inside the p95 span — the exact thing A-037 exists to prevent.

## Consequences

- **`prope_call_ledger_metadata_dropped_total` can stay 0 and stay a page.** It now means both the
  broker and the database were unavailable, which is a genuine incident rather than a deploy.
- **Metrics change.** `spill_bytes`, `spill_write_failed_total` and `spill_replayed_total` are removed;
  `publish_failed_total` and `fallback_direct_write_total` replace them. `LedgerSpillWriteFailed`
  becomes `LedgerPublishFailing`. `queue_depth` now reads the broker's queue rather than an in-process
  gauge. Recorded as an amendment in the lock file.
- **AC-1 and AC-2 must be restated** against the broker and the fallback rather than against an
  in-process queue and a spill replay. Flagged in the lock; the properties they assert — metadata never
  dropped, exactly-once on replay — are unchanged and are now easier to test, because a broker
  redelivery can be provoked deliberately.
- A sustained broker outage becomes visible as a rising `fallback_direct_write_total` rather than as
  data loss. The system degrades from batched asynchronous writes to inline ones, which is slower on the
  post-flush tail and correct throughout.
- The gateway process now holds a database write path it did not have before. It is exercised only in
  the fallback, and it is the same writer function the worker calls, so there is one code path priced
  and one code path stamping `expires_at` — not two implementations that could drift.

> **Followed up 2026-08-09 at the gateway's stack pass. The deletion was incomplete in the docs, and it
> left one stated cost.**
>
> **`gateway.lock.yml` still named the spill file four times** — in its `outputs` seam (*"a spill replay
> after a crash cannot double-count it"*), in the queue-saturation failure mode (*"metadata is spilled
> locally and never dropped"*), in A-087's assumption text, and in the chaos plan (*"assert the metadata
> spill survives"*). All four are now rewritten against publisher confirms and the inline fallback, and
> **gateway AC-11 is owed a restatement** for the same reason this ADR already flagged call-ledger's
> AC-1 and AC-2: it asserts an in-process queue filling and bodies being dropped first, which is no
> longer the write path. Worth noting as a general lesson — deleting a mechanism is a documentation
> sweep across every module that referenced it, and this one reached two locks.
>
> **The residue, now recorded as A-139.** This ADR keeps A-087's ordering deliberately, so the publish
> happens *after* the response is flushed. A process **hard-killed in that interval** loses the record,
> and `prope_call_ledger_metadata_dropped_total` does not increment — nothing ran to count it. That is
> precisely what the spill file used to cover. Nothing is rebuilt for it, on this ADR's own grounds: an
> outbox row puts a database write back inside the p95 span (already rejected above), and publishing
> before the flush puts the broker on the response path, which
> `00_context.md#constraints` forbids non-negotiably. The window is the enqueue span, p95 < 1 ms; a
> graceful stop drains and does not hit it, so an ordinary ADR-0031 deploy is not the exposure. It is
> stated rather than hidden, which is the same treatment this ADR gave every other trade it made.
