"""regression_gate + cost_guard combined.

In the full backend plan these are two separate nodes. Here they collapse
into one because the eval node already returns the regression list and
cost delta. We re-validate against config thresholds so the config stays
authoritative.
"""
from __future__ import annotations

from ...core.config import get_settings
from ...core.logging import get_logger
from ..state import PromptWorkflowState

logger = get_logger(__name__)


async def regression_gate(
    state: PromptWorkflowState, *, provider=None  # noqa: ARG001
) -> PromptWorkflowState:
    settings = get_settings()
    comp = state.get("comparison") or {}
    token_pct = state.get("token_delta_percent") or 0.0
    cost_pct = state.get("cost_delta_percent") or 0.0

    warnings: list[str] = []
    if abs(token_pct) >= settings.token_warning_threshold:
        warnings.append(
            f"token delta {token_pct:+.1f}% exceeds threshold "
            f"{settings.token_warning_threshold:.1f}%"
        )
    if abs(cost_pct) >= settings.cost_warning_threshold:
        warnings.append(
            f"cost delta {cost_pct:+.1f}% exceeds threshold "
            f"{settings.cost_warning_threshold:.1f}%"
        )

    gate = state.get("quality_gate") or "FAIL"
    if gate == "PASS" and warnings:
        gate = "PASS_WITH_WARNING"
    state["quality_gate"] = gate
    state.setdefault("analysis", {})["runtime_warnings"] = warnings
    state["stage"] = "gate_checked"
    logger.info("regression_gate: %s, %d warnings", gate, len(warnings))
    return state
