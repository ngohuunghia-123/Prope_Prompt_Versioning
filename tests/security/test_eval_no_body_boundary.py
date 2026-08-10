"""A-055 / T-02-12: the no-body rule, and the fact that only Python enforces it.

**This file asserts an absence, on purpose.** Every other test in this package
proves the engine refuses something. This one proves the engine does *not* —
and that is the point, because A-055 ("no ``call_body`` row will ever exist for
a ``source = 'eval'`` call") is the one guarantee in call-ledger that lives in
application code rather than in the schema.

Migration 0004 records why. A ``CHECK`` cannot reach another table, so the only
database shape that would work is a ``BEFORE INSERT`` trigger on ``call_body``
looking up the referenced ``call_record.source`` on every insert — a per-row
probe on the highest-volume insert path in the system, to duplicate a refusal
``write_records`` already makes at the single choke point, and one
``docs/modules/call-ledger.lock.yml`` never asked for. The trigger is refused as
a **knowing exception** to this project's database-first pattern.

An exception that is merely written down is a belief. So the two halves are
asserted here instead:

1. **The enforcement that exists.** ``write_records`` refuses an eval draft
   carrying a body, by ``ValueError``, naming the ``call_id``, before any row is
   built — so the refusal is whole-batch and nothing is half-written.
2. **The enforcement that does not.** A hand-written ``INSERT INTO
   ledger.call_body`` for a ``source = 'eval'`` record, executed as
   ``prope_migrate``, **succeeds**. If a later revision ever does add the
   trigger, this test goes red, and its failure is the notification that the
   boundary moved.

A later phase that builds a body reader therefore inherits a recorded boundary
rather than a hope: the guarantee holds exactly as far as ``write_records``
reaches, and no further.

``prope_migrate`` is the right role for half 2 and not a convenience. It is the
owner, exempt from the tenant policy by ADR-0035's owner bypass, so a successful
insert is unambiguous evidence about the *table's* constraints rather than about
a grant or a policy that happened to intervene first.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.call_ledger.domain import CallBodyDraft
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from tests.unit import WORKSPACE_A, day, eval_draft

#: Written out here rather than reused from ``tests.security.__init__`` because
#: that helper builds a gateway row: ``ck_call_record_eval_calls_carry_run``
#: requires ``run_id`` AND ``case_id`` and requires ``consumer_key_id`` to be
#: NULL, and it does NOT require ``version_id`` — that one is gateway-only
#: (RESEARCH Pitfall 4). Getting this wrong produces a constraint failure that
#: looks like the thing under test and is not.
INSERT_EVAL_CALL_RECORD = text(
    """
    INSERT INTO ledger.call_record (
        call_id, workspace_id, source, outcome,
        run_id, case_id,
        pinned, fallback, streaming,
        input_tokens, output_tokens, usage_status,
        cost, currency, price_row_id, cost_status,
        created_at
    ) VALUES (
        :call_id, :workspace_id, 'eval', 'ok',
        :run_id, :case_id,
        false, false, false,
        200, 100, 'reported',
        NULL, NULL, NULL, 'unpriced',
        :created_at
    )
    """
)

INSERT_BODY_BY_HAND = text(
    """
    INSERT INTO ledger.call_body (
        call_id, workspace_id, request_body, response_body, byte_size,
        expires_at, created_at
    ) VALUES (
        :call_id, :workspace_id, 'a request', 'a response', 18,
        :expires_at, :created_at
    )
    """
)

COUNT_BODIES = text("SELECT count(*) FROM ledger.call_body WHERE call_id = :call_id")
COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")
READ_SOURCE = text("SELECT source FROM ledger.call_record WHERE call_id = :call_id")

EVAL_CALL_ID = "cal_01J00000000000000000EVAL1"
RUN_ID = "run_01J000000000000000000001"
CASE_ID = "cas_01J000000000000000000001"


async def _seed_eval_record(migrate_engine: AsyncEngine, call_id: str = EVAL_CALL_ID) -> None:
    """One ``source = 'eval'`` record, as the owner, with no body."""
    async with migrate_engine.begin() as connection:
        await connection.execute(
            INSERT_EVAL_CALL_RECORD,
            {
                "call_id": call_id,
                "workspace_id": WORKSPACE_A,
                "run_id": RUN_ID,
                "case_id": CASE_ID,
                "created_at": day(5),
            },
        )


async def test_the_write_path_refuses_an_eval_draft_carrying_a_body(
    app_sessionmaker, migrate_engine
):
    """Half 1: the enforcement that exists, exercised through the real seam.

    The raise happens in the loop before any row is assembled, so the refusal is
    whole-batch — asserted here by writing the eval draft alongside a second,
    perfectly legal draft and then finding that neither landed. A refusal that
    let the batch-mate through would be a partial write, which is the failure
    ``write_records``' all-or-nothing contract exists to prevent.
    """
    poisoned = eval_draft(
        call_id=EVAL_CALL_ID,
        body=CallBodyDraft(request_body="a request", response_body="a response", byte_size=18),
    )
    innocent = eval_draft(call_id="cal_01J00000000000000000EVAL2")

    with pytest.raises(ValueError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await write_records(session, [poisoned, innocent])

    message = str(excinfo.value)
    assert EVAL_CALL_ID in message, "the refusal must name the call it refused"
    assert "A-055" in message

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_RECORDS)).scalar_one() == 0, (
            "the batch-mate landed: the refusal was not whole-batch"
        )


async def test_the_database_carries_no_guard_and_a_hand_written_body_lands(migrate_engine):
    """Half 2: the recorded absence.

    This insert is exactly what a future body-writing code path would do if it
    forgot the rule, and the database accepts it. Nothing is broken by that —
    it is the boundary, written down where it can be re-checked.

    **If this test starts failing, do not "fix" it.** It failing means somebody
    added the database guard, which is a real improvement and a real change to
    what later phases inherit. Delete the test, and delete the exception recorded
    in ``alembic/versions/0004_workspace_retention.py`` in the same change.
    """
    await _seed_eval_record(migrate_engine)

    async with migrate_engine.begin() as control:
        # Positive control: the record really is an eval record. Without this the
        # insert below would prove nothing — a body against a gateway record is
        # allowed by everybody and is not the case under test.
        assert (await control.execute(READ_SOURCE, {"call_id": EVAL_CALL_ID})).scalar_one() == "eval"

        await control.execute(
            INSERT_BODY_BY_HAND,
            {
                "call_id": EVAL_CALL_ID,
                "workspace_id": WORKSPACE_A,
                "expires_at": day(35),
                "created_at": day(5),
            },
        )

    async with migrate_engine.begin() as control:
        landed = (await control.execute(COUNT_BODIES, {"call_id": EVAL_CALL_ID})).scalar_one()

    assert landed == 1, (
        "the insert was refused, so the database HAS acquired a guard for A-055. "
        "That is a change in what later phases inherit: remove this test and the "
        "knowing-exception note in revision 0004 together."
    )
