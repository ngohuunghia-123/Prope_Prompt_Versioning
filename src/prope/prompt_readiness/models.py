"""The five `readiness` tables as Core `Table` objects. Not the source of truth.

Revision 0029 is. These exist so ``tests/architecture/test_schema_invariants.py``
and ``test_tenant_coverage.py`` can walk this module's tables — a drift guard
only sees tables whose module has been imported, and a walk that finds an empty
declaration set passes **vacuously**, which is the failure shape both of those
files were written to refuse.

No ``ForeignKey`` leaves this schema and only one exists inside it
(``probe_case_result.probe_run_id``). ``prompt_id``, ``version_id``, ``call_id``
and ``actor_id`` are values, the posture ``property_history`` uses for
``target_id`` and ``call_record`` uses for ``prompt_id``. Declaring them as
relationships here would be declaring an edge the module map does not draw, in
the one file where nobody would think to look for one.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from prope.db.metadata import metadata

TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "readiness"

dismissal = Table(
    "dismissal",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("prompt_id", Text, primary_key=True),
    Column("rule_id", Text, primary_key=True),
    Column("reason", Text, nullable=False),
    Column("actor_id", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

report = Table(
    "report",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("version_id", Text, nullable=False),
    Column("profile_snapshot", JSONB, nullable=False),
    Column("rendered_findings", JSONB, nullable=False),
    Column("catalogue_version", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

probe_run = Table(
    "probe_run",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("version_id", Text, nullable=False),
    Column("catalogue_ref", ARRAY(Text), nullable=False),
    Column("status", Text, nullable=False),
    Column("refused_count", Integer, nullable=False),
    Column("leaked_count", Integer, nullable=False),
    Column("error_count", Integer, nullable=False),
    Column("actor_id", Text, nullable=False),
    Column("started_at", TIMESTAMPTZ, nullable=False),
    Column("completed_at", TIMESTAMPTZ),
    schema=SCHEMA,
)

probe_case_result = Table(
    "probe_case_result",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column(
        "probe_run_id",
        Text,
        ForeignKey("readiness.probe_run.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("case_ref", Text, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("assertion_detail", Text, nullable=False),
    Column("latency_ms", Integer),
    Column("call_id", Text),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

lane_b_cache = Table(
    "lane_b_cache",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("fingerprint", Text, primary_key=True),
    Column("findings", JSONB, nullable=False),
    Column("model", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)
