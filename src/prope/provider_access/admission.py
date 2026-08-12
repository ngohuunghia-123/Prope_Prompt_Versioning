"""ADR-0046 — two static caps, one per process, each over its own column."""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from prope.provider_access.domain import Priority
from prope.provider_access.observability import admission_wait_seconds, shed_total

__all__ = ["Shed", "admit", "in_flight", "reset_gate"]

SHED_REASON_AT_CAPACITY = "at_capacity"

SHED_REASON_DEADLINE = "deadline"

_semaphores: dict[tuple[str, Priority], tuple[asyncio.Semaphore, int]] = {}

_in_flight: dict[tuple[str, Priority], int] = {}


class Shed(Exception):  # noqa: N818
    def __init__(self, priority: Priority, reason: str) -> None:
        super().__init__(
            f"a {priority.value} dispatch was refused by Prope's own admission gate ({reason})"
        )
        self.priority = priority
        self.reason = reason


def reset_gate() -> None:
    _semaphores.clear()
    _in_flight.clear()


def in_flight(provider_config_id: str, priority: Priority) -> int:
    return _in_flight.get((provider_config_id, priority), 0)


def _semaphore(provider_config_id: str, priority: Priority, limit: int) -> asyncio.Semaphore:
    key = (provider_config_id, priority)
    existing = _semaphores.get(key)
    if existing is None or existing[1] != limit:
        _semaphores[key] = (asyncio.Semaphore(limit), limit)
    return _semaphores[key][0]


@asynccontextmanager
async def admit(
    provider_config_id: str,
    priority: Priority,
    limit: int,
    *,
    deadline_seconds: float | None = None,
) -> AsyncIterator[None]:
    """Interactive fails fast; batch waits, bounded by the caller's deadline."""
    key = (provider_config_id, priority)
    semaphore = _semaphore(provider_config_id, priority, limit)
    started = time.perf_counter()

    if priority is Priority.INTERACTIVE:
        if semaphore.locked():
            shed_total.labels(
                priority=priority.value, reason=SHED_REASON_AT_CAPACITY
            ).inc()
            raise Shed(priority, SHED_REASON_AT_CAPACITY)
        await semaphore.acquire()
    else:
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=deadline_seconds)
        except TimeoutError as error:
            shed_total.labels(priority=priority.value, reason=SHED_REASON_DEADLINE).inc()
            raise Shed(priority, SHED_REASON_DEADLINE) from error

    admission_wait_seconds.labels(priority=priority.value).observe(time.perf_counter() - started)
    _in_flight[key] = _in_flight.get(key, 0) + 1
    try:
        yield
    finally:
        _in_flight[key] -= 1
        semaphore.release()
