"""Persistent, content-free execution graphs for background product work.

Revision ID: 0038
Revises: 0037
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0038"
down_revision: str | Sequence[str] | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_RUN = r"""
CREATE TABLE agent.run (
    id                  text        NOT NULL,
    workspace_id        text        NOT NULL,
    requested_by        text        NOT NULL,
    kind                text        NOT NULL,
    plan_basis          text        NOT NULL,
    status              text        NOT NULL,
    prompt_id           text,
    version_id          text,
    source_refs         jsonb       NOT NULL DEFAULT '[]'::jsonb,
    result_actions      jsonb       NOT NULL DEFAULT '[]'::jsonb,
    progress_current    integer,
    progress_total      integer,
    progress_unit       text,
    idempotency_key     text        NOT NULL,
    lease_owner         text,
    lease_until         timestamptz,
    acknowledged_at     timestamptz,
    created_at          timestamptz NOT NULL,
    updated_at          timestamptz NOT NULL,
    started_at          timestamptz,
    finished_at         timestamptz,
    CONSTRAINT pk_agent_run PRIMARY KEY (id),
    CONSTRAINT uq_agent_run_workspace_id_idempotency_key UNIQUE (workspace_id, idempotency_key),
    CONSTRAINT ck_agent_run_id_prefix CHECK (id LIKE 'arn\_%'),
    CONSTRAINT ck_agent_run_kind_values CHECK (kind IN (
        'import', 'evaluation', 'production_analysis', 'improvement'
    )),
    CONSTRAINT ck_agent_run_plan_basis_values CHECK (plan_basis IN (
        'llm', 'explicit_user_action', 'schedule'
    )),
    CONSTRAINT ck_agent_run_status_values CHECK (status IN (
        'queued', 'running', 'waiting_for_user', 'succeeded', 'warning',
        'failed', 'cancelled'
    )),
    CONSTRAINT ck_agent_run_progress_is_whole CHECK (
        (progress_current IS NULL AND progress_total IS NULL AND progress_unit IS NULL)
        OR (progress_current >= 0 AND progress_total > 0
            AND progress_current <= progress_total
            AND progress_unit IS NOT NULL AND length(progress_unit) BETWEEN 1 AND 40)
    ),
    CONSTRAINT ck_agent_run_finished_is_terminal CHECK (
        finished_at IS NULL OR status IN ('succeeded', 'warning', 'failed', 'cancelled')
    ),
    CONSTRAINT ck_agent_run_idempotency_key_is_bounded CHECK (
        length(idempotency_key) BETWEEN 8 AND 200
    )
);
"""

CREATE_NODE = r"""
CREATE TABLE agent.node (
    run_id              text        NOT NULL,
    workspace_id        text        NOT NULL,
    id                  text        NOT NULL,
    sequence            integer     NOT NULL,
    capability          text        NOT NULL,
    kind                text        NOT NULL,
    status              text        NOT NULL,
    idempotency_key     text        NOT NULL,
    evidence_refs       jsonb       NOT NULL DEFAULT '[]'::jsonb,
    progress_current    integer,
    progress_total      integer,
    progress_unit       text,
    started_at          timestamptz,
    finished_at         timestamptz,
    CONSTRAINT pk_agent_node PRIMARY KEY (run_id, id),
    CONSTRAINT fk_agent_node_run FOREIGN KEY (run_id) REFERENCES agent.run (id) ON DELETE CASCADE,
    CONSTRAINT uq_agent_node_workspace_id_idempotency_key UNIQUE (workspace_id, idempotency_key),
    CONSTRAINT ck_agent_node_id_prefix CHECK (id LIKE 'nod\_%'),
    CONSTRAINT ck_agent_node_kind_values CHECK (kind IN (
        'llm', 'retrieval', 'automated_check', 'provider_call', 'human_decision'
    )),
    CONSTRAINT ck_agent_node_status_values CHECK (status IN (
        'pending', 'running', 'waiting_for_user', 'succeeded', 'warning',
        'failed', 'cancelled', 'skipped'
    )),
    CONSTRAINT ck_agent_node_sequence_nonnegative CHECK (sequence >= 0),
    CONSTRAINT ck_agent_node_progress_is_whole CHECK (
        (progress_current IS NULL AND progress_total IS NULL AND progress_unit IS NULL)
        OR (progress_current >= 0 AND progress_total > 0
            AND progress_current <= progress_total
            AND progress_unit IS NOT NULL AND length(progress_unit) BETWEEN 1 AND 40)
    )
);
"""

CREATE_EDGE = """
CREATE TABLE agent.edge (
    run_id              text NOT NULL,
    workspace_id        text NOT NULL,
    source_node_id      text NOT NULL,
    target_node_id      text NOT NULL,
    CONSTRAINT pk_agent_edge PRIMARY KEY (run_id, source_node_id, target_node_id),
    CONSTRAINT fk_agent_edge_run FOREIGN KEY (run_id) REFERENCES agent.run (id) ON DELETE CASCADE,
    CONSTRAINT fk_agent_edge_source FOREIGN KEY (run_id, source_node_id)
        REFERENCES agent.node (run_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_agent_edge_target FOREIGN KEY (run_id, target_node_id)
        REFERENCES agent.node (run_id, id) ON DELETE CASCADE,
    CONSTRAINT ck_agent_edge_not_self CHECK (source_node_id <> target_node_id)
);
"""


def upgrade() -> None:
    op.execute("CREATE SCHEMA agent AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA agent TO prope_app, prope_report")
    assume_migrate_role()
    op.execute(CREATE_RUN)
    op.execute(CREATE_NODE)
    op.execute(CREATE_EDGE)
    op.execute(
        "CREATE INDEX ix_agent_run_workspace_status_updated "
        "ON agent.run (workspace_id, status, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_agent_run_claim "
        "ON agent.run (status, lease_until, created_at) "
        "WHERE status IN ('queued', 'running')"
    )
    enable_tenant_rls("agent", "run")
    enable_tenant_rls("agent", "node")
    enable_tenant_rls("agent", "edge")
    grant_table(
        "agent", "run", app_privileges=["SELECT", "INSERT", "UPDATE"]
    )
    grant_table(
        "agent", "node", app_privileges=["SELECT", "INSERT", "UPDATE"]
    )
    grant_table("agent", "edge", app_privileges=["SELECT", "INSERT"])
    # A chat turn and its pending human action point at the durable graph by
    # value. No cross-schema foreign key: the transcript remains readable if a
    # run is later removed under a different retention policy.
    op.execute("ALTER TABLE chat.message ADD COLUMN run_id text")
    op.execute("ALTER TABLE chat.pending_action ADD COLUMN run_id text")
    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("ALTER TABLE chat.pending_action DROP COLUMN run_id")
    op.execute("ALTER TABLE chat.message DROP COLUMN run_id")
    op.execute("DROP SCHEMA agent CASCADE")
    reset_role()
