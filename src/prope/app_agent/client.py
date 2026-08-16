"""Process-wide OpenAI clients built exclusively from app-owned settings.

**Two clients, because chat and embeddings are two products.** Prope's App Agent
speaks `/chat/completions` (prompt conversion, index-time extraction) and its
search speaks `/embeddings`, and an OpenAI-compatible gateway is under no
obligation to serve both — several serve chat for a dozen upstream models and no
embedding model at all. One client for both made that arrangement unreachable:
pointing the base URL at such a gateway turned every semantic search into a 404
from a route the provider never claimed to have.

So the embedding settings are their own three, each **falling back to the agent's**
when unset. A deployment using one provider for everything configures nothing new
and behaves exactly as before; a deployment splitting them sets three variables
and nothing else moves.
"""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI

APP_OPENAI_BASE_URL = os.environ.get("APP_OPENAI_BASE_URL", "https://api.openai.com/v1")
APP_OPENAI_API_KEY = os.environ.get("APP_OPENAI_API_KEY", "")
APP_AGENT_MODEL = os.environ.get("APP_AGENT_MODEL", "gpt-4o-mini")

#: Where `/embeddings` lives, defaulting to wherever the agent lives.
EMBEDDING_BASE_URL = os.environ.get("EMBEDDING_BASE_URL") or APP_OPENAI_BASE_URL
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY") or APP_OPENAI_API_KEY

#: The model every stored vector was produced by, and the reason
#: `APP_EMBEDDING_MODEL` is still read: it is written into
#: `search.prompt_search_index.embedding_model` and into the embedding cache key,
#: and `get_index_status` calls an index STALE when the row's model is not this
#: one. Dropping the old name outright would silently re-stale every index in
#: every existing deployment on the next deploy, so the new name wins and the old
#: one still answers.
EMBEDDING_MODEL = (
    os.environ.get("EMBEDDING_MODEL")
    or os.environ.get("APP_EMBEDDING_MODEL")
    or "text-embedding-3-small"
)

#: How many numbers the provider must return, because the column says so.
#:
#: `content_embedding` and `embedding_cache.embedding_vector` are both declared
#: `vector(1536)`, so a model answering with any other width does not store — it
#: raises, on the insert, after the call has been paid for. Plenty of good
#: embedding models are not 1536 wide (Qwen3-Embedding-8B is 4096), and the
#: OpenAI embeddings API has a parameter for exactly this: ask for the width you
#: need and let the provider do the reduction, which for a Matryoshka-trained
#: model is a shorter *embedding* rather than a truncated array.
#:
#: Sent on every request when set. A provider that rejects the parameter — the
#: legacy `text-embedding-ada-002` is the one that matters — is served by setting
#: `EMBEDDING_DIMENSIONS=` empty, which omits it. Empty is the only way to omit
#: it, deliberately: silence should mean *the column's width*, not *whatever the
#: model felt like*.
_dimensions = os.environ.get("EMBEDDING_DIMENSIONS", "1536").strip()
EMBEDDING_DIMENSIONS: int | None = int(_dimensions) if _dimensions else None

#: How long one embedding attempt may take, and why it is not the agent's 5s.
#:
#: The agent's 5s suits a chat completion from a provider tuned for latency. An
#: embedding from a large open-weights model on a shared host does not: measured
#: cold calls to an 8B embedding model ran ~10s, which under a 5s timeout meant
#: every one of them burned a full attempt before succeeding on the retry — and a
#: slow minute at the provider exhausted all four and surfaced as a 503 for a
#: request that would have succeeded given another two seconds.
#:
#: Generous rather than tight because of where this sits: the import screen's
#: duplicate check runs once per prompt, is cached by text hash afterwards, and
#: is advisory — waiting is cheap, a false *"nothing resembles this"* is not.
EMBEDDING_TIMEOUT_SECONDS = float(os.environ.get("EMBEDDING_TIMEOUT_SECONDS") or 30.0)


def embedding_request(text: str) -> dict[str, object]:
    """The keyword arguments for one `embeddings.create` call.

    One place, because the two call sites (search's query embedding and the
    indexer's purpose embedding) writing vectors of different widths into the
    same column is a failure that would only appear once both had run.
    """
    request: dict[str, object] = {"model": EMBEDDING_MODEL, "input": text}
    if EMBEDDING_DIMENSIONS is not None:
        request["dimensions"] = EMBEDDING_DIMENSIONS
    return request

_openai_client: "AsyncOpenAI | None" = None
_embedding_client: "AsyncOpenAI | None" = None


async def get_openai_client() -> "AsyncOpenAI":
    """The App Agent's client: `/chat/completions`, conversion and extraction."""
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI

        _openai_client = AsyncOpenAI(
            base_url=APP_OPENAI_BASE_URL,
            api_key=APP_OPENAI_API_KEY,
            max_retries=3,
            timeout=5.0,
        )
    return _openai_client


async def get_embedding_client() -> "AsyncOpenAI":
    """The search client: `/embeddings`, and nothing else calls it.

    Its own instance even when the settings match the agent's. Sharing one when
    they happen to be equal would make the split work in development and stop
    working the moment somebody set one variable — the kind of bug that only
    appears in the deployment nobody is watching.
    """
    global _embedding_client
    if _embedding_client is None:
        from openai import AsyncOpenAI

        _embedding_client = AsyncOpenAI(
            base_url=EMBEDDING_BASE_URL,
            api_key=EMBEDDING_API_KEY,
            max_retries=3,
            timeout=EMBEDDING_TIMEOUT_SECONDS,
        )
    return _embedding_client


def reset_openai_client() -> None:
    """Drop both cached clients. Tests re-read the environment through this."""
    global _openai_client, _embedding_client
    _openai_client = None
    _embedding_client = None
