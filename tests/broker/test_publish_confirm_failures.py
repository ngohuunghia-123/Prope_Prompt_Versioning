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
"""

import asyncio

import pytest
import structlog
from prometheus_client import REGISTRY

from prope.broker.connection import build_connection, publisher_channel
from prope.broker.topology import WORK_QUEUE_ARGUMENTS, declare_topology
from prope.call_ledger.enqueue import enqueue, publish_record, reset_handoff
from tests.unit import gateway_draft

#: A queue with the production overflow mode and a threshold a test can reach.
#: Everything except ``x-max-length`` matches ``WORK_QUEUE_ARGUMENTS``.
OVERFLOWING_QUEUE = "prope.test.overflowing"
OVERFLOWING_ARGUMENTS = {**WORK_QUEUE_ARGUMENTS, "x-max-length": 1}

#: A routing key nothing is bound to. The default exchange routes by queue name,
#: so a name no queue has is unroutable by construction.
UNBOUND_ROUTING_KEY = "prope.test.nothing-is-bound-here"


def _counter_value(reason: str) -> float:
    value = REGISTRY.get_sample_value(
        "prope_call_ledger_publish_failed_total", {"reason": reason}
    )
    return value or 0.0


def _dropped_value() -> float:
    return REGISTRY.get_sample_value("prope_call_ledger_metadata_dropped_total") or 0.0


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


async def test_unroutable_is_counted_and_enqueue_returns(
    amqp_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mandatory=True to a routing key nothing is bound to."""
    monkeypatch.setattr("prope.call_ledger.enqueue.WORK_QUEUE", UNBOUND_ROUTING_KEY)
    before, dropped_before = _counter_value("unroutable"), _dropped_value()

    connection = await build_connection(amqp_url)
    async with connection:
        async with publisher_channel(connection) as channel:
            await declare_topology(channel)
            acked = await publish_record(channel.default_exchange, gateway_draft())

    assert acked is False
    assert _counter_value("unroutable") == before + 1
    assert _dropped_value() == dropped_before + 1


async def test_nacked_is_counted_and_enqueue_returns(
    amqp_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Publishing past x-max-length on a reject-publish-dlx queue nacks the publisher.

    This is the signal that made the Task 1 checkpoint choose a classic queue: a
    quorum queue cannot do ``reject-publish-dlx``, so it could never produce
    this branch, and ADR-0041's Phase 3 fallback would never fire on overflow.
    """
    monkeypatch.setattr("prope.call_ledger.enqueue.WORK_QUEUE", OVERFLOWING_QUEUE)
    before, dropped_before = _counter_value("nacked"), _dropped_value()

    connection = await build_connection(amqp_url)
    async with connection:
        async with connection.channel() as setup:
            queue = await setup.declare_queue(
                OVERFLOWING_QUEUE, durable=True, arguments=OVERFLOWING_ARGUMENTS
            )
            await queue.purge()

        async with publisher_channel(connection) as channel:
            # The first fills the queue to its max-length of one.
            assert await publish_record(channel.default_exchange, gateway_draft())
            # The second overflows it, and is rejected rather than dropped.
            acked = await publish_record(
                channel.default_exchange, gateway_draft(call_id="cal_overflow")
            )

        async with connection.channel() as teardown:
            await teardown.queue_delete(OVERFLOWING_QUEUE)

    assert acked is False, "an overflowing publish is nacked, not silently accepted"
    assert _counter_value("nacked") == before + 1
    assert _dropped_value() == dropped_before + 1


async def test_timeout_is_counted_and_enqueue_returns(
    amqp_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A confirm that cannot arrive inside the timeout is `timeout`, not `nacked`."""
    monkeypatch.setattr("prope.call_ledger.enqueue.PUBLISH_TIMEOUT_SECONDS", 1e-9)
    before, dropped_before = _counter_value("timeout"), _dropped_value()

    connection = await build_connection(amqp_url)
    async with connection:
        async with publisher_channel(connection) as channel:
            await declare_topology(channel)
            acked = await publish_record(channel.default_exchange, gateway_draft())

    assert acked is False
    assert _counter_value("timeout") == before + 1
    assert _dropped_value() == dropped_before + 1


async def test_enqueue_returns_normally_through_every_failure_branch(
    amqp_url: str, monkeypatch: pytest.MonkeyPatch
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
            publisher = asyncio.create_task(run_publisher(channel.default_exchange, stopping))

            for index in range(3):
                assert enqueue(gateway_draft(call_id=f"cal_{index:026d}")) is None

            deadline = asyncio.get_running_loop().time() + 15
            while asyncio.get_running_loop().time() < deadline and not handoff().empty():
                await asyncio.sleep(0.05)

            stopping.set()
            await asyncio.wait_for(publisher, timeout=10)


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
    amqp_url: str, monkeypatch: pytest.MonkeyPatch, marker: str, evidence_of: str
) -> None:
    """A-046 / T-02-04, over both markers. Zero log records, zero metric labels.

    The body marker travels on ``request_body`` and ``response_body``. The
    credential-shaped marker travels on ``error_class`` as well — a field the
    publish path never reads, which is what makes it evidence about fields
    rather than about this one field.

    Redaction in the code under test is a POSITIVE allow-list of loggable
    fields (``prope.observability.LOGGABLE_FIELDS``), never a deny-list of field
    names: a deny-list passes the first time a body travels on a field nobody
    thought to forbid.
    """
    from prope.call_ledger.domain import CallBodyDraft

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
                acked = await publish_record(channel.default_exchange, draft)

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
    set bounded as seven more modules land.
    """
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prope_"):
            continue
        for sample in metric.samples:
            assert "workspace_id" not in sample.labels, metric.name
