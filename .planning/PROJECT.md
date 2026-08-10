# Prope

## What This Is

Prope is a prompt registry and release-control system for product teams whose prompts currently live in chat history, Google Sheets, Notion, and source files. It gives every prompt an owner, an immutable revision chain, a fixed eval suite, and a recorded human approval before anything reaches production — then serves the released revision through an OpenAI-compatible gateway so a consuming product calls a prompt by model name and never holds a copy of the text.

The three people it is for: the **Prompt Owner** (designer, marketer, PM, domain expert) who must be able to register and revise a prompt with zero lines of code; the **Reviewer/Approver** who sees the diff, the eval pass/fail, and the cost delta on one screen and records a decision; and the **Developer/AI Engineer** who points an OpenAI-compatible client at Prope's gateway and gets a restore-without-redeploy.

## Core Value

**No prompt reaches production without a recorded human approval, and every call can be traced back to the exact revision that served it.** If everything else fails, this must hold — it is the one thing a spreadsheet cannot do, and 0/11 teams in the survey have it today.

## Business Context

- **Customer**: Product teams across the group — designers, marketers, PMs, domain experts, and the AI engineers who consume their prompts
- **Revenue model**: Internal tooling; no direct revenue. Value is measured in redone work avoided and failures traced
- **Success metric**: 100% of non-break-glass releases carry an approval record; 0 unapproved revisions ever released
- **Strategy notes**: `docs/brainstorm/00_context.md`, `docs/brainstorm/positioning.md`

## Requirements

### Validated

(None yet — ship to validate)

### Active

All 89 requirements are adopted verbatim from the handoff. Each is exactly one acceptance criterion from one module lock file. Full text and traceability in `.planning/REQUIREMENTS.md`.

**Call Ledger** — every completed call recorded off the response path, priced once at write time

- [ ] **CL-01**: Every gateway call produces a durable call record carrying its version ID even when RabbitMQ is unreachable; only bodies are dropped, and the drop counter accounts for every one
- [ ] **CL-02**: A redelivered or replayed call record is written exactly once, leaving the workspace's spend total unchanged, with every duplicate counted
- [ ] **CL-03**: A call is priced at the price row in force at the call's own timestamp, and a price row added later never changes it
- [ ] **CL-04**: A call for a provider and model with no price row stores its tokens with cost `unpriced` — never zero — and appears on the unpriced worklist
- [ ] **CL-05**: Repricing gives a previously unpriced call its cost and leaves an already-priced call untouched
- [ ] **CL-06**: A workspace over its monthly ceiling has eval runs refused with a reason and no spend figure, while its gateway traffic continues to be recorded normally
- [ ] **CL-07**: A spend-ceiling check that cannot be evaluated returns allowed, counts the failure, and never raises into evaluation
- [ ] **CL-08**: Call bodies past their retention window are deleted while their call records stay intact
- [ ] **CL-09**: An eval-case usage row is priced and counted toward workspace spend with no body stored
- [ ] **CL-10**: No route, parameter, or function anywhere in the module returns a stored request or response body
- [ ] **CL-11**: A call whose provider returned no usage object records unknown tokens as null — never zero — and the unknown count is reported alongside the total
- [ ] **CL-12**: Enqueuing a call record stays off the caller's response path at p95 under 1 ms under sustained load, with no metadata dropped

**Property History** — the append-only record of every state change, in one table with one writer

- [ ] **PH-01**: A state change and its history event commit together or not at all, with no interleaving that leaves a release without its event
- [ ] **PH-02**: The application's database role cannot UPDATE or DELETE a history event — the engine refuses, not an application guard
- [ ] **PH-03**: A prompt's Activity returns every event about it from all four writing modules in one query, in submission order, with no event from another prompt or workspace
- [ ] **PH-04**: Two events written in one transaction have a stable, defined order even when their timestamps are identical
- [ ] **PH-05**: An append carrying an unregistered action or details key raises, fails the caller's transaction, and is counted
- [ ] **PH-06**: The registered action vocabulary and the union of the lock files' event lists are the same 31 names, with no extras and no omissions
- [ ] **PH-07**: No route in any module resolves to property-history, and no `/api/v1/history` path exists at any version
- [ ] **PH-08**: No prompt body, fallback answer, credential, password hash, eval output, or variable value appears in any history event field
- [ ] **PH-09**: A person removed from a workspace keeps their `actor_id` on every event they wrote, and none is deleted or reattributed
- [ ] **PH-10**: No history row is ever removed, and no expiry job exists that would remove one

**Access Control** — authenticates every actor, answers every may-this-actor-do-this question

- [ ] **AC-01**: A private prompt is not-found to someone with no grant, on every endpoint and in search, identical in shape and status to a prompt id that never existed
- [ ] **AC-02**: Someone who can see a subject but lacks the permission gets a refusal naming the missing permission, not a not-found
- [ ] **AC-03**: An actor's permissions are the union of their role bindings and grants; nothing subtracts
- [ ] **AC-04**: An action outside the closed vocabulary is denied, counted, and never raises into the caller
- [ ] **AC-05**: A consumer key used outside its model-name scope gets a response byte-identical to one for a model name that does not exist
- [ ] **AC-06**: Revoking a consumer key takes effect on the very next request, with no TTL elapsed and no cached allow in any module
- [ ] **AC-07**: An API key's plaintext secret appears in its creation response and nowhere else — no other response, log, metric label, or history event — and cannot be reconstructed from the stored row
- [ ] **AC-08**: An operation that would leave a workspace with zero Admins is refused and counted
- [ ] **AC-09**: `visible_subject_filter` returns exactly the prompts an actor owns or was granted, and the registry's list endpoint returns exactly that set
- [ ] **AC-10**: Every route in every module declares an action from the vocabulary; a route declaring none fails the test rather than defaulting to unauthenticated
- [ ] **AC-11**: When access-control's database is unreachable, every module refuses every request and none logs an allow
- [ ] **AC-12**: A grant and its history event share one transaction, so neither exists without the other
- [ ] **AC-13**: Tombstoning a person nulls their identifying columns, ends every session they hold, and makes a sign-in with their former email byte- and timing-identical to one with an email that never existed
- [ ] **AC-14**: A tombstoned person's history events all survive with their `actor_id` unchanged, and one reasonless `user_tombstoned` event exists per workspace they belonged to
- [ ] **AC-15**: No surface renders a name or email for a tombstoned actor; each renders the absence through a catalogue key

**Provider Access** — workspace provider configs and credentials; Prope's only outbound egress

- [ ] **PA-01**: No management response, error body, or history event ever contains a provider credential — only its last four characters
- [ ] **PA-02**: A credential cannot be recovered from the database contents alone, and can be recovered when the key-encryption key is also supplied
- [ ] **PA-03**: A provider whose endpoint returns no usage object fails verification, is not saved active, and cannot be bound to a revision
- [ ] **PA-04**: Every dispatch asks the provider for usage and returns a usage object; no caller parameter can turn it off
- [ ] **PA-05**: Every upstream failure maps to its own error class with `fallback_eligible` and `retryable` set independently
- [ ] **PA-06**: Batch dispatches yield to interactive ones on a shared credential — an arriving interactive dispatch is admitted without waiting, and shed batch work is counted
- [ ] **PA-07**: A dispatch that times out or fails issues exactly one upstream request; no retry happens inside this module regardless of error class
- [ ] **PA-08**: A rotated credential is in use in every process within 60 seconds with no restart, and its history event records the actor and the time but no part of either credential
- [ ] **PA-09**: Every provider's response is normalised into a valid OpenAI chat-completions object, with fields Prope does not model passed through unchanged
- [ ] **PA-10**: Deleting a provider configuration bound by a revision is refused with a count and no query into the registry's tables, while disabling it stops dispatch and keeps the configuration and catalogue readable
- [ ] **PA-11**: A base URL resolving to a private or loopback address is refused at save and at dispatch, and no request carrying the credential is issued
- [ ] **PA-12**: With the key-encryption key unavailable, readiness is withheld, the KEK gauge is set, and the dispatch failure is distinguishable from every provider-origin failure

**Prompt Registry** — prompt properties and their immutable revision chain; the diff; search

- [ ] **PR-01**: Editing a prompt creates the next immutable revision with author and timestamp, leaving every earlier revision byte-identical
- [ ] **PR-02**: A reviewer sees a line-level body diff plus a field-level comparison of provider, upstream model, parameters, and fallback answer, rendered under 300 ms with both bodies at the 32 KiB cap
- [ ] **PR-03**: A private prompt is absent from another person's search results, and a direct fetch by its id returns the same not-found as a nonexistent id
- [ ] **PR-04**: The gateway resolves a bare model name to the released revision's full binding at p95 under 10 ms
- [ ] **PR-05**: Retiring a prompt with an active release is refused with a message naming the release, and the prompt's status is unchanged
- [ ] **PR-06**: The database rejects any attempt to point the released pointer at a revision that is not Approved

**Evaluation** — named eval suites; runs candidate against released; cost delta

- [ ] **EVAL-01**: A 20-case suite run completes under 120 s at p95 and shows per-case pass/fail for the candidate and the released revision plus the token and money delta between them
- [ ] **EVAL-02**: Cases that ended in a dispatch error are shown as error rather than fail, and the cost delta is withheld with a stated reason
- [ ] **EVAL-03**: A baseline run is reused rather than re-dispatched when the released revision and suite version are unchanged, and the reused baseline's timestamp is shown
- [ ] **EVAL-04**: Editing a suite creates its next version, leaves an in-flight run reporting against its own version and sibling suites untouched, and a comparison across two versions is refused
- [ ] **EVAL-05**: A candidate whose suite cost exceeds the baseline by the configured threshold shows a warning above the decision buttons while approve and release stay enabled
- [ ] **EVAL-06**: Eval runs and case results for a private prompt are the same not-found shape to someone with no grant, and no output text is returned
- [ ] **EVAL-07**: A run whose worker died is marked interrupted, keeps its completed case results readable, and dispatches no case twice
- [ ] **EVAL-08**: Submitting a revision starts one run per suite, and the review summary carries one row per suite plus a rollup requiring acknowledgement if any suite has a failing case
- [ ] **EVAL-09**: A run whose declared suite modality does not match what the target returns is refused before any case is dispatched, naming both shapes, with no upstream call billed
- [ ] **EVAL-10**: Concurrent suite runs stay within the declared concurrency bounds, with the remainder queued and every run eventually completing

**Gateway** — OpenAI-compatible `/v1`; resolves a model name to the released revision; fallback

- [ ] **GATE-01**: A call using a bare model name is served from the released revision, OpenAI-shaped, with the version ID in the response header, the body's `prope` object, and the call record
- [ ] **GATE-02**: A pin to an Approved revision is served; a pin to a non-Approved revision is refused OpenAI-shaped with no upstream dispatch, counted as `pin_not_approved`
- [ ] **GATE-03**: A withdrawn prompt returns an OpenAI-shaped model-not-found — never the previous revision, never the fallback answer — counted as `no_release`, distinct from an unknown model name
- [ ] **GATE-04**: An upstream failure before the first byte serves the revision's fallback answer as a 200 marked in header, body, and call record, with zero tokens and zero cost
- [ ] **GATE-05**: An upstream failure with no fallback answer stored passes the provider's error through in the OpenAI error shape, with no canned content returned
- [ ] **GATE-06**: An upstream failure after chunks have been relayed terminates the stream with an OpenAI-shaped error chunk, appends no fallback text, and records the call as `truncated` with its partial body
- [ ] **GATE-07**: A caller-supplied system message is refused with an OpenAI-shaped 400 and no upstream dispatch; the revision's own system prompt is never concatenated with the caller's
- [ ] **GATE-08**: A request omitting a variable the revision's body declares is refused with an OpenAI-shaped 400 naming it, and no unsubstituted placeholder is ever dispatched upstream
- [ ] **GATE-09**: A release or restore reaches every gateway process within 30 seconds with no restart and no invalidation message
- [ ] **GATE-10**: A consumer key calling a model name outside its scope gets a response identical in shape to one for a name that does not exist, counted as `not_permitted`
- [ ] **GATE-11**: A stalled call-ledger leaves gateway response p95 statistically unchanged, every call record keeps its version ID, and only bodies are dropped with a matching counter
- [ ] **GATE-12**: `GET /v1/models` lists exactly the released prompts the calling key may resolve, in the OpenAI list shape, with `id` equal to the model name

**Release Control** — submit → recorded human decision → release, restore, withdraw, break-glass

- [ ] **RC-01**: A submitted revision approved by a permitted reviewer becomes Approved, with an approval row naming the reviewer and a matching history event
- [ ] **RC-02**: An author holding the approve permission may approve their own revision — recorded as `self_approved` on the row, in the history event, and in a counter, never refused — while an author holding only edit is refused
- [ ] **RC-03**: Releasing an Approved revision moves the released pointer and writes a release row carrying its approval, so no non-break-glass release lacks an approval record
- [ ] **RC-04**: Approving a candidate whose evaluation requires acknowledgement is refused without a reason and succeeds with one, which is stored on the approval and appears in the property history
- [ ] **RC-05**: When evaluation is unavailable the review screen says the evidence could not be loaded, an acknowledgement reason becomes mandatory, approval still succeeds, and the gap is counted
- [ ] **RC-06**: Restoring to a previously Approved revision writes a release of kind `restore`, moves the pointer, and has the gateway serving the restored revision within 5 minutes
- [ ] **RC-07**: Withdrawing a release clears the released pointer, records the previous version, makes the gateway return model-not-found, and unblocks retiring the prompt
- [ ] **RC-08**: A break-glass release is flagged with no approval, creates a 24-hour follow-up task that never closes itself on a timer, and is counted while overdue
- [ ] **RC-09**: Submitting a new revision supersedes the open review task for that prompt, leaving exactly one open and altering no approval already recorded
- [ ] **RC-10**: Two concurrent releases of one prompt produce exactly one release row, with the loser refused and told the currently released version ID, and the conflict counted
- [ ] **RC-11**: An approval keeps the per-suite counts and cost delta as they stood at decision time, even after the suite is edited and re-run with different results
- [ ] **RC-12**: Approve-and-release by an actor holding both permissions writes one approval and one release in a single transaction with both history events, and is refused naming the missing permission when the actor holds only one

### Out of Scope

Excluded scope, from the handoff's section 1:

- **Import/ingestion from repos, Sheets, Notion, Drive, chat exports** — the root problem is lost ownership and provenance, not the absence of somewhere to save text
- **Similar-prompt clustering** — same reason; solving discovery by similarity does not restore ownership
- **Traces, spans, trace explorer, analytics dashboards, sampling policy** — this is the observability product; integrate with Langfuse, do not compete
- **Environment aliases beyond one released pointer** — one released revision per prompt is the whole model
- **Multi-region or multi-tenant routing** — one VM, one failure domain, accepted at pilot scale
- **OpenAI endpoints beyond chat completions and `/v1/models`** — A-094: OpenAI-compatible is the whole MVP
- **Multi-level approval, configurable policy engine, scheduled drift monitoring** — one recorded decision is the MVP; a policy engine is a v2 shape
- **Individual mode** — Prope is a workspace product; a single-user mode has no approval step to record
- **LLM-judge quality scoring** — deterministic assertions only; a judge introduces the non-determinism the eval exists to remove
- **Semantic/vector search** — trigram over a trigger-maintained document column (ADR-0048); substring semantics are asserted, not incidental

**Anti-goals** — things Prope deliberately will not become:

- **The observability product** — integrate with Langfuse, do not compete
- **A prompt marketplace or public template library**
- **A chat or playground surface**
- **Auto-release of any kind** — the first non-negotiable
- **An agent that autonomously rewrites prompts or fallback answers** and puts them in front of users without a human accepting the revision
- **Any claim that Prope establishes legal IP ownership**
- **Any claim that the eval suite guarantees no quality degradation**

## Context

**The problem is measured, not assumed.** In the group's own enterprise survey (n=11, directional): 10/11 keep prompts in chat history, each person uses about 3 storage locations, and 0/11 use any dedicated prompt tool. 11/11 cannot reliably find or identify the prompt they need; 11/11 do not know which revision is the latest; 11/11 see teammates using different prompts for the same task; 9/11 do not know who owns a prompt. Downstream: 8/11 get inconsistent output, 7/11 redo work, 5/11 cannot identify which prompt caused a failure, 4/11 discover errors only after release. **0/11 have any formal approval step before a prompt reaches production.**

The root problem is **lost ownership, lost provenance, and lost trust** — not the absence of somewhere to save text. Reducing it to "users need a place to save prompts" produces the wrong product.

**The enforcement pattern is the project's spine.** Six times, a rule that could have lived in application code was pushed into the database instead: the Approved-only released pointer is a **constraint**; the append-only history is a **privilege** (`REVOKE UPDATE, DELETE`); tenant isolation is a **policy** (RLS, deny-by-default, a missing filter returns zero rows); schema-per-module is a **grant**; `search_text` is a **trigger**; and ADR-0045 inverted the RLS coverage test so it walks every table in all eight schemas. Build in that order: the migration carries the guarantee, and the application code is what the guarantee protects.

**Everything asynchronous was refused except one thing.** There is exactly one broker queue, `prope.call_record`, and it exists because writing a call record must not sit on the response path. Cache invalidation over the broker was proposed twice and rejected twice on merit. Do not add a second queue, and do not add fanout invalidation.

**Two reversals are on record.** (1) "Never on the hot path" was an anti-goal in `positioning.md`; the gateway decision overrides it and accepts Prope as a **hard dependency** — if Prope is down, every consuming product's AI feature is down, and the fallback answer does not cover this because the fallback is stored in Prope. Accepted, not mitigated. (2) The "content-free telemetry" claim in `positioning.md` §4 dies with the decision to store request and response bodies. It must be removed from the pitch, not softened.

**Existing repository state.** The repo carries a boilerplate scaffold (`Dockerfile`, `docker-compose.yml`, `Makefile`, `requirements.txt`, `scripts/`, `eval/`) with `src/` and `tests/` emptied. Treat the build as greenfield against the module specs, not as a brownfield extension.

### Glossary — use these words

| Term | One line |
|------|----------|
| **Prompt property** | One registry record: purpose, owner, model name, access level, revision chain |
| **Revision** | An immutable snapshot of body, provider, model, parameters and fallback answer *(not "version")* |
| **Model name** | The globally unique `namespace/name` a prompt is called by through the gateway |
| **Version ID** | The opaque identifier of one revision; pins a call, traces a release |
| **Trusted revision** | The revision a reviewer approved; the status stays literally `Approved` |
| **Released revision** | The one Approved revision a bare model name resolves to *(shown as "In use")* |
| **Release** | The recorded decision that points the gateway at one Approved revision *(not "publish")* |
| **Restore** | A release whose target is a previously Approved revision *(not "rollback")* |
| **Break-glass release** | A release with no prior approval: reason required, flagged, follow-up task |
| **Gateway** | The OpenAI-compatible endpoint that resolves, composes, forwards, and falls back |
| **Fallback answer** | A stored human-accepted answer returned when the upstream provider fails |
| **Call record** | One gateway call: prompt, version ID, consumer, tokens, cost, outcome, bodies |
| **Eval suite / eval case** | A named set of 10–20 hand-authored cases with deterministic assertions |
| **Cost delta** | Tokens and money, candidate versus released, over the same suite |
| **Grant access** | How a prompt reaches another person *(not "share")* |

Statuses are literal and are never renamed: **Draft, In review, Approved, In use, Retired**.

### Success metrics

| Metric | Target | How measured |
|--------|--------|--------------|
| Time to find the trusted revision of a named prompt | ≤ 30 s in ≥ 80% of attempts | Timed usability script, 5 participants × 5 prompts |
| Non-developer creates and submits a revision | 3 of 3 runs, 0 lines of code | Observed demo run against a checklist |
| Fixed eval suite completes and renders pass/fail | 10–20 cases in ≤ 120 s (p95) | Wall-clock of the eval-run endpoint, 20 runs |
| Reported token counts match the provider | within ±2% | Stored usage rows vs. provider `usage` field, 20 runs |
| Releases carrying an approval record | 100% of non-break-glass releases | SQL: releases LEFT JOIN approvals where `break_glass = false` |
| Unapproved revision reaching a release | 0 occurrences | SQL over releases where `revision.status != 'Approved'` |
| Gateway calls recording a version ID | 100% | SQL over call records with NULL `version_id` |
| Latency the gateway adds on top of the upstream call | p95 < 50 ms | Instrumented span, arrival → dispatch plus completion → flush |
| A fallback answer is detectable by the caller | 100% of fallback-served calls | `x-prope-fallback` header + `prope.fallback` field over all `outcome = fallback` records |
| Restore to a previously Approved revision | ≤ 5 min, decision → gateway serving it | `revision_restored` event → first call record carrying the restored version ID (hand-run SQL, A-126) |
| Median review turnaround | < 1 business day | `submitted_at` → `decided_at`, median over the pilot |

## Constraints

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

## Key Decisions

Merged from the handoff's sections 8 (54 ADRs, full text in `docs/adr/`) and 9 (151 assumptions in `docs/brainstorm/assumptions/`). Assumption rows are marked `assumed` — each is one file away from being overturned.

### The enforcement pattern — a rule in the database, not in application code

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ADR-0001 | The released pointer is a field on the prompt property, writable only through release-control's command | — Pending |
| ADR-0002 | The registry is append-only; revisions are never edited or deleted | — Pending |
| ADR-0025 | Append-only is a **database privilege**, not a convention — `REVOKE UPDATE, DELETE` on `history_event` | — Pending |
| ADR-0027 | One database, one schema per module, two roles | — Pending |
| ADR-0035 | Tenant isolation is a **database policy** — RLS, `SET LOCAL app.workspace_id` | — Pending |
| ADR-0045 | Every table is tenant-scoped unless declared global; the coverage test walks all eight schemas | — Pending |
| ADR-0048 | Search is a trigram index over a **trigger-maintained** document column | — Pending |

### Release and approval

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ADR-0004 | Eval-run granularity and baseline reuse | — Pending |
| ADR-0005 | A failing eval requires an acknowledgement, never a block | — Pending |
| ADR-0006 | Named eval suites per prompt | — Pending |
| ADR-0007 | The release record **is** the release decision | — Pending |
| ADR-0008 | Status moves by command, not by write | — Pending |
| ADR-0009 | Withdrawing a release is an explicit decision, with its own permission and reason | — Pending |
| ADR-0010 | Approval eligibility is permission-only; self-approval is recorded, never refused | — Pending |

### The gateway and the hot path

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ADR-0011 | The caller supplies the conversation, never the system prompt | — Pending |
| ADR-0012 | The resolution cache **expires**; nothing invalidates it | — Pending |
| ADR-0013 | Fallback is a pre-first-byte decision | — Pending |
| ADR-0015 | The OpenAI shape is the internal dispatch contract | — Pending |
| ADR-0017 | provider-access classifies failures; callers react | — Pending |
| ADR-0022 | Revocation takes effect on the next request — nothing about auth is cached | — Pending |
| ADR-0050 | The gateway is a mounted sub-application with its own error contract | — Pending |

### Credentials, keys, and data

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ADR-0014 | Credential envelope encryption; provider-access is the only module that decrypts | — Pending |
| ADR-0018 | The body store has no read path in the MVP | — Pending |
| ADR-0019 | Cost is priced once, at write time | — Pending |
| ADR-0020 | Permission is a local decision; callers supply the subject | — Pending |
| ADR-0021 | Consumer keys are **hashed**, not encrypted — the direction of use decides the storage | — Pending |
| ADR-0023 | property-history is a library in the caller's transaction | — Pending |
| ADR-0024 | One event schema with a registered payload | — Pending |
| ADR-0054 | A departing person is tombstoned, never deleted | — Pending |

### Runtime and platform

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ADR-0026 | Python and FastAPI are the one runtime | — Pending |
| ADR-0028 | RabbitMQ carries the asynchronous work — one queue, one DLQ | — Pending |
| ADR-0029 | Identity is local and the session is a row | — Pending |
| ADR-0030 | Observability is Prometheus and Grafana and nothing else | — Pending |
| ADR-0031 | CI publishes an image and CD pulls it | — Pending |
| ADR-0032 | Secrets live in one `.env` file on the host | — Pending |
| ADR-0033 | One VM, docker-compose, and Caddy | — Pending |
| ADR-0036 | Backups are a nightly dump copied off the host | — Pending |
| ADR-0041 | Broker-first with a direct-write fallback | — Pending |
| ADR-0042 | The authentication bootstrap escapes RLS through two named functions | — Pending |
| ADR-0046 | The admission gate is two per-process caps | — Pending |
| ADR-0047 | Dispatch connects to the address it validated | — Pending |
| ADR-0049 | The eval executor claims run rows rather than consuming messages | — Pending |
| ADR-0052 | The UI is a React SPA built in CI and served by Caddy | — Pending |
| ADR-0053 | The UI ships one locale behind an i18n layer | — Pending |

> **ADR-0034 is superseded by ADR-0052**, but Next.js itself remains rejected — ADR-0034's reasons survive the reversal.

### Assumptions decided on the project's behalf

The ones with the widest blast radius if wrong. All 151 are in `docs/brainstorm/assumptions/`, all `active`.

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| A-007 (assumed, agent) | Working role set: Owner, Reviewer, Viewer, Admin, with edit / approve / release separated. If it flips: `role_permission` rows change, no schema change. **Removing** a role after bindings exist is the expensive case | assumed — revisit when the role matrix is exercised in the pilot |
| A-020 (assumed, agent) | No real corporate prompts until the security baseline is signed off. If it flips: this is the line holding the pilot; it is a policy, not code | assumed — revisit when OQ-006 and OQ-013 close |
| A-051 (assumed, agent) | An owner is one person; transfer is an explicit recorded action. If it flips: `owner_id` points at a principal table instead of a user table. Kept cheap by denormalising the owner's name nowhere | assumed — revisit when OQ-008 is answered |
| A-012 (assumed, agent) | Small team, no dedicated ops, one `docker-compose up`. Amended already — the honest count is seven services. The *debuggable by one person* clause is still live and rejected Kubernetes, Vault, Keycloak, Kafka, Loki, and tracing | assumed — revisit when OQ-005 gives a team size |
| A-016 (assumed, agent) | Cost delta warns at +20% and never blocks. Threshold and block flag are configurable; the default is the assumption | assumed — revisit after the first pilot review cycle |
| A-031 (assumed, agent) | Gateway adds p95 < 50 ms. The number is a placeholder until OQ-012; the instrumented span exists either way | assumed — revisit when OQ-012 gives a number |
| A-040 (assumed, agent) | Bodies 30 days, metadata indefinite. A setting from day one, so OQ-013's answer is a configuration change and not a migration | assumed — revisit when OQ-013 closes |
| A-108 (**human**) | Local email and password with server-side sessions. Confirmed by the user and promoted to `human`; ADR-0029 records it. This closed access-control's last estimability gap | ✓ Good — confirmed by the user |
| A-008 (**human**) | Approval is permission-only; self-approval is recorded, never blocked. User overturned the agent's original segregation-of-duties assumption; ADR-0010 | ✓ Good — confirmed by the user |
| A-094 (assumed, agent) | OpenAI-compatible is the whole MVP; a second adapter is post-MVP. The provider surface is one HTTP client against a configurable base URL | assumed — revisit when a non-compatible provider is required |
| A-143 (assumed, agent) | 20 in-flight requests per consumer key. Per **process**; a gateway split would double it | assumed — revisit when the gateway is scaled past one process |
| A-144 (assumed, agent) | Login limiter: 5 per email, 20 per address, per 15 min. Same per-process footnote | assumed — revisit when the app is scaled past one process |
| A-126 (assumed, agent) | Restore time and median review turnaround are hand-run SQL at pilot review, not product surfaces | assumed — revisit if either metric needs to be continuous |

## Planning source

This project's architecture was decided upstream and is read-only here.

| What | Where |
|------|-------|
| Handoff | `docs/build/gsd_handoff.md` (bsp-gsd/1) |
| Orientation | `docs/AGENT_CONTEXT.md` |
| Module specs | `docs/modules/<module_id>.lock.yml` |
| Interfaces | `docs/architecture/interfaces.md` |
| Decisions | `docs/adr/` |
| Phase → spec index | `.planning/BSP-LINK.md` |

Do not edit anything under `docs/`. A spec that disagrees with the code is information — raise it upstream, do not patch it to agree.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

> In adoption mode, "add to Active" and "add to Key Decisions" mean recording what the build learned — **not** editing the upstream specs. A requirement that turns out to be wrong is an `OQ-NNN` raised against its lock file.

---
*Last updated: 2026-08-09 after initialization from the BSP planning handoff*
