"""Drive an ASGI application from inside the test's own event loop.

**Why this exists rather than ``fastapi.testclient.TestClient``**, because it is
the kind of thing that looks like a shortcut and is not:

1. ``starlette.testclient`` imports ``httpx``, which is not in this project's
   dependency set. Plan 02-01 already refused to add an HTTP client for the one
   management-API read it needed, on the grounds that it *"would put a package in
   ``uv.lock`` that no production code imports"*, and reached for
   ``urllib.request`` instead. The same reasoning applies here with more force,
   because there is no HTTP involved at all.
2. ``TestClient`` runs the application on **another event loop in a worker
   thread**, bridged by an anyio portal, and exposes a synchronous API. Every
   test in this suite is `async` and every assertion goes through an asyncpg
   engine — and an asyncpg connection is bound to the loop that opened it
   (``tests/conftest.py`` says so, and it is why every engine here uses
   ``NullPool``). Calling a blocking client from inside the running loop is the
   shape those decisions exist to avoid.

**This is not an HTTP implementation.** ASGI is a three-callable protocol over
plain dictionaries; Starlette does all the HTTP semantics — routing, parsing,
validation, the exception handlers under test. What is below builds a ``scope``,
feeds one body message, collects the response messages, and stops.

An unhandled exception inside the application **propagates out of** :func:`call`
rather than becoming a tidy ``500``, because ``ServerErrorMiddleware`` re-raises
after responding when no handler is registered for it. That is deliberate on both
sides — see ``schemas.install_error_envelope``, which registers no catch-all
handler for exactly this reason.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode


@dataclass(frozen=True, slots=True)
class Response:
    """What the application sent back: a status, headers, and the raw body."""

    status_code: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        """The body parsed as JSON. Raises if it is not JSON, which is the point."""
        return json.loads(self.body)

    @property
    def code(self) -> str | None:
        """The A-045 envelope's machine ``code``, or ``None`` if this is not a refusal.

        Every assertion about a refusal in this suite goes through here rather
        than through the ``message``: ADR-0053 makes the ``code`` the thing a
        client renders and the ``message`` a string nobody displays, so a test
        that matched on the message would be pinning the wrong half.
        """
        if not self.body:
            # A 204 has no body and therefore no code. Answering ``None`` rather
            # than raising lets one parametrised assertion cover a mix of
            # no-content successes and enveloped refusals.
            return None
        payload = self.json()
        if isinstance(payload, dict) and "error" in payload:
            return payload["error"]["code"]
        return None


async def call(
    app: Any,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
    stream: bool = False,
) -> Response:
    """One request through ``app``, awaited on the caller's own event loop.

    ``stream=True`` is required to collect a ``text/event-stream`` whole, and the
    reason is worth stating because the symptom is a response that looks
    truncated rather than one that looks cancelled. Starlette races the body
    generator against a disconnect listener; ``receive`` below answers
    ``http.disconnect`` as soon as the request body is delivered, which is right
    for a normal response and cancels a streaming one after its first frame. With
    ``stream=True`` it blocks instead, which is what a client that is still
    reading actually does.
    """
    query = urlencode(
        {key: value for key, value in (params or {}).items() if value is not None}
    ).encode()
    raw = b"" if json_body is None else json.dumps(json_body).encode()

    header_list: list[tuple[bytes, bytes]] = [(b"host", b"testserver")]
    if json_body is not None:
        header_list.append((b"content-type", b"application/json"))
    header_list.append((b"content-length", str(len(raw)).encode()))
    for name, value in (headers or {}).items():
        header_list.append((name.lower().encode(), value.encode()))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "root_path": "",
        "headers": header_list,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    messages: list[dict[str, Any]] = []
    delivered = False

    async def receive() -> dict[str, Any]:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": raw, "more_body": False}
        if stream:
            # Never returns. Starlette cancels this task itself once the body
            # generator is exhausted, so the request ends when the answer does.
            await asyncio.Event().wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(scope, receive, send)

    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return Response(
        status_code=start["status"],
        headers={key.decode(): value.decode() for key, value in start["headers"]},
        body=body,
    )
