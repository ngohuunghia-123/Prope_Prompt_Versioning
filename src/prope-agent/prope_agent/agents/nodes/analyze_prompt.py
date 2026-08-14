"""analyze_prompt node.

Prompt Analyst agent — produces structured findings about the input.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ...core.logging import get_logger
from ...providers.base import LLMMessage, LLMProvider
from ..prompts import ANALYST_SYSTEM_PROMPT, ANALYST_USER_TEMPLATE
from ..state import Finding, PromptWorkflowState

logger = get_logger(__name__)


def _safe_json(text: str) -> dict[str, Any]:
    """Parse JSON from a model response, tolerating ```json fences."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.DOTALL).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Fallback: pull the first {...} block.
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {
            "strengths": [],
            "issues": ["Could not parse analyst JSON output."],
            "optimization_opportunities": [],
            "risk_level": "low",
            "findings": [],
            "recommended_changes": [],
        }


async def analyze_prompt(
    state: PromptWorkflowState, *, provider: LLMProvider
) -> PromptWorkflowState:
    user = ANALYST_USER_TEMPLATE.format(
        prompt=state["original_prompt"],
        metadata=json.dumps(state.get("prompt_metadata", {}), indent=2),
    )
    res = await provider.generate(
        [
            LLMMessage(role="system", content=ANALYST_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user),
        ],
        json_mode=True,
    )
    parsed = _safe_json(res.text)
    findings_raw = parsed.get("findings") or []
    findings: list[Finding] = []
    for f in findings_raw:
        if not isinstance(f, dict):
            continue
        findings.append(
            Finding(
                category=str(f.get("category", "other")),
                severity=str(f.get("severity", "low")),
                description=str(f.get("description", "")),
                suggestion=str(f.get("suggestion", "")),
            )
        )
    state["analysis"] = {
        "strengths": parsed.get("strengths", []),
        "issues": parsed.get("issues", []),
        "optimization_opportunities": parsed.get(
            "optimization_opportunities", []
        ),
        "risk_level": parsed.get("risk_level", "low"),
        "recommended_changes": parsed.get("recommended_changes", []),
    }
    state["findings"] = findings
    state["stage"] = "analyzed"
    logger.info(
        "analyze_prompt: %d findings, risk=%s",
        len(findings),
        state["analysis"].get("risk_level"),
    )
    return state
