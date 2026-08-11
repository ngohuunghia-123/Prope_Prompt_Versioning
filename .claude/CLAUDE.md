## Project

**Prope**

Prope is a prompt registry and release-control system for product teams whose prompts currently live in chat history, Google Sheets, Notion, and source files. It gives every prompt an owner, an immutable revision chain, a fixed eval suite, and a recorded human approval before anything reaches production — then serves the released revision through an OpenAI-compatible gateway so a consuming product calls a prompt by model name and never holds a copy of the text.

The three people it is for: the **Prompt Owner** (designer, marketer, PM, domain expert) who must be able to register and revise a prompt with zero lines of code; the **Reviewer/Approver** who sees the diff, the eval pass/fail, and the cost delta on one screen and records a decision; and the **Developer/AI Engineer** who points an OpenAI-compatible client at Prope's gateway and gets a restore-without-redeploy.

**Core Value:** **No prompt reaches production without a recorded human approval, and every call can be traced back to the exact revision that served it.** If everything else fails, this must hold — it is the one thing a spreadsheet cannot do, and 0/11 teams in the survey have it today.

### Constraints

### The four non-negotiables

An implementing agent may not trade these away:

1. **Human approval before production.** No auto-release of any kind. Break-glass is the declared, counted exception, and its 24-hour follow-up task is what keeps it exceptional.
2. **Only `Approved` revisions may be released or resolved** — enforced by a database constraint, not by application code.
3. **Edit, review/approve, and release are separate permissions.** Self-approval is recorded, never refused.
4. **Prompts are private by default.** Enforced as not-found, never forbidden, and by RLS underneath.

Plus: provider credentials are workspace-supplied, encrypted at rest, never returned by any read API, and redacted everywhere. **History rows are never deleted, at the database privilege level** — including when a person leaves: their `access.user` row is tombstoned and their `actor_id` survives as an opaque value (ADR-0054). `actor_id` is a value and not a foreign key, which is what makes that free.

### Stack and platform

- **Tech stack**: Python 3.13.x, FastAPI + uvicorn + pydantic v2 — ADR-0026
- **Database**: PostgreSQL 17, one instance, one database, schema per module; roles `prope_app` / `prope_migrate` / `prope_report` — ADR-0027, ADR-0037
- **Tenant isolation**: Postgres RLS, deny-by-default, `SET LOCAL app.workspace_id`; a missing filter returns **zero rows** — ADR-0035, ADR-0045
- **Message broker**: RabbitMQ 4.x; one queue `prope.call_record` plus its DLQ — ADR-0028
- **Identity**: Local — `user` table, argon2id, server-side session rows, HttpOnly same-origin cookie. No JWT — ADR-0029, ADR-0043
- **ORM / migrations**: SQLAlchemy 2.0 async over asyncpg; Alembic also carries RLS policies, constraints, extensions, triggers — A-128
- **Observability**: Prometheus + Grafana; `structlog` JSON to stdout; bounded metric label cardinality — ADR-0030
- **CI/CD**: GitHub Actions → GHCR → deploy over SSH; the host pulls, never builds — ADR-0031
- **Secrets**: One `.env` on the VM, `0600`, git-ignored. Holds the KEK. Never enters CI — ADR-0032
- **Runtime**: Docker + docker-compose on one group-controlled Linux VM; Caddy single ingress, **7 services**, **2 images** — ADR-0033
- **Frontend**: React 19 + TypeScript SPA built by Vite, Tailwind 4; Node in CI only, baked into a `caddy:2` image — ADR-0052
- **Interface language**: Vietnamese only in the MVP, behind an i18n layer: keyed catalogue, no literal display strings. Statuses stay literal; the API returns a machine `code` the client translates — ADR-0053
- **ML stack**: `n/a` — Prope trains and serves no models

**Four `SECURITY DEFINER` functions are sanctioned** and a test asserts the set is exactly these four: `access.lookup_session`, `access.lookup_api_key`, `evaluation.claim_next_run()`, `access.list_workspaces()`. Each returns identifiers only, never rows.

### Architectural constraints

- **Eight modules, eight bounded contexts.** No "frontend" or "backend" module, because neither owns a journey.
- **Forbidden edges**: call-ledger → anything (it is a sink, so stored bodies have no read path in the MVP); anything → credential (provider-access is the only module that decrypts); evaluation → gateway; access-control → anything but property-history; property-history → anything (`target_id` and `actor_id` are values, not foreign keys).
- **Three cycles, broken deliberately**: registry ↔ release-control (the released pointer is a registry field only release-control may write, through a command); evaluation ↔ release-control (evaluation never calls back; release-control pulls); access-control ↔ property-history (property-history has no standalone UI).
- **Permission is a local decision with the subject passed in.** access-control may not read any subject it authorises — callers pass `owner_id` and `access_level` from the row they already read.
- **Refusal shapes carry security weight.** Not-found when the actor cannot see the subject; forbidden naming the missing permission when they can. A key-scope refusal is byte-identical to an unknown model name. A rate-limited login is byte- and timing-identical to a wrong password. These are asserted, not intended.

### Process constraint

- **A-020 holds the line**: no real corporate prompts in the pilot until OQ-006 and OQ-013 are answered. This is a policy, not code.

## Technology Stack

## Baseline

| Concern | Choice | ADR |
|---------|--------|-----|
| Language | Python, pinned 3.13.x | ADR-0026 |
| Web framework | FastAPI + uvicorn + pydantic v2 | ADR-0026 |
| Database | PostgreSQL 17, one instance, one database, **schema per module**; roles `prope_app` / `prope_migrate` / `prope_report` | ADR-0027, ADR-0037 |
| Tenant isolation | Postgres row-level security, deny-by-default, `SET LOCAL app.workspace_id`; a missing filter returns **zero rows** | ADR-0035, ADR-0045 |
| Message broker | RabbitMQ 4.x; one queue, `prope.call_record`, plus its DLQ | ADR-0028 |
| Identity | Local — `user` table, argon2id, **server-side session rows**, HttpOnly same-origin cookie. No JWT | ADR-0029, ADR-0043 |
| Observability | Prometheus + Grafana; `structlog` JSON to stdout; bounded metric label cardinality | ADR-0030 |
| CI/CD | GitHub Actions → GHCR → deploy over SSH; the host pulls, never builds | ADR-0031 |
| Secrets | One `.env` on the VM, `0600`, git-ignored. Holds the KEK. Never enters CI | ADR-0032 |
| Runtime | Docker + docker-compose on one group-controlled Linux VM; **Caddy single ingress**, 7 services, 2 images | ADR-0033 |
| Frontend | React 19 + TypeScript SPA built by Vite, Tailwind 4; **Node in CI only**, baked into a `caddy:2` image | ADR-0052 |
| Interface language | **Vietnamese only in the MVP**, behind an i18n layer: keyed catalogue, no literal display strings. Statuses stay literal; the API returns a machine `code` the client translates | ADR-0053 |
| ORM / migrations | SQLAlchemy 2.0 async over asyncpg; Alembic. Alembic also carries RLS policies, constraints, extensions, triggers | A-128 |
| ML stack | `n/a` — Prope trains and serves no models | — |

## Deployment shape

## Sanctioned privilege escalations

- `access.lookup_session`
- `access.lookup_api_key`
- `evaluation.claim_next_run()`
- `access.list_workspaces()`

## Notable rejections

- **Next.js** — rejected at ADR-0034. ADR-0034 is superseded by ADR-0052 (React SPA + Vite + Caddy), but Next.js itself remains rejected and ADR-0034's reasons survive the reversal.
- **Kubernetes, Vault, Keycloak, Kafka, Loki, distributed tracing** — all rejected by the A-012 *debuggable by one person* clause.
- **JWT** — rejected in favour of server-side session rows (ADR-0029, ADR-0043), because revocation must take effect on the very next request.
- **A second broker queue and broker-based cache invalidation** — proposed twice, rejected twice on merit. The gateway's 30 s resolution cache **expires**; nothing invalidates it (ADR-0012).
- **`tsvector` full-text search** — substring semantics (`'thentic'` matches `authentication`) are a required property; ADR-0048 uses a trigram index over a trigger-maintained document column.

## Sources

- `docs/architecture/tech_stack.md` — per-module rows, `Inherited` vs `Deviated`, rejected alternatives
- `docs/adr/` — 54 ADRs; `docs/adr/adr_index.md` is the index
- `docs/brainstorm/assumptions/A-128.md` — the ORM and migration choice

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| hyperresearch-1-5-chapter-partition | > Step 1.5 of the hyperresearch V8 pipeline — CHAPTERED PROFILES ONLY (dissertation). Partitions the decomposed query into 4-10 topically cohesive chapters, writes the chapter plan, and registers chapters in the run manifest. Steps 2-10 then loop per chapter, each staying within the proven per-chapter source envelope; global reconciliation and synthesis integrate across chapters. Skipped entirely when the profile's `chapters` is (0, 0). Invoked via Skill tool from the entry skill. | `.claude/skills/hyperresearch-1-5-chapter-partition/SKILL.md` |
| hyperresearch-1-decompose | > Step 1 of the hyperresearch V8 pipeline. Decomposes the canonical research query into atomic items, classifies pipeline_tier and response_format, and produces the coverage matrix that downstream steps depend on. The required_section_headings field this step produces is the single highest-leverage input for instruction-following scores. Invoked via Skill tool from the entry skill (hyperresearch). | `.claude/skills/hyperresearch-1-decompose/SKILL.md` |
| hyperresearch-10-triple-draft | > Step 10 of the hyperresearch V8 pipeline. Orchestrator pre-curates 20-50 angle-specific source IDs per draft, then spawns 3 hyperresearch-draft- orchestrator subagents in parallel — each reads its curated list (no vault surveys, no source-fetching) and writes one angle-specific draft. This step ENDS when all 3 drafts are written and validated. Step 11 (synthesizer) handles the synthesis-write that produces the final report. For light tier: writes a single draft directly to final_report.md and skips ahead to step 15 (polish). Invoked via Skill tool. | `.claude/skills/hyperresearch-10-triple-draft/SKILL.md` |
| hyperresearch-11-synthesize | > Step 11 of the hyperresearch V8 pipeline. Reads the 3 angle-specific drafts from step 10, spot-checks factual conflicts, writes a synthesis plan + outline, then spawns ONE hyperresearch-synthesizer subagent (Read+Write tool-locked) that writes the final report in TWO passes — pass 1 rough integrated draft, pass 2 voice/redundancy/length cleanup. Skipped for light tier (which writes a single draft directly in step 10). Invoked via Skill tool from the entry skill (full tier). | `.claude/skills/hyperresearch-11-synthesize/SKILL.md` |
| hyperresearch-12-critics | > Step 12 of the hyperresearch V8 pipeline. Spawns 4 adversarial critics in parallel against the synthesized final report from step 11. Each critic produces an independent findings JSON that the patcher (step 14) consumes. Critics never modify the draft directly. Invoked via Skill tool from the entry skill (full tier only). | `.claude/skills/hyperresearch-12-critics/SKILL.md` |
| hyperresearch-13-gap-fetch | > Step 13 of the hyperresearch V8 pipeline. Conditional fetcher wave to fill vault gaps that critics identified. If a critic says "the draft ignored topic X" and the vault has zero sources on X, the patcher has nothing to cite. This step fetches the missing sources BEFORE patching so the patcher has ammunition. Capped at 5 gaps. Invoked via Skill tool from the entry skill (full tier). | `.claude/skills/hyperresearch-13-gap-fetch/SKILL.md` |
| hyperresearch-14-5-cite-check | > Step 14.5 of the hyperresearch V8 pipeline (full + dissertation tiers). Verifies that each citation in the patched report actually supports its sentence: mechanical triage auto-passes pairs confirmed by the claims table, the cite-checker agent judges the sampled remainder, and a second small patcher pass applies the findings. Runs AFTER step 14 (the patcher moved text and citations; audit what will actually ship) and BEFORE step 15 (polish sees the corrected text). Invoked via Skill tool. | `.claude/skills/hyperresearch-14-5-cite-check/SKILL.md` |
| hyperresearch-14-patcher | > Step 14 of the hyperresearch V8 pipeline. Spawns the hyperresearch-patcher subagent (TOOL-LOCKED to Read + Edit) to apply critic findings as surgical Edit hunks against the synthesized final report. Zero regeneration. Pre-stubs the patch log because Edit cannot create files. Handles orchestrator-escalated structural restructures inline. Invoked via Skill tool from the entry skill (full tier). | `.claude/skills/hyperresearch-14-patcher/SKILL.md` |
| hyperresearch-15-polish | > Step 15 (final) of the hyperresearch V8 pipeline. Spawns the hyperresearch-polish-auditor subagent (TOOL-LOCKED to Read + Edit) for the final hygiene + readability pass. Strips pipeline-reference leaks, YAML frontmatter, scaffold sections, filler phrases, run-on sentences. Escalates structural mismatches rather than fabricating content. Invoked via Skill tool from the entry skill. Followed by step 16 (readability audit) which is the actual final step before ship. | `.claude/skills/hyperresearch-15-polish/SKILL.md` |
| hyperresearch-16-readability-audit | > Step 16 (final) of the hyperresearch V8 pipeline. Spawns the hyperresearch-readability-recommender subagent (Read+Write tool-locked) to audit the polished final report and write JSON recommendations for paragraph merges, breaks, list/table conversions, bold injection, sentence splits, and HR removal. The orchestrator reads the recommendations and SELECTIVELY applies them via direct Edit calls (the recommender does NOT modify the report itself). Logs orchestrator decisions to a separate file. Runs for ALL tiers. Invoked via Skill tool from the entry skill. | `.claude/skills/hyperresearch-16-readability-audit/SKILL.md` |
| hyperresearch-2-width-sweep | > Step 2 of the hyperresearch V8 pipeline. Multi-perspective search planning (breadth / depth / adversarial lenses) followed by parallel fetcher waves. Achieves comprehensive topical coverage with 55–80 curated sources for full tier. Includes coverage check, evidence redundancy audit, and source count gating. Invoked via Skill tool from the entry skill after step 1 completes. | `.claude/skills/hyperresearch-2-width-sweep/SKILL.md` |
| hyperresearch-3-contradiction-graph | > Step 3 of the hyperresearch V8 pipeline. Builds an explicit graph of opposing claims across the corpus. Ranked fight clusters feed step 4's loci analysis so that loci emerge from where evidence actually forks, not from agent intuition. Also identifies consensus claims (3+ independent agreements) for confident assertion in the draft. Invoked via Skill tool from the entry skill after step 2 completes. | `.claude/skills/hyperresearch-3-contradiction-graph/SKILL.md` |
| hyperresearch-4-loci-analysis | > Step 4 of the hyperresearch V8 pipeline. Spawns 2 parallel loci-analyst subagents that read the width corpus and identify 1-6 specific questions where depth investigation will pay off. Deduplicates and scores each locus on importance/uncertainty/disagreement/decision_impact, then allocates source budgets dynamically. Invoked via Skill tool from the entry skill (full tier only). | `.claude/skills/hyperresearch-4-loci-analysis/SKILL.md` |
| hyperresearch-5-depth-investigation | > Step 5 of the hyperresearch V8 pipeline. Spawns K depth-investigator subagents in parallel (one per scored locus), each producing one interim note with a Committed Position section. Investigators read full source bodies for their locus and may fetch additional sources within their source_budget. Invoked via Skill tool from the entry skill (full tier only). | `.claude/skills/hyperresearch-5-depth-investigation/SKILL.md` |
| hyperresearch-6-cross-locus-reconcile | > Step 6 of the hyperresearch V8 pipeline. Reconciles the committed positions from all depth investigators into research/runs/<vault_tag>/comparisons.md — 3-5 named cross-locus tensions with engagement guidance for the draft. This is the structural step that gives the single draft argumentative density. Invoked via Skill tool from the entry skill (full tier only). | `.claude/skills/hyperresearch-6-cross-locus-reconcile/SKILL.md` |
| hyperresearch-7-source-tensions | > Step 7 of the hyperresearch V8 pipeline. Extracts explicit expert disagreements from the corpus into research/runs/<vault_tag>/temp/source-tensions.json, including orphan tensions that didn't surface as loci. Reads full source bodies of top 8-12 sources (not summaries) to find tensions that hide in nuance. The Source Tensions section in step 10's draft is the single highest-leverage move for insight scores. Invoked via Skill tool from the entry skill (full tier only). | `.claude/skills/hyperresearch-7-source-tensions/SKILL.md` |
| hyperresearch-8-corpus-critic | > Step 8 of the hyperresearch V8 pipeline. Spawns one corpus-critic subagent to identify "what source, if found, would overturn the current direction?" gaps, then runs a targeted fetch wave to fill them. Highest-leverage intervention point: corrections applied before drafting cost nothing; corrections applied after drafting require patches. Invoked via Skill tool from the entry skill (full tier only). | `.claude/skills/hyperresearch-8-corpus-critic/SKILL.md` |
| hyperresearch-9-evidence-digest | > Step 9 of the hyperresearch V8 pipeline. Assembles the top load-bearing claims and verbatim quotes from the claims JSONs into research/runs/<vault_tag>/temp/evidence-digest.md — a single high-fidelity evidence index the draft sub-orchestrators read as primary evidence (higher fidelity than fetcher summaries). Invoked via Skill tool from the entry skill (full tier). | `.claude/skills/hyperresearch-9-evidence-digest/SKILL.md` |
