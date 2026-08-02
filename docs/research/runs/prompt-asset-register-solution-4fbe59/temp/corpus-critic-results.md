# Corpus critic results — prompt-asset-register-solution-4fbe59

## Method note

The environment for this step has no shell/search tool -- only Read/Write. I could not
enumerate `research/runs/.../interim/*.md` (no directory-listing capability and no filename
convention I could recover by guessing), so I worked from `comparisons.md`,
`temp/source-tensions.json`, `loci.json`, and `temp/coverage-gaps.md`, which between them quote
every committed position, its evidence, its boundary conditions, and its self-declared gaps in
enough depth to do the adversarial pass. Where the task asked me to verify a position against
*original* source text rather than the synthesis layer, I read the underlying
`research/notes/<id>.md` files directly (listed below) rather than the interim notes. This is a
genuine deviation from the letter of the instructions and should be visible to whoever reads
this; I judge it did not weaken the pass because the synthesis documents are unusually rich
(they quote figures, name proponents by note ID, and state boundary conditions verbatim), and I
independently re-verified the load-bearing claims against primary sources rather than trusting
the synthesis.

## What I actually did

1. Read `comparisons.md` in full (five tensions + corrections + open-gaps list).
2. Read `temp/source-tensions.json` in full (seven tensions with resolutions).
3. Read `temp/coverage-gaps.md` in full (provenance caveat + audited absences).
4. Read `loci.json` in full (six loci with rationale, evidence lists, skip_loci).
5. Read the four previously-UNREAD Vietnam legal sources in full: Baker McKenzie, Duane Morris,
   Conventus Law, Vietnam Briefing.
6. Re-read the two Vietnam sources the investigator DID use (OneTrust overview, Viet An Law's
   Decree 142 explainer) to cross-check the four new reads against them.
7. Read the textual-gradients arXiv note to confirm the abstract-only status.
8. Read the EU AI Act Article 12 note to confirm Article 14 (Human Oversight) is absent from the
   corpus despite being listed in that same site's table of contents.
9. Read the Bedrock "Create a prompt" doc and the Vertex/Gemini Enterprise prompt-management doc
   to check for cross-account/cross-project aggregation language (none found in either).
10. Read the criterion-referenceability (physics judge-validity) paper's abstract/intro to verify
    the rho~0/rho~0.1 essay-marking figures are quoted accurately in the synthesis layer.
11. Read the Braintrust Loop docs to check whether "production traffic vs static benchmark"
    grounding is stated explicitly (it is not -- confirmed ambiguous).

## Headline finding: the Vietnam jurisdictional gap is now substantially closed, not open

This was flagged as the single largest unclosed gap in the whole run, and the prompt asked me
to judge whether it's findable. It was findable — the four sources were already sitting in the
vault, just unread. Having read them:

- **The core committed position holds and gets stronger.** The Conventus Law piece names the
  actual operative clause (Article 14 of the *Vietnamese* Law -- not the EU AI Act's Article 14 --
  requiring deployers of HIGH-RISK systems to "maintain the possibility of human intervention
  during use"). It is scoped to deployers of *deployed, downstream* high-risk AI systems, not to
  an internal prompt-management/versioning platform. Combined with the Decree's own exemption
  language (already in the corpus, re-read here) for systems that "do not interact with or
  provide services or content directly to the public," an internal prompt register has a
  specific, textual path to low-risk/out-of-scope status rather than the previous general
  inference from "the law regulates deployed systems, not tooling."
- **Two things comparisons.md flagged as uncorroborated are now corroborated.** The 10 Dec 2025
  passage date is stated identically by three additional independent sources (OneTrust, Baker
  McKenzie, Duane Morris). And the "12-18 months" transition figure the orchestrator originally
  passed down is real -- it is the LAW's own grace period for pre-existing systems (distinct from
  the Decree's 60-day notification deadline that the depth investigator found). These are two
  different, both-real provisions; the draft should state both, not treat the 12-18-month figure
  as an error to be discarded.
- **One genuinely open question remains, and no source resolves it:** whether the prompt
  platform (particularly its improvement-agent component, which "generates" content) itself
  meets the Law's broad AI-system definition. This is a legal-interpretation gap, not a sourcing
  gap. I recommend the draft state it as an explicit residual uncertainty rather than search
  further for it -- resolving it would require MOST regulatory guidance that likely does not
  exist yet, given the law took effect five months before this run's "today."
- One reliability flag for the drafters, not a gap to fetch: Vietnam Briefing's article describes
  a **four-tier** risk system (adding an "unacceptable risk" tier by analogy to the EU AI Act),
  while every other source (OneTrust, Baker McKenzie, Duane Morris, and the Decree text itself)
  describes a **three-tier** system (high/medium/low) with a separate list of prohibited acts.
  The article was also first published before the law passed and only lightly updated after, which
  is consistent with it front-running the final text on this specific point. Treat Vietnam
  Briefing as corroborating on dates and general structure but as the least reliable of the four
  on this one detail.

## Other verified-safe findings

- **The essay-marking judge-validity figures are accurately represented.** I read the physics
  paper's abstract/intro directly: rho≈0.1 blind, rho≈0 with a mark scheme (all CIs including
  zero), against rho>0.6 on structured questions and rho>0.84 on plot-grading. This exactly
  matches what comparisons.md and source-tensions.json quote. This is the single most
  decision-relevant piece of evidence in the whole report (it drives the block/report/monitor
  eval-gate design) and it is solid. **Safe.**
- **No vendor ships a real approval-decision object convergence extends to Vertex too.** The
  synthesis names Langfuse, PromptLayer, and Bedrock. I independently read the Vertex/Gemini
  Enterprise prompt-management doc: create/get/list/delete/restore, no pending-review state, no
  approval workflow, no rejection path -- the same shape as the other three. This strengthens an
  already-strong convergence claim to four vendors instead of three. **Safe, and improvable in
  the draft by naming Vertex alongside the other three.**
- **The Bedrock/Vertex single-account scoping claim holds against the two docs actually in the
  corpus** -- but see the AWS RAM / Vertex org-hierarchy gap below, which is the one place this
  claim was asserted rather than adversarially tested.
- **The cost-measurement finding (17% token cut -> 67% cost increase) needs no more sources.**
  The resolution in source-tensions.json is already appropriately narrow ("input-token delta is
  not a valid proxy for cost delta," not "compression doesn't work"), and a single
  well-instrumented practitioner report is adequate evidence for that narrower claim. Searching
  for a second confirming source is not worth the budget. **Safe as scoped.**

## Where I judge an absence is real and should be stated as a finding, not chased further

- **No LLM-judge validity study on marketing/advertising/creative copy.** I could not run a live
  search myself (no tool for it), but given that the width sweep and two depth investigations
  already searched this territory and the corpus's own theoretical finding (criterion-
  referenceability) predicts holistic creative work is exactly the hardest category to study
  rigorously, I judge the prior probability of finding a clean academic study here is low. One
  more targeted search pass is worth running (queries in the JSON) but the draft should be
  prepared to state the absence as a finding rather than wait on it.
- **No N-reported empirical study of non-technical adoption of an AI-artifact register.** Same
  judgment: the coverage-gaps.md audit already searched adjacent "against centralized prompt
  management" territory and found only vendor listicles. A practitioner-post-mortem search is
  worth one more pass but is unlikely to surface a rigorous source; if it doesn't, that absence
  belongs in the draft's honesty section alongside the already-flagged asymmetry (Tension 3).

## Fetch list priorities

Full detail and exact queries are in `corpus-critic-gaps.json`. In descending order of what
would most change the draft if found:

1. **High** -- Vietnam sources: not a new fetch, but the four notes must be read and incorporated
   before drafting (see JSON for the specific reusable findings).
2. **High** -- EU AI Act Article 14 (Human Oversight), single easy fetch, never attempted despite
   Articles 12 and 18 from the same site being in the corpus.
3. **High** -- textual-gradients full text via the `/html/<id>v1` mirror pattern that already
   worked for the physics paper.
4. **High** -- AWS RAM shareable-resource-types and Vertex org/folder hierarchy, to test rather
   than assert the "no cross-account aggregation" premise underneath build-vs-layer.
5. **Medium** -- marketing/creative-copy judge-validity study (one more search pass; likely absent).
6. **Medium** -- non-technical adoption practitioner account (one more search pass; likely thin).
7. **Low** -- Braintrust Loop production-traffic-vs-benchmark grounding clarity.
