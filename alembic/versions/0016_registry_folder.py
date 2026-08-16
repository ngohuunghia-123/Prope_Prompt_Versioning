"""registry.folder — the declared half of a namespace

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-15

**A folder is a namespace with a label on it, and nothing more.** There is no
foreign key from ``prompt_property`` to this table and there must not be one.
A-021 makes ``namespace/name`` the address a consuming product calls, and
``prompt_property.namespace`` is a *value* — the same posture ``actor_id`` takes
in ``history_event``. A foreign key here would make the display label
load-bearing for the gateway's hot path, and it would mean a workspace could not
hold a prompt whose folder nobody has named yet.

The consequence is deliberate and it runs both ways:

* A prompt may sit in a namespace with no row here. The folder list is the
  **union** of the declared rows and the namespaces observed in
  ``prompt_property``, computed in ``repository.list_folders``, so a prompt
  created through the API still appears in a folder.
* A row here may have no prompts. That is the entire reason the table exists:
  the registration flow is *create the folder, open it, add the first prompt*,
  and a derived-only folder cannot be empty, so the second step used to 404.
* Deleting a row removes the **label**, never a prompt. The route refuses a
  non-empty folder anyway (``registry_folder_not_empty``) because a delete that
  reads destructive should not have to be explained.

**The primary key is ``(workspace_id, slug)``, not a minted id.** Every other
table in this schema keeps a ``prm_``/``rev_`` ULID because its rows are
referenced from elsewhere; nothing references a folder, and the slug is already
the natural key the URL, the model name and the tenant policy all use. A
surrogate id would be a second way to name the same drawer.

**No history event.** ``prompt_registry.commands`` opens by saying every write
in the module appends one; folder writes are the declared exception, recorded in
that docstring. A folder holds no revision, cannot be approved, cannot be
released and cannot serve a call, so it sits outside the traceability the
history vocabulary exists to carry — and a 32nd action in
``history.history_action_registry`` would be a migration, a lock-file edit and
four test edits bought for an audit trail of who made a drawer.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: ``ck_folder_slug_shape`` is byte-identical to
#: ``ck_prompt_property_namespace_shape``. It has to be: the slug *is* the
#: namespace, and a folder whose slug no prompt could ever carry would be a
#: drawer nothing fits in.
#:
#: ``name`` is free text and deliberately unconstrained beyond a length —
#: ADR-0053 ships a Vietnamese interface, so ``Hỗ trợ khách hàng`` is the
#: expected value and the ASCII shape lives on ``slug`` alone. The character cap
#: matches ``ck_prompt_property_title_length`` for the same reason that one is in
#: characters rather than bytes.
CREATE_FOLDER = """
CREATE TABLE registry.folder (
    workspace_id  text         NOT NULL,
    slug          text         NOT NULL,
    name          text         NOT NULL,
    description   text         NOT NULL DEFAULT '',
    color         text         NOT NULL,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_folder PRIMARY KEY (workspace_id, slug),
    CONSTRAINT ck_folder_slug_shape
        CHECK (slug ~ '^[a-z0-9][a-z0-9._-]{0,62}$'),
    CONSTRAINT ck_folder_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_folder_name_length CHECK (char_length(name) <= 200),
    CONSTRAINT ck_folder_description_length CHECK (char_length(description) <= 2000),
    CONSTRAINT ck_folder_color_shape CHECK (color ~ '^#[0-9a-f]{6}$')
);
"""


def upgrade() -> None:
    assume_migrate_role()

    op.execute(CREATE_FOLDER)

    enable_tenant_rls("registry", "folder")

    # DELETE is granted here and nowhere else in this schema. `prompt_property`
    # and `revision` are the asset — A-049 makes retirement terminal and ADR-0025
    # keeps revisions append-only by privilege — while a folder row is a label
    # whose removal loses nothing a prompt was carrying.
    grant_table(
        "registry",
        "folder",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )

    reset_role()


def downgrade() -> None:
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS registry.folder")
    reset_role()
