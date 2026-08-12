"""ADR-0015 — the OpenAI chat-completions shape, with unknown fields passed through."""

import time
from collections.abc import Mapping
from typing import Any

from prope.provider_access.domain import Usage

__all__ = [
    "CHUNK_OBJECT",
    "COMPLETION_OBJECT",
    "DEFAULT_FINISH_REASON",
    "normalise_chunk",
    "normalise_response",
    "read_usage",
]

COMPLETION_OBJECT = "chat.completion"

CHUNK_OBJECT = "chat.completion.chunk"

INPUT_TOKEN_NAMES = ("prompt_tokens", "input_tokens")

OUTPUT_TOKEN_NAMES = ("completion_tokens", "output_tokens")


def _first_int(payload: Mapping[str, Any], names: tuple[str, ...]) -> int | None:
    for name in names:
        value = payload.get(name)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def read_usage(payload: Mapping[str, Any] | None) -> Usage | None:
    if not isinstance(payload, Mapping):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, Mapping):
        return None

    input_tokens = _first_int(usage, INPUT_TOKEN_NAMES)
    output_tokens = _first_int(usage, OUTPUT_TOKEN_NAMES)
    total = _first_int(usage, ("total_tokens",))
    if total is None and input_tokens is not None and output_tokens is not None:
        total = input_tokens + output_tokens
    if input_tokens is None and output_tokens is None and total is None:
        return None
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total)


def _normalise_usage(payload: dict[str, Any]) -> None:
    usage = payload.get("usage")
    if not isinstance(usage, Mapping):
        return
    read = read_usage(payload)
    if read is None:
        return
    normalised = dict(usage)
    if read.input_tokens is not None:
        normalised["prompt_tokens"] = read.input_tokens
    if read.output_tokens is not None:
        normalised["completion_tokens"] = read.output_tokens
    if read.total_tokens is not None:
        normalised["total_tokens"] = read.total_tokens
    payload["usage"] = normalised


def _normalise(
    payload: Mapping[str, Any],
    *,
    object_name: str,
    model: str,
    default_finish_reason: str | None,
) -> dict[str, Any]:
    normalised = dict(payload)
    normalised.setdefault("id", "")
    normalised.setdefault("object", object_name)
    normalised.setdefault("created", int(time.time()))
    normalised.setdefault("model", model)

    choices = normalised.get("choices")
    normalised["choices"] = list(choices) if isinstance(choices, list) else []
    for index, choice in enumerate(normalised["choices"]):
        if not isinstance(choice, Mapping):
            continue
        repaired = dict(choice)
        repaired.setdefault("index", index)
        repaired.setdefault("finish_reason", default_finish_reason)
        normalised["choices"][index] = repaired

    _normalise_usage(normalised)
    return normalised


DEFAULT_FINISH_REASON = "stop"


def normalise_response(payload: Mapping[str, Any], *, model: str) -> dict[str, Any]:
    return _normalise(
        payload,
        object_name=COMPLETION_OBJECT,
        model=model,
        default_finish_reason=DEFAULT_FINISH_REASON,
    )


def normalise_chunk(payload: Mapping[str, Any], *, model: str) -> dict[str, Any]:
    normalised = _normalise(
        payload, object_name=CHUNK_OBJECT, model=model, default_finish_reason=None
    )
    for index, choice in enumerate(normalised["choices"]):
        if isinstance(choice, Mapping) and "delta" not in choice and "message" in choice:
            repaired = dict(choice)
            repaired["delta"] = repaired["message"]
            normalised["choices"][index] = repaired
    return normalised
