"""load_context node.

Reads the original prompt, stamps workflow metadata, and seeds the state
with the baseline run metrics so later nodes can compare.

In the full backend plan this would also load: historical versions, recent
eval runs, prompt configuration, provider/model config. We keep the
focused implementation here.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from ...core.config import get_settings
from ...core.logging import get_logger
from ...eval import (
    HeuristicEvaluator,
    make_provider_generate_fn,
    run_eval,
    synthetic_cases,
)
from ...providers.base import LLMProvider
from ..state import PromptWorkflowState

logger = get_logger(__name__)


async def load_context(
    state: PromptWorkflowState, *, provider: LLMProvider
) -> PromptWorkflowState:
    """Node: seed baseline metrics and bookkeeping."""
    settings = get_settings()
    started = datetime.now(timezone.utc).isoformat()
    state.setdefault("workflow_id", str(uuid.uuid4()))
    state["started_at"] = started
    state["iteration"] = state.get("iteration", 0) + 1
    state["stage"] = "loaded"
    state.setdefault("errors", [])
    state.setdefault("prompt_metadata", {})
    state.setdefault("findings", [])
    state.setdefault("changes", [])
    state.setdefault("workspace_id", "default")

    # Run baseline eval against the ORIGINAL prompt — this is the
    # reference the optimizer will be measured against later.
    cases = synthetic_cases(settings.synthetic_eval_cases)
    gen = make_provider_generate_fn(
        provider,
        model=settings.openai_model,
        temperature=settings.temperature,
        max_tokens=min(settings.max_tokens, 512),
    )
    t0 = time.perf_counter()
    baseline = await run_eval(
        label="baseline",
        prompt_body=state["original_prompt"],
        cases=cases,
        generate=gen,
        evaluator=HeuristicEvaluator(),
    )
    baseline_ms = int((time.perf_counter() - t0) * 1000)
    state["baseline_metrics"] = baseline.aggregate  # type: ignore[assignment]
    logger.info(
        "load_context: baseline done in %d ms, %d cases",
        baseline_ms,
        len(cases),
    )
    return state
