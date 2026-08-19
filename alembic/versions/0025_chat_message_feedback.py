"""Add actor-scoped, idempotent feedback for assistant messages.

Revision ID: 0025
Revises: 0024
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    assume_migrate_role()
    op.execute(
        """
        CREATE TABLE chat.message_feedback (
            message_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            rating TEXT NOT NULL CHECK (rating IN ('helpful', 'not_helpful')),
            reason TEXT CHECK (
                reason IS NULL OR reason IN (
                    'incorrect', 'unsupported_source', 'misunderstood', 'other'
                )
            ),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (message_id, actor_id),
            CONSTRAINT fk_message_feedback_message
                FOREIGN KEY (message_id) REFERENCES chat.message (id)
        )
        """
    )
    enable_tenant_rls("chat", "message_feedback")
    grant_table(
        "chat",
        "message_feedback",
        app_privileges=["SELECT", "INSERT", "UPDATE"],
    )
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS chat.message_feedback CASCADE")
    reset_role()
