"""Freeze explicit comparison inputs while the source revision remains editable.

Revision ID: 0057
Revises: 0056
"""

from ddl import assume_migrate_role, reset_role

from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    assume_migrate_role()
    op.execute("""
        ALTER TABLE evaluation.eval_run ADD COLUMN revision_snapshot jsonb,
        ADD CONSTRAINT ck_eval_run_snapshot_object CHECK (
            revision_snapshot IS NULL OR jsonb_typeof(revision_snapshot) = 'object'
        );
    """)
    op.execute("""
        CREATE FUNCTION evaluation.keep_run_snapshot() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            IF OLD.revision_snapshot IS DISTINCT FROM NEW.revision_snapshot THEN
                RAISE EXCEPTION 'evaluation input snapshots are immutable';
            END IF;
            RETURN NEW;
        END $$;
    """)
    op.execute("""
        CREATE TRIGGER keep_run_snapshot BEFORE UPDATE ON evaluation.eval_run
        FOR EACH ROW EXECUTE FUNCTION evaluation.keep_run_snapshot();
    """)
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("DROP TRIGGER keep_run_snapshot ON evaluation.eval_run")
    op.execute("DROP FUNCTION evaluation.keep_run_snapshot()")
    op.execute("""
        ALTER TABLE evaluation.eval_run DROP CONSTRAINT ck_eval_run_snapshot_object,
            DROP COLUMN revision_snapshot;
    """)
    reset_role()
