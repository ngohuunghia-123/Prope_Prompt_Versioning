"""One tool may stage more than one kind of consent card; the label follows.

Revision ID: 0048
Revises: 0047
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0048"
down_revision: str | Sequence[str] | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: `delete_folder` stages a plain deletion and — behind a first approval — the
#: negotiated move-to-backup-then-delete. Both cards carried the tool name as
#: their only label, so the card that moves every prompt into backup announced
#: itself as "delete folder". This column holds an optional machine code the
#: client translates in place of the tool name (ADR-0053); null keeps the old
#: behaviour for every card that needs no refinement. Executor dispatch is and
#: stays keyed by `tool`.
ADD_VARIANT_COLUMN = """
ALTER TABLE chat.pending_action
    ADD COLUMN variant varchar(64)
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_VARIANT_COLUMN)
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("ALTER TABLE chat.pending_action DROP COLUMN variant")
    reset_role()
