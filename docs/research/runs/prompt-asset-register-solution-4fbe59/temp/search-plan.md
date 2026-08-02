# Search plan — prompt-asset-register-solution-4fbe59

Lens A = breadth · Lens B = citation-chain depth / canonical · Lens C = adversarial / contrarian.
Lens D (period-pinned primary sources) is **N/A** — `time_periods` is empty in the decomposition.

Target: 45–60 executed searches → 80–120 candidate URLs → 60–100 after dedup → 10–12 batches.

| # | Atomic item | Search query | Type | Lens | Target |
|---|---|---|---|---|---|
| 1 | Sub-Q1 asset framing | prompt library governance enterprise organizational asset | web | breadth | factual |
| 2 | Sub-Q1 | "prompts as assets" intellectual property company AI | web | breadth | factual |
| 3 | Sub-Q1 prior art | IT asset register lifecycle ownership decommission why CMDB rots | web | depth | canonical |
| 4 | Sub-Q1 prior art | intangible asset recognition internally developed software accounting | web | depth | canonical |
| 5 | Sub-Q1 | criticism centralized prompt library antipattern why not worth it | web | adversarial | contrarian |
| 6 | Sub-Q2 data model | prompt registry schema design fields metadata versioning | web | breadth | factual |
| 7 | Sub-Q2 | MLflow model registry stages aliases transition approval | web | depth | canonical |
| 8 | Sub-Q2 | schema registry compatibility modes backward forward Confluent | web | depth | canonical |
| 9 | Sub-Q2 | prompt coupled to model version breaks when model updated | web | adversarial | contrarian |
| 10 | Sub-Q3 ingestion | extract hardcoded prompts from codebase static analysis detection | web | breadth | factual |
| 11 | Sub-Q3 | shadow AI discovery unsanctioned LLM usage enterprise inventory | web | breadth | factual |
| 12 | Sub-Q3 | near-duplicate text clustering MinHash embedding dedup corpus | web | depth | canonical |
| 13 | Sub-Q3 | secret scanning repositories false positives precision recall | web | adversarial | contrarian |
| 14 | Sub-Q4 versioning | Langfuse prompt management labels versions rollback documentation | web | breadth | factual |
| 15 | Sub-Q4 | PromptLayer release labels deploy prompt without code change | web | breadth | factual |
| 16 | Sub-Q4 | Amazon Bedrock prompt management versions aliases documentation | web | breadth | factual |
| 17 | Sub-Q4 | Vertex AI prompt management registry versions SDK | web | breadth | factual |
| 18 | Sub-Q4 | feature flags decouple deploy from release progressive delivery kill switch | web | depth | canonical |
| 19 | Sub-Q4 | prompt versioning problems git diff not enough production drift | web | adversarial | contrarian |
| 20 | Sub-Q5 eval | LLM prompt regression testing CI pipeline gate release | web | breadth | factual |
| 21 | Sub-Q5 | promptfoo evaluation assertions CI github action | web | breadth | factual |
| 22 | Sub-Q5 | LLM-as-a-judge agreement with human annotators reliability study | academic | depth | canonical |
| 23 | Sub-Q5 | LLM judge position bias verbosity bias self-preference bias | academic | depth | canonical |
| 24 | Sub-Q5 | G-Eval NLG evaluation GPT-4 human alignment paper | academic | depth | canonical |
| 25 | Sub-Q5 | LLM evaluation unreliable why evals fail production teams | web | adversarial | contrarian |
| 26 | Sub-Q5 | statistical significance small eval sets noise LLM benchmark variance | academic | adversarial | contrarian |
| 27 | Sub-Q6 HITL | approval workflow promote prompt to production human in the loop governance | web | breadth | factual |
| 28 | Sub-Q6 RBAC | role based access control prompt editing enterprise AI governance audit log | web | breadth | factual |
| 29 | Sub-Q6 | DORA change approval external change advisory board impact delivery performance | web | depth | canonical |
| 30 | Sub-Q6 | approval bottleneck rubber stamping review queue engineering | web | adversarial | contrarian |
| 31 | Sub-Q7 cost | LLM token cost attribution per team chargeback showback FinOps | web | breadth | factual |
| 32 | Sub-Q7 | estimate token cost of prompt change before deployment | web | breadth | factual |
| 33 | Sub-Q7 | FinOps for AI cost allocation framework practices | web | depth | canonical |
| 34 | Sub-Q7 | cost quality tradeoff cheaper model prompt degrades output | web | adversarial | contrarian |
| 35 | Sub-Q8 distribution | prompt SDK fetch caching fallback latency production reliability | web | breadth | factual |
| 36 | Sub-Q8 | dynamic configuration service outage blast radius resilience pattern | web | depth | canonical |
| 37 | Sub-Q8 | remote config single point of failure incident postmortem | web | adversarial | contrarian |
| 38 | Sub-Q9 agent | automatic prompt optimization DSPy OPRO APE survey | academic | depth | canonical |
| 39 | Sub-Q9 | GEPA TextGrad reflective prompt evolution optimizer | academic | depth | canonical |
| 40 | Sub-Q9 | Braintrust Loop automatic prompt improvement agent | web | breadth | factual |
| 41 | Sub-Q9 | automatic prompt optimization overfits validation set fails production | web | adversarial | contrarian |
| 42 | Sub-Q10 build/buy | build vs buy internal developer platform maintenance burden | web | breadth | factual |
| 43 | Sub-Q10 | prompt management commoditized cloud vendors free feature | web | adversarial | contrarian |
| 44 | Sub-Q10 | OpenTelemetry GenAI semantic conventions traces spans | web | depth | canonical |
| 45 | Sub-Q11 adoption | why data catalogs fail adoption metadata management | web | breadth | factual |
| 46 | Sub-Q11 | internal developer platform adoption golden path platform as a product | web | depth | canonical |
| 47 | Sub-Q11 | feature store adoption reality most companies don't need one | web | adversarial | contrarian |
| 48 | Sub-Q11 | why teams keep using spreadsheets instead of the tool shadow spreadsheet | web | adversarial | contrarian |
| 49 | Sub-Q11 | non technical users prompt authoring PM designer workflow tooling | web | breadth | factual |
| 50 | Sub-Q12 sequencing | thin slice MVP internal platform sequencing first value | web | breadth | factual |
| 51 | Sub-Q13 counter | prompt engineering is dead context engineering replaces it | web | adversarial | contrarian |
| 52 | Sub-Q13 counter | prompts are disposable throwaway not worth versioning | web | adversarial | contrarian |
| 53 | Sub-Q13 | prompt rot maintenance drift over time production LLM | web | adversarial | contrarian |
| 54 | Entity: personas | who writes prompts in companies survey roles marketing product | web | breadth | factual |
| 55 | Cross | enterprise AI governance EU AI Act documentation record keeping obligations | web | breadth | factual |

**Adversarial count: 17** (requirement ≥5). **Academic/depth lens count: 17.**

## Search gap check vs. coverage-matrix.md

Every coverage-matrix row traced to ≥1 planned search:

| Coverage-matrix phrase | Covered by search # |
|---|---|
| "Sổ tài sản" / asset framing | 1–5 |
| prompt asset record / data model | 6–9 |
| scattered sources (code, Sheets, Notion, Drive, chat) | 10–13 |
| no history / no rollback / unknown prod version | 14–19 |
| agent create/edit/version + auto-improve | 38–41 |
| eval comparing new vs old before release | 20–26 |
| HITL promote + RBAC | 27–30 |
| token/cost alerting | 31–34 |
| API/SDK shared optimized set | 35–37 |
| competing platforms | 14–17, 40, 42–44 |
| Google Sheet / Notion incumbent | 45, 47, 48 |
| prior art (model registry, schema registry, catalog, feature store, flags, CMDB, accounting) | 3, 4, 7, 8, 18, 29, 45–47 |
| personas (non-dev primary) | 49, 54 |
| build sequence / hackathon feasibility | 50 |
| risks / counter-evidence | 5, 9, 13, 19, 25, 26, 30, 34, 37, 41, 43, 47, 48, 51–53 |
| multi-vendor runtime / layer-not-replacement | 16, 17, 44 |
| enterprise/regulatory context | 55 |

No zero-coverage phrases. Plan proceeds to execution.
