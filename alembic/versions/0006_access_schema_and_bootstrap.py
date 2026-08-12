"""the access schema, its eight tables, the RLS bootstrap, and the role matrix

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-11

The schema, eight tables, five indexes, three `SECURITY DEFINER` functions, the
tenant policies, the grant matrix, the 37-row `(role, action)` seed, and one
amendment to revision 0005's action registry.

**THREE `SECURITY DEFINER` FUNCTIONS SHIP HERE, NOT TWO — D-60.** ADR-0042
sanctions `access.lookup_session` and `access.lookup_api_key`; ADR-0051 adds
`access.list_workspaces()` and attributes it to release-control's sweeps, which
arrive in phase 22. It is built here because **the tombstone needs it in phase
8** and needs it for exactly the reason ADR-0051 generalises: *"a background job
that must discover its own work across tenants needs exactly the escape an
authentication bootstrap needs."* A-151 requires one transaction to delete every
session a departing person holds, delete every role binding, move every
membership to `removed`, delete every grant naming them, and append one
`user_tombstoned` event **per workspace** — and every one of those tables is
tenant-scoped, so a request holding one tenant can reach none of the others. The
alternatives were a fourth definer function shaped like the tombstone (rejected
by ADR-0051's own rule: a function returning ROWS performs the read with the
policy off) and leaving `session` unpolicied (rejected by ADR-0042 by name). The
generic enumerator was designed for this and returns `SETOF text`.

`evaluation.claim_next_run()` remains unbuilt; it arrives with its consumer in
phase 16. The set is enumerated, not open — see
`tests/security/test_security_definer_objects_are_exactly_the_expected_set.py`.

**Deviation D-61, no OQ owed.** ADR-0042 writes the tenant predicate as
`... = current_setting('app.workspace_id')::uuid`. `alembic/ddl.py` already
records why the cast is not issued — a workspace id is a `wsp_`-prefixed ULID,
not a UUID — and this revision is the first one where the point is load-bearing
rather than theoretical, because `access.workspace.id` **is** that value.

**Deviation D-62, OQ-132 raised.** Revision 0005 seeded `access_granted`,
`access_revoked` and `role_revoked` with **empty** `detail_keys`, derived from
lock-file `outputs` blocks that list event *names* and say nothing about
payloads. AC-12 requires the grant events to carry *"actor, grantee, level"*, and
`role_revoked` was asymmetric with `role_assigned`, which already carries
`{role, grantee_user_id}`. Three `UPDATE`s below fix it. This is the writing
module amending its own rows in its own revision; no row is added or removed, so
the 31-name vocabulary and every count asserted against it are unchanged.

**No `access.user` row is ever deleted, and the grant matrix is what says so.**
`prope_app` holds `SELECT, INSERT, UPDATE` on that table and no `DELETE` — the
same construction ADR-0025 uses on `history_event`. ADR-0054's *"tombstoned,
never deleted"* is therefore a database privilege rather than a convention, and
`workspace_member` is protected the same way because A-151 retains those rows to
know which workspaces to write the tombstone's events into.
"""

from collections.abc import Sequence

# WHY the bare name: `alembic.ddl` resolves to the installed package's own
# dialect-DDL submodule. `alembic.ini`'s prepend_sys_path puts this directory first.
from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# The tables
# ---------------------------------------------------------------------------

# The tenancy root (A-109). Its PRIMARY KEY *is* the workspace id, which is why
# ADR-0042 needed a policy written against `id` and why ADR-0045 later made it an
# ordinary GLOBAL_TABLES entry rather than a clause bolted onto the coverage test.
#
# `created_by` is a VALUE, like every other actor id in the build (A-122). No FK:
# the first workspace's creator is bootstrapped out of band, and ADR-0054 keeps
# the row forever anyway, so the constraint would buy nothing and would order the
# two inserts for no reason.
CREATE_WORKSPACE = """
CREATE TABLE access.workspace (
    id          text         NOT NULL,
    name        text         NOT NULL,
    slug        text         NOT NULL,
    created_by  text         NOT NULL,

    -- Database-observed, so it carries a default. Caller-supplied times never do.
    created_at  timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_workspace PRIMARY KEY (id),

    -- A slug is a URL segment; two workspaces sharing one is a routing bug that
    -- presents as a permission bug.
    CONSTRAINT uq_workspace_slug UNIQUE (slug),

    -- ADR-0003's typed prefixes, enforced rather than documented: `id` is the
    -- value every other schema in Prope stores as `workspace_id` and compares
    -- against `app.workspace_id`, so a malformed one is a cross-schema defect.
    CONSTRAINT ck_workspace_id_prefix CHECK (id LIKE 'wsp\\_%'),

    CONSTRAINT ck_workspace_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_workspace_slug_format CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$')
);
"""

# A person is not a tenant's property (ADR-0045). No `workspace_id`, no policy,
# and `unique(email)` is install-wide — which is also what makes it possible to
# say "this email is already registered" without reading another workspace.
#
# THE NULLABILITY IS ADR-0054'S. `email`, `display_name` and `password_hash` are
# nullable *only* so a tombstone can clear them; the pair of CHECKs below makes
# every intermediate state unreachable, so nullable-in-the-column is not
# nullable-in-practice for an active account. PostgreSQL permits any number of
# NULLs in a unique index, which is what lets many people be tombstoned (A-151).
CREATE_USER = """
CREATE TABLE access."user" (
    id                    text         NOT NULL,

    email                 text,
    display_name          text,
    password_hash         text,

    -- A-110: an Admin creates the account and hands the password over out of
    -- band, so the first sign-in must change it. Defaulting to true means an
    -- account created by a path that forgot to think about it is the SAFE one.
    must_change_password  boolean      NOT NULL DEFAULT true,

    status                text         NOT NULL DEFAULT 'active',
    created_at            timestamptz  NOT NULL DEFAULT now(),

    -- Unchanged by a tombstone (A-151): a timestamp is not identifying, and
    -- zeroing it would destroy the only signal that an account was ever used.
    last_login_at         timestamptz,

    tombstoned_at         timestamptz,
    tombstoned_by         text,

    CONSTRAINT pk_user PRIMARY KEY (id),
    CONSTRAINT uq_user_email UNIQUE (email),
    CONSTRAINT ck_user_id_prefix CHECK (id LIKE 'usr\\_%'),

    -- Never a native enum (Pitfall 4). Two values, and there is deliberately no
    -- third: A-110 has no pending state because there is no invitation to be
    -- pending on, and nothing un-tombstones a row (ADR-0054 §8).
    CONSTRAINT ck_user_status_values CHECK (status IN ('active', 'tombstoned')),

    -- A-151, FIELD BY FIELD, AT THE ENGINE. The tombstone is nine column writes
    -- in one statement, and a half-applied one is an account with no name that
    -- can still authenticate. These two CHECKs make every half state
    -- unreachable, so the erasure claim rests on a constraint rather than on the
    -- application getting all nine right.
    CONSTRAINT ck_user_active_row_is_whole CHECK (
        status <> 'active' OR (
            email IS NOT NULL
            AND display_name IS NOT NULL
            AND password_hash IS NOT NULL
            AND tombstoned_at IS NULL
            AND tombstoned_by IS NULL
        )
    ),
    CONSTRAINT ck_user_tombstoned_row_is_whole CHECK (
        status <> 'tombstoned' OR (
            email IS NULL
            AND display_name IS NULL
            AND password_hash IS NULL
            AND must_change_password = false
            AND tombstoned_at IS NOT NULL
            AND tombstoned_by IS NOT NULL
        )
    )
);
"""

# Server-side rows rather than self-contained tokens (A-108, ADR-0022, ADR-0029),
# so sign-out and member removal are effective at once instead of at expiry.
#
# `id` IS THE CREDENTIAL, AND THAT IS WHY IT IS NOT A ULID. Every other
# identifier in Prope is a prefixed ULID under A-045 because it identifies a row
# somebody is allowed to name. This one is the whole of a person's authority
# (ADR-0029) and travels in a cookie, so it is 256 bits from a CSPRNG behind a
# `ses_` prefix — see `prope.access_control.sessions`. A ULID would put a
# timestamp and a monotonic counter in a bearer token, and the prefix convention
# would have quietly supplied the reason to do it.
#
# `user_agent_hash` is a hash and never the string: a user agent is fingerprinting
# material, and A-046 keeps it out of everything downstream by never storing it.
CREATE_SESSION = """
CREATE TABLE access.session (
    id               text         NOT NULL,
    user_id          text         NOT NULL,
    workspace_id     text         NOT NULL,

    created_at       timestamptz  NOT NULL DEFAULT now(),

    -- Caller-supplied (issued_at + a window), so no default. Enforced ON READ
    -- inside access.lookup_session rather than by a sweeper: an expired row is
    -- never returned even while it is still present, which is what lets the lock
    -- file say this module has no scheduled job.
    expires_at       timestamptz  NOT NULL,
    last_seen_at     timestamptz  NOT NULL DEFAULT now(),

    user_agent_hash  text,

    CONSTRAINT pk_session PRIMARY KEY (id),
    CONSTRAINT ck_session_id_prefix CHECK (id LIKE 'ses\\_%'),
    CONSTRAINT ck_session_expires_after_creation CHECK (expires_at > created_at),

    CONSTRAINT fk_session_user_id
        FOREIGN KEY (user_id) REFERENCES access."user" (id),
    CONSTRAINT fk_session_workspace_id
        FOREIGN KEY (workspace_id) REFERENCES access.workspace (id)
);
"""

# Membership is the fact that makes a workspace mean anything. There is no
# pending state, because there is no invitation to be pending on (A-110).
#
# `status = 'removed'` rather than a deleted row, and the grant matrix withholds
# DELETE to keep it that way: A-151 needs these rows to know which workspaces a
# tombstone must write its event into, and a workspace's own trail stays complete
# because the row that says somebody was once here survives.
CREATE_WORKSPACE_MEMBER = """
CREATE TABLE access.workspace_member (
    workspace_id  text         NOT NULL,
    user_id       text         NOT NULL,
    added_by      text         NOT NULL,
    added_at      timestamptz  NOT NULL DEFAULT now(),
    status        text         NOT NULL DEFAULT 'active',

    CONSTRAINT pk_workspace_member PRIMARY KEY (workspace_id, user_id),
    CONSTRAINT ck_workspace_member_status_values
        CHECK (status IN ('active', 'removed')),

    CONSTRAINT fk_workspace_member_workspace_id
        FOREIGN KEY (workspace_id) REFERENCES access.workspace (id),
    CONSTRAINT fk_workspace_member_user_id
        FOREIGN KEY (user_id) REFERENCES access."user" (id)
);
"""

# A user may hold several roles; their permissions UNION (A-111). The primary key
# is (workspace_id, user_id, role) rather than (workspace_id, user_id), and that
# is the union rule expressed as a constraint: a schema with one role per member
# could not represent the answer AC-3 asserts.
#
# `role` carries a CHECK and not a foreign key to `role_permission`, whose key is
# (role, action) and cannot be referenced by `role` alone. The CHECK is the
# honest consequence: OQ-006 changing the MATRIX is a re-seed, and OQ-006 changing
# the ROLE SET is a migration — which is exactly what A-007 already says about
# removing a role after bindings exist.
CREATE_ROLE_BINDING = """
CREATE TABLE access.role_binding (
    workspace_id  text         NOT NULL,
    user_id       text         NOT NULL,
    role          text         NOT NULL,
    granted_by    text         NOT NULL,
    granted_at    timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_role_binding PRIMARY KEY (workspace_id, user_id, role),
    CONSTRAINT ck_role_binding_role_values
        CHECK (role IN ('Owner', 'Reviewer', 'Viewer', 'Admin')),

    CONSTRAINT fk_role_binding_workspace_id
        FOREIGN KEY (workspace_id, user_id)
        REFERENCES access.workspace_member (workspace_id, user_id)
);
"""

# The matrix, as rows. This is what makes OQ-006's answer data rather than a
# migration: a different matrix is a different seed, and GET /api/v1/permissions
# renders the running one so it can be compared against the signed-off one.
#
# One table for the whole install (ADR-0045): a per-workspace matrix would mean
# the separation of edit / review / release is negotiable per tenant, and the
# constraints table calls it non-negotiable.
CREATE_ROLE_PERMISSION = """
CREATE TABLE access.role_permission (
    role    text  NOT NULL,
    action  text  NOT NULL,

    CONSTRAINT pk_role_permission PRIMARY KEY (role, action),
    CONSTRAINT ck_role_permission_role_values
        CHECK (role IN ('Owner', 'Reviewer', 'Viewer', 'Admin')),

    -- A-115's closed vocabulary, at the engine. The list must be EDITED to grow,
    -- and that edit is the moment somebody decides who holds the new action —
    -- which is the whole feature. Mirrored in `prope.access_control.actions`, and
    -- `tests/contract/test_action_vocabulary_is_one_list.py` asserts the two are
    -- the same 25 strings so the mirror cannot drift.
    CONSTRAINT ck_role_permission_action_values CHECK (action IN (
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
);
"""

# BR-01's private-by-default grants. `workspace_id` was added by ADR-0042 for one
# reason: without it, ADR-0035's coverage test could not SEE this table, and the
# table it could not see is the one implementing the product's privacy claim.
#
# `prompt_id` is a VALUE, not a foreign key. An FK would point this schema at
# prompt-registry's table in the forbidden direction (ADR-0020) — the mirror of
# provider-access's case, where the constraint ran the same way the dependency
# already did and was therefore free. Prompts are never deleted (ADR-0002), so it
# would buy nothing anyway.
CREATE_PROMPT_GRANT = """
CREATE TABLE access.prompt_grant (
    workspace_id     text         NOT NULL,
    prompt_id        text         NOT NULL,
    grantee_user_id  text         NOT NULL,
    level            text         NOT NULL,
    granted_by       text         NOT NULL,
    granted_at       timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_prompt_grant PRIMARY KEY (workspace_id, prompt_id, grantee_user_id),

    -- A-112. No grant confers approve, release, withdraw or break-glass —
    -- letting an owner hand those out per prompt would let a workspace's
    -- non-negotiable separation be dissolved one prompt at a time.
    CONSTRAINT ck_prompt_grant_level_values CHECK (level IN ('viewer', 'editor')),

    CONSTRAINT fk_prompt_grant_workspace_id
        FOREIGN KEY (workspace_id, grantee_user_id)
        REFERENCES access.workspace_member (workspace_id, user_id)
);
"""

# A-081, A-113, ADR-0021. The id is embedded in the presented secret
# (`prope_<key_id>_<secret>`) so authentication is one indexed read plus one
# constant-time comparison rather than a table scan.
#
# HASHED, NOT ENCRYPTED, and the column set is what makes that irreversible: the
# row keeps `key_hash` for verification, `last_four` for display and
# `last_used_at` for finding dead keys, and nothing from which the secret could
# be reconstructed. A database dump yields no working key. The deliberate
# opposite answer for a provider credential is ADR-0014's, and the difference is
# the direction of use.
#
# `revoked_at` rather than a deleted row: revocation must be readable afterwards,
# and the grant matrix withholds DELETE accordingly.
CREATE_API_KEY = """
CREATE TABLE access.api_key (
    id                 text         NOT NULL,
    workspace_id       text         NOT NULL,
    name               text         NOT NULL,
    key_hash           text         NOT NULL,
    last_four          text         NOT NULL,

    -- A-081: explicit and DEFAULT-DENY. An empty scope resolves nothing, and
    -- releasing a new prompt does not make it callable by an existing key.
    scope_model_names  text[]       NOT NULL DEFAULT '{}',

    created_by         text         NOT NULL,
    created_at         timestamptz  NOT NULL DEFAULT now(),
    revoked_at         timestamptz,
    last_used_at       timestamptz,

    CONSTRAINT pk_api_key PRIMARY KEY (id),
    CONSTRAINT ck_api_key_id_prefix CHECK (id LIKE 'key\\_%'),
    CONSTRAINT ck_api_key_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_api_key_last_four_length CHECK (char_length(last_four) = 4),

    -- The presented format embeds `id`, so an id containing the separator would
    -- make the parse ambiguous and a key unauthenticatable after issue.
    CONSTRAINT ck_api_key_id_has_no_separator CHECK (position('_' in substr(id, 5)) = 0),

    CONSTRAINT fk_api_key_workspace_id
        FOREIGN KEY (workspace_id) REFERENCES access.workspace (id)
);
"""

# Five, and the count is deliberate: every other access path in this module is a
# primary-key probe or a policy-filtered scan of a table with one row per member.
#
# The first two are the LIST endpoints, which are the paths ADR-0035 was written
# to protect. The third is A-118's expensive branch — visible_subject_filter's
# `ids` mode, whose stated condition is a workspace with 1,000 prompts and an
# actor whose visibility comes entirely from grants. The fourth serves the
# tombstone and sign-out-everywhere. The fifth is the zero-Admin count (A-117),
# which runs inside every member removal and every role change.
CREATE_INDEXES = (
    """
    CREATE INDEX ix_api_key_workspace_id_created_at
        ON access.api_key (workspace_id, created_at DESC)
    """,
    """
    CREATE INDEX ix_workspace_member_workspace_id_status
        ON access.workspace_member (workspace_id, status)
    """,
    """
    CREATE INDEX ix_prompt_grant_workspace_id_grantee_user_id
        ON access.prompt_grant (workspace_id, grantee_user_id)
    """,
    """
    CREATE INDEX ix_session_workspace_id_user_id
        ON access.session (workspace_id, user_id)
    """,
    """
    CREATE INDEX ix_role_binding_workspace_id_role
        ON access.role_binding (workspace_id, role)
    """,
)


# ---------------------------------------------------------------------------
# The sanctioned bypasses (ADR-0042, ADR-0051)
# ---------------------------------------------------------------------------
#
# All three follow one template and every clause in it is a mitigation:
#
#   owned by prope_migrate     SECURITY DEFINER executes as the OWNER, and
#                              ADR-0035's tenant exemption is the owner bypass.
#                              `SET LOCAL ROLE` above is what makes that true.
#   SET search_path = ''       a definer body must not be redirectable by the
#                              caller's search_path; every identifier below is
#                              schema-qualified because of it.
#   STABLE                     they read and never write.
#   identifiers only           ADR-0051's general rule: a function returning
#                              tenant IDENTIFIERS keeps every subsequent read
#                              under RLS; one returning ROWS performs the read
#                              with the policy off, so a defect in the body is a
#                              cross-tenant leak with nothing behind it.
#   REVOKE then GRANT          PUBLIC gets EXECUTE on a new function by default.
#
# `lookup_api_key` returns the stored HASH and does not authenticate. The
# comparison stays in the application (ADR-0042, A-113) — a definer object with a
# security decision inside it is a different and much worse thing than a lookup.

CREATE_LOOKUP_SESSION = """
CREATE FUNCTION access.lookup_session(p_id text)
RETURNS TABLE (user_id text, workspace_id text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT s.user_id, s.workspace_id
    FROM   access.session AS s
    WHERE  s.id = p_id
      AND  s.expires_at > pg_catalog.now()
$$;
"""

CREATE_LOOKUP_API_KEY = """
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

# Deliberately generic, so the sanctioned set stops growing (ADR-0051). One
# enumerator serves every cross-tenant job in Prope, present and future — the
# tombstone in phase 8, release-control's sweeps in phase 22. A test asserting
# the set is exactly N means nothing once N tracks feature count.
CREATE_LIST_WORKSPACES = """
CREATE FUNCTION access.list_workspaces()
RETURNS SETOF text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT w.id FROM access.workspace AS w ORDER BY w.id
$$;
"""

DEFINER_FUNCTIONS = (
    "access.lookup_session(text)",
    "access.lookup_api_key(text)",
    "access.list_workspaces()",
)


# ---------------------------------------------------------------------------
# The seed (A-007, a placeholder for OQ-006)
# ---------------------------------------------------------------------------
#
# 37 rows over four roles. A-007's sentences, made into data:
#
#   Owner     may edit their own prompts and submit revisions
#   Reviewer  may approve or request changes on revisions they did not author
#   Viewer    may read prompts they have been granted access to
#   Admin     may transfer ownership and release
#
# THE ONE PROPERTY THAT IS NOT A PLACEHOLDER: no role holds two of
# `prompt.edit`, `revision.approve` and `release.create`. NFR-01 makes edit,
# review and release three distinct permissions, and a seed that gave one role
# two of them would satisfy every test in this repository while dissolving the
# constraint the product exists to enforce.
#
# Deciding WHO holds what is OQ-006's, and it is rated Critical. What this
# revision buys is that the answer is 37 different rows rather than a code change
# in six modules — and that `GET /api/v1/permissions` renders the running matrix
# so it can be diffed against the signed-off one when it arrives.
SEED_ROLE_PERMISSION = """
INSERT INTO access.role_permission (role, action)
VALUES
    -- Viewer, 4. Read-only, and every one of these is still filtered by
    -- ownership or a grant at the caller's edge (A-118) — a role that may read
    -- prompts is not a role that may see every prompt.
    ('Viewer',   'prompt.read'),
    ('Viewer',   'suite.read'),
    ('Viewer',   'run.read'),
    ('Viewer',   'catalogue.read'),

    -- Owner, 12. Authoring, in full: create, edit, retire, grant, revise,
    -- submit for review, edit the eval suite, start a run. NOT approve, and NOT
    -- release.
    ('Owner',    'prompt.read'),
    ('Owner',    'suite.read'),
    ('Owner',    'run.read'),
    ('Owner',    'catalogue.read'),
    ('Owner',    'prompt.create'),
    ('Owner',    'prompt.edit'),
    ('Owner',    'prompt.retire'),
    ('Owner',    'prompt.grant'),
    ('Owner',    'revision.create'),
    ('Owner',    'revision.submit'),
    ('Owner',    'suite.edit'),
    ('Owner',    'run.start'),

    -- Reviewer, 5. Reading plus exactly one write: the approval. `suite.edit` is
    -- deliberately absent — BR-10 makes editing the eval suite a distinct
    -- permission from editing prompt text, and a reviewer who could change the
    -- suite could change what "passing" means before approving.
    ('Reviewer', 'prompt.read'),
    ('Reviewer', 'suite.read'),
    ('Reviewer', 'run.read'),
    ('Reviewer', 'catalogue.read'),
    ('Reviewer', 'revision.approve'),

    -- Admin, 16. Releasing and administering. NOT `prompt.edit` and NOT
    -- `revision.approve`: an Admin who could author and approve and release
    -- would be the single actor NFR-01 exists to prevent.
    ('Admin',    'prompt.read'),
    ('Admin',    'suite.read'),
    ('Admin',    'run.read'),
    ('Admin',    'catalogue.read'),
    ('Admin',    'prompt.transfer_owner'),
    ('Admin',    'release.create'),
    ('Admin',    'release.break_glass'),
    ('Admin',    'release.withdraw'),
    ('Admin',    'workspace.manage_members'),
    ('Admin',    'workspace.manage_keys'),
    ('Admin',    'provider.configure'),
    ('Admin',    'provider.rotate_credential'),
    ('Admin',    'provider.disable'),
    ('Admin',    'price.manage'),
    ('Admin',    'spend_ceiling.manage'),
    ('Admin',    'user.tombstone');
"""


# D-62 / OQ-132. Three of this module's ten actions were seeded with no payload
# and need one. No row is added or removed; `requires_reason` is untouched
# everywhere, including on `user_tombstoned`, where its absence is ADR-0054 §7's
# whole point.
AMEND_ACTION_REGISTRY = (
    # AC-12: "an access_granted and an access_revoked event exist with actor,
    # grantee, level, and timestamp". `actor_id` and `occurred_at` are envelope
    # columns; grantee and level had nowhere to go. `target_id` is the prompt, so
    # a reader can find the grant events for a prompt — which means the grantee
    # cannot also be the target.
    """
    UPDATE history.history_action_registry
       SET detail_keys = '{grantee_user_id,level}'
     WHERE action IN ('access_granted', 'access_revoked')
    """,
    # `role_assigned` already carries `{role,grantee_user_id}`; `role_revoked`
    # carried nothing, so the trail recorded that a role was taken away and not
    # which one. An asymmetric pair is worse than either symmetric one, because a
    # reader believes the two are comparable.
    """
    UPDATE history.history_action_registry
       SET detail_keys = '{role,grantee_user_id}'
     WHERE action = 'role_revoked'
    """,
)


def upgrade() -> None:
    # WHY before assume_migrate_role(): prope_migrate may not hold CREATE ON
    # DATABASE, and AUTHORIZATION is what ADR-0035's owner bypass rests on.
    op.execute("CREATE SCHEMA access AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA access TO prope_app, prope_report")

    assume_migrate_role()

    # Creation order is foreign-key order: workspace and user are referenced by
    # everything, workspace_member by the two tables keyed on membership.
    op.execute(CREATE_WORKSPACE)
    op.execute(CREATE_USER)
    op.execute(CREATE_SESSION)
    op.execute(CREATE_WORKSPACE_MEMBER)
    op.execute(CREATE_ROLE_BINDING)
    op.execute(CREATE_ROLE_PERMISSION)
    op.execute(CREATE_PROMPT_GRANT)
    op.execute(CREATE_API_KEY)

    for statement in CREATE_INDEXES:
        op.execute(statement)

    op.execute(SEED_ROLE_PERMISSION)

    # Same revision as the tables. The window between a table existing and its
    # policy existing is a window in which prope_app reads across tenants.
    enable_tenant_rls("access", "session")
    enable_tenant_rls("access", "workspace_member")
    enable_tenant_rls("access", "role_binding")
    enable_tenant_rls("access", "prompt_grant")
    enable_tenant_rls("access", "api_key")

    # ADR-0042: the tenancy root is policied on `id`, because it IS the workspace
    # id. `ddl.enable_tenant_rls` already takes the column, so this stays a
    # helper call a reviewer can grep rather than bespoke SQL.
    enable_tenant_rls("access", "workspace", column="id")

    # The grant matrix, and every withheld privilege below is a decision:
    #
    #   workspace          no UPDATE — nothing renames a workspace in the MVP.
    #   user               no DELETE — ADR-0054 makes "tombstoned, never
    #                      deleted" a privilege rather than a convention.
    #   workspace_member   no DELETE — A-151 retains these rows so the tombstone
    #                      knows which workspaces to write its events into.
    #   role_permission    SELECT only — the matrix is seeded by migration, which
    #                      is what makes GET /api/v1/permissions a reading of the
    #                      RUNNING matrix rather than of an editable copy.
    #   api_key            no DELETE — revocation is a timestamp, because a
    #                      deleted key row would orphan its history events.
    #
    # `prompt_grant` keeps DELETE: A-151 deletes a departing person's grants, and
    # a revoked grant is not a fact anything reads afterwards — the history event
    # is (which is why D-62 above had to give that event its payload).
    grant_table("access", "workspace", app_privileges=["SELECT", "INSERT"])
    grant_table("access", '"user"', app_privileges=["SELECT", "INSERT", "UPDATE"])
    grant_table("access", "session", app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"])
    grant_table("access", "workspace_member", app_privileges=["SELECT", "INSERT", "UPDATE"])
    grant_table("access", "role_binding", app_privileges=["SELECT", "INSERT", "DELETE"])
    grant_table("access", "role_permission", app_privileges=["SELECT"])
    grant_table("access", "prompt_grant", app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"])
    grant_table("access", "api_key", app_privileges=["SELECT", "INSERT", "UPDATE"])

    op.execute(CREATE_LOOKUP_SESSION)
    op.execute(CREATE_LOOKUP_API_KEY)
    op.execute(CREATE_LIST_WORKSPACES)

    for signature in DEFINER_FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prope_app")

    for statement in AMEND_ACTION_REGISTRY:
        op.execute(statement)

    reset_role()


def downgrade() -> None:
    assume_migrate_role()

    # The amendment first, and back to 0005's literal values rather than to
    # "empty": a downgrade that guessed would leave the registry in a state no
    # revision ever wrote.
    op.execute(
        "UPDATE history.history_action_registry SET detail_keys = '{}' "
        "WHERE action IN ('access_granted', 'access_revoked', 'role_revoked')"
    )

    for signature in DEFINER_FUNCTIONS:
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")

    # CASCADE on the schema would be shorter and would also drop anything a later
    # revision put here without saying so.
    for table in (
        "api_key",
        "prompt_grant",
        "role_permission",
        "role_binding",
        "workspace_member",
        "session",
        '"user"',
        "workspace",
    ):
        op.execute(f"DROP TABLE IF EXISTS access.{table}")

    op.execute("DROP SCHEMA IF EXISTS access CASCADE")
    reset_role()
