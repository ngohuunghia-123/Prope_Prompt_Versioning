from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from prope.evaluation.domain import (
    MAX_CASES_PER_SUITE,
    AssertionType,
    CaseOutcome,
    OutputModality,
    RefusalReason,
    RunRole,
    RunStatus,
    WithheldReason,
)

__all__ = [
    "AssertionRead",
    "AssertionWrite",
    "CaseComparisonRead",
    "CaseResultRead",
    "ComparisonBlockRead",
    "CostDeltaRead",
    "EvalCaseRead",
    "EvalCaseWrite",
    "EvalRunAccepted",
    "EvalRunHandle",
    "EvalRunRead",
    "EvalRunStart",
    "EvalSuiteCreate",
    "EvalSuiteRead",
    "EvalSuiteUpdate",
]


class AssertionWrite(BaseModel):
    type: AssertionType
    value: Any = None


class AssertionRead(BaseModel):
    type: AssertionType
    value: Any = None


class EvalCaseWrite(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    input_messages: list[dict[str, Any]] = Field(min_length=1)
    input_variables: dict[str, Any] = Field(default_factory=dict)
    assertions: list[AssertionWrite] = Field(default_factory=list)


class EvalCaseRead(BaseModel):
    case_id: str
    ordinal: int
    name: str
    input_messages: list[dict[str, Any]]
    input_variables: dict[str, Any]
    assertions: list[AssertionRead]


class EvalSuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    output_modality: OutputModality
    cases: list[EvalCaseWrite] = Field(default_factory=list, max_length=MAX_CASES_PER_SUITE)


class EvalSuiteUpdate(BaseModel):
    output_modality: OutputModality
    cases: list[EvalCaseWrite] = Field(default_factory=list, max_length=MAX_CASES_PER_SUITE)


class EvalSuiteRead(BaseModel):
    suite_id: str
    prompt_id: str
    name: str
    suite_version: int
    output_modality: OutputModality
    case_count: int
    created_by: str
    created_at: datetime
    cases: list[EvalCaseRead] | None = None


class EvalRunStart(BaseModel):
    version_id: str
    suite_names: list[str] | None = None


class EvalRunHandle(BaseModel):
    run_id: str
    suite_id: str
    suite_name: str
    suite_version: int
    role: RunRole


class EvalRunAccepted(BaseModel):
    prompt_id: str
    version_id: str
    runs: list[EvalRunHandle]


class EvalRunRead(BaseModel):
    run_id: str
    prompt_id: str
    version_id: str
    suite_id: str
    role: RunRole
    status: RunStatus
    refused_reason: RefusalReason | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    pass_count: int
    fail_count: int
    error_count: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_amount: Decimal | None = None
    cost_currency: str | None = None
    priced_at: datetime | None = None
    started_by: str


class CaseResultRead(BaseModel):
    case_result_id: str
    run_id: str
    case_id: str
    outcome: CaseOutcome
    assertion_results: list[dict[str, Any]]
    output_content: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_code: str | None = None
    attempt_count: int
    created_at: datetime


class CostDeltaRead(BaseModel):
    input_tokens: int
    output_tokens: int
    cost: Decimal | None = None
    currency: str | None = None
    ratio: Decimal | None = None


class CaseComparisonRead(BaseModel):
    case_id: str
    name: str
    baseline_outcome: CaseOutcome | None = None
    candidate_outcome: CaseOutcome
    changed: bool


class ComparisonBlockRead(BaseModel):
    suite_id: str
    suite_name: str
    suite_version: int
    candidate_run_id: str
    baseline_run_id: str | None = None
    baseline_ran_at: datetime | None = None
    cases: list[CaseComparisonRead]
    cost_delta: CostDeltaRead | None = None
    withheld_reason: WithheldReason | None = None
    cost_warning: bool = False
