"""ledger.call_record.source gains 'probe' — the fifth, and the one that is not an eval run

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-20

**A fifth source, because there is now a fifth thing that spends provider money.**
A probe dispatches the profile-selected `builtin:` red-team cases against a
candidate revision, on the workspace's own credential, through provider-access
like every other call. The tokens are real and the bill is real, so a record is
written — call-ledger's rule is that everything metered is recorded, and a
convenience feature that spent money invisibly would be the one hole in it.

**Why not `eval`.** This is the migration where ADR-0067 §3 becomes a
constraint rather than a paragraph. Reusing `source = 'eval'` is the cheap build:
write an `eval_run`, reuse the runner, get the per-case rows for free. It breaks
`evaluation`'s one non-negotiable — *a model does not decide what a prompt is
measured against* — in the exact place it is load-bearing, because a probe's case
set is chosen by a declared profile and augmented by a drafter, and a suite's is
chosen by a person. A probe measures readiness; a suite measures a release.

**And it would corrupt the cost delta.** `run_id` is what release-control's
delta reads. A probe carrying one would put a convenience feature's bill inside
the number that compares what two revisions cost to *serve*, making a revision
look more expensive because somebody pressed a button. The constraint below is
what makes that impossible rather than merely discouraged: a `probe` record names
its prompt and revision — the spend IS attributable, which is the point of
recording it — and names no run, no case, and no consumer key.

`pinned` and `fallback` are both false and asserted so. A probe dispatches the
revision's binding verbatim with no fallback requested or accepted (A-164): a
silent failover would measure a model the released revision will not use, which
is the one thing a probe must not do.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0032"
down_revision: str | Sequence[str] | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: One statement, so the widened value set and the constraint that governs it land
#: in the same transaction. Revision 0027's shape, for 0027's reasons. No RLS call
#: and no grant: both are properties of the table, set by 0002, and a constraint
#: change does not disturb them.
ADD_PROBE_SOURCE = """
ALTER TABLE ledger.call_record
    DROP CONSTRAINT ck_call_record_source_values,
    ADD CONSTRAINT ck_call_record_source_values
        CHECK (source IN ('gateway', 'eval', 'playground', 'observed', 'probe')),
    ADD CONSTRAINT ck_call_record_probe_calls_name_no_run
        CHECK (
            source <> 'probe'
            OR (
                prompt_id IS NOT NULL
                AND version_id IS NOT NULL
                AND run_id IS NULL
                AND case_id IS NULL
                AND consumer_key_id IS NULL
                AND pinned = false
                AND fallback = false
            )
        );
"""

DROP_PROBE_SOURCE = """
ALTER TABLE ledger.call_record
    DROP CONSTRAINT IF EXISTS ck_call_record_probe_calls_name_no_run,
    DROP CONSTRAINT ck_call_record_source_values,
    ADD CONSTRAINT ck_call_record_source_values
        CHECK (source IN ('gateway', 'eval', 'playground', 'observed'));
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_PROBE_SOURCE)
    reset_role()


def downgrade() -> None:
    """Narrows the value set back to four.

    **Fails where any probe record exists, and that is the correct behaviour** —
    revisions 0020 and 0026 take the same position for the same reason. The
    application holds no DELETE on ``ledger.call_record`` at the privilege level;
    it is the accountability record, and reverting a feature must not quietly
    remove rows that say money was spent. The remedy is to leave the widened
    CHECK in place, not to grant a DELETE.
    """
    assume_migrate_role()
    op.execute(DROP_PROBE_SOURCE)
    reset_role()
