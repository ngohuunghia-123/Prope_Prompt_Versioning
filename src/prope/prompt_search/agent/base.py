"""App-owned OpenAI calls for prompt search, with its own circuit breaker."""

from collections.abc import Awaitable, Callable

from prope.app_agent import (
    APP_AGENT_MODEL,
    APP_OPENAI_API_KEY,
    APP_OPENAI_BASE_URL,
    EMBEDDING_MODEL,
    get_embedding_client,
    get_openai_client,
    reset_openai_client,
)
from prope.app_agent.circuit import CircuitBreaker


def _set_circuit_metric(is_open: bool) -> None:
    from prope.prompt_search.observability import agent_circuit_open

    agent_circuit_open.set(1 if is_open else 0)


_breaker = CircuitBreaker(on_state_change=_set_circuit_metric)


async def call_app_service[T](operation: Callable[[], Awaitable[T]]) -> T:
    """Run an app-owned upstream call behind a sliding-window circuit breaker."""
    return await _breaker.call(operation)


__all__ = [
    "APP_AGENT_MODEL",
    "APP_OPENAI_API_KEY",
    "APP_OPENAI_BASE_URL",
    "EMBEDDING_MODEL",
    "get_embedding_client",
    "get_openai_client",
    "call_app_service",
    "reset_openai_client",
]
