"""Create the `chat` schema: conversation, message, pending_action.

Revision ID: 0015
Revises: 0014 (search index latest/released roles)
Create Date: 2026-08-15

Tables owned by the chat-orchestrator module.

**No DELETE for `prope_app`, on any of the three.** The same privilege-level
posture the history schema takes, for a narrower but sharper reason: the
`pending_action` row is where a person's approval of a write is recorded, and the
`message` row beside it is the reasoning that approval was given on. A product
feature that could erase either would be a product feature that can erase the
evidence for a release. "Clear this conversation" is therefore an `UPDATE` to a
status somebody has to design, not a `DELETE` that already works.

**One `FOR ALL` tenant policy per table**, through `enable_tenant_rls`, so the
`WITH CHECK` half is written out rather than inherited — ADR-0040's argument: a
row whose `workspace_id` was stamped by its caller is where this module's
realistic cross-tenant leak would live.
"""

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

# revision identifiers
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

#: Read and write, never erase. See the module docstring.
APP_PRIVILEGES = ["SELECT", "INSERT", "UPDATE"]


def upgrade() -> None:
    # The bootstrap connection creates the schema because the deliberately
    # constrained migration role has no database-level CREATE privilege.
    # Explicit authorization still makes every object below migrate-owned,
    # which is what ADR-0035's owner bypass rests on.
    op.execute("CREATE SCHEMA chat AUTHORIZATION prope_migrate")
    assume_migrate_role()

    op.execute(
        """
        CREATE TABLE chat.conversation (
            id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            title_code TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            message_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (id)
        )
        """
    )
    # The list query is "my threads, newest first", so the index carries the
    # ordering column rather than leaving a sort on top of a filtered scan.
    op.execute(
        "CREATE INDEX ix_chat_conversation_actor "
        "ON chat.conversation (workspace_id, actor_id, updated_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE chat.message (
            id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'agent')),
            body TEXT NOT NULL,
            intent TEXT,
            trace JSONB NOT NULL DEFAULT '[]'::jsonb,
            citations JSONB NOT NULL DEFAULT '[]'::jsonb,
            directives JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id),
            CONSTRAINT fk_message_conversation
                FOREIGN KEY (conversation_id) REFERENCES chat.conversation (id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_chat_message_thread ON chat.message (conversation_id, created_at)"
    )

    op.execute(
        """
        CREATE TABLE chat.pending_action (
            id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            tool TEXT NOT NULL,
            summary TEXT NOT NULL,
            preview JSONB NOT NULL DEFAULT '{}'::jsonb,
            arguments JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'rejected')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            decided_at TIMESTAMPTZ,
            result_prompt_id TEXT,
            result_version_id TEXT,
            PRIMARY KEY (id),
            CONSTRAINT fk_pending_action_conversation
                FOREIGN KEY (conversation_id) REFERENCES chat.conversation (id),
            -- A decision has a time and an undecided row has none. Written as a
            -- constraint rather than trusted to the one handler that sets both,
            -- because "approved by whom, when" is the column this table exists
            -- for and a NULL there is an audit hole rather than a tidy default.
            CONSTRAINT ck_pending_action_decided_at
                CHECK ((status = 'pending') = (decided_at IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_chat_pending_action_open "
        "ON chat.pending_action (conversation_id) WHERE status = 'pending'"
    )

    for table in ("conversation", "message", "pending_action"):
        enable_tenant_rls("chat", table)
        grant_table("chat", table, app_privileges=APP_PRIVILEGES)

    reset_role()
    op.execute("GRANT USAGE ON SCHEMA chat TO prope_app, prope_report")


def downgrade() -> None:
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS chat.pending_action CASCADE")
    op.execute("DROP TABLE IF EXISTS chat.message CASCADE")
    op.execute("DROP TABLE IF EXISTS chat.conversation CASCADE")
    reset_role()
    op.execute("DROP SCHEMA IF EXISTS chat CASCADE")
