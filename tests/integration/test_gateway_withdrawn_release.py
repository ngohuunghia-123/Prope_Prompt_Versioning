"""AC-3 — a withdrawn release is a model-not-found, and never the previous revision.

ADR-0009 left this module two obligations and both are here: the miss is counted
as `no_release` rather than as `unknown_model`, so an operator can see a
withdrawal as a withdrawal instead of as a rise in typos; and the gateway *fails
loudly* rather than quietly continuing to serve what it served yesterday.

The third clause is the one worth reading twice: **the fallback answer is NOT
served.** A-034 makes the fallback a cover for a PROVIDER failure, and INT-022
says so in its own words — *"the fallback answer is for a provider failure, never
for a Prope failure; serving stored text when Prope is broken hides the outage"*.
A withdrawal is a decision somebody made, which makes serving canned text in its
place the worst possible reading of that decision.
"""

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.gateway.cache import resolution_cache
from tests.gateway import (
    MODEL,
    PROMPT_ID,
    authorization,
    gateway_api,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion

FALLBACK = "We cannot answer that right now."

WITHDRAW = text(
    "UPDATE registry.prompt_property SET released_version_id = NULL, released_at = NULL "
    "WHERE id = :prompt_id"
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _miss(reason: str) -> float:
    return REGISTRY.get_sample_value("prope_gateway_resolve_miss_total", {"reason": reason}) or 0.0


def _request(model: str = MODEL) -> dict:
    return {"model": model, "messages": [{"role": "user", "content": "hi"}]}


async def _withdraw(migrate_engine) -> None:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        await connection.execute(WITHDRAW, {"prompt_id": PROMPT_ID})


async def test_a_withdrawn_prompt_answers_model_not_found(
    api, migrate_engine, monkeypatch
) -> None:
    await seed_released_world(migrate_engine)
    await _withdraw(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
    assert provider.count == 0


async def test_the_previous_revision_is_not_served(api, migrate_engine, monkeypatch) -> None:
    """The prompt and its Approved revision both still exist — nothing is deleted
    by a withdrawal — so serving *the last thing that worked* is exactly the
    mistake available here, and it is the one somebody would call helpful.

    The cache is expired between the two calls rather than waited out. The 30 s
    window during which the previous revision IS still served is designed
    behaviour rather than an incident (ADR-0012), and it is AC-9's subject in
    `tests/e2e/test_gateway_cache_ttl.py`. What is asserted here is the other
    side of that window: once the entry is gone, resolution answers not-found and
    does not reach for the revision that used to be released.
    """
    await seed_released_world(migrate_engine, body="Decide refunds strictly.")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        served = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )
        assert served.status_code == 200, served.body

        await _withdraw(migrate_engine)
        resolution_cache().clear()

        after = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert after.status_code == 404
    assert provider.count == 1, "the withdrawn prompt was dispatched anyway"


async def test_the_fallback_answer_is_not_served_for_a_withdrawal(
    api, migrate_engine, monkeypatch
) -> None:
    """A-034 and INT-022. The revision HAS a fallback answer and it stays
    unserved: a fallback covers a provider outage, and a withdrawal is a decision
    a person made. Serving stored text here would hide the outage and would
    quietly overrule the person who withdrew it."""
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)
    await _withdraw(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 404
    assert FALLBACK not in response.body.decode()
    assert "x-prope-fallback" not in response.headers


async def test_no_release_is_counted_apart_from_a_name_that_never_existed(
    api, migrate_engine, monkeypatch
) -> None:
    """ADR-0009's blast-radius signal, and the reason the two labels exist.

    One 404 to the caller, two lines in the metric. `GatewayNoReleaseSpike` reads
    the `no_release` line against a 7-day baseline, and it is what a withdrawal
    or an unnoticed retire looks like from the traffic side — which is the only
    side it is visible from, since release-control may not read traffic data.
    """
    await seed_released_world(migrate_engine)
    await _withdraw(migrate_engine)

    no_release_before = _miss("no_release")
    unknown_before = _miss("unknown_model")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    assert _miss("no_release") == no_release_before + 1
    assert _miss("unknown_model") == unknown_before, (
        "a withdrawal is not a typo, and the metric is the only place the two are distinguishable"
    )


async def test_a_name_that_never_existed_is_counted_as_unknown_when_the_key_may_see_it(
    api, migrate_engine, monkeypatch
) -> None:
    """The other half of the label pair, with the scope out of the way.

    The key is scoped to a name nobody registered, so `may_resolve` allows it and
    the registry is the thing that answers — which is the only arrangement in
    which `unknown_model` is reachable at all.
    """
    await seed_released_world(migrate_engine, scope=(MODEL, "support/never-registered"))
    before = _miss("unknown_model")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request("support/never-registered"),
            headers=authorization(),
        )

    assert response.status_code == 404
    assert _miss("unknown_model") == before + 1


async def test_the_withdrawn_prompt_disappears_from_the_model_list(
    api, migrate_engine
) -> None:
    """A-082 and the same pointer. `GET /v1/models` lists prompts with a CURRENT
    release, so a withdrawal removes it from the catalogue a consumer discovers
    prompts through, not only from the calls they already make."""
    await seed_released_world(migrate_engine)

    listed = await call(api, "GET", "/models", headers=authorization())
    assert [row["id"] for row in listed.json()["data"]] == [MODEL]

    await _withdraw(migrate_engine)

    after = await call(api, "GET", "/models", headers=authorization())
    assert after.json()["data"] == []
