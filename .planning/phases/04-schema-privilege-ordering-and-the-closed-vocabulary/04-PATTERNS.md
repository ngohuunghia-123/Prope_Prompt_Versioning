# Phase 4: Schema, privilege, ordering, and the closed vocabulary - Pattern Map

**Mapped:** 2026-08-10
**Files analyzed:** 12 new / 4 modified
**Analogs found:** 15 / 16 (10 exact, 5 role-match, 1 placement with no precedent)

> **Read this as "copy from here", not "follow this spirit".** Every excerpt below is real text in
> this repository at the line numbers given, read in full rather than inferred from a filename. The
> single most transferable property of the Phase 1–2 code is **the module docstring carries the *why*
> at length, naming the ADR / assumption / OQ and the rejected alternative**. Every file this phase
> creates is expected to match that density — the planner should treat the docstring as a
> deliverable, not as decoration.
>
> **Two things in this file are corrections to `04-CONTEXT.md`, made by reading the files.** They are
> **agent judgements, not detector results** — no `api-coverage.cjs`, no assumption-delta detector and
> no edge probe exists in this environment, and none was run. They are flagged inline as
> **[AGENT JUDGEMENT]** where they occur:
> 1. **Four** of the five generic tests in `tests/architecture/test_schema_invariants.py` carry
>    `ledger` in their function name, not two (D-49 says two).
> 2. **Three** Phase 1 test files name the `ledger` schema by name, not two (D-47/D-48 name
>    `test_tenant_coverage.py` and `conftest.py`). The third is
>    `tests/integration/test_migration_chain.py`, and it is the dangerous one, because unlike the
>    other two it does **not** go red — it silently stops covering the new schema.
>
> **One spec conflict was found here and filed rather than absorbed:**
> `docs/brainstorm/open_questions/OQ-030.md` — the lock file declares
> `prope_property_history_rows_total` labelled by `workspace_id`, and
> `tests/broker/test_publish_confirm_failures.py:239-250` already asserts that no `prope_*` metric may
> carry one. That metric is Phase 6's, so this phase is not blocked; the question is filed so Phase 6
> inherits it rather than discovering it as a red test in another module's package.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `alembic/versions/00NN_history_schema.py` | migration | batch / DDL | `alembic/versions/0004_workspace_retention.py` | **exact** |
| `src/prope/property_history/__init__.py` | package doc | — | `src/prope/call_ledger/__init__.py` | **exact** |
| `src/prope/property_history/domain.py` | model (vocabularies + value objects) | transform / validation | `src/prope/call_ledger/domain.py` | **exact** |
| `src/prope/property_history/models.py` | model (Core tables) | — | `src/prope/call_ledger/models.py` | **exact** |
| `src/prope/property_history/registry.py` | service (read-once, process-lifetime cache) | request-response (read-all) + process state | `call_ledger/pricing.py` (query constant) + `call_ledger/enqueue.py:76-101` (lazy process-wide state) | role-match |
| `src/prope/property_history/append.py` | service (validate + insert on the **caller's** session) | request-response (write) | `src/prope/call_ledger/writer.py` | role-match |
| `src/prope/property_history/observability.py` | config (one counter) | — | `src/prope/observability.py` | role-match |
| `tests/security/test_history_is_append_only_by_privilege.py` | test | — | `tests/security/test_append_only_privilege.py` | **exact** |
| `tests/security/test_the_vocabulary_gate_is_python_only.py` (D-62's asserted absence) | test | — | `tests/security/test_eval_no_body_boundary.py` | **exact** |
| `tests/integration/test_same_transaction_events_have_a_stable_order.py` | test | — | `tests/integration/test_body_retention_delete.py` | role-match |
| `tests/unit/test_unregistered_detail_key_fails_the_transaction.py` | test | — | `test_eval_no_body_boundary.py` (whole-batch refusal) + `test_ceiling_refuses_evals_only.py:116` (counter delta) | role-match |
| shared history fixture helpers (`tests/unit/__init__.py` extension **or** a new package) | test rig | fixture | `tests/unit/__init__.py`, `tests/security/__init__.py` | shape **exact**, placement **no precedent** |
| `tests/conftest.py` (**modified**) | test rig | fixture | same file, the Postgres rig | **exact** |
| `tests/architecture/test_tenant_coverage.py` (**modified**) | test | — | same file | **exact** |
| `tests/architecture/test_schema_invariants.py` (**modified**) | test | — | same file | **exact** |
| `tests/integration/test_migration_chain.py` (**modified — not named in CONTEXT**) | test | — | same file | **exact** |

**Files this phase must NOT create, and the pattern each would otherwise pull in:**
`src/prope/property_history/api.py` (no router — D-65, PH-07), `schemas.py` (no wire types — there is
no HTTP surface and no broker envelope), `envelope.py` (nothing crosses a process boundary), and any
edit to `src/prope/app.py` or `src/prope/worker.py` (D-13's composition is Phase 5's wiring). See
**§ Patterns that do NOT apply** below, which is not optional reading: a planner scanning a pattern
list assumes every entry is binding.

---

## Pattern Assignments

### `alembic/versions/00NN_history_schema.py` (migration, DDL)

**Analog:** `alembic/versions/0004_workspace_retention.py` for the docstring and the argued-deviation
posture; `alembic/versions/0003_ledger_tables.py` for the multi-table body; and
`alembic/versions/0001_roles_and_schemas.py:60-63` for the two lines no revision since has needed.
Copy all three.

**The revision header, and the one import comment that is load-bearing** (`0003:41-54`):

```python
from collections.abc import Sequence

# `alembic/ddl.py`, imported by bare name rather than as `alembic.ddl` — that
# dotted name resolves to the installed Alembic package's own dialect-DDL
# submodule. `alembic.ini`'s prepend_sys_path puts this directory on the path.
from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
```

→ The comment is repeated verbatim in `0004:93-95`; repeat it again. `alembic.ini:20-33` carries the
same reasoning at the setting itself, including *why it must be in the ini rather than in `env.py`*:
`alembic heads` and `alembic history` load revision files **without ever running `env.py`**.
**`down_revision` is not written by the planner** (D-46, ORCHESTRATION §3): phase 3 moves the head
first, so the executor reads `uv run alembic heads` and wires it then.
`tests/integration/test_migration_chain.py:154-161` asserts exactly one head, so a guessed parent is
a red test rather than a merge revision.

**Only `op.execute` with raw SQL. Never `op.create_table`.** Verified across all four revisions —
there is not one call to Alembic's schema-construction API in this repository. Autogenerate output
is never trusted (`alembic/env.py:53-60`: *"it cannot see RLS policies, grants or triggers, and the
first autogenerate after a policy lands proposes dropping what it cannot see"*).

**The schema, and the `AUTHORIZATION` clause D-46 rests on** (`0001:60-63`) — the only place in the
repository these two lines exist:

```python
    # ADR-0027 — one schema per module, owned by the migration role. The
    # AUTHORIZATION clause is what makes prope_migrate the owner of everything
    # created inside it, which is what ADR-0035's owner bypass rests on.
    op.execute("CREATE SCHEMA ledger AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA ledger TO prope_app, prope_report")
```

→ `history` is the second schema ever created and the first created outside revision `0001`. Note
what `0001` does **not** do that this revision must: it never calls `assume_migrate_role()`, because
it runs as the superuser and creates the roles themselves. This revision does both — `CREATE SCHEMA
... AUTHORIZATION` **and** the `assume_migrate_role()` / `reset_role()` wrapper `0002`, `0003` and
`0004` all use (`ddl.py:27-46`). `assume_migrate_role`'s docstring states the pairing rule and the
consequence of forgetting it: *"Pair it with `reset_role` before the revision ends, or Alembic's own
write to `public.alembic_version` is attempted as `prope_migrate`, which holds no privilege there."*

**Table DDL as a module-level string constant, with the reasoning in SQL comments**
(`0003:57-91`, `0004:107-145`). Every non-obvious column carries a comment saying *why*, and the
comment is the argument, not a restatement of the type:

```python
CREATE_WORKSPACE_RETENTION = """
CREATE TABLE ledger.workspace_retention (
    -- A value, not a reference: the `access` schema does not exist until phase 7
    -- and call-ledger may not reference it even then. It is also what ADR-0045's
    -- coverage walk looks for, so the column name is load-bearing twice over.
    workspace_id      text         NOT NULL,
    ...
    CONSTRAINT pk_workspace_retention PRIMARY KEY (workspace_id),

    -- T-02-11. A zero or negative window makes every body written after it
    -- expire at or before the instant it was written ...
    CONSTRAINT ck_workspace_retention_window_is_positive
        CHECK (retention_window > interval '0')
);
"""
```

**Constraint names are hand-written to match `NAMING_CONVENTION`, and nothing enforces that.**
`src/prope/db/metadata.py:23-29` declares `"ck": "ck_%(table_name)s_%(constraint_name)s"` — but that
convention only renders names for DDL SQLAlchemy emits, and this project emits none
(`models.py:8-14`: *"`metadata.create_all` is never called in this project"*). So the convention is
imitated **by hand in the SQL text**: `ck_price_table_prices_are_non_negative`
(table `price_table`, rule `prices_are_non_negative`),
`ck_workspace_retention_window_is_positive`. Follow it exactly, because
`metadata.py:14-16` states what it buys: *"a security test can assert **which** constraint refused a
write rather than only that something did"*, which is precisely D-54's requirement that each of the
four named CHECKs be individually assertable.

**Identifier length is not automatic. [AGENT JUDGEMENT]** PostgreSQL truncates an identifier past 63
bytes silently, and a later `DROP CONSTRAINT` by the untruncated name then fails. The longest name
this phase needs is `ix_history_event_workspace_id_target_type_target_id_seq` at **55 characters** —
under the limit, counted rather than assumed. Every other name in D-54/D-55 is shorter. Say so in the
plan so the next planner does not have to re-count.

**Index authoring** (`0002:151-171`, `0003:201-214`) — a tuple of statement strings, each preceded by
a comment naming the query it serves and, where relevant, the phase that will run it:

```python
# Every index leads with workspace_id, as every declared index in Prope does.
CREATE_INDEXES = (
    """
    CREATE INDEX ix_call_record_workspace_id_created_at
        ON ledger.call_record (workspace_id, created_at DESC)
    """,
    # get_run_totals lands in phase 2; cheap to add now, awkward to add later
    # on what becomes the largest table in the system.
    """
    CREATE INDEX ix_call_record_workspace_id_run_id
        ON ledger.call_record (workspace_id, run_id)
        WHERE run_id IS NOT NULL
    """,
)
```

→ `0002:151`'s one-line comment — *"Every index leads with `workspace_id`, as every declared index in
Prope does"* — is a project-wide rule and D-55's four indexes all satisfy it already. The
"cheap now, awkward later" comment at `0002:164-165` is the exact register D-55's comments should
take, because D-55 is the same argument on the one table that only ever grows (A-121). Index names
follow a **looser hand convention than the constraint one**: `ix_<table>_<every column in order>`,
not `NAMING_CONVENTION`'s `ix_%(column_0_label)s`. Follow the hand convention; the four existing
indexes all do.

**The `upgrade()` body's ordering, and the grant-comment register** (`0003:229-264`):

```python
def upgrade() -> None:
    """Create the remaining four owned tables with their whole guarantee stack."""
    assume_migrate_role()

    op.execute(CREATE_CALL_BODY)
    ...
    for statement in CREATE_INDEXES:
        op.execute(statement)

    for table in ("call_body", "price_table", "workspace_spend", "spend_ceiling"):
        enable_tenant_rls("ledger", table)

    # T-006 / D-07. No UPDATE and no DELETE, ever. This is the privilege the
    # phase's irreversibility claim rests on.
    grant_table("ledger", "price_table", app_privileges=["SELECT", "INSERT"])

    reset_role()
```

Order: tables → indexes → deferred FKs → `enable_tenant_rls` per table → `grant_table` per table →
`reset_role()`. **The registry seed has no precedent and needs a placement decision**: it must run
after `CREATE TABLE history_action_registry` and **before** any `history_event` row could exist, and
D-57's composite FK means the seed must land in this same revision or the first append is a race
(D-59). Put it with the tables, before the policy/grant block, so the whole guarantee stack still
reads top-to-bottom.

**`enable_tenant_rls` is called in the revision that creates the table, never a later one**
(`0004:154-157`), with the reason written at the call:

```python
    # T-02-09. In the same revision that creates the table, never a later one:
    # the window between the two would be a table `prope_app` can read across
    # tenants, and ADR-0045's walk is what makes forgetting this a red test.
    enable_tenant_rls("ledger", "workspace_retention")
```

→ `history_event` gets exactly this. `history_action_registry` gets **no** `enable_tenant_rls` call
at all (D-56) — and because the coverage walk would then fail it, the `GLOBAL_TABLES` entry is part
of the same change, not a follow-up.

**`grant_table`'s positive form is already argued in the helper** (`ddl.py:105-119`), which is why
D-50 does not issue the lock file's literal `REVOKE UPDATE, DELETE`:

```python
    """The grant matrix for one table (D-07, ADR-0037, T-006).

    ``REVOKE ALL ... FROM PUBLIC`` is the baseline, then exactly the named
    privileges to the runtime role. Granting only what is needed is preferred
    over ``GRANT ALL`` followed by a ``REVOKE``: both end in the same state and
    the positive form is the one a reviewer can read.
    ...
    There is deliberately no ``ALTER DEFAULT PRIVILEGES``. A future table
    should arrive with no privileges until somebody writes them.
    """
```

→ `grant_table("history", "history_event", app_privileges=["SELECT", "INSERT"])` and
`grant_table("history", "history_action_registry", app_privileges=["SELECT"])`. `report_select`
defaults `True`; `0004:163-168` is the precedent for **taking the default with a written reason
rather than inheriting it silently** — CONTEXT lists this as a discretion item and that comment is
the shape the answer takes:

```python
    # `report_select` takes its default of True, which resolves the discretion
    # item Phase 1 carried forward on this table's read grants. A retention
    # window is a policy setting rather than a body, and ADR-0037 already records
    # `prope_report` as a full-read credential; withholding SELECT here would
    # make the reporting role unable to explain why a body is still present.
```

**`downgrade()` drops in reverse dependency order** (`0003:267-275`), and a schema-creating revision
drops its schema too (`0001:71-76` uses `DROP SCHEMA IF EXISTS ledger CASCADE`). This revision owns
both halves: drop the two tables (registry last — the FK points at it), then the schema.
`0004:178-184`'s downgrade docstring is the precedent for **stating what a downgrade does not
undo** — here, nothing, because no other schema references `history`.

**The declared-deviation posture** (`0004:12-27`) is the shape D-53 (`GENERATED ALWAYS` vs the lock's
`bigserial`) and D-50 (the absent `REVOKE`) need, restated at the revision so a reader does not have
to find the CONTEXT file:

```python
**D-09 — THIS IS A SIXTH TABLE, AND THE LOCK FILE NAMES FIVE.**
``docs/modules/call-ledger.lock.yml`` ``data.owns`` lists ... This is a
deviation from that field and it is declared rather than absorbed: the conflict
is raised as ``docs/brainstorm/open_questions/OQ-018.md``, naming the field, and
per ``.planning/BSP-LINK.md`` the spec is NOT edited to agree.
```

**The refused-mechanism-with-an-asserted-absence pattern** (`0004:57-81`) is D-62's template, and the
CONTEXT is right that only two of its three reasons transfer — make the argument freshly:

```python
**THE A-055 GUARD THIS REVISION DELIBERATELY DOES NOT ADD.**
... It is refused for three reasons, recorded here as a **knowing exception to
this project's database-first pattern** rather than left as an oversight:
1. It would put a per-row lookup on the highest-volume insert path in the system.
2. ``write_records`` is already the single choke point, and it already refuses ...
3. ``docs/modules/call-ledger.lock.yml`` never asked for the trigger, and
   ``.planning/BSP-LINK.md`` forbids inventing schema the spec did not declare.

Because the guarantee lives in Python and not in the engine, the ABSENCE is
asserted rather than assumed: ``tests/security/test_eval_no_body_boundary.py``
proves both halves ...
```

**The seed statement belongs here and not in `src/`, and the reason is a gate.**
`tests/architecture/test_no_sql_interpolation.py:34` sets `SOURCE_ROOT = .../src/prope` and
`rglob`s it — `alembic/` is outside the walk entirely. A thirty-one-row `INSERT` assembled by joining
names would need an `ALLOWED` entry if it lived in `src/`; written as a plain multi-row `VALUES` list
in the migration it needs nothing. **No revision in this repository has ever inserted a data row**, so
the seed statement itself has no analog — write it as one module-level constant in the shape of
`CREATE_*` above, with the derivation table's provenance in its comment.

**Types follow the existing revisions** (`0003:32-38`, `0004:83-88`): every `*_id` is `text`
(ADR-0003 prefixed ULIDs), every timestamp is `timestamptz` (A-003), and **values are not
references**. This module's only foreign key is D-57's, intra-schema, and `0003:23-30` is the
paragraph that explains why intra-schema is the only permitted kind.

---

### `src/prope/property_history/__init__.py` (package doc)

**Analog:** `src/prope/call_ledger/__init__.py:1-8` — eight lines that state the module's *defining*
property rather than describing its contents:

```python
"""call-ledger — every completed call recorded off the response path.

A sink. ``dependencies: []`` and ``outputs: []`` are this module's defining
property: nothing here may import another bounded context, and no foreign key
leaves the ``ledger`` schema. ``workspace_id``, ``prompt_id``, ``version_id``
and ``provider_config_id`` are values, not references — which is what lets the
audit trail survive independently of the registry's current state.
"""
```

→ property-history's counterpart says the three things D-65 makes structural: the **empty
`consumes` list** (the only one in Prope), **no FastAPI import at any depth**, and `target_id` /
`actor_id` / `workspace_id` as values rather than foreign keys — which is what makes ADR-0054's
tombstone-and-survive free. Also state the inversion that distinguishes it from its nearest
neighbour: **this module never opens a transaction**, where call-ledger's seams always do (D-19).

---

### `src/prope/property_history/domain.py` (model, vocabulary + value objects)

**Analog:** `src/prope/call_ledger/domain.py` — copy the docstring's opening move, which states the
byte-identity rule before anything else (`domain.py:1-14`):

```python
"""The call-ledger vocabulary, as Python values.

Four vocabularies and four value objects. The vocabularies are ``StrEnum`` and
their members' values are **byte-identical to the database CHECK sets** in
``alembic/versions/0002_call_record.py`` — ``priced`` / ``unpriced`` / ...
A native PostgreSQL ``ENUM`` was rejected (Pitfall 4); the vocabulary lives in a
``CHECK`` and is mirrored here so Python can type-check against it.

These values stay literal ASCII at rest. ADR-0053 puts Vietnamese behind an i18n
layer that translates a machine ``code`` at the API edge — a status is never
translated in the database, because a stored status is a fact and not a label.
"""
```

**Each enum's docstring names the constraint it mirrors** (`domain.py:36-41`):

```python
class CostStatus(StrEnum):
    """``ck_call_record_cost_status_values``. There is no fourth state."""
```

→ `ActorType` here names `ck_history_event_actor_type_values` and has no third state.
**D-63's rejection-reason `StrEnum` is the same discipline pointed at a different artifact**: its
members are byte-identical to the metric's declared label set
(`unknown_action | unknown_detail_key | missing_reason`) rather than to a CHECK set. CONTEXT leaves
open whether that identity is asserted by a test or by proximity; `domain.py`'s own precedent is
proximity plus a docstring, and `prope/observability.py:81-88` is the counterpart precedent on the
metric side — the counter's `#:` block states the closed label set in source. Whichever is chosen,
say which, at the definition.

**Value objects are frozen slotted dataclasses whose docstrings say what a field is derived *from***
(`domain.py:83-97`, `183-203`):

```python
@dataclass(frozen=True, slots=True)
class PriceRow:
    """One row of ``ledger.price_table``, as resolved for a given instant.

    Frozen because the table it mirrors is append-only by privilege (T-006). A
    price is superseded by a new row with a later ``effective_from``; nothing —
    in the database or here — edits one.
    """
```

→ A `HistoryEvent` value object is frozen for exactly this reason, one table over, with a stronger
claim behind it.

**Validation in `__post_init__` raises a full sentence naming the field and the rule**
(`domain.py:162-173`):

```python
    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError(
                f"created_at for {self.call_id} is naive; a naive datetime is read against the "
                "server's time zone, which makes an effective-dated price depend on geography"
            )
```

→ The aware-datetime rule transfers verbatim to `occurred_at`. **The exception class does not**
(D-63) — see § `append.py`.

**`seams.EvalUsageRow.__post_init__`** (`seams.py:147-182`) is the denser variant: a table of
`(field, reason)` pairs, each reason a sentence explaining what the engine requires and where the
model is deliberately stricter than the engine. That is the shape D-54's `actor_type` / `actor_id`
pairing rule wants on the Python side, since the engine already carries
`CHECK (actor_id IS NOT NULL OR actor_type = 'system')`.

---

### `src/prope/property_history/models.py` (model, Core tables)

**Analog:** `src/prope/call_ledger/models.py` — the docstring is the pattern, and three of its
paragraphs transfer unchanged (`models.py:8-29`):

```python
"""**These are not the source of truth for the schema. The migration is** (D-04,
A-128). Nothing here creates, alters or drops anything: ``metadata.create_all``
is never called in this project, and would produce a database missing every RLS
policy, every grant and every REVOKE — that is, a database with none of the
guarantees the tables exist to carry.
...
Each table declares ``schema="ledger"`` explicitly rather than inheriting a
default from the ``MetaData`` (Pitfall 11).
"""
```

**Type aliases at the top, each with the reason it exists** (`models.py:49-53`):

```python
#: A-003: UTC with an explicit offset. The naive type discards it silently.
TIMESTAMPTZ = DateTime(timezone=True)
```

→ `MONEY` does not transfer (no money column in `history`). `TIMESTAMPTZ` does.

**The shared `MetaData` and the drift guard, and how they interact — read this before writing
`models.py`.** `src/prope/db/metadata.py:31` builds **one** `MetaData` with no default schema, and
`test_schema_invariants.py:221` reads `models.metadata.tables.values()` filtered by
`table.schema == SCHEMA`. Registering `history.history_event` on that same object therefore does
**not** break `len(declared) == 6` (`test_schema_invariants.py:226`), because the filter excludes it.
Two consequences the plan should state:

1. `test_every_declared_model_matches_a_live_table` is one of the **three ledger-specific tests that
   stay scoped** (D-49) and its pinned count of six is call-ledger's. A history counterpart is a new
   test with its own pinned count of two, not a parameterisation of that one.
2. A drift guard only sees tables whose module has been **imported**. `test_schema_invariants.py:12`
   does `from prope.call_ledger import models` for exactly that reason; a history guard must import
   `prope.property_history.models` or it will walk an empty declaration set and pass vacuously —
   which is the failure shape `test_tenant_coverage.py:113-115` and
   `test_no_sql_interpolation.py:101-113` both exist to refuse.

---

### `src/prope/property_history/registry.py` (service, process-lifetime cache)

**There is no caching anywhere in this repository**, so the cache itself is § No Analog Found. Two
partial analogs supply everything around it.

**The query constant, with a `#:` block arguing the access path** (`pricing.py:45-60`):

```python
#: The effective-dated lookup. Every identifier is schema-qualified and every
#: value is bound. With the column order of ``uq_price_table_workspace_id``
#: matching the predicate, this is a backward index scan terminating on the
#: first entry: no sort, no filter, one heap fetch.
PRICE_IN_FORCE = text(
    """
    SELECT price_row_id, input_price_per_1k, output_price_per_1k, currency, effective_from
    FROM   ledger.price_table
    WHERE  workspace_id       = :workspace_id
    ...
    """
)
```

→ The registry read is `SELECT action, target_type, detail_keys, requires_reason, writing_module FROM
history.history_action_registry` with **no predicate at all** — and that absence needs its own
sentence, because every other statement in this repository carries a `workspace_id` predicate
alongside the tenant policy (`retention_settings.py:57-61`, `retention.py:33-39`). Here there is no
tenant column (D-56), so there is nothing to write out, and the reason is exactly what makes
`registered_actions()`'s CI consumer able to see rows at all.

**Lazy process-wide state with a test seam** (`enqueue.py:76-101`) — the only precedent for module
state built once and reused:

```python
_handoff: asyncio.Queue[CallRecordDraft] | None = None


def handoff() -> asyncio.Queue[CallRecordDraft]:
    """The process-wide handoff buffer, created on first use.

    Lazy rather than constructed at import: the queue belongs to a running
    event loop's process, and a module-level construction would bind it at
    import time in whichever context imported first.
    """
    global _handoff
    if _handoff is None:
        _handoff = asyncio.Queue(maxsize=HANDOFF_MAXSIZE)
    return _handoff


def reset_handoff() -> None:
    """Drop the handoff so the next call builds a fresh one. Test seam only.

    Nothing on the production path calls this. ...
    """
```

→ **Copy the shape and invert one property.** The handoff is deliberately mutable and reset between
tests by an autouse fixture (`conftest.py:226`); ADR-0038's registry is **immutable for the process
lifetime, with no TTL and no invalidation**, so a `reset_registry()` on the production path would be
the invalidation the ADR says does not exist. The honest version is a loader that takes a session and
returns an immutable mapping, plus whatever module-level holder Phase 5's process-start wiring needs
— and the "test seam only, nothing on the production path calls this" sentence is what keeps the two
apart. Note also that `reset_handoff` is imported *by `conftest.py:80`*, so a test seam in `src/` is
an established and reviewed practice here rather than a smell.

**Absence-is-a-complete-answer, and its limit** (`pricing.py:78-91`, `retention_settings.py:111-114`):
a `None` return is a full answer when the absence has a meaning. It does **not** transfer here: an
empty registry is not "no actions registered", it is a migration that did not run, and D-57's foreign
key makes the first append fail anyway. Say what the loader does with zero rows rather than
inheriting `resolve_price`'s posture by proximity.

---

### `src/prope/property_history/append.py` (service, the D-64 write path)

**Analog:** `src/prope/call_ledger/writer.py` — and this is the one file in the repository whose
transaction posture this module *shares*. `writer.py:9-15` is the paragraph to copy:

```python
"""**The session is handed in and carries exactly one workspace.** It comes from
``workspace_transaction()``, which opened the transaction and set the tenant for
its duration (D-08, ADR-0040). This function therefore opens no transaction,
switches no workspace, and refuses a batch containing a second ``workspace_id``
before writing any of it.
"""
```

and the signature's contract line (`writer.py:171-186`):

```python
async def write_records(
    session: AsyncSession,
    records: Sequence[CallRecordDraft],
    *,
    retention_window: timedelta = DEFAULT_RETENTION_WINDOW,
) -> WriteResult:
    """Price, stamp, insert and aggregate one workspace's batch. All or nothing.

    ``session`` must come from ``workspace_transaction()``. This function does
    not commit; the caller's context manager owns the transaction boundary, so a
    raise anywhere below leaves nothing written.
    """
```

→ **`session: AsyncSession`, never `sessionmaker`.** That single parameter type is the whole of
ADR-0023 in the signature, and it is what makes SC3's "rolls the caller's transaction back with no
partial state" true without this module doing anything. **`seams.py:37-48` is the counter-argument
written down, and it is written down *about this module*** — read it before writing the docstring so
the two files agree:

```python
**Each seam opens its own transaction and never takes the caller's** (D-19).
property-history writes inside its caller's transaction (ADR-0023) and that
pattern is deliberately *not* copied here. Two reasons, and both are specific to
this module: ...
```

**The refusal style — identifier, values in tension, the rule, and why both alternatives are false**
(`writer.py:244-250`, `seams.py:238-253`):

```python
                    raise ValueError(
                        f"{draft.call_id} prices to {cost} against price row {price_row_id}: "
                        f"{draft.input_tokens} input and {draft.output_tokens} output tokens at "
                        f"{price.input_price_per_1k}/{price.output_price_per_1k} per 1k. A priced "
                        "record cannot record a cost of zero, and neither a zero nor a downgrade "
                        "to unpriced would be true"
                    )
```

→ Copy the register. **Do not copy `ValueError`** (D-63). Two precedents exist for a named exception
and they teach different halves:

- `seams._UnevaluableCeilingError` (`seams.py:316-326`) — a bare `Exception` subclass whose entire
  body is a docstring arguing why it is an `Exception` and what path it must take. Private, because
  its only consumer is the function that raises it.
- `session_auth.ManagementRefusal` (`session_auth.py:77-113`) — the public one, carrying structured
  fields and a docstring stating what it is *not* (`"Not an ``HTTPException`` subclass. FastAPI's own
  handler renders ``{"detail": ...}``, which is a second error shape, and A-045 says there is one."`).

**Both carry a lint consequence the plan must not discover in CI.** `ruff.toml:14` selects `N`, so
pep8-naming's **N818** requires an exception class name to end in `Error`.
`session_auth.py:77` handles it with an inline `# noqa: N818` and no explanation:

```python
class ManagementRefusal(Exception):  # noqa: N818
```

→ Either name it `...Error` or repeat the `noqa`. A name five modules will `import` and deliberately
never `except` is worth choosing consciously; either way `uv run ruff check src/ tests/ alembic/` is
the gate (ORCHESTRATION §3) and it will fail on this before anything else does.

**Where a counter is incremented, and how a closed-vocabulary token reaches a label.** The rule is
*increment at the site where the classification is decided*, and pass the enum through `str()`:

```python
        ceiling_failed_open_total.inc()                      # seams.py:457
        log.warning(
            "call_ledger.ceiling_failed_open",
            workspace_id=workspace_id,
            reason=type(error).__name__,                     # the CLASS, never the message
        )
```

```python
            log.info(                                        # seams.py:438-442
                "call_ledger.ceiling_refused",
                workspace_id=workspace_id,
                reason=str(CeilingReason.MONTHLY_CEILING_EXCEEDED),
            )
```

→ `str(...)` on a `StrEnum` member is the house spelling (also `schemas.py:442`). A rejected append
logs *the action and the offending key name, never the offending value* — the lock file's own words —
which is the same "class, never the message" move one level down.

---

### `src/prope/property_history/observability.py` (config, one counter)

**Analog:** `src/prope/observability.py`, whose docstring **scopes itself by phase** and is the reason
D-65 puts this module's counter elsewhere (`observability.py:1-33`):

```python
"""The Phase 2 counters, and only those. ADR-0030.

**A-046, first, because everything below is constrained by it.** No request
body, ... reaches a log line or a metric label ... Metric label cardinality is
bounded by construction: every label declared here has a CLOSED set of values
fixed in source, and ``workspace_id`` — the highest-cardinality identifier in the
system and the one most tempting to add — is deliberately never a label. What a
log line may carry is an ALLOW-LIST (see ``LOGGABLE_FIELDS``), never a deny-list
of field names, because a deny-list fails silently the first time a field is
renamed.
"""
```

**The counter declaration pattern** (`observability.py:80-88`) — a `#:` block that names the label,
enumerates its closed set, and says where the set is fixed:

```python
#: D-21's control. The ``reason`` label has exactly three values and the lock
#: file declares the set: ``unroutable`` | ``nacked`` | ``timeout``. They are the
#: three shapes a publisher confirm can fail in, and the publish path classifies
#: into exactly these and never invents a fourth.
publish_failed_total = Counter(
    "prope_call_ledger_publish_failed_total",
    "Publisher confirms that did not arrive as an ack, by reason.",
    labelnames=("reason",),
)
```

→ `prope_property_history_append_rejected_total` is **the same counter shape with the same label
name and a different closed set** (`unknown_action | unknown_detail_key | missing_reason`). The
parallel is close enough to be worth naming in the docstring, because the lock file's note —
*"Must stay 0 in a correct build"* — is the mirror image of `metadata_dropped_total`'s
(`observability.py:24-32`), which states out loud that it *will not* stay 0 in Phase 2 and why. State
which of the two this counter is.

**`configure_logging()` is not re-declared** (`observability.py:131-153`). It is called from the
process entrypoints and from tests; a second logging configuration in a per-module observability file
would be a second sink. Import `structlog` and do `log = structlog.get_logger(__name__)` the way
every module that logs does (`seams.py:89`, `enqueue.py:55`, `app.py:75`, `worker.py:71`,
`schemas.py:65`).

**The `LOGGABLE_FIELDS` collision is real and it is in this file** (`observability.py:49-67`).
`"reason"` is already a member, with call-ledger's closed-vocabulary meaning, and the `"job"` entry
immediately below it is the precedent for **how an addition to the allow-list is argued in place**:

```python
LOGGABLE_FIELDS = frozenset(
    {
        "event",
        "call_id",
        "workspace_id",
        "reason",
        ...
        #: Added by plan 02-04 on plan 02-03's handoff. ``supervisor.job_crashed``
        #: carries it, and its values are the job-name constants fixed in
        #: ``prope.worker``'s source — a closed set of two, not an identifier and
        #: not a body. Recorded here rather than left in ``deferred-items.md``
        #: because an allow-list with a field outside it is an allow-list
        #: somebody has already stopped believing.
        "job",
    }
)
```

→ **[AGENT JUDGEMENT] `LOGGABLE_FIELDS` is nothing but a `frozenset` today — nothing imports it and
no test compares against it.** Verified by grep across `src/`, `tests/` and `alembic/`: the name
occurs at its own definition (`observability.py:10, 49`) and in four docstrings that *cite* it
(`drain.py:32`, `enqueue.py:31`, `supervisor.py:63`, `test_publish_confirm_failures.py:209`). The
A-046 log assertion that does exist is **marker-based, not set-based** — see the pattern below. So
the collision D-65 names is presently a *documentation* collision rather than a runtime one, and
whatever the plan chooses (per-module set, qualified key, a rule that the set is a floor a module may
subtract from) it should say whether it also builds the thing that reads it. A per-module allow-list
that nothing reads is two frozensets nobody reads.

**The A-046 log assertion that does exist** (`tests/broker/test_publish_confirm_failures.py:200-237`)
is the technique this phase's `reason`/`details` obligation needs, and the one Phase 6's AC-8
extends:

```python
    with structlog.testing.capture_logs() as captured:
        ...
    assert acked is False, "the failure must actually have happened, or this proves nothing"
    assert captured, "a failed confirm must log SOMETHING, or the assertion is vacuous"

    for record in captured:
        rendered = repr(record)
        assert marker not in rendered, f"{marker!r} reached a log record ({evidence_of})"

    for value in _every_metric_label_value():
        assert marker not in value, f"{marker!r} reached a metric label ({evidence_of})"
```

→ A distinctive marker string is planted in the field under suspicion, the whole captured record is
`repr`'d rather than inspected field by field (*"evidence about fields rather than about this one
field"*, `:205-206`), and **two vacuity guards** stand in front of the loop. For property-history the
markers go in `reason` (user-authored free text, forbidden in a log line) and in a `details` value.

**`test_workspace_id_is_never_a_metric_label` (`:239-250`) is the second half, it is scoped to every
`prope_*` metric, and property-history's lock file collides with it head-on.** This is a conflict
found by reading, not a pattern:

```python
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prope_"):
            continue
        for sample in metric.samples:
            assert "workspace_id" not in sample.labels, metric.name
```

`docs/modules/property-history.lock.yml` `observability_requirements.metrics` declares
`prope_property_history_rows_total  # gauge, labels: workspace_id`. That metric is **Phase 6's**, so
this phase is not blocked — its one counter, `append_rejected_total`, is labelled only by a closed
three-member `reason` set. But the test that will fail was written in Phase 2, lives in another
module's package, and is green today. Raised as **`docs/brainstorm/open_questions/OQ-030.md`**, which
names the exact lock-file line, the exact test, and `observability.py:1-33`'s stated rule. The spec
is not edited to agree. Phase 6 inherits a filed question rather than a surprise red suite.

---

### `tests/security/test_history_is_append_only_by_privilege.py`

**Analog:** `tests/security/test_append_only_privilege.py`, **whole-file**. This is the phase's first
success criterion and D-52 says copy the structure; here is exactly what to copy.

**The module docstring names the two failure modes the file is shaped against** (`:1-21`):

```python
"""T-006 / D-07: ``ledger.price_table`` is append-only by privilege.

**Every test here carries a positive control, and it is load-bearing rather than
decorative.** An ``UPDATE`` that matched zero rows and an ``UPDATE`` the engine
refused are both "nothing changed" from the test's side (Pitfall 8). So each
test first asserts, inside the very transaction that will attempt the write,
that the seeded row *is* visible. Privilege is checked before row security, so a
visible row isolates the privilege from the policy.

The last test goes one step further and is the reason this file can be trusted:
it restores the grant, observes the refusal stop holding, and revokes it again
in a ``finally``. A guarantee nobody can execute is not a guarantee ...
"""
```

**The privilege probes as named statement constants** (`:78-82`):

```python
APP_MAY_UPDATE_PRICE_TABLE = text(
    "SELECT has_table_privilege('prope_app', 'ledger.price_table', 'UPDATE')"
)
GRANT_UPDATE_ON_PRICE_TABLE = text("GRANT UPDATE ON ledger.price_table TO prope_app")
REVOKE_UPDATE_ON_PRICE_TABLE = text("REVOKE UPDATE ON ledger.price_table FROM prope_app")
```

→ D-50 requires **two** `has_table_privilege` assertions (`UPDATE` **and** `DELETE`) because the
deviation is a spelling and the end state is what is asserted. The ledger file mutation-tests only
`UPDATE`; the history file should mutation-test the privilege whose absence is PH-02, and state which
one it chose and why the other is covered by the plain refusal test.

**Seeding runs as the owner, on purpose** (`:85-97`):

```python
async def _seed_price_row(migrate_engine: AsyncEngine) -> None:
    """Seed as the owner. ``prope_app`` could insert one too, but the owner path
    keeps the seeding independent of the privilege under test."""
```

→ A seeded `history_event` must name a **registered** `(action, target_type)` pair, because D-57's
composite foreign key is real even for the owner. The registry is seeded by the migration and
excluded from the truncate fixture (D-48), so the pair is available in every test — which is a second,
independent reason the exclusion is not optional.

**The positive control lives inside the attempting transaction** (`:121-135`):

```python
async def _refusal_text(app_sessionmaker, *, visible, statement, parameters) -> str:
    """Attempt ``statement`` as ``prope_app`` where the seeded row IS visible.

    The visibility assertion runs inside the same transaction as the attempt.
    Without it, this whole file would pass against an empty table.
    """
    with pytest.raises(DBAPIError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            seen = (await session.execute(visible)).scalar_one()
            assert seen == 1, (
                "positive control failed: the seeded row is not visible to prope_app, "
                "so a refusal below would be indistinguishable from an empty table"
            )
            await session.execute(statement, parameters)
    return str(excinfo.value).lower()
```

→ Copy the helper. Assertions on the refusal are `"permission denied" in message` plus the table name
(`:151-152`), lowercased once at the helper.

**The mutation check is a test, with a `finally`** (`:214-252`) — grant, observe the refusal stop
holding by asserting `rowcount == 1`, revoke in `finally`, then re-assert the privilege is gone
outside the `try`. Note the comment at `:236-237` explaining why a *fresh transaction* is needed after
the grant commits. Do not shorten this test; its length is the argument.

**The one privilege whose presence is a guarantee** (`:189-211`) has a history counterpart worth
adding: `prope_app` must hold `SELECT` on `history_event`, and `SELECT` on
`history_action_registry`, or the registry loader and the read path cannot work. `0003:246-251`
records the same reasoning for `call_body` (*"SELECT is required alongside DELETE, and is not an
oversight ... PostgreSQL requires SELECT privilege on every column a statement references"*).

**Where shared constants live** (`tests/security/__init__.py:19-26, 51-69`): workspace ids, a fixed
`CREATED_AT`, the `INSERT_*` statement, and a `*_values(**overrides)` factory returning *"the simplest
row the CHECK set accepts, with targeted overrides"*. A history equivalent belongs in the same place
or its own — see the placement note below.

---

### `tests/security/test_the_vocabulary_gate_is_python_only.py` (D-62's asserted absence)

**Analog:** `tests/security/test_eval_no_body_boundary.py`, **whole-file, both halves**. This is the
closest structural match in the repository to what D-62 owes, and its docstring is the argument
(`:1-37`):

```python
"""A-055 / T-02-12: the no-body rule, and the fact that only Python enforces it.

**This file asserts an absence, on purpose.** Every other test in this package
proves the engine refuses something. This one proves the engine does *not* —
and that is the point ...

An exception that is merely written down is a belief. So the two halves are
asserted here instead:

1. **The enforcement that exists.** ``write_records`` refuses ... by
   ``ValueError``, naming the ``call_id``, before any row is built — so the
   refusal is whole-batch and nothing is half-written.
2. **The enforcement that does not.** A hand-written ``INSERT INTO
   ledger.call_body`` for a ``source = 'eval'`` record, executed as
   ``prope_migrate``, **succeeds**. If a later revision ever does add the
   trigger, this test goes red, and its failure is the notification that the
   boundary moved.
"""
```

**The "do not fix this" instruction on the absence half** (`:141-152, 174-178`):

```python
    """Half 2: the recorded absence.
    ...
    **If this test starts failing, do not "fix" it.** It failing means somebody
    added the database guard, which is a real improvement and a real change to
    what later phases inherit. Delete the test, and delete the exception recorded
    in ``alembic/versions/0004_workspace_retention.py`` in the same change.
    """
```

**The positive control on the owner-path insert** (`:157-159`) — assert the seeded row really is the
case under test before asserting the insert lands, or the test proves nothing:

```python
        # Positive control: the record really is an eval record. Without this the
        # insert below would prove nothing — a body against a gateway record is
        # allowed by everybody and is not the case under test.
        assert (await control.execute(READ_SOURCE, {"call_id": EVAL_CALL_ID})).scalar_one() == "eval"
```

→ D-62's version asserts that a hand-written `INSERT` as `prope_migrate` carrying **an unregistered
`details` key and no `reason` on an action that requires one** succeeds — with the positive control
being that the action really is one whose registry row says `requires_reason` is true. **The
`(action, target_type)` half is not in this test**, because that half *is* engine-enforced (D-57);
the plan should assert that half separately as a refusal, so the seam between the two enforcement
layers is visible in two files rather than blurred in one.

**A local `INSERT_*` constant rather than a reused helper, with the reason stated** (`:48-53`):

```python
#: Written out here rather than reused from ``tests.security.__init__`` because
#: that helper builds a gateway row: ``ck_call_record_eval_calls_carry_run``
#: requires ``run_id`` AND ``case_id`` ... Getting this wrong produces a
#: constraint failure that looks like the thing under test and is not.
```

---

### `tests/integration/test_same_transaction_events_have_a_stable_order.py`

**Analog (posture):** `tests/integration/test_body_retention_delete.py:1-27` — the docstring names
the failure mode that *looks healthy*, and commits the file to reading back through `migrate_engine`:

```python
"""**A retention job that runs cleanly and deletes nothing looks healthy.** So
nothing in this file asks the job what it did and believes the answer. Every
assertion is a direct query against ``ledger.call_body`` through
``migrate_engine`` — the owner role, which is subject to no policy. Checking
emptiness through an application session in the wrong tenant would return zero
rows whether or not the delete worked ...
"""
```

→ The history equivalent: *"two events read back in the order they were written look correct even
when the order is an accident of the planner"*, so the test writes both events **with byte-identical
`occurred_at`** and asserts `seq` orders them — which is AC-4's own wording.

**Analog (technique):** `tests/integration/test_body_retention_delete.py:15-22` and
`retention.py:109-111`'s `ChunkObserver` — the repository's one worked example of **observing a
property that is unobservable once the call has returned**:

```python
**A loop that holds one transaction across every chunk is indistinguishable
from a correct one once it has returned.** Both must commit before returning or
nothing would persist, so any observation taken after the call is blind to where
the transaction boundaries were. The ``per_chunk`` test therefore observes the
loop while the loop is still running, through the ``on_chunk`` seam, from a
connection the loop does not hold.
```

→ **This phase's unobservable property is "the append ran inside the caller's transaction".** Once
the transaction commits, an append that opened its own connection and an append that used the
caller's look identical. The observation that tells them apart is available without a callback seam,
because *this* module takes the session as an argument: open a `workspace_transaction`, append, read
the row back **inside** that transaction, then raise out of the block and assert through
`migrate_engine` that nothing survives. State that as the technique; do not invent an `on_append`
callback, which would be a production parameter bought for a test that does not need one.

**The fixture calendar makes "identical timestamps" arithmetic rather than a race**
(`tests/unit/__init__.py:46-54`):

```python
#: Day 1 of the fixture calendar. Every other instant in these tests is this
#: value plus a number of days, so "day 5" and "day 20" are arithmetic rather
#: than a date somebody has to decode.
DAY_1 = datetime(2026, 8, 1, tzinfo=UTC)


def day(n: int, **offset: int) -> datetime:
    """Day ``n`` of the fixture calendar, tz-aware UTC. ``day(1)`` is DAY_1."""
```

→ Pass the *same* `day(5)` to both events. A test that used `datetime.now(UTC)` twice would
occasionally produce two different instants and would then be asserting the tiebreak it meant to
remove.

**`RESTART IDENTITY` and what an ordering assertion may compare against.** `conftest.py:178` runs
`TRUNCATE ... RESTART IDENTITY CASCADE`, so once `history_event` joins the fixture the `seq`
sequence restarts between tests. That makes small absolute values stable *within a test run*, but
D-53's own note — **monotonic is not gapless**, a rolled-back transaction consumes values and never
returns them — means a test that appends, rolls back, and then appends again will see a gap. Assert
relative order; if the plan asserts absolute values, it must say which of the two properties it is
relying on.

---

### `tests/unit/test_unregistered_detail_key_fails_the_transaction.py`

**The lock file's `test_ref` path is `tests/unit/...` and it is CORRECT for this repository**, which
resolves one of CONTEXT's discretion items outright. `tests/unit/__init__.py:1-7` and
`tests/__init__.py:1-7` both define the word:

```python
""""Unit" here names the *scope* of the assertion, not the absence of a database
(D-02). Effective-dated selection at a timestamp boundary, a `numeric(20,10)`
round-trip and a CHECK refusal are properties of the engine; asserting them
against a mocked driver would assert the mock.
"""
```

→ So a test that needs a live PostgreSQL and asserts one function's rule belongs in `tests/unit/`,
exactly where the lock puts it. **`tests/contract/` and `tests/chaos/` do not exist** (the lock names
both at `:515` and `:489`); those are Phase 5's and Phase 6's problems respectively, and the plan
should say so rather than creating empty packages now.

**AC-5 has four clauses and the analogs are split across two files.**

*Raises, and the caller's transaction rolls back with no partial state* — `test_eval_no_body_boundary
.py:110-138`'s whole-batch technique: write a legal row alongside the poisoned one, then count
through `migrate_engine` and find zero:

```python
    with pytest.raises(ValueError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await write_records(session, [poisoned, innocent])
    ...
    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_RECORDS)).scalar_one() == 0, (
            "the batch-mate landed: the refusal was not whole-batch"
        )
```

*`append_rejected_total` increments with a reason* — `tests/broker/test_publish_confirm_failures.py:
55-63` and `tests/integration/test_ceiling_refuses_evals_only.py:116` are the counter-reading pattern,
and it is a **delta, never an absolute**, because `prometheus_client`'s default `REGISTRY` is
process-global and survives every test in the session:

```python
from prometheus_client import REGISTRY

def _counter_value(reason: str) -> float:
    value = REGISTRY.get_sample_value(
        "prope_call_ledger_publish_failed_total", {"reason": reason}
    )
    return value or 0.0

...
    before, dropped_before = _counter_value("unroutable"), _dropped_value()
    ...
    assert _counter_value("unroutable") == before + 1
```

→ Read before, act, assert `before + 1`. The `or 0.0` is not defensive noise: a labelled counter has
**no sample at all** until its first `.labels(...).inc()`, so `get_sample_value` returns `None` for a
reason that has never fired.

**The A-046 metric sweep is wholesale, not per-metric** (`test_publish_confirm_failures.py:66-78`) —
and this is the shape Phase 6's AC-8 will extend, so writing it in the house form now saves that
phase a rewrite:

```python
def _every_metric_label_value() -> list[str]:
    """Every label value currently in the registry, across every metric.

    A-046's metric half. Collected wholesale rather than per-metric, because the
    rule is that a body reaches NO label, and a per-metric list is a list
    somebody has to remember to extend.
    """
```

---

### Shared history fixture helpers — **shape has a precedent, placement does not**

Two helper modules exist and both are imported across test packages:
`tests/unit/__init__.py` (imported by `tests/integration/`, `tests/security/` and `tests/broker/`)
and `tests/security/__init__.py` (imported by `tests/security/`). Their shape is settled
(`tests/unit/__init__.py:9-17`):

```python
"""The seeding helpers below exist so every test in this package builds price rows
and call records the same way. Each takes overrides, so a test that wants a
refusal changes exactly the one field that should cause it and the constraint
named in the error is the constraint under test.

All datetimes here are timezone-aware UTC, without exception.
"""
```

**The placement is genuinely open and the plan must decide it.** `tests/unit/__init__.py:26-27`
already imports `prope.call_ledger.domain` and `prope.call_ledger.seams` at module scope, so adding
history factories there makes one helper module import two bounded contexts — which is exactly the
coupling `pyproject.toml:63-67`'s one-subpackage-per-context layout exists to keep out of `src/`.
A `tests/property_history/__init__.py` has no precedent, but neither did `tests/broker/` before
Phase 2. Whichever is chosen, the shared constants that already exist and should be **reused rather
than restated** are `WORKSPACE_A` / `WORKSPACE_B` / `WORKSPACE_C` and `DAY_1` / `day()`; a second
`wsp_01J...AAA` literal in a second file is the drift these modules exist to prevent.

---

### `tests/conftest.py` (**modified** — D-48)

**Analog:** the same file. The truncate fixture and its discovered table list (`:93-98`, `:170-179`):

```python
#: Discovered rather than listed, so the later plans in this phase can add
#: tables without editing the rig.
LIST_LEDGER_TABLES = text(
    "SELECT quote_ident(schemaname) || '.' || quote_ident(tablename) "
    "FROM pg_tables WHERE schemaname = 'ledger'"
)

@pytest.fixture(autouse=True)
async def truncate_ledger(migrate_engine: AsyncEngine) -> AsyncIterator[None]:
    """Empty every ledger table between tests, as the owner (A10)."""
    yield
    async with migrate_engine.begin() as connection:
        tables = (await connection.execute(LIST_LEDGER_TABLES)).scalars().all()
        if tables:
            await connection.execute(
                text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE")
            )
```

Four mechanical facts the plan needs:

1. **The exclusion keeps the statement a plain string constant.** Widening to
   `schemaname IN ('ledger','history') AND NOT (schemaname = 'history' AND tablename =
   'history_action_registry')` is still one literal. It is in `tests/`, which
   `test_no_sql_interpolation.py:34` does not walk anyway, but keeping it a constant costs nothing
   and matches every other statement in the file.
2. **The `TRUNCATE` itself is already assembled by `", ".join(...)` at `:178`** — from
   `quote_ident`ed catalogue names, which is why it is safe and why it has never needed an `ALLOWED`
   entry. Nothing about that changes.
3. **The fixture's name will read wrong.** `truncate_ledger` is autouse and is **never requested by
   name in any test** — verified: the only other occurrences are prose in four docstrings
   (`conftest.py:56`, `test_reprice_only_unpriced.py:302`, `test_write_path.py:25, 196, 418`). So a
   rename is a five-line prose edit across three files and no behavioural risk; keeping the name is a
   fixture called `truncate_ledger` that truncates two schemas. Decide, and say which.
4. **The isolation decision is stated at length and must not be quietly reversed** (`:22-26`,
   restated at `src/prope/db/session.py:30-34`):

```python
**Isolation is truncate-between-tests, not transaction rollback** (A10). The
rollback pattern is the conventional one and would silently break every
cross-tenant test: it turns the seam's ``session.begin()`` into a savepoint,
and the transaction-local tenant setting survives a savepoint, so tenant A's
context contaminates tenant B inside the same test.
```

→ This matters more here than it did for call-ledger: **this phase's tests open the transaction
themselves** (D-64), and the tempting shortcut for "assert the caller's transaction rolled back" is
an outer rollback. It is refused for the reason above, and the plan should name the refusal rather
than leave it to be rediscovered.

**Also copy the decision-per-paragraph docstring form** (`:1-58`). The file carries four Phase 1
decisions and three Phase 2 decisions, each as a bold-led paragraph. D-48's exclusion is the eighth,
and it belongs in that docstring in that voice — including the two consequences CONTEXT names
(`RESTART IDENTITY` resetting `seq`; `CASCADE` following D-57's foreign key).

---

### `tests/architecture/test_tenant_coverage.py` (**modified** — D-47, D-56)

**Analog:** the same file. Three edits, and CONTEXT names two of them.

**1. The constant** (`:39-53`), which documents its own shrink obligation:

```python
#: THIS LIST IS A PER-PHASE CONSTANT, NOT A PERMANENT FACT. It names the
#: declared schemas that do not exist *yet*. The phase that creates one owns
#: removing it here, in the same change — Phase 7 creating `access` is the first
#: such case. ...
EXPECTED_ABSENT_SCHEMAS = (
    "access", "evaluation", "gateway", "history", "provider", "registry", "release",
)
```

→ Drop `"history"`. **The comment's own example sentence — "Phase 7 creating `access` is the first
such case" — becomes false in this change and should be corrected in the same edit**, along with
`.planning/STATE.md`'s matching claim (D-47). Leaving a comment that names the wrong phase is how the
next planner inherits the same wrong belief.

**2. The companion tuple three lines below the assertion** (`:147-151`) — the edit a planner misses:

```python
    assert absent == EXPECTED_ABSENT_SCHEMAS, (
        "the set of declared-but-absent schemas changed. If a phase just created one, "
        "remove it from EXPECTED_ABSENT_SCHEMAS in this file, in that same change."
    )
    assert tuple(existing) == ("ledger",)
```

→ `("history", "ledger")`. Alphabetical, because `LIST_EXISTING_SCHEMAS` (`:67-69`) carries
`ORDER BY nspname`.

**3. `GLOBAL_TABLES` gets its first entry, and the key format is exact** (`:33-37`, `:118-120`):

```python
#: Fully-qualified table name -> the written reason it is not tenant-scoped.
#: Empty in Phase 1: all five ``ledger`` tables carry ``workspace_id``. The
#: escape hatch exists so an exemption is a sentence somebody signed rather than
#: a silent skip, and the test below refuses a blank one.
GLOBAL_TABLES: dict[str, str] = {}
```

```python
    for schema, table, row_security in tables:
        qualified = f"{schema}.{table}"
        if qualified in GLOBAL_TABLES:
            continue
```

→ The key is `"history.history_action_registry"` — `f"{schema}.{table}"`, not a bare table name.
`test_every_global_table_exemption_carries_a_written_reason` (`:154-160`) only refuses a *blank*
reason, so the quality of the sentence is on the author; D-56 says this one sets the register for
seven modules. Note that the walk itself needs no edit: it enumerates from `pg_class`
(`:57-65`) across all eight `DECLARED_SCHEMAS`, so `history_event` is picked up for free and will
fail on its own if `enable_tenant_rls` is forgotten.

**What does not need editing here:** `DECLARED_SCHEMAS` (`:22-31`) already lists `history` and cites
`tech_stack.md:162` for it. `test_alembic_version_lives_in_public_and_in_no_declared_schema`
(`:163-171`) is unaffected — `alembic/env.py:87, 99` pins `version_table_schema="public"`.

---

### `tests/architecture/test_schema_invariants.py` (**modified** — D-49)

**Analog:** the same file. The five generic tests parameterise over `("history", "ledger")`; the three
ledger-specific ones stay scoped.

| Test (line) | Generic? | Result over `history` |
|---|---|---|
| `test_the_ledger_schema_contains_no_security_definer_function` (108) | generic | empty → passes; asserts the `history` half of the four-function rule |
| `test_no_native_enum_type_exists_in_the_ledger_schema` (122) | generic | empty → passes; D-54's `actor_type` is `text` + CHECK |
| `test_no_foreign_key_leaves_the_ledger_schema` (132) | generic | empty → passes; D-57's key is intra-schema |
| `test_every_timestamp_column_carries_a_time_zone` (145) | generic | `occurred_at` → non-empty, so the vacuity guard at `:152` holds |
| `test_no_column_in_ledger_has_a_floating_point_type` (181) | generic | empty → passes |
| `test_every_money_column_is_numeric_20_10` (161) | ledger-only | pinned at six columns; `history` has none |
| `test_created_at_has_no_default_while_written_at_does` (192) | ledger-only | reads `call_record` by name |
| `test_every_declared_model_matches_a_live_table` (206) | ledger-only | pinned at `len(declared) == 6` |

**[AGENT JUDGEMENT] — correction to D-49.** CONTEXT says *"Two of the five carry `ledger` in their
function name and will read wrong once they run against `history`"*. It is **four** of the five:
`test_the_ledger_schema_contains_no_security_definer_function`,
`test_no_native_enum_type_exists_in_the_ledger_schema`, `test_no_foreign_key_leaves_the_ledger_schema`
and `test_no_column_in_ledger_has_a_floating_point_type`. Only
`test_every_timestamp_column_carries_a_time_zone` is already schema-neutral. So the rename is four
functions, not two — a bigger diff than the decision anticipated, and worth pricing in the plan
because a renamed test function is a test id that disappears from any saved output.

**The vacuity guard is the thing parameterisation must not lose** (`:152`, `:172`):

```python
    assert columns, "no _at / _from columns found — the query, not the schema, is wrong"
```

→ Every generic test that asserts `result == []` passes vacuously against a schema that does not
exist. `test_tenant_coverage.py:113-115` states the same rule in its own words (*"A walk that found
nothing would pass every assertion below"*). If the parameterisation runs before the schema exists —
which it will, on any branch where the migration is not yet applied — the five green results mean
nothing. Either the parameterisation is added in the same change as the migration, or it needs its
own "this schema exists" precondition.

**The module constant that scopes everything** (`:14`):

```python
SCHEMA = "ledger"
```

→ Parameterising means this constant either goes or becomes the ledger-specific tests' local. Choose
one; leaving both a module constant and a parameter is how the two drift.

**Do not copy these tests into a history-specific file.** `test_tenant_coverage.py:1-13` is the
argument, written about exactly this temptation:

```python
"""Scoping it to ``ledger`` and widening it per module was rejected on the ADR's
own grounds: the "walks all eight" property would then be asserted nowhere, and a
module that forgets to widen it is invisible — "the rule selecting for its own
blind spot", which is the exact failure ADR-0045 was written about after the
third instance in three passes.
"""
```

---

### `tests/integration/test_migration_chain.py` (**modified** — not named in CONTEXT)

**[AGENT JUDGEMENT] — a third Phase 1 file names `ledger` by name, and it is the one that fails
silently.** CONTEXT's Integration Points names two files (`test_tenant_coverage.py`, `conftest.py`).
There is a third, and its four `ledger`-scoped constants mean the new schema is simply **not
covered** rather than red:

```python
#: Alphabetical, because the query below orders by name. ``workspace_retention``
#: joins at revision 0004 (D-09) — a deliberately explicit list, so a table
#: appearing or vanishing from a pristine upgrade is an edit somebody made rather
#: than a count that quietly moved.
LEDGER_TABLES = (                                          # :29-40
    "call_body", "call_record", "price_table",
    "spend_ceiling", "workspace_retention", "workspace_spend",
)

LIST_LEDGER_TABLES = text(                                 # :42-44
    "SELECT tablename FROM pg_tables WHERE schemaname = 'ledger' ORDER BY tablename"
)

SNAPSHOT_COLUMNS = text(""" ... WHERE table_schema = 'ledger' ... """)     # :55-63
SNAPSHOT_POLICIES = text(""" ... WHERE schemaname = 'ledger' ... """)      # :65-72
```

Three consequences:

- `test_an_empty_cluster_reaches_head_and_yields_a_working_database` (`:111-131`) keeps passing and
  keeps asserting six `ledger` tables. **It says nothing about whether `history` reached the pristine
  cluster at all.** The constant's own comment argues for an explicit list precisely so a table
  appearing is a visible edit — that argument applies to the two new tables and is currently not
  being made for them.
- `test_running_the_chain_a_second_time_is_a_no_op` (`:134-151`) snapshots columns and policies **for
  `ledger` only**, so the idempotency property this project asserts for every guarantee it ships
  would not cover `history.history_event`'s policy or `history_action_registry`'s seed. The seed is
  the interesting case: a re-run must not duplicate thirty-one rows, and nothing here would notice.
  The assertion at `:149-150` (*"the column snapshot is empty — the comparison would be vacuous"*) is
  the file's own guard against exactly this class of gap.
- `test_the_revision_chain_has_exactly_one_head` (`:154-161`) **does** cover the new revision for
  free, and it is what makes D-46's "do not guess a `down_revision`" a red test rather than a
  convention.

→ Widening the three statements to both schemas and the constant to a two-schema mapping is a small
edit. If the plan chooses not to make it, that is a legitimate call — the tables' existence is
asserted elsewhere — but it must be a stated decision routed to Phase 5 or 6, not an omission,
because `.planning/ORCHESTRATION.md` §9 forbids a red test nobody predicted and this is its quieter
cousin: a green test nobody noticed had stopped looking.

---

## Shared Patterns

### Tenant scoping — the only way a workspace reaches SQL, and this module's inverted relationship to it

**Source:** `src/prope/db/session.py:43-62`
**Applies to:** every test in this phase. **Does not apply to `append.py` in production.**

```python
#: Sets the tenant for the current transaction only. The third argument is what
#: makes it transaction-local; the second is a bound parameter.
SET_TENANT = text("SELECT set_config('app.workspace_id', :ws, true)")


@asynccontextmanager
async def workspace_transaction(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
) -> AsyncIterator[AsyncSession]:
    """Open a transaction carrying exactly one workspace's tenant context. ..."""
    async with sessionmaker() as session:
        async with session.begin():
            await session.execute(SET_TENANT, {"ws": workspace_id})
            yield session
```

**The inversion, stated plainly:** `append()` runs inside a transaction someone else opened
(ADR-0023), so **this module never calls `workspace_transaction` in production code**. Its *tests*
call it, standing in for the five callers that do not exist yet — which is exactly how Phase 2 proved
`enqueue` and `price_usage` with neither the gateway nor evaluation in existence
(`seams.py:1-7`). The three obligations that still bind:

1. **`workspace_id` is `text` and the predicate compares text to text with no cast** —
   `ddl.py:72-79` argues it at length (Phase 1 OQ-A). `enable_tenant_rls` builds the predicate; this
   phase does not write one by hand.
2. **The identifier is bound, never assembled** (`session.py:7-18`). The gate at
   `tests/architecture/test_no_sql_interpolation.py` `rglob`s `src/prope/` (`:34`) and adopts
   `src/prope/property_history/` **for free and correctly** on the day it is written — its `ALLOWED`
   list is empty (`:36-38`) and nothing this phase writes needs an entry.
3. **A missing tenant filter returns zero rows** — which is why `history_action_registry` must be
   global (D-56) and why every read-back assertion in this phase's tests goes through
   `migrate_engine`, the owner role, which is exempt by ADR-0035's owner bypass
   (`conftest.py:140-145`).

### The `#:` idiom — a number, or a statement, that carries its own argument

**Source:** `retention.py:64-68`, `worker.py:83-110`, `enqueue.py:57-70`, `app.py:77-96`
**Applies to:** every constant this phase introduces

```python
#: A6 — a tunable judgement, not a repo decision, recorded so that changing it
#: is a visible act. The stated target is one day's expired bodies, up to
#: 500,000 rows in a batch, removed within ten minutes. At this size that is 100
#: chunks, which has ample headroom; the number is unvalidated at real scale.
DEFAULT_CHUNK_SIZE = 5_000
```

`worker.py:83-110` is the maximal form: three bold-led sub-paragraphs deriving 300 seconds from the
lock file's stated target and naming what the number is *not* validated against. **Every number in
this phase is argued, never round-picked** — the 500-character `reason` cap (D-54), the thirty-one
seed rows (D-60), the four indexes (D-55), the thirteen `target_type` values (D-61). Where the number
comes from a spec rather than from judgement, say that instead: `#:` still carries the citation.

The same marker carries statement-level reasoning (`pricing.py:45-48`, `writer.py:100-128`,
`api.py:120-155`, `seams.py:329-345`). The distinction the repository keeps: `#:` above a
module-level binding, plain `#` for an inline aside inside a function body.

### Never zero, no fourth state — the refusal posture

**Source:** `writer.py:25-36`, `domain.py:44-55`, `session_auth.py:233-238`
**Applies to:** D-63's three reasons and no fourth; D-58's single spelling of "no details"

```python
**Three states, and nothing may invent a fourth.**
...
There is no default branch. A missing price is never a zero price, a missing
usage object is never zero tokens, and no path here substitutes an average, the
nearest price row, or a figure inferred from prompt length.
```

→ `details` is `jsonb NOT NULL DEFAULT '{}'` for exactly this reason (D-58): NULL and `{}` would be
two spellings of one state, and the allow-list check would grow a branch nobody wrote. The
`declares_action` guard (`session_auth.py:216-238`) is the vocabulary-closure form of the same rule,
raising at import so a typo is a **startup error** rather than a runtime one — worth reading before
deciding where the registry's closure is enforced.

### No content in a log line or a metric label (A-046)

**Source:** `observability.py:1-33`, `writer.py:37-39`, `retention_settings.py:38-41`,
`envelope.py:40-43`, `api.py:60-63`
**Applies to:** `append.py`, `observability.py`, and every test that asserts the absence

Every module that touches user data states its A-046 position in its own docstring, including the
modules that emit nothing:

```python
**This module writes no body, emits no log and no metric** (A-046). A retention
window is a policy value, but the workspace id beside it is a tenant identifier,
and the rule that keeps identifiers out of metric labels is the same one that
keeps bodies out of log lines.
```

→ property-history's version is sharper than any of these, because the lock file forbids logging two
columns this module writes: *"Never logged: the `details` payload or the `reason` string ... The
event's id is logged; its content is not."* State it at `append.py` and at the counter.

### Schema-qualified names everywhere; no permissive `search_path`

**Source:** `src/prope/db/engine.py:1-9`

```python
"""Deliberately thin. The only opinion expressed here is a negative one: no
permissive ``search_path`` is set on the application connection. ADR-0027 makes
schema-qualified names appear in every query and every migration, and calls
that "the intended cost: it is what makes a forbidden edge legible without a
linter". A ``ledger`` on the search path is exactly what would make an
accidental ``registry.revision`` join look ordinary.
"""
```

→ Every statement this phase writes says `history.history_event` and
`history.history_action_registry`. This is also why `test_schema_invariants.py:38-43` refuses
`confrelid::regclass::text` in favour of a `pg_namespace` join — the regclass rendering depends on
who is connected.

### Assert against the live engine, with a positive control and a mutation check

**Source:** `tests/security/__init__.py:1-12`, `tests/security/test_append_only_privilege.py:9-20`,
`tests/security/test_tenant_isolation.py:8-11`
**Applies to:** every test in this phase, without exception

```python
"""Security tests — guarantees the database enforces, asserted against it.

Each test in this package carries a positive control. An RLS test against an
empty table passes for the wrong reason, and a privilege test whose UPDATE
matched zero rows is indistinguishable from one the engine refused.
"""
```

`test_tenant_isolation.py:12-18` adds the variant this phase should notice: **two paths to the same
zero-rows result are asserted separately**, because a test exercising only one does not prove the
other. The analogue here is that a refusal from D-57's foreign key and a refusal from D-62's Python
validator are both "the append failed" from the caller's side, and the plan needs them told apart.

### Ruff, and the three rules that will actually bite

**Source:** `ruff.toml:1-19`, `Makefile:13-22`, ORCHESTRATION §3

```toml
target-version = "py313"
line-length = 120
[lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]
```

- **`N` is on**, so `N818` demands an exception name ending in `Error`, and `N802`/`N806` police
  function and local names. `session_auth.py:77`'s `# noqa: N818` is the only escape currently in
  `src/`.
- **`I` is on**, so import order is enforced. Note `alembic/versions/*.py`'s deliberate ordering:
  `from ddl import ...` (first-party by ruff's reckoning, since `alembic/` is on `sys.path`) sits
  **above** `from alembic import op`.
- **`E501` is ignored and `line-length` is 120 while the repo is hand-wrapped to ~100.** That
  disagreement is Broken Window #1: `uv run ruff format --check` fails repo-wide and **is not the
  gate**; `uv run ruff check src/ tests/ alembic/` is (ORCHESTRATION §3). Do not "fix" formatting.
- `make check` runs `lint format test` — `format` **writes**, so run `make lint` and `uv run pytest -q`
  rather than `make check` if an unrelated reformat would pollute the diff.

---

## Patterns that do NOT apply to this phase — read this, it is not filler

A planner scanning a pattern list assumes every entry is binding. These are the ones that are not,
each with the reason, so that the absence is a decision rather than an oversight.

| Pattern | Where it lives | Why it does not apply here |
|---|---|---|
| **The FastAPI router** | `call_ledger/api.py:222` (`APIRouter(prefix="/api/v1")`) | property-history mounts **no route at any version** (lock `scope.non_goals`, PH-07). D-65 makes the absence structural: the package does not import FastAPI at any depth, so no route can be mounted from it even by accident. Phase 6 asserts it. |
| **The A-045 error envelope and `ErrorCode`** | `call_ledger/schemas.py:120-186, 449-522` | No HTTP surface means no envelope. **The machine-code discipline behind it still applies** (ADR-0053: a stored or transmitted token is a fact, stays literal ASCII, and is translated only at an edge) — D-63's reason vocabulary is that rule applied to an exception rather than to a response. |
| **`require_session` / `ManagementAction` / `declares_action`** | `src/prope/session_auth.py` | These exist for routes. There are none. The one thing to carry across is `ManagementAction`'s closure argument (`:186-198`) as a model for how the registry's closure is defended — and `MANAGEMENT_ACTIONS = ManagementAction` at `:207-213` explicitly names `registered_actions()` as property-history's counterpart, which is **Phase 5's**, not this phase's. |
| **`assembled_routes()` and the route-table test** | `session_auth.py:247-270`, `tests/architecture/test_route_table.py` | Broken Window #4 binds "every phase adding routes". This phase adds none, `prope.app` is untouched, and `EXPECTED_ROUTES` (`test_route_table.py:51-61`) stays at seven. Verified: nothing in `test_route_table.py` walks `src/prope/` for routers, so a new package cannot disturb it. |
| **pydantic wire models** | `call_ledger/envelope.py`, `call_ledger/schemas.py` | Nothing crosses a process boundary here — no broker message, no HTTP body. The lock names pydantic v2 as the `details` validator, which is a *validation* use inside `append.py`, not a wire-types module. If pydantic is used, it belongs beside the validator; a `schemas.py` in this package would be a file named after a layer this module does not have. |
| **D-19's own-transaction seams** | `call_ledger/seams.py:37-48`, `retention_settings.py:26-31` | The exact opposite of ADR-0023. `seams.py` argues the split *by naming property-history*. Copying `sessionmaker`-taking signatures here would silently break the five "same transaction" promises in five other lock files — which is why the lock's contract test asserts the session type explicitly. |
| **Money, `Decimal`, `numeric(20,10)`, `MONEY_SCALE_PLACES`** | `models.py:49-50`, `pricing.py:62-65`, `schemas.py:87-111` | No money column in `history`. `test_every_money_column_is_numeric_20_10` stays ledger-scoped (D-49). The **time** half of the same rule — aware datetimes everywhere, `timestamptz` at rest — applies in full. |
| **The broker: `topology.py`, `connection.py`, `aio_pika`, the `purge_queues` fixture** | `src/prope/broker/`, `conftest.py:182-238` | `events.publishes: []` and `subscribes: []`; the lock notes the naming collision explicitly (*"The `events` in this module are rows in a table, not messages"*). No history test should request `amqp_url`, and `purge_queues` (`:228-229`) already opts out by fixture graph for tests that do not. |
| **D-13 explicit central composition (`app.py`, `worker.py`)** | `app.py:1-16`, `worker.py:1-18` | D-65: this phase touches neither. ADR-0038's process-start cache load is Phase 5's wiring. This is also what removes the only file-level collision this phase could have had with Phase 3 under ORCHESTRATION §7. |
| **`supervisor.py` / a supervised job** | `src/prope/supervisor.py`, `worker.py:79-81` | A-121: nothing expires, no retention setting, no job. There is no scheduled work in this module at all, ever. |
| **`ObservedWorkspaces` / `WorkspaceEnumerator` (Broken Window #3)** | `worker.py:119-183` | A cross-tenant enumerator is needed by sweeps. This module has none. `access.list_workspaces()` remains one of the four sanctioned `SECURITY DEFINER` functions and this phase adds no fifth — asserted, once D-49's parameterisation runs, for `history` as well as `ledger`. |
| **`Settings` / `BaseSettings`** | `db/engine.py:22-59` | This module reads no environment variable and has no tunable an operator sets. Its one configuration-shaped thing — the registry — is a database table seeded by a migration (D-59). |

---

## No Analog Found

Nothing comparable exists in the repository for these. The planner should follow `04-RESEARCH.md`
and the CONTEXT decisions, and apply the docstring-density obligation with extra force — each of
these is a shape later modules will copy.

| Thing | Where it lands | Why there is no analog |
|---|---|---|
| An **immutable process-lifetime cache with no TTL and no invalidation** (ADR-0038) | `registry.py` | Nothing in this repository caches anything. `enqueue._handoff` (`enqueue.py:76-101`) is the only process-wide state and it is mutable, reset between tests, and lazily built — the shape is borrowable, the immutability is not modelled anywhere. ADR-0012's gateway cache (30 s, expires, nothing invalidates it) is Phase 19's. |
| A **public, non-`ValueError` domain exception five other modules import** | `domain.py` or `append.py` | `_UnevaluableCeilingError` is private; `ManagementRefusal` is public but is an HTTP-envelope carrier. Nothing exists that a *caller in another bounded context* is expected to see and deliberately never catch. |
| A **per-module observability module** | `property_history/observability.py` | `src/prope/observability.py` is central and scoped to Phase 2's counters by its own docstring. D-65 splits it; the split itself has no precedent, and the `LOGGABLE_FIELDS` collision is the first consequence. |
| `bigint GENERATED ALWAYS AS IDENTITY` | the migration | No identity column, no `bigserial`, no sequence of any kind exists in the schema. `conftest.py:178`'s `RESTART IDENTITY` is currently a no-op. |
| A **composite foreign key** (D-57) | the migration | The two foreign keys in the repository (`0003:88-89`, `0003:222-226`) are both single-column and intra-schema. The intra-schema *rule* has a precedent (`0003:23-30`); the composite shape does not. |
| A **`jsonb` column** (D-58) and a **`text[]` column** (D-59) | the migration | Neither type appears anywhere. `0003:68-69` explicitly refused `jsonb` for `request_body`, and D-58's inversion of that argument is the thing to write down — the two decisions look contradictory and are one rule applied twice. |
| A **data seed inside a migration** (D-59) | the migration | No revision has ever executed an `INSERT`. Verified across all four. |
| A **`GLOBAL_TABLES` entry** (D-56) | `test_tenant_coverage.py` | The dict is empty and has been since Phase 1. `test_every_global_table_exemption_carries_a_written_reason` (`:154-160`) has therefore never guarded a real entry — it currently asserts over an empty dict, which is itself a vacuous pass this phase turns into a real one. |
| A **schema-creating revision that is not `0001`** | the migration | `0001` created `ledger` alongside the roles, as a superuser, with no `assume_migrate_role()`. This revision creates a schema *and* runs as `prope_migrate` — a combination that has never existed. |
| A **second bounded context's test helpers** | `tests/…/__init__.py` | `tests/unit/__init__.py` is the shared factory module and it imports call-ledger's domain at module scope. Where property-history's factories live is a placement with no precedent; the *shape* (constants, `*_values(**overrides)`, aware datetimes) is settled. |

---

## Metadata

**Analog search scope:** `src/prope/**` (18 modules), `alembic/**` (env, ddl, 4 revisions),
`tests/**` (5 packages, 22 test modules, `conftest.py`), `pyproject.toml`, `ruff.toml`, `alembic.ini`,
`Makefile`, `docs/modules/property-history.lock.yml`
**Files read in full for this map:** `alembic/ddl.py`, `alembic/env.py`,
`alembic/versions/0001_roles_and_schemas.py`, `0003_ledger_tables.py`, `0004_workspace_retention.py`,
`src/prope/app.py`, `src/prope/worker.py`, `src/prope/session_auth.py`, `src/prope/observability.py`,
`src/prope/db/{session,metadata,engine}.py`,
`src/prope/call_ledger/{__init__,domain,models,schemas,seams,api,pricing,retention,retention_settings,envelope}.py`,
`src/prope/call_ledger/{writer,enqueue}.py` (partial),
`tests/conftest.py`, `tests/{__init__,unit/__init__,security/__init__,architecture/__init__,integration/__init__,broker/__init__}.py`,
`tests/architecture/{test_tenant_coverage,test_schema_invariants,test_no_sql_interpolation}.py`,
`tests/architecture/test_route_table.py` (partial),
`tests/security/{test_append_only_privilege,test_eval_no_body_boundary,test_tenant_isolation}.py`,
`tests/integration/{test_migration_chain,test_body_retention_delete}.py` (the latter partial),
`tests/broker/{_helpers,test_publish_confirm_failures}.py` (partial)
**Verification method:** every pattern in this file was read from the file at the line cited. The two
corrections to CONTEXT and the identifier-length count are labelled **[AGENT JUDGEMENT]** — no
deterministic detector exists in this environment and none was run or simulated.
**Pattern extraction date:** 2026-08-10
**IDs consumed by this artifact:** no `D-NN` — this file makes no implementation decision and
consumes none of the D-46…D-65 range. One open question: **`OQ-030`**, filed at
`docs/brainstorm/open_questions/OQ-030.md` for the `workspace_id` metric-label conflict found above.
`OQ-027`, `OQ-028` and `OQ-029` were already filed by CONTEXT; `OQ-031` remains unused and available
to the planner.
