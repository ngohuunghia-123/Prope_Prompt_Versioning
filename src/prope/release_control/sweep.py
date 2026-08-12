from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import list_workspace_ids
from prope.db.session import workspace_transaction
from prope.prompt_registry.seams import RevisionStatus, get_revision, list_released
from prope.release_control import repository
from prope.release_control.domain import ReviewTaskKind
from prope.release_control.observability import (
    orphaned_pointer_rows,
    review_task_open,
    review_task_overdue,
    sweep_pass_total,
    unapproved_revision_rows,
    without_approval_rows,
)

log = structlog.get_logger(__name__)

__all__ = [
    "GAUGE_PASS",
    "RECONCILE_PASS",
    "reconcile_released_pointers",
    "refresh_review_task_gauges",
]

GAUGE_PASS = "review_task_gauges"

RECONCILE_PASS = "released_pointer_reconciliation"


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def refresh_review_task_gauges(
    sessionmaker: async_sessionmaker[AsyncSession], *, now: datetime | None = None
) -> None:
    at = now if now is not None else _utc_now()

    open_by_kind = {kind.value: 0 for kind in ReviewTaskKind}
    overdue = 0

    for workspace_id in await list_workspace_ids(sessionmaker):
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            for kind, count in (await repository.count_open_review_tasks(db)).items():
                open_by_kind[kind] = open_by_kind.get(kind, 0) + count
            overdue += await repository.count_overdue_review_tasks(db, now=at)

    for kind, count in open_by_kind.items():
        review_task_open.labels(kind=kind).set(count)
    review_task_overdue.set(overdue)
    sweep_pass_total.labels(**{"pass": GAUGE_PASS}).inc()

    if overdue:
        log.warning("release_control.review_task_overdue", outcome="found")


async def reconcile_released_pointers(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    orphaned = 0
    unapproved = 0
    without_approval = 0

    for workspace_id in await list_workspace_ids(sessionmaker):
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            without_approval += await repository.count_releases_without_approval(db)

            released = await list_released(db, workspace_id)
            if not released:
                continue

            known = await repository.released_version_ids(db)
            for listing in released:
                if listing.version_id not in known:
                    orphaned += 1
                revision = await get_revision(db, listing.version_id)
                if revision is None or revision.status is not RevisionStatus.APPROVED:
                    unapproved += 1

    orphaned_pointer_rows.set(orphaned)
    unapproved_revision_rows.set(unapproved)
    without_approval_rows.set(without_approval)
    sweep_pass_total.labels(**{"pass": RECONCILE_PASS}).inc()

    if orphaned or unapproved or without_approval:
        log.warning(
            "release_control.reconciliation_found",
            orphaned=orphaned,
            unapproved=unapproved,
            without_approval=without_approval,
        )
