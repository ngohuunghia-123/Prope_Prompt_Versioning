"""ledger.call_record.source gains 'observed' — the fourth, and the mirror of the third

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-18

**A fourth source, because there is now a fourth thing that spends provider
money.** ``gateway`` is a consumer's call against a released revision, ``eval`` is
a run measuring one, ``playground`` is a person trying a draft. ``observed`` is a
call the gateway **forwarded** because it could not resolve the model name at all
(ADR-0059): no prompt, no revision, no approval — somebody else's prompt, running
through Prope, recorded so it can be discovered.

**The argument is revision 0020's, at the other end of the same metric.**
``playground`` needed its own value because filing it as ``gateway`` would corrupt
the DENOMINATOR of *"100% of gateway calls record a version ID"* with traffic no
consumer made. ``observed`` needs one because filing it as ``gateway`` would
corrupt the NUMERATOR with traffic no revision served.

Relaxing ``ck_call_record_gateway_calls_carry_version_id`` was the cheap answer
and the wrong one. ``call-ledger.lock.yml`` calls that constraint *"a database
constraint here, not a hope"*; widening it to admit the rows it was written to
exclude would delete the metric rather than extend it.

**``ck_call_record_observed_calls_name_no_revision`` is the shape of the
decision.** Each clause is load-bearing and each is the mirror of
``ck_call_record_playground_calls_are_internal``:

* ``version_id / prompt_id / revision_number IS NULL`` — no revision served this,
  and the row must not imply one did. The playground constraint asserts the
  opposite for the opposite reason, and between them the two make ``version_id``
  mean exactly one thing on every row of the largest table in the system.
* ``consumer_key_id IS NOT NULL`` — a real key authenticated this call.
  Observation is never an internal caller, which is precisely where it differs
  from the playground, and a row that let the key be NULL would let internal
  traffic hide in the discovery inventory.
* ``run_id / case_id IS NULL`` — it belongs to no run and can never be swept into
  one's totals.
* ``pinned = false AND fallback = false`` — both are properties of a revision, and
  there is none. A fallback answer in particular is impossible here by
  construction (ADR-0059), so a true value would be a lie no code path can produce
  and this is what keeps it that way.

**A-098's one-table-one-price-path property is the point.** An observed call lands
in the same workspace spend total as everything else, priced by the machinery that
already exists — which is what makes *"you are spending this much on prompts Prope
does not manage"* a number the product can put on a screen in the first week.

**The observed BODY is not here and never will be.** ADR-0018 gives
``ledger.call_body`` no reader; the discovery inventory is entirely a reader. The
bodies live in ``observation.observation`` (revision 0027), in another schema,
owned by a module that may check a permission. ADR-0060 is the argument and
ADR-0018 is untouched by it.

**The downgrade refuses while any observed row exists**, for revision 0020's
reason exactly: T-006 gives the application no DELETE on ``call_record``, and a
downgrade that quietly discarded accountability rows would be the one code path in
Prope that breaks the rule the rest of the schema enforces.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: One statement, so the widened value set and the constraint that governs it land
#: in the same transaction. No RLS call and no grant: both are properties of the
#: table, set by 0002, and a constraint change does not disturb them.
ADD_OBSERVED_SOURCE = """
ALTER TABLE ledger.call_record
    DROP CONSTRAINT ck_call_record_source_values,
    ADD CONSTRAINT ck_call_record_source_values
        CHECK (source IN ('gateway', 'eval', 'playground', 'observed')),
    ADD CONSTRAINT ck_call_record_observed_calls_name_no_revision
        CHECK (
            source <> 'observed'
            OR (
                prompt_id IS NULL
                AND version_id IS NULL
                AND revision_number IS NULL
                AND run_id IS NULL
                AND case_id IS NULL
                AND consumer_key_id IS NOT NULL
                AND pinned = false
                AND fallback = false
            )
        );
"""

DROP_OBSERVED_SOURCE = """
ALTER TABLE ledger.call_record
    DROP CONSTRAINT IF EXISTS ck_call_record_observed_calls_name_no_revision,
    DROP CONSTRAINT ck_call_record_source_values,
    ADD CONSTRAINT ck_call_record_source_values
        CHECK (source IN ('gateway', 'eval', 'playground'));
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_OBSERVED_SOURCE)
    reset_role()


def downgrade() -> None:
    """Refuses while an observed row exists. See this module's docstring."""
    assume_migrate_role()
    op.execute(DROP_OBSERVED_SOURCE)
    reset_role()
