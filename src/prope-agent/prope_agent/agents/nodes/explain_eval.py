"""explain_eval node.

Produces a short human-readable report describing the change, the expected
impact, and things to double-check. Uses the LLM for prose; deterministic
numbers come from the eval node.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ...core.logging import get_logger
from ...providers.base import LLMMessage, LLMProvider
from ..prompts import EXPLAIN_SYSTEM_PROMPT, EXPLAIN_USER_TEMPLATE
from ..state import PromptWorkflowState

logger = get_logger(__name__)


async def explain_eval(
    state: PromptWorkflowState, *, provider: LLMProvider
) -> PromptWorkflowState:
    original = state["original_prompt"]
    optimized = state.get("candidate_prompt") or ""
    findings = state.get("findings") or []
    changes = state.get("changes") or []
    comparison = state.get("comparison") or {}

    user = EXPLAIN_USER_TEMPLATE.format(
        original=original,
        optimized=optimized,
        findings=json.dumps(findings, indent=2),
        changes=json.dumps(changes, indent=2),
        comparison=json.dumps(comparison, indent=2),
    )
    res = await provider.generate(
        [
            LLMMessage(role="system", content=EXPLAIN_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user),
        ],
    )
    state["explanation"] = res.text.strip()
    state["final_prompt"] = optimized or state["original_prompt"]
    state["stage"] = "explained"
    state["finished_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("explain_eval: explanation length=%d", len(state["explanation"] or ""))
    return state
