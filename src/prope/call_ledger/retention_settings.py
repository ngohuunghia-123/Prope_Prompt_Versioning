"""D-09/D-11: the per-workspace retention window — one read, one write.

``ledger.workspace_retention`` is the sixth table this module owns, and it is a
declared deviation from ``docs/modules/call-ledger.lock.yml`` ``data.owns``,
which names five. The conflict is raised as
``docs/brainstorm/open_questions/OQ-018.md``; the spec is not edited to agree.
``alembic/versions/0004_workspace_retention.py`` carries the argument for the
separate table and D-10's stamped-once consequence at length.

**THE DRAIN READS THIS. ``write_records`` DOES NOT** (D-11). The drain's batch is
already grouped per workspace, so it reads one indexed row per group and hands
``retention_window`` in. That split is load-bearing in two directions:
``write_records`` stays a pure function of its arguments, and Phase 3's
direct-write fallback — the path that runs when the broker is already down — must
not inherit a settings query on the way to being the thing that saves the record.

**Absence of a row is the default, not an error.** call-ledger has no workspace
lifecycle to hook and may not read one: the ``access`` schema does not exist
until Phase 7, and this module is forbidden an outbound edge to it even then. So
a workspace that has never set a window is a workspace on
``writer.DEFAULT_RETENTION_WINDOW``, and there is nowhere here to raise from.
That constant is imported rather than restated — a second literal ``30`` in this
file would be exactly the second source of truth that storing the window was
supposed to remove.

**Both functions open their own transaction** and never accept a caller's
session, the same posture ``delete_expired_bodies`` takes. The tenant policy
supplies the predicate underneath the explicit one, so a row belonging to another
workspace is refused twice over — and a caller who forgot the seam gets zero
rows, which reads as the default, which is the correct answer for a workspace
whose row they could not have seen anyway.

**The clock is passed in, never read**, matching ``retention.py``'s stated rule.
``updated_at`` is the caller's instant rather than the column's ``now()``
default, so a test asserting when a window was set is arithmetic on the fixture
calendar rather than a clock nobody can move.

**This module writes no body, emits no log and no metric** (A-046). A retention
window is a policy value, but the workspace id beside it is a tenant identifier,
and the rule that keeps identifiers out of metric labels is the same one that
keeps bodies out of log lines.
"""

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.writer import DEFAULT_RETENTION_WINDOW
from prope.db.session import workspace_transaction

#: A primary-key lookup returning at most one row — ``pk_workspace_retention``
#: is ``(workspace_id)``, so this is one index probe and one heap fetch with no
#: sort and no filter. That is what makes D-11's per-group read affordable inside
#: the drain's window: one probe per workspace in the batch, not one per record.
#:
#: The ``workspace_id`` predicate is written out alongside the tenant policy
#: rather than instead of it. The policy remains the enforcement; the explicit
#: predicate is what makes the index probe a property of the statement rather
#: than of a planner choice. It is bound, like every tenant identifier in this
#: codebase.
READ_RETENTION_WINDOW = text(
    """
    SELECT retention_window
    FROM   ledger.workspace_retention
    WHERE  workspace_id = :workspace_id
    """
)

#: The write ``PUT /api/v1/workspaces/{id}/retention`` makes. An upsert rather
#: than a read-then-branch: "set this workspace's window" has one outcome
#: whichever way it happens, and a caller that had to know which one would be a
#: caller that could get it wrong under a concurrent first write.
#:
#: ``updated_at`` is assigned from the bound instant rather than left to the
#: column default, because the column default is ``now()`` and this module reads
#: no clock.
#:
#: ``ck_workspace_retention_window_is_positive`` is what refuses a zero or
#: negative window, at the engine. Nothing here re-checks it and nothing clamps:
#: a retention policy silently corrected into one the caller did not ask for is a
#: policy nobody set.
UPSERT_RETENTION_WINDOW = text(
    """
    INSERT INTO ledger.workspace_retention (
        workspace_id, retention_window, updated_by, updated_at
    ) VALUES (
        :workspace_id, :retention_window, :updated_by, :updated_at
    )
    ON CONFLICT (workspace_id) DO UPDATE SET
        retention_window = EXCLUDED.retention_window,
        updated_by       = EXCLUDED.updated_by,
        updated_at       = EXCLUDED.updated_at
    """
)


async def read_retention_window(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
) -> timedelta:
    """This workspace's retention window, or the 30-day default if it has none.

    **This is the resolver the drain accepts through its ``retention_for``
    keyword-only argument** (``prope.call_ledger.drain``), and ``prope.worker``
    is what passes it — plan 02-03. Said at the definition rather than left to
    discipline, because D-11 names the two-caller risk explicitly: the drain must
    read this and ``write_records`` must not, and a seam with a name is what
    keeps that a fact instead of a convention.

    Returns ``writer.DEFAULT_RETENTION_WINDOW`` when no row exists. That is a
    complete answer and never an error: absence means "never configured", which
    is precisely the state the default describes.
    """
    async with workspace_transaction(sessionmaker, workspace_id) as session:
        stored = (
            await session.execute(READ_RETENTION_WINDOW, {"workspace_id": workspace_id})
        ).scalar_one_or_none()

    return stored if stored is not None else DEFAULT_RETENTION_WINDOW


async def set_retention_window(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    window: timedelta,
    *,
    updated_by: str,
    now: datetime,
) -> None:
    """Set this workspace's retention window. Insert or update, one outcome.

    Raises whatever the engine raises for a window that is not strictly positive
    — ``ck_workspace_retention_window_is_positive`` — rather than clamping it.
    The refusal is the answer: a caller asking for a zero-day window is asking
    for every body to expire at the instant it is written, and a value quietly
    replaced with a legal one would leave them believing the request took effect.

    Takes effect for bodies written **after** it and for no others (D-10).
    ``expires_at`` is stamped once by ``write_records`` and never rewritten, so
    shortening a window leaves the existing rows on the expiry they were given
    and the workspace waits out the old window for them. There is no backfill,
    and building one would mean widening ``prope_app``'s grant on
    ``ledger.call_body`` — which holds ``SELECT``, ``INSERT`` and ``DELETE`` and
    deliberately no ``UPDATE``.
    """
    async with workspace_transaction(sessionmaker, workspace_id) as session:
        await session.execute(
            UPSERT_RETENTION_WINDOW,
            {
                "workspace_id": workspace_id,
                "retention_window": window,
                "updated_by": updated_by,
                "updated_at": now,
            },
        )
