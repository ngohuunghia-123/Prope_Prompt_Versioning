# Phase 04 — adversarial EXECUTABILITY critique of the plan set

**Written:** 2026-08-10 · **Role:** critic-exec · **Scope:** `04-01-PLAN.md` … `04-04-PLAN.md`, read
against the tree at `hina-dev` / `76039cd`.

The question this file answers is only: *where would a fresh executor with no memory of the planning
conversation get stuck, guess, or build the wrong thing?* Spec fidelity is `04-PLAN-CRITIQUE-SPEC.md`'s.

**Verified clean, so the findings below are not padded with things that are fine.** No plan hardcodes a
`down_revision` (04-01 Task 1 reads `uv run alembic heads` and says so twice). No surviving
`@$HOME/.claude/gsd-core/` reference anywhere in the set. No plan gates on `ruff format --check`, on a
`typecheck` target, or on `make check` — 04-01 explicitly refuses the last one because its `format`
target writes, which is correct (`Makefile:16`). Every `@` context path and every `read_first` file
exists on disk, including `docs/brainstorm/open_questions/OQ-031.md` with `status: open` and a `blocks`
list that satisfies 04-01's acceptance criterion verbatim. Line citations into existing files are
accurate to within a line or two in ~25 spot checks (`ddl.py:56-86`, `ddl.py:105-119`,
`test_append_only_privilege.py:78-82/85-97/121-135/189-211/214-252`, `test_tenant_coverage.py:151`,
`test_schema_invariants.py:14/152/206-237`, `conftest.py:93-98/170-179`, `0003:216-221/246-251`,
`0004:12-27/47-55/57-81`, `test_publish_confirm_failures.py:55-63/66-78/200-237/239-250`,
`test_eval_no_body_boundary.py:48-53/141-152/157-159`, `schemas.py:442`, `session_auth.py:77`,
`alembic.ini:20-33`). The 31-name derivation was re-checked against the five writing modules'
`outputs` blocks and is 5 + 8 + 4 + 4 + 10 = 31 with `user_tombstoned` already inside
`access-control.lock.yml:110-111` — no rounding was needed and none was done. Declared `wave:` file
lists are textually disjoint (wave 1 = 04-01 alone, wave 2 = 04-02 alone, wave 3 = 04-03 + 04-04 with
no shared path). Findings 2, 3 and 8 are about what those lists *omit*, not about what they contain.

---

## Blockers

### 1. `04-03-PLAN.md` § Task 1, test 3 — `test_a_gap_in_seq_is_not_a_missing_event` cannot pass as specified

**Severity: blocker.**

04-03 Task 1's `<behavior>` says:

> A refused append between two successful ones leaves the later event with a **strictly greater** `seq`
> than the earlier, with a gap, and the test states that the gap is correct rather than a defect.

and the `<action>` spells the mechanism out — *"write a valid event; then, in its **own** transaction,
attempt an append the validator refuses and let it roll back; then write a second valid event. Assert
`second.seq > first.seq` and assert that `second.seq - first.seq` is **greater than one**"*.

That gap does not exist. `04-02-PLAN.md`'s own `must_haves.truths` requires the opposite:

> An event whose action is not in the registry raises HistoryAppendRejected with reason
> unknown_action, **before any SQL is issued**

and `record_event` is specified as `check_event`, then one `session.execute`. A validator refusal
therefore never reaches the `INSERT`, `nextval` is never called, and no sequence value is consumed.
`second.seq - first.seq` will be exactly `1` and the assertion fails on every run. The same error is
baked into 04-03's `must_haves.truths` (*"A refused append consumes a sequence value that is never
returned"*) and into its acceptance criterion (*"a refused append between two successful ones leaves a
gap greater than one"*).

The underlying research is right and the plan mis-translated it: `04-RESEARCH.md` § Pitfall 5 says a
**rolled-back** append consumes a value — true only when the statement executed and the transaction
then aborted, which is not what `check_event` does.

**Fix.** Make the middle step one that reaches the engine and then aborts. Two candidates, either of
which restores the property: (a) a valid `record_event` on a caller-opened transaction that is then
abandoned by a sentinel raise — the same shape 04-02 Task 3 test 2 already builds; or (b) a
hand-written `INSERT` naming an unregistered action, refused by `fk_history_event_action`, which burns
the identity value before the constraint fires. Then correct the `must_haves` truth and the acceptance
criterion to say *a rolled-back **insert***, not *a refused append*, and keep the "PH-05 guarantees
gaps" narrative only if the executor also demonstrates a PH-05 path that issues SQL.

---

### 2. No plan says where a test gets the `registry` argument `record_event` requires — and two parallel plans both need it

**Severity: blocker.** Affects `04-02-PLAN.md` § Task 3, `04-03-PLAN.md` § Task 1, `04-04-PLAN.md`
§ Task 2 (test 5) and § Task 3.

04-02 fixes the signature as `async def record_event(session: AsyncSession, event: HistoryEventDraft,
registry: Mapping[str, RegisteredAction]) -> str` and is emphatic that the mapping is a parameter:

> **`register` the parameter, not a global**: the registry is passed in, because Phase 5 owns the
> process-start global and a module-level mutable default here is exactly the shape ADR-0038 warns
> about.

Nine specified tests across three plans then call `record_event` and **not one of them is told how to
obtain that mapping.** 04-02's unit test is the only place a registry is constructed, and it is
deliberately a *fake* one (*"use **invented action names** (`fixture_thing_created`, …) with a comment
saying they are deliberately not real vocabulary members"*), so it cannot serve the integration tests —
04-02 Task 3 test 4 explicitly requires the real seeded data (*"`missing_reason` must use one of the
three real actions whose registry row requires one, so the test exercises the seeded data rather than a
fixture"*). `tests/property_history/__init__.py`, written in 04-01 Task 2, predates
`load_action_registry` and declares no such helper; no plan lists a `conftest.py` under `tests/` beyond
04-01's truncate edit.

Two consequences, and the second is the damaging one. Each executor invents a different shape (a
module-level `await load_action_registry(...)`, a session fixture, a hand-built `MappingProxyType`), so
the three plans' history tests stop resembling each other. And **04-03 and 04-04 are the same wave**: if
either one lands a `registry` fixture in `tests/conftest.py` or a new `tests/property_history/conftest.py`
to avoid repeating itself, that is a write to a file neither plan declares and the orchestrator's
disjointness check cannot see it.

**Fix.** Assign the helper to exactly one plan and one already-declared file. The natural home is
`tests/property_history/__init__.py` — add `async def load_registry(app_sessionmaker) -> Mapping[str,
RegisteredAction]` (a plain session, no `workspace_transaction`, per 04-02's own rule) in **04-02
Task 2**, and add that path to 04-02's `files_modified`, which currently does not list it. Then have
04-03 and 04-04 name that helper in their `read_first` rather than each solving it.

---

## Major

### 3. `04-01-PLAN.md` frontmatter — `files_modified` omits the two files the `truncate_ledger` rename touches

**Severity: major.**

04-01 Task 1 instructs:

> Rename the constant to `LIST_TRUNCATABLE_TABLES` and the fixture to `truncate_owned_tables`: the
> fixture is autouse and is never requested by name in any test — verified, the only other occurrences
> are prose in four docstrings — so the rename is a **prose edit across three files** with no
> behavioural risk

The three files are `tests/conftest.py` (line 56), `tests/integration/test_write_path.py`
(lines 25, 196, 418) and `tests/integration/test_reprice_only_unpriced.py` (line 302) — confirmed by
grep. `files_modified` lists only `tests/conftest.py`. The plan names the count ("three files") in its
own prose and then declares one.

Wave 1 runs alone so nothing collides *today*, but `files_modified` is the orchestrator's only input for
parallelisation and for the "did this plan write outside its declaration" check, and phase 3's execution
also lives in `tests/integration/`.

**Fix.** Add `tests/integration/test_write_path.py` and `tests/integration/test_reprice_only_unpriced.py`
to 04-01's `files_modified` and to Task 1's `<files>`; or drop the rename and keep `truncate_ledger`,
which the plan itself concedes is only a naming improvement.

---

### 4. `04-03-PLAN.md` § Task 2 tells the executor to delete a docstring paragraph that `04-01-PLAN.md` never asks anyone to write

**Severity: major.**

04-03 Task 2 test 3:

> **if this test starts failing, do not "fix" it.** It failing means PostgreSQL changed the rule or
> somebody added a guard … delete the test and **delete the boundary note in the revision's docstring**
> in the same change.

and the acceptance criterion repeats it: *"The file carries the do-not-fix-this instruction, naming the
revision docstring that must be deleted with it."* Its `read_first` points at *"`alembic/versions/000N_…`
as written in plan 04-01 — the `seq` column's comment, which this file is the assertion for."*

04-01 specifies the revision's docstring as six enumerated bold-led paragraphs — what the revision is,
D-53, D-50, what it enforces and deliberately does not, the rig edits, types — and specifies the `seq`
column comment as covering the `bigserial`-is-a-default argument, `CACHE 1`, monotonic-is-not-gapless
and assignment-order-is-not-commit-order. **`OVERRIDING SYSTEM VALUE` appears nowhere in 04-01.** The
executor of 04-03 will search the revision for a boundary note, find none, and either invent one (a
cross-plan edit to a file 04-03's own `<context>` forbids: *"Do not edit `src/prope/property_history/`
… an unplanned edit here is also a collision"*, and the same logic applies to `alembic/`) or write a
dangling reference into a security test.

**Fix.** Add a seventh docstring paragraph to 04-01 Task 1's spec — *the guarantee `GENERATED ALWAYS`
gives and the documented `OVERRIDING SYSTEM VALUE` escape hatch it does not close, with
`tests/security/test_history_seq_cannot_be_supplied.py` and
`tests/architecture/test_no_overriding_system_value.py` named as the two halves that record it* — which
is exactly the shape 04-01 already uses for the D-62 boundary and plan 04-04. Then 04-03's instruction
resolves.

---

### 5. `04-01-PLAN.md` § Task 1 — widening `test_migration_chain.py` to bound schema parameters is impossible through the helper the file has

**Severity: major.**

04-01 Task 1:

> widen the three statements to `schemaname = ANY(:schemas)` / `table_schema = ANY(:schemas)` **with
> the schemas bound**

Every one of those three statements is executed through `_query_all` at
`tests/integration/test_migration_chain.py:101-108`:

```python
async def _query_all(url: str, *statements):
    engine = build_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            return [(await connection.execute(statement)).all() for statement in statements]
```

`connection.execute(statement)` takes no parameter dict, and the signature is `*statements` — there is
nowhere to put `{"schemas": [...]}` without changing the helper. The plan never mentions `_query_all`.
An executor either rewrites the helper (an unplanned change to a shared test utility in the same task
as a migration) or silently ignores "with the schemas bound".

**Fix.** Either name the `_query_all` signature change explicitly in the `<action>` — it is a small,
defensible edit — or write the three predicates as two-schema literals
(`WHERE schemaname IN ('history', 'ledger')`), which needs no parameter plumbing and matches how the
file writes SQL today.

---

### 6. `04-02-PLAN.md` § context promises a "pydantic scope" deviation that no task explains, and the `<output>` block requires the SUMMARY to state it

**Severity: major.**

`<context>`:

> This plan records two deviations and raises no OQ for either, because both are mechanism deviations
> with an identical end state: `pydantic`'s scope (**below, Task 3**) and the `test_ref` path for AC-5's
> transaction half

Task 3 does not mention pydantic. Neither does Task 1 or Task 2. The word appears exactly twice in the
plan: in that sentence and in the `<output>` block, which then instructs the executor to write a SUMMARY
stating *"the two deviations recorded without an OQ (pydantic's narrowed scope, and AC-5's `test_ref`
path …)"*. The executor is required to report a deviation it was never told the content of, and the
verifier is required to check it.

**Fix.** Write the deviation out where it belongs (presumably: the lock file expects pydantic models on
this module's surface and this phase ships frozen dataclasses because the module has no HTTP surface —
but that is a guess, which is the problem), or delete both references and leave one declared deviation.

---

### 7. `04-01-PLAN.md` § Task 1 — the two-schema pristine-cluster assertion contradicts itself and leaves the comparison shape unspecified

**Severity: major.**

The `<action>` says *"Convert `LEDGER_TABLES` into an explicit two-schema mapping
(`{"history": ("history_action_registry", "history_event"), "ledger": (…six…)}`)"*. The acceptance
criterion for the same edit says:

> Behaviour: a pristine cluster upgraded to head holds exactly two tables in `history` and six in
> `ledger`, **asserted from `pg_tables` rather than from a list the test built**

Those are opposite instructions, and the existing assertion —
`assert tuple(row[0] for row in tables) == LEDGER_TABLES` at `test_migration_chain.py:131`, over a query
that selects `tablename` only, ordered by `tablename` — cannot survive either reading unchanged: with
two schemas in play the executor must decide whether to compare schema-qualified names, to compare
per-schema tuples, or to change `ORDER BY tablename` to `ORDER BY schemaname, tablename`. None of the
three is stated. This is the tracer plan, and the shape chosen here is the one phases 5–24 extend.

**Fix.** Pick one. The mapping form plus `SELECT schemaname, tablename … ORDER BY schemaname, tablename`
compared against the mapping flattened is the smallest change that preserves the existing constant's
stated argument (*"a table appearing or vanishing from a pristine upgrade is an edit somebody made"*).
Then delete the "rather than from a list the test built" clause, which contradicts it.

---

### 8. `04-04-PLAN.md` writes `.planning/WINDOWS.md` and does not declare it

**Severity: major.**

"Artifacts this plan produces":

> **Appended to `.planning/WINDOWS.md` by the executor**: the `request_id` allow-list omission in
> `src/prope/call_ledger/schemas.py:442`, as a Broken Window, in both the table and the JSON block with
> `open_count` corrected

`files_modified` lists two test files and nothing else, and the `<verification>` block asserts *"this
plan writes only under `tests/` and appends to `.planning/WINDOWS.md`"* — the plan knows it writes a
third file and still does not declare it. 04-03 does not touch `WINDOWS.md`, so wave 3 does not collide
today; the defect is that the declaration the orchestrator parallelises on is knowingly incomplete, and
`WINDOWS.md` is a file with a hand-maintained `open_count` that two concurrent appends would corrupt.

The `request_id` finding itself is real and correctly located: `src/prope/call_ledger/schemas.py:442`
is `log.info(event, reason=str(code), request_id=request_id)` and `request_id` is not in
`LOGGABLE_FIELDS` (`src/prope/observability.py:49-67`).

**Fix.** Add `.planning/WINDOWS.md` to 04-04's `files_modified`.

---

## Minor

### 9. `04-01-PLAN.md` § Task 1 — the claim that `len(declared) == 6` needs no edit contradicts the instruction two sentences earlier

> Replace the module constant `SCHEMA = "ledger"` with a module-level `GENERIC_SCHEMAS = ("history",
> "ledger")` … **do not leave both a module constant and a parameter**

then

> `len(declared) == 6` survives without an edit because it filters `models.metadata.tables` on
> `table.schema == SCHEMA`

`test_schema_invariants.py:221` is literally `table.schema == SCHEMA`, so removing the constant *forces*
an edit to that line. The *count* survives; the *line* does not. Say "the count is unaffected; the three
ledger-specific tests each carry a local `"ledger"`, including the `table.schema ==` filter at line 221".

### 10. `04-02-PLAN.md` § Task 3 `read_first` — wrong line range for the load-bearing sentence

> `src/prope/call_ledger/writer.py` lines 9-15 and **171-186** — … the signature's contract line *"This
> function does not commit; the caller's context manager owns the transaction boundary …"*

`writer.py:171-186` is the `UNPRICED_WORKLIST` query constant. The quoted sentence is at
`writer.py:217`. The 9-15 half is correct.

### 11. `04-02-PLAN.md` § Task 2 acceptance — the empty-registry `RuntimeError` proof needs an owner-role *session* the rig does not expose

> provable by running it inside a transaction that has deleted the rows as the owner and is then rolled
> back

`load_action_registry` takes an `AsyncSession`. `tests/conftest.py` exposes `migrate_engine` (an
`AsyncEngine`) and `app_sessionmaker` — there is no owner-role sessionmaker, and `prope_app` cannot
`DELETE` from the registry (04-01 Task 3 test 4 asserts exactly that). The executor must build one with
`build_sessionmaker(migrate_engine)` from `prope.db.engine`. Say so, or the executor will reach for
`app_sessionmaker` and discover the privilege refusal instead of the `RuntimeError`.

### 12. `04-01-PLAN.md` § Task 2 — the stated reason for the factories' placement is undone by the next paragraph

The rejection of `tests/unit/__init__.py` is:

> which already imports `prope.call_ledger.domain` and `prope.call_ledger.seams` at module scope —
> adding history factories there would make one helper module import two bounded contexts

The very next paragraph then instructs `from tests.unit import WORKSPACE_A, WORKSPACE_B, WORKSPACE_C,
DAY_1, day`, which makes `tests/property_history/__init__.py` import `tests.unit`, which imports both
call-ledger modules at module scope. The coupling is identical, only pointed the other way. Either
accept it and say so, or move the four shared constants somewhere neutral.

### 13. `INSERT_HISTORY_EVENT` is defined twice under one name with no sync rule

`04-01-PLAN.md` Task 2 creates it as an eleven-column `text()` constant in
`tests/property_history/__init__.py`; `04-02-PLAN.md` Task 3 creates a production constant of the same
name and the same eleven columns in `src/prope/property_history/append.py`. Nothing says whether the
test helper should later be retired in favour of `record_event`, and 04-04 seeds through one while
04-03 writes through the other. A column added in phase 5 lands in one of the two.

### 14. `04-01-PLAN.md` § Task 1 — the registry-count idempotency criterion has an unreachable failure mode

> Behaviour: running the chain a second time … leaves the column snapshot, the policy snapshot **and
> the registry row count** byte-identical — a doubled seed is a failure

`test_running_the_chain_a_second_time_is_a_no_op` re-runs `alembic upgrade head` against an
already-stamped cluster, so no revision body executes and the seed cannot double by that path. The
assertion is harmless and cheap, but the stated rationale ("a doubled seed is a red test rather than a
discovery") does not describe anything this test can catch. Keep the assertion; fix the sentence, or the
next reader will believe a guarantee that is not there.

### 15. `04-03-PLAN.md` § Task 3 acceptance — one of the two offered proofs is not a test

> provable by a temporary local edit reverted before commit, **or** by a unit-level assertion over a
> parsed snippet rather than over a real file

The first leaves nothing in the suite and is not runnable in CI. Specify the second (parse a snippet
string with `ast` and assert the gate's predicate rejects it) and drop the alternative.

### 16. `04-03-PLAN.md` § Task 2 test 3 — the collision consequence written into the docstring will not be what the engine does

> a supplied `seq` above the sequence's current value does **not** advance the sequence, so the next
> engine-assigned value collides with it and `uq_history_event_seq` refuses that insert

True in general, unreachable in this rig: `tests/conftest.py:178`'s `TRUNCATE … RESTART IDENTITY` resets
the identity sequence before every test, and the test supplies a `seq` "far above anything the sequence
has issued", so the next `record_event` always gets a small value and never collides. The plan hedges
correctly at the assertion (*"Take whichever of the two the engine actually does"*) but the prose that
goes into the test docstring asserts the branch that cannot happen.

### 17. `04-01-PLAN.md` § Task 1 is oversized, and its own overrun fallback does not exist

One task produces: a ~250-line hand-written revision with a 31-row seed, plus edits to four pre-existing
files — `conftest.py` (predicate widening, two renames, an eighth docstring paragraph),
`test_tenant_coverage.py` (three edits including the project's first `GLOBAL_TABLES` entry),
`test_schema_invariants.py` (five-way parameterisation, four function renames, constant removal) and
`test_migration_chain.py` (two-schema conversion of four constants). The estimate comment says:

> If the revision overruns, do NOT split it — D-46 and D-59 both require one applied migration. Split
> the rig edits (**Task 1b**) out instead.

There is no Task 1b, and the rig edits are not separable at run time — dropping `"history"` from
`EXPECTED_ABSENT_SCHEMAS` must land in the same change as `CREATE SCHEMA history` or the suite is red,
which the plan itself argues at length. The fallback as written is not executable.

### 18. `04-01-PLAN.md` frontmatter declares a file it forbids the executor to write

`files_modified` includes `docs/brainstorm/open_questions/OQ-031.md`, and Task 1's `<files>` repeats it,
while the `<action>` says *"The executor does not re-raise it and must not allocate a second id … read
it, confirm it is present and `status: open`"*. The plan explains the reasoning (*"so the orchestrator's
collision check sees this phase's whole `docs/` footprint"*), but the effect is that a read-only path is
reserved as a write, and 04-01's own verification asserts `git status --porcelain docs/…` is empty —
i.e. the declared file must **not** change. Move it to `read_first`.

### 19. `04-02-PLAN.md` "Artifacts" — a false statement about the dependency set

> **No dependency change**; `python-ulid` and `pydantic` go from *pinned and unused* to *pinned and
> used* without moving

Both are already used: `src/prope/call_ledger/api.py:433` and `src/prope/call_ledger/schemas.py:441`
both build `f"{PREFIX}{ULID()}"`, and `schemas.py` is a pydantic module. The "no dependency change"
half is correct and is what matters; delete the rest.

### 20. Wave 3's two plans each run the whole suite, concurrently, on a Windows Docker host

`04-03` and `04-04` both carry `uv run pytest -q` **across the whole suite** as an acceptance criterion
and are declared `wave: 3`. A full run starts the session `postgres:17`, the session
`rabbitmq:4.3-management`, and `test_migration_chain.py`'s second module-scoped `postgres:17` — so two
concurrent runs are six containers plus image pulls. Not a correctness defect, and testcontainers
reaches the daemon without the PATH export the plans correctly document, but it is the most expensive
thing in the phase and neither plan mentions it. Consider scoping the parallel acceptance to each
plan's own files and running the whole suite once, serially, after the wave.

---

VERDICT: 2 blocker / 6 major / 12 minor
