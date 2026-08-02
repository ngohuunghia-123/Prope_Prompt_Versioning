# Scaffold — prompt-asset-register-solution-4fbe59

> PRIVATE PLANNING DOCUMENT. Must NOT appear in the final report in any form.

## User Prompt (VERBATIM — gospel)

```
on how to solve this problem, with main value is "Sổ tài sản prompt của tập đoàn"
```

The prompt is anaphoric ("this problem"). The referent is captured in
`research/runs/prompt-asset-register-solution-4fbe59/query.md` under the clearly-labelled
context block. Every subagent receives that whole file verbatim.

## Run config

| Field | Value |
|---|---|
| vault_tag | `prompt-asset-register-solution-4fbe59` |
| query_file_path | `research/runs/prompt-asset-register-solution-4fbe59/query.md` |
| run_dir | `research/runs/prompt-asset-register-solution-4fbe59/` |
| profile / gear | `full` |
| pipeline_tier | *(filled in after step 1)* |
| modality | `synthesize` (secondary current: `compare`) |
| budget_usd | none set |
| wrapper contract | none (`research/prompt.txt` and `research/wrapper_contract.json` both absent) |

## Modality classification rationale

**Primary: synthesize.** The ask is "how to solve this problem" with the central value
proposition *held fixed* — "Sổ tài sản prompt của tập đoàn" is a constraint, not an open
question. So the deliverable is not an enumeration of prompt-management options; it is a
**defended argument for a particular way to build the thing**, with evidence chains running
from the constraint (asset-register framing, non-developer primary user, HITL promote gate,
regression eval, cost alerting) to concrete mechanism (data model, ingestion, eval
bootstrapping, promote gate, distribution layer, adoption sequencing).

**Secondary: compare.** Several load-bearing forks are genuinely comparative and need
proportionate per-option depth plus a committed recommendation:
- build-on-top-of vs. build-beside vs. replace the existing runtime prompt stores
  (Bedrock / Vertex Prompt Management / Langfuse / OTel);
- prompt-as-code (git-native, dev-owned) vs. prompt-as-content (CMS-native, non-dev-owned)
  — the positioning commits to the second, and that commitment has real costs to defend;
- what "asset" actually means operationally (ownership + lifecycle + valuation) and which
  of the available accounting analogies survives contact with prompts.

Not `collect` (not an enumeration task), not `forecast` (no time-horizon prediction is the
deliverable, though vendor-commoditization risk is a live sub-question).

## Tier rationale

**Classified `full` + `argumentative` + `citation_style: inline`.** (Step 1 complete.)

The query is a solution-design ask spanning six distinct problem surfaces — asset data model,
ingestion of scattered prompts, release/rollback mechanics, regression eval methodology, HITL
governance, and cost control — plus a competitive-defence and an adoption question. It cannot be
answered by a survey: it has to commit to positions on forks where the evidence genuinely
diverges (prompt-as-code vs. prompt-as-content; whether LLM-as-judge regression eval is reliable
enough to block a release; whether a centralized registry survives its own coordination cost;
build vs. buy vs. layer against Bedrock/Vertex/Langfuse). Those live disagreements are exactly
what the contradiction graph, loci analysis, and cross-locus reconciliation exist to handle, so
tiering down to `light` would strip the machinery the question most needs.

`argumentative` follows from the same reasoning — the deliverable is a defended design, and
several sections must engage counter-evidence head-on rather than report around it.
`inline` citations were chosen over the wikilink default because this report feeds a team-facing
product document that will be read outside this vault.

Register was set to `analyze` at **low** confidence: "how to solve this problem" carries an
advocate signal (recommend a course of action), but the deliverable evaluates real forks, and
the confidence rule resolves mixed signals to the `analyze` default rather than deviating.
`inference_depth` is `deep` — prompt-registry-specific evidence is thin and largely vendor-
authored, so the answer requires inference across adjacent mature categories (model registries,
data catalogs, feature flags, change-approval research) and gray literature.

Pre-step-1 expectation, retained for the record: this should classify `full`. The question is multi-part
(architecture + governance mechanism + adoption strategy + differentiation defence), has
genuine live disagreements in the literature (prompt-as-code vs. prompt-as-content;
whether centralized prompt registries are worth their coordination cost; whether
LLM-as-judge regression eval is trustworthy enough to gate releases), and the answer has
to commit to positions rather than survey them.

## Wrapper requirements

None. No `research/prompt.txt`, no `research/wrapper_contract.json`.
Defaults apply:
- save path: `research/notes/final_report_prompt-asset-register-solution-4fbe59.md`
- citation format: pipeline default
- terminal sections: pipeline default

## Standing context the pipeline must respect

1. **The positioning is fixed input, not an open question.** `docs/product/positioning.md`
   in this repo records the committed positioning. The research serves it. Where evidence
   contradicts the positioning, that contradiction is *valuable* and must be surfaced
   explicitly (it is a dialectical locus), but the report may not quietly re-position the
   product.
2. **Two audiences at once.** The answer must be actionable for a small team building a
   demo on a Python / LangGraph / FastAPI / Docker template on a hackathon timeline, AND
   defensible as an enterprise architecture for a real conglomerate.
3. **Vietnamese-language product, English-language research corpus.** Key term:
   *Sổ tài sản prompt* = prompt asset register/ledger. The final report follows the
   pipeline's language default; the Vietnamese anchor phrase stays intact where quoted.
4. **Prior conversation established a competitive landscape** (PromptLayer, Langfuse,
   LangSmith, Braintrust, Vellum, Bedrock/Vertex/Azure native prompt management, and the
   real incumbent: Google Sheet / Notion / Drive). That landscape is a starting point for
   the width sweep, not a finding to be re-derived — the sweep should push past it into
   mechanism, governance precedent, and evidence about what actually drives adoption.
