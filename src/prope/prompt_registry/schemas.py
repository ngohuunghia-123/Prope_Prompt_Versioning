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

from datetime import timedelta
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
    MAX_FOLDER_DESCRIPTION_CHARACTERS,
    MAX_FOLDER_NAME_CHARACTERS,
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
    "ConversationGraphRead",
    "ConversationNodeRead",
    "ConversationSummaryRead",
    "DiffRead",
    "FieldChangeRead",
    "FolderCreate",
    "FolderRead",
    "FolderUpdate",
    "LineChangeRead",
    "PromptCreate",
    "PromptRead",
    "PromptUpdate",
    "PromptUsageRead",
    "RevisionCreate",
    "RevisionRead",
    "RevisionSummaryRead",
    "TrialMessage",
    "TrialParameters",
    "TrialRequest",
    "UsageBucketRead",
    "UsageCostRead",
    "UsageWindow",
]

#: A trial turn is something a person typed into a chat box. The ceiling is well
#: under ``compose``'s 256 KiB budget for the whole composed set, so a thread that
#: is going to be refused as oversize is refused per-message at the edge — naming
#: the turn — rather than after the body has been rendered onto the front of it.
MAX_TRIAL_CONTENT_CHARACTERS = 16_384

#: Enough for a real multi-turn test and far short of a way to make one HTTP
#: request cost a fortune. The composed-size limit is the real bound; this one
#: exists so the refusal arrives before the provider does.
MAX_TRIAL_MESSAGES = 60

#: The ceiling on a trial's ``max_tokens``. A revision may bind a larger figure
#: and that binding is honoured — this bounds only what somebody may type into
#: the playground's own control, which is the one path where the number is set by
#: a person watching a screen rather than by a reviewed revision.
MAX_TRIAL_OUTPUT_TOKENS = 8_192

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


#: ``ck_folder_color_shape``, at the edge. Lower case only — see ``COLOR_PATTERN``.
COLOR_PATTERN = r"^#[0-9a-f]{6}$"

Color = Annotated[str, Field(pattern=COLOR_PATTERN)]

FolderName = Annotated[str, Field(min_length=1, max_length=MAX_FOLDER_NAME_CHARACTERS)]

FolderDescription = Annotated[str, Field(max_length=MAX_FOLDER_DESCRIPTION_CHARACTERS)]


class FolderCreate(BaseModel):
    """``POST /api/v1/folders``.

    ``slug`` is required and carries A-021's namespace shape, because it is the
    first half of the model name a consuming product will call. The client
    pre-fills it by folding the Vietnamese ``name`` down to ASCII, but the fold is
    a *suggestion* the author may overwrite — which is why the field is on the
    wire rather than derived here from ``name``.
    """

    model_config = ConfigDict(extra="forbid")

    slug: Namespace
    name: FolderName
    description: FolderDescription = ""
    color: Color | None = None
    auto_name: bool = False


class FolderUpdate(BaseModel):
    """``PATCH /api/v1/folders/{slug}``, and the route that **declares** a folder.

    Patching a slug with no row inserts one, which is how an observed namespace —
    a folder derived from prompts somebody created through the API — acquires a
    Vietnamese name, a description and a colour. ``POST`` refuses that slug
    precisely because the folder already exists to the person looking at the grid;
    this is the verb that names it.

    ``slug`` is absent for A-021's reason, the same one ``PromptUpdate`` gives:
    it is the first half of the model name, renaming it breaks every caller, and
    there is deliberately no field here that could.
    """

    model_config = ConfigDict(extra="forbid")

    name: FolderName | None = None
    description: FolderDescription | None = None
    color: Color | None = None


class FolderRead(BaseModel):
    """One row of the folder list: declared rows and observed namespaces alike.

    ``declared`` is what tells them apart, and the client needs it — an observed
    folder's ``name`` is a capitalised slug and its ``description`` is the
    ``slug/*`` pattern, neither of which anybody chose.

    The counts are over the prompts the caller can see (INT-002), never over the
    namespace's true contents.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    description: str
    color: str
    declared: bool
    prompt_count: int
    approved_count: int
    in_review_count: int
    draft_count: int
    updated_at: AwareDatetime


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
    auto_name: bool = False


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
    tags: Tags = Field(default_factory=list)
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


class RevisionTagsUpdate(BaseModel):
    """Mutable presentation labels for one immutable revision body."""

    model_config = ConfigDict(extra="forbid")

    tags: Tags = Field(default_factory=list)


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
    tags: Tags = Field(default_factory=list)
    author_id: str
    author_email: str | None = None
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


class TrialMessage(BaseModel):
    """One turn of a playground conversation. **`system` is not a role a caller may send.**

    The revision body IS the system message (ADR-0011) and the composer refuses a
    second one, so the vocabulary here is narrowed to the two roles a person can
    legitimately have produced. A `Literal` rather than a runtime check because
    the refusal should be a `422` naming `role` rather than a 400 discovered
    three functions later — and because the field then documents itself in the
    schema the SPA is written against.
    """

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=MAX_TRIAL_CONTENT_CHARACTERS)]


class TrialParameters(BaseModel):
    """The sampling knobs a trial may turn. **A closed set, not a passthrough.**

    ``provider_access.upstream.compose_request`` forwards a revision's
    ``parameters`` verbatim (A-097), which is right for a figure a reviewer
    approved and wrong for one typed into a chat sidebar: an open dict here would
    let the screen set ``n``, ``logit_bias``, or any vendor extension straight
    onto a workspace's own credential. So the playground's controls are enumerated
    — five fields, each bounded — and anything else is a ``422`` naming the field.

    Every field is optional and ``None`` means *leave the revision's value
    alone*. That is why the merge in the route uses ``exclude_none``: clearing a
    control has to mean "as the revision has it", because a trial that silently
    replaced an approved ``max_tokens`` with a default would be testing something
    other than the revision.
    """

    model_config = ConfigDict(extra="forbid")

    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    max_tokens: int | None = Field(default=None, ge=1, le=MAX_TRIAL_OUTPUT_TOKENS)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)


class TrialRequest(BaseModel):
    """`POST /api/v1/prompts/{prompt_id}/revisions/{version_id}/trials`.

    **The whole thread, every turn, not just the newest one.** The trial endpoint
    holds no conversation state — there is no server-side thread to append to,
    and inventing one would mean a second store with its own retention question
    for scratch work somebody is about to throw away. So the client sends what it
    is showing, which also makes "edit an earlier turn and re-run" cost nothing.

    `variables` fills ADR-0011's `{{placeholders}}`. It mirrors the gateway's
    top-level `prope.variables` object exactly, because the point of the trial is
    to find out what the gateway will do.

    **`provider_config_id`, `upstream_model` and `parameters` override the
    revision for this one turn and change nothing.** Answering *would this prompt
    be better on the cheaper model* is the reason the playground exists, and the
    alternative — edit the revision, try it, edit it back — puts two throwaway
    rows on an immutable chain to ask a question. Nothing here writes: the
    revision keeps its binding, and the ledger records the model that actually
    ran, which is what makes the spend attributable afterwards.
    """

    model_config = ConfigDict(extra="forbid")

    messages: Annotated[
        list[TrialMessage], Field(min_length=1, max_length=MAX_TRIAL_MESSAGES)
    ]
    variables: dict[str, str] = Field(default_factory=dict)
    provider_config_id: str | None = None
    upstream_model: str | None = None
    parameters: TrialParameters | None = None

    @model_validator(mode="after")
    def _binding_is_whole(self) -> "TrialRequest":
        """Both halves of an override, or neither. The same rule `RevisionCreate` holds.

        A model name without a configuration would be dispatched against the
        revision's provider, which is a request nobody made: "gpt-5.2 on whichever
        vendor happened to be bound" is not a test of anything.
        """
        if (self.provider_config_id is None) != (self.upstream_model is None):
            raise ValueError(
                "provider_config_id and upstream_model are supplied together or not at all"
            )
        return self


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
    #: That key's display name, resolved on the same terms as the Production
    #: tab's — name only, only for keys that called a prompt the caller may read,
    #: and argued at ``access_control.labels``.
    #:
    #: **Here rather than left to the client**, because the alternative is a
    #: screen that either shows raw ids or makes a second request to a
    #: `workspace.manage_keys` endpoint a Prompt Owner cannot call. Null for the
    #: internal caller and for a key whose row has gone; the client tells those
    #: apart by whether ``consumer_key_id`` is null.
    consumer_label: str | None = None
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


class ObservabilityMessageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    redacted: bool = False


class ObservabilityRequestRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "disabled", "forbidden", "expired"]
    messages: list[ObservabilityMessageRead] = Field(default_factory=list)


class ObservabilitySpanRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: Literal["span", "generation", "event"]
    status: Literal["success", "error"]
    duration_ms: int | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: Decimal | None = None
    currency: str | None = None


class CallObservabilityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    status: Literal["success", "error"]
    duration_ms: int | None = None
    request: ObservabilityRequestRead
    spans: list[ObservabilitySpanRead]


#: The windows the Production tab offers, as a closed set.
#:
#: Not a free-form ``since`` timestamp: an arbitrary lower bound is an arbitrary
#: index range, and the three values here are the ones the screen has controls
#: for. A closed set also keeps the answer cacheable per window, and keeps a
#: client from asking for a five-year scan by editing a query string.
UsageWindow = Literal["24h", "7d", "30d"]

#: How long each window reaches back. Whole hours and whole days, resolved
#: against the moment of the request rather than against a calendar boundary —
#: "the last 24 hours" is what somebody watching a rollout means.
USAGE_WINDOW_SPANS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


class UsageCostRead(BaseModel):
    """One currency's worth of spend inside one bucket.

    **A list of these rather than an amount and a currency**, because a prompt
    served by a USD provider and a VND provider over the same month has two
    totals and no sum. A-107 forbids conversion and Prope holds no exchange rate,
    so the wire shape has to be able to say both — a single nullable pair would
    force whoever assembled it to drop one.
    """

    model_config = ConfigDict(extra="forbid")

    currency: str
    #: A string on the wire like every money value in Prope: ``Numeric(20, 10)``
    #: in the database, and a JSON number would round it through a double (A-107).
    amount: Decimal


class UsageBucketRead(BaseModel):
    """What one calling integration did to one prompt inside the window.

    **``label`` is a key's name and never a person's.** The ledger records which
    *key* called, not who held it, and that is the question the tab asks. Reading
    the name is a deliberate widening of ``workspace.manage_keys`` bounded at
    ``access_control.labels`` — name only, and only for keys that actually called
    a prompt the caller may already read.

    ``consumer_key_id is None`` is the internal caller — today, a playground
    trial, which authenticates with a session and may not carry a key at all
    (``ck_call_record_playground_calls_are_internal``). It arrives as a bucket
    like any other rather than being filtered out, because a cost total that
    dropped it would not reconcile with what the workspace actually spent. The
    client labels it; the server sends no display string (ADR-0053).

    **Eval dispatches are absent from every bucket**, because their ledger rows
    carry no ``prompt_id`` to match on — see ``call_ledger.seams.UsageBucket``.
    The Eval tab reports that spend from the run's own priced totals instead.

    ``label`` is also null for a key whose row has gone. The client falls back to
    the id rather than inventing a name.

    **No ``share`` field.** The percentage is ``requests / total_requests`` and
    the client has both; sending a third number that must agree with the other
    two is a rounding disagreement waiting to be reported as a bug.
    """

    model_config = ConfigDict(extra="forbid")

    consumer_key_id: str | None = None
    label: str | None = None
    requests: int
    input_tokens: int
    output_tokens: int
    cost: list[UsageCostRead]
    #: How many of ``requests`` no price row covered. A client that rendered the
    #: cost column without this would be under-reporting and unable to say so.
    unpriced_count: int
    #: ``caller_error`` + ``upstream_error``. ``truncated`` is excluded on
    #: purpose — the provider generated tokens and charged for them, so it is a
    #: cost event, and telling it apart from a failure is what decides whether
    #: you edit the prompt or raise ``max_tokens``.
    error_count: int
    fallback_count: int
    last_called_at: AwareDatetime | None = None


class PromptUsageRead(BaseModel):
    """One prompt's traffic for one window, split by calling integration.

    The companion to ``CallRecordRead``: the same rows, counted instead of
    listed. Both are ``prompt.read``, both are metadata only, and neither can
    reach ``ledger.call_body``.

    ``since`` is echoed so the client can label the axis with the bound the
    server actually used, rather than recomputing it from its own clock and
    disagreeing by the request's latency.
    """

    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    window: UsageWindow
    since: AwareDatetime
    #: The ``source`` filter in force, or null for every source. Echoed for the
    #: same reason ``since`` is: the tab defaults to ``gateway`` and the totals
    #: mean something different when it does not.
    source: str | None = None
    total_requests: int
    buckets: list[UsageBucketRead]


#: The character class a caller-supplied `conversation_id` may be drawn from,
#: restated from `gateway.schemas.CONVERSATION_ID_PATTERN` rather than imported:
#: prompt-registry has no edge to gateway, and the two are asserted equal by
#: `tests/unit/test_conversation_correlation.py` so the restatement cannot drift.
#:
#: Declared on the path parameter as well as at ingest, so a malformed id meets a
#: 422 naming the field instead of reaching a query as a value that can only
#: return nothing.
CONVERSATION_ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class ConversationSummaryRead(BaseModel):
    """One conversation this prompt took part in, as the list renders it.

    **No cost.** A conversation can legitimately span a provider change and
    therefore two currencies, and A-107 forbids conversion — one total across two
    of them is a number with no unit. The per-call detail carries each call's own
    currency, which is the only honest place to put it.

    ``prompt_count`` counts the *distinct prompts the conversation touched*, not
    the ones this reader may see. It is deliberately the unfiltered number: it is
    what makes a chain that fragments under the visibility rule legible rather
    than mysterious, and it discloses nothing — a count is not an identity, and
    the client renders it as "5 steps" without naming any of them.
    """

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    started_at: AwareDatetime
    last_called_at: AwareDatetime
    call_count: int
    prompt_count: int
    error_count: int
    fallback_count: int


class ConversationNodeRead(BaseModel):
    """One call in a chain: what ran, which revision, and how it went.

    ``CallRecordRead`` plus the two fields a graph needs and a flat list does not
    — the prompt this call resolved to, and the call it followed from — and minus
    nothing. **Still not one column of ``ledger.call_body``** (ADR-0018); the
    shape of a chain is metadata, and metadata is what this feature draws.

    ``prompt_id`` and ``prompt_title`` are null together, and only for a node
    whose prompt this reader may not see — which cannot happen, because such a
    node is dropped before it reaches the wire. They are nullable because the
    *column* is: a call refused before it bound a revision names no prompt.
    """

    model_config = ConfigDict(extra="forbid")

    call_id: str
    #: The call this one followed from, or null for a root. **Null also when the
    #: parent was dropped by the visibility rule or has aged out of retention** —
    #: the client cannot tell those apart, and must not: a distinguishable
    #: "your parent was hidden" is the existence disclosure BR-01 closes.
    parent_call_id: str | None = None
    prompt_id: str | None = None
    #: Resolved from the registry row this route already loaded to authorise the
    #: node. A title rather than a `label_code`: ADR-0053 keeps *Prope's* strings
    #: out of the API, and this is the customer's own name for their own prompt.
    prompt_title: str | None = None
    source: str
    version_id: str | None = None
    revision_number: int | None = None
    consumer_key_id: str | None = None
    consumer_label: str | None = None
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


class ConversationGraphRead(BaseModel):
    """One conversation, as a graph the client can lay out without guessing.

    **Nodes carry their own parent; there is no separate edge list.** A parent is
    a property of a call — the caller declared it on the request — and modelling
    it twice would let the two disagree. The client builds edges by matching
    `parent_call_id` against the `call_id`s present, and a parent that is absent
    from that set simply makes its child a root.

    **``hidden_count`` says how many nodes the visibility rule removed, and it
    is the one number here that had to be argued.** Reporting it means telling a
    reader *something ran that you cannot see*, which is a hair's breadth from the
    existence disclosure BR-01 closes. It is included because it is a count and
    not an identity: it names no prompt, no owner, no title and no revision, and
    it cannot be turned into any of those by asking again. What it buys is the
    difference between a fragmented graph and a *broken* one — without it, a
    reader seeing two disconnected chains has no way to know whether their app
    misbehaved or their permissions did, and the first of those is a bug they
    would go hunting for.
    """

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    nodes: list[ConversationNodeRead] = Field(default_factory=list)
    #: How many calls were dropped because the reader may not see their prompt.
    #: Zero for the ordinary case.
    hidden_count: int = 0
    #: True when the conversation has more calls than one graph will draw. The
    #: nodes present are the *oldest*, so a truncated graph shows the beginning of
    #: a chain rather than an arbitrary slice of its middle.
    truncated: bool = False
