from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from prope.agent_run.domain import LifecyclePhase, NextAction, NodeKind, PlanBasis, RunKind, RunStatus


class AgentRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: RunKind
    plan_basis: PlanBasis = PlanBasis.EXPLICIT_USER_ACTION
    prompt_id: str | None = Field(default=None, max_length=64)
    version_id: str | None = Field(default=None, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=200)

    @model_validator(mode="after")
    def prompt_scope_is_explicit(self) -> "AgentRunCreate":
        if self.plan_basis is not PlanBasis.EXPLICIT_USER_ACTION:
            raise ValueError("LLM and schedule plan bases are assigned by trusted backend callers")
        if self.kind is not RunKind.IMPORT and self.prompt_id is None:
            raise ValueError("prompt_id is required for this run kind")
        if self.version_id is not None and self.prompt_id is None:
            raise ValueError("version_id requires prompt_id")
        return self


class AgentNodeRead(BaseModel):
    id: str
    sequence: int
    capability: str
    kind: NodeKind
    status: str
    evidence_refs: list[str] = Field(default_factory=list)
    progress_current: int | None = None
    progress_total: int | None = None
    progress_unit: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AgentEdgeRead(BaseModel):
    source: str
    target: str


class AgentRunRead(BaseModel):
    run_id: str
    kind: RunKind
    plan_basis: PlanBasis
    status: RunStatus
    prompt_id: str | None = None
    version_id: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    result_actions: list[dict[str, str]] = Field(default_factory=list)
    progress_current: int | None = None
    progress_total: int | None = None
    progress_unit: str | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    nodes: list[AgentNodeRead] = Field(default_factory=list)
    edges: list[AgentEdgeRead] = Field(default_factory=list)


class EvalSummaryRead(BaseModel):
    run_id: str
    status: str
    passed: int
    failed: int
    errors: int
    total: int
    finished_at: datetime | None = None


class LifecycleSummaryRead(BaseModel):
    prompt_id: str
    version_id: str
    phase: LifecyclePhase
    live_version_id: str | None = None
    last_eval: EvalSummaryRead | None = None
    approval_status: str
    open_finding_count: int
    readiness_attention_count: int | None = None
    next_action: NextAction
