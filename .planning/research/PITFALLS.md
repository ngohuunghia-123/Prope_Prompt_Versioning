# Pitfalls: Prope

> Transcribed from `docs/build/gsd_handoff.md` sections 4 and 11. Not researched by GSD — these are
> decisions already made and traceable to `docs/adr/`.
> Do not revise here; revise upstream and re-run the handoff.

Distilled from `risks`, `failure_modes`, and `security_requirements` across all eight lock files. Each module's own `failure_modes` block carries detection, impact, and mitigation per row.

## Project-level risks

| Risk | Mitigation | Owner |
|------|-----------|-------|
| prompt-registry is the only `L` module and the widest surface; if it stalls, nothing else can be demonstrated | Sequenced internally: property + revision + activity first, then search and filter, then diff. Re-scope if OQ-005 reveals a one-person team | M5, phases 13–15 |
| Prompt bodies may be sensitive corporate content with no classification, encryption, or access-logging policy decided | **OQ-006 is open and gates the pilot. A-020 forbids real corporate prompts until the baseline is signed off** | Project-level policy |
| A line-level diff shows what changed but not what it will do; a reviewer can approve a change whose effect they do not understand | The fixed eval suite and cost delta are the compensating controls on the same screen. No surface may claim the eval guarantees no degradation | M6 + M8, phases 17, 23 |
| Ownership is modelled as one person while OQ-008 is open | `owner_id` is a single indirection; if OQ-008 answers "team", it points at a principal table instead. The owner's name is denormalised nowhere | M5, phase 13 |
| Prope is an accepted hard dependency; a Prope outage is a full outage for every consuming product | Accepted, not mitigated. The fallback answer does not cover it — the fallback is stored in Prope | Accepted |
| One VM, one failure domain, no HA | Accepted at pilot scale. Nightly `pg_dump` copied off-host; up to 24 h RPO | Accepted (ADR-0033, ADR-0036) |

## The failure modes that shaped the architecture

Each is stated with the module and phase that owns closing it.

| Failure mode | Detection / mitigation | Module — phase |
|--------------|------------------------|----------------|
| **The released pointer set to a non-Approved revision** — the single failure that makes the whole product worthless | Mitigated by a **database constraint**, not an application check | prompt-registry — 13 (PR-06) |
| **A new query path added without the permission filter** — a private prompt appears to someone with no grant, the top adoption barrier in the survey | Filtering lives in the **repository layer**; `prope_registry_unfiltered_query_total` is a tripwire that must stay 0 with a page attached | prompt-registry — 15 (PR-03) |
| **`prompt_property.search_text` is a second copy of the prompt body** on the table every list endpoint reads; a `SELECT *` on the list path returns every body in a page of titles | Explicit response models everywhere; the column is never selected by name outside the search predicate | prompt-registry — 15 (T-017) |
| **`search_text` drifting from the row it describes** — the prompt becomes un-findable by its own new text, with no error, no metric, and no failed query | Maintained by a **database trigger**; a CI test asserts the trigger exists | prompt-registry — 13 (ADR-0048) |
| **A restore losing up to 24 hours of prompt revisions.** Prompt text is not derivable, not re-issuable, and held nowhere else | Accepted at pilot scale with a written procedural step | Accepted (ADR-0036) |
| **Metadata lost on a broker outage** | Every call must still produce a durable `call_record` with a non-null `version_id` via the direct-write fallback; only bodies are dropped, and every drop is counted | call-ledger — 3 (CL-01); gateway — 21 (GATE-11) |
| **A redelivered call record double-counting spend.** Durability without idempotency trades lost data for wrong data | The caller-generated `call_id` and the upsert are load-bearing | call-ledger — 3 (CL-02) |
| **A stale permission serving a revoked key** | Neither `authenticate_api_key` nor `may_resolve` may be cached, by either side — a deliberate divergence from the 30 s resolution cache beside them | access-control — 9 (AC-06); gateway — 20 |
| **A caller-supplied system message concatenated with the revision's own** | Refused with an OpenAI-shaped 400 before any dispatch | gateway — 19 (GATE-07) |
| **A mid-stream upstream failure.** The fallback is reachable on one side of the first-byte boundary and not the other | After the first byte the stream terminates with an error chunk and no fallback text | gateway — 21 (GATE-06) |
| **Catastrophic regex backtracking in an assertion** blocking other work in the shared `worker` | Per-assertion timeout; the case records `outcome = error` and other work is unaffected | evaluation — 18 (owed AC-11) |
| **A base URL edited to an internal address** to make Prope fetch it with the credential attached | Refused at save *and* at dispatch, with the connection pinned to the address that was validated (ADR-0047) | provider-access — 12 (PA-11) |
| **The last Admin of a workspace removed**, locking everyone out | Refused and counted | access-control — 7 (AC-08) |
| **Argon2id's cost parameter tuned down** because the login screen feels slow | Cost parameters are asserted, not configured by feel | access-control — 7 / 9 |

## STRIDE

Run at BSP step 6 pass 3 across boundaries B1–B4. Findings are recorded inline in each lock file's `security_requirements` as `THREAT T-NNN` with a severity and a mitigation, and each HIGH has a named test in `test_plan.security`.

The registry's **T-017** (`search_text` in a list response) and **T-018** (`registry.revision` had no tenant column and holds every prompt body in Prope) are the two HIGHs that changed the schema. ADR-0045's inverted RLS coverage test — which walks every table in all eight schemas and demands each be tenant-scoped or declared global with a written reason — caught T-018 on day one with no new decision required. Four tables gained a `workspace_id` column across six passes.

---

# Coverage gaps — obligations no acceptance criterion covers

From handoff section 11. **None has been promoted into a requirement** — they are listed so they stay visible without silently expanding scope. Treat every item here as work a phase's plan should account for even though no `REQ` id points at it.

## 1. Sixteen acceptance criteria are owed and were never written as rows

**The largest gap and the one to act on first.** During the BSP step-4 stack pass, six lock files recorded acceptance criteria that step 4 could not author, in comment blocks addressed to the step-6 sweep. The sweep ran and flipped `ready_for_build: true` **without folding them in**. Because they are YAML comments and not `acceptance_criteria` rows, they are not requirements.

| Module | Owed, never written | Substance | Phase that should absorb it |
|--------|--------------------|-----------|------------------------------|
| prompt-registry | AC-7, AC-8, AC-9, AC-10, AC-11 | `search_text` absent from every response body (asserted by whole-response scan); the `search_text` trigger exists and fires on a direct INSERT bypassing the application; `registry.revision` has RLS with a policy and appears in ADR-0045's coverage walk; substring semantics hold end to end (`'thentic'` matches `authentication`) — the assertion that stops a future "optimisation" to `tsvector`; a term matching only a non-latest body returns nothing while one matching an older **change summary** returns the prompt | 13 and 15 |
| access-control | 3 criteria, **now without ids** | The `SECURITY DEFINER` set is exactly the sanctioned functions, each REVOKEd from PUBLIC with an empty `search_path`; ADR-0035's RLS coverage test extended to reach `prompt_grant` and `workspace`, failing if its second clause is removed; the login limiter performs **no argon2id verification** at threshold even with the correct password, asserted by timing or a hasher spy | 7 and 9 |
| evaluation | AC-11, AC-12, AC-13 | A catastrophic-backtracking regex aborts within its timeout and other work in the same `worker` completes unaffected; `claim_next_run()` is the only route reading a row from an unset-tenant context; two concurrent claim loops leave exactly one winner | 16 and 18 |
| gateway | AC-13, AC-14 | A malformed request body returns an OpenAI-shaped 422 and **never** FastAPI's default `{"detail": [...]}`; an unhandled exception returns an OpenAI-shaped 500 that a real OpenAI SDK raises its normal exception type for | 20 |
| provider-access | AC-13 | KEK re-wrap V1 → V2: every row reports `kek_version=2`, every credential still decrypts, V1 can be removed, and no plaintext was written anywhere | 10 or 12 |
| release-control | AC-13, AC-14 | The `worker` sweep counts an overdue task in a workspace no request has touched since process start — **and the same test with one unscoped query must count zero**; the import-linter layering contract fails the build on a cross-module model import | 22 and 24 |

> **The access-control case is worse than a miss.** Its three owed criteria were to be numbered AC-13, AC-14, AC-15. When OQ-017 was resolved later the same day, three *different* criteria took those ids (the tombstone ones, now requirements AC-13 through AC-15). The step-4 criteria are now unnumbered and would be lost entirely if this section did not restate them.

## 2. Eight acceptance criteria assert against things step 4 changed

Written before ADR-0028 / 0041 / 0046 / 0047 / 0049 and never restated. **They will pass or fail for the wrong reasons as written.** Each phase's plan must use the restated form, not the lock file's literal text.

| Module | AC | Why it no longer holds — and the restatement |
|--------|----|-----------------------------------------------|
| call-ledger | AC-1, AC-2 | Stated against an in-process queue and a spill file, neither of which exists. Restate as "RabbitMQ unreachable" and "every message redelivered after an unacknowledged consumer restart" |
| evaluation | AC-9 | A 202 now precedes the modality check; only the **claim-time** refusal writes `status=refused`, and that is what must be asserted |
| evaluation | AC-10 | Asserts a global bound of 10 that ADR-0049 deleted. Restate as the two surviving bounds independently: `max_concurrent_runs` per workspace at the claim, `batch_concurrency` per provider config at the provider seam |
| gateway | AC-11 | Same in-process-queue problem as call-ledger's. Restate against a provoked broker outage with the inline direct write taking over |
| provider-access | AC-6 | A single-process assertion against two columns that no longer exist. Restate as each cap holding within its own process, their sum never exceeded upstream, and a saturated `worker` not affecting `app`'s admission latency |
| provider-access | AC-11 | Passes today with the TOCTOU still open. The meaningful version uses a resolver answering public on validation and private immediately after, then asserts the connection went to the **first** |
| release-control | AC-7 | States "the gateway returns model-not-found" with no tolerance. ADR-0012 replaced invalidation with expiry, so as written it passes or fails on cache age. Restate as **within 30 seconds**, never serving the previous revision or the fallback in the interval |

## 3. The React SPA has no milestone

ADR-0052 specifies a React 19 + TypeScript SPA built by Vite, baked into a `caddy:2` image, consuming **INT-024 through INT-029 — 57 management routes across six modules**. No lock file owns it. The module map is explicit that this is deliberate ("there is no 'frontend' or 'backend' module, because neither owns a journey"), and for a *bounded-context* decomposition that is the right call.

**But it means the eight milestones build eight backends and no user interface**, while three success metrics ("time to find the trusted revision ≤ 30 s", "non-developer creates and submits a revision with 0 lines of code", "median review turnaround") can only be measured through it. This needs either a ninth milestone or a per-milestone UI phase before the pilot can be run at all. **It is a decision for the user, not something the handoff should invent.**

## 4. The deployment stack has no milestone

Seven services, two images, Caddy path routing, GitHub Actions → GHCR → SSH deploy, the `.env` holding the KEK, nightly `pg_dump` with two table-data exclusions, Prometheus scrape config and Grafana dashboards. All specified across ADR-0031, ADR-0032, ADR-0033, ADR-0036, ADR-0039, ADR-0044, ADR-0052 and `tech_stack.md` — and owned by no module, so present in no milestone and no phase.

## 5. Smaller gaps

- **Search and filter has no acceptance criterion.** It is a named `in_scope` capability of prompt-registry with a stated p95 < 500 ms performance requirement and a `test_plan.load` entry, but the only ACs that would cover its semantics are the owed AC-10 and AC-11 above.
- **The registry's own Activity endpoint has no AC.** property-history's PH-03 covers the read from the other side of the seam, which is most of the value, but `GET /api/v1/prompts/{id}/activity` is untested from the caller's side.
- **The i18n layer has no owner.** ADR-0053 requires a keyed catalogue with no literal display strings across every surface. Only AC-15 touches it, and only for tombstoned actors.
- **Two success metrics are deliberately not product surfaces.** Restore time end-to-end and median review turnaround are hand-run SQL at pilot review (A-126), because the first spans property-history and call-ledger across an edge the map forbids. Recorded so their absence reads as a decision.
- **The cross-module route-table tests need a home.** Three criteria (AC-10, PH-07, and prompt-registry's route-uniqueness requirement) assert properties of the *assembled* route table. They are assigned to the phase of the module that owns the rule, but they **cannot actually run until every module is mounted — i.e. not before phase 23.**

## Sources

- `docs/modules/*.lock.yml` — `risks`, `failure_modes`, `security_requirements`, `test_plan` per module
- `docs/adr/` — ADR-0012, ADR-0028, ADR-0036, ADR-0041, ADR-0045, ADR-0046, ADR-0047, ADR-0048, ADR-0049, ADR-0052
- `docs/brainstorm/open_questions/` — OQ-005, OQ-006, OQ-008, OQ-012, OQ-013
- `docs/brainstorm/assumptions/A-020.md`, `A-126.md`
