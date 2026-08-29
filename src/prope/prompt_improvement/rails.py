"""The rails an authored candidate must clear before the gate spends anything.

**ADR-0070 §2 lives here.** The closed catalogue's round-trip guarantee — *a
transform that replaces one whole block cannot drop a ``{{variable}}`` from
another* — is rebuilt as predicates over the model's output. Code owns the
rails; the model owns only the wording.

**Every check is a pure function and fails closed.** A refusal carries a typed
``RailCode`` that the bounded redraft loop feeds back to the drafter as the
validation error; a candidate that cannot clear the rails is discarded, never
rendered, and never costs the workspace a gate run to discover.

The set, and why each member exists:

``canonical_xml``
    The same validator prompt-registry refuses a body at save with. A candidate
    that cannot be saved is never worth gating.

``variable_set_changed``
    The paranoid check, lifted verbatim from ``remedies.py``'s job: a candidate
    that silently dropped a ``{{variable}}`` would break every call site the
    moment it was released — a worse outcome than the failure it remedies.

``interpolation_moved``
    The per-block restatement of the same rule. The GLOBAL set being unchanged
    is not enough: a variable moved into a block whose text is replaced by the
    edit is a variable the edit consumed, and block-level comparison catches
    what the global comparison would wave through.

``diff_unbounded``
    ADR-0068 §2's honest limit — *"the gate is a floor, and a bounded edit is
    far easier to keep inside what a suite covers"*. An authored rewrite that
    touches everything is the unbounded rewrite ADR-0068 rejected; the bound is
    whole changed blocks plus a length ratio, both constants in ``domain.py``.

``empty_delta``
    A candidate identical to the current body fixes nothing and spends a gate
    run proving it. The cheapest rail, checked first after canonicality.

``marker_echo``
    Spotlighting is SR-9: the body and the failing outputs arrive delimited,
    and an echo of the delimiters — in the candidate or in the rationale — is
    either an injection attempt or a model that started repeating its inputs.
    Both are discarded rather than interpreted.

``rationale_unbounded``
    The rationale is stored and disclosed collapsed (ADR-0070 §5); a bound
    enforced in the output model and again here, because a bound enforced once
    is a bound a second writer forgets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from xml.etree import ElementTree

from prope.canonical_prompt import validate_canonical_xml
from prope.prompt_composition import required_variables
from prope.prompt_improvement.domain import (
    DIFF_MAX_RATIO,
    DIFF_MIN_RATIO,
    MAX_CHANGED_BLOCKS,
    RATIONALE_CHARACTERS,
)

__all__ = ["FEEDBACK", "MARKERS", "RailCode", "RailsReport", "check_candidate"]


#: The spotlighting sentinels DSPy's chat adapter renders around every input
#: field. An authored candidate quoting them back is the echo this rail refuses.
MARKERS: tuple[str, ...] = ("[[ ##", "## ]]", "[[ #", "# ]]")


class RailCode(StrEnum):
    """The typed refusals. A closed set — the client renders them (ADR-0053)."""

    CANONICAL_XML = "canonical_xml"
    VARIABLE_SET_CHANGED = "variable_set_changed"
    INTERPOLATION_MOVED = "interpolation_moved"
    DIFF_UNBOUNDED = "diff_unbounded"
    EMPTY_DELTA = "empty_delta"
    MARKER_ECHO = "marker_echo"
    RATIONALE_UNBOUNDED = "rationale_unbounded"


#: The code a caller feeds back into the redraft, in one vi sentence the
#: drafter can act on. The advice text is a reviewed constant in this file,
#: changed through a pull request — the same rule the triage instruction
#: carries, for the same reason.
FEEDBACK: dict[RailCode, str] = {
    RailCode.CANONICAL_XML: (
        "Bản chỉnh phải là XML chuẩn hoá hợp lệ, giữ nguyên cấu trúc thẻ của bản gốc."
    ),
    RailCode.VARIABLE_SET_CHANGED: (
        "Bản chỉnh bị từ chối vì thay đổi tập biến {{...}}. Giữ nguyên mọi biến đã khai báo."
    ),
    RailCode.INTERPOLATION_MOVED: (
        "Bản chỉnh bị từ chối vì di chuyển biến {{...}} sang thẻ khác. Mỗi biến phải ở lại thẻ của nó."
    ),
    RailCode.DIFF_UNBOUNDED: (
        "Bản chỉnh sửa quá nhiều so với bản gốc. Chỉ chỉnh tối đa vài thẻ và giữ độ dài gần nguyên."
    ),
    RailCode.EMPTY_DELTA: (
        "Bản chỉnh trùng với bản gốc. Hãy chỉnh thật sự phần liên quan đến điều kiện bị trượt."
    ),
    RailCode.MARKER_ECHO: (
        "Bản chỉnh trích lại ký hiệu phân cách dữ liệu. Đừng lặp lại nội dung nằm trong dấu phân cách."
    ),
    RailCode.RATIONALE_UNBOUNDED: (
        "Phần giải thích vượt quá 500 ký tự. Rút gọn còn một vài câu."
    ),
}


@dataclass(frozen=True, slots=True)
class RailsReport:
    """What one candidate survived, attempt by attempt. Stored on the proposal.

    ``attempts`` carries one ``{attempt, code}`` entry per refused draft and a
    ``{attempt, code: "passed"}`` for the one that cleared — so a reader
    reconstructing the decision months later sees the redraft loop, not just
    its final frame.
    """

    passed: bool
    attempts: list[dict[str, Any]] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {"passed": self.passed, "attempts": list(self.attempts)}


def _blocks(body: str) -> list[tuple[str, str]]:
    """``[(tag, text)]`` for a body's top-level blocks, in document order."""
    root = ElementTree.fromstring(f"<prompt>{body}</prompt>")
    return [(block.tag, block.text or "") for block in root]


def _block_variables(tag: str, text: str) -> frozenset[str]:
    return frozenset(required_variables(f"<{tag}>{text}</{tag}>"))


def check_candidate(
    current: str, candidate: str, rationale: str
) -> RailCode | None:
    """``None`` when the candidate clears every rail; the first refusal's code
    otherwise. Checked cheapest-first, and short-circuiting: a candidate that
    fails canonicality is never compared for diff bounds.
    """
    if any(marker in candidate or marker in rationale for marker in MARKERS):
        return RailCode.MARKER_ECHO

    if not rationale.strip() or len(rationale) > RATIONALE_CHARACTERS:
        return RailCode.RATIONALE_UNBOUNDED

    try:
        validate_canonical_xml(candidate)
    except ValueError:
        return RailCode.CANONICAL_XML

    if candidate.strip() == current.strip():
        return RailCode.EMPTY_DELTA

    if required_variables(candidate) != required_variables(current):
        return RailCode.VARIABLE_SET_CHANGED

    try:
        before = _blocks(current)
        after = _blocks(candidate)
    except ElementTree.ParseError:
        # `current` predates a validation change — the same refusal remedies.py
        # makes, for the same reason: inventing a candidate from an unparseable
        # body is how a transform starts guessing.
        return RailCode.CANONICAL_XML

    changed = sum(1 for pair in zip(before, after, strict=False) if pair[0] != pair[1])
    changed += abs(len(before) - len(after))
    if changed > MAX_CHANGED_BLOCKS:
        return RailCode.DIFF_UNBOUNDED

    ratio = len(candidate) / len(current) if current else 0.0
    if not DIFF_MIN_RATIO <= ratio <= DIFF_MAX_RATIO:
        return RailCode.DIFF_UNBOUNDED

    # Block-level variables, the rule the global check cannot express: a
    # variable that MOVED between blocks leaves the global set intact and is
    # still consumed by the edit. Two rules, both fail-closed:
    #
    #   every tag the current body carries must keep its per-block variable
    #   sets, position for position — a changed set there is a moved variable;
    #   every tag the candidate ADDS must be variable-free. Adding a block is
    #   what the catalogue's own transforms do; putting a variable inside one
    #   is a move wearing a new tag.
    before_by_tag: dict[str, list[frozenset[str]]] = {}
    after_by_tag: dict[str, list[frozenset[str]]] = {}
    for tag, text in before:
        before_by_tag.setdefault(tag, []).append(_block_variables(tag, text))
    for tag, text in after:
        after_by_tag.setdefault(tag, []).append(_block_variables(tag, text))
    for tag, before_sets in before_by_tag.items():
        if after_by_tag.get(tag) != before_sets:
            return RailCode.INTERPOLATION_MOVED
    for tag, after_sets in after_by_tag.items():
        if tag not in before_by_tag and any(after_sets):
            return RailCode.INTERPOLATION_MOVED

    return None
