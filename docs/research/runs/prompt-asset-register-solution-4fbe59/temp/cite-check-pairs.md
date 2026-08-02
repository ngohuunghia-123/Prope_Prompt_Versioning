1. The accounting objection, disposed of once Recognition under IAS 38 (the international standard for intangible assets) requires identifiability, probable future economic benefits, control, and reliable cost measurement; internally generated know-how-type items must be expensed because such expenditure "cannot be distinguished from expenditure to develop the business as a whole" [recognition-and-cost-of-intangible-assets-ias-38-ifrs-community].

2. What survives is not the number but the affordance argument: this population has version control, code review and searchable history, and still duplicates internally at 30.4% [understanding-prompt-management-in-github-repositories-a-call-for-best-practices].

3. Sourced: a git-structured population with full deduplication affordances duplicates at 30.4% internally [understanding-prompt-management-in-github-repositories-a-call-for-best-practices].

4. The decay mechanisms, and the line they draw MLflow's model registry enforced four fixed stages, then deprecated them after "extensive feedback on the inflexibility of model registry stages." The replacement decomposes rather than enriches: freeform tags that never gate routing, reassignable **aliases** — settable through UI and client API alike, "thereby decoupling model deployment from the production system code" — and separate registered-model objects per environment for access-control separation [rfc-deprecating-model-registry-stages-issue-10336-mlflowmlflow-github].

5. The third belongs to a different field class: data catalogs fail because the entry ticket "remains too high," requiring users to understand data vocabulary, navigate complex interfaces, or know how data is technically organised [why-do-data-catalogue-projects-fail], while pure automation is right about the labour and wrong about the ceiling, since it "primarily captures technical attributes" and "fails to answer critical business questions" [3-data-catalog-pitfalls-to-avoid-for-successful-governance], [data-catalogs-are-dead-long-live-data-discovery].

6. Any hand-set status enumeration [rfc-deprecating-model-registry-stages-issue-10336-mlflowmlflow-github].

7. A register whose Tier 1 is entirely derived removes the *data-entry* steward — the role every adjacent register funded once and never re-funded [cmdb-vs-asset-management-differences-and-why-you-need-both], [why-do-data-catalogue-projects-fail].

8. It does not remove the maintenance function, and the sharpest counter-evidence on that point comes from the automated-discovery vendors themselves, who prescribe high-frequency scanning *alongside* a named steward per class, remediation SLAs and quarterly audits, and state that decay is "not a risk, it is a certainty" [servicenow-cmdb-best-practices-2026-guide-virima].

9. The register stamps `discovery_method` per record, so a claim like *the group has 213 prompts* decomposes into what code scanning found, what connectors found, and what telemetry inferred: the only honest form of a coverage claim [servicenow-cmdb-best-practices-2026-guide-virima].

10. Do not build clustering on hashing alone MinHash locality-sensitive hashing — fingerprinting documents so similar ones collide in the same bucket — is the cheap default, with real production economics: one deployment reported it "more than doubled processing speed and achieved 3-5x cost savings" while deduplicating 10 billion documents [minhash-lsh-in-milvus-the-secret-weapon-for-fighting-duplicates-in-llm-training].

11. But on typo-laden short text — the profile of a prompt pasted into chat six times and hand-edited each time — peer-reviewed benchmarking reports a neural method retrieving the correct near-duplicate 97.7% of the time across 41 languages against MinHash at 53.8%, at roughly 46x slower on CPU and competitive only on GPU [retsim-resilient-and-efficient-text-similarity] — trivially affordable for an estate of thousands of prompts.

12. Design rule: MinHash as a cheap pre-filter, then a sentence-embedding pass at cosine >0.95, the exact configuration (all-mpnet-base-v2, >0.95) the GitHub study used [understanding-prompt-management-in-github-repositories-a-call-for-best-practices].

13. Primary engineering guidance is blunt: tools "that merely wrap existing software functionality or API endpoints" waste an agent's limited context, and the prescription is "pagination, range selection, filtering, and/or truncation with sensible default parameter values," with a precedent of capping tool responses at 25,000 tokens [writing-effective-tools-for-ai-agentsusing-ai-agents-anthropic].

14. A large, browsable, semantically empty catalog is the onset of trust collapse [why-do-data-catalogue-projects-fail], [3-data-catalog-pitfalls-to-avoid-for-successful-governance], and enrichment with no capture moment attached is a wish rather than a plan.

15. Rollback has a wall-clock cost, and the register should show it Client software development kits (SDKs) cache prompts with a default time-to-live of 60 seconds and revalidate in the background, so running instances serve the rolled-back version within roughly one cache interval [prompt-cicd-version-gate-and-roll-out-prompts-like-code-langfuse], [caching-langfuse].

16. The strongest opposing figure, at full force: strong judges match controlled and crowdsourced human preferences "achieving over 80% agreement, the same level of agreement between humans" [230605685-judging-llm-as-a-judge-with-mt-bench-and-chatbot-arena] — curated general-chat preference data under a 2023 protocol.

17. More adversarially aware work does not reproduce it as a floor: after nine debiasing strategies across five judges the best configuration reached only 71.0% agreement; position swap on adversarial instances "consistently and significantly hurts all models (−3 to −13 pp)"; and residual style bias dominates, humans preferring markdown only 57% of the time versus 73–97% for four of five judges [judging-the-judges-a-systematic-evaluation-of-bias-mitigation-strategies-in-llm].

18. One architectural trap follows from a mechanistic result: self-preference bias tracks familiarity rather than authorship, since judges "assign significantly higher evaluations to outputs with lower perplexity than human evaluators, regardless of whether the outputs were self-generated" [241021819-self-preference-bias-in-llm-as-a-judge].

19. The structure is risk-aligned groups with independent thresholds, each category evaluated separately "to detect domain-specific drift that aggregate metrics can mask," with worked thresholds above 95% pass rate for one category, 100% format compliance for structured output, and 0% security violations [test-before-you-deploy-governing-updates-in-the-llm-supply-chain].

20. The aggregate is a liability rather than merely insufficient: one documented version "improved overall accuracy by 10% while negation-handling collapsed 66.7%, from 100.0%→33.3%" [prompt-engineering-fails-quietly-prompt-regression-is-why-towards-data-science].

21. The inference has stated provenance: near-zero discriminative validity on the closest studied analogue with confidence intervals spanning zero [criterion-referenceability-determines-llm-as-a-judge-validity-across-physics-ass], plus the practitioner finding that teams "gather evaluation data but cannot translate findings into concrete improvements" [260416304-results-actionability-gap-understanding-how-practitioners-evaluate-llm].

22. Chen, Zaharia and Zou (2024, *Harvard Data Science Review*) documented GPT-4's accuracy on identifying prime numbers falling from 84% to 51% between the March and June 2023 versions, and code-execution success from 52% to 10% within three months, with no version change [prompt-drift-what-it-is-and-how-to-detect-it-agenta-blog], [test-before-you-deploy-governing-updates-in-the-llm-supply-chain].

23. Anthropic's August 2025 postmortem documents three bugs affecting Claude Sonnet 4's performance "without any API modifications, including routing errors affecting up to 16% of requests" [test-before-you-deploy-governing-updates-in-the-llm-supply-chain].

24. It doesn't catch steps 2-6" [promptfoo-passes-production-still-breaks-heres-the-gap-dev-community] — which is why scheduled monitoring is a separate mechanism rather than an extension of the gate.

25. Where a judge is used, alignment is maintained work rather than setup — one team logged the response, the judge's critique and the final outcome, reviewed them with stakeholders, and over three iterations improved agreement with humans "from 68% to 94%," while naming criteria drift as a first-class failure, since perceptions of what counts as good and bad output "shift as they interact with more data" [what-weve-learned-from-a-year-of-building-with-llms-applied-llms].

26. Record-keeping mandates that high-risk systems "shall technically allow for the automatic recording of events (logs) over the lifetime of the system" — a logging obligation on the deployed system, for post-market traceability [article-12-record-keeping-eu-artificial-intelligence-act].

27. Human oversight requires that high-risk systems be designed so "that they can be effectively overseen by natural persons during the period in which they are in use," with the enumerated capacities being to monitor, interpret, disregard, override or interrupt a running system; the one two-person requirement is a check on identifications made by biometric systems in use, not a release gate on authoring tooling [article-14-human-oversight-eu-artificial-intelligence-act].

28. The Law takes effect 1 March 2026, with grace periods for most existing providers and deployers "lasting until 1 March 2027 (or 1 September 2027 for AI systems in the fields of health, education and finance)" — twelve months generally, eighteen for finance, healthcare and education, independently corroborated [vietnam-artificial-intelligence-law-foundation-and-outlook-insight-baker-mckenzi], [vietnam-the-first-law-on-artificial-intelligence-what-you-must-know-duane-morris].

29. For a system already operating before 1 March 2026 and classified into those tiers, the transition notice with a plan or compliance scheme is due "within 60 days from the effective date of the Decree (i.e., before June 30, 2026)" [update-decree-1422026nd-cp-guiding-the-artificial-intelligence-law-in-vietnam-vi].

30. A break-glass promotion, available to the owner, logged with a required one-line reason and generating a review task due within 24 hours, prevents the gate from being routed around entirely, on the logic that a system adding more steps than it removes produces a shadow process rather than compliance [why-your-team-keeps-reverting-to-spreadsheets].

31. The other side deserves its strongest form: compression research reports up to 20x compression at under 2% quality loss on standard benchmarks [prompt-compression-cut-token-costs-without-losing-quality-neuraltrust], itself vendor marketing relaying research it did not conduct; and a formal treatment establishes the frontier is real while finding "a large gap between the performance of current prompt compression methods and the optimal strategy" [240715504-fundamental-limits-of-prompt-compression-a-rate-distortion-framework-f], available at abstract level only.

32. The confirmation runs to database-schema granularity: for over a year there was no API to update a Langfuse prompt label, and a user's documented temporary solution was raw SQL against a Postgres `prompts` table, with a maintainer confirming label updates finally shipped "via our API / SDKs" as late as January 2025 [update-prompt-label-programatically-langfuse-discussion-4284-github].

33. A controlled ablation found that generic prompt additions "do not produce monotonic improvements," with the largest decline taking retrieval-grounded compliance "from 26/30 to 9/30" — 86.7% to 30% — because instructions to be helpful and comprehensive "encouraged the models to hallucinate information not present in the source documents" [260122025-when-generic-prompt-improvements-hurt-evaluation-driven-iteration-for], [when-better-prompts-hurt-evaluation-driven-iteration-for-llm-applications-a-fram].

34. Its third is a **rate-capped, eval-pre-validated exception reporter**: it fires only for assets that already have a task-specific contract, only when a failure cluster or cost signal crosses a threshold, and every candidate must clear a held-out slice of that asset's own suite before a human sees it — mirroring the split an open-source implementer describes, "40% train, 40% validation, and 20% test," so an overfitted prompt "will fail on validation and be discarded" [how-we-built-open-source-automated-prompt-optimization].

35. That is not the same as being the serving store — §8 deliberately keeps it out of the inference path, pushing approved versions down into each product's runtime — and that distinction is the whole answer to the objection: one record of truth, serving copies wherever the products already read [caching-langfuse].

36. A forward-to-bot or browser capture path is what prevents day-30 re-fragmentation, and the shadow-workflow finding says that clock runs fast [how-hidden-spreadsheets-shadow-workflows-drain-budgets-mtm-blog].

37. **Phase 0 — the schema and the approval object.** The asset and decision tables, the state machine, the actor-differs-from-reviewer constraint, the frozen evidence record, and per-field provenance stamping [servicenow-cmdb-best-practices-2026-guide-virima].

38. **Phase 1 — ingestion and clustering, built thinly.** One document connector plus a chat-export parser plus repository scanning [static-analysis-for-llm-prompt-security-a-methodology-for-pre-deploy-vulnerabili], a MinHash pre-filter with an embedding pass [retsim-resilient-and-efficient-text-similarity], the `imported` state with one-click claim, discovery-method provenance per record, and the grid.

39. **Phase 2 — authoring and one adapter.** Silent-autosave editing with no submit button; one push adapter end-to-end against whichever runtime the pilot product uses, with reconciliation; the fetch-by-label contract with a declared BACKWARD compatibility mode [schema-evolution-compatibility-types-backward-forward-full-transitive-confluent].

40. **Phase 3 — contract and telemetry.** Deterministic per-category checks for one prompt family, executed by an off-the-shelf open-source runner (promptfoo or equivalent) the platform invokes rather than one built in-house [test-before-you-deploy-governing-updates-in-the-llm-supply-chain]; non-content telemetry ingestion and cost per successful task with correct cache arithmetic [gen-ai-opentelemetry], [llm-cost-attribution-at-scale-metadata-tagging-team-budgets-and-chargeback-repor].

41. **Phase 4 — scheduled drift monitoring, the exception-reporting agent, role separation of contract editing from prompt editing, and embedded capture against the group's actual channel** [promptfoo-passes-production-still-breaks-heres-the-gap-dev-community].

42. **Explicitly deferred**: any unsupervised generative improvement sweep beyond drafting semantic fields and rewriting on request; branch-like workflows; a replacement prompt store; judge-based scoring on holistic assets, the soft-block regime for criterion-referenceable families being a Phase 4 item rather than a demo one; chargeback reporting, which follows showback; and anything resembling tracing, where free tooling is better and competing is a category error [paying-down-tech-debt-by-gergely-orosz-and-lou-franco].

43. Then the negative case, where a rejection returns the candidate to draft rather than deleting it [update-prompt-label-programatically-langfuse-discussion-4284-github].

44. **The export-killer** (proving the ledger's four fields): one view, no export, answering what is running in production right now, who owns it, what version, what it cost in the last 30 days, and when its contract was last verified [why-your-team-keeps-reverting-to-spreadsheets].

45. One beat should not be performed: do not demonstrate the agent rewriting a prompt and declaring it better, a demo both commoditized and unsound, where anyone who knows the literature will ask what the score means [260122025-when-generic-prompt-improvements-hurt-evaluation-driven-iteration-for], [criterion-referenceability-determines-llm-as-a-judge-validity-across-physics-ass].

46. One relayed projection about agentic-AI project cancellations is a vendor relaying an attribution rather than an independently verified source [servicenow-cmdb-best-practices-2026-guide-virima], so it is load-bearing nowhere here.

47. **Fewer tokens versus lower cost** [prompt-compression-cut-token-costs-without-losing-quality-neuraltrust], [240715504-fundamental-limits-of-prompt-compression-a-rate-distortion-framework-f], [why-shorter-prompts-can-make-coding-agents-worse] — resolved in §7A: input-token delta is not a valid proxy for cost delta.

48. **Judges that match humans versus judges that cannot rank at all** [230605685-judging-llm-as-a-judge-with-mt-bench-and-chatbot-arena], [criterion-referenceability-determines-llm-as-a-judge-validity-across-physics-ass], [judging-the-judges-a-systematic-evaluation-of-bias-mitigation-strategies-in-llm] — resolved in §5A/B, and the only tension where the second side wins by *explaining* the first: the variable is criterion-referenceability, and the block rule branches on it [260416304-results-actionability-gap-understanding-how-practitioners-evaluate-llm].

49. **The register as destination versus discovery in the flow** [data-catalogs-are-dead-long-live-data-discovery], [why-do-data-catalogue-projects-fail], [prompt-governance-is-the-new-data-governance-cio], [guaranteed-availability-langfuse] — resolved in §3C and §10B by splitting the functions: the ledger is the system of record and a destination, capture is embedded and built thin, and serving stays in each product's runtime.

50. **What a prompt inventory can actually see** [shadow-ai-discovery-a-critical-part-of-enterprise-ai-governance], [static-analysis-for-llm-prompt-security-a-methodology-for-pre-deploy-vulnerabili] — resolved in §3A: neither method sees the governed population, document connectors are the structurally required third, and `discovery_method` per record keeps coverage claims honest.

51. **Whether a prompt is an asset in any sense that survives scrutiny** [recognition-and-cost-of-intangible-assets-ias-38-ifrs-community], [what-is-prompt-governance-the-critical-control-for-enterprise-ai] — both sides stand, and §1B keeps them apart: nothing reaches a balance sheet, and the claim doing the work is managerial and judged on the four fields.

52. **Git's branching versus the label pointer a non-developer can move** [git-based-cms-vs-api-driven-cms-which-headless-cms-should-you-choose-bejamas], [version-control-langfuse], [release-labels-promptlayer], [api-first-cms-vs-git-based] — resolved in §4B by the persona commitment, at an uncompensated cost paid by continuous duplicate clustering.

53. **Second, the approval-decision object**, because three independently derived arguments converge on it — the sanctioned bespoke surface, the market gap conceded in a vendor's own capability table [prompt-cicd-version-gate-and-roll-out-prompts-like-code-langfuse], [update-prompt-label-programatically-langfuse-discussion-4284-github], and the agent's output target — and because it is the write trigger for owner, production pointer, governance state and both semantic fields in a single action.

54. If the first honest scan of the group's Drive and Sheets finds duplication far below the 30.4% internal-semantic rate observed in a far better-organized git population [understanding-prompt-management-in-github-repositories-a-call-for-best-practices], the founding premise weakens and the product should be rescoped around versioning rather than discovery.

55. And to the extent the group's own downstream products fall inside Vietnam's risk regime — a classification question for each product, never for this register, which no regime obliges to gate anything — the approval record is already the artifact those product teams would otherwise have to reconstruct after the fact, against clocks that have partly run [update-decree-1422026nd-cp-guiding-the-artificial-intelligence-law-in-vietnam-vi], [vietnam-artificial-intelligence-law-foundation-and-outlook-insight-baker-mckenzi].