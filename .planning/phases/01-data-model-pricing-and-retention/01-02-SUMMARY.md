---
phase: 01-data-model-pricing-and-retention
plan: 02
subsystem: call-ledger
tags: [alembic, postgresql-17, rls, privilege, append-only, adr-0025, adr-0045, testcontainers]
status: complete

requires:
  - "01-01 — the Alembic chain, alembic/ddl.py's emitters, the three roles, the ledger schema, ledger.call_record, workspace_transaction(), the testcontainers rig"
provides:
  - "`ledger.call_body`, `ledger.price_table`, `ledger.workspace_spend`, `ledger.spend_ceiling` — the four remaining owned tables, with CHECKs, indexes, tenant policies and grants"
  - "T-006 as a live privilege: `prope_app` holds SELECT + INSERT on `ledger.price_table` and nothing else"
  - "`fk_call_record_price_row_id` — the deferred in-schema foreign key 0002 could not add"
  - "`prope.call_ledger.models` — SQLAlchemy Core tables for all five, explicitly not the DDL's source of truth"
  - "`tests/architecture/test_tenant_coverage.py` — ADR-0045's walk over all eight declared schemas, with DECLARED_SCHEMAS / GLOBAL_TABLES / EXPECTED_ABSENT_SCHEMAS"
  - "`tests/architecture/test_schema_invariants.py` — the definer/enum/foreign-key/timestamptz/numeric guards plus a models-vs-DDL drift guard"
  - "`tests/security/test_append_only_privilege.py` — five live-engine privilege tests, each with a visible-row positive control, plus the runnable mutation check"
  - "`tests/integration/test_migration_chain.py` — D-05: empty cluster reaches head; a second upgrade is byte-identical; the chain has one head"
affects:
  - "Phase 2's writer — the price/spend/ceiling tables and their grant matrix are now fixed"
  - "Phase 3's retention job — `ledger.call_body` keeps SELECT alongside DELETE, and the (workspace_id, expires_at) index is the predicate's access path"
  - "Phase 7 — creating the `access` schema turns test_tenant_coverage's absent-schema assertion red unless that phase shrinks EXPECTED_ABSENT_SCHEMAS in the same change"
  - "Every later revision that adds a ledger table — the coverage walk fails it without workspace_id + RLS + a policy"

tech-stack:
  added: []
  patterns:
    - "A privilege test asserts visibility of a real row inside the same transaction as the refusal, or it is asserting an empty table"
    - "A privilege guarantee ships with a mutation check that runs inside `uv run pytest -q`, restores the grant, observes the refusal stop holding, and revokes it in a finally"
    - "Foreign-key scope is checked by joining pg_constraint through pg_namespace, never by pattern-matching confrelid::regclass::text"
    - "The models declare; the migration decides. A drift guard asserts the model columns are a subset of the live ones"
    - "A per-phase constant (EXPECTED_ABSENT_SCHEMAS) carries its own handoff comment naming the phase that owns shrinking it"

key-files:
  created:
    - alembic/versions/0003_ledger_tables.py
    - src/prope/call_ledger/models.py
    - tests/architecture/__init__.py
    - tests/architecture/test_tenant_coverage.py
    - tests/architecture/test_schema_invariants.py
    - tests/security/test_append_only_privilege.py
    - tests/integration/__init__.py
    - tests/integration/test_migration_chain.py
  modified: []
  deleted: []

decisions:
  - "No separate index over price_table's four UNIQUE columns. The UNIQUE constraint's own index already serves the effective-dated lookup as a backward index scan; a second one would be an exact duplicate, and the name the plan listed exceeds PostgreSQL's 63-byte identifier limit and would be silently truncated."
  - "The second `alembic upgrade head` in the no-op test runs on a worker thread via `asyncio.to_thread`. Alembic's `command.upgrade` is synchronous and this project's async `env.py` drives it with `asyncio.run`, which refuses to start inside a running event loop."
  - "The eight DECLARED_SCHEMAS were confirmed against docs/architecture/tech_stack.md's per-module Database rows before being hard-coded. No name was guessed."
  - "prope_report keeps SELECT on ledger.call_body (Discretion §6, ADR-0037). Narrowing it would need an ADR and is out of scope."

metrics:
  duration: ~1h
  completed: 2026-08-10

actuals:
  tokens: 12400
  tasks: 2
  commits: 2
---

# Phase 01 Plan 02: The ledger schema, complete and asserted — Summary

`ledger` now holds exactly the five tables call-ledger owns, and the phase's
irreversibility claim is a live database privilege rather than a sentence in a
lock file: `prope_app` cannot `UPDATE` or `DELETE` a price row, the refusal is
asserted against PostgreSQL 17 with the row visible in the same transaction, and
a fifth test proves that refusal has teeth by restoring the grant, watching the
refusal stop holding, and revoking it again inside the same `pytest` run.

## What was built

**Revision `0003_ledger_tables`.** Four tables in one revision, each with its
whole guarantee stack. `call_body` (`text` bodies, not `jsonb` — a malformed
body is the one worth keeping) with the `(workspace_id, expires_at)` retention
index ADR-0040 requires to be an index scan. `price_table` with the four-column
`UNIQUE (workspace_id, provider_config_id, upstream_model, effective_from)`
that makes an effective-date tie impossible to insert rather than something the
resolver has to break, and deliberately **no** `CHECK (effective_from >= now())`
— CL-05 depends on a price row being addable behind existing calls.
`workspace_spend` keyed `(workspace_id, period_month)` so A-103's aggregate is a
single conflict-target upsert. `spend_ceiling` with both limits off by default.
Then `fk_call_record_price_row_id`, the foreign key 0002 had to leave as a plain
`text` column because its target did not exist yet.

**The grant matrix, which is the point.** `price_table` gets `SELECT, INSERT`
and nothing else (T-006 / D-07). `call_record` keeps `UPDATE` for A-099's upsert
and CL-05 repricing and has no `DELETE`. `call_body` keeps `SELECT` alongside
`DELETE` — a `DELETE … WHERE expires_at <= $1` reads a column, and PostgreSQL
requires `SELECT` on every column a statement references, so revoking it in the
name of "no read path" would break retention. `prope_report` gets `SELECT` on
all four.

**`src/prope/call_ledger/models.py`.** SQLAlchemy 2.0 Core `Table` objects for
all five, bound to the shared `MetaData`, each declaring `schema="ledger"`
explicitly. `metadata.create_all` is never called anywhere in this project and
would produce a database with none of the policies, grants or REVOKEs — the
docstring says so, and a drift guard test enforces the split rather than relying
on it being remembered.

**Four test files.** 20 new tests, all against a live PostgreSQL 17.

## Verification — what actually ran

Every row below is the output of a command executed in this session. Nothing
here is read out of the migration source.

| Check | Result |
|-------|--------|
| `uv run alembic upgrade head` vs. a pristine `postgres:17` (standalone container) | exit 0; `0001 → 0002 → 0003` |
| `uv run alembic heads` | `0003 (head)` |
| `uv run pytest tests/security/test_append_only_privilege.py -q` | **5 passed** |
| `uv run pytest tests/security/test_append_only_privilege.py -k teeth -q` | **1 passed, 4 deselected** |
| `uv run pytest tests/architecture -q` | **12 passed** |
| `uv run pytest tests/integration/test_migration_chain.py -q` | **3 passed** |
| `uv run pytest -q` (whole suite) | **34 passed** — Wave 1's 14 among them |
| `uv run ruff check src/ tests/ alembic/` | All checks passed |
| `uv run python -c "…sorted(models.metadata.tables)"` | the five `ledger.*` tables |
| `uv run python -c "…len(m.DECLARED_SCHEMAS) == 8"` | exit 0 |
| `grep -c DECLARED_SCHEMAS tests/architecture/test_tenant_coverage.py` | 5 |
| `docs/` changed since the fixed phase base `b27b58a` | 0 committed, 0 uncommitted, 0 untracked |

Direct catalogue queries against the pristine container, after `upgrade head`:

| Property | Observed |
|----------|----------|
| tables in `ledger` | `5` |
| columns named `workspace_id` in `ledger` | `5` — every owned table carries it |
| policies in `ledger` | `5`: `call_body_tenant`, `call_record_tenant`, `price_table_tenant`, `spend_ceiling_tenant`, `workspace_spend_tenant` |
| tables with RLS off, or FORCEd | `0` |
| foreign keys whose target namespace ≠ `ledger` | `0` (namespace join, not `regclass` text) |
| foreign keys present | `fk_call_body_call_id`, `fk_call_record_price_row_id` |
| indexes matching `%expires_at%` | `1` |
| UNIQUE constraints on `price_table` | `1`, columns `workspace_id, provider_config_id, upstream_model, effective_from` |
| `has_table_privilege('prope_app','ledger.price_table', …)` | UPDATE `false`, DELETE `false`, INSERT `true`, SELECT `true` |
| `…('prope_app','ledger.call_record', …)` | DELETE `false`, UPDATE `true` |
| `…('prope_app','ledger.call_body', …)` | DELETE `true`, SELECT `true`, UPDATE `false` |
| `…('prope_report','ledger.call_record','SELECT')` | `true` |
| `double precision` / `real` columns in `ledger` | `0` |
| `SECURITY DEFINER` functions in `ledger` | `0` |
| native enum types in `ledger` | `0` |
| `_at` / `_from` columns not `timestamp with time zone` | none |
| money columns | all six `numeric(20,10)` |
| `workspace_spend.period_month` | `date` |
| `call_record.created_at` default / `written_at` default | `NULL` / `now()` |

### The must-have truths, and what proves each

| Truth | Proved by |
|-------|-----------|
| Five tables in `ledger`, each with `workspace_id`, RLS on, exactly one policy | catalogue queries above **and** `test_every_table_in_every_declared_schema_is_tenant_scoped` |
| `UPDATE` on `price_table` refused, with a **visible** row | `test_update_on_price_table_is_refused_by_the_engine` — asserts `count(*) == 1` inside the same transaction, then `permission denied … price_table` |
| `DELETE` on `price_table` refused, same positive control | `test_delete_on_price_table_is_refused_by_the_engine` |
| Restoring the grant makes the refusal stop holding, and the matrix is left as found | `test_the_append_only_refusal_has_teeth` — asserts `false` before, GRANTs as `prope_migrate`, asserts `true`, performs the very UPDATE tests 1–2 expect refused and asserts `rowcount == 1`, REVOKEs in a `finally`, then asserts `false` again |
| `DELETE` on `call_record` refused; `DELETE` on `call_body` succeeds | `test_delete_on_call_record_is_refused_by_the_engine`; `test_delete_on_call_body_succeeds_because_retention_must_have_it` — the latter verifies by direct query as `prope_migrate`, and also asserts the `call_record` row survived |
| The walk covers all EIGHT declared schemas and **reports** the absent ones | `test_declared_schemas_that_do_not_exist_are_reported_not_skipped` — asserts the absent tuple equals the seven, and that the existing set is exactly `("ledger",)` |
| Pristine cluster reaches head; a second run is a no-op | `test_an_empty_cluster_reaches_head_and_yields_a_working_database` and `test_running_the_chain_a_second_time_is_a_no_op` — the latter compares full `information_schema.columns` + `pg_policies` snapshots and asserts they are non-empty first, so the comparison cannot be vacuous |
| No foreign key leaves `ledger` | `test_no_foreign_key_leaves_the_ledger_schema` |
| Zero `SECURITY DEFINER` functions in `ledger` | `test_the_ledger_schema_contains_no_security_definer_function` |
| Every money column `numeric(20,10)`, every timestamp `timestamptz`, no float anywhere | three separate tests in `test_schema_invariants.py` |
| The four-column UNIQUE makes an effective-date tie unenterable | catalogue query above; the constraint is `uq_price_table_workspace_id` |

**One truth is proved from inside the suite rather than after it.** The plan's
verification item "`has_table_privilege('prope_app','ledger.price_table','UPDATE')`
returns false … again after it" is asserted by the last statement of the teeth
test, on the same cluster, after its `finally` has run. The testcontainers
container is destroyed at session end, so there is no cluster left to query
externally once `pytest` returns — the in-suite assertion is the strongest form
this check can take, and it is where a leak would actually be caught.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 — Bug] `asyncio.run() cannot be called from a running event loop` in the no-op test**
- **Found during:** Task 2
- **Issue:** the second `alembic upgrade head` has to run inside an async test
  (it sits between two async snapshot queries). `command.upgrade` is
  synchronous and this project's async `env.py` drives it with `asyncio.run`,
  which refuses to start while pytest-asyncio's loop is running.
  `test_running_the_chain_a_second_time_is_a_no_op` failed with `RuntimeError`.
- **Fix:** `await asyncio.to_thread(_upgrade_to_head, pristine_container)`, with
  a comment naming why the module-scoped fixture escapes the same problem by
  being synchronous.
- **Commit:** `6988d90`

### Departures from the plan text

**2. No `ix_price_table_workspace_id_provider_config_id_upstream_model_effective_from`**
- The plan's "Indexes" list names it, but the plan's own Task 1 action text says
  the `UNIQUE` constraint is "declared in that column order **so it also serves
  the effective-dated lookup** as a backward index scan terminating on the first
  row". The constraint already creates exactly that index. A second index over
  the identical four columns in the identical order would be a pure duplicate —
  write amplification on the table CL-03 reads once per drain batch, for nothing.
- Independently, the listed name is **76 bytes**, past PostgreSQL's 63-byte
  identifier limit; the server would have silently truncated it, so any test
  asserting the name would have failed against a correct schema.
- The acceptance criteria are unaffected: the `expires_at` index criterion is met
  by `ix_call_body_workspace_id_expires_at`, and the UNIQUE-constraint criterion
  is met with the exact column list.

**3. The `-k teeth` test asserts the refusal stops holding by performing the write, not only by reading the privilege bit**
- The plan asks for both ("assert `has_table_privilege(…)` is now true **and**
  that no permission error is raised"). Both are done. Recorded because the
  second half is the one that matters: a privilege bit that flipped while the
  statement still failed would mean tests 1 and 2 were passing for some other
  reason, which is the whole thing this test exists to rule out.

**4. The tenancy walk carries one assertion the plan did not ask for**
- `assert tables` — a walk that found nothing would satisfy every per-table
  assertion vacuously. Added under Rule 2: a coverage test that cannot fail is
  the exact defect ADR-0045 was written about. Same reasoning added the two
  non-empty snapshot assertions in the no-op test.

## Owed to a later phase

**`EXPECTED_ABSENT_SCHEMAS` in `tests/architecture/test_tenant_coverage.py` is a
per-phase constant.** It currently names the seven declared schemas Phase 1 has
not built: `access`, `evaluation`, `gateway`, `history`, `provider`, `registry`,
`release`. The phase that creates one of them owns removing it from that tuple
**in the same change**. **Phase 7 is the first to hit it** — the moment it
creates `access`, `test_declared_schemas_that_do_not_exist_are_reported_not_skipped`
goes red. This is deliberate: a schema that silently fails to appear must not
pass as coverage. The comment beside the constant says so, and the assertion
message tells the reader what to edit.

## Open questions — status after this plan

- **OQ-A** — implemented again here without deviation: all four new tables use
  `workspace_id text` and every policy predicate compares text to text with no
  cast. Asserted for the whole schema, not per table, by
  `test_no_policy_predicate_casts_the_tenant_setting_to_uuid` (01-01) over
  `pg_policies WHERE schemaname='ledger'`. The ADR wording still needs upstream
  correction; nothing under `docs/` was touched.
- **OQ-B** — the per-workspace retention window still has no column. `expires_at`
  is stamped per body, which is what A-106 requires; where the window itself
  lives remains Phase 2's to answer.
- **OQ-C** — **no fifth `SECURITY DEFINER` function was created**, and
  `test_the_ledger_schema_contains_no_security_definer_function` now makes that
  a failing test rather than a resolution someone remembers.
- **OQ-D, OQ-E** — untouched by this plan.

No new open question arose. The eight schema names were confirmed against
`docs/architecture/tech_stack.md` before being hard-coded (history l.162, ledger
l.186, access l.212, provider l.250, registry l.289, evaluation l.359, release
l.521, gateway l.480 — "A `gateway` schema is created and left empty"); none had
to be guessed, so there is no mismatch to name.

## Requirements — deliberately NOT marked complete

This plan's frontmatter claims `[CL-03, CL-05, CL-08]`, and **none of the three
was checked off in `REQUIREMENTS.md`.** All three are shared with later plans in
this phase — CL-03 with 01-03, CL-05 and CL-08 with 01-04 — and this plan builds
only the tables those requirements will be satisfied *against*. CL-03 says a
call is priced at the row in force at its own timestamp; no code prices anything
yet. CL-05 says repricing fills a previously-unpriced call; there is no
repricing function. CL-08 says expired bodies are deleted while their records
stay intact; `test_delete_on_call_body_succeeds_because_retention_must_have_it`
proves the *privilege* exists, not that a retention job does. Marking them
complete here would put three false ticks in the traceability table that nothing
downstream would ever revisit. 01-03 and 01-04 own them.

## Known Stubs

None. Nothing in this plan renders a placeholder, returns a hardcoded empty
value, or leaves a code path unwired. `GLOBAL_TABLES` is an empty mapping, but
that is its correct Phase 1 value — all five `ledger` tables are tenant-scoped,
so there is nothing to exempt — and the test that would catch a blank exemption
is present and passing.

The prohibition held: **no second resting place for a call body** was created.
`call_body` has no soft-delete flag and no tombstone column, no archive, audit or
shadow table exists, no committed fixture holds a real body (the test bodies are
the literals `'a request'` and `'a response'`), and nothing logs or labels a
body — this plan adds no logging and no metrics at all.

## Threat Flags

None. Every threat in the plan's register is addressed as dispositioned:
T-01-07 and T-01-08 by the grant matrix plus five tests, T-01-09 by the
namespace-joined foreign-key walk, T-01-10 by the eight-schema coverage walk,
T-01-11 by the definer-function assertion, T-01-13 by the absence noted above.
T-01-12 (`prope_report`'s `BYPASSRLS` + `SELECT` on `call_body`) stands as
`accept`, per ADR-0037 and Discretion §6 — recorded, not missed.

No file created here introduces network surface, an auth path, file access, or a
trust-boundary schema change outside that register.

## Notes for the next plan

- `ledger.call_body` requires its `ledger.call_record` first —
  `fk_call_body_call_id` is real and has no cascade. Seed the record, then the
  body.
- A price row's `created_at` defaults; its `effective_from` does not, and must be
  allowed to sit in the past.
- `tests/conftest.py`'s truncate fixture discovers tables from `pg_tables`, so
  all five are now cleaned between tests with no edit to the rig. `TRUNCATE …
  CASCADE` handles the two foreign keys.
- Anything that has to run `alembic upgrade head` from inside an async test must
  go through `asyncio.to_thread`.
- `prope_app` has no `UPDATE` on `price_table`. A Phase 2 writer that tries to
  correct a price in place will fail at the engine, which is the intended
  outcome — supersede with a later `effective_from`.

## Self-Check: PASSED

All 8 created files verified present on disk. Both commits (`4e5b2b8`,
`6988d90`) verified present in `git log --oneline --all`.
