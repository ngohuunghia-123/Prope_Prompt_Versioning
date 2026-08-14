"""Validation and deterministic serialization for prompt conversion."""

import json
import re
from collections import Counter
from dataclasses import dataclass
from html import escape
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from prope.canonical_prompt import MAX_CANONICAL_CHARACTERS, validate_canonical_xml

MAX_SOURCE_CHARACTERS = MAX_CANONICAL_CHARACTERS

SourceFormat = Literal["txt", "markdown", "json", "yaml"]
BlockType = Literal[
    "system",
    "context",
    "instructions",
    "output_format",
    "examples",
    "constraints",
]

BLOCK_ORDER: tuple[BlockType, ...] = (
    "system",
    "context",
    "instructions",
    "examples",
    "constraints",
    "output_format",
)
BLOCK_ORDER_INDEX = {name: index for index, name in enumerate(BLOCK_ORDER)}

VARIABLE_PATTERN = re.compile(r"{{[^{}]+}}")


class InvalidSourceError(ValueError):
    pass


class InvalidAgentOutputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NormalizedSource:
    text: str
    format: SourceFormat


class ConversionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: BlockType
    content: str = Field(min_length=1, max_length=MAX_SOURCE_CHARACTERS)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("block content must not be blank")
        return value


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # There are only six semantic types, therefore more than six blocks
    # is always fragmentation rather than useful structure.
    blocks: list[ConversionBlock] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def block_types_must_be_unique(self) -> "AgentOutput":
        types = [block.type for block in self.blocks]
        duplicates = [name for name, count in Counter(types).items() if count > 1]

        if duplicates:
            raise ValueError(
                f"duplicate semantic block types: {', '.join(sorted(duplicates))}"
            )

        return self


def normalize_source(source_text: str, source_format: str) -> NormalizedSource:
    aliases = {
        "md": "markdown",
        "markdown": "markdown",
        "yml": "yaml",
    }
    normalized_format = aliases.get(source_format.lower(), source_format.lower())

    if normalized_format not in {"txt", "markdown", "json", "yaml"}:
        raise InvalidSourceError("source_format is not supported")

    if not source_text or not source_text.strip():
        raise InvalidSourceError("source_text must not be empty")

    if len(source_text) > MAX_SOURCE_CHARACTERS:
        raise InvalidSourceError(
            f"source_text exceeds {MAX_SOURCE_CHARACTERS} characters"
        )

    try:
        if normalized_format == "json":
            json.loads(source_text)
        elif normalized_format == "yaml":
            yaml.safe_load(source_text)
    except (json.JSONDecodeError, yaml.YAMLError) as error:
        raise InvalidSourceError(f"invalid {normalized_format} syntax") from error

    return NormalizedSource(
        text=source_text,
        format=normalized_format,  # type: ignore[arg-type]
    )


#: A Markdown heading of four words or fewer is a SECTION LABEL — `# Role`,
#: `## Output format` — and a faithful conversion drops it, because the label's
#: meaning survives as the block's type. A longer heading is a sentence somebody
#: wrote and must be kept. Four is a judgement call and it is written here so
#: that the next person tuning `COVERAGE_FLOOR` finds the knob rather than the
#: symptom.
#: `[^\S\n]` rather than `\s` at every position, because `\s` matches a newline
#: and `re.MULTILINE` makes `$` match before one — so `\s+` inside the word
#: window let a heading swallow the FIRST LINE OF ITS OWN SECTION, and the
#: denominator came out at half its true size while every ratio read ~1.9.
#: There is no `\s` in either pattern and there must not be one.
_INLINE_SPACE = r"[^\S\n]"
_MARKDOWN_LABEL_HEADING = re.compile(
    rf"^{_INLINE_SPACE}{{0,3}}#{{1,6}}{_INLINE_SPACE}+"
    rf"\S+(?:{_INLINE_SPACE}+\S+){{0,3}}{_INLINE_SPACE}*$",
    re.MULTILINE,
)
_MARKDOWN_MARKER = re.compile(
    rf"^{_INLINE_SPACE}{{0,3}}"
    rf"(#{{1,6}}{_INLINE_SPACE}+|[-*+]{_INLINE_SPACE}+|>{_INLINE_SPACE}?"
    rf"|\d+[.)]{_INLINE_SPACE}+)",
    re.MULTILINE,
)
_MARKDOWN_EMPHASIS = re.compile(r"[*_`]{1,3}")
_WHITESPACE_RUN = re.compile(r"\s+")


def _measure(text: str) -> int:
    """Characters, with every whitespace run counted as one.

    Both sides of the coverage ratio go through this, so that a JSON source's
    indentation and a block's line breaks cannot move the number.
    """
    return len(_WHITESPACE_RUN.sub(" ", text).strip())


def _scalars(node: object) -> list[str]:
    """Every leaf value in a parsed JSON/YAML document. Keys are syntax, not content.

    Mirrors the instruction the agent is given — "only remove syntax that
    clearly belongs to the source format itself, such as ... structural
    JSON/YAML field syntax" — so that the denominator and the agent are
    measuring the same thing.
    """
    if isinstance(node, dict):
        return [value for child in node.values() for value in _scalars(child)]
    if isinstance(node, (list, tuple)):
        return [value for child in node for value in _scalars(child)]
    if node is None:
        return []
    return [str(node)]


def source_content_characters(source_text: str, source_format: str) -> int:
    """The source's CONTENT length, with its format's syntax discounted.

    Without this the ratio below punishes exactly the formats the module exists
    to accept. An indented JSON source is roughly 40% braces, quotes, commas and
    keys; a Markdown source with six headings loses a fixed tax per section. A
    perfect conversion of either would score far under any floor worth setting,
    so the floor would have to be lowered until it stopped catching summaries —
    which is the failure this metric exists for.

    Falls back to the raw length when a document does not parse. That cannot
    happen through the API, where `normalize_source` has already refused it, but
    it can happen to a golden-set record and a silent zero would be worse than a
    pessimistic ratio.
    """
    if source_format in {"json", "yaml"}:
        try:
            parsed = (
                json.loads(source_text)
                if source_format == "json"
                else yaml.safe_load(source_text)
            )
        except (json.JSONDecodeError, yaml.YAMLError):
            return _measure(source_text)
        return _measure(" ".join(_scalars(parsed)))

    if source_format == "markdown":
        without_labels = _MARKDOWN_LABEL_HEADING.sub("", source_text)
        return _measure(
            _MARKDOWN_EMPHASIS.sub("", _MARKDOWN_MARKER.sub("", without_labels))
        )

    return _measure(source_text)


def content_coverage(
    output: AgentOutput,
    *,
    source_text: str,
    source_format: str = "txt",
) -> float:
    """Classified characters over source CONTENT characters. A drift signal, not a gate.

    The agent's one forbidden behaviour that deterministic validation cannot
    catch is SUMMARIZING: an output that drops a paragraph is still well-formed
    XML with every variable intact, so nothing in `serialize_agent_output`
    refuses it. What changes is this ratio — a faithful conversion lands near
    1.0 whatever format it came from, while a summary lands far below it.

    Deliberately a number and not a judgement. It costs nothing, it leaves no
    content anywhere, and it is the whole of this module's fourth-pillar signal:
    `service.py` records it as a Prometheus histogram and a Langfuse score, and
    an alert reads the histogram. An LLM-as-judge would be a second model call
    over the same corporate prompt body for a worse version of the same alarm.

    Ratios above 1.0 are possible and are not clipped — an agent that duplicates
    content into two blocks is also broken, and clipping would hide it.
    """
    content_length = source_content_characters(source_text, source_format)
    if not content_length:
        return 0.0

    classified = _measure(" ".join(block.content for block in output.blocks))
    return classified / content_length


def serialize_agent_output(output: AgentOutput, *, source_text: str) -> str:
    source_variables = Counter(VARIABLE_PATTERN.findall(source_text))
    output_variables = Counter(
        variable
        for block in output.blocks
        for variable in VARIABLE_PATTERN.findall(block.content)
    )

    if source_variables != output_variables:
        # Name the variables, because this string is what the bounded repair
        # attempt sends back to the model. "did not preserve template variables"
        # asks it to diff two documents it can no longer see; "dropped {{name}}"
        # is an instruction. The names are placeholders out of a source the model
        # was just given, so echoing them adds no exposure.
        dropped = sorted((source_variables - output_variables).elements())
        added = sorted((output_variables - source_variables).elements())
        detail = ", ".join(
            part
            for part in (
                f"dropped {' '.join(dropped)}" if dropped else "",
                f"invented {' '.join(added)}" if added else "",
            )
            if part
        )
        raise InvalidAgentOutputError(
            f"agent output did not preserve template variables exactly: {detail}"
        )

    # Never let the model decide serialization order.
    ordered_blocks = sorted(
        output.blocks,
        key=lambda block: BLOCK_ORDER_INDEX[block.type],
    )

    xml = "\n\n".join(
        f"<{block.type}>\n{escape(block.content, quote=False)}\n</{block.type}>"
        for block in ordered_blocks
    )

    if len(xml) > MAX_CANONICAL_CHARACTERS:
        raise InvalidAgentOutputError(
            "generated XML exceeds the revision size limit"
        )

    try:
        validate_canonical_xml(xml)
    except ValueError as error:
        raise InvalidAgentOutputError(str(error)) from error

    return xml
