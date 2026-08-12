"""the history schema, its two tables, and the closed action vocabulary

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-11

The schema, both tables, four indexes, the vocabulary key, the tenant policy,
the grant matrix and the 31-row seed.

**Deviation, D-53.** The lock file and ADR-0024 spell ``seq`` as ``bigserial``;
this ships ``GENERATED ALWAYS AS IDENTITY``, which refuses a caller-supplied
value where a default would accept it silently. Behavioural, not spelling — see
``docs/brainstorm/open_questions/OQ-131.md``.

**Deviation, D-50, no OQ owed.** The literal ``REVOKE UPDATE, DELETE`` the lock
names is not issued: ``prope_app`` never holds either, so it would be a no-op
that reads in a diff as protection. Byte-identical end state.

**Two absences, asserted rather than assumed; delete neither sentence without
the test that names it.** The ``details`` allow-list and ``requires_reason`` are
refused only in Python, ADR-0023 having rejected a trigger here by name
(``test_history_validation_has_no_database_backstop.py``). And ``OVERRIDING
SYSTEM VALUE`` bypasses ``GENERATED ALWAYS`` with no privilege, leaving the next
engine-assigned ``seq`` *lower* and the read order silently wrong
(``test_history_seq_cannot_be_supplied.py``, ``test_no_overriding_system_
value.py``).
"""

from collections.abc import Sequence

# WHY the bare name: `alembic.ddl` resolves to the installed package's own
# dialect-DDL submodule. `alembic.ini`'s prepend_sys_path puts this directory first.
from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_HISTORY_ACTION_REGISTRY = """
CREATE TABLE history.history_action_registry (
    action           text     NOT NULL,
    target_type      text     NOT NULL,

    detail_keys      text[]   NOT NULL,
    requires_reason  boolean  NOT NULL,
    writing_module   text     NOT NULL,

    CONSTRAINT pk_history_action_registry PRIMARY KEY (action),

    -- WHY: not a redundant duplicate of the primary key. A REFERENCES clause
    -- must name a unique constraint over exactly the referenced columns.
    CONSTRAINT uq_history_action_registry_action UNIQUE (action, target_type),

    CONSTRAINT ck_history_action_registry_writing_module_values
        CHECK (writing_module IN (
            'prompt-registry', 'release-control', 'evaluation',
            'provider-access', 'access-control'
        ))
);
"""

# D-56: no workspace_id, and the absence is the decision — a tenant-scoped
# registry returns zero rows to INT-008's no-tenant consumer, so AC-6 would
# compare two empty sets forever. GLOBAL_TABLES carries the written reason.

CREATE_HISTORY_EVENT = """
CREATE TABLE history.history_event (
    -- D-53 / OQ-131. CACHE 1 is the default, written out anyway: above one,
    -- values may be assigned out of order across sessions.
    seq              bigint       GENERATED ALWAYS AS IDENTITY (CACHE 1) NOT NULL,

    id               text         NOT NULL,

    workspace_id     text         NOT NULL,
    actor_type       text         NOT NULL,
    actor_id         text,
    action           text         NOT NULL,
    target_type      text         NOT NULL,
    target_id        text         NOT NULL,
    scope_prompt_id  text,
    reason           text,

    -- WHY jsonb where 0003's request_body is text: that column keeps malformed
    -- provider bodies on purpose. A-124's allow-list is over KEYS only.
    details          jsonb        NOT NULL DEFAULT '{}'::jsonb,

    -- D-54: no `written_at` beside this; `seq` carries every ordering claim.
    occurred_at      timestamptz  NOT NULL,

    CONSTRAINT pk_history_event PRIMARY KEY (id),

    -- WHY, not the fifth index D-55 refuses: the sequence alone guarantees
    -- distinctness only until somebody restarts it, and the rig does (D-48).
    CONSTRAINT uq_history_event_seq UNIQUE (seq),

    -- Never a native enum (Pitfall 4).
    CONSTRAINT ck_history_event_actor_type_values
        CHECK (actor_type IN ('user', 'system')),

    CONSTRAINT ck_history_event_actor_id_present_unless_system
        CHECK (actor_id IS NOT NULL OR actor_type = 'system'),

    -- ADR-0053: characters, not bytes — a byte cap is ~170 characters of
    -- Vietnamese, the MVP's only interface language.
    CONSTRAINT ck_history_event_reason_length
        CHECK (reason IS NULL OR char_length(reason) <= 500),

    -- D-57. No ON DELETE/ON UPDATE: naming a behaviour for an impossible case
    -- invites someone to make it possible (0003:216-221).
    CONSTRAINT fk_history_event_action
        FOREIGN KEY (action, target_type)
        REFERENCES history.history_action_registry (action, target_type)
);
"""

# No CHECK on target_type: the composite key above closes the column.

# D-55 fixed the number at four; all four ship with the table, not the reader.
CREATE_INDEXES = (
    """
    CREATE INDEX ix_history_event_workspace_id_scope_prompt_id_seq
        ON history.history_event (workspace_id, scope_prompt_id, seq DESC)
    """,
    """
    CREATE INDEX ix_history_event_workspace_id_target_type_target_id_seq
        ON history.history_event (workspace_id, target_type, target_id, seq DESC)
    """,
    """
    CREATE INDEX ix_history_event_workspace_id_actor_id_seq
        ON history.history_event (workspace_id, actor_id, seq DESC)
    """,
    """
    CREATE INDEX ix_history_event_workspace_id_action_seq
        ON history.history_event (workspace_id, action, seq)
    """,
)

# D-59: a migration, not a startup task — D-57's key means the registry must be
# non-empty before the first event. The 31 rows are the union of five lock
# files' `outputs`; `target_type` and the 28 empty `detail_keys` are derived,
# and OQ-029 carries both.
SEED_ACTION_REGISTRY = """
INSERT INTO history.history_action_registry
    (action, target_type, detail_keys, requires_reason, writing_module)
VALUES
    -- prompt-registry, 5. OQ-028: three of these break A-120's naming rule and
    -- are seeded as the lock files spell them, because AC-6 is an equality.
    ('property_created',              'property',        '{}', false, 'prompt-registry'),
    ('revision_created',              'revision',        '{}', false, 'prompt-registry'),
    ('owner_changed',                 'property',        '{}', false, 'prompt-registry'),
    ('access_level_changed',          'property',        '{}', false, 'prompt-registry'),
    ('retired',                       'property',        '{}', false, 'prompt-registry'),

    -- release-control, 8.
    ('revision_submitted',            'revision',        '{}', false, 'release-control'),
    ('revision_approved',             'revision',        '{}', false, 'release-control'),
    ('revision_changes_requested',    'revision',        '{}', true,  'release-control'),
    ('revision_released',             'revision',
        '{version_id,previous_version_id,break_glass}',        false, 'release-control'),
    ('revision_restored',             'revision',        '{}', false, 'release-control'),
    ('revision_break_glass_released', 'revision',        '{}', true,  'release-control'),
    ('release_withdrawn',             'release',         '{}', true,  'release-control'),
    ('review_task_closed',            'review_task',     '{}', false, 'release-control'),

    -- evaluation, 4.
    ('eval_suite_updated',            'eval_suite',      '{}', false, 'evaluation'),
    ('eval_run_started',              'eval_run',        '{}', false, 'evaluation'),
    ('eval_run_completed',            'eval_run',        '{}', false, 'evaluation'),
    ('eval_run_interrupted',          'eval_run',        '{}', false, 'evaluation'),

    -- provider-access, 4.
    ('provider_configured',           'provider_config', '{}', false, 'provider-access'),
    ('provider_updated',              'provider_config', '{}', false, 'provider-access'),
    ('provider_disabled',             'provider_config', '{}', false, 'provider-access'),
    ('credential_rotated',            'provider_config', '{}', false, 'provider-access'),

    -- access-control, 10.
    ('workspace_created',             'workspace',       '{}', false, 'access-control'),
    ('member_added',                  'member',          '{}', false, 'access-control'),
    ('member_removed',                'member',          '{}', false, 'access-control'),
    ('role_assigned',                 'role',
        '{role,grantee_user_id}',                              false, 'access-control'),
    ('role_revoked',                  'role',            '{}', false, 'access-control'),
    ('access_granted',                'prompt_grant',    '{}', false, 'access-control'),
    ('access_revoked',                'prompt_grant',    '{}', false, 'access-control'),
    ('api_key_created',               'api_key',         '{}', false, 'access-control'),
    ('api_key_revoked',               'api_key',         '{}', false, 'access-control'),
    ('user_tombstoned',               'user',            '{}', false, 'access-control');
"""


def upgrade() -> None:
    # WHY before assume_migrate_role(): prope_migrate may not hold CREATE ON
    # DATABASE, and AUTHORIZATION is what ADR-0035's owner bypass rests on.
    op.execute("CREATE SCHEMA history AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA history TO prope_app, prope_report")

    assume_migrate_role()

    # Registry first: the composite key points at it.
    op.execute(CREATE_HISTORY_ACTION_REGISTRY)
    op.execute(SEED_ACTION_REGISTRY)
    op.execute(CREATE_HISTORY_EVENT)

    for statement in CREATE_INDEXES:
        op.execute(statement)

    # T-04-03. Same revision as the table: the window between is a table
    # prope_app can read across tenants.
    enable_tenant_rls("history", "history_event")

    # PH-02 in its entirety: no UPDATE, no DELETE, here or later (ADR-0025).
    # SELECT is required, not generous — the policy predicate references
    # workspace_id. report_select keeps its True default so ADR-0037's Success
    # SQL does not run as the one role that can DELETE a row.
    grant_table("history", "history_event", app_privileges=["SELECT", "INSERT"])

    # D-51: SELECT only — the single writer being the migration is what makes
    # ADR-0038's un-invalidated cache safe.
    grant_table("history", "history_action_registry", app_privileges=["SELECT"])

    reset_role()


def downgrade() -> None:
    # Reverse dependency order.
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS history.history_event")
    op.execute("DROP TABLE IF EXISTS history.history_action_registry")
    op.execute("DROP SCHEMA IF EXISTS history CASCADE")
    reset_role()
