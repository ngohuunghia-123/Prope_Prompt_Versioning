The corporate group's prompt asset register — *Sổ tài sản prompt của tập đoàn* — is a falsifiable commitment, and that is its virtue as a design constraint. An asset register carries four things per item: a named owner, a lifecycle with a retirement path, a record of what consumes it, and a cost. Pick twenty prompts at random on day 90 and check those four fields. If any is blank, stale, or maintained by a human who has to remember to maintain it, the product is a database with an expensive name, and a marketer inside the group is right to go back to the Google Sheet.

The three differentiators the positioning names — start from the existing chaos, cost as a promotion gate rather than a retrospective chart, an approval decidable in two minutes — are the three points at which the ledger writes itself. Ingestion populates identity and provenance, telemetry populates usage and cost, and the approval click populates owner, production pointer and lifecycle state as a side effect of a decision someone was already making. The rule: **every operational field must be derived from an action someone was already going to take**, and the one field class that cannot be derived — what a prompt is *for* — gets captured inside the one mandatory human step.

Two of the four hard constraints cannot be honoured as written. Regression evaluation cannot guarantee no quality degradation as a single automated verdict; it can block on deterministic contract properties, render subjective quality as adjudicable evidence, and monitor provider-side drift on a schedule. Mandatory human-in-the-loop approval (HITL — a named person signs off before a version reaches production) has no statutory basis for an internal tooling layer in either jurisdiction examined; it rests on corporate segregation of duties plus prophylactic readiness for the group's downstream products. Keep both; sell neither on a false premise.

One asymmetry runs through the evidence. The positive case for prompt registers is thin, largely vendor-authored, and in the adoption chapter entirely analogical; the negative case — a widely deployed model registry publicly reversing its own lifecycle design, configuration databases rotting on a named mechanism, data catalogs failing among business users — is disinterested and strong. The response is not to abandon the framing but to build against the specific failures those critics name.

## 1. What the Asset Framing Commits You To — And the Prior Art It Inherits

An asset register is an old organizational form: a list of what an organization owns, who is accountable, what state each item is in, what it costs. Corporate IT has configuration-management databases (CMDBs — inventories of hardware, software and service components); data teams have catalogs; machine-learning teams have model registries. All three have a failure literature, none of it written to sell anything like this product.

### A. The commitment is testable, which is the point of making it

Observability platform or evaluation framework are capability claims, graded on a feature matrix against funded competitors; a ledger is graded on whether its entries are true — a bar the real incumbent (a Sheet, a Notion page, a Drive folder, a chat thread) fails absolutely rather than partially.

The framing also does schema work. The strongest published articulation of governed prompts is practitioner-authored and names a bundle rather than a string: we lock the prompt together with the specific model version and configuration parameters, belonging in a shared repository rather than a private folder [1]. If prompt text alone is the versioned unit, a provider silently swapping the model changes behaviour without changing any version. A parallel trade-press argument identifies what to capture at the gate — the reasoning, not only the outcome — since every override an employee approves is producing a labeled training example that encodes judgment no public dataset contains [2].

### B. The accounting objection, disposed of once

Recognition under IAS 38 (the international standard for intangible assets) requires identifiability, probable future economic benefits, control, and reliable cost measurement; internally generated know-how-type items must be expensed because such expenditure "cannot be distinguished from expenditure to develop the business as a whole" [3]. A corporate prompt library resembles that excluded category far more than licensed software. No prompt is going on the balance sheet, and volunteering that forecloses the most damaging objection a finance director can raise. The claim doing the work is managerial, and stronger for being narrowed: it is falsifiable by inspecting four fields.

### C. The founding premise is plausible, mechanistically supported, and not measured here

The only disinterested measurement of prompt duplication available studies GitHub, and its figures are widely garbled. Across 24,800 prompts in 92 repositories:

| Duplication type | Rate | Base |
|---|---|---|
| Internal exact | 13.0% | 12 of 92 repositories |
| Internal semantic | 30.4% | 28 of 92 repositories |
| External exact | 16.3% | 15 of 92 repositories |
| External semantic | 34.8% | 32 of 92 repositories |
| Prompt-level semantic (cosine >0.95, sentence embeddings) | 38.5% | 9,553 of 24,800 prompts | One caveat cuts at every figure, not only the external ones: the corpus is 72.8% public prompt-collection repositories, the eight largest supply 90.8% of the 24,800 prompts, and the six largest are all collections. So the 38.5% prompt-level headline substantially measures collection dumps, and a repository built to aggregate prompts holds near-identical variants by design at the internal level too. Neither number is a clean measurement of organizational waste. What survives is not the number but the affordance argument: this population has version control, code review and searchable history, and still duplicates internally at 30.4% [4].

The design therefore rests on an inference, stated as one. Sourced: a git-structured population with full deduplication affordances duplicates at 30.4% internally [4]. Sourced: the target population lives in Sheets, Notion, Drive and chat threads, which have none of those affordances. Together they imply the target duplicates at least as much. No source measures duplication inside a single organization's document estate — an audited absence whose consequence is that the ingestion sweep's own output becomes the first real measurement of the premise.

## 2. The Asset Record — Prompt Identity, Data Model, and Lifecycle

A data model for a register is mostly a decision about who types. Every field is either derived by the system from something that happened, or typed by a person who must remember to keep it true. The second kind decays. Three adjacent categories decayed for two distinguishable reasons, and the difference between those reasons is the schema.

### A. The decay mechanisms, and the line they draw

MLflow's model registry enforced four fixed stages, then deprecated them after "extensive feedback on the inflexibility of model registry stages." The replacement decomposes rather than enriches: freeform tags that never gate routing, reassignable **aliases** — settable through UI and client API alike, "thereby decoupling model deployment from the production system code" — and separate registered-model objects per environment for access-control separation [5]. A widely deployed registry publicly reversing its own design is the most disinterested precedent available, and it transfers exactly: *which version is running in production* must be a pointer moved **by** the promote action, never a status flag set afterwards. The other half of that feedback was inflexibility, and the replacement carries no fixed enumeration at all, so `governance_state` earns its place only while nothing routes on it and the enumeration extends without a migration. (The RFC closed as not-planned; the deprecation is attributable to the MLflow 2.9 announcement it records, not to a removal verified here.)

The second mechanism is contested ownership — two systems disagreeing on the basics, "and no one has decided which one wins on which field" [6] — which yields the refinement most registers skip: *last updated* is not *last verified*, since such timestamps are often artifacts of a bulk import or administrative edit, not evidence of a verified infrastructure scan, and the fix is tagging every attribute with its discovery source and scan timestamp [7]. The third belongs to a different field class: data catalogs fail because the entry ticket remains too high, requiring users to understand data vocabulary, navigate complex interfaces, or know how data is technically organised [8]. Pure automation is right about the labour and wrong about the ceiling: it "primarily captures technical attributes" and "fails to answer critical business questions" [9], [10]. These converge on a synthesis none states: operational fields must be entirely auto-derived; semantic fields cannot be, and survive only if their capture collapses into a step the organization already mandates — which the hard HITL constraint supplies.

### B. The field list, and what makes each field go stale

**Tier 0 — identity. Written once at creation or ingestion, then immutable or hash-verified.**

| Field | Populated by | Goes stale when |
|---|---|---|
| `asset_id` | System, at first ingestion or creation | Never |
| `slug` | Agent-proposed at ingestion, confirmed at first promotion, frozen once any consumer has fetched it | Never, because frozen — it is the join key against `gen_ai.prompt.name`, and renaming it silently orphans telemetry [11] |
| `version_id` | System, monotonic per asset, on every save | Never |
| `content_hash` | Hash of rendered template plus bound model and configuration — the bundle [1] | Never; it is the instrument that detects other fields going stale |
| `bundle.model`, `bundle.params` | Captured at save from the editing context | On silent provider substitution — detectable when `gen_ai.response.model` diverges from `gen_ai.request.model` [11] |

**Tier 1 — operational. Entirely auto-derived. No text box in the interface writes to these.**

| Field | Populated by | Goes stale when |
|---|---|---|
| `owner_of_record` | The identity that approved the current production version — not the author | The person leaves; resolve against the corporate directory on a schedule, and a deprovisioned identity flips the asset to orphaned and enqueues reassignment |
| `production_pointer[env]` | Alias reassignment by the promote action itself [5] | Cannot go stale against the register's intent; can diverge from runtime reality, which the next field measures |
| `runtime_bindings[]` | The push adapter per target: which provider account holds a copy, push status, last sync, remote content hash | The moment someone edits directly in a provider console; hash mismatch raises drift rather than silently reconciling [6] |
| `consumers[]` (blast radius) | Service identities fetching the slug, plus spans carrying `gen_ai.prompt.name` [11] | Decays honestly: each consumer carries a last-seen stamp and moves to historic past a threshold, never silently dropped |
| `calls_30d`, `last_used_at` | Telemetry | Never — absence of calls is itself the signal |
| `cost_30d`, `cost_per_successful_task` | `gen_ai.usage.*` attributes against a versioned pricing table [11], [12] | When the pricing table is unversioned, or cache tokens are double-counted |
| `contract_status`, `last_verified_at` | Scheduled re-run of the contract against the currently serving model [7] | By construction it expires; that is its job |
| `discovery_method`, `discovery_at` | Which ingestion method found the record: code scan, document connector, or telemetry orphan | Never; it lets an approver trust a bulk import differently from a promote-derived record [7] |
| `governance_state` | Derived transition: imported → claimed → governed → deprecated → retired | Only if a transition can be set by hand, or if any routing decision reads it. Neither is permitted |

**Tier 2 — semantic. Agent-drafted, human-confirmed, captured only inside the promote step.**

| Field | Populated by | Goes stale when |
|---|---|---|
| `purpose_one_line` | Agent-drafted from content and observed traffic, confirmed or edited at the **first** promotion, carrying an `ai-drafted` versus `human-confirmed` flag visible throughout the register | When use changes without a promotion; mitigated by re-surfacing it whenever `consumers[]` gains a new product |
| `cluster_id`, `canonicalization_decision` | Clustering proposes; a human settles whether near-duplicates are one asset or deliberate variants | Continuously — every new near-duplicate reopens it |
| `criticality_class` | Human, at first promotion: is this output criterion-referenceable (structured, checkable) or holistic (copy, tone)? | When output format changes; force re-confirmation when the contract changes |
| `production_contract` | Deterministic checks plus per-risk-category thresholds [13]; editable only by a stricter role than prompt text | Continuously, through criteria drift [14] |
| `retirement_rationale` | Human, at deprecation | Terminal |

**Tier 3 — the fields the schema refuses.** A stored scalar quality score, which masks category-level collapse. A free-text description separate from `purpose_one_line`, because two fields claiming one attribute is the configuration-database rot mechanism verbatim [6]. Required tags at creation. Any capitalized-value field. Any hand-set status enumeration [5]. Registers do not fail from having too few columns.

### C. Retirement, which most registers never build

Retirement here is derivable to the point of proposal: when 30-day calls reach zero and no consumer has been active for a defined window, the asset proposes its own deprecation to the owner of record, who confirms with a rationale or resets the clock. Promotion needs human judgment because it adds risk; retirement can be machine-proposed because leaving a dead asset in the ledger is itself the risk.

A register whose Tier 1 is entirely derived removes the *data-entry* steward — the role every adjacent register funded once and never re-funded [6], [8]. It does not remove the maintenance function, and the sharpest counter-evidence on that point comes from the automated-discovery vendors themselves, who prescribe high-frequency scanning *alongside* a named steward per class, remediation SLAs and quarterly audits, and state that decay is "not a risk, it is a certainty" [7]. The closest precedent to this design's own answer ran the experiment and still needed the steward. Auto-derivation therefore buys away the entry cost, not the ownership: what survives is a reconciliation queue — orphaned owners, hash mismatches, expired contracts, unclaimed imports — and the design bar is that the queue stays small enough for the platform owner to be the entire staffing model. If it does not, the configuration-database outcome is the base rate rather than the exception.

## 3. Ingestion: Starting From the Existing Chaos

Finding an organization's prompts is a discovery problem, and the security industry has built two patterns for it. One reads source code before anything runs; the other watches traffic leaving the company. Between them sits the estate this product exists to govern, and neither can see it.

### A. Three methods, because two of them are jointly blind

Two of the three methods have a published methodology, and each names its own blind spot.

| Method | What it does | Blind spot |
|---|---|---|
| **Static analysis** | Parses source files and extracts the string literals passed to model APIs, producing a Prompt SBOM (software bill of materials) — "a CycloneDX v1.4 structured inventory of every prompt string in the codebase," carrying content, hash, source file and line number, across TypeScript, JavaScript, Python, Go, Rust, Java and C#. Maps onto `content_hash` and `discovery_method` | Prompts assembled at runtime from variables, database values or user inputs "are not visible to static analysis by definition" [15] |
| **Egress-boundary discovery** | Observes traffic to known model endpoints, on the framing that blocking one tool only drives employees to another, "leaving the enterprise blind to real usage" [16] | Traffic cannot be attributed to an authored, versioned prompt, and sees nothing of a prompt sitting unused in a Notion page. That literature is derivative and recycles unattributed prevalence figures; it is used here for method only |

The gap between the two is exactly the document-and-chat estate, so **document-source connectors are a structurally required third method, not an optional integration** — with an asymmetry worth stating: the two methods with published methodologies are the two that cannot see the target estate, while the required third has none published. Nothing searched here specifies how a prompt candidate is distinguished from ordinary prose in a document or how a chat export is segmented, which makes it the design's largest unevidenced dependency. The consequence is a field rather than a feature bullet. The register stamps `discovery_method` per record, so a claim like *the group has 213 prompts* decomposes into what code scanning found, what connectors found, and what telemetry inferred: the only honest form of a coverage claim [7].

### B. Do not build clustering on hashing alone

MinHash locality-sensitive hashing — fingerprinting documents so similar ones collide in the same bucket — is the cheap default, with real production economics: one deployment reported it "more than doubled processing speed and achieved 3-5x cost savings" while deduplicating 10 billion documents [17]. But on typo-laden short text — the profile of a prompt pasted into chat six times and hand-edited each time — peer-reviewed benchmarking reports a neural method retrieving the correct near-duplicate 97.7% of the time across 41 languages, against MinHash at 53.8% [18]. It is roughly 46x slower on CPU and competitive only on GPU — trivially affordable for an estate of thousands of prompts. Design rule: MinHash as a cheap pre-filter, then a sentence-embedding pass at cosine >0.95, the exact configuration (all-mpnet-base-v2, >0.95) the GitHub study used [4]. That threshold is the tunable deciding whether near-duplicates surface as one `cluster_id` or as deliberate variants. Hashing alone under-clusters precisely the population the sweep exists to find.

The agent doing this must be built to a context budget rather than to completeness. Primary engineering guidance is blunt: tools "that merely wrap existing software functionality or API endpoints" waste an agent's limited context, and the prescription is pagination, range selection, filtering, and/or truncation with sensible default parameter values, with a precedent of capping tool responses at 25,000 tokens [19]. So the ingestion agent reads a paginated candidate list from deterministic extraction rather than a whole Notion workspace, and is used only where judgment is required — naming a cluster, drafting a purpose line, flagging a likely secret.

### C. The two-population register

Zero-labour ingestion is the flagship differentiator, and it manufactures a specific hazard: a register whose majority population has never passed the one moment where meaning gets captured. A large, browsable, semantically empty catalog is the onset of trust collapse [8], [9], and enrichment with no capture moment attached is a wish rather than a plan.

The committed design is a two-population register. Imported records land in an `imported` state visibly outside the governed ledger — no owner badge, no production pointer, Tier 2 fields shown empty rather than guessed, a provenance stamp naming the source, exclusion from every governed statistic — while remaining fully browsable and searchable, which is the day-one win. The capture trigger is **first use, not first promotion**: the moment a human opens, copies, edits or claims an imported record, one agent-drafted question fires — what is this for? — as a single dismissible field, and the record moves to claimed.

The front page therefore never reads *412 assets*. It reads **412 discovered, 38 governed**, and the governed fraction stands as a self-diagnostic rather than a vanity metric. Records nobody touches stay unadopted, which is not a defect: an unadopted record with zero fetches in six months is a retirement candidate, and having found it is already more than the group had.

## 4. Versioning, Release, and Rollback Mechanics

Versioning a prompt has two shapes. One treats prompts as code: files in a repository, branches, merges, pull requests. The other treats prompts as content: immutable numbered versions in a database, with a movable label — `production` — pointing at whichever version is live.

### A. Every vendor converges on the same primitive

| Surface | Versioning primitive | Deployment mechanism | Rollback | Scope unit | Approval object |
|---|---|---|---|---|---|
| Langfuse | Version IDs plus user labels | Assign the `production` label to a version [20] | Reassign the label to a previous version [20] | Project; separate projects per environment need syncing [20] | None; protected labels are a write restriction [20] |
| PromptLayer | Template versions | Add a release label in the interface [21] | Move the release label | Workspace | None |
| Amazon Bedrock | Immutable numbered snapshots from a `DRAFT` [22] | Retrieve by version number [23] | Fetch the prior version | Single AWS account, gated by IAM identity [22] | None |
| Google Vertex | `create_version`, `list_versions`, `restore_version` [24] | Restore a version | `restore_version` | Single Google Cloud project [24] | None |

Promotion everywhere is a role-gated write to a pointer. Langfuse makes the shape explicit: protected labels prevent modification, but "admin and owner roles can still modify or delete the label, effectively changing the production prompt version" [20]. That is permission over a column, not a workflow.

### B. Take the movable pointer, and pay for it explicitly

A movable label lets a non-developer publish and roll back without a deploy, picked up on the application's next fetch [20], [21], and git-based content workflows are described as unsuitable where content changes rapidly [25]; with a marketer as primary user the architecture is settled. The opposing case names a cost that must be paid: git-based systems support sophisticated versioning, distributed and parallel multi-environment workflows, or branching, with straightforward reverts [26], [25], while label-based versioning gives linear history with movable environment pointers, not divergent branches with reconciliation. Two people editing the same prompt in different directions produce either colliding linear versions or — far more likely where the incumbent is a spreadsheet — a second near-duplicate under a slightly different name, and nothing in the versioning primitive catches that. **Near-duplicate clustering is therefore the standing compensating control for an architecture that cannot merge**, running continuously against the live register rather than once at migration: `cluster_id` recomputes on every save, and a new asset whose nearest neighbour crosses the threshold is surfaced to its author immediately — *this looks like `checkout-email-vi` v7, variant or same thing?*

### C. Rollback has a wall-clock cost, and the register should show it

Client software development kits (SDKs) cache prompts with a default time-to-live of 60 seconds and revalidate in the background, so running instances serve the rolled-back version within roughly one cache interval [27], [28]. That default is set per fetch, so rollback wall-clock is a register-side policy rather than a fact of the world — a shorter interval where the `consumers[]` blast radius is large, the default elsewhere — and the figure the card shows is per-consumer. A design rule follows as an inference. Sourced: the mandatory approval wall is a fixed constraint. Sourced: rollback is one pointer reassignment the same non-developer can perform [20]. Together they imply that **the gate is only defensible to a non-engineer if undo is one click and takes effect in seconds** — putting the rollback control on the prompt's main view rather than in a version-history submenu, and forbidding a second approval to use it.

Because the eval provably cannot certify the residual risk, the pointer should also move partially. Progressive-delivery practice separates release from deployment and makes the kill switch the same pointer reassignment the design already has [29]. Per-request percentage canary, however, needs variant assignment in the hot path §8A deliberately refuses to occupy, so v1 rolls out at the grain it can control: promote to one consuming product's `runtime_bindings[]` entry first and to the rest after a defined soak window, reverting automatically if the live contract pass rate falls below its declared threshold.

## 5. Regression Eval You Can Actually Gate On

Evaluating a prompt change means asking whether the new version is better than the old. Deterministic checks run code against the output: valid JSON, mandatory disclaimer present, within the length bound, no banned claims. Judge-based checks ask another model to score quality. Their reliability profiles differ completely, and that difference is what the constraint *regression eval to guarantee no quality degradation* runs into.

### A. Judge validity is a property of the task, not of the model

The decisive evidence separates absolute error from *discriminative validity* — whether a judge can rank-order responses at all. A rank correlation near 0.6 means a judge can usefully rank-order responses; near zero means it cannot rank them at all. On structured physics questions models reach robust discriminative validity (Spearman ρ>0.6), rising to ρ=0.885 for a judge committee given the official solutions. On holistically marked essays, "blind AI marking is harsher and more variable than human marking," and discrimination collapses to ρ≈0 with every confidence interval spanning zero. Neither a written mark scheme nor anchored exemplars repairs it, and anchoring is the trap a builder will walk into: it compresses the AI score distribution below the human standard deviation and pulls the mean within a couple of marks of the human mean, so low absolute error and a well-aligned score histogram look exactly like validation while discrimination stays absent.

The cause is the task rather than the model — human markers agreed with *each other* on rank at only ρ=0.054. Build in the paper's own deployment diagnostic: establish first whether the task is sufficiently criterion-referenceable that human markers themselves assign stable and discriminative judgements [30]. That is what `criticality_class` records.

The strongest opposing figure, at full force: strong judges match controlled and crowdsourced human preferences "achieving over 80% agreement, the same level of agreement between humans" [31] — curated general-chat preference data under a 2023 protocol. More adversarially aware work does not reproduce it as a floor: after nine debiasing strategies across five judges the best configuration reached only 71.0% agreement; position swap on adversarial instances consistently and significantly hurts all models (−3 to −13 pp); and residual style bias dominates, humans preferring markdown only 57% of the time versus 73–97% for four of five judges [32].

Marketing copy, brand voice and creative briefs sit at the holistic end of that axis by construction, and the essay-marking analogy is a labelled proxy: **no source studies judge validity on marketing, advertising or brand-voice copy at all**, an absence that is itself a finding. One architectural trap follows from a mechanistic result: self-preference bias tracks familiarity rather than authorship, since judges "assign significantly higher evaluations to outputs with lower perplexity than human evaluators, regardless of whether the outputs were self-generated" [33]. An agent that both proposes edits and judges them with the same model family is structurally exposed, so the eval contract records the judge family and the register refuses a judge from the proposer's family.

### B. Block on contract, render quality as evidence, monitor for drift

**Block** automatically on deterministic contract properties: schema conformance, required disclaimers, banned claims, brand-name spelling, length bounds, no personal data echoed, no embedded credential or key, latency, cost. Beyond those the rule branches on `criticality_class`, which is the field's entire purpose. Where an asset is criterion-referenceable — structured extraction, a classification label, a templated document with checkable fields — a well-specified judge may additionally soft-block, because on that regime discrimination is real [30]. Where it is holistic — copy, tone, brand voice — the judge never scores and never blocks, and is used only to select divergence examples. The approver sets the regime per prompt family at first promotion; one universal policy would make the field decorative. A practitioner who abandoned the judge route puts it cleanly: regression testing isn't really a quality problem — it's a contract problem, and on a binary intent match "a judge model just adds noise" [34].

The structure is risk-aligned groups with independent thresholds, each category evaluated separately to detect domain-specific drift that aggregate metrics can mask, with worked thresholds above 95% pass rate for one category, 100% format compliance for structured output, and 0% security violations [13]. The aggregate is a liability rather than merely insufficient: one documented version improved overall accuracy by 10% while negation-handling collapsed 66.7%, from 100.0%→33.3% [34]. A single red category blocks regardless of the aggregate.

**Render** the subjective signal as evidence rather than as a score, because a number carrying no rank information, displayed with a green tick, manufactures false confidence in the person least equipped to discount it. The inference has stated provenance: near-zero discriminative validity on the closest studied analogue with confidence intervals spanning zero [30], plus the practitioner finding that teams "gather evaluation data but cannot translate findings into concrete improvements" [35].

Together they imply the correct rendering is **evidence a human can adjudicate**: three to five real production inputs where old and new versions diverge most, shown side by side, with the judge used only to *select which examples to surface*. Selecting which cases to surface asks only which two outputs differ most, not which is better, so it does not need the rank information the essay study shows a judge lacks — a design inference no source tests, and one that fails if divergence selection inherits the same residual style bias [32]. The mitigation is mechanical: rank divergence on embedding distance and contract-relevant deltas first, and use the model only to caption what changed. Vendor practice confirms side-by-side comparison is the interaction non-engineers actually use, putting "two prompt variants in separate columns" so product managers and domain experts can work without writing code [36].

**Monitor** on a schedule, because a pre-release gate structurally cannot see the failure mode that matters most. Chen, Zaharia and Zou (2024, *Harvard Data Science Review*) documented GPT-4's accuracy on identifying prime numbers falling from 84% to 51% between the March and June 2023 versions, and code-execution success from 52% to 10% within three months, with no version change [37], [13]. Anthropic's August 2025 postmortem documents three bugs affecting Claude Sonnet 4's performance "without any API modifications, including routing errors affecting up to 16% of requests" [13]. This is also the documented limit of the pre-deploy runner the design adopts — "PromptFoo catches regressions at step 1. It doesn't catch steps 2-6" [38] — which is why scheduled monitoring is a separate mechanism rather than an extension of the gate. So re-run the same deterministic contract against the currently serving model on a schedule, acknowledging that framework's own limits: threshold calibration lacks principled statistical grounding, run-to-run variability is real, and providers rarely expose version identifiers, so drift attribution operates under partial observability [13].

### C. Bootstrapping the contract, and who may change it

With no test set, the contract is built from production traffic: sample real inputs, keep those where the prompt is actually used, and have a human confirm a handful of expected properties rather than write expected outputs. Where a judge is used, alignment is maintained work rather than setup — one team logged the response, the judge's critique and the final outcome, reviewed them with stakeholders, and over three iterations improved agreement with humans from 68% to 94%, while naming criteria drift as a first-class failure, since perceptions of what counts as good and bad output "shift as they interact with more data" [14]. The meta-cost is explicit: "You must maintain a mini-evaluation system to track its quality" [39].

That settles the permission boundary. Prompt-text editing stays open to marketers and designers, since authorship is low-stakes and fully reversible through versioning, and gating it is the friction that drives people back to a spreadsheet. **Editing the production contract — thresholds, critical-category list, banned phrases — requires the stricter role**, because the contract is as unstable and as consequential as the prompt it gates, and leaving both editable by one person collapses the two-key structure human approval exists to provide. No source studies prompt-registry permission design directly, but this is not a lone inference: criteria drift and the criterion-referenceability framework reach it independently, and it is the only arrangement preserving that two-key property.

## 6. The Promote Gate — HITL, RBAC, and the Two-Minute Decision

Role-based access control (RBAC) means what a person may do depends on their role rather than their goodwill. The model is four roles against one escalating permission.

| Role | May |
|---|---|
| **Viewer** | Read |
| **Author** — any authenticated member of the group | Edit prompt text, create versions and run the contract, unwalled |
| **Owner** | Promote to production for the assets they own; holds the break-glass path |
| **Contract admin** | Edit thresholds, the critical-category list and banned phrases |

Two mechanisms follow that the incumbent cannot offer. *Propose versus edit*: a member of subsidiary B with no edit right on subsidiary A's asset still opens a candidate version that lands in the same pending state, which costs nothing extra because the decision object already separates requesting actor from deciding reviewer. *Auditability*: the incumbent's real failure is shared accounts, so per-identity attribution on every version and every decision is the baseline RBAC win, independent of any restriction. Combined with mandatory sign-off, this makes the promote click the product's one deliberate piece of friction.

### A. The delivery-performance attack, given full force and then answered

The evidence against a mandatory gate is unambiguous. No evidence was found to support the hypothesis that a more formal, external review process was associated with lower change fail rates [40]. Organizations with formal external approval processes were found to be 2.6 times more likely to be low performers, and, quoting *Accelerate*, external approvals were negatively correlated with lead time, deployment frequency and restore time, had no correlation with change fail rate, and were "worse than having no change approval process at all." UK regulator data across more than a million production changes shows the failure from inside: "CABs approved over 90% of the major changes they reviewed, and in some firms the CAB had not rejected a single change during 2019" [41].

Read what was measured: approval by people external to the team proposing the change — "a change advisory board (CAB) or a senior manager" — lacking context and expected to reconstruct the reasoning itself. The prescribed remedy is not removal but use peer review to meet the goal of segregation of duties, with reviews and approvals captured in the team's development platform [40]. The second term of that enumeration is uncomfortable here, because the approver persona is a manager. So this design escapes the penalty on a condition rather than by category: the approver must be the accountable owner closest to the prompt, holding context, deciding inside the platform from evidence assembled in advance. Route promotion up a management line instead and it reproduces precisely what was measured; an approver who has to go and find the evaluation results is a change-advisory board in miniature and earns the penalty in full.

The second attack is throughput-driven. As change volume rises, reviews become rubber-stamps: the human approves because the code looks correct, because the tests pass, and because the cognitive cost of genuine scrutiny is prohibitive, against a baseline where developers at large organisations spend between ten and fifteen percent of working hours reading and commenting on others' code — with a carve-out that describes a production-prompt promotion better than a routine commit, reserving approval for "high-risk changes, novel architecture choices, and regulated code paths where a named human must bear legal accountability" [42]. The practitioner literature supplies the failure signature — approvals within minutes of opening, substance-free comments, reviewers approving what they have not read — and **no quantified size threshold**; any line-count figure attributed to that source would be fabricated [43]. Two defences follow: at most one active candidate version per prompt awaiting decision, and instrumentation of the signature the source actually names, which is a conjunction rather than one metric — short time-to-decision *together with* a near-total approval rate, since short time-to-decision alongside a live rejection rate is the card working as designed [43]. This holds at first-year volumes and would need revisiting at hundreds of promotions per week.

### B. The legal basis, stated correctly

Neither regime obliges a pre-release human sign-off on an internal prompt-management layer — a reading taken from two Vietnamese legal analyses read in full with four further Vietnamese sources unread, which makes it the most provisional position in this report and the first to put to counsel. All four instruments on point read the same way: a runtime obligation, never a release gate on authoring tooling.

| Instrument | What it requires | What it is not |
|---|---|---|
| EU AI Act Art. 12 — record-keeping | High-risk systems "shall technically allow for the automatic recording of events (logs) over the lifetime of the system" [44] | A logging obligation on the deployed system, for post-market traceability — not a pre-release sign-off |
| EU AI Act Art. 14 — human oversight | High-risk systems designed so that they can be effectively overseen by natural persons during the period in which they are in use, the enumerated capacities being to monitor, interpret, disregard, override or interrupt a running system [45] | The one two-person requirement is a check on identifications made by biometric systems in use, not a release gate |
| Vietnam — deployer obligations, high-risk systems | Operators run and monitor the system in accordance with its intended purpose and "maintain the possibility of human intervention during use" [46] | A runtime intervention capacity, not a release gate |
| Vietnam — the Decree's internal-use exemption | Applies narrowly to AI-generated-content and deepfake labelling [46], [47] | Not a general carve-out from risk classification or documentation duties |

Two Vietnamese clocks are both real and routinely conflated.

| Clock | Trigger | Deadline |
|---|---|---|
| **Grace period** | The Law takes effect 1 March 2026; grace applies to most existing providers and deployers | "lasting until 1 March 2027 (or 1 September 2027 for AI systems in the fields of health, education and finance)" — twelve months generally, eighteen for finance, healthcare and education, independently corroborated [48], [49] |
| **Transition notice** | Conditional, and the condition is the actionable part. Risk classification into three tiers must occur before a system is put into operation, by self-assessment or a conformity-assessment body; only medium- and high-risk systems are then notified to the Ministry of Science and Technology through the one-stop portal, and low-risk systems carry no notification duty at all | For a system already operating before 1 March 2026 and classified into those tiers, the transition notice with a plan or compliance scheme is due within 60 days from the effective date of the Decree (i.e., before June 30, 2026) [47] |

The first action a product team owes is therefore classification, not notification. Two obligations, two clocks; do not merge them and do not drop either.

So why keep mandatory approval? Corporate segregation of duties: the person who writes a production change should not be the only person who releases it, an argument an internal-controls function recognises immediately. Prophylactic readiness: the group's downstream products may clear Vietnam's medium- or high-risk classification, and an approval record with pre-computed evidence is a plausible component of satisfying their documentation and oversight duties. And most consequentially for design, automated judging carries near-zero rank information on exactly the holistic copy this product's users produce.

The honest form of that argument is narrower than it first looks: in the same study human markers agreed with each other on rank at ρ=0.054, so the human is not a better *ranker* of holistic quality either — on this task class nobody is. What only an accountable human supplies is consequence judgment and ownership of the outcome: whether *this version stops asking for the customer's budget* is acceptable for this brand, this audience, this quarter. That is why the card renders divergence in consequence language and never asks for a quality score. The gate is load-bearing not because the human scores better than the model, but because on this task class scoring is the wrong act and someone must own the decision.

### C. Four jobs, one card, ordered by what actually blocks

The gate is being asked to read an evaluation result, exercise judgment automation cannot supply, confirm agent-drafted metadata, and check cost and blast radius, in two minutes. Asserting the card is well-designed does not make those compatible; ordering and defaulting does.

1. **Blocks, zero human effort.** Deterministic contract results per risk category run before the card is generated, so a failing candidate never reaches the approver. The card shows one line: six of six categories pass, or the named failure and the input it failed on. This is the only job that blocks.
2. **Pre-computed, glanceable.** Blast radius — which products fetch this prompt and how many calls in 30 days — and the cost-per-successful-task delta in local currency, both derived from telemetry already held.
3. **Pre-computed, adjudicable — the two minutes.** Three to five real production inputs where old and new outputs diverge most, side by side, under a consequence-language diff: *this version stops asking for the customer's budget*. No score. This is the job the human is uniquely qualified for.
4. **Demoted and defaulted.** Semantic capture: one agent-drafted purpose line, editable in place, asked **only on the first promotion of a new asset and on canonicalization merges**, never on every version. A genuine concession — capture on every promotion is what the schema would prefer, and the rubber-stamp evidence says it would degrade into reflex clicking.

When the approver does nothing but click approve, the production pointer moves, the owner of record is set to the approver, the evidence snapshot freezes into the decision object, and the governance state becomes governed. Tier 2 fields keep their drafted values flagged `ai-drafted, unconfirmed` and are displayed that way everywhere: a field that honestly says *we think this prompt does X and nobody has confirmed it* is safer than a confidently wrong confirmed one. Nothing silently becomes true that was not true — the property distinguishing a real approval object from a label write — and it lets the register report what fraction of governed assets have a human-confirmed purpose.

An emergency path is mandatory. A system that adds more steps than it removes produces a shadow process rather than compliance [50]; the design consequence drawn here is a break-glass promotion, available to the owner, logged with a required one-line reason and generating a review task due within 24 hours, so the gate is escapable under load rather than routed around permanently. A gate with no sanctioned exception acquires an unsanctioned one.

## 7. Cost and Token Economics as a Release Control

Cost is the one number a marketer, a manager and a finance partner all understand without training, which makes it the register's most effective vehicle for governance that does not feel like governance. It is also the constraint most easily built wrong, because the obvious implementation — count the tokens in the prompt, alert when the number rises — measures the wrong thing.

### A. Prompt length is not cost

The counter-example is specific and well instrumented: "aggressive compression reduced input tokens by 17 percent and still increased total session cost by 67 percent. The model had less text to read and more work to do" [51] — one practitioner report relaying a paper rather than a controlled multi-site study, and weighted accordingly. The other side deserves its strongest form: compression research reports up to 20x compression at under 2% quality loss on standard benchmarks [52], itself vendor marketing relaying research it did not conduct; and a formal treatment establishes the frontier is real while finding "a large gap between the performance of current prompt compression methods and the optimal strategy" [53], available at abstract level only.

The claim is not that compression does not work, which overreaches on one report, but the narrower and better-supported one: **input-token delta is not a valid proxy for cost delta.** A length-based gate fires on changes that reduce spend and stays silent on changes that raise it — worse than no gate, because it is confidently wrong and will be trusted. The register instead measures **cost per successfully completed task over a traffic sample, including retries and multi-turn recovery, attributed to the prompt version.**

### B. The implementable architecture, and one arithmetic trap

The shape comes off the shelf from gateway practice:

- **Per-request metadata tagging** — the gateway stores a JSON object on the trace and "projects a curated subset to low-cardinality metric labels".
- **Per-trace cost** — computed at span close from `gen_ai.usage` attributes and a versioned pricing table.
- **Two-tier enforcement** — soft alerts at 80% of budget, hard limits returning HTTP 429 with a `budget_exhausted` error, plus a degradation path to a cheaper model tier so the pipeline does not stop.

The same source flags a trap that would otherwise be found in production — `gen_ai.usage.input_tokens` "is defined as the total including both cache lines," so subtracting once for cache_read but not for cache_write "double-counts the cache-write portion" [12]. Wrong cache accounting produces cost deltas that err in the direction of looking good, the worst available error; and an unversioned pricing table lets historical figures silently change when a provider re-prices, which makes it not a ledger.

The join key is standardized by OpenTelemetry's generative-AI semantic conventions, an open standard defining vendor-neutral attribute names for model calls: `gen_ai.prompt.name`, the name of the prompt that uniquely identifies it, alongside `gen_ai.usage.input_tokens`, `output_tokens`, `cache_creation.input_tokens` and `cache_read.input_tokens`, plus `gen_ai.provider.name` (enumerating `aws.bedrock`, `gcp.vertex_ai`, `openai`, `anthropic`), `gen_ai.request.model` and `gen_ai.response.model` — all non-content attributes. Content-bearing attributes are separately deprecated and gated, with `gen_ai.prompt` "Removed, no replacement at this time" and the message attributes warned to be "likely to contain sensitive information including user/PII data" [11].

That supports an inference with a significant consequence for a conglomerate. The attribute gating is sourced [11]; the cost-computation mechanism is sourced [12]; together they imply that **the hardest of the four constraints can be satisfied entirely on non-content telemetry** — so the register can populate the cost field for a subsidiary's customer-facing product without ingesting that product's user data. No source states this. It converts a data-governance blocker into a configuration default.

### C. Showback before chargeback, gate before chart

To the editor, cost is ambient and non-blocking: a small figure beside the editing field showing modelled monthly cost at current traffic, in local currency per month rather than tokens per call. To the approver it is binding: a delta above a per-asset threshold requires an explicit override captured in the decision object with a reason. One caveat is structural, and §7A creates it: cost per successful task cannot exist for a version that has not yet served production traffic. The promote-time figure is therefore a modelled estimate — the candidate replayed over a sample of recent real inputs, priced from the versioned table, retries counted — and it is the weaker of the two measures, which is why the same threshold also arms a post-promotion alert over the first window of live traffic and the override record names the estimate it relied on, so the two reconcile later.

Beyond the single asset the ledger rolls up on the dimension a group actually budgets on, the finance cost-centre, and the sequencing in the heading is a real decision: run showback, where each team sees its own number with no bill attached, long enough to surface attribution gaps, and only then charge back, because billing before coverage holds produces disputes rather than accountability [54]. That source also names the trap this product inherits from its own incumbent — one shared API key across several teams prints a single total and no owner — which is why attribution is captured at the call from `gen_ai.prompt.name` rather than reconstructed from an invoice [11]. The override record is itself a register field, answering *who decided the group would pay 40% more for this* — a question a ledger exists to answer and a dashboard structurally cannot. Cost can block where quality cannot precisely because it is a contract property: deterministic, code-checkable, reproducible. Two honest limits. First, cost per successful task requires a definition of success; for a marketing prompt the working proxy is completion without a contract violation and without a human re-run in the same session — a defensible heuristic rather than a measurement. Second, the counter-example rests on one practitioner report against two sources including a formal analysis, so the narrow proxy claim is well supported while a broader verdict on compression is not.

## 8. Distribution to Products — API/SDK, Parity, and Failure Modes

Developers are the third persona and have the least influence on whether a marketer adopts the register — right up until the register causes a production incident, at which point that team bans it and the marketer's tool dies with it. The moment a product fetches a prompt at request time, the register sits in that product's inference path and can take it down.

### A. The reliability bar, and the decision it forces

The documented shape of a safe prompt-serving layer is specific: client-side caching in the SDK, so "there's no latency impact after the first use and no availability risk"; stale-while-revalidate, where stale prompts "are served immediately while it revalidates in the background"; and a layered server cache where "if Redis is unavailable, the database serves as backup" [28]. One failure mode remains, documented rather than hidden: the fetch throws if no local cached prompt is available, fresh or stale, **and** the network request fails after retries — mitigated by prefetch-and-exit-on-failure at startup, and by a hardcoded fallback prompt compiled into the client used when both the cache is empty and the API is unavailable [55].

Convergent design in an unrelated domain confirms this is not one vendor's habit. Mobile and game remote-configuration guidance independently prescribes the same pattern — products should continue to function smoothly even if a Remote Config fetch is delayed, times out, or returns an error, teams should provide a local default for every Remote Config key, and the last successful fetch is cached on the device [56]. Two industries with no shared lineage arriving at cache-plus-time-to-live-plus-async-refresh-plus-local-default is about as strong as adjacent-domain mechanism evidence gets.

The highest-leverage scope call in the design follows: **the register must not sit in the hot path.** It pushes approved versions down into each product's existing runtime store — Bedrock's create-and-version APIs, Vertex's equivalents, or a lightweight store for self-hosted services — so each product keeps reading from the store it already reads from, at the reliability that store already provides [22], [24], with telemetry flowing back the other way [11]. If the register is down, no inference call fails; only promotions and reporting pause. The concession is scoped: products with no existing prompt store — a self-hosted service with prompts as string literals — need something to be the store, and for that path alone the full cache-plus-fallback shape must be implemented, because there is no vendor underneath to inherit it from. That is a requirement, not a demonstrated feasibility on a short timeline.

### B. Parity is the credibility contract

The aggregation claim is real because the vendor surfaces do not span each other. Bedrock operates within a single AWS account behind an IAM identity [22]; Vertex manages prompts within your Google Cloud project, with listing scoped to "the current project" [24]. Chaining those two mechanism documents yields an inference neither vendor states: a group running products on both cannot purchase a single ledger, because neither scope unit spans the other. One honesty note — neither documentation set was checked against AWS Resource Access Manager cross-account sharing or Vertex's organization and folder hierarchy, so the claim holds firmly *across* providers and is unverified *within* one provider's multi-account estate.

Parity is therefore a field, `runtime_bindings[]` with per-target push status and remote content hash, catching three failures that would otherwise make the ledger lie.

- **Divergence** — someone edits directly in a provider console, and hash mismatch flags it; silent overwrite is the wrong default because it destroys the evidence that a governance bypass occurred.
- **Partial push** — version 7 landed on one runtime and failed on another, so *which version is in production* has two answers and the register must show both.
- **Silent substitution** — `gen_ai.response.model` differs from `gen_ai.request.model`, meaning the bundle running is not the bundle approved [11].

The developer contract should be deliberately small: fetch by name and label, receive content plus version identity plus declared metadata, and link every generation to the version that produced it so per-version metrics separate cleanly [27]. Products fetch the `production` label by default and may pin an explicit version for high-blast-radius paths; a pinned consumer still resolves a deprecated version and stops resolving a retired one, which makes the retirement path real rather than cosmetic. Test environments fetch by a different label, so staging never serves an unapproved version [20]. The served payload declares BACKWARD compatibility — consumers using new schema can read data written with old schema (add optional fields, remove fields), the default mode in established schema-registry practice [57] — because a register that breaks three products' deserializers on a Tuesday will never be trusted in an inference path again. The developer also gets something back for the migration, and it is the same artifact the gate uses: the asset's deterministic contract runs as a pipeline step in the product team's own repository, tagged with the commit, so a failing prompt change is caught at the pull request rather than at the promote click [58].

The *shared* prompt set — `dùng chung` — is the other half of the API/SDK requirement, and it is a serving decision rather than a curation exercise. The register already holds the mechanism: a cluster resolved to one canonical asset with named variants *is* the shared set. So group-level fragments — brand voice, safety preamble, disclosure block — are separately versioned assets that a product prompt references by frozen slug, which makes promotion of a shared fragment one approval rather than thirty and makes its blast radius span subsidiaries. Without that, each subsidiary's brand-voice preamble is a separate asset and the founding problem is reproduced one level up. Cross-subsidiary blast radius is what distinguishes a group ledger from a team one.

### C. The architecture in one view

| Component | Owns | Writes |
|---|---|---|
| Discovery scanners | Code scan, document connectors, telemetry orphan detection | `imported` records, `discovery_method` |
| Clustering service | MinHash pre-filter plus embedding pass, run on every save | `cluster_id`, canonicalization proposals |
| Asset store | The Tier 0/1/2 schema; single system of record | All asset fields |
| Approval-decision service | Pending state, actor≠reviewer, frozen evidence snapshot | `production_pointer[env]`, `owner_of_record`, `governance_state`, Tier 2 |
| Contract runner | Deterministic per-category checks, off-the-shelf | `contract_status`, `last_verified_at`, the card |
| Push adapters | One per runtime — Bedrock, Vertex, self-hosted store | `runtime_bindings[]`, remote content hash |
| Telemetry ingest | OpenTelemetry `gen_ai.*` non-content attributes | `consumers[]`, `calls_30d`, `cost_30d` |

One flow invariant governs the whole table: approved versions are pushed **down** into each product's existing runtime store and telemetry flows **back**, so the register is never in the inference hot path.

## 9. The Agent Layer and the Build / Buy / Layer Decision

The brief asks for an agent that creates, edits, versions and improves prompts. The market already sells most of that. The useful question is narrower: what is structurally unavailable from any vendor at any price? A disciplined framework asks whether existing solutions fit or requirements are genuinely bespoke, and whether the capability forms part of the company's own offering [59].

### A. Four durable surfaces, plus one standing control

Version storage, immutable numbering, draft states, diff views and playground interfaces are emphatically not bespoke; hyperscalers and open-source tooling ship them at a reliability standard a small team cannot match on a short timeline [22], [24], [20]. Reuse wins there by the framework's own test. Cross-account, cross-provider aggregation carrying owner, lifecycle and cost, and a real approval-decision object, are sold by nobody.

Maintenance economics bound the build from the other side. Internal tools fail on day two rather than day one — getting a build working on one person's computer is straightforward, but who's going to take responsibility for updating libraries, or maintaining test cases? [59]. Every built surface is therefore a standing liability someone must staff forever. That also answers the objection that a layer thin enough to be maintainable is too thin to be worth adopting: the three distinctive pieces — the ingestion agent, the embedded capture surface, and the clustering that compensates for missing merge semantics — sit outside the durable list because the two lists answer different questions. The durable surfaces are **what you must be able to operate** in three years; the differentiators are **what you must be able to demonstrate** now. Neither of the latter sits in an inference path, which is exactly why they are cheap to build first and dangerous to promise durably.

The durable list is four rows of that architecture table — the **cross-provider asset schema**, the **approval-decision object**, the **per-runtime push adapters** and **non-content telemetry ingestion** — plus a fifth entry with different status, since label-based versioning has no merge semantics and duplicate clustering is the only mechanism that catches divergent edits, making it a permanent operational control rather than onboarding sugar. The honest count is **four durable surfaces plus duplicate clustering as a standing control**, not a tidy four. The deterministic contract runner is not on it: assertion execution is emphatically not bespoke by the framework's own test, so the platform invokes an off-the-shelf open-source runner rather than building one. All four exist to populate the four asset-register fields, which is why scope discipline is not an independent constraint coexisting with the asset framing; it *is* the asset framing expressed as a build list.

### B. The keystone: one component satisfying three independent requirements

The approval-decision object is the strongest architectural claim available, because three separately derived arguments converge on it.

It is the **market gap across every surface examined here** — a claim scoped to what was read, not a survey. Across the four vendor surfaces read in full (Langfuse, PromptLayer, Bedrock, Vertex) promotion is a role-gated write to a pointer with no pending-review state, no evidence record, no reviewer distinct from actor and no rejection path. LangSmith, Azure AI Foundry and Braintrust's eval-coupled versioning were not read in this pass, so the gap is established on four surfaces and asserted no further. The confirmation runs to database-schema granularity: when users asked in November 2024 how to move a prompt label programmatically, the documented temporary solution was raw SQL against a Postgres `prompts` table, and a maintainer confirmed label updates had shipped "via our API / SDKs" only in January 2025 [60]. There was a labels column; there was never an approval object. And the vendor concedes it in its own voice, stating that it does not ship a built-in pull-request-style approval flow for prompt promotions and placing multi-step approval workflow in the **Composed** column of its own capability table rather than the **Native** column, with the documented workaround being four mechanisms glued together: protect the label, post continuous-integration evidence to a pull request, notify approvers by webhook, keep audit logs on an enterprise plan [27].

It is the **sanctioned bespoke surface** under the complexity and core-capability test [59]. And it is the **agent's output target**, because what a human should review is an assembled evidence card rather than a raw diff carrying a machine's account of its own reasoning.

Concretely, the object carries:

- a decision identifier
- asset, from-version and to-version
- requesting actor and deciding reviewer, with a hard constraint that they differ
- state: pending, approved, rejected, withdrawn or expired
- an immutable evidence snapshot — contract results per category, advisory signals with the judge model named, cost delta with the pricing-table version used, blast radius at decision time, model binding, and the divergence examples exactly as rendered
- a decision rationale, required on rejection
- the semantic-capture payload with its confirmed-or-drafted flag
- push results per runtime binding Two properties make it an object rather than a log line — it exists in a pending state before the write, and it has a rejection path. Both are absent from all four surfaces read.

### C. The agent, narrowed rather than dropped

The literal capability the brief requests is commoditized; the closest shipped competitor's optimizer fires from human annotations and gates consequential actions behind confirmation [61]. Competing there is a poor use of a small team, and ungated generic improvement is measurably dangerous. A controlled ablation found that generic prompt additions do not produce monotonic improvements, with the largest decline taking retrieval-grounded compliance from 26/30 to 9/30 — 86.7% to 30% — because instructions to be helpful and comprehensive encouraged the models to hallucinate information not present in the source documents [62], [63]. The harm is dimension-specific — the same edit improved instruction-following — so there is no scalar better prompt.

The four-condition ablation localises it, which is the part a builder can act on: a system-level wrapper alone changed nothing, while appending generic rules to the *user* prompt is what degraded grounding [63]. The build rule follows directly — the exception reporter may propose task-specific contract language, never generic helpfulness rules appended to the user prompt. The paper calls its results existence proofs on small synthetic suites with two local quantized models, so the mechanism transfers and the percentages do not.

The agent therefore has three jobs. Its lead job is **ingestion and mapping** — scanning, extracting, clustering, naming clusters in human language, drafting the semantic fields — because that is where nothing is commoditized and where the register's own fields get populated. Its second is **evidence-card assembly**, rendering a version diff in consequence language rather than character-level marks. Authoring assistance survives inside this, but only in the form the evidence licenses: drafting a first version from a stated intent and rewriting in place on request, always checked against the asset's own deterministic contract and always as a proposed new version the author accepts or discards — the annotation-triggered, confirmation-gated shape the closest shipped competitor uses [61]. The problem statement asks for an agent that helps create and edit; that ask is met at the keystroke. What is refused is the unsupervised generic improvement sweep.

Its third job is a **rate-capped, eval-pre-validated exception reporter**: it fires only for assets that already have a task-specific contract, only when a failure cluster or cost signal crosses a threshold, and every candidate must clear a held-out slice of that asset's own suite before a human sees it — mirroring the split an open-source implementer describes, 40% train, 40% validation, and 20% test, so an overfitted prompt "will fail on validation and be discarded" [64]. That source reports no quantified train/test generalization gap; the split is asserted design intent rather than a measured result. At most one active candidate per asset — a reasoned default, since no source quantifies a rate cap.

The ingestion differentiator deserves an honest label. **No source shows any competitor doing it**, an argument for novelty rather than efficacy — simultaneously the strongest reason to believe this product is not a reimplementation of an existing tool and the least evidenced claim in the design.

## 10. Adoption Inside the Organization

The competitor is not a funded LLMOps platform. It is a spreadsheet with a shareable link, instant editing, no permission wall and years of muscle memory, and against that incumbent feature richness is a tax rather than an advantage. The evidence here is the weakest in the report: none of the relevant sources is about prompt registers, none is peer-reviewed, and none reports a controlled study or a sample size.

### A. The mechanism, named by four unrelated fields

Teams revert to spreadsheets when the official system feels slower than the workaround, harder to trust, or disconnected from how the work actually happens, with the first root cause listed as the official platform adds more steps than it removes. The same source warns that "buying another platform rarely fixes spreadsheet reversion if process design is weak" [50]. Data governance reaches the same place from the opposite direction, the entry ticket leaving the catalogue "a tool reserved for data teams" while departments "continue to operate outside the system" [8], [10].

Creative-production operations supplies the migration rule and this product's own problem statement: the most common migration failure is asking a team to abandon a working tool before the replacement can do what the tool does, and AI tools used individually without integration into the shared environment are a new category of shadow workflow, scaling "significantly faster than it did in the spreadsheet era" [65].

The same source carries the three rollout steps this design must not drop:

1. **Migrate the live content**, not the structure — teams abandon a new system the moment they need information that exists only in the old one.
2. **Name a transition owner** per migrated team, who validates coverage and flags gaps through the first four weeks.
3. **Declare single source of truth** from first live use — if it is not in the register it does not count for decisions.

Four genuinely unrelated fields converging on one mechanism without citing each other is meaningful corroboration; convergence of diagnosis is still not measurement of effect, and the transfer to prompt registers remains analogical judgment. One instrument comes out of it directly: the same diagnostic treats reporting exports as the tell that daily execution is about to migrate back to a spreadsheet, so **export volume from the register's own browse view is a leading indicator of failure and should be instrumented on day one** [50].

### B. The friction budget, spent deliberately

| Sheet affordance | Matched? | What compensates |
|---|---|---|
| Instant edit — click, type, done | Approximated | The prompt body is one large freeform field with silent autosave and no submit button; every other field is optional or inferred. Match on the field that matters |
| No permission wall | Deliberately not matched | One wall, at promote-to-production. Everything upstream stays as unwalled as typing in a cell, and spreadsheets never gated production releases, so nothing is taken away |
| Free-text anything | Partially matched | Exactly two required fields at creation: name and body. Everything else is inferred from ingestion context |
| Shareable link | Fully matched, required day one | Single-sign-on-scoped permalink to a specific prompt and version, no folder drilling, no visible login for an authenticated member |
| Zero learning curve | Unmatchable by definition | Mimic the mental model rather than inventing one: the default view is a sortable, filterable grid where rows are prompts and columns are owner, state, version, cost |

Two of five are structurally unmatchable and one is deliberately traded away, so *replicate before retiring* cannot mean parity. It means parity on the affordances that drive the abandonment decision — edit speed, unwalled authoring, link sharing — in exchange for something a spreadsheet structurally cannot do: versioned, auditable, cost-gated promotion.

The ledger is a destination and its capture surface is embedded, two jobs the word *catalogue* conflates. Unlike a data catalog, a prompt register is not an index pointing at assets someone else owns; it is the system of record for the artifact itself. That is not the same as being the serving store — §8 deliberately keeps it out of the inference path, pushing approved versions down into each product's runtime — and that distinction is the whole answer to the objection: one record of truth, serving copies wherever the products already read [28]. But prompts are born in chat threads and document cells, and if the only way to add one is to visit the register, the register will hold the prompts people remembered to file — precisely the population an asset ledger is useless for. A forward-to-bot or browser capture path is what prevents day-30 re-fragmentation, and the shadow-workflow finding says that clock runs fast [65].

The first-session bar is falsifiable: if a first-time user does not see their own existing prompts, deduplicated and browsable and editable, within roughly the first minute, the win condition is unlikely to be reached, because a bookmarked spreadsheet clears that bar trivially. Governance depth sustains retention from week four; it does not win session one.

### C. Two boundary conditions a Vietnamese group makes live

The friction differential dominates under *organic* adoption. A mandate changes which axis dominates, and the same diagnostic treats leaders bypassing the system as a separate problem class from tool fit [50]. A conglomerate plausibly has mandate available, which reduces but does not remove the friction requirement, because a mandated system slower than the workaround produces parallel records rather than compliance.

The second is a gap: **no source addresses software-adoption behaviour inside a Vietnamese corporate group, approval-hierarchy norms in that setting, or whether Zalo rather than Slack is the real incumbent chat channel.** Every Vietnam-specific source located is legal or regulatory analysis [48], [46]. The consequence is a build instruction rather than paralysis: make the capture connector interface pluggable rather than hard-coding one chat platform, and treat the pilot team's actual channel mix as a week-one finding.

## 11. Build Sequence and Demo Proof Points

Two ordering principles govern the sequence and point the same way. Build the thing nobody sells before anything anybody sells, and build what wins session one before what sustains the quarter.

| Phase | What ships | Note |
|---|---|---|
| **0 — schema and approval object** | Asset and decision tables, the state machine, the actor-differs-from-reviewer constraint, the frozen evidence record, per-field provenance stamping [7] | First because three independent arguments converge on it, because every later surface writes into it, and because it is the cheapest of the four in engineering terms — a data model and a state machine, not a distributed system |
| **1 — ingestion and clustering, built thinly** | One document connector, a chat-export parser, repository scanning [15], a MinHash pre-filter with an embedding pass [18], the `imported` state with one-click claim, discovery-method provenance per record, the grid | Batch rather than real-time |
| **2 — authoring and one adapter** | Silent-autosave editing with no submit button; one push adapter end-to-end against whichever runtime the pilot product uses, with reconciliation; the fetch-by-label contract with a declared BACKWARD compatibility mode [57] | — |
| **3 — contract and telemetry** | Deterministic per-category checks for one prompt family, executed by an off-the-shelf open-source runner (promptfoo or equivalent) the platform invokes rather than one built in-house [13]; non-content telemetry ingestion and cost per successful task with correct cache arithmetic [11], [12] | Makes the evidence card carry real numbers rather than placeholders |
| **4 — drift monitoring and the rest** | Scheduled drift monitoring; the exception-reporting agent; role separation of contract editing from prompt editing; embedded capture against the group's actual channel | Only the first of these is sourced: a CI-triggered evaluation cannot see provider-side change, so monitoring must run on a schedule independently of edits [38]. The other three are this report's design choices, sequenced last because each depends on the earlier phases being in use |

The mandated stack maps onto the phases without strain.

- **Postgres** holds the asset and decision tables, with pgvector for the embedding pass, so Phases 0 and 1 are a schema plus a batch job rather than a distributed system.
- **FastAPI** serves the fetch-by-label contract and receives the OpenTelemetry non-content export.
- **LangGraph** runs exactly two graphs — the ingestion and cluster-naming agent, and the evidence-card assembler — which is where its human-in-the-loop interrupt maps onto the promote gate directly.
- **Docker Compose** ships everything in one file, so the demo runs offline on a laptop.

Phases 0–2 are the demo-critical path; Phases 3–4 ship partly stubbed.

**Stubbed, not deferred — present in the demo, not production-grade behind it:**

- a seeded export standing in for live Notion and Drive crawling, where the connector interface is real and the crawl is not
- a second runtime binding faked against a local store, so the partial-push and divergence failures are demonstrable without a second cloud account
- a pinned pricing-table snapshot rather than a live price feed, versioned so the arithmetic stays honest
- the divergence selector running over a pre-computed pair set rather than live traffic
- directory-backed identity mocked to a fixed user list, with the actor≠reviewer constraint enforced for real

**Explicitly deferred:**

- any unsupervised generative improvement sweep beyond drafting semantic fields and rewriting on request
- branch-like workflows
- a replacement prompt store
- judge-based scoring on holistic assets, the soft-block regime for criterion-referenceable families being a Phase 4 item rather than a demo one
- chargeback reporting, which follows showback
- anything resembling tracing, where free tooling is better and competing is a category error [66]


The demo runs four beats with a non-technical persona at the controls, each visibly writing to the ledger.

1. **The map** — proving ingestion from chaos: a real or seeded export ingested live and rendered as a deduplicated browsable grid, with a cluster card as the visual payload — *seven near-identical versions of your welcome-email prompt across three sources* — under the two-population headline rather than a single inflated count [10].
2. **The edit** — proving versioning and rollback without a deploy: an inline change with no save button producing a new version automatically, then a one-click rollback moving the production pointer, with the cache interval shown rather than hidden [20].
3. **The wall** — proving the two-minute HITL *and* the cost gate: one promote click producing one card — contract results by named category, blast radius, three divergent output pairs side by side, one drafted purpose line. It runs deliberately on a version whose cost-per-successful-task estimate crosses its per-asset threshold, so the approver cannot proceed without typing an override reason, and that reason is then shown written into the decision object. Then the negative case: a rejection returns the candidate to draft rather than deleting it — a state transition no surveyed tool provides, since a label write has no rejection path to return from.
4. **The export-killer** — proving the ledger's four fields: one view, no export, answering what is running in production right now, who owns it, what version, what it cost in the last 30 days, and when its contract was last verified [50].

The third beat is where the phrase *sổ tài sản* stops being a tagline and becomes a screenshot, because owner, production pointer, consuming products and cost are all populated by the click and none of them typed by a human. One beat should not be performed: do not demonstrate the agent rewriting a prompt and declaring it better, a demo both commoditized and unsound, where anyone who knows the literature will ask what the score means [62], [30]. Scope discipline deserves to be an explicit deliverable, because registry plus versioning plus evaluation plus agent plus distribution is the roadmap of twenty funded companies.

## 12. Where the Framing Breaks — Risks and Counter-Evidence

**The evidence is asymmetric, and it does not favour the product.**

| The positive case rests on | The negative case rests on |
|---|---|
| A premise measured in a git-structured public population dominated by prompt-collection repositories [4] | MLflow reversing its own lifecycle design after extensive feedback [5] |
| Adoption evidence transferred analogically, with no controlled study and no reported sample size [50], [65] | Configuration-database field-ownership rot with a named mechanism [6] |
| An ingestion capability whose novelty is not efficacy | Data-catalog adoption failure from two independent directions [8], [10] |
| A governance framework whose most articulate advocate is a practitioner opinion column [1] | Feature-store scepticism from a practitioner who notes that most positive content in that category is written by feature-store providers [67] |

These two bodies should not be presented with equal confidence.

One finding cuts the other way, and one cuts back. Across the literature searched — configuration-management, data-catalog, feature-store, model-registry, DevOps-governance and headless-CMS sources — every negative voice but one critiques a mechanism (external change-advisory approval, manual-entry catalogs, rigid stage enumerations) while treating governance of the artifact as sound in principle. The exception objects on the merits: centralizing into one shared store "creates a data dependency" that forces cross-team coordination on every change, and the lighter default proposed is a git-maintained catalog of definitions offering "loose coupling between teams" where each team upgrades at its own pace [67]. That objection lands on this design, and the answer is scope rather than denial: the register centralizes the *record* while serving copies stay in each product's own runtime (§8), so no product's release is coupled to another's. Where that separation fails, the objection holds.

**The keystone risk is that bulk import manufactures the decay the register exists to prevent.** The two-tier schema works only where the approval action genuinely touches every version that matters, and a migration sweep produces a population that never passes it. The two-population design is the committed answer, and its residual risk is unresolved by any source: **nobody has measured whether approval-time confirm-or-edit fields get filled with real judgment or rubber-stamped**, and the code-review failure signature is qualitative, carrying no quantified threshold [43]. If promote-time confirmation proves as neglected as a standalone stewardship task, collapsing capture into the approval step relocates the entry-ticket problem rather than solving it. The answer is instrumentation: because every semantic value carries its `ai-drafted` versus `human-confirmed` flag, **the product measures its own rubber-stamping rate as a first-class metric** — edit rate on the pre-drafted purpose field, governed fraction on the front page, median time to decision. If the edit rate stays near zero in a pilot, the honest response is to stop claiming the semantic fields are trustworthy rather than to add a mandatory text box.

**The gate does not scale, and the escape should be designed now.** Since the rubber-stamp mechanism is throughput-driven, per-prompt-family risk tiers — low-blast-radius prompts promoting on contract-pass alone with post-hoc notification — are what reserve human approval for the decisions that genuinely require it [42].

**Vendor commoditization will close half the gap.** A vendor shipping a pending-review state with an evidence record and a rejection path would convert the keystone from a moat into a feature, and the composition path is already documented as a workaround, usually the last step before a native implementation [27]. The cross-provider half will not close, because it would require a vendor to build a first-class view of a competitor's resources. The durable defence is the accumulated history rather than the feature: the ingestion history and the approval record are organization-specific and non-portable. Relatedly, do not over-borrow the registry pattern — much of the abstract asset-registry architecture in circulation is inherited from feature-store marketing, and of that source's four adoption reasons — preventing repeated development work, preventing repeated computation, fetching features absent from consumer input, and train-serve skew — only the first maps onto prompts at all. The source explicitly declines to cover discoverability and lineage, so it cannot be cited for them [67].

**Audited absences, carried as findings.** Searching the configuration-management, data-catalog, model-registry, evaluation, code-review, adoption and Vietnamese legal literatures returned nothing on eight points, each argued where it arises:

1. Duplication inside a single organization's document estate (§1C).
2. Any published method for extracting prompt candidates from documents or chat exports (§3A).
3. Non-technical adoption of any AI-artifact register (§10).
4. Any Vietnam- or conglomerate-specific organizational evidence (§10).
5. Judge validity on marketing or brand-voice copy, where essay marking stands as a labelled proxy throughout (§5A) [30].
6. Any quantified review-size threshold for rubber-stamping (§6A) [43].
7. Any measured train/test generalization gap for the open-source optimizer (§9C) [64].
8. The three vendor surfaces named in the brief but not read (§9B). One relayed projection about agentic-AI project cancellations is a vendor relaying an attribution rather than an independently verified source [7], so it is load-bearing nowhere here.

## Source Tensions

Seven tensions run through the evidence, each argued where it arises.

| Tension | Sources | Where resolved, and how |
|---|---|---|
| **Fewer tokens versus lower cost** | [52], [53], [51] | §7A — input-token delta is not a valid proxy for cost delta. The claim is about the proxy, not about whether compression works |
| **Judges that match humans versus judges that cannot rank at all** | [31], [30], [32] | §5A/B — the only tension where the second side wins by *explaining* the first: the variable is criterion-referenceability, and the block rule branches on it [35] |
| **The register as destination versus discovery in the flow** | [10], [8], [1], [55] | §3C and §10B, by splitting the functions: the ledger is the system of record and a destination, capture is embedded and built thin, serving stays in each product's runtime |
| **Approval as a drag on delivery versus approval as accountability** | [41], [40], [42], [44], [46] | §6A, on a condition rather than a category, since a senior manager is inside the measured population: the approver must hold context and decide from pre-computed evidence inside the platform. Two qualifiers survive — the theatre mechanism is throughput-driven, and the basis is segregation of duties, not a statutory command |
| **What a prompt inventory can actually see** | [16], [15] | §3A — neither method sees the governed population, document connectors are the structurally required third, and `discovery_method` per record keeps coverage claims honest. Shadow-AI material is cited for method, never for prevalence |
| **Whether a prompt is an asset in any sense that survives scrutiny** | [3], [68] | Both sides stand; §1B keeps them apart — nothing reaches a balance sheet, and the claim doing the work is managerial and judged on the four fields |
| **Git's branching versus the label pointer a non-developer can move** | [26], [20], [21], [25] | §4B, by the persona commitment, at an uncompensated cost paid by continuous duplicate clustering |

## Opinionated Synthesis

Build the ledger, let the four asset-register fields dictate everything else, and put the one component nobody sells at the centre.

The recommendation, ranked.

1. **Ingestion**, because it is the only capability that can beat a bookmarked spreadsheet in sixty seconds, and because manual population is the named mechanism by which every adjacent register examined failed [8], [10], [50]. Land everything in a visibly ungoverned state and report *N discovered, M governed*.
2. **The approval-decision object**, because three independently derived arguments converge on it — the sanctioned bespoke surface, the market gap conceded in a vendor's own capability table [27], [60], and the agent's output target — and because it is the write trigger for owner, production pointer, governance state and both semantic fields in a single action.
3. **Deterministic contract checks and cost attribution**, because together they make the approval card decidable in two minutes without asking a non-engineer to interpret a statistic that carries no rank information.
4. **Role granularity and the improvement agent**, deferred because introduced before the friction win they read as automation with no clear job.

All four hard constraints survive, and none is argued away. Human approval is exactly one wall at promote-to-production, held by an accountable owner with context, fed by a pre-computed card, escapable through a logged break-glass path, and grounded in segregation of duties rather than a legal claim. Role-based permissions are the four-role model of §6. Regression evaluation survives as three enforced parts rather than one dishonest verdict, and this report never claims the gate guarantees no quality degradation, because on this product's primary workload no gate can. Cost alerting is measured end-to-end per successful task rather than in prompt tokens, ambient while editing and binding at promotion.

What would falsify the recommendation is knowable and cheap to measure. If the first honest scan of the group's Drive and Sheets finds duplication far below the 30.4% internal-semantic rate observed in a far better-organized git population [4], the founding premise weakens and the product should be rescoped around versioning rather than discovery. If the purpose-field edit rate stays near zero in a pilot, the semantic tier is not trustworthy and should be described that way. If people export the grid to a spreadsheet in week one, the in-register view is not answering the question they actually have. Ship those three instruments alongside the product.

Three forces decide whether it ages into group infrastructure. The vendor gap will close on the single-provider half within a release cycle or two; the cross-provider half will not, and the build sequence should spend that window rather than bank on it.

Drift is structural and worsening, because hosted providers do not define a behavioural specification a deployer can test against [13] — so a register re-running the same deterministic contract against the live model on a schedule owns the only defensible answer to *is our production behaviour still what we approved?*, and that capability, not versioning and not the agent, is what the platform will be valued for in two years. And to the extent the group's own downstream products fall inside Vietnam's risk regime — a classification question for each product, never for this register, which no regime obliges to gate anything — the approval record is already the artifact those product teams would otherwise have to reconstruct after the fact, against clocks that have partly run [47], [48].

The final judgement is a wager with a stated basis. One disinterested critic does attack centralization on the merits, and the rest attack implementations rather than the premise that a group should know which prompts it owns, who owns them, what runs in production, and what they cost. But the nearest precedent for this design's own answer — derive everything, staff nobody — decayed anyway and still funds a steward. So this is a considered bet on a reconciliation queue staying small, not a solved problem, and the three instruments above are what would tell the group within one pilot which it turned out to be.

## Sources

1. Prompt governance is the new data governance | CIO
2. Your Company's Most Valuable Asset In The Age Of AI Is Walking Out The Door
3. Recognition and Cost of Intangible Assets (IAS 38) - IFRS Community
4. Understanding Prompt Management in GitHub Repositories: A Call for Best Practices
5. RFC: deprecating model registry stages · Issue #10336 · mlflow/mlflow · GitHub
6. CMDB vs Asset Management Differences and Why You Need Both
7. ServiceNow CMDB best practices: 2026 guide | Virima
8. Why do data catalogue projects fail?
9. 3 Data Catalog Pitfalls to Avoid for Successful Governance
10. Data Catalogs Are Dead; Long Live Data Discovery
11. Gen AI | OpenTelemetry
12. LLM Cost Attribution at Scale: Metadata Tagging, Team Budgets, and Chargeback
13. Test Before You Deploy: Governing Updates in the LLM Supply Chain
14. What We’ve Learned From A Year of Building with LLMs – Applied LLMs
15. Static Analysis for LLM Prompt Security: A Methodology for Pre-Deploy Vulnerability
16. Shadow AI Discovery: A Critical Part of Enterprise AI Governance
17. MinHash LSH in Milvus: The Secret Weapon for Fighting Duplicates in LLM Training\
18. RETSim: Resilient and Efficient Text Similarity
19. Writing effective tools for AI agents—using AI agents \ Anthropic
20. Version Control - Langfuse
21. Release Labels - PromptLayer
22. Create a prompt using Prompt management - Amazon Bedrock
23. View information about versions of a prompt in Prompt management - Amazon Bedrock
24. Prompt management  |  Gemini Enterprise Agent Platform  |  Google Cloud Documentation
25. API-first CMS vs Git-based
26. Git-based CMS vs. API-driven CMS: Which Headless CMS Should You Choose? -
27. Prompt CI/CD: version, gate, and roll out prompts like code - Langfuse
28. Caching - Langfuse
29. How Feature Flags Help With Progressive Delivery Progressive delivery with
30. Criterion-referenceability determines LLM-as-a-judge validity across physics
31. [2306.05685] Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena
32. Judging the Judges: A Systematic Evaluation of Bias Mitigation Strategies
33. [2410.21819] Self-Preference Bias in LLM-as-a-Judge
34. Prompt Engineering Fails Quietly —  Prompt Regression Is Why | Towards Data
35. [2604.16304] Results-Actionability Gap: Understanding How Practitioners Evaluate
36. Prompt Management for Non-Engineers: How Product Teams Can Own Their AI Prompts
37. Prompt Drift: What It Is and How to Detect It — Agenta Blog
38. PromptFoo Passes. Production Still Breaks. Here's the Gap. - DEV Community
39. Your AI Product Needs Evals – Hamel's Blog
40. DORA | Capabilities: Streamlining change approval
41. When DORA metrics meet governance in banking - Expert View — Team Topologies
42. The End of Code Review: Coding Agents Supersede Human Inspection
43. Rubber-Stamp Reviews | minware
44. Article 12: Record-Keeping | EU Artificial Intelligence Act
45. Article 14: Human Oversight | EU Artificial Intelligence Act
46. Companies Developing And Using AI In Vietnam: Key Legal Obligations Under
47. Update Decree 142/2026/ND-CP guiding the Artificial Intelligence Law in Vietnam
48. Vietnam: Artificial Intelligence Law - Foundation and Outlook | Insight |
49. VIETNAM – THE FIRST LAW ON ARTIFICIAL INTELLIGENCE – WHAT YOU MUST KNOW – Duane
50. Why Your Team Keeps Reverting to Spreadsheets -
51. Why Shorter Prompts Can Make Coding Agents Worse
52. Prompt Compression: Cut Token Costs Without Losing Quality | NeuralTrust
53. [2407.15504] Fundamental Limits of Prompt Compression: A Rate-Distortion Framework
54. How to Allocate AI Cost: A Step-by-Step FinOps Method - Amnic
55. Guaranteed Availability - Langfuse
56. What Is the Recommended Way to Handle Remote Config Fetch Failures? – Unity
57. Schema Evolution & Compatibility Types | Backward, Forward, Full, Transitive
58. CI/CD Integration for LLM Eval and Security | Promptfoo
59. Build vs buy: a guide for internal tools | Retool Blog
60. Update prompt label programatically · langfuse · Discussion #4284 · GitHub
61. Loop agent - Braintrust
62. [2601.22025] When Generic Prompt Improvements Hurt: Evaluation-Driven Iteration
63. When “Better” Prompts Hurt: Evaluation-Driven Iteration for LLM Applications
64. How we built open-source automated prompt optimization
65. How Hidden Spreadsheets & Shadow Workflows Drain Budgets - MTM Blog
66. Paying down tech debt - by Gergely Orosz and Lou Franco
67. You Still Don't Need A Feature Store | Xebia
68. What is Prompt Governance? The Critical Control for Enterprise AI
