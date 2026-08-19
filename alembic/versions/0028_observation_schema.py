"""The observation schema — ADR-0060's two tables, and the one that is not a call body

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-18

**These bodies are read, which is the whole reason they are not in
``ledger.call_body``.** ADR-0018 gives that table no reader by construction,
ADR-0039 excludes it from the backup, and the retention job deletes it. A
discovery inventory that lived there would silently empty itself, and the first
person to notice would be a customer whose screen went blank. ADR-0060 puts them
here instead, in a schema owned by a module that may check a permission — and
leaves ADR-0018 untouched.

**Two tables, and the second one is bounded on purpose.** ``observation`` is one
row per distinct prompt body per workspace; ``sighting`` is the occurrences. A
sighting whose ``body_hash`` matches the group's current one carries **no body**
and exists only to be counted — only a sighting that CHANGED the body keeps its
own copy. Without that rule this table is ``ledger.call_body`` under another name,
at the same volume, on the readable side of ADR-0018.

**``namespace`` is the column that makes the module safe** (ADR-0062 §3). It is
written from the consumer key's ``observe_namespace`` and it is what gives an
observation a container: who may read one product's ungoverned prompts is one
``access.namespace_grant``, evaluated by the ordinary ``may()`` union. Before it,
prompt-observation's SR-2 recorded a real widening with no fix available inside
the module — an observation had no owner, so BR-01 had nothing to key on.

**No foreign keys leave this schema.** ``call_id`` is a value, not a reference
into ``ledger.call_record``; ``adopted_prompt_id`` is a value, not a reference into
``registry.prompt_property``. Both follow the rule ``actor_id`` and ``target_id``
already follow: a constraint would point this module's schema at another module's
table, across an edge the module map does not draw.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: ``ck_observation_namespace_shape`` is byte-identical to
#: ``ck_prompt_property_namespace_shape``. It has to be: an observation adopted
#: into a namespace the registry would refuse is an inventory row nobody can act
#: on, and the CHECK is what makes that impossible at the moment of writing rather
#: than at the moment of adopting.
CREATE_OBSERVATION = """
CREATE TABLE observation.observation (
    id                   text         NOT NULL,
    workspace_id         text         NOT NULL,
    namespace            text         NOT NULL,

    -- A-154's grouping key: a hash of the NORMALISED system message. `body_hash`
    -- is the exact hash of `current_body`, and the pair is what makes "the body
    -- changed on Tuesday" answerable — same fingerprint, different body_hash.
    fingerprint          text         NOT NULL,
    body_hash            text         NOT NULL,
    current_body         text         NOT NULL,

    -- The proposal's raw material, stored rather than recomputed: A-154 infers
    -- slots by diffing a group's members, and the diff needs the members.
    inferred_variables   text[]       NOT NULL DEFAULT '{}',

    sighting_count       bigint       NOT NULL DEFAULT 0,
    first_seen_at        timestamptz  NOT NULL,
    last_seen_at         timestamptz  NOT NULL,
    upstream_models      text[]       NOT NULL DEFAULT '{}',

    -- Adoption and dismissal are recorded HERE rather than as history events.
    -- A-102's precedent: A-014 makes every state change on a PROMPT PROPERTY an
    -- event, and an observation is not one. The moment it becomes a prompt,
    -- prompt-registry's own property_created / revision_created take over and the
    -- trail is unbroken from there.
    adopted_prompt_id    text,
    adopted_by           text,
    adopted_at           timestamptz,
    dismissed_by         text,
    dismissed_at         timestamptz,
    dismissal_reason     text,
    redacted_at          timestamptz,

    created_at           timestamptz  NOT NULL DEFAULT now(),
    updated_at           timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_observation PRIMARY KEY (id),
    CONSTRAINT ck_observation_id_prefix CHECK (id LIKE 'obs\\_%'),

    -- The grouping key IS the identity, per workspace. A second row for the same
    -- fingerprint would split one prompt's history in two and make the sighting
    -- count a lie, which is the number the whole inbox is sorted by.
    CONSTRAINT uq_observation_fingerprint UNIQUE (workspace_id, fingerprint),

    CONSTRAINT ck_observation_namespace_shape
        CHECK (namespace ~ '^[a-z0-9][a-z0-9._-]{0,62}$'),

    -- Each of the three lifecycle stamps is all-or-nothing. A row that named an
    -- adopting actor with no prompt, or a prompt with no actor, would be an
    -- inventory entry nobody can explain.
    CONSTRAINT ck_observation_adoption_is_whole
        CHECK (num_nonnulls(adopted_prompt_id, adopted_by, adopted_at) IN (0, 3)),
    CONSTRAINT ck_observation_dismissal_is_whole
        CHECK (num_nonnulls(dismissed_by, dismissed_at) IN (0, 2)),

    -- SR-4's delete and redact exist before the retention policy does (OQ-148).
    -- A redacted row keeps its counts and its dates and loses its text, so the
    -- inventory still says "there was something here" after somebody removes it.
    CONSTRAINT ck_observation_redacted_body_is_empty
        CHECK (redacted_at IS NULL OR current_body = '')
);
"""

#: A sighting that did not change the body carries no body. That is the bound, and
#: it is structural rather than a tuning knob — see the module docstring.
CREATE_SIGHTING = """
CREATE TABLE observation.sighting (
    id               text         NOT NULL,
    workspace_id     text         NOT NULL,
    observation_id   text         NOT NULL,
    body_hash        text         NOT NULL,

    -- NULL unless this sighting is the one that changed the body. The drift view
    -- reads exactly the non-NULL ones.
    body             text,

    -- VALUES, not foreign keys. `call_id` names a row in `ledger.call_record`
    -- that this module has no edge to and may not read; it is here so a person can
    -- carry one id between the inventory screen and the call-record screen.
    call_id          text         NOT NULL,
    consumer_key_id  text         NOT NULL,
    upstream_model   text         NOT NULL,
    occurred_at      timestamptz  NOT NULL,

    CONSTRAINT pk_sighting PRIMARY KEY (id),
    CONSTRAINT ck_sighting_id_prefix CHECK (id LIKE 'sig\\_%'),
    CONSTRAINT fk_sighting_observation
        FOREIGN KEY (observation_id) REFERENCES observation.observation (id) ON DELETE CASCADE
);
"""

#: Both lead with `workspace_id`, as every declared index in Prope does. The first
#: serves the inbox (newest first); the second serves the drift view, and is
#: partial because only body-changing sightings are ever read one by one.
CREATE_INDEXES = (
    """
    CREATE INDEX ix_observation_workspace_id_last_seen
        ON observation.observation (workspace_id, last_seen_at DESC)
    """,
    """
    CREATE INDEX ix_observation_workspace_id_namespace
        ON observation.observation (workspace_id, namespace)
    """,
    """
    CREATE INDEX ix_sighting_observation_id_occurred_at
        ON observation.sighting (workspace_id, observation_id, occurred_at DESC)
        WHERE body IS NOT NULL
    """,
)


def upgrade() -> None:
    # The bootstrap connection creates the schema, as revision 0012 does and for
    # the same reason: the migration role deliberately holds no database-level
    # CREATE privilege. AUTHORIZATION makes every object below migrate-owned,
    # which is what ADR-0035's owner bypass rests on.
    op.execute("CREATE SCHEMA observation AUTHORIZATION prope_migrate")

    # Issued by the BOOTSTRAP connection, before the role switch, because
    # `prope_migrate` owns the schema but a grant on it is still the owner's to
    # make and the bootstrap connection is the one holding the wider authority
    # here. Every other schema-creating revision does the same in the same place
    # (0005 through 0015).
    #
    # **Without this, `grant_table` below is not enough and the failure is not
    # obvious**: table-level privileges are checked only after schema USAGE, so
    # the application ends up with SELECT, INSERT, UPDATE and DELETE on two
    # tables it cannot reach at all. The error is `permission denied for schema
    # observation`, and on this module's write path it surfaces as an abandoned
    # observation and a counter — a silent, empty inbox rather than a crash.
    op.execute("GRANT USAGE ON SCHEMA observation TO prope_app, prope_report")

    assume_migrate_role()

    op.execute(CREATE_OBSERVATION)
    op.execute(CREATE_SIGHTING)
    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("observation", "observation")
    enable_tenant_rls("observation", "sighting")

    # DELETE is granted on both, unlike on `call_record` and `history_event`.
    # SR-4: this is the first table in Prope holding customer text that arrived
    # without an explicit submission, and the answer to "take that one out" must
    # not be a migration. The append-only rule belongs to the accountability
    # record, and an inventory is not one.
    grant_table(
        "observation",
        "observation",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )
    grant_table(
        "observation",
        "sighting",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )

    reset_role()


def downgrade() -> None:
    """Drops both tables and the schema.

    Unlike revisions 0020 and 0026 this does not refuse. Those guard
    ``ledger.call_record``, which is the accountability record and on which the
    application holds no DELETE at all; these two tables are an inventory the
    application may already delete from row by row (SR-4). Reverting the feature
    means discarding the inventory, and pretending otherwise would be theatre.
    """
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS observation.sighting")
    op.execute("DROP TABLE IF EXISTS observation.observation")
    reset_role()
    op.execute("DROP SCHEMA IF EXISTS observation")
