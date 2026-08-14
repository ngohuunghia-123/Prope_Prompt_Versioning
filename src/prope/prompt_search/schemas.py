"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field


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
