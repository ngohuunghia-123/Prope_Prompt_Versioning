"""the registry schema, its two tables, BR-03's constraint, and the search trigger

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-11

Four guarantees ride in this revision and none of them is application code.

**BR-03 is a composite foreign key, not an `if`.** `prompt_property` carries a
STORED generated column that is the literal `'Approved'` whenever the released
pointer is set and NULL whenever it is not, and the pointer is a two-column
foreign key into `revision (version_id, status)`. `MATCH SIMPLE` skips the check
entirely when either column is NULL, which is why ADR-0009's separate
`clear_released_revision` command needs no carve-out in the constraint. A `Draft`
target is refused by the engine, and so is demoting a released revision's status.
The same shape revision 0005 uses for `fk_history_event_action`.

**Append-only on `revision` is a PRIVILEGE.** T-020 recorded that the table
cannot take ADR-0025's treatment wholesale because INT-012 must move `status`.
Column-level `GRANT UPDATE (status)` is the honest form of that: the one column a
command may move is the only one granted, and `prope_app` holds no DELETE at all.

**`search_text` is maintained by a trigger, in the same transaction as the
change** (ADR-0048). Drift is silent and wrong in the unsafe direction — a body
edited without the document rewritten makes the prompt un-findable by its own new
text, with no error and no failed query.

**Diacritic and case folding happens INSIDE the trigger** ([[A-150]], ADR-0053).
`unaccent()` is STABLE rather than IMMUTABLE, so an index expression would need a
wrapper marked IMMUTABLE that is not; only the derived column is folded, and
`title`, `purpose` and every revision body are stored untouched.

**The document includes the model name, which the lock's field list omits.**
AC-10 requires `'refund'` to return `support/refund-classifier`, and ADR-0048's
case against `tsvector` rests on exactly that query — its parser reads
`namespace/name` as a file path. A document that could not answer it would fail
the acceptance criterion the ADR was written to protect.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_EXTENSIONS = (
    "CREATE EXTENSION pg_trgm WITH SCHEMA registry",
    "CREATE EXTENSION unaccent WITH SCHEMA registry",
)

DROP_EXTENSIONS = (
    "DROP EXTENSION IF EXISTS unaccent",
    "DROP EXTENSION IF EXISTS pg_trgm",
)

CREATE_PROMPT_PROPERTY = """
CREATE TABLE registry.prompt_property (
    id                       text         NOT NULL,
    workspace_id             text         NOT NULL,
    namespace                text         NOT NULL,
    name                     text         NOT NULL,
    title                    text         NOT NULL,
    purpose                  text         NOT NULL DEFAULT '',
    owner_id                 text         NOT NULL,
    access_level             text         NOT NULL DEFAULT 'private',
    status                   text         NOT NULL DEFAULT 'active',
    tags                     text[]       NOT NULL DEFAULT '{}',
    released_version_id      text,
    released_at              timestamptz,
    search_text              text         NOT NULL DEFAULT '',
    created_at               timestamptz  NOT NULL DEFAULT now(),
    updated_at               timestamptz  NOT NULL DEFAULT now(),

    released_revision_status text
        GENERATED ALWAYS AS (
            CASE WHEN released_version_id IS NULL THEN NULL ELSE 'Approved' END
        ) STORED,

    CONSTRAINT pk_prompt_property PRIMARY KEY (id),
    CONSTRAINT uq_prompt_property_namespace UNIQUE (workspace_id, namespace, name),
    CONSTRAINT ck_prompt_property_id_prefix CHECK (id LIKE 'prm\\_%'),
    CONSTRAINT ck_prompt_property_namespace_shape
        CHECK (namespace ~ '^[a-z0-9][a-z0-9._-]{0,62}$'),
    CONSTRAINT ck_prompt_property_name_shape
        CHECK (name ~ '^[a-z0-9][a-z0-9._-]{0,62}$'),
    CONSTRAINT ck_prompt_property_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT ck_prompt_property_title_length CHECK (char_length(title) <= 200),
    CONSTRAINT ck_prompt_property_purpose_length CHECK (char_length(purpose) <= 2000),
    CONSTRAINT ck_prompt_property_access_level_values
        CHECK (access_level IN ('private', 'workspace')),
    CONSTRAINT ck_prompt_property_status_values
        CHECK (status IN ('active', 'retired')),
    CONSTRAINT ck_prompt_property_tags_bounded CHECK (cardinality(tags) <= 20),
    CONSTRAINT ck_prompt_property_release_is_whole
        CHECK ((released_version_id IS NULL) = (released_at IS NULL))
);
"""

CREATE_REVISION = """
CREATE TABLE registry.revision (
    version_id          text         NOT NULL,
    workspace_id        text         NOT NULL,
    prompt_id           text         NOT NULL,
    revision_number     integer      NOT NULL,
    body                text         NOT NULL,
    provider_config_id  text,
    upstream_model      text,
    parameters          jsonb        NOT NULL DEFAULT '{}'::jsonb,
    fallback_answer     text,
    change_summary      text         NOT NULL,
    author_id           text         NOT NULL,
    status              text         NOT NULL DEFAULT 'Draft',
    created_at          timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_revision PRIMARY KEY (version_id),
    CONSTRAINT uq_revision_prompt_id UNIQUE (prompt_id, revision_number),
    CONSTRAINT uq_revision_version_id UNIQUE (version_id, status),
    CONSTRAINT ck_revision_id_prefix CHECK (version_id LIKE 'rev\\_%'),
    CONSTRAINT ck_revision_number_positive CHECK (revision_number > 0),
    CONSTRAINT ck_revision_body_length CHECK (char_length(body) <= 32768),
    CONSTRAINT ck_revision_change_summary_not_blank CHECK (btrim(change_summary) <> ''),
    CONSTRAINT ck_revision_change_summary_length CHECK (char_length(change_summary) <= 200),
    CONSTRAINT ck_revision_fallback_answer_length
        CHECK (fallback_answer IS NULL OR char_length(fallback_answer) <= 32768),
    CONSTRAINT ck_revision_status_values
        CHECK (status IN ('Draft', 'In review', 'Approved')),
    CONSTRAINT ck_revision_binding_is_whole
        CHECK ((provider_config_id IS NULL) = (upstream_model IS NULL)),

    CONSTRAINT fk_revision_prompt_id
        FOREIGN KEY (prompt_id)
        REFERENCES registry.prompt_property (id),

    CONSTRAINT fk_revision_provider_config_id
        FOREIGN KEY (provider_config_id)
        REFERENCES provider.provider_config (id)
);
"""

CREATE_RELEASED_POINTER_CONSTRAINT = """
ALTER TABLE registry.prompt_property
    ADD CONSTRAINT fk_prompt_property_released_version_id
        FOREIGN KEY (released_version_id, released_revision_status)
        REFERENCES registry.revision (version_id, status);
"""

CREATE_SEARCH_DOCUMENT = """
CREATE FUNCTION registry.search_document(
    p_prompt_id  text,
    p_namespace  text,
    p_name       text,
    p_title      text,
    p_purpose    text,
    p_tags       text[]
) RETURNS text
LANGUAGE sql
STABLE
AS $function$
    SELECT lower(registry.unaccent('registry.unaccent'::regdictionary, concat_ws(' ',
        p_namespace || '/' || p_name,
        p_namespace,
        p_name,
        p_title,
        p_purpose,
        array_to_string(coalesce(p_tags, '{}'::text[]), ' '),
        (SELECT r.body
           FROM registry.revision AS r
          WHERE r.prompt_id = p_prompt_id
          ORDER BY r.revision_number DESC
          LIMIT 1),
        (SELECT string_agg(r.change_summary, ' ' ORDER BY r.revision_number)
           FROM registry.revision AS r
          WHERE r.prompt_id = p_prompt_id)
    )));
$function$;
"""

CREATE_PROPERTY_TRIGGER = """
CREATE FUNCTION registry.property_rebuilds_search_text() RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.search_text := registry.search_document(
        NEW.id, NEW.namespace, NEW.name, NEW.title, NEW.purpose, NEW.tags
    );
    RETURN NEW;
END;
$function$;
"""

CREATE_REVISION_TRIGGER = """
CREATE FUNCTION registry.revision_rebuilds_search_text() RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    UPDATE registry.prompt_property AS p
       SET search_text = registry.search_document(
               p.id, p.namespace, p.name, p.title, p.purpose, p.tags
           ),
           updated_at = now()
     WHERE p.id = NEW.prompt_id;
    RETURN NULL;
END;
$function$;
"""

ATTACH_TRIGGERS = (
    """
    CREATE TRIGGER property_rebuilds_search_text
    BEFORE INSERT OR UPDATE OF title, purpose, tags, namespace, name
    ON registry.prompt_property
    FOR EACH ROW EXECUTE FUNCTION registry.property_rebuilds_search_text()
    """,
    """
    CREATE TRIGGER revision_rebuilds_search_text
    AFTER INSERT ON registry.revision
    FOR EACH ROW EXECUTE FUNCTION registry.revision_rebuilds_search_text()
    """,
)

FUNCTION_PRIVILEGES = (
    "registry.search_document(text, text, text, text, text, text[])",
    "registry.property_rebuilds_search_text()",
    "registry.revision_rebuilds_search_text()",
)

CREATE_INDEXES = (
    """
    CREATE INDEX ix_prompt_property_search_text
        ON registry.prompt_property USING gin (search_text registry.gin_trgm_ops)
    """,
    """
    CREATE INDEX ix_prompt_property_workspace_id_updated_at
        ON registry.prompt_property (workspace_id, updated_at DESC, id DESC)
    """,
    """
    CREATE INDEX ix_prompt_property_workspace_id_released_version_id
        ON registry.prompt_property (workspace_id, released_version_id)
        WHERE released_version_id IS NOT NULL
    """,
    """
    CREATE INDEX ix_prompt_property_workspace_id_owner_id
        ON registry.prompt_property (workspace_id, owner_id)
    """,
    """
    CREATE INDEX ix_revision_prompt_id_revision_number
        ON registry.revision (prompt_id, revision_number DESC)
    """,
    """
    CREATE INDEX ix_revision_workspace_id_provider_config_id
        ON registry.revision (workspace_id, provider_config_id)
        WHERE provider_config_id IS NOT NULL
    """,
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA registry AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA registry TO prope_app, prope_report")

    for statement in CREATE_EXTENSIONS:
        op.execute(statement)

    assume_migrate_role()

    op.execute(CREATE_PROMPT_PROPERTY)
    op.execute(CREATE_REVISION)
    op.execute(CREATE_RELEASED_POINTER_CONSTRAINT)

    op.execute(CREATE_SEARCH_DOCUMENT)
    op.execute(CREATE_PROPERTY_TRIGGER)
    op.execute(CREATE_REVISION_TRIGGER)
    for statement in ATTACH_TRIGGERS:
        op.execute(statement)

    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("registry", "prompt_property")
    enable_tenant_rls("registry", "revision")

    grant_table(
        "registry",
        "prompt_property",
        app_privileges=["SELECT", "INSERT", "UPDATE"],
    )

    grant_table("registry", "revision", app_privileges=["SELECT", "INSERT"])
    op.execute("GRANT UPDATE (status) ON registry.revision TO prope_app")

    for signature in FUNCTION_PRIVILEGES:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prope_app")

    reset_role()


def downgrade() -> None:
    assume_migrate_role()

    op.execute(
        "ALTER TABLE IF EXISTS registry.prompt_property "
        "DROP CONSTRAINT IF EXISTS fk_prompt_property_released_version_id"
    )
    op.execute("DROP TABLE IF EXISTS registry.revision")
    op.execute("DROP TABLE IF EXISTS registry.prompt_property")

    reset_role()

    for statement in DROP_EXTENSIONS:
        op.execute(statement)

    op.execute("DROP SCHEMA IF EXISTS registry CASCADE")
