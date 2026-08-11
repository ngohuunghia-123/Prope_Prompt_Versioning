# Phase 15 — deferred items, mappings, and the planner's own self-check

**Phase:** 15 — Private by default, the tripwire, and the `search_text` leak · **Module:**
prompt-registry · **Milestone:** M5 Prompt Registry — **this phase CLOSES it** · **Depends on:** Phase 14

Written by the phase planner under the MINIMAL PROTOCOL (ORCHESTRATION §10a). There is no CONTEXT,
RESEARCH, PATTERNS, DISCUSSION-LOG or COVERAGE artifact for this phase, and **no critic reviewed these
plans before execution.** Everything the deleted artifacts carried lives in the plans' `<objective>`
sections — the eighteen `D-NN` decisions with their rejected alternatives and reversibility ratings, and
the re-ground instruction each plan opens with. Everything the deleted *checks* would have caught is
self-checked in §8 below. **Every judgement in this file is an agent judgement made by reading files.**
No deterministic detector exists in this environment and nothing here is detector output.

**This phase closes M5, so ORCHESTRATION §9a binds it.** Plan **15-06 Task 2** walks
`docs/modules/prompt-registry.lock.yml`'s `acceptance_criteria`, all seven `test_plan` categories, all
eight `failure_modes` rows, `observability_requirements`, `performance_requirements` and
`security_requirements` clause by clause, and appends the result to this file under
`## M5 milestone audit (ORCHESTRATION §9a)`. §5 below is the **seed** for that walk — the ledger phase 13
left plus what this phase's plans claim. **It is not the walk.**

Executors append to this file. Do not renumber the sections — six plans cite these numbers by name.

---

## 1. The phase's whole `docs/` footprint

`docs/` is read-only with exactly one exception: **creating** `docs/brainstorm/open_questions/OQ-NNN.md`.
The allocated range was **OQ-080 through OQ-084** and **all five were consumed.** Every one is a real spec
conflict found while planning; none is a placeholder.

| Id | One line | Severity | Named against |
|---|---|---|---|
| **OQ-080** | **`mode: all` and private-by-default are two different answers to the same question.** INT-002 says `mode: all` means the actor may see every subject of that type in the workspace; `is_visible` does not list role bindings among its three terms. A colleague with an ordinary `prompt.read` role would see another person's `private` prompt **in a list page** while the detail route answers 404 for the same row — a breach of non-negotiable #4 and of AC-3's exact words | **high** | `interfaces.md` INT-002 (`mode: all` paragraph); `access-control.lock.yml` `apis.exposes`; `prompt-registry.lock.yml` `security_requirements` + AC-3 |
| **OQ-081** | **`is_visible` needs `is_active_member` and no seam returns it.** `access.workspace_member` is another module's table and `data.reads` forbids the join; none of access-control's five internal functions returns membership. INT-002's own specified predicate has two disjuncts, so implemented literally a `workspace`-level prompt is invisible to every member except its owner and grantees | medium | `access-control.lock.yml` (the `is_visible` rule, `apis.exposes`); `prompt-registry.lock.yml` `data.reads`; `interfaces.md` INT-005 |
| **OQ-082** | **`RegistryUnapprovedPointer` is an alert whose condition is SQL**, over a series no metric declares, in a stack ADR-0030 built with no SQL-to-metric bridge — and phase 13's D-221 foreign key makes the condition structurally unreachable anyway, so the honest reading of a hit is *"the constraint is gone"* | medium | `prompt-registry.lock.yml` `observability_requirements.alerts` + `.metrics` + `failure_modes` row 2; `ADR-0030` |
| **OQ-083** | **`search_text` never leaves through the API and nothing says anything about the two doors it does leave through.** `prope_report` (`BYPASSRLS`, ADR-0037) can `SELECT` the one column that concatenates every latest body into a single greppable, **folded** document; ADR-0036's dump carries it with no exclusion, so the dump holds every latest body twice | medium | `prompt-registry.lock.yml` `security_requirements` (*inherits every rule the body already carries*); `ADR-0036` (two exclusions, neither in `registry`); `ADR-0037` |
| **OQ-084** | **The search load condition names no workspace count, no filter set, no permission shape and no measurement point**, and PITFALLS gap 5 already records that search and filter has no acceptance criterion to adjudicate any of them. Three readings produce three different tests and the fastest and slowest actor differ by more than the target | low | `prompt-registry.lock.yml` `performance_requirements` (search row) + `test_plan.load` + `scope.in_scope` (the six filterable fields) |

**Nothing else under `docs/` was written or edited.** No lock file, no ADR, no `interfaces.md` line, no
assumption file, no `adr_index.md` entry. **All five files were written at planning time**, before any
plan executes — so `git status --porcelain docs/` must be **empty** for every plan in this phase, and plan
15-06's phase gate asserts exactly that. Every plan carries a `# READ-ONLY and deliberately NOT in
files_modified` block saying so, because a path listed as modified that the plan forbids writing is a
declaration the orchestrator cannot trust.

Highest OQ id on disk when this phase was planned was **OQ-085** (a concurrent planner holds it); 070-074
are phase 13's, 075-079 are phase 14's and were not yet written to disk. **This phase claimed 080-084 and
none of the others.** No collision.

**`.planning/` files this phase's planner did NOT touch and its executors must not:**
`ORCHESTRATION.md`, `ORCHESTRATION-DECISIONS.md`, `WINDOWS.md`, `ROADMAP.md`, `REQUIREMENTS.md`,
`STATE.md`, `research/PITFALLS.md`, `BSP-LINK.md`, and every other phase's directory. Plan 15-06 Task 2
**writes the diffs** those files need, as ready-to-apply text, into this file; the orchestrator applies
them. Five other planners ran concurrently and a write outside this directory is a race.

---

## 2. Mappings

### 2a. ROADMAP success criterion → plan. Each owned by exactly one.

| # | Success criterion (ROADMAP, Phase 15) | Owning plan | Requirement | Proven by |
|---|---|---|---|---|
| 1 | A private prompt owned by A does not appear when B searches its exact title, and a direct GET by id returns the same not-found response as a nonexistent id | **15-01** (Tasks 2 and 4) | **PR-03** | `tests/security/test_private_by_default.py` — the search half with A's own search as the positive control, the detail half asserted **byte-identical** after one sanctioned `request_id` normalisation, the whole route census, and the repository-level form of the same claim. `tests/security/_refusal_shapes.py` is the comparator |
| 2 | `prope_registry_unfiltered_query_total` stays 0, with a page attached if it moves | **15-03** (Tasks 1 and 2) | — | `tests/security/test_unfiltered_query_tripwire.py` — a **zero delta** across every read path including `resolve()` and the three commands, a negative control moving it by exactly one with its logged reason, and an AST walk proving nothing under `src/` calls the hatch. `deploy/prometheus/rules/prompt_registry.rules.yml` + `tests/architecture/test_alert_rules.py` carry the page |
| 3 | `search_text` is absent from every list and detail response, asserted by a whole-response scan rather than a field allow-list | **15-02** (Tasks 1–3) | — | `tests/security/test_search_text_never_returned.py` — three markers over serialized **bytes**, every route, every page, the 404/422/500 bodies and the log records, with a positive control on each path; `tests/security/_search_text_markers.py` proves the scan can fail; `tests/architecture/test_registry_response_models.py` covers the contract |
| 4 | A cross-workspace read of `registry.revision` is refused by RLS, and a read with no `app.workspace_id` set returns zero rows rather than all rows | **15-04** (Tasks 1 and 2) | — | `tests/security/test_registry_read_paths_are_tenant_scoped.py` — asserted **through every read function the module exposes**, including `resolve()` on a model name two workspaces share and `list_released(workspace_id=other)`; and the **policy drop-and-restore** proving the zero is the policy's doing |

**Four criteria, four owning plans, none claimed twice and none unclaimed.**

**SC4 needs a sentence, because it overlaps a phase-13 test and the orchestrator will notice.** Phase 13's
plan 13-06 Task 1 wrote `tests/security/test_registry_tenant_isolation.py`, which asserts the wrong
tenant, the unset tenant, a mis-stamped `INSERT` and a cross-tenant parent **at the table level**. That is
a precursor, not a duplicate claim, and phase 15 does not restate a line of it. What phase 15 adds is the
half that did not exist when phase 13 ran: the module now has ten routes, two hot reads and three
commands, and SC4 is asserted **through those functions** rather than through hand-written SQL — plus the
mutation control (drop the policy, watch every prompt body appear, restore it) that nothing in phases 1-14
has run for `registry`. Plan 15-04's own docstring is required to state which file covers what, and plan
15-06 Task 3 clause 6 reports the relationship for the verifier.

Plans **15-05** and **15-06** own **no** ROADMAP success criterion. They own the ROADMAP's **Spec**
routing for this phase — `failure_modes` (all 8 rows), `observability_requirements`,
`security_requirements`, `test_plan`, `acceptance_criteria` — which §9a makes a separate obligation from
the success criteria and which is the whole reason a milestone-closing phase exists.

### 2b. Requirement → plan. Each id in exactly one plan's `requirements:`.

| Requirement | Lock AC | Plan | Status after this phase |
|---|---|---|---|
| **PR-03** | prompt-registry AC-3 | **15-01** | proven — `tests/security/test_private_by_default.py`, which is the file AC-3's own `test_ref` names |

**Phase 15 owns exactly one requirement and it appears in exactly one plan's `requirements:`.** Plans
15-02 through 15-06 carry `requirements: []`, deliberately: they discharge *owed* acceptance criteria and
`test_plan` clauses that PITFALLS gap 1 and gap 5 record and that no `REQ` id points at. The same posture
is precedented at 03-04, 04-04, 05-01, 05-02, 06-05, 06-06, 07-01, 07-03, 07-06, 08-03, 08-04, 09-06,
10-04, 10-05, 10-06, 12-04, 12-05, 12-06, 13-04 and 13-06.

**PR-01, PR-02, PR-05 and PR-06 are phase 13's; PR-04 is phase 14's.** None appears here.

### 2c. The five owed acceptance criteria — the M5-wide ledger

PITFALLS gap 1 records **AC-7 through AC-11** as owed to prompt-registry and split between phases 13 and
15. Phase 13's `deferred-items.md` §2c recorded its half; this is the whole:

| Owed AC | Substance | Phase 13 | Phase 15 |
|---|---|---|---|
| **AC-7** | `search_text` absent from every response body, by a **whole-response scan** | structural halves only — the column unwritable (13-01's grant matrix) and unselectable (13-04's source gate) | **whole**, plan **15-02** |
| **AC-8** | The trigger exists **and fires on a direct `INSERT` bypassing the application** | **taken** — 13-04 Task 2, with a drop-and-restore check | — |
| **AC-9** | `registry.revision` has RLS with a policy and appears in ADR-0045's coverage walk | **taken** — 13-01 structurally, 13-06 behaviourally at the table | plan **15-04** adds the read-path form **and the mutation control**, which phase 13 did not run |
| **AC-10** | Substring semantics end to end — `'thentic'` matches `authentication`, `'refund'` matches `support/refund-classifier` | **taken at the SQL layer** — 13-04 Task 2 | **end-to-end half**, plan **15-05** Task 1, through `GET /api/v1/prompts` |
| **AC-11** | A term matching only a non-latest body returns nothing; one matching an older **change summary** returns the prompt | **taken** — 13-04 Task 2 | — |

**All five are accounted for and none is claimed twice.** Plan 15-06 Task 2 verifies this table against
the SUMMARYs rather than against the plans, because an audit written from plans audits intentions.

### 2d. What this phase absorbs from PITFALLS gap 5

| Gap 5 bullet | Disposition |
|---|---|
| **Search and filter has no acceptance criterion** | **Closed here** — plan 15-05 Task 1 is the criterion, written as a test because the lock file is read-only. Six filters, both directions each, the permission filter under a parameterised cross product, and cursor stability |
| **The registry's Activity endpoint has no AC from the caller's side** | **Split.** Phase 14's SC3 covers the content half (*events from all four writing modules in one indexed read on `(workspace_id, scope_prompt_id, seq DESC)`*). Phase 15 covers the **refusal** half — `/activity` is in plan 15-01's `REGISTRY_READ_ROUTES` census, so an invisible prompt's activity is a byte-identical 404 — and the **leak** half, since it is scanned by plan 15-02. Plan 15-06 Task 2 records whether anything is left |
| **The i18n layer has no owner** | **Not this milestone's.** The registry's one piece of it — a `vi` catalogue key for `RevisionDiff.exact`, which phase 13's §3 item 6 routed to phase 14 — is recorded in plan 15-06's audit with its status, not absorbed |
| **The cross-module route-table tests cannot run before phase 23** | **Routed, and named as routed rather than left as a hole.** The registry's route-uniqueness rule is one of the three. Phase 13's §4 already says it is neither phase 13's nor phase 15's; plan 15-06 Task 2 records it against phase 23 so the milestone ledger reads as complete |
| **Two success metrics are hand-run SQL at pilot review** | Unchanged (A-126). Not this phase's |

---

## 3. Plans, waves and dependencies

| Plan | Wave | depends_on | What it is |
|---|---|---|---|
| **15-01** | 1 | — | **Tracer.** One thin path through every layer the phase touches — a session, a route, the repository predicate, RLS underneath, a response — driven against the live engine. Fixes the visibility disjunction phase 14 routed here, resolves `mode: all` against non-negotiable #4, and ships the byte-identity comparator and the route census every later plan uses. **PR-03** |
| **15-02** | 2 | 15-01 | The owed **AC-7** whole: three markers over serialized bytes, every route, every page, every refusal body, the log records, plus the model and OpenAPI contract walk |
| **15-03** | 2 | 15-01 | The tripwire proved in both directions, and the three declared alerts as a rules file the existing read-back covers |
| **15-04** | 3 | 15-01 | SC4 through the module's own read functions, plus the policy drop-and-restore negative control, plus the source gate that keeps an unscoped session unreachable |
| **15-05** | 3 | 15-01 | The `test_plan` and `performance_requirements` clauses no phase owned: the search AC, AC-10 end to end, search p95, revision-create p95, and both chaos clauses |
| **15-06** | 4 | 15-01…15-05 | The milestone close: the four forbidden edges, the write boundary, the §9a clause-by-clause audit, and the phase gate |

**Two plans in this phase MUST run alone** (ORCHESTRATION §7a) and the orchestrator decides this, not the
planner — but both are named here so the decision is cheap:

- **15-04** — clause **(b)**, shared-container-state mutation. Task 2 **drops a row-level-security policy**
  on the session-scoped Postgres container and restores it in a `finally`. A concurrent test inside that
  window reads another tenant's prompt bodies and fails somewhere else entirely, and the failure looks
  like a real defect.
- **15-05** — clause **(a)**, latency assertions (search p95 < 500 ms, revision-create p95 < 300 ms), and
  clause **(b)** as well, because Task 4 **terminates a database backend**.

**15-02 and 15-03 are in the same wave and their `files_modified` are disjoint**, so they *may* fan out —
but 15-03's negative control increments a **process-global** Prometheus counter, which is why every
assertion about it in the phase is a delta (D-267). With deltas everywhere, concurrency is safe; **if an
executor ever writes an absolute assertion, it is not.** Stated here because it is the one place
concurrency and a design decision interact.

Execution is serial regardless (ORCHESTRATION §7); the waves express correctness ordering only.

**One ordering fact is load-bearing:** every plan from 15-02 onward imports something 15-01 created —
`REGISTRY_READ_ROUTES` (15-02, 15-03, 15-04), `_refusal_shapes.assert_identical_refusals` (15-04's
cross-workspace refusal), and the AST-walk shape in `test_registry_permission_filter.py` (15-03's Task 2
clause 3). 15-01 first, always.

---

## 4. Routed OUT of this phase — with a named owner each

The milestone closes here, so **an item on this list is an item that leaves M5 and lands in somebody
else's milestone.** Each is named rather than assumed, and plan 15-06 Task 2 re-states each with its
disposition in the formal audit.

1. **`test_plan.e2e` — the whole clause.** *"register → edit twice → diff revisions 1 and 3 →
   release-control approves and releases → gateway resolves the bare model name and receives revision
   3."* Four of its five steps cross **release-control** (M8, phases 22-24) and **the gateway** (M7,
   phases 19-21). **Routed to phase 23 or 24** — plan 15-06 Task 2 picks and states which — with phase
   12's `OQ-066` as the precedent: that is an M4 acceptance clause discharged inside M8's milestone, and
   this is the same shape. **Do not assert a partial version and call it e2e.**
2. **`test_plan.contract`'s consumer half.** Phase 14 owns `resolve()`'s and
   `set_released_revision()`'s **shapes**; their **consumers** are evaluation (phase 17), the gateway
   (phase 19/20) and release-control (phase 23). Routed by consumer.
3. **The route-table uniqueness test.** Four modules mount under `/api/v1/prompts/{prompt_id}` and no
   collision exists today; the assertion is about the **assembled** table and **cannot run before phase
   23** (PITFALLS gap 5). Neither phase 13's nor phase 15's, and recorded as routed rather than as a hole.
4. **The import-linter layering contract.** Release-control's owed AC-14 asks for it over the whole
   eight-module graph and it is **phase 24's**. Plan 15-06's D-277 ships a module-local AST walk instead
   and says in the file that phase 24 should **replace** it rather than keep it beside a graph-wide
   contract.
5. **`OQ-078`'s path-parameter spelling.** Phase 14's D-246 adopted `{prompt_id}` from the lock and raised
   the disagreement with `interfaces.md` INT-024 and ROADMAP SC3, which both write `{id}`. **One spelling
   must win project-wide before phase 23's route-table test can see a genuine duplicate**, and phase 15
   does not decide it — plan 15-01's route census uses whatever is mounted.
6. **`OQ-080`, `OQ-081` and `OQ-083` are user decisions, not phase work.** Each is adopted fail-closed and
   asserted; none blocks the build. `OQ-080` in particular cannot be answered the other way without
   renegotiating non-negotiable #4, and plan 15-01's `<human-check>` says so.
7. **`prope_report`'s read of `search_text` and the nightly dump's second copy** (`OQ-083`). Plan 15-04
   asserts the exposure as a fact rather than hiding it, and closes the only half that is closable here
   (the role holds no write privilege). The classification answer belongs to **OQ-006**, which gates the
   pilot rather than the build.

---

## 5. Seed for the §9a audit — what plan 15-06 Task 2 must dispose of

**This is a seed, not the walk.** The walk reads the lock file and the SUMMARYs; this is the ledger phase
13 handed forward plus what this phase's plans claim, so that Task 2 starts from a list rather than from a
blank page.

**From phase 13's `deferred-items.md` §4, verbatim in substance:**

| Item phase 13 routed here | This phase's disposition |
|---|---|
| AC-7 whole, and AC-10's end-to-end half | 15-02 and 15-05 Task 1 |
| `test_plan.load` — the **search** half (`resolve` half is phase 14's) | 15-05 Task 2 |
| `test_plan.chaos` clause 3 — connection lost mid-create, no orphan revision, no orphan event | 15-05 Task 4, with a **real terminated backend** (D-275) |
| `test_plan.chaos` clause 1 — the **rewritten** form only | 15-05 Task 4, with the literal form refused in writing (D-276) |
| `performance_requirements` — revision create p95 < 300 ms including the history append | 15-05 Task 3 |
| `observability_requirements.alerts` — three rules, none written by phase 13 | 15-03 Task 1, with `RegistryUnapprovedPointer` shipping as a document (D-270, `OQ-082`) |
| The route-table uniqueness test | routed to phase 23 (§4 item 3) |

**From phase 14 — unknown at planning time and therefore an explicit instruction.** Phase 14 was planned
**concurrently, by a different agent**, and only its `14-01-PLAN.md` existed when this phase was planned.
**Plan 15-06's re-ground block makes reading `.planning/phases/14-…/deferred-items.md` step 4**, and
anything phase 14 routed to phase 15 that plans 15-01 through 15-05 did not take is Task 2's to absorb or
to re-route with a named owner. Two items are already known from `14-01-PLAN.md` and both are taken:

- **D-245's two-disjunct visibility form**, routed here in as many words (*"Widening it is phase 15's"*) →
  plan 15-01, D-260 and D-261.
- **D-242's single-endpoint response scan**, whose every-endpoint form is *"the owed AC-7 and belongs to
  phase 15"* → plan 15-02.

**`test_plan.chaos` clause 2** — *concurrent revision writes on one prompt* — is **not** on this list and
that is deliberate: phase 13's D-231 built the in-transaction allocation and the retry-once path, and
13-02 asserts it. Plan 15-06 Task 2 must confirm that against phase 13's SUMMARY and record it as
`asserted` **there**, not re-assert it here. If phase 13's SUMMARY does not show it, it becomes this
phase's finding and is routed.

---

## 6. Decisions — `D-260` through `D-277`, eighteen of an allocated twenty

Continuous project-wide numbering, never restarting. Phase 1 used D-01…D-08, phase 2 D-09…D-25, phase 3
D-26…D-45, phase 4 D-46…D-65, phases 5-9 D-66…D-145, phases 10-12 D-146…D-219, phase 13 D-220…D-239,
phase 14 D-240 onward. **This phase was allocated D-260…D-279 and consumed D-260…D-277.** D-278 and D-279
are **unused** — recorded so a later phase does not assume they were taken.

| # | Plan | Decision | Reversibility |
|---|---|---|---|
| **D-260** | 15-01 | **`mode: all` widens PERMISSION, never VISIBILITY.** Three unconditional disjuncts; `mode: all` contributes an empty id array. Rejected: INT-002's literal reading, which puts a colleague's private prompt in a list page → **`OQ-080`** | **costly** |
| **D-261** | 15-01 | The membership term is the **session**, not a column or a sixth seam; the inference is written at the predicate and labelled as one → **`OQ-081`** | cheap |
| **D-262** | 15-01 | Byte-identity after **exactly one** normalisation (`request_id`), with the un-normalised difference asserted so the normalisation cannot hide a broken envelope | cheap |
| **D-263** | 15-01 | The refusal is asserted over a **written-out route census**, proved complete against `assembled_routes()`, never over the route the test happened to pick | cheap |
| **D-264** | 15-02 | The corpus is serialized response **bytes** from every route, with a positive control on every path | cheap |
| **D-265** | 15-02 | **Three markers**, not one — raw phrase, folded phrase, literal key — because the stored copy is folded and a leak arrives in two shapes. Change summaries are deliberately **not** a marker | cheap |
| **D-266** | 15-02 | The **contract** is scanned too — response models and the whole OpenAPI document — because absence from a fetched response is a weaker claim than absence from the surface | cheap |
| **D-267** | 15-03 | The tripwire is asserted as a **delta**, never as an absolute zero, because `prometheus_client`'s registry is process-global and the negative control increments it on purpose | cheap (mechanism); the rule/test divergence is permanent and documented |
| **D-268** | 15-03 | The negative control **calls the escape hatch directly** and asserts +1 with its logged reason; an AST walk asserts nothing under `src/` calls it. The pairing is the claim | cheap |
| **D-269** | 15-03 | Three rules, **exactly one pages**, and it is `RegistryUnfilteredQuery`; `increase(…[5m]) > 0` rather than the lock's literal `> 0`, with the deviation declared in the rule's own description | cheap on the file, **one-way on the alert** |
| **D-270** | 15-03 | `RegistryUnapprovedPointer` ships as a **document** — the SQL, the ADR-0030 argument, the D-221 structural point and `OQ-082` in its description — and the SQL is asserted as a test instead | cheap |
| **D-271** | 15-04 | SC4 is asserted **through the module's own read functions**, and the policy is **dropped and restored** to prove the zero is the policy's doing | cheap |
| **D-272** | 15-04 | **Nothing in the package may obtain a session except through `workspace_transaction`**, asserted by AST walk, with an empty `ALLOWED` | cheap |
| **D-273** | 15-05 | The search load condition is read **pessimistically** — one workspace, `owner` + `tag`, a grant-list actor, measured at the repository call — and the corpus is built **inside the test** because the autouse truncate is function-scoped → **`OQ-084`** | cheap (the number is not) |
| **D-274** | 15-05 | The 20,000-revision corpus is built with **bulk SQL**, and the trigger's per-insert cost is reported as its own number with **no threshold asserted** | cheap |
| **D-275** | 15-05 | The lost connection is a **real terminated backend** (`pg_terminate_backend` from a second connection), not a raised Python exception — because the raise-side is already phase 13's | cheap |
| **D-276** | 15-05 | `test_plan.chaos` clause 1 is asserted in its **rewritten** form only, and the literal form is **refused in writing** with the lock's own premise-deleting paragraph quoted | cheap |
| **D-277** | 15-06 | The four forbidden edges are an **AST import walk with the lock's reasons quoted**, not a layering tool — phase 24 owns the graph-wide import-linter contract | cheap |

**Plan 15-06 records exactly one decision and no more**, following phase 13's 13-06 precedent in the
opposite direction: 13-06 recorded none because it built nothing, and this one has exactly one thing to
decide. Inventing a second to fill a slot would be the hidden-decision failure §10a warns about, inverted.

---

## 7. `UNCONFIRMED` adoptions — the human-decision list for `15-UAT.md` and `ORCHESTRATION-DECISIONS.md`

Under `mode: yolo` a one-way decision is written in full, adopted, and marked `UNCONFIRMED` rather than
blocking (ORCHESTRATION §6). **`ORCHESTRATION §2`'s exception was checked against every one of these and
none violates a non-negotiable** — D-260 exists to *satisfy* one, and it is the only adoption in the phase
that could have gone the other way and been a breach. Had `OQ-080` been adopted INT-002's way, this phase
would have stopped and escalated; it was adopted the other way and the question is raised instead.

| # | Adoption | Plan | Reversibility | What a human is actually being asked |
|---|---|---|---|---|
| 1 | **`mode: all` widens permission, never visibility** (D-260) | 15-01 Task 1 | **costly** | Confirm that an actor whose only authority is a role binding sees an **empty** prompt list in a workspace of private prompts. The alternative reading is INT-002's literal one, and adopting it means renegotiating non-negotiable #4 first. `OQ-080` |
| 2 | **The session is the membership witness** (D-261) | 15-01 Task 1 | cheap | Confirm that a live session implies active membership — or say what removing a member does to their session row, which nothing read establishes. `OQ-081` |
| 3 | **`request_id` is the only normalisation in the byte-identity comparator** (D-262) | 15-01 Task 2 | cheap | Confirm. Every additional normalisation is a byte range the existence-leak assertion stops looking at |
| 4 | **Change summaries are not a `search_text` marker** (D-265) | 15-02 Task 1 | cheap | Confirm that a change summary appearing in a response is legitimate (the revision list returns them) while a body phrase is not. The asymmetry is what makes the scan possible at all |
| 5 | **`increase(…[5m]) > 0` instead of the lock's `> 0`** (D-269) | 15-03 Task 1 | cheap on the file | Confirm the deviation, or accept that the literal form pages forever once the counter has ever moved |
| 6 | **`RegistryUnapprovedPointer` ships as a document rather than an evaluable rule** (D-270) | 15-03 Task 1 | cheap | Confirm — or choose one of `OQ-082`'s other two options: a seventh metric set by a `worker` job in a module that declares it has none, or dropping the rule to two and editing the lock's alert block |
| 7 | **`prope_report` reading `search_text` is asserted as an accepted exposure** (`OQ-083`) | 15-04 Task 1 | costly to close later | Confirm, or say which of the two doors closes — a column-level `REVOKE`, or a dump exclusion with a documented restore backfill |
| 8 | **The pessimistic search-load reading** (D-273) | 15-05 Task 2 | cheap now | Confirm the four choices — one workspace, `owner` + `tag`, a grant-list actor, measured at the repository call. `OQ-084` |
| 9 | **`test_plan.chaos` clause 1's literal form is refused** (D-276) | 15-05 Task 4 | cheap | Confirm that a clause whose premise the architecture deleted should be asserted in its rewritten form only. The alternative is a passing test of an impossible state, cited as coverage |
| 10 | **`test_plan.e2e` is discharged inside M8's milestone** (§4 item 1) | 15-06 Task 2 | — | Confirm the route, with phase 12's `OQ-066` as the precedent. An M5 acceptance clause will be closed by a phase whose ROADMAP entry does not mention it |

---

## 8. The planner's own self-check

The critic stage is deleted for phases 5-24. These are the checks it would have run, run by the planner
against its own output. **All are agent judgements from reading files.**

### 8.1 Every ROADMAP success criterion is owned by exactly one plan

Checked in §2a. SC1 → 15-01, SC2 → 15-03, SC3 → 15-02, SC4 → 15-04. Four criteria, four plans, no
duplicates, no orphans. Plans 15-05 and 15-06 own none and own the Spec routing instead. **Pass**, with
SC4's relationship to phase 13's `test_registry_tenant_isolation.py` written out in §2a because it is the
one an orchestrator could read as a double claim.

### 8.2 Every requirement id appears in exactly one plan's `requirements:`

Phase 15 owns exactly one: **PR-03** → 15-01. Plans 15-02 through 15-06 carry `requirements: []`, which is
precedented twenty times in phases 3-13. No requirement appears twice and none is missing. **Pass.**

### 8.3 Every file named in a task's `<action>` or `<files>` appears in that plan's `files_modified`

Read back line by line, per plan. **Pass**, with three corrections made during the check and recorded here
so the process is auditable:

- **15-01's `files_modified` did not name `tests/architecture/test_registry_permission_filter.py`**, which
  is Task 3's entire subject and is also named in its *Artifacts this plan produces* block. **Added.**
  This is exactly the defect class the deleted exec-critic existed to catch, found by the planner in its
  own output.
- **15-05's `tests/chaos/__init__.py`** was described in a read-only comment as *"create it and report it
  as a file outside this declaration"*, which is a foreseeable file being pre-labelled as drift. **Moved
  into `files_modified` as a declared contingency**, and both the comment and the re-ground step were
  rewritten to match.

- **15-02's `src/prope/prompt_registry/schemas.py` and `.../repository.py`.** Task 2's action names both as
  the place a discovered `search_text` leak gets fixed, and the frontmatter had them in the READ-ONLY block
  with an instruction to report the write as drift. That is the same defect shape as the `tests/chaos/`
  one above, and it was inconsistent with this phase's own practice twice over: **15-01 declares `api.py`
  and `search.py` as contingencies and 15-03 declares `observability.py` as one.** Both files are now
  **declared**, the action prose says the write is sanctioned rather than drift, and the SUMMARY is still
  required to name the leak, the file, and whether the fix belonged to phase 14's plan. The distinction the
  original comment was reaching for is real and survives — *a repair in another phase's file is
  information the orchestrator needs* — but it is a **reporting** obligation, not a reason to leave a path
  out of `files_modified`. A path an action names is declared; what the SUMMARY says about it is separate.

Per-plan tallies after the corrections: 15-01 seven declared / seven named; 15-02 **five / five**; 15-03
four / four; 15-04 two / two; 15-05 six / six; 15-06 two / two (Task 3 names none, deliberately — it is a
run and a report).

**Every other path that appears in a plan's `<tasks>` block and not in its `files_modified` was checked
individually and is `<read_first>` or read-in-`<action>` only.** The full list, so the check is
reproducible rather than asserted: another module's package (`src/prope/access_control/*`,
`src/prope/db/session.py`, `src/prope/observability.py`), phase 13's and 14's registry modules read for
real signatures (`domain.py`, `resolve.py`, `revisions.py`, `api.py`, `__init__.py`), the migration and DDL
read for exact policy text (`alembic/ddl.py`, `alembic/versions/*_registry_schema.py`), the sibling tests
read to match or to avoid restating (`test_no_sql_interpolation.py`, `test_route_table.py`,
`test_registry_search_statements.py`, `test_registry_tenant_isolation.py`,
`test_registry_schema_ships_its_guarantees.py`, `test_search_corpus_and_substring.py`,
`test_tenant_isolation.py`, `test_append_only_privilege.py`, `test_fifty_rps_for_ten_minutes.py`,
`_forbidden_renderings.py`, `call_ledger.rules.yml`, `tests/conftest.py`, `tests/security/__init__.py`,
`tests/access_control/__init__.py`, `tests/integration/_asgi.py`, `tests/prompt_registry/__init__.py` in
every plan but 15-01), the lock file and ADRs, and — in 15-06 Task 2 only — `.planning/REQUIREMENTS.md`,
`ROADMAP.md`, `STATE.md`, `WINDOWS.md` and `ORCHESTRATION-DECISIONS.md`, which that task is **forbidden**
to edit and writes ready-to-apply diffs for instead.

**File-disjointness across plans, checked explicitly** because the orchestrator acts on it:

| Pair | Shared file | Consequence |
|---|---|---|
| 15-01 / 15-02 | `src/prope/prompt_registry/repository.py` — 15-01 edits it (Task 1, the predicate); 15-02 declares it **only on the leak contingency** | **wave 1 vs wave 2, so never concurrent.** The overlap is real and is the price of declaring the contingency honestly; it costs nothing because the wave ordering already separates them, and 15-02's write only happens if it finds a defect in what 15-01 just wrote |
| 15-01 / 15-03 | `src/prope/prompt_registry/` — 15-01 may edit `repository.py`, 15-03 may edit `observability.py` | **different files**, but both in the same package; different waves regardless |
| 15-02 / 15-03 | none — 15-02's two contingent `src/` files are `schemas.py` and `repository.py`; 15-03's is `observability.py` | disjoint, **including on both contingencies** — this pair is the one that may actually fan out, and it stays safe. See §3's note on the process-global counter |
| 15-02 / 15-04 | none | disjoint |
| 15-03 / 15-04 | none | disjoint |
| 15-04 / 15-05 | none | disjoint; **both must run alone anyway** |
| 15-06 / all | none — 15-06 edits only its own new test and this file | disjoint |

`tests/prompt_registry/__init__.py` is written by **15-01 only**, and 15-02, 15-03 and 15-04 are each
forbidden in writing from editing it. That is the single most likely collision in the phase and it is
closed by declaration rather than by hope.

### 8.4 Every symbol, fixture, constant and file a plan tells an executor to extend exists, or is created earlier

Checked by grep against the tree and against the plans of phases 4-14. **Pass, with the contingencies
below written into the plans rather than assumed.** Everything in the *phase 14* rows is a claim about a
plan that was being written **concurrently** and only partially existed when this phase was planned;
every plan opens with a re-ground instruction saying exactly that.

| Thing | Where it comes from | Status |
|---|---|---|
| `assembled_routes`, `declares_session`, `declared_action`, `MANAGEMENT_ACTIONS` | `src/prope/session_auth.py` | **exists today** |
| `workspace_transaction`, `SET_TENANT` | `src/prope/db/session.py` | **exists today** |
| `migrate_engine`, `app_engine`, `app_sessionmaker`, `report_engine`, the autouse truncate | `tests/conftest.py` | **exists today** |
| `WORKSPACE_A` / `WORKSPACE_B` | `tests/security/__init__.py` | **exists today** |
| `call()`, `Response.code`, `Response.body` | `tests/integration/_asgi.py` | **exists today** |
| `REGISTRY`, `get_sample_value`, the `_text_calls` / `rglob` AST idiom | `prometheus_client`, `tests/architecture/test_no_sql_interpolation.py` | **exists today** |
| `tests/architecture/test_alert_rules.py`, `deploy/prometheus/rules/call_ledger.rules.yml` | phase 3 | **exists today**; phases 6, 9 and 12 extend it — 15-03 reads what is on disk and generalises rather than copying |
| `registry.prompt_property`, `registry.revision`, the policies, the trigger, `compose_search_text`, `gin_trgm_ops`, `unaccent` | plan **13-01** | contingency: 15-04 reads the **exact** policy name and DDL from the migration file rather than from the plan |
| `find_prompt_ids_by_keyword`, `MATCH_SEARCH_TEXT`, `search_duration_seconds` | plan **13-04** | 15-01 Task 4 and 15-05 call them; re-ground instruction in both |
| `create_revision`, `register_prompt_property`, `get_revision`, `compute_diff`, the domain errors | plans **13-02**, **13-03**, **13-05** | re-ground instruction in 15-05 |
| `tests/prompt_registry/__init__.py` with `INSERT_PROMPT_PROPERTY` / `INSERT_REVISION` | plans **13-01**, **14-01** | 15-01 extends it; 15-05 Task 2 uses the raw INSERTs for the bulk build |
| `tests/security/test_registry_tenant_isolation.py`, `tests/integration/test_registry_schema_ships_its_guarantees.py` | plan **13-06** | READ by 15-04 and 15-03; **not edited**, and 15-04 must not restate an assertion either makes |
| `repository.py`, `read_without_permission_filter`, `VisibleSubjects` as a required argument | plan **14-01** (D-240, D-243) | **concurrently planned.** 15-01 and 15-03 both open with an instruction to follow the code and report drift; 15-01 Task 1 consolidates the predicate if phase 14 spread it |
| `api.py`, `schemas.py`, the ten routes, the session mechanism used in phase 14's tests | plan **14-01** and later | re-ground instruction in 15-01, 15-02 and 15-05: **reuse phase 14's mechanism, do not invent a second way in** |
| `resolve()`, `list_released()`, the three commands | phase **14** (plans 14-05/14-06, unread) | 15-03 and 15-04 call them; **if the module names differ, follow the tree** |
| `visible_subject_filter`, `VisibleSubjects`, `VisibilityMode` | plan **08-02** | re-ground instruction in 15-01: **do not assume `ALL` / `IDS` / `NONE`; read them** |
| `may`, `refusal_for`, `is_visible`, `Action` | plans **07-01**, **08-01**, **09-01** | re-ground instruction in 15-01 |
| `append(session, event)`, `history_event` | plan **05-01** | referenced by 15-05's chaos clause 3 only |
| `tests/chaos/`, `tests/load/` | plans **12-03**, **01-04**/**03-06** | 15-05 declares `tests/chaos/__init__.py` as a contingency and matches `tests/load/`'s percentile style |
| `import-linter` | **nothing** | deliberately **not** used — D-277 rejects it and routes the graph-wide contract to phase 24. No `uv add` anywhere in this phase |

**No plan in this phase adds a dependency, a migration, a schema, a metric, an alert name beyond the three
declared, a `SECURITY DEFINER` function, or a route.** `EXPECTED_ABSENT_SCHEMAS` is untouched because this
phase creates no schema — phase 13 already shrank it for `registry`.

### 8.5 The five mechanical prohibitions

- **No plan hardcodes an Alembic `down_revision`.** **No plan in this phase adds a migration at all** —
  15-06 Task 3 clause 4 asserts the head is exactly what phase 14 left, and names it as a finding if it
  moved. **Pass.**
- **No plan gates on `ruff format --check`.** Every plan's `<context>` states that it fails repo-wide on
  Broken Window #1 and is not a gate; `uv run ruff check src/ tests/ alembic/` is the gate in all six.
  **Pass.**
- **No plan references a `gsd-core` path.** Every `<context>` block is `@`-prefixed project files only.
  **Pass.**
- **The whole-suite `uv run pytest -q` appears only in the last plan's `<verification>`.** 15-01 through
  15-05 name targeted paths in every `<verify><automated>` and every `<verification>` block; 15-06 Task 3
  is the single whole-suite run, per ORCHESTRATION §10a. **Pass.**
- **No plan adds mypy, a `typecheck` target, a fifth `SECURITY DEFINER` function, a second broker queue,
  broker-based cache invalidation, `tsvector`, Next.js, Kubernetes, Vault, Keycloak, Kafka, Loki,
  distributed tracing, or any frontend artifact.** 15-01's and 15-04's source gates assert the absence of
  several of these in this package; 15-06's forbidden-edge walk covers the module graph. `import-linter`
  was considered and **rejected** rather than added (D-277). **Pass.**

### 8.6 What this planner could not check

- **Nothing was executed.** No migration was applied, no test was run, and no PostgreSQL or
  `prometheus_client` behaviour was verified. Two claims are about libraries rather than about this
  repository and are labelled at the code: that an **unlabelled** counter defined at import renders a
  sample at `0.0` so a delta is subtractable without a `None` guard (15-03 carries the guard anyway), and
  that `pg_terminate_backend` on a session's own backend produces a surfaced error rather than a silent
  return (15-05 asserts the error explicitly for that reason).
- **Phase 14 was planned concurrently and only `14-01-PLAN.md` existed.** Every claim here about
  `repository.py`, `api.py`, `schemas.py`, `resolve.py` and `commands.py` is a claim about *that plan*,
  not about code, and plans 15-01, 15-02, 15-03 and 15-05 each open saying so. **Plan 15-06's re-ground
  step 4 is the compensating control**: read phase 14's own `deferred-items.md` and absorb or re-route
  whatever it sent here.
- **Three numbers are targets read out of the lock file and have never been run in this environment**:
  search p95 < 500 ms, revision-create p95 < 300 ms, and the 1,000 × 20 corpus. 15-05 forbids moving any
  of them and requires the observed figures and the `EXPLAIN` output in the SUMMARY, so a miss becomes
  information rather than a silently loosened budget.
- **One regression is predicted rather than observed.** Plan 15-01 changes a `WHERE` clause that phase
  14's own route tests were written against, and a phase-14 test asserting a `workspace`-level prompt is
  invisible to a colleague is now wrong — in the direction this phase deliberately changed. 15-06 Task 3
  names the class in advance and routes the fix into phase 14's file, so an executor meeting it recognises
  it rather than debugging it or reverting the predicate.

---

## 9. Executor appendix

Executors append below this line: files touched outside a plan's `files_modified` (report as drift, do not
silently absorb), assertions that failed in 15-06 and the follow-up commit that fixed them, the branch
taken for each contingency in §8.4, the observed p95 figures and `EXPLAIN` output from 15-05, the captured
log line from 15-03's negative control, and — from plan 15-06 Task 2 — the
`## M5 milestone audit (ORCHESTRATION §9a)` section with the five ready-to-apply bookkeeping diffs.
