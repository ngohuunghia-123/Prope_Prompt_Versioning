"""Value objects and domain types for prompt-search. No SQL, no FastAPI, no I/O."""

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

__all__ = [
    "MAX_ENTITIES",
    "MAX_SEARCH_TERMS",
    "MIN_TERM_LENGTH",
    "STOP_WORDS",
    "DOCUMENT_CHARACTER_LIMIT",
    "INDEX_DOCUMENT_STRATEGY",
    "build_index_document",
    "enriched_index_document",
    "index_document",
    "query_terms",
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


#: How much text one embedding call may carry.
#:
#: **This bound was missing entirely, and its absence was a latent outage.**
#: A revision body may be 32,768 characters (`MAX_BODY_CHARACTERS`); the
#: embedding models this product is configured against accept 8,191 tokens.
#: English prose sits near four characters per token so the largest prompt in a
#: sample library measured 7,917 tokens — under the ceiling by 3%. Vietnamese is
#: nowhere near four characters per token, and ADR-0053 makes Vietnamese the
#: interface language. The first prompt written in it at full length would have
#: failed its indexing job with `embedding_error` and, on the import screen,
#: turned the duplicate check into a 503.
#:
#: 12,000 characters rather than the maximum that fits: past the first few
#: thousand characters a mean-pooled vector barely moves, and everything cut here
#: is still reachable through the lexical leg, which reads the registry's
#: trigram document over the *whole* body.
DOCUMENT_CHARACTER_LIMIT = 12_000


def enriched_index_document(
    *,
    title: str,
    purpose: str,
    body: str,
    keywords: tuple[str, ...] = (),
    topics: tuple[str, ...] = (),
    entities: tuple[str, ...] = (),
    limit: int = DOCUMENT_CHARACTER_LIMIT,
) -> str:
    """What a prompt is embedded as: its distilled description, then its text.

    **The index-time extraction is promoted from decoration to representation.**
    Every indexed prompt already carries agent-extracted keywords, topics and
    entities, and until this they earned a `+0.05` bonus on a keyword substring
    match and nothing else. They are a compression of the document produced by a
    model that read it — which is exactly what
    `docs/materials/2-rag-pipeline.pdf` p26 recommends embedding, and cost
    nothing extra here because the job already pays for them.

    **Why the raw document alone ranked badly.** A prompt library is 375
    documents in one genre: they open the same way, they use the same vocabulary,
    and each one is thousands of words long. Mean-pooled into a single vector,
    the shared genre dominates and the two lines that identify the prompt — its
    title and its subject — contribute a few percent. Leading with title, topics
    and keywords puts the discriminating text where it is a large share of the
    document instead of a rounding error.

    Blank sections are dropped, and the body is cut to `limit` — see
    :data:`DOCUMENT_CHARACTER_LIMIT` for why a cut has to exist at all.
    """
    sections = [
        title.strip(),
        ", ".join(topic.strip() for topic in topics if topic.strip()),
        ", ".join(keyword.strip() for keyword in keywords if keyword.strip()),
        ", ".join(entity.strip() for entity in entities if entity.strip()),
        purpose.strip(),
    ]
    head = "\n".join(section for section in sections if section)
    remaining = max(0, limit - len(head) - 1)
    trimmed_body = body.strip()[:remaining]
    return f"{head}\n{trimmed_body}".strip() if trimmed_body else head


#: Which document an indexing job embeds. `legacy` is title + purpose + the whole
#: body; `enriched` leads with the extraction. Switchable because the difference
#: is an empirical claim about ranking, and a claim like that should be
#: falsifiable by re-running `eval/retrieval` rather than by argument.
INDEX_DOCUMENT_STRATEGY = os.environ.get("PROMPT_SEARCH_INDEX_DOCUMENT", "enriched")


def build_index_document(
    *,
    title: str,
    purpose: str,
    body: str,
    metadata: "ExtractedMetadata | None" = None,
    strategy: str = "",
) -> str:
    """The text an indexing job embeds, under whichever strategy is configured.

    One place, because the worker and the evaluation harness must embed the same
    bytes or the evaluation measures a system nobody ships.
    """
    chosen = strategy or INDEX_DOCUMENT_STRATEGY
    if chosen == "legacy" or metadata is None:
        return index_document(title=title, purpose=purpose, body=body)
    return enriched_index_document(
        title=title,
        purpose=purpose,
        body=body,
        keywords=metadata.keywords,
        topics=metadata.topics,
        entities=metadata.entities,
    )


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
        # Short function words. Absent while the minimum term length was four,
        # and required the moment it dropped to three: without them a search for
        # "how can the agent use tools" probes `the`, `can` and `use` against a
        # corpus where every document contains all three.
        "and", "are", "for", "not", "but", "all", "any", "out", "its", "was",
        "has", "had", "may", "our", "own", "too", "also", "the", "you",
        "một", "các", "cần", "cho", "khi", "này", "như", "thì", "được",
    }
)

#: How many terms the lexical leg is allowed to probe with.
#:
#: Each term costs one indexed query, so this is a latency budget as much as a
#: relevance one. Eight is enough to characterise a prompt — a refund-triage
#: prompt and a peer-review prompt do not share eight distinctive words — and few
#: enough that the leg stays comparable to the single vector query beside it.
MAX_SEARCH_TERMS = 8

#: The shortest token worth probing.
#:
#: Four excluded `sql`, `api`, `rag`, `ssh`, `xml`, `ci` — the class of term the
#: lexical leg exists to catch, because they are exactly what a dense vector is
#: worst at (`docs/materials/2-rag-pipeline.pdf` p19). A search for `SQL` found
#: nothing lexically and fell back to whatever the vector leg felt like. Three
#: costs a handful of common short words, which the stop list now absorbs.
MIN_TERM_LENGTH = 3

#: Above this many tokens the input is a document, not a question.
#:
#: The two callers hand this module very different text: a search box sends a
#: phrase, and the import screen's duplicate check sends up to 32 KiB of pasted
#: prompt. Both need terms, and they need them chosen differently — every word of
#: a phrase matters, while a document has to be reduced to its most distinctive
#: few. One threshold, so there is one function and not two that drift.
PHRASE_TOKEN_LIMIT = 16


def _tokenize(text: str) -> list[str]:
    """Lowercased alphanumeric runs, in order, minus stop words and short tokens."""
    tokens: list[str] = []
    word: list[str] = []
    for character in text.lower():
        if character.isalnum():
            word.append(character)
            continue
        if word:
            token = "".join(word)
            word = []
            if len(token) >= MIN_TERM_LENGTH and token not in STOP_WORDS and not token.isdigit():
                tokens.append(token)
    if word:
        token = "".join(word)
        if len(token) >= MIN_TERM_LENGTH and token not in STOP_WORDS and not token.isdigit():
            tokens.append(token)
    return tokens


def query_terms(query: str, limit: int = MAX_SEARCH_TERMS) -> tuple[str, ...]:
    """The terms to probe an index with, for a phrase or for a whole document.

    **A phrase keeps its words; a document is reduced to its longest.** Below
    :data:`PHRASE_TOKEN_LIMIT` tokens the input is somebody's question and every
    word of it is a deliberate constraint — dropping "cluster" from "kubernetes
    cluster hardening" throws away the half that narrows the answer. Above it the
    input is a pasted prompt, where keeping everything means probing with a
    hundred words that appear in every document, and length is the cheapest
    available stand-in for *distinctive* with no corpus statistics to hand.

    Order is preserved for phrases so that a caller truncating to `limit` keeps
    what the person typed first, which is what they led with.
    """
    tokens = _tokenize(query)
    if not tokens:
        return ()

    if len(tokens) <= PHRASE_TOKEN_LIMIT:
        seen: set[str] = set()
        ordered: list[str] = []
        for token in tokens:
            if token not in seen:
                seen.add(token)
                ordered.append(token)
        return tuple(ordered[:limit])

    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-len(item[0]), -item[1], item[0]))
    return tuple(term for term, _ in ranked[:limit])


#: Retained name for :func:`query_terms`.
#:
#: The two were one function doing one job under two rules, and the rules were
#: the bug: this one required four characters and ranked by length, which is
#: right for a pasted document and wrong for a typed phrase. Folding stays where
#: it always was — in the caller's SQL, where ``list_prompts`` folds the term
#: with the same Postgres dictionary that folded the document (A-150). A second
#: implementation of *fold* in Python is two implementations that agree until
#: they do not.
search_terms = query_terms
