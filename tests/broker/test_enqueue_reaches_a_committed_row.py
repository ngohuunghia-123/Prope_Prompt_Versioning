"""The tracer: one call record from ``enqueue()`` to a committed ledger row.

One path, end to end, against a live broker and a live PostgreSQL. One
publisher, one consumer, one workspace. This is the slice everything else in
Phase 2 expands off, so it proves the layers CONNECT rather than proving any one
of them thoroughly — the arguments, the three confirm failures and the poison
batch are asserted in their own modules.

**Nothing here asks the drain what it did.** The row assertion is a query issued
through ``migrate_engine``, the owner role, which is subject to no policy. A
drain that acked everything and wrote nothing would pass a test that read the
drain's own return value; it fails this one.

**The derived columns are asserted as derived.** ``cost_status`` and
``usage_status`` are checked against what ``write_records`` works out from the
price row in force at the record's own ``created_at``, not against anything this
test supplied — a caller able to supply them is a caller able to supply a zero,
which is the whole reason the draft has no field for them.
"""

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.broker.connection import build_connection, publisher_channel
from prope.broker.topology import declare_topology
from prope.call_ledger.domain import CallBodyDraft
from prope.call_ledger.drain import run_drain
from prope.call_ledger.enqueue import MAX_BODY_BYTES, enqueue, reset_handoff, run_publisher
from tests.broker._helpers import fallback_writer
from tests.unit import UPSTREAM_MODEL, WORKSPACE_A, gateway_draft, seed_price_row

#: Read as the owner. No tenant is set, no policy applies, and the columns read
#: are the ones the writer DERIVED rather than the ones the caller supplied.
READ_RECORD = text(
    """
    SELECT call_id, workspace_id, source, cost_status, usage_status, cost, currency
    FROM   ledger.call_record
    WHERE  call_id = :call_id
    """
)

READ_BODY = text("SELECT request_body, response_body FROM ledger.call_body WHERE call_id = :cid")

READ_BODY_SIZE = text("SELECT byte_size FROM ledger.call_body WHERE call_id = :cid")

COUNT_BODIES = text("SELECT count(*) FROM ledger.call_body WHERE call_id = :cid")


async def _row_count(migrate_engine: AsyncEngine, call_id: str) -> int:
    async with migrate_engine.begin() as connection:
        return (
            await connection.execute(
                text("SELECT count(*) FROM ledger.call_record WHERE call_id = :cid"),
                {"cid": call_id},
            )
        ).scalar_one()


async def _drain_until_written(
    amqp_url: str,
    sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    call_id: str,
    *,
    timeout: float = 20.0,
) -> None:
    """Run the real drain until the row is queryable, then stop it.

    The stop signal is a directly-settable ``asyncio.Event`` — the same one the
    supervisor will set on SIGTERM in plan 02-03 — because
    ``loop.add_signal_handler`` is unimplemented on Windows and this test has to
    run on the development host.
    """
    stopping = asyncio.Event()
    connection = await build_connection(amqp_url)

    async with connection:
        channel = await connection.channel()
        drain = asyncio.create_task(run_drain(channel, sessionmaker, stopping=stopping))

        deadline = asyncio.get_running_loop().time() + timeout
        try:
            while asyncio.get_running_loop().time() < deadline:
                if await _row_count(migrate_engine, call_id):
                    return
                await asyncio.sleep(0.1)
        finally:
            stopping.set()
            await asyncio.wait_for(drain, timeout=10)


async def _publish_one(
    amqp_url: str,
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    timeout: float = 20.0,
) -> None:
    """Run the real background publisher until the handoff is empty, then stop it.

    The fallback is the real one (D-26 makes it a required keyword argument with
    no default), so a broker failure inside this helper would still produce a
    durable row rather than a silent loss — which is what a caller asserting on
    ``ledger.call_body`` needs to be able to distinguish.
    """
    from prope.call_ledger.enqueue import handoff

    stopping = asyncio.Event()
    connection = await build_connection(amqp_url)

    async with connection:
        async with publisher_channel(connection) as channel:
            await declare_topology(channel)
            publisher = asyncio.create_task(
                run_publisher(
                    channel.default_exchange,
                    stopping,
                    fallback=fallback_writer(sessionmaker),
                )
            )
            deadline = asyncio.get_running_loop().time() + timeout
            try:
                while asyncio.get_running_loop().time() < deadline:
                    if handoff().empty():
                        # Empty means taken off the buffer; the publish and its
                        # confirm may still be in flight, so let the loop turn.
                        await asyncio.sleep(0.2)
                        return
                    await asyncio.sleep(0.05)
            finally:
                stopping.set()
                await asyncio.wait_for(publisher, timeout=15)


async def test_one_record_reaches_a_committed_ledger_row(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """enqueue() -> broker -> drain -> workspace_transaction -> ledger.call_record."""
    reset_handoff()
    await seed_price_row(migrate_engine)

    draft = gateway_draft(upstream_model=UPSTREAM_MODEL)

    enqueue(draft)
    await _publish_one(amqp_url, app_sessionmaker)
    await _drain_until_written(amqp_url, app_sessionmaker, migrate_engine, draft.call_id)

    async with migrate_engine.begin() as connection:
        rows = (
            (await connection.execute(READ_RECORD, {"call_id": draft.call_id}))
            .mappings()
            .all()
        )

    assert len(rows) == 1, "exactly one row, published once and written once"
    row = rows[0]
    assert row["workspace_id"] == WORKSPACE_A
    assert row["source"] == "gateway"
    # Derived by write_records from the seeded price row, not supplied here.
    assert row["cost_status"] == "priced"
    assert row["usage_status"] == "reported"
    assert row["cost"] > 0
    assert row["currency"] == "USD"

    async with migrate_engine.begin() as connection:
        body = (
            (await connection.execute(READ_BODY, {"cid": draft.call_id})).mappings().one()
        )
    assert body["request_body"] == "a request"
    assert body["response_body"] == "a response"


async def test_an_oversize_record_lands_with_no_body_row_at_all(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """D-29 through the WHOLE path, which is why this case lives here.

    Its counter-half is in ``test_publish_confirm_failures.py``. This half needs a
    committed row and that file starts no drain — and the fallback could not
    supply one either, because it rebuilds every record with ``body=None`` by
    design. So the assertion that a body genuinely never reaches
    ``ledger.call_body`` can only be made where a message is actually drained.

    Both halves are asserted, not one: a record row without zero body rows would
    mean the cap did nothing, and zero body rows without a record row would mean
    the whole record was dropped for its body's sake — which D-29 forbids.
    """
    reset_handoff()

    oversize = "z" * (MAX_BODY_BYTES + 1)
    draft = gateway_draft(
        body=CallBodyDraft(request_body=oversize, response_body=None, byte_size=None)
    )

    enqueue(draft)
    await _publish_one(amqp_url, app_sessionmaker)
    await _drain_until_written(amqp_url, app_sessionmaker, migrate_engine, draft.call_id)

    async with migrate_engine.begin() as connection:
        records = (
            await connection.execute(
                text("SELECT count(*) FROM ledger.call_record WHERE call_id = :cid"),
                {"cid": draft.call_id},
            )
        ).scalar_one()
        bodies = (
            await connection.execute(COUNT_BODIES, {"cid": draft.call_id})
        ).scalar_one()

    assert records == 1, "the record survives its body"
    assert bodies == 0, "and the body does not survive the cap"


async def test_the_stored_byte_size_is_the_one_this_module_computed(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """A cap enforced from a figure the capped party supplies is not a cap.

    The caller supplies a deliberately wrong ``byte_size``; ``enqueue()``
    overwrites it from bytes it encoded itself, and THAT is what reaches the
    column. Read through ``migrate_engine`` — the owner role, subject to no
    policy — rather than through anything that could be reporting its own input.
    """
    reset_handoff()

    request_body, response_body = "a request", "a response"
    expected = len(request_body.encode()) + len(response_body.encode())
    draft = gateway_draft(
        body=CallBodyDraft(
            request_body=request_body,
            response_body=response_body,
            byte_size=999_999,
        )
    )

    enqueue(draft)
    await _publish_one(amqp_url, app_sessionmaker)
    await _drain_until_written(amqp_url, app_sessionmaker, migrate_engine, draft.call_id)

    async with migrate_engine.begin() as connection:
        stored = (
            await connection.execute(READ_BODY_SIZE, {"cid": draft.call_id})
        ).scalar_one()

    assert stored == expected, "the computed size, not the caller's 999,999"


async def test_enqueue_returns_normally_with_no_broker_running() -> None:
    """INT-018's contract at its hardest branch: there is no broker at all.

    The assertion is on the RETURN, not on the log. ``enqueue()`` is the
    gateway's response path, and a log line saying something went wrong is not
    the same fact as a call that came back.
    """
    reset_handoff()
    draft = gateway_draft()

    # No connection has been built, no publisher is running, and nothing in this
    # test has ever reached a broker.
    assert enqueue(draft) is None


async def test_enqueue_returns_normally_when_the_handoff_is_full() -> None:
    """A full buffer counts and drops (D-25). It does not block and does not raise."""
    from prope.call_ledger.enqueue import HANDOFF_MAXSIZE, handoff

    reset_handoff()
    for index in range(HANDOFF_MAXSIZE):
        enqueue(gateway_draft(call_id=f"cal_{index:026d}"))

    assert handoff().full()
    assert enqueue(gateway_draft(call_id="cal_overflowing")) is None
    assert handoff().qsize() == HANDOFF_MAXSIZE, "the buffer is bounded, not grown"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workspace_id", "wsp_has a space"),
        ("workspace_id", "wsp_line\nbreak"),
        ("workspace_id", "wsp_quote'injected"),
        ("workspace_id", "ws"),
        ("schema_version", 2),
    ],
)
def test_envelope_refuses_the_values_that_must_never_reach_set_config(
    field: str, value: object
) -> None:
    """The V5 source gate, asserted at the model rather than claimed in a docstring.

    ``workspace_id`` is the one value on this wire that decides which tenant's
    rows a transaction may touch. ``schema_version`` is ``Literal[1]``, so a
    version this code has never seen is refused here rather than failing
    further in with a worse error.
    """
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from prope.call_ledger.envelope import CallRecordEnvelope

    valid = CallRecordEnvelope.from_draft(
        gateway_draft(), occurred_at=datetime.now(UTC)
    ).model_dump()
    valid[field] = value

    with pytest.raises(ValidationError):
        CallRecordEnvelope.model_validate(valid)
