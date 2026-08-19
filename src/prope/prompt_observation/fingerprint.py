"""A-154 — what counts as the same prompt, and which spans are variables.

**This file is the module's one genuinely uncertain thing**, and OQ-149 says so.
The rule cannot be validated in advance because the input is other people's code.
What can be chosen is the direction it fails in, and it is chosen to fail
*visibly*: too tight and one prompt becomes many rows, which is obvious in the
first screenshot; too loose and two prompts merge into one, which is silently
wrong. It leans tight.

**Only the system message is ever fingerprinted or stored.** OQ-148 §4 asks
whether an end user's interpolated text should be persisted at all — even briefly,
even to compute a diff — and the conservative build is the answer this file
implements: the user turns are dropped before anything is written, and the
variable inference works by diffing system messages against each other, so they
are not an input to anything. That is the largest category of surprise removed
before any policy conversation starts.

**The inference proposes and never applies** (A-154). It hands a person a body
with slots cut and the observed body beside it; nothing is written, and
prompt-registry's own validation refuses an unfilled placeholder at dispatch
(A-078) rather than serving a broken prompt quietly.
"""

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from difflib import SequenceMatcher

__all__ = [
    "MASK",
    "PLACEHOLDER_PREFIX",
    "body_hash",
    "fingerprint",
    "infer_variables",
    "normalise",
    "system_message",
]

#: What an interpolated span is replaced by before hashing. It is deliberately a
#: token no prompt would contain rather than an empty string: collapsing a value
#: to nothing would make "You are helping ACME" and "You are helping" the same
#: prompt, and the second one is a different prompt with a bug in it.
MASK = "\x00~\x00"

#: The form prompt-registry already accepts (A-011, A-078), so an adopted body
#: round-trips through the registry's own validation with nothing in between.
PLACEHOLDER_PREFIX = "var"

SYSTEM_ROLE = "system"

#: What "interpolated-looking" means, and OQ-149 §1 records that there is no
#: general answer. Each pattern earns its place by being a shape that varies per
#: request *and* would otherwise split one prompt into hundreds of rows:
#:
#: * ISO-8601 timestamps and plain dates — the single most common interpolation,
#:   and the one that guarantees a fresh fingerprint on every single call.
#: * UUIDs and ULID-shaped ids — customer ids, session ids, order numbers.
#: * Long digit runs — order numbers, phone numbers, account numbers. Bounded at
#:   four so that "top 3 results" and "GPT-4" survive as prompt text, which they
#:   are.
#: * Currency amounts.
#:
#: NOT masked, deliberately: single words, names, and anything in quotes. Those
#: are where a mask starts merging genuinely different prompts, and the failure
#: direction this file leans away from.
_INTERPOLATED = (
    re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?Z?)?"),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b"),
    re.compile(r"\b\d{5,}\b"),
    re.compile(r"[$€£¥]\s?\d[\d,.]*"),
)

_WHITESPACE = re.compile(r"\s+")


def system_message(messages: Sequence[Mapping[str, object]]) -> str | None:
    """The caller's system message, or ``None`` when there is not one.

    ADR-0011's own decomposition, read backwards: the revision's body **is** the
    system message and the caller supplies the conversation, so a prompt whose
    identity varied with the user's turn would not be a prompt. The first system
    message wins; a second is unusual enough that merging them would be inventing
    a body nobody sent.
    """
    for message in messages:
        if message.get("role") != SYSTEM_ROLE:
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    return None


def normalise(body: str) -> str:
    """The grouping form: interpolated spans masked, whitespace collapsed.

    Masking runs **before** whitespace collapsing, because a timestamp containing
    a space would otherwise be half-matched by the pattern that expects one.
    """
    masked = body
    for pattern in _INTERPOLATED:
        masked = pattern.sub(MASK, masked)
    return _WHITESPACE.sub(" ", masked).strip()


def fingerprint(body: str) -> str:
    """A-154's grouping key: a hash of the normalised system message.

    SHA-256 for the same reason ``keys.hash_secret`` uses it and for none of the
    same stakes — this is a grouping key, not a secret, and what is wanted is a
    stable fixed-width string with no collisions in practice.

    **The raw body is stored beside this**, which is what makes the rule cheap to
    change: a different normalisation is a re-hash of a table rather than a lost
    inventory. That property is why A-154 is marked cheaply reversible.
    """
    return hashlib.sha256(normalise(body).encode("utf-8")).hexdigest()


def body_hash(body: str) -> str:
    """The EXACT hash, unnormalised — what makes "the body changed on Tuesday" true.

    Two calls with the same ``fingerprint`` and different ``body_hash`` are the
    same prompt, edited. Two with different fingerprints are different prompts.
    The pair is the whole drift view.
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def infer_variables(bodies: Iterable[str]) -> tuple[str, list[str]]:
    """Diff a group's members; return a body with slots cut, and the slot names.

    Spans that differ between sightings of one fingerprint are candidate
    variables; spans identical across every sighting are prompt text. With fewer
    than two distinct bodies there is nothing to diff and nothing is proposed —
    which is the common case on day one, and returning the body unchanged is the
    honest answer rather than a guess.

    ``difflib`` and nothing more (A-012's debuggable-by-one-person clause). A
    fuzzier matcher would buy precision this does not need: the result is shown to
    a person against the observed body before it does anything, so legibility is
    worth more here than accuracy.

    Slots are named positionally — ``{{var_1}}``, ``{{var_2}}`` — because naming
    them from content would be a second inference layered on an uncertain one, and
    the person adopting is about to rename them anyway.
    """
    distinct = list(dict.fromkeys(body for body in bodies if body))
    if len(distinct) < 2:
        return (distinct[0] if distinct else ""), []

    template = distinct[0]
    # Intersect the stable spans across every pair, so a span survives only if it
    # is identical in ALL members. Two members agreeing is not evidence when a
    # third disagrees, and the alternative — union — would cut a slot wherever any
    # two sightings differed and shred the body.
    stable: list[tuple[int, int]] = [(0, len(template))]
    for other in distinct[1:]:
        matcher = SequenceMatcher(None, template, other, autojunk=False)
        matching = [(block.a, block.a + block.size) for block in matcher.get_matching_blocks() if block.size]
        stable = _intersect(stable, matching)

    # A span the FINGERPRINT already treats as interpolated is a variable whole,
    # whatever the diff says about it. Without this the proposal for three dates
    # differing in one digit is `2026-08-1{{var_1}}` — literally correct, useless
    # to adopt, and wrong the first time the month rolls over. The two mechanisms
    # have to agree: it would be incoherent for `normalise` to say a timestamp is
    # not part of a prompt's identity while the proposal keeps nine tenths of it
    # as prompt text.
    return _cut(template, _subtract(stable, _forced_spans(template)))


def _intersect(
    left: Sequence[tuple[int, int]], right: Sequence[tuple[int, int]]
) -> list[tuple[int, int]]:
    """Overlapping spans of two sorted, non-overlapping span lists."""
    out: list[tuple[int, int]] = []
    i = j = 0
    while i < len(left) and j < len(right):
        start = max(left[i][0], right[j][0])
        end = min(left[i][1], right[j][1])
        if start < end:
            out.append((start, end))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return out


def _forced_spans(template: str) -> list[tuple[int, int]]:
    """Every span :data:`_INTERPOLATED` matches, merged and sorted."""
    spans = sorted(
        (match.start(), match.end())
        for pattern in _INTERPOLATED
        for match in pattern.finditer(template)
    )
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _subtract(
    spans: Sequence[tuple[int, int]], removed: Sequence[tuple[int, int]]
) -> list[tuple[int, int]]:
    """``spans`` with every part of ``removed`` cut out of it."""
    out: list[tuple[int, int]] = []
    for start, end in spans:
        cursor = start
        for cut_start, cut_end in removed:
            if cut_end <= cursor or cut_start >= end:
                continue
            if cut_start > cursor:
                out.append((cursor, cut_start))
            cursor = max(cursor, cut_end)
        if cursor < end:
            out.append((cursor, end))
    return out


#: Below this, a "stable" span is noise — a stray space or a shared bracket that
#: two unrelated sentences happen to have in common. Cutting on those produces a
#: body of alternating one-character fragments and placeholders, which is worse
#: than proposing nothing.
_MIN_STABLE_RUN = 8


def _cut(template: str, stable: Sequence[tuple[int, int]]) -> tuple[str, list[str]]:
    kept = [span for span in stable if span[1] - span[0] >= _MIN_STABLE_RUN]
    if not kept:
        return template, []

    pieces: list[str] = []
    names: list[str] = []
    cursor = 0
    for start, end in kept:
        if start > cursor:
            names.append(f"{PLACEHOLDER_PREFIX}_{len(names) + 1}")
            pieces.append("{{" + names[-1] + "}}")
        pieces.append(template[start:end])
        cursor = end
    if cursor < len(template):
        names.append(f"{PLACEHOLDER_PREFIX}_{len(names) + 1}")
        pieces.append("{{" + names[-1] + "}}")

    return "".join(pieces), names
