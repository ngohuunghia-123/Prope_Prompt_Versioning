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
    "TTL_SECONDS",
    "CacheKey",
    "ResolutionCache",
    "reset_resolution_cache",
    "resolution_cache",
]

MAX_ENTRIES = 5_000

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


_cache: ResolutionCache | None = None


def resolution_cache() -> ResolutionCache:
    global _cache
    if _cache is None:
        _cache = ResolutionCache()
    return _cache


def reset_resolution_cache() -> None:
    global _cache
    _cache = None
