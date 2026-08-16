"""evaluation.dataset_attachment — which yardsticks a prompt has chosen

**A dataset is a reusable bundle of eval cases; a suite is what actually
measures a revision.** They are deliberately different objects. ``eval_suite``
is per-prompt, versioned and immutable because A-004 needs the *same* yardstick
to measure both revisions in a comparison — so a library dataset can never be
the thing a run reads, or editing it would silently re-explain every past run.
This table is the join between the two: a row says *this prompt has chosen this
dataset*, and ``materialised_suite_id`` records which immutable suite version
that choice was last turned into.

**Ticking is cheap, running is what costs.** A row here is written the moment
somebody ticks a dataset in the eval workspace, before any provider call
happens. ``POST /prompts/{id}/eval-runs/from-attachments`` is what materialises:
it fingerprints the dataset's cases and assertions, reuses
``materialised_suite_id`` when the fingerprint still matches, and writes a new
suite version only when the dataset has actually changed. Ten runs of an
unchanged dataset therefore produce one suite version rather than ten, and the
run history still names an immutable ``suite_id`` either way.

**``dataset_id`` is a value, not a foreign key, and it names two different
kinds of thing.** A ``builtin:<slug>@<version>`` id resolves to the read-only
catalogue that ships inside ``prope.evaluation.common_datasets`` — those sets
must be byte-identical in every workspace, and RLS (ADR-0035, ADR-0045) has no
such thing as a global row, so they live in the image rather than in Postgres.
A ``dst_`` id resolves to a workspace-owned row in a table that does not exist
yet (step 4b). The shape CHECK below admits exactly those two forms, which is
what keeps a typo out without inventing a foreign key to a catalogue that has no
table. This is the posture ``actor_id`` and ``prompt_property.namespace``
already take.

**``prope_app`` holds DELETE here, which no history table grants.** An
attachment is current-state configuration — the same kind of thing as a folder
label — and unticking a dataset by mistake during registration should not be a
support ticket. Nothing audit-bearing is lost: the suite versions this
attachment materialised stay in ``eval_suite``, every run still names the exact
``suite_id`` it measured with, and ``history_event`` rows are untouched. What a
delete removes is a future intention, never a past fact.

**No history event**, for the reason ``registry.folder`` gives in 0016: an
attachment holds no revision, cannot be approved, cannot be released and cannot
serve a call. The traceability A-004 needs is carried by the run, which names
an immutable suite.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: ``uq_dataset_attachment_suite_name`` is the constraint that does the most
#: work here. ``write_suite_version`` versions a suite *by name*, so two
#: different datasets attached under the same name would silently merge into one
#: suite lineage and each run would overwrite the other's yardstick. The engine
#: refuses the second attachment rather than the application noticing.
#:
#: ``ck_dataset_attachment_materialisation_is_whole`` is the same both-halves-or-
#: neither shape ``ck_revision_binding_is_whole`` uses: a suite id with no
#: fingerprint could never be checked for staleness, and a fingerprint with no
#: suite id names nothing.
CREATE_DATASET_ATTACHMENT = """
CREATE TABLE evaluation.dataset_attachment (
    workspace_id             text         NOT NULL,
    prompt_id                text         NOT NULL,
    dataset_id               text         NOT NULL,
    suite_name               text         NOT NULL,
    materialised_suite_id    text,
    materialised_fingerprint text,
    attached_by              text         NOT NULL,
    attached_at              timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_dataset_attachment
        PRIMARY KEY (workspace_id, prompt_id, dataset_id),
    CONSTRAINT uq_dataset_attachment_suite_name
        UNIQUE (workspace_id, prompt_id, suite_name),

    CONSTRAINT ck_dataset_attachment_dataset_id_shape
        CHECK (dataset_id ~ '^(builtin:[a-z0-9][a-z0-9-]{0,62}@[0-9]{1,4}|dst_[0-9A-HJKMNP-TV-Z]{26})$'),
    CONSTRAINT ck_dataset_attachment_suite_name_not_blank
        CHECK (btrim(suite_name) <> ''),
    CONSTRAINT ck_dataset_attachment_suite_name_length
        CHECK (char_length(suite_name) <= 100),
    CONSTRAINT ck_dataset_attachment_suite_id_prefix
        CHECK (materialised_suite_id IS NULL OR materialised_suite_id LIKE 'evs\\_%'),
    CONSTRAINT ck_dataset_attachment_materialisation_is_whole
        CHECK (
            (materialised_suite_id IS NULL AND materialised_fingerprint IS NULL)
            OR (materialised_suite_id IS NOT NULL AND materialised_fingerprint IS NOT NULL)
        )
);
"""

#: The eval workspace lists a prompt's attachments on every page load, and the
#: primary key already leads with ``workspace_id, prompt_id`` — so the PK index
#: serves that read and no second index is bought here. RLS adds
#: ``workspace_id`` to the predicate of every query regardless.
INDEXES: tuple[str, ...] = ()


def upgrade() -> None:
    assume_migrate_role()

    op.execute(CREATE_DATASET_ATTACHMENT)
    for statement in INDEXES:
        op.execute(statement)

    enable_tenant_rls("evaluation", "dataset_attachment")

    # SELECT/INSERT/DELETE for tick and untick; UPDATE so a run can stamp which
    # suite version the attachment materialised into. Narrower than the table's
    # full surface would suggest: `prope_report` gets nothing beyond the read
    # `grant_table` gives it, because an attachment is configuration and not a
    # reporting fact.
    grant_table(
        "evaluation",
        "dataset_attachment",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )

    reset_role()


def downgrade() -> None:
    assume_migrate_role()

    op.execute("DROP TABLE IF EXISTS evaluation.dataset_attachment")

    reset_role()
