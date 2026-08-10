# Phase 03 — executability critique of the plan set

> **Scope.** Adversarial read of `03-01-PLAN.md` … `03-06-PLAN.md` against the tree at
> `E:\Projects\P-113` as it stands. The single question is: *if a fresh executor with no memory of
> this conversation ran these plans top to bottom, where would it get stuck, guess, or build the
> wrong thing?* Not spec fidelity — `03-PLAN-CRITIQUE-SPEC.md` owns that, and findings 5 and 12
> below are the only deliberate overlaps.
>
> **No detector was run.** The GSD toolchain is absent (ORCHESTRATION §0). Every line reference,
> symbol existence check, count and file listing below was gathered by hand with `grep`, `sed` and
> `Read` against the live tree, and every judgement is an **agent judgement, labelled as one**.

## What is right, so it is not re-litigated

Line references are unusually accurate. I spot-checked forty-one of them across `enqueue.py`,
`app.py`, `worker.py`, `supervisor.py`, `writer.py`, `drain.py`, `seams.py`, `schemas.py`,
`domain.py`, `models.py`, `conftest.py`, `test_route_table.py`, `test_no_sql_interpolation.py`,
`test_worker_jobs.py`, `_helpers.py`, `ddl.py` and all four migrations; **every one resolved to the
construct the plan names.** No plan hardcodes a `down_revision` and no plan writes a migration. No
`@$HOME/.claude/gsd-core/` reference survives anywhere in the phase directory. No plan gates on
`ruff format --check` or on a `typecheck` target; all six name `uv run ruff check src/ tests/
alembic/` as the gate and say why. `CONTENT_TYPE_PLAIN_0_0_4` really is exported by the installed
`prometheus-client` 0.26.0 and `CONTENT_TYPE_LATEST` really is `version=1.0.0` (`exposition.py:51`,
`:57`) — 03-04's claim is correct. PyYAML 6.0.3 really is a `uvicorn[standard]` extra
(`uv.lock:747-753`) — 03-04's dependency reasoning is correct. `OQ-022`…`OQ-026` are genuinely free
(`docs/brainstorm/open_questions/` jumps 021 → 027). `models.call_record` and `models.call_body`
declare a superset of every key in `writer.py`'s `record_rows` / `body_rows` dicts, so D-33's move to
the Core layer will compile. The wave file-lists are disjoint as declared, and `COVERAGE.md`'s
disjointness table is accurate.

The findings below are what is left.

---

## Findings

### 1. `03-06-PLAN.md` Task 1 (and Task 3) — the timed run overflows the handoff, so the zero-drop assertion cannot pass

**Severity: blocker.**

**What the plan says.** Task 1, the measurement, steps 1 and 3:

> "1. `reset_handoff()`, then `enqueue()` `HANDOFF_80_PERCENT` drafts to reach the stated depth. **No
> publisher runs**, which is what makes 80% depth free to arrange…"
> "3. `start = time.perf_counter_ns()`, the bare `enqueue(draft)`, `samples.append(…)`."

with `HANDOFF_80_PERCENT = int(HANDOFF_MAXSIZE * 0.8)` and `SAMPLES = 500`.

**The arithmetic.** `HANDOFF_MAXSIZE = 512` (`src/prope/call_ledger/enqueue.py:70`), so
`HANDOFF_80_PERCENT = 409`. The test then makes **500 more** `enqueue()` calls with nothing draining:
409 + 500 = **909 records into a 512-slot bounded queue**. The 103rd timed call fills it, and calls
104 through 500 — **397 records** — take `enqueue()`'s `except asyncio.QueueFull` branch at
`enqueue.py:120-129`, which does `metadata_dropped_total.inc()` and
`enqueued_total.labels(outcome="dropped").inc()`.

**What breaks.** The plan's own `must_haves.truths` — *"Across that run,
`prope_call_ledger_metadata_dropped_total` does not move"* — and Task 1's acceptance criterion
*"`prope_call_ledger_metadata_dropped_total` moves by zero across the run, asserted as a before/after
delta"* are **arithmetically unreachable**. The p95 assertion would pass (the `QueueFull` path is
cheap), so the failure arrives as a bare counter mismatch with no diagnosis attached, and the
obvious "fix" an executor reaches for — deleting the drop assertion — deletes half of CL-12.

Task 3's second assertion repeats it (*"Time `SAMPLES` calls at an empty handoff and `SAMPLES` calls
at 80% depth in the same test"*), and the byte-cap test in Task 1 is a third instance.

**Fix.** Name the drain in the plan. The cheapest correct shape is a one-line consumer inside the
sample loop but **outside** the timed span — `queue.get_nowait()` immediately after
`samples.append(...)` — which holds the depth at exactly 409 for the whole run and is what "at 80%
depth" actually means. State it explicitly, and add an acceptance criterion that
`handoff().qsize() == HANDOFF_80_PERCENT` at the end of the run, so a future executor cannot
reintroduce the overflow silently. The alternative — `SAMPLES = HANDOFF_MAXSIZE - HANDOFF_80_PERCENT`
= 103 — is refused by the plan's own order-statistic argument (*"At N=100 there are five [above the
p95], and a single GC pause is a fifth of the tail"*), so do not take it.

---

### 2. `03-01-PLAN.md` Task 2 — `fallback.py` and `enqueue.py` import each other at module scope

**Severity: blocker.**

**What the plan says.** Task 2 places `HandoffItem` in `enqueue.py` (*"Define the handoff element type
here or in `enqueue.py` — pick `enqueue.py`, because that is where it is produced"*) and
`FallbackWriter` in `fallback.py`:

> ```python
> FallbackWriter = Callable[[HandoffItem], Awaitable[None]]
> ```

and the frontmatter `key_links` entry states the direction explicitly: *"publish_record calls the
injected fallback at every failure site; **enqueue.py imports the TYPE only**"*.

**What breaks.** That is a module-scope import cycle. `fallback.py` needs `HandoffItem` at
**evaluation** time — the `Callable[[HandoffItem], …]` alias is a module-level assignment, not an
annotation — so it must `from prope.call_ledger.enqueue import HandoffItem`. `enqueue.py` must
`from prope.call_ledger.fallback import FallbackWriter` for `publish_record`'s and `run_publisher`'s
signatures. Whichever module is imported first, the second re-enters it before its class definitions
have run. `src/prope/app.py:70` imports `prope.call_ledger.enqueue` first, so the concrete failure is
`ImportError: cannot import name 'HandoffItem' from partially initialized module
'prope.call_ledger.enqueue' (most likely due to a circular import)` — at application import, which
takes `tests/architecture/test_route_table.py` down with it.

No module in `src/prope/` uses `from __future__ import annotations`, so the usual escape is not
already in the house style and the plan never names it.

**Fix.** Pick one of two, and say which in the plan rather than leaving it to the executor:
(a) declare **both** `HandoffItem` and `FallbackWriter` in `enqueue.py` and have `fallback.py` import
in one direction only — `FallbackWriter` is a description of what `enqueue.py` requires, so this is
also the more honest home; or (b) keep `FallbackWriter` in `fallback.py` and have `enqueue.py` guard
its import with `if TYPE_CHECKING:` plus `from __future__ import annotations`, which the plan must
state because it is a new convention for this package. (a) is cheaper and needs no new convention.

---

### 3. `03-06-PLAN.md` Task 1 — "needs no container" is false, and the plan forbids the only fix

**Severity: blocker.**

**What the plan says.** The objective: *"in-process, with no container, no broker and no database"*.
Task 1's acceptance criterion: *"`uv run pytest tests/load/test_enqueue_off_response_path.py -q`
completes **without starting a Docker container** — provable by running it with the Docker daemon
stopped"*. The `<verification>` block repeats it.

**What the code actually does.** `tests/conftest.py:168-178`:

```python
@pytest.fixture(autouse=True)
async def truncate_ledger(migrate_engine: AsyncEngine) -> AsyncIterator[None]:
```

`autouse=True`, unconditional, and it depends on `migrate_engine` → `postgres_container`
(session-scoped `PostgresContainer`). **Every test collected under `tests/` starts PostgreSQL**,
including anything under a new `tests/load/`. The plan's own `read_first` correctly identifies
`purge_queues` as opting in by fixture graph (`conftest.py:213-237`) and then generalises that
property to `truncate_ledger`, which does not have it.

The stated criterion therefore fails on this host, and the plan's other acceptance criterion — *"No
registry-reset fixture and no rollback fixture is added to `tests/conftest.py` — `git status
--porcelain tests/conftest.py` is empty"* — reads as a blanket prohibition on the edit that would fix
it.

**Fix.** Either drop the no-container claim and replace it with what is true and still worth
asserting (*"the proxy asks for no broker fixture, so it adds no RabbitMQ startup and no AMQP round
trip; the session Postgres container is already paid for by the suite"*), or explicitly authorise the
one-line `conftest.py` change that makes `truncate_ledger` opt in by fixture graph the way
`purge_queues` already does, and amend the "conftest is untouched" criterion to name that edit. Do
not leave both statements standing.

---

### 4. `03-01-PLAN.md` Tasks 1, 2 and 4 — the fallback-only job is created in Task 2 but the shutdown drain it is promised is only built for `run_publisher` in Task 4

**Severity: major.**

**What the plan says.** Task 1 adopts `fallback-only-job` and commits: *"Adopt **fallback-only-job**,
and **factor the shutdown drain so both bodies use it** rather than duplicating it."* Task 2 then
builds the second body in `app.py`: *"start the fallback-only job instead of returning with no task:
a coroutine that reads `handoff()` on the same 0.1 s poll and awaits `fallback(item)` for every
item."* Task 4 builds the drain — but only inside `run_publisher`: *"In `enqueue.py`, **after the
`while not stopping.is_set()` loop in `run_publisher`**: 1. `handoff().shutdown()` …"* — and never
mentions the fallback-only body again. Its acceptance criterion then says
`handoff().shutdown()` is called **"exactly once, after the main loop"**.

**What breaks.** Three ways, and an executor hits at least one.
1. The factoring Task 1 promised has no home: Task 4 gives no helper name, no signature, and no
   instruction to make the fallback-only body call it. The most literal reading leaves a process that
   started against a dead broker with **no** shutdown drain at all — which is CR-02 reopened on
   exactly the branch SC1 calls "the most ordinary provocation".
2. "`handoff().shutdown()` exactly once" and "two job bodies that both drain on stop" are in direct
   tension. A grep-shaped criterion will refuse the correct implementation.
3. Task 4's supervision instruction — *"Compose it as `asyncio.create_task(supervise({JOB_…: job},
   stopping))` **in place of today's** `asyncio.create_task(run_publisher(...))`"* — names only
   `app.py:137`, the success branch. The failure branch (Task 2's fallback-only job) is never said to
   be supervised, yet D-32's whole argument is that a raising fallback must not end the task
   silently, and the fallback-only job is *made entirely of* fallback calls.

**Fix.** Name the shared helper in Task 4 — e.g. `async def drain_handoff_on_stop(publish: Callable[[HandoffItem], Awaitable[bool]] | None, fallback: FallbackWriter) -> None` in `enqueue.py`, called
from both bodies — restate the acceptance criterion as *"`handoff().shutdown()` appears in exactly
one function, and both job bodies call it"*, and extend the supervision instruction to say that
**both** branches of `_start_publisher` create their task through `supervise(...)`, with each branch
contributing its own single-entry job map.

---

### 5. `03-05-PLAN.md` Task 1 — `CallBodyPayload` does not exist, and the walk's offender set is larger than the spec critique found

**Severity: major.** (Overlaps `03-PLAN-CRITIQUE-SPEC.md` finding 1; recorded here for the part that
critique does not cover.)

The nonexistent `CallBodyPayload` (the real type is `envelope.py:68 CallRecordPayload`), and the
missing `CallRecordDraft.body` / `CallRecordEnvelope.payload` entries, are already covered there and
its four-entry fix is correct as far as it goes. **It is still short**, because layer 2 as specified
also walks callables:

> "**Callables** (`inspect.isfunction` / `inspect.iscoroutinefunction`): **no parameter name is in
> `FORBIDDEN_FIELD_NAMES`**…"

`prope.call_ledger.api` exposes three public coroutine functions whose request-body parameter is
literally named `payload`, which is a member of `FORBIDDEN_FIELD_NAMES`
(`tests/architecture/test_route_table.py:78`):

- `api.py:373  async def create_price_row(payload: PriceRowCreate, …)`
- `api.py:577  async def set_spend_ceiling(payload: SpendCeilingSet, …)`
- `api.py:688  async def set_retention(payload: RetentionSet, …)`

They are module-level names (the `@router.*` decorators return the function), so a `pkgutil` walk
over `prope.call_ledger` finds all three. That is **three more offenders** on top of the four, and
they are *callables*, not types — so the fix cannot be "add them to a frozenset of type names". An
executor will discover this only after writing the walk.

**Fix.** Split the exemption structure in two — `BODY_NAMING_EXEMPT_TYPES` (four entries, the spec
critique's list) and `BODY_NAMING_EXEMPT_PARAMETERS` (three entries, `module.function` → reason,
*"the FastAPI request-body parameter; the name is the route's input, not a stored body"*) — assert
both sizes, and state in the plan that a parameter named `payload` on a route handler is not the
failure CL-10 is about. Then keep the plan's positive control unchanged, because it is the half that
makes the whole thing worth having.

---

### 6. `03-02-PLAN.md` Task 1 — "keep the mixed-currency refusal in pass 1" is under-specified, and the obvious implementation changes behaviour

**Severity: major.**

**What the plan says.**

> "**Pass 1 stays where it is and keeps validating the WHOLE batch.** The two-workspace refusal, the
> eval-carries-a-body refusal, the zero-cost refusal, and — critically — the **mixed-currency
> refusal** all stay over every offered record. … **Pass 2 is new.** … build the month buckets by
> iterating the per-draft results and skipping any `call_id` not in `inserted`."

**What the code actually does.** The mixed-currency refusal is not a separable check — it is a
side effect of the month-bucket accumulation at `writer.py:338-351`:

```python
bucket = months.setdefault(period_month(draft.created_at), {...})
...
if bucket["currency"] is None:
    bucket["currency"] = currency
elif bucket["currency"] != currency:
    raise ValueError(f"batch mixes currencies {bucket['currency']} and {currency}; …")
```

The check is **per `period_month`**, not per batch. A batch containing January-USD and February-VND
records is accepted today. Splitting the loop means pass 1 has to rebuild a *second*, offered-records
month→currency map purely for validation, and the plan says only "the cost of splitting is one extra
iteration over a list already in memory" without saying that the extra iteration must reproduce the
per-month keying. The natural reading — one batch-wide `{r.currency for r in records}` set — silently
tightens `write_records` and would fail nothing in the suite, because
`test_a_batch_mixing_two_currencies_raises_rather_than_summing` (`test_write_path.py:312`) uses a
single month.

**Fix.** Say it in one sentence in the action: *"the pass-1 currency check is keyed on
`period_month(draft.created_at)`, exactly as the bucket is today; a batch whose two currencies fall
in two different months is accepted now and must stay accepted."* Add a behaviour line and an
acceptance criterion for the cross-month case, since it is the regression the split invites and
nothing currently guards it.

---

### 7. `03-04-PLAN.md` Task 1 — `prope.app.APP_SOURCE` does not exist

**Severity: major.**

**What the plan says.** Task 1's new assertion: *"assert that `/metrics` is present in `_table()` …
**and** in `app.openapi()["paths"]`, and that **`prope.app.APP_SOURCE`** contains no
`application.mount(`."*

**What the code contains.** `APP_SOURCE` is declared at `tests/architecture/test_route_table.py:86`:

```python
APP_SOURCE = Path(prope.app.__file__).read_text(encoding="utf-8")
```

It is a **test-module** constant. `prope.app` declares no `APP_SOURCE` and must not — adding a
module-level `read_text` of its own source to a production module for a test's benefit is exactly the
kind of change D-13's composition rules exist to refuse, and it would be the first such thing in
`src/`. The instruction as written points an executor at that mistake.

**Fix.** Change the reference to `APP_SOURCE` (the module-local constant in the test file this
assertion lives in) and add the same guard to the acceptance criterion, which currently uses the
grep form `grep -c "application.mount(" src/prope/app.py` — correct, and inconsistent with the prose
above it.

---

### 8. `03-01-PLAN.md` Task 3 — the `byte_size` acceptance criterion cannot be met in the file the task routes the test to

**Severity: major.**

**What the plan says.** Task 3 puts the byte-cap tests in `test_publish_confirm_failures.py`
(*"Extend `tests/broker/test_publish_confirm_failures.py` (or add the cases beside it, in the file
that already owns A-046's assertion)"*), and then asserts:

> "Behaviour: the computed byte size is stored on the `call_body` row even when the caller supplied
> `byte_size=None` or a wrong figure — asserted by supplying a deliberately wrong `byte_size` and
> **reading the stored column through `migrate_engine`**."

**What breaks.** A `ledger.call_body` row only exists after the **drain** has consumed the message and
`write_records` has run. `test_publish_confirm_failures.py` never starts a drain — it publishes and
inspects confirms. And the fallback path cannot supply it either: the fallback rebuilds the record
with `body=None` by design (Task 2, step 1), so nothing it writes reaches `call_body`. The only file
in 03-01's `files_modified` that runs a drain is
`tests/broker/test_enqueue_reaches_a_committed_row.py`, which Task 3 does not name.

**Fix.** Route this one criterion explicitly to `tests/broker/test_enqueue_reaches_a_committed_row.py`
(it is already in the plan's `files_modified`, so no frontmatter change is needed) and say that the
oversize/at-cap counter assertions stay in `test_publish_confirm_failures.py` while the
stored-column assertion needs the committed-row test's drain.

---

### 9. `03-04-PLAN.md` Task 3 — where the gauge is set, and how the deleted count is captured, are both left to the executor

**Severity: minor.**

**What the plan says.** *"one indexed read per enumerated workspace, **inside the same enumeration
`sweep_expired_bodies` already walks**, reduced to the maximum age across workspaces and set on one
unlabelled gauge"*, and separately *"`sweep_expired_bodies` returns the number of rows deleted, so
increment by that amount after each pass, **in `worker.py`** rather than in `retention.py`"*.

**What is missing.** `sweep_expired_bodies` (`worker.py:233-265`) returns `int` and its docstring
pins two properties — *"`now` is read once per pass by the caller and passed in"* and *"an exception
propagates"*. Putting the gauge read inside it means either a second return value (breaking the
existing signature and `test_worker_jobs.py`'s callers) or a metric side effect inside a function the
module has kept side-effect-free. Meanwhile `expired_body_sweep` (`worker.py:325-328`) **discards**
`sweep_expired_bodies`' return today, so `retention_deleted_total` needs that call site changed too,
which the plan does not say. Two executors will make two different choices and one of them will
change a signature the plan's own acceptance criteria do not cover.

**Fix.** State the shape: `sweep_expired_bodies` gains a keyword-only `on_workspace_age:
Callable[[str, float], None] | None = None` observation seam in `retention.py:131-142`'s idiom, *or*
the age read moves into a separate small coroutine in `worker.py` that reuses `observed.current`.
Either is defensible; leaving it open is not. And name `expired_body_sweep` as the place where
`sweep_expired_bodies`' return value stops being discarded.

---

### 10. `03-01-PLAN.md` Task 4 — `queue.shutdown()` is permanent for the process and nothing resets it on the production path

**Severity: minor.**

The plan records the property — *"(b) `queue.shutdown()` is one-way for the process: `handoff()`
caches in a module global and only `reset_handoff()` clears it"* — and then addresses only the
"runs at most once" half. The half it leaves open: after `_stop_publisher` has run, **every**
subsequent `enqueue()` in that process takes the new `except asyncio.QueueShutDown` branch and
counts a drop, forever. In the suite this is masked because `purge_queues` calls `reset_handoff()` at
teardown (`conftest.py:226`) — but any test that enters the `lifespan` twice, and any future
in-process restart, silently drops every record with `reason="shutting_down"`.

**Fix.** One sentence in Task 4 telling the executor to call `reset_handoff()` from the lifespan's
`finally` after `_stop_publisher(application)` returns, with the reason written at the call: the
handoff belongs to a process's serving lifetime, and a lifespan that ends is the boundary. Then add
the acceptance criterion that two consecutive lifespans in one process both enqueue successfully.

---

### 11. `03-01-PLAN.md` Task 4 acceptance — `grep`-shaped criteria that contradict their own prose

**Severity: minor.**

Three of these, all mechanical and all resolvable by rewording:

- 03-02 Task 2: *"`grep -c "metadata_dropped_total" src/prope/call_ledger/drain.py` returns 0 for
  increment calls — the identifier may survive only inside an explanatory comment."* `grep -c` counts
  matching **lines**; if the identifier survives in a comment the count is not 0. Use
  `grep -c "metadata_dropped_total\.inc" src/prope/call_ledger/drain.py`.
- 03-03 Task 2: *"`grep -c ArithmeticError src/` returns 0"* — `grep -c` on a directory without `-r`
  exits 2 with "Is a directory" on this host. Use `grep -rc` or `grep -r … | wc -l`.
- 03-01 Task 4: *"`asyncio.create_task(run_publisher(` appears nowhere"* — after Task 4 the publisher
  is wrapped, but `run_publisher` is still referenced inside the job closure, so a naive grep for
  `run_publisher(` will hit. State the exact string being refused.

---

### 12. `03-06-PLAN.md` Task 2 — the ten-minute run cannot be executed inside one tool call, and the task's own `<automated>` verify does not run it

**Severity: minor.** (Adjacent to `03-PLAN-CRITIQUE-SPEC.md` finding 10, which covers the
verifier-facing half; this is the executor-facing half.)

Task 2 requires *"Run it once, in this task, and record the observed numbers in the SUMMARY"* — a
30,000-record, 600-second run plus PostgreSQL and RabbitMQ container startup. The executor's Bash
tool caps at **600,000 ms**, so a foreground `PROPE_RUN_LOAD=1 uv run pytest -m load -q` will time
out before the test finishes even in the best case. Meanwhile the task's own
`<verify><automated>uv run pytest tests/load/ -q</automated></verify>` runs with `PROPE_RUN_LOAD`
unset, so it **skips** the test it is supposed to verify and exits 0 either way.

Separately, the `Makefile` target's inline env prefix is POSIX-shell syntax:

```make
load:
	PROPE_RUN_LOAD=1 uv run pytest -m load -q
```

GNU Make 4.4.1 is on this host and defaults `SHELL` to `/bin/sh` when one exists, so this works from
Git Bash. It does not work if `make` is invoked where no `sh` is found. The existing `clean` target
already assumes `sh` (it uses `find … -exec`), so this is consistent rather than new — but the plan
should say so, since the phase's primary shell is PowerShell.

**Fix.** Change Task 2's `<automated>` to `PROPE_RUN_LOAD=1 uv run pytest -m load -q` and add an
instruction that the run must be launched with `run_in_background: true` and its result collected
later, because a 600-second test does not fit a foreground tool call. Add one line to the Makefile
comment recording the `sh` assumption, and add `load` to `.PHONY` (the plan does not mention it).

---

### 13. `files_modified` drift — one over-declaration and one under-declaration

**Severity: minor.** Neither is a wave hazard (both files are untouched by the sibling plan in the
same wave), but `files_modified` is what the orchestrator parallelises on and both should be exact.

- **03-01 declares `tests/conftest.py`** in `files_modified` and **no task edits it.** Task 2 adds a
  helper to `tests/broker/_helpers.py`, not to `conftest.py`. This also collides in spirit with
  03-06's acceptance criterion *"`git status --porcelain tests/conftest.py` is empty"*. Remove it, or
  say what it is for.
- **03-02 does not declare `src/prope/call_ledger/models.py`** but its action offers it as an edit
  site: *"`tests/architecture/test_schema_invariants.py` … Note that in **`models.py`'s
  neighbourhood** or in the writer's docstring."* Pick one — the writer's docstring — and delete the
  alternative, rather than adding a file to the frontmatter for an optional comment.

---

### 14. Small factual slips that cost an executor a minute each

**Severity: minor.**

- 03-01 Task 2 refers to *"the two `[REWRITE]` paragraphs at `:16-25` and `:179-184`"*. The line
  numbers are right; the marker is not — the string `[REWRITE]` appears nowhere in
  `src/prope/call_ledger/enqueue.py`. An executor greps for it, finds nothing, and re-reads.
- 03-01 Task 2 says *"seven call sites in `tests/broker/test_publish_confirm_failures.py` and one in
  `tests/broker/test_enqueue_reaches_a_committed_row.py`"*. The real counts are **five**
  `publish_record(` plus **one** `run_publisher(` in the first file (`:91`, `:120`, `:122`, `:145`,
  `:171`, `:227`) and one `run_publisher(` in the second (`:100`) — six and one. More importantly,
  those sites do not merely *"gain an argument"*: the second positional changes type from
  `CallRecordDraft` to `HandoffItem`, which the plan never says at the call sites.
- 03-02 Task 1 warns that moving two statements out of `text()` may drop
  `test_no_sql_interpolation.py`'s `found >= 5` floor below its threshold. `src/` currently holds
  **eighteen** `text()` constants; removing two leaves sixteen. The floor cannot go red, and the
  paragraph reads as a live risk that is not one. Harmless, but it invites an executor to "fix"
  something.
- 03-04 Task 2's acceptance criterion renames the worker test to
  `test_the_..._supervised_jobs_are_the_lock_files_residents` and has it assert **three**. The lock
  file's `deployment_target` names exactly two (`worker.py:73-78` quotes it: *"The retention job …
  and the drain both run in `worker`"*). A test named "the lock file's residents" that asserts a set
  the lock file does not contain is the kind of name that stops being checked. Rename it for the
  property instead — `test_the_worker_runs_exactly_the_three_jobs_this_file_composes` — and say in
  its docstring that the third is Phase 3's addition and is not in the lock file.

---

## Checked and dismissed — not findings

Recorded so they are not re-raised.

- **`asyncio.Queue.shutdown()` availability.** New in Python 3.13; `pyproject.toml:8` pins
  `>=3.13,<3.14` and the venv is cp313. Available. (The bare `python` on PATH is 3.14.2 — irrelevant,
  every command in the plans goes through `uv run`.)
- **`envelope.occurred_at` reachable from `_write_group`.** 03-02 Task 2 puts the `write_lag_seconds`
  observation in `_write_group` beside the `written_total` increment. `_write_group` receives
  `group: Sequence[tuple[AbstractIncomingMessage, CallRecordEnvelope]]` (`drain.py:261-264`) and
  `CallRecordEnvelope` declares `occurred_at: AwareDatetime` (`envelope.py:159`). Implementable as
  written.
- **`pg_insert(models.call_record)` and `written_at`.** The Core `Table` declares `written_at` as
  `nullable=False` with no default (`models.py:87`), and the DDL carries `DEFAULT now()`
  (`0002_call_record.py:88`). SQLAlchemy compiles the INSERT from the parameter dict's keys, so the
  column is simply omitted and the server default applies — the same behaviour the current `text()`
  statement gets.
- **`REGISTRY.get_sample_value` on an untouched unlabelled counter.** Returns `0.0`, not `None`, for
  unlabelled `Counter`s because the child is created at construction. 03-01's acceptance criterion is
  satisfiable. (It would *not* be for a labelled metric — none of the criteria asks for that.)
- **`ceiling_check_total`'s three label literals appearing at most once each in `src/`.**
  `grep -rn '"allowed"\|"refused"\|"failed_open"' src/` currently returns nothing. Satisfiable.
- **`deploy/` does not exist.** Correct — 03-04 creates it, `pyproject.toml`'s
  `[tool.hatch.build.targets.wheel] packages = ["src/prope"]` means it is not packaged, and
  `ruff.toml` does not lint YAML. No conflict.
- **Wave disjointness.** Verified against the six frontmatters directly, not against `COVERAGE.md`'s
  claim about them. Wave 2 (`03-02` / `03-03`) and wave 4 (`03-05` / `03-06`) are genuinely disjoint.
  The three cross-wave collisions `COVERAGE.md` names — `app.py`, `test_route_table.py`,
  `pyproject.toml` — are all serialised by the wave ordering.
- **`docker` off the bash PATH.** Every plan's `<context>` carries the
  `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"` note and the
  "testcontainers needs no PATH help" corollary. Confirmed: `which docker` fails, and the suite runs.

---

VERDICT: 3 blocker / 5 major / 6 minor
