"""Scoring an extraction without asking a model whether it was any good.

**Why there is no LLM judge here.** Three reasons, in order of how much they
cost to get wrong. A judge would have to be shown the prompt body to grade the
terms drawn from it, which puts corporate prompt text on a second upstream call
under A-020. A judge drifts — its own model version changes underneath the
metric, so a score dip becomes ambiguous between "extraction got worse" and
"judge got stricter", and an ambiguous quality metric is worse than none. And a
judge costs a call per extraction, which is a doubling of the one place Prope
spends its own money.

Everything below is arithmetic over the extraction and the text it came from. It
runs in microseconds, it cannot drift, and it is therefore cheap enough to run on
**every live extraction** and not only in a nightly job — which is what makes
`prompt_search_extraction_quality` a continuous-eval signal rather than a
periodic report.

**What it can and cannot see.** It measures whether the extraction is complete,
grounded in the source, and tidy. It cannot tell you whether `refund triage` was
a better keyword than `customer complaint`. That judgement belongs to the golden
set in `datasets/`, where a human wrote the expected terms down once.
"""

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prope.prompt_search.domain import (
    MAX_KEYWORDS,
    MAX_TERM_CHARACTERS,
    MAX_TOPICS,
    ExtractedMetadata,
    ExtractedVariations,
)

__all__ = [
    "ExtractionScore",
    "PASS_THRESHOLD",
    "extraction_metric",
    "fold",
    "golden_path",
    "load_examples",
    "score_extraction",
]

#: The lock file asks for 5-15 keywords and 2-5 topics. Scoring treats those as
#: the target band rather than a hard rule, because 4 excellent keywords beat 5
#: padded ones and the instruction says so.
MIN_KEYWORDS = 5
MIN_TOPICS = 2
MIN_VARIATIONS = 2

#: Below this an extraction is worth a human's attention. It is the alert
#: threshold in `deploy/prometheus/rules/prompt_search.rules.yml` and the
#: pass/fail line the DSPy optimizer bootstraps against, and those two must be
#: the same number or the optimizer is compiling for a bar production does not
#: use.
PASS_THRESHOLD = 0.70

#: 0.45 completeness / 0.35 groundedness / 0.20 hygiene.
#:
#: Groundedness is weighted heavily for its size because it is the only component
#: that catches the failure that actually hurts: an extraction full of plausible
#: invented terms scores perfectly on counts and tidiness, and sends every future
#: search to the wrong prompt. Completeness outweighs it only because an empty
#: extraction is both more common and more obviously broken.
WEIGHT_COMPLETENESS = 0.45
WEIGHT_GROUNDEDNESS = 0.35
WEIGHT_HYGIENE = 0.20


def fold(text: str) -> str:
    """Casefold and strip diacritics, so `Kiểm` and `kiem` compare equal.

    Vietnamese is half of this module's input (ADR-0053) and a model that writes
    `kiem tra` where the body says `kiểm tra` has grounded its term correctly.
    Same normalisation idea as ADR-0048's search folding; done locally because
    that one lives in a Postgres trigger and this runs in Python.
    """
    decomposed = unicodedata.normalize("NFD", text.casefold())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    # `đ` is a distinct letter, not a `d` with a combining mark, so NFD leaves it
    # alone and it has to be folded by hand.
    return unicodedata.normalize("NFC", stripped).replace("đ", "d")


@dataclass(frozen=True, slots=True)
class ExtractionScore:
    """The three components and their weighted total. All values are 0.0 to 1.0."""

    completeness: float
    groundedness: float
    hygiene: float

    @property
    def total(self) -> float:
        return round(
            self.completeness * WEIGHT_COMPLETENESS
            + self.groundedness * WEIGHT_GROUNDEDNESS
            + self.hygiene * WEIGHT_HYGIENE,
            4,
        )

    @property
    def passed(self) -> bool:
        return self.total >= PASS_THRESHOLD


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _completeness(metadata: ExtractedMetadata) -> float:
    """Did the extraction produce the fields an index row needs?

    Five equally-weighted checks. `entities` is NOT one of them: a prompt that
    names no product or system correctly returns an empty list, and scoring it
    would reward inventing one — which is precisely what groundedness exists to
    punish.
    """
    checks = (
        len(metadata.keywords) >= MIN_KEYWORDS,
        len(metadata.topics) >= MIN_TOPICS,
        len(metadata.variations.en) >= MIN_VARIATIONS,
        len(metadata.variations.vi) >= MIN_VARIATIONS,
        bool(metadata.language),
    )
    return _ratio(sum(checks), len(checks))


def _groundedness(metadata: ExtractedMetadata, *, source: str) -> float:
    """What fraction of the keywords and entities actually occur in the source?

    Substring matching over folded text, not token equality, so that `refund` is
    grounded by `refunds` and `kiem tra` by `kiểm tra`. Multi-word terms must
    appear as a phrase; that is deliberate, because `customer support` grounded by
    a stray `customer` and a stray `support` two paragraphs apart is exactly the
    invented-but-plausible term this component is looking for.

    **`variations` and `topics` are excluded on purpose.** A variation is a
    paraphrase for a searcher whose words differ from the author's, and a topic is
    a category broader than anything written down. Requiring either to appear in
    the source would score the two most useful fields as failures.
    """
    terms = metadata.keywords + metadata.entities
    if not terms:
        return 0.0

    haystack = fold(source)
    grounded = sum(1 for term in terms if fold(term) in haystack)
    return _ratio(grounded, len(terms))


def _hygiene(metadata: ExtractedMetadata) -> float:
    """Is it shaped like an index, or like prose somebody pasted in?"""
    keywords = metadata.keywords
    topics = metadata.topics
    every_term = keywords + topics + metadata.entities

    keyword_set = {fold(term) for term in keywords}
    topic_set = {fold(term) for term in topics}

    checks = (
        # Keywords are search terms, not sentences.
        all(len(term) <= MAX_TERM_CHARACTERS for term in every_term),
        # A topic that merely repeats a keyword adds no recall.
        not (keyword_set & topic_set),
        # The instruction asks for lowercase keywords.
        all(term == term.lower() for term in keywords),
        # Caps respected, so nothing was padded to hit a number.
        len(keywords) <= MAX_KEYWORDS and len(topics) <= MAX_TOPICS,
        # The column admits `en` and `vi` and nothing else.
        set(metadata.language) <= {"en", "vi"},
        # Variations paraphrase the intent; an empty string is not a paraphrase.
        all(term.strip() for term in metadata.variations.en + metadata.variations.vi),
    )
    return _ratio(sum(checks), len(checks))


def score_extraction(
    metadata: ExtractedMetadata,
    *,
    title: str,
    purpose: str,
    body: str,
) -> ExtractionScore:
    """Grade one extraction against the text it was drawn from."""
    return ExtractionScore(
        completeness=_completeness(metadata),
        groundedness=_groundedness(metadata, source=f"{title}\n{purpose}\n{body}"),
        hygiene=_hygiene(metadata),
    )


# ---------------------------------------------------------------------------
# The DSPy side: the same score, shaped as an optimizer metric and a golden set.
# ---------------------------------------------------------------------------


def golden_path() -> Path:
    return Path(__file__).parent / "datasets" / "extraction_golden.jsonl"


def _metadata_from_prediction(prediction: Any) -> ExtractedMetadata:
    """Late import so that scoring a live extraction never pulls DSPy in."""
    from prope.prompt_search.agent.dspy_program import metadata_of

    return metadata_of(prediction)


def _expected_recall(expected: dict, metadata: ExtractedMetadata) -> float:
    """How many of the hand-written expected keywords did the model find?

    Only `expected_keywords` is graded, and only for RECALL. An extraction that
    finds every term a human thought of plus three good ones of its own is
    better, not worse, so precision against a hand-written list would penalise
    the behaviour the golden set exists to encourage.
    """
    wanted = [fold(term) for term in expected.get("expected_keywords", [])]
    if not wanted:
        return 1.0

    produced = " | ".join(fold(term) for term in metadata.keywords)
    found = sum(1 for term in wanted if term in produced)
    return _ratio(found, len(wanted))


def extraction_metric(example: Any, prediction: Any, trace: Any = None) -> float | bool:
    """The metric DSPy's `Evaluate` and optimizers call.

    Returns a float normally. When `trace` is set — which is how DSPy signals that
    it is deciding whether to KEEP a bootstrapped demonstration — it returns a
    bool instead, because a demonstration is either good enough to teach from or
    it is not.
    """
    try:
        metadata = _metadata_from_prediction(prediction)
    except Exception:
        return False if trace is not None else 0.0

    deterministic = score_extraction(
        metadata,
        title=getattr(example, "title", ""),
        purpose=getattr(example, "purpose", ""),
        body=getattr(example, "body", ""),
    ).total

    expected = getattr(example, "expected", None) or {}
    recall = _expected_recall(expected, metadata)

    # Two thirds the live signal, one third the human's answer key. The live
    # signal dominates so that the optimizer improves the thing production
    # measures, rather than overfitting to twelve hand-written rows.
    score = round(deterministic * (2 / 3) + recall * (1 / 3), 4)

    if trace is not None:
        return score >= PASS_THRESHOLD
    return score


def load_examples(path: Path | None = None) -> list[Any]:
    """The golden set as `dspy.Example`s. Imports DSPy, so call it from a CLI."""
    import dspy

    source = path or golden_path()
    examples: list[Any] = []

    for line in source.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        record = json.loads(line)
        examples.append(
            dspy.Example(
                title=record["title"],
                purpose=record["purpose"],
                body=record["body"],
                expected=record.get("expected", {}),
            ).with_inputs("title", "purpose", "body")
        )

    return examples


def evaluate(program: Any, *, examples: list[Any] | None = None, num_threads: int = 4) -> float:
    """Average metric over the golden set. Used by `optimize.py` on both sides of a compile."""
    import dspy

    dataset = examples if examples is not None else load_examples()
    evaluator = dspy.Evaluate(
        devset=dataset,
        metric=extraction_metric,
        num_threads=num_threads,
        display_progress=True,
    )
    result = evaluator(program)
    return float(getattr(result, "score", result))


def empty_metadata() -> ExtractedMetadata:
    """The zero value, for a failed extraction that still has to be scored."""
    return ExtractedMetadata(
        keywords=(),
        topics=(),
        entities=(),
        variations=ExtractedVariations(),
        language=(),
    )
