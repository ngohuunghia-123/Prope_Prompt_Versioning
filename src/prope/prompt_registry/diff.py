"""A-015's line-level body diff and the field-level comparison beside it.

**Computed on demand and never stored** (A-047). There is no table here and no
cache: a stored diff is a third copy of the prompt body, on top of ``revision``
and ``search_text``, and T-017 already shows what the second one costs to keep
out of a response.

**``autojunk=False``, and it is the whole reason this module names its
constructor arguments.** ``SequenceMatcher``'s default silently discards lines
appearing in more than 1% of a sequence longer than 200 elements — so on a
32 KiB body with repeated short lines (a prompt with many blank lines, or many
``- `` bullets, which is most of them) the heuristic drops exactly the lines a
reviewer is looking at. The result is a diff that looks WRONG rather than slow,
and a reviewer who approves a change they did not see is the failure the whole
review screen exists to prevent.

Disabling it removes the quadratic-case guard, and that cost is under test
rather than assumed: AC-2 asserts 300 ms with **both** bodies at A-050's 32 KiB
cap.

**Equal leading and trailing lines are trimmed before the matcher sees them**,
which is what pays for that. Trimming is lossless — a line equal at the same
position on both sides is equal in any edit script — and it is the difference
between 1.2 s and 3 ms on the shape that actually breaks the budget: a long list
of near-identical bullets with one line changed in the middle. Without it,
``SequenceMatcher`` compares every occurrence of a repeated line against every
other and a real 32 KiB body blows AC-2's number by a factor of four. A body
built to defeat the trim (alternating repeated lines, no common ends) is still
quadratic; it is a self-inflicted slow screen inside one authenticated
workspace, not a way in.

**The field comparison renders values as strings.** A reviewer comparing two
parameter sets should not have to read JSON to see which number moved, and a
rendered value cannot carry a type the SPA has to branch on (ADR-0053).
"""

import json
from difflib import SequenceMatcher
from typing import Any

from prope.prompt_registry.domain import (
    DiffResult,
    FieldChange,
    LineChange,
    LineOp,
    RevisionRead,
)

__all__ = ["COMPARED_FIELDS", "compute_diff", "render_value"]

#: The four fields A-015 names beside the body, in the order the review screen
#: shows them. A tuple rather than a set: the order is part of the contract, and
#: a reviewer who reads the same screen twice should read it the same way.
COMPARED_FIELDS = ("provider_config_id", "upstream_model", "parameters", "fallback_answer")


def render_value(value: Any) -> str | None:
    """One value as the comparison shows it. ``None`` stays ``None``.

    ``parameters`` is a mapping and is rendered with sorted keys, because Python
    preserves insertion order and two revisions that set the same parameters in a
    different order would otherwise render as a change nobody made.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def _lines(body: str) -> list[str]:
    """``splitlines`` rather than ``split('\\n')``.

    A prompt body is human-authored text pasted from somewhere else, so it
    arrives with whatever line endings that somewhere used. ``splitlines`` treats
    ``\\r\\n`` and ``\\n`` alike; ``split`` would render every line of a
    Windows-authored body as changed against a Unix-authored one.
    """
    return body.splitlines()


def _common_prefix(before: list[str], after: list[str]) -> int:
    """How many leading lines are equal on both sides."""
    limit = min(len(before), len(after))
    index = 0
    while index < limit and before[index] == after[index]:
        index += 1
    return index


def _common_suffix(before: list[str], after: list[str], head: int) -> int:
    """How many trailing lines are equal, without reaching back past ``head``.

    The bound is what stops a body that is entirely one repeated line from being
    counted twice — once as prefix and once as suffix — and emitting more lines
    than either revision has.
    """
    limit = min(len(before), len(after)) - head
    index = 0
    while index < limit and before[-1 - index] == after[-1 - index]:
        index += 1
    return index


def _equal_run(texts: list[str], from_start: int, to_start: int) -> list[LineChange]:
    return [
        LineChange(
            op=LineOp.EQUAL,
            text=text,
            from_line=from_start + offset + 1,
            to_line=to_start + offset + 1,
        )
        for offset, text in enumerate(texts)
    ]


def compute_diff(before: RevisionRead, after: RevisionRead) -> DiffResult:
    """The line diff and the field comparison, for two revisions of one prompt.

    Callers pass the revisions in the order the screen reads them — ``before`` is
    the ``from`` and ``after`` is the ``to``. Nothing here checks that they belong
    to the same prompt: INT-011's caller has already read both rows through the
    permission filter, and a check here would be a second answer to a question
    the repository already answered.
    """
    from_lines = _lines(before.body)
    to_lines = _lines(after.body)

    head = _common_prefix(from_lines, to_lines)
    tail = _common_suffix(from_lines, to_lines, head)

    from_middle = from_lines[head : len(from_lines) - tail]
    to_middle = to_lines[head : len(to_lines) - tail]

    matcher = SequenceMatcher(a=from_middle, b=to_middle, autojunk=False)

    lines: list[LineChange] = _equal_run(from_lines[:head], 0, 0)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            lines.extend(_equal_run(from_middle[i1:i2], head + i1, head + j1))
            continue

        if tag in ("replace", "delete"):
            for offset, text in enumerate(from_middle[i1:i2]):
                lines.append(
                    LineChange(op=LineOp.REMOVED, text=text, from_line=head + i1 + offset + 1)
                )

        if tag in ("replace", "insert"):
            for offset, text in enumerate(to_middle[j1:j2]):
                lines.append(
                    LineChange(op=LineOp.ADDED, text=text, to_line=head + j1 + offset + 1)
                )

    lines.extend(
        _equal_run(
            from_lines[len(from_lines) - tail :],
            len(from_lines) - tail,
            len(to_lines) - tail,
        )
    )

    fields = tuple(
        FieldChange(
            field=name,
            before=render_value(getattr(before, name)),
            after=render_value(getattr(after, name)),
        )
        for name in COMPARED_FIELDS
    )

    return DiffResult(
        from_version_id=before.version_id,
        to_version_id=after.version_id,
        lines=tuple(lines),
        fields=fields,
    )
