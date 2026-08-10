# Phase 4: Schema, privilege, ordering, and the closed vocabulary - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-10
**Phase:** 4-schema-privilege-ordering-and-the-closed-vocabulary
**Mode:** `workflow.discuss_mode: assumptions`, run `--batch --analyze` per `.claude/CLAUDE.md`.
Under `mode: yolo` (ORCHESTRATION §6) this session **does not stop**: each assumption is stated with
its evidence and its trade-off table, an option is adopted, and anything that would have been a
blocking one-way checkpoint is marked `ADOPTED: UNCONFIRMED` with a reversibility rating.
**Areas surfaced:** The first new schema since Phase 1 · Append-only, and how the privilege is
spelled · The total order and the twelve columns · The closed vocabulary — where it is enforced and
what is actually in it · Where Phase 4 stops and Phase 5 begins

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| The first new schema since Phase 1 | Two Phase 1 files name a schema literally. Revision `0004` proved a new *table* is free; a new *schema* is not | ✓ |
| Append-only, and how the privilege is spelled | PH-02 is the phase's first criterion and contains no application code. The lock names a literal `REVOKE` the project's helper does not issue | ✓ |
| The total order and the twelve columns | PH-04 rests on `seq` being assigned only by the engine, on a table where `prope_app` holds `INSERT` | ✓ |
| The closed vocabulary | Three registry columns have no declared values; the count is 30 in six places and 31 in five; and the enforcement layer is unsettled | ✓ |
| Where Phase 4 stops and Phase 5 begins | ROADMAP puts `append()` in Phase 5 and PH-05 in Phase 4 | ✓ |

**All five surfaced.** Two areas were considered and not raised as their own: the metric and log-field
wiring (only one counter lands here, and the collision it exposes is recorded inside the module-layout
decision), and the `details` validator's library choice (pydantic v2 is already pinned and the lock
names it — nothing to trade).

---

## The first new schema since Phase 1

### Assumption: a new schema is adopted by the Phase 1 rig for free, the way `ledger.workspace_retention` was

**Status: FALSE, and the correction is two files.** Revision `0004`'s docstring claims *"no test rig
edit is needed, and that is the point"* — true of a new **table**, because ADR-0045's walk enumerates
`pg_class` and the truncate fixture enumerates `pg_tables`. Both are nevertheless told a **schema**
name: `tests/conftest.py:97` filters `schemaname = 'ledger'`, and
`tests/architecture/test_tenant_coverage.py` carries `EXPECTED_ABSENT_SCHEMAS` plus a companion
`assert tuple(existing) == ("ledger",)`.

`.planning/STATE.md`'s Phase 01 line says *"Phase 7 (access) is the first phase that must shrink
it"*. That is now wrong; this phase is first.

**This finding is an agent judgement from reading the two files. No detector was run — the GSD
detectors do not exist in this environment (ORCHESTRATION §0).**

### What the truncate fixture does about the seeded registry

| Option | Description | Adopted |
|--------|-------------|---------|
| Widen to both schemas, exclude `history_action_registry` by name | The registry is written by the migration and by nothing else. Truncating it destroys the seed after test one, and `CASCADE` reaches `history_event` through the vocabulary key. Costs one named exclusion with a comment | ✓ |
| Widen to both schemas, re-seed the registry in the fixture | Symmetric with the other tables. Costs a **second provisioning path** for the vocabulary — the split D-02 rejected by name — and lets the suite pass against a registry the migration never wrote, which is the one failure AC-6 exists to catch | |
| Leave the fixture on `ledger` and truncate history per test file | No shared edit. Costs: every history test file owns cleanup, and the first one that forgets leaks rows into the next | |

**Adopted:** exclude by name (D-48).
**Notes:** the failure mode of getting this wrong is diagnostically nasty — "every test after the
first says the action is unregistered" points at the validator, not at a fixture two directories
away. Also recorded: `RESTART IDENTITY` resets the `seq` sequence between tests, which makes
per-test `seq` values small and predictable.

### Whether the generic schema invariants are parameterised or copied

| Option | Description | Adopted |
|--------|-------------|---------|
| Parameterise the five generic tests over both schemas | No `SECURITY DEFINER`, no native enum, no FK leaving the schema, every timestamp zoned, no floats — these are project rules, not ledger rules. One assertion site | ✓ |
| Copy them into a `history` counterpart file | No edit to a Phase 1 file. Costs: the rule is asserted twice and the copy that stops being maintained is invisible — D-06's *"the rule selecting for its own blind spot"* | |
| Assert them only for `ledger` and trust `history` | Cheapest. Costs: the schema holding the product's central claim is the one nobody checks for a stray `SECURITY DEFINER` | |

**Adopted:** parameterise (D-49).
**Notes:** flagged at the time as a **cross-phase edit** — this phase modifies a Phase 1 test file,
and CONTEXT requires the plan to say so rather than let it appear in a diff. Five of the file's eight
tests are generic; the three ledger-specific ones (money columns, the `created_at`/`written_at`
default split, the `len(declared) == 6` drift guard) stay scoped and untouched. Two of the five carry
`ledger` in their function names and need renaming as part of the same edit.

---

## Append-only, and how the privilege is spelled

### Assumption: the migration must issue the literal statement the lock file names

**Status: PARTIALLY FALSE.** `docs/modules/property-history.lock.yml` `libraries_frameworks` names
`REVOKE UPDATE, DELETE ON history.history_event FROM prope_app`. `alembic/ddl.py`'s `grant_table`
helper reaches the same end state by `REVOKE ALL FROM PUBLIC` plus positive grants, and its docstring
already argues the choice: *"both end in the same state and the positive form is the one a reviewer
can read."* `prope_app` never holds `UPDATE` or `DELETE`, so the literal `REVOKE` would be a no-op
that reads in a diff as protection.

| Option | Description | Adopted |
|--------|-------------|---------|
| `grant_table` positive form, assert the end state | Matches every other table in the project, so a reviewer greps one helper name. The assertion is two `has_table_privilege` calls returning false — true under either spelling | ✓ |
| Issue the literal `REVOKE` as well, for fidelity to the lock | Zero risk, matches the text. Costs: a statement that does nothing, in the one migration whose readability is the guarantee, teaching the next module to write no-op REVOKEs | |
| Issue the literal `REVOKE` **instead** of using the helper | Fidelity, and the grant matrix is then bespoke. Costs: `history_event` becomes the one table in Prope whose grants a reviewer cannot find by grepping `grant_table` | |

**Adopted:** positive form (D-50).
**ADOPTED: UNCONFIRMED** — a declared deviation in *spelling* from a lock-file field. **No OQ
raised**, because the field describes a mechanism and the end state is identical; if a reviewer
disagrees that a spelling deviation can go un-raised, that is the thing to say.
**Reversibility: one-way in the D-07 sense** — a later widening is blocked by whatever has come to
depend on the absence, and here that is the product's central claim.

### How much of `test_append_only_privilege.py`'s shape is copied

| Option | Description | Adopted |
|--------|-------------|---------|
| Structural mirror, including the positive control **and** the mutation check | The positive control runs inside the attempting transaction, so a refusal is distinguishable from an invisible row; the mutation check grants, observes the refusal stop, revokes in a `finally` | ✓ |
| Positive control only, skip the mutation check | Shorter. Costs: nobody ever proves the two refusal tests are asserting a refusal rather than an empty table — and under RLS an empty table is the default observation | |
| Neither; assert `has_table_privilege` and stop | Cheapest and genuinely tests the grant. Costs: it tests the catalogue, not the engine's behaviour, and ADR-0025's whole argument is about what the engine does | |

**Adopted:** full mirror (D-52).
**Notes:** `price_table`'s version of this protects a cost figure's explicability; this one protects
the sentence the product is sold on and is the phase's first success criterion. Copying the shape is
cheaper than rediscovering why it has that shape.

---

## The total order and the twelve columns

### Assumption: `seq` should be `bigserial`, because the lock file says `bigserial`

**Status: TRUE AS A TYPE, INSUFFICIENT AS A GUARANTEE.** `bigserial` is a `DEFAULT nextval(...)`, and
a default is only consulted when the caller omits the column. `prope_app` holds `INSERT` on this
table by design, so a statement supplying its own `seq` is accepted and the total order stops being
total with no error anywhere.

| Option | Description | Adopted |
|--------|-------------|---------|
| `bigint GENERATED ALWAYS AS IDENTITY`, `NOT NULL UNIQUE` | The engine refuses a caller-supplied value. Same column type, same monotonicity, strictly stronger. Same class of guarantee as the absent `UPDATE` grant, on the same table, for the same reason | ✓ |
| `bigserial`, literally as written | Fidelity to the lock's word. Costs: the phase's second success criterion rests on a default | |
| `GENERATED BY DEFAULT AS IDENTITY` | Reads as identity, behaves as `bigserial`. Costs: all of the above plus the false comfort of the word "identity" | |

**Adopted:** `GENERATED ALWAYS` (D-53).
**ADOPTED: UNCONFIRMED** — the lock file's `data.owns` note says `bigserial`. Treated as naming a
spelling rather than a behaviour, since the same sentence names the behaviour ("monotonic, and the
ONLY sort key") and `GENERATED ALWAYS` implements it more strictly. **No OQ raised**, on the same
footing as the `REVOKE` spelling above. If a planner disagrees, this is an OQ, not a quiet reversal.
**Reversibility: one-way once rows exist** — changing the sort key of an append-only table means
rewriting rows the application role cannot rewrite.

### Which column is the primary key

| Option | Description | Adopted |
|--------|-------------|---------|
| `id` (the `hev_` ULID) is the PK; `seq` carries `UNIQUE NOT NULL` | `id` is what INT-006 returns, what the lock says is logged, and what A-045 makes the convention across eight modules. One identity per row | ✓ |
| `seq` is the PK; `id` carries `UNIQUE` | Smallest index, and the cursor key is the key. Costs: two identities for one row and a per-call-site decision about which one is meant | |
| Composite `(workspace_id, seq)` | Aligns the PK with every read scope. Costs: `id` becomes decorative, and A-045's identifier convention stops being uniform | |

**Adopted:** `id` as PK (D-53).

### Whether `occurred_at` defaults to `now()`

| Option | Description | Adopted |
|--------|-------------|---------|
| `NOT NULL`, no default; the caller supplies it, and `append()`'s Python signature defaults to "now" | INT-006's envelope lists `occurred_at` as caller-carried. One source for the value. The consequence is stated rather than mitigated: a caller can stamp a wrong time, and nothing order-bearing reads it | ✓ |
| `NOT NULL DEFAULT now()` | The database stamps it, so a caller cannot lie on the one table that is evidence. And `now()` is transaction start, so two events in one transaction share a timestamp — which is exactly AC-4's case, handled correctly by `seq` | |
| Both — default the column *and* accept a caller value | Never wrong at either end. Costs: two sources for one fact, which is the thing D-58 refuses one column over | |

**Adopted:** caller-supplied, no default (D-54).
**Notes:** the second option is genuinely attractive for an audit table and was rejected on INT-006
rather than on merit — the registered envelope says the caller carries it, and A-125 removes the
stake by forbidding any ordering claim from reading it. Recorded because "the database should stamp
the audit timestamp" is the argument a reviewer will make, and it deserves an answer that is not
"we didn't think of it".

### The `reason` cap

| Option | Description | Adopted |
|--------|-------------|---------|
| `CHECK (reason IS NULL OR char_length(reason) <= 500)` | Characters, not bytes, and a named constraint a test can assert by name. ADR-0053 ships a Vietnamese-only interface, so a byte cap would silently be a ~170-character cap for every user the MVP has | ✓ |
| `varchar(500)` | One word, enforced by the type. Costs: a later change is an `ALTER TYPE` rewrite on an append-only table, and there is no constraint name for a test to point at | |
| No cap; trust the caller | The cap is a blast-radius control, not a correctness rule (the lock says so). Costs: the one field a human types free text into is the one place content the allow-list exists to keep out can arrive | |

**Adopted:** named CHECK in characters (D-54).

---

## The closed vocabulary — where it is enforced and what is actually in it

### Assumption: `history_action_registry` is tenant-scoped like every other table in Prope

**Status: FALSE, and getting it wrong makes AC-6 pass vacuously.** ADR-0045's default is that every
table carries `workspace_id`. Under ADR-0035's inversion, a tenant-scoped registry returns **zero
rows** to a caller with no tenant context — which is precisely `registered_actions()`'s consumer, a
CI test. AC-6 would then compare an empty set against an empty set and stay green forever.

| Option | Description | Adopted |
|--------|-------------|---------|
| No `workspace_id`; first entry in `GLOBAL_TABLES` with a written reason | The vocabulary is closed globally by A-120. The exemption is a sentence a reviewer can disagree with, which is what `GLOBAL_TABLES` is for, and `test_every_global_table_exemption_carries_a_written_reason` starts guarding a real entry | ✓ |
| `workspace_id` on the registry, 31 rows per workspace | No exemption, no argument to write. Costs: "closed at 31" becomes a per-tenant claim, and INT-008 reads nothing outside a tenant context | |
| Not a table at all — a Python constant | ADR-0038 caches it in process anyway. Costs: ADR-0024 and the lock both make it a table so `registered_actions()` is queryable by a route-table test and a CI schema check, and D-57's key needs a table to point at | |

**Adopted:** global, exempted with a reason (D-56).
**ADOPTED: UNCONFIRMED** — the first `GLOBAL_TABLES` entry in the project, and it sets the register
for the seven modules that follow. **Reversibility: costly** — every later reader is written against
a table with no tenant column.

### Where the closed vocabulary is actually enforced

| Option | Description | Adopted |
|--------|-------------|---------|
| Composite FK `(action, target_type)` → the registry, **plus** the Python check | The vocabulary lives in exactly one place and the engine enforces it. Closes the hand-written-statement path ADR-0025 names as the realistic threat, and makes a wrong action/target pairing an engine refusal. The Python check still runs first, because only it can produce `append_rejected_total{reason=…}` | ✓ |
| `CHECK (action IN (…31 literals…))` | No second table on the insert path. Costs: the vocabulary is duplicated, and the 32nd action becomes `DROP`/`ADD CONSTRAINT` with a validating scan over a table that only grows — where ADR-0038 assumes a plain `INSERT` | |
| Python only, no database constraint | Matches ADR-0038's cached-mapping reading literally. Costs: "closed vocabulary" is a convention on the one table where ADR-0025 exists to remove the word "convention" | |
| `BEFORE INSERT` trigger doing the whole check | Genuinely in the transaction, covers all three validations. Costs: ADR-0023 rejects triggers for this module **by name** — they put the audit vocabulary in migrations where ADR-0024's allow-list cannot run | |

**Adopted:** composite FK plus the Python check (D-57).
**ADOPTED: UNCONFIRMED** — an intra-schema foreign key on a tenant-scoped table, which is a shape
Phase 1 refused in `ledger` for a stated reason. The reason (RI checks bypass RLS, so a key into
another tenant-scoped table is a covert channel) **does not apply**: this key's target is global and
identical for every workspace, so there is nothing to infer. Checked rather than assumed.
**Reversibility: cheap to drop, costly to add later** — one line either way today, a validating scan
over a never-shrinking audit table once the pilot has run.

### Where `requires_reason` and the `details` allow-list are enforced

| Option | Description | Adopted |
|--------|-------------|---------|
| Python, at one validation site, with the absence of a database backstop **asserted** | Neither rule can be a CHECK — a CHECK cannot reach another table. The allow-list cannot be a trigger without reimplementing it in PL/pgSQL. A test proves a hand-written `INSERT` bypassing the module succeeds, so a later phase inherits a recorded boundary rather than a belief | ✓ |
| A `BEFORE INSERT` trigger for `requires_reason` only, Python for the allow-list | Half the rules in the engine. Costs: three validations split across two languages so that one of them can be a trigger, which is worse than either whole | |
| Python, absence not asserted | Shortest. Costs: exactly the defect T-006 was written about — a property correct by intention rather than by assertion | |

**Adopted:** Python, absence asserted (D-62).
**Notes:** revision `0004` refused a trigger once already, with three numbered reasons. **Only two
transfer** — the volume argument does not apply here, because `history_event` takes one row per
state change, not one per gateway call. The argument was therefore re-made rather than cited, and
the decisive citation turned out to be ADR-0023 rather than `0004`.

### What is actually in the vocabulary

**Assumption surfaced: the 31 names can be read off ADR-0024's table. FALSE.** ADR-0024's Context
table lists **30** and omits `user_tombstoned`; a derivation from it produces a red AC-6. The union
of the five writing modules' `outputs` blocks — which is the source AC-6 names — is **exactly 31 with
no adjustment**, because `user_tombstoned` was added to `access-control.lock.yml` `outputs` by
ADR-0054 on 2026-08-09.

| Finding | Evidence | Adopted |
|---|---|---|
| The count is 30 in six places and 31 in five, twice inside the same file | ADR-0024 lines 1/13/120 vs 53; `interfaces.md` 248/312 vs 229/33; A-120 line 25 vs 15; `assumptions.md` 128 | **31**, raise `OQ-027` |
| Four action names do not satisfy A-120's own `<target_type>_<past participle>` rule against their real target — `retired`, `owner_changed`, `access_level_changed`, `access_granted`/`access_revoked` | A-120's rename list covers only release-control's six bare verbs | Seed **the lock files' literal names**, raise `OQ-028` |
| `target_type` is a "closed enumeration" listed nowhere; only `user` is stated anywhere (A-151) | ADR-0024 line 54, A-122, A-119 | **Derive 13 values**, record the derivation, raise `OQ-029` |
| A-119 says the prompt-scoped set names *six* `target_type`s; the derivation gives **seven** | A-119 vs the 31-name derivation | Recorded in `OQ-029`, not resolved |
| `detail_keys` is declared for 3 of 31 actions; the other 28 belong to modules built 6–18 phases from now | A-124's two examples, `release-control.lock.yml`, ADR-0054's empty set | **Seed only the declared keys; leave 28 empty**, which refuses any key at all on those actions |

**ADOPTED: UNCONFIRMED** — seeding `retired` leaves A-120 false for one of 31 names; seeding
`property_retired` makes AC-6 red. AC-6 is an asserted equality and A-120 is prose, so the equality
wins. **Reversibility: one-way after the pilot** — A-120's own note says a rename before data exists
is cheap, and after it is an `UPDATE` on a table `prope_app` cannot update by design (ADR-0025).
**The window in which this is a two-line lock-file edit closes at the pilot.**

### Where the seed lives, and `details`' type

| Option | Description | Adopted |
|--------|-------------|---------|
| Seed in the same revision as the tables | ADR-0038's safety argument *is* a deploy ordering — the row exists, then the code that names it starts — and that only holds if the seed is a migration. D-57's key also means the registry must be non-empty before the first event | ✓ |
| A separate data revision | Separates schema from data. Costs: two revisions that must not be applied apart, for no gain | |
| Seed from application code at startup | Idempotent upsert, no migration. Costs: a second provisioning path, and the first append after a fresh deploy becomes a race against the seeder | |

**Adopted:** same revision (D-59).

| Option | Description | Adopted |
|--------|-------------|---------|
| `details jsonb NOT NULL DEFAULT '{}'::jsonb` | Our own code assembles it from allow-listed keys, so a malformed payload is a caller bug and the engine refusing it is right. One spelling of "no details", so the allow-list check has one branch | ✓ |
| `json`, nullable | Byte-preserving, keeps duplicate keys and key order. Costs: NULL and `{}` become two spellings of the same fact, and nothing requires byte fidelity | |
| `text` | What `call_body.request_body` is. Costs: the reason there was that a malformed **provider** body is exactly the body worth keeping — the opposite case | |

**Adopted:** `jsonb NOT NULL DEFAULT '{}'` (D-58). No GIN index: no query in any lock file reads a
details key, and none of the four declared indexes touches the column.

---

## Where Phase 4 stops and Phase 5 begins

### Assumption: `append()` is entirely Phase 5's, because Phase 5's goal names it

**Status: INCOMPATIBLE WITH PH-05.** ROADMAP Phase 5's goal names `append()`, `read()` and
`registered_actions()`. ROADMAP Phase 4 owns **PH-05**, whose success criterion is *"an append with
an unregistered action or an unregistered `details` key raises, rolls the caller's transaction back
with no partial state, and increments `append_rejected_total` with a reason"* — none of which is
observable without a path that validates and writes. ORCHESTRATION §9: *"a red test is never
'expected'."*

| Option | Description | Adopted |
|--------|-------------|---------|
| Split by capability: the validating write path here, the three registered seams in Phase 5 | Phase 4 builds the registry loader, the validator, the refusal type, the counter and an internal insert on a caller-supplied session; Phase 5 wraps it as INT-006's signature and adds `read()` and `registered_actions()`. Costs: Phase 4 ships a path under a name no downstream spec uses | ✓ |
| Build the full `append()` here and leave Phase 5 `read()` + `registered_actions()` | No renaming later. Costs: takes `scope_prompt_id` stamping and the INT-006 contract out of the phase whose goal names them, and pulls the cache wiring into `app`/`worker` a phase early | |
| Schema and privilege only; let Phase 5 prove PH-05 | Clean phase goals. Costs: Phase 4's third success criterion cannot be tested inside Phase 4, which §9 forbids and which would move a requirement without moving it in REQUIREMENTS.md | |

**Adopted:** split by capability (D-64).
**ADOPTED: UNCONFIRMED** — this reallocates work across two ROADMAP phase goals without renumbering
anything. Requirement ownership is untouched: PH-05 stays Phase 4's and PH-03/PH-06 stay Phase 5's.
**Reversibility: cheap** — the split is a naming boundary inside one module and one milestone; Phase
5 renames or wraps, and no other module can see either name.

### Assumption: the module needs an entry in `app.py` or `worker.py`

**Status: FALSE for this phase, TRUE for Phase 5.** ADR-0038 loads the registry cache at process
start in both containers, which is a D-13 explicit-composition edit — but the cache is what
`append()` reads, and `append()` is Phase 5's. Phase 4's loader is a plain function its tests call
directly. Adopted (D-65) because it also removes the only file-level collision this phase could have
had with Phase 3 under ORCHESTRATION §7's serial-execution rule; the remaining shared-file contact is
`tests/conftest.py`, and D-48's edit there is additive.

### Assumption: the module's counter and log fields belong in `src/prope/observability.py`

**Status: HALF FALSE, AND IT SURFACED A COLLISION.** That module's docstring scopes it to *"the Phase
2 counters, and only those"* and every metric in it is `prope_call_ledger_*` — so the counter belongs
in the module. But `LOGGABLE_FIELDS` in the same file is a **project-wide** A-046 allow-list, and
**`reason` is already in it**: for call-ledger a closed vocabulary token (`unroutable | nacked |
timeout`), for property-history user-authored free text the lock says must **never** be logged. One
flat set keyed on field name cannot express both. Phase 2's own note — *"an allow-list with a field
outside it is an allow-list somebody has already stopped believing"* — closes off the easy answer of
quietly forking a second set.

**Not decided here.** Recorded in D-65 and routed to CONTEXT's Claude's Discretion list as the first
item, because the resolution shape (per-module list, qualified key, rename, or a floor-and-subtract
rule) is a design call the planner should make with the metric set in front of it.

---

## Claude's Discretion

Left to the researcher and planner, open rather than decided:

- How the `LOGGABLE_FIELDS` collision on `reason` is resolved, keeping the property assertable in one place
- Whether the rejection-reason `StrEnum` lives in `domain.py` or beside the counter, and whether its byte-identity with the metric label set is asserted by a test or by proximity
- The `hev_` identifier generation site, and whether it is shared with the six prefixes Phase 7 onward will want
- Whether `scope_prompt_id` gets any constraint in this phase, given the lock routes its enforcement to a metric (which is Phase 6's) rather than to a refusal
- `prope_report`'s read grants on both tables — `grant_table`'s default is true and A-126's Success SQL argues the same way, but the argument should be made rather than inherited
- Whether the three vocabulary findings are three OQ files or fewer; all three conflicts must be raised
- The exact `GLOBAL_TABLES` reason string — the first one in the project, and it sets the register
- Whether D-60's derivation table is committed as a fixture Phase 5's AC-6 reads, or re-derived there from the lock files
- Test file placement against the lock's `test_ref` paths, several of which name `tests/unit/…` for tests that need a live database

## Deferred Ideas

Two, both raised while deriving the vocabulary, both with a named owner and neither absorbed:

- **No phase owns "each writing module registers its own `detail_keys`."** Captured in `OQ-029`;
  natural homes are Phases 10, 13, 16 and 22.
- **AC-3 / Phase 5 SC1 say "all ten events" over a lifecycle that enumerates nine.** Handed to Phase
  5, which owns AC-3, rather than raised as an OQ from outside it.

The items in CONTEXT's `<deferred>` section beyond these two are fixed ROADMAP boundaries — Phase 5's
three seams and AC-6, Phase 6's four asserted guarantees and six metrics, the five writing modules,
the SPA and the deployment stack — noted so a planner does not mistake them for gaps.

## Carried forward under `mode: yolo`

Six adoptions are marked `ADOPTED: UNCONFIRMED` above and must be copied into `04-UAT.md` as numbered
human-verification items and into `.planning/ORCHESTRATION-DECISIONS.md` as one row each
(ORCHESTRATION §6):

| # | Decision | What was adopted without confirmation | Reversibility |
|---|---|---|---|
| 1 | D-50 | `grant_table`'s positive form instead of the lock file's literal `REVOKE UPDATE, DELETE`; no OQ raised for a spelling deviation | one-way |
| 2 | D-53 | `GENERATED ALWAYS AS IDENTITY` where the lock says `bigserial`; no OQ raised for a strengthening | one-way once rows exist |
| 3 | D-56 | `history_action_registry` is the project's first `GLOBAL_TABLES` entry | costly |
| 4 | D-57 | A composite foreign key on a tenant-scoped table, where Phase 1 refused foreign keys in `ledger` | cheap to drop, costly to add later |
| 5 | D-61 | Seeding `retired` (leaving A-120 false for one name) and a derived 13-value `target_type` set; 28 actions seeded with an empty `detail_keys` | one-way after the pilot |
| 6 | D-64 | The validating write path lands in Phase 4 though ROADMAP's Phase 5 goal names `append()` | cheap |

**None of the six touches a §2 non-negotiable.** Items 1, 2 and 4 all move in the direction of a
stronger engine-enforced guarantee, which is the direction the non-negotiables point.
