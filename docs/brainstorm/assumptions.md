# Assumptions

Generated from `assumptions/A-NNN.md`. The files are the source of truth; if this table disagrees
with a file, the file wins. Everything marked `agent` in **Decided by** is a call made on your
behalf — overturn any of them by editing one file. Nothing here is waiting on you.

| ID | Scope | Status | Decided by | From OQ | Statement |
|----|-------|--------|------------|---------|-----------|
| [A-001](assumptions/A-001.md) | global | active | agent | none | "version / rollback / promote" render as revision / restore / release in user-facing copy. |
| [A-002](assumptions/A-002.md) | global | active | agent | none | A revision is immutable, numbered per prompt, and carries an opaque global version ID. |
| [A-003](assumptions/A-003.md) | global | active | agent | none | All timestamps are stored and exchanged as RFC 3339 UTC. |
| [A-004](assumptions/A-004.md) | global | active | agent | none | Eval suites belong to the prompt, not to the revision (amended 2026-08-08 — named suites, A-062). |
| [A-005](assumptions/A-005.md) | global | active | agent | none | Pass/fail comes only from deterministic assertions; subjective quality is displayed, never scored. |
| [A-006](assumptions/A-006.md) | global | active | agent | none | Cost delta is measured over one full eval-suite run, candidate vs. released revision. |
| [A-007](assumptions/A-007.md) | global | active | agent | [OQ-006](open_questions/OQ-006.md) | Working role set: Owner, Reviewer, Viewer, Admin, with edit / approve / release separated. |
| [A-008](assumptions/A-008.md) | global | active | human | none | Who may approve is determined by permission alone; self-approval is recorded, never blocked (amended 2026-08-08 by the user; ADR-0010). |
| [A-009](assumptions/A-009.md) | global | active | agent | none | Break-glass release is in the MVP: a reason, a flag, and a 24-hour review task. |
| [A-010](assumptions/A-010.md) | global | active | agent | [OQ-002](open_questions/OQ-002.md) | Restore may only target a previously Approved revision, recorded as a release event. |
| [A-011](assumptions/A-011.md) | global | active | agent | none | A prompt body is one plain-text system message with optional `{{variable}}` placeholders. |
| [A-012](assumptions/A-012.md) | global | active | agent | [OQ-005](open_questions/OQ-005.md) | The team is small with no dedicated ops; one `docker-compose up` must bring everything up (amended 2026-08-09 — the "no broker, no separate worker fleet" clause superseded by ADR-0028; seven services). |
| [A-013](assumptions/A-013.md) | global | active | agent | none | Search is keyword and filter, not semantic. |
| [A-014](assumptions/A-014.md) | global | active | agent | none | Every state change writes an append-only property-history event. |
| [A-015](assumptions/A-015.md) | global | active | agent | none | Feature 2 ships as a line-level textual diff, not a consequence-language diff. |
| [A-016](assumptions/A-016.md) | global | active | agent | [OQ-009](open_questions/OQ-009.md) | Proposed default: cost delta warns at +20% and never blocks. |
| [A-017](assumptions/A-017.md) | global | active | agent | [OQ-007](open_questions/OQ-007.md) | Proposed default: individual mode is out of the MVP. |
| [A-018](assumptions/A-018.md) | global | active | agent | [OQ-010](open_questions/OQ-010.md) | Proposed default: Vietnamese UI copy, English status labels and API vocabulary. |
| [A-019](assumptions/A-019.md) | global | active | agent | [OQ-011](open_questions/OQ-011.md) | Proposed default: the demo runs locally via docker-compose. |
| [A-020](assumptions/A-020.md) | global | active | agent | [OQ-006](open_questions/OQ-006.md) | Proposed default: no real corporate prompts until the security baseline is signed off. |
| [A-021](assumptions/A-021.md) | global | active | agent | [OQ-003](open_questions/OQ-003.md) | The model name is `namespace/name`, unique per workspace, and immutable once created. |
| [A-022](assumptions/A-022.md) | global | active | agent | [OQ-003](open_questions/OQ-003.md) | A bare model name resolves to the released revision; `name@<n>` pins; failures never fall back to another revision. |
| [A-023](assumptions/A-023.md) | global | active | agent | none | One environment in the MVP: a single released pointer per prompt. |
| [A-024](assumptions/A-024.md) | global | active | agent | [OQ-004](open_questions/OQ-004.md) | Provider, model, and parameters live on the revision; the caller cannot override them. |
| [A-025](assumptions/A-025.md) | global | active | agent | [OQ-006](open_questions/OQ-006.md) | Provider credentials are workspace-scoped, encrypted at rest, and never readable back (amended 2026-08-08 — decryptable only in provider-access, not in the gateway or the eval runner; scheme in ADR-0014). |
| [A-026](assumptions/A-026.md) | global | active | agent | [OQ-003](open_questions/OQ-003.md) | The gateway implements chat completions and `/v1/models` only, with OpenAI-shaped errors. |
| [A-027](assumptions/A-027.md) | global | active | agent | none | The eval runner calls a revision through the same resolution path as the gateway. |
| [A-028](assumptions/A-028.md) | global | active | agent | [OQ-002](open_questions/OQ-002.md) | Proposed default: restore to a previously released revision needs no new approval. |
| [A-029](assumptions/A-029.md) | global | active | agent | [OQ-004](open_questions/OQ-004.md) | Spend ceilings exist but default to off; they refuse eval runs, never gateway traffic. |
| [A-030](assumptions/A-030.md) | global | active | agent | [OQ-004](open_questions/OQ-004.md) | Only providers returning a usage object are supported; prices are effective-dated. |
| [A-031](assumptions/A-031.md) | global | active | agent | [OQ-012](open_questions/OQ-012.md) | Gateway resolution: 30 s cache, fallback on upstream failure, error on caller failure, p95 +50 ms (the "invalidated immediately" clause superseded 2026-08-08 by ADR-0012 — the cache expires). |
| [A-032](assumptions/A-032.md) | global | active | agent | [OQ-012](open_questions/OQ-012.md) | The fallback answer is a field on the revision, reviewed and approved with it. |
| [A-033](assumptions/A-033.md) | global | active | agent | [OQ-012](open_questions/OQ-012.md) | A fallback is served as HTTP 200 in the OpenAI shape, marked in header, body, and call record. |
| [A-034](assumptions/A-034.md) | global | active | agent | [OQ-012](open_questions/OQ-012.md) | The fallback fires on upstream failure only, never on caller failure. |
| [A-035](assumptions/A-035.md) | global | active | agent | [OQ-012](open_questions/OQ-012.md) | The fallback answer is optional; without one, the upstream error passes through. |
| [A-036](assumptions/A-036.md) | global | active | agent | [OQ-012](open_questions/OQ-012.md) | An AI-generated fallback answer is a proposed revision, never a live artefact. |
| [A-037](assumptions/A-037.md) | global | active | agent | [OQ-012](open_questions/OQ-012.md) | Logging is off the response path: metadata durable, bodies best-effort (amended 2026-08-09 — "no broker" superseded by ADR-0028; A-099's upsert is now load-bearing under at-least-once delivery). |
| [A-038](assumptions/A-038.md) | global | active | agent | [OQ-012](open_questions/OQ-012.md) | Streaming responses are accumulated and logged after the stream closes. |
| [A-039](assumptions/A-039.md) | global | active | agent | [OQ-012](open_questions/OQ-012.md) | Prope stores raw call records, not traces; Langfuse is an export target, not a rebuild. |
| [A-040](assumptions/A-040.md) | global | active | agent | [OQ-013](open_questions/OQ-013.md) | Placeholder retention: bodies 30 days, metadata indefinite, bodies readable by the owner only. |
| [A-041](assumptions/A-041.md) | global | active | agent | none | The released pointer is a field on the prompt property, writable only by release-control. |
| [A-042](assumptions/A-042.md) | global | active | agent | none | Evaluation never calls release-control; release-control reads run state when it renders. |
| [A-043](assumptions/A-043.md) | global | active | agent | none | Upstream dispatch lives in provider-access; both the gateway and the eval runner call it. |
| [A-044](assumptions/A-044.md) | global | active | agent | none | Property History has one writer, one event schema, and no standalone UI. |
| [A-045](assumptions/A-045.md) | global | active | agent | none | Global management-API conventions: ULID ids, one error envelope, cursor pagination, `/healthz` + `/readyz`. |
| [A-046](assumptions/A-046.md) | global | active | agent | none | Global observability conventions: structured JSON logs, `prope_<module>_<name>_<unit>` metrics, bodies never logged. |
| [A-047](assumptions/A-047.md) | prompt-registry | active | agent | none | The diff is computed on demand and never stored. |
| [A-048](assumptions/A-048.md) | prompt-registry | active | agent | none | Revision numbers are allocated inside the creating transaction, arbitrated by a unique constraint. |
| [A-049](assumptions/A-049.md) | prompt-registry | active | agent | none | Prompt properties and revisions are never hard-deleted; Retired is the terminal status. |
| [A-050](assumptions/A-050.md) | prompt-registry | active | agent | none | Prompt body ≤ 32 KiB; change summary required, ≤ 200 chars. |
| [A-051](assumptions/A-051.md) | global | active | agent | [OQ-008](open_questions/OQ-008.md) | Proposed default: an owner is one person; transfer is an explicit recorded action. |
| [A-052](assumptions/A-052.md) | global | active | agent | none | Retiring a prompt is refused while it has an active release. |
| [A-053](assumptions/A-053.md) | evaluation | active | agent | none | Eval runs use the revision's own parameters; one attempt per case; retries only on transport error. |
| [A-054](assumptions/A-054.md) | evaluation | active | agent | none | Eval runs execute asynchronously at concurrency 5; the client polls; a sweeper reaps interrupted runs (**flagged 2026-08-09** — "in-process" must be revised at evaluation's step-4 pass now that ADR-0028 adds a worker; the run model is unaffected). |
| [A-055](assumptions/A-055.md) | evaluation | active | agent | none | Eval dispatch submits usage for pricing only; outputs live in `case_result`, never in `call_body`. |
| [A-056](assumptions/A-056.md) | global | active | agent | none | The spend-ceiling value is owned by call-ledger; evaluation asks it a yes/no. |
| [A-057](assumptions/A-057.md) | evaluation | active | agent | none | A dispatch failure is `error`, never `fail`, and any error withholds the cost delta. |
| [A-058](assumptions/A-058.md) | global | active | human | [OQ-014](open_questions/OQ-014.md) | Approving over a failing case requires a recorded one-line reason; a failing case never blocks. |
| [A-059](assumptions/A-059.md) | evaluation | active | agent | none | A prompt may have an empty eval suite; the screen says "no eval suite", never "pass". |
| [A-060](assumptions/A-060.md) | evaluation | active | agent | none | With no released revision there is no baseline; the run is absolute and the delta omitted. |
| [A-061](assumptions/A-061.md) | evaluation | active | agent | none | Assertions are an extensible registry keyed by the suite's declared output modality. |
| [A-062](assumptions/A-062.md) | global | active | human | none | A prompt carries several named eval suites, each versioned and run independently. |
| [A-063](assumptions/A-063.md) | evaluation | active | agent | none | The dispatch concurrency bound is global per workspace, not per run. |
| [A-064](assumptions/A-064.md) | global | active | agent | none | Release-control changes revision status by command; prompt-registry performs the write. |
| [A-065](assumptions/A-065.md) | global | active | agent | none | "In use" is derived from the released pointer and is never stored as a revision status. |
| [A-066](assumptions/A-066.md) | global | active | agent | none | Changes requested returns the revision to Draft; the fix is a new revision. |
| [A-067](assumptions/A-067.md) | global | active | agent | none | At most one revision per prompt is In review; a newer submission supersedes the open task. |
| [A-068](assumptions/A-068.md) | global | active | agent | none | A revision approval does not expire; the release screen states its age and its reviewer. |
| [A-069](assumptions/A-069.md) | global | active | agent | none | Withdraw release clears the pointer by command, needs its own permission and a reason. |
| [A-070](assumptions/A-070.md) | release-control | active | agent | none | An unavailable review summary is treated like failing evidence: the reason becomes mandatory. |
| [A-071](assumptions/A-071.md) | global | active | human | [OQ-015](open_questions/OQ-015.md) | Notification is an in-app review queue only; no email, Slack, or webhook. |
| [A-072](assumptions/A-072.md) | release-control | active | agent | none | A release is a compare-and-set on the released pointer, carrying the previous version ID. |
| [A-073](assumptions/A-073.md) | global | active | agent | none | The break-glass follow-up task never auto-closes and never expires. |
| [A-074](assumptions/A-074.md) | release-control | active | agent | none | An approval stores the evidence digest as it stood at decision time; it is testimony, not a cache. |
| [A-075](assumptions/A-075.md) | global | active | agent | none | No person-level segregation exists: the releaser may be the approver and may be the author. |
| [A-076](assumptions/A-076.md) | release-control | active | agent | none | Approve-and-release is one request that writes two rows; it is never a third kind of decision. |
| [A-077](assumptions/A-077.md) | gateway | active | agent | none | The caller supplies the conversation; the system prompt is the revision's, and a caller system message is refused. |
| [A-078](assumptions/A-078.md) | gateway | active | agent | none | Variables arrive in a `prope.variables` object; an unfilled placeholder is a caller error, never dispatched. |
| [A-079](assumptions/A-079.md) | gateway | active | agent | none | Every response identifies what served it, in both headers and body; streaming carries it on the first chunk. |
| [A-080](assumptions/A-080.md) | gateway | active | agent | none | The resolution cache is a bounded TTL-only LRU with a 5-minute stale-if-error window (ADR-0012). |
| [A-081](assumptions/A-081.md) | global | active | agent | [OQ-006](open_questions/OQ-006.md) | Consumer API keys belong to access-control; a key is default-deny and names the models it may resolve. |
| [A-082](assumptions/A-082.md) | gateway | active | agent | none | `GET /v1/models` lists only prompts with a current release that the key may resolve. |
| [A-083](assumptions/A-083.md) | gateway | active | agent | none | Usage is requested upstream unconditionally and the gateway strips the extra chunk; missing usage is unknown, never estimated (the forcing moved to provider-access 2026-08-08 — A-089). |
| [A-084](assumptions/A-084.md) | gateway | active | agent | [OQ-012](open_questions/OQ-012.md) | The gateway does not retry upstream; it sets one deadline. |
| [A-085](assumptions/A-085.md) | gateway | active | agent | none | A fallback is only reachable before the first byte; after that a failure truncates honestly (ADR-0013). |
| [A-086](assumptions/A-086.md) | gateway | active | agent | none | An authenticated call that is refused still writes a call record; an unauthenticated one does not. |
| [A-087](assumptions/A-087.md) | gateway | active | agent | none | The gateway enqueues after the response is flushed; the buffer and spill belong to call-ledger. |
| [A-088](assumptions/A-088.md) | provider-access | active | agent | none | A dispatch is exactly one attempt; the retry policy belongs to the caller. |
| [A-089](assumptions/A-089.md) | global | active | agent | none | provider-access always requests usage from the provider; it is never a caller option (amends A-083 and ADR-0013). |
| [A-090](assumptions/A-090.md) | provider-access | active | agent | none | A provider configuration is verified by a live probe before it can be bound to a revision. |
| [A-091](assumptions/A-091.md) | provider-access | active | agent | none | The model catalogue is discovered from the provider, refreshable, manually extensible, and holds no prices. |
| [A-092](assumptions/A-092.md) | provider-access | active | agent | none | Decrypted credentials live only in a 60 s process-local cache; a rotation is effective within 60 s. |
| [A-093](assumptions/A-093.md) | global | active | agent | none | A dispatch carries a priority class, and batch yields to interactive at the provider seam (ADR-0016). |
| [A-094](assumptions/A-094.md) | provider-access | active | human | [OQ-016](open_questions/OQ-016.md) | The MVP ships one adapter kind, OpenAI-compatible with a configurable base URL; a second adapter is post-MVP (confirmed 2026-08-08). |
| [A-095](assumptions/A-095.md) | global | active | agent | none | Every upstream failure carries class, origin, fallback_eligible, and retryable as four separate facts. |
| [A-096](assumptions/A-096.md) | provider-access | active | agent | none | A provider configuration is disabled, never silently deleted; deletion is refused while a revision binds it. |
| [A-097](assumptions/A-097.md) | global | active | agent | none | Generation parameters pass through verbatim; a parameter the provider rejects is a revision defect, not an upstream failure. |
| [A-098](assumptions/A-098.md) | call-ledger | active | agent | none | One call_record table with source = gateway \| eval; one price path and one spend total; bodies only for gateway. |
| [A-099](assumptions/A-099.md) | global | active | agent | none | The call_id is generated by the caller and the writer upserts on it, so a spill replay cannot double-count spend. |
| [A-100](assumptions/A-100.md) | call-ledger | active | agent | none | Cost is priced once at write time and stored with the price row that produced it (ADR-0019). |
| [A-101](assumptions/A-101.md) | global | active | agent | none | A missing price is unpriced and a missing usage object is unknown; neither is ever zero. |
| [A-102](assumptions/A-102.md) | call-ledger | active | agent | none | The price table is append-only and effective-dated, and is this module's audit trail; no property-history event is written. |
| [A-103](assumptions/A-103.md) | call-ledger | active | agent | none | The monthly spend total is an aggregate row updated in the writer's transaction. |
| [A-104](assumptions/A-104.md) | call-ledger | active | agent | none | check_spend_ceiling fails open, and counts the failure. |
| [A-105](assumptions/A-105.md) | call-ledger | active | agent | [OQ-013](open_questions/OQ-013.md) | Stored bodies have no read path in the MVP (ADR-0018). |
| [A-106](assumptions/A-106.md) | call-ledger | active | agent | [OQ-013](open_questions/OQ-013.md) | Retention is a per-workspace setting with expires_at stamped at write time; the alert measures the oldest body, not job success. |
| [A-107](assumptions/A-107.md) | call-ledger | active | agent | none | A price row carries an explicit currency; a workspace uses one currency and there is no conversion in the MVP. |
| [A-108](assumptions/A-108.md) | global | active | **human** | [OQ-006](open_questions/OQ-006.md) | People sign in with email and password against Prope's own user table, with server-side sessions; no SSO in the MVP (**confirmed by the user 2026-08-09**; ADR-0029 — this closes the sole reason access-control scored `Estimable: no`). |
| [A-109](assumptions/A-109.md) | global | active | agent | none | The `workspace` table belongs to access-control; it is the tenancy root every workspace_id refers to. |
| [A-110](assumptions/A-110.md) | access-control | active | agent | none | A person joins a workspace by an Admin creating the account; there are no invitations, because there is no email (A-071). |
| [A-111](assumptions/A-111.md) | global | active | agent | none | Effective permission is the union of role bindings and per-prompt grants; there are no negative grants. |
| [A-112](assumptions/A-112.md) | access-control | active | agent | [OQ-006](open_questions/OQ-006.md) | A prompt grant carries a level, viewer or editor; no grant confers approve, release, withdraw, or break-glass. |
| [A-113](assumptions/A-113.md) | global | active | agent | none | A consumer API key is `prope_<key_id>_<secret>`, stored as a fast hash and shown once; passwords use argon2id (ADR-0021). |
| [A-114](assumptions/A-114.md) | global | active | agent | none | Nothing in access-control is cached, by this module or by its callers; revocation is immediate (ADR-0022). |
| [A-115](assumptions/A-115.md) | global | active | agent | none | The action vocabulary is a closed enumerated list, and an unknown action is denied rather than errored or allowed. |
| [A-116](assumptions/A-116.md) | global | active | agent | none | Not-found when the actor cannot see the subject; forbidden naming the permission when they can. |
| [A-117](assumptions/A-117.md) | access-control | active | agent | none | A workspace always has at least one Admin, and the last one cannot be removed or demoted. |
| [A-118](assumptions/A-118.md) | global | active | agent | none | Access-control exposes a set form beside may(), so list endpoints filter in SQL rather than per row. |
| [A-119](assumptions/A-119.md) | global | active | agent | none | Every history event carries a nullable `scope_prompt_id`, so a property's Activity is one indexed read. |
| [A-120](assumptions/A-120.md) | global | active | agent | none | Event action names are `<target_type>_<past participle>`; the vocabulary is closed at 30, and release-control's six bare verbs are renamed. |
| [A-121](assumptions/A-121.md) | global | active | agent | none | History events are never deleted and never expire; there is no retention setting. |
| [A-122](assumptions/A-122.md) | property-history | active | agent | none | The event's target is `(target_type, target_id)` with no foreign key. |
| [A-123](assumptions/A-123.md) | property-history | active | agent | none | property-history mounts no HTTP route; its read API takes an already-authorised scope. |
| [A-124](assumptions/A-124.md) | global | active | agent | none | The `details` payload is validated at append time against a per-action key allow-list. |
| [A-125](assumptions/A-125.md) | property-history | active | agent | none | Event order is a monotonic sequence, not a timestamp. |
| [A-126](assumptions/A-126.md) | property-history | active | agent | none | The two audit-event Success metrics are hand-run SQL at pilot review, not product surfaces. |
| [A-127](assumptions/A-127.md) | global | active | agent | none | LangChain and LangGraph are removed; nothing in Prope is a graph. |
| [A-128](assumptions/A-128.md) | global | active | agent | none | SQLAlchemy 2.0 async + Alembic + asyncpg; raw SQL for the gateway resolve read and A-118's set filter. |
| [A-129](assumptions/A-129.md) | global | active | agent | none | Caddy is the single ingress and terminates TLS; no other container publishes a port to the host. |
| [A-130](assumptions/A-130.md) | global | active | agent | none | The gateway shares a process with the UI for now; the split trigger is the p95 histogram, not a judgement. |
| [A-131](assumptions/A-131.md) | global | active | agent | none | The backup destination is a second group-controlled machine — and there may not be one yet; object storage is excluded on residency. |
| [A-132](assumptions/A-132.md) | call-ledger | active | agent | none | `call_body` is not partitioned; retention stays a chunked DELETE, with a numeric revisit trigger. |
| [A-133](assumptions/A-133.md) | access-control | active | agent | OQ-006 | A restore un-revokes keys, grants, bindings and memberships inside the RPO — and the history events recording them roll back too, so nothing inside Prope can reconstruct what was lost. |
| [A-134](assumptions/A-134.md) | provider-access | active | agent | OQ-012 | `interactive_concurrency` 24 and `batch_concurrency` 8 are placeholders against no real provider quota, and must be tuned as a sum. |
| [A-135](assumptions/A-135.md) | provider-access | active | agent | OQ-006 | `.env` may hold several `PROPE_KEK_V<n>`; `kek_version` selects, and a rotation re-wraps every `wrapped_dek` without touching a plaintext credential. |
| [A-136](assumptions/A-136.md) | prompt-registry | active | agent | OQ-006 | A restore loses up to 24 h of prompt text, and the `revision_created` events prove exactly which revisions were lost without recovering a character of them. |
| [A-137](assumptions/A-137.md) | evaluation | active | agent | OQ-013 | `case_result` is the second unbounded table and the only one with no delete path at all; it stays in the dump because the counts live on the parent and the evidence lives on it. |
| [A-138](assumptions/A-138.md) | global | active | agent | OQ-012 | Nothing bounds `worker` across workspaces — accepted for the pilot; ADR-0049's bound survives replication and ADR-0046's does not, so the cap comes before the replica. |
| [A-139](assumptions/A-139.md) | gateway | active | agent | none | A gateway process hard-killed between response flush and publish loses that call record and nothing counts it — the one gap in "100% of calls record a version ID" the instrumentation cannot see. |
| [A-140](assumptions/A-140.md) | release-control | active | agent | [OQ-012](open_questions/OQ-012.md) | The cross-tenant sweep is N+1 transactions per pass, unbounded in workspace count — and a stale gauge is indistinguishable from a healthy one. |
| [A-141](assumptions/A-141.md) | global | active | agent | [OQ-005](open_questions/OQ-005.md) | The SPA is Prope's first long-lived client of its own API — a tab open across a deploy runs the old bundle against the new API, which server rendering made impossible. |
| [A-142](assumptions/A-142.md) | global | active | agent | none | Global interface conventions: an in-process seam is a Python call in the caller's own container and RAISES unless recorded otherwise; `/api/v1` is frozen; one broker envelope, additive-only; no idempotency key. |
| [A-143](assumptions/A-143.md) | gateway | active | user | [OQ-012](open_questions/OQ-012.md) | The gateway admits at most 20 concurrent calls per consumer key and refuses the rest with an OpenAI-shaped 429 — in-flight, not RPS, because that is what actually exhausts the host. |
| [A-144](assumptions/A-144.md) | access-control | active | user | none | The login limiter is 5 failures per email and 20 per source address in a rolling 15 minutes, and a limited attempt is indistinguishable from a wrong password. |
| [A-145](assumptions/A-145.md) | global | active | agent | [OQ-013](open_questions/OQ-013.md) | Retention for all 27 owned tables. ADR-0033 said exactly one unbounded term and A-137 corrected it to two; it is **four** — `call_body` (has a delete path), `call_record` and `case_result` (none), `history_event` (never, by design). |
| [A-146](assumptions/A-146.md) | global | active | agent | none | PII per column: only `access.user.email` and `display_name` directly identify a person. No column-level encryption is added — `credential` stays the sole exception, and prompt bodies stay unencrypted at rest, as the user already decided. |
| [A-147](assumptions/A-147.md) | global | active | agent | none | The threats the step-6 STRIDE pass scored medium or low and accepted, each against a stated condition — plus the two things the pass expected to find and did not. |
| [A-148](assumptions/A-148.md) | gateway | active | agent | none | Inbound bodies are bounded: Caddy refuses over 1 MiB on every route, the gateway refuses a composed message set over 256 KiB with an OpenAI-shaped 400. Nothing bounded them before. |
| [A-149](assumptions/A-149.md) | call-ledger | active | agent | [OQ-013](open_questions/OQ-013.md) | The broker is a second body store: `prope.call_record` gets a 24 h TTL, its DLQ a 30-day TTL matching `call_body`, and any non-zero DLQ depth is an alert — ADR-0039's argument applied to the transport channel. |
| [A-150](assumptions/A-150.md) | prompt-registry | active | agent | [OQ-010](open_questions/OQ-010.md) | Registry search folds diacritics and case **inside the `search_text` trigger**, not in the index expression — `unaccent()` is STABLE, so an index expression needs a wrapper marked IMMUTABLE that is not. Consequence of the Vietnamese UI decision (ADR-0053) landing on ADR-0048. |
| [A-151](assumptions/A-151.md) | access-control | active | agent | [OQ-017](open_questions/OQ-017.md) | What a tombstone does field by field: identity columns NULL, sessions deleted, role bindings and grants removed, **memberships retained**, **API keys untouched**, one `user_tombstoned` event per workspace with no details and no reason, and a re-apply step in the recovery runbook because a tombstone does not reach the backups. |
| [A-152](assumptions/A-152.md) | release-control | active | human | none | Canary temporarily routes a stable percentage of conversations to an Approved candidate; missing conversation IDs stay on baseline and promotion remains human. |
| [A-153](assumptions/A-153.md) | call-ledger | active | human | [OQ-013](open_questions/OQ-013.md) | Opt-in labeling may read redacted retained call bodies behind a dedicated permission and audit trail; PropAI cannot auto-write or release from labels. |
