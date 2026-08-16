"""Retrieval metrics, and which failure each one points at.

The mapping to `docs/materials/2-rag-pipeline.pdf` (RAGAS triad, p43-47) is
deliberate — that deck's diagnosis table only works if the numbers mean what it
says they mean:

* ``context_recall`` — did the retriever bring back the evidence at all? Low
  recall is a **retrieval** failure: chunking, embedding, or query handling.
* ``context_precision`` — is what came back relevant? Low precision with high
  recall is a **ranking** failure: the right prompt is in the list, buried.
* ``mrr`` / ``ndcg`` — where in the list. These separate "found it" from "found
  it first", which for a dialog showing three rows is the whole product.
* ``abstention`` — the adversarial half. There is no generator here to
  hallucinate, so the equivalent failure is answering a question the corpus
  cannot answer, which the import screen renders as a near-duplicate warning.

No metric here calls an LLM. `judge.py` does that, separately, because a judged
score and a labelled score failing together should be visible as two facts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median


def recall_at_k(retrieved: list[str], primary: frozenset[str] | set[str], k: int) -> float | None:
    """Share of the wanted prompts that appear in the top ``k``. ``None`` if nothing was wanted."""
    if not primary:
        return None
    top = retrieved[:k]
    return len(primary.intersection(top)) / len(primary)


def precision_at_k(retrieved: list[str], relevant: frozenset[str] | set[str], k: int) -> float | None:
    """Share of the top ``k`` that is relevant, over the positions actually filled.

    Dividing by ``len(top)`` rather than by ``k``: a query that legitimately has
    one answer and returns exactly it scores 1.0, not 0.33. Padding the
    denominator would reward returning more, which is the opposite of what a
    three-row dialog wants.
    """
    if not relevant:
        return None
    top = retrieved[:k]
    if not top:
        return 0.0
    return len(relevant.intersection(top)) / len(top)


def reciprocal_rank(retrieved: list[str], primary: frozenset[str] | set[str]) -> float | None:
    if not primary:
        return None
    for position, name in enumerate(retrieved, start=1):
        if name in primary:
            return 1.0 / position
    return 0.0


def ndcg_at_k(retrieved: list[str], gain, k: int, ideal_gains: list[float]) -> float | None:
    """Graded ranking quality against the best possible ordering.

    ``gain`` is a callable so the caller keeps ownership of the grading scheme
    (primary 3, secondary 1) rather than this module inventing a second one.
    """
    if not ideal_gains:
        return None
    actual = sum(
        gain(name) / math.log2(position + 1) for position, name in enumerate(retrieved[:k], start=1)
    )
    ideal = sum(
        value / math.log2(position + 1)
        for position, value in enumerate(sorted(ideal_gains, reverse=True)[:k], start=1)
    )
    if ideal == 0:
        return None
    return actual / ideal


@dataclass(slots=True)
class QueryOutcome:
    """One golden query, run once, scored."""

    query_id: str
    difficulty: str
    category: str
    route: str
    retrieved: list[str]
    scores: list[float]
    latency_ms: float
    recall_at_3: float | None = None
    recall_at_10: float | None = None
    precision_at_3: float | None = None
    mrr: float | None = None
    ndcg_at_10: float | None = None
    #: Adversarial only: True when the ranker correctly returned nothing.
    abstained: bool | None = None
    error: str | None = None
    matched_fields: list[list[str]] = field(default_factory=list)
    judge_scores: list[int] = field(default_factory=list)

    #: Rank 1 is a wanted prompt. Tracked as its own number because it is the
    #: one the product actually spends: the import dialog's first row, and the
    #: only result most people read.
    first_is_primary: bool = False


def _mean(values: list[float]) -> float | None:
    usable = [value for value in values if value is not None]
    return sum(usable) / len(usable) if usable else None


def aggregate(outcomes: list[QueryOutcome]) -> dict:
    """Overall and per-difficulty rollup, plus the adversarial half.

    Reported separately by difficulty because one average over easy lookups and
    cluster-discrimination queries hides the only movement worth seeing: a change
    that fixes lookups and breaks clusters looks flat.
    """
    scored = [outcome for outcome in outcomes if outcome.difficulty != "adversarial"]
    adversarial = [outcome for outcome in outcomes if outcome.difficulty == "adversarial"]

    def rollup(group: list[QueryOutcome]) -> dict:
        return {
            "queries": len(group),
            "hit_at_1": _mean([1.0 if outcome.first_is_primary else 0.0 for outcome in group]),
            "context_recall_at_3": _mean([outcome.recall_at_3 for outcome in group]),
            "context_recall_at_10": _mean([outcome.recall_at_10 for outcome in group]),
            "context_precision_at_3": _mean([outcome.precision_at_3 for outcome in group]),
            "mrr": _mean([outcome.mrr for outcome in group]),
            "ndcg_at_10": _mean([outcome.ndcg_at_10 for outcome in group]),
            "mean_results": _mean([float(len(outcome.retrieved)) for outcome in group]),
        }

    by_difficulty = {}
    for level in ("easy", "medium", "hard"):
        group = [outcome for outcome in scored if outcome.difficulty == level]
        if group:
            by_difficulty[level] = rollup(group)
    by_category = {}
    for category in sorted({outcome.category for outcome in scored}):
        group = [outcome for outcome in scored if outcome.category == category]
        by_category[category] = rollup(group)

    latencies = sorted(outcome.latency_ms for outcome in outcomes if outcome.error is None)
    judged = [score for outcome in outcomes for score in outcome.judge_scores]

    return {
        "overall": rollup(scored),
        "by_difficulty": by_difficulty,
        "by_category": by_category,
        "adversarial": {
            "queries": len(adversarial),
            "abstention_rate": _mean([1.0 if outcome.abstained else 0.0 for outcome in adversarial]),
            "mean_false_positives": _mean([float(len(outcome.retrieved)) for outcome in adversarial]),
        },
        "latency_ms": {
            "p50": median(latencies) if latencies else None,
            "p95": latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else None,
            "max": latencies[-1] if latencies else None,
        },
        "judge": {
            "pairs": len(judged),
            "mean_score": _mean([float(score) for score in judged]),
            "share_relevant": _mean([1.0 if score >= 4 else 0.0 for score in judged]),
        },
        "errors": [
            {"query_id": outcome.query_id, "error": outcome.error}
            for outcome in outcomes
            if outcome.error
        ],
    }
