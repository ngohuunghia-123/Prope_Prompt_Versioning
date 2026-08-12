import json
from datetime import datetime

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.prompt_registry.seams import (
    RevisionRead,
    RevisionStatus,
    clear_released_revision,
    get_revision,
    set_released_revision,
    set_revision_status,
)
from prope.release_control import events, repository
from prope.release_control.domain import (
    BREAK_GLASS_FOLLOW_UP,
    DEFAULT_REVIEW_ROLE,
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
from prope.release_control.observability import (
    acknowledged_total,
    break_glass_total,
    decision_total,
    release_total,
    review_turnaround_seconds,
    self_approval_total,
    submit_total,
)

log = structlog.get_logger(__name__)

__all__ = [
    "APPROVAL_ID_PREFIX",
    "RELEASE_ID_PREFIX",
    "REVIEW_TASK_ID_PREFIX",
    "close_review_task",
    "create_release",
    "record_decision",
    "submit_for_review",
    "withdraw_release",
]

APPROVAL_ID_PREFIX = "apr_"

RELEASE_ID_PREFIX = "rel_"

REVIEW_TASK_ID_PREFIX = "rvt_"

INSERT_REVIEW_TASK = text(
    """
    INSERT INTO release.review_task (
        id, workspace_id, prompt_id, version_id, kind, assigned_role, due_at,
        status, created_from_release_id, created_at
    ) VALUES (
        :id, :workspace_id, :prompt_id, :version_id, :kind, :assigned_role, :due_at,
        'open', :created_from_release_id, :now
    )
    """
)

SUPERSEDE_REVIEW_TASK = text(
    """
    UPDATE release.review_task
       SET status = 'superseded'
     WHERE id = :task_id AND status = 'open'
    """
)

CLOSE_REVIEW_TASK = text(
    """
    UPDATE release.review_task
       SET status      = 'closed',
           closed_by   = :closed_by,
           closed_at   = :now,
           closed_note = :closed_note
     WHERE id = :task_id AND status = 'open'
    """
)

INSERT_APPROVAL = text(
    """
    INSERT INTO release.approval (
        id, workspace_id, prompt_id, version_id, decision, reviewer_id, comment,
        acknowledgement_reason, evidence_digest, self_approved, decided_at
    ) VALUES (
        :id, :workspace_id, :prompt_id, :version_id, :decision, :reviewer_id, :comment,
        :acknowledgement_reason, CAST(:evidence_digest AS jsonb), :self_approved, :now
    )
    """
)

INSERT_RELEASE = text(
    """
    INSERT INTO release.release (
        id, workspace_id, prompt_id, version_id, kind, previous_version_id,
        approval_id, break_glass, reason, released_by, released_at
    ) VALUES (
        :id, :workspace_id, :prompt_id, :version_id, :kind, :previous_version_id,
        :approval_id, :break_glass, :reason, :released_by, :now
    )
    """
)


async def submit_for_review(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    revision: RevisionRead,
    now: datetime,
) -> ReviewTaskRow:
    task_id = f"{REVIEW_TASK_ID_PREFIX}{ULID()}"
    outcome = "opened"

    standing = await repository.open_review_task(db, prompt_id)
    if standing is not None:
        if standing.version_id == revision.version_id:
            submit_total.labels(outcome="refused").inc()
            raise ReviewAlreadyOpen(prompt_id, standing.version_id)

        incumbent = await get_revision(db, standing.version_id)
        if incumbent is not None and incumbent.revision_number >= revision.revision_number:
            submit_total.labels(outcome="refused").inc()
            raise ReviewAlreadyOpen(prompt_id, standing.version_id)

        await db.execute(SUPERSEDE_REVIEW_TASK, {"task_id": standing.id})
        if incumbent is not None and incumbent.status is RevisionStatus.IN_REVIEW:
            await set_revision_status(
                db,
                version_id=standing.version_id,
                status=RevisionStatus.DRAFT,
                decision_id=task_id,
            )
        outcome = "superseded"

    await db.execute(
        INSERT_REVIEW_TASK,
        {
            "id": task_id,
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "version_id": revision.version_id,
            "kind": ReviewTaskKind.REVIEW.value,
            "assigned_role": DEFAULT_REVIEW_ROLE,
            "due_at": None,
            "created_from_release_id": None,
            "now": now,
        },
    )

    await set_revision_status(
        db,
        version_id=revision.version_id,
        status=RevisionStatus.IN_REVIEW,
        decision_id=task_id,
    )

    await events.revision_submitted(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        version_id=revision.version_id,
        occurred_at=now,
    )

    submit_total.labels(outcome=outcome).inc()
    log.info(
        "release_control.revision_submitted",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        version_id=revision.version_id,
        review_task_id=task_id,
    )

    task = await repository.load_review_task(db, task_id)
    assert task is not None
    return task


async def record_decision(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    revision: RevisionRead,
    decision: Decision,
    comment: str | None,
    acknowledgement_reason: str | None,
    digest: EvidenceDigest,
    now: datetime,
) -> ApprovalRow:
    if decision is Decision.CHANGES_REQUESTED and not (comment or "").strip():
        raise ReasonRequired("request-changes")

    approval_id = f"{APPROVAL_ID_PREFIX}{ULID()}"
    self_approved = revision.author_id == actor_id

    await db.execute(
        INSERT_APPROVAL,
        {
            "id": approval_id,
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "version_id": revision.version_id,
            "decision": decision.value,
            "reviewer_id": actor_id,
            "comment": comment,
            "acknowledgement_reason": acknowledgement_reason,
            "evidence_digest": json.dumps(digest.as_json()),
            "self_approved": self_approved,
            "now": now,
        },
    )

    target = (
        RevisionStatus.APPROVED
        if decision is Decision.APPROVED
        else RevisionStatus.DRAFT
    )
    await set_revision_status(
        db, version_id=revision.version_id, status=target, decision_id=approval_id
    )

    if decision is Decision.APPROVED:
        await events.revision_approved(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt_id,
            version_id=revision.version_id,
            occurred_at=now,
        )
    else:
        await events.revision_changes_requested(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt_id,
            version_id=revision.version_id,
            reason=str(comment),
            occurred_at=now,
        )

    standing = await repository.open_review_task(db, prompt_id)
    if standing is not None and standing.version_id == revision.version_id:
        await db.execute(
            CLOSE_REVIEW_TASK,
            {
                "task_id": standing.id,
                "closed_by": actor_id,
                "closed_note": None,
                "now": now,
            },
        )
        review_turnaround_seconds.observe((now - standing.created_at).total_seconds())

    decision_total.labels(decision=decision.value).inc()
    if self_approved and decision is Decision.APPROVED:
        self_approval_total.inc()
    if acknowledgement_reason is not None and decision is Decision.APPROVED:
        acknowledged_total.inc()

    log.info(
        "release_control.decision_recorded",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        version_id=revision.version_id,
        approval_id=approval_id,
        decision=decision.value,
        acknowledged=acknowledgement_reason is not None,
        self_approved=self_approved,
    )

    approval = await repository.load_approval(db, approval_id)
    assert approval is not None
    return approval


async def create_release(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    revision: RevisionRead,
    kind: ReleaseKind,
    approval_id: str | None,
    expected_current_version_id: str | None,
    reason: str | None,
    break_glass: bool,
    now: datetime,
) -> ReleaseRow:
    if revision.status is not RevisionStatus.APPROVED:
        raise RevisionNotApproved(revision.version_id, revision.status.value)

    if kind is ReleaseKind.RESTORE and not await repository.was_ever_released(
        db, revision.version_id
    ):
        raise NotPreviouslyReleased(revision.version_id)

    mandatory_reason = break_glass or kind is ReleaseKind.RESTORE
    if mandatory_reason and not (reason or "").strip():
        raise ReasonRequired("break-glass" if break_glass else "restore")

    if break_glass:
        approval_id = None
    elif approval_id is None:
        raise NoApprovalRecorded(revision.version_id)

    release_id = f"{RELEASE_ID_PREFIX}{ULID()}"

    await db.execute(
        INSERT_RELEASE,
        {
            "id": release_id,
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "version_id": revision.version_id,
            "kind": kind.value,
            "previous_version_id": expected_current_version_id,
            "approval_id": approval_id,
            "break_glass": break_glass,
            "reason": reason,
            "released_by": actor_id,
            "now": now,
        },
    )

    await set_released_revision(
        db,
        prompt_id=prompt_id,
        version_id=revision.version_id,
        release_id=release_id,
        expected_current_version_id=expected_current_version_id,
    )

    await events.revision_released(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        version_id=revision.version_id,
        previous_version_id=expected_current_version_id,
        break_glass=break_glass,
        occurred_at=now,
    )

    if kind is ReleaseKind.RESTORE:
        await events.revision_restored(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt_id,
            version_id=revision.version_id,
            occurred_at=now,
        )

    if break_glass:
        await events.revision_break_glass_released(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt_id,
            version_id=revision.version_id,
            reason=str(reason),
            occurred_at=now,
        )
        await _open_break_glass_follow_up(
            db,
            workspace_id=workspace_id,
            prompt_id=prompt_id,
            version_id=revision.version_id,
            release_id=release_id,
            now=now,
        )
        break_glass_total.inc()

    release_total.labels(kind=kind.value).inc()
    log.info(
        "release_control.released",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        version_id=revision.version_id,
        release_id=release_id,
        approval_id=approval_id,
        kind=kind.value,
        break_glass=break_glass,
        previous_version_id=expected_current_version_id,
    )

    row = await repository.load_release(db, release_id)
    assert row is not None
    return row


async def withdraw_release(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    previous_version_id: str,
    reason: str | None,
    now: datetime,
) -> ReleaseRow:
    if not (reason or "").strip():
        raise ReasonRequired("withdraw")

    release_id = f"{RELEASE_ID_PREFIX}{ULID()}"

    await db.execute(
        INSERT_RELEASE,
        {
            "id": release_id,
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "version_id": None,
            "kind": ReleaseKind.WITHDRAW.value,
            "previous_version_id": previous_version_id,
            "approval_id": None,
            "break_glass": False,
            "reason": reason,
            "released_by": actor_id,
            "now": now,
        },
    )

    await clear_released_revision(db, prompt_id=prompt_id, release_id=release_id)

    await events.release_withdrawn(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        release_id=release_id,
        reason=str(reason),
        occurred_at=now,
    )

    release_total.labels(kind=ReleaseKind.WITHDRAW.value).inc()
    log.info(
        "release_control.withdrawn",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        release_id=release_id,
        previous_version_id=previous_version_id,
    )

    row = await repository.load_release(db, release_id)
    assert row is not None
    return row


async def close_review_task(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    task: ReviewTaskRow,
    note: str | None,
    now: datetime,
) -> ReviewTaskRow:
    if task.status is not ReviewTaskStatus.OPEN:
        raise ReviewTaskNotOpen(task.id, task.status)

    await db.execute(
        CLOSE_REVIEW_TASK,
        {"task_id": task.id, "closed_by": actor_id, "closed_note": note, "now": now},
    )

    await events.review_task_closed(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=task.prompt_id,
        task_id=task.id,
        occurred_at=now,
    )

    log.info(
        "release_control.review_task_closed",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=task.prompt_id,
        review_task_id=task.id,
        kind=task.kind.value,
    )

    closed = await repository.load_review_task(db, task.id)
    assert closed is not None
    return closed


async def _open_break_glass_follow_up(
    db: AsyncSession,
    *,
    workspace_id: str,
    prompt_id: str,
    version_id: str,
    release_id: str,
    now: datetime,
) -> str:
    task_id = f"{REVIEW_TASK_ID_PREFIX}{ULID()}"
    await db.execute(
        INSERT_REVIEW_TASK,
        {
            "id": task_id,
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "version_id": version_id,
            "kind": ReviewTaskKind.BREAK_GLASS_FOLLOWUP.value,
            "assigned_role": DEFAULT_REVIEW_ROLE,
            "due_at": now + BREAK_GLASS_FOLLOW_UP,
            "created_from_release_id": release_id,
            "now": now,
        },
    )
    return task_id
