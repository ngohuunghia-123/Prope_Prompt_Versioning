"""Semantic prompt search.

Search uses the app embedding model directly. The App Agent is intentionally not
in this path: the module lock reserves LLM work for index-time extraction.
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
    """Embed one query and rank only indexed, actor-visible prompts."""
    client = await get_embedding_client()
    embedding, cache_hit = await repository.get_or_create_embedding(db, workspace_id, query, client)
    return await repository.search_indexed_prompts(
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
