"""Index the latest revision and the released one, over whole-prompt vectors.

Three changes to ``search.prompt_search_index``, and they are one decision.

**A prompt gets two rows, not one.** ``role`` is ``latest`` or ``released`` and
``uq_prompt_search_index_prompt_role`` allows one of each — so the corpus holds
what somebody is working on *and* what production is serving, and never a third
thing. The old ``uq_prompt_search_index_prompt_id`` said one row per prompt, and
under it indexing a draft meant overwriting the released prompt's vector: the
duplicate check would have started answering about text no consumer had ever
been served.

**The vector covers the whole prompt, so the column is renamed.**
``purpose_embedding`` held an embedding of ``prompt.purpose`` alone, which is why
comparing a pasted body against this corpus behaved so poorly — a one-line
description and a two-thousand-word instruction are not near each other in any
embedding space, however similar the prompts are. ``content_embedding`` holds
``title + purpose + body``. The rename is not cosmetic: a column still called
``purpose_embedding`` holding whole-prompt vectors is the kind of name that
survives long enough for somebody to write a query trusting it.

**Existing rows are deleted rather than migrated.** There is no way to turn a
purpose vector into a content vector without calling the provider again, and a
corpus mixing the two ranks nonsense — the cosine distance between them is not
meaningful. Deleting makes every prompt *unindexed*, which the product already
models honestly (the import screen renders it as "nothing indexed resembles
this"), and re-indexing is a button. Keeping them would have been the silent
option, not the safe one.

Revision ID: 0014
Revises: 0013
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Every stored vector embeds a different text than the new one will. See the
    # docstring: mixing the two spaces produces rankings nobody can interpret.
    op.execute("DELETE FROM search.prompt_search_index")
    op.execute("DELETE FROM search.embedding_cache")

    op.execute(
        "ALTER TABLE search.prompt_search_index "
        "RENAME COLUMN purpose_embedding TO content_embedding"
    )
    op.execute(
        "ALTER TABLE search.prompt_search_index "
        "ADD COLUMN role text NOT NULL DEFAULT 'released'"
    )
    op.execute(
        "ALTER TABLE search.prompt_search_index "
        "ADD CONSTRAINT ck_prompt_search_index_role "
        "CHECK (role IN ('latest', 'released'))"
    )
    op.execute(
        "ALTER TABLE search.prompt_search_index "
        "DROP CONSTRAINT IF EXISTS uq_prompt_search_index_prompt_id"
    )
    op.execute("DROP INDEX IF EXISTS search.uq_prompt_search_index_prompt_id")
    op.execute(
        "CREATE UNIQUE INDEX uq_prompt_search_index_prompt_role "
        "ON search.prompt_search_index (prompt_id, role)"
    )
    # The default exists only so the ADD COLUMN could run against rows that no
    # longer exist. Dropping it makes every future writer state which of the two
    # rows it is writing, which is the whole point of the column.
    op.execute("ALTER TABLE search.prompt_search_index ALTER COLUMN role DROP DEFAULT")


def downgrade() -> None:
    # Back to one row per prompt: keep the released one where a prompt has both,
    # because that is what the old single row meant.
    op.execute(
        """
        DELETE FROM search.prompt_search_index psi
        WHERE psi.role = 'latest'
          AND EXISTS (
              SELECT 1 FROM search.prompt_search_index other
              WHERE other.prompt_id = psi.prompt_id AND other.role = 'released'
          )
        """
    )
    op.execute("DROP INDEX IF EXISTS search.uq_prompt_search_index_prompt_role")
    op.execute(
        "ALTER TABLE search.prompt_search_index "
        "DROP CONSTRAINT IF EXISTS ck_prompt_search_index_role"
    )
    op.execute("ALTER TABLE search.prompt_search_index DROP COLUMN role")
    op.execute(
        "CREATE UNIQUE INDEX uq_prompt_search_index_prompt_id "
        "ON search.prompt_search_index (prompt_id)"
    )
    op.execute(
        "ALTER TABLE search.prompt_search_index "
        "RENAME COLUMN content_embedding TO purpose_embedding"
    )
