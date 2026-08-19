"""The SDK against the real gateway, with only the provider stubbed. ADR-0065.

`sdk/python/tests/` pins what the SDK *does* against a mocked HTTP layer. This
file pins that what it does is what the gateway *accepts* — the two halves of a
contract that now spans two distributables, one of which runs in somebody else's
process at a version Prope cannot force (OQ-152).

Driven through `httpx.ASGITransport` against the gateway application mounted at
`/v1`, which is where `main.py` mounts it and therefore where a customer's
`base_url` points. Mounting it here rather than pointing the SDK at the bare
router is the difference between testing the contract and testing around it: the
SDK owns the `/v1` path segment, and a test that let it address `/chat/completions`
would pass while every real installation 404ed.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from prope_sdk import AsyncPrope, CallerSystemMessage, ModelNotFound
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.gateway import (
    MODEL,
    SECRET,
    UPSTREAM_MODEL,
    VERSION_ID,
    gateway_api,
    presented,
    seed_released_world,
    stub_upstream,
)
from tests.provider_access._stub import completion

USER = [{"role": "user", "content": "Is this refund in policy?"}]


@pytest.fixture
def mounted(app_sessionmaker: async_sessionmaker[AsyncSession]):
    """The gateway where production puts it: under `/v1` on a parent app."""
    with gateway_api(app_sessionmaker) as gateway:
        parent = FastAPI()
        parent.mount("/v1", gateway)
        yield parent


def sdk(app: FastAPI, secret: str = SECRET) -> AsyncPrope:
    return AsyncPrope(
        presented(secret=secret),
        "http://testserver",
        client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app)),
    )


async def test_the_sdk_calls_a_released_prompt_and_learns_which_revision_served_it(
    mounted, migrate_engine, monkeypatch
) -> None:
    """The whole SDK in one request, and the assertion that matters most:
    `version_id` came back, so an application can log what answered without ever
    having seen the prompt."""
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        async with sdk(mounted) as prope:
            answer = await prope.chat(MODEL, messages=USER)

    assert provider.count == 1
    assert answer.text == "pong"
    assert answer.model == MODEL
    assert answer.version_id == VERSION_ID
    assert answer.revision == 1
    assert answer.upstream_model == UPSTREAM_MODEL
    assert answer.call_id, "the call id is what the next step of a chain sends as its parent"


async def test_the_sdk_never_receives_a_prompt_body(mounted, migrate_engine, monkeypatch) -> None:
    """ADR-0065's hard rule, asserted against a live response rather than a mock.

    The revision's body is `You are a helpful assistant.` (the factory default).
    It becomes the system message the provider sees, and it must appear nowhere
    in what comes back to the caller.
    """
    await seed_released_world(migrate_engine, body="SECRET-BODY-DO-NOT-LEAK")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        async with sdk(mounted) as prope:
            answer = await prope.chat(MODEL, messages=USER)

    assert "SECRET-BODY-DO-NOT-LEAK" not in str(answer.raw)
    assert "SECRET-BODY-DO-NOT-LEAK" not in answer.text


async def test_the_gateway_agrees_that_a_system_message_is_refused(
    mounted, migrate_engine, monkeypatch
) -> None:
    """The SDK refuses locally; this asserts it is refusing the same thing.

    A local check that had drifted from the server's rule would be worse than no
    check: it would reject calls the gateway accepts, in a client nobody can
    patch remotely.
    """
    await seed_released_world(migrate_engine)

    async with sdk(mounted) as prope:
        with pytest.raises(CallerSystemMessage):
            await prope.chat(
                MODEL, messages=[{"role": "system", "content": "..."}, *USER]
            )

        # And the same request, forced past the local check, is refused by the
        # gateway with the code the SDK claims.
        response = await prope._client.post(
            "http://testserver/v1/chat/completions",
            json={"model": MODEL, "messages": [{"role": "system", "content": "..."}, *USER]},
            headers={"authorization": f"Bearer {presented()}"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "system_message_not_allowed"


async def test_a_chain_threads_itself_through_a_live_gateway(
    mounted, migrate_engine, monkeypatch
) -> None:
    """`Conversation` against real call ids rather than a stub's.

    The ids come from `x-prope-call-id` on each response, so this is the test
    that would catch the gateway renaming that header — which would leave every
    step of every customer's chain a root, silently.
    """
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        async with sdk(mounted) as prope:
            chain = prope.conversation("conv_sdk_test")
            first = await chain.chat(MODEL, messages=USER)
            assert chain.last_call_id == first.call_id

            second = await chain.chat(MODEL, messages=USER)

    assert first.call_id and second.call_id
    assert first.call_id != second.call_id
    assert second.conversation_id == "conv_sdk_test"


async def test_an_out_of_scope_prompt_raises_model_not_found(
    mounted, migrate_engine, monkeypatch
) -> None:
    """A-116 reaching the caller as the exception the SDK documents."""
    await seed_released_world(migrate_engine, scope=())

    async with sdk(mounted) as prope:
        with pytest.raises(ModelNotFound) as raised:
            await prope.chat(MODEL, messages=USER)

    assert raised.value.code == "model_not_found"


async def test_models_lists_what_the_key_may_resolve(mounted, migrate_engine) -> None:
    await seed_released_world(migrate_engine)

    async with sdk(mounted) as prope:
        assert await prope.models() == [MODEL]


async def test_streaming_through_the_sdk_reassembles_the_answer(
    mounted, migrate_engine, monkeypatch
) -> None:
    """Proves the SSE framing the gateway emits is the framing `_wire` parses."""
    from tests.provider_access._stub import sse

    frames = sse(
        {"choices": [{"index": 0, "delta": {"content": "po"}}]},
        {"choices": [{"index": 0, "delta": {"content": "ng"}}]},
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=frames, headers={"content-type": "text/event-stream"})

    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, handler):
        async with sdk(mounted) as prope:
            text = ""
            async for chunk in prope.stream(MODEL, messages=USER):
                text += chunk.text

    assert text == "pong"
