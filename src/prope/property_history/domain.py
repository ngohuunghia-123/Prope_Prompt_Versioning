"""The property-history vocabulary, as Python values.

``ActorType``'s members are byte-identical to ``ck_history_event_actor_type_
values`` in ``alembic/versions/0005_history_schema_and_vocabulary.py``.
``RejectionReason``'s are byte-identical to the metric label set
``docs/modules/property-history.lock.yml`` declares. The difference matters:
``ActorType`` has a live CHECK an existing invariant reads back, so proximity is
enough; ``RejectionReason`` has no database counterpart, so its cardinality is
pinned by a test (``tests/unit/test_details_allow_list.py``).

These values stay literal ASCII at rest. ADR-0053 puts Vietnamese behind an i18n
layer at an API edge this module does not have — a stored token is a fact, not a
label.

The enums live here and the counter lives in ``observability.py`` because the
exception carries the reason: an enum beside the counter would make the module's
vocabulary import its metrics.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import structlog
from ulid import ULID

from prope.property_history.observability import append_rejected_total

log = structlog.get_logger(__name__)

#: A-045 / ADR-0003. No shared ``new_id()`` helper: this is the third instance of
#: a pattern already written twice (``prc_``, ``req_``), and a helper worth
#: having would have to refactor the first two. Phase 7 owns that.
EVENT_ID_PREFIX = "hev_"

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

    The ``Error`` suffix N818 asks for is refused deliberately: INT-006 says *"a
    caller that catches this has broken the product's central claim"*, and
    ``Error`` is the suffix an ``except`` clause reaches for by habit. Not a
    ``ValueError`` for the same reason, one step further out — five modules will
    call the append path from code that validates its own request bodies, and an
    ``except ValueError`` around a request body would swallow the audit log's
    refusal and commit the state change without its event.

    ``__init__`` is the ONE increment site and the ONE log site. The label can
    therefore only ever be an enum member, the count fires on construction —
    before the raise and whether or not anybody catches it — and a
    ``prometheus_client`` counter is process state, so the caller's rollback
    cannot reach it. That last property is the whole reason it is the right
    instrument for a failure whose signature is that the transaction did not
    happen.

    The message and the log line name the offending **key**, never the offending
    value, and never ``reason`` or ``details``: those are the two columns the
    lock file forbids logging, and the value is by definition the object that
    failed the allow-list.
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


@dataclass(frozen=True, slots=True)
class RegisteredAction:
    """One row of ``history.history_action_registry``.

    ``detail_keys`` is a ``frozenset`` because the allow-list check is a set
    difference, and because it is what makes ADR-0038's mapping immutable rather
    than immutable-at-the-top-level.
    """

    action: str
    target_type: str
    detail_keys: frozenset[str]
    requires_reason: bool
    writing_module: str


@dataclass(frozen=True, slots=True)
class HistoryEventDraft:
    """One event as a writing module knows it. Every column except ``seq``.

    **Eleven fields where INT-006's envelope names ten.** ``id`` is the eleventh
    and — unlike ``seq`` — the envelope does not declare it database-assigned
    either, because A-045 / ADR-0003 make it the provider's to mint. It is
    carried here with a default factory so ``record_event`` can return a value
    the caller already holds. The widening is declared, not raised, and **Phase 5
    owns the reconciliation** with INT-006's actual signature; meanwhile
    ``__post_init__`` refuses an ``id`` without the ``hev_`` prefix.

    The field order deviates from the column order because a dataclass requires
    defaulted fields last, and matching the columns exactly would force a default
    onto ``workspace_id`` — the one field that must never have one.

    ``frozen=True`` freezes the binding, not the ``details`` mapping it holds.
    Nothing in this module mutates ``details``: it is read exactly twice, once
    for the allow-list difference and once to serialise it.
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
    id: str = field(default_factory=lambda: f"{EVENT_ID_PREFIX}{ULID()}")

    def __post_init__(self) -> None:
        if not self.id.startswith(EVENT_ID_PREFIX):
            raise ValueError(
                f"id {self.id!r} does not carry the {EVENT_ID_PREFIX!r} prefix; A-045 makes the "
                "type readable from the identifier and a bare ULID makes it a guess"
            )
        if self.occurred_at.tzinfo is None:
            raise ValueError(
                f"occurred_at for {self.id} is naive; a naive datetime is read against the "
                "server's time zone, which makes a displayed instant depend on geography"
            )
        # ck_history_event_actor_id_present_unless_system, stated twice on
        # purpose: the caller meets a sentence naming the field rather than a
        # constraint name it cannot act on. A system actor WITH an id is allowed.
        if self.actor_id is None and self.actor_type is not ActorType.SYSTEM:
            raise ValueError(
                f"{self.id} has actor_type={self.actor_type} and no actor_id; only a system "
                "actor may be anonymous, and an audit row that cannot say who acted is not one"
            )
        if self.reason is not None and len(self.reason) > MAX_REASON_CHARACTERS:
            raise ValueError(
                f"reason for {self.id} is {len(self.reason)} characters; "
                f"ck_history_event_reason_length caps it at {MAX_REASON_CHARACTERS}"
            )
