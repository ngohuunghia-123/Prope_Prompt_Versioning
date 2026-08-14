"""Value objects and domain types for prompt-search. No SQL, no FastAPI, no I/O."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

__all__ = [
    "ExtractedMetadata",
    "ExtractedVariations",
    "IndexStatus",
    "IndexJobStatus",
    "IndexRow",
    "IndexJobRow",
    "NearestNeighborWarning",
    "SearchResult",
    "SearchType",
]


class SearchType(StrEnum):
    """Search mode: quick (keyword) or ai (semantic)."""

    QUICK = "quick"
    AI = "ai"


class IndexJobStatus(StrEnum):
    """Status of an indexing job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IndexStatus(StrEnum):
    """Index status for a prompt."""

    NOT_INDEXED = "not_indexed"
    INDEXED = "indexed"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ExtractedVariations:
    """Multilingual variations of the prompt purpose."""

    en: tuple[str, ...] = field(default_factory=tuple)
    vi: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "en": list(self.en),
            "vi": list(self.vi),
        }

    @classmethod
    def from_dict(cls, data: dict[str, list[str]]) -> "ExtractedVariations":
        return cls(
            en=tuple(data.get("en", [])),
            vi=tuple(data.get("vi", [])),
        )


@dataclass(frozen=True, slots=True)
class ExtractedMetadata:
    """Structured metadata extracted by the App Agent."""

    keywords: tuple[str, ...]
    topics: tuple[str, ...]
    entities: tuple[str, ...]
    variations: ExtractedVariations
    language: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "keywords": list(self.keywords),
            "topics": list(self.topics),
            "entities": list(self.entities),
            "variations": self.variations.to_dict(),
            "language": list(self.language),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractedMetadata":
        return cls(
            keywords=tuple(data.get("keywords", [])),
            topics=tuple(data.get("topics", [])),
            entities=tuple(data.get("entities", [])),
            variations=ExtractedVariations.from_dict(data.get("variations", {})),
            language=tuple(data.get("language", [])),
        )


@dataclass(frozen=True, slots=True)
class IndexRow:
    """A prompt_search_index row as this module reads it."""

    id: str
    prompt_id: str
    version_id: str
    workspace_id: str
    keywords: tuple[str, ...]
    topics: tuple[str, ...]
    entities: tuple[str, ...]
    variations: ExtractedVariations
    language: tuple[str, ...]
    is_bilingual: bool
    indexed_at: datetime
    indexed_by: str
    nearest_neighbor_id: str | None
    nearest_neighbor_similarity: float | None
    embedding_model: str

    @classmethod
    def from_db_row(cls, row: dict) -> "IndexRow":
        return cls(
            id=row["id"],
            prompt_id=row["prompt_id"],
            version_id=row["version_id"],
            workspace_id=row["workspace_id"],
            keywords=tuple(row["keywords"] or []),
            topics=tuple(row["topics"] or []),
            entities=tuple(row["entities"] or []),
            variations=ExtractedVariations.from_dict(row["variations"] or {}),
            language=tuple(row["language"] or []),
            is_bilingual=row["is_bilingual"],
            indexed_at=row["indexed_at"],
            indexed_by=row["indexed_by"],
            nearest_neighbor_id=row["nearest_neighbor_id"],
            nearest_neighbor_similarity=(
                float(row["nearest_neighbor_similarity"]) if row["nearest_neighbor_similarity"] is not None else None
            ),
            embedding_model=row["embedding_model"],
        )


@dataclass(frozen=True, slots=True)
class IndexJobRow:
    """A prompt_search_index_job row as this module reads it."""

    job_id: str
    prompt_id: str
    version_id: str
    workspace_id: str
    status: IndexJobStatus
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    result_json: dict | None
    created_by: str

    @classmethod
    def from_db_row(cls, row: dict) -> "IndexJobRow":
        return cls(
            job_id=row["job_id"],
            prompt_id=row["prompt_id"],
            version_id=row["version_id"],
            workspace_id=row["workspace_id"],
            status=IndexJobStatus(row["status"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error=row["error"],
            result_json=row["result_json"],
            created_by=row["created_by"],
        )


@dataclass(frozen=True, slots=True)
class NearestNeighborWarning:
    """A near-duplicate detected at index time."""

    prompt_id: str
    title: str
    similarity: float


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One result from a search operation."""

    prompt_id: str
    title: str
    purpose: str
    similarity: float | None
    keywords: tuple[str, ...]
    topics: tuple[str, ...]
    is_indexed: bool
    version_id: str | None
    entities: tuple[str, ...] = ()
    variations: ExtractedVariations = field(default_factory=ExtractedVariations)
    language: tuple[str, ...] = ()
    matched_fields: tuple[str, ...] = ()
