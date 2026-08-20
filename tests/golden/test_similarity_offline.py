"""The ten labelled triplets, run through every free rung of the funnel.

**What this measures and what it cannot.** The adjudicator is stubbed to the
label the fixture declares, so nothing here says whether a model would judge
these pairs correctly — `make golden-live` answers that. What is exercised is
everything the model does not decide: whether the free pre-filter carries the
twin into the five candidates that get judged at all, whether a contract check
demotes a verdict it should not, and whether the display floor then hides a
duplicate the funnel already found. Those three are pure functions, they are
where the reported failure actually happened, and they cost nothing to run — so
this is part of `make test` rather than something opted into.

**Why a twenty-candidate pool.** `structural._idf` is *pool-relative*: the term
weights are computed over the incoming body plus whatever candidates it is shown
beside, with a BM25-smoothed document frequency. Scoring a twin against two
candidates would give term weights nothing like production's twenty, and a
`match_score` measured that way could not be used to set a threshold. So each
triplet is scored inside a pool of `RETRIEVAL_LIMIT` prompts drawn from the same
library, exactly as retrieval would hand it over.

The separation numbers — twin `match_score` against decoy `match_score` — are
the point of the file. A floor is defensible only in the gap between those two
distributions, and if they overlap then no single lexical threshold is
defensible at any value.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest

from prope.prompt_search.comparison.domain import Severity, Verdict
from prope.prompt_search.comparison.pipeline import (
    ADJUDICATION_LIMIT,
    RETRIEVAL_LIMIT,
    CandidateInput,
    compare,
)
from prope.prompt_search.comparison.structural import facts_of, rank_candidates
from prope.prompt_search.comparison.verdict import MATCH_FLOOR

# `eval/` is a namespace directory next to `src/`, not an installed package, and
# pytest puts `tests/` on the path rather than the repo root. Importing the
# fixture therefore needs the root added explicitly — the alternative is copying
# thirty labels into this file, where the live lane could not read them.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.retrieval.corpus import load_corpus  # noqa: E402
from eval.retrieval.similarity import TRIPLETS, Triplet, required_stems, twin_text  # noqa: E402

#: Enough prompts to fill a realistic pool for every triplet without loading all
#: 375 — the required stems, plus fill. Conversion is the slow part, so this is
#: cached for the session.
CORPUS_SIZE = 60

#: Scored with the floor wide open. The floor's effect is computed afterwards
#: from the recorded `match_score`, which is the only way to see how far below it
#: a hidden duplicate sat — `summarise` reports the count and not the distance.
NO_FLOOR = 0.0


@lru_cache(maxsize=1)
def _corpus():
    return load_corpus(CORPUS_SIZE, required=tuple(sorted(required_stems())))


@dataclass(frozen=True, slots=True)
class Outcome:
    """One candidate's journey through the funnel, and where it stopped."""

    stem: str
    reached_adjudicator: bool
    verdict: str | None
    match_score: float
    hard_findings: tuple[str, ...]
    listed: bool

    def attribution(self, expected_verdict: str) -> str:
        if not self.reached_adjudicator:
            return "cut_by_prefilter"
        if self.verdict is None:
            return "dropped_as_unrelated"
        if self.verdict != expected_verdict:
            return "demoted_by_contract" if self.hard_findings else "verdict_wrong"
        return "shown"


async def _run(triplet: Triplet, *, floor: float = NO_FLOOR) -> dict[str, Outcome]:
    """Drive one triplet through `compare` with the adjudicator held to the label."""
    items = {item.stem: item for item in _corpus()}
    labelled = {pair.stem: pair for pair in triplet.pairs}

    incoming_body = (
        twin_text(triplet) if triplet.written else items[triplet.incoming].raw
    )

    # The two labelled prompts, then library fill up to the retrieval width. The
    # incoming prompt's own file is excluded when it came from the corpus: it is
    # the thing being pasted, not something the workspace already holds.
    excluded = set(labelled) | {triplet.incoming}
    pool = [items[stem] for stem in labelled]
    pool += [item for item in _corpus() if item.stem not in excluded][
        : RETRIEVAL_LIMIT - len(labelled)
    ]

    candidates = [
        CandidateInput(
            prompt_id=item.stem,  # the stem IS the identifier here; no database
            title=item.stem,
            body=item.body,
            keywords=(),
            topics=(),
            entities=(),
        )
        for item in pool
    ]

    ranked = rank_candidates(
        facts_of(incoming_body),
        [candidate.resolved_facts() for candidate in candidates],
        limit=ADJUDICATION_LIMIT,
    )
    judged_stems = [scored.facts.prompt_id for scored in ranked]

    async def adjudicate(_incoming, briefs):
        # `title` is the stem, so the stub answers with the fixture's own label
        # and nothing about a real model's behaviour leaks into this lane.
        return {
            label: (labelled[title].relation if title in labelled else "different", ())
            for label, title, _ in briefs
        }

    sheet = await compare(
        incoming_body=incoming_body,
        candidates=candidates,
        adjudicate=adjudicate,
        match_floor=floor,
    )
    shown = {candidate.prompt_id: candidate for candidate in sheet.candidates}
    scores = {scored.facts.prompt_id: scored.match for scored in ranked}

    outcomes: dict[str, Outcome] = {}
    for stem in labelled:
        evidence = shown.get(stem)
        outcomes[stem] = Outcome(
            stem=stem,
            reached_adjudicator=stem in judged_stems,
            verdict=evidence.verdict.value if evidence else None,
            match_score=scores.get(stem, 0.0),
            hard_findings=tuple(
                finding.code
                for finding in (evidence.findings if evidence else ())
                if finding.severity is Severity.HARD
            ),
            listed=evidence is not None,
        )
    return outcomes


@pytest.mark.golden
@pytest.mark.parametrize("triplet", TRIPLETS, ids=lambda t: t.id)
async def test_the_twin_survives_every_free_rung(triplet: Triplet) -> None:
    """A prompt doing the same job reaches the sheet with the verdict its label says.

    This is the assertion the product failed. Everything upstream of the
    adjudicator is free and deterministic, so a twin lost here was lost by
    ranking or by a contract check — never by a model having a bad day.
    """
    outcomes = await _run(triplet)
    twin = outcomes[triplet.twin.stem]

    assert twin.reached_adjudicator, (
        f"{triplet.id}: the free pre-filter cut the twin before anything judged it. "
        f"{triplet.twin.stem} did not make the top {ADJUDICATION_LIMIT} of "
        f"{RETRIEVAL_LIMIT}. No threshold downstream can recover it."
    )
    assert twin.verdict == triplet.twin.verdict, (
        f"{triplet.id}: expected {triplet.twin.verdict}, got {twin.verdict}. "
        f"Hard findings: {twin.hard_findings or 'none'}. Rule: {triplet.twin.why}"
    )


@pytest.mark.golden
@pytest.mark.parametrize("triplet", TRIPLETS, ids=lambda t: t.id)
async def test_the_decoy_is_never_a_duplicate(triplet: Triplet) -> None:
    """The near-miss is not resolved as `same`, and is never pre-selected.

    The load-bearing half. Any threshold loose enough to admit the twins also
    admits most of a single-genre library, so a run where all ten twins pass and
    the decoys pass with them has measured nothing.
    """
    outcomes = await _run(triplet)
    decoy = outcomes[triplet.decoy.stem]

    assert decoy.verdict != Verdict.SAME.value, (
        f"{triplet.id}: {triplet.decoy.stem} resolved as a duplicate. Rule: {triplet.decoy.why}"
    )
    # A decoy the pre-filter never carried into the judged five is a BETTER
    # outcome than one shown as context, not a worse one, so absence satisfies
    # this. The labelled relation is only binding on a decoy that got judged —
    # asserting it unconditionally would have made the funnel's quietest correct
    # answer look like a failure.
    if decoy.reached_adjudicator:
        assert decoy.verdict == triplet.decoy.verdict, (
            f"{triplet.id}: expected {triplet.decoy.verdict}, got {decoy.verdict}. "
            f"Rule: {triplet.decoy.why}"
        )


@pytest.mark.golden
async def test_no_duplicate_is_recommended_while_measurement_is_missing() -> None:
    """Not one triplet recommends discarding the incoming prompt.

    `USE_EXISTING_REQUIRES_MEASUREMENT` is the gate that keeps §1.5's one
    unrecoverable error unreachable while §2.1 and §2.3 are unbuilt. Ten
    confirmed duplicates is exactly the input that would expose a regression in
    it, so the set asserts it rather than trusting the constant.
    """
    for triplet in TRIPLETS:
        items = {item.stem: item for item in _corpus()}
        labelled = {pair.stem: pair for pair in triplet.pairs}
        excluded = set(labelled) | {triplet.incoming}
        pool = [items[stem] for stem in labelled]
        pool += [item for item in _corpus() if item.stem not in excluded][
            : RETRIEVAL_LIMIT - len(labelled)
        ]
        candidates = [
            CandidateInput(prompt_id=i.stem, title=i.stem, body=i.body) for i in pool
        ]

        async def adjudicate(_incoming, briefs, _labelled=labelled):
            return {
                label: (_labelled[title].relation if title in _labelled else "different", ())
                for label, title, _ in briefs
            }

        sheet = await compare(
            incoming_body=twin_text(triplet) if triplet.written else items[triplet.incoming].raw,
            candidates=candidates,
            adjudicate=adjudicate,
            match_floor=NO_FLOOR,
        )
        assert sheet.recommended_action.value != "use_existing", (
            f"{triplet.id} recommended discarding the incoming prompt"
        )


@pytest.mark.golden
@pytest.mark.parametrize("triplet", TRIPLETS, ids=lambda t: t.id)
async def test_the_production_floor_cannot_hide_a_confirmed_duplicate(
    triplet: Triplet,
) -> None:
    """At the shipped `MATCH_FLOOR`, every confirmed twin still reaches the screen.

    The regression guard for the reported bug. All ten twins score below 0.90 —
    the highest reaches 0.472 — so before `_survives_floor` existed this
    assertion failed ten times out of ten: the funnel identified a duplicate and
    the display discarded it. Parametrised rather than aggregated so a
    reintroduction names the topic it broke.
    """
    outcomes = await _run(triplet, floor=MATCH_FLOOR)
    twin = outcomes[triplet.twin.stem]

    assert twin.listed, (
        f"{triplet.id}: {triplet.twin.stem} was judged {twin.verdict} and then hidden by the "
        f"{MATCH_FLOOR:.0%} floor at a match of {twin.match_score:.1%}. A wording threshold "
        "must not overrule the adjudicator."
    )


@pytest.mark.golden
async def test_the_separation_report_is_written() -> None:
    """Write the attribution table and the two `match_score` distributions.

    The artifact the tuning is argued from, and the reason the floor stops
    governing `same`. Two numbers carry the argument:

    ``hidden_at_0_90`` — how many confirmed duplicates the shipped threshold
    would have hidden. It is 10 of 10.

    ``gap`` — the distance between the worst twin and the best decoy. It is
    **negative**, which is the finding: the two populations overlap, so no value
    of a lexical floor separates a duplicate from a near-miss, and the ones
    listed in ``inverted`` score *below* their own decoy. That is reported rather
    than asserted against, because it is a property of measuring wording overlap
    at all and not a defect any threshold can repair.
    """
    rows = []
    for triplet in TRIPLETS:
        outcomes = await _run(triplet)
        twin = outcomes[triplet.twin.stem]
        decoy = outcomes[triplet.decoy.stem]
        rows.append(
            {
                "id": triplet.id,
                "topic": triplet.topic,
                "written_twin": triplet.written,
                "twin": {
                    "stem": twin.stem,
                    "match_score": round(twin.match_score, 4),
                    "verdict": twin.verdict,
                    "attribution": twin.attribution(triplet.twin.verdict),
                },
                "decoy": {
                    "stem": decoy.stem,
                    "match_score": round(decoy.match_score, 4),
                    "verdict": decoy.verdict,
                    "attribution": decoy.attribution(triplet.decoy.verdict),
                },
            }
        )

    twins = [row["twin"]["match_score"] for row in rows]
    decoys = [row["decoy"]["match_score"] for row in rows]
    report = {
        "triplets": rows,
        "separation": {
            "twin_min": min(twins),
            "twin_median": sorted(twins)[len(twins) // 2],
            "twin_max": max(twins),
            "decoy_min": min(decoys),
            "decoy_median": sorted(decoys)[len(decoys) // 2],
            "decoy_max": max(decoys),
            # Positive means one threshold separates the two sets cleanly. Zero
            # or negative means no single value of MATCH_FLOOR can, at which
            # point the floor is the wrong instrument rather than the wrong
            # number.
            "gap": round(min(twins) - max(decoys), 4),
            "hidden_at_0_90": sum(1 for score in twins if score < 0.90),
            "hidden_at_shipped_floor": sum(1 for score in twins if score < MATCH_FLOOR),
            "inverted": [
                row["id"]
                for row in rows
                if row["twin"]["match_score"] <= row["decoy"]["match_score"]
            ],
        },
    }
    destination = _ROOT / "eval" / "result" / "similarity-offline.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["separation"], indent=2))

    # The one thing that would make the free rung useless rather than merely
    # imprecise: if no twin outscored its decoy anywhere, wording overlap would
    # carry no signal at all and the pre-filter should be deleted, not tuned.
    assert len(report["separation"]["inverted"]) < len(TRIPLETS), (
        "not one twin outscored its decoy — the structural stage carries no signal"
    )
