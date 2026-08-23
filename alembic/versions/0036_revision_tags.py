"""Store revision tags and expose them in the version history.

Revision ID: 0036
Revises: 0035
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0036"
down_revision: str | Sequence[str] | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    assume_migrate_role()
    op.execute(
        """
        ALTER TABLE registry.revision
        ADD COLUMN tags text[] NOT NULL DEFAULT '{}'
        """
    )
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("ALTER TABLE registry.revision DROP COLUMN IF EXISTS tags")
    reset_role()
