"""The wire shapes this module accepts and returns. OpenAI's, plus the `prope` object."""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from prope.gateway.domain import CALL_ID_PREFIX, CHATCMPL_PREFIX, PIN_SEPARATOR

__all__ = [
    "CHATCMPL_PREFIX",
    "ChatCompletionRequest",
    "ChatMessage",
    "CONVERSATION_ID_MAX_LENGTH",
    "CONVERSATION_ID_PATTERN",
    "PropeRequestOptions",
]

#: The character class a caller-supplied correlation id may be drawn from, and
#: the same one `envelope.WORKSPACE_ID_PATTERN` uses — for an overlapping but not
#: identical reason. There, the value reaches `set_config('app.workspace_id', ...)`
#: and decides which tenant's rows a transaction may touch. Here it does not: it
#: lands in a text column and is compared against other text.
#:
#: What it does instead is become a **path segment** — `/prompts/{id}/conversations/
#: {conversation_id}` — and appear in an index. So the class is what keeps a
#: slash, a space, a control character or a multi-byte sequence out of a URL that
#: a person will paste into a support ticket, and out of a value somebody might
#: later be tempted to log. A-020 does not stop at the trace: this is customer
#: text, it is never emitted as a metric label (ADR-0030's cardinality bound
#: would be unbounded by construction), and it is never logged.
CONVERSATION_ID_PATTERN = r"^[A-Za-z0-9_-]+$"

#: Comfortably above a UUID with its hyphens (36) and a prefixed ULID (30), and
#: far below anything worth calling a payload. `ledger.call_record.call_id` is
#: itself bounded at 64 by the envelope, so this matches its neighbour.
CONVERSATION_ID_MAX_LENGTH = 64

#: Compiled once. `conversation_id` gets the class through pydantic's own
#: `pattern=`; `parent_call_id` cannot, because its validator has to strip a
#: prefix before the class applies, and a `pattern=` would have rejected the
#: prefixed form before the validator ever saw it.
_CONVERSATION_ID_RE = re.compile(CONVERSATION_ID_PATTERN)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())

    role: str
    content: Any = None


class PropeRequestOptions(BaseModel):
    """The caller's own additions to an otherwise OpenAI-shaped request.

    ``extra="forbid"``, which is what makes adding a field here a deliberate and
    visible act rather than an accident — and what makes a typo in a customer's
    integration a 422 they can see instead of a feature that silently never works.

    **The two correlation fields are optional and always will be.** A caller that
    has never heard of them keeps sending the body it always sent and gets the
    behaviour it always got; it simply has no conversation graph. Nothing in an
    OpenAI-compatible request identifies a conversation, and inferring one from
    the key and a time window would be a guess that is wrong the moment two
    end-users are served concurrently — which, for a deployed chatbot, is the
    normal case rather than the exotic one.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    variables: dict[str, Any] = Field(default_factory=dict)

    #: Which revision to serve, when the caller wants a specific one instead of
    #: whatever is released. A revision number (``1``) or a version id
    #: (``rev_01J...``) — the same two forms ``name@<pin>`` has always taken, and
    #: the same lookup, because `domain.pinned_at` folds this into the very same
    #: `ModelReference` before anything downstream can tell them apart.
    #:
    #: **Absent is the normal case and stays the normal case.** A caller that
    #: omits it is served the released revision and therefore follows every
    #: future release without a redeploy, which is the restore-without-redeploy
    #: the product is sold on. Sending this field is opting out of that, and
    #: `prope_gateway_pinned_call_total` counts it as such.
    #:
    #: Stored as text rather than as ``int``, because a version id is not a
    #: number and the registry compares the two against different columns. The
    #: validator below is what lets a caller write the number as a number.
    version: str | None = Field(default=None)

    #: The caller's own name for one end-user conversation. Prope never generates
    #: it, never validates that it is unique, and attaches no meaning to it beyond
    #: *these calls belong together*.
    conversation_id: str | None = Field(
        default=None, min_length=1, max_length=CONVERSATION_ID_MAX_LENGTH, pattern=CONVERSATION_ID_PATTERN
    )

    #: The `call_id` of the call this one follows from, or absent for a root.
    #: Optional even when `conversation_id` is present: threading parents is the
    #: richer integration, and a caller that sends only the conversation gets a
    #: flat chain ordered by time rather than nothing at all.
    parent_call_id: str | None = Field(
        default=None, min_length=1, max_length=CONVERSATION_ID_MAX_LENGTH
    )

    @field_validator("version", mode="before")
    @classmethod
    def _take_the_number_as_a_number(cls, value: Any) -> Any:
        """Accept ``2`` as readily as ``"2"``, then insist on something usable.

        JSON has a number type and a revision number is a number, so
        ``{"version": 2}`` is what an integrator writes on the first try. Refusing
        it over a missing pair of quotes would be a 422 about nothing.

        The refusals are all shape, never registry: an empty string, a wrong
        type, a value carrying the ``@`` that belongs to the other spelling. A
        well-formed version naming a revision that does not exist — or one that
        exists but is not Approved — is **not** refused here. It goes to the
        registry and comes back as the same byte-identical 404 that every other
        miss produces, because a validator that could tell a caller *that
        revision is not yours* would be an enumeration oracle (A-116).

        ``bool`` is excluded before ``int`` on purpose. It is an ``int`` subclass
        in Python, so ``{"version": true}`` would otherwise pin revision 1 —
        a silently-served wrong revision, which is the failure this whole field
        exists to prevent.
        """
        if value is None or isinstance(value, str):
            text = value.strip() if isinstance(value, str) else value
        elif isinstance(value, bool):
            raise ValueError("version must be a revision number or a version id, not a boolean")
        elif isinstance(value, int):
            text = str(value)
        else:
            raise ValueError("version must be a revision number or a version id")

        if text is None:
            return None
        if not text:
            raise ValueError("version is empty; omit it to be served the released revision")
        if PIN_SEPARATOR in text:
            raise ValueError(
                f"version carries a {PIN_SEPARATOR!r}; put the revision here on its own, or use "
                f"the model name's {PIN_SEPARATOR}<version> form, but not one inside the other"
            )
        return text

    @field_validator("parent_call_id", mode="after")
    @classmethod
    def _accept_the_id_we_actually_handed_back(cls, value: str | None) -> str | None:
        """Take `chatcmpl-cal_...` as readily as `cal_...`, then insist on the rest.

        The gateway answers with ``id: "chatcmpl-cal_01J..."`` because that is the
        shape OpenAI's clients expect. The obvious integration is therefore to
        copy that string into the next request's ``parent_call_id`` — and the
        obvious integration must work, because the failure mode is silent: an id
        that matches no row is not an error, it is a node with no parent, which
        renders as a second root. A graph that quietly draws two chains where
        there was one is worse than a 422 that names the problem.

        So the prefix is stripped, and what remains must look like a `call_id`
        this gateway issued. Strictness after the lenience is the point: it is
        what catches a caller who has put their *conversation* id in this field,
        which would otherwise also fail silently.
        """
        if value is None:
            return None
        stripped = value.removeprefix(CHATCMPL_PREFIX)
        if not stripped.startswith(CALL_ID_PREFIX):
            raise ValueError(
                f"parent_call_id must be a call id this gateway issued — {CALL_ID_PREFIX}... , "
                f"optionally still wearing the {CHATCMPL_PREFIX!r} prefix from the response it "
                "came from. An id that matches no call is indistinguishable from no parent at all, "
                "so it is refused here rather than drawn as a second root."
            )
        if not _CONVERSATION_ID_RE.match(stripped):
            raise ValueError("parent_call_id carries characters a call id cannot contain")
        return stripped


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    stream_options: dict[str, Any] | None = None
    prope: PropeRequestOptions | None = None

    def caller_messages(self) -> list[dict[str, Any]]:
        return [message.model_dump(exclude_none=True) for message in self.messages]

    def variables(self) -> dict[str, Any]:
        return dict(self.prope.variables) if self.prope is not None else {}

    def conversation_id(self) -> str | None:
        return None if self.prope is None else self.prope.conversation_id

    def version(self) -> str | None:
        """The pin the body asked for, or ``None`` for the released revision."""
        return None if self.prope is None else self.prope.version

    def parent_call_id(self) -> str | None:
        """The parent, and **only** when a conversation names it.

        A parent without a conversation is unanswerable: the graph is assembled by
        conversation, so a parent link with nothing to hang it in would be stored
        and never read. Dropping it here rather than storing it keeps
        `ck_call_record_parent_needs_a_conversation` — the database's version of
        this same rule — from ever having to refuse a live call.
        """
        if self.prope is None or self.prope.conversation_id is None:
            return None
        return self.prope.parent_call_id

    def wants_usage(self) -> bool:
        options = self.stream_options or {}
        return bool(options.get("include_usage"))
