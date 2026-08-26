from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import list_workspace_ids
from prope.agent_run.repository import (
    advance_improvement_execution,
    claim_runs,
    fail_inline_run,
    finish_improvement_execution,
    start_improvement_execution,
    sync_claimed_run,
)
from prope.db.session import workspace_transaction
from prope.prompt_improvement.sweep import run_manual_improvement


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
            if run["kind"] == "improvement":
                run_id = str(run["id"])
                async with workspace_transaction(sessionmaker, workspace_id) as db:
                    await start_improvement_execution(db, workspace_id=workspace_id, run_id=run_id)
                try:
                    async def advance(sequence: int) -> None:
                        async with workspace_transaction(sessionmaker, workspace_id) as progress_db:
                            await advance_improvement_execution(
                                progress_db, workspace_id=workspace_id,
                                run_id=run_id, sequence=sequence,
                            )

                    action = await run_manual_improvement(
                        sessionmaker, workspace_id, prompt_id=str(run["prompt_id"]),
                        version_id=str(run["version_id"]), on_phase=advance,
                    )
                except Exception:
                    async with workspace_transaction(sessionmaker, workspace_id) as db:
                        await fail_inline_run(db, workspace_id=workspace_id, run_id=run_id)
                    continue
                async with workspace_transaction(sessionmaker, workspace_id) as db:
                    await finish_improvement_execution(
                        db, workspace_id=workspace_id, run_id=run_id,
                        action=action,
                        source_refs=tuple(str(ref) for ref in run["source_refs"]),
                    )
                continue
            async with workspace_transaction(sessionmaker, workspace_id) as db:
                await sync_claimed_run(db, workspace_id=workspace_id, claimed=run)
