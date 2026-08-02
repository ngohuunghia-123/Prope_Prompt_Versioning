# Synthesis plan

Three drafts came back genuinely distinct, which is what the ensemble is for. This plan says
what to take from each, what to arbitrate, and where the drafts conflict.

## What each draft uniquely contributes

**Draft A — "the ledger earns its name"** (~9,000 words). Its deliverable is the thing the
other two gesture at: a concrete four-tier field schema (Tier 0 identity, Tier 1 operational
and 100% auto-derived, Tier 2 semantic and captured inside the promote step, Tier 3 fields the
schema deliberately *refuses*), with each row naming both how the field is populated and what
makes it go stale. Take these tables largely intact — they are the report's spine made
concrete. A also specifies the approval-decision object field by field, and adds an
`ai-drafted` vs `human-confirmed` provenance flag that lets the product measure its own
rubber-stamping rate. That flag is a genuinely good answer to a question no source resolves.

**Draft B — "build the smallest thing that cannot be bought"** (~8,200 words). Its deliverable
is the keystone argument: the approval-decision object is simultaneously the confirmed market
gap, the sanctioned bespoke surface under an honest build/buy test, and the agent layer's
output target — one component satisfying three independently derived requirements. B also found
evidence nobody else did: Langfuse's own capability table marks "Multi-step approval workflow"
as *Composed* rather than Native and states it does not ship a built-in pull-request-style
approval flow for prompt promotions. **That converts the market-gap claim from a survey
inference into a vendor's own admission and must survive into the final report.** B also makes
an honest self-correction worth keeping: because label-based versioning cannot merge, duplicate
clustering is a permanent operational control rather than onboarding sugar — arguably a fifth
durable surface on B's own logic.

**Draft C — "it only counts if the marketer uses it on Monday"** (~8,900 words). Its deliverable
is the single best insight in the run, and it belongs in the final report prominently: because
judge rank-agreement collapses on holistic work, the subjective signal must be rendered as
*adjudicable evidence* — three to five real production inputs where old and new outputs diverge
most, side by side — rather than as a score. The judge is used only to **select which examples
to surface**, which is a retrieval task rather than a ranking task, and therefore is not subject
to the validity collapse that makes scoring dishonest. This resolves the eval literature, the
non-engineer persona, and the two-minute card into one concrete UI decision. Take it whole.

## Convergences — assert these confidently

All three drafts arrived independently at:

1. **The two-population register.** Bulk-imported prompts land in a visibly separate,
   ungoverned state; they are excluded from governed statistics; the front page reports
   something like "412 discovered, 38 governed" rather than a single inflated asset count.
   A and C both reached this; C adds first *use* rather than first promotion as the capture
   trigger, and instrumentation on the purpose-field edit rate so the design falsifies itself
   from telemetry. Merge these into one treatment — it is the resolution of Tension 2 and the
   most credibility-generating move available in a demo.
2. **Block on contract / report as advisory / monitor for drift.** No draft claims a guarantee.
3. **The approval object is greenfield across every surveyed vendor.**
4. **Mandatory HITL rests on segregation of duties, not statute.**
5. **The evidence asymmetry is stated plainly in all three.** Keep it stated once, well, near
   the top and again in the closing synthesis — not repeated in every section.

## What to arbitrate

- **Minimum surface count.** B says four bespoke surfaces, then concedes a fifth. A's schema and
  C's capture surfaces imply more. Resolve by B's own sequencing logic: distinguish what is
  built *durably* from what is built *thinly and first*, and state the count honestly as
  "four durable plus dedup-clustering as a standing control", not as a tidy four.
- **Where the ingestion agent sits.** B's discipline excludes it; A and C treat it as the lead
  differentiator. The honest resolution is that it is differentiating AND unproven — no source
  shows a competitor doing it, which is an argument for novelty rather than efficacy. Say both.
- **Tone toward the premise.** A is most willing to say the framing is a falsifiable commitment
  that could fail; C is most willing to say adoption evidence is analogically transferred. Keep
  both admissions; they are what make the recommendation credible.

## Length and shape

Target **8,500–9,500 words** (profile band for `argumentative` is 5,000–10,000). The three
drafts total roughly 26,000 words, so this is a genuine synthesis with heavy compression, not a
merge. Cut: repeated statements of the evidence asymmetry, competitor-mechanism recaps beyond
what the argument needs, and any section that restates the source tensions already covered in
the dedicated section.

## Citations

Drafts cite as `[note-id]`. **Keep that format in the synthesized report.** The orchestrator
runs a deterministic renumbering pass afterwards that converts every `[note-id]` to a numbered
`[N]` and generates the `## Sources` list from the vault index. Do not attempt to number
citations yourself and do not write a Sources section — it will be generated.
