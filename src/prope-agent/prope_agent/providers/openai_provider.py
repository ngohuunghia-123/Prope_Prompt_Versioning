"""OpenAI provider."""
from __future__ import annotations

import time
from typing import Any

from openai import AsyncOpenAI

from ..core.exceptions import ProviderError
from .base import LLMMessage, LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
    ) -> None:
        if not api_key:
            raise ProviderError("OpenAI api_key is required")
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._default_model = default_model

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        m = model or self._default_model
        payload: list[dict[str, str]] = [
            {"role": x.role, "content": x.content} for x in messages
        ]
        kwargs_dict: dict[str, Any] = {
            "model": m,
            "messages": payload,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs_dict["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        try:
            res = await self._client.chat.completions.create(**kwargs_dict)
        except Exception as exc:  # openai raises OpenAIError; we surface generically
            raise ProviderError(f"OpenAI call failed: {exc}") from exc
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        text = (res.choices[0].message.content or "").strip()
        usage = res.usage
        return LLMResponse(
            text=text,
            input_tokens=(usage.prompt_tokens if usage else 0),
            output_tokens=(usage.completion_tokens if usage else 0),
            latency_ms=elapsed_ms,
            provider=self.name,
            model=m,
            raw={"id": getattr(res, "id", None)},
        )
