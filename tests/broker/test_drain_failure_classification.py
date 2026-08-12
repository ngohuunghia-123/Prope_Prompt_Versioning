"""The drain's failure classification, and CR-01's second named test.

Every write failure the drain can meet is either **permanent** — the record can
never be written as it is, so redelivery cannot help — or **transient** — the
moment was wrong, not the record. A permanent failure is rejected without
requeue so it dead-letters and is counted; a transient one is nacked with
requeue and the drain backs off. **A permanent failure is never requeued**: a
classic queue has no ``x-delivery-limit`` (the accepted cost of the Task 1
queue-type decision), so a permanently-failing record that is requeued is an
infinite loop with nothing to stop it.

**The Phase 2 gap this file used to make visible is closed, and the sentence
that said otherwise is rewritten rather than deleted.** Phase 2's version of this
paragraph recorded that ``ledger.call_record``'s primary key is ``call_id`` alone
while ``write_records`` issued a plain ``INSERT``, so **an ordinary consumer
restart dead-lettered records that were already written** — a real, named gap
that CL-02 closes. It is closed: ``write_records`` now issues
``ON CONFLICT (call_id) DO NOTHING … RETURNING call_id`` (D-33), so a redelivered
record raises nothing at all here. It is skipped by the statement, counted on
``duplicate_call_id_total``, and — the part CL-02 is actually about — adds
nothing to ``ledger.workspace_spend``. **An ``IntegrityError`` reaching
``classify_write_failure`` now means a different constraint**, a CHECK the record
violates, and the branch stays ``PERMANENT`` for the original reason. The proof
of the closed gap lives in
``tests/broker/test_redelivery_leaves_the_total_unmoved.py``, where the second
consumer is the real drain.

**A dead-letter is no longer counted as a drop** (D-30). ``metadata_dropped_total``
means a record exists NOWHERE and its alert pages immediately; a dead-lettered
record is on ``prope.call_record.dlq``, whose non-zero depth is its own signal.
Two tests below assert the counter stays still — each with the positive control
that makes the assertion mean something, because "a counter did not move" is also
true of a drain that did nothing.

**CR-01's second named test is ``test_one_unwritable_record_does_not_discard_its
_batch_mates``.** ``write_records`` is all-or-nothing by design, which is
correct and is also why one poison record would otherwise take four innocent
ones with it. The drain answers that by retrying a failed group one record at a
time.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.broker.connection import build_connection
from prope.broker.topology import DLQ, WORK_QUEUE, declare_topology
from prope.call_ledger.domain import CallBodyDraft
from prope.call_ledger.drain import WriteFailure, classify_write_failure
from prope.db.session import workspace_transaction
from tests.broker._helpers import (
    counter_value,
    drain_until,
    publish_bodies,
    publish_drafts,
    queue_depth,
)
from tests.unit import WORKSPACE_A, eval_draft, gateway_draft

COUNT_RECORDS = text("SELECT count(*) FROM ledger.call_record")


def _dropped() -> float:
    """``metadata_dropped_total``, read as a delta at every call site."""
    return counter_value("prope_call_ledger_metadata_dropped_total")


def _lag_observations() -> tuple[float, float]:
    """``write_lag_seconds``' ``_count`` and ``_sum``, as a pair.

    A histogram exposes no single value, and both halves are needed: ``_count``
    says the observation happened at all, and ``_sum`` is where a negative
    observation would show, because ``prometheus_client`` decrements ``_sum``
    while incrementing ``_count`` and never complains.
    """
    count = REGISTRY.get_sample_value("prope_call_ledger_write_lag_seconds_count") or 0.0
    total = REGISTRY.get_sample_value("prope_call_ledger_write_lag_seconds_sum") or 0.0
    return count, total


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
        # A CHECK the record violates. After CL-02 a redelivery cannot produce a
        # unique violation here at all — the upsert skips it — so this branch now
        # only ever sees a constraint the encoding genuinely cannot satisfy.
        (
            IntegrityError("INSERT", {}, Exception("ck_call_record_cost_state_is_coherent")),
            WriteFailure.PERMANENT,
        ),
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
# D-30 — a dead-letter is not a drop, and the counter must not move
# --------------------------------------------------------------------------


async def test_a_dead_lettered_record_moves_metadata_dropped_total_by_zero(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """D-30, with the positive control the removal needs to mean anything.

    A test asserting a counter did **not** move passes trivially against a drain
    that did nothing at all, so both halves are here in one test: the
    dead-letter is proved to have happened — one message on the DLQ, and the
    innocent record beside it committed — **and** ``metadata_dropped_total``
    moved by zero across the whole of it.

    The counter now means what ADR-0041 says it means: a record that exists
    nowhere. This one exists in ``prope.call_record.dlq``, whose depth is its own
    signal and whose alert is a ticket rather than a page.
    """
    innocent = gateway_draft(call_id="cal_innocent0000000000000000")
    poison = eval_draft(
        call_id="cal_poison00000000000000000",
        workspace_id=WORKSPACE_A,
        body=CallBodyDraft(request_body="refused", response_body="refused", byte_size=7),
    )
    dropped_before = _dropped()

    await publish_drafts(amqp_url, [innocent, poison])

    dead_lettered = await drain_until(
        amqp_url, app_sessionmaker, lambda: _dlq_reached(amqp_url, 1)
    )

    assert dead_lettered, "the poison record never reached the DLQ"
    assert await _dlq_depth(amqp_url) == 1
    assert await _committed(migrate_engine) == 1, (
        "positive control: without a committed batch-mate the drain may simply not have run"
    )
    assert _dropped() == dropped_before, (
        "a dead-lettered record is not a dropped one — LedgerMetadataDropped pages, and this "
        "record is on the DLQ where dlq_depth can see it"
    )


async def test_write_lag_is_observed_on_the_drains_committed_path(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """The histogram is closed after the commit, on the production path.

    Not behind ``on_window``: ``drain_until`` supplies no observer, which is
    exactly the production shape, and the observations still appear. If the
    metric sat behind that hook it would be absent in the one process
    ``LedgerWriteLagHigh`` reads it from.

    ``_sum`` is asserted non-decreasing because the observation is clamped at
    zero. ``occurred_at`` is stamped in ``app`` and the durable instant is read in
    ``worker``; an unclamped negative would decrement ``_sum`` while incrementing
    ``_count``, which is invisible on a quantile panel and nonsense on an average
    one.
    """
    drafts = [gateway_draft(call_id=f"cal_lag{index:023d}") for index in range(3)]
    count_before, sum_before = _lag_observations()

    await publish_drafts(amqp_url, drafts)
    landed = await drain_until(
        amqp_url, app_sessionmaker, lambda: _committed_reaches(migrate_engine, 3)
    )

    assert landed, "the three records never committed"

    count_after, sum_after = _lag_observations()
    assert count_after == count_before + 3, "one observation per record, after its group committed"
    assert sum_after >= sum_before, "a negative observation reached the histogram"


async def _committed_reaches(migrate_engine: AsyncEngine, expected: int) -> bool:
    return await _committed(migrate_engine) >= expected


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

    **D-30's second half is asserted here**: three envelopes are rejected and
    ``metadata_dropped_total`` moves by zero, with the DLQ depth as the positive
    control that says the rejections actually happened. After the removal an
    invalid envelope produces one log line, one ``reject(requeue=False)`` and no
    counter movement of any kind — which is deliberate, and whose limit
    (``dlq_depth`` is a gauge behind a 30-day TTL) is written at the removal site
    in ``drain.py`` and carried in ``deferred-items.md``.
    """
    entered: list[str] = []
    dropped_before = _dropped()

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
    assert _dropped() == dropped_before, (
        "an envelope that never became a record is on the DLQ, not nowhere — "
        "metadata_dropped_total is the page for a record that reached neither store"
    )


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
