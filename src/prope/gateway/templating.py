"""A-078 / ADR-0011: `{{variable}}` placeholders, and the refusal when one is unfilled."""

import re
from collections.abc import Mapping

__all__ = [
    "PLACEHOLDER",
    "MissingVariable",
    "UnfilledPlaceholder",
    "render",
    "required_variables",
]

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")


class MissingVariable(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"the revision's body uses {{{{{name}}}}} and the request supplied no value")
        self.name = name


class UnfilledPlaceholder(ValueError):
    def __init__(self, expected: int, substituted: int) -> None:
        super().__init__(
            f"{expected} placeholders were checked and {substituted} were substituted; "
            "a request carrying a literal placeholder is never dispatched"
        )
        self.expected = expected
        self.substituted = substituted


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
