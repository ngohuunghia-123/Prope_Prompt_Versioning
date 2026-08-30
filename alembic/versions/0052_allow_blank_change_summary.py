"""The change summary stops being a gate: blank is allowed

Editing a prompt now goes through an editable draft that can be promoted
without a written summary, and the SPA no longer demands four characters
before saving. The API schema (prompt_registry.schemas.ChangeSummary) was
relaxed to match, which alone would only turn the 422 into a 500 —
``ck_revision_change_summary_not_blank`` would refuse the empty string at
insert. Dropping that CHECK finishes the relaxation. The length cap
(``ck_revision_change_summary_length``, <= 200) stays: optional is not the
same as unbounded.

Revision ID: 0052
Revises: 0051
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0052"
down_revision: str | Sequence[str] | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
    ALTER TABLE registry.revision
        DROP CONSTRAINT ck_revision_change_summary_not_blank
"""

DOWNGRADE_SQL = """
    ALTER TABLE registry.revision
        ADD CONSTRAINT ck_revision_change_summary_not_blank
        CHECK (btrim(change_summary) <> '')
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(UPGRADE_SQL)
    reset_role()


def downgrade() -> None:
    """Restores the not-blank CHECK. Deliberately fails if blank summaries were
    written while the constraint was absent: reverting the product rule cannot
    invent a summary for those rows, so they have to be given one first."""
    assume_migrate_role()
    op.execute(DOWNGRADE_SQL)
    reset_role()
