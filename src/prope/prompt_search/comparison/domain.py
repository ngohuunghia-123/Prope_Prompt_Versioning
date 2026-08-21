"""What a similarity answer is made of. Pure types, no I/O, no model, no SQL.

The vocabulary this module fixes is the whole point of the redesign
(`docs/brainstorm/prompt-similarity.draft.md` §1). Before it, the duplicate
check computed *which vectors are nearest* and the import dialog rendered that
as *these are duplicates* — and nothing in the code had ever said what
"duplicate" meant, so nothing could be wrong about it and nothing could be
fixed.

Three commitments live here rather than in prose:

1. **Similarity is a property of substitution, not of text.** Two prompts do the
   same job when swapping one for the other would not break the caller. That
   relation is **asymmetric** — "B can serve A's callers" and "A can serve B's
   callers" are different claims — which is why :class:`Verdict` has
   ``supersedes`` at all and why a cosine, symmetric by construction, could
   never have represented the answer.
2. **A finding is a code and its parameters, never a sentence.** ADR-0053: the
   interface is Vietnamese behind a keyed catalogue, the API returns a machine
   ``code`` and the client translates it. A finding carrying prose would be a
   display string smuggled through the wire, and it would also be a finding
   nobody can count.
3. **`hard` is a veto, not a large number.** Nothing here averages anything. A
   hard finding disqualifies substitution regardless of how good the rest of the
   comparison looked — the happy path washing out the one edge case that
   mattered is exactly the failure a mean produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "FINDING_CODES",
    "REASON_CODES",
    "TASK_RELATIONS",
    "Action",
    "BlockOverlapRead",
    "CandidateEvidence",
    "CandidateOverlap",
    "EvidenceSheet",
    "Finding",
    "InputContractRelation",
    "Severity",
    "Verdict",
]


class Verdict(StrEnum):
    """How a candidate relates to the incoming prompt.

    Richer than same / related / unrelated because ``variant`` and ``supersedes``
    are precisely the cases a naive judge calls ``same``, and both are cases
    where *"use the existing prompt instead"* is actively wrong.
    """

    #: Substitutable in both directions.
    SAME = "same"
    #: The candidate does the incoming prompt's job and more. Neither a revision
    #: nor a redirect is correct — it is its own relation.
    SUPERSEDES = "supersedes"
    #: Same task, incompatible contract — output shape, variables, language.
    VARIANT = "variant"
    #: Same domain, different task. Shown as context, never as a duplicate.
    RELATED = "related"
    #: Not shown at all.
    UNRELATED = "unrelated"


class Action(StrEnum):
    """What the screen offers. Derived in code from a verdict plus its findings.

    **Never emitted by a model.** The final agent produces evidence; the action
    is a function of that evidence, so that "what Prope recommended" is
    reproducible and reviewable rather than a sentence a model happened to write
    (§4 of the draft).
    """

    #: Discard the incoming prompt and call the existing one. **The dangerous
    #: recommendation** — the only irrecoverable error in §1.5's table — so it
    #: requires a `same` verdict *and* a measured comparison, and is never a
    #: default.
    USE_EXISTING = "use_existing"
    #: Attach the incoming body to the existing prompt as a new revision.
    ADD_REVISION = "add_revision"
    #: Register a new prompt. **The unmeasured default**: it discards nothing and
    #: writes something recoverable.
    CREATE_NEW = "create_new"


class Severity(StrEnum):
    """How much weight a finding carries downstream."""

    #: A veto. No cost saving or quality gain trades it away.
    HARD = "hard"
    #: Weighed by a human against the rest of the sheet.
    SOFT = "soft"
    #: Context. Never moves a verdict on its own.
    INFO = "info"


class InputContractRelation(StrEnum):
    """``required_variables(B)`` against ``required_variables(A)``.

    Set math with a direction, because ``prompt_composition.render()`` raises
    ``MissingVariable`` for a placeholder without a value and **ignores
    extras**. Fewer variables is safe; more is fatal.
    """

    #: Neither prompt takes a variable.
    NONE = "none"
    IDENTICAL = "identical"
    #: B requires a strict subset of A's. Callers still send the extras.
    SUBSET = "subset"
    #: B requires everything A does and more. Every caller gets `MissingVariable`.
    SUPERSET = "superset"
    #: Same names dropped for new ones — the classic `{{document}}` -> `{{text}}`.
    RENAMED = "renamed"
    #: Some shared, some not, in both directions.
    PARTIAL = "partial"


#: The relations the adjudicator may return, and the only ones code understands.
#:
#: **Task relations, not verdicts.** ``same_task`` says two prompts do the same
#: work; whether they are *substitutable* additionally requires the input and
#: output contracts to line up, and those are decided for free without a model.
#: Keeping the two vocabularies apart is what stops a model's opinion about
#: wording from overriding an exact fact about variables.
TASK_RELATIONS: tuple[str, ...] = (
    "same_task",
    "candidate_broader",
    "candidate_narrower",
    "same_domain",
    "different",
)

#: Why the adjudicator decided what it decided, as a closed vocabulary.
#:
#: A closed set rather than free text for three reasons: it is countable, so a
#: dashboard can show which axis most often separates two prompts; it is
#: translatable, which ADR-0053 requires of anything a person reads; and it
#: cannot smuggle a fragment of somebody's prompt into a payload that is
#: rendered on a screen.
#:
#: **These live here rather than beside the agent for an import reason as much as
#: a modelling one**, exactly as `domain.MAX_KEYWORDS` does: a contract test
#: checks them against the interface catalogue, and reaching them through
#: `comparison_program` would pull `import dspy` — eleven seconds of litellm,
#: tokenizers and the OTel SDK — into a test that reads two files.
REASON_CODES: tuple[str, ...] = (
    "same_action_same_object",
    "different_action",
    "different_object",
    "different_audience",
    "different_domain",
    "different_policy",
    "candidate_covers_more_cases",
    "incoming_covers_more_cases",
    "different_output_shape",
    "different_language",
)


#: Every code this package may emit, closed and in source.
#:
#: **It exists so the interface catalogue can be checked against it.** ADR-0053
#: puts every sentence a person reads in a keyed catalogue and sends only a code
#: over the wire, which means a code with no key renders as itself — a raw
#: `similar.output_contract.bare_relaxed` on an import dialog is worse than no
#: finding, because it is a warning nobody can act on. A contract test reads this
#: tuple and the Vietnamese catalogue and refuses a code with no sentence, the
#: same guarantee `readiness` already has for its rule ids.
FINDING_CODES: tuple[str, ...] = (
    "similar.input_contract.renamed",
    "similar.input_contract.requires_more",
    "similar.input_contract.requires_fewer",
    "similar.input_contract.identical",
    "similar.output_contract.keys_missing",
    "similar.output_contract.keys_added",
    "similar.output_contract.enum_undeclared",
    "similar.output_contract.enum_dropped",
    "similar.output_contract.enum_added",
    "similar.output_contract.modality_undeclared",
    "similar.output_contract.modality_changed",
    "similar.output_contract.bare_relaxed",
    "similar.output_contract.cardinality_changed",
    "similar.output_contract.language_changed",
    "similar.output_contract.length_changed",
    "similar.output_contract.not_established",
    "similar.output_contract.compatible",
    "similar.output_contract.declared_in_instructions",
    "similar.output_contract.inferred_from_prose",
    "similar.coverage.adjudication_unavailable",
    "similar.coverage.incoming_not_canonical",
    "similar.coverage.partially_indexed",
    "similar.coverage.use_existing_requires_measurement",
    "similar.coverage.below_match_floor",
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing the comparison established, as a code the client translates.

    ``params`` holds only machine values — variable names, block tags, counts,
    key names. Never a body, never a sentence, never anything that would make
    this row a display string in disguise.
    """

    code: str
    severity: Severity
    #: Which question it belongs to: ``input_contract``, ``output_contract``,
    #: ``task``, ``coverage``. Kept so a screen can group findings without
    #: parsing the code, and so a metric can be labelled by it at bounded
    #: cardinality (ADR-0030).
    axis: str
    params: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "axis": self.axis,
            "params": dict(self.params),
        }


@dataclass(frozen=True, slots=True)
class BlockOverlapRead:
    """One canonical block's overlap, as it travels to the interface."""

    block: str
    score: float
    shared_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "block": self.block,
            "score": round(self.score, 4),
            "shared_terms": list(self.shared_terms),
        }


@dataclass(frozen=True, slots=True)
class CandidateOverlap:
    """**Why** a candidate is on the sheet, in the words the two prompts share.

    Separate from :class:`Finding` on purpose, and the separation is a rule about
    content rather than a modelling preference. A finding is a code and machine
    values, translatable and countable, safe in a log line. This is the *evidence*
    behind the ranking: block names, a containment per block, and the shared
    words themselves — which are somebody's prompt text.

    It is admissible on the import dialog's response, which already carries two
    thousand characters of the candidate's body as ``body_preview``, and nowhere
    else. **Never a log field, never a metric label, never a finding param.**

    Why it exists at all: a verdict without it is an assertion. *"These two do
    the same job"* invites agreement or nothing; *"they share `refund`,
    `escalate` and `tier` in `instructions`, and `{{ticket}}`"* invites a reader
    to say **no** — and a duplicate check nobody can contradict is how three
    unrelated prompts came to be shown as duplicates in the first place.
    """

    blocks: tuple[BlockOverlapRead, ...] = ()
    #: Every block tag the pre-filter actually scored, including the ones that
    #: scored zero and were dropped from `blocks`.
    #:
    #: **Because a screen that shows one number per block has to tell "shared
    #: nothing" from "never compared".** `blocks` carries only what overlapped,
    #: which is right for a list — a row reading `examples 0%` is true,
    #: uninteresting, and pushes the row that matters off the dialog. But a fixed
    #: grid of metrics has a cell for `output_format` whether or not anything
    #: landed in it, and rendering an absent block as `0%` would report *these
    #: two declare incompatible output* about a prompt that declares no output
    #: block at all. Same distinction as `output_contract.not_established`, one
    #: layer down.
    compared_blocks: tuple[str, ...] = ()
    shared_variables: tuple[str, ...] = ()
    #: Share of the incoming prompt's variables the candidate also reads.
    variable_overlap: float = 0.0
    #: The denominator of `variable_overlap`. Zero means the incoming prompt
    #: takes no variables, which is not the same as sharing none of them.
    variables_required: int = 0
    #: Overlap on the agent-extracted keywords, topics and entities. Zero for a
    #: candidate the indexing worker has not reached, which is not the same as
    #: no overlap and is why the field travels beside `is_indexed`.
    metadata_overlap: float = 0.0

    def to_dict(self) -> dict:
        return {
            "blocks": [block.to_dict() for block in self.blocks],
            "compared_blocks": list(self.compared_blocks),
            "shared_variables": list(self.shared_variables),
            "variable_overlap": round(self.variable_overlap, 4),
            "variables_required": self.variables_required,
            "metadata_overlap": round(self.metadata_overlap, 4),
        }


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """Everything known about one candidate, and nothing inferred beyond it."""

    prompt_id: str
    verdict: Verdict
    action: Action
    findings: tuple[Finding, ...] = ()
    #: Cosine, where there is one. `None` for a lexical-only candidate — see
    #: `ranking.FusedResult.similarity` for why that is the honest answer.
    similarity: float | None = None
    #: The free structural score that ordered the pre-filter. Diagnostic; it is
    #: not "how similar" and is never rendered as a percentage.
    structural_score: float = 0.0
    #: The same evidence normalised to 0..1 — the share of the incoming prompt's
    #: distinctive weight this candidate carries. **The one number here that is a
    #: percentage**, and the one the display floor is applied to. It says how
    #: much of the text is covered and never that the two prompts do the same
    #: job: that claim is `verdict`, and it is made by the adjudicator and the
    #: contract checks, neither of which reads this field.
    match_score: float = 0.0
    #: Whether the semantic adjudicator saw this candidate at all. A candidate
    #: cut by the pre-filter carries its structural verdict and says so.
    adjudicated: bool = False
    #: Why the adjudicator said what it said, as codes it was constrained to
    #: choose from. Empty when nothing adjudicated it.
    reasons: tuple[str, ...] = ()
    #: The free rung's evidence: which blocks overlapped, on which words.
    overlap: CandidateOverlap | None = None

    @property
    def has_hard_finding(self) -> bool:
        return any(finding.severity is Severity.HARD for finding in self.findings)

    def to_dict(self) -> dict:
        return {
            "prompt_id": self.prompt_id,
            "verdict": self.verdict.value,
            "action": self.action.value,
            "findings": [finding.to_dict() for finding in self.findings],
            "similarity": self.similarity,
            "structural_score": round(self.structural_score, 4),
            "match_score": round(self.match_score, 4),
            "adjudicated": self.adjudicated,
            "reasons": list(self.reasons),
            "overlap": self.overlap.to_dict() if self.overlap is not None else None,
        }


@dataclass(frozen=True, slots=True)
class EvidenceSheet:
    """The comparison's whole answer for one incoming prompt.

    **A sheet, not a verdict.** The core value is that no prompt reaches
    production without a recorded human approval; a payload that reads as the
    approval is a payload that has taken the decision. ``recommended_action`` is
    what the dialog should *pre-select*, and it is `create_new` unless the
    evidence for something else is complete.
    """

    candidates: tuple[CandidateEvidence, ...]
    recommended_action: Action
    #: Set when `recommended_action` names an existing prompt.
    recommended_prompt_id: str | None = None
    #: How many prompts the retrieval leg offered before the pre-filter cut them.
    retrieved: int = 0
    #: How many reached the adjudicator.
    adjudicated: int = 0
    #: The `match_score` a candidate had to clear to be listed at all, and how
    #: many cleared everything else and were held back by it.
    #:
    #: Both travel so the screen can say the floor out loud. A row that is absent
    #: because of a threshold is indistinguishable from a row that was never
    #: found, and the difference is the whole of whether *"no duplicates"* can be
    #: trusted — the same reason `retrieved` travels beside the rows.
    match_floor: float = 0.0
    below_floor: int = 0
    #: Findings about the answer itself rather than about a candidate — the
    #: index-coverage ceiling, a skipped adjudication, a body that is not
    #: canonical XML. An empty candidate list means *nothing indexed resembles
    #: this* and never *this is not a duplicate*, and this is where that is said.
    coverage: tuple[Finding, ...] = ()

    def for_prompt(self, prompt_id: str) -> CandidateEvidence | None:
        for candidate in self.candidates:
            if candidate.prompt_id == prompt_id:
                return candidate
        return None

    def to_dict(self) -> dict:
        return {
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "recommended_action": self.recommended_action.value,
            "recommended_prompt_id": self.recommended_prompt_id,
            "retrieved": self.retrieved,
            "adjudicated": self.adjudicated,
            "match_floor": round(self.match_floor, 4),
            "below_floor": self.below_floor,
            "coverage": [finding.to_dict() for finding in self.coverage],
        }
