"""ADR-0012 / A-080: a bounded TTL-only LRU. Nothing invalidates it; it expires.

An expired entry is never served — the stale-if-error window ADR-0012 originally
carried was deleted on 2026-08-09 and there is no code path here that could
return one.
"""

import time
from collections import OrderedDict
from dataclasses import dataclass

from prope.prompt_registry.domain import RevisionBinding

__all__ = [
    "MAX_ENTRIES",
    "MAX_NAMESPACE_ENTRIES",
    "TTL_SECONDS",
    "CacheKey",
    "NamespaceCache",
    "ResolutionCache",
    "namespace_cache",
    "reset_resolution_cache",
    "resolution_cache",
]

MAX_ENTRIES = 5_000

#: One entry per workspace, not per model name, so the bound is workspaces on one
#: host rather than prompts in a registry. ADR-0033 puts one VM under this.
MAX_NAMESPACE_ENTRIES = 500

TTL_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class CacheKey:
    workspace_id: str
    model_name: str
    pin: str | None


class ResolutionCache:
    __slots__ = ("_entries", "_maxsize", "_ttl")

    def __init__(self, maxsize: int = MAX_ENTRIES, ttl_seconds: float = TTL_SECONDS) -> None:
        self._entries: OrderedDict[CacheKey, tuple[float, RevisionBinding]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl_seconds

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: CacheKey, *, now: float | None = None) -> RevisionBinding | None:
        entry = self._entries.get(key)
        if entry is None:
            return None

        stored_at, binding = entry
        clock = time.monotonic() if now is None else now
        if clock - stored_at >= self._ttl:
            del self._entries[key]
            return None

        self._entries.move_to_end(key)
        return binding

    def put(self, key: CacheKey, binding: RevisionBinding, *, now: float | None = None) -> None:
        clock = time.monotonic() if now is None else now
        self._entries[key] = (clock, binding)
        self._entries.move_to_end(key)
        while len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()


class NamespaceCache:
    """ADR-0062's namespace set, on ADR-0012's TTL and under ADR-0012's rule.

    The set of namespaces a workspace uses — what :func:`~prope.prompt_registry.
    seams.list_namespaces` returns — keyed by workspace and expiring after
    :data:`TTL_SECONDS`. **Nothing invalidates it; it expires**, exactly as the
    resolution cache does and for the same reason: this edge runs one way, and no
    invalidation mechanism exists in a system where the registry may not call the
    gateway.

    The staleness window is one TTL and it fails in a known direction. A namespace
    created 5 seconds ago is not yet in the set, so a call addressed to it is
    forwarded and observed rather than refused — which costs one observation row
    somebody dismisses. The reverse, a namespace deleted 5 seconds ago, cannot
    produce a wrong serve: forwarding is decided *before* resolution and a stale
    "this namespace exists" only ever makes the gateway refuse, which is what it
    would have done anyway.
    """

    __slots__ = ("_entries", "_maxsize", "_ttl")

    def __init__(
        self, maxsize: int = MAX_NAMESPACE_ENTRIES, ttl_seconds: float = TTL_SECONDS
    ) -> None:
        self._entries: OrderedDict[str, tuple[float, frozenset[str]]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl_seconds

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, workspace_id: str, *, now: float | None = None) -> frozenset[str] | None:
        entry = self._entries.get(workspace_id)
        if entry is None:
            return None

        stored_at, namespaces = entry
        clock = time.monotonic() if now is None else now
        if clock - stored_at >= self._ttl:
            del self._entries[workspace_id]
            return None

        self._entries.move_to_end(workspace_id)
        return namespaces

    def put(
        self, workspace_id: str, namespaces: frozenset[str], *, now: float | None = None
    ) -> None:
        clock = time.monotonic() if now is None else now
        self._entries[workspace_id] = (clock, namespaces)
        self._entries.move_to_end(workspace_id)
        while len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()


_cache: ResolutionCache | None = None
_namespaces: NamespaceCache | None = None


def resolution_cache() -> ResolutionCache:
    global _cache
    if _cache is None:
        _cache = ResolutionCache()
    return _cache


def namespace_cache() -> NamespaceCache:
    global _namespaces
    if _namespaces is None:
        _namespaces = NamespaceCache()
    return _namespaces


def reset_resolution_cache() -> None:
    """Both caches. One name, because a test that reset half of one gateway's
    memoisation and not the other would pass for the wrong reason."""
    global _cache, _namespaces
    _cache = None
    _namespaces = None
