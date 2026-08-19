"""The namespace becomes the unit of authorisation — ADR-0061

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-18

Four changes, one shape. Every one of them exists because ``registry.folder`` is
**flat** — ``(workspace_id, slug)`` with no parent column — so a namespace is one
string with no ancestors and ``access_control`` never has to read a row it is
forbidden to read (ADR-0020). A nested folder tree would need ancestor
resolution, and none of this would be expressible.

1. ``access.namespace_grant`` — ``prompt_grant``'s twin one scope up.
2. ``access.api_key.scope_namespaces`` — beside ``scope_model_names``, union not
   replacement, both default ``'{}'`` so A-081's default-deny is untouched.
3. ``access.api_key.observe_provider_config_id`` / ``observe_namespace`` — the
   ADR-0059 switch and the folder its observations land in, NULL together.
4. ``namespace.grant`` joins the closed action vocabulary, which becomes 26.

``access.lookup_api_key`` is DROPped and recreated rather than replaced, because
``CREATE OR REPLACE FUNCTION`` cannot change a return type. **The sanctioned
``SECURITY DEFINER`` set stays at four** — this is the same function with three
more columns, and ``tests/security/test_definer_functions_are_the_sanctioned_set``
should go on finding exactly four.

**No foreign key from ``namespace_grant`` to ``registry.folder``, deliberately**
(A-157). Migration 0016 refuses the equivalent FK from ``prompt_property`` and its
reasons carry one table further out: a label must not become load-bearing, and
``list_folders`` returns the union of declared rows and namespaces OBSERVED on
prompts, so most namespaces in a live workspace have no row at all. Under this
revision an FK would be worse than redundant — deleting a folder would become a
permission change, and a cascade would be how a workspace silently loses access
to a thousand prompts at once.

The FK that IS here runs to ``access.workspace_member``, exactly as
``prompt_grant``'s does, because that one runs the same way the dependency
already does and is therefore free (A-096's rule). ADR-0054's tombstone deletes
rows here for the same reason it deletes them there.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: ``ck_namespace_grant_namespace_shape`` is byte-identical to
#: ``ck_prompt_property_namespace_shape`` and ``ck_folder_slug_shape``. It has to
#: be: a grant on a namespace no prompt could ever carry is a grant on nothing,
#: and the shape is the only thing keeping ``namespace`` a namespace rather than
#: free text on a table nothing else validates.
CREATE_NAMESPACE_GRANT = """
CREATE TABLE access.namespace_grant (
    workspace_id     text         NOT NULL,
    namespace        text         NOT NULL,
    grantee_user_id  text         NOT NULL,
    level            text         NOT NULL,
    granted_by       text         NOT NULL,
    granted_at       timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_namespace_grant PRIMARY KEY (workspace_id, namespace, grantee_user_id),

    CONSTRAINT ck_namespace_grant_namespace_shape
        CHECK (namespace ~ '^[a-z0-9][a-z0-9._-]{0,62}$'),

    -- A-112's ceiling, unchanged at the wider scope. No grant confers approve,
    -- release, withdraw or break-glass, and letting a FOLDER grant do so would
    -- dissolve NFR-01's separation a thousand prompts at a time rather than one.
    CONSTRAINT ck_namespace_grant_level_values CHECK (level IN ('viewer', 'editor')),

    CONSTRAINT fk_namespace_grant_workspace_member
        FOREIGN KEY (workspace_id, grantee_user_id)
        REFERENCES access.workspace_member (workspace_id, user_id)
);
"""

#: Leads with ``workspace_id`` like every declared index in Prope. The lookup
#: `permissions.py` issues is by ``(namespace, grantee_user_id)`` under a policy
#: that has already fixed the workspace, and the visible-filter read is by
#: ``grantee_user_id`` alone — so one index over the triple serves the first and
#: a second over the grantee serves the second.
CREATE_INDEXES = (
    """
    CREATE INDEX ix_namespace_grant_workspace_id_grantee
        ON access.namespace_grant (workspace_id, grantee_user_id)
    """,
)

#: Both arrays default empty, which is the whole of A-081's default-deny surviving
#: A-158's union: ``= ANY('{}')`` is false for every input, so a key with neither
#: array set resolves nothing without a branch anybody could forget to write.
ADD_KEY_COLUMNS = """
ALTER TABLE access.api_key
    ADD COLUMN scope_namespaces text[] NOT NULL DEFAULT '{}',
    ADD COLUMN observe_provider_config_id text,
    ADD COLUMN observe_namespace text,

    -- ADR-0059's switch is a PAIR, and half of one is an observation with
    -- nowhere to land. Enforced here rather than in the handler because the
    -- handler is not what a second insert path would go through.
    ADD CONSTRAINT ck_api_key_observe_is_all_or_nothing
        CHECK (num_nonnulls(observe_provider_config_id, observe_namespace) <> 1),

    ADD CONSTRAINT ck_api_key_observe_namespace_shape
        CHECK (observe_namespace IS NULL
               OR observe_namespace ~ '^[a-z0-9][a-z0-9._-]{0,62}$');
"""

DROP_KEY_COLUMNS = """
ALTER TABLE access.api_key
    DROP CONSTRAINT IF EXISTS ck_api_key_observe_namespace_shape,
    DROP CONSTRAINT IF EXISTS ck_api_key_observe_is_all_or_nothing,
    DROP COLUMN IF EXISTS observe_namespace,
    DROP COLUMN IF EXISTS observe_provider_config_id,
    DROP COLUMN IF EXISTS scope_namespaces;
"""

#: Twenty-six. A-160 keeps `namespace.grant` distinct from `prompt.grant` because
#: `prompt.grant` sits in `OWNER_ACTIONS` — reusing it would let any prompt owner
#: hand over a folder holding a thousand prompts, which is the escalation OQ-079
#: spent its length declining to create by accident.
WIDEN_ACTION_VOCABULARY = """
ALTER TABLE access.role_permission
    DROP CONSTRAINT ck_role_permission_action_values,
    ADD CONSTRAINT ck_role_permission_action_values CHECK (action IN (
        'prompt.read', 'prompt.create', 'prompt.edit', 'prompt.retire',
        'prompt.transfer_owner', 'prompt.grant', 'revision.create',
        'suite.read', 'suite.edit', 'run.start', 'run.read',
        'revision.submit', 'revision.approve',
        'release.create', 'release.break_glass', 'release.withdraw',
        'provider.configure', 'provider.rotate_credential', 'provider.disable',
        'catalogue.read',
        'workspace.manage_members', 'workspace.manage_keys',
        'price.manage', 'spend_ceiling.manage',
        'user.tombstone',
        'namespace.grant'
    ));
"""

#: A TUPLE, not one string with two statements in it. asyncpg prepares every
#: statement it is given, and a prepared statement holds exactly one command —
#: `op.execute` with two would raise `cannot insert multiple commands into a
#: prepared statement` at migrate time. The multi-statement bodies elsewhere in
#: this chain get away with it by being one `DO $$ ... $$` block or one
#: `CREATE FUNCTION`, which are single commands whatever is inside them.
#:
#: The DELETE must run FIRST: `role_permission` holds a seeded `namespace.grant`
#: row, and narrowing the CHECK while that row exists fails the constraint.
NARROW_ACTION_VOCABULARY = (
    "DELETE FROM access.role_permission WHERE action = 'namespace.grant'",
    """
ALTER TABLE access.role_permission
    DROP CONSTRAINT ck_role_permission_action_values,
    ADD CONSTRAINT ck_role_permission_action_values CHECK (action IN (
        'prompt.read', 'prompt.create', 'prompt.edit', 'prompt.retire',
        'prompt.transfer_owner', 'prompt.grant', 'revision.create',
        'suite.read', 'suite.edit', 'run.start', 'run.read',
        'revision.submit', 'revision.approve',
        'release.create', 'release.break_glass', 'release.withdraw',
        'provider.configure', 'provider.rotate_credential', 'provider.disable',
        'catalogue.read',
        'workspace.manage_members', 'workspace.manage_keys',
        'price.manage', 'spend_ceiling.manage',
        'user.tombstone'
    ))
""",
)

#: ADMIN ONLY, and it is the whole of the seed decision. Handing somebody a
#: folder is an administrative act: `prompt.grant` stays with Owner so an author
#: can share one prompt, and the bulk instrument stays with the role that already
#: holds `workspace.manage_members` and `workspace.manage_keys`. Which role
#: SHOULD hold it is OQ-006's, like every other row in this table; what this line
#: buys is that the answer is a row rather than a code change.
SEED_NAMESPACE_GRANT_ACTION = """
INSERT INTO access.role_permission (role, action)
VALUES ('Admin', 'namespace.grant');
"""

#: The trail. `target_id` is the NAMESPACE — a string, not a row id, because
#: A-157 makes a grant name a string rather than a folder row, and
#: `history_event.target_id` is a value and not a foreign key (ADR-0054), which is
#: what makes that free. A reader looking for *who was let into `support`* finds
#: both events under `support`, whether or not a `registry.folder` row for it has
#: ever existed or still does.
#:
#: `detail_keys` mirrors `access_granted`'s post-amendment shape rather than
#: revision 0005's empty one, because AC-12's requirement — actor, grantee, level,
#: timestamp — applies here word for word and the asymmetric pair D-62 fixed for
#: prompt grants is not worth reintroducing one scope up.
SEED_NAMESPACE_HISTORY_ACTIONS = """
INSERT INTO history.history_action_registry
    (action, target_type, detail_keys, requires_reason, writing_module)
VALUES
    ('namespace_access_granted', 'namespace_grant',
        '{grantee_user_id,level}', false, 'access-control'),
    ('namespace_access_revoked', 'namespace_grant',
        '{grantee_user_id,level}', false, 'access-control');
"""

#: Leaves the EVENTS behind, which is the whole asymmetry of this pair. The
#: registry rows go because nothing may reference an action that no longer exists;
#: any `history_event` already written under them would block this DELETE by the
#: foreign key, and that refusal is correct — a downgrade must not be able to
#: erase a record of who was granted what.
UNSEED_NAMESPACE_HISTORY_ACTIONS = """
DELETE FROM history.history_action_registry
 WHERE action IN ('namespace_access_granted', 'namespace_access_revoked');
"""

#: DROP and CREATE rather than CREATE OR REPLACE: the return type changes, and
#: Postgres refuses a replacement that does. The function stays one of ADR-0042's
#: four sanctioned escalations — it still returns an identity tuple and still
#: authenticates nothing, because the hash comparison stays in the application
#: (ADR-0042's rule, and the reason this returns `key_hash` rather than a bool).
DROP_LOOKUP_API_KEY = "DROP FUNCTION IF EXISTS access.lookup_api_key(text);"

CREATE_LOOKUP_API_KEY = """
CREATE FUNCTION access.lookup_api_key(p_key_id text)
RETURNS TABLE (
    workspace_id                text,
    key_id                      text,
    key_hash                    text,
    scope_model_names           text[],
    scope_namespaces            text[],
    observe_provider_config_id  text,
    observe_namespace           text,
    revoked_at                  timestamptz
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT k.workspace_id, k.id, k.key_hash, k.scope_model_names, k.scope_namespaces,
           k.observe_provider_config_id, k.observe_namespace, k.revoked_at
    FROM   access.api_key AS k
    WHERE  k.id = p_key_id
$$;
"""

RESTORE_LOOKUP_API_KEY = """
CREATE FUNCTION access.lookup_api_key(p_key_id text)
RETURNS TABLE (
    workspace_id       text,
    key_id             text,
    key_hash           text,
    scope_model_names  text[],
    revoked_at         timestamptz
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT k.workspace_id, k.id, k.key_hash, k.scope_model_names, k.revoked_at
    FROM   access.api_key AS k
    WHERE  k.id = p_key_id
$$;
"""

#: The function is owned by `prope_migrate` and executed by `prope_app`, which is
#: what makes the definer escalation work at all. Recreating it drops the grant
#: with the old function, so it is re-issued here.
#: A tuple for `NARROW_ACTION_VOCABULARY`'s reason. `REVOKE` then `GRANT`, in
#: that order: the revoke strips the implicit `PUBLIC EXECUTE` a freshly created
#: function carries, and the grant hands it back to the one role that may have it
#: — reversing them would leave the function briefly world-executable and then
#: revoke the grant it had just issued.
GRANT_LOOKUP_API_KEY = (
    "REVOKE ALL ON FUNCTION access.lookup_api_key(text) FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION access.lookup_api_key(text) TO prope_app",
)


def upgrade() -> None:
    assume_migrate_role()

    op.execute(CREATE_NAMESPACE_GRANT)
    for statement in CREATE_INDEXES:
        op.execute(statement)
    enable_tenant_rls("access", "namespace_grant")

    # DELETE is granted, unlike on api_key: a revocation here removes the row, the
    # way `prompt_grant`'s does, and the history event is what survives it
    # (ADR-0024's `access_revoked`). The append-only rule belongs to
    # `history_event`, not to every table a history event is about.
    grant_table(
        "access",
        "namespace_grant",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )

    op.execute(ADD_KEY_COLUMNS)
    op.execute(WIDEN_ACTION_VOCABULARY)
    op.execute(SEED_NAMESPACE_GRANT_ACTION)
    op.execute(SEED_NAMESPACE_HISTORY_ACTIONS)

    op.execute(DROP_LOOKUP_API_KEY)
    op.execute(CREATE_LOOKUP_API_KEY)
    for statement in GRANT_LOOKUP_API_KEY:
        op.execute(statement)

    reset_role()


def downgrade() -> None:
    """Drops grants. Refuses nothing, and that asymmetry is deliberate.

    Revision 0020's downgrade refuses while a playground row exists, because
    ``call_record`` is the accountability record and T-006 gives the application
    no DELETE on it. A ``namespace_grant`` is not that: it is live authority, the
    application already holds DELETE on it, and revoking every namespace grant is
    exactly what reverting this feature *means*. The events recording that they
    were granted stay in ``history_event``, where nothing deletes them.
    """
    assume_migrate_role()

    op.execute(DROP_LOOKUP_API_KEY)
    op.execute(RESTORE_LOOKUP_API_KEY)
    for statement in GRANT_LOOKUP_API_KEY:
        op.execute(statement)

    op.execute(UNSEED_NAMESPACE_HISTORY_ACTIONS)
    for statement in NARROW_ACTION_VOCABULARY:
        op.execute(statement)
    op.execute(DROP_KEY_COLUMNS)
    op.execute("DROP TABLE IF EXISTS access.namespace_grant")

    reset_role()
