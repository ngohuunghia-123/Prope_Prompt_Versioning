"""The two `observation` tables as Core `Table` objects. Not the source of truth.

Migration 0027 is. These exist so the repository can compose a list query with
five optional predicates in Core rather than by concatenating SQL text, which
``tests/architecture/test_no_sql_interpolation.py`` refuses outright — the same
reason ``prompt_registry.models`` exists.

**Neither table carries a foreign key to anything outside this schema**, and the
absence is the design. ``sighting.call_id`` names a row in ``ledger.call_record``
this module has no edge to; ``observation.adopted_prompt_id`` names a row in
``registry.prompt_property`` that A-049 lets somebody retire. Both are values, on
``property_history.target_id``'s precedent: a constraint here would either forbid
a retention delete the ledger is entitled to perform, or force this module to
read a table it may not.

The one foreign key that IS declared is ``sighting.observation_id``, with
``ON DELETE CASCADE`` — a sighting whose group is gone is not history, it is a
fragment of a body with nothing to say what prompt it came from, and SR-4's
delete exists to remove exactly that.
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY

from prope.db.metadata import metadata

TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "observation"

observation = Table(
    "observation",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("namespace", Text, nullable=False),
    Column("fingerprint", Text, nullable=False),
    Column("body_hash", Text, nullable=False),
    Column("current_body", Text, nullable=False),
    Column("inferred_variables", ARRAY(Text), nullable=False),
    Column("sighting_count", BigInteger, nullable=False),
    Column("first_seen_at", TIMESTAMPTZ, nullable=False),
    Column("last_seen_at", TIMESTAMPTZ, nullable=False),
    Column("upstream_models", ARRAY(Text), nullable=False),
    Column("adopted_prompt_id", Text),
    Column("adopted_by", Text),
    Column("adopted_at", TIMESTAMPTZ),
    Column("dismissed_by", Text),
    Column("dismissed_at", TIMESTAMPTZ),
    Column("dismissal_reason", Text),
    Column("redacted_at", TIMESTAMPTZ),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

sighting = Table(
    "sighting",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column(
        "observation_id",
        Text,
        ForeignKey(f"{SCHEMA}.observation.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("body_hash", Text, nullable=False),
    #: NULL unless this sighting is the one that CHANGED the body. That rule is
    #: what keeps this table from becoming `ledger.call_body` at the same volume
    #: on the readable side of ADR-0018.
    Column("body", Text),
    Column("call_id", Text, nullable=False),
    Column("consumer_key_id", Text, nullable=False),
    Column("upstream_model", Text, nullable=False),
    Column("occurred_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)
