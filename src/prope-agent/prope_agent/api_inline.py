"""High-level convenience API.

For the common case:
    from prope_agent import optimize_text
    new_prompt = optimize_text("You are a helpful assistant.")

For full structured access:
    from prope_agent import optimize
    result = optimize("You are a helpful assistant.")
    print(result["final_prompt"])
    print(result["comparison"])
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from .agents import run_workflow
from .core.config import Settings
from .providers import build_provider


def _run_sync(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def optimize(
    prompt: str,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Run the optimization workflow and return the full state dict."""
    settings = Settings()
    if provider:
        from .core.config import ProviderKind
        settings.provider = ProviderKind(provider)
    if model:
        settings.openai_model = model
    if api_key:
        settings.openai_api_key = api_key
    p = build_provider(settings)
    initial = {
        "workflow_id": "inline",
        "workspace_id": "inline",
        "original_prompt": prompt,
        "prompt_metadata": metadata or {},
    }
    return _run_sync(run_workflow(initial_state=initial, provider=p))


def optimize_text(
    prompt: str,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Run the workflow and return just the improved prompt as a string.

    Matches the user's stated contract:
        input  = system prompt (str)
        output = improved system prompt (str)
    """
    state = optimize(
        prompt,
        provider=provider,
        model=model,
        api_key=api_key,
        metadata=metadata,
    )
    return (
        state.get("final_prompt")
        or state.get("candidate_prompt")
        or prompt
    )
