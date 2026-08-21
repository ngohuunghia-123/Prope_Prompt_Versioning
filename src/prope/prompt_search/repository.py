"""Repository: every read and write for prompt-search.

Permission filtering lives HERE, not in handlers (A-118, T-019).
The visible_subject_filter is applied in every list query.

Tables:
  - prompt_search_index (psi_): extracted metadata and embeddings
  - prompt_search_index_job (psj_): job lifecycle tracking

Raw SQL for pgvector similarity search (A-128 carve-out).
"""

import json
import os
import time
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.access_control.domain import VisibleFilter
from prope.prompt_registry import repository as registry_repository
from prope.prompt_registry.domain import PromptRow
from prope.prompt_search import ranking
from prope.prompt_search.domain import (
    ExtractedMetadata,
    ExtractedVariations,
    IndexJobRow,
    IndexJobStatus,
    IndexRow,
    SearchResult,
    query_terms,
)
from prope.prompt_search.models import prompt_search_index
from prope.prompt_search.observability import (
    ai_duration_seconds,
    embedding_cache_hits_total,
    embedding_cache_misses_total,
    quick_duration_seconds,
    result_count_bucket,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "create_index_record",
    "create_job_record",
    "delete_expired_completed_jobs",
    "find_nearest_neighbors",
    "get_index_by_prompt",
    "get_job_status",
    "get_or_create_embedding",
    "list_prompts_for_quick_search",
    "MIN_SEARCH_SIMILARITY",
    "search_prompts_hybrid",
    "update_job_completed",
    "update_job_failed",
    "update_job_started",
]

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

#: Embedding cache table name
EMBEDDING_CACHE_TABLE = "search.embedding_cache"

#: Duplicate similarity threshold
DUPLICATE_SIMILARITY_THRESHOLD = float(os.environ.get("SEARCH_DUPLICATE_THRESHOLD", "0.9"))

#: Embedding model dimensions
EMBEDDING_DIMENSIONS = 1536


# --- SQL Statements ---

#: Check if embedding exists in cache
CHECK_EMBEDDING_CACHE = text(
    """
    SELECT embedding_vector
    FROM search.embedding_cache
    WHERE workspace_id = :workspace_id AND text_hash = :text_hash
      AND embedding_model = :embedding_model
    LIMIT 1
    """
)

#: Insert embedding into cache
INSERT_EMBEDDING_CACHE = text(
    """
    INSERT INTO search.embedding_cache
        (id, workspace_id, text_hash, embedding_model, embedding_vector, created_at)
    VALUES (:id, :workspace_id, :text_hash, :embedding_model, :embedding_vector, NOW())
    ON CONFLICT (workspace_id, text_hash, embedding_model) DO NOTHING
    """
)

#: Create index record
INSERT_INDEX = text(
    """
    INSERT INTO search.prompt_search_index
        (id, prompt_id, version_id, workspace_id, role, keywords, topics, entities,
         variations, language, content_embedding, embedding_model, is_bilingual, indexed_at,
         indexed_by, nearest_neighbor_id, nearest_neighbor_similarity, output_descriptor)
    VALUES
        (:id, :prompt_id, :version_id, :workspace_id, :role, :keywords, :topics,
         :entities, CAST(:variations AS jsonb), :language, :content_embedding, :embedding_model, :is_bilingual,
         NOW(), :indexed_by, :nearest_neighbor_id, :nearest_neighbor_similarity,
         CAST(:output_descriptor AS jsonb))
    ON CONFLICT (prompt_id, role) DO UPDATE SET
        id = EXCLUDED.id, version_id = EXCLUDED.version_id,
        workspace_id = EXCLUDED.workspace_id, keywords = EXCLUDED.keywords,
        topics = EXCLUDED.topics, entities = EXCLUDED.entities,
        variations = EXCLUDED.variations, language = EXCLUDED.language,
        content_embedding = EXCLUDED.content_embedding,
        embedding_model = EXCLUDED.embedding_model,
        is_bilingual = EXCLUDED.is_bilingual, indexed_at = NOW(),
        indexed_by = EXCLUDED.indexed_by,
        nearest_neighbor_id = EXCLUDED.nearest_neighbor_id,
        nearest_neighbor_similarity = EXCLUDED.nearest_neighbor_similarity,
        output_descriptor = EXCLUDED.output_descriptor
    """
)

#: Create job record
INSERT_JOB = text(
    """
    INSERT INTO search.prompt_search_index_job
        (job_id, prompt_id, version_id, workspace_id, status, created_by)
    VALUES
        (:job_id, :prompt_id, :version_id, :workspace_id, :status, :created_by)
    """
)

#: Update job started
UPDATE_JOB_STARTED = text(
    """
    UPDATE search.prompt_search_index_job
    SET status = 'running', started_at = NOW()
    WHERE job_id = :job_id
    """
)

#: Update job completed
UPDATE_JOB_COMPLETED = text(
    """
    UPDATE search.prompt_search_index_job
    SET status = 'completed', completed_at = NOW(), result_json = CAST(:result_json AS jsonb)
    WHERE job_id = :job_id
    """
)

#: Update job failed
UPDATE_JOB_FAILED = text(
    """
    UPDATE search.prompt_search_index_job
    SET status = 'failed', completed_at = NOW(), error = :error
    WHERE job_id = :job_id
    """
)

#: Delete index record
DELETE_INDEX = text(
    """
    DELETE FROM search.prompt_search_index
    WHERE prompt_id = :prompt_id
    """
)

#: Get job status
GET_JOB = text(
    """
    SELECT job_id, prompt_id, version_id, workspace_id, status, started_at, completed_at, error, result_json, created_by
    FROM search.prompt_search_index_job
    WHERE job_id = :job_id
    """
)

#: The metadata quick-search reports, one row per prompt.
#:
#: `released` wins over `latest` where a prompt has both: this feeds *"is this
#: indexed, and under what"* on a list screen, and the honest answer there is the
#: revision production is serving, not the draft somebody is still editing.
INDEX_METADATA = text(
    """
    SELECT DISTINCT ON (prompt_id)
           prompt_id, version_id, role, keywords, topics, entities, variations, language
    FROM search.prompt_search_index
    WHERE workspace_id = :workspace_id AND prompt_id = ANY(:prompt_ids)
    ORDER BY prompt_id, (role = 'released') DESC, indexed_at DESC
    """
)

QUICK_METADATA_MATCH = text(
    """
    SELECT prompt_id
    FROM search.prompt_search_index
    WHERE workspace_id = :workspace_id
      AND prompt_id = ANY(:prompt_ids)
      AND (lower(array_to_string(keywords, ' ')) LIKE :keyword
           OR lower(array_to_string(topics, ' ')) LIKE :keyword)
    """
)

#: One row per PROMPT, chosen from the two a prompt may hold.
#:
#: `DISTINCT ON` rather than a plain scan because a prompt whose draft and
#: released revision are both indexed has two vectors, and without this the same
#: prompt would occupy two of the three slots the import dialog shows — a
#: duplicate check whose duplicates are itself. The nearer of the two wins, which
#: is the right answer to *"does anything here resemble what I am about to
#: import"*: it is a hit if EITHER what is live or what is being drafted matches.
SEMANTIC_SEARCH = text(
    """
    SELECT ranked.*
    FROM (
        SELECT DISTINCT ON (psi.prompt_id)
               psi.prompt_id,
               -- The RAW cosine, with no keyword bonus folded into it. The
               -- bonus used to be `+0.05` added here, which made one number
               -- mean two things: the floor below and the percentage the
               -- interface shows were both reading a similarity that had a
               -- lexical signal baked in. `keyword_match` travels beside it
               -- instead, and `ranking.fuse` decides what it is worth.
               1 - (psi.content_embedding <=> CAST(:embedding AS public.vector)) AS similarity,
               psi.keywords, psi.topics, psi.entities, psi.variations, psi.language,
               psi.version_id, psi.role,
               lower(array_to_string(psi.keywords || psi.topics, ' ')) LIKE :keyword
                 AS keyword_match
        FROM search.prompt_search_index psi
        WHERE psi.workspace_id = :workspace_id
          AND psi.embedding_model = :embedding_model
          AND psi.prompt_id = ANY(:prompt_ids)
        ORDER BY psi.prompt_id, similarity DESC
    ) AS ranked
    ORDER BY ranked.similarity DESC, ranked.prompt_id
    LIMIT :limit OFFSET :offset
    """
)

#: Same one-row-per-prompt rule as `SEMANTIC_SEARCH`, for the duplicate warning
#: shown at index time. A prompt counted twice here would report a neighbour that
#: is the same prompt seen from its other revision.
NEIGHBORS_ALL = text(
    """
    SELECT nearest.*
    FROM (
        SELECT DISTINCT ON (psi.prompt_id) psi.id, psi.prompt_id,
               1 - (psi.content_embedding <=> CAST(:embedding AS public.vector)) AS similarity
        FROM search.prompt_search_index psi
        WHERE psi.workspace_id = :workspace_id
          AND psi.embedding_model = :embedding_model
          AND psi.prompt_id != :exclude_prompt_id
          AND 1 - (psi.content_embedding <=> CAST(:embedding AS public.vector)) > :threshold
        ORDER BY psi.prompt_id, similarity DESC
    ) AS nearest
    ORDER BY nearest.similarity DESC, nearest.prompt_id
    LIMIT 5
    """
)

NEIGHBORS_FILTERED = text(
    """
    SELECT nearest.*
    FROM (
        SELECT DISTINCT ON (psi.prompt_id) psi.id, psi.prompt_id,
               1 - (psi.content_embedding <=> CAST(:embedding AS public.vector)) AS similarity
        FROM search.prompt_search_index psi
        WHERE psi.workspace_id = :workspace_id
          AND psi.embedding_model = :embedding_model
          AND psi.prompt_id != :exclude_prompt_id
          AND 1 - (psi.content_embedding <=> CAST(:embedding AS public.vector)) > :threshold
          AND psi.prompt_id = ANY(:visible_ids)
        ORDER BY psi.prompt_id, similarity DESC
    ) AS nearest
    ORDER BY nearest.similarity DESC, nearest.prompt_id
    LIMIT 5
    """
)

SET_SEARCH_TIMEOUT = text("SELECT set_config('statement_timeout', '5s', true)")


def _map_index_row(row: Any) -> IndexRow:
    return IndexRow.from_db_row(row)


def _map_job_row(row: Any) -> IndexJobRow:
    return IndexJobRow.from_db_row(row)


async def _visible_prompts(
    db: AsyncSession,
    *,
    visible: VisibleFilter,
    actor_id: str,
    keyword: str | None = None,
) -> list[PromptRow]:
    """Read visible registry rows through prompt-registry's public repository seam."""
    rows: list[PromptRow] = []
    cursor: str | None = None
    while True:
        page = await registry_repository.list_prompts(
            db,
            actor_id=actor_id,
            visible=visible,
            keyword=keyword,
            cursor=cursor,
            limit=registry_repository.MAX_LIMIT,
        )
        rows.extend(page)
        if len(page) < registry_repository.MAX_LIMIT:
            return rows
        cursor = page[-1].id


async def _term_hits(
    db: AsyncSession,
    *,
    workspace_id: str,
    terms: tuple[str, ...],
    visible_ids: set[str],
    visible: VisibleFilter,
    actor_id: str,
) -> dict[str, set[str]]:
    """Which visible prompts each term matches, over the document AND the metadata.

    One indexed query per term against the registry's trigram document, plus one
    over the extracted keyword and topic arrays. The second is what makes the
    index-time extraction pay for itself on the keyword path: a prompt whose body
    never says "kubernetes" but whose extracted topics do is found.

    The returned sets are also the document frequencies — the input IDF needs —
    so weighting terms costs no query that retrieval did not already run.
    """
    hits: dict[str, set[str]] = {}
    for term in terms:
        matched = {
            prompt.id
            for prompt in await _visible_prompts(db, visible=visible, actor_id=actor_id, keyword=term)
            if prompt.id in visible_ids
        }
        if visible_ids:
            metadata = await db.execute(
                QUICK_METADATA_MATCH,
                {
                    "workspace_id": workspace_id,
                    "prompt_ids": list(visible_ids),
                    "keyword": f"%{term}%",
                },
            )
            matched.update(metadata.scalars())
        if matched:
            hits[term] = matched
    return hits


async def list_prompts_for_quick_search(
    db: AsyncSession,
    *,
    workspace_id: str,
    keyword: str,
    visible: VisibleFilter,
    actor_id: str,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[SearchResult]:
    """Keyword search across ALL prompts, **tokenised and ranked**.

    Two defects, and they were the default search mode:

    **A multi-word query matched nothing.** The whole string went into one
    ``LIKE '%…%'``, so "kubernetes cluster hardening and workload orchestration"
    required those 54 characters to appear verbatim in a document. Measured over
    the golden set, every multi-word query returned zero results — hit@1, recall
    and MRR were all exactly 0.000 (`eval/result/*-baseline.json`).

    **A single-word query was unranked.** "SQL" returned five prompts in
    ``prompt_id`` order, and the SQL assistant was not among the first three.
    There was no scoring step at all: matching was the whole algorithm.

    So: tokenise (`query_terms`), probe each term, and rank by the share of the
    query's IDF mass a prompt accounts for (`ranking.lexical_scores`). A prompt
    matching every distinctive word sorts above one matching the common half,
    which is the entire content of "relevance" on a keyword path.

    Falls back to the whole-string substring match when tokenisation yields
    nothing — a query of two characters, or of nothing but stop words, still
    behaves the way it did.
    """
    started = time.perf_counter()

    visible_prompts = await _visible_prompts(db, visible=visible, actor_id=actor_id)
    by_id = {prompt.id: prompt for prompt in visible_prompts}
    visible_ids = set(by_id)

    terms = query_terms(keyword)
    if terms:
        hits = await _term_hits(
            db,
            workspace_id=workspace_id,
            terms=terms,
            visible_ids=visible_ids,
            visible=visible,
            actor_id=actor_id,
        )
        # No anchor requirement here: see `ranking.lexical_scores`. This path is
        # a filter over words the person typed, not an assertion that two prompts
        # resemble each other.
        scores = ranking.lexical_scores(
            hits, corpus_size=len(visible_ids), require_anchor=False
        )
    else:
        fallback = await _visible_prompts(db, visible=visible, actor_id=actor_id, keyword=keyword)
        scores = {prompt.id: 1.0 for prompt in fallback if prompt.id in visible_ids}

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    offset = int(cursor or "0")
    page = [by_id[prompt_id] for prompt_id, _ in ordered[offset : offset + limit] if prompt_id in by_id]
    prompt_ids = [prompt.id for prompt in page]
    metadata: dict[str, Any] = {}
    if prompt_ids:
        result = await db.execute(
            INDEX_METADATA,
            {"workspace_id": workspace_id, "prompt_ids": prompt_ids},
        )
        metadata = {row["prompt_id"]: row for row in result.mappings().all()}

    duration = time.perf_counter() - started
    quick_duration_seconds.labels(result_count_bucket=result_count_bucket(len(page))).observe(duration)

    return [
        SearchResult(
            prompt_id=prompt.id,
            title=prompt.title,
            purpose=prompt.purpose,
            # No longer `None`. There is a ranking now, and a row that cannot say
            # how well it matched cannot be ordered by anything a reader can
            # check. It is a term-overlap share, not a cosine — `matched_fields`
            # is what keeps the two from being read as the same number.
            similarity=scores.get(prompt.id),
            keywords=tuple(metadata.get(prompt.id, {}).get("keywords") or ()),
            topics=tuple(metadata.get(prompt.id, {}).get("topics") or ()),
            is_indexed=prompt.id in metadata,
            version_id=metadata.get(prompt.id, {}).get("version_id"),
            entities=tuple(metadata.get(prompt.id, {}).get("entities") or ()),
            variations=ExtractedMetadata.from_dict(
                {"variations": metadata.get(prompt.id, {}).get("variations") or {}}
            ).variations,
            language=tuple(metadata.get(prompt.id, {}).get("language") or ()),
            matched_fields=("keyword",),
        )
        for prompt in page
    ]


#: Below this, a vector match is noise and is dropped.
#:
#: **Cosine distance always answers.** Every indexed row has some similarity to
#: every query, so without a floor a search for `zzqqx wibblefrotz` returns the
#: five least-unrelated prompts in the workspace at 0.11-0.17 — and the import
#: dialog presents whatever it is given as *near-matches worth versioning*. An
#: empty answer to a query nothing matches is information; five arbitrary prompts
#: is not.
#:
#: 0.25 is set where measured noise sits (an unrelated pair scores ~0.1-0.2 on
#: this corpus) rather than at a level that also cuts genuine weak matches — a
#: reworded duplicate measured 0.80 and a same-topic prompt 0.42, both far clear
#: of it. It is a floor on what is SHOWN, never on what is searched: everything
#: visible is still ranked.
#:
#: Now defined by `ranking.VECTOR_FLOOR` and re-exported here, because the name
#: is referenced by the module lock and by tests. What changed is not its value
#: but what it guards: the raw cosine, rather than a number the lexical leg had
#: already been blended into.
MIN_SEARCH_SIMILARITY = ranking.VECTOR_FLOOR


async def search_prompts_hybrid(
    db: AsyncSession,
    *,
    workspace_id: str,
    embedding: list[float],
    keyword: str,
    visible: VisibleFilter,
    actor_id: str,
    embedding_cache_hit: bool = False,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[SearchResult]:
    """Rank **every visible prompt**, using the vector index where one exists.

    Two legs over the same visible set, merged into one list:

    * **Vector.** pgvector cosine distance against `prompt_search_index`. Only
      indexed prompts have a row, and this leg is what makes a match *semantic* —
      a reworded prompt still ranks near its original.
    * **Lexical.** The distinctive terms of the query (`search_terms`) probed
      against `registry.prompt_property.search_text`, the trigram-indexed document
      the registry's trigger maintains. That document already contains the latest
      revision's **body** alongside the title, purpose, tags and model name, so
      this leg reaches prompts nothing has ever indexed.

    **The index is an accelerator, not a gate.** Until this, AI search answered
    only from `prompt_search_index`, which meant a prompt nobody had pressed the
    button for was invisible to the flow whose entire job is finding prompts you
    already have — and a workspace that had never indexed anything got *"nothing
    resembles this"* for every query, which reads as *no duplicates* and is the
    one wrong answer this path must not give.

    **The two legs are fused by rank, not by score** (`ranking.fuse`). They do
    not share a scale — one is a cosine between whole-prompt vectors, the other a
    share of the query's distinctive terms — and the previous blend papered over
    that with a constant: the lexical side was multiplied by a ceiling of 0.6 so
    it could never outrank a vector hit. On a corpus written in one genre every
    cosine lands between about 0.25 and 0.50, so *any* vector match preceded
    *every* lexical match, and the leg that catches error codes, proper nouns and
    exact identifiers was decorative.

    `matched_fields` still records which legs fired, and `similarity` is still
    the cosine wherever there is one, so a caller can say *found semantically*
    rather than implying it.
    """
    started = time.perf_counter()
    await db.execute(SET_SEARCH_TIMEOUT)
    from prope.prompt_search.agent.base import EMBEDDING_MODEL

    prompts = await _visible_prompts(db, visible=visible, actor_id=actor_id)
    prompts_by_id = {prompt.id: prompt for prompt in prompts}
    if not prompts_by_id:
        return []

    # --- vector leg -------------------------------------------------------
    # Unpaginated: both legs are merged and ranked in Python below, so a SQL
    # `LIMIT` here would cut candidates before the lexical leg had been counted.
    # Bounded by the visible set, which is the same bound `_visible_prompts`
    # already accepts at this module's stated scale.
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    result = await db.execute(
        SEMANTIC_SEARCH,
        {
            "workspace_id": workspace_id,
            "embedding_model": EMBEDDING_MODEL,
            "embedding": embedding_str,
            "keyword": f"%{keyword.lower()}%",
            "prompt_ids": list(prompts_by_id),
            "limit": len(prompts_by_id),
            "offset": 0,
        },
    )
    vector_rows = {row["prompt_id"]: row for row in result.mappings().all()}

    # --- lexical leg ------------------------------------------------------
    # One indexed query per term, through the registry's own seam so the
    # visibility filter is the same one every other read uses rather than a
    # second copy of it. `query_terms` is what turns a pasted body — or a typed
    # phrase — into something `LIKE '%term%'` can answer.
    terms = query_terms(keyword)
    hits = await _term_hits(
        db,
        workspace_id=workspace_id,
        terms=terms,
        visible_ids=set(prompts_by_id),
        visible=visible,
        actor_id=actor_id,
    )
    lexical = ranking.lexical_scores(hits, corpus_size=len(prompts_by_id))

    # --- fuse -------------------------------------------------------------
    vector = {prompt_id: float(row["similarity"]) for prompt_id, row in vector_rows.items()}
    keyword_matches = {
        prompt_id for prompt_id, row in vector_rows.items() if row["keyword_match"]
    }
    fused = ranking.fuse(vector=vector, lexical=lexical, keyword_matches=keyword_matches)

    ranked: list[SearchResult] = []
    for result in fused:
        prompt = prompts_by_id.get(result.prompt_id)
        if prompt is None:
            continue
        row = vector_rows.get(result.prompt_id)
        ranked.append(
            SearchResult(
                prompt_id=result.prompt_id,
                title=prompt.title,
                purpose=prompt.purpose,
                similarity=result.similarity,
                keywords=tuple(row["keywords"] or []) if row else (),
                topics=tuple(row["topics"] or []) if row else (),
                # Unindexed, and found anyway. `is_indexed=False` is what lets
                # the caller show this differently rather than claim a semantic
                # match it did not make.
                is_indexed=row is not None,
                version_id=row["version_id"] if row else None,
                entities=tuple(row["entities"] or ()) if row else (),
                variations=(
                    ExtractedMetadata.from_dict({"variations": row["variations"] or {}}).variations
                    if row
                    else ExtractedVariations()
                ),
                language=tuple(row["language"] or ()) if row else (),
                matched_fields=result.matched_fields,
            )
        )

    offset = int(cursor or "0")
    page = ranked[offset : offset + limit]

    duration = time.perf_counter() - started
    ai_duration_seconds.labels(
        result_count_bucket=result_count_bucket(len(page)),
        cache_hit=str(embedding_cache_hit).lower(),
    ).observe(duration)

    return page


async def find_nearest_neighbors(
    db: AsyncSession,
    *,
    workspace_id: str,
    embedding: list[float],
    exclude_prompt_id: str,
    visible: VisibleFilter | None = None,
    actor_id: str | None = None,
    threshold: float = DUPLICATE_SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Find nearest neighbors for duplicate detection."""
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    from prope.prompt_search.agent.base import EMBEDDING_MODEL

    visible_ids: list[str] = []
    if visible is not None:
        prompts = await _visible_prompts(db, visible=visible, actor_id=actor_id or "")
        visible_ids = [prompt.id for prompt in prompts]
        if not visible_ids:
            return []
    query = NEIGHBORS_FILTERED if visible is not None else NEIGHBORS_ALL
    result = await db.execute(
        query,
        {
            "workspace_id": workspace_id,
            "embedding_model": EMBEDDING_MODEL,
            "embedding": embedding_str,
            "exclude_prompt_id": exclude_prompt_id,
            "threshold": threshold,
            "actor_id": actor_id,
            "visible_ids": visible_ids,
        },
    )
    rows = result.mappings().all()
    return list(rows)


async def get_index_by_prompt(
    db: AsyncSession, prompt_id: str, *, role: str | None = None
) -> IndexRow | None:
    """One of a prompt's index rows: the named `role`, or the released one.

    Defaulting to `released` over `latest` keeps `GET /prompts/{id}/index`
    answering about the revision production is serving. A status screen that
    reported a draft's index as the prompt's would say *indexed* about text no
    consumer has been served — the same conflation the two-row model exists to
    end.
    """
    query = select(prompt_search_index).where(prompt_search_index.c.prompt_id == prompt_id)
    if role is not None:
        query = query.where(prompt_search_index.c.role == role)
    else:
        query = query.order_by((prompt_search_index.c.role == "released").desc())
    result = await db.execute(query)
    row = result.mappings().first()
    return _map_index_row(row) if row else None


#: The stored descriptors of several prompts, with the revision each belongs to.
#:
#: ``version_id`` travels with the descriptor and is not decoration: a descriptor
#: extracted from revision 4 says nothing about revision 7's output contract, and
#: attributing it to the body actually being compared would produce a confident
#: finding about text no model ever read. The caller matches on it and treats a
#: mismatch as *not established*.
LOAD_OUTPUT_DESCRIPTORS = text(
    """
    SELECT prompt_id, version_id, role, output_descriptor
    FROM   search.prompt_search_index
    WHERE  prompt_id = ANY(:prompt_ids)
      AND  output_descriptor IS NOT NULL
    """
)

#: Fill in a descriptor the indexer never wrote, for the revision it belongs to.
#:
#: **Two guards, and each one refuses a different wrong write.** ``version_id``
#: means the descriptor can only ever land on the row for the body it was
#: extracted from — the same rule :data:`LOAD_OUTPUT_DESCRIPTORS`'s caller
#: enforces from the other end, and the reason no ``role`` appears here: a row
#: carrying that version carries that body whichever role it holds, and pinning
#: `latest` would leave a `released`-only row unfillable while the read side
#: happily uses it. ``output_descriptor IS NULL`` means this never overwrites
#: what the worker wrote: the indexer sees the canonical body and this path
#: often sees unstructured text, so where the two disagree the indexer is the
#: better source and gets to keep its answer.
#:
#: It is a cache fill on a read path, which the embedding cache on this same
#: route already does. Losing the write costs one extraction next time and
#: nothing else, so it is not worth a transaction of its own failing a request
#: over. RLS scopes it: no ``workspace_id`` predicate, because a missing filter
#: must update zero rows rather than somebody else's (ADR-0035).
CACHE_OUTPUT_DESCRIPTOR = text(
    """
    UPDATE search.prompt_search_index
       SET output_descriptor = CAST(:descriptor AS jsonb)
     WHERE prompt_id = :prompt_id
       AND version_id = :version_id
       AND output_descriptor IS NULL
    """
)

#: How many of a set of prompts have any index row at all.
#:
#: **The recall ceiling, and nothing reported it before.** Indexing is async and
#: soft-failing by design, so a prompt never indexed cannot be retrieved and can
#: never be found as a duplicate however good the ranking gets. At a thousand
#: prompts the unindexed share *is* the ceiling, which makes this a prerequisite
#: measurement rather than a dashboard nicety.
COUNT_INDEXED_PROMPTS = text(
    """
    SELECT count(DISTINCT prompt_id) AS indexed
    FROM   search.prompt_search_index
    WHERE  prompt_id = ANY(:prompt_ids)
    """
)


async def cache_output_descriptors(
    db: AsyncSession, descriptors: dict[str, tuple[str, dict]]
) -> int:
    """Write back descriptors extracted on the read path. Returns rows filled.

    ``{prompt_id: (version_id, descriptor)}``, the same shape
    :func:`load_output_descriptors` returns, so the round trip is symmetrical.
    """
    filled = 0
    for prompt_id, (version_id, descriptor) in descriptors.items():
        result = await db.execute(
            CACHE_OUTPUT_DESCRIPTOR,
            {
                "prompt_id": prompt_id,
                "version_id": version_id,
                "descriptor": json.dumps(descriptor),
            },
        )
        filled += result.rowcount or 0
    return filled


async def load_output_descriptors(
    db: AsyncSession, prompt_ids: list[str]
) -> dict[str, tuple[str, dict]]:
    """``{prompt_id: (version_id, descriptor)}`` for the rows that have one.

    Prefers the ``latest`` row, because the comparison loads each candidate's
    latest revision body and the two must describe the same text.
    """
    if not prompt_ids:
        return {}
    rows = (
        await db.execute(LOAD_OUTPUT_DESCRIPTORS, {"prompt_ids": list(prompt_ids)})
    ).mappings().all()
    found: dict[str, tuple[str, dict]] = {}
    for row in rows:
        descriptor = row["output_descriptor"]
        if not isinstance(descriptor, dict):
            continue
        existing = found.get(row["prompt_id"])
        if existing is None or row["role"] == "latest":
            found[row["prompt_id"]] = (row["version_id"], descriptor)
    return found


async def count_indexed(db: AsyncSession, prompt_ids: list[str]) -> int:
    """How many of ``prompt_ids`` carry an index row of either role."""
    if not prompt_ids:
        return 0
    return int(await db.scalar(COUNT_INDEXED_PROMPTS, {"prompt_ids": list(prompt_ids)}) or 0)


async def create_index_record(
    db: AsyncSession,
    *,
    id: str,
    prompt_id: str,
    version_id: str,
    workspace_id: str,
    role: str,
    metadata: ExtractedMetadata,
    embedding: list[float],
    indexed_by: str,
    nearest_neighbor_id: str | None,
    nearest_neighbor_similarity: float | None,
    output_descriptor: dict | None = None,
) -> IndexRow:
    """Create a new index record.

    ``output_descriptor`` is the normalized declared output contract for this
    revision (migration 0035), or ``None`` when the extraction did not run or
    produced nothing. It is written on the same upsert as everything else so a
    row can never carry a descriptor from one revision beside the vector of
    another.
    """
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    from prope.prompt_search.agent.base import EMBEDDING_MODEL

    await db.execute(
        INSERT_INDEX,
        {
            "id": id,
            "prompt_id": prompt_id,
            "version_id": version_id,
            "workspace_id": workspace_id,
            "role": role,
            "keywords": list(metadata.keywords),
            "topics": list(metadata.topics),
            "entities": list(metadata.entities),
            "variations": json.dumps(metadata.variations.to_dict()),
            "language": list(metadata.language),
            "content_embedding": embedding_str,
            "embedding_model": EMBEDDING_MODEL,
            "is_bilingual": "en" in metadata.language and "vi" in metadata.language,
            "indexed_at": "NOW()",
            "indexed_by": indexed_by,
            "nearest_neighbor_id": nearest_neighbor_id,
            "nearest_neighbor_similarity": nearest_neighbor_similarity,
            "output_descriptor": (
                json.dumps(output_descriptor) if output_descriptor is not None else None
            ),
        },
    )
    created = await get_index_by_prompt(db, prompt_id, role=role)
    if created is None:
        raise RuntimeError("index upsert completed without a readable row")
    return created


async def delete_index_record(db: AsyncSession, prompt_id: str) -> bool:
    """Delete the index record for a prompt."""
    result = await db.execute(DELETE_INDEX, {"prompt_id": prompt_id})
    return result.rowcount > 0


async def create_job_record(
    db: AsyncSession,
    *,
    job_id: str,
    prompt_id: str,
    version_id: str,
    workspace_id: str,
    created_by: str,
) -> IndexJobRow:
    """Create a new job record."""
    await db.execute(
        INSERT_JOB,
        {
            "job_id": job_id,
            "prompt_id": prompt_id,
            "version_id": version_id,
            "workspace_id": workspace_id,
            "status": IndexJobStatus.PENDING.value,
            "created_by": created_by,
        },
    )
    created = await get_job_status(db, job_id)
    if created is None:
        raise RuntimeError("job insert completed without a readable row")
    return created


async def update_job_started(db: AsyncSession, job_id: str) -> IndexJobRow | None:
    """Mark job as started."""
    await db.execute(UPDATE_JOB_STARTED, {"job_id": job_id})
    return await get_job_status(db, job_id)


async def update_job_completed(db: AsyncSession, job_id: str, result_json: dict) -> IndexJobRow | None:
    """Mark job as completed."""
    import json

    await db.execute(
        UPDATE_JOB_COMPLETED,
        {"job_id": job_id, "result_json": json.dumps(result_json)},
    )
    return await get_job_status(db, job_id)


async def update_job_failed(db: AsyncSession, job_id: str, error: str) -> IndexJobRow | None:
    """Mark job as failed."""
    await db.execute(UPDATE_JOB_FAILED, {"job_id": job_id, "error": error})
    return await get_job_status(db, job_id)


async def get_job_status(db: AsyncSession, job_id: str) -> IndexJobRow | None:
    """Get job status."""
    result = await db.execute(GET_JOB, {"job_id": job_id})
    row = result.mappings().first()
    return _map_job_row(row) if row else None


async def delete_expired_completed_jobs(db: AsyncSession) -> int:
    """Delete completed job diagnostics after the lock's seven-day window."""
    result = await db.execute(
        text(
            """
            DELETE FROM search.prompt_search_index_job
            WHERE status = 'completed'
              AND completed_at < NOW() - INTERVAL '7 days'
            """
        )
    )
    return result.rowcount


async def get_or_create_embedding(
    db: AsyncSession,
    workspace_id: str,
    text: str,
    client,
) -> tuple[list[float], bool]:
    """Get embedding from cache or create new one.

    Returns (embedding, cache_hit).
    """
    import hashlib

    text_hash = hashlib.sha256(text.encode()).hexdigest()

    # Check cache
    from prope.prompt_search.agent.base import (
        EMBEDDING_MODEL,
        call_app_service,
        embedding_request,
    )

    result = await db.execute(
        CHECK_EMBEDDING_CACHE,
        {
            "workspace_id": workspace_id,
            "text_hash": text_hash,
            "embedding_model": EMBEDDING_MODEL,
        },
    )
    row = result.first()

    if row and row[0]:
        embedding_cache_hits_total.inc()
        # Parse vector from string format
        vec_str = str(row[0])
        embedding = _parse_vector_string(vec_str)
        return embedding, True

    embedding_cache_misses_total.inc()

    # Create new embedding
    response = await call_app_service(
        lambda: client.embeddings.create(**embedding_request(text))
    )
    embedding = response.data[0].embedding

    # Cache it
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    from ulid import ULID

    await db.execute(
        INSERT_EMBEDDING_CACHE,
        {
            "id": f"emb_{ULID()}",
            "workspace_id": workspace_id,
            "text_hash": text_hash,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_vector": embedding_str,
        },
    )

    return embedding, False


def _parse_vector_string(vec_str: str) -> list[float]:
    """Parse PostgreSQL vector string format to list of floats."""
    # Format: [0.123,0.456,0.789]
    content = vec_str.strip("[]")
    return [float(x) for x in content.split(",")]
