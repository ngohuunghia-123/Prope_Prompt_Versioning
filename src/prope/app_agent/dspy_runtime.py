"""The app-owned LM as DSPy sees it, plus the token accounting around it.

Two agents now run on DSPy — `prompt_conversion` and `prompt_search`'s metadata
extraction — and every line in this file is a thing that must be identical in
both or the difference is a bug rather than a choice:

* **`cache=False` is a SECURITY setting.** DSPy's default on-disk cache writes
  every rendered prompt into `~/.dspy_cache` on the host. Both agents are fed
  untrusted corporate prompt bodies (A-020, A-046), and a cache directory is a
  copy of them that nothing in Prope governs, expires, or encrypts. Having this
  written once means it cannot be true in one module and forgotten in the other.
* **Prices are per deployed MODEL, not per feature.** Both agents call
  `APP_AGENT_MODEL` with `APP_OPENAI_API_KEY`. Two copies of the price constants
  would let a model swap update one module's cost metric and not the other's,
  and the resulting graph is worse than no graph — it is a wrong number that
  looks maintained.
* **Usage summing across model names.** A provider that echoes a resolved id
  (`gpt-4o-mini-2024-07-18`) rather than the requested one must not silently
  report zero tokens and a zero bill.

`max_tokens` is the one setting that is genuinely per-agent — a conversion
returns the whole prompt restructured, an extraction returns a few dozen short
strings — so it is a required argument rather than a shared constant.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import dspy

from prope.app_agent.client import (
    APP_AGENT_MODEL,
    APP_OPENAI_API_KEY,
    APP_OPENAI_BASE_URL,
)

__all__ = [
    "PRICE_INPUT_PER_MTOK",
    "PRICE_OUTPUT_PER_MTOK",
    "build_lm",
    "cost_usd",
    "usage_of",
    "usage_tracking",
]

#: Prices per MILLION tokens, so that cost is computed at the call site from the
#: provider's own usage numbers rather than reconstructed from a bill a month
#: later. Defaults are `gpt-4o-mini`'s. An operator who changes `APP_AGENT_MODEL`
#: and not these gets a wrong number, which is why both agents record the model
#: name as span metadata beside the cost.
#:
#: Output is 4-6x input at every provider in the 2026 price table, so the two are
#: separate settings and the metrics that report them are labelled by direction.
PRICE_INPUT_PER_MTOK = float(os.getenv("APP_AGENT_PRICE_INPUT_PER_MTOK", "0.15"))
PRICE_OUTPUT_PER_MTOK = float(os.getenv("APP_AGENT_PRICE_OUTPUT_PER_MTOK", "0.60"))


def build_lm(
    *,
    max_tokens: int,
    temperature: float = 0.0,
    model: str | None = None,
    num_retries: int = 3,
    timeout: float | None = None,
) -> dspy.LM:
    """The app-owned LM, built from `APP_OPENAI_*` exactly as the rest of the app is.

    `temperature=0.0` by default because both current callers are performing a
    classification with a right answer, and because a non-deterministic call
    makes a retry unattributable — a second attempt that happens to succeed says
    nothing about whether the first failure was the prompt's fault or the
    sampler's.

    `model`, `num_retries` and `timeout` are per-program overrides for callers
    whose latency profile differs from the default. The chat router runs on
    every turn ahead of everything else, so it points at whatever fast model
    the gateway offers (`CHAT_ROUTER_MODEL`) and fails visibly in seconds
    rather than invisibly after three silent retries against a slow proxy.
    """
    return dspy.LM(
        model=f"openai/{model or APP_AGENT_MODEL}",
        api_key=APP_OPENAI_API_KEY,
        api_base=APP_OPENAI_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        cache=False,
        num_retries=num_retries,
        **({"timeout": timeout} if timeout is not None else {}),
    )


@contextmanager
def usage_tracking() -> Iterator[None]:
    """Turn on DSPy's token accounting for the duration of one call.

    Per-call rather than through the process-wide `dspy.configure`, which is
    main-thread-only and would raise under whichever event-loop task FastAPI
    hands a request to. `dspy.context` writes a ContextVar, so it is correct both
    across an `await` inside one task and across concurrent requests.
    """
    with dspy.context(track_usage=True):
        yield


def usage_of(prediction: Any) -> dict[str, int]:
    """Input/output token counts from a prediction, or `{}` when untracked."""
    get = getattr(prediction, "get_lm_usage", None)
    if get is None:
        return {}

    try:
        per_model = get() or {}
    except Exception:  # pragma: no cover - defensive; usage is never load-bearing
        return {}

    totals = {"input": 0, "output": 0}
    for entry in per_model.values():
        totals["input"] += int(entry.get("prompt_tokens") or 0)
        totals["output"] += int(entry.get("completion_tokens") or 0)

    return totals if totals["input"] or totals["output"] else {}


def cost_usd(usage: dict[str, int]) -> float:
    """Cost for one call, from the provider's own token counts."""
    return (
        usage.get("input", 0) / 1_000_000 * PRICE_INPUT_PER_MTOK
        + usage.get("output", 0) / 1_000_000 * PRICE_OUTPUT_PER_MTOK
    )
