"""The six tables call-ledger owns, as SQLAlchemy Core objects.

Six, not the five ``docs/modules/call-ledger.lock.yml`` ``data.owns`` names.
``workspace_retention`` is D-09's declared deviation, raised as ``OQ-018``
rather than patched into the spec — see ``alembic/versions/0004_workspace_
retention.py`` for the argument.

**These are not the source of truth for the schema. The migration is** (D-04,
A-128). Nothing here creates, alters or drops anything: ``metadata.create_all``
is never called in this project, and would produce a database missing every RLS
policy, every grant and every REVOKE — that is, a database with none of the
guarantees the tables exist to carry. What lives here is the shape the
application queries through, so a repository writes ``select(call_record)``
instead of assembling SQL by hand.

The drift risk that follows is real and is answered by a test rather than by
discipline: ``tests/architecture/test_schema_invariants.py`` asserts every table
declared here has a live counterpart whose columns are a superset of the
declaration.

Each table declares ``schema="ledger"`` explicitly rather than inheriting a
default from the ``MetaData`` (Pitfall 11). One shared ``MetaData`` with no
default schema is the pattern the other seven modules inherit; a
``MetaData(schema="ledger")`` shared across eight modules would silently file
the next module's tables under ``ledger``.

SQLAlchemy 2.0 style throughout: these are consumed with ``select()``, never
with the legacy ``Query`` interface.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    Interval,
    Numeric,
    Table,
    Text,
)

from prope.db.metadata import metadata

#: Money is exact decimal end to end, never a float. The scale spans a USD price
#: of order 0.00002 per 1k tokens and a VND price of order 1000, and a cost is
#: quantised at this scale rather than at a currency's minor units — which would
#: store 0.00 for a realistic per-call figure.
MONEY = Numeric(20, 10)

#: A-003: UTC with an explicit offset. The naive type discards it silently.
TIMESTAMPTZ = DateTime(timezone=True)


call_record = Table(
    "call_record",
    metadata,
    Column("call_id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("source", Text, nullable=False),
    Column("prompt_id", Text),
    Column("version_id", Text),
    Column("revision_number", Integer),
    Column("run_id", Text),
    Column("case_id", Text),
    # Caller-supplied correlation (migration 0023). Values, never foreign keys —
    # see `domain.CallRecordDraft` for why a chain whose head has been retained
    # away must still be storable.
    Column("conversation_id", Text),
    Column("parent_call_id", Text),
    Column("consumer_key_id", Text),
    Column("actor_id", Text),
    Column("provider_config_id", Text),
    Column("upstream_model", Text),
    Column("outcome", Text, nullable=False),
    Column("pinned", Boolean, nullable=False),
    Column("fallback", Boolean, nullable=False),
    Column("streaming", Boolean, nullable=False),
    Column("input_tokens", BigInteger),
    Column("output_tokens", BigInteger),
    Column("usage_status", Text, nullable=False),
    Column("cost", MONEY),
    Column("currency", Text),
    Column("price_row_id", Text),
    Column("cost_status", Text, nullable=False),
    Column("added_latency_ms", Integer),
    Column("upstream_duration_ms", Integer),
    Column("error_class", Text),
    # The call's own time, supplied by the caller. Never a default here and
    # never one in the DDL: a default would price a backlogged record at drain
    # time (ADR-0019).
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("written_at", TIMESTAMPTZ, nullable=False),
    schema="ledger",
)


call_body = Table(
    "call_body",
    metadata,
    Column("call_id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("request_body", Text),
    Column("response_body", Text),
    Column("byte_size", BigInteger),
    Column("expires_at", TIMESTAMPTZ, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema="ledger",
)


price_table = Table(
    "price_table",
    metadata,
    Column("price_row_id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("provider_config_id", Text, nullable=False),
    Column("upstream_model", Text, nullable=False),
    Column("input_price_per_1k", MONEY, nullable=False),
    Column("output_price_per_1k", MONEY, nullable=False),
    Column("minimum_charge_per_request", MONEY, nullable=False),
    Column("currency", Text, nullable=False),
    Column("effective_from", TIMESTAMPTZ, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema="ledger",
)


workspace_spend = Table(
    "workspace_spend",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("period_month", Date, primary_key=True),
    Column("currency", Text),
    Column("total_cost", MONEY),
    Column("call_count", BigInteger, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema="ledger",
)


spend_ceiling = Table(
    "spend_ceiling",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("monthly_limit", MONEY),
    Column("per_run_limit", MONEY),
    Column("currency", Text),
    Column("enabled", Boolean, nullable=False),
    Column("updated_by", Text),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema="ledger",
)


#: D-09's sixth table. ``Interval`` rather than an integer of days so the value
#: round-trips as a ``timedelta`` and never needs unit arithmetic that could
#: disagree with ``writer.DEFAULT_RETENTION_WINDOW``.
workspace_retention = Table(
    "workspace_retention",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("retention_window", Interval, nullable=False),
    Column("updated_by", Text, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema="ledger",
)
