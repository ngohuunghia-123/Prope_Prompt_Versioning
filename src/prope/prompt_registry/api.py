"""INT-024 — ten operations across seven paths, and no read that skips INT-002.

**Every refusal shape here is a security decision** (A-116). A prompt the actor
cannot see answers **not-found**, byte-identical to a prompt id that never
existed; a prompt they can see but may not act on answers **forbidden naming the
missing permission**. :func:`_visible_prompt` is the only place that choice is
made, so there is one implementation of it rather than ten.

**The permission subject carries the row's own attributes** (ADR-0020).
access-control may not read ``prompt_property`` and the reverse edge is a cycle,
so this module — which has just read the row it is about to act on — passes
``owner_id`` and ``access_level`` as parameters. That is why every handler loads
before it authorises, and why loading before authorising is not a leak: nothing
is returned until ``may()`` has answered.

**Four modules mount routes under ``/api/v1/prompts/{prompt_id}``** — this one,
access-control's grants, and evaluation and release-control later. No module owns
the prefix, no collision exists, and
``tests/architecture/test_route_table.py::test_the_assembled_table_has_no_
duplicate_operation`` is what keeps that true rather than the fact that nobody
has collided yet.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import (
    AccessLevel,
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
from prope.prompt_registry import commands, repository
from prope.prompt_registry.diff import compute_diff
from prope.prompt_registry.domain import (
    NothingToUpdate,
    PromptRow,
    PromptStatus,
    RevisionConflict,
    RevisionDraft,
)
from prope.prompt_registry.schemas import (
    ActivityEntryRead,
    DiffRead,
    FieldChangeRead,
    LineChangeRead,
    PromptCreate,
    PromptRead,
    PromptUpdate,
    RevisionCreate,
    RevisionRead,
    RevisionSummaryRead,
)
from prope.property_history.domain import PromptScope
from prope.property_history.read import read as read_history
from prope.provider_access.seams import get_model_catalogue
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _not_found() -> ManagementRefusal:
    """The one not-found in this module, and every path that refuses uses it.

    A prompt the actor may not see and a prompt id that does not exist answer
    **the same bytes**. Written once so the two cannot drift into
    distinguishability, which is the failure BR-01 is about: a ``403`` on a
    private prompt confirms the prompt exists.
    """
    return ManagementRefusal(
        status_code=404, code=ErrorCode.NOT_FOUND, message="no such prompt"
    )


def _forbidden(action: Action) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=403,
        code=ErrorCode.PERMISSION_DENIED,
        message=f"this action requires the {action.value} permission",
        details={"permission": action.value, "subject_type": SubjectType.PROMPT.value},
    )


def _actor(session: Session) -> Actor:
    return Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id)


def _subject(session: Session, row: PromptRow) -> Subject:
    """ADR-0020's contract as a call: the row's own attributes, passed in.

    ``access_level`` is parsed into access-control's own enum rather than passed
    as a string, so a value this module invented would raise here instead of
    silently failing every comparison inside ``may()`` — which would deny, and
    therefore look like a working permission check.
    """
    return Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
    )


async def _visible_prompt(
    db: AsyncSession, session: Session, action: Action, prompt_id: str
) -> PromptRow:
    """Load the prompt, authorise it, and refuse in whichever of A-116's two shapes fits.

    The order matters and is not negotiable: the row is read first because
    ``may()`` needs its owner and access level (ADR-0020), authorised second, and
    returned only third. Nothing reaches a caller between the read and the
    answer.

    The second ``may()`` call — for ``prompt.read`` — runs only on the deny path,
    and it is what decides between 404 and 403. It costs two indexed reads on a
    request that is already being refused, and it buys the difference between *no
    such prompt* and *you need prompt.retire*, which is the difference between a
    leak and a support conversation that ends.
    """
    row = await repository.load_prompt(db, prompt_id)
    if row is None:
        raise _not_found()

    actor = _actor(session)
    subject = _subject(session, row)

    if await may(db, actor, action, subject):
        return row

    if action is not Action.PROMPT_READ and await may(db, actor, Action.PROMPT_READ, subject):
        raise _forbidden(action)

    raise _not_found()


def _prompt_read(row: PromptRow) -> PromptRead:
    return PromptRead(
        prompt_id=row.id,
        model_name=row.model_name,
        namespace=row.namespace,
        name=row.name,
        title=row.title,
        purpose=row.purpose,
        owner_id=row.owner_id,
        access_level=row.access_level,
        status=row.status,
        tags=list(row.tags),
        released_version_id=row.released_version_id,
        released_at=row.released_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _revision_summary(row: Any) -> RevisionSummaryRead:
    return RevisionSummaryRead(
        version_id=row.version_id,
        prompt_id=row.prompt_id,
        revision_number=row.revision_number,
        change_summary=row.change_summary,
        author_id=row.author_id,
        status=row.status,
        provider_config_id=row.provider_config_id,
        upstream_model=row.upstream_model,
        created_at=row.created_at,
    )


def _revision_read(row: Any) -> RevisionRead:
    return RevisionRead(
        version_id=row.version_id,
        prompt_id=row.prompt_id,
        revision_number=row.revision_number,
        change_summary=row.change_summary,
        author_id=row.author_id,
        status=row.status,
        provider_config_id=row.provider_config_id,
        upstream_model=row.upstream_model,
        created_at=row.created_at,
        body=row.body,
        parameters=row.parameters,
        fallback_answer=row.fallback_answer,
    )


@router.post(
    "/prompts",
    response_model=PromptRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_CREATE))],
)
async def create_prompt(
    payload: PromptCreate,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> PromptRead:
    """Register a prompt property. There is no row yet, so there is no subject to read.

    The permission question is asked against the **workspace** rather than
    against a prompt, because ADR-0020's caller-supplies-the-attributes contract
    has nothing to supply for a row that does not exist. ``prompt.create`` is a
    role-granted permission for exactly that reason — no grant can confer it,
    since a grant is per prompt.

    ``owner_id`` defaults to the actor. An Admin may register on somebody's
    behalf by naming them, which is A-007; a non-Admin naming somebody else is
    refused by the ``prompt.transfer_owner`` check, because handing a prompt away
    at creation is the same act as handing one away later.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        actor = _actor(session)
        workspace = Subject(
            type=SubjectType.WORKSPACE, id=session.workspace_id, workspace_id=session.workspace_id
        )
        if not await may(db, actor, Action.PROMPT_CREATE, workspace):
            raise _forbidden(Action.PROMPT_CREATE)

        owner_id = payload.owner_id or session.user_id
        if owner_id != session.user_id and not await may(
            db, actor, Action.PROMPT_TRANSFER_OWNER, workspace
        ):
            raise _forbidden(Action.PROMPT_TRANSFER_OWNER)

        row = await commands.create_prompt(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            namespace=payload.namespace,
            name=payload.name,
            title=payload.title,
            purpose=payload.purpose,
            owner_id=owner_id,
            access_level=payload.access_level,
            tags=list(payload.tags),
            now=now,
        )

    return _prompt_read(row)


@router.get(
    "/prompts",
    response_model=list[PromptRead],
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_LIST))],
)
async def list_prompts(
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    owner_id: Annotated[str | None, Query()] = None,
    status: Annotated[PromptStatus | None, Query()] = None,
    access_level: Annotated[str | None, Query(pattern=r"^(private|workspace)$")] = None,
    tag: Annotated[str | None, Query(max_length=60)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=repository.MAX_LIMIT)] = repository.DEFAULT_LIMIT,
) -> list[PromptRead]:
    """List and search, permission-filtered in the repository (A-118, T-019).

    There is **no** per-row ``may()`` loop after the query and there must not be
    one: fifty permission checks per page is not the alternative this shape was
    chosen over — the alternative is the unfiltered query somebody writes when
    fifty checks look expensive.

    ``q`` is a substring match, which is the product requirement (A-013) and the
    reason ADR-0048 chose a trigram index over ``tsvector``. It matches the
    prompt's title, purpose, tags, model name, latest body and **every**
    revision's change summary.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)
        rows = await repository.list_prompts(
            db,
            actor_id=session.user_id,
            visible=visible,
            keyword=q,
            owner_id=owner_id,
            status=status,
            access_level=access_level,
            tag=tag,
            cursor=cursor,
            limit=limit,
        )

    return [_prompt_read(row) for row in rows]


@router.get(
    "/prompts/{prompt_id}",
    response_model=PromptRead,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_READ))],
)
async def read_prompt(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> PromptRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
    return _prompt_read(row)


@router.patch(
    "/prompts/{prompt_id}",
    response_model=PromptRead,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_UPDATE))],
)
async def update_prompt(
    payload: PromptUpdate,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> PromptRead:
    """Edit the mutable half. **Two fields need more than ``prompt.edit``.**

    Transferring ownership is an Admin act (A-007): an owner who could transfer
    could also launder a prompt out of a reviewer's sight, so
    ``prompt.transfer_owner`` is checked separately and is deliberately absent
    from ``OWNER_ACTIONS`` in access-control.

    Changing the access level is ``prompt.grant``. A-115 spells that permission
    ``prompt.grant`` where ``interfaces.md`` spells it ``prompt.change_access``;
    this follows A-115, which is what the seed and the ``CHECK`` are written
    from, and the discrepancy is ``OQ-133`` rather than a favourite being picked
    here.

    Both extra checks run **only when the field actually moves**. A PATCH that
    resends the current owner is an edit, not a transfer.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await _visible_prompt(db, session, Action.PROMPT_EDIT, prompt_id)
        actor = _actor(session)
        subject = _subject(session, row)

        if payload.owner_id is not None and payload.owner_id != row.owner_id:
            if not await may(db, actor, Action.PROMPT_TRANSFER_OWNER, subject):
                raise _forbidden(Action.PROMPT_TRANSFER_OWNER)

        if payload.access_level is not None and payload.access_level != row.access_level:
            if not await may(db, actor, Action.PROMPT_GRANT, subject):
                raise _forbidden(Action.PROMPT_GRANT)

        try:
            updated = await commands.update_prompt(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                title=payload.title,
                purpose=payload.purpose,
                owner_id=payload.owner_id,
                access_level=payload.access_level,
                tags=None if payload.tags is None else list(payload.tags),
                now=now,
            )
        except NothingToUpdate as error:
            raise _not_found() from error

    return _prompt_read(updated)


@router.post(
    "/prompts/{prompt_id}/retire",
    response_model=PromptRead,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_RETIRE))],
)
async def retire_prompt(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> PromptRead:
    """A-052. Refused while a release is active, with the release named in ``details``.

    A ``POST`` rather than a ``DELETE`` because nothing is deleted: ``Retired`` is
    a terminal status and every revision survives it (A-049). A ``DELETE`` verb
    would describe an operation this product does not offer and cannot offer.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_RETIRE, prompt_id)
        try:
            row = await commands.retire_prompt(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                now=now,
            )
        except NothingToUpdate as error:
            raise _not_found() from error

    return _prompt_read(row)


@router.get(
    "/prompts/{prompt_id}/revisions",
    response_model=list[RevisionSummaryRead],
    dependencies=[Depends(declares_action(ManagementAction.REVISION_LIST))],
)
async def list_revisions(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    cursor: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=repository.MAX_LIMIT)] = repository.DEFAULT_LIMIT,
) -> list[RevisionSummaryRead]:
    """The revision chain, newest first, **without bodies**.

    Permission is decided once, on the parent prompt, and the revisions inherit
    it. A revision is not a separately grantable subject — ``SubjectType`` has a
    ``REVISION`` member and ``prompt_grant`` has no row that could carry one,
    which is deliberate: a grant on one revision of a prompt would be a promise
    the immutable chain cannot keep.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        rows = await repository.list_revisions(db, prompt_id, cursor=cursor, limit=limit)

    return [_revision_summary(row) for row in rows]


@router.post(
    "/prompts/{prompt_id}/revisions",
    response_model=RevisionRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.REVISION_CREATE))],
)
async def create_revision(
    payload: RevisionCreate,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> RevisionRead:
    """A-002's next immutable revision, with its history event in the same transaction.

    **INT-016 is consulted and never obeyed** (A-091). The catalogue is discovered
    from the provider's own list and allows manual entries precisely because
    provider endpoints omit models, so treating it as authoritative would block a
    legitimate revision on a third party's incomplete API. A binding outside the
    catalogue is logged and saved; a binding naming a configuration that does not
    exist is refused, which is a different failure — a broken reference rather
    than a stale list.

    Every revision starts ``Draft``. Only INT-012 moves it, and only
    release-control issues INT-012.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.REVISION_CREATE, prompt_id)

        if payload.provider_config_id is not None and payload.upstream_model is not None:
            await _warn_if_outside_catalogue(
                db, payload.provider_config_id, payload.upstream_model
            )

        try:
            created = await commands.create_revision(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                draft=RevisionDraft(
                    body=payload.body,
                    change_summary=payload.change_summary,
                    provider_config_id=payload.provider_config_id,
                    upstream_model=payload.upstream_model,
                    fallback_answer=payload.fallback_answer,
                    parameters=dict(payload.parameters),
                ),
                now=now,
            )
        except RevisionConflict as conflict:
            raise ManagementRefusal(
                status_code=409,
                code=ErrorCode.REGISTRY_REVISION_CONFLICT,
                message="somebody else saved a revision of this prompt first",
                details={"revision_number": conflict.revision_number},
            ) from conflict

    return _revision_read(created)


async def _warn_if_outside_catalogue(
    db: AsyncSession, provider_config_id: str, upstream_model: str
) -> None:
    """INT-016's soft read. It logs and it never refuses.

    An empty catalogue is not evidence of anything — a configuration whose last
    refresh failed has one, and so does a brand-new one — so the check runs only
    when the catalogue has entries to check against. What it buys is a line an
    operator can find later, when ``ProviderModelUnavailable`` pages and somebody
    asks how long that binding has been wrong.
    """
    entries = await get_model_catalogue(db, provider_config_id)
    if entries and not any(entry.model_id == upstream_model for entry in entries):
        log.info(
            "prompt_registry.binding_outside_catalogue",
            provider_config_id=provider_config_id,
            upstream_model=upstream_model,
        )


@router.get(
    "/revisions/{version_id}",
    response_model=RevisionRead,
    dependencies=[Depends(declares_action(ManagementAction.REVISION_READ))],
)
async def read_revision(
    version_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> RevisionRead:
    """One revision in full. The permission lives on its prompt, not on it.

    The revision is read first because it is the only thing that knows which
    prompt to authorise against — and it is discarded unread if that prompt
    refuses. A revision id the actor may not see answers the same not-found as
    one that does not exist, which is why the refusal is
    :func:`_visible_prompt`'s rather than a second shape written here.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await repository.load_revision(db, version_id)
        if row is None:
            raise _not_found()
        await _visible_prompt(db, session, Action.PROMPT_READ, row.prompt_id)

    return _revision_read(row)


@router.get(
    "/prompts/{prompt_id}/diff",
    response_model=DiffRead,
    dependencies=[Depends(declares_action(ManagementAction.DIFF_READ))],
)
async def read_diff(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    from_version_id: Annotated[str, Query(alias="from")],
    to_version_id: Annotated[str, Query(alias="to")],
) -> DiffRead:
    """A-015's diff, computed here and never stored (A-047).

    Both revisions must belong to the prompt in the path. That is not
    bookkeeping: without it, a caller with permission on one prompt could diff
    two revisions of another and read both bodies out of the response.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        before = await repository.load_revision(db, from_version_id)
        after = await repository.load_revision(db, to_version_id)

    if before is None or after is None:
        raise _not_found()
    if before.prompt_id != prompt_id or after.prompt_id != prompt_id:
        raise _not_found()

    result = compute_diff(before, after)

    return DiffRead(
        prompt_id=prompt_id,
        from_version_id=result.from_version_id,
        to_version_id=result.to_version_id,
        lines=[
            LineChangeRead(
                op=line.op, text=line.text, from_line=line.from_line, to_line=line.to_line
            )
            for line in result.lines
        ],
        fields=[
            FieldChangeRead(
                field=change.field,
                before=change.before,
                after=change.after,
                changed=change.changed,
            )
            for change in result.fields
        ],
    )


@router.get(
    "/prompts/{prompt_id}/activity",
    response_model=list[ActivityEntryRead],
    dependencies=[Depends(declares_action(ManagementAction.ACTIVITY_READ))],
)
async def read_activity(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=repository.MAX_LIMIT)] = repository.DEFAULT_LIMIT,
) -> list[ActivityEntryRead]:
    """A-044's Activity: every event scoped to this prompt, from four modules.

    Revisions, submissions, approvals, releases, restores, suite edits and grants
    all appear, written by four modules against six target types — and this
    module may not join to any of their tables to collect them. What makes it one
    indexed read is ``scope_prompt_id``, stamped at append by every writer
    (A-119), on ``ix_history_event_workspace_id_scope_prompt_id_seq``.

    **This module checks permission and property-history checks none.** That is
    the whole of A-044's cycle break: property-history has no outbound edge, no
    actor parameter and no way to grow one, so the check has to happen here or
    nowhere.

    Ordered by ``seq`` and never by timestamp — approve-and-release writes two
    events with the same instant (A-125), and a timestamp sort mis-orders exactly
    the pair that matters most.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        events = await read_history(
            db,
            PromptScope(workspace_id=session.workspace_id, scope_prompt_id=prompt_id),
            cursor=cursor,
            limit=limit,
        )

    return [
        ActivityEntryRead(
            event_id=event.id,
            seq=event.seq,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            actor_type=str(event.actor_type),
            actor_id=event.actor_id,
            reason=event.reason,
            details=dict(event.details),
            occurred_at=event.occurred_at,
        )
        for event in events
    ]
