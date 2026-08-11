"""D-64's validating write path. Phase 5 renames or wraps this as INT-006's ``append()``.

**The session is handed in and the caller owns the transaction boundary**
(ADR-0023). This module opens no transaction, switches no workspace, commits
nothing and **never calls ``session.rollback()``** — ending the caller's
transaction underneath them is the exact inverse of *"commits or rolls back with
it"*, which five other lock files' "same transaction" sentence rests on. It is
the deliberate opposite of call-ledger's D-19; ``call_ledger/seams.py``'s own
argument names this module as the shape it does not copy, so the two files are
read together. **The raise is the whole mechanism**, and the caller's ``async
with`` is what performs the rollback.

**Two enforcement layers, and the seam between them is a decision.** The
``(action, target_type)`` pairing is refused by the engine
(``fk_history_event_action``); the ``details`` allow-list and ``requires_reason``
are refused here, because a CHECK cannot reach another table and ADR-0023 rejects
triggers for this module by name. ``tests/security/test_history_validation_has_
no_database_backstop.py`` is what keeps that asymmetry honest.

**A-046**: the ``details`` payload and the ``reason`` string are never logged. A
rejected append logs the action and the offending key NAME.

One ``ValueError`` can still originate on this path and it is the library's, not
this module's: ``python-ulid`` 4.x's default ``StrictMonotonicPolicy`` raises on
millisecond randomness exhaustion — 2**80 ids in one millisecond, unreachable.
"""

import json
from collections.abc import Mapping

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.property_history.domain import (
    HistoryAppendRejected,
    HistoryEventDraft,
    RegisteredAction,
    RejectionReason,
)

log = structlog.get_logger(__name__)

#: Eleven columns. **``seq`` is absent — not ``DEFAULT``, not a comment,
#: absent** — because a column that is not named cannot acquire a value by a
#: one-word edit, and ``GENERATED ALWAYS`` refuses the statement anyone would
#: write but not the statement someone determined would write.
#:
#: ``CAST(:details AS jsonb)`` over a ``json.dumps`` string rather than a bound
#: ``dict``: a raw ``text()`` statement carries no SQLAlchemy type information,
#: so a bound dict reaches the asyncpg dialect's jsonb encoder
#: (``b"\\x01" + str_value.encode()``) and raises ``AttributeError`` from inside
#: a codec. The cast makes the parameter's inferred type ``text``, and
#: serialisation becomes this module's decision rather than a dialect's — which
#: matters on the one column A-124 exists to police.
INSERT_HISTORY_EVENT = text(
    """
    INSERT INTO history.history_event (
        id, workspace_id, actor_type, actor_id, action, target_type, target_id,
        scope_prompt_id, reason, details, occurred_at
    ) VALUES (
        :id, :workspace_id, :actor_type, :actor_id, :action, :target_type, :target_id,
        :scope_prompt_id, :reason, CAST(:details AS jsonb), :occurred_at
    )
    """
)


def check_event(event: HistoryEventDraft, registry: Mapping[str, RegisteredAction]) -> None:
    """D-62's single validation site. ``record_event`` calls it and nothing else may.

    Phase 5's ``append()`` wraps ``record_event`` and **must not call this a
    second time**: a second call double-counts ``append_rejected_total``, and the
    lock's alert makes every increment a page, so a double count is a second page
    for one failure.

    The check order is a decision, not an accident. ``unknown_action`` first,
    because without a registration the other two questions have no answer;
    ``unknown_detail_key`` before ``missing_reason``, because a payload leak is
    T-022 (HIGH) and a missing reason is a policy omission, so the more serious
    refusal wins when a caller manages both.
    """
    registered = registry.get(event.action)
    if registered is None:
        raise HistoryAppendRejected(RejectionReason.UNKNOWN_ACTION, action=event.action)

    unregistered = frozenset(event.details) - registered.detail_keys
    if unregistered:
        # min() for a DETERMINISTIC message, not for meaning: one unregistered
        # key is enough to refuse, and the lexically first is reproducible.
        raise HistoryAppendRejected(
            RejectionReason.UNKNOWN_DETAIL_KEY,
            action=event.action,
            detail_key=min(unregistered),
        )

    # A reason of "   " satisfies NOT NULL and the 500-character CHECK and is not
    # a reason, so whitespace-only is refused here where the engine cannot.
    if registered.requires_reason and not (event.reason or "").strip():
        raise HistoryAppendRejected(RejectionReason.MISSING_REASON, action=event.action)


async def record_event(
    session: AsyncSession,
    event: HistoryEventDraft,
    registry: Mapping[str, RegisteredAction],
) -> str:
    """Validate ``event`` and insert it on the CALLER's session. Returns its id.

    ``session`` must be one the caller has already opened and set a tenant on.
    This function does not commit, so a raise anywhere below leaves nothing
    written and the caller's context manager owns the boundary.

    ``registry`` is a parameter and not a module global: Phase 5 owns the
    process-start load, and a module-level mutable default here is the shape
    ADR-0038 warns about.
    """
    check_event(event, registry)

    await session.execute(
        INSERT_HISTORY_EVENT,
        {
            "id": event.id,
            "workspace_id": event.workspace_id,
            "actor_type": str(event.actor_type),
            "actor_id": event.actor_id,
            "action": event.action,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "scope_prompt_id": event.scope_prompt_id,
            "reason": event.reason,
            "details": json.dumps(dict(event.details)),
            "occurred_at": event.occurred_at,
        },
    )

    # `reason` and `details` are absent from this line deliberately and
    # permanently — the lock file forbids both (A-046).
    log.info(
        "property_history.event_appended",
        event_id=event.id,
        action=event.action,
        target_type=event.target_type,
        target_id=event.target_id,
        scope_prompt_id=event.scope_prompt_id,
        actor_id=event.actor_id,
        workspace_id=event.workspace_id,
    )
    return event.id
