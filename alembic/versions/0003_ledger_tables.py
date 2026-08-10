"""the remaining four ledger tables, the T-006 revokes, and the deferred price FK

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-10

The four tables ``call_record`` did not need in order to exist: ``call_body``,
``price_table``, ``workspace_spend`` and ``spend_ceiling``. Each arrives with
its whole guarantee stack in one revision — columns, named CHECKs, indexes, the
tenant policy and the grant matrix — the same shape 0002 established.

T-006 IS THE POINT OF THIS REVISION. ``price_table`` is granted ``SELECT`` and
``INSERT`` and nothing else. That absence is what makes a recorded cost
explicable years later: a price is never edited and never deleted, a change is a
new row with a later ``effective_from``, and the old row stays because a figure
recorded under it must remain derivable. ADR-0025 rejects the two alternatives
by name — a ``BEFORE UPDATE`` trigger is droppable by the role it polices and
disabled wholesale by ``ALTER TABLE ... DISABLE TRIGGER``, and a repository
convention is not enforcement at all. D-07 pulled this into Phase 1 rather than
Phase 3 precisely because a later REVOKE is blocked by whatever application code
has come to depend on the privilege in the meantime.

NO FOREIGN KEY LEAVES ``ledger``. ``workspace_id``, ``provider_config_id`` and
``created_by`` are values, not references. Beyond the module-boundary argument,
PostgreSQL documents that referential-integrity checks always bypass row
security, so a cross-schema foreign key from a tenant-scoped table would be a
covert channel. The two foreign keys added here are both intra-schema:
``call_body.call_id`` -> ``call_record.call_id``, and the deferred
``call_record.price_row_id`` -> ``price_table.price_row_id`` that 0002 left as a
plain ``text`` column because its target did not exist yet.

TYPES follow 0002. Every ``*_id`` is ``text`` (ADR-0003 prefixed ULIDs), every
timestamp is ``timestamptz`` (A-003), every money column is ``numeric(20,10)``
— wide enough for a USD price of order 0.00002 per 1k tokens and a VND price of
order 1000, and never rounded to a currency's minor units, which would store
``0.00`` for a realistic per-call figure and violate the never-zero rule.
``period_month`` is a ``date`` holding the first day of the month in UTC:
sortable, comparable and indexable, none of which a ``YYYY-MM`` text is.
"""

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


CREATE_CALL_BODY = """
CREATE TABLE ledger.call_body (
    call_id        text         NOT NULL,

    -- Denormalised, never joined for authorisation. Added at lock step 4 for a
    -- reason worth restating: reachable only through call_record, this table —
    -- the one table in Prope holding raw end-user content — would have been
    -- skipped by ADR-0045's coverage walk, which enumerates tables CARRYING
    -- workspace_id and asserts a policy on each.
    workspace_id   text         NOT NULL,

    -- text, not jsonb. These are provider payloads, and jsonb would reject a
    -- malformed body — which is exactly the body worth keeping.
    request_body   text,
    response_body  text,
    byte_size      bigint,

    -- Stamped at write time from the workspace's retention window (A-106), so
    -- the deletion job is an index scan on one column rather than a join
    -- against a settings table that may have changed since.
    expires_at     timestamptz  NOT NULL,

    -- No default, for the same reason call_record.created_at has none: the
    -- caller supplies the call's own time, never the drain's.
    created_at     timestamptz  NOT NULL,

    CONSTRAINT pk_call_body PRIMARY KEY (call_id),

    -- Intra-schema, and no ON DELETE in either direction. Deleting a body at
    -- retention must not touch the record: A-040 keeps the metadata and drops
    -- the body, which is the whole reason these are two tables.
    CONSTRAINT fk_call_body_call_id
        FOREIGN KEY (call_id) REFERENCES ledger.call_record (call_id)
);
"""

CREATE_PRICE_TABLE = """
CREATE TABLE ledger.price_table (
    price_row_id         text            NOT NULL,
    workspace_id         text            NOT NULL,
    provider_config_id   text            NOT NULL,

    -- Free text, deliberately NOT validated against provider-access's model
    -- catalogue: that would require an outbound dependency this module is
    -- forbidden to have, and the reconciliation it would buy is already covered
    -- by the unpriced worklist, which catches the same mistake from the
    -- direction that matters — a call that produced no cost.
    upstream_model       text            NOT NULL,

    input_price_per_1k   numeric(20,10)  NOT NULL,
    output_price_per_1k  numeric(20,10)  NOT NULL,
    currency             text            NOT NULL,

    -- MUST be allowed to be in the past. CL-05 / AC-5 is precisely "a price row
    -- is added after calls have accrued", and repricing them requires the new
    -- row's effective_from to predate those calls. There is deliberately no
    -- CHECK (effective_from >= now()).
    effective_from       timestamptz     NOT NULL,

    created_by           text            NOT NULL,
    -- Genuinely "when the database saw this", so it does default.
    created_at           timestamptz     NOT NULL DEFAULT now(),

    CONSTRAINT pk_price_table PRIMARY KEY (price_row_id),

    -- Load-bearing, not hygienic. Two rows sharing this key would make
    -- `ORDER BY effective_from DESC LIMIT 1` non-deterministic, and a
    -- non-deterministic number ending up on an approval record is the thing
    -- ADR-0019 exists to prevent. The tie is made impossible rather than
    -- broken. A typo is corrected by superseding it with a later
    -- effective_from.
    --
    -- The column order is also the lookup order, so this constraint's index
    -- serves the effective-dated resolution as a backward index scan
    -- terminating on the first row. No separate index is created over the same
    -- four columns: it would be an exact duplicate.
    CONSTRAINT uq_price_table_workspace_id
        UNIQUE (workspace_id, provider_config_id, upstream_model, effective_from),

    CONSTRAINT ck_price_table_prices_are_non_negative
        CHECK (input_price_per_1k >= 0 AND output_price_per_1k >= 0),
    CONSTRAINT ck_price_table_currency_format
        CHECK (currency ~ '^[A-Z]{3}$')
);
"""

CREATE_WORKSPACE_SPEND = """
CREATE TABLE ledger.workspace_spend (
    workspace_id  text            NOT NULL,

    -- The first day of the month, UTC. A date rather than a 'YYYY-MM' text
    -- because it must sort, compare and index.
    period_month  date            NOT NULL,

    currency      text,
    total_cost    numeric(20,10),

    -- Counts EVERY written record for the (workspace, month), including
    -- unpriced and not_applicable ones; total_cost sums only priced costs.
    -- call_count answers "how much traffic", total_cost answers "how much
    -- money", and conflating them would let unpriced traffic look free.
    call_count    bigint          NOT NULL DEFAULT 0,

    updated_at    timestamptz     NOT NULL DEFAULT now(),

    -- The composite key is what makes A-103's aggregate update a single
    -- conflict-target upsert inside the writer's own transaction, instead of a
    -- SUM over the largest and fastest-growing table in the system.
    CONSTRAINT pk_workspace_spend PRIMARY KEY (workspace_id, period_month),

    CONSTRAINT ck_workspace_spend_currency_format
        CHECK (currency IS NULL OR currency ~ '^[A-Z]{3}$'),

    -- A-107: the currency travels with the figure. A total with no currency is
    -- a number nobody can act on.
    CONSTRAINT ck_workspace_spend_total_cost_carries_currency
        CHECK (total_cost IS NULL OR currency IS NOT NULL)
);
"""

CREATE_SPEND_CEILING = """
CREATE TABLE ledger.spend_ceiling (
    workspace_id   text            NOT NULL,
    monthly_limit  numeric(20,10),
    per_run_limit  numeric(20,10),
    currency       text,

    -- Both limits default to off (A-029).
    enabled        boolean         NOT NULL DEFAULT false,

    -- On the row because there is no property-history event for this: a spend
    -- ceiling is not a state change on a prompt property, so A-014 does not
    -- reach it, and recording it elsewhere would mean inventing a forbidden
    -- edge (A-102).
    updated_by     text,
    updated_at     timestamptz     NOT NULL DEFAULT now(),

    CONSTRAINT pk_spend_ceiling PRIMARY KEY (workspace_id),

    CONSTRAINT ck_spend_ceiling_currency_format
        CHECK (currency IS NULL OR currency ~ '^[A-Z]{3}$')
);
"""

CREATE_INDEXES = (
    # THE retention predicate. ADR-0040 requires it to be an index scan rather
    # than a join against a settings table.
    """
    CREATE INDEX ix_call_body_workspace_id_expires_at
        ON ledger.call_body (workspace_id, expires_at)
    """,
    # prope_call_ledger_oldest_body_age_seconds (Phase 3), if the gauge is
    # computed as a MIN. Cheap now, awkward later on the largest table.
    """
    CREATE INDEX ix_call_body_workspace_id_created_at
        ON ledger.call_body (workspace_id, created_at)
    """,
)

# 0002 left price_row_id as a plain text column because ledger.price_table did
# not exist yet. It exists now, so the reference becomes enforceable: "why is
# this number this number" is answerable by the database rather than by faith.
# No ON DELETE clause of any kind — price_table has no DELETE grant, so the case
# cannot arise, and naming a behaviour for an impossible case invites someone to
# make it possible.
ADD_DEFERRED_PRICE_FK = """
ALTER TABLE ledger.call_record
    ADD CONSTRAINT fk_call_record_price_row_id
    FOREIGN KEY (price_row_id) REFERENCES ledger.price_table (price_row_id)
"""


def upgrade() -> None:
    """Create the remaining four owned tables with their whole guarantee stack."""
    assume_migrate_role()

    op.execute(CREATE_CALL_BODY)
    op.execute(CREATE_PRICE_TABLE)
    op.execute(CREATE_WORKSPACE_SPEND)
    op.execute(CREATE_SPEND_CEILING)

    for statement in CREATE_INDEXES:
        op.execute(statement)

    op.execute(ADD_DEFERRED_PRICE_FK)

    for table in ("call_body", "price_table", "workspace_spend", "spend_ceiling"):
        enable_tenant_rls("ledger", table)

    # SELECT is required alongside DELETE, and is not an oversight: a
    # `DELETE ... WHERE expires_at <= $1` reads a column, and PostgreSQL requires
    # SELECT privilege on every column a statement references. Revoking SELECT
    # here in the name of "no read path" would break the retention job. AC-10's
    # no-read-path guarantee is a property of the ROUTE TABLE (Phase 3), not of
    # the grant matrix. No UPDATE: bodies are written once and deleted.
    grant_table("ledger", "call_body", app_privileges=["SELECT", "INSERT", "DELETE"])

    # T-006 / D-07. No UPDATE and no DELETE, ever. This is the privilege the
    # phase's irreversibility claim rests on.
    grant_table("ledger", "price_table", app_privileges=["SELECT", "INSERT"])

    # UPDATE for A-103's upsert.
    grant_table("ledger", "workspace_spend", app_privileges=["SELECT", "INSERT", "UPDATE"])

    # UPDATE because "set or clear a ceiling" is an update.
    grant_table("ledger", "spend_ceiling", app_privileges=["SELECT", "INSERT", "UPDATE"])

    reset_role()


def downgrade() -> None:
    """Drop the four tables and the deferred foreign key that depends on one."""
    assume_migrate_role()
    op.execute("ALTER TABLE ledger.call_record DROP CONSTRAINT IF EXISTS fk_call_record_price_row_id")
    op.execute("DROP TABLE IF EXISTS ledger.spend_ceiling")
    op.execute("DROP TABLE IF EXISTS ledger.workspace_spend")
    op.execute("DROP TABLE IF EXISTS ledger.price_table")
    op.execute("DROP TABLE IF EXISTS ledger.call_body")
    reset_role()
