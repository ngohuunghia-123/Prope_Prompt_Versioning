from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

__all__ = [
    "BREAK_GLASS_FOLLOW_UP",
    "DEFAULT_REVIEW_ROLE",
    "MAX_CLOSED_NOTE_CHARACTERS",
    "MAX_COMMENT_CHARACTERS",
    "MAX_REASON_CHARACTERS",
    "AcknowledgementRequired",
    "ApprovalRow",
    "CostEvidence",
    "Decision",
    "EvidenceDigest",
    "NoApprovalRecorded",
    "NotPreviouslyReleased",
    "ReasonRequired",
    "ReleaseKind",
    "ReleaseRow",
    "ReviewAlreadyOpen",
    "ReviewTaskKind",
    "ReviewTaskNotOpen",
    "ReviewTaskRow",
    "ReviewTaskStatus",
    "RevisionNotApproved",
    "SuiteEvidence",
]

MAX_COMMENT_CHARACTERS = 2000

MAX_REASON_CHARACTERS = 500

MAX_CLOSED_NOTE_CHARACTERS = 2000

BREAK_GLASS_FOLLOW_UP = timedelta(hours=24)

DEFAULT_REVIEW_ROLE = "Reviewer"


class Decision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


class ReleaseKind(StrEnum):
    RELEASE = "release"
    RESTORE = "restore"
    WITHDRAW = "withdraw"


class ReviewTaskKind(StrEnum):
    REVIEW = "review"
    BREAK_GLASS_FOLLOWUP = "break_glass_followup"


class ReviewTaskStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class CostEvidence:
    input_tokens: int
    output_tokens: int
    cost: Decimal | None
    currency: str | None
    ratio: Decimal | None

    def as_json(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost": None if self.cost is None else str(self.cost),
            "currency": self.currency,
            "ratio": None if self.ratio is None else str(self.ratio),
        }


@dataclass(frozen=True, slots=True)
class SuiteEvidence:
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
    cost_delta: CostEvidence | None

    def as_json(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "suite_name": self.suite_name,
            "suite_version": self.suite_version,
            "run_id": self.run_id,
            "status": self.status,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "error_count": self.error_count,
            "case_count": self.case_count,
            "baseline_run_id": self.baseline_run_id,
            "baseline_ran_at": None
            if self.baseline_ran_at is None
            else self.baseline_ran_at.isoformat(),
            "cost_delta": None if self.cost_delta is None else self.cost_delta.as_json(),
        }


@dataclass(frozen=True, slots=True)
class EvidenceDigest:
    version_id: str
    captured_at: datetime
    summary_available: bool
    requires_acknowledgement: bool
    suites: tuple[SuiteEvidence, ...] = field(default_factory=tuple)
    total_cost_delta: CostEvidence | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "captured_at": self.captured_at.isoformat(),
            "summary_available": self.summary_available,
            "requires_acknowledgement": self.requires_acknowledgement,
            "suites": [suite.as_json() for suite in self.suites],
            "total_cost_delta": None
            if self.total_cost_delta is None
            else self.total_cost_delta.as_json(),
        }

    @property
    def failing_suites(self) -> tuple[str, ...]:
        return tuple(
            suite.suite_name
            for suite in self.suites
            if suite.fail_count or suite.error_count
        )


@dataclass(frozen=True, slots=True)
class ApprovalRow:
    id: str
    workspace_id: str
    prompt_id: str
    version_id: str
    decision: Decision
    reviewer_id: str
    comment: str | None
    acknowledgement_reason: str | None
    evidence_digest: dict[str, Any]
    self_approved: bool
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class ReleaseRow:
    id: str
    workspace_id: str
    prompt_id: str
    version_id: str | None
    kind: ReleaseKind
    previous_version_id: str | None
    approval_id: str | None
    break_glass: bool
    reason: str | None
    released_by: str
    released_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewTaskRow:
    id: str
    workspace_id: str
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

    def is_overdue(self, now: datetime) -> bool:
        return (
            self.status is ReviewTaskStatus.OPEN
            and self.due_at is not None
            and self.due_at <= now
        )


class ReviewAlreadyOpen(Exception):  # noqa: N818
    def __init__(self, prompt_id: str, version_id: str) -> None:
        super().__init__(
            f"{prompt_id} already has revision {version_id} In review; at most one revision per "
            "prompt is In review, and only a NEWER submission supersedes the open task"
        )
        self.prompt_id = prompt_id
        self.version_id = version_id


class AcknowledgementRequired(Exception):  # noqa: N818
    def __init__(self, version_id: str, failing_suites: tuple[str, ...], available: bool) -> None:
        super().__init__(
            f"approving {version_id} requires a one-line acknowledgement_reason: "
            + (
                f"these suites are not passing: {', '.join(failing_suites) or 'unknown'}"
                if available
                else "the review summary could not be pulled, and unknown evidence is treated "
                "like failing evidence"
            )
        )
        self.version_id = version_id
        self.failing_suites = failing_suites
        self.available = available


class ReasonRequired(Exception):  # noqa: N818
    def __init__(self, action: str) -> None:
        super().__init__(f"{action} carries a mandatory one-line reason and none was supplied")
        self.action = action


class RevisionNotApproved(Exception):  # noqa: N818
    def __init__(self, version_id: str, status: str) -> None:
        super().__init__(
            f"{version_id} is {status!r} and only an Approved revision may be released"
        )
        self.version_id = version_id
        self.status = status


class NoApprovalRecorded(Exception):  # noqa: N818
    def __init__(self, version_id: str) -> None:
        super().__init__(
            f"{version_id} carries no approval record; a release without one is only reachable "
            "through break-glass, which is a separate permission and a separate route"
        )
        self.version_id = version_id


class NotPreviouslyReleased(Exception):  # noqa: N818
    def __init__(self, version_id: str) -> None:
        super().__init__(
            f"{version_id} has never been released, so restoring to it is an ordinary release "
            "and still requires the release decision"
        )
        self.version_id = version_id


class ReviewTaskNotOpen(Exception):  # noqa: N818
    def __init__(self, task_id: str, status: ReviewTaskStatus) -> None:
        super().__init__(f"review task {task_id} is {status.value} and cannot be closed again")
        self.task_id = task_id
        self.status = status
