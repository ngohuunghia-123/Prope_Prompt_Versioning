"""evaluation.dataset / dataset_case — the workspace's own half of the library

Step 4a shipped the *attachment* and the read-only Chung catalogue that lives in
the image. This is the other half: datasets a workspace writes for itself, by
hand, by copying a shipped set, or by asking the agent to draft one from a
prompt body.

**These two tables are mutable, and that is the difference between a dataset and
a suite.** ``eval_suite`` has no UPDATE and no DELETE because a run's results are
only readable if the yardstick they were measured with still exists (A-004). A
dataset is not a yardstick — it is the *library object somebody edits*, and the
suite it produced is a copy taken at materialisation time. So editing a dataset
can never disturb a past run, and the fingerprint on ``dataset_attachment`` is
what turns an edit into a new suite version on the next run rather than a silent
change to an old one.

**Editing replaces the case list wholesale.** ``dataset_case`` grants DELETE for
that reason: a case editor that reconciled per-row would need stable case ids
across an edit, and a stable id across a changed input is a lie the fingerprint
would then have to see through. Delete-all-and-reinsert makes "what does this
dataset assert" a single readable question. Case ids are consequently NOT stable
across an edit, which is fine because nothing references them — ``case_result``
points at ``eval_case``, which is the copy inside the suite.

**``folder`` is a value and not a foreign key**, matching ``registry.folder``'s
posture in 0016 exactly: the slug is the namespace, a dataset may sit in a
folder nobody has named yet, and the display label must never be load-bearing.
An empty string is the *Chung* group, which is where the shipped catalogue
appears — a workspace row may sit there too, and then it is a workspace-wide set
this team wrote for itself.

**Deleting a dataset takes its attachments with it**, in the caller's
transaction. That is not a cascade the database performs — ``dataset_id`` is a
value, so there is no foreign key to cascade along — it is a deliberate act in
``commands.delete_dataset``. A retired *builtin* version leaves its attachments
behind because the id once resolved and the row is a record of that; a deleted
workspace dataset will never resolve again, so leaving a permanently broken tick
on every prompt that chose it is litter, not history. The suites and runs it
already produced are untouched.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: ``ck_dataset_folder_shape`` is byte-identical to ``ck_folder_slug_shape`` in
#: 0016 and to ``ck_prompt_property_namespace_shape``, with the empty string
#: additionally admitted for the Chung group. It has to match: the slug IS the
#: namespace, and a dataset filed under a slug no folder could ever carry would
#: be in a drawer that cannot be opened.
#:
#: ``ck_dataset_kind_values`` and ``ck_dataset_output_modality_values`` restate
#: enumerations that already exist in Python. They are here for the reason every
#: other CHECK in this schema is: the database is the only participant that sees
#: every write, including the ones a future migration or a psql session makes.
CREATE_DATASET = """
CREATE TABLE evaluation.dataset (
    id               text         NOT NULL,
    workspace_id     text         NOT NULL,
    folder           text         NOT NULL DEFAULT '',
    name             text         NOT NULL,
    description      text         NOT NULL DEFAULT '',
    kind             text         NOT NULL,
    output_modality  text         NOT NULL,
    case_count       integer      NOT NULL DEFAULT 0,
    created_by       text         NOT NULL,
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_dataset PRIMARY KEY (id),
    CONSTRAINT uq_dataset_name UNIQUE (workspace_id, name),
    CONSTRAINT ck_dataset_id_prefix CHECK (id LIKE 'dst\\_%'),
    CONSTRAINT ck_dataset_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_dataset_name_length CHECK (char_length(name) <= 100),
    CONSTRAINT ck_dataset_description_length CHECK (char_length(description) <= 2000),
    CONSTRAINT ck_dataset_folder_shape
        CHECK (folder = '' OR folder ~ '^[a-z0-9][a-z0-9._-]{0,62}$'),
    CONSTRAINT ck_dataset_kind_values
        CHECK (kind IN ('golden', 'regression', 'red-team')),
    CONSTRAINT ck_dataset_output_modality_values
        CHECK (output_modality IN ('text', 'structured')),
    CONSTRAINT ck_dataset_case_count_not_negative CHECK (case_count >= 0)
);
"""

#: ``uq_dataset_name`` is workspace-wide rather than per-folder, and the reason
#: is downstream: a dataset's name becomes the *suite name* when it is
#: materialised, and ``uq_dataset_attachment_suite_name`` already refuses two
#: datasets sharing one on a prompt. Making the library itself unique on name
#: means that refusal is something a person meets while naming a dataset — where
#: it is obvious what to do — instead of later, while ticking one.

#: Mirrors ``eval_case`` field for field, deliberately: materialisation copies
#: one into the other, and a shape that drifted between the two would turn a
#: copy into a translation.
CREATE_DATASET_CASE = """
CREATE TABLE evaluation.dataset_case (
    id               text         NOT NULL,
    workspace_id     text         NOT NULL,
    dataset_id       text         NOT NULL,
    ordinal          integer      NOT NULL,
    name             text         NOT NULL,
    input_messages   jsonb        NOT NULL,
    input_variables  jsonb        NOT NULL DEFAULT '{}'::jsonb,
    assertions       jsonb        NOT NULL DEFAULT '[]'::jsonb,
    created_at       timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_dataset_case PRIMARY KEY (id),
    CONSTRAINT uq_dataset_case_ordinal UNIQUE (dataset_id, ordinal),
    CONSTRAINT ck_dataset_case_id_prefix CHECK (id LIKE 'dsc\\_%'),
    CONSTRAINT ck_dataset_case_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_dataset_case_name_length CHECK (char_length(name) <= 200),
    CONSTRAINT ck_dataset_case_ordinal_positive CHECK (ordinal > 0),
    CONSTRAINT ck_dataset_case_input_messages_is_a_list
        CHECK (jsonb_typeof(input_messages) = 'array'),
    CONSTRAINT ck_dataset_case_assertions_is_a_list
        CHECK (jsonb_typeof(assertions) = 'array'),

    CONSTRAINT fk_dataset_case_dataset_id
        FOREIGN KEY (dataset_id) REFERENCES evaluation.dataset (id) ON DELETE CASCADE
);
"""

#: A real foreign key here, where ``dataset_attachment.dataset_id`` has none.
#: The difference is that a case has no meaning apart from its dataset and both
#: rows are in this schema, whereas an attachment's ``dataset_id`` sometimes
#: names a file in the image. ``ON DELETE CASCADE`` is what makes deleting a
#: dataset one statement instead of two.

INDEXES: tuple[str, ...] = (
    # The tree lists the whole library on every page load, grouped by folder.
    "CREATE INDEX ix_dataset_folder ON evaluation.dataset (workspace_id, folder, name)",
    # The editor and materialisation both read one dataset's cases in order.
    "CREATE INDEX ix_dataset_case_dataset_id ON evaluation.dataset_case (dataset_id, ordinal)",
)


def upgrade() -> None:
    assume_migrate_role()

    op.execute(CREATE_DATASET)
    op.execute(CREATE_DATASET_CASE)
    for statement in INDEXES:
        op.execute(statement)

    enable_tenant_rls("evaluation", "dataset")
    enable_tenant_rls("evaluation", "dataset_case")

    # UPDATE and DELETE, which `eval_suite` and `eval_case` are deliberately
    # denied. A dataset is a library object somebody edits; a suite is the
    # immutable copy a run measured with. This table being mutable is what lets
    # the other one stay append-only.
    grant_table(
        "evaluation", "dataset", app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"]
    )
    grant_table(
        "evaluation", "dataset_case", app_privileges=["SELECT", "INSERT", "DELETE"]
    )

    reset_role()


def downgrade() -> None:
    assume_migrate_role()

    op.execute("DROP TABLE IF EXISTS evaluation.dataset_case")
    op.execute("DROP TABLE IF EXISTS evaluation.dataset")

    reset_role()
