"""The documentation corpus and its retrieval. The RAG half of the assistant.

**Why a corpus at all, when the model already "knows" how prompt registries
work.** Deck 5 (p35) calls an answer with no source *ungrounded* and puts it top
of the risk table; deck 2 makes grounding the property a RAG pipeline exists to
buy. A model asked "how does approval work here" will answer confidently about
how approval works *somewhere*, and the person cannot tell the difference. Every
product answer this assistant gives is retrieved from files in this package or it
is refused.

**Why the corpus ships inside `src/` rather than under `docs/`.** `.dockerignore`
excludes `docs/`, so a corpus there would be present in every test run and absent
from every deployment — the worst possible split. Living here also makes it what
it should be: a reviewed artifact that ships with the code and changes through a
pull request, not a directory somebody can edit on the host.

**Hybrid retrieval with a lexical floor, and the floor is the interesting half.**
Dense retrieval needs the embedding provider. This assistant answers questions
like *"why did my release fail"*, which is precisely the question somebody asks
during an outage — possibly the same outage that took the provider down. So the
lexical leg runs unconditionally and the dense leg is an improvement on top of
it, never a precondition. `retrieve()` reports which legs actually ran, and the
answer layer says so rather than silently degrading (deck 4, p41: a pipeline that
returns nothing looks identical to a pipeline with nothing to return).

**Chunking is by heading, deliberately, and deck 4 (p19) is why**: cutting by
character count makes the agent quote half a clause — still with a citation,
still wrong. A `##` heading is an editorial decision about where one answer ends,
which is the boundary a citation should land on.
"""

import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

__all__ = [
    "CORPUS_DIRECTORY",
    "Chunk",
    "RetrievalOutcome",
    "ScoredChunk",
    "corpus_fingerprint",
    "load_corpus",
    "reset_corpus",
    "retrieve",
]

CORPUS_DIRECTORY: Final = Path(__file__).parent / "knowledge"

#: Below this cosine the dense leg is asserting nothing. Lower than search's 0.25
#: floor because the corpus is small and topically narrow: with six documents,
#: the nearest chunk to "how do I roll back" is genuinely about rollback even at
#: 0.2, whereas a 375-prompt library has real near-misses at that distance.
MIN_DENSE_SIMILARITY: Final = 0.20

#: Below this share of the question's distinctive weight, a lexical hit is one
#: incidental word in common.
MIN_LEXICAL_SCORE: Final = 0.15

#: Shorter than this and a token is grammar rather than subject matter. Three
#: rather than four because Vietnamese carries meaning in short syllables — `nợ`,
#: `key`, `xoá` — and a four-character floor deletes half the language.
MIN_TERM_LENGTH: Final = 3

#: Words that appear in almost every question and therefore separate nothing.
#: Both languages, because the interface is Vietnamese and the vocabulary is not.
_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        "and", "are", "can", "does", "for", "from", "has", "how", "the", "this",
        "that", "what", "when", "where", "which", "who", "why", "with", "you",
        "your", "prope", "prompt", "promt",
        "cai", "cho", "khi", "khong", "lam", "mot", "nao", "nay", "nhu", "nhung",
        "sao", "the", "thi", "toi", "trong", "va", "voi", "duoc", "gi", "co",
        "cua", "den", "tai", "hay", "phai", "bang",
    }
)

_WORD = re.compile(r"[0-9a-z]+")


def _fold(text: str) -> str:
    """Lowercase, diacritics removed. `phát hành` and `phat hanh` are one word.

    Vietnamese is typed both ways and searched both ways, and ADR-0048 already
    settled that question for prompt search: the folded form is what matching
    runs against. Same decision, same reason, one layer up.
    """
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    # `đ` has no combining form, so NFD leaves it whole.
    return stripped.replace("đ", "d")


def _terms(text: str) -> set[str]:
    """The distinctive words of one string."""
    return {
        token
        for token in _WORD.findall(_fold(text))
        if len(token) >= MIN_TERM_LENGTH and token not in _STOP_WORDS
    }


@dataclass(frozen=True, slots=True)
class Chunk:
    """One `##` section: the retrieval unit and the citation unit at once."""

    id: str
    document: str
    heading: str
    text: str
    terms: frozenset[str]

    @property
    def embeddable(self) -> str:
        """What gets embedded.

        Heading first, then body — the same ordering decision prompt-search
        settled by measurement when it moved to an enriched index document. A
        corpus of six documents about one product mean-pools into near-identical
        vectors unless the line that identifies the section leads.
        """
        return f"{self.heading}\n\n{self.text}"


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    """One retrieved chunk with the evidence for why it was retrieved."""

    chunk: Chunk
    score: float
    dense: float | None
    lexical: float | None


@dataclass(frozen=True, slots=True)
class RetrievalOutcome:
    """What came back and how it was found.

    `dense_ran` is separate from "there were dense scores", because those are two
    different facts and only one of them is actionable: no dense leg means the
    provider is unreachable and somebody should know; a dense leg that scored
    everything below the floor means the corpus does not cover the question.
    """

    chunks: tuple[ScoredChunk, ...]
    dense_ran: bool
    lexical_ran: bool


def _parse(path: Path) -> list[Chunk]:
    """One markdown file, split at its `##` headings.

    Text before the first `##` is the document's title block and is dropped: it
    is a heading and a sentence of framing, and a chunk made of it would win on
    generic questions and cite nothing useful.
    """
    document = path.stem
    chunks: list[Chunk] = []

    sections = re.split(r"^##\s+", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    for index, section in enumerate(sections[1:], start=1):
        heading, _, body = section.partition("\n")
        heading = heading.strip()
        body = body.strip()
        if not heading or not body:
            continue
        chunks.append(
            Chunk(
                id=f"{document}#{index}",
                document=document,
                heading=heading,
                text=body,
                # The heading is part of the searchable text: it is the question
                # the section answers, so it carries more retrieval weight per
                # word than any sentence in the body.
                terms=frozenset(_terms(f"{heading} {heading} {body}")),
            )
        )

    return chunks


@lru_cache(maxsize=1)
def load_corpus() -> tuple[Chunk, ...]:
    """Every chunk, parsed once per process.

    Cached because the corpus is a shipped artifact and cannot change without a
    deploy. `reset_corpus()` is what a test calls after writing a temporary file.
    """
    if not CORPUS_DIRECTORY.is_dir():  # pragma: no cover - the directory ships
        return ()

    chunks: list[Chunk] = []
    for path in sorted(CORPUS_DIRECTORY.glob("*.md")):
        chunks.extend(_parse(path))
    return tuple(chunks)


def reset_corpus() -> None:
    """Drop the parsed corpus and every embedding derived from it."""
    load_corpus.cache_clear()
    _vectors.clear()


def corpus_fingerprint() -> str:
    """A short digest of what is loaded, for the trace and for `/readyz` prose.

    Counts rather than a hash of the text: this value is logged, and a hash would
    be a value nobody can act on while a document count is one somebody can
    compare against the directory listing.
    """
    corpus = load_corpus()
    return f"{len({chunk.document for chunk in corpus})}docs/{len(corpus)}chunks"


# ---------------------------------------------------------------------------
# The lexical leg
# ---------------------------------------------------------------------------


def _document_frequency(corpus: tuple[Chunk, ...]) -> dict[str, int]:
    frequency: dict[str, int] = {}
    for chunk in corpus:
        for term in chunk.terms:
            frequency[term] = frequency.get(term, 0) + 1
    return frequency


def lexical_scores(question: str, corpus: tuple[Chunk, ...]) -> dict[str, float]:
    """Share of the question's IDF weight that each chunk accounts for.

    Not a copy of `prompt_search.ranking`: that module ranks a 375-document
    library where a term appearing in a quarter of it is noise, and this one ranks
    thirty chunks that are all about the same product, where "release" appearing
    in a third of them is the corpus being coherent. So there is no
    document-frequency *cap* here — only IDF weighting, which downranks the common
    term without deleting it.
    """
    terms = _terms(question)
    if not terms or not corpus:
        return {}

    total = len(corpus)
    frequency = _document_frequency(corpus)

    weights = {
        term: math.log((total + 1) / (frequency.get(term, 0) + 1)) + 1.0 for term in terms
    }
    denominator = sum(weights.values())
    if denominator <= 0:  # pragma: no cover - the `+ 1.0` floor makes this unreachable
        return {}

    scores: dict[str, float] = {}
    for chunk in corpus:
        matched = sum(weight for term, weight in weights.items() if term in chunk.terms)
        if matched > 0:
            scores[chunk.id] = matched / denominator

    return scores


# ---------------------------------------------------------------------------
# The dense leg
# ---------------------------------------------------------------------------

#: `(model, chunk_id) -> vector`. Process-local and never persisted: the corpus is
#: six files and re-embedding it costs one batch call on the first question after
#: a deploy, which is cheaper than owning a cache invalidation.
_vectors: dict[tuple[str, str], list[float]] = {}


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):  # pragma: no cover - one model produces one width
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:  # pragma: no cover - defensive
        return 0.0
    return dot / (left_norm * right_norm)


async def _embed(texts: list[str]) -> list[list[float]]:
    """One batched `/embeddings` call through the app-owned client."""
    from prope.app_agent.client import EMBEDDING_MODEL, embedding_request, get_embedding_client

    client = await get_embedding_client()
    request: dict[str, Any] = embedding_request("")
    request["input"] = texts
    request["model"] = EMBEDDING_MODEL
    response = await client.embeddings.create(**request)
    return [list(item.embedding) for item in response.data]


async def _dense_scores(question: str, corpus: tuple[Chunk, ...]) -> dict[str, float] | None:
    """Cosine per chunk, or `None` when the provider could not be reached.

    `None` and `{}` are different answers and the caller acts on the difference:
    `None` means the leg did not run, `{}` means it ran and found nothing near.
    """
    from prope.app_agent.client import EMBEDDING_MODEL

    missing = [chunk for chunk in corpus if (EMBEDDING_MODEL, chunk.id) not in _vectors]

    try:
        if missing:
            for chunk, vector in zip(
                missing, await _embed([chunk.embeddable for chunk in missing]), strict=True
            ):
                _vectors[(EMBEDDING_MODEL, chunk.id)] = vector
        query_vector = (await _embed([question]))[0]
    except Exception:
        # Fail open to the lexical leg. An unreachable embedding provider must
        # not turn "how does approval work" into an error page.
        return None

    return {
        chunk.id: _cosine(query_vector, _vectors[(EMBEDDING_MODEL, chunk.id)])
        for chunk in corpus
        if (EMBEDDING_MODEL, chunk.id) in _vectors
    }


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

#: How much a lexical hit may move a chunk the dense leg already ranked. Small,
#: for the reason prompt-search settled by measurement: the two legs disagree
#: about *ordering* far more often than about *membership*, and letting the
#: weaker signal reorder the stronger one costs more than it buys.
_LEXICAL_BONUS: Final = 0.10


async def retrieve(
    question: str,
    *,
    limit: int = 4,
    allow_dense: bool = True,
) -> RetrievalOutcome:
    """The chunks that answer one question, best first.

    Tiered rather than reciprocal-rank fused, and the tiers mean something:
    a chunk the dense leg found is above every chunk only the lexical leg found,
    because a lexical-only hit in a corpus this small is usually one shared word.
    Within the dense tier, lexical agreement is worth `_LEXICAL_BONUS` — enough to
    break a tie, never enough to invert one.

    `allow_dense=False` is how a test, or a caller that already knows the provider
    is down, skips the network without pretending it was tried.
    """
    corpus = load_corpus()
    if not corpus:  # pragma: no cover - the corpus ships with the package
        return RetrievalOutcome(chunks=(), dense_ran=False, lexical_ran=False)

    lexical = lexical_scores(question, corpus)
    dense = await _dense_scores(question, corpus) if allow_dense else None

    by_id = {chunk.id: chunk for chunk in corpus}
    scored: list[ScoredChunk] = []

    for chunk_id, chunk in by_id.items():
        dense_score = (dense or {}).get(chunk_id)
        lexical_score = lexical.get(chunk_id)

        if dense_score is not None and dense_score >= MIN_DENSE_SIMILARITY:
            bonus = _LEXICAL_BONUS if (lexical_score or 0.0) >= MIN_LEXICAL_SCORE else 0.0
            scored.append(
                ScoredChunk(
                    chunk=chunk,
                    score=1.0 + dense_score + bonus,
                    dense=dense_score,
                    lexical=lexical_score,
                )
            )
        elif lexical_score is not None and lexical_score >= MIN_LEXICAL_SCORE:
            scored.append(
                ScoredChunk(
                    chunk=chunk,
                    score=lexical_score,
                    dense=dense_score,
                    lexical=lexical_score,
                )
            )

    # `chunk.id` as the final key so that two chunks scoring identically page in
    # the same order every time. A cursor over an unstable order shows a row
    # twice, and a cited answer that reorders between two identical questions
    # reads as the system being unsure.
    scored.sort(key=lambda item: (-item.score, item.chunk.id))

    return RetrievalOutcome(
        chunks=tuple(scored[:limit]),
        dense_ran=dense is not None,
        lexical_ran=True,
    )
