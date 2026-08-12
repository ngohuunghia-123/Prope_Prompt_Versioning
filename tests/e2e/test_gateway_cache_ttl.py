"""AC-9 and the Developer persona's whole journey: release, restore, withdraw — no restart.

*"A restore changes what production runs without a code change"* is the product's
headline claim to the Developer, and ADR-0012 is what makes it true without a
message bus: **nothing invalidates the cache; it expires.** So the guarantee is
*within 30 seconds, always, with no coordination between processes* — not
instantly, and the release and withdraw screens say so in words rather than
implying otherwise.

The clock is driven rather than waited on. A test that slept 30 seconds per
assertion would take three minutes to prove a property whose whole content is
*the TTL is the only mechanism*, and it would prove it against `time.monotonic`
rather than against the cache.
"""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.gateway import cache as cache_module
from prope.gateway.cache import TTL_SECONDS
from tests.gateway import (
    CONFIG_ID,
    MODEL,
    PROMPT_ID,
    UPSTREAM_MODEL,
    VERSION_ID,
    authorization,
    gateway_api,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.prompt_registry import approve, seed_revision
from tests.provider_access._stub import completion

SECOND_VERSION = "rev_01J000000000000000000REV2"

WITHDRAW = text(
    "UPDATE registry.prompt_property SET released_version_id = NULL, released_at = NULL "
    "WHERE id = :prompt_id"
)

POINT_AT = text(
    "UPDATE registry.prompt_property SET released_version_id = :version_id, released_at = now() "
    "WHERE id = :prompt_id"
)


class _Clock:
    """A monotonic clock the test moves, standing in for the one the cache reads.

    The cache takes `now` as an argument at both call sites precisely so this is
    an injection rather than a patch of `time.monotonic` — patching the module
    would also move every other timer in the process, including the ones
    measuring the histograms these tests do not care about.
    """

    def __init__(self) -> None:
        self.value = 1_000.0

    def advance(self, seconds: float) -> None:
        self.value += seconds

    def __call__(self) -> float:
        return self.value


@pytest.fixture
def clock(monkeypatch) -> _Clock:
    ticking = _Clock()
    monkeypatch.setattr(cache_module.time, "monotonic", ticking)
    return ticking


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _request() -> dict:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}


async def _served_version(api, monkeypatch) -> str | None:  # noqa: ANN001
    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )
    if response.status_code != 200:
        return None
    return response.headers["x-prope-version-id"]


async def _point_at(migrate_engine, version_id: str) -> None:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        await connection.execute(POINT_AT, {"prompt_id": PROMPT_ID, "version_id": version_id})


async def test_a_release_reaches_the_caller_within_the_ttl_and_not_before(
    api, migrate_engine, monkeypatch, clock
) -> None:
    """Both halves, because only asserting the first would pass on a cache that
    does not exist, and only asserting the second would pass on one that never
    expires.

    Inside the window the previous — always Approved — revision is still served,
    which ADR-0009 already accepted as the cost. At the window it is the new one,
    with no restart and no invalidation message anywhere in the system.
    """
    await seed_released_world(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        body="The second body.",
        provider_config_id=CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
    )
    await approve(migrate_engine, SECOND_VERSION)

    assert await _served_version(api, monkeypatch) == VERSION_ID

    await _point_at(migrate_engine, SECOND_VERSION)

    clock.advance(TTL_SECONDS - 1)
    assert await _served_version(api, monkeypatch) == VERSION_ID

    clock.advance(1)
    assert await _served_version(api, monkeypatch) == SECOND_VERSION


async def test_a_restore_reaches_the_caller_the_same_way(
    api, migrate_engine, monkeypatch, clock
) -> None:
    """The restore is the release path run backwards, and it has to cost the same
    30 seconds — the ≤ 5 min restore target (H-05) is what pays for it, at
    roughly 10x headroom."""
    await seed_released_world(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        body="The second body.",
        provider_config_id=CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
    )
    await approve(migrate_engine, SECOND_VERSION)
    await _point_at(migrate_engine, SECOND_VERSION)
    clock.advance(TTL_SECONDS)

    assert await _served_version(api, monkeypatch) == SECOND_VERSION

    await _point_at(migrate_engine, VERSION_ID)
    clock.advance(TTL_SECONDS)

    assert await _served_version(api, monkeypatch) == VERSION_ID


async def test_a_withdrawal_reaches_the_caller_as_a_model_not_found(
    api, migrate_engine, monkeypatch, clock
) -> None:
    """The end of the journey. ADR-0009 wanted the gateway to fail loudly, and
    the TTL is how long *loudly* takes to arrive."""
    await seed_released_world(migrate_engine)
    assert await _served_version(api, monkeypatch) == VERSION_ID

    async with migrate_engine.begin() as connection:
        await connection.execute(WITHDRAW, {"prompt_id": PROMPT_ID})

    clock.advance(TTL_SECONDS - 1)
    assert await _served_version(api, monkeypatch) == VERSION_ID

    clock.advance(1)
    assert await _served_version(api, monkeypatch) is None


async def test_a_pinned_consumer_is_not_reached_by_the_restore(
    api, migrate_engine, monkeypatch, clock
) -> None:
    """The risk row, made concrete. Pinning is in scope by the user's own words,
    and this is what it costs: the restore guarantee does not apply to a consumer
    who opted out of it, however long you wait.

    `prope_gateway_pinned_call_total{prompt}` is the whole mitigation — visibility
    — and it cannot be surfaced on the release screen, because release-control may
    not read traffic data.
    """
    await seed_released_world(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        body="The second body.",
        provider_config_id=CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
    )
    await approve(migrate_engine, SECOND_VERSION)
    await _point_at(migrate_engine, SECOND_VERSION)
    clock.advance(TTL_SECONDS)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        pinned = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": f"{MODEL}@1", "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )

    assert pinned.headers["x-prope-version-id"] == VERSION_ID
    assert await _served_version(api, monkeypatch) == SECOND_VERSION


async def test_nothing_in_the_process_invalidates_the_cache(
    api, migrate_engine, monkeypatch, clock
) -> None:
    """ADR-0012 asserted as an absence, which is the only way to assert it.

    The released pointer moves and the entry does not; only the clock moves it.
    A future edit that added an invalidation hook — a broker subscription, a
    registry callback, a shared flag — would make the middle assertion fail, and
    that is the assertion's whole job.
    """
    await seed_released_world(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        provider_config_id=CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
    )
    await approve(migrate_engine, SECOND_VERSION)

    assert await _served_version(api, monkeypatch) == VERSION_ID

    await _point_at(migrate_engine, SECOND_VERSION)

    for _ in range(5):
        assert await _served_version(api, monkeypatch) == VERSION_ID

    clock.advance(TTL_SECONDS)
    assert await _served_version(api, monkeypatch) == SECOND_VERSION
