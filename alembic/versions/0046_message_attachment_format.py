"""A sent message remembers it carried an attachment.

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

#: The body itself never enters the transcript — only the fact that one rode
#: along, so a reloaded thread can still show what the person sent. Same value
#: domain as `chat.pending_action.resume_attachment_format` (migration 0043's
#: CHECK), enforced by the API layer's Literal type rather than a constraint.
ADD_ATTACHMENT_FORMAT = """
ALTER TABLE chat.message
    ADD COLUMN IF NOT EXISTS attachment_format TEXT
"""

DROP_ATTACHMENT_FORMAT = """
ALTER TABLE chat.message
    DROP COLUMN IF EXISTS attachment_format
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_ATTACHMENT_FORMAT)
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute(DROP_ATTACHMENT_FORMAT)
    reset_role()
