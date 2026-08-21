"""The transports, against a stubbed HTTP layer rather than a live gateway.

`httpx.MockTransport` keeps these fast and dependency-free. The counterpart that
runs against the **real** gateway app with a stubbed provider lives in the
service repository at `tests/integration/test_sdk_calls_the_gateway.py` — this
file pins client behaviour, that one pins that the two agree.
"""

from __future__ import annotations

import json

import httpx
import pytest

from prope_sdk import AsyncPrope, CallerSystemMessage, GatewayUnavailable, ModelNotFound, Prope

USER = [{"role": "user", "content": "Where is my refund?"}]

COMPLETION = {
    "id": "cmpl-1",
    "model": "support/refund-classifier",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}}],
    "prope": {"version_id": "ver_1", "revision_number": 2, "pinned": False, "fallback": False},
}


def _client(handler, **kwargs) -> Prope:
    return Prope(
        "prope_key_test", "https://prope.example", client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs
    )


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=COMPLETION, headers={"x-prope-call-id": "call_1"})


# --- the request that actually leaves ---------------------------------------


def test_the_authorization_header_is_a_bearer_key() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return _ok(request)

    _client(handler).chat("support/x", messages=USER)

    assert seen["authorization"] == "Bearer prope_key_test"
    assert seen["user-agent"].startswith("prope-sdk-python/")


def test_a_base_url_that_already_ends_in_v1_does_not_produce_v1_v1() -> None:
    """The most common configuration mistake in every OpenAI-compatible client.
    Normalised rather than diagnosed."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _ok(request)

    Prope(
        "k", "https://prope.example/v1/", client=httpx.Client(transport=httpx.MockTransport(handler))
    ).chat("support/x", messages=USER)

    assert seen == ["https://prope.example/v1/chat/completions"]


def test_a_system_message_never_reaches_the_network() -> None:
    """Refused locally, so the assertion is that the handler was never called."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _ok(request)

    with pytest.raises(CallerSystemMessage):
        _client(handler).chat(
            "support/x", messages=[{"role": "system", "content": "..."}, *USER]
        )

    assert calls == []


def test_a_bad_conversation_id_fails_where_it_was_chosen() -> None:
    with pytest.raises(ValueError, match="conversation_id"):
        _client(_ok).chat("support/x", messages=USER, conversation_id="has spaces")


# --- the answer -------------------------------------------------------------


def test_chat_returns_the_identity_of_the_revision_that_served_it() -> None:
    answer = _client(_ok).chat("support/x", messages=USER)

    assert answer.text == "pong"
    assert (answer.version_id, answer.revision, answer.call_id) == ("ver_1", 2, "call_1")


def test_a_refusal_becomes_a_typed_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"error": {"message": "no such model", "code": "model_not_found", "param": "model"}},
        )

    with pytest.raises(ModelNotFound) as raised:
        _client(handler).chat("support/x", messages=USER)

    assert raised.value.code == "model_not_found"


def test_an_unreachable_gateway_is_its_own_exception() -> None:
    """Distinct from `UpstreamError`, because this one means Prope did not work
    — and it is the failure an application most needs to handle deliberately."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    with pytest.raises(GatewayUnavailable):
        _client(handler).chat("support/x", messages=USER)


def test_models_lists_what_this_key_may_resolve() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"object": "list", "data": [{"id": "support/a"}, {"id": "billing/b"}]})

    assert _client(handler).models() == ["support/a", "billing/b"]


# --- chains -----------------------------------------------------------------


def test_a_conversation_threads_every_step_and_the_first_one_is_a_root() -> None:
    """The property the whole class exists for: step two names step one, without
    the caller holding an id."""
    bodies: list[dict] = []
    ids = iter(["call_1", "call_2", "call_3"])

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=COMPLETION, headers={"x-prope-call-id": next(ids)})

    prope = _client(handler)
    with prope.conversation("conv_abc") as chain:
        chain.chat("support/planner", messages=USER)
        chain.chat("support/answer", messages=USER)
        chain.chat("support/guard", messages=USER)

    assert bodies[0]["prope"] == {"conversation_id": "conv_abc"}
    assert bodies[1]["prope"] == {"conversation_id": "conv_abc", "parent_call_id": "call_1"}
    assert bodies[2]["prope"] == {"conversation_id": "conv_abc", "parent_call_id": "call_2"}


def test_a_generated_conversation_id_satisfies_the_gateways_own_pattern() -> None:
    prope = _client(_ok)
    chain = prope.conversation()

    assert 1 <= len(chain.conversation_id) <= 64
    assert chain.conversation_id.isalnum()


def test_the_answer_carries_the_conversation_back() -> None:
    """The gateway does not echo it — it is the caller's own value — so a caller
    logging one object would otherwise be missing the field that finds the call
    again."""
    prope = _client(_ok)
    with prope.conversation("conv_abc") as chain:
        answer = chain.chat("support/x", messages=USER)

    assert answer.conversation_id == "conv_abc"


def test_a_branch_fans_out_from_one_parent_rather_than_chaining() -> None:
    """Three critics on one draft: each names the draft, not each other."""
    bodies: list[dict] = []
    ids = iter(["call_1", "call_2", "call_3"])

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=COMPLETION, headers={"x-prope-call-id": next(ids)})

    prope = _client(handler)
    chain = prope.conversation("conv_abc")
    chain.chat("support/draft", messages=USER)

    left, right = chain.branch(), chain.branch()
    left.chat("support/critic-a", messages=USER)
    right.chat("support/critic-b", messages=USER)

    assert bodies[1]["prope"]["parent_call_id"] == "call_1"
    assert bodies[2]["prope"]["parent_call_id"] == "call_1"


# --- streaming --------------------------------------------------------------


def _sse(*frames: dict) -> bytes:
    return b"".join(f"data: {json.dumps(frame)}\n\n".encode() for frame in frames) + b"data: [DONE]\n\n"


def test_streaming_yields_deltas_and_concatenates_to_the_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse(
                {"choices": [{"delta": {"content": "he"}}]},
                {"choices": [{"delta": {"content": "llo"}}]},
            ),
            headers={"content-type": "text/event-stream"},
        )

    text = "".join(chunk.text for chunk in _client(handler).stream("support/x", messages=USER))

    assert text == "hello"


def test_a_refusal_before_the_first_byte_is_json_and_still_raises() -> None:
    """A stream request refused at admission never becomes an event stream, so a
    client that assumed SSE from the request would report nothing at all."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"message": "no", "code": "model_not_found"}})

    with pytest.raises(ModelNotFound):
        list(_client(handler).stream("support/x", messages=USER))


# --- async ------------------------------------------------------------------


async def test_the_async_client_sends_the_same_request() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=COMPLETION, headers={"x-prope-call-id": "call_1"})

    async with AsyncPrope(
        "prope_key_test",
        "https://prope.example",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    ) as prope:
        answer = await prope.chat("support/x", messages=USER, variables={"tier": "gold"})

    assert answer.version_id == "ver_1"
    assert bodies[0]["prope"] == {"variables": {"tier": "gold"}}


async def test_an_async_conversation_threads_too() -> None:
    bodies: list[dict] = []
    ids = iter(["call_1", "call_2"])

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=COMPLETION, headers={"x-prope-call-id": next(ids)})

    async with AsyncPrope(
        "k", "https://prope.example", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ) as prope:
        chain = prope.conversation("conv_abc")
        await chain.chat("support/a", messages=USER)
        await chain.chat("support/b", messages=USER)

    assert bodies[1]["prope"]["parent_call_id"] == "call_1"
