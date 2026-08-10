# Phase 2: Seams: enqueue, the broker drain, and the ceiling - Pattern Map

**Mapped:** 2026-08-10
**Files analyzed:** 14 new / 3 modified
**Analogs found:** 9 / 17 (5 exact, 4 role-match, 8 no analog)

> **Read this as "copy from here", not "follow this spirit".** Every excerpt below is real text in
> this repository at the line numbers given. The single most transferable property of the Phase 1
> code is **the module docstring carries the *why* at length, naming the ADR/assumption/OQ and the
> rejected alternative**. Every file this phase creates is expected to match that density — the
> planner should treat the docstring as a deliverable, not as decoration.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `alembic/versions/0004_workspace_retention.py` | migration | batch / DDL | `alembic/versions/0003_ledger_tables.py` | **exact** |
| `src/prope/call_ledger/retention_settings.py` | service (repository) | CRUD (read one indexed row / upsert) | `src/prope/call_ledger/pricing.py` (`resolve_price`) | **exact** |
| `src/prope/call_ledger/seams.py` — `price_usage` | service | request-response (write) | `src/prope/call_ledger/retention.py` (`delete_expired_bodies`) | **exact** |
| `src/prope/call_ledger/seams.py` — `check_spend_ceiling` | service | request-response (single-row read) | `src/prope/call_ledger/pricing.py` (`resolve_price`) | **exact** |
| `src/prope/call_ledger/seams.py` — `get_run_totals` | service | request-response (aggregate read) | `src/prope/call_ledger/writer.py` (`UNPRICED_WORKLIST`) | **exact** |
| `src/prope/call_ledger/drain.py` | worker job | event-driven → batch | `src/prope/call_ledger/retention.py` (bounded chunk loop) | role-match |
| `src/prope/call_ledger/enqueue.py` | service | pub-sub (publish) | — | **no analog** |
| `src/prope/broker/topology.py` | config | declaration | `alembic/ddl.py` (declarative guarantee constants) | role-match |
| `src/prope/broker/connection.py` | provider/factory | connection lifecycle | `src/prope/db/engine.py` | **exact** |
| `src/prope/supervisor.py` | utility | event-driven (task supervision) | — | **no analog** |
| `src/prope/worker.py` | entrypoint | process | — | **no analog** |
| `src/prope/app.py` | entrypoint | request-response | — | **no analog** |
| `src/prope/call_ledger/api.py` | controller (router) | request-response | — | **no analog** |
| `src/prope/call_ledger/schemas.py` | model | transform / validation | `src/prope/call_ledger/domain.py` | role-match |
| `tests/conftest.py` (**modified**) | test rig | fixture | `tests/conftest.py` (Postgres rig, same file) | **exact** |
| `tests/broker/…` | test | event-driven | `tests/integration/test_body_retention_delete.py` | role-match |
| `pyproject.toml` (**modified**) | config | — | `pyproject.toml` (existing pin comments) | **exact** |

---

## Pattern Assignments

### `alembic/versions/0004_workspace_retention.py` (migration, DDL)

**Analog:** `alembic/versions/0003_ledger_tables.py` — copy its shape wholesale. Migration `0004`
carries **one table with its whole guarantee stack in one revision**: DDL constant + `enable_tenant_rls`
+ `grant_table`, wrapped in `assume_migrate_role()` / `reset_role()`.

**Imports + revision header** (`0003_ledger_tables.py:41-54`) — note the *bare* `ddl` import, which is
load-bearing and commented as such:

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
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

→ For 0004: `revision = "0004"`, `down_revision = "0003"`. D-04's chain is linear and hand-written.

**Table DDL as a module-level string constant, with the reasoning in SQL comments**
(`0003_ledger_tables.py:57-91`):

```python
CREATE_CALL_BODY = """
CREATE TABLE ledger.call_body (
    call_id        text         NOT NULL,

    -- Denormalised, never joined for authorisation. Added at lock step 4 for a
    -- reason worth restating: reachable only through call_record, this table —
    -- the one table in Prope holding raw end-user content — would have been
    -- skipped by ADR-0045's coverage walk, which enumerates tables CARRYING
    -- workspace_id and asserts a policy on each.
    workspace_id   text         NOT NULL,
    ...
    -- Genuinely "when the database saw this", so it does default.
    created_at     timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_call_body PRIMARY KEY (call_id),
);
"""
```

**Type conventions to inherit verbatim** (`0003_ledger_tables.py:32-38`): every `*_id` is `text`
(ADR-0003 prefixed ULIDs), every timestamp is `timestamptz`, no foreign key leaves `ledger`
(`workspace_id` and `updated_by` are **values, not references** — `0003:23-27`).

**`upgrade()` / `downgrade()` body** (`0003_ledger_tables.py:229-275`) — the exact ordering and the
grant-comment style to copy:

```python
def upgrade() -> None:
    """Create the remaining four owned tables with their whole guarantee stack."""
    assume_migrate_role()

    op.execute(CREATE_CALL_BODY)
    ...
    for table in ("call_body", "price_table", "workspace_spend", "spend_ceiling"):
        enable_tenant_rls("ledger", table)

    # UPDATE because "set or clear a ceiling" is an update.
    grant_table("ledger", "spend_ceiling", app_privileges=["SELECT", "INSERT", "UPDATE"])

    reset_role()


def downgrade() -> None:
    """Drop the four tables and the deferred foreign key that depends on one."""
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS ledger.spend_ceiling")
    reset_role()
```

→ For `ledger.workspace_retention`: `enable_tenant_rls("ledger", "workspace_retention")` and
`grant_table("ledger", "workspace_retention", app_privileges=["SELECT", "INSERT", "UPDATE"])`
(a `PUT` that sets a window is an upsert). `report_select` defaults `True` — RESEARCH Open Question 6
recommends taking the default, which is what every Phase 1 table did.

**Why no test edit is needed:** the tenant coverage walk discovers from `pg_class`
(`tests/architecture/test_tenant_coverage.py:57-65`) and the truncate fixture discovers from
`pg_tables` (`tests/conftest.py:63-66`). Do **not** add the table to any list. `EXPECTED_ABSENT_SCHEMAS`
(`test_tenant_coverage.py:45-53`) is untouched by this phase.

---

### `src/prope/call_ledger/retention_settings.py` (service, CRUD)

**Analog:** `src/prope/call_ledger/pricing.py` — a `text()` SELECT constant with the index reasoning in
its `#:` comment, plus a thin async function taking a session from `workspace_transaction`.

**Read-query pattern** (`pricing.py:45-60`):

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

**Absence-is-an-answer pattern** — the exact posture D-11 needs for "no row = the 30-day default"
(`pricing.py:78-91`):

```python
    """The price row in force at ``at`` for this key, or ``None``.

    ``session`` comes from ``workspace_transaction()``, so the tenant policy
    applies underneath the explicit ``workspace_id`` predicate — a row belonging
    to another workspace is refused twice over.

    ``None`` is a complete answer. ...
    """
```

**Row → frozen dataclass** (`pricing.py:93-105`):

```python
    row = (
        await session.execute(PRICE_IN_FORCE, {...})
    ).mappings().first()

    return PriceRow(**row) if row is not None else None
```

**The default constant to reuse, not redefine:** `writer.DEFAULT_RETENTION_WINDOW`
(`writer.py:58-62`) — `timedelta(days=30)`, whose own comment says *"Phase 2 owns the storage decision
when `PUT /workspaces/{id}/retention` arrives"*. Import it; do not write a second `30`.

---

### `src/prope/call_ledger/seams.py` (service ×3, request-response)

**Analog for the transaction boundary (D-19):** `retention.py:114-152` — the function takes a
`sessionmaker`, opens `workspace_transaction` itself, and never accepts a caller's session.

```python
async def delete_expired_bodies(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    *,
    now: datetime,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    ...
) -> int:
    ...
    async with workspace_transaction(sessionmaker, workspace_id) as session:
        result = await session.execute(DELETE_CHUNK, {"ws": workspace_id, ...})
```

Note the **keyword-only tail after `*`** and the **clock passed in, never read** (`retention.py:11-17`
— *"`now` is an argument and never a clock read"*). `check_spend_ceiling` must follow this for its
`period_month` (RESEARCH Pitfall 8): take `now: datetime` and derive the month with the writer's own
helper.

**The month helper to reuse, not re-derive** (`writer.py:160-168`):

```python
def _period_month(draft: CallRecordDraft) -> date:
    """The first day of the record's own month, in UTC.

    From the record's ``created_at``, never from wall clock — same reasoning as
    pricing. A drain catching up across a month boundary must not file
    September's calls under August.
    """
    at_utc = draft.created_at.astimezone(UTC)
    return date(at_utc.year, at_utc.month, 1)
```

→ It is currently private and takes a `CallRecordDraft`. The plan should extract a
`period_month(at: datetime) -> date` that both `write_records` and `check_spend_ceiling` call, so
Pitfall 8's "both sides file into the same month" is a shared function rather than two agreeing
implementations.

**`price_usage` writes nothing of its own** — it builds `CallRecordDraft`s and calls `write_records`.
Draft construction pattern and the constraint it must satisfy (`domain.py:113-160`,
`writer.py:205-209`):

```python
        if draft.source == Source.EVAL and draft.body is not None:
            raise ValueError(
                f"{draft.call_id} is source=eval and carries a body; no call_body row will ever "
                "exist for an eval call (A-055)"
            )
```

`case_id` is required by `ck_call_record_eval_calls_carry_run` — see RESEARCH Pitfall 4.

**Refusal style to inherit** — a raise names what is missing and never substitutes a figure
(`writer.py:244-250`, `domain.py:162-173`). Every `ValueError` in this codebase is a full sentence
naming the identifier, the two values, and the rule. `check_spend_ceiling`'s refusal must follow the
same style **minus any number** (the lock's `test_plan.security`).

**Aggregate-read shape for `get_run_totals`** (`writer.py:138-157`) — a projection over the stored
encoding, no second table, and the tenant policy supplying the workspace predicate:

```python
#: CL-04's operational surface, as a projection over the stored encoding rather
#: than a second table. Served by ``ix_call_record_unpriced_worklist``, ...
#: Phase 1 owes the encoding, the index and this query. Phase 2 owes the route
#: (``GET /api/v1/prices/unpriced``); none is built here. The tenant policy
#: supplies the workspace restriction, so there is no ``workspace_id`` predicate
#: to forget.
UNPRICED_WORKLIST = text(
    """
    SELECT provider_config_id, upstream_model,
           count(*)        AS unpriced_calls,
           min(created_at) AS since
    FROM   ledger.call_record
    WHERE  cost_status = 'unpriced'
    GROUP  BY provider_config_id, upstream_model
    ORDER  BY unpriced_calls DESC, upstream_model
    """
)
```

→ `get_run_totals` is the same shape with `WHERE run_id = :run_id` and
`count(*) FILTER (WHERE usage_status = 'unknown')` / `FILTER (WHERE cost_status = 'unpriced')`, per
`WriteResult`'s documented contract (`domain.py:183-193`).

**Return-value shape:** copy `WriteResult` (`domain.py:183-203`) — a `@dataclass(frozen=True, slots=True)`
whose docstring says what each count is derived *from*. `RunTotals` and `CeilingDecision` should be the
same kind of object.

---

### `src/prope/call_ledger/drain.py` (worker job, event-driven → batch)

**Analog (partial):** `retention.py:144-170` — the bounded loop with the transaction boundary made
explicit by a comment, and the exit condition explained rather than asserted:

```python
    while True:
        async with workspace_transaction(sessionmaker, workspace_id) as session:
            result = await session.execute(DELETE_CHUNK, {...})
            deleted_in_chunk = result.rowcount
        # The transaction is committed here, and the next one has not opened.
        # Row locks and the snapshot are released; another session can see what
        # this chunk did.
        ...
        if deleted_in_chunk < chunk_size:
            # A short chunk means the predicate has no more rows to offer.
            break
```

→ The drain's `for workspace_id, group in ...: async with workspace_transaction(...)` loop is the same
shape. **The ack goes exactly where the comment `# The transaction is committed here` sits** — that
is D-15's "ack after commit", per group (RESEARCH assumption A3).

**Observation seam for tests** (`retention.py:109-111, 131-142`) — copy this idea for the drain's
window boundary, because "one transaction per group" is unobservable after the call returns:

```python
#: What ``on_chunk`` must look like: awaited with the rows this chunk removed
#: and the running total.
ChunkObserver = Callable[[int, int], Awaitable[None]]
```

with the docstring stating: *"It is an observation seam and nothing else. It is keyword-only, defaults
to `None`, and when it is `None` the branch is not taken: the production call path supplies no
callback and behaves exactly as it would without the parameter."*

**Tuning constants get a `#:` comment that names them as judgement** (`retention.py:64-68`) — this is
the shape D-15's N and T must take:

```python
#: A6 — a tunable judgement, not a repo decision, recorded so that changing it
#: is a visible act. The stated target is one day's expired bodies, up to
#: 500,000 rows in a batch, removed within ten minutes. At this size that is 100
#: chunks, which has ample headroom; the number is unvalidated at real scale.
DEFAULT_CHUNK_SIZE = 5_000
```

**What the drain must NOT do:** read the retention window inside `write_records` (D-11), and never
build SQL of its own — `write_records(session, drafts, retention_window=…)` is the only write
(`writer.py:1-8`).

---

### `src/prope/broker/connection.py` (provider/factory, connection lifecycle)

**Analog:** `src/prope/db/engine.py` — "deliberately thin", settings via `BaseSettings`, two builder
functions whose docstrings carry the one non-obvious kwarg's reason.

**Settings pattern to extend, not duplicate** (`engine.py:22-38`):

```python
class Settings(BaseSettings):
    """Runtime configuration read from the environment.

    ADR-0032: one ``.env`` on the host, 0600, git-ignored, never in CI. The
    ``PROPE_`` prefix keeps Prope's keys distinguishable ... and
    ``extra="ignore"`` means an unrelated key in the same file is not an error.
    """

    model_config = SettingsConfigDict(
        env_prefix="PROPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
```

→ The broker URL is `PROPE_BROKER_URL` on **this same class** (one `Settings`, one `.env`), not a
second settings object.

**Builder-function style** (`engine.py:41-55`):

```python
def build_engine(url: str, **kwargs: Any) -> AsyncEngine:
    """An async engine over asyncpg (A-128 — a sync driver would block the
    event loop the gateway's p95 budget depends on)."""
    return create_async_engine(url, **kwargs)
```

→ `build_connection(url)` → `aio_pika.connect_robust(...)`, with the docstring naming why *robust*
(transparent reconnect) and why confirm mode is the default.

---

### `src/prope/broker/topology.py` (config, declaration)

**Analog (role-match):** `alembic/ddl.py` — a module of named constants and small emitters, whose
docstring states *why the helper exists at all* and where the one runtime value enters.

```python
"""Reusable DDL emitters — the guarantee carriers every revision calls.
...
Identifiers interpolated below are module constants and revision-supplied
schema/table names — never runtime values. The one place a runtime value
reaches SQL is the tenant identifier in ``prope.db.session``, and that one is
bound as a parameter.
"""

MIGRATION_ROLE = "prope_migrate"
...
#: The session variable the tenant policy reads. ADR-0035.
TENANT_GUC = "app.workspace_id"
```

And the per-token justification pattern from `enable_tenant_rls` (`ddl.py:56-86`), which is exactly
how D-23's five queue arguments should be documented — a named sub-heading per argument:

```python
    """ADR-0035 / ADR-0045: the deny-by-default tenant policy for one table.

    Three tokens here are load-bearing and none is stylistic:

    ``ENABLE``, never ``FORCE``
        ...

    ``current_setting(..., true)`` — two arguments
        The one-argument form *raises* ... The two-argument form returns NULL ...

    ``WITH CHECK`` written out
        It defaults to the ``USING`` expression, but ADR-0040 makes it the
        load-bearing half ...
    """
```

→ `WORK_QUEUE_ARGUMENTS` gets one such block per argument, and
`x-dead-letter-routing-key` is the one whose absence loses data silently (RESEARCH Pitfall 3) — write
that at the constant, plus the one-way-declaration warning from Pitfall 2.

---

### `src/prope/call_ledger/schemas.py` (model, validation)

**Analog:** `src/prope/call_ledger/domain.py` — vocabularies as `StrEnum` byte-identical to the
database `CHECK` sets, value objects as frozen slotted dataclasses, and validation in `__post_init__`
that raises a sentence.

```python
@dataclass(frozen=True, slots=True)
class CallRecordDraft:
    ...
    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError(
                f"created_at for {self.call_id} is naive; a naive datetime is read against the "
                "server's time zone, which makes an effective-dated price depend on geography"
            )
```

→ pydantic v2 models are the route/envelope layer; **do not re-declare the vocabularies** — import
`Source`, `Outcome`, `CostStatus`, `UsageStatus` from `domain.py`. `domain.py:1-19` states the
byte-identity rule and `domain.py:12-14` states that statuses stay literal ASCII at rest and are
translated only at the API edge (ADR-0053) — which is the precedent for `check_spend_ceiling`'s
machine `code`.

---

### `tests/conftest.py` (modified — the D-22 broker fixture)

**Analog:** the same file's Postgres rig. Copy the *shape*: session-scoped container, pinned image tag,
derived URL helper, and an autouse per-test cleanup.

**Container + session fixture** (`conftest.py:99-105`):

```python
@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """A pristine PostgreSQL 17 with the chain applied, for the whole session."""
    with PostgresContainer("postgres:17", driver="asyncpg") as container:
        _upgrade_to_head(container)
        asyncio.run(_set_test_role_passwords(container))
        yield container
```

**URL helper** (`conftest.py:69-74`):

```python
def _role_url(container: PostgresContainer, role: str) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5432)
    ...
```

**Autouse cleanup between tests, discovered not listed** (`conftest.py:61-66, 138-147`):

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
        ...
```

→ The broker equivalent is a **per-test queue purge** (never a delete-and-redeclare — a mismatched
redeclare is a 406 that reads as an unrelated failure). Import path is
`testcontainers.community.rabbitmq`, matching `conftest.py:46`'s `testcontainers.community.postgres`.

**Also copy the four-decision docstring** (`conftest.py:1-34`) — the new broker fixture's decisions
(session scope, purge-not-redeclare, image pin) belong in the same docstring, in the same voice.

---

### `tests/broker/`, `tests/integration/` (test, event-driven)

**Analog:** `tests/integration/test_body_retention_delete.py`.

**The test-module docstring names the failure mode the tests are shaped against** (`:1-27`):

```python
"""CL-08: expired bodies are gone by any query, and their call records remain.

**A retention job that runs cleanly and deletes nothing looks healthy.** So
nothing in this file asks the job what it did and believes the answer. Every
assertion is a direct query against ``ledger.call_body`` through
``migrate_engine`` — the owner role, which is subject to no policy. ...
"""
```

→ The drain's equivalent: *"a drain that acks and writes nothing looks healthy"* — assert through
`migrate_engine`, never through the code under test.

**Assert through the real write path, never by hand-inserting the state under test** (`:57-68`):

```python
def _expiring_at(call_id: str, expires_at, **overrides):
    """A gateway draft whose body will be stamped to expire at ``expires_at``.

    The stamp is produced by the real write path — ``created_at`` plus the
    writer's retention window — rather than written into ``call_body`` by hand,
    so this test cannot pass against a writer that stamps something else.
    """
```

**Shared fixture helpers live in `tests/unit/__init__.py`** and are imported across packages
(`test_body_retention_delete.py:37`):

```python
from tests.unit import WORKSPACE_A, WORKSPACE_B, day, gateway_draft
```

→ Add `eval_draft` / `WORKSPACE_C` there rather than defining local factories per test module.

---

### `pyproject.toml` (modified)

**Analog:** the file's own existing pins. Every dependency carries a comment naming the ADR or
assumption that put it there, and a pin whose upper bound is explained:

```python
    # ADR-0026 — FastAPI + uvicorn + pydantic v2 is the one runtime.
    # Pinned in phase 1 (D-03); no route is built until phase 2.
    "pydantic==2.13.4",
```

→ `aio-pika==9.6.2` gets the same treatment, and RESEARCH's version note (A2 — 9.6.2 over 10.0.1,
because `aiormq 7` is a one-month-old major on the durability path) is the comment text. Dev group:
`testcontainers[postgresql,rabbitmq]==4.15.0`, with a line naming `pika` as the transitive sync client
so its appearance in `uv.lock` is expected.

---

## Shared Patterns

### Tenant scoping — the only way a workspace reaches SQL

**Source:** `src/prope/db/session.py:39-58`
**Apply to:** `drain.py`, `seams.py` (all three), `retention_settings.py`, every route handler that reads

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

**Two obligations this phase inherits from that module's docstring (`session.py:7-14`):**
1. *"There is no interpolation of any kind in this module, **and a source gate asserts it**."* — Phase 1's
   verifier logged WR-06: **no such gate exists.** This is the phase where `workspace_id` starts
   arriving from outside the process (broker payload). Write the gate or delete the sentence.
2. The docstring already names this phase: *"a value which, from phase 2 onward, arrives inside a
   broker payload"* — pydantic validation of the envelope is the V5 control.

### The one write path

**Source:** `src/prope/call_ledger/writer.py:1-8, 171-186`
**Apply to:** `drain.py`, `seams.py::price_usage` — and nowhere else may write SQL against
`ledger.call_record`, `ledger.call_body` or `ledger.workspace_spend`.

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

    Raises ``ValueError`` for a batch this encoding cannot represent: more than
    one workspace, more than one currency, an ``eval`` record carrying a body,
    or a priced record whose cost works out to zero.
    """
```

**Those four `ValueError` cases are the drain's "permanent failure" classification list** (RESEARCH
Pitfall 1) — plus `UniqueViolationError` on redelivery, which has no upsert behind it until Phase 3.

### Never zero, no fourth state — the refusal posture

**Source:** `src/prope/call_ledger/writer.py:25-36, 244-250`
**Apply to:** every new refusal — `check_spend_ceiling`'s reason, `get_run_totals` on mixed currency,
the drain's failure classification, the routes' `422`

```python
                    raise ValueError(
                        f"{draft.call_id} prices to {cost} against price row {price_row_id}: "
                        f"{draft.input_tokens} input and {draft.output_tokens} output tokens at "
                        f"{price.input_price_per_1k}/{price.output_price_per_1k} per 1k. A priced "
                        "record cannot record a cost of zero, and neither a zero nor a downgrade "
                        "to unpriced would be true"
                    )
```

The template: **identifier, the two values in tension, the rule, and why both alternative answers are
false.** `check_spend_ceiling` is the one exception in kind — same voice, **no figure in any branch**.

### No body, no log, no metric label

**Source:** `src/prope/call_ledger/writer.py:37-39`
**Apply to:** `enqueue.py`'s publish-failure line (D-21), `supervisor.py`'s `job_crashed` line,
`drain.py`'s DLQ-reject line

```python
"""...
**No body reaches a log line or a metric label** (A-046). This module writes a
body to exactly one place — ``ledger.call_body`` — and it emits no log and no
metric at all.
"""
```

→ Phase 2 is the first phase that emits any log or metric. State the A-046 rule in each such module's
docstring, and RESEARCH's Security Domain names the test: provoke a failed confirm and grep the
captured log record for the body string.

### Money and time

**Source:** `src/prope/call_ledger/domain.py:15-19`
**Apply to:** `schemas.py`, `seams.py`, every route response carrying a cost

```python
"""**No field on any object here is a binary floating-point number.** Money is
``decimal.Decimal`` end to end (Pitfall 5) and every timestamp is a
timezone-aware ``datetime`` (Pitfall 7): a naive value compared against a
``timestamptz`` column is interpreted against the server's time zone ...
"""
```

→ pydantic v2 models must type money as `Decimal` and datetimes as aware, and serialise a `Decimal` as
a JSON string rather than a float.

---

## No Analog Found

The planner should follow `02-RESEARCH.md`'s Architecture Patterns 1–4 and Code Examples for these,
because nothing comparable exists in the repository yet. **Each of these is a shape seven more modules
inherit** (D-13, D-14), so the docstring density obligation applies with extra force.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/prope/app.py` | entrypoint | request-response | No FastAPI app exists. `Makefile:8` already targets `prope.app:app`. RESEARCH § Recommended Project Structure is the reference |
| `src/prope/call_ledger/api.py` | controller | request-response | **No route exists anywhere in the repo.** No error envelope, no pagination helper, no auth dependency to copy. A-045 / ADR-0003 supply the conventions; RESEARCH Pitfall 11 supplies the `require_session` placeholder shape |
| `src/prope/worker.py` | entrypoint | process | No process entrypoint exists |
| `src/prope/supervisor.py` | utility | event-driven | No `asyncio.TaskGroup` usage in the repo. RESEARCH Pattern 4 has the sketch, plus the two named traps (ExceptionGroup cancellation; `add_signal_handler` is unimplemented on Windows) |
| `src/prope/call_ledger/enqueue.py` | service | pub-sub | No broker code exists. RESEARCH Pattern 2 (three-branch confirm classification matching the declared metric labels) is the reference |
| `src/prope/broker/topology.py` (content) | config | declaration | Shape borrowed from `alembic/ddl.py`; the *content* is entirely new. RESEARCH Pattern 1 |
| Prometheus counters / structlog config | config | — | `structlog` and `prometheus-client` are pinned and **completely unused**. Phase 2 is the first user; there is no logging config, no metric registry, no naming convention in-repo. The metric names and label sets come from `docs/modules/call-ledger.lock.yml:355-373` |
| `tests/broker/` package | test | event-driven | No broker test exists. Fixture shape from `tests/conftest.py`; assertion posture from `tests/integration/test_body_retention_delete.py`; the read-back technique from RESEARCH § Code Examples |

**Note on the two repo files that look like analogs and are not:** root `Dockerfile` and
`docker-compose.yml` are boilerplate from another project (`python:3.11-slim`, a `requirements.txt`
that does not exist, a single `backend` service with a `/health` check). They contradict ADR-0026,
ADR-0033 and INT-030. **Do not extend them.** RESEARCH § State of the Art routes them to
`deferred-items.md`.

---

## Metadata

**Analog search scope:** `src/prope/**`, `alembic/**`, `tests/**`, `pyproject.toml`, `Makefile`
**Files scanned:** 17 source files (2,059 lines of Python across `src/`, `alembic/versions/`,
`tests/conftest.py`), 4 test packages enumerated
**Pattern extraction date:** 2026-08-10
