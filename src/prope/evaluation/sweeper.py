from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import list_workspace_ids
from prope.db.session import workspace_transaction
from prope.evaluation import commands, events, repository
from prope.evaluation.domain import SWEEP_NO_PROGRESS_SECONDS, RunStatus
from prope.evaluation.observability import run_interrupted_total, run_total

log = structlog.get_logger(__name__)

__all__ = ["sweep_interrupted_runs"]


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def sweep_interrupted_runs(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    clock: Callable[[], datetime] = _utc_now,
    no_progress_seconds: float = SWEEP_NO_PROGRESS_SECONDS,
) -> int:
    now = clock()
    cutoff = now - timedelta(seconds=no_progress_seconds)
    reaped = 0

    for workspace_id in await list_workspace_ids(sessionmaker):
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            reaped += await _sweep_one_workspace(db, workspace_id, cutoff=cutoff, now=now)

    return reaped


async def _sweep_one_workspace(
    db: AsyncSession, workspace_id: str, *, cutoff: datetime, now: datetime
) -> int:
    reaped = 0

    for run_id in await repository.list_stalled_runs(db, cutoff):
        run = await repository.load_run(db, run_id)
        if run is None:
            continue

        if not await commands.mark_interrupted(db, run_id=run_id, now=now):
            continue

        await events.eval_run_interrupted(
            db,
            workspace_id=workspace_id,
            actor_id=None,
            prompt_id=run.prompt_id,
            run_id=run_id,
            occurred_at=now,
        )

        run_interrupted_total.inc()
        run_total.labels(status=RunStatus.INTERRUPTED.value).inc()
        reaped += 1

        log.warning(
            "evaluation.run_reaped",
            workspace_id=workspace_id,
            prompt_id=run.prompt_id,
            run_id=run_id,
            status=RunStatus.INTERRUPTED.value,
        )

    return reaped
