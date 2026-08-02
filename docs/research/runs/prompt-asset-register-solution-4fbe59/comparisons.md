# Cross-locus reconciliation — prompt-asset-register-solution-4fbe59

Six depth investigators returned committed positions. This document names the tensions
BETWEEN those positions — the places where two well-evidenced conclusions pull against each
other — and tells the drafters how to engage each one. A draft that reports the six positions
serially without engaging these five tensions has missed the argument.

**Corrections established during depth investigation (binding on all downstream steps):**

1. The figure "prompt duplication affects 23.9% of repositories", which the orchestrator
   passed down from a search snippet, **does not appear in the paper**. The registry-decay
   investigator read the full text and recovered four distinct figures: internal exact
   duplication 13.0% (12/92 repos), internal semantic duplication 30.4% (28/92), external
   exact 16.3% (15/92), external semantic 34.8% (32/92), plus a prompt-level semantic
   duplication figure of 38.5% (9,553/24,800). **Use these; never use 23.9%.**
2. The drift statistic 84%→51% is **confirmed**: GPT-4 prime-number identification, March→June
   2023, Chen, Zaharia & Zou (2024), *Harvard Data Science Review*. The same study reports
   code-execution success falling 52%→10%. Attribute to Chen et al., not to the blogs that
   relay it.
3. The Vietnamese transition period the orchestrator described as "12–18 months" was not what
   the investigator found in Decree 142/2026/ND-CP: the provision located was a **60-day
   notification deadline (before 30 June 2026)** to submit a transition plan. The "passed 10
   Dec 2025" date was also uncorroborated in the two Vietnam sources read. Treat both as
   unverified; four further Vietnam sources sit unread in the corpus.
4. `rubber-stamp-reviews-minware` contains **no quantified review-size threshold**. The
   "400/1000 line" figures circulating in the orchestrator's search notes came from a different
   source and must not be attributed to it. Recorded as an audited absence.
5. The "5–20% train/test accuracy gap" attributed to Evidently was **not found** in that
   source. Audited absence.

---

## Tension 1 — The promote gate is carrying four jobs, and only one of them fits in two minutes

**This is the keystone tension of the whole report.** Four loci independently converged on the
promote-approval moment as the place where their problem gets solved — without coordinating,
and without noticing they were all loading the same beam.

- **eval-gate** concludes the human approver is *not ceremonial*: since automated judging is
  statistically indistinguishable from noise (ρ≈0, CI spanning zero) on the holistic-copy task
  class this product's users actually produce, the human is "the only mechanism in the pipeline
  capable of exercising the judgment the eval literature shows automation cannot supply."
- **registry-decay** concludes the promote step is the *only natural capture moment* for the
  semantic fields (purpose, canonicalization judgment, deprecation rationale) that cannot be
  auto-derived — proposing a two-click confirm/edit of an AI-drafted field folded into the
  approval, precisely to avoid creating a separate stewardship task.
- **agent-scope** concludes the evidence card is the mechanism that keeps the gate from
  decaying into rubber-stamping, and that the agent's proposals must arrive *as* evidence
  cards rather than as raw diffs with self-narrated rationales.
- **promote-gate** concludes the gate survives DORA's critique only if the approver is an
  accountable owner supplied with *pre-computed* evidence rather than expected to reconstruct
  it — i.e. the card must do the reasoning work in advance.

**And pulling directly against all four: adoption** concludes the mandatory wall must appear
"exactly once, at promote-to-production, and nowhere else in the flow", because the dominant
day-one failure mode is "the official system adds more steps than it removes."

**The tension:** every locus agrees the gate should exist once; they disagree implicitly about
how much can be stacked on that single moment. Reading a judge score, exercising subjective
judgment automation cannot supply, confirming AI-drafted semantic metadata, checking cost and
blast radius, and doing it in two minutes are not obviously compatible. The registry-decay
investigator flagged this himself, pointing at the rubber-stamp literature and asking whether
approval-time confirm/edit fields "actually get filled with real judgment or rubber-stamped."

**Engagement guidance:** do not resolve this by asserting the card is well-designed. Resolve it
by *ordering and defaulting*: state which of the four jobs is load-bearing enough to block on,
which can be pre-filled with a safe default the approver only overrides, and what the card
looks like when the approver does nothing but click approve. If the honest answer is that the
semantic-capture job degrades under load, say so and propose the fallback (e.g. capture it only
on first promotion of a new prompt, not every version). The draft is stronger for naming the
overload risk than for pretending four jobs fit in two minutes.

---

## Tension 2 — Zero-labor ingestion manufactures the exact decay the register exists to prevent

A direct, clean collision between two committed positions.

- **adoption** is unambiguous that day one is won by mass, zero-labor ingestion: the first
  session must show the user "*their own* existing prompts already deduplicated and browsable,
  never a blank state demanding manual entry", and if the tool cannot do this within roughly
  60 seconds the win condition is unreachable.
- **registry-decay** states the boundary condition that breaks it: the two-tier scheme works
  only "for a register whose promote-approval action is genuinely mandatory and genuinely
  touches every version that matters — if a meaningful share of prompts never go through a
  promote gate (e.g. prompts imported in bulk during the initial migration sweep), Tier 2
  fields for *those* records have no natural capture moment and will start stale."

**The tension:** the flagship differentiator (bulk import everything, ask nothing) produces a
register whose majority population has never passed the one moment where meaning gets captured.
On day 30 the register is large, browsable, and semantically empty — which is precisely the
condition the data-catalog sources identify as the onset of trust collapse.

**Engagement guidance:** this must be engaged head-on, not resolved by hand-waving about
"progressive enrichment." Options worth weighing in the draft: import into a distinct
*unadopted* state that is visibly not part of the governed ledger until someone claims it;
make first *use* (not first promotion) the capture trigger for imported records; or accept a
two-population register and design the UI so the ungoverned population cannot be mistaken for
the governed one. Take a position. Note that this tension also supplies the honest answer to
"is the register a destination or a capability" — the adoption investigator split on exactly
this, arguing the ledger must be a destination while the *capture surface* must be embedded.

---

## Tension 3 — The evidence for the product is weaker than the evidence against it

An asymmetry that runs across every locus and must be stated plainly rather than buried.

- The **positive** case rests on: a premise the registry-decay investigator judged *asserted,
  not measured* for this setting (the GitHub study samples public prompt-collection repos —
  72.8% of its corpus — where cross-repo duplication plausibly reflects benign convergence on
  popular public prompts rather than organizational waste); adoption evidence that is
  analogically transferred from CRM, data-catalog and campaign-tracker contexts with "no
  controlled or N-reported study, none addressing prompt registers specifically"; and a
  differentiating ingestion capability for which *no source shows any competitor doing it* —
  which is an argument for novelty, not for efficacy.
- The **negative** case rests on: MLflow reversing its own lifecycle design after user
  feedback, CMDB field-ownership rot, data-catalog adoption failure, and feature-store
  scepticism — all disinterested, all from mature categories, none selling this product.

**Engagement guidance:** the draft must not present the positive case with the confidence the
negative case earns. The correct move — and it is a strengthening move, not a hedge — is the
*a fortiori* argument the registry-decay investigator supplied: the GitHub study measures a
git-structured population with version control, code review and searchable history, and still
finds 30.4% of repositories carrying internal semantic duplication. A population living in
Sheets, Notion, Drive and chat threads has none of those affordances, so duplication is very
likely *at least as bad*. That reasoning is honest, it does not overstate the source, and it
gets the premise where it needs to go without pretending the measurement was taken.

---

## Tension 4 — Two of the four hard constraints cannot be honoured as literally written

Two loci independently found that a stated constraint is not satisfiable in the form given.

- **eval-gate:** "regression eval to ensure no quality degradation" cannot be honestly
  implemented as a single automated verdict. Judge agreement caps around 60–71% under
  best-effort debiasing on general tasks and collapses to ρ≈0 on holistic copy; and drift is
  structurally invisible to any pre-release gate — Chen et al.'s 84%→51% and 52%→10% collapses
  happened with no version change at all. The verdict: *block* only on deterministic,
  code-checkable contract properties; *report* subjective quality as advisory; and *monitor*
  by re-running the same contract on a schedule against the live model.
- **promote-gate:** the mandatory HITL requirement has no statutory basis for this platform.
  Neither the EU AI Act as read nor Vietnam's Law 134/2025/QH15 with Decree 142/2026/ND-CP
  obliges a pre-release human sign-off for an *internal prompt-management layer* — they
  regulate the deployed AI system's documentation, logging and runtime human-intervention
  capacity. The honest basis is ordinary segregation-of-duties corporate governance plus
  prophylactic readiness for the group's downstream products.

**They also agree on something important:** both conclude the constraint should be *kept*, in
a redesigned and honestly-described form. Neither recommends dropping it.

**Engagement guidance:** this is where the report earns its credibility. Reframe both
constraints precisely rather than either satisfying them nominally or discarding them. The
resulting three-part eval rule (block on contract / report on quality / monitor for drift) is
a *better* answer than the constraint as written, and the governance-not-statute basis for HITL
is more durable than a legal claim that would not survive counsel review. Say both plainly, and
say why the reframing is stronger. Do not let EU AI Act citations imply an obligation that does
not bind.

---

## Tension 5 — Scope discipline versus differentiation: how thin can the layer actually be?

- **build-vs-layer** commits, with high confidence, to a minimal built surface: exactly four
  bespoke components (cross-provider asset schema, approval-decision object, per-runtime push
  adapters, OTel telemetry ingestion on non-content attributes), explicitly declining to
  rebuild prompt storage, editing UI, or a caching layer — because vendors already meet a
  reliability bar (TTL caching, stale-while-revalidate, Redis+DB fallback, startup prefetch,
  hardcoded fallback) "this team cannot match on a short timeline."
- But **agent-scope** makes the ingestion/clustering agent *the lead differentiator* — a fifth
  bespoke surface. And **adoption** requires embedded capture surfaces (browser extension,
  forward-to-bot) or "the register will re-accumulate the exact shadow-workflow problem it
  launched to solve within weeks" — a sixth and seventh.

**The tension:** the thin-layer discipline is well-argued and the maintenance economics behind
it are real, but the three things that make this product *distinctive* all sit outside the four
sanctioned surfaces. A layer thin enough to be maintainable may be too thin to be worth
adopting.

**Engagement guidance:** resolve by sequencing rather than by arbitration. The build-vs-layer
position is about what to build *durably*; the differentiators can be built first and thinly.
Note the honest convergence available here: the approval-decision object is simultaneously
build-vs-layer's sanctioned surface, promote-gate's confirmed market gap ("no vendor across
Langfuse, PromptLayer, or Bedrock ships a pending-review/evidence-record/rejection-path
object", confirmed to database-schema granularity in Langfuse's case), and agent-scope's output
target. One component satisfies three positions — that is the report's strongest single
architectural claim and should be stated as such. Also carry forward build-vs-layer's named
uncompensated cost: label-based versioning has no branch/merge semantics, so divergent edits
become colliding linear versions or near-duplicate assets that only clustering catches after
the fact.

---

## Convergences worth asserting without hedging

Where the loci agree independently, the draft should be confident:

1. **Operational register fields must be auto-derived from actions already being taken** —
   owner from who promoted, current-production pointer from the promote action (MLflow's
   alias-reassignment pattern, not a manually-set stage flag), usage from SDK fetch calls, cost
   from traces, last-used from telemetry. Three adjacent domains converge on this without
   citing each other.
2. **No existing tool ships a real approval-decision object.** Promotion everywhere is a
   role-gated write to a label or version pointer. Four independent vendor sources, fully
   convergent.
3. **A pre-release gate cannot see drift.** Independently established by four sources across
   peer-reviewed and practitioner literature.
4. **The permission boundary belongs around the eval contract, not only the prompt text.**
   eval-gate argues this from the criteria-drift finding; agent-scope's gating design assumes
   it. Prompt-text editing stays open to non-developers; threshold and critical-category edits
   need a stricter reviewed role.
5. **Cost must be measured end-to-end, not as prompt length.** Promoted directly from the
   contradiction graph (a logged case where a ~17% input-token cut raised total session cost
   ~67% because the model paid to recover stripped meaning). No locus disputes it.

## Open gaps the drafters must not paper over

- No source measures non-technical adoption of any AI-artifact register empirically.
- No source studies LLM-judge validity on marketing or ad copy specifically; essay marking is
  the closest available proxy and the analogy should be labelled as such.
- No Vietnam- or conglomerate-specific evidence on organizational approval hierarchy, or on
  whether Zalo rather than Slack is the real incumbent chat channel.
- Four Vietnam legal sources remain unread; the jurisdictional conclusion rests on two.
- The full text of the textual-gradients critique was never fetched; its argument is taken at
  abstract level.
