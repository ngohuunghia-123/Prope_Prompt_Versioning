"""Broker events published by prompt-search after durable state changes."""

import json

from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractChannel

EVENT_EXCHANGE = "prope.events"


async def publish_event(channel: AbstractChannel, topic: str, payload: dict[str, object]) -> None:
    exchange = await channel.declare_exchange(EVENT_EXCHANGE, ExchangeType.TOPIC, durable=True)
    await exchange.publish(
        Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
        ),
        routing_key=topic,
        mandatory=False,
    )


__all__ = ["EVENT_EXCHANGE", "publish_event"]
