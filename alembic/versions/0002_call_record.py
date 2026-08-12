"""call_record with its constraints, indexes, policy and grants

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-10

One revision carrying the whole guarantee stack for one table: the columns, the
CHECK set, the indexes, the RLS policy and the grant matrix. Each guarantee
stays greppable through the ``alembic/ddl.py`` helper that emits it.

The DDL is written out rather than assembled from ``op.create_table``: this
project's revisions are hand-written (D-04), the constraint names are asserted
by tests, and the names below are exactly what ``prope.db.metadata``'s naming
convention renders (``ck_%(table_name)s_%(constraint_name)s``,
``pk_%(table_name)s``). Spelling them out makes the diff and the database agree
without a reader having to run a template in their head.

TYPES. Every ``*_id`` is ``text`` — ADR-0003 identifiers are prefixed ULIDs
(``cal_01J...``), not UUIDs. Vocabularies are ``text`` with named CHECKs and
never a native PostgreSQL enum: adding a value to an enum later cannot run
inside a transaction block, and removing one is impossible at any price.
Timestamps are ``timestamptz`` (A-003 — UTC with an explicit offset; the naive
type silently discards it). Money is ``numeric(20,10)``, wide enough for a USD
price of order 0.00002 per 1k tokens and a VND price of order 1000, and never
rounded to a currency's minor units.

NO FOREIGN KEY LEAVES ``ledger``. ``workspace_id``, ``prompt_id``,
``version_id`` and ``provider_config_id`` are values, not references, so the
audit trail survives independently of the registry's current state. Beyond the
module-boundary argument, PostgreSQL's referential-integrity checks always
bypass row security, so a cross-tenant FK would be a covert channel.
``price_row_id`` is a plain ``text`` column here; its in-schema FK to
``ledger.price_table`` is added in 0003, once that table exists.
"""

from collections.abc import Sequence

# `alembic/ddl.py`, imported by bare name rather than as `alembic.ddl` — that
# dotted name resolves to the installed Alembic package's own dialect-DDL
# submodule. `env.py` puts this directory on the path.
from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_CALL_RECORD = """
CREATE TABLE ledger.call_record (
    call_id               text            NOT NULL,
    workspace_id          text            NOT NULL,
    source                text            NOT NULL,
    prompt_id             text,
    version_id            text,
    revision_number       integer,
    run_id                text,
    case_id               text,
    consumer_key_id       text,
    actor_id              text,
    provider_config_id    text,
    upstream_model        text,
    outcome               text            NOT NULL,
    pinned                boolean         NOT NULL,
    fallback              boolean         NOT NULL,
    streaming             boolean         NOT NULL,
    input_tokens          bigint,
    output_tokens         bigint,
    usage_status          text            NOT NULL,
    cost                  numeric(20,10),
    currency              text,
    price_row_id          text,
    cost_status           text            NOT NULL,
    added_latency_ms      integer,
    upstream_duration_ms  integer,
    error_class           text,

    -- NO COLUMN DEFAULT, deliberately. The caller supplies created_at, because
    -- a default would price a backlogged record at drain time: a call made on
    -- day 5 and written on day 12 would be priced at day 12, and CL-03 would
    -- pass on an idle machine and fail under load. This is the single easiest
    -- way to get CL-03 subtly wrong (ADR-0019).
    created_at            timestamptz     NOT NULL,
    -- written_at is genuinely "when the database saw this", so it does default.
    written_at            timestamptz     NOT NULL DEFAULT now(),

    CONSTRAINT pk_call_record PRIMARY KEY (call_id),

    CONSTRAINT ck_call_record_usage_status_values
        CHECK (usage_status IN ('reported', 'unknown')),
    CONSTRAINT ck_call_record_cost_status_values
        CHECK (cost_status IN ('priced', 'unpriced', 'not_applicable')),
    CONSTRAINT ck_call_record_source_values
        CHECK (source IN ('gateway', 'eval')),
    CONSTRAINT ck_call_record_outcome_values
        CHECK (outcome IN ('ok', 'fallback', 'truncated', 'caller_error', 'upstream_error')),
    CONSTRAINT ck_call_record_currency_format
        CHECK (currency IS NULL OR currency ~ '^[A-Z]{3}$'),

    -- ROADMAP success criterion 2, literally: "no row anywhere records a cost
    -- of zero". *Anywhere* is a table-level statement, so it is a table-level
    -- constraint and not a guard in the writer.
    CONSTRAINT ck_call_record_cost_is_never_zero
        CHECK (cost IS NULL OR cost > 0),

    -- CL-11 / AC-11: a provider that returned no usage object records NULL
    -- tokens, never zeros. An absent figure asks a question; a wrong figure
    -- answers it.
    CONSTRAINT ck_call_record_unknown_usage_is_null
        CHECK (
            (usage_status = 'unknown'
                AND input_tokens IS NULL AND output_tokens IS NULL)
            OR
            (usage_status = 'reported'
                AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL)
        ),

    -- CL-04 / AC-4 / AC-11: each cost state carries exactly its own fields, so
    -- a missing price is a value rather than a zero.
    CONSTRAINT ck_call_record_cost_state_is_coherent
        CHECK (
            (cost_status = 'priced'
                AND cost IS NOT NULL AND currency IS NOT NULL
                AND price_row_id IS NOT NULL AND usage_status = 'reported')
            OR
            (cost_status = 'unpriced'
                AND cost IS NULL AND currency IS NULL
                AND price_row_id IS NULL AND usage_status = 'reported')
            OR
            (cost_status = 'not_applicable'
                AND cost IS NULL AND currency IS NULL
                AND price_row_id IS NULL AND usage_status = 'unknown')
        ),

    -- "a database constraint here, not a hope" (call-ledger.lock.yml:162-164).
    -- The "100% of gateway calls record a version ID" success metric.
    CONSTRAINT ck_call_record_gateway_calls_carry_version_id
        CHECK (source <> 'gateway' OR version_id IS NOT NULL),

    CONSTRAINT ck_call_record_eval_calls_carry_run
        CHECK (
            source <> 'eval'
            OR (run_id IS NOT NULL AND case_id IS NOT NULL AND consumer_key_id IS NULL)
        )
);
"""

# Every index leads with workspace_id, as every declared index in Prope does.
CREATE_INDEXES = (
    """
    CREATE INDEX ix_call_record_workspace_id_created_at
        ON ledger.call_record (workspace_id, created_at DESC)
    """,
    # Serves BOTH the CL-04 unpriced worklist and the CL-05 repricing scan. A
    # partial index over a status that is rare by design is close to free.
    """
    CREATE INDEX ix_call_record_unpriced_worklist
        ON ledger.call_record (workspace_id, provider_config_id, upstream_model)
        WHERE cost_status = 'unpriced'
    """,
    # get_run_totals lands in phase 2; cheap to add now, awkward to add later
    # on what becomes the largest table in the system.
    """
    CREATE INDEX ix_call_record_workspace_id_run_id
        ON ledger.call_record (workspace_id, run_id)
        WHERE run_id IS NOT NULL
    """,
)


def upgrade() -> None:
    """Create ledger.call_record with its whole guarantee stack."""
    assume_migrate_role()

    op.execute(CREATE_CALL_RECORD)
    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("ledger", "call_record")

    # UPDATE is retained for A-099's upsert and for CL-05 repricing.
    # DELETE is deliberately absent: nothing in the module deletes a call
    # record, and T-006 wants that to be a privilege rather than a convention.
    grant_table(
        "ledger",
        "call_record",
        app_privileges=["SELECT", "INSERT", "UPDATE"],
    )

    reset_role()


def downgrade() -> None:
    """Drop the table; the policy, indexes and grants go with it."""
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS ledger.call_record")
    reset_role()
