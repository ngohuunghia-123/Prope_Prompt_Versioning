"""Lane A. Deterministic, free, no model, no dispatch, and it runs on every card.

**Pure functions over one dataclass.** Nothing here touches a session, a
provider, or a clock. That is what lets the whole lane be tested without a
database and run on a keystroke-debounced save without a budget conversation —
and it is why Lane A is the one lane that runs unasked (D-08).

**Two parsers are reused and none is written.** ``prope.canonical_prompt`` knows
what a canonical block is and ``prope.prompt_composition.PLACEHOLDER`` knows what
a variable is. A second placeholder regex in this codebase would be a second
definition of what gets substituted, and the one that drifted would be this one —
which would make the card report on a body that production never renders.

**The only proposed edit in the module is here** (D-05, SR-10). Pre-publish there
is no baseline: on a fresh import there is usually no suite either, so an author
who accepts a rewrite and *then* writes cases writes them against the edited
body, and the before was never measured. That is the 26/30 → 9/30 regression,
invisible by construction. Relocating an interpolation out of an instruction
block has a definition of correct that does not require running the prompt.
*"Tighten this guardrail's wording"* does not, and it lives in
`prompt-improvement` behind a baseline and an eval gate.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from xml.etree import ElementTree

from prope.prompt_composition import PLACEHOLDER
from prope.prompt_readiness.domain import (
    Acts,
    Audience,
    Finding,
    RuleId,
    Sensitivity,
    Severity,
    UsageProfile,
)

__all__ = ["StaticInputs", "run_static_lane"]

#: A suite with fewer cases than this passes too easily to be evidence. Deck 7
#: slide 13's golden-dataset discipline, at the smallest number that is not zero:
#: the point is not that five is enough, it is that one is a coin toss with
#: ceremony.
THIN_SUITE_CASES: Final = 5

#: Roughly four characters to the token. A real tokenizer would be a dependency
#: and a model-specific one at that, and the figure is rendered as *about* — an
#: order of magnitude is what a person needs to decide whether the body is worth
#: shortening, and a precise number would invite a precision this cannot support.
CHARACTERS_PER_TOKEN: Final = 4

#: Blocks whose content is INSTRUCTION rather than data. A `{{variable}}` here is
#: text an attacker supplies being read at instruction priority — deck 5 slide 38.
INSTRUCTION_BLOCKS: Final = frozenset({"instructions", "constraints", "output_format"})

#: The canonical reading order. `context` before `instructions` because an
#: instruction that interprets context the model has not read yet is an
#: instruction read twice or not at all.
CANONICAL_ORDER: Final = (
    "system",
    "context",
    "instructions",
    "constraints",
    "output_format",
    "examples",
)

#: Near-misses: brace shapes a person writes when they mean a variable and that
#: `PLACEHOLDER` will not match. Single braces, `${}` shell style, `%s`, and a
#: `{{ }}` carrying a character the real pattern excludes.
_NEAR_MISS = re.compile(r"(?<!\{)\{[^{}\n]{1,64}\}(?!\})|\$\{[^}\n]{1,64}\}|%\((?:[^)\n]{1,64})\)s")


@dataclass(frozen=True, slots=True)
class StaticInputs:
    """Everything Lane A reads, gathered by the caller.

    A dataclass rather than four arguments because the set grows, and because
    every field here is a fact somebody else's module owns — which makes this
    type the written record of exactly what this module needs from them.
    """

    body: str
    profile: UsageProfile
    #: How many eval suites this prompt currently has, and how many cases they
    #: hold between them. From evaluation, which owns both numbers.
    suite_count: int = 0
    case_count: int = 0


def _blocks(body: str) -> list[tuple[str, str]]:
    """``(tag, text)`` per canonical block, in document order. Empty on a parse failure.

    Silent on failure, deliberately. A body that will not parse is already
    refused by prompt-registry's own validation before it can be saved, so a
    finding about it here would be a second refusal for a state that cannot
    reach this code — and raising would turn a card read into a 500 for a
    revision somebody can see.
    """
    try:
        root = ElementTree.fromstring(f"<prompt>{body}</prompt>")
    except ElementTree.ParseError:
        return []
    return [(child.tag, "".join(child.itertext())) for child in root]


def _interpolation_inside_instructions(inputs: StaticInputs) -> Finding | None:
    """Spotlighting. Deck 5 slide 38, and the one rule carrying an edit.

    The remedy moves the variable's block, not the variable: the placeholder
    keeps its exact spelling, so ``required_variables`` returns the identical set
    before and after and AC-6's round-trip holds by construction rather than by
    care.
    """
    offenders: list[tuple[str, str]] = []
    for tag, text in _blocks(inputs.body):
        if tag not in INSTRUCTION_BLOCKS:
            continue
        offenders.extend((tag, name) for name in PLACEHOLDER.findall(text))
    if not offenders:
        return None

    names = sorted({name for _tag, name in offenders})
    return Finding(
        rule_id=RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS,
        # A warning rather than advice: this is the mechanism behind the injection
        # cases the probe measures, so a card that called it advice would be
        # rating the cause below the symptom.
        severity=Severity.WARNING,
        params={
            "variables": names,
            "blocks": sorted({tag for tag, _name in offenders}),
            "count": len(offenders),
        },
        proposed_body=_relocate_to_context(inputs.body, names),
    )


def _relocate_to_context(body: str, names: Sequence[str]) -> str | None:
    """Move the offending placeholders into a ``<context>`` block. Parser-derived.

    Returns ``None`` when the move cannot be made mechanically — a placeholder
    embedded mid-sentence inside an instruction cannot be relocated without
    rewriting the sentence, and rewriting a sentence is a semantic act this lane
    is not permitted to perform at any confidence (D-05).

    What it CAN do, and does: where an instruction block's placeholder already
    sits on a line of its own, that line moves into ``<context>`` with a label.
    Every declared variable survives with its exact spelling, which is what makes
    the round-trip assertion hold.
    """
    blocks = _blocks(body)
    if not blocks:
        return None

    moved: list[str] = []
    rewritten: list[tuple[str, str]] = []
    for tag, text in blocks:
        if tag not in INSTRUCTION_BLOCKS:
            rewritten.append((tag, text))
            continue
        kept_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            matches = PLACEHOLDER.findall(stripped)
            # A line that is ENTIRELY one placeholder, optionally with a short
            # label before it. Anything else is a sentence, and a sentence is not
            # ours to move.
            if len(matches) == 1 and matches[0] in names and len(stripped) <= 80:
                moved.append(stripped)
                continue
            kept_lines.append(line)
        rewritten.append((tag, "\n".join(kept_lines)))

    if not moved:
        return None

    context_addition = "\n".join(moved)
    out: list[str] = []
    seen_context = False
    for tag, text in rewritten:
        if tag == "context":
            seen_context = True
            text = f"{text.rstrip()}\n{context_addition}\n"
        out.append(f"<{tag}>{text}</{tag}>")
    if not seen_context:
        # Inserted after `system` if there is one, first otherwise — the
        # canonical order, so the proposal does not create the structure finding
        # while fixing the interpolation one.
        block = f"<context>\n{context_addition}\n</context>"
        insert_at = 1 if rewritten and rewritten[0][0] == "system" else 0
        out.insert(insert_at, block)
    return "".join(out)


def _placeholder_will_not_substitute(inputs: StaticInputs) -> Finding | None:
    """Braces that reach the model as literal text.

    ``render`` substitutes what ``PLACEHOLDER`` matches and nothing else, so
    ``{customer_name}`` is sent verbatim to the provider. Silent, cheap to
    write by accident, and invisible until somebody reads an answer that
    mentions curly brackets.
    """
    suspects = sorted({match.group(0) for match in _NEAR_MISS.finditer(inputs.body)})
    if not suspects:
        return None
    return Finding(
        rule_id=RuleId.PLACEHOLDER_WILL_NOT_SUBSTITUTE,
        severity=Severity.WARNING,
        params={"found": suspects[:10], "count": len(suspects)},
    )


def _canonical_structure_weak(inputs: StaticInputs) -> Finding | None:
    """No instructions, or blocks out of reading order."""
    blocks = _blocks(inputs.body)
    if not blocks:
        return None
    tags = [tag for tag, _text in blocks]

    problems: list[str] = []
    if "instructions" not in tags:
        problems.append("no_instructions")

    ordered = [tag for tag in tags if tag in CANONICAL_ORDER]
    positions = [CANONICAL_ORDER.index(tag) for tag in ordered]
    if positions != sorted(positions):
        problems.append("out_of_order")

    if not problems:
        return None
    return Finding(
        rule_id=RuleId.CANONICAL_STRUCTURE_WEAK,
        severity=Severity.ADVICE,
        params={"problems": problems, "order": tags},
    )


def _eval_coverage(inputs: StaticInputs) -> Finding | None:
    """No suite, or a thin one.

    **Severity moves with the profile and existence does not.** *"You have no
    tests"* is true whatever the prompt is for; how much it matters is not. So
    the rule fires for everyone and the weight changes, rather than the rule
    being suppressed for an internal prompt — which would leave the author of a
    synthetic-data prompt with no prompt at all to add coverage they might still
    want.
    """
    resolved = inputs.profile.resolve()
    exposed = resolved.audience != Audience.INTERNAL or resolved.acts != Acts.ANSWERS_ONLY

    if inputs.suite_count == 0:
        return Finding(
            rule_id=RuleId.NO_EVAL_COVERAGE,
            severity=Severity.WARNING if exposed else Severity.ADVICE,
            params={"suites": 0},
        )
    if inputs.case_count < THIN_SUITE_CASES:
        return Finding(
            rule_id=RuleId.THIN_EVAL_COVERAGE,
            severity=Severity.ADVICE,
            params={"cases": inputs.case_count, "threshold": THIN_SUITE_CASES},
        )
    return None


def _lethal_trifecta(inputs: StaticInputs) -> Finding | None:
    """Deck 5 slide 41, computed from a declaration rather than guessed.

    The finding is generated whenever the declaration says all three legs are
    present; the ADMISSION clause in ``profile.py`` says the same thing, so this
    one rule is checked twice. That is deliberate and not redundant: the clause
    is what the card quotes back as ``admitted_by``, and a rule that generated
    itself unconditionally and relied on the filter would have no params to show.
    """
    resolved = inputs.profile.resolve()
    private = resolved.sensitivity in (Sensitivity.BUSINESS, Sensitivity.PERSONAL_DATA)
    untrusted = resolved.untrusted_input != "none"
    acts_out = resolved.acts in (Acts.EMITS_TOOL_CALLS, Acts.IRREVERSIBLE)
    if not (private and untrusted and acts_out):
        return None
    return Finding(
        rule_id=RuleId.LETHAL_TRIFECTA,
        severity=Severity.WARNING,
        params={
            "sensitivity": str(resolved.sensitivity),
            "untrusted_input": str(resolved.untrusted_input),
            "acts": str(resolved.acts),
            "assumed": not inputs.profile.is_declared,
        },
    )


def _body_cost(inputs: StaticInputs) -> Finding | None:
    """What the body alone costs on every call, before any input or output.

    Always advice and never a warning: a long body is a trade somebody made, not
    a defect. The number is here so the trade is visible at the moment it is
    still cheap to change.
    """
    tokens = max(1, len(inputs.body) // CHARACTERS_PER_TOKEN)
    return Finding(
        rule_id=RuleId.BODY_COST,
        severity=Severity.ADVICE,
        params={"approx_tokens": tokens, "characters": len(inputs.body)},
    )


def _profile_undeclared(inputs: StaticInputs) -> Finding | None:
    """Nobody answered, so everything above ran against the worst case.

    The only rule whose remedy is a dropdown rather than an edit, and the one
    that makes the conservative default honest instead of a silent assertion
    that somebody called this prompt public.
    """
    if inputs.profile.is_declared:
        return None
    missing = [
        axis
        for axis, value in inputs.profile.as_dict().items()
        if value == "undeclared"
    ]
    return Finding(
        rule_id=RuleId.PROFILE_UNDECLARED,
        severity=Severity.ADVICE,
        params={"missing": missing, "assumed": inputs.profile.resolve().as_dict()},
    )


#: Order is the order they are generated in, not the order they are shown in —
#: ``apply_profile`` sorts the card. Kept as a tuple so adding a rule is one line
#: and so a test can assert the catalogue and this list agree.
_RULES = (
    _interpolation_inside_instructions,
    _placeholder_will_not_substitute,
    _canonical_structure_weak,
    _eval_coverage,
    _lethal_trifecta,
    _body_cost,
    _profile_undeclared,
)


def run_static_lane(inputs: StaticInputs) -> tuple[Finding, ...]:
    """Every Lane A rule, unfiltered.

    **Unfiltered on purpose.** The profile filter runs afterwards, in
    ``profile.apply_profile``, so that a suppression is counted — see that
    module's docstring. Returning a filtered list from here would make the same
    card and lose the number that proves the profile is doing anything.
    """
    return tuple(finding for rule in _RULES if (finding := rule(inputs)) is not None)
