"""Value objects and domain types for prompt-search. No SQL, no FastAPI, no I/O."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

__all__ = [
    "MAX_ENTITIES",
    "MAX_SEARCH_TERMS",
    "STOP_WORDS",
    "index_document",
    "search_terms",
    "MAX_KEYWORDS",
    "MAX_TERM_CHARACTERS",
    "MAX_TOPICS",
    "MAX_VARIATIONS",
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

#: Caps on what one extraction may write into an index row.
#:
#: **They live in `domain` rather than beside the agent for an import reason as
#: much as a modelling one.** `agent/evaluation.py` needs them to score a live
#: extraction, and `agent/extraction.py` imports `evaluation` at module scope; if
#: they lived in `agent/dspy_program.py` that chain would pull `import dspy` —
#: eleven seconds of litellm, tokenizers and the OTel SDK — onto the startup of
#: every process built from the image, `worker` included. They are also genuinely
#: domain constraints: they describe what a `prompt_search_index` row may hold,
#: not how the agent that fills it is configured.
MAX_KEYWORDS = 15
MAX_TOPICS = 5
MAX_ENTITIES = 15
MAX_VARIATIONS = 5

#: Longest single index term kept. A "keyword" longer than this is a sentence the
#: model copied out of the body, which is useless for search and is the content
#: leak the extraction instruction forbids.
MAX_TERM_CHARACTERS = 80


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


def index_document(*, title: str, purpose: str, body: str) -> str:
    """The text a prompt is indexed under: what it is called, what it is for, what it says.

    All three, because each answers a question the others cannot. Two prompts
    with the same body and different titles are the same prompt; two with the
    same title and different bodies are not. Embedding the purpose alone — what
    this module did until migration 0014 — meant the import screen compared a
    pasted instruction against a one-line description and found nothing, which
    read as *no duplicates* rather than as *the wrong question was asked*.

    Blank parts are dropped rather than contributing empty lines: `purpose`
    defaults to the empty string on a freshly registered prompt, and a leading
    blank line is noise the embedding would have to account for.
    """
    return "\n".join(part for part in (title.strip(), purpose.strip(), body.strip()) if part)


@dataclass(frozen=True, slots=True)
class IndexRow:
    """A prompt_search_index row as this module reads it."""

    id: str
    prompt_id: str
    version_id: str
    workspace_id: str
    #: `latest` or `released`. A prompt may hold one of each (migration 0014).
    role: str
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
            role=row["role"],
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


#: Words that carry no retrieval signal, in the MVP's two interface languages.
#:
#: Short rather than exhaustive on purpose. A stop list is a blunt instrument and
#: every word on it is a word nobody can search for; these are the ones that
#: appear in almost every prompt ever written, so keeping them would make the
#: lexical leg match everything equally and therefore rank nothing.
STOP_WORDS: frozenset[str] = frozenset(
    {
        "about", "after", "against", "always", "answer", "assistant", "based", "because",
        "before", "being", "between", "could", "does", "doing", "each", "else", "ensure",
        "every", "from", "give", "have", "here", "should", "into", "make", "many",
        "more", "must", "never", "only", "other", "output", "over", "please", "provide",
        "response", "same", "some", "such", "than", "that", "their", "them", "then",
        "there", "these", "they", "this", "those", "through", "user", "using", "very",
        "what", "when", "where", "which", "while", "will", "with", "would", "your",
        "bạn", "của", "các", "cho", "khi", "không", "một", "người", "những", "phải",
        "trong", "và", "với",
    }
)

#: How many terms the lexical leg is allowed to probe with.
#:
#: Each term costs one indexed query, so this is a latency budget as much as a
#: relevance one. Eight is enough to characterise a prompt — a refund-triage
#: prompt and a peer-review prompt do not share eight distinctive words — and few
#: enough that the leg stays comparable to the single vector query beside it.
MAX_SEARCH_TERMS = 8


def search_terms(query: str, limit: int = MAX_SEARCH_TERMS) -> tuple[str, ...]:
    """The most distinctive words in a query, for substring retrieval.

    **A whole prompt body is not a search term.** ``search_text`` is matched with
    ``LIKE '%term%'``, so passing two thousand characters of instructions matches
    nothing at all — which is why an unindexed prompt was previously unfindable
    by the very flow meant to find near-duplicates of it. Terms are what make a
    document query into a retrieval query.

    Ranked by length before frequency, which is a deliberate choice and not an
    arbitrary one: with no corpus statistics to compute IDF from, length is the
    cheapest available proxy for *distinctive*. "escalate" says more about a
    prompt than "order", even when "order" occurs three times as often.

    Folding is left to the caller's query — ``list_prompts`` folds the term with
    the same Postgres dictionary that folded the document (A-150), and a second
    implementation of "fold" in Python is two implementations that agree until
    they do not.
    """
    counts: dict[str, int] = {}
    word = []
    for character in query.lower():
        if character.isalnum():
            word.append(character)
            continue
        if word:
            token = "".join(word)
            word = []
            if len(token) >= 4 and token not in STOP_WORDS and not token.isdigit():
                counts[token] = counts.get(token, 0) + 1
    if word:
        token = "".join(word)
        if len(token) >= 4 and token not in STOP_WORDS and not token.isdigit():
            counts[token] = counts.get(token, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: (-len(item[0]), -item[1], item[0]))
    return tuple(term for term, _ in ranked[:limit])
