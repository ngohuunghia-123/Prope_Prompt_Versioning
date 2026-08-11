# Phase 12 — deferred items, mappings, and the planner's own self-check

**Phase:** 12 — The credential never leaves, and the KEK is a readiness gate · **Module:** provider-access ·
**Milestone:** M4 — **this phase CLOSES it** · **Depends on:** Phase 11

Written by the phase planner under the MINIMAL PROTOCOL (ORCHESTRATION §10a). There is no CONTEXT,
RESEARCH, PATTERNS, DISCUSSION-LOG or COVERAGE artifact for this phase, and **no critic reviewed these
plans before execution.** Everything the deleted artifacts carried lives in the plans' `<objective>`
sections; everything the deleted *checks* would have caught is self-checked in §9 below. Every judgement
in this file is an **agent judgement made by reading files** — no deterministic detector exists in this
environment and nothing here is detector output.

**This phase closes M4, so ORCHESTRATION §9a binds it.** Plan **12-06 Task 3** walks
`docs/modules/provider-access.lock.yml`'s `acceptance_criteria`, all seven `test_plan` categories, all nine
`failure_modes` rows and the six STRIDE threats clause by clause, and appends the result to this file
under `## M4 milestone audit (ORCHESTRATION §9a)`. §7 below is the **seed** for that walk — the ledger
phase 11 left plus what this phase's plans claim. It is not the walk.

Executors append to this file. Do not renumber the sections.

---

## 1. The phase's whole `docs/` footprint

`docs/` is read-only with exactly one exception: **creating** `docs/brainstorm/open_questions/OQ-NNN.md`.
The allocated range was **OQ-065 through OQ-069** and **all five were consumed.** Every one is a real spec
conflict found while planning; none is a placeholder. Highest id on disk when this range was allocated was
**OQ-054**; 055-059 belong to phase 10's planner and 060-064 to phase 11's, both running concurrently, and
none was touched.

| Id | One line | Severity | Named against |
|---|---|---|---|
| **OQ-065** | **Two of the seven declared alerts cannot fire against what is scrapable.** `ProviderBatchStarved` reads `shed_total{priority=batch}`, incremented only in `worker`, which serves no HTTP; the `worker` half of `ProviderKekUnavailable` is likewise unreachable; and `ProviderVerificationFailing` is declared as a spike *"on a previously passing configuration"* while `verification_total` declares only `result` and `reason`, so no expression can distinguish it from a new admin getting a URL wrong twice | high | lock `observability_requirements.alerts` (three rules) and `.metrics` (`verification_total`'s labels); `docs/adr/0046`; extends `OQ-026` |
| **OQ-066** | **provider-access's `test_plan.e2e` belongs to M4 and can only run after M7.** Four of the BYOK journey's seven steps cross prompt-registry, evaluation and the gateway. Phase 12 routes it to **phase 23** (PITFALLS §5's precedent) — which assigns an acceptance clause of provider-access's lock file to a phase of release-control's milestone, whose ROADMAP entry does not mention it and whose planner has already run | medium | lock `test_plan.e2e`; `.planning/ROADMAP.md` M4's three phases and Phase 23's criteria; PITFALLS §5 |
| **OQ-067** | **`origin = prope` is a declared label value with no member in the closed error set.** ADR-0017's eight classes and INT-015's seven all describe what the *provider* did, yet `error_total`'s declared labels include `origin = prope \| provider` and the lock file itself describes **four** Prope-origin conditions. Phase 10 added two by inference; phase 12 adds two more | high | `docs/adr/0017` Decision table; `interfaces.md` INT-015; lock `observability_requirements.metrics` `error_total`; lock `failure_modes` rows 1, 4, 9 and `test_plan.chaos` clause 5. **Distinct from `OQ-055` and `OQ-060`**, which are about the same set being written twice with different names |
| **OQ-068** | **The KEK readiness mitigation covers `app` and cannot cover `worker`, and one of its two triggers cannot fail at start-up.** `worker` serves no HTTP so it cannot withhold readiness, and it *pulls* work — a keyless `worker` keeps claiming eval runs and fails every case. Separately, the lock says both triggers *"fail at start-up"*, but a `kek_version` a **row** names is a property of a row and would need a boot-time scan of every credential in every workspace | medium | lock `failure_modes` row 1 (mitigation and RESOLVED paragraph); lock `deployment_target`; `docs/adr/0028` + D-17; `A-135` |
| **OQ-069** | **The SSRF guard's rejection policy is injectable and no authority sanctions the seam.** The lock, ADR-0047 and INT-023 all refuse loopback unconditionally; every test in this module drives a stub on `127.0.0.1`. Phase 11 chose an injected predicate over a compiled exemption and phase 12 injects the resolver too, which doubles the surface a specification is silent about | medium | lock `security_requirements` (the `base_url` bullet, T-025) and `test_plan.security`; `docs/adr/0047` Decision; `interfaces.md` INT-023 |

**Nothing else under `docs/` was written or edited.** No lock file, no ADR, no `interfaces.md` line, no
assumption file, no `adr_index.md` entry.

**`.planning/` files this phase's planner did NOT touch and its executors must not:**
`ORCHESTRATION.md`, `ORCHESTRATION-DECISIONS.md`, `WINDOWS.md`, `ROADMAP.md`, `REQUIREMENTS.md`,
`STATE.md`, `research/PITFALLS.md`, `BSP-LINK.md`, and every other phase's directory. Plan 12-06 Task 3
**writes the diffs** those files need, as ready-to-apply text, into this file; the orchestrator applies
them. Five other planners ran concurrently and a write outside this directory is a race.

---

## 2. ROADMAP success criterion → plan. Each owned by exactly one.

| # | Success criterion (ROADMAP, Phase 12) | Owning plan | Requirement | Proven by |
|---|---|---|---|---|
| 1 | Reading a saved configuration through list, detail, after update, in an error body, and in its property-history event returns no credential in any form — only its last four characters | **12-02** | PA-01 | `tests/security/test_credential_never_returned.py` (ten operations + five refusal shapes + every history column + every log record + every metric label + `repr`/`asdict`, over six renderings, with `last_four` as the positive control) · `tests/security/_forbidden_renderings.py` · `tests/architecture/test_credential_absent_from_the_schema.py` |
| 2 | A base URL resolving to a private or loopback address is refused at save and again at dispatch, and no request carrying the credential is issued | **12-01** | PA-11 | `tests/security/test_base_url_ssrf_guard.py` (the restated AC-11 — a resolver answering public then private, and the connection asserted to the first) · `tests/integration/test_provider_base_url_refused_at_save.py` (the save half, with zero-request and zero-decrypt controls) · `tests/unit/test_address_policy.py` |
| 3 | With the KEK unavailable, readiness is withheld, the KEK gauge reads 1, the dispatch failure class is distinct from every provider-origin class, and no log line suggests a provider outage | **12-03** | PA-12 | `tests/chaos/test_kek_unavailable.py` (AC-12's declared `test_ref`; the key removed from a running process, with recovery) · `tests/integration/test_health_and_readiness.py` · `tests/unit/test_key_ring_availability.py` |

**Three criteria, three owning plans, none claimed twice and none unclaimed.**

**One criterion ships with a stated internal boundary, named here rather than implied** — the same posture
phase 2 took for CL-01/CL-02 and phase 11 for SC5 and SC6:

- **SC3's "readiness is withheld" is true of `app` and structurally unavailable to `worker`.** `worker`
  serves no HTTP (D-17, from ADR-0028) and *pulls* work rather than receiving routed traffic. Plan 12-03
  Task 4 asserts the half that is true — `worker` sets the gauge and keeps running — writes the asymmetry
  and its consequence into `src/prope/worker.py`, and raises `OQ-068`. **It does not invent a mechanism**:
  a claim loop that checks the key ring is a behaviour change to evaluation's claim path, owned by phase
  16 and by a decision nobody has taken.

Plans **12-04**, **12-05** and **12-06** own **no** ROADMAP success criterion. They own the ROADMAP's
**Spec** routing for this phase — `observability_requirements.metrics`, `failure_modes` (all 9 rows),
`security_requirements`, `test_plan` and `acceptance_criteria` — which §9a makes a separate obligation from
the success criteria and which is the whole reason a milestone-closing phase exists.

---

## 2a. Requirement → plan. Each id in exactly one plan's `requirements:`.

| Requirement | Lock AC | Plan | Note |
|---|---|---|---|
| **PA-01** | provider-access AC-1 | **12-02** | Complete. All six read paths, asserted as a corpus scan over serialized bytes rather than a field allow-list, with a positive control on every path |
| **PA-11** | provider-access AC-11 (**restated**, PITFALLS gap 2) | **12-01** | Complete against the restatement. The lock file's literal text *"passes today with the TOCTOU still open"* and is deliberately **not** what was asserted |
| **PA-12** | provider-access AC-12 | **12-03** | Complete for `app`; the `worker` half of the readiness clause is structurally unavailable and raised as `OQ-068` (see §2) |

**Three requirements, three appearances, no duplicates and no omissions.** Plans 12-04, 12-05 and 12-06
carry an empty `requirements:` list — the same shape as phase 9's 09-06 and phase 10's 10-04/10-05/10-06,
and for the same reason: the lock file's `test_plan`, `failure_modes` and `observability_requirements`
blocks carry obligations that `.planning/REQUIREMENTS.md` never turned into a `REQ` id.

---

## 3. Plans, waves and dependencies

| Plan | Wave | depends_on | What it is |
|---|---|---|---|
| **12-01** | 1 | — | **Tracer.** One thin path through every layer the phase touches — a management route, the address guard, the pinned transport, the failure taxonomy, a metric and a log line — driven against the live engine and a real socket. Closes SSRF at save and at dispatch, and proves the **pinning** rather than the checking |
| **12-02** | 2 | 12-01 | The credential-never-returned corpus sweep across all six read paths, plus the `_forbidden_renderings` helper that plans 12-03, 12-04 and 12-06 all import |
| **12-03** | 2 | 12-01, 12-02 | The KEK as a readiness gate: `/readyz`'s second check, the gauge in both processes, the distinct failure class, the four mechanical claims that replace *"no log line suggests a provider outage"*, and `test_plan.chaos` clause 1 |
| **12-04** | 3 | 12-01, 12-02, 12-03 | The observability close: fourteen metrics read out of the lock file, three identifier labels decided one at a time, a widened cardinality walk, and seven alerts as a rules file |
| **12-05** | 3 | 12-01, 12-03 | Resilience: `test_plan.load`'s three clauses in the bounded/marked pair, and `test_plan.chaos`'s two remaining clauses |
| **12-06** | 4 | 12-01…12-05 | The milestone close: the outbound forbidden-edge walk, AC-13 verified and built if absent, the §9a audit, and the phase gate |

**No two plans in this phase have disjoint `files_modified`.** Every plan after the tracer touches at least
one of `src/prope/provider_access/observability.py`, `src/prope/observability.py`,
`src/prope/provider_access/dispatch.py` or one of the two candidate stub-provider modules; 12-01 and 12-05
both touch `tests/architecture/test_error_taxonomy_is_closed.py`, and 12-02, 12-03, 12-04 and 12-06 all
touch or import `tests/security/_forbidden_renderings.py`. **The orchestrator's disjointness check will
never fan out, which is correct.** Execution is serial regardless (ORCHESTRATION §7); the waves express
correctness ordering only.

Waves 2 and 3 each contain two plans. Inside a wave the ordering is numeric, and it is load-bearing in one
place: **12-02 must run before 12-03**, because 12-03 imports `_forbidden_renderings.py`. That is why
12-03's `depends_on` names 12-02 despite both being wave 2.

Two ordering facts about the error taxonomy, stated because three plans move the same constant:

- Phase 10's plan 10-02 asserts *exactly two* classes carry `origin = prope`.
- Plan **12-01** adds `address_refused` and moves it to **three**.
- Plan **12-05** adds `dispatch_deadline_exceeded` and moves it to **four**.

Each move happens **in the same change as the class it adds**, and each names the members individually
rather than only counting them. An executor running these out of order will find the number already moved;
the instruction in both plans is to read the current number rather than assume it.

---

## 4. `D-NN` decisions recorded. Range consumed: **D-200 … D-219** (all twenty).

| D | Plan | Decision | Reversibility |
|---|---|---|---|
| D-200 | 12-01 | **The production scheme allow-list drops `http`** — `frozenset({"https"})`. The private-range refusal already blocks every private `http` target, so the only thing `http` still buys is a bearer credential in cleartext on the public internet. `checkpoint:decision`, `OQ-069` q4 | cheap as code; **one-way for a configured workspace** — none exists (A-020) |
| D-201 | 12-01 | The **resolver** joins the predicate as an injected seam, and both collapse into one `AddressPolicy` object, so a caller cannot override half and keep the other's production default. This is what makes the restated AC-11 assertable at all. `OQ-069` | cheap |
| D-202 | 12-01 | **The guard runs before the credential is touched**, on all three paths (save, verify, dispatch). Turns *"no request carrying the credential is issued"* from an observation into an ordering property, asserted with a zero-call spy | cheap as code; the property is the point |
| D-203 | 12-01 | A Prope-side address refusal is its own class — `address_refused`, `origin = prope`, `fallback_eligible` true, `retryable` **false**. `OQ-067` | **costly** — two consumer modules branch on the taxonomy |
| D-204 | 12-01 | A save-time refusal is a **422** with a machine `code` and a closed reason token, and **never names the resolved address**. Echoing it would be host discovery through an authenticated form | costly — INT-027's response shape |
| D-205 | 12-02 | The sweep is a **corpus scan over serialized bytes**, across ten operations and five refusal shapes, **with a positive control on every path**. A file of absence assertions run against a broken application is green, and that is how this class of test actually fails | cheap |
| D-206 | 12-02 | **Six renderings of five secrets, and a run of five or more consecutive plaintext characters is a leak.** The marker's alphabet is chosen so that threshold does not flake — *do not lower the threshold, change the alphabet.* The inbound credential field becomes a redacting type | cheap for the corpus; **costly** for the field type |
| D-207 | 12-02 | The generated-schema name check is a **second line** in its own file, labelled as the weaker of the two claims so nobody deletes the sweep because "the schema test covers it" | cheap |
| D-208 | 12-03 | **`/readyz` gains the KEK check**, reversing `app.py`'s *"this is its final form"* on the authority of the lock file's `apis.exposes` and `deployment_target`. The docstring names the reversal; a provider outage still never affects readiness | **costly** — a compose healthcheck and an orchestrator read this endpoint |
| D-209 | 12-03 | A process with no usable KEK **boots**, sets the gauge and withholds readiness rather than exiting. A gauge never exported because the process died at import is a page that never fires, and a restart loop looks like four other faults | cheap |
| D-210 | 12-03 | *"No log line suggests a provider outage"* becomes **four mechanical claims**: the provider counter unmoved, zero records with a provider origin, zero records containing a word from a written-out outage vocabulary, and the stub's request counter at zero | cheap |
| D-211 | 12-03 | **The gauge is restorable and the cache window is stated.** 1 → 0 on recovery, asserted; and a credential already in the 60 s cache keeps working until its TTL expires, which is graceful degradation and is written down so it is not deleted as a flake | cheap |
| D-212 | 12-04 | The fourteen-metric set is **read out of the lock file as YAML**, in both directions, rather than retyped into the test. Where a real second machine-readable source exists, retyping it is how two lists come to disagree | cheap |
| D-213 | 12-04 | **Three declared identifier labels, three answers.** `credential_rejected_total` keeps `provider_config_id` under a declared exemption naming `ProviderCredentialRejected`; `upstream_duration_seconds` (a Histogram) and `model_unavailable_total` drop theirs and the facts move to the log line | cheap now, **costly after a series is scraped** |
| D-214 | 12-04 | The project-wide cardinality walk forbids a **set** of identifier names, not one, with exemptions that must exist, must have a reason, and must **name an alert**. A walk that forbids one name passes for every name nobody thought of | cheap — and it may redden an earlier phase, which is the point |
| D-215 | 12-04 | **Seven alerts, not six**, each with its reason, and **the two that cannot fire say so at the rule**. Writing an unfireable rule with a comment beats leaving it as prose nobody checks | cheap |
| D-216 | 12-05 | **The correctness halves gate; the timing halves are measured and reported**, with the three lock-file thresholds asserted only under `@pytest.mark.load`. A threshold that fails for the machine it ran on gets deleted rather than investigated | cheap |
| D-217 | 12-05 | A deadline consumed **inside Prope** is `dispatch_deadline_exceeded`, `origin = prope`, `fallback_eligible` true, `retryable` **true**. Blaming the provider for Prope's own stalled database is the same defect SC3 forbids one seam over. `OQ-067` | **costly** — two consumer modules branch on the taxonomy |
| D-218 | 12-06 | The module's outbound forbidden edges are an **allow-list**, not a deny-list. A deny-list naming the five forbidden modules passes for the four that M5-M8 have not written yet | cheap |
| D-219 | 12-06 | **`test_plan.e2e`'s BYOK journey is routed to phase 23** by name, with the reason, and `OQ-066` raised because that assigns an M4 acceptance clause to a phase of M8 | cheap as a routing decision |

---

## 5. `checkpoint:decision` blocks and their `UNCONFIRMED` adoptions

Under `mode: yolo` the planner writes the checkpoint in full and then adopts, per ORCHESTRATION §6. **One
genuine one-way decision surfaced in this phase** and is recorded as a `checkpoint:decision` task:

| Where | Question | Adopted | Status | Reversibility |
|---|---|---|---|---|
| **12-01 Task 1** | The production scheme allow-list: keep `http` (a self-hosted OpenAI-compatible endpoint is a legitimate pilot shape, and neither the lock nor ADR-0047 names the list's members) vs `https` only (the private-range refusal already blocks every private `http` target) | **Option B — `frozenset({"https"})`** (D-200) | `adopted: UNCONFIRMED` | cheap as code; **one-way for a configured workspace** |

**Deciding argument, restated for the ledger:** Option A's stated benefit does not survive the guard that
is already there. The private-network endpoint `http` exists for is refused **for being private**; what is
left is cleartext credentials to a public address, which no reading of A-025 or ADR-0014 permits. Taking
it now costs nothing — A-020 holds the line and there is no pilot workspace — and taking it later means
telling somebody their working configuration is no longer accepted.

**Every `<human-check>` in the six plans is also an adoption the user may reverse.** The substantive ones
are **D-200, D-201, D-203, D-206, D-208, D-209, D-213, D-216, D-217 and D-219**, plus two findings that are
not decisions but need adjudication:

- **the AC-1 finding** (12-02): whether pydantic v2's `input` key — the submitted value, present in every
  validation error dict — was reaching a `422` body before this plan, and that the fix landed in the shared
  error envelope rather than in provider-access alone, because **every request model in Prope carrying a
  secret has the same hole**;
- **the alert count** (12-04): the lock file declares **seven** alerts and phase 11's `deferred-items.md`
  §6 routed *"all six"* here. The rules file and its test carry seven.

Each is carried by an `OQ` where it is a spec conflict and by a `<human-check>` line where it is a
judgement. **No decision in this phase would violate an ORCHESTRATION §2 non-negotiable**, and none is
blocked.

---

## 6. Out-of-scope discoveries, and things routed rather than absorbed

| Item | Why it is not phase 12's | Routed to |
|---|---|---|
| **`test_plan.e2e`'s BYOK journey** — register → probe → catalogue → a revision binds a model → the gateway serves a live call → the eval runner runs a suite → rotate → both paths use the new credential within 60 s | Four of the seven steps cross prompt-registry (M5), evaluation (M6) and the gateway (M7). No phase of M4 can assert it, and a stubbed version would fake the majority of its own journey | **Phase 23** — the first phase after every module it crosses is mounted (PITFALLS §5's precedent). D-219, `OQ-066` |
| **The live `registry.revision` delete refusal** — a real revision bound to a configuration, a 409 with a count of 1 | `registry.revision` is created in phase 13. Phase 11's plan 11-05 asserts the shape against a stand-in FK the test creates | **Phase 13** (phase 11's `OQ-063`, D-196) |
| **A `worker` readiness surface, or a claim loop that checks the key ring** | `worker` serves no HTTP by D-17, derived from ADR-0028. The mechanism that would work is evaluation's claim path declining to claim, which is a behaviour change to a module phase 16 owns | **Phase 16** — or `OQ-068` q1, if the answer is that `worker` gains HTTP |
| **`worker`'s unscrapable metrics** — `shed_total{priority=batch}`, `admission_wait_seconds{priority=batch}`, every batch dispatch series, and the `worker` half of `kek_unavailable` | `OQ-026` is an existing question about exactly this, raised by phase 3 for call-ledger. `docs/` is read-only so it cannot be extended in place | **`OQ-065`**, which names `OQ-026` and adds provider-access's list. Unowned by any phase |
| **A `provider_config_id` label on `verification_total`**, without which `ProviderVerificationFailing` cannot be written as declared | It is a second identifier-label exemption and therefore a decision against ADR-0030, not an omission. Plan 12-04 writes the rule in the expressible form with the gap named | **`OQ-065` clause 3** |
| **Phase 10's finding `F-10-1` and `OQ-059` clause 2** — the three declared identifier metric labels, shipped as declared by phase 10 on the standing rule *do not drop a declared label to avoid raising a question*, and routed here with the instruction *"It should raise this from its own OQ range"* | **Answered as a decision rather than a question: D-213**, which resolves all three per metric with the reasoning at each — one kept under a declared exemption naming the alert that requires it, two dropped with the facts moved to the log line. Phase 9's `OQ-053` is the precedent for resolving this shape per metric rather than as one question. **The one piece that remains open is `OQ-065` clause 3**, where a *fourth* metric (`verification_total`) would need a label it does not declare in order for its alert to be expressible | **Answered by D-213**; residue in `OQ-065` clause 3 |
| **Phase 10's `F-10-1` versus phase 11's `D-199`** — phase 10 says it ships all three identifier labels; phase 11 says it drops all three | Both executed before this phase and they disagree. Plan 12-04's re-ground block says to **read the registry** and apply D-213 to whatever is actually there, then report which was true | **12-04**, reported in its SUMMARY |
| **Reconciling `origin = prope` into ADR-0017's Decision table and INT-015's list** | `docs/` is read-only. Four classes now exist that neither authority names, added across two phases | **`OQ-067`**. Consumers in phases 16-18 and 19-21 branch on these values |
| **A `pg_dump`-plus-`.env` separation check** (`security_requirements` ADR-0032/ADR-0036, T-027's backup half) | It is a property of a **deploy artifact** — a backup script and a destination — and PITFALLS §4 records that the deployment stack owns no milestone and appears in no phase. AC-2's live-database half is phase 10's (plan 10-01's subprocess recovery attempt) | **Unowned — PITFALLS §4.** Recorded in the §9a audit as `unowned` with this reason |
| **`test_plan.security`'s permission-separation clause** — *"permission separation between prompt editing and credential rotation"* | The prompt-editing half needs prompt-registry's permissions, which arrive in M5. Phase 11's plan 11-05 asserts the four provider actions are checked; the *separation from prompt editing* is assertable only once both vocabularies are enforced together | **Phase 15** — recorded in the §9a audit with this reason |
| **The React SPA that consumes INT-027** | PITFALLS §3: no lock file owns it and it has no milestone | Unowned, user decision |
| **Surfacing an unfinished KEK re-wrap** — phase 10's `U-10-5` asks this phase whether a mixed `kek_version` corpus should become a readiness or alerting concern, since a mixed corpus works indefinitely and is invisible | **Answered: no, and `OQ-068` clause 2 is why.** Detecting it means reading `kek_version` off every credential row in every workspace across the RLS boundary, and plan 12-03's readiness check is deliberately database-free and decrypt-free because `/readyz` is polled. The consequence — a partial KEK loss is invisible to readiness — is written into `OQ-068` clause 2 with a candidate answer (have the re-wrap record the lowest version still in use, so readiness compares one number without scanning) | **`OQ-068` q3.** Recorded in the §9a audit as routed, so `U-10-5` closes by decision rather than by nobody reading it |
| **Resolving any open question** | `OQ-026`, `OQ-053`, `OQ-058`, and `OQ-055` through `OQ-069` are all open at the close of M4. This phase raises five and answers none | User |

---

## 7. The seed for the M4 §9a audit — what this phase claims, before the walk

Plan 12-06 Task 3 writes the real audit. This table is the **seed** it starts from: phase 11's `§7` ledger
plus what phases 10 and 12 claim. **Every row here is a claim about a plan, not a verified fact about the
tree** — the walk's job is to convert each into a file and a test function name, or into a routed owner.

| Lock clause | Claimed disposition | By |
|---|---|---|
| AC-1 | asserted — `tests/security/test_credential_never_returned.py` | **12-02** |
| AC-2 | asserted — `tests/security/test_envelope_encryption_roundtrip.py`, the three-way subprocess recovery attempt | phase 10, 10-01 |
| AC-3 | asserted — `tests/integration/test_provider_must_report_usage.py` | phase 10, 10-03 |
| AC-4 | asserted — `tests/unit/test_usage_always_requested.py` | phase 11, 11-02 |
| AC-5 | asserted — `tests/unit/test_failure_classification_table.py` | phase 10, 10-02 |
| AC-6 (**restated**, PITFALLS gap 2) | asserted — `tests/load/test_batch_yields_to_interactive.py`. **The audit row must state that the restatement was audited**, not the literal text, which asserts against two deleted columns | phase 11, 11-04 |
| AC-7 | asserted — `tests/unit/test_exactly_one_attempt.py`, counted at the wire | phase 11, 11-01 |
| AC-8 | asserted — `tests/integration/test_credential_rotation_effective.py` + `tests/security/test_rotation_event_carries_no_credential.py` | phase 11, 11-06 |
| AC-9 | asserted, first clause against a test-only adapter (11-03's D-187) | phase 11, 11-03 |
| AC-10 | asserted, first clause against a stand-in FK (11-05's D-196); live form → **phase 13** | phase 11, 11-05 |
| AC-11 (**restated**, PITFALLS gap 2) | asserted — `tests/security/test_base_url_ssrf_guard.py`. **The audit row must state that the restatement was audited**; the literal text *"passes today with the TOCTOU still open"* | **12-01** |
| AC-12 | asserted — `tests/chaos/test_kek_unavailable.py`; the `worker` readiness half is structurally unavailable (`OQ-068`) | **12-03** |
| AC-13 (**owed, PITFALLS gap 1**) | **claimed by phase 10** — `tests/security/test_kek_rewrap_v1_to_v2.py` + the re-wrap callable + `OQ-058` + D-177. Phase 10's own `deferred-items.md` §2c is headed *"AC-13 is discharged in phase 10, and phase 12's verifier must not look for it"* and instructs this phase to *"treat AC-13 as closed and confirm it by reading `tests/security/test_kek_rewrap_v1_to_v2.py`, not by writing a second one."* **Plan 12-06 Task 2 follows that instruction: verify on the disk, change nothing if the six clauses hold, and build only if the claim did not survive execution** — PITFALLS says *"10 or 12"* and this phase closes the milestone | phase 10, 10-05 — **verified by 12-06** |
| `test_plan.unit` — classification table | asserted | phase 10, 10-02 |
| `test_plan.unit` — response and chunk normalisation, unknown-field pass-through | asserted | phase 11, 11-03 |
| `test_plan.unit` — the usage parser against exact field names | asserted | phase 11, 11-02 |
| `test_plan.unit` — envelope encrypt / decrypt / **rewrap** | encrypt/decrypt phase 10; **rewrap is AC-13**, verified by 12-06 Task 2 | phase 10 / **12-06** |
| `test_plan.unit` — the credential cache's TTL arithmetic | asserted | phase 11, 11-06 |
| `test_plan.unit` — admission-gate accounting | asserted | phase 11, 11-04 |
| `test_plan.unit` — **base-URL validation** | asserted in full — `tests/unit/test_address_policy.py` | **12-01** |
| `test_plan.integration` — create with a passing and a failing probe | asserted | phase 10, 10-03 |
| `test_plan.integration` — rotation and its 60 s effectiveness | asserted | phase 11, 11-06 |
| `test_plan.integration` — delete refused while bound | asserted against a stand-in; live form → phase 13 | phase 11, 11-05 |
| `test_plan.integration` — catalogue discovery, refresh, manual add, model unavailable | asserted | phase 10, 10-04 / phase 11, 11-03 |
| `test_plan.integration` — the history event in the same transaction | asserted | phase 11, 11-05 and 11-06 |
| `test_plan.integration` — permission checks on every management endpoint | asserted | phase 11, 11-05 |
| `test_plan.integration` — the two internal contracts from the calling side | asserted | phase 11, 11-06 |
| `test_plan.contract` — `dispatch()` and `get_model_catalogue()` parsed with a real SDK model | asserted | phase 11, 11-03 and 11-06 |
| `test_plan.e2e` — the BYOK journey | **routed to phase 23** (D-219, `OQ-066`) | **12-06** |
| `test_plan.load` — 50 rps, overhead p95 < 10 ms, cache ratio > 99% | asserted; correctness gated, timing under `@pytest.mark.load` (D-216) | **12-05** |
| `test_plan.load` — the concurrent 100-case batch, interactive p95 unchanged, only batch shed | asserted, minus whatever 11-04 already covers | **12-05** |
| `test_plan.load` — 200-chunk streaming at 10 concurrent streams, per-chunk p95 < 1 ms | asserted; ordering and completeness gated, timing under the marker | **12-05** |
| `test_plan.security` — the credential-never-returned sweep (T-028's corpus form) | asserted | **12-02** |
| `test_plan.security` — database-only recovery attempt (AC-2, T-027's live half) | asserted | phase 10, 10-01 |
| `test_plan.security` — T-027's **backup** half (`.env` never alongside the dump) | **unowned — PITFALLS §4**, no deploy artifact has a milestone | — |
| `test_plan.security` — SSRF at save and dispatch with a DNS answer that changes between them (T-025) | asserted | **12-01** |
| `test_plan.security` — an echoing provider cannot carry a prompt body out (T-026) | asserted for messages (11-01); asserted for the **credential** in 12-02 Task 2 | phase 11, 11-01 / **12-02** |
| `test_plan.security` — permission separation between prompt editing and credential rotation | provider half asserted (11-05); the **separation** needs prompt-registry → **phase 15** | phase 11 / **phase 15** |
| `test_plan.chaos` — KEK removed from a running process | asserted | **12-03** |
| `test_plan.chaos` — provider killed mid-stream | asserted | phase 11, 11-02 |
| `test_plan.chaos` — 429 storms, batch sheds before interactive | asserted | **12-05** |
| `test_plan.chaos` — property-history unavailable during a rotation | asserted | phase 11, 11-06 |
| `test_plan.chaos` — database open but unresponsive during a decrypt-cache miss | asserted, plus the origin claim (D-217) | **12-05** |
| `failure_modes` — all nine rows | **not yet walked.** Plan 12-06 Task 3 audits each row's `detection` signal AND its `mitigation`. The ROADMAP routes this block to phase 12 by name | **12-06** |
| `observability_requirements.metrics` — fourteen | asserted against the lock file read as YAML, both directions | **12-04** |
| `observability_requirements.log_fields` — three bullets | asserted — `LOGGABLE_FIELDS` positively, the *Never logged* set by corpus scan | **12-02** and **12-04** |
| `observability_requirements.alerts` — **seven** | asserted as a rules file + test; two carry a written cannot-fire note (`OQ-065`) | **12-04** |
| `security_requirements` — T-025 … T-030 | T-025 → 12-01; T-026 → 11-01 + 12-02; T-027 live half → 10-01, backup half unowned; T-028 → 12-02; T-029 → 11-04 + 12-05; T-030 accepted, with 12-01 Task 2 asserting pinning did not relax certificate verification | mixed |
| `performance_requirements` — seven rows | three covered by 12-05's marked tests; the other four (verification probe timeout, catalogue read p95, rotation effectiveness ≤ 60 s, decrypt on a hit) → walked in 12-06 Task 3 | mixed / **12-06** |

---

## 8. Assumptions this phase makes about phases it cannot read

**Phases 10 and 11 were planned in parallel with this phase and execute before it.** Their *plan files*
existed when these plans were written; their *code* did not. Every claim below is a claim about a plan, and
each is paired with a re-ground instruction in the plan that depends on it. **If one is wrong, the executor
reports drift rather than working around it.**

| Assumed | Where it matters | If wrong |
|---|---|---|
| `src/prope/provider_access/address.py` exists with `resolve_and_pin`, `PinnedTarget`, `is_globally_routable`, `AddressRefused` and the three reason tokens | 12-01 | The decisions are about behaviour, not a keyword's spelling. Adapt and report |
| The row writer is called `configurations.py` (phase 11) **or** `configs.py` (phase 10) | 12-01, 12-02, 12-04 | **Both declared in `files_modified` everywhere it matters.** Import from what exists; never create a second copy |
| The classification table is `failures.py` (phase 10) **or** `errors.py` (phase 11) | every plan | Both declared, same reason |
| The stub provider lives at `tests/provider/_stub_provider.py` (phase 11) **or** `tests/provider_access/stub_provider.py` (phase 10) | 12-01, 12-03, 12-04, 12-05 | Both declared. If **both** exist, that is drift the SUMMARY reports |
| `tests/architecture/test_error_taxonomy_is_closed.py` exists and asserts *exactly two* `origin = prope` classes | 12-01, 12-05 | Read the current number rather than assuming; move it to that number plus one, and **never delete the assertion** |
| `keyring.py` holds a `KeyRing` over `SecretStr` slots on the one `Settings` class, with `key_for` raising `KekUnavailable` and A-135's highest-present-wraps rule | 12-03 | If it is a function or a dict, adapt. If nothing installs a ring, 12-03 hoists it onto `app.state` and says so |
| `prope_provider_access_kek_unavailable` already exists and already moves (phase 10, 10-01) | 12-03, 12-04 | 12-03 adds only the **startup** evaluation and the **readiness** read; it does not redefine the gauge |
| The fourteen metrics are defined at import in `src/prope/provider_access/observability.py` | 12-04 | Both that file and `src/prope/observability.py` are declared. Edit the one that already holds a `prope_provider_access_*` name |
| Phase 9's plan 09-06 left an exemption mechanism in `tests/broker/test_publish_confirm_failures.py` | 12-04 | **Extend it; do not build a second walk.** If it is a bare `if metric.name == …`, 12-04 turns it into the declared mapping |
| `deploy/prometheus/rules/` holds `call_ledger.rules.yml` and `access_control.rules.yml`, and `test_alert_rules.py` walks them | 12-04 | Extend the same test file; its `METRIC_NAME` regex is call-ledger-specific and needs a per-module form |
| `tests/load/test_batch_yields_to_interactive.py` asserts the restated AC-6's three claims | 12-05 | **Do not re-assert them.** If 11-04 also covers the latency-distribution clause, assert only what is left and record it |
| Phase 3's `load` marker is registered in `pyproject.toml` and there is **no** `addopts` key | 12-05 | `pyproject.toml` is outside this phase's boundary. If the marker is gone, report it and use a bare `skipif` |
| Phase 10 shrank `EXPECTED_ABSENT_SCHEMAS` when it created the `provider` schema | every plan (a red suite otherwise), read back in 12-06 | Report as drift; **do not edit another phase's constant** |
| Phase 10's plan 10-05 shipped AC-13's re-wrap. **Phase 10's `deferred-items.md` appeared on disk while this phase was being planned and confirms the claim in §2c and D-177**, instructing phase 12 to verify by reading rather than by writing a second test | 12-06 Task 2 | Verified on the disk regardless — a plan's claim is not a fact about the tree. Both files are declared **conditionally** and built here only if the claim did not survive. **The function name is not hardcoded**: phase 10's plan says `rewrap_workspace_credentials` and its deferred-items says `rewrap_all_credentials`, and its finding **F-10-6** says the workspace enumerator may have become an explicit `workspace_ids` argument |
| Phase 10's plan 10-06 asserts the reverse-direction credential walk, the four `SECURITY DEFINER` set and the three-table schema; phase 11's 11-06 asserts the absence of a broker import | 12-06 Task 1 | **Do not duplicate.** Reference by file name and assert only the outbound edges |

**Phases 5, 7, 8 and 9 are planned but not built.** `append()`, `may()`, `refusal_for()`,
`require_usable_session`, `access.list_workspaces()` and `src/prope/management_api.py`'s `ErrorCode` /
`install_error_envelope` / `get_sessionmaker` are claims about *their plans*. `install_error_envelope` lives
in `src/prope/call_ledger/api.py` **today** and phase 8's D-116 moves it; 12-02 says to import from wherever
it actually is and to say loudly if the move has not happened, because importing call-ledger's copy would
give provider-access a dependency on a sink.

---

## 9. The planner's self-check — the five things the deleted exec-critic would have checked

Run by the planner against its own six files. Every result is an **agent judgement from reading**, not a
detector.

1. **Every ROADMAP success criterion is owned by exactly one plan.** ✅ §2's table: SC1 → 12-02,
   SC2 → 12-01, SC3 → 12-03. Three criteria, three plans, no criterion in two and none in none. Plans
   12-04, 12-05 and 12-06 own the ROADMAP's **Spec** routing instead, which §9a makes a separate
   obligation — and this phase closes M4, so it is the obligation that actually decides whether the
   milestone is done.

2. **Every requirement id appears in exactly one plan's `requirements:`.** ✅ PA-01 (12-02), PA-11 (12-01),
   PA-12 (12-03). Verified by reading the six frontmatter blocks: the union is exactly the phase's three
   and the intersection of any two is empty. 12-04, 12-05 and 12-06 carry `requirements: []`.

3. **Every file named in any task's `<action>` or `<files>` appears in that plan's `files_modified`.** ✅
   after a mechanical cross-check (a regex over every path-shaped token inside each `<tasks>` block, diffed
   against the frontmatter) and **four corrections**, each recorded here because the correction is the
   evidence the check ran:
   - **12-01** — Task 3's action answers a `422` with *"a machine `code` (ADR-0053)"*, which means adding a
     member to the closed `ErrorCode` enum. `src/prope/management_api.py` was absent from `files_modified`
     and from Task 3's `<files>`. **Added to both, conditionally**, with the note that if phase 8's D-116
     move has not happened the enum is still in `src/prope/call_ledger/api.py` and importing *that* would
     give provider-access a dependency on a sink — report it rather than do it.
   - **12-03** — Task 3's action asserts *"the stub's `request_count` is zero"* and uses the chaos rig, so
     the two candidate stub modules and `tests/conftest.py` belonged in Task 3's `<files>`. They were in
     `files_modified` but not in the task. **Added to the task.**
   - **12-05** — Task 4 measures per-chunk relay overhead, which may need an instrumentation point on the
     chunk path. `src/prope/provider_access/streaming.py` was absent from `files_modified` and from Task
     4's `<files>`. **Added to both, conditionally.**
   - **12-03 and 12-04** — both import plan 12-02's `tests/security/_forbidden_renderings.py` and neither
     declared `12-02` in `depends_on`; 12-03's own context even called the absence *"a `depends_on`
     violation"*. **Both `depends_on` lists corrected** (12-03 → `[12-01, 12-02]`, 12-04 →
     `[12-01, 12-02, 12-03]`).

   Every remaining path the cross-check flagged appears **only** inside a `<read_first>` block or as a
   named reference in prose (*"do not duplicate it"*, *"matching this file's posture"*), and each is listed
   in the plan's `files_modified` comment block as **read-only and deliberately not declared** — a path
   listed as modified that the plan forbids writing is a declaration the orchestrator cannot trust.
   `deferred-items.md` is deliberately **not** declared in 12-06's list either: it is a planner-seeded,
   executor-appended artifact rather than a code file, which is the convention phase 9 recorded.

4. **Every symbol, fixture, constant and file the plans tell an executor to extend exists today, or is
   created by an earlier plan in this phase, or is specified by an earlier phase's plans.** ✅ Verified by
   reading the tree and the phase 10 / 11 plan files. Nothing is assumed into existence.
   - **Exists today, read on disk:** `src/prope/app.py` (`create_app`, `lifespan`, `healthz`, `readyz` with
     its *final form* docstring, `metrics`, `READINESS_PROBE`, `READINESS_TIMEOUT_SECONDS`,
     `app.state.engine`); `src/prope/worker.py` (`run_worker`, `main`); `src/prope/db/engine.py`
     (`Settings` with `env_prefix="PROPE_"`, `build_engine`, `build_sessionmaker`);
     `src/prope/db/session.py`; `src/prope/observability.py` (`LOGGABLE_FIELDS`, the bucket-edge rule,
     D-40's define-at-import paragraph); `src/prope/session_auth.py` (`assembled_routes`);
     `src/prope/supervisor.py`; `src/prope/call_ledger/domain.py` and `drain.py`; `tests/conftest.py`
     (`postgres_container`, `migrate_engine`, `app_sessionmaker`, `report_engine`);
     `tests/integration/_asgi.py`; `tests/integration/test_health_and_readiness.py`;
     `tests/integration/test_management_routes.py`; `tests/architecture/test_tenant_coverage.py`
     (`DECLARED_SCHEMAS`, `GLOBAL_TABLES`, `EXPECTED_ABSENT_SCHEMAS`);
     `tests/architecture/test_route_table.py` (`EXPECTED_ROUTES`);
     `tests/architecture/test_no_sql_interpolation.py`; `tests/architecture/test_alert_rules.py`
     (`RULES_FILE`, `METRIC_NAME`, the written-out alert list);
     `tests/broker/test_publish_confirm_failures.py` (`_every_metric_label_value`,
     `test_workspace_id_is_never_a_metric_label`); `tests/load/__init__.py` and
     `test_fifty_rps_for_ten_minutes.py`; `tests/security/__init__.py`; `tests/unit/__init__.py`;
     `deploy/prometheus/rules/call_ledger.rules.yml`; `pyproject.toml`'s `load` marker and its
     deliberately absent `addopts`. **Every ADR and OQ path used in a `<context>` block was resolved
     against `ls docs/adr/` and `ls docs/brainstorm/open_questions/`; three ADR filenames were corrected
     after the first draft** (`0016-batch-yields-to-interactive-at-the-provider-seam.md`,
     `0021-consumer-keys-are-hashed-not-encrypted.md`,
     `0024-one-event-schema-with-a-registered-payload.md`).
   - **Created by an earlier plan in this phase:** `tests/security/_forbidden_renderings.py` (12-02);
     `tests/chaos/__init__.py` (12-03); the `address_refused` class and `AddressPolicy` /
     `PRODUCTION_POLICY` / `Resolver` (12-01); `PERMISSIVE_POLICY` in the stub module (12-01);
     `wrapping_key_available()` (12-03). Every consumer declares the producing plan in `depends_on`.
   - **Specified by an earlier phase's plans, not code:** everything under
     `src/prope/provider_access/` — phase 10's `keyring.py`, `crypto.py`, `models.py`, `domain.py`,
     `observability.py`, `credentials.py`, `configs.py`, `failures.py`, `probe.py`, `upstream.py`,
     `catalogue.py`, `rewrap.py`; phase 11's `dispatch.py`, `address.py`, `admission.py`,
     `credential_cache.py`, `streaming.py`, `usage.py`, `adapters.py`, `api.py`, `schemas.py`,
     `references.py`, `configurations.py`, `errors.py`; the test files each phase declares. Plus
     `append()` / `HistoryEventDraft` (phase 5, 05-01), the history registry seed with the four provider
     actions (phase 4, 04-01), `may()` (phase 7, 07-02), `access.list_workspaces()` (phase 7, 07-01),
     `management_api.py`'s `ErrorCode` / `ManagementRefusal` / `install_error_envelope` /
     `get_sessionmaker` (phase 8, 08-01, D-116), `refusal_for` / `is_visible` /
     `require_usable_session` (phase 9, 09-01), `deploy/prometheus/rules/access_control.rules.yml` and
     `tests/integration/test_access_control_metrics.py` (phase 9, 09-06). **Every one is named in the
     plan's re-ground block with an instruction to follow the code rather than the plan.**
   - **Genuinely undecided and hedged at the call site:** the phase-10-versus-phase-11 module-name split
     (§8's table). Both candidates are declared in `files_modified` everywhere the choice matters.

5. **No plan hardcodes an Alembic `down_revision`, gates on `ruff format --check`, references a
   `gsd-core` path, or puts the whole-suite `uv run pytest -q` anywhere but the last plan's
   `<verification>`.** ✅ Verified by grep across all six files:
   - **No migration is declared anywhere in this phase**, and the string `down_revision` does not appear
     in any of the six files. Phase 12 adds no schema; the two concurrency columns and the three tables
     are phases 10 and 11's. Plan 12-06's gate asserts `uv run alembic heads` reports **exactly one** head,
     which is D-04's linearity read back rather than a revision written.
   - `ruff format` appears only inside the standing-environment paragraph that says it is **not** a gate,
     fails repo-wide on Broken Window #1, and must not be run. Every lint gate is
     `uv run ruff check src/ tests/ alembic/`.
   - No `<execution_context>` block and no `$HOME/.claude/gsd-core/...` path appears in any of the six
     files.
   - The whole-suite `uv run pytest -q` appears **only** in 12-06 — in Task 4's `<verify>`, in Task 4's
     acceptance criteria, and in `<verification>`. Every other plan's `<verify><automated>` names targeted
     test paths. 12-05's `<verification>` carries a **marker-selected** `PROPE_RUN_LOAD=1 uv run pytest
     -m load -q`, run once by hand as a measurement whose failure is explicitly **not** a blocker — the
     shape phase 3's D-45.2 and phase 9's D-145 established.
   - No plan adds mypy, a `typecheck` target, a scheduler, a second broker queue, broker-based cache
     invalidation, `tsvector`, Next.js, or a fifth `SECURITY DEFINER` function. 12-06's gate queries the
     `SECURITY DEFINER` set from `pg_proc` and asserts it is exactly the four sanctioned ones.

**Three residuals this planner cannot close and states rather than hides.**

- **Phases 10 and 11 disagree about module names**, and neither had executed when these plans were
  written. That disagreement is this phase's largest risk surface, and the compensating control is a
  re-ground block at the top of every plan plus dual declarations in `files_modified`. **If phase 10 and
  phase 11 both shipped their own name, provider-access will have two credential modules and two stub
  providers**, and phase 12's executors will be the first stage to see it — there is no pre-execution
  stage left that would have.
- **Plan 12-01 tightens a default an entire earlier phase's tests depend on.** Dropping `http` from the
  scheme allow-list (D-200) reddens every phase-11 test that drives a stub on `http://127.0.0.1` unless
  every permissive-policy site is found and routed through one object. The plan says to find them all and
  list them; a missed one is a red test attributed to the wrong phase.
- **Three plans move the same closure constant** (`origin = prope`: two → three → four). Each move is in
  the same change as the class it adds and each names the members individually, but an executor running
  12-05 before 12-01 will find a number it does not expect. Both plans say to read the current value
  rather than assume it.

---

## M4 milestone audit (ORCHESTRATION §9a)

**Reserved. Written by plan 12-06 Task 3's executor**, one row per clause of
`docs/modules/provider-access.lock.yml`'s `acceptance_criteria`, all seven `test_plan` categories, all nine
`failure_modes` rows, the `security_requirements` block including T-025 through T-030, the
`observability_requirements` block, the seven `performance_requirements` rows and the `apis.exposes`
bullets — each `asserted` with a **file and a test function name**, `routed` with a **named phase**, or
`unowned` with a reason. §7 above is the seed the walk starts from; **it is not the walk.**

Followed by the three summary subsections plan 12-06 Task 3 specifies: *what M4 closes with unasserted*
(stated explicitly even if empty), *what M4 routes forward with the phase named*, and *the bookkeeping
diffs the orchestrator must apply* to `ROADMAP.md`, `REQUIREMENTS.md`, `STATE.md`, `WINDOWS.md` and
`ORCHESTRATION-DECISIONS.md`.
