from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import list_workspace_ids
from prope.agent_run.repository import claim_runs, sync_claimed_run
from prope.db.session import workspace_transaction


async def sync_agent_runs(
    sessionmaker: async_sessionmaker[AsyncSession], *, worker_id: str = "agent-run-worker",
) -> None:
    """Claim and reconcile runs from durable source records, one tenant at a time."""
    for workspace_id in await list_workspace_ids(sessionmaker):
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            claimed = await claim_runs(
                db, workspace_id=workspace_id, worker_id=worker_id,
            )
            for run in claimed:
                await sync_claimed_run(db, workspace_id=workspace_id, claimed=run)
