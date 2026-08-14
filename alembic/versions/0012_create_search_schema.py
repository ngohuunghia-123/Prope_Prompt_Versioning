"""Create search schema with prompt_search_index and prompt_search_index_job tables.

Revision ID: 0012
Revises: 0011 (call-record prompt index)
Create Date: 2026-08-13

Tables:
  - prompt_search_index: stores extracted metadata and embeddings
  - prompt_search_index_job: tracks async indexing job lifecycle
  - embedding_cache: caches embeddings by text hash

Tables owned by prompt-search module.
"""

from ddl import assume_migrate_role, reset_role

from alembic import op

# revision identifiers
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("GRANT USAGE ON SCHEMA public TO prope_migrate, prope_app")
    # The bootstrap connection creates schemas because the deliberately
    # constrained migration role has no database-level CREATE privilege.
    # Explicit authorization still makes every object below migrate-owned.
    op.execute("CREATE SCHEMA search AUTHORIZATION prope_migrate")
    assume_migrate_role()

    # Create prompt_search_index table
    op.execute(
        """
        CREATE TABLE search.prompt_search_index (
            id TEXT NOT NULL,
            prompt_id TEXT NOT NULL,
            version_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            keywords TEXT[] NOT NULL DEFAULT '{}',
            topics TEXT[] NOT NULL DEFAULT '{}',
            entities TEXT[] NOT NULL DEFAULT '{}',
            variations JSONB NOT NULL DEFAULT '{}',
            language TEXT[] NOT NULL DEFAULT '{}',
            purpose_embedding public.vector(1536) NOT NULL,
            embedding_model TEXT NOT NULL,
            is_bilingual BOOLEAN NOT NULL DEFAULT FALSE,
            indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            indexed_by TEXT NOT NULL,
            nearest_neighbor_id TEXT,
            nearest_neighbor_similarity NUMERIC(6, 5),
            PRIMARY KEY (id)
        )
        """
    )

    # Create indexes on prompt_search_index
    op.execute("CREATE INDEX ix_prompt_search_index_prompt_id ON search.prompt_search_index (prompt_id)")
    op.execute("CREATE UNIQUE INDEX uq_prompt_search_index_prompt_id ON search.prompt_search_index (prompt_id)")
    op.execute("CREATE INDEX ix_prompt_search_index_workspace_id ON search.prompt_search_index (workspace_id)")
    op.execute("CREATE INDEX ix_prompt_search_index_keywords ON search.prompt_search_index USING GIN (keywords)")
    op.execute("CREATE INDEX ix_prompt_search_index_topics ON search.prompt_search_index USING GIN (topics)")
    # Create RLS policy for prompt_search_index
    op.execute(
        """
        ALTER TABLE search.prompt_search_index ENABLE ROW LEVEL SECURITY
        """
    )
    op.execute(
        """
        CREATE POLICY prompt_search_index_tenant_policy ON search.prompt_search_index
            USING (workspace_id = current_setting('app.workspace_id', true))
        """
    )

    # Create prompt_search_index_job table
    op.execute(
        """
        CREATE TABLE search.prompt_search_index_job (
            job_id TEXT NOT NULL,
            prompt_id TEXT NOT NULL,
            version_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            error TEXT,
            result_json JSONB,
            created_by TEXT NOT NULL,
            PRIMARY KEY (job_id)
        )
        """
    )

    # Create indexes on prompt_search_index_job
    op.execute("CREATE INDEX ix_prompt_search_index_job_prompt_id ON search.prompt_search_index_job (prompt_id)")
    op.execute("CREATE INDEX ix_prompt_search_index_job_status ON search.prompt_search_index_job (status)")
    op.execute("ALTER TABLE search.prompt_search_index_job ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY prompt_search_index_job_tenant_policy ON search.prompt_search_index_job
            USING (workspace_id = current_setting('app.workspace_id', true))
        """
    )

    # Create embedding_cache table for caching embeddings
    op.execute(
        """
        CREATE TABLE search.embedding_cache (
            id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            text_hash TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_vector public.vector(1536) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id),
            UNIQUE (workspace_id, text_hash, embedding_model)
        )
        """
    )

    # Create index on embedding_cache
    op.execute("CREATE INDEX ix_embedding_cache_text_hash ON search.embedding_cache (workspace_id, text_hash)")
    op.execute("ALTER TABLE search.embedding_cache ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY embedding_cache_tenant_policy ON search.embedding_cache
            USING (workspace_id = current_setting('app.workspace_id', true))
        """
    )

    # Grant permissions to prope_app role
    op.execute("GRANT USAGE ON SCHEMA search TO prope_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA search TO prope_app")

    # Create trigger to update nearest_neighbor fields on insert
    # Note: This is done at insert time in the application for more control
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS search.embedding_cache CASCADE")
    op.execute("DROP TABLE IF EXISTS search.prompt_search_index_job CASCADE")
    op.execute("DROP TABLE IF EXISTS search.prompt_search_index CASCADE")
    op.execute("DROP SCHEMA IF EXISTS search CASCADE")
    reset_role()
