from sqlalchemy import Boolean, Column, DateTime, Table, Text
from sqlalchemy.dialects.postgresql import JSONB

from prope.db.metadata import metadata

TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "release"

approval = Table(
    "approval",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("version_id", Text, nullable=False),
    Column("decision", Text, nullable=False),
    Column("reviewer_id", Text, nullable=False),
    Column("comment", Text),
    Column("acknowledgement_reason", Text),
    Column("evidence_digest", JSONB, nullable=False),
    Column("self_approved", Boolean, nullable=False),
    Column("decided_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

release = Table(
    "release",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("version_id", Text),
    Column("kind", Text, nullable=False),
    Column("previous_version_id", Text),
    Column("approval_id", Text),
    Column("break_glass", Boolean, nullable=False),
    Column("reason", Text),
    Column("released_by", Text, nullable=False),
    Column("released_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

review_task = Table(
    "review_task",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("version_id", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("assigned_role", Text, nullable=False),
    Column("due_at", TIMESTAMPTZ),
    Column("status", Text, nullable=False),
    Column("created_from_release_id", Text),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("closed_by", Text),
    Column("closed_at", TIMESTAMPTZ),
    Column("closed_note", Text),
    schema=SCHEMA,
)
