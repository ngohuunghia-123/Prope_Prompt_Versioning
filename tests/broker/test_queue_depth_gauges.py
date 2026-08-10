"""D-42: the two depth gauges, read from the broker's own view of both queues.

**Asserted against the broker, never against a number this file computed.** The
gauges exist to answer *"how much unwritten traffic is the broker holding"*, and
a test that published five messages and asserted the gauge equals five, having
set the gauge from its own count, would assert nothing. Every value below comes
out of a passive declare — the broker's answer — through the production function.

**One pass of the job, not the whole worker.** ``read_queue_depths`` is what the
supervised job calls; running ``run_worker`` here would add a drain that empties
the queue underneath the assertion, which is the one thing a depth test must not
have. The composed job is covered where composition is covered
(``tests/integration/test_worker_jobs.py``).

**The gauge's semantics are narrower than its name, and one test asserts exactly
that** (Pitfall 10). RabbitMQ defines queue length as *"the number of messages
ready for delivery"*, and a message is either ready or delivered-but-unacked. The
drain holds up to ``WINDOW_SIZE`` (500) unacked, so a backlog can be genuinely
invisible here. A test asserting equality under a holding consumer would be
asserting something RabbitMQ does not promise, so this file asserts the
inequality and names why.

Values are read as **absolutes** rather than deltas, unlike every counter in this
suite: these are gauges, each pass *sets* rather than adds, and the value after a
pass is a fact about the broker at that instant rather than about what other
tests did earlier.
"""

import asyncio
import functools

import structlog
from prometheus_client import REGISTRY

from prope.broker.connection import build_connection
from prope.broker.topology import DLQ, WORK_QUEUE
from prope.observability import queue_depth
from prope.supervisor import interval_job, supervise
from prope.worker import JOB_QUEUE_DEPTH_GAUGES, read_queue_depths
from tests.broker._helpers import publish_bodies

#: How many messages one pass is asked to count. Small enough to be quick, and
#: unmistakably not zero or one — a gauge that reported the wrong thing would
#: have to report exactly seven to pass by accident.
PUBLISHED = 7

#: How many of those a holding consumer takes without acknowledging, for the
#: ready-versus-unacknowledged assertion. Three of seven, so the remainder is
#: neither zero nor the whole.
HELD_UNACKED = 3

#: A queue nothing declares, for the channel-level-error case. The name is
#: deliberately outside the ``prope.`` prefix so that a future topology change
#: cannot accidentally bring it into existence.
NO_SUCH_QUEUE = "queue.that.was.never.declared"

#: How long the supervision test waits for the crash it is provoking. Generous
#: against a container on a loaded host; the loop below exits the moment the line
#: appears, so the number is a ceiling rather than a sleep.
CRASH_DEADLINE_SECONDS = 20.0


def _gauge(name: str) -> float:
    """One gauge's current value, and a refusal if the metric does not exist.

    ``REGISTRY.get_sample_value`` answers ``None`` for a metric nothing declared,
    and ``None`` compares equal to nothing — so an ``== 0`` assertion over an
    undeclared metric fails for the right reason only by luck. D-40 defines all
    eighteen at import so this cannot happen; this assertion keeps that true.
    """
    value = REGISTRY.get_sample_value(name)
    assert value is not None, f"{name} is not in the registry"
    return value


async def _messages(count: int) -> list[bytes]:
    """``count`` distinct raw payloads. Never parsed — nothing consumes them."""
    return [f"depth-gauge-fixture-{index:03d}".encode() for index in range(count)]


async def test_one_pass_sets_both_depths_from_the_brokers_own_view(amqp_url: str) -> None:
    """The healthy case: work queue at what was published, DLQ at zero.

    Nothing consumes, so every published message is *ready* and the ready count
    is the whole count — which is the only condition under which the gauge and
    the publish count are the same number.
    """
    await publish_bodies(amqp_url, await _messages(PUBLISHED))

    connection = await build_connection(amqp_url)
    async with connection:
        await read_queue_depths(connection)

    assert _gauge("prope_call_ledger_queue_depth") == PUBLISHED
    assert _gauge("prope_call_ledger_dlq_depth") == 0


async def test_a_dead_lettered_message_moves_the_dlq_gauge(amqp_url: str) -> None:
    """T-005's mitigation, end to end: one rejected message, one on the DLQ.

    The message is rejected with ``requeue=False``, which is what
    ``x-dead-letter-exchange`` acts on — so this exercises the declared topology
    (D-23) rather than a message this test placed on the DLQ by hand. Both gauges
    are asserted, because *"one moved to the other"* is the claim: the work queue
    is one lighter and the DLQ is one heavier.
    """
    await publish_bodies(amqp_url, await _messages(PUBLISHED))

    connection = await build_connection(amqp_url)
    async with connection:
        async with connection.channel() as channel:
            queue = await channel.get_queue(WORK_QUEUE)
            message = await queue.get(timeout=20)
            await message.nack(requeue=False)

        await read_queue_depths(connection)

    assert _gauge("prope_call_ledger_dlq_depth") == 1
    assert _gauge("prope_call_ledger_queue_depth") == PUBLISHED - 1


async def test_the_gauge_counts_ready_messages_and_not_the_unacknowledged_ones(
    amqp_url: str,
) -> None:
    """**Pitfall 10, asserted as semantics rather than reported as a bug.**

    RabbitMQ: *"Queue length is defined as the number of messages ready for
    delivery"*. A consumer holding messages unacknowledged has taken them out of
    that count without them having been written anywhere — and the real drain
    holds up to ``WINDOW_SIZE`` (500) at a time.

    So the assertion is an inequality and an exact remainder, not an equality
    against ``PUBLISHED``: a test that asserted the gauge still read seven would
    be asserting something the broker does not promise, and would fail the day
    somebody read this file for the meaning of the metric.

    The consequence carried at the gauge and worth repeating here: **a test
    asserting that a backlog cleared must assert the durable side — rows in
    ``ledger.call_record`` — rather than this gauge.** The gauge is a graph; the
    table is the fact.
    """
    await publish_bodies(amqp_url, await _messages(PUBLISHED))

    connection = await build_connection(amqp_url)
    async with connection:
        async with connection.channel() as holding:
            queue = await holding.get_queue(WORK_QUEUE)
            held = [await queue.get(timeout=20) for _ in range(HELD_UNACKED)]

            await read_queue_depths(connection)

            unacked = _gauge("prope_call_ledger_queue_depth")

            # Put them back, so the next assertion is about the same messages
            # rather than about a queue this test emptied.
            for message in held:
                await message.nack(requeue=True)

        await read_queue_depths(connection)

    assert unacked == PUBLISHED - HELD_UNACKED, "ready messages only, by RabbitMQ's definition"
    assert unacked < PUBLISHED, "the held messages were invisible to the gauge, as documented"
    assert _gauge("prope_call_ledger_queue_depth") == PUBLISHED, (
        "requeued messages are ready again, so the gauge sees the whole backlog"
    )


async def test_a_missing_queue_crashes_the_job_instead_of_freezing_the_gauge(
    amqp_url: str,
) -> None:
    """Pitfall 11, and the thing the supervision actually buys.

    A passive declare of a queue that does not exist is an AMQP **channel-level**
    error, which closes the channel it was issued on. The failure mode that
    matters is not the error — it is what a long-lived job holding one channel
    would do afterwards: read one gauge, fail on the second, and then be dead for
    every subsequent pass while the series it publishes sits frozen at its last
    value. A frozen gauge and a healthy one look identical on a graph.

    Because the pass opens a fresh channel per queue **and** because the job is
    supervised, the correct outcome is a **restarting job with a
    ``supervisor.job_crashed`` line** carrying its ``job`` field — visible,
    attributable, and recoverable the moment the queue exists. That field is in
    ``LOGGABLE_FIELDS`` only because its values are a closed set of job names
    fixed in ``prope.worker``'s source (A-046), so the assertion is on the
    constant rather than on a string typed here.

    The second job is the control that makes this a supervision test rather than
    an exception test: ``asyncio.TaskGroup`` cancels every sibling on the first
    unhandled child exception, and the whole reason ``run_with_restart`` wraps
    each job is that a crash in one resident must not stop the other two. If the
    wrapper were ever removed, ``ticks`` would stop.
    """
    stopping = asyncio.Event()
    crashed: list[dict] = []
    ticks: list[int] = []

    async def keeps_running() -> None:
        while not stopping.is_set():
            ticks.append(1)
            await asyncio.sleep(0.05)

    connection = await build_connection(amqp_url)
    async with connection:

        async def gauge_job_against_a_missing_queue() -> None:
            await interval_job(
                functools.partial(
                    read_queue_depths, connection, gauges=((NO_SUCH_QUEUE, queue_depth),)
                ),
                0.05,
                stopping,
            )

        with structlog.testing.capture_logs() as captured:
            supervisor = asyncio.create_task(
                supervise(
                    {
                        JOB_QUEUE_DEPTH_GAUGES: gauge_job_against_a_missing_queue,
                        "the_control": keeps_running,
                    },
                    stopping,
                )
            )
            loop = asyncio.get_running_loop()
            deadline = loop.time() + CRASH_DEADLINE_SECONDS
            try:
                while loop.time() < deadline:
                    crashed = [
                        record
                        for record in captured
                        if record["event"] == "supervisor.job_crashed"
                    ]
                    if crashed:
                        break
                    await asyncio.sleep(0.05)
            finally:
                stopping.set()
                await asyncio.wait_for(supervisor, timeout=20)

    assert crashed, "a passive declare of a missing queue did not surface as a crashed job"
    assert crashed[0]["job"] == JOB_QUEUE_DEPTH_GAUGES
    assert crashed[0]["reason"] == "ChannelNotFoundEntity", (
        f"the crash reason was {crashed[0]['reason']!r}; the documented class for a passive "
        "declare of a missing queue is ChannelNotFoundEntity, a ChannelClosed subclass"
    )
    assert ticks, "the sibling job stopped when its neighbour crashed; supervision is not working"


async def test_the_real_pass_reads_exactly_the_two_declared_queues() -> None:
    """The default pair is the topology's, not a list retyped in ``worker.py``.

    ``DEPTH_GAUGES`` is importable and a test could assert its contents against
    two string literals — which would pass on a typo in both places. The names
    come from ``prope.broker.topology``, where ``DLQ`` is *derived* from
    ``WORK_QUEUE`` so the pair cannot drift, and that identity is what is
    asserted here.
    """
    from prope.observability import dlq_depth
    from prope.worker import DEPTH_GAUGES

    assert DEPTH_GAUGES == ((WORK_QUEUE, queue_depth), (DLQ, dlq_depth))
