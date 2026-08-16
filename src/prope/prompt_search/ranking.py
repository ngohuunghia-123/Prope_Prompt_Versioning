"""How two retrieval legs become one ordered list. Pure functions, no I/O.

Split out of `repository` because fusion is the part of search most likely to be
wrong and least likely to be caught: it has no database dependency, no upstream
call, and — until this module existed — no test that could fail when the
ordering got worse.

**What was here before, and why it had to change.** The merge was a weighted sum
of two numbers that do not live on the same scale: a cosine similarity between
whole-prompt vectors, and `matched_terms / total_terms × 0.6`. Three consequences,
all measured in `eval/result/`:

* Every term counted the same. A prompt sharing the word "engineer" with the
  query scored exactly like one sharing "kubernetes", on a corpus where hundreds
  of prompts say "engineer" and one says "kubernetes".
* The ceiling of 0.6 was doing the work an IDF weight should do — it kept
  lexical noise below vector matches by fiat rather than by evidence, and it also
  capped genuine exact-term matches, which are the case the lexical leg exists
  for (`docs/materials/2-rag-pipeline.pdf` p19: error codes, proper nouns).
* A vector match always won, however weak. On a corpus of documents that are all
  the same genre, cosine ranges over about 0.25–0.50 for everything, so "always
  wins" meant "the lexical leg was decorative".

Two fusions are implemented and one is chosen by measurement, not by taste:
:func:`reciprocal_rank_fusion` (deck p20, the standard) and :func:`alpha_fusion`
(the same slide's alternative). `PROMPT_SEARCH_RANKER` selects.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

__all__ = [
    "ALPHA",
    "LEXICAL_FLOOR",
    "RANKER",
    "RRF_K",
    "VECTOR_FLOOR",
    "FusedResult",
    "alpha_fusion",
    "fuse",
    "lexical_scores",
    "reciprocal_rank_fusion",
]

#: Which fusion runs, and **the default is not the textbook one.**
#:
#: `docs/materials/2-rag-pipeline.pdf` p20 recommends RRF, and measured against
#: this golden set RRF ranked *worse* than the scheme it replaced: MRR 0.83
#: against 0.89, and recall@3 on cluster-discrimination queries 0.43 against
#: 0.78 (`eval/result/*-C-corroborated.json` against `*-baseline.json`).
#:
#: The reason is a property of RRF rather than a bug in it. RRF rewards
#: agreement between legs, which is right when the legs are comparably good. Here
#: they are not: on a corpus where every document is an LLM instruction, the
#: vector leg alone answers 89% of queries at rank 1 and the lexical leg is a
#: specialist for exact identifiers. Agreement-boosting let a prompt the vector
#: leg ranked fifth overtake the one it ranked first, because the fifth also
#: shared two ordinary words with the query.
#:
#: So `blend` is the default: the vector ordering leads, lexical evidence adjusts
#: it within a bounded band, and lexical-only candidates follow. `rrf` and
#: `alpha` remain selectable — they are how the claim above stays falsifiable.
RANKER = os.environ.get("PROMPT_SEARCH_RANKER", "blend")

#: How far lexical agreement may move a prompt inside the vector ordering.
#:
#: A bound, not a weight: 0.08 of cosine. Cosines on a single-genre corpus
#: occupy roughly 0.25-0.50, so this can reorder prompts the vector leg scored
#: within eight points of each other — where that leg is genuinely undecided —
#: and cannot touch a clear winner. It is the `+0.05` keyword bonus this module
#: always had, applied to a signal that now means something.
LEXICAL_BONUS = float(os.environ.get("PROMPT_SEARCH_LEXICAL_BONUS", "0.08"))

#: The RRF constant from Cormack et al., and the value every implementation of
#: this ships with. Large enough that the top of one list cannot bulldoze the
#: other: rank 1 contributes 1/61 and rank 5 contributes 1/65, so agreement
#: across legs matters more than depth within one.
RRF_K = int(os.environ.get("PROMPT_SEARCH_RRF_K", "60"))

#: How much of an alpha-fused score the vector leg carries.
ALPHA = float(os.environ.get("PROMPT_SEARCH_ALPHA", "0.7"))

#: Cosine below this is not evidence of anything.
#:
#: Unchanged in value from the floor it replaces (`MIN_SEARCH_SIMILARITY`) and
#: unchanged in purpose: cosine distance answers for every row in the corpus, so
#: without a floor a query matching nothing returns the least-unrelated prompts
#: and the import dialog presents them as near-duplicates. What changed is that
#: it now gates *the vector leg's candidacy* rather than the final blended
#: number, which is what let a lexical-only hit inherit a threshold calibrated
#: for cosines.
VECTOR_FLOOR = float(os.environ.get("PROMPT_SEARCH_MIN_SIMILARITY", "0.25"))

#: The share of the query's *distinctive* weight a prompt must match lexically.
#:
#: Expressed in IDF mass rather than in term count: matching one rare term is
#: worth more than matching three common ones, and this floor is what makes that
#: statement operative instead of decorative.
LEXICAL_FLOOR = float(os.environ.get("PROMPT_SEARCH_MIN_LEXICAL", "0.15"))


@dataclass(frozen=True, slots=True)
class FusedResult:
    prompt_id: str
    #: Which leg found it: 0 when the vector leg did, 1 when only the lexical leg
    #: did. The ordering key before anything else, so that a prompt matched on
    #: meaning always precedes one matched on wording — the property that keeps
    #: "the index is an accelerator, not a gate" from turning into "an unindexed
    #: prompt can displace an indexed one".
    tier: int
    #: The number the interface shows, and it is **a cosine or nothing**.
    #:
    #: The import dialog renders this as "N% similar". A lexical score is a share
    #: of the query's distinctive terms, not a distance between meanings, and a
    #: prompt that matched every word of a short query scores 1.0 on it — which
    #: that dialog would have rendered as *100% similar* for a prompt nobody has
    #: ever indexed. `None` is the honest answer there, and `matched_fields`
    #: carries what did fire.
    similarity: float | None
    fused: float
    vector_similarity: float | None
    lexical_similarity: float | None
    matched_fields: tuple[str, ...]


#: A term matching more than this share of visible prompts is not a search term.
#:
#: **Measured, and it was a false-positive machine.** ADR-0048 matches by
#: substring over a diacritic-folded document, so the Vietnamese for "beef noodle
#: soup" folds to `pho` and `bo` and those match *phone*, *robot*, *about* — a
#: recipe query retrieved ten prompts, and abstention on the adversarial set fell
#: from 100% to 20% (`eval/result/*-A-ranking.json`). IDF alone does not save it:
#: the weights are a share of one query's mass, so a query made entirely of
#: worthless terms still distributes 100% of its mass among them.
#:
#: A term this common cannot separate two documents whatever weight it carries,
#: which is what makes dropping it different from down-weighting it. The corpus
#: decides which words those are; nothing is hard-coded per language.
MAX_DOCUMENT_FREQUENCY_SHARE = float(os.environ.get("PROMPT_SEARCH_MAX_DF_SHARE", "0.25"))

#: Rare enough to anchor a match on its own.
#:
#: One in twenty prompts. Measured, the gap is wide and lands either side of it:
#: the terms that carry a real question here are `kubernetes` (2%), `postgres`
#: (1%), `remembers` (0.5%), `hardening` (3%); the ones that carried the false
#: positives are `last` (20%), `weight` (16%), `cable` (11%), `pho` (10%, and
#: only because diacritic folding turns `phở` into a substring of *phone*).
SPECIFIC_DOCUMENT_FREQUENCY_SHARE = float(os.environ.get("PROMPT_SEARCH_SPECIFIC_DF_SHARE", "0.05"))

#: An anchor has to be a word, not a fragment.
#:
#: Rarity alone is not enough when matching is `LIKE '%term%'` over folded text.
#: `phở` folds to `pho`; `gia` — from `gia truyền` — matched one prompt in two
#: hundred, which made it rare enough to anchor a recipe query onto a creative
#: writing prompt that happens to contain `…gia…` inside a longer word. Three
#: characters landing inside one document is an accident of substring matching;
#: four or more is a term. Short terms still SEARCH — `sql`, `api`, `rag` — and a
#: query consisting of one of them is exempt from anchoring entirely. What they
#: may no longer do is vouch for a match on their own.
MIN_ANCHOR_LENGTH = int(os.environ.get("PROMPT_SEARCH_MIN_ANCHOR_LENGTH", "4"))

#: Below this many visible prompts, document frequency is not evidence.
#:
#: Twenty is where "one in four prompts" stops being an accident of a tiny
#: sample. Under it every rule that reads a share is switched off rather than
#: scaled, because a threshold applied to five observations is a coin toss
#: wearing a decimal point.
MIN_CORPUS_FOR_FREQUENCY = int(os.environ.get("PROMPT_SEARCH_MIN_CORPUS_FOR_DF", "20"))

#: How much a lexical rank counts against a vector rank in the fusion.
#:
#: Plain RRF treats the legs as equals, and on this corpus that measured worse
#: than the ranker it replaced: a lexical rank-1 tied with a vector rank-1, so
#: term overlap displaced genuine semantic matches on precisely the queries —
#: cluster discrimination — where meaning is the only thing that separates two
#: documents. Half weight keeps the lexical leg able to promote a prompt the
#: vector leg ranked poorly or never saw, while a vector top-two still outranks a
#: lexical top-one. It is the old ceiling's intent, expressed where it belongs:
#: on the evidence, not on the score.
LEXICAL_WEIGHT = float(os.environ.get("PROMPT_SEARCH_LEXICAL_WEIGHT", "0.5"))


def lexical_scores(
    term_hits: dict[str, set[str]],
    *,
    corpus_size: int,
    require_anchor: bool = True,
    max_document_frequency_share: float = MAX_DOCUMENT_FREQUENCY_SHARE,
) -> dict[str, float]:
    """Per-prompt lexical relevance in ``[0, 1]``, weighted by inverse document frequency.

    ``term_hits`` maps each probed term to the prompts it matched — which the
    lexical leg already has, because it ran one indexed query per term. The
    document frequency is therefore free: it is the size of each of those sets,
    and computing IDF from it costs no additional query.

    Smoothed as ``log((N + 1) / (df + 1))`` so that a term matching every visible
    prompt still divides by something. A prompt's score is the share of the
    query's total IDF mass it accounts for, which is 1.0 only for a prompt
    matching every distinctive term in the query.

    Every rule here that reads a *share* of the corpus is suspended below
    :data:`MIN_CORPUS_FOR_FREQUENCY` prompts, where the shares are artefacts of
    the sample size rather than facts about language.
    """
    if not term_hits or corpus_size <= 0:
        return {}

    # **Document frequency means nothing in a small workspace.** A share is a
    # share of what exists: with four prompts, a term matching two of them is in
    # 50% of the corpus and the cap deletes it — so a brand-new workspace, which
    # is every workspace on its first day, got an empty answer to a query naming
    # a prompt it holds. Caught by an integration test over four rows, invisible
    # in a 200-prompt evaluation, which is a fair description of what each is for.
    if corpus_size >= MIN_CORPUS_FOR_FREQUENCY:
        discriminating = {
            term: hits
            for term, hits in term_hits.items()
            if len(hits) / corpus_size <= max_document_frequency_share
        }
    else:
        discriminating = dict(term_hits)

    # A query whose every term is too common is left with nothing on purpose. It
    # was tempting to fall back to ranking by the dropped terms rather than
    # answering nothing — but that would mean the cap could never drop the LAST
    # term, which is precisely the adversarial case it was measured to stop: one
    # ordinary word matching half the corpus, returned as a hundred suggestions.
    if not discriminating:
        return {}

    # Textbook smoothed IDF, and **without the customary `+ 1` floor**. That
    # constant exists to keep a term appearing in every document from weighing
    # zero; :data:`MAX_DOCUMENT_FREQUENCY_SHARE` has already removed those, so all
    # it does here is compress the range — with it, a term in 1% of the corpus
    # outweighs one in 20% by 1.95x; without it, by 2.6x. The whole point of this
    # weight is to separate those two.
    weights = {
        term: math.log((corpus_size + 1) / (len(hits) + 1))
        for term, hits in discriminating.items()
    }
    total = sum(weights.values())
    if total <= 0:
        # **Every surviving term is in every prompt, so IDF has nothing to say.**
        # `log((N + 1) / (df + 1))` is exactly zero when `df == N`, and dropping
        # the customary `+ 1` floor — which is worth 2.6x against 1.95x in
        # separating a 1% term from a 20% one — is what lets that reach here. In
        # a workspace of one prompt EVERY term has `df == N`, so the leg weighed
        # the query at zero and returned nothing at all: search found no match
        # for a phrase printed in the only prompt the workspace held.
        #
        # Falling back to uniform weights says the honest thing. When rarity
        # cannot separate two documents, the number of query terms a prompt
        # matches is the only signal left, and ranking by it is what the caller
        # asked for.
        weights = dict.fromkeys(discriminating, 1.0)
        total = float(len(weights))

    scores: dict[str, float] = {}
    matches: dict[str, int] = {}
    for term, hits in discriminating.items():
        share = weights[term] / total
        for prompt_id in hits:
            scores[prompt_id] = scores.get(prompt_id, 0.0) + share
            matches[prompt_id] = matches.get(prompt_id, 0) + 1

    # **A match needs corroboration and an anchor.**
    #
    # The share above is relative to the query, so a question with three usable
    # terms hands a third of its mass to each and a prompt containing one of them
    # clears any floor. Corroboration alone does not fix it either: measured on
    # the adversarial set, "what time does the last train from Utrecht to
    # Amsterdam leave on Sunday" retrieved seven prompts at a *perfect* 1.0,
    # because `last` and `leave` are ordinary words that co-occur constantly and
    # `utrecht`, `amsterdam` and `sunday` — the words that make it that question —
    # matched nothing at all.
    #
    # So a candidate must also match one term the corpus finds SPECIFIC. That is
    # the difference between the queries that should answer and the ones that
    # should not: `kubernetes` in 2% of prompts, `postgres` in 1%, `remembers` in
    # 0.5% — against `last` in 20% and `weight` in 16%.
    #
    # A query left with one usable term is exempt from both rules. There is
    # nothing to corroborate with, and that case is the lexical leg's whole reason
    # to exist: `SQL`, `GDPR`, an error code, an identifier. Somebody who typed
    # one word has asked for exactly it.
    #
    # **`require_anchor` is off for the keyword path, and the asymmetry is the
    # point.** The two callers pay different prices for a loose match. The
    # duplicate check speaks in the product's voice — a row there asserts *this
    # may already exist*, and being wrong sends somebody to read a prompt that has
    # nothing to do with theirs. A keyword box asserts nothing: the person typed
    # the words, reads the titles, and picks. Measured, requiring an anchor on
    # both cost the keyword path a fifth of its recall (rec@3 0.64 to 0.58),
    # because a conceptual question — "teach me by asking questions instead of
    # giving me the answer" — contains no rare word to anchor on and its answer
    # was dropped outright rather than ranked low.
    if len(discriminating) == 1:
        return scores

    admitted = {prompt_id for prompt_id, count in matches.items() if count >= 2}
    if require_anchor:
        # The rarity half of the anchor test is a share too, and in a small
        # workspace it is unsatisfiable rather than strict: with four prompts the
        # rarest possible term is in 25% of them, never the 5% an anchor needs, so
        # requiring it would refuse every multi-word duplicate check until the
        # workspace held twenty prompts. Below that, length is the only half of
        # the test the corpus can actually answer, and it keeps the fragment rule
        # (`gia`, `pho`) doing its job.
        specific = {
            term
            for term, hits in discriminating.items()
            if len(term) >= MIN_ANCHOR_LENGTH
            and (
                corpus_size < MIN_CORPUS_FOR_FREQUENCY
                or len(hits) / corpus_size <= SPECIFIC_DOCUMENT_FREQUENCY_SHARE
            )
        }
        admitted &= {prompt_id for term in specific for prompt_id in discriminating[term]}
    return {prompt_id: score for prompt_id, score in scores.items() if prompt_id in admitted}


def reciprocal_rank_fusion(
    ranked_legs: list[list[str]],
    *,
    k: int = RRF_K,
    weights: list[float] | None = None,
) -> dict[str, float]:
    """``Σ 1/(k + rank)`` over each leg's ordering. Scale-free by construction.

    The property that matters here is what it does NOT need: any belief that a
    cosine of 0.42 and a lexical share of 0.42 mean comparable things. Only the
    orderings are used, so the two legs can disagree about magnitude — which they
    always do — without one silently dominating.
    """
    fused: dict[str, float] = {}
    leg_weights = weights or [1.0] * len(ranked_legs)
    for leg, weight in zip(ranked_legs, leg_weights, strict=False):
        for rank, prompt_id in enumerate(leg, start=1):
            fused[prompt_id] = fused.get(prompt_id, 0.0) + weight / (k + rank)
    return fused


def alpha_fusion(
    vector: dict[str, float],
    lexical: dict[str, float],
    *,
    alpha: float = ALPHA,
) -> dict[str, float]:
    """``α·cosine + (1−α)·lexical``, both already in ``[0, 1]``.

    Kept alongside RRF because it preserves an interpretable magnitude — the
    fused number is still "how similar", which a screen showing a percentage
    needs — where RRF only preserves an order.
    """
    keys = set(vector) | set(lexical)
    return {
        key: alpha * vector.get(key, 0.0) + (1.0 - alpha) * lexical.get(key, 0.0) for key in keys
    }


def fuse(
    *,
    vector: dict[str, float],
    lexical: dict[str, float],
    keyword_matches: frozenset[str] | set[str] = frozenset(),
    ranker: str = RANKER,
    vector_floor: float = VECTOR_FLOOR,
    lexical_floor: float = LEXICAL_FLOOR,
) -> list[FusedResult]:
    """One ordered list from two legs, with each leg gated on its own scale.

    **Gating before fusing, not after.** A candidate enters because its own leg
    says so — cosine over :data:`VECTOR_FLOOR`, or IDF share over
    :data:`LEXICAL_FLOOR`. Filtering the blended number instead is what let a
    lexical-only match be judged against a threshold calibrated for cosine
    distance, and it is why the floor had to be set low enough to admit noise.

    **Ties break on the stronger leg score, then on ``prompt_id``.** RRF is
    scale-free, which is its virtue and, at the top of the list, its blind spot:
    a candidate ranked first by the vector leg and one ranked first by the
    lexical leg receive exactly ``1/(k+1)`` each, and something has to order
    them. Deciding by magnitude compares two scales RRF deliberately refuses to
    compare — but it only ever fires between candidates RRF has already declared
    equal, and the alternative is letting the alphabet rank the first row of a
    three-row dialog. ``prompt_id`` remains the final key so that two runs over
    the same corpus produce the same page; a cursor over an unstable order pages
    the same prompt twice.
    """
    vector_candidates = {
        prompt_id: score for prompt_id, score in vector.items() if score >= vector_floor
    }
    lexical_candidates = {
        prompt_id: score for prompt_id, score in lexical.items() if score >= lexical_floor
    }

    if ranker == "alpha":
        fused = alpha_fusion(vector_candidates, lexical_candidates)
    elif ranker == "rrf":
        vector_order = sorted(vector_candidates, key=lambda key: (-vector_candidates[key], key))
        lexical_order = sorted(lexical_candidates, key=lambda key: (-lexical_candidates[key], key))
        fused = reciprocal_rank_fusion(
            [vector_order, lexical_order], weights=[1.0, LEXICAL_WEIGHT]
        )
    else:
        fused = {
            prompt_id: vector_candidates.get(prompt_id, 0.0)
            + LEXICAL_BONUS * lexical_candidates.get(prompt_id, 0.0)
            for prompt_id in set(vector_candidates) | set(lexical_candidates)
        }

    results: list[FusedResult] = []
    for prompt_id, score in fused.items():
        vector_score = vector_candidates.get(prompt_id)
        lexical_score = lexical_candidates.get(prompt_id)
        fields: list[str] = []
        if vector_score is not None:
            fields.append("semantic")
        if prompt_id in keyword_matches:
            fields.append("keyword")
        if lexical_score is not None:
            fields.append("lexical")
        results.append(
            FusedResult(
                prompt_id=prompt_id,
                tier=0 if vector_score is not None else 1,
                similarity=vector_score,
                fused=score,
                vector_similarity=vector_score,
                lexical_similarity=lexical_score,
                matched_fields=tuple(fields),
            )
        )

    results.sort(
        key=lambda result: (
            result.tier,
            -result.fused,
            -max(result.vector_similarity or 0.0, result.lexical_similarity or 0.0),
            result.prompt_id,
        )
    )
    return results
