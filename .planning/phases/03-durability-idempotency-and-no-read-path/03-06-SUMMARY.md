---
phase: 03-durability-idempotency-and-no-read-path
plan: 06
subsystem: backend
tags: [load, performance, cl-12, ac-12, prometheus, histogram, chaos, retention, pytest-markers]

# Dependency graph
requires:
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 01
    provides: "enqueue() in its final form — HANDOFF_MAXSIZE, MAX_BODY_BYTES, the D-41 occurred_at stamp, reset_handoff() as the documented seam, and ENQUEUE_DURATION_BUCKETS with 0.001 as an edge specifically so this plan can assert on it; fallback.build_fallback_writer; run_publisher's required fallback argument"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 02
    provides: "write_records' idempotent upsert, and WRITE_LAG_BUCKETS with 2.0 as an edge — AC-12's third clause is computable because of it"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 04
    provides: "worker.sweep_expired_bodies / observe_oldest_body_age / build_retention_resolver / ObservedWorkspaces — the composition test_plan.chaos clause 5 drives under load"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 01
    provides: "tests/broker/_helpers.py — pooled_sessionmaker and fallback_writer, and the drain_until shape the run's two-drain controller is modelled on"
provides:
  - "tests/load/ — a new test package with the two halves of CL-12's claim and the registry-reading helpers both need"
  - "tests/load/test_enqueue_off_response_path.py — CL-12's CI-resident proxy: the p95 and the zero-drop claim at the lock file's stated 80% depth, plus the two assertions that defend the proxy's claim to stand in for SC5"
  - "tests/load/test_fifty_rps_for_ten_minutes.py — ROADMAP SC5's literal condition, marked `load`, skipped unless PROPE_RUN_LOAD is set, executed twice during this plan"
  - "The `load` pytest marker, registered in pyproject.toml with NO addopts key"
  - "`make load` — the documented invocation, and `make check` deliberately does not depend on it"
  - "A measured, localised finding: the drain does not reach performance_requirements' 500 records/sec on this host, and 70% of a priced window is one resolve_price round trip per record"
affects: [03-VERIFICATION, 16-18-evaluation, 19-21-gateway]

actuals:
  tokens: 74000
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns:
    - "A timed span containing exactly one statement, with the fixture work, the draft construction and the buffer bookkeeping all outside the clock reads"
    - "A published histogram cross-checked against an independent measurement of the same calls — one observation per call asserted, not just the distribution"
    - "A quantile assertion over a window of a cumulative histogram, computed from bucket snapshots taken at named moments"
    - "A percentile clause and a deliberately injected outage held in DIFFERENT windows of the same run, with the window boundaries part of the assertion"
    - "A performance assertion written last so a machine-dependent number cannot mask a correctness one"
    - "A marked long test that is SKIPPED rather than deselected, so it stays visible in the default summary"

key-files:
  created:
    - tests/load/__init__.py
    - tests/load/test_enqueue_off_response_path.py
    - tests/load/test_fifty_rps_for_ten_minutes.py
  modified:
    - pyproject.toml
    - Makefile
    - .planning/phases/03-durability-idempotency-and-no-read-path/deferred-items.md

key-decisions:
  - "The write-lag clause is asserted over the two windows in which AC-12's own condition (50 rps sustained) holds, not over the union with the deliberate 60 s consumer outage. Sixty seconds at fifty a second is 3,000 records — 10% of the run — every one written 5 to 65 s after it was enqueued, so a p95 over the union is above target BY ARITHMETIC and fails for a reason that has nothing to do with the writer. The whole-run share is computed and printed beside it. The clause is asserted, not dropped"
  - "The >= 500 records/sec assertion was NOT lowered and NOT removed. It is measured at 189 records/sec end to end (212 on the first execution) on this host and it is what goes red. src/prope/call_ledger/writer.py was not touched: it is outside files_modified, it is the system's central write path, and a plan whose purpose is honest measurement must not change the thing it measures to make its own number come out"
  - "The performance assertion is written LAST in the test, after every correctness assertion. In the first execution it failed early and masked four families that the printed report showed passing; ordering is the whole of the fix and nothing was relaxed by it. The reordered run then executed and PASSED all nine correctness assertions, so the plan's evidence rests on assertions rather than on prints"
  - "test_plan.chaos clause 5's sweep is given 5,000 genuinely expired bodies in a second workspace to delete, written through write_records with a one-second retention_window against the fixture calendar. A sweep with nothing to remove is an index scan, not a deletion job. This is beyond what the plan asked for and is recorded as a strengthening"
  - "The proxy runs by default with no marker and no skip — SC5 proven by a test that never executes is SC5 not proven — and its module docstring records that it is NOT container-free, because truncate_ledger is autouse and unconditional. tests/conftest.py was not touched"
  - "No addopts key. The comment in pyproject.toml names `addopts` twice on purpose, against an acceptance criterion that greps for the token: a note that may not name the thing it forbids is not a note, and the honest check is the parsed table"
  - "Every timed loop drains one record per timed call, outside the span. 409 pre-filled plus 500 timed with nothing draining is 909 records into a 512-slot queue, which makes the zero-drop half of CL-12 arithmetically unreachable while the p95 half still passes"

patterns-established:
  - "Locate a threshold as a bucket EDGE in the declared tuple rather than writing it twice — the `le` label string is then rendered from the same float the histogram was built with, and a bucket set that lost the edge fails loudly instead of silently answering to the next bucket's width"
  - "Print the run's numbers before the assertions, so a green run reports what it was proven WITH and a red one still carries every figure"
  - "Derive a load test's row count from its rate and duration, so a run at different numbers cannot assert a count belonging to another one"
  - "An absolute, self-correcting arrival schedule (`target = t0 + n/rate`) rather than sleep-per-iteration, so an overshooting sleep is absorbed rather than accumulated"

requirements-completed: [CL-12]

coverage:
  - id: D1
    description: "With the handoff pre-filled to 80% of its bound and no publisher running, the p95 of 500 timed enqueue() calls is under 1 ms measured around the bare call, and metadata_dropped_total does not move"
    requirement: CL-12
    verification:
      - kind: load
        ref: "tests/load/test_enqueue_off_response_path.py::test_enqueue_p95_stays_under_a_millisecond_at_eighty_percent_depth"
        status: pass
    human_judgment: false
  - id: D2
    description: "A record whose body sits exactly at MAX_BODY_BYTES fits the same budget, as its own named assertion so a failure says which cost moved"
    requirement: CL-12
    verification:
      - kind: load
        ref: "tests/load/test_enqueue_off_response_path.py::test_a_body_at_the_cap_still_fits_the_budget"
        status: pass
    human_judgment: false
  - id: D3
    description: "The histogram enqueue() publishes saw exactly one observation per call and at least 95% of them at or below the 0.001 edge, cross-checked against an independent perf_counter_ns measurement of the same calls"
    verification:
      - kind: load
        ref: "tests/load/test_enqueue_off_response_path.py::test_the_published_histogram_agrees_with_an_independent_measurement"
        status: pass
    human_judgment: false
  - id: D4
    description: "The p95 at an empty handoff and at 80% depth are both inside the budget and within a stated factor of each other, with qsize asserted at the end of both loops — the proxy's claim to stand in for the ten-minute run, as an assertion"
    verification:
      - kind: load
        ref: "tests/load/test_enqueue_off_response_path.py::test_buffer_depth_does_not_change_the_callers_span"
        status: pass
    human_judgment: false
  - id: D5
    description: "ROADMAP SC5 at its literal condition — 30,000 records paced at 50 rps for 600 s, enqueue p95 under 1 ms sampled throughout, metadata_dropped_total unmoved, and 30,000 rows in ledger.call_record read through migrate_engine"
    requirement: CL-12
    verification:
      - kind: load
        ref: "tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes"
        status: pass
    human_judgment: false
  - id: D6
    description: "AC-12 clause 2 — at least 95% of write_lag_seconds observations at or below the 2.0 bucket edge, over the windows in which AC-12's stated condition holds, with 2.0 located in WRITE_LAG_BUCKETS rather than written as a literal"
    requirement: CL-12
    verification:
      - kind: load
        ref: "tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes"
        status: pass
    human_judgment: false
  - id: D7
    description: "test_plan.load's stall clause — the drain is stopped for a full 60 s at T+300 s while the producer keeps pace, and the backlog CLEARS rather than growing, asserted on rows in ledger.call_record and never on queue_depth"
    verification:
      - kind: load
        ref: "tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes"
        status: pass
    human_judgment: false
  - id: D8
    description: "test_plan.load's throughput clause — the recovery clears at >= 500 records/sec, derived as rows written / elapsed across the recovery interval"
    verification:
      - kind: load
        ref: "tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes"
        status: fail
    human_judgment: false
    rationale: "Measured at 189 records/sec end to end on run 2 and 212 on run 1, and 494 records/sec for write_records in isolation, against a stated 500. Localised: 0.710 s of a priced 500-record window's 1.012 s is one resolve_price round trip per record. Two independent full-length executions 2.5x under the figure is not a flake. NOT lowered and NOT removed; the writer was not touched. This is the plan's blocker — see the body and deferred-items Part 10."
  - id: D9
    description: "test_plan.chaos clause 5 — one retention sweep executes under load at T+450 s and removes 5,000 genuinely expired bodies, read back through migrate_engine, with the write-lag clause still holding across the window that contains it"
    verification:
      - kind: load
        ref: "tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes"
        status: pass
    human_judgment: false
  - id: D10
    description: "uv run pytest -q means what it meant before this plan — no addopts key, the marked test skipped rather than deselected, and no PytestUnknownMarkWarning"
    verification:
      - kind: command
        ref: "uv run pytest -q -rs; uv run python -c \"import tomllib; 'addopts' in ...['ini_options']\" -> False"
        status: pass
    human_judgment: false
  - id: D11
    description: "The posture on a flaky timing assertion (one re-run, then investigate, never a new threshold) and the trade that `make check` does not depend on `make load`"
    verification: []
    human_judgment: true
    rationale: "The plan's two <human-check> items. Both are judgements about posture rather than properties a test can assert; the mechanical halves — the threshold is the lock file's, `check` does not depend on `load`, the proxy's depth argument is an assertion — are all built."

# Metrics
duration: 118min
completed: 2026-08-11
status: blocked
---

# Phase 03 Plan 06: Durability, idempotency, and no-read-path Summary

**CL-12 is proven at ROADMAP SC5's literal condition, and the milestone-closing audit found one
`performance_requirements` figure the system does not meet.** Thirty thousand records paced at fifty a
second for six hundred seconds produced an enqueue p95 of **0.4814 ms** against a 1 ms budget, moved
`prope_call_ledger_metadata_dropped_total` by **zero**, and left **30,000 of 30,000** rows in
`ledger.call_record` read through the owner role. AC-12's third clause — write lag p95 under 2 s — holds
at **97.8%** of steady-state observations at or below the 2.0 s bucket edge. `test_plan.chaos` clause 5's
deletion job removed **5,000 expired bodies under load**. And `performance_requirements`' *"writer drain
>= 500 records/sec sustained"* measured **189 records/sec end to end** — 212 on the first execution —
which is the plan's blocker: it was not lowered, it was not removed, and `writer.py` was not touched to
make it pass.

The figures above are run 2's, because run 2 is the execution in which every one of them was **asserted**
and not merely printed; run 1 agreed on all of them within noise but stopped at the throughput assertion
before four assertion families could run. Both executions are recorded below.

## Performance

- **Duration:** ~118 min, of which ~21 are the two full-length load executions
- **Tasks:** 3
- **Files created:** 3 · **modified:** 3 (two config, one planning artifact)
- **Default suite:** unchanged in meaning — `uv run pytest -q` selects what it always did, plus four new
  tests that run and one that skips visibly

## What shipped

**`tests/load/`** — a new test package whose `__init__.py` states what separates its two files and
carries the three registry-reading helpers both need: `counter_value` (a third copy, with the reason),
`bucket_edge`, and `histogram_totals`.

**`tests/load/test_enqueue_off_response_path.py`** — four tests, no marker, no skip.

1. The p95 of 500 timed `enqueue()` calls at the lock file's stated 80% handoff depth, with
   `metadata_dropped_total` asserted unmoved as a before/after delta.
2. The same measurement with every body at exactly `MAX_BODY_BYTES`, as a **separate named test**, so a
   regression says whether the buffer got slower or the encode did.
3. The histogram `enqueue()` publishes, cross-checked against the independent `perf_counter_ns`
   measurement of the same calls — **one observation per call** asserted, and at least 95% at or below
   the `0.001` edge located in `ENQUEUE_DURATION_BUCKETS`.
4. The p95 at an empty handoff against the p95 at 80% depth, which is the proxy's own argument turned
   into an assertion.

**`tests/load/test_fifty_rps_for_ten_minutes.py`** — SC5's literal condition, marked `load` and skipped
unless `PROPE_RUN_LOAD` is set, driving a real publisher, a real fallback, a real broker and a real
drain, with a 60 s writer stall at T+300 s and a retention sweep at T+450 s.

**`pyproject.toml`** — the `load` marker registered, with a comment stating what it means, the exact
invocation, and why **no `addopts` key is added**. **`Makefile`** — a `load` target, added to `.PHONY`,
with `check` deliberately not depending on it.

## The observed numbers, from the two executions

Both were launched with `run_in_background: true`: a >600 s run does not fit a foreground tool call, and
a timed-out call is indistinguishable from a failing test.

### Run 1 — `PROPE_RUN_LOAD=1 uv run pytest -m load -q -s`, 625.44 s

```
  wall time            600.8 s for 30000 records
  enqueue span over 30000 calls: p50 0.1599 ms, p95 0.4555 ms, p99 0.6222 ms (CL-12's budget is 1.000 ms)
  rows (WORKSPACE_A)   30000 of 30000
  stall                60.0 s, backlog target 18018, reached 18512
  recovery             3500 rows in 16.53 s = 212 records/sec
  write lag <= 2.0 s  steady windows 26171/26484, whole run 26187/30000
  retention sweep      5000 bodies deleted under load
```

```
FAILED tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes
1 failed, 406 deselected, 1 warning in 625.44s (0:10:25)
```

Reading it: the pacing held to within a second of the ideal 599.98 s over ten minutes; the caller's span
never approached its budget; nothing was dropped and nothing was lost; the stall was a full sixty
seconds and the backlog **cleared**; the steady-state write-lag share is 98.8% and the whole-run share
is 87.3%, which is the arithmetic the window split exists for. The one red number is the recovery rate.

**But run 1 proved less than it printed.** The throughput assertion sat fourth in the file, so it fired
before the write-lag assertions and before the chaos clause, and **four assertion families never
executed**. The numbers above were *printed* by all of them; only three were *asserted*. That is exactly
the failure mode ORCHESTRATION §9a's audit is supposed to catch, and it was found here by reading the
traceback rather than the print. The assertion was moved to the end of the test — nothing else changed,
nothing was relaxed — and the run was executed again.

### Run 2 — the same command, after the reordering, 622.64 s

```
  wall time            600.7 s for 30000 records
  enqueue span over 30000 calls: p50 0.1685 ms, p95 0.4814 ms, p99 0.6597 ms (CL-12's budget is 1.000 ms)
  rows (WORKSPACE_A)   30000 of 30000
  stall                60.0 s, backlog target 18014, reached 18367
  recovery             3359 rows in 17.79 s = 189 records/sec
  write lag <= 2.0 s  steady windows 26038/26625, whole run 26054/30000
  retention sweep      5000 bodies deleted under load
```

```
FAILED tests/load/test_fifty_rps_for_ten_minutes.py::test_fifty_records_a_second_for_ten_minutes
1 failed, 406 deselected, 1 warning in 622.64s (0:10:22)
```

**This is the run that carries the plan's evidence**, because every assertion above the throughput one
executed and passed:

| Clause | Assertion | Run 2 |
|---|---|---|
| CL-12, caller's span | 30,000 samples, p95 < 1 ms | 0.4814 ms — **passed** |
| CL-12, no metadata dropped | drop counter delta == 0 | **passed** |
| SC5, durable side | 30,000 rows through `migrate_engine` | 30000 of 30000 — **passed** |
| `test_plan.load`, the stall | drain stopped >= 60 s | 60.0 s — **passed** |
| `test_plan.load`, backlog clears | reached >= target | 18367 >= 18014 — **passed** |
| AC-12, window coverage | asserted windows >= 75% of the run | 26,625 of 30,000 (88.8%) — **passed** |
| AC-12, write lag | >= 95% at or below the 2.0 s edge | 26038/26625 = **97.8%** — **passed** |
| `test_plan.chaos` clause 5 | 5,000 expired bodies swept under load | 5000 — **passed** |
| chaos clause 5, read back | zero surviving bodies through the owner role | 0 — **passed** |
| `performance_requirements` | drain >= 500 records/sec | 189 — **FAILED** |

**The two runs agree on every clause and disagree only on the machine-dependent one**: enqueue p95 0.4555
vs 0.4814 ms, write-lag share 98.8% vs 97.8%, throughput 212 vs 189 records/sec. Two independent
measurements roughly 2.5x under the required figure is not a flake, and reporting the pair rather than
the better one is the point.

### The CI-resident proxy, on the same host

```
uv run pytest tests/load/test_enqueue_off_response_path.py -q
4 passed, 1 warning in 7.40s
```

**Seven seconds against six hundred and twenty-two**, which is the whole point of it: this is what runs
on every push, and it re-runs green in the same time after every edit (6.27 s at the final gate below).

Its own measurements, from the throwaway harness used to size the constants: **p95 0.055 ms** at 80%
depth, **0.037 ms** at an empty handoff (a ratio of ~1.5, against the 8x sanity bound the test asserts),
and **0.123 ms** with a body at the 256 KiB cap. The proxy and the ten-minute run therefore disagree by
a factor of about eight on the same call — the proxy's loop is tight and cache-hot, the paced run's is
not — and **both are far inside the budget**, which is the useful thing to know about the margin.

## Why the proxy stands in for the ten-minute run, and which assertion now defends that

The plan's `<output>` asks for this in as many words.

**The argument.** `enqueue()` is deliberately synchronous, so the caller's span is exactly the function
call: one byte-size computation, one clock read, one `put_nowait`, two counter increments and one
histogram observation. Nothing in it scales with elapsed time. What ten minutes of arrival adds is
**buffer depth**, and the proxy buys that directly by pre-filling to the lock file's stated 80% — and the
only term in the span that depth touches is `put_nowait`'s bookkeeping on a bounded `asyncio.Queue`.

**The assertion that defends it** is `test_buffer_depth_does_not_change_the_callers_span`: it times
`SAMPLES` calls at an empty handoff and `SAMPLES` at 80% depth in one test, asserts both p95s inside the
budget, and asserts the depth p95 is within `DEPTH_COST_FACTOR` (8x) of the empty one. **If that test
starts failing while the absolute p95 still passes, it is the proxy's claim to represent SC5 that
broke** — and the test says so, by name, pointing at `make load`.

**The second defence** is `test_the_published_histogram_agrees_with_an_independent_measurement`, which
asserts the production histogram saw exactly one observation per `enqueue()` call. A histogram wired to
the wrong span is otherwise invisible forever, because a dashboard cannot tell you what it is measuring.

**What the proxy still cannot show**, named in its own module docstring: drift over ten minutes, the
fallback under sustained pressure, the drain keeping up, and the enqueue-to-durable lag. Those are the
marked run's, and the marked run has now been executed.

## `uv run pytest -q` selects exactly what it always did

Stated explicitly because the plan's `<output>` requires it.

**No `addopts` key was added.** The marked test opts itself out with an ordinary
`skipif(not os.environ.get("PROPE_RUN_LOAD"))`, so it is **skipped** — visible as an `s` in the summary
and, under `-rs`, as its reason and its invocation — rather than **deselected**, which is invisible.
`addopts = "-m 'not load'"` would have changed the default selection for the whole suite for every phase
from 4 to 24, and ORCHESTRATION §9's gate is literally `uv run pytest -q`. That is not a change this
phase should make on twenty-one later phases' behalf, and the `pyproject.toml` comment says so where the
next person would make it.

The key's absence is verified by parsing the table rather than by grepping the file:

```
uv run python -c "import tomllib; print('addopts' in tomllib.load(open('pyproject.toml','rb'))['tool']['pytest']['ini_options'])"
False
```

## The gate, observed

```
uv run pytest tests/load/test_enqueue_off_response_path.py -q
4 passed, 1 warning in 6.27s
```

```
uv run pytest -q
406 passed, 1 skipped, 1 warning in 201.45s (0:03:21)
```

```
uv run ruff check src/ tests/ alembic/
All checks passed!
```

**The one `s` is the marked run**, exactly as designed: the default suite gained four tests that execute
and one that announces itself as skipped. Before this plan the suite was 402 passed; it is now 406 passed
and 1 skipped, and no existing test changed. `uv run ruff format --check` is not run: it fails repo-wide
on the pre-existing 120-vs-100 column disagreement recorded as Broken Window #1, it is not a gate, and it
is not this plan's to fix.

## The blocker: `performance_requirements`' 500 records/sec is not met

**What the lock file requires.** `performance_requirements` states *"writer drain throughput >= 500
records/sec sustained"*, condition *"batched inserts, bodies included, single writer"*, with the reason
written into the spec: *"a writer that merely keeps up has no capacity to clear a backlog after a stall,
so every stall becomes permanent pressure."* `test_plan.load` restates it beside the stall clause.
**Neither is CL-12 and neither is AC-12** — this clause is one of the three that ORCHESTRATION §9a's
milestone audit told this plan to pick up because M1 closes here and no later phase owns call-ledger's
writer.

**What was measured.** **189 records/sec** end to end across the recovery from the 60 s stall (3,359 rows
in 17.79 s) on run 2, and **212 records/sec** (3,500 rows in 16.53 s) on run 1 — and, measured in
isolation against the same containers through the same pooled sessionmaker, **494 records/sec** for
`write_records` itself. Three measurements, none of them at 500.

**Where the time goes**, localised before the finding was written rather than after:

| Measurement | Result |
|---|---|
| 500 sequential `resolve_price` round trips | **0.710 s** (1.42 ms each) |
| `write_records(500 priced, bodies attached)` | **1.012 s** → 494 records/sec |
| `write_records(500 unknown-usage, no price lookup)` | **0.157 s** → 3,185 records/sec |
| an empty `workspace_transaction` | 4.33 ms |

**Seventy percent of a priced window's cost is one `resolve_price` SELECT per record**, issued from
`write_records`' pass-1 loop for every draft whose `usage_status` is `reported` — and issued whether or
not a price row exists, so an unpriced workspace pays the same. It is an N+1 read inside the one write
path in the system.

**What was not done, and why each was refused.**

- **The number was not lowered.** It is `performance_requirements`' and not this test's, and the plan
  says so at the assertion.
- **`writer.py` was not touched.** It is outside this plan's `files_modified`, it is the system's central
  write path, and a plan whose entire purpose is honest measurement must not change the thing it is
  measuring to make its own number come out.
- **The assertion was not removed or marked.** It is still `>= 500`, exactly as Task 2 specifies, and it
  is what goes red.

**The honest caveats, which do not make the number go away.** This run drives the publisher **and** the
drain in one process on one event loop — which is what makes AC-12's write-lag clause readable at all,
since `OQ-026`'s two-registry split does not bite inside a test — while the deployment shape is two
processes on one host. So the end-to-end 189 and 212 understate what the drain can do with a loop to
itself; the isolated 494 does not, and it is still under 500. A Linux VM with `app`, `worker` and
`postgres` on one docker network has round trips roughly an order of magnitude cheaper than Docker
Desktop on Windows, which would move the isolated figure a long way — **but that is an inference and this
summary does not record it as a measurement.** What this repository has measured is 494, 212 and 189,
against a stated 500.

**What would fix it**, so the next person does not re-derive it: one query per distinct
`(provider_config_id, upstream_model)` in a batch, returning the effective-dated rows, resolved per
record in Python against each record's own `created_at`. That preserves ADR-0019 exactly and turns N
round trips into one. The obvious cheaper move — memoising on the exact `created_at` instant — would look
excellent in this test (all 30,000 drafts share `day(5)`) and buy nothing in production.

## Deviations from Plan

### 1. AC-12's write-lag clause is asserted over two windows, not over the whole run

**Plan text:** *"read `prope_call_ledger_write_lag_seconds`' bucket counts from the registry and assert
that at least 95% of observations fall at or below the `2.0` edge"*, together with *"at T+300 s, stop the
drain and leave it stopped for 60 s while the producer keeps its 50 rps pace"*.

**The two are arithmetically incompatible.** Sixty seconds at fifty a second is 3,000 records — **ten
percent of a thirty-thousand-record run** — and every one is written five to sixty-five seconds after it
was enqueued, by construction. Both runs measured exactly that: **26,187 of 30,000 (87.3%)** and
**26,054 of 30,000 (86.8%)** over the whole run. AC-12's own condition is *"50 rps sustained for 10
minutes"*; a deliberately removed consumer is not that condition, it is `test_plan.load`'s and
`test_plan.chaos`'s.

**Resolved by** snapshotting the histogram at four moments and asserting the clause over the two windows
in which AC-12's condition holds — start-to-stall and end-of-recovery-to-end — which is **26,625 of
30,000 observations (88.8%) and includes the retention sweep**, and by measuring the outage window
against the clause that governs it. Measured there on run 2: **26,038/26,625 = 97.8%** (run 1:
26,171/26,484 = 98.8%). The whole-run share is computed and printed beside it, so nothing is hidden. A
second assertion requires the asserted windows to cover at least 75% of the run, so a future boundary
error cannot quietly shrink the clause to nothing. **The clause is asserted, not dropped** — the plan's
own instruction is that it must never be deleted in an objective paragraph.

### 2. The performance assertion moved to the end of the test, after run 1

In run 1 the throughput assertion failed **before** the write-lag and chaos assertions, so four assertion
families never executed even though the printed report showed all four inside their thresholds. A
machine-dependent number must not be able to hide *"thirty thousand records arrived and thirty thousand
rows exist"*. The assertion was moved after every correctness assertion, with the reason written at it,
and the test re-run at full length. **Nothing was relaxed; only the order changed** — and run 2 then
executed and passed all nine correctness assertions before failing on the same throughput number, which
is what turns the four printed figures into asserted ones.

### 3. The retention sweep was given 5,000 expired bodies to delete

The plan asks for *"one retention sweep pass"* and does not say it must remove anything. A sweep over a
workspace with nothing expired runs one bounded `DELETE` returning zero rows — an index scan, not a
deletion job, and a thin closure of a chaos clause whose words are *"run the deletion job concurrently
with peak writes"*. The run therefore seeds 5,000 bodies in a **second workspace** through
`write_records` with a one-second `retention_window` against the fixture calendar's day 5 — genuinely
expired, with no clock moved, because `retention.py`'s whole design is that `now` is an argument. A
second workspace rather than a call-id prefix keeps the completion assertion a plain equality on
`WORKSPACE_A`'s rows. Recorded as a strengthening rather than slipped in.

### 4. Two acceptance criteria contradict the plan's own instructions; both resolved for substance

- **`grep -c "addopts" pyproject.toml` returns 0** vs. *"the explicit note that no `addopts` key is added
  and why"*. A note that may not name the thing it forbids is not a note. The comment names it twice; the
  **key** is absent, proved by parsing the table (above), which a comment cannot fake.
- **`the literal 410 does not appear in the file`** vs. the prescribed constant comment *"rather than
  written as 410"*. Reworded — and the plan's number was wrong anyway: `int(512 * 0.8)` is **409**.

Both are in `deferred-items.md` Part 10, with the carry-forward that a criterion phrased as a grep for a
refused spelling is unsatisfiable in a repository whose docstrings name refused spellings on purpose.
Part 9 recorded the same collision for `app.routes`.

### 5. `tests/load/__init__.py` carries a third copy of `counter_value`

`tests/broker/_helpers.py:99` and `tests/integration/test_write_path.py:140` carry the other two. The
proxy asserts that it asks for no broker; importing a helper module that imports `aio_pika`, the drain
and the fallback to borrow four lines would make that claim false at import time.

## What did not go as planned

**The scaled-down smoke run was worth its cost and is the reason this plan has a localised finding rather
than a bare red number.** Before the twelve-minute run, a throwaway harness at 1/15th scale exercised the
whole mechanism — the two-drain controller, the paced producer, the window snapshots, the sweep — and
found the throughput shortfall in sixty seconds. A second throwaway probe then measured
`write_records` and `resolve_price` directly. Both harnesses were deleted; `git status --porcelain`
confirms nothing of them survives.

**The assertion ordering was the plan's own near-miss.** Run 1 printed nine figures and asserted three of
them, and the difference is invisible in the printed report — it is only in the traceback. The cost of
finding it was a second twelve-minute run; the cost of not finding it would have been a summary claiming
four clauses closed on the strength of a `print`. This is recorded here rather than only in deviation 2
because the general lesson is cheap: **in a test that both reports and asserts, the order of the
assertions decides which of the reported numbers are load-bearing.**

**The two runs are reproducible where it matters.** Enqueue p95 0.4555 and 0.4814 ms, steady write-lag
share 98.8% and 97.8%, throughput 212 and 189 records/sec, both stalls a full 60 s with the backlog
cleared, both sweeps 5,000 bodies, both 30,000 of 30,000 rows. The spread is host noise; the shortfall is
not.

**Nothing else surprised.** The absolute arrival schedule held to within a second over ten minutes
(600.8 s and 600.7 s against an ideal 599.98 s), the handoff never filled, the fallback never fired, and
the two autouse fixtures cleaned up 35,000 rows and two queues without a line of bespoke teardown.

## For the reviewer and for later phases

- **CL-12's own three AC-12 clauses are green.** The blocker is a `performance_requirements` row that
  ROADMAP's success criteria do not restate and that this plan picked up under ORCHESTRATION §9a. If the
  orchestrator accepts the host caveat, CL-12 can be ticked and the drain figure routed to a named owner;
  if not, the fix is the batched price resolution described above and it belongs to whoever owns
  `writer.py` next.
- **The verifier must run `PROPE_RUN_LOAD=1 uv run pytest -m load -q` in its own session** — ORCHESTRATION
  §9.1 does not permit SC5 to be scored from this summary, and the default suite skips it. Budget ~11
  minutes plus container startup, launch it in the background, and **run nothing else against Docker while
  it runs**: the p95 and the throughput figure are both corrupted by concurrent container load.
- **`make check` does not depend on `make load`**, deliberately. The proxy is what stands in between full
  runs, and its argument is now two assertions rather than a paragraph.
- **Any later phase that injects an outage into a run carrying a latency percentile inherits deviation 1's
  arithmetic.** The rule: a percentile assertion and an injected outage belong to different windows of the
  same run, and the window boundaries are part of the assertion.
