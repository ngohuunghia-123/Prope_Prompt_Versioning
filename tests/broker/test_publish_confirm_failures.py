"""D-21's three publish-failure reasons, each PROVOKED rather than mocked, plus A-046.

``prope_call_ledger_publish_failed_total``'s ``reason`` label has a closed set —
``unroutable`` | ``nacked`` | ``timeout`` — and a mocked ``exchange.publish``
would prove only that the test knows how to raise. Each of the three below is
produced by a real broker doing the real thing:

- **unroutable** — publish with ``mandatory=True`` to a routing key no queue is
  bound to. The broker returns the message and aiormq raises ``PublishError``.
- **nacked** — publish past ``x-max-length`` on a queue whose ``x-overflow`` is
  ``reject-publish-dlx``. The broker sends ``basic.nack`` and aiormq raises the
  parent ``DeliveryError``.
- **timeout** — a publish timeout too short for a confirm to come back.

**Why the nack is provoked on a separate queue and not on ``prope.call_record``.**
The production queue's ``x-max-length`` is 1,000,000, and a test that published
a million messages to reach it would be a test nobody runs. The queue declared
below carries the SAME ``x-overflow: reject-publish-dlx`` with a max-length of
1, so the broker behaviour under test — an overflow rejection producing a
``basic.nack`` — is identical; only the threshold differs. The production
queue's own max-length is asserted in ``test_declared_arguments.py``, where it
is read back from the broker.

**A-046, in BOTH of its shapes, as one parameterised test.** A body-shaped
marker proves the code is not logging the field it knows is a body. A
credential-shaped marker on a field whose contents the publish path never
inspects proves it is not logging a field it never looked at. The orchestrator's
threat statement (T-02-04) names bodies AND provider credentials; asserting only
the first would leave the second a claim. They are one test over two markers,
not two tests, because the assertion is identical and the difference is entirely
in what each marker is evidence OF.

**Phase 3 changed what each of the three reasons MEANS, and the assertions moved
with it.** Every failure below now runs with the real ADR-0041 fallback bound, so
the record is written straight to PostgreSQL instead of being lost:
``fallback_direct_write_total`` moves and ``metadata_dropped_total`` does **not**.
Asserting only the first would leave the change in meaning described rather than
proved — and ``metadata_dropped_total`` is the counter whose alert pages
immediately, so "it did not move" is the load-bearing half.

The A-046 assertion is re-run with the fallback in the path for the same reason:
the fallback is a **new** consumer of the body-carrying record, and it is the
newest place a body could reach a log line.

**D-29's byte cap is asserted here in its counter-and-log half only.** A
``ledger.call_body`` row exists only after the drain has consumed the message and
``write_records`` has run; this module publishes and inspects confirms and starts
no drain, and the fallback cannot supply the row either, because it rebuilds every
record with ``body=None`` by design. The two assertions that need a committed row
live in ``test_enqueue_reaches_a_committed_row.py``, which drains.
"""

import asyncio

import pytest
import structlog
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.broker.connection import build_connection, publisher_channel
from prope.broker.topology import WORK_QUEUE_ARGUMENTS, declare_topology
from prope.call_ledger.domain import CallBodyDraft
from prope.call_ledger.enqueue import MAX_BODY_BYTES, enqueue, publish_record, reset_handoff
from tests.broker._helpers import counter_value, fallback_writer, handoff_item
from tests.unit import gateway_draft

#: A queue with the production overflow mode and a threshold a test can reach.
#: Everything except ``x-max-length`` matches ``WORK_QUEUE_ARGUMENTS``.
OVERFLOWING_QUEUE = "prope.test.overflowing"
OVERFLOWING_ARGUMENTS = {**WORK_QUEUE_ARGUMENTS, "x-max-length": 1}

#: A routing key nothing is bound to. The default exchange routes by queue name,
#: so a name no queue has is unroutable by construction.
UNBOUND_ROUTING_KEY = "prope.test.nothing-is-bound-here"


def _counter_value(reason: str) -> float:
    return counter_value("prope_call_ledger_publish_failed_total", {"reason": reason})


def _dropped_value() -> float:
    return counter_value("prope_call_ledger_metadata_dropped_total")


def _fell_back_value() -> float:
    return counter_value("prope_call_ledger_fallback_direct_write_total")


def _body_dropped_value(reason: str) -> float:
    return counter_value("prope_call_ledger_body_dropped_total", {"reason": reason})


def _enqueued_value(outcome: str) -> float:
    return counter_value(
        "prope_call_ledger_enqueued_total", {"source": "gateway", "outcome": outcome}
    )


def _every_metric_label_value() -> list[str]:
    """Every label value currently in the registry, across every metric.

    A-046's metric half. Collected wholesale rather than per-metric, because the
    rule is that a body reaches NO label, and a per-metric list is a list
    somebody has to remember to extend.
    """
    values: list[str] = []
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            values.extend(str(v) for v in sample.labels.values())
    return values


async def test_unroutable_is_counted_and_the_record_falls_back(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mandatory=True to a routing key nothing is bound to, absorbed by the fallback."""
    monkeypatch.setattr("prope.call_ledger.enqueue.WORK_QUEUE", UNBOUND_ROUTING_KEY)
    before, dropped_before = _counter_value("unroutable"), _dropped_value()
    fell_back_before = _fell_back_value()

    connection = await build_connection(amqp_url)
    async with connection:
        async with publisher_channel(connection) as channel:
            await declare_topology(channel)
            acked = await publish_record(
                channel.default_exchange,
                handoff_item(gateway_draft()),
                fallback=fallback_writer(app_sessionmaker),
            )

    assert acked is False
    assert _counter_value("unroutable") == before + 1
    assert _fell_back_value() == fell_back_before + 1, "CL-01: the record was written"
    assert _dropped_value() == dropped_before, "nothing was lost, so nothing is counted lost"


async def test_nacked_is_counted_and_the_record_falls_back(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Publishing past x-max-length on a reject-publish-dlx queue nacks the publisher.

    This is the signal that made the Task 1 checkpoint choose a classic queue: a
    quorum queue cannot do ``reject-publish-dlx``, so it could never produce
    this branch, and ADR-0041's fallback would never fire on overflow.
    """
    monkeypatch.setattr("prope.call_ledger.enqueue.WORK_QUEUE", OVERFLOWING_QUEUE)
    before, dropped_before = _counter_value("nacked"), _dropped_value()
    fell_back_before = _fell_back_value()
    fallback = fallback_writer(app_sessionmaker)

    connection = await build_connection(amqp_url)
    async with connection:
        async with connection.channel() as setup:
            queue = await setup.declare_queue(
                OVERFLOWING_QUEUE, durable=True, arguments=OVERFLOWING_ARGUMENTS
            )
            await queue.purge()

        async with publisher_channel(connection) as channel:
            # The first fills the queue to its max-length of one.
            assert await publish_record(
                channel.default_exchange, handoff_item(gateway_draft()), fallback=fallback
            )
            # The second overflows it, and is rejected rather than dropped.
            acked = await publish_record(
                channel.default_exchange,
                handoff_item(gateway_draft(call_id="cal_overflow")),
                fallback=fallback,
            )

        async with connection.channel() as teardown:
            await teardown.queue_delete(OVERFLOWING_QUEUE)

    assert acked is False, "an overflowing publish is nacked, not silently accepted"
    assert _counter_value("nacked") == before + 1
    assert _fell_back_value() == fell_back_before + 1
    assert _dropped_value() == dropped_before


async def test_timeout_is_counted_and_the_record_falls_back(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A confirm that cannot arrive inside the timeout is `timeout`, not `nacked`.

    **This is the case CL-02 does not close and this plan says so out loud.** The
    broker may well have received the message; the fallback writes it anyway, and
    the redelivery that follows raises an ``IntegrityError`` the drain
    dead-letters until plan 03-02's idempotent upsert lands.
    """
    monkeypatch.setattr("prope.call_ledger.enqueue.PUBLISH_TIMEOUT_SECONDS", 1e-9)
    before, dropped_before = _counter_value("timeout"), _dropped_value()
    fell_back_before = _fell_back_value()

    connection = await build_connection(amqp_url)
    async with connection:
        async with publisher_channel(connection) as channel:
            await declare_topology(channel)
            acked = await publish_record(
                channel.default_exchange,
                handoff_item(gateway_draft()),
                fallback=fallback_writer(app_sessionmaker),
            )

    assert acked is False
    assert _counter_value("timeout") == before + 1
    assert _fell_back_value() == fell_back_before + 1
    assert _dropped_value() == dropped_before


async def test_a_fallback_that_itself_raises_loses_exactly_one_record(
    amqp_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both stores gone. This is the ONLY event metadata_dropped_total now means.

    The fallback here is the real one bound to a session factory that cannot
    connect, so the refusal comes from the engine rather than from a test raising
    on purpose — and it exercises ``build_fallback_writer``'s own ``except``
    rather than ``publish_or_fall_back``'s outer one.
    """
    from prope.call_ledger.fallback import build_fallback_writer
    from prope.db.engine import build_engine, build_sessionmaker

    monkeypatch.setattr("prope.call_ledger.enqueue.WORK_QUEUE", UNBOUND_ROUTING_KEY)
    dropped_before, fell_back_before = _dropped_value(), _fell_back_value()

    engine = build_engine("postgresql+asyncpg://nobody:sk-secret-marker@127.0.0.1:1/nothing")
    try:
        connection = await build_connection(amqp_url)
        with structlog.testing.capture_logs() as captured:
            async with connection:
                async with publisher_channel(connection) as channel:
                    await declare_topology(channel)
                    acked = await publish_record(
                        channel.default_exchange,
                        handoff_item(gateway_draft()),
                        fallback=build_fallback_writer(build_sessionmaker(engine)),
                    )
    finally:
        await engine.dispose()

    assert acked is False
    assert _dropped_value() == dropped_before + 1, "exactly one record, exactly one count"
    assert _fell_back_value() == fell_back_before, "nothing was written, so nothing is counted"

    failures = [record for record in captured if record["event"] == "call_ledger.fallback_failed"]
    assert len(failures) == 1, "one lost record, one line"
    # A-046: the exception's CLASS reaches the log; its MESSAGE does not, and at
    # this depth the message can quote the connection string — which is why the
    # password above is shaped like a credential.
    assert failures[0]["reason"].isidentifier(), "a class name, not a sentence"
    assert "sk-secret-marker" not in repr(failures[0])


async def test_enqueue_returns_normally_through_every_failure_branch(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INT-018 across all three reasons at once: the caller never sees any of them.

    Asserted on the RETURN of ``enqueue``, which is the whole of the caller's
    span. A publisher failing behind it is not the caller's problem, and this is
    the assertion that says so.
    """
    monkeypatch.setattr("prope.call_ledger.enqueue.WORK_QUEUE", UNBOUND_ROUTING_KEY)
    reset_handoff()

    from prope.call_ledger.enqueue import handoff, run_publisher

    stopping = asyncio.Event()
    connection = await build_connection(amqp_url)
    async with connection:
        async with publisher_channel(connection) as channel:
            await declare_topology(channel)
            publisher = asyncio.create_task(
                run_publisher(
                    channel.default_exchange,
                    stopping,
                    fallback=fallback_writer(app_sessionmaker),
                )
            )

            for index in range(3):
                assert enqueue(gateway_draft(call_id=f"cal_{index:026d}")) is None

            deadline = asyncio.get_running_loop().time() + 15
            while asyncio.get_running_loop().time() < deadline and not handoff().empty():
                await asyncio.sleep(0.05)

            stopping.set()
            await asyncio.wait_for(publisher, timeout=15)


def _body_of(size: int) -> CallBodyDraft:
    """A request/response pair whose UTF-8 encoding is exactly ``size`` bytes.

    Split across the two halves, because the cap is on the PAIR. The caller's own
    ``byte_size`` is deliberately a lie: a cap enforced from a figure the capped
    party supplies is not a cap, so ``enqueue()`` overwrites it from bytes it
    encoded itself.
    """
    half, rest = divmod(size, 2)
    return CallBodyDraft(
        request_body="a" * half,
        response_body="b" * (half + rest),
        byte_size=1,
    )


async def test_a_body_one_byte_over_the_cap_is_dropped_and_counted() -> None:
    """D-29: the body goes, the record stays, and the drop lands on the right counter."""
    reset_handoff()
    oversize_before = _body_dropped_value("oversize")
    accepted_before, dropped_before = _enqueued_value("accepted"), _enqueued_value("dropped")

    from prope.call_ledger.enqueue import handoff

    enqueue(gateway_draft(body=_body_of(MAX_BODY_BYTES + 1)))

    assert _body_dropped_value("oversize") == oversize_before + 1
    assert _enqueued_value("accepted") == accepted_before + 1, "the RECORD is accepted"
    assert _enqueued_value("dropped") == dropped_before, "the record is not dropped for its body"
    assert handoff().qsize() == 1
    assert handoff().get_nowait().draft.body is None, "metadata continues with body=None"


async def test_a_body_exactly_at_the_cap_keeps_its_body() -> None:
    """The boundary from the other side, or the test above proves only that a cap exists."""
    reset_handoff()
    oversize_before = _body_dropped_value("oversize")

    from prope.call_ledger.enqueue import handoff

    enqueue(gateway_draft(body=_body_of(MAX_BODY_BYTES)))

    assert _body_dropped_value("oversize") == oversize_before, "at the cap is not over it"
    item = handoff().get_nowait()
    assert item.draft.body is not None
    assert item.draft.body.byte_size == MAX_BODY_BYTES, "computed here, not taken from the caller"


async def test_a_body_that_cannot_be_encoded_is_counted_and_enqueue_returns() -> None:
    """A lone surrogate is the reachable form of "the failure nobody predicted".

    ``str.encode()`` on a caller-supplied string can raise, and INT-018 says
    ``enqueue()`` never does. The body is dropped and counted; the record
    continues.
    """
    reset_handoff()
    oversize_before = _body_dropped_value("oversize")

    from prope.call_ledger.enqueue import handoff

    unencodable = CallBodyDraft(request_body="\ud800", response_body="fine", byte_size=None)
    assert enqueue(gateway_draft(body=unencodable)) is None

    assert _body_dropped_value("oversize") == oversize_before + 1
    assert handoff().get_nowait().draft.body is None


async def test_the_oversize_log_line_carries_no_fragment_of_the_body() -> None:
    """A-046 on the newest log line in the module, with the file's own marker technique."""
    reset_handoff()
    marker = "MARKER-body-9f3a1c-do-not-log"
    body = CallBodyDraft(
        request_body=marker + "x" * MAX_BODY_BYTES,
        response_body=marker,
        byte_size=None,
    )

    with structlog.testing.capture_logs() as captured:
        enqueue(gateway_draft(body=body))

    assert captured, "an oversize body must log SOMETHING, or the assertion is vacuous"
    for record in captured:
        assert marker not in repr(record), f"{marker!r} reached a log record"
    for value in _every_metric_label_value():
        assert marker not in value, f"{marker!r} reached a metric label"


@pytest.mark.parametrize(
    ("marker", "evidence_of"),
    [
        (
            "MARKER-body-9f3a1c-do-not-log",
            "the code is not logging the field it KNOWS is a body",
        ),
        (
            "sk-proj-MARKER7c2ee41d9b0aXXXXXXXXXXXXXXXXXXXX",
            "the code is not logging a field whose contents it NEVER inspected",
        ),
    ],
    ids=["body_marker", "credential_shaped_marker"],
)
async def test_no_marker_reaches_a_log_record_or_a_metric_label(
    amqp_url: str,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    marker: str,
    evidence_of: str,
) -> None:
    """A-046 / T-02-04, over both markers. Zero log records, zero metric labels.

    The body marker travels on ``request_body`` and ``response_body``. The
    credential-shaped marker travels on ``error_class`` as well — a field the
    publish path never reads, which is what makes it evidence about fields
    rather than about this one field.

    **Re-run with the fallback in the path**, because the fallback is a NEW
    consumer of the body-carrying record — it inspects ``record.body`` to decide
    whether to count a drop, and it logs — so it is the newest place in this
    module where a body could reach a log line.

    Redaction in the code under test is a POSITIVE allow-list of loggable
    fields (``prope.observability.LOGGABLE_FIELDS``), never a deny-list of field
    names: a deny-list passes the first time a body travels on a field nobody
    thought to forbid.
    """
    monkeypatch.setattr("prope.call_ledger.enqueue.WORK_QUEUE", UNBOUND_ROUTING_KEY)

    draft = gateway_draft(
        body=CallBodyDraft(request_body=marker, response_body=marker, byte_size=len(marker)),
        error_class=marker,
    )

    connection = await build_connection(amqp_url)
    with structlog.testing.capture_logs() as captured:
        async with connection:
            async with publisher_channel(connection) as channel:
                await declare_topology(channel)
                acked = await publish_record(
                    channel.default_exchange,
                    handoff_item(draft),
                    fallback=fallback_writer(app_sessionmaker),
                )

    assert acked is False, "the failure must actually have happened, or this proves nothing"
    assert captured, "a failed confirm must log SOMETHING, or the assertion is vacuous"

    for record in captured:
        rendered = repr(record)
        assert marker not in rendered, f"{marker!r} reached a log record ({evidence_of})"

    for value in _every_metric_label_value():
        assert marker not in value, f"{marker!r} reached a metric label ({evidence_of})"


async def test_workspace_id_is_never_a_metric_label() -> None:
    """ADR-0030's bounded cardinality, asserted rather than intended.

    ``workspace_id`` is the highest-cardinality identifier in the system and the
    most tempting label to add. Its absence is the control that keeps the metric
    set bounded as seven more modules land — and it must keep holding at eighteen
    metrics, not only at five.
    """
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prope_"):
            continue
        for sample in metric.samples:
            assert "workspace_id" not in sample.labels, metric.name


async def test_the_two_extended_label_sets_stayed_closed_at_their_declared_size() -> None:
    """The vocabularies, read back from the registry rather than from the source.

    ``publish_failed_total``'s ``reason`` is declared closed at three and Phase 3
    did **not** grow it: the bare-``except`` branch that absorbs a closed channel
    still leaves it untouched, which is why ``OQ-022``'s fifth clause exists at
    all. ``body_dropped_total``'s ``reason`` is the one set this phase did extend,
    and it is extended by exactly one value — the declared ``queue_full`` has no
    producer and must never appear.

    Run last in this module by position, after every reason above has actually
    been provoked, so the sets it reads are populated rather than empty.
    """
    observed: dict[str, set[str]] = {}
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if "reason" not in sample.labels:
                continue
            observed.setdefault(metric.name, set()).add(sample.labels["reason"])

    assert observed["prope_call_ledger_publish_failed"] == {"unroutable", "nacked", "timeout"}
    assert observed["prope_call_ledger_body_dropped"] <= {"fallback", "oversize"}
    assert "queue_full" not in observed["prope_call_ledger_body_dropped"]
