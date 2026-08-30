"""Cancel as a first-class act: the history vocabulary learns `eval_run_cancelled`

The eval run cancel endpoint (INT-025's surface, POST /eval-runs/{id}/cancel)
appends a property-history event so the audit trail says *who* stopped a run —
ADR-0038 keeps that vocabulary closed, so a new action is a registry row plus a
restart rather than a string somebody typed. The row mirrors
`eval_run_interrupted` in every column but the name: same target type, no
detail keys, no reason requirement — the actor is the person, which is the
whole point of the event.

Revision ID: 0051
Revises: 0050
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0051"
down_revision: str | Sequence[str] | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INSERT_ACTION = """
    INSERT INTO history.history_action_registry
        (action, target_type, detail_keys, requires_reason, writing_module)
    VALUES ('eval_run_cancelled', 'eval_run', '{}', false, 'evaluation')
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(INSERT_ACTION)
    reset_role()


def downgrade() -> None:
    """Removes the vocabulary row. Refuses nothing: no event of this action can
    exist in a schema whose registry lacks it — the foreign key that makes the
    registry the vocabulary also makes this delete the clean reversal."""
    assume_migrate_role()
    op.execute("DELETE FROM history.history_action_registry WHERE action = 'eval_run_cancelled'")
    reset_role()
