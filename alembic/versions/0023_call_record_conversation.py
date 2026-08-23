"""Caller-supplied conversation correlation on `ledger.call_record`.

Two nullable columns and one partial index, so that the calls one end-user
conversation made can be read back as a chain instead of as fifty unrelated rows
scattered through the largest table in the system.

**These are the first columns on this table whose meaning is defined outside
Prope.** Every other column is a fact Prope established — a price it resolved, a
revision it bound, an outcome it observed. `conversation_id` is whatever the
customer's application decided to call one conversation, and Prope neither
generates it, nor checks it for uniqueness, nor attaches any meaning to it beyond
*these calls belong together*. The gate on the way in (`gateway.schemas` and
`call_ledger.envelope`) is therefore about shape, not semantics: an ASCII class
and a length, because the value becomes a URL path segment and an index key.

**Both are values, not foreign keys, and `parent_call_id` especially.** The
obvious `REFERENCES ledger.call_record(call_id)` is wrong here for the reason
`property_history.target_id` is a bare value: retention deletes old rows
(ADR-0018's 30-day window applies to bodies, but a workspace may set its own
window for records), and a foreign key would either block that delete or cascade
it into records the workspace still needs. An unmatched parent is not corruption
— it is a chain whose head has aged out, and it renders as a root. That is the
honest picture.

**No CHECK that a parent implies a conversation, despite the application
enforcing exactly that.** `CallRecordDraft.__post_init__` refuses the pair and
the drain dead-letters it, which is where a publisher bug should surface — loudly,
one message at a time, with the envelope preserved. A CHECK here would instead
abort the whole batch the writer is committing, taking a hundred innocent records
down with one malformed one, on the path A-087 keeps off the response.

Revision ID: 0023
Revises: 0022
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_call_record_workspace_id_conversation_id_created_at"

ADD_COLUMNS = """
ALTER TABLE ledger.call_record
    ADD COLUMN conversation_id text,
    ADD COLUMN parent_call_id  text
"""

#: **Partial on `conversation_id IS NOT NULL`, because almost no row has one.**
#: Every record written before this migration, every eval dispatch, every
#: playground trial and every gateway call from a caller that has not adopted the
#: field carries NULL. Indexing those would grow the index by the whole table to
#: serve none of it — the same argument `0011_call_record_prompt_index.py` makes,
#: on the same table, for the same reason.
#:
#: **Leads with `workspace_id`, as every declared index in Prope does.** The
#: tenant policy is what makes a missing filter return zero rows (ADR-0035), and
#: an index that did not lead with the column the policy filters on would be an
#: index the policy's own predicate cannot use.
#:
#: `created_at, call_id` complete the key rather than decorating it: the graph
#: read orders by them as a row value so that two calls sharing a millisecond —
#: which, for a fan-out to parallel sub-agents, is the *expected* case rather than
#: the unlucky one — have a total order rather than an arbitrary one.
CREATE_INDEX = f"""
CREATE INDEX {INDEX_NAME}
    ON ledger.call_record (workspace_id, conversation_id, created_at, call_id)
    WHERE conversation_id IS NOT NULL
"""


def upgrade() -> None:
    op.execute(ADD_COLUMNS)
    op.execute(CREATE_INDEX)


def downgrade() -> None:
    """Drops the index first, then the columns.

    Order matters only for legibility — `DROP COLUMN` would take the index with
    it — but a downgrade that names both is a downgrade whose diff shows what it
    undoes.
    """
    op.execute(f"DROP INDEX IF EXISTS ledger.{INDEX_NAME}")
    op.execute(
        "ALTER TABLE ledger.call_record "
        "DROP COLUMN IF EXISTS parent_call_id, "
        "DROP COLUMN IF EXISTS conversation_id"
    )
