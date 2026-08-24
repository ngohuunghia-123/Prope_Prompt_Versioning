"""A chat-approved model-name change records why it happened.

Revision ID: 0045
Revises: 0044
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0045"
down_revision: str | Sequence[str] | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: A-021 made the model name immutable because renaming it silently breaks
#: callers. The chat assistant now offers a rename/move as a *proposal* a
#: person explicitly approves, which is the governed path A-021 anticipated at
#: ``revisit_when``. The event vocabulary widens with it: without this row the
#: append refuses the one event that explains why a prompt's identity moved,
#: and the activity feed would show the effect without the cause.
INSERT_MODEL_NAME_CHANGED_ACTION = """
INSERT INTO history.history_action_registry
    (action, target_type, detail_keys, requires_reason, writing_module)
VALUES (
    'model_name_changed',
    'property',
    ARRAY['from', 'to'],
    false,
    'prompt-registry'
)
"""

DELETE_MODEL_NAME_CHANGED_ACTION = """
DELETE FROM history.history_action_registry WHERE action = 'model_name_changed'
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(INSERT_MODEL_NAME_CHANGED_ACTION)
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute(DELETE_MODEL_NAME_CHANGED_ACTION)
    reset_role()
