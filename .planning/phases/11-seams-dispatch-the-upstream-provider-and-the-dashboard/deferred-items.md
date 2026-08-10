# Phase 11 — deferred items, mappings, and the planner's own self-check

**Phase:** 11 — Seams: dispatch, the upstream provider, and the dashboard · **Module:** provider-access ·
**Milestone:** M4 (does **not** close it — phase 12 does) · **Depends on:** Phase 10

Written by the phase planner under the MINIMAL PROTOCOL (ORCHESTRATION §10a). There is no CONTEXT,
RESEARCH, PATTERNS, DISCUSSION-LOG or COVERAGE artifact for this phase, and **no critic reviewed these
plans before execution.** Everything the deleted artifacts carried lives in the plans' `<objective>`
sections; everything the deleted *checks* would have caught is self-checked in §9 below. Every judgement
in this file is an **agent judgement made by reading files** — no deterministic detector exists in this
environment and nothing here is detector output.

**Phase 12 closes M4, so ORCHESTRATION §9a binds phase 12 rather than this one.** §7 below is the ledger
this phase leaves for that audit: what phase 11 asserted, what it routed, and to whom.

Executors append to this file. Do not renumber the sections.

---

## 1. The phase's whole `docs/` footprint

`docs/` is read-only with exactly one exception: **creating** `docs/brainstorm/open_questions/OQ-NNN.md`.
The allocated range was **OQ-060 through OQ-064** and **all five were consumed.** Every one is a real
spec conflict found while planning; none is a placeholder. Highest id on disk before this phase was
**OQ-054** (phase 9's range); 055-059 belong to sibling planners running concurrently and were not
touched.

| Id | One line | Severity | Named against |
|---|---|---|---|
| **OQ-060** | The upstream error-class vocabulary is written twice and disagrees: ADR-0017 declares **eight** classes, `interfaces.md` INT-015 declares **seven** with three renamed, and `provider_contract_violation` — the class a provider that stops returning usage has to take — is missing from INT-015 entirely | medium | `docs/adr/0017-…` Decision table; `docs/architecture/interfaces.md` INT-015; `docs/modules/provider-access.lock.yml` `failure_modes` + `alerts`, which use ADR-0017's names |
| **OQ-061** | **Two closed vocabularies owned by other modules do not cover this module's declared surface** — there is no `provider.read` action, so six of ten operations borrow `provider.configure`; and the 31-name history registry has no deletion action, so `DELETE /providers/{id}` writes no event while A-014 says every state change does | medium | lock `apis.consumes` (the four actions); `interfaces.md` per-module action table + INT-027; `docs/modules/access-control.lock.yml` (A-115's closed vocabulary); `docs/modules/property-history.lock.yml` (the four provider events); lock `apis.exposes` DELETE bullet |
| **OQ-062** | **AC-10/SC6's two clauses are jointly unsatisfiable.** A foreign-key violation carries no count, so *"stating how many revisions bind the configuration"* requires counting rows in a registry table, which SC6's *"no query into the registry's tables"* forbids | medium | `.planning/ROADMAP.md` Phase 11 SC6; lock `apis.exposes` DELETE bullet; `interfaces.md` INT-027 failure semantics; lock AC-10 |
| **OQ-063** | **PA-10 is mapped to Phase 11 and its declared mechanism is created in Phase 13.** `registry.revision.provider_config_id` is the foreign key that refuses the delete, and `registry.revision` is prompt-registry's `data.owns` | medium | `.planning/REQUIREMENTS.md` PA-10 row; `.planning/ROADMAP.md` Phase 11 SC6 and Phase 13; lock `data.referenced_by`; `docs/modules/prompt-registry.lock.yml` `data.owns` |
| **OQ-064** | **Batch admission has three authorities pointing three ways.** SC2 requires every unadmitted batch dispatch be counted, INT-015 promises a run is *"slowed — never failed — by production load"*, and ADR-0046 makes batch and interactive structurally non-contending so nothing could shed batch at all | medium | `.planning/ROADMAP.md` Phase 11 SC2; `interfaces.md` INT-015 Admission; `docs/adr/0046-…`; lock AC-6 (owed a restatement) + the `ProviderBatchStarved` alert |

**Nothing else under `docs/` was written or edited.** No lock file, no ADR, no `interfaces.md` line, no
assumption file, no `adr_index.md` entry.

**`.planning/` files this phase's planner did NOT touch and its executors must not:**
`ORCHESTRATION.md`, `ORCHESTRATION-DECISIONS.md`, `WINDOWS.md`, `ROADMAP.md`, `REQUIREMENTS.md`,
`STATE.md`, `research/PITFALLS.md`, `BSP-LINK.md`, and every other phase's directory. Plan 11-06's phase
gate **reports the diffs** the bookkeeping files need; the orchestrator applies them.

---

## 2. ROADMAP success criterion → plan. Each owned by exactly one.

| # | Success criterion (ROADMAP, Phase 11) | Owning plan | Requirement | Proven by |
|---|---|---|---|---|
| 1 | Every dispatch requests usage from the provider and returns a usage object; no caller parameter can turn it off, including on a stream | **11-02** | PA-04 | `tests/unit/test_usage_always_requested.py` (four wire-level cases + an `ast` assertion that `include_usage` appears once as a literal `True`) · `tests/unit/test_usage_field_names.py` · `tests/provider/test_streaming_dispatch.py` |
| 2 | With batch dispatches saturating a configuration, an arriving interactive dispatch is admitted without waiting, and every unadmitted batch dispatch is counted in `shed_total{priority=batch}` | **11-04** | PA-06 | `tests/load/test_batch_yields_to_interactive.py` (the restated AC-6's three claims, sum measured at the stub) · `tests/provider/test_admission_gate.py` |
| 3 | A dispatch that times out or 5xxs issued exactly one upstream request, regardless of error class | **11-01** | PA-07 | `tests/unit/test_exactly_one_attempt.py` (four provocations + a 302 + an `ast` assertion + a counter negative control) |
| 4 | A rotated credential is in use in every process within 60 seconds with no restart, and its history event contains no part of either credential | **11-06** | PA-08 | `tests/integration/test_credential_rotation_effective.py` · `tests/provider/test_credential_cache_ttl.py` · `tests/security/test_rotation_event_carries_no_credential.py` |
| 5 | A response from a non-OpenAI-shaped adapter is a valid OpenAI chat-completions object, and an unmodelled field from a compatible provider survives unchanged | **11-03** | PA-09 | `tests/contract/test_response_normalisation.py` (a real OpenAI SDK model as the oracle, plus a test-only `RenamedFieldsAdapter`) · `tests/architecture/test_openai_sdk_is_test_only.py` |
| 6 | Deleting a bound configuration is refused by the foreign key with a count and no query into the registry's tables; disabling it stops dispatch and keeps the configuration and catalogue readable | **11-05** | PA-10 | `tests/integration/test_config_delete_refused_while_bound.py` (a real FK created by the test) · `tests/provider/test_disabled_config_refuses_dispatch.py` |

**Six criteria, six owning plans, none claimed twice and none unclaimed.**

**Two criteria ship as HALVES, and both halves are named here rather than implied** — the same posture
phase 2 took for CL-01/CL-02 and phase 9 for AC-1:

- **SC6's first clause is asserted against a stand-in.** `registry.revision` does not exist until phase
  13, so 11-05's test creates a **real** foreign key in a scratch schema and exercises the production
  path unchanged. The **live** assertion — a revision bound to a configuration, a 409 with a count of 1 —
  is routed to **phase 13** by name. `OQ-063`. Its second clause (disable stops dispatch, catalogue stays
  readable) completes here in full.
- **SC5's first clause is asserted against a test-only adapter.** A-094 and OQ-016 fix the MVP at one
  adapter kind and there is no phase in which a second is built, so *"a non-OpenAI-shaped provider
  adapter"* is otherwise unassertable. 11-03 ships `RenamedFieldsAdapter` in the test suite and states in
  the test's own docstring what it proves (the boundary is real, a foreign shape reaches the caller as an
  OpenAI one, the SDK validates the output) and what it does not (that any particular real provider
  translates correctly). Its second clause — unmodelled fields at four depths — completes here in full.

---

## 2a. Requirement → plan. Each id in exactly one plan's `requirements:`.

| Requirement | Lock AC | Plan | Note |
|---|---|---|---|
| **PA-04** | provider-access AC-4 | 11-02 | Complete. Both paths, forced at the wire, plus the structural *no parameter exists* assertion |
| **PA-06** | provider-access AC-6 (**restated**, PITFALLS gap 2) | 11-04 | Complete against the restatement. The lock file's literal text asserts against two deleted columns |
| **PA-07** | provider-access AC-7 | 11-01 | Complete. Counted at the wire across four error classes plus a redirect |
| **PA-08** | provider-access AC-8 | 11-06 | Complete. 60 s asserted three ways; the event asserted by whole-column scan |
| **PA-09** | provider-access AC-9 | 11-03 | Second clause complete; first clause against a test-only adapter (see §2) |
| **PA-10** | provider-access AC-10 | 11-05 | Second clause complete; first clause against a stand-in FK, live form routed to phase 13 (`OQ-063`) |

**Six requirements, six appearances, no duplicates and no omissions.** No plan in this phase carries an
empty `requirements:` list — unusually, the six ROADMAP criteria and the six requirements map
one-to-one, so every plan owns exactly one of each.

---

## 3. Plans, waves and dependencies

| Plan | Wave | depends_on | What it is |
|---|---|---|---|
| **11-01** | 1 | — | **Tracer.** One interactive dispatch from a `provider_config_id` to a real socket and back, with the httpx client, the pinned transport, the address guard, the credential cache, the gate object, and exactly-one-request counted at the wire |
| **11-02** | 2 | 11-01 | Usage, always, including on a stream: the SSE reader, the forced `include_usage`, the terminal error as a value, and `provider_contract_violation` for a provider that stops reporting |
| **11-03** | 2 | 11-01 | ADR-0015's one translation: the adapter protocol, the identity that is a decision, the real-SDK oracle, and INT-016's catalogue |
| **11-04** | 3 | 11-01 | ADR-0046's two per-process caps, the two shed behaviours, both composition roots, and the restated AC-6's three claims |
| **11-05** | 3 | 11-01, 11-03 | INT-027's ten operations, the delete the database refuses with a catalogue-derived count, and the disable that stops dispatch |
| **11-06** | 4 | 11-01…11-05 | The 60 s rotation propagation, the event that says nothing, both callers' contract shapes, the metric surface, and the phase gate |

**No two plans in this phase have disjoint `files_modified`.** Every plan after the tracer touches
`src/prope/provider_access/dispatch.py`, and every one touches at least one of the two candidate metric
modules. 11-01, 11-04, 11-05 and 11-06 additionally share `src/prope/app.py` or
`tests/provider/_stub_provider.py`. **The orchestrator's disjointness check will never fan out, which is
correct.** Execution is serial regardless (ORCHESTRATION §7); the waves express correctness ordering only.

Waves 2 and 3 each contain two plans that depend only on the tracer and could in principle interleave.
They do not: 11-03 moves 11-02's `FORCED_UPSTREAM_KEYS` into the adapter's `compose_request`, and 11-05
consumes 11-03's `catalogue.py`. The ordering inside a wave is the numeric order.

---

## 4. `D-NN` decisions recorded. Range consumed: **D-180 … D-199** (all twenty).

| D | Plan | Decision | Reversibility |
|---|---|---|---|
| D-180 | 11-01 | `httpx` with a client cache keyed on **(config, scheme, host, port, validated address)**, not one client per dispatch. The validated address is part of the key, so a changed resolution is a cache **miss** rather than a reused connection | cheap |
| D-181 | 11-01 | The dispatch-time SSRF guard ships **now** with its rejection policy injected and its production default asserted; phase 12 owns PA-11's assertions rather than a second guard | cheap |
| D-182 | 11-01 | `dispatch()` returns a typed value for every upstream condition and raises **only** for a caller contract violation (unknown config id, no installed gate) | one-way in practice — two modules build against the return type |
| D-183 | 11-01 | The error-class vocabulary is **ADR-0017's eight**, because the lock file's own `failure_modes` use those names; INT-015's seven are the outlier. `OQ-060` | costly — two consumers branch on it |
| D-184 | 11-02 | Parameters are copied verbatim, then **exactly two** keys are overwritten (`stream`, `stream_options.include_usage`). `include_usage` is a **reporting** flag, not a generation parameter, which is how A-089 and A-097 are both true | cheap as code; one-way as a property |
| D-185 | 11-02 | A stream's terminal failure is a `DispatchError` **value on the iterator**, never an exception across the seam | one-way in practice — phase 21 is written against it |
| D-186 | 11-02 | The SSE reader is **byte-oriented** and tested against recorded byte streams sliced at hostile boundaries, including one byte at a time | cheap |
| D-187 | 11-03 | One `Adapter` protocol, one production implementation, and a **test-only** `RenamedFieldsAdapter` so AC-9's first clause is assertable in a one-adapter MVP | cheap |
| D-188 | 11-03 | Translation is mapping-in, mapping-out. Runtime code never constructs a typed model; the `openai` SDK is the **oracle only**, asserted by a source walk | one-way in practice |
| D-189 | 11-03 | The catalogue is soft in both directions: `[]` and never a raise; `available: false` and never a delete; a failed refresh leaves the store untouched | cheap |
| D-190 | 11-04 | One `asyncio.Semaphore` per (process, configuration), **sized once at first use**. A changed column takes effect at the next process restart; re-reading per dispatch is the coordination cost ADR-0046 rejected | cheap |
| D-191 | 11-04 | **Interactive fails fast; batch waits to its own `deadline_ms` and is shed on expiry.** All three of SC2, INT-015 and ADR-0046 hold under that shape. `OQ-064` | cheap for the behaviour; costly for the metric's meaning |
| D-192 | 11-04 | The two-process property is asserted as **two objects with no shared state** plus a sum measured at the provider, not by spawning a second interpreter | cheap |
| D-193 | 11-04 → 11-05 | Ten operations over four actions; six borrow `provider.configure` because the closed vocabulary has no `provider.read`, and `catalogue.read` would hand a credential's last four characters to Viewer and Reviewer. `OQ-061` | cheap |
| D-194 | 11-05 | The refusal is the **engine's**; the count is derived from `pg_constraint` **after** the refusal, with no registry table named in Prope's source and `test_no_sql_interpolation.py` kept green without an exemption. `OQ-062` | cheap for the count; one-way for the response shape |
| D-195 | 11-05 | Deleting a configuration writes **no** history event, stated at the route, rather than appending `provider_disabled` — which would put a false statement in an append-only log. `OQ-061` | one-way in the record |
| D-196 | 11-05 | The FK refusal is asserted now against a **real** foreign key the test creates; the live `registry.revision` assertion is routed to **phase 13** by name. `OQ-063` | cheap |
| D-197 | 11-06 | The 60-second claim is asserted **three ways** — the constant as a value, the mechanism through an injected clock, and once in real time with a short TTL | cheap |
| D-198 | 11-06 | The event's emptiness is asserted by scanning **every column** of the stored row, and `last_four` is in the forbidden set even though it is displayed and loggable | one-way — an event already written cannot be unwritten |
| D-199 | 11-06 | This phase declares only the metrics it increments, **drops all three declared identifier labels**, and routes the 14-metric set, the alert rules and the final label call to **phase 12** | cheap now, costly after a series is scraped |

---

## 5. `checkpoint:decision` blocks and their `UNCONFIRMED` adoptions

Under `mode: yolo` the planner writes the checkpoint in full and then adopts, per ORCHESTRATION §6. One
genuine one-way-ish decision surfaced in this phase and is recorded as a `checkpoint:decision` task:

| Where | Question | Adopted | Status | Reversibility |
|---|---|---|---|---|
| **11-01 Task 1** | The HTTP client's lifetime: one `AsyncClient` per dispatch (pinning trivially true, a TLS handshake per gateway call) vs a client cache keyed on the validated address (handshake paid once per target, a cache to manage) | **Option B — the keyed cache** (D-180) | `adopted: UNCONFIRMED` | **cheap** |

**Deciding argument, restated for the ledger:** Option A spends the product's latency budget in the one
place this module's own metric cannot see — a handshake lands in `upstream_duration_seconds`, not in the
10 ms `dispatch_overhead_seconds` this module is measured on — so the regression would be undetectable
from the dashboard built to detect it. Option B's failure mode on a wrong key is a cache **miss**, which
costs a handshake rather than a connection to the wrong host.

**Every `<human-check>` in the six plans is also an adoption the user may reverse**, and the substantive
ones are D-181, D-183, D-184, D-185, D-187, D-189, D-190, D-191, D-193, D-194, D-195, D-196, D-197,
D-198 and D-199 — each carried by an `OQ` where it is a spec conflict and by a `<human-check>` line where
it is a judgement. **No decision in this phase would violate an ORCHESTRATION §2 non-negotiable**, and
none is blocked.

---

## 6. Out-of-scope discoveries, and things routed rather than absorbed

| Item | Why it is not phase 11's | Routed to |
|---|---|---|
| **PA-01** — the credential-never-returned **corpus sweep** across every endpoint, error body, log line, metric label and history event | The ROADMAP gives it to phase 12. 11-05 asserts the subset the ten routes can prove and 11-01/11-06 assert the log and event surfaces; the corpus scan is one artefact and belongs to one phase | **Phase 12** |
| **PA-11** — the **save-time** SSRF refusal and the restated AC-11 (a resolver answering public then private, asserting the connection went to the first) | Phase 12's SC2. 11-01 ships the dispatch-time guard as code (D-181) so no hole is open for a phase | **Phase 12** |
| **PA-12** — the KEK readiness gate, `kek_unavailable`, and a dispatch failure class distinct from every provider-origin class | Phase 12's SC3. `/readyz` today is the database alone (phase 2's D-16, phase 3's final form); this phase does not touch it | **Phase 12** |
| **The full 14-metric set, all six alerts, and `deploy/prometheus/rules/provider_access.rules.yml`** | The ROADMAP routes `observability_requirements.metrics` to phase 12. 11-06 declares only what it increments and writes the omission notes | **Phase 12** |
| **The three declared identifier metric labels** — `upstream_duration_seconds{provider_config_id, upstream_model}`, `credential_rejected_total{provider_config_id}`, `model_unavailable_total{provider_config_id}` | Same shape phase 9 raised as `OQ-053` and resolved per-metric. Phase 11 drops all three with a written note; phase 12 owns the final call and may reinstate one with an argument | **Phase 12** |
| **`test_plan.load`'s three clauses** — 50 rps interactive with overhead p95 < 10 ms and cache hit ratio > 99%; the concurrent 100-case batch; 200-chunk streaming at 10 concurrent streams with per-chunk overhead p95 < 1 ms | This phase asserts the **correctness** halves (the caps, the sum, the admission latency under saturation) and observes but does not gate on the timing halves. The load block belongs with the milestone's resilience phase | **Phase 12** |
| **`test_plan.chaos`'s five clauses** — KEK removed from a running process; provider killed mid-stream; 429 storms; property-history unavailable during a rotation; a database connection held open but unresponsive during a decrypt-cache miss | Two are asserted here (mid-stream kill in 11-02, the rotation half-commit in 11-06). Three are phase 12's | **Phase 12** (three of five) |
| **AC-13 (owed, PITFALLS gap 1)** — KEK re-wrap V1 → V2: every row reports `kek_version=2`, every credential still decrypts, V1 can be removed, no plaintext written | PITFALLS assigns it to *"10 or 12"*. It is a key-management operation, not a seam | **Phase 10 or 12** — and if phase 10 did not take it, **phase 12 must** |
| **The live `registry.revision` delete refusal** | `registry.revision` is created in phase 13 (`OQ-063`, D-196) | **Phase 13** |
| **The gateway's half of streaming** — stripping the extra usage-only chunk from a stream whose caller did not ask for usage (ADR-0015's last consequence) | The gateway is phases 19-21. 11-02 states the consequence at the forcing site so phase 21 finds the sentence | **Phase 21** |
| **The `/metrics` per-process gap (`OQ-026`)** — `worker` serves no HTTP, so every provider-access metric incremented in `worker` (batch dispatch, batch admission, batch shed) is unscrapable | An existing, recorded open question this phase makes worse rather than creates: `shed_total{priority=batch}` — which `ProviderBatchStarved` alerts on — is incremented **only in `worker`**. Raised here as an addition to `OQ-026`'s list, not as a new question | **Phase 12**, with `OQ-026` |
| **The React SPA that consumes INT-027** | PITFALLS gap 3: no lock file owns it and it has no milestone | Unowned, user decision |

---

## 7. The ledger phase 12 inherits for its M4 §9a audit

Phase 12 closes M4 and therefore walks `docs/modules/provider-access.lock.yml`'s `acceptance_criteria`
and all seven `test_plan` categories clause by clause. This is what phase 11 leaves it, so the audit
starts from evidence:

| Lock clause | Phase 11's disposition |
|---|---|
| AC-4 | **asserted** — `tests/unit/test_usage_always_requested.py`, plus the `ast` assertion that no parameter could turn it off |
| AC-6 (restated) | **asserted** — `tests/load/test_batch_yields_to_interactive.py`, three claims |
| AC-7 | **asserted** — `tests/unit/test_exactly_one_attempt.py`, counted at the wire |
| AC-8 | **asserted** — `tests/integration/test_credential_rotation_effective.py` + `tests/security/test_rotation_event_carries_no_credential.py` |
| AC-9 | **asserted**, first clause against a test-only adapter (D-187) |
| AC-10 | **asserted**, first clause against a stand-in FK (D-196); live form routed to phase 13 |
| AC-1, AC-2, AC-3, AC-5, AC-11, AC-12, AC-13 | **not phase 11's** — phases 10 and 12 |
| `test_plan.unit` — the classification table | **phase 10's** (PA-05) |
| `test_plan.unit` — response and chunk normalisation incl. unknown-field pass-through | **asserted** — 11-03 |
| `test_plan.unit` — the usage parser against exact field names | **asserted** — `tests/unit/test_usage_field_names.py` |
| `test_plan.unit` — envelope encrypt/decrypt/rewrap | **phase 10's**; the **rewrap** half is AC-13 and may be unowned (see §6) |
| `test_plan.unit` — the credential cache's TTL arithmetic | **asserted** — `tests/provider/test_credential_cache_ttl.py` |
| `test_plan.unit` — admission-gate accounting | **asserted** — `tests/provider/test_admission_gate.py` |
| `test_plan.unit` — base-URL validation | **partially asserted** — 11-01 asserts the production default refuses loopback; the full form is PA-11, **phase 12** |
| `test_plan.integration` — rotation and its 60 s effectiveness | **asserted** — 11-06 |
| `test_plan.integration` — delete refused while bound | **asserted against a stand-in** — 11-05 |
| `test_plan.integration` — catalogue discovery, refresh, manual add, a model going unavailable | **asserted** — `tests/provider/test_model_catalogue.py` |
| `test_plan.integration` — the history event in the same transaction | **asserted** — 11-05 and 11-06 (including the half-commit provocation) |
| `test_plan.integration` — permission checks on every management endpoint | **asserted** — `tests/integration/test_provider_management_routes.py` |
| `test_plan.integration` — configuration create with a passing and a failing probe | **phase 10's** (PA-03) |
| `test_plan.integration` — the two internal contracts from the calling side | **asserted** — `tests/contract/test_dispatch_seam_from_both_callers.py` |
| `test_plan.contract` — `dispatch()` and `get_model_catalogue()` parsed with a real SDK model | **asserted** — 11-03 and 11-06 |
| `test_plan.e2e` — the whole BYOK journey | **not asserted anywhere.** It spans prompt-registry (13-15), the gateway (19-21) and evaluation (16-18). **Unowned as a single test; phase 12 must route or declare it** |
| `test_plan.load` — three clauses | **routed to phase 12** (§6) |
| `test_plan.security` — six clauses incl. T-025…T-028 | **partially asserted**: T-026's echoing provider in 11-01, the credential-never-returned subset in 11-05. T-025, T-027, T-028's corpus form → **phase 12** |
| `test_plan.chaos` — five clauses | **two asserted** (11-02, 11-06), **three routed to phase 12** |

---

## 8. Assumptions this phase makes about phases it cannot read

**Phase 10's plans did not exist when this phase was planned.** Every claim below is a claim about
`docs/modules/provider-access.lock.yml`, not about code, and each is paired with a re-ground instruction
in the plan that depends on it. If one is wrong, the executor **reports drift** rather than working
around it.

| Assumed | Where it matters | If wrong |
|---|---|---|
| `src/prope/provider_access/` exists with the three tables mapped | every plan | 11-01 cannot start; report and stop |
| A decrypt path exists and returns a plaintext `str` | 11-01, 11-06 | `credentials.py` is declared conditionally in 11-01 |
| A classification table exists producing `DispatchError` with four separate facts | 11-01 … 11-06 | `errors.py` declared conditionally in 11-01, 11-02, 11-03 |
| The table carries `provider_contract_violation` | 11-02, 11-03 | 11-02 may add **that one member** and must report it (`OQ-060`) |
| `provider_config` carries `interactive_concurrency` (24) and `batch_concurrency` (8) | 11-04 | A conditional migration is declared in 11-04, named `000N_…`, `down_revision` read from `uv run alembic heads` |
| Phase 10 shrank `EXPECTED_ABSENT_SCHEMAS` when it created the `provider` schema | every plan (a red suite otherwise) | 11-01 reports it as drift and **does not** edit another phase's constant |
| `httpx` may already be pinned by phase 10's probe | 11-01 | Task 1 adds only what is missing and records the resolved versions |
| A verification probe exists, with its own upstream call and possibly its own usage parser and model-list call | 11-01, 11-02, 11-03 | Those calls **move** into the shared client / parser / adapter rather than being duplicated |

**Phases 5, 7, 8 and 9 are planned but not built.** `append()`, `may()`, `management_api.py`,
`refusal_for()` and `require_usable_session` are claims about *their plans*. `get_sessionmaker` lives in
`src/prope/call_ledger/api.py` **today** and phase 8's D-116 moves it; 11-05 says to import from wherever
it actually is and to say loudly if the move has not happened, because importing call-ledger's copy would
give provider-access a dependency on a sink.

---

## 9. The planner's self-check — the five things the deleted exec-critic would have checked

Run by the planner against its own six files. Every result is an agent judgement from reading, not a
detector.

1. **Every ROADMAP success criterion is owned by exactly one plan.** ✅ §2's table: SC1→11-02, SC2→11-04,
   SC3→11-01, SC4→11-06, SC5→11-03, SC6→11-05. Six criteria, six plans, no criterion in two plans and
   none in none.
2. **Every requirement id appears in exactly one plan's `requirements:`.** ✅ PA-04 (11-02), PA-06
   (11-04), PA-07 (11-01), PA-08 (11-06), PA-09 (11-03), PA-10 (11-05). Verified by reading the six
   frontmatter blocks; the union is exactly the phase's six and the intersection of any two is empty.
3. **Every file named in any task's `<action>` or `<files>` appears in that plan's `files_modified`.** ✅
   after four corrections made during this check, each recorded here because the correction is the
   evidence the check ran:
   - **11-02** — Task 1's action says *"report it as drift and add it in this plan"* about
     `src/prope/provider_access/errors.py`, which had been listed as read-only. Added to
     `files_modified` as conditional, with the addition bounded to the one ADR-0017 member.
   - **11-03** — Task 1's action can require the same file for a translation-failure class. Added as
     conditional, and added to Task 1's `<files>` along with the two observability modules its action
     already touched.
   - **11-04** — Task 3's action begins *"`_stub_provider.py` gains a concurrency observer"* and the file
     was absent from `files_modified`. Added.
   - **11-06** — Task 4's action says *"extend `tests/broker/test_publish_confirm_failures.py`'s existing
     registry walk in place"* and the file was absent. Added as conditional, with the alternative
     (leave it alone, record the divergence) stated.
   `deferred-items.md` is deliberately **not** declared in 11-06's list: it is a planner-seeded,
   executor-appended artifact rather than a code file, which is the convention phase 9 recorded.
4. **Every symbol, fixture, constant and file the plans tell an executor to extend exists today, or is
   created by an earlier plan in this phase, or is specified by an earlier phase's plans.** ✅ Verified by
   reading the tree, with the results below. Nothing is assumed into existence.
   - **Exists today, read on disk:** `pyproject.toml` (incl. the registered `load` marker and the
     *deliberately absent* `addopts`, phase 3's D-45.2); `src/prope/app.py` (`lifespan`, `create_app`,
     `/healthz`, `/readyz`, `/metrics`); `src/prope/worker.py` (`run_worker`, `main`, the three job
     constants); `src/prope/db/session.py` (`workspace_transaction`, `SET_TENANT`);
     `src/prope/db/engine.py` (`Settings`, `build_engine`, `build_sessionmaker`);
     `src/prope/observability.py` (`LOGGABLE_FIELDS`, the bucket-edge rule, D-40's define-at-import
     paragraph); `src/prope/session_auth.py` (`assembled_routes`, `declares_action`, `declared_action`,
     `ManagementAction`, `require_session`, `ManagementRefusal`, `Session`); `src/prope/supervisor.py`;
     `tests/conftest.py` (`postgres_container`, `migrate_engine`, `app_sessionmaker`, `report_engine`,
     `rabbitmq_container`, `amqp_url`, `management_url`, the autouse truncate and purge fixtures);
     `tests/integration/_asgi.py` (`call`, `Response.code`);
     `tests/architecture/test_route_table.py` (`EXPECTED_ROUTES`, **8 entries today**);
     `tests/architecture/test_no_sql_interpolation.py`; `tests/architecture/test_tenant_coverage.py`
     (`DECLARED_SCHEMAS`, `GLOBAL_TABLES`, `EXPECTED_ABSENT_SCHEMAS`);
     `tests/broker/test_publish_confirm_failures.py` (`test_workspace_id_is_never_a_metric_label`,
     `test_the_two_extended_label_sets_stayed_closed_at_their_declared_size`); `tests/load/__init__.py`;
     `tests/security/__init__.py`; `tests/unit/__init__.py`; `alembic/ddl.py`.
   - **Created by an earlier plan in this phase:** `tests/provider/__init__.py` and
     `tests/provider/_stub_provider.py` (11-01); `tests/contract/__init__.py` and `adapters.py`,
     `catalogue.py` (11-03); `streaming.py`, `usage.py` (11-02); `references.py`, `api.py`,
     `schemas.py`, `configurations.py` (11-05). Every consumer declares the producing plan in
     `depends_on`.
   - **Specified by an earlier phase's plans, not code:** `src/prope/property_history/append.py`'s
     `append(session, event) -> str` and `HistoryEventDraft` (phase 5, plan 05-01); the 31-row
     `history.history_action_registry` seed including the four provider actions with **empty**
     `detail_keys` (phase 4, plan 04-01); `may(session, actor, action, subject) -> bool` with `Actor` /
     `Subject` in `src/prope/access_control/permissions.py` (phase 7, plan 07-02); the 25-action
     `role_permission` seed containing all four provider actions (phase 7, plan 07-01);
     `src/prope/management_api.py` holding `ErrorCode`, `ManagementRefusal`, `get_sessionmaker` and
     `install_error_envelope` (phase 8, plan 08-01, D-116); `refusal_for` / `is_visible` in
     `src/prope/access_control/refusals.py` and `require_usable_session` in `session_auth.py` (phase 9,
     plan 09-01, D-131/D-133/D-134); `SHARED_ACTIONS` / `ACTION_FREE_ROUTES` / `UNAUTHENTICATED_ROUTES`
     in `test_route_table.py` (phase 8). Every one is named in the plan's re-ground block with an
     instruction to follow the code rather than the plan.
   - **Assumed from phase 10 and explicitly hedged:** §8's table. Phase 10's plan files did not exist;
     both candidate module names are declared in `files_modified` wherever the choice matters.
5. **No plan hardcodes an Alembic `down_revision`, gates on `ruff format --check`, references a
   `gsd-core` path, or puts the whole-suite `uv run pytest -q` anywhere but the last plan's
   `<verification>`.** ✅
   - Exactly one migration is declared anywhere in the phase — 11-04's **conditional**
     `alembic/versions/000N_provider_per_process_concurrency_caps.py` — and both its `files_modified`
     comment and its task action say the `000N_` prefix is a placeholder and that `down_revision` is read
     from `uv run alembic heads` and **never** hardcoded.
   - No plan mentions `ruff format`; every lint gate is `uv run ruff check src/ tests/ alembic/`, and
     each plan's `<context>` states that `ruff format --check` is not a gate and fails repo-wide on
     Broken Window #1.
   - No `<execution_context>` block and no `$HOME/.claude/gsd-core/...` path appears in any of the six
     files.
   - `uv run pytest -q` across the whole suite appears **only** in 11-06 — in Task 4's `<verify>` and in
     `<verification>`. Every other plan's `<verify><automated>` names targeted test paths.
   - No plan adds mypy, a `typecheck` target, a scheduler, a second broker queue, broker-based cache
     invalidation, `tsvector`, or a fifth `SECURITY DEFINER` function. 11-06 asserts the *absence* of a
     broker import under `src/prope/provider_access/` structurally.

**One residual this planner cannot close and states rather than hides.** Phase 10's plans did not exist
at planning time, so §8's eight assumptions are the phase's real risk surface, and the compensating
control is a re-ground block at the top of every plan plus conditional declarations wherever a name was
genuinely unknowable. **If phase 10 shipped ADR-0016's superseded `max_concurrency` /
`reserved_interactive` columns, or an HTTP client with `follow_redirects` unset, phase 11's executors
will be the first stage in this orchestration to see it** — there is no pre-execution stage left that
would have.
