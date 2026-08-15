"""The two `search` tables as SQLAlchemy Core `Table` objects.

Tables:
  - prompt_search_index: stores extracted metadata and embeddings for indexed prompts
  - prompt_search_index_job: tracks async indexing job lifecycle

id prefix: psi_ for prompt_search_index, psj_ for prompt_search_index_job
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Numeric,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.types import UserDefinedType

from prope.db.metadata import metadata

#: A-003: UTC with an explicit offset
TIMESTAMPTZ = DateTime(timezone=True)

#: Schema for this module
SCHEMA = "search"


class Vector(UserDefinedType):
    """The pgvector column type without coupling runtime code to an ORM plugin."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_kw: object) -> str:
        return f"VECTOR({self.dimensions})"


prompt_search_index = Table(
    "prompt_search_index",
    metadata,
    Column("id", Text, primary_key=True),
    Column("prompt_id", Text, nullable=False),
    Column("version_id", Text, nullable=False),
    Column("workspace_id", Text, nullable=False),
    Column("keywords", ARRAY(Text), nullable=False, default=list),
    Column("topics", ARRAY(Text), nullable=False, default=list),
    Column("entities", ARRAY(Text), nullable=False, default=list),
    Column("variations", JSONB, nullable=False, default=dict),
    Column("language", ARRAY(Text), nullable=False, default=list),
    # `latest` or `released` — at most one of each per prompt. See migration 0014.
    Column("role", Text, nullable=False),
    Column("content_embedding", Vector(1536), nullable=False),
    Column("embedding_model", Text, nullable=False),
    Column("is_bilingual", Boolean, nullable=False, default=False),
    Column("indexed_at", TIMESTAMPTZ, nullable=False),
    Column("indexed_by", Text, nullable=False),
    Column("nearest_neighbor_id", Text),
    Column("nearest_neighbor_similarity", Numeric(6, 5)),
    schema=SCHEMA,
)


prompt_search_index_job = Table(
    "prompt_search_index_job",
    metadata,
    Column("job_id", Text, primary_key=True),
    Column("prompt_id", Text, nullable=False),
    Column("version_id", Text, nullable=False),
    Column("workspace_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("started_at", TIMESTAMPTZ),
    Column("completed_at", TIMESTAMPTZ),
    Column("error", Text),
    Column("result_json", JSONB),
    Column("created_by", Text, nullable=False),
    schema=SCHEMA,
)
