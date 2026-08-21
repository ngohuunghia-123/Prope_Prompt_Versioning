"""Ten labelled triplets: what "the same job" means, written down.

**Why this file exists.** `prompt-similarity.draft.md` §7 calls the absence of a
labelled pair set *the blocker* — "no threshold, rubric or verdict boundary can
be justified and every proposal in §5 is an assertion". Every number in the
funnel (`MATCH_FLOOR`, `VECTOR_FLOOR`, `BLOCK_WEIGHTS`, the 20 and the 5) was
chosen rather than measured, because there was nothing to measure against.

**Why triplets rather than pairs.** `golden.duplicate_probes` already measures
one thing: feed back the first 1,800 characters of a corpus file and check the
same file comes back. That is verbatim self-retrieval, and it cannot fail the way
the product fails — the reported `context_precision_at_3 = 0.333` is not even a
finding, it is forced arithmetic, because each probe declares one `primary` and
`precision_at_k` divides by `len(top)`.

What the product gets wrong is the two cases that probe cannot express:

- a **twin** — same job, rewritten, sharing almost no distinctive vocabulary;
- a **decoy** — same subject, adjacent job, sharing a great deal of it.

Both must be judged correctly by the same threshold, and **that is the hard
part**: a bar low enough to admit the twin admits most of a single-genre prompt
library, because every prompt in one is polite, structured and role-prefixed.
So the pass condition here is **separation**, never recall. Ten twins found is
worth nothing without ten decoys refused.

**Where the labels come from.** Six triplets are entirely real — anchor, twin and
decoy are all files in `playgrounds/prompts`, which is where §7 said to look.
Four have a written twin under `twins/`, because the professional-persona files
in the corpus are each unique and have no genuine paraphrase; writing those makes
vocabulary the single moving part, which is precisely the variable that failed.
Both kinds are marked, so a result can be read separately for each.

**The disagreements are part of the data, not noise in it.** Where two reasonable
people would label a pair differently, `why` says so out loud and the pair is
kept. §7: *"the disagreements are the definition"* — a rubric that only contains
the easy calls has not been written down at all.

Nothing here is a corporate prompt. The corpus is a public library and A-020's
bar — no real corporate prompts until OQ-006 and OQ-013 close — is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "TRIPLETS",
    "Pair",
    "Triplet",
    "required_stems",
    "twin_text",
]

_TWINS = Path(__file__).resolve().parent / "twins"


@dataclass(frozen=True, slots=True)
class Pair:
    """One labelled comparison: the incoming prompt against one stored candidate.

    ``relation`` is the adjudicator's closed vocabulary (`comparison.domain
    .TASK_RELATIONS`) and ``verdict`` is what `resolve_verdict` must produce from
    it when no HARD contract finding fires. They are recorded separately on
    purpose: a wrong relation is a model failure, a right relation with a wrong
    verdict is a code failure, and a run that conflates them cannot say which
    half to fix.
    """

    #: Corpus file stem of the stored prompt being compared against.
    stem: str
    #: One of `same_task`, `candidate_broader`, `candidate_narrower`,
    #: `same_domain`, `different`.
    relation: str
    #: `same`, `supersedes`, `variant`, `related`, `unrelated`.
    verdict: str
    #: True when this candidate should reach the screen at all. A `related` row
    #: is context and may legitimately be hidden by a display threshold; a `same`
    #: row may not.
    listed: bool
    #: The human rule this pair encodes — the sentence that would go in a rubric.
    why: str


@dataclass(frozen=True, slots=True)
class Triplet:
    """One topic: the prompt somebody pastes, the duplicate, and the near-miss."""

    id: str
    topic: str
    #: The prompt being imported. A corpus stem, or a name under ``twins/`` when
    #: ``written`` is True.
    incoming: str
    #: Same job. Must be found.
    twin: Pair
    #: Same subject, different job. Must not be recommended.
    decoy: Pair
    #: True when ``incoming`` is a written paraphrase rather than a corpus file.
    written: bool = False

    @property
    def pairs(self) -> tuple[Pair, Pair]:
        return (self.twin, self.decoy)


#: The set. One topic each, decoys deliberately varied in *kind* so that a
#: threshold cannot pass by being wrong in one consistent direction:
#: opposite-action, different-action, different-audience, different-input-shape,
#: and two narrower-tool cases.
TRIPLETS: tuple[Triplet, ...] = (
    Triplet(
        id="t01",
        topic="turning a vague request into a precise prompt",
        incoming="5w3h_intent_architect",
        twin=Pair(
            stem="reprompt_requirements_engineering_prompt_architect",
            relation="same_task",
            verdict="same",
            listed=True,
            why=(
                "Both take an under-specified request and return a production-ready prompt by "
                "surfacing the intent the request left out. One calls the missing pieces 5W3H "
                "dimensions, the other calls them requirements elicited over four RE stages. "
                "Same action, same object, same deliverable; almost no shared vocabulary. This is "
                "the pair the product failed on, reproduced from the library."
            ),
        ),
        decoy=Pair(
            stem="prompt_compression_strategist",
            relation="same_domain",
            verdict="related",
            listed=False,
            why=(
                "Same object as the anchor — a prompt — and the opposite action performed on it. "
                "One expands an under-specified prompt, the other decides whether to prune tokens "
                "out of an over-long one. Swapping them breaks every caller. The hardest kind of "
                "decoy, because object overlap is what a whole-document embedding scores on."
            ),
        ),
    ),
    Triplet(
        id="t02",
        topic="designing memory for long-running agents",
        incoming="agent_memory_architect",
        twin=Pair(
            stem="agent_native_memory_system_architect",
            relation="same_task",
            verdict="same",
            listed=True,
            why=(
                "Both design the memory subsystem of a long-running agent — what is retained, how "
                "it is retrieved, how it is aged out. The second frames it as a data-management "
                "problem, the first as a retrieval-architecture one; that is framing, not job."
            ),
        ),
        decoy=Pair(
            stem="context_compression_architect",
            relation="same_domain",
            verdict="related",
            listed=False,
            why=(
                "Adjacent and genuinely different: compressing what is already in the window is "
                "not deciding what should persist beyond it. Drawn from the `agent_*` block, which "
                "corpus.py calls the densest cluster of near-identical documents in the library — "
                "exactly one triplet comes from there, and it is this one."
            ),
        ),
    ),
    Triplet(
        id="t03",
        topic="tutoring a student through a subject",
        incoming="socratic_tutor",
        twin=Pair(
            stem="Mr_Ranedeer",
            relation="same_task",
            verdict="same",
            listed=True,
            why=(
                "Both sit opposite one student and teach any subject by questioning rather than "
                "lecturing. One states the method in prose, the other encodes it as a "
                "configuration block with a communication style set to Socratic. Same job, "
                "radically different surface."
            ),
        ),
        decoy=Pair(
            stem="Adaptive_Learning_Designer",
            relation="same_domain",
            verdict="related",
            listed=False,
            why=(
                "Different audience, which is the axis the adjudicator is told to check third. "
                "This one advises an institution on curriculum and learning-analytics design; it "
                "never speaks to a learner. A tutor swapped for a designer leaves the student with "
                "a programme specification."
            ),
        ),
    ),
    Triplet(
        id="t04",
        topic="reviewing application code for security defects",
        incoming="code_reviewer_security",
        twin=Pair(
            stem="owasp_secure_application_architect",
            relation="candidate_broader",
            verdict="supersedes",
            listed=True,
            why=(
                "The stored prompt reviews code for the same vulnerability classes AND designs and "
                "audits architecture on top. Everything the incoming one handles it handles. "
                "OQ-a case 5, the superset — kept deliberately, because SUPERSEDES surviving the "
                "funnel is asserted nowhere else."
            ),
        ),
        decoy=Pair(
            stem="security_researcher",
            relation="same_domain",
            verdict="related",
            listed=False,
            why=(
                "Threat modelling and vulnerability research is not reviewing a diff. Enormous "
                "shared vocabulary — OWASP, injection, supply chain, cryptography — and a "
                "different deliverable from a different input. The pair that punishes any ranking "
                "that trusts term overlap."
            ),
        ),
    ),
    Triplet(
        id="t05",
        topic="stripping AI tells out of written prose",
        incoming="humanizer",
        twin=Pair(
            stem="stop_slop",
            relation="same_task",
            verdict="same",
            listed=True,
            why=(
                "Take supplied prose, return the same prose with machine-sounding patterns "
                "removed. One calls them signs of AI writing, the other calls them slop. As close "
                "to a true duplicate as the library holds, and the words barely overlap."
            ),
        ),
        decoy=Pair(
            stem="talk_normal_enabler",
            relation="same_domain",
            verdict="related",
            listed=False,
            why=(
                "A different input contract, not a different topic. The twin is an editor over "
                "text somebody supplies; this is a standing directive governing how the assistant "
                "writes its own replies. It takes no document and returns no edit. Released as a "
                "duplicate it would silently reconfigure an assistant's voice."
            ),
        ),
    ),
    Triplet(
        id="t06",
        topic="running production cloud-native platforms",
        incoming="kubernetes_specialist",
        twin=Pair(
            stem="platform_engineer_iac",
            relation="same_task",
            verdict="same",
            listed=True,
            why=(
                "DISPUTED, and kept for that reason (§7). Both own the production platform layer — "
                "designing it, deploying onto it, operating it, declaring it as code. Read "
                "narrowly the objects differ: clusters versus the internal developer platform "
                "around them. Two reasonable reviewers split here, and the rule adopted is that a "
                "difference of emphasis within one deliverable is not a different job."
            ),
        ),
        decoy=Pair(
            stem="terraform_iac_specialist",
            relation="candidate_narrower",
            verdict="related",
            listed=False,
            why=(
                "One tool inside the job rather than the job. Writing and diagnosing Terraform is "
                "part of what the anchor does; a prompt scoped to it cannot stand in for the whole. "
                "Narrower must never resolve to `same`, or the registry starts recommending that "
                "somebody replace a platform practice with a single provider's DSL."
            ),
        ),
    ),
    Triplet(
        id="t07",
        topic="writing and tuning relational queries",
        incoming="sql_assistant",
        written=True,
        twin=Pair(
            stem="sql_assistant",
            relation="same_task",
            verdict="same",
            listed=True,
            why=(
                "A deliberate paraphrase of the anchor: same dialects, same three deliverables "
                "(compose, tune, lay out tables), same refusal to guess at an unseen schema — "
                "written to share as little wording as the job allows. Vocabulary is the only "
                "moving part, which is the variable the product failed on."
            ),
        ),
        decoy=Pair(
            stem="database_schema_designer",
            relation="candidate_narrower",
            verdict="related",
            listed=False,
            why=(
                "Schema design is one of the three things the anchor does, taken alone and taken "
                "deeper. Substituting it loses query authoring and tuning entirely."
            ),
        ),
    ),
    Triplet(
        id="t08",
        topic="clinical decision support at the point of care",
        incoming="clinical_assistant",
        written=True,
        twin=Pair(
            stem="clinical_assistant",
            relation="same_task",
            verdict="same",
            listed=True,
            why=(
                "Same two deliverables — a ranked differential with can't-miss conditions "
                "surfaced, and a four-part encounter record — for the same reader, under the same "
                "PHI restriction, with none of the same terminology."
            ),
        ),
        decoy=Pair(
            stem="healthcare_operations_agent",
            relation="same_domain",
            verdict="related",
            listed=False,
            why=(
                "Same setting, administrative rather than clinical work: prior authorisation, "
                "claim appeals, message triage. Shares HIPAA, patient, clinical documentation — "
                "and reasons about payer rules, never about what the patient has."
            ),
        ),
    ),
    Triplet(
        id="t09",
        topic="legal research and contract analysis",
        incoming="legal_analyst",
        written=True,
        twin=Pair(
            stem="legal_analyst",
            relation="same_task",
            verdict="same",
            listed=True,
            why=(
                "Same pair of outputs — a sourced answer on a question of law, and a provision-by-"
                "provision read of an executed agreement — same subordinate posture behind a "
                "qualified lawyer, same insistence that every proposition carries its authority."
            ),
        ),
        decoy=Pair(
            stem="Contract_Negotiation_Strategist",
            relation="same_domain",
            verdict="related",
            listed=False,
            why=(
                "Same object, forward-looking action. Analysing an executed agreement and "
                "structuring a deal not yet signed are different work for different readers at "
                "different points in time, over near-identical vocabulary."
            ),
        ),
    ),
    Triplet(
        id="t10",
        topic="writing prompts for generative image models",
        incoming="generative_image_prompt_engineer",
        written=True,
        twin=Pair(
            stem="generative_image_prompt_engineer",
            relation="same_task",
            verdict="same",
            listed=True,
            why=(
                "Same job: a described picture in, model-specific instruction text out, with the "
                "optical and lighting reasoning that makes it steerable. Written to avoid the "
                "anchor's phrasing throughout."
            ),
        ),
        decoy=Pair(
            stem="flux_image_gen",
            relation="candidate_narrower",
            verdict="related",
            listed=False,
            why=(
                "A fill-in template for one model family, not a prompt that reasons about a "
                "described image across models. Substituting it silently drops every other target "
                "model — the kind of narrowing that only shows up in production."
            ),
        ),
    ),
)


def twin_text(triplet: Triplet) -> str:
    """The written paraphrase for a ``written`` triplet.

    Kept as files under ``twins/`` rather than as literals here for the same
    reason the corpus is files: these are multi-paragraph prompts, and a diff
    over a Python string literal is unreadable. They live outside
    ``playgrounds/prompts`` deliberately — the corpus loader reads that directory
    and would otherwise seed the paraphrases into the very library they are meant
    to be searched against.
    """
    if not triplet.written:
        raise ValueError(f"{triplet.id} takes its incoming body from the corpus, not from twins/")
    return (_TWINS / f"{triplet.incoming}.txt").read_text(encoding="utf-8")


def required_stems() -> frozenset[str]:
    """Every corpus stem the set names, for ``corpus.load_corpus(required=...)``.

    Mirrors `golden.required_stems`. A triplet whose decoy was not loaded scores
    as if the decoy had been correctly refused, which would read as a pass — so
    the corpus slice has to be pinned rather than hoped for.
    """
    stems: set[str] = set()
    for triplet in TRIPLETS:
        if not triplet.written:
            stems.add(triplet.incoming)
        stems.update(pair.stem for pair in triplet.pairs)
    return frozenset(stems)
