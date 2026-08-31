from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RunKind(StrEnum):
    CHAT = "chat"
    IMPORT = "import"
    EVALUATION = "evaluation"
    PRODUCTION_ANALYSIS = "production_analysis"
    IMPROVEMENT = "improvement"


class PlanBasis(StrEnum):
    LLM = "llm"
    EXPLICIT_USER_ACTION = "explicit_user_action"
    SCHEDULE = "schedule"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    SUCCEEDED = "succeeded"
    WARNING = "warning"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeKind(StrEnum):
    LLM = "llm"
    RETRIEVAL = "retrieval"
    AUTOMATED_CHECK = "automated_check"
    PROVIDER_CALL = "provider_call"
    HUMAN_DECISION = "human_decision"


class LifecyclePhase(StrEnum):
    DRAFT = "draft"
    EVALUATED = "evaluated"
    WAITING_REVIEW = "waiting_review"
    APPROVED = "approved"
    LIVE = "live"
    ATTENTION = "attention"


class NextAction(StrEnum):
    RUN_EVALUATION = "run_evaluation"
    EDIT_PROMPT = "edit_prompt"
    SUBMIT_REVIEW = "submit_review"
    VIEW_RELEASE = "view_release"
    RELEASE = "release"
    VIEW_ACTIVITY = "view_activity"
    VIEW_IMPROVEMENTS = "view_improvements"


@dataclass(frozen=True, slots=True)
class PlanNode:
    capability: str
    kind: NodeKind


PLAN_CATALOGUE: dict[RunKind, tuple[PlanNode, ...]] = {
    RunKind.CHAT: (
        PlanNode("chat_guardrail", NodeKind.AUTOMATED_CHECK),
        PlanNode("chat_routing", NodeKind.LLM),
        PlanNode("chat_response", NodeKind.LLM),
    ),
    RunKind.IMPORT: (
        PlanNode("prompt_conversion", NodeKind.LLM),
        PlanNode("prompt_search", NodeKind.RETRIEVAL),
        PlanNode("duplicate_adjudication", NodeKind.LLM),
        PlanNode("create_revision", NodeKind.HUMAN_DECISION),
    ),
    RunKind.EVALUATION: (
        PlanNode("evaluation_dataset", NodeKind.RETRIEVAL),
        PlanNode("provider_execution", NodeKind.PROVIDER_CALL),
        PlanNode("evaluation_assertions", NodeKind.AUTOMATED_CHECK),
        PlanNode("review_result", NodeKind.HUMAN_DECISION),
    ),
    RunKind.PRODUCTION_ANALYSIS: (
        PlanNode("prompt_observation", NodeKind.RETRIEVAL),
        PlanNode("production_analysis", NodeKind.AUTOMATED_CHECK),
    ),
    RunKind.IMPROVEMENT: (
        PlanNode("prompt_observation", NodeKind.RETRIEVAL),
        PlanNode("improvement_detector", NodeKind.AUTOMATED_CHECK),
        PlanNode("improvement_triage", NodeKind.LLM),
        # ADR-0070: present in every improvement plan; the drift path marks it
        # `skipped` because a catalogue remedy needs no drafter, and the
        # eval-evidence path runs it — the one LLM step that authors anything.
        PlanNode("improvement_draft", NodeKind.LLM),
        PlanNode("evaluation_gate", NodeKind.PROVIDER_CALL),
        PlanNode("approve_revision", NodeKind.HUMAN_DECISION),
    ),
}


@dataclass(frozen=True, slots=True)
class RunRow:
    id: str
    workspace_id: str
    requested_by: str
    kind: RunKind
    plan_basis: PlanBasis
    status: RunStatus
    prompt_id: str | None
    version_id: str | None
    source_refs: tuple[str, ...]
    result_actions: tuple[dict[str, str], ...]
    progress_current: int | None
    progress_total: int | None
    progress_unit: str | None
    acknowledged_at: datetime | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
