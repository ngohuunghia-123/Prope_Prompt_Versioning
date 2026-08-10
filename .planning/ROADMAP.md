# Roadmap: Prope

> Transcribed from `docs/build/gsd_handoff.md` section 7 (bsp-gsd/1). **Adopted, not derived.**
> Phase boundaries come from the dependency graph and the lock files, both settled upstream.
> **Phase numbering is continuous across the whole project and never restarts inside a milestone** —
> the module task lists, the requirement traceability, and `.planning/BSP-LINK.md` all cite these
> numbers. Renumbering breaks every one of them at once.

## Overview

Eight milestones, one per module, ordered by dependency wave then alphabetically within a wave. 24 phases numbered continuously 1–24. Granularity is **coarse**: each module collapses the seven-phase spine into three — `A+B` (data model and core logic), `C+D` (exposed and consumed seams), `E+F+G` (resilience, observability and security, acceptance closeout).

The journey runs from two independent sinks and ledgers, through the permission oracle and the only module that talks to the outside world, into the registry that holds every prompt, and ends at the module that makes "0/11 teams have any approval step" false.

**Critical path**: property-history → access-control → provider-access → prompt-registry → evaluation → release-control. Six waves.

**Parallelism**: M1 (call-ledger) and M2 (property-history) have no upstream dependencies and may run in parallel from day one. M6 (evaluation) and M7 (gateway) are both wave 4 and may run in parallel once M5 and M1 are done.

## Milestones

- 📋 **M1 Call Ledger** — Phases 1–3 *(wave 0)* — planned
- 📋 **M2 Property History** — Phases 4–6 *(wave 0)* — planned
- 📋 **M3 Access Control** — Phases 7–9 *(wave 1)* — planned
- 📋 **M4 Provider Access** — Phases 10–12 *(wave 2)* — planned
- 📋 **M5 Prompt Registry** — Phases 13–15 *(wave 3)* — planned
- 📋 **M6 Evaluation** — Phases 16–18 *(wave 4)* — planned
- 📋 **M7 Gateway** — Phases 19–21 *(wave 4, parallel with M6)* — planned
- 📋 **M8 Release Control** — Phases 22–24 *(wave 5)* — planned

## Phases

- [ ] **Phase 1: Data model, pricing, and retention** - The `ledger` schema and irreversible write-time pricing
- [ ] **Phase 2: Seams: enqueue, the broker drain, and the ceiling** - Three internal contracts, six routes, the worker drain
- [ ] **Phase 3: Durability, idempotency, and no-read-path** - Metadata survives every failure; no surface reads a body
- [ ] **Phase 4: Schema, privilege, ordering, and the closed vocabulary** - Append-only as a database privilege
- [ ] **Phase 5: The three functions five modules build against** - `append()`, `read()`, `registered_actions()`
- [ ] **Phase 6: Atomicity, no route, no content, no deletion** - The four guarantees asserted rather than intended
- [ ] **Phase 7: Schema, identity, and the permission decision** - Eight `access` tables, argon2id sign-in, `may()`
- [ ] **Phase 8: Seams: five internal functions and fifteen routes** - What six modules build against
- [ ] **Phase 9: Failing closed, refusal shapes, and the login path** - Refusals leak nothing; revocation is immediate
- [ ] **Phase 10: Schema, envelope encryption, verification, and classification** - Credentials at rest, providers probed live
- [ ] **Phase 11: Seams: dispatch, the upstream provider, and the dashboard** - The one external HTTP seam
- [ ] **Phase 12: The credential never leaves, and the KEK is a readiness gate** - SSRF closed at save and dispatch
- [ ] **Phase 13: Schema, immutability, the constraint, the trigger, and the diff** - The Approved-only rule as a DB constraint
- [ ] **Phase 14: Seams: ten routes, five internal calls, three inbound commands** - The gateway's hot read
- [ ] **Phase 15: Private by default, the tripwire, and the `search_text` leak** - Private-by-default through every read path
- [ ] **Phase 16: Schema, suite versioning, assertions, and the run lifecycle** - Suites version independently; the claim loop
- [ ] **Phase 17: Seams: nine routes, the review summary, and four consumed modules** - The evidence a reviewer decides on
- [ ] **Phase 18: The sweeper, the bounds, and result privacy** - A dead worker cannot strand a run
- [ ] **Phase 19: Resolution, composition, and the fallback decision** - The 30 s cache and the first-byte boundary
- [ ] **Phase 20: Seams: `/v1`, four consumed modules, and the admission cap** - Wire-compatible, per-key authenticated
- [ ] **Phase 21: Streaming failure, the TTL, and staying off the response path** - The two hardest properties in the build
- [ ] **Phase 22: Schema, the decision state machine, and the evidence digest** - Break-glass and its follow-up task
- [ ] **Phase 23: Seams: eleven routes, three registry commands, one evaluation pull** - Every decision surface
- [ ] **Phase 24: Conflicts, degraded evidence, and the end-to-end journeys** - Restore and withdraw demonstrated end to end

## Phase Details

### 📋 M1 Call Ledger (Planned)

**Milestone Goal:** Store every completed call off the response path, price its usage against an effective-dated table, and answer whether a workspace has hit its spend ceiling. This module is a sink: nothing it does may reach back into a module that is serving a request.

**Module:** `call-ledger` · **Spec:** `docs/modules/call-ledger.lock.yml` · **Wave:** 0

#### Phase 1: Data model, pricing, and retention

**Goal**: The `ledger` schema exists with all five tables, and a call's usage is priced correctly and irreversibly at write time.
**Depends on**: Nothing. This is a project entry point.
**Requirements**: CL-03, CL-04, CL-05, CL-08, CL-11
**Success Criteria** (what must be TRUE):

  1. A call made on day 5 and written on day 12 is priced at the day-5 price row, and adding a day-20 price does not move it.
  2. A call with no price row stores its tokens with `cost_status = unpriced` and appears on the unpriced worklist; no row anywhere records a cost of zero.
  3. A call whose provider returned no usage object stores null token counts with `usage_status = unknown`, never zeros.
  4. Bodies older than the retention window are gone by any query while their call records remain.

**Spec**: `docs/modules/call-ledger.lock.yml` — `data.owns` (`call_record`, `call_body`, `price_table`, `workspace_spend`, `spend_ceiling`), `scope.in_scope` (pricing at write time, the append-only effective-dated price table, the batched deletion job), `non_goals` (no estimation, no currency conversion). Also ADR-0019, ADR-0039, ADR-0040, ADR-0045.
**Plans**: 4/4 plans executed in 4 waves
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Toolchain, Docker, and the tenant-isolation tracer: roles, `ledger` schema, `call_record` with its CHECKs/policy/grants, `workspace_transaction()`, the testcontainers rig

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — The remaining four tables, the T-006 append-only REVOKEs, and the live-engine guarantee suite (privilege, eight-schema tenancy coverage, schema invariants, migration chain)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Effective-dated pricing, exact-decimal cost, and `write_records`: the three cost states as real rows (CL-03, CL-04, CL-11)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — Repricing only what was never priced (CL-05) and the bounded-chunk body retention delete (CL-08)

#### Phase 2: Seams: enqueue, the broker drain, and the ceiling

**Goal**: The three internal contracts and the six management routes exist, and the `worker`'s drain consumes `prope.call_record` and writes batches grouped per workspace.
**Depends on**: Phase 1
**Requirements**: CL-06, CL-09
**Success Criteria** (what must be TRUE):

  1. `check_spend_ceiling` refuses an eval run for a workspace over its ceiling with a reason and no figure, while gateway traffic for the same workspace continues to be recorded.
  2. An eval-case usage row arrives with `source = eval`, `run_id` and `version_id`, is priced, counts toward the workspace's monthly spend, and creates no `call_body` row.
  3. `get_run_totals` returns the unpriced and unknown-usage counts alongside the totals.

**Spec**: `docs/modules/call-ledger.lock.yml` — `apis.exposes` (`enqueue`, `check_spend_ceiling`, `get_run_totals`, `/api/v1/prices`, `/prices/unpriced`, `/spend-ceiling`, `/retention`, `/healthz`, `/readyz`), `events.subscribes` (queue `prope.call_record`), `apis.consumes` (empty — this module is a sink). Seams INT-018, INT-019, INT-020, INT-021, INT-028. Also ADR-0028, ADR-0040, ADR-0041.
**Plans**: 5/5 plans executed

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Tracer: one call record from `enqueue()` through the broker to a committed ledger row, plus the queue's declared arguments, the three publish-failure reasons, and the drain's failure classification (wave 1)
- [x] 02-02-PLAN.md — Migration `0004` and `ledger.workspace_retention`, the retention read and write, and the three Phase 1 findings that go live with a drain (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-03-PLAN.md — `worker`: the `asyncio.TaskGroup` supervisor, the drain job with the real retention resolver, and the retention job's scheduler (wave 2)
- [x] 02-04-PLAN.md — The three internal seams: `price_usage`, `check_spend_ceiling`, `get_run_totals` — all three phase success criteria (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-05-PLAN.md — `app`: INT-028's five `/api/v1` routes plus INT-030's `/healthz` and `/readyz` — seven paths in the assembled route table — and the declared session boundary (wave 3)

#### Phase 3: Durability, idempotency, and no-read-path

**Goal**: Metadata survives every failure mode, a redelivery cannot move a workspace's spend, and no surface anywhere can read a stored body.
**Depends on**: Phase 2
**Requirements**: CL-01, CL-02, CL-07, CL-10, CL-12
**Success Criteria** (what must be TRUE):

  1. With RabbitMQ unreachable, 1,000 calls each still produce a durable record with a non-null `version_id` through the direct-write fallback; only bodies are dropped and every drop is counted.
  2. Every message redelivered after an unacknowledged consumer restart lands exactly once; the workspace's monthly total is unchanged and every redelivery is counted.
  3. A ceiling check that cannot be evaluated returns allowed, increments the failed-open counter, and does not raise into evaluation.
  4. Enumerating the module's entire HTTP and internal surface finds no route, parameter, or function that returns a request or response body.
  5. At 50 rps sustained for 10 minutes, `enqueue` p95 stays under 1 ms in the caller's process and no metadata is dropped.

**Spec**: `docs/modules/call-ledger.lock.yml` — `failure_modes` (all 8 rows), `observability_requirements.metrics` (17 metrics incl. `body_dropped_total`, `metadata_dropped_total`, `fallback_direct_write_total`, `duplicate_call_id_total`, `missing_version_id_total`), `security_requirements`, `test_plan` (unit / integration / contract / load / security / chaos), `acceptance_criteria`. Also ADR-0018, ADR-0041.
**Plans**: TBD

---

### 📋 M2 Property History (Planned)

**Milestone Goal:** The append-only record of every state change, in one table with one schema, written through one writer that runs inside the caller's own transaction. The product's central claim against a spreadsheet — that the record cannot be quietly rewritten — is this table's guarantee to keep.

**Module:** `property-history` · **Spec:** `docs/modules/property-history.lock.yml` · **Wave:** 0

#### Phase 4: Schema, privilege, ordering, and the closed vocabulary

**Goal**: `history_event` and `history_action_registry` exist; append-only is a database privilege; events have a total order by a monotonic sequence; and the 31-name vocabulary rejects everything else.
**Depends on**: Nothing. This is a project entry point.
**Requirements**: PH-02, PH-04, PH-05
**Success Criteria** (what must be TRUE):

  1. `prope_app` attempting UPDATE or DELETE on a history event is refused by the engine, not by an application guard.
  2. Two events written in one transaction have a stable order on every run, including when their timestamps are identical.
  3. An append with an unregistered action or an unregistered `details` key raises, rolls the caller's transaction back with no partial state, and increments `append_rejected_total` with a reason.

**Spec**: `docs/modules/property-history.lock.yml` — `data.owns` (`history_event` with `seq`, `scope_prompt_id`, `details`, `reason`; `history_action_registry` with `detail_keys`, `requires_reason`, `writing_module`), `scope.in_scope` (append inside the caller's transaction, the closed vocabulary, details validation, total order by sequence). Also ADR-0023, ADR-0024, ADR-0025, ADR-0035.
**Plans**: TBD

#### Phase 5: The three functions five modules build against

**Goal**: `append()`, `read(scope, cursor, limit)` and `registered_actions()` exist as the in-process contract, with `scope_prompt_id` stamped at append so a prompt's Activity is one indexed read.
**Depends on**: Phase 4
**Requirements**: PH-03, PH-06
**Success Criteria** (what must be TRUE):

  1. A prompt with a full lifecycle returns all ten of its events in one query in submission order, with nothing from another prompt or another workspace.
  2. The registry compared against the union of the five lock files' event lists is the same 31 names, with no extras and no omissions.
  3. `read()` is ordered by `seq` descending and never by timestamp, and performs no permission check.

**Spec**: `docs/modules/property-history.lock.yml` — `apis.exposes` (`append`, `read`, `registered_actions`; explicitly **no HTTP surface**), `apis.consumes` (empty — the only module in Prope with an empty consumes list). Seams INT-006, INT-007, INT-008.
**Plans**: TBD

#### Phase 6: Atomicity, no route, no content, no deletion

**Goal**: The four guarantees this module exists to keep are asserted rather than intended.
**Depends on**: Phase 5
**Requirements**: PH-01, PH-07, PH-08, PH-09, PH-10
**Success Criteria** (what must be TRUE):

  1. Killing the process between a release row and its history event at several interleavings leaves either both or neither; there is no state in which a release exists without its event.
  2. Enumerating the assembled route table finds no route resolving to property-history and no `/api/v1/history` path at any version.
  3. Inspecting every field of every event in a full pilot dataset finds no prompt body, fallback answer, credential, password hash, eval output, or variable value.
  4. A removed member's `actor_id` is unchanged on every event they wrote, and no expiry job exists.

**Spec**: `docs/modules/property-history.lock.yml` — `failure_modes` (all 7 rows), `observability_requirements.metrics` (7 metrics incl. `append_rejected_total`, `null_scope_prompt_total`, `rows_total`), `security_requirements`, `test_plan`, `acceptance_criteria`. Also ADR-0025 (privilege test shape), A-121 (nothing expires), A-123 (no route).
**Plans**: TBD

---

### 📋 M3 Access Control (Planned)

**Milestone Goal:** Authenticate every actor and answer every may-this-actor-do-this question, so that no other module holds a copy of the rules. The oracle six modules consult, depending on one module and calling none of its callers.

**Module:** `access-control` · **Spec:** `docs/modules/access-control.lock.yml` · **Wave:** 1

#### Phase 7: Schema, identity, and the permission decision

**Goal**: The eight `access` tables exist with RLS and the two `SECURITY DEFINER` bootstrap functions; argon2id sign-in issues a server-side session row; and `may()` decides over a closed vocabulary from a `role_permission` matrix stored as rows.
**Depends on**: Phase 6 *(property-history is this module's only upstream dependency)*
**Requirements**: AC-03, AC-04, AC-08, AC-13
**Success Criteria** (what must be TRUE):

  1. An actor with two role bindings, one granting `prompt.edit` and one not, is allowed — permissions union and nothing subtracts.
  2. An action string outside the vocabulary is denied, `unknown_action_total` increments, and no exception reaches the caller.
  3. Removing or demoting the last Admin of a workspace is refused, `admin_count` stays 1, and `last_admin_refused_total` increments.
  4. Tombstoning a person nulls `email`, `display_name` and `password_hash`, deletes every session they hold, and makes a sign-in with the former email byte- and timing-identical to one with an email that never existed.

**Spec**: `docs/modules/access-control.lock.yml` — `data.owns` (`workspace`, `user`, `session`, `workspace_member`, `role_binding`, `role_permission`, `prompt_grant`, `api_key`), `scope.in_scope` (person and key authentication, `may()`, ownership of grants and keys, the zero-Admin refusal), `non_goals` (no SSO/OIDC, no deny-override grants, no caching). Also ADR-0020, ADR-0021, ADR-0029, ADR-0042, ADR-0054.
**Plans**: TBD

#### Phase 8: Seams: five internal functions and fifteen routes

**Goal**: The five in-process answers other modules build against exist, along with the fifteen management routes, each write appending its history event in the same transaction.
**Depends on**: Phase 7
**Requirements**: AC-09, AC-10, AC-12, AC-14
**Success Criteria** (what must be TRUE):

  1. `visible_subject_filter` returns `mode=ids` listing exactly the granted and owned prompts in a 1,000-prompt workspace, and the registry's list endpoint returns exactly that set.
  2. Every route in every module declares an action from the vocabulary; a route declaring none fails the test rather than defaulting to unauthenticated.
  3. A grant and its `access_granted` event cannot exist without each other; the same holds for revocation.
  4. A tombstone writes one `user_tombstoned` event per workspace the person belonged to, with empty `details` and no reason.

**Spec**: `docs/modules/access-control.lock.yml` — `apis.exposes` (`may`, `visible_subject_filter`, `authenticate_api_key`, `may_resolve`, `authenticate_session`, plus `/auth/*`, `/workspaces/*`, `/prompts/{id}/grants`, `/keys`, `/permissions`, `/users/{id}/tombstone`, `/healthz`, `/readyz`), `apis.consumes` (`property-history: append`), `outputs` (the nine event names plus `user_tombstoned`). Seams INT-001 through INT-005, INT-029.
**Plans**: TBD

#### Phase 9: Failing closed, refusal shapes, and the login path

**Goal**: Every refusal leaks nothing, revocation is immediate everywhere, and an unavailable access-control takes the whole system down safely rather than open.
**Depends on**: Phase 8
**Requirements**: AC-01, AC-02, AC-05, AC-06, AC-07, AC-11, AC-15
**Success Criteria** (what must be TRUE):

  1. A private prompt is not-found on every registry, evaluation and release endpoint and in search, identical in shape and status to an id that never existed; a viewer who lacks a permission instead gets a refusal naming it.
  2. A key used outside its scope produces a response byte-identical to one for a model name that does not exist, and a revoked key is refused on the very next request with no cached allow anywhere.
  3. A created key's plaintext appears in exactly one response and in no log, metric label, or history event, and cannot be reconstructed from the stored row.
  4. With the database unreachable, every module refuses every request and none logs an allow — asserted per caller, not only here.

**Spec**: `docs/modules/access-control.lock.yml` — `failure_modes` (all 11 rows), `observability_requirements.metrics` (17 metrics incl. `unknown_action_total`, `key_scope_refusal_total`, `login_rate_limited_total`, `last_admin_refused_total`), `security_requirements` (incl. the login limiter at 5/email and 20/address per 15 min), `test_plan`, `acceptance_criteria`. Also ADR-0022, ADR-0043, ADR-0053.
**Plans**: TBD

---

### 📋 M4 Provider Access (Planned)

**Milestone Goal:** Hold each workspace's own provider configurations and credentials, and be the single place in Prope that makes an upstream model call. **Prope's only outbound egress**, and the only module that decrypts anything.

**Module:** `provider-access` · **Spec:** `docs/modules/provider-access.lock.yml` · **Wave:** 2

#### Phase 10: Schema, envelope encryption, verification, and classification

**Goal**: The three `provider` tables exist with RLS; credentials are envelope-encrypted with a per-credential data key; a configuration is probed live before it may be used; and every upstream failure has a class.
**Depends on**: Phase 9
**Requirements**: PA-02, PA-03, PA-05
**Success Criteria** (what must be TRUE):

  1. An attacker holding the entire database and nothing else cannot recover a credential; supplying the KEK as well recovers it.
  2. A provider endpoint that returns no usage object fails verification, is not saved active, and cannot be bound to a revision, with the reason naming the missing usage object.
  3. 429, 500, 401, a content-policy refusal and a bad-parameter 400 each map to their own class with `fallback_eligible` and `retryable` set independently — 401 fallback-eligible but not retryable, 429 both, the last two neither.

**Spec**: `docs/modules/provider-access.lock.yml` — `data.owns` (`provider_config`, `credential`, `model_catalogue`), `scope.in_scope` (registration and verification, encryption and rotation, the catalogue, failure classification, admission), `non_goals` (no retrying, no fallback decision, no pricing). Also ADR-0014, ADR-0017, ADR-0045.
**Plans**: TBD

#### Phase 11: Seams: dispatch, the upstream provider, and the dashboard

**Goal**: `dispatch()` and `get_model_catalogue()` exist as the in-process contracts, the ten management routes are live, and the one external HTTP seam normalises every provider into the OpenAI shape while admitting interactive work ahead of batch.
**Depends on**: Phase 10
**Requirements**: PA-04, PA-06, PA-07, PA-08, PA-09, PA-10
**Success Criteria** (what must be TRUE):

  1. Every dispatch requests usage from the provider and returns a usage object; no caller parameter can turn it off, including on a stream.
  2. With batch dispatches saturating a configuration, an arriving interactive dispatch is admitted without waiting, and every unadmitted batch dispatch is counted in `shed_total{priority=batch}`.
  3. A dispatch that times out or 5xxs issued exactly one upstream request, regardless of error class.
  4. A rotated credential is in use in every process within 60 seconds with no restart, and its history event contains no part of either credential.
  5. A response from a non-OpenAI-shaped adapter is a valid OpenAI chat-completions object, and an unmodelled field from a compatible provider survives unchanged.
  6. Deleting a bound configuration is refused by the foreign key with a count and no query into the registry's tables; disabling it stops dispatch and keeps the configuration and catalogue readable.

**Spec**: `docs/modules/provider-access.lock.yml` — `apis.exposes` (`/api/v1/providers` ×8, `/healthz`, `/readyz`, `dispatch`, `get_model_catalogue`), `apis.consumes` (`access-control: may`, `property-history: append`), `external_services` (the workspace's own OpenAI-compatible endpoint, with its auth, rate limits, absent SLA, and the usage-object admission rule). Seams INT-015, INT-016, INT-023, INT-027. Also ADR-0015, ADR-0016.
**Plans**: TBD

#### Phase 12: The credential never leaves, and the KEK is a readiness gate

**Goal**: The non-negotiable credential rule is asserted from every direction, SSRF is closed at both the save and the dispatch, and losing the KEK is unmistakable.
**Depends on**: Phase 11
**Requirements**: PA-01, PA-11, PA-12
**Success Criteria** (what must be TRUE):

  1. Reading a saved configuration through list, detail, after update, in an error body, and in its property-history event returns no credential in any form — only its last four characters.
  2. A base URL resolving to a private or loopback address is refused at save and again at dispatch, and no request carrying the credential is issued.
  3. With the KEK unavailable, readiness is withheld, the KEK gauge reads 1, the dispatch failure class is distinct from every provider-origin class, and no log line suggests a provider outage.

**Spec**: `docs/modules/provider-access.lock.yml` — `failure_modes` (all 9 rows), `observability_requirements.metrics` (14 metrics incl. `shed_total`, `usage_missing_total`, `kek_unavailable`, `credential_rejected_total`), `security_requirements`, `test_plan`, `acceptance_criteria`. Also ADR-0047 (dispatch connects to the address it validated).
**Plans**: TBD

---

### 📋 M5 Prompt Registry (Planned)

**Milestone Goal:** The record of every prompt property and the immutable chain of revisions behind it. The only `L` module and the widest surface in the build — build property + revision + activity first, then search and filter, then the diff.

**Module:** `prompt-registry` · **Spec:** `docs/modules/prompt-registry.lock.yml` · **Wave:** 3

#### Phase 13: Schema, immutability, the constraint, the trigger, and the diff

**Goal**: `prompt_property` and `revision` exist with RLS; the released pointer's Approved-only rule is a database constraint; `search_text` is maintained by a trigger; revisions are append-only; and the diff computes on demand.
**Depends on**: Phase 12
**Requirements**: PR-01, PR-02, PR-05, PR-06
**Success Criteria** (what must be TRUE):

  1. Saving an edit to a prompt with 3 revisions creates a 4th with author and timestamp, and revisions 1–3 are byte-identical to before the save.
  2. A diff of two revisions renders a line-level body diff plus a field-level comparison of provider, upstream model, parameters and fallback answer in under 300 ms with both bodies at the 32 KiB cap.
  3. Retiring a prompt with an active release is refused with a message naming the release, and the status is unchanged.
  4. `set_released_revision` against a Draft revision is rejected **by the database**, and the pointer is unchanged.

**Spec**: `docs/modules/prompt-registry.lock.yml` — `data.owns` (`prompt_property` incl. `released_version_id` and `search_text`; `revision` incl. `workspace_id`), `scope.in_scope` (registration, immutable revisions, historical reads, the diff, search), `non_goals` (no release decisions, no dispatch, no semantic search). Also ADR-0001, ADR-0002, ADR-0048, A-050 (32 KiB body, 200-char change summary).
**Plans**: TBD

#### Phase 14: Seams: ten routes, five internal calls, three inbound commands

**Goal**: The management API, the gateway's hot read, and the three commands only release-control may issue all exist, with permission filtering living in the repository layer.
**Depends on**: Phase 13
**Requirements**: PR-04
**Success Criteria** (what must be TRUE):

  1. `resolve()` returns the released revision's full binding — body, provider config, model, parameters, fallback answer, version ID — at p95 under 10 ms over 1,000 requests.
  2. `resolve()` distinguishes *model name unknown* from *model name known, nothing released* in its miss result, so a withdrawal is visible in `resolve_miss_total`.
  3. `GET /api/v1/prompts/{id}/activity` returns events from all four writing modules in one indexed read on `(workspace_id, scope_prompt_id, seq DESC)`.
  4. `set_revision_status`, `set_released_revision` and `clear_released_revision` are the only paths that change status or the pointer, and each validates the transition here.

**Spec**: `docs/modules/prompt-registry.lock.yml` — `apis.exposes` (10 HTTP routes plus `resolve`, `list_released`, `set_released_revision`, `clear_released_revision`, `set_revision_status`), `apis.consumes` (`may`, `visible_subject_filter`, `append`, `get_model_catalogue`), `inputs` (the three commands from release-control), `outputs` (the five event names with `scope_prompt_id`). Seams INT-009 through INT-014, INT-016, INT-024. Also ADR-0008, A-118, A-119, A-128.
**Plans**: TBD

#### Phase 15: Private by default, the tripwire, and the `search_text` leak

**Goal**: The private-by-default promise holds through every read path, and the second copy of the prompt body never reaches a response.
**Depends on**: Phase 14
**Requirements**: PR-03
**Success Criteria** (what must be TRUE):

  1. A private prompt owned by A does not appear when B searches its exact title, and a direct GET by id returns the same not-found response as a nonexistent id.
  2. `prope_registry_unfiltered_query_total` stays 0, with a page attached if it moves.
  3. `search_text` is absent from every list and detail response, asserted by a whole-response scan rather than a field allow-list.
  4. A cross-workspace read of `registry.revision` is refused by RLS, and a read with no `app.workspace_id` set returns zero rows rather than all rows.

**Spec**: `docs/modules/prompt-registry.lock.yml` — `failure_modes` (all 8 rows), `observability_requirements` (6 metrics, 3 alerts incl. `RegistryUnfilteredQuery` and `RegistryUnapprovedPointer`), `security_requirements` (incl. threats T-017 through T-020 and the route-table uniqueness test), `test_plan`, `acceptance_criteria`. **Five acceptance criteria are owed to this phase and were never written as rows — see `.planning/research/PITFALLS.md` gap 1.**
**Plans**: TBD

---

### 📋 M6 Evaluation (Planned)

**Milestone Goal:** Hold each prompt's named eval suites, run them against a candidate and the released revision, and report per-case pass/fail plus the token and money delta — so a reviewer decides on measured evidence instead of reading a diff and guessing.

**Module:** `evaluation` · **Spec:** `docs/modules/evaluation.lock.yml` · **Wave:** 4

#### Phase 16: Schema, suite versioning, assertions, and the run lifecycle

**Goal**: The four `evaluation` tables exist; suites version independently of revisions and of each other; deterministic assertions evaluate per modality; and runs move queued → running → completed through a claim loop in `worker`.
**Depends on**: Phase 15, Phase 3
**Requirements**: EVAL-02, EVAL-03, EVAL-04, EVAL-09
**Success Criteria** (what must be TRUE):

  1. Cases that ended in a dispatch error are recorded as `error` and never as `fail`, and the cost delta is withheld with a stated reason.
  2. A completed baseline for the released revision at a suite version is reused rather than re-dispatched while that revision is still released, and the reused timestamp is shown.
  3. Saving an edited suite creates its next version; an in-flight run keeps reporting against its own version, sibling suites are untouched, and a cross-version comparison is refused.
  4. A run whose declared modality does not match the returned shape is refused before any case is dispatched, naming both, with no upstream call billed.

**Spec**: `docs/modules/evaluation.lock.yml` — `data.owns` (`eval_suite`, `eval_case`, `eval_run`, `case_result`), `scope.in_scope` (named suites per prompt, independent versioning, the run, comparison, pricing, warn-only cost), `non_goals` (no LLM-judge, no blocking on cost, no direct provider calls, no generated cases). Also ADR-0004, ADR-0006, ADR-0049.
**Plans**: TBD

#### Phase 17: Seams: nine routes, the review summary, and four consumed modules

**Goal**: The management API exists, `get_review_summary()` is the one thing release-control pulls, and dispatch, pricing, totals and the ceiling check all flow through their owners.
**Depends on**: Phase 16
**Requirements**: EVAL-01, EVAL-05, EVAL-08
**Success Criteria** (what must be TRUE):

  1. A 20-case suite run completes in under 120 s at p95 and the comparison shows per-case pass/fail for both revisions plus the token and money delta.
  2. Submitting a revision with three suites creates three runs; the review summary carries three rows plus a rollup, and `requires_acknowledgement` is true if any one has a failing case.
  3. A candidate exceeding the baseline cost by the configured threshold shows a warning above the decision buttons while approve and release stay enabled.
  4. The rollup's total cost delta is withheld whenever any suite withheld its own, and the valid per-suite deltas are still returned.

**Spec**: `docs/modules/evaluation.lock.yml` — `apis.exposes` (9 HTTP routes plus `get_review_summary`), `apis.consumes` (`get_revision`, `get_released_revision`, `dispatch` at `priority=batch`, `price_usage`, `get_run_totals`, `check_spend_ceiling`, `may`, `append`), `outputs` (the four event names). Seams INT-011, INT-015, INT-017, INT-019, INT-020, INT-021, INT-025. Also ADR-0005, ADR-0016, ADR-0019.
**Plans**: TBD

#### Phase 18: The sweeper, the bounds, and result privacy

**Goal**: A dead worker cannot strand a run, concurrency is bounded where it is actually enforced, and eval outputs inherit the registry's private-by-default rule.
**Depends on**: Phase 17
**Requirements**: EVAL-06, EVAL-07, EVAL-10
**Success Criteria** (what must be TRUE):

  1. A run whose worker died is marked `interrupted`, its completed case results stay readable, and no case is dispatched twice.
  2. Eval runs and case results for a private prompt return the same not-found shape as a nonexistent id, and no output text is returned.
  3. Concurrent submissions stay within the declared bounds, the remainder sit in `queued`, and every run eventually completes.
  4. A catastrophic-backtracking regex aborts within its timeout and records `outcome = error`, and other work in the same `worker` container completes unaffected.

**Spec**: `docs/modules/evaluation.lock.yml` — `failure_modes` (all 9 rows), `observability_requirements.metrics` (10 metrics incl. `case_flip_total`, `run_interrupted_total`, `modality_mismatch_total`, `run_queue_depth`), `security_requirements`, `test_plan`, `acceptance_criteria`. Also ADR-0049 (`claim_next_run()` and the `FOR UPDATE SKIP LOCKED` claim). **Three new criteria and two restatements are owed to this phase — see `.planning/research/PITFALLS.md` gaps 1 and 2.**
**Plans**: TBD

---

### 📋 M7 Gateway (Planned)

**Milestone Goal:** The OpenAI-compatible endpoint where the `model` field names a prompt property. Resolves, composes, dispatches, and falls back — while every call is recorded off the response path with the version ID that served it. **Owns no tables.**

**Module:** `gateway` · **Spec:** `docs/modules/gateway.lock.yml` · **Wave:** 4 (parallel with M6)

#### Phase 19: Resolution, composition, and the fallback decision

**Goal**: Model-name parsing, the 30 s in-process resolution cache, variable substitution, the system-prompt rule, and the first-byte fallback boundary all exist and behave.
**Depends on**: Phase 15, Phase 3
**Requirements**: GATE-02, GATE-03, GATE-04, GATE-05, GATE-07, GATE-08
**Success Criteria** (what must be TRUE):

  1. A pin to an Approved revision is served; a pin to a Draft revision is refused OpenAI-shaped with no upstream dispatch, counted as `pin_not_approved`.
  2. A withdrawn prompt returns OpenAI-shaped model-not-found — never the previous revision, never the fallback answer — counted as `no_release` and distinct from `unknown_model`.
  3. An upstream 500 before any byte is relayed serves the fallback answer as a 200 marked in header, body and call record, with zero tokens and zero cost; with no fallback stored, the provider's error passes through translated, with no canned content.
  4. A caller-supplied `system` message is refused with an OpenAI-shaped 400 and no dispatch, and the revision's own system prompt is never concatenated with the caller's.
  5. A request omitting a declared `{{variable}}` is refused naming it, and no request containing a literal placeholder is ever dispatched upstream.

**Spec**: `docs/modules/gateway.lock.yml` — `data.owns` (**none** — the resolution cache is a bounded in-process LRU, rebuildable), `scope.in_scope` (wire compatibility, resolution and pinning, composition, the fallback, response marking, the 30 s TTL), `non_goals` (no retrying, no aliases, no spend enforcement). Also ADR-0011, ADR-0012, ADR-0013.
**Plans**: TBD

#### Phase 20: Seams: `/v1`, four consumed modules, and the admission cap

**Goal**: `POST /v1/chat/completions` and `GET /v1/models` are wire-compatible and mounted as their own sub-application with their own error contract, authenticated per consumer key.
**Depends on**: Phase 19
**Requirements**: GATE-01, GATE-10, GATE-12
**Success Criteria** (what must be TRUE):

  1. A bare model name is served from the released revision, OpenAI-shaped, with the version ID in the `x-prope-version-id` header, the body's `prope` object, and the call record.
  2. A key calling a model name outside its scope gets a response identical in shape to one for a name that does not exist, counted as `not_permitted`.
  3. `GET /v1/models` lists exactly the released prompts that key may resolve, in the OpenAI list shape, with `id` equal to the model name.
  4. Errors are OpenAI-shaped on every path and never the management envelope; a 21st concurrent request on one key gets an OpenAI-shaped 429 with `Retry-After`.

**Spec**: `docs/modules/gateway.lock.yml` — `apis.exposes` (`/v1/chat/completions`, `/v1/models`, `/healthz`, `/readyz`), `apis.consumes` (`resolve`, `list_released`, `authenticate_api_key`, `may_resolve` — **neither auth call may be cached** — `dispatch` at `priority=interactive`, `enqueue`). Seams INT-003, INT-004, INT-009, INT-010, INT-015, INT-018, INT-022. Also ADR-0050, A-143 (20 in-flight per key).
**Plans**: TBD

#### Phase 21: Streaming failure, the TTL, and staying off the response path

**Goal**: The two hardest properties in the build — mid-stream failure semantics and a p95 that does not move when the ledger stalls — are demonstrated rather than asserted.
**Depends on**: Phase 20
**Requirements**: GATE-06, GATE-09, GATE-11
**Success Criteria** (what must be TRUE):

  1. An upstream failure after 10 relayed chunks terminates the caller's stream with an OpenAI-shaped error chunk, appends no fallback text, and records `outcome = truncated` with the partial body.
  2. A released prompt changed with no process restarted and no invalidation sent is served from the new revision by every process within 30 seconds.
  3. With the ledger stalled and 1,000 calls served, response p95 is statistically unchanged, every call record keeps its version ID, and only bodies are dropped with a matching counter.
  4. Added latency excluding the upstream call stays at p95 under 50 ms at 50 rps, with the authentication pair inside a p95 5 ms sub-budget measured in this module's own load test.

**Spec**: `docs/modules/gateway.lock.yml` — `failure_modes` (all 9 rows), `performance_requirements` (added latency p95 < 50 ms), `observability_requirements.metrics` (13 metrics incl. `added_latency_seconds`, `resolve_miss_total`, `fallback_total`, `rejected_system_message_total`, `record_missing_version_id_total`), `security_requirements`, `test_plan`, `acceptance_criteria`. **Two new criteria and one restatement are owed to this phase — see `.planning/research/PITFALLS.md` gaps 1 and 2.**
**Plans**: TBD

---

### 📋 M8 Release Control (Planned)

**Milestone Goal:** Carry a revision from submitted, through a recorded human decision, to released — and back again on a restore or a withdrawal. **The module that makes "0/11 teams have any approval step" false.**

**Module:** `release-control` · **Spec:** `docs/modules/release-control.lock.yml` · **Wave:** 5

#### Phase 22: Schema, the decision state machine, and the evidence digest

**Goal**: `approval`, `release` and `review_task` exist; the Draft → In review → Approved transitions are validated; break-glass creates its follow-up task; and an approval stores the evidence as it stood at decision time.
**Depends on**: Phase 18
**Requirements**: RC-02, RC-08, RC-09, RC-11
**Success Criteria** (what must be TRUE):

  1. An author holding approve may approve their own revision — `self_approved` true on the row and in the history event, counted, no alert — while an author holding only edit is refused.
  2. A break-glass release has `break_glass = true` and `approval_id` null, creates a `break_glass_followup` task due in 24 hours that never closes itself on a timer, and is counted while overdue.
  3. Submitting revision 6 supersedes revision 5's review task, leaves exactly one open task for the prompt, and alters no approval already recorded.
  4. An approval still shows the per-suite counts and cost delta as they stood at decision time after the suite is edited and re-run with different results.

**Spec**: `docs/modules/release-control.lock.yml` — `data.owns` (`approval`, `release`, `review_task`), `scope.in_scope` (submit, the review screen, approve / request changes, release, approve-and-release, restore, break-glass, withdraw, the review queue), `non_goals` (no multi-level approval, no environments, no notifications, no auto-release). Also ADR-0007, ADR-0009, ADR-0010, ADR-0074/A-074 (the evidence digest).
**Plans**: TBD

#### Phase 23: Seams: eleven routes, three registry commands, one evaluation pull

**Goal**: Every decision surface exists, every write appends its history event in the same transaction, and the released pointer moves only through the registry's compare-and-set command.
**Depends on**: Phase 22
**Requirements**: RC-01, RC-03, RC-04, RC-12
**Success Criteria** (what must be TRUE):

  1. Submit-then-approve moves the revision to Approved through `set_revision_status`, writes an approval row naming the reviewer, and appends the matching event.
  2. Releasing an Approved revision moves the pointer through `set_released_revision`, writes a release row with `approval_id` set and `break_glass` false, and the Success-metric SQL for releases lacking an approval returns zero rows.
  3. Approving a candidate reporting `requires_acknowledgement` is refused without a reason and succeeds with one, which is stored on the approval and appears in the history.
  4. Approve-and-release writes exactly one approval and one release in a single transaction with both events, and is refused naming the missing permission when the actor holds only one.

**Spec**: `docs/modules/release-control.lock.yml` — `apis.exposes` (11 routes: `/submit`, `/review`, `/approve`, `/request-changes`, `/releases`, `/approve-and-release`, `/releases/break-glass`, `/releases/withdraw`, `/releases` list, `/review-tasks`, `/review-tasks/{id}/close`), `apis.consumes` (`get_revision`, `get_diff`, `get_released_revision`, `set_revision_status`, `set_released_revision`, `clear_released_revision`, `get_review_summary`, `may`, `append`), `outputs` (the eight event names). Seams INT-011 through INT-014, INT-017, INT-026. Also ADR-0005, ADR-0008.
> **The three cross-module route-table assertions (AC-10, PH-07, prompt-registry's route-uniqueness rule) cannot actually run before this phase** — every module must be mounted first.
**Plans**: TBD

#### Phase 24: Conflicts, degraded evidence, and the end-to-end journeys

**Goal**: The two concurrency hazards are closed, approving with missing evidence is possible but recorded, and restore and withdraw are demonstrated end to end through the gateway.
**Depends on**: Phase 23
**Requirements**: RC-05, RC-06, RC-07, RC-10
**Success Criteria** (what must be TRUE):

  1. With evaluation unavailable, the eval panel says the evidence could not be loaded, an acknowledgement reason becomes mandatory, approval still succeeds, and the gap is counted.
  2. Restoring to a previously Approved revision writes a release of kind `restore`, moves the pointer, and has the gateway serving the restored revision within 5 minutes of the `revision_restored` event.
  3. Withdrawing clears the pointer, writes a release of kind `withdraw` with a non-null `previous_version_id`, makes the gateway return model-not-found, and unblocks retiring the prompt.
  4. Two concurrent releases of one prompt produce exactly one release row; the loser is refused with the currently released version ID and the conflict is counted.

**Spec**: `docs/modules/release-control.lock.yml` — `failure_modes` (all 7 rows), `observability_requirements.metrics` (11 metrics incl. `pointer_conflict_total`, `self_approval_total`, `summary_unavailable_total`, `review_task_overdue`, `review_turnaround_seconds`), `security_requirements`, `test_plan`, `acceptance_criteria`. Also A-072 (compare-and-set), ADR-0012 (the withdrawal is visible within the 30 s TTL), ADR-0051 (the cross-workspace sweep). **Two new criteria and one restatement are owed to this phase — see `.planning/research/PITFALLS.md` gaps 1 and 2.**
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order 1 → 24, subject to the dependency graph. Phases 1 and 4 are both entry points and may start simultaneously. Phases 16 and 19 both depend on 15 and 3, so M6 and M7 may run in parallel.

| Phase | Milestone | Module | Plans Complete | Status | Completed |
|-------|-----------|--------|----------------|--------|-----------|
| 1. Data model, pricing, and retention | M1 | call-ledger | 4/4 | In Progress|  |
| 2. Seams: enqueue, the broker drain, and the ceiling | M1 | call-ledger | 5/5 | In Progress|  |
| 3. Durability, idempotency, and no-read-path | M1 | call-ledger | 0/TBD | Not started | - |
| 4. Schema, privilege, ordering, and the closed vocabulary | M2 | property-history | 0/TBD | Not started | - |
| 5. The three functions five modules build against | M2 | property-history | 0/TBD | Not started | - |
| 6. Atomicity, no route, no content, no deletion | M2 | property-history | 0/TBD | Not started | - |
| 7. Schema, identity, and the permission decision | M3 | access-control | 0/TBD | Not started | - |
| 8. Seams: five internal functions and fifteen routes | M3 | access-control | 0/TBD | Not started | - |
| 9. Failing closed, refusal shapes, and the login path | M3 | access-control | 0/TBD | Not started | - |
| 10. Schema, envelope encryption, verification, and classification | M4 | provider-access | 0/TBD | Not started | - |
| 11. Seams: dispatch, the upstream provider, and the dashboard | M4 | provider-access | 0/TBD | Not started | - |
| 12. The credential never leaves, and the KEK is a readiness gate | M4 | provider-access | 0/TBD | Not started | - |
| 13. Schema, immutability, the constraint, the trigger, and the diff | M5 | prompt-registry | 0/TBD | Not started | - |
| 14. Seams: ten routes, five internal calls, three inbound commands | M5 | prompt-registry | 0/TBD | Not started | - |
| 15. Private by default, the tripwire, and the search_text leak | M5 | prompt-registry | 0/TBD | Not started | - |
| 16. Schema, suite versioning, assertions, and the run lifecycle | M6 | evaluation | 0/TBD | Not started | - |
| 17. Seams: nine routes, the review summary, and four consumed modules | M6 | evaluation | 0/TBD | Not started | - |
| 18. The sweeper, the bounds, and result privacy | M6 | evaluation | 0/TBD | Not started | - |
| 19. Resolution, composition, and the fallback decision | M7 | gateway | 0/TBD | Not started | - |
| 20. Seams: /v1, four consumed modules, and the admission cap | M7 | gateway | 0/TBD | Not started | - |
| 21. Streaming failure, the TTL, and staying off the response path | M7 | gateway | 0/TBD | Not started | - |
| 22. Schema, the decision state machine, and the evidence digest | M8 | release-control | 0/TBD | Not started | - |
| 23. Seams: eleven routes, three registry commands, one evaluation pull | M8 | release-control | 0/TBD | Not started | - |
| 24. Conflicts, degraded evidence, and the end-to-end journeys | M8 | release-control | 0/TBD | Not started | - |

## Not in any milestone

Two bodies of specified work own no module and therefore appear in no phase above. Recorded here so their absence reads as a known gap rather than an oversight. Both need a user decision; neither blocks phase 1.

- **The React SPA** — ADR-0052, consuming INT-024 through INT-029 (57 management routes across six modules). The eight milestones build eight backends and no user interface, while three success metrics can only be measured through it. Needs either a ninth milestone or a per-milestone UI phase before the pilot can run.
- **The deployment stack** — 7 services, 2 images, Caddy path routing, GitHub Actions → GHCR → SSH deploy, the `.env` holding the KEK, nightly `pg_dump`, Prometheus scrape config, Grafana dashboards. Specified across ADR-0031, ADR-0032, ADR-0033, ADR-0036, ADR-0039, ADR-0044, ADR-0052 and `tech_stack.md`; owned by no module.
