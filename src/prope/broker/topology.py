"""The one queue declaration both processes call (D-24, A-149, D-23).

``app`` declares on publisher startup and ``worker`` declares on consumer
startup, from this module and nowhere else. A worker-declares-only shape was
rejected because it turns deploy ordering into a data-loss question on the one
path that must never raise; a separate deploy-time init command was rejected for
the same reason. Declaring is idempotent, so both callers doing it is free.

**These values are one-way.** RabbitMQ answers a redeclare of an existing queue
with different arguments with ``PRECONDITION_FAILED`` (channel error 406). In any
environment that has already run, changing a TTL or a max-length here means
DELETING the queue — with whatever is sitting in it — and redeclaring. That is
D-23 read with its consequence attached, and it is why
``tests/broker/test_declared_arguments.py`` asserts these values against the
broker's own view in the same phase that declares them.

**Classic durable, not quorum.** A-149 requires that overflow *dead-letters
rather than drops*. ``reject-publish-dlx`` is the only overflow mode that both
dead-letters the overflowing message and ``basic.nack``s the publisher, and that
nack is precisely the signal ``prope_call_ledger_publish_failed_total{reason=
"nacked"}`` counts (D-21) and that ADR-0041's Phase 3 direct-write fallback
consumes. Quorum queues do not support ``reject-publish-dlx`` configurations at
all — their only overflow mode is ``drop-head``, which dead-letters the OLDEST
record and never nacks, so A-149 would be met in the letter and not in substance
and the Phase 3 fallback would never fire on overflow. A single-node host
(ADR-0033) also buys nothing from Raft replication, and classic mirroring was
removed in RabbitMQ 4.0, so "classic" no longer implies "mirrored" and carries no
deprecation smell.

**The accepted cost of that choice, stated rather than buried:** a classic queue
has no ``x-delivery-limit``, so poison-message dead-lettering is the drain's job
rather than the broker's. That work is real and it is this project's to own and
test — see ``prope.call_ledger.drain.classify_write_failure``.

**A-046.** Nothing in this module logs, and no value here is a metric label.
"""

from aio_pika.abc import AbstractChannel, AbstractQueue

#: A-142 §5: the ONLY work queue in Prope. A second broker queue was proposed
#: twice and rejected twice on merit; the DLQ below is not a second work queue,
#: it is INT-018's declared dead-letter target.
WORK_QUEUE = "prope.call_record"

#: A-142 §5: "DLQ naming is ``<queue>.dlq``". Derived rather than written out, so
#: the two names cannot drift apart in an edit.
DLQ = f"{WORK_QUEUE}.dlq"

#: A-149's four guarantees for the work queue, in the units RabbitMQ documents
#: them in. Every one of the six keys below is load-bearing and none is
#: stylistic.
#:
#: ``x-queue-type`` — ``classic``
#:     **The Task 1 checkpoint decision, written where it is enforced rather
#:     than only where it is explained.** Classic is RabbitMQ 4.x's default, so
#:     this argument changes nothing today — the broker reports
#:     ``x-queue-type: classic`` on this queue whether or not it is declared.
#:     It is written out anyway for two reasons. First, a decision that exists
#:     only as a default is a decision no reader can find and no test can
#:     assert; declared, it is greppable and it round-trips through the
#:     read-back assertion. Second, ``x-overflow: reject-publish-dlx`` is
#:     **not available on a quorum queue at all** — if a future broker default
#:     ever moved, this queue would silently become one whose only overflow mode
#:     is ``drop-head``, which dead-letters the OLDEST record and never nacks
#:     the publisher. That failure would be invisible until the day the queue
#:     filled. Declaring the type turns it into a declaration error instead.
#:
#: ``x-message-ttl`` — 86,400,000 ms, which is 24 hours
#:     Milliseconds, because that is the unit ``x-message-ttl`` is documented in;
#:     writing 24 * 60 * 60 * 1000 rather than the literal keeps the unit
#:     visible. A record that has sat here for a day is a record the drain has
#:     not been able to take for a day, and an expired message dead-letters
#:     rather than vanishing because ``x-dead-letter-exchange`` is set below.
#:     ONE-WAY: changing this after any environment has run requires deleting
#:     the queue.
#:
#: ``x-max-length`` — 1,000,000 messages
#:     The bound on how much unwritten traffic the broker will hold. Combined
#:     with ``x-overflow`` below, reaching it dead-letters the incoming record
#:     and nacks its publisher rather than silently discarding anything.
#:     ONE-WAY, same as the TTL.
#:
#: ``x-overflow`` — ``reject-publish-dlx``
#:     The one overflow mode that BOTH dead-letters the overflowing message and
#:     ``basic.nack``s the publisher (see the module docstring for why that
#:     matters and why it rules out a quorum queue). ``drop-head`` would drop
#:     the oldest record and stay silent; plain ``reject-publish`` would nack
#:     without dead-lettering, which fails A-149.
#:
#: ``x-dead-letter-exchange`` — the empty string
#:     The default exchange, which ALWAYS EXISTS. RabbitMQ's own documentation
#:     warns that a dead-letter exchange "does not have to be declared when the
#:     queue is declared but it should exist by the time messages need to be
#:     dead-lettered. If it is missing then, the messages are silently dropped."
#:     A named DLX would be a second thing to declare and a second way to lose
#:     records; the default exchange cannot be missing.
#:
#: ``x-dead-letter-routing-key`` — ``prope.call_record.dlq``
#:     **The argument whose ABSENCE loses data silently.** Dead-lettering to the
#:     default exchange without an explicit routing key re-publishes the message
#:     with its OWN routing key — which is the queue it just came from. RabbitMQ
#:     then detects the cycle and DROPS the message: "to prevent automatic
#:     infinite message looping within RabbitMQ, RabbitMQ will detect a cycle
#:     and drop the message if there was no rejection in the entire cycle."
#:     Because the exchange is the default one, the routing key IS the
#:     destination queue name. This is asserted back from the broker alongside
#:     the TTLs for exactly that reason.
WORK_QUEUE_ARGUMENTS: dict[str, str | int] = {
    "x-queue-type": "classic",
    "x-message-ttl": 24 * 60 * 60 * 1000,
    "x-max-length": 1_000_000,
    "x-overflow": "reject-publish-dlx",
    "x-dead-letter-exchange": "",
    "x-dead-letter-routing-key": DLQ,
}

#: A-149's two guarantees for the dead-letter queue.
#:
#: ``x-queue-type`` — ``classic``
#:     The same decision as the work queue and for consistency with it. The DLQ
#:     never publishes under overflow pressure, so ``reject-publish-dlx`` is not
#:     the argument here — but two queues in one topology with two queue types
#:     would be a difference somebody has to explain, and there is nothing to
#:     explain.
#:
#: ``x-message-ttl`` — 2,592,000,000 ms, which is 30 days
#:     The same window A-040 gives ``ledger.call_body``, so a dead-lettered
#:     record carrying a body does not outlive the body it duplicates.
#:     **A-149 ties this number to OQ-013, and OQ-013 is unresolved and rated
#:     Critical.** A number that moves when OQ-013 answers is a number whose
#:     change costs a queue delete-and-redeclare in every environment that has
#:     run. Recorded here so that cost is visible at the moment someone reaches
#:     for the edit, not discovered afterwards.
#:
#: ``x-max-length`` — 100,000 messages
#:     A hundredth of the work queue's bound. The DLQ is an inspection surface,
#:     not a second buffer.
#:
#: **No dead-letter arguments of its own, deliberately.** A dead-letter of a
#: dead-letter has nowhere honest to go, and pointing the DLQ back at anything
#: is how a cycle gets built.
DLQ_ARGUMENTS: dict[str, str | int] = {
    "x-queue-type": "classic",
    "x-message-ttl": 30 * 24 * 60 * 60 * 1000,
    "x-max-length": 100_000,
}


async def declare_topology(channel: AbstractChannel) -> AbstractQueue:
    """Declare the DLQ and then the work queue. Returns the work queue.

    Both are ``durable=True``: ADR-0028 requires the queue to survive a broker
    restart, and a durable queue holding persistent messages is the pair that
    makes that true — either half alone does not.

    The DLQ is declared FIRST. RabbitMQ does not require a dead-letter target to
    exist at declare time, so the order is not a protocol requirement; it is
    there because a missing target silently drops dead-lettered messages, and
    declaring in the order the messages flow means no window exists in which the
    work queue can dead-letter into nothing.

    Idempotent, so D-24's "both processes declare" costs one round trip per
    startup and nothing else — provided the arguments match. A redeclare with
    DIFFERENT arguments raises ``PRECONDITION_FAILED`` and closes the channel;
    that is the property ``tests/broker/test_declared_arguments.py`` uses as its
    negative control.
    """
    await channel.declare_queue(DLQ, durable=True, arguments=DLQ_ARGUMENTS)
    return await channel.declare_queue(
        WORK_QUEUE, durable=True, arguments=WORK_QUEUE_ARGUMENTS
    )
