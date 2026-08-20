"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from prope.canonical_prompt import MAX_CANONICAL_CHARACTERS


class SearchResultItem(BaseModel):
    """One item in a search result."""

    prompt_id: str
    title: str
    purpose: str
    similarity: float | None = None
    keywords: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    variations: dict[str, list[str]] = Field(default_factory=dict)
    language: list[str] = Field(default_factory=list)
    matched_fields: list[str] = Field(default_factory=list)
    is_indexed: bool = False
    body_preview: str | None = None


class SearchResponse(BaseModel):
    """Response for GET /api/v1/prompts/search."""

    prompts: list[SearchResultItem]
    next_cursor: str | None = None
    total: int | None = None
    search_type: str


class SimilarSearchCreate(BaseModel):
    """``POST /api/v1/prompts/search/similar``. A whole prompt, not a query string.

    The GET search takes its query in ``?q=`` and caps it at 500 characters,
    which is a search box's length and not a prompt's. The one caller of this
    route is the import screen, which holds a body somebody pasted or uploaded
    and wants to know whether the workspace already has it — so the cap here is
    ``MAX_CANONICAL_CHARACTERS``, the same 32 KiB ceiling a revision body and a
    conversion source are held to. Anything the registry would accept can be
    checked for duplicates before it is accepted.

    ``limit`` caps the rows the dialog is SHOWN, and it no longer decides what is
    compared. Retrieval always runs at ``comparison.RETRIEVAL_LIMIT`` because the
    mouth of the funnel owes recall — a candidate that never enters can never be
    confirmed or rejected — and the cheap rungs behind it are what make that
    affordable. There is no cursor: a paged duplicate check is a duplicate check
    nobody finishes reading.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_CANONICAL_CHARACTERS)
    limit: int = Field(default=5, ge=1, le=10)


class ComparisonFindingRead(BaseModel):
    """One finding, as a code the client translates.

    ADR-0053: the API returns a machine ``code`` and the client owns the words.
    ``params`` carries machine values only — variable names, keys, counts — so
    this row can be rendered in Vietnamese without the backend ever holding a
    display string.
    """

    code: str
    #: ``hard`` is a veto the reviewer may not trade away, ``soft`` is weighed,
    #: ``info`` is context.
    severity: str
    #: ``input_contract``, ``output_contract``, ``task`` or ``coverage``.
    axis: str
    params: dict = Field(default_factory=dict)


class ComparisonBlockOverlapRead(BaseModel):
    """One canonical block's overlap with its counterpart.

    ``block`` is a canonical tag — ``instructions``, ``output_format`` — or
    ``whole_text`` when the incoming body has not been converted to canonical XML
    yet and there were no blocks to align. It stays literal, as statuses do
    (ADR-0053): it names a part of the prompt contract, not a phrase.
    """

    block: str
    #: Share of the incoming block's distinctive weight this candidate carries.
    #: A containment over IDF-weighted terms, **not a cosine and not "how
    #: similar"** — the interface must not render it as a percentage of sameness.
    score: float = 0.0
    #: The shared words that produced the score, most distinctive first. Prompt
    #: text, and the only content-bearing field in the comparison payload —
    #: admissible here beside `body_preview`, and nowhere near a log line.
    shared_terms: list[str] = Field(default_factory=list)


class ComparisonOverlapRead(BaseModel):
    """Why a candidate is on the sheet: what the two prompts actually share."""

    blocks: list[ComparisonBlockOverlapRead] = Field(default_factory=list)
    #: Every block the pre-filter scored, zeros included. ``blocks`` above lists
    #: only what overlapped; a metric grid needs this to tell *shared nothing*
    #: from *never compared*, and drawing the second as ``0%`` would report an
    #: incompatibility about a block neither prompt declares.
    compared_blocks: list[str] = Field(default_factory=list)
    shared_variables: list[str] = Field(default_factory=list)
    variable_overlap: float = 0.0
    #: The denominator of ``variable_overlap``. Zero means the incoming prompt
    #: takes no variables, which is not the same as sharing none of them.
    variables_required: int = 0
    metadata_overlap: float = 0.0


class ComparisonCandidateRead(BaseModel):
    """One candidate's verdict and the evidence behind it."""

    prompt_id: str
    #: ``same`` | ``supersedes`` | ``variant`` | ``related``. Never ``unrelated``:
    #: a candidate that is not related is not on the sheet at all.
    verdict: str
    #: ``add_revision`` or ``create_new``. Derived in code from the verdict and
    #: the findings, never emitted by a model.
    action: str
    findings: list[ComparisonFindingRead] = Field(default_factory=list)
    similarity: float | None = None
    structural_score: float = 0.0
    #: How much of the incoming prompt's distinctive weight this candidate
    #: carries, 0..1. **The one field on this row that is a percentage**, and the
    #: one the display floor is applied to. It measures text coverage, never
    #: agreement about the job — that is ``verdict``.
    match_score: float = 0.0
    #: False when the pre-filter ranked it but the adjudicator never saw it, or
    #: when the adjudicator was unavailable. Such a candidate is shown as context
    #: and never as a duplicate.
    adjudicated: bool = False
    #: Closed-vocabulary codes the adjudicator chose from — `same_action_same_object`,
    #: `different_audience`, `candidate_covers_more_cases` and the rest. The
    #: client translates them; the wire never carries the model's own words.
    reasons: list[str] = Field(default_factory=list)
    #: The free rung's evidence. `None` only for a candidate assembled without a
    #: structural pass, which no shipping path produces.
    overlap: ComparisonOverlapRead | None = None


class SimilarSearchResponse(SearchResponse):
    """``POST /prompts/search/similar``: the rows, plus why each one is there.

    **An evidence sheet, not a verdict.** ``recommended_action`` is what the
    dialog should pre-select and it is ``create_new`` unless the evidence for
    something else is complete — the outcome that discards nothing and writes
    something recoverable. ``use_existing`` is never recommended from declared
    evidence alone: making somebody discard their prompt for one that does not do
    their job is the single error in this flow with no recovery.

    ``prompts`` keeps the existing row shape so one zod schema still validates
    both search routes; ``candidates`` is the parallel classification, joined by
    ``prompt_id``.
    """

    recommended_action: str = "create_new"
    recommended_prompt_id: str | None = None
    #: How many prompts retrieval offered before the free pre-filter cut them,
    #: and how many reached the adjudicator. Shown as *what was checked* — the
    #: rows are what was found, and the two are different numbers.
    retrieved: int = 0
    adjudicated: int = 0
    #: The ``match_score`` a candidate had to clear to be listed, and how many
    #: were held back by it alone. Both travel because a row absent for a
    #: threshold is otherwise indistinguishable from a row nothing found, and the
    #: difference decides whether *"no duplicates"* can be trusted.
    match_floor: float = 0.0
    below_floor: int = 0
    candidates: list[ComparisonCandidateRead] = Field(default_factory=list)
    #: Findings about the answer itself: adjudication unavailable, the incoming
    #: body not canonical, how much of the workspace is indexed. An empty
    #: ``prompts`` list means *nothing indexed resembles this* and never *this is
    #: not a duplicate*, and this is where that distinction is carried.
    coverage: list[ComparisonFindingRead] = Field(default_factory=list)


class IndexStatusResponse(BaseModel):
    """Response for GET /api/v1/prompts/{prompt_id}/index."""

    is_indexed: bool
    is_stale: bool = False
    indexed_at: datetime | None = None
    indexed_by: str | None = None
    version_id: str | None = None
    nearest_neighbor: dict | None = None


class IndexTriggerResponse(BaseModel):
    """Response for POST /api/v1/prompts/{prompt_id}/index."""

    job_id: str


class IndexPreviewResponse(BaseModel):
    """Response for GET /api/v1/prompts/{prompt_id}/index/preview."""

    keywords: list[str]
    topics: list[str]
    entities: list[str]
    variations: dict
    language: list[str]
    duplicate_warning: dict | None = None


class IndexDeindexResponse(BaseModel):
    """Response for DELETE /api/v1/prompts/{prompt_id}/index."""

    success: bool


class JobStatusResponse(BaseModel):
    """Response for GET /api/v1/prompt-search/jobs/{job_id}."""

    job_id: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class SearchQueryParams:
    """Query parameters for search endpoints."""

    q: Annotated[str | None, Query(max_length=500, description="Search query")] = None
    cursor: Annotated[str | None, Query(description="Pagination cursor")] = None
    limit: Annotated[int, Query(ge=1, le=200)] = 50
