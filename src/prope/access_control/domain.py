"""The value objects the five seams are written in. No SQL, no FastAPI, no I/O.

Frozen and slotted throughout, like every value object in
`prope.call_ledger.domain` — and here the reason is sharper than style. An
`Actor` a handler could mutate is a handler that could answer a permission
question about somebody else; a `Subject` it could mutate is ADR-0020's
caller-supplies-the-attributes contract with the safety removed.

**Vocabularies are `StrEnum` and their members are byte-identical to the
database `CHECK` sets** in revision 0006. A second spelling here would be a
second thing to keep in step with a constraint, and the first drift would be
invisible in both directions — the query would return zero rows and the check
would deny, which is the safe answer and therefore the silent one.

**`AccessLevel` and `OwnerId` are inputs, not state.** They describe a subject
this module may not read (ADR-0020). They appear here because `may()`'s signature
needs a type for them, and nowhere else — no table in the `access` schema holds
either.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "AccessLevel",
    "Actor",
    "ActorType",
    "FilterMode",
    "GrantLevel",
    "MemberStatus",
    "PermissionRefused",
    "Role",
    "Subject",
    "SubjectType",
    "UserStatus",
    "VisibleFilter",
]


class ActorType(StrEnum):
    """Who is asking. Two kinds, and the second one cannot hold a session.

    A `USER` presents a session cookie (INT-005); a `CONSUMER_KEY` presents
    `prope_<key_id>_<secret>` at the gateway (INT-003). They are not
    interchangeable and the difference is not cosmetic: a consumer key holds no
    role binding and no grant, so `may()` answers **deny** for every action in
    the vocabulary when the actor is a key. A key's entire authority is
    `may_resolve()`, which is a different question against a different table.
    """

    USER = "user"
    CONSUMER_KEY = "consumer_key"


class Role(StrEnum):
    """A-007's four working roles. `ck_role_binding_role_values` holds the same set.

    **A placeholder for OQ-006, and the placeholder is load-bearing anyway.** The
    matrix rows are a seed and OQ-006's answer replaces them without a release
    (`GET /api/v1/permissions` renders the running one so the two can be diffed).
    The *role set* is not: removing a role after bindings exist needs a data
    migration, which is why A-007 records exactly four and why they map onto the
    separation `00_context.md#constraints` already fixes.
    """

    OWNER = "Owner"
    REVIEWER = "Reviewer"
    VIEWER = "Viewer"
    ADMIN = "Admin"


class GrantLevel(StrEnum):
    """A-112. What a per-prompt grant may confer, and the ceiling is deliberate.

    No grant confers approve, release, withdraw or break-glass. Letting an owner
    hand those out per prompt would let a workspace's non-negotiable separation
    of edit / review / release be dissolved one prompt at a time, by somebody
    being helpful.
    """

    VIEWER = "viewer"
    EDITOR = "editor"


class AccessLevel(StrEnum):
    """BR-01's private-by-default, as the caller reports it.

    **Supplied by prompt-registry, never read here** (ADR-0020). `PRIVATE` is the
    default state a prompt is created in and the reason `visible_subject_filter`
    exists at all; `WORKSPACE` is a prompt its owner has opened to the workspace,
    which is what makes ownership and grants stop being the only path to it.
    """

    PRIVATE = "private"
    WORKSPACE = "workspace"


class MemberStatus(StrEnum):
    """`active` or `removed`, and there is no third.

    There is no pending state because there is no invitation to be pending on
    (A-110). A removed member keeps their row: A-151 needs it to know which
    workspaces a tombstone must write its event into, and revision 0006 withholds
    `DELETE` on the table so the retention is a privilege rather than a habit.
    """

    ACTIVE = "active"
    REMOVED = "removed"


class UserStatus(StrEnum):
    """`active` or `tombstoned`. Nothing un-tombstones a row (ADR-0054 §8)."""

    ACTIVE = "active"
    TOMBSTONED = "tombstoned"


class SubjectType(StrEnum):
    """What a permission question is *about*.

    Deliberately not a closed mirror of every table in Prope: this module cannot
    read any of them, so the type is a label the caller supplies and this module
    passes back into its own grant lookup. Only `PROMPT` has per-subject grants;
    the rest resolve on role bindings alone, which is why `prompt_grant` is the
    only per-subject table in the schema.
    """

    PROMPT = "prompt"
    REVISION = "revision"
    RELEASE = "release"
    EVAL_SUITE = "eval_suite"
    EVAL_RUN = "eval_run"
    PROVIDER_CONFIG = "provider_config"
    WORKSPACE = "workspace"
    USER = "user"


class FilterMode(StrEnum):
    """A-118's three answers, and `NONE` is a real one.

    `NONE` must render as an empty list at the caller, never as an error and
    never as an unfiltered query. That is not a nicety — the failure this whole
    seam exists to prevent is a developer under deadline pressure writing the
    list query with no filter, and a mode that looked like a failure is a mode
    somebody would code around.

    `ALL` means the actor may see every subject of that type **in the
    workspace**. It is not a bypass of tenancy: RLS enforces that underneath
    regardless (ADR-0045).
    """

    ALL = "all"
    NONE = "none"
    IDS = "ids"


@dataclass(frozen=True, slots=True)
class Actor:
    """Who is asking, and in which workspace. INT-001's first parameter.

    `workspace_id` is the tenant the caller has already authenticated into, and
    it is compared against the subject's rather than trusted alone — see
    `permissions.may`. An actor and a subject in two different workspaces is a
    deny, not a cross-tenant read, because there is no query here that could
    reach the other one anyway.
    """

    type: ActorType
    id: str
    workspace_id: str


@dataclass(frozen=True, slots=True)
class Subject:
    """What the question is about, **with its attributes supplied by the caller**.

    This is ADR-0020 as a type. `owner_id` and `access_level` live in tables this
    module is forbidden to read, so the caller — which has just read the row it
    is about to act on — passes them. Both are optional because most subjects
    have neither, and a subject that omits them is answered on role bindings
    alone.

    **A caller that lies gets the answer it asked for**, and that is stated
    rather than mitigated. In one process (A-012) a caller that would forge an
    owner id is a caller that could have skipped the check entirely, so the
    boundary this defends is module hygiene rather than a hostile one. If Prope's
    modules are ever split across processes this signature is the first thing
    that must change, and ADR-0020 says so in writing.
    """

    type: SubjectType
    id: str
    workspace_id: str
    owner_id: str | None = None
    access_level: AccessLevel | None = None


@dataclass(frozen=True, slots=True)
class VisibleFilter:
    """A-118's return: a **set**, for the caller's own `WHERE` clause.

    Not a predicate, not a callback, not a row filter. The caller pushes it into
    SQL it already owns, which is what lets prompt-registry keep its promise that
    *"permission filtering lives in the repository layer, not in handlers"*
    without the cross-module join its own lock forbids.

    `ids` is empty unless `mode` is `IDS`, and `__post_init__` refuses the two
    incoherent shapes rather than letting a caller meet them at a `WHERE id IN
    ()`. An `ALL` carrying ids would be a filter somebody reads as narrower than
    it is; an `IDS` carrying none is `NONE` spelled in a way that survives a
    careless `if result.ids:`.
    """

    mode: FilterMode
    ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.mode is FilterMode.IDS and not self.ids:
            raise ValueError("mode=ids with no ids is mode=none; say the narrower thing")
        if self.mode is not FilterMode.IDS and self.ids:
            raise ValueError(f"mode={self.mode} carries ids, which no caller would apply")

    @classmethod
    def all(cls) -> "VisibleFilter":
        return cls(FilterMode.ALL)

    @classmethod
    def none(cls) -> "VisibleFilter":
        return cls(FilterMode.NONE)

    @classmethod
    def of(cls, ids: Sequence[str]) -> "VisibleFilter":
        """`IDS` for a non-empty sequence, `NONE` for an empty one.

        The collapse happens here rather than at three call sites, because the
        empty case is the one a query returns and the one `__post_init__`
        refuses.
        """
        unique = tuple(sorted(set(ids)))
        return cls(FilterMode.IDS, unique) if unique else cls.none()


class PermissionRefused(Exception):  # noqa: N818
    """A-116's two refusal shapes, as one exception carrying which one it is.

    **The shape is a security decision, not an ergonomic one.** `visible=False`
    renders as not-found — identical in status and body to an id that does not
    exist — because a forbidden response on a private prompt confirms the prompt
    exists, which is precisely the leak BR-01 is about. `visible=True` renders as
    forbidden **naming the missing permission**, because once somebody can
    already see the subject, hiding *why* they cannot act on it protects nothing
    and produces the worst support conversation in the product: a button that
    does nothing, with no way to find out what to ask for.

    Not a `ManagementRefusal` subclass. This is raised in the permission layer,
    which has no HTTP status to give; `api.refuse` turns it into one. Keeping the
    two apart is what stops the permission layer growing an opinion about status
    codes — and what lets prompt-registry, evaluation and release-control reuse
    the decision without importing an envelope.
    """

    def __init__(self, action: str, subject: Subject, *, visible: bool) -> None:
        super().__init__(f"{action} refused on {subject.type}:{subject.id}")
        self.action = action
        self.subject = subject
        self.visible = visible


#: Details attached to a history event, before `property_history.append` checks
#: them against the registered allow-list. Declared here so `events.py` has one
#: name for the shape and `append`'s `Mapping[str, object]` is not re-spelled at
#: ten call sites.
EventDetails = dict[str, Any]


@dataclass(frozen=True, slots=True)
class KeyPresentation:
    """A parsed `prope_<key_id>_<secret>`, **with the secret already discarded**.

    The type exists to make A-046's rule structural instead of remembered. The
    presented string is a credential in full; `keys.parse_presented_key` returns
    this, and this carries only the `key_id` — which the lock file explicitly
    marks loggable — plus the digest the comparison needs. There is no field on
    it that could reach a log line, and no accessor that could reconstruct the
    secret.
    """

    key_id: str
    secret_hash: str = field(repr=False)
