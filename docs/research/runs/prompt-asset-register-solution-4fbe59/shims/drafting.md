## Run directives

Auto-selected for this run in step 1; binding wherever they adjust a default in your prompt. Absent instructions here leave your prompt's defaults untouched.

- register: analyze
- inference depth: deep

### Register posture

Default evaluative posture (this run confirms your prompt's defaults).
Write authoritative analysis: commit to the positions the evidence
supports, engage the strongest counterarguments explicitly, and rank
when the query asks which option wins. No adjustment to your prompt.

### Domain notes

Sourcing: vendor documentation is the primary source for MECHANISM (how Langfuse/PromptLayer/Bedrock/Vertex actually implement versioning, labels, rollback) and should be cited for mechanism only — never for comparative claims. Beware the comparison-blog trap: most 'best prompt management tools 2026' listicles are SEO content authored by the vendors being ranked (PromptLayer, Braintrust, Maxim, FutureAGI all publish self-favouring comparisons); treat them as vendor positioning, not evidence. Strongest evidence is practitioner post-mortems, engineering blogs from teams who actually operated a prompt registry, GitHub issues, and HN/Reddit threads where teams describe abandoning or keeping these tools. For eval-gating claims, prefer academic work on LLM-as-judge reliability (position/verbosity/self-preference bias, agreement with human labels) over vendor eval marketing. For adoption and governance claims, the transferable evidence lives in ADJACENT mature categories — data catalogs, model registries (MLflow stage transitions), feature stores, schema registries, CMDB/IT asset registers, feature flags, and DORA research on change-approval bottlenecks — because prompt-registry-specific adoption literature is thin. Recency: 18-24 months matters for tooling mechanics and pricing; governance/asset-management precedent can be older and is often better for being older. Vietnamese-market or SEA-specific enterprise context is a bonus, not a requirement.

### Inference depth

DEEP inference. Explicit inference chains are licensed WITH
provenance stated: when no source states X but sourced claims A and B
jointly imply it, say so in exactly that shape, citing A and B. Never
present an inference as a sourced fact; the citation checker verifies
number-bearing sentences pair-by-pair and an inference dressed as a
quote or finding will be flagged. Audited absences (what the record
should contain but does not) are reportable findings.
