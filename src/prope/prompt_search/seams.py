"""In-process seams for prompt-search.

Provides:
  - enqueue_index_job: persist a job row and publish it, never raising
  - publish_indexing_job: publish an indexing job to RabbitMQ
  - PromptSearchExtractionResult: result from the extraction worker

These are the only ways other modules interact with prompt-search.
"""

import json

import structlog
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel, AbstractQueue
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

log = structlog.get_logger(__name__)

__all__ = [
    "PromptSearchExtractionResult",
    "enqueue_index_job",
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
    role: str = "released",
) -> None:
    """Publish an indexing job onto prompt-search's own durable queue.

    ``role`` says WHICH of a prompt's two index rows this job writes —
    ``latest`` for the revision somebody just saved, ``released`` for the one
    production is serving. It defaults to ``released`` so that the manual
    *"index this prompt"* button keeps its original meaning.

    **This is the only way another module asks for an index, and it is
    deliberately a message rather than a call.** Indexing runs an LLM extraction
    and an embedding — seconds of upstream latency, sometimes tens of them. A
    save that waited for both would be a save that fails when a third party is
    slow, which is the opposite of what a registry is for. The publish is also
    the caller's LAST act: it happens after their transaction commits, so a
    worker cannot pick up a job for a revision that was rolled back.
    """
    envelope = {
        "type": "prompt_search_index",
        "job_id": job_id,
        "prompt_id": prompt_id,
        "version_id": version_id,
        "workspace_id": workspace_id,
        "created_by": created_by,
        "role": role,
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


async def enqueue_index_job(
    sessionmaker: async_sessionmaker[AsyncSession],
    channel: AbstractChannel | None,
    *,
    prompt_id: str,
    version_id: str,
    workspace_id: str,
    created_by: str,
    role: str = "latest",
) -> str | None:
    """Ask for a prompt to be indexed. **Never raises, and never blocks a save.**

    Two writes the caller should not have to know about: a job row, so the worker
    can verify a message against something durable rather than trusting the queue,
    and the publish itself. Both live here because the caller is another bounded
    context — the registry may reach exactly this module and only through this
    file, and a version of this that handed back a repository would be an edge
    into prompt-search's internals wearing a seam's name.

    **Every failure is swallowed and logged, and that is the contract.** This is
    called after a revision has already been committed. Indexing is a
    convenience — it makes the prompt findable by the duplicate check — and a
    broker that is down, or a search schema mid-migration, must not turn a saved
    revision into a 500 for work the author already finished. The prompt simply
    stays unindexed, which the product already renders honestly, and re-indexing
    is a button.

    Returns the job id when the job was enqueued, and ``None`` when it was not,
    so a caller that wants to report *"indexing queued"* can tell the difference.
    """
    if channel is None:
        log.warning("prompt_search.enqueue_skipped", prompt_id=prompt_id, reason="no_broker_channel")
        return None

    job_id = f"psj_{ULID()}"
    try:
        from prope.db.session import workspace_transaction
        from prope.prompt_search import repository

        async with workspace_transaction(sessionmaker, workspace_id) as db:
            await repository.create_job_record(
                db,
                job_id=job_id,
                prompt_id=prompt_id,
                version_id=version_id,
                workspace_id=workspace_id,
                created_by=created_by,
            )
        await publish_indexing_job(
            channel,
            job_id=job_id,
            prompt_id=prompt_id,
            version_id=version_id,
            workspace_id=workspace_id,
            created_by=created_by,
            role=role,
        )
    except Exception as error:
        log.warning(
            "prompt_search.enqueue_failed",
            job_id=job_id,
            prompt_id=prompt_id,
            workspace_id=workspace_id,
            reason=type(error).__name__,
        )
        return None

    return job_id
