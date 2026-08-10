---
phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
reviewed: 2026-08-10T00:00:00Z
depth: standard
files_reviewed: 50
files_reviewed_list:
  - alembic/versions/0004_workspace_retention.py
  - docs/brainstorm/open_questions/OQ-018.md
  - docs/brainstorm/open_questions/OQ-019.md
  - docs/brainstorm/open_questions/OQ-020.md
  - docs/brainstorm/open_questions/OQ-021.md
  - pyproject.toml
  - src/prope/app.py
  - src/prope/broker/__init__.py
  - src/prope/broker/connection.py
  - src/prope/broker/topology.py
  - src/prope/call_ledger/api.py
  - src/prope/call_ledger/drain.py
  - src/prope/call_ledger/enqueue.py
  - src/prope/call_ledger/envelope.py
  - src/prope/call_ledger/models.py
  - src/prope/call_ledger/retention.py
  - src/prope/call_ledger/retention_settings.py
  - src/prope/call_ledger/schemas.py
  - src/prope/call_ledger/seams.py
  - src/prope/call_ledger/writer.py
  - src/prope/db/engine.py
  - src/prope/db/session.py
  - src/prope/observability.py
  - src/prope/session_auth.py
  - src/prope/supervisor.py
  - src/prope/worker.py
  - tests/architecture/test_no_sql_interpolation.py
  - tests/architecture/test_route_table.py
  - tests/architecture/test_schema_invariants.py
  - tests/broker/_helpers.py
  - tests/broker/test_declared_arguments.py
  - tests/broker/test_drain_failure_classification.py
  - tests/broker/test_enqueue_reaches_a_committed_row.py
  - tests/broker/test_publish_confirm_failures.py
  - tests/conftest.py
  - tests/integration/_asgi.py
  - tests/integration/test_ceiling_refuses_evals_only.py
  - tests/integration/test_eval_usage_priced_without_body.py
  - tests/integration/test_health_and_readiness.py
  - tests/integration/test_management_routes.py
  - tests/integration/test_migration_chain.py
  - tests/integration/test_run_totals.py
  - tests/integration/test_spend_currency_invariant.py
  - tests/integration/test_worker_jobs.py
  - tests/integration/test_workspace_retention_setting.py
  - tests/security/test_eval_no_body_boundary.py
  - tests/unit/__init__.py
  - tests/unit/test_period_month.py
  - tests/unit/test_retention_argument_guards.py
  - tests/unit/test_supervisor.py
findings:
  critical: 2
  warning: 16
  info: 0
  total: 18
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-08-10
**Depth:** standard
**Files Reviewed:** 50
**Status:** issues_found

## Summary

The tenant seam holds. I traced every statement in this phase to its transaction and
found no missing `SET LOCAL app.workspace_id`, no SQL interpolation, and no unbounded
metric label. The `workspace_id` gate on `CallRecordEnvelope` is real and is genuinely
the first thing that runs on the broker payload; `_parse` dead-letters before any
transaction opens, and the spy test proves it rather than asserts it. Refusal shapes
(404-not-403 on `{id}`, byte-identical 401 on every route) are correct. The
`ON CONFLICT ... WHERE` currency invariant is correct and is proved three separate ways.

Two things are wrong badly enough to block.

The first is an **unbounded integer on a management route** that reaches
`datetime + timedelta` inside the drain: `PUT /api/v1/workspaces/{id}/retention` accepts
any `int`, and a value above ~2.9 million silently converts every subsequent
body-carrying record for that workspace into a permanently dead-lettered one. It is
reachable by a workspace admin, it is classified `PERMANENT` by
`classify_write_failure`, and nothing anywhere names the retention setting as the cause.

The second is **silent, uncounted record loss on every graceful shutdown**. `enqueue`'s
module docstring stakes the whole Phase-2 known-lossy-window argument on
`metadata_dropped_total` making the loss *measurable rather than merely admitted*.
`run_publisher` exits on `stopping` without draining the handoff, so the records sitting
in the buffer at deploy time vanish and that counter never moves. The one control the
phase relies on does not cover the most routine loss path there is.

Underneath those, a cluster of async-lifecycle defects in `prope.app` and `prope.worker`
(unsupervised background task, shutdown that aborts before `engine.dispose()`, a
readiness timeout that does not cover the thing that actually hangs, a non-interruptible
sleep in the drain) plus an A-046 control — `LOGGABLE_FIELDS` — that is referenced only
in prose and read by no code at all.

Two tests pass while proving materially less than their names and docstrings claim.

## Critical Issues

### CR-01: `retention_days` is an unbounded `int`; a management route can permanently poison the drain for a workspace

**File:** `src/prope/call_ledger/schemas.py:394`, `src/prope/call_ledger/api.py:715-742`,
`src/prope/call_ledger/writer.py:333`

**Issue:** `RetentionSet.retention_days` carries no bound:

```python
class RetentionSet(BaseModel):
    retention_days: int
```

The docstring argues the absence deliberately — *"There is no lower bound on this field
and that is deliberate. `ck_workspace_retention_window_is_positive` is what refuses a
zero or negative window"*. That reasoning covers the **lower** bound only. There is no
upper bound anywhere: not in the model, not at the route, not in
`set_retention_window`, and not in the CHECK, which only tests `retention_window >
interval '0'`.

Two distinct failures follow, and the second is the serious one.

**(a) Unhandled 500.** `api.set_retention` does `timedelta(days=payload.retention_days)`
at line 720. `timedelta` raises `OverflowError` for `days >= 10**9`, and
`OverflowError: Python int too large to convert to C int` for very large values. That
is not `IntegrityError`, so the route's `except` does not see it; it is not
`SQLAlchemyError`, so `install_error_envelope`'s handler does not see it; and
`install_error_envelope` deliberately registers no catch-all. `{"retention_days":
1000000000000}` therefore produces an unhandled exception, a traceback in the log, and a
non-envelope 500 — the second error shape A-045 says does not exist.

**(b) Permanent, silent record loss.** For values in roughly `2_912_227 .. 999_999_999`
the whole write path succeeds: `timedelta` accepts it, the CHECK accepts it, Postgres
`interval` holds it, `read_retention_window` returns it as a `timedelta`, and
`_write_group` hands it to `write_records`. There, at `writer.py:333`:

```python
"expires_at": draft.created_at + retention_window,
```

raises `OverflowError: date value out of range` (verified: for a record created
2026-08-05, `retention_days = 2_912_227` is the first breaking value). `OverflowError`
matches none of `classify_write_failure`'s branches, so it takes the documented
default — `WriteFailure.PERMANENT` — and the record is `reject(requeue=False)`'d to the
DLQ with `reason="write_refused"`. **Every gateway record carrying a body, for that
workspace, from that moment on**, is dead-lettered. The drain reports itself healthy,
`/readyz` stays green, and the only log line says `write_refused` with no mention of
retention. Recovering means noticing a DLQ that fills for one tenant only.

This is a data-loss path reachable from an authenticated management route with a value
that looks like a plausible typo (`retention_days: 30000000` — "thirty million", a
fat-fingered 30). It is not the accepted Phase-2 loss window: that one is bounded,
broker-scoped, and counted.

**Fix:** Bound the field where the other bounds live, and state the ceiling in terms of
the thing that actually breaks.

```python
#: The ceiling is not decoration. ``write_records`` stamps
#: ``created_at + retention_window``, and a window that pushes a record's expiry past
#: ``datetime.max`` raises ``OverflowError`` inside the drain — which
#: ``classify_write_failure`` reads as PERMANENT and dead-letters. 100 years is far
#: beyond any retention policy and far inside the arithmetic.
MAX_RETENTION_DAYS = 36_500

class RetentionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retention_days: int = Field(le=MAX_RETENTION_DAYS)
```

`ge`/positivity stays at the engine as argued. Add a route test at
`MAX_RETENTION_DAYS + 1` asserting `422` / `ErrorCode.VALIDATION_FAILED`, and a drain
test asserting that a workspace on the maximum window still writes rather than
dead-letters. Separately, consider adding `OverflowError` to
`classify_write_failure`'s explicit branches so a future arithmetic overflow is named
rather than swept into the unrecognised-error default.

---

### CR-02: every graceful shutdown drops the handoff without incrementing `metadata_dropped_total`

**File:** `src/prope/call_ledger/enqueue.py:274-283`, `src/prope/app.py:143-157`,
`src/prope/app.py:183-189`

**Issue:** `run_publisher` tests `stopping` at the top of its loop and returns:

```python
queue = handoff()
while not stopping.is_set():
    try:
        record = await asyncio.wait_for(queue.get(), timeout=0.1)
    except TimeoutError:
        continue
    ...
```

`lifespan`'s `finally` sets `stopping` and then calls `_stop_publisher`, which waits for
the task to return. Whatever is sitting in `_handoff` at that instant — up to
`HANDOFF_MAXSIZE` (512) records, and in practice whatever arrived in the last
publish round trip — is discarded when the process exits. **No counter is incremented
and no log line is written.**

That directly contradicts the control the whole phase rests on. `enqueue.py`'s module
docstring:

> `prope_call_ledger_metadata_dropped_total` is what makes that window measurable
> rather than merely admitted, and it will be non-zero in Phase 2.

and `app.py`'s `readyz` docstring says the same. The known-and-accepted list covers
`enqueue()` counting-and-dropping on a full buffer and on a failed confirm. It does not
cover a drop that is invisible to the counter — and "A-139 already accepts that loss"
in the `HANDOFF_MAXSIZE` comment is scoped to a **hard kill**, not to an ordinary
`docker compose up -d` rollout, which takes this path every single time.

There is a second, narrower instance of the same hole: `publish_record` catches
`Exception`, not `BaseException`, so a record in flight when
`_stop_publisher`'s `asyncio.wait_for` timeout cancels the task is also lost
uncounted.

**Fix:** Drain the buffer on the way out, and count what cannot be drained. Two changes:

```python
async def run_publisher(exchange: AbstractExchange, stopping: asyncio.Event) -> None:
    queue = handoff()
    try:
        while not stopping.is_set():
            try:
                record = await asyncio.wait_for(queue.get(), timeout=0.1)
            except TimeoutError:
                continue
            try:
                await publish_record(exchange, record)
            finally:
                queue.task_done()
    finally:
        # Shutdown is not a licence to lose records silently. Publish what is
        # still buffered; count whatever the exchange will no longer take.
        await _drain_remaining(exchange, queue)


async def _drain_remaining(exchange: AbstractExchange, queue) -> None:
    while True:
        try:
            record = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        try:
            await publish_record(exchange, record)
        except BaseException:
            metadata_dropped_total.inc()
            log.warning(
                "call_ledger.handoff_abandoned",
                call_id=record.call_id,
                workspace_id=record.workspace_id,
                reason="shutdown",
            )
        finally:
            queue.task_done()
```

and give `_stop_publisher` a stop budget large enough for that drain, or count the
residue explicitly if the timeout fires. Add a test in
`tests/broker/test_publish_confirm_failures.py`: enqueue N records, set `stopping`
immediately, assert that `written`/`published` plus the delta on
`metadata_dropped_total` equals N — i.e. that no record leaves the system unaccounted
for. `handoff_abandoned` / `shutdown` are both closed-vocabulary values and fit
`LOGGABLE_FIELDS`' existing `reason` entry.

## Warnings

### WR-01: `/readyz`'s timeout does not cover connection acquisition — the probe can still hang

**File:** `src/prope/app.py:262-275`

**Issue:**

```python
async with engine.connect() as connection:
    await asyncio.wait_for(
        connection.execute(READINESS_PROBE),
        timeout=READINESS_TIMEOUT_SECONDS,
    )
```

`READINESS_TIMEOUT_SECONDS` guards only `SELECT 1` on an **already established**
connection. `engine.connect()` — DNS, TCP connect, TLS, auth, pool wait — is outside it,
and that is the step that actually blocks when a database is unreachable rather than
merely slow. Against a blackholed host (dropped SYN, not a refused one) `/readyz` hangs
until the OS TCP timeout, typically well over two minutes.

The constant's own docstring makes the opposite promise: *"A readiness probe that hangs
is reported unhealthy anyway, by the healthcheck's own timeout, with a reason nobody can
read. Answering `503` with the failed check named is strictly more information than
timing out."* The code does not deliver that for the dominant failure mode.

`tests/integration/test_health_and_readiness.py:42` is shaped so it cannot catch this —
*"Port 1 on the loopback refuses immediately rather than hanging, which keeps these tests
fast"* — so `READINESS_TIMEOUT_SECONDS` currently has no test at all.

**Fix:**

```python
try:
    async def _probe() -> None:
        async with engine.connect() as connection:
            await connection.execute(READINESS_PROBE)

    await asyncio.wait_for(_probe(), timeout=READINESS_TIMEOUT_SECONDS)
except Exception as error:
    log.warning("app.not_ready", reason=type(error).__name__)
else:
    return JSONResponse(status_code=200, content={"status": "ready", "checks": ["database"]})
```

Add a test that points the engine at a socket that accepts and never answers (a
`asyncio.start_server` that reads and does nothing), and assert `/readyz` returns 503
inside, say, 5 s.

---

### WR-02: a publisher exception aborts lifespan shutdown before `engine.dispose()` and before the broker stack closes

**File:** `src/prope/app.py:143-157`, `src/prope/app.py:183-189`

**Issue:**

```python
with suppress(TimeoutError, asyncio.CancelledError):
    await asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)
```

`asyncio.wait_for` re-raises whatever the awaited task raised. `suppress` covers
`TimeoutError` and `CancelledError` only, so if `run_publisher` died on anything else,
that exception propagates out of `_stop_publisher` and out of `lifespan`'s `finally`
block — skipping `await stack.aclose()` (the broker connection and confirm channel) and
`await engine.dispose()` (the whole asyncpg pool), and skipping `log.info("app.stopped")`.

The consequence is a shutdown that leaves the AMQP connection and every pooled database
connection unclosed, on the exact path a rolling deploy takes, and a lifespan error that
uvicorn reports instead of a clean stop.

**Fix:** Isolate the publisher teardown, and unwind the rest unconditionally.

```python
async def _stop_publisher(application: FastAPI) -> None:
    publisher = getattr(application.state, "publisher", None)
    if publisher is not None:
        try:
            await asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)
        except (TimeoutError, asyncio.CancelledError):
            publisher.cancel()
        except Exception as error:
            # A-046: the class, never the message.
            log.warning("app.publisher_crashed", reason=type(error).__name__)
        application.state.publisher = None
    ...
```

and in `lifespan`:

```python
finally:
    stopping.set()
    try:
        await _stop_publisher(application)
    finally:
        await engine.dispose()
        log.info("app.stopped")
```

---

### WR-03: the background publisher is an unsupervised, unobserved task on the record path

**File:** `src/prope/app.py:136-140`

**Issue:**

```python
application.state.publisher = asyncio.create_task(
    run_publisher(channel.default_exchange, stopping)
)
```

No `add_done_callback`, no restart, no metric, no log. If `run_publisher` ever raises —
a channel object in a bad state, a `RuntimeError` from an `asyncio.Queue` bound to a
different loop, anything `publish_record`'s `except Exception` cannot see — the task
dies, Python surfaces it only as *"Task exception was never retrieved"* at garbage
collection time, and `app` keeps serving. `/readyz` is the database alone, so it stays
green by design. `enqueue()` then fills the buffer and starts counting drops, which is
the only visible symptom, and there is no `/metrics` endpoint this phase.

This is precisely the failure `prope.supervisor` exists to prevent, and `prope.worker`
gets it for both of its jobs. `app`'s single long-lived task gets nothing. The
asymmetry is not argued anywhere in `app.py`'s otherwise very complete docstring.

**Fix:** At minimum, observe it:

```python
def _publisher_died(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        log.warning("app.publisher_crashed", reason=type(error).__name__)

publisher = asyncio.create_task(run_publisher(channel.default_exchange, stopping))
publisher.add_done_callback(_publisher_died)
```

Better: wrap it in `prope.supervisor.run_with_restart("call_record_publisher", ...)`,
which already exists, already backs off, and already logs `supervisor.job_crashed` with
a `job` field that is on `LOGGABLE_FIELDS`. That would make the two processes share one
restart discipline instead of one having it and one not.

---

### WR-04: the drain's transient backoff sleep is not interruptible and is per-group

**File:** `src/prope/call_ledger/drain.py:402`

**Issue:**

```python
for message, _ in group:
    await message.nack(requeue=True)
await asyncio.sleep(TRANSIENT_BACKOFF_SECONDS)
continue
```

A bare `asyncio.sleep` inside the per-group loop. Two problems:

1. **Shutdown latency is unbounded in group count.** A window can hold up to
   `WINDOW_SIZE` messages across an arbitrary number of workspaces. With the database
   down, each group nacks and sleeps a full second, and `stopping` is not consulted
   between them. A 30-workspace window is 30 s of shutdown latency; docker-compose's
   default stop grace period is 10 s, so the container is `SIGKILL`ed mid-window instead
   of draining. `run_worker`'s docstring promises the opposite: *"The in-flight window is
   committed before that happens."*
2. It contradicts the project's own stated discipline. `supervisor.py` names this as
   Trap 2 — *"Every wait in this module goes through `_sleep_or_stop`, which returns the
   moment the stop event is set"* — and `drain.py` is the module that receives the same
   `stopping` event and does not follow it.

**Fix:** Reuse the existing helper rather than writing a second one.

```python
from prope.supervisor import _sleep_or_stop  # or lift it to a shared name

...
for message, _ in group:
    await message.nack(requeue=True)
if await _sleep_or_stop(stopping, TRANSIENT_BACKOFF_SECONDS):
    return
continue
```

(`_sleep_or_stop` should lose its leading underscore if it is going to be shared.)
Assert it: publish records for K workspaces, make the write transient, set `stopping`,
and assert `run_drain` returns in well under `K * TRANSIENT_BACKOFF_SECONDS`.

---

### WR-05: `_refuse_unrepresentable_money` checks scale but not precision, so an over-large figure is a 500 rather than a 422

**File:** `src/prope/call_ledger/api.py:309-348`

**Issue:** The guard's docstring says it refuses *"a figure the money columns cannot hold
**exactly**"*, but it only tests finiteness and the number of decimal places:

```python
if not figure.is_finite():
    unrepresentable[name] = str(figure)
elif -figure.as_tuple().exponent > MONEY_SCALE_PLACES:
    unrepresentable[name] = str(figure)
```

`numeric(20,10)` is precision 20, scale 10 — ten integer digits at most.
`Decimal("99999999999")` (eleven integer digits) is finite, has exponent `0`, passes the
guard, reaches the `INSERT`, and Postgres answers `numeric field overflow`. asyncpg
raises `DataError`, which is a `DBAPIError` and **not** an `IntegrityError`, so
`create_price_row`'s `except IntegrityError` does not see it. It falls through to
`install_error_envelope`'s `SQLAlchemyError` handler and the caller gets
`500 internal_error` for what is plainly a client input error. The same applies to
`monthly_limit` / `per_run_limit` on `PUT /spend-ceiling`.

Every other money refusal on this route carries its own `ErrorCode` precisely because
ADR-0053 makes the code the thing the SPA renders. A 500 renders as nothing useful.

**Fix:** Test the whole representable range, not half of it.

```python
#: numeric(20,10): ten integer digits and ten fractional ones.
MONEY_INTEGER_PLACES = MONEY_SCALE_PLACES  # 20 - 10

def _exceeds_column(figure: Decimal) -> bool:
    exponent = figure.as_tuple().exponent
    digits = len(figure.as_tuple().digits)
    scale = max(0, -exponent)
    integer_digits = max(0, digits + min(0, exponent) if exponent < 0 else digits + exponent)
    return scale > MONEY_SCALE_PLACES or integer_digits > MONEY_INTEGER_PLACES
```

and keep the existing `MONEY_SCALE_EXCEEDED` code (or add
`MONEY_PRECISION_EXCEEDED` if the two deserve separate catalogue entries). Add a route
test asserting `422` rather than `500` for `input_price_per_1k = "99999999999"`.

Note also that `-figure.as_tuple().exponent` is a type error under a strict checker:
`exponent` is `int | Literal["n", "N", "F"]`. The `is_finite()` guard makes it safe at
runtime, but the negation should move inside a narrowed branch.

---

### WR-06: `LOGGABLE_FIELDS` is read by no code — the A-046 allow-list is prose, not a control

**File:** `src/prope/observability.py:49-67`

**Issue:** `LOGGABLE_FIELDS` is defined, documented at length as the mechanism —

> What a log line may carry is an ALLOW-LIST (see `LOGGABLE_FIELDS`), never a deny-list
> of field names, because a deny-list fails silently the first time a field is renamed.

— and cited by `enqueue.py:31`, `drain.py:32`, `supervisor.py:63` and a test docstring.
A repo-wide grep finds **zero** reads of it outside docstrings. `configure_logging()`
installs `merge_contextvars`, `add_log_level`, `TimeStamper`, `JSONRenderer` and nothing
that filters keys. Any `log.warning("x", body=...)` anywhere in the codebase would be
emitted verbatim.

So the control that A-046 rests on is a naming convention enforced by review, described
in four modules as if it were enforced by construction. The publish-path marker tests
in `test_publish_confirm_failures.py` check two specific marker strings on two specific
code paths — real evidence, but evidence about those paths, not about the allow-list.

**Fix:** Make the constant do the job its docstring claims, as a structlog processor:

```python
def _allow_listed(logger, method_name, event_dict):
    """A-046: drop any key not on the allow-list, and say so rather than staying silent."""
    unexpected = set(event_dict) - LOGGABLE_FIELDS - {"level", "timestamp"}
    for key in unexpected:
        event_dict.pop(key)
    if unexpected:
        event_dict["dropped_fields"] = sorted(unexpected)  # names only, never values
    return event_dict
```

inserted before `JSONRenderer`. Then add an architecture test that logs a body-shaped
value on an invented field and asserts it does not appear in the rendered line. If a
runtime filter is not wanted, the alternative is an AST gate in
`tests/architecture/` over every `log.<level>(...)` keyword in `src/prope/` — the same
posture `test_no_sql_interpolation.py` already takes. Either way, delete the four
docstring claims or make one of them true.

---

### WR-07: `request_id` is logged but is not on `LOGGABLE_FIELDS`

**File:** `src/prope/call_ledger/schemas.py:442`, `src/prope/observability.py:49-67`

**Issue:**

```python
log.info(event, reason=str(code), request_id=request_id)
```

`request_id` is not a member of `LOGGABLE_FIELDS`. `observability.py` added `job` in this
same phase with an explicit note:

> Recorded here rather than left in `deferred-items.md` because an allow-list with a
> field outside it is an allow-list somebody has already stopped believing.

`request_id` is exactly that field, added in the same wave, and it was not recorded. It
is a server-generated prefixed ULID, so it qualifies on the same rule `job` qualified
on — this is a bookkeeping miss, not a leak. But it is the first drift, and it lands in
the phase that wrote the sentence warning about it.

**Fix:** Add it beside `job`, with the same style of justification:

```python
        #: Added by plan 02-05. ``api.refused`` / ``api.failed`` carry it, and its
        #: value is a server-generated ``req_`` ULID — not a caller value, not an
        #: identifier of any stored subject, and the only thing joining a client's
        #: envelope to the line that refused it (INT-024).
        "request_id",
```

---

### WR-08: `prope.worker` has no bounded broker connect, and leaks the engine if the connect fails

**File:** `src/prope/worker.py:342-367`

**Issue:**

```python
connection = await build_connection(settings.broker_url)
try:
    async with connection:
        ...
finally:
    log.info("worker.stopped")
    await engine.dispose()
```

`build_connection` is **outside** the `try`. `aio_pika.connect_robust` defaults to
`fail_fast=True`, so an unreachable broker raises here — before the `try` — and
`engine.dispose()` never runs. More importantly there is no timeout: a broker host that
resolves and does not answer holds `_amain` open indefinitely, and `worker` exposes no
HTTP surface (D-17), so its compose healthcheck is process-level and reports a worker
that has never finished starting as healthy.

`prope.app` guards exactly this shape and explains why:

> a process that never finishes starting is worse than one that starts degraded — the
> compose healthcheck cannot tell them apart

`worker` inherits none of that reasoning.

**Fix:**

```python
#: The same bound ``prope.app`` puts on its own broker bring-up, and for the same
#: reason: a worker that never finishes starting is indistinguishable from a healthy
#: one to a process-level healthcheck.
BROKER_CONNECT_TIMEOUT_SECONDS = 10.0

...
try:
    connection = await asyncio.wait_for(
        build_connection(settings.broker_url), timeout=BROKER_CONNECT_TIMEOUT_SECONDS
    )
    async with connection:
        log.info("worker.started")
        await run_worker(...)
finally:
    log.info("worker.stopped")
    await engine.dispose()
```

If crashing on an absent broker is the intended behaviour (defensible — the drain is
the worker's reason to exist), say so at the code, because the retention sweep would
otherwise still have useful work to do.

---

### WR-09: `run_drain`'s `finally` can mask the exception that killed it

**File:** `src/prope/call_ledger/drain.py:427-428`

**Issue:**

```python
finally:
    await queue.cancel(consumer_tag)
```

The most likely reason `run_drain`'s body raises is a channel-level failure — an
`ack`/`nack`/`reject` on a closed channel, a broker disconnect mid-window. In exactly
that state `queue.cancel(consumer_tag)` also raises, and because it raises from a
`finally` it **replaces** the original exception. What reaches
`supervisor.run_with_restart` is then the cancel's exception class, and A-046 means the
only thing logged is `reason=type(error).__name__` — so the operator is told
`ChannelInvalidStateError` from the teardown instead of whatever actually broke.

On the one path whose whole purpose is not losing records, that is a real diagnostic
loss.

**Fix:**

```python
finally:
    # A cancel that fails must not replace the exception that caused the failure —
    # the class name is all A-046 lets us log, so it has to be the right one.
    with suppress(Exception):
        await queue.cancel(consumer_tag)
```

---

### WR-10: two tenant-scoped statements omit the explicit `workspace_id` predicate the rest of the module writes out

**File:** `src/prope/call_ledger/seams.py:530-541`, `src/prope/call_ledger/writer.py:168-179`

**Issue:** `RUN_TOTALS` filters on `run_id` alone, and `UNPRICED_WORKLIST` on
`cost_status` alone. Both rely entirely on the RLS policy for tenant scoping, and both
say so:

> The tenant policy supplies the workspace restriction, so there is no `workspace_id`
> predicate to forget

Every other tenant-scoped statement in this module takes the opposite posture and argues
for it explicitly — `CEILING_READ` (*"The explicit predicate is bound and is written
alongside the policy rather than instead of it"*), `retention.DELETE_CHUNK` (*"The
workspace predicate is written out, alongside the policy rather than instead of it"*),
`retention_settings.READ_RETENTION_WINDOW`, `api.PRICE_ROWS`' `PARTITION BY`. Two
statements in one module doing the opposite of the module's stated rule is the kind of
inconsistency that gets copied.

It also undercuts `get_run_totals`' own argument. D-20 justifies the two-argument
signature partly on the index: *"Phase 1's `ix_call_record_workspace_id_run_id` leads
with `workspace_id`, and the one-argument form could not have used it."* The statement
that is supposed to use that index never names its leading column; whether the index is
reachable depends on the planner folding the RLS qual in, which is exactly the
planner-choice dependency `retention.DELETE_CHUNK` refuses to rely on.

**Fix:** Bind it, like everywhere else. `get_run_totals` already has the value in hand.

```python
RUN_TOTALS = text(
    """
    SELECT ...
    FROM   ledger.call_record
    WHERE  workspace_id = :workspace_id AND run_id = :run_id
    """
)
```

`UNPRICED_WORKLIST` is called from `list_unpriced`, which likewise already holds
`session.workspace_id`. Keep the comments; change what they say to match the rest of the
module.

---

### WR-11: two tests pass while proving materially less than their names claim

**File:** `tests/broker/test_publish_confirm_failures.py:152-181`,
`tests/broker/test_enqueue_reaches_a_committed_row.py:156-168`

**Issue:**

`test_enqueue_returns_normally_through_every_failure_branch` — the only assertion in the
body is `assert enqueue(gateway_draft(...)) is None`, three times. `enqueue` is
annotated `-> None` and every branch ends in a bare `return`, so this can only ever be
`None`; the assertion carries no information beyond "it did not raise". The test then
runs the publisher until the handoff empties and stops it, and asserts **nothing** about
what happened. A regression in which every publish silently succeeded, or in which
`publish_record` stopped counting, would leave this green. Its three siblings above it
all assert counter deltas; this one does not, and it is the one whose docstring claims
*"INT-018 across all three reasons at once"* — it exercises one reason (`unroutable`),
not three.

`test_enqueue_returns_normally_with_no_broker_running` — docstring: *"INT-018's contract
at its hardest branch: there is no broker at all."* The body calls `enqueue(draft)` with
no publisher running. Nothing in the test ever attempts to reach a broker, so "no broker
running" is not a branch the test exercises; it is testing `put_nowait` on an empty
queue, which is the *easiest* branch.

**Fix:** For the first, assert the counters the siblings assert:

```python
before = _counter_value("unroutable")
dropped_before = _dropped_value()
...
assert _counter_value("unroutable") == before + 3
assert _dropped_value() == dropped_before + 3
```

For the second, either rename it to what it proves
(`test_enqueue_buffers_without_a_publisher_and_returns`) or make it prove its title by
running `run_publisher` against `UNREACHABLE_BROKER_URL`-style connection state and
asserting `metadata_dropped_total` moved by the number enqueued — which is also the
assertion CR-02 needs.

---

### WR-12: `enqueue()`'s catch-all branch increments one counter but not the other

**File:** `src/prope/call_ledger/enqueue.py:130-141`

**Issue:** The `QueueFull` branch increments both `metadata_dropped_total` and
`enqueued_total{outcome="dropped"}`, with a docstring explaining why both are needed:
*"the second says a record was offered and refused, the first says it will never reach
`ledger.call_record`"*. The catch-all branch immediately below increments only
`metadata_dropped_total`:

```python
except Exception:
    metadata_dropped_total.inc()
    log.warning("call_ledger.handoff_failed", ...)
    return
```

So `sum(enqueued_total)` under-counts records actually offered, and the invariant
`enqueued_total{accepted} + enqueued_total{dropped} == records offered` — which is the
only thing that makes `enqueued_total` interpretable — is false on that branch.

**Fix:**

```python
except Exception:
    metadata_dropped_total.inc()
    enqueued_total.labels(source=str(record.source), outcome="dropped").inc()
    ...
```

`record.source` is already read on the branch above, so it is available and cannot be
the thing that raised.

---

### WR-13: `prope.call_ledger.models` is imported by no production code, and its stated purpose is contradicted by every call site

**File:** `src/prope/call_ledger/models.py:1-29`

**Issue:** The module docstring:

> What lives here is the shape the application queries through, so a repository writes
> `select(call_record)` instead of assembling SQL by hand.

No module under `src/prope/` imports it. Every statement in `writer.py`, `seams.py`,
`api.py`, `retention.py`, `retention_settings.py` and `db/session.py` is a raw
`text(...)` constant — which is itself a deliberate decision, enforced by
`tests/architecture/test_no_sql_interpolation.py`. The only importer is
`tests/architecture/test_schema_invariants.py`. `alembic/env.py` imports
`prope.db.metadata` but not these tables, so they do not feed autogenerate either.

That leaves 164 lines of Core `Table` definitions whose sole function is to be the
left-hand side of a drift assertion. That is a legitimate use, but the docstring
describes a different one, and the mismatch will send the next reader looking for the
`select()` call sites that do not exist.

**Fix:** Do not delete it — the drift guard is worth keeping. Rewrite the first
paragraph to say what it is:

```
"""The six tables call-ledger owns, declared so a drift guard has something to compare.

**Nothing in ``src/prope/`` imports this module.** Every statement in this package is a
raw ``text()`` constant, because ``tests/architecture/test_no_sql_interpolation.py``
requires one and because schema-qualified SQL is what makes a forbidden edge legible
(ADR-0027). These declarations exist so
``tests/architecture/test_schema_invariants.py`` can assert the live catalogue is a
superset of them — a drift guard, not a query surface. If a later phase does start
writing ``select(call_record)``, this paragraph is what changes.
"""
```

---

### WR-14: dead branch in `_stop_publisher`

**File:** `src/prope/app.py:149-150`

**Issue:**

```python
with suppress(TimeoutError, asyncio.CancelledError):
    await asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)
if not publisher.done():
    publisher.cancel()
```

`asyncio.wait_for` cancels the awaited task on timeout and awaits its cancellation
before raising, so by the time control reaches line 149 the task is always `done()`. The
branch is unreachable on every path — normal return, timeout, or exception. Harmless,
but it reads as a safety net that is doing something, which will discourage the next
reader from looking at the real gap (WR-02).

**Fix:** Fold it into the restructured handler in WR-02, where `publisher.cancel()`
moves into the `except (TimeoutError, CancelledError)` branch and is reachable only if
`wait_for`'s own cancellation did not complete.

---

### WR-15: docstrings reference a constant that does not exist

**File:** `src/prope/call_ledger/api.py:352`, `src/prope/call_ledger/api.py:507`

**Issue:** Both cite `RANGED_PRICE_ROWS`:

```python
"""One mapping from ``RANGED_PRICE_ROWS`` as its response model."""
...
    stored — see :data:`RANGED_PRICE_ROWS`.
```

The constant is named `PRICE_ROWS` (line 156). `:data:` is a Sphinx cross-reference, so
this is a broken link as well as a stale name, and a reader greps for a symbol that is
not there. Given how much of this codebase's correctness argument lives in its
docstrings, name drift in them is not cosmetic.

**Fix:** Rename both references to `PRICE_ROWS`.

---

### WR-16: `call_id` crosses the broker with no character-class gate, unlike `workspace_id` beside it

**File:** `src/prope/call_ledger/envelope.py:143`

**Issue:**

```python
call_id: str = Field(min_length=1, max_length=64)
workspace_id: str = Field(
    min_length=WORKSPACE_ID_MIN_LENGTH,
    max_length=WORKSPACE_ID_MAX_LENGTH,
    pattern=WORKSPACE_ID_PATTERN,
)
```

The module docstring's argument for the `workspace_id` gate is that binding stops
injection but *"does not stop a `workspace_id` that is 4 MB of text, or one carrying a
newline"*. `call_id` is caller-supplied too (A-099), is the primary key of
`ledger.call_record`, and is the value carried on **every** log line this phase's
publish and drain paths emit (`enqueue.py:124`, `:136`, `:206`, `:220`, `:246`;
`drain.py:315`). It gets length bounds and no character class.

The residual risk is small — `JSONRenderer` escapes control characters, so log injection
is not available, and the value is bound not interpolated. But the asymmetry is
unexplained in a module whose whole point is the gate, and `call_id` is the field a
future operator tool is most likely to render unescaped.

**Fix:** Give it the same treatment and say why the class differs, if it does:

```python
#: The same posture as ``workspace_id``: an identifier that reaches a primary key and
#: every log line on this path is bounded in length AND in character class. ADR-0003's
#: prefixed ULIDs (``cal_...``) are a strict subset; this is a boundary gate, not a
#: second implementation of the identifier grammar.
CALL_ID_PATTERN = r"^[A-Za-z0-9_-]+$"

call_id: str = Field(min_length=1, max_length=64, pattern=CALL_ID_PATTERN)
```

Add the refusal to the existing
`test_envelope_refuses_the_values_that_must_never_reach_set_config` parametrisation
(rename it, since it would then cover more than `set_config`).

---

_Reviewed: 2026-08-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
