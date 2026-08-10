# Phase 8 — Deferred items

Out-of-scope discoveries found while planning, the decisions adopted without confirmation under
`mode: yolo`, the SC → plan and requirement → plan mappings, and the open-question ids this phase
consumed. **Logged, not fixed.** The executor and the verifier append to this file; the planner seeded
it.

Phase 8 runs under **ORCHESTRATION §10a, the MINIMAL PROTOCOL**: plans, summaries, verification, and
this file. There is no CONTEXT, RESEARCH, PATTERNS, DISCUSSION-LOG or COVERAGE, and **no critic
reviewed these plans before execution.** The planner's self-checks are §7 below and are the only
pre-execution check this phase received. Every judgement in this file is an **agent judgement made by
reading files** — no deterministic detector exists in this environment and nothing here is detector
output.

**This phase does NOT close milestone M3.** ORCHESTRATION §9a binds the last phase of a milestone and
M3 closes at **Phase 9**. §5 below records what Phase 8 leaves for that walk, so Phase 9 starts from a
list rather than from the lock file.

---

## 1. Plans, waves, and what each carries

| Plan | Wave | Requirements | Carries |
|---|---|---|---|
| `08-01` | 1 | **AC-12** | **Tracer.** The shared A-045 surface moves out of call-ledger's package; INT-005 verified behind `require_session` and driven without `dependency_overrides` for the first time; the three `/prompts/{id}/grants` routes; the grant and its `access_granted` event in one transaction, both directions; the registry migration that registers `level`. |
| `08-02` | 2 | **AC-09** | INT-002 `visible_subject_filter`, its three modes, and the 1,000-subject cross-check against `may()` that catches the set path and the row path disagreeing. |
| `08-03` | 3 | — | INT-003 `authenticate_api_key` and INT-004 `may_resolve`; the three `/keys` routes; the whole-surface assertion that the plaintext secret appears exactly once. |
| `08-04` | 4 | — | The three `/auth` routes, `POST /workspaces`, the member collection, `PUT .../roles`, `GET /permissions`. Five of the module's ten events. The action-free exemption list. |
| `08-05` | 5 | **AC-14** | `POST /users/{id}/tombstone`, the event fan-out, and the whole-row proof that the trail is unchanged. |
| `08-06` | 6 | **AC-10** | AC-10's mechanism half + the bridge from `ManagementAction` to `vocabulary.Action`; the five seams as contracts; a **verification** that Phase 7 closed Broken Window #3; the phase gate. |

**Waves are strictly sequential here, and that is a fact rather than a formality.** Every plan after
the tracer extends the same four files — `src/prope/access_control/domain.py`,
`src/prope/access_control/__init__.py`, the access-control metrics module and
`tests/access_control/__init__.py` — and the four route plans additionally share
`src/prope/access_control/routes/__init__.py` and `tests/architecture/test_route_table.py`. **No two
plans in this phase have disjoint `files_modified`**, so the orchestrator's disjointness check will
never fan out, which is correct. Execution is serial regardless (ORCHESTRATION §7); the waves express
correctness ordering only.

**Two plans carry `requirements: []`, and that is a fact about `REQUIREMENTS.md` rather than about the
work.** `08-03` ships two of the five INT seams and three routes, and `08-04` ships nine routes and
five history events — but the criteria those satisfy (AC-05, AC-06, AC-07, AC-08) are mapped to
Phases 7 and 9. Phases 5 and 6 recorded exactly the same thing for the same reason.

---

## 2. ROADMAP success criteria → plan (each owned by exactly one)

| SC | Statement | Owner |
|---|---|---|
| **SC1** | `visible_subject_filter` returns `mode=ids` listing exactly the granted and owned prompts in a 1,000-prompt workspace, and the registry's list endpoint returns exactly that set | **08-02** |
| **SC2** | Every route in every module declares an action from the vocabulary; a route declaring none fails the test rather than defaulting to unauthenticated | **08-06** |
| **SC3** | A grant and its `access_granted` event cannot exist without each other; the same holds for revocation | **08-01** |
| **SC4** | A tombstone writes one `user_tombstoned` event per workspace the person belonged to, with empty `details` and no reason | **08-05** |

**Verified: four criteria, four owners, none claimed twice and none unclaimed.**

**Two of the four are shipped as HALVES, and both are named here rather than implied.**

- **SC1's second clause** — *"and the registry's list endpoint returns exactly that set"* — cannot run
  in Phase 8. prompt-registry does not exist until Phase 13 and its repository-layer permission
  filtering is **PR-03, Phase 15**. Plan 08-02 asserts the lock file's own stronger clause instead
  (the id list compared row-for-row against `may()` over 1,000 subjects, in all three modes) and
  routes the endpoint half to Phase 15 by name. **Additionally, SC1's first clause is literally
  unsatisfiable** — see `OQ-048`: access-control is forbidden the only input that would let it return
  *owned* prompts.
- **SC2's scope** — *"every route in every module"* — is a property of the assembled table with all
  eight modules mounted, and `.planning/research/PITFALLS.md` §5 says it *"cannot actually run until
  every module is mounted — i.e. not before phase 23."* Two of eight are mounted. Plan 08-06 ships the
  **mechanism** (a route declaring no action fails; four exemptions enumerated and asserted for exact
  equality; the bridge from `ManagementAction` to `prope.access_control.vocabulary.Action` and the
  live `role_permission` matrix; a mutation
  control proving the assertion can fail) and its test's own docstring names Phase 23 as the owner of
  the census. **Do not read Phase 8's green AC-10 test as the whole criterion.**

## Requirement → plan (each in exactly one plan's `requirements:`)

| Requirement | Lock AC | Owner |
|---|---|---|
| **AC-09** | access-control AC-9 | `08-02` |
| **AC-10** | access-control AC-10 | `08-06` |
| **AC-12** | access-control AC-12 | `08-01` |
| **AC-14** | access-control AC-14 | `08-05` |

**Verified: four requirements, four appearances, no duplicates and no omissions.**

---

## 3. Adopted without confirmation — the adjudication list

`mode: yolo` is set and this orchestration does not stop at blocking checkpoints (ORCHESTRATION §6,
§10a). **Every row belongs in `08-UAT.md` as a numbered human-verification item and in
`.planning/ORCHESTRATION-DECISIONS.md` as one row.**

| # | Decision | Plan | What was adopted, and what was rejected | Reversibility |
|---|---|---|---|---|
| 1 | **D-116** | 08-01 | The shared A-045 surface — `ErrorCode`, `ManagementRefusal`, the envelope, `install_error_envelope`, `PageRequest`, `get_sessionmaker` — moves from `prope.call_ledger.schemas` and `prope.session_auth` into a new neutral `src/prope/management_api.py`. Rejected: access-control importing call-ledger's package (a `forbidden_dependencies` edge that release-control's owed AC-14 import-linter contract would later fail the build on), a second envelope (A-045 says there is one), and a re-export shim (two public homes for one closed `StrEnum`). **The move was written down in advance by `install_error_envelope`'s own docstring**; `OQ-021` is cited and is **not** resolved by it | cheap |
| 2 | **D-117** | 08-01 | Sixteen routes in five modules under `src/prope/access_control/routes/`, assembled into one router included once by `prope.app`. Rejected: one `api.py` (~2,000 lines, and every plan in the phase editing it), and five `include_router` calls. **The route count is sixteen, not the fifteen INT-029 states** — raised as `OQ-049` | cheap |
| 3 | **D-118** | 08-01 | `ManagementAction` gains access-control's members, **each valued from `prope.access_control.vocabulary.Action`** — the twenty-five-name `StrEnum` Phase 7's D-98 creates and its migration mirrors as the `role_permission.action` `CHECK` — imported rather than retyped. Rejected: an `access_control.` prefix (two spellings per permission), and not extending `ManagementAction` at all, which is what Phase 7's D-98 chose *for Phase 7* and is right there: it declined twenty-five members **no route declares**, while Phase 8 adds only members that **have** routes. **Consequences: `test_the_action_vocabulary_is_a_str_enum_of_machine_codes` (asserts every member starts with `call_ledger.`) and `test_every_registered_action_is_declared_exactly_once` (an exact set equality) are both rewritten in 08-01 Task 4.** And per Phase 7's **D-99**, A-115's spellings win over INT-001's, so the grants routes declare **`prompt.grant`**, not `prompt.change_access`. Raised as `OQ-046`; Phase 7 raised the same conflict independently as `OQ-041` and the name disagreement as `OQ-042` | **costly** — the values are permission strings five modules will be written against |
| 4 | **D-119** | 08-01 | **SUPERSEDED BY PHASE 7's D-101 and rewritten as a finding.** Phase 7 gives `require_session` a `Request` parameter, has it read `request.app.state.sessionmaker` and call `authenticate_session` — which means `session_auth` imports `prope.access_control`, and `prope.call_ledger.api` imports `session_auth`, so **call-ledger transitively depends on access-control**: the exact edge ADR-0018 says it does not have and release-control's owed AC-14 import-linter contract would fail the build on. Phase 7's D-101 makes the same argument for `get_sessionmaker` and does not make it in this direction. **Adopted: leave Phase 7's wiring as it shipped and RECORD the edge for Phase 24**, on the ground that rewriting Prope's authentication boundary one phase after it shipped trades a real regression risk for an import-graph property no test asserts until Phase 24. D-116 closes the other half of the same problem, which is why that half is done here | cheap — the installed-authenticator shape stays available to whichever phase takes the contract |
| 5 | **D-120** | 08-01 | The grant events carry the grantee in `target_id`, the prompt in `scope_prompt_id`, and the level in a **newly registered** `detail_keys` entry on `access_granted` — an additive Alembic revision, mirroring `role_assigned` / `role_revoked`. Rejected: reading the level back from `prompt_grant` (revocation deletes the row), `reason` (ADR-0054's argument), and a surrogate `id` on `prompt_grant`. **Consequence: `tests/integration/test_history_schema_ships_its_guarantees.py` goes from two declared key sets to three, in the same change.** Raised as `OQ-047` | **costly** — a registered detail key cannot be un-registered once events carry it |
| 6 | **D-121** | 08-02 | `visible_subject_filter` returns the **grant-derived contribution**; ownership stays the caller's own `owner_id = :actor` predicate, stated in the contract in those words. No `IN`-list ceiling; the size is a histogram. Rejected: returning everything the actor may see (access-control may not read `prompt_property` — the module's central design constraint), an `owned_ids` parameter (two round trips to build one `WHERE`), and a widening cap. Raised as `OQ-048`, **severity high** | **costly** — prompt-registry's repository layer is written against it from Phase 15 |
| 7 | **D-122** | 08-02 | `mode: none` means *no grant-derived visibility*, **not** *sees nothing*, documented at the constant. Rejected: collapsing `none` into an empty `ids` — a caller treating that as "return nothing" would hide a person's own prompts from them | cheap |
| 8 | **D-123** | 08-03 | The presented key is parsed into a frozen `PresentedKey` whose `__repr__` omits the secret; every failure branch of `authenticate_api_key` returns `None` and none raises, with a dummy-hash comparison on the unknown-id branch so timing does not separate. Rejected: passing the raw `prope_<key_id>_<secret>` string downstream (the lock file names this exact leak), a logger deny-list, and distinct return values per failure | cheap |
| 9 | **D-124** | 08-03 | `may_resolve` returns a bare `bool`, default-deny, and `ApiKeyCreate` refuses `*`, `%` and `?` in a scope entry. Rejected: a wildcard or prefix match (A-081's explicit cost is accepted out loud instead), and returning a reason with the `False` (the enumeration oracle A-081 and A-116 close) | **costly** — a wildcard cannot be un-added from keys already carrying it |
| 10 | **D-125** | 08-03 | The plaintext secret exists on exactly one response model, `ApiKeyCreated`, and the OpenAPI schema is asserted to contain exactly one secret-shaped property. Rejected: a nullable `secret` on the read model — a field that can be filled by a later edit makes the guarantee depend on a value rather than on a shape | cheap to keep; irreversible in the other direction |
| 11 | **D-126** | 08-04 | The three `/auth` routes declare no action and are enumerated in `ACTION_FREE_ROUTES`, asserted for **exact** equality in both directions; `UNAUTHENTICATED_ROUTES` holds `POST /auth/login` alone. Rejected: inventing `auth.*` members every role holds (a check that can never deny, rendered by `GET /permissions` as if it were policy), and leaving them undeclared (the default AC-10 forbids) | cheap |
| 12 | **D-127** | 08-04 | `POST /workspaces` is permission-checked against the actor's **current** workspace. Rejected: no check (a fourth exemption, for a write), and checking against the workspace being created (no binding exists there, so it would always deny). **See §6 for the bootstrap gap this exposes** | cheap |
| 13 | **D-128** | 08-04 | `POST /auth/login` ships in Phase 8 **with no rate limiter**; `PUT .../roles` is a full replacement emitting one event per change. Rejected: holding the login route to Phase 9 (every other route needs a session), and building a partial limiter (ADR-0043's value is *where* it sits — before the user row is read and before any hash is computed) | cheap |
| 14 | **D-129** | 08-05 | The tombstone fan-out is one `user_tombstoned` per `workspace_member` row **of any status**, `details={}`, `reason=None`, refused while an active membership remains. Rejected: one event in the acting workspace (a workspace whose member vanished would have no event explaining it), deriving the list from `role_binding` (deleted by the same operation), and carrying the count or the former name in `details` | **one-way** — the operation is irreversible by design and the events are permanent by privilege |
| 15 | **D-130** | 08-06 | AC-10 lands as **mechanism now, census at Phase 23**, with the vocabulary bridge to the live `role_permission` matrix and a mutation control. Rejected: claiming the criterion whole (a green test named after a criterion it half asserts is worse than a missing one), deferring the whole thing to Phase 23, and parking it in `test_route_table.py` (06-02's D-84 refused the same thing for the same reason) | cheap |
| 16 | **no `D-NN` — range exhausted** | 08-06 Task 3 | **Phase 8 VERIFIES `access.list_workspaces()` rather than building it, conditionally on a grep.** Phase 7 took the work in the interval between this plan being written and Phase 7's plans landing: 07-01 creates the function alongside the other two `SECURITY DEFINER` names (its D-97), and 07-03 deletes `ObservedWorkspaces` and binds the enumerator, with a prohibition against keeping the stand-in. Rejected: building it here — a second `CREATE FUNCTION` fails and a second enumerator is the two-answers split 07-03 refuses by name. **Outcome 3 (Phase 7 slipped) is an escalation, not a silent pass**, and the fallback is written out so nobody designs under pressure. **The phase's allocated D range is D-116 … D-130 and is full; the orchestrator should assign this adoption a number from the next available range** | cheap — nothing is built either way |

**None of the sixteen touches a §2 non-negotiable.** Human approval before production, the
Approved-only database constraint, the three separate permissions and private-by-default are all
untouched by every row. The four worth a human's attention are **#3** and **#5** (both change a test
another phase wrote), **#6** (a seam five modules build against, and its criterion is literally
unsatisfiable as written), and **#13** (one phase of an unauthenticated, unthrottled login on a
4 vCPU host running argon2id at 46 MiB per attempt).

---

## 4. Open questions consumed

Phase 8's allocated range is **OQ-046 … OQ-049**. **All four are consumed and written.** The highest
id on disk before this phase was OQ-039; OQ-040 … OQ-045 belong to the orchestrator and to the four
planners running in parallel with this one. **No id outside the range was touched, and no existing OQ
file was edited.**

| id | Raised by | Severity | Conflict, in one line |
|---|---|---|---|
| **OQ-046** | 08-01 planning (D-118) | medium | **"The vocabulary" names two different closed sets.** `role_permission.action` holds INT-001's nineteen unprefixed permission strings plus `user.tombstone`; `ManagementAction` holds five `call_ledger.`-prefixed route declarations. They are disjoint today and cannot both be what AC-10 means. Adopted: two sets, named separately, with an asserted bridge and ADR-0018 cited at call-ledger's exemption |
| **OQ-047** | 08-01 planning (D-120) | medium | **AC-12 requires the grant events to carry a `level`; the Phase 4 seed forbids them any `details` key at all.** The level is unrecoverable from `prompt_grant` because revocation deletes the row, and `prompt_grant` has no `id` column to be a `target_id`. `role_assigned` — the sibling operation — *is* seeded with two keys, which is what makes this look like an oversight. Adopted: an additive migration registering `{level}` on `access_granted` only |
| **OQ-048** | 08-02 planning (D-121) | **high** | **`visible_subject_filter` is required to return owned prompts and forbidden the only input that records ownership.** `prompt_property.owner_id` is unreadable here by `data.reads: []` and ADR-0020. AC-9's `given` clause is carefully written for an actor who owns nothing, which is exactly the case that makes the impossible half vacuous. Adopted: the grant-derived contribution, with ownership as the caller's own predicate, stated in the contract |
| **OQ-049** | 08-01 planning (D-117) | low | **The route count is written as 15 (INT-029), as 19 (`libraries_frameworks`), and as an enumeration of 16.** The counting convention was settled one module earlier — `tests/architecture/test_route_table.py:42-50`, *"every count in this file is a path count"* — and INT-029 disagrees with its own list. Adopted: the enumeration is authoritative; the ROADMAP's "fifteen routes" title is not edited |

**Live open questions from earlier phases that Phase 8 leans on and does not resolve:** `OQ-021` (where
the shared management-API surface belongs — D-116 moves the surface and cites the question rather than
answering it), `OQ-027` (the 30-vs-31 vocabulary count, 31 adopted), `OQ-030` (`workspace_id` as a
metric label, resolved by Phase 6 as *unlabelled*, and the precedent Phase 8's two label findings point
at), and `OQ-035` (`append`'s widened signature, which every write path in this phase calls).

---

## 5. What Phase 9's §9a milestone audit inherits from Phase 8

M3 closes at **Phase 9**, which owns the clause-by-clause walk of `access-control.lock.yml`'s
`acceptance_criteria` and `test_plan`. Phase 8 records what it leaves so that walk starts from a list.

| Item | Why not in Phase 8 | Owner |
|---|---|---|
| **AC-9's second clause** — *"and prompt-registry's list endpoint returns exactly that set"* | prompt-registry does not exist until Phase 13; its repository-layer filtering is PR-03 | **Phase 15** |
| **AC-10's cross-module census** — the assembled table with all eight modules mounted | PITFALLS §5: not before every module is mounted | **Phase 23** |
| **AC-5** — the key-scope refusal byte-compared against the gateway's unknown-model response | The gateway is Phase 19. Phase 8 ships the bare boolean that makes the byte-identity achievable and asserts no reason leaks from it | **Phase 9 (module side), Phase 20 (cross-module)** |
| **AC-7's whole-system enumeration** — the secret in *no other response in the system* | Phase 8 asserts it over the OpenAPI schema, the logs, the metric labels, the history rows and the stored row of the two modules that exist | **Phase 9** |
| **AC-15** — no surface renders a name or an email for a tombstoned actor, through a catalogue key | Phase 8 writes no rendering surface | **Phase 9** |
| **`test_plan.load`** — 50 rps of key authentication plus 50 management requests/sec for 10 minutes, with the combined `authenticate_api_key` + `may_resolve` p95 under 5 ms | Phase 8 ships bucket edges at 0.005 and 0.02 so the targets are measurable, and asserts only a **generous smoke bound** on the 1,000-prompt filter with the reason at the constant | **Phase 9**, reusing Phase 3's registered `load` marker and Phase 6's D-94 proxy posture |
| **`test_plan.chaos`** — the database taken away mid-request, a key revoked under sustained load, a role removed with a session open, a corrupted `role_permission` seed | Phase 8 asserts the immediate-revocation half in one process; the rest needs the chaos rig Phase 6 built and AC-11's per-caller form | **Phase 9** |
| **`prope_access_control_key_scope_refusal_total{key_id}` and `prope_access_control_admin_count{workspace_id}`** — two unbounded metric label sets the lock file declares | Shipped as declared, reported in the SUMMARYs, **not silently dropped and not re-raised as a new OQ**. Same class of finding as `OQ-030` | **Phase 9**, with this module's observability sweep |
| **`must_change_password` enforced on every other route** (A-110) | Phase 8 ships the flag's clearing and the login response carrying it; refusing every other route while it is set belongs with the rest of the refusal vocabulary | **Phase 9** |
| **`prope_property_history_rows_total`'s setter** — Phase 6 routed it here | **Re-routed, and the orchestrator should confirm.** The work is a periodic job in `worker` reading **property-history's** table and setting a gauge **property-history declares**; Phase 8 supplies the missing ingredient (`access.list_workspaces()`) and nothing else. See `OQ-037` | **Phase 23** (re-route from Phase 8) |
| **The post-restore tombstone re-apply runbook** (ADR-0036's 30 days, A-151, A-133) | It is a runbook, not code, and the deployment work owns no milestone | **Unowned — PITFALLS §4** |

---

## 6. Declared deviations and gaps that are **not** raised as open questions

Recorded so a reviewer finds them deliberately rather than by diff.

- **Prope has no way to create its first workspace or its first user.** `POST /api/v1/workspaces`
  requires a session, a session requires a user, a user is created by an Admin inside a workspace
  (A-110), there is no self-service sign-up (A-108) and no invitation (A-071). Phase 7 owns identity
  and may ship a bootstrap path; **if it does not, nobody does**, and the honest destination is the
  deployment work that owns no milestone (PITFALLS §4). Phase 8 deliberately does **not** invent one —
  an unauthenticated bootstrap route would be Prope's second unauthenticated path, added under
  deadline pressure, in the phase that just finished arguing there is exactly one. **Not raised as an
  OQ because the phase's four ids are spent; the orchestrator should allocate one if it wants the
  question on the record.**
- **`last_used_at` is never written.** INT-003 calls the side effect *"outside the contract"* and says
  it must never be on the request's critical path; the lock file calls the signal it feeds *weak* in
  its own words; and its only consumer, the gateway, is Phase 19. Phase 8 leaves the column NULL and
  documents the absence at the column.
- **No metric counts tombstones.** The lock declares seventeen metrics and this operation is
  deliberately not among them. Phase 8 does not invent an eighteenth — that would repeat `OQ-039`'s
  finding in the opposite direction — and records the absence instead.
- **Path parameter naming.** `interfaces.md` INT-029 abbreviates the grants path as
  `/prompts/{id}/grants` while `access-control.lock.yml` writes `/prompts/{prompt_id}/grants`. Phase 8
  uses the lock file's spelling, because the lock file is authority 1 and `interfaces.md` is authority
  2 (ORCHESTRATION §1). The route-table literal therefore reads `{prompt_id}`.
- **`/healthz` and `/readyz` are not re-mounted.** INT-030 gives access-control the readiness rule
  *"the database is reachable"*, which is byte-identical to call-ledger's and is what `prope.app`
  already serves. One process, one pair. The `/readyz`-not-gated-on-property-history rule the lock file
  spends a paragraph on is already true, for the stronger reason the lock file itself gives: history is
  a library on this module's own connection, so there is nothing separate to gate on.
- **AC-13's test file is not created by this phase.** It is AC-13's declared `test_ref`, AC-13 is
  Phase 7's requirement, and plan 08-05 is explicitly told to extend it if it exists and to **report
  its absence** if it does not — because creating another phase's requirement's test file here would
  hide a gap the phase gate should surface.

---

## 7. Planner self-check — the checks the deleted critic stage would have made

No exec-critic and no spec-critic reviewed these plans (ORCHESTRATION §10a). The planner ran the
following itself. **Every one is an agent judgement from reading files.**

1. **Every ROADMAP success criterion is owned by exactly one plan.** §2's first table. Four criteria,
   four owners, none doubled, none missing. Two of the four ship as halves and both halves are named
   with their owner phases.
2. **Every requirement id appears in exactly one plan's `requirements:`.** §2's second table. AC-09,
   AC-10, AC-12, AC-14 — four ids, four appearances. `08-03` and `08-04` carry `[]` with the reason in
   §1.
3. **`files_modified` is exhaustive in every plan.** Each plan's task `<files>` lists and every path
   named in a task's `<action>` prose were extracted mechanically and diffed against the frontmatter.
   Every residual is a **read-only** reference — a `@`-context line, a `read_first` entry, a
   `key_links` target, or a file named as a precedent to copy — and each was checked individually
   against the prose that names it. Corrections made during planning: `08-01` gained
   `tests/unit/test_retention_days_bound.py` and `tests/integration/_asgi.py` (both import or cite the
   moved `ErrorCode`), and `src/prope/call_ledger/api.py` (which loses `get_sessionmaker`); `08-01`,
   `08-02`, `08-03`, `08-04` and `08-05` each declare **both** candidate metric modules with the
   condition stated in the frontmatter, because which one Phase 7 created is not knowable from here;
   `08-06` declares `alembic/versions/000N_access_list_workspaces.py`, `src/prope/worker.py` and
   `tests/integration/test_worker_jobs.py` as conditional on a grep whose result decides Task 3.
   **Read-only references are deliberately not declared** — `08-06` names
   `tests/architecture/test_route_table.py` and asserts it is untouched, which is 06-02's D-84 posture.
4. **Every symbol, fixture, constant and file the plans tell an executor to extend was grepped for.**
   Confirmed present in the tree today: `assembled_routes`, `declared_action`, `declares_session`,
   `declares_action`, `MANAGEMENT_ACTIONS`, `ManagementAction`, `ManagementRefusal`, `Session`,
   `require_session`, `SESSION_COOKIE`, `SESSION_REQUIRED`, `ErrorCode`, `ApiError`, `ErrorEnvelope`,
   `PageRequest`, `install_error_envelope`, `_envelope`, `REQUEST_ID_PREFIX`, `get_sessionmaker`,
   `path_workspace`, `workspace_transaction`, `SET_TENANT`, `LOGGABLE_FIELDS`, `configure_logging`,
   `WorkspaceEnumerator`, `run_worker`, `migrate_engine`, `app_sessionmaker`,
   `postgres_container`, `EXPECTED_ROUTES`, `UNVERSIONED`, and every test in
   `tests/architecture/test_route_table.py` that these plans edit, **each cited by its exact test
   name**.
   Created by phases that execute first: `src/prope/property_history/` and `append(session, event)`
   (**Phase 5**, D-66/D-67/D-68 — the two-argument signature returning the minted id), `install_registry`
   / `registered_registry` / `reset_registry` (**Phase 5**), `tests/contract/__init__.py` (**Phase 5**),
   `tests/chaos/` (**Phase 6**), the `load` pytest marker (**Phase 3**), the `history` schema, both
   tables and the 31-row seed including all ten access-control event names (**Phase 4** — verified
   against `04-01-PLAN.md`'s seed table, and `access_granted` / `access_revoked` / `user_tombstoned`
   are all present, which is the check the orchestrator asked for), and the whole `access` schema,
   `may()`, `access.lookup_session`, `access.lookup_api_key` and the `role_permission` seed
   (**Phase 7**), plus `prope.access_control.vocabulary.Action` (07-01 D-98, twenty-five members),
   `prope.access_control.bootstrap.list_workspaces` (07-01), `access.list_workspaces()` (07-01) and
   `build_workspace_enumerator` with `ObservedWorkspaces` **deleted** (07-03).
   **`tests/access_control/__init__.py` and its `failing_append()` helper are created by `08-01` in
   this phase**, and `08-03`, `08-04` and `08-05` are each told to import rather than reinvent.
   **The live risks are §8's first three rows: everything Phase 7 owns.**
5. **No plan hardcodes an Alembic `down_revision`** — both migrations are named `000N_…` with the
   placeholder stated and a prohibition against hardcoding; grepped, and the only occurrences of
   `down_revision` are the instructions not to hardcode it. **No plan gates on `ruff format --check`**
   — grepped; the only occurrences are the sentences saying it is not a gate. **No plan references a
   `gsd-core` path** — grepped, zero occurrences, and no `<execution_context>` block was written.
   **No per-plan `<verify><automated>` block runs the whole suite** — grepped; `uv run pytest -q`
   appears only in `08-06`, the last plan, in its Task 4 and its `<verification>`.

---

## 8. Risks the executor must know before it starts

| Risk | Why it matters | What to do |
|---|---|---|
| **Phase 7's `may()` signature is unknown to this planner.** Every plan in this phase calls it, and `08-02`'s `visible_subject_filter` must match its argument convention | Phase 7 was being planned **concurrently** with Phase 8 by a different agent. Whether `may()` takes an `AsyncSession` first, what its actor and subject value objects are called, and whether it exposes a role→action helper are all Phase 7's to decide | **Re-ground against the tree first** (ORCHESTRATION §7). Match whatever Phase 7 shipped; do not invent a second convention one plan later. Report every difference as drift in the SUMMARY |
| **Phase 7's `vocabulary.Action` decides ten `ManagementAction` string literals**, and Phase 7's **D-99** already changed two of them | Phase 7 creates `prope.access_control.vocabulary.Action` with A-115's twenty-five names and rules that **A-115's spellings beat INT-001's** — so `prompt.change_access` is `prompt.grant` and `prompt.change_owner` is `prompt.transfer_owner`. A guessed spelling ships a route declaring an action that is not a permission, and `08-06`'s bridge test fails at the end of the phase rather than at the plan that guessed | The members are in **one block** in `session_auth.py`, and every value is `Action.<MEMBER>.value` — **imported, never retyped** — so a vocabulary rename is a compile-time break rather than a silent divergence. Read `vocabulary.py` before writing any of the four blocks |
| **Phase 7 may already have mounted `POST /api/v1/auth/login` and may already ship a tombstone service** | Two routes on one path is prompt-registry's route-uniqueness rule broken in the way that is hardest to see, because both copies work. And a second tombstone implementation would split one transaction's guarantee across two functions. Phase 7 plan 07-01's threat table says *"there is no `/auth/login` route until Phase 8"*, so the route is expected to be Phase 8's — **confirm rather than assume** | `08-04` and `08-05` both carry the instruction: **extend, do not duplicate**, and report it as drift. `08-05` additionally must not create AC-13's test file if it is absent |
| **Phase 7's D-101 wires `require_session` in a way that creates a forbidden transitive edge, and Phase 8 deliberately does not fix it** | `require_session(request, session_cookie)` calls `authenticate_session`, so `session_auth` imports `prope.access_control`; `prope.call_ledger.api` imports `session_auth`; therefore call-ledger transitively depends on access-control — the edge ADR-0018 names. It is invisible until release-control's owed AC-14 import-linter contract lands in Phase 24 | **Do not rewrite the boundary** (D-119). Confirm the import exists, record it in the SUMMARY and in §9 here, and name Phase 24. D-116's `management_api.py` move closes the other half of the same problem, which is the half that was cheap |
| **`08-06` Task 3 changed from a build to a verification while this phase was being planned** | Phase 7 plans 07-01 and 07-03 took `access.list_workspaces()` and the enumerator wiring, and 07-03 **deletes** `ObservedWorkspaces` with a prohibition against keeping it. An executor following this plan's first draft would have written a duplicate migration | Task 3's first step is a grep with three named outcomes. Outcome 1 (expected) is *touch nothing*; outcome 2 (both exist) is *report, do not clean up*; outcome 3 (Phase 7 slipped) is *stop and escalate*, with the fallback written out but not authorised silently |
| **`08-01` moves the A-045 envelope across a package boundary** and six files import it | A move that changes behaviour is not a move. The existing suite is the assertion that it did not | The acceptance criterion is explicit: **the diff over `tests/` contains no change inside any `assert`**. If one has to move, that is drift and the SUMMARY names the assertion |
| **`08-01`'s migration edits a Phase 4 test in another module's file** | `test_history_schema_ships_its_guarantees.py` asserts *"every other action's `detail_keys` is empty"*. Registering `level` on `access_granted` makes that false, and the edit must land in the **same** change as the migration or the suite is red | Rename the test to `..._and_the_three_declared_key_sets`, add the assertion, and **leave the `requires_reason` set and the strictness of the remaining twenty-eight exactly as they are** |
| **The tombstone writes into more than one tenant in one transaction** | `workspace_transaction` sets one tenant context and the fan-out writes N events across N workspaces. The tenant policy's `WITH CHECK` will refuse the ones outside it — which is the policy working correctly | `08-05` Task 1 names three options, refuses the one that weakens atomicity, and prefers re-issuing `set_config` per workspace **inside one transaction**. **Check what Phase 7's policy actually permits rather than assuming**, and write the argument at the code — the next reader will assume it is a bug |
| **Four plans edit `tests/architecture/test_route_table.py` and its counts are arithmetic** | A wrong count is a red test at the gate, three plans after the mistake | The arithmetic is fixed and is written in every plan that touches it: **5 call-ledger operations + 16 access-control operations = 21 versioned; 23 including the two unversioned health routes**; distinct paths end at 17. Per-plan checkpoints: 10 → 13 → 22 → 23 |
| **`08-03` and `08-04` may ship metric labels that a Phase 2 test forbids project-wide** | `tests/broker/test_publish_confirm_failures.py`'s walk asserts no `prope_*` metric carries `workspace_id`, and the lock file declares `prope_access_control_admin_count` with exactly that label | **Ship what the lock declares, report what the walk does, and do not narrow the walk.** `08-06`'s gate names this as one of three predicted red candidates. Route the decision to Phase 9 with `key_id` |
| **`08-06` Task 3 may write a `SECURITY DEFINER` migration** | A duplicate `CREATE FUNCTION` if Phase 7 already shipped it; a red four-and-only-four test if the count is not updated | **The grep is the task's first step** and its result is recorded in the SUMMARY. If the four-and-only-four test goes red at four names, the migration is wrong — not the test |
| **`src/prope/access_control/` may not exist at all if Phase 7 slipped** | Every plan in this phase extends it | Phase 8 depends on Phase 7 and execution is serial (ORCHESTRATION §7, §8 batch B3: 7 → 8 → 9). If it is absent, stop and report rather than building Phase 7's schema inside Phase 8 |

---

## 9. Pre-existing, still open, and not this phase's to fix

- **`uv run ruff format --check` fails repo-wide** on the `line-length` disagreement (`ruff.toml` says
  120, the repo is hand-wrapped to ~100). **Broken Window #1.** Every plan here writes in the house
  ~100 style, lists `ruff check` as its gate, and does not list `ruff format --check`.
- **Broken Window #4 is binding on this phase more than on any before it.** Sixteen new routes is the
  largest single addition to the route table so far, and a naive `app.routes` walk would have found
  none of them while passing. Every route assertion in this phase goes through `assembled_routes()`,
  and `08-06`'s mutation control is the proof that the walk can fail.
- **Broken Window #3** — `ObservedWorkspaces` skipping idle workspaces — is **Phase 7's** (plans 07-01
  and 07-03). `08-06` Task 3 verifies the closure and escalates if it did not happen; it does not
  build. If `ObservedWorkspaces` survives alongside the real enumerator, that is a Phase 7 finding and
  Phase 8 reports it rather than cleaning it up.
- **A forbidden transitive edge is left open on purpose.** Phase 7's D-101 makes `session_auth` import
  `prope.access_control`, and call-ledger's routes import `session_auth` — so call-ledger transitively
  depends on access-control (ADR-0018's forbidden edge). Phase 8 records it (D-119) and does not
  rewrite Prope's authentication boundary to close it. **Owner: Phase 24's import-linter contract**
  (release-control's owed AC-14). This is the one item in this file that a reviewer should be
  unsatisfied by.
- **`OQ-018` … `OQ-021`, `OQ-022` … `OQ-039` remain unresolved.** No phase resolves an open question
  by editing a spec; later phases inherit each deviation as declared. `OQ-021` in particular is leaned
  on by D-116 and is **not** answered by it.
- **The root `Dockerfile` and `docker-compose.yml` are boilerplate from another project**, recorded in
  Phase 2's `deferred-items.md` and unchanged.
- **The deployment stack and the React SPA own no milestone** (PITFALLS §3, §4). Three items in this
  phase point at that gap: the first-workspace bootstrap (§6), the post-restore tombstone re-apply
  runbook (§5), and ADR-0053's translation catalogue for the **five** new `ErrorCode` members this
  phase adds — `forbidden` (08-01), `authentication_failed`, `last_admin`, `email_taken` (08-04) and
  `membership_active` (08-05). A code the SPA's catalogue has never seen renders as nothing at all,
  and nothing in the phase plan owns the catalogue.
