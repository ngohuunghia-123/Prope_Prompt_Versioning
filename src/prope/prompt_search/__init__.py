"""prompt-search: semantic and keyword search over prompt-registry prompts.

Scope (from docs/modules/prompt-search.lock.yml):
  - Quick search: keyword match on title, purpose, tags, body across ALL prompts
  - AI search: semantic similarity over indexed prompts only (pgvector)
  - On-demand indexing: author clicks "Index this prompt" after approval
  - Agent-extracted metadata: keywords, topics, entities, multilingual variations, language
  - App Agent for extraction: separate from user's BYOK provider
  - Duplicate detection at index time (>90% similarity -> warning)

Tables owned:
  - prompt_search_index (psi_ prefix): purpose_embedding VECTOR(1536), keywords/topics TEXT[],
    variations JSONB, nearest_neighbor fields
  - prompt_search_index_job (psj_ prefix): job lifecycle tracking

External services:
  - OpenAI API: App Agent (gpt-4o-mini) + text-embedding-3-small

Dependencies:
  - prompt-registry (read approved revisions)
  - access-control (permission filtering)
  - pgvector (infrastructure)
"""

from prope.prompt_search.api import router
from prope.prompt_search.models import (
    prompt_search_index,
    prompt_search_index_job,
)
from prope.prompt_search.seams import (
    PromptSearchExtractionResult,
    publish_indexing_job,
)

__all__ = [
    "router",
    "prompt_search_index",
    "prompt_search_index_job",
    "publish_indexing_job",
    "PromptSearchExtractionResult",
]
