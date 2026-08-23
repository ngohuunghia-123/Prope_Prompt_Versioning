"""Allow the application role to manage revision classification tags.

Revision ID: 0037
Revises: 0036
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0037"
down_revision: str | Sequence[str] | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    assume_migrate_role()
    op.execute("GRANT UPDATE (tags) ON registry.revision TO prope_app")
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("REVOKE UPDATE (tags) ON registry.revision FROM prope_app")
    reset_role()
