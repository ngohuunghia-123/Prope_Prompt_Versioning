"""The nameless `<>` block: what "keep the text as it is" is allowed to mean.

Declining the conversion used to wrap the source in `<instructions>` with `&`,
`<` and `>` escaped, which meant the one button labelled *keep as is* was the one
that changed the text. The nameless block is the replacement, and it makes two
promises this file holds to:

1. **Nothing inside is touched.** Not escaped, not parsed, not size-normalised
   past the revision limit every body shares. A prompt whose subject is markup
   survives a round trip through the registry byte for byte.
2. **The markers never reach a provider.** `<>` and `</>` are Prope's notation
   for *this was stored whole*; `compose` — the one function every dispatch path
   goes through — removes them.

Between those two, the second is the one that would be silently wrong: a body
that kept its markers still validates, still stores, still releases, and only
shows up as two stray characters at the top of a system prompt somebody is being
billed for.
"""

import pytest

from prope.canonical_prompt import (
    MAX_CANONICAL_CHARACTERS,
    blocks_of,
    unwrap_verbatim,
    validate_canonical_xml,
    verbatim_text,
    wrap_verbatim,
)
from prope.prompt_composition import compose, render

# Every one of these is a body that the named-block contract refuses, and the
# whole point of the nameless block is that a person may keep it anyway.
AWKWARD = [
    "You are helpful.",
    "Use a <div> tag.",
    "Cost & margin, expressed as a > b.",
    "<!DOCTYPE html> is how an HTML document opens.",
    "<persona>not a canonical block</persona>",
    "an unclosed <tag",
    "<system>looks canonical but is not: </context>",
    "a </> marker inside the text",
    "\na body that opens on a blank line",
    "trailing newline\n",
    "Today is {{today}}.",
    "",
]


@pytest.mark.parametrize("text", AWKWARD, ids=lambda text: repr(text[:32]))
def test_the_round_trip_is_exact_for_any_text(text: str) -> None:
    """`verbatim_text(wrap_verbatim(t)) == t`, with no exceptions.

    Parametrised over the awkward cases rather than the easy one, because the
    easy one round-trips under a dozen wrong implementations. The two that
    actually pin the rule are the body carrying its own `</>` — which forces the
    close to be the LAST marker, not the first — and the ones with a leading or
    trailing newline, which forbid a convenience `.strip()`.
    """
    assert verbatim_text(wrap_verbatim(text)) == text


@pytest.mark.parametrize("text", AWKWARD, ids=lambda text: repr(text[:32]))
def test_a_body_the_named_contract_refuses_is_still_a_valid_verbatim_body(text: str) -> None:
    validate_canonical_xml(wrap_verbatim(text))


@pytest.mark.parametrize(
    "body",
    [
        "<>",
        "</>",
        "<>unclosed",
        "closed</>",
        "<system>x</system>",
        "plain text",
    ],
    ids=repr,
)
def test_what_is_not_a_verbatim_body(body: str) -> None:
    """Both markers, in that order, or it is not one.

    `verbatim_text` returning `None` is what routes a body to the XML parser, so
    a false positive here would mean a named-block body escaping validation
    entirely — every refusal in the canonical contract skipped by a prompt that
    happened to end in `</>`.
    """
    assert verbatim_text(body) is None


def test_the_markers_are_gone_from_what_the_provider_is_sent() -> None:
    """The promise the whole form rests on, at the only place it can be kept."""
    body = wrap_verbatim("You are a bot. Emit <result> tags.")

    composed = compose([{"role": "user", "content": "hi"}], body)

    assert composed[0] == {"role": "system", "content": "You are a bot. Emit <result> tags."}
    assert composed[1] == {"role": "user", "content": "hi"}


def test_a_named_block_body_is_dispatched_unchanged() -> None:
    """`compose` strips unconditionally, so this is the half that must not move.

    A canonical body's angle brackets are the prompt's own structure and the
    provider is meant to see them; an over-eager unwrap here would quietly
    rewrite every prompt in the registry that was converted properly.
    """
    body = "<system>You are helpful.</system>"

    assert compose([], body)[0]["content"] == body


def test_variables_are_substituted_before_the_markers_come_off() -> None:
    """`render` then `compose`, which is the order all four dispatch paths use.

    Worth asserting because the wrapper is the outermost thing in the string:
    a placeholder next to it must still be found, and the substituted value must
    not be re-wrapped or re-escaped on the way out.
    """
    body = wrap_verbatim("Today is {{today}}. Use <b>bold</b>.")

    composed = compose([], render(body, {"today": "Monday"}))

    assert composed[0]["content"] == "Today is Monday. Use <b>bold</b>."


def test_a_verbatim_body_reports_no_named_blocks() -> None:
    """What the similarity and comparison readers see, and why they cope.

    They already handle *no blocks* — it is the import screen's normal case,
    where nothing has been converted yet — and they fall back to reading the
    whole text. An empty mapping is therefore the answer that needs no new branch
    anywhere; a `{"instructions": ...}` here would have made a body nobody
    structured look structured.
    """
    assert blocks_of(wrap_verbatim("<system>not a block, just text</system>")) == {}


def test_the_size_limit_is_the_one_every_body_shares() -> None:
    """Verbatim opts out of the shape rules, not out of the storage limit."""
    validate_canonical_xml(wrap_verbatim("x" * (MAX_CANONICAL_CHARACTERS - 10)))

    with pytest.raises(ValueError, match="size limit"):
        validate_canonical_xml(wrap_verbatim("x" * MAX_CANONICAL_CHARACTERS))


def test_unwrap_is_a_pass_through_for_anything_that_is_not_wrapped() -> None:
    """Which is what lets the dispatch path apply it without asking."""
    assert unwrap_verbatim("<system>x</system>") == "<system>x</system>"
    assert unwrap_verbatim("not canonical at all") == "not canonical at all"
