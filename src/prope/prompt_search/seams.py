"""In-process seams for prompt-search.

Provides:
  - publish_indexing_job: publish an indexing job to RabbitMQ
  - PromptSearchExtractionResult: result from the extraction worker

These are the only ways other modules interact with prompt-search.
"""

import json

import structlog
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel, AbstractQueue
from pydantic import BaseModel

log = structlog.get_logger(__name__)

__all__ = [
    "PromptSearchExtractionResult",
    "publish_indexing_job",
    "declare_search_queue",
]

SEARCH_INDEX_QUEUE = "prope.prompt_search.index"


async def declare_search_queue(channel: AbstractChannel) -> AbstractQueue:
    """Declare prompt-search's durable queue in both publishing processes."""
    return await channel.declare_queue(
        SEARCH_INDEX_QUEUE,
        durable=True,
        arguments={"x-queue-type": "classic", "x-message-ttl": 24 * 60 * 60 * 1000},
    )


class PromptSearchExtractionResult(BaseModel):
    """Result from the extraction agent, passed through the queue."""

    job_id: str
    prompt_id: str
    version_id: str
    workspace_id: str
    metadata: dict
    embedding: list[float]
    nearest_neighbor_id: str | None
    nearest_neighbor_similarity: float | None
    indexed_by: str


async def publish_indexing_job(
    channel,
    job_id: str,
    prompt_id: str,
    version_id: str,
    workspace_id: str,
    created_by: str,
) -> None:
    """Publish an indexing job to the queue.

    Uses the same queue as call-ledger for simplicity.
    """
    envelope = {
        "type": "prompt_search_index",
        "job_id": job_id,
        "prompt_id": prompt_id,
        "version_id": version_id,
        "workspace_id": workspace_id,
        "created_by": created_by,
    }

    await channel.default_exchange.publish(
        Message(
            body=json.dumps(envelope).encode(),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
        ),
        routing_key=SEARCH_INDEX_QUEUE,
        mandatory=True,
    )

    log.info(
        "prompt_search.job_published",
        job_id=job_id,
        prompt_id=prompt_id,
        workspace_id=workspace_id,
    )
