from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_APPROVAL = """
CREATE TABLE release.approval (
    id                      text         NOT NULL,
    workspace_id            text         NOT NULL,
    prompt_id               text         NOT NULL,
    version_id              text         NOT NULL,
    decision                text         NOT NULL,
    reviewer_id             text         NOT NULL,
    comment                 text,
    acknowledgement_reason  text,
    evidence_digest         jsonb        NOT NULL DEFAULT '{}'::jsonb,
    self_approved           boolean      NOT NULL DEFAULT false,
    decided_at              timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_approval PRIMARY KEY (id),
    CONSTRAINT ck_approval_id_prefix CHECK (id LIKE 'apr\\_%'),
    CONSTRAINT ck_approval_decision_values
        CHECK (decision IN ('approved', 'changes_requested')),
    CONSTRAINT ck_approval_comment_length CHECK (char_length(comment) <= 2000),
    CONSTRAINT ck_approval_acknowledgement_reason_length
        CHECK (char_length(acknowledgement_reason) <= 500),
    CONSTRAINT ck_approval_changes_requested_carries_a_comment
        CHECK (decision <> 'changes_requested' OR btrim(comment) <> ''),
    CONSTRAINT ck_approval_evidence_digest_is_an_object
        CHECK (jsonb_typeof(evidence_digest) = 'object')
);
"""

CREATE_RELEASE = """
CREATE TABLE release.release (
    id                   text         NOT NULL,
    workspace_id         text         NOT NULL,
    prompt_id            text         NOT NULL,
    version_id           text,
    kind                 text         NOT NULL,
    previous_version_id  text,
    approval_id          text,
    break_glass          boolean      NOT NULL DEFAULT false,
    reason               text,
    released_by          text         NOT NULL,
    released_at          timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_release PRIMARY KEY (id),
    CONSTRAINT ck_release_id_prefix CHECK (id LIKE 'rel\\_%'),
    CONSTRAINT ck_release_kind_values
        CHECK (kind IN ('release', 'restore', 'withdraw')),
    CONSTRAINT ck_release_withdraw_has_no_target
        CHECK ((kind = 'withdraw') = (version_id IS NULL)),
    CONSTRAINT ck_release_withdraw_names_what_it_removed
        CHECK (kind <> 'withdraw' OR previous_version_id IS NOT NULL),
    CONSTRAINT ck_release_approval_absent_only_for_break_glass
        CHECK (approval_id IS NOT NULL OR break_glass OR version_id IS NULL),
    CONSTRAINT ck_release_break_glass_carries_no_approval
        CHECK (NOT break_glass OR approval_id IS NULL),
    CONSTRAINT ck_release_break_glass_is_not_a_withdrawal
        CHECK (NOT break_glass OR kind <> 'withdraw'),
    CONSTRAINT ck_release_reason_length CHECK (char_length(reason) <= 500),
    CONSTRAINT ck_release_mandatory_reason
        CHECK (
            (kind NOT IN ('restore', 'withdraw') AND NOT break_glass)
            OR btrim(reason) <> ''
        ),

    CONSTRAINT fk_release_approval_id
        FOREIGN KEY (approval_id)
        REFERENCES release.approval (id)
);
"""

CREATE_REVIEW_TASK = """
CREATE TABLE release.review_task (
    id                       text         NOT NULL,
    workspace_id             text         NOT NULL,
    prompt_id                text         NOT NULL,
    version_id               text         NOT NULL,
    kind                     text         NOT NULL,
    assigned_role            text         NOT NULL,
    due_at                   timestamptz,
    status                   text         NOT NULL DEFAULT 'open',
    created_from_release_id  text,
    created_at               timestamptz  NOT NULL DEFAULT now(),
    closed_by                text,
    closed_at                timestamptz,
    closed_note              text,

    CONSTRAINT pk_review_task PRIMARY KEY (id),
    CONSTRAINT ck_review_task_id_prefix CHECK (id LIKE 'rvt\\_%'),
    CONSTRAINT ck_review_task_kind_values
        CHECK (kind IN ('review', 'break_glass_followup')),
    CONSTRAINT ck_review_task_status_values
        CHECK (status IN ('open', 'closed', 'superseded')),
    CONSTRAINT ck_review_task_break_glass_followup_is_due
        CHECK (kind <> 'break_glass_followup' OR due_at IS NOT NULL),
    CONSTRAINT ck_review_task_break_glass_followup_names_its_release
        CHECK (kind <> 'break_glass_followup' OR created_from_release_id IS NOT NULL),
    CONSTRAINT ck_review_task_closed_carries_an_actor
        CHECK (status <> 'closed' OR (closed_by IS NOT NULL AND closed_at IS NOT NULL)),
    CONSTRAINT ck_review_task_open_is_not_closed
        CHECK (status = 'closed' OR (closed_by IS NULL AND closed_at IS NULL)),
    CONSTRAINT ck_review_task_closed_note_length
        CHECK (char_length(closed_note) <= 2000),

    CONSTRAINT fk_review_task_created_from_release_id
        FOREIGN KEY (created_from_release_id)
        REFERENCES release.release (id)
);
"""

CREATE_INDEXES = (
    """
    CREATE INDEX ix_approval_workspace_id_version_id
        ON release.approval (workspace_id, version_id, decided_at DESC)
    """,
    """
    CREATE INDEX ix_approval_workspace_id_prompt_id
        ON release.approval (workspace_id, prompt_id, decided_at DESC)
    """,
    """
    CREATE INDEX ix_release_workspace_id_prompt_id
        ON release.release (workspace_id, prompt_id, released_at DESC)
    """,
    """
    CREATE INDEX ix_release_workspace_id_version_id
        ON release.release (workspace_id, version_id)
        WHERE version_id IS NOT NULL
    """,
    """
    CREATE INDEX ix_release_workspace_id_approval_id
        ON release.release (workspace_id, break_glass)
        WHERE approval_id IS NULL AND version_id IS NOT NULL
    """,
    """
    CREATE INDEX ix_review_task_workspace_id_status
        ON release.review_task (workspace_id, status, kind, due_at)
    """,
    """
    CREATE UNIQUE INDEX uq_review_task_one_open_review_per_prompt
        ON release.review_task (workspace_id, prompt_id)
        WHERE status = 'open' AND kind = 'review'
    """,
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA release AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA release TO prope_app, prope_report")

    assume_migrate_role()

    op.execute(CREATE_APPROVAL)
    op.execute(CREATE_RELEASE)
    op.execute(CREATE_REVIEW_TASK)

    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("release", "approval")
    enable_tenant_rls("release", "release")
    enable_tenant_rls("release", "review_task")

    grant_table("release", "approval", app_privileges=["SELECT", "INSERT"])
    grant_table("release", "release", app_privileges=["SELECT", "INSERT"])
    grant_table("release", "review_task", app_privileges=["SELECT", "INSERT", "UPDATE"])

    reset_role()


def downgrade() -> None:
    assume_migrate_role()

    op.execute("DROP TABLE IF EXISTS release.review_task")
    op.execute("DROP TABLE IF EXISTS release.release")
    op.execute("DROP TABLE IF EXISTS release.approval")

    reset_role()

    op.execute("DROP SCHEMA IF EXISTS release CASCADE")
