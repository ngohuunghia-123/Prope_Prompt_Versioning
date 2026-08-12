"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

D-04: revisions in this project are hand-written. Autogenerate may draft a
table diff, but its output is never committed unreviewed — it cannot see RLS
policies, grants or triggers, and the first autogenerate after a policy lands
proposes dropping what it cannot see.

Every revision from 0002 onward opens with ``assume_migrate_role()`` so the
objects it creates are owned by ``prope_migrate``, which is what ADR-0035's
owner bypass depends on.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
