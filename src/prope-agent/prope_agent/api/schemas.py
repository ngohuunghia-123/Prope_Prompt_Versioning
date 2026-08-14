"""Pydantic schemas for the public API."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OptimizeRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="System prompt to improve.")
    metadata: dict[str, Any] = Field(default_factory=dict)
    target_use_case: Optional[str] = None


class OptimizeResponse(BaseModel):
    workflow_id: str
    status: str
    stage: Optional[str] = None


class OptimizeResultResponse(BaseModel):
    workflow_id: str
    stage: str
    original_prompt: str
    final_prompt: str
    candidate_prompt: Optional[str] = None
    analysis: dict[str, Any] = Field(default_factory=dict)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    baseline_metrics: Optional[dict[str, Any]] = None
    candidate_metrics: Optional[dict[str, Any]] = None
    comparison: Optional[dict[str, Any]] = None
    quality_gate: Optional[str] = None
    explanation: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    errors: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowListItem(BaseModel):
    workflow_id: str
    stage: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
