"""Module-neutral validation for the canonical prompt XML contract."""

from xml.etree import ElementTree

MAX_CANONICAL_CHARACTERS = 32_768
ALLOWED_BLOCKS = frozenset(
    {"system", "context", "instructions", "output_format", "examples", "constraints"}
)

#: The nameless block, and the second canonical form.
#:
#: A person who declines the conversion is saying *do not restructure my text*,
#: and the old answer — wrap it in `<instructions>`, XML-escaping the angle
#: brackets and ampersands on the way in — did not honour that: what came back
#: out of the registry was not what went in, and a prompt whose own subject is
#: markup came back mangled. So declining now wraps the text in `<>` … `</>`,
#: which is a marker rather than a tag: nothing is escaped, nothing is parsed,
#: and `prompt_composition.compose` removes the two markers again before the
#: body is dispatched. The provider therefore sees the original bytes.
VERBATIM_OPEN = "<>"
VERBATIM_CLOSE = "</>"


def verbatim_text(xml: str) -> str | None:
    """The text inside a nameless `<>` block, or ``None`` if this is not one.

    The close is the *last* `</>` rather than the first, which is what makes
    ``verbatim_text(wrap(text)) == text`` hold for every possible text — angle
    brackets, markers and all. A first-match rule would have made the one thing
    this form exists to guarantee false for exactly the texts that need it.

    A verbatim body is the whole body. There is no mixing it with named blocks,
    so there is nothing to scan past and no ordering to decide.
    """
    body = xml.strip()
    if len(body) < len(VERBATIM_OPEN) + len(VERBATIM_CLOSE):
        return None
    if not (body.startswith(VERBATIM_OPEN) and body.endswith(VERBATIM_CLOSE)):
        return None
    inner = body[len(VERBATIM_OPEN) : -len(VERBATIM_CLOSE)]
    # Exactly one newline off each end — the two `wrap_verbatim` put there, and
    # no more. Stripping every newline would be the one liberty this form is not
    # allowed to take: a prompt that opens on a blank line meant to.
    inner = inner.removeprefix("\n")
    return inner[:-1] if inner.endswith("\n") else inner


def wrap_verbatim(text: str) -> str:
    """One text, stored whole. The inverse of :func:`verbatim_text`."""
    return f"{VERBATIM_OPEN}\n{text}\n{VERBATIM_CLOSE}"


def unwrap_verbatim(xml: str) -> str:
    """The body as a provider must see it: markers gone, everything else kept.

    A pass-through for every named-block body, so callers on the dispatch path
    apply it unconditionally rather than asking which of the two forms they hold.
    """
    text = verbatim_text(xml)
    return xml if text is None else text


def validate_canonical_xml(xml: str) -> None:
    if len(xml) > MAX_CANONICAL_CHARACTERS:
        raise ValueError("canonical XML exceeds the revision size limit")
    # The verbatim form is never parsed as XML and never reaches a parser, so
    # the DOCTYPE refusal below — which exists to keep entity declarations away
    # from `ElementTree` — has nothing to protect here, and applying it anyway
    # would refuse a prompt whose subject is HTML for containing the word.
    if verbatim_text(xml) is not None:
        return
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("DOCTYPE and entity declarations are not allowed")
    try:
        root = ElementTree.fromstring(f"<prompt>{xml}</prompt>")
    except ElementTree.ParseError as error:
        raise ValueError("canonical XML is malformed") from error
    if root.text and root.text.strip():
        raise ValueError("text must be contained in a canonical block")
    if not list(root):
        raise ValueError("canonical XML must contain at least one block")
    for block in root:
        if block.tag not in ALLOWED_BLOCKS:
            raise ValueError(f"unsupported canonical block: {block.tag}")
        if block.attrib:
            raise ValueError("canonical blocks may not have attributes")
        if list(block):
            raise ValueError("canonical blocks may not be nested")
        if block.tail and block.tail.strip():
            raise ValueError("text must be contained in a canonical block")


#: The canonical block order. `ALLOWED_BLOCKS` is a set and a set has no order,
#: but every reader that renders or compares blocks side by side needs one, and
#: two readers inventing their own is two orders that agree until they do not.
BLOCK_ORDER: tuple[str, ...] = (
    "system",
    "context",
    "instructions",
    "output_format",
    "examples",
    "constraints",
)


def blocks_of(xml: str) -> dict[str, str]:
    """The canonical blocks of a body, as ``{tag: text}``. Missing blocks are absent.

    **Parsing, not validating.** :func:`validate_canonical_xml` refuses anything
    that is not exactly the contract; this accepts what it can read and returns
    what it found, because its callers hold text that has not been through the
    registry yet — a body somebody pasted into the import screen is checked for
    duplicates *before* anything decides whether it is canonical.

    Returns an empty mapping for text that is not canonical XML at all. The
    caller decides what that means; here it is simply *no blocks were found*,
    which is different from *the blocks were empty*.

    Repeated tags are joined with a blank line rather than last-wins. The
    contract forbids them, so this only ever fires on text that never reached the
    registry, and dropping half of somebody's instructions silently is the worse
    of the two ways to be wrong.
    """
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        return {}
    # A verbatim body has exactly one block and it is nameless, so there are no
    # named blocks to find. Stated rather than left to the parse error below,
    # because *no blocks* is the answer every caller here already handles — they
    # fall back to reading the whole text — and an accident that happens to
    # produce the right answer is not the same as the right answer.
    if verbatim_text(xml) is not None:
        return {}
    try:
        root = ElementTree.fromstring(f"<prompt>{xml}</prompt>")
    except ElementTree.ParseError:
        return {}

    found: dict[str, list[str]] = {}
    for block in root:
        if block.tag not in ALLOWED_BLOCKS:
            continue
        text = "".join(block.itertext()).strip()
        found.setdefault(block.tag, []).append(text)

    return {tag: "\n\n".join(parts).strip() for tag, parts in found.items() if any(parts)}
