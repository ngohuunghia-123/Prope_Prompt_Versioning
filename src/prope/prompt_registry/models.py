"""The three `registry` tables as Core `Table` objects. Not the source of truth.

``prompt_property.released_revision_status`` is deliberately absent. It is a
STORED generated column that exists only to carry BR-03's half of
``fk_prompt_property_released_version_id``, and a column no statement may ever
name is one the application should not be able to name.

``folder`` carries no foreign key to ``prompt_property`` and none the other way.
The join between them is ``folder.slug = prompt_property.namespace``, written out
at the one site that needs it (``repository.list_folders``) rather than declared
here, because it is an outer join in both directions: a folder may hold no
prompts and a prompt may sit in a namespace nobody has named.
"""

from sqlalchemy import Column, DateTime, Integer, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from prope.db.metadata import metadata

TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "registry"

prompt_property = Table(
    "prompt_property",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("namespace", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("purpose", Text, nullable=False),
    Column("owner_id", Text, nullable=False),
    Column("access_level", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("tags", ARRAY(Text), nullable=False),
    Column("released_version_id", Text),
    Column("released_at", TIMESTAMPTZ),
    Column("search_text", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

revision = Table(
    "revision",
    metadata,
    Column("version_id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("revision_number", Integer, nullable=False),
    Column("body", Text, nullable=False),
    Column("original_body", Text, nullable=False),
    Column("original_format", Text, nullable=False),
    Column("original_filename", Text),
    Column("conversion_model", Text),
    Column("conversion_schema_version", Text),
    Column("provider_config_id", Text),
    Column("upstream_model", Text),
    Column("parameters", JSONB, nullable=False),
    Column("fallback_answer", Text),
    Column("change_summary", Text, nullable=False),
    Column("author_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

folder = Table(
    "folder",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("slug", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("color", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)
