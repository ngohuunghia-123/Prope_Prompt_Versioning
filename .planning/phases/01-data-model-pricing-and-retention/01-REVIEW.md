---
phase: 01-data-model-pricing-and-retention
reviewed: 2026-08-10T00:00:00Z
depth: standard
files_reviewed: 42
files_reviewed_list:
  - Makefile
  - alembic.ini
  - alembic/README
  - alembic/ddl.py
  - alembic/env.py
  - alembic/script.py.mako
  - alembic/versions/0001_roles_and_schemas.py
  - alembic/versions/0002_call_record.py
  - alembic/versions/0003_ledger_tables.py
  - pyproject.toml
  - ruff.toml
  - src/prope/__init__.py
  - src/prope/call_ledger/__init__.py
  - src/prope/call_ledger/domain.py
  - src/prope/call_ledger/models.py
  - src/prope/call_ledger/pricing.py
  - src/prope/call_ledger/repricing.py
  - src/prope/call_ledger/retention.py
  - src/prope/call_ledger/writer.py
  - src/prope/db/__init__.py
  - src/prope/db/engine.py
  - src/prope/db/metadata.py
  - src/prope/db/session.py
  - tests/__init__.py
  - tests/architecture/__init__.py
  - tests/architecture/test_schema_invariants.py
  - tests/architecture/test_tenant_coverage.py
  - tests/conftest.py
  - tests/integration/__init__.py
  - tests/integration/test_body_retention_delete.py
  - tests/integration/test_migration_chain.py
  - tests/integration/test_reprice_only_unpriced.py
  - tests/integration/test_write_path.py
  - tests/security/__init__.py
  - tests/security/test_append_only_privilege.py
  - tests/security/test_call_record_guarantees.py
  - tests/security/test_tenant_isolation.py
  - tests/unit/__init__.py
  - tests/unit/test_cost_arithmetic.py
  - tests/unit/test_effective_dated_pricing.py
  - tests/unit/test_missing_price_is_unpriced_not_zero.py
  - tests/unit/test_unknown_usage_never_zero.py
findings:
  critical: 1
  warning: 8
  info: 7
  total: 16
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-08-10
**Depth:** standard
**Files Reviewed:** 42
**Status:** issues_found

## Summary

The phase's flagship invariants hold under adversarial reading, and I want to
be specific about which ones I tried to break and could not:

- **Tenant identifiers are bound everywhere.** `src/prope/db/session.py:41`
  uses `set_config(..., :ws, true)` rather than an interpolated `SET LOCAL`;
  `retention.py` binds `:ws`; `pricing.py` binds all four values. There is no
  f-string, `%`-format or concatenation carrying a runtime value into SQL
  anywhere in `src/`. The only interpolation in the tree is in
  `alembic/ddl.py`, over module constants and revision-supplied identifiers.
- **The RLS predicate is uncast text** (`alembic/ddl.py:87`) and the
  two-argument `current_setting` is used, so a missing filter yields zero rows.
  No `::uuid` appears anywhere.
- **No new `SECURITY DEFINER` function**, no native enum, no float column, and
  `created_at` carries no default. Each is asserted against the live catalogue,
  not against the migration source.
- **Money is `Decimal` end to end** and `compute_cost` refuses a non-`Decimal`
  price rather than coercing.
- **`prope_app` holds no `DELETE` on `call_record` or `price_table`.** The
  retention path deletes bodies only, and the `ctid` CTE is snapshot-safe
  because the CTE and the `DELETE` are one statement.
- The test suite is unusually honest: nearly every negative assertion carries a
  positive control, and `test_the_append_only_refusal_has_teeth` is a genuine
  mutation check.

What the executors did not catch is a state the schema **permits** and the
write path **cannot represent**: a price row that computes a cost of zero. It
is reachable by a single legal `INSERT`, it fails the whole batch rather than
the one record, and because `price_table` has neither `UPDATE` nor `DELETE`
granted, the resulting state cannot be undone. That is CR-01 and it is the one
finding I would block a ship on. The remaining eight warnings are real but
bounded: an unguarded loop, a read-then-write race on the currency invariant,
an unbounded repricing transaction, a deploy path that revision 0001 breaks,
and a documented control (`session.py`'s "source gate") that does not exist.

## Critical Issues

### CR-01: A zero-cost price row is legal, unrepresentable, and unrecoverable — it halts the write path and repricing permanently

**Files:**
- `alembic/versions/0003_ledger_tables.py:136-137` (the permissive CHECK)
- `src/prope/call_ledger/pricing.py:127-131` (produces the zero)
- `src/prope/call_ledger/writer.py:237-250` (refuses the whole batch)
- `src/prope/call_ledger/repricing.py:172-180` (refuses the whole pass)
- `alembic/versions/0003_ledger_tables.py:256` (no `UPDATE`/`DELETE` to undo it)

**Issue:** Three decisions that are individually defensible combine into an
irrecoverable failure state.

1. `ck_price_table_prices_are_non_negative` is `CHECK (input_price_per_1k >= 0
   AND output_price_per_1k >= 0)`. A row with both prices `0` — the obvious
   thing an operator enters for a free-tier or self-hosted model — is accepted.
   So is any price small enough that a short call quantises below `1e-10`.
2. `compute_cost` then returns exactly `Decimal("0E-10")`. This is not
   speculative: the project's own `tests/unit/test_cost_arithmetic.py:158-161`
   asserts `compute_cost(1, 0, tie) == Decimal("0")` for a legal
   `input_price_per_1k = Decimal("0.00000005")`.
3. `write_records` raises `ValueError` for that record, and because the batch
   is all-or-nothing, **every other record in the batch is discarded too**.
   Phase 2's drain will re-deliver the same batch and hit the same raise
   forever — a poison batch. `reprice_unpriced` behaves identically: one poison
   candidate aborts the whole pass for the workspace.

The trap closes at T-006. `price_table` is granted `SELECT, INSERT` only, so
the offending row can be neither corrected nor removed. Superseding it with a
later `effective_from` does not help: calls whose `created_at` falls inside the
zero-priced interval still resolve to the zero row, so `reprice_unpriced` for
that `(provider_config_id, upstream_model)` pair raises on every future run,
permanently. `repricing.py`'s own docstring calls this outcome "a price row
that is itself the problem" — but the schema is what let the problem in, and
the phase's design explicitly forbids taking it back out.

`01-RESEARCH.md:866` anticipates the shape of this failure in a different guise
("turning a rounding decision into a write-path outage") and the fix chosen
there — quantise at the column scale — does not close this hole, because the
hole is a *legal price*, not a rounding choice.

**Fix:** Refuse the unrepresentable state at the boundary where it can still be
refused — the price row — instead of at the boundary where refusing it destroys
records. In a new revision:

```sql
-- A price row must be able to produce a cost. A pair of zeros, or a pair so
-- small that a realistic call quantises to nothing, cannot: ck_call_record_
-- cost_is_never_zero refuses the row it would produce, and price_table has no
-- UPDATE or DELETE grant, so a row that cannot price is a row nobody can undo.
ALTER TABLE ledger.price_table
    DROP CONSTRAINT ck_price_table_prices_are_non_negative,
    ADD  CONSTRAINT ck_price_table_prices_are_non_negative
         CHECK (input_price_per_1k >= 0 AND output_price_per_1k >= 0
                AND (input_price_per_1k > 0 OR output_price_per_1k > 0));
```

That removes the both-zero case. The sub-quantum case survives it, so the
writer must also stop taking the batch down with the record. In
`src/prope/call_ledger/writer.py`, replace the raise with a per-record
downgrade that is loud but not fatal — or, if the "neither answer is true"
argument is to be kept, at minimum isolate the blast radius:

```python
if cost <= 0:
    # Unrepresentable for THIS record. Refusing the batch discards records
    # that are perfectly representable, and a broker redelivery will refuse
    # them again — so the failure is carried on the record, not on the batch.
    raise UnpriceableRecord(draft.call_id, price_row_id, cost)
```

and have the caller (Phase 2's drain, Phase 3's fallback) route the single
record to the DLQ. Whichever branch is taken, add a test that a price row of
`(0, 0)` is refused at insert, and a test that one unpriceable record does not
discard its batch-mates.

## Warnings

### WR-01: `delete_expired_bodies(chunk_size=0)` loops forever, opening a transaction per iteration

**File:** `src/prope/call_ledger/retention.py:114-170`
**Issue:** `chunk_size` is a public keyword argument with no validation.
`LIMIT 0` deletes nothing, so `deleted_in_chunk` is `0`; the termination test
is `if deleted_in_chunk < chunk_size` — `0 < 0` is false — and `max_chunks`
defaults to `None`. The loop never exits, and each iteration opens a fresh
transaction and issues a `DELETE`, so the process hammers the database
indefinitely rather than failing. A negative `chunk_size` at least raises
(`LIMIT must not be negative`); zero is the silent one.
**Fix:** Reject the value where it enters, before the loop:

```python
if chunk_size < 1:
    raise ValueError(f"chunk_size must be at least 1, got {chunk_size}")
if max_chunks is not None and max_chunks < 1:
    raise ValueError(f"max_chunks must be at least 1 or None, got {max_chunks}")
```

### WR-02: The one-currency-per-workspace invariant is enforced by a read-then-write race

**File:** `src/prope/call_ledger/writer.py:322-339`
**Issue:** `READ_SPEND_CURRENCY` is executed, compared, and only then is
`UPSERT_WORKSPACE_SPEND` issued. Two concurrent transactions writing the same
`(workspace_id, period_month)` in different currencies both read `NULL` (or
both read the same pre-existing value), both pass the check, and then serialise
on the primary-key index. The second one takes the `DO UPDATE` branch, where
`total_cost = COALESCE(existing, 0) + EXCLUDED.total_cost` sums across
currencies and `currency = COALESCE(existing.currency, EXCLUDED.currency)`
keeps the *first* label. The stored row is then a USD-labelled total containing
VND — precisely the "number with no unit" A-107 forbids, and the CHECK
constraint cannot see it because a currency *is* present. Nothing in Phase 1
serialises drains per workspace, and Phase 2 is not obliged to.
**Fix:** Move the invariant into the statement, so the engine and not the
sequence of two statements enforces it:

```sql
ON CONFLICT (workspace_id, period_month) DO UPDATE SET
    ...
WHERE ledger.workspace_spend.currency IS NULL
   OR EXCLUDED.currency IS NULL
   OR ledger.workspace_spend.currency = EXCLUDED.currency
```

and treat `result.rowcount == 0` on a conflicting upsert as the mismatch,
raising the same `ValueError`. Keep the pre-read for the friendlier message if
desired, but stop relying on it.

### WR-03: `reprice_unpriced` is unbounded — one transaction, one round trip per candidate, all-or-nothing

**File:** `src/prope/call_ledger/repricing.py:138-196`
**Issue:** `SELECT_CANDIDATES` has no `LIMIT` and the result is materialised
with `.all()`. Every candidate then costs one `resolve_price` round trip plus
one `UPDATE`, all inside the caller's single transaction. On a real backlog —
and the unpriced worklist exists precisely because backlogs happen — this holds
`UPDATE` row locks on the largest table in the system for the duration of the
whole pass, keeps one snapshot open, and discards every applied update if any
one candidate raises (which CR-01 makes reachable). This is the exact hazard
`retention.py:20-29` argues against at length for the delete path; the
repricing path was not given the same treatment.
**Fix:** Give repricing the shape retention already has — a bounded chunk, its
own transaction per chunk, driven from a sessionmaker:

```python
SELECT_CANDIDATES = text(
    """
    SELECT ... FROM ledger.call_record
    WHERE  cost_status = 'unpriced' AND ...
    ORDER  BY created_at
    LIMIT  :chunk_size
    """
)
```

with the loop terminating on a short chunk, exactly as `delete_expired_bodies`
does. Repricing is idempotent by its status predicate, so chunking costs
nothing in correctness.

### WR-04: Revision 0001 revokes the privilege the migration chain needs to record itself

**File:** `alembic/versions/0001_roles_and_schemas.py:68`
**Issue:** `REVOKE ALL ON SCHEMA public FROM PUBLIC` removes `USAGE` (not only
`CREATE`) from `PUBLIC`, and `public.alembic_version` is where `env.py:99` pins
the version table. Nothing grants `prope_migrate` any privilege on schema
`public`. The rig passes because the container's connection is a superuser, but
the file's own docstring contemplates the other supported path — "the attribute
becomes a documented out-of-band bootstrap step", i.e. a non-superuser
`prope_migrate`. On that path the `INSERT INTO public.alembic_version` that
follows `upgrade()` fails with `permission denied for schema public`, and the
chain cannot be run at all. `alembic/ddl.py:37-39` already half-notices this
("Alembic's own write to `public.alembic_version` ... holds no privilege
there") but treats it as a `RESET ROLE` concern only.
**Fix:** Grant back what the chain needs, in the same revision that takes it
away:

```python
op.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
# The version table lives here (env.py pins version_table_schema="public"), so
# the migration role needs its own grant now that PUBLIC has none.
op.execute("GRANT USAGE, CREATE ON SCHEMA public TO prope_migrate")
```

and add an assertion to `tests/integration/test_migration_chain.py` that
`has_schema_privilege('prope_migrate', 'public', 'USAGE')` is true.

### WR-05: Intra-schema foreign keys bypass RLS — a cross-tenant existence oracle and bodies that escape retention

**Files:** `alembic/versions/0003_ledger_tables.py:88-89, 222-226`
**Issue:** `0002_call_record.py:29-31` and
`tests/architecture/test_schema_invariants.py:132-136` both state the principle
correctly: "referential-integrity checks always bypass row security, so a
foreign key from a tenant-scoped table ... is a covert channel". The mitigation
adopted was "no foreign key leaves `ledger`" — but the property that makes an FK
a covert channel is the RLS bypass, not the schema boundary. Both FKs added
here join two tenant-scoped tables:

- `fk_call_body_call_id` lets a `call_body` row stamped for workspace B
  reference workspace A's `call_record`. `WITH CHECK` constrains only
  `call_body.workspace_id`, and the FK check does not see the policy. Such a
  row is invisible to A and is never deleted by A's retention sweep, which
  filters on `call_body.workspace_id` — raw end-user payloads outliving their
  window with no owner.
- `pk_call_record` is `(call_id)` alone, not `(workspace_id, call_id)`, and
  `call_id` is caller-supplied (`domain.py:114-127`). A caller can therefore
  distinguish "this id exists in another workspace" (unique violation) from
  "it does not" (success) — a refusal shape that is not byte-identical across
  tenants, which the project's own refusal-shape rule cares about.

No shipped Phase 1 code creates such a row; the writer stamps body and record
from the same draft. The exposure arrives with Phase 3's caller-supplied ids.
**Fix:** Make the FK carry the tenant, so the reference cannot cross a
workspace:

```sql
ALTER TABLE ledger.call_record
    ADD CONSTRAINT uq_call_record_call_id_workspace_id
    UNIQUE (call_id, workspace_id);

ALTER TABLE ledger.call_body
    DROP CONSTRAINT fk_call_body_call_id,
    ADD  CONSTRAINT fk_call_body_call_id
         FOREIGN KEY (call_id, workspace_id)
         REFERENCES ledger.call_record (call_id, workspace_id);
```

and the same treatment for `fk_call_record_price_row_id` against
`price_table (price_row_id, workspace_id)`. Extend
`test_schema_invariants.py` to assert that every FK on a tenant-scoped table
includes `workspace_id`, rather than only that it stays inside `ledger`.

### WR-06: Token counts have no non-negativity constraint in the schema or the draft

**Files:** `alembic/versions/0002_call_record.py:70-71`,
`src/prope/call_ledger/domain.py:162-173`
**Issue:** The phase forbids a zero standing in for an absence with a
table-level CHECK, but nothing forbids a *negative* count. `CallRecordDraft.__post_init__`
validates timezone-awareness and both-or-neither, not sign or type. An
`input_tokens = -300` draft passes the draft check, passes
`ck_call_record_unknown_usage_is_null`, produces a negative contribution in
`compute_cost`, and — provided the other side keeps the total positive — is
stored with a silently understated cost that `ck_call_record_cost_is_never_zero`
happily accepts. Relatedly, `compute_cost` guards the *price* types rigorously
(`pricing.py:117-125`) but applies `Decimal(input_tokens)` to whatever it is
handed, so the type discipline is one-sided.
**Fix:** Constrain it where "no row anywhere" is already stated — the table:

```sql
CONSTRAINT ck_call_record_token_counts_are_non_negative
    CHECK ((input_tokens IS NULL OR input_tokens >= 0)
       AND (output_tokens IS NULL OR output_tokens >= 0))
```

and add the sign check to `__post_init__` beside the existing pair check so the
caller learns which record is wrong rather than which statement failed.

### WR-07: `session.py` claims a source gate that does not exist

**File:** `src/prope/db/session.py:13-14`
**Issue:** "There is no interpolation of any kind in this module, and a source
gate asserts it." No such test exists anywhere in the suite — grepping the tree
for `getsource`, `inspect.`, or any source-text assertion returns nothing.
`test_workspace_id_containing_a_quote_round_trips_unchanged`
(`tests/security/test_tenant_isolation.py:107`) proves the *current*
implementation binds correctly, which is not the same thing: it would still
pass against an f-string that happened to escape the quote, and it would not
notice a second statement added to the module later. The docstring's whole
argument is that the tempting repair is interpolation — so the control it names
is the one that matters.
**Fix:** Either write the gate or delete the claim. The gate is four lines:

```python
def test_the_tenant_seam_contains_no_string_interpolation():
    source = inspect.getsource(prope.db.session)
    assert "f\"" not in source and "f'" not in source
    assert "%" not in source and ".format(" not in source
    assert "+ workspace_id" not in source
```

### WR-08: `make check` mutates the working tree and can never fail on formatting

**File:** `Makefile:16-22`
**Issue:** `check: lint format test` invokes `ruff format`, which rewrites
files in place and exits 0 regardless. A verification target that edits the code
it is verifying cannot gate anything, and in CI it either reports success over
a dirty tree or silently reformats before the tests run.
**Fix:**

```make
format:
	uv run ruff format src/ tests/ alembic/

format-check:
	uv run ruff format --check src/ tests/ alembic/

check: lint format-check test
```

## Info

### IN-01: `RepriceResult.examined` under-reports when an update matches nothing

**File:** `src/prope/call_ledger/repricing.py:182-196`
**Issue:** `repriced += result.rowcount` is correct, but when a concurrent
writer has priced the row between the select and the update, `rowcount` is 0
and `left_alone` is not incremented either — so `examined` (line 110) is less
than the number of candidates actually examined. The docstring says the two
counters partition the candidate set; they do not.
**Fix:** Add a third counter (`raced` or `already_priced`) incremented when
`result.rowcount == 0`, and include it in `examined`.

### IN-02: `domain.py` describes an upsert the writer does not perform

**File:** `src/prope/call_ledger/domain.py:116-119`
**Issue:** "that is what makes a broker redelivery safe, because the writer can
upsert on it rather than counting a record into a workspace's spend twice."
`INSERT_CALL_RECORD` is a plain insert; a redelivery raises `IntegrityError` and
takes the batch with it. `01-03-SUMMARY.md:324` records this correctly as Phase
3 scope, so the code is in scope — the docstring is what overstates.
**Fix:** Change "can upsert" to "will upsert (Phase 3, CL-02); today a
redelivery is refused by `pk_call_record` and the batch rolls back".

### IN-03: The highest-liability grant in the phase is made by a defaulted keyword with no comment

**File:** `alembic/versions/0003_ledger_tables.py:252`
**Issue:** Every other grant line in this revision carries a written reason.
`grant_table("ledger", "call_body", app_privileges=[...])` silently takes
`report_select=True`, handing `prope_report` — which is `BYPASSRLS` — `SELECT`
on the one table holding raw end-user request and response bodies across every
workspace. The risk is explicitly accepted upstream (T-01-12, ADR-0037,
Discretion §6), so this is not a new decision; it is a decision that is
invisible at the call site.
**Fix:** Make it explicit so a reader of the migration sees it:
`grant_table(..., report_select=True)  # T-01-12: accepted, ADR-0037 — full-read credential over raw bodies`.

### IN-04: `retention_window` is unvalidated

**File:** `src/prope/call_ledger/writer.py:175, 296`
**Issue:** `expires_at = draft.created_at + retention_window`. A zero or
negative `timedelta` stamps every body as already expired, and the next
retention sweep deletes them — a silent data-loss path behind a single wrong
argument. Phase 2 will read this value from a per-workspace setting.
**Fix:** `if retention_window <= timedelta(0): raise ValueError(...)` at the
top of `write_records`.

### IN-05: `max_chunks=0` still runs one chunk

**File:** `src/prope/call_ledger/retention.py:167-168`
**Issue:** The bound is checked after the chunk executes, so "at most zero
chunks" deletes up to `chunk_size` rows. Harmless today (no caller passes 0)
and covered by WR-01's validation if that is adopted.
**Fix:** Included in WR-01's guard, or move the check to the top of the loop.

### IN-06: Revision 0001's downgrade does not undo its public-schema revoke

**File:** `alembic/versions/0001_roles_and_schemas.py:71-76`
**Issue:** `upgrade()` issues `REVOKE ALL ON SCHEMA public FROM PUBLIC`;
`downgrade()` drops the schema and the roles but leaves the revoke in place, so
downgrading does not return the cluster to its prior state. For a
cluster-scoped side effect that is worth being deliberate about.
**Fix:** Either restore it (`GRANT USAGE ON SCHEMA public TO PUBLIC`) or state
in the docstring that the revoke is intentionally one-way.

### IN-07: The test rig builds `ALTER ROLE ... PASSWORD` by f-string

**File:** `tests/conftest.py:94`
**Issue:** `text(f"ALTER ROLE {role} WITH PASSWORD '{password}'")`. The values
come from the `TEST_ROLE_PASSWORDS` module constant and the container is
destroyed at session end, so there is no exploitable path today — but this is
the only string-assembled SQL in the tree, and it sits in the file that a
future contributor will copy when they need a second rig. If the password ever
comes from an environment variable, it becomes an injection site.
**Fix:** Assemble the identifier only, and note why the value cannot be bound
(`ALTER ROLE` takes no parameters), or move the password assignment into the
container's init so no SQL is built at all.

---

_Reviewed: 2026-08-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
