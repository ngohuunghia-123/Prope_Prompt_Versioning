---
phase: 03-durability-idempotency-and-no-read-path
plan: 04
subsystem: backend
tags: [prometheus, observability, fastapi, rabbitmq, retention, tenancy, alerts, supervision]

# Dependency graph
requires:
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 03
    provides: "prope.supervisor — supervise(), interval_job(), run_with_restart() and the supervisor.job_crashed log line the depth job's crash path rides on"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 04
    provides: "prope.worker — run_worker's two-job supervise() map, ObservedWorkspaces, sweep_expired_bodies, and the WorkspaceEnumerator seam Phase 7 replaces"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 05
    provides: "prope.app — create_app, the seven-path table, prope.session_auth.assembled_routes, and tests/integration/_asgi.call"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 01
    provides: "prope.observability — all eighteen metrics defined at import (D-40), including the four this plan gives producers to"
provides:
  - "GET /metrics — the eighth path, a plain APIRoute serving generate_latest(REGISTRY) (D-39)"
  - "prope.worker.read_queue_depths — the passive-declare pass behind queue_depth and dlq_depth (D-42)"
  - "prope.worker.observe_oldest_body_age — the per-workspace min(created_at) reduction behind oldest_body_age_seconds (D-43)"
  - "JOB_QUEUE_DEPTH_GAUGES and DEPTH_GAUGE_INTERVAL_SECONDS — the worker's third resident"
  - "retention_deleted_total's increment site, in run_worker's sweep closure"
  - "deploy/prometheus/rules/call_ledger.rules.yml — EIGHT alert rules with their thresholds and reasons"
  - "tests/architecture/test_alert_rules.py — the only reader of that file, and the thing that stops it rotting"
  - "docs/brainstorm/open_questions/OQ-023.md and OQ-026.md — the two declared deviations"
affects: [03-05-no-read-path, 03-06-load, 07-access-control, 09-ac10-route-table, 23-cross-module-route-table]

actuals:
  tokens: 92000
  tasks: 4
  commits: 1

tech-stack:
  added:
    - "pyyaml==6.0.3 (dev group) — already resolved transitively via uvicorn[standard]; declared so a test about alert rules does not depend on a web server's extras list"
  patterns:
    - "An exposition surface as a plain APIRoute, never a Mount, because a Mount carries no dependant and is invisible to the assembled route table"
    - "A gauge published by a job that does NOT share a failure with the thing it measures"
    - "A cross-tenant reduction computed per enumerated workspace inside the tenant transaction, never as one unscoped query"
    - "An AST walk rather than a substring grep, where the module's own docstrings name the refused shape on purpose"
    - "A repository artifact with no consumer, kept honest by a test that compares it against the registry"
    - "Registry names derived from collected FAMILIES rather than from samples, so a labelled counter with no child cannot make the assertion order-dependent"

key-files:
  created:
    - deploy/prometheus/rules/call_ledger.rules.yml
    - tests/architecture/test_alert_rules.py
    - tests/broker/test_queue_depth_gauges.py
    - docs/brainstorm/open_questions/OQ-023.md
    - docs/brainstorm/open_questions/OQ-026.md
  modified:
    - src/prope/app.py
    - src/prope/worker.py
    - tests/architecture/test_route_table.py
    - tests/integration/test_worker_jobs.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "The alert-rules file ships EIGHT rules, not the plan's seven. The lock file's alerts block declares SEVEN (LedgerDuplicateCallIds included) and plan 03-04's Task 4 table listed six of them plus LedgerDlqNonEmpty, dropping LedgerDuplicateCallIds — which the same plan's objective names as declared. The lock file outranks the plan (ORCHESTRATION §1), and shipping seven would have left a declared alert with no rule in the last phase of its milestone"
  - "/metrics is a plain APIRoute with include_in_schema=True, never app.mount(make_asgi_app()) — a Mount has no dependant, so assembled_routes skips it and it is absent from both the route table and the OpenAPI schema, which is the shape AC-10 exists to refuse"
  - "CONTENT_TYPE_PLAIN_0_0_4, not CONTENT_TYPE_LATEST — the latter says version=1.0.0 in prometheus-client 0.26.0 while generate_latest emits 0.0.4, so the constant's value is a format claim the payload would not honour"
  - "The mount refusal is asserted by an AST walk plus a runtime Mount scan, not by grep — prope.app names the refused shape twice in prose on purpose, exactly the trap test_worker_imports_no_web_framework already documents. The plan's grep criterion still returns 0 because the prose says app.mount( rather than application.mount("
  - "The depth gauges are their own supervised job (D-42), not a read in the drain's window loop: a depth gauge published by the consumer whose backlog it measures goes silent exactly when the backlog matters"
  - "DEPTH_GAUGE_INTERVAL_SECONDS = 15.0, matched to Prometheus's conventional scrape interval, with the honest caveat that the scrape interval is a deployment setting and the deployment stack owns no milestone"
  - "oldest_body_age_seconds is min(created_at) per enumerated workspace reduced to the MAXIMUM, never one unscoped query — under ADR-0045 an unscoped prope_app read returns zero rows and the gauge would read healthy forever, which is the exact failure the alert exists to catch one layer up"
  - "The gauge is clamped at zero. created_at is caller-supplied and unbounded to the past, and a negative age is not a state this gauge can report meaningfully. Same posture as write_lag_seconds' max(0.0, lag)"
  - "retention_deleted_total is incremented in run_worker's sweep closure and NOT inside sweep_expired_bodies or retention.py — the former has callers whose signature must not move, the latter is a pure function with no metric imports and stays that way"
  - "_registered_names() in the alert test expands collected metric FAMILIES rather than samples: a labelled counter with no child renders zero samples, so a sample-derived set would hold whatever earlier tests in the shared process happened to increment"
  - "read_queue_depths carries a keyword-only `gauges` seam and run_worker a `depth_interval_seconds` parameter, neither named in the plan. Both follow the on_chunk / on_backoff observation-seam discipline: keyword-only, defaulted, production passes neither"

patterns-established:
  - "A served path is proved visible in BOTH walks (assembled_routes and app.openapi()) plus proved not to be a Mount, because either walk alone is blind to the failure the other catches"
  - "A test that audits a repository artifact proves its own mechanism against a SYNTHETIC rotten document rather than by editing the artifact it audits"
  - "A blind spot inherited rather than closed is asserted as a test — the gauge reads the enumerated workspace's healthy age while an ancient body sits in an unenumerated one — so the partial close is a fact and not a paragraph"

requirements-completed: []

coverage:
  - id: D1
    description: "GET /metrics returns the Prometheus text exposition of the default registry, with no session and no declared management action"
    verification:
      - kind: integration
        ref: "tests/architecture/test_route_table.py::test_metrics_answers_the_registry_without_a_session"
        status: pass
      - kind: integration
        ref: "tests/architecture/test_route_table.py::test_metrics_declares_no_session_and_no_management_action"
        status: pass
      - kind: integration
        ref: "tests/architecture/test_route_table.py::test_metrics_exposes_a_metric_nothing_has_incremented"
        status: pass
    human_judgment: false
  - id: D2
    description: "/metrics appears in the assembled route table AND in the OpenAPI schema — it is the eighth path, not a mount the assertions cannot see"
    verification:
      - kind: architecture
        ref: "tests/architecture/test_route_table.py::test_metrics_is_a_route_the_table_can_see_and_not_a_mount"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_route_table.py::test_the_assembled_table_is_exactly_the_eight_paths"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_route_table.py::test_the_openapi_schema_agrees_with_the_route_table"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_route_table.py::test_the_unversioned_routes_declare_no_session_and_no_action"
        status: pass
    human_judgment: false
  - id: D3
    description: "queue_depth and dlq_depth are set from the broker's own view of both queues, on an interval, by a job that is not the drain"
    verification:
      - kind: integration
        ref: "tests/broker/test_queue_depth_gauges.py::test_one_pass_sets_both_depths_from_the_brokers_own_view"
        status: pass
      - kind: integration
        ref: "tests/broker/test_queue_depth_gauges.py::test_a_dead_lettered_message_moves_the_dlq_gauge"
        status: pass
      - kind: integration
        ref: "tests/broker/test_queue_depth_gauges.py::test_the_real_pass_reads_exactly_the_two_declared_queues"
        status: pass
    human_judgment: false
  - id: D4
    description: "A wedged or crashed depth pass does not stop the other jobs, and a missing queue surfaces as a restarting job with a supervisor.job_crashed line carrying its job field"
    verification:
      - kind: integration
        ref: "tests/broker/test_queue_depth_gauges.py::test_a_missing_queue_crashes_the_job_instead_of_freezing_the_gauge"
        status: pass
    human_judgment: false
  - id: D5
    description: "The gauge counts READY messages only; a consumer holding messages unacknowledged makes it read below the number published (Pitfall 10)"
    verification:
      - kind: integration
        ref: "tests/broker/test_queue_depth_gauges.py::test_the_gauge_counts_ready_messages_and_not_the_unacknowledged_ones"
        status: pass
    human_judgment: false
  - id: D6
    description: "oldest_body_age_seconds reports the age of the oldest surviving body across every enumerated workspace, reduced to the maximum, and is zero when there are none"
    verification:
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_the_age_gauge_reads_the_age_of_the_oldest_body_it_can_see"
        status: pass
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_the_age_gauge_reads_the_larger_of_two_workspaces"
        status: pass
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_the_age_gauge_reads_zero_when_there_are_no_bodies_at_all"
        status: pass
    human_judgment: false
  - id: D7
    description: "The cold-workspace blind spot is a PARTIAL close, asserted rather than believed: an ancient body in an unenumerated workspace leaves the gauge unmoved"
    verification:
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_an_ancient_body_in_an_unenumerated_workspace_leaves_the_gauge_unmoved"
        status: pass
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_a_workspace_the_enumerator_omits_keeps_its_expired_bodies"
        status: pass
    human_judgment: false
  - id: D8
    description: "test_plan.chaos clause 4 — a sweep whose predicate matches nothing reports success and raises nothing WHILE the age gauge reads above the retention window"
    verification:
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_a_sweep_that_deletes_nothing_reports_success_while_the_gauge_reads_overdue"
        status: pass
    human_judgment: false
  - id: D9
    description: "retention_deleted_total moves by the number of body rows a sweep pass actually deleted"
    verification:
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_one_sweep_pass_moves_retention_deleted_total_by_the_rows_it_removed"
        status: pass
    human_judgment: false
  - id: D10
    description: "The worker runs three supervised jobs and the three names are the closed set its module docstring, its constants and its test all state"
    verification:
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_the_worker_runs_exactly_the_three_jobs_this_file_composes"
        status: pass
      - kind: integration
        ref: "tests/integration/test_worker_jobs.py::test_worker_imports_no_web_framework"
        status: pass
    human_judgment: false
  - id: D11
    description: "Every metric named by an alert rule exists in the registry, and all eight alert names are present — both directions fail"
    verification:
      - kind: architecture
        ref: "tests/architecture/test_alert_rules.py::test_every_metric_named_by_a_rule_exists_in_the_registry"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_alert_rules.py::test_the_rules_file_parses_and_holds_exactly_the_declared_alerts"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_alert_rules.py::test_a_rule_naming_a_metric_that_does_not_exist_is_reported"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_alert_rules.py::test_the_name_expansion_matches_what_prometheus_client_actually_renders"
        status: pass
    human_judgment: false
  - id: D12
    description: "Every rule carries a severity and a real reason; exactly two page; LedgerPublishFailing names both counters and says why; LedgerRetentionOverdue names both its caveats"
    verification:
      - kind: architecture
        ref: "tests/architecture/test_alert_rules.py::test_every_rule_carries_a_severity_and_a_reason"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_alert_rules.py::test_the_two_alerts_that_page_are_the_two_that_mean_data_is_gone"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_alert_rules.py::test_publish_failing_reads_both_counters_and_says_why"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_alert_rules.py::test_retention_overdue_names_both_of_the_caveats_it_ships_with"
        status: pass
    human_judgment: false
---

# Plan 03-04 — the eighteen metrics made readable, the three gauges given producers, and the alerts written down

## What shipped

Four things, in the plan's order.

**`GET /metrics` on `app`, as the eighth path.** A plain `APIRoute` returning
`generate_latest(REGISTRY)` with `media_type=CONTENT_TYPE_PLAIN_0_0_4`, unversioned, sessionless, with
no declared `ManagementAction`. `EXPECTED_ROUTES` went from seven paths to eight and `UNVERSIONED`
from two to three, and every assertion that moves with those counts moved.

**The depth-gauge job — the worker's third resident.** `read_queue_depths` passive-declares
`prope.call_record` and `prope.call_record.dlq` on a fresh channel each, per pass, and sets
`queue_depth` and `dlq_depth` from `declaration_result.message_count`.
`JOB_QUEUE_DEPTH_GAUGES = "queue_depth_gauges"` joins the two existing job names;
`DEPTH_GAUGE_INTERVAL_SECONDS = 15.0` is argued against the scrape it feeds. `retention_deleted_total`
got its increment site in the same change, at the sweep closure that had been discarding
`sweep_expired_bodies`' return value.

**`oldest_body_age_seconds`, computed from the data.** `observe_oldest_body_age` runs one indexed
`min(created_at)` read per enumerated workspace, inside that workspace's own transaction, and reduces
to the maximum age. Composed into the retention sweep, sharing that pass's single `now`.

**`deploy/prometheus/rules/call_ledger.rules.yml` and the test that stops it rotting.** Eight rules —
see below — each with `expr`, `for`, `labels.severity` and an `annotations.description` carrying the
reasoning. `tests/architecture/test_alert_rules.py` is the file's only reader.

---

## Why `/metrics` is a route and not a mount

`prometheus_client.make_asgi_app()` mounted with `app.mount(...)` produces a Starlette `Mount`.
`prope.session_auth.assembled_routes` appends a route only if it has `effective_route_contexts` **or**
a non-`None` `dependant`, and a `Mount` has neither — so a mounted exposition is skipped by the helper
that every route assertion in this repository is built on. It would also be absent from
`app.openapi()`.

**The failure is not that the assertion breaks. It is that nothing breaks at all.** Both count
assertions in `test_route_table.py` compare a table built *from* `assembled_routes` against a literal
list, so a `Mount` is invisible to both and they would keep passing at seven.
`test_the_router_and_the_health_routes_are_the_only_things_mounted` walks raw `app.routes` but asserts
only that `/docs`, `/redoc` and `/openapi.json` are absent. So `/metrics` would have been served,
unauthenticated, and invisible to every route assertion in the repository — which is precisely the
shape AC-10 exists to refuse, and the same class of hole Broken Window #4 already records one layer
in: a route the *helper* cannot see rather than one the *test* cannot see. Mounting at `/metrics` also
serves `/metrics/` with a 307 in front, which is the smaller second reason.

`test_metrics_is_a_route_the_table_can_see_and_not_a_mount` asserts the property in three directions —
present in `_table()`, present in `app.openapi()["paths"]`, and no `.mount(` call anywhere in
`prope.app` — because the path alone would pass under a mount that happened to have a route beside it.

---

## The metrics that remain unreadable or partial, and why the fix is out of reach

`prometheus_client`'s registry is **per process** and Prope runs two. `worker` serves no HTTP by D-17,
which is *derived from* ADR-0028 rather than chosen in discussion, so it is not this phase's to
reverse — and the refusal is mechanical as well as architectural: `test_worker_imports_no_web_framework`
goes red on the import alone, before a line of server code is written.

**Absent entirely from `/metrics` — eight, incremented only in `worker`:** `written_total`,
`write_lag_seconds`, `queue_depth`, `dlq_depth`, `redelivered_total`, `retention_deleted_total`,
`oldest_body_age_seconds`, `ceiling_check_total`.

**Partial — four, incremented in both processes, so `app`'s copy is the fallback's share alone:**
`unpriced_total`, `unknown_usage_total`, `missing_version_id_total`, `duplicate_call_id_total`.

**Three of the eight rules read metrics on that list:** `LedgerWriteLagHigh`,
`LedgerRetentionOverdue` (which pages) and `LedgerDuplicateCallIds`.

`OQ-026` carries the list and the four rejected answers with their costs — a metrics port on `worker`,
a Pushgateway, multiprocess mode over a shared volume, and shipping nothing. Multiprocess mode is the
only genuinely viable one and it is a change to a **deployment stack that owns no milestone**, which
is itself part of what the question is asking.

`OQ-026`'s second clause is the declaration defect: `apis.exposes` does not list `/metrics`, and
`interfaces.md:1236-1239` says in as many words that the line *"should gain an `exposes` line during
step 6"*. Step 6 ran (`ready_for_build: true`) and did not add it, while ADR-0052's Caddyfile already
routes `handle /metrics { reverse_proxy app:8000 }`. The route ships with the deviation declared; no
spec file was edited.

---

## The cold-workspace half of `oldest_body_age_seconds` is a PARTIAL close

The gauge measures the data — that half is true, and it is the whole reason `LedgerRetentionOverdue`
reads a gauge rather than a job's exit status. It measures the data **for enumerated workspaces
only**, because it walks the same `ObservedWorkspaces` the retention sweep does.

**So the gauge inherits Broken Window #3 instead of catching it.** `ObservedWorkspaces`' docstring
promised the opposite — *"Phase 3's `oldest_body_age_seconds` gauge reads above the window for exactly
those workspaces"* — and that paragraph was corrected in this change rather than left standing. It was
not cosmetic: it was a load-bearing sentence that had become false, of the exact kind this job exists
to refuse (something that reports healthy because it looked at nothing).

`test_an_ancient_body_in_an_unenumerated_workspace_leaves_the_gauge_unmoved` asserts the omission
holds, so the partial close is a fact rather than a paragraph. Phase 7 closes it by passing an
enumerator backed by `access.list_workspaces()` into `run_worker` — **a replaced argument, not an
edited job**. The delete-together instruction now names three things: that test, its retention twin,
and `ObservedWorkspaces`' corrected paragraph.

**No fifth `SECURITY DEFINER` function was created**, and the architecture test asserting the set is
exactly four passes unchanged.

---

## What the alert-rules test can and cannot claim

**Can:** the file is well-formed YAML; every `prope_call_ledger_*` name any `expr` mentions exists in
the registry as a family this application declares; all eight alert names are present, with no
duplicates; every rule carries a severity from `{page, ticket}` and a description that is not a
restatement of its summary; the two rules that page are the two that mean data is gone;
`LedgerPublishFailing` names both counters and cites `OQ-022`; `LedgerRetentionOverdue` names both its
caveats.

**Cannot:** it does not prove the file is a valid *Prometheus rules file* — that schema is
Prometheus's, not YAML's — and it does not prove that a single PromQL expression parses. A rule whose
`expr` is grammatical nonsense over real metric names passes everything. That is `promtool check
rules`, which needs a binary this repository does not have and which PITFALLS §4 gives no home to. The
boundary is written at the top of the test file so no reader infers more.

Both directions were demonstrated by temporary local edit and then restored:

```
# after replacing LedgerDlqNonEmpty's expr with prope_call_ledger_spill_bytes > 0
E       AssertionError: rules name metrics that do not exist: ['prope_call_ledger_spill_bytes']
FAILED tests/architecture/test_alert_rules.py::test_every_metric_named_by_a_rule_exists_in_the_registry
1 failed, 7 passed, 1 warning in 7.21s

# after renaming LedgerDuplicateCallIds
FAILED tests/architecture/test_alert_rules.py::test_the_rules_file_parses_and_holds_exactly_the_declared_alerts
1 failed, 7 passed, 1 warning in 6.92s
```

The file was restored byte-for-byte (the one surviving `prope_call_ledger_spill_bytes` in it is the
header comment's worked example, which the extractor never sees because it reads `expr` values only).

---

## Deviations from Plan

### 1. EIGHT alert rules, not seven — the plan miscounted the lock file (BLOCKING-CLASS, resolved)

`docs/modules/call-ledger.lock.yml`'s `observability_requirements.alerts` block declares **seven**
alerts: `LedgerMetadataDropped`, `LedgerPublishFailing`, `LedgerWriteLagHigh`,
`LedgerBodyDropRateHigh`, `LedgerPriceMissing`, `LedgerRetentionOverdue` and **`LedgerDuplicateCallIds`**.

`03-04-PLAN.md`'s Task 4 table has seven rows: six of those plus `LedgerDlqNonEmpty`. It **omits
`LedgerDuplicateCallIds` entirely** — while the same plan's `<objective>` names that alert as one of
the three declared alerts reading unreadable metrics, and `03-CONTEXT.md`'s D-44, the plan's success
criteria and `COVERAGE.md` all say *"the six alert rules"*.

The lock file outranks the plan (ORCHESTRATION §1), so **eight rules ship** and `DECLARED_ALERTS` is a
literal frozenset of eight with the reason written at the constant. Shipping seven would have left a
declared alert with no rule, in the last phase of the milestone that owns it, where nobody inherits
it. The acceptance criterion *"exactly seven rules ... the lock file's six plus `LedgerDlqNonEmpty`"*
is met in substance and exceeded in count; no test was weakened.

### 2. The mount refusal is an AST walk, not a `grep`

The plan's acceptance criterion is `grep -c "application.mount(" src/prope/app.py` returning 0, and it
does. But the criterion is the wrong assertion for the property, and this repository already knows
why: `test_worker_imports_no_web_framework`'s docstring says *"An AST walk, not a string search — the
docstring names `/healthz` on purpose"*. The plan also *requires* `prope.app` to explain the refused
shape at length, which it now does twice. The first version of the test grepped and failed on the
module docstring.

So the test walks the parsed source for any `ast.Call` on an attribute named `mount`, **and** walks
`app.routes` for a `starlette.routing.Mount` instance — both strictly stronger, the second catching a
mount that arrived through a spelling the parser never sees. The prose was written as `app.mount(...)`
rather than `application.mount(...)` so the plan's literal criterion also holds.

### 3. The registry side of the alert test reads FAMILIES, not samples

The plan says to *"collect the registry's sample names from `REGISTRY.collect()`"*. That is unsound
here: **a labelled counter with no child renders zero samples**, and six of the eighteen metrics are
labelled. A sample-derived set would hold whatever earlier tests in the shared process happened to
increment, so the assertion would pass in a full run and fail alone, or the reverse.

`_registered_names()` therefore expands each collected family by `prometheus_client`'s own rendering
rule. The family exists from import — which is exactly the property D-40 was taken for. The plan's
`_total`-suffix trap is handled inside that expansion, and the expansion itself is asserted against a
known counter, gauge and histogram plus one deliberately unreal name, as the plan required.

### 4. Two parameters the plan did not name

`read_queue_depths(connection, *, gauges=DEPTH_GAUGES)` and
`run_worker(..., depth_interval_seconds=DEPTH_GAUGE_INTERVAL_SECONDS)`. Both follow the observation-seam
discipline `delete_expired_bodies`' `on_chunk` and `run_with_restart`'s `on_backoff` already set:
keyword-only, defaulted, production passes neither.

`gauges` exists because the channel-level-error branch cannot otherwise be provoked — a test cannot
delete `prope.call_record` to make the point, since the declaration is one-way (D-23) and the whole
session shares one broker. `depth_interval_seconds` exists so `run_worker`'s standing sentence *"every
parameter after `stopping` exists so this composition is drivable from a test"* stays true now that
there are two schedules.

### 5. The age gauge is clamped at zero

`created_at` is the caller's own instant and is not bounded to the past, so a future-stamped body could
drive the reduction negative. `max(0.0, oldest)`, named at the function, same posture as
`write_lag_seconds`' `max(0.0, lag)`. One line the plan did not specify.

### 6. `tests/architecture/test_route_table.py` now imports `tests.integration._asgi`

The behavioural criteria for `/metrics` (200, content type, body contents, no session) need a request
through the ASGI stack, and `_asgi.call` is this project's answer to that — `httpx` is deliberately not
a dependency. Cross-package test imports have precedent (`test_worker_jobs.py` imports
`tests.broker._helpers`), but this is the first one **into** `tests/architecture/`, which was until now
a package of pure source-and-schema walks. Phase 23 extends this file and should know.

### 7. Two prose corrections outside the plan's literal instruction list

`create_app`'s docstring said an unauthenticated `/docs` would be *"the sixth, seventh and eighth paths
in a table this phase asserts holds seven"*, and
`test_the_router_and_the_health_routes_are_the_only_things_mounted`'s said *"the eighth, ninth and
tenth entries ... holds seven"*. Both became false at eight paths and both were corrected. Neither is
asserted by a string test; both were fixed because a stale count in prose is the thing this phase spends
three paragraphs refusing elsewhere.

### 8. Files touched outside `files_modified`

`.planning/phases/03-durability-idempotency-and-no-read-path/deferred-items.md` (Part 8 appended, as
instructed) and this SUMMARY. Both are the standing per-plan artifacts; neither is code.

---

## Discretion items the plan directed be resolved

| Item | Resolution | Argument |
|---|---|---|
| The depth-gauge interval | `DEPTH_GAUGE_INTERVAL_SECONDS = 15.0` | Matched to Prometheus's conventional `scrape_interval`. Below it, round trips buy samples nothing reads; above it, a staircase Prometheus cannot smooth and an alert one interval late. Rejected 5 s (3× the round trips) and 60 s (a DLQ message invisible for a minute, and `dlq_depth > 0` is T-005's HIGH mitigation). Caveat carried at the constant: the scrape interval is a **deployment** setting and the deployment stack owns no milestone |
| The age-gauge query shape | `min(created_at)`, not a predicate over `expires_at` | Both columns are indexed, so this is semantic. The metric is an **age**; the alert compares an age; and **D-10 is decisive** — `expires_at` is stamped once and never rewritten, so for a workspace that shortened its window `min(expires_at)` reflects the OLD policy and reads healthy against the new one, which is exactly the failure the alert exists to catch |
| PyYAML | Declared `pyyaml==6.0.3` in the dev group | It was already resolved and importable — but only as a transitive extra of `uvicorn[standard]`, whose extra list is uvicorn's to change. A test that imports `yaml` undeclared breaks on an unrelated web-server upgrade, in a file whose whole purpose is to stop another file from rotting. `uv sync` moved `uv.lock` by exactly two lines and added no package |

---

## Verification

```
$ uv run pytest -q
........................................................................ [ 20%]
........................................................................ [ 40%]
........................................................................ [ 60%]
........................................................................ [ 80%]
........................................................................ [100%]
360 passed, 1 warning in 200.50s (0:03:20)
```

```
$ uv run ruff check src/ tests/ alembic/
All checks passed!
ruff exit=0
```

```
$ git status --porcelain docs/modules docs/architecture docs/adr Dockerfile docker-compose.yml
(no output)
```

```
$ grep -c "application.mount(" src/prope/app.py
0
```

Per-task, as they were finished:

```
$ uv run pytest tests/architecture/test_route_table.py -q
20 passed, 1 warning in 8.37s

$ uv run pytest tests/broker/test_queue_depth_gauges.py tests/integration/test_worker_jobs.py -q
23 passed, 1 warning in 30.55s

$ uv run pytest tests/architecture/test_alert_rules.py -q
8 passed, 1 warning in 11.03s
```

The suite grew from **337** (the 03-03 baseline) to **360**, +23. No Phase 1 or Phase 2 test was
weakened, skipped or deleted;
three moved, all three anticipated by the plan:

| Test | Change |
|---|---|
| `test_the_assembled_table_is_exactly_the_seven_paths` | renamed `..._eight_paths`; `EXPECTED_ROUTES` grew by one entry |
| `test_the_health_routes_are_unversioned_and_declare_nothing` | renamed `test_the_unversioned_routes_declare_no_session_and_no_action`; `UNVERSIONED` grew from two paths to three, so *"the health routes"* would have become a lie |
| `test_the_two_supervised_jobs_are_the_lock_files_two_residents` | renamed `test_the_worker_runs_exactly_the_three_jobs_this_file_composes`, and strengthened: it now enumerates every `JOB_*` name in the module and requires each to appear as a key in `run_worker`'s `supervise()` map, so a constant without a job — or a job without a constant — fails |

---

## Human Verification Required

Carried from the plan's `<human-check>` blocks, plus one this execution added.

1. **`OQ-026`.** Twelve of the eighteen metrics are unreadable or partial from `app`'s `/metrics`, and
   three of the eight rules read metrics on that list. Confirm this ships as a declared gap, and choose
   among the four recorded answers (a port on `worker`, a Pushgateway, multiprocess mode over a shared
   volume, or leaving it) before the deployment stack is built.
2. **`LedgerRetentionOverdue`'s threshold.** It is per-workspace and the gauge it reads is unlabelled
   and reduced, so the rule compares against the 30-day default plus one day. Confirm that a workspace
   with a longer window false-positiving is acceptable until `OQ-022` is answered.
3. **The rules file has no consumer and never will inside this roadmap.** Confirm that shipping it as a
   reviewed repository artifact — thresholds and reasons written down, with a test that keeps its metric
   names real — is the intended outcome rather than a service nobody ordered.
4. **NEW — the alert count.** The lock file declares seven alerts; the plan's Task 4 table listed six of
   them. Eight rules ship (seven declared plus T-005's `LedgerDlqNonEmpty`). Confirm that is the intended
   set, and note that *"the six alerts"* is wrong in `03-CONTEXT.md` D-44, in `03-04-PLAN.md` and in
   `COVERAGE.md`. No upstream spec file was edited.
5. **`OQ-023`.** `unpriced_total`'s declared labels carry a per-workspace identifier
   (`provider_config_id`) and the registry is now served on an unauthenticated route. Both halves are
   correct in isolation and neither is fixable inside call-ledger. Confirm the exposure is acceptable, or
   pick one of the four recorded answers.

---

## Flagged Assumptions Carried to Verification

- **15 s is matched to a convention, not to a configured value.** There is no Prometheus in this
  repository and no `scrape_interval` anywhere to check it against. If the deployment stack is ever
  built with a different scrape interval, `DEPTH_GAUGE_INTERVAL_SECONDS` is what moves.
- **The depth gauges' round-trip cost is stated, not measured.** *"Single-digit milliseconds on a
  compose network"* is an estimate. The tests run against a testcontainer on a Windows host and were not
  timed.
- **`test_a_missing_queue_crashes_the_job...` asserts the exception class as a literal string**
  (`ChannelNotFoundEntity`, discovered by running it). An aio-pika upgrade that renames it fails this
  test loudly, which is the intended behaviour but is worth knowing.
- **No load or scale validation of `observe_oldest_body_age`.** It is N+1 transactions per sweep on top
  of the sweep's own N+1, accepted at pilot scale by the same A-140 reasoning the sweep already carries.

---

## Known Stubs

None introduced. `ObservedWorkspaces` remains the stand-in it already was (Broken Window #3), and this
plan narrowed what it claims rather than widening what it does.

---

## Threat Flags

All eight rows of the plan's STRIDE register were addressed as written:

- **T-03-26** (a route the assertion cannot see) — mitigated by the plain `APIRoute` plus the
  three-direction test. This was the highest-value single decision in the plan.
- **T-03-29** (a retention gauge reporting healthy because it read zero rows) — mitigated by the
  per-workspace read; the unscoped form appears nowhere in `src/`.
- **T-03-30** (the cold-workspace blind spot reported as closed) — **accepted, declared**, and now
  named in five places: the gauge's docstring, `ObservedWorkspaces`' corrected paragraph, a test,
  `LedgerRetentionOverdue`'s annotation, and `deferred-items.md`.
- **T-03-31** (a fifth `SECURITY DEFINER` function) — refused outright; the sanctioned-set test passes
  unchanged.
- **T-03-32** (cardinality) — `queue_depth`, `dlq_depth` and `oldest_body_age_seconds` all ship
  unlabelled; `test_workspace_id_is_never_a_metric_label` passes at eighteen metrics.
- **T-03-25** (an unauthenticated `/metrics`) — mitigated as far as this module can, and the residue —
  `unpriced_total`'s per-workspace labels — is raised as `OQ-023` rather than resolved by dropping a
  declared label.

---

## Notes for the next plans

- **Plan 03-05** extends `tests/architecture/` with the no-read-path proof. That package is no longer
  import-free: `test_route_table.py` now imports `tests.integration._asgi`. Also, `/metrics` returns a
  `Response` and therefore contributes **no component schema**, so the OpenAPI body-name walk is
  unaffected by the eighth path.
- **Plan 03-06**'s paced run drives the drain in-process, so `write_lag_seconds` is readable there
  regardless of `OQ-026`. It should assert the durable side — rows in `ledger.call_record` — and never
  `queue_depth`, which counts **ready** messages and can read zero while 500 are in flight.
- **Phase 7** replaces `run_worker`'s `workspaces` argument with `access.list_workspaces()`. Three
  things are then deleted together: `test_a_workspace_the_enumerator_omits_keeps_its_expired_bodies`,
  `test_an_ancient_body_in_an_unenumerated_workspace_leaves_the_gauge_unmoved`, and
  `ObservedWorkspaces`' corrected paragraph. Nothing in `observe_oldest_body_age` changes.
- **Phase 7/9** meets `UNVERSIONED`, which grew from two paths to three. It is the exemption list for
  access-control's AC-10 — *"a route declaring none fails the test rather than defaulting to
  unauthenticated"* — and the reasoning for the third entry is written at the set.
- **Phase 23** replaces `EXPECTED_ROUTES` with eight modules' worth of paths. `/metrics` is the one
  entry no lock file's `apis.exposes` declares; `OQ-026` clause 2 is where that is recorded.
- **A future "grep the repository for retired metric names"** check will hit
  `prope_call_ledger_spill_bytes` in the rules file's header comment, where it is the worked example of
  the rot the test catches. Scope such a check to `expr:` values.

---

## Self-Check: PASSED

- [x] Every task's `<automated>` verify command run and green
- [x] `uv run pytest -q` green across the whole suite — **360 passed**
- [x] `uv run ruff check src/ tests/ alembic/` exits 0
- [x] No test weakened, skipped, `xfail`ed or deleted; three renamed, all anticipated by the plan, one strengthened
- [x] No file under `docs/modules`, `docs/architecture` or `docs/adr` touched; no `Dockerfile` or `docker-compose.yml` change
- [x] Two OQ files created (`OQ-023`, `OQ-026`), both `status: open`, `blocks_build: false`
- [x] No fifth `SECURITY DEFINER` function; no `workspace_id` metric label; no ASGI import in `worker.py`
- [x] Every file touched outside `files_modified` named, in `deferred-items.md` Part 8 and above
- [x] The plan's count of the lock file's alerts was wrong; corrected in code, recorded, and not fixed by editing the spec
