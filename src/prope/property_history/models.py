"""The two tables the ``history`` schema owns, as SQLAlchemy Core objects.

**These are not the source of truth for the schema. The migration is** (D-04,
A-128). ``metadata.create_all`` is never called and would produce a database
missing every RLS policy, every grant and every REVOKE — a database with none of
the guarantees the tables exist to carry.

**Their only consumer is the drift guard** in
``tests/architecture/test_schema_invariants.py``. On the one module whose product
claim *is* its schema, that mechanism is worth the file: nothing else in
``src/prope/property_history/`` selects through them, because the two statements
this module issues are raw ``text()`` so they stay inside
``tests/architecture/test_no_sql_interpolation.py``'s walk.

Each table declares ``schema="history"`` explicitly rather than inheriting a
default; the one shared ``MetaData`` has none.
"""

from sqlalchemy import ARRAY, BigInteger, Boolean, Column, DateTime, Table, Text
from sqlalchemy.dialects.postgresql import JSONB

from prope.db.metadata import metadata

#: A-003: UTC with an explicit offset. The naive type discards it silently.
TIMESTAMPTZ = DateTime(timezone=True)


history_action_registry = Table(
    "history_action_registry",
    metadata,
    Column("action", Text, primary_key=True),
    Column("target_type", Text, nullable=False),
    Column("detail_keys", ARRAY(Text), nullable=False),
    Column("requires_reason", Boolean, nullable=False),
    Column("writing_module", Text, nullable=False),
    schema="history",
)


history_event = Table(
    "history_event",
    metadata,
    Column("seq", BigInteger, nullable=False),
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("actor_type", Text, nullable=False),
    Column("actor_id", Text),
    Column("action", Text, nullable=False),
    Column("target_type", Text, nullable=False),
    Column("target_id", Text, nullable=False),
    Column("scope_prompt_id", Text),
    Column("reason", Text),
    Column("details", JSONB, nullable=False),
    Column("occurred_at", TIMESTAMPTZ, nullable=False),
    schema="history",
)
