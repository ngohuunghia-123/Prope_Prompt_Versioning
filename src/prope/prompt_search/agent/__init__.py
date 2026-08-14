"""Agent package for prompt-search LLM integration.

Provides LangGraph-based agents for:
- Metadata extraction from prompt bodies
- Semantic search orchestration
- Full pipeline AI search

Uses Langfuse for observability and tracing.
"""

from prope.prompt_search.agent.base import (
    APP_AGENT_MODEL,
    APP_EMBEDDING_MODEL,
    APP_OPENAI_API_KEY,
    APP_OPENAI_BASE_URL,
    get_openai_client,
)
from prope.prompt_search.agent.extraction import (
    extract_metadata,
    preview_extraction,
)
from prope.prompt_search.agent.search import (
    semantic_search,
)

__all__ = [
    # Configuration
    "APP_OPENAI_BASE_URL",
    "APP_OPENAI_API_KEY",
    "APP_EMBEDDING_MODEL",
    "APP_AGENT_MODEL",
    "get_openai_client",
    # Extraction agent
    "extract_metadata",
    "preview_extraction",
    # Search agent
    "semantic_search",
]
