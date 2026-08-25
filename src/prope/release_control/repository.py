from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.release_control.domain import (
    ApprovalRow,
    Decision,
    ReleaseKind,
    ReleaseRow,
    ReviewTaskKind,
    ReviewTaskRow,
    ReviewTaskStatus,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "count_open_review_tasks",
    "count_overdue_review_tasks",
    "count_releases_without_approval",
    "latest_approval",
    "latest_decision",
    "list_approvals",
    "list_releases",
    "list_review_tasks",
    "load_approval",
    "load_release",
    "load_review_task",
    "open_review_task",
    "released_version_ids",
    "was_ever_released",
]

DEFAULT_LIMIT = 50

MAX_LIMIT = 200

LOAD_APPROVAL = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, decision, reviewer_id, comment,
           acknowledgement_reason, evidence_digest, self_approved, decided_at
    FROM   release.approval
    WHERE  id = :approval_id
    """
)

LATEST_APPROVAL = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, decision, reviewer_id, comment,
           acknowledgement_reason, evidence_digest, self_approved, decided_at
    FROM   release.approval
    WHERE  version_id = :version_id AND decision = 'approved'
    ORDER  BY decided_at DESC, id DESC
    LIMIT  1
    """
)

#: **The last decision of any kind**, which is not what ``LATEST_APPROVAL``
#: reads. That one filters ``decision = 'approved'`` because its callers are
#: asking *"may this be released"*; this one is asking *"what did the reviewer
#: last say"*, and a rejection is an answer to that question. Two queries rather
#: than one with a flag, because a caller that had to pass the flag correctly is
#: a caller that could render a rejection as an approval by getting it wrong.
LATEST_DECISION = text(
    """
    SELECT decision
    FROM   release.approval
    WHERE  prompt_id = :prompt_id AND version_id = :version_id
    ORDER  BY decided_at DESC, id DESC
    LIMIT  1
    """
)

LIST_APPROVALS = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, decision, reviewer_id, comment,
           acknowledgement_reason, evidence_digest, self_approved, decided_at
    FROM   release.approval
    WHERE  version_id = :version_id
    ORDER  BY decided_at DESC, id DESC
    LIMIT  :limit
    """
)

LOAD_RELEASE = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, kind, previous_version_id,
           approval_id, break_glass, reason, released_by, released_at
    FROM   release.release
    WHERE  id = :release_id
    """
)

LIST_RELEASES = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, kind, previous_version_id,
           approval_id, break_glass, reason, released_by, released_at
    FROM   release.release
    WHERE  prompt_id = :prompt_id
    ORDER  BY released_at DESC, id DESC
    LIMIT  :limit
    """
)

WAS_EVER_RELEASED = text(
    """
    SELECT count(*)
    FROM   release.release
    WHERE  version_id = :version_id AND kind IN ('release', 'restore')
    """
)

RELEASED_VERSION_IDS = text(
    """
    SELECT DISTINCT version_id
    FROM   release.release
    WHERE  version_id IS NOT NULL
    """
)

COUNT_RELEASES_WITHOUT_APPROVAL = text(
    """
    SELECT count(*)
    FROM   release.release
    WHERE  version_id IS NOT NULL AND approval_id IS NULL AND break_glass = false
    """
)

LOAD_REVIEW_TASK = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, kind, assigned_role, due_at, status,
           created_from_release_id, created_at, closed_by, closed_at, closed_note
    FROM   release.review_task
    WHERE  id = :task_id
    """
)

OPEN_REVIEW_TASK = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, kind, assigned_role, due_at, status,
           created_from_release_id, created_at, closed_by, closed_at, closed_note
    FROM   release.review_task
    WHERE  prompt_id = :prompt_id AND kind = 'review' AND status = 'open'
    LIMIT  1
    """
)

LIST_REVIEW_TASKS = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, kind, assigned_role, due_at, status,
           created_from_release_id, created_at, closed_by, closed_at, closed_note
    FROM   release.review_task
    WHERE  (CAST(:status AS text) IS NULL OR status = CAST(:status AS text))
      AND  (CAST(:kind AS text) IS NULL OR kind = CAST(:kind AS text))
      AND  (NOT CAST(:overdue AS boolean)
            OR (status = 'open' AND due_at IS NOT NULL AND due_at <= :now))
    ORDER  BY created_at DESC, id DESC
    LIMIT  :limit
    """
)

COUNT_OPEN_REVIEW_TASKS = text(
    """
    SELECT kind, count(*)
    FROM   release.review_task
    WHERE  status = 'open'
    GROUP  BY kind
    """
)

COUNT_OVERDUE_REVIEW_TASKS = text(
    """
    SELECT count(*)
    FROM   release.review_task
    WHERE  status = 'open'
      AND  kind = 'break_glass_followup'
      AND  due_at IS NOT NULL
      AND  due_at <= :now
    """
)


def _approval(row: Any) -> ApprovalRow:
    return ApprovalRow(
        id=row["id"],
        workspace_id=row["workspace_id"],
        prompt_id=row["prompt_id"],
        version_id=row["version_id"],
        decision=Decision(row["decision"]),
        reviewer_id=row["reviewer_id"],
        comment=row["comment"],
        acknowledgement_reason=row["acknowledgement_reason"],
        evidence_digest=dict(row["evidence_digest"] or {}),
        self_approved=row["self_approved"],
        decided_at=row["decided_at"],
    )


def _release(row: Any) -> ReleaseRow:
    return ReleaseRow(
        id=row["id"],
        workspace_id=row["workspace_id"],
        prompt_id=row["prompt_id"],
        version_id=row["version_id"],
        kind=ReleaseKind(row["kind"]),
        previous_version_id=row["previous_version_id"],
        approval_id=row["approval_id"],
        break_glass=row["break_glass"],
        reason=row["reason"],
        released_by=row["released_by"],
        released_at=row["released_at"],
    )


def _review_task(row: Any) -> ReviewTaskRow:
    return ReviewTaskRow(
        id=row["id"],
        workspace_id=row["workspace_id"],
        prompt_id=row["prompt_id"],
        version_id=row["version_id"],
        kind=ReviewTaskKind(row["kind"]),
        assigned_role=row["assigned_role"],
        due_at=row["due_at"],
        status=ReviewTaskStatus(row["status"]),
        created_from_release_id=row["created_from_release_id"],
        created_at=row["created_at"],
        closed_by=row["closed_by"],
        closed_at=row["closed_at"],
        closed_note=row["closed_note"],
    )


async def load_approval(db: AsyncSession, approval_id: str) -> ApprovalRow | None:
    row = (await db.execute(LOAD_APPROVAL, {"approval_id": approval_id})).mappings().first()
    return None if row is None else _approval(row)


async def latest_approval(db: AsyncSession, version_id: str) -> ApprovalRow | None:
    row = (await db.execute(LATEST_APPROVAL, {"version_id": version_id})).mappings().first()
    return None if row is None else _approval(row)


async def latest_decision(db: AsyncSession, *, prompt_id: str, version_id: str) -> str | None:
    """The most recent recorded decision for one revision, or ``None`` for none.

    A string rather than an ``ApprovalRow``: the caller renders a status label
    beside a lifecycle phase and has no business with a reviewer id, a comment or
    an evidence digest — the third bound `access_control.labels.key_labels`
    argues for, applied to a column instead of a mapping.
    """
    return (
        await db.execute(LATEST_DECISION, {"prompt_id": prompt_id, "version_id": version_id})
    ).scalar_one_or_none()


async def list_approvals(
    db: AsyncSession, version_id: str, *, limit: int = DEFAULT_LIMIT
) -> tuple[ApprovalRow, ...]:
    rows = (
        await db.execute(LIST_APPROVALS, {"version_id": version_id, "limit": _bounded(limit)})
    ).mappings().all()
    return tuple(_approval(row) for row in rows)


async def load_release(db: AsyncSession, release_id: str) -> ReleaseRow | None:
    row = (await db.execute(LOAD_RELEASE, {"release_id": release_id})).mappings().first()
    return None if row is None else _release(row)


async def list_releases(
    db: AsyncSession, prompt_id: str, *, limit: int = DEFAULT_LIMIT
) -> tuple[ReleaseRow, ...]:
    rows = (
        await db.execute(LIST_RELEASES, {"prompt_id": prompt_id, "limit": _bounded(limit)})
    ).mappings().all()
    return tuple(_release(row) for row in rows)


async def was_ever_released(db: AsyncSession, version_id: str) -> bool:
    return bool(await db.scalar(WAS_EVER_RELEASED, {"version_id": version_id}))


async def released_version_ids(db: AsyncSession) -> frozenset[str]:
    return frozenset((await db.execute(RELEASED_VERSION_IDS)).scalars().all())


async def count_releases_without_approval(db: AsyncSession) -> int:
    return int(await db.scalar(COUNT_RELEASES_WITHOUT_APPROVAL) or 0)


async def load_review_task(db: AsyncSession, task_id: str) -> ReviewTaskRow | None:
    row = (await db.execute(LOAD_REVIEW_TASK, {"task_id": task_id})).mappings().first()
    return None if row is None else _review_task(row)


async def open_review_task(db: AsyncSession, prompt_id: str) -> ReviewTaskRow | None:
    row = (await db.execute(OPEN_REVIEW_TASK, {"prompt_id": prompt_id})).mappings().first()
    return None if row is None else _review_task(row)


async def list_review_tasks(
    db: AsyncSession,
    *,
    now: datetime,
    status: ReviewTaskStatus | None = None,
    kind: ReviewTaskKind | None = None,
    overdue: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> tuple[ReviewTaskRow, ...]:
    rows = (
        await db.execute(
            LIST_REVIEW_TASKS,
            {
                "status": None if status is None else status.value,
                "kind": None if kind is None else kind.value,
                "overdue": overdue,
                "now": now,
                "limit": _bounded(limit),
            },
        )
    ).mappings().all()
    return tuple(_review_task(row) for row in rows)


async def count_open_review_tasks(db: AsyncSession) -> dict[str, int]:
    rows = (await db.execute(COUNT_OPEN_REVIEW_TASKS)).all()
    return {kind: int(count) for kind, count in rows}


async def count_overdue_review_tasks(db: AsyncSession, *, now: datetime) -> int:
    return int(await db.scalar(COUNT_OVERDUE_REVIEW_TASKS, {"now": now}) or 0)


def _bounded(limit: int) -> int:
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit={limit} is outside A-045's bound of 1..{MAX_LIMIT}")
    return limit
