"""The three `provider` tables as Core `Table` objects. Not the source of truth."""

from sqlalchemy import Boolean, Column, DateTime, Integer, Table, Text

from prope.db.metadata import metadata

TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "provider"

provider_config = Table(
    "provider_config",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("adapter", Text, nullable=False),
    Column("base_url", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("credential_id", Text),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    Column("last_verified_at", TIMESTAMPTZ),
    Column("verification_status", Text, nullable=False),
    Column("verification_error", Text),
    Column("interactive_concurrency", Integer, nullable=False),
    Column("batch_concurrency", Integer, nullable=False),
    schema=SCHEMA,
)

credential = Table(
    "credential",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("provider_config_id", Text, nullable=False),
    Column("ciphertext", Text, nullable=False),
    Column("nonce", Text, nullable=False),
    Column("wrapped_dek", Text, nullable=False),
    Column("kek_version", Integer, nullable=False),
    Column("last_four", Text, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("rotated_at", TIMESTAMPTZ),
    schema=SCHEMA,
)

model_catalogue = Table(
    "model_catalogue",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("provider_config_id", Text, nullable=False),
    Column("model_id", Text, nullable=False),
    Column("display_name", Text),
    Column("source", Text, nullable=False),
    Column("supports_streaming", Boolean, nullable=False),
    Column("available", Boolean, nullable=False),
    Column("first_seen_at", TIMESTAMPTZ, nullable=False),
    Column("last_seen_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)
