# Phase 3: Durability, idempotency, and no-read-path — Research

**Researched:** 2026-08-10
**Domain:** PostgreSQL 17 upsert-with-RETURNING semantics under SQLAlchemy 2.0's `insertmanyvalues`; `prometheus_client` exposition and registry scope across two processes; asyncio shutdown draining on Python 3.13; AMQP passive-declare depth reads; the three-layer absence proof AC-10 asks for
**Confidence:** HIGH on everything read out of this repository, out of the installed wheels, or provoked against the installed libraries this session; HIGH on the PostgreSQL and RabbitMQ semantics (quoted from vendor docs); MEDIUM on the histogram bucket edges and the depth-gauge interval (arithmetic against stated targets, offered as the argument the Discretion list demands rather than as a measurement); LOW on nothing that is load-bearing

> **One thing to know before anything else.** This phase adds **no new runtime dependency and no new
> package of any kind**. Every library it needs is already pinned in `pyproject.toml` and already
> installed. The research budget is therefore spent where the phase actually turns: on the exact
> behaviour of `INSERT … ON CONFLICT DO NOTHING … RETURNING` when SQLAlchemy batches it, on what
> `prometheus_client`'s per-process registry means for a system with two processes, on what a passive
> AMQP declare does and does not count, and on the three places a stored body can be read from that a
> route-table assertion cannot see. **Pitfall 1 is the one that would silently break CL-02**, and it
> was found by provoking the installed SQLAlchemy rather than by reading about it.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

*Copied verbatim from `.planning/phases/03-durability-idempotency-and-no-read-path/03-CONTEXT.md`
§ Implementation Decisions. Numbering continues from Phase 2's D-09…D-25. **This phase consumes D-26
through D-45.***

**The direct-write fallback — CL-01, ROADMAP SC1**

- **D-26:** The fallback is an **injected callable, bound at `app.py`**, and it lives in a new
  `src/prope/call_ledger/fallback.py`. `run_publisher` and `publish_record` take
  `fallback: FallbackWriter` as a **required keyword argument with no default**, and call it at **all
  four** failure sites in `publish_record` — the three declared `publish_failed_total` reasons plus the
  bare `except Exception` branch that catches a closed channel, a dead connection or a broker that was
  never running. That fourth branch is the one an ordinary `docker compose up -d` produces and it is
  the one ADR-0041 was written about; leaving it out would build the fallback for the rare failures and
  not for the mundane one. **`enqueue.py` gains no database import.** That module's whole contract is
  *never raises, never blocks*, and a `workspace_transaction` import sitting in it is an invitation to
  write inside `enqueue()` — which is CL-12's budget. Rejected: importing the sessionmaker into
  `enqueue.py` (see above); an optional parameter defaulting to `None` (a process composed without a
  fallback loses records silently, and the composition root is one file so there is nothing to make
  optional for). Consequence to state in the plan: every existing `tests/broker/` call site must pass a
  fallback, and that churn is the price of the argument being required.
  — **Reversibility:** costly — the signature is the seam Phase 19's gateway inherits, and `app.py` is
  the one composition root seven more modules edit.
- **D-27:** **One record, one transaction.** The fallback writes the single record that just failed to
  publish, through `workspace_transaction(sessionmaker, record.workspace_id)` and `write_records`, and
  returns. It does not drain the handoff, does not group, and does not batch. ADR-0041 words it exactly
  this way (*"write the metadata row directly to PostgreSQL inline"*) and the arithmetic agrees: a
  single-record transaction against a local PostgreSQL costs on the order of 1.5 ms, so the fallback
  sustains roughly 650 records/sec against a steady-state 50 rps — thirteen times the rate it has to
  absorb, which is why the handoff does not fill during a broker outage and why SC1's thousand calls do
  not need a faster shape. Rejected: draining and batching by workspace like the drain does. It buys
  throughput the arithmetic says is not needed, and it costs a duplicate of
  `_retry_group_one_at_a_time` inside `app` — because `write_records` is all-or-nothing, so a batched
  fallback needs the same one-at-a-time retry ladder the drain has. **That is ADR-0041's own argument
  against the spill file turned on this phase: the mechanism most likely to be wrong is the one
  exercised least, and this one only ever runs during an incident.** One record per transaction also
  means one record's refusal loses exactly that record, so `metadata_dropped_total` increments by
  exactly one and needs no reconciliation.
- **D-28:** **The fallback is metadata-only, and therefore reads no setting.** The draft is rewritten
  with `body=None` before it reaches `write_records`. This is what makes D-11's promise — *"Phase 3's
  direct-write fallback inherits no settings query"* — true for free rather than by discipline:
  `expires_at` is stamped only on a `call_body` row, so a path that writes no body never consults
  `ledger.workspace_retention` and `write_records`' `retention_window` default is never exercised here.
  The dropped body increments `body_dropped_total`. **Its declared `reason` label set is
  `queue_full | oversize` and neither value is true** — there is no in-process queue to be full since
  ADR-0041 deleted it, and the body is not oversize. A third value is needed. **Raise `OQ-022` against
  `docs/modules/call-ledger.lock.yml` `observability_requirements.metrics`** naming the field and the
  conflict; do not edit the spec to agree, and do not quietly reuse `queue_full` for a queue that does
  not exist.
- **D-29:** **A per-body size cap of 256 KiB on the pair, enforced inside `enqueue()`, computed from
  bytes this module encodes itself.** The lock's eighth failure mode requires a cap and states no
  number, so the number is argued here. ADR-0033 sizes the host against *"roughly 10 KB per call"*, so
  256 KiB is twenty-six times the stated average and about 64k tokens of UTF-8 — above the context
  window of the models a pilot will use, which makes a body above it an asset or a base64 blob rather
  than a conversation. The disk arithmetic is the check that matters: the queue's declared bound is
  1,000,000 *messages* with **no byte bound at all**, so the real ceiling on broker disk is the 24-hour
  TTL, and 24 hours of the ADR's stated 10k calls/day at the cap is at most 2.5 GB — inside the 80 GB
  host that already carries `call_body` at ~3 GB/month. Rejected: 64 KiB, which is ~16k tokens and
  inside an ordinary long response, so `body_dropped_total{reason=oversize}` would become a
  normal-traffic counter rather than an anomaly signal. Rejected: no cap — nothing else on the path
  bounds bytes, and `x-max-length-bytes` **cannot be added to the queue now** without D-23's
  delete-and-redeclare in every environment that has run. **Enforced in `enqueue()`, before the
  `put_nowait`**, because the handoff's own docstring says the growth is *"in units of payload, not
  units of pointer"* — a cap applied in the background publisher lets 512 unbounded bodies into memory
  first. **The size is computed here and overwrites `CallBodyDraft.byte_size`**, which is caller-supplied
  and `int | None`: a cap enforced from a figure the capped party supplies is not a cap. The record
  itself always continues with `body=None` — metadata is never dropped for a body's sake. The cost is
  one `str.encode()` in the caller's span; at the cap that is tens of microseconds against a 1 ms
  budget, and it is stated rather than assumed because CL-12 measures that span.
  — **Reversibility:** cheap — a constant with a counter behind it, and no stored data depends on it.
- **D-30:** **`metadata_dropped_total` counts records that exist nowhere, and a dead-letter is not one.**
  Phase 2's `drain.py` increments it twice for records it dead-letters — at `_parse` for an invalid
  envelope (`drain.py:249`) and in `_retry_group_one_at_a_time` for a refused write (`drain.py:313`).
  Both of those records are in `prope.call_record.dlq`, which A-149 gives a 30-day TTL and T-005 gives
  an alert on any non-zero depth. **Both increments are removed here.** ADR-0041 is explicit that after
  the fallback this counter *"means both the broker and the database were unavailable"*, and
  `LedgerMetadataDropped` pages immediately — a page that fires on one malformed envelope is a page
  people learn to close. The three surviving increment sites are: a full handoff, a fallback that
  itself raised, and D-31's undrained shutdown remainder. The trade, stated out loud: a dead-lettered
  record is genuinely absent from `ledger.call_record`, so the *"100% of calls record a version ID"*
  claim is false for it — and the signal that says so becomes `dlq_depth > 0` rather than a second page
  for the same event.
  — **Reversibility:** cheap.
- **D-31:** **CR-02 is closed by draining, not only by counting.** `run_publisher` currently returns as
  soon as `stopping` is set, with up to `HANDOFF_MAXSIZE` (512) records in the buffer and no counter and
  no log (`enqueue.py:274-283`). On stop it now drains what is in the handoff — publishing where the
  broker answers, falling back where it does not — under a bounded deadline, and increments
  `metadata_dropped_total` once per record still buffered when the deadline expires, with one log line
  carrying the count. Rejected: counting the remainder without draining it. SC1's words are *"every drop
  is counted"*, and a deploy that counts 512 drops is a correct counter over a worse product; the
  fallback makes draining cheap (D-27's arithmetic clears a full 512-record buffer in under a second)
  and A-139 already promises *"a graceful stop drains and does not hit it"*. The deadline must be
  argued against `app.py:89`'s existing `PUBLISHER_STOP_TIMEOUT_SECONDS = 5.0`, which currently bounds
  the wait on this same task — the two numbers are one number and the plan must not set them
  independently.
- **D-32:** **`app`'s publisher becomes a supervised job.** It is started today as a bare
  `asyncio.create_task` (`app.py:137`), so an exception escaping `run_publisher` ends the publisher
  silently: every later `enqueue` fills the handoff and then drops, with no crash, no restart and
  nothing in `/readyz`, which is the database alone by decision. `prope.supervisor.supervise` already
  restarts a crashed job with backoff and drains on stop, and D-14 built it *"to accommodate later jobs
  without being redesigned"* — this is the first such job outside `worker`. Consequence: `app` imports
  `prope.supervisor`, and a `supervisor.job_crashed` line can now come from the `app` process, whose
  `job` label values are still a closed set fixed in source (`LOGGABLE_FIELDS` already carries `job`).
  Rejected: a bare `try/except` loop inside `run_publisher`. It handles the raise this phase can
  imagine and not the one it cannot, and it duplicates backoff logic the project already owns and tests.
  — **Reversibility:** cheap.

**Idempotency — CL-02, ROADMAP SC2**

- **D-33:** **`INSERT … ON CONFLICT (call_id) DO NOTHING … RETURNING call_id`, never `DO UPDATE`, and
  the monthly aggregate is computed from the rows that actually inserted.** Three reasons and each is
  sufficient. First, ADR-0019 prices once at write time and never revises; a `DO UPDATE` would re-price
  an existing record from a redelivered envelope, which is the one thing effective dating exists to
  prevent. Second, `ledger.call_body` **cannot** use `DO UPDATE` — `prope_app` holds
  `SELECT, INSERT, DELETE` and deliberately no `UPDATE` (`0003_ledger_tables.py:252`) — so `DO UPDATE`
  on one table and `DO NOTHING` on the other would put two idempotency semantics inside one function.
  Third, and this is the load-bearing one: **`RETURNING` over `DO NOTHING` is the only thing that says
  which rows were new**, and CL-02's actual claim is about `ledger.workspace_spend`, not about
  `ledger.call_record`. A redelivered batch of five where three already exist must add two to
  `call_count` and two records' worth of cost, and no other statement shape tells you that. This
  restructures `write_records`: the month buckets are built **after** the insert, from the returned
  `call_id` set, and the currency-conflict check runs over the inserted subset. **The statement must
  move from `text()` to a Core `insert()`** — `sqlalchemy.dialects.postgresql.insert(models.call_record)`
  — because a `text()` executemany does not return per-row results and `models.py` already defines the
  five tables as Core `Table` objects. `tests/architecture/test_no_sql_interpolation.py` is the gate
  that must still pass across the change.
  — **Reversibility:** one-way in effect — every workspace's spend total is derived from this statement,
  and a total that was moved by a redelivery cannot be un-moved from the data.
- **D-34:** **A `call_body` row is written only for a record this transaction actually inserted.** The
  body insert is filtered by the same returned `call_id` set (and carries its own
  `ON CONFLICT DO NOTHING`, because `DO UPDATE` is not available to it). The case this decides is the
  one ADR-0041 creates on purpose: a confirm that **timed out** rather than being refused means the
  broker did get the message, the fallback wrote the record without its body, and the broker later
  delivers the same record *with* its body. Letting that body land would recover data — and would break
  AC-1's stated equality, *"`body_dropped_total` equals the number missing from `call_body`"*, because
  the drop was already counted. A counter that cannot be reconciled against the table is worse than a
  body that was already declared best-effort (A-037). Consequence to state: a body lost to a timed-out
  confirm is lost permanently, by decision.
- **D-35:** **Two counters at two layers, because they measure two different things.**
  `prope_call_ledger_redelivered_total` is incremented in the drain from `AbstractIncomingMessage.redelivered`
  — the broker's own view of what it re-sent. `prope_call_ledger_duplicate_call_id_total` is incremented
  inside `write_records`, from the gap between rows offered and `call_id`s returned — the database's own
  view of what was already there. They are deliberately not one counter: the lock's
  `LedgerDuplicateCallIds` alert reads them **together** (*"duplicates that track redeliveries are the
  broker working, and duplicates that exceed them are a caller generating ids badly"*), and that
  comparison is impossible if either side is derived from the other. Because the count lives in
  `write_records`, all three callers — the drain, the fallback, and `price_usage` — get it for free,
  which is the answer to INT-019's *"idempotent on `call_id` — the same upsert INT-018's drain uses"*.
- **D-36:** **`classify_write_failure`'s `IntegrityError` branch narrows and changes meaning.** Its
  docstring today names a unique violation on `call_id` as the thing it dead-letters and calls that *"a
  named Phase 2 gap, not an accident"* (`drain.py:130-140`). After D-33 that violation cannot occur, so
  an `IntegrityError` reaching the classifier now means a genuinely different constraint — a CHECK the
  record violates. The branch stays `PERMANENT` and the docstring is rewritten to say so. **The
  `PERMANENT` default itself is not touched:** it rests on the classic queue having no
  `x-delivery-limit` (T-02-06), which D-23 fixed one-way, and a phase that softened it would make a
  permanently-failing record an infinite loop.
- **D-37:** **CR-01's bound goes on the pydantic field, and this is the one bound the database cannot
  carry.** `schemas.py:394` declares `retention_days: int` with no upper bound and its docstring argues,
  correctly for the lower bound, that `ck_workspace_retention_window_is_positive` owns it at the engine.
  The upper bound is different in kind: `api.py:720` evaluates `timedelta(days=payload.retention_days)`
  **before any statement exists**, and `OverflowError` subclasses `ArithmeticError`, which matches none
  of `classify_write_failure`'s branches and so takes the `PERMANENT` default. A `CHECK` cannot help
  with an exception raised in the client. So the field gains `le=3650` — ten years. Argued, not
  rounded: the bound's job is to keep an input from becoming an unclassifiable exception, and among
  values that do that, ten years is the largest that is still recognisably a retention *policy*. Longer
  than the pilot, longer than anything OQ-013 could plausibly answer, and short enough that "never
  delete" — the one answer ADR-0018 and A-040 refuse — cannot be spelled in this field. The
  asymmetry between the two bounds is written at the field so the next reader does not "tidy" one of
  them into the other's home. The route is unreachable until Phase 7 fills the session seam, so this is
  a fix landed before its own exposure, which is the cheap moment.

**The body store has no reader — CL-10, ROADMAP SC4**

- **D-38:** **The sweep is three assertions at three layers, and AC-10's word *internal* is what forces
  the second and third.** AC-10 says *"the module's entire HTTP **and internal** surface"*, and Phase 2
  asserted only the first — `tests/architecture/test_route_table.py` walks the assembled table and the
  OpenAPI schema for `FORBIDDEN_FIELD_NAMES`, and its own docstring says *"CL-10's full claim is Phase
  3's"*. The two layers it does not reach:
  1. **The internal Python surface** — every public callable and every public dataclass / pydantic model
     reachable from `prope.call_ledger`, walked by `inspect`/AST, asserting no return annotation, field
     name or parameter name is a body. `get_run_totals` is a function, not a route, and a body reaching
     a caller through a returned dataclass would satisfy every route-table assertion in the repository.
  2. **The grant matrix** — `prope_app`'s privileges on `ledger.call_body` are `SELECT, INSERT, DELETE`
     and the `SELECT` is load-bearing for the retention `DELETE` (`0003_ledger_tables.py:246-252` says
     so). So the database cannot be the guarantee, and the assertion that stands in for it is that the
     only statements naming `call_body` anywhere in `src/` are `writer.INSERT_CALL_BODY` and
     `retention.py`'s bounded delete. Asserted as a source-level enumeration, not as a claim.
  Written using the existing shared helpers (`prope.session_auth.assembled_routes`, `declared_action`)
  so **Phase 23 extends this test rather than inventing one** — and using `assembled_routes` rather
  than `app.routes` is not optional: Broken Window #4 records that a naive walk asserts vacuously.
- **D-39:** **`/metrics` ships on `app` as the eighth path — unversioned, no session dependency, no
  declared `ManagementAction` — and twelve of the eighteen metrics are still not scrapable.** The first
  half is straightforward: ADR-0030 puts Prometheus in the stack and a metric no scraper can reach is an
  alert rule that is true on paper; a scraper has no session, so the route sits beside `/healthz` and
  `/readyz` under A-045's unversioned rule; `EXPECTED_ROUTES` in `test_route_table.py` grows from seven
  to eight and the count assertions move with it. The second half is the finding. **`prometheus_client`'s
  registry is per process, and `worker` serves no HTTP by D-17** — which is *derived from ADR-0028*,
  not chosen, and therefore not this phase's to reverse. `written_total`, `write_lag_seconds`,
  `queue_depth`, `dlq_depth`, `redelivered_total`, `retention_deleted_total`, `oldest_body_age_seconds`
  and `ceiling_check_total` exist only in `worker`; `unpriced_total`, `unknown_usage_total`,
  `missing_version_id_total` and `duplicate_call_id_total` are incremented in both processes, so `app`'s
  copy is a partial count. **Three of the six declared alerts — `LedgerWriteLagHigh`,
  `LedgerRetentionOverdue`, `LedgerDuplicateCallIds` — read metrics on that list.** Rejected here and
  named in the open question: opening a metrics port on `worker` (reverses a derived ADR decision and
  adds the surface T-02-15 registers); a Pushgateway (ADR-0033 fixes the count at seven services);
  `prometheus_client`'s multiprocess mode over a shared volume (viable — one image, one host, one compose
  file — but it needs a writable volume shared between two containers, degrades gauges to a chosen
  reduction mode, and is a deployment-stack change in a stack that owns no milestone). **Raise `OQ-026`**
  naming ADR-0028 / D-17 against `docs/modules/call-ledger.lock.yml` `observability_requirements` and
  `alerts`. Ship the instrumentation, ship `/metrics` on `app`, and record the gap with the exact list
  above.
  — **Reversibility:** costly — an eighth path in a table seven more modules extend, and the OQ's answer
  may move where the exposition lives.

**The eighteen metrics and the six alerts — T-005's sweep**

- **D-40:** **All eighteen are defined at import in `prope/observability.py`, including the ones nothing
  increments yet.** The lock lists seventeen and `security_requirements` T-005 requires an eighteenth,
  `prope_call_ledger_dlq_depth`, which is absent from the metrics block — that omission rides `OQ-022`.
  A metric that appears the first time it is non-zero has no baseline, and an alert cannot be written
  against a series that does not exist; `missing_version_id_total` is the sharpest case, since its whole
  job is to be zero. Two consequences the plan must state. **`missing_version_id_total` needs a place to
  be incremented**, and today there is none: a `source=gateway` draft with a NULL `version_id` is
  refused by `ck_call_record_gateway_calls_carry_version_id` as an `IntegrityError`, which dead-letters
  under a constraint name rather than under this counter's name. So `write_records` gains an explicit
  refusal for that case, before the insert, incrementing the counter — the same posture
  `EvalUsageRow.__post_init__` already takes for `run_id`, `case_id` and `version_id`. And **Phase 2's
  `ceiling_failed_open_total` is not in the spec**: the declared metric is
  `ceiling_check_total{result = allowed | refused | failed_open}`, which counts all three branches. The
  declared one ships; whether the Phase 2 counter is retired or kept alongside is left to the planner
  (see Claude's Discretion).
- **D-41:** **`occurred_at` is stamped in `enqueue()`, not in `publish_record`.** Today
  `CallRecordEnvelope.from_draft(record, occurred_at=datetime.now(UTC))` is evaluated in the background
  publisher (`enqueue.py:186`), so the handoff dwell falls outside it — and `write_lag_seconds` is
  declared as *"enqueue -> durable"*. Measuring from the publish moment would make the one interval the
  fallback exists to protect invisible in the one metric named after it. The record's own `created_at`
  is not the alternative: that is the call's time, before the response was even flushed, so it would
  fold the whole request into the lag. Cost, stated: `enqueue()` acquires a clock read it does not have
  today, on the order of a hundred nanoseconds inside a 1 ms budget. `occurred_at` is call-ledger's own
  envelope field and crosses no registered contract, so nothing outside this module changes.
- **D-42:** **The two depth gauges are their own supervised job in `worker`, not a read inside the
  drain.** A passive re-declare of `prope.call_record` and `prope.call_record.dlq` on an interval sets
  `queue_depth` and `dlq_depth`. The reason it is not folded into the drain's window loop is the failure
  it has to survive: **a depth gauge published by the consumer whose backlog it measures goes silent
  exactly when the backlog matters.** A wedged or crashed drain stops reporting depth, and Prometheus
  sees a stale series rather than a rising one. A separate job also reports honestly when there is no
  traffic at all, which is the state `LedgerWriteLagHigh` and the DLQ alert care about most. The
  interval is a judgement to be argued in the plan against Prometheus's conventional 15 s scrape and
  against two AMQP round trips per pass, not picked. Consequence: `worker` gains a third resident,
  and `worker.py`'s docstring sentence about which jobs join it must be corrected in the same change.
  **`queue_depth`'s declared `lane = metadata | body` label describes the two in-process lanes ADR-0041
  deleted** — a broker queue has one depth. That rides `OQ-022`.
- **D-43:** **`oldest_body_age_seconds` is computed per workspace and reduced to one unlabelled gauge,
  and it inherits Broken Window #3's blind spot — stated, not hidden.** The gauge cannot be a single
  query: under ADR-0045 a `prope_app` read with no `app.workspace_id` set returns **zero rows**, so a
  bare `SELECT min(created_at) FROM ledger.call_body` reports a healthy gauge forever, which is the
  exact failure this alert exists to catch, one layer up. It is therefore computed inside the same
  enumeration the retention sweep already walks (`ObservedWorkspaces`), one indexed read per workspace,
  and reduced to the maximum. **The consequence is that a workspace which has sent no traffic since the
  process started is invisible to the gauge that exists to notice its unswept bodies.** Phase 2's
  `worker.py` promised this gauge would measure that gap; it measures it only for enumerated
  workspaces, and closing it needs `access.list_workspaces()` in Phase 7. The plan must say so and
  `deferred-items.md` must carry it forward — this is a genuine partial close, and reporting it as a
  full one would be the same shape as the job that runs cleanly and deletes nothing. Unlabelled for
  `metadata_dropped_total`'s reason: a per-workspace gauge is the label ADR-0030 and this repo's own
  test refuse.
  — **Reversibility:** cheap — the reduction changes when the enumerator does.
- **D-44:** **The six alert rules ship as a Prometheus rules file in the repository, and a test parses
  it and asserts every metric it names exists in the registry.** The deployment stack owns no milestone
  (PITFALLS §4), so no phase will ever wire this file into a running Prometheus — and that is not a
  reason to leave the rules unwritten, because the rules are where the thresholds and the *reasons* for
  them live, and the lock file spells all six out including `LedgerRetentionOverdue`'s deliberate choice
  to read the data rather than the job. The test is what stops the file rotting: a rule referencing
  `prope_call_ledger_spill_bytes` would parse fine and alert never. Rejected: leaving the alerts as
  prose in the lock file (unassertable, and the phase's own spec line names `alerts`); inventing a
  compose service to run Prometheus (ADR-0033 fixes the count and the deployment stack is not this
  phase's).

**Proving it — CL-12, ROADMAP SC5, and the chaos suite**

- **D-45:** **The load claim splits into a fast CI-resident test and a marked full-fat run, and the
  broker outage is provoked without touching the session container.** Three parts:
  1. **`enqueue` p95 < 1 ms is measured in the caller's process, at 80% handoff depth**, which is the
     lock file's stated `condition` and is cheap to set up — pre-fill the handoff to 410 of 512 with
     the publisher paused, then time 500 `enqueue()` calls with `perf_counter_ns` around the call and
     nothing else. 500 samples because a p95 is the (0.95N)th order statistic: at N=500 there are 25
     observations above it, so one scheduling hiccup moves the estimate by a rank rather than defining
     it; at N=100 there are five, and a single GC pause is a fifth of the tail.
  2. **The 50 rps × 10 min run is marked and deselected by default.** 30,000 records and ten minutes
     against a 151-second suite is a suite nobody runs; a marked test with a documented invocation is a
     test that exists and is honest about when it runs. The CI-resident proxy above asserts the same
     two properties — the p95 and `metadata_dropped_total == 0` — at a duration the suite can carry.
  3. **"RabbitMQ unreachable" is provoked by closing the publisher's channel and connection under the
     running publisher**, and separately by pointing `build_connection` at a closed port to cover the
     startup path. Rejected: stopping the session-scoped `rabbitmq_container` (it is session-scoped and
     shared, so every later test in the run fails for an unrelated reason); a second module-scoped
     RabbitMQ container for the chaos module.

### Claude's Discretion

*Copied verbatim. These are **open, not decided** — resolved below in § Open Questions, with the
evidence each resolution rests on. The plan must record which resolutions it adopted.*

- **Histogram bucket edges for `enqueue_duration_seconds` and `write_lag_seconds`**, argued against
  p95 < 1 ms and p95 < 2 s / p99 < 10 s respectively. `prometheus_client`'s default buckets start at
  5 ms, which would put every enqueue observation in the first bucket and make the p95 unmeasurable —
  the defaults are not usable for either metric and the plan must say what replaces them.
- **How `/metrics` is mounted.** `prometheus_client.make_asgi_app()` mounted as a sub-application is
  not an `APIRoute` and would **not** appear in `assembled_routes()` — a route that evades the table
  AC-10 asserts over. Whichever shape is chosen, the eighth path must be visible to
  `test_route_table.py` and to the OpenAPI walk, or it must be asserted absent from both on purpose.
- **Whether `ceiling_failed_open_total` is retired** in favour of the declared
  `ceiling_check_total{result}`, kept alongside as a Phase 2 artefact, or made an alias.
- **The `oldest_body_age_seconds` query shape** — `min(created_at)` against wall clock, or a predicate
  over `expires_at`. The two differ for a workspace whose window changed after D-10 stamped its rows.
- **The shutdown-drain deadline** (D-31) and its relationship to `app.py:89`'s existing
  `PUBLISHER_STOP_TIMEOUT_SECONDS`.
- **The depth-gauge interval** (D-42), argued against the scrape interval and the round-trip cost.
- **Whether the CI-resident load proxy runs by default** or behind the same marker as the full run, and
  where the marker is registered (`pyproject.toml` has no `markers` key today, so an unregistered
  marker warns).
- **Whether `enqueued_total` gains an `oversize` outcome value** or the oversize body is visible only
  on `body_dropped_total` — the record itself is still `accepted`, so the two readings differ.
- **How many OQs the five conflicts become.** OQ-022 through OQ-026 are allocated to this phase and
  each conflict below is named against a distinct upstream field; one file per field is Phase 2's
  precedent (OQ-018…OQ-021) but the split is a planner call. **All five must be raised.**
- **`prope_report` read grants** on `ledger.workspace_retention` and on the ledger generally — carried
  forward unresolved from Phase 1 and Phase 2's identical open item, and this is the last M1 phase in
  which it can be closed cheaply.

### Deferred Ideas (OUT OF SCOPE)

*Copied in substance from CONTEXT § Deferred.*

None — discussion stayed within phase scope. Two items are **partially** closed and carried forward
with their residue named: `oldest_body_age_seconds` covers only the workspaces `ObservedWorkspaces` has
enumerated (Phase 7 closes it with `access.list_workspaces()`), and twelve of the eighteen metrics are
unscrapable or partial from `app`'s `/metrics` until OQ-026 is answered.

Fixed ROADMAP boundaries rather than omissions: the **gateway** (Phases 19–21, GATE-11 is CL-01's other
half); the **evaluation** module (Phases 16–18); the **cross-module route-table assertion** in full
(Phase 23, PITFALLS §5); the **deployment stack** and the **React SPA**, which own no milestone
(PITFALLS §3 and §4). **OQ-013 remains unresolved and A-020 holds the line.**
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **CL-01** | "Every gateway call produces a durable call record carrying its version ID even when RabbitMQ is unreachable; only bodies are dropped, and the drop counter accounts for every one" [VERIFIED: `.planning/REQUIREMENTS.md:22`] | § *Pattern 1* (the injected `FallbackWriter` and its four call sites); § *Pitfall 4* (`_start_publisher` swallows a broker failure, so the fallback must be bound even when the broker never connected); § *Pitfall 9* (a fallback that raises is the only remaining `metadata_dropped_total` site and must be caught) |
| **CL-02** | "A redelivered or replayed call record is written exactly once, leaving the workspace's spend total unchanged, with every duplicate counted" [VERIFIED: `.planning/REQUIREMENTS.md:23`] | § **Pitfall 1** — the `sort_by_parameter_order` trap that would turn CL-02's own statement into an `InvalidRequestError`; § *Pattern 2* (the restructured `write_records`); § *Pitfall 2* (the mixed-currency refusal moves subject); § *Pitfall 3* (the body follows its record, and `DO NOTHING` is legal on `call_body` where `DO UPDATE` is not) |
| **CL-07** | "A spend-ceiling check that cannot be evaluated returns allowed, counts the failure, and never raises into evaluation" [VERIFIED: `.planning/REQUIREMENTS.md:28`] | § *OQ-R3* (retire `ceiling_failed_open_total`; the declared metric is `ceiling_check_total{result}` and **all three branches need an increment site**, not just the open one — today only the open branch counts) |
| **CL-10** | "No route, parameter, or function anywhere in the module returns a stored request or response body" [VERIFIED: `.planning/REQUIREMENTS.md:31`] | § *Pattern 6* (the three layers); § **Pitfall 12** — `prope_report` is `LOGIN BYPASSRLS` and holds `SELECT` on `ledger.call_body`, which no layer of D-38's sweep can see; § *Pitfall 7* (`/metrics` as a `Mount` evades the very table AC-10 asserts over) |
| **CL-12** | "Enqueuing a call record stays off the caller's response path at p95 under 1 ms under sustained load, with no metadata dropped" [VERIFIED: `.planning/REQUIREMENTS.md:32`] | § *OQ-R1* (bucket edges that let the target fail); § *OQ-R7* (marker registration and the default-selection blast radius); § *State of the Art* (Python 3.13 made `time.monotonic` usable on Windows — the old advice is obsolete and the reason is version-specific) |

**Also touched, and to be stated rather than ticked:**

- **CL-11** is filed under Phase 1 / Pending [VERIFIED: `.planning/REQUIREMENTS.md:176`] while both clauses
  are built and green — clause 1 by `tests/unit/test_unknown_usage_never_zero.py` (Phase 1), clause 2 by
  `tests/integration/test_run_totals.py` (Phase 2), where `seams.py:569` records that it built the
  function and deliberately claimed no requirement. CONTEXT's disposition holds: **do not split the id
  and do not remap the row.** This phase re-asserts both clauses from tests it runs itself and carries
  the tick recommendation as a numbered `03-UAT.md` item, exactly as Phase 1 did for CL-08.
- **GATE-11** is CL-01's other half and belongs to Phase 21 [VERIFIED: `.planning/research/PITFALLS.md`,
  failure-mode table]. Nothing here may assume a gateway caller exists.
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

Extracted from `./.claude/CLAUDE.md` and `./CLAUDE.md`. Treat with the same authority as CONTEXT's
locked decisions.

| Directive | Bearing on this phase |
|---|---|
| Python 3.13.x pinned | Load-bearing twice, and both are gifts rather than constraints: `asyncio.Queue.shutdown()` / `QueueShutDown` exist (new in 3.13) and are exactly D-31's primitive; `time.monotonic()` on Windows moved to `QueryPerformanceCounter` in 3.13, so the classic 15.6 ms-resolution trap that would have wrecked CL-12's measurement on this host is gone |
| SQLAlchemy 2.0 async over asyncpg; **Alembic carries RLS policies, constraints, grants** | D-33's move from `text()` to `postgresql.insert()` is a change of construct on tables `models.py` already declares. **No migration is required by any locked decision** — Pitfall 12 is the one candidate for a `0005`, and it is a decision for the planner, not an inevitability |
| PostgreSQL 17, RLS deny-by-default, `SET LOCAL app.workspace_id` | The fallback inherits `workspace_transaction` unchanged (ADR-0035). D-43's per-workspace loop exists *because* an unscoped read is zero rows, not an error |
| **RabbitMQ 4.x, exactly one queue plus its DLQ. A second broker queue was rejected twice** | D-42 reads depth from the two queues that exist. Nothing here declares a third |
| call-ledger is a SINK: forbidden edge call-ledger → anything | `ObservedWorkspaces` stays the enumerator; a fifth `SECURITY DEFINER` function is refused outright, and a test asserts the sanctioned set is exactly four |
| History rows are never deleted at the database privilege level | Untouched. `price_table` keeps `SELECT, INSERT`; nothing in this phase asks for more |
| Bounded metric label cardinality (ADR-0030) | Eighteen metrics ship. **ADR-0030's text is more permissive than `observability.py`'s docstring** — the ADR permits `model_name` and `workspace_id` "at pilot scale"; the module docstring says `workspace_id` is "deliberately never a label". The gap matters to D-43 and to OQ-023 and is named in § *OQ-R4* |
| Refusal shapes carry security weight | `check_spend_ceiling` still returns no figure under any branch, including the two branches that gain a counter increment in this phase |
| **Do not edit `docs/`** | Five known conflicts become `OQ-022`…`OQ-026`. A sixth is identified in Pitfall 12 and has **no allocated id** — see § *Metadata* for how to route it |
| **GSD workflow enforcement** | Applies to execution, not to this document |

---

## Summary

Phase 2 built the write path and wrote its own gap into three docstrings. Phase 3 closes it, and the
work divides into four tracks whose files barely overlap, which is what makes a wave plan possible:
(1) `writer.py`'s statement rewrite and the counters that fall out of it; (2) `enqueue.py` + a new
`fallback.py` + `app.py`'s composition; (3) `observability.py`'s eighteen metrics, the `/metrics`
route, the depth-gauge job in `worker.py`, and the alert-rules file; (4) the three-layer no-read-path
sweep and the load/chaos suites.

**The single most important finding is a correctness trap in track 1, and it was found by provoking
the installed SQLAlchemy rather than by reading documentation.** D-33's statement —
`INSERT … ON CONFLICT (call_id) DO NOTHING … RETURNING call_id`, executed with a list of parameter
dicts — is exactly the shape SQLAlchemy's `insertmanyvalues` handles, **provided
`sort_by_parameter_order` is left off.** Turn it on and SQLAlchemy picks `call_id` as a client-side
sentinel column [VERIFIED, provoked this session: `stmt.compile(...).._insertmanyvalues` reports
`sentinel_columns=(Column('call_id', …),), num_sentinel_columns=1`], and then, on the first redelivery
where any row conflicts, raises:

> `Sentinel-keyed result set did not produce correct number of rows {n}; produced {m}. Please ensure the
> sentinel column is fully unique and populated in all cases.`
> [VERIFIED: `.venv/Lib/site-packages/sqlalchemy/engine/default.py:908-918`]

That is CL-02's *exact* scenario turned into an exception, on a path whose whole job is to survive it.
The correct shape needs no ordering at all, because the returned `call_id`s are used as a **set** — the
month buckets are built from set membership, not from positional correspondence — which is why D-33
says `RETURNING call_id` and not `RETURNING` an index. Write the plan so the absence of
`sort_by_parameter_order` is a *stated* property with a comment at the statement, not an accident of
not having typed it.

The second finding is structural rather than a bug, and it is the one that limits what this phase can
honestly claim. **`prometheus_client`'s registry is per process**, `worker` serves no HTTP by D-17, and
D-17 is derived from ADR-0028. So of the eighteen metrics, eight exist only in `worker`, four are
partial in `app`, and three of the six declared alerts read metrics on that list. CONTEXT already
routes this to OQ-026; what research adds is the exact `/metrics` shape that keeps the phase's other
claims true — **a plain FastAPI route, never `app.mount(make_asgi_app())`**, because
`assembled_routes()` appends only objects carrying a `dependant` [VERIFIED:
`src/prope/session_auth.py:265-271`] and a `Mount` carries none, and because the library's own issue
tracker records that mounting at `/metrics` actually serves `/metrics/` with a 307 in front of it
[CITED: prometheus/client_python#1016]. A route AC-10's table cannot see is precisely the shape AC-10
exists to refuse.

The third finding is a hole in the no-read-path claim that no layer of D-38's sweep reaches.
`prope_report` is created `LOGIN BYPASSRLS` [VERIFIED: `alembic/versions/0001_roles_and_schemas.py:47`]
and `grant_table`'s `report_select` default gave it `SELECT` on `ledger.call_body` in the revision that
created the table [VERIFIED: `alembic/ddl.py:103, 122-123`; `alembic/versions/0003_ledger_tables.py:252`].
**One statement on that credential reads every stored body in every workspace.** AC-10 is written about
routes, parameters and functions and does not reach it; `security_requirements`' first clause — *"no
endpoint, no export, no admin viewer, and no join from another module's query"* — arguably does. This
is the sharpened form of the `prope_report` item carried forward unresolved from Phases 1 and 2, and it
is the one thing in this phase that would need a migration.

**Primary recommendation:** rewrite `write_records` around `postgresql.insert(...).on_conflict_do_nothing(
index_elements=["call_id"]).returning(call_record.c.call_id)` with `sort_by_parameter_order` deliberately
absent and commented; put the fallback behind an injected `FallbackWriter` bound in `app.py`'s lifespan
and drain the handoff on stop with `asyncio.Queue.shutdown()`; expose `/metrics` as a plain `APIRoute`
returning `generate_latest(REGISTRY)` under `CONTENT_TYPE_PLAIN_0_0_4` (**not** `CONTENT_TYPE_LATEST`,
which in 0.26.0 declares a format version `generate_latest` does not emit); give the two latency
histograms explicit bucket edges that bracket their own targets; and route the `prope_report` /
`call_body` grant to a decision rather than leaving it as the thing nobody looked at.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Body size cap, `occurred_at` stamp, enqueue timing | **API / Backend (`app`), caller's span** | — | D-29, D-41, CL-12. All three are inside the 1 ms budget and all three are measured by the histogram they sit beside |
| Publish → confirm → **fallback** | **API / Backend (`app`), background job** | Database | D-26. The fallback is the one place `app` writes to PostgreSQL outside the management routes (ADR-0041 names this consequence) |
| Handoff drain on stop | **API / Backend (`app`)** | Database | D-31. `asyncio.Queue.shutdown()` closes the door; the fallback empties the room |
| Idempotent upsert, duplicate count, missing-version-id refusal | **Database + `write_records`** | — | D-33, D-35, D-40. One implementation, three callers, and the counters live where the callers cannot forget them |
| Redelivery count | **Worker (`worker`), drain** | Broker | D-35. `AbstractIncomingMessage.redelivered` is the broker's own view and only the consumer sees it |
| Queue and DLQ depth | **Worker (`worker`), third supervised job** | Broker | D-42. Separate from the drain precisely so a wedged drain does not silence its own backlog gauge |
| Oldest-body age | **Worker (`worker`), inside the retention enumeration** | Database | D-43. One indexed read per enumerated workspace; ADR-0045 is why it cannot be one query |
| `/metrics` exposition | **API / Backend (`app`) only** | — | D-39 + D-17. `worker` serves no HTTP, and that is derived from ADR-0028 rather than chosen |
| Alert rules | **Repository artifact + a test** | — | D-44. PITFALLS §4: the deployment stack owns no milestone, so the file has no consumer and the test is its only reader |
| No-read-path proof | **Tests, three layers** | Database (grant matrix) | D-38 + Pitfall 12. The route table, the internal Python surface, and the grants — and one credential none of the three reaches |

---

## Standard Stack

### There is no new package. This is the whole dependency finding.

Every capability this phase needs is already pinned in `pyproject.toml` and already resolved in
`uv.lock`. **No `uv add` is required for any locked decision.** Stated plainly because the alternative —
padding a dependency section — would hide the one genuine dependency question, which is PyYAML and is
below.

| Library | Version | Already pinned | What this phase newly leans on it for |
|---------|---------|---------------|----------------------------------------|
| `sqlalchemy[asyncio]` | **2.0.51** | `pyproject.toml:10` | `sqlalchemy.dialects.postgresql.insert()`, `.on_conflict_do_nothing()`, `.returning()` and the `insertmanyvalues` machinery underneath. D-33's whole statement. See **Pitfall 1** |
| `asyncpg` | 0.31.0 | `pyproject.toml:11` | Unchanged. It is the dialect whose `use_insertmanyvalues=True` and `insertmanyvalues_page_size=1000` make the batch a single round trip [VERIFIED, this session: `postgresql.dialect()` reports both] |
| `prometheus-client` | **0.26.0** | `pyproject.toml:29` | Fourteen new metric objects, `generate_latest`, `CONTENT_TYPE_PLAIN_0_0_4`, and the `Histogram(buckets=…)` argument. See **Pitfall 6** and **Pitfall 8** |
| `aio-pika` | 9.6.2 | `pyproject.toml:44` | `channel.declare_queue(name, passive=True)` → `queue.declaration_result.message_count`, for D-42. See **Pitfall 10** |
| `fastapi` | 0.141.1 | `pyproject.toml:21` | One more route. `assembled_routes()` already exists for it (Broken Window #4) |
| `structlog` | 26.1.0 | `pyproject.toml:28` | Two new log lines (the shutdown remainder, the oversize drop). No new field outside `LOGGABLE_FIELDS` |
| `pydantic` | 2.13.4 | `pyproject.toml:19` | `Field(le=3650)` for D-37 |
| `testcontainers[postgresql,rabbitmq]` | 4.15.0 | dev group | Unchanged. D-45 explicitly does **not** add a second broker container |

### The one dependency question: PyYAML for D-44's rules-file test

D-44 ships a Prometheus rules file and a test that parses it. Parsing it needs a YAML reader.

**PyYAML 6.0.3 is already resolved and importable** [VERIFIED: `uv.lock:580`; `import yaml` succeeds in
the project venv] — **but only as a transitive extra of `uvicorn[standard]`** [VERIFIED: `uv.lock:746-753`,
`[package.optional-dependencies] standard = [… { name = "pyyaml" } …]`]. That is a real distinction, not
pedantry: `uvicorn[standard]`'s extra list is uvicorn's to change, and a test that imports `yaml` without
declaring it is a test that breaks on an unrelated upgrade, in a file whose whole purpose is to stop
another file from rotting.

Three options, in order of preference:

1. **Declare `pyyaml==6.0.3` in the dev group.** One line, pins the version already resolved, and makes
   the test's dependency visible where a reader looks for it. It adds nothing to `uv.lock` that is not
   there. **Recommended.**
2. **Import `yaml` and rely on the transitive.** Zero edits and works today. The cost is a silent
   coupling between a test about alert rules and a web server's extras list.
3. **Write the rules file as YAML and validate it without a YAML parser** — a line-oriented reader that
   extracts `expr:` values by regex. Rejected: a hand-rolled parser for a format with a specification is
   the exact "don't hand-roll" the table below is about, and it would pass on a file Prometheus rejects.

> **What the test can and cannot claim.** Parsing with PyYAML proves the file is *well-formed YAML* and
> lets the test extract every metric name an `expr` mentions. It does **not** prove the file is a valid
> Prometheus rules file, and it does not prove a PromQL expression parses — that is `promtool check rules`,
> which needs a Prometheus binary this repository does not have and PITFALLS §4 gives no home to. State
> the boundary at the test: *this asserts every metric named by a rule exists in the registry*, which is
> the rot D-44 is actually shaped against, and nothing more.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| A plain `APIRoute` for `/metrics` | `app.mount("/metrics", make_asgi_app())` | The documented pattern, and it handles content negotiation for free. **Rejected**: a `Mount` carries no `dependant`, so `assembled_routes()` skips it [VERIFIED: `session_auth.py:265-271`] and it appears in neither the route-table assertion nor the OpenAPI walk; and it serves `/metrics/` with a 307 on `/metrics` [CITED: prometheus/client_python#1016]. Both halves make it the shape AC-10 exists to refuse |
| Explicit histogram buckets | `prometheus_client`'s defaults | Defaults are `(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, inf)` [VERIFIED, this session: `Histogram.DEFAULT_BUCKETS`]. The first edge is 5× the enqueue target and the last is 3× *below* `LedgerWriteLagHigh`'s threshold. Unusable at both ends |
| `INSERT … ON CONFLICT DO NOTHING RETURNING` | `INSERT … ON CONFLICT DO UPDATE` | Absorbs both duplicate shapes in one clause and needs no `RETURNING` gymnastics. **Rejected by D-33 on three grounds**, and PostgreSQL adds a fourth the ADRs did not need to: `DO UPDATE` requires `UPDATE` privilege on the table [CITED: postgresql.org/docs/17/sql-insert], which `prope_app` does not hold on `ledger.call_body` |
| Set membership from `RETURNING call_id` | `sort_by_parameter_order=True` and positional correspondence | Would let the code index the result. **Rejected — it raises.** See Pitfall 1 |
| `asyncio.Queue.shutdown()` | A `get_nowait()` loop until `QueueEmpty` | Works, and is what a pre-3.13 codebase would write. **Rejected**: it leaves the door open — between `stopping.set()` and the last `get_nowait()`, `enqueue()` can still `put_nowait` a record that will never be published, and nothing counts it. `shutdown()` closes puts and drains gets in one call, which is CR-02's actual shape |
| A separate depth-gauge job | Reading depth inside the drain's window loop | No new job. **Rejected by D-42**, and the reason is worth restating as a property rather than a preference: the gauge and its subject would share a failure |
| `min(created_at)` for the age gauge | `min(expires_at)` | Both are indexed — `ix_call_body_workspace_id_created_at` and `ix_call_body_workspace_id_expires_at` both exist [VERIFIED: `alembic/versions/0003_ledger_tables.py:205-213`] — so the choice is semantic, not a performance question. See § *OQ-R4* |

**Installation:** nothing, unless the planner takes option 1 above:

```bash
uv add --dev "pyyaml==6.0.3"   # optional; the version already resolved via uvicorn[standard]
```

---

## Package Legitimacy Audit

> **This is an agent judgement, not a detector result.** Phase 1–2 artifacts cite
> `gsd-tools query package-legitimacy check`; that binary does not exist in this environment
> (ORCHESTRATION §0). What follows is the same audit performed by hand against PyPI metadata and the
> installed artifacts, and it is labelled as such. **No detector output is reproduced or invented.**

**Only one package is even a candidate, and it is a maybe.** Every other library this phase uses is
already pinned, already audited in `02-RESEARCH.md` § Package Legitimacy Audit, and already in
`uv.lock` at the same version.

| Package | Registry | Age / cadence | Downloads | Source repo | Judgement | Disposition |
|---------|----------|---------------|-----------|-------------|-----------|-------------|
| `pyyaml` | PyPI | 6.0.3 uploaded 2025-09-25 [VERIFIED: `uv.lock:582`, `upload-time`]; the project dates to 2006 and is the reference Python YAML implementation | not observable — see below | github.com/yaml/pyyaml | **Legitimate.** Not a typosquat: the name is the canonical one, the wheels in `uv.lock` carry `cp313` ABI tags for every platform this project targets, and it arrives here as `uvicorn[standard]`'s own declared extra rather than as something a search result suggested | **Approved, dev-only if declared at all.** If the planner takes option 2 (rely on the transitive) nothing is added to the lock file and there is nothing to audit; option 1 pins a version already present |

**Packages removed on a [SLOP]-equivalent judgement:** none.
**Packages I would have flagged and did not:** none.

**On the download signal, and why its absence carries no information.** `02-RESEARCH.md` recorded that
every PyPI package returns `null` for downloads because the PyPI JSON API exposes no download counter,
so a "SUS: unknown-downloads" verdict fires universally and distinguishes nothing. That is still true
and I did not treat it as evidence in either direction. **Apply the same scepticism to my own signals
here:** "the project dates to 2006" is an argument about a *name*, not about the artifact that was
resolved, and the thing that actually protects this repository is `uv.lock`'s per-wheel `sha256` — which
is checked on install and is the only claim in this table a machine verifies. No package in this phase
ships a build hook or a `setup.py` executed at install time; all of them install from wheels.

**No `checkpoint:human-verify` task is warranted.** The one candidate is a transitive dependency of a
package the project already runs in production, at the version already resolved.

---

## Architecture Patterns

### System Architecture Diagram

Deltas from Phase 2 marked `◄NEW`.

```
                     ┌──────────────────────── process: app (uvicorn) ─────────────────────────────┐
                     │                                                                             │
 gateway (Ph.19-21)─►│ enqueue(record)                                                             │
 [no caller yet]     │  ├─ size the body: len(req)+len(resp) > 256 KiB ► body=None,        ◄NEW D-29│
                     │  │    body_dropped_total{reason=<OQ-022>}, byte_size overwritten             │
                     │  ├─ occurred_at = now()                                            ◄NEW D-41│
                     │  ├─ perf_counter around the span ► enqueue_duration_seconds{source} ◄NEW     │
                     │  └─ put_nowait((draft, occurred_at))                                        │
                     │        ├─ QueueFull      ► metadata_dropped + enqueued{dropped}             │
                     │        └─ QueueShutDown  ► metadata_dropped + enqueued{dropped}    ◄NEW D-31│
                     │                                    │                                        │
                     │   supervise({publisher: …})  ◄NEW D-32   bounded handoff (512)               │
                     │            │                             │                                  │
                     │            ▼  run_publisher(exchange, stopping, *, fallback)  ◄NEW D-26      │
                     │      publish(persistent, mandatory, confirm)                                │
                     │            ├─ Basic.Ack ─────────────────────────────► done                 │
                     │            ├─ PublishError  ► publish_failed{unroutable} ┐                  │
                     │            ├─ DeliveryError ► publish_failed{nacked}     ├─► fallback(rec)  │
                     │            ├─ TimeoutError  ► publish_failed{timeout}    │   ◄NEW, 4 sites  │
                     │            └─ Exception (dead channel / no broker) ──────┘                  │
                     │                                                     │                       │
                     │   on stopping: handoff().shutdown(); drain to        │ fallback.py  ◄NEW    │
                     │   deadline; count the remainder  ◄NEW D-31           │ body=None (D-28)     │
                     │                                                     │ one record,          │
                     │  GET /healthz   GET /readyz (database alone, D-16)  │ one transaction      │
                     │  GET /metrics   ◄NEW D-39 — plain APIRoute, NOT a Mount (Pitfall 7)         │
                     └──────────┬──────────────────────────────────────────┼───────────────────────┘
                                │                                          │
                                ▼                                          │
              ┌──────── RabbitMQ 4.x (unchanged, D-23) ────────┐            │
              │ prope.call_record   ◄── depth read passively   │            │
              │ prope.call_record.dlq ◄── depth read passively │            │
              └──────────┬────────────────────────────▲────────┘            │
                         │ prefetch = 500             │ passive declare     │
      ┌──────────────────┼─────── process: worker ────┼─────────────────┐   │
      │  supervise({drain, retention, depth_gauges})  │      ◄NEW D-42  │   │
      │    ├─ drain: window ► group ► write_records   │                 │   │
      │    │    redelivered_total ◄NEW D-35           │                 │   │
      │    │    metadata_dropped increments REMOVED ◄NEW D-30           │   │
      │    ├─ retention sweep + oldest_body_age_seconds ◄NEW D-43       │   │
      │    └─ depth job: queue_depth, dlq_depth every 15 s ─────────────┘   │
      │           (message_count = READY only — Pitfall 10)              │   │
      └───────────────────────────┬──────────────────────────────────────┘   │
                                  ▼                                          ▼
                    ┌──────────────── PostgreSQL 17 (RLS) ─────────────────────┐
                    │ write_records:                                           │
                    │   INSERT … ON CONFLICT (call_id) DO NOTHING              │
                    │        RETURNING call_id     ◄NEW D-33                   │
                    │   ── NO sort_by_parameter_order (Pitfall 1) ──           │
                    │   months built from the RETURNED set  ◄NEW               │
                    │   body rows filtered by the RETURNED set ◄NEW D-34       │
                    │   duplicate_call_id_total = offered − returned ◄NEW D-35 │
                    └──────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/prope/
├── app.py                  # EDIT. bind FallbackWriter; supervise the publisher (D-32);
│                           #       GET /metrics as a plain route (D-39)
├── worker.py               # EDIT. third supervised job + its name constant (D-42);
│                           #       oldest_body_age_seconds inside the sweep (D-43)
├── observability.py        # REWRITE. 18 metrics, corrected docstring, LOGGABLE_FIELDS unchanged
├── supervisor.py           # unchanged — D-14 built it for exactly this
└── call_ledger/
    ├── fallback.py         # NEW. FallbackWriter type + build_fallback_writer(sessionmaker)
    ├── enqueue.py          # EDIT. size cap (D-29), occurred_at (D-41), fallback arg (D-26),
    │                       #       shutdown drain (D-31), enqueue_duration_seconds
    ├── writer.py           # EDIT. the statement rewrite (D-33/34/35/40). The largest single diff
    ├── drain.py            # EDIT. redelivered_total; remove two metadata_dropped increments (D-30);
    │                       #       rewrite classify_write_failure's IntegrityError docstring (D-36)
    ├── seams.py            # EDIT. ceiling_check_total{result} on all three branches (D-40)
    ├── schemas.py          # EDIT. retention_days: int = Field(le=3650) (D-37)
    └── models.py domain.py pricing.py repricing.py retention.py retention_settings.py api.py envelope.py
                            # unchanged
deploy/
└── prometheus/rules/call_ledger.rules.yml   # NEW. D-44's six rules
tests/
├── conftest.py             # EDIT only if a fallback fixture is shared; reset_handoff already exists
├── broker/                 # EDIT. 7 call sites gain a fallback argument (D-26's stated churn)
├── chaos/                  # NEW. closed channel, closed port, redelivery after unacked restart
├── load/                   # NEW. the CI-resident proxy + the marked full-fat run
├── security/               # EXTEND. the three-layer no-read-path sweep
└── architecture/           # EDIT. EXPECTED_ROUTES 7 → 8; the alert-rules-vs-registry test
```

> **`EXPECTED_ABSENT_SCHEMAS` is untouched** — this phase creates no schema, so `tests/architecture/
> test_tenant_coverage.py` needs no edit and Phase 7 is still the first that must shrink it.

### Pattern 1: The injected fallback, bound once at the composition root (D-26)

```python
# src/prope/call_ledger/fallback.py  — NEW
from collections.abc import Awaitable, Callable
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.domain import CallRecordDraft
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from prope.observability import (
    body_dropped_total, fallback_direct_write_total, metadata_dropped_total,
)

#: What a fallback must look like: awaited with the record that failed to publish.
#: NEVER raises — INT-018's contract reaches this far, because this runs inside the
#: publisher task whose death is what D-32 exists to notice.
FallbackWriter = Callable[[CallRecordDraft], Awaitable[None]]


def build_fallback_writer(sessionmaker: async_sessionmaker[AsyncSession]) -> FallbackWriter:
    """ADR-0041's inline direct write. One record, one transaction (D-27)."""

    async def write_directly(record: CallRecordDraft) -> None:
        # D-28: metadata only. Rewritten to body=None BEFORE it reaches write_records,
        # which is what keeps D-11's promise structural: expires_at is stamped only on
        # a call_body row, so this path never consults ledger.workspace_retention and
        # write_records' retention_window default is never exercised here.
        had_body = record.body is not None
        metadata_only = replace(record, body=None) if had_body else record
        try:
            async with workspace_transaction(sessionmaker, metadata_only.workspace_id) as session:
                await write_records(session, [metadata_only])
        except Exception:
            # Broker gone AND database gone. This is the event ADR-0041 says
            # metadata_dropped_total now means, and the only page in the module.
            metadata_dropped_total.inc()
            log.warning("call_ledger.fallback_failed", call_id=record.call_id,
                        workspace_id=record.workspace_id, reason="fallback_refused")
            return
        fallback_direct_write_total.inc()
        if had_body:
            body_dropped_total.labels(reason=BODY_DROP_REASON_FALLBACK).inc()   # OQ-022

    return write_directly
```

**`replace()` rather than mutation**: `CallRecordDraft` and `CallBodyDraft` are both
`@dataclass(frozen=True, slots=True)` [VERIFIED: `src/prope/call_ledger/domain.py:100, 113`], so
`record.body = None` raises `FrozenInstanceError`. The same applies to D-29's `byte_size` overwrite.

**Anti-pattern this replaces:** importing `workspace_transaction` into `enqueue.py`. D-26 rejects it by
name and the reason is a property of the module rather than taste — `enqueue.py`'s contract is *never
raises, never blocks*, and the next reader of a file that already imports a session factory is one line
from putting a write on the caller's span.

### Pattern 2: The restructured `write_records` (D-33, D-34, D-35, D-40)

The loop stays; what moves is *when the aggregate is computed*. Today the month buckets accumulate
inside the per-draft loop [VERIFIED: `src/prope/call_ledger/writer.py:338-351`] and the insert happens
after [VERIFIED: `writer.py:355-357`]. D-33 inverts that.

```python
# src/prope/call_ledger/writer.py — the shape, not the whole function
from sqlalchemy.dialects.postgresql import insert as pg_insert
from prope.call_ledger import models

#: D-33. `sort_by_parameter_order` is DELIBERATELY ABSENT and this comment is the
#: reason: with it, SQLAlchemy selects `call_id` as a client-side sentinel and then
#: raises InvalidRequestError the first time ON CONFLICT skips a row — which is
#: CL-02's own scenario. The returned ids are used as a SET, never positionally,
#: so no ordering is needed and asking for one is strictly harmful.
UPSERT_CALL_RECORD = (
    pg_insert(models.call_record)
    .on_conflict_do_nothing(index_elements=["call_id"])
    .returning(models.call_record.c.call_id)
)

UPSERT_CALL_BODY = pg_insert(models.call_body).on_conflict_do_nothing(index_elements=["call_id"])

async def write_records(session, records, *, retention_window=DEFAULT_RETENTION_WINDOW):
    ...
    # PASS 1 — unchanged: price each draft, refuse what the encoding cannot represent.
    #   The workspace check, the eval-body check, the zero-cost check and the
    #   mixed-currency check all stay HERE, over the WHOLE batch (Pitfall 2).
    #   NEW (D-40): a source=gateway draft with version_id None is refused here,
    #   incrementing missing_version_id_total, instead of dying as an IntegrityError
    #   under ck_call_record_gateway_calls_carry_version_id.

    inserted = set(
        (await session.execute(UPSERT_CALL_RECORD, record_rows)).scalars().all()
    )
    duplicates = len(record_rows) - len(inserted)
    if duplicates:
        duplicate_call_id_total.inc(duplicates)          # D-35

    # PASS 2 — NEW: the aggregate is built from what actually inserted.
    months: dict[date, dict] = {}
    for draft, priced in per_draft:                       # priced carries cost/currency
        if draft.call_id not in inserted:
            continue
        bucket = months.setdefault(period_month(draft.created_at), _empty_bucket())
        bucket["call_count"] += 1
        ...

    # D-34: a body follows its record. Filtered by the same set, with its own
    # DO NOTHING because prope_app holds no UPDATE on ledger.call_body.
    surviving_bodies = [row for row in body_rows if row["call_id"] in inserted]
    if surviving_bodies:
        await session.execute(UPSERT_CALL_BODY, surviving_bodies)

    # The workspace_spend upsert is UNCHANGED — including its ON CONFLICT … WHERE
    # currency invariant (T-02-13). Only its inputs moved.
```

**Why the returned set is the whole point.** `ledger.call_record`'s primary key is `call_id` alone
[VERIFIED: `alembic/versions/0002_call_record.py:90`], so a second row was already impossible. What a
redelivery corrupts is `ledger.workspace_spend`, maintained inside this transaction (A-103). A plan that
stops at `ON CONFLICT DO NOTHING` passes a "the record appears once" test and still fails CL-02 —
CONTEXT § Specific Ideas says exactly this and it is worth repeating at the code.

**Why `WriteResult` gains a fifth field.** `duplicates` is what the drain, the fallback and
`price_usage` all need to know without re-querying. The dataclass already carries four counts
[VERIFIED: `src/prope/call_ledger/domain.py:195-198`; `writer.py:403-408`], and
`tests/integration/test_write_path.py:366` (`test_write_records_returns_counts_that_match_what_landed`)
is the test that must grow with it.

### Pattern 3: Draining the handoff on stop with `asyncio.Queue.shutdown()` (D-31, CR-02)

Python 3.13 added `Queue.shutdown()` and `QueueShutDown` [CITED: docs.python.org/3/whatsnew/3.13.html —
*"Add `Queue.shutdown` and `QueueShutDown` to manage queue termination"*], and the semantics are exactly
CR-02's shape: `shutdown(immediate=False)` makes **`put` raise at once** and lets **`get` keep returning
until the queue is empty**, then raise [VERIFIED, this session: `asyncio.Queue.shutdown.__doc__`].

```python
# src/prope/call_ledger/enqueue.py

#: D-31's deadline, DERIVED rather than chosen independently — see app.PUBLISHER_STOP_TIMEOUT_SECONDS.
#: Worst case is a full handoff (512) written one record at a time through the fallback at ~1.5 ms
#: each ≈ 0.77 s (D-27's arithmetic). 3.0 s is ~4x that, and it leaves 2.0 s of margin under the
#: outer wait so the counting below actually runs before app.py cancels this task.
HANDOFF_DRAIN_DEADLINE_SECONDS = 3.0

async def run_publisher(exchange, stopping, *, fallback: FallbackWriter) -> None:
    queue = handoff()
    while not stopping.is_set():
        try:
            item = await asyncio.wait_for(queue.get(), timeout=0.1)
        except TimeoutError:
            continue
        try:
            if not await publish_record(exchange, item, fallback=fallback):
                pass          # publish_record already fell back and counted
        finally:
            queue.task_done()

    # ── stopping is set. Close the door, then empty the room. ──
    queue.shutdown()          # every later enqueue() put_nowait raises QueueShutDown
    deadline = asyncio.get_running_loop().time() + HANDOFF_DRAIN_DEADLINE_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        try:
            item = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        except asyncio.QueueShutDown:
            break
        try:
            await publish_record(exchange, item, fallback=fallback)
        finally:
            queue.task_done()

    remaining = queue.qsize()
    if remaining:
        metadata_dropped_total.inc(remaining)
        log.warning("call_ledger.handoff_abandoned", reason="stop_deadline", group_size=remaining)
```

> **`shutdown()` closes a hole the counting alone would leave open.** Without it, every record
> `enqueue()` accepts between `stopping.set()` and the publisher's last `get` is a record that will
> never be published *and* is not in the remainder count, because it arrived after the count. With it,
> `put_nowait` raises `QueueShutDown` and the drop is counted at the enqueue site where it happens.
> **This requires a new `except` branch in `enqueue()`** — `QueueShutDown` derives from `Exception`, so
> today it lands in the bare handler and logs `reason="handoff_failed"`, which reads as a bug rather
> than as a deploy. Give it `reason="shutting_down"` and its own line.

### Pattern 4: The publisher as a supervised job (D-32)

`supervise()` takes `Mapping[str, Job]` where `Job = Callable[[], Awaitable[None]]`
[VERIFIED: `src/prope/supervisor.py:83, 185-209`], and `app.py` already builds a `stopping` event
[VERIFIED: `app.py:178-180`]. The change is small and the trap is in the shutdown ordering.

```python
# src/prope/app.py — inside _start_publisher
JOB_CALL_RECORD_PUBLISHER = "call_record_publisher"   # a LOGGABLE_FIELDS `job` value; closed set

fallback = build_fallback_writer(application.state.sessionmaker)

async def publisher_job() -> None:
    await run_publisher(channel.default_exchange, stopping, fallback=fallback)

application.state.publisher = asyncio.create_task(
    supervise({JOB_CALL_RECORD_PUBLISHER: publisher_job}, stopping)
)
```

**Three consequences to write down rather than discover:**

1. `supervise()` returns only when every job has returned, and `run_with_restart` restarts a job that
   returns cleanly [VERIFIED: `supervisor.py:160-182` — `else: delay = base; await asyncio.sleep(0)`].
   `run_publisher` returns only when `stopping` is set, so the outer `while not stopping.is_set()` in
   `run_with_restart` ends the loop immediately. That is correct **only because** `run_publisher`
   observes the same event. A future `run_publisher` that returned for any other reason would be
   restarted in a tight loop with the handoff already shut down.
2. **`queue.shutdown()` is one-way for the process.** If the supervisor *did* restart the publisher, the
   restarted one would call `handoff()` and get the shut-down queue back, because `handoff()` caches in
   a module global and only `reset_handoff()` clears it [VERIFIED: `enqueue.py:76-100`]. So the drain
   block above must run at most once per process. Guard it on `stopping.is_set()` — which it already is —
   and say so at the code.
3. `PUBLISHER_STOP_TIMEOUT_SECONDS` now waits on a `supervise()` task rather than on `run_publisher`
   directly. The existing `_stop_publisher` shape (`wait_for` then `cancel`) still works, and
   `run_with_restart` re-raises `CancelledError` untouched [VERIFIED: `supervisor.py:163-164`], so a
   cancel does what it says.

### Pattern 5: `/metrics` as a plain route, not a mount (D-39)

```python
# src/prope/app.py — the eighth path
from prometheus_client import CONTENT_TYPE_PLAIN_0_0_4, REGISTRY, generate_latest
from fastapi import Response

@application.get("/metrics", response_class=Response, include_in_schema=True)
async def metrics() -> Response:
    """Prometheus exposition. Unversioned, sessionless — a scraper holds no session.

    **A plain route rather than `app.mount(make_asgi_app())`, and that is not style.**
    A Mount carries no `dependant`, so `prope.session_auth.assembled_routes` skips it
    entirely — the route would be served and invisible to every assertion in
    `tests/architecture/test_route_table.py`, which is exactly the shape AC-10 exists
    to refuse. It would also serve `/metrics/` and 307 from `/metrics`.

    **CONTENT_TYPE_PLAIN_0_0_4, not CONTENT_TYPE_LATEST.** In prometheus-client 0.26.0
    `CONTENT_TYPE_LATEST` is `text/plain; version=1.0.0`, while `generate_latest`
    emits the 0.0.4 text format — the library's own `choose_encoder` pairs this
    function with `CONTENT_TYPE_PLAIN_0_0_4`. Labelling the payload 1.0.0 would be a
    claim about the format that the payload does not honour.
    """
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_PLAIN_0_0_4)
```

The route-table edits that follow, all in `tests/architecture/test_route_table.py`:

| Assertion | Today | After |
|---|---|---|
| `EXPECTED_ROUTES` | 7 entries (`:51-61`) | 8 — add `("GET", "/metrics")` |
| `UNVERSIONED` | `{"/healthz", "/readyz"}` (`:65`) | add `"/metrics"` |
| `test_the_health_routes_are_unversioned_and_declare_nothing` (`:162`) | iterates `UNVERSIONED` | unchanged in shape; now covers three paths and asserts `/metrics` declares no session and no action |
| `test_no_route_is_reachable_except_through_the_application` (`:343`) | `len(paths) == len(EXPECTED_ROUTES)` | unchanged; the count moves with the frozenset |
| `test_the_openapi_schema_agrees_with_the_route_table` (`:103`) | 7 documented paths | 8. **`include_in_schema=True` is load-bearing** — excluding it would make the served table and the schema disagree, which is the exact hole `:107-109` says it exists to close |
| `test_no_schema_property_or_parameter_exposes_a_stored_body` (`:178`) | walks components + parameters | unchanged; a `Response` return contributes no component schema |

### Pattern 6: The three-layer absence proof (D-38)

```python
# tests/security/test_no_body_read_path.py — AC-10's full claim, three layers

# LAYER 1 — the assembled HTTP surface. Already asserted in Phase 2's
# tests/architecture/test_route_table.py; this file states the dependency rather
# than duplicating it, so Phase 23 extends one test and not two.

# LAYER 2 — the internal Python surface. `get_run_totals` is a function, not a
# route: a body returned through a dataclass satisfies every route-table
# assertion in the repository.
def test_no_public_callable_or_model_in_the_module_names_a_body() -> None:
    offenders: list[str] = []
    for module in _walk_package(prope.call_ledger):
        for name, obj in vars(module).items():
            if name.startswith("_"):
                continue
            if inspect.isfunction(obj) or inspect.iscoroutinefunction(obj):
                sig = inspect.signature(obj)
                for parameter in sig.parameters:
                    if parameter.lower() in FORBIDDEN_FIELD_NAMES:
                        offenders.append(f"{module.__name__}.{name}({parameter})")
                offenders += _annotation_offenders(module, name, sig.return_annotation)
            elif dataclasses.is_dataclass(obj) or _is_pydantic_model(obj):
                offenders += [f"{module.__name__}.{name}.{f}"
                              for f in _field_names(obj) if f.lower() in FORBIDDEN_FIELD_NAMES]
    assert offenders == []

# THE POSITIVE CONTROL, which is what stops layer 2 from being vacuous. It is a
# walk over a package, and a walk that imported nothing would pass silently.
def test_the_walk_would_have_found_one() -> None:
    assert "response_body" in _field_names(prope.call_ledger.domain.CallBodyDraft)
    # ^ CallBodyDraft is the WRITE-side input and is expected to name bodies. The
    #   assertion above must therefore exempt it BY NAME, and this test is what
    #   proves the exemption list is doing work rather than swallowing the walk.

# LAYER 3 — the grant matrix, asserted as a source enumeration because the
# database cannot be the guarantee: prope_app holds SELECT on ledger.call_body
# and the retention DELETE needs it (0003_ledger_tables.py:246-252).
def test_only_two_statements_in_src_name_call_body() -> None:
    naming = _grep_src_for("call_body")
    assert naming == {
        "src/prope/call_ledger/writer.py",        # INSERT_CALL_BODY / UPSERT_CALL_BODY
        "src/prope/call_ledger/retention.py",     # the bounded DELETE
        "src/prope/call_ledger/models.py",        # the Table declaration
    }
```

> **Layer 2's exemption list is the whole risk.** `CallBodyDraft` legitimately names
> `request_body`, `response_body` and `byte_size`, and so does `CallBodyPayload` on the envelope. An
> exemption list that grows silently is an assertion that stops asserting. Write the exemptions as a
> literal frozenset with a one-line reason each, and assert its **size** as well as its contents — the
> same posture `EXPECTED_ROUTES` takes.

### Pattern 7: The depth-gauge job (D-42)

`tests/broker/_helpers.py` already contains this exact read, with the channel caveat already written
down:

> *"Its own channel each time: a failed declare closes the channel it was issued on, and a shared one
> would take the next assertion down with it."* [VERIFIED: `tests/broker/_helpers.py`, `queue_depth`]

The production job should adopt that shape rather than invent a second one.

```python
# src/prope/worker.py
JOB_QUEUE_DEPTH_GAUGES = "queue_depth_gauges"      # the third name; LOGGABLE_FIELDS `job` value

#: D-42's interval, argued against the scrape rather than picked. Prometheus's
#: conventional scrape_interval is 15 s; a gauge refreshed less often than the scrape
#: produces a staircase Prometheus cannot smooth, and one refreshed more often burns
#: round trips on samples nothing reads. Cost per pass is two channel-open + passive
#: declare + close cycles, single-digit milliseconds on a compose network.
#:
#: The honest caveat: the scrape interval is a DEPLOYMENT setting and the deployment
#: stack owns no milestone (PITFALLS §4), so this is matched to a convention rather
#: than to a configured value.
DEPTH_GAUGE_INTERVAL_SECONDS = 15.0

async def read_queue_depths(connection: AbstractRobustConnection) -> None:
    """One pass: passive-declare both queues, set both gauges.

    `passive=True` and not a full redeclare. A passive declare checks existence and
    reports the counts WITHOUT comparing arguments, so it can never answer 406
    PRECONDITION_FAILED — which matters because D-23's arguments are one-way and a
    gauge job that could 406 would turn a drift into an outage of the thing that
    would have shown it.

    A fresh channel per queue: a passive declare of a queue that does not exist is a
    channel-level error (aio_pika.exceptions.ChannelNotFoundEntity) and CLOSES the
    channel, so a shared one would take the second read down with the first.
    """
    for queue_name, gauge in ((WORK_QUEUE, queue_depth), (DLQ, dlq_depth)):
        async with connection.channel() as channel:
            queue = await channel.declare_queue(queue_name, passive=True)
            gauge.set(queue.declaration_result.message_count or 0)
```

### Anti-Patterns to Avoid

- **`sort_by_parameter_order=True` on the upsert.** It raises on the first redelivery. Pitfall 1.
- **`DO UPDATE` on either table.** Re-prices against ADR-0019 on `call_record`, and is *refused by the
  engine* on `call_body` — `prope_app` holds no `UPDATE` there and PostgreSQL requires it for
  `DO UPDATE` [CITED: postgresql.org/docs/17/sql-insert].
- **`app.mount("/metrics", make_asgi_app())`.** Invisible to `assembled_routes()`; serves `/metrics/`.
- **`CONTENT_TYPE_LATEST` on a hand-written exposition route.** In 0.26.0 it declares `version=1.0.0`
  and `generate_latest` emits 0.0.4.
- **A single `SELECT min(created_at) FROM ledger.call_body` for the age gauge.** Zero rows under
  ADR-0045, forever, and it reports healthy. D-43 exists because of this.
- **Reading depth inside the drain.** D-42; the gauge and its subject would share one failure.
- **Counting the shutdown remainder without draining it.** D-31; SC1's words are "every drop is counted",
  and a correct counter over a worse product is not the trade.
- **A fifth `SECURITY DEFINER` function** to enumerate workspaces for D-43. Refused outright; a test
  asserts the sanctioned set is exactly four.
- **Adding an `oversize` value to `enqueued_total{outcome}`.** See § *OQ-R8* — it would put two subjects
  in one label.
- **Letting the fallback raise.** It runs inside the publisher task. D-32 would restart the publisher,
  which is better than silence, but the record is still gone and `metadata_dropped_total` is the only
  thing that says so.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Idempotent insert that reports which rows were new | A pre-`SELECT` of existing `call_id`s, then an `INSERT` of the difference | `ON CONFLICT DO NOTHING … RETURNING call_id` | The pre-`SELECT` is a TOCTOU: two drains between the read and the write both think their rows are new. PostgreSQL: *"Only rows that were successfully inserted or updated will be returned"* [CITED: postgresql.org/docs/17/sql-insert] |
| Batched RETURNING over executemany | A loop of single-row `INSERT … RETURNING` | SQLAlchemy's `insertmanyvalues`, which is on by default for asyncpg | `use_insertmanyvalues=True`, `insertmanyvalues_page_size=1000` [VERIFIED, this session] — a 500-record window is one round trip, and a loop would be 500 |
| Closing the handoff on shutdown | A `get_nowait()` loop plus a boolean flag guarding `put_nowait` | `asyncio.Queue.shutdown()` / `QueueShutDown` (Python 3.13) | The flag has a race with the put; `shutdown()` does not. New in 3.13 [CITED: docs.python.org/3/whatsnew/3.13.html] |
| Restart-with-backoff for the publisher | A `while True: try/except` in `run_publisher` | `prope.supervisor.supervise` | D-14 and D-32. It exists, it is tested, and it already handles the interruptible-backoff trap `supervisor.py`'s docstring calls Trap 2 |
| Queue depth | Polling the management HTTP API on an interval | `channel.declare_queue(name, passive=True).declaration_result.message_count` | `_helpers.py`'s own comment: *"the management API's statistics refresh on an interval and a test that read depth from it would be racing a scheduler"*. The same is true of a gauge |
| Prometheus exposition | Formatting the text format yourself | `generate_latest(REGISTRY)` | It handles `_total`/`_created` suffixes, escaping, and `+Inf` bucket ordering. Hand-formatting is how a `# TYPE` line goes missing and a scraper drops a series silently |
| Content negotiation on `/metrics` | Reading the `Accept` header yourself | `prometheus_client.exposition.choose_encoder(accept)` if negotiation is wanted at all | It is the same function `make_asgi_app` uses via `_bake_output` [VERIFIED: `prometheus_client/asgi.py`], and it is what pairs `generate_latest` with the right content type |
| A per-body byte count | Trusting `CallBodyDraft.byte_size` | `len(request.encode()) + len(response.encode())` computed in `enqueue()` | D-29 by name: the field is `int \| None` and caller-supplied, and a cap enforced from a figure the capped party supplies is not a cap |
| Pricing, `expires_at`, the aggregate, the tenant | Anything | `write_records(...)`, `workspace_transaction(...)` | Unchanged from Phase 1 and Phase 2. `writer.py:4-7`: *"There is one implementation of it on purpose"* |
| YAML parsing for the rules file | A regex line reader | `yaml.safe_load` | See § *Standard Stack* — and note what the test can honestly claim |

**Key insight:** this phase writes almost no new *logic*. It writes one statement, one injected
callable, one shutdown block, one route, one interval job, one rules file and a lot of assertions. The
genuinely new decisions are (a) that the aggregate is derived from the returned set, (b) that the
fallback is injected rather than imported, and (c) where the exposition surface lives. Everything else
is composition over things Phases 1 and 2 already built and tested.

---

## Common Pitfalls

### Pitfall 1: `sort_by_parameter_order` turns CL-02's own scenario into an exception

**What goes wrong:** D-33's statement executed with `sort_by_parameter_order=True` on the `returning()`
call raises `sqlalchemy.exc.InvalidRequestError` the first time any row conflicts:

> *"Sentinel-keyed result set did not produce correct number of rows {n}; produced {m}. Please ensure the
> sentinel column is fully unique and populated in all cases."*
> [VERIFIED: `.venv/Lib/site-packages/sqlalchemy/engine/default.py:908-918`, read this session]

**Why it happens:** `call_id` is a client-supplied primary key, so SQLAlchemy selects it as a
**client-side sentinel** when ordering is requested. Provoked directly this session: compiling
`pg_insert(models.call_record).on_conflict_do_nothing(index_elements=["call_id"]).returning(
models.call_record.c.call_id, sort_by_parameter_order=True)` for executemany yields
`_InsertManyValues(sort_by_parameter_order=True, sentinel_columns=(Column('call_id', …),),
num_sentinel_columns=1, implicit_sentinel=False)`. At execution time the driver builds
`rows_by_sentinel` and compares its length to the batch length; `ON CONFLICT DO NOTHING` guarantees they
differ whenever a duplicate arrives, which is precisely the redelivery CL-02 is about.

Without the flag, the same compile yields `sort_by_parameter_order=False, sentinel_columns=None,
num_sentinel_columns=0, includes_upsert_behaviors=True` and the driver takes the `else: result.extend(rows)`
branch [VERIFIED: `default.py:944-945`] — the returned rows are simply concatenated across batches, which
is exactly right for a set.

**How to avoid:** never pass `sort_by_parameter_order` here, and **write a comment at the statement
saying so with this reason**, because the absence of an argument is invisible and somebody adding
ordering "for determinism" would be making a reasonable-looking change that fails only under load.
Assert it, too: a test that writes a five-record batch, re-writes the same five plus two new ones, and
checks `call_count` moved by exactly two is the CL-02 test, and it is also this pitfall's regression test.

**Warning signs:** a redelivery test that passes with one record and fails with five; `InvalidRequestError`
in a drain traceback with the word "Sentinel" in it.

### Pitfall 2: the mixed-currency refusal changes subject if the restructure is done naively

**What goes wrong:** `write_records` refuses a batch that mixes currencies, and the refusal is raised
from inside the month-bucket accumulation [VERIFIED: `src/prope/call_ledger/writer.py:342-351`]. Move
that accumulation after the insert (D-33) and the refusal moves with it — so a batch that mixes
currencies but whose second-currency records are **all duplicates** would now be accepted where it is
refused today. `tests/integration/test_write_path.py:312`
(`test_a_batch_mixing_two_currencies_raises_rather_than_summing`) is the test that would go red or,
worse, stay green while the property quietly changed.

**Why it happens:** one loop is doing two jobs — validating the batch and aggregating it — and only the
second one is about what inserted.

**How to avoid:** **split them.** Keep the currency validation in pass 1, over the whole batch, exactly
where it is; build the month buckets in pass 2, over the inserted subset only. A batch that mixes
currencies is a caller bug whether or not its rows are duplicates, and refusing it whole is the module's
established posture. The cost is one extra iteration over a list already in memory.

### Pitfall 3: `ON CONFLICT DO UPDATE` on `call_body` is refused by the engine, not by a code review

**What goes wrong:** a planner reaching for symmetry writes `DO UPDATE` on both tables and discovers at
runtime that `prope_app` cannot.

**Why it happens:** PostgreSQL: *"If `ON CONFLICT DO UPDATE` is present, `UPDATE` privilege on the table
is also required"*, while *"all forms of `ON CONFLICT` also require `SELECT` privilege on any column
whose values are read"* [CITED: postgresql.org/docs/17/sql-insert]. `prope_app` holds
`SELECT, INSERT, DELETE` on `ledger.call_body` [VERIFIED: `alembic/versions/0003_ledger_tables.py:252`]
and `SELECT, INSERT, UPDATE` on `ledger.call_record` [VERIFIED: `0002_call_record.py:187-191`].

**The pleasant corollary, worth writing at the migration comment rather than leaving to be rediscovered:**
the `SELECT` grant on `call_body` — which `0003`'s comment justifies solely as *"required alongside DELETE
… a `DELETE ... WHERE expires_at <= $1` reads a column"* — is now **also** what makes D-34's
`ON CONFLICT (call_id) DO NOTHING` legal on that table. A future tightening that revoked `SELECT` in the
name of "no read path" would break two things, not one.

### Pitfall 4: the fallback must be bound even when the broker never connected

**What goes wrong:** `_start_publisher` catches every exception from the broker bring-up, sets
`application.state.publisher = None`, logs `app.broker_unavailable` and returns
[VERIFIED: `src/prope/app.py:129-134`]. **On that path no publisher task is created at all**, so
`enqueue()` fills the 512-record handoff and then drops — with no publish attempt and therefore no
fallback call, in the exact scenario ADR-0041 was written about (*"`docker compose up -d` restarts
`rabbitmq` while `app` keeps serving"*).

**Why it happens:** the fallback as designed lives on `publish_record`'s failure branch, and
`publish_record` is only reached from a publisher that was started.

**How to avoid:** the plan must decide, explicitly, what happens when the broker was never reachable at
startup. Two shapes work and one does not:
 (a) **Start the publisher anyway, with `exchange=None`, so every record takes the bare-`except` branch
 and falls back.** Keeps one code path and makes `fallback_direct_write_total` rise the way the ADR
 describes. Costs a nullable exchange threaded through `publish_record`.
 (b) **Start a fallback-only job** when the broker is absent: same supervised job, a body that reads the
 handoff and calls `fallback` directly. One extra branch at the composition root, no nullable exchange.
 (c) *Do nothing* — leave the current early return. **This fails SC1**, because SC1's provocation is
 "RabbitMQ unreachable" and a broker that was unreachable *at startup* is the most ordinary form of that.
Recommend **(b)**: `app.py` is the composition root and choosing between two job bodies is exactly what a
composition root is for, whereas a nullable exchange puts the degraded case inside the function that
handles the healthy one.

**Warning signs:** an SC1 test that provokes the outage by closing a live channel passes, and the one
that points `build_connection` at a closed port does not. D-45 asks for both for this reason.

### Pitfall 5: `occurred_at` moving into `enqueue()` changes the handoff's element type

**What goes wrong:** D-41 stamps `occurred_at` in `enqueue()`. The handoff is
`asyncio.Queue[CallRecordDraft]` [VERIFIED: `src/prope/call_ledger/enqueue.py:76`] and
`CallRecordEnvelope.from_draft(record, occurred_at=…)` is called in `publish_record`
[VERIFIED: `enqueue.py:186`]. The timestamp has to travel with the draft, so the queue's element type
changes — and so does every test that pokes the handoff.

**Why it happens:** the draft is frozen and has no field for it; `occurred_at` is an envelope field, not
a record field, and correctly so — it means "when this was handed off", which the record has no business
knowing.

**How to avoid:** a small frozen dataclass (`HandoffItem(draft, occurred_at)`) rather than a tuple. A
tuple is one character shorter and turns every unpack site into a positional guess; the fallback also
needs `occurred_at` (to observe `write_lag_seconds` on the direct-write path, which is also
"enqueue → durable"), so the pair travels to three places rather than two.

### Pitfall 6: the default histogram buckets cannot measure either of this phase's latency claims

**What goes wrong:** `Histogram.DEFAULT_BUCKETS` is
`(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, inf)`
[VERIFIED, this session]. For `enqueue_duration_seconds` the target is p95 < 1 ms, five times *below*
the first edge — every observation lands in the first bucket and `histogram_quantile` can only ever
answer "somewhere under 5 ms". For `write_lag_seconds` the alert threshold is p95 > 30 s, three times
*above* the last finite edge — every lag from 10 s to an hour is the same `+Inf` observation.

**Why it happens:** the defaults are shaped for HTTP request latency, which is the one thing neither of
these measures.

**How to avoid:** explicit `buckets=` on both, with the target values *at bucket edges*. See § *OQ-R1*
for the two proposed sets and the arithmetic behind them. The rule that generates them:
`histogram_quantile` interpolates linearly **inside** the bucket holding the quantile, so a target that
falls in a bucket's interior can only be answered to that bucket's width — put the number you are going
to assert on at an edge.

### Pitfall 7: a mounted ASGI app is a route the assertion cannot see

**What goes wrong:** `app.mount("/metrics", make_asgi_app())` produces a `starlette.routing.Mount`, which
has no `dependant`. `assembled_routes()` iterates `application.routes` and appends a route only if it
either expands (`effective_route_contexts`) or carries a `dependant`
[VERIFIED: `src/prope/session_auth.py:263-271`]. A `Mount` does neither, so it is skipped — and every
assertion in `test_route_table.py` is written over `assembled_routes()`. The endpoint would be served,
scrapable, unauthenticated, and **absent from the table AC-10 asserts is complete**.

Two smaller consequences ride along: the mount is not in `app.openapi()` either, so
`test_the_openapi_schema_agrees_with_the_route_table` would keep passing at 7; and mounting at
`/metrics` serves `/metrics/`, with `/metrics` answering 307 [CITED: prometheus/client_python#1016].

**Why it matters beyond this route:** Broken Window #4 already records that a naive `app.routes` walk
asserts vacuously. This is the same class of hole one layer out — a route the *helper* cannot see rather
than a route the *test* cannot see — and seven more modules will read this file for the pattern.

**How to avoid:** a plain `@application.get("/metrics")`. Pattern 5.

### Pitfall 8: `CONTENT_TYPE_LATEST` no longer describes what `generate_latest` emits

**What goes wrong:** a route returns `generate_latest(REGISTRY)` with `media_type=CONTENT_TYPE_LATEST`
and labels a 0.0.4-format payload as format version 1.0.0.

**Why it happens:** in `prometheus-client` 0.26.0, `CONTENT_TYPE_LATEST = CONTENT_TYPE_PLAIN_1_0_0 =
'text/plain; version=1.0.0; charset=utf-8'` [VERIFIED: `prometheus_client/exposition.py:51-57`], while
the library's own negotiator returns `(generate_latest, CONTENT_TYPE_PLAIN_0_0_4)` as the fallback pair
and only reaches for a 1.0.0 label when the client explicitly asked for `version=1.0.0`
[VERIFIED: `exposition.py:361-387`]. The constant's name says "latest"; its value is a *format claim*.

**How to avoid:** `CONTENT_TYPE_PLAIN_0_0_4`, or use `choose_encoder(request.headers.get("accept", ""))`
and return both halves of what it hands back. Recommend the former for a first exposition surface: it is
one line, it is what the library itself defaults to, and negotiation is a feature nothing in this
deployment asks for. Note it in the docstring so a later reader does not "modernise" the constant.

### Pitfall 9: a negative `write_lag_seconds` observation silently corrupts the metric's `_sum`

**What goes wrong:** `write_lag_seconds` is computed as `now − occurred_at`, and `occurred_at` is stamped
in `app` while `now` is read in `worker`. If the two clocks ever disagree in the wrong direction, the
observation is negative. `prometheus_client` accepts it without complaint: provoked this session,
`h.observe(0.5); h.observe(-3.0)` yields `_count 2.0` and **`_sum -2.5`** — the lowest bucket takes the
sample and the sum goes down. `histogram_quantile` still reads sensibly; `rate(_sum[5m])` goes negative
and any average-latency panel built on it becomes nonsense.

**Why it happens:** two processes, one metric, and no guard. On ADR-0033's single VM both containers read
the same kernel clock, so this is currently unreachable — which is exactly why it would be shipped
unguarded and discovered on the day the topology changes.

**How to avoid:** `observe(max(0.0, lag))` with a comment naming the cross-process measurement, and count
the clamp if it is worth counting (it is not — no metric is declared for it, and inventing a nineteenth
is worse than a comment). Also state the property positively: *this metric is only meaningful because
`app` and `worker` share a host*.

### Pitfall 10: `message_count` counts ready messages, so `queue_depth` under-reports by up to one window

**What goes wrong:** the depth gauge reads `declaration_result.message_count` from a passive declare.
RabbitMQ: *"Queue length is defined as the number of messages ready for delivery"*
[CITED: rabbitmq.com/docs/queues], and messages are in one of two states — *"Ready for delivery"* and
*"Delivered but not yet acknowledged by consumer"*. The drain sets `prefetch_count = WINDOW_SIZE = 500`
[VERIFIED: `src/prope/call_ledger/drain.py:365`], so up to 500 messages can be unacknowledged and
therefore **invisible** to `queue_depth` at any moment.

**Why it matters:** a "the backlog cleared" assertion written against `queue_depth == 0` can pass while
500 messages are in flight, and the first failure-mode row's detection narrative
(*"`queue_depth` rises"*) understates a small backlog completely.

**How to avoid:** write the semantics at the gauge (*ready messages; up to one window is unacked and not
counted*) and, in any test asserting a backlog cleared, assert the durable side — rows in
`ledger.call_record` — rather than the gauge. The gauge is a graph; the table is the fact.

### Pitfall 11: a passive declare of a missing queue closes the channel

**What goes wrong:** `channel.declare_queue(name, passive=True)` raises when the queue does not exist —
aio-pika documents *"Raises `aio_pika.exceptions.ChannelClosed` when queue doesn't exist"*
[VERIFIED: `aio_pika/channel.py:363-380` docstring; the concrete class is `ChannelNotFoundEntity`, a
`ChannelClosed` subclass, present in `aio_pika.exceptions`]. It is an AMQP channel-level error, so the
channel is gone with it. A long-lived gauge job holding one channel would read `queue_depth`, fail on
`dlq_depth`, and then be dead for every subsequent pass.

**Why it happens:** channel-level errors close channels; that is AMQP, not aio-pika.

**How to avoid:** a fresh channel per queue per pass, which is what `tests/broker/_helpers.py` already
does and says why. Pattern 7. And because the job is supervised (D-42), a genuinely missing queue becomes
a restarting job with a `supervisor.job_crashed` line rather than a silently stuck gauge — which is the
correct outcome and is worth asserting once.

### Pitfall 12: `prope_report` can read every body, and none of D-38's three layers can see it

**What goes wrong:** the no-read-path claim is proven at three layers — routes, internal Python surface,
and the statements in `src/` that name `call_body`. **All three are about this application.** The
database has a fourth reader that none of them touches:

- `CREATE ROLE prope_report LOGIN BYPASSRLS`
  [VERIFIED: `alembic/versions/0001_roles_and_schemas.py:47`]
- `grant_table(..., report_select: bool = True)` and `GRANT SELECT ON {schema}.{table} TO prope_report`
  [VERIFIED: `alembic/ddl.py:103, 122-123`]
- `grant_table("ledger", "call_body", app_privileges=["SELECT", "INSERT", "DELETE"])` — taking the
  `report_select` default [VERIFIED: `alembic/versions/0003_ledger_tables.py:252`]

So `SELECT request_body, response_body FROM ledger.call_body` on the `prope_report` credential returns
every stored body in **every** workspace, RLS bypassed by role attribute. `tests/conftest.py` even builds
that engine as a session fixture [VERIFIED: `tests/conftest.py:162-167`].

**Why it is not obviously a defect:** ADR-0037 records `prope_report` as a deliberate full-read reporting
credential, and ADR-0036's restore rehearsal depends on it existing. AC-10's text is about *"route,
parameter, or function"* and does not reach a database role.

**Why it is not obviously fine either:** `security_requirements`' first clause is *"Bodies have no read
path in the MVP — no endpoint, **no export**, no admin viewer, and no join from another module's query"*,
and T-005's own reasoning is *"a body's lifecycle is a property of every place it can rest, not of the
table it is meant to live in"* — which is the argument ADR-0039 already used to exclude `call_body` from
the nightly dump. This is the same argument one layer down.

**How to handle it:** do **not** silently ship the sweep as if it were complete. Three honest options:
 (a) **`REVOKE SELECT ON ledger.call_body FROM prope_report` in a migration `0005`**, with a test that
 provokes the refusal against the live engine (the `tests/security/test_append_only_privilege.py` pattern)
 and a positive control on another ledger table proving the credential still reads. Makes ADR-0037's
 "full-read" into "full-read except the one table declared to have no reader", which must be written down.
 (b) **Leave it and assert it deliberately** — a test named for what it proves (*the reporting credential
 can read a body, and that is a recorded exception, not an oversight*), the same move
 `tests/security/test_eval_no_body_boundary.py::test_the_database_carries_no_guard_and_a_hand_written_body_lands`
 already makes for A-055.
 (c) Do nothing and mention it nowhere. **Refused** — "we looked and decided not to" and "nobody looked"
 are indistinguishable a year later, which is the failure this repository's whole verification posture is
 shaped against.

**This is also the honest close of the carried-forward `prope_report` discretion item.** That item has
been phrased since Phase 1 as "what grants does `prope_report` get on the new table", and this phase
creates no table — so as phrased it is vacuous. The real question was always this one.

**Note on ids:** this is a **sixth** spec conflict, against `security_requirements` (and ADR-0037), and
**OQ-022…OQ-026 are all already assigned** by CONTEXT. It fits most naturally as a second clause on
**OQ-025** (whose subject is already *"a body rests somewhere the no-read-path claim does not reach"*),
or it needs an id from outside this phase's range, which only the orchestrator may allocate. Do not
invent OQ-027 — another phase may hold it.

### Pitfall 13: removing D-30's increments leaves an envelope-rejection with no counter at all

**What goes wrong:** `_parse` currently increments `metadata_dropped_total` for an invalid envelope
[VERIFIED: `src/prope/call_ledger/drain.py:249`] and that is its *only* metric. D-30 removes it. After
the removal, a malformed envelope produces one log line, a `reject(requeue=False)`, and **no counter
movement of any kind**.

**Why it happens:** the declared eighteen contain no "envelope invalid" counter. D-30's answer is
`dlq_depth > 0`, which is correct as a *detection* — nothing drains the DLQ, so the depth is monotone
until an operator acts.

**But state the limit:** `dlq_depth` is a **gauge**, and the DLQ carries a 30-day TTL (A-149, D-23). So
it answers "is there anything in the DLQ right now" and can never answer "how many have ever gone
there" — after 30 days the message expires and the gauge returns to zero with no record that it was ever
non-zero. The durable record of the event is the log line, and container logs are capped at
`max-size: 50m, max-file: 5` per service by ADR-0030.

**How to avoid the wrong fix:** do **not** invent a nineteenth metric. Write the limitation at the removal
site and in `deferred-items.md`, so the phase that eventually owns the deployment stack knows that DLQ
history lives in logs with a bounded life.

### Pitfall 14: `missing_version_id_total`'s increment site changes what `writer.py` claims about itself

**What goes wrong:** `writer.py`'s module docstring says *"it emits no log and no metric at all"*
[VERIFIED: `src/prope/call_ledger/writer.py:37-39`]. D-35 puts `duplicate_call_id_total` inside it and
D-40 puts `missing_version_id_total` inside it. The sentence becomes false in the same change that makes
it false, and a docstring that has stopped being true is worse than no docstring.

**Why it happens:** the sentence was a correct statement of a Phase 1 property that Phase 3 deliberately
retires, for a stated reason — D-35's *"all three callers get it for free"*.

**How to avoid:** rewrite the paragraph in the same commit, saying what is now true and why: *this module
emits two counters and no log, and both counters describe the statement's own outcome rather than the
records' contents (A-046 still holds — no body reaches a label, because no label exists on either
counter)*. The alternative shape — raising a typed `MissingVersionIdError` and incrementing at the three
call sites — is rejected for consistency: D-35 already put one counter here, and two metric conventions
inside one function is worse than one broken sentence.

**Related, and easy to miss:** after D-40's explicit refusal, a `source=gateway` record with a NULL
`version_id` becomes a `ValueError`, which `classify_write_failure` maps to `PERMANENT`
[VERIFIED: `drain.py:152-153`] and therefore dead-letters. So `missing_version_id_total` rising and
`dlq_depth` rising are **the same event**, and an operator should be told that in the alert annotation
rather than opening two incidents.

---

## Code Examples

### Provoking a broker outage without touching the session container (D-45.3)

```python
# tests/chaos/test_metadata_never_dropped.py

async def test_a_dead_channel_sends_every_record_through_the_fallback(
    amqp_url, app_sessionmaker, migrate_engine
):
    """SC1, provoked the cheap way: close the channel under the running publisher.

    Rejected alternatives, both recorded at the test rather than only in the plan:
    stopping `rabbitmq_container` (session-scoped and shared — every later test in
    the run would fail for an unrelated reason), and a module-scoped second broker
    (a 10-20 s boot repeated per subagent pytest run, for a failure a closed channel
    reproduces exactly).
    """
    stopping = asyncio.Event()
    fallback = build_fallback_writer(app_sessionmaker)
    connection = await build_connection(amqp_url)

    async with connection:
        channel = await connection.channel(publisher_confirms=True)
        await declare_topology(channel)
        publisher = asyncio.create_task(
            run_publisher(channel.default_exchange, stopping, fallback=fallback)
        )
        await channel.close()                       # the broker is now "unreachable"

        for draft in [gateway_draft(f"call-{i}") for i in range(1000)]:
            enqueue(draft)                          # SC1's thousand calls

        await _wait_until(lambda: _row_count(migrate_engine) == 1000, timeout=60)
        stopping.set()
        await asyncio.wait_for(publisher, timeout=10)

    # Every one durable, with its version_id. Only bodies dropped, and counted.
    assert await _rows_with_null_version_id(migrate_engine) == 0
    assert await _call_body_count(migrate_engine) == 0
    assert _counter_value(body_dropped_total, reason=BODY_DROP_REASON_FALLBACK) == 1000
    assert _counter_value(fallback_direct_write_total) == 1000
    assert _counter_value(metadata_dropped_total) == 0        # the whole claim
```

> **`_counter_value` needs care.** `prometheus_client` counters are process-global and the suite shares a
> process, so a counter read must be a **delta** across the test rather than an absolute. Take a snapshot
> at the top (`REGISTRY.get_sample_value(name, labels)`) and assert on the difference. A test that
> asserts an absolute count passes when run alone and fails when run after its neighbour, which is the
> worst failure shape a suite can have. There is no autouse fixture resetting the registry today and
> **adding one would be worse** — it would make every counter's cross-test behaviour invisible.

### The redelivery test that actually tests CL-02 (SC2)

```python
async def test_a_redelivery_does_not_move_the_workspace_total(
    amqp_url, app_sessionmaker, migrate_engine
):
    """AC-2 restated (PITFALLS §2): 'every message redelivered after an
    unacknowledged consumer restart'. NOT the lock's literal spill-replay text.
    """
    drafts = [gateway_draft(f"call-{i}", cost_bearing=True) for i in range(5)]
    await publish_drafts(amqp_url, drafts)

    await drain_until(amqp_url, app_sessionmaker, lambda: _row_count(migrate_engine) == 5)
    before = await _spend_row(migrate_engine)          # call_count, total_cost

    # Re-publish the same five envelopes. Same call_ids: the shape a redelivery
    # after an unacknowledged consumer restart produces, without needing to kill
    # a consumer mid-flight — and the drain cannot tell the difference, which is
    # the property under test.
    await publish_drafts(amqp_url, drafts)
    await drain_until(amqp_url, app_sessionmaker, lambda: _duplicates_seen() == 5)

    after = await _spend_row(migrate_engine)
    assert after == before                              # CL-02's actual claim
    assert await _row_count(migrate_engine) == 5
    assert _counter_delta(duplicate_call_id_total) == 5
```

**One property this shape does not prove** and the plan should not claim: `redelivered_total` reads
`AbstractIncomingMessage.redelivered`, which is the *broker's* flag and is only set on a genuine
redelivery. Re-publishing produces new messages with `redelivered=False`. So `redelivered_total` needs
its own test that really does leave messages unacknowledged — `drain_until` with a predicate that never
becomes true, then a second drain over the same connection — while the *idempotency* claim above is
better served by re-publishing, because it is deterministic. Two tests, two mechanisms, both named.

### The CI-resident load proxy (D-45.1)

```python
# tests/load/test_enqueue_off_response_path.py

HANDOFF_80_PERCENT = int(HANDOFF_MAXSIZE * 0.8)      # 410 of 512 — the lock's stated `condition`
SAMPLES = 500                                        # 25 observations above the p95; see D-45

def test_enqueue_p95_under_one_millisecond_at_eighty_percent_depth() -> None:
    """CL-12 / SC5's proxy. No container, no broker, no database — the handoff is
    in-process and no publisher is running, which is what makes 80% depth free to
    arrange and what makes this test belong in the default suite.
    """
    reset_handoff()
    for i in range(HANDOFF_80_PERCENT):
        enqueue(gateway_draft(f"prefill-{i}"))

    drafts = [gateway_draft(f"timed-{i}") for i in range(SAMPLES)]
    samples: list[int] = []
    for draft in drafts:
        start = time.perf_counter_ns()
        enqueue(draft)                                # the whole of the caller's span
        samples.append(time.perf_counter_ns() - start)

    samples.sort()
    p95_ns = samples[int(0.95 * len(samples))]
    assert p95_ns < 1_000_000, f"p95 {p95_ns/1e6:.3f} ms"
    assert _counter_delta(metadata_dropped_total) == 0
```

Two things this deliberately does **not** do. It does not `pytest.mark.load` — see § *OQ-R7*. And it does
not attach a 256 KiB body to the timed drafts, because D-29's `str.encode()` is the largest term in the
span and timing it at the cap is a *second* assertion with a different subject; write it as one
(`test_a_body_at_the_cap_still_fits_the_budget`, with `SAMPLES` at the cap) so a failure names which cost
moved.

### The alert-rules file and the test that keeps it honest (D-44)

```yaml
# deploy/prometheus/rules/call_ledger.rules.yml
groups:
  - name: call_ledger
    rules:
      - alert: LedgerMetadataDropped
        expr: increase(prope_call_ledger_metadata_dropped_total[5m]) > 0
        labels: {severity: page}
        annotations:
          summary: A call record reached neither the broker nor the database
          description: >-
            After ADR-0041 this counter means BOTH stores were unavailable. The
            "100% of calls record a version ID" claim is now false and measurably so.
            A dead-lettered record does NOT increment this (D-30) — see LedgerDlqNonEmpty.
      - alert: LedgerDlqNonEmpty
        expr: prope_call_ledger_dlq_depth > 0
        for: 0m
        labels: {severity: ticket}
        annotations:
          summary: Something is in prope.call_record.dlq
          description: >-
            T-005's mitigation. Any non-zero value alerts. NOTE the metric is a GAUGE and
            the DLQ has a 30-day TTL, so this cannot answer "how many have ever gone there".
```

```python
# tests/architecture/test_alert_rules.py
RULES = Path("deploy/prometheus/rules/call_ledger.rules.yml")
METRIC = re.compile(r"prope_call_ledger_[a-z0-9_]+")

def test_every_metric_named_by_a_rule_exists_in_the_registry() -> None:
    """D-44's whole purpose. A rule naming prope_call_ledger_spill_bytes parses
    fine and alerts never — which is the failure this file's TEST exists to catch,
    not the file itself.
    """
    document = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    named = {m for group in document["groups"] for rule in group["rules"]
             for m in METRIC.findall(rule["expr"])}
    registered = {s.name.removesuffix("_total").removesuffix("_created")
                  for metric in REGISTRY.collect() for s in metric.samples}
    assert named - registered == set(), f"rules name metrics that do not exist: {named - registered}"

def test_all_six_declared_alerts_are_present() -> None:
    """The other direction. A rules file that lost a rule still parses."""
    document = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    names = {rule["alert"] for group in document["groups"] for rule in group["rules"]}
    assert names == DECLARED_ALERTS      # the lock's six, plus T-005's LedgerDlqNonEmpty
```

> **The `_total` suffix trap.** `generate_latest` renders a `Counter` named `x_total` as samples `x_total`
> **and** `x_created`, and PromQL refers to it as `x_total`. Matching registry sample names against rule
> text without normalising the suffixes produces a test that passes for the wrong reason on counters and
> fails for the wrong reason on gauges. Normalise once, in one helper, and assert the helper on a known
> pair.

---

## State of the Art

| Old approach | Current approach | When changed | Impact here |
|---|---|---|---|
| `INSERT … RETURNING` only for single rows; a loop for batches | `insertmanyvalues` — batched INSERT with RETURNING, on by default | SQLAlchemy 2.0 (2023); `sort_by_parameter_order` added in **2.0.10** | D-33's whole statement is one round trip rather than 500. **And the ordering flag is the trap** — Pitfall 1 |
| `time.monotonic()` unusable for sub-millisecond timing on Windows | `time.monotonic()` uses `QueryPerformanceCounter` | **Python 3.13** — *"On Windows, `monotonic()` now uses the `QueryPerformanceCounter()` clock for a resolution of 1 microsecond, instead of the `GetTickCount64()` clock which has a resolution of 15.6 milliseconds"* [CITED: docs.python.org/3/whatsnew/3.13.html] | Confirmed on this host: `time.get_clock_info("monotonic")` reports `resolution=1e-07, implementation=QueryPerformanceCounter()` [VERIFIED, this session]. **The classic advice "never use `monotonic` for microsecond timing on Windows" is obsolete on 3.13.** `perf_counter_ns` is still the right call in D-45's proxy — it is unambiguous — but the *reason* is clarity, not resolution |
| Ad-hoc queue teardown flags | `asyncio.Queue.shutdown()` / `QueueShutDown` | **Python 3.13** [CITED: docs.python.org/3/whatsnew/3.13.html, gh-104228] | D-31's primitive. Pattern 3 |
| `text/plain; version=0.0.4` as *the* Prometheus text format | `text/plain; version=1.0.0` exists and `CONTENT_TYPE_LATEST` now points at it | `prometheus-client` recent line; 0.26.0 is current (2026-07-24) [VERIFIED: pypi.org/pypi/prometheus-client/json] | Pitfall 8. `generate_latest` still emits 0.0.4 |
| `ValueError` on duplicate metric registration | `prometheus_client.registry.DuplicateTimeseries` (a `ValueError` subclass) | **0.26.0** — release note *"Specific exception handling for duplicate timeseries"* [CITED: github.com/prometheus/client_python releases] | Confirmed this session. Matters because `observability.py` defines eighteen metrics at import and a test that reimports the module gets a precise exception instead of a generic one |
| Quorum queues for `x-delivery-limit` | unchanged — Phase 2 chose classic durable for `reject-publish-dlx` | RabbitMQ 4.0 | Not reopened. D-36 keeps `PERMANENT` as the classifier default *because* of it |

**Deprecated / stale in this repo, and still not this phase's to fix:**

- **Root `Dockerfile` and `docker-compose.yml` remain boilerplate** from another project (`python:3.11-slim`,
  `requirements.txt`, a single `backend` service). Recorded by Phase 2's `deferred-items.md`. D-39 and D-42
  both describe compose-shaped facts and a planner will find these files. **Do not extend them.**
- **`uv run ruff format --check` still fails repo-wide** on the `line-length` disagreement (Broken Window #1).
  `ruff check` is the gate.
- **`observability.py`'s docstring says "Phase 2 wires four counters" and there are five**
  [VERIFIED: `src/prope/observability.py:14` vs the five `Counter(...)` definitions at `:74, 84, 92, 101, 125`].
  This phase rewrites the file anyway; correct it in passing.

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | The absence of `sort_by_parameter_order` is sufficient, i.e. SQLAlchemy will not select a sentinel on its own for this statement | Pitfall 1 | Verified by compiling the exact statement this session (`sentinel_columns=None, num_sentinel_columns=0`), so the risk is that a **later SQLAlchemy version** changes the default. Mitigated by the pin (`==2.0.51`) and by the test in Pitfall 1's "how to avoid" |
| A2 | A plain `APIRoute` for `/metrics` is preferable to a `Mount` | Pattern 5, Pitfall 7 | The `Mount` gets content negotiation and gzip for free. If the planner wants those, `choose_encoder` gives negotiation on a plain route and Caddy can do the compression. The visibility argument is the load-bearing one and it is a fact about `assembled_routes()`, not a preference |
| A3 | Bucket edges: enqueue `(0.00005 … 0.05, +Inf)`, lag `(0.05 … 300, +Inf)` | OQ-R1 | Arithmetic against stated targets, not measurement. Both sets put every asserted number on an edge, which is the property that matters; the intermediate edges are judgement |
| A4 | Retire `ceiling_failed_open_total` rather than keep it | OQ-R3 | SC3's words are *"increments the failed-open counter"*. If a verifier reads that as naming the Phase 2 constant rather than the declared labelled one, the phase looks incomplete. **Stated in the plan is the mitigation** |
| A5 | `min(created_at)` rather than `min(expires_at)` for the age gauge | OQ-R4 | The metric's own name says "age" and the alert compares against a window, so both point the same way. The residual is that the *alert's threshold is per-workspace* and the gauge is not — named, unresolved, and routed |
| A6 | `HANDOFF_DRAIN_DEADLINE_SECONDS = 3.0`, derived, with `PUBLISHER_STOP_TIMEOUT_SECONDS = deadline + 2.0` | OQ-R5 | The 1.5 ms-per-fallback-write figure is D-27's arithmetic, unvalidated at real scale like every number of this kind here. If a single-record transaction costs 10 ms, a full 512 buffer takes 5 s and the deadline truncates it — the counter then reports the truncation, which is the correct behaviour, not a silent loss |
| A7 | Depth-gauge interval 15.0 s | OQ-R6 | Matched to a *convention* because the scrape interval is a deployment setting with no owner (PITFALLS §4). If Prometheus is eventually configured at 30 s or 60 s, this over-samples harmlessly |
| A8 | The CI-resident proxy runs by default; the full-fat run is skipped by env var rather than deselected by `addopts` | OQ-R7 | `addopts = "-m 'not load'"` would change what `uv run pytest -q` means for phases 4–24, which is a repo-wide decision this phase should not take unilaterally. A skipped test is visible in the summary; a deselected one is not |
| A9 | Pattern 4's shape (b) for the broker-never-connected case | Pitfall 4 | This is my extension, not a locked decision — D-26 places the fallback at `publish_record`'s failure sites and is silent about the path where no publisher exists. A planner may reasonably prefer (a). **What is not optional is that the plan decides**, because SC1's most ordinary provocation goes through it |
| A10 | Pitfall 12 (`prope_report` on `call_body`) is in scope enough to require a decision | Pitfall 12 | AC-10's literal text does not reach a database role, so a reviewer could call this out of scope. The counter-argument is `security_requirements`' *"no export"* clause and T-005's own reasoning. Either disposition is defensible; **silence is not** |
| A11 | PyYAML should be declared in the dev group rather than relied on transitively | Standard Stack | One line in `pyproject.toml` and one entry in `uv.lock` that is already there. If the planner disagrees, the test still works today |
| A12 | Counter assertions must be deltas, not absolutes | Code Examples | `prometheus_client`'s default `REGISTRY` is process-global and pytest shares a process. Verified by construction rather than by a failing test; if a planner adds a registry-reset fixture instead, say so, because it hides cross-test counter behaviour |

---

## Open Questions — the Discretion list, resolved

**Status: ten recommendations, each with the evidence it rests on.** These were open *to the researcher*.
None is a spec conflict — the five spec conflicts leave this document entirely and become
`docs/brainstorm/open_questions/OQ-022…OQ-026`. **The plan must record which of these it adopted**, in the
same posture Phase 2's plans used.

### OQ-R1 — Histogram bucket edges

- **Recommendation — `enqueue_duration_seconds`:**
  `(0.00005, 0.0001, 0.00025, 0.0005, 0.00075, 0.001, 0.0025, 0.005, 0.01, 0.05, +Inf)`
- **Recommendation — `write_lag_seconds`:**
  `(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0, +Inf)`
- **What we know:** the defaults are `(0.005 … 10.0, inf)` [VERIFIED, this session]. The enqueue target is
  p95 < 1 ms; the lag targets are p95 < 2 s and p99 < 10 s
  [VERIFIED: `docs/modules/call-ledger.lock.yml`, `performance_requirements`]; `LedgerWriteLagHigh` fires
  at *"write_lag p95 > 30 s for 10 min"* [VERIFIED: same file, `alerts`].
- **The rule that generates both sets:** `histogram_quantile` interpolates linearly *inside* the bucket
  containing the quantile, so **every number the project will ever assert on must be a bucket edge**.
  That fixes `0.001` in the first set and `2.0`, `10.0` and `30.0` in the second. Everything else is
  resolution.
- **The arithmetic for the enqueue set:** the timed span is one `put_nowait` (tens of nanoseconds), one
  clock read, two counter increments, and — at the cap — a 256 KiB `str.encode()`, which is tens of
  microseconds. So the interesting range is 10 µs to 1 ms, which is where seven of the eleven edges sit.
  `0.05` and `+Inf` are the tail: above 50 ms the answer is "the event loop stalled", and one more edge
  would not change what anyone did about it.
- **The arithmetic for the lag set:** steady state is `WINDOW_MS` (250 ms) plus one write, so four edges
  under 1 s keep a healthy p95 legible instead of collapsing to "under 2 s". Above 30 s, `60` and `300`
  are what distinguish "the threshold was crossed" from "there is a backlog", and the backlog target is
  *"60 s of traffic drained within 60 s"*, so that is exactly the range in which somebody decides whether
  it is clearing.
- **Cardinality:** enqueue has a `source` label with two values → 11 × 2 = 22 bucket series. Lag is
  unlabelled → 12. Both well inside ADR-0030's rule.

### OQ-R2 — How `/metrics` is mounted

- **Recommendation: a plain `@application.get("/metrics")` returning `Response(generate_latest(REGISTRY),
  media_type=CONTENT_TYPE_PLAIN_0_0_4)`, `include_in_schema=True`, no session, no `ManagementAction`.**
- **What we know:** `assembled_routes()` appends a route only when it expands or carries a `dependant`
  [VERIFIED: `src/prope/session_auth.py:263-271`]; a `Mount` carries neither. Mounting at `/metrics` serves
  `/metrics/` [CITED: prometheus/client_python#1016]. `CONTENT_TYPE_LATEST` in 0.26.0 declares a format
  `generate_latest` does not emit [VERIFIED: `prometheus_client/exposition.py:51-57, 387`].
- **The security half, stated because it is not resolved by the shape:** the route is unauthenticated,
  and it must be — a scraper holds no session, and call-ledger *cannot* check a permission (ADR-0018's
  forbidden edge). What is exposed is the metric set, and **that is exactly OQ-023's subject**:
  `unpriced_total`'s declared labels are `provider_config_id, upstream_model`, and a `provider_config_id`
  resolves to exactly one workspace. Ship the route, raise OQ-023, and do **not** invent an auth scheme
  this module has no way to evaluate.

### OQ-R3 — `ceiling_failed_open_total`: retire, keep, or alias

- **Recommendation: retire it.** `ceiling_check_total{result="failed_open"}` is the same number under the
  declared name.
- **What we know:** the declared metric is `prope_call_ledger_ceiling_check_total # labels: result =
  allowed | refused | failed_open` [VERIFIED: lock file, `observability_requirements.metrics`]. The Phase 2
  counter is reachable from three places only — its definition (`observability.py:125`), its import
  (`seams.py:87`) and its increment site — and **no declared alert names it**.
- **Why not "keep alongside":** two names for one number, and the failure mode of two names for one number
  is that one of them stops being incremented in a refactor nobody reviews for that.
- **Why not "alias":** `prometheus_client` has no alias primitive; an alias is a second `Counter`
  incremented beside the first, which is "keep alongside" with a nicer word on it.
- **The consequence the plan must carry:** `ceiling_check_total` counts **all three** branches, and today
  `check_spend_ceiling` increments only on the open failure [VERIFIED: `src/prope/call_ledger/seams.py`,
  the fail-open branch is the only `.inc()`]. **The `allowed` and `refused` branches need increment sites
  added** — which is more than a rename and is the actual work.
- **And say it out loud:** ROADMAP SC3 reads *"increments the failed-open counter"*. A labelled counter is
  a counter; write that sentence in the plan so the verifier does not read SC3 as naming a Phase 2 constant.

### OQ-R4 — The `oldest_body_age_seconds` query shape

- **Recommendation: `SELECT min(created_at) FROM ledger.call_body` per enumerated workspace, gauge =
  `max over workspaces of (now − min(created_at))`.**
- **Both shapes are indexed** — `ix_call_body_workspace_id_created_at` and
  `ix_call_body_workspace_id_expires_at` both exist [VERIFIED:
  `alembic/versions/0003_ledger_tables.py:205-213`] — so this is a semantic choice, not a performance one.
- **Three reasons for `created_at`:** (1) the metric's name is `oldest_body_**age**_seconds` and an age is
  `now − created_at`; (2) the alert compares *"age exceeds the workspace's retention window plus one day"*
  [VERIFIED: lock, `alerts`], which only type-checks if the gauge is an age; (3) **D-10 is decisive** —
  `expires_at` is stamped once and never rewritten, so for a workspace that shortened its window,
  `min(expires_at)` reflects the *old* policy and would read healthy against the *new* one. That is the
  precise "looks healthy and is not" failure the alert exists to catch.
- **The residue, named rather than solved.** The alert's threshold is *per workspace* and D-43's gauge is
  *unlabelled and reduced*, so the rules file can only compare against the **default** 30-day window plus
  one day, and a workspace with a longer window will false-positive.
  - The strongest technical alternative is a `workspace_id` label on this one gauge — one series per
    workspace, on a gauge set once per sweep rather than per request. **And ADR-0030 permits it**:
    *"`model_name` and `workspace_id` are permitted at pilot scale and reviewed if either grows past
    hundreds"* [VERIFIED: `docs/adr/0030-…:53-54`]. That is **more permissive than `observability.py`'s own
    docstring**, which states flatly that `workspace_id` *"is deliberately never a label"*.
  - **D-43 is locked and this document does not reverse it.** What research adds is that the stricter rule
    D-43 cites is the module's, not the ADR's — so if OQ-022's answer comes back "the alert is right, fix
    the metric", the label is available without an ADR change.
  - Recommend the mismatch rides **OQ-022** as a third bullet (it is the same block and the same class of
    defect: a declared metric shape that its own declared alert cannot consume).

### OQ-R5 — The shutdown-drain deadline and `PUBLISHER_STOP_TIMEOUT_SECONDS`

- **Recommendation: `HANDOFF_DRAIN_DEADLINE_SECONDS = 3.0` in `enqueue.py`, and `app.py` **derives**
  `PUBLISHER_STOP_TIMEOUT_SECONDS = HANDOFF_DRAIN_DEADLINE_SECONDS + 2.0`.**
- **Why derivation and not two constants with a comment:** `_stop_publisher` does
  `asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)` and then `cancel()`
  [VERIFIED: `src/prope/app.py:143-151`]. If the inner deadline ever equals or exceeds the outer wait, the
  cancel lands **while the drain is still working** and the remainder count never runs — which reproduces
  CR-02 with more machinery. The relationship is invisible from either file, and a comment in one module
  about a constant in another is the definition of a fact nobody maintains.
- **Import direction:** `app.py` already imports from `enqueue.py`; the reverse would be a cycle. So the
  drain deadline is the primary and the stop timeout is derived from it, not the other way round.
- **The arithmetic:** a full handoff is 512 records; D-27 prices a single-record fallback transaction at
  ~1.5 ms, so the worst case (broker entirely gone, every record falling back) is ~0.77 s. 3.0 s is ~4×
  that. The +2.0 s margin covers `wait_for`'s own overhead and the `AsyncExitStack` unwinding of channel
  and connection that follows.
- **Add a test.** Three lines, importing both modules, asserting the inequality. Derivation makes drift
  impossible; the test makes a future "simplification" back to two literals fail loudly.

### OQ-R6 — The depth-gauge interval

- **Recommendation: `DEPTH_GAUGE_INTERVAL_SECONDS = 15.0`.**
- **Argued against the scrape:** Prometheus's conventional `scrape_interval` is 15 s. A gauge refreshed
  *less* often than the scrape produces a staircase Prometheus cannot smooth and an alert that fires one
  interval late; refreshed *more* often it burns round trips on samples nothing reads.
- **Argued against the round-trip cost:** two channel-open + passive-declare + close cycles per pass
  (Pitfall 11 forces a channel each), which is single-digit milliseconds on a compose network — 0.05% duty
  cycle at 15 s.
- **Rejected: 5 s** — three times the round trips for a series nothing samples that often.
  **Rejected: 60 s** — a DLQ message would be invisible for up to a minute and `dlq_depth > 0` is T-005's
  HIGH mitigation.
- **The honest caveat:** the scrape interval is a deployment setting, and the deployment stack owns no
  milestone (PITFALLS §4). So 15 s is matched to a *convention* rather than to a configured value, and
  that sentence belongs at the constant.

### OQ-R7 — Whether the CI-resident proxy runs by default, and where the marker lives

- **Recommendation: the proxy runs by default and carries no marker. The 50 rps × 10 min run carries
  `@pytest.mark.load` AND `@pytest.mark.skipif(not os.environ.get("PROPE_RUN_LOAD"), reason=…)`. Register
  `markers` in `pyproject.toml`. Do NOT add `addopts`.**
- **What we know:** `[tool.pytest.ini_options]` currently holds `asyncio_mode` and `testpaths` and **no
  `markers` key** [VERIFIED: `pyproject.toml:69-71`], so an unregistered marker emits
  `PytestUnknownMarkWarning`. There is no `filterwarnings = error`, so it warns rather than fails — which
  is worse, because a warning nobody acts on is a warning everybody stops reading.
- **Why the proxy runs by default:** it needs no Docker at all. The handoff is in-process, `reset_handoff()`
  already exists, and no publisher runs. It costs 910 `enqueue()` calls. **SC5 proven by a test that never
  executes is SC5 not proven.**
- **Why `skipif` over `addopts = "-m 'not load'"`:** `addopts` changes the default selection for the whole
  suite, for every phase from 4 to 24, and ORCHESTRATION §9's gate is literally `uv run pytest -q`. A
  deselected test is invisible in the summary; a **skipped** test prints `s` and its reason. This phase
  should not silently redefine what the project's green gate covers.
- **Document the invocation** in the `Makefile` as its own target, so `PROPE_RUN_LOAD=1 uv run pytest -m load`
  is discoverable rather than tribal.

### OQ-R8 — Whether `enqueued_total` gains an `oversize` outcome

- **Recommendation: no. `outcome` stays `accepted | dropped`.**
- **What we know:** the lock declares `prope_call_ledger_enqueued_total # labels: source, outcome` with no
  value list; Phase 2 fixed it at two values in source [VERIFIED: `src/prope/observability.py:69-78`].
  D-29 says the record with an oversize body *"always continues with `body=None`"* — so the record **is
  accepted**.
- **Why not:** `outcome` currently means *the fate of the record*. `oversize` would mean *the fate of the
  body*. Two subjects in one label makes the counter unsummable — `sum(enqueued_total)` would stop being
  "records offered", which is the one thing it is for.
- **Write it at the counter**, in the `#:` comment, so the next reader does not "complete" the vocabulary.
  The oversize event is fully visible on `body_dropped_total{reason=…}`, which is the counter whose subject
  *is* the body.

### OQ-R9 — How many OQ files the five conflicts become

- **Recommendation: five, exactly as CONTEXT allocated — OQ-022 … OQ-026.**
- **The rule, restated so the split does not look like a violation of precedent:** Phase 2's rule was one
  file per *blocked upstream field* (OQ-018 `data.owns`, OQ-019 `apis.exposes`, OQ-020 INT-021's signature).
  OQ-022 and OQ-023 are both against `observability_requirements.metrics`, so a literal reading would merge
  them. **The property the rule was standing in for is "one file per thing a resolver can accept
  independently"**, and these two are not: OQ-022 is a vocabulary correction the spec owner can make in an
  afternoon; OQ-023 is a data-exposure question that needs whoever owns OQ-013. Five files.
- All five `blocks_build: false`. The code ships either way; the deviations are declared, not resolved.
- Per Phase 2's precedent the **files are written by the plan or executor that reaches each conflict**, not
  by a research or context pass. This document creates none.

### OQ-R10 — `prope_report` read grants

- **Recommendation: reframe the item and then decide it.** As carried forward from Phases 1 and 2 the
  question is *"what does `prope_report` get on the new table"*, and **this phase creates no table**, so as
  phrased it is vacuous and should be closed with that reason.
- **The live question is Pitfall 12**: `prope_report` is `BYPASSRLS` and holds `SELECT` on
  `ledger.call_body`, so one credential reads every stored body in every workspace, and none of D-38's
  three layers can see it. Option (a) is `REVOKE SELECT … FROM prope_report` in a migration `0005` with a
  live-engine refusal test and a positive control; option (b) is a test that asserts the exception
  deliberately and names it as recorded rather than overlooked.
- **Either is defensible. Doing neither is not**, and if the planner takes (b) then `deferred-items.md`
  must carry it, because the difference between "considered and accepted" and "never noticed" is exactly
  what a deferred-items file exists to record.
- **On `ledger.workspace_retention` specifically** (the literal wording of the carried item): Phase 2
  already took `grant_table`'s `report_select=True` default for it, matching every other table
  [VERIFIED: `alembic/ddl.py:103`]. A retention *window* is a policy row, not a body. Nothing to change.

---

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| Docker daemon | the two existing testcontainers | ✓ | Server 29.6.2 (STATE.md, resolved in Phase 1) | none — D-02/D-22 refuse a second provisioning path |
| `postgres:17` image | the rig | ✓ | pulled and cached | — |
| `rabbitmq:4.3-management` image | the rig | ✓ | pulled in Phase 2 | — |
| `prometheus-client` 0.26.0 | eighteen metrics, `/metrics` | ✓ installed | 0.26.0, current on PyPI (2026-07-24) [VERIFIED: pypi.org/pypi/prometheus-client/json] | — |
| `pyyaml` | D-44's rules test | ✓ importable | 6.0.3, transitive via `uvicorn[standard]` | declare it in the dev group — § *Standard Stack* |
| `promtool` | *would* validate the rules file properly | ✗ and not obtainable here | — | **None.** The test asserts metric existence, not PromQL validity. State the boundary |
| A running Prometheus | would consume the rules file | ✗ by design | — | PITFALLS §4 — the deployment stack owns no milestone. D-44 ships a file into a repository |
| Network egress to PyPI | nothing new | ✓ | — | — |

**Standing environment facts, still true and still load-bearing:**

- `docker` is **not** on the default bash PATH; a shell driving it must first
  `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`. testcontainers reaches the daemon
  without PATH help.
- The development host is **Windows** and `loop.add_signal_handler` is unimplemented there, so every stop
  path is a directly-settable `asyncio.Event`. `install_stop_handlers` already returns `()` on `win32`
  [VERIFIED: `src/prope/supervisor.py:273-274`]. **D-31's shutdown drain must therefore be drivable by
  setting the event directly**, which it is.
- `uv run ruff format --check` fails repo-wide (Broken Window #1). **Not this phase's to fix.**
- **New, and good news:** `time.get_clock_info("perf_counter")` and `("monotonic")` both report
  `resolution=1e-07` with `implementation=QueryPerformanceCounter()` on this host under Python 3.13.14
  [VERIFIED, this session]. CL-12's sub-millisecond measurement is honest on the machine it is written on.

**Missing dependencies with no fallback:** `promtool`, and it is a boundary rather than a blocker.

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high`
[VERIFIED: `.planning/config.json`].

### Applicable ASVS categories

| Category | Applies | Control in this phase |
|---|---|---|
| V2 Authentication | **partly** | `/metrics` is deliberately unauthenticated and joins `/healthz` and `/readyz` in `UNVERSIONED`. The obligation is that this is a **stated** decision with a test asserting it declares no session, not a default |
| V4 Access Control | **yes, as tenancy** | The fallback inherits `workspace_transaction` unchanged. D-43's per-workspace loop exists because an unscoped read is zero rows |
| V5 Input Validation | **yes** | D-29's byte cap is the only byte bound anywhere on the path; D-37's `le=3650` stops an input becoming an unclassifiable exception |
| V7 Error Handling & Logging | **yes** | Two new log lines (`handoff_abandoned`, the oversize drop) and one new `job` value. Every field stays inside `LOGGABLE_FIELDS`; **no new field is added** |
| V8 Data Protection | **yes, and this is the phase's centre** | AC-10's three layers, plus the fourth reader Pitfall 12 found |
| V9 Communications | **new here** | `/metrics` is a new network surface on `app`. Behind Caddy under ADR-0033, reachable from every container on the compose network |

### Threat table

| Pattern | STRIDE | Mitigation, and where it lands |
|---|---|---|
| **T-005 — the broker is a second body store; the DLQ had no policy** (HIGH, from the lock) | Information disclosure (B8) | A-149's four arguments were declared and asserted in Phase 2 (D-23). **This phase owes the sweep**: the `dlq_depth` gauge (D-40, D-42) and its alert rule (D-44). The byte-bound half is **OQ-025** — the queue's declared bound is a message count and `x-max-length-bytes` cannot be added now without a delete-and-redeclare |
| **A stored body read by a credential no test enumerates** | Information disclosure (B7 host) | **Pitfall 12.** `prope_report` is `BYPASSRLS` with `SELECT` on `ledger.call_body`. Decide it; do not ship the sweep silently incomplete |
| **`/metrics` leaking a workspace's identity through a label** | Information disclosure | `unpriced_total`'s declared labels are `provider_config_id, upstream_model`, and a `provider_config_id` resolves to exactly one workspace — on an unauthenticated endpoint. **OQ-023**, raised, not resolved by dropping the declared label |
| A body reaching a log line from the new drop paths | Information disclosure | A-046. The oversize path logs `call_id`, `workspace_id`, `reason`; the shutdown path logs `reason` and a count. **Assert it** the way Phase 2 did — provoke each and grep the captured record for the body string |
| A body reaching a **metric label** from the new drop paths | Information disclosure | `body_dropped_total`'s only label is `reason`, from a closed set. `byte_size` is never a label — a size is a value and this repo's rule fixes labels to closed sets |
| A forged call record moving a workspace's spend | Spoofing (B8) | **T-007, MEDIUM, accepted** — *"anything able to publish already holds the `.env` that also holds the KEK"*. Do not re-mitigate. **Note it is now slightly cheaper to exploit**: D-33's `DO NOTHING` means a forged record with a colliding `call_id` is silently ignored rather than raising. That is the correct behaviour and it is worth writing down |
| SQL injection via `workspace_id` from a broker payload | Tampering (B4) | Unchanged — `set_config('app.workspace_id', :ws, true)`, bound. **D-33's move to Core `insert()` must keep `tests/architecture/test_no_sql_interpolation.py` green**, and a Core construct makes that easier than `text()` did |
| A `SECURITY DEFINER` function added to enumerate workspaces for D-43 | Elevation | **Refused outright.** Four are sanctioned and a test asserts the set is exactly four |
| `/metrics` as an unauthenticated surface on the compose network | Information disclosure (B7) | T-02-15 registered the same class of concern for a metrics port on `worker`. Here it is on `app`, which is already the ingress target. The exposure is the metric *contents* (OQ-023), not the port |

---

## Sources

### Primary — in-repo, read this session

`docs/modules/call-ledger.lock.yml` (`performance_requirements`, `observability_requirements` incl. all
six alerts, `security_requirements` incl. T-005/T-006/T-007, `failure_modes` all eight rows,
`acceptance_criteria` incl. the AC-1/AC-2 amendment block, `test_plan`);
`docs/architecture/interfaces.md` (INT-018's failure table, INT-019, INT-020, INT-030);
`docs/adr/0041-broker-first-with-a-direct-write-fallback.md` (in full, including the A-139 follow-up);
`docs/adr/0018-body-store-has-no-read-path-in-the-mvp.md`;
`docs/adr/0030-observability-is-prometheus-and-grafana-and-nothing-else.md` (the label-cardinality
paragraph); `.planning/ROADMAP.md` § Phase 3; `.planning/REQUIREMENTS.md`;
`.planning/research/PITFALLS.md` §2, §4, §5; `.planning/ORCHESTRATION.md`; the phase's own `03-CONTEXT.md`
and `03-DISCUSSION-LOG.md`; `.planning/phases/02-*/02-RESEARCH.md`, `02-CONTEXT.md`, `02-VERIFICATION.md`,
`deferred-items.md`; and, line by line, `src/prope/{app,worker,supervisor,observability,session_auth}.py`,
`src/prope/call_ledger/{writer,enqueue,drain,seams,models,domain,envelope,schemas,api}.py`,
`src/prope/broker/{topology,connection}.py`, `alembic/ddl.py`, `alembic/versions/0001…0004`,
`tests/conftest.py`, `tests/broker/_helpers.py`, `tests/architecture/test_route_table.py`,
`pyproject.toml`, `uv.lock`.

### Primary — provoked against the installed artifacts this session

These are experiments, not citations, and each is reproducible from the project venv:

- `pg_insert(models.call_record).on_conflict_do_nothing(index_elements=["call_id"]).returning(...)`
  compiled `for_executemany=True` → `_InsertManyValues(sort_by_parameter_order=False,
  sentinel_columns=None, num_sentinel_columns=0, includes_upsert_behaviors=True)`; the same with
  `sort_by_parameter_order=True` → `sentinel_columns=(Column('call_id', …),), num_sentinel_columns=1`
- `.venv/Lib/site-packages/sqlalchemy/engine/default.py:908-918` — the `Sentinel-keyed result set did not
  produce correct number of rows` raise, read from the installed source
- `postgresql.dialect()` → `use_insertmanyvalues=True`, `insertmanyvalues_page_size=1000`
- `Histogram.DEFAULT_BUCKETS`; `CONTENT_TYPE_LATEST == 'text/plain; version=1.0.0; charset=utf-8'`;
  `prometheus_client/exposition.py:361-387` (`choose_encoder`'s `generate_latest, CONTENT_TYPE_PLAIN_0_0_4`
  fallback); `prometheus_client/asgi.py` (`make_asgi_app` via `_bake_output`);
  `prometheus_client.registry.DuplicateTimeseries`
- `Histogram.observe(-3.0)` → `_sum` decreases while `_count` increases
- `asyncio.Queue.shutdown` and `asyncio.QueueShutDown` present on Python 3.13.14; the docstring's
  `immediate=False` semantics
- `time.get_clock_info("monotonic"/"perf_counter")` → `resolution=1e-07`,
  `implementation=QueryPerformanceCounter()`
- `aio_pika.exceptions` → `ChannelNotFoundEntity` is present and is a `ChannelClosed`;
  `aio_pika/channel.py:352-380` (`declare_queue(passive=…)`), `aio_pika/queue.py:103-128` and
  `aio_pika/abc.py:90-92` (`DeclarationResult.message_count`)

### Primary — vendor documentation

- `https://www.postgresql.org/docs/17/sql-insert.html` — *"Only rows that were successfully inserted or
  updated will be returned"*; `ON CONFLICT DO UPDATE` requires `UPDATE` privilege while all forms of
  `ON CONFLICT` require `SELECT` on any column read
- `https://www.rabbitmq.com/docs/queues` — *"Queue length is defined as the number of messages ready for
  delivery"*; the ready / delivered-but-unacknowledged split; `queue.declare-ok`'s `message_count` field
- `https://docs.python.org/3/whatsnew/3.13.html` — `Queue.shutdown` / `QueueShutDown` (gh-104228);
  `monotonic()` on Windows moving to `QueryPerformanceCounter` (gh-88494)
- `https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/` — the `groups` / `rules`
  YAML shape and the `alert` / `expr` / `for` / `labels` / `annotations` fields
- `https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html` and `/core/connections.html` —
  `sort_by_parameter_order`, *"most database backends provide no formal guarantee of the order in which
  the records from RETURNING are returned"*
- `https://pypi.org/pypi/prometheus-client/json` — 0.26.0 current, 2026-07-24, `requires_python >=3.9`
- `https://github.com/prometheus/client_python/releases` — 0.24.0 → 0.26.0 notes
- `https://github.com/prometheus/client_python/issues/1016` — mounting at `/metrics` serves `/metrics/`

### Secondary — MEDIUM confidence

- WebSearch summarisation of the `insertmanyvalues` / `ON CONFLICT` interaction. **Superseded and not
  relied on** — the SQLAlchemy documentation does not state the caveat explicitly, so the claim in
  Pitfall 1 rests entirely on the installed source and on the compile experiment above, both of which are
  reproducible.

---

## Metadata

**Confidence breakdown:**

- **The upsert statement and its trap: HIGH.** Provoked against the pinned SQLAlchemy, with the raising
  code read from the installed wheel. The one residual is a future version changing the default, which the
  `==2.0.51` pin bounds.
- **PostgreSQL and RabbitMQ semantics: HIGH.** Every behavioural claim is quoted from vendor documentation
  at the pinned major version.
- **`prometheus_client` behaviour: HIGH.** Bucket defaults, content-type constants, the negotiation
  fallback, the duplicate exception and the negative-observation behaviour were all executed this session
  against 0.26.0.
- **The in-repo facts: HIGH.** Every `file:line` was opened.
- **The bucket edges and the depth interval: MEDIUM.** Arithmetic against stated targets, offered as the
  argument the Discretion list demands rather than as a measurement. Both are cheap to change.
- **Pitfall 4's recommended shape (b): MEDIUM.** It is my extension of D-26 into a case D-26 does not
  address. The *requirement that the plan decide* is HIGH — SC1's most ordinary provocation goes through it.
- **Pitfall 12's scope: MEDIUM.** Whether a database role falls inside AC-10 is a reading of the spec, not
  a fact. The underlying grant is a fact and is verified.

**Deviations and ids:**

- **This document consumes no `D-NN` and creates no `OQ-NNN`.** CONTEXT allocated D-26…D-45 and OQ-022…
  OQ-026; per Phase 2's precedent the OQ files are written by the plan or executor that reaches each
  conflict.
- **One conflict was found that has no allocated id** — Pitfall 12, `prope_report`'s `SELECT` on
  `ledger.call_body` against `security_requirements`' *"no export"* clause and ADR-0037. It fits as a
  second clause on **OQ-025**; if the planner wants a file of its own, the id must come from the
  orchestrator, because OQ-027 may belong to the phase being planned in parallel.

**Research date:** 2026-08-10
**Valid until:** 2026-09-09 (30 days). Re-check sooner if SQLAlchemy publishes a 2.0.52 touching
`insertmanyvalues`, if `prometheus-client` publishes 0.27 (the content-type constants are already moving),
or if OQ-013 resolves — `call_body`'s retention, and therefore Pitfall 12's disposition, inherits its answer.
