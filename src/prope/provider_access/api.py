"""INT-027 — ten operations across six paths, and the credential is write-only."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import Actor, ActorType, Subject, SubjectType, may
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.provider_access import catalogue, commands, credentials, verification
from prope.provider_access.addresses import BlockedAddress, validate_base_url
from prope.provider_access.crypto import KeyUnavailable
from prope.provider_access.domain import CatalogueSource
from prope.provider_access.schemas import (
    CatalogueRefreshRead,
    CredentialRotate,
    ModelCreate,
    ModelRead,
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
    VerificationRead,
)
from prope.provider_access.verification import Probe
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

router = APIRouter(prefix="/api/v1")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _subject(session: Session, provider_config_id: str) -> Subject:
    return Subject(
        type=SubjectType.PROVIDER_CONFIG,
        id=provider_config_id,
        workspace_id=session.workspace_id,
    )


async def require_permission(
    db: AsyncSession, session: Session, action: Action, subject: Subject
) -> None:
    actor = Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id)
    if await may(db, actor, action, subject):
        return
    raise ManagementRefusal(
        status_code=403,
        code=ErrorCode.PERMISSION_DENIED,
        message=f"this action requires the {action.value} permission",
        details={"permission": action.value, "subject_type": subject.type.value},
    )


async def _authorise(
    sessionmaker: async_sessionmaker[AsyncSession],
    session: Session,
    action: Action,
    provider_config_id: str,
) -> commands.ProviderRow | None:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await require_permission(db, session, action, _subject(session, provider_config_id))
        return await commands.load_row(db, provider_config_id)


def _read(row: commands.ProviderRow) -> ProviderRead:
    return ProviderRead(
        provider_config_id=row.id,
        display_name=row.display_name,
        adapter=row.adapter,
        base_url=row.base_url,
        status=row.status,
        verification_status=row.verification_status,
        last_verified_at=row.last_verified_at,
        verification_error=row.verification_error,
        credential_last_four=row.credential_last_four,
        interactive_concurrency=row.interactive_concurrency,
        batch_concurrency=row.batch_concurrency,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _no_such_provider() -> ManagementRefusal:
    return ManagementRefusal(
        status_code=404, code=ErrorCode.NOT_FOUND, message="no such provider configuration"
    )


async def _probe(base_url: str, credential: str, now: datetime) -> Probe:
    try:
        await validate_base_url(base_url)
    except BlockedAddress as blocked:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.PROVIDER_BASE_URL_REFUSED,
            message="the base URL is refused: it must be https and must not resolve to a "
            "loopback, link-local, reserved or private address",
            details={"reason": blocked.reason},
        ) from blocked
    return await verification.verify(base_url, credential, checked_at=now)


def _key_unavailable() -> ManagementRefusal:
    return ManagementRefusal(
        status_code=503,
        code=ErrorCode.PROVIDER_KEY_UNAVAILABLE,
        message="no key-encryption key is available in this process, so no credential can be "
        "stored or read",
    )


@router.post(
    "/providers",
    response_model=ProviderRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.PROVIDER_CREATE))],
)
async def create_provider(
    payload: ProviderCreate,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ProviderRead:
    now = _utc_now()
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await require_permission(
            db, session, Action.PROVIDER_CONFIGURE, _subject(session, session.workspace_id)
        )

    probe = await _probe(payload.base_url, payload.credential, now)

    try:
        async with workspace_transaction(sessionmaker, session.workspace_id) as db:
            row = await commands.create_provider(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                display_name=payload.display_name,
                base_url=payload.base_url,
                credential=payload.credential,
                interactive_concurrency=payload.interactive_concurrency,
                batch_concurrency=payload.batch_concurrency,
                probe=probe,
                now=now,
            )
    except KeyUnavailable as error:
        raise _key_unavailable() from error

    return _read(row)


@router.get(
    "/providers",
    response_model=list[ProviderRead],
    dependencies=[Depends(declares_action(ManagementAction.PROVIDER_LIST))],
)
async def list_providers(
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[ProviderRead]:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await require_permission(db, session, Action.CATALOGUE_READ, _subject(session, session.workspace_id))
        rows = await commands.list_rows(db)
    return [_read(row) for row in rows]


@router.get(
    "/providers/{provider_id}",
    response_model=ProviderRead,
    dependencies=[Depends(declares_action(ManagementAction.PROVIDER_READ))],
)
async def read_provider(
    provider_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ProviderRead:
    row = await _authorise(sessionmaker, session, Action.CATALOGUE_READ, provider_id)
    if row is None:
        raise _no_such_provider()
    return _read(row)


@router.patch(
    "/providers/{provider_id}",
    response_model=ProviderRead,
    dependencies=[Depends(declares_action(ManagementAction.PROVIDER_UPDATE))],
)
async def update_provider(
    payload: ProviderUpdate,
    provider_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ProviderRead:
    if payload.base_url is not None:
        try:
            await validate_base_url(payload.base_url)
        except BlockedAddress as blocked:
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.PROVIDER_BASE_URL_REFUSED,
                message="the base URL is refused: it must be https and must not resolve to a "
                "loopback, link-local, reserved or private address",
                details={"reason": blocked.reason},
            ) from blocked

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await require_permission(
            db, session, Action.PROVIDER_CONFIGURE, _subject(session, provider_id)
        )
        row = await commands.update_provider(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            provider_config_id=provider_id,
            display_name=payload.display_name,
            base_url=payload.base_url,
            status=payload.status,
            interactive_concurrency=payload.interactive_concurrency,
            batch_concurrency=payload.batch_concurrency,
            now=_utc_now(),
        )
    return _read(row)


@router.post(
    "/providers/{provider_id}/credential",
    response_model=ProviderRead,
    dependencies=[Depends(declares_action(ManagementAction.PROVIDER_ROTATE_CREDENTIAL))],
)
async def rotate_credential(
    payload: CredentialRotate,
    provider_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ProviderRead:
    now = _utc_now()
    current = await _authorise(
        sessionmaker, session, Action.PROVIDER_ROTATE_CREDENTIAL, provider_id
    )
    if current is None:
        raise _no_such_provider()

    probe = await _probe(current.base_url, payload.credential, now)

    try:
        async with workspace_transaction(sessionmaker, session.workspace_id) as db:
            row = await commands.rotate_credential(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                provider_config_id=provider_id,
                credential=payload.credential,
                probe=probe,
                now=now,
            )
    except KeyUnavailable as error:
        raise _key_unavailable() from error

    return _read(row)


@router.post(
    "/providers/{provider_id}/verify",
    response_model=VerificationRead,
    dependencies=[Depends(declares_action(ManagementAction.PROVIDER_VERIFY))],
)
async def verify_provider(
    provider_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> VerificationRead:
    now = _utc_now()
    current = await _authorise(sessionmaker, session, Action.PROVIDER_CONFIGURE, provider_id)
    if current is None:
        raise _no_such_provider()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        try:
            secret = await credentials.resolve_secret(db, provider_id)
        except KeyUnavailable as error:
            raise _key_unavailable() from error

    probe = await verification.verify(current.base_url, secret, checked_at=now)

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row, discovered = await commands.record_verification(
            db,
            workspace_id=session.workspace_id,
            provider_config_id=provider_id,
            probe=probe,
            now=now,
        )

    return VerificationRead(
        provider_config_id=row.id,
        verification_status=row.verification_status,
        last_verified_at=row.last_verified_at,
        verification_error=row.verification_error,
        models_discovered=discovered,
    )


@router.delete(
    "/providers/{provider_id}",
    status_code=204,
    dependencies=[Depends(declares_action(ManagementAction.PROVIDER_DELETE))],
)
async def delete_provider(
    provider_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> None:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await require_permission(
            db, session, Action.PROVIDER_DISABLE, _subject(session, provider_id)
        )
        await commands.delete_provider(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            provider_config_id=provider_id,
            now=_utc_now(),
        )


@router.get(
    "/providers/{provider_id}/models",
    response_model=list[ModelRead],
    dependencies=[Depends(declares_action(ManagementAction.CATALOGUE_READ))],
)
async def list_models(
    provider_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[ModelRead]:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await require_permission(
            db, session, Action.CATALOGUE_READ, _subject(session, provider_id)
        )
        if await commands.load_row(db, provider_id) is None:
            raise _no_such_provider()
        entries = await catalogue.get_model_catalogue(db, provider_id)

    return [
        ModelRead(
            model_id=entry.model_id,
            display_name=entry.display_name,
            supports_streaming=entry.supports_streaming,
            available=entry.available,
            source=entry.source,
            input_price_per_1k=entry.input_price_per_1k,
            output_price_per_1k=entry.output_price_per_1k,
        )
        for entry in entries
    ]


@router.post(
    "/providers/{provider_id}/models/refresh",
    response_model=CatalogueRefreshRead,
    dependencies=[Depends(declares_action(ManagementAction.CATALOGUE_REFRESH))],
)
async def refresh_models(
    provider_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> CatalogueRefreshRead:
    now = _utc_now()
    current = await _authorise(sessionmaker, session, Action.PROVIDER_CONFIGURE, provider_id)
    if current is None:
        raise _no_such_provider()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        try:
            secret = await credentials.resolve_secret(db, provider_id)
        except KeyUnavailable as error:
            raise _key_unavailable() from error

    try:
        models = await verification.discover_models(current.base_url, secret)
    except BlockedAddress as blocked:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.PROVIDER_BASE_URL_REFUSED,
            message="the stored base URL now resolves to a refused address",
            details={"reason": blocked.reason},
        ) from blocked

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        discovered = await commands.refresh_catalogue(
            db,
            workspace_id=session.workspace_id,
            provider_config_id=provider_id,
            models=models,
            now=now,
        )

    return CatalogueRefreshRead(provider_config_id=provider_id, discovered=discovered)


@router.post(
    "/providers/{provider_id}/models",
    response_model=ModelRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.CATALOGUE_ADD))],
)
async def add_model(
    payload: ModelCreate,
    provider_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ModelRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await require_permission(
            db, session, Action.PROVIDER_CONFIGURE, _subject(session, provider_id)
        )
        if await commands.load_row(db, provider_id) is None:
            raise _no_such_provider()

        added = await catalogue.add_manual_model(
            db,
            workspace_id=session.workspace_id,
            provider_config_id=provider_id,
            model_id=payload.model_id,
            display_name=payload.display_name,
            supports_streaming=payload.supports_streaming,
            now=_utc_now(),
        )
        if not added:
            raise ManagementRefusal(
                status_code=409,
                code=ErrorCode.ALREADY_EXISTS,
                message="that model is already in this configuration's catalogue",
                details={"model_id": payload.model_id},
            )

    return ModelRead(
        model_id=payload.model_id,
        display_name=payload.display_name,
        supports_streaming=payload.supports_streaming,
        available=True,
        source=CatalogueSource.MANUAL,
    )
