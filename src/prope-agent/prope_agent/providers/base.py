"""LLM provider abstraction.

The contract:
    generate(messages, model, temperature, **kwargs) -> LLMResponse

This is used by the eval engine, agent nodes, and the optional runtime
playground path. Normalized so the rest of the system does not care which
vendor is configured.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    provider: str = "unknown"
    model: str = "unknown"
    raw: dict[str, Any] = Field(default_factory=dict)


class LLMMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMProvider(ABC):
    """Protocol — every provider must implement `generate`."""

    name: str = "abstract"

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
        **kwargs: Any,
    ) -> LLMResponse: ...
