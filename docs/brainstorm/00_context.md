# Prope — MVP Context

**Date**: 2026-08-08

## Problem

Product teams across the group depend on prompts that live in chat history, Google Sheets,
Notion, and source files. In the group's own enterprise survey (n=11, directional — see
`prope_source_of_truth.md` §21): 10/11 keep prompts in chat history, each person uses about 3
storage locations, and 0/11 use any dedicated prompt tool.

The consequences are measured, not assumed. 11/11 cannot reliably find or identify the prompt
they need; 11/11 do not know which revision is the latest; 11/11 see teammates using different
prompts for the same task; 9/11 do not know who owns a prompt. Downstream: 8/11 get inconsistent
output, 7/11 redo work, 5/11 cannot identify which prompt caused a failure, 4/11 discover errors
only after release. 0/11 have any formal approval step before a prompt reaches production.

What they do today is rewrite the prompt, search chat, or copy-paste an unverified version into
the app. The root problem is **lost ownership, lost provenance, and lost trust** — not the
absence of somewhere to save text. Reducing it to "users need a place to save prompts" produces
the wrong product.

## Users

- **Prompt Owner** (designer, marketer, PM, domain expert) — today writes and edits prompts in
  chat or a Sheet, with no history and no record of who is responsible. Changes: registers the
  prompt once, edits produce immutable revisions automatically, ownership and access are explicit,
  and nothing is shared or released without their action. Must work with zero lines of code.
- **Reviewer / Approver** (manager, product owner) — today either does not review at all, or
  reviews by reading a pasted diff in chat. Changes: receives a submitted revision, sees what
  changed, the pass/fail result of a fixed eval suite, and the cost delta on one screen, and
  records an approve-or-request-changes decision that is stored.
- **Developer / AI Engineer** — today copy-pastes prompts and cannot say which text is running in
  production. Changes: points an OpenAI-compatible client at Prope's gateway and calls the prompt
  by model name; the released revision is resolved server-side, and a restore changes what
  production runs without a code change or a redeploy.

## Success

| Metric | Target | How it is measured |
|--------|--------|--------------------|
| Time to find the trusted revision of a named prompt | ≤ 30 s in ≥ 80% of attempts | Timed usability script, 5 participants × 5 prompts, stopwatch recorded per attempt |
| Non-developer creates and submits a revision | 3 of 3 runs complete with 0 lines of code written | Observed demo run against an observer checklist |
| Fixed eval suite completes and renders pass/fail | 10–20 cases in ≤ 120 s (p95) | Wall-clock of the eval-run endpoint, 20 recorded runs |
| Reported token counts match the provider | within ±2% of provider-reported usage | Stored usage rows vs. the provider response `usage` field, 20 runs |
| Releases carrying an approval record | 100% of non-break-glass releases | SQL: releases LEFT JOIN approvals, count rows with NULL approval and `break_glass = false` |
| Unapproved revision reaching a release | 0 occurrences | SQL over releases where `revision.status != 'Approved'` |
| Gateway calls recording a version ID | 100% | SQL over call records with NULL `version_id`; the metadata write uses a durable buffer that is never dropped (A-037) |
| Latency the gateway adds on top of the upstream call | p95 < 50 ms | Instrumented span from request arrival to upstream dispatch, plus upstream completion to response flush; logging excluded by construction |
| A fallback answer is detectable by the caller | 100% of fallback-served calls | Presence of the `x-prope-fallback` header and the `prope.fallback` field, checked over all call records with `outcome = fallback` |
| Restore to a previously Approved revision | ≤ 5 min, decision to gateway serving the restored revision | Audit events: **`revision_restored`** → first call record carrying the restored version ID. *Corrected 2026-08-09 (step 6, pass 1): this row named `restore_requested`, which **no module writes** — release-control writes `revision_restored` when the release commits, which is the moment this row means by "decision" anyway. Flagged at three module locks and in ADR-0024 and A-126 before the source was fixed. The measurement spans release-control's event and call-ledger's record, so it is hand-run SQL at pilot review rather than a product surface (A-126).* |
| Median review turnaround | < 1 business day | Audit events: `submitted_at` → `decided_at`, median over the pilot |

## Scope

**In scope**
- Prompt registry: register a prompt with an owner, a globally unique model name, access level,
  status, tags; search and filter by title, body, owner, status, access.
- Immutable revision history: every edit produces a revision with author, timestamp, and change
  summary; older revisions stay readable. The revision carries the prompt body, its provider,
  model, and generation parameters, and its fallback answer.
- Version diff: side-by-side comparison of any two revisions of one prompt.
- Fixed eval suites: a prompt carries one or more **named** suites (`safety`, `accuracy`, `format`, …),
  each 10–20 hand-authored cases with deterministic assertions, each versioned and run independently,
  each run against the candidate revision and the current released revision (A-062, ADR-0006).
- Prope manages every kind of prompt, not only chatbot prompts. It attaches the system prompt and routes
  to the destination agent; the transport is always OpenAI-compatible chat completions, but the content
  returned may be prose, structured data, or a reference to a created asset. Assertions are keyed to the
  suite's declared output modality (A-061).
- Cost delta: tokens and money for one full eval-suite run, candidate vs. released revision,
  shown before the approve decision. Warn only in MVP.
- HITL release: submit for review → one reviewer approves the revision → a second, recorded
  decision releases it; break-glass release with a mandatory one-line reason; restore to a
  previously Approved revision.
- **OpenAI-compatible gateway**: `POST /v1/chat/completions` where the `model` field names a prompt
  property (`ecom/agent-pipeline`, optionally `@revision`). Prope resolves the released revision,
  applies its system prompt and model binding, forwards to the configured provider, and returns the
  provider's response.
- **Fallback answer**: each revision may carry a stored answer served when the upstream provider
  fails, marked so the caller can detect it.
- **Provider configuration dashboard**: the workspace supplies its own provider credentials and
  chooses the provider and model per prompt.
- **Call records**: per call, the prompt, version ID, consumer, timestamp, tokens, cost, outcome,
  and the request and response bodies. Written off the response path.

**Out of scope**
- Import and ingestion from repositories, Sheets, Notion, Drive, or chat exports — deferred to a
  later integration feature (OQ-001, resolved 2026-08-08).
- Similar-prompt clustering and duplicate grouping.
- Trace and span models, a trace explorer UI, analytics dashboards, sampling policy. Prope stores
  raw call records; Langfuse export is a later integration (A-039).
- Environment aliases beyond a single released pointer; multi-region or multi-tenant routing.
- OpenAI endpoints other than chat completions and `/v1/models`.
- Multi-level approval, configurable policy engine, scheduled drift monitoring.
- Individual mode (save → find → reuse, without governance) — pending OQ-007.
- LLM-judge quality scoring; semantic/vector search.

**Anti-goals**
- Building the observability product. Prope keeps call records for traceability and for the later
  review screen; it does not build traces, spans, or dashboards, and it integrates with Langfuse
  rather than competing with it.
- A prompt marketplace or public template library.
- A chat or playground surface for talking to a model.
- Auto-release: no prompt reaches production without a recorded human decision.
- An agent that autonomously rewrites prompts, or fallback answers, and puts them in front of users
  without a human accepting the revision.
- Any claim that Prope establishes legal intellectual-property ownership.
- Any claim that the eval suite guarantees no quality degradation.

> **Two reversals on record.**
> 1. `positioning.md` §6 and §12 T3 list "never on the hot path" as an anti-goal, and §11 warns the
>    developer persona holds a veto triggered by exactly this. The gateway decision of 2026-08-08
>    overrides it, and the follow-up decision accepts Prope as a **hard dependency**: if Prope is
>    down, every consuming product's AI feature is down. The fallback answer does not cover this
>    case, because the fallback is stored in Prope. This is an accepted risk, not a mitigated one.
> 2. `positioning.md` §4 "USP hỗ trợ #2" argues that content-free telemetry lets Prope fill in the
>    cost field for a subsidiary's customer-facing product *without reading that subsidiary's user
>    data*. Storing request and response bodies ends that claim. It must be removed from the pitch,
>    not softened.

## Constraints

| Constraint | Category | Source | Non-negotiable | Notes |
|------------|----------|--------|----------------|-------|
| Human approval is mandatory before a revision is promoted to production | compliance | user — original brief, `research/runs/prompt-asset-register-solution-4fbe59/query.md`; BR-04 | yes | Sold as internal control, never as a legal requirement (`positioning.md` §7.1) |
| Approval attaches to **both** the revision and the release: a revision is approved once, and each release is a second recorded decision | compliance | user — 2026-08-08 (OQ-002) | yes | Restore is the open exception — see OQ-002, A-028 |
| Only revisions in status `Approved` may be released or resolved by the gateway | compliance | BR-03, `prope_source_of_truth.md` §10.5 | yes | The gateway errors or serves the fallback; it never falls back to another revision |
| Edit, review/approve, and release must be separate permissions | security | user — original brief (RBAC); NFR-01 | yes | Full role matrix still open — see OQ-006 |
| Prompts are private by default; no auto-publish, auto-share, or auto-release | security | BR-01, `prope_source_of_truth.md` §6, §11 | yes | Top adoption barrier in the survey is reluctance to share personal prompts |
| Provider credentials are supplied by the workspace, encrypted at rest, never returned by a read API, and redacted in logs and audit records | security | user — 2026-08-08 (OQ-004); NFR-03 | yes | Prope holds third-party secrets; this widens OQ-006 |
| Prope is an accepted hard dependency of consuming products' request paths | deploy_target | user — 2026-08-08 (OQ-012) | yes | No consumer-side fallback is assumed; a Prope outage is a full outage |
| Persisting call records must not sit on the response path | performance_budget | user — 2026-08-08 (OQ-012, "redirect trước, lưu logs sau") | yes | Metadata durable, bodies best-effort — see A-037 |
| Request and response bodies are stored; retention, read access, and PII handling must be settled before any real traffic | security | user — 2026-08-08 (OQ-012); NFR-03 | yes | The storing is decided; the policy is OQ-013 and A-040 is a placeholder |
| Cost must be measured from actual runs; never inferred from prompt token length | performance_budget | BR-07; `BRIEF.md` §5③ (−17% input tokens, +67% session cost) | yes | In MVP the review-time unit is one full eval-suite run — see A-006 |
| No surface may claim the eval "guarantees no quality degradation" | compliance | `BRIEF.md` §8; NFR-04 | yes | Pass/fail is limited to deterministic assertions — see A-005 |
| User-facing vocabulary: revision, restore, release, grant access; statuses stay literal (Draft, In review, Approved, In use, Retired) | language_preference | `prope_source_of_truth.md` §8, §18 | yes | Overrides "version / rollback / promote" from the feature request — see A-001 |
| "Property" is a product metaphor only; no legal ownership claim in any copy | compliance | BR-09, `prope_source_of_truth.md` §1 | yes | No real-estate metaphors |
| The gateway must be wire-compatible with the OpenAI chat-completions request and response shape, including streaming and error bodies | third_party_api | user — 2026-08-08 (OQ-003) | yes | A near-miss breaks every client SDK |
| Stack: Python 3.13, FastAPI, PostgreSQL 17, RabbitMQ 4, **React + TypeScript SPA (Vite, Tailwind 4)**, Caddy, Docker Compose | language_preference | step 4 — ADR-0026 … ADR-0035, **ADR-0052**; user, 2026-08-09 | no | **Settled 2026-08-09, replacing the inherited hackathon row.** Python and FastAPI confirmed; PostgreSQL and Docker confirmed and now actually implemented. **LangGraph removed** — nothing in scope is a graph (A-127). **RabbitMQ added** (ADR-0028). **Frontend, amended the same day**: ADR-0034 first replaced Next.js with server-rendered Jinja2 + HTMX; the user then chose React for ecosystem compatibility, and **ADR-0052 supersedes it** — a Vite-built React SPA with **Node in CI only**, baked into a `caddy:2` image. Node still never runs in production, the service count stays at 7, and ADR-0029's cookie stays same-origin. **Next.js itself remains rejected** (ADR-0034's reasons survive the reversal). See `docs/architecture/tech_stack.md` |
| Gateway-added latency, excluding the upstream call, targets p95 under 50 ms | performance_budget | A-031 (agent-decided placeholder, pending OQ-012) | no | The strategy is yours; the number is mine until you replace it |
| Restore to a previously Approved revision completes in under 5 minutes | performance_budget | H-05, `prope_source_of_truth.md` §13 | no | Stated as a hypothesis target, not a committed SLA |
| Finding the trusted revision takes under 30 seconds | performance_budget | H-01, `prope_source_of_truth.md` §13 | no | Stated as a hypothesis target |
| The whole system must run for one small team with no dedicated ops, on one host, with no component needing its own runbook | ops_capacity | A-012 as amended 2026-08-09; ADR-0028, ADR-0033 | no | **Amended 2026-08-09.** Still one `docker-compose up`, but the honest count is **seven services** — `caddy`, `app`, `worker`, `postgres`, `rabbitmq`, `prometheus`, `grafana`. A-012's "no broker, no separate worker fleet" clause is superseded by the user's choice of RabbitMQ; its *debuggable by one person* and *no component needing its own runbook* clauses are still live and still decided things during step 4 (they rejected Kubernetes, Vault, Keycloak, Kafka, Loki, and tracing) |
| The demo and pilot run on one group-controlled Linux VM; nothing leaves that host | deploy_target | user — 2026-08-09 (OQ-011, resolved); ADR-0033 | no | Single failure domain with no HA, consistent with the already-accepted *"a Prope outage is a full outage"* row. Sizing: 4 vCPU / 8 GB / 80 GB SSD. Revisit when a consuming product depends on Prope in production |
| All tenant-scoped tables enforce workspace isolation with a PostgreSQL row-level security policy | security | ADR-0035; user — 2026-08-09 | no | The **mechanism**, not the rule: the rule is BR-01's *"prompts are private by default"*, which is non-negotiable in its own row. A forgotten `WHERE workspace_id` returns **zero rows**, not another workspace's data — the same enforcement move as BR-03's constraint and ADR-0025's privilege |

## Glossary

### Prompt property
**Definition**: One registry record representing a prompt with a stated purpose, an owner, a model name, an access level, and a chain of revisions.
**Source**: `prope_source_of_truth.md` §8
**Aliases**: prompt, prompt asset (strategy documents only)

### Model name
**Definition**: The globally unique `namespace/name` string by which a prompt property is called through the gateway, and which appears in the `model` field of an OpenAI-compatible request.
**Source**: user — 2026-08-08 (OQ-003)
**Aliases**: prompt reference
**proposed: true**

### Gateway
**Definition**: The OpenAI-compatible endpoint that resolves a model name to a released revision, applies its system prompt and model binding, forwards the call to the configured provider, and returns the result or the fallback answer.
**Source**: user — 2026-08-08 (OQ-003, OQ-012)
**Aliases**: none
**proposed: true**

### Fallback answer
**Definition**: A stored answer, authored by a human or proposed by an agent and accepted by a human, returned in place of a model response when the upstream provider fails.
**Source**: user — 2026-08-08 (OQ-012)
**Aliases**: none
**proposed: true**

### Call record
**Definition**: The stored record of one gateway call — prompt, version ID, consumer, timestamp, tokens, cost, outcome, and the request and response bodies.
**Source**: user — 2026-08-08 (OQ-012)
**Aliases**: usage record (metadata subset), log
**proposed: true**

### Provider configuration
**Definition**: The workspace-level record of an upstream provider, its credential, and the models it exposes, managed from the dashboard.
**Source**: user — 2026-08-08 (OQ-004)
**Aliases**: none
**proposed: true**

### Prompt Owner
**Definition**: The person accountable for stewardship of one prompt property — its purpose, access, and revisions.
**Source**: `prope_source_of_truth.md` §4.1
**Aliases**: prompt creator (deprecated), owner

### Reviewer
**Definition**: The person who receives a submitted revision and records an approve or request-changes decision.
**Source**: `prope_source_of_truth.md` §4.2
**Aliases**: Approver

### Revision
**Definition**: An immutable snapshot of a prompt's body, provider, model, generation parameters, and fallback answer at one point in time, with an author and a timestamp.
**Source**: `prope_source_of_truth.md` §8; BR-06
**Aliases**: version (technical contexts only)

### Trusted revision
**Definition**: The revision a reviewer has approved and that the team is expected to use.
**Source**: `prope_source_of_truth.md` §8
**Aliases**: approved revision; the system status stays literally `Approved`

### Released revision
**Definition**: The one Approved revision the gateway currently resolves a bare model name to.
**Source**: user — 2026-08-08 (OQ-003)
**Aliases**: In use

### Version ID
**Definition**: The opaque, globally unique identifier of one revision, used to pin a gateway call and to trace a release.
**Source**: `prope_source_of_truth.md` §8
**Aliases**: none

### Registry
**Definition**: The searchable record of all prompt properties and their current owner, status, access, and trusted revision.
**Source**: `prope_source_of_truth.md` S1
**Aliases**: Portfolio (a user's own subset)

### Release
**Definition**: The recorded decision that points the gateway at one Approved revision, carrying a version ID and its own approval.
**Source**: `prope_source_of_truth.md` §8, S7; user — 2026-08-08 (OQ-002)
**Aliases**: promote (developer-facing only), publish (forbidden)

### Restore
**Definition**: A release whose target revision is a previously Approved revision, used to recover from a bad change.
**Source**: `prope_source_of_truth.md` §8
**Aliases**: rollback (API and technical documentation only)

### Break-glass release
**Definition**: A release performed without a prior approval record, requiring a one-line reason, flagged as such, and generating a follow-up review task.
**Source**: `BRIEF.md` §5②
**Aliases**: emergency release

### Eval case
**Definition**: One stored test input plus its deterministic assertions, used to check a revision.
**Source**: `prope_source_of_truth.md` S5; user feature request #3
**Aliases**: test case

### Eval suite
**Definition**: A named, separately versioned set of 10–20 eval cases attached to one prompt property, declaring the output modality its assertions apply to. A prompt may carry several.
**Source**: user feature request #3; user — 2026-08-08 (named suites, A-062)
**Aliases**: test set, eval contract (broader term in `business-analysis.md` §7)

### Output modality
**Definition**: The shape of the content a target returns for a given suite — prose, or structured data and asset references — which determines the assertion types that suite may use.
**Source**: user — 2026-08-08; A-061
**Aliases**: none
**proposed: true**

### Deterministic assertion
**Definition**: A check on a model output that code can decide without judgment — exact or substring match, regex, JSON-schema validity, required phrase, forbidden phrase, length, latency, cost.
**Source**: BR-08; `positioning.md` §4 "USP hỗ trợ #1"
**Aliases**: contract check
**proposed: true**

### Cost delta
**Definition**: The difference in tokens and money between running the eval suite on the candidate revision and on the current released revision.
**Source**: user feature request #4; BR-07
**Aliases**: cost comparison

### Property history
**Definition**: The append-only log of every state change on a prompt property — actor, action, target, timestamp, reason.
**Source**: `prope_source_of_truth.md` §8; NFR-02
**Aliases**: audit history, Activity (simple UI)

### Grant access
**Definition**: The explicit act by which an owner makes a private prompt visible to a team.
**Source**: `prope_source_of_truth.md` §8
**Aliases**: share (forbidden in user-facing copy)
