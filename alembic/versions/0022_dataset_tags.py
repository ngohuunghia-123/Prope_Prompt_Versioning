"""User-defined neutral tags for evaluation datasets.

Revision ID: 0022
Revises: 0021
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADD_TAGS = """
ALTER TABLE evaluation.dataset
    ADD COLUMN tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD CONSTRAINT ck_dataset_tags_is_a_list CHECK (jsonb_typeof(tags) = 'array'),
    ADD CONSTRAINT ck_dataset_tags_limit CHECK (jsonb_array_length(tags) <= 10);
"""

BACKFILL_TAGS = """
UPDATE evaluation.dataset
SET tags = jsonb_build_array(
    CASE kind
        WHEN 'golden' THEN 'Golden'
        WHEN 'regression' THEN 'Regression'
        ELSE 'Red Team'
    END
);
"""

DROP_TAGS = "ALTER TABLE evaluation.dataset DROP COLUMN tags;"


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_TAGS)
    op.execute(BACKFILL_TAGS)
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute(DROP_TAGS)
    reset_role()
