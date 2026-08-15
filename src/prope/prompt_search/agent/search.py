"""Semantic prompt search over every visible prompt.

Search uses the app embedding model directly. The App Agent is intentionally not
in this path: the module lock reserves LLM work for index-time extraction.

The vector index does not bound what is searchable. `search_prompts_hybrid` ranks
indexed prompts by cosine distance and reaches the rest through the registry's
trigram-indexed document, which already contains their bodies — so an unindexed
prompt is found, just less precisely, and indexing is what makes it fast and
semantic rather than what makes it visible.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from prope.access_control.domain import VisibleFilter
from prope.prompt_search import repository
from prope.prompt_search.agent.base import get_embedding_client
from prope.prompt_search.domain import SearchResult


async def semantic_search(
    *,
    db: AsyncSession,
    query: str,
    workspace_id: str,
    visible: VisibleFilter,
    actor_id: str,
    cursor: str | None = None,
    limit: int = 50,
) -> list[SearchResult]:
    """Embed one query and rank every actor-visible prompt against it."""
    client = await get_embedding_client()
    embedding, cache_hit = await repository.get_or_create_embedding(db, workspace_id, query, client)
    return await repository.search_prompts_hybrid(
        db,
        workspace_id=workspace_id,
        embedding=embedding,
        keyword=query,
        visible=visible,
        actor_id=actor_id,
        embedding_cache_hit=cache_hit,
        cursor=cursor,
        limit=limit,
    )


__all__ = ["semantic_search"]
