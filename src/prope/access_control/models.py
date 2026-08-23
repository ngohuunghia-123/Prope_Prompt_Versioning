"""The eight `access` tables as Core `Table` objects. **Not the source of truth.**

Revision 0006 is (D-04, A-128). `create_all` is never called and these objects
are never queried through — every statement in this package is a module-level
`text()` constant, for the reasons `prope.db.session` gives.

Their only consumer is
`tests/architecture/test_schema_invariants.py::test_every_declared_access_model_matches_a_live_table`,
which asserts that every column declared here exists live and that the count of
declared tables is exactly nine. That makes this file a **drift guard**: a
migration that renamed a column without updating the package fails here, and a
tenth table added to the module fails the pinned count, which is a visible edit
rather than a silent widening.

**The count moved from eight to nine with revision 0022**, and that is the guard
working rather than the guard being worked around: `workspace_invite` is a real
widening of what this schema holds, so the number that had to be edited by hand is
exactly the signal it was put there to produce.

Constraints and defaults are deliberately **not** restated. A `CHECK` written
twice is a `CHECK` that can disagree with itself, and the engine owns every one
of them — see `prope.call_ledger.models`, which made the same choice first.
"""

from sqlalchemy import ARRAY, Boolean, Column, DateTime, Integer, Table, Text

from prope.db.metadata import metadata

#: Every timestamp in the schema. Never a naive one: a naive value compared
#: against a `timestamptz` is read against the server's time zone, and
#: `expires_at` is the column where that would silently extend a session.
TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "access"

workspace = Table(
    "workspace",
    metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("slug", Text, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

#: `user` is quoted everywhere it appears in SQL — it is a reserved word, and
#: `access.user` unquoted parses as the `USER` keyword under a schema qualifier
#: in enough contexts to be a trap. SQLAlchemy quotes it for us here; the raw
#: statements in this package write `access."user"` by hand.
user = Table(
    "user",
    metadata,
    Column("id", Text, primary_key=True),
    #: Nullable ONLY so a tombstone can clear them (ADR-0054). Revision 0006's
    #: two CHECKs make every half-tombstoned state unreachable, so nullable in
    #: the column is not nullable in practice for an active account.
    Column("email", Text),
    Column("display_name", Text),
    Column("password_hash", Text),
    Column("must_change_password", Boolean, nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("last_login_at", TIMESTAMPTZ),
    Column("tombstoned_at", TIMESTAMPTZ),
    Column("tombstoned_by", Text),
    schema=SCHEMA,
)

session = Table(
    "session",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    #: Nullable since revision 0022 (ADR-0056). A NULL is the **lobby**: a live
    #: session whose owner belongs to no workspace yet, or belongs to several and
    #: has not chosen. Such a row is invisible to `prope_app` under the ordinary
    #: tenant policy — NULL is not equal to anything — so it is reachable only
    #: through `session_lobby`, keyed on `app.user_id`, and through
    #: `access.lookup_session`, which was always SECURITY DEFINER and therefore
    #: never met a policy at all.
    Column("workspace_id", Text),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("expires_at", TIMESTAMPTZ, nullable=False),
    Column("last_seen_at", TIMESTAMPTZ, nullable=False),
    Column("user_agent_hash", Text),
    schema=SCHEMA,
)

workspace_member = Table(
    "workspace_member",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("user_id", Text, primary_key=True),
    Column("added_by", Text, nullable=False),
    Column("added_at", TIMESTAMPTZ, nullable=False),
    Column("status", Text, nullable=False),
    schema=SCHEMA,
)

#: `role` is part of the primary key, and that is A-111 as a constraint: a schema
#: with one role per member could not represent the union AC-3 asserts.
role_binding = Table(
    "role_binding",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("user_id", Text, primary_key=True),
    Column("role", Text, primary_key=True),
    Column("granted_by", Text, nullable=False),
    Column("granted_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

role_permission = Table(
    "role_permission",
    metadata,
    Column("role", Text, primary_key=True),
    Column("action", Text, primary_key=True),
    schema=SCHEMA,
)

#: `prompt_id` is a VALUE and there is no `ForeignKey` on it — an FK would point
#: this schema at prompt-registry's table in the forbidden direction (ADR-0020),
#: and `test_no_foreign_key_leaves_the_schema` would catch it if the direction
#: rule ever stopped being enough.
prompt_grant = Table(
    "prompt_grant",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("prompt_id", Text, primary_key=True),
    Column("grantee_user_id", Text, primary_key=True),
    Column("level", Text, nullable=False),
    Column("granted_by", Text, nullable=False),
    Column("granted_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

api_key = Table(
    "api_key",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("name", Text, nullable=False),
    #: The SHA-256 digest, never the secret. Nothing in this row can reconstruct
    #: one (ADR-0021), which is the property that makes "a database dump yields
    #: no working key" a fact about the schema rather than about the code.
    Column("key_hash", Text, nullable=False),
    Column("last_four", Text, nullable=False),
    Column("scope_model_names", ARRAY(Text), nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("revoked_at", TIMESTAMPTZ),
    Column("last_used_at", TIMESTAMPTZ),
    schema=SCHEMA,
)

#: The ninth table, added by revision 0022 (ADR-0057). Shaped on `api_key` above,
#: because the two objects have the same security properties: a secret is minted,
#: shown once, and stored only as a digest.
#:
#: **There is no `last_four`, and its absence is the one place this table departs
#: from `api_key`'s shape.** A key's secret is long enough that four characters
#: identify a row without weakening it. An invite code is six characters, so four
#: of them would leave 62² guesses — the display convenience would have cost most
#: of the entropy. Nothing derived from the code is stored at all.
#:
#: `code_hash` and `invited_email` are mutually exclusive
#: (`ck_workspace_invite_one_kind`): a code invite admits whoever presents it to
#: the *pending* queue, an email invite reserves a seat for one address. One table
#: because the admin screen renders them as one list and they revoke through one
#: path.
workspace_invite = Table(
    "workspace_invite",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("code_hash", Text),
    Column("invited_email", Text),
    Column("grants_roles", ARRAY(Text), nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("expires_at", TIMESTAMPTZ, nullable=False),
    Column("revoked_at", TIMESTAMPTZ),
    Column("max_uses", Integer),
    Column("use_count", Integer, nullable=False),
    schema=SCHEMA,
)
