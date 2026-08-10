---
phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
plan: 01
subsystem: infra
tags: [rabbitmq, aio-pika, amqp, asyncio, pydantic, prometheus, structlog, postgres, rls, testcontainers]

# Dependency graph
requires:
  - phase: 01-data-model-pricing-and-retention
    provides: "write_records (the one write path), workspace_transaction (the tenant seam), CallRecordDraft/CallBodyDraft, DEFAULT_RETENTION_WINDOW, and the session-scoped PostgreSQL 17 test rig"
provides:
  - "prope.broker.topology — the one queue/DLQ declaration both processes call (D-24), with A-149's full arguments and the classic-durable queue type declared explicitly"
  - "prope.broker.connection — connect_robust plus a single confirm-mode channel with on_return_raises=True"
  - "prope.call_ledger.envelope — INT-018's wire contract, and the V5 source gate on workspace_id"
  - "prope.call_ledger.enqueue — D-25's bounded handoff and the background publisher's three-branch confirm classification (D-21)"
  - "prope.call_ledger.drain — D-15's size-or-time window, ADR-0040's per-workspace grouping, per-group commit and per-group ack, and the permanent/transient failure classification"
  - "prope.observability — the four Phase 2 counters and the structlog JSON configuration"
  - "Settings.broker_url (PROPE_BROKER_URL) on the existing Settings class"
  - "tests/conftest.py — D-22's session-scoped RabbitMQ 4.3 container, amqp_url, management_url, and the per-test queue purge"
  - "tests/architecture/test_no_sql_interpolation.py — the source gate that closes Phase 1's WR-06"
affects: [02-02-retention-settings, 02-03-worker-supervisor, 02-04-seams-and-routes, 02-05-management-routes, 03-fallback-and-upsert, 19-21-gateway]

actuals:
  tokens: 33074
  tasks: 3
  commits: 2

tech-stack:
  added:
    - "aio-pika==9.6.2 (over 10.0.1 — aiormq 7 is a one-month-old major on the durability path)"
    - "testcontainers[postgresql,rabbitmq]==4.15.0 (pulls pika transitively as RabbitMqContainer's readiness probe)"
  patterns:
    - "One topology module both processes declare from (D-24)"
    - "Hand off, publish in the background, classify the confirm into a closed three-value set (D-25, D-21)"
    - "Size-or-time window, group by workspace, one transaction per group, ack per group after that group's commit"
    - "A pydantic model as the process-boundary source gate on every value that reaches set_config"
    - "Permanent/transient failure classification defaulting to permanent, because a classic queue has no delivery limit"
    - "An ast walk over src/ as a source gate, rather than a docstring claim"

key-files:
  created:
    - src/prope/broker/topology.py
    - src/prope/broker/connection.py
    - src/prope/call_ledger/envelope.py
    - src/prope/call_ledger/enqueue.py
    - src/prope/call_ledger/drain.py
    - src/prope/observability.py
    - tests/broker/test_enqueue_reaches_a_committed_row.py
    - tests/broker/test_declared_arguments.py
    - tests/broker/test_publish_confirm_failures.py
    - tests/broker/test_drain_failure_classification.py
    - tests/architecture/test_no_sql_interpolation.py
  modified:
    - pyproject.toml
    - tests/conftest.py
    - src/prope/db/engine.py
    - src/prope/db/session.py

key-decisions:
  - "prope.call_record is a CLASSIC DURABLE queue, not quorum (Task 1 checkpoint, user-selected): reject-publish-dlx is the only overflow mode that both dead-letters AND nacks the publisher, and that nack is the signal D-21 counts and ADR-0041's Phase 3 fallback consumes"
  - "x-queue-type: classic is DECLARED explicitly rather than left to the broker default, so a drifting default cannot silently produce a queue that reject-publish-dlx does not exist on"
  - "One long-lived robust connection with a single confirm-mode channel, not a pool — D-25 puts exactly one publisher task on it"
  - "on_return_raises=True on the publisher channel: with aio-pika's default an unroutable publish resolves as a SUCCESS, making `unroutable` an unreachable label"
  - "HANDOFF_MAXSIZE = 512 — 50 rps x 2 s is 100 records; 512 is ~10 s of headroom and bounded, because an unbounded queue converts a broker outage into memory growth on the gateway's response path"
  - "WINDOW_SIZE = 500, WINDOW_MS = 250, prefetch = WINDOW_SIZE — at 50 rps T dominates and N is irrelevant; N only binds during a backlog, where >=500/sec against a 250 ms floor needs N >= 125"
  - "Ack per GROUP, not per window, and never multiple=True — the window is N transactions and two workspaces' delivery tags interleave"
  - "classify_write_failure defaults to PERMANENT — a classic queue has no x-delivery-limit, so an unclassified requeue is an infinite loop (T-02-06)"
  - "A unique violation on call_id is PERMANENT and dead-letters, rather than being treated as 'already written, ack it' — the latter is CL-02's guarantee arriving early under another name"
  - "Only four counters this phase, no /metrics endpoint, no alert rules — the 17-metric set is Phase 3's T-005 sweep"

patterns-established:
  - "Queue arguments carry a named sub-heading per argument in the module docstring, matching alembic/ddl.py's per-token justification style"
  - "Log redaction is a POSITIVE allow-list of loggable fields (LOGGABLE_FIELDS), never a deny-list of field names"
  - "A tuning constant gets a #: comment carrying the arithmetic that chose it, so changing it is a visible act"
  - "An observation seam (on_window, on_chunk) is keyword-only, defaults to None, and is not a branch on the production path"
  - "Broker tests assert through migrate_engine, never through the code under test — a drain that acks and writes nothing looks healthy"

requirements-completed: [CL-06]

coverage:
  - id: D1
    description: "A call record handed to enqueue() reaches ledger.call_record through the broker and the drain, and enqueue() returns without awaiting the publisher confirm"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/broker/test_enqueue_reaches_a_committed_row.py::test_one_record_reaches_a_committed_ledger_row"
        status: pass
    human_judgment: false
  - id: D2
    description: "enqueue() never raises into its caller under any branch — full handoff buffer, unroutable publish, nacked confirm, confirm timeout, or a broker that is not running"
    requirement: CL-06
    verification:
      - kind: integration
        ref: "tests/broker/test_enqueue_reaches_a_committed_row.py::test_enqueue_returns_normally_with_no_broker_running"
        status: pass
      - kind: integration
        ref: "tests/broker/test_enqueue_reaches_a_committed_row.py::test_enqueue_returns_normally_when_the_handoff_is_full"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_enqueue_returns_normally_through_every_failure_branch"
        status: pass
    human_judgment: false
  - id: D3
    description: "The declared arguments of prope.call_record and prope.call_record.dlq read back from the broker match A-149 exactly, and one changed argument per key is proven to be refused"
    verification:
      - kind: integration
        ref: "tests/broker/test_declared_arguments.py (9 tests: management-API read-back for both queues, DLQ carries no DLX of its own, exact-redeclare positive control, 5 negative controls, non-durable refusal)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The drain opens exactly one workspace_transaction per distinct workspace_id in a window and acks each group only after that group's transaction has committed"
    verification:
      - kind: integration
        ref: "tests/broker/test_drain_failure_classification.py::test_one_unwritable_record_does_not_discard_its_batch_mates"
        status: pass
      - kind: integration
        ref: "tests/broker/test_drain_failure_classification.py::test_the_retention_resolver_is_called_with_exactly_the_workspace_id"
        status: pass
    human_judgment: false
  - id: D5
    description: "A permanently-unwritable record is dead-lettered alone and its batch-mates still commit (CR-01's second named test)"
    verification:
      - kind: integration
        ref: "tests/broker/test_drain_failure_classification.py::test_one_unwritable_record_does_not_discard_its_batch_mates"
        status: pass
    human_judgment: false
  - id: D6
    description: "A broker envelope that fails validation is dead-lettered and never reaches workspace_transaction"
    verification:
      - kind: integration
        ref: "tests/broker/test_drain_failure_classification.py::test_an_invalid_envelope_dead_letters_without_opening_a_transaction"
        status: pass
      - kind: unit
        ref: "tests/broker/test_enqueue_reaches_a_committed_row.py::test_envelope_refuses_the_values_that_must_never_reach_set_config"
        status: pass
    human_judgment: false
  - id: D7
    description: "No log line and no metric label emitted by the publish or drain path contains a request body, a response body or a provider-credential-shaped value"
    verification:
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_no_marker_reaches_a_log_record_or_a_metric_label[body_marker]"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_no_marker_reaches_a_log_record_or_a_metric_label[credential_shaped_marker]"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_workspace_id_is_never_a_metric_label"
        status: pass
    human_judgment: false
  - id: D8
    description: "Every text(...) call under src/prope/ takes a plain string constant, asserted by a walk over the source (closes Phase 1's WR-06)"
    verification:
      - kind: unit
        ref: "tests/architecture/test_no_sql_interpolation.py"
        status: pass
    human_judgment: false
  - id: D9
    description: "The queue-type selection recorded at the Task 1 checkpoint is the one written into WORK_QUEUE_ARGUMENTS, and the Phase 2 loss window is an acceptable one-phase posture before CL-01 lands"
    verification: []
    human_judgment: true
    rationale: "The plan's own <human-check>. Whether a deliberately lossy one-phase window is an acceptable posture is a judgement about risk appetite, not a property any test can assert. The mechanical half (classic-durable is what is declared) IS asserted by test_declared_arguments.py's x-queue-type negative control."

# Metrics
duration: 105min
completed: 2026-08-10
status: complete
---

# Phase 02 Plan 01: Seams — enqueue, the broker drain, and the ceiling Summary

**One call record now travels enqueue() → a bounded in-process handoff → a confirmed publish onto a classic durable `prope.call_record` → a windowed drain → one `workspace_transaction` per workspace group → a committed `ledger.call_record` row, with the queue's A-149 arguments read back from the broker and each of the three publish-failure reasons provoked against a live RabbitMQ 4.3 rather than mocked.**

## Performance

- **Duration:** ~105 min (including one Docker Hub rate-limit stall)
- **Tasks:** 3 (Task 1 resolved at a user checkpoint; Tasks 2 and 3 executed)
- **Files created/modified:** 19
- **Test suite:** 141 passed, 0 failed

## Accomplishments

- **The broker seam call-ledger will live on for the next 22 phases exists and is proven end to end.** Not sketched, not mocked: a real RabbitMQ 4.3 testcontainer joins the real PostgreSQL 17 one (D-22), and the tracer asserts the committed row through `migrate_engine` — the owner role, subject to no policy — rather than through the drain's own return value.
- **The one-way decision was made correctly and is now asserted, not intended.** The queue's declared arguments cannot be changed in place; D-23 required the read-back to land in the same phase as the declaration, and it did. The management HTTP API supplies the positive assertion (literally "reads them back from the broker"), and a per-argument non-passive redeclare supplies five negative controls.
- **`enqueue()` demonstrably never raises**, across a full buffer, an unroutable publish, a nacked confirm, a confirm timeout, and no broker running at all.
- **CR-01's second named test is built and green:** a five-record group containing one record `write_records` refuses leaves exactly four rows committed and exactly one message on the DLQ.
- **Phase 1's WR-06 is closed.** `src/prope/db/session.py` claimed "a source gate asserts it" and no gate existed. There is one now — an `ast` walk over every module under `src/prope/`, with a discovered file list and an empty, explicit `ALLOWED` list — and the docstring names it.
- **A-046 is asserted over two markers, not one.** A body-shaped marker proves the code is not logging the field it knows is a body; a credential-shaped `sk-`-prefixed marker on `error_class` — a field the publish path never inspects — proves it is not logging a field it never looked at.

## Task Commits

1. **Task 1: Queue type — classic durable, or quorum** — no commit (a `checkpoint:decision`; the decision is recorded in `topology.py`'s docstring, at `WORK_QUEUE_ARGUMENTS["x-queue-type"]`, and in this SUMMARY)
2. **Task 2: End-to-end — one call record from enqueue() to a committed ledger row** — `c15b647` (feat)
3. **Task 3: The broker's declared contract, the three failure reasons, and the poison batch** — `01bfc65` (test)

## The Task 1 decision, and why

**Selected: `classic-durable`.**

A-149 requires that overflow **dead-letters rather than drops**. `x-overflow: reject-publish-dlx` is the only overflow mode that both dead-letters the overflowing message *and* `basic.nack`s the publisher — and that nack is precisely the signal D-21 counts and that ADR-0041's Phase 3 direct-write fallback consumes. **Quorum queues do not support `reject-publish-dlx` configurations at all**; their only overflow mode is `drop-head`, which dead-letters the *oldest* record and never nacks. Under quorum, A-149 would be satisfied in the letter and not in substance, and the Phase 3 fallback would never fire on overflow. A single-node host (ADR-0033) also buys nothing from Raft replication, and classic mirroring was removed in RabbitMQ 4.0, so "classic" no longer implies "mirrored" and carries no deprecation smell.

**The accepted cost, and where it was paid.** A classic queue has no `x-delivery-limit`, so poison-message dead-lettering is the drain's job rather than the broker's. That work is `classify_write_failure` plus `_retry_group_one_at_a_time` in `src/prope/call_ledger/drain.py`, built and tested in Task 3 rather than left implicit.

## The Phase 2 loss window this plan deliberately leaves open

Stated here in its own words, as the plan's `<output>` requires.

Phase 2 ships **one** write path and it is **lossy on failure**. On a full handoff buffer and on every failed publisher confirm, `enqueue()` counts and drops: `prope_call_ledger_publish_failed_total{reason=…}` and `prope_call_ledger_metadata_dropped_total` increment, a log line is written with no body in it, and nothing raises. There is no direct-write fallback in this phase and no idempotent upsert on `call_id`. Meanwhile `/readyz` ships its **final** semantics — the database alone (D-16) — so a broker outage is a counted-degraded signal and never un-readiness.

Put together, that means: **for one phase there is a window in which the broker is down, readiness is green, and records genuinely are lost.**

A second face of the same window: at-least-once delivery begins now, while the upsert that makes a redelivery safe does not. `ledger.call_record`'s primary key is `call_id` alone and `write_records` issues a plain `INSERT`, so a redelivered record raises a unique violation, which the drain classifies as permanent and dead-letters. **An ordinary consumer restart therefore dead-letters records that were already written.**

`prope_call_ledger_metadata_dropped_total` carries the lock file's `# must stay 0` note. **It will not stay 0 in Phase 2.** That is the point of incrementing it: the window is measurable rather than merely admitted, which is the difference the lock's own risk section calls "an incident and a lie".

**The two requirements that close it, both in Phase 3:**

- **CL-01** — the direct-write fallback. The exact line it goes on is marked in `enqueue.py`'s `publish_record`, on the branch that has established that this specific record did not reach the broker and knows which of the three reasons applies.
- **CL-02** — the idempotent upsert on `call_id`. This is what makes a redelivery safe, and therefore what makes CL-01's fallback write safe against a confirm that was lost rather than refused.

## Files Created/Modified

**Created**
- `src/prope/broker/topology.py` — the one queue/DLQ declaration both processes call (D-24). Six work-queue arguments and three DLQ arguments, each with a named sub-heading explaining it and the one-way-declaration consequence stated at the constant.
- `src/prope/broker/connection.py` — `build_connection` (connect_robust) and `publisher_channel` (one confirm-mode channel with `on_return_raises=True`).
- `src/prope/call_ledger/envelope.py` — `CallRecordEnvelope` / `CallRecordPayload`, `to_draft()` / `from_draft()`, and the `workspace_id` min-length/max-length/character-class gate.
- `src/prope/call_ledger/enqueue.py` — `HANDOFF_MAXSIZE`, `enqueue()`, `publish_record()`, `_classify_publish_failure()`, `run_publisher()`.
- `src/prope/call_ledger/drain.py` — `WINDOW_SIZE`, `WINDOW_MS`, `classify_write_failure()`, `WriteFailure`, `run_drain()`, `default_retention_window()`.
- `src/prope/observability.py` — the four counters, `LOGGABLE_FIELDS`, `configure_logging()`.
- `tests/broker/_helpers.py` — the management-API reader, the passive-declare depth reader, and the publish/drain drivers.
- `tests/broker/test_enqueue_reaches_a_committed_row.py`, `tests/broker/test_declared_arguments.py`, `tests/broker/test_publish_confirm_failures.py`, `tests/broker/test_drain_failure_classification.py`.
- `tests/architecture/test_no_sql_interpolation.py` — the WR-06 source gate.
- `.planning/phases/02-…/deferred-items.md`.

**Modified**
- `pyproject.toml` / `uv.lock` — `aio-pika==9.6.2`, `testcontainers[postgresql,rabbitmq]==4.15.0`.
- `tests/conftest.py` — `rabbitmq_container`, `amqp_url`, `management_url`, the autouse `purge_queues`, and three new decisions in the rig's docstring.
- `src/prope/db/engine.py` — `broker_url` on the existing `Settings` class. **No second `BaseSettings` subclass exists under `src/prope/`.**
- `src/prope/db/session.py` — the source-gate sentence now names the gate that makes it true.

## Decisions Made

Beyond Task 1's checkpoint and the discretion items the plan directed be resolved (all listed in the frontmatter's `key-decisions`), three resolutions are worth calling out because a reader will otherwise wonder:

1. **The drain consumes via `queue.consume(callback)` into a local accumulator, not via `queue.iterator()`.** RESEARCH warned against the callback form because it runs handlers concurrently under the prefetch count — which is exactly wrong for a windowed batch drain. The objection is answered rather than ignored: the callback does **one** thing, `await inbox.put(message)`, so it *is* the accumulator's inbox and there is one accumulator. The iterator form was tried first and rejected on inspection of aio-pika's source: `QueueIterator.__anext__` **closes the iterator** on `CancelledError` as well as on timeout, so driving a repeating window with `asyncio.wait_for` around it would close the consumer after the first empty window.
2. **The nack is provoked on a purpose-declared queue with `x-max-length: 1`, not on `prope.call_record`.** The production queue's bound is 1,000,000, and a test that published a million messages is a test nobody runs. The overflow mode is identical (`reject-publish-dlx`), so the broker behaviour under test is the same; only the threshold differs. The production max-length is asserted separately, by read-back.
3. **The management HTTP API is read with `urllib.request`, not an HTTP client dependency.** It is the only HTTP call in the suite, and adding `httpx` for it would put a package in `uv.lock` that no production code imports.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] The plan's confirm classification would have labelled every nack `unroutable`**
- **Found during:** Task 3 (`test_publish_confirm_failures.py`)
- **Issue:** The plan specified "`DeliveryError` is `unroutable` … and a returned confirmation that is not `Basic.Ack` is `nacked`". Against the real library that is backwards for the case that matters: aiormq raises `PublishError` (a **subclass** of `DeliveryError`) for a returned mandatory message, and the **parent** `DeliveryError` for a `basic.nack`. Both are `DeliveryError` by `isinstance`, so the plan's mapping would have classified every overflow rejection as a routing problem — and overflow rejection is the exact signal `reject-publish-dlx` was chosen to produce.
- **Fix:** `_classify_publish_failure` tests the subclass first: `PublishError` → `unroutable`, other `DeliveryError` → `nacked`, `TimeoutError` → `timeout`. The reasoning is written at the function.
- **Files modified:** `src/prope/call_ledger/enqueue.py`
- **Verification:** all three reasons provoked against the live broker and asserted on their own label value
- **Committed in:** `01bfc65`

**2. [Rule 1 — Bug] `unroutable` was an unreachable label, because aio-pika does not raise on a return by default**
- **Found during:** Task 3 (the unroutable test failed, reporting `reason=nacked`)
- **Issue:** `aio_pika.Connection.channel()` defaults `on_return_raises=False`. Under that default, a message returned because it was unroutable resolves the publish **successfully**, carrying a `DeliveredMessage`. A publisher that only caught exceptions would count an unroutable publish as delivered; one that checked "is the result an ack" would call it a nack. Neither is true, and `unroutable` could never be reached.
- **Fix:** `publisher_channel` sets `on_return_raises=True`, with the pairing to `mandatory=True` written out. Independently, `publish_record`'s non-Ack fallback branch now inspects the confirmation's shape and classifies a returned `Basic.Return` as `unroutable`, so a channel opened elsewhere without the flag is still counted honestly.
- **Files modified:** `src/prope/broker/connection.py`, `src/prope/call_ledger/enqueue.py`
- **Verification:** `test_unroutable_is_counted_and_enqueue_returns`
- **Committed in:** `01bfc65`

**3. [Rule 2 — Missing critical functionality] `x-queue-type` was not declared, leaving Task 1's decision as an implicit default**
- **Found during:** Task 3 (the read-back assertion failed: the broker reports `x-queue-type: classic` in its `arguments` object whether or not it was declared)
- **Issue:** The plan listed five work-queue arguments and did not include the queue type, because classic is RabbitMQ 4.x's default. But `reject-publish-dlx` **does not exist on a quorum queue**, so a queue whose type is only ever a default is one whose most load-bearing property rests on a default not changing. That failure would be invisible until the day the queue filled — and Task 1's decision would have existed nowhere a test could reach.
- **Fix:** `x-queue-type: "classic"` declared explicitly in both `WORK_QUEUE_ARGUMENTS` and `DLQ_ARGUMENTS`, with the reasoning at the constant, plus a negative control asserting a `quorum` redeclare is refused.
- **Files modified:** `src/prope/broker/topology.py`, `tests/broker/test_declared_arguments.py`
- **Verification:** `test_the_broker_reports_the_arguments_that_were_declared`, `test_one_changed_argument_is_refused[x-queue-type-quorum]`
- **Committed in:** `01bfc65`

---

**Total deviations:** 3 auto-fixed (2 × Rule 1, 1 × Rule 2)
**Impact on plan:** All three are corrections that make the plan's *stated intent* true against the real library and the real broker. Two of them (1 and 2) directly protect D-21's three-reason contract; the third protects the Task 1 checkpoint decision itself. No scope creep — every one was found by an assertion the plan already asked for.

## Issues Encountered

**Docker Hub anonymous pull rate limit (429).** The `rabbitmq:4.3-management` image was not present locally and every pull — including `hello-world`, which is how it was diagnosed as a global rate limit rather than a bad tag — returned `429 Too Many Requests`. Task 2 was committed with its live-broker verification explicitly recorded as UNRUN, and the remaining 7 tests in the module plus the full 88-test Phase 1 suite were run to establish there was no regression. The limit cleared shortly afterwards, the image pulled, and the tracer's `<verify>` was run and passed before any expansion work began. **No task shipped on an unverified tracer.**

**A `git stash` was run by mistake** while checking working-tree state, which reverted every uncommitted file in this plan. It was detected immediately, `git stash list` confirmed the single entry was the one just created, and `git stash pop` restored everything before any further work. No content was lost. Recorded because the destructive-git prohibition names `git stash` explicitly and a silent recovery would make the incident unlearnable.

## Notes for the next plans in this phase

- **`retention_for` takes exactly ONE positional argument, the `workspace_id`.** Plan 02-02's `read_retention_window(sessionmaker, workspace_id)` is a two-argument function and is **not** directly assignable — plan 02-03 must bind the sessionmaker with `functools.partial` first. Passing the bare function type-checks under a loose annotation and then raises `TypeError` on the first workspace group at runtime, inside a consumer. This is recorded at the parameter, in the docstring, and asserted by `test_the_retention_resolver_is_called_with_exactly_the_workspace_id`.
- **Prefetch bounds unacknowledged work at one window only while there is exactly ONE drain consumer** — RabbitMQ applies `prefetch_count` per consumer, not per channel, and `0` means infinite. Plan 02-03's supervisor is where "exactly one" must be asserted. This also carries Phase 1's WARN-2 (the read-then-write race on `workspace_spend.currency`), which stays latent only while there is one consumer.
- **`configure_logging()` exists and nothing calls it in production yet.** The entrypoints arrive in 02-03 and 02-04.
- **There is no `/metrics` endpoint**, so the four counters are observable from tests and nothing else. Phase 3's T-005 sweep owns the endpoint, the `dlq_depth` gauge, the 17-metric set and every alert rule.
- **CL-06's second clause only.** This plan addresses "gateway traffic continues to be recorded normally". `check_spend_ceiling` and the refusal-with-no-figure are plan 02-04's.

## Known Stubs

None. Every symbol this plan created is wired to a caller inside this plan or to a test that drives it. The two deliberate not-yets — no direct-write fallback and no upsert — are requirements assigned to Phase 3 (CL-01, CL-02), documented at their call sites and in this SUMMARY, not stubs.

## User Setup Required

None for the test suite. For a future deployment, `PROPE_BROKER_URL` joins `PROPE_DATABASE_URL` in the single `.env` on the host (ADR-0032); `Settings.broker_url` is a required field, so a missing key is a startup error rather than a silent default.

## Next Phase Readiness

Ready. `declare_topology`, `enqueue`, `run_publisher` and `run_drain` are the four entry points 02-03's supervisor and 02-04's `app` compose. The one thing 02-03 must not get wrong is the `functools.partial` binding of the retention resolver, and it is documented at the parameter and covered by a test.

## Self-Check: PASSED

- All 12 created source/test files exist on disk.
- Both task commits (`c15b647`, `01bfc65`) exist in git history.
- `HANDOFF_MAXSIZE` defined in `enqueue.py`; `WINDOW_SIZE = 500` and `WINDOW_MS = 250` defined in `drain.py`, with `set_qos(prefetch_count=WINDOW_SIZE)`.
- `broker_url` present on `Settings`; exactly one `BaseSettings` subclass exists under `src/prope/`.
- `uv run pytest -q` → **141 passed**. `uv run ruff check src/ tests/ alembic/` → clean.
- Known unsatisfiable verification line: `uv run ruff format --check` fails repo-wide on pre-existing Phase 1 files (no `[tool.ruff]` `line-length` is configured). Logged in `deferred-items.md`, not fixed, because reformatting 19 files this plan does not own is out of scope.

---
*Phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling*
*Completed: 2026-08-10*
