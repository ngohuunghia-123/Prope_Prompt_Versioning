"""A confirmed proposal carries its import source forward.

Revision ID: 0043
Revises: 0039
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0043"
down_revision: str | Sequence[str] | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: One write per turn means an import that needs a folder finishes across two
#: confirmations. These columns hold the body the first proposal was made from,
#: so the follow-up turn resumes the task instead of asking for it again.
ADD_RESUME_COLUMNS = """
ALTER TABLE chat.pending_action
    ADD COLUMN resume_attachment text,
    ADD COLUMN resume_attachment_format text,
    ADD CONSTRAINT ck_pending_action_resume_format CHECK (
        resume_attachment IS NULL
        OR (resume_attachment_format IS NOT NULL AND resume_attachment_format IN (
            'txt', 'md', 'markdown', 'json', 'yaml'
        ))
    )
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_RESUME_COLUMNS)
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("ALTER TABLE chat.pending_action DROP COLUMN resume_attachment_format")
    op.execute("ALTER TABLE chat.pending_action DROP COLUMN resume_attachment")
    reset_role()
