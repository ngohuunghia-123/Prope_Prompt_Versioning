"""ADR-0011's composition: the revision's body is the system message, and the only one."""

import json
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "MAX_COMPOSED_BYTES",
    "SYSTEM_ROLE",
    "CallerSystemMessage",
    "OversizeRequest",
    "compose",
    "composed_size",
]

SYSTEM_ROLE = "system"

MAX_COMPOSED_BYTES = 256 * 1024


class CallerSystemMessage(ValueError):
    def __init__(self, index: int) -> None:
        super().__init__("the caller supplied a system message")
        self.index = index


class OversizeRequest(ValueError):
    def __init__(self, size: int) -> None:
        super().__init__(f"the composed message set is {size} bytes")
        self.size = size


def refuse_caller_system_message(messages: Sequence[Mapping[str, Any]]) -> None:
    for index, message in enumerate(messages):
        if str(message.get("role", "")).strip().lower() == SYSTEM_ROLE:
            raise CallerSystemMessage(index)


def composed_size(messages: Sequence[Mapping[str, Any]]) -> int:
    return len(json.dumps(list(messages), ensure_ascii=False).encode("utf-8"))


def compose(
    messages: Sequence[Mapping[str, Any]],
    system_prompt: str,
) -> list[dict[str, Any]]:
    refuse_caller_system_message(messages)

    composed: list[dict[str, Any]] = [{"role": SYSTEM_ROLE, "content": system_prompt}]
    composed.extend(dict(message) for message in messages)

    size = composed_size(composed)
    if size > MAX_COMPOSED_BYTES:
        raise OversizeRequest(size)

    return composed
