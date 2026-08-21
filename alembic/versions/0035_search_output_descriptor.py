"""search.prompt_search_index gains output_descriptor — the declared output contract, cached

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-20

**One column, because a comparison must not cost one extraction per pair.**

The duplicate check's stage 2b compares what two prompts *say* they emit —
modality, keys, enum values, whether preamble is forbidden, cardinality,
language, length — as a normalized descriptor rather than as two blocks of prose,
because comparing prose blocks by embedding is the whole-document mistake one
level down. Extracting that descriptor needs a model call.

**The descriptor is a property of one revision, so it is extracted per revision
and never per pair.** That is a correctness rule before it is a cost one: an
extractor shown two `<output_format>` blocks at once is drawn toward finding them
alike, the same anchoring problem as judging N pairs holistically. Extracting
per revision also means an import comparing one incoming body against five
candidates costs **one** call rather than six, and the five were already paid for
at index time by a job that was running an agent anyway.

**Why the index row and not a registry column.** The descriptor is arguably a
property of a revision that prompt-readiness and prompt-improvement would both
like to read, which would argue for prompt-registry owning it (OQ-e in the draft
design). It lands here because it is filled by *this* module's indexing job, on
*this* module's schedule, and moving it later is a migration; putting it in
another module's table now would be an edge into that module for a value nothing
there reads yet.

**Nullable, and no backfill.** A NULL means *never extracted*, which the
comparison reports as "not established" — deliberately distinct from a descriptor
that exists and says `unspecified`, which is the prompt itself being silent and
is a finding about the prompt. Backfilling would mean calling the app agent once
per indexed row inside a migration, and a migration that spends money on an
external service is a migration nobody can safely re-run. Rows fill in as prompts
are re-indexed, and until then the comparison says so.

No RLS change: the column inherits the table's existing policies, which are what
bound every read of this row already.
"""

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE search.prompt_search_index "
        "ADD COLUMN IF NOT EXISTS output_descriptor jsonb"
    )
    op.execute(
        "COMMENT ON COLUMN search.prompt_search_index.output_descriptor IS "
        "'Normalized declared output contract for this revision. "
        "NULL means never extracted, which is not the same as the prompt "
        "declaring nothing.'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE search.prompt_search_index DROP COLUMN IF EXISTS output_descriptor"
    )
