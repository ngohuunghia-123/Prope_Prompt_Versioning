from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

__all__ = [
    "ASSERTION_TYPES_BY_MODALITY",
    "CASE_DEADLINE_MS",
    "COST_WARNING_BLOCKS",
    "COST_WARNING_THRESHOLD",
    "MAX_ASSERTION_INPUT_CHARACTERS",
    "MAX_CASES_PER_SUITE",
    "MAX_CONCURRENT_RUNS",
    "MAX_TRANSPORT_RETRIES",
    "PER_RUN_CONCURRENCY",
    "REGEX_TIMEOUT_SECONDS",
    "SWEEP_NO_PROGRESS_SECONDS",
    "AssertionOutcome",
    "AssertionPatternInvalid",
    "AssertionSpec",
    "AssertionType",
    "CaseComparison",
    "CaseDraft",
    "CaseErrorCode",
    "CaseOutcome",
    "CaseResultRow",
    "CaseRow",
    "ClaimedRun",
    "ComparisonBlock",
    "CostDelta",
    "EmptySuite",
    "EvalSuiteNotFound",
    "ModalityMismatch",
    "OutputModality",
    "RefusalReason",
    "ReviewSummary",
    "RunNotFound",
    "RunRole",
    "RunRow",
    "RunStatus",
    "SuiteSummary",
    "SuiteVersionMismatch",
    "WithheldReason",
]

MAX_CASES_PER_SUITE = 20

MAX_ASSERTION_INPUT_CHARACTERS = 32768

REGEX_TIMEOUT_SECONDS = 1.0

MAX_CONCURRENT_RUNS = 2

PER_RUN_CONCURRENCY = 5

CASE_DEADLINE_MS = 60_000

MAX_TRANSPORT_RETRIES = 2

COST_WARNING_THRESHOLD = Decimal("0.20")

COST_WARNING_BLOCKS = False

SWEEP_NO_PROGRESS_SECONDS = 300.0


class OutputModality(StrEnum):
    TEXT = "text"
    STRUCTURED = "structured"


class RunRole(StrEnum):
    CANDIDATE = "candidate"
    BASELINE = "baseline"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    REFUSED = "refused"


class CaseOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class AssertionType(StrEnum):
    EXACT = "exact"
    SUBSTRING = "substring"
    REGEX = "regex"
    JSON_SCHEMA = "json_schema"
    REQUIRED_PHRASE = "required_phrase"
    FORBIDDEN_PHRASE = "forbidden_phrase"
    MAX_LENGTH = "max_length"
    MAX_LATENCY = "max_latency"
    MAX_COST = "max_cost"
    ASSET_COUNT = "asset_count"
    ASSET_TYPE = "asset_type"


ASSERTION_TYPES_BY_MODALITY: dict[OutputModality, frozenset[AssertionType]] = {
    OutputModality.TEXT: frozenset(
        {
            AssertionType.EXACT,
            AssertionType.SUBSTRING,
            AssertionType.REGEX,
            AssertionType.JSON_SCHEMA,
            AssertionType.REQUIRED_PHRASE,
            AssertionType.FORBIDDEN_PHRASE,
            AssertionType.MAX_LENGTH,
            AssertionType.MAX_LATENCY,
            AssertionType.MAX_COST,
        }
    ),
    OutputModality.STRUCTURED: frozenset(
        {
            AssertionType.JSON_SCHEMA,
            AssertionType.ASSET_COUNT,
            AssertionType.ASSET_TYPE,
            AssertionType.MAX_LATENCY,
            AssertionType.MAX_COST,
        }
    ),
}


class CaseErrorCode(StrEnum):
    ASSERTION_TIMEOUT = "assertion_timeout"
    ASSERTION_UNEVALUABLE = "assertion_unevaluable"
    DISPATCH_FAILED = "dispatch_failed"


class RefusalReason(StrEnum):
    SPEND_CEILING_REACHED = "spend_ceiling_reached"
    MODALITY_MISMATCH = "modality_mismatch"


class WithheldReason(StrEnum):
    HAS_ERRORS = "has_errors"
    UNPRICED = "unpriced"
    UNKNOWN_USAGE = "unknown_usage"
    NO_BASELINE = "no_baseline"
    MIXED_CURRENCY = "mixed_currency"
    RUN_INCOMPLETE = "run_incomplete"


@dataclass(frozen=True, slots=True)
class AssertionSpec:
    type: AssertionType
    value: Any = None

    def as_json(self) -> dict[str, Any]:
        return {"type": self.type.value, "value": self.value}


@dataclass(frozen=True, slots=True)
class AssertionOutcome:
    type: AssertionType
    passed: bool
    detail: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {"type": self.type.value, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class SuiteRow:
    id: str
    workspace_id: str
    prompt_id: str
    name: str
    suite_version: int
    output_modality: OutputModality
    case_count: int
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CaseRow:
    id: str
    workspace_id: str
    suite_id: str
    ordinal: int
    name: str
    input_messages: tuple[dict[str, Any], ...]
    input_variables: dict[str, Any]
    assertions: tuple[AssertionSpec, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CaseDraft:
    name: str
    input_messages: tuple[dict[str, Any], ...]
    assertions: tuple[AssertionSpec, ...]
    input_variables: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunRow:
    id: str
    workspace_id: str
    prompt_id: str
    version_id: str
    suite_id: str
    role: RunRole
    status: RunStatus
    refused_reason: RefusalReason | None
    started_at: datetime | None
    finished_at: datetime | None
    pass_count: int
    fail_count: int
    error_count: int
    input_tokens: int | None
    output_tokens: int | None
    cost_amount: Decimal | None
    cost_currency: str | None
    priced_at: datetime | None
    started_by: str


@dataclass(frozen=True, slots=True)
class CaseResultRow:
    id: str
    workspace_id: str
    run_id: str
    case_id: str
    outcome: CaseOutcome
    assertion_results: tuple[AssertionOutcome, ...]
    output_content: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    error_code: str | None
    attempt_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ClaimedRun:
    run_id: str
    workspace_id: str
    prompt_id: str
    version_id: str
    suite_id: str


@dataclass(frozen=True, slots=True)
class CostDelta:
    input_tokens: int
    output_tokens: int
    cost: Decimal | None
    currency: str | None
    ratio: Decimal | None


@dataclass(frozen=True, slots=True)
class CaseComparison:
    case_id: str
    name: str
    baseline_outcome: CaseOutcome | None
    candidate_outcome: CaseOutcome
    changed: bool


@dataclass(frozen=True, slots=True)
class SuiteSummary:
    suite_id: str
    suite_name: str
    suite_version: int
    run_id: str
    status: RunStatus
    pass_count: int
    fail_count: int
    error_count: int
    case_count: int
    baseline_run_id: str | None
    baseline_ran_at: datetime | None
    baseline_reused: bool
    cost_delta: CostDelta | None
    withheld_reason: WithheldReason | None
    cost_warning: bool


@dataclass(frozen=True, slots=True)
class ComparisonBlock:
    suite_id: str
    suite_name: str
    suite_version: int
    candidate_run_id: str
    baseline_run_id: str | None
    baseline_ran_at: datetime | None
    cases: tuple[CaseComparison, ...]
    cost_delta: CostDelta | None
    withheld_reason: WithheldReason | None
    cost_warning: bool


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    prompt_id: str
    version_id: str
    suites: tuple[SuiteSummary, ...] = field(default_factory=tuple)
    total_cost_delta: CostDelta | None = None
    withheld_reason: WithheldReason | None = None
    cost_warning: bool = False
    requires_acknowledgement: bool = False


class EvalSuiteNotFound(Exception):  # noqa: N818
    def __init__(self, suite_id: str) -> None:
        super().__init__(f"no such eval suite: {suite_id}")
        self.suite_id = suite_id


class RunNotFound(Exception):  # noqa: N818
    def __init__(self, run_id: str) -> None:
        super().__init__(f"no such eval run: {run_id}")
        self.run_id = run_id


class EmptySuite(Exception):  # noqa: N818
    def __init__(self, suite_id: str) -> None:
        super().__init__(
            f"suite {suite_id} has no cases; an empty suite is not a pass (A-059) and there "
            "is nothing to dispatch"
        )
        self.suite_id = suite_id


class ModalityMismatch(Exception):  # noqa: N818
    def __init__(self, declared: OutputModality, returned: str) -> None:
        super().__init__(
            f"the suite declares output_modality={declared.value} and the target returned "
            f"{returned}; every assertion would fail at once and read as a bad prompt"
        )
        self.declared = declared
        self.returned = returned


class SuiteVersionMismatch(Exception):  # noqa: N818
    def __init__(self, candidate_suite_id: str, baseline_suite_id: str) -> None:
        super().__init__(
            f"{candidate_suite_id} and {baseline_suite_id} are different versions of a suite; "
            "two revisions measured with two yardsticks is not a comparison"
        )
        self.candidate_suite_id = candidate_suite_id
        self.baseline_suite_id = baseline_suite_id


class AssertionPatternInvalid(ValueError):  # noqa: N818
    def __init__(self, ordinal: int, detail: str) -> None:
        super().__init__(f"case {ordinal} carries an assertion that cannot be compiled: {detail}")
        self.ordinal = ordinal
        self.detail = detail
