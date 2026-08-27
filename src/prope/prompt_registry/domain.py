"""The value objects the six seams are written in. No SQL, no FastAPI, no I/O.

Frozen and slotted throughout, like every value object in
``prope.call_ledger.domain`` and ``prope.access_control.domain``. Here the reason
is the same one ``Subject`` has: a :class:`RevisionBinding` a handler could mutate
is a binding whose body could be swapped after the released pointer chose it, and
the released pointer is the one thing in this product that must be traceable.

**Vocabularies are ``StrEnum`` and their members are byte-identical to the
database ``CHECK`` sets** in revision 0008. ``RevisionStatus`` in particular keeps
its spaces and its capitals — ``In review`` is stored, transmitted and compared
literally, and it is translated only at the point of display (ADR-0053 rule 9).
A second spelling here would be a second thing to keep in step with a constraint
that BR-03's foreign key reads.

**"In use" is not a status.** It is derived from
``prompt_property.released_version_id`` and never stored (A-065). There is no
member for it below and there must not be one.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

__all__ = [
    "MAX_BODY_CHARACTERS",
    "MAX_CHANGE_SUMMARY_CHARACTERS",
    "MAX_PURPOSE_CHARACTERS",
    "MAX_ROUTE_ENTRIES",
    "MAX_TAGS",
    "MAX_TAG_CHARACTERS",
    "MAX_TITLE_CHARACTERS",
    "NAME_PATTERN",
    "STATUS_TRANSITIONS",
    "DiffResult",
    "EventDetails",
    "FieldChange",
    "IllegalTransition",
    "LineOp",
    "LineChange",
    "ModelName",
    "ModelNameInvalid",
    "NothingToUpdate",
    "PromptRow",
    "PromptStatus",
    "ReleasedPointerConflict",
    "ResolveMiss",
    "RevisionBinding",
    "RevisionConflict",
    "RevisionDraft",
    "RevisionRead",
    "RevisionStatus",
    "RouteEntry",
    "RouterComboRow",
    "ReleasedListing",
    "NothingReleased",
]

#: A-050. Characters, never bytes — ADR-0053 makes Vietnamese the one interface
#: language, and a byte cap is roughly a third of the text a character cap allows.
MAX_BODY_CHARACTERS = 32768

MAX_CHANGE_SUMMARY_CHARACTERS = 200

MAX_TITLE_CHARACTERS = 200

MAX_PURPOSE_CHARACTERS = 2000

MAX_TAGS = 20

MAX_TAG_CHARACTERS = 60

#: A-021's shape for both halves of the model name, byte-identical to
#: ``ck_prompt_property_namespace_shape`` and ``ck_prompt_property_name_shape``.
#: Lower case only, because a model name reaches the gateway as an OpenAI
#: ``model`` field and a case-sensitive lookup on a value people retype by hand
#: is a support conversation nobody wins.
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


class PromptStatus(StrEnum):
    """``ck_prompt_property_status_values``. Retired is terminal (A-049).

    Nothing un-retires a prompt and nothing deletes one. A retired prompt keeps
    every revision it ever had, because the revisions are the asset and the
    status is a label on the shelf they sit on.
    """

    ACTIVE = "active"
    RETIRED = "retired"


class RevisionStatus(StrEnum):
    """``ck_revision_status_values``, spaces and capitals included (A-065).

    These three are what is STORED. ``In use`` is derived from the released
    pointer and ``Retired`` is a prompt status, and neither has a member here.

    The values travel through INT-012 from release-control, and BR-03's foreign
    key compares ``Approved`` literally — so a "tidier" lower-case spelling would
    silently make every released pointer unsettable.
    """

    DRAFT = "Draft"
    IN_REVIEW = "In review"
    APPROVED = "Approved"


#: ADR-0008's state machine, and it lives HERE because INT-012 says the provider
#: validates the transition. release-control decides *whether* to ask; this
#: module decides whether the ask is legal, so the legal machine exists once.
#:
#: ``Approved -> Draft`` is the changes-requested path and is deliberately
#: present: a reviewer who asks for changes puts the revision back where its
#: author can supersede it. ``Approved -> Approved`` is absent, which is what
#: makes INT-012 non-idempotent — a double-submit raises rather than being
#: absorbed.
STATUS_TRANSITIONS: dict[RevisionStatus, frozenset[RevisionStatus]] = {
    RevisionStatus.DRAFT: frozenset({RevisionStatus.IN_REVIEW}),
    RevisionStatus.IN_REVIEW: frozenset({RevisionStatus.APPROVED, RevisionStatus.DRAFT}),
    RevisionStatus.APPROVED: frozenset({RevisionStatus.DRAFT}),
}


class ResolveMiss(StrEnum):
    """INT-009's two misses, which are one 404 and two metric lines.

    They are the same answer to the caller and must never be two — a consumer
    key that could tell them apart could enumerate the registry by observing
    which names refuse differently (A-081, A-116). They are two values here
    because ``prope_registry_resolve_miss_total``'s ``reason`` label is the only
    place a withdrawal is visible as a withdrawal rather than as a typo
    (ADR-0009).
    """

    UNKNOWN_MODEL = "unknown_model"
    NO_RELEASE = "no_release"


class ModelNameInvalid(ValueError):  # noqa: N818
    """A model name that is not ``namespace/name`` in A-021's shape."""


@dataclass(frozen=True, slots=True)
class ModelName:
    """A-021's ``namespace/name``, parsed once at the edge and passed as a value.

    Immutable once created, which the lock states as a property of the stored
    row and this type states as a property of the parse: there is no setter, and
    :meth:`parse` is the only constructor a caller should reach for.

    The pin is deliberately NOT part of this type. ``support/refund@3`` is a
    model name and a pin, and keeping them apart is what stops a pin reaching a
    unique-constraint lookup.
    """

    namespace: str
    name: str

    def __str__(self) -> str:
        return f"{self.namespace}/{self.name}"

    @classmethod
    def parse(cls, raw: str) -> "ModelName":
        namespace, separator, name = raw.partition("/")
        if not separator:
            raise ModelNameInvalid(
                f"{raw!r} is not a model name; A-021 makes it namespace/name, and a bare name "
                "would be unique per workspace only by accident"
            )
        if "/" in name:
            raise ModelNameInvalid(
                f"{raw!r} carries more than one '/'; the name is one segment, not a path"
            )
        if not NAME_PATTERN.match(namespace) or not NAME_PATTERN.match(name):
            raise ModelNameInvalid(
                f"{raw!r} is outside A-021's shape: each half is lower-case alphanumeric, may "
                "carry '.', '_' or '-' after the first character, and is at most 63 characters"
            )
        return cls(namespace=namespace, name=name)


#: A router combo holds at most this many rungs. Byte-identical to
#: ``ck_router_combo_entry_priority_bounded`` and its twin on the frozen copy, and
#: it is also what bounds the gateway's ``entry`` metric label. ADR-0069.
MAX_ROUTE_ENTRIES = 5


@dataclass(frozen=True, slots=True)
class RouteEntry:
    """One rung of a route, ordered by ``priority`` ascending.

    Deliberately three fields and no display name. This travels on the hot path
    inside a :class:`RevisionBinding`, where a provider's display name is
    something the gateway would carry and never read — and carrying it would put
    workspace-authored text one careless log line away from A-046. The settings
    screens join the name in their own read model.
    """

    priority: int
    provider_config_id: str
    upstream_model: str


@dataclass(frozen=True, slots=True)
class RouterComboRow:
    """One editable template, with its rungs, as the settings screen reads it.

    **No provider display names.** Resolving them here would mean registry SQL
    joining ``provider.provider_config`` across a schema boundary, which
    schema-per-module forbids and which INT-016 deliberately does not open a seam
    for. The client already holds the provider list — it renders a name for a
    revision's binding the same way — so it joins these ids itself.

    ``entries`` is ordered by priority and is the whole list: a combo with no
    rungs cannot be saved, and one is never paged.
    """

    combo_id: str
    workspace_id: str
    display_name: str
    description: str
    entries: tuple[RouteEntry, ...]
    created_by: str
    created_at: datetime
    updated_at: datetime
    #: How many revisions were snapshotted from this template. NOT a dependency
    #: count — nothing is blocked by it. It is the number that lets the edit
    #: screen say *"editing this changes nothing already released"* with a figure
    #: behind it, which is the sentence the snapshot rule needs to be believed.
    revision_count: int = 0


@dataclass(frozen=True, slots=True)
class RevisionBinding:
    """INT-009's hit: everything the gateway needs to make one call, and no more.

    No title, no owner, no tags, no change summary — the gateway renders nothing
    and a field it does not need is a field that ends up in a log line on the hot
    path. ``fallback_answer`` is here because A-033 makes it the gateway's answer
    to an upstream failure, and it travels with the binding rather than being
    fetched separately so that a fallback can never belong to a different
    revision than the call it is standing in for.

    **A revision binds one pair, or one route, or neither** — never both, and
    ``ck_revision_binds_a_pair_or_a_route_never_both`` is what makes that a fact
    rather than an intention. :attr:`candidates` is how the gateway stops caring
    which of the two it got.
    """

    prompt_id: str
    version_id: str
    revision_number: int
    body: str
    provider_config_id: str | None
    upstream_model: str | None
    parameters: dict[str, Any]
    fallback_answer: str | None
    #: Provenance of the frozen route, snapshotted at create. A VALUE: the
    #: template it was copied from may since have been renamed or deleted, and
    #: what this revision runs is unaffected either way (ADR-0069).
    route_combo_id: str | None = None
    route_combo_name: str | None = None
    route: tuple[RouteEntry, ...] = ()

    @property
    def routed(self) -> bool:
        return self.route_combo_id is not None

    @property
    def candidates(self) -> tuple[RouteEntry, ...]:
        """The ordered list the gateway walks, whichever way this revision binds.

        **A single pair is a ONE-ENTRY ROUTE, and that is the whole point.** The
        gateway's dispatch loop is then written once, and the unrouted path — the
        overwhelming majority of traffic — is that loop's degenerate case rather
        than a second branch standing beside it. A second branch is where the two
        paths drift, and the one that drifts is always the one nobody exercises.

        Empty when the revision binds nothing at all, which is a legal state for
        a draft and is what the gateway answers with
        ``provider_configuration_unusable``.
        """
        if self.route:
            return self.route
        if self.provider_config_id is None or self.upstream_model is None:
            return ()
        return (RouteEntry(1, self.provider_config_id, self.upstream_model),)


@dataclass(frozen=True, slots=True)
class ReleasedListing:
    """One row of INT-010. Three fields, and that is the whole of ``GET /v1/models``."""

    model_name: str
    version_id: str
    revision_number: int


@dataclass(frozen=True, slots=True)
class RevisionRead:
    """INT-011's shape: a revision as evaluation and release-control read it.

    Wider than :class:`RevisionBinding` by exactly the fields a review screen
    shows — author, timestamp, change summary and status. A single type serving
    both seams would put the body on a screen that wanted a status and the author
    on a hot path that wanted neither.
    """

    version_id: str
    prompt_id: str
    workspace_id: str
    revision_number: int
    body: str
    provider_config_id: str | None
    upstream_model: str | None
    parameters: dict[str, Any]
    fallback_answer: str | None
    change_summary: str
    author_id: str
    status: RevisionStatus
    created_at: datetime
    #: Mutable presentation labels on an otherwise immutable body — the version
    #: rail's own classification, edited in place rather than by a new revision.
    #:
    #: There is deliberately no `author_email` beside this. `author_id` is an
    #: opaque value owned by access-control, and the byline is resolved by
    #: `access_control.seams.user_emails` and handed to the response mapper —
    #: the same shape as a call record's `consumer_label`. A field here would
    #: mean registry SQL reading `access."user"` across a schema boundary.
    tags: tuple[str, ...] = ()
    #: The profile STAMPED at revision create and re-stamped at submit (D-02).
    #: A reviewer approves a body and the exposure it was judged under, and the
    #: drift between this and the property's current profile is what
    #: `prompt-improvement` will later raise `PROFILE_DRIFT` on.
    audience: str = "undeclared"
    untrusted_input: str = "undeclared"
    acts: str = "undeclared"
    sensitivity: str = "undeclared"
    original_body: str = ""
    original_format: str = "legacy"
    original_filename: str | None = None
    conversion_model: str | None = None
    conversion_schema_version: str | None = None
    #: The frozen route, when this revision binds one instead of a pair. Carried
    #: here rather than fetched per revision because four screens render it and
    #: several of them render lists — see ADR-0069. Empty for a pair-bound or
    #: unbound revision, and `route_combo_id` is the field that tells the two
    #: apart without inspecting the tuple.
    route_combo_id: str | None = None
    route_combo_name: str | None = None
    route: tuple[RouteEntry, ...] = ()

    @property
    def routed(self) -> bool:
        return self.route_combo_id is not None

    @property
    def primary(self) -> RouteEntry | None:
        """The ONE binding a measurement uses. Rung 1 of a route, or the pair.

        **This is not :meth:`RevisionBinding.candidates` and must not become it.**
        That property exists so the gateway can walk a route; this one exists so
        evaluation, the readiness probe and the playground deliberately do not.

        A-164 says it in as many words for the probe — *"a probe wants the truth
        about what this binding does, and a silent failover would measure a model
        the released revision will not use"* — and the same argument decides
        evaluation. A cost delta computed against whichever provider happened to
        be up that minute is not comparable to the one computed last week, and a
        pass rate that moved because a rate limit pushed half the cases onto a
        different model is a number nobody can act on. Measurement wants one
        model; production wants an answer.

        ``None`` when the revision binds nothing at all, which is a legal draft
        state and is what those three callers already refuse on.
        """
        if self.route:
            return self.route[0]
        if self.provider_config_id is None or self.upstream_model is None:
            return None
        return RouteEntry(1, self.provider_config_id, self.upstream_model)


@dataclass(frozen=True, slots=True)
class PromptRow:
    """One ``prompt_property`` row as this module reads it.

    ``search_text`` is ABSENT and must stay absent (T-017). It is a second copy
    of the prompt body maintained for the trigram index, and the cheapest way to
    keep it out of every response is for the type the responses are built from to
    have no field that could carry it.
    """

    id: str
    workspace_id: str
    namespace: str
    name: str
    title: str
    purpose: str
    owner_id: str
    access_level: str
    status: PromptStatus
    tags: tuple[str, ...]
    released_version_id: str | None
    released_at: datetime | None
    created_at: datetime
    updated_at: datetime

    #: ADR-0067's Usage Profile. Registry OWNS these columns; prompt-readiness
    #: reads them and never writes them. Last in the field order because they
    #: carry defaults — `"undeclared"` is a real value and not a NULL (revision
    #: 0030), so a card can badge an unanswered profile honestly rather than
    #: quietly asserting somebody called this prompt public.
    audience: str = "undeclared"
    untrusted_input: str = "undeclared"
    acts: str = "undeclared"
    sensitivity: str = "undeclared"

    @property
    def model_name(self) -> str:
        return f"{self.namespace}/{self.name}"


class LineOp(StrEnum):
    """What happened to one line of the body. ``difflib``'s opcodes, named."""

    EQUAL = "equal"
    ADDED = "added"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class LineChange:
    """One line of A-015's textual diff, with both sides' numbers where they exist."""

    op: LineOp
    text: str
    from_line: int | None = None
    to_line: int | None = None


@dataclass(frozen=True, slots=True)
class FieldChange:
    """One row of the field-level comparison beside the body diff.

    ``before`` and ``after`` are rendered strings rather than raw values: the
    comparison is shown to a human on the review screen, and a reviewer
    comparing ``{"temperature": 0.7}`` against ``{"temperature": 0.2}`` should not
    have to know what a JSON object looks like to see which number moved.
    """

    field: str
    before: str | None
    after: str | None

    @property
    def changed(self) -> bool:
        return self.before != self.after


@dataclass(frozen=True, slots=True)
class DiffResult:
    """A-015 and A-047: computed on demand, never stored.

    Both halves in one value because the review screen shows both and a caller
    that could ask for one without the other would eventually ship a screen that
    shows a body change with no note that the model underneath it changed too.
    """

    from_version_id: str
    to_version_id: str
    lines: tuple[LineChange, ...]
    fields: tuple[FieldChange, ...]


class RevisionConflict(Exception):  # noqa: N818
    """A-048: two authors allocated the same ``revision_number`` and one lost.

    Carries the number that collided so the loser's message can say *someone
    else saved first* rather than *something went wrong*. The unique constraint
    is the arbiter; this is what the arbiter's verdict is called in Python.
    """

    def __init__(self, prompt_id: str, revision_number: int) -> None:
        super().__init__(
            f"revision {revision_number} of {prompt_id} was allocated by another transaction"
        )
        self.prompt_id = prompt_id
        self.revision_number = revision_number


class ReleasedPointerConflict(Exception):  # noqa: N818
    """INT-013's compare-and-set lost: somebody released something else meanwhile.

    Surfaced as a ``409`` at release-control's edge. Overwriting silently is how
    a release nobody decided reaches production, so this is a raise and never a
    retry.
    """

    def __init__(self, prompt_id: str, expected: str | None, actual: str | None) -> None:
        super().__init__(
            f"{prompt_id} has {actual!r} released, not the {expected!r} this decision was made "
            "against"
        )
        self.prompt_id = prompt_id
        self.expected = expected
        self.actual = actual


class NothingReleased(Exception):  # noqa: N818
    """INT-014 was asked to withdraw a release that does not exist.

    A caller bug rather than a no-op, and it raises for that reason: a withdrawal
    that quietly succeeded against nothing would write a ``release_withdrawn``
    event describing an act that did not happen.
    """

    def __init__(self, prompt_id: str) -> None:
        super().__init__(f"{prompt_id} has nothing released to withdraw")
        self.prompt_id = prompt_id


class NothingToUpdate(Exception):  # noqa: N818
    """The prompt vanished between the permission check and the write.

    Only reachable if another transaction did something no route offers, since
    nothing in this module deletes a prompt and ``Retired`` is a status rather
    than a removal (A-049). It exists so that the impossible case is a named
    exception rather than an ``AttributeError`` on ``None`` three frames away.
    """

    def __init__(self, prompt_id: str) -> None:
        super().__init__(f"{prompt_id} disappeared between the permission check and the write")
        self.prompt_id = prompt_id


class IllegalTransition(Exception):  # noqa: N818
    """INT-012 was asked for a transition :data:`STATUS_TRANSITIONS` does not allow.

    Also raised for an unknown ``version_id``, because from release-control's
    side both are the same mistake: the decision it recorded cannot be applied,
    and its transaction must abort along with the history event claiming it was.
    """

    def __init__(self, version_id: str, current: RevisionStatus | None, target: RevisionStatus) -> None:
        known = "unknown" if current is None else current.value
        super().__init__(f"{version_id} is {known} and cannot move to {target.value}")
        self.version_id = version_id
        self.current = current
        self.target = target


#: Details attached to a history event, before ``property_history.append`` checks
#: them against the registered allow-list. Declared here so ``events.py`` has one
#: name for the shape, exactly as ``access_control.domain`` declares its own.
EventDetails = dict[str, Any]


@dataclass(frozen=True, slots=True)
class RevisionDraft:
    """What ``POST /prompts/{id}/revisions`` carries into the write path.

    ``parameters`` defaults through a factory rather than a shared literal: a
    mutable default on a frozen dataclass is the one way a "frozen" value object
    can still be edited by whoever holds a second reference to it.
    """

    body: str
    change_summary: str
    original_body: str | None = None
    original_format: str = "xml"
    original_filename: str | None = None
    conversion_model: str | None = None
    conversion_schema_version: str | None = None
    provider_config_id: str | None = None
    upstream_model: str | None = None
    #: The TEMPLATE to copy, not the entries to write. The caller names a combo
    #: and the write path copies it in one statement, so "which combo was this"
    #: stays a fact rather than a claim and no caller can compose a route that no
    #: combo in Settings ever contained (ADR-0069).
    router_combo_id: str | None = None
    fallback_answer: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    #: Classification labels stamped at create and editable afterwards without a
    #: new revision — the one part of this draft that is not immutable once
    #: written. A tuple, so a frozen draft cannot be relabelled through a second
    #: reference the way a list default would allow.
    tags: tuple[str, ...] = ()


#: The palette the folder grid draws from, and the one the client offers as
#: swatches. Eight entries, ordered — :func:`default_folder_color` indexes into
#: it, so reordering this tuple silently repaints every folder that never picked
#: a colour. The client holds the same list in the same order.
FOLDER_COLORS: tuple[str, ...] = (
    "#6366f1",
    "#f59e0b",
    "#10b981",
    "#8b5cf6",
    "#ef4444",
    "#06b6d4",
    "#ec4899",
    "#14b8a6",
)

MAX_FOLDER_NAME_CHARACTERS = 200

MAX_FOLDER_DESCRIPTION_CHARACTERS = 2000

#: ``ck_folder_color_shape``. Lower case only, so ``#6366F1`` and ``#6366f1``
#: cannot both be stored and then compared as different colours.
COLOR_PATTERN = re.compile(r"^#[0-9a-f]{6}$")


def default_folder_color(slug: str) -> str:
    """The colour a folder gets when nobody picked one.

    A hash rather than a counter, because a folder that has never been declared
    has no row to hold a counter's state — an *observed* namespace and a declared
    one must render the same colour or the grid repaints the moment somebody
    renames a folder. Ported byte-for-byte from the client's ``folderColor``,
    including the 32-bit wrap: the two must agree or the swatch the dialog
    pre-selects is not the colour the row comes back with.
    """
    accumulator = 0
    for character in slug:
        accumulator = (accumulator * 31 + ord(character)) & 0xFFFFFFFF
    return FOLDER_COLORS[accumulator % len(FOLDER_COLORS)]


@dataclass(frozen=True, slots=True)
class FolderRow:
    """One row of the folder list — a **union**, not a table read.

    ``declared`` is what tells the two halves apart. A folder with a row in
    ``registry.folder`` carries the name, description and colour somebody chose;
    an observed namespace carries derived stand-ins, and the caller may still
    ``PATCH`` it, which is what turns it into a declared one.

    The four counts are over the prompts **this actor can see** (INT-002). A
    count that ignored visibility would put the number of private prompts in a
    namespace on a card that lists none of them, which is the disclosure BR-01
    closes as not-found.
    """

    slug: str
    name: str
    description: str
    color: str
    declared: bool
    prompt_count: int
    approved_count: int
    in_review_count: int
    draft_count: int
    updated_at: datetime


class FolderSlugTaken(Exception):  # noqa: N818
    """The slug is already claimed — by a folder row, or by a prompt's namespace.

    One exception for both, because they are one fact to the person typing: the
    grid already draws a card with that name either way, and telling them the
    folder "does not exist yet, but the name is unavailable" would be a
    distinction about our storage rather than about their workspace.
    """

    def __init__(self, slug: str) -> None:
        super().__init__(f"the slug {slug!r} is already in use in this workspace")
        self.slug = slug


class FolderNotEmpty(Exception):  # noqa: N818
    """Delete refused: prompts still carry this namespace.

    Deleting the row would in fact be harmless — the prompts keep their
    ``namespace`` value and the folder simply reverts to a derived one — but a
    delete that *reads* destructive should not need that explained in a dialog.
    """

    def __init__(self, slug: str, prompt_count: int) -> None:
        super().__init__(f"the folder {slug!r} still holds {prompt_count} prompt(s)")
        self.slug = slug
        self.prompt_count = prompt_count
