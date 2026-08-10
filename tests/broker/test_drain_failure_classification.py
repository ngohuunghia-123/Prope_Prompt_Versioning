"""The drain's failure classification, and CR-01's second named test.

Every write failure the drain can meet is either **permanent** — the record can
never be written as it is, so redelivery cannot help — or **transient** — the
moment was wrong, not the record. A permanent failure is rejected without
requeue so it dead-letters and is counted; a transient one is nacked with
requeue and the drain backs off. **A permanent failure is never requeued**: a
classic queue has no ``x-delivery-limit`` (the accepted cost of the Task 1
queue-type decision), so a permanently-failing record that is requeued is an
infinite loop with nothing to stop it.

**The Phase 2 gap this file makes visible, by name.** At-least-once delivery
begins in THIS phase, while the idempotent upsert on ``call_id`` that makes a
redelivery safe is **CL-02, in Phase 3**. ``ledger.call_record``'s primary key
is ``call_id`` alone and ``write_records`` issues a plain ``INSERT``, so a
redelivered record raises a unique violation, which this module classifies as
permanent and dead-letters. The consequence, stated plainly: **an ordinary
consumer restart dead-letters records that were already written.** That is a
real, named Phase 2 gap that CL-02 closes — not an accident, and not a bug to be
filed. The alternative (treat a unique violation as "already written, ack it")
was rejected because it is CL-02's guarantee arriving early under another name.

**CR-01's second named test is ``test_one_unwritable_record_does_not_discard_its
_batch_mates``.** ``write_records`` is all-or-nothing by design, which is
correct and is also why one poison record would otherwise take four innocent
ones with it. The drain answers that by retrying a failed group one record at a
time.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.broker.connection import build_connection
from prope.broker.topology import DLQ, WORK_QUEUE, declare_topology
from prope.call_ledger.domain import CallBodyDraft
from prope.call_ledger.drain import WriteFailure, classify_write_failure
from prope.db.session import workspace_transaction
from tests.broker._helpers import drain_until, publish_bodies, publish_drafts, queue_depth
from tests.unit import WORKSPACE_A, eval_draft, gateway_draft

COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")


async def _committed(migrate_engine: AsyncEngine) -> int:
    """Rows in ``ledger.call_record``, read as the OWNER — never via the drain."""
    async with migrate_engine.begin() as connection:
        return (await connection.execute(COUNT_RECORDS)).scalar_one()


async def _dlq_depth(amqp_url: str) -> int:
    connection = await build_connection(amqp_url)
    async with connection:
        return await queue_depth(connection, DLQ)


# --------------------------------------------------------------------------
# The classification itself
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        # write_records' four ValueError refusals, and the envelope's.
        (ValueError("batch spans 2 workspaces"), WriteFailure.PERMANENT),
        (ValueError("batch mixes currencies USD and VND"), WriteFailure.PERMANENT),
        (ValueError("is source=eval and carries a body"), WriteFailure.PERMANENT),
        (ValueError("prices to 0 against price row"), WriteFailure.PERMANENT),
        # The unique violation on call_id that arrives on ordinary redelivery.
        (IntegrityError("INSERT", {}, Exception("duplicate key")), WriteFailure.PERMANENT),
        # Ask again later.
        (OperationalError("SELECT", {}, Exception("connection lost")), WriteFailure.TRANSIENT),
        (InterfaceError("SELECT", {}, Exception("cannot perform operation")), WriteFailure.TRANSIENT),
        (ConnectionResetError("connection reset by peer"), WriteFailure.TRANSIENT),
        (TimeoutError(), WriteFailure.TRANSIENT),
    ],
)
def test_every_failure_is_classified(error: BaseException, expected: WriteFailure) -> None:
    assert classify_write_failure(error) is expected


def test_an_unrecognised_failure_defaults_to_permanent() -> None:
    """The default is what stops T-02-06, and it is asserted rather than assumed.

    A classic queue has no delivery limit. Defaulting to transient would requeue
    an error nobody classified, forever; defaulting to permanent loses one
    record into a place somebody can look at.
    """
    assert classify_write_failure(RuntimeError("nobody has seen this before")) is (
        WriteFailure.PERMANENT
    )


# --------------------------------------------------------------------------
# The batch-mate rule — CR-01's second named test
# --------------------------------------------------------------------------


async def test_one_unwritable_record_does_not_discard_its_batch_mates(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """Five records, one of which ``write_records`` refuses: four commit, one dead-letters.

    The refused record is ``source=eval`` carrying a body — A-055's rule, which
    is enforced in ``write_records`` and has no database constraint behind it.
    It is refused before anything is written, which is exactly why the whole
    group would otherwise be lost.

    Both halves are asserted, and both are necessary: four committed rows
    without one DLQ message would mean the poison record vanished, and one DLQ
    message without four rows would mean the batch was discarded.
    """
    drafts = [
        gateway_draft(call_id=f"cal_{index:026d}", workspace_id=WORKSPACE_A)
        for index in range(4)
    ]
    poison = eval_draft(
        call_id="cal_poison00000000000000000",
        workspace_id=WORKSPACE_A,
        body=CallBodyDraft(request_body="refused", response_body="refused", byte_size=7),
    )
    await publish_drafts(amqp_url, [*drafts[:2], poison, *drafts[2:]])

    landed = await drain_until(
        amqp_url, app_sessionmaker, lambda: _four_committed(migrate_engine)
    )
    assert landed, "the four writable records never committed"

    assert await _committed(migrate_engine) == 4
    assert await _dlq_depth(amqp_url) == 1, "exactly the offender, and only the offender"


async def _four_committed(migrate_engine: AsyncEngine) -> bool:
    return await _committed(migrate_engine) == 4


# --------------------------------------------------------------------------
# The envelope gate
# --------------------------------------------------------------------------


async def test_an_invalid_envelope_dead_letters_without_opening_a_transaction(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-02-01: a workspace_id that failed its gate never reaches set_config.

    The assertion is not "the record was not written" — that would also be true
    if the transaction had opened and rolled back. It is that
    ``workspace_transaction`` was **never entered**, which is the only form of
    the claim that says the untrusted value never reached the tenant seam.
    """
    entered: list[str] = []

    def _spy(
        sessionmaker: async_sessionmaker[AsyncSession], workspace_id: str
    ) -> AsyncIterator[AsyncSession]:
        entered.append(workspace_id)
        return workspace_transaction(sessionmaker, workspace_id)

    monkeypatch.setattr("prope.call_ledger.drain.workspace_transaction", _spy)

    await publish_bodies(
        amqp_url,
        [
            b'{"schema_version": 99, "call_id": "cal_x", "workspace_id": "wsp_a",'
            b' "occurred_at": "2026-08-10T00:00:00Z", "producer": "app", "payload": {}}',
            b'{"schema_version": 1, "call_id": "cal_y", "workspace_id": "wsp bad space",'
            b' "occurred_at": "2026-08-10T00:00:00Z", "producer": "app", "payload": {}}',
            b"this is not json at all",
        ],
    )

    dead_lettered = await drain_until(
        amqp_url, app_sessionmaker, lambda: _dlq_reached(amqp_url, 3)
    )

    assert dead_lettered, "all three malformed envelopes should have dead-lettered"
    assert entered == [], "workspace_transaction was entered for an unvalidated envelope"


async def _dlq_reached(amqp_url: str, expected: int) -> bool:
    return await _dlq_depth(amqp_url) >= expected


# --------------------------------------------------------------------------
# Redelivery
# --------------------------------------------------------------------------


async def test_unacknowledged_messages_are_redelivered_after_a_consumer_restart(
    amqp_url: str,
) -> None:
    """At-least-once, asserted against the broker rather than assumed from the docs.

    This is the property that makes CL-02's upsert necessary, and asserting it
    here is what makes the Phase 2 gap in this module's docstring a measured
    statement rather than a worry.
    """
    await publish_drafts(
        amqp_url,
        [gateway_draft(call_id=f"cal_{index:026d}") for index in range(3)],
    )

    received: list[str] = []

    # First consumer: takes all three and acknowledges none, then goes away.
    connection = await build_connection(amqp_url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        queue = await declare_topology(channel)
        async with queue.iterator() as messages:
            async for message in messages:
                received.append(message.message_id or "")
                if len(received) == 3:
                    break

    assert len(received) == 3

    # Second consumer: the same three come back.
    redelivered = 0
    connection = await build_connection(amqp_url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        queue = await channel.get_queue(WORK_QUEUE)
        async with queue.iterator() as messages:
            async for message in messages:
                assert message.redelivered, "the broker marks a second delivery as redelivered"
                await message.ack()
                redelivered += 1
                if redelivered == 3:
                    break

    assert redelivered == 3, "every unacknowledged message is delivered again"


# --------------------------------------------------------------------------
# The retention resolver's shape
# --------------------------------------------------------------------------


async def test_the_retention_resolver_is_called_with_exactly_the_workspace_id(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """One positional argument, the workspace_id — the signature 02-03 must bind to.

    Plan 02-02's real reader is ``read_retention_window(sessionmaker,
    workspace_id)``, which is NOT assignable here; plan 02-03 binds the
    sessionmaker with ``functools.partial`` first. Passing the bare two-argument
    function would type-check under a loose annotation and raise ``TypeError``
    on the first workspace group at runtime, inside a consumer. This test is
    what makes that a red build rather than an incident.
    """
    seen: list[str] = []

    async def _resolver(workspace_id: str) -> timedelta:
        seen.append(workspace_id)
        return timedelta(days=7)

    await publish_drafts(amqp_url, [gateway_draft(created_at=datetime.now(UTC))])

    landed = await drain_until(
        amqp_url,
        app_sessionmaker,
        lambda: _at_least_one(migrate_engine),
        retention_for=_resolver,
    )

    assert landed
    assert seen == [WORKSPACE_A]


async def _at_least_one(migrate_engine: AsyncEngine) -> bool:
    return await _committed(migrate_engine) >= 1
