"""Add controlled observability content access.

Revision ID: 0028
Revises: 0027
"""

from collections.abc import Sequence

from alembic import op
from ddl import assume_migrate_role, reset_role

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    assume_migrate_role()
    op.execute(
        "ALTER TABLE ledger.workspace_retention "
        "ADD COLUMN observability_content_access_enabled boolean NOT NULL DEFAULT false"
    )
    op.execute(
        """
        INSERT INTO history.history_action_registry (
            action, target_type, detail_keys, requires_reason, writing_module
        ) VALUES (
            'observability_content_viewed', 'property', ARRAY[]::text[], false, 'prompt-registry'
        )
        """
    )
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute(
        "DELETE FROM history.history_action_registry "
        "WHERE action = 'observability_content_viewed'"
    )
    op.execute(
        "ALTER TABLE ledger.workspace_retention "
        "DROP COLUMN IF EXISTS observability_content_access_enabled"
    )
    reset_role()
