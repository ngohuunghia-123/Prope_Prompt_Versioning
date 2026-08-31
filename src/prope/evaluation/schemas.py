from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from prope.evaluation.domain import (
    MAX_ATTACHED_DATASETS,
    MAX_CASES_PER_SUITE,
    AssertionType,
    CaseOutcome,
    DatasetKind,
    OutputModality,
    RefusalReason,
    RunRole,
    RunStatus,
    WithheldReason,
)
from prope.evaluation.generation import DEFAULT_CASE_TARGET

__all__ = [
    "AnalysisFindingRead",
    "AssertionRead",
    "AssertionWrite",
    "AttachmentRead",
    "AttachmentWrite",
    "CaseComparisonRead",
    "CaseResultRead",
    "ComparisonBlockRead",
    "CostDeltaRead",
    "DatasetCaseRead",
    "DatasetDeleted",
    "DatasetDetailRead",
    "DatasetDraftRequest",
    "DatasetRead",
    "DatasetSuggestRead",
    "DatasetSuggestRequest",
    "DatasetSuggestionRead",
    "DatasetWrite",
    "EvalAnalysisRead",
    "EvalAnalysisRequest",
    "EvalCaseRead",
    "EvalCaseTraceRead",
    "EvalTraceSpanRead",
    "EvalCaseWrite",
    "EvalRunAccepted",
    "EvalRunHandle",
    "EvalRunRead",
    "EvalRunStart",
    "EvalRunSummaryRead",
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


class DatasetRead(BaseModel):
    """One row of the eval workspace's dataset tree.

    Builtin and workspace datasets share this shape deliberately: the tree, the
    tick and the run never learn which kind they are holding, so step 4b's
    workspace-owned rows arrive without a wire change. ``read_only`` and
    ``folder`` are the only fields that differ in practice — a builtin is always
    read-only and always sits in the *Chung* group (``folder = ""``).

    ``cases`` is absent from the list projection. Five datasets of twenty cases
    each is a payload nobody reading a sidebar asked for.
    """

    dataset_id: str
    name: str
    description: str
    kind: DatasetKind
    tags: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(default_factory=list, max_length=10)
    output_modality: OutputModality
    case_count: int
    folder: str
    read_only: bool
    #: A warning rendered beside the set: why ticking it may fail a prompt that
    #: is working correctly. ``None`` for a set that applies to any prompt.
    applicability: str | None = None
    fingerprint: str


class DatasetCaseRead(BaseModel):
    """One case as the editor loads it.

    No ``case_id``. A dataset edit replaces the case list wholesale rather than
    reconciling it, so an id here would be stable only until the next save —
    and a client that keyed on one would be keying on something that means
    "row that happened to exist last time". ``ordinal`` is the identity a case
    has within its dataset.
    """

    ordinal: int
    name: str
    input_messages: list[dict[str, Any]]
    input_variables: dict[str, Any] = Field(default_factory=dict)
    assertions: list[AssertionRead] = Field(default_factory=list)


class DatasetDetailRead(DatasetRead):
    cases: list[DatasetCaseRead] = Field(default_factory=list)


class DatasetWrite(BaseModel):
    """Create or replace a library dataset.

    ``copy_from`` is how a shipped Chung set becomes editable: the server
    resolves it and uses its cases when ``cases`` is empty. Copying server-side
    rather than round-tripping through the client means the copy is provably the
    same set — the fingerprint of the copy equals the fingerprint of the
    original, which is the property that makes "sao chép" honest.
    """

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    kind: DatasetKind = DatasetKind.GOLDEN
    tags: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(default_factory=list, max_length=10)
    output_modality: OutputModality = OutputModality.TEXT
    #: A registry folder slug, or `""` for the workspace-wide Chung group.
    folder: str = Field(default="", max_length=63)
    cases: list[EvalCaseWrite] = Field(default_factory=list, max_length=MAX_CASES_PER_SUITE)
    copy_from: str | None = Field(default=None, max_length=100)


class DatasetDeleted(BaseModel):
    """What a delete actually did.

    ``detached`` is reported rather than swallowed because deleting a dataset
    silently changes what *other* prompts will be measured with. A number the
    interface can put in a sentence is the difference between that being a
    decision and being a surprise.
    """

    dataset_id: str
    detached: int


class DatasetDraftRequest(BaseModel):
    """Ask the agent to draft a dataset from a prompt.

    ``version_id`` is optional: absent means the prompt's latest revision, which
    is the one somebody looking at this screen has just written. The drafted set
    lands in the library and is **not** attached — a model does not get to decide
    what a prompt is measured against.
    """

    version_id: str | None = None
    folder: str | None = Field(default=None, max_length=63)
    name: str | None = Field(default=None, max_length=100)
    brief: str | None = Field(default=None, max_length=4000)
    case_target: int = Field(default=DEFAULT_CASE_TARGET, ge=1, le=MAX_CASES_PER_SUITE)


class DatasetSuggestRequest(BaseModel):
    """Ask for ranked dataset proposals for one prompt's body.

    Same optional-``version_id`` shape as drafting: absent means latest. Unlike
    drafting, the answer **writes nothing** — a suggestion is a proposal to
    tick, and the tick stays the write.
    """

    version_id: str | None = None


class DatasetSuggestionRead(BaseModel):
    dataset_id: str
    name: str
    #: Why this set, in one sentence a person can judge without opening it.
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class DatasetSuggestRead(BaseModel):
    prompt_id: str
    version_id: str
    suggestions: list[DatasetSuggestionRead] = Field(default_factory=list)


class EvalAnalysisRequest(BaseModel):
    """Ask for a read of this revision's finished runs.

    Required ``version_id``: the analysis is about the revision the tab has
    selected, never "the prompt in general" — runs of other revisions would
    describe a body that no longer exists.
    """

    version_id: str = Field(min_length=1, max_length=64)


class AnalysisFindingRead(BaseModel):
    suite_name: str
    assertion_type: str
    failed: int
    total: int
    issue: str
    advice: str
    severity: Literal["advice", "warning"]


class EvalAnalysisRead(BaseModel):
    prompt_id: str
    version_id: str
    runs_considered: int
    brief: str
    findings: list[AnalysisFindingRead] = Field(default_factory=list)


class AttachmentWrite(BaseModel):
    """The whole tick-state of the dataset tree, sent at once.

    Declarative rather than incremental: what arrives is what the prompt ends up
    attached to, so a tick and an untick are the same request and replaying one
    is harmless. The cap is ``MAX_ATTACHED_DATASETS`` because every attachment
    becomes a suite and every suite becomes a run — an unbounded list is an
    unbounded number of provider calls behind one button.
    """

    dataset_ids: list[str] = Field(default_factory=list, max_length=MAX_ATTACHED_DATASETS)


class AttachmentRead(BaseModel):
    """A prompt's choice of one dataset, and what became of it.

    ``suite_id`` is ``None`` until the first run — attaching writes no suite, so
    a tick that has never been run has nothing to point at. ``stale`` says the
    next run will write a new suite version rather than reuse the last one,
    which is how the workspace can show "this set changed since you last ran it"
    without diffing anything.

    ``dataset`` is ``None`` when the id no longer resolves. That happens when a
    shipped set's ``version`` is bumped: the old id retires, the attachment
    survives, and unticking is how it is cleared. Rendering it as unresolved
    beats 500-ing on a row that is merely out of date.
    """

    dataset_id: str
    suite_name: str
    suite_id: str | None
    stale: bool
    attached_by: str
    attached_at: datetime
    dataset: DatasetRead | None = None


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


class EvalRunSummaryRead(EvalRunRead):
    """A run as the prompt-detail Eval tab lists it: the run, plus what it ran.

    **A subclass rather than a parallel model.** The run's own fields have one
    definition, so a column added to `EvalRunRead` cannot appear on the detail
    view and go missing from the history. What is added here is not the run's —
    the suite's name and version, and the dataset the suite was materialised
    from — which is why they are added rather than folded in.

    All four are nullable. A hand-authored suite was never built from a dataset,
    and that is a fact about it, not a gap: the tab names the suite and says
    nothing about a dataset, instead of showing an empty cell that reads like
    missing data.
    """

    suite_name: str | None = None
    suite_version: int | None = None
    dataset_id: str | None = None
    dataset_name: str | None = None


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


class EvalTraceSpanRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: Literal["span", "generation", "event"]
    status: Literal["success", "error"]
    duration_ms: int | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class EvalCaseTraceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    status: Literal["success", "error"]
    duration_ms: int | None = None
    spans: list[EvalTraceSpanRead]


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
