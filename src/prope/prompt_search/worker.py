"""Worker consumer for prompt-search indexing jobs.

Consumes from prope.call_record queue (shared with call-ledger).
Message format:
{
    "type": "prompt_search_index",
    "job_id": "psj_...",
    "prompt_id": "prm_...",
    "version_id": "rev_...",
    "workspace_id": "ws_...",
    "created_by": "usr_..."
}

Flow:
1. Mark job as running
2. Load prompt and revision from registry
3. Extract metadata via App Agent
4. Generate embedding
5. Find nearest neighbors
6. Write index record
7. Mark job as completed
"""

import json
from asyncio import Event

import structlog
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from prope.db.session import workspace_transaction
from prope.prompt_registry.domain import RevisionStatus
from prope.prompt_registry.repository import load_prompt, load_revision
from prope.prompt_search import repository
from prope.prompt_search.agent import extract_metadata, get_openai_client
from prope.prompt_search.domain import IndexJobStatus
from prope.prompt_search.events import publish_event
from prope.prompt_search.seams import declare_search_queue

log = structlog.get_logger(__name__)

#: Queue name for prompt-search indexing
DUPLICATE_THRESHOLD = repository.DUPLICATE_SIMILARITY_THRESHOLD


class IndexingEnvelope(BaseModel):
    """Envelope from the queue."""

    model_config = ConfigDict(extra="forbid")

    type: str
    job_id: str
    prompt_id: str
    version_id: str
    workspace_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    created_by: str


def parse_envelope(body: bytes) -> IndexingEnvelope | None:
    """Parse indexing envelope from message body."""
    try:
        data = json.loads(body)
        if not isinstance(data, dict) or data.get("type") != "prompt_search_index":
            return None
        return IndexingEnvelope.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return None


async def run_indexing_job(
    db: AsyncSession,
    envelope: IndexingEnvelope,
) -> bool:
    """Execute a single indexing job.

    Returns True on success, False on failure.
    """
    from prope.prompt_search.observability import index_completed_total, index_failed_total

    job_id = envelope.job_id
    failure_reason = "db_error"
    persisted_job_matches = False
    savepoint = await db.begin_nested()

    try:
        # Mark job as started
        job = await repository.get_job_status(db, job_id)
        if (
            job is None
            or job.status is not IndexJobStatus.PENDING
            or (
                job.prompt_id != envelope.prompt_id
                or job.version_id != envelope.version_id
                or job.workspace_id != envelope.workspace_id
                or job.created_by != envelope.created_by
            )
        ):
            raise ValueError("indexing envelope does not match its persisted job")
        persisted_job_matches = True
        await repository.update_job_started(db, job_id)
        log.info("prompt_search.job_started", job_id=job_id, prompt_id=envelope.prompt_id)

        # Load prompt and revision
        prompt = await load_prompt(db, envelope.prompt_id)
        if prompt is None:
            raise ValueError(f"Prompt not found: {envelope.prompt_id}")

        revision = await load_revision(db, envelope.version_id)
        if (
            revision is None
            or revision.prompt_id != envelope.prompt_id
            or revision.status is not RevisionStatus.APPROVED
            or prompt.released_version_id != envelope.version_id
        ):
            raise ValueError(f"No current released revision for prompt: {envelope.prompt_id}")

        # Extract metadata via App Agent
        failure_reason = "agent_error"
        metadata = await extract_metadata(
            body=revision.body,
            purpose=prompt.purpose,
            title=prompt.title,
        )

        # Get embedding
        failure_reason = "embedding_error"
        client = await get_openai_client()
        embedding, cache_hit = await repository.get_or_create_embedding(
            db, envelope.workspace_id, prompt.purpose, client
        )

        # Find nearest neighbors for duplicate detection
        failure_reason = "db_error"
        neighbors = await repository.find_nearest_neighbors(
            db,
            workspace_id=envelope.workspace_id,
            embedding=embedding,
            exclude_prompt_id=envelope.prompt_id,
            threshold=DUPLICATE_THRESHOLD,
        )

        nearest_neighbor_id = None
        nearest_neighbor_similarity = None
        has_warning = False

        if neighbors:
            nearest = neighbors[0]
            similarity = nearest.get("similarity", 0)
            if similarity >= DUPLICATE_THRESHOLD:
                has_warning = True
                nearest_neighbor_id = nearest["prompt_id"]
                nearest_neighbor_similarity = similarity
                log.info(
                    "prompt_search.duplicate_detected",
                    job_id=job_id,
                    prompt_id=envelope.prompt_id,
                    neighbor_id=nearest_neighbor_id,
                    similarity=nearest_neighbor_similarity,
                )

        # Create index record
        index_id = f"psi_{ULID()}"
        await repository.create_index_record(
            db,
            id=index_id,
            prompt_id=envelope.prompt_id,
            version_id=envelope.version_id,
            workspace_id=envelope.workspace_id,
            metadata=metadata,
            embedding=embedding,
            indexed_by=envelope.created_by,
            nearest_neighbor_id=nearest_neighbor_id,
            nearest_neighbor_similarity=nearest_neighbor_similarity,
        )

        # Mark job as completed
        await repository.update_job_completed(
            db,
            job_id=job_id,
            result_json={
                "index_id": index_id,
                "keywords_count": len(metadata.keywords),
                "topics_count": len(metadata.topics),
                "nearest_neighbor_id": nearest_neighbor_id,
                "nearest_neighbor_similarity": nearest_neighbor_similarity,
                "cache_hit": cache_hit,
            },
        )
        await savepoint.commit()

        # Update metrics
        index_completed_total.labels(
            workspace_id=envelope.workspace_id,
            with_dup_warning=str(has_warning).lower(),
        ).inc()

        log.info(
            "prompt_search.job_completed",
            job_id=job_id,
            prompt_id=envelope.prompt_id,
            workspace_id=envelope.workspace_id,
        )

        return True

    except Exception as error:
        if savepoint.is_active:
            await savepoint.rollback()
        safe_error = {
            "agent_error": "metadata extraction failed",
            "embedding_error": "embedding generation failed",
            "db_error": "index persistence failed",
        }[failure_reason]
        if persisted_job_matches:
            await repository.update_job_failed(db, job_id, error=safe_error)

        index_failed_total.labels(
            workspace_id=envelope.workspace_id,
            reason=failure_reason,
        ).inc()

        log.error(
            "prompt_search.job_failed",
            job_id=job_id,
            prompt_id=envelope.prompt_id,
            workspace_id=envelope.workspace_id,
            reason=type(error).__name__,
        )

        return False


async def handle_indexing_message(
    message: AbstractIncomingMessage,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> bool:
    """Consume one prompt-search envelope from the shared work queue."""
    envelope = parse_envelope(message.body)
    if envelope is None:
        try:
            payload = json.loads(message.body)
        except json.JSONDecodeError:
            await message.reject(requeue=False)
            return True
        if not isinstance(payload, dict) or payload.get("type") != "prompt_search_index":
            await message.reject(requeue=False)
            return True
        await message.reject(requeue=False)
        return True

    index = None
    async with workspace_transaction(sessionmaker, envelope.workspace_id) as db:
        await repository.delete_expired_completed_jobs(db)
        succeeded = await run_indexing_job(db, envelope)
        if succeeded:
            index = await repository.get_index_by_prompt(db, envelope.prompt_id)
    if index is not None:
        await publish_event(
            message.channel,
            "prope.prompt_indexed",
            {
                "prompt_id": index.prompt_id,
                "version_id": index.version_id,
                "indexed_by": index.indexed_by,
                "keywords_count": len(index.keywords),
                "topics_count": len(index.topics),
                "nearest_neighbor_id": index.nearest_neighbor_id,
                "nearest_neighbor_similarity": index.nearest_neighbor_similarity,
            },
        )
    await message.ack()
    return True


async def run_indexing_consumer(
    channel: AbstractChannel,
    sessionmaker: async_sessionmaker[AsyncSession],
    stopping: Event,
) -> None:
    """Consume prompt indexing independently from call-ledger ingestion."""
    await channel.set_qos(prefetch_count=1)
    queue = await declare_search_queue(channel)
    async with queue.iterator() as messages:
        async for message in messages:
            await handle_indexing_message(message, sessionmaker)
            if stopping.is_set():
                return
