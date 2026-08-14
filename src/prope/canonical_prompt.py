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
