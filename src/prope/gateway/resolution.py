"""Authenticate the key, apply its scope, then resolve — in that order, every request.

Neither access-control call is cached, by this module or by access-control
(A-114, ADR-0022): a stale pointer serves a previously approved revision one TTL
late, and a stale permission serves a revoked key. The 30 s resolution cache sits
behind both.
"""

import time

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import AuthenticatedKey, authenticate_api_key, may_resolve
from prope.db.session import workspace_transaction
from prope.gateway.cache import CacheKey, resolution_cache
from prope.gateway.domain import MissReason, ModelReference
from prope.gateway.errors import GatewayError, authentication_failed, model_not_found
from prope.gateway.observability import (
    auth_failure_total,
    resolve_duration_seconds,
    resolve_miss_total,
)
from prope.prompt_registry.domain import ReleasedListing, ResolveMiss, RevisionBinding
from prope.prompt_registry.seams import list_released, resolve

log = structlog.get_logger(__name__)

__all__ = [
    "BEARER_PREFIX",
    "authenticate",
    "presented_key",
    "released_listings",
    "resolve_binding",
]

BEARER_PREFIX = "bearer "


def presented_key(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith(BEARER_PREFIX):
        return authorization[len(BEARER_PREFIX) :].strip() or None
    return authorization.strip() or None


async def authenticate(
    sessionmaker: async_sessionmaker[AsyncSession], authorization: str | None
) -> AuthenticatedKey:
    key = await authenticate_api_key(sessionmaker, presented_key(authorization))
    if key is None:
        auth_failure_total.inc()
        log.info("gateway.auth_failed", result="unknown")
        raise authentication_failed()
    return key


def _missed(reason: MissReason, started: float, model: str) -> GatewayError:
    resolve_miss_total.labels(reason=reason.value).inc()
    resolve_duration_seconds.labels(cache="miss").observe(time.perf_counter() - started)
    return model_not_found(model)


def _reason_for(outcome: ResolveMiss, reference: ModelReference) -> MissReason:
    if outcome is ResolveMiss.UNKNOWN_MODEL:
        return MissReason.UNKNOWN_MODEL
    if reference.pinned:
        return MissReason.PIN_NOT_APPROVED
    return MissReason.NO_RELEASE


async def resolve_binding(
    sessionmaker: async_sessionmaker[AsyncSession],
    key: AuthenticatedKey,
    reference: ModelReference,
) -> RevisionBinding:
    started = time.perf_counter()
    cache = resolution_cache()
    cache_key = CacheKey(
        workspace_id=key.workspace_id, model_name=reference.model_name, pin=reference.pin
    )
    cached = cache.get(cache_key)

    async with workspace_transaction(sessionmaker, key.workspace_id) as db:
        if not await may_resolve(db, key.key_id, reference.model_name):
            raise _missed(MissReason.NOT_PERMITTED, started, reference.raw)

        if cached is not None:
            resolve_duration_seconds.labels(cache="hit").observe(time.perf_counter() - started)
            return cached

        outcome = await resolve(db, key.workspace_id, reference.name, reference.pin)

    if isinstance(outcome, ResolveMiss):
        raise _missed(_reason_for(outcome, reference), started, reference.raw)

    cache.put(cache_key, outcome)
    resolve_duration_seconds.labels(cache="miss").observe(time.perf_counter() - started)
    return outcome


async def released_listings(
    sessionmaker: async_sessionmaker[AsyncSession], key: AuthenticatedKey
) -> tuple[ReleasedListing, ...]:
    async with workspace_transaction(sessionmaker, key.workspace_id) as db:
        listings = await list_released(db, key.workspace_id)

    scope = frozenset(key.scope)
    return tuple(listing for listing in listings if listing.model_name in scope)
