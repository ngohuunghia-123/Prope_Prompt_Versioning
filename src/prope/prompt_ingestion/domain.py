from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final

MAX_BATCH_ITEMS: Final = 100
MAX_UPLOAD_BYTES: Final = 20 * 1024 * 1024
MAX_EXPANDED_BYTES: Final = 50 * 1024 * 1024
MAX_ZIP_MEMBERS: Final = 100
MAX_SOURCE_CHARACTERS: Final = 32_768
STAGING_RETENTION: Final = timedelta(days=7)
LEASE_DURATION: Final = timedelta(minutes=5)
MAX_AUTOMATIC_ATTEMPTS: Final = 3


class ImportMode(StrEnum):
    FILES = "files"
    TABLE = "table"


class BatchStatus(StrEnum):
    PROCESSING = "processing"
    REVIEW_READY = "review_ready"
    COMMITTING = "committing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    EXPIRED = "expired"


class ItemState(StrEnum):
    PARSED = "parsed"
    CONVERTING = "converting"
    DUPLICATE_CHECK = "duplicate_check"
    READY = "ready"
    RETRYABLE = "retryable"
    NEEDS_ATTENTION = "needs_attention"
    COMMITTING = "committing"
    COMMITTED = "committed"
    SKIPPED = "skipped"
    FAILED = "failed"


class Resolution(StrEnum):
    CREATE = "create"
    REVISE = "revise"
    SKIP = "skip"


class IngestionError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ParsedCandidate:
    source_filename: str
    source_format: str
    source_text: str
    title: str
    purpose: str
    namespace: str
    name: str
    tags: tuple[str, ...]
    change_summary: str
    target_prompt_id: str | None = None


@dataclass(frozen=True, slots=True)
class ItemSnapshot:
    item_id: str
    item_version: int
    resolution: str
    target_prompt_id: str | None
    base_version_id: str | None
