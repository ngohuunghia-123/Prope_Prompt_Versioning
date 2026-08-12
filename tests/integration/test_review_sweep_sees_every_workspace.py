"""AC-13 — the sweep sees a workspace no request has touched, and the negative half is the point.

ADR-0051 exists because of one defect that would have shipped silently. Computed
the obvious way — one unscoped query from ``app`` — both review-task gauges would
read **0 forever** under ADR-0045's deny-by-default policy,
``BreakGlassTaskOverdue`` would never fire, and nothing anywhere would indicate
that the only control keeping break-glass exceptional was dead. A gauge that is
always zero and a system with nothing overdue are indistinguishable from a graph.

So this file asserts both halves against the same data:

* the **sweep**, which enumerates workspaces through ``access.list_workspaces()``
  and issues ``SET LOCAL app.workspace_id`` per workspace, counts the overdue
  task in a workspace this process has never served a request for;
* the **same query without the enumeration** counts zero — which is what the
  policy correctly returns, and what would have shipped.

The second is not a test of Postgres. It is the evidence that the first one is
load-bearing rather than decorative.
"""

from datetime import timedelta

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.release_control.repository import COUNT_OVERDUE_REVIEW_TASKS
from prope.release_control.sweep import (
    reconcile_released_pointers,
    refresh_review_task_gauges,
)
from tests.access_control import WORKSPACE_A, WORKSPACE_B, seed_workspace
from tests.release_control import utc_now

QUIET_WORKSPACE = WORKSPACE_B

BUSY_WORKSPACE = WORKSPACE_A

OVERDUE_TASK = "rvt_01J0000000000000OVERDUE01"

OPEN_TASK = "rvt_01J00000000000000000OPEN1"

INSERT_TASK = text(
    """
    INSERT INTO release.review_task (
        id, workspace_id, prompt_id, version_id, kind, assigned_role, due_at,
        status, created_from_release_id, created_at
    ) VALUES (
        :id, :workspace_id, :prompt_id, :version_id, :kind, 'Reviewer', :due_at,
        'open', :created_from_release_id, :created_at
    )
    """
)

INSERT_RELEASE = text(
    """
    INSERT INTO release.release (
        id, workspace_id, prompt_id, version_id, kind, previous_version_id,
        approval_id, break_glass, reason, released_by, released_at
    ) VALUES (
        :id, :workspace_id, :prompt_id, :version_id, 'release', NULL,
        NULL, true, 'incident', :released_by, :released_at
    )
    """
)

BREAK_GLASS_RELEASE = "rel_01J0000000000000QUIET001"

QUIET_PROMPT = "prm_01J000000000000000QUIET01"

QUIET_VERSION = "rev_01J000000000000000QUIET01"


def _overdue() -> float:
    return REGISTRY.get_sample_value("prope_release_review_task_overdue") or 0.0


def _open(kind: str) -> float:
    return REGISTRY.get_sample_value("prope_release_review_task_open", {"kind": kind}) or 0.0


def _passes(name: str) -> float:
    return REGISTRY.get_sample_value("prope_release_sweep_pass_total", {"pass": name}) or 0.0


async def _an_overdue_task_in_a_workspace_nothing_has_touched(
    migrate_engine: AsyncEngine,
) -> None:
    """A break-glass follow-up whose release happened yesterday, in workspace B.

    Seeded through the owner rather than through the routes, because the subject
    is the SWEEP: driving a break-glass release would put the task in the
    workspace whose session the request carried, which is the workspace the
    obvious implementation can already see.
    """
    await seed_workspace(migrate_engine, BUSY_WORKSPACE)
    await seed_workspace(migrate_engine, QUIET_WORKSPACE, slug="quiet")

    now = utc_now()
    async with migrate_engine.begin() as connection:
        # The release comes first: `ck_review_task_break_glass_followup_names_its_
        # release` refuses a follow-up that cannot say what it is following up on,
        # which is what keeps the 24 h task attached to the act it exists to
        # review rather than floating in a queue.
        await connection.execute(
            INSERT_RELEASE,
            {
                "id": BREAK_GLASS_RELEASE,
                "workspace_id": QUIET_WORKSPACE,
                "prompt_id": QUIET_PROMPT,
                "version_id": QUIET_VERSION,
                "released_by": "usr_01J00000000000000000ADMIN",
                "released_at": now - timedelta(hours=25),
            },
        )
        await connection.execute(
            INSERT_TASK,
            {
                "id": OVERDUE_TASK,
                "workspace_id": QUIET_WORKSPACE,
                "prompt_id": QUIET_PROMPT,
                "version_id": QUIET_VERSION,
                "kind": "break_glass_followup",
                "due_at": now - timedelta(hours=1),
                "created_from_release_id": BREAK_GLASS_RELEASE,
                "created_at": now - timedelta(hours=25),
            },
        )
        await connection.execute(
            INSERT_TASK,
            {
                "id": OPEN_TASK,
                "workspace_id": BUSY_WORKSPACE,
                "prompt_id": "prm_01J0000000000000000BUSY01",
                "version_id": "rev_01J0000000000000000BUSY01",
                "kind": "review",
                "due_at": None,
                "created_from_release_id": None,
                "created_at": now,
            },
        )


async def test_the_sweep_counts_a_task_in_a_workspace_no_request_has_touched(
    migrate_engine: AsyncEngine, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _an_overdue_task_in_a_workspace_nothing_has_touched(migrate_engine)

    before = _passes("review_task_gauges")
    await refresh_review_task_gauges(app_sessionmaker, now=utc_now())

    assert _overdue() == 1.0
    assert _open("break_glass_followup") == 1.0
    assert _open("review") == 1.0
    assert _passes("review_task_gauges") == before + 1


async def test_the_same_query_without_the_enumeration_counts_zero(
    migrate_engine: AsyncEngine, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """The negative half, and the whole reason ADR-0051 exists.

    ``prope_app`` with no ``app.workspace_id`` set matches nothing, so the obvious
    one-statement implementation answers **zero rows** — the tenant policy working
    exactly as designed, and the worst possible answer for a must-stay-non-zero
    gauge. This is what would have shipped, and it is asserted so the enumeration
    above cannot be "simplified" away in a later pass.
    """
    await _an_overdue_task_in_a_workspace_nothing_has_touched(migrate_engine)

    async with app_sessionmaker() as session:
        async with session.begin():
            unscoped = await session.scalar(COUNT_OVERDUE_REVIEW_TASKS, {"now": utc_now()})

    assert unscoped == 0

    async with migrate_engine.begin() as connection:
        as_owner = await connection.scalar(COUNT_OVERDUE_REVIEW_TASKS, {"now": utc_now()})

    assert as_owner == 1, "the row is there; only the runtime role cannot see it unscoped"


async def test_the_gauges_drop_back_when_the_task_is_closed(
    migrate_engine: AsyncEngine, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """A sweep that only ever counted up would look identical to a stuck one."""
    await _an_overdue_task_in_a_workspace_nothing_has_touched(migrate_engine)
    await refresh_review_task_gauges(app_sessionmaker, now=utc_now())
    assert _overdue() == 1.0

    async with migrate_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE release.review_task SET status = 'closed', closed_by = 'usr_x', "
                "closed_at = now() WHERE id = :id"
            ),
            {"id": OVERDUE_TASK},
        )

    await refresh_review_task_gauges(app_sessionmaker, now=utc_now())

    assert _overdue() == 0.0
    assert _open("break_glass_followup") == 0.0


async def test_the_reconciliation_finds_a_release_with_no_approval_across_workspaces(
    migrate_engine: AsyncEngine, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """The Success-metric SQL as a series, swept the same way and for the same reason.

    ``ReleaseWithoutApproval`` pages, and its condition is a query rather than a
    counter. The seeded release is ``break_glass = true`` — legitimate, and it
    must NOT be counted.

    **The offending state is unreachable while the constraint stands, and that is
    asserted first.** Flipping ``break_glass`` to false is refused by
    ``ck_release_approval_absent_only_for_break_glass`` even for the OWNER, which
    is the whole reason this alert's description says *firing means the
    constraint is gone*. So the constraint is DROPPED for the duration of the
    third act — the only way to reach the state the gauge exists to report — and
    restored afterwards. A test that could not produce the state at all would be
    asserting that the gauge is always zero, which is what a dead gauge looks
    like.
    """
    import sqlalchemy.exc

    await _an_overdue_task_in_a_workspace_nothing_has_touched(migrate_engine)

    before = _passes("released_pointer_reconciliation")
    await reconcile_released_pointers(app_sessionmaker)

    assert (REGISTRY.get_sample_value("prope_release_without_approval_rows") or 0.0) == 0.0
    assert _passes("released_pointer_reconciliation") == before + 1

    async with migrate_engine.begin() as connection:
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            async with connection.begin_nested():
                await connection.execute(
                    text("UPDATE release.release SET break_glass = false WHERE id = :id"),
                    {"id": BREAK_GLASS_RELEASE},
                )

    async with migrate_engine.begin() as connection:
        await connection.execute(
            text(
                "ALTER TABLE release.release "
                "DROP CONSTRAINT ck_release_approval_absent_only_for_break_glass"
            )
        )
        await connection.execute(
            text("UPDATE release.release SET break_glass = false WHERE id = :id"),
            {"id": BREAK_GLASS_RELEASE},
        )

    try:
        await reconcile_released_pointers(app_sessionmaker)
        assert (REGISTRY.get_sample_value("prope_release_without_approval_rows") or 0.0) == 1.0
    finally:
        async with migrate_engine.begin() as connection:
            await connection.execute(
                text("UPDATE release.release SET break_glass = true WHERE id = :id"),
                {"id": BREAK_GLASS_RELEASE},
            )
            await connection.execute(
                text(
                    "ALTER TABLE release.release "
                    "ADD CONSTRAINT ck_release_approval_absent_only_for_break_glass "
                    "CHECK (approval_id IS NOT NULL OR break_glass OR version_id IS NULL)"
                )
            )
