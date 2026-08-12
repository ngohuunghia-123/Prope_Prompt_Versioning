import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import list_workspace_ids
from prope.db.session import workspace_transaction
from prope.evaluation.domain import MAX_CONCURRENT_RUNS, ClaimedRun
from prope.evaluation.observability import run_queue_depth
from prope.evaluation.repository import count_queued_runs

log = structlog.get_logger(__name__)

__all__ = ["CLAIM_NEXT_RUN", "claim_next_run", "refresh_queue_depth"]

CLAIM_NEXT_RUN = text(
    """
    SELECT run_id, workspace_id, prompt_id, version_id, suite_id
    FROM   evaluation.claim_next_run(:max_concurrent_runs)
    """
)


async def claim_next_run(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    max_concurrent_runs: int = MAX_CONCURRENT_RUNS,
) -> ClaimedRun | None:
    async with sessionmaker() as session, session.begin():
        row = (
            (
                await session.execute(
                    CLAIM_NEXT_RUN, {"max_concurrent_runs": max_concurrent_runs}
                )
            )
            .mappings()
            .first()
        )

    if row is None:
        return None

    claimed = ClaimedRun(
        run_id=row["run_id"],
        workspace_id=row["workspace_id"],
        prompt_id=row["prompt_id"],
        version_id=row["version_id"],
        suite_id=row["suite_id"],
    )

    log.info(
        "evaluation.run_claimed",
        workspace_id=claimed.workspace_id,
        prompt_id=claimed.prompt_id,
        version_id=claimed.version_id,
        suite_id=claimed.suite_id,
        run_id=claimed.run_id,
    )
    return claimed


async def refresh_queue_depth(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    total = 0
    for workspace_id in await list_workspace_ids(sessionmaker):
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            total += await count_queued_runs(db)

    run_queue_depth.set(total)
    return total
