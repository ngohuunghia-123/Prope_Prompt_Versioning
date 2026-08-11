---
phase: 03-durability-idempotency-and-no-read-path
plan: 08
kind: review-remediation
source: .planning/phases/03-durability-idempotency-and-no-read-path/03-REVIEW.md#CR-03
subsystem: backend
tags: [cr-03, cr-02, wr-14, shutdown, cancellation, asyncio, metadata-dropped, sc1]

# Dependency graph
requires:
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 01
    provides: "drain_handoff_on_stop, publish_or_fall_back, HANDOFF_DRAIN_DEADLINE_SECONDS and PUBLISH_TIMEOUT_SECONDS; app._stop_publisher and the derived PUBLISHER_STOP_TIMEOUT_SECONDS; tests/broker/test_handoff_shutdown_drain.py"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 07
    provides: "the phase state the review was written against"
provides:
  - "drain_handoff_on_stop with a STRUCTURAL remainder count (a `finally`) and a per-item budget bound — a cancel mid-drain can no longer skip the count, and one hung record can no longer hold the drain past its own deadline"
  - "In-flight accounting: the record taken out of the queue when the cancel lands is counted, which `qsize()` cannot see"
  - "HANDOFF_DRAIN_DEADLINE_SECONDS' arithmetic restated on the PUBLISH branch (512 x 5.0 s), which is the ordinary composition, instead of on the fallback branch's healthy-day 0.77 s"
  - "app._stop_publisher's cancel folded into `except (TimeoutError, asyncio.CancelledError)` — Phase 2's WR-14 dead branch is gone"
  - "tests/broker/test_handoff_shutdown_drain.py::test_one_hung_record_cannot_hold_the_drain_past_its_own_deadline and ::test_a_cancel_mid_drain_still_counts_every_record — the behaviour, both verified red against the old body"
affects: [03-VERIFICATION, 03-REVIEW, 19-21-gateway]

actuals:
  tokens: 61000
  tasks: 4
  commits: 0

tech-stack:
  added: []
  patterns:
    - "A loss counter that lives in a `finally`, because the caller cancels and CancelledError is not an Exception"
    - "A deadline enforced per item with the REMAINING budget, so it bounds when a loop RETURNS and not only when it stops TAKING work"
    - "In-flight accounting beside a queue's `qsize()`, because an item already taken out is invisible to the queue"
    - "A behavioural test written against the exact cancellation shape of the production caller, with `inspect.getsource` asserting the shapes are the same two lines rather than trusting the resemblance"
    - "A constant-inequality test kept and re-docstringed as necessary-not-sufficient rather than deleted when the behaviour it stood in for gains its own test"

key-files:
  created: []
  modified:
    - src/prope/call_ledger/enqueue.py
    - src/prope/app.py
    - tests/broker/test_handoff_shutdown_drain.py

key-decisions:
  - "The remainder count moved into a `finally` rather than the cancellation being caught. Catching BaseException in drain_handoff_on_stop would have counted the remainder and then swallowed a shutdown signal, which is the failure publish_or_fall_back's docstring already refuses in as many words ('a shutdown must still cancel this task rather than being counted as a durability failure'). A `finally` counts and then lets the CancelledError leave, so the task still ends cancelled — asserted as `drain.done()` in the new test."
  - "The in-flight record is counted too, which the review's sketch did not do. `get_nowait()` removes the item before the await, so `queue.qsize()` after a cancel reports 19 of 20 — exactly the review's own reproduction. The review's stated acceptance was 'metadata_dropped_total moved by N', so an `in_flight_unaccounted` counter is added and folded into the remainder. It can only ever be 0 or 1: TimeoutError sets `accounted`, and every ordinary Exception is caught and counted inside publish_or_fall_back."
  - "The per-item bound is `asyncio.wait_for(..., timeout=budget)` where budget is `deadline - loop.time()`, not a fresh per-item constant. A per-item constant would let N items each take it and reopen the same hole at N x constant; the remaining budget makes the loop's total bounded by the deadline it already declares, which is precisely what app's derived +2.0 s margin was assuming all along."
  - "A record that times out on its own gets its own log line WITH a call_id; the records still in the buffer keep the single group line. There is a name to report in the first case and none in the second, and `test_a_truncated_drain_counts_exactly_the_remainder_and_names_it_once`'s 'one line for the whole remainder' property is preserved for the remainder."
  - "test_the_stop_timeout_is_derived_from_the_drain_deadline was KEPT, not replaced. The inequality is still necessary — drift between the two constants is a real regression — it is just not sufficient, and its docstring now says so and names the two tests that carry the property."
  - "_stop_publisher's cancel moved into `except (TimeoutError, asyncio.CancelledError)` and both exceptions stay SWALLOWED. Re-raising would be defensible on its own terms but would stop the lifespan's `finally` reaching reset_handoff(), whose omission poisons every later enqueue() in the process — that is CR-08's subject and CR-08 is not this remediation's scope."
  - "The docstring at _stop_publisher states honestly that the cancel is a SECOND cancel request — reachable when the task ignored the first (CPython's own stated reason for keeping one available) or when an outer CancelledError arrives with the publisher still pending — rather than claiming the old trailing branch was doing work."

patterns-established:
  - "When a review supplies a concrete replacement implementation, check its accounting against the review's own reproduction numbers before adopting it verbatim — here the sketch would have counted 19 of 20"
  - "Prove a new regression test is discriminating by running its scenarios against a replica of the pre-fix body, and quote the numbers; a test that would have been green before the fix is not a regression test"

requirements-completed: []

coverage:
  - id: R1
    description: "A cancel that lands mid-drain — exactly the shape `_stop_publisher` produces — still counts every buffered record on prope_call_ledger_metadata_dropped_total, including the one already taken out of the queue"
    verification:
      - kind: test
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_a_cancel_mid_drain_still_counts_every_record"
        status: pass
    human_judgment: false
  - id: R2
    description: "One record whose fallback never returns cannot hold the drain past HANDOFF_DRAIN_DEADLINE_SECONDS — the deadline bounds when the drain RETURNS, not only when it stops taking work"
    verification:
      - kind: test
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_one_hung_record_cannot_hold_the_drain_past_its_own_deadline"
        status: pass
    human_judgment: false
  - id: R3
    description: "Both new tests are discriminating: run against a replica of the pre-fix drain body they reproduce the review's numbers (never returns; 19 still buffered, dropped delta 0.0)"
    verification:
      - kind: command
        ref: "scratchpad probe replicating the old loop over the real queue, publish_or_fall_back and counter — output quoted in the body"
        status: pass
    human_judgment: false
  - id: R4
    description: "HANDOFF_DRAIN_DEADLINE_SECONDS' arithmetic paragraph argues from the publish branch (512 x PUBLISH_TIMEOUT_SECONDS) and names the fallback's absent timeout, instead of quoting D-27's 0.77 s healthy-fallback figure as the bound"
    verification:
      - kind: manual
        ref: "src/prope/call_ledger/enqueue.py — the constant's docstring"
        status: pass
    human_judgment: false
  - id: R5
    description: "app._stop_publisher's cancel is inside an `except (TimeoutError, asyncio.CancelledError)` clause; the unreachable trailing `if not publisher.done()` branch (WR-14) is gone"
    verification:
      - kind: test
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_a_cancel_mid_drain_still_counts_every_record (its inspect.getsource assertions)"
        status: pass
    human_judgment: false
  - id: R6
    description: "The constant-inequality test survives and declares itself necessary-not-sufficient"
    verification:
      - kind: test
        ref: "tests/broker/test_handoff_shutdown_drain.py::test_the_stop_timeout_is_derived_from_the_drain_deadline"
        status: pass
    human_judgment: false

# Metrics
duration: 42min
completed: 2026-08-11
status: complete
---

# Phase 03 Remediation 08: CR-03 — the shutdown drain's remainder count

**This is a review remediation, not a plan execution.** There is no `03-08-PLAN.md`; the plan is
`03-REVIEW.md`'s single critical finding, CR-03, and the four items its "Fix" and its two named
follow-ons ask for. Everything below is scoped to that finding. The review's eight warnings and one
info are untouched and remain open.

**CR-03 is closed, and the closure is asserted by behaviour rather than by an inequality between two
literals.** `drain_handoff_on_stop` now counts what it could not reach from inside a `finally`, so a
`CancelledError` — which is a `BaseException` and therefore caught by nothing on the way out — can no
longer skip the count; and each item is bounded by the drain's own *remaining* budget, so the deadline
bounds when the loop **returns** and not merely when it stops **taking** work. Both properties have a
test, and both tests were verified red against a replica of the pre-fix body before being accepted.

## Performance

- **Duration:** ~42 min
- **Tasks:** 4 (the drain, the constant's prose, the tests, `_stop_publisher`)
- **Files modified:** 3 · created: 0 · **+259 / −40 lines**
- **Suite:** 414 passed / 1 skipped before → **416 passed / 1 skipped** after. Two tests added, none
  changed, none removed.

## The defect, restated in one paragraph

`_stop_publisher` does `asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)`, which
**cancels** the awaited task when the wait expires. That cancellation travels through `supervise`'s
`TaskGroup` and `run_with_restart` into `drain_handoff_on_stop`, which was mid-`await`.
`publish_or_fall_back` catches `Exception` and deliberately not `BaseException`, so the
`CancelledError` propagated straight out of the `while` and the three lines that counted the remainder
— which sat *after* the loop, unprotected — never ran. Twenty records buffered, nineteen still in the
queue, `prope_call_ledger_metadata_dropped_total` unmoved at `0.0`. That is CR-02's own sentence
reproduced inside the function written to close it, and it defeats ROADMAP SC1's *"every drop is
counted"*.

The constant derivation that was supposed to make it unreachable —
`PUBLISHER_STOP_TIMEOUT_SECONDS = HANDOFF_DRAIN_DEADLINE_SECONDS + 2.0` — bounds when the loop stops
*taking* work. `while loop.time() < deadline` gates entry to an iteration; it does not interrupt one.

## What shipped

### 1. `drain_handoff_on_stop` — structural count, per-item budget

```python
    loop = asyncio.get_running_loop()
    deadline = loop.time() + HANDOFF_DRAIN_DEADLINE_SECONDS
    in_flight_unaccounted = 0
    try:
        while True:
            budget = deadline - loop.time()
            if budget <= 0:
                break
            try:
                item = queue.get_nowait()
            except (asyncio.QueueEmpty, asyncio.QueueShutDown):
                break
            accounted = False
            try:
                await asyncio.wait_for(
                    publish_or_fall_back(item, publish, fallback), timeout=budget
                )
                accounted = True
            except TimeoutError:
                metadata_dropped_total.inc()
                accounted = True
                log.warning("call_ledger.handoff_abandoned", call_id=..., workspace_id=..., reason="stop_deadline")
            finally:
                queue.task_done()
                if not accounted:
                    in_flight_unaccounted += 1
    finally:
        remaining = queue.qsize() + in_flight_unaccounted
        if remaining:
            metadata_dropped_total.inc(remaining)
            log.warning("call_ledger.handoff_abandoned", reason="stop_deadline", group_size=remaining)
```

Three things about this that the review's sketch did not have, and one it did:

- **`in_flight_unaccounted` is the correction to the sketch.** `get_nowait()` removes the item
  *before* the await, so `queue.qsize()` in the `finally` reports **19 of 20** on a cancel — which is
  exactly the number the review's own reproduction printed. The review's stated acceptance is
  "`metadata_dropped_total` moved by **N**", so the record in flight has to be counted too. The
  variable can only ever be 0 or 1: a `TimeoutError` sets `accounted`, and every ordinary `Exception`
  is caught and counted one frame down inside `publish_or_fall_back`.
- **The cancellation is not caught, only counted.** A `except BaseException` here would swallow a
  shutdown signal, which `publish_or_fall_back`'s docstring already refuses in as many words. The
  `finally` counts and then lets the `CancelledError` leave, so the task still ends *cancelled* — the
  new test asserts `drain.done()` for exactly that reason.
- **The per-item timeout is the REMAINING budget, not a per-item constant.** A constant would let N
  items each take it and reopen the same hole at N × constant. `deadline - loop.time()` makes the
  loop's total bounded by the deadline it already declares.
- **A timed-out record is named individually; the untaken remainder keeps one group line.** There is a
  `call_id` to report in the first case and none in the second. No new log field is introduced —
  `call_id`, `workspace_id`, `reason` and `group_size` are all already on
  `observability.LOGGABLE_FIELDS`, so A-046 is untouched.

### 2. `HANDOFF_DRAIN_DEADLINE_SECONDS`' arithmetic, restated on the branch that runs

The old paragraph priced the worst case at **0.77 s** from D-27's ~1.5 ms single-record *fallback*
transaction. The ordinary composition is the **publish** branch: `run_publisher` binds
`publish_record`, which awaits `exchange.publish(..., timeout=PUBLISH_TIMEOUT_SECONDS)` — **5.0 s**.
So a broker that has accepted the connection and stopped answering confirms holds **one** record for
longer than the whole 3.0 s inner deadline *and* longer than the whole 5.0 s outer wait, and a full
512-record handoff for up to `512 × 5.0 s` ≈ **43 minutes**. The fallback is worse in kind rather than
merely slower: `build_fallback_writer`'s `workspace_transaction` + `write_records` has **no timeout at
all**, and a degraded database during shutdown is exactly the state in which records are still
buffered. The docstring now says all of that, says D-27's 0.77 s is the good day rather than the bound,
and says in its own words that *"the derivation is necessary; it is not what the guarantee rests on"*.

### 3. The tests

- **`test_one_hung_record_cannot_hold_the_drain_past_its_own_deadline`** — deadline patched to 0.5 s,
  20 records, a fallback that awaits an `asyncio.Event()` nobody sets. Asserts the drain returns in
  less than `PUBLISH_TIMEOUT_SECONDS`, that the counter moved by 20, and that the log carries the
  hung record's own `call_id` line followed by one group line of 19. **Before the fix this test hangs**
  — the outer `wait_for(timeout=10)` is the failure mode, not the assertion.
- **`test_a_cancel_mid_drain_still_counts_every_record`** — deadline patched **above** the wait rather
  than below it, deliberately falsifying the derivation; 20 records; the drain cancelled with the same
  two lines `_stop_publisher` uses, and `inspect.getsource(_stop_publisher)` asserted to contain them
  so the resemblance is checked rather than trusted. Asserts `drain.done()`, that the counter moved by
  **20**, and that there is exactly one group line at `group_size == 20`.
- **`test_the_stop_timeout_is_derived_from_the_drain_deadline`** is **kept**, with a docstring that now
  says the inequality is *necessary and not sufficient*, that it was green while the drain lost 19 of
  20 records, and which two tests carry the property instead.

### 4. `_stop_publisher` — WR-14's dead branch, folded

```python
        try:
            await asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)
        except (TimeoutError, asyncio.CancelledError):
            publisher.cancel()
        application.state.publisher = None
```

`contextlib.suppress` is no longer imported by `app.py` — it had one use site and this was it. Both
exceptions stay **swallowed**, exactly as before: re-raising is defensible on its own terms but would
stop the lifespan's `finally` reaching `reset_handoff()`, and that is CR-08's subject, not this
remediation's. The new docstring is honest about what the cancel is: a **second** cancel request,
reachable when the task caught and ignored the first — CPython's own stated reason for keeping one
available, quoted in `Task.cancel`'s source — or when an outer `CancelledError` arrives with the
publisher still pending. It does not claim the old trailing `if not publisher.done()` was doing work;
it says it was a branch that could not be taken.

## The evidence that the new tests are discriminating

A test that would have been green before the fix is not a regression test. Rather than reverting the
module in a shared tree, a scratch probe replicated the **pre-fix loop body verbatim** over the real
`handoff()` queue, the real `publish_or_fall_back` and the real counter, and drove the two scenarios:

```
hung-record: OLD BODY NEVER RETURNED (outer wait_for blew) -> test would fail
cancel-mid-drain: still buffered 19, dropped delta 0.0 (want 20.0)
```

The second line is the review's reproduction to the digit — *"still buffered: 19 | dropped after:
0.0"*. Against the shipped body both scenarios pass. The probe lives in the session scratchpad and is
not in the repository.

## The gate, observed

```
uv run ruff check src/ tests/ alembic/
All checks passed!
```

```
uv run pytest -q
416 passed, 1 skipped, 1 warning in 224.42s (0:03:44)
```

The suite was **414 passed, 1 skipped** at the review; it is **416 passed, 1 skipped** now, and the
two added tests are the whole difference. The one `s` is still `test_fifty_records_a_second_for_ten_minutes`
behind `PROPE_RUN_LOAD`. `uv run ruff format --check` was not run — Broken Window #1, not a gate, not
this remediation's.

## What this does NOT close

Said plainly, because the review is the plan and eight of its ten findings are untouched:

- **CR-04** (worker-only gauges served hard zeros, two paging alerts that cannot fire) — open.
  `app.py` was edited here, and its `/metrics` docstring was **deliberately not corrected**, because
  that correction is CR-04's and doing half of it in a CR-03 change would make the next reader think
  it was handled.
- **CR-05** (writer-side retention overflow at 2,912,227 days), **CR-06** (four modules' stale prose —
  including `enqueue.py:24-29`, which this change did not rewrite because it is CR-06's paragraph and
  not CR-03's), **CR-07** (WR-11's two tests), **CR-08** (`lifespan` teardown can still skip
  `reset_handoff()` / `engine.dispose()`), **CR-09** (six unrecorded UNCONFIRMED adoptions,
  `WINDOWS.md` has no phase-3 row), **CR-10** (the red `performance_requirements` throughput clause),
  **CR-11**, **CR-12** — all open, none touched.
- **Phase 2's carried-forward register** is unchanged except **WR-14**, which CR-03 folded in and
  which is now closed.

## For the reviewer and for later phases

- **The guarantee no longer rests on two constants agreeing.** It rests on a `finally` and a per-item
  `wait_for`. The constants are still derived and still asserted, and their test now says out loud
  that it is the weaker of the three.
- **`queue.qsize()` is not the count of what a stop lost.** Anything that took an item out before
  awaiting owes the caller an in-flight variable. This is the second time in this phase that a loss
  counter was wrong by exactly the item in flight, and phases 19–21's gateway inherits the same
  handoff.
- **The publish branch is the branch to argue from.** Any future timing argument about the shutdown
  path that quotes D-27's 1.5 ms is arguing about the fallback on a healthy database, which is not the
  ordinary composition and is not the worst case.

## Ledger entries owed

### deferred-items.md

- **CR-03 is remediated in full** (drain count structural, per-item budget bound, constant's arithmetic
  corrected, `_stop_publisher`'s cancel folded). The review's `findings.critical: 1` can be scored
  closed; `status: issues_found` should stay, because eight warnings and one info are open.
- **Phase 2's WR-14 (dead branch in `_stop_publisher`) is CLOSED** — the carried-forward register in
  `03-REVIEW.md` marks it *"folded into CR-03's fix"*, and it now is.
- **CR-04's `/metrics` docstring correction was deliberately NOT taken here**, although `app.py` was
  edited. It belongs with CR-04's alert-rule assertion and OQ-026 note, in one change, with an owner.
- **The remainder count's in-flight term is a behaviour change worth one line in `03-UAT.md`**: a
  shutdown that is cancelled mid-drain now counts the record that was in flight as well as those still
  buffered, so `prope_call_ledger_metadata_dropped_total` moves by the full buffered count rather than
  by that count minus one. It is a more accurate number on an existing counter, not a new signal.

### ORCHESTRATION-DECISIONS.md

| Phase | Plan | Decision | Rejected alternative | Reversibility |
|---|---|---|---|---|
| 03 | 08 (CR-03 remediation) | `drain_handoff_on_stop` bounds each item with the drain's remaining budget, so a record whose publish or fallback hangs is abandoned at the stop deadline and counted on `metadata_dropped_total` rather than holding the drain open | Leaving the bound between items only and relying on `PUBLISHER_STOP_TIMEOUT_SECONDS > HANDOFF_DRAIN_DEADLINE_SECONDS`, which bounds when the loop stops taking work and not when it returns | Reversible — code only, no data, no wire format |
| 03 | 08 (CR-03 remediation) | `_stop_publisher` continues to SWALLOW `TimeoutError` and `asyncio.CancelledError` after moving the cancel into the `except` clause | Re-raising the `CancelledError` so a cancelled shutdown is not silently absorbed — refused here because the lifespan's `finally` must still reach `reset_handoff()`, which is CR-08's scope | Reversible — code only |

### WINDOWS.md (broken windows)

- No new window. **One candidate closed:** the CR-03 defect itself, if the orchestrator opened a window
  for it. Broken Window #1 (`ruff format --check` fails repo-wide) is unchanged and was not run.
