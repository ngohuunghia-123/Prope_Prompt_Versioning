---
phase: 03-durability-idempotency-and-no-read-path
reviewed: 2026-08-11T00:00:00Z
depth: standard
files_reviewed: 51
files_reviewed_list:
  - .planning/ORCHESTRATION-DECISIONS.md
  - .planning/WINDOWS.md
  - Makefile
  - alembic/versions/0004_workspace_retention.py
  - deploy/prometheus/rules/call_ledger.rules.yml
  - docs/brainstorm/open_questions/OQ-025.md
  - docs/brainstorm/open_questions/OQ-026.md
  - docs/brainstorm/open_questions/OQ-085.md
  - docs/modules/call-ledger.lock.yml
  - pyproject.toml
  - src/prope/app.py
  - src/prope/call_ledger/api.py
  - src/prope/call_ledger/domain.py
  - src/prope/call_ledger/drain.py
  - src/prope/call_ledger/enqueue.py
  - src/prope/call_ledger/envelope.py
  - src/prope/call_ledger/fallback.py
  - src/prope/call_ledger/pricing.py
  - src/prope/call_ledger/repricing.py
  - src/prope/call_ledger/retention_settings.py
  - src/prope/call_ledger/schemas.py
  - src/prope/call_ledger/seams.py
  - src/prope/call_ledger/writer.py
  - src/prope/observability.py
  - src/prope/supervisor.py
  - src/prope/worker.py
  - tests/architecture/test_alert_rules.py
  - tests/architecture/test_route_table.py
  - tests/broker/_helpers.py
  - tests/broker/test_broker_unreachable_fallback.py
  - tests/broker/test_drain_failure_classification.py
  - tests/broker/test_enqueue_reaches_a_committed_row.py
  - tests/broker/test_handoff_shutdown_drain.py
  - tests/broker/test_publish_confirm_failures.py
  - tests/broker/test_queue_depth_gauges.py
  - tests/broker/test_redelivery_leaves_the_total_unmoved.py
  - tests/conftest.py
  - tests/integration/test_ceiling_refuses_evals_only.py
  - tests/integration/test_health_and_readiness.py
  - tests/integration/test_management_routes.py
  - tests/integration/test_price_resolution_is_batched.py
  - tests/integration/test_worker_jobs.py
  - tests/integration/test_write_path.py
  - tests/load/__init__.py
  - tests/load/test_enqueue_off_response_path.py
  - tests/load/test_fifty_rps_for_ten_minutes.py
  - tests/security/test_no_body_read_path.py
  - tests/security/test_report_role_can_read_bodies.py
  - tests/unit/__init__.py
  - tests/unit/test_effective_dated_pricing.py
  - tests/unit/test_retention_days_bound.py
findings:
  critical: 1
  warning: 8
  info: 1
  total: 10
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-08-11
**Depth:** standard
**Files Reviewed:** 51 — the 40 source, test and deploy files the phase's seven commits changed,
plus 11 the findings depend on (the three open questions the phase raised or appended, the lock
file, the retention migration, `supervisor.py`, `retention_settings.py`, `conftest.py`,
`tests/unit/__init__.py`, and the two planning ledgers §9 requires)
**Status:** issues_found

## Summary

The durability claim is real. I drove every failure site in `publish_record` to the injected
`FallbackWriter` and back out to `ledger.call_record`, and the row is there — written through the
one `write_records`, priced at the record's own `created_at`, `body=None` before the write rather
than after, and read back in the tests through `migrate_engine` rather than through the code that
put it there. `prope_call_ledger_metadata_dropped_total` now means what ADR-0041 says it means.
CL-02 is closed on the statement rather than on an error handler, and
`test_the_upsert_and_not_the_error_handler_is_what_absorbs_a_duplicate` is the negative control
that says so — it re-offers the same `call_id` through the raw `INSERT` the writer no longer
issues and watches PostgreSQL refuse it, which is the only way to distinguish "the upsert skipped
it" from "something caught an `IntegrityError`".

**The N+1 fix is keyed on the pair, not on the instant, and I checked this three ways.**
`load_price_book` groups on `(provider_config_id, upstream_model)` (`pricing.py:63-67`), the
statement joins pairwise through `unnest` of two arrays rather than through two independent
`= ANY`, and `PriceBook.price_at` is called with `at=draft.created_at` per record
(`writer.py:455-459`) and never with a batch-wide instant.
`test_records_either_side_of_a_price_change_get_different_prices` writes three records straddling
a supersession in **one batch and one transaction**, asserts one round trip, and then reads back
two different `price_row_id`s and two different costs through the owner role — a whole-batch
shortcut or an instant-keyed memo fails it whatever its round-trip count says. ADR-0019 is intact:
the writer never revisits a stored cost, and `repricing.UPDATE_TO_PRICED` carries
`AND cost_status = 'unpriced'` in its own `WHERE`, so a price row added later cannot move a call
that was already priced. The commit message's claim that the key is deliberately not the timestamp
is the code's behaviour and not a rationalisation.

The `prope_report` finding is the best piece of work in the phase. The body-read sweep is
enumerated at three layers *and* the fourth reader — the `LOGIN BYPASSRLS` reporting role that no
layer the application controls can see — is asserted deliberately in
`tests/security/test_report_role_can_read_bodies.py`, with the tenant GUC checked unset on the
reading connection so it is a bypass rather than a forgotten context, a `prope_app` negative
control beside it, and the two facts behind it (`rolbypassrls`, `has_table_privilege`) asserted
separately so a future `REVOKE` and a future `NOBYPASSRLS` are distinguishable failures. It is
routed to OQ-025 clause 2 rather than fixed, and the file says at the top what to read before
"fixing" a red run.

Anti-patterns: **zero.** No `TODO`, `FIXME`, `XXX`, `HACK` or `TBD` anywhere in `src/`, `tests/`,
`alembic/` or `deploy/`; no `NotImplementedError` outside the one `except NotImplementedError` the
Windows signal guard needs; no bare `pass`; no ellipsis stub. Phase 2's bar held.

Forbidden edges hold. Every `from prope...` import under `src/prope/call_ledger/` resolves to
`prope.call_ledger.*`, `prope.broker.*`, `prope.db.*`, `prope.observability` or
`prope.session_auth`. No business module is imported and `apis.consumes: []` is still true.
`ruff check src/ tests/ alembic/` exits clean, observed this session.

**One thing is wrong badly enough to block, and it is CR-02 itself.**
`drain_handoff_on_stop` counts the remainder *after* its loop, with nothing between them, so the
count is skipped entirely when `_stop_publisher`'s `asyncio.wait_for` cancels the task mid-drain.
I reproduced it: twenty records buffered, the drain cancelled the way `_stop_publisher` cancels it,
**nineteen records still in the queue and `metadata_dropped_total` unmoved at 0.0.** The derivation
that is supposed to make this unreachable — `PUBLISHER_STOP_TIMEOUT_SECONDS =
HANDOFF_DRAIN_DEADLINE_SECONDS + 2.0` — bounds when the loop stops *taking* work, not when it
*returns*, and a single item can hold it for `PUBLISH_TIMEOUT_SECONDS` (5.0 s) plus an unbounded
database transaction. The only test of the derivation asserts that one constant is larger than the
other.

Underneath that: the two paging alerts that read `worker`-only gauges are served **hard zeros** by
the only scrapable process rather than being absent, which is worse and is the opposite of what
both the code and OQ-026 say; CR-01 is closed at the route with the writer-side overflow Phase 2
called "the serious one" left unbounded, untested, and argued against a ceiling 300× too large;
four modules carry prose that this phase's own later plans made false; and Phase 2's WR-11 was
edited by 03-01 and left proving nothing.

Scope drift was declared honestly in every case I checked. 03-01's
`test_health_and_readiness.py` change from `is None` to `is not None` is the fallback-only job
being correct, not a test bent to fit — the assertion got **stronger**, and
`test_a_broker_that_was_never_reachable_still_produces_durable_records` is the independent proof
that a job now runs on that branch and writes rows. Every one of 03-04's seven, 03-05's four and
03-06's five deviations is a strengthening or a recorded judgement; none relaxes an assertion.

## Critical Issues

### CR-03: the shutdown drain's remainder count is skipped when the stop wait cancels it — CR-02 is closed on the ordinary path and reopened on the timeout path

**File:** `src/prope/call_ledger/enqueue.py:600-626`, `src/prope/call_ledger/enqueue.py:100-128`,
`src/prope/app.py:270-278`, `tests/broker/test_handoff_shutdown_drain.py:87-97`

**Issue:** `drain_handoff_on_stop` counts what it could not reach *after* its loop, unprotected:

```python
    while loop.time() < deadline:
        try:
            item = queue.get_nowait()
        except (asyncio.QueueEmpty, asyncio.QueueShutDown):
            break
        try:
            await publish_or_fall_back(item, publish, fallback)
        finally:
            queue.task_done()

    remaining = queue.qsize()
    if remaining:
        metadata_dropped_total.inc(remaining)
        log.warning("call_ledger.handoff_abandoned", reason="stop_deadline", group_size=remaining)
```

`publish_or_fall_back` catches `Exception` and deliberately not `BaseException`. So a
`CancelledError` thrown into the loop propagates straight out of the `while` and the three lines
that count the remainder never execute. That is not hypothetical — it is precisely what
`_stop_publisher` does when its wait expires:

```python
with suppress(TimeoutError, asyncio.CancelledError):
    await asyncio.wait_for(publisher, timeout=PUBLISHER_STOP_TIMEOUT_SECONDS)
```

`asyncio.wait_for` cancels the awaited task on timeout, `supervise`'s `TaskGroup` propagates the
cancellation into the job body, `run_with_restart` re-raises `CancelledError` untouched by
contract, and `drain_handoff_on_stop` dies mid-`await`. Reproduced against the real module, with
no database and no broker — a slow fallback standing in for a hung one:

```
buffered: 20 | dropped before: 0.0
still buffered: 19 | dropped after: 0.0
```

Nineteen records gone, `prope_call_ledger_metadata_dropped_total` unmoved. That is CR-02's exact
sentence — *"records vanish and that counter never moves"* — reproduced inside the function
written to close it, and it defeats ROADMAP SC1's "every drop is counted".

**The derivation that is supposed to make this unreachable does not bound the thing it claims
to.** `HANDOFF_DRAIN_DEADLINE_SECONDS`' docstring (`enqueue.py:100-119`) says:

> if the inner deadline ever equalled or exceeded the outer wait, the cancel would land while the
> drain was still working and the remainder count would never run — which reproduces CR-02 with
> more machinery.

and then argues the numbers from:

> a full handoff is 512 records; D-27 prices a single-record fallback transaction at roughly 1.5 ms
> against a local PostgreSQL, so the worst case — the broker entirely gone and every record falling
> back — is roughly 0.77 s

Three things are wrong with that as a bound.

1. **The deadline is consulted only between items.** `while loop.time() < deadline` gates entry to
   an iteration; it does not interrupt one. An item taken at `t = 2.99 s` may return at any later
   time whatsoever.
2. **One item is not 1.5 ms on the branch this actually runs on.** The healthy branch passes
   `publish = partial(publish_record, exchange, fallback=fallback)`, and `publish_record` awaits
   `exchange.publish(..., timeout=PUBLISH_TIMEOUT_SECONDS)` — **5.0 s** (`enqueue.py:92`). A broker
   that has accepted the connection and stopped answering confirms therefore holds a single item
   for longer than the whole 3.0 s inner deadline and longer than the whole 5.0 s outer wait. The
   stated worst case of 0.77 s describes the fallback-only branch and is off by three orders of
   magnitude on the branch where a publisher exists.
3. **The fallback itself has no timeout at all.** `build_fallback_writer`'s `workspace_transaction`
   + `write_records` is bounded by nothing. A degraded database during shutdown — which is exactly
   the state in which records are still in the buffer — produces the same outcome on the degraded
   branch.

**The test cannot see any of this.** `test_the_stop_timeout_is_derived_from_the_drain_deadline`
asserts `PUBLISHER_STOP_TIMEOUT_SECONDS > HANDOFF_DRAIN_DEADLINE_SECONDS` — a relationship between
two literals, not the property the derivation exists to buy.
`test_a_truncated_drain_counts_exactly_the_remainder_and_names_it_once` patches the deadline to
`0.0`, so its loop body never runs at all and the cancellation path is never entered. Both are
green today and both would stay green after this defect got worse.

**Fix:** make the count structural rather than positional, and bound each item.

```python
async def drain_handoff_on_stop(publish, fallback) -> None:
    queue = handoff()
    queue.shutdown()

    loop = asyncio.get_running_loop()
    deadline = loop.time() + HANDOFF_DRAIN_DEADLINE_SECONDS
    try:
        while True:
            budget = deadline - loop.time()
            if budget <= 0:
                break
            try:
                item = queue.get_nowait()
            except (asyncio.QueueEmpty, asyncio.QueueShutDown):
                break
            try:
                # One item may not consume the whole stop budget: the publish
                # alone is bounded at PUBLISH_TIMEOUT_SECONDS and the fallback's
                # transaction is bounded by nothing, so without this the loop's
                # own deadline bounds when it stops TAKING work and not when it
                # RETURNS — and the cancel below lands mid-drain.
                await asyncio.wait_for(
                    publish_or_fall_back(item, publish, fallback), timeout=budget
                )
            except TimeoutError:
                metadata_dropped_total.inc()
                log.warning(
                    "call_ledger.handoff_abandoned",
                    call_id=item.draft.call_id,
                    workspace_id=item.draft.workspace_id,
                    reason="stop_deadline",
                )
            finally:
                queue.task_done()
    finally:
        # In a `finally`, because the caller cancels this task when its own wait
        # expires and a CancelledError is not an Exception — a count that lives
        # after the loop is a count that a cancel skips, which is CR-02 exactly.
        remaining = queue.qsize()
        if remaining:
            metadata_dropped_total.inc(remaining)
            log.warning(
                "call_ledger.handoff_abandoned", reason="stop_deadline", group_size=remaining
            )
```

Then replace the constant-inequality test with the behaviour. Enqueue N records, run
`drain_handoff_on_stop` against a fallback that never returns, cancel it the way `_stop_publisher`
does, and assert `metadata_dropped_total` moved by N — i.e. that no record leaves the system
unaccounted for even when the stop budget is blown. Keep
`test_the_stop_timeout_is_derived_from_the_drain_deadline` as well; the inequality is still
necessary, it is just not sufficient, and its docstring should say so.

Two follow-ons worth doing in the same change, because they are the same argument:

- `HANDOFF_DRAIN_DEADLINE_SECONDS`' arithmetic paragraph should state the publish branch's worst
  case (`512 × PUBLISH_TIMEOUT_SECONDS` without a per-item bound) rather than the fallback branch's,
  since the publish branch is the ordinary composition.
- `_stop_publisher`'s `if not publisher.done(): publisher.cancel()` (`app.py:276-277`) is still
  Phase 2's WR-14 dead branch — `wait_for` has already cancelled and awaited by then. Fold the
  cancel into an `except (TimeoutError, asyncio.CancelledError)` clause where it is reachable,
  rather than leaving a safety net that reads as if it were doing something.

## Warnings

### CR-04: the two alerts that read `worker`-only gauges are served **hard zeros**, not nothing — and the code and OQ-026 both say the opposite

**File:** `src/prope/app.py:470-484`, `deploy/prometheus/rules/call_ledger.rules.yml:164-165`,
`deploy/prometheus/rules/call_ledger.rules.yml:218-219`,
`docs/brainstorm/open_questions/OQ-026.md:38-51`, `src/prope/call_ledger/fallback.py:141-142`

**Issue:** `/metrics`' docstring and OQ-026 both classify eight metrics as *"absent from this
response entirely"* / *"Absent entirely — incremented only in `worker`"*. Rendering the registry
the way the route does shows that five of the eight are **present and read zero**:

```
prope_call_ledger_written_total                      -> NO SAMPLE
prope_call_ledger_write_lag_seconds_count            -> ['prope_call_ledger_write_lag_seconds_count 0.0']
prope_call_ledger_queue_depth                        -> ['prope_call_ledger_queue_depth 0.0']
prope_call_ledger_dlq_depth                          -> ['prope_call_ledger_dlq_depth 0.0']
prope_call_ledger_redelivered_total                  -> ['prope_call_ledger_redelivered_total 0.0']
prope_call_ledger_retention_deleted_total            -> ['prope_call_ledger_retention_deleted_total 0.0']
prope_call_ledger_oldest_body_age_seconds            -> ['prope_call_ledger_oldest_body_age_seconds 0.0']
prope_call_ledger_ceiling_check_total                -> NO SAMPLE
```

That is D-40 working exactly as designed — a family declared at import renders even with no
increment, which is the property `test_metrics_exposes_a_metric_nothing_has_incremented` asserts on
purpose two files away. The consequence for the alert rules is the opposite of "absent", and worse:

- **`LedgerRetentionOverdue`** — `prope_call_ledger_oldest_body_age_seconds > (30 + 1) * 24 * 60 *
  60`, **severity: page**. `app` publishes a hard `0.0` and `worker` publishes nothing at all, so
  the series exists, is healthy-looking on every graph, and **the rule can never fire.** An absent
  series at least leaves `absent()` available as a meta-rule; a zero series does not.
- **`LedgerDlqNonEmpty`** — `prope_call_ledger_dlq_depth > 0`, T-005's HIGH mitigation and, after
  D-30, the *only* signal that says a record is genuinely missing from `ledger.call_record`. Same
  shape: permanently `0.0`.

There is also a plain factual error in the same list. `write_lag_seconds` is listed as
`worker`-only — *"the drain, on the durable moment"* — but `fallback.write_directly` observes it in
`app` (`fallback.py:141-142`), by design, because the direct write is a durable moment too and its
own docstring argues for exactly that. So it belongs in the **partial** group and the split is five
partial / seven absent, not four / eight. This matters beyond bookkeeping: `LedgerWriteLagHigh`
computes `histogram_quantile` over `app`'s buckets, which during a broker outage carry the
fallback's real observations and during normal running carry none.

**Why this is a warning and not "declared":** OQ-026 is the artifact the user will adjudicate, it
is rated `high` on the strength of "three of the seven declared alerts cannot fire", and the
mechanism it describes is not the mechanism that is running. A resolver choosing between the four
recorded answers needs to know that option 3 (`prometheus_client` multiprocess mode) is not
competing against silence but against a false-healthy series, and that a fifth cheap answer — drop
the eight `worker`-only families from `app`'s registry, or serve them via `absent()`-friendly
recording rules — exists precisely because they are being rendered.

**Fix:** correct `app.py`'s `/metrics` docstring to say *present and permanently zero* rather than
*absent*, move `write_lag_seconds` into the partial list there, and note the correction in
`deferred-items.md` so the verifier can carry it into OQ-026 rather than this review editing a
`docs/` artifact. Then add the assertion the correction implies, in
`tests/architecture/test_alert_rules.py`:

```python
def test_the_worker_only_gauges_render_as_zero_from_app_and_the_rules_know_it() -> None:
    """OQ-026's real shape: a zero series, not an absent one — which is worse.

    An absent series can be caught with `absent()`; a hard zero looks like a
    measurement. `LedgerRetentionOverdue` pages on this gauge and `app` is the
    only process that serves it.
    """
    body = generate_latest(REGISTRY).decode()
    for name in ("prope_call_ledger_oldest_body_age_seconds", "prope_call_ledger_dlq_depth"):
        assert f"\n{name} 0.0" in body, f"{name} is not rendered at all; OQ-026 has changed shape"
```

---

### CR-05: CR-01 is closed at the route only — the writer-side overflow Phase 2 called "the serious one" has no bound, no test, and a stated ceiling 300× too large

**File:** `src/prope/call_ledger/schemas.py:120-139`, `src/prope/call_ledger/schemas.py:409-442`,
`src/prope/call_ledger/writer.py:566`, `src/prope/call_ledger/drain.py:179-192`,
`alembic/versions/0004_workspace_retention.py:138-143`,
`tests/unit/test_retention_days_bound.py:67-87`

**Issue:** `RetentionSet.retention_days: int = Field(le=MAX_RETENTION_DAYS)` with
`MAX_RETENTION_DAYS = 3650` genuinely closes the route, and the route test asserts `422` /
`VALIDATION_FAILED` with a positive control at the boundary. That is CR-01 part (a).

CR-01 part (b) — the one Phase 2's review called *"the serious one"* — is a different failure at a
different boundary in a different module. `write_records` stamps

```python
"expires_at": draft.created_at + retention_window,
```

and that raises `OverflowError: date value out of range` from **2,912,227 days**, not from
1,000,000,000. Verified against the pinned interpreter for a record created 2026-08-05:

```
first overflowing days: 2912227
timedelta.max.days: 999999999
```

`OverflowError` is an `ArithmeticError` and matches no branch of `classify_write_failure`, so it
takes the `PERMANENT` default and dead-letters — *every body-carrying record for that workspace,
from that moment on*, with `write_refused` in the log and no mention of retention. The phase
declined to add a branch for it ("classify_write_failure gains no ArithmeticError branch —
drain.py is untouched").

The recorded reasoning names only the smaller boundary, and it names it as the whole story:

> above ``timedelta.max.days`` — 999,999,999 — that expression raises ``OverflowError``

and at the constant:

> **What it does not do.** It does not bound the stored column. A workspace whose window is already
> longer than ten years would be unaffected — there are none, and no path exists that could have
> created one

Both sentences are true today. Together they are an invitation. A later reader tuning
`MAX_RETENTION_DAYS` upward has been told the hazard is `timedelta.max.days`, so `100_000` and
`5_000_000` both look equally safe by the stated argument — and one of them silently reopens a
permanent per-tenant data-loss path two modules away. The engine, which *can* hold this bound
(`ck_workspace_retention_window_is_positive` is right there and bounds only the other end), is
argued out of it on a premise that covers part (a) alone: *"a CHECK cannot refuse an exception
raised in the client"*. True for the route; false for the writer, whose overflow comes from a value
the engine handed back.

The test file inherits the same blind spot. It proves `timedelta(days=10**9)` raises and that the
schema refuses it; it proves `timedelta(days=3650).days == 3650`. Nothing anywhere asserts that a
record written under the maximum window survives `write_records` — which is the drain test Phase
2's CR-01 explicitly asked for.

**Fix:** three small things, none of which moves the constant.

1. State the real ceiling where the constant is argued, in terms of what actually breaks:

```python
#: **The binding ceiling is not ``timedelta.max.days``.** ``writer.write_records``
#: stamps ``created_at + retention_window`` (``writer.py:566``), and that overflows
#: at roughly **2,912,227 days** — about 0.3% of ``timedelta.max.days``. Above it the
#: OverflowError is raised inside the DRAIN, from a value the engine handed back, and
#: ``classify_write_failure`` reads it as PERMANENT: every body-carrying record for
#: that workspace dead-letters, permanently, under a log line that says
#: ``write_refused`` and never says "retention". Anyone raising this constant is
#: bounded by that number and not by the one the route's own exception names.
MAX_RETENTION_DAYS = 3650
```

2. Put the bound where it can also hold against a value that did not come through the route. A
   second CHECK in the next revision costs one line and makes the engine, not `RetentionSet`, the
   thing that refuses a poisoning window:

```sql
CONSTRAINT ck_workspace_retention_window_is_bounded
    CHECK (retention_window <= interval '3650 days')
```

   If that is deliberately refused, the refusal belongs beside the positivity CHECK's paragraph
   rather than only in a pydantic docstring.

3. Add the drain test CR-01 asked for: a workspace on `MAX_RETENTION_DAYS`, one body-carrying
   record through `write_records`, and a `call_body` row read back through `migrate_engine`. It is
   three lines and it is the only assertion that would go red if the constant were ever raised past
   the real ceiling.

---

### CR-06: four modules carry prose that this phase's own later plans made false

**File:** `src/prope/call_ledger/enqueue.py:24-29`, `src/prope/app.py:388-393`,
`src/prope/observability.py:33-37`, `src/prope/observability.py:288-290`,
`src/prope/observability.py:369-373`

**Issue:** 03-01 wrote forward-looking sentences about what 03-02 and 03-04 would do. Those plans
landed and the sentences were not revisited. All five are still in the tree:

`enqueue.py:24-29` —

> **What is still missing is the idempotent upsert on `call_id`** that makes a REDELIVERED record
> safe: … the second arrival raises an `IntegrityError` the drain dead-letters. That is CL-02 and
> plan 03-02, and until it lands a timed-out confirm is survivable rather than safe.

CL-02 landed in 03-02. `write_records` issues `ON CONFLICT (call_id) DO NOTHING … RETURNING
call_id`, and `drain.classify_write_failure`'s own docstring now says *"That gap is closed"* — so
one module in this package states the opposite of another about the same mechanism.

`app.py:388-393`, inside `readyz`'s docstring, which the route-table test polices for exactly this
class of rot —

> And until CL-02's idempotent upsert lands, a record whose confirm timed out is written by the
> fallback and then redelivered by the broker, where the second arrival dead-letters rather than
> being absorbed.

`observability.py:33-37` —

> **There is still no `/metrics` endpoint.** It arrives in plan 03-04, on `app` alone … so until
> then these are observable from tests and from nothing else.

03-04 shipped it as the eighth route.

`observability.py:288-290` — *"Plan 03-02 **removes** the two increments in `drain.py` … today"*.
It removed them in this phase; the present tense reads as pending work.

`observability.py:369-373` — the sharpest one, because it is factually inverted:

> Its increment site arrives with plan 03-02's explicit refusal in `write_records`: **today** a
> `source=gateway` draft with a NULL `version_id` dies as an `IntegrityError` under
> `ck_call_record_gateway_calls_carry_version_id` and dead-letters under a CONSTRAINT's name rather
> than under this counter's.

`writer.py:425-430` has done `missing_version_id_total.inc()` and raised a named `ValueError` since
03-02. The counter's own docstring tells the next reader that its increment site does not exist.

**Why this is a finding and not housekeeping.** This phase set the standard itself, twice, and both
times in writing. `test_the_module_states_the_readiness_rule_and_the_loss_window_that_survives`
changed its required string from `"records genuinely"` to `"A-139"` with the reason *"a docstring
that has stopped being true is worse than no docstring"*. 03-04's deviation 7 corrected two stale
path counts on the same grounds, unasked. `observability.py` is the module every later phase reads
to learn what a metric means, and it currently teaches three things that are not so.

**Fix:** rewrite each in the past tense with the outcome, in the voice 03-04's deviation 7 used —
`enqueue.py` to say the upsert landed and what the residual is (the 512-record hard-kill window,
and D-34's decision that a body arriving after a timed-out confirm is discarded);
`app.py:388-393` to drop the "until CL-02 lands" clause and keep A-139;
`observability.py:33-37` to say `/metrics` is served on `app` and point at OQ-026 for what is
partial there; `:288-290` to past tense; `:369-373` to name `writer.py`'s refusal as the live
increment site. Consider extending
`test_the_module_states_the_readiness_rule_and_the_loss_window_that_survives` with
`assert "until CL-02" not in APP_SOURCE`, which is the shape that would have caught this one.

---

### CR-07: 03-01 edited both of Phase 2's WR-11 tests and left them proving nothing

**File:** `tests/broker/test_publish_confirm_failures.py:260-297`,
`tests/broker/test_enqueue_reaches_a_committed_row.py:256-268`

**Issue:** Phase 2's review named these two as *"tests that pass while proving materially less than
their names and docstrings claim"*. 03-01 touched both files heavily (+300 and +112 lines) and
edited the first test's body directly — adding the `fallback=` argument and raising the timeout
from 10 to 15 — without adding an assertion.

`test_enqueue_returns_normally_through_every_failure_branch` still ends:

```python
            for index in range(3):
                assert enqueue(gateway_draft(call_id=f"cal_{index:026d}")) is None

            deadline = asyncio.get_running_loop().time() + 15
            while ... and not handoff().empty():
                await asyncio.sleep(0.05)

            stopping.set()
            await asyncio.wait_for(publisher, timeout=15)
```

`enqueue` is annotated `-> None` and every branch ends in a bare `return`, so `is None` cannot
fail. Nothing after it asserts anything. Its docstring still says *"INT-018 across all three
reasons at once"* while the fixture provokes one (`unroutable`, via `UNBOUND_ROUTING_KEY`).

It is now **weaker relative to its neighbours than it was in Phase 2**, because 03-01 rewrote the
three siblings immediately above it — `test_unroutable_is_counted_and_the_record_falls_back`,
`test_nacked_…`, `test_timeout_…` — to assert `publish_failed_total`,
`fallback_direct_write_total` and `metadata_dropped_total` deltas. This test drives three records
through that same fallback machinery and asserts none of it. A regression in which the fallback
silently stopped writing, or in which `publish_failed_total` stopped moving, leaves it green.

`test_enqueue_returns_normally_with_no_broker_running` is unchanged and still claims *"INT-018's
contract at its hardest branch: there is no broker at all"* while testing `put_nowait` on an empty
queue — the easiest branch. The phase did build the real assertion,
`test_a_broker_that_was_never_reachable_still_produces_durable_records`, which is excellent; the
misleading test and its docstring were left standing beside it.

**Fix:** for the first, assert what the siblings assert — the fallback ran and nothing was lost:

```python
    before = _fell_back_value(), _dropped_value(), _counter_value("unroutable")
    ...
    assert _fell_back_value() == before[0] + 3
    assert _dropped_value() == before[1], "the broker refused; PostgreSQL did not"
    assert _counter_value("unroutable") == before[2] + 3
```

and either exercise all three reasons or rename the test to the one it drives. For the second,
rename to `test_enqueue_buffers_without_a_publisher_and_returns` and point its docstring at
`test_broker_unreachable_fallback.py` for the branch it claims.

---

### CR-08: `lifespan`'s teardown can still skip `reset_handoff()` and `engine.dispose()` — and 03-01 put a statement the next lifespan depends on inside that block

**File:** `src/prope/app.py:310-324`, `src/prope/app.py:270-283`

**Issue:** Phase 2's WR-02 recorded that an exception out of `_stop_publisher` skips the rest of
the `finally`. The shape is unchanged, and 03-01 added a third statement to it:

```python
    finally:
        stopping.set()
        await _stop_publisher(application)
        reset_handoff()
        await engine.dispose()
        log.info("app.stopped")
```

`_stop_publisher` has two raise sites that `suppress(TimeoutError, asyncio.CancelledError)` does
not cover: `asyncio.wait_for` re-raising anything else the supervise task raised, and
`await stack.aclose()` unwinding a channel and connection that may already be broken — which is the
state a shutdown after a broker outage is in.

`reset_handoff()` is not optional bookkeeping. `drain_handoff_on_stop` calls `queue.shutdown()`,
which is one-way for the queue object, and `handoff()` caches in a module global — so a lifespan
that ends without the reset leaves **every subsequent `enqueue()` in that process taking the
`QueueShutDown` branch and counting a drop, forever**. The phase knows this: it is written out at
`reset_handoff`'s docstring and at the `finally` itself, and
`test_two_consecutive_lifespans_in_one_process_both_enqueue` exists specifically to prove the
second lifespan is not poisoned. That test drives the clean path only. The statement it depends on
sits behind a call that can raise.

**Fix:** the same isolation Phase 2 proposed, now with three things to protect instead of two:

```python
    finally:
        stopping.set()
        try:
            await _stop_publisher(application)
        except Exception as error:
            # A-046: the class, never the message — at this depth it can quote the
            # broker URL. A teardown failure must not cost the handoff reset: the
            # queue is shut down one-way and a process that skips this counts a
            # drop on every later enqueue().
            log.warning("app.stop_failed", reason=type(error).__name__)
        finally:
            reset_handoff()
            await engine.dispose()
            log.info("app.stopped")
```

and isolate `stack.aclose()` from the publisher wait inside `_stop_publisher` for the same reason.

---

### CR-09: none of the phase's six UNCONFIRMED adoptions reached `ORCHESTRATION-DECISIONS.md`, and `WINDOWS.md` has no phase-3 row

**File:** `.planning/ORCHESTRATION-DECISIONS.md:16`, `.planning/WINDOWS.md:1-24`,
`.planning/phases/03-durability-idempotency-and-no-read-path/deferred-items.md:15-116`

**Issue:** ORCHESTRATION §9 items 7 and 8 are definition-of-done clauses. Both are unmet with all
seven commits landed.

`deferred-items.md` Part 1 records **six** decisions adopted without a human: the fallback-only job
on a dead broker (and its consequence — such a process never publishes until restarted),
`MAX_BODY_BYTES = 256 KiB`, `metadata_dropped_total` no longer counting dead-letters (which changes
what an existing **page** means), `MAX_RETENTION_DAYS = 3650`, `prope_report` keeping its `SELECT`
on `ledger.call_body`, and the load-test split. Its own header says each *"belongs on `03-UAT.md`
as a numbered human-verification item and in `.planning/ORCHESTRATION-DECISIONS.md` as one row"*.
That file still reads:

```
| — | — | — | *(none yet — phase 3 planning in flight)* | — | — | — |
```

`WINDOWS.md` still has `open_count: 4` and four Phase 2 rows. Phase 3 produced at least three
candidates: the `performance_requirements` throughput assertion that is red (CR-10 below), the
two-registry split that leaves two alerts unable to fire (CR-04), and the cold-workspace blind spot
that `oldest_body_age_seconds` **inherits** rather than catches — the last of which is a genuine
new fact, because Broken Window #3 was recorded on the assumption the gauge would close it and
03-04 corrected that assumption in `ObservedWorkspaces`' own docstring.

This is the mechanism by which one-way decisions taken on the user's behalf get adjudicated. Two of
the six touch things the four non-negotiables care about — a full-read credential on the body store,
and a change to what a page means.

**Fix:** the verifier or the bookkeeping pass appends six rows to
`ORCHESTRATION-DECISIONS.md`'s phase-3 table (phase, plan, decision, rejected alternative,
reversibility, `UNCONFIRMED`), copies them into `03-UAT.md` as numbered items, and appends the
three windows to `WINDOWS.md` in both the table and the JSON block with `open_count` corrected to
7. None of it requires judgement beyond what `deferred-items.md` already states.

---

### CR-10: a declared `performance_requirements` clause is failing, its assertion is red, and nothing in the default gate says so

**File:** `tests/load/test_fifty_rps_for_ten_minutes.py:124-131`,
`tests/load/test_fifty_rps_for_ten_minutes.py:688-695`, `docs/brainstorm/open_questions/OQ-085.md`

**Issue:** `throughput >= RECOVERY_RECORDS_PER_SECOND` (500 records/sec) is red. 03-06 measured
189 and 212; 03-07's N+1 fix moved it to 450 and 448. The assertion was not lowered, not marked,
not deleted — that part is exactly right, and the discipline is worth saying out loud. But:

- the whole file is `pytest.mark.skipif(not os.environ.get("PROPE_RUN_LOAD"))`, so
  `uv run pytest -q` reports `414 passed, 1 skipped` and the shortfall is invisible at the gate
  ORCHESTRATION §9 item 2 is written against;
- ORCHESTRATION §9 says *"A red test is never 'expected'. If a test cannot pass in this phase, the
  plan must have said so in advance and routed it to a named later phase, the way phase 2 routed
  CL-01 and CL-02 to phase 3."* OQ-085 routes the **question** to the user (`owner: user`,
  `blocks_build: false`). No phase owns the **number**;
- §9a makes this milestone-closing phase responsible for auditing the lock file's
  `performance_requirements` clause by clause and either asserting each one or *routing it
  explicitly with a named owner*. This one is asserted and failing, which is neither.

The engineering here is honest and the finding is about where the failure is visible from. A gate
that is green while a declared clause is failing is the condition under which phase 12 discovers
the shortfall by accident.

**Fix:** two lines of bookkeeping and one decision.

1. Append the shortfall to `WINDOWS.md` as an open window naming the file, the constant, the two
   measurements (450/448 against 500) and OQ-085, so it is visible without opening a phase folder.
2. Name an owner in `deferred-items.md`: either "M1 sign-off is blocked on OQ-085" or a phase — the
   deployment/scale phase is the natural home, since the honest caveat at the assertion is that the
   run drives the publisher and the drain on one event loop while the deployment shape gives the
   drain a process to itself.
3. Record in `03-UAT.md` that the ROADMAP SC5 evidence is a **skipped** test, so the human
   verifying SC5 knows to run `make load` rather than reading the suite summary.

---

### CR-11: the retention route's positive control reads state back through application code

**File:** `tests/integration/test_management_routes.py:681-701`

**Issue:** `test_the_largest_window_the_bound_allows_still_takes_effect` asserts the write landed by
calling `read_retention_window(app_sessionmaker, WORKSPACE_A)` — application code, on the
policy-bound role, and the same module the route it is testing wrote through. Its sibling
`test_a_non_positive_window_is_refused_and_stores_nothing` reads `COUNT_RETENTION_ROWS` through
`migrate_engine`, which is the house rule, and the new `422` test above it does the same.

The residual is small — a reader that shared a defect with the writer would have to fail in a way
that produced exactly `timedelta(days=3650)` — but this is the file's own established pattern and
this is the one test in it that does not follow it.

**Fix:**

```python
    async with migrate_engine.begin() as connection:
        stored = (
            await connection.execute(
                text(
                    "SELECT retention_window FROM ledger.workspace_retention "
                    "WHERE workspace_id = :ws"
                ),
                {"ws": WORKSPACE_A},
            )
        ).scalar_one()
    assert stored == timedelta(days=MAX_RETENTION_DAYS)
```

## Info

### CR-12: `worker`'s broker connect is still unbounded and still outside its `try`

**File:** `src/prope/worker.py:629-636`

**Issue:** Phase 2's WR-08, unchanged, in a file this phase rewrote substantially (+317 lines):

```python
    connection = await build_connection(settings.broker_url)
    try:
        async with connection:
            ...
    finally:
        log.info("worker.stopped")
        await engine.dispose()
```

`build_connection` is outside the `try`, so an unreachable broker leaks the engine, and there is no
timeout — a broker host that resolves and does not answer holds `_amain` open indefinitely while
the process-level compose healthcheck reports it healthy. `prope.app` guards exactly this and
argues for it at `BROKER_CONNECT_TIMEOUT_SECONDS`; `worker` inherits none of the reasoning.

Filed as info rather than warning because it was not routed to this phase and the fix is Phase 2's
verbatim: lift `build_connection` inside the `try`, wrap it in
`asyncio.wait_for(..., timeout=BROKER_CONNECT_TIMEOUT_SECONDS)`, and state at the constant whether
crashing on an absent broker is intended (defensible — the drain is the worker's reason to exist)
given that the retention sweep would still have useful work to do.

## Known and deliberate

These are recorded decisions, not defects. They are separated out so the list above stays
credible.

- **`/metrics` is unauthenticated and `unpriced_total` carries `provider_config_id`.** A
  `provider_config_id` resolves to exactly one workspace, so the exposition surface carries
  tenant-scoped identifiers with no session in front of it. Raised as **OQ-023** at the moment it
  became concrete, with the alternative (dropping a declared label) named and refused. The
  deployment stack owns no milestone, so nothing in this roadmap places Caddy in front of it —
  which is PITFALLS gap 4 and not this phase's.
- **`prope_report` keeps `SELECT` on `ledger.call_body`.** Asserted deliberately in
  `tests/security/test_report_role_can_read_bodies.py`, routed to **OQ-025** clause 2, with the
  class-level question (should `grant_table`'s `report_select` default be `False` for a table
  declared to have no reader) raised rather than answered locally. The three reasons for leaving it
  are recorded in order of weight and the "do nothing and mention it nowhere" option is refused in
  writing.
- **`ledger.workspace_retention` is a sixth table where the lock file names five** — OQ-018,
  inherited from Phase 2, unresolved by design.
- **`/metrics` is served and declared in no lock file's `apis.exposes`** — OQ-026 clause 2, with
  `interfaces.md`'s own note that step 6 should have added it.
- **Eight alert rules ship where the plan's table listed seven.** 03-04 restored
  `LedgerDuplicateCallIds` because the lock file declares it and the plan's table dropped it. The
  lock file outranks the plan (§1); nothing was weakened.
- **AC-12's write-lag clause is asserted over two windows rather than the whole run.** The
  deliberately injected 60 s consumer outage is 10% of the run by construction and is not AC-12's
  stated condition. The whole-run share is computed and printed beside the asserted one, and a
  second assertion floors the asserted windows at 75% of the run so a boundary error cannot shrink
  the clause to nothing. Declared as 03-06 deviation 1.
- **The load split.** `test_enqueue_off_response_path.py` runs unmarked in the default suite and
  carries CL-12's p95 and zero-drop claims at the lock file's stated 80% depth; the ten-minute run
  is skipped rather than deselected so it prints an `s` and its reason. `addopts` is deliberately
  absent so `uv run pytest -q` still means what §9 says it means.
- **`MAX_BODY_BYTES = 256 KiB` and `MAX_RETENTION_DAYS = 3650`** are product-visible limits adopted
  UNCONFIRMED, both argued from stated arithmetic rather than rounded.
- **OQ-085's id.** It skips 075–084 because ids 027–074 were allocated by the phase 4–9 planning
  commits; `deferred-items.md` records that the orchestrator allocated 085 for plan 03-07. Not a
  numbering defect.
- **`ruff format --check` is not a gate** (Broken Window #1) and `make check` inherits its failure.
  Not this phase's to fix.

## Carried forward from Phase 2 — still open, still unowned

ORCHESTRATION §4 routed only CR-01 and CR-02 to this phase. The remaining Phase 2 warnings were
never assigned an owner, and several now sit in code this phase rewrote. Listed so the next phase
that touches these files inherits a register rather than a re-discovery:

| Id | Subject | State after Phase 3 |
|---|---|---|
| WR-01 | `/readyz`'s timeout does not cover `engine.connect()` | Unchanged (`app.py:405-418`) |
| WR-02 | lifespan teardown can skip `engine.dispose()` | **Worse** — see CR-08 |
| WR-03 | unsupervised background publisher | **Closed** by D-32; both branches go through `supervise` and a test asserts it |
| WR-04 | drain's transient backoff sleep is not interruptible and is per group | Unchanged (`drain.py:500`) |
| WR-05 | `_refuse_unrepresentable_money` checks scale but not precision | Unchanged |
| WR-06 | `LOGGABLE_FIELDS` is read by no code | Unchanged — still zero non-docstring readers repo-wide |
| WR-07 | `request_id` is logged and is not on `LOGGABLE_FIELDS` | Unchanged |
| WR-08 | `worker`'s unbounded broker connect | Unchanged — see CR-12 |
| WR-09 | `run_drain`'s `finally` can mask the exception that killed it | Unchanged (`drain.py:525-526`) |
| WR-10 | two tenant-scoped statements omit the explicit `workspace_id` predicate | Unchanged |
| WR-11 | two tests prove less than their names claim | Unchanged — see CR-07 |
| WR-12 | `enqueue()`'s catch-all increments one counter but not the other | **Partly.** The new `QueueShutDown` branch (`enqueue.py:356-371`) correctly increments both. The bare `except Exception` (`enqueue.py:372-383`) still increments `metadata_dropped_total` alone, so `sum(enqueued_total)` still under-counts records offered on that branch |
| WR-13 | `models.py`'s docstring describes a query surface that does not exist | Unchanged |
| WR-14 | dead branch in `_stop_publisher` | Unchanged — folded into CR-03's fix |
| WR-15 | docstrings reference `RANGED_PRICE_ROWS` | Unchanged |
| WR-16 | `call_id` crosses the broker with no character-class gate | Unchanged |

---

_Reviewed: 2026-08-11_
_Reviewer: Claude (orchestration reviewer)_
_Depth: standard_
