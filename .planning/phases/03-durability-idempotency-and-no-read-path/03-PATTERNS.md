# Phase 3: Durability, idempotency, and no-read-path - Pattern Map

**Mapped:** 2026-08-10
**Files analyzed:** 7 new / 11 modified
**Analogs found:** 17 / 18 (12 exact, 5 role-match, 1 no analog) — plus **three sub-shapes inside
role-matched files that have no precedent anywhere in this repository**: a Core
`insert(...).on_conflict_do_nothing().returning(...)`, a `prometheus_client` `Histogram` or `Gauge`,
and an HTTP route with no session dependency inside `/api/v1`'s neighbourhood. Those three are called
out where they land.

> **Read this as "copy from here", not "follow this spirit".** Every excerpt below is real text in
> this repository at the line numbers given, read in full rather than inferred from a filename.
>
> **This phase is unusual in one way and the planner should notice it before anything else: Phase 3
> is mostly EDITS to files Phase 2 wrote, not new files.** Eleven of the eighteen entries below are
> modifications. That changes what "match the pattern" means — the analog for
> `enqueue.py`'s new fallback call is `enqueue.py` itself, and the risk is not writing something
> foreign, it is leaving a Phase-2 docstring standing that describes a gap this phase closed. Several
> of the paragraphs excerpted below are **this phase's to delete or rewrite**, and each one is marked
> `[REWRITE]` where it appears. A module docstring that still says "Phase 2 counts and drops" after
> the fallback ships is a lie in the most load-bearing prose in the codebase.
>
> The single most transferable property of the existing code remains: **the module docstring carries
> the *why* at length, naming the ADR / assumption / OQ and the rejected alternative.** Treat the
> docstring as a deliverable.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/prope/call_ledger/fallback.py` | service (injected callable) | request-response (single-row write) | `src/prope/call_ledger/seams.py` — `price_usage` | **exact** |
| `src/prope/call_ledger/writer.py` (**mod**) | repository | batch write + aggregate | `retention_settings.UPSERT_RETENTION_WINDOW` / `writer.UPSERT_WORKSPACE_SPEND` | role-match |
| `src/prope/call_ledger/enqueue.py` (**mod**) | service | pub-sub (publish) | the same file's Phase 2 shape | **exact** |
| `src/prope/call_ledger/drain.py` (**mod**) | worker job | event-driven → batch | the same file | **exact** |
| `src/prope/call_ledger/schemas.py` (**mod**) | model | validation | `schemas.PageRequest` (`le=` as a cap, not a clamp) | **exact** |
| `src/prope/call_ledger/seams.py` (**mod**) | service | request-response | the same file's fail-open branch | **exact** |
| `src/prope/observability.py` (**mod**) | config | — | its own five `Counter`s | role-match |
| `src/prope/app.py` (**mod**) — `/metrics` | controller | request-response | `app.healthz` / `app.readyz` | role-match |
| `src/prope/app.py` (**mod**) — supervised publisher | entrypoint | process | `worker.run_worker`'s `supervise({...})` | **exact** |
| `src/prope/worker.py` (**mod**) — depth-gauge job | worker job | interval | `worker.expired_body_deletion_job` + `supervisor.interval_job` | **exact** |
| `src/prope/worker.py` (**mod**) — `oldest_body_age` | worker job | aggregate read per workspace | `worker.sweep_expired_bodies`'s enumerate-then-loop | role-match |
| Prometheus rules file (path is the planner's) | config | declaration | `src/prope/broker/topology.py` — declared constants + read-back test | role-match |
| `tests/architecture/test_no_body_read_path.py` | test | — | `tests/architecture/test_no_sql_interpolation.py` | **exact** |
| `tests/architecture/test_route_table.py` (**mod**) | test | — | the same file | **exact** |
| `tests/broker/` — chaos (broker outage) | test | event-driven | `tests/broker/test_publish_confirm_failures.py` | **exact** |
| `tests/…` — redelivery idempotency | test | event-driven → batch | `test_drain_failure_classification.py::test_unacknowledged_messages_are_redelivered_after_a_consumer_restart` | **exact** |
| `tests/…` — the load claim (CL-12) | test | — | — | **no analog** |
| `tests/conftest.py` (**mod**) | test rig | fixture | the same file's `purge_queues` / `truncate_ledger` | **exact** |
| `pyproject.toml` (**mod**) — `markers` | config | — | the file's own pin comments | **exact** |

---

## Pattern Assignments

### `src/prope/call_ledger/fallback.py` (new — service, injected callable)

**Analog: `seams.py::price_usage` (`seams.py:207-261`), and the match is exact.** That function is
the repository's one existing example of *"take a sessionmaker, open the tenant transaction yourself,
convert nothing, call `write_records`, write no SQL of your own"* — which is D-27's whole shape.

```python
async def price_usage(
    sessionmaker: async_sessionmaker[AsyncSession],
    run_id: str,
    usage_rows: Sequence[EvalUsageRow],
) -> None:
    """INT-019. Price and count one eval run's usage. Raises, or commits.

    **The signature takes a ``sessionmaker``, never a session** (D-19). ...

    **It writes no SQL of its own.** Every row is converted to a
    ``CallRecordDraft`` and handed to ``write_records`` ...
    """
    ...
    async with workspace_transaction(sessionmaker, workspace_id) as session:
        await write_records(session, drafts)
```

→ D-26/D-27's fallback is `async with workspace_transaction(sessionmaker, record.workspace_id) as
session: await write_records(session, [record])` and nothing else. **`write_records` takes a
`Sequence`** (`writer.py:208-213`) — a one-element list, not a new single-record overload. There is
one implementation on purpose (`writer.py:3-7`).

**The three refusal contracts on this path are all different, and the plan must state which one
`fallback.py` holds.** The repository already has both poles written down:

| Function | Contract | Where it says so |
|---|---|---|
| `enqueue` | **never raises, ever** | `enqueue.py:3-8`, `enqueue.py:103-117` |
| `price_usage` | **raises**, so evaluation can record a run error | `seams.py:12-24` |
| `write_records` | raises `ValueError` for a batch the encoding cannot represent | `writer.py:214-223` |

The fallback sits under `run_publisher`, which is a supervised background task, not a caller's span.
`run_publisher`'s own promise is at `enqueue.py:270-272` — *"Nothing raised by a single record's
publish escapes this loop. A publisher that dies on one bad record takes the whole handoff with
it"* — so the fallback's raise is caught **there**, and D-30's third surviving
`metadata_dropped_total` site ("a fallback that itself raised") is that catch. Write that at the
`try` rather than only in the plan.

**The A-046 declaration is not optional on a new module.** Every module in `src/prope/call_ledger/`
states its logging posture in its own docstring — `writer.py:37-39`, `enqueue.py:26-34`,
`drain.py:30-34`, `envelope.py:40-42`, `retention_settings.py:38-41`, `topology.py:35`,
`connection.py:21-23`. `fallback.py` writes a body-carrying record to PostgreSQL and logs the drop,
so it needs the paragraph more than most.

**Injected-callable typing.** The repository's idiom for "a function shaped like this arrives from
the composition root" is a module-level `Callable` alias with a `#:` comment saying what it is
awaited with:

```python
#: What ``retention_for`` must look like: awaited with ONE POSITIONAL ARGUMENT,
#: the ``workspace_id``, returning that workspace's retention window.
RetentionResolver = Callable[[str], Awaitable[timedelta]]          # drain.py:103-105

#: What a workspace enumerator must look like: awaited with nothing, returning
#: the workspace ids one sweep pass must visit.
WorkspaceEnumerator = Callable[[], Awaitable[Sequence[str]]]       # worker.py:115-119

#: What a job is: a zero-argument coroutine factory. ...
Job = Callable[[], Awaitable[None]]                                # supervisor.py:79-83
```

→ `FallbackWriter = Callable[[CallRecordDraft], Awaitable[None]]` gets the same treatment, and the
`#:` block must state the argument count, because `drain.py:345-352` and `worker.py:192-203` are two
pages of prose about the last time a resolver's arity was got wrong at a composition root. That is
the precedent D-26's *required keyword argument with no default* is guarding against, and the plan
should cite it.

---

### `src/prope/call_ledger/writer.py` (modified — D-33/D-34/D-35, the upsert)

**This is the highest-risk edit in the phase and it has only a partial analog.**

**What has an analog: the `ON CONFLICT` idiom.** Two exist and they take opposite branches, on
purpose, and the plan should name which one it is copying:

```python
# retention_settings.py:83-95 — DO UPDATE, because "set this window" has one outcome
ON CONFLICT (workspace_id) DO UPDATE SET
    retention_window = EXCLUDED.retention_window, ...

# writer.py:136-150 — DO UPDATE with a WHERE that makes a conflicting row NOT MATCH,
# so rowcount 0 is a real refusal rather than a no-op (T-02-13 / WARN-2)
ON CONFLICT (workspace_id, period_month) DO UPDATE SET
    call_count = ledger.workspace_spend.call_count + EXCLUDED.call_count, ...
WHERE  ledger.workspace_spend.currency IS NULL
   OR  EXCLUDED.currency IS NULL
   OR  ledger.workspace_spend.currency = EXCLUDED.currency
```

→ D-33 takes **neither**: `DO NOTHING … RETURNING call_id`. The rowcount-as-refusal reading at
`writer.py:379-401` is the pattern to *not* copy blindly — under `DO NOTHING` a zero rowcount means
"already there", which is the ordinary case, not a refusal. Say so at the statement, because the
neighbouring statement in the same file says the opposite about its own rowcount and a reader will
carry the reading across.

**What has NO analog anywhere in `src/`: a Core `insert()` construct.** Every statement in `src/`
today is `sqlalchemy.text()` — verified by the AST walk in
`tests/architecture/test_no_sql_interpolation.py:53-74`, which finds `text()` calls in `writer.py`,
`pricing.py`, `repricing.py`, `retention.py`, `retention_settings.py`, `seams.py`, `api.py`,
`db/session.py` and `app.py`. `models.py` declares the six tables as Core `Table` objects
(`models.py:56-163`) and **nothing consumes them** — `models.py:26-28` says they are *"consumed with
`select()`"* and no `select()` exists. So D-33's
`sqlalchemy.dialects.postgresql.insert(models.call_record)` is the first use of the Core layer in
this project.

Three consequences the plan must state rather than discover:

1. **`test_no_sql_interpolation.py` does not walk Core constructs.** Its parametrised test
   (`:77-98`) inspects `text(...)` arguments only. A Core `insert()` is not a `text()` call, so it
   passes the gate **by not being seen**, not by being safe. That is not a hole — the construct binds
   its own parameters and there is nothing to interpolate — but the gate's own guard test,
   `test_the_walk_actually_found_statements_to_check` (`:101-112`), asserts `found >= 5`, and moving
   statements out of `text()` moves that count. Re-run it; do not raise the threshold to make it pass.
2. **`ALLOWED` stays empty** (`test_no_sql_interpolation.py:36-38`): *"A legitimate exception is an
   entry in `ALLOWED`, never a weakening of the rule."* The Core construct needs no entry.
3. **`models.py`'s drift test starts mattering.** `tests/architecture/test_schema_invariants.py`
   asserts every declared table has a live counterpart whose columns are a superset
   (`models.py:16-19`). Until this phase that was insurance on an unused declaration; from D-33 it
   guards the statement that writes every call record in the system.

**The month-bucket inversion is a structural change, not a line change.** Today the buckets are
accumulated inside the per-draft loop (`writer.py:338-351`) and the inserts happen after
(`writer.py:355-357`). D-33 inverts that: insert first, read the returned `call_id` set, then bucket
only the rows in it. The currency-conflict raise at `writer.py:345-350` moves with the buckets, and
its message — which names both currencies and A-107 — is copied, not rewritten.

**`WriteResult` grows a fifth field, and the docstring rule is what governs it**
(`domain.py:183-193`):

> ``unknown`` counts records whose provider returned no usage object … It is derived from
> ``usage_status``, never by asking whether a token column is NULL

→ `duplicates` (D-35) is derived from *"rows offered minus `call_id`s returned"* and the docstring
says exactly that. It is a `@dataclass(frozen=True, slots=True)` with defaults on every field
(`domain.py:183-203`), so adding one breaks no existing construction site.

**D-40's `missing_version_id_total` refusal follows `EvalUsageRow.__post_init__`'s shape**
(`seams.py:147-169`) — a loop over `(field_name, reason)` pairs raising a sentence that names the
field, the constraint and why the record is not evidence anybody can act on. And it follows
`writer.py:274-287`'s rule: **name what is missing; never substitute.**

---

### `src/prope/call_ledger/enqueue.py` (modified — D-26, D-29, D-31, D-41)

**The analog is the file itself, and four of its paragraphs are `[REWRITE]`.**

`enqueue.py:16-24` is the Phase 2 gap declaration:

> **The Phase 2 gap this module creates deliberately, stated at the site.** On a full handoff and on
> every failed confirm, this module COUNTS AND DROPS. There is no direct-write fallback (CL-01, Phase
> 3) and no idempotent upsert on `call_id` (CL-02, Phase 3). … `:func:_classify_publish_failure` is
> the exact line Phase 3's direct write goes on.

and `publish_record`'s own docstring names its successor (`enqueue.py:181-184`):

> **Phase 3's direct-write fallback goes on the failure branch below.** Not beside it, not in the
> caller: at the point where this function has established that this specific record did not reach
> the broker … CL-01 replaces the `return False` with a write through `write_records`.

→ Both `[REWRITE]`. The same obligation applies to `app.py:46-51` and `app.py:243-250`
(`readyz`'s Phase-2-consequence paragraph), `observability.py:14-32`, `drain.py:12-21` in
`test_drain_failure_classification.py`, `writer.py:3-4`, `seams.py:64-71`, and
`retention_settings.py:12-15`. **`tests/architecture/test_route_table.py:249-262` asserts four of
those strings are present in `app.py`** — `"degraded-and-counted"`, `"CL-01"`,
`"metadata_dropped_total"`, `"records genuinely"` — so rewriting that paragraph is a **test edit in
the same change**, and the test's own docstring explains why it exists: *"a reasoning obligation that
is only reviewed is an obligation somebody deletes in a tidy-up."* Keep the assertion and change what
it asserts; do not delete it.

**D-26's four failure cases live at three `return False` sites.** `enqueue.py:200-211` is the
`except (DeliveryError, TimeoutError)` branch, which produces `unroutable` / `nacked` / `timeout` via
`_classify_publish_failure`; `:228-252` is the defence-in-depth branch that inspects a non-`Ack`
confirmation and produces `unroutable` or `nacked` a second way; and `:212-226` is the bare
`except Exception`, commented *"A closed channel, a dead connection, a broker that was never
running"*. **That last one is the branch D-26 calls the mundane case** — the one an ordinary
`docker compose up -d` produces — and it deliberately does **not** touch `publish_failed_total`, so
the label set stays closed at three (`:214-217`). The fallback goes on all three sites; the label set
does not grow.

**`_classify_publish_failure` (`enqueue.py:146-169`) does not change.** Its docstring is the model
for how a closed label set is defended — *"this function is the only place a value is chosen, so a
fourth cannot appear by accident"* — and D-28's `body_dropped_total{reason}` conflict is the same
shape one metric over. Write D-28's third value the same way: one function, one place, and the OQ
cited at the constant.

**The size cap (D-29) goes inside `enqueue()` and must not raise.** `enqueue()`'s two `except`
blocks (`:118-141`) are the template — count, log with `reason` from a closed set, `return`. Note
that the second is `except Exception` with the comment *"INT-018 says never, and never includes the
failure nobody predicted"*: a `str.encode()` on a caller-supplied string can raise, and it must be
inside a branch that returns rather than propagates. The counter pair at `:121-122` is also the
template for D-29's *"does `enqueued_total` gain an `oversize` outcome"* discretion item — the
existing comment explains precisely why two counters increment on one event.

**D-41's clock read.** `occurred_at` is stamped at `enqueue.py:186` inside `publish_record`. Moving
it into `enqueue()` gives that function its **first clock read**, and this repository has a strong
convention against clock reads that the plan must be explicit about breaking:
`retention.py:14-17` (*"`now` is an argument and never a clock read"*), `writer.py:19-23` (*"Nothing
in this module reads a clock"*), `retention_settings.py:33-37`, `worker.py:268-270` and
`api.py:225-233` (both named `_utc_now`, both documented as *"the one clock read in this
process/module, in the one place that may read it"*). → `enqueue()` becomes call-ledger's third
sanctioned clock site and the docstring says so in those words, naming `write_lag_seconds` as the
reason.

---

### `src/prope/call_ledger/drain.py` (modified — D-30, D-35, D-36)

**D-30 is a removal, and removals are the ones that get skipped.** The two increments are at
`drain.py:249` (inside `_parse`, for an invalid envelope) and `drain.py:313` (inside
`_retry_group_one_at_a_time`, for a refused write). Both sit immediately above a
`log.warning(..., reason=...)` and a `reject(requeue=False)`. **Delete the counter line, keep the log
line**, and keep the `reject` comment at `:320-322` (*"a classic queue has no delivery limit"*) —
that reasoning is untouched by this phase.

**D-36 rewrites a docstring paragraph, not a branch.** `classify_write_failure`'s `IntegrityError`
bullet (`drain.py:133-140`) currently reads:

> - an `IntegrityError`: a CHECK the record violates, and — the one that matters this phase — a
>   **unique-key violation on `call_id`**. … **That is a named Phase 2 gap, not an accident**

→ `[REWRITE]`, and the branch itself (`:154-155`) stays `PERMANENT`. **The default is not
touched** — `:143-150` argues it from T-02-06 and the absence of `x-delivery-limit`
(`topology.py:30-33` states the same cost), and `test_an_unrecognised_failure_defaults_to_permanent`
(`test_drain_failure_classification.py:87-96`) asserts it.

**D-35's `redelivered_total` reads `AbstractIncomingMessage.redelivered`.** The property is already
used, as an assertion, at `test_drain_failure_classification.py:238`. The counter's increment site is
a drain-side decision; note that `_parse` (`drain.py:229-258`) is the first place every message is
individually handled and is before any transaction opens, which is the same reason the envelope gate
lives there (`:234-238`, T-02-01).

**Where the observer seam already is.** `on_window` (`drain.py:167-169`, `:358-363`) is awaited after
a window's groups have committed and acked. It is the existing hook for a write-lag histogram
observation, and the seam rules are stated at `retention.py:131-142`: *"keyword-only, defaults to
`None`, and when it is `None` the branch is not taken: the production call path supplies no callback
and behaves exactly as it would without the parameter."* → **A metric is not an observation seam.**
If `write_lag_seconds` is observed inside the drain it is production behaviour and belongs on the
production path, not behind `on_window`; if the plan wants it behind the seam it must say why.

---

### `src/prope/call_ledger/schemas.py` (modified — D-37, CR-01)

**Exact analog, in the same file, ten classes up.** `PageRequest.limit` (`schemas.py:207`) is a
bound expressed as `Field(le=...)` with the reason written above it (`:189-203`):

```python
class PageRequest(BaseModel):
    """A-045's cursor pagination: ``limit`` 50 by default, 200 at most.

    **A cap and not a suggestion.** ``le=MAX_PAGE_LIMIT`` makes ``limit=201`` a
    ``422`` rather than a silently clamped page, for ``set_retention_window``'s
    reason one table over: a request quietly corrected into one the caller did
    not make leaves them believing it took effect. ...
    """

    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
```

→ `RetentionSet.retention_days` gains `le=…` and inherits that argument verbatim, including the
consequence: it is a `422` through the A-045 envelope, not a clamp.

**The paragraph immediately above it is the one D-37 must edit rather than contradict**
(`schemas.py:386-390`):

> **There is no lower bound on this field and that is deliberate.**
> `ck_workspace_retention_window_is_positive` is what refuses a zero or negative window, at the
> engine, and `set_retention_window` surfaces the refusal rather than clamping. Re-checking it here
> would put the guarantee in two places, and this repository's rule is that the database owns it

→ That paragraph stays true for the *lower* bound and must not be deleted. D-37 adds the asymmetry
beside it: the upper bound cannot be a `CHECK`, because `api.py:720` evaluates
`timedelta(days=payload.retention_days)` **before a statement exists**, and `OverflowError` is an
`ArithmeticError` that `classify_write_failure` matches nowhere (`drain.py:152-165` — it falls to the
`PERMANENT` default at `:165`). Write the asymmetry at the field so a later reader does not tidy one
bound into the other's home.

**Two constants, not literals.** `MAX_PAGE_LIMIT` exists at `schemas.py:116-117` with the comment
*"Written as constants because the route-table and pagination tests assert the numbers, and a literal
in a `Field` is a number a test would have to restate."* → `MAX_RETENTION_DAYS = 3650` gets the same
treatment. And note that `ErrorCode` (`schemas.py:120-148`) is a closed `StrEnum` — a `le=` violation
renders as the **existing** `VALIDATION_FAILED` through `install_error_envelope`'s
`RequestValidationError` handler (`schemas.py:497-510`), so **no new `ErrorCode` member is needed**
and adding one would be a code the SPA's catalogue has never seen (`:122-128`, ADR-0053).

---

### `src/prope/observability.py` (modified — D-40, the eighteen metrics)

**Role-match at best.** Five `Counter`s exist (`observability.py:74`, `:84`, `:92`, `:101`, `:125`)
and they are the naming and commenting template. **No `Histogram` and no `Gauge` exists anywhere in
`src/` or `tests/`** — verified by grep; the only `prometheus_client` import in `src/` is
`from prometheus_client import Counter` at `observability.py:39`. `enqueue_duration_seconds`,
`write_lag_seconds`, `queue_depth`, `dlq_depth` and `oldest_body_age_seconds` are the first of their
kind here, and `03-RESEARCH.md` is the reference for their construction.

**The counter template, with everything that must be reproduced:**

```python
#: D-21's control. The ``reason`` label has exactly three values and the lock
#: file declares the set: ``unroutable`` | ``nacked`` | ``timeout``. They are the
#: three shapes a publisher confirm can fail in, and the publish path classifies
#: into exactly these and never invents a fourth.
publish_failed_total = Counter(
    "prope_call_ledger_publish_failed_total",
    "Publisher confirms that did not arrive as an ack, by reason.",
    labelnames=("reason",),
)
```

Four rules, each visible in the excerpt and each stated in the module docstring (`:1-33`):

1. **Name is the lock file's, verbatim**, `prope_call_ledger_*`, and the `_total` suffix stays on the
   name rather than being left to `prometheus_client`'s own suffixing.
2. **Every label's value set is closed and fixed in source**, and the `#:` block names the members.
   `enqueued_total`'s comment (`:69-73`) goes further and disambiguates a collision — *"`outcome`
   here is the fate of the HANDOFF, not the `Outcome` vocabulary"* — which is the level of care
   `ceiling_check_total{result}` needs, since `result` is a third vocabulary again.
3. **An unlabelled metric says why it is unlabelled.** `metadata_dropped_total` (`:98-100`) and
   `ceiling_failed_open_total` (`:115-117`) both do, and both give the same reason:
   *"the workspace whose check could not be evaluated is exactly the label ADR-0030 forbids."*
   → D-43's `oldest_body_age_seconds` reduction to one unlabelled gauge inherits that sentence.
4. **A counter that is also a control says what it controls.** `ceiling_failed_open_total:107-124` is
   the model: *"**An open-failing check nobody watches is an off switch**, so the mitigation for
   T-02-26 is this counter rather than the branch."*

**`LOGGABLE_FIELDS` is a positive allow-list and it is never inverted** (`observability.py:41-67`):

```python
#: The allow-list A-046 requires: the ONLY keys any publish-path or drain-path
#: log line may carry beside its event name. Positive, never a deny-list — a
#: deny-list of forbidden field names passes the first time a body is carried on
#: a field nobody thought to forbid, which is every field that has not been
#: invented yet.
LOGGABLE_FIELDS = frozenset({"event", "call_id", "workspace_id", "reason", "queue",
                             "delivery_tag", "group_size", "window_size", "job"})
```

The `job` entry (`:59-65`) is the precedent for *how* an entry is added: a `#:` sub-comment naming
which plan added it, which log line carries it, and why its values are a closed set. → Any new field
this phase logs (a shutdown-drain remainder count, a fallback outcome) gets the same block. **Note
that `LOGGABLE_FIELDS` is a declaration and nothing enforces it today** — the enforcement is
`test_publish_confirm_failures.py:198-237`, which provokes a real failure and greps every captured
log record and every metric label for a marker. That is the shape of the assertion, not a lint.

**Two `[REWRITE]` paragraphs in this file.** `:14-22` (*"Phase 2 wires four counters and nothing
else"* — there are five, and it says there is no `/metrics` endpoint) and `:24-32` (*"It will not
stay 0 in Phase 2"*). The second is the paragraph this phase earns the right to delete.

**Bounded cardinality is asserted, not intended.** `test_publish_confirm_failures.py:240-251` walks
`REGISTRY.collect()` for every `prope_`-prefixed metric and asserts `workspace_id` is in no label
set. Eighteen metrics must still pass it, and `unpriced_total{provider_config_id, upstream_model}` is
the one whose declared labels are closest to unbounded — the lock file declares them, so they ship,
but the plan should note the cardinality argument rather than let it pass silently.

**Reading a metric in a test goes through `REGISTRY.get_sample_value`, with a `or 0.0` for the
never-incremented case** (`test_publish_confirm_failures.py:55-63`,
`test_ceiling_refuses_evals_only.py:117`) — and always as a **delta** (`before`/`after`), never an
absolute, because the registry is process-global and the suite shares one process. D-40's *"all
eighteen are defined at import"* is exactly what makes `get_sample_value` return `0.0` instead of
`None` for a metric nothing has touched, and the plan should say that is the point.

---

### `src/prope/app.py` (modified — D-32 supervision, D-39 `/metrics`)

**D-32: the analog is `worker.run_worker` (`worker.py:318-339`), and it is exact.**

```python
    async def call_record_drain_job() -> None:
        async with connection.channel() as channel:
            await run_drain(channel, sessionmaker, stopping=stopping, retention_for=retention_for)

    await supervise(
        {
            JOB_CALL_RECORD_DRAIN: call_record_drain_job,
            JOB_EXPIRED_BODY_DELETION: expired_body_deletion_job,
        },
        stopping,
    )
```

→ A job is a **name constant plus a zero-argument closure** (`supervisor.py:79-83`), and the name
constants are module-level and documented as `LOGGABLE_FIELDS`' `job` values
(`worker.py:73-80`). `app.py` gets `JOB_CALL_RECORD_PUBLISH = "call_record_publish"` (or the
planner's name) in the same shape.

**The one difference the plan must handle: `supervise` blocks until every job returns**
(`supervisor.py:193-209`), and `app.py`'s lifespan cannot block — it yields
(`app.py:183-189`). So the composition is `asyncio.create_task(supervise({...}, stopping))` in place
of today's `asyncio.create_task(run_publisher(...))` at `app.py:137-139`, and `_stop_publisher`
(`app.py:143-157`) keeps its `wait_for(..., PUBLISHER_STOP_TIMEOUT_SECONDS)` +
`suppress(TimeoutError, asyncio.CancelledError)` shape. **`PUBLISHER_STOP_TIMEOUT_SECONDS = 5.0` at
`app.py:86-89` is the number D-31's drain deadline must be argued against** — its own comment says
*"`run_publisher` polls the handoff on a 0.1 s timeout, so this is generous by an order of
magnitude"*, and that sentence stops being true the moment the stop path drains 512 records. One
number, argued once, or two numbers whose relationship is written down.

**D-39: `/metrics` is the eighth path, and three tests move together.** `app.py:214-228`'s `healthz`
is the exact analog — an unversioned route declared with `@application.get`, no
`Depends(require_session)`, no `declares_action`, and a docstring giving A-045's unversioned rule and
the reason an operator must be able to reach it. The tests that must change in the same commit:

| Assertion | Location | Change |
|---|---|---|
| `EXPECTED_ROUTES` literal frozenset | `test_route_table.py:51-61` | add `("GET", "/metrics")`; **seven → eight** |
| `UNVERSIONED` frozenset | `test_route_table.py:65` | add `/metrics` |
| `test_the_assembled_table_is_exactly_the_seven_paths` | `:98-101` | rename with the count |
| `test_the_health_routes_are_unversioned_and_declare_nothing` | `:162-176` | it iterates `UNVERSIONED`, so `/metrics` must also declare no session and no action |
| `test_no_route_is_reachable_except_through_the_application` | `:343-354` | `len(paths) == len(EXPECTED_ROUTES)` |
| `test_the_openapi_schema_agrees_with_the_route_table` | `:103-117` | **the trap — see below** |

**The trap, and it is structural.** `assembled_routes` (`session_auth.py:247-270`) walks
`application.routes` and keeps an entry only if it has `effective_route_contexts` **or** a
non-`None` `dependant`:

```python
    for route in application.routes:
        expand = getattr(route, "effective_route_contexts", None)
        if expand is not None:
            routes.extend(expand())
        elif getattr(route, "dependant", None) is not None:
            routes.append(route)
```

A `prometheus_client.make_asgi_app()` mounted with `app.mount(...)` is a Starlette `Mount`: it has
neither attribute, so it appears in **neither** `assembled_routes` nor `app.openapi()`. **And nothing
in the suite would notice.** `test_the_assembled_table_is_exactly_the_seven_paths` (`:98-101`) and
`test_the_assembled_table_holds_no_route_this_phase_did_not_declare` (`:297-309`) both compare
`_table()` — built from `assembled_routes` — against `EXPECTED_ROUTES`, so a `Mount` is simply
invisible to them and they stay green.
`test_the_router_and_the_health_routes_are_the_only_things_mounted` (`:275-294`) does walk raw
`app.routes` and *would* see the mount, but it asserts only that `/docs`, `/redoc` and
`/openapi.json` are absent — so it stays green too. **A served path that every route assertion in the
repository is blind to is exactly the shape AC-10 exists to refuse**, which is why this is a decision
and not a mounting detail. → Either mount `/metrics` as an ordinary `@application.get` returning
`Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)` so it is visible to both walks,
or assert its absence from both **on purpose with the reason written down**. Broken Window #4 is
standing: `assembled_routes` is not optional (`session_auth.py:249-256`).

**Whatever shape wins, it inherits `app.py:192-209`'s reasoning about `docs_url=None`**: the
route-count assertions exist so *"a router mounted for a side effect — a metrics endpoint, a debug
route, a second health check — cannot arrive unnoticed"* (`test_route_table.py:299-303`). This phase
mounts exactly the metrics endpoint that sentence names. Add it to the list; do not weaken the list.

---

### `src/prope/worker.py` (modified — D-42 depth gauges, D-43 oldest-body age)

**D-42's job is an exact copy of the retention job's composition** (`worker.py:325-331`):

```python
    async def expired_body_sweep() -> None:
        await sweep_expired_bodies(
            sessionmaker, observed.current, now=clock(), chunk_size=chunk_size
        )

    async def expired_body_deletion_job() -> None:
        await interval_job(expired_body_sweep, retention_interval_seconds, stopping)
```

`interval_job` (`supervisor.py:212-243`) runs the body **first** and waits after — *"A worker that
has just started after an outage is the case that matters"* — and its wait is interruptible, which is
what lets an interval be long without lengthening shutdown (Trap 2, `supervisor.py:38-43`).

**The interval constant is a `#:` block that argues the number** — `RETENTION_SWEEP_INTERVAL_SECONDS`
(`worker.py:82-110`) is twenty-nine lines of arithmetic for one float, and it is the density D-42's
depth-gauge interval must match. See "The tuning-constant idiom" below.

**Three names, not two, and three places to change them.** `worker.py:73-80` declares the two job
constants with the comment that `deployment_target` *"names exactly these"*; the module docstring
(`:1-7`) counts the later arrivals; and
`test_worker_jobs.py:506-509` (`test_the_two_supervised_jobs_are_the_lock_files_two_residents`)
asserts the pair. All three change together, and the test's name changes with them.

**D-43's shape is `sweep_expired_bodies` (`worker.py:233-265`), not a query.** That function is the
existing "enumerate, then one bounded read per workspace" loop, and its docstring already carries the
two things D-43's gauge inherits:

> **N+1 transactions per pass, one per workspace, unbounded in workspace count.** A-140 records the
> same shape … **An exception propagates and is not swallowed.**

And the blind spot is already written down and already asserted. `ObservedWorkspaces`
(`worker.py:122-167`) says it in the module that owns it —

> **What it misses, exactly.** A workspace that has sent no traffic since this process started is not
> swept … Phase 3's `oldest_body_age_seconds` gauge reads above the window for exactly those
> workspaces, which is the alert measuring the data rather than the job.

— and `test_worker_jobs.py:393-417`
(`test_a_workspace_the_enumerator_omits_keeps_its_expired_bodies`) fixes the boundary in place with
the instruction *"if it ever starts failing, somebody closed the gap, and this test and
`ObservedWorkspaces`' docstring should be deleted together."* **D-43 makes that docstring's promise
half-true, and the honest edit is to that paragraph, in this phase.** It currently promises the gauge
catches the gap; after D-43 the gauge inherits the gap. Rewriting it is not optional — leaving it is
the same failure shape as the job that runs cleanly and deletes nothing.

**The gauge query must not be a single unscoped read.** `retention.py:31-38` and
`ObservedWorkspaces:126-135` both spell out why: under the tenant policy a `prope_app` read with no
`app.workspace_id` set returns **zero rows**, so `SELECT min(created_at) FROM ledger.call_body` would
report a healthy gauge forever. `pricing.PRICE_IN_FORCE` (`pricing.py:45-60`) and
`retention_settings.READ_RETENTION_WINDOW` (`retention_settings.py:52-68`) are the shape for the
per-workspace read: a `text()` constant whose `#:` comment names the index that serves it and states
that the explicit predicate sits *alongside* the policy rather than instead of it.

---

### The Prometheus rules file (new — D-44)

**Role-match: `src/prope/broker/topology.py`.** It is the repository's only existing example of
*"declare a set of externally-meaningful constants, argue every one of them in a per-token docstring
block, and then assert them back from the system that consumes them."*

```python
#: A-149's four guarantees for the work queue, in the units RabbitMQ documents
#: them in. Every one of the six keys below is load-bearing and none is
#: stylistic.
#:
#: ``x-message-ttl`` — 86,400,000 ms, which is 24 hours
#:     Milliseconds, because that is the unit ``x-message-ttl`` is documented in;
#:     writing 24 * 60 * 60 * 1000 rather than the literal keeps the unit
#:     visible. ...
#:
#: ``x-dead-letter-routing-key`` — ``prope.call_record.dlq``
#:     **The argument whose ABSENCE loses data silently.** ...
WORK_QUEUE_ARGUMENTS: dict[str, str | int] = { ... }
```

→ Six alerts, one block each, carrying the threshold **and the reason for the threshold** — the lock
file supplies both, including `LedgerRetentionOverdue`'s written argument for measuring the data
rather than the job and `LedgerDuplicateCallIds`' "read the two counters together" correction. The
same per-token style is used by `enable_tenant_rls` (`ddl.py:56-86`) with its three named
sub-headings, so it is a repository idiom rather than one file's habit.

**The read-back test's analog is `tests/broker/test_declared_arguments.py`**, which reads the queue's
arguments from RabbitMQ's management API rather than re-deriving them
(`tests/broker/_helpers.py:55-65`): *"the `arguments` object in the response is the broker's record of
what was declared, and a test comparing against it cannot pass by reading a dict it built itself."*
→ D-44's test parses the rules **file** and asserts every metric name it mentions exists in
`REGISTRY`. There is no running Prometheus to read back from (PITFALLS §4), so the registry is the
other side of the comparison, and the plan should say that explicitly rather than let the analogy
imply a service that does not exist.

**One dependency question the plan must settle, not assume:** parsing YAML. There is no YAML parser
in `pyproject.toml`'s dependency set or dev group. The precedent for this exact situation is
`tests/broker/_helpers.py:41-52` — *"`urllib.request` rather than an HTTP client dependency: this is
the only HTTP call in the test suite, and adding a runtime dependency for it would put a package in
`uv.lock` that no production code imports"* — and `tests/integration/_asgi.py:1-30` made the same
call for `httpx`. Resolve it the same way (a regex/line scan over a file this repository writes and
controls, or a stated dependency addition with its reason), and say which.

---

### `tests/architecture/test_no_body_read_path.py` (new — D-38 layers 2 and 3)

**Exact analog: `tests/architecture/test_no_sql_interpolation.py`.** Every property D-38's internal
sweep needs is already solved there:

```python
SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "prope"

#: Explicit, reasoned exceptions. Empty, and meant to stay that way. An entry is
#: ``(module path relative to src/prope, line number, why)``.
ALLOWED: frozenset[tuple[str, int]] = frozenset()

def _source_modules() -> list[Path]:
    modules = sorted(SOURCE_ROOT.rglob("*.py"))
    assert modules, f"no modules found under {SOURCE_ROOT}; the walk is looking in the wrong place"
    return modules
```

Four properties to copy verbatim (`test_no_sql_interpolation.py:10-26`):

1. **The file list is discovered by `rglob`, never written down** — *"so a module added in Phase 7 is
   covered by this test on the day it is written and nobody has to remember to add it."*
2. **A non-empty assertion on the walk itself**, so the test cannot pass by inspecting nothing
   (`:49`, and `test_the_walk_actually_found_statements_to_check` at `:101-112`). D-38's layer 2 needs
   both: *N* callables found, and *M* `text()` statements naming `call_body` found.
3. **An `ALLOWED` escape hatch that is an entry with a reason, never a relaxed assertion** (`:22-26`).
   Layer 3 needs one, because `writer.INSERT_CALL_BODY` and `retention.DELETE_CHUNK` are the two
   legitimate statements naming the table.
4. **`@pytest.mark.parametrize(... ids=lambda p: p.name)`** so a failure names the offending module.

**The vocabulary is already written and must be reused, not re-listed.** `FORBIDDEN_FIELD_NAMES`
(`test_route_table.py:71-84`) is the ten names — `request_body`, `response_body`, `byte_size`,
`body`, `bytes`, `payload`, `request_payload`, `response_payload`, `raw_body`, `call_body` — with
the comment naming ADR-0018/A-105/CL-10. → Import it rather than re-declaring it; two lists is two
places for the eleventh name to be added to only one.

**Layer 3's posture has its own precedent: `tests/security/test_eval_no_body_boundary.py`.** That
file's whole job is to prove a guarantee lives in Python and *not* in the engine, and it says so
(`:1-37`) and asserts both halves — the refusal that exists, and the hand-written insert that
succeeds. `0003_ledger_tables.py:246-252` says the same thing from the migration's side:

```python
    # SELECT is required alongside DELETE, and is not an oversight: ...
    # Revoking SELECT here in the name of "no read path" would break the retention
    # job. AC-10's no-read-path guarantee is a property of the ROUTE TABLE
    # (Phase 3), not of the grant matrix. No UPDATE: bodies are written once and deleted.
    grant_table("ledger", "call_body", app_privileges=["SELECT", "INSERT", "DELETE"])
```

→ **That comment names this phase and hands it the argument.** D-38's layer 3 is not "assert the
grant is narrow" — the grant is deliberately not narrow. It is "enumerate every statement in `src/`
that names `call_body` and assert the set is exactly two, and record that the database is not the
guarantee." Same move, same file style, and `test_eval_no_body_boundary.py:141-178`'s
*"**If this test starts failing, do not "fix" it**"* framing is the one to copy for both.

**Layers 1 and 2's shared helpers must come from `prope.session_auth`, not from the test.**
`assembled_routes`, `declared_action` and `declares_session` live there *"precisely so **Phase 23
extends a test rather than inventing one**"* (`test_route_table.py:8-12`). Anything D-38 invents that
Phase 23 will need again belongs beside them.

---

### `tests/broker/` — the chaos suite (D-45.3)

**Exact analog: `tests/broker/test_publish_confirm_failures.py`.** Its docstring (`:1-32`) is the
governing rule for this phase's chaos tests:

> `prope_call_ledger_publish_failed_total`'s `reason` label has a closed set … and a mocked
> `exchange.publish` **would prove only that the test knows how to raise**. Each of the three below
> is produced by a real broker doing the real thing

and its second decision is the one D-45 reuses — *"Why the nack is provoked on a separate queue and
not on `prope.call_record`"*: build the smallest real thing that produces the identical broker
behaviour, rather than degrading the shared fixture. → D-45.3 closes the publisher's own channel and
connection, and points `build_connection` at a closed port; it does **not** stop
`rabbitmq_container`, which is session-scoped (`conftest.py:182-194`) and shared by every later test
in the run.

**`monkeypatch.setattr` against a module attribute is the established provocation**
(`test_publish_confirm_failures.py:84`, `:107`, `:138`, `:161`, `:215`) — e.g.
`monkeypatch.setattr("prope.call_ledger.enqueue.PUBLISH_TIMEOUT_SECONDS", 1e-9)`. Note it patches the
*importing* module's namespace, which is the form that works given `from … import X` at the top of
`enqueue.py`.

**The suite's counter-delta idiom is `before`/`after` around the provocation**
(`test_publish_confirm_failures.py:85`, `:94-95`) and never an absolute value.

**A running drain is driven through `tests/broker/_helpers.py:115-146`'s `drain_until`**, which
creates the task, polls a predicate, and always stops it in a `finally`. The stop signal is a
directly-settable `asyncio.Event` — *"the shape the drain takes precisely because
`loop.add_signal_handler` is unimplemented on Windows"*. `test_worker_jobs.py:101-135`'s
`_run_worker_until` is the same helper one level up, and returns whether the predicate ever held so
the caller can assert on it rather than on a timeout.

---

### Redelivery idempotency (D-33/D-35, ROADMAP SC2)

**The redelivery mechanism already has a test and it is the one to extend:**
`test_drain_failure_classification.py:199-244`, which takes three messages with a first consumer that
acks none, drops the connection, and asserts `message.redelivered` on the second consumer's
deliveries. Its docstring says why it exists: *"This is the property that makes CL-02's upsert
necessary, and asserting it here is what makes the Phase 2 gap in this module's docstring a measured
statement rather than a worry."*

**The assertion that matters is on `ledger.workspace_spend`, not on `ledger.call_record`.** A
duplicate in `call_record` is refused by the primary key with or without this phase; what redelivery
corrupts is the aggregate maintained inside the writer's transaction (`writer.py:100-128`, A-103).
Read it back through `migrate_engine` — the owner role, subject to no policy — which is the standing
posture stated at `test_body_retention_delete.py`, `test_worker_jobs.py:9-16` and
`test_drain_failure_classification.py:49-52`:

```python
async def _committed(migrate_engine: AsyncEngine) -> int:
    """Rows in ``ledger.call_record``, read as the OWNER — never via the drain."""
    async with migrate_engine.begin() as connection:
        return (await connection.execute(COUNT_RECORDS)).scalar_one()
```

**Both halves, always.** `test_one_unwritable_record_does_not_discard_its_batch_mates`
(`:104-137`) is the model: *"four committed rows without one DLQ message would mean the poison record
vanished, and one DLQ message without four rows would mean the batch was discarded."* → A redelivery
test asserts the record count is unchanged **and** `duplicate_call_id_total` moved **and**
`workspace_spend.call_count` is unchanged. Any two of the three pass against a drain that silently
did nothing.

---

### The load claim (D-45.1/D-45.2 — CL-12, ROADMAP SC5)

**No analog. Nothing in this repository times anything.** `03-RESEARCH.md` is the reference. Three
repository facts constrain it:

- **`pyproject.toml` has no `[tool.pytest.ini_options] markers` key** (`pyproject.toml:69-72` is
  `asyncio_mode` and `testpaths` only). An unregistered marker emits `PytestUnknownMarkWarning`, so
  D-45.2's marker is a `pyproject.toml` edit in the same change, and it gets a comment in the file's
  established style (every dependency there carries the ADR or assumption that put it there —
  `:10`, `:17-18`, `:23`, `:25`, `:28-39`, `:46-54`).
- **`HANDOFF_MAXSIZE = 512`** (`enqueue.py:70`) is what 80% is 80% *of*; `reset_handoff()`
  (`enqueue.py:92-100`) is the documented test seam for a clean buffer, and `purge_queues`
  (`conftest.py:212-237`) calls it autouse between every test.
- **`enqueue()` is synchronous** (`enqueue.py:103-108`, *"It is deliberately **synchronous** — there
  is nothing to await, and a coroutine would invite a caller to await something"*), which is what
  makes `perf_counter_ns` around the bare call the honest measurement of the caller's whole span.

---

### `tests/conftest.py` (modified)

**The rig's four + three decisions are in its docstring (`conftest.py:1-58`) and this phase adds to
that list rather than beside it.** The two that bear directly:

**Isolation is truncate-between-tests, never an outer rollback** (`:22-27`):

> The rollback pattern is the conventional one and would silently break every cross-tenant test: it
> turns the seam's `session.begin()` into a savepoint, and the transaction-local tenant setting
> survives a savepoint, so tenant A's context contaminates tenant B inside the same test.

`db/session.py:30-34` states the same rule from the other side. → **A phase adding an idempotency
test must not reach for a rollback fixture to "make redelivery cheap".** It would work and it would
poison the tenant tests.

**Cleanup is discovered, never listed** (`conftest.py:94-98`, `:170-179`): `truncate_ledger`
enumerates from `pg_tables`, and `test_tenant_coverage.py:57-65` enumerates from `pg_class`. This
phase creates no table, so **neither needs an edit** — the same "no test rig edit is needed, and that
is the point" property `0004_workspace_retention.py:47-55` claimed and proved.

**What may need an edit: the Prometheus registry.** `prometheus_client`'s default `REGISTRY` is
process-global and every existing metric test works around it with before/after deltas
(`test_publish_confirm_failures.py:55-63`). Eighteen metrics and six alert assertions make that
harder. If the plan wants a reset fixture, it is autouse in the shape of `purge_queues`
(`:212-237`) — including its **opt-in-by-fixture-graph** trick, *"a test that never asked for
`amqp_url` should not pay for a broker container it does not use"* — and it must not unregister the
module-level collectors, because `observability.py` defines them at import and re-import will not
happen.

---

### `pyproject.toml` (modified)

**Analog: the file's own comments.** Every entry names the ADR or assumption that put it there and
explains any non-obvious pin:

```python
    # ADR-0028 — RabbitMQ carries the asynchronous work; aio-pika is the client
    # `docs/modules/call-ledger.lock.yml:291` names by hand.
    #
    # 9.6.2 rather than the current 10.0.1, and the reason is a risk posture
    # rather than a compatibility fact. ...
    "aio-pika==9.6.2",
```

→ A `markers` key gets the same treatment: what the marker means, why the test it gates is not in the
default selection, and **the exact invocation that runs it** — D-45.2's own words are *"a marked test
with a documented invocation is a test that exists and is honest about when it runs."*

---

## Shared Patterns

### Tenant scoping — the only way a workspace reaches SQL

**Source:** `src/prope/db/session.py:43-62`
**Applies to:** `fallback.py`, `worker.py`'s `oldest_body_age` read, and every statement this phase
writes. **Does not apply to** the depth gauges (D-42), which read the broker, not the database.

```python
#: Sets the tenant for the current transaction only. The third argument is what
#: makes it transaction-local; the second is a bound parameter.
SET_TENANT = text("SELECT set_config('app.workspace_id', :ws, true)")


@asynccontextmanager
async def workspace_transaction(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
) -> AsyncIterator[AsyncSession]:
```

Four properties, all load-bearing (`session.py:7-34`, `ddl.py:56-86`):

1. **`set_config` with a bound `:ws`, never `SET LOCAL app.workspace_id = <interpolated>`** —
   PostgreSQL's assignment statement takes no bind parameters, so the obvious form does not bind and
   the tempting repair is an injection site on a value that arrives inside a broker payload.
2. **`workspace_id` is `text` and the predicate compares text to text with no cast** —
   `ddl.py:73-80` records that ADR-0035 and ADR-0045 write the predicate with `::uuid` and that a
   `wsp_`-prefixed ULID would raise where zero rows are required. The ADR wording is carried upstream
   for correction, **not patched**.
3. **The transaction opens first, then the setting** — a transaction-local setting issued outside a
   transaction block warns and does nothing, *"it would protect nothing while looking like it
   protected something."*
4. **One workspace per context manager, as a constructor argument and never a setter** (ADR-0040).
   D-27's one-record-one-transaction fallback satisfies this trivially; a batched fallback would not.

**A missing filter returns zero rows, not an error**, and that is the failure D-43 has to design
around rather than the failure it can rely on (`ObservedWorkspaces:126-135`, `retention.py:40-48`).

### The one write path

**Source:** `src/prope/call_ledger/writer.py:1-8, 208-223`
**Applies to:** `fallback.py`, the drain, `price_usage` — and nothing else may write SQL against
`ledger.call_record`, `ledger.call_body` or `ledger.workspace_spend`.

> `write_records` is what Phase 2's broker drain calls once per workspace group and what Phase 3's
> direct-write fallback calls with a single record. **There is one implementation of it on purpose**:
> the lock file requires that pricing and `expires_at` stamping cannot drift between those two
> callers, and two functions that both "write a call record" is exactly how they would.

→ The file already names this phase's caller. D-33's changes land **inside** it, which is why the
duplicate count is free for all three callers (D-35, INT-019's *"the same upsert INT-018's drain
uses"*).

**All-or-nothing is a contract, not an implementation detail** (`writer.py:216-218`, *"This function
does not commit; the caller's context manager owns the transaction boundary, so a raise anywhere
below leaves nothing written"*). It is why `_retry_group_one_at_a_time` (`drain.py:285-325`) exists,
and why D-27 declines to duplicate that ladder in `app`.

### Never zero, no fourth state — the refusal posture

**Source:** `src/prope/call_ledger/writer.py:25-36, 274-287`
**Applies to:** D-40's `missing_version_id_total` refusal, D-29's oversize decision, D-37's bound

```python
                    raise ValueError(
                        f"{draft.call_id} prices to {cost} against price row {price_row_id}: "
                        f"{draft.input_tokens} input and {draft.output_tokens} output tokens at "
                        f"{price.input_price_per_1k}/{price.output_price_per_1k} per 1k. A priced "
                        "record cannot record a cost of zero, and neither a zero nor a downgrade "
                        "to unpriced would be true"
                    )
```

The template: **identifier, the two values in tension, the rule, and why both alternative answers are
false.** `get_run_totals`'s mixed-currency raise (`seams.py:597-603`) and `delete_expired_bodies`'
argument guards (`retention.py:152-163`) are two more instances.

→ D-29's oversize body is the interesting case: it is **not** a refusal in that sense, because the
record continues with `body=None` and `enqueue()` may not raise. So it is counted and logged, not
raised — and the plan should say which of the two postures it took and why, rather than letting the
reader assume.

### No body, no log, no metric label — A-046

**Source:** `writer.py:37-39`, `enqueue.py:26-34`, `drain.py:30-34`, `envelope.py:40-42`,
`supervisor.py:54-61`, `api.py:60-62`, `schemas.py:432-439`, `connection.py:21-23`
**Applies to:** `fallback.py` (new module docstring), every new log line, all eighteen metrics

Two rules and both are asserted somewhere:

- **The allow-list is positive** (`observability.py:41-48`). A deny-list *"passes the first time a
  body is carried on a field nobody thought to forbid, which is every field that has not been
  invented yet."*
- **An exception's CLASS reaches a log line; its message does not** —
  `app.py:129-134` (*"at this depth the message is liable to contain the broker URL, which carries
  credentials"*), `supervisor.py:166-172`, `seams.py:449-462`, `schemas.py:512-521`. → The fallback's
  failure log follows this exactly: `reason=type(error).__name__`.

The enforcement is `test_publish_confirm_failures.py:184-237` — two markers (a body-shaped one and a
credential-shaped one on a field the code never reads), provoked through a real failure, then greped
out of every captured `structlog` record and every metric label in `REGISTRY`. **`assert captured, "a
failed confirm must log SOMETHING, or the assertion is vacuous"** (`:230`) is the part most likely to
be dropped when the test is copied. Do not drop it.

### Prove the absence, and provide the positive control

**Source:** `tests/security/__init__.py:1-11`, `test_eval_no_body_boundary.py:141-178`,
`test_worker_jobs.py:393-417`, `test_route_table.py:126-134`
**Applies to:** D-38 (all three layers), D-45's chaos suite, D-30's counter removals

> Each test in this package carries a positive control. An RLS test against an empty table passes for
> the wrong reason, and a privilege test whose UPDATE matched zero rows is indistinguishable from one
> the engine refused.

Concrete instances to copy:
- `test_eval_no_body_boundary.py:157-159` reads `source` back before asserting the insert lands —
  *"Without this the insert below would prove nothing."*
- `test_route_table.py:130-134` asserts the route **count** before iterating, because
  `include_router` would otherwise make the walk vacuous.
- `test_no_sql_interpolation.py:101-112` asserts the walk found statements at all.
- `test_publish_confirm_failures.py:229` asserts the failure actually happened before checking the
  logs.

→ D-30 is a removal, and a removal has the same problem in reverse: a test asserting
`metadata_dropped_total` did **not** move must first prove the dead-letter actually happened (the DLQ
depth went to 1), or it passes against a drain that did nothing.

### The tuning-constant idiom — `#:` marks a number as judgement and carries its argument

**Source:** `retention.py:64-68`, `drain.py:57-93`, `supervisor.py:96-111`, `worker.py:82-110`,
`enqueue.py:57-74`, `app.py:77-101`
**Applies to:** D-29's 256 KiB cap, D-31's drain deadline, D-42's gauge interval, D-45's 500 samples,
the histogram bucket edges

```python
#: A6 — a tunable judgement, not a repo decision, recorded so that changing it
#: is a visible act. The stated target is one day's expired bodies, up to
#: 500,000 rows in a batch, removed within ten minutes. At this size that is 100
#: chunks, which has ample headroom; the number is unvalidated at real scale.
DEFAULT_CHUNK_SIZE = 5_000
```

The full form has five parts, all present in `drain.WINDOW_SIZE` (`drain.py:57-76`) and
`worker.RETENTION_SWEEP_INTERVAL_SECONDS` (`worker.py:82-110`):

1. the requirement or target the number is derived **from**, quoted;
2. the arithmetic, written out;
3. **what the number does not bind** — `WINDOW_SIZE`'s *"At the steady-state rate, T dominates and N
   is irrelevant"* is the exemplar;
4. the rejected alternative and why it is worse;
5. **"a tunable judgement, not a repo decision, recorded so that changing it is a visible act.
   Unvalidated at real scale, like every number of this kind in this codebase."** — this sentence, or
   a close variant, appears at `retention.py:64-68`, `drain.py:74-75`, `supervisor.py:101-103` and
   `worker.py:108-109`. It is the house closing.

**Constants that are NOT judgements say so instead.** `IDLE_POLL_SECONDS` (`drain.py:85-87`) —
*"Not a tuning parameter — it is the shutdown latency of an idle drain, and it is short because an
idle drain is what a deploy interrupts."* And `TRANSIENT_BACKOFF_SECONDS` (`drain.py:90-93`) argues
*flat rather than exponential*. Pick the right one; a judgement dressed as a fact is worse than
either.

### Error envelope, machine codes, and the fail-closed session

**Source:** `session_auth.py:77-113, 136-165`, `schemas.py:120-186, 421-521`
**Applies to:** D-37's `422` (inherited free), D-39's `/metrics` (which declares **neither**)

Three rules:

1. **There is one error shape** — `{error: {code, message, details?, request_id}}` — and
   `install_error_envelope` (`schemas.py:449-521`) registers three handlers to make FastAPI's own
   `{"detail": ...}` unreachable. **There is deliberately no catch-all `Exception` handler**
   (`:480-484`): *"Registering one makes Starlette's `ServerErrorMiddleware` stop re-raising, so a
   genuine bug becomes a tidy `500` that no test fails on."*
2. **`code` is what the client renders; `message` is for the log** (ADR-0053, `schemas.py:120-136`,
   `session_auth.py:84-92`). The vocabulary is a closed `StrEnum`, and `SESSION_REQUIRED` takes its
   value from `session_auth.SESSION_REQUIRED` rather than repeating the literal. → **D-37 needs no
   new member**; a `le=` violation is `VALIDATION_FAILED` through the existing handler.
3. **`require_session` refuses unconditionally and that is not this phase's to weaken**
   (`session_auth.py:136-165`, ORCHESTRATION §4). All five `/api/v1` routes answer `401` until Phase
   7. D-37's bound therefore lands on a route nobody can reach — *"a fix landed before its own
   exposure, which is the cheap moment"* — and its test drives the handler through
   `dependency_overrides`, which `session_auth.py:28-33` calls **a test seam and not a bypass**, with
   `tests/integration/test_management_routes.py` asserting that a request made *without* the override
   is refused.

**`/metrics` sits outside all of it**: unversioned per A-045 (`test_route_table.py:63-65`), no
session (a scraper has none), no `ManagementAction`, and — following `readyz` (`app.py:255-260`) —
**not the A-045 envelope**, because a Prometheus exposition is not a management-API refusal. Write
that reason at the route, as `readyz` does.

### Explicit central composition (D-13)

**Source:** `app.py:6-16`, `worker.py:9-18`, `test_route_table.py:202-231`,
`test_worker_jobs.py:459-503`
**Applies to:** D-26 (binding the fallback), D-32 (the supervised publisher), D-39 (`/metrics`),
D-42 (the third worker job)

> A route that can appear because a file was named a certain way is precisely the shape those tests
> exist to refuse: the assertion would be checking a list the discovery mechanism also produced.

`test_the_application_is_composed_by_hand_and_not_discovered` (`test_route_table.py:202-231`) AST-walks
`app.py` for `importlib` / `pkgutil` / `__import__` and then asserts the **positive** half — the exact
import line and the exact `include_router` line as source strings. → Everything this phase adds to
`app.py` or `worker.py` is a hand-written line in the import block and a hand-written entry in the
job map. `app.py` gaining `import prope.supervisor` (D-32) does not break that walk;
`worker.py` gaining a metrics import would break `test_worker_imports_no_web_framework`
(`test_worker_jobs.py:459-478`), whose forbidden set is
`{"fastapi", "starlette", "uvicorn", "http", "socket", "socketserver"}` — **which is the mechanical
reason D-39 cannot solve the two-registry problem by opening a port on `worker`.**

### Money and time

**Source:** `domain.py:15-19`, `models.py:46-53`, `schemas.py:87-111`
**Applies to:** anything this phase adds that carries a figure — which, if the design holds, is
nothing

> **No field on any object here is a binary floating-point number.** Money is `decimal.Decimal` end to
> end and every timestamp is a timezone-aware `datetime`.

→ Mostly **not binding this phase**: no money crosses any surface D-26…D-45 adds, and
`CeilingDecision` (`seams.py:290-314`) must still *"never grow a third field that carries a
number"* — D-40's `ceiling_check_total{result}` counts branches and carries no figure, which is what
keeps A-056 intact. The timezone half **is** binding: D-41's `occurred_at` and D-43's gauge
arithmetic are both `datetime` work, and `envelope.py:27-32` refuses a naive value at the boundary.

---

## Patterns on this list that are NOT binding for Phase 3 — stated, because a pattern list reads as binding

### Migration authoring — the full stack, and why this phase writes none

**No decision in `03-CONTEXT.md` requires a migration, and `03-CONTEXT.md` says so twice**
(*"No new table and no migration are required by any decision above. If a plan finds it needs one,
that is information"*). The `ledger` schema is Phase 1's and `data.owns` already carries an OQ-018
deviation. **`EXPECTED_ABSENT_SCHEMAS` (`test_tenant_coverage.py:39-53`) is untouched** — Phase 7
creating `access` is still the first phase that must shrink it.

It is written out anyway, because a plan that discovers it needs one must not invent the shape:

**The bare `ddl` import** (`0004_workspace_retention.py:93-96`) — this is a real trap and it is
commented as one in three places (here, `alembic.ini:19-30`, `alembic/env.py:34-39`):

```python
# `alembic/ddl.py`, imported by bare name rather than as `alembic.ddl` — that
# dotted name resolves to the installed Alembic package's own dialect-DDL
# submodule. `alembic.ini`'s prepend_sys_path puts this directory on the path.
from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role
```

**The revision header, and D-04's linear chain** (`0004:100-104`): `revision = "0004"`,
`down_revision = "0003"`. **A plan never hardcodes `down_revision`** (ORCHESTRATION §3) — the
executor reads `uv run alembic heads` and wires it then. `tests/integration/test_migration_chain.py`
asserts linearity.

**Constants plus emitters** (`ddl.py:1-15`): the table DDL is a module-level string constant with the
reasoning in SQL comments, and every guarantee is a helper call so *"a reviewer greps the helper
name"* —

```python
def upgrade() -> None:
    assume_migrate_role()
    op.execute(CREATE_WORKSPACE_RETENTION)
    enable_tenant_rls("ledger", "workspace_retention")
    grant_table("ledger", "workspace_retention", app_privileges=["SELECT", "INSERT", "UPDATE"])
    reset_role()
```

`assume_migrate_role()` / `reset_role()` bracket every revision from 0002 onward (`ddl.py:27-46`) —
without the reset, *"Alembic's own write to `public.alembic_version` is attempted as `prope_migrate`,
which holds no privilege there."*

**`enable_tenant_rls`'s per-token justification docstring** (`ddl.py:56-86`) is the house style for
documenting a set of load-bearing tokens, and it is the style D-44's rules file and D-42's queue
arguments inherit even though no migration is written: `ENABLE` never `FORCE`;
`current_setting(..., true)` with **two** arguments; **no cast** (OQ-A); `WITH CHECK` written out
rather than defaulted.

**`version_table_schema="public"`** (`env.py:6-12`, `:87`, `:99`) — with schema-per-module and
`include_schemas=True`, an unpinned `alembic_version` lands wherever `search_path` points, and inside
`ledger` it fails D-06's coverage walk for carrying no `workspace_id`.
`test_tenant_coverage.py:163-171` asserts it.

**The whole guarantee stack in one revision, and no test-rig edit.** `0004:47-55` proved that the
truncate fixture and the coverage walk both discover from the catalogue, so a new table needs no list
edit anywhere — *"if this revision forgot `enable_tenant_rls` the walk would go red on its own."*

### Grant narrowing is not the answer to CL-10

`0003_ledger_tables.py:246-252` already decided this, in a comment addressed to this phase:
*"AC-10's no-read-path guarantee is a property of the ROUTE TABLE (Phase 3), not of the grant
matrix."* `prope_app` keeps `SELECT, INSERT, DELETE` on `call_body` and the `SELECT` is load-bearing
for the retention `DELETE`. **Do not narrow it**; D-38's third layer asserts the *statement*
enumeration instead.

### The `prope_report` grant question is Phase 1/2's open item, not a pattern

`grant_table`'s `report_select` defaults `True` (`ddl.py:97-104`) and `0004:163-168` took the default
with a written reason. This phase creates no table, so the pattern has nothing to apply to; the
open item survives in `03-CONTEXT.md`'s Discretion list as a decision to record, not a grant to write.

### `ruff format --check` is Broken Window #1 and is not this phase's to fix

`ruff.toml:2` says `line-length = 120`; the repository is hand-wrapped to ~100. `make check` runs
`format` (a rewrite) rather than `format --check`. **`uv run ruff check src/ tests/ alembic/` is the
gate** (ORCHESTRATION §3) and `ruff.toml:14-15` selects `E, F, I, N, W, UP` with `E501` ignored.

### The root `Dockerfile` and `docker-compose.yml` are boilerplate from another project

Phase 2 routed them to `deferred-items.md` (`02-PATTERNS.md` § "No Analog Found"). D-44's rules file
does **not** extend them, and the deployment stack owns no milestone (PITFALLS §4).

---

## No Analog Found

| Item | Role | Reason |
|------|------|--------|
| A Core `insert(...).on_conflict_do_nothing().returning(...)` | repository | Every statement in `src/` is `text()`. `models.py`'s `Table` objects exist and are consumed by nothing. `03-RESEARCH.md` owns the construct, the `insertmanyvalues` behaviour, and whether `RETURNING` composes with executemany on asyncpg — **this is the single most load-bearing unknown in the phase**, because CL-02's real claim lives in the returned set |
| `prometheus_client.Histogram` / `Gauge` | config | Only `Counter` is imported anywhere. Default buckets start at 5 ms and cannot measure a p95 < 1 ms target; bucket edges are a `#:`-argued decision with no in-repo precedent |
| A `/metrics` exposition surface | controller | No route in this repository serves a non-JSON body, and none is exempt from both `require_session` and `declares_action` inside a router. `healthz` is the closest and is on the application, not the router |
| A timing assertion | test | Nothing in the suite measures duration. `perf_counter_ns`, an order statistic, and a marked long-running test are all new here |
| Parsing a YAML file in a test | test | No YAML parser is in the dependency set. `_helpers.py:41-52` and `_asgi.py:1-30` are the two precedents for how this project answers "we need a parser for one test" |
| A shutdown drain with a deadline | service | `run_publisher` returns immediately on `stopping` (`enqueue.py:274`); `run_drain` finishes its in-flight window but drains nothing further (`worker.py:284-293`); `interval_job` returns without a final pass (`supervisor.py:240-243`). D-31's bounded drain-then-count has no precedent in any of the three |

---

## Metadata

**Analog search scope:** `src/prope/**` (27 modules, 6,168 lines), `alembic/**` (6 files —
`ddl.py`, `env.py`, revisions 0001–0004), `tests/**` (40 files across 6 packages, 9,384 lines),
`pyproject.toml`, `ruff.toml`, `alembic.ini`, `Makefile`
**Files read in full:** `writer.py`, `enqueue.py`, `drain.py`, `seams.py`, `schemas.py`,
`domain.py`, `models.py`, `envelope.py`, `retention.py`, `retention_settings.py`, `observability.py`,
`supervisor.py`, `session_auth.py`, `app.py`, `worker.py`, `db/session.py`, `db/engine.py`,
`broker/topology.py`, `broker/connection.py`, `alembic/ddl.py`, `alembic/env.py`,
`alembic/versions/0004_workspace_retention.py`, `tests/conftest.py`,
`tests/architecture/test_route_table.py`, `tests/architecture/test_no_sql_interpolation.py`,
`tests/architecture/test_tenant_coverage.py`, `tests/broker/_helpers.py`,
`tests/broker/test_publish_confirm_failures.py`,
`tests/broker/test_drain_failure_classification.py`, `tests/integration/test_worker_jobs.py`,
`tests/integration/_asgi.py`, `tests/security/test_eval_no_body_boundary.py`,
`tests/unit/__init__.py`, `tests/security/__init__.py`; partial reads of `api.py` (1-180, 225-337,
640-742) and `alembic/versions/0003_ledger_tables.py` (225-275)
**Pattern extraction date:** 2026-08-10
**Decisions consumed:** none — `03-CONTEXT.md` holds D-26 through D-45 and this artifact adds no
decision of its own. **Open-question ids consumed:** none — OQ-022…OQ-026 are allocated to this phase
and are the plans' to raise.

**One judgement recorded as a judgement, not as a detector result** (ORCHESTRATION §0): the
"Analogs found: 17 / 18" line and the match-quality column are an agent's assessment of similarity,
reached by reading both files. No `api-coverage.cjs`, no estimate-calibration and no
assumption-delta detector exists in this environment, and none was run.
