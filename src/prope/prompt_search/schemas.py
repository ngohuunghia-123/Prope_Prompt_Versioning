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

    ``limit`` defaults to three because this is a top-N probe shown in a
    decision dialog, not a result page. There is no cursor for the same reason.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_CANONICAL_CHARACTERS)
    limit: int = Field(default=3, ge=1, le=10)


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
