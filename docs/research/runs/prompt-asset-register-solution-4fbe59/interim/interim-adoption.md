---
type: interim
locus: displacing-the-spreadsheet-day-one
tags: [prompt-asset-register-solution-4fbe59, locus-adoption]
---

# Interim report: displacing-the-spreadsheet-day-one

**Locus question:** What specific day-one mechanisms actually cause a non-technical team to abandon a good-enough spreadsheet or Notion page, as opposed to governance features that demonstrably fail to?
**Flavor:** convergent

## Provenance note — read before weighting this report

Of the five sources assigned to this locus, **zero are about prompt asset registers**, and only one (`prompt-management-for-non-engineers-how-product-teams-can-own-their-ai-prompts-a`, Agenta's blog) is about this product category at all — and it is vendor content promoting Agenta's own playground, so its prescriptive feature list is treated as positioning, not evidence. The other four are disinterested operational diagnostics from *adjacent* domains: marketing-ops consultancy (`why-your-team-keeps-reverting-to-spreadsheets`), data-catalog/governance consultancy (`why-do-data-catalogue-projects-fail`), creative-production-ops (`how-hidden-spreadsheets-shadow-workflows-drain-budgets-mtm-blog`), and a data-observability vendor's category argument (`data-catalogs-are-dead-long-live-data-discovery`, Monte Carlo, arguing for "discovery" over "catalog" — note this vendor sells neither catalogs nor prompt registers, so its self-interest doesn't bias *this* question directly, though it is still a sales-adjacent piece for a different product). None is peer-reviewed; none reports a controlled study with an N. The inferential move this report makes is: **tool-adoption-vs-shadow-workaround is a general phenomenon of "official system" vs. "workaround" dynamics, and the mechanism that drives it (friction differential, not feature richness) transfers across artifact types** (CRM records, data assets, campaign trackers, prompts). That transfer is judgment, not measurement — flagged throughout below with confidence downgrades.

## What the sources say

### 1. `why-your-team-keeps-reverting-to-spreadsheets` — the operational diagnostic

This is the single most load-bearing source for naming *specific* day-one failure mechanisms, verbatim:

> "Teams revert to spreadsheets when the official system feels slower than the workaround, harder to trust, or disconnected from how the work actually happens."

Six named root causes, of which four map directly onto register design:

1. **"The official platform adds more steps than it removes"** — friction differential, not friction absolute.
2. **Tool-fit mismatch** — "pipeline stages that do not reflect real sales movement... task structures that make handoffs harder instead of clearer."
3. **Unclear ownership**: *"If no one governs fields, stages, handoffs, or data quality, the system degrades fast... The spreadsheet then feels safer because the team controls the logic directly."*
4. **In-system reporting that fails to answer the real question, with exports as the diagnostic tell**: *"Teams often export data into spreadsheets because the official reporting does not answer basic operational questions... Once reporting moves into spreadsheets, daily execution usually follows."* Exports are explicitly named as a warning sign, and treating them as normal is listed among the "common mistakes that make spreadsheet dependency worse": *"Treating reporting exports as normal instead of as a warning sign."*

Critically, the source explicitly separates **tool problem / process problem / adoption problem**, and warns that "buying another platform rarely fixes spreadsheet reversion if process design is weak" — i.e., shipping more governance features onto a system that already has a friction differential does not fix adoption; it can make it worse ("Automation exists, but has no clear job... Bad automation creates noise instead of leverage").

### 2. `why-do-data-catalogue-projects-fail` — the entry-ticket mechanism (the closest structural analog to this product's persona split)

This is an independent domain (data governance) converging on the same underlying mechanism from the opposite direction — not "why do people leave the good tool" but "why does the good tool never capture the non-technical user in the first place":

> "In many organisations, the catalogue is gradually becoming a tool reserved for data teams. The departments, for their part, continue to operate outside the system. Because the 'entry ticket' remains too high."

> "A business manager isn't looking for a technical table or a database structure. They're looking for a simple answer... However, current systems still require understanding data vocabulary, navigating complex interfaces, or knowing the technical organisation of data."

This produces **expert dependency** — a small group becomes the sole interface, a bottleneck measured in "several hours a week simply answering comprehension questions." This maps with unsettling precision onto the query's own persona split: primary user (non-dev marketer/designer), user #2 (approver-manager), user #3 (developer who consumes via API/SDK). If the register's entry ticket is technical, it inverts the product's stated bet and becomes what this source predicts — a dev-only tool, while Minh and the design/marketing team keep pasting prompts into a chat thread, which is the exact status quo the query already describes.

The source's own prescription is notable: *"Think usage before documentation"* — start from priority use cases, not exhaustive cataloging — and use conversational/AI interfaces to collapse the entry ticket rather than lowering documentation quality bars.

### 3. `how-hidden-spreadsheets-shadow-workflows-drain-budgets-mtm-blog` — the migration rule and the shadow-AI extension

This is the source with the most direct actionable sequencing logic. Central rule:

> "The most common migration failure is asking a team to abandon a working tool before the replacement can do what the tool does."

Four-step migration roadmap, verbatim structure: (1) **replicate functionality before retiring the spreadsheet** — "Identify the three to five things the shadow spreadsheet does that the official system currently cannot... and build that capability in the official environment first"; (2) **migrate live data, not just structure** — "Teams will abandon a new system the moment they need information that only exists in the old one"; (3) **assign a transition owner** per migrated process — the person who ran the shadow spreadsheet validates coverage and "flag[s] any gap that appears during the first four weeks"; (4) **enforce single source of truth from the first live use** — a categorical rule: "if it is not in the system, it does not exist for decision-making purposes."

Four diagnostic signals of an active shadow workflow, useful as a pre-registration checklist for what the ingestion scan needs to surface: single-owner knowledge, "just to be safe" duplication, status-that-requires-a-meeting, and approval-that-happened-in-chat.

Most important for this specific product: the source names AI-generated shadow workflows as a *new, faster-growing* instance of the same pattern:

> "AI tools used individually by team members without integration into the shared production environment are a new category of shadow workflow... When every team member uses their own AI, the shadow data problem scales significantly faster than it did in the spreadsheet era."

This is, almost word for word, the query's own referent: "Prompt của các sản phẩm AI nằm rải rác trong code, Google Sheet, Notion" plus prompts pasted into chat threads. The MTM source frames this not as an isolated observation but as an accelerating instance of a known pattern, which raises the stakes on solving it fast rather than incrementally.

### 4. `data-catalogs-are-dead-long-live-data-discovery` — destination vs. flow

Monte Carlo's argument (older piece, ~2020-21, which the run directives explicitly sanction for governance precedent) is that catalogs fail for three structural reasons: **lack of automation** ("traditional data catalogs... rely on data teams to do the heavy lifting of manual data entry... requires significant manual toil that could otherwise be automated"), **inability to scale** with unstructured/dynamic data, and **undistributed format** — the catalog documents an "ideal" state while the real data constantly changes shape. Their proposed alternative, data discovery, is defined by:

> "Data discovery surfaces a real-time understanding of the data's current state as opposed to its ideal or 'cataloged' state."

The load-bearing point for this locus is #1: **manual data entry is the mechanism that kills catalog adoption**, independent of governance quality. This converges cleanly with source #2's "entry ticket" framing — both identify the labor of populating a central system as the actual barrier, not the concept of centralization itself.

### 5. `prompt-management-for-non-engineers-how-product-teams-can-own-their-ai-prompts-a` — vendor content, but the only source naming this exact persona and its current workarounds

Treated as vendor positioning (Agenta promoting its own playground), but its diagnostic section is useful because it names the query's status quo almost exactly, independently of the query itself:

> "The spreadsheet method. A subject matter expert tests prompt variations in a Google Sheet or a Jupyter Notebook... eventually share[s] a 'winning' prompt with the engineering team via Slack or email... Neither side has full context about what the other tested or why."
> "The ticket-and-wait method... The pair-programming method..."
> "There is no shared history of what was tried. There is no way to compare prompt versions systematically. There is no safe path from experiment to production."

Its role-split proposal — "domain experts own prompt content and test cases. Engineers own the integration and deployment pipeline. Product managers own the evaluation criteria and prioritization" — is a direct precedent for the query's three-persona structure (Minh/Toàn/Quân), though it should be read as one vendor's opinionated org design, not evidence that this split is what actually drives adoption.

## Evidence synthesis

The four non-prompt-specific sources converge, independently, on a single mechanism: **adoption is decided by the friction differential between the official system and the workaround at the moment of use, not by the richness of governance features layered onto the official system.** Consultevo names it directly ("the official system adds more steps than it removes"); MTM operationalizes it into a migration sequencing rule (replicate before retiring, migrate live data not just structure); the data-catalog source locates the same mechanism at the point of first contact ("entry ticket too high" → tool becomes reserved for the technical team); Monte Carlo locates it in the labor of *populating* the system (manual data entry as the catalog killer). None of these sources talks about approval workflows, audit trails, or RBAC as *causes* of adoption — where governance appears in these sources, it appears as something that must be confined to a single deliberate gate (MTM's "if it is not in the system it does not exist for decision-making purposes," applied only at the point of consequence) rather than distributed across every interaction, or it appears as a failure mode when added without a clear job ("Automation exists, but has no clear job").

Where the sources genuinely diverge is on *where the system should live*. Consultevo and MTM assume a destination system (CRM, project tool) that must out-compete the spreadsheet on its own turf. Monte Carlo argues the destination-catalog model is structurally wrong for data because data doesn't sit still — but a prompt asset register is a different kind of artifact than the data it indexes: the register *is* the asset (the prompt text, its version, its owner), not an index pointing elsewhere. That distinction matters for how far the "discovery over destination" lesson can be imported — see below.

The Agenta source, despite its vendor incentive, corroborates the *shape* of the incumbent workflow (spreadsheet-method, ticket-and-wait, pair-programming) closely enough that it should be read as independently confirming the query's own problem statement, even though its solution (playground features) is marketing.

## Two specific design questions

### The register-as-destination problem

A prompt asset register cannot fully avoid being a destination — unlike a data catalog, which indexes assets that live elsewhere, the register's core value proposition (a de-duplicated, versioned corporate ledger of prompt text, ownership, lifecycle, cost) is itself the artifact. It cannot be "discovered in the flow" the way a data-discovery tool surfaces facts about tables that live in a warehouse, because there is no separate warehouse — the register *is* the warehouse. So the "catalogs are dead, long live discovery" lesson does not mean "don't build a destination." It means something narrower and still important: **don't make the destination the only door, and don't make entering it require unpaid labor.**

Concretely, this splits into two different surfaces with two different requirements:

- **Retrieval and governance surface (destination, required):** a navigable, permalinked, single-source-of-truth register is unavoidable and is in fact the whole point — Sheets already does this well (a link opens the thing). The register must at minimum match this: SSO-scoped shareable links that deep-link to a specific prompt+version, no folder-drilling, one click from a Slack/Zalo/email link to the content.
- **Capture surface (must not be destination-only):** the moment a new prompt is *written* today happens inside a chat thread, a Sheet cell, or a Notion block — not inside a purpose-built tool. This is exactly the "manual data entry" failure Monte Carlo names as the catalog killer, and exactly the entry-ticket problem the data-catalog source names. The product's own three-USP-pillar-1 design (scan repos/Sheets/Notion/Drive/chat exports at onboarding) is the correct resolution of this for the **historical backlog** — it converts "who does the tedious cataloging labor" into a zero-effort scan, directly answering Monte Carlo's #1 catalog failure mode. But it does not solve the **flow problem**: new prompts created after the initial scan will keep being born in chat threads unless there is a lightweight embedded capture point (browser extension "save to register," or a forward-to-bot pattern) at the point of creation. Per the MTM source, unaddressed AI-tool shadow workflows scale *faster* than the spreadsheet-era version once every user has their own chat history to paste from — so this is not a nice-to-have, it is the mechanism by which the register would otherwise re-accumulate the exact problem it launched to solve, within weeks of a successful onboarding demo.

**Position on surface area:** destination for the ledger (non-negotiable — it is the product), embedded/lightweight for capture (non-negotiable — it is what prevents day-30 re-fragmentation). A pure destination-only build will win the demo (impressive scan + grid) and lose the six-month adoption war exactly the way data catalogs lose to discovery: by requiring a special trip to log something someone already wrote somewhere else.

### The sequencing trap — Sheets' affordances, honestly scored

| Sheets affordance | Will the register match it? | What compensates |
|---|---|---|
| **Instant edit** (click cell, type, done, no save dialog) | **No, not fully** — structured fields (owner, stage, cost, eval linkage) are inherently more form-like than a blank cell. | Make the prompt body itself a single big freeform field with silent autosave and no submit button; push every other field to optional/agent-inferred metadata rather than required-at-creation. Match Sheets on the field that matters (the prompt text), not on every field. |
| **No permission wall** (anyone with edit rights just edits) | **No, and should not** — mandatory HITL-to-promote is a stated hard constraint, not incidental friction. | Confine the wall to exactly one action: promote-to-production. Drafting, versioning, editing, running an eval must remain as walled-off as editing a cell — zero approval required. This is consistent with the sequencing rule (replicate low-friction authoring first; add the one deliberate gate only where Sheets never had an equivalent function anyway, since Sheets was never gating production releases). |
| **Free-text anything** (no schema, no required fields) | **Partially** — the register needs at minimum a name/slug to be addressable via API/SDK (a hard requirement per the query's own "consumed via API/SDK" pillar). | Require only two fields at creation (name + body); auto-suggest everything else (owner, tags, source) from ingestion context (which chat/sheet it came from, who pasted it) so it *feels* schema-free even though structure exists underneath. |
| **Shareable link** (URL opens straight to content) | **Yes, matchable** — no structural reason this can't be built. | SSO-scoped permalink per prompt+version, deep-linkable, no login flow visible to an already-authenticated org member. This should be a required day-one feature, not an aspiration. |
| **"Works offline in the head"** (zero learning curve — years of spreadsheet muscle memory) | **No, cannot fully match on day one** — any new tool has a nonzero learning curve by definition. | Mimic the mental model rather than inventing a new one: the default "browse all prompts" view should render as a sortable/filterable grid (rows = prompts, columns = owner/stage/cost/version), not a chat-first or graph-first UI, so spreadsheet scanning habits transfer directly instead of requiring new navigation logic to be learned. |

Two of five affordances are structurally unmatchable and one is deliberately *not* matched (the promotion gate is the product's reason for existing) — the sequencing rule from the MTM source ("replicate functionality before retiring the spreadsheet") therefore cannot mean full parity; it must mean **parity on the affordances that cause the abandonment decision (edit speed, no-wall authoring, link-sharing) and an explicit, minimized footprint for the one affordance being deliberately traded away (unwalled everything) in exchange for the thing Sheets structurally cannot do (versioned, auditable, cost-gated promotion).**

## Committed position

Day-one displacement will be driven almost entirely by removing labor and friction at two specific points, not by governance richness: **(1) zero-labor ingestion** — the register must auto-populate from the org's actual Sheets/Notion/Drive/chat exports so a marketer's first session shows *their own* existing prompts already deduplicated and browsable, never a blank state demanding manual entry (this directly answers both the "entry ticket too high" failure mode from data catalogs and the "manual data entry" failure mode from data discovery); and **(2) a single confined approval gate** — all authoring, editing, and versioning must be as frictionless as a spreadsheet cell, with the mandatory HITL wall appearing exactly once, at promote-to-production, and nowhere else in the flow (this directly answers the "official system adds more steps than it removes" failure mode). Governance features — RBAC granularity, audit depth, eval rigor — are what sustain retention from week 4 onward, not what wins session one; introduced before the ingestion win is demonstrated, they read as the "automation with no clear job" pattern that these sources say actively drives reversion. The demo therefore must prove, live, with a non-technical persona at the controls: a real (or seeded) Sheet/Notion/chat export ingested and rendered as a deduplicated, browsable grid within the session (performing USP pillar 1 as the inverse of the catalog failure mode); an inline edit with no save button producing a new version automatically (proving edit-speed parity); and exactly one visible moment of deliberate friction — the promote click producing a single evidence card — with nothing else in the path gated. If the tool cannot show unprompted, editable, recognizably-theirs content within roughly the first 60 seconds of a first-time user landing on it, the win condition ("used more than Google Sheet") is very unlikely to be reached, because a bookmarked Sheet already clears that bar trivially.

- **Position:** Day-one adoption is won by zero-labor ingestion (converting the historical chaos into a populated, browsable register with no user data entry) plus a single confined approval gate (frictionless authoring, one deliberate wall only at promotion) — not by governance feature completeness, which should be deferred past the first session.
- **Confidence:** medium. Four independent-domain diagnostic sources converge on the friction-differential mechanism, which is meaningful corroboration across genuinely unrelated fields (marketing ops, data governance, creative-production ops, data observability), but none is a controlled or N-reported study, none addresses prompt registers specifically, and the transfer from "CRM/catalog/campaign-tracker adoption" to "prompt register adoption" is an analogical judgment, not a measured finding.
- **Boundary conditions:** This holds specifically for the *first session and first ~4 weeks* of organic (non-mandated) adoption by the primary non-dev persona choosing between a familiar Sheet and an unfamiliar register. It weakens once a top-down mandate exists (consultevo's own framework treats "leaders bypass the system" / "system use is optional" as a distinct *adoption*-problem axis, separate from tool-fit — a mandate changes which axis dominates) and it may not apply to user #2 (approver-manager, who has organizational leverage to tolerate friction) or user #3 (developer, who has technical comfort with more structure).
- **What would change this position:** If a pilot showed non-technical users tolerating manual re-entry of their top prompts without reverting to Sheets once a mandate or incentive existed, that would falsify the primacy given to zero-labor ingestion. Conversely, if users kept exporting the register's own browse view back into a Sheet within week 1 — replaying consultevo's "exports as diagnostic warning sign" pattern — that would show in-register reporting still fails to answer the real question ("what's running in prod and what does it cost") and would mean proof-point (1) alone is insufficient; the demo would need to add a fourth beat showing that exact question answered without an export.
- **Evidence weight:** 4 independent-domain consultant/vendor diagnostic pieces converge directionally (no peer review, no reported N, pattern-recognition genre); 1 vendor blog (Agenta) corroborates the specific persona and its current workarounds but its prescriptive feature list is marketing for a different, adjacent product and is discounted accordingly. Zero sources are prompt-registry-specific or Vietnam/conglomerate-specific — this is a real gap, not filled by anything in this locus's budget.

## Open questions

- No source measures adoption of a prompt-specific (or any AI-artifact) register by non-technical business users empirically — the closest analog (data catalogs) is a different artifact type (an index of external data vs. the register *being* the asset).
- No source quantifies the entry-ticket threshold (seconds-to-first-edit, click count, fields-required) at which business-user adoption actually tips one way or the other.
- Whether embedding a capture surface in chat tools (browser extension, Slack/Zalo-forward-to-bot) measurably reduces new shadow-prompt creation, versus simply adding one more surface to fragment across, is asserted here by analogy from the MTM shadow-AI point but is untested in any source read.
- Nothing in this locus's budget addresses Vietnamese-conglomerate-specific context — organizational hierarchy around approvals, whether Zalo/email dominates over Slack, how much of the "chat thread with prompts pasted in" incumbent runs through personal vs. corporate channels. Worth a targeted follow-up locus if budget allows.

## Sources

1. [[why-your-team-keeps-reverting-to-spreadsheets]] — "Why Your Team Keeps Reverting to Spreadsheets" (ConsultEvo)
2. [[why-do-data-catalogue-projects-fail]] — "Why do data catalogue projects fail?" (JEMS Group)
3. [[how-hidden-spreadsheets-shadow-workflows-drain-budgets-mtm-blog]] — "How Hidden Spreadsheets & Shadow Workflows Drain Budgets" (MTM Blog)
4. [[data-catalogs-are-dead-long-live-data-discovery]] — "Data Catalogs Are Dead; Long Live Data Discovery" (Monte Carlo)
5. [[prompt-management-for-non-engineers-how-product-teams-can-own-their-ai-prompts-a]] — "Prompt Management for Non-Engineers" (Agenta Blog, vendor content)
