"""Process-wide OpenAI client built exclusively from app-owned settings."""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI

APP_OPENAI_BASE_URL = os.environ.get("APP_OPENAI_BASE_URL", "https://api.openai.com/v1")
APP_OPENAI_API_KEY = os.environ.get("APP_OPENAI_API_KEY", "")
APP_AGENT_MODEL = os.environ.get("APP_AGENT_MODEL", "gpt-4o-mini")
APP_EMBEDDING_MODEL = os.environ.get("APP_EMBEDDING_MODEL", "text-embedding-3-small")

_openai_client: "AsyncOpenAI | None" = None


async def get_openai_client() -> "AsyncOpenAI":
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


def reset_openai_client() -> None:
    global _openai_client
    _openai_client = None
