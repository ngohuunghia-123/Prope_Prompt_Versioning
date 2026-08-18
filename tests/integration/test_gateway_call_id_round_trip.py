"""ADR-0058 — the caller can learn the id of the call it just made, and send it back.

`prope.parent_call_id` is the field that turns a bag of calls into a chain, and
it names a `call_id` **Prope** generated. So there is exactly one question that
decides whether the conversation graph is a feature or a field nobody can fill:
*how does the caller find out what this call was called?*

Until this test existed the answer was that it could not. `ServedIdentity.stamp`
set `model` and `prope` and passed the provider's own `id` straight through, so a
client copying the response `id` into the next request's `parent_call_id` sent
`cmpl-1` — which the validator refuses, by design, because an id that matches no
call would otherwise render as a silent second root.

So the id is Prope's on every path, and it also rides in a header, because a
streaming caller has the headers before it has a body.
"""

import json

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.gateway.domain import CALL_ID_PREFIX, CHATCMPL_PREFIX
from tests.gateway import (
    MODEL,
    UPSTREAM_MODEL,
    authorization,
    enqueued_records,
    gateway_api,
    seed_released_world,
    stream_call,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion

CONVERSATION = "conv-round-trip"

#: The stub provider's own id. Named here because the assertion that matters most
#: in this file is that it never reaches the caller.
PROVIDER_ID = "cmpl-1"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _request(**extra) -> dict:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hi"}], **extra}


def _chunk(index: int) -> str:
    payload = {
        "id": PROVIDER_ID,
        "object": "chat.completion.chunk",
        "created": 1_760_000_000,
        "model": UPSTREAM_MODEL,
        "choices": [{"index": 0, "delta": {"content": f"part{index} "}, "finish_reason": None}],
    }
    return f"data: {json.dumps(payload)}\n\n"


def _relays(count: int):  # noqa: ANN202
    async def body():
        for index in range(count):
            yield _chunk(index).encode()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body(), headers={"content-type": "text/event-stream"})

    return handler


def _events(response) -> list[dict]:  # noqa: ANN001
    return [
        json.loads(line[len("data: ") :])
        for line in response.body.decode().split("\n\n")
        if line.startswith("data: ") and line[len("data: ") :] != "[DONE]"
    ]


async def test_the_header_carries_the_call_id_that_was_recorded(
    api, migrate_engine, monkeypatch
) -> None:
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    served = response.headers["x-prope-call-id"]
    assert served.startswith(CALL_ID_PREFIX)
    assert [record.call_id for record in enqueued_records()] == [served]


async def test_the_body_id_is_the_call_id_and_never_the_providers(
    api, migrate_engine, monkeypatch
) -> None:
    """The provider's id is overwritten rather than passed through.

    Not cosmetic. `id` is the only handle the caller has on the row Prope wrote,
    and a response whose id names a third party's record is a traceability claim
    that stops at the boundary — which is the one claim this product is for.
    """
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    body = json.loads(response.body)
    assert body["id"] != PROVIDER_ID
    assert body["id"] == CHATCMPL_PREFIX + response.headers["x-prope-call-id"]


async def test_every_streamed_chunk_carries_the_same_call_id(
    api, migrate_engine, monkeypatch
) -> None:
    """Every chunk, not only the one the identity rides on.

    A client that keeps the last chunk it read — which is what an accumulating
    SDK does — would otherwise end the stream holding the provider's id, and the
    field would work or not work depending on which chunk happened to survive.
    """
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, _relays(4)):
        response = await stream_call(
            api, "/chat/completions", json_body=_request(stream=True), headers=authorization()
        )

    served = response.headers["x-prope-call-id"]
    ids = {event["id"] for event in _events(response)}
    assert ids == {CHATCMPL_PREFIX + served}


async def test_the_fallback_path_and_the_relay_path_agree(
    api, migrate_engine, monkeypatch
) -> None:
    """The fallback answer has always been stamped with the call id. Now both are.

    Before, `id` meant *Prope's call* when the provider was down and *the
    provider's completion* when it was up — the same field naming two different
    things depending on a third party's availability.
    """
    await seed_released_world(migrate_engine, fallback_answer="We cannot answer right now.")

    def refuse(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "down"}})

    with stub_upstream(monkeypatch, refuse):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    body = json.loads(response.body)
    assert body["id"] == CHATCMPL_PREFIX + response.headers["x-prope-call-id"]
    assert body["prope"]["fallback"] is True


async def test_the_id_it_handed_back_is_accepted_as_the_next_calls_parent(
    api, migrate_engine, monkeypatch
) -> None:
    """The whole round trip, which is the only thing that proves the field usable.

    Two calls, the second naming the first exactly as it was handed over —
    prefix included, because that is what a caller copies. What the ledger stores
    is the bare id, which is what the graph query joins on.
    """
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        first = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(prope={"conversation_id": CONVERSATION}),
            headers=authorization(),
        )
        handed_back = json.loads(first.body)["id"]

        second = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(
                prope={"conversation_id": CONVERSATION, "parent_call_id": handed_back}
            ),
            headers=authorization(),
        )

    assert second.status_code == 200, second.body

    records = enqueued_records()
    assert [record.parent_call_id for record in records] == [None, records[0].call_id]
    assert {record.conversation_id for record in records} == {CONVERSATION}
