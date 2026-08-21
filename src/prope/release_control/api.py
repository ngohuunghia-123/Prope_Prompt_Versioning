from datetime import UTC, datetime
from typing import Annotated

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
)
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.prompt_registry.seams import (
    DiffResult,
    IllegalTransition,
    NothingReleased,
    PromptRow,
    ReleasedPointerConflict,
    RevisionRead,
    get_prompt,
    get_revision,
)
from prope.property_history.domain import HistoryEvent
from prope.release_control import commands, repository, review
from prope.release_control.domain import (
    AcknowledgementRequired,
    ApprovalRow,
    Decision,
    EvidenceDigest,
    NoApprovalRecorded,
    NotPreviouslyReleased,
    ReasonRequired,
    ReleaseKind,
    ReleaseRow,
    ReviewAlreadyOpen,
    ReviewTaskKind,
    ReviewTaskNotOpen,
    ReviewTaskRow,
    ReviewTaskStatus,
    RevisionNotApproved,
)
from prope.release_control.observability import pointer_conflict_total
from prope.release_control.schemas import (
    ApprovalRead,
    ApproveAndReleaseRead,
    ApproveAndReleaseRequest,
    ApproveRequest,
    BreakGlassReleaseRequest,
    CloseReviewTaskRequest,
    DiffFieldRead,
    DiffLineRead,
    DiffRead,
    HistoryEntryRead,
    ReleaseRead,
    ReleaseRequest,
    RequestChangesRequest,
    ReviewScreenRead,
    ReviewTaskRead,
    RevisionCardRead,
    SuiteEvidenceRead,
    SummaryRead,
    WithdrawReleaseRequest,
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


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _not_found() -> ManagementRefusal:
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


def _subject(row: PromptRow) -> Subject:
    return Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        # ADR-0061. Read off the same row the other two come from, and required
        # for the same reason ADR-0020 requires them: a namespace grant is the
        # fifth source `may()` unions, and a subject that omitted its namespace
        # would silently skip it — which reads as "the grant does not work"
        # rather than as a missing field.
        namespace=row.namespace,
    )


async def _visible_prompt(
    db: AsyncSession, session: Session, action: Action, prompt_id: str
) -> PromptRow:
    row = await get_prompt(db, prompt_id)
    if row is None:
        raise _not_found()

    actor = _actor(session)
    subject = _subject(row)

    if await may(db, actor, action, subject):
        return row

    if await may(db, actor, Action.PROMPT_READ, subject):
        raise _forbidden(action)

    raise _not_found()


async def _require(
    db: AsyncSession, session: Session, action: Action, prompt: PromptRow
) -> None:
    if not await may(db, _actor(session), action, _subject(prompt)):
        raise _forbidden(action)


async def _revision_of(db: AsyncSession, prompt_id: str, version_id: str) -> RevisionRead:
    revision = await get_revision(db, version_id)
    if revision is None or revision.prompt_id != prompt_id:
        raise _not_found()
    return revision


def _approval_read(row: ApprovalRow) -> ApprovalRead:
    return ApprovalRead(
        approval_id=row.id,
        prompt_id=row.prompt_id,
        version_id=row.version_id,
        decision=row.decision,
        reviewer_id=row.reviewer_id,
        comment=row.comment,
        acknowledgement_reason=row.acknowledgement_reason,
        evidence_digest=row.evidence_digest,
        self_approved=row.self_approved,
        decided_at=row.decided_at,
    )


def _release_read(row: ReleaseRow) -> ReleaseRead:
    return ReleaseRead(
        release_id=row.id,
        prompt_id=row.prompt_id,
        version_id=row.version_id,
        kind=row.kind,
        previous_version_id=row.previous_version_id,
        approval_id=row.approval_id,
        break_glass=row.break_glass,
        reason=row.reason,
        released_by=row.released_by,
        released_at=row.released_at,
    )


def _review_task_read(row: ReviewTaskRow, now: datetime) -> ReviewTaskRead:
    return ReviewTaskRead(
        review_task_id=row.id,
        prompt_id=row.prompt_id,
        version_id=row.version_id,
        kind=row.kind,
        assigned_role=row.assigned_role,
        due_at=row.due_at,
        status=row.status,
        created_from_release_id=row.created_from_release_id,
        created_at=row.created_at,
        closed_by=row.closed_by,
        closed_at=row.closed_at,
        closed_note=row.closed_note,
        overdue=row.is_overdue(now),
    )


def _revision_card(revision: RevisionRead) -> RevisionCardRead:
    return RevisionCardRead(
        version_id=revision.version_id,
        prompt_id=revision.prompt_id,
        revision_number=revision.revision_number,
        change_summary=revision.change_summary,
        author_id=revision.author_id,
        status=revision.status.value,
        created_at=revision.created_at,
    )


def _diff_read(diff: DiffResult | None) -> DiffRead | None:
    if diff is None:
        return None
    return DiffRead(
        from_version_id=diff.from_version_id,
        to_version_id=diff.to_version_id,
        lines=[
            DiffLineRead(
                op=line.op.value,
                text=line.text,
                from_line=line.from_line,
                to_line=line.to_line,
            )
            for line in diff.lines
        ],
        fields=[
            DiffFieldRead(
                field=change.field,
                before=change.before,
                after=change.after,
                changed=change.changed,
            )
            for change in diff.fields
        ],
    )


def _summary_read(screen: review.ReviewScreen, now: datetime) -> SummaryRead | None:
    if screen.summary is None:
        return None

    digest = review.capture_evidence(
        version_id=screen.revision.version_id,
        summary=screen.summary,
        available=screen.summary_available,
        now=now,
    )
    return SummaryRead(
        suites=[
            SuiteEvidenceRead(
                suite_id=suite.suite_id,
                suite_name=suite.suite_name,
                suite_version=suite.suite_version,
                run_id=suite.run_id,
                status=suite.status,
                pass_count=suite.pass_count,
                fail_count=suite.fail_count,
                error_count=suite.error_count,
                case_count=suite.case_count,
                baseline_run_id=suite.baseline_run_id,
                baseline_ran_at=suite.baseline_ran_at,
                cost_delta=None if suite.cost_delta is None else suite.cost_delta.as_json(),
            )
            for suite in digest.suites
        ],
        total_cost_delta=None
        if digest.total_cost_delta is None
        else digest.total_cost_delta.as_json(),
        requires_acknowledgement=screen.summary.requires_acknowledgement,
        cost_warning=screen.summary.cost_warning,
    )


def _history_read(event: HistoryEvent) -> HistoryEntryRead:
    return HistoryEntryRead(
        event_id=event.id,
        action=event.action,
        target_type=event.target_type,
        target_id=event.target_id,
        actor_id=event.actor_id,
        reason=event.reason,
        details=dict(event.details),
        occurred_at=event.occurred_at,
    )


def _refuse_review_already_open(error: ReviewAlreadyOpen) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.RELEASE_REVIEW_ALREADY_OPEN,
        message="another revision of this prompt is already In review",
        details={"version_id": error.version_id},
    )


def _refuse_acknowledgement(error: AcknowledgementRequired) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=422,
        code=ErrorCode.RELEASE_ACKNOWLEDGEMENT_REQUIRED,
        message="this decision requires a one-line acknowledgement_reason",
        details={
            "version_id": error.version_id,
            "failing_suites": list(error.failing_suites),
            "summary_available": error.available,
        },
    )


def _refuse_reason(error: ReasonRequired) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=422,
        code=ErrorCode.RELEASE_REASON_REQUIRED,
        message="this action carries a mandatory one-line reason",
        details={"action": error.action},
    )


def _refuse_pointer_conflict(error: ReleasedPointerConflict) -> ManagementRefusal:
    pointer_conflict_total.inc()
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.RELEASE_POINTER_CONFLICT,
        message="something else was released while this decision was being made",
        details={"expected_current_version_id": error.expected, "released_version_id": error.actual},
    )


def _refuse_not_approved(error: RevisionNotApproved) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.RELEASE_REVISION_NOT_APPROVED,
        message="only an Approved revision may be released",
        details={"version_id": error.version_id, "status": error.status},
    )


def _refuse_no_approval(error: NoApprovalRecorded) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.RELEASE_NO_APPROVAL_RECORDED,
        message="this revision carries no approval record",
        details={"version_id": error.version_id},
    )


def _refuse_not_previously_released(error: NotPreviouslyReleased) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.RELEASE_NOT_PREVIOUSLY_RELEASED,
        message="a restore may only target a revision that was released before",
        details={"version_id": error.version_id},
    )


def _refuse_illegal_transition(error: IllegalTransition) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.RELEASE_ILLEGAL_TRANSITION,
        message="this revision is not in a state that allows the decision",
        details={
            "version_id": error.version_id,
            "current": None if error.current is None else error.current.value,
            "target": error.target.value,
        },
    )


def _refuse_nothing_released() -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.RELEASE_NOTHING_RELEASED,
        message="this prompt has nothing released to withdraw",
    )


def _refuse_task_not_open(error: ReviewTaskNotOpen) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.RELEASE_TASK_NOT_OPEN,
        message="this review task is not open",
        details={"review_task_id": error.task_id, "status": error.status.value},
    )


@router.post(
    "/prompts/{prompt_id}/revisions/{version_id}/submit",
    response_model=ReviewTaskRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_SUBMIT))],
)
async def submit_revision(
    prompt_id: Annotated[str, Path()],
    version_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ReviewTaskRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.REVISION_SUBMIT, prompt_id)
        revision = await _revision_of(db, prompt_id, version_id)

        try:
            task = await commands.submit_for_review(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                revision=revision,
                now=now,
            )
        except ReviewAlreadyOpen as error:
            raise _refuse_review_already_open(error) from error
        except IllegalTransition as error:
            raise _refuse_illegal_transition(error) from error

    return _review_task_read(task, now)


@router.get(
    "/prompts/{prompt_id}/revisions/{version_id}/review",
    response_model=ReviewScreenRead,
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_REVIEW_READ))],
)
async def read_review_screen(
    prompt_id: Annotated[str, Path()],
    version_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ReviewScreenRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        prompt = await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        revision = await _revision_of(db, prompt_id, version_id)
        screen = await review.compose_review(
            db, actor_id=session.user_id, prompt=prompt, revision=revision
        )

    return ReviewScreenRead(
        prompt_id=prompt.id,
        model_name=prompt.model_name,
        revision=_revision_card(screen.revision),
        diff=_diff_read(screen.diff),
        diff_against_version_id=screen.diff_against_version_id,
        summary=_summary_read(screen, now),
        summary_available=screen.summary_available,
        acknowledgement_required=screen.acknowledgement_required,
        self_authored=screen.self_authored,
        released_version_id=screen.released_version_id,
        latest_revision_number=screen.latest_revision_number,
        revisions_since=screen.revisions_since,
        approvals=[_approval_read(row) for row in screen.approvals],
        review_task=None
        if screen.review_task is None
        else _review_task_read(screen.review_task, now),
        history=[_history_read(event) for event in screen.history],
    )


@router.post(
    "/prompts/{prompt_id}/revisions/{version_id}/approve",
    response_model=ApprovalRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_APPROVE))],
)
async def approve_revision(
    payload: ApproveRequest,
    prompt_id: Annotated[str, Path()],
    version_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ApprovalRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.REVISION_APPROVE, prompt_id)
        revision = await _revision_of(db, prompt_id, version_id)

        digest = await _digest_or_refuse(
            db,
            prompt_id=prompt_id,
            revision=revision,
            acknowledgement_reason=payload.acknowledgement_reason,
            now=now,
        )

        try:
            approval = await commands.record_decision(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                revision=revision,
                decision=Decision.APPROVED,
                comment=payload.comment,
                acknowledgement_reason=payload.acknowledgement_reason,
                digest=digest,
                now=now,
            )
        except IllegalTransition as error:
            raise _refuse_illegal_transition(error) from error

    return _approval_read(approval)


@router.post(
    "/prompts/{prompt_id}/revisions/{version_id}/request-changes",
    response_model=ApprovalRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_REQUEST_CHANGES))],
)
async def request_changes(
    payload: RequestChangesRequest,
    prompt_id: Annotated[str, Path()],
    version_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ApprovalRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.REVISION_APPROVE, prompt_id)
        revision = await _revision_of(db, prompt_id, version_id)

        summary, available = await review.pull_review_summary(db, prompt_id, version_id)
        digest = review.capture_evidence(
            version_id=version_id, summary=summary, available=available, now=now
        )

        try:
            approval = await commands.record_decision(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                revision=revision,
                decision=Decision.CHANGES_REQUESTED,
                comment=payload.comment,
                acknowledgement_reason=None,
                digest=digest,
                now=now,
            )
        except ReasonRequired as error:
            raise _refuse_reason(error) from error
        except IllegalTransition as error:
            raise _refuse_illegal_transition(error) from error

    return _approval_read(approval)


@router.post(
    "/prompts/{prompt_id}/revisions/{version_id}/approve-and-release",
    response_model=ApproveAndReleaseRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_APPROVE_AND_RELEASE))],
)
async def approve_and_release(
    payload: ApproveAndReleaseRequest,
    prompt_id: Annotated[str, Path()],
    version_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ApproveAndReleaseRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        prompt = await _visible_prompt(db, session, Action.REVISION_APPROVE, prompt_id)
        await _require(db, session, Action.RELEASE_CREATE, prompt)

        revision = await _revision_of(db, prompt_id, version_id)

        digest = await _digest_or_refuse(
            db,
            prompt_id=prompt_id,
            revision=revision,
            acknowledgement_reason=payload.acknowledgement_reason,
            now=now,
        )

        try:
            approval = await commands.record_decision(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                revision=revision,
                decision=Decision.APPROVED,
                comment=payload.comment,
                acknowledgement_reason=payload.acknowledgement_reason,
                digest=digest,
                now=now,
            )
            approved = await _revision_of(db, prompt_id, version_id)
            release = await commands.create_release(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                revision=approved,
                kind=ReleaseKind.RELEASE,
                approval_id=approval.id,
                expected_current_version_id=payload.expected_current_version_id,
                reason=None,
                break_glass=False,
                now=now,
            )
        except IllegalTransition as error:
            raise _refuse_illegal_transition(error) from error
        except RevisionNotApproved as error:
            raise _refuse_not_approved(error) from error
        except ReleasedPointerConflict as error:
            raise _refuse_pointer_conflict(error) from error

    return ApproveAndReleaseRead(
        approval=_approval_read(approval), release=_release_read(release)
    )


@router.post(
    "/prompts/{prompt_id}/releases",
    response_model=ReleaseRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_CREATE))],
)
async def create_release(
    payload: ReleaseRequest,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ReleaseRead:
    now = _utc_now()

    if payload.kind is ReleaseKind.WITHDRAW:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.VALIDATION_FAILED,
            message="a withdrawal is its own route and its own permission",
            details={"kind": payload.kind.value},
        )

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.RELEASE_CREATE, prompt_id)
        revision = await _revision_of(db, prompt_id, payload.version_id)

        approval = await repository.latest_approval(db, payload.version_id)

        try:
            release = await commands.create_release(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                revision=revision,
                kind=payload.kind,
                approval_id=None if approval is None else approval.id,
                expected_current_version_id=payload.expected_current_version_id,
                reason=payload.reason,
                break_glass=False,
                now=now,
            )
        except RevisionNotApproved as error:
            raise _refuse_not_approved(error) from error
        except NotPreviouslyReleased as error:
            raise _refuse_not_previously_released(error) from error
        except NoApprovalRecorded as error:
            raise _refuse_no_approval(error) from error
        except ReasonRequired as error:
            raise _refuse_reason(error) from error
        except ReleasedPointerConflict as error:
            raise _refuse_pointer_conflict(error) from error

    return _release_read(release)


@router.post(
    "/prompts/{prompt_id}/releases/break-glass",
    response_model=ReleaseRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_BREAK_GLASS))],
)
async def break_glass_release(
    payload: BreakGlassReleaseRequest,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ReleaseRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.RELEASE_BREAK_GLASS, prompt_id)
        revision = await _revision_of(db, prompt_id, payload.version_id)

        try:
            release = await commands.create_release(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                revision=revision,
                kind=ReleaseKind.RELEASE,
                approval_id=None,
                expected_current_version_id=payload.expected_current_version_id,
                reason=payload.reason,
                break_glass=True,
                now=now,
            )
        except RevisionNotApproved as error:
            raise _refuse_not_approved(error) from error
        except ReasonRequired as error:
            raise _refuse_reason(error) from error
        except ReleasedPointerConflict as error:
            raise _refuse_pointer_conflict(error) from error

    return _release_read(release)


@router.post(
    "/prompts/{prompt_id}/releases/withdraw",
    response_model=ReleaseRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_WITHDRAW))],
)
async def withdraw_release(
    payload: WithdrawReleaseRequest,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ReleaseRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        prompt = await _visible_prompt(db, session, Action.RELEASE_WITHDRAW, prompt_id)

        if prompt.released_version_id is None:
            raise _refuse_nothing_released()

        try:
            release = await commands.withdraw_release(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                previous_version_id=prompt.released_version_id,
                reason=payload.reason,
                now=now,
            )
        except ReasonRequired as error:
            raise _refuse_reason(error) from error
        except NothingReleased as error:
            raise _refuse_nothing_released() from error

    return _release_read(release)


@router.get(
    "/prompts/{prompt_id}/releases",
    response_model=list[ReleaseRead],
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_LIST))],
)
async def list_releases(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    limit: Annotated[int, Query(ge=1, le=repository.MAX_LIMIT)] = repository.DEFAULT_LIMIT,
) -> list[ReleaseRead]:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.PROMPT_READ, prompt_id)
        rows = await repository.list_releases(db, prompt_id, limit=limit)

    return [_release_read(row) for row in rows]


@router.get(
    "/review-tasks",
    response_model=list[ReviewTaskRead],
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_REVIEW_TASK_LIST))],
)
async def list_review_tasks(
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    status: Annotated[ReviewTaskStatus | None, Query()] = None,
    kind: Annotated[ReviewTaskKind | None, Query()] = None,
    overdue: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=repository.MAX_LIMIT)] = repository.DEFAULT_LIMIT,
) -> list[ReviewTaskRead]:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        candidates = await repository.list_review_tasks(
            db, now=now, status=status, kind=kind, overdue=overdue, limit=limit
        )

        readable: dict[str, bool] = {}
        visible: list[ReviewTaskRow] = []
        for task in candidates:
            if task.prompt_id not in readable:
                readable[task.prompt_id] = await _may_read(db, session, task.prompt_id)
            if readable[task.prompt_id]:
                visible.append(task)

    return [_review_task_read(task, now) for task in visible]


@router.post(
    "/review-tasks/{task_id}/close",
    response_model=ReviewTaskRead,
    dependencies=[Depends(declares_action(ManagementAction.RELEASE_REVIEW_TASK_CLOSE))],
)
async def close_review_task(
    payload: CloseReviewTaskRequest,
    task_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ReviewTaskRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        task = await repository.load_review_task(db, task_id)
        if task is None:
            raise _not_found()

        await _visible_prompt(db, session, Action.REVISION_APPROVE, task.prompt_id)

        try:
            closed = await commands.close_review_task(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                task=task,
                note=payload.note,
                now=now,
            )
        except ReviewTaskNotOpen as error:
            raise _refuse_task_not_open(error) from error

    return _review_task_read(closed, now)


async def _may_read(db: AsyncSession, session: Session, prompt_id: str) -> bool:
    prompt = await get_prompt(db, prompt_id)
    if prompt is None:
        return False
    return await may(db, _actor(session), Action.PROMPT_READ, _subject(prompt))


async def _digest_or_refuse(
    db: AsyncSession,
    *,
    prompt_id: str,
    revision: RevisionRead,
    acknowledgement_reason: str | None,
    now: datetime,
) -> EvidenceDigest:
    summary, available = await review.pull_review_summary(db, prompt_id, revision.version_id)
    digest = review.capture_evidence(
        version_id=revision.version_id, summary=summary, available=available, now=now
    )

    if review.acknowledgement_is_required(summary, available) and not (
        acknowledgement_reason or ""
    ).strip():
        raise _refuse_acknowledgement(
            AcknowledgementRequired(revision.version_id, digest.failing_suites, available)
        )

    return digest
