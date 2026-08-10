"""D-23: the queue's declared arguments, read back FROM THE BROKER and asserted.

A-149's numbers are a one-way decision — RabbitMQ answers a redeclare with
different arguments with ``PRECONDITION_FAILED`` (channel error 406), so
changing a TTL or a max-length in any environment that has already run means
deleting the queue with whatever is in it and redeclaring. That is exactly why
D-23 requires the assertion to land in the same phase as the declaration: this
is the last cheap moment.

**Two shapes of assertion, and each covers what the other cannot.**

The positive assertion goes through the **management HTTP API**: GET the queue
resource and compare the broker's own ``arguments`` object against the module
constants. That is literally "reads them back from the broker", which is D-23's
wording, and it cannot pass by reading a dict the test built itself.

The negative controls go through **pure AMQP**: a non-passive redeclare with one
argument changed must be refused. A ``passive=True`` declare checks existence
only and ignores arguments entirely, so it cannot verify them — the refusal is
the only pure-AMQP proof that the STORED value differs from the offered one.

**A note the reader should not have to discover.** RabbitMQ's own documentation
recommends runtime **policies** over declare-time ``x-arguments``, precisely
because "hardcoded x-arguments ... cannot be updated without redeploying
applications and deleting the queue before it can be redeclared". D-23 locks
x-arguments anyway, and takes the irreversibility as its own argument. If an
operator later adds a same-valued policy alongside these arguments, note that
the two rules **disagree in direction**: for length limits "the minimum of the
two values specified is used", while for the dead-letter exchange "the one
specified in arguments overrules the one specified in policy".
"""

import pytest
from aio_pika.exceptions import ChannelPreconditionFailed

from prope.broker.connection import build_connection
from prope.broker.topology import (
    DLQ,
    DLQ_ARGUMENTS,
    WORK_QUEUE,
    WORK_QUEUE_ARGUMENTS,
    declare_topology,
)
from tests.broker._helpers import read_queue_from_management_api


async def _declare(amqp_url: str) -> None:
    connection = await build_connection(amqp_url)
    async with connection:
        channel = await connection.channel()
        await declare_topology(channel)


@pytest.mark.parametrize(
    ("queue_name", "expected"),
    [(WORK_QUEUE, WORK_QUEUE_ARGUMENTS), (DLQ, DLQ_ARGUMENTS)],
    ids=["work_queue", "dlq"],
)
async def test_the_broker_reports_the_arguments_that_were_declared(
    amqp_url: str, management_url: str, queue_name: str, expected: dict
) -> None:
    """Every declared argument, compared against the broker's own record of it.

    Whole-object equality rather than key-by-key: an EXTRA argument the broker
    holds and this project does not know about is as much a drift as a wrong
    value, and a per-key loop would not see one.
    """
    await _declare(amqp_url)

    reported = await read_queue_from_management_api(management_url, queue_name)

    assert reported["durable"] is True, "ADR-0028: the queue survives a broker restart"
    assert reported["arguments"] == expected

    # Spelled out separately, so a failure names the guarantee rather than
    # printing two dicts and leaving the reader to diff them.
    for key, value in expected.items():
        assert reported["arguments"][key] == value, f"{queue_name}: {key}"


async def test_the_dlq_carries_no_dead_letter_arguments_of_its_own(
    amqp_url: str, management_url: str
) -> None:
    """A dead-letter of a dead-letter has nowhere honest to go.

    Asserted as an ABSENCE, because the failure this guards against is somebody
    adding a DLX to the DLQ and building a cycle.
    """
    await _declare(amqp_url)

    reported = await read_queue_from_management_api(management_url, DLQ)

    assert "x-dead-letter-exchange" not in reported["arguments"]
    assert "x-dead-letter-routing-key" not in reported["arguments"]


async def test_a_redeclare_with_the_exact_arguments_succeeds(amqp_url: str) -> None:
    """The positive control for the negative controls below.

    Without this, every ``ChannelPreconditionFailed`` below would also be
    explained by "a redeclare always fails", which would make the whole negative
    suite vacuous.
    """
    await _declare(amqp_url)

    connection = await build_connection(amqp_url)
    async with connection:
        async with connection.channel() as channel:
            queue = await channel.declare_queue(
                WORK_QUEUE, durable=True, arguments=WORK_QUEUE_ARGUMENTS
            )
    assert queue.name == WORK_QUEUE


@pytest.mark.parametrize(
    ("argument", "wrong_value"),
    [
        ("x-message-ttl", 1),
        ("x-max-length", 1),
        ("x-overflow", "drop-head"),
        # The Task 1 checkpoint decision, asserted as a refusal. A quorum queue
        # cannot do reject-publish-dlx at all, so this is the argument whose
        # drift would meet A-149 in the letter and break it in substance.
        ("x-queue-type", "quorum"),
        # The one whose ABSENCE loses data silently: dead-lettering to the
        # default exchange without it re-publishes with the message's own
        # routing key, which is this queue, and the cycle detector drops it.
        ("x-dead-letter-routing-key", "nope"),
    ],
)
async def test_one_changed_argument_is_refused(
    amqp_url: str, argument: str, wrong_value: object
) -> None:
    """A non-passive redeclare with one argument changed raises 406.

    A fresh channel per attempt, because a failed declare CLOSES the channel it
    was issued on — reusing one would make every attempt after the first fail
    for the wrong reason.
    """
    await _declare(amqp_url)

    connection = await build_connection(amqp_url)
    async with connection:
        channel = await connection.channel()
        with pytest.raises(ChannelPreconditionFailed):
            await channel.declare_queue(
                WORK_QUEUE,
                durable=True,
                arguments={**WORK_QUEUE_ARGUMENTS, argument: wrong_value},
            )


async def test_a_redeclare_as_non_durable_is_refused(amqp_url: str) -> None:
    """Durability is part of the declaration too, and is equally one-way."""
    await _declare(amqp_url)

    connection = await build_connection(amqp_url)
    async with connection:
        channel = await connection.channel()
        with pytest.raises(ChannelPreconditionFailed):
            await channel.declare_queue(
                WORK_QUEUE, durable=False, arguments=WORK_QUEUE_ARGUMENTS
            )
