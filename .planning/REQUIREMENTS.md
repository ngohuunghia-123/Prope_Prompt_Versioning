# Requirements: Prope

**Defined:** 2026-08-09
**Source:** `docs/build/gsd_handoff.md` section 6 (bsp-gsd/1) — adopted verbatim, not derived
**Core Value:** No prompt reaches production without a recorded human approval, and every call can be traced back to the exact revision that served it

> **89 requirements. One per acceptance criterion, one acceptance criterion per requirement.**
> Nothing here was invented. Ids are stable references that the module lock files, the phases, and
> later verification all point at — **do not renumber, re-prefix, or re-group them.**
>
> Category = module title, so requirement grouping and milestone grouping stay aligned.
>
> **Two prefixes look alike and are not.** `AC-01`…`AC-15` (zero-padded) are **access-control's
> requirement ids** below. `AC-1`…`AC-15` (unpadded, always written with their module name) are
> **acceptance-criterion ids inside a lock file**. The traceability table always names the module, so
> the two never collide in practice.

## v1 Requirements

### Call Ledger

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

### Property History

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

### Access Control

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

### Provider Access

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

### Prompt Registry

- [ ] **PR-01**: Editing a prompt creates the next immutable revision with author and timestamp, leaving every earlier revision byte-identical
- [ ] **PR-02**: A reviewer sees a line-level body diff plus a field-level comparison of provider, upstream model, parameters, and fallback answer, rendered under 300 ms with both bodies at the 32 KiB cap
- [ ] **PR-03**: A private prompt is absent from another person's search results, and a direct fetch by its id returns the same not-found as a nonexistent id
- [ ] **PR-04**: The gateway resolves a bare model name to the released revision's full binding at p95 under 10 ms
- [ ] **PR-05**: Retiring a prompt with an active release is refused with a message naming the release, and the prompt's status is unchanged
- [ ] **PR-06**: The database rejects any attempt to point the released pointer at a revision that is not Approved

### Evaluation

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

### Gateway

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

### Release Control

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

## v2 Requirements

None. All eight modules are `ready_for_build: true` and no requirement is blocked.

## Out of Scope

Explicitly excluded upstream, from the handoff's section 1.

| Feature | Reason |
|---------|--------|
| Import/ingestion from repos, Sheets, Notion, Drive, chat exports | The root problem is lost ownership and provenance, not the absence of somewhere to save text |
| Similar-prompt clustering | Same reason — solving discovery by similarity does not restore ownership |
| Traces, spans, trace explorer, analytics dashboards, sampling policy | This is the observability product; integrate with Langfuse, do not compete |
| Environment aliases beyond one released pointer | One released revision per prompt is the whole model |
| Multi-region or multi-tenant routing | One VM, one failure domain, accepted at pilot scale (ADR-0033) |
| OpenAI endpoints beyond chat completions and `/v1/models` | A-094 — OpenAI-compatible is the whole MVP |
| Multi-level approval, configurable policy engine, scheduled drift monitoring | One recorded decision is the MVP; a policy engine is a v2 shape |
| Individual mode | Prope is a workspace product; a single-user mode has no approval step to record |
| LLM-judge quality scoring | Deterministic assertions only; a judge introduces the non-determinism the eval exists to remove |
| Semantic/vector search | ADR-0048 — trigram over a trigger-maintained document column; substring semantics are asserted |

**Anti-goals** — things Prope deliberately will not become:

| Anti-goal | Reason |
|-----------|--------|
| The observability product | Integrate with Langfuse, do not compete |
| A prompt marketplace or public template library | Not the problem being solved |
| A chat or playground surface | Not the problem being solved |
| **Auto-release of any kind** | The first non-negotiable; break-glass is the declared, counted exception |
| An agent that autonomously rewrites prompts or fallback answers and puts them in front of users | A human must accept the revision |
| Any claim that Prope establishes legal IP ownership | Not true, and cannot be made true by the product |
| Any claim that the eval suite guarantees no quality degradation | Not true; the eval is a compensating control, not a guarantee |

## Traceability

Adopted from the handoff's traceability table. Five columns, not two: each requirement maps to its milestone, phase, lock file, and the acceptance criterion it *is*.

| Requirement | Milestone | Phase | Spec | Traces to | Status |
|-------------|-----------|-------|------|-----------|--------|
| CL-03 | M1 | Phase 1 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-3 | Pending |
| CL-04 | M1 | Phase 1 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-4 | Pending |
| CL-05 | M1 | Phase 1 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-5 | Pending |
| CL-08 | M1 | Phase 1 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-8 | Pending |
| CL-11 | M1 | Phase 1 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-11 | Pending |
| CL-06 | M1 | Phase 2 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-6 | Pending |
| CL-09 | M1 | Phase 2 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-9 | Pending |
| CL-01 | M1 | Phase 3 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-1 | Pending |
| CL-02 | M1 | Phase 3 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-2 | Pending |
| CL-07 | M1 | Phase 3 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-7 | Pending |
| CL-10 | M1 | Phase 3 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-10 | Pending |
| CL-12 | M1 | Phase 3 | `docs/modules/call-ledger.lock.yml` | call-ledger AC-12 | Pending |
| PH-02 | M2 | Phase 4 | `docs/modules/property-history.lock.yml` | property-history AC-2 | Pending |
| PH-04 | M2 | Phase 4 | `docs/modules/property-history.lock.yml` | property-history AC-4 | Pending |
| PH-05 | M2 | Phase 4 | `docs/modules/property-history.lock.yml` | property-history AC-5 | Pending |
| PH-03 | M2 | Phase 5 | `docs/modules/property-history.lock.yml` | property-history AC-3 | Pending |
| PH-06 | M2 | Phase 5 | `docs/modules/property-history.lock.yml` | property-history AC-6 | Pending |
| PH-01 | M2 | Phase 6 | `docs/modules/property-history.lock.yml` | property-history AC-1 | Pending |
| PH-07 | M2 | Phase 6 | `docs/modules/property-history.lock.yml` | property-history AC-7 | Pending |
| PH-08 | M2 | Phase 6 | `docs/modules/property-history.lock.yml` | property-history AC-8 | Pending |
| PH-09 | M2 | Phase 6 | `docs/modules/property-history.lock.yml` | property-history AC-9 | Pending |
| PH-10 | M2 | Phase 6 | `docs/modules/property-history.lock.yml` | property-history AC-10 | Pending |
| AC-03 | M3 | Phase 7 | `docs/modules/access-control.lock.yml` | access-control AC-3 | Pending |
| AC-04 | M3 | Phase 7 | `docs/modules/access-control.lock.yml` | access-control AC-4 | Pending |
| AC-08 | M3 | Phase 7 | `docs/modules/access-control.lock.yml` | access-control AC-8 | Pending |
| AC-13 | M3 | Phase 7 | `docs/modules/access-control.lock.yml` | access-control AC-13 | Pending |
| AC-09 | M3 | Phase 8 | `docs/modules/access-control.lock.yml` | access-control AC-9 | Pending |
| AC-10 | M3 | Phase 8 | `docs/modules/access-control.lock.yml` | access-control AC-10 | Pending |
| AC-12 | M3 | Phase 8 | `docs/modules/access-control.lock.yml` | access-control AC-12 | Pending |
| AC-14 | M3 | Phase 8 | `docs/modules/access-control.lock.yml` | access-control AC-14 | Pending |
| AC-01 | M3 | Phase 9 | `docs/modules/access-control.lock.yml` | access-control AC-1 | Pending |
| AC-02 | M3 | Phase 9 | `docs/modules/access-control.lock.yml` | access-control AC-2 | Pending |
| AC-05 | M3 | Phase 9 | `docs/modules/access-control.lock.yml` | access-control AC-5 | Pending |
| AC-06 | M3 | Phase 9 | `docs/modules/access-control.lock.yml` | access-control AC-6 | Pending |
| AC-07 | M3 | Phase 9 | `docs/modules/access-control.lock.yml` | access-control AC-7 | Pending |
| AC-11 | M3 | Phase 9 | `docs/modules/access-control.lock.yml` | access-control AC-11 | Pending |
| AC-15 | M3 | Phase 9 | `docs/modules/access-control.lock.yml` | access-control AC-15 | Pending |
| PA-02 | M4 | Phase 10 | `docs/modules/provider-access.lock.yml` | provider-access AC-2 | Pending |
| PA-03 | M4 | Phase 10 | `docs/modules/provider-access.lock.yml` | provider-access AC-3 | Pending |
| PA-05 | M4 | Phase 10 | `docs/modules/provider-access.lock.yml` | provider-access AC-5 | Pending |
| PA-04 | M4 | Phase 11 | `docs/modules/provider-access.lock.yml` | provider-access AC-4 | Pending |
| PA-06 | M4 | Phase 11 | `docs/modules/provider-access.lock.yml` | provider-access AC-6 | Pending |
| PA-07 | M4 | Phase 11 | `docs/modules/provider-access.lock.yml` | provider-access AC-7 | Pending |
| PA-08 | M4 | Phase 11 | `docs/modules/provider-access.lock.yml` | provider-access AC-8 | Pending |
| PA-09 | M4 | Phase 11 | `docs/modules/provider-access.lock.yml` | provider-access AC-9 | Pending |
| PA-10 | M4 | Phase 11 | `docs/modules/provider-access.lock.yml` | provider-access AC-10 | Pending |
| PA-01 | M4 | Phase 12 | `docs/modules/provider-access.lock.yml` | provider-access AC-1 | Pending |
| PA-11 | M4 | Phase 12 | `docs/modules/provider-access.lock.yml` | provider-access AC-11 | Pending |
| PA-12 | M4 | Phase 12 | `docs/modules/provider-access.lock.yml` | provider-access AC-12 | Pending |
| PR-01 | M5 | Phase 13 | `docs/modules/prompt-registry.lock.yml` | prompt-registry AC-1 | Pending |
| PR-02 | M5 | Phase 13 | `docs/modules/prompt-registry.lock.yml` | prompt-registry AC-2 | Pending |
| PR-05 | M5 | Phase 13 | `docs/modules/prompt-registry.lock.yml` | prompt-registry AC-5 | Pending |
| PR-06 | M5 | Phase 13 | `docs/modules/prompt-registry.lock.yml` | prompt-registry AC-6 | Pending |
| PR-04 | M5 | Phase 14 | `docs/modules/prompt-registry.lock.yml` | prompt-registry AC-4 | Pending |
| PR-03 | M5 | Phase 15 | `docs/modules/prompt-registry.lock.yml` | prompt-registry AC-3 | Pending |
| EVAL-02 | M6 | Phase 16 | `docs/modules/evaluation.lock.yml` | evaluation AC-2 | Pending |
| EVAL-03 | M6 | Phase 16 | `docs/modules/evaluation.lock.yml` | evaluation AC-3 | Pending |
| EVAL-04 | M6 | Phase 16 | `docs/modules/evaluation.lock.yml` | evaluation AC-4 | Pending |
| EVAL-09 | M6 | Phase 16 | `docs/modules/evaluation.lock.yml` | evaluation AC-9 | Pending |
| EVAL-01 | M6 | Phase 17 | `docs/modules/evaluation.lock.yml` | evaluation AC-1 | Pending |
| EVAL-05 | M6 | Phase 17 | `docs/modules/evaluation.lock.yml` | evaluation AC-5 | Pending |
| EVAL-08 | M6 | Phase 17 | `docs/modules/evaluation.lock.yml` | evaluation AC-8 | Pending |
| EVAL-06 | M6 | Phase 18 | `docs/modules/evaluation.lock.yml` | evaluation AC-6 | Pending |
| EVAL-07 | M6 | Phase 18 | `docs/modules/evaluation.lock.yml` | evaluation AC-7 | Pending |
| EVAL-10 | M6 | Phase 18 | `docs/modules/evaluation.lock.yml` | evaluation AC-10 | Pending |
| GATE-02 | M7 | Phase 19 | `docs/modules/gateway.lock.yml` | gateway AC-2 | Pending |
| GATE-03 | M7 | Phase 19 | `docs/modules/gateway.lock.yml` | gateway AC-3 | Pending |
| GATE-04 | M7 | Phase 19 | `docs/modules/gateway.lock.yml` | gateway AC-4 | Pending |
| GATE-05 | M7 | Phase 19 | `docs/modules/gateway.lock.yml` | gateway AC-5 | Pending |
| GATE-07 | M7 | Phase 19 | `docs/modules/gateway.lock.yml` | gateway AC-7 | Pending |
| GATE-08 | M7 | Phase 19 | `docs/modules/gateway.lock.yml` | gateway AC-8 | Pending |
| GATE-01 | M7 | Phase 20 | `docs/modules/gateway.lock.yml` | gateway AC-1 | Pending |
| GATE-10 | M7 | Phase 20 | `docs/modules/gateway.lock.yml` | gateway AC-10 | Pending |
| GATE-12 | M7 | Phase 20 | `docs/modules/gateway.lock.yml` | gateway AC-12 | Pending |
| GATE-06 | M7 | Phase 21 | `docs/modules/gateway.lock.yml` | gateway AC-6 | Pending |
| GATE-09 | M7 | Phase 21 | `docs/modules/gateway.lock.yml` | gateway AC-9 | Pending |
| GATE-11 | M7 | Phase 21 | `docs/modules/gateway.lock.yml` | gateway AC-11 | Pending |
| RC-02 | M8 | Phase 22 | `docs/modules/release-control.lock.yml` | release-control AC-2 | Pending |
| RC-08 | M8 | Phase 22 | `docs/modules/release-control.lock.yml` | release-control AC-8 | Pending |
| RC-09 | M8 | Phase 22 | `docs/modules/release-control.lock.yml` | release-control AC-9 | Pending |
| RC-11 | M8 | Phase 22 | `docs/modules/release-control.lock.yml` | release-control AC-11 | Pending |
| RC-01 | M8 | Phase 23 | `docs/modules/release-control.lock.yml` | release-control AC-1 | Pending |
| RC-03 | M8 | Phase 23 | `docs/modules/release-control.lock.yml` | release-control AC-3 | Pending |
| RC-04 | M8 | Phase 23 | `docs/modules/release-control.lock.yml` | release-control AC-4 | Pending |
| RC-12 | M8 | Phase 23 | `docs/modules/release-control.lock.yml` | release-control AC-12 | Pending |
| RC-05 | M8 | Phase 24 | `docs/modules/release-control.lock.yml` | release-control AC-5 | Pending |
| RC-06 | M8 | Phase 24 | `docs/modules/release-control.lock.yml` | release-control AC-6 | Pending |
| RC-07 | M8 | Phase 24 | `docs/modules/release-control.lock.yml` | release-control AC-7 | Pending |
| RC-10 | M8 | Phase 24 | `docs/modules/release-control.lock.yml` | release-control AC-10 | Pending |

**Coverage:**
- v1 requirements: 89 total
- Mapped to phases: 89
- Unmapped: 0 ✓
- Phases with no requirement: 0 ✓ (all 24 covered)

## Obligations with no requirement

Sixteen acceptance criteria are owed by the lock files but were never written as rows, and eight more assert against infrastructure that a later decision replaced. **None is promoted into a requirement here** — doing so would silently expand scope. They are catalogued with the phase that should absorb each in `.planning/research/PITFALLS.md`, coverage gaps 1 and 2. The React SPA (gap 3) and the deployment stack (gap 4) own no milestone at all and need a user decision before the pilot.

---
*Requirements defined: 2026-08-09*
*Last updated: 2026-08-09 — adopted verbatim from `docs/build/gsd_handoff.md` section 6*
