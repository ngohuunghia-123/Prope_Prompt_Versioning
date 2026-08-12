"""D-09/D-10/D-11: the read the drain makes, and the write the route will make.

Three failure modes shape this file, and none of them looks like a failure from
the reader's side.

**A reader that answers 30 days for everybody looks correct until somebody sets
a window.** So no test here asserts only the default. Every default assertion is
paired with a set-then-read that must come back different, and the tenant test
seeds a *real* window for workspace A before asserting that B still reads the
default — otherwise "B reads 30 days" would pass against a function that reads
nothing at all.

**"No row" and "a row holding exactly the default" must be indistinguishable.**
That is the companion invariant to promoting the retention window from a derived
constant to a stored value: the constant is demoted to *the value returned when
no row exists*, which is one variant of the general case rather than a second
mechanism. A future change that made "unset" and "explicitly 30 days" behave
differently would reintroduce the second source of truth, so it is asserted
directly rather than left to follow from the implementation.

**D-10 is a consequence, not a bug, and is asserted as one.** ``expires_at`` is
stamped once at write and never rewritten, so shortening a window leaves every
already-written body with the expiry it was given. That is checked through
``migrate_engine`` — the owner role, subject to no policy — because reading it
back through the application session would prove the policy was set, not what
the column holds.

Every assertion about stored state goes through ``migrate_engine``. Asking
``read_retention_window`` what it wrote and believing the answer is the shape of
test this file exists to avoid.
"""

from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.call_ledger.retention_settings import (
    read_retention_window,
    set_retention_window,
)
from prope.call_ledger.writer import DEFAULT_RETENTION_WINDOW, write_records
from prope.db.session import workspace_transaction
from tests.unit import WORKSPACE_A, WORKSPACE_B, day, gateway_draft

SEVEN_DAYS = timedelta(days=7)

ACTOR = "usr_01J000000000000000000001"
OTHER_ACTOR = "usr_01J000000000000000000002"

#: The instant handed to every write. A clock is never read, here or in the
#: module under test (``retention.py``'s stated rule, inherited).
NOW = day(10)

READ_ROW = text(
    "SELECT workspace_id, retention_window, updated_by, updated_at "
    "FROM ledger.workspace_retention WHERE workspace_id = :ws"
)
COUNT_ROWS = text("SELECT count(*) FROM ledger.workspace_retention")
READ_EXPIRES_AT = text("SELECT expires_at FROM ledger.call_body WHERE call_id = :call_id")


async def _row(migrate_engine: AsyncEngine, workspace_id: str = WORKSPACE_A):
    """The stored row as the owner. Never through the application session."""
    async with migrate_engine.begin() as control:
        return (await control.execute(READ_ROW, {"ws": workspace_id})).mappings().first()


async def _write_body(app_sessionmaker, call_id: str, *, window: timedelta):
    """One gateway call with a body, stamped by the real write path.

    ``expires_at`` is produced by ``write_records`` from ``created_at`` plus the
    window, rather than written into ``call_body`` by hand, so these tests cannot
    pass against a writer that stamps something else.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await write_records(
            session, [gateway_draft(call_id=call_id, created_at=day(5))], retention_window=window
        )


async def test_a_workspace_with_no_row_reads_the_thirty_day_default(app_sessionmaker):
    """Absence is the default, not an error (D-11).

    call-ledger has no workspace lifecycle to hook and may not read one — the
    ``access`` schema does not exist until phase 7 and this module is forbidden
    an outbound edge to it even then. So a workspace that has never set a window
    is a workspace on the default, and there is nowhere to raise from.
    """
    window = await read_retention_window(app_sessionmaker, WORKSPACE_A)

    assert window == DEFAULT_RETENTION_WINDOW
    assert window == timedelta(days=30), "the constant moved; D-10 and A-040 both name 30 days"


async def test_a_workspace_with_a_row_reads_that_rows_window(app_sessionmaker, migrate_engine):
    """The paired half. Without it the test above passes against a stub."""
    await set_retention_window(
        app_sessionmaker, WORKSPACE_A, SEVEN_DAYS, updated_by=ACTOR, now=NOW
    )

    assert await read_retention_window(app_sessionmaker, WORKSPACE_A) == SEVEN_DAYS
    assert (await _row(migrate_engine))["retention_window"] == SEVEN_DAYS


async def test_setting_a_window_for_a_workspace_with_no_row_inserts_it(
    app_sessionmaker, migrate_engine
):
    """The insert half of the upsert, with the stored row inspected as the owner."""
    assert await _row(migrate_engine) is None, "positive control: nothing is stored yet"

    await set_retention_window(
        app_sessionmaker, WORKSPACE_A, SEVEN_DAYS, updated_by=ACTOR, now=NOW
    )

    row = await _row(migrate_engine)
    assert row is not None
    assert row["retention_window"] == SEVEN_DAYS
    assert row["updated_by"] == ACTOR
    assert row["updated_at"] == NOW

    assert await read_retention_window(app_sessionmaker, WORKSPACE_A) == SEVEN_DAYS


async def test_setting_a_window_twice_updates_in_place(app_sessionmaker, migrate_engine):
    """The update half. One row, the new window, the new actor, the new instant.

    The row count is asserted because ``ON CONFLICT`` failing silently to the
    insert side is not possible, but ``ON CONFLICT`` targeting the wrong column
    would be — and that mistake shows up as a second row, not as an error.
    """
    await set_retention_window(
        app_sessionmaker, WORKSPACE_A, SEVEN_DAYS, updated_by=ACTOR, now=NOW
    )

    later = NOW + timedelta(days=3)
    await set_retention_window(
        app_sessionmaker,
        WORKSPACE_A,
        timedelta(days=14),
        updated_by=OTHER_ACTOR,
        now=later,
    )

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_ROWS)).scalar_one() == 1, "the upsert inserted a second row"

    row = await _row(migrate_engine)
    assert row["retention_window"] == timedelta(days=14)
    assert row["updated_by"] == OTHER_ACTOR
    assert row["updated_at"] == later

    assert await read_retention_window(app_sessionmaker, WORKSPACE_A) == timedelta(days=14)


@pytest.mark.parametrize("window", [timedelta(0), timedelta(days=-1)])
async def test_a_zero_or_negative_window_is_refused_by_the_engine_and_not_clamped(
    app_sessionmaker, migrate_engine, window
):
    """T-02-11. The refusal comes from ``ck_workspace_retention_window_is_positive``.

    A window of zero or less makes every body written after it expire at or
    before the instant it was written — reachable from
    ``PUT /api/v1/workspaces/{id}/retention``, which is why the CHECK is in the
    migration rather than in a validator. The function surfaces the refusal; it
    does not clamp the value into one the caller did not ask for, because a
    silently corrected retention policy is a policy nobody set.
    """
    with pytest.raises(IntegrityError) as excinfo:
        await set_retention_window(
            app_sessionmaker, WORKSPACE_A, window, updated_by=ACTOR, now=NOW
        )

    assert "ck_workspace_retention_window_is_positive" in str(excinfo.value)

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_ROWS)).scalar_one() == 0

    assert await read_retention_window(app_sessionmaker, WORKSPACE_A) == DEFAULT_RETENTION_WINDOW


async def test_one_workspaces_window_is_invisible_to_another(app_sessionmaker, migrate_engine):
    """T-02-09. A missing tenant policy on a new table is a silent cross-tenant read.

    Workspace A's row exists and is seeded first, so a tenant-blind read would
    find it. B must read the default — which is the same answer B would give if
    the reader were broken, so A's own read is asserted alongside as the control
    that distinguishes the two.
    """
    await set_retention_window(
        app_sessionmaker, WORKSPACE_A, SEVEN_DAYS, updated_by=ACTOR, now=NOW
    )

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_ROWS)).scalar_one() == 1, (
            "positive control: A's row must exist, or B's default proves nothing"
        )

    assert await read_retention_window(app_sessionmaker, WORKSPACE_A) == SEVEN_DAYS
    assert await read_retention_window(app_sessionmaker, WORKSPACE_B) == DEFAULT_RETENTION_WINDOW


async def test_an_unset_workspace_and_one_set_to_the_default_are_indistinguishable(
    app_sessionmaker,
):
    """The companion invariant to promoting the window to a stored value.

    ``DEFAULT_RETENTION_WINDOW`` is demoted to *the value returned when no row
    exists* — one variant of the general case, not a parallel mechanism. If a
    later change ever made "unset" and "explicitly 30 days" behave differently,
    there would be two sources of truth for a workspace's window again, and this
    is the assertion that goes red.
    """
    unset = await read_retention_window(app_sessionmaker, WORKSPACE_B)

    await set_retention_window(
        app_sessionmaker,
        WORKSPACE_A,
        DEFAULT_RETENTION_WINDOW,
        updated_by=ACTOR,
        now=NOW,
    )
    explicit = await read_retention_window(app_sessionmaker, WORKSPACE_A)

    assert unset == explicit == DEFAULT_RETENTION_WINDOW


async def test_shortening_a_window_leaves_already_stamped_expiries_alone(
    app_sessionmaker, migrate_engine
):
    """D-10, stated as a consequence and asserted as one.

    A body written under the 30-day default keeps a 30-day expiry after the
    workspace moves to 7 days; a body written afterwards gets 7. So a workspace
    tightening its policy waits up to the OLD window for what it already has, and
    ``oldest_body_age_seconds`` reads above the new window meanwhile.

    No backfill exists and none is wanted: rewriting those stamps is an ``UPDATE``
    on ``ledger.call_body``, and Phase 1 granted ``prope_app`` ``SELECT``,
    ``INSERT`` and ``DELETE`` there and deliberately no ``UPDATE``.
    """
    before_id = "cal_01J0000000000000000BEFORE"
    after_id = "cal_01J00000000000000000AFTER"

    wide = await read_retention_window(app_sessionmaker, WORKSPACE_A)
    assert wide == DEFAULT_RETENTION_WINDOW
    await _write_body(app_sessionmaker, before_id, window=wide)

    await set_retention_window(
        app_sessionmaker, WORKSPACE_A, SEVEN_DAYS, updated_by=ACTOR, now=NOW
    )

    narrow = await read_retention_window(app_sessionmaker, WORKSPACE_A)
    assert narrow == SEVEN_DAYS
    await _write_body(app_sessionmaker, after_id, window=narrow)

    async with migrate_engine.begin() as control:
        before_expiry = (
            await control.execute(READ_EXPIRES_AT, {"call_id": before_id})
        ).scalar_one()
        after_expiry = (await control.execute(READ_EXPIRES_AT, {"call_id": after_id})).scalar_one()

    # Both bodies were created on day 5, so the two expiries differ by exactly
    # the difference between the two windows and nothing else.
    assert before_expiry == day(5) + DEFAULT_RETENTION_WINDOW, (
        "the earlier body's expires_at moved when the window was shortened; "
        "expires_at is stamped once at write and never rewritten (D-10)"
    )
    assert after_expiry == day(5) + SEVEN_DAYS
