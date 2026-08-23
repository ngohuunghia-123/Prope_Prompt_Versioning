"""Human annotations for real call metadata.

Revision ID: 0039
Revises: 0038
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0039"
down_revision: str | Sequence[str] | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    assume_migrate_role()
    op.execute(r"""
        CREATE TABLE registry.call_annotation (
            workspace_id text NOT NULL,
            call_id text NOT NULL,
            prompt_id text NOT NULL,
            verdict text NOT NULL,
            categories text[] NOT NULL DEFAULT '{}',
            correction text NOT NULL DEFAULT '',
            note text NOT NULL DEFAULT '',
            annotated_by text NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT pk_registry_call_annotation PRIMARY KEY (workspace_id, call_id),
            CONSTRAINT ck_registry_call_annotation_verdict CHECK (verdict IN ('good', 'issue', 'review')),
            CONSTRAINT ck_registry_call_annotation_categories CHECK (cardinality(categories) <= 10),
            CONSTRAINT ck_registry_call_annotation_text_bounded CHECK (
                char_length(correction) <= 4000 AND char_length(note) <= 4000
            )
        )
    """)
    op.execute("CREATE INDEX ix_registry_call_annotation_prompt ON registry.call_annotation (workspace_id, prompt_id, updated_at DESC)")
    enable_tenant_rls("registry", "call_annotation")
    grant_table("registry", "call_annotation", app_privileges=["SELECT", "INSERT", "UPDATE"])
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("DROP TABLE registry.call_annotation")
    reset_role()
