from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from prope.prompt_ingestion.domain import MAX_BATCH_ITEMS


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BatchRead(StrictModel):
    id: str
    mode: Literal["files", "table"]
    status: str
    default_namespace: str
    default_access_level: Literal["private", "workspace"]
    field_mapping: dict[str, str]
    review_version: int
    item_count: int = 0
    ready_count: int = 0
    committed_count: int = 0
    error_count: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    expires_at: datetime


class SemanticMatchRead(StrictModel):
    prompt_id: str
    title: str
    purpose: str = ""
    similarity: float | None = None


class ItemRead(StrictModel):
    id: str
    batch_id: str
    ordinal: int
    source_filename: str
    source_format: str
    source_hash: str
    source_text: str
    title: str
    purpose: str
    namespace: str
    name: str
    tags: list[str]
    change_summary: str
    canonical_body: str | None
    conversion_model: str | None
    conversion_schema_version: str | None
    semantic_matches: list[SemanticMatchRead]
    resolution: Literal["create", "revise", "skip"] | None
    target_prompt_id: str | None
    base_version_id: str | None
    state: str
    error_code: str | None
    attempts: int
    item_version: int
    result_prompt_id: str | None
    result_version_id: str | None
    created_at: datetime
    updated_at: datetime


class ItemListRead(StrictModel):
    items: list[ItemRead]
    next_cursor: int | None = None


class ItemUpdate(StrictModel):
    expected_version: Annotated[int, Field(ge=1)]
    title: Annotated[str | None, Field(default=None, min_length=1, max_length=200)]
    purpose: Annotated[str | None, Field(default=None, max_length=2000)]
    namespace: Annotated[str | None, Field(default=None, min_length=1, max_length=63)]
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=63)]
    tags: Annotated[list[Annotated[str, Field(min_length=1, max_length=60)]] | None, Field(default=None, max_length=20)]
    change_summary: Annotated[str | None, Field(default=None, min_length=1, max_length=200)]
    resolution: Literal["create", "revise", "skip"] | None = None
    target_prompt_id: str | None = None
    base_version_id: str | None = None

    @model_validator(mode="after")
    def revision_has_target(self) -> ItemUpdate:
        if self.resolution == "revise" and not self.target_prompt_id:
            raise ValueError("revise resolution requires target_prompt_id")
        return self


class RetryRequest(StrictModel):
    item_ids: Annotated[list[str], Field(min_length=1, max_length=MAX_BATCH_ITEMS)]


class RetryRead(StrictModel):
    retried_item_ids: list[str]


class CommitProposalCreate(StrictModel):
    expected_review_version: Annotated[int, Field(ge=1)]
    item_ids: Annotated[list[str], Field(min_length=1, max_length=MAX_BATCH_ITEMS)]


class CommitProposalRead(StrictModel):
    id: str
    batch_id: str
    status: str
    expected_review_version: int
    preview: dict[str, object]


class ProposalDecision(StrictModel):
    approve: bool


class CommitResultRead(StrictModel):
    id: str
    status: str
    batch_id: str
    committed_count: int = 0
    conflict_count: int = 0


class BatchListRead(StrictModel):
    batches: list[BatchRead]
