"""The lock's `performance_requirements`, run as a measurement rather than quoted.

Five numbers are stated and four are measured here. Every one of them is worth
reading with the same caveat the lock attaches to the first:

> The 50 is an agent-decided placeholder — OQ-012 still owes the real budget, and
> the constraints table says so. revisit_when OQ-012 sets a number.

So what this file is for is **producing a real figure to replace the placeholder
with, rather than an argument about how to measure it**. The instrumented span
exists either way (`prope_gateway_added_latency_seconds`), and the assertions
below are deliberately loose enough that a laptop under a container runtime does
not fail a target that was written for a 4 vCPU VM — a load test that fails for
the wrong reason is a load test somebody deletes.

Skipped unless `PROPE_RUN_LOAD` is set, and marked `load`, following
`tests/load/test_resolve_latency.py`. A SKIPPED test prints an `s` and its
reason; a deselected one is invisible, which is why there is no `addopts`
anywhere in this project.
"""

import os
import statistics
import time

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.gateway.cache import TTL_SECONDS
from tests.gateway import (
    MODEL,
    UPSTREAM_MODEL,
    authorization,
    gateway_api,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion

pytestmark = pytest.mark.load

RUN_LOAD = pytest.mark.skipif(
    not os.environ.get("PROPE_RUN_LOAD"),
    reason="The gateway's paced latency run. Set PROPE_RUN_LOAD=1 to include it.",
)

#: Enough samples for a p95 to mean something and few enough that the run is
#: minutes rather than hours. 200 puts the 95th percentile at the 190th sample.
REQUESTS = 200

#: The upstream's fixed delay, matching the lock's condition *"upstream stubbed
#: at a fixed delay"*. It exists so that the measured span can be separated from
#: the provider's own time by subtraction rather than by hoping the stub is fast.
UPSTREAM_DELAY_SECONDS = 0.02

CHUNKS = 200


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _request(**extra) -> dict:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hi"}], **extra}


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def _slow_provider(delay: float):  # noqa: ANN202
    def handler(_: httpx.Request) -> httpx.Response:
        time.sleep(delay)
        return httpx.Response(200, json=completion())

    return handler


def _stream_body(count: int) -> bytes:
    import json

    chunk = {
        "id": "cmpl-1",
        "object": "chat.completion.chunk",
        "created": 1_760_000_000,
        "model": UPSTREAM_MODEL,
        "choices": [{"index": 0, "delta": {"content": "token "}, "finish_reason": None}],
    }
    body = "".join(f"data: {json.dumps(chunk)}\n\n" for _ in range(count))
    return (body + "data: [DONE]\n\n").encode()


@RUN_LOAD
async def test_added_latency_p95_is_inside_the_budget(api, migrate_engine, monkeypatch) -> None:
    """Arrival to dispatch plus upstream completion to flush, with the upstream's
    own time subtracted — which is what the success metric is defined as, and why
    the stub carries a fixed delay rather than answering instantly.

    Warm cache, per the stated condition. The two access-control reads in front of
    the cache are NOT warm and never will be (A-114), and their p95 < 5 ms budget
    is *"measured inside this module's own load test rather than in isolation"* —
    which means it is inside the figure below rather than beside it.
    """
    await seed_released_world(migrate_engine)
    added: list[float] = []

    with stub_upstream(monkeypatch, _slow_provider(UPSTREAM_DELAY_SECONDS)):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

        for _ in range(REQUESTS):
            started = time.perf_counter()
            response = await call(
                api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
            )
            elapsed = time.perf_counter() - started
            assert response.status_code == 200
            added.append(max(0.0, elapsed - UPSTREAM_DELAY_SECONDS))

    p95 = _percentile(added, 0.95)
    assert p95 < 0.05, (
        f"added latency p95 {p95 * 1000:.1f} ms against A-031's 50 ms placeholder; "
        f"median {statistics.median(added) * 1000:.1f} ms over {REQUESTS} requests"
    )


@RUN_LOAD
async def test_the_cache_hit_ratio_stays_above_the_stated_floor(
    api, migrate_engine, monkeypatch
) -> None:
    """*"cache hit ratio > 95% at 1,000 prompt properties"*.

    With one prompt and a 30 s TTL the ratio is bounded by the run's duration
    rather than by the cache's size, which is the honest thing this can measure
    without seeding a thousand prompts into a container for one number: at
    `REQUESTS` requests inside one TTL there is exactly one miss.
    """
    await seed_released_world(migrate_engine)

    from prometheus_client import REGISTRY

    def count(cache: str) -> float:
        return (
            REGISTRY.get_sample_value(
                "prope_gateway_resolve_duration_seconds_count", {"cache": cache}
            )
            or 0.0
        )

    hits_before, misses_before = count("hit"), count("miss")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        for _ in range(REQUESTS):
            await call(
                api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
            )

    hits = count("hit") - hits_before
    misses = count("miss") - misses_before

    assert misses == 1, "one cold resolution, and the TTL is longer than this run"
    assert hits / (hits + misses) > 0.95
    assert TTL_SECONDS == 30.0


@RUN_LOAD
async def test_per_chunk_relay_overhead_stays_under_two_milliseconds(
    api, migrate_engine, monkeypatch
) -> None:
    """A-038 requires that accumulation never delay a chunk, and this is the
    number that says so: the relay and the accumulate run in the same loop, so
    the cost of recording the response is inside the per-chunk figure rather than
    hidden behind it."""
    await seed_released_world(migrate_engine)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=_stream_body(CHUNKS), headers={"content-type": "text/event-stream"}
        )

    with stub_upstream(monkeypatch, handler):
        started = time.perf_counter()
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(stream=True),
            headers=authorization(),
        )
        elapsed = time.perf_counter() - started

    assert response.status_code == 200
    per_chunk = elapsed / CHUNKS
    assert per_chunk < 0.002, f"{per_chunk * 1000:.2f} ms per chunk over {CHUNKS} chunks"


@RUN_LOAD
async def test_listing_models_stays_inside_its_own_budget(api, migrate_engine) -> None:
    """*"GET /v1/models — p95 < 300 ms at 1,000 prompt properties"*.

    Seeded through `seed_released_prompts`, which batches four `executemany`
    statements for the reason written there: the row-at-a-time factories open a
    connection each, and `migrate_engine` uses `NullPool`, so 1,000 neighbours
    through that path is minutes of SCRAM handshakes rather than a measurement.
    """
    from tests.prompt_registry import seed_released_prompts

    await seed_released_world(migrate_engine)
    await seed_released_prompts(migrate_engine, 999)

    samples: list[float] = []
    for _ in range(20):
        started = time.perf_counter()
        response = await call(api, "GET", "/models", headers=authorization())
        samples.append(time.perf_counter() - started)
        assert response.status_code == 200

    p95 = _percentile(samples, 0.95)
    assert p95 < 0.3, f"GET /v1/models p95 {p95 * 1000:.0f} ms at 1,000 prompt properties"
