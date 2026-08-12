"""T-012 and T-013 — the two inbound quantities that were bounded by nothing.

Both are HIGH in the step-6 STRIDE pass and both are denial of service at
boundary B1, *"the only anonymous-until-authenticated surface in Prope, and the
one an outside team's code calls"*.

**T-012 (A-148)**: Prope caps almost everything it stores and nothing it
receives. The caller's `messages` array was *"the one field on the one
internet-facing route that an unauthenticated-until-checked caller controls the
size of, on a host with 8 GB of RAM and no HA"*, held in memory twice on the way
through. Caddy's 1 MiB is configuration and not code; the gateway's 256 KiB on
the **composed** set is the one asserted here. **Refused, never truncated** — a
silently truncated conversation is a wrong answer rather than a refused one.

**T-013 (A-143)**: without a cap, one consuming product's retry loop is
indistinguishable from a Prope fault and takes every other consumer with it. The
cap is per `key_id` and **per process**, so an A-130 split makes the effective
limit 40 — asserted here as per-process semantics rather than as a global count.
"""

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.gateway.admission import MAX_IN_FLIGHT_PER_KEY, admit
from prope.gateway.composition import MAX_COMPOSED_BYTES
from tests.access_control import KEY_ID
from tests.gateway import (
    MODEL,
    SECOND_KEY_ID,
    authorization,
    gateway_api,
    seed_key,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _oversize() -> float:
    return REGISTRY.get_sample_value("prope_gateway_oversize_request_total") or 0.0


def _message(size: int) -> dict:
    return {"role": "user", "content": "x" * size}


def _request(content_size: int) -> dict:
    return {"model": MODEL, "messages": [_message(content_size)]}


async def test_a_composed_set_just_under_the_cap_is_served(
    api, migrate_engine, monkeypatch
) -> None:
    """The boundary from below, because a cap asserted only from above is a cap
    that could be refusing traffic nobody meant to refuse. 1 KiB of headroom
    covers the JSON framing and the revision's own body, which are both inside
    the measured set."""
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MAX_COMPOSED_BYTES - 1024),
            headers=authorization(),
        )

    assert response.status_code == 200, response.body


async def test_a_composed_set_over_the_cap_is_refused_and_never_dispatched(
    api, migrate_engine, monkeypatch
) -> None:
    """The memory is spent by the time the ledger's own body cap would fire, which
    is why this one is measured on the COMPOSED set before the dispatch."""
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MAX_COMPOSED_BYTES + 1),
            headers=authorization(),
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "request_too_large"
    assert provider.count == 0


async def test_the_oversize_request_is_refused_and_not_truncated(
    api, migrate_engine, monkeypatch
) -> None:
    """A-148 is explicit: *"It does not rate-limit by bytes per second, does not
    queue, and does not truncate."* A truncated conversation would produce a
    plausible answer to a question the caller did not ask."""
    await seed_released_world(migrate_engine)
    marker = "THE-TAIL-OF-THE-CONVERSATION"

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        await call(
            api,
            "POST",
            "/chat/completions",
            json_body={
                "model": MODEL,
                "messages": [_message(MAX_COMPOSED_BYTES), {"role": "user", "content": marker}],
            },
            headers=authorization(),
        )

    assert provider.requests == []


async def test_the_refusal_is_counted(api, migrate_engine, monkeypatch) -> None:
    """`prope_gateway_oversize_request_total`, named by A-148 itself. Without it a
    legitimate long-context consumer being refused is invisible until they
    complain."""
    await seed_released_world(migrate_engine)
    before = _oversize()

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MAX_COMPOSED_BYTES + 1),
            headers=authorization(),
        )

    assert _oversize() == before + 1


async def test_the_twenty_first_in_flight_call_on_one_key_is_refused(
    api, migrate_engine, monkeypatch
) -> None:
    """T-013 through the route.

    The twenty slots are held directly rather than by launching twenty real
    requests: what is under test is the ADMISSION decision and its wire shape,
    and twenty concurrent stubbed dispatches would be testing `asyncio.gather`
    while making the assertion depend on scheduling.
    """
    await seed_released_world(migrate_engine)
    held = [admit(KEY_ID) for _ in range(MAX_IN_FLIGHT_PER_KEY)]
    for slot in held:
        slot.__enter__()

    try:
        with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
            response = await call(
                api,
                "POST",
                "/chat/completions",
                json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
                headers=authorization(),
            )
    finally:
        for slot in held:
            slot.__exit__(None, None, None)

    assert response.status_code == 429
    assert response.json()["error"]["type"] == "rate_limit_error"
    assert response.headers["retry-after"] == "1"
    assert provider.count == 0, "a refused request must not be queued, delayed, or dispatched"


async def test_a_second_key_is_unaffected_by_the_first_keys_cap(
    api, migrate_engine, monkeypatch
) -> None:
    """The whole reason A-143 is per key rather than global: the misbehaving key
    is refused, the counter names its bucket, and everyone else is served."""
    await seed_released_world(migrate_engine)
    await seed_key(migrate_engine, SECOND_KEY_ID, scope=(MODEL,))

    held = [admit(KEY_ID) for _ in range(MAX_IN_FLIGHT_PER_KEY)]
    for slot in held:
        slot.__enter__()

    try:
        with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
            response = await call(
                api,
                "POST",
                "/chat/completions",
                json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
                headers=authorization(SECOND_KEY_ID),
            )
    finally:
        for slot in held:
            slot.__exit__(None, None, None)

    assert response.status_code == 200, response.body


async def test_the_cap_is_applied_after_authentication_and_before_dispatch(
    api, migrate_engine, monkeypatch
) -> None:
    """A-143's stated position in the pipeline, asserted from both sides.

    An unauthenticated request at the cap is a `401` and not a `429`, because the
    cap is keyed on a `key_id` that does not exist yet — and answering `429`
    would tell an unauthenticated caller that somebody else's key is busy.
    """
    await seed_released_world(migrate_engine)
    held = [admit(KEY_ID) for _ in range(MAX_IN_FLIGHT_PER_KEY)]
    for slot in held:
        slot.__enter__()

    try:
        with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
            response = await call(
                api,
                "POST",
                "/chat/completions",
                json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
                headers={"authorization": "Bearer prope_key_01J0000000000000000BOGUS_nope"},
            )
    finally:
        for slot in held:
            slot.__exit__(None, None, None)

    assert response.status_code == 401
