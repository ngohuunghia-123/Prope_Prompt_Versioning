# Coverage report — step 2.5

**Corpus: 96 substantive notes.** Target for `full` tier was 55–80; minimum 45. Exceeded.
Retraction check: **zero retracted sources** (`sources score` returned `"retracted": []` twice,
after wave 1 and after wave 2).

Waves run: wave 1 (87 URLs, 78 succeeded), correction wave (12 URLs, 9 succeeded — arXiv `/pdf/`
forms were failing and were re-issued as `/abs/`), wave 2 gap-fill (12 URLs, 8 succeeded).

## Coverage by atomic item

| Atomic item | Sources | Status | Notes |
|---|---|---|---|
| Sub-Q1 asset framing & prior art | 12 | Well-covered | 7 prompt-governance sources + CMDB/ITAM/IAS-38 prior art. See caveat below |
| Sub-Q2 data model / identity / lifecycle | 9 | Well-covered | MLflow registry + the stage-deprecation RFC, Confluent compatibility, Langfuse data model |
| Sub-Q3 ingestion from chaos | 8 | Well-covered | Prompt-SBOM static analysis, 4 shadow-AI sources, MinHash-LSH + RETSim |
| Sub-Q4 versioning / release / rollback | 13 | Well-covered | Langfuse, PromptLayer, Bedrock (×2), Vertex, feature-flag precedent (×4) |
| Sub-Q5 regression eval | 15 | Well-covered | 8 academic (judge bias, validity, actionability gap) + promptfoo + practitioner evals |
| Sub-Q6 HITL / RBAC / approval | 8 | Well-covered | DORA, Team Topologies, rubber-stamp, end-of-code-review, EU AI Act ×3, CAB |
| Sub-Q7 cost & token economics | 5 | Adequate | Attribution/FinOps ×2, compression ×2, the shorter-prompts-are-worse counter-case |
| Sub-Q8 distribution / API-SDK / resilience | 6 | Well-covered | Langfuse caching + guaranteed-availability + SDK discussion, OTel GenAI, Unity remote-config |
| Sub-Q9 agent layer / auto-optimization | 7 | Well-covered | 2 APO surveys, OPRO, textual-gradients critique, Evidently, Braintrust Loop |
| Sub-Q10 build / buy / layer | 5 | Adequate | Retool build-vs-buy, tech-debt economics, feature-store critique, vendor docs as landscape |
| Sub-Q11 adoption vs. incumbents | 9 | Well-covered | Data catalogs ×3, spreadsheets ×2, golden paths, feature store, non-engineer prompt authoring |
| Sub-Q12 build sequence / MVP | 3 | Thin | Atlan's 5-step sequencing w/ timeline, tech-debt piece, applied-llms. Mostly a synthesis task |
| Sub-Q13 counter-evidence / where it breaks | 14 | Well-covered | Drift ×3, regression ×2, CMDB decay ×3, catalog failure ×3, APO critique, feature-store critique |

**Zero `uncovered` atomic items. One `thin` item (Sub-Q12).** Sub-Q12 is a sequencing/judgment
question rather than an evidence question — the material to answer it comes from combining the
mechanism sources with the adoption evidence, not from a source that answers it directly. This
is acceptable per the exit criterion (thin is allowed; uncovered is not).

## Standing caveat on Sub-Q1 (must survive into the draft)

The 7 sources arguing "prompts are organizational assets" are **all vendor, consultancy, or
individual thought-leadership** — CIO trade press, a data-catalog vendor, a risk/compliance
vendor selling exactly this product, an IT-services firm, a community article platform, an
AI-generated topic aggregator, and a practitioner Medium essay. They converge on an identical
skeleton (owner · intent · version history · pre-production approval · RBAC on edit ·
retirement), and that convergence is *itself* the finding — but it is convergence among
interested parties, not independent corroboration.

**The one genuinely disinterested empirical source on the premise is arXiv:2509.12421**
("Understanding Prompt Management in GitHub Repositories"), which measured 24,800 prompts
across 92 repositories. It is the only evidence in the corpus that the scattered/duplicated
starting state is real and measurable rather than asserted. It is therefore load-bearing out of
proportion to its size, and step 5 should read its full body rather than a summary.

**Audited absence, recorded as a finding:** despite targeted adversarial searching
("centralized prompt library antipattern", "prompt management tools not worth it"), **no source
was found that argues against centralized prompt management on the merits.** The search
returned only vendor listicles promoting it. The critique of centralized registries in this
corpus is therefore entirely *transferred* from adjacent categories (CMDB decay, data-catalog
adoption failure, MLflow's own retreat from fixed stages, "you still don't need a feature
store"). The report must be explicit that the negative case is inferred by analogy, not
directly evidenced — that is an honest limitation, and the analogies are strong, but they are
analogies.

## Step 2.6 — redundancy audit

**Not run: no `claims-<note-id>.json` files exist.** The step's own gate says to skip when no
claim files exist. Cause is the environment deviation logged in `orchestrator-notes.md` — the
fetcher subagents that normally emit claims files had no shell tool, so the orchestrator
performed ingestion directly and no per-source claims extraction occurred.

**Mitigation:** claim extraction moves downstream. Step 5's depth investigators and step 9's
evidence digest read note bodies directly from `research/notes/*.md` (readable with the Read
tool, so no shell dependency). Step 9 becomes the single point where verbatim quotes are
pinned, and is correspondingly more important than in a normal run.

**Manual redundancy observation** (in place of the automated cluster analysis): the shadow-AI
cluster (4 sources) is substantially derivative — three are security-vendor pages recycling the
same handful of statistics ("80% of workers use unapproved AI", breach-cost figures) without
independent measurement. Treat as **one** independent source for coverage purposes, and do not
cite the vendor-page statistics without noting their unverified provenance. Similarly, the
Bedrock docs pair and the promptfoo docs pair are each one source split across two pages.
Adjusted independent-source count is roughly 88, still well above the floor.

## Step 2.8 — browser escalation queue

No items were queued: the fetch failures encountered were 403/404 responses and PDF-format
issues, not login or bot walls. Three URLs remain permanently unfetched and are recorded here
rather than silently dropped: the ACM DOI for the results-actionability-gap paper (403 — but
the arXiv version of the same paper WAS fetched, so the evidence is not lost), a Microsoft
Learn feature-store guide (404), and the O'Reilly "what we learned from a year of building with
LLMs" article (403 — mitigated: `applied-llms.org`, which hosts the same authors' collected
write-up, was fetched successfully).
