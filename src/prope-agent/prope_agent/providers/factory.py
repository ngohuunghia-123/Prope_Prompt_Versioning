"""Provider factory."""
from __future__ import annotations

from ..core.config import ProviderKind, Settings
from .base import LLMProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProvider


def build_provider(settings: Settings) -> LLMProvider:
    if settings.provider == ProviderKind.OPENAI:
        if not settings.openai_api_key:
            raise ValueError(
                "PROPE_AGENT_OPENAI_API_KEY is required when provider=openai"
            )
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            default_model=settings.openai_model,
        )
    return MockProvider()
