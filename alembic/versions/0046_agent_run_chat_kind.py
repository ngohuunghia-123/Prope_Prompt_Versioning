"""Track chat turns as first-class agent runs.

Revision ID: 0046
Revises: 0045
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0046"
down_revision: str | Sequence[str] | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    assume_migrate_role()
    op.execute("ALTER TABLE agent.run DROP CONSTRAINT ck_agent_run_kind_values")
    op.execute(
        "ALTER TABLE agent.run ADD CONSTRAINT ck_agent_run_kind_values "
        "CHECK (kind IN ('chat', 'import', 'evaluation', 'production_analysis', 'improvement'))"
    )
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("ALTER TABLE agent.run DROP CONSTRAINT ck_agent_run_kind_values")
    op.execute(
        "ALTER TABLE agent.run ADD CONSTRAINT ck_agent_run_kind_values "
        "CHECK (kind IN ('import', 'evaluation', 'production_analysis', 'improvement'))"
    )
    reset_role()
