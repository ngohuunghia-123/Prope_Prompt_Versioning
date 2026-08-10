# API Coverage — Phase 2: Seams: enqueue, the broker drain, and the ceiling

> Deterministic detector result (`bin/lib/api-coverage.cjs --json` over the ROADMAP phase scope +
> `02-CONTEXT.md`): `{"detected": false, "signals": []}`.
>
> The detector returned **false**, but this phase adds `aio-pika` and talks AMQP 0-9-1 to a RabbitMQ
> 4.x broker for the first time in the project. A broker is a real external service with a real
> capability surface, and "we integrated whatever the first use case exercised" is exactly the hole
> this matrix exists to close. A matrix is therefore recorded rather than a no-integration
> declaration — the stricter of the two available answers.

**Surface enumerated:** the AMQP 0-9-1 / RabbitMQ 4.x capability set reachable through
`aio-pika==9.6.2`, plus the RabbitMQ management HTTP API. `INTEGRATE` is the default; every
`OPT-OUT` carries a reason.

| capability | decision | reason |
|---|---|---|
| `connection.open` — `aio_pika.connect_robust` (auto-reconnect, state recovery) | INTEGRATE | |
| `channel.open` in confirm mode (`publisher_confirms=True`, the aio-pika default) | INTEGRATE | |
| `queue.declare` with `x-arguments` (durable, `x-message-ttl`, `x-max-length`, `x-overflow`) | INTEGRATE | |
| `queue.declare` dead-letter arguments (`x-dead-letter-exchange`, `x-dead-letter-routing-key`) | INTEGRATE | |
| `basic.publish` persistent (`DeliveryMode.PERSISTENT`) with `mandatory=True` | INTEGRATE | |
| Publisher confirm handling — `Basic.Ack` / `Basic.Nack` / `DeliveryError` / `TimeoutError` | INTEGRATE | |
| `basic.consume` via the async queue iterator with `no_ack=False` | INTEGRATE | |
| `basic.qos` — `set_qos(prefetch_count=...)` | INTEGRATE | |
| `basic.ack` (single delivery tag) | INTEGRATE | |
| `basic.reject` / `basic.nack` with `requeue` both ways | INTEGRATE | |
| `queue.purge` | INTEGRATE | test rig only — the per-test broker cleanup that mirrors the Postgres truncate fixture |
| Management HTTP API `GET /api/queues/{vhost}/{queue}` | INTEGRATE | test only — D-23's declared-argument read-back needs the broker's own view of what it stored |
| `basic.ack(multiple=True)` (cumulative ack) | OPT-OUT | unsafe once workspace groups commit independently — a cumulative tag would ack a failed group alongside committed ones (RESEARCH Pattern 3) |
| `exchange.declare` — direct / topic / fanout / headers exchanges | OPT-OUT | one queue only (ADR-0028, A-142 §5); the default exchange routes by queue name and always exists, which also removes the "DLX missing at dead-letter time silently drops" failure |
| Alternate exchange (`alternate-exchange`) | OPT-OUT | `mandatory=True` plus the `unroutable` confirm branch already surfaces an unroutable publish as a counted failure |
| Quorum queues / streams / `x-queue-type` | OPT-OUT | quorum queues do not support `reject-publish-dlx`, which A-149's "overflow dead-letters rather than drops" and ADR-0041's nack-driven fallback both depend on; Raft replication buys nothing at n=1 (ADR-0033). Confirmed at the plan 02-01 decision checkpoint |
| `x-delivery-limit` (poison-message limit) | OPT-OUT | not available on a classic queue; the drain's own permanent/transient failure classification carries the poison-message decision instead |
| Runtime **policies** (`max-length`, `message-ttl`, `dead-letter-exchange` as broker policy) | OPT-OUT | D-23 locks the values as declare-time `x-arguments` so a test can read them back; the irreversibility is recorded at the declaration site rather than traded away |
| Transactions (`tx.select` / `tx.commit`) | OPT-OUT | publisher confirms are the ADR-0028 mechanism and are an order of magnitude cheaper; transactions would sit on the one path with a p95 < 1 ms budget |
| RPC pattern — `reply_to` / `correlation_id` / direct-reply-to | OPT-OUT | `events.publishes: []` — nothing waits on a written call record, so there is no reply to route |
| Message `priority` / `x-max-priority` | OPT-OUT | every call record is equally accountable; a priority ordering would let one workspace's records outrank another's |
| Message `headers` beyond the envelope body | OPT-OUT | the envelope is versioned in-band (`schema_version`) and evolves additively (A-142 §5); a header channel would be a second, unversioned contract |
| Consumer priorities / exclusive / single-active consumer | OPT-OUT | the drain is a single consumer by design (Pitfall 6 and 7) and that is asserted in code, not negotiated with the broker |
| Delayed-message and shovel/federation plugins | OPT-OUT | plugins are host state the compose file would have to carry; ADR-0033 fixes 7 services / 2 images |
| TLS / `amqps://` | OPT-OUT | the broker is reachable only on the compose-internal network on one VM (ADR-0033); credentials come from the single `.env` (ADR-0032). Revisit if the broker ever leaves the host |
| Multiple vhosts | OPT-OUT | one instance, one queue; a vhost boundary would duplicate the isolation Postgres RLS already owns |
| Consumer-cancel notification | OPT-OUT | `connect_robust` re-establishes the consumer on reconnection (the specific 9.6.0 fix this pin was chosen for); a hand-rolled cancel handler would duplicate it |
| `queue.delete` / `queue.unbind` at runtime | OPT-OUT | the queue is declared once from one shared definition (D-24) and never torn down by application code; a delete-and-redeclare is an operator act with data in it |
