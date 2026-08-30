"""INT-023 — the one seam in Prope that leaves the host."""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx

from prope.provider_access.addresses import ValidatedEndpoint, join, pin

__all__ = [
    "CHAT_COMPLETIONS_PATH",
    "MODELS_PATH",
    "SSE_DONE",
    "UpstreamCall",
    "compose_request",
    "call_json",
    "stream_completion",
]

CHAT_COMPLETIONS_PATH = "/chat/completions"

MODELS_PATH = "/models"

#: Sent alongside the Bearer credential because `api.anthropic.com` authenticates
#: every path — including `/models` — with `x-api-key` and refuses a Bearer-only
#: request there, and its compatibility layer reads the same header back. Every
#: other OpenAI-compatible vendor ignores both headers, so the single adapter
#: keeps one code path rather than growing a per-vendor branch.
ANTHROPIC_VERSION_HEADER = "anthropic-version"

ANTHROPIC_API_VERSION = "2023-06-01"

SSE_DONE = "[DONE]"

RESERVED_PARAMETERS = frozenset({"model", "messages", "stream", "stream_options"})


@dataclass(frozen=True, slots=True)
class UpstreamCall:
    status: int
    body: Mapping[str, Any] | None


def compose_request(
    *,
    upstream_model: str,
    parameters: Mapping[str, Any],
    messages: Sequence[Mapping[str, Any]],
    stream: bool,
) -> dict[str, Any]:
    """A-097 passes parameters verbatim; A-089 asks for usage unconditionally."""
    payload: dict[str, Any] = {
        key: value for key, value in parameters.items() if key not in RESERVED_PARAMETERS
    }
    payload["model"] = upstream_model
    payload["messages"] = [dict(message) for message in messages]
    payload["stream"] = stream
    if stream:
        payload["stream_options"] = {"include_usage": True}
    return payload


def _headers(
    secret: str, host_header: Mapping[str, str], *, anthropic_dialect: bool = False
) -> dict[str, str]:
    """Plain Bearer by default.

    `x-api-key` + `anthropic-version` are opt-in because they are not
    read-and-ignored everywhere: OpenRouter serves its
    anthropic-compatible catalogue — ids like `anthropic/<slug>[1m]` that
    its own `/chat/completions` refuses — to any request wearing
    `anthropic-version`, so a blanket header poisons every listing it
    touches. Callers that have evidence a host wants the dialect (a listing
    refused without it) pass the flag.
    """
    headers = {
        "authorization": f"Bearer {secret}",
        "accept": "application/json",
        "content-type": "application/json",
        **host_header,
    }
    if anthropic_dialect:
        headers["x-api-key"] = secret
        headers[ANTHROPIC_VERSION_HEADER] = ANTHROPIC_API_VERSION
    return headers


@asynccontextmanager
async def _client(timeout_seconds: float) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=False,
        transport=httpx.AsyncHTTPTransport(retries=0),
    ) as client:
        yield client


def _decode(response: httpx.Response) -> Mapping[str, Any] | None:
    try:
        decoded = json.loads(response.text)
    except ValueError:
        return None
    return decoded if isinstance(decoded, Mapping) else None


async def call_json(
    endpoint: ValidatedEndpoint,
    secret: str,
    *,
    path: str,
    method: str = "POST",
    payload: Mapping[str, Any] | None = None,
    timeout_seconds: float,
    anthropic_dialect: bool = False,
) -> UpstreamCall:
    url, host_header, extensions = pin(endpoint, join(endpoint, path))
    async with _client(timeout_seconds) as client:
        response = await client.request(
            method,
            url,
            json=dict(payload) if payload is not None else None,
            headers=_headers(secret, host_header, anthropic_dialect=anthropic_dialect),
            extensions=extensions,
        )
    return UpstreamCall(status=response.status_code, body=_decode(response))


async def stream_completion(
    endpoint: ValidatedEndpoint,
    secret: str,
    *,
    payload: Mapping[str, Any],
    timeout_seconds: float,
    anthropic_dialect: bool = False,
) -> AsyncIterator[UpstreamCall | Mapping[str, Any]]:
    """Yields one `UpstreamCall` on a refusal, or the decoded SSE data objects."""
    url, host_header, extensions = pin(endpoint, join(endpoint, CHAT_COMPLETIONS_PATH))
    async with _client(timeout_seconds) as client:
        request = client.build_request(
            "POST",
            url,
            json=dict(payload),
            headers={
                **_headers(secret, host_header, anthropic_dialect=anthropic_dialect),
                "accept": "text/event-stream",
            },
            extensions=extensions,
        )
        response = await client.send(request, stream=True)
        try:
            if response.status_code >= 400:
                await response.aread()
                yield UpstreamCall(status=response.status_code, body=_decode(response))
                return

            async for line in response.aiter_lines():
                stripped = line.strip()
                if not stripped or not stripped.startswith("data:"):
                    continue
                data = stripped[len("data:") :].strip()
                if data == SSE_DONE:
                    return
                try:
                    decoded = json.loads(data)
                except ValueError:
                    continue
                if isinstance(decoded, Mapping):
                    yield decoded
        finally:
            await response.aclose()
