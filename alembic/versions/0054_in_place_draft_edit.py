"""The in-place edit of a never-published Draft version

A prompt nothing of which is in use has no published line to protect, and
iterating on its Draft versions must not mint a new revision per save — a
just-imported prompt would drown in r2..rN before anybody ever saw r1. The
command (``update_draft_revision``) overwrites the Draft row itself, guarded
by ``status = 'Draft'`` in the UPDATE's WHERE clause.

The privilege layer was the last thing still saying "no": ``prope_app`` could
UPDATE ``revision`` only on ``status`` and ``tags`` (the release flow and the
rail's label editor), and ``revision_route_entry`` had no DELETE at all. This
revision widens exactly those two, column by column: content columns become
overwritable, while ``revision_number``, ``author_id`` and ``created_at``
stay untouched — a Draft can be rewritten, never renumbered or re-authored.

Revision ID: 0054
Revises: 0053
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0054"
down_revision: str | Sequence[str] | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANT_REVISION_COLUMNS = """
    GRANT UPDATE (
        body,
        fallback_answer,
        change_summary,
        parameters,
        provider_config_id,
        upstream_model,
        route_combo_id,
        route_combo_name
    ) ON registry.revision TO prope_app
"""

GRANT_ROUTE_DELETE = """
    GRANT DELETE ON registry.revision_route_entry TO prope_app
"""

REVOKE_ROUTE_DELETE = """
    REVOKE DELETE ON registry.revision_route_entry FROM prope_app
"""

REVOKE_REVISION_COLUMNS = """
    REVOKE UPDATE (
        body,
        fallback_answer,
        change_summary,
        parameters,
        provider_config_id,
        upstream_model,
        route_combo_id,
        route_combo_name
    ) ON registry.revision FROM prope_app
"""

RESTATE_STATUS_TAGS = """
    GRANT UPDATE (status, tags) ON registry.revision TO prope_app
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(GRANT_REVISION_COLUMNS)
    op.execute(GRANT_ROUTE_DELETE)
    reset_role()


def downgrade() -> None:
    """Back to the append-only privilege shape: content columns lose their
    UPDATE, route entries lose their DELETE. The status/tags grant is restated
    because REVOKE UPDATE (cols) does not touch the separately granted ones —
    this makes the downgrade's end state explicit rather than assumed."""
    assume_migrate_role()
    op.execute(REVOKE_ROUTE_DELETE)
    op.execute(REVOKE_REVISION_COLUMNS)
    op.execute(RESTATE_STATUS_TAGS)
    reset_role()
