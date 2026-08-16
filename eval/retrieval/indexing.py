"""Index the evaluation corpus through the product's own extraction and embedding.

Same three steps ``worker.run_indexing_job`` runs — extract, embed, write the
row — minus RabbitMQ, which contributes nothing to ranking and a great deal to
wall-clock. Everything that shapes a result is the real thing: the DSPy
extraction program, the app-owned LM, ``domain.index_document``, the embedding
provider, and ``repository.create_index_record``.

**Artifacts are cached on disk, keyed by the exact text sent upstream.** An
eval that costs 200 LLM calls every time it runs is an eval nobody runs twice,
and comparing two rankers requires re-provisioning the same corpus at least
twice. Change what gets embedded and the key changes with it, so the cache
cannot serve a stale representation — that is the one thing it must never do.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import struct
import time
from dataclasses import dataclass
from pathlib import Path

from eval.retrieval.corpus import CorpusItem
from eval.retrieval.provision import EvalWorkspace

CACHE_DIR = Path(__file__).resolve().parents[2] / "eval" / "cache"
CACHE_FILE = CACHE_DIR / "artifacts.jsonl"


def _pack(vector: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vector)}f", *vector)).decode("ascii")


def _unpack(blob: str) -> list[float]:
    raw = base64.b64decode(blob)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


@dataclass(slots=True)
class Artifact:
    metadata: dict
    embedding: list[float]
    from_cache: bool = False


class ArtifactCache:
    """Append-only JSONL, loaded once. Not in git — it is derived data.

    **Extraction and embedding are cached separately, and the reason is the
    experiment.** Comparing two document formats means re-embedding the whole
    corpus; it does not mean re-extracting it, because the metadata depends on
    the prompt and not on how the document is assembled afterwards. One cache
    keyed on the assembled document would have charged 200 LLM calls for a
    change that touches none of them.
    """

    def __init__(self, path: Path = CACHE_FILE) -> None:
        self.path = path
        self._extractions: dict[str, dict] = {}
        self._embeddings: dict[str, list[float]] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("kind") == "embedding":
                    self._embeddings[record["key"]] = _unpack(record["value"])
                elif record.get("kind") == "extraction":
                    self._extractions[record["key"]] = record["value"]

    @staticmethod
    def key(*parts: str) -> str:
        digest = hashlib.sha256()
        for part in parts:
            digest.update(part.encode("utf-8"))
            digest.update(b"\x00")
        return digest.hexdigest()

    def _append(self, kind: str, key: str, value) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"kind": kind, "key": key, "value": value}) + "\n")

    def get_extraction(self, key: str) -> dict | None:
        return self._extractions.get(key)

    def put_extraction(self, key: str, metadata: dict) -> None:
        self._extractions[key] = metadata
        self._append("extraction", key, metadata)

    def get_embedding(self, key: str) -> list[float] | None:
        return self._embeddings.get(key)

    def put_embedding(self, key: str, embedding: list[float]) -> None:
        self._embeddings[key] = embedding
        self._append("embedding", key, _pack(embedding))

    def __len__(self) -> int:
        return len(self._extractions) + len(self._embeddings)

    def summary(self) -> str:
        return f"{len(self._extractions)} extractions, {len(self._embeddings)} embeddings"


async def _embed(text: str) -> list[float]:
    from prope.prompt_search.agent.base import call_app_service, embedding_request, get_embedding_client

    client = await get_embedding_client()
    response = await call_app_service(lambda: client.embeddings.create(**embedding_request(text)))
    return list(response.data[0].embedding)


async def build_artifact(item: CorpusItem, cache: ArtifactCache) -> Artifact:
    """Extraction then embedding for one prompt, in the worker's order.

    The order is not incidental: ``build_index_document`` embeds the extraction,
    so the extraction has to exist first. That is also why the worker runs them
    in this sequence and why the two caches are keyed differently — the metadata
    depends on the prompt, the vector depends on the metadata.
    """
    from prope.prompt_search.agent import ExtractionContext, extract_metadata
    from prope.prompt_search.domain import ExtractedMetadata, build_index_document

    extraction_key = cache.key("extract-v1", item.title, item.purpose, item.body)
    metadata_dict = cache.get_extraction(extraction_key)
    hit = metadata_dict is not None
    if metadata_dict is None:
        metadata = await extract_metadata(
            body=item.body,
            purpose=item.purpose,
            title=item.title,
            context=ExtractionContext(
                workspace_id="eval",
                actor_id="eval-harness",
                prompt_id=item.stem,
                version_id="eval",
            ),
        )
        metadata_dict = metadata.to_dict()
        cache.put_extraction(extraction_key, metadata_dict)

    document = build_index_document(
        title=item.title,
        purpose=item.purpose,
        body=item.body,
        metadata=ExtractedMetadata.from_dict(metadata_dict),
    )
    embedding_key = cache.key("embed-v1", os.environ.get("EMBEDDING_MODEL", ""), document)
    embedding = cache.get_embedding(embedding_key)
    if embedding is None:
        hit = False
        embedding = await _embed(document)
        cache.put_embedding(embedding_key, embedding)

    return Artifact(metadata=metadata_dict, embedding=embedding, from_cache=hit)


@dataclass(slots=True)
class IndexReport:
    indexed: int = 0
    cached: int = 0
    failed: int = 0
    seconds: float = 0.0
    errors: list[str] = None  # type: ignore[assignment]
    #: How many prompts have a >= 0.9 neighbour. A uniformity measure for the
    #: corpus, and the number the duplicate warning fires on.
    near_duplicates: int = 0

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


async def index_corpus(
    workspace: EvalWorkspace,
    items: list[CorpusItem],
    *,
    cache: ArtifactCache,
    concurrency: int = 6,
    progress=None,
) -> IndexReport:
    from prope.db.session import workspace_transaction
    from prope.prompt_search import repository
    from prope.prompt_search.domain import ExtractedMetadata

    report = IndexReport()
    started = time.perf_counter()
    gate = asyncio.Semaphore(concurrency)
    done = 0

    async def one(item: CorpusItem) -> None:
        nonlocal done
        prompt_id = workspace.prompt_id_by_stem.get(item.stem)
        version_id = workspace.version_id_by_stem.get(item.stem)
        if prompt_id is None or version_id is None:
            report.failed += 1
            report.errors.append(f"{item.stem}: not seeded")
            return
        async with gate:
            try:
                artifact = await build_artifact(item, cache)
                if artifact.from_cache:
                    report.cached += 1
                async with workspace_transaction(workspace.sessionmaker, workspace.workspace_id) as db:
                    neighbours = await repository.find_nearest_neighbors(
                        db,
                        workspace_id=workspace.workspace_id,
                        embedding=artifact.embedding,
                        exclude_prompt_id=prompt_id,
                    )
                    nearest = neighbours[0] if neighbours else None
                    if nearest is not None:
                        report.near_duplicates += 1
                    await repository.create_index_record(
                        db,
                        id=f"psi_{prompt_id[-24:]}",
                        prompt_id=prompt_id,
                        version_id=version_id,
                        workspace_id=workspace.workspace_id,
                        role="latest",
                        metadata=ExtractedMetadata.from_dict(artifact.metadata),
                        embedding=artifact.embedding,
                        indexed_by=workspace.user_id,
                        nearest_neighbor_id=nearest["prompt_id"] if nearest else None,
                        nearest_neighbor_similarity=float(nearest["similarity"]) if nearest else None,
                    )
                report.indexed += 1
            except Exception as error:  # one bad prompt must not end the run
                report.failed += 1
                report.errors.append(f"{item.stem}: {type(error).__name__}: {error}")
            finally:
                done += 1
                if progress is not None and done % 10 == 0:
                    progress(done, len(items))

    await asyncio.gather(*(one(item) for item in items))
    report.seconds = time.perf_counter() - started
    return report
