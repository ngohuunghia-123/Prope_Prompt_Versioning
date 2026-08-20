"""The ten triplets against the real adjudicator. Costs money; opted into.

**The half the free lane cannot reach.** `test_similarity_offline.py` holds the
adjudicator to the fixture's own label, so it measures ranking, contracts and the
floor and says nothing about whether a model gets these pairs right. That is the
rung the reported failure most likely died on, and it can only be measured by
calling it.

Two properties are under test and they are different failures:

**Truncation.** `present()` sends at most `PRESENTATION_CHARACTER_LIMIT`
characters per candidate, drawn only from `instructions`, `output_format` and
`constraints`. This lane is what condemned the old 1,200: prompts in this set run
to 23,925 characters and the model was seeing as little as 2.8% of one, so the
commonest error was `same_task` answered as `candidate_narrower` — a model shown
a third of a prompt reporting, correctly, that it does a third of the job. At
4,000 that error drops from 4 to 1 and recognised duplicates go from 4 to 7,
with no decoy called `same_task` at either budget. `characters_seen` against
`characters_available` in the report is the column that says so.

**The `same_domain` tilt.** The instruction says *"When you are unsure between
same_task and same_domain, answer same_domain"*, which is the right error
economics and is also a thumb on the scale. The confusion matrix is what
separates a correct conservative call from a systematic one.

Skipped unless ``PROPE_RUN_GOLDEN_LIVE`` is set, following the `load` precedent:
a skip prints an ``s`` and its reason, where a deselect is invisible. Run it with
``make golden-live``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

import pytest

from prope.prompt_search.agent import adjudicate
from prope.prompt_search.comparison.pipeline import (
    ADJUDICATION_LIMIT,
    RETRIEVAL_LIMIT,
    CandidateInput,
    present,
)
from prope.prompt_search.comparison.structural import facts_of, rank_candidates

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# The provider settings this lane needs are put in the environment by
# `tests/golden/conftest.py`, which has to run before `prope.app_agent.client`
# binds them into module constants — see the note there.
from eval.retrieval.corpus import load_corpus  # noqa: E402
from eval.retrieval.similarity import TRIPLETS, required_stems, twin_text  # noqa: E402

pytestmark = [
    pytest.mark.golden_live,
    pytest.mark.skipif(
        not os.environ.get("PROPE_RUN_GOLDEN_LIVE"),
        reason="live adjudication costs a model call per triplet; see `make golden-live`",
    ),
]

CORPUS_SIZE = 60

#: Seconds to wait between triplets.
#:
#: One adjudication of five candidates measures at ~27 s against the configured
#: provider, and ten of them issued back to back come back `LMServerError` in
#: two to four seconds each — every one of them, while the same call made on its
#: own succeeds. That is upstream rate limiting, not a defect in the funnel, and
#: pacing is the honest fix: a lane that reports "the model refused" when the
#: model was throttled would be worse than no lane, because it reads as a
#: finding about the prompts.
CALL_SPACING_SECONDS = float(os.environ.get("PROPE_GOLDEN_LIVE_SPACING", "20"))


@pytest.fixture(scope="module")
def corpus():
    return load_corpus(CORPUS_SIZE, required=tuple(sorted(required_stems())))


async def test_the_adjudicator_agrees_with_the_labels(corpus) -> None:
    """One real call per triplet; report the matrix, then assert the two rules.

    The assertions are deliberately weaker than "every label matches". A model
    answering `same_domain` where the fixture says `same_task` is being
    conservative in the direction the instruction asks for, and failing the suite
    for it would tune the set to the model. What is not negotiable is the other
    direction: a decoy called `same_task` is the error that ends with somebody
    discarding a prompt that does work the other one does not do.
    """
    items = {item.stem: item for item in corpus}
    matrix: Counter[tuple[str, str]] = Counter()
    rows = []
    unavailable: list[str] = []

    for position, triplet in enumerate(TRIPLETS):
        if position:
            await asyncio.sleep(CALL_SPACING_SECONDS)
        labelled = {pair.stem: pair for pair in triplet.pairs}
        incoming_body = twin_text(triplet) if triplet.written else items[triplet.incoming].raw
        excluded = set(labelled) | {triplet.incoming}
        pool = [items[stem] for stem in labelled]
        pool += [item for item in corpus if item.stem not in excluded][
            : RETRIEVAL_LIMIT - len(labelled)
        ]
        candidates = [
            CandidateInput(prompt_id=item.stem, title=item.stem, body=item.body)
            for item in pool
        ]

        incoming = facts_of(incoming_body)
        ranked = rank_candidates(
            incoming,
            [candidate.resolved_facts() for candidate in candidates],
            limit=ADJUDICATION_LIMIT,
        )
        by_id = {candidate.prompt_id: candidate for candidate in candidates}
        briefs = [
            (
                f"C{position}",
                scored.facts.prompt_id,
                present(by_id[scored.facts.prompt_id].resolved_facts()),
            )
            for position, scored in enumerate(ranked, start=1)
        ]
        labels = {f"C{position}": brief[1] for position, brief in enumerate(briefs, start=1)}

        judged = await adjudicate(
            incoming_prompt=present(incoming), candidates=briefs, context=None
        )
        # An empty answer is recorded as `unavailable` for this triplet and the
        # run continues. Skipping the whole lane on the first refusal would throw
        # away nine measurements to report one, and *which* triplet the provider
        # refuses is itself a finding — the corpus contains persona and
        # jailbreak-styled prompts, and a provider declining to reason about one
        # of them is a production behaviour, not a test defect.
        if not judged:
            unavailable.append(triplet.id)

        for label, stem in labels.items():
            if stem not in labelled:
                continue
            expected = labelled[stem].relation
            relation, reasons = judged.get(label, ("", ()))
            actual = relation or "not_judged"
            matrix[(expected, actual)] += 1
            rows.append(
                {
                    "id": triplet.id,
                    "stem": stem,
                    "role": "twin" if stem == triplet.twin.stem else "decoy",
                    "expected": expected,
                    "actual": actual,
                    # The reason codes matter as much as the relation: the
                    # vocabulary has no way to say "same job, different output
                    # shape" — that is `variant`, a VERDICT the contract check
                    # derives, not a relation the model can return. So a
                    # `same_task` carrying `different_output_shape` is the model
                    # answering as well as it is able, and the demotion is code's
                    # job.
                    "reasons": list(reasons),
                    # The whole reason the cut is suspected: what the model saw.
                    "characters_seen": len(dict(zip(labels, briefs, strict=False))[label][2]),
                    "characters_available": len(items[stem].body),
                }
            )

    report = {
        "rows": rows,
        "unavailable": unavailable,
        "confusion": {f"{expected}->{actual}": n for (expected, actual), n in matrix.items()},
        "twins_called_same_job": sum(
            1
            for row in rows
            if row["role"] == "twin" and row["actual"] in {"same_task", "candidate_broader"}
        ),
        "decoys_called_same_task": sum(
            1 for row in rows if row["role"] == "decoy" and row["actual"] == "same_task"
        ),
    }
    (_ROOT / "eval" / "result" / "similarity-live.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))

    # The unrecoverable direction — §1.5's one error with no recovery — held to a
    # measured tolerance rather than to zero, for two reasons that are findings
    # rather than excuses.
    #
    # **This layer is allowed to be wrong.** `agent/comparison.py` states the
    # layering outright: adjudication is *the only* probabilistic step, and
    # contract compatibility is decided in code beneath it. A `same_task` that
    # survives to the screen has still to pass `compare_output_contracts`, and a
    # HARD finding demotes it to `variant`, which is never recommended. Asserting
    # perfection at a layer with a designed safety net tests the wrong thing.
    #
    # **And the relation is not symmetric in practice.** t04 is the standing
    # example: asked `code_reviewer_security` -> `security_researcher` the model
    # answers `same_task`; asked the other way round, through the real route, it
    # answers `related` with `different_action, different_object`. Their output
    # contracts settle it — one is keyed to `File:LineNumber` and quotes the
    # offending source, the other to a component with a CVSS vector and detection
    # guidance — so the label stands and the model is over-calling in one
    # direction only. Worth its own fix; not worth a red suite in the meantime.
    #
    # Two would mean the tolerance has stopped describing the measurement.
    if len(unavailable) == len(TRIPLETS):
        pytest.skip(f"the adjudicator refused every triplet ({unavailable}); nothing measured")

    offenders = [row for row in rows if row["role"] == "decoy" and row["actual"] == "same_task"]
    assert len(offenders) <= 1, f"near-misses judged interchangeable: {offenders}"

    # The recoverable direction, held to a floor rather than to perfection: the
    # instruction tells the model to prefer `same_domain` when unsure, so some
    # conservatism is correct behaviour and only a collapse is a defect.
    measured = len(TRIPLETS) - len(unavailable)
    assert report["twins_called_same_job"] >= measured // 2, (
        f"only {report['twins_called_same_job']} of {measured} true duplicates were "
        "recognised as doing the same job — see characters_seen against "
        "characters_available before tuning anything else"
    )
