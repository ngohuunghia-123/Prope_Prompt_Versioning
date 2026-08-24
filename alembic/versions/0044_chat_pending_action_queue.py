"""A multi-write request keeps its plan after the first confirmation card.

Revision ID: 0044
Revises: 0043
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0044"
down_revision: str | Sequence[str] | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: One write per turn means "đổi tên prompt rồi bỏ vào thư mục mới" loses its
#: second half the moment the first card appears. This column holds the planned
#: steps that follow the proposed one, so the next confirmation picks the task
#: back up instead of the person asking again. Empty by default: a single-write
#: proposal carries no queue and reads exactly as before.
ADD_QUEUE_COLUMN = """
ALTER TABLE chat.pending_action
    ADD COLUMN remaining_steps jsonb NOT NULL DEFAULT '[]'::jsonb
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_QUEUE_COLUMN)
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("ALTER TABLE chat.pending_action DROP COLUMN remaining_steps")
    reset_role()
