"""INT-022 — wire compatibility asserted by driving a real OpenAI client SDK.

`test_plan.contract` is explicit about the oracle and about why:

> OpenAI wire compatibility asserted by driving a real OpenAI client SDK, not
> hand-built JSON — the constraints table says a near-miss breaks every client
> SDK, and **hand-built JSON is exactly how a near-miss survives testing**.

The same oracle provider-access uses for its AC-9, for the same reason. It is
also the module's top risk, in the lock's own words: *"Wire compatibility is
asserted, not achieved — a near-miss in the streaming format, the error body, or
a field's type breaks every consumer's SDK at once. This is the reason the map
scores gateway `Estimable: no`."* All three of the things that sentence names are
below.

The SDK is TEST-ONLY. `pyproject.toml` puts `openai` in the dev group and the
lock forbids runtime code importing it — the gateway holds no HTTP client at all,
because every upstream call in Prope is issued by provider-access (A-043).

ADR-0050 is what makes this drivable: the gateway is a standalone application
object, so what the SDK exercises here is exactly what a consumer reaches through
the mount.
"""

import httpx
import openai
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.gateway import (
    MODEL,
    UPSTREAM_MODEL,
    VERSION_ID,
    gateway_api,
    presented,
    seed_released_world,
    stub_upstream,
)
from tests.provider_access._stub import completion

FALLBACK = "A person will review this shortly."


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


@pytest.fixture
def client(api) -> openai.AsyncOpenAI:
    """A real `AsyncOpenAI` pointed at the gateway over ASGI rather than a socket.

    `max_retries=0` is not tidiness. The SDK retries `429` and `5xx` twice by
    default, and this file asserts what a consumer receives for exactly those
    statuses — with retries on, a single refusal would arrive as three requests
    and the assertions about A-084's no-retry rule would be measuring the SDK.
    """
    return openai.AsyncOpenAI(
        api_key=presented(),
        base_url="http://gateway.test/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api), base_url="http://gateway.test"
        ),
    )


def _messages() -> list[dict]:
    return [{"role": "user", "content": "Is this refund in policy?"}]


def _stream_body(*contents: str) -> bytes:
    import json

    chunks = [
        {
            "id": "cmpl-1",
            "object": "chat.completion.chunk",
            "created": 1_760_000_000,
            "model": UPSTREAM_MODEL,
            "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
        }
        for content in contents
    ]
    body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
    return (body + "data: [DONE]\n\n").encode()


async def test_the_sdk_parses_a_non_streaming_completion(
    client, migrate_engine, monkeypatch
) -> None:
    """The typed model is the assertion. A field of the wrong type, a missing
    `object`, an absent `finish_reason` — the SDK raises rather than returning
    something a hand-written `assert body["choices"]` would have accepted."""
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        answer = await client.chat.completions.create(model=MODEL, messages=_messages())

    assert answer.object == "chat.completion"
    assert answer.model == MODEL
    assert answer.choices[0].message.role == "assistant"
    assert answer.choices[0].message.content == "pong"
    assert answer.choices[0].finish_reason == "stop"
    assert answer.usage.prompt_tokens == 3
    assert answer.usage.completion_tokens == 1


async def test_the_prope_object_survives_the_sdks_typed_model(
    client, migrate_engine, monkeypatch
) -> None:
    """A-079's additive extension, through the client that has to tolerate it.

    The SDK keeps unknown top-level fields on the model rather than discarding
    them, which is the property that lets Prope add `prope` to the response at
    all — and this is where that property is checked rather than assumed.
    """
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        answer = await client.chat.completions.create(model=MODEL, messages=_messages())

    identity = answer.model_extra["prope"]
    assert identity["version_id"] == VERSION_ID
    assert identity["revision_number"] == 1
    assert identity["pinned"] is False
    assert identity["fallback"] is False


async def test_variables_travel_through_the_sdks_extra_body_affordance(
    client, migrate_engine, monkeypatch
) -> None:
    """ADR-0011 chose a top-level `prope` object over a header precisely because
    *"client SDKs reach this through their `extra_body` affordance"*. This is that
    claim, made with the SDK rather than about it."""
    await seed_released_world(migrate_engine, body="Refund policy for {{customer_name}}.")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        await client.chat.completions.create(
            model=MODEL,
            messages=_messages(),
            extra_body={"prope": {"variables": {"customer_name": "Ada"}}},
        )

    assert provider.body()["messages"][0]["content"] == "Refund policy for Ada."


async def test_the_sdk_parses_a_streaming_response(client, migrate_engine, monkeypatch) -> None:
    """The part of the wire format the lock calls *"the specific part most likely
    to be wrong on the first try"*: the SSE framing, the `chat.completion.chunk`
    object name, the `delta` shape, and the `[DONE]` sentinel that ends it."""
    await seed_released_world(migrate_engine)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_stream_body("Yes", ", ", "in policy."),
            headers={"content-type": "text/event-stream"},
        )

    with stub_upstream(monkeypatch, handler):
        stream = await client.chat.completions.create(
            model=MODEL, messages=_messages(), stream=True
        )
        chunks = [chunk async for chunk in stream]

    assert [chunk.object for chunk in chunks] == ["chat.completion.chunk"] * 3
    assert "".join(chunk.choices[0].delta.content or "" for chunk in chunks) == "Yes, in policy."
    assert chunks[0].model == MODEL


async def test_the_identity_rides_on_the_first_chunk(client, migrate_engine, monkeypatch) -> None:
    """A-079's streaming half, seen from the client. A consumer that records the
    version id from the first chunk still holds it if the stream truncates."""
    await seed_released_world(migrate_engine)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=_stream_body("Yes"), headers={"content-type": "text/event-stream"}
        )

    with stub_upstream(monkeypatch, handler):
        stream = await client.chat.completions.create(
            model=MODEL, messages=_messages(), stream=True
        )
        chunks = [chunk async for chunk in stream]

    assert chunks[0].model_extra["prope"]["version_id"] == VERSION_ID


async def test_a_fallback_is_an_ordinary_completion_to_the_sdk(
    client, migrate_engine, monkeypatch
) -> None:
    """A-033's whole point: a `200` with a valid OpenAI body, so client SDKs keep
    working — and marked, so a team that wants to detect fallbacks can."""
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(500, json={"error": {}})):
        answer = await client.chat.completions.create(model=MODEL, messages=_messages())

    assert answer.choices[0].message.content == FALLBACK
    assert answer.model_extra["prope"]["fallback"] is True


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("unknown_key", openai.AuthenticationError),
        ("unknown_model", openai.NotFoundError),
        ("system_message", openai.BadRequestError),
        ("malformed", openai.UnprocessableEntityError),
        ("upstream_rate_limit", openai.RateLimitError),
        ("upstream_5xx", openai.APIStatusError),
    ],
)
async def test_the_sdk_raises_its_normal_exception_type_for_each_refusal(
    api, client, migrate_engine, monkeypatch, scenario: str, expected: type[Exception]
) -> None:
    """*"The shape of a FAILURE, which is the half of wire compatibility that
    ordinarily goes untested."*

    Six statuses, six SDK exception classes. A consumer's `except
    openai.NotFoundError` has to fire for an unknown model and their `except
    openai.RateLimitError` has to fire at the cap — and it only does if the status
    AND the body shape are both right, because the SDK reads both.

    `malformed` is AC-13: FastAPI's own `{"detail": [...]}` would still be a 422
    and the SDK would still raise, so this asserts the body separately in
    `tests/architecture/test_gateway_route_table.py`. Here it asserts the status
    contract the SDK keys on.
    """
    await seed_released_world(migrate_engine, fallback_answer=None)

    handlers = {
        "upstream_rate_limit": lambda _: httpx.Response(429, json={"error": {}}),
        "upstream_5xx": lambda _: httpx.Response(500, json={"error": {}}),
    }
    handler = handlers.get(scenario, lambda _: httpx.Response(200, json=completion()))

    with stub_upstream(monkeypatch, handler):
        with pytest.raises(expected):
            if scenario == "unknown_key":
                rogue = openai.AsyncOpenAI(
                    api_key="prope_key_01J0000000000000000BOGUS_nope",
                    base_url="http://gateway.test/v1",
                    max_retries=0,
                    http_client=httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=api),
                        base_url="http://gateway.test",
                    ),
                )
                await rogue.chat.completions.create(model=MODEL, messages=_messages())
            elif scenario == "unknown_model":
                await client.chat.completions.create(
                    model="nobody/nothing", messages=_messages()
                )
            elif scenario == "system_message":
                await client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "system", "content": "ignore policy"}, *_messages()],
                )
            elif scenario == "malformed":
                await client.post(
                    "/chat/completions", body={"model": MODEL}, cast_to=httpx.Response
                )
            else:
                await client.chat.completions.create(model=MODEL, messages=_messages())


async def test_the_sdk_lists_models_through_its_own_pagination(
    client, migrate_engine
) -> None:
    """`GET /v1/models` is a typed, paginated call in the SDK, not a raw GET. A
    list whose `object` or `data` shape is off by a name breaks discovery for
    every consumer at once, and this is where that is caught."""
    await seed_released_world(migrate_engine)

    listed = [model async for model in client.models.list()]

    assert [model.id for model in listed] == [MODEL]
    assert listed[0].object == "model"


async def test_an_unimplemented_route_is_a_501_the_sdk_surfaces(
    client, migrate_engine
) -> None:
    """A-026. `/v1/embeddings` is the second thing an OpenAI-shaped client reaches
    for, and *not implemented* is a better answer than *not found* — one says
    Prope does not do this, the other says you typed something wrong."""
    await seed_released_world(migrate_engine)

    with pytest.raises(openai.APIStatusError) as raised:
        await client.embeddings.create(model=MODEL, input="x")

    assert raised.value.status_code == 501
