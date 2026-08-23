"""The app-owned LLM layer for prompt-search.

Two things happen here and they are not the same kind of thing. **Extraction** is
an agent call: a DSPy program (`dspy_program`) running an instruction a human
labelled `production` in Langfuse (`prompting`), traced, priced and graded
(`evaluation`) on every run. **Search** is not: `search.semantic_search` embeds a
query and hands it to pgvector, and the lock file's `non_goals` reserve LLM work
for index time — "Agent-assisted search queries" is explicitly out of scope.

The previous version of this docstring claimed the package "provides
LangGraph-based agents" and "uses Langfuse for observability and tracing".
Neither was true: nothing here imported either library. It is worth naming
because a docstring that describes an intention rather than the code is the one
piece of documentation that actively costs something — it is why nobody noticed
the extraction path had no traces at all.
"""

from prope.prompt_search.agent.base import (
    APP_AGENT_MODEL,
    APP_OPENAI_API_KEY,
    APP_OPENAI_BASE_URL,
    EMBEDDING_MODEL,
    get_embedding_client,
    get_openai_client,
)
from prope.prompt_search.agent.comparison import (
    ComparisonContext,
    adjudicate,
    extract_output_descriptor,
    warm_comparison_agent,
)
from prope.prompt_search.agent.comparison_prompting import (
    ADJUDICATION_PROMPT_NAME,
    OUTPUT_CONTRACT_PROMPT_NAME,
    load_adjudication_prompt,
    load_output_contract_prompt,
)
from prope.prompt_search.agent.extraction import (
    ExtractionContext,
    ExtractionFailedError,
    extract_metadata,
    preview_extraction,
    warm_extraction_agent,
)
from prope.prompt_search.agent.prompting import (
    EXTRACTION_PROMPT_NAME,
    FALLBACK_EXTRACTION_PROMPT,
    load_extraction_prompt,
)
from prope.prompt_search.agent.search import (
    semantic_search,
)

__all__ = [
    # Configuration
    "APP_OPENAI_BASE_URL",
    "APP_OPENAI_API_KEY",
    "EMBEDDING_MODEL",
    "APP_AGENT_MODEL",
    "get_embedding_client",
    "get_openai_client",
    # Extraction agent
    "ExtractionContext",
    "ExtractionFailedError",
    "extract_metadata",
    "preview_extraction",
    "warm_extraction_agent",
    # The comparison funnel's two calls
    "ComparisonContext",
    "adjudicate",
    "extract_output_descriptor",
    "warm_comparison_agent",
    "ADJUDICATION_PROMPT_NAME",
    "OUTPUT_CONTRACT_PROMPT_NAME",
    "load_adjudication_prompt",
    "load_output_contract_prompt",
    # Managed instruction
    "EXTRACTION_PROMPT_NAME",
    "FALLBACK_EXTRACTION_PROMPT",
    "load_extraction_prompt",
    # Search (no agent involved — see the module docstring)
    "semantic_search",
]
