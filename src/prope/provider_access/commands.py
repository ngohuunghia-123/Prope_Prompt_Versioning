"""The writes INT-027 exposes. Each one appends its history event in the same transaction."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.errors import ErrorCode
from prope.provider_access import catalogue, credentials, crypto, events
from prope.provider_access.domain import (
    Adapter,
    CatalogueEntry,
    ConfigStatus,
    VerificationStatus,
)
from prope.provider_access.verification import Probe
from prope.session_auth import ManagementRefusal

__all__ = [
    "CREDENTIAL_ID_PREFIX",
    "PROVIDER_ID_PREFIX",
    "ProviderRow",
    "create_provider",
    "delete_provider",
    "load_row",
    "record_verification",
    "refresh_catalogue",
    "rotate_credential",
    "update_provider",
]

PROVIDER_ID_PREFIX = "prv_"

CREDENTIAL_ID_PREFIX = "crd_"

INSERT_PROVIDER_CONFIG = text(
    """
    INSERT INTO provider.provider_config (
        id, workspace_id, display_name, adapter, base_url, status, credential_id,
        created_by, created_at, updated_at, last_verified_at, verification_status,
        verification_error, interactive_concurrency, batch_concurrency
    ) VALUES (
        :id, :workspace_id, :display_name, :adapter, :base_url, 'active', :credential_id,
        :created_by, :now, :now, :last_verified_at, :verification_status,
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
        :kek_version, :last_four, :created_by, :now
    )
    """
)

REPLACE_CREDENTIAL = text(
    """
    UPDATE provider.credential
       SET ciphertext  = :ciphertext,
           nonce       = :nonce,
           wrapped_dek = :wrapped_dek,
           kek_version = :kek_version,
           last_four   = :last_four,
           rotated_at  = :now
     WHERE provider_config_id = :provider_config_id
    """
)

UPDATE_PROVIDER_CONFIG = text(
    """
    UPDATE provider.provider_config
       SET display_name            = coalesce(:display_name, display_name),
           base_url                = coalesce(:base_url, base_url),
           status                  = coalesce(:status, status),
           interactive_concurrency = coalesce(:interactive_concurrency, interactive_concurrency),
           batch_concurrency       = coalesce(:batch_concurrency, batch_concurrency),
           updated_at              = :now
     WHERE id = :id
    """
)

RECORD_VERIFICATION = text(
    """
    UPDATE provider.provider_config
       SET verification_status = :verification_status,
           verification_error  = :verification_error,
           last_verified_at    = :last_verified_at,
           updated_at          = :now
     WHERE id = :id
    """
)

RESET_VERIFICATION = text(
    """
    UPDATE provider.provider_config
       SET verification_status = 'pending',
           verification_error  = NULL,
           last_verified_at    = NULL,
           updated_at          = :now
     WHERE id = :id
    """
)

DELETE_PROVIDER_CONFIG = text("DELETE FROM provider.provider_config WHERE id = :id")

LOAD_ROW = text(
    """
    SELECT pc.id, pc.display_name, pc.adapter, pc.base_url, pc.status,
           pc.verification_status, pc.verification_error, pc.last_verified_at,
           pc.interactive_concurrency, pc.batch_concurrency, pc.created_by,
           pc.created_at, pc.updated_at, c.last_four
    FROM   provider.provider_config AS pc
    LEFT   JOIN provider.credential AS c ON c.provider_config_id = pc.id
    WHERE  pc.id = :id
    """
)

LIST_ROWS = text(
    """
    SELECT pc.id, pc.display_name, pc.adapter, pc.base_url, pc.status,
           pc.verification_status, pc.verification_error, pc.last_verified_at,
           pc.interactive_concurrency, pc.batch_concurrency, pc.created_by,
           pc.created_at, pc.updated_at, c.last_four
    FROM   provider.provider_config AS pc
    LEFT   JOIN provider.credential AS c ON c.provider_config_id = pc.id
    ORDER  BY pc.display_name
    """
)


@dataclass(frozen=True, slots=True)
class ProviderRow:
    id: str
    display_name: str
    adapter: Adapter
    base_url: str
    status: ConfigStatus
    verification_status: VerificationStatus
    verification_error: str | None
    last_verified_at: datetime | None
    interactive_concurrency: int
    batch_concurrency: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    credential_last_four: str | None


def _row(record: object) -> ProviderRow:
    return ProviderRow(
        id=record.id,
        display_name=record.display_name,
        adapter=Adapter(record.adapter),
        base_url=record.base_url,
        status=ConfigStatus(record.status),
        verification_status=VerificationStatus(record.verification_status),
        verification_error=record.verification_error,
        last_verified_at=record.last_verified_at,
        interactive_concurrency=record.interactive_concurrency,
        batch_concurrency=record.batch_concurrency,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        credential_last_four=record.last_four,
    )


def _not_found() -> ManagementRefusal:
    return ManagementRefusal(
        status_code=404, code=ErrorCode.NOT_FOUND, message="no such provider configuration"
    )


def _verification_failed(probe: Probe) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=422,
        code=ErrorCode.PROVIDER_VERIFICATION_FAILED,
        message="the provider configuration did not pass its verification probe",
        details={"reason": probe.outcome.reason, "detail": probe.outcome.detail},
    )


async def load_row(db: AsyncSession, provider_config_id: str) -> ProviderRow | None:
    record = (await db.execute(LOAD_ROW, {"id": provider_config_id})).one_or_none()
    return None if record is None else _row(record)


async def _reload(db: AsyncSession, provider_config_id: str) -> ProviderRow:
    row = await load_row(db, provider_config_id)
    if row is None:
        raise _not_found()
    return row


async def list_rows(db: AsyncSession) -> tuple[ProviderRow, ...]:
    return tuple(_row(record) for record in (await db.execute(LIST_ROWS)).all())


async def create_provider(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    display_name: str,
    base_url: str,
    credential: str,
    interactive_concurrency: int,
    batch_concurrency: int,
    probe: Probe,
    now: datetime,
) -> ProviderRow:
    if not probe.outcome.passed:
        raise _verification_failed(probe)

    encrypted = crypto.encrypt(credential)
    provider_config_id = f"{PROVIDER_ID_PREFIX}{ULID()}"
    credential_id = f"{CREDENTIAL_ID_PREFIX}{ULID()}"

    try:
        await db.execute(
            INSERT_PROVIDER_CONFIG,
            {
                "id": provider_config_id,
                "workspace_id": workspace_id,
                "display_name": display_name,
                "adapter": Adapter.OPENAI_COMPATIBLE.value,
                "base_url": base_url,
                "credential_id": credential_id,
                "created_by": actor_id,
                "now": now,
                "last_verified_at": probe.outcome.checked_at,
                "verification_status": VerificationStatus.PASSED.value,
                "verification_error": None,
                "interactive_concurrency": interactive_concurrency,
                "batch_concurrency": batch_concurrency,
            },
        )
    except IntegrityError as error:
        raise ManagementRefusal(
            status_code=409,
            code=ErrorCode.ALREADY_EXISTS,
            message="this workspace already has a provider configuration with that name",
            details={"display_name": display_name},
        ) from error

    await db.execute(
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
            "created_by": actor_id,
            "now": now,
        },
    )

    await catalogue.store_discovered(
        db,
        workspace_id=workspace_id,
        provider_config_id=provider_config_id,
        models=probe.models,
        now=now,
    )
    await events.provider_configured(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        provider_config_id=provider_config_id,
        occurred_at=now,
    )

    return await _reload(db, provider_config_id)


async def update_provider(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    provider_config_id: str,
    display_name: str | None,
    base_url: str | None,
    status: ConfigStatus | None,
    interactive_concurrency: int | None,
    batch_concurrency: int | None,
    now: datetime,
) -> ProviderRow:
    current = await load_row(db, provider_config_id)
    if current is None:
        raise _not_found()

    try:
        await db.execute(
            UPDATE_PROVIDER_CONFIG,
            {
                "id": provider_config_id,
                "display_name": display_name,
                "base_url": base_url,
                "status": status.value if status is not None else None,
                "interactive_concurrency": interactive_concurrency,
                "batch_concurrency": batch_concurrency,
                "now": now,
            },
        )
    except IntegrityError as error:
        raise ManagementRefusal(
            status_code=409,
            code=ErrorCode.ALREADY_EXISTS,
            message="this workspace already has a provider configuration with that name",
            details={"display_name": display_name},
        ) from error

    if base_url is not None and base_url != current.base_url:
        await db.execute(RESET_VERIFICATION, {"id": provider_config_id, "now": now})

    await events.provider_updated(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        provider_config_id=provider_config_id,
        occurred_at=now,
    )
    if status is ConfigStatus.DISABLED and current.status is not ConfigStatus.DISABLED:
        await events.provider_disabled(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            provider_config_id=provider_config_id,
            occurred_at=now,
        )

    return await _reload(db, provider_config_id)


async def rotate_credential(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    provider_config_id: str,
    credential: str,
    probe: Probe,
    now: datetime,
) -> ProviderRow:
    if await load_row(db, provider_config_id) is None:
        raise _not_found()
    if not probe.outcome.passed:
        raise _verification_failed(probe)

    encrypted = crypto.encrypt(credential)
    result = await db.execute(
        REPLACE_CREDENTIAL,
        {
            "provider_config_id": provider_config_id,
            "ciphertext": encrypted.ciphertext,
            "nonce": encrypted.nonce,
            "wrapped_dek": encrypted.wrapped_dek,
            "kek_version": encrypted.kek_version,
            "last_four": encrypted.last_four,
            "now": now,
        },
    )
    if result.rowcount == 0:
        credential_id = f"{CREDENTIAL_ID_PREFIX}{ULID()}"
        await db.execute(
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
                "created_by": actor_id,
                "now": now,
            },
        )

    await db.execute(
        RECORD_VERIFICATION,
        {
            "id": provider_config_id,
            "verification_status": VerificationStatus.PASSED.value,
            "verification_error": None,
            "last_verified_at": probe.outcome.checked_at,
            "now": now,
        },
    )
    await events.credential_rotated(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        provider_config_id=provider_config_id,
        occurred_at=now,
    )
    credentials.forget(provider_config_id)

    return await _reload(db, provider_config_id)


async def record_verification(
    db: AsyncSession,
    *,
    workspace_id: str,
    provider_config_id: str,
    probe: Probe,
    now: datetime,
) -> tuple[ProviderRow, int]:
    if await load_row(db, provider_config_id) is None:
        raise _not_found()

    await db.execute(
        RECORD_VERIFICATION,
        {
            "id": provider_config_id,
            "verification_status": (
                VerificationStatus.PASSED if probe.outcome.passed else VerificationStatus.FAILED
            ).value,
            "verification_error": probe.outcome.detail,
            "last_verified_at": probe.outcome.checked_at if probe.outcome.passed else None,
            "now": now,
        },
    )

    discovered = 0
    if probe.models:
        discovered = await catalogue.store_discovered(
            db,
            workspace_id=workspace_id,
            provider_config_id=provider_config_id,
            models=probe.models,
            now=now,
        )

    return await _reload(db, provider_config_id), discovered


async def refresh_catalogue(
    db: AsyncSession,
    *,
    workspace_id: str,
    provider_config_id: str,
    models: Sequence[CatalogueEntry],
    now: datetime,
) -> int:
    if await load_row(db, provider_config_id) is None:
        raise _not_found()
    return await catalogue.store_discovered(
        db,
        workspace_id=workspace_id,
        provider_config_id=provider_config_id,
        models=models,
        now=now,
    )


async def delete_provider(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    provider_config_id: str,
    now: datetime,
) -> None:
    if await load_row(db, provider_config_id) is None:
        raise _not_found()

    try:
        await db.execute(DELETE_PROVIDER_CONFIG, {"id": provider_config_id})
    except IntegrityError as error:
        # **Three foreign keys can produce this now**, where there was one:
        # `revision.provider_config_id`, and since ADR-0069 the two that a router
        # combo brings — `router_combo_entry` (an editable template names it) and
        # `revision_route_entry` (a frozen route does). The mechanism is unchanged
        # and so is the direction: this module still never reads `registry`, and
        # INT-016's forbidden edge still does not exist.
        #
        # The message widens because the next action differs. A bound revision is
        # history and cannot be unbound; a template is something the person can
        # edit right now. Which one it is, they find out on the Router screen —
        # naming it here would mean reading the registry to say so.
        raise ManagementRefusal(
            status_code=409,
            code=ErrorCode.PROVIDER_BOUND_BY_REVISIONS,
            message=(
                "at least one revision or router combo binds this provider "
                "configuration; disable it instead"
            ),
            details={"provider_config_id": provider_config_id},
        ) from error

    await events.provider_disabled(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        provider_config_id=provider_config_id,
        occurred_at=now,
    )
    credentials.forget(provider_config_id)
