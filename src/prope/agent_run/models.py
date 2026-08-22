from sqlalchemy import Column, DateTime, ForeignKeyConstraint, Integer, Table, Text
from sqlalchemy.dialects.postgresql import JSONB

from prope.db.metadata import metadata

TIMESTAMPTZ = DateTime(timezone=True)

run = Table(
    "run", metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("requested_by", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("plan_basis", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("prompt_id", Text),
    Column("version_id", Text),
    Column("source_refs", JSONB, nullable=False),
    Column("result_actions", JSONB, nullable=False),
    Column("progress_current", Integer),
    Column("progress_total", Integer),
    Column("progress_unit", Text),
    Column("idempotency_key", Text, nullable=False),
    Column("lease_owner", Text),
    Column("lease_until", TIMESTAMPTZ),
    Column("acknowledged_at", TIMESTAMPTZ),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    Column("started_at", TIMESTAMPTZ),
    Column("finished_at", TIMESTAMPTZ),
    schema="agent",
)

node = Table(
    "node", metadata,
    Column("run_id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("id", Text, primary_key=True),
    Column("sequence", Integer, nullable=False),
    Column("capability", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("idempotency_key", Text, nullable=False),
    Column("evidence_refs", JSONB, nullable=False),
    Column("progress_current", Integer),
    Column("progress_total", Integer),
    Column("progress_unit", Text),
    Column("started_at", TIMESTAMPTZ),
    Column("finished_at", TIMESTAMPTZ),
    ForeignKeyConstraint(["run_id"], ["agent.run.id"], ondelete="CASCADE"),
    schema="agent",
)

edge = Table(
    "edge", metadata,
    Column("run_id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("source_node_id", Text, primary_key=True),
    Column("target_node_id", Text, primary_key=True),
    ForeignKeyConstraint(["run_id"], ["agent.run.id"], ondelete="CASCADE"),
    ForeignKeyConstraint(
        ["run_id", "source_node_id"], ["agent.node.run_id", "agent.node.id"],
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ["run_id", "target_node_id"], ["agent.node.run_id", "agent.node.id"],
        ondelete="CASCADE",
    ),
    schema="agent",
)
