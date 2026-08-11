---
phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
plan: 01
subsystem: backend
tags: [migration, ddl, rls, grants, append-only, ph-02, vocabulary, seed, test-rig, global-tables]

# Dependency graph
requires:
  - phase: 01-data-model-pricing-and-retention
    plan: 01
    provides: "alembic/ddl.py — assume_migrate_role / reset_role / enable_tenant_rls / grant_table, and the three roles revision 0001 creates"
  - phase: 01-data-model-pricing-and-retention
    plan: 02
    provides: "tests/conftest.py's three role-scoped engines and the autouse truncate fixture; tests/architecture/test_tenant_coverage.py's ADR-0045 walk and its GLOBAL_TABLES escape hatch; tests/architecture/test_schema_invariants.py's five generic invariants; tests/integration/test_migration_chain.py's pristine-cluster and idempotency tests"
  - phase: 01-data-model-pricing-and-retention
    plan: 03
    provides: "tests/security/test_append_only_privilege.py — the whole-file analog this plan's PH-02 test mirrors, including _refusal_text and the grant/observe/revoke mutation check"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 01
    provides: "tests/broker/ — the precedent for a per-subject test package created when its subject arrived"
provides:
  - "alembic/versions/0005_history_schema_and_vocabulary.py — the `history` schema, both tables, four indexes, the composite vocabulary key, the tenant policy, the grant matrix and the 31-row seed, in one applied migration"
  - "history.history_action_registry — the closed action vocabulary, global (no workspace_id), SELECT-only for prope_app, seeded by the migration and by nothing else"
  - "history.history_event — append-only by privilege: prope_app holds SELECT and INSERT and holds neither UPDATE nor DELETE"
  - "tests/property_history/__init__.py — the shared history factories: history_event_values(**overrides), SEED_HISTORY_EVENT (eleven columns, seq absent), seed_history_event(), and the count/order statement constants"
  - "tests/security/test_history_is_append_only_by_privilege.py — PH-02, with a positive control inside the attempting transaction and a grant/observe/revoke mutation check"
  - "tests/integration/test_history_schema_ships_its_guarantees.py — 31 rows readable with no tenant context, the spec-determined registry columns, the four indexes by name, seqcache = 1"
  - "The project's first GLOBAL_TABLES entry, and a numberless reason string that keeps OQ-027's stale count out of tests/"
  - "A two-schema test rig: LIST_TRUNCATABLE_TABLES / truncate_owned_tables, GENERIC_SCHEMAS parameterisation, SCHEMA_TABLES and the registry-count idempotency snapshot"
affects: [04-02, 04-03, 04-04, 04-VERIFICATION, 05-property-history-read-path, 07-access-control]

actuals:
  tokens: 78000
  tasks: 3
  commits: 0

tech-stack:
  added: []
  patterns:
    - "A schema-creating revision that is not 0001: CREATE SCHEMA ... AUTHORIZATION runs BEFORE assume_migrate_role(), everything after runs under it"
    - "A data seed inside a migration, placed with the tables so the deploy ordering ADR-0038 rests on is a property of the chain"
    - "A composite foreign key onto a global table from a tenant-scoped one, with the cross-tenant objection disposed of at the constraint rather than assumed"
    - "GLOBAL_TABLES reason strings that name the rule, the failure mode of the alternative and the authority — and carry no number"
    - "A project-wide catalogue invariant parameterised over a schema tuple, with the ledger-specific tests carrying their own literal so no module constant sits beside a parameter"
    - "A per-subject test-helper package (tests/property_history/) that reuses tests.unit's calendar constants rather than restating them"

key-files:
  created:
    - alembic/versions/0005_history_schema_and_vocabulary.py
    - tests/property_history/__init__.py
    - tests/integration/test_history_schema_ships_its_guarantees.py
    - tests/security/test_history_is_append_only_by_privilege.py
  modified:
    - tests/conftest.py
    - tests/architecture/test_tenant_coverage.py
    - tests/architecture/test_schema_invariants.py
    - tests/integration/test_migration_chain.py
    - tests/integration/test_write_path.py
    - tests/integration/test_reprice_only_unpriced.py

key-decisions:
  - "The revision is 0005 and its down_revision is 0004, read from `uv run alembic heads` at execution time and not written by the planner. Phase 3 added no migration, so the expected head and the observed head agreed — but the value was read, not assumed, and `test_the_revision_chain_has_exactly_one_head` is what would have caught a guess"
  - "ORCHESTRATION §12 overrides this plan's comment-density instructions and was applied. The revision's seven bold-led docstring paragraphs were kept — they are a cross-plan contract (plan 04-03 Task 2 is written against the seventh existing, and §12 itself requires the deviation record) — but each was written at a fraction of the plan's prescribed length, and the plan's per-column / per-constraint / per-grant comment lists were reduced to the surprising cases only: seq, details, the redundant-looking UNIQUE, the FK's ON DELETE absence and cross-tenant disposal, the target_type CHECK that is not there, and the two grant blocks"
  - "EXPECTED_ABSENT_SCHEMAS was shrunk to six in the same change that created the schema, and the constant's own comment — which named Phase 7 as the first phase to do this — was corrected to name Phase 4 first and Phase 7 next. `.planning/STATE.md` carries the same wrong claim and is the orchestrator's to fix (§7); it was NOT edited here"
  - "The plan named three Phase 1 files that carry `ledger` as a literal. Two go red (conftest.py, test_tenant_coverage.py) and the third — test_migration_chain.py — goes GREEN-BUT-BLIND: it kept asserting six ledger tables while saying nothing about whether `history` reached a pristine cluster, and its idempotency snapshot covered neither history_event's policy nor the registry's seed. All three were edited; the blind one is the one worth naming"
  - "The registry row count joined the idempotency snapshot with an honest comment about what it can catch. It CANNOT catch a double-apply of 0005 — that test re-runs `alembic upgrade head` against an already-stamped cluster, so no revision body executes. What it is for is the next migration: one that re-seeds, back-fills or widens the vocabulary moves the count and goes red at the moment it is written"
  - "test_migration_chain.py's two-schema predicates are LITERALS, not bound parameters. `_query_all` takes its statements as varargs and executes them with no parameter dict, so `= ANY(:schemas)` would have meant changing a shared test utility in the same change as a migration. `_query_all`'s signature is unchanged"
  - "The five generic schema invariants were parameterised over ('history', 'ledger') rather than copied into a history-specific file, on D-06's grounds. The module constant SCHEMA was removed entirely and the three ledger-specific tests carry their own literal — leaving both a constant and a parameter is how the two drift. Four of the five tests were renamed to schema-neutral names, which is four test ids that disappear from any saved output"
  - "The truncate fixture was renamed truncate_ledger -> truncate_owned_tables and its constant LIST_LEDGER_TABLES -> LIST_TRUNCATABLE_TABLES. The fixture is autouse and is never requested by name, so the rename is a prose edit; keeping the name would have left a fixture called truncate_ledger truncating two schemas. Re-seeding the registry inside the fixture is refused BY NAME in the docstring rather than merely not done"
  - "tests/property_history/__init__.py's placement argument is precedent (tests/broker/), NOT the plan's original draft that tests/unit was rejected for importing two bounded contexts — that argument is false, because this module imports tests.unit and pulls the same two call-ledger modules in transitively. The false version was not written"
  - "The factory constant is SEED_HISTORY_EVENT and deliberately not INSERT_HISTORY_EVENT: plan 04-02 ships a production constant of that name with the same eleven columns, and two constants sharing one name across tests/ and src/ is a Phase 5 column landing in whichever file the author had open"
  - "The mutation check grants and revokes UPDATE rather than DELETE, because UPDATE is the statement a well-meaning repair script actually reaches for. DELETE's absence is covered by its own plain refusal test plus this cycle proving the probe is pointed at the right object at all — an `is False` assertion against a mis-targeted table would also pass"

patterns-established:
  - "Create a schema outside revision 0001: the two CREATE SCHEMA / GRANT USAGE lines run before assume_migrate_role() because prope_migrate is not guaranteed to hold CREATE ON DATABASE, and everything after runs under the assumed role so ADR-0035's owner bypass holds"
  - "Seed a closed vocabulary in the migration that creates its table, before the table whose foreign key points at it, so the deploy ordering ADR-0038 rests on is a property of the chain rather than of a startup task"
  - "Exclude a migration-owned table from the truncate fixture by name, and refuse re-seeding it there by name too — a second provisioning path would let the suite pass against a vocabulary the migration never wrote"
  - "Prove a GLOBAL_TABLES exemption POSITIVELY from the other side: a prope_app session with no tenant context reading all the rows, plus the mirror count of zero on the tenant-scoped table beside it, because the walk itself currently `continue`s past an exemption with no assertion (OQ-031)"
  - "Pin an index count rather than deriving it, so the fifth index somebody reaches for is a visible edit"

requirements-completed: [PH-02]

coverage:
  - id: D1
    description: "The `history` schema exists after `alembic upgrade head` on a pristine cluster, owned by prope_migrate, with USAGE granted to prope_app and prope_report"
    requirement: PH-02
    verification:
      - kind: integration
        ref: "tests/integration/test_migration_chain.py::test_an_empty_cluster_reaches_head_and_yields_a_working_database"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_tenant_coverage.py::test_declared_schemas_that_do_not_exist_are_reported_not_skipped"
        status: pass
    human_judgment: false
  - id: D2
    description: "history.history_action_registry holds exactly 31 rows after the migration, and a prope_app session with NO tenant context reads all 31 of them and zero history events"
    verification:
      - kind: integration
        ref: "tests/integration/test_history_schema_ships_its_guarantees.py::test_the_registry_is_readable_with_no_tenant_context_and_holds_thirty_one_rows"
        status: pass
    human_judgment: false
  - id: D3
    description: "prope_app holds SELECT and INSERT on history.history_event and neither UPDATE nor DELETE, and an attempted UPDATE or DELETE against a row provably visible to the attempting transaction is refused with `permission denied`"
    requirement: PH-02
    verification:
      - kind: security
        ref: "tests/security/test_history_is_append_only_by_privilege.py::test_update_on_history_event_is_refused_by_the_engine"
        status: pass
      - kind: security
        ref: "tests/security/test_history_is_append_only_by_privilege.py::test_delete_on_history_event_is_refused_by_the_engine"
        status: pass
      - kind: security
        ref: "tests/security/test_history_is_append_only_by_privilege.py::test_prope_app_holds_select_and_insert_on_history_event"
        status: pass
    human_judgment: false
  - id: D4
    description: "prope_app holds SELECT on history.history_action_registry and holds no INSERT, UPDATE or DELETE on it"
    verification:
      - kind: security
        ref: "tests/security/test_history_is_append_only_by_privilege.py::test_the_registry_is_select_only_for_the_application_role"
        status: pass
    human_judgment: false
  - id: D5
    description: "prope_report holds SELECT on both history tables and holds nothing else on either"
    verification:
      - kind: security
        ref: "tests/security/test_history_is_append_only_by_privilege.py::test_prope_report_reads_both_tables_and_writes_neither"
        status: pass
    human_judgment: false
  - id: D6
    description: "Granting UPDATE on history.history_event makes the refusal stop holding, and revoking it restores the refusal — proven inside the suite"
    requirement: PH-02
    verification:
      - kind: security
        ref: "tests/security/test_history_is_append_only_by_privilege.py::test_the_append_only_refusal_has_teeth"
        status: pass
    human_judgment: false
  - id: D7
    description: "An INSERT naming an (action, target_type) pair that is not a registry row is refused by fk_history_event_action even as prope_migrate"
    verification:
      - kind: none
        ref: "plan 04-04 owns the assertion; the constraint exists and is exercised indirectly here"
        status: deferred
    human_judgment: false
    rationale: "The composite key ships in this revision and every seeding path in this plan depends on it — history_event_values() names a registered pair precisely because the key is real even for the owner, and a wrong pair fails the seed. The DIRECT assertion (a deliberately unregistered pair refused as prope_migrate) is plan 04-04's, which this plan's own objective routes it to. Named here rather than claimed."
  - id: D8
    description: "history.history_event carries row security with a policy; history.history_action_registry carries neither, and its exemption is a GLOBAL_TABLES entry with a written reason"
    verification:
      - kind: architecture
        ref: "tests/architecture/test_tenant_coverage.py::test_every_table_in_every_declared_schema_is_tenant_scoped"
        status: pass
      - kind: architecture
        ref: "tests/architecture/test_tenant_coverage.py::test_every_global_table_exemption_carries_a_written_reason"
        status: pass
    human_judgment: false
  - id: D9
    description: "The identity sequence behind history_event.seq has a cache size of 1"
    verification:
      - kind: integration
        ref: "tests/integration/test_history_schema_ships_its_guarantees.py::test_the_identity_sequence_has_no_cache"
        status: pass
    human_judgment: false
  - id: D10
    description: "The whole pre-existing suite is green: EXPECTED_ABSENT_SCHEMAS names six schemas, the existing-schema tuple is (history, ledger), and the five generic schema invariants run against both schemas"
    verification:
      - kind: command
        ref: "uv run pytest -q -> 431 passed, 1 skipped in 333.39s"
        status: pass
    human_judgment: false
  - id: D11
    description: "The five decisions this revision bakes in are the intended ones, and the four A-120-violating action names are preferred over renames that would make AC-6 red"
    verification: []
    human_judgment: true
    rationale: "The plan's two <human-check> items. Both are adjudications, not properties a test can assert; every mechanical half is built and asserted, and all five are already rows in deferred-items.md §2 owed to ORCHESTRATION-DECISIONS.md."

# Metrics
duration: 62min
completed: 2026-08-11
status: complete
---

# Phase 04 Plan 01: Schema, privilege ordering and the closed vocabulary — Summary

**PH-02 is proven, and the engine is what says so.** `prope_app` holds `SELECT` and `INSERT` on
`history.history_event` and holds neither `UPDATE` nor `DELETE`; an `UPDATE` or a `DELETE` attempted
against a row the *same transaction has just counted as visible* raises `permission denied for table
history_event`; and the suite itself demonstrates that the refusal stops holding when the privilege is
restored and starts holding again when it is revoked. Nothing under `src/prope/` knows the schema
exists, which is the deliberate gap this plan leaves.

## The revision, and the head it was wired to

`uv run alembic heads` reported **`0004 (head)`** before the task ran. The revision is therefore
**`0005`** with `down_revision = "0004"` — read, not written by the planner and not guessed. Phase 3's
CONTEXT said no migration was required by any of its decisions, so the expectation and the observation
agreed; the point is that `test_the_revision_chain_has_exactly_one_head` would have made a guess a red
test rather than a merge revision. `uv run alembic heads` now reports `0005 (head)`.

`alembic/versions/0005_history_schema_and_vocabulary.py` carries, in one applied migration:

- `CREATE SCHEMA history AUTHORIZATION prope_migrate` and `GRANT USAGE ON SCHEMA history TO prope_app,
  prope_report`, both **before** the first `assume_migrate_role()` — `prope_migrate` is not guaranteed
  to hold `CREATE ON DATABASE`, which is why `0001` created `ledger` as the connected superuser.
- `history.history_action_registry` — five columns, no sixth, **no `workspace_id`**, with
  `pk_history_action_registry`, the mechanically-required `uq_history_action_registry_action` and
  `ck_history_action_registry_writing_module_values`.
- The **31-row seed**, executed between the registry and `history_event` because the composite key
  points at it. Exactly 3 rows carry `requires_reason` true; exactly 2 carry a non-empty `detail_keys`.
- `history.history_event` — the twelve columns ADR-0024 names and no thirteenth, `seq` as
  `bigint GENERATED ALWAYS AS IDENTITY (CACHE 1)`, `pk_history_event` on `id`, `uq_history_event_seq`,
  three named CHECKs, and `fk_history_event_action` with no `ON DELETE` or `ON UPDATE` clause.
- Four indexes, every one leading with `workspace_id`.
- `enable_tenant_rls("history", "history_event")` and **no such call on the registry**.
- `grant_table("history", "history_event", app_privileges=["SELECT", "INSERT"])` and
  `grant_table("history", "history_action_registry", app_privileges=["SELECT"])`, both taking
  `report_select`'s default of `True` with ADR-0037's argument written at the call.

No `op.create_table`, no `op.create_index`, no `CREATE TRIGGER`, no `CREATE TYPE ... AS ENUM`, no
`SECURITY DEFINER`, and no literal `REVOKE UPDATE` or `REVOKE DELETE` — the only `REVOKE` in the applied
DDL is `grant_table`'s `REVOKE ALL ... FROM PUBLIC`. The two grep hits for `ON DELETE` / `ON UPDATE` and
`REVOKE UPDATE` in the file are prose stating the absence, in the revision docstring and in the
constraint's comment.

## The four rig files, and which one would have gone green rather than red

`0004`'s docstring says *"NO TEST RIG EDIT IS NEEDED, AND THAT IS THE POINT."* That is true of a new
**table** and false of a new **schema**.

| File | What it named | What would have happened |
|---|---|---|
| `tests/conftest.py` | `schemaname = 'ledger'` in the truncate filter | **Red** — `history` rows survive between tests |
| `tests/architecture/test_tenant_coverage.py` | `EXPECTED_ABSENT_SCHEMAS` and `== ("ledger",)` | **Red** — twice |
| `tests/integration/test_migration_chain.py` | four `ledger`-scoped constants | **GREEN, and blind** |
| `tests/architecture/test_schema_invariants.py` | `SCHEMA = "ledger"` | **Green, and not asserting the five project rules over `history` at all** |

The third is the one worth naming. It kept passing, kept asserting six `ledger` tables, and said nothing
about whether `history` reached a pristine cluster; its idempotency snapshot covered neither
`history_event`'s policy nor the registry's seed. It is now a two-schema `SCHEMA_TABLES` mapping, a
`(schemaname, tablename)` comparison against that mapping flattened, two-schema column and policy
snapshots, and a registry row count in the before/after comparison.

**What the registry count can and cannot catch**, written at the constant rather than assumed: it
**cannot** catch a double-apply of `0005`, because `test_running_the_chain_a_second_time_is_a_no_op`
re-runs `alembic upgrade head` against a cluster already stamped at head and no revision body executes.
What it is for is the **next** migration — one that re-seeds, back-fills or widens the vocabulary moves
the count and goes red at the moment it is written.

## `EXPECTED_ABSENT_SCHEMAS`, and the note in STATE.md that is now wrong

`EXPECTED_ABSENT_SCHEMAS` is shrunk from seven entries to six, in the same change that created the
schema, and the constant's own comment — which read *"Phase 7 creating `access` is the first such
case"* — now names **Phase 4 creating `history` as the first, with Phase 7's `access` as the next**.

**`.planning/STATE.md` carries the same claim and it is now wrong.** It was **not** edited: shared
ledger files are orchestrator-owned (ORCHESTRATION §7) and this is in the ledger section below and in
`deferred-items.md` §5, which already names the orchestrator as the owner.

## The deliberate gap

After this plan the `history` schema is complete and unwritable by application code, and **nothing under
`src/prope/` knows it exists.** There is no `record_event`, no registry loader, no counter, no package.
The tests here seed events with a raw `INSERT` through `tests/property_history/__init__.py` rather than
through a write path that does not exist yet — which is also what keeps PH-02's assertion independent of
the code plan 04-02 writes. Plan 04-02 builds the validating write path (PH-05); plan 04-03 proves the
total order (PH-04) and owns `test_history_seq_cannot_be_supplied.py` and
`test_no_overriding_system_value.py`, both named in the revision's seventh docstring paragraph; plan
04-04 owns the unregistered-pair refusal and `test_history_validation_has_no_database_backstop.py`.

## The gate, observed

```
uv run ruff check src/ tests/ alembic/
All checks passed!
```

```
uv run pytest -q
431 passed, 1 skipped, 1 warning in 333.39s (0:05:33)
```

The one `s` is Phase 3's `PROPE_RUN_LOAD`-gated load test, unchanged. `uv run ruff format --check` was
not run: it fails repo-wide on the pre-existing 120-vs-100 column disagreement (Broken Window #1), it is
not the gate, and it is not this plan's to fix. `make check` was not run because its `format` target
writes.

Intermediate gates, both green before the full run:

```
uv run pytest tests/architecture/ tests/integration/test_migration_chain.py -q   ->  78 passed
uv run pytest tests/integration/test_history_schema_ships_its_guarantees.py \
              tests/security/test_history_is_append_only_by_privilege.py -q      ->  10 passed
```

```
git status --porcelain docs/modules docs/architecture docs/adr pyproject.toml uv.lock
(no output)
```

## Deviations from the plan

### 1. ORCHESTRATION §12 was applied over the plan's comment-density instructions

**Recorded as the §12 override this plan's own header requires.** The plan instructs, in as many words,
that *"the module docstring is a deliverable, not decoration"*, lists *"comments that must be present"*
per column, and prescribes multi-paragraph arguments at the seed, the foreign key and both grants. §12
outranks all of it.

What was kept and why: the revision's **seven bold-led docstring paragraphs survive**, because two of
them are cross-plan contracts rather than decoration — §12's own *"Migrations specifically"* clause
requires the deviation record with its OQ status (paragraph 2), and plan 04-03 Task 2 is written against
the `OVERRIDING SYSTEM VALUE` boundary note existing and instructs its executor to delete it if the
boundary moves, so a missing paragraph 7 is a dangling reference in a security test.

What was cut: each paragraph is a fraction of its prescribed length, and the per-column /
per-constraint / per-grant comment lists were reduced to the genuinely surprising cases — `seq`
(`GENERATED ALWAYS`, `CACHE 1`, monotonic-is-not-gapless, assignment-order-is-not-commit-order),
`details` (the inversion of `0003`'s `text` call), the `UNIQUE` that looks like a redundant duplicate of
the primary key, the foreign key's absent `ON DELETE` plus its cross-tenant disposal and multixact
note, the `target_type` CHECK that deliberately does not exist, and the two `grant_table` calls.
Everything else in the plan — the DDL, the constraints, the grants, the names, the tests, the ordering,
the prohibitions — stands exactly as written.

### 2. Two acceptance-criteria literals match modulo the DDL's column alignment

The criterion asks that the revision contain the exact strings `text[] NOT NULL` and
`jsonb NOT NULL DEFAULT '{}'::jsonb`. The house DDL style (`0003`, `0004`) pads the type to a column, so
the file reads `detail_keys      text[]   NOT NULL,` and
`details          jsonb        NOT NULL DEFAULT '{}'::jsonb,`. **A whitespace-only difference with a
byte-identical end state**, which ORCHESTRATION §5 says owes no OQ — but a verifier grepping for the
literal will miss two of four, so it is named here rather than left to be discovered. The other two
(`GENERATED ALWAYS AS IDENTITY`, `CACHE 1`) match exactly. House alignment was preferred over
un-aligning two columns inside an otherwise aligned block.

### 3. Four `truncate_ledger` prose citations in `tests/load/` were left stale

`tests/load/test_fifty_rps_for_ten_minutes.py:89` and
`tests/load/test_enqueue_off_response_path.py:65,69,74` name `truncate_ledger` in docstring prose. They
are **not in `files_modified`** and were not touched (ORCHESTRATION §5, §8). No code depends on the
name — the fixture is autouse and never requested — so these are stale references, not breakage.
Carried in the ledger below.

## What did not go as planned

**Nothing failed.** Both intermediate gates and the full suite were green on first execution, with no
test disabled, no assertion weakened and no existing assertion changed in meaning. Three things were
verified rather than assumed and are worth recording because a later reader would otherwise re-derive
them:

- **`_query_all` genuinely cannot take parameters.** It executes `connection.execute(statement)` with
  no parameter dict and takes its statements as varargs. The plan's instruction to use literals rather
  than `= ANY(:schemas)` is correct at the line level, and `_query_all`'s signature is unchanged.
- **`pg_get_serial_sequence` really does resolve an identity column's sequence**, which is what makes
  the `seqcache` assertion writable without knowing the generated name.
- **The composite key bites the owner too.** `history_event_values()` names `revision_approved` /
  `revision` deliberately, and the whole PH-02 file would fail at its own seeding if D-48's registry
  exclusion were ever dropped — which is the second, independent reason that exclusion is not optional.

## Ledger entries owed

### `.planning/phases/04-.../deferred-items.md`

The planner already seeded §1 through §6 and this executor confirmed every relevant row. Two additions
and one confirmation:

- **§4, confirmed by execution.** Both of the planner's corrections to `04-CONTEXT.md` are correct as
  written. The generic-invariant rename is **four** functions, not two
  (`test_the_ledger_schema_contains_no_security_definer_function`,
  `test_no_native_enum_type_exists_in_the_ledger_schema`, `test_no_foreign_key_leaves_the_ledger_schema`,
  `test_no_column_in_ledger_has_a_floating_point_type` → schema-neutral names). And
  `tests/integration/test_migration_chain.py` was indeed the green-but-blind third file.
- **NEW — §3 (declared deviations not raised as OQs).** *Two acceptance-criteria literals
  (`text[] NOT NULL`, `jsonb NOT NULL DEFAULT '{}'::jsonb`) are satisfied modulo the house DDL's column
  alignment.* Whitespace only, byte-identical end state, no OQ owed under §5 — recorded so a verifier's
  grep miss reads as known rather than as a gap.
- **NEW — §5 (handed forward).** *Four `truncate_ledger` prose citations survive in `tests/load/`*
  (`test_fifty_rps_for_ten_minutes.py:89`, `test_enqueue_off_response_path.py:65,69,74`). Owner: any
  later plan that already has those files in its `files_modified`. Nothing depends on the name; the
  fixture is autouse.
- **§1, still owed and still unallocated.** The **D-53 OQ** — `GENERATED ALWAYS AS IDENTITY` where
  `docs/modules/property-history.lock.yml` `data.owns → history_event → seq` and ADR-0024's Decision
  block say `bigserial`. The revision docstring records the deviation, the behavioural difference and
  the test that proves it, and states that the id is owed and unallocated. `OQ-027…OQ-031` are
  consumed; no id was taken from another phase's range.

### `.planning/ORCHESTRATION-DECISIONS.md`

Rows 1–5 of `deferred-items.md` §2 all land in plan 04-01 and are all now **built and asserted**:

| Phase | Plan | Decision | Rejected alternative | Reversibility |
|---|---|---|---|---|
| 04 | 01 | **D-50** — `grant_table`'s positive form; the lock's literal `REVOKE UPDATE, DELETE` is not issued | Issuing the no-op REVOKE as well (reads in a diff as protection); issuing it instead of the helper | one-way in D-07's sense — no OQ owed, identical end state |
| 04 | 01 | **D-53** — `bigint GENERATED ALWAYS AS IDENTITY (CACHE 1)` where the lock says `bigserial` | `bigserial` (a DEFAULT, only consulted when the caller omits the column); `GENERATED BY DEFAULT` | one-way once rows exist — **an OQ IS owed and its id must be allocated by the orchestrator** |
| 04 | 01 | **D-56** — the registry carries no `workspace_id` and is the project's first `GLOBAL_TABLES` entry, with a numberless reason string | A tenant-scoped registry (zero rows to `registered_actions()`'s only consumer; AC-6 passes vacuously forever); a Python constant | costly |
| 04 | 01 | **D-57** — a composite FK `history_event (action, target_type) → registry (action, target_type)` on a tenant-scoped table | `CHECK (action IN (…31…))`; no constraint; a `BEFORE INSERT` trigger | cheap to drop, costly to add after the pilot |
| 04 | 01 | **D-61** — the lock files' literal action names (leaving A-120 false for four of 31), a derived 13-value `target_type` set, and 28 actions seeded with an empty `detail_keys` | Renaming on the way in, which would make Phase 5's AC-6 red | one-way after the pilot |

Also owed, from the revision's `report_select` block: **`prope_report` holds `SELECT` over `reason` and
`details` across every workspace** — a full-read credential over the module's two most content-bearing
columns. ADR-0037 already declares it and A-126's cross-workspace Success SQL requires it; withholding
it would send that query back to `prope_migrate`, the only role that can delete a history row. Adopted,
argued at the code, and listed as human-check (e) in the plan.

### `.planning/STATE.md`

- Phase 01's note naming **Phase 7 as the first phase that must shrink `EXPECTED_ABSENT_SCHEMAS` is now
  wrong.** Phase 4 is first. The matching comment inside `tests/architecture/test_tenant_coverage.py`
  was corrected in this change; the STATE line was **not** touched (§7).

### `.planning/WINDOWS.md` (broken windows)

- **No new broken window is opened by this plan.** Broken Window #1 (`ruff format --check` fails
  repo-wide on the 120-vs-100 disagreement) is unchanged and was worked around by writing every new file
  in the house ~100 style; `ruff check src/ tests/ alembic/` is green.
- One **near-window, recorded rather than opened**: `OQ-031`'s second half — the ADR-0045 walk
  `continue`s past a `GLOBAL_TABLES` entry where the ADR's own pseudocode asserts against it, so an
  exemption currently buys no check at all. This plan now puts the **first real entry** in that dict, so
  the hole is live rather than theoretical. It is closed from the other side here
  (`test_the_registry_is_readable_with_no_tenant_context_and_holds_thirty_one_rows`) and the walk itself
  is Phase 7's to fix, as `OQ-031` says.
