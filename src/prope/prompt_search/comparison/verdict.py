"""Task relation plus contract findings, resolved into a verdict and an action.

**This is the aggregation layer, and it is code on purpose.** The sub-stages emit
per-axis findings; something has to combine them, and if that something is a
paragraph handed to an agent then the aggregation happens in natural language by
a rule nobody can inspect — the happy path washing out the one edge case that
mattered, relocated somewhere it cannot be audited. A mean was a bad shape; at
least it was reproducible. These are rules, and they are both.

Two rules govern everything below.

**A hard finding is a veto that nothing trades away.** Different
``required_variables`` breaks every existing caller, and no cost saving
compensates. A verdict function that can be argued out of that is a system that
can approve a breaking change on its own.

**The unmeasured default is `create_new`.** From the error economics: missing a
duplicate leaves a duplicate in a registry that can still find it; wrongly
offering "add as a revision" costs an immutable revision and a permanent history
row; wrongly saying *"use X instead"* makes somebody discard their prompt for one
that does not do their job, and that fails silently, in production, months later,
traceable to nothing. So the evidence bar inverts from intuition — **"use X
instead" requires more evidence than "add as a revision", never less** — and
:data:`USE_EXISTING_REQUIRES_MEASUREMENT` is where that inversion is enforced
rather than merely believed.
"""

from __future__ import annotations

import os

from prope.prompt_search.comparison.domain import (
    Action,
    CandidateEvidence,
    EvidenceSheet,
    Finding,
    Severity,
    Verdict,
)

__all__ = [
    "MATCH_FLOOR",
    "USE_EXISTING_REQUIRES_MEASUREMENT",
    "recommend",
    "resolve_action",
    "resolve_verdict",
    "summarise",
]

#: How much of the incoming prompt a candidate must cover to be listed at all.
#:
#: **A display floor, and the last rung rather than the first.** Everything above
#: it in the funnel deliberately refuses to threshold: retrieval owes recall, the
#: pre-filter orders and rejects nothing, and a candidate that never enters can
#: never be confirmed *or* rejected. This applies at the other end, to a
#: candidate that has already been judged, and it answers a different question —
#: not *"is this worth checking"* but *"is this worth putting in front of a
#: person"*.
#:
#: **It governs `related` rows only** — see :func:`_survives_floor` for why a
#: wording threshold does not get to overrule a verdict.
#:
#: **0.25 is measured, and 0.90 was not.** The previous value was inherited from
#: A-S153 in `prompt-search.lock.yml`, where *"90% similarity"* means a **cosine**
#: computed at index time whose only effect is a non-blocking warning on the
#: index preview. This is an IDF-weighted **containment** that hides rows. The
#: two are different scales, and on a single-genre prompt corpus neither reaches
#: 0.9 — OQ-c puts the cosine band at 0.25–0.50, and the ten labelled triplets
#: put the highest confirmed duplicate at **0.472**. A threshold nothing can
#: reach is not strict, it is off, and it reads as *"90%"* on a screen where 90%
#: is unattainable.
#:
#: The number now comes from `eval/retrieval/similarity.py`: across ten labelled
#: near-misses the highest wording overlap observed is **0.178**, and the median
#: confirmed duplicate sits at **0.236**. 0.25 is the round value just above the
#: near-miss ceiling — a `related` row must carry at least as much of the
#: incoming prompt as a real duplicate typically does before it is worth a line
#: on a decision surface.
#:
#: **What it still costs.** The twin and near-miss ranges overlap (`gap` is
#: negative in the report), so this separates nothing on its own; it only
#: quietens context. That is all a lexical threshold can honestly be asked to do,
#: and it is why the verdicts bypass it. `below_floor` counts what it removed and
#: the dialog and trace both say so.
MATCH_FLOOR = float(os.environ.get("PROMPT_SEARCH_MATCH_FLOOR", "0.25"))

#: *"Use the existing prompt instead"* is never recommended from declared
#: evidence alone. It needs a `same` verdict **and** a measured comparison — the
#: differential behavioural run and the cost/quality deltas — because it is the
#: one recommendation in the error table with no recovery. Until those stages
#: run, the action exists as something a person may choose and never as something
#: Prope pre-selects.
USE_EXISTING_REQUIRES_MEASUREMENT = True

#: How a task relation maps onto a verdict **before** the contract findings are
#: applied. `candidate_narrower` deliberately lands on `related` rather than on a
#: mirror of `supersedes`: a stored prompt that does only part of the incoming
#: prompt's job cannot serve its callers, so from the import screen's point of
#: view it is context, not a duplicate.
_RELATION_VERDICT: dict[str, Verdict] = {
    "same_task": Verdict.SAME,
    "candidate_broader": Verdict.SUPERSEDES,
    "candidate_narrower": Verdict.RELATED,
    "same_domain": Verdict.RELATED,
    "different": Verdict.UNRELATED,
}


def resolve_verdict(*, relation: str, findings: tuple[Finding, ...]) -> Verdict:
    """The verdict for one candidate: what the task relation says, contracts permitting.

    **The contract findings can only demote, never promote.** A pair the
    adjudicator called `same_domain` does not become `same` because their
    variables happen to line up — sharing an input contract is not doing the same
    work. But a pair it called `same_task` becomes `variant` the moment a hard
    contract finding exists, because *"same task, incompatible contract"* is
    precisely what `variant` names.
    """
    verdict = _RELATION_VERDICT.get(relation, Verdict.UNRELATED)
    if verdict in (Verdict.SAME, Verdict.SUPERSEDES) and any(
        finding.severity is Severity.HARD for finding in findings
    ):
        return Verdict.VARIANT
    return verdict


def resolve_action(verdict: Verdict) -> Action:
    """What the screen offers for one candidate.

    `supersedes` maps to `create_new` and the reason is worth stating, because
    the intuitive answer is "add it as a revision of the broader prompt". It is
    not: the incoming prompt is the *narrower* one, so attaching it as a revision
    would replace a prompt that handles more cases with one that handles fewer,
    and every caller relying on the extra coverage would lose it silently. The
    right outcome is a new prompt and a human deciding whether the two should be
    merged.
    """
    if verdict is Verdict.SAME:
        return (
            Action.ADD_REVISION
            if USE_EXISTING_REQUIRES_MEASUREMENT
            else Action.USE_EXISTING
        )
    return Action.CREATE_NEW


def recommend(candidates: tuple[CandidateEvidence, ...]) -> tuple[Action, str | None]:
    """What the dialog should pre-select, and for which prompt.

    `add_revision` only when **exactly one** candidate is `same`. Two `same`
    candidates is not a stronger signal, it is an unresolved question — which of
    the two — and pre-selecting either one answers it by position. The registry
    already holds a duplicate in that case, which is its own finding and not this
    dialog's to settle.
    """
    same = [
        candidate
        for candidate in candidates
        if candidate.verdict is Verdict.SAME and not candidate.has_hard_finding
    ]
    if len(same) == 1:
        return Action.ADD_REVISION, same[0].prompt_id
    return Action.CREATE_NEW, None


def _survives_floor(candidate: CandidateEvidence, floor: float) -> bool:
    """Whether the display floor may hide this row.

    **A lexical threshold does not get to overrule the adjudicator.** The floor
    measures how much of the incoming prompt's wording a candidate carries. That
    is a useful way to quieten context rows, and it is the wrong instrument
    entirely for deciding whether a confirmed duplicate exists — a prompt that
    was rewritten rather than copied does the same job with different words,
    which is precisely the case the whole redesign exists to catch, and it is the
    case a wording threshold is guaranteed to fail.

    Measured on the ten labelled triplets (`eval/retrieval/similarity.py`), not
    argued: **every one of the ten confirmed twins scores below 0.90**, the
    highest reaching 0.472, and the twin ranges overlap the decoy ranges, so no
    value of this floor separates a duplicate from a near-miss. Applied to
    `same` and `supersedes` it was not a strict threshold, it was a guarantee
    that the funnel's own conclusion never reached the screen.

    So the rule is: **if the adjudicator concluded the two prompts share a job in
    any form, the row is listed.** That is `same`, `supersedes`, and `variant` —
    and `variant` belongs there most of all, because it means *this does your
    job and its contract is incompatible with yours*, which is the single most
    expensive thing the screen can know and the one a reader least expects to
    have to ask for. Their coverage is reported honestly beside them by the
    metric tiles rather than used to suppress them.

    `related` — a narrower prompt, a same-domain neighbour, or anything no
    adjudicator saw — stays subject to the floor. That is context, and hiding
    thin context is what the floor was added to do.
    """
    if candidate.verdict in (Verdict.SAME, Verdict.SUPERSEDES, Verdict.VARIANT):
        return True
    return candidate.match_score >= floor


def summarise(
    candidates: tuple[CandidateEvidence, ...],
    *,
    retrieved: int,
    adjudicated: int,
    coverage: tuple[Finding, ...] = (),
    # Resolved here rather than bound as a default, because a default argument
    # is evaluated once at import and `MATCH_FLOOR` is the one number in this
    # package a deployment is expected to move.
    match_floor: float | None = None,
) -> EvidenceSheet:
    """Assemble the sheet, dropping what must not be shown at all.

    `unrelated` candidates are removed rather than returned with a label. The
    import dialog is a decision surface: a row on it is an accusation that this
    prompt might be the one you already have, and rendering *"here are three
    prompts we checked and rejected"* is how the previous version came to show
    three unrelated prompts as duplicates. What was checked is a count
    (``retrieved`` / ``adjudicated``), not a list.

    **Then the match floor — over context rows only, and applied here rather
    than upstream on purpose.** By this point a candidate has been retrieved,
    ranked, judged and contract-checked, so dropping it costs nothing that was
    not already spent and removes no evidence from any other row — the IDF
    weights that produced every score were computed over the pool as retrieved,
    and thresholding earlier would have changed them. It runs **before**
    :func:`recommend` because a prompt the screen does not list must not be the
    prompt the screen pre-selects: a radio button that is not on the page cannot
    be argued with. What it may not touch is a `same` or `supersedes` — see
    :func:`_survives_floor` for the measurement that settled that.

    Ordering is `same`, `supersedes`, `variant`, `related` — the order in which a
    reader should read them — and within a verdict by structural score, so the
    order is reproducible across runs.
    """
    floor = MATCH_FLOOR if match_floor is None else match_floor
    shown = tuple(
        candidate for candidate in candidates if candidate.verdict is not Verdict.UNRELATED
    )
    above = tuple(candidate for candidate in shown if _survives_floor(candidate, floor))
    below_floor = len(shown) - len(above)
    shown = above
    priority = {
        Verdict.SAME: 0,
        Verdict.SUPERSEDES: 1,
        Verdict.VARIANT: 2,
        Verdict.RELATED: 3,
        Verdict.UNRELATED: 4,
    }
    shown = tuple(
        sorted(
            shown,
            key=lambda candidate: (
                priority[candidate.verdict],
                -candidate.structural_score,
                candidate.prompt_id,
            ),
        )
    )

    action, prompt_id = recommend(shown)
    extra: list[Finding] = list(coverage)

    if below_floor:
        # Said out loud, on the screen, in the same list as every other reason
        # the answer might be incomplete. A threshold whose effect is invisible
        # is a threshold that turns "nothing resembles this" into a claim the
        # system cannot support — and this one is strict enough to hide a real
        # duplicate that was rewritten rather than copied.
        extra.append(
            Finding(
                code="similar.coverage.below_match_floor",
                severity=Severity.INFO,
                axis="coverage",
                params={"hidden": below_floor, "floor": round(floor * 100)},
            )
        )

    if action is Action.ADD_REVISION and USE_EXISTING_REQUIRES_MEASUREMENT:
        # Said out loud rather than left as an absence. The screen is about to
        # offer "add as a revision" for a prompt Prope believes does the same
        # job, and the reason it is not offering "use that one instead" is that
        # nothing has yet measured whether the incoming prompt is better, worse
        # or merely different.
        extra.append(
            Finding(
                code="similar.coverage.use_existing_requires_measurement",
                severity=Severity.INFO,
                axis="coverage",
                params={"prompt_id": prompt_id},
            )
        )

    return EvidenceSheet(
        candidates=shown,
        recommended_action=action,
        recommended_prompt_id=prompt_id,
        retrieved=retrieved,
        adjudicated=adjudicated,
        match_floor=floor,
        below_floor=below_floor,
        coverage=tuple(extra),
    )
