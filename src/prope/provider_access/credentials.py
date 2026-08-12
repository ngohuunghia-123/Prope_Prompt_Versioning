"""A-092 — the decrypted credential lives in a 60 s process-local cache and nowhere else."""

import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.provider_access import crypto
from prope.provider_access.domain import (
    Adapter,
    ConfigStatus,
    CredentialRecord,
    ProviderConfig,
    VerificationStatus,
)
from prope.provider_access.observability import credential_decrypt_seconds

__all__ = [
    "CACHE_TTL_SECONDS",
    "clear_cache",
    "forget",
    "load_config",
    "load_credential",
    "resolve_secret",
]

CACHE_TTL_SECONDS = 60.0

LOAD_CONFIG = text(
    """
    SELECT id, workspace_id, display_name, adapter, base_url, status,
           verification_status, interactive_concurrency, batch_concurrency
    FROM   provider.provider_config
    WHERE  id = :id
    """
)

LOAD_CREDENTIAL = text(
    """
    SELECT id, provider_config_id, ciphertext, nonce, wrapped_dek, kek_version, last_four
    FROM   provider.credential
    WHERE  provider_config_id = :provider_config_id
    """
)

_cache: dict[str, tuple[str, float]] = {}


def clear_cache() -> None:
    _cache.clear()


def forget(provider_config_id: str) -> None:
    _cache.pop(provider_config_id, None)


async def load_config(db: AsyncSession, provider_config_id: str) -> ProviderConfig | None:
    row = (await db.execute(LOAD_CONFIG, {"id": provider_config_id})).one_or_none()
    if row is None:
        return None
    return ProviderConfig(
        id=row.id,
        workspace_id=row.workspace_id,
        display_name=row.display_name,
        adapter=Adapter(row.adapter),
        base_url=row.base_url,
        status=ConfigStatus(row.status),
        verification_status=VerificationStatus(row.verification_status),
        interactive_concurrency=row.interactive_concurrency,
        batch_concurrency=row.batch_concurrency,
    )


async def load_credential(
    db: AsyncSession, provider_config_id: str
) -> CredentialRecord | None:
    row = (
        await db.execute(LOAD_CREDENTIAL, {"provider_config_id": provider_config_id})
    ).one_or_none()
    if row is None:
        return None
    return CredentialRecord(
        id=row.id,
        provider_config_id=row.provider_config_id,
        ciphertext=row.ciphertext,
        nonce=row.nonce,
        wrapped_dek=row.wrapped_dek,
        kek_version=row.kek_version,
        last_four=row.last_four,
    )


def cached_secret(provider_config_id: str, *, now: float | None = None) -> str | None:
    entry = _cache.get(provider_config_id)
    if entry is None:
        return None
    secret, expires_at = entry
    if (now if now is not None else time.monotonic()) >= expires_at:
        _cache.pop(provider_config_id, None)
        return None
    return secret


async def resolve_secret(db: AsyncSession, provider_config_id: str) -> str:
    started = time.perf_counter()
    hit = cached_secret(provider_config_id)
    if hit is not None:
        credential_decrypt_seconds.labels(cache="hit").observe(time.perf_counter() - started)
        return hit

    record = await load_credential(db, provider_config_id)
    if record is None:
        raise crypto.KeyUnavailable(
            f"provider configuration {provider_config_id} carries no credential row"
        )

    secret = crypto.decrypt(record)
    _cache[provider_config_id] = (secret, time.monotonic() + CACHE_TTL_SECONDS)
    credential_decrypt_seconds.labels(cache="miss").observe(time.perf_counter() - started)
    return secret
