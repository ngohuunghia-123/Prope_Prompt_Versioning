"""evaluation.case_result.error_detail — the provider's own error message, verbatim.

Revision ID: 0056
Revises: 0055
Create Date: 2026-09-01

**Why the column exists.** An errored case used to carry only the coarse class
(``invalid_request``, ``rate_limited``, …) — the fact the gateway needs to
decide what to do next, but not the fact a person needs to decide what to fix.
When a provider refuses a run, the sentence it wrote back (the rate-limit
window, the rejected parameter, the missing model) is the diagnostic; hiding it
behind a class name turns a readable failure into a guess. The executor now
persists the provider's ``error.message`` verbatim beside the class.

**Why verbatim text and not a second enum.** The message is the provider's own
wording and every provider words it differently; classifying it again would
rebuild the same lossy funnel this column exists to bypass. It is nullable
because not every error path has a provider body behind it — a timeout, a
composition failure, an assertion that never dispatched.

**The CHECK is one-sided.** ``error_detail`` may exist only on an ``error`` row,
but an ``error`` row may exist without one — the existing
``ck_case_result_error_carries_a_code`` keeps owning the bidirectional half.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0056"
down_revision: str | Sequence[str] | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADD_ERROR_DETAIL = """
ALTER TABLE evaluation.case_result
    ADD COLUMN error_detail text,
    ADD CONSTRAINT ck_case_result_error_detail_needs_an_error
        CHECK (error_detail IS NULL OR outcome = 'error');
"""

DROP_ERROR_DETAIL = """
ALTER TABLE evaluation.case_result
    DROP CONSTRAINT IF EXISTS ck_case_result_error_detail_needs_an_error,
    DROP COLUMN error_detail;
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_ERROR_DETAIL)
    reset_role()


def downgrade() -> None:
    """Drops the column. Old rows lose the provider's wording and keep the
    class — the pre-0056 behaviour, degraded but not corrupted."""
    assume_migrate_role()
    op.execute(DROP_ERROR_DETAIL)
    reset_role()
