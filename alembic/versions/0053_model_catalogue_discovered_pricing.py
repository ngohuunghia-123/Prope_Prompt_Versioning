"""Model catalogue carries the prices the provider listed

OpenRouter publishes a per-token ``pricing`` object on every model entry of
``GET /models``. Storing it beside the catalogue entry means the provider
screen can show — and, with one click, adopt — the vendor's own rate card
instead of typing it by hand. The ledger stays the only price WRITER
(INT-016's forbidden edge stays absent): these columns are discovery
metadata, the same status the ``source`` column already carries, and
adopting a figure is still an explicit append to ``ledger.price_table``.

Per-token dollars times 1000 lands on the ledger's per-1k unit, so the
adoption path is the same multiplication the manual form does for per-1M.

Revision ID: 0053
Revises: 0052
Create Date: 2026-08-30
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0053"
down_revision: str | Sequence[str] | None = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
    ALTER TABLE provider.model_catalogue
        ADD COLUMN input_price_per_1k  NUMERIC,
        ADD COLUMN output_price_per_1k NUMERIC
"""

DOWNGRADE_SQL = """
    ALTER TABLE provider.model_catalogue
        DROP COLUMN input_price_per_1k,
        DROP COLUMN output_price_per_1k
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(UPGRADE_SQL)
    reset_role()


def downgrade() -> None:
    """Drops only discovery metadata: no ledger row ever referenced these
    columns, so nothing adopted is lost by reverting."""
    assume_migrate_role()
    op.execute(DOWNGRADE_SQL)
    reset_role()
