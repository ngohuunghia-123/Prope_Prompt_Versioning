"""The four `improvement` tables as Core `Table` objects. Not the source of truth.

Revision 0033 is. These exist so ``tests/architecture/test_schema_invariants.py``
and ``test_tenant_coverage.py`` can walk this module's tables — a drift guard
only sees tables whose module has been imported, and a walk that finds an empty
declaration set passes **vacuously**, which is the failure shape both of those
files were written to refuse.

No ``ForeignKey`` leaves this schema and only one exists inside it
(``proposal.finding_id``). ``prompt_id``, ``gate_run_id`` and every actor column
are values, the posture ``property_history`` uses for ``target_id`` and
``call_record`` uses for ``prompt_id``. Declaring them as relationships here
would be declaring an edge the module map does not draw, in the one file where
nobody would think to look for one.

**The two partial unique indexes are NOT declared here**, and the omission is
deliberate rather than an oversight. SQLAlchemy Core can express them, and
expressing them would put a second definition of the module's two controls — the
rate cap and the dedupe — in a file whose docstring says it is not the source of
truth. Revision 0033 owns both, and the tests that assert them read the database.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from prope.db.metadata import metadata

TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "improvement"

finding = Table(
    "finding",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("detector_id", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("params", JSONB, nullable=False),
    Column("evidence_line", Text),
    Column("first_seen", TIMESTAMPTZ, nullable=False),
    Column("last_seen", TIMESTAMPTZ, nullable=False),
    Column("occurrence_count", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("dismissed_reason", Text),
    Column("dismissed_by", Text),
    Column("dismissed_at", TIMESTAMPTZ),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

proposal = Table(
    "proposal",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column(
        "finding_id",
        Text,
        ForeignKey("improvement.finding.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("remedy_kind", Text, nullable=False),
    Column("remedy_family", Text),
    Column("candidate_body", Text),
    Column("gate_run_id", Text),
    Column("gate_delta", JSONB),
    Column("status", Text, nullable=False),
    Column("decided_by", Text),
    Column("decided_at", TIMESTAMPTZ),
    Column("expires_at", TIMESTAMPTZ, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

sweep = Table(
    "sweep",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("window_start", TIMESTAMPTZ, nullable=False),
    Column("window_end", TIMESTAMPTZ, nullable=False),
    Column("prompts_scanned", Integer, nullable=False),
    Column("findings_opened", Integer, nullable=False),
    Column("is_first_sweep", Boolean, nullable=False),
    Column("completed_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

schedule = Table(
    "schedule",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("enabled", Boolean, nullable=False),
    Column("cadence_days", Integer, nullable=False),
    Column("namespaces", ARRAY(Text), nullable=False),
    Column("prompt_ids", ARRAY(Text), nullable=False),
    Column("last_run_at", TIMESTAMPTZ),
    Column("updated_by", Text, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)
