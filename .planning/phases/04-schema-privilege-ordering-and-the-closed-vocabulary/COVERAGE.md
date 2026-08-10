# Coverage — Phase 4: Schema, privilege, ordering, and the closed vocabulary

> **The deterministic detector is not available in this environment.** `bin/lib/api-coverage.cjs` — the
> tool Phase 1 and Phase 2 ran to decide whether a phase introduces an external surface — does not exist
> here; the GSD toolchain is absent (`.planning/ORCHESTRATION.md` §0). **No detector output is
> reproduced, inferred or invented.** Everything below is an **agent enumeration**, produced by reading
> the lock file, the four existing Alembic revisions, `pyproject.toml`, `uv.lock` and the PostgreSQL 17
> documentation, and it is labelled as such rather than presented as a detector verdict.

---

## 1. Requirement → plan, and success criterion → plan

Every requirement this phase owns appears in **exactly one** plan's `requirements:` field, and every
ROADMAP success criterion is owned by **exactly one** plan.

| Requirement | ROADMAP SC | Plan | Wave | Proven by |
|---|---|---|---|---|
| **PH-02** — the application's database role cannot UPDATE or DELETE a history event; the engine refuses, not an application guard | **SC1** | `04-01` | 1 | `tests/security/test_history_is_append_only_by_privilege.py` — two `has_table_privilege` probes, two provoked engine refusals each with a positive control inside the attempting transaction, and a grant / observe / revoke-in-`finally` mutation check |
| **PH-05** — an append carrying an unregistered action or details key raises, fails the caller's transaction, and is counted | **SC3** | `04-02` | 2 | `tests/unit/test_details_allow_list.py` (the pure half) and `tests/integration/test_unregistered_detail_key_fails_the_transaction.py` (the transaction half, with a valid event written in the same transaction and asserted gone) |
| **PH-04** — two events written in one transaction have a stable, defined order even when their timestamps are identical | **SC2** | `04-03` | 3 | `tests/integration/test_same_transaction_events_have_a_stable_order.py`, with a control asserting the two rows' `occurred_at` values are equal |
| — | — | `04-04` | 3 | Carries **no requirement id.** It asserts the two boundaries the three above rest on: where the vocabulary check actually lives (D-62's owed pair) and what never leaves the process (A-046). Stated in the plan rather than left as an empty field |

**Requirements touched but deliberately not ticked**, so a verifier does not tick them by proximity:

| Requirement | Phase that owns it | Why this phase touches it |
|---|---|---|
| **PH-06** — the registry equals the union of five lock files' event lists, 31 names, no extras and no omissions | **Phase 5** | This phase **seeds** what Phase 5 asserts against, and owes it a written derivation (D-60, reproduced in plan 04-01 Task 1). Plan 04-01 Task 2 asserts the three registry columns the specs fully determine — `requires_reason` and the two declared `detail_keys` sets — and deliberately does **not** assert the action names |
| **PH-03** — a prompt's Activity in one query | **Phase 5** | The four indexes that serve it ship here (D-55), with the table, because the reader that uses them would otherwise be adding four indexes to a table that already holds rows |
| **PH-07** — no route resolves to property-history | **Phase 6** | Made **structural** here rather than asserted: nothing under `src/prope/property_history/` imports FastAPI at any depth, and neither `app.py` nor `worker.py` is touched. Per `.planning/research/PITFALLS.md` §5 the route-table assertion cannot really run before Phase 23 |
| **PH-08** — no content in any history event field | **Phase 6** | AC-8 is full-corpus. Plan 04-04 asserts the **log and metric** half for the paths this module exercises, and routes the source-level gate to Phase 6 with AC-8 |
| **PH-01 / PH-09 / PH-10** — atomicity under a killed process, actor survival after removal, never deleted | **Phase 6** | Nothing here claims them. The privilege that makes PH-10 true ships in plan 04-01 and is asserted as a privilege, not as a never-deleted proof |
| The access-control PITFALLS §1 item *"the `SECURITY DEFINER` set is exactly the sanctioned functions"* | **Phase 7** | D-49's parameterisation delivers the `history` half three phases early, as a side effect. **Say so; do not claim the criterion** |

---

## 2. External surface — there is none, and here is what that means

**This phase integrates no new external service and adds no dependency.** No SDK, no HTTP client, no
broker interaction, no new container. `pyproject.toml` and `uv.lock` are untouched by every plan in the
phase, and a task list containing a `uv add` has found something the research did not.

**No library changes status, and in particular `pydantic` does not become used by this module.**
`python-ulid==4.0.1` acquires a third call site — `EVENT_ID_PREFIX = "hev_"` — beside the two it
already has at `src/prope/call_ledger/api.py:433` and `src/prope/call_ledger/schemas.py:441`, so it was
already in use and does not move. **`pydantic==2.13.4` is not used by `src/prope/property_history/` at
all**: the lock's `libraries_frameworks` says pydantic validates the `details` payload against the
per-action allow-list, and plan 04-02 ships that check as a set difference over frozen dataclasses
instead, with no pydantic model declared anywhere in the package. That deviation is argued in
`deferred-items.md` §3 against the lock field it deviates from, and is stated here rather than left to
a verifier who would go looking for a model and find none. Both packages were audited by hand in
`04-RESEARCH.md` § *Package Legitimacy Audit*, which is itself labelled an agent judgement because
`gsd-tools query package-legitimacy` does not exist here. Neither ships a build hook. Neither warrants a
`checkpoint:human-verify`.

**A no-integration declaration would nevertheless be the weaker of the two available answers**, for the
reason Phase 2 gave when it recorded a matrix against a `false` detector verdict: this phase reaches for
a set of **PostgreSQL 17 capabilities that have never been used in this repository**, on the one table
whose editability would falsify the product's pitch. A capability chosen by accident on this table is
exactly the hole a coverage matrix exists to close. So the surface enumerated below is the PostgreSQL 17
DDL and privilege surface this phase touches for the first time. `INTEGRATE` is the default; every
`OPT-OUT` carries a written reason.

| capability | decision | reason |
|---|---|---|
| `CREATE SCHEMA … AUTHORIZATION <role>` outside revision `0001` | INTEGRATE | ADR-0027. The `AUTHORIZATION` clause is what makes `prope_migrate` the owner, which is what ADR-0035's owner bypass rests on |
| `GRANT USAGE ON SCHEMA` | INTEGRATE | The `ledger` shape repeated for `history` |
| `bigint GENERATED ALWAYS AS IDENTITY` | INTEGRATE | D-53. The first identity column in the project |
| `sequence_options` inline on an identity column — `(CACHE 1)` | INTEGRATE | Pitfall 4. Written out although it is also the default, so the value is a stated intention a test can read back |
| `pg_get_serial_sequence` on an identity column | INTEGRATE | Test only. It is what makes `seqcache` assertable without knowing the generated sequence's name |
| `jsonb` column with a `DEFAULT '{}'::jsonb` | INTEGRATE | D-58. The first `jsonb` in the project; revision `0003` refused it for `request_body` on the opposite argument, and the two are one rule applied twice |
| `text[]` column | INTEGRATE | D-59. `detail_keys` is a set of identifiers and the allow-list check is a set operation |
| `CAST(:param AS jsonb)` over a `json.dumps` string | INTEGRATE | Pitfall 6. Keeps serialisation this module's decision rather than a dialect's, and keeps the statement inside `test_no_sql_interpolation.py`'s walk |
| Composite `FOREIGN KEY (a, b) REFERENCES t (a, b)`, intra-schema | INTEGRATE | D-57. The first composite key in the project; the first two are single-column |
| `UNIQUE (a, b)` existing solely to receive a `REFERENCES` clause | INTEGRATE | Mechanical, not semantic — commented at the constraint so it is not tidied away as a duplicate of the primary key |
| Named `CHECK` constraints imitating `NAMING_CONVENTION` by hand | INTEGRATE | The project emits no SQLAlchemy DDL, so the convention is imitated in SQL text; it is what lets a test say *which* constraint refused |
| `char_length()` in a CHECK | INTEGRATE | D-54. Characters, not bytes — ADR-0053 ships a Vietnamese-only interface |
| A multi-row `INSERT … VALUES` **inside a migration** | INTEGRATE | D-59. No revision in this repository has ever inserted a data row; ADR-0038's safety argument is a deploy ordering that only exists if the seed is a migration |
| `TRUNCATE … RESTART IDENTITY CASCADE` spanning two schemas with a named exclusion | INTEGRATE | D-48, test rig only. `CASCADE` reaches `history_event` through the vocabulary key, which is the second independent reason the registry is excluded |
| `has_table_privilege(role, schema.table, privilege)` | INTEGRATE | Already used by `test_append_only_privilege.py`; extended here to `DELETE` and to a second role |
| `OVERRIDING SYSTEM VALUE` | **OPT-OUT** | It bypasses `GENERATED ALWAYS` with **no privilege requirement**, which would break `seq`'s only property. Refused in `src/prope/` and `alembic/` by a source gate, and its acceptance by the engine is asserted as a recorded boundary rather than assumed away (plan 04-03) |
| `GENERATED BY DEFAULT AS IDENTITY`, and `bigserial` | **OPT-OUT** | Both behave as a `DEFAULT`, which is only consulted when the caller omits the column — and `prope_app` holds `INSERT` by design. `BY DEFAULT` is the worse of the two because it carries the word "identity" while behaving as `bigserial` |
| Native `CREATE TYPE … AS ENUM` | **OPT-OUT** | Pitfall 4, now a standing project rule with a parameterised test behind it: adding a value cannot run inside a transaction block and removing one is impossible at any price |
| `CREATE TRIGGER` of any kind | **OPT-OUT** | ADR-0023 rejects triggers **for this module by name**; ADR-0025 rejects a `BEFORE UPDATE` trigger as *"strictly weaker for the same effort"* because it is droppable by the role it polices. The consequence — a Python-only guarantee — is asserted rather than assumed (plan 04-04) |
| `SECURITY DEFINER` function | **OPT-OUT** | The sanctioned set is exactly four and none is in `history`. A fifth is never the answer |
| `CHECK (action IN (…31 literals…))` | **OPT-OUT** | A second copy of the vocabulary, and the thirty-second action would become a `DROP`/`ADD CONSTRAINT` with a validating scan over an append-only table — where ADR-0038 assumes a plain `INSERT` |
| `CHECK (target_type IN (…13 literals…))` | **OPT-OUT** | The same argument one column over. The registry's thirty-one rows **are** the enumeration and the composite key is what closes it |
| `GIN` index on `details` | **OPT-OUT** | D-55. No query in any lock file reads a details key, and this is the one table in Prope that only ever grows (A-121) |
| `ON DELETE` / `ON UPDATE` referential actions | **OPT-OUT** | `0003`'s stated rule: the registry is `SELECT`-only for `prope_app` and the vocabulary is closed, *"so the case cannot arise, and naming a behaviour for an impossible case invites someone to make it possible"* |
| `FORCE ROW LEVEL SECURITY` | **OPT-OUT** | It would subject the owner to the policy, breaking every migration and every test-rig positive control. ADR-0035 depends on the owner bypass |
| `ALTER DEFAULT PRIVILEGES` | **OPT-OUT** | `grant_table`'s docstring: *"a future table should arrive with no privileges until somebody writes them"* |
| Table partitioning on `history_event` | **OPT-OUT** | A-121 keeps events forever and the lock's own growth estimate is *"< 500 events per prompt property per year at pilot volume"*. Partitioning is a runbook A-012 has no budget for, and the revisit trigger is the pilot's measured growth, not a guess |
| `pg_cron`, a retention job, or any expiry mechanism | **OPT-OUT** | A-121: nothing expires, there is no retention setting and no job. **The absence of a deletion path is part of the guarantee** |
| A hash chain or tamper-evidence column | **OPT-OUT** | ADR-0025 rejects it by name: *"it detects tampering after the fact and prevents nothing, which is backwards for a log whose realistic threat is a well-meaning repair script, not a forger"* |
| `LISTEN`/`NOTIFY` for registry invalidation | **OPT-OUT** | ADR-0038's cache has no TTL and no invalidation by design; the only writer is a migration and ADR-0031 restarts the application after migrating. A second invalidation channel was rejected project-wide twice already |
| A second broker queue for history events | **OPT-OUT** | `events.publishes: []`. *"The `events` in this module are rows in a table, not messages"* — a naming collision the lock states once so nobody looks for a topic |

---

## 3. What this phase does **not** cover, stated so a verifier does not look for it

- **`append()`, `read()` and `registered_actions()` as INT-006 / INT-007 / INT-008's registered
  signatures**, cursor pagination, `scope_prompt_id` as a contract, AC-6's vocabulary equality, and the
  wiring of ADR-0038's cache into `app` and `worker` — **Phase 5** (PH-03, PH-06). D-64 draws the line
  by capability rather than by filename, and plan 04-02 ships the write path under a name no downstream
  spec uses.
- **Atomicity under a killed process (AC-1), the route-table assertion (AC-7), the full-corpus content
  inspection (AC-8), actor survival after removal (AC-9), the never-deleted proof (AC-10)**, six of the
  seven metrics and all three alerts — **Phase 6**.
- **The five writing modules** — Phases 7, 10, 13, 16 and 22. Every contract this phase builds is proven
  from property-history's own tests, exactly as Phase 2 proved `enqueue` and `price_usage` with neither
  the gateway nor evaluation in existence.
- **Two concurrent transactions.** Nothing in this phase exercises them, so *assignment order is not
  commit order* is documented rather than asserted, and is handed to Phase 5 with the reason (plan
  04-03).
