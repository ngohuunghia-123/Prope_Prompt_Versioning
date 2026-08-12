"""the provider schema, its three tables, the tenant policies and the grant matrix

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-11
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_PROVIDER_CONFIG = """
CREATE TABLE provider.provider_config (
    id                       text         NOT NULL,
    workspace_id             text         NOT NULL,
    display_name             text         NOT NULL,
    adapter                  text         NOT NULL DEFAULT 'openai_compatible',
    base_url                 text         NOT NULL,
    status                   text         NOT NULL DEFAULT 'active',
    credential_id            text,
    created_by               text         NOT NULL,
    created_at               timestamptz  NOT NULL DEFAULT now(),
    updated_at               timestamptz  NOT NULL DEFAULT now(),
    last_verified_at         timestamptz,
    verification_status      text         NOT NULL DEFAULT 'pending',
    verification_error       text,
    interactive_concurrency  integer      NOT NULL DEFAULT 24,
    batch_concurrency        integer      NOT NULL DEFAULT 8,

    CONSTRAINT pk_provider_config PRIMARY KEY (id),
    CONSTRAINT uq_provider_config_display_name UNIQUE (workspace_id, display_name),
    CONSTRAINT ck_provider_config_id_prefix CHECK (id LIKE 'prv\\_%'),
    CONSTRAINT ck_provider_config_display_name_not_blank
        CHECK (btrim(display_name) <> ''),
    CONSTRAINT ck_provider_config_adapter_values
        CHECK (adapter IN ('openai_compatible')),
    CONSTRAINT ck_provider_config_status_values
        CHECK (status IN ('active', 'disabled')),
    CONSTRAINT ck_provider_config_verification_status_values
        CHECK (verification_status IN ('pending', 'passed', 'failed')),
    CONSTRAINT ck_provider_config_verified_row_is_whole CHECK (
        verification_status <> 'passed' OR last_verified_at IS NOT NULL
    ),
    CONSTRAINT ck_provider_config_base_url_scheme CHECK (base_url LIKE 'https://%'),
    CONSTRAINT ck_provider_config_interactive_concurrency_positive
        CHECK (interactive_concurrency > 0),
    CONSTRAINT ck_provider_config_batch_concurrency_positive
        CHECK (batch_concurrency > 0)
);
"""

CREATE_CREDENTIAL = """
CREATE TABLE provider.credential (
    id                  text         NOT NULL,
    workspace_id        text         NOT NULL,
    provider_config_id  text         NOT NULL,
    ciphertext          text         NOT NULL,
    nonce               text         NOT NULL,
    wrapped_dek         text         NOT NULL,
    kek_version         integer      NOT NULL,
    last_four           text         NOT NULL,
    created_by          text         NOT NULL,
    created_at          timestamptz  NOT NULL DEFAULT now(),
    rotated_at          timestamptz,

    CONSTRAINT pk_credential PRIMARY KEY (id),
    CONSTRAINT uq_credential_provider_config_id UNIQUE (provider_config_id),
    CONSTRAINT ck_credential_id_prefix CHECK (id LIKE 'crd\\_%'),
    CONSTRAINT ck_credential_last_four_length CHECK (char_length(last_four) = 4),
    CONSTRAINT ck_credential_kek_version_positive CHECK (kek_version > 0),

    CONSTRAINT fk_credential_provider_config_id
        FOREIGN KEY (provider_config_id)
        REFERENCES provider.provider_config (id) ON DELETE CASCADE
);
"""

CREATE_MODEL_CATALOGUE = """
CREATE TABLE provider.model_catalogue (
    id                  text         NOT NULL,
    workspace_id        text         NOT NULL,
    provider_config_id  text         NOT NULL,
    model_id            text         NOT NULL,
    display_name        text,
    source              text         NOT NULL,
    supports_streaming  boolean      NOT NULL DEFAULT true,
    available           boolean      NOT NULL DEFAULT true,
    first_seen_at       timestamptz  NOT NULL DEFAULT now(),
    last_seen_at        timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_model_catalogue PRIMARY KEY (id),
    CONSTRAINT uq_model_catalogue_model_id UNIQUE (provider_config_id, model_id),
    CONSTRAINT ck_model_catalogue_id_prefix CHECK (id LIKE 'mdl\\_%'),
    CONSTRAINT ck_model_catalogue_model_id_not_blank CHECK (btrim(model_id) <> ''),
    CONSTRAINT ck_model_catalogue_source_values
        CHECK (source IN ('discovered', 'manual')),

    CONSTRAINT fk_model_catalogue_provider_config_id
        FOREIGN KEY (provider_config_id)
        REFERENCES provider.provider_config (id) ON DELETE CASCADE
);
"""

CREATE_INDEXES = (
    """
    CREATE INDEX ix_provider_config_workspace_id_status
        ON provider.provider_config (workspace_id, status)
    """,
    """
    CREATE INDEX ix_model_catalogue_workspace_id_provider_config_id
        ON provider.model_catalogue (workspace_id, provider_config_id, model_id)
    """,
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA provider AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA provider TO prope_app, prope_report")

    assume_migrate_role()

    op.execute(CREATE_PROVIDER_CONFIG)
    op.execute(CREATE_CREDENTIAL)
    op.execute(CREATE_MODEL_CATALOGUE)

    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("provider", "provider_config")
    enable_tenant_rls("provider", "credential")
    enable_tenant_rls("provider", "model_catalogue")

    grant_table(
        "provider",
        "provider_config",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )
    grant_table(
        "provider",
        "credential",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
        report_select=False,
    )
    grant_table(
        "provider",
        "model_catalogue",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )

    reset_role()


def downgrade() -> None:
    assume_migrate_role()

    for table in ("model_catalogue", "credential", "provider_config"):
        op.execute(f"DROP TABLE IF EXISTS provider.{table}")

    op.execute("DROP SCHEMA IF EXISTS provider CASCADE")
    reset_role()
