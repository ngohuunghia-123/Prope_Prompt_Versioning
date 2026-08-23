"""Module-neutral validation for the canonical prompt XML contract."""

from xml.etree import ElementTree

MAX_CANONICAL_CHARACTERS = 32_768
ALLOWED_BLOCKS = frozenset(
    {"system", "context", "instructions", "output_format", "examples", "constraints"}
)


def validate_canonical_xml(xml: str) -> None:
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("DOCTYPE and entity declarations are not allowed")
    if len(xml) > MAX_CANONICAL_CHARACTERS:
        raise ValueError("canonical XML exceeds the revision size limit")
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
