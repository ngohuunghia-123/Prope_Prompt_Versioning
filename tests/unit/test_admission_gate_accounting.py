"""AC-6, in the form ADR-0046 owes it.

The original criterion asserted a single-process semaphore with a reserved
share, against two columns that no longer exist. Under per-process caps the
replacement asserts each cap holds within its own process, that a saturated
batch process has no observable effect on the interactive one, and that
`shed_total` accounts for every dispatch that was not admitted.
"""

import asyncio

import pytest
from prometheus_client import REGISTRY

from prope.provider_access.admission import (
    SHED_REASON_AT_CAPACITY,
    SHED_REASON_DEADLINE,
    Shed,
    admit,
    in_flight,
    reset_gate,
)
from prope.provider_access.domain import Priority

CONFIG = "prv_01TEST"


@pytest.fixture(autouse=True)
def _clean_gate():
    reset_gate()
    yield
    reset_gate()


def _shed(priority: Priority, reason: str) -> float:
    value = REGISTRY.get_sample_value(
        "prope_provider_access_shed_total",
        {"priority": priority.value, "reason": reason},
    )
    return value or 0.0


async def test_an_interactive_dispatch_fails_fast_rather_than_queueing() -> None:
    """On the hot path a queue is just a slower error (ADR-0016)."""
    before = _shed(Priority.INTERACTIVE, SHED_REASON_AT_CAPACITY)
    released = asyncio.Event()

    async def hold() -> None:
        async with admit(CONFIG, Priority.INTERACTIVE, 1):
            await released.wait()

    holder = asyncio.create_task(hold())
    await asyncio.sleep(0)

    with pytest.raises(Shed) as refused:
        async with admit(CONFIG, Priority.INTERACTIVE, 1):
            pass

    released.set()
    await holder

    assert refused.value.reason == SHED_REASON_AT_CAPACITY
    assert _shed(Priority.INTERACTIVE, SHED_REASON_AT_CAPACITY) == before + 1


async def test_occupancy_never_exceeds_the_cap_belonging_to_this_process() -> None:
    limit = 3
    peak = 0
    started = asyncio.Event()

    async def one() -> None:
        nonlocal peak
        try:
            async with admit(CONFIG, Priority.BATCH, limit, deadline_seconds=2.0):
                peak = max(peak, in_flight(CONFIG, Priority.BATCH))
                await started.wait()
        except Shed:
            pass

    workers = [asyncio.create_task(one()) for _ in range(limit * 3)]
    await asyncio.sleep(0.05)
    started.set()
    await asyncio.gather(*workers)

    assert peak <= limit


async def test_a_saturated_batch_process_does_not_delay_an_interactive_admission() -> None:
    """The property is structural under ADR-0046 rather than enforced by a
    reservation: the two classes hold different semaphores because they run in
    different containers, so batch cannot occupy an interactive slot at all."""
    released = asyncio.Event()

    async def batch() -> None:
        async with admit(CONFIG, Priority.BATCH, 1, deadline_seconds=5.0):
            await released.wait()

    holder = asyncio.create_task(batch())
    await asyncio.sleep(0)

    async with admit(CONFIG, Priority.INTERACTIVE, 1):
        assert in_flight(CONFIG, Priority.INTERACTIVE) == 1
        assert in_flight(CONFIG, Priority.BATCH) == 1

    released.set()
    await holder


async def test_a_batch_dispatch_waits_and_is_shed_at_its_deadline() -> None:
    """Batch yields; it does not fail fast. What bounds the wait is the
    caller's own deadline, not a queue length nobody set."""
    before = _shed(Priority.BATCH, SHED_REASON_DEADLINE)
    released = asyncio.Event()

    async def hold() -> None:
        async with admit(CONFIG, Priority.BATCH, 1, deadline_seconds=5.0):
            await released.wait()

    holder = asyncio.create_task(hold())
    await asyncio.sleep(0)

    with pytest.raises(Shed) as refused:
        async with admit(CONFIG, Priority.BATCH, 1, deadline_seconds=0.01):
            pass

    released.set()
    await holder

    assert refused.value.reason == SHED_REASON_DEADLINE
    assert _shed(Priority.BATCH, SHED_REASON_DEADLINE) == before + 1


async def test_a_slot_is_released_even_when_the_dispatch_raises() -> None:
    """A leaked slot is a cap that shrinks by one every time a provider errors,
    which presents weeks later as an unexplained shed rate."""
    with pytest.raises(RuntimeError):
        async with admit(CONFIG, Priority.INTERACTIVE, 1):
            raise RuntimeError("upstream exploded")

    async with admit(CONFIG, Priority.INTERACTIVE, 1):
        assert in_flight(CONFIG, Priority.INTERACTIVE) == 1


async def test_two_configurations_do_not_share_a_budget() -> None:
    """The cap is per configuration, because it is a share of one provider's
    key rather than a share of this process's capacity."""
    released = asyncio.Event()

    async def hold() -> None:
        async with admit("prv_01ONE", Priority.INTERACTIVE, 1):
            await released.wait()

    holder = asyncio.create_task(hold())
    await asyncio.sleep(0)

    async with admit("prv_01TWO", Priority.INTERACTIVE, 1):
        assert in_flight("prv_01TWO", Priority.INTERACTIVE) == 1

    released.set()
    await holder
