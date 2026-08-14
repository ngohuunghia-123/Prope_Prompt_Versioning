"""optimize_prompt node.

Prompt Optimizer agent — produces a proposed improved prompt and a list of
discrete changes.

The agent NEVER writes into production. It only emits a proposal that the
deterministic quality gate then evaluates.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ...core.logging import get_logger
from ...providers.base import LLMMessage, LLMProvider
from ..prompts import OPTIMIZER_SYSTEM_PROMPT, OPTIMIZER_USER_TEMPLATE
from ..state import Change, PromptWorkflowState

logger = get_logger(__name__)


def _safe_json(text: str) -> dict[str, Any]:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.DOTALL).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"proposed_prompt": "", "changes": [], "risks": []}


async def optimize_prompt(
    state: PromptWorkflowState, *, provider: LLMProvider
) -> PromptWorkflowState:
    user = OPTIMIZER_USER_TEMPLATE.format(
        prompt=state["original_prompt"],
        analysis=json.dumps(state.get("analysis", {}), indent=2),
    )
    res = await provider.generate(
        [
            LLMMessage(role="system", content=OPTIMIZER_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user),
        ],
        json_mode=True,
    )
    parsed = _safe_json(res.text)
    proposed = parsed.get("proposed_prompt") or ""
    changes_raw = parsed.get("changes") or []
    changes: list[Change] = []
    for c in changes_raw:
        if not isinstance(c, dict):
            continue
        changes.append(
            Change(
                type=str(c.get("type", "modify")),
                reason=str(c.get("reason", "")),
                expected_effect=str(c.get("expected_effect", "")),
            )
        )
    state["candidate_prompt"] = proposed
    state["changes"] = changes
    state["stage"] = "optimized"
    logger.info(
        "optimize_prompt: %d chars proposed, %d changes",
        len(proposed),
        len(changes),
    )
    return state
