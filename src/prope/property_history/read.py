"""INT-007's Activity read: one prompt's decision trail, newest ``seq`` first.

**No permission check, and no way to make one** — no actor parameter, and no
import of another Prope module (A-044), asserted by an import walk in
``tests/architecture/test_property_history_depends_on_nothing.py``. RLS is the
backstop (ADR-0045), not the control.

**Ordered by ``seq``, never by ``occurred_at``** (A-125, ADR-0024): A-076 writes
two events with one timestamp in one transaction, so a timestamp sort mis-orders
the case that matters most. **Descending**, because assignment order is not
commit order — an ascending ``seq > N`` poll skips a late-committing lower ``seq``
permanently. ``tests/integration/test_history_read_is_ordered_by_seq_not_time.py``
asserts both.
"""

from typing import Any

from sqlalchemy import TextClause, text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.property_history.domain import (
    ActorScope,
    ActorType,
    HistoryCursorUnknown,
    HistoryEvent,
    HistoryScopeMismatch,
    PromptScope,
    Scope,
    TargetScope,
)

#: Written for ``ix_history_event_workspace_id_scope_prompt_id_seq``
#: ``(workspace_id, scope_prompt_id, seq DESC)`` — predicate order and sort
#: direction match the index rather than happening to (A-119). ``workspace_id`` is
#: here alongside the tenant policy, never instead of it (``PRICE_ROWS``' posture).
#:
#: ``before_seq`` switches its own disjunct off when NULL, so one statement serves
#: page one and a cursored page; this phase always passes ``None`` and plan 05-02
#: widens the call. Without the ``CAST`` asyncpg has no type to infer for a NULL
#: parameter — ``api.py`` records the identical reasoning.
READ_BY_PROMPT = text(
    """
    SELECT seq, id, workspace_id, actor_type, actor_id, action, target_type,
           target_id, scope_prompt_id, reason, details, occurred_at
    FROM   history.history_event
    WHERE  workspace_id = :workspace_id
      AND  scope_prompt_id = :scope_prompt_id
      AND  (CAST(:before_seq AS bigint) IS NULL OR seq < CAST(:before_seq AS bigint))
    ORDER  BY seq DESC
    LIMIT  :limit
    """
)

#: Written for ``ix_history_event_workspace_id_target_type_target_id_seq``
#: ``(workspace_id, target_type, target_id, seq DESC)`` — one subject's trail.
READ_BY_TARGET = text(
    """
    SELECT seq, id, workspace_id, actor_type, actor_id, action, target_type,
           target_id, scope_prompt_id, reason, details, occurred_at
    FROM   history.history_event
    WHERE  workspace_id = :workspace_id
      AND  target_type = :target_type
      AND  target_id = :target_id
      AND  (CAST(:before_seq AS bigint) IS NULL OR seq < CAST(:before_seq AS bigint))
    ORDER  BY seq DESC
    LIMIT  :limit
    """
)

#: Written for ``ix_history_event_workspace_id_actor_id_seq``
#: ``(workspace_id, actor_id, seq DESC)`` — one person's actions.
#:
#: ``actor_id`` is a value and not a foreign key (A-122), so a person removed
#: from the workspace still matches every event they caused and nothing cascades.
#: That is why ADR-0054's tombstone cost this module nothing, and it is what
#: makes AC-9 answerable.
READ_BY_ACTOR = text(
    """
    SELECT seq, id, workspace_id, actor_type, actor_id, action, target_type,
           target_id, scope_prompt_id, reason, details, occurred_at
    FROM   history.history_event
    WHERE  workspace_id = :workspace_id
      AND  actor_id = :actor_id
      AND  (CAST(:before_seq AS bigint) IS NULL OR seq < CAST(:before_seq AS bigint))
    ORDER  BY seq DESC
    LIMIT  :limit
    """
)

#: D-71: the cursor is an opaque event ``id``, never a ``seq`` — ``seq`` is one
#: global identity sequence, so a decimal cursor in a URL is a cross-tenant
#: volume oracle on a table that never shrinks. The ``workspace_id`` term makes a
#: cursor non-portable across tenants; that is a containment, not an
#: optimisation.
#:
#: WHY its own round trip rather than a scalar subquery in the page statement:
#: ``seq < (SELECT …)`` on an unknown id compares against NULL and returns zero
#: rows silently — a page that reads as *the trail ended here*.
RESOLVE_CURSOR = text(
    """
    SELECT seq
    FROM   history.history_event
    WHERE  id = :cursor
      AND  workspace_id = :workspace_id
    """
)

#: D-72's diagnosis, and it runs ONLY on the empty path (see :func:`read`). The
#: second argument is ``missing_ok``: without it an unset GUC raises inside the
#: statement and the caller meets a driver error instead of this module's named
#: refusal. It is NOT the same ``true`` as the third argument ``session.py``
#: binds the setting with, which is what makes that setting transaction-local.
TENANT_IN_FORCE = text("SELECT current_setting('app.workspace_id', true)")

#: A-045, and the lock's ``p95 < 50 ms`` condition names the same number.
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _event(row: Any) -> HistoryEvent:
    # WHY no json.loads: the asyncpg dialect installs a jsonb decode codec on
    # connect, so `details` arrives as a dict even from a raw statement. Verified.
    return HistoryEvent(
        seq=row["seq"],
        id=row["id"],
        workspace_id=row["workspace_id"],
        actor_type=ActorType(row["actor_type"]),
        actor_id=row["actor_id"],
        action=row["action"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        scope_prompt_id=row["scope_prompt_id"],
        reason=row["reason"],
        details=row["details"],
        occurred_at=row["occurred_at"],
    )


def _statement_for(scope: Scope) -> tuple[TextClause, dict[str, Any]]:
    match scope:
        case PromptScope():
            return READ_BY_PROMPT, {
                "workspace_id": scope.workspace_id,
                "scope_prompt_id": scope.scope_prompt_id,
            }
        case TargetScope():
            return READ_BY_TARGET, {
                "workspace_id": scope.workspace_id,
                "target_type": scope.target_type,
                "target_id": scope.target_id,
            }
        case ActorScope():
            return READ_BY_ACTOR, {
                "workspace_id": scope.workspace_id,
                "actor_id": scope.actor_id,
            }
        case _:
            # Not defensive noise: `Scope` is closed, so a fourth shape is a new
            # declared read. A dict or a half-built scope meets this instead of
            # a full-workspace scan.
            raise TypeError(
                f"{type(scope).__name__} is not one of INT-007's three declared scope shapes "
                "(PromptScope, TargetScope, ActorScope)"
            )


async def read(
    session: AsyncSession,
    scope: Scope,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[HistoryEvent, ...]:
    """One scope's events, newest ``seq`` first, on the CALLER's session.

    ``session`` must be one the caller has already opened and set a tenant on;
    a session without one raises :class:`HistoryScopeMismatch` rather than
    reading as an empty trail. ``cursor`` is the ``id`` of the last event on the
    previous page, and the caller derives the next one exactly as
    ``call_ledger/api.py:528`` does — ``events[-1].id if len(events) == limit
    else None``. A page that comes back exactly full over an exactly-full corpus
    yields a cursor whose next page is empty; correct, cheap, and what the
    prices endpoint already does.

    ``cursor`` and ``limit`` are keyword-only because the lock spells the
    parameters ``read(scope, cursor, limit)`` and both
    ``read(session, scope, 50, None)`` and ``read(session, scope, None, 50)``
    look plausible while one of them is silently wrong.
    """
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(
            f"limit={limit} is outside A-045's bound of 1..{MAX_LIMIT}; a page of zero is a "
            "caller bug that would render an empty Activity, and a page above the cap is how one "
            "screen turns a 50,000-event workspace into one response"
        )

    statement, parameters = _statement_for(scope)

    # Resolved FIRST: a bad cursor and a mismatched tenant are different mistakes
    # with different fixes, and the cursor is what the caller supplied most recently.
    before_seq: int | None = None
    if cursor is not None:
        before_seq = (
            await session.execute(
                RESOLVE_CURSOR, {"cursor": cursor, "workspace_id": scope.workspace_id}
            )
        ).scalar_one_or_none()
        if before_seq is None:
            raise HistoryCursorUnknown(cursor, scope.workspace_id)

    rows = (
        (await session.execute(statement, {**parameters, "before_seq": before_seq, "limit": limit}))
        .mappings()
        .all()
    )
    # A returned row proves the tenant matched — the policy would not have let it
    # through otherwise — so a populated read pays nothing for D-72's diagnosis.
    if rows:
        return tuple(_event(row) for row in rows)

    in_force = (await session.execute(TENANT_IN_FORCE)).scalar_one_or_none()
    # WHY both: a never-set GUC reads NULL on a pristine connection and '' on a
    # reused one (tests/security/test_tenant_isolation.py asserts both routes).
    if not in_force:
        raise HistoryScopeMismatch(scope.workspace_id, None)
    if in_force != scope.workspace_id:
        raise HistoryScopeMismatch(scope.workspace_id, in_force)
    return ()
