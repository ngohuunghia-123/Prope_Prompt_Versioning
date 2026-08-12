from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from prope.release_control.domain import (
    MAX_CLOSED_NOTE_CHARACTERS,
    MAX_COMMENT_CHARACTERS,
    MAX_REASON_CHARACTERS,
    Decision,
    ReleaseKind,
    ReviewTaskKind,
    ReviewTaskStatus,
)

__all__ = [
    "ApprovalRead",
    "ApproveAndReleaseRequest",
    "ApproveAndReleaseRead",
    "ApproveRequest",
    "BreakGlassReleaseRequest",
    "CloseReviewTaskRequest",
    "DiffFieldRead",
    "DiffLineRead",
    "DiffRead",
    "HistoryEntryRead",
    "ReleaseRead",
    "ReleaseRequest",
    "RequestChangesRequest",
    "ReviewScreenRead",
    "ReviewTaskRead",
    "RevisionCardRead",
    "SuiteEvidenceRead",
    "SummaryRead",
    "WithdrawReleaseRequest",
]


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: str | None = Field(default=None, max_length=MAX_COMMENT_CHARACTERS)
    acknowledgement_reason: str | None = Field(default=None, max_length=MAX_REASON_CHARACTERS)


class RequestChangesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: str = Field(min_length=1, max_length=MAX_COMMENT_CHARACTERS)


class ReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str = Field(min_length=1, max_length=64)
    kind: ReleaseKind = ReleaseKind.RELEASE
    expected_current_version_id: str | None = Field(default=None, max_length=64)
    reason: str | None = Field(default=None, max_length=MAX_REASON_CHARACTERS)


class ApproveAndReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: str | None = Field(default=None, max_length=MAX_COMMENT_CHARACTERS)
    acknowledgement_reason: str | None = Field(default=None, max_length=MAX_REASON_CHARACTERS)
    expected_current_version_id: str | None = Field(default=None, max_length=64)


class BreakGlassReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str = Field(min_length=1, max_length=64)
    expected_current_version_id: str | None = Field(default=None, max_length=64)
    reason: str = Field(min_length=1, max_length=MAX_REASON_CHARACTERS)


class WithdrawReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=MAX_REASON_CHARACTERS)


class CloseReviewTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=MAX_CLOSED_NOTE_CHARACTERS)


class ApprovalRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    prompt_id: str
    version_id: str
    decision: Decision
    reviewer_id: str
    comment: str | None
    acknowledgement_reason: str | None
    evidence_digest: dict[str, Any]
    self_approved: bool
    decided_at: datetime


class ReleaseRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: str
    prompt_id: str
    version_id: str | None
    kind: ReleaseKind
    previous_version_id: str | None
    approval_id: str | None
    break_glass: bool
    reason: str | None
    released_by: str
    released_at: datetime


class ReviewTaskRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_task_id: str
    prompt_id: str
    version_id: str
    kind: ReviewTaskKind
    assigned_role: str
    due_at: datetime | None
    status: ReviewTaskStatus
    created_from_release_id: str | None
    created_at: datetime
    closed_by: str | None
    closed_at: datetime | None
    closed_note: str | None
    overdue: bool


class ApproveAndReleaseRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval: ApprovalRead
    release: ReleaseRead


class DiffLineRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: str
    text: str
    from_line: int | None
    to_line: int | None


class DiffFieldRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    before: str | None
    after: str | None
    changed: bool


class DiffRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_version_id: str
    to_version_id: str
    lines: list[DiffLineRead]
    fields: list[DiffFieldRead]


class SuiteEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_id: str
    suite_name: str
    suite_version: int
    run_id: str
    status: str
    pass_count: int
    fail_count: int
    error_count: int
    case_count: int
    baseline_run_id: str | None
    baseline_ran_at: datetime | None
    cost_delta: dict[str, Any] | None


class SummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suites: list[SuiteEvidenceRead]
    total_cost_delta: dict[str, Any] | None
    requires_acknowledgement: bool
    cost_warning: bool


class RevisionCardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str
    prompt_id: str
    revision_number: int
    change_summary: str
    author_id: str
    status: str
    created_at: datetime


class HistoryEntryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    action: str
    target_type: str
    target_id: str
    actor_id: str | None
    reason: str | None
    details: dict[str, Any]
    occurred_at: datetime


class ReviewScreenRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    model_name: str
    revision: RevisionCardRead
    diff: DiffRead | None
    diff_against_version_id: str | None
    summary: SummaryRead | None
    summary_available: bool
    acknowledgement_required: bool
    self_authored: bool
    released_version_id: str | None
    latest_revision_number: int
    revisions_since: int
    approvals: list[ApprovalRead]
    review_task: ReviewTaskRead | None
    history: list[HistoryEntryRead]
