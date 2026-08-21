"""Request in, response out. **No I/O in this module, deliberately.**

Everything that decides *what Prope is sent* and *what its answer means* lives
here as pure functions, so the sync client, the async client and the tests
exercise one implementation rather than three that agree today.

It is also what keeps ADR-0065's thinness claim checkable: if this file starts
importing a transport, the SDK has stopped being a request shape and started
being a framework.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from .errors import (
    AuthenticationError,
    CallerSystemMessage,
    InvalidRequest,
    MissingVariable,
    ModelNotFound,
    PropeError,
    RateLimited,
    UpstreamError,
)
from .types import Answer, Chunk, Usage

__all__ = [
    "CHAT_PATH",
    "answer_from",
    "build_body",
    "check_messages",
    "chunk_from",
    "model_reference",
    "raise_for",
    "sse_payloads",
]

CHAT_PATH = "/v1/chat/completions"

#: Refused locally rather than at the gateway. See `check_messages`.
_FORBIDDEN_ROLE = "system"


def model_reference(prompt: str, pin: str | None) -> str:
    """`namespace/name`, or `namespace/name@v3` when a revision is pinned.

    The pin goes in the model string rather than in the `prope` block because
    that is where INT-022 puts it — a pinned call and an unpinned call differ in
    the name they address, which is what makes the resolution cache key correct
    without a special case.
    """
    if pin is None:
        return prompt
    pin = pin.strip()
    if not pin:
        return prompt
    return f"{prompt}@{pin}"


def check_messages(messages: Sequence[Mapping[str, Any]]) -> None:
    """Refuse a caller `system` message **before the request leaves**.

    The gateway refuses it too (`system_message_not_allowed`), so this is not a
    security control — it is the single most likely mistake in a freshly
    migrated call site, where the literal that used to be the system prompt is
    still being passed alongside the model name that now carries it. Failing
    here names the index and the reason without a round trip.
    """
    for index, message in enumerate(messages):
        if message.get("role") == _FORBIDDEN_ROLE:
            raise CallerSystemMessage(
                "A released revision carries its own system prompt, so this request may not "
                f"send one. Remove messages[{index}] (role='system'). If that text is the "
                "prompt you are migrating, it belongs in the revision, not in the call.",
                code="system_message_not_allowed",
                param=f"messages.{index}.role",
            )


def build_body(
    *,
    prompt: str,
    messages: Sequence[Mapping[str, Any]],
    variables: Mapping[str, Any] | None = None,
    pin: str | None = None,
    stream: bool = False,
    conversation_id: str | None = None,
    parent_call_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """INT-022's request. The `prope` block is omitted entirely when empty.

    Omitted rather than sent as `{}` because an empty block is a field the
    gateway then has to treat as absent anyway, and a request that carries no
    Prope-specific intent should look on the wire exactly like one from a plain
    OpenAI client.

    `parent_call_id` is dropped unless a `conversation_id` accompanies it — the
    gateway drops it too (a parent with nothing to hang it in is stored and
    never read), and dropping it here means the request matches what will be
    recorded.
    """
    body: dict[str, Any] = {
        "model": model_reference(prompt, pin),
        "messages": list(messages),
        "stream": stream,
    }
    if stream:
        body["stream_options"] = {"include_usage": True}

    prope: dict[str, Any] = {}
    if variables:
        prope["variables"] = dict(variables)
    if conversation_id:
        prope["conversation_id"] = conversation_id
        if parent_call_id:
            prope["parent_call_id"] = parent_call_id
    if prope:
        body["prope"] = prope

    if extra:
        # Provider parameters — `temperature`, `max_tokens`, `tools`. Merged last
        # so a caller cannot accidentally overwrite `model` or `messages`, which
        # are the two fields Prope's own semantics depend on.
        for key, value in extra.items():
            if key not in ("model", "messages", "prope"):
                body[key] = value

    return body


def _usage(payload: Mapping[str, Any]) -> Usage:
    raw = payload.get("usage")
    if not isinstance(raw, Mapping):
        return Usage()
    return Usage(
        prompt_tokens=raw.get("prompt_tokens"),
        completion_tokens=raw.get("completion_tokens"),
        total_tokens=raw.get("total_tokens"),
    )


def _flag(value: str | None) -> bool:
    return str(value).lower() == "true"


def raise_for(
    status: int, payload: Mapping[str, Any] | None, headers: Mapping[str, str] | None = None
) -> None:
    """Translate a refusal into the narrowest exception that is still honest.

    A body Prope did not write — a proxy's HTML error page, an empty 502 — has no
    `error` object, so the status alone decides. That case is real: it is what a
    load balancer in front of the gateway produces, and it must not surface as
    `PropeError(None)`.
    """
    if status < 400:
        return

    error: Mapping[str, Any] = {}
    if isinstance(payload, Mapping) and isinstance(payload.get("error"), Mapping):
        error = payload["error"]

    message = str(error.get("message") or f"The gateway answered {status}.")
    code = error.get("code")
    param = error.get("param")
    error_type = error.get("type")
    common = {"code": code, "status": status, "param": param, "error_type": error_type}

    if status == 401:
        raise AuthenticationError(message, **common)
    if status == 404:
        raise ModelNotFound(message, **common)
    if status == 429:
        retry = (headers or {}).get("retry-after")
        raise RateLimited(
            message, retry_after=float(retry) if retry else None, **common
        )
    if status >= 500:
        raise UpstreamError(message, **common)
    if status == 400:
        if code == "missing_variable":
            raise MissingVariable(message, **common)
        if code == "system_message_not_allowed":
            raise CallerSystemMessage(message, **common)
        raise InvalidRequest(message, **common)
    raise PropeError(message, **common)


def answer_from(
    payload: Mapping[str, Any], headers: Mapping[str, str] | None = None
) -> Answer:
    """Build an `Answer` from the body, using headers only for what the body lacks.

    The body is authoritative because it is what A-079 specifies and what a
    caller reading `response.prope` would see; the headers are a superset in
    exactly one respect — `x-prope-call-id`, which the body does not carry and
    which the next step of a chain needs.
    """
    headers = {key.lower(): value for key, value in (headers or {}).items()}
    prope: Mapping[str, Any] = payload.get("prope") if isinstance(payload.get("prope"), Mapping) else {}

    choices = payload.get("choices") or []
    text = ""
    if choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping) and isinstance(message.get("content"), str):
            text = message["content"]

    revision = prope.get("revision_number")
    if revision is None and headers.get("x-prope-revision"):
        try:
            revision = int(headers["x-prope-revision"])
        except ValueError:
            revision = None

    return Answer(
        text=text,
        model=str(payload.get("model") or headers.get("x-prope-model") or ""),
        call_id=str(headers.get("x-prope-call-id") or payload.get("id") or ""),
        version_id=prope.get("version_id") or headers.get("x-prope-version-id"),
        revision=revision,
        upstream_model=prope.get("upstream_model"),
        pinned=bool(prope.get("pinned", _flag(headers.get("x-prope-pinned")))),
        fallback=bool(prope.get("fallback", _flag(headers.get("x-prope-fallback")))),
        usage=_usage(payload),
        raw=payload,
    )


def sse_payloads(lines: Iterator[str]) -> Iterator[Mapping[str, Any]]:
    """Decode `data:` frames, dropping `[DONE]` and anything unparseable.

    Tolerant on purpose. A stream is the one place where a strict parser turns a
    cosmetic upstream quirk — a comment line, a keep-alive, a blank frame — into
    a failed request that has already half-answered the user.
    """
    for line in lines:
        line = line.strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            yield parsed


def chunk_from(payload: Mapping[str, Any]) -> Chunk:
    """One SSE frame as a `Chunk`. A mid-stream error frame raises.

    Raising mid-iteration is correct rather than convenient: the gateway relays
    an upstream failure as its own event and records the call as truncated, so a
    caller that kept consuming would be building a string it has no reason to
    trust. What already arrived is still in whatever the caller accumulated.
    """
    error = payload.get("error")
    if isinstance(error, Mapping):
        raise UpstreamError(
            str(error.get("message") or "The stream failed after it began."),
            code=error.get("code"),
            error_type=error.get("type"),
        )

    text = ""
    for choice in payload.get("choices") or ():
        if not isinstance(choice, Mapping):
            continue
        delta = choice.get("delta")
        if isinstance(delta, Mapping) and isinstance(delta.get("content"), str):
            text += delta["content"]

    prope = payload.get("prope") if isinstance(payload.get("prope"), Mapping) else {}
    raw_usage = payload.get("usage")
    return Chunk(
        text=text,
        call_id=prope.get("call_id"),
        version_id=prope.get("version_id"),
        usage=_usage(payload) if isinstance(raw_usage, Mapping) else None,
        raw=payload,
    )
