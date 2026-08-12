"""CL-08: the bounded-chunk delete that removes expired bodies and nothing else.

``ledger.call_body`` holds raw end-user request and response payloads. It is the
highest-liability data in Prope and it has the fewest ways to reach it, on
purpose (ADR-0018): no endpoint, no export, no admin viewer, no debug route, no
accessor, and no join from another module's query. **This module does not
create one.** The statement below is the single statement in the MVP that
touches the table for anything other than an insert, and it projects the
physical row locator — ``ctid`` — rather than any stored column, so even here
there is nothing to read.

**The cut-off is passed in.** ``now`` is an argument and never a clock read, in
this module or in the SQL. AC-8's "bodies written 31 days ago with a 30-day
retention window" is then plain arithmetic on ``datetime`` values, with no clock
to freeze — which matters because no Python time-travel library can move the
*server's* clock, so a design that asked the database what time it is would not
have been testable at all.

**One transaction per chunk (OQ-D).** ADR-0040 says the job "deletes each one's
expired bodies in bounded chunks inside that workspace's transaction". Read
literally, the singular puts every chunk in one transaction — which holds every
row lock and the whole snapshot for the duration of the run, and therefore
delivers none of the benefit chunking exists for. The lock file's chaos plan
runs this job concurrently with peak writes and requires the writer's lag to
stay inside its target, which only short transactions can satisfy. The adopted
reading: **each transaction covers exactly one workspace and carries its own
tenant context**, and every chunk gets one. The policy's check clause still
applies to each, no transaction is long-lived, and the row locks are released
between chunks. Raised upstream as OQ-D; the ADR is not edited.

**The workspace predicate is written out, alongside the policy rather than
instead of it.** The tenant policy's ``USING`` qualifier restricts these rows
anyway and remains the enforcement. But it reaches the ``(workspace_id,
expires_at)`` index only if the planner chooses to, and ADR-0040's "index scan
rather than a join" requirement should not rest on a planner choice. The
explicit predicate makes the index scan a property of the statement. It is
bound, like every tenant identifier in this codebase — never assembled into the
SQL by any means.

**No scheduler and no cross-tenant enumerator ship here (OQ-C).** This function
is called with one workspace id. The ``worker`` process that would host a timer
arrives in Phase 2, and the enumerator ADR-0051 designates for the cross-tenant
sweep lives in a schema that does not exist until Phase 7 — and reaching for it
would mean either a forbidden dependency or a fifth privilege-escalating
database routine, when a project test asserts the sanctioned set is exactly
four. No such routine is created here, and no timer library enters the build.
CL-08 and AC-8 are satisfied in full for one workspace at a time; the sweep that
visits all of them is carried upstream rather than improvised.

**Space returns to the table's free list, not to the disk.** A-132 states and
accepts that. Do not "fix" it with a full rewrite of the table: that takes an
exclusive lock on the largest relation in the system, which is the outage this
whole chunked shape exists to avoid.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction

#: A6 — a tunable judgement, not a repo decision, recorded so that changing it
#: is a visible act. The stated target is one day's expired bodies, up to
#: 500,000 rows in a batch, removed within ten minutes. At this size that is 100
#: chunks, which has ample headroom; the number is unvalidated at real scale.
DEFAULT_CHUNK_SIZE = 5_000

#: One chunk. The inner select names rows by their physical locator and nothing
#: else — no stored column is read, so the one statement that may touch this
#: table cannot quietly become its reader.
#:
#: The locator is re-derived on every iteration, never cached across them: a
#: physical locator identifies where a row lives right now, and a row that has
#: been updated or vacuumed since lives somewhere else.
#:
#: **There is deliberately no locking clause, and the reason is a privilege.**
#: A7 proposed selecting the chunk with a row lock that skips rows already
#: locked, which would make the job safe to run concurrently with itself and
#: with the writer. PostgreSQL requires the ``UPDATE`` privilege for a locking
#: select, and the runtime role's grants on this table are ``SELECT``,
#: ``INSERT`` and ``DELETE`` — no ``UPDATE``, so that a stored body cannot be
#: altered by the role that serves traffic. Asking for the lock returns
#: ``permission denied for table call_body``; the identical statement without
#: it succeeds. A7 states the lock is a safety improvement and not a
#: requirement, so it is dropped rather than bought by widening a grant that
#: exists to stop exactly this. The cost is recorded rather than hidden: two
#: concurrent runs of this job can now contend on the same rows instead of
#: stepping around each other. Nothing in the MVP runs two — there is no
#: scheduler — and restoring the property is a grant decision for a later
#: phase, not a silent edit here.
DELETE_CHUNK = text(
    """
    WITH victims AS (
        SELECT ctid
        FROM   ledger.call_body
        WHERE  workspace_id = :ws
          AND  expires_at  <= :cut_off_at
        ORDER  BY expires_at
        LIMIT  :chunk_size
    )
    DELETE FROM ledger.call_body b
    USING  victims v
    WHERE  b.ctid = v.ctid
    """
)

#: What ``on_chunk`` must look like: awaited with the rows this chunk removed
#: and the running total.
ChunkObserver = Callable[[int, int], Awaitable[None]]


async def delete_expired_bodies(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    *,
    now: datetime,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_chunks: int | None = None,
    on_chunk: ChunkObserver | None = None,
) -> int:
    """Delete this workspace's bodies expired at or before ``now``. Returns the count.

    Every chunk opens its own ``workspace_transaction`` — the tenant seam, so
    the transaction is opened before the tenant is set and carries exactly one
    workspace. The loop ends when a chunk removes fewer rows than it asked for,
    which is how it learns there is no more work without a second round trip to
    find out, or when ``max_chunks`` iterations have run.

    ``on_chunk`` is an **observation seam and nothing else**. It is keyword-only,
    defaults to ``None``, and when it is ``None`` the branch is not taken: the
    production call path supplies no callback and behaves exactly as it would
    without the parameter. When supplied it is awaited **after** that chunk's
    transaction has committed and **before** the next one opens — that placement
    is the entire point, because one transaction per chunk is observable only
    from inside a running multi-chunk loop. Once the call has returned, a
    per-chunk implementation and a loop-wide one are indistinguishable: both
    must have committed to have persisted anything.

    A callback that raises propagates. In the test it is carrying an assertion,
    and swallowing it would turn a failed proof into a passing one.

    Raises ``ValueError`` for a ``chunk_size`` below 1 or a ``max_chunks`` below
    1, before opening any transaction. That is WARN-1: with ``chunk_size=0`` the
    statement deletes nothing, ``0 < 0`` is false so the short-chunk exit never
    fires, and ``max_chunks`` defaults to ``None`` so the bound never fires
    either — an infinite loop opening a transaction per iteration. D-12 wires an
    operator-supplied value into this function in plan 02-03, which is why the
    guard lands with the phase that builds the scheduler and not after it.
    """
    if chunk_size < 1:
        raise ValueError(
            f"chunk_size is {chunk_size}; a chunk must ask for at least one row. A chunk of zero "
            "or fewer deletes nothing, never returns short, and so never ends the loop — it opens "
            "a transaction per iteration forever"
        )
    if max_chunks is not None and max_chunks < 1:
        raise ValueError(
            f"max_chunks is {max_chunks}; a bound must permit at least one chunk. None is how a "
            "caller asks for an unbounded run, and a bound of zero or fewer is neither that nor a "
            "run — the loop would still execute its first chunk before testing the bound"
        )

    deleted_total = 0
    chunks_run = 0

    while True:
        async with workspace_transaction(sessionmaker, workspace_id) as session:
            result = await session.execute(
                DELETE_CHUNK,
                {"ws": workspace_id, "cut_off_at": now, "chunk_size": chunk_size},
            )
            deleted_in_chunk = result.rowcount
        # The transaction is committed here, and the next one has not opened.
        # Row locks and the snapshot are released; another session can see what
        # this chunk did.

        deleted_total += deleted_in_chunk
        chunks_run += 1

        if on_chunk is not None:
            await on_chunk(deleted_in_chunk, deleted_total)

        if deleted_in_chunk < chunk_size:
            # A short chunk means the predicate has no more rows to offer.
            break
        if max_chunks is not None and chunks_run >= max_chunks:
            break

    return deleted_total
