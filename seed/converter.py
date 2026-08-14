"""Deterministic, offline conversion of a raw prompt file into canonical XML.

The product's own converter (`prope.prompt_conversion.convert_source`) is an LLM
call — probabilistic, one network round-trip per prompt, and gated on an OpenAI
key. That is the right tool for a human pasting one prompt into the app; it is
the wrong tool for seeding 359 files reproducibly. So this module does the split
deterministically and then hands the result to the *same* deterministic
serializer the product uses (`serialize_agent_output` + `validate_canonical_xml`),
so the bytes we store are canonical by construction, not by hope.

What "canonical" means here is fixed by `prope.canonical_prompt`: at most six
block types — system, context, instructions, examples, constraints,
output_format — each appearing at most once, no attributes, no nesting, content
escaped, whole thing <= 32,768 characters.

The heuristic is intentionally conservative:

* A decorative header (a title line, a "Source:" line, a divider) is stripped and
  its first line is offered as the prompt title.
* Sections are cut at Markdown `#`/`##` headings and at bare lines that *exactly*
  match a known section word ("Role", "Context", "Output format", ...). Bare
  lines are only treated as headings when they match a keyword, so ordinary
  Title-Case sentences never trip the splitter.
* A known heading routes its section to the matching block; an unknown heading's
  section falls to `instructions`; the preamble before the first heading seeds
  `system`.
* If nothing splits (pseudo-XML prompts, single-paragraph prompts), the whole
  cleaned body becomes one `system` block. Always valid, always complete.

Fidelity over cleverness: every character of the source (minus the decorative
header and the matched label lines the canonical format makes redundant) survives
into some block, so a conversion never silently drops prompt text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from prope.canonical_prompt import MAX_CANONICAL_CHARACTERS
from prope.prompt_conversion.domain import (
    BLOCK_ORDER,
    AgentOutput,
    ConversionBlock,
    serialize_agent_output,
)

# The six canonical block types, in a fixed precedence used only for deciding
# which bucket a preamble seeds. Serialization order is owned by BLOCK_ORDER.
SYSTEM = "system"
CONTEXT = "context"
INSTRUCTIONS = "instructions"
EXAMPLES = "examples"
CONSTRAINTS = "constraints"
OUTPUT_FORMAT = "output_format"

#: Section words we recognise, mapped to the canonical block they belong in.
#: Keys are lower-cased and stripped of a trailing ':' before lookup. Anything
#: not here is content, not a section boundary.
KEYWORD_TO_TYPE: dict[str, str] = {
    # system / role
    "role": SYSTEM,
    "persona": SYSTEM,
    "identity": SYSTEM,
    "system": SYSTEM,
    "system prompt": SYSTEM,
    "who you are": SYSTEM,
    "your role": SYSTEM,
    # context / background
    "context": CONTEXT,
    "background": CONTEXT,
    "situation": CONTEXT,
    "overview": CONTEXT,
    "domain": CONTEXT,
    "core mission": CONTEXT,
    "mission": CONTEXT,
    # instructions / task
    "instructions": INSTRUCTIONS,
    "instruction": INSTRUCTIONS,
    "task": INSTRUCTIONS,
    "tasks": INSTRUCTIONS,
    "your task": INSTRUCTIONS,
    "process": INSTRUCTIONS,
    "workflow": INSTRUCTIONS,
    "your workflow": INSTRUCTIONS,
    "steps": INSTRUCTIONS,
    "methodology": INSTRUCTIONS,
    "approach": INSTRUCTIONS,
    "procedure": INSTRUCTIONS,
    "objectives": INSTRUCTIONS,
    "objective": INSTRUCTIONS,
    "goal": INSTRUCTIONS,
    "goals": INSTRUCTIONS,
    "responsibilities": INSTRUCTIONS,
    "when to use": INSTRUCTIONS,
    "when to use this skill": INSTRUCTIONS,
    "how to use": INSTRUCTIONS,
    "guidelines": INSTRUCTIONS,
    # examples
    "example": EXAMPLES,
    "examples": EXAMPLES,
    "sample": EXAMPLES,
    "samples": EXAMPLES,
    "few-shot": EXAMPLES,
    "demonstrations": EXAMPLES,
    # constraints / rules
    "constraints": CONSTRAINTS,
    "constraint": CONSTRAINTS,
    "rules": CONSTRAINTS,
    "rule": CONSTRAINTS,
    "critical rules": CONSTRAINTS,
    "guardrails": CONSTRAINTS,
    "safety": CONSTRAINTS,
    "limitations": CONSTRAINTS,
    "boundaries": CONSTRAINTS,
    "restrictions": CONSTRAINTS,
    "policies": CONSTRAINTS,
    "policy": CONSTRAINTS,
    "requirements": CONSTRAINTS,
    # output
    "output": OUTPUT_FORMAT,
    "output format": OUTPUT_FORMAT,
    "output structure": OUTPUT_FORMAT,
    "format": OUTPUT_FORMAT,
    "response format": OUTPUT_FORMAT,
    "deliverables": OUTPUT_FORMAT,
    "deliverable": OUTPUT_FORMAT,
}

_MD_HEADING = re.compile(r"^\s{0,3}(#{1,2})\s+(.+?)\s*#*\s*$")
_DIVIDER = re.compile(r"^\s*([-=_*]){3,}\s*$")
_MULTIPLE_BLANKS = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class Conversion:
    """The result of converting one file."""

    title: str
    xml: str
    block_types: tuple[str, ...]
    truncated: bool


def _normalize_keyword(text: str) -> str | None:
    """Return the canonical block for a heading's text, or None if unrecognised."""
    key = text.strip().strip(":").strip().lower()
    # Collapse internal whitespace so "Output   Format" matches "output format".
    key = re.sub(r"\s+", " ", key)
    return KEYWORD_TO_TYPE.get(key)


def _looks_like_bare_heading(line: str) -> str | None:
    """A short bare line that exactly matches a section word is a heading.

    Restricting bare headings to known keywords keeps ordinary Title-Case
    sentences ("You are a world-class ...") from being mistaken for section
    labels — the failure that would shatter a paragraph into fragments.
    """
    stripped = line.strip()
    if not stripped or len(stripped.split()) > 4:
        return None
    return _normalize_keyword(stripped)


def _strip_decorative_header(lines: list[str]) -> tuple[list[str], str | None]:
    """Remove a leading title/source/divider block; return (body, title).

    Only consumes the first few lines and only when a divider or a "Source:"/URL
    attribution line makes the intent unambiguous. A file that opens straight
    into "Role" keeps every line.
    """
    title: str | None = None
    header_end = 0
    saw_divider = False
    for index, raw in enumerate(lines[:6]):
        line = raw.strip()
        if _DIVIDER.match(line):
            header_end = index + 1
            saw_divider = True
            break
        lowered = line.lower()
        looks_like_meta = (
            lowered.startswith("source:")
            or lowered.startswith("http://")
            or lowered.startswith("https://")
            or lowered.startswith("# source")
            or lowered.startswith("author:")
        )
        md = _MD_HEADING.match(raw)
        if index == 0 and md and _normalize_keyword(md.group(2)) is None:
            # A leading '# Title' that is not itself a section word — capture it.
            title = md.group(2).strip()
            header_end = index + 1
            continue
        if index == 0 and not md and not looks_like_meta:
            # No divider-style header; the file starts with real content.
            break
        if looks_like_meta:
            if title is None and index == 0:
                title = line
            header_end = index + 1
            continue
        # A non-meta, non-divider line ends the header scan.
        break

    if not saw_divider and header_end and header_end < len(lines):
        # We only trimmed a '# Title' line (no divider). Keep it as the title but
        # do not eat following content beyond that single line.
        header_end = min(header_end, 1)

    body = lines[header_end:]
    # Drop leading blank lines left behind by the header.
    while body and not body[0].strip():
        body.pop(0)
    return body, title


def _segment(body: list[str]) -> list[tuple[str | None, list[str]]]:
    """Cut the body into (block_type_or_None, content_lines) sections."""
    sections: list[tuple[str | None, list[str]]] = []
    current_type: str | None = None
    current: list[str] = []
    started = False

    def flush() -> None:
        if current or started:
            sections.append((current_type, current.copy()))

    for raw in body:
        md = _MD_HEADING.match(raw)
        heading_text: str | None = None
        if md is not None:
            heading_text = md.group(2)
        else:
            bare = _looks_like_bare_heading(raw)
            if bare is not None:
                heading_text = raw.strip()

        if heading_text is not None:
            flush()
            current_type = _normalize_keyword(heading_text)
            # Drop the label line when it is a recognised section word (the
            # canonical block type already carries its meaning); keep an unknown
            # heading as a content line so its wording is not lost.
            current = [] if current_type is not None else [raw.rstrip()]
            started = True
            continue

        current.append(raw.rstrip())
        started = True

    flush()
    return sections


def _clean(text: str) -> str:
    """Collapse >2 blank lines and trim trailing whitespace."""
    return _MULTIPLE_BLANKS.sub("\n\n", text).strip()


def _assemble_blocks(sections: list[tuple[str | None, list[str]]]) -> dict[str, str]:
    """Merge sections into at most one string per canonical block type."""
    buckets: dict[str, list[str]] = {}

    # Preamble = the first section with no heading. It seeds `system` unless a
    # real system/role section also exists, in which case it becomes context.
    has_system_section = any(t == SYSTEM for t, _ in sections)

    for index, (block_type, lines) in enumerate(sections):
        content = _clean("\n".join(lines))
        if not content:
            continue
        target = block_type
        if target is None:
            if index == 0:
                target = CONTEXT if has_system_section else SYSTEM
            else:
                target = INSTRUCTIONS
        buckets.setdefault(target, []).append(content)

    return {
        block_type: _clean("\n\n".join(parts))
        for block_type, parts in buckets.items()
        if _clean("\n\n".join(parts))
    }


def _fit_to_limit(blocks: dict[str, str]) -> tuple[dict[str, str], bool]:
    """Trim block content until the serialized XML fits MAX_CANONICAL_CHARACTERS.

    Escaping (`<` -> `&lt;`) grows content, so we measure with the real
    serializer and, while over budget, shorten the currently-largest block. Only
    the two ~33 KB source files ever reach this path.
    """
    truncated = False
    marker = "\n\n[... truncated to fit the 32,768-character canonical limit ...]"
    while True:
        xml = _serialize(blocks)
        if len(xml) <= MAX_CANONICAL_CHARACTERS:
            return blocks, truncated
        truncated = True
        # Shrink the largest block by the overflow plus headroom for escaping
        # and the marker.
        victim = max(blocks, key=lambda key: len(blocks[key]))
        overflow = len(xml) - MAX_CANONICAL_CHARACTERS
        cut = overflow + len(marker) + 64
        kept = blocks[victim][: max(1, len(blocks[victim]) - cut)].rstrip()
        blocks[victim] = (kept + marker) if kept else marker.strip()


def _serialize(blocks: dict[str, str]) -> str:
    """Build canonical XML from a {type: content} map via the product serializer."""
    ordered = [
        ConversionBlock(type=block_type, content=blocks[block_type])
        for block_type in BLOCK_ORDER
        if block_type in blocks
    ]
    output = AgentOutput(blocks=ordered)
    # source_text is only used by the serializer to assert template-variable
    # parity; the blocks ARE a partition of the source, so the concatenation of
    # their content carries exactly the same {{variables}}.
    source_text = "".join(block.content for block in output.blocks)
    return serialize_agent_output(output, source_text=source_text)


def convert_text(raw_text: str) -> tuple[str, dict[str, str]]:
    """Split raw prompt text into (title, {block_type: content}). No XML yet."""
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    body, header_title = _strip_decorative_header(lines)
    sections = _segment(body)
    blocks = _assemble_blocks(sections)

    if not blocks:
        cleaned = _clean("\n".join(body)) or _clean(raw_text)
        blocks = {SYSTEM: cleaned}

    return header_title or "", blocks


def convert_file(raw_text: str, *, fallback_title: str) -> Conversion:
    """Convert one prompt file's text into a canonical-XML `Conversion`."""
    if not raw_text.strip():
        raise ValueError("prompt file is empty")

    header_title, blocks = convert_text(raw_text)
    blocks, truncated = _fit_to_limit(blocks)
    xml = _serialize(blocks)

    title = (header_title or fallback_title).strip()[:200] or fallback_title
    present = tuple(bt for bt in BLOCK_ORDER if bt in blocks)
    return Conversion(title=title, xml=xml, block_types=present, truncated=truncated)
