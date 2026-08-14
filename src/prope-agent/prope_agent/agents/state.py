"""LangGraph state for the prompt optimization workflow.

The state is a TypedDict so LangGraph can serialize / merge per-node
outputs. Every node reads from and writes back to this dict.

Stages (the `stage` field is the single source of truth for "where we are"):
    loaded -> analyzed -> optimized -> evaluated -> explained -> done

Failures land in `errors` and route the workflow to `failed` (terminal).
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class Finding(TypedDict, total=False):
    """A single observation from the Prompt Analyst agent."""
    category: str          # e.g. "ambiguity", "missing_constraint"
    severity: str          # "low" | "medium" | "high"
    description: str
    suggestion: str


class Change(TypedDict, total=False):
    """A single edit made by the Optimizer agent."""
    type: str              # "modify" | "add" | "remove"
    reason: str
    expected_effect: str


class EvalScores(TypedDict, total=False):
    """Aggregate eval scores. One per version."""
    quality: float
    format_compliance: float
    safety: float
    avg_latency_ms: float
    total_tokens: int
    estimated_cost_usd: float


class EvalComparison(TypedDict, total=False):
    """The deterministic comparison between baseline and candidate."""
    baseline: EvalScores
    candidate: EvalScores
    quality_delta: float
    token_delta_pct: float
    cost_delta_pct: float
    regressions: list[dict[str, Any]]
    gate: str  # "PASS" | "PASS_WITH_WARNING" | "FAIL"


class PromptWorkflowState(TypedDict, total=False):
    # ---- identity ----
    workflow_id: str
    workspace_id: str

    # ---- input ----
    original_prompt: str
    prompt_metadata: dict[str, Any]
    target_use_case: Optional[str]

    # ---- analysis (analyst node) ----
    analysis: dict[str, Any]           # strengths / issues / opportunities
    findings: list[Finding]

    # ---- proposal (optimizer node) ----
    candidate_prompt: Optional[str]
    changes: list[Change]

    # ---- evaluation ----
    eval_run_id: Optional[str]
    baseline_metrics: Optional[EvalScores]
    candidate_metrics: Optional[EvalScores]
    comparison: Optional[EvalComparison]
    quality_gate: Optional[str]        # PASS | PASS_WITH_WARNING | FAIL

    # ---- cost / token guard ----
    token_delta_percent: Optional[float]
    cost_delta_percent: Optional[float]

    # ---- final output ----
    final_prompt: Optional[str]
    explanation: Optional[str]

    # ---- bookkeeping ----
    iteration: int
    stage: str
    errors: list[dict[str, Any]]
    started_at: Optional[str]
    finished_at: Optional[str]
