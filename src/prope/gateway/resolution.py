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
from prope.gateway.cache import CacheKey, namespace_cache, resolution_cache
from prope.gateway.domain import MissReason, ModelReference
from prope.gateway.errors import GatewayError, authentication_failed, model_not_found
from prope.gateway.observability import (
    auth_failure_total,
    resolve_duration_seconds,
    resolve_miss_total,
)
from prope.prompt_registry.domain import ReleasedListing, ResolveMiss, RevisionBinding
from prope.prompt_registry.seams import list_namespaces, list_released, resolve

log = structlog.get_logger(__name__)

__all__ = [
    "BEARER_PREFIX",
    "authenticate",
    "is_workspace_namespace",
    "presented_key",
    "released_listings",
    "resolve_binding",
    "workspace_namespaces",
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
        if not await may_resolve(db, key.key_id, reference.model_name, reference.name.namespace):
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
    """INT-010 narrowed to what this key may resolve. **Both scopes, one `OR`.**

    ADR-0061 / A-158, and the filter has to agree with `may_resolve` exactly or
    the list lies in one of two directions. Listing a name the key cannot call is
    an enumeration leak (A-116); *omitting* one it can call is the quieter defect
    — the picker comes back empty, the integration looks broken, and the key is
    working perfectly. A folder-scoped key hits the second one every time, which
    is the whole reason a folder scope exists.

    Split rather than a stored field: `model_name` is `namespace/name` and A-021
    makes that immutable, so the first segment *is* the namespace. `ReleasedListing`
    carries three fields and INT-010 says three; adding a fourth to save a
    `partition` here would widen a published seam for one call site.
    """
    async with workspace_transaction(sessionmaker, key.workspace_id) as db:
        listings = await list_released(db, key.workspace_id)

    scope = frozenset(key.scope)
    namespaces = frozenset(key.scope_namespaces)
    return tuple(
        listing
        for listing in listings
        if listing.model_name in scope or listing.model_name.partition("/")[0] in namespaces
    )


async def workspace_namespaces(
    sessionmaker: async_sessionmaker[AsyncSession], key: AuthenticatedKey
) -> frozenset[str]:
    """ADR-0062's entry rule, second case: which namespaces does this workspace use?

    INT-036, cached per workspace on ADR-0012's existing 30 s TTL. Nothing
    invalidates it; it expires, for the reason the resolution cache beside it
    expires — this edge runs one way and no invalidation mechanism exists in a
    system where the registry may not call the gateway.

    **Only ever reached on an observe-enabled key.** A key with no
    `observe_provider_config_id` never asks this question, so the read is not on
    the hot path of any integration that existed before ADR-0059, and AC-17's
    *"an observe-disabled key is unaffected on every path"* is true by
    construction rather than by care.
    """
    cache = namespace_cache()
    cached = cache.get(key.workspace_id)
    if cached is not None:
        return cached

    async with workspace_transaction(sessionmaker, key.workspace_id) as db:
        namespaces = await list_namespaces(db, key.workspace_id)

    cache.put(key.workspace_id, namespaces)
    return namespaces


async def is_workspace_namespace(
    sessionmaker: async_sessionmaker[AsyncSession],
    key: AuthenticatedKey,
    namespace: str,
) -> bool:
    """A-156's test, and the whole of the difference between serving and forwarding.

    True when Prope has something to say under this name — the namespace is one
    the workspace uses, or one this key was explicitly scoped to. Either way the
    request goes down the ordinary path and every refusal it can produce is
    byte-identical to what it was before ADR-0059.

    **The key's own scope counts as a workspace namespace**, which is the clause
    that stops an empty registry from being an oracle: a key scoped to `support`
    calling `support/nothing` is refused rather than forwarded, even on the day
    before the first `support/` prompt is created. Without it, the first request
    of a new integration would forward to the provider and file its own prompt as
    ungoverned.
    """
    if namespace in key.scope_namespaces:
        return True
    return namespace in await workspace_namespaces(sessionmaker, key)
