"""The funnel, end to end. Retrieval hands it candidates; it hands back a sheet.

    1000 prompts
       |  retrieval — vector + lexical, recall-tuned, milliseconds
       v
     ~20 candidates
       |  structural pre-filter — canonical blocks, pool-relative IDF
       |  FREE: no dispatch, no model call
       v
      ~5 candidates
       |  adjudicator — ONE call over all five
       v
     0-2  same / supersedes
       |  behavioural and cost comparison — NOT IN THIS STAGE (see below)
       v
     the evidence sheet

Each rung costs roughly ten times more per item and carries five to ten times
fewer items, and the total bill is bounded by the last rung running on at most
two candidates. That is what makes the design affordable at a thousand prompts,
and it is also why the rungs may not be reordered for convenience.

**Retrieval owes recall; precision moved downstream.** When the probe's top three
went straight to a human, every row was an accusation and precision ruled. With
an adjudicator behind it, a candidate that never enters can never be confirmed
*or* rejected — so the mouth of the funnel caps K, does not threshold hard, and
lets the later stages reject. Nothing in this module filters on variable set,
folder or language: a true duplicate can rename its variables, cross-folder
duplicates are the fragmentation this exists to catch, and a language difference
is what `variant` is made of. They are signals. The only legitimate hard filter
is visibility, and that is applied by the repository before anything gets here.

**What this stage does NOT do, stated so its absence is not read as a pass.** The
behavioural comparison (a differential run over stratified inputs) and the cost
and quality deltas (A's suite re-run against the candidate body) are the two
paid stages of the design. Neither runs here: they cost 2N dispatches and a suite
run on the workspace's own provider credential, they cannot run inside an import
dialog that already sits at twenty-five seconds, and whether "may read prompt X"
implies "may spend on X's provider config" is an open question. Their absence is
why :data:`verdict.USE_EXISTING_REQUIRES_MEASUREMENT` holds and why no sheet from
this module ever recommends discarding somebody's prompt.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace

from prope.prompt_search.comparison.domain import (
    BlockOverlapRead,
    CandidateEvidence,
    CandidateOverlap,
    EvidenceSheet,
    Finding,
    Severity,
    Verdict,
)
from prope.prompt_search.comparison.input_contract import compare_input_contracts
from prope.prompt_search.comparison.output_contract import (
    UNSPECIFIED,
    OutputDescriptor,
    compare_output_contracts,
)
from prope.prompt_search.comparison.structural import (
    BLOCK_ORDER,
    BLOCK_WEIGHTS,
    PromptFacts,
    ScoredCandidate,
    facts_of,
    rank_candidates,
)
from prope.prompt_search.comparison.trace import Step, StepState, TraceEvent
from prope.prompt_search.comparison.verdict import (
    resolve_action,
    resolve_verdict,
    summarise,
)

__all__ = [
    "ADJUDICATION_LIMIT",
    "PRESENTATION_BLOCKS",
    "RETRIEVAL_LIMIT",
    "CandidateInput",
    "compare",
    "present",
]

#: How many candidates retrieval offers the funnel.
#:
#: **A recall target, not a page size.** Twenty is the K at which `recall@K`
#: should reach ~1.0 on a labelled set: if the true duplicate is in the top
#: twenty the funnel finds it, and the two cheap rungs behind it are what make
#: twenty affordable. Needing a hundred would mean the representation is wrong —
#: a hundred is too many for free signals to sort and too many for one
#: adjudicator call — and the fix for that is block-level vectors, not a bigger
#: number here.
RETRIEVAL_LIMIT = int(os.environ.get("PROMPT_SEARCH_RETRIEVAL_LIMIT", "20"))

#: How many reach the one adjudication call. Five is what fits in one context
#: alongside the incoming prompt without any of them being summarised, and
#: summaries are where evidence dies.
ADJUDICATION_LIMIT = int(os.environ.get("PROMPT_SEARCH_ADJUDICATION_LIMIT", "5"))

#: Which blocks the adjudicator is shown, in this order.
#:
#: `instructions` carries the job, `output_format` the contract, `constraints`
#: the policy envelope. `system` is persona and `examples` is volume, and
#: including them would re-create in the model's context exactly the problem the
#: whole-document embedding has: the genre drowning the job.
PRESENTATION_BLOCKS = ("instructions", "output_format", "constraints")

#: Per-candidate character budget for the adjudication call.
#:
#: **Measured rather than assumed, because 1,200 was demonstrably too small.**
#: On the ten labelled triplets the adjudicator saw between 415 and 1,222
#: characters of prompts running from 3,129 to 23,925 — as little as 2.8% of one
#: of them — and the single most common error was `same_task` answered as
#: `candidate_narrower`, on 4 of 10 pairs. That is not a model being cautious,
#: it is a model reporting what it was shown: given a third of a prompt it
#: concludes the prompt does a third of the job. Only 4 of 10 confirmed
#: duplicates were recognised as doing the same job at 1,200.
#:
#: Re-measured at 4,000 over the same ten triplets, same decoys, nothing else
#: changed:
#:
#: ===========================  =====  =====
#: budget                       1,200  4,000
#: ===========================  =====  =====
#: twins recognised (of 10)         4      7
#: `same_task` -> `narrower`        4      1
#: decoys called `same_task`        0      0
#: ===========================  =====  =====
#:
#: Recall nearly doubles, the truncation-signature error all but disappears, and
#: **precision is unchanged** — no near-miss was called interchangeable at either
#: budget, which is the direction §1.5 says must not move.
#:
#: Raising it costs input tokens on one call per import, not per candidate pair,
#: and the funnel already spends ~27 s in that call. It does not change the free
#: rungs at all. The `examples` block is still never presented, so this does not
#: reopen the door `PRESENTATION_BLOCKS` closes.
PRESENTATION_CHARACTER_LIMIT = int(
    os.environ.get("PROMPT_SEARCH_PRESENTATION_CHARACTERS", "4000")
)

AdjudicateFn = Callable[
    [str, list[tuple[str, str, str]]], Awaitable[dict[str, tuple[str, tuple[str, ...]]]]
]

#: One body in, its output contract out, paired with the block it was read from.
#:
#: Injected for the same reason ``AdjudicateFn`` is — this module must stay
#: runnable without DSPy — and it returns the ``source_block`` alongside the
#: descriptor because the trace reports *where* a contract was found and the
#: sheet weighs a prose-inferred one differently from a declared one.
#:
#: The first argument is the subject's id, empty for the incoming paste. This
#: module has no use for it; the caller does, because a descriptor extracted
#: here is worth writing back to the index row it was missing from, and a cache
#: fill that cannot name its row would have to match on the body text — which
#: two genuine duplicates share, which is the whole subject of this screen.
DescribeFn = Callable[[str, str], Awaitable[tuple[OutputDescriptor | None, str]]]

#: Where a rung's progress goes. Synchronous and returning nothing, so that a
#: caller with nowhere to put it passes nothing and the funnel is unchanged —
#: and so that no rung can ever be made to wait on its own narration.
StepFn = Callable[[TraceEvent], None]


@dataclass(frozen=True, slots=True)
class CandidateInput:
    """One retrieved prompt, with everything the funnel needs and nothing else."""

    prompt_id: str
    title: str
    body: str
    keywords: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    #: The cached descriptor from this prompt's index row. ``None`` means never
    #: extracted, which stage 2b reports as *not established* rather than as
    #: compatible.
    descriptor: OutputDescriptor | None = None
    similarity: float | None = None
    is_indexed: bool = False
    facts: PromptFacts | None = field(default=None, compare=False)

    def resolved_facts(self) -> PromptFacts:
        if self.facts is not None:
            return self.facts
        return facts_of(
            self.body,
            prompt_id=self.prompt_id,
            keywords=self.keywords,
            topics=self.topics,
            entities=self.entities,
        )


def present(facts: PromptFacts, *, limit: int = PRESENTATION_CHARACTER_LIMIT) -> str:
    """One prompt as the adjudicator sees it: the discriminating blocks, labelled.

    Blocks are labelled rather than concatenated so the model can tell a task
    statement from an output contract — the distinction the whole comparison
    turns on. A body with no canonical blocks (the import screen's normal case,
    where the text has not been converted yet) is presented whole, cut to the
    same budget.
    """
    if not facts.is_canonical:
        return facts.fallback.strip()[:limit]

    present_blocks = [
        (tag, text)
        for tag in PRESENTATION_BLOCKS
        if (text := facts.blocks.get(tag, "").strip())
    ]

    # **The per-block share is a reservation, not a ceiling.** It exists so a long
    # `instructions` cannot consume the whole budget and leave the output
    # contract — the shortest and most discriminating block — cut off entirely.
    # As a hard cap it did something else: a prompt the converter placed entirely
    # in one block was shown `limit // 3` characters and the rest of the budget
    # went unspent, so raising `PRESENTATION_CHARACTER_LIMIT` bought a
    # single-block prompt only a third of the increase. Measured consequence: a
    # prompt pasted against its own stored text came back `candidate_narrower` —
    # the adjudicator was comparing 4,000 characters of the incoming against
    # 1,333 of the identical candidate and correctly reporting that the incoming
    # covers more.
    #
    # So reserve first, then hand the unclaimed remainder back in block order.
    # Blocks that are short keep their guarantee; a lone block gets the lot.
    reserve = max(120, limit // len(PRESENTATION_BLOCKS)) if present_blocks else 0
    allocation = {tag: min(len(text), reserve) for tag, text in present_blocks}
    spare = limit - sum(allocation.values())
    for tag, text in present_blocks:
        if spare <= 0:
            break
        extra = min(len(text) - allocation[tag], spare)
        if extra > 0:
            allocation[tag] += extra
            spare -= extra

    parts: list[str] = [
        f"[{tag}]\n{text[: allocation[tag]]}" for tag, text in present_blocks
    ]
    remaining = limit - sum(allocation.values())

    if parts:
        return "\n\n".join(parts)

    # **Never hand the adjudicator an empty candidate.** A canonical prompt whose
    # content sits entirely in `system`, `context` or `examples` matches none of
    # the three blocks above, and this used to return `""`. The model was then
    # asked to compare a real prompt against nothing — and it does not abstain:
    # measured on the labelled set, a 4,500-character prompt presented as zero
    # characters came back `same_task`, which resolves to `SAME` and is the one
    # recommendation §1.5 calls unrecoverable. An empty brief is not weak
    # evidence, it is an invitation to agree.
    #
    # So fall back to whatever the prompt does have, in `BLOCK_ORDER`, still
    # labelled and still inside the same budget. Weaker evidence than the three
    # discriminating blocks, and honest about which blocks it came from.
    for tag in BLOCK_ORDER:
        text = facts.blocks.get(tag, "").strip()
        if not text or remaining <= 0:
            continue
        share = min(len(text), remaining)
        parts.append(f"[{tag}]\n{text[:share]}")
        remaining -= share
    return "\n\n".join(parts)


def _overlap_of(scored: ScoredCandidate) -> CandidateOverlap:
    """The free rung's working, carried forward instead of thrown away.

    ``rank_candidates`` already computes every number here to decide the order;
    keeping them costs nothing and is the difference between a screen that
    asserts two prompts are alike and one that shows what it read.

    Blocks that shared nothing are dropped rather than listed at zero: a row
    saying `examples 0%` is true, uninteresting, and pushes the row that matters
    off the visible part of a dialog.

    **Ordered by how much the block counts, not by how well it scored.** Two
    prompts from the same library share their `system` block almost verbatim, so
    persona routinely scores higher than the job — and a list sorted by score
    would put the least meaningful agreement at the top of the screen, which is
    the whole-document embedding's mistake reproduced in the interface. The order
    is `BLOCK_WEIGHTS`, so the reader meets `instructions` first and `system`
    last, with both numbers visible.
    """
    return CandidateOverlap(
        blocks=tuple(
            BlockOverlapRead(
                block=overlap.block,
                score=overlap.score,
                shared_terms=overlap.shared_terms,
            )
            for overlap in sorted(
                scored.blocks,
                key=lambda item: (-BLOCK_WEIGHTS.get(item.block, 1.0), -item.score, item.block),
            )
            if overlap.score > 0.0
        ),
        # Every tag that was compared, zeros included, in the same weight order.
        # `blocks` is the list a reader scans; this is what a fixed grid of
        # metrics needs so an unmeasured block is never drawn as a zero.
        compared_blocks=tuple(
            overlap.block
            for overlap in sorted(
                scored.blocks,
                key=lambda item: (-BLOCK_WEIGHTS.get(item.block, 1.0), item.block),
            )
        ),
        shared_variables=scored.shared_variables,
        variable_overlap=scored.variable_overlap,
        variables_required=scored.variables_required,
        metadata_overlap=scored.metadata_overlap,
    )


def _contract_findings(
    incoming_body: str,
    incoming_descriptor: OutputDescriptor | None,
    candidate: CandidateInput,
) -> tuple[Finding, ...]:
    """Stages 2a and 2b for one pair. Free, exact, and it runs before anything is spent.

    The direction is fixed and asymmetric: the **candidate** is the stored prompt
    whose callers exist, and the **incoming** body is what would be swapped in.
    So `compare_input_contracts` is asked whether the incoming body still works
    for the stored prompt's callers — which is the question the import screen is
    actually asking, and the reverse of it would report a safe change as a
    breaking one on every subset.
    """
    contract = compare_input_contracts(
        candidate_body=incoming_body,
        released_body=candidate.body,
    )
    return (
        *contract.findings(),
        *compare_output_contracts(
            candidate=incoming_descriptor, released=candidate.descriptor
        ),
    )


async def compare(
    *,
    incoming_body: str,
    candidates: list[CandidateInput],
    incoming_descriptor: OutputDescriptor | None = None,
    adjudicate: AdjudicateFn | None = None,
    describe: DescribeFn | None = None,
    adjudication_limit: int = ADJUDICATION_LIMIT,
    coverage: tuple[Finding, ...] = (),
    match_floor: float | None = None,
    on_step: StepFn | None = None,
) -> EvidenceSheet:
    """Run the free rungs, then the one paid rung, and assemble the sheet.

    ``adjudicate`` is injected rather than imported so this module stays testable
    without a model and without DSPy's eleven-second import: the whole free half
    of the funnel is exercised by passing a function that returns a fixed
    mapping. ``describe`` is injected the same way and for the same reason.

    **``describe`` is what makes stage 2b reachable from the import screen.**
    The descriptor is meant to be a per-revision property extracted once at
    index time and read from the index row here; in practice a row is missing
    one whenever the prompt predates the column, its extraction failed, or the
    stored descriptor belongs to an older revision, and the incoming body has
    never had one at all because nobody has indexed something that is being
    pasted. Given ``describe`` the funnel fills those gaps itself, in one
    parallel batch, and compares real contracts instead of reporting *not
    established* on both sides forever. Given ``None`` it behaves exactly as
    before: whatever the index carried, and a coverage finding for the rest.

    ``on_step`` is optional and the funnel does not change shape when it is
    absent: the JSON caller passes nothing, the streaming caller passes a queue
    writer. Narration that altered the thing being narrated would make the trace
    a description of a different run.
    """

    def step(kind: Step, state: StepState, **params: object) -> None:
        if on_step is not None:
            on_step(TraceEvent(step=kind, state=state, params=params))

    retrieved = len(candidates)
    if not candidates:
        step(Step.PREFILTER, StepState.SKIPPED, retrieved=0)
        return summarise(
            (), retrieved=0, adjudicated=0, coverage=coverage, match_floor=match_floor
        )

    incoming = facts_of(incoming_body)
    by_id = {candidate.prompt_id: candidate for candidate in candidates}

    step(Step.PREFILTER, StepState.STARTED, retrieved=retrieved)
    ranked = rank_candidates(
        incoming,
        [candidate.resolved_facts() for candidate in candidates],
        limit=adjudication_limit,
    )
    step(
        Step.PREFILTER,
        StepState.DONE,
        retrieved=retrieved,
        kept=len(ranked),
        canonical=incoming.is_canonical,
    )

    briefs: list[tuple[str, str, str]] = []
    labels: dict[str, str] = {}
    for position, scored in enumerate(ranked, start=1):
        label = f"C{position}"
        labels[label] = scored.facts.prompt_id
        candidate = by_id[scored.facts.prompt_id]
        briefs.append((label, candidate.title, present(scored.facts)))

    judged: dict[str, tuple[str, tuple[str, ...]]] = {}
    unavailable = False
    if adjudicate is not None and briefs:
        step(Step.ADJUDICATION, StepState.STARTED, candidates=len(briefs))
        judged = await adjudicate(present(incoming), briefs)
        unavailable = not judged
        step(
            Step.ADJUDICATION,
            StepState.FAILED if unavailable else StepState.DONE,
            candidates=len(briefs),
            judged=len(judged),
        )
    else:
        step(Step.ADJUDICATION, StepState.SKIPPED, candidates=len(briefs))

    # Stage 2b, for whatever the index could not supply. It runs **after**
    # adjudication so it is only ever spent on candidates the sheet will show:
    # a pair the adjudicator called `different` is dropped from the sheet
    # entirely, and its contract cannot change that — output findings only
    # demote. One batch, gathered, so five extractions cost one extraction's
    # latency on a dialog that already sits at 25 seconds.
    filled: dict[str, OutputDescriptor | None] = {}
    incoming_source = UNSPECIFIED
    if describe is not None:
        wanted = [
            scored.facts.prompt_id
            for position, scored in enumerate(ranked, start=1)
            if by_id[scored.facts.prompt_id].descriptor is None
            and judged.get(f"C{position}", ("", ()))[0] not in ("", "different")
        ]
        needs_incoming = incoming_descriptor is None
        if wanted or needs_incoming:
            step(
                Step.OUTPUT_CONTRACT,
                StepState.STARTED,
                incoming=needs_incoming,
                candidates=len(wanted),
            )
            jobs = [describe(prompt_id, by_id[prompt_id].body) for prompt_id in wanted]
            if needs_incoming:
                jobs.append(describe("", incoming_body))
            answers = await asyncio.gather(*jobs, return_exceptions=True)
            for prompt_id, answer in zip(wanted, answers, strict=False):
                # `describe` swallows its own failures by contract; an exception
                # here is a bug in the caller, and one candidate's bug may not
                # cost the other four their comparison.
                filled[prompt_id] = answer[0] if isinstance(answer, tuple) else None
            if needs_incoming:
                last = answers[-1]
                if isinstance(last, tuple):
                    incoming_descriptor, incoming_source = last
            extracted = sum(1 for value in filled.values() if value is not None)
            if incoming_descriptor is not None:
                state = StepState.DONE
            elif incoming_source == UNSPECIFIED:
                # Nothing to read. The body says nothing about what it returns,
                # which is a fact about the prompt and not an incident.
                state = StepState.SKIPPED
            else:
                # There WAS a contract to read and the extractor did not answer.
                # That one is a failure, and collapsing the two would teach a
                # reader that this row's colour means nothing.
                state = StepState.FAILED
            step(
                Step.OUTPUT_CONTRACT,
                state,
                source_block=incoming_source,
                candidates=extracted,
            )
        else:
            step(Step.OUTPUT_CONTRACT, StepState.SKIPPED, source_block="cached", candidates=0)

    evidence: list[CandidateEvidence] = []
    hard_findings = 0
    for position, scored in enumerate(ranked, start=1):
        candidate = by_id[scored.facts.prompt_id]
        if candidate.prompt_id in filled and filled[candidate.prompt_id] is not None:
            candidate = replace(candidate, descriptor=filled[candidate.prompt_id])
            by_id[candidate.prompt_id] = candidate
        findings = _contract_findings(incoming_body, incoming_descriptor, candidate)
        hard_findings += sum(1 for finding in findings if finding.severity is Severity.HARD)
        relation, reasons = judged.get(f"C{position}", ("", ()))

        if relation:
            verdict = resolve_verdict(relation=relation, findings=findings)
        else:
            # Nothing judged this pair. It is shown as context and never as a
            # duplicate: claiming `same` on structural overlap alone is exactly
            # the inference — nearest vectors rendered as duplicates — that this
            # redesign exists to remove.
            verdict = Verdict.RELATED

        evidence.append(
            CandidateEvidence(
                prompt_id=candidate.prompt_id,
                verdict=verdict,
                action=resolve_action(verdict),
                findings=findings,
                similarity=candidate.similarity,
                structural_score=scored.score,
                match_score=scored.match,
                adjudicated=bool(relation),
                reasons=reasons,
                overlap=_overlap_of(scored),
            )
        )

    step(
        Step.CONTRACTS,
        StepState.DONE,
        checked=len(evidence),
        hard=hard_findings,
        demoted=sum(
            1
            for item in evidence
            if item.verdict is Verdict.VARIANT and item.has_hard_finding
        ),
    )

    extra = list(coverage)
    if unavailable and briefs:
        extra.append(
            Finding(
                code="similar.coverage.adjudication_unavailable",
                severity=Severity.SOFT,
                axis="coverage",
                params={"candidates": len(briefs)},
            )
        )
    if not incoming.is_canonical:
        # Worth saying: the free stages compared whole text against blocks, which
        # is weaker evidence than block against block, and the output contract
        # could not be read at all.
        extra.append(
            Finding(
                code="similar.coverage.incoming_not_canonical",
                severity=Severity.INFO,
                axis="coverage",
                params={},
            )
        )

    sheet = summarise(
        tuple(evidence),
        retrieved=retrieved,
        adjudicated=len(judged),
        coverage=tuple(extra),
        match_floor=match_floor,
    )
    step(
        Step.VERDICT,
        StepState.DONE,
        shown=len(sheet.candidates),
        hidden=sheet.below_floor,
        floor=round(sheet.match_floor * 100),
        action=sheet.recommended_action.value,
    )
    return sheet
