"""The value objects this module is written in. No SQL, no FastAPI, no I/O.

Frozen and slotted throughout, like every value object in Prope. Here the reason
is the usual one plus a specific one: an :class:`ObservationDraft` a background
task could mutate is a body somebody could edit between the gateway reading it
and the repository writing it, and the whole claim of this module is that what it
shows you is what your product actually sent.

**Nothing here has an owner or an access level**, and that is not an oversight —
it is what ADR-0061 exists to answer. An observation's access container is its
:attr:`ObservationDraft.namespace`, written from the consumer key's
``observe_namespace``, and who may read it is one ``access.namespace_grant``
through the ordinary ``may()`` union. Before that decision this module had a
widening with no fix available inside it, recorded as SR-2.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

__all__ = [
    "AdoptionProposal",
    "ObservationDraft",
    "ObservationRow",
    "ObservationStatus",
    "SightingRow",
]


class ObservationStatus(StrEnum):
    """Where an observation is in the only lifecycle it has.

    Not a database column — it is derived from ``adopted_at`` and ``dismissed_at``,
    which are the facts, and computed at the edge so the inbox can filter on it.
    A stored status would be a third thing to keep in step with two timestamps
    that already say everything.

    ``OPEN`` is the default and the only one that means work is outstanding.
    ``ADOPTED`` and ``DISMISSED`` are both *somebody looked*, which is the
    distinction the inbox is actually sorted by.
    """

    OPEN = "open"
    ADOPTED = "adopted"
    DISMISSED = "dismissed"


@dataclass(frozen=True, slots=True)
class ObservationDraft:
    """One forwarded call, as the gateway knows it. INT-034's payload.

    Deliberately carries **no fingerprint**. The gateway does not compute one:
    A-154's normalisation rule is this module's, it is the thing most likely to
    change, and a copy of it on the hot path would be a second implementation
    drifting against the first — with the drift invisible, because both sides
    would keep working and simply group differently.

    ``call_id`` is a **value**, not a reference into ``ledger.call_record``. This
    module has no edge to call-ledger and may not read it; the id is here so a
    person can carry one string between the inventory screen and the call-record
    screen.
    """

    workspace_id: str
    namespace: str
    call_id: str
    consumer_key_id: str
    upstream_model: str
    occurred_at: datetime
    #: The caller's whole message set, exactly as it went upstream. The system
    #: message inside it is what gets fingerprinted; the rest is context the
    #: proposal never reads. See :mod:`prope.prompt_observation.fingerprint` for
    #: why the user turns are dropped before anything is stored.
    messages: Sequence[Mapping[str, object]] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ObservationRow:
    """One fingerprint group, as the inbox reads it."""

    id: str
    workspace_id: str
    namespace: str
    fingerprint: str
    body_hash: str
    current_body: str
    inferred_variables: tuple[str, ...]
    sighting_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    upstream_models: tuple[str, ...]
    adopted_prompt_id: str | None = None
    adopted_by: str | None = None
    adopted_at: datetime | None = None
    dismissed_by: str | None = None
    dismissed_at: datetime | None = None
    dismissal_reason: str | None = None
    redacted_at: datetime | None = None

    @property
    def status(self) -> ObservationStatus:
        if self.adopted_at is not None:
            return ObservationStatus.ADOPTED
        if self.dismissed_at is not None:
            return ObservationStatus.DISMISSED
        return ObservationStatus.OPEN

    @property
    def redacted(self) -> bool:
        return self.redacted_at is not None


@dataclass(frozen=True, slots=True)
class SightingRow:
    """One occurrence that CHANGED the body, which is the only kind that is kept.

    A sighting matching the group's current ``body_hash`` is rolled into the
    counter and stored as a row with no body. Without that rule this table is
    ``ledger.call_body`` under another name, at the same volume, on the readable
    side of ADR-0018 — which is the one thing ADR-0060 was written to avoid.
    """

    id: str
    observation_id: str
    body_hash: str
    body: str | None
    call_id: str
    consumer_key_id: str
    upstream_model: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class AdoptionProposal:
    """What the adopt screen offers, and **it is not a write** (ADR-0060).

    A person posts this through prompt-registry's own create routes, which write
    the ``property_created`` and ``revision_created`` events they always write.
    That is prompt-conversion's rule — *conversion never saves a revision* — for
    prompt-conversion's reason: adoption must be an act somebody performed, so
    non-negotiable #1 needs no new enforcement anywhere.

    **`namespace` is None and stays None** (SR-6). A-021 makes a model name
    immutable and ADR-0061 makes the namespace the access container, so a prompt
    adopted into the observation's own folder inherits that folder's grants for
    life and can never be moved out — A-049 makes retirement terminal, so there is
    not even a clean remedy. This is the one place in the module where a
    convenient default would do permanent damage, so there is no default and the
    person chooses.
    """

    observation_id: str
    #: The canonical body with `{{name}}` placeholders cut, in the form
    #: prompt-registry already accepts (A-011, A-078).
    body: str
    #: The slots A-154 inferred by diffing this group's members. A proposal, never
    #: applied — the same authority prompt-conversion's agent gets, and less,
    #: because a diff is weaker than a model.
    variables: tuple[str, ...]
    #: The `name` half of A-021's `namespace/name` only. Never the namespace.
    suggested_name: str
    namespace: None = None
