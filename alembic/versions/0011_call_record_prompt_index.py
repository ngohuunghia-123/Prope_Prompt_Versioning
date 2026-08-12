"""An index for the per-prompt call-record read.

`GET /api/v1/prompts/{prompt_id}/call-records` filters `ledger.call_record` by
prompt and orders it newest-first. Phase 1's `ix_call_record_workspace_id_created_at`
serves the workspace-wide ordering and nothing else, so without this the read
walks a workspace's whole history in time order and discards most of it — on the
table `0002_call_record.py`'s own comment calls *"the largest table in the
system"*.

**Partial on `prompt_id IS NOT NULL`, because most rows have no prompt.** A call
that arrived through the gateway names one; an evaluation run's calls carry a
`run_id` and a NULL `prompt_id`, and so does anything the resolver refused before
it bound a revision. Indexing those NULLs would grow the index by every row it can
never serve.

**Leads with `workspace_id`, as every declared index in Prope does.** The tenant
policy is what makes a missing filter return zero rows (ADR-0035); an index that
did not lead with the column the policy filters on would be an index the policy's
own predicate cannot use.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_call_record_workspace_id_prompt_id_created_at"

CREATE_INDEX = f"""
CREATE INDEX {INDEX_NAME}
    ON ledger.call_record (workspace_id, prompt_id, created_at DESC, call_id DESC)
    WHERE prompt_id IS NOT NULL
"""


def upgrade() -> None:
    """Add the per-prompt, newest-first index.

    `call_id DESC` is part of the key rather than decoration: the read's keyset
    cursor compares `(created_at, call_id)` as a row value, because two records
    written in the same millisecond would otherwise page unstably — one of them
    appearing twice and the other never.
    """
    op.execute(CREATE_INDEX)


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS ledger.{INDEX_NAME}")
