"""Worker consumer for prompt-search indexing jobs.

Consumes from prope.call_record queue (shared with call-ledger).
Message format:
{
    "type": "prompt_search_index",
    "job_id": "psj_...",
    "prompt_id": "prm_...",
    "version_id": "rev_...",
    "workspace_id": "ws_...",
    "created_by": "usr_...",
    "role": "latest" | "released"
}

Flow:
1. Mark job as running
2. Load prompt and revision from registry
3. Extract metadata via App Agent
4. Extract the declared output contract into a normalized descriptor
5. Embed title + purpose + body
6. Find nearest neighbors
7. Write the `latest` or `released` index row
8. Mark job as completed

Step 4 is the comparison funnel's stage 2b, paid here rather than at comparison
time: the descriptor is a property of ONE revision, so extracting it per pair
would cost six calls per import instead of one and would show an extractor two
`<output_format>` blocks at once, which biases it toward finding them alike. It
fails soft — a NULL column reads downstream as *not established*.

A prompt holds at most two index rows and `role` says which one this job is
(migration 0014). Only `released` requires an approved, currently-released
revision; `latest` indexes whatever was just saved, which is what makes a
freshly imported draft findable by the duplicate check.
"""

import json
from asyncio import Event
from typing import Literal

import structlog
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from prope.app_agent.telemetry import flush_langfuse
from prope.db.session import workspace_transaction
from prope.prompt_registry.domain import RevisionStatus
from prope.prompt_registry.repository import load_prompt, load_revision
from prope.prompt_search import repository
from prope.prompt_search.agent import (
    ExtractionContext,
    extract_metadata,
    get_embedding_client,
    warm_extraction_agent,
)
from prope.prompt_search.agent.comparison import (
    ComparisonContext,
    extract_output_descriptor,
    warm_comparison_agent,
)
from prope.prompt_search.comparison import declared_output_text
from prope.prompt_search.domain import IndexJobStatus, build_index_document
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
    #: Which of the prompt's two index rows this job writes. Defaulted rather
    #: than required so a message published before migration 0014 — one already
    #: sitting in the durable queue across a deploy — still parses, and parses as
    #: what it meant when it was written.
    role: Literal["latest", "released"] = "released"


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
        if revision is None or revision.prompt_id != envelope.prompt_id:
            raise ValueError(f"No such revision for prompt: {envelope.prompt_id}")

        # **The `released` row still has to BE the released one.** Only the
        # `latest` row is allowed to hold unapproved text: it exists so that a
        # prompt somebody is drafting can be found by the duplicate check before
        # anybody has approved anything, which is the whole point of importing
        # into a registry rather than a folder. Letting a draft overwrite the
        # `released` row would put unreviewed text where every read that asks
        # *"what is in production"* would find it — the one conflation this
        # module must not make.
        if envelope.role == "released" and (
            revision.status is not RevisionStatus.APPROVED
            or prompt.released_version_id != envelope.version_id
        ):
            raise ValueError(f"No current released revision for prompt: {envelope.prompt_id}")

        # Extract metadata via App Agent. The context carries identifiers only —
        # it is what ties this job's Langfuse trace back to the workspace, the
        # actor who asked for the index, and the job row, without any of the
        # three text fields being sent to the telemetry backend.
        failure_reason = "agent_error"
        metadata = await extract_metadata(
            body=revision.body,
            purpose=prompt.purpose,
            title=prompt.title,
            context=ExtractionContext(
                workspace_id=envelope.workspace_id,
                actor_id=envelope.created_by,
                prompt_id=envelope.prompt_id,
                version_id=envelope.version_id,
                job_id=job_id,
            ),
        )

        # The declared output contract, extracted once per revision and cached on
        # the index row (migration 0035). Two reasons it belongs HERE rather than
        # at comparison time: a comparison against five candidates would
        # otherwise cost six extractions instead of one, and an extractor shown
        # two `<output_format>` blocks at once is drawn toward finding them
        # alike — so it must never see a pair.
        #
        # **Failure is not a job failure.** `extract_output_descriptor` returns
        # `None` when the agent is unreachable or the prompt declares nothing,
        # and a NULL column reads downstream as *not established*, which is the
        # honest answer. Refusing to index a prompt because a secondary
        # extraction failed would trade the module's main job for its newest one.
        declared_output, source_block = declared_output_text(revision.body)
        descriptor = await extract_output_descriptor(
            declared_output=declared_output,
            source_block=source_block,
            context=ComparisonContext(
                workspace_id=envelope.workspace_id,
                actor_id=envelope.created_by,
                correlation_id=job_id,
            ),
        )

        # Get embedding. The extraction above ran on the App Agent's client;
        # this one is the embedding provider's, which may be a different host.
        #
        # **Title, purpose AND body**. Embedding the purpose alone is what made
        # the import screen's duplicate check useless: it compared a pasted
        # two-thousand-word instruction against one-line descriptions, which are
        # not near each other in any embedding space however similar the two
        # prompts actually are.
        #
        # And now the extraction above leads the document (`build_index_document`).
        # It is a model-written compression of this exact prompt, it is already
        # paid for, and on a corpus of documents in one genre it is the part that
        # tells two of them apart — see `domain.enriched_index_document`.
        failure_reason = "embedding_error"
        client = await get_embedding_client()
        embedding, cache_hit = await repository.get_or_create_embedding(
            db,
            envelope.workspace_id,
            build_index_document(
                title=prompt.title,
                purpose=prompt.purpose,
                body=revision.body,
                metadata=metadata,
            ),
            client,
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
            role=envelope.role,
            metadata=metadata,
            embedding=embedding,
            indexed_by=envelope.created_by,
            nearest_neighbor_id=nearest_neighbor_id,
            nearest_neighbor_similarity=nearest_neighbor_similarity,
            output_descriptor=descriptor.to_dict() if descriptor is not None else None,
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
                "output_contract_declared": descriptor is not None,
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
    channel: AbstractChannel,
) -> bool:
    """Consume one prompt-search envelope from the shared work queue.

    ``channel`` is the consumer's own aio_pika channel, and it is a parameter
    because ``message.channel`` is **not the same kind of object** — it is the
    underlying `aiormq` channel, which has no ``declare_exchange``. Publishing
    the completion event through it raised `AttributeError` *after* the index row
    had committed, so the message was never acked, came back, and failed the
    second time against its own now-completed job row. The index was correct and
    the job said it had failed.

    That went unseen because nothing reached this line: indexing used to require
    a released revision, and the failure needed an index that actually completed.
    """
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
            channel,
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

    # Pay DSPy's eleven-second import while the queue is being declared rather
    # than inside the first job, where it would sit inside that job's
    # `extraction_duration_seconds` observation and make the p95 a lie.
    await warm_extraction_agent()
    await warm_comparison_agent()

    try:
        async with queue.iterator() as messages:
            async for message in messages:
                await handle_indexing_message(message, sessionmaker, channel)
                if stopping.is_set():
                    return
    finally:
        # The SDK exports on a background thread. Without this a container that
        # is told to stop takes the last job's trace with it, and the traces that
        # go missing are disproportionately the ones from a crash.
        flush_langfuse()
