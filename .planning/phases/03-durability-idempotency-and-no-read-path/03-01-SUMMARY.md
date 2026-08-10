---
phase: 03-durability-idempotency-and-no-read-path
plan: 01
subsystem: backend
tags: [rabbitmq, postgres, prometheus, structlog, asyncio, durability, tenancy, security]

# Dependency graph
requires:
  - phase: 01-data-model-pricing-and-retention
    provides: "write_records (the one write path), workspace_transaction, CallRecordDraft/CallBodyDraft, ledger.call_record and ledger.call_body, and the session-scoped PostgreSQL 17 rig"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 01
    provides: "prope.observability — the counter module, LOGGABLE_FIELDS, configure_logging"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 03
    provides: "prope.supervisor — Job, supervise(), run_with_restart's backoff, and the Windows stop-event shape D-32 reuses"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 05
    provides: "prope.app — the composition root, _start_publisher/_stop_publisher, the lifespan, and /readyz's D-16 paragraph this plan rewrites"
provides:
  - "prope.call_ledger.fallback.build_fallback_writer — ADR-0041's inline direct write, bound at the composition root"
  - "prope.call_ledger.enqueue.HandoffItem and FallbackWriter — the pair that travels to the publisher, the envelope and the fallback"
  - "prope.call_ledger.enqueue.drain_handoff_on_stop — CR-02's shared shutdown drain, called by both job bodies"
  - "prope.call_ledger.enqueue.publish_or_fall_back — one record's whole handling, with the catch that lets nothing out"
  - "MAX_BODY_BYTES = 256 KiB — the only byte bound anywhere on the path"
  - "HANDOFF_DRAIN_DEADLINE_SECONDS = 3.0, from which app.PUBLISHER_STOP_TIMEOUT_SECONDS is DERIVED"
  - "All eighteen declared metrics, defined at import, plus ENQUEUE_DURATION_BUCKETS and WRITE_LAG_BUCKETS"
  - "JOB_CALL_RECORD_PUBLISHER / JOB_CALL_RECORD_FALLBACK — app's two job names, a closed set fixed in source"
  - "tests/broker/_helpers.py — handoff_item, fallback_writer, pooled_sessionmaker, counter_value"
  - "docs/brainstorm/open_questions/OQ-022.md, OQ-024.md, OQ-025.md — three declared deviations, raised not absorbed"
affects: [03-02-idempotent-upsert, 03-03-ceiling-and-cr-01, 03-04-metrics-route-and-alerts, 03-06-load-and-chaos, 19-21-gateway]

actuals:
  tokens: 118000
  tasks: 4
  commits: 1

tech-stack:
  added: []
  patterns:
    - "An injected callable bound once at the composition root, with its type alias declared by the module that REQUIRES it rather than by the module that implements it"
    - "A composition root that chooses between two job bodies instead of threading a nullable dependency through the healthy path"
    - "A shutdown that closes the door (asyncio.Queue.shutdown) before it empties the room, so records arriving during the stop are counted where they are refused"
    - "A constant DERIVED from another module's constant rather than two literals whose relationship lives in a comment"
    - "A cap computed from bytes the enforcing module encoded itself, overwriting the caller-supplied figure"
    - "Histogram buckets argued from the numbers the project will assert on, because histogram_quantile can only answer to a bucket's width"

key-files:
  created:
    - src/prope/call_ledger/fallback.py
    - tests/broker/test_broker_unreachable_fallback.py
    - tests/broker/test_handoff_shutdown_drain.py
    - docs/brainstorm/open_questions/OQ-022.md
    - docs/brainstorm/open_questions/OQ-024.md
    - docs/brainstorm/open_questions/OQ-025.md
  modified:
    - src/prope/observability.py
    - src/prope/call_ledger/enqueue.py
    - src/prope/app.py
    - tests/broker/_helpers.py
    - tests/broker/test_publish_confirm_failures.py
    - tests/broker/test_enqueue_reaches_a_committed_row.py
    - tests/architecture/test_route_table.py
    - tests/integration/test_health_and_readiness.py

key-decisions:
  - "Task 1 adopted UNCONFIRMED: a broker that was never reachable starts a fallback-only job, not a publisher with a nullable exchange. The consequence a human must rule on is that such a process never publishes until it is restarted"
  - "publish_or_fall_back is a second named helper in enqueue.py beyond the plan's artifact list, because with two job bodies the per-record catch has two callers and the alternative was copying metadata_dropped_total.inc() into app.py"
  - "A body that cannot be UTF-8 encoded takes the cap's own branch and the cap's own reason (oversize) rather than a third value: a body whose size cannot be computed cannot be admitted under a byte cap"
  - "SC1's producer is PACED against handoff().qsize(). enqueue() is synchronous, so a bare loop over 1,000 records never yields and record 513 takes the full-handoff branch — which would make the test about HANDOFF_MAXSIZE rather than about the fallback"
  - "The 1,000-record and shutdown-drain tests build a POOLED sessionmaker inside the test. Measured: 188 s unpooled vs 17 s pooled for 1,000 fallback writes, and 20 unpooled writes take ~3.6 s against a 3.0 s drain deadline — which would make a durability assertion a timing race"
  - "tests/integration/test_health_and_readiness.py was edited outside files_modified (declared drift). The assertion got STRONGER: publisher is None became publisher is not None, because asserting None would now be asserting the bug"

patterns-established:
  - "A shared drain helper asserted as shared by an AST walk — 'shutdown() is called in exactly one FUNCTION and both job bodies call that function' rather than a substring count that would count the docstrings explaining it"
  - "A truncation test that patches the deadline to zero so the remainder is exact, with the full-deadline test beside it as the positive control that the same setup drains everything"
  - "A cross-module constant relationship asserted by a three-line inequality test, so a simplification back to two literals fails loudly"

requirements-completed: [CL-01]

coverage:
  - id: D1
    description: "With the broker unreachable, a record handed to enqueue() still reaches ledger.call_record carrying its version_id, written directly to PostgreSQL from the app process — over both provocations"
    requirement: CL-01
    verification:
      - kind: integration
        ref: "tests/broker/test_broker_unreachable_fallback.py::test_a_thousand_records_survive_a_channel_that_closed_under_the_publisher"
        status: pass
      - kind: integration
        ref: "tests/broker/test_broker_unreachable_fallback.py::test_a_broker_that_was_never_reachable_still_produces_durable_records"
        status: pass
    human_judgment: false
  - id: D2
    description: "A record that falls back is written without its body, every dropped body increments body_dropped_total{reason=fallback} exactly once, and the counter therefore equals the rows missing from ledger.call_body"
    requirement: CL-01
    verification:
      - kind: integration
        ref: "tests/broker/test_broker_unreachable_fallback.py::test_a_thousand_records_survive_a_channel_that_closed_under_the_publisher"
        status: pass
    human_judgment: false
  - id: D3
    description: "metadata_dropped_total stays at zero for the whole of a broker outage in which PostgreSQL is reachable, on all three publish-failure reasons and on the closed channel"
    requirement: CL-01
    verification:
      - kind: integration
        ref: "tests/broker/test_broker_unreachable_fallback.py::test_a_thousand_records_survive_a_channel_that_closed_under_the_publisher"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_unroutable_is_counted_and_the_record_falls_back"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_nacked_is_counted_and_the_record_falls_back"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_timeout_is_counted_and_the_record_falls_back"
        status: pass
    human_judgment: false
  - id: D4
    description: "A fallback that itself raises loses exactly one record, increments metadata_dropped_total by exactly one, logs one line carrying the exception's class and no message, and does not kill the publisher"
    requirement: CL-01
    verification:
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_a_fallback_that_itself_raises_loses_exactly_one_record"
        status: pass
    human_judgment: false
  - id: D5
    description: "A broker that was never reachable at startup still produces durable records — the composition root starts a supervised job either way"
    requirement: CL-01
    verification:
      - kind: integration
        ref: "tests/broker/test_broker_unreachable_fallback.py::test_a_broker_that_was_never_reachable_still_produces_durable_records"
        status: pass
      - kind: integration
        ref: "tests/integration/test_health_and_readiness.py::test_readyz_answers_200_with_the_broker_unreachable"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_route_table.py::test_both_publisher_branches_are_supervised_jobs_and_neither_is_a_bare_task"
        status: pass
    human_judgment: false
  - id: D6
    description: "A request/response pair whose UTF-8 encoding exceeds 256 KiB is recorded as metadata with no body, counted on body_dropped_total{reason=oversize}, and the record itself is still accepted; a pair exactly at the cap keeps its body and stores the size this module computed"
    verification:
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_a_body_one_byte_over_the_cap_is_dropped_and_counted"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_a_body_exactly_at_the_cap_keeps_its_body"
        status: pass
      - kind: integration
        ref: "tests/broker/test_enqueue_reaches_a_committed_row.py::test_an_oversize_record_lands_with_no_body_row_at_all"
        status: pass
      - kind: integration
        ref: "tests/broker/test_enqueue_reaches_a_committed_row.py::test_the_stored_byte_size_is_the_one_this_module_computed"
        status: pass
    human_judgment: false
  - id: D7
    description: "enqueue() never raises under any branch, including an unencodable body and a handoff that has been shut down"
    verification:
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_a_body_that_cannot_be_encoded_is_counted_and_enqueue_returns"
        status: pass
      - kind: integration
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_enqueue_after_the_door_is_shut_returns_normally_and_counts"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_enqueue_returns_normally_through_every_failure_branch"
        status: pass
    human_judgment: false
  - id: D8
    description: "CR-02: a graceful stop publishes or falls back what is in the handoff before returning, on BOTH job bodies; any record still buffered when the deadline expires is counted on metadata_dropped_total and named in exactly one log line"
    verification:
      - kind: integration
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_a_graceful_stop_publishes_or_falls_back_what_is_buffered"
        status: pass
      - kind: integration
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_a_truncated_drain_counts_exactly_the_remainder_and_names_it_once"
        status: pass
      - kind: integration
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_the_fallback_only_branch_also_drains_on_stop"
        status: pass
      - kind: architecture
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_the_door_is_shut_in_one_place_and_both_job_bodies_reach_it"
        status: pass
    human_judgment: false
  - id: D9
    description: "The handoff belongs to a serving lifetime: two consecutive lifespans in one process both enqueue successfully, so the first lifespan's queue.shutdown() does not poison the second"
    verification:
      - kind: integration
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_two_consecutive_lifespans_in_one_process_both_enqueue"
        status: pass
    human_judgment: false
  - id: D10
    description: "An exception escaping the publisher restarts the publisher rather than ending it silently, and the crash line carries app's own job name"
    verification:
      - kind: integration
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_an_exception_out_of_the_publisher_job_restarts_it_and_is_logged"
        status: pass
    human_judgment: false
  - id: D11
    description: "All eighteen declared metrics are present in the default registry at import, before anything increments them, and the two histograms carry the bucket edges the project asserts on"
    verification:
      - kind: manual
        ref: "REGISTRY.get_sample_value returns 0.0 (not None) for prope_call_ledger_missing_version_id_total at import; 19 prope_-prefixed collectors present (18 declared + Phase 2's ceiling_failed_open_total, retired by 03-03)"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_workspace_id_is_never_a_metric_label"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_the_two_extended_label_sets_stayed_closed_at_their_declared_size"
        status: pass
    human_judgment: false
  - id: D12
    description: "No request body, response body or credential-shaped value reaches a log line or a metric label from the fallback, the oversize path or the shutdown path"
    verification:
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_no_marker_reaches_a_log_record_or_a_metric_label[body_marker]"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_no_marker_reaches_a_log_record_or_a_metric_label[credential_shaped_marker]"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_the_oversize_log_line_carries_no_fragment_of_the_body"
        status: pass
    human_judgment: false
  - id: D13
    description: "PUBLISHER_STOP_TIMEOUT_SECONDS is derived from HANDOFF_DRAIN_DEADLINE_SECONDS rather than chosen, so a cancel can never land while the drain is still working"
    verification:
      - kind: unit
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_the_stop_timeout_is_derived_from_the_drain_deadline"
        status: pass
    human_judgment: false
  - id: D14
    description: "Task 1's adopted shape means a process that starts against a dead broker never publishes until it is restarted — records are durable throughout, but the work queue stays empty"
    verification: []
    human_judgment: true
    rationale: "Adopted UNCONFIRMED under mode: yolo. Whether the composition should instead retry the broker connection on an interval is a product question this phase does not own. Both halves of the mechanical claim ARE asserted: the job runs, and the records land."
  - id: D15
    description: "MAX_BODY_BYTES = 256 KiB is a product-visible policy — a request/response pair above it is recorded with no body, permanently"
    verification: []
    human_judgment: true
    rationale: "The number is argued at the constant in the five-part house form and the boundary is asserted from both sides, but 'is 256 KiB the right policy' is a product judgement, not a property a test can settle."
  - id: D16
    description: "Removing metadata_dropped_total's increment from the three publish-failure sites changes what LedgerMetadataDropped means"
    verification: []
    human_judgment: true
    rationale: "Confirm that a failed confirm absorbed by the fallback should page nobody, and that LedgerPublishFailing (ticket, not page) is the intended signal. The mechanical half — the counter does not move on any of the three reasons — IS asserted."

# Metrics
duration: 95min
completed: 2026-08-11
status: complete
---

# Phase 03 Plan 01: Durability, idempotency, and no-read-path Summary

**CL-01 is closed. A broker outage now costs bodies and nothing else.** One thousand records handed to
`enqueue()` with the publisher's channel closed under it produce one thousand rows in
`ledger.call_record`, every one carrying its `version_id`, read back through `migrate_engine` — with
zero `ledger.call_body` rows, `prope_call_ledger_fallback_direct_write_total` and
`prope_call_ledger_body_dropped_total{reason="fallback"}` each moved by exactly 1,000, and
`prope_call_ledger_metadata_dropped_total` moved by **zero**. The same holds when the broker was never
reachable at all, which is the provocation that would fail if the composition root returned with no
task. CR-02 is closed by draining and then counting, not by counting alone.

## Performance

- **Duration:** ~95 min
- **Tasks:** 4 (one decision checkpoint adopted UNCONFIRMED, one tracer, two auto)
- **Files created/modified:** 14 (6 created, 8 modified — one of them undeclared; see Deviations)
- **Test suite:** **312 passed**, 0 failed (292 at the 02-05 baseline; +20)

## What `prope_call_ledger_metadata_dropped_total` now means

The plan's `<output>` requires this in the summary's own words, so it is stated in full.

**It counts records that exist nowhere.** Neither the broker nor the database took them. That is
ADR-0041's sentence and it is now true of the code: the three publish-failure sites in
`publish_record` no longer increment it, because a record that fails to publish is no longer lost — it
falls back.

**Three kinds of event survive, and a dead-letter is not one of them:**

| # | Event | Where |
|---|---|---|
| 1 | **The handoff refused the record** — full, already shut down, or the failure nobody predicted | `enqueue()`, three branches |
| 2 | **The direct write did not land** — the database refused it, or something nobody predicted escaped the publisher's handling of that record | `fallback.build_fallback_writer`'s `except`, and `enqueue.publish_or_fall_back`'s outer catch |
| 3 | **The stop deadline expired with records still buffered** — counted once per record, named in one log line | `enqueue.drain_handoff_on_stop` |

`LedgerMetadataDropped` pages immediately on `> 0`. **A dead-letter must not be a fourth kind**, and
plan 03-02 removes the two increments in `drain.py` that make it one today: a dead-lettered record is
in `prope.call_record.dlq` with a 30-day TTL, and the signal for it is `dlq_depth > 0` — a ticket. A
page that fired on one malformed envelope is a page people learn to close.

## The loss window that survives this plan

Two of them, both named at the code as well as here.

**A-139's hard kill.** The handoff is 512 records and a `SIGKILL` loses whatever is in it. A
*graceful* stop no longer does: `drain_handoff_on_stop` shuts the queue (so records arriving during
the stop are refused at the producer and counted there rather than vanishing uncounted), empties it
under a 3.0 s deadline, and counts whatever the deadline could not reach.

**A redelivery still dead-letters, and this is the case a timed-out confirm creates on purpose.** A
confirm that timed out means the broker may well have received the message; the fallback writes the
record anyway, and when the broker later delivers it, `write_records`' plain `INSERT` meets
`call_record`'s primary key and raises an `IntegrityError` that `classify_write_failure` sends to the
DLQ. **That is CL-02 and plan 03-02**, and it is why a timed-out confirm is survivable today rather
than safe. It is written at
`test_publish_confirm_failures.py::test_timeout_is_counted_and_the_record_falls_back` so the next
reader meets it where it happens.

## Task 1 — the decision adopted UNCONFIRMED

**Adopted: `fallback-only-job`.** When `_start_publisher` cannot reach the broker, the composition
root starts a job that reads the handoff and writes every record straight to PostgreSQL, instead of
returning with no task (which is what Phase 2 did) and instead of starting the publisher with
`exchange=None`.

The argument is about where a degraded case belongs. A nullable exchange puts the outage **inside** the
function that handles the healthy path, and `publish_record` is the seam Phase 19's gateway is built
against; it also makes an `AttributeError` caught by a bare `except` the mechanism, which is a real
behaviour resting on an accident. `app.py` already branches on broker availability, so this is a second
consequence of a decision that file already makes.

**What a human is actually being asked to rule on is the consequence, not the shape:** with this
adopted, a process that starts against a dead broker **never publishes until it is restarted**, because
`connect_robust`'s recovery is attached to a connection that was never established. Records are durable
throughout — that is the point — but the work queue stays empty and the drain has nothing to do.
Whether that is acceptable, or whether the composition should retry the connection on an interval, is a
product question this phase does not own. It is written at `fallback_only_job` in `app.py`, in
`deferred-items.md` Part 1 item 1, and it is owed a numbered row on `03-UAT.md` and on
`.planning/ORCHESTRATION-DECISIONS.md` (whose phase-3 table still reads *"none yet"* — that ledger is
not in this plan's `files_modified` and is the orchestrator's to update).

## What shipped

**`src/prope/call_ledger/fallback.py` (new)** — `build_fallback_writer(sessionmaker) -> FallbackWriter`.
One record, one `workspace_transaction`, one `write_records`, and **no SQL of its own** (asserted:
the file contains no `text(` call and no `INSERT`). The draft is rebuilt with `body=None` **before**
the write, which is what makes D-11's *"the fallback inherits no settings query"* structural rather
than disciplinary: `expires_at` is stamped only on a `call_body` row, so a path that writes no body
never consults `ledger.workspace_retention`. On success it increments `fallback_direct_write_total`,
observes `write_lag_seconds` with `max(0.0, now - occurred_at)` — clamped because a negative
observation decrements `_sum` while incrementing `_count`, which makes `rate(_sum[5m])` negative — and
counts one body drop per **record**. On any `Exception` (never `BaseException`) it counts one
`metadata_dropped_total` and logs the exception's **class**, never its message.

**`src/prope/call_ledger/enqueue.py`** — `HandoffItem` (frozen, `(draft, occurred_at)`) and
`FallbackWriter` are both declared here and imported by `fallback.py`, so the dependency runs one way
and no module-scope cycle exists. `occurred_at` moved from `publish_record` into `enqueue()`, which
makes it call-ledger's **third sanctioned clock site** — stated in the docstring against the four
places that say they read no clock — and changes the *meaning* of a registered INT-018 field from
"when the publisher published it" to "when the caller handed it over", also written down. The three
`return False` sites all `await fallback(item)` and none of them increments `metadata_dropped_total`
any more; `publish_failed_total`'s label set stays closed at three and the bare-`except` branch still
does not touch it. `MAX_BODY_BYTES = 256 * 1024` is enforced before the `put_nowait`, computed from
bytes this module encodes, overwriting the caller's `byte_size`. `drain_handoff_on_stop` and
`publish_or_fall_back` are the two shared helpers both job bodies call.

**`src/prope/observability.py`** — all eighteen metrics defined at import (the lock's seventeen plus
T-005's `dlq_depth`), each with a `#:` block naming its label set and why the set is closed;
`ENQUEUE_DURATION_BUCKETS` and `WRITE_LAG_BUCKETS` with the arithmetic written out;
`BODY_DROP_REASON_FALLBACK` / `BODY_DROP_REASON_OVERSIZE`; and the `metadata_dropped_total` docstring
rewritten to the paragraph above. `ceiling_failed_open_total` is untouched with one added `#:` line
saying 03-03 retires it and why it is not retired here.

**`src/prope/app.py`** — the fallback bound from `app.state.sessionmaker`, two job-name constants, both
branches of `_start_publisher` composing through `supervise(...)`, `PUBLISHER_STOP_TIMEOUT_SECONDS`
**derived** from `HANDOFF_DRAIN_DEADLINE_SECONDS`, `reset_handoff()` in the lifespan's `finally`, and
`readyz`'s Phase 2 paragraph rewritten from *"records genuinely are lost"* to what is now true.

**Three OQ files**, all `status: open`, `blocks_build: false`.
`git status --porcelain docs/modules docs/architecture docs/adr` produces no output.

## Discretion items the plan directed be resolved

**Histogram bucket edges.** Adopted as the plan specified, with the rule written once and referenced:
`histogram_quantile` interpolates *inside* the bucket holding the quantile, so every number this
project asserts on must be an **edge**. `0.001` is in the enqueue set because CL-12 asserts p95 < 1 ms;
`2.0`, `10.0` and `30.0` are in the lag set because `performance_requirements` states p95 < 2 s and
p99 < 10 s and `LedgerWriteLagHigh` fires at p95 > 30 s. `prometheus_client`'s defaults would have put
every enqueue observation in the first bucket and every lag from 10 s to an hour in `+Inf`.

**`enqueued_total{outcome}` stays two-valued.** Written at the counter. `outcome` means *the fate of
the record*; `oversize` would mean *the fate of the body*, and two subjects in one label makes
`sum(enqueued_total)` stop being "records offered". The oversize event is fully visible on
`body_dropped_total`, whose subject *is* the body.

**The shutdown-drain deadline.** `HANDOFF_DRAIN_DEADLINE_SECONDS = 3.0` in `enqueue.py`, and
`app.PUBLISHER_STOP_TIMEOUT_SECONDS = HANDOFF_DRAIN_DEADLINE_SECONDS + 2.0`. Derivation rather than
two literals, because if the inner deadline ever reached the outer wait the cancel would land while
the drain was still working and the remainder count would never run — CR-02 reproduced with more
machinery. A three-line test asserts the inequality.

## Deviations from Plan

### Declared drift — a file outside `files_modified`

**1. `tests/integration/test_health_and_readiness.py`**

- **Found during:** Task 4 (whole-suite run).
- **Issue:** `test_readyz_answers_200_with_the_broker_unreachable` asserted
  `application.state.publisher is None` on the broker-unavailable path, and its docstring carried the
  Phase 2 paragraph *"ADR-0041's inline fallback does not exist yet, so in exactly this state
  `enqueue()` fills its bounded handoff and then counts and drops — readiness green, records lost."*
  Task 1's adopted shape makes the assertion false **on purpose** and CL-01 makes the paragraph false.
  The plan anticipated the behaviour change (it is the whole of Task 1) but did not list this file.
- **Fix:** the assertion was **strengthened, never weakened** — `is None` became `is not None` with the
  reason at the assertion, because asserting `None` here would now be asserting the bug. The stale
  paragraph was rewritten to say that the gap is closed and that the assertion got stronger rather
  than being deleted. The readiness rule itself (D-16) is untouched.
- **Verification:** `tests/integration/test_health_and_readiness.py` — 12 passed.

### Auto-fixed issues

**2. [Rule 2 — missing critical functionality] The plan's per-record catch had two callers, not one**

- **Found during:** Task 2 / Task 4.
- **Issue:** the plan says to catch once in `run_publisher` around `publish_record`. With Task 1's
  adopted shape there are **two** job bodies, and `app.py`'s fallback-only job needs the same catch.
  The literal reading would have put a bare `metadata_dropped_total.inc()` inside the composition root.
- **Fix:** `enqueue.publish_or_fall_back(item, publish, fallback)` — one named helper, `publish=None`
  on the fallback-only branch, called by `run_publisher`, by `drain_handoff_on_stop` and by
  `app.py`'s job body. **This is one public name beyond the plan's artifact list** and is recorded in
  `deferred-items.md` Part 5 so a later plan reading that list finds it.

**3. [Rule 2] An unencodable body had no defined reason value**

- **Found during:** Task 3.
- **Issue:** the plan requires the sizing not to raise and to "count", and `body_dropped_total`'s
  reason set is closed at two by this plan's own decision. A lone surrogate (`"\ud800"`) makes
  `str.encode()` raise, and neither `fallback` nor a third value was specified.
- **Fix:** counted as `oversize`, with the reason written at the branch — *a body whose size cannot be
  computed cannot be admitted under a byte cap, so it takes the cap's own branch and the cap's own
  reason rather than inventing a third value one line away from the second.* Asserted by
  `test_a_body_that_cannot_be_encoded_is_counted_and_enqueue_returns`.

**4. [Rule 3 — blocking] SC1's 1,000 records overflowed the handoff before the publisher could run**

- **Found during:** Task 2.
- **Issue:** `enqueue()` is synchronous (D-25), so a bare `for` loop over 1,000 calls never yields and
  the publisher never runs — record 513 takes the full-handoff branch and increments
  `metadata_dropped_total`, which is the counter the test exists to prove stays at zero. The test would
  have been about `HANDOFF_MAXSIZE` rather than about the fallback.
- **Fix:** the producer is paced against `handoff().qsize()`, with the reason at the helper: a gateway
  at the stated 50 rps hands records over one request at a time with the loop turning in between, so
  the pacing **is** the arrival rate rather than a workaround.

**5. [Rule 3 — blocking] The drain deadline is 3.0 s and 20 unpooled fallback writes take ~3.6 s**

- **Found during:** Task 4.
- **Issue:** measured twice with `pytest --durations`: 1,000 fallback writes take **188 s** over the
  `NullPool` fixture engines and **17 s** over a pooled engine. At ~180 ms per record, a
  20-record shutdown drain races its own 3.0 s deadline and would count a remainder on a slow day.
- **Fix:** `tests/broker/_helpers.py::pooled_sessionmaker`, a context manager that builds and disposes
  a pooled engine **inside one test, on one loop** — which is what `prope.app` actually builds, so it
  is more production-faithful, and which does not weaken `conftest.py`'s `NullPool` rule (nothing
  crosses loops). Used by the SC1 test, the closed-port test, and the two shutdown-drain tests that
  write rows.

**6. [Rule 3] `asyncio.create_task(supervise(...))` has not started when `_start_publisher` returns**

- **Found during:** Task 4.
- **Issue:** a test that starts the fallback-only job and immediately sets `stopping` gets **no job at
  all**: `run_with_restart`'s own `while not stopping.is_set()` sees the event already set. The test
  read as "the drain did not run" when in fact nothing had started.
- **Fix:** one `await asyncio.sleep(0.2)` after `_start_publisher` in that test, commented at the call.
  Recorded in `deferred-items.md` Part 5 because it is a trap for every later test of a stop path.

---

**Total deviations:** 1 declared drift + 5 auto-fixed (2 × Rule 2, 3 × Rule 3). **No architectural
change:** no new table, no migration, no new library, no new database routine, no new role, no
forbidden edge, and **no fifth `SECURITY DEFINER` function**.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest -q` (whole suite) | **312 passed, 1 warning in 230.16s** (292 at the 02-05 baseline) |
| `uv run pytest tests/broker/ -q` | **57 passed, 1 warning in 97.25s** |
| `uv run pytest tests/broker/test_broker_unreachable_fallback.py -x -q` | 2 passed (Task 2's `<verify>`) |
| `uv run pytest tests/broker/test_publish_confirm_failures.py -q` | passes within the broker run (Task 3's `<verify>`) |
| `uv run pytest tests/broker/test_handoff_shutdown_drain.py tests/architecture/test_route_table.py -q` | 8 + 22 passed (Task 4's `<verify>`) |
| `uv run ruff check src/ tests/ alembic/` | **All checks passed!** |
| `git status --porcelain docs/modules docs/architecture docs/adr` | no output |
| `REGISTRY.get_sample_value("prope_call_ledger_missing_version_id_total")` at import | `0.0`, not `None` |
| `prope_`-prefixed collectors in the registry at import | 19 = the eighteen declared + `ceiling_failed_open_total` (03-03 retires it) |
| `0.001 in ENQUEUE_DURATION_BUCKETS`; `{2.0, 10.0, 30.0} ⊂ WRITE_LAG_BUCKETS` | both `True` |
| AST walk: `prope.db` imports in `enqueue.py` | `[]` |
| `inspect.signature`: `fallback` on `publish_record` / `run_publisher` | `KEYWORD_ONLY`, no default, both |
| `grep -c "text(\|INSERT" src/prope/call_ledger/fallback.py` | `0` |
| `uv run ruff format --check` | **not run — not a gate.** Broken Window #1, unsatisfiable repo-wide |

**Literal tail of the final full-suite run:**

```
312 passed, 1 warning in 230.16s (0:03:50)
```

**Literal output of the lint gate:**

```
All checks passed!
```

## Human Verification Required

Three items, all of them postures rather than tests. They are the plan's three `<human-check>`s.

> **1.** Task 1's adopted shape (`fallback-only-job`) means a process that starts against a dead
> broker never publishes until it is restarted — records are durable throughout, but the queue stays
> empty and the drain has nothing to do. Confirm that is acceptable, or that the composition should
> retry the broker connection on an interval.

> **2.** `MAX_BODY_BYTES = 256 KiB` is a product-visible policy: a request/response pair above it is
> recorded with no body, permanently. Confirm the number, or name the one that replaces it.

> **3.** Removing `metadata_dropped_total`'s increment from the three publish-failure sites changes
> what an existing page means. Confirm that a failed confirm absorbed by the fallback should page
> nobody, and that `LedgerPublishFailing` (ticket, not page) is the intended signal.

Item 1 additionally owes a row on `.planning/ORCHESTRATION-DECISIONS.md`, whose phase-3 table still
reads *"none yet — phase 3 planning in flight"*. That file is not in this plan's `files_modified`.

## Flagged Assumptions Carried to Verification

The plan's own flagged-assumptions block says no deterministic edge probe exists in this environment
and that the boundary conditions were an **agent enumeration, labelled as one**. All seven are now
asserted, which is evidence about the enumeration rather than about the probe:

| Enumerated boundary | Asserted by |
|---|---|
| a broker that dies mid-run | `test_a_thousand_records_survive_a_channel_that_closed_under_the_publisher` |
| a broker that was never reachable | `test_a_broker_that_was_never_reachable_still_produces_durable_records` |
| a fallback whose database is also gone | `test_a_fallback_that_itself_raises_loses_exactly_one_record` |
| a body exactly at the cap, and one byte over | `test_a_body_exactly_at_the_cap_keeps_its_body`, `test_a_body_one_byte_over_the_cap_is_dropped_and_counted` |
| a record with no body at all | `_sized_or_dropped`'s early return, exercised by every eval-shaped draft in the suite |
| a graceful stop with a full buffer | `test_a_graceful_stop_publishes_or_falls_back_what_is_buffered` |
| a graceful stop whose deadline expires | `test_a_truncated_drain_counts_exactly_the_remainder_and_names_it_once` |

An eighth was found while writing them and is asserted too: **a body that cannot be UTF-8 encoded**.

## Known Stubs

None. Every symbol this plan created is driven by a test in this plan.

**Twelve of the eighteen metrics have no increment site yet, and that is the plan's premise rather
than a stub.** D-40 requires them defined now: a metric that first appears when it goes non-zero has
no baseline, and `REGISTRY.get_sample_value` answers `None` rather than `0.0` for a metric nothing has
touched — which is why `missing_version_id_total`, whose whole job is to be zero, is the sharpest
case. The increments land in 03-02 (`write_records`), 03-03 (`seams.py`) and 03-04 (`worker.py`); the
`/metrics` route is 03-04's.

## Notes for the next plans

- **`write_records` still issues a plain `INSERT`, so a redelivery dead-letters.** That is 03-02's
  whole job, and the timed-out-confirm case above is the scenario that makes it matter.
- **`ceiling_failed_open_total` survives this plan, with a `#:` line saying 03-03 retires it.**
  `seams.py` imports the name; removing it here would have left a red import for a wave.
- **`publish_record`'s second positional is a `HandoffItem`, not a `CallRecordDraft`.** Any later test
  that publishes one record should use `tests/broker/_helpers.py::handoff_item`.
- **Both `app` job names are `LOGGABLE_FIELDS`' `job` values.** The closed set across the two processes
  is now four (`call_record_publisher`, `call_record_fallback`, `call_record_drain`,
  `expired_body_deletion`). No new `LOGGABLE_FIELDS` entry was added by this plan — the shutdown line
  uses `reason` and `group_size`, both already members.
- **Plan 03-06 should read `deferred-items.md` Part 5 before it writes a throughput assertion.** The
  fixture engines' `NullPool` costs ~180 ms per single-record transaction on this host, which is what a
  ≥500 records/sec claim would actually measure if it ran over `app_sessionmaker`.
- **`enqueue()` cannot be handed more than ~512 records without yielding.** Pace the producer, or the
  test is about `HANDOFF_MAXSIZE`.

## Self-Check: PASSED

- All six created files exist on disk; all eight modified files carry this plan's changes.
- `src/prope/call_ledger/fallback.py` defines `build_fallback_writer` and contains no `text(` call and
  no `INSERT`.
- `src/prope/call_ledger/enqueue.py` defines `HandoffItem`, `FallbackWriter`, `MAX_BODY_BYTES`,
  `HANDOFF_DRAIN_DEADLINE_SECONDS`, `drain_handoff_on_stop` and `publish_or_fall_back`, and imports
  nothing from `prope.db` (AST-verified).
- `src/prope/observability.py` defines all eighteen metric objects plus both bucket tuples and both
  body-drop reason constants.
- `src/prope/app.py` calls `supervise(` on both branches of `_start_publisher`; the string
  `asyncio.create_task(run_publisher(` appears nowhere; `reset_handoff()` is called in the lifespan's
  `finally`.
- `docs/brainstorm/open_questions/OQ-022.md`, `OQ-024.md` and `OQ-025.md` exist, all `status: open`.
- `uv run pytest -q` → **312 passed**. `uv run ruff check src/ tests/ alembic/` → clean.
- No commit in this plan deleted a tracked file, and no file under `docs/modules`,
  `docs/architecture` or `docs/adr` was modified.

---
*Phase: 03-durability-idempotency-and-no-read-path*
*Completed: 2026-08-11*
