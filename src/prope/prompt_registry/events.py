"""The six history events this module writes, appended in the caller's transaction.

Five are seeded by revision 0005 with ``writing_module = 'prompt-registry'`` and
empty ``detail_keys``, so none of those five may attach ``details`` — ``append``
refuses an unregistered key, which is A-124's allow-list working as designed
rather than an obstacle to route around.

``usage_profile_changed`` is the sixth, seeded by revision 0031 with ADR-0067,
and it is the one that DOES carry details: its four registered keys are the four
axes, so an event can say WHICH declaration moved. It is written by
prompt-registry rather than by prompt-readiness because registry owns the column
— `prompt-readiness` reads the profile and never writes it, which is what keeps
``ck_history_action_registry_writing_module_values`` at nine modules instead of
ten.

**Every append stamps ``scope_prompt_id``** (A-119), including the two whose
``target_type`` is ``revision``-adjacent. That column is what makes
``GET /prompts/{id}/activity`` one indexed read over events written by four
modules against six target types, and this module may not join to any of their
tables to collect them.

``target_type`` is ``property`` for four of the five and ``revision`` for the
one about a revision — the pairing is closed by ``fk_history_event_action``, so
a mismatch here is a poisoned transaction rather than a named refusal. It is
written out per function rather than derived, because the registry is the
authority and a derivation would be this module's guess at it.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft

__all__ = [
    "access_level_changed",
    "owner_changed",
    "property_created",
    "retired",
    "revision_created",
    "usage_profile_changed",
]

PROPERTY_TARGET_TYPE = "property"

REVISION_TARGET_TYPE = "revision"


async def _append(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    prompt_id: str,
    occurred_at: datetime,
) -> str:
    return await append(
        db,
        HistoryEventDraft(
            workspace_id=workspace_id,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            scope_prompt_id=prompt_id,
            occurred_at=occurred_at,
        ),
    )


async def property_created(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="property_created",
        target_type=PROPERTY_TARGET_TYPE,
        target_id=prompt_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def revision_created(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    version_id: str,
    occurred_at: datetime,
) -> str:
    """The one event whose target is not the prompt itself.

    ``target_id`` is the revision, so ``READ_BY_TARGET`` answers *this
    revision's trail*; ``scope_prompt_id`` is the prompt, so the Activity screen
    still shows it. Both are needed and neither is derivable from the other.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="revision_created",
        target_type=REVISION_TARGET_TYPE,
        target_id=version_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def owner_changed(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    occurred_at: datetime,
) -> str:
    """A-051's *transfer is an explicit recorded action*, and this is the record.

    The new owner is deliberately not in ``details``: the registered
    ``detail_keys`` for this action are empty, and the prompt row already says
    who owns it now. What the event carries is that it happened, by whom, and when.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="owner_changed",
        target_type=PROPERTY_TARGET_TYPE,
        target_id=prompt_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def access_level_changed(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="access_level_changed",
        target_type=PROPERTY_TARGET_TYPE,
        target_id=prompt_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def retired(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    occurred_at: datetime,
) -> str:
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="retired",
        target_type=PROPERTY_TARGET_TYPE,
        target_id=prompt_id,
        prompt_id=prompt_id,
        occurred_at=occurred_at,
    )


async def usage_profile_changed(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    moved: Sequence[str],
    occurred_at: datetime,
) -> str:
    """ADR-0067. One event for the four axes, naming which of them actually moved.

    **One event and not four.** The axes are answered together on one screen, and
    four rows for one dropdown session would bury the owner change somebody is
    actually looking for in the same activity feed.

    ``details`` carries the axis NAMES and not their values. The names are the
    four registered ``detail_keys``, so A-124's allow-list admits them; the values
    are on the row, where a reader who wants them can see the current ones and a
    reader who wants the old ones has the previous event's timestamp to bound a
    search. Recording the values here would put a security-relevant declaration in
    two places that can disagree.
    """
    return await append(
        db,
        HistoryEventDraft(
            workspace_id=workspace_id,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            action="usage_profile_changed",
            target_type=PROPERTY_TARGET_TYPE,
            target_id=prompt_id,
            scope_prompt_id=prompt_id,
            occurred_at=occurred_at,
            details={axis: True for axis in moved},
        ),
    )
