# Phase 4: Schema, privilege, ordering, and the closed vocabulary - Context

**Gathered:** 2026-08-10
**Status:** Ready for planning

<domain>
## Phase Boundary

The `history` schema exists as a migration that **carries its own guarantees**, and the three
properties the whole module is sold on become facts an engine enforces rather than sentences five
lock files repeat: the log cannot be rewritten, two events written together have a defined order,
and a name outside the vocabulary is refused.

This is the first new schema since Phase 1, so it is also the phase that discovers what "add a
schema" costs in a test rig built around one.

**Delivers:**
- The `history` schema, created and owned by `prope_migrate`, with `USAGE` granted to `prope_app`
  and `prope_report` — the ADR-0027 shape revision `0001` established for `ledger`
- `history.history_event` — twelve columns, no thirteenth, with its named CHECKs, its four declared
  indexes, ADR-0035's tenant policy and the grant matrix, all in one revision
- **The privilege that is the guarantee**: `prope_app` holds `SELECT` and `INSERT` on
  `history_event` and holds neither `UPDATE` nor `DELETE`, asserted against the live engine with a
  positive control and a mutation check (PH-02)
- `history.history_action_registry` — the closed vocabulary as thirty-one seeded rows, `SELECT`-only
  for `prope_app`, and the first entry Prope has ever made in `GLOBAL_TABLES`
- **A total order**: `seq` as a database-assigned monotonic identity column that a caller cannot
  supply, with a test proving two events written in one transaction order stably even when their
  `occurred_at` values are byte-identical (PH-04)
- **The validating write path**: the registry loaded into ADR-0038's immutable process-lifetime
  mapping, the three-way validation (unknown action, unregistered `details` key, missing required
  reason), a dedicated refusal type, `prope_property_history_append_rejected_total`, and the proof
  that a refusal leaves the caller's transaction rolled back with no partial state (PH-05)
- The `history` half of the project-wide schema invariants — no `SECURITY DEFINER` function, no
  native enum type, no foreign key leaving the schema, every timestamp carrying a zone
- The two edits a new schema forces on Phase 1's rig: `EXPECTED_ABSENT_SCHEMAS` and the truncate
  fixture

**Fixed out of scope by ROADMAP (do not absorb):**
- `append(event)`, `read(scope, cursor, limit)` and `registered_actions()` as the three registered
  in-process seams five modules build against, `scope_prompt_id` stamping as a contract, and the
  cursor pagination that goes with `read()` — **Phase 5** (PH-03, PH-06). See D-64 for exactly where
  the line falls, because it is not where a reader of the two phase goals would first put it
- The AC-6 vocabulary equality — registry against the union of five lock files — is **Phase 5's
  assertion** (PH-06). This phase produces the derivation it will be checked against (D-60)
- Atomicity under a killed process, the route-table assertion that nothing is mounted, the
  full-corpus content inspection, and the never-deleted proof — **Phase 6** (PH-01, PH-07, PH-08,
  PH-09, PH-10)
- The other six metrics and all three alerts. Only `append_rejected_total` lands here, because
  ROADMAP success criterion 3 names it by name. The rest is Phase 6's observability set
- The five writing modules. None exists: access-control is Phase 7, provider-access Phase 10,
  prompt-registry Phase 13, evaluation Phase 16, release-control Phase 22. This phase builds what
  they will call and proves it from its own tests, exactly as Phase 2 did for `enqueue`

**Requirements:** PH-02, PH-04, PH-05.

</domain>

<decisions>
## Implementation Decisions

Numbering continues from Phase 2's D-09…D-25. Phase 3 holds D-26…D-45; this phase consumes
**D-46 through D-65** and no id outside that range. The project numbers continuously and never
restarts.

### The first new schema since Phase 1

- **D-46:** The schema, both tables, their constraints, indexes, policies, grants and the
  thirty-one-row seed ship in **one revision**, and that revision opens with
  `CREATE SCHEMA history AUTHORIZATION prope_migrate` followed by
  `GRANT USAGE ON SCHEMA history TO prope_app, prope_report`. This is the shape `0002`, `0003` and
  `0004` all use — the whole guarantee stack for a subject in one applied migration — and the
  `AUTHORIZATION` clause is load-bearing rather than decorative: ADR-0035's owner bypass is what
  exempts `prope_migrate` from the tenant policy, and it only holds if `prope_migrate` actually owns
  what the revision creates (`alembic/ddl.py:27-41`). A separate "create the seven remaining schemas
  up front" revision is rejected: a schema with no tables is a `GRANT USAGE` nothing exercises, and
  revision `0001` only created `ledger` alongside the roles because roles are cluster-level and had
  to exist first.
  **The revision's `down_revision` is not written by the planner.** Phase 3 executes before this
  phase and moves the head; the executor reads `uv run alembic heads` and wires it then. D-04 makes
  the chain linear and `tests/integration/test_migration_chain.py` asserts it, so a guessed parent
  is a red test rather than a merge revision.
- **D-47:** **`EXPECTED_ABSENT_SCHEMAS` shrinks in this phase, and Phase 1's note saying otherwise is
  now wrong.** `.planning/STATE.md` records *"Phase 7 (access) is the first phase that must shrink
  it"*; that was true when only `ledger` was planned near-term and it is not true any more — this
  phase creates `history` and is therefore first. Two edits in
  `tests/architecture/test_tenant_coverage.py`, not one: the constant drops `"history"` from seven
  entries to six, **and** `test_declared_schemas_that_do_not_exist_are_reported_not_skipped`'s
  companion line `assert tuple(existing) == ("ledger",)` becomes `("history", "ledger")` — alphabetical,
  because `LIST_EXISTING_SCHEMAS` carries `ORDER BY nspname`. The second assertion is the one a
  planner misses, because the constant is the documented one and the tuple is three words at the end
  of the same test. **This is an agent judgement made by reading the file, not a detector result.**
- **D-48:** The truncate fixture spans two schemas, and **`history.history_action_registry` is
  excluded from it by name.** `tests/conftest.py:95-98` filters `pg_tables` on
  `schemaname = 'ledger'` — the 0004 revision's claim that the rig "is not told this table's name"
  is true of the table and false of the schema. Extending the filter to `('ledger', 'history')`
  without an exclusion truncates the registry after the first test in the session, and every test
  after it fails with an unregistered action for a reason that points nowhere near the fixture.
  Re-seeding the registry inside the fixture is rejected by name: it is a second provisioning path
  for the vocabulary — the split D-02 refused — and it would let the suite pass against a
  fixture-seeded registry the migration never wrote, which is the one thing AC-6 exists to catch.
  Two consequences to state in the plan: `RESTART IDENTITY` resets the `seq` sequence between tests,
  so an ordering assertion may compare against small absolute values rather than only relative ones;
  and `CASCADE` follows D-57's foreign key, which is a second, independent reason the registry must
  not be in the truncate list.
- **D-49:** The generic invariants in `tests/architecture/test_schema_invariants.py` are
  **parameterised over both schemas rather than copied into a history-specific file.** Five of the
  eight tests there state project rules, not ledger rules — no `SECURITY DEFINER` function, no native
  enum type, no foreign key leaving the schema, every `_at`/`_from` column carrying a time zone, no
  floating-point column — and the file's `SCHEMA = "ledger"` module constant is what scopes them.
  Copying them is rejected on D-06's own grounds: a rule asserted in two files drifts, and the copy
  that stops being maintained is invisible, which is "the rule selecting for its own blind spot".
  The three genuinely ledger-specific tests (the six money columns, the `created_at`/`written_at`
  default split, the model-count drift guard pinned at six) stay where they are and stay scoped.
  Two of the five carry `ledger` in their function name and will read wrong once they run against
  `history`; renaming them is part of the edit, not a follow-up.
  **Consequence to state out loud: this phase edits a Phase 1 test file**, which is a cross-phase
  edit and needs to be visible in the plan rather than discovered in review.
  — **Reversibility:** cheap — a parameterisation is one decorator, and un-parameterising it is the
  same edit backwards.

### Append-only is a privilege, and the privilege is the product

- **D-50:** The grant matrix is written with `grant_table` from `alembic/ddl.py:97`, in its positive
  form — `REVOKE ALL … FROM PUBLIC`, then `GRANT SELECT, INSERT … TO prope_app`, then
  `GRANT SELECT … TO prope_report`. **No literal `REVOKE UPDATE, DELETE ON history.history_event
  FROM prope_app` is issued**, even though `docs/modules/property-history.lock.yml`
  `libraries_frameworks` names that exact statement. A `REVOKE` of a privilege that was never granted
  is a no-op that reads in a diff as protection, and the helper's own docstring already argues the
  positive form: *"both end in the same state and the positive form is the one a reviewer can read."*
  This is a deviation in spelling and not in effect, and it is **not** raised as an OQ for that
  reason — but the end state is what the plan must assert, not the statement: two
  `has_table_privilege('prope_app', 'history.history_event', 'UPDATE'|'DELETE')` calls returning
  false. That assertion is true under either spelling and false under neither.
  — **Reversibility:** one-way in the sense D-07 established — a later widening is blocked by
  whatever application code has come to depend on the absence, and here the thing depending on it is
  the product's central claim.
- **D-51:** `history_action_registry` is granted **`SELECT` only** to `prope_app`. ADR-0038 states
  this outright — *"the registry table is `SELECT`-only for `prope_app` … there is no user-editable
  path and no API that writes it, so there is no runtime event that could make the cache stale"* —
  so this is **derived from an ADR rather than chosen**, and it is recorded here so a planner does
  not read it as a settled preference open to trade. It is what makes ADR-0038's process-lifetime
  cache with no invalidation safe: the only writer is `prope_migrate`, the only write is a migration,
  and ADR-0031 restarts the application after migrating. If a planner disagrees, that is an OQ, not a
  quiet reversal.
- **D-52:** The privilege test is written as a **structural mirror of
  `tests/security/test_append_only_privilege.py`**, including the two things that file exists to
  teach. First, **the positive control runs inside the very transaction that will attempt the
  write** (`_refusal_text`, line 121-135): an `UPDATE` matching zero rows and an `UPDATE` the engine
  refused are the same observation from the test's side, and under RLS a history row is invisible to
  a session with no tenant context — so without the control the entire file passes against a table it
  cannot see. Second, **the mutation check is a test and not a procedure** (line 214-252): grant
  `UPDATE`, observe the refusal stop holding, revoke it in a `finally`. The plan must not treat this
  as optional polish. `price_table`'s append-only property protects a cost figure's explicability;
  `history_event`'s protects the one sentence the product is sold on, and it is the phase's first
  success criterion. Copying the shape is cheaper than rediscovering why it has that shape.

### The total order

- **D-53:** `seq` is **`bigint GENERATED ALWAYS AS IDENTITY`**, `NOT NULL`, with a `UNIQUE`
  constraint — **not** the primary key, and not `bigserial`. Three parts, each argued separately.
  *Not `bigserial`*: `bigserial` is a `DEFAULT nextval(...)`, and a default is only used when the
  caller omits the column. `prope_app` holds `INSERT`, so a hand-written or mis-generated statement
  supplying its own `seq` is accepted and the total order silently stops being total.
  `GENERATED ALWAYS` makes the engine refuse a caller-supplied value, which is the same class of
  guarantee as D-50's absent grant and belongs on the same table for the same reason. The lock file
  says "bigserial"; that names a spelling, and the property it names in the same sentence —
  "monotonic, and the ONLY sort key" — is what `GENERATED ALWAYS` implements more strictly.
  **CORRECTED at plan-critique resolution.** This paragraph originally read *"No OQ is raised for a
  strengthening that changes neither the column type (`bigint` either way) nor the observable
  behaviour"* — and the second half of that is false, which the phase's own plan set proves:
  `04-03-PLAN.md` Task 2 test 1 asserts that an `INSERT` naming `seq` with a value, attempted as
  `prope_app`, raises with `generated always` in the message. Under the lock's `bigserial` that
  statement **succeeds silently**. So this is a strengthening with an **observable behavioural
  difference** against a literal spec token, on the column the module's second success criterion rests
  on — the kind Phase 2 raised four times as OQ-018…OQ-021 rather than absorbing. **An OQ is owed**,
  naming `docs/modules/property-history.lock.yml` `data.owns → history_event → seq` and
  `docs/adr/0024-…`'s Decision block, with the conflict stated as *"the spec names a default-backed
  sequence; the build ships `GENERATED ALWAYS`, which refuses a caller-supplied value — a strengthening
  with an observable behavioural difference, asserted in
  `tests/security/test_history_seq_cannot_be_supplied.py`."* Phase 4's allocated range OQ-027…OQ-031 is
  fully consumed and OQ-022…OQ-026 belong to Phase 3, so **the id is escalated to the orchestrator in
  `deferred-items.md` §1 rather than taken from another phase's range.** The decision itself stands —
  it is the better of the two options and a `<human-check>` in plan 04-01 already puts it in front of a
  person; what was wrong was the paperwork, and the paperwork is the only thing that lets someone say
  *no, keep `bigserial` and enforce it in the writer*.
  *Not the primary key*: `id`, the `hev_`-prefixed ULID, is the primary key. It is what INT-006's
  envelope returns, what the lock's `log_fields` says is logged (*"the event's id is logged; its
  content is not"*), and what A-045 makes the identifier convention across all eight modules. A
  `bigint` surrogate key beside it would be two identities for one row, and the module would have to
  decide per call site which one it means.
  *Two properties the plan must state rather than assume*: **monotonic is not gapless** — a rolled-back
  transaction consumes sequence values and never returns them, which is correct for an order and
  wrong for a count, so nothing may infer "events lost" from a gap. And **assignment order is not
  commit order** — two concurrent transactions can take 5 and 6 and commit 6 first, so a reader
  between the two commits sees 6 without 5. Inside one transaction, which is the entire case PH-04
  and AC-4 are about, the order is exact. Across transactions it is not, and that is a live hazard
  for Phase 5's cursor pagination, which is why it is written down here rather than found there.
  — **Reversibility:** one-way once rows exist — changing the sort key of an append-only table means
  rewriting rows the application role cannot rewrite.
- **D-54:** **Exactly the twelve columns ADR-0024's schema block names, and no thirteenth.** The
  temptation is a database-stamped `written_at` beside the caller-supplied `occurred_at`, the split
  `call_record` draws — and it is refused, because `seq` already carries every ordering claim the
  module makes and `.planning/BSP-LINK.md` forbids inventing schema the spec did not declare. Each
  non-obvious column carries a **named** CHECK, so a security test can assert *which* constraint
  refused a write (`src/prope/db/metadata.py`'s naming-convention argument):
  - `occurred_at timestamptz NOT NULL` with **no default**. INT-006's envelope lists it as
    caller-carried, so the caller supplies it and `append()`'s Python signature defaults it to "now"
    when omitted — one source of the value, not two. The consequence is stated rather than
    mitigated: a caller can stamp a wrong `occurred_at`, and this phase does not defend against that,
    because A-125 forbids sorting on it and `seq` carries every order-bearing claim. A timestamp
    nobody sorts on is display and arithmetic, not evidence about sequence.
  - `actor_type` is `text` with `CHECK (actor_type IN ('user','system'))` — **never a native enum**.
    Pitfall 4 and `test_no_native_enum_type_exists_in_the_ledger_schema` are the standing rule:
    adding a value to a native enum cannot run inside a transaction block and removing one is
    impossible at any price. `domain.py`'s four `StrEnum`s mirror the CHECK sets byte-identically and
    this module's vocabularies follow that same discipline.
  - `CHECK (actor_id IS NOT NULL OR actor_type = 'system')` — the pairing rule read exactly as the
    lock states it: `actor_id` is null *only* in the system case, and a system actor with an id is
    permitted. Named so a test can say which rule refused, not merely that something did.
  - `CHECK (reason IS NULL OR char_length(reason) <= 500)` — **characters, not bytes, and a CHECK,
    not `varchar(500)`**. ADR-0053 ships a Vietnamese-only interface, so a user-authored reason is
    multi-byte and a byte cap would silently be a ~170-character cap for the only users the MVP has.
    A named CHECK is also droppable and re-addable, where a type change on an append-only table is a
    rewrite the application role cannot perform.
- **D-55:** **All four declared indexes ship with the table, in this phase**, not with the reader
  that uses them. Three back `read()`'s three scopes and one backs A-126's hand-run Success SQL, so
  "wait until there is a query" would leave Phase 5 adding four indexes to a table that already
  holds rows, on the one table in Prope that only ever grows (A-121). The number is the lock's four,
  argued rather than accepted: `(workspace_id, scope_prompt_id, seq DESC)` is the Activity read and
  is the reason A-119 exists at all; `(workspace_id, target_type, target_id, seq DESC)` is one
  subject's trail; `(workspace_id, actor_id, seq DESC)` is a person's actions and is what makes AC-9
  answerable after a tombstone; `(workspace_id, action, seq)` is the Success queries. **A fifth is
  not invented and none of the four is dropped** — in particular there is no index on `details`,
  because no query in any lock file reads a details key (see D-58).

### The closed vocabulary

- **D-56:** `history.history_action_registry` carries **no `workspace_id`** and becomes the **first
  entry Prope has ever made in `GLOBAL_TABLES`**, with its written reason. Two arguments, and the
  second is the decisive one. The vocabulary is closed globally by A-120, so a tenant-scoped registry
  would be thirty-one rows per workspace and "closed at thirty-one" would become a per-tenant claim
  nobody could assert once. And **under ADR-0035's inversion a tenant-scoped registry returns zero
  rows to a caller with no tenant context** — which is precisely INT-008's consumer, a CI test.
  AC-6 would then compare an empty set against an empty set and pass, vacuously, forever. A rule
  whose failure mode is a green test is the exact shape ADR-0045 was written about.
  Consequence: `test_every_global_table_exemption_carries_a_written_reason` starts guarding a real
  entry instead of an empty dict, and the ADR-0045 coverage walk skips the registry by exemption
  rather than by accident. The reason string is a sentence a reviewer can disagree with, per the
  file's own rule.
  — **Reversibility:** costly — every module that later reads the vocabulary is written against a
  table with no tenant column, and adding one means seeding per workspace.
- **D-57:** The closed vocabulary is enforced by a **composite foreign key**
  `history_event (action, target_type) → history_action_registry (action, target_type)`, with the
  registry keyed on `action` and carrying `UNIQUE (action, target_type)` to receive it. This is
  Prope's standing "build database-first" posture applied to the one table whose editability would
  falsify the pitch, and it buys two things a Python check alone cannot: an unregistered action
  cannot enter the table through a hand-written statement — the repair-script path ADR-0025 names as
  the realistic threat — and an event cannot pair a registered action with a *wrong* target type,
  which turns a whole class of caller bug into an engine refusal.
  Three rejected alternatives. **A `CHECK (action IN (…31 literals…))`** duplicates the vocabulary in
  a second place, and adding the thirty-second action becomes a `DROP`/`ADD CONSTRAINT` with a
  validating scan over an append-only table that only grows — where ADR-0038's *"adding an action is
  safe by construction"* assumes a plain `INSERT` into the registry. **No constraint at all, Python
  only** leaves the vocabulary a convention on the table where "convention" is the word ADR-0025
  exists to remove. **A `BEFORE INSERT` trigger** is refused for the reasons in D-62.
  The cross-tenant concern that killed foreign keys in `ledger` does not apply and the reason must be
  stated rather than assumed: `test_no_foreign_key_leaves_the_ledger_schema` refuses keys that *leave
  a schema*, because PostgreSQL's referential-integrity checks bypass row security and a key into
  another tenant-scoped table is a covert channel. This key is intra-schema and its target is global
  and identical for every workspace, so there is nothing to infer from the check succeeding. The
  history counterpart of that test still asserts no key leaves `history` — this one does not.
  — **Reversibility:** cheap to drop, costly to add later — one line either way today, a validating
  scan over the largest-and-only-growing audit table once the pilot has run.
- **D-58:** `details` is **`jsonb NOT NULL DEFAULT '{}'::jsonb`**. Revision `0003` made the opposite
  call one schema over — `call_body.request_body` is `text`, *"not jsonb… jsonb would reject a
  malformed body, which is exactly the body worth keeping"* — and the inversion here is the whole
  argument: a `details` payload is assembled by our own code out of allow-listed keys and never
  contains provider content, so a malformed payload is a caller bug and refusing it at the engine is
  right, where a malformed provider body is evidence and refusing it destroys the thing being kept.
  `NOT NULL DEFAULT '{}'` because `user_tombstoned`'s `detail_keys` are deliberately empty and NULL
  versus `{}` would be two spellings of "no details" — the allow-list check would then have two
  branches and one of them would eventually be the one nobody wrote. **No GIN index** (D-55).
- **D-59:** The registry's shape **and its thirty-one-row seed ship in the same revision as the
  tables**. `detail_keys` is `text[] NOT NULL` (possibly empty) rather than jsonb or a joined string,
  because it is a set of identifiers and the allow-list check is a set operation. `requires_reason`
  is `boolean NOT NULL`. `writing_module` is `text NOT NULL` with a `CHECK` over the five writer
  names, because the five are a genuinely closed set and the lock declares `writing_module` a bounded
  metric label — a typo there mis-attributes an event's writer in a Prometheus series, which is the
  quietest kind of wrong.
  Seeding in a *later data revision* is rejected because ADR-0038's entire safety argument is a deploy
  ordering — *"the row exists, then the code that names it starts"* — and that ordering only exists
  if the seed is a migration. Seeding **from application code at startup** is rejected twice over: it
  is a second provisioning path, and D-57's foreign key means the registry must be non-empty before
  the first event can be written, so a startup seed makes the first append after a fresh deploy a
  race. Consequence, stated plainly: the thirty-second action is a new revision plus a restart, and
  ADR-0038 already records that sharp edge.
- **D-60:** **The thirty-one names are derived here by reading the five writing modules' `outputs`
  blocks, and the derivation is recorded so Phase 5's AC-6 has a written baseline rather than a
  re-derivation.** The union is **exactly 31 with no adjustment**: `user_tombstoned` is already inside
  `access-control.lock.yml` `outputs` (added 2026-08-09 by ADR-0054), so nothing is added by hand and
  no rounding-off was needed.

  | Writer | Count | Actions |
  |---|---|---|
  | prompt-registry | 5 | `property_created`, `revision_created`, `owner_changed`, `access_level_changed`, `retired` |
  | release-control | 8 | `revision_submitted`, `revision_approved`, `revision_changes_requested`, `revision_released`, `revision_restored`, `revision_break_glass_released`, `release_withdrawn`, `review_task_closed` |
  | evaluation | 4 | `eval_suite_updated`, `eval_run_started`, `eval_run_completed`, `eval_run_interrupted` |
  | provider-access | 4 | `provider_configured`, `provider_updated`, `provider_disabled`, `credential_rotated` |
  | access-control | 10 | `workspace_created`, `member_added`, `member_removed`, `role_assigned`, `role_revoked`, `access_granted`, `access_revoked`, `api_key_created`, `api_key_revoked`, `user_tombstoned` |
  | **Total** | **31** | |

  `requires_reason` is true for exactly three — `revision_break_glass_released`, `release_withdrawn`,
  `revision_changes_requested` — stated identically in the lock file, in `release-control.lock.yml`
  and in INT-006, so it is the one registry column that is fully determined by the specs.
  **The count itself is contested in the authorities.** ADR-0024's title, its Context table (which
  omits `user_tombstoned`) and its Consequences bullet all say 30; line 53 of the same ADR says 31.
  `interfaces.md` says 31 in INT-006's header and INT-008's row, and 30 in INT-006's validation bullet
  and INT-008's rationale. A-120 says 31 in its Statement and 30 in its Rationale. **Adopt 31** —
  the lock file, ADR-0038, ADR-0054, `tech_stack.md` and this derivation all agree — and raise
  **`OQ-027`** naming the exact lines. The spec is not edited to agree.
- **D-61:** **`target_type` and `detail_keys` are derived, not read, and the two gaps are not the
  same size.** `target_type` is declared a "closed enumeration" by ADR-0024 and A-122 and is
  enumerated nowhere; the only member stated anywhere in `docs/` is `target_type = user`, in
  A-151/ADR-0054. It is derivable from the action names plus A-120's rule and its cost of being wrong
  is bounded — nothing joins on it (A-122 forbids the key), AC-6 asserts only the action names, and
  D-57 makes the *pairing* an engine fact even though the vocabulary is a judgement. So it is
  derived, seeded, and recorded. Thirteen values result: `property`, `revision`, `release`,
  `review_task`, `eval_suite`, `eval_run`, `provider_config`, `workspace`, `member`, `role`,
  `prompt_grant`, `api_key`, `user`.
  `detail_keys` is **not** derivable. **CORRECTED at plan-critique resolution: declared keys exist in a
  lock file for SEVEN of thirty-one actions, not three.** This paragraph originally said three, and the
  omission is `evaluation.lock.yml:94-97`, which declares that `eval_suite_updated`,
  `eval_run_started`, `eval_run_completed` and `eval_run_interrupted` each carry *"the prompt_id,
  version_id, suite_version, and actor (A-014)"* — `prompt_id` maps to the `scope_prompt_id` column and
  `actor` to `actor_id`, but **`version_id` and `suite_version` are not columns `history_event` has, so
  they are `details` keys, declared today, in a lock file that exists.** The seven are:
  `revision_released` (`version_id`, `previous_version_id`, `break_glass`), `role_assigned` (`role`,
  `grantee_user_id`), `user_tombstoned` (deliberately empty, ADR-0054), and the four `eval_*` actions
  (`version_id`, `suite_version`). The other twenty-four belong to
  modules that will not exist for another six to eighteen phases, and a key invented now is a guess
  the real writer discovers is wrong at the moment its transaction fails. **Seed two non-empty sets —
  `revision_released` and `role_assigned` — and leave the other twenty-nine empty**, which is the
  strictest available position: any key at all on those actions is refused, loudly, which is A-124's
  friction landing exactly where A-124 says it should. **The four `eval_*` actions are seeded empty
  deliberately rather than by oversight**, because Phase 16 is the module that will write them and it
  should register them with its own test; the accepted cost, named here rather than discovered twelve
  phases later, is that **Phase 16 writing `eval_run_started` with `details={"version_id": …}` against
  this seed is refused with `unknown_detail_key`.** That handover is recorded in `deferred-items.md` §5
  with Phase 16 named, and `OQ-029` — which carries the same three-of-thirty-one count in its own text
  — should absorb the correction when it is adjudicated. It is not edited from here: `docs/` is
  read-only to this phase beyond creating an OQ file.
  Two findings that fall out of the derivation and are raised rather than smoothed:
  four names do not satisfy A-120's own `<target_type>_<past participle>` rule against their real
  target — `retired` (no target type at all), `owner_changed` and `access_level_changed` (a field,
  not a subject), and `access_granted`/`access_revoked` (whose subject is the `prompt_grant` row) —
  and A-119's *"six different `target_type`s"* for the prompt-scoped set derives as **seven**.
  Seed the lock files' literal names, because AC-6 is an asserted equality and A-120 is prose, and
  raise **`OQ-028`** (the naming rule) and **`OQ-029`** (the missing enumerations, the seven-vs-six
  count, and the unowned obligation that each writing module must later register its own keys).
  — **Reversibility:** one-way after the pilot — A-120's own note says a rename before data exists is
  cheap and after it is an `UPDATE` on a table the application role cannot update.
- **D-62:** **`requires_reason` and the `details` allow-list are enforced in Python, at one
  validation site, and the asymmetry with D-57's engine-enforced half is stated rather than hidden.**
  Neither can be a CHECK: a CHECK cannot reach another table, and the registry is where both rules
  live. The shape that would work is a `BEFORE INSERT` trigger doing the lookup, and revision `0004`
  already refused a trigger once — for the A-055 body guard — on three grounds. **Only two of those
  three transfer, so the argument is made freshly rather than cited.** The volume argument does not
  apply: `history_event` takes one row per state change, not one per gateway call, so a per-row
  registry probe is affordable here where it was not there. What does transfer is that
  `.planning/BSP-LINK.md` forbids inventing schema the spec did not declare, and — decisively —
  ADR-0023 rejected triggers for this module by name, on the grounds that they *"put the audit
  vocabulary in migrations rather than in a module, where the allow-list of ADR-0024 cannot run."*
  The `details` half genuinely cannot be a trigger without reimplementing the allow-list in PL/pgSQL,
  and splitting three validations across two languages so that two of them can be triggers is worse
  than either whole.
  **The absence is therefore asserted, not assumed**, the way `0004` asserted the A-055 boundary: a
  test proves that a hand-written `INSERT` as `prope_migrate`, carrying an unregistered `details` key
  and no reason on an action that requires one, **succeeds** — so a later phase inherits a recorded
  boundary rather than a belief about where the guarantee lives.
- **D-63:** The refusal is a **dedicated exception type**, deliberately **not** a `ValueError`.
  `src/prope/call_ledger/writer.py` raises `ValueError` throughout and that is right there, because
  its callers are the drain and its own tests. It is wrong here: INT-006 says *"a caller that catches
  this has broken the product's central claim"*, and five modules will wrap `append()` in code that
  validates its own inputs — an `except ValueError` around a request body would swallow the audit
  log's refusal and commit the state change without its event, which is the module's most serious
  failure mode arriving by accident. A named type makes catching it a deliberate act that reads wrong
  in review. Its reason vocabulary is a `StrEnum` whose members are **byte-identical to the metric's
  declared label set** — `unknown_action`, `unknown_detail_key`, `missing_reason`, the three the lock
  file names and no fourth — the same discipline `domain.py` keeps between its enums and the database
  CHECK sets. **A fourth reason is a lock-file change, not a new enum member.**

### Where this phase stops and Phase 5 begins

- **D-64:** **The validating write path lands in Phase 4; the three registered seams land in Phase 5.**
  A reader of the two phase goals would put `append()` entirely in Phase 5 — its goal names the
  function — and that reading makes this phase's third success criterion unprovable, which ORCHESTRATION
  §9 forbids. PH-05 is *this* phase's requirement and SC3 names a raise, a rolled-back caller
  transaction with no partial state, and a counter increment with a reason; none of the three is
  observable without a path that validates and writes. So the line is drawn by capability, not by
  filename:
  - **Phase 4 builds** the registry loader (ADR-0038's immutable mapping, loaded from a session),
    the three-way validator, the refusal type and its reason vocabulary, the rejection counter, and
    an internal insert that runs on a session handed to it. Its tests drive that path directly and
    open the transaction themselves, which is also how the "inside the caller's transaction"
    property gets its first assertion.
  - **Phase 5 builds** `append(event)` as INT-006's registered signature with `scope_prompt_id` as a
    contract rather than a column, `read(scope, cursor, limit)` with its cursor semantics, and
    `registered_actions()` — plus AC-6's equality and the wiring of the registry cache into `app` and
    `worker` at process start.
  The plan must say out loud that Phase 4 ships a write path under a name no downstream spec uses,
  and that Phase 5 renames or wraps it. That is the honest cost of the split, and it is smaller than
  a phase whose stated criterion cannot be tested inside it.
- **D-65:** The package is `src/prope/property_history/` (D-01's one-subpackage-per-bounded-context
  shape), and three absences in it are load-bearing.
  **It does not import FastAPI, anywhere, at any depth.** The lock file makes this structural rather
  than asserted — *"not having the framework in scope is what makes that assertion cheap to keep
  true"* — and PH-07 (Phase 6) is the test that reads it back.
  **It does not touch `src/prope/app.py` or `src/prope/worker.py`.** D-13's explicit central
  composition means a module appears in those two files because somebody typed it, and this module
  never does; ADR-0038's process-start cache load is Phase 5's wiring, not this phase's. That also
  removes the only file-level collision this phase could have had with Phase 3, which matters under
  ORCHESTRATION §7's serial-execution rule.
  **Its counter lives in the module, not in `src/prope/observability.py`.** That module's docstring
  scopes itself to "The Phase 2 counters, and only those" and every metric in it is
  `prope_call_ledger_*`. But `LOGGABLE_FIELDS` — the A-046 allow-list in the same file — is
  project-wide, and extending it here surfaces a real collision the plan must resolve rather than
  paper over: **`reason` is already in that allow-list**, where for call-ledger it is a closed
  vocabulary token (`unroutable | nacked | timeout`, and `CeilingReason`), and for property-history
  it is user-authored free text that the lock file says must **never** be logged. One flat set keyed
  on field name cannot hold "loggable from call-ledger, forbidden from property-history", and Phase
  2's own note — *"an allow-list with a field outside it is an allow-list somebody has already
  stopped believing"* — is what stops the easy answer of quietly forking a second set.

### Claude's Discretion

Deliberately left open for the researcher and planner. They are **open, not decided** — resolve them
from the lock file, the interfaces registry and the phase's success criteria, and **state the
resolution in the plan**:

- **How the `LOGGABLE_FIELDS` collision on `reason` is resolved** (D-65) — a per-module allow-list, a
  qualified key, a rename of one side, or a rule that the allow-list is a floor and a module may
  subtract. Whatever is chosen must keep the property assertable in one place.
- **Whether the rejection counter's three-reason `StrEnum` lives in `domain.py` or beside the
  counter**, and whether the byte-identity between the enum and the label set is asserted by a test
  or by proximity. `domain.py`'s precedent is proximity plus a docstring; the lock's alert makes every
  increment a page, which argues for the test.
- **The `id` generation site.** `python-ulid` is pinned and unused; whether the `hev_` prefix is
  assembled in the module or in a shared identifier helper is open, and Phase 7 onward will want the
  same for six more prefixes.
- **Whether `scope_prompt_id` gets a column-level constraint in this phase at all.** It is nullable
  by design and the registry knows which actions are prompt-scoped, so a data-driven check is
  possible; the lock routes the enforcement to a *metric*
  (`prope_property_history_null_scope_prompt_total`) rather than a refusal, deliberately, because
  the failure is silent-but-detectable rather than wrong. Decide which, and if it is the metric, note
  that the metric itself is Phase 6's.
- **`prope_report`'s read grants on both tables** — `grant_table`'s `report_select` defaults to true
  and revision `0004` took the default with a written reason. A-126's hand-run Success SQL reads
  `history_event` across workspaces under `prope_report` (ADR-0037), which argues the same way, but
  the argument should be made rather than inherited.
- **How many OQs the three vocabulary findings become.** D-60, D-61 allocate `OQ-027`, `OQ-028` and
  `OQ-029` as three files; whether the naming rule and the missing enumeration are really one
  question is a planner's call. All three conflicts must be raised.
- **The exact `GLOBAL_TABLES` reason string** (D-56). It is the first one ever written and it sets
  the register for the seven modules that follow.
- **Whether the derivation table in D-60 is also committed as a fixture** the Phase 5 AC-6 test reads,
  or re-derived there from the lock files. Re-deriving is stronger and slower; a fixture is a third
  copy of a list AC-6 exists to stop copying.
- **Test file placement** across `tests/security/`, `tests/architecture/`, `tests/unit/` and
  `tests/integration/`, against the lock's `test_ref` paths — several of which name files
  (`tests/unit/test_unregistered_detail_key_fails_the_transaction`) whose content needs a live
  database and therefore is not a unit test as this repo uses the word.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

These are authoritative and read-only. Per `.planning/BSP-LINK.md` and ORCHESTRATION §1: do not edit
anything under `docs/`, with the single exception of **creating** an `OQ-NNN` file. A spec that
disagrees with the code is information — raise an `OQ-NNN` naming the exact field and the conflict;
do not patch the spec to agree. **Three such conflicts are already known and are D-60 and D-61
above, allocated `OQ-027`, `OQ-028` and `OQ-029`.**

### The module spec and the seam registry — read first
- `docs/modules/property-history.lock.yml` — `data.owns` (**both tables' full field notes; the
  `seq`/`id`/`details`/`reason`/`scope_prompt_id` paragraphs are the schema's actual specification**),
  `scope.in_scope`, `scope.non_goals` (*"Exposing any HTTP route — not a history endpoint, not
  /healthz, not /readyz"*), `inputs` (the five writers' event lists — **this is D-60's source**),
  `apis.exposes` (the three seams and the NO HTTP surface clause), `security_requirements` (T-021
  through T-024), `failure_modes` (rows 2, 4 and 5 are this phase's), `acceptance_criteria` AC-2,
  AC-4, AC-5, `test_plan.unit` / `.security`
- `docs/architecture/interfaces.md` — **INT-006** (`append(event)`: the envelope's ten caller-carried
  fields, *"raises, and the raise is the mechanism"*, the three validations performed here so no
  caller restates them, and the three `requires_reason` actions), **INT-007** (`read()` — Phase 5's,
  read for the ordering and cursor properties this phase's indexes must serve), **INT-008**
  (`registered_actions()` returns **four** fields where the lock's `apis.exposes` names three —
  `requires_reason` is in one and not the other; a Phase 5 detail, noted so it is not discovered
  there)
- `.planning/BSP-LINK.md` — the phase → spec index and the "Out of bounds" rules
- `.planning/ORCHESTRATION.md` — §3's standing engineering facts, §5's out-of-bounds list, §6's
  decision-checkpoint policy under `mode: yolo`

### The three guarantees this phase makes real
- `docs/adr/0025-append-only-is-a-database-privilege-not-a-convention.md` — the `INSERT`+`SELECT`
  grant, why a `BEFORE UPDATE` trigger and a repository convention are both rejected, why a hash
  chain is the wrong guarantee at the wrong price, and the sentence that makes this the phase's first
  criterion: *"a log the application can rewrite is a Sheet with better indexing"*
- `docs/adr/0024-one-event-schema-with-a-registered-payload.md` — the twelve-column schema block,
  the naming rule, the payload allow-list, `scope_prompt_id`, and **the rejection of "sort by
  `occurred_at` with a tiebreak on id"**, which is the argument D-53 implements. Note its Context
  table lists 30 and omits `user_tombstoned` — see `OQ-027`
- `docs/adr/0023-property-history-is-a-library-in-the-callers-transaction.md` — no process, no port,
  no route; the append is a function call on the caller's connection; **triggers rejected by name**,
  which is D-62's decisive citation; and the condition under which the decision expires
- `docs/adr/0038-the-action-registry-is-cached-for-the-process-lifetime.md` — the immutable mapping,
  no TTL and no invalidation, `SELECT`-only for `prope_app` (D-51), *"adding an action is safe by
  construction"* and the one operational sharp edge it creates
- `docs/adr/0054-a-departing-person-is-tombstoned-never-deleted.md` — why `user_tombstoned` exists,
  why its `detail_keys` are empty and its `requires_reason` false against the house style, and why
  none of it costs this module anything

### Tenancy, roles, and the enforcement pattern
- `docs/adr/0035-tenant-isolation-is-a-database-policy.md` — deny-by-default,
  `SET LOCAL app.workspace_id`, `USING` **and** `WITH CHECK`, and the owner bypass D-46's
  `AUTHORIZATION` clause rests on
- `docs/adr/0045-every-table-is-tenant-scoped-unless-declared-global.md` — the inverted coverage
  walk, and `GLOBAL_TABLES` as an entry with a written reason a reviewer can disagree with. **D-56
  writes the first one**
- `docs/adr/0027-one-database-one-schema-per-module-two-roles.md` — schema `history`; the role split
- `docs/adr/0037-a-third-role-reads-across-workspaces.md` — `prope_report`, and A-126's cross-workspace
  Success SQL running under it rather than under the one role that can delete a history row

### Vocabulary, ordering, and the payload — the assumptions that are the actual spec
- `docs/brainstorm/assumptions/A-125.md` — order is a sequence, never a timestamp, and *why*:
  approve-and-release writes two rows in one transaction. This is PH-04 in one page
- `docs/brainstorm/assumptions/A-120.md` — the naming rule and the closed count. **Its Statement says
  31 and its Rationale says 30** — see `OQ-027`; and four names do not satisfy the rule — `OQ-028`
- `docs/brainstorm/assumptions/A-124.md` — the per-action key allow-list, the two declared examples,
  and why a deny-list was rejected
- `docs/brainstorm/assumptions/A-122.md` — `(target_type, target_id)` with no foreign key, and the
  three reasons in order of strength. **The reason D-57's key is intra-schema only**
- `docs/brainstorm/assumptions/A-119.md` — `scope_prompt_id`, and the *"six different `target_type`s"*
  count that derives as seven — see `OQ-029`
- `docs/brainstorm/assumptions/A-121.md` — nothing expires, no retention setting, no job. The absence
  of a deletion path is part of the guarantee
- `docs/brainstorm/assumptions/A-003.md`, `A-045.md` — RFC 3339 UTC, `hev_`-prefixed ULIDs

### Known gaps this phase must plan around
- `.planning/research/PITFALLS.md` §1 — sixteen acceptance criteria owed and never written as rows.
  **property-history is not in that table**, which is worth knowing rather than assuming: this
  module's ten criteria are all real rows with `test_ref`s. Read it anyway for the access-control row,
  because one of its three owed criteria is *"the `SECURITY DEFINER` set is exactly the sanctioned
  functions"* — the `history` half of which this phase asserts under D-49
- `.planning/research/PITFALLS.md` §2 — eight criteria that assert against replaced infrastructure.
  **None is property-history's.** Recorded so a planner does not go looking for a restatement that
  does not exist
- `.planning/research/PITFALLS.md` §5 — *"the cross-module route-table tests cannot actually run
  before phase 23"*, and **PH-07 is named in it explicitly**. That is Phase 6's problem, not this
  phase's, but it is why D-65 makes the FastAPI absence structural: an import that cannot happen needs
  no route table to prove it
- `.planning/phases/01-data-model-pricing-and-retention/01-CONTEXT.md` — D-01 through D-08, and in
  particular D-06's argument for the coverage walk that D-47 and D-56 both act on
- `.planning/phases/02-seams-enqueue-the-broker-drain-and-the-ceiling/02-CONTEXT.md` — D-09 through
  D-25. D-13 (explicit central composition), D-17 (a decision derived from an ADR, labelled as such —
  the model for D-51 here) and D-19 (call-ledger's seams open their **own** transaction, which is the
  posture this module must **not** copy)
- `.planning/STATE.md` — the Phase 01 accumulated-context line naming Phase 7 as the first to shrink
  `EXPECTED_ABSENT_SCHEMAS`. **D-47 supersedes it**; the plan should say so where a reader of STATE
  would otherwise trust it

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `alembic/ddl.py` — **`assume_migrate_role()`, `reset_role()`, `enable_tenant_rls()`,
  `grant_table()`.** Four helpers and one constant, and the file's docstring states the pattern this
  phase inherits: per-kind greppability lives in the helper names, so *"every tenant policy in the
  project is an `enable_tenant_rls` call and every grant line is a `grant_table` call"*. The
  `enable_tenant_rls` docstring (lines 56-86) argues four tokens that this phase must not re-derive:
  `ENABLE` not `FORCE`, the two-argument `current_setting` that returns NULL instead of raising,
  **no cast** (workspace ids are `wsp_`-prefixed ULIDs, not UUIDs — Phase 1 OQ-A), and `WITH CHECK`
  written out. `history_event.workspace_id` is `text` and the predicate compares text to text.
- `alembic/versions/0004_workspace_retention.py` — the most recent revision and the closest template.
  Its docstring is the density bar: a declared deviation argued at the point of use, a stated
  consequence (`expires_at` is never rewritten), and — at lines 57-81 — **a refused database trigger
  with three numbered reasons and an asserted absence in place of it**. D-62 is the same move made
  again with a freshly-checked argument, because only two of those three reasons transfer.
- `alembic/versions/0003_ledger_tables.py` — how a table's whole guarantee stack reads in one
  revision: `CREATE TABLE` as a module-level string constant with per-column comments carrying the
  *why*, then indexes, then `enable_tenant_rls` per table, then `grant_table` per table with the
  privilege set argued in a comment. Line 252's comment (*"No UPDATE: bodies are written once and
  deleted"*) is the register D-50's grant comment should match.
- `alembic/versions/0001_roles_and_schemas.py:62-63` — `CREATE SCHEMA ledger AUTHORIZATION
  prope_migrate` followed by `GRANT USAGE ON SCHEMA ledger TO prope_app, prope_report`. The two lines
  D-46 repeats for `history`, and the `AUTHORIZATION` clause's stated reason.
- `tests/security/test_append_only_privilege.py` — the whole file is D-52's template.
  `_refusal_text` (121-135) is the positive-control-inside-the-attempting-transaction helper;
  `test_the_append_only_refusal_has_teeth` (214-252) is the grant/observe/revoke-in-`finally`
  mutation check. Its module docstring states the reason both exist: *"An `UPDATE` that matched zero
  rows and an `UPDATE` the engine refused are both 'nothing changed' from the test's side."*
- `src/prope/db/session.py` — `workspace_transaction(sessionmaker, workspace_id)`. The only place a
  tenant identifier reaches SQL, bound via `set_config` and never interpolated. **This module's
  relationship to it is the opposite of call-ledger's**: `append()` runs inside a transaction someone
  else opened, so the module never calls this helper in production — its *tests* do, standing in for
  the callers that do not exist yet.
- `src/prope/db/metadata.py` — the one shared `MetaData` with **no default schema** and the
  `NAMING_CONVENTION` that makes every constraint name deterministic. Its docstring gives the reason
  D-54 leans on: *"a security test can assert which constraint refused a write rather than only that
  something did."* `history` tables declare `schema="history"` explicitly, per its Pitfall 11 note.
- `src/prope/call_ledger/domain.py` — four `StrEnum` vocabularies whose members are *"byte-identical
  to the database CHECK sets"*, with a native PostgreSQL `ENUM` rejected by name (Pitfall 4). D-54's
  `actor_type` and D-63's rejection reasons follow this exactly.
- `src/prope/observability.py` — `LOGGABLE_FIELDS`, the A-046 positive allow-list, and five
  `prope_call_ledger_*` counters. **`reason` is already in the allow-list** with call-ledger's
  closed-vocabulary meaning; D-65 names the collision that creates.
- `pyproject.toml` — `pydantic==2.13.4` and `python-ulid==4.0.1` are pinned and, for this module,
  still unused. The lock names pydantic v2 as the `details` validator and python-ulid as the `hev_`
  source. **This phase adds no dependency**; everything it needs is already pinned.

### Established Patterns

- **Build database-first.** The migration carries the guarantee — constraint, privilege, policy,
  grant, trigger — and the application code is what the guarantee protects. This module is the
  purest instance in the project: D-50's absent grant *is* PH-02, and no application code is
  involved in it at all.
- **Assert against the live engine, not the driver.** D-07's REVOKE test, D-08's zero-rows test,
  D-06's coverage walk and D-22's broker container are four instances. D-50, D-52 and D-57 are three
  more.
- **A refused mechanism gets its absence asserted.** Revision `0004` refused the A-055 trigger and
  wrote `tests/security/test_eval_no_body_boundary.py` to prove *both* halves — the write path
  refuses, and a hand-written `INSERT` as `prope_migrate` succeeds. D-62 owes the same pair.
- **Never zero, and no fourth state.** `write_records` has no default branch and raises rather than
  inventing a figure. Here the analogue is D-63's three reasons and no fourth, and D-58's single
  spelling of "no details".
- **Alembic is one linear hand-written chain** (D-04), autogenerate output never trusted because it
  cannot see policies, grants or triggers. `test_migration_chain.py` asserts linearity, which is why
  D-46 refuses to name a parent.
- **Module docstrings carry the *why* at length.** `session.py`, `metadata.py`, `observability.py`
  and every revision under `alembic/versions/` are written that way and reviewers check it.

### Integration Points

- **`history` is the first schema added since `ledger`, and two Phase 1 files are told about a schema
  by name.** `tests/architecture/test_tenant_coverage.py` (`EXPECTED_ABSENT_SCHEMAS`, and the
  `assert tuple(existing) == ("ledger",)` companion) and `tests/conftest.py:95-98`
  (`schemaname = 'ledger'`). Revision `0004` proved a new *table* is adopted for free; a new *schema*
  is not, and that difference is exactly what D-47 and D-48 exist for.
- **`tests/architecture/test_no_sql_interpolation.py` adopts this module for free and correctly.** It
  `rglob`s `src/prope/` and requires every `text(...)` argument to be a plain string constant, with
  an empty `ALLOWED` list. Nothing in this phase needs an exception — but a registry seed assembled
  by joining thirty-one names into one statement *would* need one, which is a reason to write the
  seed in the migration (D-59) where the gate does not reach, rather than in `src/`.
- **`test_schema_invariants.py` does not adopt it for free**: `SCHEMA = "ledger"` is a module
  constant and `len(declared) == 6` is a hardcoded count of call-ledger's tables. D-49 parameterises
  the five generic tests and leaves the four specific ones alone.
- **No inbound or outbound module edges, and this is the module where that is the point.**
  `dependencies: []`, `outputs: []`, `apis.consumes: []` — the only empty consumes list in Prope.
  `workspace_id`, `actor_id` and `target_id` are values, not foreign keys (A-122), which is what
  makes ADR-0054's tombstone-and-survive free. The only foreign key in the whole module is D-57's,
  and it points at the module's own second table.
- **`src/prope/app.py` and `src/prope/worker.py` are untouched by this phase** (D-65). Under
  ORCHESTRATION §7 those are two of the three files that force serial execution; this phase touching
  neither means its only shared-file contact with Phase 3 is `tests/conftest.py`, and D-48's edit
  there is additive.
- **Standing environment fact:** Windows host. `docker` is not on the default bash PATH — a shell
  driving it must first `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`.
  testcontainers reaches the daemon without PATH help, so `uv run pytest` needs no PATH change.
  `uv run ruff format --check` fails repo-wide on the pre-existing `line-length` disagreement
  (Broken Window #1); `ruff check` is the gate and `ruff format --check` is not.

</code_context>

<specifics>
## Specific Ideas

- **The REVOKE is the entire requirement, and there is no application code in it.** PH-02 is proven or
  disproven by two `has_table_privilege` calls and a refused statement. Everything else this phase
  builds is what that privilege protects. A plan that spends its weight on the validator and treats
  the grant matrix as a line in a migration has inverted the phase.

- **A positive control is not test hygiene here; it is the difference between a test and a
  decoration.** `history_event` is RLS-scoped, so a session with no tenant context sees zero rows and
  a refused `UPDATE` is indistinguishable from an `UPDATE` that matched nothing. Phase 1 learned this
  the hard way enough to write it into a module docstring. The seeded row must be asserted visible
  *inside the transaction that then attempts the write*, and the mutation check must actually restore
  the grant and watch the refusal stop holding.

- **`bigserial` is a default, and a default is advice.** The whole of PH-04 rests on `seq` being
  assigned by the engine and only by the engine, and `prope_app` holds `INSERT`. `GENERATED ALWAYS AS
  IDENTITY` refuses a supplied value; `bigserial` accepts it silently. This is the same reasoning as
  ADR-0025's — the guarantee belongs in the authorisation layer, not in the application declining to
  exercise a capability it has.

- **Monotonic is not gapless, and assignment order is not commit order.** Inside one transaction —
  the entire case PH-04 and AC-4 are about — `seq` is exact. Across concurrent transactions a reader
  can see 6 before 5 exists, which is a live correctness hazard for Phase 5's cursor pagination and
  is invisible in a single-threaded test. Naming it here is what stops Phase 5 discovering it in a
  flaky test at 2am.

- **The registry is global, and if it is not, AC-6 passes by seeing nothing.** A tenant-scoped
  `history_action_registry` returns zero rows to `registered_actions()`'s actual consumer — a CI test
  with no tenant context — and an equality between two empty sets is green forever. ADR-0035's
  inversion is a feature everywhere in Prope and a trap on exactly this one table.

- **The truncate fixture will eat the seed.** `TRUNCATE ... RESTART IDENTITY CASCADE` over every table
  in the `history` schema removes the thirty-one migration-seeded rows after the first test, and
  `CASCADE` reaches `history_event` through D-57's foreign key. The failure surfaces as "every test
  after the first one says the action is unregistered", which points at the validator and not at the
  fixture. Exclude the registry by name, and do not re-seed in the fixture.

- **`details` is jsonb here for the same reason `request_body` is text there.** Revision `0003`
  refused jsonb because a malformed provider body is exactly the body worth keeping. A malformed
  `details` payload is a caller bug on a column our own code assembles from allow-listed keys, so the
  engine refusing it is right. The two decisions look contradictory and are one rule applied twice.

- **Three validations, two enforcement layers, and the seam between them stated out loud.** The
  action/target-type pair is refused by the engine (D-57). The `details` allow-list and
  `requires_reason` are refused in Python (D-62). That asymmetry is a decision, not an accident, and
  the way it is kept honest is a test proving a hand-written `INSERT` bypassing the module *succeeds*
  — the same move revision `0004` made for A-055.

- **`ValueError` is the wrong exception on this one function.** Five modules will call `append()` from
  inside code that validates its own request bodies. INT-006 says catching the refusal breaks the
  product's central claim; a `ValueError` is the exception a caller catches by habit, without ever
  deciding to.

- **This phase's third criterion cannot be tested unless a write path exists, so one is built here.**
  ROADMAP puts `append()` in Phase 5 and PH-05 in Phase 4. D-64 resolves it by capability rather than
  by name, and the plan must say plainly that Phase 4 ships a path under a name no downstream spec
  uses and Phase 5 wraps it. ORCHESTRATION §9 forbids the alternative: *"a red test is never
  expected."*

</specifics>

<deferred>
## Deferred Ideas

Two, both raised while deriving the vocabulary and both pushed out with a named owner:

- **Each writing module must register its own `detail_keys`, and no phase owns that obligation.**
  D-61 seeds the three declared sets and leaves twenty-eight actions with an empty allow-list, which
  is the strict and correct position. But "prompt-registry's phase adds prompt-registry's keys" is
  written in no requirement and no ROADMAP phase goal. Captured in `OQ-029`; the natural homes are
  Phases 10, 13, 16 and 22.
- **AC-3's arithmetic does not close.** Phase 5's success criterion 1 and the lock's AC-3 both say a
  full prompt lifecycle returns *"all ten events"*, and the lifecycle they enumerate — created,
  revised twice, submitted, approved, released, suite edited, access granted, restored — is **nine**.
  Not this phase's criterion and not raised as an OQ, because Phase 5 owns AC-3 and may find the
  tenth event by reading its own scope. Handed forward so it is a decision there rather than a
  surprise.

Recorded so a planner does not mistake them for gaps, these are fixed ROADMAP boundaries rather than
omissions:

- **`append()`, `read()` and `registered_actions()` as INT-006/007/008's registered signatures**, the
  cursor semantics, `scope_prompt_id` as a contract, AC-6's vocabulary equality, and the wiring of
  ADR-0038's cache into `app` and `worker` belong to **Phase 5** (PH-03, PH-06). D-64 draws the line.
- **Atomicity under a killed process (AC-1), the route-table assertion that nothing is mounted
  (AC-7), the full-corpus content inspection (AC-8), actor survival after removal (AC-9) and the
  never-deleted proof (AC-10)** belong to **Phase 6** (PH-01, PH-07, PH-08, PH-09, PH-10), along with
  six of the seven metrics and all three alerts.
- **The five writing modules** are Phases 7, 10, 13, 16 and 22. Every contract this phase builds is
  proven from property-history's own tests, exactly as Phase 2 proved `enqueue` and `price_usage`
  with neither the gateway nor evaluation in existence.
- **The React SPA and the deployment stack** own no milestone (PITFALLS §3 and §4). Neither blocks
  this phase; both need a user decision.

</deferred>

---

*Phase: 4-schema-privilege-ordering-and-the-closed-vocabulary*
*Decisions consumed: D-46 through D-65. Open questions raised: OQ-027, OQ-028, OQ-029.*
*Context gathered: 2026-08-10*
