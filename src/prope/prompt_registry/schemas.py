"""INT-024's wire types. **`search_text` is in none of them, and cannot be.**

T-017 is the reason every model below lists its fields explicitly instead of
reading them off the row: ``prompt_property.search_text`` is a second copy of
the prompt body on the table every list endpoint reads, so a
``from_attributes`` model over the whole row would return every body in a page
of titles. There is no ``model_config = ConfigDict(from_attributes=True)`` in
this file and there must not be one.

The omission is belt; ``tests/security/test_search_text_never_leaves_the_
process.py`` is braces — it scans **whole responses** for a known body string
rather than checking a field allow-list, because the field a future endpoint
leaks it on is by definition one no allow-list mentions.

``extra="forbid"`` throughout, as in every other module's schemas: a request
body carrying a field this API does not know is a client that believes something
untrue about it, and answering ``422`` is how it finds out.
"""

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from prope.canonical_prompt import validate_canonical_xml
from prope.prompt_registry.domain import (
    MAX_BODY_CHARACTERS,
    MAX_CHANGE_SUMMARY_CHARACTERS,
    MAX_PURPOSE_CHARACTERS,
    MAX_TAG_CHARACTERS,
    MAX_TAGS,
    MAX_TITLE_CHARACTERS,
    LineOp,
    PromptStatus,
    RevisionStatus,
)

__all__ = [
    "ActivityEntryRead",
    "CallRecordRead",
    "DiffRead",
    "FieldChangeRead",
    "LineChangeRead",
    "PromptCreate",
    "PromptRead",
    "PromptUpdate",
    "RevisionCreate",
    "RevisionRead",
    "RevisionSummaryRead",
]

#: A-021's shape, and the same pattern the database CHECK carries. Declared as a
#: pydantic constraint as well as a constraint so the caller meets a ``422``
#: naming the field rather than a ``500`` naming a constraint they cannot read.
NAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,62}$"

Namespace = Annotated[str, Field(pattern=NAME_PATTERN)]

Name = Annotated[str, Field(pattern=NAME_PATTERN)]

Tags = Annotated[
    list[Annotated[str, Field(min_length=1, max_length=MAX_TAG_CHARACTERS)]],
    Field(max_length=MAX_TAGS),
]

#: A-050, at the edge. **Characters, not bytes**, matching
#: ``ck_revision_body_length`` — ADR-0053 makes Vietnamese the one interface
#: language and a byte cap would be about a third of the text a character cap
#: allows, which would read to a Vietnamese author as an arbitrary limit that
#: their English colleague does not hit.
#:
#: Enforced here as well as in the database so the author sees a limit message
#: with the current size rather than a truncated save — truncating a prompt body
#: silently would corrupt the asset the product exists to protect.
Body = Annotated[str, Field(min_length=1, max_length=MAX_BODY_CHARACTERS)]

ChangeSummary = Annotated[str, Field(min_length=1, max_length=MAX_CHANGE_SUMMARY_CHARACTERS)]


class PromptCreate(BaseModel):
    """``POST /api/v1/prompts``. Private by default, which is BR-01 as a default value."""

    model_config = ConfigDict(extra="forbid")

    namespace: Namespace
    name: Name
    title: str = Field(min_length=1, max_length=MAX_TITLE_CHARACTERS)
    purpose: str = Field(default="", max_length=MAX_PURPOSE_CHARACTERS)
    access_level: str = Field(default="private", pattern=r"^(private|workspace)$")
    tags: Tags = []
    owner_id: str | None = None


class PromptUpdate(BaseModel):
    """``PATCH /api/v1/prompts/{id}``. Five fields, and the model name is not among them.

    A-021 makes ``namespace/name`` immutable once created: it is what a consuming
    product calls, and renaming it breaks every caller with no error anywhere.
    There is deliberately no field here that could.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE_CHARACTERS)
    purpose: str | None = Field(default=None, max_length=MAX_PURPOSE_CHARACTERS)
    access_level: str | None = Field(default=None, pattern=r"^(private|workspace)$")
    tags: Tags | None = None
    owner_id: str | None = None


class RevisionCreate(BaseModel):
    """``POST /api/v1/prompts/{id}/revisions``. The change summary is required (A-050).

    Not optional and not defaulted: the summary is what makes the search corpus
    recover *"which prompt did we change for the refund thing"* years later, and
    a field that may be skipped is a field that is skipped.
    """

    model_config = ConfigDict(extra="forbid")

    body: Body
    change_summary: ChangeSummary
    provider_config_id: str | None = None
    upstream_model: str | None = Field(default=None, max_length=200)
    parameters: dict[str, Any] = {}
    fallback_answer: str | None = Field(default=None, max_length=MAX_BODY_CHARACTERS)
    original_body: Body | None = None
    original_format: Literal["xml", "txt", "markdown", "json", "yaml"] = "xml"
    original_filename: str | None = Field(default=None, min_length=1, max_length=255)
    conversion_model: str | None = Field(default=None, min_length=1, max_length=200)
    conversion_schema_version: str | None = Field(default=None, min_length=1, max_length=50)

    @field_validator("body")
    @classmethod
    def _body_is_canonical_xml(cls, value: str) -> str:
        validate_canonical_xml(value)
        return value

    @field_validator("original_filename")
    @classmethod
    def _filename_is_a_basename(cls, value: str | None) -> str | None:
        if value is not None and ("/" in value or "\\" in value):
            raise ValueError("original_filename must be a basename")
        return value

    @model_validator(mode="after")
    def _binding_is_whole(self) -> "RevisionCreate":
        """Both halves of the binding or neither, mirroring ``ck_revision_binding_is_whole``.

        An upstream model with no provider configuration resolves to whichever
        provider the next piece of code happens to pick, which is exactly the
        implicit default that makes a released revision untraceable. The database
        refuses it either way; this is what turns that refusal into a ``422``
        naming the two fields instead of a ``500`` naming a constraint.
        """
        if (self.provider_config_id is None) != (self.upstream_model is None):
            raise ValueError(
                "provider_config_id and upstream_model must be given together or not at all"
            )
        converted = self.original_format != "xml"
        if converted and self.original_body is None:
            raise ValueError("converted revisions require original_body")
        if converted != (self.conversion_model is not None):
            raise ValueError("converted revisions require conversion_model")
        if converted != (self.conversion_schema_version is not None):
            raise ValueError("converted revisions require conversion_schema_version")
        if not converted and self.original_body is not None and self.original_body != self.body:
            raise ValueError("direct XML original_body must equal body")
        return self


class PromptRead(BaseModel):
    """One prompt property as every read endpoint renders it.

    ``status`` is the STORED literal and is translated only at the point of
    display (ADR-0053 rule 9). ``released_version_id`` being non-null is what
    *In use* is derived from — there is no field carrying that word, because
    A-065 makes it derived and never stored.
    """

    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    model_name: str
    namespace: str
    name: str
    title: str
    purpose: str
    owner_id: str
    access_level: str
    status: PromptStatus
    tags: list[str]
    released_version_id: str | None = None
    released_at: AwareDatetime | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class RevisionSummaryRead(BaseModel):
    """A revision on the chain screen: everything but the body.

    The body is deliberately absent from the LIST shape. A revision list is a
    navigation surface, and twenty 32 KiB bodies in one page is 640 KiB of the
    most sensitive text in the product sent to render a column of dates.
    """

    model_config = ConfigDict(extra="forbid")

    version_id: str
    prompt_id: str
    revision_number: int
    change_summary: str
    author_id: str
    status: RevisionStatus
    provider_config_id: str | None = None
    upstream_model: str | None = None
    created_at: AwareDatetime


class RevisionRead(RevisionSummaryRead):
    """One revision in full — the detail shape, and the only one carrying the body."""

    body: str
    parameters: dict[str, Any]
    fallback_answer: str | None = None
    original_body: str
    original_format: str
    original_filename: str | None = None
    conversion_model: str | None = None
    conversion_schema_version: str | None = None


class LineChangeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: LineOp
    text: str
    from_line: int | None = None
    to_line: int | None = None


class FieldChangeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    before: str | None = None
    after: str | None = None
    changed: bool


class DiffRead(BaseModel):
    """A-015 and A-047: both halves together, computed on demand, never stored.

    The two are one response rather than two endpoints because the review screen
    shows both, and a client that could fetch one without the other would
    eventually ship a screen showing a body change with no note that the model
    underneath it changed too.
    """

    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    from_version_id: str
    to_version_id: str
    lines: list[LineChangeRead]
    fields: list[FieldChangeRead]


class ActivityEntryRead(BaseModel):
    """One property-history event, as ``GET /prompts/{id}/activity`` renders it.

    Written by **four modules against six target types** and read here as one
    indexed pass over ``(workspace_id, scope_prompt_id, seq DESC)``. This module
    checks permission and property-history checks none, which is the whole of
    A-044's cycle break.

    ``seq`` is the ordering fact and ``occurred_at`` is the displayed one.
    Approve-and-release writes two events with the same timestamp (A-125), so a
    client that sorted on ``occurred_at`` would show them in either order; the
    list arrives sorted and ``seq`` is present so a client can prove it.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str
    seq: int
    action: str
    target_type: str
    target_id: str
    actor_type: str
    actor_id: str | None = None
    reason: str | None = None
    details: dict[str, Any]
    occurred_at: AwareDatetime


class CallRecordRead(BaseModel):
    """One call's metadata, as ``GET /prompts/{id}/call-records`` renders it.

    **Metadata, and not one column of ``ledger.call_body``.** ADR-0018 forbids a
    read path for *bodies* — request and response text — and says of everything
    else: *"Metadata is unaffected. It is kept indefinitely, it has readers, and
    it is the audit trail NFR-02 requires."* This model is the wire form of one of
    those readers, and ``tests/security/test_no_body_read_path.py`` asserts the
    distinction against this file rather than trusting this paragraph.

    **The permission is ``prompt.read`` and the refusal shape is not-found.** The
    route loads the prompt and authorises it through ``_visible_prompt`` before it
    reads a single record, which is what keeps a private prompt's traffic as
    invisible as the prompt itself (BR-01). A workspace-wide version of this
    endpoint could not do that, and that is why there is not one.

    ``cost`` is a string on the wire, as every money value in Prope is: it is
    ``Numeric(20, 10)`` in the database and a JSON number would round it through a
    double on the way to a client (A-107). ``cost_status`` says whether to believe
    it — ``unpriced`` means no price row covered this call yet, and a client that
    summed those as zero would under-report.
    """

    model_config = ConfigDict(extra="forbid")

    call_id: str
    source: str
    version_id: str | None = None
    revision_number: int | None = None
    #: Which integration called, never who. A key, not a person — see
    #: ``call_ledger.seams.LIST_PROMPT_CALL_RECORDS`` for why ``actor_id`` is
    #: absent from the read entirely.
    consumer_key_id: str | None = None
    provider_config_id: str | None = None
    upstream_model: str | None = None
    outcome: str
    pinned: bool
    fallback: bool
    streaming: bool
    input_tokens: int | None = None
    output_tokens: int | None = None
    usage_status: str
    cost: Decimal | None = None
    currency: str | None = None
    cost_status: str
    added_latency_ms: int | None = None
    upstream_duration_ms: int | None = None
    error_class: str | None = None
    created_at: AwareDatetime
