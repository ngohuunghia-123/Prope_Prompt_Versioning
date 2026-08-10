# Phase 3 — Deferred items

Out-of-scope discoveries, declared deviations, and decisions adopted without a human in the loop.
Seeded by the planner; the executor and the reviewer append.

> **How to read the `UNCONFIRMED` entries.** ORCHESTRATION §6 puts this run in `mode: yolo`: a genuine
> one-way decision is still written out in full — both options, both costs, the reversibility rating —
> and then **one is adopted and marked `adopted: UNCONFIRMED`** rather than blocking on the user.
> Every one of them belongs on `03-UAT.md` as a numbered human-verification item and in
> `.planning/ORCHESTRATION-DECISIONS.md` as one row, so the user has a single list to adjudicate
> rather than twenty-two buried ones.

---

## Part 1 — Decisions adopted UNCONFIRMED

### 1. The broker was never reachable at startup — `fallback-only-job` (plan 03-01, Task 1)

**Reversibility: cheap.** `app.py:129-134` currently catches every exception from the broker bring-up
and **returns without creating any task at all**, so `enqueue()` fills the 512-record handoff and then
drops — with no publish attempt and therefore no fallback call — in exactly the scenario ADR-0041 was
written about. D-26 places the fallback on `publish_record`'s failure sites and is silent about the
path where no publisher exists, so this gap is the planner's to close.

**Adopted:** start a **fallback-only job** in place of the publisher when the broker is absent, rather
than starting the publisher with a nullable exchange. The composition root chooses between two job
bodies, which is what a composition root is for; a nullable exchange would put the degraded case
inside the function that handles the healthy one, and `publish_record`'s signature is the seam Phase
19's gateway inherits.

**What a human should actually rule on** is not the shape but its consequence: with this adopted, a
process that starts against a dead broker **never publishes until it is restarted**, because
`connect_robust`'s recovery is attached to a connection that was never established. Records are
durable throughout — that is the point — but the queue stays empty and the drain has nothing to do.
Whether that is acceptable, or whether the composition should retry the connection on an interval, is
a product question this phase does not own.

### 2. `MAX_BODY_BYTES = 256 KiB` (plan 03-01, Task 3)

**Reversibility: cheap** — a constant with a counter behind it, and no stored data depends on it — but
it is a **product-visible policy** and belongs on the human list. The lock file's eighth failure mode
requires a cap and states no number anywhere.

Argued from ADR-0033's *"roughly 10 KB per call"* sizing (26×), from the token arithmetic (~64k tokens
of UTF-8, above the context window of pilot models, so a body above it is an asset or a base64 blob
rather than a conversation), and from broker disk (the queue's bound is a message count, so the real
ceiling is the 24-hour TTL: ≤2.5 GB at the ADR's 10k calls/day). Rejected: 64 KiB, which would make
`body_dropped_total{reason="oversize"}` a normal-traffic counter; and no cap, since nothing else on
the path bounds bytes.

**Consequence:** a request/response pair above the cap is recorded as metadata with **no body,
permanently**. The record is never dropped for its body's sake.

### 3. `metadata_dropped_total` stops counting dead-letters (plan 03-02, Task 2, D-30)

**Reversibility: cheap**, but it **changes what an existing page means**, and a removal is the kind of
change that gets skipped rather than argued.

After the fallback, ADR-0041 says this counter means *"both the broker and the database were
unavailable"* and `LedgerMetadataDropped` pages immediately. `drain.py` increments it twice for records
it **dead-letters**, which are in `prope.call_record.dlq` with a 30-day TTL and an alert on any
non-zero depth. Both increments are removed; `dlq_depth > 0` is the substitute signal.

**Confirm:** that a failed confirm absorbed by the fallback should page nobody, and that
`LedgerPublishFailing` (ticket, not page) is the intended signal for it.

### 4. `MAX_RETENTION_DAYS = 3650` (plan 03-03, Task 2, CR-01)

**Reversibility: cheap**, and it is a **product-visible limit**: no workspace can set a retention
window longer than ten years through the API. Argued as the largest value that is still recognisably a
retention *policy* while keeping an input from becoming an unclassifiable `OverflowError` — longer
than the pilot, longer than anything OQ-013 could plausibly answer, and short enough that "never
delete", the one answer ADR-0018 and A-040 refuse, cannot be spelled in the field.

### 5. `prope_report` keeps its `SELECT` on `ledger.call_body` (plan 03-05, Task 3)

**Reversibility: one-way-ish** — the migration either way is cheap, but the *claim* is not: ADR-0037
records `prope_report` as a deliberate full-read reporting credential and ADR-0036's restore rehearsal
assumes it, so a revoke makes "full-read" into "full-read except one table" and every later reader
inherits that reading.

**The exposure, verified:** `prope_report` is created `LOGIN BYPASSRLS`
(`alembic/versions/0001_roles_and_schemas.py:47`), `grant_table`'s `report_select` defaults to `True`
(`alembic/ddl.py:103`), and `0003_ledger_tables.py:252` took that default for `ledger.call_body`. So
**one statement on that credential reads every stored body in every workspace**, RLS bypassed by role
attribute. `tests/conftest.py:162-167` already builds that engine as a session fixture. None of
D-38's three layers can see it: layers 1 and 2 are about this application and layer 3 is about the
statements this application contains.

**Adopted: leave the grant, assert the exposure deliberately, and route it to `OQ-025`.** Three
reasons. (a) *Scope* — SC4 is about routes, parameters and functions, and a database role is none of
the three; ORCHESTRATION §5 prescribes naming the excess and handing it upstream. (b) *Level* —
`report_select` defaults to `True` for **every** table, so revoking on one table fixes one table and
leaves the pattern intact; the decision that matters is what the default should be for a table
declared to have no reader, which is above this phase. (c) *Reversibility* — leaving it and revoking
later costs one migration; revoking now against an unbuilt restore rehearsal and an ADR that records
the opposite costs a claim every later module reads, in a phase that cannot amend either document.

**Refused outright:** doing nothing and mentioning it nowhere. A year later, *"we looked and decided
not to"* and *"nobody looked"* are indistinguishable.

**Two things to confirm:** the disposition itself, and the class-level question — should
`grant_table`'s `report_select` default be `False` for tables declared to have no reader?

### 6. The load split — a CI-resident proxy plus a skipped full-fat run (plan 03-06)

**Reversibility: cheap.** ROADMAP SC5's literal condition (50 rps × 10 min, 30,000 records) exists as
a test and is **skipped** rather than deselected, with `make load` as its documented invocation.
`make check` deliberately does not depend on it, so the routine gate does not carry ten minutes.

**Confirm:** that trade, and the proxy's argument for standing in between full runs — that nothing in
`enqueue()`'s span scales with elapsed time, and what duration adds is buffer depth, which the proxy
buys directly at the lock file's stated 80%.

**And the flake posture:** a timing assertion runs on every `uv run pytest`. The recorded rule is one
re-run, then investigate — **never raise the threshold**, which is the lock file's rather than the
test's.

---

## Part 2 — Open questions allocated and raised

All five allocated ids are used; `03-CONTEXT.md` requires that all five be raised. Every one is
`blocks_build: false` — the code ships either way and the deviation is declared, not resolved.

| Id | Raised by | Blocks | What it says |
|---|---|---|---|
| **OQ-022** | 03-01 | `call-ledger.lock.yml` `observability_requirements.metrics` · **and `failure_modes` row 2 / `alerts` `LedgerPublishFailing`** | Five clauses. Four against `metrics`: `body_dropped_total`'s `reason` set is `queue_full \| oversize` and neither is true for a fallback drop; `queue_depth`'s `lane = metadata \| body` describes the two in-process lanes ADR-0041 deleted, and a broker queue has one depth; `prope_call_ledger_dlq_depth` is required by T-005 and absent from the list the ROADMAP counts at seventeen; and `LedgerRetentionOverdue` compares against *"the workspace's retention window plus one day"* while the metric it reads is declared unlabelled. **Clause 5 (added at critique):** `publish_failed_total`'s `reason` set is closed at three values that all mean *the broker answered and refused*, so a closed channel (the bare-`except` branch) and a broker absent at startup (no `publish_record` call at all) move it by **zero** — leaving `LedgerPublishFailing` silent in exactly the outage `failure_modes` row 2 describes. Plan 03-04's rule reads `fallback_direct_write_total` **or** `publish_failed_total`; the rejected alternative is a fourth `reason` value |
| **OQ-023** | 03-04 | `call-ledger.lock.yml` `observability_requirements.metrics` | `unpriced_total`'s declared labels `provider_config_id, upstream_model` are per-workspace identifiers — a `provider_config_id` resolves to exactly one workspace — while `observability.py` states `workspace_id` is never a label and a test enforces it. The question became concrete the moment `/metrics` shipped unauthenticated |
| **OQ-024** | 03-01 | `call-ledger.lock.yml` `test_plan.chaos` and `test_plan.unit` | *"Fill the spill volume and assert the page fires and readiness is withheld"* and *"queue accounting and the two-lane drop order"* both test machinery ADR-0041 deleted, and the first contradicts the amended `/readyz` clause **in the same file** — D-16's readiness is the database alone and a broker failure is degraded-and-counted, never un-readiness |
| **OQ-025** | 03-01 (clause 1) · **appended by 03-05** (clause 2) | `call-ledger.lock.yml` `security_requirements` T-005 / A-149 · and ADR-0037 | *A stored body rests somewhere no assertion in this repository reaches.* **Clause 1:** the queue's declared bound is a message count with no byte bound at any layer, `x-max-length-bytes` was never declared and cannot be added without D-23's delete-and-redeclare, while T-005's own text says the broker is a second body store. **Clause 2:** `prope_report` is `LOGIN BYPASSRLS` with `SELECT` on `ledger.call_body` |
| **OQ-026** | 03-04 | ADR-0028 / D-17 against `observability_requirements` and `alerts` · **and `call-ledger.lock.yml` `apis.exposes`** | **Clause 1:** `prometheus_client`'s registry is **per process** and Prope runs two. Eight metrics exist only in `worker`, four more are incremented in both so `app`'s copy is partial, and **three of the six declared alerts** (`LedgerWriteLagHigh`, `LedgerRetentionOverdue`, `LedgerDuplicateCallIds`) read metrics on that list. Four rejected answers are recorded with their costs. **Clause 2 (added at critique):** `/metrics` is the eighth served path and `apis.exposes` does not declare it. `interfaces.md:1236-1239` says the line *"should gain an `exposes` line during step 6"*; step 6 ran (`ready_for_build: true`) and did not add it. ORCHESTRATION §5 requires naming the field rather than absorbing the gap. Also records that `UNVERSIONED` grows from two to three, which access-control's AC-10 will meet in Phase 7/9 |

**A sixth conflict has no allocated id and is deliberately not given one.** `prope_report`'s grant is
filed as `OQ-025`'s second clause rather than as `OQ-027`, because both clauses are the same question
and because **OQ-027 may belong to the phase being planned in parallel**. Only the orchestrator may
allocate outside this phase's range.

---

## Part 3 — Partial closes carried forward with their residue named

### `oldest_body_age_seconds` covers only enumerated workspaces (plan 03-04, D-43)

The gauge ships and measures the **data** — one indexed `min(created_at)` read per workspace inside
the tenant transaction, reduced to the maximum across workspaces, on one unlabelled gauge. It cannot
be one query: under ADR-0045 an unscoped `prope_app` read returns **zero rows**, so
`SELECT min(created_at) FROM ledger.call_body` would report a healthy gauge forever, which is the
exact failure `LedgerRetentionOverdue` exists to catch, one layer up.

**The residue:** a workspace that has sent no traffic since process start is invisible to the gauge
that exists to notice its unswept bodies. `ObservedWorkspaces`' docstring currently *promises* this
gauge catches that gap; plan 03-04 corrects that paragraph, because after this phase the gauge
**inherits** the gap instead. Closing it needs `access.list_workspaces()` in **Phase 7**, and
`run_worker` already takes the enumerator as a parameter, so Phase 7 replaces an argument rather than
editing the job. `02-VERIFICATION.md` deferred item 4 routed this here and it is honestly a **partial**
close.

This is asserted rather than believed: `test_a_workspace_the_enumerator_omits_keeps_its_expired_bodies`
stays, and plan 03-04 adds a companion asserting that an ancient body in an omitted workspace leaves
the gauge unchanged. The delete-together instruction now covers three things: that test, this one, and
`ObservedWorkspaces`' docstring.

### Twelve of the eighteen metrics are unreadable or partial (plan 03-04, D-39)

`/metrics` ships on `app` and eight metrics live only in `worker`; four more are incremented in both
processes, so `app`'s copy is a partial count. This is `OQ-026`'s subject and it may land in the
**deployment stack, which owns no milestone** (PITFALLS §4) — so there is currently nowhere for the
answer to be implemented, which is itself part of what the question is asking.

### DLQ history lives in bounded logs (plan 03-02, Task 2)

After D-30's removals, an invalid envelope produces one log line, one `reject(requeue=False)`, and
**no counter movement of any kind**. `dlq_depth` is a **gauge** and the DLQ carries a 30-day TTL, so
it answers *"is there anything in the DLQ right now"* and can never answer *"how many have ever gone
there"* — after 30 days the message expires and the gauge returns to zero with no record it was ever
non-zero. The durable record is the log line, and ADR-0030 caps container logs at `max-size: 50m,
max-file: 5` per service.

**Do not invent a nineteenth metric to fix it.** Recorded so the phase that eventually owns the
deployment stack knows DLQ history has a bounded life.

---

### The ≥500 rec/sec figure is derived, not benchmarked (plan 03-06, Task 2)

`test_plan.load`'s *"writer drain >= 500/sec"* and *"stall the writer for 60 s and assert the backlog
clears rather than growing"* were unowned by any plan until the critique pass; they are now assertions
**inside** 03-06's one paced ten-minute run, at T+300 s, rather than a separate benchmark. The residue
to state plainly: the throughput number is **rows written divided by elapsed seconds across the
recovery interval on one developer host**, not an isolated calibrated measurement, and the run
executes once. A red result is a signal to investigate; the number itself is
`performance_requirements`' and never the test's to lower. Whoever eventually owns the deployment
stack should re-measure it on the real VM.

`test_plan.chaos`' fifth clause — *"run the deletion job concurrently with peak writes and assert the
writer's lag stays inside its target"* — is closed in the same run at T+450 s by executing **one**
retention sweep pass under load. **One pass is not sustained contention**, and the test says so: the
clause is closed as written and not more than it.

### The verifier owes ten minutes to SC5 (plan 03-06)

ORCHESTRATION §9.1 requires every success criterion to be proven by a test the **verifier ran itself**,
and `uv run pytest -q` **skips** `tests/load/test_fifty_rps_for_ten_minutes.py`. So verification of
this phase costs one `PROPE_RUN_LOAD=1 uv run pytest -m load -q` — roughly twelve minutes plus
container startup, launched in the background because it exceeds the shell tool's 600 s cap. Recorded
here so the cost is on the phase's timeline rather than a surprise at the gate.

## Part 4 — Out-of-scope discoveries found while planning

### `writer.py` becomes the first consumer of the Core `Table` declarations

`models.py:26-28` says its six `Table` objects are *"consumed with `select()`"* and **nothing consumes
them** — no `select()` exists anywhere in `src/`. D-33's `postgresql.insert(models.call_record)` is the
first use of the Core layer in this project. Two consequences that are not this phase's to fix but are
this phase's to record:

- `tests/architecture/test_no_sql_interpolation.py` inspects `text(...)` arguments only, so a Core
  construct passes the gate **by not being seen** rather than by being safe. That is not a hole — the
  construct binds its own parameters — but the gate's coverage of `src/` is now genuinely narrower
  than it reads. Whether it should learn to walk Core constructs is a question for whichever phase
  next adds one.
- `tests/architecture/test_schema_invariants.py` was insurance on an unused declaration and is now the
  guard on the statement that writes every call record in the system. Its importance changed without
  its code changing.

### The root `Dockerfile` and `docker-compose.yml` are still another project's boilerplate

Carried from Phase 2's `deferred-items.md`, re-confirmed while planning 03-04, and **still not fixed
here**. `python:3.11-slim` cannot run this code (`requires-python = ">=3.13,<3.14"`); `COPY
requirements.txt` names a file that does not exist; the compose file declares one `backend` service
healthchecked on `/health` where Prope has two processes from one image and `worker` deliberately
serves no HTTP.

Plan 03-04 describes several compose-shaped facts — a scrape target, a rules-file path, a metrics port
that deliberately does not exist on `worker` — and an executor will find these files. **Do not extend
them.** The deployment stack owns no milestone (PITFALLS §4).

### `ruff format --check` still fails repo-wide (Broken Window #1)

`ruff.toml` sets `line-length = 120`; the repository is hand-wrapped to roughly 100, so the formatter
wants to *join* short lines rather than break long ones. `uv run ruff check` — the gate — passes
clean, because `E501` is ignored. **No plan in this phase lists `ruff format --check` as a
verification command**, because the line is unsatisfiable without a repo-wide decision, and none of
these plans reformats files it does not own. New files are written in the house ~100 style so they
read like their neighbours rather than like the formatter's preference.

### `testcontainers[postgresql]` extra still does not exist

`uv sync` emits `warning: The package testcontainers==4.15.0 does not have an extra named postgresql`.
Pre-existing from Phase 1, harmless, and untouched here — plan 03-04 edits the dev group to add
`pyyaml==6.0.3` and deliberately does not correct the neighbouring line, so that plan's dependency
diff stays about the thing it is for.

### A long-lived RabbitMQ for broker tests is still a pending todo

`.planning/todos/pending/2026-08-10-reuse-a-long-lived-rabbitmq-for-broker-tests.md` records that a
broker boot costs 10–20 s, that the cost repeats across every subagent's pytest run, that
testcontainers 4.15.0 has no `with_reuse()`, and that `purge_queues` is teardown-only so a crash
leaks. **D-45.3's rejection of a second module-scoped broker rests on that todo**, and this phase adds
no container of any kind — every provocation is a closed channel or a closed port. The todo stays
pending.

### `enqueue.py` gains its first clock read, and the repository has a convention against them

`retention.py:14-17`, `writer.py:19-23`, `retention_settings.py:33-37`, `worker.py:268-270` and
`api.py:225-233` all state, in their own words, that the module reads no clock or reads exactly one in
exactly one place. D-41 makes `enqueue()` call-ledger's **third** sanctioned clock site, for
`write_lag_seconds`' sake, and plan 03-01 requires that the docstring say so explicitly rather than
quietly break the convention. Recorded here because the convention now has an exception list, and an
exception list nobody maintains is how a convention stops being one.

---

## Part 5 — Found during execution (plan 03-01)

Appended by the executor of plan 03-01. Everything here was discovered while running the code, not
while planning it, and none of it is fixed by this plan.

### The test rig's `NullPool` makes a single-record fallback write ~188 ms, and that is load-bearing

**Measured on the development host, twice, with `pytest --durations`.** 1,000 records through the
fallback over the `app_sessionmaker` fixture take **188 s**; the same 1,000 over a pooled engine built
from the same URL take **17 s**. `tests/conftest.py` builds every role-scoped engine with `NullPool`
for a reason that still holds — pytest-asyncio gives each test its own loop and an asyncpg connection
is bound to the loop that opened it — so the fixture is right and the arithmetic is simply different
from production's.

Two consequences, and the second is the sharp one:

- D-27's *"roughly 1.5 ms per single-record transaction"* is arithmetic about a **pooled** connection.
  It is not wrong; it is not what the fixture measures.
- **`HANDOFF_DRAIN_DEADLINE_SECONDS` is 3.0 s, and 20 unpooled fallback writes take about 3.6 s.** A
  shutdown-drain test written over the `NullPool` fixture is therefore a timing race against its own
  deadline — it will pass on a fast day and count a remainder on a slow one. Plan 03-01 answered this
  with `tests/broker/_helpers.py::pooled_sessionmaker`, a context manager that builds and disposes a
  pooled engine **inside one test, on one loop**, so nothing crosses loops and the conftest rule is
  not weakened.

**Plan 03-06's load work should read this before it starts.** Its CI-resident proxy times `enqueue()`
only and is unaffected, but its full-fat run asserts a ≥500 records/sec drain and a 60 s
stall-recovery — both of which are throughput claims, and both of which will measure the fixture's
connection cost rather than the writer's if they run over a `NullPool` sessionmaker.

### `enqueue()` cannot be handed a thousand records in one synchronous burst

`enqueue()` is synchronous by design (D-25), so a bare `for` loop over 1,000 calls **never yields to
the event loop** and the publisher never runs: record 513 takes the full-handoff branch and is counted
as dropped. SC1's test therefore paces its producer against `handoff().qsize()`, which is what a
gateway at 50 rps does anyway — one record per request, with the loop turning in between. Recorded
because it is not obvious from the plan text and because every later test that offers more than 512
records to `enqueue()` meets it.

### `asyncio.create_task(supervise(...))` has not started when `_start_publisher` returns

A test that starts the publisher and immediately sets `stopping` gets **no job at all**:
`run_with_restart`'s own `while not stopping.is_set()` sees the event already set and never calls the
job body. This is correct behaviour and it is a trap for any test asserting on the stop path — the
fix is one `await asyncio.sleep(0.2)` after `_start_publisher`, commented at the call. It also means
a real process that received SIGTERM inside its own startup would skip the drain, which is harmless
(there is nothing buffered yet) and worth knowing.

### `tests/integration/test_health_and_readiness.py` was not in plan 03-01's `files_modified`

Declared drift, closed by strengthening rather than weakening — see `03-01-SUMMARY.md`. The test
asserted `application.state.publisher is None` on the broker-unavailable path, which Task 1's adopted
`fallback-only-job` deliberately makes false, and its docstring carried the Phase 2 *"readiness green,
records lost"* paragraph that CL-01 closes. **The planner's `files_modified` lists for later plans
should be checked against `grep -rn "state.publisher" tests/`** before they run.

### `prope.call_ledger.enqueue.publish_or_fall_back` is one public name beyond the plan's artifact list

The plan named `drain_handoff_on_stop` as the shared helper and said the per-record catch should live
"once in `run_publisher`". With two job bodies there are two loops, and `app.py`'s fallback-only job
needs the same catch — so the catch is a second named helper in `enqueue.py` rather than a copy of
`metadata_dropped_total.inc()` inside the composition root. Recorded because a later plan reading the
artifact list will find a name that is not on it.

---

## Part 6 — Found during execution (plan 03-02)

Appended by the executor of plan 03-02. Everything here was discovered while writing or running the
code, and none of it is fixed by this plan.

### `written_total` now over-counts on a redelivery

`drain._write_group` increments `prope_call_ledger_written_total{source}` **once per draft in the
group**, unconditionally, after the transaction commits. After CL-02 a redelivered group commits a
transaction that inserts **no rows at all** — the upsert skips every one of them — so five redelivered
records move a counter documented as *"Call records committed to `ledger.call_record` by the drain, by
source"* by five while `ledger.call_record` gains nothing.

This is not a regression introduced by 03-02 so much as a meaning that shifted underneath an existing
line: before the upsert, a redelivered group **raised** and never reached the increment at all. It is
now reachable and wrong.

**Why it is not fixed here.** The honest fix needs `write_records` to report *which* `call_id`s
inserted rather than only how many did not — `WriteResult.duplicates` gives the count but not the set,
and a per-source breakdown needs the set. That is a signature change on the one write path, in a plan
whose `files_modified` covers the writer but whose remit is the aggregate, and `observability.py` (where
the counter's docstring would have to change with it) belongs to plan 03-01's diff and 03-03's.

**Who should decide it.** **Plan 03-04**, which ships the alert rules that read these counters and
already owns `observability.py`'s remaining edits. Three shapes are available and none is obviously
right: return the inserted set from `write_records` and count exactly; leave the counter as *"records
the drain handled"* and correct its docstring to say so; or subtract `WriteResult.duplicates` from the
group size and accept that the `source` breakdown is then approximate for a mixed group.

### `write_lag_seconds` now contains observations for records that were already durable

The same shape, one metric over. `_write_group` observes the histogram once per record after the
commit, including for a group in which every record was a duplicate. For a genuine redelivery the
observation is arguably honest — the envelope's `occurred_at` is the original hand-over, so the value
includes the time the message spent unacknowledged, which is real latency somebody may care about. For
a *re-published* envelope it is a fresh stamp and the value is short.

Recorded because **plan 03-06 asserts a write-lag p95 against this histogram** and should know that its
population is "records the drain committed a transaction for", not "records that became rows".

### `writer.py` now imports `prope.observability`, which is a new edge in the import graph

Before this plan the writer imported only `domain`, `pricing` and SQLAlchemy, and its docstring said it
emitted *"no log and no metric at all"*. D-35 and D-40 put four counters inside it, so anything that
imports the writer now transitively constructs the metric objects at import time. That is already true
of every process entry point and of the test suite, so nothing changes in practice — but there is **no
architecture test asserting anything about which modules may import `observability`**, and the module
boundary rules in `.claude/CLAUDE.md` are about modules rather than about this. Recorded so it is a
noticed edge rather than an unnoticed one.

### The `text()` count under `src/prope` fell from 18 to 16

Measured with the same AST walk `tests/architecture/test_no_sql_interpolation.py` runs, before and
after. `INSERT_CALL_RECORD` and `INSERT_CALL_BODY` left `text()` for the Core layer. The guard test's
floor is `found >= 5` and **was not raised, lowered or otherwise touched**; `ALLOWED` is still
`frozenset()`. Recorded only so that a later phase seeing the number move knows which two statements
left and why — and so that the standing instruction survives: if that floor ever goes red, the repair
is to confirm the remaining statements are genuinely fewer and adjust the floor **with a comment naming
which ones left**, never by adding an entry to `ALLOWED`.

### `src/prope/call_ledger/envelope.py` was not in plan 03-02's `files_modified`

Declared drift, closed by rewriting a sentence rather than deleting it — see `03-02-SUMMARY.md`.
`occurred_at`'s field comment said *"Nothing in the write path reads this field"*, and Task 2's
`write_lag_seconds` observation in `_write_group` makes the drain read it. The planner's
`files_modified` lists for later plans should be checked against
`grep -rn "occurred_at" src/ tests/` before they run, for the same reason 03-01 recorded the
`state.publisher` grep.

---

## Part 7 — Found during execution (plan 03-03)

Two of these are corrections to the plan's own acceptance criteria rather than discoveries about the
code. They are recorded here anyway, because a verifier will run those greps.

### `src/prope/call_ledger/api.py` was not in plan 03-03's `files_modified`

Declared drift, closed by rewriting one sentence. `set_spend_ceiling`'s docstring named
`prope_call_ledger_ceiling_failed_open_total` as the live control behind its *"a limit with no
currency is refused"* argument — the sharpest paragraph in that route — and the plan's own acceptance
criterion requires `grep -r "ceiling_failed_open_total" src/` to find nothing. It now names
`prope_call_ledger_ceiling_check_total{result="failed_open"}`. **No code changed in that file.**

The general rule this is the third instance of (after `test_health_and_readiness.py` in 03-01 and
`envelope.py` in 03-02): **a plan that retires or renames a symbol should grep for the symbol's name
in prose as well as in code before writing `files_modified`.** For this phase the standing greps are
`grep -rn "occurred_at" src/ tests/`, `grep -rn "state.publisher" src/ tests/` and now
`grep -rn "<metric_name>" src/ tests/` for any metric a later plan renames or retires.

### Two acceptance criteria in `03-03-PLAN.md` contradict the plan's own instructions

Both are grep-shaped proxies for a real property, and both are unsatisfiable as literally written
because a different part of the same plan requires the string they forbid. Neither was weakened;
each was narrowed to what it was protecting, and the reading is recorded in `03-03-SUMMARY.md`.

1. **`grep -r "ceiling_failed_open_total" src/` returns nothing** vs. the `<action>`'s requirement to
   record the retirement at the code — which the plan's own `<verification>` block anticipates by
   allowing *"a comment recording the retirement"*. Resolved to **exactly one comment block**, in
   `observability.py` where the constant used to be defined; every other mention in `src/` says
   *"Phase 2's separate fail-open counter"* instead. The `Counter` object is gone from the registry,
   which is the property.
2. **`grep -r "ArithmeticError" src/` produces no output** vs. the `<verification>` block's
   requirement that `RetentionSet`'s new paragraph name `OverflowError`, `ArithmeticError` and
   `classify_write_failure` **by name**. The criterion's own text says what it is really asserting —
   *"`drain.py` gains no `ArithmeticError` branch"* — so the narrow form is the one to run:
   `grep -rn "ArithmeticError" src/prope/call_ledger/drain.py` returns nothing, and
   `git diff src/prope/call_ledger/drain.py` is empty.

**For later phases:** a grep criterion over a whole tree is a bad proxy for a property when the same
plan requires the symbol to be *documented*. Scope the grep to the file whose behaviour is at stake.

### `check_spend_ceiling` had four evaluated branches and three tests

The missing one — a ceiling row exists and no priced traffic has landed this month, which is the
`LEFT JOIN`'s own branch — now has `test_an_enabled_ceiling_with_no_priced_spend_this_month_is_allowed`.
Recorded because it is the shape of a gap worth looking for elsewhere: **a metric or a guard added to
every branch of a function whose test file covers only some of them passes the file and closes
nothing.** The counterpart assertion that makes it visible is summing every label value's delta across
one call and requiring the sum to be exactly one, which is now this repository's precedent for a
closed-vocabulary counter.

### `schemas.py` maintains an explicit `__all__` and it is easy to miss

`MAX_RETENTION_DAYS` was added to it. A public constant added to that file and left out of the list is
a list that has stopped being maintained — and `tests/integration/test_management_routes.py` imports
constants from there by name. No other module in `src/prope` declares `__all__`, which is why it is
easy to walk past.

### `RetentionSet` now changes the assembled OpenAPI schema

`Field(le=MAX_RETENTION_DAYS)` renders as a `maximum` on the request body schema for
`PUT /api/v1/workspaces/{id}/retention`. `tests/architecture/test_route_table.py`'s OpenAPI walk
passes unchanged (it looks for forbidden field names, not for constraints), but plan 03-04 and Phase
23 both extend that file and should know the constraint is now in the document.

---

## Part 8 — Found during execution (plan 03-04)

### The lock file declares SEVEN alerts, not six, and the plan's Task 4 table dropped one

**This is the finding of the plan and it is a counting error in the plan, not in the spec.**
`docs/modules/call-ledger.lock.yml`'s `observability_requirements.alerts` block lists
`LedgerMetadataDropped`, `LedgerPublishFailing`, `LedgerWriteLagHigh`, `LedgerBodyDropRateHigh`,
`LedgerPriceMissing`, `LedgerRetentionOverdue` **and `LedgerDuplicateCallIds`** — seven. Plan 03-04's
Task 4 table has seven rows, six of them declared plus `LedgerDlqNonEmpty`, and **omits
`LedgerDuplicateCallIds` entirely** — while the same plan's `<objective>` names that alert as one of
the three declared alerts that read unreadable metrics. So the plan contradicts itself and the lock
file settles it.

`deploy/prometheus/rules/call_ledger.rules.yml` therefore ships **eight** rules: the lock file's seven
plus T-005's `LedgerDlqNonEmpty`. `DECLARED_ALERTS` in `tests/architecture/test_alert_rules.py` is a
literal frozenset of eight and the reason is written at the constant. Shipping seven would have left a
declared alert with no rule, in the last phase of the milestone that owns it — nobody inherits it after
that.

**For later phases:** *"the six alerts"* appears in `03-CONTEXT.md` (D-44), in `03-04-PLAN.md`'s
objective and success criteria, and in `COVERAGE.md`. The number is wrong in all of them. No upstream
spec file was edited; the count is corrected in the code and recorded here.

### `test_route_table.py` now imports `tests.integration._asgi`

Asserting that `GET /metrics` answers `200` with an exposition body needs a request through the ASGI
stack, and `_asgi.call` is the project's answer to that (`httpx` is deliberately not a dependency).
Cross-package test imports already have precedent — `tests/integration/test_worker_jobs.py` imports
`tests.broker._helpers` — but this is the first one **into** `tests/architecture/`, which was until now
a package of pure source-and-schema walks. Phase 23 extends this file; it should know that the module is
no longer import-free.

### The mount refusal is an AST walk, not a substring grep

`03-04-PLAN.md`'s acceptance criterion is `grep -c "application.mount(" src/prope/app.py` returning 0,
and it does. But a grep is the wrong assertion for this property and this repository already knows why:
`test_worker_imports_no_web_framework`'s docstring says *"An AST walk, not a string search — the
docstring names `/healthz` on purpose"*. `prope.app` now names the refused shape twice, in prose, at
exactly the places a reader meets the decision. The first version of the test grepped for
`application.mount(` and failed on the module docstring.

So `test_metrics_is_a_route_the_table_can_see_and_not_a_mount` walks the parsed source for any
`ast.Call` whose func is an attribute named `mount`, **and** walks `app.routes` for a
`starlette.routing.Mount` instance. Both are strictly stronger than the grep, and the second catches a
mount that arrived through a spelling the parser never sees. The prose was changed to say
`app.mount(...)` rather than `application.mount(...)` so the plan's literal criterion also holds.

### The alert test reads metric FAMILIES, not samples, and that changes what it can claim

`03-04-PLAN.md` says to *"collect the registry's sample names from `REGISTRY.collect()`"*. That does not
work here, and the reason is worth carrying: **a labelled counter with no child renders zero samples.**
`unpriced_total`, `body_dropped_total`, `ceiling_check_total`, `enqueued_total`, `written_total` and
`publish_failed_total` are all labelled, so a sample-derived name set holds whatever earlier tests in the
shared process happened to increment — the test would pass in a full run and fail alone, or the reverse.

`_registered_names()` therefore expands each collected **family** by `prometheus_client`'s own rendering
rule (counter → `_total` + `_created`; histogram → base + `_bucket`/`_sum`/`_count`/`_created`; gauge →
itself). The family exists from import, which is exactly the property D-40 was taken for. The expansion
is asserted against a known counter, gauge and histogram plus one deliberately unreal name, so the
normalisation cannot be the thing that silently swallows the test.

### `read_queue_depths` carries a `gauges` seam, and `run_worker` a `depth_interval_seconds`

Both follow the observation-seam discipline `delete_expired_bodies`' `on_chunk` and
`run_with_restart`'s `on_backoff` already set: keyword-only, defaulted, and the production composition
passes neither. `gauges` exists so the channel-level-error branch can be provoked against a queue name
that is not one of ours — a test cannot delete `prope.call_record` to make the point, because the
declaration is one-way (D-23) and the whole session shares one broker. `depth_interval_seconds` exists
so `run_worker`'s standing sentence — *"every parameter after `stopping` exists so this composition is
drivable from a test"* — stays true now that there are two schedules rather than one. Neither was named
in the plan.

### `oldest_body_age_seconds` is clamped at zero

`created_at` is the caller's own instant and is not bounded to the past, so a future-stamped body could
in principle drive the reduction negative. A negative age is not a state this gauge can report
meaningfully and `0.0` — "nothing is overdue" — is the truthful reading of it, so the set is
`max(0.0, oldest)`. Same posture as `write_lag_seconds`' `max(0.0, lag)` and named at the function. It
is a one-line behaviour the plan did not specify.

### The rules file's own header contains a dead metric name on purpose

`deploy/prometheus/rules/call_ledger.rules.yml`'s header comment uses `prope_call_ledger_spill_bytes` —
one of the three metrics ADR-0041 deleted — as its worked example of the rot the test exists to catch.
`test_every_metric_named_by_a_rule_exists_in_the_registry` extracts names from `expr` values only, so it
is unaffected. **A future "grep the repository for retired metric names" check would hit it**, and the
right response is to scope that check to `expr:` values rather than to delete the example.

### Two artifacts were written outside `files_modified`, both instructed

`.planning/phases/03-durability-idempotency-and-no-read-path/deferred-items.md` (this file) and
`03-04-SUMMARY.md`. Both are the standing per-plan artifacts the orchestration contract requires; neither
is code. Recorded because the rule is that every file touched outside the declaration is named.
