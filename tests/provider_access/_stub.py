"""A stub provider at the httpx transport, and the reason it is not a socket.

The SSRF guard refuses loopback, link-local and private addresses at save time
and again at dispatch time (ADR-0047), so a real HTTP server on `127.0.0.1` is
precisely the thing this module is built to refuse. A stub bound to a public
address is not available to a test suite, and relaxing the guard "for tests"
would disable the control the tests exist to prove.

So the stub sits one layer below: `httpx.MockTransport` answers the request the
production client built, which means the request the assertions read is the real
composed request — URL, headers, body, and the `sni_hostname` extension that
carries ADR-0047's pinning.
"""

import json
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import httpx
import pytest

from prope.provider_access import upstream
from prope.provider_access.addresses import ValidatedEndpoint

PUBLIC_ADDRESS = "93.184.216.34"

PRIVATE_ADDRESS = "169.254.169.254"

BASE_URL = "https://provider.example/v1"


def endpoint(address: str = PUBLIC_ADDRESS) -> ValidatedEndpoint:
    return ValidatedEndpoint(
        base_url=BASE_URL,
        scheme="https",
        host="provider.example",
        port=443,
        address=address,
    )


def completion(**extra: Any) -> dict[str, Any]:
    return {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 1_760_000_000,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "pong"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        **extra,
    }


def model_list(*model_ids: str) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": model_id, "object": "model"} for model_id in model_ids or ("gpt-4o-mini",)],
    }


def sse(*chunks: dict[str, Any]) -> bytes:
    body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
    return (body + "data: [DONE]\n\n").encode()


class Recorder:
    """Every request the production client actually built."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    @property
    def count(self) -> int:
        return len(self.requests)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def body(self, index: int = -1) -> dict[str, Any]:
        return json.loads(self.requests[index].content)


@contextmanager
def stub_provider(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> Iterator[Recorder]:
    recorder = Recorder()

    def record(request: httpx.Request) -> httpx.Response:
        recorder.requests.append(request)
        return handler(request)

    @asynccontextmanager
    async def stubbed(timeout_seconds: float) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            transport=httpx.MockTransport(record),
        ) as client:
            yield client

    monkeypatch.setattr(upstream, "_client", stubbed)
    yield recorder


def answers(status: int, payload: dict[str, Any] | None = None) -> Callable[..., httpx.Response]:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload if payload is not None else {})

    return handler


def route(**by_path: httpx.Response | Callable[[httpx.Request], httpx.Response]):  # noqa: ANN201
    """Dispatch on the last path segment: `models=...`, `completions=...`."""

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.path.rsplit("/", 1)[-1]
        answer = by_path.get(key)
        if answer is None:
            return httpx.Response(404, json={"error": {"message": "no stub", "type": "test"}})
        return answer(request) if callable(answer) else answer

    return handler
