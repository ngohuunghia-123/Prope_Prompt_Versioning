"""Create durable prompt-ingestion batches, items, and commit proposals.

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA ingestion AUTHORIZATION prope_migrate")
    assume_migrate_role()

    op.execute(
        """
        CREATE TABLE ingestion.import_batch (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            mode TEXT NOT NULL CHECK (mode IN ('files', 'table')),
            status TEXT NOT NULL CHECK (status IN (
                'processing', 'review_ready', 'committing', 'completed',
                'completed_with_errors', 'failed', 'expired'
            )),
            default_namespace TEXT NOT NULL,
            default_access_level TEXT NOT NULL CHECK (default_access_level IN ('private', 'workspace')),
            field_mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
            review_version INTEGER NOT NULL DEFAULT 1 CHECK (review_version > 0),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_ingestion_batch_actor ON ingestion.import_batch "
        "(workspace_id, actor_id, updated_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE ingestion.import_item (
            id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL REFERENCES ingestion.import_batch(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
            source_filename TEXT NOT NULL,
            source_format TEXT NOT NULL CHECK (source_format IN ('txt', 'md', 'markdown', 'json', 'yaml')),
            source_hash TEXT NOT NULL,
            source_text TEXT NOT NULL CHECK (char_length(source_text) BETWEEN 1 AND 32768),
            title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            purpose TEXT NOT NULL DEFAULT '' CHECK (char_length(purpose) <= 2000),
            namespace TEXT NOT NULL,
            name TEXT NOT NULL,
            tags TEXT[] NOT NULL DEFAULT '{}',
            change_summary TEXT NOT NULL CHECK (char_length(change_summary) BETWEEN 1 AND 200),
            canonical_body TEXT CHECK (canonical_body IS NULL OR char_length(canonical_body) BETWEEN 1 AND 32768),
            conversion_model TEXT,
            conversion_schema_version TEXT,
            semantic_matches JSONB NOT NULL DEFAULT '[]'::jsonb,
            resolution TEXT CHECK (resolution IS NULL OR resolution IN ('create', 'revise', 'skip')),
            target_prompt_id TEXT,
            base_version_id TEXT,
            state TEXT NOT NULL CHECK (state IN (
                'parsed', 'converting', 'duplicate_check', 'ready', 'retryable',
                'needs_attention', 'committing', 'committed', 'skipped', 'failed'
            )),
            error_code TEXT,
            attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            item_version INTEGER NOT NULL DEFAULT 1 CHECK (item_version > 0),
            lease_until TIMESTAMPTZ,
            result_prompt_id TEXT,
            result_version_id TEXT,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            UNIQUE (batch_id, ordinal)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_ingestion_item_claim ON ingestion.import_item "
        "(state, lease_until, created_at) WHERE state IN ('parsed', 'retryable')"
    )
    op.execute(
        "CREATE INDEX ix_ingestion_item_batch ON ingestion.import_item (batch_id, ordinal)"
    )

    op.execute(
        """
        CREATE TABLE ingestion.commit_proposal (
            id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL REFERENCES ingestion.import_batch(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            expected_review_version INTEGER NOT NULL,
            item_snapshot JSONB NOT NULL,
            preview JSONB NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'rejected', 'stale')),
            created_at TIMESTAMPTZ NOT NULL,
            decided_at TIMESTAMPTZ,
            CHECK ((status = 'pending') = (decided_at IS NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_ingestion_open_proposal ON ingestion.commit_proposal "
        "(batch_id, actor_id) WHERE status = 'pending'"
    )

    for table in ("import_batch", "import_item", "commit_proposal"):
        enable_tenant_rls("ingestion", table)
        grant_table(
            "ingestion",
            table,
            app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
        )

    reset_role()
    op.execute("GRANT USAGE ON SCHEMA ingestion TO prope_app, prope_report")


def downgrade() -> None:
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS ingestion.commit_proposal CASCADE")
    op.execute("DROP TABLE IF EXISTS ingestion.import_item CASCADE")
    op.execute("DROP TABLE IF EXISTS ingestion.import_batch CASCADE")
    reset_role()
    op.execute("DROP SCHEMA IF EXISTS ingestion CASCADE")
