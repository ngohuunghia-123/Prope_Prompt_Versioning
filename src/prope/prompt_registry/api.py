"""INT-024's operations plus the four folder ones, and no read that skips INT-002.

**Folders are not in INT-024 and are not a ninth module.** A folder is
``prompt_property.namespace`` with a display label beside it, so the routes mount
here — this is the module that owns the column. They are grouped together under
their own banner below, with the reasoning for their permission and their refusal
shapes at that banner rather than up here, because none of the rules in this
docstring is about them: they touch no prompt, no revision and no release.


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

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import (
    AccessLevel,
    Actor,
    ActorType,
    Subject,
    SubjectType,
    key_labels,
    may,
    visible_subject_filter,
)
from prope.call_ledger.seams import (
    CALL_RECORD_MAX_LIMIT,
    CALL_RECORD_PAGE_LIMIT,
    CONVERSATION_MAX_LIMIT,
    CONVERSATION_NODE_CAP,
    CONVERSATION_PAGE_LIMIT,
    CallRecordListing,
    ConversationCall,
    ConversationListing,
    # The ledger's own vocabulary, re-exported by the one surface this module may
    # import from it (ADR-0055). Restating the values here as a local `Literal`
    # would be a second copy of `ck_call_record_source_values` that nothing keeps
    # in step with the first.
    Outcome,
    Source,
    UsageBucket,
    aggregate_prompt_usage,
    check_spend_ceiling,
    list_prompt_call_records,
    _read_prompt_call_content,
    read_prompt_call_record,
    list_prompt_conversations,
    read_conversation_calls,
)
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.prompt_composition import (
    MissingVariable,
    OversizeRequest,
    UnfilledPlaceholder,
    compose,
    render,
)
from prope.prompt_registry import commands, events, repository
from prope.prompt_registry.diff import compute_diff
from prope.prompt_registry.domain import (
    FolderNotEmpty,
    FolderRow,
    FolderSlugTaken,
    NothingToUpdate,
    PromptRow,
    PromptStatus,
    RevisionConflict,
    RevisionDraft,
)
from prope.prompt_registry.schemas import (
    CONVERSATION_ID_PATTERN,
    NAME_PATTERN,
    USAGE_WINDOW_SPANS,
    ActivityEntryRead,
    CallRecordRead,
    CallObservabilityRead,
    ConversationGraphRead,
    ConversationNodeRead,
    ConversationSummaryRead,
    DiffRead,
    FieldChangeRead,
    FolderCreate,
    FolderRead,
    FolderUpdate,
    LineChangeRead,
    PromptCreate,
    PromptRead,
    PromptUpdate,
    PromptUsageRead,
    RevisionCreate,
    RevisionRead,
    RevisionSummaryRead,
    RevisionTagsUpdate,
    TrialParameters,
    TrialRequest,
    UsageBucketRead,
    UsageCostRead,
    UsageWindow,
    ObservabilityRequestRead,
    ObservabilitySpanRead,
)
from prope.prompt_registry.observability import redacted_messages
from prope.prompt_registry.trial import stream_trial
from prope.prompt_search.seams import enqueue_index_job
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
        tags=list(row.tags),
        author_id=row.author_id,
        author_email=row.author_email,
        status=row.status,
        provider_config_id=row.provider_config_id,
        upstream_model=row.upstream_model,
        created_at=row.created_at,
    )


def _call_record_read(record: CallRecordListing, labels: Mapping[str, str]) -> CallRecordRead:
    """Every field named, like every other mapper in this module.

    **Not ``CallRecordRead(**vars(record))``, and not ``from_attributes``.** This
    file's own rule is T-017's: models list their fields rather than reading them
    off a row, because a mapper that copies whatever it is handed is a mapper that
    will one day copy a column somebody added upstream. Here that column would be
    a body — the one thing ADR-0018 says must never cross — so the spelled-out
    form is the boundary rather than a style choice.
    """
    return CallRecordRead(
        call_id=record.call_id,
        source=record.source,
        version_id=record.version_id,
        revision_number=record.revision_number,
        consumer_key_id=record.consumer_key_id,
        consumer_label=None
        if record.consumer_key_id is None
        else labels.get(record.consumer_key_id),
        provider_config_id=record.provider_config_id,
        upstream_model=record.upstream_model,
        outcome=record.outcome,
        pinned=record.pinned,
        fallback=record.fallback,
        streaming=record.streaming,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        usage_status=record.usage_status,
        cost=record.cost,
        currency=record.currency,
        cost_status=record.cost_status,
        added_latency_ms=record.added_latency_ms,
        upstream_duration_ms=record.upstream_duration_ms,
        error_class=record.error_class,
        created_at=record.created_at,
    )


def _usage_bucket_read(bucket: UsageBucket, labels: Mapping[str, str]) -> UsageBucketRead:
    """Every field named, for the same reason ``_call_record_read`` is.

    ``labels.get`` rather than ``labels[...]``: a key can be missing from the
    lookup — a row removed, or an id from a workspace this reader cannot see —
    and a ``KeyError`` there would fail the whole tab over one unnameable
    integration. Null tells the client to fall back to the id.
    """
    return UsageBucketRead(
        consumer_key_id=bucket.consumer_key_id,
        label=None if bucket.consumer_key_id is None else labels.get(bucket.consumer_key_id),
        requests=bucket.requests,
        input_tokens=bucket.input_tokens,
        output_tokens=bucket.output_tokens,
        cost=[
            UsageCostRead(currency=currency, amount=amount) for currency, amount in bucket.cost
        ],
        unpriced_count=bucket.unpriced_count,
        error_count=bucket.error_count,
        fallback_count=bucket.fallback_count,
        last_called_at=bucket.last_called_at,
    )


def _revision_read(row: Any) -> RevisionRead:
    return RevisionRead(
        version_id=row.version_id,
        prompt_id=row.prompt_id,
        revision_number=row.revision_number,
        change_summary=row.change_summary,
        tags=list(row.tags),
        author_id=row.author_id,
        author_email=row.author_email,
        status=row.status,
        provider_config_id=row.provider_config_id,
        upstream_model=row.upstream_model,
        created_at=row.created_at,
        body=row.body,
        original_body=row.original_body,
        original_format=row.original_format,
        original_filename=row.original_filename,
        conversion_model=row.conversion_model,
        conversion_schema_version=row.conversion_schema_version,
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

        name, title = payload.name, payload.title
        if payload.auto_name:
            name, title = await commands.next_untitled_prompt(
                db, workspace_id=session.workspace_id, namespace=payload.namespace
            )
        row = await commands.create_prompt(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            namespace=payload.namespace,
            name=name,
            title=title,
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


# --- folders -----------------------------------------------------------------
#
# Four operations over two paths. A folder is a namespace with a label on it, so
# these mount here rather than anywhere else: `namespace` is a column of
# `prompt_property` and this is the module that owns it.
#
# **None of these refuses as not-found, and that is not an oversight.** A-116's
# not-found shape protects a *prompt* the actor may not see (BR-01). A folder
# discloses nothing of the kind: its very existence is already visible to anyone
# who may list prompts, its counts run through `visible_subject_filter`, and a
# slug that names nothing and a slug that names an empty folder are the same
# thing. `PATCH` on an unknown slug therefore creates rather than refuses, and
# `DELETE` on one succeeds silently.


def _forbidden_workspace(action: Action) -> ManagementRefusal:
    """``_forbidden`` for the routes whose subject is the workspace, not a prompt.

    The two differ only in ``details.subject_type``, and they are separate
    functions rather than one with a parameter because the prompt-shaped one is
    the security-sensitive default: every path that could leak a prompt's
    existence should reach for the function that says ``prompt``.
    """
    return ManagementRefusal(
        status_code=403,
        code=ErrorCode.PERMISSION_DENIED,
        message=f"this action requires the {action.value} permission",
        details={"permission": action.value, "subject_type": SubjectType.WORKSPACE.value},
    )


def _workspace(session: Session) -> Subject:
    return Subject(
        type=SubjectType.WORKSPACE, id=session.workspace_id, workspace_id=session.workspace_id
    )


async def _may_organise(db: AsyncSession, session: Session) -> None:
    """The one permission every folder write asks for. See ``ROUTE_ACTION``."""
    if not await may(db, _actor(session), Action.PROMPT_CREATE, _workspace(session)):
        raise _forbidden_workspace(Action.PROMPT_CREATE)


def _slug_taken(slug: str) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.REGISTRY_FOLDER_SLUG_TAKEN,
        message="that folder name is already in use in this workspace",
        details={"slug": slug},
    )


def _folder_not_empty(slug: str, prompt_count: int) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.REGISTRY_FOLDER_NOT_EMPTY,
        message="the folder still holds prompts",
        details={"slug": slug, "prompt_count": prompt_count},
    )


def _folder_read(row: FolderRow) -> FolderRead:
    return FolderRead(
        slug=row.slug,
        name=row.name,
        description=row.description,
        color=row.color,
        declared=row.declared,
        prompt_count=row.prompt_count,
        approved_count=row.approved_count,
        in_review_count=row.in_review_count,
        draft_count=row.draft_count,
        updated_at=row.updated_at,
    )


Slug = Annotated[str, Path(pattern=NAME_PATTERN)]


@router.get(
    "/folders",
    response_model=list[FolderRead],
    dependencies=[Depends(declares_action(ManagementAction.FOLDER_LIST))],
)
async def list_folders(
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[FolderRead]:
    """Every folder in the workspace: declared rows and observed namespaces alike.

    **No cursor, and no ``limit``.** A folder list is a wall of cards a person
    scans, and the number of namespaces in a workspace is bounded by how many
    drawers a team can hold in its head — not by how many prompts they have
    written. Paging it would mean the grid could omit the folder somebody just
    created, which is the one thing this endpoint exists to prevent.

    The counts come out of SQL rather than out of a page of prompts, which is
    what fixes them: deriving them client-side capped every count at whatever
    ``GET /prompts`` happened to return.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)
        rows = await repository.list_folders(db, actor_id=session.user_id, visible=visible)

    return [_folder_read(row) for row in rows]


@router.post(
    "/folders",
    response_model=FolderRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.FOLDER_CREATE))],
)
async def create_folder(
    payload: FolderCreate,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> FolderRead:
    """Declare a namespace so it can be opened before it holds anything.

    Refuses ``registry_folder_slug_taken`` when the slug is claimed by a folder
    row **or** by any prompt's namespace — one refusal, because to the person
    typing they are one fact. Renaming that existing folder is ``PATCH``.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _may_organise(db, session)
        slug, name = payload.slug, payload.name
        if payload.auto_name:
            slug, name = await commands.next_untitled_folder(
                db, workspace_id=session.workspace_id
            )
        try:
            await commands.create_folder(
                db,
                workspace_id=session.workspace_id,
                slug=slug,
                name=name,
                description=payload.description,
                color=payload.color,
                now=now,
            )
        except FolderSlugTaken as taken:
            raise _slug_taken(taken.slug) from taken

        row = await _one_folder(db, session, slug)

    return _folder_read(row)


@router.patch(
    "/folders/{slug}",
    response_model=FolderRead,
    dependencies=[Depends(declares_action(ManagementAction.FOLDER_UPDATE))],
)
async def update_folder(
    slug: Slug,
    payload: FolderUpdate,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> FolderRead:
    """Name, describe or recolour a folder — **including one that has no row yet.**

    Most folders in a live workspace are namespaces observed on prompts rather
    than rows anybody created, and without the upsert they would be stuck with a
    capitalised slug for a name forever. So this is the verb that adopts: ``POST``
    refuses an existing folder, and this one names it.

    The slug is not among the fields, for A-021's reason — it is the first half of
    the model name a consuming product calls, and moving it would break every
    caller with no error anywhere.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _may_organise(db, session)
        await commands.update_folder(
            db,
            workspace_id=session.workspace_id,
            slug=slug,
            name=payload.name,
            description=payload.description,
            color=payload.color,
            now=now,
        )
        row = await _one_folder(db, session, slug)

    return _folder_read(row)


@router.delete(
    "/folders/{slug}",
    status_code=204,
    dependencies=[Depends(declares_action(ManagementAction.FOLDER_DELETE))],
)
async def delete_folder(
    slug: Slug,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> None:
    """Remove a folder's label. Refused while any prompt carries the namespace.

    **Idempotent on an unknown slug.** A slug with no row is either a folder
    nobody named or a folder somebody already deleted, and both are already in the
    state the caller asked for — a ``404`` here would be reporting a difference
    the caller cannot act on.

    The refusal on a non-empty folder is a product decision rather than an
    integrity one: nothing would break, the prompts keep their namespace and the
    folder reverts to a derived card. It is refused because a delete that reads
    destructive should not be one people learn to click through.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _may_organise(db, session)
        try:
            await commands.delete_folder(db, slug=slug)
        except FolderNotEmpty as blocked:
            raise _folder_not_empty(blocked.slug, blocked.prompt_count) from blocked


async def _one_folder(db: AsyncSession, session: Session, slug: str) -> FolderRow:
    """Re-read one folder out of the list, so a write answers in the read's shape.

    A second query rather than building the response from the payload: the counts
    and ``updated_at`` are derived, and a create that reported ``prompt_count: 0``
    from a local variable would be right by luck on the empty case and wrong the
    moment ``PATCH`` adopts a namespace holding twelve prompts.
    """
    visible = await visible_subject_filter(db, _actor(session), SubjectType.PROMPT)
    rows = await repository.list_folders(db, actor_id=session.user_id, visible=visible)
    for row in rows:
        if row.slug == slug:
            return row

    # Unreachable in practice — the row was just written in this transaction.
    # Not an exception the client can act on, so it fails loudly here rather than
    # answering a folder that does not exist.
    raise RuntimeError(f"folder {slug!r} vanished between its write and its read-back")


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


@router.patch(
    "/prompts/{prompt_id}/revisions/{version_id}/tags",
    response_model=RevisionSummaryRead,
    dependencies=[Depends(declares_action(ManagementAction.REVISION_TAGS_UPDATE))],
)
async def update_revision_tags(
    payload: RevisionTagsUpdate,
    prompt_id: Annotated[str, Path()],
    version_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> RevisionSummaryRead:
    """Edit revision labels from the version rail without changing authored content."""
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_EDIT, prompt_id)
        try:
            updated = await commands.update_revision_tags(
                db,
                workspace_id=session.workspace_id,
                prompt_id=prompt_id,
                version_id=version_id,
                tags=list(payload.tags),
            )
        except NothingToUpdate as error:
            raise _not_found() from error
    return _revision_summary(updated)


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
    request: Request,
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

    **The index request is published after the transaction closes, and it cannot
    fail this route** (`enqueue_index_job`). After, because a message published
    inside the transaction names a revision a rollback may still erase — the
    worker would then look for a version_id that never existed. And soft, because
    indexing costs an LLM extraction and an embedding, seconds of somebody
    else's latency: a save that waited for them would fail when a third party is
    slow, and a save that *refused* on a broker outage would lose text the author
    had already written. An unindexed prompt is a prompt the duplicate check
    cannot see yet, which the import screen states rather than papers over.
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
                    original_body=payload.original_body or payload.body,
                    original_format=payload.original_format,
                    original_filename=payload.original_filename,
                    conversion_model=payload.conversion_model,
                    conversion_schema_version=payload.conversion_schema_version,
                    provider_config_id=payload.provider_config_id,
                    upstream_model=payload.upstream_model,
                    fallback_answer=payload.fallback_answer,
                    parameters=dict(payload.parameters),
                    tags=list(payload.tags),
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

    await enqueue_index_job(
        sessionmaker,
        getattr(request.app.state, "broker_channel", None),
        prompt_id=prompt_id,
        version_id=created.version_id,
        workspace_id=session.workspace_id,
        created_by=session.user_id,
        role="latest",
    )

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


@router.post(
    "/prompts/{prompt_id}/revisions/{version_id}/trials",
    dependencies=[Depends(declares_action(ManagementAction.REVISION_TRIAL))],
)
async def trial_revision(
    payload: TrialRequest,
    prompt_id: Annotated[str, Path()],
    version_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> StreamingResponse:
    """The playground: one turn against **any** revision of this prompt, including a Draft.

    **This is not the gateway and it does not resolve anything.** The gateway
    serves the *released* revision of a model name, which is the whole trusted
    path and is why a consumer never holds prompt text. This route serves the
    revision named in its own URL, to somebody holding a session and
    ``run.start``, so that a prompt can be tried in the minutes between being
    written and being approved. Nothing here consults the released pointer,
    authenticates a key, or can be reached without a cookie.

    **``run.start``, because the act is spending money.** A Viewer may read this
    body already; what they may not do is bill the workspace for it. That is the
    same distinction ``eval_run.start`` draws, and reusing the permission is what
    keeps a workspace's answer to *who may cause provider spend* in one place
    instead of two that can disagree.

    **Every refusal happens before the provider is called, or not at all.** Once
    the first byte is out the response is a stream and its status line is already
    ``200``, so a failure after that point can only be an in-band event — which is
    exactly how the gateway behaves and exactly what the client has to be written
    for. The four pre-flight refusals below are therefore worth the round trips:
    an unbound revision, an unfilled placeholder, an oversize thread and a
    workspace over its ceiling all produce an ordinary error envelope the SPA can
    render, instead of a stream whose first event is an apology.

    **An override changes the turn and never the revision.** The payload may name
    a different provider configuration, a different upstream model and different
    sampling parameters, because *would this be as good on the cheap model* is a
    question the playground exists to answer and the alternative is two throwaway
    revisions on an immutable chain. No write happens on this path — there is no
    ``UPDATE`` in this function — and the ledger row records what actually ran, so
    a trial on an unbound-to-this-revision model is attributable rather than
    invisible. Approval still governs what the gateway serves: nothing here can
    change which revision is released, and a person who overrides a model into
    working has changed the answer on their screen and nothing else.

    **``compose`` cannot raise ``CallerSystemMessage`` here** and that is why it
    is not caught. ``TrialMessage.role`` is ``Literal["user", "assistant"]``, so a
    system turn is a ``422`` from pydantic naming the field, one layer before this
    function runs. The gateway needs the runtime check because its callers send
    raw OpenAI payloads; this one's caller is our own screen.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        prompt = await _visible_prompt(db, session, Action.RUN_START, prompt_id)
        revision = await repository.load_revision(db, version_id)

    # Checked outside the transaction for the same reason `read_diff` checks its
    # pair outside: a revision belonging to another prompt is a not-found, and
    # deciding that inside the transaction would suggest the row's tenancy was
    # the thing being tested. It was not — RLS already did that.
    if revision is None or revision.prompt_id != prompt_id:
        raise _not_found()

    # The override, or the revision's own binding. A configuration id belonging to
    # another workspace is not checked here and does not need to be: `dispatch`
    # loads it inside `workspace_transaction`, so RLS answers "no such provider
    # configuration in this workspace" — a `configuration_unusable` the screen
    # already renders, and byte-identical to one that never existed.
    provider_config_id = payload.provider_config_id or revision.provider_config_id
    upstream_model = payload.upstream_model or revision.upstream_model

    if provider_config_id is None or upstream_model is None:
        raise ManagementRefusal(
            status_code=409,
            code=ErrorCode.REGISTRY_TRIAL_UNBOUND,
            message="this revision binds no provider configuration",
            details={"version_id": version_id},
        )

    try:
        system_prompt = render(revision.body, payload.variables)
    except MissingVariable as missing:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.REGISTRY_TRIAL_MISSING_VARIABLE,
            message="the revision's body uses a variable no value was supplied for",
            details={"variable": missing.name},
        ) from missing
    except UnfilledPlaceholder as unfilled:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.REGISTRY_TRIAL_MISSING_VARIABLE,
            message="a placeholder in the revision's body was not substituted",
            details={"expected": unfilled.expected, "substituted": unfilled.substituted},
        ) from unfilled

    try:
        messages = compose(
            [message.model_dump() for message in payload.messages], system_prompt
        )
    except OversizeRequest as oversize:
        raise ManagementRefusal(
            status_code=413,
            code=ErrorCode.REGISTRY_TRIAL_TOO_LARGE,
            message="the composed message set is larger than a trial accepts",
            details={"bytes": oversize.size},
        ) from oversize

    # INT-020, and the one seam in Prope that fails open: a check that cannot be
    # evaluated returns allowed and counts itself. Checked here rather than per
    # turn inside the relay because a ceiling refuses a *decision to spend*, and
    # the decision is this request.
    decision = await check_spend_ceiling(sessionmaker, session.workspace_id, now=_utc_now())
    if not decision.allowed:
        raise ManagementRefusal(
            status_code=402,
            code=ErrorCode.REGISTRY_TRIAL_SPEND_CEILING_REACHED,
            message="this workspace is over its monthly spend ceiling",
        )

    return StreamingResponse(
        stream_trial(
            sessionmaker,
            revision=revision,
            model_name=prompt.model_name,
            provider_config_id=provider_config_id,
            upstream_model=upstream_model,
            parameters=_trial_parameters(revision.parameters, payload.parameters),
            messages=messages,
            # The turns and the variables, never the rendered body: the body is
            # already stored on the revision this record names, and a second copy
            # in the ledger would be a copy with its own retention window.
            request_body=_trial_request_body(payload),
        ),
        status_code=200,
        media_type="text/event-stream",
        # Proxies that buffer an event stream turn streaming into a slow
        # non-streaming response, which is invisible in development and obvious
        # in production. Caddy honours the second header.
        #
        # `no-transform` is the third, and it is the one a CDN reads: `no-store`
        # governs caching and says nothing about altering a payload in flight.
        # Cloudflare documents `no-transform` as what disables edge compression,
        # and compression is the mechanism that buffers — a compressor cannot
        # emit until it has something worth compressing. Same three headers as
        # `gateway.routes.STREAM_HEADERS`, for the same reason; they are not
        # shared because the two surfaces have no import between them and a
        # constant in `gateway` read by `prompt_registry` would invent one.
        headers={"cache-control": "no-store, no-transform", "x-accel-buffering": "no"},
    )


def _trial_parameters(
    base: dict[str, Any], override: TrialParameters | None
) -> dict[str, Any]:
    """The revision's parameters, with the playground's controls on top.

    A merge rather than a replacement, and ``exclude_none`` rather than a full
    dump. A revision may carry a parameter the playground has no control for —
    ``stop``, a vendor extension — and a trial that dropped it would be answering
    a question about a configuration nobody has. So an untouched control leaves
    the revision's value in place, and only a figure somebody actually set
    displaces one.
    """
    merged = dict(base)
    if override is not None:
        merged.update(override.model_dump(exclude_none=True))
    return merged


def _trial_request_body(payload: TrialRequest) -> str | None:
    """The same shape the gateway records, so one reader parses both (A-037).

    ``parameters`` is included when the caller overrode something, because
    otherwise the stored request would not explain its own cost: two rows against
    the same revision with different token counts and no visible reason is the
    thing a ledger exists to prevent. The binding itself is not repeated here —
    ``provider_config_id`` and ``upstream_model`` are columns on the row.
    """
    try:
        return json.dumps(
            {
                "messages": [message.model_dump() for message in payload.messages],
                "variables": dict(payload.variables),
                **(
                    {}
                    if payload.parameters is None
                    else {"parameters": payload.parameters.model_dump(exclude_none=True)}
                ),
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        return None


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


@router.get(
    "/prompts/{prompt_id}/call-records",
    response_model=list[CallRecordRead],
    dependencies=[Depends(declares_action(ManagementAction.CALL_RECORD_LIST))],
)
async def read_call_records(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[
        int, Query(ge=1, le=CALL_RECORD_MAX_LIMIT)
    ] = CALL_RECORD_PAGE_LIMIT,
    source: Annotated[Source | None, Query()] = None,
    outcome: Annotated[Outcome | None, Query()] = None,
    version_id: Annotated[str | None, Query()] = None,
    window: Annotated[UsageWindow | None, Query()] = None,
) -> list[CallRecordRead]:
    """What this prompt has actually served: one row per call, newest first.

    **Metadata only.** ADR-0018 forbids a read path for ``ledger.call_body`` —
    request and response text, the riskiest data in Prope — and is explicit that
    the rest is different: *"Metadata is unaffected. It is kept indefinitely, it
    has readers, and it is the audit trail NFR-02 requires."* This is one of those
    readers, and it names no body column.

    **Why the reader lives here and not in call-ledger.** ADR-0018 makes that
    module a sink: it has no edge to access-control, so it cannot check a
    permission, so any endpoint it exposed would have to be one that needs none.
    A workspace-wide call-record list is not such an endpoint — every row names a
    ``prompt_id``, so it would tell any member that a **private** prompt exists,
    which is the disclosure BR-01 closes as not-found. Putting the read behind
    ``prompt.read``, in the module that already loads the prompt row and
    authorises against it, is what makes the feature reachable without reopening
    that. call-ledger gains no outbound edge and stays a sink; this module gains
    an inbound one, which is the direction that was always allowed.

    **The refusal is ``_visible_prompt``'s, so it is A-116's two shapes and not a
    third.** A prompt the actor may not see answers not-found, byte-identical to
    an id that never existed — before any record is read, so the response cannot
    differ by how much traffic the prompt has had.

    Paged on a keyset over ``(created_at, call_id)`` rather than an offset: this
    is the largest table in the system and the newest page is the one anybody
    looks at, so an offset scan would get slower exactly as the data got more
    interesting. The cursor is the last ``call_id`` of the previous page.

    **The four filters are applied in the query, not by the client.** A page is
    fifty rows on a keyset; a client that filtered what it received would show
    "two calls from this app" for a prompt with two thousand, and the count would
    change as it paged. Each is a closed set or an id, so an unknown value is a
    ``422`` rather than a silently empty page.

    Empty is the ordinary answer for a prompt that has never been released, and
    the client renders it as such rather than as a failure.
    """
    since = None if window is None else _utc_now() - USAGE_WINDOW_SPANS[window]

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        records = await list_prompt_call_records(
            db,
            prompt_id,
            cursor=cursor,
            limit=limit,
            source=source,
            outcome=outcome,
            version_id=version_id,
            since=since,
        )
        # The ids come from the page just read, so this can name only keys that
        # called a prompt the caller is already authorised for. Same bound, and
        # same argument, as the Production tab's — see `access_control.labels`.
        labels = await key_labels(
            db, [record.consumer_key_id for record in records if record.consumer_key_id]
        )

    return [_call_record_read(record, labels) for record in records]


READ_OBSERVABILITY_POLICY = text(
    """
    SELECT
      COALESCE((
        SELECT observability_content_access_enabled
        FROM ledger.workspace_retention
        WHERE workspace_id = :workspace_id
      ), false) AS enabled,
      EXISTS(
        SELECT 1
        FROM access.role_binding
        WHERE workspace_id = :workspace_id
          AND user_id = :user_id
          AND role IN ('Owner', 'Admin', 'Reviewer')
      ) AS allowed_role
    """
)


def _call_trace(record: CallRecordListing) -> tuple[int | None, list[ObservabilitySpanRead]]:
    status = "success" if record.outcome in {"ok", "fallback"} else "error"
    durations = [value for value in (record.added_latency_ms, record.upstream_duration_ms) if value is not None]
    total = sum(durations) if durations else None
    spans = [
        ObservabilitySpanRead(
            span_id=f"{record.call_id}:root",
            name="gateway.request",
            kind="span",
            status=status,
            duration_ms=total,
        )
    ]
    if record.added_latency_ms is not None:
        spans.append(
            ObservabilitySpanRead(
                span_id=f"{record.call_id}:prope",
                parent_span_id=f"{record.call_id}:root",
                name="prope.overhead",
                kind="span",
                status="success",
                duration_ms=record.added_latency_ms,
            )
        )
    if record.upstream_duration_ms is not None:
        spans.append(
            ObservabilitySpanRead(
                span_id=f"{record.call_id}:provider",
                parent_span_id=f"{record.call_id}:root",
                name="provider.generation",
                kind="generation",
                status=status,
                duration_ms=record.upstream_duration_ms,
                model=record.upstream_model,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                cost=record.cost,
                currency=record.currency,
            )
        )
    return total, spans


@router.get(
    "/prompts/{prompt_id}/call-records/{call_id}/observability",
    response_model=CallObservabilityRead,
    dependencies=[Depends(declares_action(ManagementAction.CALL_OBSERVABILITY_READ))],
)
async def read_call_observability(
    prompt_id: Annotated[str, Path()],
    call_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    response: Response,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    include_request: Annotated[bool, Query()] = False,
) -> CallObservabilityRead:
    """One call's metadata-derived trace and, when policy permits, redacted content."""
    now = _utc_now()
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        record = await read_prompt_call_record(db, prompt_id, call_id)
        if record is None:
            raise _not_found()

        request_status = "disabled"
        messages: list[dict[str, Any]] = []
        if include_request:
            policy = (
                await db.execute(
                    READ_OBSERVABILITY_POLICY,
                    {"workspace_id": session.workspace_id, "user_id": session.user_id},
                )
            ).mappings().one()
            if bool(policy["enabled"]) and not bool(policy["allowed_role"]):
                request_status = "forbidden"
            elif bool(policy["enabled"]):
                body = await _read_prompt_call_content(db, prompt_id, call_id)
                if body is None or body.expires_at <= now:
                    request_status = "expired"
                else:
                    messages = redacted_messages(body.request_content, body.response_content)
                    request_status = "available"
                    await events.observability_content_viewed(
                        db,
                        workspace_id=session.workspace_id,
                        actor_id=session.user_id,
                        prompt_id=prompt_id,
                        call_id=call_id,
                        occurred_at=now,
                    )

    duration, spans = _call_trace(record)
    response.headers["Cache-Control"] = "private, no-store"
    status = "success" if record.outcome in {"ok", "fallback"} else "error"
    return CallObservabilityRead(
        trace_id=record.call_id,
        status=status,
        duration_ms=duration,
        request=ObservabilityRequestRead(status=request_status, messages=messages),
        spans=spans,
    )


@router.get(
    "/prompts/{prompt_id}/usage",
    response_model=PromptUsageRead,
    dependencies=[Depends(declares_action(ManagementAction.PROMPT_USAGE_READ))],
)
async def read_prompt_usage(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    window: Annotated[UsageWindow, Query()] = "30d",
    source: Annotated[Source | None, Query()] = None,
) -> PromptUsageRead:
    """Which integrations are calling this prompt, and what they are costing.

    The counted form of ``/call-records`` — same rows, same permission, same
    metadata-only rule, and the same reason it lives in this module rather than
    in call-ledger: ADR-0018 leaves that module unable to check a permission, and
    a workspace-wide version of this read would name a private prompt's id.

    **This route resolves an ``access.api_key`` name, and it is the only one in
    this module that reads anything belonging to access-control's own tables.**
    Listing keys is ``workspace.manage_keys``; naming the keys that called a
    prompt you may already read is not, and the argument for the difference — with
    its three bounds — is at ``prope.access_control.labels``. The rollup is read
    first and the labels second, from the ids it returned, so there is no path
    here that can enumerate keys.

    **The bucket with no key is the internal caller** — a playground trial,
    refused a key by ``ck_call_record_playground_calls_are_internal``. It is
    returned rather than dropped: the tab's cost column has to reconcile with
    what the workspace actually spent on this prompt, and the client shows it
    under its own label. The ``source`` filter is what separates production
    traffic from it, and the client defaults that filter to ``gateway``.

    Eval dispatches reach no bucket here — their ledger rows carry no
    ``prompt_id``, so nothing per-prompt can match them. The Eval tab reads their
    cost from ``evaluation.eval_run`` instead.

    Both queries run inside the one transaction that authorised the prompt, so
    the traffic and the names come from a single snapshot.
    """
    since = _utc_now() - USAGE_WINDOW_SPANS[window]

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        buckets = await aggregate_prompt_usage(db, prompt_id, since=since, source=source)
        labels = await key_labels(
            db, [bucket.consumer_key_id for bucket in buckets if bucket.consumer_key_id]
        )

    return PromptUsageRead(
        prompt_id=prompt_id,
        window=window,
        since=since,
        source=source,
        total_requests=sum(bucket.requests for bucket in buckets),
        buckets=[_usage_bucket_read(bucket, labels) for bucket in buckets],
    )


@router.get(
    "/prompts/{prompt_id}/conversations",
    response_model=list[ConversationSummaryRead],
    dependencies=[Depends(declares_action(ManagementAction.CONVERSATION_LIST))],
)
async def read_prompt_conversations(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[
        int, Query(ge=1, le=CONVERSATION_MAX_LIMIT)
    ] = CONVERSATION_PAGE_LIMIT,
    window: Annotated[UsageWindow | None, Query()] = None,
) -> list[ConversationSummaryRead]:
    """The end-user conversations this prompt took part in, most recent first.

    **This is the customer's chain, not Prope's.** Every other read in this module
    answers a question about the prompt as an asset — who changed it, what it
    cost, which integration called it. This one answers a question about the
    *application the prompt is part of*: a chatbot that puts a system prompt, a
    guardrail and a tool definition through the gateway makes three calls, and
    until now nothing said they were one conversation. The caller says so, by
    sending `prope.conversation_id`; a caller that does not send it has no
    conversations here and the list is empty, which is the ordinary answer rather
    than a failure.

    **Same permission, same refusal, same reason as ``/call-records``.**
    ``_visible_prompt`` runs before a single row is read, so a prompt the actor
    cannot see answers not-found — byte-identical to an id that never existed, and
    decided before any traffic is counted, so the response cannot differ by how
    busy the prompt has been.

    **There is deliberately no workspace-wide version of this route.** A list of
    every conversation would name conversations that ran through private prompts,
    which tells a reader those prompts exist — BR-01's disclosure arriving through
    a door nobody thought of as a read. Scoping the list to one prompt whose
    visibility has already been decided means there is no such door.

    Paged on a keyset over ``(last_called_at, conversation_id)``, for
    ``/call-records``' reason: this reads the largest table in the system and the
    newest page is the one anybody looks at.
    """
    since = None if window is None else _utc_now() - USAGE_WINDOW_SPANS[window]

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        conversations = await list_prompt_conversations(
            db, prompt_id, cursor=cursor, limit=limit, since=since
        )

    return [_conversation_summary_read(row) for row in conversations]


@router.get(
    "/prompts/{prompt_id}/conversations/{conversation_id}",
    response_model=ConversationGraphRead,
    dependencies=[Depends(declares_action(ManagementAction.CONVERSATION_READ))],
)
async def read_conversation_graph(
    prompt_id: Annotated[str, Path()],
    conversation_id: Annotated[str, Path(pattern=CONVERSATION_ID_PATTERN, max_length=64)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ConversationGraphRead:
    """One conversation as a graph: which prompts ran, in what order, and how each went.

    **Two gates, and both are load-bearing.**

    The first is ``_visible_prompt`` on ``prompt_id``, which is the permission
    this route declares. The second is inside ``read_conversation_calls``: the
    conversation is returned only if that prompt actually took part in it.
    Without the second, naming any prompt you may read alongside any
    ``conversation_id`` you could guess would hand back that conversation entire —
    the permission would be checked against a subject with no relationship to the
    thing being read. A conversation the caller has no connection to comes back
    empty rather than refused, which is not-found's shape and says nothing about
    whether the id exists.

    **Nodes whose prompt the caller may not see are dropped, and their edges are
    not bridged.** ADR-0020's rule applies once per distinct prompt in the chain:
    the row is loaded, its ``owner_id`` and ``access_level`` are passed to
    ``may()``, and a deny removes the node. The child of a removed node becomes a
    root rather than being re-parented onto its grandparent — a bridged edge would
    claim *A called C*, which is a different chain from the one that ran, and a
    graph that is confidently wrong about shape is worse than one that is visibly
    incomplete.

    **A gap in the chain discloses nothing**, which is what makes dropping
    tolerable where a placeholder node would not be. Calls the customer's own app
    made outside the gateway — a tool execution, a retrieval, a regex guardrail —
    are absent from this graph by construction, because Prope never saw them. So a
    discontinuity already has several innocent explanations, and a hidden private
    prompt is indistinguishable from any of them. ``hidden_count`` reports how
    many nodes went, because a reader who cannot tell a permissions gap from an
    application bug will go hunting for the bug — and a count names no prompt,
    no owner and no revision, and cannot be turned into any of those by asking
    again.

    **One prompt row per distinct prompt in the chain, not one per call.** A
    conversation is a handful of calls over a handful of prompts, so this is a
    small bounded fan-out inside the transaction that already authorised the
    entry point — and it is the only shape ADR-0020 permits, because ``may()``
    must be given a subject somebody read.

    **Capped, not paged**, and the cap is asked for as ``+ 1`` so that a
    conversation sitting exactly on it is not reported as truncated. Page two of
    a tree is a set of nodes whose parents are on page one; every layout decision
    needs the whole set.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        calls = await read_conversation_calls(
            db, prompt_id, conversation_id, limit=CONVERSATION_NODE_CAP + 1
        )

        truncated = len(calls) > CONVERSATION_NODE_CAP
        calls = calls[:CONVERSATION_NODE_CAP]

        titles = await _visible_prompt_titles(db, session, calls)
        visible = [call for call in calls if call.prompt_id in titles]
        labels = await key_labels(
            db, [call.consumer_key_id for call in visible if call.consumer_key_id]
        )

    return _conversation_graph_read(
        conversation_id,
        visible,
        titles=titles,
        labels=labels,
        hidden_count=len(calls) - len(visible),
        truncated=truncated,
    )


async def _visible_prompt_titles(
    db: AsyncSession, session: Session, calls: Sequence[ConversationCall]
) -> dict[str, str]:
    """The prompts in this chain the caller may read, by id, with their titles.

    ADR-0020 in a loop: load the row, pass its own ``owner_id`` and
    ``access_level`` to ``may()``, believe the answer. There is no bulk form of
    this and there should not be — a query that filtered by visibility would be
    access-control's rule living in prompt-registry's SQL, which is the second
    copy ADR-0020 exists to prevent.

    A call with no ``prompt_id`` is absent from the result and therefore dropped
    by the caller. That is the safe default rather than a tidy-up: a node with no
    subject is a node no permission check can be run against, and the honest
    thing to do with a row nobody can authorise is not to show it. In practice
    there are none — the gateway abandons a record with no ``version_id`` before
    it is ever enqueued, and no other source sets a ``conversation_id``.
    """
    actor = _actor(session)
    titles: dict[str, str] = {}
    for prompt_id in dict.fromkeys(call.prompt_id for call in calls if call.prompt_id):
        row = await repository.load_prompt(db, prompt_id)
        if row is not None and await may(db, actor, Action.PROMPT_READ, _subject(session, row)):
            titles[prompt_id] = row.title
    return titles


def _conversation_summary_read(row: ConversationListing) -> ConversationSummaryRead:
    """Every field named, for ``_call_record_read``'s reason."""
    return ConversationSummaryRead(
        conversation_id=row.conversation_id,
        started_at=row.started_at,
        last_called_at=row.last_called_at,
        call_count=row.call_count,
        prompt_count=row.prompt_count,
        error_count=row.error_count,
        fallback_count=row.fallback_count,
    )


def _conversation_graph_read(
    conversation_id: str,
    calls: Sequence[ConversationCall],
    *,
    titles: Mapping[str, str],
    labels: Mapping[str, str],
    hidden_count: int,
    truncated: bool,
) -> ConversationGraphRead:
    """The visible calls as nodes, with every edge that lands on a hidden one cut.

    ``present`` is the set of ``call_id``s that survived — **not** the set that
    was read. A parent that was dropped, or that aged out of retention, or that a
    truncated read never reached, all resolve the same way: the child becomes a
    root. That uniformity is the security property. If a hidden parent produced a
    different shape from an expired one, the shape itself would answer the
    question BR-01 closes.

    Fields are listed rather than copied, for ``_call_record_read``'s reason —
    here the column that must never cross is again a body.
    """
    present = {call.call_id for call in calls}
    return ConversationGraphRead(
        conversation_id=conversation_id,
        nodes=[
            ConversationNodeRead(
                call_id=call.call_id,
                parent_call_id=call.parent_call_id if call.parent_call_id in present else None,
                prompt_id=call.prompt_id,
                prompt_title=None if call.prompt_id is None else titles.get(call.prompt_id),
                source=call.source,
                version_id=call.version_id,
                revision_number=call.revision_number,
                consumer_key_id=call.consumer_key_id,
                consumer_label=None
                if call.consumer_key_id is None
                else labels.get(call.consumer_key_id),
                provider_config_id=call.provider_config_id,
                upstream_model=call.upstream_model,
                outcome=call.outcome,
                pinned=call.pinned,
                fallback=call.fallback,
                streaming=call.streaming,
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
                usage_status=call.usage_status,
                cost=call.cost,
                currency=call.currency,
                cost_status=call.cost_status,
                added_latency_ms=call.added_latency_ms,
                upstream_duration_ms=call.upstream_duration_ms,
                error_class=call.error_class,
                created_at=call.created_at,
            )
            for call in calls
        ],
        hidden_count=hidden_count,
        truncated=truncated,
    )
