"""Shared app-owned OpenAI configuration and client construction."""

from prope.app_agent.client import (
    APP_AGENT_MODEL,
    APP_OPENAI_API_KEY,
    APP_OPENAI_BASE_URL,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
    get_embedding_client,
    get_openai_client,
    reset_openai_client,
)

__all__ = [
    "APP_AGENT_MODEL",
    "APP_OPENAI_API_KEY",
    "APP_OPENAI_BASE_URL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_MODEL",
    "get_embedding_client",
    "get_openai_client",
    "reset_openai_client",
]
