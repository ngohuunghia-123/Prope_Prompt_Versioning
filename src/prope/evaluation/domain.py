import hashlib
import json
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
    "MAX_ATTACHED_DATASETS",
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
    "AttachmentRow",
    "CaseComparison",
    "CaseDraft",
    "CaseErrorCode",
    "CaseOutcome",
    "CaseResultRow",
    "CaseRow",
    "ClaimedRun",
    "ComparisonBlock",
    "CostDelta",
    "DatasetKind",
    "DatasetNameTaken",
    "DatasetNotFound",
    "DatasetSpec",
    "EmptySuite",
    "EvalSuiteNotFound",
    "ModalityMismatch",
    "OutputModality",
    "SuiteNameTaken",
    "fingerprint_cases",
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

#: How many datasets one prompt may have attached at once. Every attachment
#: becomes a suite and every suite becomes a run, so this is the ceiling on how
#: many provider calls one press of "Chạy thử" can start: eight sets of twenty
#: cases is 160 dispatches, which is already well past the 120 s p95 the
#: evaluation success criterion asks for. It is a guard rail on cost and
#: latency, not a statement about how many yardsticks a prompt deserves.
MAX_ATTACHED_DATASETS = 8

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


class DatasetKind(StrEnum):
    """A badge on a dataset, and nothing the engine reads.

    It exists so the tree can say *what kind of thing is going to fail* before
    anybody opens the set — a red-team failure is news, a regression failure is
    a bug. Deliberately not an ``AssertionType`` concern: two sets of identical
    assertions can be a golden set and a regression set depending on why they
    were written.
    """

    GOLDEN = "golden"
    REGRESSION = "regression"
    RED_TEAM = "red-team"


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


def fingerprint_cases(cases: "tuple[CaseDraft, ...]") -> str:
    """A stable digest of what a dataset measures.

    Lives here rather than beside either of its two callers because the shipped
    catalogue and the workspace's own tables must produce the *same* digest for
    the same cases — a set copied out of Chung into a folder is unchanged, and a
    second hashing implementation would be the only thing saying otherwise.

    ``sort_keys`` and a fixed separator are what make it reproducible across
    processes; without them a dict ordering change would restate every suite on
    the next deploy. The name, description and folder are deliberately absent:
    those are how a set is labelled, not what it asserts, so renaming one must
    not force a new suite version onto every prompt that attached it.
    """
    payload = [
        {
            "name": case.name,
            "input_messages": list(case.input_messages),
            "input_variables": dict(case.input_variables),
            "assertions": [spec.as_json() for spec in case.assertions],
        }
        for case in cases
    ]
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """A reusable bundle of cases, resolved and ready to materialise.

    **This is not what a run reads.** A run reads an ``eval_suite``, which is
    per-prompt, versioned and immutable, because A-004 needs the same yardstick
    on both sides of a comparison. A dataset is the *library* object somebody
    picked; ``materialise_attachment`` is what turns one into a suite version.

    ``id`` is either ``builtin:<slug>@<version>``, resolving to a YAML file in
    ``common_datasets`` that ships in the image, or a ``dst_`` ULID resolving to
    a workspace row (step 4b). Both shapes flow through here identically, which
    is the point of the type — the tree, the attachment and the materialisation
    never learn which kind they are holding.

    ``fingerprint`` is over the cases and their assertions only. Renaming a
    dataset or fixing its description does not restate what it measures, so it
    must not force a new suite version onto every prompt that attached it.

    ``folder`` is a slug value, never a foreign key, the same posture
    ``registry.folder`` takes toward prompts. An empty string is the *Chung*
    group, which is where every builtin sits: those apply workspace-wide and are
    filed under no domain area.
    """

    id: str
    name: str
    description: str
    kind: DatasetKind
    tags: tuple[str, ...]
    output_modality: OutputModality
    cases: tuple[CaseDraft, ...]
    fingerprint: str
    applicability: str | None = None
    folder: str = ""
    read_only: bool = True

    @property
    def case_count(self) -> int:
        return len(self.cases)


@dataclass(frozen=True, slots=True)
class AttachmentRow:
    """One prompt's choice of one dataset.

    ``materialised_suite_id`` and ``materialised_fingerprint`` are both NULL
    until the first run — ticking is free, and nothing in ``eval_suite`` is
    written until somebody actually asks to measure something. After a run they
    move together (``ck_dataset_attachment_materialisation_is_whole``): the
    suite the dataset was last turned into, and the dataset's fingerprint at
    that moment, so the next run can tell reuse from restate.
    """

    workspace_id: str
    prompt_id: str
    dataset_id: str
    suite_name: str
    materialised_suite_id: str | None
    materialised_fingerprint: str | None
    attached_by: str
    attached_at: datetime

    def is_stale(self, fingerprint: str) -> bool:
        """True when a run would have to write a new suite version.

        Never materialised counts as stale — there is nothing to reuse.
        """
        return (
            self.materialised_suite_id is None or self.materialised_fingerprint != fingerprint
        )


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


#: How far back a prompt's run history reads in one request.
#:
#: A run is an act somebody performs on purpose and pays a provider for, so runs
#: accrue in tens rather than in millions — unlike call records, which is why that
#: read is a keyset and this one is a ceiling. Two hundred covers a year of
#: weekly runs against four suites, and a prompt that exceeds it has a history
#: question no tab was going to answer anyway.
RUN_HISTORY_LIMIT = 200


@dataclass(frozen=True, slots=True)
class RunListing:
    """A run plus the two labels that let a reader tell it apart from its siblings.

    **Composition rather than a wider `RunRow`.** The labels come from
    `eval_suite` and `dataset`, which the run itself does not own; folding them
    into `RunRow` would put another table's columns on the type that four other
    call sites construct from `evaluation.eval_run` alone.

    Every label is nullable. A suite row can be absent — and a hand-authored
    suite has no dataset behind it at all, which is a fact about how it was made
    rather than a gap to paper over.
    """

    run: RunRow
    suite_name: str | None
    suite_version: int | None
    dataset_id: str | None
    dataset_name: str | None


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


class DatasetNotFound(Exception):  # noqa: N818
    def __init__(self, dataset_id: str) -> None:
        super().__init__(f"no such dataset: {dataset_id}")
        self.dataset_id = dataset_id


class DatasetNameTaken(Exception):  # noqa: N818
    """Dataset names are unique across the workspace, not per folder.

    The reason is downstream: a dataset's name becomes the *suite* name when it
    is materialised, and ``uq_dataset_attachment_suite_name`` already refuses
    two datasets sharing one on a prompt. Enforcing uniqueness in the library
    means somebody meets that rule while naming a dataset — where it is obvious
    what to do about it — rather than later, while ticking one.
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"this workspace already has a dataset named {name!r}")
        self.name = name


class SuiteNameTaken(Exception):  # noqa: N818
    """Two datasets cannot share a suite name on one prompt.

    ``write_suite_version`` versions a suite *by name*, so a second dataset
    attached under a name already in use would join the first one's lineage and
    each run would overwrite the other's yardstick — silently, and in a way that
    looks like the suite simply changed. ``uq_dataset_attachment_suite_name`` is
    what actually refuses it; this is how that refusal reaches a caller.
    """

    def __init__(self, prompt_id: str, suite_name: str) -> None:
        super().__init__(
            f"prompt {prompt_id} already has a dataset attached as suite {suite_name!r}"
        )
        self.prompt_id = prompt_id
        self.suite_name = suite_name


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
