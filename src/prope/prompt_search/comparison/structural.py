"""The free rung of the funnel: ~20 retrieved candidates down to the ~5 worth paying for.

Nothing here calls a model, embeds anything, or touches the database. It reads
two bodies that are already in memory and ranks on the one signal the retrieval
leg cannot use: **which canonical block the words came from.**

**Why the block matters more than the words.** A prompt library is one genre.
Mean-pooled into a single vector, the shared genre dominates and the two lines
that identify a prompt contribute a few percent — ``system`` + ``examples`` +
``constraints`` are the longest and most generic blocks, and they drown
``instructions``, which carries the job. That is the false positives,
mechanically explained. Here the blocks are separate fields, so ``instructions``
can be weighted as what it is.

**IDF is computed over the candidate pool, not over the corpus.** Twenty
documents is far too few for a stable corpus statistic and that is not what it is
being asked for: within *this* pool, a term every candidate shares is the genre
and a term two of them share is the job. A word like "assistant" earns almost
nothing here without anybody having to maintain a list saying so — almost, and
not exactly nothing, because the weight is smoothed (see :func:`_idf`).

**This stage may reject nothing on its own.** It orders; the adjudicator
decides. A candidate that never enters can never be confirmed *or* rejected, so
the mouth of the funnel owes recall and precision moved downstream — the
inversion is the point, and it is why there is no floor in this module.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

from prope.canonical_prompt import BLOCK_ORDER, blocks_of, unwrap_verbatim
from prope.prompt_composition import required_variables
from prope.prompt_search.domain import MIN_TERM_LENGTH, STOP_WORDS

__all__ = [
    "BLOCK_WEIGHTS",
    "SHARED_TERMS_SHOWN",
    "BlockOverlap",
    "PromptFacts",
    "ScoredCandidate",
    "facts_of",
    "rank_candidates",
]

#: How much each block contributes to the structural score.
#:
#: ``instructions`` carries the task — the job itself — and ``output_format``
#: carries the output contract, which is short and highly discriminating and is
#: exactly what a whole-document vector loses. ``system`` is persona: weak signal
#: at high volume. ``examples`` is near-noise for this purpose and is scored at
#: zero rather than dropped, so that the intent is written down where the next
#: reader can disagree with it.
BLOCK_WEIGHTS: dict[str, float] = {
    "instructions": 1.0,
    "output_format": 0.6,
    "context": 0.4,
    "constraints": 0.4,
    "system": 0.15,
    "examples": 0.0,
}

#: Weight of a shared ``{{variable}}`` name relative to a shared instruction term.
#:
#: A **signal, never a gate.** A true duplicate can rename its variables, so
#: filtering on them drops exactly the pair being looked for; two prompts that
#: both read ``{{customer_tier}}`` are nonetheless unusually likely to be about
#: the same thing, because a variable name is a word the author chose for a slot
#: rather than for prose.
VARIABLE_WEIGHT = 0.5

#: Weight of a shared agent-extracted keyword, topic or entity. Available only
#: for indexed candidates, so it may not dominate: a prompt the worker has not
#: reached yet would otherwise rank below one that says less.
METADATA_WEIGHT = 0.25

#: How many shared terms one block reports.
#:
#: **The score answers "how much" and these answer "which", and only the second
#: one can be argued with.** A reader told two prompts overlap by 0.71 can
#: neither agree nor disagree; a reader shown that the shared words are *refund*,
#: *escalate* and *tier* can say "yes, that is the same job" or "no, those are
#: the only three words we have in common" — and the second reading is exactly
#: the false positive this redesign exists to make visible.
#:
#: Eight because they are ranked by IDF weight: the ninth-most-distinctive shared
#: word in a block has already stopped being evidence, and a wall of chips reads
#: as noise however good the ranking behind it is.
SHARED_TERMS_SHOWN = 8

#: How hard to penalise a candidate for carrying the incoming prompt's material
#: among a great deal of unrelated material. **Ranking only** — it never touches
#: `match`, which stays a statement about coverage of the incoming body.
#:
#: **Why it had to exist.** Containment divides by the *incoming* prompt's term
#: mass and nothing else, so a candidate is rewarded for every incoming term it
#: happens to contain and is never charged for its own size. Over a real corpus
#: that stops being a ranking and becomes a length sort: measured on the ten
#: labelled triplets, the four longest documents in a twenty-candidate pool took
#: four of the top five places for *every* incoming prompt regardless of subject
#: — a 20 k-character prompt about removing AI tells from prose outranked
#: `clinical_assistant` for an incoming clinical prompt, and outranked
#: `legal_analyst` for an incoming legal one. Both true duplicates fell outside
#: the five that get judged, and nothing downstream can recover a candidate the
#: adjudicator never sees.
#:
#: So the ranking multiplies containment by the share of the CANDIDATE's own mass
#: that the overlap accounts for, raised to this power. At `0.0` the behaviour is
#: exactly what it was. Above `0.0` a candidate that carries the incoming
#: prompt's material *and little else* is preferred to one that buries it.
#:
#: **It is an exponent rather than a second term because superset candidates must
#: survive it.** `candidate_broader` is a verdict the set has a name for, and a
#: symmetric measure — Jaccard, Dice, cosine — would demote a genuine superset
#: for its extra length exactly as if the extra were noise. A fractional exponent
#: bends the ranking without flattening that distinction: a prompt that really
#: does the incoming job plus more still concentrates most of its mass on the
#: shared material, while an unrelated 20 k document does not.
FOCUS_EXPONENT = float(os.environ.get("PROMPT_SEARCH_FOCUS_EXPONENT", "0.35"))


def _terms(text: str) -> frozenset[str]:
    """Distinct content tokens of one block.

    Set semantics, not counts: a block that repeats "refund" eleven times is
    still one prompt about refunds, and term frequency on a document this short
    measures verbosity.
    """
    tokens: set[str] = set()
    word: list[str] = []
    for character in f"{text} ":
        if character.isalnum():
            word.append(character.lower())
            continue
        if word:
            token = "".join(word)
            word = []
            if len(token) >= MIN_TERM_LENGTH and token not in STOP_WORDS and not token.isdigit():
                tokens.add(token)
    return frozenset(tokens)


@dataclass(frozen=True, slots=True)
class PromptFacts:
    """Everything the free stages read about one prompt. Assembled once, reused.

    ``prompt_id`` is empty for the incoming body, which has not been registered
    and may never be.
    """

    prompt_id: str
    #: Canonical block text, keyed by tag. Empty when the body is not canonical
    #: XML — which is normal on the import screen, where the text has not been
    #: through the converter yet.
    blocks: dict[str, str] = field(default_factory=dict)
    #: The whole body, used as the fallback comparison surface when there are no
    #: blocks. Never re-parsed; kept so nothing downstream needs the raw text.
    fallback: str = ""
    variables: frozenset[str] = frozenset()
    metadata_terms: frozenset[str] = frozenset()

    @property
    def is_canonical(self) -> bool:
        return bool(self.blocks)

    def block_terms(self, tag: str) -> frozenset[str]:
        return _terms(self.blocks.get(tag, ""))

    @property
    def fallback_terms(self) -> frozenset[str]:
        return _terms(self.fallback)

    @property
    def comparison_terms(self) -> frozenset[str]:
        """Every content term of this prompt, however it is stored.

        The surface used when one side has canonical blocks and the other does
        not — the import screen's normal case, where the incoming text has not
        been through the converter yet. Comparing a raw paste against only the
        candidate's `fallback` (which is empty for a canonical body) scored every
        pair at zero, which read as *nothing resembles this* for exactly the
        prompts the screen exists to find.
        """
        if self.blocks:
            return _terms(" ".join(self.blocks.values()))
        return self.fallback_terms


def facts_of(
    body: str,
    *,
    prompt_id: str = "",
    keywords: tuple[str, ...] = (),
    topics: tuple[str, ...] = (),
    entities: tuple[str, ...] = (),
) -> PromptFacts:
    """One body, parsed into everything the free stages need.

    The extracted metadata is folded into a single term set rather than kept in
    three: the distinction between a keyword and a topic matters to the search
    index and does not matter to *do these two prompts overlap*.
    """
    blocks = blocks_of(body)
    metadata_terms: set[str] = set()
    for term in (*keywords, *topics, *entities):
        metadata_terms |= _terms(term)
    return PromptFacts(
        prompt_id=prompt_id,
        blocks=blocks,
        # `unwrap_verbatim` because a body stored whole has no named blocks and
        # therefore reads through this fallback. Its two markers are Prope's,
        # not the author's, and leaving them in would let `<>` be a term that a
        # verbatim prompt shares with every other verbatim prompt.
        fallback=unwrap_verbatim(body) if not blocks else "",
        variables=frozenset(required_variables(body)),
        metadata_terms=frozenset(metadata_terms),
    )


@dataclass(frozen=True, slots=True)
class BlockOverlap:
    """What one canonical block shares with its counterpart, and how much.

    ``shared_terms`` are words out of two prompt bodies, so they are content in
    a way the rest of this package's output is not. They are admissible on the
    one path that carries them — the import dialog, which is already sent
    ``body_preview``, two thousand characters of the same body — and inadmissible
    everywhere else: **never a log field, never a metric label, never a
    `Finding.param`.** ADR-0030 and A-046 both hold; this is not an exception to
    them, it is a value that stays inside the response that already carries more.
    """

    block: str
    #: Share of the incoming block's distinctive weight the candidate carries.
    #: A containment, not a cosine, and deliberately not called "similarity".
    score: float
    shared_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """One candidate with its free score and the parts that made it up."""

    facts: PromptFacts
    score: float
    #: The same evidence as ``score``, divided by what this pair could have
    #: scored. **The only number here that may be shown as a percentage**, and
    #: the one the display floor is applied to.
    #:
    #: ``score`` is a sum of weighted containments and its ceiling moves with the
    #: incoming prompt: a body with all five weighted blocks and variables can
    #: reach 3.3, a bare paste 1.0. A floor on that would mean five different
    #: things for five different prompts and 0.9 would read as *"90%"* while
    #: meaning *"a third of what was available"*. Dividing by the attainable
    #: total makes it a weighted average of containments — the share of this
    #: prompt's distinctive weight the candidate carries — which is a sentence a
    #: person can check.
    #:
    #: **The ranking is unchanged by it.** The divisor is a property of the
    #: incoming body alone, so it is the same for every candidate in a run and
    #: cannot reorder them.
    match: float = 0.0
    #: The share of the candidate's own distinctive weight that the overlap
    #: accounts for. Ordering only — `rank_candidates` sorts on
    #: ``score * focus ** FOCUS_EXPONENT`` — and never rendered, because it is a
    #: fact about the OTHER prompt's bulk rather than about the pair.
    #: Diagnostic: a twin ranked below an unrelated document almost always shows
    #: a healthy `score` and a collapsed `focus`.
    focus: float = 1.0
    #: Per-block overlap, in `BLOCK_ORDER`. The diagnosis of a bad ranking, and
    #: — since the terms travel with it — the explanation shown to a reader.
    blocks: tuple[BlockOverlap, ...] = ()
    variable_overlap: float = 0.0
    metadata_overlap: float = 0.0
    #: `{{variable}}` names both prompts read. A signal, never a gate: a true
    #: duplicate can rename its variables, and filtering on these would drop
    #: exactly the pair being looked for.
    shared_variables: tuple[str, ...] = ()
    #: How many `{{variables}}` the incoming prompt requires — the denominator of
    #: `variable_overlap`, carried because **zero and zero-of-zero are different
    #: facts.** A prompt that takes no variables and a prompt that shares none of
    #: its three both leave `variable_overlap` at 0.0, and an interface that
    #: cannot tell them apart reports "no variables in common" for a prompt that
    #: has no variables to have in common.
    variables_required: int = 0

    @property
    def block_scores(self) -> dict[str, float]:
        """The scores alone, for callers that only rank."""
        return {overlap.block: overlap.score for overlap in self.blocks}


def _idf(pool: list[frozenset[str]]) -> dict[str, float]:
    """Inverse document frequency over the candidate pool, including the incoming body.

    **BM25's smoothed form, and the smoothing is load-bearing rather than
    conventional.** Plain ``log(N / df)`` sends a term present in every document
    to exactly zero, which is the right instinct — a word every candidate shares
    is the genre, not the job — but it also sends EVERY term to zero when the
    pool holds two documents, because a shared term is then in all of them. The
    funnel is specified for a pool of twenty and must not silently score every
    pair at zero when a workspace has one candidate.

    So ``log(1 + (N - df + 0.5) / (df + 0.5))``: a term in one of twenty carries
    about a hundred times the weight of a term in all twenty, and a term in both
    of two still carries something. Coarse either way, which is correct — the
    only distinction it is asked to draw is *genre* against *job*.
    """
    total = len(pool)
    if total == 0:
        return {}
    document_frequency: dict[str, int] = {}
    for terms in pool:
        for term in terms:
            document_frequency[term] = document_frequency.get(term, 0) + 1
    return {
        term: math.log(1.0 + (total - count + 0.5) / (count + 0.5))
        for term, count in document_frequency.items()
    }


def _weighted_containment(
    incoming: frozenset[str],
    candidate: frozenset[str],
    idf: dict[str, float],
) -> tuple[float, tuple[str, ...]]:
    """How much of the incoming block the candidate carries, and which words say so.

    **Containment rather than Jaccard, and the asymmetry is deliberate.** The
    question is whether the candidate covers what the incoming prompt asks for;
    a candidate that says everything the incoming one says *and more* is a
    superset, which is a real relation the verdict set has a name for, and
    Jaccard would penalise it for its extra length exactly as if it were noise.

    The terms come back ranked by the same IDF weight that produced the score, so
    the words a reader is shown are the words that actually moved it — not the
    longest, not the first, and not the ones that happen to look impressive.
    """
    if not incoming:
        return 0.0, ()
    mass = sum(idf.get(term, 0.0) for term in incoming)
    if mass <= 0.0:
        return 0.0, ()
    overlap = incoming & candidate
    shared = sum(idf.get(term, 0.0) for term in overlap)
    ranked = sorted(overlap, key=lambda term: (-idf.get(term, 0.0), term))
    return shared / mass, tuple(ranked[:SHARED_TERMS_SHOWN])


def _focus(
    incoming: frozenset[str],
    candidate: frozenset[str],
    idf: dict[str, float],
) -> float:
    """How much of the CANDIDATE's own weight the overlap accounts for, 0..1.

    The other direction of :func:`_weighted_containment`, and the half that was
    missing. Containment answers *does this candidate carry what I asked for*;
    this answers *and is that most of what it carries, or a footnote inside
    something else*. A long document scores well on the first for almost any
    input and badly on the second unless it is genuinely about the same thing.

    Used for ordering only. It is deliberately **not** folded into ``score`` or
    ``match``: those are shown to a person as coverage percentages, and a number
    that silently mixed in "…discounted because the other prompt is long" would
    be unreadable as either.
    """
    if not incoming or not candidate:
        return 0.0
    mass = sum(idf.get(term, 0.0) for term in candidate)
    if mass <= 0.0:
        return 0.0
    shared = sum(idf.get(term, 0.0) for term in incoming & candidate)
    return shared / mass


def rank_candidates(
    incoming: PromptFacts,
    candidates: list[PromptFacts],
    *,
    limit: int,
) -> list[ScoredCandidate]:
    """Order candidates by free structural evidence and keep the top ``limit``.

    Ties break on ``prompt_id`` so that two runs over the same corpus produce
    the same five candidates — an adjudication whose input set shuffles between
    runs is an adjudication nobody can reproduce a complaint about.
    """
    if not candidates:
        return []

    # One IDF table per block tag, over this pool only. The incoming body is part
    # of the pool: a term it shares with every candidate is genre there too.
    idf_by_block: dict[str, dict[str, float]] = {}
    for tag in BLOCK_ORDER:
        pool = [incoming.block_terms(tag)] + [candidate.block_terms(tag) for candidate in candidates]
        pool = [terms for terms in pool if terms]
        if pool:
            idf_by_block[tag] = _idf(pool)

    # The whole-text pool uses `comparison_terms`, not `fallback`: when the
    # incoming body is a raw paste the candidates are still canonical, and an
    # IDF table built from their empty `fallback` would weight every term at
    # nothing.
    fallback_pool = [incoming.comparison_terms] + [
        candidate.comparison_terms for candidate in candidates
    ]
    fallback_idf = _idf([terms for terms in fallback_pool if terms])

    metadata_pool = [incoming.metadata_terms] + [
        candidate.metadata_terms for candidate in candidates
    ]
    metadata_idf = _idf([terms for terms in metadata_pool if terms])

    # A non-canonical body on either side has no blocks to compare, so the whole
    # text stands in for `instructions` at that block's weight. The import
    # screen's pasted text is the normal case for this, not the exception, and
    # reporting "no overlap" for it would make the free stage useless exactly
    # where it is needed.
    comparable_blocks = [
        tag
        for tag in BLOCK_ORDER
        if BLOCK_WEIGHTS.get(tag, 0.0) > 0.0 and incoming.block_terms(tag)
    ]

    # What a perfect candidate could score against THIS incoming body: the
    # weights of the blocks it actually has, plus the two signals it actually
    # carries. Hoisted out of the loop because it is a property of the incoming
    # prompt and not of any candidate — which is the same reason dividing by it
    # cannot change the order.
    attainable = (
        sum(BLOCK_WEIGHTS[tag] for tag in comparable_blocks)
        if comparable_blocks
        else BLOCK_WEIGHTS["instructions"]
    )
    if incoming.variables:
        attainable += VARIABLE_WEIGHT
    if incoming.metadata_terms:
        attainable += METADATA_WEIGHT

    scored: list[ScoredCandidate] = []
    for candidate in candidates:
        blocks: list[BlockOverlap] = []
        total = 0.0

        if comparable_blocks:
            for tag in comparable_blocks:
                weight = BLOCK_WEIGHTS[tag]
                overlap, terms = _weighted_containment(
                    incoming.block_terms(tag),
                    candidate.block_terms(tag) or candidate.comparison_terms,
                    idf_by_block.get(tag, {}),
                )
                blocks.append(BlockOverlap(block=tag, score=overlap, shared_terms=terms))
                total += weight * overlap
        else:
            overlap, terms = _weighted_containment(
                incoming.comparison_terms,
                candidate.comparison_terms,
                fallback_idf,
            )
            # `whole_text` rather than a block tag, so a reader is never told the
            # instructions matched when what actually matched was a paste nobody
            # has parsed yet.
            blocks.append(BlockOverlap(block="whole_text", score=overlap, shared_terms=terms))
            total += BLOCK_WEIGHTS["instructions"] * overlap

        shared_variables = tuple(sorted(incoming.variables & candidate.variables))
        variable_overlap = 0.0
        if incoming.variables:
            variable_overlap = len(shared_variables) / len(incoming.variables)
            total += VARIABLE_WEIGHT * variable_overlap

        metadata_overlap, _ = _weighted_containment(
            incoming.metadata_terms, candidate.metadata_terms, metadata_idf
        )
        total += METADATA_WEIGHT * metadata_overlap

        scored.append(
            ScoredCandidate(
                facts=candidate,
                score=total,
                match=total / attainable if attainable > 0.0 else 0.0,
                focus=_focus(
                    incoming.comparison_terms, candidate.comparison_terms, fallback_idf
                ),
                blocks=tuple(blocks),
                variable_overlap=variable_overlap,
                metadata_overlap=metadata_overlap,
                shared_variables=shared_variables,
                variables_required=len(incoming.variables),
            )
        )

    # Ordered by containment discounted for the candidate's own bulk, so that a
    # long document cannot buy a top-five place with incidental overlap. `score`
    # itself is left alone: it is the evidence a reader is shown, and the ranking
    # is a separate question from what the number means.
    scored.sort(
        key=lambda item: (
            -(item.score * (item.focus**FOCUS_EXPONENT)),
            item.facts.prompt_id,
        )
    )
    return scored[: max(0, limit)]
