"""ADR-0069 — a routed request holds ONE slot against A-143's cap, however far it walks.

`admit(key.key_id)` wraps the whole of `_serve`, so the loop runs *inside* one
slot. That is the difference between failover being cover and failover being an
amplifier: a request that took a slot per rung would let a single failing
provider cut a consumer's effective concurrency by the length of its route, and
the cap would start refusing traffic at a fifth of the volume it was sized for —
at exactly the moment the workspace most needs the backup to work.

The property is invisible from outside a request, so it is read off
`prope_gateway_inflight` while the loop is mid-walk. A gauge sampled from inside
the stub is the only vantage point that can see it at all.
"""

import json

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.gateway.admission import MAX_IN_FLIGHT_PER_KEY
from tests.gateway import (
    BACKUP_MODEL,
    MODEL,
    UPSTREAM_MODEL,
    authorization,
    gateway_api,
    seed_routed_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _request() -> dict:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}


def _in_flight() -> float:
    return REGISTRY.get_sample_value("prope_gateway_inflight") or 0.0


async def test_three_attempts_hold_one_slot_between_them(
    api, migrate_engine, monkeypatch
) -> None:
    """Sampled at every rung, and the answer must be 1 each time.

    A three-rung route: two failures and a success, so the gauge is read at the
    start of the walk, in the middle of it, and at the rung that answers.
    """
    await seed_routed_world(
        migrate_engine,
        entries=(
            ("prv_01J000000000000000PROV1", UPSTREAM_MODEL),
            ("prv_01J000000000000000PROV2", BACKUP_MODEL),
            # A third rung on the backup configuration with a cheaper model —
            # the same provider with a DIFFERENT model is a legal rung, and the
            # cheapest way to walk three of them without a third credential.
            ("prv_01J000000000000000PROV2", "gpt-4o-mini-backup"),
        ),
    )

    sampled: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        sampled.append(_in_flight())
        if model == "gpt-4o-mini-backup":
            return httpx.Response(200, json=completion(model=model))
        return httpx.Response(500, json={"error": {"message": "upstream is unwell"}})

    with stub_upstream(monkeypatch, handler) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    assert provider.count == 3
    assert response.headers["x-prope-route-entry"] == "3"
    assert sampled == [1.0, 1.0, 1.0], sampled


async def test_the_slot_is_returned_after_an_exhausted_route(
    api, migrate_engine, monkeypatch
) -> None:
    """However the request ends, including when every rung failed.

    A slot leaked on the failure path would be worse than one leaked on the
    success path: it accumulates precisely while a provider is down, so the cap
    would tighten as the outage went on and a consumer would be refused for
    something Prope did.
    """
    await seed_routed_world(migrate_engine)

    def fails(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "upstream is unwell"}})

    with stub_upstream(monkeypatch, fails) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert provider.count == 2
    assert response.status_code != 200
    assert _in_flight() == 0.0


def test_the_cap_is_unchanged_by_routing() -> None:
    """A-143's number is about requests, not about upstream calls.

    Stated here rather than assumed: if the cap ever became per-attempt, the two
    tests above would still pass while the guarantee they exist for was gone.
    """
    assert MAX_IN_FLIGHT_PER_KEY == 20
