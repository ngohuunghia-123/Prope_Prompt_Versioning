"""A session may name no workspace; a membership may be pending; invitations exist

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-17

**Three guarantees, one revision, because they are one feature.** A person can now
sign in without belonging anywhere, ask to join a workspace they were given a code
for, and wait there until somebody with `workspace.manage_members` decides. Each of
the three needs the other two to mean anything: a pending membership with no way to
be signed in is unreachable, and an invitation that admits instantly is not a
decision anybody records.

## What each piece is, and what it costs

**`access.session.workspace_id` becomes nullable.** Until now a session named
exactly one tenant and `dependencies.path_workspace` compared against it, which is
what made that equality a total answer. It still is — a session that names a
workspace names exactly one — but a session may now name *none*, and every route
that touches tenant data refuses one. The refusal lives in
`prope.session_auth.require_session`, which is the only place a `Session` is
constructed, so the nullable column cannot leak into a handler that assumed a
string.

**A NULL there is invisible to `prope_app` under the existing policy**, and that is
not a side effect — it is the problem this revision has to solve. `workspace_id =
current_setting('app.workspace_id', true)` evaluates to NULL for a NULL column, NULL
is not true, and `WITH CHECK` therefore refuses the INSERT as well as hiding the
row. So a workspace-less session could not be *written* by the runtime role at all.

`session_lobby` is the answer, and it is a **second policy rather than a widened
one**. Policies for the same role and command are OR-ed, so the tenant policy is
left byte-identical to what `ddl.enable_tenant_rls` emits everywhere else in the
product — a reviewer greps the helper name and finds the same predicate on `session`
as on the other five tables, and the exception is a separate object with its own
name they can also grep. Widening the first predicate would have hidden the
exception inside the rule.

Its predicate is `workspace_id IS NULL AND user_id = current_setting('app.user_id',
true)`. Deny-by-default survives in the same way ADR-0035 buys it everywhere else:
on a connection that never set `app.user_id` the two-argument `current_setting`
returns NULL, the comparison is NULL, and the policy admits nothing. **A lobby
session is reachable only inside a transaction opened by the person who owns it** —
`prope.db.session.lobby_transaction` is the only thing that sets that GUC — so the
row holding a bearer credential is not sitting in a bucket every tenant can read,
which is what a sentinel `wsp_lobby` workspace would have produced.

`app.user_id` is the second tenant-ish GUC in the product and it is deliberately
**not** a tenant: nothing else is policied on it, and nothing else may be. It exists
because a lobby session has no workspace to be scoped by and still must be scoped by
something.

**`workspace_member.status` gains `pending`.** Revision 0006 wrote *"there is no
pending state, because there is no invitation to be pending on (A-110)"*, and that
sentence was true for exactly as long as A-110's no-invitation rule held. It no
longer does — see ADR-0057, which supersedes that clause — so the CHECK is widened
by one value.

The gating this buys is **already written and needs no new code**:
`sessions.LOAD_ACTIVE_MEMBERSHIP` filters `status = 'active'`, so a pending member
cannot resolve that workspace at sign-in or in the switcher, and there is no second
code path anybody could forget to add the condition to. `LIST_MEMBERS` already takes
a status filter, so the approval queue is a query parameter rather than an endpoint.

`role_binding`'s foreign key points at `workspace_member (workspace_id, user_id)`
and is untouched — a pending member *could* hold a role binding as far as the schema
is concerned. Nothing writes one: roles are assigned by `commands.approve_member` at
the moment the status is lifted, in the same transaction, which is the same
one-transaction rule `create_workspace` already follows for A-117.

**`access.workspace_invite` is the ninth table in `access`**, and the count in
`prope.access_control.models` and `tests/architecture/test_schema_invariants.py`
moves from eight to nine in the same commit. That drift guard exists to make a
widening *visible*, not to prevent one; this is the visible edit it asks for.

It is shaped on `access.api_key` on purpose, because the two objects have the same
security properties: a secret is minted, shown once, and stored only as a SHA-256
digest, so a database dump yields nothing anybody can present. **Unlike `api_key`
there is no `last_four`.** A key's secret is long and four characters identify a row
without weakening it; an invite code is six characters, and displaying four of them
would leave 62² guesses. Nothing derived from the code is stored, and the admin list
identifies a row by when it was made and when it dies.

**One table for two kinds of invitation**, split by `ck_workspace_invite_one_kind`:
a *code* invite carries `code_hash` and admits whoever presents it — to the pending
queue, never further; an *email* invite carries `invited_email` and reserves a seat
for one address, redeemed automatically when that person registers. They are one
table because the admin screen renders them as one list, they revoke through one
path, and a second table would be a second place for "who is on their way in" to be
answered from.

`invite_redeem` is the second exception policy in this revision and it is
**`FOR SELECT` only**, scoped by `app.invite_code_hash` / `app.invite_email`. The
important property is not that it lets a lobby read happen — it is that it bounds
what a lobby read can *return*. A careless `SELECT * FROM access.workspace_invite`
inside `invite_lookup_transaction` yields at most the single row whose code the
caller actually presented, so "dump every live invitation in the install" is not a
statement anybody can write by forgetting a `WHERE`. That is ADR-0035's inversion
applied to a non-tenant axis, and it is why this is a policy rather than an
unpolicied table.

**Five history actions.** `invite_created` and `invite_revoked` carry **no detail
keys**, copying `api_key_created`'s empty allow-list deliberately rather than by
omission: there must be no registered slot for the code, and none for
`invited_email` either — an address is a fact about a person, and the trail is the
one table nothing can be deleted from. Who was invited is readable from
`GET /workspaces/{id}/invites` by somebody already holding `workspace.manage_members`.

`member_join_requested` is the one exception and carries `{invite_id}`, because the
question an Admin asks at the approval screen is *which door did this person come
through* — and answering it any other way would need a column on
`workspace_member`, which would make the membership table remember how every member
arrived forever.

All five are `requires_reason = false`. A reason is demanded where an act is
exceptional and needs justifying as it happens — break-glass, a withdrawal, a change
request. Deciding who works here is ordinary administration.

**`target_type = 'invite'` is new**, and `property_history.domain`'s
`NEVER_PROMPT_SCOPED_TARGET_TYPES` gains it in the same commit. Without that, every
invite event would increment `null_scope_prompt_total` — the counter that exists to
find events which *should* have named a prompt and did not — and an invitation names
no prompt by construction.
"""

from collections.abc import Sequence

from ddl import (
    APP_ROLE,
    assume_migrate_role,
    enable_tenant_rls,
    grant_table,
    reset_role,
)

from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# access.session — a session may now name no workspace
# ---------------------------------------------------------------------------

DROP_SESSION_WORKSPACE_NOT_NULL = """
ALTER TABLE access.session ALTER COLUMN workspace_id DROP NOT NULL;
"""

RESTORE_SESSION_WORKSPACE_NOT_NULL = """
ALTER TABLE access.session ALTER COLUMN workspace_id SET NOT NULL;
"""

#: Deletes lobby rows so the NOT NULL above can be restored. A session is a
#: credential with a 12-hour ceiling and no downstream reader, so ending some
#: early is the cheapest correct downgrade — the alternative is inventing a
#: workspace for a person who is a member of none.
DELETE_LOBBY_SESSIONS = """
DELETE FROM access.session WHERE workspace_id IS NULL;
"""

#: The exception, as its own object. `FOR ALL` rather than `FOR SELECT`: the
#: lobby session is inserted at sign-in, read on every request, and deleted when
#: the person enters a workspace or signs out — all four commands, all under
#: this predicate, none of them reachable without the GUC.
CREATE_SESSION_LOBBY_POLICY = f"""
CREATE POLICY session_lobby ON access.session
    FOR ALL TO {APP_ROLE}
    USING      (workspace_id IS NULL
                AND user_id = current_setting('app.user_id', true))
    WITH CHECK (workspace_id IS NULL
                AND user_id = current_setting('app.user_id', true));
"""

DROP_SESSION_LOBBY_POLICY = "DROP POLICY IF EXISTS session_lobby ON access.session;"

#: `lookup_session` is unchanged and does not need to be: it is SECURITY DEFINER,
#: so it never met the policy in the first place, and its RETURNS TABLE already
#: types `workspace_id` as plain `text` with no NOT NULL to violate.
#:
#: The one index worth adding. `lobby_transaction` reads and deletes by
#: `user_id` under a predicate that is only ever satisfied by NULL rows, and a
#: partial index is what keeps that off a sequential scan without adding a
#: second full index to a table every authenticated request already touches.
CREATE_SESSION_LOBBY_INDEX = """
CREATE INDEX ix_session_user_id_lobby
    ON access.session (user_id)
    WHERE workspace_id IS NULL;
"""

DROP_SESSION_LOBBY_INDEX = "DROP INDEX IF EXISTS access.ix_session_user_id_lobby;"


# ---------------------------------------------------------------------------
# access.workspace_member — a third status
# ---------------------------------------------------------------------------

#: One statement per element. asyncpg prepares every statement it is handed, and
#: a prepared statement holds exactly one command — so a semicolon-joined blob is
#: a syntax error rather than a script, and every multi-statement step in this
#: file is a tuple for that reason.
WIDEN_MEMBER_STATUS = (
    """
    ALTER TABLE access.workspace_member
        DROP CONSTRAINT ck_workspace_member_status_values
    """,
    """
    ALTER TABLE access.workspace_member
        ADD CONSTRAINT ck_workspace_member_status_values
            CHECK (status IN ('active', 'removed', 'pending'))
    """,
)

#: A pending row is a request nobody answered. Rewriting it to `removed` on the
#: way down is the honest reading — the person is not a member, and `removed` is
#: the value that has always meant that.
NARROW_MEMBER_STATUS = (
    """
    UPDATE access.workspace_member SET status = 'removed' WHERE status = 'pending'
    """,
    """
    ALTER TABLE access.workspace_member
        DROP CONSTRAINT ck_workspace_member_status_values
    """,
    """
    ALTER TABLE access.workspace_member
        ADD CONSTRAINT ck_workspace_member_status_values
            CHECK (status IN ('active', 'removed'))
    """,
)

#: The approval queue's read — every pending member of one workspace — needs no
#: index of its own: revision 0006 already built
#: `ix_workspace_member_workspace_id_status` on `(workspace_id, status)`, which
#: is exactly the pair this filter fixes, and `LIST_MEMBERS` keysets on `user_id`
#: so the ordering still falls out of the primary key. A third status is more
#: rows under an existing leading edge, not a new access path. Creating it here
#: as well is what made this revision fail with `DuplicateTableError`, and the
#: downgrade that dropped it would have taken 0006's index with it.


# ---------------------------------------------------------------------------
# access.workspace_invite — the ninth table
# ---------------------------------------------------------------------------

CREATE_WORKSPACE_INVITE = """
CREATE TABLE access.workspace_invite (
    id             text         NOT NULL,
    workspace_id   text         NOT NULL,

    -- Exactly one of these two is present; the CHECK below is what says so.
    -- `code_hash` is SHA-256 of the presented code and there is deliberately no
    -- column derived from the code itself: six characters cannot afford a
    -- `last_four`.
    code_hash      text,
    invited_email  text,

    -- What the approval screen pre-selects for a code invite, and what an email
    -- invite grants outright. An empty array is legal and means "decide at
    -- approval" — refusing it would push admins toward reflexively picking one.
    grants_roles   text[]       NOT NULL DEFAULT '{}',

    created_by     text         NOT NULL,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    expires_at     timestamptz  NOT NULL,
    revoked_at     timestamptz,

    -- NULL means unlimited within the window. Every redemption still lands in
    -- the pending queue, so a shared code admits nobody on its own.
    max_uses       integer,
    use_count      integer      NOT NULL DEFAULT 0,

    CONSTRAINT pk_workspace_invite PRIMARY KEY (id),
    CONSTRAINT ck_workspace_invite_id_prefix CHECK (id LIKE 'inv\\_%'),

    CONSTRAINT ck_workspace_invite_one_kind
        CHECK (num_nonnulls(code_hash, invited_email) = 1),

    CONSTRAINT ck_workspace_invite_expires_after_creation
        CHECK (expires_at > created_at),

    -- The same closed set `ck_role_binding_role_values` holds, checked here so
    -- an invitation cannot promise a role the binding table would refuse an
    -- hour later, at the moment somebody is being let in.
    CONSTRAINT ck_workspace_invite_roles_values
        CHECK (grants_roles <@ ARRAY['Owner', 'Reviewer', 'Viewer', 'Admin']::text[]),

    CONSTRAINT ck_workspace_invite_max_uses_positive
        CHECK (max_uses IS NULL OR max_uses > 0),
    CONSTRAINT ck_workspace_invite_use_count_not_negative
        CHECK (use_count >= 0),

    CONSTRAINT fk_workspace_invite_workspace_id
        FOREIGN KEY (workspace_id) REFERENCES access.workspace (id),
    CONSTRAINT fk_workspace_invite_created_by
        FOREIGN KEY (created_by) REFERENCES access."user" (id)
);
"""

CREATE_INVITE_INDEXES = (
    # Globally unique, across every tenant, and that is required rather than
    # tidy: a six-character code is resolved to a workspace by the code alone,
    # so two workspaces holding the same live code would make the answer
    # ambiguous. Partial, because an email invite has no code and several may
    # legitimately have none.
    """
    CREATE UNIQUE INDEX uq_workspace_invite_code_hash
        ON access.workspace_invite (code_hash)
        WHERE code_hash IS NOT NULL
    """,
    # The claim lookup at registration: every live seat reserved for one
    # address. Not unique — the same person may be expected in two workspaces.
    """
    CREATE INDEX ix_workspace_invite_invited_email
        ON access.workspace_invite (invited_email)
        WHERE invited_email IS NOT NULL
    """,
    # The admin list, newest first.
    """
    CREATE INDEX ix_workspace_invite_workspace_id_created_at
        ON access.workspace_invite (workspace_id, created_at DESC)
    """,
)

#: The second exception policy. `FOR SELECT` and nothing else: a lobby caller
#: reads an invitation to find out which workspace it belongs to, and every
#: write that follows happens under that workspace's ordinary tenant context.
#:
#: The predicate names the presented secret rather than the caller, which is
#: what makes an unfiltered `SELECT *` harmless here — it returns the one row
#: the caller could already have named, or none.
CREATE_INVITE_REDEEM_POLICY = f"""
CREATE POLICY invite_redeem ON access.workspace_invite
    FOR SELECT TO {APP_ROLE}
    USING (code_hash = current_setting('app.invite_code_hash', true)
           OR invited_email = current_setting('app.invite_email', true));
"""

DROP_INVITE_REDEEM_POLICY = (
    "DROP POLICY IF EXISTS invite_redeem ON access.workspace_invite;"
)


# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------

#: `history_action_registry` is written by migrations and only by migrations
#: (D-51 grants `prope_app` SELECT alone), which is what makes ADR-0038's
#: un-invalidated cache of it safe.
ADD_INVITE_ACTIONS = """
INSERT INTO history.history_action_registry
    (action, target_type, detail_keys, requires_reason, writing_module)
VALUES
    ('invite_created',         'invite', '{}',            false, 'access-control'),
    ('invite_revoked',         'invite', '{}',            false, 'access-control'),
    ('member_join_requested',  'member', '{invite_id}',   false, 'access-control'),
    ('member_join_approved',   'member', '{}',            false, 'access-control'),
    ('member_join_rejected',   'member', '{}',            false, 'access-control');
"""

DROP_INVITE_ACTIONS = """
DELETE FROM history.history_action_registry
 WHERE action IN (
    'invite_created',
    'invite_revoked',
    'member_join_requested',
    'member_join_approved',
    'member_join_rejected'
 );
"""


def upgrade() -> None:
    assume_migrate_role()

    op.execute(DROP_SESSION_WORKSPACE_NOT_NULL)
    op.execute(CREATE_SESSION_LOBBY_POLICY)
    op.execute(CREATE_SESSION_LOBBY_INDEX)

    for statement in WIDEN_MEMBER_STATUS:
        op.execute(statement)

    op.execute(CREATE_WORKSPACE_INVITE)
    for statement in CREATE_INVITE_INDEXES:
        op.execute(statement)

    # Same revision as the table. The window between a table existing and its
    # policy existing is a window in which prope_app reads across tenants.
    enable_tenant_rls("access", "workspace_invite")
    op.execute(CREATE_INVITE_REDEEM_POLICY)

    # No DELETE, for `api_key`'s reason exactly: a deleted invitation would
    # orphan the `invite_created` event that names it, in a table nothing can
    # remove the event from. Revocation is a timestamp.
    grant_table(
        "access", "workspace_invite", app_privileges=["SELECT", "INSERT", "UPDATE"]
    )

    op.execute(ADD_INVITE_ACTIONS)

    reset_role()


def downgrade() -> None:
    """Refuses while an invite event exists — `history_event` has no DELETE (PH-02)."""
    assume_migrate_role()

    op.execute(DROP_INVITE_ACTIONS)

    op.execute(DROP_INVITE_REDEEM_POLICY)
    op.execute("DROP POLICY IF EXISTS workspace_invite_tenant ON access.workspace_invite")
    op.execute("DROP TABLE IF EXISTS access.workspace_invite")

    for statement in NARROW_MEMBER_STATUS:
        op.execute(statement)

    op.execute(DROP_SESSION_LOBBY_INDEX)
    op.execute(DROP_SESSION_LOBBY_POLICY)
    op.execute(DELETE_LOBBY_SESSIONS)
    op.execute(RESTORE_SESSION_WORKSPACE_NOT_NULL)

    reset_role()
