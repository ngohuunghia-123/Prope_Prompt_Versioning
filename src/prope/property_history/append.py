"""INT-006's validating write path.

**The caller owns the transaction boundary** (ADR-0023, the opposite of
call-ledger's D-19): no transaction is opened, nothing is committed, and
``session.rollback()`` is never called. The raise is the whole mechanism.

**Two enforcement layers**, kept honest by
``tests/security/test_history_validation_has_no_database_backstop.py``: the
``(action, target_type)`` pairing is the engine's, the ``details`` allow-list
and ``requires_reason`` are refused here. A-046: neither ``details`` nor
``reason`` is ever logged.
"""

import json
import time
from collections.abc import Mapping

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.property_history.domain import (
    NEVER_PROMPT_SCOPED_TARGET_TYPES,
    HistoryAppendRejected,
    HistoryEventDraft,
    RegisteredAction,
    RejectionReason,
)
from prope.property_history.observability import (
    append_duration_seconds,
    append_total,
    null_scope_prompt_total,
    write_failed_total,
)
from prope.property_history.registry import registered_registry

log = structlog.get_logger(__name__)

#: A-045 / ADR-0003, minted here because this is the one site that writes. Phase
#: 7 owns the ``new_id()`` refactor this is the third instance of.
EVENT_ID_PREFIX = "hev_"

#: Eleven columns; ``seq`` is **absent**, not ``DEFAULT`` — a column that is
#: not named cannot acquire a value by a one-word edit.
#:
#: WHY the cast: a raw ``text()`` carries no type information, so a bound dict
#: reaches asyncpg's jsonb encoder and raises from inside a codec.
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
    """D-62's single validation site. :func:`append` calls it and nothing else may
    — a second call is a second page for one failure (D-66).

    Order is a decision: ``unknown_action`` first, then ``unknown_detail_key``
    ahead of ``missing_reason`` because a payload leak is T-022 (HIGH).

    **Three checks, not four, and the allow-list reaches keys and not values.**
    The ``(action, target_type)`` pairing is deliberately left to
    ``fk_history_event_action`` though ``registered.target_type`` is in memory,
    so a mispaired caller gets a poisoned transaction rather than a named
    refusal; and a nested object under a registered key is stored, which is
    A-124's mechanism and not its whole rationale. Both boundaries are recorded
    by tests, not merely believed.
    """
    registered = registry.get(event.action)
    if registered is None:
        raise HistoryAppendRejected(RejectionReason.UNKNOWN_ACTION, action=event.action)

    unregistered = frozenset(event.details) - registered.detail_keys
    if unregistered:
        # min() for a DETERMINISTIC message, not for meaning.
        raise HistoryAppendRejected(
            RejectionReason.UNKNOWN_DETAIL_KEY,
            action=event.action,
            detail_key=min(unregistered),
        )

    # "   " satisfies NOT NULL and the CHECK and is not a reason.
    if registered.requires_reason and not (event.reason or "").strip():
        raise HistoryAppendRejected(RejectionReason.MISSING_REASON, action=event.action)


async def append(session: AsyncSession, event: HistoryEventDraft) -> str:
    """Validate ``event``, insert it on the CALLER's session, return the minted id.

    ``session`` must already be open with a tenant set. ``event.workspace_id`` is
    written as given and never compared to that tenant: the policy's
    ``WITH CHECK`` is the whole defence against a mis-stamped row (ADR-0040), and
    ``tests/security/test_history_tenant_isolation.py`` asserts it. Returning the
    id widens INT-006's ``-> void`` — OQ-035.
    """
    started = time.perf_counter()
    registry = registered_registry()
    check_event(event, registry)
    registered = registry[event.action]

    # python-ulid's StrictMonotonicPolicy raises ValueError on 2**80 ids in one
    # millisecond. The only ValueError this path can originate.
    event_id = f"{EVENT_ID_PREFIX}{ULID()}"

    try:
        await session.execute(
            INSERT_HISTORY_EVENT,
            {
                "id": event_id,
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
    except Exception:
        write_failed_total.inc()
        raise

    append_total.labels(action=event.action, writing_module=registered.writing_module).inc()
    if event.target_type not in NEVER_PROMPT_SCOPED_TARGET_TYPES and event.scope_prompt_id is None:
        null_scope_prompt_total.labels(action=event.action).inc()
    append_duration_seconds.observe(time.perf_counter() - started)

    # `reason` and `details` are absent permanently — A-046.
    log.info(
        "property_history.event_appended",
        event_id=event_id,
        action=event.action,
        target_type=event.target_type,
        target_id=event.target_id,
        scope_prompt_id=event.scope_prompt_id,
        actor_id=event.actor_id,
        workspace_id=event.workspace_id,
    )
    return event_id
