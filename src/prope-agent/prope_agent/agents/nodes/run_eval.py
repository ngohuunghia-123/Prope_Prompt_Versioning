"""run_eval node.

Runs the candidate prompt against the same dataset used for baseline and
produces a deterministic comparison.

Per the backend plan: both versions use same input / same dataset / same
evaluator / same relevant model settings — fair comparison enforced.
"""
from __future__ import annotations

import uuid

from ...core.config import get_settings
from ...core.logging import get_logger
from ...eval import (
    HeuristicEvaluator,
    compare,
    make_provider_generate_fn,
    run_eval,
    synthetic_cases,
)
from ...providers.base import LLMProvider
from ..state import PromptWorkflowState

logger = get_logger(__name__)


async def run_eval_node(
    state: PromptWorkflowState, *, provider: LLMProvider
) -> PromptWorkflowState:
    settings = get_settings()
    cases = synthetic_cases(settings.synthetic_eval_cases)
    gen = make_provider_generate_fn(
        provider,
        model=settings.openai_model,
        temperature=settings.temperature,
        max_tokens=min(settings.max_tokens, 512),
    )

    baseline = await run_eval(
        label="baseline",
        prompt_body=state["original_prompt"],
        cases=cases,
        generate=gen,
        evaluator=HeuristicEvaluator(),
    )
    candidate = await run_eval(
        label="candidate",
        prompt_body=state.get("candidate_prompt") or "",
        cases=cases,
        generate=gen,
        evaluator=HeuristicEvaluator(),
    )

    comparison = compare(baseline, candidate)
    state["eval_run_id"] = str(uuid.uuid4())
    state["baseline_metrics"] = baseline.aggregate  # type: ignore[assignment]
    state["candidate_metrics"] = candidate.aggregate  # type: ignore[assignment]
    state["comparison"] = comparison  # type: ignore[assignment]
    state["quality_gate"] = comparison.get("gate", "FAIL")
    state["token_delta_percent"] = comparison.get("token_delta_pct")
    state["cost_delta_percent"] = comparison.get("cost_delta_pct")
    state["stage"] = "evaluated"
    logger.info(
        "run_eval: gate=%s quality_delta=%.3f tokens=%.1f%% cost=%.1f%%",
        state["quality_gate"],
        comparison.get("quality_delta", 0.0),
        state["token_delta_percent"] or 0.0,
        state["cost_delta_percent"] or 0.0,
    )
    return state
