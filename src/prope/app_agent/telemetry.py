"""The one Langfuse client, shared by every app-owned agent.

**Why this lives in `app_agent/` and not in a module.** `prope.app_agent` is
already the shared home of the app-owned LLM — the key, the base URL, the model
name, the circuit breaker. The trace backend those calls report to belongs at
the same level. The alternative on offer was `prompt_search` importing
`prompt_conversion.telemetry`, which would have invented a module edge that
`docs/modules/prompt-search.lock.yml` does not declare, to share thirty lines.

**Fail-open, deliberately.** No keys configured returns `None` and every call
site treats that as "no telemetry", never as an error. A prompt that could not
be indexed because an observability backend was unreachable would be the worst
possible trade of the two jobs involved.

**One client per process.** `lru_cache` rather than a module global so that a
test can `get_langfuse.cache_clear()`. The Langfuse SDK v4 owns an OpenTelemetry
tracer provider and a background export thread; constructing a second one per
request would leak both.
"""

import os
from functools import lru_cache

from langfuse import Langfuse

__all__ = ["flush_langfuse", "get_langfuse"]


@lru_cache(maxsize=1)
def get_langfuse() -> Langfuse | None:
    """The process's Langfuse client, or `None` when it is not configured."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        return None

    # Langfuse Python SDK v4 calls this `base_url`. `LANGFUSE_HOST` is the name
    # already in Prope's `.env` and compose files, so both are accepted and the
    # v4 spelling wins when somebody sets it.
    base_url = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")

    if base_url:
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url,
        )

    return Langfuse(public_key=public_key, secret_key=secret_key)


def flush_langfuse() -> None:
    """Push buffered spans now. For process shutdown and for short-lived scripts.

    The SDK exports on a background thread on its own schedule, which is right
    for `app` and `worker` and wrong for anything that exits promptly: a CLI that
    returns before the batch interval elapses takes its traces with it. Safe to
    call when Langfuse is unconfigured, and safe to call twice.
    """
    langfuse = get_langfuse()
    if langfuse is None:
        return

    try:
        langfuse.flush()
    except Exception:
        # Telemetry is fail-open here too. A shutdown path is the last place
        # that should raise on an unreachable collector.
        pass
