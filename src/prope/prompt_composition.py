"""ADR-0011: `{{variable}}` substitution, and the revision body as the only system message.

**Module-neutral, like `canonical_prompt.py` and for the same reason.** These two
rules are properties of *what a revision means when it is sent to a provider*, not
properties of the gateway that first needed them. Two callers now compose a
revision for dispatch — the gateway serving a released one, and prompt-registry's
playground trying a draft — and a second implementation of either rule is a second
answer to "what did Prope actually send", which is the one question the whole
product exists to answer.

They lived in `prope.gateway.templating` and `prope.gateway.composition` until the
playground needed them. Importing them from there would have given prompt-registry
an edge into the gateway, which is precisely the edge the module map forbids
`evaluation` from having — the gateway is the outermost surface and nothing inland
may depend on it. So the code moved here and the gateway now imports it, which
leaves the gateway's behaviour byte-identical and its own modules as thin
re-exports.

**Nothing here reads a clock, a database, or a request.** Both functions are pure
over their arguments, which is what lets the same two lines run on the hot path
and in an interactive handler without either one needing to know about the other.
"""

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "MAX_COMPOSED_BYTES",
    "PLACEHOLDER",
    "SYSTEM_ROLE",
    "CallerSystemMessage",
    "MissingVariable",
    "OversizeRequest",
    "UnfilledPlaceholder",
    "compose",
    "composed_size",
    "refuse_caller_system_message",
    "render",
    "required_variables",
]

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")

SYSTEM_ROLE = "system"

MAX_COMPOSED_BYTES = 256 * 1024


class MissingVariable(ValueError):  # noqa: N818
    def __init__(self, name: str) -> None:
        super().__init__(f"the revision's body uses {{{{{name}}}}} and the request supplied no value")
        self.name = name


class UnfilledPlaceholder(ValueError):  # noqa: N818
    def __init__(self, expected: int, substituted: int) -> None:
        super().__init__(
            f"{expected} placeholders were checked and {substituted} were substituted; "
            "a request carrying a literal placeholder is never dispatched"
        )
        self.expected = expected
        self.substituted = substituted


class CallerSystemMessage(ValueError):  # noqa: N818
    def __init__(self, index: int) -> None:
        super().__init__("the caller supplied a system message")
        self.index = index


class OversizeRequest(ValueError):  # noqa: N818
    def __init__(self, size: int) -> None:
        super().__init__(f"the composed message set is {size} bytes")
        self.size = size


def required_variables(body: str) -> tuple[str, ...]:
    seen: list[str] = []
    for match in PLACEHOLDER.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def render(body: str, variables: Mapping[str, object] | None) -> str:
    supplied = variables or {}

    for name in required_variables(body):
        if name not in supplied or supplied[name] is None:
            raise MissingVariable(name)

    expected = len(PLACEHOLDER.findall(body))
    rendered, substituted = PLACEHOLDER.subn(lambda match: str(supplied[match.group(1)]), body)

    if substituted != expected:
        raise UnfilledPlaceholder(expected, substituted)

    return rendered


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
