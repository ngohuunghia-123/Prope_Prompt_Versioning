---
phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
plan: 02
subsystem: backend
tags: [postgres, alembic, rls, sqlalchemy, retention, concurrency, upsert, tenancy]

# Dependency graph
requires:
  - phase: 01-data-model-pricing-and-retention
    provides: "the five ledger tables and their guarantee stack, alembic/ddl.py's emitters, write_records, delete_expired_bodies, workspace_transaction, DEFAULT_RETENTION_WINDOW, and the session-scoped PostgreSQL 17 rig"
provides:
  - "ledger.workspace_retention — the sixth ledger table (D-09), with pk_workspace_retention, ck_workspace_retention_window_is_positive, its ADR-0045 tenant policy and its SELECT/INSERT/UPDATE grant to prope_app plus SELECT to prope_report"
  - "prope.call_ledger.retention_settings.read_retention_window — the real per-workspace resolver plan 02-01's drain accepts through retention_for; absence of a row is the 30-day default, never an error (D-11)"
  - "prope.call_ledger.retention_settings.set_retention_window — the upsert plan 02-05's PUT /api/v1/workspaces/{id}/retention will call; surfaces the engine's refusal of a non-positive window rather than clamping"
  - "prope.call_ledger.writer.period_month(at) — the one UTC month helper both write_records and plan 02-04's check_spend_ceiling call"
  - "UPSERT_WORKSPACE_SPEND carrying the one-currency invariant in its DO UPDATE ... WHERE (WARN-2 closed), so a zero rowcount is a real refusal"
  - "delete_expired_bodies argument guards on chunk_size and max_chunks (WARN-1 closed), ahead of D-12 wiring an operator-supplied value in plan 02-03"
  - "docs/brainstorm/open_questions/OQ-018.md — the declared deviation from call-ledger.lock.yml data.owns"
  - "prope.call_ledger.models.workspace_retention — the sixth Core table object"
affects: [02-03-worker-supervisor, 02-04-seams-and-ceiling, 02-05-management-routes, 03-fallback-and-upsert]

actuals:
  tokens: 28621
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "One table, one revision, whole guarantee stack — extended to a table added after the founding set, with the coverage walk adopting it untold"
    - "A stored value that demotes a constant to 'what absence returns', rather than adding a second mechanism beside it"
    - "A concurrency invariant carried into the statement's own WHERE, so a zero rowcount is the refusal (the repricing.UPDATE_TO_PRICED technique, second use)"
    - "Assert the ABSENCE of a guarantee, so a knowing exception to database-first is recorded rather than believed"
    - "Argument guards that raise before any transaction opens, proved with a sessionmaker that explodes when called"

key-files:
  created:
    - alembic/versions/0004_workspace_retention.py
    - src/prope/call_ledger/retention_settings.py
    - tests/security/test_eval_no_body_boundary.py
    - tests/integration/test_workspace_retention_setting.py
    - tests/integration/test_spend_currency_invariant.py
    - tests/unit/test_period_month.py
    - tests/unit/test_retention_argument_guards.py
    - docs/brainstorm/open_questions/OQ-018.md
  modified:
    - src/prope/call_ledger/models.py
    - src/prope/call_ledger/writer.py
    - src/prope/call_ledger/retention.py
    - tests/integration/test_migration_chain.py
    - tests/architecture/test_schema_invariants.py

key-decisions:
  - "ledger.workspace_retention is a sixth table, not a column on spend_ceiling and not a key/value settings row (D-09) — and it is work beyond both of this phase's named requirements, CL-06 and CL-09, stated out loud as D-12 requires"
  - "Migration 0004 does NOT add a BEFORE INSERT trigger enforcing A-055's no-body rule. Recorded as a knowing exception to the database-first pattern, with the absence asserted by tests/security/test_eval_no_body_boundary.py"
  - "grant_table takes its report_select default of True on the new table, resolving Phase 1's carried-forward discretion item: a retention window is a policy setting rather than a body, and ADR-0037 already records prope_report as a full-read credential"
  - "The WARN-2 fix ADDS the invariant to the upsert's WHERE and KEEPS the pre-read, the same both-places posture repricing.UPDATE_TO_PRICED already takes; the pre-read gives the clearer message on the sequential path without spending a doomed transaction"
  - "period_month takes an instant rather than a CallRecordDraft, because plan 02-04's check_spend_ceiling has no record and must call the same function"

metrics:
  duration: ~65 min
  completed: 2026-08-10

status: complete
---

# Phase 2 Plan 02: The Retention Setting and Three Phase 1 Carry-Forwards Summary

`ledger.workspace_retention` plus its read and write path, so the drain has a real per-workspace
window with a real default — and the three Phase 1 findings (CR-01's neighbour WARN-1, WARN-2, and
Pitfall 8's month helper) that stop being theoretical the moment a drain exists.

## What Was Built

**The sixth ledger table.** `alembic/versions/0004_workspace_retention.py` creates
`ledger.workspace_retention` — `workspace_id text` as the primary key, `retention_window interval NOT
NULL` with `ck_workspace_retention_window_is_positive`, `updated_by text NOT NULL`, `updated_at
timestamptz NOT NULL DEFAULT now()` — with `enable_tenant_rls` and `grant_table(app_privileges=
["SELECT", "INSERT", "UPDATE"])` in the same revision. `interval` rather than an integer of days is
load-bearing twice: it makes the positivity CHECK a plain comparison, and asyncpg hands the value back
as a `timedelta`, so the reader does no unit arithmetic that could disagree with
`writer.DEFAULT_RETENTION_WINDOW`.

**The claim that the coverage walk adopts a new table untold, tested for the first time.** This is
the first table added since Phase 1's five. `tests/architecture/test_tenant_coverage.py` discovers
tables from `pg_class` and `tests/conftest.py`'s truncate fixture from `pg_tables`; **neither was
edited**, and both cover the table. Had the revision forgotten `enable_tenant_rls`, the walk would
have gone red on its own.

**`retention_settings.py`.** `read_retention_window(sessionmaker, workspace_id) -> timedelta` is a
primary-key probe — one index probe, one heap fetch, no sort, no filter — which is what makes D-11's
per-group read affordable inside the drain's window. `set_retention_window(sessionmaker,
workspace_id, window, *, updated_by, now)` is an `INSERT ... ON CONFLICT (workspace_id) DO UPDATE`.
Both open their own `workspace_transaction` and never take a caller's session, and both take the clock
as an argument rather than reading one, matching `retention.py`'s stated rule.
`DEFAULT_RETENTION_WINDOW` is imported from `writer`; there is no second `30` in the file.

**The three carry-forwards.**

| Finding | Was | Is now |
|---------|-----|--------|
| Pitfall 8 | `writer._period_month(draft)`, private, taking a draft | `writer.period_month(at)`, public, taking an instant — one function both `write_records` and plan 02-04's `check_spend_ceiling` call |
| WARN-2 | `workspace_spend.currency` read, then upserted — a race the CHECK cannot see | The invariant is in `UPSERT_WORKSPACE_SPEND`'s `DO UPDATE ... WHERE`; a conflicting currency makes the row not match, `rowcount` is 0, and `write_records` raises naming both currencies |
| WARN-1 | `delete_expired_bodies(chunk_size=0)` loops forever | `ValueError` on `chunk_size < 1` and on `max_chunks` not `None` and `< 1`, raised before any transaction opens |

**OQ-018.** The deviation from `docs/modules/call-ledger.lock.yml` `data.owns` is raised as an open
question naming the field, the conflict, and the two things a resolver must choose between. No file
under `docs/modules/`, `docs/architecture/` or `docs/adr/` was modified — verified:
`git status --porcelain docs/modules docs/architecture docs/adr` produces no output.

## Work Beyond CL-06 and CL-09 — Stated Out Loud

**Neither CL-06 nor CL-09 asks for `ledger.workspace_retention`.** CL-06 is the spend ceiling refusing
eval runs; CL-09 is an eval-case usage row priced and counted with no body stored. Neither mentions a
per-workspace retention window, a sixth table, or a settings read.

The table is here because D-09 put it here, and because
`PUT /api/v1/workspaces/{id}/retention` is one of the `/api/v1` routes the ROADMAP names for this
phase. A route that persists a window the writer never reads would be a route that lies for a phase,
which is what D-11 exists to prevent. D-12 requires this to be said rather than absorbed, and this
section is the saying.

The same disclosure covers the three carry-forwards: WARN-1 and WARN-2 are Phase 1 verifier findings,
not requirements of this phase. They land here because Phase 2 is where their triggers arrive — an
operator-supplied `chunk_size` (plan 02-03) and a drain that can run `write_records` concurrently.

## The A-055 Database-Guard Exception, In Its Own Words

A-055 says no `call_body` row may ever exist for a `source = 'eval'` call record. **There is no
database constraint behind that rule, and migration 0004 deliberately does not add one.**

A `CHECK` cannot reach another table, so the only shape that would work is a `BEFORE INSERT` trigger
on `call_body` that looks up the referenced `call_record.source` on every insert. It is refused for
three reasons, recorded in the revision docstring as a **knowing exception to this project's
database-first pattern** rather than left as an oversight:

1. It puts a per-row index probe on the highest-volume insert path in the system. `call_body` takes
   one row per gateway call and the drain inserts them in batches.
2. `write_records` is already the single choke point and already refuses, in the loop, before any row
   is built. Nothing else in this module writes `ledger.call_body`.
3. `docs/modules/call-ledger.lock.yml` never asked for the trigger, and `.planning/BSP-LINK.md`
   forbids inventing schema the spec did not declare.

**An exception that is merely written down is a belief, so both halves are asserted** in
`tests/security/test_eval_no_body_boundary.py`. Half one: `write_records` refuses an eval draft
carrying a body with a `ValueError` naming the `call_id` and A-055 — and the refusal is whole-batch,
proved by writing a legal batch-mate alongside and then finding neither landed. Half two: a
hand-written `INSERT INTO ledger.call_body` for a `source = 'eval'` record, executed as
`prope_migrate` (the owner, exempt from the tenant policy, so a success is unambiguous evidence about
the table's constraints), **succeeds**.

That second test is written to fail loudly if the boundary ever moves. Its message says so: if it
starts failing, somebody added the guard, and the test and the exception note in revision 0004 should
be deleted together. A later phase that builds a body reader inherits a recorded boundary — the
guarantee holds exactly as far as `write_records` reaches, and no further.

This is the plan's one `verification: backstop` truth, and it is confirmed by explicit positive
evidence rather than by absence of contrary evidence.

## Key Implementation Details

**The one-currency invariant, and why the pre-read stayed.** The `WHERE` on the `DO UPDATE` branch is
three disjuncts — the stored currency is NULL, the incoming one is NULL, or they are equal — because
those are the three cases that are *not* a conflict. A batch that prices nothing still has to bump
`call_count` against a labelled row, and that is the disjunct most easily lost if the predicate is
written as a plain equality; it has its own test. The Phase 1 pre-read was kept alongside rather than
replaced, the same both-places posture `repricing.UPDATE_TO_PRICED` already takes: it produces the
clearer message on the ordinary sequential path and does so without spending a doomed transaction.
On the racing path the pre-read is stale by one commit, and the zero rowcount is what catches it —
`write_records` then re-reads the stored currency (READ COMMITTED gives the new statement a fresh
snapshot, so the committed conflicting row is visible) and raises naming the workspace, the month,
both currencies and the rule, with no invented figure.

**WARN-2 is proved three ways, because one would not be enough.** A statement-level test drives
`UPSERT_WORKSPACE_SPEND` directly against a seeded USD row and asserts `rowcount == 0` for VND; a
negative control asserts `rowcount == 1` when the currencies agree, so an always-false `WHERE` cannot
pass; and the race is reproduced twice — once with the interleave pinned by hand (a stale reader sees
no row, another transaction commits USD underneath it, the stale writer's VND upsert is refused) and
once with two genuinely overlapping `write_records` calls through `asyncio.gather`, asserting exactly
one committed and one refused and that the stored label equals the currency of the records the total
is made of.

**D-10 asserted as a consequence, not described as one.** `test_shortening_a_window_leaves_already_
stamped_expiries_alone` writes a body under the 30-day default, shortens the workspace to 7 days,
writes a second body, and reads both `expires_at` values through `migrate_engine`. The earlier body
keeps day-5 + 30 days; the later gets day-5 + 7. So a workspace tightening its policy waits up to the
**old** window for what it already has, and `oldest_body_age_seconds` reads above the new window
meanwhile. No backfill exists and none was built: rewriting those stamps is an `UPDATE` on
`ledger.call_body`, and Phase 1 granted `prope_app` `SELECT`, `INSERT`, `DELETE` there and
deliberately no `UPDATE`.

**The companion invariant from the assumption-delta decision.** A workspace with no row and a
workspace whose row equals the default are asserted indistinguishable to every caller. That is what
makes `DEFAULT_RETENTION_WINDOW` a demoted constant — one variant of the general case — rather than a
second source of truth standing beside the table.

**The argument guards are proved structurally.** A test cannot assert "it did not hang" (a hanging
test does not fail, it stops the suite). So the guards are handed an `_ExplodingSessionmaker` that
raises the instant anything calls it; `workspace_transaction` calls `sessionmaker()` as its first act,
so a guard placed after the loop began would surface as that `AssertionError` instead of the
`ValueError` under test. A negative control asserts `max_chunks=None` — every production call site —
still reaches the unbounded run, and another asserts `chunk_size=1, max_chunks=1` is accepted, so the
boundary stays on the accepted side.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Two test-rig lists name the ledger table set explicitly and had to be updated**

- **Found during:** Task 1
- **Issue:** The plan's acceptance criteria require that no list in `tests/architecture/test_tenant_
  coverage.py` or `tests/conftest.py` be edited — and neither was. But two *other* tests pin the table
  set by hand and go red when a sixth table appears: `tests/integration/test_migration_chain.py`'s
  `LEDGER_TABLES` tuple (asserted against a pristine upgrade) and
  `tests/architecture/test_schema_invariants.py`'s `assert len(declared) == 5` in the models drift
  guard. Neither is in the plan's `files_modified`.
- **Fix:** `workspace_retention` added to `LEDGER_TABLES` in alphabetical position with a comment
  naming revision 0004; `== 5` became `== 6` with a comment naming D-09 and OQ-018. Both counts are
  deliberately still pinned rather than derived — a drift guard that computes its own expectation
  guards nothing.
- **Files modified:** `tests/integration/test_migration_chain.py`,
  `tests/architecture/test_schema_invariants.py`
- **Commit:** `d4acec6`

**2. [Rule 1 - Bug] `period_month` was shadowed by a loop variable of the same name**

- **Found during:** Task 3
- **Issue:** `write_records`' aggregate loop reads `for period_month, bucket in months.items():`.
  Promoting `_period_month` to a module-level `period_month` made that loop variable shadow the
  function inside the loop body — silent today, and a `TypeError` waiting for the first person who
  calls the helper from inside it.
- **Fix:** Loop variable renamed to `month`, with a comment saying why.
- **Files modified:** `src/prope/call_ledger/writer.py`
- **Commit:** `1b3cab2`

**3. [Rule 1 - Bug] The Phase 2 `deferred-items.md` entry on `ruff format --check` had the cause backwards**

- **Found during:** Task 3 (verification)
- **Issue:** Plan 02-01's entry states that `pyproject.toml` declares no `[tool.ruff]` section so
  ruff's default `line-length = 88` applies. **A `ruff.toml` exists at the repo root and sets
  `line-length = 120`** with `[lint] ignore = ["E501"]`. That inverts the diff's direction: the
  formatter does not want to break long lines, it wants to join wrapped ones back up to 120. Left
  uncorrected, the next reader would try to fix it by adding a `line-length` that is already there.
- **Fix:** Entry corrected in place, with the counts updated and the actual decision named — pick
  which of the two line lengths the repo means (100 to match the prose-wrapped house style every
  module docstring is written in, or keep 120 and reformat once).
- **Files modified:**
  `.planning/phases/02-seams-enqueue-the-broker-drain-and-the-ceiling/deferred-items.md`
- **Commit:** the docs commit for this plan

### Authentication Gates

None.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest -q` (whole suite) | **174 passed** (141 at the 02-01 baseline; +33 from this plan) |
| `uv run pytest tests/integration/test_migration_chain.py tests/architecture/ tests/security/test_eval_no_body_boundary.py -q` | 38 passed |
| `uv run pytest tests/integration/test_workspace_retention_setting.py -q` | 9 passed |
| `uv run pytest tests/unit/test_period_month.py tests/unit/test_retention_argument_guards.py tests/integration/test_spend_currency_invariant.py -q` | 21 passed |
| `uv run ruff check src/ tests/ alembic/` | clean |
| `git status --porcelain docs/modules docs/architecture docs/adr` | no output |
| ADR-0045 coverage walk with six ledger tables, no rig list edited | passes |
| `uv run ruff format --check src/ tests/ alembic/` | **known-failing, pre-existing** — see below |

**On `ruff format --check`.** It reports 31 files would be reformatted, 26 already formatted. This is
pre-existing and systemic, logged in this phase's `deferred-items.md` (entry corrected by this plan —
see deviation 3): `ruff.toml` sets `line-length = 120` while the whole repo, Phase 1 included, is
hand-wrapped to roughly 100, so every hunk is the formatter joining a wrapped call back onto one line.
`uv run ruff check` — the linter, which is what CI would gate on today — is clean and stays clean;
`E501` is explicitly ignored. **No repo-wide reformat was performed**, and this plan's new files are
written in the house ~100 style so they read like their neighbours; 5 of the 7 would be joined by the
formatter for exactly the same reason every Phase 1 file would be. Satisfying the plan's
`ruff format --check` line requires the repo-wide line-length decision, which is not this plan's to
make.

## Human Verification Required

The plan's `<verification>` block carries one `<human-check>`, restated here because it is a trade
rather than a test:

> Confirm the A-055 decision: this plan records a knowing exception to the database-first pattern
> rather than adding a `BEFORE INSERT` trigger on `call_body`, and asserts the absence of the guard so
> a later phase inherits a recorded boundary. Confirm that is the intended trade, given the trigger's
> cost is a per-row lookup on the highest-volume insert path in the system.

The reasoning as implemented, and the assertion that records it, are in
"The A-055 Database-Guard Exception" above. Reversing the decision is a new revision adding the
trigger plus deleting `tests/security/test_eval_no_body_boundary.py`'s second test — both cheap, and
neither gets cheaper by waiting.

## CL-09 Is Marked Complete, and Only Half of It Was Built Here

`REQUIREMENTS.md` now reads CL-09 as complete, because this plan's frontmatter carries it and the
state step marks what the frontmatter carries. **Say plainly what that mark covers.** CL-09 is *"an
eval-case usage row is priced and counted toward workspace spend with no body stored"*, and this plan
built and asserted the **no body stored** half — the A-055 refusal, its whole-batch behaviour, and the
recorded absence of a database guard. The **priced and counted** half is `price_usage`, which is plan
02-04; `02-04-PLAN.md` carries CL-09 too and is where the clause is actually finished.

This follows plan 02-01's precedent, which marked CL-06 complete while `check_spend_ceiling` also
belongs to 02-04. It is recorded here rather than quietly inherited so the phase verifier reads CL-09
as **jointly satisfied by 02-02 and 02-04**, and does not accept this plan alone as evidence for the
pricing half.

## Flagged Assumption Carried to Verification

**CL-09 — `unclassified` / `unresolved`.** The deterministic edge probe proposed no edge predicates
for "an eval-case usage row is priced and counted toward workspace spend with no body stored". The
boundary conditions that clause genuinely has are covered by this plan's derived truths and by plan
02-04's, not by probe output. **The assumption to confirm at verification is that the absence of
probe-derived edges for CL-09 reflects a classification miss, not an edge-free requirement.**

## Known Stubs

None. Every function this plan created is wired to a real table, and every claim it makes is asserted
against the live engine.

The one deliberate incompleteness is a seam, not a stub: `read_retention_window` is the resolver plan
02-01's `drain.py` accepts through its `retention_for` keyword-only argument, and **plan 02-03 is what
passes it**. Until then the drain runs on its own working default. That is D-11's design — the two
meet in `worker.py`, in wave 2 — and it is named at the function definition so the two-caller risk
D-11 flags is answered by a named seam rather than by discipline.

## Threat Flags

None. Every security-relevant surface this plan introduces was in the plan's `<threat_model>`:
T-02-09 (tenant policy on the new table), T-02-10 (its grant matrix), T-02-11 (the non-positive
window), T-02-12 (the A-055 boundary) and T-02-13 (the currency race) are all mitigated and asserted.
No new network endpoint, auth path or file-access pattern was created — the route that will call
`set_retention_window` belongs to plan 02-05.

## Self-Check: PASSED

All eight created files exist on disk; all five modified files carry this plan's changes. All four
commits are present in `git log`: `d4acec6`, `8ee6349`, `81dba30`, `1b3cab2`.
