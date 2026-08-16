"""ledger.price_table.minimum_charge_per_request — a floor under one call's cost

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-15

**A per-request floor, carried by the rate card rather than beside it.** Some
gateways bill a minimum per request regardless of tokens: a call that prices to
0.0004 still costs 0.01. Until now Prope could not express that, and a workspace
whose provider charges one would have had every figure in the ledger understate
the invoice.

**It lives on the price row, not on the provider config.** That is the whole
decision and it follows from ADR-0019: a stored cost has to stay explicable
years later under the row that produced it. A provider-level setting would be
mutable, and editing it would silently re-explain every cost already recorded
against that provider. Here it is effective-dated with the two per-1k prices,
superseded the same way (a new row with a later ``effective_from``), and
append-only by the same privilege (T-006) — so ``price_row_id`` on a call record
still identifies every input to that call's arithmetic.

**``DEFAULT 0`` is "no floor", which is exactly today's behaviour.** Every row
written before this migration means what it always meant, and
``compute_cost``'s ``max(cost, floor)`` is the identity when the floor is zero.
The default stays on the column afterwards rather than being dropped: the
insert-only privilege set means a row is never revisited, so an omitted floor has
to be a legible zero at write time rather than a NULL nobody can add a NOT NULL
to later.

**The free-tier refusal loosens as a consequence.** ``POST /api/v1/prices``
refused ``(0, 0)`` because ``compute_cost`` would return exactly zero and
``ck_call_record_cost_is_never_zero`` would then discard the whole batch
(CR-01). With a positive floor that chain no longer holds — every call the row
prices costs the floor — so the refusal now needs all three figures at zero. The
CHECK here is only non-negativity, for the same reason
``ck_price_table_prices_are_non_negative`` is: the poisoning condition is a
property of three columns together and the API is where it is named.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: ``numeric(20,10)`` because every money column in ``ledger`` is, and
#: ``tests/architecture/test_schema_invariants.py`` asserts exactly that over the
#: named set — a floor stored at a different scale would be the one figure in the
#: schema that could not be compared against the cost it is a floor on.
#:
#: No RLS call and no grant here: both are properties of the *table*, already set
#: by 0003, and a new column inherits them.
ADD_MINIMUM_CHARGE = """
ALTER TABLE ledger.price_table
    ADD COLUMN minimum_charge_per_request numeric(20,10) NOT NULL DEFAULT 0,
    ADD CONSTRAINT ck_price_table_minimum_charge_is_non_negative
        CHECK (minimum_charge_per_request >= 0);
"""

DROP_MINIMUM_CHARGE = """
ALTER TABLE ledger.price_table
    DROP CONSTRAINT IF EXISTS ck_price_table_minimum_charge_is_non_negative,
    DROP COLUMN IF EXISTS minimum_charge_per_request;
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_MINIMUM_CHARGE)
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute(DROP_MINIMUM_CHARGE)
    reset_role()
