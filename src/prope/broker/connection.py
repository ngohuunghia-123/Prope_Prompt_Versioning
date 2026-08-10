"""Broker connection and channel construction. Deliberately thin.

The shape of ``prope.db.engine``, for the same reason: the only opinions worth
expressing here are the two non-obvious kwargs, and everything else is a call to
the library.

**One long-lived robust connection with a single confirm-mode channel, not a
pool.** This resolves the CONTEXT discretion item rather than leaving it to a
call site. D-25 puts exactly ONE background publisher task on this channel — the
handoff queue has one drainer — so a pool would be idle capacity bought with a
lifecycle to get wrong, and ``connect_robust`` already supplies transparent
reconnection with full state recovery, which is the thing a pool is usually
reached for. If a second publisher ever appears, this is the module that
changes, and the change will be visible.

**Publisher confirms are aio-pika's default and are not disabled here.** A
confirm is what makes ``prope_call_ledger_publish_failed_total``'s three reasons
observable at all: without it ``publish`` returns as soon as the frame is
written and D-21 has nothing to count.

**A-046.** Nothing in this module logs. A broker URL carries credentials, so it
is never written to a log line or a metric label — the fact that it is only ever
passed, never formatted, is the control.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractRobustConnection


async def build_connection(url: str) -> AbstractRobustConnection:
    """A robust AMQP connection over ``url``.

    ``connect_robust`` rather than ``connect``: it reconnects transparently and
    recovers channels, queues and consumers after a broker restart, which is the
    difference between a worker that resumes and a worker that has to be
    restarted by hand. aio-pika 9.6.0 specifically fixed callback-based
    consumers and queue iterators failing to resume across a reconnection, which
    is a reason the pin sits where it does.
    """
    return await aio_pika.connect_robust(url)


@asynccontextmanager
async def publisher_channel(
    connection: AbstractRobustConnection,
) -> AsyncIterator[AbstractChannel]:
    """One channel in confirm mode, closed on exit.

    ``publisher_confirms=True`` is aio-pika's default and is written out anyway:
    it is the property D-21's whole failure classification rests on, and a
    default that goes unstated is a default somebody can turn off without
    noticing what it was holding up.
    """
    async with connection.channel(publisher_confirms=True) as channel:
        yield channel
