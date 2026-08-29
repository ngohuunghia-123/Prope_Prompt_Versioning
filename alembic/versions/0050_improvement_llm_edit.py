"""The authored edit, its rails report and its rationale — ADR-0070

ADR-0068 §3 built the remedy catalogue so the round-trip guarantee was
assertable by construction: a transform that replaces one whole block cannot
drop a ``{{variable}}`` from another. ADR-0070 lets the App Agent author
candidate bodies for **eval-evidence findings**, and the guarantee moves from
*the transform cannot break it* to *the rails checked it did not* — a shift in
mechanism, not in strength, and this revision is where the schema catches up.

Three changes, each narrow:

1. ``remedy_family`` learns ``llm_edit``. The CHECK is widened, not replaced —
   the three drift families keep their meanings, and
   ``ck_improvement_proposal_an_edit_is_gated`` is untouched: an ``llm_edit``
   proposal still carries a body, a family, a gate run and a delta, exactly as
   a catalogue one does. What the authored edit adds is its own provenance:

2. ``draft_rationale`` and ``rails_report``. The rationale is the model's own
   bounded claim about its edit — stored for the audit record and disclosed as
   a collapsed, machine-attributed note (ADR-0070 §5), never as the card. The
   rails report is what the candidate survived: which checks ran, which fired
   on which attempt. ``ck_improvement_proposal_an_llm_edit_carries_its_draft``
   makes the pair mandatory for ``llm_edit`` and forbidden for everything
   else, mirroring the gate CHECK's shape: a column that only one remedy
   family may populate is a column every other row must prove is NULL.

3. Nothing else. The finding table needs no change — there is no CHECK on
   ``detector_id``; the catalogue is a Python-side vocabulary and the eval
   detectors ride the existing dedupe index unchanged. No new history action:
   a disposition is a disposition whatever authored the body, and
   ``gate_failed`` stays deliberately absent (ADR-0068's consequence, reaffirmed).

Revision ID: 0050
Revises: 0049
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0050"
down_revision: str | Sequence[str] | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Widened in place. The constraint name keeps its meaning — "the families this
#: table may carry" — and a name that survives a widening with its meaning
#: intact is worth more than a second constraint saying "...and also that one".
WIDEN_FAMILY = """
    ALTER TABLE improvement.proposal
        DROP CONSTRAINT ck_improvement_proposal_remedy_family_values
"""

FAMILY_VALUES = """
    ALTER TABLE improvement.proposal
        ADD CONSTRAINT ck_improvement_proposal_remedy_family_values
        CHECK (remedy_family IS NULL OR remedy_family IN (
            'tighten_refusal_block', 'add_length_rule', 'add_brevity_clause',
            'llm_edit'
        ))
"""

ADD_COLUMNS = """
    ALTER TABLE improvement.proposal
        ADD COLUMN draft_rationale text,
        ADD COLUMN rails_report   jsonb
"""

#: The provenance pair is whole or absent, and only for the family that has it.
#: A catalogue proposal carrying a rationale would be a rationale nobody wrote;
#: an ``llm_edit`` without its rails report would be an edit claiming to have
#: been checked with no record of the checking. Both are refused by the engine,
#: the way ``ck_improvement_proposal_an_edit_is_gated`` refuses an ungated edit.
LLM_EDIT_CARRIES_ITS_DRAFT = """
    ALTER TABLE improvement.proposal
        ADD CONSTRAINT ck_improvement_proposal_an_llm_edit_carries_its_draft
        CHECK (
            (remedy_family = 'llm_edit') =
            (draft_rationale IS NOT NULL AND rails_report IS NOT NULL)
        )
"""

#: 500, the bound the output model and `domain.RATIONALE_CHARACTERS` already
#: carry. In the database because a bound enforced only in the model is a bound
#: a different writer forgets.
RATIONALE_BOUNDED = """
    ALTER TABLE improvement.proposal
        ADD CONSTRAINT ck_improvement_proposal_rationale_is_bounded
        CHECK (draft_rationale IS NULL OR char_length(draft_rationale) <= 500)
"""


def upgrade() -> None:
    # The proposal table already carries the app role's grants from revision
    # 0033, and new columns inherit them; the migrate role is still assumed for
    # the DDL, as every revision since 0012 does.
    assume_migrate_role()

    op.execute(WIDEN_FAMILY)
    op.execute(FAMILY_VALUES)
    op.execute(ADD_COLUMNS)
    op.execute(LLM_EDIT_CARRIES_ITS_DRAFT)
    op.execute(RATIONALE_BOUNDED)

    reset_role()


def downgrade() -> None:
    """Drops the columns and the constraint, and re-narrows the family set.

    Refuses nothing: no row can exist with ``remedy_family = 'llm_edit'`` in a
    schema this reverted to, and the columns it drops are this feature's own.
    """
    assume_migrate_role()

    op.execute(
        "ALTER TABLE improvement.proposal "
        "DROP CONSTRAINT IF EXISTS ck_improvement_proposal_rationale_is_bounded, "
        "DROP CONSTRAINT IF EXISTS ck_improvement_proposal_an_llm_edit_carries_its_draft, "
        "DROP COLUMN IF EXISTS rails_report, "
        "DROP COLUMN IF EXISTS draft_rationale"
    )
    op.execute(WIDEN_FAMILY)
    op.execute(
        "ALTER TABLE improvement.proposal "
        "ADD CONSTRAINT ck_improvement_proposal_remedy_family_values "
        "CHECK (remedy_family IS NULL OR remedy_family IN ("
        "'tighten_refusal_block', 'add_length_rule', 'add_brevity_clause'))"
    )

    reset_role()
