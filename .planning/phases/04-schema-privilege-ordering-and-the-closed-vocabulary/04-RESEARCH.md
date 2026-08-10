# Phase 4: Schema, privilege, ordering, and the closed vocabulary — Research

**Researched:** 2026-08-10
**Domain:** PostgreSQL 17 privilege and identity semantics; RLS interaction with an intra-schema foreign key; append-only enforcement at the authorisation layer; a closed vocabulary seeded by migration; the first new schema in a test rig built around one
**Confidence:** HIGH on the PostgreSQL semantics (every one quoted from postgresql.org/docs/17 this session) and on the in-repo state (every claim carries a `file:line` read this session); HIGH on the vocabulary derivation (read from all five lock files, not from ADR-0024); MEDIUM on the multixact throughput estimate (arithmetic against a stated load target, not measured); LOW on nothing that is load-bearing

> **This phase adds no dependency.** Everything it needs is already pinned in `pyproject.toml`. The
> research budget therefore went to the hard technical questions instead: what `GENERATED ALWAYS`
> actually refuses and what it does not, what a foreign key costs on a table that only grows, what
> "rolls the caller's transaction back with no partial state" means when the module is forbidden to
> own the transaction, and what a new schema costs in a rig that names `ledger` in two files.
> Section *Standard Stack* says so plainly and argues the two pins that go from *pinned and unused*
> to *pinned and used* in this phase.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

*Condensed from `.planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-CONTEXT.md`
§ Implementation Decisions to the operative sentence of each, with reversibility where CONTEXT gives
one. **The full argument lives in CONTEXT and this file does not restate it** — where research below
disagrees with, extends, or finds a gap in one of these, it says so at that decision's number.
Numbering continues from Phase 3's D-26…D-45; this phase consumes **D-46 through D-65** and no id
outside that range.*

**The first new schema since Phase 1**

- **D-46:** Schema, both tables, constraints, indexes, policies, grants and the 31-row seed ship in
  **one revision**, opening with `CREATE SCHEMA history AUTHORIZATION prope_migrate` +
  `GRANT USAGE ON SCHEMA history TO prope_app, prope_report`. **The `down_revision` is not written by
  the planner** — the executor reads `uv run alembic heads`.
- **D-47:** `EXPECTED_ABSENT_SCHEMAS` shrinks **in this phase**, and `.planning/STATE.md`'s note
  naming Phase 7 as first is now wrong. **Two** edits in `tests/architecture/test_tenant_coverage.py`,
  not one — the constant, *and* the companion `assert tuple(existing) == ("ledger",)`.
- **D-48:** The truncate fixture spans two schemas and **`history.history_action_registry` is
  excluded by name**. Re-seeding inside the fixture is rejected as a second provisioning path.
  `RESTART IDENTITY` resets `seq` between tests; `CASCADE` follows D-57's foreign key.
- **D-49:** The five generic tests in `tests/architecture/test_schema_invariants.py` are
  **parameterised over both schemas**, not copied. Two carry `ledger` in their function names and are
  renamed as part of the edit. **This phase edits a Phase 1 test file.** — *Reversibility: cheap.*

**Append-only is a privilege, and the privilege is the product**

- **D-50:** The grant matrix uses `grant_table` in its **positive form**. No literal
  `REVOKE UPDATE, DELETE … FROM prope_app` is issued, even though the lock's `libraries_frameworks`
  names that statement. **The end state is asserted, not the statement**: two
  `has_table_privilege(...)` calls returning false. — *Reversibility: one-way, in D-07's sense.*
- **D-51:** `history_action_registry` is `SELECT`-only for `prope_app`. **Derived from ADR-0038**, not
  chosen. Disagreement is an OQ, not a quiet reversal.
- **D-52:** The privilege test is a **structural mirror of `tests/security/test_append_only_privilege.py`**,
  including the positive control inside the attempting transaction and the grant/observe/revoke-in-
  `finally` mutation check. Not optional polish.

**The total order**

- **D-53:** `seq` is `bigint GENERATED ALWAYS AS IDENTITY`, `NOT NULL`, `UNIQUE` — **not** the primary
  key (`id`, the `hev_` ULID, is) and **not** `bigserial`. Monotonic is not gapless; assignment order
  is not commit order. — *Reversibility: one-way once rows exist.*
- **D-54:** **Exactly the twelve columns ADR-0024 names, no thirteenth.** `occurred_at timestamptz
  NOT NULL` with no default; `actor_type text` with a `CHECK (… IN ('user','system'))` and never a
  native enum; `CHECK (actor_id IS NOT NULL OR actor_type = 'system')`;
  `CHECK (reason IS NULL OR char_length(reason) <= 500)` — characters, not bytes. All CHECKs named.
- **D-55:** **All four declared indexes ship with the table**, in this phase. No fifth is invented;
  none of the four is dropped; there is no index on `details`.

**The closed vocabulary**

- **D-56:** The registry carries **no `workspace_id`** and becomes the first entry in `GLOBAL_TABLES`
  *in code*, with a written reason. A tenant-scoped registry returns zero rows to `registered_actions()`'s
  only consumer and **AC-6 would compare two empty sets and pass forever.** — *Reversibility: costly.*
- **D-57:** The vocabulary is enforced by a **composite foreign key** `history_event (action,
  target_type) → history_action_registry (action, target_type)`, the registry keyed on `action` and
  carrying `UNIQUE (action, target_type)` to receive it. `CHECK (action IN (…31…))`, no-constraint,
  and a `BEFORE INSERT` trigger are all rejected by name. — *Reversibility: cheap to drop, costly to
  add later.*
- **D-58:** `details jsonb NOT NULL DEFAULT '{}'::jsonb`. No GIN index.
- **D-59:** Registry shape **and** its 31-row seed ship in the same revision as the tables.
  `detail_keys text[] NOT NULL`, `requires_reason boolean NOT NULL`, `writing_module text NOT NULL`
  with a `CHECK` over the five writer names.
- **D-60:** The 31 names are derived here from the five writing modules' `outputs` blocks and the
  derivation is recorded. The union is **exactly 31 with no adjustment**. The count is contested in
  the authorities; **adopt 31** and raise `OQ-027`.
- **D-61:** `target_type` and `detail_keys` are **derived, not read**. Thirteen `target_type` values;
  only the three declared `detail_keys` sets are seeded and the other twenty-eight are left empty.
  `OQ-028` (the naming rule) and `OQ-029` (the missing enumerations). — *Reversibility: one-way after
  the pilot.*
- **D-62:** `requires_reason` and the `details` allow-list are enforced **in Python, at one validation
  site**, and the asymmetry with D-57's engine-enforced half is stated. **The absence of a database
  backstop is asserted, not assumed** — a hand-written `INSERT` as `prope_migrate` carrying an
  unregistered key and no reason must *succeed*.
- **D-63:** The refusal is a **dedicated exception type**, deliberately not `ValueError`. Its reason
  vocabulary is a `StrEnum` byte-identical to the metric's declared label set — three members, no
  fourth.

**Where this phase stops and Phase 5 begins**

- **D-64:** **The validating write path lands in Phase 4; the three registered seams land in Phase 5.**
  Phase 4 builds the registry loader, the three-way validator, the refusal type and its vocabulary,
  the rejection counter, and an internal insert on a session handed to it. — *Reversibility: cheap.*
- **D-65:** The package is `src/prope/property_history/`. It **does not import FastAPI at any depth**,
  **does not touch `app.py` or `worker.py`**, and **its counter lives in the module** — which surfaces
  the `LOGGABLE_FIELDS` collision on `reason`.

### Claude's Discretion

*Copied faithfully. These are **open, not decided**. Every one is resolved in
§ *Resolving Claude's Discretion* below, with the evidence, or handed to the planner with the grounds
on which to decide.*

- How the `LOGGABLE_FIELDS` collision on `reason` is resolved (D-65), keeping the property assertable
  in one place.
- Whether the rejection counter's three-reason `StrEnum` lives in `domain.py` or beside the counter,
  and whether the byte-identity is asserted by a test or by proximity.
- The `id` generation site — module-local or a shared identifier helper.
- Whether `scope_prompt_id` gets a column-level constraint in this phase at all.
- `prope_report`'s read grants on both tables.
- How many OQs the three vocabulary findings become.
- The exact `GLOBAL_TABLES` reason string (D-56) — the first one in the file, and it sets the register.
- Whether D-60's derivation table is committed as a fixture Phase 5's AC-6 reads, or re-derived there.
- Test file placement against the lock's `test_ref` paths.

### Deferred Ideas (OUT OF SCOPE)

*Copied.* Two, both with a named owner:

- **Each writing module must register its own `detail_keys`, and no phase owns that obligation.**
  Captured in `OQ-029`; natural homes are Phases 10, 13, 16 and 22.
- **AC-3's arithmetic does not close** — "all ten events" over a lifecycle enumerating nine. Handed to
  Phase 5, which owns AC-3.

Recorded so a planner does not mistake them for gaps, these are fixed ROADMAP boundaries: `append()`,
`read()` and `registered_actions()` as INT-006/007/008's registered signatures, cursor semantics,
`scope_prompt_id` as a contract, AC-6's equality and the cache wiring belong to **Phase 5**; AC-1,
AC-7, AC-8, AC-9, AC-10 and six of the seven metrics belong to **Phase 6**; the five writing modules
are Phases 7, 10, 13, 16 and 22; the SPA and the deployment stack own no milestone.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research support |
|----|-------------|-----------------|
| **PH-02** | "The application's database role cannot UPDATE or DELETE a history event — the engine refuses, not an application guard" [VERIFIED: `.planning/REQUIREMENTS.md:38`] | § *Pattern 3* (the grant matrix), § *Pattern 8* (the D-52 mirror), § *Pitfall 1* (privilege is checked before RLS, which is why the positive control is load-bearing), § *Pitfall 2* (`has_table_privilege` counts PUBLIC and role membership) |
| **PH-04** | "Two events written in one transaction have a stable, defined order even when their timestamps are identical" [VERIFIED: `.planning/REQUIREMENTS.md:40`] | § *Pattern 2* (identity, not `bigserial`), § *Pitfall 3* (**`OVERRIDING SYSTEM VALUE` bypasses `GENERATED ALWAYS` with no privilege check** — the gap D-53 does not cover), § *Pitfall 4* (a sequence `CACHE > 1` destroys the global order), § *Pitfall 5* (assignment order is not commit order, and what that costs Phase 5) |
| **PH-05** | "An append carrying an unregistered action or details key raises, fails the caller's transaction, and is counted" [VERIFIED: `.planning/REQUIREMENTS.md:41`] | § *Pattern 6* (the three-way validator), § *Pattern 7* (**who performs the rollback, and why `append()` must not**), § *Pitfall 8* (a naive test passes against a module that opened its own transaction), § *Pitfall 9* (the counter survives the rollback because it is process state) |

**Also touched but not owed by this phase — state it, do not tick it:**

- **PH-06** (the vocabulary equality) is **Phase 5** [VERIFIED: `.planning/REQUIREMENTS.md:188`]. This
  phase seeds what Phase 5 asserts against and owes it a written baseline (D-60). § *Resolving
  Claude's Discretion #8* records two engineering facts Phase 5 inherits that nothing else names.
- **PH-07** (no route resolves to property-history) is **Phase 6** and, per
  `.planning/research/PITFALLS.md` §5, *"cannot actually run until every module is mounted — i.e. not
  before phase 23"* [VERIFIED: `.planning/research/PITFALLS.md` §5]. D-65 makes the FastAPI absence
  **structural**, which is what makes the Phase 6 assertion guard something already impossible.
- The **access-control** row of PITFALLS §1 owes *"the `SECURITY DEFINER` set is exactly the
  sanctioned functions"*. D-49's parameterisation delivers the `history` half of it three phases
  early, as a side effect. Say so; do not claim the criterion.
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

Extracted from `.claude/CLAUDE.md`. Same authority as CONTEXT's locked decisions.

| Directive | Bearing on this phase |
|---|---|
| Python 3.13.x; FastAPI + uvicorn + pydantic v2 | `requires-python = ">=3.13,<3.14"` [VERIFIED: `pyproject.toml:8`]. **FastAPI is the one baseline component this module must not reach** (D-65, and the lock: *"NOT FastAPI. Deliberate and testable"*) |
| SQLAlchemy 2.0 async over asyncpg; **Alembic carries RLS policies, constraints, triggers** | One revision carries schema + two tables + four indexes + one policy + three grant matrices + a 31-row seed. Autogenerate is never trusted (D-04) — it can see none of those |
| PostgreSQL 17, schema per module, RLS deny-by-default, `SET LOCAL app.workspace_id` | `history` is schema #2 of 8. `history_event` is policied; `history_action_registry` is **exempted with a written reason** and is the first exemption in code |
| **History rows are never deleted, at the database privilege level** | This is the phase. `prope_app` gets `SELECT, INSERT` and nothing else; the REVOKE-shaped absence *is* PH-02 |
| **Four `SECURITY DEFINER` functions are sanctioned and a test asserts the set is exactly these four** | None is in `history`. D-49's parameterisation is what asserts it for this schema |
| property-history has an **empty consumes list** and no outbound edge; `target_id`/`actor_id` are values, not foreign keys | The only foreign key in the module is D-57's, and it points at the module's own second table. The `history` counterpart of `test_no_foreign_key_leaves_the_ledger_schema` must still pass |
| Vietnamese only, behind an i18n layer; statuses stay literal | Directly decides D-54's `reason` cap: `char_length`, not `octet_length`, not `varchar(500)`. See § *Pattern 4* |
| **Do not edit `docs/`** (BSP-LINK § Out of bounds) | Four conflicts. Three already have files (`OQ-027`, `OQ-028`, `OQ-029`, on disk). The fourth is new — see § *Summary* |
| **GSD workflow enforcement** | Applies to execution, not to this document. The GSD toolchain is absent (ORCHESTRATION §0) and this orchestration is the sanctioned entry point |

---

## Summary

Phase 4 is the purest instance in Prope of the project's own stated pattern: **the migration carries
the guarantee, and the application code is what the guarantee protects.** PH-02 contains no
application code at all — it is proven or disproven by two `has_table_privilege` calls and a statement
the engine refuses. A plan that spends its weight on the validator and treats the grant matrix as a
line in a migration has inverted the phase.

The research turned up **six findings that change or extend a CONTEXT decision**, and they are the
reason this document exists rather than the pattern catalogue.

**1. `GENERATED ALWAYS AS IDENTITY` is stronger than `bigserial` and it is not unbypassable.**
PostgreSQL's own `INSERT` documentation says: *"For an identity column defined as `GENERATED ALWAYS`,
it is an error to insert an explicit value (other than `DEFAULT`) without specifying either
`OVERRIDING SYSTEM VALUE` or `OVERRIDING USER VALUE`"* [CITED: postgresql.org/docs/17/sql-insert.html].
The naive form is refused with SQLSTATE **`428C9` (`generated_always`)** [VERIFIED: postgres
`src/backend/utils/errcodes.txt`, `ERRCODE_GENERATED_ALWAYS`]. But `OVERRIDING SYSTEM VALUE` carries
**no privilege requirement in PostgreSQL** — the documentation attaches none, and the engine's own
error message names the escape hatch in its `HINT`. D-53 says `GENERATED ALWAYS` "makes the engine
refuse a caller-supplied value"; that is true of the statement anyone would actually write and false
of the statement someone determined would write. **The correct posture is the one this repository has
already used twice**: assert the absence rather than assume it (revision `0004`'s A-055 boundary,
D-62's own owed pair). Two tests, both cheap — the engine refuses the naive form, *and* the source
gate refuses the literal token `OVERRIDING` anywhere under `src/prope/`. See § *Pitfall 3*.

**2. Identity columns need no sequence grant; `bigserial` would have needed one, and forgetting it is
a runtime failure on the first append.** With a `serial`/`bigserial` column the implicit sequence is a
separate privilege object: *"`GRANT INSERT ON test_old TO foo; … INSERT INTO test_old (payload) VALUES
('d'); ERROR: permission denied for sequence test_old_id_seq"* [CITED:
enterprisedb.com/blog/postgresql-10-identity-columns-explained, by the author of the identity-column
feature]. Identity columns create the sequence *"as a proper internal dependency of the table"* and no
sequence grant is required. This is **independent corroboration for D-53 that D-53 does not cite**,
and it matters operationally: under `bigserial`, `grant_table` (`alembic/ddl.py:97-123`) would have
been silently insufficient for this one table, because it grants on tables and knows nothing about
sequences, and the failure would have arrived at the first `append()` in a new environment rather than
in the migration.

**3. ADR-0045 already wrote D-56's `GLOBAL_TABLES` entry, and its reason string carries the stale
count.** The ADR's decision block contains, verbatim:
`'history.history_action_registry': "30 seeded actions, immutable, ADR-0024 and ADR-0038"`
[VERIFIED: `docs/adr/0045-every-table-is-tenant-scoped-unless-declared-global.md:46-51`]. So D-56 is
**derived from an ADR rather than chosen** — the same footing D-51 and Phase 2's D-17 stand on — and
CONTEXT's phrase *"the first entry Prope has ever made"* is true of the code and not of the
authorities. Two consequences. The planner should not present D-56 as a novel decision in the
migration docstring; it should cite ADR-0045 and say the ADR is being implemented. **And the ADR is a
sixth site of OQ-027's stale count that OQ-027 does not list** — the one whose text this phase is
about to copy into a security-relevant file. See § *Resolving Claude's Discretion #6*.

**4. The implemented coverage walk *skips* a `GLOBAL_TABLES` entry; ADR-0045's pseudocode *asserts*
against it.** The ADR writes `if table in GLOBAL_TABLES: assert rls_state_matches_declaration(table);
continue`; the code writes `if qualified in GLOBAL_TABLES: continue`
[VERIFIED: `tests/architecture/test_tenant_coverage.py:120-121`]. Adding the registry therefore buys
it **no assertion whatsoever** — not that it lacks `workspace_id`, not that row security is off, not
that the grants are what D-51 says. The exemption is currently a hole with a sentence in front of it.
The plan should close it, and the cheapest way is also the strongest: **a test that loads the registry
on a session with no tenant context and asserts 31 rows come back.** That single assertion proves the
table is genuinely global, proves the seed landed, and is exactly the read ADR-0038's process-start
cache performs — so it fails for the real reason if D-56 is ever reversed.

**5. The truncate fixture's `CASCADE` reaches the seed from the direction nobody checks.** PostgreSQL:
*"`CASCADE` — Automatically truncate all tables that have foreign-key references to any of the named
tables"* [CITED: postgresql.org/docs/17/sql-truncate.html]. So including
`history.history_action_registry` in the list drags `history_event` along (harmless, it is truncated
anyway) **and empties the 31-row seed** (fatal, silently, from the second test onward). The reverse
direction is safe: `history_event` has no inbound foreign key, so truncating it alone is legal without
`CASCADE`. D-48 is correct and the mechanism is now quoted rather than assumed.

**6. The rollback in PH-05 is performed by the *caller's* context manager, not by `append()` — and a
naive test cannot tell the difference between the two.** Because D-62 puts the Python validation
first, an unregistered action or key raises **before any SQL is issued**, so PostgreSQL has not
aborted anything; the transaction is merely destined to be rolled back if the caller unwinds
correctly. `append()` must therefore **never call `session.rollback()`** — doing so ends the caller's
transaction underneath them, which is the exact inverse of ADR-0023's *"commits or rolls back with
it"*. The test that proves SC3 honestly must write a stand-in state-change row **in the same
transaction, before the append**, and assert that row is gone afterwards. A test that only asserts "no
history row" passes against a module that opened its own transaction — which is D-19's shape and the
one thing ADR-0023 forbids. See § *Pattern 7* and § *Pitfall 8*.

**Primary recommendation:** ship one revision that creates `history` with `AUTHORIZATION
prope_migrate`; declare `seq` as `bigint GENERATED ALWAYS AS IDENTITY NOT NULL` with an explicit
`CACHE 1` sequence option and a named `UNIQUE`; give `history_event` exactly `SELECT, INSERT` and the
registry exactly `SELECT` for `prope_app`, both `SELECT` for `prope_report`; enforce the vocabulary
with the composite foreign key and **no `ON DELETE`/`ON UPDATE` clause**, following `0003`'s stated
rule about naming behaviours for impossible cases; write the `details` bind as
`CAST(:details AS jsonb)` over a `json.dumps` string; validate in Python on a mapping the caller hands
in rather than a module-level global; and assert three absences — the engine's refusal of a supplied
`seq`, the source's refusal of `OVERRIDING`, and the Python-only boundary D-62 owes.

---

## Architectural Responsibility Map

| Capability | Primary tier | Secondary tier | Rationale |
|---|---|---|---|
| Append-only (PH-02) | **Database (grant matrix)** | — | ADR-0025: *"a log the application can rewrite is a Sheet with better indexing"*. No application code participates |
| Total order (PH-04) | **Database (identity column)** | Source gate | D-53. The engine assigns; § *Pitfall 3*'s gate closes the one hole the engine leaves |
| Action / target-type pairing | **Database (composite FK)** | Python (first, for the metric) | D-57. The Python check runs first only so `append_rejected_total{reason=…}` exists; the engine is the guarantee |
| `details` allow-list, `requires_reason` | **Python, one validation site** | — | D-62. A CHECK cannot reach another table; ADR-0023 rejects triggers for this module *by name* |
| Tenant isolation on `history_event` | **Database (RLS policy)** | `workspace_transaction` in tests | ADR-0035 / ADR-0045. `enable_tenant_rls('history','history_event')` |
| The vocabulary's existence and content | **Migration (seed)** | — | D-59. ADR-0038's safety argument *is* a deploy ordering, and that only holds if the seed is a migration |
| The registry as an in-process mapping | **Python (loader)** | Database (`SELECT` at start) | ADR-0038. **Phase 4 builds the loader as a plain function; Phase 5 owns the process-start global** (D-64, D-65) |
| The refusal's shape and vocabulary | **Python (`domain.py`)** | Metric label | D-63. A named type; three reasons; no fourth |
| The rejection count | **Module-local counter** | — | D-65. `observability.py` is scoped to *"The Phase 2 counters, and only those"* [VERIFIED: `src/prope/observability.py:1`] |
| The transaction | **The caller** | — | ADR-0023 / INT-006. This module never opens one — **the opposite of call-ledger's D-19** |
| Cross-workspace reporting reads | **`prope_report`** | — | ADR-0037, written *about this table*. See § *Resolving Claude's Discretion #5* |

---

## Standard Stack

### Core — everything is already pinned; nothing is added

| Library | Version | Status in this phase | Why it is the right pin |
|---|---|---|---|
| `sqlalchemy[asyncio]` | **2.0.51** *(pinned, in use)* | The session `append()` is handed; the jsonb codec that decides § *Pitfall 6* | A-128. Its asyncpg dialect registers the `jsonb` codec this phase's write path runs through [VERIFIED: `.venv/…/sqlalchemy/dialects/postgresql/asyncpg.py:1208-1238`] |
| `asyncpg` | **0.31.0** *(pinned, in use)* | Returns `text[]` as `list[str]` and `jsonb` as a decoded object | A-128 |
| `alembic` | **1.19.1** *(pinned, in use)* | The revision that is the whole phase | D-04 / A-128 |
| `python-ulid` | **4.0.1** *(pinned; first used by this module)* | `hev_`-prefixed event ids | **Argued below — this is a three-week-old major and the argument is not a formality** |
| `pydantic` | **2.13.4** *(pinned; first used by this module)* | `details` shape validation, per the lock's `libraries_frameworks` | **Argued below, including where it is *not* the right tool** |
| `prometheus-client` | **0.26.0** *(pinned, in use)* | `prope_property_history_append_rejected_total` | ADR-0030. `REGISTRY.get_sample_value(...)` is the repo's established assertion pattern [VERIFIED: `tests/broker/test_publish_confirm_failures.py:56`] |
| `structlog` | **26.1.0** *(pinned, in use)* | The rejected-append log line | ADR-0030 / A-046 |

> **`python-ulid==4.0.1` — the pin, argued.** 4.0.1 is the current release, published **2026-07-20**
> [VERIFIED: pypi.org/pypi/python-ulid/json]. **4.0.0 was published the same day**, and it is a real
> major: it *"Removed `ValueProvider` and the `ULID.provider` class attribute"* and replaced them with
> a public `ULIDGenerator` carrying pluggable monotonicity policies —
> `StrictMonotonicPolicy` (the new **default**), `LaxMonotonicPolicy`, `PureRandomPolicy` [VERIFIED:
> github.com/mdomke/python-ulid releases, tags 4.0.0 and 4.0.1]. 4.0.1's only change is renaming
> `ULID.from_uuidv7` to `ULID.from_uuid7`.
>
> **Keep 4.0.1.** Three reasons, and the third is the one that matters. (a) The blast radius of the
> 4.0 break against this repository is *zero*: `ULID.provider` is referenced nowhere, because
> `python-ulid` was pinned in Phase 1 and first called in Phase 2 through two sites that use only
> `ULID()` [VERIFIED: `src/prope/call_ledger/api.py:433`, `src/prope/call_ledger/schemas.py:441`].
> (b) `uv.lock` already resolves 4.0.1, so *downgrading* is the change that carries risk, not staying.
> (c) The 4.0 default moves in the direction this module wants: within one generator, ids created in
> the same millisecond now increment rather than randomise [VERIFIED:
> `.venv/Lib/site-packages/ulid/__init__.py:71-160, 231-241`], which removes a class of confusing test
> flake where two events written in one transaction have ids that compare in a random order. It
> changes nothing about correctness — **A-125 forbids sorting on the id and D-53 puts every ordering
> claim on `seq`** — and ADR-0024's rejection of *"sort by `occurred_at` with a tiebreak on id"* stands
> undisturbed, because `default_generator` is a **process-local singleton**
> [VERIFIED: same file, line 231] and two containers generate independently.
>
> **One 4.0 behaviour the plan should name rather than discover.** `StrictMonotonicPolicy` *"Raises
> ValueError on millisecond randomness exhaustion"* [VERIFIED: same file, lines 117-130]. Exhaustion
> means 2^80 ids in one millisecond and is unreachable, so this is not a risk — but it is a
> **`ValueError` raised from inside the id generator on the audit log's write path**, which is
> precisely the exception type D-63 spends a paragraph explaining why this module must not raise. A
> reviewer who reads D-63 and then greps for `ValueError` will find one, from the library. Two lines
> in the module docstring cost nothing; the alternative is that finding being made in review.

> **`pydantic==2.13.4` — the pin, and the honest scope of its job.** 2.13.4 is the current release
> [VERIFIED: pypi.org/pypi/pydantic/json], already pinned [VERIFIED: `pyproject.toml:19`], and there is
> no version question to answer. There *is* a scope question. The lock says pydantic *"validates the
> `details` payload against the per-action key allow-list at append time (A-124). **Chosen because it
> is already the baseline's validation library (ADR-0026), not for a property specific to this
> module**"* [VERIFIED: `docs/modules/property-history.lock.yml:285-287`] — the field concedes the
> point itself. The allow-list check is `set(details) - registered_keys`, a set difference. Building
> thirty-one `create_model(..., model_config=ConfigDict(extra="forbid"))` models to express it would
> buy type coercion nobody asked for and turn one clear refusal into a `ValidationError` that then has
> to be translated back into D-63's three-member vocabulary — adding a failure mode to the path whose
> whole point is that its failure mode is exactly three shapes. **Recommendation: pydantic validates
> that `details` is a mapping of `str` keys to JSON-scalar values (a real job, and one it is good at);
> the key allow-list is a set difference.** Both run at D-62's single validation site, so the lock's
> "one validation site" property is intact. This is a deviation in *mechanism* with an identical end
> state and it rides D-50's footing: record it in the plan, do not raise an OQ. `OQ-030` is unconsumed
> if a reviewer disagrees.

### Deliberately absent from this phase

| Not used | Why |
|---|---|
| **FastAPI** | D-65 and the lock make the absence *structural*, not asserted. Nothing in `src/prope/property_history/` may import it at any depth. This is what makes Phase 6's PH-07 cheap |
| **`aio-pika` / the broker** | The lock's `events.publishes: []` carries the note *"read 'No broker (A-012)'. One EXISTS (ADR-0028). **Nothing to publish to** is the surviving half"* [VERIFIED: `docs/modules/property-history.lock.yml:136-140`]. A history event is a row, not a message |
| **A new testcontainer** | The Phase 1 PostgreSQL rig is the whole requirement. No broker fixture is touched |
| **`PyYAML`** | Not needed here — and **it is not a declared dependency at all**. It resolves only as a transitive of `uvicorn[standard]` [VERIFIED: `uv.lock`, `uvicorn` `[package.optional-dependencies] standard = [… { name = "pyyaml" } …]`]. That is a live trap for Phase 5, recorded in § *Resolving Claude's Discretion #8* |
| **A native PostgreSQL `ENUM`** | Pitfall 4 from Phase 1, now a standing rule with a test behind it. `actor_type` is `text` + a named CHECK |
| **A trigger, of any kind** | ADR-0023 rejects triggers **for this module by name**; ADR-0025 rejects a `BEFORE UPDATE` trigger as *"strictly weaker for the same effort"* |
| **A fifth `SECURITY DEFINER` function** | The sanctioned set is four and none is in `history` |

**Installation:** none. `uv sync` is unchanged by this phase, and `uv.lock` must not move. **A plan
whose task list contains a `uv add` has found something this research did not, and should say what.**

---

## Package Legitimacy Audit

> **This is an agent judgement, not a detector result.** `gsd-tools query package-legitimacy` does not
> exist in this environment (ORCHESTRATION §0). Phase 2's audit was run against a real seam and
> recorded three `SUS` verdicts; this one is a reading of `pyproject.toml`, `uv.lock` and the two
> upstream registries, performed by hand this session, and it is labelled as such.

**No package is added by this phase, so the audit has one honest question:** are the two libraries
that go from *pinned and unused* to *pinned and used* still what they were when Phase 1 pinned them?

| Package | Registry | Latest / pinned | Source repo | Judgement | Disposition |
|---|---|---|---|---|---|
| `python-ulid` | PyPI | 4.0.1 = latest, 2026-07-20 [VERIFIED: pypi.org/pypi/python-ulid/json] | github.com/mdomke/python-ulid | **Watch, approved.** A **3-week-old major** on the identifier path. Release notes are specific, list breaking changes by name, and the break does not touch this repo | **Approved.** Named by `docs/modules/property-history.lock.yml:291` and by A-045 / ADR-0003 — an authoritative in-repo spec, not a search result. The version argument is in § *Standard Stack* and is a risk posture, not a compatibility fact |
| `pydantic` | PyPI | 2.13.4 = latest [VERIFIED: pypi.org/pypi/pydantic/json] | github.com/pydantic/pydantic | **Clean.** Baseline library, ADR-0026, in the lock's `libraries_frameworks` | **Approved.** Scope narrowed — see § *Standard Stack* |

**Two signals that carry no information, and are recorded so nobody reads them as evidence.**
First, exactly as Phase 2 found: **PyPI exposes no download counter**, so a `unknown-downloads`
signal fires for every package on the index and distinguishes nothing. Second, and specific to this
audit: **"released three weeks ago" fires for `python-ulid` 4.0.1 and would fire identically for a
routine patch of a fifteen-year-old project.** `python-ulid`'s history runs 3.1.0 (2025-08-18) →
3.2.0 (2026-07-17) → 4.0.0 → 4.0.1 (2026-07-20), which is a maintained project doing a deliberate API
cleanup in one week, not a package that appeared. The *substantive* question — does the major break
touch us — was answered by reading the release notes and grepping the repo for `ULID.provider`, which
is a check a recency heuristic cannot perform.

**Packages removed due to a [SLOP] verdict:** none. **Build hooks / postinstall equivalents:** none;
neither ships one. **`checkpoint:human-verify` warranted:** none.

---

## Architecture Patterns

### System diagram

```
   ┌──── Phases 7 / 10 / 13 / 16 / 22 — the five writing modules. NONE EXISTS YET. ─────┐
   │  access-control (10)   provider-access (4)   prompt-registry (5)                   │
   │  evaluation (4)        release-control (8)                    = 31 actions         │
   └───────────────┬────────────────────────────────────────────────────────────────────┘
                   │  each opens ITS OWN transaction and hands the session in
                   ▼                          ( ADR-0023 — the opposite of call-ledger's D-19 )
   ┌──────── src/prope/property_history/  ── NO FastAPI import, at any depth (D-65) ────┐
   │                                                                                    │
   │   load_action_registry(session) ──► MappingProxyType[str, RegisteredAction]        │
   │        one SELECT, no tenant context   (ADR-0038 — Phase 5 owns the process global) │
   │                                          │                                          │
   │   record_event(session, event, registry) │                                          │
   │        │                                 ▼                                          │
   │        ├── 1. action in registry?  ──no──► HistoryAppendRejected(unknown_action)    │
   │        ├── 2. set(details) ⊆ keys?  ──no──► HistoryAppendRejected(unknown_detail_key)│
   │        ├── 3. requires_reason met?  ──no──► HistoryAppendRejected(missing_reason)   │
   │        │                                        │  append_rejected_total{reason}++  │
   │        │        NO SQL HAS BEEN ISSUED YET ─────┤  (process state — survives the    │
   │        │                                        │   rollback by construction)       │
   │        ▼                                        └─► raise ─► the CALLER's           │
   │   INSERT … CAST(:details AS jsonb) …                        `async with` unwinds    │
   │        │  seq omitted — the engine assigns it               and rolls back BOTH     │
   └────────┼───────────────────────────────────────────────────────────────────────────┘
            ▼
   ┌──────────────── PostgreSQL 17 · schema `history` (AUTHORIZATION prope_migrate) ─────┐
   │                                                                                     │
   │  history_event                              history_action_registry                 │
   │   seq  bigint GEN ALWAYS AS IDENTITY         action  text  PK                        │
   │        NOT NULL UNIQUE  CACHE 1              target_type    text NOT NULL            │
   │   id   text PK  (hev_ ULID)                  detail_keys    text[] NOT NULL          │
   │   workspace_id text  ── RLS ──┐              requires_reason boolean NOT NULL        │
   │   actor_type ∈ {user,system}  │              writing_module  text NOT NULL + CHECK   │
   │   actor_id / target_type /    │              UNIQUE (action, target_type) ◄──┐       │
   │   target_id / scope_prompt_id │                                              │       │
   │   reason  char_length ≤ 500   │              31 SEEDED ROWS (D-59, D-60)     │       │
   │   details jsonb NOT NULL '{}' │              NO workspace_id — GLOBAL_TABLES │       │
   │   occurred_at timestamptz     │              (D-56, and ADR-0045:46-51       │       │
   │   FK (action,target_type) ────┼──────────────────────────────────────────────┘       │
   │                               │                                                      │
   │  policy history_event_tenant  │  grants:  prope_app  → SELECT, INSERT  (no UPDATE,   │
   │   USING + WITH CHECK on       │                        no DELETE — THIS IS PH-02)    │
   │   workspace_id = current_setting('app.workspace_id', true)   registry → SELECT only  │
   │                                  prope_report → SELECT on both (ADR-0037)            │
   │  4 indexes, no fifth:                                                                │
   │   (workspace_id, scope_prompt_id, seq DESC)   (workspace_id, target_type, target_id, │
   │   (workspace_id, actor_id, seq DESC)           seq DESC)   (workspace_id, action, seq)│
   └──────────────────────────────────────────────────────────────────────────────────────┘
```

### Recommended project structure

```
src/prope/property_history/
├── __init__.py          # NEW. Exports nothing FastAPI-shaped, ever.
├── domain.py            # NEW. HistoryEvent draft, RegisteredAction, RejectionReason (StrEnum),
│                        #      HistoryAppendRejected. D-63. The vocabulary file — mirrors
│                        #      call_ledger/domain.py, and observability imports IT, never the reverse.
├── registry.py          # NEW. load_action_registry(session) -> MappingProxyType. ADR-0038's mapping,
│                        #      built here as a plain function; Phase 5 owns the process-start global.
├── writer.py            # NEW. record_event(session, event, registry). D-64's "internal insert that
│                        #      runs on a session handed to it". Phase 5 renames or wraps it.
├── models.py            # NEW (recommended, see Discretion #9). Core objects for the two tables.
└── observability.py     # NEW. append_rejected_total ONLY. Six other metrics are Phase 6's.

src/prope/observability.py          # EDITED — LOGGABLE_FIELDS grows. CROSS-PHASE EDIT #2.
alembic/versions/000N_history_schema_and_vocabulary.py   # NEW. N read from `uv run alembic heads`.
tests/
├── conftest.py                              # EDITED — truncate spans two schemas, registry excluded.
├── architecture/test_tenant_coverage.py     # EDITED — D-47's TWO edits + the registry's own assertion.
├── architecture/test_schema_invariants.py   # EDITED — D-49 parameterisation. CROSS-PHASE EDIT #1.
├── architecture/test_no_overriding_system_value.py   # NEW — Pitfall 3's source gate.
├── security/test_history_is_append_only_by_privilege.py     # NEW — PH-02. Matches the lock's test_ref.
├── security/test_history_seq_cannot_be_supplied.py          # NEW — Pitfall 3's engine half.
├── security/test_history_validation_has_no_database_backstop.py  # NEW — D-62's owed pair.
├── unit/test_details_allow_list.py                          # NEW — the pure half of AC-5.
└── integration/
    ├── test_same_transaction_events_have_a_stable_order.py  # NEW — PH-04. Matches the lock's test_ref.
    ├── test_unregistered_detail_key_fails_the_transaction.py# NEW — PH-05. DEVIATES from the lock's
    │                                                        #   test_ref path; see Discretion #9.
    └── test_action_registry_loads_without_a_tenant.py       # NEW — the D-56 assertion that matters.
```

> **The structure claim worth checking, and it does not hold this time.** Revision `0004`'s docstring
> says *"NO TEST RIG EDIT IS NEEDED, AND THAT IS THE POINT"* [VERIFIED:
> `alembic/versions/0004_workspace_retention.py:47-55`]. That is true of a new **table** and false of a
> new **schema**, and the difference is two literals: `tests/conftest.py:97` filters
> `WHERE schemaname = 'ledger'` and `tests/architecture/test_tenant_coverage.py:151` asserts
> `tuple(existing) == ("ledger",)`. Both were read this session. `test_no_sql_interpolation.py` *does*
> adopt the new module for free and correctly — it `rglob`s `src/prope/` with an empty `ALLOWED`
> [VERIFIED: `tests/architecture/test_no_sql_interpolation.py:34-50`].

### Pattern 1 — The schema, and why `AUTHORIZATION` is load-bearing

```python
# alembic/versions/000N_history_schema_and_vocabulary.py
def upgrade() -> None:
    # ADR-0027, and the two lines revision 0001 wrote for `ledger`
    # (alembic/versions/0001_roles_and_schemas.py:62-63). AUTHORIZATION is not
    # decoration: ADR-0035's owner bypass is what exempts prope_migrate from the
    # tenant policy, and it only holds if prope_migrate OWNS what is created here
    # (alembic/ddl.py:27-41). CREATE SCHEMA ... AUTHORIZATION makes every object
    # created inside it owned by that role.
    op.execute("CREATE SCHEMA history AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA history TO prope_app, prope_report")

    assume_migrate_role()          # SET LOCAL ROLE prope_migrate, per 0002-0004
    ...
    reset_role()                   # or Alembic's own write to public.alembic_version fails
```

**Order matters and is easy to get backwards.** `CREATE SCHEMA … AUTHORIZATION` must run *before*
`assume_migrate_role()`, because `prope_migrate` is not guaranteed to hold `CREATE ON DATABASE`;
revision `0001` created `ledger` as the connected superuser for exactly this reason. Everything after
it runs under the assumed role so the tables are owned correctly.

### Pattern 2 — `seq`: identity, `CACHE 1`, `UNIQUE`, and not the primary key

```sql
CREATE TABLE history.history_event (
    -- A-125 / D-53. GENERATED ALWAYS, not bigserial: a bigserial is a
    -- DEFAULT nextval(), and a default is only consulted when the caller omits
    -- the column. prope_app holds INSERT by design, so a hand-written statement
    -- supplying its own seq would be accepted and the total order would stop
    -- being total with no error anywhere.
    --
    -- CACHE 1 is written out although it is also the default. With cache > 1
    -- "the values might be generated out of sequence when all the sessions are
    -- considered" (postgresql.org/docs/17/sql-createsequence.html) — session A
    -- reserves 1..10 and session B reserves 11..20 and returns 11 first. That is
    -- the ONE setting that destroys this column's only property, it is a
    -- one-word ALTER SEQUENCE away, and a schema-invariant test reads seqcache
    -- back. Naming it here is what makes the assertion read as intentional.
    seq          bigint      GENERATED ALWAYS AS IDENTITY (CACHE 1) NOT NULL,

    -- A-045 / ADR-0003. The PK, because it is what INT-006 returns, what the
    -- lock says is logged, and what A-045 makes the convention across eight
    -- modules. A bigint surrogate beside it would be two identities for one row.
    id           text        NOT NULL,
    ...
    CONSTRAINT pk_history_event PRIMARY KEY (id),

    -- Not hygiene. The identity sequence guarantees distinctness only while
    -- nobody restarts it and nobody uses OVERRIDING SYSTEM VALUE, and the test
    -- rig restarts it between tests by design (D-48). This is the backstop that
    -- makes "seq is a total order" a property of the table rather than of the
    -- sequence's history. It is also the only index that can serve a
    -- cross-workspace ORDER BY seq under prope_report (A-126, ADR-0037), which
    -- is why it is not the fifth index D-55 refuses.
    CONSTRAINT uq_history_event_seq UNIQUE (seq)
);
```

**On the "fifth index" tension, which the plan should resolve out loud rather than leave to a
reviewer.** D-55 says four indexes and no fifth; a `UNIQUE` constraint *is* an index. The resolution
is that D-55 is about **query support** — four indexes for four declared read shapes — while
`uq_history_event_seq` exists to enforce a constraint. Its write cost is a right-edge B-tree insert on
a monotonically increasing bigint, which is the cheapest index maintenance PostgreSQL has, and it has
one real reader nothing else can serve. State it at the constraint; do not let it arrive silently on
the one table in Prope that only ever grows (A-121).

### Pattern 3 — The grant matrix, in the positive form (D-50)

```python
    # PH-02, and the whole of it. ADR-0025: "The application's database role
    # holds INSERT and SELECT on it and does not hold UPDATE or DELETE."
    #
    # docs/modules/property-history.lock.yml libraries_frameworks names the
    # literal `REVOKE UPDATE, DELETE ON history.history_event FROM prope_app`.
    # It is not issued: prope_app never holds either, so the statement would be a
    # no-op that reads in a diff as protection, and grant_table's own docstring
    # already argues the positive form — "both end in the same state and the
    # positive form is the one a reviewer can read" (alembic/ddl.py:105-110).
    # A declared deviation in SPELLING, not in effect. The END STATE is what the
    # security test asserts, and that assertion is true under either spelling.
    grant_table("history", "history_event", app_privileges=["SELECT", "INSERT"])

    # D-51, derived from ADR-0038 rather than chosen: "the registry table is
    # SELECT-only for prope_app ... there is no user-editable path and no API
    # that writes it, so there is no runtime event that could make the cache
    # stale." The only writer is prope_migrate; the only write is a migration;
    # ADR-0031 restarts the application after migrating.
    grant_table("history", "history_action_registry", app_privileges=["SELECT"])
```

`report_select` takes its default of `True` on both — see § *Resolving Claude's Discretion #5* for the
argument, which is ADR-0037's and is stronger here than the inheritance revision `0004` took.

**`SELECT` is required alongside `INSERT` and is not generosity.** PostgreSQL requires `SELECT`
privilege on every column a statement *references*, and the tenant policy's `USING`/`WITH CHECK`
predicate references `workspace_id`. Revision `0003` records the same reasoning for `call_body`
[VERIFIED: `alembic/versions/0003_ledger_tables.py:246-251`]. `SELECT` is also what INT-007's
`read()` needs in Phase 5.

### Pattern 4 — The four named CHECKs (D-54)

```sql
    -- Never a native enum. Pitfall 4 and
    -- test_no_native_enum_type_exists_in_the_ledger_schema are the standing rule:
    -- adding a value to a native enum cannot run inside a transaction block and
    -- removing one is impossible at any price. domain.py's StrEnums mirror the
    -- CHECK sets byte-identically; this module follows the same discipline.
    CONSTRAINT ck_history_event_actor_type_values
        CHECK (actor_type IN ('user', 'system')),

    -- The pairing rule, read exactly as the lock states it: actor_id is null
    -- ONLY in the system case, and a system actor WITH an id is permitted.
    -- Named so a security test can say which rule refused, not merely that
    -- something did (src/prope/db/metadata.py:12-16).
    CONSTRAINT ck_history_event_actor_id_present_unless_system
        CHECK (actor_id IS NOT NULL OR actor_type = 'system'),

    -- CHARACTERS, not bytes, and a CHECK, not varchar(500). ADR-0053 ships a
    -- Vietnamese-only interface, so a user-authored reason is multi-byte:
    -- octet_length('josé') is 5 where char_length('josé') is 4
    -- (postgresql.org/docs/17/functions-string.html), and a byte cap would
    -- silently be a ~170-character cap for every user the MVP has. A named CHECK
    -- is also droppable and re-addable, where a type change on an append-only
    -- table is a rewrite the application role cannot perform.
    CONSTRAINT ck_history_event_reason_length
        CHECK (reason IS NULL OR char_length(reason) <= 500),
```

`writing_module` on the registry gets the fifth, over the **five `module_id` values spelled exactly as
`docs/modules/*.lock.yml` spells them** — `prompt-registry`, `release-control`, `evaluation`,
`provider-access`, `access-control`, hyphens included. It is a bounded Prometheus label (the lock
declares it one), and a typo mis-attributes an event's writer in a metric series, which is the
quietest kind of wrong.

**No CHECK on `target_type`, anywhere.** ADR-0024 calls it a *"closed enumeration"*, and D-57 already
rejected `CHECK (action IN (…))` for duplicating the vocabulary in a second place. The same argument
applies one column over: the registry's 31 seeded rows **are** the enumeration, and `history_event`'s
`target_type` is closed by the composite foreign key. Adding a CHECK would be a fourteenth literal
list to maintain and would make adding a fourteenth target type a `DROP`/`ADD CONSTRAINT` with a
validating scan — the exact cost D-57 refused.

### Pattern 5 — The composite foreign key (D-57)

```sql
-- The registry receives the key. `action` is the PK because A-120 closes the
-- vocabulary at 31 NAMES, so one action has exactly one target type; the
-- separate UNIQUE exists ONLY because a REFERENCES clause must name a unique
-- constraint over exactly the referenced columns. It is mechanical, not
-- semantic, and saying so here is what stops it being "tidied away" as a
-- redundant duplicate of the primary key.
CONSTRAINT pk_history_action_registry PRIMARY KEY (action),
CONSTRAINT uq_history_action_registry_action UNIQUE (action, target_type)
```

```sql
-- On history_event. No ON DELETE and no ON UPDATE clause of any kind, following
-- 0003's stated rule: price_table has no DELETE grant, "so the case cannot arise,
-- and naming a behaviour for an impossible case invites someone to make it
-- possible" (alembic/versions/0003_ledger_tables.py:216-221). The registry is
-- SELECT-only for prope_app and A-120's vocabulary is closed; a cascade
-- behaviour here would be a behaviour for a case ADR-0038 says does not exist.
CONSTRAINT fk_history_event_action
    FOREIGN KEY (action, target_type)
    REFERENCES history.history_action_registry (action, target_type)
```

**The cross-tenant objection does not apply, and the reason must be stated rather than assumed.**
`test_no_foreign_key_leaves_the_ledger_schema` exists because *"referential integrity checks, such as
unique or primary key constraints and foreign key references, always bypass row security to ensure
that data integrity is maintained"* [CITED: postgresql.org/docs/17/ddl-rowsecurity.html] — so a key
from a tenant-scoped table into *another tenant-scoped table* is a covert channel: the success or
failure of the check leaks the existence of another tenant's row. **This key's target is global and
byte-identical for every workspace**, so there is nothing to infer from the check succeeding. The
`history` counterpart of that test still asserts no key leaves `history`; this one does not.

A second consequence of the same quote, in this module's favour: because RI checks bypass row
security *and* run with the referenced table's privileges, the foreign key would function even if
`prope_app` held no `SELECT` on the registry. D-51 grants it anyway, for the cache load. Worth knowing
so nobody concludes the grant is what makes the key work.

### Pattern 6 — The registry as ADR-0038's immutable mapping

```python
# src/prope/property_history/registry.py
LOAD_REGISTRY = text(
    """
    SELECT action, target_type, detail_keys, requires_reason, writing_module
    FROM   history.history_action_registry
    """
)

async def load_action_registry(session: AsyncSession) -> Mapping[str, RegisteredAction]:
    """ADR-0038's mapping: read once, immutable, no TTL and no invalidation.

    **Runs on a session with NO tenant context, and that is the assertion.** The
    registry carries no ``workspace_id`` and is exempt from the tenant policy
    (D-56, ADR-0045). If it were ever made tenant-scoped, ADR-0035's inversion
    would return ZERO rows here rather than raising — and an empty vocabulary
    makes every append fail with ``unknown_action`` while AC-6 compares two empty
    sets and stays green. That is why the test for this function opens a plain
    session rather than ``workspace_transaction``.

    Phase 4 calls this from tests. Phase 5 owns loading it once at process start
    into ``app`` and ``worker`` (D-64, D-65); nothing here is a module global,
    deliberately, so that Phase 5 introduces the global rather than inheriting a
    mutable one somebody already reached for.
    """
    rows = (await session.execute(LOAD_REGISTRY)).all()
    # ``detail_keys`` arrives from asyncpg as list[str]; frozenset is what the
    # allow-list check wants and is also what makes the mapping genuinely
    # immutable rather than immutable-at-the-top-level.
    loaded = {
        action: RegisteredAction(
            action=action,
            target_type=target_type,
            detail_keys=frozenset(detail_keys),
            requires_reason=requires_reason,
            writing_module=writing_module,
        )
        for action, target_type, detail_keys, requires_reason, writing_module in rows
    }
    # MappingProxyType is a VIEW. The dict it wraps must not outlive this frame,
    # or "immutable after load" is a claim about a name rather than about an
    # object. Returning the proxy and dropping the local reference is what makes
    # ADR-0038's "a mutable module-level dict is how a later 'just refresh it
    # here' turns into a race" unreachable rather than discouraged.
    return MappingProxyType(loaded)
```

### Pattern 7 — The three-way validator, and who performs the rollback

```python
# src/prope/property_history/writer.py
INSERT_HISTORY_EVENT = text(
    """
    INSERT INTO history.history_event (
        id, workspace_id, actor_type, actor_id, action, target_type, target_id,
        scope_prompt_id, reason, details, occurred_at
    ) VALUES (
        :id, :workspace_id, :actor_type, :actor_id, :action, :target_type, :target_id,
        :scope_prompt_id, :reason, CAST(:details AS jsonb), :occurred_at
    )
    """
)   # `seq` is ABSENT from the column list. See Pitfall 3 — naming it at all,
    # even as DEFAULT, is one keyword away from naming it with a value.

async def record_event(
    session: AsyncSession,
    event: HistoryEventDraft,
    registry: Mapping[str, RegisteredAction],
) -> str:
    """D-64's internal write path. Phase 5 wraps this as INT-006's ``append()``.

    **This function opens no transaction and closes none.** It runs on the
    session the caller opened (ADR-0023), which is the property every other
    lock's "same transaction" sentence rests on, and it is the deliberate
    opposite of call-ledger's D-19. It therefore also **never calls
    ``session.rollback()``**: ending the caller's transaction underneath them is
    the inverse of "commits or rolls back with it". The raise is the whole
    mechanism, and the caller's ``async with`` is what performs the rollback.
    """
    registered = registry.get(event.action)
    if registered is None:
        raise HistoryAppendRejected(RejectionReason.UNKNOWN_ACTION, action=event.action)

    unregistered = frozenset(event.details) - registered.detail_keys
    if unregistered:
        # A-046: the offending KEY NAME, never the offending value — which is by
        # definition the thing that failed the allow-list and therefore the least
        # safe object on hand. ``min()`` for a deterministic message, not for
        # meaning: one unregistered key is enough to refuse.
        raise HistoryAppendRejected(
            RejectionReason.UNKNOWN_DETAIL_KEY, action=event.action, detail_key=min(unregistered)
        )

    if registered.requires_reason and not (event.reason or "").strip():
        raise HistoryAppendRejected(RejectionReason.MISSING_REASON, action=event.action)

    await session.execute(INSERT_HISTORY_EVENT, {..., "details": json.dumps(event.details)})
    return event.id
```

`HistoryAppendRejected.__init__` is where `append_rejected_total.labels(reason=self.reason.value).inc()`
belongs — one site, so the label value can only ever be a `RejectionReason` member, and the counter
increments for every construction of the exception whether or not a caller catches it (which INT-006
forbids anyway).

**The three checks run in that order, and the order is a decision.** `unknown_action` first because
without a registration the other two questions have no answer; `unknown_detail_key` before
`missing_reason` because a payload leak is T-022 (HIGH) and a missing reason is a policy omission, so
the more serious refusal wins when a caller manages both. State it; a reviewer will otherwise assume
it is incidental.

### Pattern 8 — The privilege test, mirrored (D-52)

`tests/security/test_append_only_privilege.py` is the template and **both of the things it exists to
teach transfer without modification.**

```python
async def _refusal_text(app_sessionmaker, *, visible, statement, parameters) -> str:
    """VERBATIM in shape from tests/security/test_append_only_privilege.py:121-135.

    The visibility assertion runs INSIDE the transaction that will attempt the
    write. Without it this whole file passes against a table it cannot see:
    history_event is RLS-scoped, and an UPDATE that matched zero rows and an
    UPDATE the engine refused are the same observation from the test's side.
    Privilege is checked BEFORE row security, so a visible row isolates the
    privilege from the policy — which is what makes the refusal message
    ``permission denied for table history_event`` rather than a policy violation.
    """
```

The mutation check (`test_the_append_only_refusal_has_teeth`, lines 214-252) transfers the same way:
`GRANT UPDATE`, observe the refusal stop holding, `REVOKE` in a `finally`. **The `finally` is not
style** — a failure inside the granted window would otherwise leave `prope_app` holding `UPDATE` on
the audit log for every test that follows in the session.

One line changes and it matters: `price_table`'s version protects a cost figure's explicability;
this one protects the sentence the product is sold on, and it is the phase's first success criterion.

### Anti-patterns to avoid

- **`append()` opening its own transaction, or calling `rollback()`/`commit()`.** ADR-0023's whole
  decision, and call-ledger's D-19 is the shape that must *not* be copied. Asserted, not intended:
  see § *Pitfall 8*.
- **A `BEFORE INSERT` trigger for the allow-list.** ADR-0023 rejects triggers for this module **by
  name**, on the grounds they *"put the audit vocabulary in migrations rather than in a module, where
  the allow-list of ADR-0024 cannot run."* Only two of revision `0004`'s three anti-trigger reasons
  transfer — the volume argument does not, because `history_event` takes one row per state change —
  so D-62's argument is made freshly, and ADR-0023 is the decisive citation rather than `0004`.
- **Naming `seq` in the INSERT column list at all.** See § *Pitfall 3*.
- **`bigserial`, or `GENERATED BY DEFAULT AS IDENTITY`.** The second is the worse of the two: it
  behaves as `bigserial` while carrying the word "identity", which is false comfort in the one place
  the phase's second criterion lives.
- **Re-seeding the registry in a test fixture.** D-48 refuses it by name: a second provisioning path
  for the vocabulary, and it would let the suite pass against a registry the migration never wrote,
  which is the one failure AC-6 exists to catch.
- **A `GIN` index on `details`.** D-55. No query in any lock file reads a details key, and this is the
  one table in Prope that only ever grows (A-121).
- **A `workspace_id` on the registry.** § *Summary* finding 4 and § *Pitfall 7*: it makes AC-6 pass
  vacuously and forever.
- **Copying the five generic schema invariants into a `history` file.** D-49, on D-06's own grounds —
  *"the rule selecting for its own blind spot"*.

---

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| The tenant policy | A hand-written `CREATE POLICY` | `enable_tenant_rls("history", "history_event")` | `alembic/ddl.py:49-94` argues four tokens the plan must not re-derive: `ENABLE` not `FORCE`, the two-argument `current_setting`, **no cast** (Phase 1 OQ-A), and `WITH CHECK` written out |
| The grant matrix | A bespoke `GRANT`/`REVOKE` pair | `grant_table(...)` | `alembic/ddl.py:97-123`. *"every grant line is a `grant_table` call, so a reviewer greps the helper name"*. Bespoke grants make `history_event` the one table whose privileges a reviewer cannot find |
| Owning what the revision creates | `SET ROLE` by hand | `assume_migrate_role()` / `reset_role()` | `alembic/ddl.py:27-46`. Transaction-local, and forgetting `reset_role()` breaks Alembic's own write to `public.alembic_version` |
| Deterministic constraint names | A hand-rolled naming scheme | `src/prope/db/metadata.py`'s `NAMING_CONVENTION` | *"a security test can assert **which** constraint refused a write rather than only that something did"* [VERIFIED: `src/prope/db/metadata.py:12-16`] |
| Binding the tenant | `SET LOCAL app.workspace_id = '…'` | `workspace_transaction(sessionmaker, workspace_id)` | `src/prope/db/session.py:45-62`. **This module never calls it in production** — its *tests* do, standing in for callers that do not exist |
| Poison-proof id generation | A shared `new_id()` helper | `EVENT_ID_PREFIX = "hev_"` + `f"{EVENT_ID_PREFIX}{ULID()}"` | The repo already has this pattern twice [VERIFIED: `src/prope/call_ledger/api.py:103,433`; `schemas.py:418,441`]. A helper introduced as the third instance would have to refactor the first two to be worth anything. See Discretion #3 |
| A monotonic id | Your own timestamp+counter scheme | `seq`, and nothing else | A-125 / ADR-0024. ULIDs are monotonic only within one generator; `default_generator` is process-local [VERIFIED: `.venv/…/ulid/__init__.py:231`] |
| Asserting a counter | Reading `Counter._value` | `REGISTRY.get_sample_value("prope_property_history_append_rejected_total", {"reason": …})` | The repo's established pattern [VERIFIED: `tests/broker/test_publish_confirm_failures.py:56`] |
| jsonb serialisation | Passing a `dict` as a bind parameter | `CAST(:details AS jsonb)` over `json.dumps(...)` | § *Pitfall 6*. SQLAlchemy's asyncpg jsonb encoder is `lambda str_value: b"\x01" + str_value.encode()` — a `dict` produces an `AttributeError` from inside a codec |
| A schema drift guard | A new mechanism | `tests/architecture/test_schema_invariants.py`'s `len(declared) == N` shape | The repo's own precedent for pinning a count so that adding a table is a **visible edit** |

**Key insight:** almost nothing in this phase is new logic. The novel surface is *one migration* and
*three `if` statements*. Every place the plan is tempted to write DDL by hand, `alembic/ddl.py` has
the helper with the argument already written; every place it is tempted to invent an assertion shape,
`tests/security/test_append_only_privilege.py` has it. **The genuinely new decisions are exactly
three**: what the identity column does and does not refuse, where the vocabulary is enforced, and who
performs the rollback.

---

## Common Pitfalls

### Pitfall 1 — A refusal and an invisible row are the same observation, and this table is RLS-scoped

**What goes wrong:** the whole privilege test file passes against a table it cannot see.
`history_event` carries the tenant policy, so a session with no tenant context sees zero rows;
`UPDATE … WHERE id = 'hev_…'` then matches nothing and reports `rowcount = 0`, which is what a refused
statement also looks like from outside a `pytest.raises`.
**Why it happens:** the natural test writes the seed as `prope_migrate` (owner bypass), then attempts
the write as `prope_app` — and forgets that the seed is invisible to the attempting session unless
that session carries the same `workspace_id`.
**How to avoid:** copy `_refusal_text`'s shape exactly [VERIFIED:
`tests/security/test_append_only_privilege.py:121-135`] — assert the seeded row is visible **inside
the transaction that will attempt the write**. Privilege is checked before row security, so a visible
row isolates the privilege from the policy. Phase 1 wrote this into a module docstring because it
learned it the hard way; it is not new information and it is why D-52 says "structural mirror".
**Warning signs:** a green privilege test whose refusal assertion is `rowcount == 0` rather than a
raised `DBAPIError` containing `permission denied`.

### Pitfall 2 — `has_table_privilege` answers a broader question than "was this granted"

**What goes wrong:** the assertion `has_table_privilege('prope_app', 'history.history_event',
'UPDATE') is False` passes for the wrong reason, or fails for one.
**Why it happens:** the function answers *"Does user have privilege for table?"*
[CITED: postgresql.org/docs/17/functions-info.html] — which includes privileges held via `PUBLIC` and
via role membership, not only privileges granted directly. `grant_table`'s `REVOKE ALL … FROM PUBLIC`
is what keeps the answer clean [VERIFIED: `alembic/ddl.py:120`], and it must be present for the
assertion to mean what the plan thinks it means.
**How to avoid:** three things. Always pass the **schema-qualified** table name as a string, because
an unqualified name resolves through the connection's `search_path` and two roles can have different
ones. Assert `UPDATE` **and** `DELETE` separately, not `'UPDATE, DELETE'` (the multi-privilege form
answers "any of these", which is the wrong question in the direction that hides a bug). And keep the
D-52 mutation check, which is the only thing that proves the `False` is a real absence rather than a
typo'd privilege name silently returning `False` — a misspelled privilege raises, but a test asserting
`is False` against a mis-*targeted* table (`ledger.history_event`) would raise too, so the mutation
check is what proves the assertion is pointed at the right object.

### Pitfall 3 — `GENERATED ALWAYS` refuses the statement anyone would write, not every statement

**What goes wrong:** the plan treats `bigint GENERATED ALWAYS AS IDENTITY` as making a caller-supplied
`seq` impossible. It makes it *inconvenient*.
**Why it happens:** PostgreSQL documents an explicit escape hatch. *"For an identity column defined as
`GENERATED ALWAYS`, it is an error to insert an explicit value (other than `DEFAULT`) without
specifying either `OVERRIDING SYSTEM VALUE` or `OVERRIDING USER VALUE`"* [CITED:
postgresql.org/docs/17/sql-insert.html]. `OVERRIDING SYSTEM VALUE` then *"override[s] the default
sequence-generated values"*, and **the documentation attaches no privilege requirement to it** — any
role holding `INSERT` may use it. The refusal of the naive form is SQLSTATE `428C9`
(`ERRCODE_GENERATED_ALWAYS`) [VERIFIED: postgres `src/backend/utils/errcodes.txt`], and PostgreSQL's
own error message names the bypass in its `HINT`.
**How to avoid:** the move this repository has already made twice — **assert the absence rather than
assume it.** Three cheap things, all of which the plan should carry:
 1. **Omit `seq` from the INSERT column list entirely.** Not `DEFAULT`, not a comment; absent. A
    column that is not named cannot acquire a value by a one-word edit.
 2. **A source gate**, modelled on `test_no_sql_interpolation.py` (which is already a source walk, not
    a runtime claim): every `.py` under `src/prope/` is read and the literal token `OVERRIDING` is
    refused, with the same `ALLOWED`-with-a-reason escape hatch that file uses. Twelve lines, and it
    turns "nobody would do that" into a checked property.
 3. **Prove both halves at the engine**, the way revision `0004` proved the A-055 boundary: an
    `INSERT` naming `seq` is refused with `428C9`, **and** the same `INSERT` with `OVERRIDING SYSTEM
    VALUE` **succeeds**. The second assertion is the honest one. A later phase then inherits a
    recorded boundary instead of a belief about where the guarantee lives.
**Warning signs:** a plan that says "the engine refuses a caller-supplied `seq`" with no qualifier.
That sentence is what this pitfall exists to correct.

### Pitfall 4 — One `ALTER SEQUENCE` destroys the only property `seq` has

**What goes wrong:** somebody sets a cache on the identity sequence for throughput, and the total
order silently stops being one.
**Why it happens:** *"although multiple sessions are guaranteed to allocate distinct sequence values,
the values might be generated out of sequence when all the sessions are considered. For example, with
a cache setting of 10, session A might reserve values 1..10 and return `nextval`=1, then session B
might reserve values 11..20 and return `nextval`=11 before session A has generated `nextval`=2. Thus,
with a cache setting of one it is safe to assume that `nextval` values are generated sequentially"*
[CITED: postgresql.org/docs/17/sql-createsequence.html]. The default **is** 1 — *"The minimum value is
1 (only one value can be generated at a time, i.e., no cache), and this is also the default"* — so the
correct behaviour is free, and it is one `ALTER SEQUENCE … CACHE 20` away from being wrong with no
test noticing.
**How to avoid:** write `(CACHE 1)` explicitly in the `GENERATED ALWAYS AS IDENTITY` sequence options
so the value is a stated intention rather than an inherited default, and add one line to the schema
invariants: `SELECT seqcache FROM pg_sequence WHERE seqrelid = pg_get_serial_sequence('history.history_event','seq')::regclass`
must be `1`. `pg_get_serial_sequence` works for identity columns — *"If the column is an identity
column, the associated sequence is the sequence internally created for that column"* [CITED:
postgresql.org/docs/17/functions-info.html] — which is what makes the assertion writable without
knowing the generated sequence's name.

### Pitfall 5 — Monotonic is not gapless, and assignment order is not commit order

**What goes wrong:** two different wrong inferences, one of which is Phase 5's problem and is invisible
in a single-threaded test.
**Why it happens:** *"Because `nextval` and `setval` calls are never rolled back, sequence objects
cannot be used if 'gapless' assignment of sequence numbers is needed"* [CITED:
postgresql.org/docs/17/sql-createsequence.html]. So a rolled-back append consumes a value and never
returns it — and PH-05's own success criterion *guarantees* rolled-back appends, which means **gaps in
`history_event.seq` are a normal product of the phase's third requirement.** Separately, two concurrent
transactions can take 5 and 6 and commit 6 first, so a reader between the two commits sees 6 with no 5.
**How to avoid:** state both, at the column, in the words the plan will be held to. *Nothing may infer
"events were deleted" from a gap* — which matters more here than anywhere else in Prope, because A-121
and ADR-0025 make "an event is missing" the most serious accusation available about this table, and
AC-10 is a Phase 6 test named *"events are never deleted"*. *And nothing may treat `seq` as a
watermark across transactions.* Inside one transaction — the entire case PH-04 and AC-4 are about — the
order is exact. Across transactions it is not, and the hazard lands on **Phase 5's cursor
pagination**: a "what is new since `seq > N`" poll will permanently skip a row that committed after a
higher `seq` was already returned. INT-007 paginates `seq DESC`, which is the safer direction, so this
is a warning to carry rather than a defect to fix here — but naming it now is what stops Phase 5
discovering it in a flaky test.

### Pitfall 6 — A `dict` bound to a `jsonb` parameter fails inside a codec, not at the call site

**What goes wrong:** `session.execute(INSERT_HISTORY_EVENT, {..., "details": {"role": "admin"}})`
raises `AttributeError: 'dict' object has no attribute 'encode'` from somewhere in SQLAlchemy's
asyncpg adapter, which reads as a driver bug rather than as a type error in the call.
**Why it happens:** by default *"asyncpg does not decode the `json` and `jsonb` types"*, so SQLAlchemy's
dialect registers its own binary codecs on every connection — and the `jsonb` encoder is
`def _jsonb_encoder(str_value): return b"\x01" + str_value.encode()` [VERIFIED:
`.venv/Lib/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:1220-1238`, `on_connect` at
1273-1274]. It expects a **`str`**. A raw `text()` statement carries no SQLAlchemy type information, so
whatever Python object is bound goes straight to that encoder.
**How to avoid:** write the statement as `CAST(:details AS jsonb)` and bind `json.dumps(details)`.
Two properties follow. The cast makes the parameter's inferred type `text`, so binding a `dict` by
mistake produces a clear `expected str, got dict` from asyncpg instead of an `AttributeError` from a
codec. And serialisation becomes this module's decision rather than a dialect's, which matters because
`details` is the one column A-124 exists to police. Reading is unaffected: the registered decoder
`json.loads`es on the way out, so a test can compare a returned `dict` directly.
**The alternative, and why it is not the recommendation:** declaring the column in `models.py` as
`JSONB` and using a Core `insert()` lets the type do the serialisation. It works, and it moves the
statement **outside `test_no_sql_interpolation.py`'s coverage**, which walks `text()` calls only. On
this module, staying inside the gate is worth more than the convenience.

### Pitfall 7 — A tenant-scoped registry makes AC-6 green forever

**What goes wrong:** the registry gets a `workspace_id` "for consistency", ADR-0045's coverage walk
goes green, and `registered_actions()` returns nothing to its only consumer.
**Why it happens:** ADR-0035's inversion is a feature everywhere in Prope and a trap on exactly this
table. INT-008's consumer is *"the route-table test in CI"* [VERIFIED:
`docs/architecture/interfaces.md:303`] — a test with no tenant context — and a policy predicate
comparing against a setting that was never set yields **zero rows, not an error** by design. AC-6 then
compares an empty registry against an empty extraction and passes.
**How to avoid:** D-56, plus the assertion the exemption does not currently buy. The implemented
coverage walk `continue`s past a `GLOBAL_TABLES` entry with no check at all
[VERIFIED: `tests/architecture/test_tenant_coverage.py:120-121`], which is *weaker* than ADR-0045's own
pseudocode (`assert rls_state_matches_declaration(table)`). Write the positive test instead: **load
the registry on a plain session with no tenant set and assert 31 rows.** That one assertion proves the
table is global, proves the seed landed, and is the exact read ADR-0038's process-start cache performs.
**Warning signs:** any test of the vocabulary that opens `workspace_transaction`. If the registry is
correct, it does not need one; if it needs one, the registry is wrong.

### Pitfall 8 — "The caller's transaction rolls back with no partial state" is not testable by looking at `history_event`

**What goes wrong:** the PH-05 test asserts `SELECT count(*) FROM history.history_event` is 0 after a
refused append, goes green, and proves nothing. That assertion passes identically against a module
that opened and rolled back **its own** transaction — which is call-ledger's D-19 shape and the one
arrangement ADR-0023 forbids, because it silently breaks five other lock files' "same transaction"
sentence.
**Why it happens:** the criterion names *the caller's* transaction, and the caller does not exist yet.
Nothing in the phase forces the test to model one.
**How to avoid:** make the test *be* the caller, and give it something to lose.

```python
async def test_an_unregistered_detail_key_rolls_the_callers_transaction_back(
    app_sessionmaker, migrate_engine
):
    before = rejected_total("unknown_detail_key")

    with pytest.raises(HistoryAppendRejected) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            # The stand-in state change. Any row the caller writes in the same
            # transaction will do; a second, VALID history event is the honest
            # choice, because it is the only table this phase may write to and
            # because it makes the assertion "no partial state" mean something
            # this module can actually observe.
            await record_event(session, valid_event(), registry)
            await record_event(session, event_with_an_unregistered_key(), registry)

    assert excinfo.value.reason is RejectionReason.UNKNOWN_DETAIL_KEY

    # As the OWNER, outside RLS: BOTH rows are gone, including the one that
    # succeeded. That is the half a count-of-zero on the failing row cannot see,
    # and it is the half that proves record_event did not own the transaction.
    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 0

    assert rejected_total("unknown_detail_key") == before + 1
```

**And the mirror assertion, which costs one more test and buys the other direction:** write a *valid*
event on a caller-opened transaction, roll that transaction back deliberately, and assert the row is
absent. If `record_event` had opened and committed its own transaction, the row would survive. That is
the first assertion of ADR-0023's central property, and D-64 explicitly says this phase gets it. Phase
5 owns the registered-signature contract test; this is the cheap version that stops the property being
lost in between.

### Pitfall 9 — The counter must survive the rollback, and it does — for a reason worth writing down

**What goes wrong:** somebody "fixes" the counter by moving the increment into the caller's `except`,
or worries that a rolled-back transaction un-counts it.
**Why it happens:** every other durable fact in this phase is transactional, so the counter looks like
it should be too.
**How to avoid:** state it at the increment site. A `prometheus_client` `Counter` is **process state,
not database state** — the rollback cannot reach it, which is precisely why it is the right instrument
for a failure whose entire signature is that the transaction did not happen. Increment inside
`HistoryAppendRejected.__init__` (§ *Pattern 7*), so it fires on construction, before the raise, and
independently of whether any caller catches it — which INT-006 forbids, and the metric is how a
violation of that prohibition becomes visible at all. The lock's alert makes every increment a page
[VERIFIED: `docs/modules/property-history.lock.yml:346-349`], so an increment that could be lost to a
rollback would be an alert that fires only when the failure was harmless.

### Pitfall 10 — The truncate fixture eats the seed, and the symptom points two directories away

**What goes wrong:** the fixture's filter is widened to `('ledger', 'history')`, the 31 seeded rows are
truncated after the first test, and **every test after the first fails with `unknown_action`** — an
error that points at the validator, at the migration's seed, or at the registry loader, and not at a
fixture in `conftest.py`.
**Why it happens:** `TRUNCATE … RESTART IDENTITY CASCADE` is issued over every discovered table
[VERIFIED: `tests/conftest.py:170-179`], and the discovery query is a literal
`WHERE schemaname = 'ledger'` [VERIFIED: `tests/conftest.py:95-98`]. `CASCADE` compounds it:
*"Automatically truncate all tables that have foreign-key references to any of the named tables"*
[CITED: postgresql.org/docs/17/sql-truncate.html], so naming the registry drags `history_event` in as
well.
**How to avoid:** D-48 — widen the filter and **exclude `history_action_registry` by name, with a
comment saying why**. The reverse direction is safe and worth knowing: `history_event` has no inbound
foreign key, so truncating it alone needs no `CASCADE` and does not reach the registry. Two
consequences the plan should carry: `RESTART IDENTITY` resets the `seq` sequence between tests, so
per-test `seq` values are small and predictable and an ordering assertion **may** compare absolute
values — but should not, because a test that asserts `seq == 1` breaks the moment two tests share a
transaction. Assert the *relation* (`approval.seq < release.seq`), not the values.
**Warning signs:** a passing first test in a file and a failing second, in every file.

### Pitfall 11 — A foreign key onto 31 rows makes those 31 rows the hottest rows in the database

**What goes wrong:** D-57's foreign key means **every** `history_event` insert takes a row lock on one
of 31 registry rows. Under concurrency those become multixact-generating hot rows.
**Why it happens:** *"During the operation of the `INSERT` statement, the transaction that is doing the
`INSERT` will take a `FOR KEY SHARE` lock on that record"*, and *"if more than one transaction at a
time has a lock on a single record, the MultiXact system handles this"* — observable as *"lots of
sessions suddenly waiting on various `MultiXact*` lightweight locks"*
[CITED: thebuild.com/blog/a-foreign-key-pathology-to-avoid/, Christophe Pettus].
**Why it is nevertheless the right call here — an agent judgement, arithmetic not measurement.**
`FOR KEY SHARE` locks are mutually compatible, so they never block each other; the cost is multixact
creation, and multixacts are created only when **two or more transactions hold a lock on the same row
at the same instant**. That is a function of concurrency, not of throughput. ADR-0033 runs one `app`
and one `worker` on one VM; the load target is 200 appends/sec inside real transactions
[VERIFIED: `docs/modules/property-history.lock.yml:556-559`]; and the appends spread over 31 rows with
transaction lifetimes measured in milliseconds. The pathology is a real property of the design and is
not expected to bite at pilot scale.
**How to avoid / what to do if it does:** name it at the constraint, and record the escape hatch
honestly — **dropping the foreign key is cheap at any time; adding it back after the pilot is a
validating scan over a never-shrinking audit table.** D-57's reversibility note says exactly this and
this pitfall is the mechanism behind it. Do not pre-emptively tune `autovacuum_multixact_freeze_max_age`;
the registry is 31 rows and vacuums instantly, and a tuning knob turned for a problem nobody has is a
second runbook A-012 forbids.

### Pitfall 12 — Two Phase-1 files name `ledger` literally, and one of the two edits is three words long

**What goes wrong:** the plan updates `EXPECTED_ABSENT_SCHEMAS`, the suite is still red, and the
failure is in a test whose name says nothing about schemas being absent.
**Why it happens:** `test_declared_schemas_that_do_not_exist_are_reported_not_skipped` carries **two**
assertions. The documented one is the constant. The second is
`assert tuple(existing) == ("ledger",)` — the last line of the same test [VERIFIED:
`tests/architecture/test_tenant_coverage.py:151`] — and it becomes `("history", "ledger")`,
alphabetically, because `LIST_EXISTING_SCHEMAS` carries `ORDER BY nspname` [VERIFIED: same file, line
68]. **This is an agent judgement from reading the file, not a detector result.**
**How to avoid:** D-47 names both. Also correct `.planning/STATE.md`'s Phase 01 accumulated-context
line, which says *"Phase 7 (access) is the first phase that must shrink it"* — that was true when only
`ledger` was planned near-term and it is not true now. The plan should say so where a reader of STATE
would otherwise trust it; the file itself is the orchestrator's to update at phase close
(ORCHESTRATION §9.6).

### Pitfall 13 — `test_every_timestamp_column_carries_a_time_zone` has a guard that a parameterisation can trip

**What goes wrong:** D-49's parameterisation is applied and one of the five generic tests fails on a
schema that is perfectly correct.
**Why it happens:** that test asserts `columns, "no _at / _from columns found — the query, not the
schema, is wrong"` [VERIFIED: `tests/architecture/test_schema_invariants.py:152`] — a
did-the-walk-find-anything guard, exactly like `test_the_walk_actually_found_statements_to_check`. For
`history` it passes, because `occurred_at` matches `LIKE '%\_at'`. **But the same guard makes the
parameterisation fragile for every later schema**, and Phase 7's `access` schema will hit it if a
future module ever has no `_at` column at all.
**How to avoid:** parameterise the five, keep the guard, and note in the file that the guard is
per-schema and intentional. The three ledger-specific tests — the six money columns, the
`created_at`/`written_at` default split, and `len(declared) == 6` — stay scoped and untouched (D-49),
and `len(declared) == 6` survives without an edit because it filters `models.metadata.tables` on
`table.schema == SCHEMA` [VERIFIED: same file, line 221], so declaring two `history` tables on the same
shared `MetaData` does not change its count. **Two of the five carry `ledger` in their function names
and will read wrong once they run against `history`; renaming them is part of the edit, not a
follow-up.**

---

## Code Examples

### The 31-row seed, and why it is written in the migration rather than in `src/`

```python
# alembic/versions/000N_history_schema_and_vocabulary.py
#
# D-59/D-60. One statement, thirty-one rows, in the same revision as the tables.
# ADR-0038's entire safety argument is a DEPLOY ORDERING — "the row exists, then
# the code that names it starts" — and that ordering only exists if the seed is a
# migration. D-57's foreign key adds a second, independent reason: the registry
# must be non-empty before the first event can be written, so a startup seed
# would make the first append after a fresh deploy a race against the seeder.
#
# Written HERE and not in src/: tests/architecture/test_no_sql_interpolation.py
# rglobs src/prope/ and requires every text() argument to be a plain string
# constant with an empty ALLOWED list. A seed assembled by joining thirty-one
# names into one statement would need an exception; assembled in a migration it
# needs none, because the gate does not reach alembic/ and the values here are
# module constants rather than runtime input.
SEED_ACTION_REGISTRY = """
INSERT INTO history.history_action_registry
    (action, target_type, detail_keys, requires_reason, writing_module)
VALUES
    -- prompt-registry (5). OQ-028: `retired` carries no target type at all and
    -- `owner_changed` / `access_level_changed` name a FIELD rather than a
    -- subject, so three of these do not satisfy A-120's own naming rule. Seeded
    -- as the lock file literally spells them, because AC-6 is an asserted
    -- equality and A-120 is prose.
    ('property_created',              'property',        '{}',                      false, 'prompt-registry'),
    ...
    -- release-control (8). Three of these carry requires_reason, and this is the
    -- one registry column fully determined by the specs: the same three names
    -- appear in property-history.lock.yml, release-control.lock.yml and INT-006.
    ('revision_released',             'revision',
        '{version_id,previous_version_id,break_glass}', false, 'release-control'),
    ('revision_changes_requested',    'revision',        '{}',                      true,  'release-control'),
    ('revision_break_glass_released', 'revision',        '{}',                      true,  'release-control'),
    ('release_withdrawn',             'release',         '{}',                      true,  'release-control'),
    ...
    -- access-control (10). ADR-0054's 31st name, and the only one whose
    -- detail_keys are empty AND whose requires_reason is false despite being
    -- rare, consequential and admin-only — both deliberately, because every
    -- candidate key and every free-text reason available to it is a fact about
    -- the person the operation exists to erase.
    ('role_assigned',                 'role',            '{role,grantee_user_id}',  false, 'access-control'),
    ('user_tombstoned',               'user',            '{}',                      false, 'access-control')
"""
```

**The `detail_keys` position is the strictest one available and that is deliberate.** Three of the
thirty-one actions have declared keys; the other twenty-eight belong to modules that will not exist for
another six to eighteen phases. Seeding an empty array means **any key at all on those actions is
refused, loudly**, which is A-124's friction landing exactly where A-124 says it should. A key invented
now is a guess the real writer discovers is wrong at the moment its transaction fails.

### The derivation, verified against the source AC-6 names

D-60's table is correct. Verified this session by reading the `outputs` block of each of the five
writing modules' lock files — **not** ADR-0024's Context table, which lists 30 and omits
`user_tombstoned`:

| Writer | Count | `outputs` block |
|---|---|---|
| prompt-registry | 5 | `docs/modules/prompt-registry.lock.yml:87-93` |
| release-control | 8 | `docs/modules/release-control.lock.yml:97-118` |
| evaluation | 4 | `docs/modules/evaluation.lock.yml:94-98` |
| provider-access | 4 | `docs/modules/provider-access.lock.yml:91-95` |
| access-control | 10 | `docs/modules/access-control.lock.yml:107-122` |
| **Union** | **31** | no adjustment, no hand-added name |

`user_tombstoned` is already inside `access-control.lock.yml` `outputs`, added 2026-08-09 by ADR-0054,
so the union is 31 without anything being added by hand. **The derivation is reproducible from the
five files and requires no judgement**; `target_type` and `detail_keys` are a different matter and are
`OQ-029`.

### Asserting the D-62 boundary (the pair revision `0004` owes and this phase repeats)

```python
async def test_a_hand_written_insert_bypasses_the_python_validations(migrate_engine):
    """The absence of a database backstop, ASSERTED rather than assumed.

    D-62 puts `requires_reason` and the details allow-list in Python because
    neither can be a CHECK (a CHECK cannot reach another table) and ADR-0023
    rejects triggers for this module by name. So the guarantee lives in one
    language and not in the engine — and this test is what makes a later phase
    inherit a RECORDED BOUNDARY rather than a belief about where it lives.

    Same move as tests/security/test_eval_no_body_boundary.py, which proves both
    halves of A-055 for exactly the same reason.
    """
    async with migrate_engine.begin() as connection:
        # A registered action/target pair, so the FOREIGN KEY is satisfied — the
        # half that IS in the engine. An unregistered details key and no reason
        # on an action that requires one — the half that is not.
        await connection.execute(INSERT_BREAK_GLASS_WITH_A_STRAY_KEY_AND_NO_REASON)
        assert (await connection.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 1

async def test_an_unregistered_action_is_refused_by_the_engine(migrate_engine):
    """And the half that IS in the engine, proven the same way (D-57)."""
    with pytest.raises(IntegrityError) as excinfo:
        async with migrate_engine.begin() as connection:
            await connection.execute(INSERT_WITH_AN_UNREGISTERED_ACTION)
    assert "fk_history_event_action" in str(excinfo.value)
```

The second test is the one that makes D-57 worth its cost: it proves an unregistered action cannot
enter the table **through the repair-script path ADR-0025 names as the realistic threat**, as
`prope_migrate`, with the module not involved at all.

---

## Resolving Claude's Discretion

### 1. The `LOGGABLE_FIELDS` collision on `reason` — RECOMMENDED

**Recommendation: `reason` keeps call-ledger's meaning and this module never binds it. The rejection's
reason is logged under a different name.**

`LOGGABLE_FIELDS` today is `{event, call_id, workspace_id, reason, queue, delivery_tag, group_size,
window_size, job}` [VERIFIED: `src/prope/observability.py:49-67`]. For call-ledger, `reason` is a
closed-vocabulary token — `unroutable | nacked | timeout`, `envelope_invalid`, `write_refused`,
`transient`, `permanent` [VERIFIED: `drain.py:252,318,396,411`; `enqueue.py`]. For property-history the
lock says the opposite in as many words: *"Never logged: the `details` payload or the `reason` string
… `reason` is user-authored free text that may quote whatever the author was looking at"* [VERIFIED:
`docs/modules/property-history.lock.yml:341-343`].

One flat set keyed on field name cannot hold both meanings, and Phase 2's own note closes off the easy
answer: *"an allow-list with a field outside it is an allow-list somebody has already stopped
believing"*. **So do not fork the set, do not add a per-module dimension, and do not subtract.
Rename this module's side.** The three things property-history actually wants to log are
`rejection_reason` (a `RejectionReason` member — a closed set of three), `detail_key` (the offending
key name, which the lock's `log_fields` names explicitly and which is a *name*, never a value), and
`event_id` (*"the event's id is logged; its content is not"*). Plus the lock's base additions:
`action`, `target_type`, `target_id`, `scope_prompt_id`, `actor_id`, `writing_module`.

**The user-authored `reason` then has no name in the allow-list at all**, which is exactly the property
the lock demands, expressed as an absence rather than as a subtraction rule somebody has to remember.
The set stays flat, stays positive, and stays in one place.

**Two costs, both to be stated in the plan rather than absorbed.** First, `LOGGABLE_FIELDS` grows from
9 entries to 17 and now spans two modules, inside a file whose docstring opens *"The Phase 2 counters,
and only those"* [VERIFIED: `src/prope/observability.py:1`]. That sentence is about the **counters** —
`LOGGABLE_FIELDS` is described in the same docstring as project-wide — but a reader will trip on it.
**Edit the scope sentence in the same change.** That is this phase's **second cross-phase edit**,
beside D-49's, and both belong in the plan's `files_modified` rather than in a diff.

Second, the optional half. The allow-list is currently a convention with no gate: nothing checks that a
log call's keywords are in it. An AST walk over `src/prope/` requiring every keyword argument to a
structlog call to be a member — modelled exactly on `test_no_sql_interpolation.py`, which is already a
source walk with an `ALLOWED`-with-a-reason hatch — would make A-046 the same class of enforced
property that WR-06 became in Phase 2. **The plan must know what it costs before adopting it: the gate
goes red on arrival**, because `src/prope/call_ledger/schemas.py:442` logs
`request_id=request_id` and `request_id` is not in `LOGGABLE_FIELDS` — in a function whose docstring
carefully argues A-046 four lines above [VERIFIED: `schemas.py:434-442`]. The fix is one word
(`request_id` is ADR-0003's error-envelope correlation id: an identifier, plainly loggable, plainly not
a body), but it is a third cross-phase edit. **Recommendation: adopt the gate, and record the
`request_id` finding as what it is — a Phase 2 allow-list omission this phase found.** If the planner
declines the gate, the omission still exists and belongs in `.planning/WINDOWS.md` as a Broken Window
rather than nowhere.

### 2. Where the rejection-reason `StrEnum` lives, and how the byte-identity is kept — RECOMMENDED

**Recommendation: the enum and the exception in `domain.py`; the counter in the module's own
`observability.py`; the byte-identity asserted by a test, not by proximity.**

Three arguments, in order of strength. **Direction of dependency**: the exception type carries the
reason, so if the enum lived beside the counter then `domain.py` would import `observability.py` — the
module's vocabulary depending on its metrics, which is backwards and is not what
`src/prope/call_ledger/` does. **Precedent**: `call_ledger/domain.py` is the vocabulary file and holds
four `StrEnum`s [VERIFIED: `src/prope/call_ledger/domain.py:36-81`]; a fifth vocabulary in a different
kind of file would be the second pattern. **Structural identity beats asserted identity**: increment
as `append_rejected_total.labels(reason=self.reason.value).inc()` inside
`HistoryAppendRejected.__init__`, and the label value **cannot** be anything but an enum member. There
is then nothing to keep in sync at the call sites.

What still needs a test is the *cardinality*, and proximity cannot supply it. `domain.py`'s precedent
works because each `StrEnum` there has a live database `CHECK` set that an existing test reads back;
this enum has no database counterpart, so proximity has nothing to be checked against. **Pin it the way
this repo already pins a count**: `assert set(RejectionReason) == {"unknown_action",
"unknown_detail_key", "missing_reason"}`, the same shape as `len(declared) == 6` [VERIFIED:
`tests/architecture/test_schema_invariants.py:226`], with the comment D-63 supplies — *a fourth reason
is a lock-file change, not a new enum member*. The lock's `PropertyHistoryAppendRejected` alert makes
every increment a page, so a silently added fourth label value is a new page nobody declared.

### 3. The `id` generation site — RECOMMENDED

**Recommendation: `EVENT_ID_PREFIX = "hev_"` as a module constant plus an inline
`f"{EVENT_ID_PREFIX}{ULID()}"`. No shared helper in this phase.**

The repo already has this pattern **twice**, both written in Phase 2:
`PRICE_ROW_ID_PREFIX = "prc_"` / `f"{PRICE_ROW_ID_PREFIX}{ULID()}"` [VERIFIED:
`src/prope/call_ledger/api.py:103,433`] and `REQUEST_ID_PREFIX = "req_"` /
`f"{REQUEST_ID_PREFIX}{ULID()}"` [VERIFIED: `src/prope/call_ledger/schemas.py:418,441`]. A shared
`new_id()` helper introduced as the **third** instance would have to refactor the first two to be worth
anything, and refactoring `api.py` and `schemas.py` is a cross-phase edit this phase has no other
reason to make.

The counter-argument — seven more prefixes are coming from Phase 7 onward — is real and is answered by
noticing what is actually shared. **The shared dependency already exists and it is `python-ulid`**; a
Prope-level wrapper adds an indirection over a one-line f-string and buys nothing until the *format*
needs to vary, which A-045 and ADR-0003 fix. Record the trigger in `deferred-items.md` with a named
owner: **Phase 7**, which adds four prefixes at once and is where the sixth call site appears — at
which point a helper is obviously right rather than speculative. And record the one thing it must never
become: a prefix registry mapping types to prefixes, which is the auto-discovery shape D-13 refuses.

### 4. Whether `scope_prompt_id` gets a constraint in this phase — RECOMMENDED

**Recommendation: no constraint of any kind, and say why in the migration rather than leaving the
absence to be read as an oversight.**

Three grounds. A `CHECK` **cannot** express it — the rule is "prompt-scoped actions must carry a
scope", the registry is what knows which actions are prompt-scoped, and a CHECK cannot reach another
table. That is D-62's own argument, and a trigger is refused by ADR-0023 by name. Second, **the lock
routes this deliberately to a metric rather than to a refusal**:
`prope_property_history_null_scope_prompt_total`, alert `PropertyHistoryScopeMissing`, severity
**ticket**, with the note *"The write succeeded and an Activity feed is quietly incomplete. This is the
only silent-but-detectable failure here"* [VERIFIED:
`docs/modules/property-history.lock.yml:336-338, 350-352, 437-444`]. Converting it to a refusal would
fail a user's state change over a display concern — inverting the lock's own severity, and doing so on
the one column whose failure mode the lock calls out as *deliberately* non-fatal. Third, **the metric
is Phase 6's**, and the six other metrics with it.

**What this phase owes Phase 6 instead** is the derivation, so the check is data-driven when it
arrives. CONTEXT fixes the registry at five columns, so a sixth `prompt_scoped boolean` is inventing
schema the spec did not declare. The set is therefore derived from `target_type`, and here it is:
**seven of the thirteen values are prompt-scoped** — `property`, `revision`, `release`, `review_task`,
`eval_suite`, `eval_run`, `prompt_grant`. The remaining six are not — `provider_config`, `workspace`,
`member`, `role`, `api_key`, `user`. **A-119 says the prompt-scoped set names six**; the derivation
gives seven, and that discrepancy is already inside `OQ-029`.

### 5. `prope_report`'s read grants on both tables — RECOMMENDED

**Recommendation: take `grant_table`'s default `report_select=True` on both — and make the argument
rather than inherit it, because on this table the argument is unusually strong.**

`grant_table` defaults `report_select: bool = True` and every Phase 1 table took the default; revision
`0004` also took it and wrote a short reason [VERIFIED: `alembic/ddl.py:97-123`;
`alembic/versions/0004_workspace_retention.py:164-168`]. The temptation here is to treat that as
precedent and move on. Do not — **ADR-0037 was written about this exact table**, and its reasoning is
the reason to grant rather than a reason to shrug:

> *"This is a property-history-shaped problem specifically. In every other module a stray privileged
> session is a risk; here it is the module whose entire product claim is that the record cannot be
> quietly rewritten."* … *"with one privileged role used for two purposes, no session record
> distinguishes a person reading a metric from a person editing a row, and the second is exactly what a
> reader of the trail would want to know about."* [VERIFIED:
> `docs/adr/0037-a-third-role-reads-across-workspaces.md:31-33, 55-59`]

A-126's cross-workspace Success SQL — median review turnaround, `revision_submitted` →
`revision_approved | revision_changes_requested` — reads `history_event` across workspaces. **Withhold
`SELECT` from `prope_report` and that query goes back to `prope_migrate`, which is the only role that
can `DELETE` a history row and is the precise outcome ADR-0037 exists to prevent.** Granting is not
the lenient option here; it is the one that keeps ADR-0025's distinction intact.

State the counter-consideration honestly rather than omitting it: `history_event.reason` is
user-authored free text and `details` is a payload, so `prope_report` becomes a full-read credential
over the module's two most content-bearing columns. ADR-0037 already declares that posture
(*"`SELECT` only … for humans running ad-hoc and scheduled reads across workspaces"*), and the control
on what those columns may contain is A-124's allow-list plus A-020's line, not a grant.

### 6. How many OQ files the vocabulary findings become — RESOLVED, AND ONE ADDITION

**Finding: all three files already exist on disk.** `docs/brainstorm/open_questions/OQ-027.md`,
`OQ-028.md` and `OQ-029.md` were created during the CONTEXT pass, 2026-08-10 [VERIFIED: `ls
docs/brainstorm/open_questions/` returns `OQ-001` … `OQ-021`, `OQ-027`, `OQ-028`, `OQ-029`; frontmatter
read this session]. **The planner does not raise them — it cites them**, and it should not re-raise
under a new id. `OQ-022`…`OQ-026` belong to Phase 3's allocation and are not this phase's to touch.
`OQ-030` and `OQ-031` remain **unconsumed** and are available.

**One addition the planner should make, and it is not cosmetic.** OQ-027 lists six files where the
count is stale and does **not** list `docs/adr/0045-every-table-is-tenant-scoped-unless-declared-global.md`,
whose `GLOBAL_TABLES` block reads:

```python
    'history.history_action_registry': "30 seeded actions, immutable, ADR-0024 and ADR-0038",
```
[VERIFIED: `docs/adr/0045-…:46-51`]

That is a **seventh** site, and it is the only one whose text this phase is about to copy into a
security-relevant file in `tests/`. Append the row to OQ-027's table and the file to its `blocks:`
list. OQ-027 is this phase's own artifact, so amending it is bookkeeping within the phase's own
allocation rather than an edit to somebody else's spec — but if the planner reads the `docs/`
read-only rule strictly, `OQ-030` is available and the conflict is identical in kind.

### 7. The exact `GLOBAL_TABLES` reason string — RECOMMENDED

ADR-0045's own entries are one clause each and the file's rule is that the reason must be *"a sentence
somebody signed"* and *"a sentence a reviewer can disagree with"*. Copying the ADR's string verbatim
would import the stale count into the code. **Recommendation — state the reason and the failure mode,
and let the count live in the migration where OQ-027 can move it:**

```python
GLOBAL_TABLES: dict[str, str] = {
    "history.history_action_registry": (
        "the action vocabulary is closed install-wide, not per workspace (A-120, ADR-0024); "
        "tenant-scoping it would return zero rows to registered_actions()'s only consumer — a CI "
        "test with no tenant context — and AC-6 would compare two empty sets and pass forever. "
        "Seeded by migration, SELECT-only for prope_app, never written at runtime (ADR-0038). "
        "Declared global by ADR-0045, which names this table."
    ),
}
```

Three properties it has and the alternatives do not: it names the **rule** (install-wide closure), the
**failure mode of the alternative** (a green test asserting nothing), and the **authority** — and it
contains no number, so OQ-027's resolution does not have to reach into a security file. Put the longer
argument in the migration docstring, where revision `0004` puts its equivalent.

### 8. Fixture versus re-derivation for Phase 5's AC-6 — RECOMMENDED, WITH TWO INHERITED PROBLEMS

**Recommendation: no fixture. Phase 5 re-derives from the five lock files.** A committed derivation
table would be a seventh copy of a list AC-6 exists to stop copying, and the failure mode is the worst
available: the fixture and the migration agree, the lock files have drifted, and the test is green.

But re-derivation is harder than it reads, and this phase is where the two obstacles should be named so
Phase 5 does not meet them cold.

**(a) The five `outputs[].what` values are prose paragraphs, not lists.** Release-control's is a
five-sentence paragraph that contains the eight action names *and* the tokens `version_id`,
`previous_version_id`, `break_glass`, `set_revision_status`, `review_task_closed`, `A-120`, `ADR-0024`
[VERIFIED: `docs/modules/release-control.lock.yml:97-118`]. A permissive `[a-z_]+_[a-z]+` regex over
that string extracts more than eight names and would make AC-6's "no extras" half fail for the wrong
reason — or, if the test intersects rather than compares, pass while asserting nothing.
**Recommended shape for Phase 5:** extract per module, then assert **both** directions **and** the
per-module count, using the counts the specs themselves declare — `property-history.lock.yml`'s
`inputs` block states *"5 events"*, *"8 events"*, *"4 events"*, *"4 events"*, *"10 events"* in prose
beside each list [VERIFIED: `docs/modules/property-history.lock.yml:59-102`]. A lenient regex then
cannot pass, because it changes a count.

**(b) `PyYAML` is not a declared dependency of this project.** It resolves only as a transitive of
`uvicorn[standard]` [VERIFIED: `uv.lock`, `uvicorn` `[package.optional-dependencies].standard`]. So an
`import yaml` in a Phase 5 test **passes today by accident** and breaks the day somebody narrows the
uvicorn extra — a failure that would read as an unrelated CI break in an unrelated phase. Phase 5 must
either add `pyyaml` to the dev group explicitly with its reason, or read the lock files as text.
Recorded here because this phase owns the handoff and nothing else names it.

### 9. Test file placement against the lock's `test_ref` paths — RECOMMENDED

| Criterion | Recommended file | Against the lock's `test_ref` |
|---|---|---|
| AC-2 / **PH-02** | `tests/security/test_history_is_append_only_by_privilege.py` | **Matches exactly** |
| AC-4 / **PH-04** | `tests/integration/test_same_transaction_events_have_a_stable_order.py` | **Matches exactly** |
| PH-04, the identity half | `tests/security/test_history_seq_cannot_be_supplied.py` | New. The lock names no test for it; § *Pitfall 3* is why it exists |
| AC-5 / **PH-05**, validator half | `tests/unit/test_details_allow_list.py` | New. Pure Python, no database |
| AC-5 / **PH-05**, transaction half | `tests/integration/test_unregistered_detail_key_fails_the_transaction.py` | **DEVIATES.** The lock says `tests/unit/test_unregistered_detail_key_fails_the_transaction` |
| D-62's boundary | `tests/security/test_history_validation_has_no_database_backstop.py` | New. Modelled on `tests/security/test_eval_no_body_boundary.py` |
| D-56 | `tests/integration/test_action_registry_loads_without_a_tenant.py` | New, and § *Pitfall 7* argues it is the phase's single most valuable new test |

**On the one deviation.** "The caller's transaction rolls back with no partial state" is not observable
without a database, and in this repository `tests/unit/` means pure Python — `test_cost_arithmetic`,
`test_period_month`, `test_supervisor`, `test_missing_price_is_unpriced_not_zero`. The lock uses
"unit" loosely throughout: its own `test_plan.unit` names *"ordering by `seq` across identical
timestamps"*, which needs an engine too. **Recommendation: record the deviation in the plan and in
`deferred-items.md`; do not raise an OQ.** A `test_ref` names a file, not a guarantee, and both halves
of AC-5 are asserted — which is more than the single named file would have delivered. `OQ-030` is
available if a reviewer disagrees that a `test_ref` path can deviate un-raised.

**One structural recommendation not on the discretion list.** Declare `src/prope/property_history/models.py`
for both tables and add the `history` counterpart of the drift guard, pinned at **2**. `models.py` in
call-ledger is imported by exactly one thing — the drift guard [VERIFIED: `tests/architecture/test_schema_invariants.py:12`]
— and that is the whole of its value: it is the only mechanism that notices when the migration and the
application's idea of the schema diverge. On the one module whose product claim *is* its schema, that
mechanism is worth the file. Keep the INSERT as raw `text()` regardless, so it stays inside
`test_no_sql_interpolation.py`'s coverage (§ *Pitfall 6*).

---

## State of the Art

| Old approach | Current approach | When it changed | Impact here |
|---|---|---|---|
| `bigserial` for a surrogate key | `GENERATED ALWAYS AS IDENTITY` | PostgreSQL 10 (SQL-standard identity columns) | D-53. Strictly stronger, **and** it removes the separate sequence grant `bigserial` requires — see § *Summary* finding 2 |
| Append-only by trigger | Append-only by privilege | ADR-0025, and it is Prope's own decision rather than an industry shift | *"A trigger is owned by the same role that owns the table, so the actor it is meant to stop can drop it"* [CITED: ADR-0025] |
| Tamper-evidence by hash chain | Tamper-*prevention* by authorisation | ADR-0025 rejects the chain by name | *"It detects tampering after the fact and prevents nothing, which is backwards for a log whose realistic threat is a well-meaning repair script, not a forger"* |
| Enumerate the tables that need a tenant policy | Invert: every table needs one, exemptions are declared with a reason | ADR-0045, after *"the third instance in three passes"* | D-56 is the first exemption **in code**; ADR-0045 already wrote it in prose |
| `python-ulid` 3.x — `ULID.provider`, no monotonicity layer | 4.x — `ULIDGenerator` + `StrictMonotonicPolicy` by default | 2026-07-20 | Three weeks old. Argued in § *Standard Stack*; blast radius against this repo is zero |
| ULIDs as a sortable key | A database sequence | ADR-0024 rejected *"sort by `occurred_at` with a tiebreak on id"* | Verified against the pinned library: `default_generator` is process-local, so ids are monotonic within one process and not across two |

**Deprecated / outdated in this repo, and not this phase's to fix:** the root `Dockerfile` and
`docker-compose.yml` remain the Phase 2-era boilerplate from another project (`FROM python:3.11-slim`,
a `requirements.txt` that does not exist). PITFALLS §4 assigns the deployment stack to no milestone.
Recorded so a planner reading the repo finds them and does not extend them.

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | `OVERRIDING SYSTEM VALUE` is the material gap in D-53's guarantee, and a source gate plus an asserted engine boundary is the proportionate response | Pitfall 3 | The docs verify the mechanism and the absent privilege requirement; **that this warrants a gate is my judgement.** If the planner thinks the escape hatch is beneath notice, the engine assertion alone is defensible and the gate is dropped |
| A2 | The multixact cost of D-57's foreign key is acceptable at pilot scale | Pitfall 11 | Arithmetic against a stated load target (200 appends/sec, one `app`, one `worker`, 31 rows), **not a measurement.** If concurrency is much higher than ADR-0033 implies, the answer is to drop the key — which D-57 already prices as cheap |
| A3 | Writing the `details` bind as `CAST(:details AS jsonb)` over `json.dumps` is better than a Core `insert()` with a `JSONB` column | Pitfall 6 | The codec behaviour is verified from SQLAlchemy 2.0.51's source, **read not run** — no test may be executed in this session. The preference for staying inside `test_no_sql_interpolation.py`'s coverage is a judgement |
| A4 | The PH-05 test must write a stand-in state-change row in the same transaction | Pitfall 8, Pattern 7 | If a reviewer reads SC3 as being only about `history_event`, this is more test than the criterion demands. The reasoning — that the weaker test cannot distinguish ADR-0023's shape from D-19's — is written out so it can be disagreed with |
| A5 | `pydantic`'s job is the payload's *shape*, and the key allow-list is a set difference | Standard Stack | A declared deviation in mechanism from `libraries_frameworks`, riding D-50's footing. If the planner reads that field as prescribing per-action models, that is an OQ (`OQ-030`), not a quiet reversal |
| A6 | ADR-0045's `GLOBAL_TABLES` line is a **seventh** stale-count site and belongs in OQ-027 | Discretion #6 | The line is verified. Whether it belongs in OQ-027 or in a new `OQ-030` is a bookkeeping call; **all that matters is that it is raised somewhere** |
| A7 | `uq_history_event_seq` is a constraint index rather than D-55's forbidden fifth | Pattern 2 | If a reviewer counts indexes rather than read shapes, this needs an argument at the constraint. It is supplied; the alternative (drop `UNIQUE`, trust the sequence) is defensible and weaker |
| A8 | The rejection counter belongs in `HistoryAppendRejected.__init__` | Pattern 7, Pitfall 9 | Incrementing in a constructor is unusual and a reviewer may object on style. The property it buys — the label value cannot be anything but an enum member, and the count survives a caught exception — is the argument |
| A9 | Declaring `models.py` for two tables plus a drift guard pinned at 2 is worth the file | Discretion #9 | `call_ledger/models.py` currently has exactly one consumer, its own drift guard. If the planner judges that decorative, declaring none is consistent — but then say so, because silence reads as an omission |
| A10 | The recommended index/constraint/grant shapes have not been executed | everywhere | **No test was run in this session** (the orchestrator forbids it: 150+ seconds and Docker pulls). Every schema claim is a reading of PostgreSQL 17 documentation plus a reading of the four existing revisions, not an observed migration |

---

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| Docker daemon | The Phase 1 PostgreSQL testcontainer | ✓ | Server 29.6.2 [VERIFIED: `.planning/STATE.md`, resolved during phase 01] | none — D-02 refuses a second provisioning path |
| `postgres:17` image | the existing rig | ✓ | pulled and cached since Phase 1 | — |
| `rabbitmq:4.3-management` | **nothing in this phase** | ✓ | pulled in Phase 2 | this phase touches no broker fixture |
| `uv` | build / test | ✓ | `Makefile` uses `uv run` throughout | — |
| Network egress to PyPI | **nothing** | — | no dependency changes; `uv.lock` must not move | — |

**Standing environment facts, carried and still true.** `docker` is **not** on the default bash PATH —
a shell driving it must first `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`;
testcontainers reaches the daemon without PATH help, so `uv run pytest` needs no PATH change. The host
is **Windows**; `loop.add_signal_handler` is not implemented there, which is Phase 2's problem and not
this phase's (`property_history` starts no process — D-65). `uv run ruff format --check` fails
repo-wide on the pre-existing `line-length` disagreement (Broken Window #1); **`ruff check` is the gate
and `ruff format --check` is not.**

**One environment fact specific to this phase.** The revision number is **not** knowable at planning
time. Phase 3 executes first and its CONTEXT states *"No new table and no migration are required by any
decision above"* [VERIFIED: `.planning/phases/03-durability-idempotency-and-no-read-path/03-CONTEXT.md:572`],
so the head is *expected* to remain `0004` and this revision is *expected* to be `0005`. **That
expectation is not a licence to hardcode it.** D-04 makes the chain linear,
`tests/integration/test_migration_chain.py` asserts linearity, and phase 3's plans may yet add a
migration for CR-01 or CR-02. The executor reads `uv run alembic heads` and wires both the `revision`
id and the `down_revision` then.

**Missing dependencies with no fallback:** none.

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high`
[VERIFIED: `.planning/config.json:47-49`].

### Applicable ASVS categories

| ASVS category | Applies | Standard control |
|---|---|---|
| V2 Authentication | **no** | This module has no actor concept beyond an id and *"cannot ask"* (A-044). access-control is Phase 7 |
| V3 Session Management | no | No process, no port, no route (ADR-0023) |
| V4 Access Control | **yes, as tenancy only** | `history_event` carries the ADR-0035 policy. `read()`'s permission check is the load-bearing **absence** (T-023) and is Phase 5/6's |
| V5 Input Validation | **yes, and it is the phase** | Three validations at one site (D-62) plus the composite foreign key (D-57). `details` is the highest-risk input surface in Prope by the lock's own assessment |
| V6 Cryptography | no | This module holds no credential and never sees one |
| V7 Error Handling & Logging | **yes** | A-046, and this phase surfaces the `reason` collision (Discretion #1). A rejected append logs *"the action and the offending key name — never the offending value"* |
| V8 Data Protection | **yes** | `reason` and `details` are the two places content the allow-list exists to exclude can arrive by human hand. Bounded, not eliminated: 500 characters, never logged, never a metric label |
| **V10 Malicious Code / integrity** | **yes, and it is PH-02** | Append-only by privilege. The threat is a well-meaning repair script, and the control is the authorisation layer |

### Known threat patterns for this stack

| Pattern | STRIDE | Mitigation, and where it lands in this phase |
|---|---|---|
| **T-021 — a release, approval or grant nobody can be shown to have made** (CRITICAL; *"THIS MODULE'S REASON TO EXIST"*) | Repudiation (B4/B5) | Three properties that must hold **together**: the append is inside the caller's transaction (§ *Pattern 7*), the table is append-only by privilege (§ *Pattern 3* — PH-02), and `seq` gives a total order (§ *Pattern 2* — PH-04). **All three land in this phase.** The fourth half — keeping `prope_migrate` out of the runtime environment — is T-001 in access-control's lock and is Phase 7's |
| **T-022 — a prompt body or credential reaching the audit log through an undeclared field** (HIGH) | Information disclosure (B4) | The per-action allow-list, in Python at one site (D-62). **The phase must also assert what it does NOT protect** — a hand-written `INSERT` bypasses it, and § *Code Examples* proves that half explicitly |
| **T-023 — an audit screen that reintroduces the access-control cycle** (HIGH) | Elevation (B4) | An **asserted absence**, and D-65 makes it structural: `src/prope/property_history/` imports no FastAPI at any depth, so no route can be mounted from it even by accident. The route-table assertion is PH-07 (Phase 6) and per PITFALLS §5 cannot really run before Phase 23; the import absence can be asserted today |
| **T-024 — a restore rolls the audit log back to the last dump** (MEDIUM, accepted) | Tampering (B7) | Accepted with a procedural step (A-133, ADR-0044). **Do not re-mitigate**; A-012 has no budget for synchronous replication |
| A caller-supplied `seq` breaking the total order | Tampering | `GENERATED ALWAYS` + the `OVERRIDING` source gate + the asserted engine boundary (§ *Pitfall 3*). **New in this document** — CONTEXT's D-53 does not cover the `OVERRIDING` path |
| An unregistered action entering through a repair script | Tampering | D-57's composite foreign key, asserted as `prope_migrate` — the role a repair script actually runs as (§ *Code Examples*) |
| A tenant-scoped registry silently emptying the vocabulary | Denial of service / false assurance | D-56 + the no-tenant load test (§ *Pitfall 7*). The failure mode is **a green test**, which is the shape ADR-0045 was written about |
| SQL injection through `workspace_id` on a history append | Tampering (B4) | `set_config('app.workspace_id', :ws, true)` — bound, never interpolated [VERIFIED: `src/prope/db/session.py:45`] — and `test_no_sql_interpolation.py` adopts the new module for free |
| A cross-workspace read constructed with mismatched ids | Information disclosure | The policy's `USING`; and INT-007's *"scopes every query by `workspace_id` at the function boundary"* is **Phase 5's** function to write. This phase supplies the policy underneath it |
| `prope_report` reading `reason` and `details` across workspaces | Information disclosure | Accepted, and it is ADR-0037's declared posture. The control is A-124's allow-list and A-020's line, not a grant (§ *Discretion #5*) |

---

## Sources

### Primary (HIGH confidence)

**In-repo, read this session** — `docs/modules/property-history.lock.yml` (whole file);
`docs/modules/{prompt-registry,release-control,evaluation,provider-access,access-control}.lock.yml`
`outputs` blocks; `docs/architecture/interfaces.md` INT-006/007/008;
`docs/adr/0023`, `0024`, `0025`, `0037`, `0038`, `0045` (whole files or decision blocks);
`docs/brainstorm/assumptions/A-119.md`, `A-120.md`, `A-124.md`, `A-125.md`, `A-126.md`;
`docs/brainstorm/open_questions/OQ-027.md`, `OQ-028.md`, `OQ-029.md`;
`alembic/ddl.py`, `alembic/versions/0001_roles_and_schemas.py`, `0003_ledger_tables.py`,
`0004_workspace_retention.py`; `src/prope/db/session.py`, `db/metadata.py`, `observability.py`,
`call_ledger/domain.py`, `call_ledger/writer.py`, `call_ledger/models.py`, `call_ledger/api.py`,
`call_ledger/schemas.py`, `call_ledger/drain.py`; `tests/conftest.py`,
`tests/architecture/test_tenant_coverage.py`, `test_schema_invariants.py`,
`test_no_sql_interpolation.py`, `tests/security/test_append_only_privilege.py`;
`pyproject.toml`, `uv.lock`; `.planning/REQUIREMENTS.md`, `.planning/ORCHESTRATION.md`,
`.planning/research/PITFALLS.md`, `.planning/config.json`;
`.planning/phases/03-durability-idempotency-and-no-read-path/03-CONTEXT.md`;
`.planning/phases/02-*/02-RESEARCH.md`, `.planning/phases/01-*/01-RESEARCH.md`.

**Installed artefacts, read rather than trusted to documentation** —
`.venv/Lib/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:1184-1280` (the json/jsonb codecs
and `on_connect`); `.venv/Lib/site-packages/ulid/__init__.py:51-241` (`ULIDGenerator`, the three
monotonicity policies, `default_generator`).

**PostgreSQL 17 documentation** —
- `postgresql.org/docs/17/sql-insert.html` — `OVERRIDING SYSTEM VALUE` / `OVERRIDING USER VALUE`, and
  the absence of any privilege requirement on either
- `postgresql.org/docs/17/sql-createtable.html` — identity columns, the implicit sequence, `ALWAYS`
  vs `BY DEFAULT`, and the `sequence_options` clause that makes `CACHE 1` writable inline
- `postgresql.org/docs/17/sql-createsequence.html` — `CACHE`'s default of 1, the out-of-order-across-
  sessions caveat quoted in full, and *"`nextval` and `setval` calls are never rolled back"*
- `postgresql.org/docs/17/sql-truncate.html` — `RESTART IDENTITY`, `CASCADE`'s direction, and the rule
  that all FK-referencing tables must be truncated in the same command
- `postgresql.org/docs/17/ddl-rowsecurity.html` — *"Referential integrity checks … always bypass row
  security"*; owner bypass and `FORCE ROW LEVEL SECURITY`
- `postgresql.org/docs/17/functions-string.html` — `char_length` vs `octet_length`, with the `josé`
  example
- `postgresql.org/docs/17/functions-info.html` — `pg_get_serial_sequence` on identity columns;
  `has_table_privilege`
- `github.com/postgres/postgres` `src/backend/utils/errcodes.txt` — `428C9 ERRCODE_GENERATED_ALWAYS`

**Upstream registries and repositories** — `pypi.org/pypi/python-ulid/json`, `pypi.org/pypi/pydantic/json`,
`api.github.com/repos/mdomke/python-ulid/releases` (4.0.0 and 4.0.1 release notes).

### Secondary (MEDIUM confidence)

- `enterprisedb.com/blog/postgresql-10-identity-columns-explained` — the `permission denied for
  sequence` contrast between `serial` and identity columns. Written by the identity-column feature's
  author; the behaviour it describes is corroborated by the `CREATE TABLE` docs' statement that the
  sequence is an internal dependency, but the specific error message is quoted from the blog
- `thebuild.com/blog/a-foreign-key-pathology-to-avoid/` (Christophe Pettus) — `FOR KEY SHARE` on the
  referenced row and the multixact symptom. **The PostgreSQL `explicit-locking` page does not state
  which lock a foreign key check takes**, which is why a secondary source carries this claim

### Tertiary (LOW confidence, not relied on)

- Web-search summarisation of the `428C9` error's remediation advice, superseded by the `INSERT`
  documentation and the `errcodes.txt` entry

---

## Metadata

**Confidence breakdown:**

- **PostgreSQL semantics: HIGH.** Every claim about identity columns, sequences, truncation, RLS and
  string length is a direct quotation from postgresql.org/docs/17, fetched this session. The one
  behaviour a primary source would not give — which lock a foreign key check takes — is attributed to a
  named secondary source and labelled.
- **In-repo state: HIGH.** Every `file:line` in this document was read this session. The two Phase 1
  literals D-47 and D-48 turn on were read directly rather than inferred, and § *Pitfall 12*'s claim
  about the second assertion is a reading of line 151, **labelled as an agent judgement because no
  detector exists here** (ORCHESTRATION §0).
- **The vocabulary derivation: HIGH.** Read from all five writing modules' `outputs` blocks, which is
  the source AC-6 names, and it reproduces D-60's table exactly at 31 with no adjustment. The
  `target_type` and `detail_keys` halves are explicitly **not** derivations of a spec and are `OQ-029`.
- **The stack: HIGH.** No package is added. Both pins that go live were checked against PyPI and, for
  `python-ulid`, against the 4.0.0 release notes and the installed source.
- **Pitfalls: HIGH for eleven of thirteen.** Pitfall 11's throughput judgement is MEDIUM (arithmetic,
  not measurement) and Pitfall 6's recommendation is MEDIUM (the codec is verified from source; the
  runtime behaviour was not exercised, because no test may be run in this session).
- **The discretion resolutions: MEDIUM to HIGH.** #5 (`prope_report`) and #6 (the OQ bookkeeping) are
  HIGH — they follow from an ADR written about this table and from files verified on disk. #1
  (`LOGGABLE_FIELDS`) and #9 (test placement) are design calls with the trade-offs written out so a
  planner can overrule them.

**Not verified, and stated so:** **no test was executed and no migration was applied.** The
orchestrator forbids running the suite (150+ seconds, Docker pulls), so every schema recommendation
here is a reading of documentation plus a reading of the four existing revisions. The first plan to
execute is where these become facts.

**Research date:** 2026-08-10
**Valid until:** 2026-09-09 (30 days). Re-check sooner if `python-ulid` publishes 4.1.x or a 4.0.2, if
Phase 3's plans turn out to add a migration after all (the revision id assumption in § *Environment
Availability* moves), or if `OQ-027` resolves — the count is stated in a security-relevant file from
this phase onward.
