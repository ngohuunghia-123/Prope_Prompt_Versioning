# Phase 3: Durability, idempotency, and no-read-path - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-10
**Phase:** 3-durability-idempotency-and-no-read-path
**Mode:** `workflow.discuss_mode: assumptions`, run `--batch --analyze` per `.claude/CLAUDE.md`.
This session surfaced **evidence-backed assumptions with a trade-off table and a recommendation**
rather than open questions. Under ORCHESTRATION §6's `mode: yolo` the recommendation is **adopted**
rather than escalated; anything that would have been a blocking decision checkpoint carries an explicit
`ADOPTED: UNCONFIRMED` marker with its reversibility rating and is copied into `03-UAT.md` and
`.planning/ORCHESTRATION-DECISIONS.md`.

**Areas discussed:** The fallback's shape and placement · What the upsert actually protects · The
observability sweep and where it can be read from · Proving it — the sweep, the load claim, the chaos
provocation · The two carry-forwards (CR-01, CR-02)

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| The fallback's shape and placement | CL-01 and SC1. Phase 2 marked the failure site and left it; where the write goes, what it carries, and who wires it | ✓ |
| What the upsert actually protects | CL-02 and SC2. The primary key already refuses a second row; the claim is about the aggregate | ✓ |
| The observability sweep and where it can be read from | 17 declared metrics + T-005's 18th, six alerts, and a two-process registry nobody reconciled | ✓ |
| Proving it | AC-10's *internal* surface, the 50 rps claim, and how a broker outage is provoked without wrecking the suite | ✓ |
| CR-01 and CR-02 | Routed here by ORCHESTRATION §4 with the evidence already gathered | ✓ |

**Notes:** All five taken. `enqueue`'s handoff bound, the drain's window and the queue's arguments were
settled in Phase 2 (D-15, D-23, D-25) and are not reopened. The retention scheduler's cold-workspace gap
is Phase 7's and is only touched here because `oldest_body_age_seconds` inherits it.

---

## The fallback's shape and placement

### Where the direct write goes and who supplies the session

**Assumption surfaced:** `enqueue.py:180` already says *"Phase 3's direct-write fallback goes on the
failure branch below. Not beside it, not in the caller"*, so the placement is settled and the open
question is only how the database reaches a module that today has no database import.

| Option | Description | Adopted |
|--------|-------------|---------|
| An injected `FallbackWriter`, bound at `app.py`, living in a new `fallback.py` | `publish_record` calls a required keyword argument. `enqueue.py` gains no `workspace_transaction` import, so nothing invites a write inside `enqueue()`'s 1 ms span. Matches `build_retention_resolver`'s posture — bind at the composition root | ✓ |
| Import the sessionmaker into `enqueue.py` | Fewer moving parts, one file. Costs: a database import in the module whose contract is *never raises, never blocks*, and the next reader is one line away from putting a write on the caller's span | |
| An optional parameter defaulting to `None` | No churn in the existing `tests/broker/` call sites. Costs: a process composed without a fallback loses records and says nothing; there is exactly one composition root, so there is nothing to make it optional for | |

**Adopted:** injected, required, in its own module. **`ADOPTED: UNCONFIRMED` — reversibility: costly.**
The signature is what Phase 19's gateway inherits and `app.py` is the file seven more modules edit.
Accepted cost stated in CONTEXT: every existing broker test call site must pass a fallback.

### Whether the fallback batches

**Assumption surfaced:** the fallback will be under throughput pressure during an outage, so it should
drain the handoff and write per-workspace batches the way the drain does.
**The arithmetic contradicts the assumption**, which is why it was surfaced rather than asked.

| Option | Description | Adopted |
|--------|-------------|---------|
| One record, one transaction | ADR-0041's literal wording. ~1.5 ms per single-record transaction is ~650 writes/sec against a 50 rps arrival rate — 13× headroom, so the handoff does not fill. One record's refusal loses exactly one record | ✓ |
| Drain and batch by workspace | Higher ceiling. Costs: `write_records` is all-or-nothing, so a batched fallback needs a duplicate of `_retry_group_one_at_a_time` inside `app` — complexity on the one path that only ever runs during an incident, which is ADR-0041's own argument against the spill file | |

**Adopted:** one record, one transaction. The rejection quotes ADR-0041 back at itself: *the mechanism
most likely to be wrong is the one exercised least.*

### What the fallback carries

| Option | Description | Adopted |
|--------|-------------|---------|
| Metadata only; body dropped and counted | ADR-0041 and A-037. Falls out well: `expires_at` is stamped only on a body row, so this path reads no retention setting and D-11's promise holds structurally rather than by discipline | ✓ |
| Metadata plus body | Recovers data the outage would otherwise cost. Costs: reintroduces a settings read on the degraded path D-11 exempted by name, and contradicts ADR-0041's stated decision | |

**Adopted:** metadata only.
**Conflict found while adopting:** `body_dropped_total`'s declared `reason` label set is
`queue_full | oversize` and neither is true here — there is no in-process queue since ADR-0041 deleted
it. **Raised as `OQ-022`** against `docs/modules/call-ledger.lock.yml`
`observability_requirements.metrics`, not resolved by reusing `queue_full`.

### The per-body size cap

**Assumption surfaced:** the lock's eighth failure mode requires a cap *and states no number anywhere*,
so a number has to be argued here or it will be picked at implementation time.

| Option | Description | Adopted |
|--------|-------------|---------|
| 256 KiB on the pair, enforced in `enqueue()`, bytes computed here | 26× ADR-0033's stated ~10 KB/call; ~64k tokens of UTF-8, above the context window of pilot models, so a body above it is an asset rather than a conversation. 24 h of the ADR's 10k calls/day at the cap is ≤2.5 GB of broker disk | ✓ |
| 64 KiB | Tighter disk bound. Costs: ~16k tokens is inside an ordinary long response, so `body_dropped_total{reason=oversize}` becomes a normal-traffic counter rather than an anomaly signal | |
| No cap | Nothing to argue. Costs: nothing else on the path bounds bytes — A-149's queue bound is a message *count*, and `x-max-length-bytes` cannot be added now without D-23's delete-and-redeclare | |
| Trust the caller's `CallBodyDraft.byte_size` | Free. Costs: the field is `int \| None` and caller-supplied; a cap enforced from a figure the capped party supplies is not a cap | |

**Adopted:** 256 KiB, computed here, enforced before the `put_nowait` so 512 unbounded bodies cannot
enter the handoff first. **`ADOPTED: UNCONFIRMED` — reversibility: cheap** (a constant and a counter; no
stored data depends on it), but it is a product-visible policy and belongs on the human list.

**Related conflict raised, not adopted around:** the queue has a declared message-count bound and no
byte bound at all, while T-005's own text says the broker is a second body store. **`OQ-025`** against
`security_requirements` T-005 / A-149.

---

## What the upsert actually protects

### The statement shape

**Assumption surfaced:** "idempotent on `call_id`" means `ON CONFLICT (call_id)`, and the choice is
between `DO NOTHING` and `DO UPDATE`. **The framing is wrong**, and surfacing it is the point: the
primary key already refuses a second `call_record` row today, so a plan that stops at `ON CONFLICT`
passes "the record appears once" and still fails CL-02. What redelivery corrupts is
`ledger.workspace_spend`, which is maintained inside the writer's own transaction (A-103).

| Option | Description | Adopted |
|--------|-------------|---------|
| `DO NOTHING … RETURNING call_id`, aggregate built from the returned set | The only shape that says *which rows were new*. Requires moving from `text()` to a Core `insert()` over the existing `models.call_record` Table, and inverting `write_records`' loop so the month buckets are built after the insert | ✓ |
| `DO UPDATE` | Absorbs both duplicate shapes and keeps the current statement shape. Costs: re-prices an existing record from a redelivered envelope, which ADR-0019 forbids; and it is **unavailable on `call_body`**, where `prope_app` holds no `UPDATE` — two idempotency semantics in one function | |
| `DO NOTHING` without `RETURNING` | Smallest diff. Costs: the aggregate is still incremented for rows that were not inserted, so a redelivery still moves a workspace's spend. This is CL-02 failing while looking closed | |

**Adopted:** `DO NOTHING … RETURNING`. **`ADOPTED: UNCONFIRMED` — reversibility: one-way in effect.**
Every workspace's spend total is derived from this statement and a total moved by a redelivery cannot be
recovered from the data.

### What happens to a body whose record was already written by the fallback

**Assumption surfaced:** ADR-0041 creates a duplicate shape nobody has to guess at — a *timed-out*
confirm means the broker did receive the message, the fallback wrote the record without its body, and
the broker later delivers the same record *with* its body.

| Option | Description | Adopted |
|--------|-------------|---------|
| The body follows its record: write a body only for a `call_id` this transaction inserted | Keeps AC-1's stated equality — *"`body_dropped_total` equals the number missing from `call_body`"* — reconcilable. A counter that cannot be checked against the table is worse than a body already declared best-effort | ✓ |
| Let the late body land under its own `ON CONFLICT DO NOTHING` | Recovers real data. Costs: the drop was already counted, so `body_dropped_total` over-counts against `call_body` forever and AC-1's equality stops being assertable | |

**Adopted:** the body follows its record. **`ADOPTED: UNCONFIRMED` — reversibility: one-way for the
data in question** — a body not written at the moment of the late delivery is not written later.

### Counting redeliveries and duplicates

| Option | Description | Adopted |
|--------|-------------|---------|
| Two counters at two layers | `redelivered_total` from `message.redelivered` in the drain (the broker's view); `duplicate_call_id_total` from the offered/returned gap in `write_records` (the database's view). `LedgerDuplicateCallIds` reads them together, which is impossible if one is derived from the other. Placing the second in `write_records` gives the drain, the fallback and `price_usage` the count for free | ✓ |
| One counter | Simpler. Costs: the alert's whole stated method — *"duplicates that track redeliveries are the broker working, duplicates that exceed them are a caller generating ids badly"* — becomes uncomputable | |

**Adopted:** two counters.

### What `metadata_dropped_total` means after the fallback

**Assumption surfaced:** ADR-0041 says the counter now means *"both the broker and the database were
unavailable"*, but `drain.py` increments it twice for records it **dead-letters** (`_parse:249` and the
retry ladder at `:313`). Those records are in the DLQ, which A-149 gives a 30-day TTL and T-005 gives
an alert on any non-zero depth.

| Option | Description | Adopted |
|--------|-------------|---------|
| Remove both increments; the counter means "exists nowhere" | `LedgerMetadataDropped` pages immediately, and a page that fires on one malformed envelope is a page people learn to close. `dlq_depth > 0` is the signal for a dead-letter, and nothing goes unreported | ✓ |
| Keep them; a dead-lettered record is genuinely absent from `ledger.call_record` | Defensible on the success metric's own words. Costs: two alerts for one event, and the page that is supposed to mean "both stores are gone" becomes routine | |

**Adopted:** remove both. **`ADOPTED: UNCONFIRMED` — reversibility: cheap**, but it changes what an
existing page means, and the removal is the kind of change that gets skipped rather than argued.

---

## The observability sweep and where it can be read from

### How many metrics ship, and when

| Option | Description | Adopted |
|--------|-------------|---------|
| All eighteen at import, including the ones nothing increments | A metric that appears the first time it is non-zero has no baseline and no alert can be written against it. `missing_version_id_total`'s whole job is to be zero | ✓ |
| Only the ones this phase's code touches | Smaller surface. Costs: the phase's own spec line names the metric block, and the gap would land on nobody | |

**Adopted:** all eighteen — the lock's seventeen plus T-005's `prope_call_ledger_dlq_depth`, whose
absence from the metric block rides `OQ-022`.
**Two consequences recorded rather than discovered:** `missing_version_id_total` has no increment site
today (a gateway draft with a NULL `version_id` dies as an `IntegrityError` under a constraint name), so
`write_records` gains an explicit refusal; and Phase 2's `ceiling_failed_open_total` is not the declared
metric — `ceiling_check_total{result}` is. Whether the Phase 2 counter is retired is left to the planner.

### Where the metrics are read from

**Assumption surfaced — and it is the largest structural finding of the phase:** `prometheus_client`'s
registry is **per process**, and Prope runs two. D-17 says `worker` serves no HTTP, and D-17 is
*derived from ADR-0028* rather than chosen, so it is not this phase's to reverse.

| Option | Description | Adopted |
|--------|-------------|---------|
| `/metrics` on `app` as the eighth path; name the gap; raise an OQ | Ships the exposition surface that makes eight metrics readable now, does not reverse a derived ADR decision, and puts the reconciliation in front of the spec owner with the exact list attached | ✓ |
| Open a metrics port on `worker` | Every metric readable. Costs: reverses a decision derived from ADR-0028, and adds the surface T-02-15 registers — a port reachable from every container on the compose network | |
| `prometheus_client` multiprocess mode over a shared volume | Genuinely viable: one image, one host, one compose file. Costs: a writable volume shared between two containers, gauges degraded to a chosen reduction mode, and a change to a deployment stack that owns no milestone | |
| A Pushgateway | Standard answer for short-lived producers. Costs: ADR-0033 fixes the runtime at seven services | |
| Ship no `/metrics` at all, as Phase 2 did | Consistent with Phase 2's stated posture. Costs: this is the last M1 phase, so no phase would ever ship it, and six alert rules would be true on paper | |

**Adopted:** `/metrics` on `app`, unversioned and sessionless beside `/healthz` and `/readyz`;
`EXPECTED_ROUTES` grows from seven to eight. **`ADOPTED: UNCONFIRMED` — reversibility: costly** (an
eighth path in a table seven more modules extend, and OQ-026's answer may move where exposition lives).
**Raised as `OQ-026`**, naming ADR-0028 / D-17 against the lock's `observability_requirements` and
`alerts`, with the exact list: eight metrics exist only in `worker`, four more are incremented in both
processes so `app`'s copy is partial, and three of the six alerts read metrics on that list.

### Where the depth gauges are read

| Option | Description | Adopted |
|--------|-------------|---------|
| A third supervised job in `worker`, passive-declaring both queues on an interval | A depth gauge published by the consumer whose backlog it measures **goes silent exactly when the backlog matters**. A separate job also reports honestly when there is no traffic at all | ✓ |
| Inside the drain's window loop | No new job, and the depth is read where it is consumed. Costs: a wedged drain stops publishing depth, and Prometheus sees a stale series rather than a rising one | |

**Adopted:** a separate job. `worker`'s two job-name constants become three and the module docstring's
sentence about later arrivals is corrected in the same change.
**Conflict carried into `OQ-022`:** `queue_depth`'s declared `lane = metadata | body` label describes
the two in-process lanes ADR-0041 deleted; a broker queue has one depth.

### `oldest_body_age_seconds`, deferred out of Phase 2 into this one

**Assumption surfaced:** the gauge is a single query. **It is not** — under ADR-0045 a `prope_app` read
with no `app.workspace_id` returns zero rows, so `SELECT min(created_at) FROM ledger.call_body` reports
a healthy gauge forever. That is the same failure the alert exists to catch, one layer up.

| Option | Description | Adopted |
|--------|-------------|---------|
| Per workspace across `ObservedWorkspaces`, reduced to one unlabelled gauge | Correct for every workspace the process has seen, one indexed read each, and it reuses the enumeration the retention sweep already walks | ✓ |
| A fifth `SECURITY DEFINER` function to enumerate workspaces | Complete coverage. Costs: exactly four are sanctioned and a test asserts the set is those four. **Refused outright** | |
| Report it as a full close | Tidier. Costs: it would be the same lie the alert is written against | |

**Adopted:** per workspace, reduced, **and reported as a partial close.** A workspace that has sent no
traffic since process start is invisible to the gauge that exists to notice its unswept bodies; closing
that needs `access.list_workspaces()` in **Phase 7**, which `run_worker` already takes as a parameter.

### The six alert rules

| Option | Description | Adopted |
|--------|-------------|---------|
| A rules file in the repository, plus a test that parses it and asserts every metric it names is in the registry | The thresholds and their reasons are the value, and the test is what stops the file rotting — a rule referencing `prope_call_ledger_spill_bytes` would parse fine and alert never | ✓ |
| Leave the alerts as prose in the lock file | Nothing to maintain. Costs: unassertable, and the phase's spec line names `alerts` | |
| Add a Prometheus service so the rules run | Honest end to end. Costs: ADR-0033 fixes seven services and the deployment stack owns no milestone (PITFALLS §4) | |

**Adopted:** a rules file plus its registry test.

---

## Proving it

### AC-10's *internal* surface

**Assumption surfaced:** Phase 2's `test_route_table.py` already covers this. **It covers one third of
it** — its own docstring says *"CL-10's full claim is Phase 3's"*, and AC-10's words are *"the module's
entire HTTP **and internal** surface"*.

| Option | Description | Adopted |
|--------|-------------|---------|
| Three layers: assembled route table + OpenAPI, the internal Python surface, the grant matrix | `get_run_totals` is a function, not a route — a body returned through a dataclass satisfies every route-table assertion in the repository. And `prope_app` holds `SELECT` on `call_body` because the retention `DELETE` needs it, so the database cannot be the guarantee and the source-level enumeration stands in for it | ✓ |
| Extend the route-table test only | Cheapest. Costs: asserts the layer that was never at risk and skips the two that are | |

**Adopted:** three layers, written with the existing shared helpers so **Phase 23 extends a test rather
than inventing one**, and using `assembled_routes()` rather than `app.routes` because Broken Window #4
is standing and a naive walk asserts vacuously.

### The 50 rps claim

| Option | Description | Adopted |
|--------|-------------|---------|
| A CI-resident proxy at 80% handoff depth plus a marked full-fat run | The lock's stated `condition` is *"queue at 80% depth"* and pre-filling to 410 of 512 is instant. 500 timed `enqueue()` calls put 25 samples above the p95, so one scheduling hiccup moves the estimate by a rank rather than defining it. The 10-minute run exists, marked, with a documented invocation | ✓ |
| Run 50 rps × 10 min in CI | Proves the stated criterion exactly. Costs: 30,000 records and ten minutes on a 151-second suite is a suite nobody runs | |
| Write only the full-fat run | Honest to the spec. Costs: SC5 is then proven by a test that never executes | |

**Adopted:** split. **`ADOPTED: UNCONFIRMED` — reversibility: cheap.** Whether the proxy runs by default
and where the marker is registered (`pyproject.toml` has no `markers` key) is left to the planner.

### How a broker outage is provoked

| Option | Description | Adopted |
|--------|-------------|---------|
| Close the publisher's channel and connection under the running publisher; separately point `build_connection` at a closed port | Produces exactly the bare `except Exception` branch the fallback must cover, in milliseconds, with no container manipulation | ✓ |
| Stop the session-scoped `rabbitmq_container` | The most literal reading of "unreachable". Costs: the fixture is session-scoped and shared, so every later test in the run fails for an unrelated reason | |
| A module-scoped second RabbitMQ for the chaos tests | Real and isolated. Costs: the pending todo already records a 10–20 s broker boot repeated across every subagent's pytest run; paying it again for a failure a closed channel reproduces exactly is the wrong trade | |

**Adopted:** closed channel plus closed port.

---

## The two carry-forwards

### CR-01 — unbounded `retention_days`

**Evidence, re-confirmed here rather than inherited:** `schemas.py:394` declares `retention_days: int`
with no `le=`; `api.py:720` evaluates `timedelta(days=payload.retention_days)`; `OverflowError`
subclasses `ArithmeticError` and matches none of `classify_write_failure`'s branches, so it takes the
`PERMANENT` default and dead-letters.

| Option | Description | Adopted |
|--------|-------------|---------|
| `le=3650` on the pydantic field | The bound's job is to stop an input becoming an unclassifiable exception. Ten years is the largest value still recognisably a retention *policy* — longer than the pilot, longer than anything OQ-013 could answer, and short enough that "never delete" cannot be spelled in the field | ✓ |
| A `CHECK` on the column instead | Matches "build database-first". Costs: **impossible** — the `OverflowError` is raised in the client before any statement exists | |
| Add an `ArithmeticError` branch to `classify_write_failure` | Fixes the dead-letter. Costs: treats a bad input as a write-classification problem two modules away from where it was accepted | |

**Adopted:** `le=3650`, with the asymmetry against the lower bound written at the field so the next
reader does not tidy one into the other's home. **`ADOPTED: UNCONFIRMED` — reversibility: cheap**, but
it is a product-visible limit. The route is unreachable until Phase 7 fills the session seam, so this
lands before its own exposure.

### CR-02 — `run_publisher` returns with the handoff undrained

**Evidence:** `enqueue.py:274-283` — `while not stopping.is_set()` exits with up to `HANDOFF_MAXSIZE`
(512) records buffered, with **no counter and no log**. SC1's words are *"every drop is counted"*.

| Option | Description | Adopted |
|--------|-------------|---------|
| Drain on stop under a bounded deadline, then count and log the remainder | A-139 already promises *"a graceful stop drains and does not hit it"*, and the fallback clears a full 512-record buffer in under a second. The deadline must be reconciled with `app.py:89`'s existing `PUBLISHER_STOP_TIMEOUT_SECONDS`, which bounds the wait on this same task | ✓ |
| Count the remainder without draining | Literal compliance with "every drop is counted". Costs: a deploy that counts 512 drops is a correct counter over a worse product | |

**Adopted:** drain, then count what is left.

### The publisher task's own death

**Assumption surfaced while reading CR-02:** the publisher is started as a bare `asyncio.create_task`
(`app.py:137`), so an exception escaping `run_publisher` ends it silently — every later `enqueue` fills
the handoff and drops, with no crash, no restart, and nothing in `/readyz`, which is the database alone
by decision (D-16). The fallback makes that reachable, because the fallback can raise where
`publish_record` currently cannot.

| Option | Description | Adopted |
|--------|-------------|---------|
| Make it a supervised job | `prope.supervisor.supervise` already restarts with backoff and drains on stop, and D-14 built it to take later jobs without redesign. This is its first host outside `worker` | ✓ |
| A broad `try/except` loop inside `run_publisher` | Local and small. Costs: handles the raise this phase can imagine and not the one it cannot, and duplicates backoff the project already owns and tests | |

**Adopted:** supervised.

---

## Claude's Discretion

Left to the researcher and planner, open rather than decided:

- Histogram bucket edges for `enqueue_duration_seconds` and `write_lag_seconds` — the library defaults
  start at 5 ms and cannot measure a p95 < 1 ms target at all
- How `/metrics` is mounted, given that an ASGI sub-application mount is invisible to
  `assembled_routes()` and to the OpenAPI walk AC-10 asserts over
- Whether `ceiling_failed_open_total` is retired in favour of the declared `ceiling_check_total{result}`
- The `oldest_body_age_seconds` query shape — `min(created_at)` against wall clock, or a predicate over
  `expires_at`, which differ for a workspace whose window changed after D-10 stamped its rows
- The shutdown-drain deadline and its relationship to `PUBLISHER_STOP_TIMEOUT_SECONDS`
- The depth-gauge interval, argued against the scrape interval and the round-trip cost
- Whether the CI-resident load proxy runs by default, and where the pytest marker is registered
- Whether `enqueued_total` gains an `oversize` outcome value or the oversize body is visible only on
  `body_dropped_total`
- How many OQ files the five conflicts become — one per upstream field is Phase 2's precedent, but the
  split is a planner call. **All five must be raised: OQ-022 … OQ-026**
- `prope_report` read grants, carried forward unresolved from Phase 1 and Phase 2, and this is the last
  M1 phase in which closing it is cheap

## Open questions allocated

| Id | Against | Conflict |
|----|---------|----------|
| OQ-022 | `call-ledger.lock.yml` `observability_requirements.metrics` | `body_dropped_total.reason` (`queue_full \| oversize`) and `queue_depth.lane` (`metadata \| body`) both describe the in-process queue ADR-0041 deleted; the fallback's body drop has no declared reason value; and `dlq_depth`, required by `security_requirements` T-005, is absent from the list ROADMAP counts at 17 |
| OQ-023 | `call-ledger.lock.yml` `observability_requirements.metrics` | `unpriced_total`'s declared labels `provider_config_id, upstream_model` are per-workspace identifiers — a `provider_config_id` resolves to exactly one workspace — while the repo asserts `workspace_id` is never a label, and `/metrics` is unauthenticated |
| OQ-024 | `call-ledger.lock.yml` `test_plan.chaos` and `test_plan.unit` | *"fill the spill volume and assert the page fires and readiness is withheld"* and *"queue accounting and the two-lane drop order"* both test machinery ADR-0041 deleted, and the first contradicts the amended `/readyz` clause in the same file |
| OQ-025 | `call-ledger.lock.yml` `security_requirements` T-005 / A-149 | The queue's declared bound is a message count with no byte bound; `x-max-length-bytes` was never declared and cannot be added without D-23's delete-and-redeclare, while T-005's own text says the broker is a second body store |
| OQ-026 | ADR-0028 / D-17 against `call-ledger.lock.yml` `observability_requirements` + `alerts` | `prometheus_client`'s registry is per process and `worker` serves no HTTP, so eight metrics exist only in `worker` and four more are partial in `app`; three of the six declared alerts read metrics on that list |

Per Phase 2's precedent (OQ-018…OQ-021 were created by the plans that hit them), the files are written
by the plan or executor that reaches each conflict, not by this context pass. The ids above are reserved
for those five and for nothing else.

## Deferred Ideas

None — discussion stayed within phase scope. Two **partial closes** are recorded in CONTEXT.md's
`<deferred>` section with their residue named: `oldest_body_age_seconds` covers only enumerated
workspaces until Phase 7's `access.list_workspaces()`, and twelve of the eighteen metrics are
unscrapable or partial from `app`'s `/metrics` until OQ-026 is answered. Everything else in that section
is a fixed ROADMAP boundary — the gateway (19–21), evaluation (16–18), Phase 23's cross-module route
table, and the deployment stack and SPA, which own no milestone.
