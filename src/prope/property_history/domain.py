"""The property-history vocabulary, as Python values.

``ActorType`` mirrors ``ck_history_event_actor_type_values``, which a live CHECK
reads back; ``RejectionReason`` mirrors the lock file's metric label set, which
has no database counterpart and so is pinned by a test instead
(``tests/unit/test_details_allow_list.py``).

These values stay literal ASCII at rest: ADR-0053's i18n layer sits at an API
edge this module does not have, and a stored token is a fact, not a label.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

import structlog

from prope.property_history.observability import append_rejected_total

log = structlog.get_logger(__name__)

#: ``ck_history_event_reason_length``. Characters, not bytes — ADR-0053 ships a
#: Vietnamese-only interface, so a byte cap would be a ~170-character cap.
MAX_REASON_CHARACTERS = 500


class ActorType(StrEnum):
    """``ck_history_event_actor_type_values``. There is no third state."""

    USER = "user"
    SYSTEM = "system"


class RejectionReason(StrEnum):
    """The label set of ``prope_property_history_append_rejected_total``.

    ``PropertyHistoryAppendRejected`` pages on **every** increment, so a fourth
    label value is a new page nobody declared. A fourth reason is a lock-file
    change, not a new enum member (D-63).
    """

    UNKNOWN_ACTION = "unknown_action"
    UNKNOWN_DETAIL_KEY = "unknown_detail_key"
    MISSING_REASON = "missing_reason"


class HistoryAppendRejected(Exception):  # noqa: N818
    """An append refused before any SQL was issued. **Do not catch this.**

    N818's ``Error`` suffix is refused deliberately, and so is ``ValueError``:
    both are what an ``except`` clause around a request body reaches for by
    habit, and swallowing this refusal commits the state change without its
    event (INT-006).

    ``__init__`` is the ONE increment site and the ONE log site, so the label can
    only ever be an enum member and the count fires whether or not anybody
    catches the raise. A ``prometheus_client`` counter is process state, which is
    why it survives the caller's rollback — the right instrument for a failure
    whose signature is that the transaction did not happen.

    The message names the offending **key**, never its value and never
    ``reason`` or ``details``.
    """

    def __init__(
        self,
        reason: RejectionReason,
        *,
        action: str,
        detail_key: str | None = None,
    ) -> None:
        super().__init__(_rejection_message(reason, action, detail_key))
        self.reason = reason
        self.action = action
        self.detail_key = detail_key

        append_rejected_total.labels(reason=reason.value).inc()
        fields: dict[str, str] = {"rejection_reason": str(reason), "action": action}
        if detail_key is not None:
            fields["detail_key"] = detail_key
        log.warning("property_history.append_rejected", **fields)


def _rejection_message(reason: RejectionReason, action: str, detail_key: str | None) -> str:
    if reason is RejectionReason.UNKNOWN_ACTION:
        return (
            f"action {action!r} is not in the action registry; the vocabulary is closed and "
            "a thirty-second action is a migration plus a restart (ADR-0038)"
        )
    if reason is RejectionReason.UNKNOWN_DETAIL_KEY:
        return (
            f"details key {detail_key!r} is not registered for action {action!r}; the value is "
            "deliberately not shown, because it is the object that failed the allow-list"
        )
    return f"action {action!r} requires a reason and none was supplied"


class HistoryDraftInvalid(Exception):  # noqa: N818
    """A draft that cannot be an audit row at all, refused at construction.

    Not a ``ValueError``, for :class:`HistoryAppendRejected`'s reason one step
    earlier: a draft is assembled inside the caller's own request validation,
    which is exactly where an ``except ValueError`` lives.

    **Not counted** — ``append_rejected_total``'s three labels are D-63's, and a
    draft that never reached ``append()`` refused no append.
    """


class HistoryCursorUnknown(Exception):  # noqa: N818
    """A cursor that resolves to no event in this workspace.

    Raised rather than answered with an empty page, which would read as *the
    trail ended here* — the one thing this table claims never happens.
    """

    def __init__(self, cursor: str, workspace_id: str) -> None:
        super().__init__(
            f"cursor {cursor!r} names no event in workspace {workspace_id!r}; the cursor is an "
            "opaque event id this module minted, and an empty page here would read as the end of "
            "a trail that does not end"
        )
        self.cursor = cursor
        self.workspace_id = workspace_id


class HistoryScopeMismatch(Exception):  # noqa: N818
    """D-72: the scope's workspace and the session's tenant disagree, or there is no tenant."""

    def __init__(self, scope_workspace_id: str, session_workspace_id: str | None) -> None:
        super().__init__(_mismatch_message(scope_workspace_id, session_workspace_id))
        self.scope_workspace_id = scope_workspace_id
        self.session_workspace_id = session_workspace_id


def _mismatch_message(scope_workspace_id: str, session_workspace_id: str | None) -> str:
    if session_workspace_id is None:
        return (
            f"a scope for workspace {scope_workspace_id!r} was read on a session carrying no "
            "app.workspace_id; open it with prope.db.session.workspace_transaction — without it "
            "every scope returns zero rows forever, which looks exactly like an empty audit log"
        )
    return (
        f"the scope names workspace {scope_workspace_id!r} but the session's tenant is "
        f"{session_workspace_id!r}; the read is contained either way, and this says so rather "
        "than answering with an empty Activity"
    )


@dataclass(frozen=True, slots=True)
class RegisteredAction:
    """One row of ``history.history_action_registry``. ``detail_keys`` is a
    ``frozenset`` because the allow-list check is a set difference, and because
    it is what makes ADR-0038's mapping immutable below the top level."""

    action: str
    target_type: str
    detail_keys: frozenset[str]
    requires_reason: bool
    writing_module: str


@dataclass(frozen=True, slots=True)
class HistoryEventDraft:
    """One event as a writing module hands it in — INT-006's ten envelope fields.

    ``id`` is absent by decision: :func:`append` mints it at the one site that
    writes, so no caller can collide on ``pk_history_event`` (OQ-035).

    ``frozen=True`` freezes the binding, not the ``details`` mapping. Nothing
    here mutates it — it is read twice and never written.
    """

    workspace_id: str
    actor_type: ActorType
    action: str
    target_type: str
    target_id: str
    occurred_at: datetime

    actor_id: str | None = None
    scope_prompt_id: str | None = None
    reason: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise HistoryDraftInvalid(
                f"occurred_at for a {self.action!r} event is naive; a naive datetime is read "
                "against the server's time zone, which makes a displayed instant depend on "
                "geography"
            )
        # ck_history_event_actor_id_present_unless_system, stated twice on
        # purpose: the caller meets a sentence naming the field rather than a
        # constraint name it cannot act on. A system actor WITH an id is allowed.
        if self.actor_id is None and self.actor_type is not ActorType.SYSTEM:
            raise HistoryDraftInvalid(
                f"a {self.action!r} event has actor_type={self.actor_type} and no actor_id; only "
                "a system actor may be anonymous, and an audit row that cannot say who acted is "
                "not one"
            )
        if self.reason is not None and len(self.reason) > MAX_REASON_CHARACTERS:
            raise HistoryDraftInvalid(
                f"reason for a {self.action!r} event is {len(self.reason)} characters; "
                f"ck_history_event_reason_length caps it at {MAX_REASON_CHARACTERS}"
            )


@dataclass(frozen=True, slots=True)
class HistoryEvent:
    """One event as a read returns it: all twelve columns, in table order.

    The asymmetry with :class:`HistoryEventDraft` is ``seq`` — engine-assigned,
    absent from the draft by construction, and the only sort key (A-125).

    Frozen for ``PriceRow``'s reason: ``prope_app`` cannot edit this table at all
    (ADR-0025), so a mutable view would be a lie about what it views.
    ``details`` is wrapped below because it is the mapping that escapes.
    """

    seq: int
    id: str
    workspace_id: str
    actor_type: ActorType
    actor_id: str | None
    action: str
    target_type: str
    target_id: str
    scope_prompt_id: str | None
    reason: str | None
    details: Mapping[str, object]
    occurred_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


@dataclass(frozen=True, slots=True)
class PromptScope:
    """INT-007's first scope shape: ``{workspace_id, scope_prompt_id}``, verbatim.

    ``KIND`` is the lock's ``scope_kind`` label value, named here so Phase 6's
    metric reads it rather than re-deriving it. Read on
    ``ix_history_event_workspace_id_scope_prompt_id_seq``.
    """

    workspace_id: str
    scope_prompt_id: str

    KIND = "prompt"


@dataclass(frozen=True, slots=True)
class TargetScope:
    """INT-007's second shape: ``{workspace_id, target_type, target_id}`` — one
    subject's trail. Read on
    ``ix_history_event_workspace_id_target_type_target_id_seq``."""

    workspace_id: str
    target_type: str
    target_id: str

    KIND = "target"


@dataclass(frozen=True, slots=True)
class ActorScope:
    """INT-007's third shape: ``{workspace_id, actor_id}`` — one person's actions.

    No screen names it. It exists because the lock declares it and because AC-9
    (*a removed member's events are still attributed to them*) is unanswerable
    without it.
    """

    workspace_id: str
    actor_id: str

    KIND = "actor"


#: D-73. Three concrete shapes rather than one with optional field groups: a
#: half-filled scope matches no declared read shape and no index.
Scope = PromptScope | TargetScope | ActorScope
