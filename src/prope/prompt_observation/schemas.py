"""The wire shapes INT-035 returns. Pydantic only — no SQL, no permission logic.

**The list row carries an EXCERPT and the detail carries the body.** That is a
product decision with a security edge: the inbox is the screen somebody leaves
open on a shared display, and a full production system prompt rendered fifty to a
page is the kind of disclosure nobody chose. Both are behind the same
``prompt.read`` check, so the split narrows blast radius rather than authority.

**No schema here has a `fingerprint` field.** It is an internal grouping key, it
identifies nothing a person can act on, and putting it on the wire would invite a
client to treat it as stable across a change to A-154's normalisation rule — which
is the one rule this module expects to change.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "EXCERPT_LENGTH",
    "AdoptionProposalRead",
    "ObservationAdopt",
    "ObservationDetailRead",
    "ObservationDismiss",
    "ObservationRead",
    "SightingRead",
]

#: How much of a body the inbox shows. Long enough to recognise a prompt at a
#: glance — the opening sentence of a system message is almost always the role
#: statement — and short enough that fifty of them are a list rather than a wall.
EXCERPT_LENGTH = 200


class ObservationRead(BaseModel):
    """One inbox row."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str
    namespace: str
    #: The first :data:`EXCERPT_LENGTH` characters of the current body. Empty for
    #: a redacted group, which is the whole visible difference redaction makes.
    body_excerpt: str
    inferred_variables: list[str]
    sighting_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    upstream_models: list[str]
    #: Derived from the two timestamps below rather than stored — see
    #: :class:`~prope.prompt_observation.domain.ObservationStatus`.
    status: str
    redacted: bool
    adopted_prompt_id: str | None = None
    adopted_by: str | None = None
    adopted_at: datetime | None = None
    dismissed_by: str | None = None
    dismissed_at: datetime | None = None
    dismissal_reason: str | None = None


class SightingRead(BaseModel):
    """One occurrence. ``body`` is present only when this is where it changed."""

    model_config = ConfigDict(extra="forbid")

    sighting_id: str
    body: str | None
    call_id: str
    consumer_key_id: str
    upstream_model: str
    occurred_at: datetime


class ObservationDetailRead(ObservationRead):
    """One group opened: the full current body and the drift behind it."""

    current_body: str
    sightings: list[SightingRead]


class AdoptionProposalRead(BaseModel):
    """What the adopt screen offers. **Nothing has been written** (ADR-0060).

    ``namespace`` is absent from this shape entirely rather than present and
    null, because a null in a form field is a default somebody accepts by
    pressing enter. A-021 makes the model name immutable and ADR-0061 makes the
    namespace the access container, so the folder chosen here follows the prompt
    for the rest of its life — and A-049 makes retirement terminal, so there is
    not even a clean way back. The client asks (SR-6, AC-10).
    """

    model_config = ConfigDict(extra="forbid")

    observation_id: str
    body: str
    variables: list[str]
    suggested_name: str


class ObservationAdopt(BaseModel):
    """*prompt-registry created this; point the inventory at it.*"""

    model_config = ConfigDict(extra="forbid")

    prompt_id: str = Field(min_length=1, max_length=64)


class ObservationDismiss(BaseModel):
    """*Somebody looked and this is not worth governing.*"""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)
