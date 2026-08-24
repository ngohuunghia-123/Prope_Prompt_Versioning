"""Request and response models for the chat API.

**Two naming decisions are load-bearing and neither is style.**

`MessageRead.text` rather than `body`. `tests/architecture/test_route_table.py`
refuses any schema property named `body`, `payload`, `raw_body` or `byte_size`
across the whole assembled OpenAPI document — ADR-0018's rule that the call-body
store has no read path, asserted over the spec rather than over the source, so a
model reaching the API through a route nobody remembered to read still fails.
Two fields in prompt-registry carry a written exemption. This module asks for
none: a chat turn's content is a `text`, and the word `body` is spoken for.

`TurnRead.code` rather than a message. ADR-0053 makes the interface Vietnamese
behind a keyed catalogue with **no literal display strings**, so every refusal,
every degradation and every failure here is a machine code the client translates.
The one string that is genuinely generated — the assistant's own reply — is prose
by nature and is the sole exception, which is why it has a field of its own.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from prope.canonical_prompt import MAX_CANONICAL_CHARACTERS
from prope.chat_orchestrator.domain import MAX_MESSAGE_CHARACTERS

__all__ = [
    "ActionDecisionCreate",
    "ActionDecisionRead",
    "ChatMessageCreate",
    "CitationRead",
    "ConversationListRead",
    "ConversationRead",
    "ConversationTranscriptRead",
    "FeedbackCreate",
    "FeedbackRead",
    "MessageRead",
    "PendingActionRead",
    "PipelineEdgeRead",
    "PipelineNodeRead",
    "PipelineRead",
    "TraceEntryRead",
    "TurnRead",
    "UiDirectiveRead",
]


class ChatMessageCreate(BaseModel):
    """``POST /api/v1/chat/messages``.

    `attachment` is separate from `text` and that separation is the whole point:
    a pasted prompt is *data the person is asking about*, and keeping it out of
    the message field means the guardrail layer inspects a question rather than a
    4 KB prompt full of the word "ignore". It is held to
    `MAX_CANONICAL_CHARACTERS` — the same 32 KiB ceiling a revision body and a
    conversion source are held to — because anything the registry would accept
    should be discussable here.

    `conversation_id` absent opens a new thread. A client that has lost its
    thread id gets a new conversation rather than an error, which is the right
    failure for a chat panel that was reloaded.
    """

    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = Field(default=None, max_length=64)
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARACTERS)
    attachment: str | None = Field(default=None, max_length=MAX_CANONICAL_CHARACTERS)
    # The four formats prompt-conversion accepts, plus the `md` spelling it
    # already aliases. **`xml` is deliberately absent**: this module's import
    # flow always converts, and `registry.revision`'s provenance constraint
    # pairs an `xml` original with a NULL conversion model — so an `xml`
    # attachment that went through the agent would be a row the database
    # refuses, discovered after somebody confirmed the write.
    attachment_format: Literal["txt", "md", "markdown", "json", "yaml"] = "txt"


class TraceEntryRead(BaseModel):
    """One line of the decision path. See `domain.TraceEntry` for what is absent."""

    agent: str
    action: str
    status: str
    latency_ms: int
    detail: dict[str, Any] = Field(default_factory=dict)


class CitationRead(BaseModel):
    """Where one claim came from: a documentation chunk or a stored prompt."""

    kind: str
    reference: str
    label: str
    score: float | None = None
    index: int = 0
    mentions: list[int] = Field(default_factory=list)
    excerpt: str = ""
    document: str | None = None
    href: str | None = None


class UiDirectiveRead(BaseModel):
    """One validated instruction to the client.

    `arguments` is an open dict on the wire and a closed vocabulary in fact: it
    has already been through `guardrails.sanitise_directives`, which drops any
    key the kind does not admit. Typed as a dict because seven kinds with seven
    argument shapes would be a discriminated union in the OpenAPI document that
    buys the client nothing it does not already have to switch on.
    """

    kind: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class PendingActionRead(BaseModel):
    """A write the assistant proposed and has not made.

    `preview` is what the confirmation card renders and it is deliberately not
    the raw arguments: the arguments carry the whole converted prompt, and a
    confirmation card that renders 8 KB of XML is a card nobody reads — which is
    the rubber-stamp failure deck 5 names. The full text is one click away in the
    editor the directives already opened.
    """

    id: str
    tool: str
    summary: str
    preview: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None


class TurnRead(BaseModel):
    """``POST /api/v1/chat/messages`` — one turn's answer.

    `reply` and `code` are alternatives. A generated answer fills `reply` and
    leaves `code` null; a refusal fills `code` and leaves `reply` empty. A client
    that renders `reply || t(code)` is correct for both.
    """

    conversation_id: str
    message_id: str
    intent: str
    reply: str = ""
    code: str | None = None
    outcome: str
    degraded: list[str] = Field(default_factory=list)
    trace: list[TraceEntryRead] = Field(default_factory=list)
    citations: list[CitationRead] = Field(default_factory=list)
    directives: list[UiDirectiveRead] = Field(default_factory=list)
    pending: PendingActionRead | None = None
    run_id: str | None = None


class ActionDecisionCreate(BaseModel):
    """``POST /api/v1/chat/actions/{action_id}`` — the person's decision.

    A required boolean with no default. A default would mean a malformed client
    request performs a write, and this is the one route in the module where that
    matters.

    `edits` is the person's correction to an editable proposal's identity —
    a renamed import on its confirmation card. Whitelisted per tool at the
    settle, persisted with the row *before* execution, so what a person
    approved and what runs still cannot differ.
    """

    model_config = ConfigDict(extra="forbid")

    approve: bool
    edits: dict[str, str] | None = None


class ActionDecisionRead(BaseModel):
    """What the decision produced.

    `secret_once` is the one channel a minted key's plaintext may travel. It is
    filled only by `create_api_key`, it appears exactly once, and it never passes
    through the model's reply — the output rails redact credential-shaped text,
    so a reply-borne secret would be unrecoverable `[đã ẩn]`.

    `continuation` is the automatic turn that runs after the settle commits: the
    agent picking the remaining task back up (an eval run proposed on a freshly
    approved revision) or acknowledging a rejection. `None` when the decision
    closed the task or the continuation could not run — the settlement itself
    never fails because its follow-up did.
    """

    id: str
    status: str
    code: str | None = None
    prompt_id: str | None = None
    version_id: str | None = None
    secret_once: str | None = None
    directives: list[UiDirectiveRead] = Field(default_factory=list)
    continuation: TurnRead | None = None


class FeedbackCreate(BaseModel):
    """Granular feedback on one assistant message, replaceable by the actor."""

    model_config = ConfigDict(extra="forbid")

    rating: Literal["helpful", "not_helpful"]
    reason: Literal["incorrect", "unsupported_source", "misunderstood", "other"] | None = None


class FeedbackRead(BaseModel):
    message_id: str
    rating: str
    reason: str | None = None


class ConversationRead(BaseModel):
    """One thread in the history list.

    `title_code` rather than a title: a thread title taken from the first message
    is prompt content rendered in a sidebar, and the client renders the routed
    intent instead — `chat.thread.search`, `chat.thread.import_prompt`.
    """

    id: str
    title_code: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationListRead(BaseModel):
    """``GET /api/v1/chat/conversations``."""

    conversations: list[ConversationRead] = Field(default_factory=list)


class MessageRead(BaseModel):
    """One stored turn. `text`, never `body` — see the module docstring."""

    id: str
    role: str
    text: str
    intent: str | None = None
    created_at: datetime
    trace: list[TraceEntryRead] = Field(default_factory=list)
    citations: list[CitationRead] = Field(default_factory=list)
    directives: list[UiDirectiveRead] = Field(default_factory=list)
    run_id: str | None = None


class ConversationTranscriptRead(BaseModel):
    """``GET /api/v1/chat/conversations/{conversation_id}``."""

    conversation: ConversationRead
    messages: list[MessageRead] = Field(default_factory=list)
    pending: PendingActionRead | None = None


class PipelineNodeRead(BaseModel):
    """One node of the pipeline the assistant *could* walk.

    **`agent` and `action` are the join to a trace, and they are separate from
    `id` on purpose.** A `TraceEntry` says who ran, not which box to light up, and
    the two are not one-to-one: `supervisor` appears twice in a turn — once to
    route and once to answer — so `agent` alone is ambiguous for exactly one
    node kind. `action` disambiguates it and is null everywhere it would be
    noise. A client matches an entry to a node by `agent`, then by `action` when
    the node names one.

    `label_code` and never a label. ADR-0053: the API returns a key, the client
    owns the Vietnamese.

    `stage` is an ordinal, not a coordinate. It says this node is the third of
    five things that happen, which is a fact about the pipeline; how far along
    the x-axis that lands is the client's business. Nodes sharing a stage are
    alternatives at the same point in time — the six workers — and the client
    stacks them.
    """

    id: str
    agent: str
    action: str | None = None
    kind: Literal["guardrail", "supervisor", "worker"]
    label_code: str
    stage: int
    #: True for the two workers that end a plan by proposing a write. The client
    #: marks them, because "the assistant stopped here to ask you" is a different
    #: shape of turn from one that ran out of steps.
    writes: bool = False


class PipelineEdgeRead(BaseModel):
    """One directed step between nodes. `source`/`target`, never `from`/`to`."""

    source: str
    target: str


class PipelineRead(BaseModel):
    """``GET /api/v1/chat/pipeline`` — the shape, not any turn's path.

    Derived from `domain.TOOLS` at request time and identical for every actor in
    every workspace, which is what makes it cacheable by the client for the whole
    session. It exists so the graph can draw the nodes a turn did **not** visit:
    a picture of only what ran cannot answer "why didn't it search?", which is the
    question the flat trace list already failed to answer.

    A seventh tool added to `domain.TOOLS` appears here, and therefore in the
    graph, with no change to this module and none to the client.
    """

    nodes: list[PipelineNodeRead] = Field(default_factory=list)
    edges: list[PipelineEdgeRead] = Field(default_factory=list)
