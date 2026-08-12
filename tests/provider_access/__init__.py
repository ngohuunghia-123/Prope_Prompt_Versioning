"""Shared factories for the ``provider`` schema's tests.

Everything here seeds through ``migrate_engine`` — the owner — so the rows a test
needs exist independently of the privileges and policies under test. A test whose
subject is a command writes through the command.

``seed_credential`` encrypts through the real envelope rather than writing
plausible-looking strings, because every test that decrypts one is asserting
about ADR-0014 and a hand-written ciphertext would assert about nothing.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from ulid import ULID

from prope.provider_access import crypto
from tests.access_control import ADMIN_ID
from tests.unit import WORKSPACE_A, day

__all__ = [
    "ADMIN_ID",
    "CONFIG_ID",
    "CREDENTIAL_ID",
    "SECRET",
    "WORKSPACE_A",
    "day",
    "seed_catalogue_entry",
    "seed_credential",
    "seed_provider_config",
]

CONFIG_ID = "prv_01J000000000000000PROV1"

CREDENTIAL_ID = "crd_01J0000000000000000CRD1"

SECRET = "sk-live-000000000000cafe"

INSERT_PROVIDER_CONFIG = text(
    """
    INSERT INTO provider.provider_config (
        id, workspace_id, display_name, adapter, base_url, status, credential_id,
        created_by, created_at, updated_at, last_verified_at, verification_status,
        verification_error, interactive_concurrency, batch_concurrency
    ) VALUES (
        :id, :workspace_id, :display_name, :adapter, :base_url, :status, :credential_id,
        :created_by, :created_at, :created_at, :last_verified_at, :verification_status,
        :verification_error, :interactive_concurrency, :batch_concurrency
    )
    """
)

INSERT_CREDENTIAL = text(
    """
    INSERT INTO provider.credential (
        id, workspace_id, provider_config_id, ciphertext, nonce, wrapped_dek,
        kek_version, last_four, created_by, created_at
    ) VALUES (
        :id, :workspace_id, :provider_config_id, :ciphertext, :nonce, :wrapped_dek,
        :kek_version, :last_four, :created_by, :created_at
    )
    """
)

INSERT_MODEL = text(
    """
    INSERT INTO provider.model_catalogue (
        id, workspace_id, provider_config_id, model_id, display_name, source,
        supports_streaming, available, first_seen_at, last_seen_at
    ) VALUES (
        :id, :workspace_id, :provider_config_id, :model_id, :display_name, :source,
        :supports_streaming, :available, :now, :now
    )
    """
)


async def _insert(migrate_engine: AsyncEngine, statement, values: dict[str, Any]) -> None:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        await connection.execute(statement, values)


async def seed_provider_config(
    migrate_engine: AsyncEngine,
    provider_config_id: str = CONFIG_ID,
    workspace_id: str = WORKSPACE_A,
    **overrides: Any,
) -> str:
    values: dict[str, Any] = {
        "id": provider_config_id,
        "workspace_id": workspace_id,
        "display_name": f"provider {provider_config_id[-4:]}",
        "adapter": "openai_compatible",
        "base_url": "https://provider.example/v1",
        "status": "active",
        "credential_id": CREDENTIAL_ID,
        "created_by": ADMIN_ID,
        "created_at": day(1),
        "last_verified_at": day(1),
        "verification_status": "passed",
        "verification_error": None,
        "interactive_concurrency": 24,
        "batch_concurrency": 8,
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_PROVIDER_CONFIG, values)
    return str(values["id"])


async def seed_credential(
    migrate_engine: AsyncEngine,
    secret: str = SECRET,
    credential_id: str = CREDENTIAL_ID,
    provider_config_id: str = CONFIG_ID,
    workspace_id: str = WORKSPACE_A,
) -> str:
    encrypted = crypto.encrypt(secret)
    await _insert(
        migrate_engine,
        INSERT_CREDENTIAL,
        {
            "id": credential_id,
            "workspace_id": workspace_id,
            "provider_config_id": provider_config_id,
            "ciphertext": encrypted.ciphertext,
            "nonce": encrypted.nonce,
            "wrapped_dek": encrypted.wrapped_dek,
            "kek_version": encrypted.kek_version,
            "last_four": encrypted.last_four,
            "created_by": ADMIN_ID,
            "created_at": day(1),
        },
    )
    return credential_id


async def seed_catalogue_entry(
    migrate_engine: AsyncEngine,
    model_id: str = "gpt-4o-mini",
    provider_config_id: str = CONFIG_ID,
    workspace_id: str = WORKSPACE_A,
    **overrides: Any,
) -> None:
    values: dict[str, Any] = {
        "id": f"mdl_{ULID()}",
        "workspace_id": workspace_id,
        "provider_config_id": provider_config_id,
        "model_id": model_id,
        "display_name": None,
        "source": "discovered",
        "supports_streaming": True,
        "available": True,
        "now": day(1),
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_MODEL, values)
