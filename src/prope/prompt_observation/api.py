"""INT-035 — seven operations over four paths, and no read that skips INT-002.

**Every route asks the same question**: ``may(actor, 'prompt.read', subject)``
where the subject carries the observation's ``namespace`` (SR-1). One action, one
attribute, no rule of this module's own. An actor sees an observation exactly
when they would see a prompt in the same folder — by a ``namespace_grant``, or by
a role binding that grants ``prompt.read`` workspace-wide.

That includes the four writes, and it is deliberate rather than lax. Adopting,
dismissing, redacting and deleting are acts on an **inventory**; none of them
writes a prompt, a revision or a release. ``POST .../adopted`` records that
prompt-registry created something, through prompt-registry's own routes, under
prompt-registry's own permissions — this module cannot create a prompt and that
is what keeps non-negotiable #1 out of its hands entirely.

**The refusal shape is not-found, everywhere, with no forbidden branch** (A-116),
and that is a genuine difference from ``prompt_registry.api``. There, a second
``may()`` on the deny path buys the difference between *no such prompt* and *you
need prompt.retire*, because the actor can see the prompt and is missing a
narrower permission. Here there is only one action: an actor who fails it cannot
see the observation at all, so there is nothing a 403 could tell them that a 404
does not — except that the observation exists, which is the disclosure the shape
exists to close.

**The subject's type is `PROMPT`, and it has no `owner_id` and no
`access_level`.** An observation has neither; ADR-0061 replaced that hole with a
namespace. The type is `PROMPT` because `may()` consults the grant tables only
for that type, and a namespace grant is what has to be reachable.
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import (
    Actor,
    ActorType,
    Subject,
    SubjectType,
    may,
    visible_subject_filter,
)
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.prompt_observation import repository
from prope.prompt_observation.domain import ObservationRow, ObservationStatus
from prope.prompt_observation.schemas import (
    EXCERPT_LENGTH,
    AdoptionProposalRead,
    ObservationAdopt,
    ObservationDetailRead,
    ObservationDismiss,
    ObservationRead,
    SightingRead,
)
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")

OBSERVATION_ID = Annotated[str, Path(min_length=1, max_length=64)]


def _not_found() -> ManagementRefusal:
    """The only refusal in this module, and every path that refuses uses it.

    An observation in a namespace the actor cannot see and an id that never
    existed answer **the same bytes**. Written once so the two cannot drift into
    distinguishability.
    """
    return ManagementRefusal(
        status_code=404, code=ErrorCode.NOT_FOUND, message="no such observation"
    )


def _conflict(message: str) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409, code=ErrorCode.VALIDATION_FAILED, message=message
    )


def _actor(session: Session) -> Actor:
    return Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id)


def _subject(row: ObservationRow) -> Subject:
    """ADR-0020's contract as a call, with ADR-0061's field carrying the answer."""
    return Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        namespace=row.namespace,
    )


async def _visible(db: AsyncSession, session: Session, observation_id: str) -> ObservationRow:
    """Load, authorise, return — in that order, and nothing leaves before ``may()``.

    The row is read first because ``may()`` needs its namespace (ADR-0020) and
    the row is where the namespace is. Reading before authorising is not a leak:
    nothing reaches a caller between the read and the answer.
    """
    row = await repository.load_observation(db, session.workspace_id, observation_id)
    if row is None:
        raise _not_found()
    if not await may(db, _actor(session), Action.PROMPT_READ, _subject(row)):
        raise _not_found()
    return row


def _read(row: ObservationRow) -> ObservationRead:
    return ObservationRead(
        observation_id=row.id,
        namespace=row.namespace,
        body_excerpt=row.current_body[:EXCERPT_LENGTH],
        inferred_variables=list(row.inferred_variables),
        sighting_count=row.sighting_count,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        upstream_models=list(row.upstream_models),
        status=row.status.value,
        redacted=row.redacted,
        adopted_prompt_id=row.adopted_prompt_id,
        adopted_by=row.adopted_by,
        adopted_at=row.adopted_at,
        dismissed_by=row.dismissed_by,
        dismissed_at=row.dismissed_at,
        dismissal_reason=row.dismissal_reason,
    )


@router.get(
    "/observations",
    response_model=list[ObservationRead],
    dependencies=[Depends(declares_action(ManagementAction.OBSERVATION_LIST))],
)
async def list_observations(
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    status: Annotated[ObservationStatus | None, Query()] = None,
    namespace: Annotated[str | None, Query(max_length=63)] = None,
    limit: Annotated[int, Query(ge=1, le=repository.MAX_LIMIT)] = repository.DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ObservationRead]:
    """The discovery inbox, permission-filtered in the repository (A-118, T-019).

    There is **no** per-row ``may()`` loop after the query and there must not be
    one, for prompt-registry's reason: the alternative to fifty checks per page
    is not fifty checks, it is the unfiltered query somebody writes when fifty
    checks look expensive.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)
        rows = await repository.list_observations(
            db,
            session.workspace_id,
            visible,
            status=status,
            namespace=namespace,
            limit=limit,
            offset=offset,
        )

    return [_read(row) for row in rows]


@router.get(
    "/observations/{observation_id}",
    response_model=ObservationDetailRead,
    dependencies=[Depends(declares_action(ManagementAction.OBSERVATION_READ))],
)
async def read_observation(
    session: Annotated[Session, Depends(require_session)],
    observation_id: OBSERVATION_ID,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ObservationDetailRead:
    """One group: the current body, and every occurrence behind it.

    The drift view is the governance value that arrives before any migration —
    *this body changed on Tuesday and nobody reviewed it* is a true and useful
    sentence about a prompt Prope does not manage.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _visible(db, session, observation_id)
        sightings = await repository.list_sightings(db, session.workspace_id, row.id)

    return ObservationDetailRead(
        **_read(row).model_dump(),
        current_body=row.current_body,
        sightings=[
            SightingRead(
                sighting_id=sighting.id,
                body=sighting.body,
                call_id=sighting.call_id,
                consumer_key_id=sighting.consumer_key_id,
                upstream_model=sighting.upstream_model,
                occurred_at=sighting.occurred_at,
            )
            for sighting in sightings
        ],
    )


@router.post(
    "/observations/{observation_id}/proposal",
    response_model=AdoptionProposalRead,
    dependencies=[Depends(declares_action(ManagementAction.OBSERVATION_PROPOSAL))],
)
async def propose(
    session: Annotated[Session, Depends(require_session)],
    observation_id: OBSERVATION_ID,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> AdoptionProposalRead:
    """A canonical body with its slots cut, and a suggested name. **Writes no prompt.**

    A ``POST`` for a route that creates nothing, because it computes a diff over
    the group's stored bodies and caches the result — it is not safe to retry
    blindly as a ``GET`` implies, and a client that prefetched it on hover would
    be running the diff on every row it passed under the cursor.

    The client posts what comes back to prompt-registry's create routes. That is
    prompt-conversion's rule — *conversion never saves a revision* — for
    prompt-conversion's reason: adoption must be an act somebody performed.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _visible(db, session, observation_id)
        if row.redacted:
            raise _conflict("this observation has been redacted and has no body to propose")
        proposal = await repository.propose_adoption(db, row)

    return AdoptionProposalRead(
        observation_id=proposal.observation_id,
        body=proposal.body,
        variables=list(proposal.variables),
        suggested_name=proposal.suggested_name,
    )


@router.post(
    "/observations/{observation_id}/adopted",
    response_model=ObservationRead,
    dependencies=[Depends(declares_action(ManagementAction.OBSERVATION_ADOPTED))],
)
async def mark_adopted(
    session: Annotated[Session, Depends(require_session)],
    observation_id: OBSERVATION_ID,
    payload: ObservationAdopt,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ObservationRead:
    """Record which prompt this group became. Idempotent, and **not** a create.

    ``prompt_id`` is a **value**, not a foreign key: A-049 makes retirement
    terminal and this module has no edge to prompt-registry's tables, so the id
    is stored as text on ``property_history.target_id``'s precedent. An id naming
    a prompt that was later retired still tells a person where to look.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _visible(db, session, observation_id)
        await repository.adopt(
            db,
            session.workspace_id,
            row.id,
            prompt_id=payload.prompt_id,
            actor_id=session.user_id,
        )
        updated = await repository.load_observation(db, session.workspace_id, row.id)

    log.info(
        "observation.adopted",
        observation_id=observation_id,
        workspace_id=session.workspace_id,
        prompt_id=payload.prompt_id,
    )
    return _read(updated or row)


@router.post(
    "/observations/{observation_id}/dismissed",
    response_model=ObservationRead,
    dependencies=[Depends(declares_action(ManagementAction.OBSERVATION_DISMISSED))],
)
async def mark_dismissed(
    session: Annotated[Session, Depends(require_session)],
    observation_id: OBSERVATION_ID,
    payload: ObservationDismiss,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ObservationRead:
    """*Somebody looked and this is not worth governing.* Reversible.

    Refuses a group that is already adopted, and the refusal comes from the
    statement's own ``WHERE`` rather than from a check before it — so two people
    acting at once cannot produce a row that is both adopted and dismissed.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _visible(db, session, observation_id)
        dismissed = await repository.dismiss(
            db,
            session.workspace_id,
            row.id,
            actor_id=session.user_id,
            reason=payload.reason,
        )
        if not dismissed:
            raise _conflict("this observation has already been adopted")
        updated = await repository.load_observation(db, session.workspace_id, row.id)

    return _read(updated or row)


@router.post(
    "/observations/{observation_id}/redacted",
    response_model=ObservationRead,
    dependencies=[Depends(declares_action(ManagementAction.OBSERVATION_REDACTED))],
)
async def mark_redacted(
    session: Annotated[Session, Depends(require_session)],
    observation_id: OBSERVATION_ID,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ObservationRead:
    """SR-4. Remove the text and keep the fact that there was text.

    The gentler of the two removals and the one the UI leads with: the counts,
    the dates and the models survive, so the inventory still says *there was
    something here*, and the group goes on counting even while the caller is
    still sending — the write path pins a redacted body rather than restoring it.

    This route exists from the first commit, **before** the retention policy that
    would eventually cover it, and that inversion is the point (SR-4). This is
    the first table in Prope holding customer text that arrived without anybody
    submitting it, and the answer to *take that one out* must not be a migration.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _visible(db, session, observation_id)
        await repository.redact(db, session.workspace_id, row.id)
        updated = await repository.load_observation(db, session.workspace_id, row.id)

    log.info(
        "observation.redacted",
        observation_id=observation_id,
        workspace_id=session.workspace_id,
    )
    return _read(updated or row)


@router.delete(
    "/observations/{observation_id}",
    status_code=204,
    dependencies=[Depends(declares_action(ManagementAction.OBSERVATION_DELETE))],
)
async def delete_observation(
    session: Annotated[Session, Depends(require_session)],
    observation_id: OBSERVATION_ID,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> None:
    """Remove the group and its sightings outright.

    **This is not the history delete the non-negotiables forbid.** History rows
    record what a person in Prope decided; an observation records what somebody
    else's code sent, and no decision of anybody's is lost with it. Nothing here
    touches ``history.history_event``, which remains undeletable at the database
    privilege level.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _visible(db, session, observation_id)
        await repository.delete_observation(db, session.workspace_id, row.id)

    log.info(
        "observation.deleted",
        observation_id=observation_id,
        workspace_id=session.workspace_id,
    )
