"""AC-6 / ADR-0013 — after the first byte the fallback is unreachable, and the stream truncates honestly.

The status line is already `200` and the caller already holds partial content, so
there is no version of this in which a fallback can be *served* — it can only be
**spliced**. ADR-0013 rejects that by name: splicing canned text onto a
half-finished answer produces *"a response that is half model output and half
canned text, joined at an arbitrary token boundary, that no human wrote and no
reviewer approved"*, and the `x-prope-fallback` marker cannot even be set,
because the headers went out before anything went wrong.

So the stream ends with an OpenAI-shaped error chunk and the record says
`truncated` — which carries a real cost, because the provider generated tokens
and charged for them.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.domain import Outcome
from tests.gateway import (
    MODEL,
    UPSTREAM_MODEL,
    VERSION_ID,
    authorization,
    enqueued_records,
    gateway_api,
    seed_released_world,
    stream_call,
    stub_upstream,
)

FALLBACK = "We are unable to assess this refund automatically."

RELAYED_CHUNKS = 10


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _upstream_errors(stage: str) -> float:
    return REGISTRY.get_sample_value("prope_gateway_upstream_error_total", {"stage": stage}) or 0.0


def _calls(outcome: str) -> float:
    return REGISTRY.get_sample_value("prope_gateway_call_total", {"outcome": outcome}) or 0.0


def _chunk(index: int) -> str:
    payload = {
        "id": "cmpl-1",
        "object": "chat.completion.chunk",
        "created": 1_760_000_000,
        "model": UPSTREAM_MODEL,
        "choices": [{"index": 0, "delta": {"content": f"part{index} "}, "finish_reason": None}],
    }
    import json

    return f"data: {json.dumps(payload)}\n\n"


def _dies_after(count: int):  # noqa: ANN202
    """A provider that relays `count` chunks and then drops the connection."""

    async def body() -> AsyncIterator[bytes]:
        for index in range(count):
            yield _chunk(index).encode()
        raise httpx.ReadError("the connection dropped")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body(), headers={"content-type": "text/event-stream"}
        )

    return handler


def _request() -> dict:
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }


async def test_the_relayed_chunks_reach_the_caller_before_the_failure(
    api, migrate_engine, monkeypatch
) -> None:
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _dies_after(RELAYED_CHUNKS)):
        response = await stream_call(
            api, "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200
    body = response.body.decode()
    for index in range(RELAYED_CHUNKS):
        assert f"part{index} " in body


async def test_the_stream_terminates_with_an_openai_shaped_error_chunk(
    api, migrate_engine, monkeypatch
) -> None:
    """An error the caller's SDK can see. A stream that simply stops is
    indistinguishable from a complete short answer, which is the failure mode
    this chunk exists to remove."""
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _dies_after(RELAYED_CHUNKS)):
        response = await stream_call(
            api, "/chat/completions", json_body=_request(), headers=authorization()
        )

    import json

    events = [
        json.loads(line[len("data: ") :])
        for line in response.body.decode().split("\n\n")
        if line.startswith("data: ") and line[len("data: ") :] != "[DONE]"
    ]
    assert "error" in events[-1]
    assert set(events[-1]["error"]) == {"message", "type", "param", "code"}


async def test_no_fallback_text_is_appended(api, migrate_engine, monkeypatch) -> None:
    """The revision HAS a fallback answer and it is not used. This is the whole
    of ADR-0013: the fallback is a pre-first-byte decision, and after that the
    honest answer is a truncated one."""
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _dies_after(RELAYED_CHUNKS)):
        response = await stream_call(
            api, "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert FALLBACK not in response.body.decode()
    assert "x-prope-fallback" not in response.headers


async def test_the_record_says_truncated_and_carries_the_partial_body(
    api, migrate_engine, monkeypatch
) -> None:
    """A-038: streaming responses are accumulated and logged AFTER the stream
    closes, and the accumulation runs alongside the relay rather than in front of
    it. What was actually delivered is what is recorded — including on the path
    where what was delivered is half an answer."""
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _dies_after(RELAYED_CHUNKS)):
        await stream_call(api, "/chat/completions", json_body=_request(), headers=authorization())

    record = enqueued_records()[0]
    assert record.outcome is Outcome.TRUNCATED
    assert record.streaming is True
    assert record.version_id == VERSION_ID
    assert record.body is not None
    assert record.body.response_body.startswith("part0 ")
    assert "part9 " in record.body.response_body


async def test_the_failure_is_counted_as_mid_stream_and_not_as_pre_first_byte(
    api, migrate_engine, monkeypatch
) -> None:
    """ADR-0013: *"`prope_gateway_upstream_error_total` is labelled `stage =
    pre_first_byte | mid_stream`, so the two are never one number."*

    They ask different questions. A pre-first-byte failure is covered by the
    fallback and shows up as canned answers; a mid-stream one reaches the
    consumer as a broken response, and no fallback rate will ever mention it.
    """
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)
    mid_before = _upstream_errors("mid_stream")
    pre_before = _upstream_errors("pre_first_byte")
    truncated_before = _calls("truncated")

    with stub_upstream(monkeypatch, _dies_after(RELAYED_CHUNKS)):
        await stream_call(api, "/chat/completions", json_body=_request(), headers=authorization())

    assert _upstream_errors("mid_stream") == mid_before + 1
    assert _upstream_errors("pre_first_byte") == pre_before
    assert _calls("truncated") == truncated_before + 1


async def test_the_identity_rode_in_the_headers_and_survives_the_truncation(
    api, migrate_engine, monkeypatch
) -> None:
    """A-079: *"On a streaming response the identity rides in the headers and on
    the first chunk, so a caller can record it even if the stream is later
    truncated."* This is the case that sentence was written for."""
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _dies_after(RELAYED_CHUNKS)):
        response = await stream_call(
            api, "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.headers["x-prope-version-id"] == VERSION_ID
    assert response.headers["x-prope-model"] == MODEL

    import json

    first = json.loads(response.body.decode().split("\n\n")[0][len("data: ") :])
    assert first["prope"]["version_id"] == VERSION_ID
