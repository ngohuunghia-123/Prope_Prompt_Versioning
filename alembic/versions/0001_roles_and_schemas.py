"""roles and schemas

Revision ID: 0001
Revises:
Create Date: 2026-08-10

The first revision in the project's one linear hand-written chain (D-04).

REQUIRES A SUPERUSER CONNECTION (flagged assumption A9). ``CREATE ROLE
prope_report LOGIN BYPASSRLS`` cannot be issued by a non-superuser. In the
testcontainers rig the default user *is* superuser, so this passes locally and
would fail on a real deploy where a DBA issued a non-superuser
``prope_migrate``. Named here rather than assumed: either the deploy's
migration connection is a superuser for this one attribute, or the attribute
becomes a documented out-of-band bootstrap step.

No passwords are baked into any role. ADR-0032 puts them in one ``.env`` on the
host, 0600 and git-ignored, set out of band (D-05). The test rig issues its own
``ALTER ROLE ... WITH PASSWORD`` after ``upgrade head`` for the same reason.

``CREATE ROLE`` is transactional in PostgreSQL (unlike ``CREATE DATABASE``), so
no autocommit block is needed and the revision keeps its all-or-nothing
property.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_ROLES = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prope_migrate') THEN
    CREATE ROLE prope_migrate LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prope_app') THEN
    CREATE ROLE prope_app LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prope_report') THEN
    CREATE ROLE prope_report LOGIN BYPASSRLS;
  END IF;
END $$;
"""


def upgrade() -> None:
    """Create the three roles and the ledger schema."""
    # Idempotent: roles are cluster-level, so a second database in the same
    # cluster must not fail on them already existing (D-05).
    op.execute(CREATE_ROLES)

    # ADR-0027 — one schema per module, owned by the migration role. The
    # AUTHORIZATION clause is what makes prope_migrate the owner of everything
    # created inside it, which is what ADR-0035's owner bypass rests on.
    op.execute("CREATE SCHEMA ledger AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA ledger TO prope_app, prope_report")

    # Belt and braces: PostgreSQL 15+ already revokes CREATE on public from
    # PUBLIC, but the ledger schema's deny-by-default posture should not depend
    # on a server-version default.
    op.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")


def downgrade() -> None:
    """Drop the ledger schema and the three roles."""
    op.execute("DROP SCHEMA IF EXISTS ledger CASCADE")
    op.execute("DROP ROLE IF EXISTS prope_app")
    op.execute("DROP ROLE IF EXISTS prope_report")
    op.execute("DROP ROLE IF EXISTS prope_migrate")
