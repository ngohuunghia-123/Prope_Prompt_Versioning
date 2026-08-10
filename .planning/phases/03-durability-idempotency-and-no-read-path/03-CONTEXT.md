# Phase 3: Durability, idempotency, and no-read-path - Context

**Gathered:** 2026-08-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 shipped the write path and named its own hole out loud: a broker outage loses records, a
redelivery dead-letters, and the counters that would make either visible are four out of eighteen.
This phase closes the hole and **closes milestone M1**. After it, `prope_call_ledger_metadata_dropped_total`
means what ADR-0041 says it means — both the broker and the database were gone — and nothing else.

**Delivers:**
- **The direct-write fallback** at `publish_record`'s failure branch: on a failed, nacked, timed-out or
  unavailable publish, the metadata row is written straight to PostgreSQL, counted by
  `fallback_direct_write_total`, and the body is dropped and counted (CL-01, ADR-0041)
- **The idempotent upsert on the caller-generated `call_id`**, and with it the property CL-02 is
  actually about: a redelivered record does not move `ledger.workspace_spend` (A-099)
- **A per-body size cap** — the only byte bound anywhere on the path, since A-149's queue bound is a
  message count
- **`prope_call_ledger_duplicate_call_id_total` and `prope_call_ledger_redelivered_total`**, the pair
  the `LedgerDuplicateCallIds` alert reads together
- **The full observability set**: eighteen metrics (the lock's seventeen plus T-005's `dlq_depth`), a
  `/metrics` exposition surface on `app`, and the six declared alert rules as a file asserted against
  the registry
- **`prope_call_ledger_oldest_body_age_seconds`** — the gauge that measures the *data*, deferred out of
  Phase 2 and routed here by `02-VERIFICATION.md`
- **CL-07's claim**: the fail-open branch shipped in Phase 2 becomes a requirement this phase proves,
  with the declared `ceiling_check_total{result}` counter behind it
- **The no-body-read-path sweep** (CL-10 / AC-10) across three layers — the assembled route table, the
  module's internal Python surface, and the grant matrix
- **The load and chaos suites**: 50 rps with `enqueue` p95 < 1 ms measured in the caller's process at
  80% handoff depth, and a provoked broker outage that loses nothing
- **CR-01** (unbounded `retention_days` → `OverflowError` → dead-letter) and **CR-02** (`run_publisher`
  returning with up to 512 records buffered, uncounted), both carried forward from `02-VERIFICATION.md`

**Fixed out of scope by ROADMAP (do not absorb):**
- **The gateway** that will actually call `enqueue` under load — Phases 19–21 (GATE-11 is CL-01's other
  half). This phase proves the seam from call-ledger's own tests, as Phase 2 did
- **The evaluation module** that calls `price_usage`, `check_spend_ceiling` and `get_run_totals` —
  Phases 16–18
- **`access.list_workspaces()`** and with it the cold-workspace half of the retention sweep — **Phase 7**
  (Broken Window #3; `run_worker` already takes the enumerator as a parameter, so Phase 7 replaces an
  argument). `oldest_body_age_seconds` inherits that blind spot and D-43 says so rather than hiding it
- **The cross-module route-table assertion** in its full form — **Phase 23**, when eight modules are
  mounted (PITFALLS §5). This phase writes the single-module form so Phase 23 extends a test
- **The deployment stack** — Prometheus scrape config, Grafana dashboards, the compose file, Caddy,
  the `json-file` log caps. Owns no milestone (PITFALLS §4). This phase ships instrumentation and a
  rules file; it does not ship the service that reads them

**Requirements:** CL-01, CL-02, CL-07, CL-10, CL-12.

**CL-11 disposition, stated rather than left silent.** `REQUIREMENTS.md` files CL-11 under Phase 1 /
Pending, but both its clauses are built and green: the first (`unknown` tokens are NULL, never zero) by
`tests/unit/test_unknown_usage_never_zero.py` in Phase 1, the second (the unknown count reported
alongside the total) by `tests/integration/test_run_totals.py` in Phase 2, where `seams.py:569` records
that it built the function and deliberately claimed no requirement. **This phase does not split the id
and does not remap the row.** Requirement ids are stable (ORCHESTRATION §1) and re-attributing one
across two phases is a bookkeeping decision only the developer may take. What Phase 3 does instead: its
own suite re-asserts both clauses from tests it runs itself, and `03-UAT.md` carries the tick
recommendation as a numbered human-verification item — the same posture Phase 1 used for CL-08.

</domain>

<decisions>
## Implementation Decisions

Numbering continues from Phase 2's D-09…D-25. The project numbers continuously and never restarts.
**This phase consumes D-26 through D-45.**

### The direct-write fallback — CL-01, ROADMAP SC1

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

### Idempotency — CL-02, ROADMAP SC2

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

### The body store has no reader — CL-10, ROADMAP SC4

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

### The eighteen metrics and the six alerts — T-005's sweep

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
  today, on the order of a hundred nanoseconds inside a 1 ms budget. **`occurred_at` IS a registered
  field** — `docs/architecture/interfaces.md:667` lists it under INT-018's *"Envelope carries (A-142
  §5)"* — and the earlier form of this sentence, which said it "crosses no registered contract", was
  wrong and is corrected here. What is true is narrower and is the reason the decision still stands:
  the field's **presence, name and type are unchanged**, A-142's additive-only evolution rule is
  untouched, and call-ledger owns both producer and consumer today, so no other module's code changes.
  What *does* change is the **semantic** — the value becomes "when the caller handed the record over"
  rather than "when the publisher published it" — and the gateway inherits that meaning in Phases
  19–21. INT-018 is named in `interfaces.md`'s own residual-risk block as *"the only shape in Prope
  that can be in flight across a deploy"*, so the new meaning is written into `enqueue()`'s docstring
  rather than left to be inferred (plan 03-01, Task 2).
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

### Proving it — CL-12, ROADMAP SC5, and the chaos suite

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
     RabbitMQ container for the chaos module (`.planning/todos/pending/2026-08-10-reuse-a-long-lived-rabbitmq-for-broker-tests.md`
     already records that a broker boot costs 10–20 s and that the cost repeats across every subagent's
     pytest run — paying it again per chaos module, for a failure a closed channel reproduces exactly,
     is the wrong trade).

### Claude's Discretion

These are **open, not decided**. Resolve them from the lock file, the interfaces registry and this
phase's success criteria, and **state the resolution in the plan**:

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

These are authoritative and read-only. Per `.planning/BSP-LINK.md` and ORCHESTRATION §5: do not edit
anything under `docs/`. A spec that disagrees with the code is information — raise an `OQ-NNN` naming
the exact lock-file, interfaces or ADR field and the conflict; do not patch the spec to agree. **Five
such conflicts are already known and are named in D-28, D-39, D-42 and the Discretion list:
`OQ-022`…`OQ-026`.**

### The module spec — read first, and read the amended blocks not the literal ACs
- `docs/modules/call-ledger.lock.yml`
  - **`failure_modes` — all eight rows.** Row 2 is the one this phase is about, and note that its
    *replacement* scenario is written inside the `scenario:` block while the stale spill scenario is
    retained below it as `original_scenario:` — plan against the first. Row 3 (redelivery), row 7
    (fail-open), row 8 (oversize body) are the other three this phase closes
  - **`observability_requirements.metrics`** — seventeen names with their label sets; `log_fields` and
    its never-logged list; **`alerts` — all six**, including `LedgerRetentionOverdue`'s written reason
    for measuring the data rather than the job, and `LedgerDuplicateCallIds`'s "read the two counters
    together" correction
  - **`security_requirements`** — the no-read-path clauses, and **T-005**, whose mitigation names
    `prope_call_ledger_dlq_depth` and its alert; **T-006**, which is why `price_table` and
    `call_record` have the grants they do
  - **`test_plan`** — `unit`, `integration`, `contract`, `load`, `security`, `chaos`. The `security`
    entry spells out T-005's and T-006's assertions verbatim; the `chaos` entry contains two stale
    clauses (see PITFALLS below)
  - **`acceptance_criteria`** — AC-7, AC-10, AC-12 literally; **AC-1 and AC-2 only through the amended
    comment block above them**
  - **`performance_requirements`** — the enqueue p95, the ≥500 records/sec drain, the p95 < 2 s /
    p99 < 10 s lag, the 60 s backlog drain after a consumer restart
- `docs/architecture/interfaces.md`
  - **INT-018** — the failure table is the specification of this phase: what each of the five failure
    rows does, that a redelivery *cannot* move a workspace's spend, and A-139's honestly-recorded
    remaining loss window
  - **INT-019** — *"idempotent on `call_id` — the same upsert INT-018's drain uses"*, which is why
    D-35's counter lives in `write_records` rather than in the drain
  - **INT-020** — the one seam in Prope that fails open, and *"the counter is the control"* (CL-07)
  - **INT-030** — readiness differs per module; the row that bears on D-39's `/metrics` placement

### The two ADRs the ROADMAP names
- `docs/adr/0041-broker-first-with-a-direct-write-fallback.md` — the decision, the three rejected
  alternatives (**read the spill-file rejection: it is the argument D-27 reuses**), the consequences
  list naming which metrics were deleted and which replaced them, and the follow-up note recording
  A-139
- `docs/adr/0018-body-store-has-no-read-path-in-the-mvp.md` — why the absence is *asserted against the
  route table* rather than understood, and the four rejected ways of building a reader

### Observability and the runtime it assumes
- `docs/adr/0030-observability-is-prometheus-and-grafana.md` — `prometheus-client` directly, not OTel;
  **the label-cardinality rule and its explicit never-list**; the four numbers the one Grafana dashboard
  holds. Bears on D-39, D-42, D-43 and OQ-023
- `docs/adr/0033-one-vm-docker-compose-and-caddy.md` — the seven-service table (`prometheus` and
  `grafana` are two of them), the 80 GB / 8 GB sizing, and **the "roughly 10 KB per call" figure D-29's
  cap is argued against**
- `docs/adr/0028-rabbitmq-carries-the-asynchronous-work.md` — *"`worker` consumes and never serves
  HTTP"*, which is D-17 and therefore OQ-026's other side

### Pricing, tenancy and the writer this phase edits
- `docs/adr/0019-cost-is-priced-once-at-write-time.md` — why D-33 refuses `DO UPDATE`
- `docs/adr/0040-the-ledger-writer-batches-per-workspace.md` — one transaction per workspace, and
  *"the fallback write obeys ADR-0040 for free — a single record for a single workspace"*
- `docs/adr/0045-every-table-is-tenant-scoped-unless-declared-global.md` — the zero-rows behaviour that
  makes D-43's gauge a per-workspace loop rather than one query
- `docs/adr/0035-tenant-isolation-is-a-database-policy.md` — `SET LOCAL app.workspace_id` per
  transaction, which the fallback inherits unchanged

### Known gaps this phase must plan around
- **`.planning/research/PITFALLS.md` §2 — the one that governs this phase.** call-ledger AC-1 and AC-2
  are stated against an in-process queue and a spill file, **neither of which exists**. Plan against
  the restated form: AC-1 = *"RabbitMQ unreachable"*, AC-2 = *"every message redelivered after an
  unacknowledged consumer restart"*. The ROADMAP's SC1 and SC2 are already the restated form and are
  the safer text to plan from. The same section flags gateway AC-11 as owed the same restatement —
  that is Phase 21's, not this phase's
- **`.planning/research/PITFALLS.md` §5** — the cross-module route-table assertions cannot run before
  Phase 23. D-38 writes the single-module form deliberately
- **`.planning/research/PITFALLS.md` §4** — the deployment stack owns no milestone. This is why D-44
  ships a rules file and not a service, and why OQ-026 has nowhere to route its answer today
- `.planning/ORCHESTRATION.md` §3 and §4 — the standing engineering facts, and **CR-01 / CR-02, which
  this phase owns** (D-37, D-31). §3 also carries Broken Window #4 (`assembled_routes()`), which D-38
  depends on
- `.planning/phases/02-seams-enqueue-the-broker-drain-and-the-ceiling/02-CONTEXT.md` — D-09…D-25, and
  especially **D-11** (the fallback inherits no settings query — D-28 is how that stays true), **D-16**
  (readiness is the database alone and is final), **D-21** (count-and-drop, which this phase replaces)
  and **D-25** (the handoff, at whose failure site D-26 lands)
- `.planning/phases/02-seams-enqueue-the-broker-drain-and-the-ceiling/02-VERIFICATION.md` — the deferred
  table routes three items here; the anti-pattern table is CR-01 and CR-02 with the evidence already
  gathered
- `.planning/phases/02-seams-enqueue-the-broker-drain-and-the-ceiling/deferred-items.md` — the
  `ruff format --check` broken window (do not fix), the boilerplate Dockerfile/compose (do not extend),
  and the `LOGGABLE_FIELDS` `job` entry that 02-04 closed
- `.planning/todos/pending/2026-08-10-reuse-a-long-lived-rabbitmq-for-broker-tests.md` — the broker
  boot cost, the empirical finding that testcontainers 4.15.0 has no `with_reuse()`, and the
  teardown-only `purge_queues` crash-leak. D-45's chaos rejection rests on it

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/prope/call_ledger/writer.py` — **`write_records(session, records, *, retention_window)` takes a
  `Sequence`, not a single record**, and there is one implementation on purpose. This is the file D-33
  edits: `INSERT_CALL_RECORD` (line 64), `INSERT_CALL_BODY` (line 88) and `UPSERT_WORKSPACE_SPEND`
  (line 129) are all `text()` constructs executed with executemany, and the month buckets are
  accumulated in the per-draft loop *before* the insert (line 338). D-33 inverts that order. The
  existing `WriteResult` already carries `priced` / `unpriced` / `unknown` / `bodies_written`, so the
  duplicate count is a fifth field on a type that already exists.
- `src/prope/call_ledger/enqueue.py:172-254` — **`publish_record`'s docstring already names its own
  successor**: *"Phase 3's direct-write fallback goes on the failure branch below. Not beside it, not
  in the caller."* Four `return False` sites, one per D-26 call site. `_classify_publish_failure`
  (line 146) is the closed three-value set and does not change.
- `src/prope/call_ledger/drain.py` — `classify_write_failure` (line 120) is the CR-01 surface;
  `_retry_group_one_at_a_time` (line 285) is the one-at-a-time ladder D-27 declines to duplicate in
  `app`; `_parse` (line 229) and the retry ladder are the two `metadata_dropped_total` increments D-30
  removes; the `on_window` observer (line 169) is the existing seam a lag histogram can be timed
  around.
- `src/prope/call_ledger/models.py:56-155` — the six tables as Core `Table` objects on one shared
  `MetaData`. This is what makes D-33's move from `text()` to
  `sqlalchemy.dialects.postgresql.insert(...)` a change of construct rather than a new modelling layer.
- `src/prope/supervisor.py` — `supervise(jobs, stopping)`, `interval_job`, `install_stop_handlers`.
  D-32 gives it a second host process and D-42 gives it a third job. D-14 built it for exactly this.
- `src/prope/observability.py` — five counters (the module docstring says *"Phase 2 wires four
  counters"* and there are five; the sweep is rewriting this file anyway and should correct it), the
  `LOGGABLE_FIELDS` allow-list, and `configure_logging()`. The docstring's paragraph explaining that
  `metadata_dropped_total` *will not stay 0 in Phase 2* is the paragraph this phase gets to delete.
- `tests/conftest.py` — the session-scoped Postgres and RabbitMQ containers, three role-scoped engines,
  `truncate_ledger` and `purge_queues` (both autouse, both teardown-only), and `reset_handoff()` between
  tests. `purge_queues` opts in by fixture graph, so a test that never asks for `amqp_url` pays nothing.
- `tests/architecture/test_route_table.py` — `EXPECTED_ROUTES` as a literal seven-entry frozenset,
  `FORBIDDEN_FIELD_NAMES`, and the OpenAPI walk. D-38 extends this file and D-39 changes the count.
- `src/prope/session_auth.py:247` — `assembled_routes(application)`, which exists because
  `include_router` appends one lazy `_IncludedRouter` and a naive `app.routes` walk asserts vacuously.
  **Use it. Broken Window #4 is standing.**

### Established Patterns

- **Build database-first** — but D-37 is the documented exception, and the plan must say why: the
  `OverflowError` happens in the client before a statement exists, so no `CHECK` can carry it. Naming
  the exception is what keeps the rule intact.
- **Assert against the live engine, not the driver.** T-006's REVOKE test, the RLS zero-rows test, the
  ADR-0045 coverage walk, and `tests/broker/test_declared_arguments.py` reading the queue arguments back
  from RabbitMQ's management API all do this. D-38's third layer and D-45's chaos suite inherit it.
- **Prove the absence, do not assume it.** `tests/security/test_eval_no_body_boundary.py` contains
  `test_the_database_carries_no_guard_and_a_hand_written_body_lands` — a test whose whole job is to show
  that the guarantee is `write_records`' refusal and nothing else. D-38's grant-matrix layer is the same
  move for `call_body`.
- **The alert measures the data, not the job.** D-43 is the only place in this phase where that rule is
  hard to honour, and the honest answer is a partial close with the residue named.
- **Counters are controls, and an unwatched control is an off switch.** `observability.py:107-124`
  argues it for `ceiling_failed_open_total`. D-39 is the same argument one layer out: a counter no
  scraper reaches is a counter nobody watches.
- **Never zero, and no fourth state.** `write_records` has no default branch. D-40's
  `missing_version_id_total` refusal follows it — name what is missing, do not substitute.
- Module docstrings carry the *why* at length. `enqueue.py`, `drain.py`, `topology.py` and `worker.py`
  are the density to match, and several of their paragraphs are this phase's to rewrite rather than to
  leave standing as descriptions of a gap that has closed.

### Integration Points

- **`app` acquires a database write path it did not have.** ADR-0041 names this consequence explicitly.
  `app.state.sessionmaker` already exists (built in `lifespan`, `app.py:176`) and is currently used only
  by the management routes via `get_sessionmaker`; D-26 binds it into the publisher at the same place.
- **`worker` acquires a third resident.** `worker.py:73-80` names the two by constant
  (`JOB_CALL_RECORD_DRAIN`, `JOB_EXPIRED_BODY_DELETION`) and the module docstring counts the later
  arrivals. D-42 adds one and both must be updated together — the job names are `LOGGABLE_FIELDS`'
  `job` values and are a closed set fixed in source.
- **`EXPECTED_ABSENT_SCHEMAS` in `tests/architecture/test_tenant_coverage.py` is untouched by this
  phase.** No schema is created here; Phase 7 is still the first that must shrink it.
- **No new table and no migration are required by any decision above.** If a plan finds it needs one,
  that is information — the `ledger` schema is Phase 1's and `data.owns` already carries an OQ-018
  deviation.
- **Still no inbound or outbound module edges.** `dependencies: []` and `outputs: []` hold through the
  close of M1. The gateway and evaluation remain the callers these seams are built for and neither
  exists; the contracts are proven from call-ledger's own tests, as in Phases 1 and 2.
- **Standing environment facts:** `docker` is not on the default bash PATH (`export PATH="/c/Program
  Files/Docker/Docker/resources/bin:$PATH"`); testcontainers reaches the daemon without it;
  `loop.add_signal_handler` is unimplemented on Windows, so every stop path is a directly-settable
  `asyncio.Event`; `uv run ruff format --check` fails repo-wide and is **not** this phase's to fix.

</code_context>

<specifics>
## Specific Ideas

- **The upsert's real subject is `ledger.workspace_spend`, not `ledger.call_record`.** A redelivery
  landing twice in `call_record` is refused by the primary key with or without this phase. What
  redelivery actually corrupts is the aggregate that `check_spend_ceiling` reads, because the aggregate
  is maintained inside the writer's transaction (A-103) and would be incremented for a row that was not
  inserted. That is why D-33 turns on `RETURNING` rather than on `ON CONFLICT`: the conflict clause
  makes the insert survivable, and only the returned set makes the aggregate correct. A plan that stops
  at `ON CONFLICT DO NOTHING` will pass a "the record appears once" test and fail CL-02.

- **`prope_app` holds `UPDATE` on `call_record` and deliberately not on `call_body`, and that asymmetry
  decides the statement shape.** `0002_call_record.py:190` grants `SELECT, INSERT, UPDATE`;
  `0003_ledger_tables.py:252` grants `SELECT, INSERT, DELETE` with the comment *"No UPDATE: bodies are
  written once and deleted."* So `DO UPDATE` is available on one table and impossible on the other. Two
  idempotency semantics in one function is the thing to refuse, and refusing it happens to give the
  answer ADR-0019 wanted anyway.

- **The fallback writes no body, and that is what keeps D-11's promise honest.** `expires_at` is stamped
  only when a `call_body` row is built, so the metadata-only path never touches
  `ledger.workspace_retention` — not by discipline, but because there is nothing on that path for a
  retention window to be applied to. Any plan that reaches for the retention resolver in `app` has
  taken a wrong turn somewhere upstream.

- **A dead-letter and a drop are different events, and Phase 2 conflated them.** `drain.py` increments
  `metadata_dropped_total` for records it puts in the DLQ. After the fallback, that counter is the page
  that means both stores are gone; leaving the dead-letter increments in place would make it fire on one
  malformed envelope, and a page that fires on a data bug is a page people learn to close. D-30 is a
  removal, and removals are the ones that get skipped.

- **`prometheus_client`'s registry is per process and Prope has two.** This is the single largest
  structural surprise in the phase and it is not solvable inside the phase's boundaries: D-17 says
  `worker` serves no HTTP and D-17 is *derived from ADR-0028*, not chosen, so it is not this phase's to
  reverse. Ship the instrumentation, ship `/metrics` on `app`, name the twelve metrics that are
  unscrapable or partial, and raise OQ-026. **Do not solve it by opening a port on `worker`.**

- **A `/metrics` mounted as an ASGI sub-application is invisible to `assembled_routes()`.** FastAPI's
  `mount` produces a `Mount`, not an `APIRoute`, so it carries no `dependant` and appears in neither the
  route-table assertion nor the OpenAPI schema. That is precisely the shape AC-10 exists to refuse — a
  route the table cannot see. Whatever shape is chosen must be visible to the assertion, or asserted
  absent from it on purpose with the reason written down.

- **`prometheus_client`'s default histogram buckets cannot measure either of this phase's latency
  claims.** They start at 5 ms; the enqueue target is p95 < 1 ms, so every observation would land in the
  first bucket and the p95 would read as "somewhere under 5 ms" forever. A metric that cannot fail its
  own target is not a measurement.

- **`text()` with executemany does not return per-row results.** D-33 needs
  `sqlalchemy.dialects.postgresql.insert()` over the existing `models.call_record` Table to get
  insertmanyvalues plus `RETURNING`. `tests/architecture/test_no_sql_interpolation.py` is the gate the
  rewritten statement must still pass, and the Core construct makes that easier rather than harder.

- **`occurred_at` is stamped in the wrong place today for the metric that is about to be added.** It is
  set in `publish_record`, so `write_lag_seconds` measured from it would exclude exactly the handoff
  interval the fallback exists to protect. Moving the stamp into `enqueue()` is three lines and it is
  the difference between a metric that measures the system and one that measures the broker.

- **SC1's thousand calls do not need a fast fallback, and the arithmetic is worth doing before the
  design.** One record per transaction against a local PostgreSQL sustains roughly 650 writes/sec
  against a 50 rps arrival rate. The handoff holds 512. There is no pressure here, and a plan that
  batches the fallback is optimising a path whose whole risk is that it is rarely exercised.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Two items are **partially** closed and carried forward
with their residue named rather than left to be discovered:

- **`oldest_body_age_seconds` is a partial close (D-43).** The gauge ships and measures the data, but
  only across the workspaces `ObservedWorkspaces` has enumerated. The cold-workspace half needs
  `access.list_workspaces()` and is **Phase 7's**, exactly as `02-VERIFICATION.md` deferred item 4
  already records. `run_worker` takes the enumerator as a parameter, so Phase 7 replaces an argument.
- **Twelve of the eighteen metrics are unscrapable or partial from `app`'s `/metrics` (D-39).** The
  answer is `OQ-026`'s and it may land in the deployment stack, which owns no milestone.

Recorded so a planner does not mistake them for gaps, these are fixed ROADMAP boundaries rather than
omissions:

- The **gateway** that will call `enqueue` under real load, and **GATE-11** — CL-01's other half — are
  **Phases 19–21**. The **evaluation** module that calls `price_usage`, `check_spend_ceiling` and
  `get_run_totals` is **Phases 16–18**. Neither exists; both contracts are proven from call-ledger's own
  tests, which is the posture Phases 1 and 2 already established.
- The **cross-module route-table assertion** in its full form is **Phase 23** (PITFALLS §5). D-38 writes
  the single-module form using the shared helpers so Phase 23 extends it.
- The **deployment stack** — Prometheus and Grafana as running services, the scrape config, the
  dashboard, the compose file, Caddy, the `json-file` log caps — **owns no milestone** (PITFALLS §4).
  D-44 ships a rules file into a repository, not a rule into a Prometheus.
- The **React SPA** that would consume INT-028's routes owns no milestone either (PITFALLS §3). Neither
  it nor the deployment stack blocks this phase; both need a user decision.
- **OQ-013** remains unresolved and rated Critical, and **A-020 holds the line** — no real corporate
  prompts until the security baseline is signed off. This phase makes the answer cheaper to apply and
  does not contain it.

</deferred>

---

*Phase: 3-durability-idempotency-and-no-read-path*
*Context gathered: 2026-08-10*
*Decisions consumed: D-26 through D-45. Open-question ids allocated: OQ-022 through OQ-026.*
