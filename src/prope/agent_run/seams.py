"""This module's inbound seams. **Four acts, all of them appends.**

Four modules record a run — evaluation when a suite is dispatched,
prompt-ingestion when a batch is committed, chat-orchestrator when the assistant
executes a plan, and this module's own routes. Until 2026-08-25 the three
outsiders reached `agent_run.repository` and `agent_run.domain` directly, which
put `claim_runs`, `sync_claimed_run`, `read_run` and `list_runs` in reach of a
request handler that wanted to write one row. Only evaluation had a dependency
test to notice.

**`property_history` is the shape this copies**, and for its reason. That module
is a recorder every module writes to and none reads back, allow-listed by name in
each caller's list, and `test_evaluation_depends_on_five_modules` already asserts
the distinction that matters there: *the writer is imported, and
`property_history.models` is not*. A run row is the same kind of thing — an
append that says an act happened, read back through this module's own routes and
nowhere else.

**The other two are chat-orchestrator's, and they exist because that caller
executes its own run.** An assistant turn does not go through `prope.worker` —
the person is waiting on it — so the run it recorded has to be moved off
`queued` and closed by the handler that did the work. `begin_inline_run`, `close_inline_run` and
`fail_inline_run` are that set, and they are the whole of it: none takes a
status, so a caller cannot mark a run `CANCELLED` or put it back to `queued`,
and `close_inline_run` derives `WAITING_FOR_USER` versus `SUCCEEDED` from the
one fact the caller actually holds — whether a confirmation card is on screen.

**What is NOT here is the worker.** `claim_runs` and `sync_claimed_run` are the
executor's, they run in `prope.worker`, and a route that could call them could
mark somebody else's run finished from inside a request. They stay behind the
package boundary this file is the door in.

**Nothing here checks a permission.** The caller has authorised its own act — a
route through `may()`, against the prompt row it read (ADR-0020) — and a second
check here is a second answer that can disagree with the first. `requested_by`
is passed in for the same reason: this module reads no session.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from prope.agent_run.domain import PlanBasis, RunKind
from prope.agent_run.repository import (
    create_run,
    finish_inline_run,
    start_inline_run,
)
from prope.agent_run.repository import fail_inline_run as _fail_inline_run


async def record_run(
    db: AsyncSession,
    *,
    workspace_id: str,
    requested_by: str,
    kind: RunKind,
    plan_basis: PlanBasis,
    idempotency_key: str,
    prompt_id: str | None = None,
    version_id: str | None = None,
    source_refs: tuple[str, ...] = (),
    result_actions: tuple[dict[str, str], ...] = (),
    now: datetime | None = None,
) -> str:
    """Record one run and its planned nodes. Returns the run id.

    **Idempotent on ``idempotency_key``, and the caller depends on that.** A
    second call with the same key returns the first run's id rather than a second
    run — which is what makes a retried request show one entry on the timeline
    instead of two, and what lets a caller record the run and dispatch the work in
    the same transaction without a read-then-branch that could race.

    On the caller's session, deliberately: the run row and the act it describes
    commit together or not at all. A timeline entry for work that rolled back is
    worse than no entry, because it is the one a person would go looking for.
    """
    return await create_run(
        db,
        workspace_id=workspace_id,
        requested_by=requested_by,
        kind=kind,
        plan_basis=plan_basis,
        idempotency_key=idempotency_key,
        prompt_id=prompt_id,
        version_id=version_id,
        source_refs=source_refs,
        result_actions=result_actions,
        now=now,
    )


async def begin_inline_run(db: AsyncSession, *, workspace_id: str, run_id: str) -> None:
    """Move a run off ``queued`` because the caller is executing it itself.

    For a turn a person is waiting on, which `prope.worker` would never see. The
    run is already recorded — this says somebody picked it up.
    """
    await start_inline_run(db, workspace_id=workspace_id, run_id=run_id)


async def close_inline_run(
    db: AsyncSession,
    *,
    workspace_id: str,
    run_id: str,
    evidence_refs: tuple[str, ...],
    waiting_for_user: bool,
) -> None:
    """Close a run the caller executed. ``waiting_for_user`` is not a status.

    It is the one fact the caller holds — whether it left a confirmation card on
    screen — and this module turns it into ``WAITING_FOR_USER`` or ``SUCCEEDED``.
    A caller that could pass the status could close somebody else's run as
    succeeded, which is the difference between a seam and a setter.
    """
    await finish_inline_run(
        db,
        workspace_id=workspace_id,
        run_id=run_id,
        evidence_refs=evidence_refs,
        waiting_for_user=waiting_for_user,
    )


async def fail_inline_run(db: AsyncSession, *, workspace_id: str, run_id: str) -> None:
    """Close a run the caller could not finish. **Not a status either.**

    `close_inline_run`'s other half, and the pair is the whole vocabulary: a
    caller can say *done* or *it fell over*, and nothing else. A node that had
    already succeeded keeps its outcome, so a turn that failed on its last leg
    does not retroactively erase the work that landed.
    """
    await _fail_inline_run(db, workspace_id=workspace_id, run_id=run_id)


__all__ = [
    "PlanBasis",
    "RunKind",
    "begin_inline_run",
    "close_inline_run",
    "fail_inline_run",
    "record_run",
]
