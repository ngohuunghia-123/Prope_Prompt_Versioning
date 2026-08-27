"""Router combos, and the frozen copy a revision keeps of one — ADR-0069

A revision binds one provider and one upstream model, and the gateway makes
exactly one upstream attempt. That single pair is a single point of failure for
every prompt released against it, and the only cover is the canned
``fallback_answer``. This revision adds the shape that lets a revision name an
ORDERED list instead, so the gateway can advance when an entry is unusable.

**Three tables, and the third is a copy of the second.** ``router_combo`` and
``router_combo_entry`` are the workspace's editable template.
``revision_route_entry`` is the frozen copy one revision keeps. They are separate
tables rather than one table plus a pointer, and that duplication IS the design:

**A route is a snapshot, for two independent reasons.** A-024 makes provider and
model part of the revision precisely so the approval record describes what ran;
a live reference would let one Settings edit re-route every released prompt with
no approval, which is BR-02 defeated by a foreign key. The second reason is
ADR-0012: the gateway's resolution cache is TTL-only and *nothing invalidates
it*, because no invalidation mechanism exists in a system where this module may
not call the gateway. A live reference would make a template edit a production
change the cache cannot see. Snapshotting is what keeps both true, and it is why
``revision_route_entry`` holds no UPDATE and no DELETE privilege at all.

**``route_combo_id`` on ``revision`` is a VALUE, not a foreign key.** The
template must stay deletable and renameable while every revision copied from it
survives untouched — the same rule ADR-0054 established for ``actor_id`` and
revision 0028 restated for ``call_id``. ``route_combo_name`` is snapshotted
beside it for the same reason ``readiness.report`` snapshots
``profile_snapshot``: the review screen must still read *"Routed via Primary EU
stack"* for a revision approved before somebody renamed the template.

**``ck_revision_binding_is_whole`` is NOT touched.** A routed revision leaves
both ``provider_config_id`` and ``upstream_model`` NULL, so ``(NULL IS NULL) =
(NULL IS NULL)`` holds and the constraint still means exactly what it has always
meant: a half-binding is refused. Its name appears in ``schemas.py``, in
``TrialRequest``, in the lock file and in tests, and rewriting what it says while
keeping its name is how a constraint stops meaning what people think it means.
The either/or rule ships as its own constraint beside it, named for what it does.

**The composite foreign key is BR-03's own trick, reused.**
``fk_prompt_property_released_version_id`` references ``revision (version_id,
status)`` so that only an ``Approved`` revision can be released — a rule enforced
by the engine rather than by application code. Here
``revision_route_entry.route_combo_id`` is NOT NULL and the key references
``revision (version_id, route_combo_id)``, so the engine refuses an orphan entry
AND refuses an entry attached to a pair-bound revision. It costs one unique index
on the parent, in the same shape as the existing ``uq_revision_version_id``.

**Why a child table and not a ``jsonb`` column on ``revision``.**
``DELETE /api/v1/providers/{id}`` is refused by ONE mechanism: the
``IntegrityError`` that ``fk_revision_provider_config_id`` produces, which
``provider_access.commands.delete_provider`` catches. INT-016 names that foreign
key as the mechanism and says in as many words that the alternative edge does not
exist. A ``jsonb`` array has no foreign key, and there is no legal way to add the
refusal back: provider-access reading ``registry.revision`` violates
schema-per-module, and provider-access asking prompt-registry is the forbidden
reverse edge. A ``jsonb`` route would therefore silently stop protecting a
provider that a released prompt depends on. Ordering, duplicate rejection and the
cardinality bound come free as constraints on top.

**``priority BETWEEN 1 AND 5`` IS the cardinality bound.** The primary key makes
priorities unique per combo, so the CHECK caps a combo at five entries without a
count column and without a trigger. Five because it also bounds a metric label at
five series, and because no workspace in the pilot configures more than five
providers. Raising it is one line here and one line in the gateway's label help.

**The template's foreign key to ``provider_config`` takes no ON DELETE action**,
so deleting a provider configuration is refused while a *template* names it, not
only while a revision does. ``ON DELETE CASCADE`` was the alternative and it is
worse in a way that surfaces late: it silently shortens a combo, every revision
created afterwards routes differently, and no event anywhere records that the
list changed.

Revision ID: 0048
Revises: 0047
Create Date: 2026-08-27
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0048"
down_revision: str | Sequence[str] | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: The workspace's editable template. ``updated_at`` is maintained by the command
#: layer rather than by a trigger, matching ``registry.prompt_property``.
CREATE_ROUTER_COMBO = r"""
CREATE TABLE registry.router_combo (
    id            text         NOT NULL,
    workspace_id  text         NOT NULL,
    display_name  text         NOT NULL,
    description   text         NOT NULL DEFAULT '',

    -- A VALUE, never a foreign key. ADR-0054.
    created_by    text         NOT NULL,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_router_combo PRIMARY KEY (id),
    CONSTRAINT ck_router_combo_id_prefix CHECK (id LIKE 'rtc\_%'),
    CONSTRAINT ck_router_combo_display_name_not_blank
        CHECK (btrim(display_name) <> ''),
    CONSTRAINT ck_router_combo_display_name_length
        CHECK (char_length(display_name) <= 200),
    CONSTRAINT ck_router_combo_description_length
        CHECK (char_length(description) <= 2000),

    -- Per workspace, because the name is how an author picks one in a Select.
    CONSTRAINT uq_router_combo_display_name UNIQUE (workspace_id, display_name)
);
"""

#: No ``id`` column: the primary key is ``(combo_id, priority)``, the same shape
#: ``registry.folder`` uses, so there is no id-prefix constraint to invent.
#:
#: ``uq_router_combo_entry_target`` refuses the same provider and model twice in
#: one list. That is a typo rather than a preference — the second attempt would
#: fail for exactly the reason the first did, so the rung is unreachable by
#: construction. The SAME provider with a DIFFERENT model is allowed and is a
#: real case: a cheaper model on a key that already works.
CREATE_ROUTER_COMBO_ENTRY = """
CREATE TABLE registry.router_combo_entry (
    combo_id            text     NOT NULL,
    workspace_id        text     NOT NULL,
    priority            integer  NOT NULL,
    provider_config_id  text     NOT NULL,
    upstream_model      text     NOT NULL,

    CONSTRAINT pk_router_combo_entry PRIMARY KEY (combo_id, priority),
    CONSTRAINT uq_router_combo_entry_target
        UNIQUE (combo_id, provider_config_id, upstream_model),
    CONSTRAINT ck_router_combo_entry_priority_bounded
        CHECK (priority BETWEEN 1 AND 5),
    CONSTRAINT ck_router_combo_entry_upstream_model_not_blank
        CHECK (btrim(upstream_model) <> ''),
    CONSTRAINT ck_router_combo_entry_upstream_model_length
        CHECK (char_length(upstream_model) <= 200),

    -- Deleting the template takes its rungs. They have no meaning apart from it,
    -- and every revision that ever used it holds its own frozen copy.
    CONSTRAINT fk_router_combo_entry_combo_id
        FOREIGN KEY (combo_id)
        REFERENCES registry.router_combo (id) ON DELETE CASCADE,

    -- No ON DELETE action: deleting a provider configuration is REFUSED while a
    -- template names it. See the module docstring.
    CONSTRAINT fk_router_combo_entry_provider_config_id
        FOREIGN KEY (provider_config_id)
        REFERENCES provider.provider_config (id)
);
"""

#: Provenance of the snapshot, on the revision itself. Both nullable, and whole
#: together — ``ck_revision_route_provenance_is_whole`` is what makes the LEFT
#: JOIN in ``commands.INSERT_REVISION`` catch an unknown combo id: a miss yields
#: a NULL display name against a non-NULL id, and the engine refuses the row.
ALTER_REVISION_ADD_ROUTE = """
ALTER TABLE registry.revision
    ADD COLUMN route_combo_id   text,
    ADD COLUMN route_combo_name text;
"""

ALTER_REVISION_ADD_ROUTE_CONSTRAINTS = """
ALTER TABLE registry.revision
    ADD CONSTRAINT ck_revision_route_provenance_is_whole
        CHECK ((route_combo_id IS NULL) = (route_combo_name IS NULL)),

    ADD CONSTRAINT ck_revision_binds_a_pair_or_a_route_never_both
        CHECK (NOT (provider_config_id IS NOT NULL AND route_combo_id IS NOT NULL)),

    ADD CONSTRAINT uq_revision_route_combo UNIQUE (version_id, route_combo_id);
"""

#: The frozen copy. Written once with its revision and never touched again —
#: ``grant_table`` below gives SELECT and INSERT and nothing else, which is
#: STRICTER than the parent ``registry.revision``, where ``status`` is updatable.
CREATE_REVISION_ROUTE_ENTRY = """
CREATE TABLE registry.revision_route_entry (
    version_id          text     NOT NULL,
    workspace_id        text     NOT NULL,

    -- NOT NULL is what makes the composite key below bite. See the docstring.
    route_combo_id      text     NOT NULL,

    priority            integer  NOT NULL,
    provider_config_id  text     NOT NULL,
    upstream_model      text     NOT NULL,

    CONSTRAINT pk_revision_route_entry PRIMARY KEY (version_id, priority),
    CONSTRAINT uq_revision_route_entry_target
        UNIQUE (version_id, provider_config_id, upstream_model),
    CONSTRAINT ck_revision_route_entry_priority_bounded
        CHECK (priority BETWEEN 1 AND 5),
    CONSTRAINT ck_revision_route_entry_upstream_model_not_blank
        CHECK (btrim(upstream_model) <> ''),
    CONSTRAINT ck_revision_route_entry_upstream_model_length
        CHECK (char_length(upstream_model) <= 200),

    -- An entry cannot exist unless its revision actually declares THIS combo.
    CONSTRAINT fk_revision_route_entry_revision
        FOREIGN KEY (version_id, route_combo_id)
        REFERENCES registry.revision (version_id, route_combo_id),

    -- The same refusal INT-016 already relies on, one table wider.
    CONSTRAINT fk_revision_route_entry_provider_config_id
        FOREIGN KEY (provider_config_id)
        REFERENCES provider.provider_config (id)
);
"""

#: The two ``(workspace_id, provider_config_id)`` indexes exist for the delete
#: path: when the foreign key refuses, the command reports how many templates and
#: revisions name the configuration, and it should not seq-scan to do it. The
#: listing index carries ``updated_at DESC`` because the Router settings page
#: renders most-recently-edited first.
CREATE_INDEXES = (
    """
    CREATE INDEX ix_router_combo_workspace_id_updated_at
        ON registry.router_combo (workspace_id, updated_at DESC, id DESC)
    """,
    """
    CREATE INDEX ix_router_combo_entry_workspace_id_provider_config_id
        ON registry.router_combo_entry (workspace_id, provider_config_id)
    """,
    """
    CREATE INDEX ix_revision_route_entry_workspace_id_provider_config_id
        ON registry.revision_route_entry (workspace_id, provider_config_id)
    """,
)


def upgrade() -> None:
    """Three tables, two revision columns, three constraints, three indexes.

    No ``CREATE SCHEMA``: ``registry`` has existed since revision 0008 and this
    module owns it. The tables live here rather than in ``provider`` because
    ordering provider-and-model pairs is a RESOLUTION decision, and
    provider-access names choosing the provider or the model as an explicit
    non-goal.
    """
    assume_migrate_role()

    op.execute(CREATE_ROUTER_COMBO)
    op.execute(CREATE_ROUTER_COMBO_ENTRY)

    # The columns and their unique key must land before the child table, whose
    # composite foreign key references them.
    op.execute(ALTER_REVISION_ADD_ROUTE)
    op.execute(ALTER_REVISION_ADD_ROUTE_CONSTRAINTS)

    op.execute(CREATE_REVISION_ROUTE_ENTRY)

    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("registry", "router_combo")
    enable_tenant_rls("registry", "router_combo_entry")
    enable_tenant_rls("registry", "revision_route_entry")

    # The template is editable, so it carries the full matrix.
    grant_table(
        "registry",
        "router_combo",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )

    # No UPDATE. `PUT /api/v1/router-combos/{id}` replaces the list by deleting
    # and reinserting inside one transaction, because an ordered list edited in
    # place is an ordered list somebody eventually corrupts.
    grant_table(
        "registry",
        "router_combo_entry",
        app_privileges=["SELECT", "INSERT", "DELETE"],
    )

    # Neither UPDATE nor DELETE. The snapshot is frozen by privilege rather than
    # by convention — the way `registry.revision` is, one notch tighter.
    grant_table("registry", "revision_route_entry", app_privileges=["SELECT", "INSERT"])

    reset_role()


def downgrade() -> None:
    """Drops the three tables, the three constraints and the two columns.

    Does not refuse, unlike revisions 0020 and 0026. Those guard
    ``ledger.call_record``, the accountability record. Nothing here is one: a
    frozen route is part of a revision's binding, and reverting the feature means
    those revisions bind nothing — a state the schema has always allowed and
    which the gateway already answers with ``provider_configuration_unusable``.
    Pretending the data could survive a revert would be theatre.
    """
    assume_migrate_role()

    op.execute("DROP TABLE IF EXISTS registry.revision_route_entry")
    op.execute("DROP TABLE IF EXISTS registry.router_combo_entry")
    op.execute("DROP TABLE IF EXISTS registry.router_combo")

    op.execute(
        "ALTER TABLE registry.revision "
        "DROP CONSTRAINT IF EXISTS ck_revision_route_provenance_is_whole, "
        "DROP CONSTRAINT IF EXISTS ck_revision_binds_a_pair_or_a_route_never_both, "
        "DROP CONSTRAINT IF EXISTS uq_revision_route_combo"
    )
    op.execute(
        "ALTER TABLE registry.revision "
        "DROP COLUMN IF EXISTS route_combo_id, "
        "DROP COLUMN IF EXISTS route_combo_name"
    )

    reset_role()
