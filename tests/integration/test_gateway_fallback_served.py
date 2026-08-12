"""AC-4 — an upstream failure before the first byte is answered with the revision's fallback.

A-033 makes it a `200` carrying a valid OpenAI body, so client SDKs keep working,
and marks it in three places — the `x-prope-fallback` header, `prope.fallback` in
the body, and `outcome = fallback` on the call record. All three, because *"an
unmarked 200 is worse than an error: the consuming product ships a canned answer
to a real user believing it came from the model, and nobody ever finds out"*.

The zero tokens and zero cost are not a rounding convenience either — counting a
zero-token fallback as a cheap success would make a broken provider look like a
cost improvement on the review screen.
"""

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.domain import Outcome
from tests.gateway import (
    MODEL,
    VERSION_ID,
    authorization,
    enqueued_records,
    gateway_api,
    seed_released_world,
    stream_call,
    stub_upstream,
)
from tests.integration._asgi import call

FALLBACK = "We are unable to assess this refund automatically. A person will review it."


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _fallbacks(reason: str) -> float:
    return REGISTRY.get_sample_value("prope_gateway_fallback_total", {"reason": reason}) or 0.0


def _upstream_errors(stage: str) -> float:
    return (
        REGISTRY.get_sample_value("prope_gateway_upstream_error_total", {"stage": stage}) or 0.0
    )


def _request(**extra) -> dict:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hi"}], **extra}


def _fails(status: int):  # noqa: ANN202
    return lambda _: httpx.Response(status, json={"error": {"message": "upstream is unwell"}})


async def test_the_caller_receives_a_200_carrying_the_fallback_answer(
    api, migrate_engine, monkeypatch
) -> None:
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _fails(500)):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    body = response.json()
    assert body["choices"][0]["message"]["content"] == FALLBACK
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["finish_reason"] == "stop"


async def test_it_is_marked_in_the_header_and_in_the_body(
    api, migrate_engine, monkeypatch
) -> None:
    """Two of A-033's three markers. SDKs that ignore unknown fields still work,
    and a team that wants to detect fallbacks can — at the transport layer or in
    the body, whichever their client makes reachable."""
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _fails(500)):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.headers["x-prope-fallback"] == "true"
    assert response.headers["x-prope-version-id"] == VERSION_ID
    assert response.json()["prope"]["fallback"] is True
    assert response.json()["prope"]["version_id"] == VERSION_ID


async def test_the_call_record_says_fallback_with_no_tokens_and_no_cost(
    api, migrate_engine, monkeypatch
) -> None:
    """A-033's third marker, and the reason it must not be a cheap success.

    Both token columns are NULL together rather than zero — an absent figure asks
    a question and a zero answers it (ADR-0019) — and `cost` is not this module's
    to set at all: the writer prices from the price row in force at the record's
    own `created_at`, and a caller able to supply a cost is a caller able to
    supply a zero.
    """
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _fails(500)):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    record = enqueued_records()[0]
    assert record.outcome is Outcome.FALLBACK
    assert record.fallback is True
    assert record.version_id == VERSION_ID
    assert record.input_tokens is None
    assert record.output_tokens is None


@pytest.mark.parametrize("status", [500, 502, 503, 429, 401])
async def test_every_fallback_eligible_upstream_failure_reaches_the_fallback(
    api, migrate_engine, monkeypatch, status: int
) -> None:
    """5xx, rate limit and a rejected credential. provider-access classifies the
    failure and this module reads `fallback_eligible` rather than re-deriving it
    (A-095, ADR-0017) — a copy of that table here would be the second of two that
    drift, and deciding whether a failure is upstream or caller-side needs
    provider knowledge this module does not have."""
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _fails(status)):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    assert response.headers["x-prope-fallback"] == "true"


async def test_the_fallback_is_counted_by_the_failure_that_reached_for_it(
    api, migrate_engine, monkeypatch
) -> None:
    """`prope_gateway_fallback_total{reason}` and
    `prope_gateway_upstream_error_total{stage="pre_first_byte"}`.

    Two counters rather than one, because *why* a fallback fired and *when* the
    upstream failed are different questions: `GatewayFallbackRateHigh` reads the
    first and the mid-stream half of the second is a case the fallback cannot
    reach at all.
    """
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)
    rate_limited_before = _fallbacks("rate_limited")
    stage_before = _upstream_errors("pre_first_byte")

    with stub_upstream(monkeypatch, _fails(429)):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    assert _fallbacks("rate_limited") == rate_limited_before + 1
    assert _upstream_errors("pre_first_byte") == stage_before + 1


async def test_a_streaming_caller_receives_the_fallback_as_a_stream(
    api, migrate_engine, monkeypatch
) -> None:
    """A streaming request that fails before its first byte is still pre-first-byte.

    ADR-0013's rule is about what the CALLER has received, not about what shape
    they asked for — the status line has not been sent, so the fallback is still
    reachable, and it arrives in the wire format the caller's SDK is already
    parsing.
    """
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _fails(503)):
        response = await stream_call(
            api,
            "/chat/completions",
            json_body=_request(stream=True),
            headers=authorization(),
        )

    assert response.status_code == 200, response.body
    assert response.headers["x-prope-fallback"] == "true"
    body = response.body.decode()
    assert FALLBACK in body
    assert body.rstrip().endswith("data: [DONE]")


async def test_no_retry_is_made_on_the_callers_behalf(
    api, migrate_engine, monkeypatch
) -> None:
    """A-084 and A-088, asserted by counting requests rather than by promising.

    *"A retry inside a latency-critical path doubles the worst case to buy an
    outcome the fallback already covers."* The gateway enforces this by not
    calling again, which is only observable from the provider's side.
    """
    await seed_released_world(migrate_engine, fallback_answer=FALLBACK)

    with stub_upstream(monkeypatch, _fails(500)) as provider:
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    assert provider.count == 1
