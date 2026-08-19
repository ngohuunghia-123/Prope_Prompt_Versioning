"""User-defined neutral tags for evaluation datasets.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADD_TAG_COLUMN = """
ALTER TABLE evaluation.dataset
    ADD COLUMN IF NOT EXISTS tags jsonb NOT NULL DEFAULT '[]'::jsonb;
"""

ADD_TAG_CONSTRAINTS = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'evaluation.dataset'::regclass
          AND conname = 'ck_dataset_tags_is_a_list'
    ) THEN
        ALTER TABLE evaluation.dataset
            ADD CONSTRAINT ck_dataset_tags_is_a_list
            CHECK (jsonb_typeof(tags) = 'array');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'evaluation.dataset'::regclass
          AND conname = 'ck_dataset_tags_limit'
    ) THEN
        ALTER TABLE evaluation.dataset
            ADD CONSTRAINT ck_dataset_tags_limit
            CHECK (jsonb_array_length(tags) <= 10);
    END IF;
END $$;
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
    op.execute(ADD_TAG_COLUMN)
    op.execute(ADD_TAG_CONSTRAINTS)
    op.execute(BACKFILL_TAGS)
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute(DROP_TAGS)
    reset_role()
