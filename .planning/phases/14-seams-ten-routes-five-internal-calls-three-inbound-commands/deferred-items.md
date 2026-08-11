# Phase 14 — deferred items, mappings, and the planner's own self-check

**Phase:** 14 — Seams: ten routes, five internal calls, three inbound commands · **Module:** prompt-registry ·
**Milestone:** M5 — this phase does **not** close it (phase 15 does) · **Depends on:** Phase 13

Written by the phase planner under the MINIMAL PROTOCOL (ORCHESTRATION §10a). There is no CONTEXT,
RESEARCH, PATTERNS, DISCUSSION-LOG or COVERAGE artifact for this phase, and **no critic reviewed these
plans before execution.** Everything the deleted artifacts carried lives in the plans' `<objective>`
sections; everything the deleted *checks* would have caught is self-checked in §9 below. Every judgement
in this file is an **agent judgement made by reading files** — no deterministic detector exists in this
environment and nothing here is detector output.

Executors append to this file. Do not renumber the sections.

---

## 1. The phase's whole `docs/` footprint

`docs/` is read-only with exactly one exception: **creating** `docs/brainstorm/open_questions/OQ-NNN.md`.
The allocated range was **OQ-075 through OQ-079** and **all five were consumed.** Every one is a real
spec conflict found while planning; none is a placeholder. The orchestrator's brief said the highest id
on disk was OQ-054; **that was stale** — `OQ-070` … `OQ-074` (phase 13's planner) and `OQ-085` (another
concurrent planner) were already present when this range was allocated. None of them was touched.

| Id | One line | Severity | Named against |
|---|---|---|---|
| **OQ-075** | **`resolve()`'s registered contract is under-specified in two ways and both fail silently.** INT-009's *Request carries* names no workspace, and a `prope_app` read with no `app.workspace_id` returns **zero rows rather than an error** (ADR-0045) — so a workspace-less `resolve()` would answer `unknown_model` for every model name in the product and nothing would fail. Separately, a **pin** produces a miss that is neither declared reason, and INT-009's stated justification for the pin rule (*"this seam reads a pointer the constraint has already guaranteed"*) is true of the released pointer and **false of a pin** | high | `interfaces.md` INT-009 (*Request carries*, and the pin paragraph); lock `apis.exposes` (`resolve(model_name, pin)`); lock `observability_requirements.metrics` (`resolve_miss_total`'s two label values). Same shape as phase 2's `OQ-020` |
| **OQ-076** | **`set_revision_status` is told to validate a transition table nobody wrote, and a `decision_id` it may not read.** ADR-0008 fixes the vocabulary and A-066 fixes one edge; **no authority declares the legal set of moves**, while INT-012 says *"the provider validates the transition"*. And INT-012's *"raises on a `decision_id` that does not exist"* requires reading release-control's tables — a **forbidden dependency**, the exact edge whose absence is the cycle break | high | `interfaces.md` INT-012 (validation clause + failure semantics); `docs/adr/0008` Decision and Consequences; lock `apis.exposes` (`set_revision_status`); lock `forbidden_dependencies` (release-control) |
| **OQ-077** | **A-050's caps are a `413` in one place and a `422` in another, and only one of them can carry the size.** `failure_modes` says *"413 rate on the revision endpoint"*; INT-024 says *"422 for validation with `details`"*; A-045 says there is one envelope. The cap is on **one JSON field**, not on the HTTP entity, and A-050 requires *"a message naming the actual size"*, which a bare 413 cannot carry | medium | lock `failure_modes` (last row, `detection`); `interfaces.md` INT-024 failure semantics; `A-045` |
| **OQ-078** | **The prompt path parameter is spelled two ways, and the test that would catch a real duplicate compares literal strings.** The lock spells `{prompt_id}` in all ten `apis.exposes` strings; INT-024, INT-025 and the ROADMAP spell `{id}`; call-ledger already ships `{id}`. The lock's own ROUTE-TABLE UNIQUENESS rule asserts *no duplicate (method, path) pair* over **four** modules sharing the prefix — and two spellings make a genuine duplicate invisible to it | medium | lock `apis.exposes` (ten strings) and `security_requirements` (ROUTE-TABLE UNIQUENESS); `interfaces.md` INT-024/025/026/029; `ROADMAP.md` phase 14 SC3 |
| **OQ-079** | **`access_level` has no permission that changes it and no disjunct that reads it.** A-115 has no member for INT-001's `prompt.change_access`, and its nearest name `prompt.grant` was assigned to access-control's grants routes by phase 8. Separately, INT-002's declared caller query has **two** disjuncts while phase 9's `is_visible` has **three** — the third being `access_level == "workspace" and is_active_member`, whose membership row this module may not read | high | `A-115` (25-name list); `interfaces.md` INT-001 caller table and INT-002 *Returns*; lock `apis.exposes` (PATCH); `access-control.lock.yml` permission matrix |

**Nothing else under `docs/` was written or edited.** No lock file, no ADR, no `interfaces.md` line, no
assumption file, no `adr_index.md` entry. Every plan's `<verification>` block asserts
`git status --porcelain docs/` produces no output.

**`.planning/` files this phase's planner did NOT touch and its executors must not:**
`ORCHESTRATION.md`, `ORCHESTRATION-DECISIONS.md`, `WINDOWS.md`, `ROADMAP.md`, `REQUIREMENTS.md`,
`STATE.md`, `research/PITFALLS.md`, `BSP-LINK.md`, and every other phase's directory. **Five other
planners and a live phase-3 execution ran concurrently** with this one; a write outside this directory is
a race.

---

## 2. ROADMAP success criterion → plan. Each owned by exactly one.

| # | Success criterion (ROADMAP, Phase 14) | Owning plan | Proven by |
|---|---|---|---|
| 1 | `resolve()` returns the released revision's full binding — body, provider config, model, parameters, fallback answer, version ID — at p95 under 10 ms over 1,000 requests | **14-05** | `tests/load/test_resolve_latency.py` (AC-4's declared `test_ref`; 1,000 properties, warm pooled engine, order statistics) · `tests/integration/test_resolve_binding.py` (all seven binding fields, field by field) |
| 2 | `resolve()` distinguishes *model name unknown* from *model name known, nothing released* in its miss result, so a withdrawal is visible in `resolve_miss_total` | **14-05** | `tests/integration/test_resolve_miss_reasons.py` (both reasons as counter **deltas**, each paired with an assertion that the other did not move, plus the hit → `no_release` withdrawal transition) |
| 3 | `GET /api/v1/prompts/{id}/activity` returns events from all four writing modules in one indexed read on `(workspace_id, scope_prompt_id, seq DESC)` | **14-04** | `tests/integration/test_activity_endpoint.py` (four modules' actions, six target types, `seq` beating a tied timestamp, three exclusions each with a positive control) · `tests/integration/test_activity_is_one_indexed_read.py` (`EXPLAIN` over a 2,000-event corpus: the named index used, no `Seq Scan`, **no join node of any kind**) |
| 4 | `set_revision_status`, `set_released_revision` and `clear_released_revision` are the only paths that change status or the pointer, and each validates the transition here | **14-06** | `tests/integration/test_registry_commands.py` (the 3×3 transition matrix, the compare-and-set, the constraint-driven refusal, the caller's-transaction test) · `tests/architecture/test_only_commands_write_status_and_pointer.py` (every `text()` statement in `src/prope/` parsed, every governed write attributed, with a pinned count) · `tests/integration/test_no_route_moves_status_or_pointer.py` (all ten routes and both read seams driven, full before/after snapshot) |

**Four criteria, three owning plans, none claimed twice and none unclaimed.** SC1 and SC2 are both
14-05's because they are two properties of one function and splitting them would be a layer slice —
implementation in one plan, its measurement in another — which the phase's slicing rule refuses.

**Plans 14-01, 14-02 and 14-03 own no ROADMAP success criterion.** They own the ROADMAP's **Spec**
routing for this phase — INT-024's ten HTTP routes, `apis.consumes` (`may`, `visible_subject_filter`,
`get_model_catalogue`), the five `outputs` events reaching history through phase 13's commands, and
INT-016 — none of which any success criterion restates. That is the same posture phase 12 recorded for
its own three non-SC plans.

---

## 2a. Requirement → plan. Each id in exactly one plan's `requirements:`.

| Requirement | Lock AC | Plan | Note |
|---|---|---|---|
| **PR-04** — *The gateway resolves a bare model name to the released revision's full binding at p95 under 10 ms* | prompt-registry **AC-4** | **14-05** | The phase owns exactly one requirement and exactly one plan carries it. Plans 14-01, 14-02, 14-03, 14-04 and 14-06 all declare `requirements: []` |

`.planning/REQUIREMENTS.md` line 225 maps PR-04 to M5 / Phase 14 / prompt-registry AC-4 / Pending. **No
other requirement id is claimed by this phase**, and no plan here ticks PR-01, PR-02, PR-03, PR-05 or
PR-06 — those are phases 13 and 15.

---

## 3. UNCONFIRMED adoptions — every one, with its reversibility

Under `mode: yolo` a one-way decision is written out in full, **adopted**, marked `UNCONFIRMED`, and
recorded here rather than stopping the run (ORCHESTRATION §6). None of the adoptions below would violate
a §2 non-negotiable under either option; the one that came closest — the transition table — is adopted in
the direction that keeps the audit trail complete.

| # | Adoption | Plan | Reversibility | What a human is being asked |
|---|---|---|---|---|
| 1 | **`resolve()` takes `workspace_id`**, which INT-009's declared request does not mention | 14-05 · D-256 | **costly** — the signature is what phases 19-21 are written against | Confirm the parameter, or name the mechanism that supplies a tenant to a read subject to a deny-by-default policy (`OQ-075`) |
| 2 | **`MissReason` gains a third value, `pin_unresolvable`**, beyond the lock's declared two | 14-05 · D-257 | **costly** — the miss vocabulary is what phase 19 branches on and what the alerting reads | Confirm, or say which declared value a bad pin should be counted as, knowing either choice makes one of them mean two things (`OQ-075`) |
| 3 | **`outcome` is read as three disjoint values** — `pinned` = a successful pin resolution, `miss` = any miss | 14-05 · D-257 | cheap | Confirm the reading; the lock gives `hit/miss/pinned` with no note and the obvious alternative overlaps |
| 4 | **`Approved` is terminal**; three legal transitions, every self-transition raises | 14-06 · D-259, Task 1 checkpoint | **one-way** — a table becomes true the moment release-control is written against it and rows exist under it | Confirm that a mistaken approval is corrected by a **new revision**, or say release-control needs an un-approve action — its own permission, its own name in the closed 31-action registry, a migration plus a restart (`OQ-076`) |
| 5 | **`decision_id` / `release_id` are accepted, logged, stored nowhere**, and their existence is not validated | 14-06 · D-258 | cheap | Confirm the linkage lives only in release-control's own record plus ADR-0051's reconciliation query (`OQ-076`) |
| 6 | **A-050's caps refuse with `422`, not the lock's `413`** | 14-03 · D-253 | **costly on the wire** — a client that learned one code breaks on the other | Confirm 422; the `failure_modes` row's `detection` line then needs rewording to a rate that can be non-zero (`OQ-077`) |
| 7 | **The path parameter is `{prompt_id}`**, following the lock rather than INT-024 | 14-01 · D-246 | cheap here, **costly across the build** after phase 17 mounts more `/api/v1/prompts/…` routes | Confirm one spelling project-wide, or the uniqueness test compares strings that route identically and differ literally (`OQ-078`) |
| 8 | **`access_level` changes ride on `prompt.edit`**; `owner_id` changes get a second `may()` for `prompt.transfer_owner` | 14-03 · D-252 | cheap on the route, **costly on the vocabulary** | Confirm, or mint `prompt.change_access` and accept a migration in `role_permission`'s `CHECK` (`OQ-079`) |
| 9 | **The visibility predicate has two disjuncts**, not three; a `workspace`-level prompt is invisible to a plain member | 14-01 · D-245 | cheap; **fails closed** | Confirm the two-disjunct reading INT-002's own text specifies, or say where membership comes from given this module may not read `access.workspace_member` (`OQ-079`) |
| 10 | **A new revision on a `Retired` prompt is allowed** | 14-03 · Task 2 | cheap | No authority forbids it and the revision cannot be released. Confirm, or make it a refusal and name the code. **Product question, not a spec conflict — deliberately not given an OQ** |
| 11 | **`resolve()` and the three commands do not trip `unfiltered_query_total`** | 14-01 · D-243 | cheap on the mechanism, **one-way on the alert** — once `RegistryUnfilteredQuery` has been seen firing in normal operation nobody trusts it again | Confirm that the tripwire counts the person-facing read paths only. Getting this wrong makes phase 15's SC2 unsatisfiable on day one |

Items 1–10 are owed to `14-UAT.md` as numbered human-verification items, and to
`.planning/ORCHESTRATION-DECISIONS.md` as one row each. **The orchestrator applies those two writes**;
this planner did not touch either file (§1).

---

## 4. Waves, and what may actually fan out

| Plan | Wave | Runs alone? | Why |
|---|---|---|---|
| 14-01 | 1 | — | Tracer. Nothing else in the phase can start until `api.py`, `schemas.py` and `repository.py` exist |
| 14-02 | 2 | no | Read routes. `files_modified` disjoint from 14-05's |
| 14-05 | 2 | **YES — §7a(a)** | Asserts a latency number: p95 < 10 ms over 1,000 resolutions. ORCHESTRATION §7a names phase 14's `resolve()` p95 explicitly. It also seeds 1,000 rows and runs `ANALYZE` on shared tables — §7a(b) |
| 14-03 | 3 | — | Write routes. Edits `api.py`, so it cannot share a wave with 14-02 or 14-04 |
| 14-04 | 4 | **YES — §7a(b)** | Seeds ~2,000 history events and runs `ANALYZE history.history_event`. Statistics survive the truncate fixture, so a concurrent test could see a differently-planned query and fail for a reason that has nothing to do with it |
| 14-06 | 5 | — | Commands, the enumeration, and the phase gate. Must be last: the enumeration inspects the finished package and the sweep drives all ten routes |

**Four of the six plans edit `src/prope/prompt_registry/api.py`** (14-01 → 14-04), which is why they sit
in four successive waves. That is D-241's stated cost and it is bookkeeping honesty rather than
wall-clock: execution is serial regardless (ORCHESTRATION §7). **The one genuinely concurrent pair —
14-02 and 14-05 in wave 2 — is defeated by 14-05's run-alone requirement**, so in practice this phase
executes strictly in plan order.

**`files_modified` disjointness within wave 2**, checked by hand:

- 14-02: `api.py`, `schemas.py`, `repository.py`, `search.py`, `management_api.py`,
  `call_ledger/schemas.py`, `session_auth.py`, `tests/architecture/test_route_table.py`,
  `tests/prompt_registry/__init__.py`, two integration modules.
- 14-05: `resolve.py`, `__init__.py`, `domain.py`, `prompt_registry/observability.py`,
  `tests/prompt_registry/corpus.py`, three integration modules, one load module.
- **Intersection: empty.** 14-05's test helpers live in a **new** `tests/prompt_registry/corpus.py`
  specifically so it cannot collide with 14-02's edits to `tests/prompt_registry/__init__.py`; 14-05
  reads that file and is forbidden from editing it.

---

## 5. Cross-phase dependencies the executor must know before starting

Everything phase 14 assumes about phases 4 through 13 is a claim about **their plans**, not about code.
Every plan opens with a re-ground block naming the files to read first. The five that would cost the most
if they are wrong:

1. **`get_diff` must exist** from phase 13 (its SC2 / PR-02). Phase 13's plans 13-04 through 13-06 were
   **still being written** when this phase was planned — only 13-01, 13-02 and 13-03 existed on disk. Plan
   14-02's re-ground block carries an explicit contingency: if no diff function exists, mount the other
   three routes, leave the diff route unmounted, drop its pair from `EXPECTED_ROUTES` so the table test
   stays **green rather than red**, and report the blocker. **Do not write a second `difflib`
   implementation.**
2. **`ix_history_event_workspace_id_scope_prompt_id_seq`** must exist on `history.history_event` with
   `(workspace_id, scope_prompt_id, seq DESC)` — phase 4's plan 04-01 creates it. Plan 14-04 Task 3
   **verifies rather than assumes** and, if it is absent, **reports it as an SC3 blocker and does not
   create it**: it is property-history's table and another phase's migration.
3. **The 31 seeded action names** in `history.history_action_registry`. Plan 14-04's four-module seed must
   use real names — `history_event` has a composite foreign key to the registry (phase 4's D-57) — and if
   one of the lock's five registry events (`property_created`, `revision_created`, `owner_changed`,
   `access_level_changed`, `retired`) is **absent from the seed**, that is a finding for the SUMMARY, not
   a registry row to insert. ADR-0038 makes a thirty-second action a migration plus a restart.
4. **D-116's shared surface.** `ErrorCode`, `ManagementRefusal`, `PageRequest`, `get_sessionmaker`,
   `install_error_envelope` and possibly `ManagementAction` are supposed to have moved from
   `prope.call_ledger.schemas` / `prope.session_auth` into `src/prope/management_api.py`. **If they have
   not, prompt-registry importing them from call-ledger's package creates the exact edge plan 14-01's own
   verification greps against**, and which release-control's owed AC-14 import-linter contract would
   later fail the build on. Plans 14-01, 14-02 and 14-03 all say: **complete the move**, do not create
   the edge, and record which branch was taken. `src/prope/call_ledger/api.py` and
   `src/prope/call_ledger/schemas.py` are declared in `files_modified` for exactly that contingency —
   including for `_constraint_name`, which plan 14-03 Task 2 Step 0 relocates.
5. **`vocabulary.Action`'s member names.** Every `ManagementAction` member this phase adds takes its value
   from that enum (D-244), which `role_permission.action`'s `CHECK` mirrors. **If a member A-115 declares
   is missing — `prompt.transfer_owner` and `revision.create` are the two at risk — stop and report it**
   rather than adding one: a member added from this phase is a schema change in another module.

---

## 6. Out-of-scope discoveries, and what is routed where

| Discovery | Disposition |
|---|---|
| **The owed AC-7** (`search_text` absent from **every** response body, by whole-response scan) | **Phase 15.** Plans 14-01 and 14-02 ship the single-endpoint and per-plan forms and name AC-7 by id, so phase 15 generalises a shape rather than inventing one |
| **The owed AC-10 and AC-11** (substring semantics end to end; the corpus decision) | **Phases 13 and 15**, per PITFALLS gap 1. Plan 14-02 Task 3 asserts both **at the route**, because that is the only place they are observable end to end, and explicitly claims no ownership of the criteria |
| **PITFALLS gap 5: *"The registry's own Activity endpoint has no AC"*** | **Closed by this phase in substance.** ROADMAP SC3 is the criterion the lock never wrote as a row, and plan 14-04 asserts both its halves. Recorded here so the gap-5 line can be struck rather than inherited |
| **PITFALLS gap 5: *"Search and filter has no acceptance criterion"*** | **Still open.** Plan 14-02 asserts the semantics; the p95 < 500 ms performance row is **not** asserted by this phase and no plan claims it. Routed to **phase 15**, which owns the module's remaining `test_plan.load` clause, or to the M5-closing audit under ORCHESTRATION §9a |
| **`test_plan.load`'s *search p95 < 500 ms* at 1,000 × 20** | **Not asserted here.** Plan 14-02 wires `search_duration_seconds` with a `0.5` bucket edge so the measurement is possible; the load run itself is unclaimed. **Phase 15 closes M5 and §9a binds it to audit the lock's `test_plan` clause by clause** |
| **`test_plan.e2e`** — register → edit twice → diff → release-control approves and releases → gateway resolves | **Cannot run before phase 21.** Four of its steps cross release-control and the gateway. Same shape as provider-access's `OQ-066`; routed to **phase 23 or 24**, whichever the M8 planner takes |
| **`test_plan.chaos`** — provider-access unavailable at editor open; concurrent revision writes; connection lost mid-create | Concurrent writes are **phase 13's** (13-02's conflict truth). The provider-access clause is partly asserted by plan 14-03's `catalogue_unavailable` case. The mid-create clause is phase 13's atomicity assertion. **No clause is claimed by phase 14 and none is silently dropped** |
| **`prope_registry_revision_created_total` and `revision_conflict_total` increment sites** | **Phase 13's** (13-02). Phase 14 wires `resolve_duration_seconds`, `resolve_miss_total`, `search_duration_seconds` and `unfiltered_query_total` and touches neither of the other two |
| **The three alerts** (`RegistryResolveLatencyHigh`, `RegistryUnfilteredQuery`, `RegistryUnapprovedPointer`) | **Not written by this phase.** `tests/architecture/test_alert_rules.py` exists and phase 15 owns the registry's alert rows. Plan 14-05 puts the resolve histogram's `0.010` edge in place so `RegistryResolveLatencyHigh`'s threshold is expressible; the rule itself is unclaimed here |
| **`registry.revision.body` versus `FORBIDDEN_FIELD_NAMES`** | `tests/architecture/test_route_table.py`'s CL-10 walk forbids a `body` field. `ledger.call_body` has no read path (ADR-0018); **`registry.revision.body` has a legitimate one** (INT-011, `GET /api/v1/revisions/{version_id}`). Plan 14-01 Task 4 narrows the walk to call-ledger's paths **before** plan 14-02 needs it, with ADR-0018 named as the reason the rule is call-ledger's and not the project's |
| **`prometheus_client` default buckets start at 0.005** | Phase 3 hit this. Plan 14-05 verifies `RESOLVE_DURATION_BUCKETS` has `0.010` as an **edge** and fixes it if not; plan 14-02 does the same for `SEARCH_DURATION_BUCKETS` and `0.5` |
| **The i18n catalogue keys** | Six new `ErrorCode` members ship in this phase and **every one is a `vi` catalogue key** (ADR-0053). No catalogue exists (§10b: backend only), so the keys are recorded in the plans and nothing is written. PITFALLS gap 5's *"the i18n layer has no owner"* is unchanged by this phase |

---

## 7. What phase 15 inherits from phase 14, stated so it is not rediscovered

Phase 15 owns **PR-03** and closes **M5**, so §9a binds it. Four things this phase hands it:

1. **The tripwire's wire.** `prope_registry_unfiltered_query_total` is incremented by exactly one named
   function in `repository.py` and by nothing else, and no code in the package calls it. Phase 15's SC2
   (*stays 0, with a page attached if it moves*) is asserted against that. **D-243's carve-out is
   load-bearing**: `resolve()`, `list_released()` and the three commands deliberately do not count, and
   if phase 15 disagrees, SC2 is unsatisfiable the moment the gateway resolves anything.
2. **The two-disjunct visibility predicate**, which fails closed. Phase 15's SC1 is the private-by-default
   claim and is where the third-disjunct question (`OQ-079`) lands.
3. **The single-endpoint form of AC-7** — an explicit response model plus a whole-response byte scan —
   on `GET /api/v1/prompts/{prompt_id}` and on the four read routes, plus a **source gate** over every
   `text()` in the package. Phase 15 generalises the scan to every endpoint.
4. **Ten mounted routes** in `EXPECTED_ROUTES`, so phase 15's every-endpoint assertions can enumerate
   from a literal rather than from the application.

---

## 8. Identifier ranges consumed

- **`D-NN`: D-240 through D-259 — all twenty consumed.** Continuous project-wide and never restarted.
  Phase 1 used D-01…D-08, phase 2 D-09…D-25, phase 3 D-26…D-45, phase 4 D-46…D-65, phases 5-9
  D-66…D-145, phases 10-13 the ranges up to D-239. **Phase 15 starts at D-260.**

  | Plan | Decisions |
  |---|---|
  | 14-01 | D-240 (filtering is a required argument), D-241 (one `api.py`), D-242 (`search_text` excluded three ways), D-243 (the tripwire counts the person-facing paths only), D-244 (`ManagementAction` valued from `vocabulary.Action`), D-245 (the filtered read **is** the visibility answer; `may()` runs either way), D-246 (`{prompt_id}`), D-247 (`LOGGABLE_FIELDS`) |
  | 14-02 | D-248 (the search term's folding and escaping), D-249 (`updated_at DESC`, an opaque cursor resolved through the filter, no body in a list), D-250 (`GET /revisions/{version_id}` resolves permission through its parent in one statement) |
  | 14-03 | D-251 (routes thin over phase 13's commands; two transactions), D-252 (one declared action, a second checked), D-253 (the refusal vocabulary; INT-016 never refuses) |
  | 14-04 | D-254 (`EXPLAIN`, not a timing, and no planner switch), D-255 (the event as stored; no `module` field, no actor name) |
  | 14-05 | D-256 (the workspace parameter; the pin's `Approved` filter), D-257 (one `LEFT JOIN`; a typed miss with a third reason; the `0.010` bucket edge) |
  | 14-06 | D-258 (the caller's session; no history event; the ids stored nowhere), D-259 (the transition table) |

- **`OQ-NNN`: OQ-075 through OQ-079 — all five consumed.** See §1.
- **Threat ids**: `T-14-01` … `T-14-54`, allocated per plan and continuous across the phase.

---

## 9. The planner's own self-check

The critic stage is deleted for phases 5-24 (ORCHESTRATION §10a). These five checks were run by the
planner, by reading its own files. **They are agent judgements, not detector output.**

**1. Every ROADMAP success criterion is owned by exactly one plan.** ✅ §2. SC1 → 14-05, SC2 → 14-05,
SC3 → 14-04, SC4 → 14-06. Three plans own none, and §2 says which obligation they carry instead.

**2. Every requirement id in PR-04 appears in exactly one plan's `requirements:`.** ✅ §2a. `14-05` only;
the other five declare `requirements: []`.

**3. Every file named in any task's `<action>` or `<files>` appears in that plan's `files_modified`.**
✅ Checked plan by plan and task by task, reading the action prose back line by line. Four corrections
were made during that pass and each is recorded because it is the defect class this check exists to
catch:

- **14-01** gained `src/prope/call_ledger/api.py` — Task 2's `get_sessionmaker` contingency edits it if
  D-116 has not landed.
- **14-03** gained `src/prope/call_ledger/api.py` and Task 2 gained `src/prope/management_api.py` — the
  `_constraint_name` relocation in Step 0 edits both.
- **14-02** gained an explicit contingency for a missing `get_diff` rather than an instruction that
  cannot be followed.
- **14-06** Task 5's per-task `<verify>` was changed from the whole suite to the lint gate; the whole
  suite lives only in that plan's `<verification>`.

Read-only files named in prose are listed as comments **inside** `files_modified` with the word
READ-ONLY, following plan 13-01's convention, so the declaration stays exhaustive without over-claiming.

**4. Every symbol, fixture, constant and file the plans tell an executor to extend either exists today,
is created by an earlier plan in this phase, or is specified by the plans of a phase that executes
before this one.** ✅ Each was grepped. Exists **today**: `assembled_routes`, `declares_action`,
`declared_action`, `declares_session`, `require_session`, `Session`, `ManagementRefusal`,
`ManagementAction`, `workspace_transaction`, `build_engine`, `build_sessionmaker`, `_constraint_name`,
`ErrorCode`, `PageRequest`, `get_sessionmaker`, `install_error_envelope`, `LOGGABLE_FIELDS`,
`EXPECTED_ROUTES`, `UNVERSIONED`, `FORBIDDEN_FIELD_NAMES`, `tests/integration/_asgi.py::call`,
`migrate_engine` / `app_engine` / `app_sessionmaker`, `_percentiles`. Specified by an **earlier phase's
plans**: `may` / `Actor` / `Subject` (07-02), `vocabulary.Action` (07-01/D-98), `visible_subject_filter`
/ `VisibleSubjects` (08-02), `management_api.py` / D-116 (08-01), `refusal_for` / `is_visible` (09-01),
`get_model_catalogue` / `CatalogueEntry` (11-03), `append` / `read` / `PromptScope` / `HistoryEvent` /
`HistoryCursorUnknown` / `HistoryScopeMismatch` (05-01, 05-02),
`ix_history_event_workspace_id_scope_prompt_id_seq` and the 31-name registry (04-01), the `registry`
schema and every constraint name, `uq_prompt_property_model_name`,
`ix_prompt_property_workspace_updated_at`, `compose_search_text`, the six metrics, `MAX_BODY_BYTES`,
`RESOLVE_DURATION_BUCKETS`, `tests/prompt_registry/__init__.py` (13-01),
`register_prompt_property` / `create_revision` / `get_revision` (13-02), `retire_prompt_property` /
`update_prompt_property` (13-03). Created **within this phase**: `repository.py`, `api.py`, `schemas.py`
(14-01), `search.py` (14-02), `catalogue_check.py` (14-03), `activity.py` (14-04), `resolve.py` and
`tests/prompt_registry/corpus.py` (14-05), `commands.py` (14-06). **The one symbol that could not be
confirmed is `get_diff`** — phase 13's plans 13-04 through 13-06 did not exist on disk when this phase
was planned — and it is handled as a stated contingency rather than as an assumption (§5.1).

**5. No plan hardcodes an Alembic `down_revision`, gates on `ruff format --check`, references a
`gsd-core` path, or puts the whole-suite `uv run pytest -q` anywhere but the last plan's
`<verification>`.** ✅ **Phase 14 writes no migration at all** — plans 14-04 and 14-06 assert
`git status --porcelain alembic/` is empty and 14-06 asserts `uv run alembic heads` is unchanged from
what phase 13 left. Every plan states that `ruff format --check` is **not** a gate and names Broken
Window #1. No `<context>` block references `$HOME/.claude/gsd-core` or any `gsd-core` path; every
reference is an `@`-prefixed project file. The whole-suite run appears exactly once, in **14-06's
`<verification>`**.

**Two further checks the planner ran on itself:**

**6. No plan asserts a phase-13 or phase-15 criterion as its own.** Plan 14-03 explicitly states that
PR-05 and phase 13's SC3 belong to phase 13 and that the retire route owns only the status code and the
envelope; plan 14-06 Task 3 states that plan 13-01's `test_released_pointer_constraint.py` owns the
engine-level half of the Approved-only proof and that this phase owns the wrapper's half. Plans 14-01 and
14-02 name AC-7, AC-10 and AC-11 as owed criteria belonging to phases 13 and 15 and claim none of them.

**7. Nothing in this phase edits another module's package.** `src/prope/property_history/`,
`src/prope/access_control/` and `src/prope/provider_access/` are **called and imported, never edited**,
and each plan's `files_modified` says so in a READ-ONLY comment. The three shared files this phase does
edit — `src/prope/app.py`, `src/prope/observability.py` and the D-116 surface — are shared infrastructure
rather than another module's package, and `src/prope/call_ledger/*` is touched **only** to complete a
move phase 8 already decided.

---

## 10. Risks the executor should carry into the phase

1. **The p95 is the phase's largest single risk.** Four round trips — `BEGIN`, `set_config`, the query,
   `COMMIT` — inside 10 ms, through Docker Desktop for Windows, against a test rig whose every engine
   uses `NullPool`. Plan 14-05 Task 4 builds its own pooled engine for exactly that reason and names the
   arithmetic. **If it misses, report the quantiles and name which round trip dominates. Never move the
   threshold**, and never make the tenant setting session-scoped to save a hop — that is the one
   optimisation on this path that is catastrophic rather than merely wrong.
2. **The `EXPLAIN` test is a property of the data as much as of the schema.** Plan 14-04 seeds ~2,000
   events and runs `ANALYZE` so the planner's choice is real, and **refuses `enable_seqscan = off` by
   name**. A future reader seeing it flake on a smaller corpus will reach for the switch; the docstring
   is written to stop them.
3. **Four plans edit `api.py`.** Waves 1-4 are successive for that reason. An orchestrator fanning out on
   wave number alone would collide; §4's table is the check.
4. **`revision.status` and the released pointer are writable by `prope_app` by design.** Phase 13's grant
   matrix gives column-level `UPDATE` on `status` because INT-012 needs it, and ADR-0008's amendment says
   plainly that this is *"the ninth application-maintained invariant in the build and the first that could
   not be pushed into the database."* **Plan 14-06's enumeration is the compensating control** and its own
   docstring states what it cannot see — a statement built at runtime, a migration, a `psql` session — and
   names release-control's reconciliation query as the runtime detector for the rest.
5. **Nothing in this phase can be exercised by hand until phase 7's session store exists.** Every
   `/api/v1` route answers `401` unconditionally through `require_session` until then, and the tests
   reach the handlers through `dependency_overrides`, which is **a test seam and not a bypass**. Plan
   14-01 Task 3 asserts that a request made without the override is refused rather than served.
