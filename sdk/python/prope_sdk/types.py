"""What comes back. Frozen, slotted, and carrying the identity of what served it.

**There is no prompt body on any of these types and there never will be**
(ADR-0065). If you are looking for the text, it is in the web application, read
by a person holding ``prompt.read`` — not by a process holding a consumer key.

Every field here comes off the response Prope already sends (A-079). Nothing is
computed locally, so nothing can drift from what the gateway recorded.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Answer", "Chunk", "Usage"]


@dataclass(frozen=True, slots=True)
class Usage:
    """Token counts, when the provider reported them.

    All three are ``None`` rather than ``0`` when absent: a provider that did not
    report usage and one that reported zero are different facts, and a caller
    summing costs needs to tell them apart.
    """

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class Answer:
    """One completed call, and the identity of the revision that produced it.

    ``version_id`` and ``revision`` are the traceability half of Prope's core
    value made available to the caller: the application can log which revision
    answered without ever having seen the revision.
    """

    text: str
    #: The Prope model name the caller asked for — `namespace/name`, not the
    #: provider's model. A-079: clients compare this field, so the gateway
    #: echoes what was requested rather than what was dispatched.
    model: str
    call_id: str
    version_id: str | None = None
    revision: int | None = None
    #: The provider's model, for cost attribution. Visible, never substituted.
    upstream_model: str | None = None
    pinned: bool = False
    #: True when the released revision could not be served and the revision's
    #: declared fallback answer was returned instead.
    fallback: bool = False
    usage: Usage = field(default_factory=Usage)
    #: The conversation this call belongs to, when one was threaded.
    conversation_id: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class Chunk:
    """One streamed delta.

    ``text`` is the incremental content and is ``""`` on the frames that carry
    only identity or usage — a caller can concatenate every chunk's ``text``
    without filtering.
    """

    text: str
    call_id: str | None = None
    version_id: str | None = None
    usage: Usage | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


#: A caller message. `role` is `user`, `assistant` or `tool` — never `system`.
Message = Mapping[str, Any]
Messages = Sequence[Message]
