# Orchestrator notes — prompt-asset-register-solution-4fbe59

## Environment deviation (recorded for provenance)

The `hyperresearch-fetcher` subagent type is defined with a Bash tool, but on this
Windows/PowerShell host the subagents receive only Read/Write/WebSearch — no shell of any
kind. All 11 wave-1 fetchers reported the same blocker; four returned before I stopped the
rest. **No fabricated notes were produced by any of them** — each correctly refused to invent
note IDs, which is the right call and preserved the vault's provenance model.

**Workaround adopted:** the orchestrator drives `hyperresearch fetch` directly from
PowerShell (which does work — verified against dora.dev before committing to this path), in
three parallel slices. Notes land as real vault files under `research/notes/`, which
downstream subagents CAN read with the Read tool. So the pipeline's structure survives; only
the *ingestion mechanism* moved from subagent to orchestrator. Claims-extraction, which
fetchers would normally have done per-source, will have to be folded into steps 5/9 by agents
reading the note bodies from disk.

**Consequence to watch:** fetchers normally chase 3–8 primary sources per batch via citation
chains. That agency is lost with centralized fetching. Step 8 (corpus critic) and step 13
(gap fetch) become more load-bearing than usual — they are now the *only* citation-chasing in
the run. One lead already surfaced this way and was added to slice A: **arXiv:2509.12421,
"Understanding Prompt Management in GitHub Repositories"** (24,800 prompts across 92 repos,
reporting formatting inconsistency, internal/external duplication, readability/spelling
issues). If that holds up it is the single strongest empirical anchor for the whole premise —
it is the only non-vendor, non-assertion evidence found so far that the "prompts are scattered
and duplicated" starting state is real and measurable rather than a pitch narrative.

## What the corpus is shaping up to say

**The premise is well-evidenced but almost entirely by vendors.** Every source in the asset-
framing cluster converges on the same skeleton — owner, intent/use case, version history,
approval before production, RBAC on edit, eventual retirement. That convergence is suspicious
rather than reassuring: consultancies and tool vendors have an obvious interest in the
conclusion "you need a governance layer." The convergence is worth reporting, but the report
should say plainly that it is convergence *of interested parties*, and lean the actual
argument on the adjacent-category evidence, which is disinterested.

**The strongest tension in the run is going to be the HITL constraint.** The problem statement
makes human approval to promote MANDATORY. DORA's research says formal approval by an external
body correlates with materially worse delivery performance (~2.6x more likely to be low
performers) and shows *no* evidence of lower change-failure rates; its recommendation is peer
review plus automation instead. That is a head-on collision with a stated hard constraint.
The honest resolution is probably not "drop HITL" — the EU AI Act's record-keeping and
traceability obligations, and the fact that a marketer-authored prompt reaching production is
a different risk class from a code change, both cut the other way. The resolution is more
likely **what KIND of approval**: DORA's finding is specifically about *external* bodies
reviewing changes they lack context on. An approval by the accountable owner, pre-loaded with
evidence, is closer to peer review than to a CAB. That distinction is the argument, and it
directly justifies the "two-minute evidence card" design rather than merely decorating it.

**The second tension: can the eval gate honestly be called a guarantee?** The constraint says
regression eval "to ensure no quality degradation." The judge literature says agreement with
humans is strongly task-dependent — high (κ ~0.9+) on objective/verifiable tasks, mediocre
(κ ~0.23–0.36) on subjective satisfaction judgments where even humans only reach ~0.34. The
product's primary users are marketers and designers, i.e. exactly the subjective end. So the
gate is most trustworthy precisely where this product needs it least, and least trustworthy
where it needs it most. Add self-preference bias being embedded in representations and
unresponsive to prompt-level instruction, and "guarantee" is not defensible. What IS
defensible: a gate that blocks on *verifiable* properties (schema, required disclaimers,
forbidden claims, length, latency, cost) with high confidence, and reports subjective quality
as a *signal to the human approver* rather than an automated verdict. That maps cleanly onto
the two-minute card and makes the HITL requirement load-bearing rather than ceremonial — the
human is there precisely because the judge cannot be trusted on the subjective axis.

**The third tension: prompt regression vs. prompt drift.** A pre-release gate structurally
cannot catch drift, because nothing changed on the deployer's side. Any claim that the
platform "ensures no quality degradation" is therefore false by construction for the largest
single cause of degradation. The arXiv "Test Before You Deploy" framing (production contracts
/ risk-category suites / compatibility gates) plus scheduled baseline re-runs is the honest
answer, and it strengthens the asset-register framing rather than weakening it: an asset with
a recorded expected behaviour is exactly the thing you can re-test on a schedule. Drift
detection is arguably a *better* argument for the register than versioning is.

**The fourth tension: does centralization survive its own coordination cost?** CMDB decay
within ~18 months of go-live where CI retirement isn't tied to lifecycle events; data catalogs
failing on stewardship decay and over-technical interfaces; MLflow *deprecating* fixed stages
after feedback that they were too inflexible; "you still don't need a feature store." This is
a consistent, disinterested body of evidence that registries rot when maintenance is a
separate act of virtue from doing the work. It is the single most important input to the
design: **every field in the prompt asset record must be derivable from an action someone was
going to take anyway, or it will be stale within two quarters.** Owner should come from who
promoted it, usage from the SDK's own fetch calls, cost from the traces, last-used from
telemetry. Anything requiring a human to remember to update it is a future ghost asset. This
should probably be stated as an explicit design law in the report.

## Structural note for step 10/11

The 12 required headings are in place, but the argument has a natural spine that cuts across
them and the drafters should be told it: **the register is only as good as the fields it can
populate without asking anyone to maintain it.** Ingestion (§3) populates it from the existing
mess; distribution (§8) is what keeps usage/cost fields live; the gate (§6, §7) is what
attaches evidence to each version. Framed that way, the three USP pillars aren't three
features — they're the three points where the ledger gets written to automatically. That is a
much stronger thesis than "we built a nice registry," and it survives the CMDB critique
instead of ignoring it.

## Post-step-3 update

Independence check came back nearly clean: 96 sources, exactly **one** syndication cluster
(the two EU AI Act article pages). So the corpus is genuinely multi-voiced, and the vendor-
convergence problem in the asset-framing cluster is a *provenance* problem, not a syndication
problem — those sources really are separate organizations independently arriving at the same
conclusion. That is weaker than independent corroboration (they share an interest) but
stronger than one press release being reprinted seven times. Worth stating precisely in the
draft; the distinction matters.

Nine fight clusters emerged, all scoring high on decision relevance, which is unusual and tells
me something about the question: almost every design decision in this platform sits on top of a
genuine evidentiary fork. That argues for a draft that is structured around *defended choices*
rather than around *feature descriptions*. Each of the 12 required sections should end up
resolving at least one fork rather than enumerating capabilities.

Three of the nine clusters dissolve on inspection into scope confusions rather than real
disagreements — approval gates (external reviewer vs. accountable owner), eval reliability
(objective vs. subjective task), and cost (prompt tokens vs. end-to-end session cost). Those
are the most valuable ones for the report, because dissolving a confusion produces a design
rule, not a hedge. The remaining six are real and at least one of them (registry decay) has
evidence weighted heavily against the product's own premise.

## Open questions for loci analysis (step 4)

1. Is there any disinterested evidence that a prompt registry improved an outcome, or is the
   entire positive case vendor-authored? (Audited absence is a legitimate finding here.)
2. What is the actual defensible scope of an automated quality gate for subjective tasks?
3. Does the non-developer-primary choice survive contact with the RBAC/approval requirement,
   or does it collapse into "non-developers propose, engineers approve" — which is what the
   incumbent tools already do?
4. Given Bedrock/Vertex/Langfuse ship the versioning primitives for free, is the register's
   defensible core the *cross-vendor, cross-product ledger* rather than any single feature?
5. What does the GitHub-repos prompt study actually measure, and does it support or undercut
   the duplication claim the ingestion pillar rests on?
