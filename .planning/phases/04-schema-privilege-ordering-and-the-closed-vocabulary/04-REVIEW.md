---
phase: 04-schema-privilege-ordering-and-the-closed-vocabulary
reviewed: 2026-08-11T00:00:00Z
depth: standard
files_reviewed: 48
files_reviewed_list:
  - .planning/ORCHESTRATION.md
  - .planning/ROADMAP.md
  - .planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-01-PLAN.md
  - .planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-01-SUMMARY.md
  - .planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-02-PLAN.md
  - .planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-02-SUMMARY.md
  - .planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-03-PLAN.md
  - .planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-03-SUMMARY.md
  - .planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-04-PLAN.md
  - .planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-04-SUMMARY.md
  - alembic/ddl.py
  - alembic/versions/0001_roles_and_schemas.py
  - alembic/versions/0005_history_schema_and_vocabulary.py
  - docs/brainstorm/assumptions/A-124.md
  - docs/brainstorm/open_questions/OQ-131.md
  - docs/modules/access-control.lock.yml
  - docs/modules/evaluation.lock.yml
  - docs/modules/prompt-registry.lock.yml
  - docs/modules/property-history.lock.yml
  - docs/modules/provider-access.lock.yml
  - docs/modules/release-control.lock.yml
  - src/prope/db/session.py
  - src/prope/observability.py
  - src/prope/property_history/__init__.py
  - src/prope/property_history/append.py
  - src/prope/property_history/domain.py
  - src/prope/property_history/models.py
  - src/prope/property_history/observability.py
  - src/prope/property_history/registry.py
  - tests/architecture/test_no_overriding_system_value.py
  - tests/architecture/test_schema_invariants.py
  - tests/architecture/test_tenant_coverage.py
  - tests/conftest.py
  - tests/integration/test_action_registry_loads_without_a_tenant.py
  - tests/integration/test_history_schema_ships_its_guarantees.py
  - tests/integration/test_migration_chain.py
  - tests/integration/test_reprice_only_unpriced.py
  - tests/integration/test_same_transaction_events_have_a_stable_order.py
  - tests/integration/test_unregistered_detail_key_fails_the_transaction.py
  - tests/integration/test_write_path.py
  - tests/property_history/__init__.py
  - tests/security/test_call_record_guarantees.py
  - tests/security/test_history_is_append_only_by_privilege.py
  - tests/security/test_history_seq_cannot_be_supplied.py
  - tests/security/test_history_validation_has_no_database_backstop.py
  - tests/security/test_no_history_content_reaches_a_log_line.py
  - tests/security/test_tenant_isolation.py
  - tests/unit/test_details_allow_list.py
findings:
  critical: 0
  warning: 7
  info: 4
  total: 11
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-08-11
**Depth:** standard
**Files Reviewed:** 48 — the 26 source, test, migration and `docs/` files commit `4702933` changed,
the 8 plan and summary artifacts, and 14 the findings depend on (the two contracts, `ddl.py`,
revision `0001`, the tenant seam, the two Phase 1 security tests this phase had a precedent in, the
five writing modules' lock files, and A-124)
**Status:** issues_found

## Summary

**The central claim holds, and I could not break it.** I stood up a PostgreSQL 17 container at this
exact commit, applied the chain, and attacked `history.history_event` as `prope_app` by every route I
could construct: `UPDATE`, `DELETE`, `TRUNCATE`, `TRUNCATE history_action_registry CASCADE`, a
data-modifying CTE (`WITH gone AS (DELETE … RETURNING id)`), `INSERT … ON CONFLICT (id) DO UPDATE`,
`MERGE … WHEN MATCHED THEN UPDATE`, `MERGE … WHEN MATCHED THEN DELETE`, `ALTER TABLE … DROP COLUMN`,
`DROP TABLE`, `CREATE RULE … DO INSTEAD`, `ALTER TABLE … DISABLE ROW LEVEL SECURITY`,
`SET session_replication_role = 'replica'`, `SET ROLE prope_migrate`, `CREATE FUNCTION` in `public`,
`CREATE TABLE` in `history` and in `public`, and a self-`GRANT`. Every one was refused:

```
  [refused] plain UPDATE                        -> permission denied for table history_event
  [refused] plain DELETE                        -> permission denied for table history_event
  [refused] TRUNCATE                            -> permission denied for table history_event
  [refused] TRUNCATE ... CASCADE via registry   -> permission denied for table history_action_registry
  [refused] CTE data-modifying DELETE           -> permission denied for table history_event
  [refused] INSERT ... ON CONFLICT DO UPDATE    -> permission denied for table history_event
  [refused] MERGE ... WHEN MATCHED THEN UPDATE  -> permission denied for table history_event
  [refused] MERGE ... WHEN MATCHED THEN DELETE  -> permission denied for table history_event
  [refused] ALTER TABLE drop a column           -> must be owner of table history_event
  [refused] CREATE RULE ... DO INSTEAD NOTHING  -> must be owner of table history_event
  [refused] session_replication_role = replica  -> permission denied to set parameter
  [refused] SET ROLE prope_migrate              -> permission denied to set role "prope_migrate"
  AFTER ALL ATTACKS: rows=1  reason='<null>'
```

Two statements — `REVOKE INSERT … FROM prope_app` and `GRANT UPDATE … TO prope_app` — return
without error, because PostgreSQL answers a non-owner's grant with a `WARNING` rather than an
`ERROR`. I re-checked the catalogue afterwards and they are no-ops:
`has_table_privilege('prope_app','history.history_event','UPDATE')` is still `false`, `INSERT` is
still `true`, and a subsequent `UPDATE` is still refused. There is no self-escalation here.

The live grant matrix is exactly what `04-01`'s `must_haves` claim, read from the running catalogue
rather than from the migration source:

```
  prope_app       history.history_event            -> ['SELECT', 'INSERT']
  prope_app       history.history_action_registry  -> ['SELECT']
  prope_report    history.history_event            -> ['SELECT']
  prope_report    history.history_action_registry  -> ['SELECT']
  prope_migrate   history.history_event            -> SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER
  history_event owner=prope_migrate rls=true forcerls=false | history_action_registry rls=false
  prope_app  super/bypassrls/createrole/createdb = false/false/false/false  member_of=(none)
```

**The `seq` total order is real, and the attack surface it does not close is the one the phase
recorded.** `prope_app` holds no privilege at all on the identity sequence — `USAGE`, `SELECT` and
`UPDATE` are all `false`, the sequence is owned by `prope_migrate`, and `setval()`,
`ALTER SEQUENCE … CACHE 20` and `ALTER TABLE … ALTER COLUMN seq RESTART` are each refused. `seqcache`
reads `1` from the catalogue and is a persisted sequence property, so it survives reconnection and a
restart; `TRUNCATE … RESTART IDENTITY` in the rig resets `last_value` and not the cache. The one
opening — `OVERRIDING SYSTEM VALUE`, which carries no privilege requirement — is asserted in both
directions in `tests/security/test_history_seq_cannot_be_supplied.py`, including the non-obvious half
that the *next* engine-assigned value is **lower** than the supplied one, and both that test and
`0005`'s docstring say in writing what to delete if the boundary ever moves. That is the right
posture and it is rare.

**The ordering test distinguishes what it claims to distinguish.**
`test_approval_precedes_release_when_their_timestamps_are_identical` reads back `ORDER BY seq` and
then asserts `len({row.occurred_at for row in rows}) == 1`, so a timestamp tiebreak cannot be
producing the result. Its three-element sibling drops a lucky pass from one-in-two to one-in-eight.
And the gap pair is the best-argued thing in the phase: `test_a_gap_in_seq_is_not_a_missing_event`
and `test_a_validation_refusal_between_two_writes_leaves_no_gap` assert the two *different*
mechanisms separately, so "a rolled-back INSERT strands a value" and "a validation refusal issues no
SQL" are exercised rather than conflated. Asserting only the first would have left the looser, false
version of the claim equally consistent with the evidence.

**The 31-row seed is the union of the five lock files' event lists, and I checked it name by name
against the source rather than against the plan.** `prompt-registry.lock.yml:90` (5),
`release-control.lock.yml:102-103` (8), `evaluation.lock.yml:96` (4),
`provider-access.lock.yml:93` (4), `access-control.lock.yml:110-111` (10) = 31, with no extras and no
omissions, including `user_tombstoned` which ADR-0024's own Context table drops. `requires_reason` is
true for exactly the three `release-control.lock.yml:110-112` names, and the two non-empty
`detail_keys` sets match `release-control.lock.yml:113-114` and `A-124:16`. The phase deliberately
does **not** assert the full name equality (that is Phase 5 SC2) and says so in three places, which
is the honest call — the derivation and the assertion belong together.

**The rollback is asserted against the database, not a mock.**
`test_an_unregistered_detail_key_rolls_the_callers_transaction_back` writes a valid event first, then
the poisoned one, and reads `count(*) == 0` back through `migrate_engine` — the owner role, outside
RLS. That is what distinguishes ADR-0023's "commits or rolls back with the caller" from call-ledger's
D-19 shape, and the file's docstring says exactly that. The counter delta is checked on all three
labels, so a refusal that incremented the wrong one fails.

Anti-patterns: **zero.** No `TODO`, `FIXME`, `XXX`, `HACK`, `TBD`, `NotImplementedError`, bare `pass`
or ellipsis stub anywhere in the phase's new source or tests. Forbidden edges hold: every import
under `src/prope/property_history/` resolves to `prope.property_history.*` or `prope.db.metadata`, no
FastAPI at any depth, and `src/prope/app.py` and `src/prope/worker.py` are untouched.
`uv.lock` and `pyproject.toml` did not move. Nothing was written outside the union of the four plans'
`files_modified` except `docs/brainstorm/open_questions/OQ-131.md`, which `04-01`'s frontmatter
explicitly excludes on purpose and which the orchestrator allocated. `04-04`'s plan lists
`.planning/WINDOWS.md` in `files_modified` and its executor correctly refused to write it under §7.

Gate, run by me at this commit: `uv run ruff check src/ tests/ alembic/` → `All checks passed!`;
`uv run pytest -q` → **516 passed, 1 skipped** in 287 s. Green.

**Nothing here is critical.** What is wrong is a coverage pattern, and it is consistent enough to be
a finding rather than seven: **the phase proved the guarantees it argued about and left the ones it
inherited unasserted.** The grant matrix, the composite key, `seq` and the rollback all have tests
with positive controls. The tenant policy on `history_event` and all three named `CHECK` constraints
have none — they are proven to exist by a catalogue row and proven to work only by me, in this
review. Phase 1 wrote both of those test shapes for `ledger`, in the same two directories, and this
phase did not inherit either. Underneath that: one positive control is an assertion over an empty
table, four validation branches in `domain.py` have no test and raise the one exception class that
module argues must never carry an audit refusal, the `OVERRIDING SYSTEM VALUE` source gate is
defeated by a second space, the `details` allow-list checks keys and the code claims it checks
content, and §12's named backlog is still measurably over budget.

## Critical Issues

**None.** The product claim this module is sold on — that the log cannot be quietly rewritten — is
enforced by the engine, and I could not defeat it by any route. The two success criteria the phase
owns end to end (PH-02's privilege refusal and PH-04's stable order) are proven by tests that would
fail if the guarantee were removed, each with a positive control that would fail if the test were
pointed at the wrong object.

## Warnings

### PH-01: the tenant policy on `history_event` is asserted structurally and never behaviourally — and `record_event` takes `workspace_id` from the caller, which is ADR-0040's named leak

**File:** `alembic/versions/0005_history_schema_and_vocabulary.py:389`,
`src/prope/property_history/append.py:103-135`,
`tests/architecture/test_tenant_coverage.py:127-141`,
`tests/security/test_tenant_isolation.py` (the Phase 1 precedent that has no Phase 4 counterpart)

**Issue:** `enable_tenant_rls("history", "history_event")` ships the policy, and three things assert
that it *exists*: the coverage walk checks `relrowsecurity` and a `pg_policies` row,
`test_migration_chain.py`'s snapshot captures `qual`/`with_check` text, and that is all. **No test in
this phase writes an event for two workspaces and reads one back.** `WORKSPACE_B` and `WORKSPACE_C`
are exported from `tests/property_history/__init__.py:46-47` and used by nothing —
`grep -rn "WORKSPACE_B" tests/property_history tests/security tests/integration` returns only the
import and the `__all__` entry.

That matters more here than it would on another table, because of how the append path is shaped.
`record_event` binds `event.workspace_id` straight from the draft
(`append.py:124`), and `check_event` never compares it to the session's tenant. `workspace_transaction`
sets `app.workspace_id` from a *separate* argument (`session.py:59-62`). So a writing module that
constructs a `HistoryEventDraft` with one workspace and opens its transaction on another is
writing a mis-stamped, denormalised `workspace_id` — which is verbatim the leak ADR-0040 is about and
that `enable_tenant_rls`'s own docstring (`ddl.py:81-85`) says the written-out `WITH CHECK` exists to
stop. **The `WITH CHECK` is the only thing standing there, and nothing in the suite exercises it for
this table.**

I verified the policy does work, against the live engine:

```
  prope_app SELECT tenant=A   -> 3
  prope_app SELECT tenant=B   -> 1
  prope_app SELECT no tenant  -> 0
  prope_app INSERT stamping another tenant -> ERROR: new row violates row-level security policy
  owner row count (positive control): 4
```

So this is an unasserted guarantee, not a broken one. But `test_tenant_coverage.py` would stay green
if the policy were replaced by a permissive `USING (true)`, and the `history` half of the migration
snapshot only catches a change made in a *later* migration, not a change made by hand or by a helper
edit. Non-negotiable #4 rests on this and it currently has no behavioural test.

**Fix:** the Phase 1 file is the template and it is two directories away. Add
`tests/security/test_history_tenant_isolation.py` with the four assertions
`test_tenant_isolation.py` already makes for `call_record`, retargeted:

```python
async def test_an_event_written_for_another_tenant_is_invisible(app_sessionmaker, migrate_engine):
    await seed_history_event(migrate_engine, id=EVENT_ID, workspace_id=WORKSPACE_A)
    await seed_history_event(migrate_engine, id=OTHER_EVENT_ID, workspace_id=WORKSPACE_B)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        seen = (await session.execute(text("SELECT id FROM history.history_event"))).scalars().all()
    assert seen == [EVENT_ID]

    # Positive control: both rows are there, and the POLICY is what hid one.
    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 2


async def test_record_event_stamping_another_tenant_is_refused_by_with_check(
    app_sessionmaker, migrate_engine
):
    """ADR-0040 on this table: the draft carries its own workspace_id and
    `check_event` does not compare it to the session's tenant, so WITH CHECK is
    the whole defence."""
    registry = await load_registry(app_sessionmaker)
    with pytest.raises(DBAPIError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await record_event(session, draft(workspace_id=WORKSPACE_B), registry)
    assert "row-level security" in str(excinfo.value).lower()

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 0
```

and one for the pristine-connection path (`app_sessionmaker()` with no tenant ever set) so the NULL
predicate is covered as well as the reverted-to-`''` one — `test_tenant_isolation.py:12-18` argues
why those are two different routes and both must be exercised.

Separately, consider whether `record_event` should refuse a draft whose `workspace_id` differs from
`current_setting('app.workspace_id')` before issuing SQL. It would turn an `IntegrityError` that
poisons the caller's whole transaction into a named refusal with a counter, and it is one `SELECT`
the module already has a session for. If it is deliberately not done, that belongs in `append.py`'s
docstring beside the other two enforcement-seam decisions.

---

### PH-02: the positive control in the registry-exemption test is an assertion over an empty table, and its docstring says it proves something it cannot

**File:** `tests/integration/test_history_schema_ships_its_guarantees.py:59-77`

**Issue:**

```python
async def test_the_registry_is_readable_with_no_tenant_context_and_holds_thirty_one_rows(
    app_sessionmaker,
):
    """...The companion count on ``history_event`` is the positive control's
    mirror: it proves the session really has no tenant context, so the 31 rows
    came from the exemption and not from a leaky policy."""
    async with app_sessionmaker() as session:
        assert (await session.execute(COUNT_REGISTRY_ROWS)).scalar_one() == 31
        assert (await session.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 0
```

**Nothing in this test writes a `history_event` row.** `truncate_owned_tables` is a `yield`-then-
truncate autouse fixture (`tests/conftest.py:188-202`), so `history_event` is empty when the test
starts. `count(*) == 0` is therefore true with a tenant set, with a tenant unset, with the policy
dropped, with RLS disabled, and against a table that does not have the column the predicate names. It
distinguishes no hypothesis from any other, which is exactly the failure mode
`test_the_walk_actually_found_modules_to_check` and `test_no_zero_anywhere_in_a_mixed_batch…` exist to
prevent elsewhere in this repository — and it is the one the file's own module docstring
(`:1-13`) says it is shaped against.

The test's *first* assertion is genuine and valuable: 31 rows readable by `prope_app` on a session
with no tenant is exactly ADR-0038's process-start read, and the exemption fails loudly if reversed.
The defect is the second line and the sentence justifying it.

**Fix:** give the control something to hide. Seed one event as the owner first, then the zero means
the policy:

```python
async def test_the_registry_is_readable_with_no_tenant_context_and_holds_thirty_one_rows(
    app_sessionmaker, migrate_engine
):
    # The control needs a row to hide, or the zero below is true against an
    # empty table and distinguishes nothing.
    await seed_history_event(migrate_engine)

    async with app_sessionmaker() as session:
        assert (await session.execute(COUNT_REGISTRY_ROWS)).scalar_one() == 31
        assert (await session.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 0

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 1
```

That makes the pair mean what the docstring already claims: the same session sees 31 registry rows
and zero events, with a row provably present — so the registry is genuinely exempt and the session
genuinely carries no tenant.

---

### PH-03: three named `CHECK` constraints shipped on `history_event` and not one of them is asserted, and `ActorType.SYSTEM` appears in no test in the repository

**File:** `alembic/versions/0005_history_schema_and_vocabulary.py:194-195`,
`alembic/versions/0005_history_schema_and_vocabulary.py:199-200`,
`alembic/versions/0005_history_schema_and_vocabulary.py:207-208`,
`tests/security/test_call_record_guarantees.py:40-64` (the Phase 1 precedent)

**Issue:** `grep -rn "ck_history_event" tests/` returns nothing. Phase 1 wrote
`tests/security/test_call_record_guarantees.py`, which provokes each ledger `CHECK` and asserts the
constraint **by name** in the message, and six other files name a ledger constraint in an assertion.
This phase shipped three and asserted none:

- `ck_history_event_actor_type_values` — the "never a native enum" position. `test_schema_invariants`
  proves no native enum *exists*; nothing proves the CHECK that replaced it refuses anything.
- `ck_history_event_actor_id_present_unless_system` — the nullable-actor rule.
  `grep -rn "ActorType.SYSTEM" tests/` returns **nothing**. Half of a two-member enum, the entire
  system-actor branch of `domain.py:184-188`, and both directions of this constraint are unexercised.
  If the column had shipped `NOT NULL`, or if the CHECK were inverted, every test in the phase would
  still pass.
- `ck_history_event_reason_length` — ADR-0053's whole reason for a `CHECK` over `varchar(500)` is that
  the cap must be **characters, not bytes**, because a Vietnamese-only interface would otherwise get a
  ~170-character cap. Nothing asserts that. A later "simplification" to `varchar(500)` would pass the
  suite, pass `ruff`, pass the schema invariants, and silently truncate the MVP's only language.

All three work — I provoked each against the live engine at this commit:

```
  system actor, actor_id NULL                 -> INSERT 0 1
  user actor, actor_id NULL                   -> ERROR: ... "ck_history_event_actor_id_present_unless_system"
  actor_type 'robot'                          -> ERROR: ... "ck_history_event_actor_type_values"
  reason 500 chars                            -> INSERT 0 1
  reason 501 chars                            -> ERROR: ... "ck_history_event_reason_length"
  reason 500 MULTIBYTE chars ('ứ' * 500)      -> INSERT 0 1
```

so the finding is coverage, not correctness. But the last line is the one worth having in the suite:
it is the only assertion that would distinguish this schema from the `varchar(500)` the plan refused,
and it costs three lines.

**Fix:** one file, in the shape `test_call_record_guarantees.py` already established:

```python
async def test_a_user_actor_with_no_actor_id_is_refused_by_name(migrate_engine):
    with pytest.raises(IntegrityError) as excinfo:
        async with migrate_engine.begin() as connection:
            await connection.execute(
                SEED_HISTORY_EVENT, history_event_values(actor_type="user", actor_id=None)
            )
    assert "ck_history_event_actor_id_present_unless_system" in str(excinfo.value)


async def test_a_system_actor_may_be_anonymous(migrate_engine):
    """The permitted half. ADR-0054 needs it and no test in the phase writes one."""
    async with migrate_engine.begin() as connection:
        await connection.execute(
            SEED_HISTORY_EVENT, history_event_values(actor_type="system", actor_id=None)
        )


async def test_the_reason_cap_counts_characters_and_not_bytes(migrate_engine):
    """ADR-0053: 500 Vietnamese characters is ~1400 bytes. A varchar(500) or a
    byte cap would be a ~170-character cap for every user the MVP has, and this
    is the only assertion that tells the two apart."""
    async with migrate_engine.begin() as connection:
        await connection.execute(
            SEED_HISTORY_EVENT, history_event_values(reason="ứ" * MAX_REASON_CHARACTERS)
        )

    with pytest.raises(IntegrityError) as excinfo:
        async with migrate_engine.begin() as connection:
            await connection.execute(
                SEED_HISTORY_EVENT,
                history_event_values(id=OTHER_EVENT_ID, reason="ứ" * (MAX_REASON_CHARACTERS + 1)),
            )
    assert "ck_history_event_reason_length" in str(excinfo.value)
```

---

### PH-04: `HistoryEventDraft.__post_init__` has four raise sites, zero tests, and raises the one exception class the same module argues must never carry an audit refusal

**File:** `src/prope/property_history/domain.py:170-193`,
`src/prope/property_history/domain.py:62-72`, `src/prope/property_history/append.py:22-25`

**Issue:** `HistoryAppendRejected`'s docstring makes an unusually careful argument for why it is not a
`ValueError`:

> Not a ``ValueError`` for the same reason, one step further out — five modules will call the append
> path from code that validates its own request bodies, and an ``except ValueError`` around a request
> body would swallow the audit log's refusal and commit the state change without its event.

Twelve lines below that argument, `__post_init__` raises a plain `ValueError` four times, for four
audit invariants:

```python
        if not self.id.startswith(EVENT_ID_PREFIX):          raise ValueError(...)   # :172
        if self.occurred_at.tzinfo is None:                  raise ValueError(...)   # :177
        if self.actor_id is None and ... is not SYSTEM:      raise ValueError(...)   # :185
        if self.reason is not None and len(...) > 500:       raise ValueError(...)   # :190
```

Two of the four are database invariants restated in Python by design —
`:185` is `ck_history_event_actor_id_present_unless_system` and the comment above it says so, and
`:190` is `ck_history_event_reason_length`. So the module raises audit refusals as `ValueError` in
exactly the place its own design note says that class must never appear. The construction happens in
the caller's code, which is where the `except ValueError` the docstring warns about actually lives —
a route assembling a draft from a request body inside its own validation handler swallows the
refusal and proceeds, and `:185` is the one that then produces a state change with no event.

Compounding it: `append.py`'s module docstring (`:22-25`) tells the next reader that only one
`ValueError` can originate on this path and that it is `python-ulid`'s. Four more can, from the
module next door, and the reader has been told to stop looking.

**None of the four is tested.** `grep -rn "raises(ValueError" tests/` finds fourteen call sites and
not one is in a history test; `EVENT_ID_PREFIX` and `MAX_REASON_CHARACTERS` are referenced by no test
at all. Nine `HistoryEventDraft(...)` constructions exist across the suite and every one is valid.

**Fix:** either raise `HistoryAppendRejected` from `__post_init__` with a fourth `RejectionReason` —
which `D-63` and `tests/unit/test_details_allow_list.py:155-165` correctly forbid, because the lock's
alert pages on every increment and a fourth label is a page nobody declared — or, the cheaper and
more consistent option, give the module its own construction-time exception that is not a
`ValueError` and is not counted:

```python
class HistoryDraftInvalid(Exception):  # noqa: N818
    """A draft that cannot be an audit row. Constructed before any append, so it
    is NOT counted by append_rejected_total (D-63: a fourth label is a fourth
    page). Not a ValueError, for HistoryAppendRejected's reason: an
    `except ValueError` around a request body would swallow it and commit the
    state change without its event."""
```

Either way, add the four missing tests to `tests/unit/test_details_allow_list.py` (or a sibling), and
correct `append.py:22-25` to say that `domain.HistoryEventDraft` refuses four things at construction
and names them.

---

### PH-05: the `OVERRIDING SYSTEM VALUE` source gate is defeated by a line break or a second space, and its own failure message claims a token it does not match

**File:** `tests/architecture/test_no_overriding_system_value.py:45`,
`tests/architecture/test_no_overriding_system_value.py:80`,
`tests/architecture/test_no_overriding_system_value.py:102-109`,
`tests/architecture/test_no_overriding_system_value.py:123-138`

**Issue:** the gate is a single-token substring test over string constants:

```python
TOKEN = "overriding system value"
...
        if TOKEN in node.value.lower():
```

SQL is whitespace-insensitive, so every one of these is a valid statement the gate does not see. I
ran them through the file's own `_overriding_hits`:

```
  CAUGHT   single line OVERRIDING SYSTEM VALUE
  MISSED   line-broken across the token
  MISSED   newline before VALUE only
  MISSED   two spaces between words
  MISSED   OVERRIDING USER VALUE
```

The two-space case is the one that lands by accident — the repository's own SQL constants are
column-aligned, so an aligned `OVERRIDING  SYSTEM VALUE` is a plausible thing to write. The
line-broken cases are the ones a determined author uses, and this gate exists precisely because
`GENERATED ALWAYS` "does not refuse the statement someone determined would write" (`0005:60-74`). The
gate also only reads literal `ast.Constant` strings, so `text("... " + OVERRIDE + " ...")` or an
f-string walks past it entirely.

The committed positive control at `:123-138` uses only the single-line form, so the hole is invisible
from inside the suite — which is the same shape as the finding, one level up.

Separately, the assertion message at `:103-104` reads *"contains 'OVERRIDING SYSTEM VALUE' (or
OVERRIDING USER VALUE)"*. `TOKEN` never matches `OVERRIDING USER VALUE`. That one is harmless in
effect — PostgreSQL discards a supplied value under `OVERRIDING USER VALUE` and uses the sequence, so
it cannot break the order — but the message tells a reader the gate polices something it does not.

**Fix:** match on a whitespace-tolerant pattern and cover both tokens, and extend the positive
control to the forms that currently pass:

```python
#: Whitespace-tolerant, because SQL is. `OVERRIDING  SYSTEM VALUE` and a
#: line break inside the token are both valid statements and both used to pass.
#: USER VALUE is matched too: it is harmless (the engine discards the supplied
#: value) but a reader should not have to know that to trust the message.
TOKEN = re.compile(r"overriding\s+(system|user)\s+value", re.IGNORECASE)
...
        if TOKEN.search(node.value):
            hits.append(node)
```

```python
def test_the_gate_is_not_defeated_by_whitespace() -> None:
    for source in (
        'S = "insert into t (a) overriding system value values (1)"',
        'S = """insert into t (a)\nOVERRIDING SYSTEM\nVALUE VALUES (1)"""',
        'S = "insert into t (a) OVERRIDING  SYSTEM VALUE values (1)"',
        'S = "insert into t (a) OVERRIDING USER VALUE values (1)"',
    ):
        assert _overriding_hits(ast.parse('"""doc"""\n' + source + "\n")), source
```

State the remaining limit in the module docstring: a token assembled from concatenated fragments is
outside an AST-constant walk, and the honest claim is *no literal statement*, not *no statement*.

---

### PH-06: §12's named comment-density backlog is still over budget, measured, and the migration is the worst of it

**File:** `alembic/versions/0005_history_schema_and_vocabulary.py`,
`src/prope/property_history/__init__.py`, `src/prope/property_history/observability.py`,
`src/prope/property_history/registry.py`, `src/prope/property_history/append.py`,
`src/prope/property_history/domain.py`

**Issue:** `.planning/ORCHESTRATION.md` §12 names these six files, assigns the trimming as work rather
than polish, and says *"a reviewer that sees them still over budget should report it as a **warning**
with the file named."* They are still over budget. Measured at this commit, counting comment lines,
docstring lines and `--` comment lines inside the DDL string constants, over non-blank lines:

| File | Non-blank lines | Prose lines | Prose % | §12 target |
|---|---|---|---|---|
| `src/prope/property_history/__init__.py` | 13 | 13 | **100%** | < 33% |
| `src/prope/property_history/observability.py` | 25 | 19 | **76%** | < 33% |
| `alembic/versions/0005_history_schema_and_vocabulary.py` | 382 | 257 | **67%** | **< 25%** |
| `src/prope/property_history/registry.py` | 55 | 26 | **47%** | < 33% |
| `src/prope/property_history/append.py` | 128 | 59 | **46%** | < 33% |
| `src/prope/property_history/domain.py` | 156 | 70 | **45%** | < 33% |
| `src/prope/property_history/models.py` | 46 | 15 | 33% | < 33% |

(§12's own table records `0005` at 50%; that figure appears to exclude the SQL `--` comments inside
the `CREATE TABLE` constants, which are 91 of the 257 lines and are the bulk of what §12's
*"Migrations specifically"* clause is about — `GENERATED ALWAYS AS IDENTITY (CACHE 1)` has 17 lines of
commentary at `:134-149`, where §12 asks for one.)

Both executors did note the override in their summaries (`04-01-SUMMARY.md:301-321`,
`04-02-SUMMARY.md:318`) and both genuinely cut against their plans' instructions, which is why this is
a warning and not something sharper. But `04-01` and `04-02` were written before §12 existed and the
result is what §12 predicted.

The worst individual offenders, for a remediation pass:

- `0005:134-149` — 16 lines of comment above one column definition, re-arguing D-53, `CACHE 1`,
  monotonic-is-not-gapless and assignment-order-is-not-commit-order. All four arguments already exist
  in `04-01-PLAN.md`, `04-CONTEXT.md` and `OQ-131.md`. §12: *"`GENERATED ALWAYS AS IDENTITY (CACHE 1)`
  gets one line, not fourteen."*
- `0005:210-227` — 18 lines on the foreign key, including a multixact arithmetic paragraph marked
  `[AGENT JUDGEMENT]`. That is a decision record, and §12 says relocate it, not delete it:
  `04-01-SUMMARY.md`'s `key-decisions` is where it belongs.
- `0005:269-309` — 41 lines above `SEED_ACTION_REGISTRY`. The derivation is genuinely valuable and is
  genuinely already in the plan and in OQ-029.
- `src/prope/property_history/__init__.py` — 13 lines, all docstring, no code. §12 does not forbid a
  package docstring; it forbids re-arguing the ADRs in one. Four lines and two citations would carry
  the same facts.

**Fix:** trim to §12's budget in a pass that has all six files in scope, moving every argument worth
keeping into `04-01-SUMMARY.md` / `04-02-SUMMARY.md` `key-decisions`, `04-CONTEXT.md`, or an OQ —
§12: *"Nothing that records a decision may be lost — only relocated."* Two paragraphs of `0005`'s
docstring must survive verbatim in substance: paragraph 2 (the D-53 deviation record, which §12's
*Migrations specifically* clause requires) and paragraph 7 (the `OVERRIDING SYSTEM VALUE` boundary,
which `tests/security/test_history_seq_cannot_be_supplied.py:107-112` instructs a future agent to
delete *together with*, so removing it silently leaves a dangling reference in a security test).

---

### PH-07: the `details` allow-list checks keys only, and two places claim it checks content

**File:** `src/prope/property_history/append.py:87-95`,
`alembic/versions/0005_history_schema_and_vocabulary.py:166-175`,
`src/prope/property_history/append.py:14-19`, `docs/brainstorm/assumptions/A-124.md:14-26`

**Issue:** `check_event` computes `frozenset(event.details) - registered.detail_keys` — a top-level
key-set difference. Values are never inspected. A nested object under a **registered** key is
therefore unbounded, and I confirmed the engine stores it:

```
  INSERT ... 'revision_released' ... details = {"version_id": {"prompt_body": "SECRET PROMPT TEXT"}}
  engine: INSERT 0 1
```

That matches A-124's mechanism, which is explicitly a key allow-list — so the code is not wrong
against its assumption. What is wrong is that two places state the stronger property:

- `0005:166-175` justifies `jsonb` over `0003`'s `text` on the grounds that *"the payload is assembled
  by our own code out of allow-listed keys and **never carries provider content**"*. The first clause
  is enforced; the second is not, and it is the one carrying the argument.
- `append.py:14-19` frames the seam as *"the `details` allow-list … refused here"*, which reads as the
  whole of A-124's rule rather than its key half.

A-124's own rationale is the reason this matters: *"'just put the whole object in for debugging' is a
one-line change that no reviewer would flag. The allow-list makes the leak a build failure at the
moment it is written."* Under the shipped check, `details={"version_id": whole_response_object}` is a
build success. T-022 is HIGH and `prope_report` holds `SELECT` on this column across every workspace
(`0005:398-409`), so the blast radius of a nested leak is the whole install.

**Fix:** the cheap version costs four lines and is compatible with every key declared today —
`version_id`, `previous_version_id`, `break_glass`, `role`, `grantee_user_id` are all scalars:

```python
    # A-124's rule is about VALUES as well as keys, and the key check does not
    # reach them: `details={"version_id": whole_response_object}` passes a
    # key-only allow-list. Scalars only — every key any lock file declares today
    # is a string or a bool, and a nested object is the shape A-124's rationale
    # names ("just put the whole object in for debugging").
    nested = sorted(
        key
        for key, value in event.details.items()
        if value is not None and not isinstance(value, (str, int, float, bool))
    )
    if nested:
        raise HistoryAppendRejected(
            RejectionReason.UNKNOWN_DETAIL_KEY, action=event.action, detail_key=nested[0]
        )
```

If that is deliberately refused — and there is a defensible case, since a fourth `RejectionReason`
would be a fourth page and reusing `unknown_detail_key` overloads the label — then record the
boundary the way this phase recorded the `OVERRIDING SYSTEM VALUE` one: a test named
`test_a_nested_payload_under_a_registered_key_is_not_refused`, with the same *"if this starts failing,
do not fix it — delete this test and the docstring paragraph together"* header that
`test_history_validation_has_no_database_backstop.py:164-168` uses. Then correct `0005:169-170` from
*"never carries provider content"* to the property that is actually enforced.

## Info

### PH-08: `OQ-131` exists and nothing in the tree points at it; `0005`'s docstring still says the id is unallocated

**File:** `alembic/versions/0005_history_schema_and_vocabulary.py:20-25`,
`docs/brainstorm/open_questions/OQ-131.md:76-79`

`grep -rn "OQ-131" src/ tests/ alembic/ .planning/phases/04-*/` returns **nothing**. The revision
still reads *"Phase 4's allocated range OQ-027..OQ-031 is consumed, so the id is owed and
unallocated"*, while `OQ-131.md` shipped in the same commit, names this file under `blocks:` and under
*What is affected either way*, and the commit message says the deviation is *"recorded in OQ-131"*.
The executor's behaviour was correct at the time — `04-01-SUMMARY.md:379-383` escalates rather than
borrowing an id — and the orchestrator allocated afterwards. Nothing has closed the loop since.

This is CR-06's class from the Phase 3 review, at one site instead of five. **Fix:** replace the
"owed and unallocated" sentence with `see docs/brainstorm/open_questions/OQ-131.md`, and note the
allocation in `deferred-items.md` §1 (orchestrator-owned, §7).

---

### PH-09: `LOGGABLE_FIELDS` cannot express the distinction its own comment claims, and one added name has no producer

**File:** `src/prope/observability.py:65`, `src/prope/observability.py:77-86`,
`src/prope/observability.py:103`

The added block says property-history's user-authored `reason` column *"gets **no name in this list at
all**, which is the strongest available spelling of the lock file's 'never logged': an absence needs no
maintenance where a subtraction rule needs somebody to keep believing it."* But `"reason"` **is** in
the set, at `:65`, from Phase 2. The two columns share a name, so
`test_every_logged_key_is_in_the_allow_list` would pass a future
`log.info("property_history.…", reason=event.reason)` without a murmur. The protection is convention,
not the absence the comment describes. The marker tests catch it only on the three paths they drive.

Also `"writing_module"` (`:103`) is allow-listed and logged by nothing —
`grep -rn "writing_module" src/` finds it only in the registry query, the dataclass field and this
entry. Harmless (an allow-list is permissive), and the mirror of Phase 2's WR-06.

**Fix:** either rename call-ledger's token to `refusal_reason` so the absence is real, or add the
assertion the comment implies — an AST check that no `structlog` call site under
`src/prope/property_history/` passes a `reason=` keyword. Phase 6 owns the full-corpus source gate
(AC-8) and this is one predicate on it.

---

### PH-10: `RegisteredAction.target_type` is loaded, held, and read by no code

**File:** `src/prope/property_history/domain.py:130`, `src/prope/property_history/append.py:83-100`

`check_event` reads `registered.detail_keys` and `registered.requires_reason` and never
`registered.target_type`. The pairing is left entirely to `fk_history_event_action`, which is a
deliberate and well-argued seam (`test_history_validation_has_no_database_backstop.py:102-120` asserts
it). The cost is that a caller pairing `revision_released` with `target_type='property'` gets an
`IntegrityError` naming a constraint, with the transaction already poisoned, instead of the named
refusal-plus-counter every other vocabulary error gets — and the registry row that would have caught
it before any SQL is already in memory.

Not a defect; the phase chose this. Worth one line in `check_event`'s docstring saying the fourth
check is deliberately the engine's, so the unread field does not read as an oversight.

---

### PH-11: `04-04`'s plan declares an orchestrator-owned file in `files_modified`

**File:** `.planning/phases/04-schema-privilege-ordering-and-the-closed-vocabulary/04-04-PLAN.md:16`

The plan lists `.planning/WINDOWS.md` with a wave-disjointness argument. §7 forbids an executor from
writing it *"even when its plan's `files_modified` lists one"*, and the executor correctly refused
(`04-04-SUMMARY.md:213`) and reported the `request_id` window in its ledger section instead. Recorded
so the planner-side rule is visible: a plan must not name a §7 file, because `files_modified` is what
the orchestrator checks disjointness against and a listed-but-forbidden path is a declaration that
cannot be trusted either way.

## Known and deliberate

These are recorded decisions, not defects. They are separated out so the list above stays credible.

- **`seq` ships as `GENERATED ALWAYS AS IDENTITY (CACHE 1)` where the lock file says `bigserial`** —
  a strengthening with an observable behavioural difference, correctly refused an id from another
  phase's range, escalated, and allocated `OQ-131` by the orchestrator. The reversal cost is stated
  and correct.
- **`OVERRIDING SYSTEM VALUE` is accepted and that is asserted, not hidden.**
  `test_overriding_system_value_is_accepted_and_that_is_the_recorded_boundary` proves the branch that
  is real in this rig (the next engine value is *lower*, and the read order is silently wrong) rather
  than the `uq_history_event_seq` collision a naive reading predicts, and says why the collision is
  unreachable here. Both it and `0005`'s paragraph 7 carry delete-together instructions.
- **The `details` allow-list and `requires_reason` have no database backstop** — a `CHECK` cannot
  reach another table and ADR-0023 rejects triggers for this module by name. The absence is asserted
  in `test_a_hand_written_insert_bypasses_the_python_validations` rather than assumed, with a
  positive control proving the chosen action really is the case under test.
- **Twenty-eight actions are seeded with empty `detail_keys`, including four whose keys
  `evaluation.lock.yml:96` already declares.** The consequence is stated at the seed rather than
  discovered later: Phase 16 writing `eval_run_started` with `details={"version_id": …}` is refused
  with `unknown_detail_key`. `OQ-029` carries the obligation.
- **`target_type`'s thirteen values are derived, not read.** Nothing in `docs/` enumerates them; only
  `user` is stated anywhere (A-151, ADR-0054). Cited to `OQ-029`, and the cost of being wrong is
  bounded because nothing joins on it and the *pairing* is an engine fact.
- **Three of the 31 action names break A-120's own `<target_type>_<past participle>` rule** —
  `retired`, `owner_changed`, `access_level_changed`. Seeded as the lock files spell them, because
  AC-6 is an asserted equality and A-120 is prose. `OQ-028`.
- **`history_action_registry` is the project's first `GLOBAL_TABLES` entry, and the walk `continue`s
  past it rather than asserting against it** — so the exemption currently buys no check.
  `OQ-031`, closed from the other side by
  `test_the_registry_is_readable_with_no_tenant_context_and_holds_thirty_one_rows`, with the walk
  itself routed to Phase 7. (See PH-02: the "other side" needs one more line to be a real control.)
- **`prope_report` holds `SELECT` on `reason` and `details` across every workspace** — a full-read
  credential on the module's two most content-bearing columns. ADR-0037 declares it and A-126's
  cross-workspace Success SQL requires it; withholding it sends that query back to `prope_migrate`,
  the only role that can delete a history row. Argued at the code and listed for human check.
- **The registry-count line in the idempotency snapshot cannot catch a double-apply of `0005`**, and
  `test_migration_chain.py:76-82` says so — the second `upgrade head` runs no revision body. It is
  there for the *next* migration.
- **AC-5's `test_ref` names `tests/unit/…` and the file shipped under `tests/integration/`** — the
  transaction half is not observable without a database. Both halves are asserted, which is more than
  the named file would have delivered. Recorded in the plan; no OQ owed.
- **`tests/property_history/__init__.py` imports `tests.unit`**, which executes two call-ledger
  imports. A test-rig dependency, not a module edge; `dependencies: []` is a statement about
  `src/prope/`, and nothing under `src/prope/property_history/` imports another module at any depth
  (verified).
- **`ruff format --check` is not a gate** (Broken Window #1) and `make check` inherits its failure.
  Not this phase's to fix.

## Carried forward from Phase 3 — still open, still unowned

Phase 3's review left ten findings. Phase 4 touched none of the files involved and closed one item by
side effect; the rest are unchanged and are listed so the next phase inherits a register rather than
a re-discovery.

| Id | Subject | State after Phase 4 |
|---|---|---|
| CR-03 | the shutdown drain's remainder count is skipped when the stop wait cancels it | Unchanged — `enqueue.py` untouched by this phase |
| CR-04 | two paging alerts read `worker`-only gauges that `app` serves as hard zeros | Unchanged |
| CR-05 | CR-01 closed at the route only; the writer-side overflow is unbounded | Unchanged |
| CR-06 | four modules carry prose that later plans made false | Unchanged, and PH-08 above adds a fifth site in a new file |
| CR-07 | 03-01 edited both WR-11 tests and left them proving nothing | Unchanged |
| CR-08 | `lifespan`'s teardown can still skip `reset_handoff()` and `engine.dispose()` | Unchanged |
| CR-09 | none of phase 3's six UNCONFIRMED adoptions reached `ORCHESTRATION-DECISIONS.md` | Unchanged, and Phase 4 adds five more plus the `prope_report` posture (`04-01-SUMMARY.md:385-401`) |
| CR-10 | the 500 records/sec load assertion is red and skipped by default | Unchanged |
| CR-11 | the retention route's positive control reads back through application code | Unchanged |
| CR-12 | `worker`'s broker connect is unbounded and outside its `try` | Unchanged |
| WR-06 | `LOGGABLE_FIELDS` is read by no code | **Closed.** `tests/security/test_no_history_content_reaches_a_log_line.py:181-220` is its first reader. See PH-09 for what that reader can and cannot see |
| WR-07 | `request_id` is logged and is not on `LOGGABLE_FIELDS` | Unchanged, and now explicitly routed: `test_no_history_content_reaches_a_log_line.py:20-26` names `schemas.py:442` as what the Phase 6 source gate goes red on |

---

_Reviewed: 2026-08-11_
_Reviewer: Claude (orchestration reviewer)_
_Depth: standard_
