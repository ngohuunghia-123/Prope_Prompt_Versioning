"""ledger.call_record.source gains 'playground' — the third and last internal caller

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-16

**A third source, because there is now a third thing that spends provider money.**
``gateway`` is a consumer's call against a released revision; ``eval`` is a run
measuring one. The playground is neither: a person sitting in the SPA, talking to
a *draft* revision through a session cookie, before anything has been approved.
Recording it as ``gateway`` would corrupt the "100% of gateway calls record a
version ID" metric's denominator with traffic no consumer made, and recording it
as ``eval`` would put rows in ``get_run_totals`` that belong to no run. So it gets
its own value, and A-098's one-table-one-price-path property is preserved: the
cost of a playground turn lands in the same workspace spend total as everything
else, which is the only reason a person can answer "what did this workspace
spend" with one query.

**``ck_call_record_playground_calls_are_internal`` is the shape of the decision,
written where it cannot be forgotten.** It says four things at once, and each is
load-bearing:

* ``version_id IS NOT NULL`` — a trial is always *of a specific revision*. This is
  the exact counterpart of ``ck_call_record_gateway_calls_carry_version_id``, and
  it exists for the same reason: traceability back to the revision that served is
  the product's core promise, and a promise enforced by application code is a
  promise until somebody writes a second insert.
* ``consumer_key_id IS NULL`` — **no key authenticated this call, and the row must
  not imply one did.** The playground is session-authenticated. A record naming a
  key that was never presented would be a false entry in the one table an auditor
  reads to answer "who called this prompt", and the temptation to point it at the
  workspace's fallback key for a tidier ``GROUP BY`` is precisely what this
  constraint refuses. Internal usage is identified by ``source``, not by borrowing
  somebody's credential.
* ``run_id IS NULL AND case_id IS NULL`` — a trial belongs to no run, so it can
  never be swept into a run's totals.

**Playground rows may carry a ``call_body``, and eval rows still may not.** A-055
withholds bodies from eval because a suite's inputs are already stored in the
suite; a trial's turns exist nowhere else, and the person who typed them is the
person the workspace's retention window is set by. ``ledger.call_body`` has no
source predicate of its own, so this needs no change there — it is recorded here
because the asymmetry looks like an oversight until you know why.

**The downgrade will refuse while any playground row exists, and that is
correct.** T-006 gives the application no DELETE on ``call_record`` and ADR-0054
makes "history rows are never deleted" a privilege rather than a habit, so a
downgrade that quietly discarded them would be the one code path in Prope that
breaks the rule the rest of the schema enforces. Reverting after the feature has
been used is a data decision for a person to make, out loud, not a side effect of
running a migration backwards.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: One statement, so the widened value set and the constraint that governs it
#: land in the same transaction. No RLS call and no grant: both are properties of
#: the table, set by 0002, and a constraint change does not disturb them.
ADD_PLAYGROUND_SOURCE = """
ALTER TABLE ledger.call_record
    DROP CONSTRAINT ck_call_record_source_values,
    ADD CONSTRAINT ck_call_record_source_values
        CHECK (source IN ('gateway', 'eval', 'playground')),
    ADD CONSTRAINT ck_call_record_playground_calls_are_internal
        CHECK (
            source <> 'playground'
            OR (
                version_id IS NOT NULL
                AND consumer_key_id IS NULL
                AND run_id IS NULL
                AND case_id IS NULL
            )
        );
"""

DROP_PLAYGROUND_SOURCE = """
ALTER TABLE ledger.call_record
    DROP CONSTRAINT IF EXISTS ck_call_record_playground_calls_are_internal,
    DROP CONSTRAINT ck_call_record_source_values,
    ADD CONSTRAINT ck_call_record_source_values
        CHECK (source IN ('gateway', 'eval'));
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_PLAYGROUND_SOURCE)
    reset_role()


def downgrade() -> None:
    """Refuses while a playground row exists. See this module's docstring."""
    assume_migrate_role()
    op.execute(DROP_PLAYGROUND_SOURCE)
    reset_role()
