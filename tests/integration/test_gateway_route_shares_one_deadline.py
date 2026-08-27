"""ADR-0069 — one deadline for the whole request, however many entries it walks.

**This file guards the claim that lets ADR-0069 amend ADR-0013 rather than waive
it.** ADR-0013 and A-084 rejected retry on two grounds. The second — *"it
multiplies load against a provider that is already failing"* — does not apply,
because a route goes to a different provider. The first — *"a retry doubles the
worst case inside the strictest latency budget in the system"* — is only
answered if `DEADLINE_MS` is the budget for the WHOLE request rather than for
one attempt.

That is not a property anybody can read off a response. A caller who gets a 200
from rung 2 cannot tell whether rung 2 was given the remaining budget or a fresh
one, and the difference only shows up as a p99 nobody can explain months later.
So the deadline handed to each dispatch is captured directly.

The streaming half lives here too, for the same reason: a lazy relay hides a
pre-first-byte failure until the first item is pulled, so where the loop pulls
that item is exactly where the streaming failover boundary sits — and getting it
wrong means a stream that has already started gets a second provider spliced
onto it, which is ADR-0013's hybrid-response argument arriving through a
different door.
"""

import json
from collections.abc import AsyncIterator

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.domain import Outcome
from prope.gateway import routes
from tests.gateway import (
    BACKUP_MODEL,
    MODEL,
    UPSTREAM_MODEL,
    authorization,
    enqueued_records,
    gateway_api,
    seed_routed_world,
    stream_call,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion, sse


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _request(**extra) -> dict:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hi"}], **extra}


def _by_model(**answers):  # noqa: ANN003, ANN202
    """Route the stub on the upstream model the request names.

    An answer may be a prepared `httpx.Response` or a callable that builds one —
    the streaming cases need the latter, because a response body is consumed
    once and a rung asked twice would answer the second time with nothing.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        answer = answers[json.loads(request.content)["model"]]
        return answer(request) if callable(answer) else answer

    return handler


def _fails(status: int) -> httpx.Response:
    return httpx.Response(status, json={"error": {"message": "upstream is unwell"}})


def _exhausted(reason: str) -> float:
    return (
        REGISTRY.get_sample_value("prope_gateway_route_exhausted_total", {"reason": reason}) or 0.0
    )


def _deadline_spy(monkeypatch) -> list[int]:  # noqa: ANN001
    """Every `deadline_ms` the gateway hands to `dispatch`, in order.

    Wraps the real function rather than replacing it, so the calls still go
    through provider-access and the stub still answers them — a fake dispatch
    would capture the argument and prove nothing about the request that was
    actually made.
    """
    captured: list[int] = []
    real = routes.dispatch

    async def spy(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        captured.append(kwargs["deadline_ms"])
        return await real(*args, **kwargs)

    monkeypatch.setattr(routes, "dispatch", spy)
    return captured


async def test_each_entry_is_given_what_is_left_of_one_budget(
    api, migrate_engine, monkeypatch
) -> None:
    """Strictly decreasing, and the first is never more than `DEADLINE_MS`.

    Two attempts under one budget: the worst case stays 60 s whether a revision
    binds one pair or five, which is what makes *"a retry doubles the worst
    case"* answered by construction rather than by argument.
    """
    await seed_routed_world(migrate_engine)
    deadlines = _deadline_spy(monkeypatch)

    with stub_upstream(
        monkeypatch,
        _by_model(
            **{
                UPSTREAM_MODEL: _fails(500),
                BACKUP_MODEL: httpx.Response(200, json=completion(model=BACKUP_MODEL)),
            }
        ),
    ):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    assert len(deadlines) == 2, deadlines
    assert deadlines[0] <= routes.DEADLINE_MS
    assert deadlines[1] < deadlines[0], "the second attempt was given a fresh deadline"
    assert deadlines[1] > 0


async def test_a_spent_budget_stops_the_route_before_the_next_entry(
    api, migrate_engine, monkeypatch
) -> None:
    """`MIN_ATTEMPT_MS` is a floor, and below it a further attempt is theatre.

    With the budget monkeypatched under the floor, rung 2 is never dispatched:
    the caller would otherwise wait for an attempt that cannot finish and be
    handed a timeout that says nothing about why the route failed. What they get
    instead is the last real error.

    `GatewayRouteBudgetExhausted` watches this counter, and it is a ticket
    precisely because the rule is not supposed to bind: when it does, the route
    was decoration for those requests.
    """
    await seed_routed_world(migrate_engine)
    monkeypatch.setattr(routes, "DEADLINE_MS", routes.MIN_ATTEMPT_MS)
    before = _exhausted("budget_exhausted")

    with stub_upstream(
        monkeypatch,
        _by_model(
            **{
                UPSTREAM_MODEL: _fails(500),
                BACKUP_MODEL: httpx.Response(200, json=completion(model=BACKUP_MODEL)),
            }
        ),
    ) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert provider.count == 1, "the second entry was dispatched with no budget for it"
    assert response.status_code != 200
    assert _exhausted("budget_exhausted") == before + 1


async def test_a_stream_that_fails_before_its_first_byte_moves_to_the_next_entry(
    api, migrate_engine, monkeypatch
) -> None:
    """The lazy relay is pulled inside the loop, so a stream can still fail over.

    A streaming dispatch returns a relay whose pre-first-byte failure is only
    visible once the first item is asked for. Pulling it in the loop is what
    puts the streaming failover boundary on the same seam ADR-0013 drew for the
    fallback — before anything reaches the caller.
    """
    await seed_routed_world(migrate_engine)

    chunk = {
        "id": "cmpl-1",
        "object": "chat.completion.chunk",
        "created": 1_760_000_000,
        "model": BACKUP_MODEL,
        "choices": [{"index": 0, "delta": {"content": "pong"}, "finish_reason": None}],
    }

    with stub_upstream(
        monkeypatch,
        _by_model(
            **{
                UPSTREAM_MODEL: _fails(503),
                BACKUP_MODEL: httpx.Response(
                    200,
                    content=sse(chunk),
                    headers={"content-type": "text/event-stream"},
                ),
            }
        ),
    ) as provider:
        response = await stream_call(
            api,
            "/chat/completions",
            json_body=_request(stream=True),
            headers=authorization(),
        )

    assert response.status_code == 200, response.body
    assert provider.count == 2
    assert response.headers["x-prope-route-entry"] == "2"
    body = response.body.decode()
    assert "pong" in body
    assert body.rstrip().endswith("data: [DONE]")


async def test_a_stream_that_fails_mid_way_is_truncated_and_never_spliced(
    api, migrate_engine, monkeypatch
) -> None:
    """**The second entry must never be asked**, and that is the assertion.

    Once a chunk has reached the caller the outcome is committed. Splicing
    provider B's continuation onto provider A's half-answer produces something
    that looks like one model's output and is two, and no reader of that call
    record could ever tell. ADR-0013's argument applies verbatim and harder here
    than it does to the canned fallback.
    """
    await seed_routed_world(migrate_engine, fallback_answer="canned")

    chunk = {
        "id": "cmpl-1",
        "object": "chat.completion.chunk",
        "created": 1_760_000_000,
        "model": UPSTREAM_MODEL,
        "choices": [{"index": 0, "delta": {"content": "half"}, "finish_reason": None}],
    }
    #: One `data:` frame, without the terminator `sse` appends.
    frame = sse(chunk).removesuffix(b"data: [DONE]\n\n")

    def broken(_request: httpx.Request) -> httpx.Response:
        """Two chunks, then the connection drops.

        `test_gateway_midstream_failure`'s shape, and it has to be: a body that
        merely ends without `[DONE]` is a CLEAN stream as far as httpx is
        concerned, so the outcome would be `ok` and this test would assert
        nothing about truncation at all.
        """

        async def body() -> AsyncIterator[bytes]:
            yield frame
            yield frame
            raise httpx.ReadError("the connection dropped")

        return httpx.Response(200, content=body(), headers={"content-type": "text/event-stream"})

    with stub_upstream(monkeypatch, _by_model(**{UPSTREAM_MODEL: broken})) as provider:
        response = await stream_call(
            api,
            "/chat/completions",
            json_body=_request(stream=True),
            headers=authorization(),
        )

    assert provider.count == 1, "a mid-stream failure was walked to a second provider"
    assert "half" in response.body.decode()
    assert "canned" not in response.body.decode()
    assert enqueued_records()[0].outcome is Outcome.TRUNCATED
