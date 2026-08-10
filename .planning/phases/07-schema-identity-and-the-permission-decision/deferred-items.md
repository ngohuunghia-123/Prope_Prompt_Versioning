# Phase 07 — deferred items, mappings, and the planner's own self-check

**Phase:** 07 — Schema, identity, and the permission decision · **Module:** access-control ·
**Milestone:** M3 (opens it) · **Depends on:** Phase 6

Written by the phase planner under the MINIMAL PROTOCOL (ORCHESTRATION §10a). There is no CONTEXT,
RESEARCH, PATTERNS, DISCUSSION-LOG or COVERAGE artifact for this phase, and **no critic reviewed these
plans before execution.** Everything the deleted artifacts carried lives in the plans' `<objective>`
sections; everything the deleted *checks* would have caught is self-checked in §7 below.

Executors append to this file. Do not renumber the sections.

---

## 1. The phase's whole `docs/` footprint

`docs/` is read-only with exactly one exception: **creating** `docs/brainstorm/open_questions/OQ-NNN.md`.
The allocated range for this phase was **OQ-041 through OQ-045** and **all five were consumed.** Every
one is a real spec conflict found while planning; none is a placeholder.

| Id | One line | Severity | Named against |
|---|---|---|---|
| **OQ-041** | There are two closed action vocabularies in the repository — A-115's 25 permission names and `session_auth.ManagementAction`'s 5 `call_ledger.`-prefixed route labels — and they share no member, while AC-10 asserts they are one | medium | `docs/modules/access-control.lock.yml` AC-10; A-115; `src/prope/session_auth.py` |
| **OQ-042** | A-115 and INT-001 name two different actions for the same two prompt-registry operations (`prompt.transfer_owner`/`prompt.change_owner`, `prompt.grant`/`prompt.change_access`), and `revision.create` appears in A-115 with no declared caller | low | A-115; `docs/architecture/interfaces.md` INT-001 caller table |
| **OQ-043** | `access_level` is a parameter of every permission decision in Prope and its value set is declared nowhere — this is the field that decides BR-01 | medium | ADR-0020's `subject` signature; `docs/modules/prompt-registry.lock.yml` `prompt_property.fields` |
| **OQ-044** | Three columns in the `access` schema are named with a status and enumerated with one value: `user.status`, `workspace_member.status`, and `api_key.scope_model_names`'s type | low | `docs/modules/access-control.lock.yml` `data.owns` |
| **OQ-045** | The four-and-only-four `SECURITY DEFINER` assertion names `evaluation.claim_next_run()`, which cannot exist before Phase 16, so an exact equality is unwritable for nine phases | medium | `.claude/CLAUDE.md`; ADR-0042 as amended; lock `test_plan.security` T-003 |

**Nothing else under `docs/` was written or edited.** No lock file, no ADR, no `interfaces.md` line, no
assumption file. Highest OQ id on disk when this phase was planned was **OQ-039** (other planners
consumed 033-039 concurrently); this phase's range was pre-allocated and did not collide.

**`.planning/` files this phase's planner did NOT touch and its executors must not:**
`ORCHESTRATION.md`, `ORCHESTRATION-DECISIONS.md`, `WINDOWS.md`, `ROADMAP.md`, `REQUIREMENTS.md`,
`STATE.md`, and every other phase's directory.

---

## 2. ROADMAP success criterion → plan. Each owned by exactly one.

| # | Success criterion (ROADMAP, Phase 7) | Owning plan | Requirement | Proven by |
|---|---|---|---|---|
| 1 | An actor with two role bindings, one granting `prompt.edit` and one not, is allowed — permissions union and nothing subtracts | **07-02** | AC-03 | `tests/unit/test_effective_permission_is_a_union.py` (the union, no container) + `tests/integration/test_permission_matrix_is_rows.py` (end to end through `may()`) |
| 2 | An action string outside the vocabulary is denied, `unknown_action_total` increments, and no exception reaches the caller | **07-02** | AC-04 | `tests/unit/test_unknown_action_denies.py`, including the no-query assertion against a session that raises if touched |
| 3 | Removing or demoting the last Admin of a workspace is refused, `admin_count` stays 1, and `last_admin_refused_total` increments | **07-04** | AC-08 | `tests/integration/test_last_admin_cannot_be_removed.py` — both routes, plus the engine's own refusal of a hand-written statement |
| 4 | Tombstoning a person nulls `email`, `display_name` and `password_hash`, deletes every session they hold, and makes a sign-in with the former email byte- and timing-identical to one with an email that never existed | **07-05** | AC-13 | `tests/integration/test_tombstone_clears_identity_and_sessions.py` + `tests/security/test_tombstoned_email_is_indistinguishable.py` |

No criterion is owned by two plans. No criterion is unowned.

## 2a. Requirement → plan. Each id in exactly one plan's `requirements:`.

| Requirement | Plan | Note |
|---|---|---|
| **AC-03** | 07-02 | |
| **AC-04** | 07-02 | |
| **AC-08** | 07-04 | |
| **AC-13** | 07-05 | Row-level half here; the HTTP byte-comparison over the login response is Phase 9's — see §5 |

`requirements:` is `[]` on plans **07-01**, **07-03** and **07-06**. That is deliberate: 07-01 is the
tracer and carries the schema and the session seam, which no requirement id points at; 07-03 closes a
Broken Window; 07-06 writes two acceptance criteria that PITFALLS gap 1 records as **owed and never
written as rows**, so no id exists to claim.

---

## 3. Plans, waves and dependencies

| Plan | Wave | depends_on | What it is |
|---|---|---|---|
| **07-01** | 1 | — | **Tracer.** The `access` schema in one migration (8 tables, 7 policies, 3 `SECURITY DEFINER` functions, the 35-row matrix seed), argon2id, sign-in, the session row, and `require_session` filled |
| **07-02** | 2 | 07-01 | `may()` — the closed vocabulary, the union, the unknown action |
| **07-03** | 2 | 07-01 | `access.list_workspaces()` replaces `ObservedWorkspaces` (Broken Window #3) |
| **07-04** | 3 | 07-01, 07-02 | Membership and role commands, and A-117's last-Admin refusal |
| **07-05** | 4 | 07-01, 07-04 | The tombstone |
| **07-06** | 5 | all | The two owed acceptance criteria, and the phase gate |

**Wave-2 disjointness, checked by hand because the orchestrator enforces it:** 07-02 modifies
`{vocabulary.py, permissions.py, access_control/__init__.py, observability.py,
tests/access_control/__init__.py, 3 test modules}`; 07-03 modifies `{worker.py,
tests/integration/test_worker_jobs.py}`. **Disjoint.** 07-03 *imports* `list_workspaces` and
`seed_workspace` from files 07-01 created and modifies neither.

Execution is serial regardless (ORCHESTRATION §7). The waves express correctness ordering.

---

## 4. UNCONFIRMED adoptions — for the phase UAT and `ORCHESTRATION-DECISIONS.md`

`mode: yolo`. Each of these was decided by the planner on the user's behalf, is written out in full in
the owning plan's `<objective>` with its rejected alternatives, and appears as a `<human-check>` in
that plan's `<verification>`. **All six need a human ruling; none of them blocks execution.**

| # | Decision | Plan | Reversibility | What the user is being asked |
|---|---|---|---|---|
| **U-07-1** | **`may()` is visibility AND permission**, each a union. A role granting `prompt.read` does **not** make every prompt in the workspace readable; visibility comes only from ownership, a `prompt_grant`, or an `access_level` of `workspace` (D-104) | 07-02 | moderate | This is the most consequential interpretation in the phase. **A-111's literal text reads the other way** — *"allows the action if any of the actor's workspace role bindings grants it"* — and taken literally it destroys BR-01 on contact with A-007's seeded matrix, because Viewer, Owner and Reviewer all hold `prompt.read`. The reconciliation is A-111's own closing paragraph: private-by-default is a *starting state*, not a subtraction. Confirm the reading |
| **U-07-2** | **The `role_permission` seed**: 35 rows over A-007's four roles, with `prompt.edit` on Owner alone, `revision.approve` on Reviewer alone, `release.create` on Admin alone, and `release.break_glass` on Admin alone (07-01, Task 2) | 07-01 | cheap (a re-seed) | Every row is derived from A-007's four sentences, A-112 and ADR-0054 §8 and from nothing else, and the edit/review/release separation the constraints table calls non-negotiable is visible in the seed itself. OQ-006 owns the real matrix. Confirm it is an acceptable placeholder to build the pilot against |
| **U-07-3** | **`AccessLevel` is `private | workspace`**, `private` is the default, and an unrecognised value behaves as `private` (D-104, OQ-043) | 07-02 | cheap | The value set is declared in no document. Confirm the two values and the fail-closed direction |
| **U-07-4** | **A-117 is enforced twice** — an application refusal carrying a message and a counter, plus a deferred constraint trigger that refuses at `COMMIT` (D-110) | 07-04 | costly (a landed revision) | `alembic/versions/0004_…` recorded a *knowing exception* to database-first for a cross-table rule of the same shape (A-055). The difference argued here: A-055's failure is a stray row, A-117's is a permanently frozen tenant with **no recovery path** and A-012 rules out building one. Confirm the extra guard is wanted |
| **U-07-5** | **The tombstone is ONE transaction that moves the tenant marker between workspaces** with `SET_TENANT`, deviating from `src/prope/db/session.py`'s stated one-workspace-per-transaction posture (D-112) | 07-05 | costly | The two alternatives both fail: N+1 transactions leave a half-erased person in every ordering (an erased name with live sessions, or cleared grants with the name intact), and a `SECURITY DEFINER` bypass is a forbidden fifth object *and* a write-performing bypass ADR-0051 rules out by shape. Confirm |
| **U-07-6** | **The `SECURITY DEFINER` assertion is written as *sanctioned minus a declared not-yet-built list*** rather than as a literal four (D-115, OQ-045) | 07-06 | cheap on the list, one-way on the count | `.claude/CLAUDE.md` says *"exactly these four"* and one of the four cannot exist before Phase 16. Confirm the reading, or accept OQ-045's option (a): restate the rule in `.claude/CLAUDE.md` and lock T-003 |

Two further one-phase postures that are consequences rather than decisions, and that a human should
see before Phase 8 runs:

- **`require_session` opening five routes across workspaces.** Filling the seam makes call-ledger's
  five `/api/v1` routes reachable by **any** session holder in **any** workspace, because call-ledger
  performs no permission check by design (ADR-0018) and `may()` is not wired into routes until Phase 8.
  Declared in `src/prope/session_auth.py`'s docstring, in 07-01's objective, and as `T-07-10`.
- **An unlimited login path.** ADR-0043's limiter is Phase 9's. Phase 7 defines
  `login_rate_limited_total` (D-40's rule) and increments it nowhere. Bounded meanwhile by there being
  no `/api/v1/auth/login` route until Phase 8 — the sign-in function is reachable only from tests.
  `T-07-09`.

---

## 5. Routed forward — owed work with a named owner

### 5a. PITFALLS gap 1 — the three owed access-control criteria that have no ids

`.planning/research/PITFALLS.md` gap 1 records three acceptance criteria for this module that BSP
step 4 wrote as comments and the step-6 sweep never folded in. They were to be AC-13/14/15 and three
*different* criteria took those ids when OQ-017 resolved the same day, so **no requirement points at
them.** Their routing:

| Owed criterion | Owner | Where |
|---|---|---|
| (a) The `SECURITY DEFINER` set is exactly the sanctioned functions, each REVOKEd from PUBLIC with an empty `search_path` | **Phase 7** | plan 07-06 Task 1 — `tests/security/test_security_definer_set_is_exactly_sanctioned.py` |
| (b) ADR-0035's RLS coverage test extended to reach `prompt_grant` and `workspace`, failing if its second clause is removed | **Phase 7** | plan 07-06 Task 2 — restated for ADR-0045, which retired the *second clause* in favour of a map entry: `POLICIED_ON_ANOTHER_COLUMN` is asserted rather than skipped, and the mechanism is tested against a synthetic input so the assertion cannot be quietly deleted |
| (c) The login limiter performs **no argon2id verification** at threshold even with the correct password, asserted by timing or a hasher spy | **Phase 9** | Not written here. ADR-0043's limiter is Phase 9's and a test in Phase 7 would assert against something that does not exist; a test asserting its *absence* would have to be deleted in Phase 9. Phase 7 ships the hasher-spy technique in `tests/security/test_tombstoned_email_is_indistinguishable.py`, which Phase 9 can reuse directly |

### 5b. Everything else this phase deliberately did not do

| Item | Owner | Note |
|---|---|---|
| INT-002 `visible_subject_filter`, INT-003 `authenticate_api_key`, INT-004 `may_resolve` | **Phase 8** | Phase 7 ships INT-001 (`may`) and INT-005 (`authenticate_session`) only. `access.lookup_api_key` **is** created by 07-01's migration and exercised by a direct SQL test; its Python caller is Phase 8's |
| The fifteen INT-029 routes, including `POST /api/v1/auth/login`, `/logout`, `/password`, the member routes, the grant routes, the key routes, `/permissions` and `/users/{id}/tombstone` | **Phase 8** | Phase 7 ships the **commands** those routes call. Each command takes its `actor_id` as a parameter and performs **no** permission check — the route checks at the module's edge (ADR-0020) |
| **AC-14** — one `user_tombstoned` event per workspace, empty details, no reason | **Phase 8** | Phase 7's tombstone **writes** those events (A-014: no state change without its event, in the same transaction) and asserts the count and shape as part of AC-13's test. **Phase 8 owns the numbered criterion.** ⚠️ *Flagged for the orchestrator:* Phase 8's planner ran concurrently and may plan to implement the same append. If both plans write it, the phase-8 executor should find it already there and report it as satisfied rather than duplicating it |
| **AC-13's HTTP half** — *byte-identical* over a login **response** | **Phase 9** | Phase 7 asserts the property at the function: identical return value, identical work, hasher spy. Phase 9 owns the login path and byte-compares the three responses A-144 names — unknown email, wrong password, rate-limited — including status, headers and body |
| A-116's refusal shapes — not-found vs forbidden-naming-the-permission | **Phase 9** | `may()` returns a bare `bool` (INT-001) and the *shape* is the caller's to render. Phase 7 records the ground of every decision in a log line and never across the seam |
| The `admin_count` gauge for workspaces that existed before this phase | — | The gauge is set on every successful membership change and on no other path. A workspace that never changes membership after creation never re-publishes its count. Not a gap in AC-08, which is about the count *not moving* on a refusal, but worth knowing before writing `AccessControlAdminCountZero`'s rule |
| `.planning/WINDOWS.md` Broken Window #3 closure | **phase bookkeeping** | Plan 07-03 closes the window in code and is forbidden to edit the file. 07-06's SUMMARY lists the diff |
| Ticking AC-03, AC-04, AC-08, AC-13 in `.planning/REQUIREMENTS.md`; ROADMAP checkbox and Plans line; STATE.md | **phase bookkeeping** | Same reason. 07-06 Task 3 lists the exact rows |

---

## 6. Discoveries an executor or a later phase needs, that are not in any plan's happy path

1. **`retention_days` still has no upper bound at the time of planning.** `src/prope/call_ledger/schemas.py:394`
   reads `retention_days: int` with a docstring that argues *against* a lower bound and says nothing
   about an upper one. CR-01 is Phase 3's and Phase 3 was executing while this phase was planned.
   **Plan 07-01 Task 1 is a gate that halts the phase if the bound is absent**, because filling
   `require_session` is what makes `PUT /api/v1/workspaces/{id}/retention` reachable and
   `timedelta(days=…)`'s `OverflowError` is not matched by `classify_write_failure`.
2. **Every existing retention-sweep test seeds ledger rows for workspace ids that have no
   `access.workspace` row.** The real enumerator reads `access.workspace`, so the moment plan 07-03
   lands, those tests enumerate zero workspaces and delete nothing — failing in a way that reads like a
   retention bug rather than a fixture gap. Plan 07-03 Task 2 adds the seeding fixture and forbids the
   tempting "fix" of falling back to the ledger.
3. **`_StopOnFirstSighting` subclasses `ObservedWorkspaces` as a timing trigger, not as an observer.**
   It is the only mechanism in the repository that can hit *"a stop arriving mid-window"*
   deterministically (T-02-19). Deleting the class without keeping the observation *point* would cost a
   proven property. D-109 keeps the hook as a plain `Callable[[str], None]`.
4. **A `SECURITY DEFINER` trigger function would be a fifth sanctioned object.** Plan 07-04's
   constraint trigger must be `SECURITY INVOKER` (the default). It is a one-word mistake with a
   plausible-sounding justification, it would fail plan 07-06's exact-set test, and 07-06 asserts
   `access.assert_workspace_has_an_admin`'s absence from the set **by name** so the failure message
   says which one.
5. **`access.lookup_session` knows nothing about `user.status`.** A session row that survived a
   tombstone would still authenticate a person with no password and no name. This is why plan 07-05
   deletes sessions inside the tombstone's own transaction rather than relying on `may()`'s
   `is_active_member` check.
6. **A-117 and A-151 compose, and the composition is load-bearing.** A person cannot be removed while
   they are a workspace's last Admin, therefore they cannot reach *no active membership*, therefore
   they cannot be tombstoned — which is what keeps the tombstone's `role_binding` deletions from ever
   meeting plan 07-04's deferred trigger with an Adminless outcome. Worked out in 07-04 Task 1,
   asserted in 07-05 Task 2.
7. **Argon2id costs ~60 ms per verification, by decision, and the suite now runs a lot of them.**
   `tests/unit/test_argon2id_cost_is_asserted.py` exists so that speeding the suite up by lowering the
   cost is a failing test rather than a commit. 07-06's SUMMARY records the measured whole-suite wall
   time so the effect is a number.
8. **`prope_app` holds no `DELETE` on `access."user"`.** That is the privilege half of *nothing
   un-tombstones a row*, and it means any future "delete a user" feature is a migration and a review,
   not a route.
9. **Phase 4/5 name drift is possible and is called out in every plan's `<context>`.** Specifically
   `append` vs `record_event`, `truncate_owned_tables` vs `truncate_ledger`, and
   `SCHEMA_TABLES`/`LIST_OWNED_TABLES` vs `LEDGER_TABLES`/`LIST_LEDGER_TABLES`. Executors use what is
   on disk and report the difference; they do not follow this file's spelling.

---

## 7. The planner's self-check — because no critic ran

ORCHESTRATION §10a deleted the two plan critiques. These five checks are the ones `critic-exec` and
`critic-spec` would have made, run by the planner against its own output.

**1. Every ROADMAP success criterion is owned by exactly one plan.** ✅ §2. Four criteria, four owning
plans (07-02 owns two), no overlap, no gap.

**2. Every requirement id in AC-03, AC-04, AC-08, AC-13 appears in exactly one plan's `requirements:`.**
✅ §2a. 07-02 `[AC-03, AC-04]`, 07-04 `[AC-08]`, 07-05 `[AC-13]`; 07-01, 07-03 and 07-06 are `[]`.

**3. Every file named in a task's `<action>` or `<files>` appears in that plan's `files_modified`.**
✅ Read back task by task. Four files are named in an action **as read-only** and are declared as such
in a `files_modified` comment rather than as modified paths, because a path listed as modified that the
plan forbids writing is a declaration the orchestrator cannot trust:

- 07-01 — `src/prope/call_ledger/schemas.py` (CR-01 verification, Task 1) and
  `src/prope/call_ledger/api.py` (`get_sessionmaker`'s 503, reproduced not imported, Task 4). Both
  tasks carry an acceptance criterion asserting `git diff --stat src/prope/call_ledger/` is empty.
- 07-02 — `src/prope/session_auth.py` (one `ManagementAction` value imported as a test case).
- 07-03 — `src/prope/access_control/bootstrap.py` and `tests/access_control/__init__.py` (imports),
  and all of `src/prope/call_ledger/` (D-108's whole point).

`tests/integration/test_migration_chain.py` is declared in **07-04** for a change that is expected not
to be needed, because the executor may legitimately have to touch it if plan 04-01's second-upgrade
snapshot covers `pg_trigger`.

**4. Every symbol, fixture, constant and file a plan tells an executor to extend actually exists.**
✅ Grepped. Verified present on disk today: `alembic/ddl.py`'s `assume_migrate_role`, `reset_role`,
`enable_tenant_rls` (**including its `column=` parameter**, which is what makes
`access.workspace`'s policy on `id` a one-line call) and `grant_table`; `db/session.py`'s `SET_TENANT`
and `workspace_transaction`; `db/engine.py`'s `Settings`/`build_engine`/`build_sessionmaker`;
`session_auth.py`'s `SESSION_REQUIRED`, `SESSION_COOKIE`, `ManagementRefusal`, `Session`,
`require_session`, `ManagementAction`, `assembled_routes`, `declared_action`, `declares_session`;
`schemas.py`'s `ErrorCode.INTERNAL_ERROR == "internal_error"`; `api.py`'s `get_sessionmaker`;
`observability.py`'s `LOGGABLE_FIELDS` and the D-40 argument; `worker.py`'s `ObservedWorkspaces`,
`WorkspaceEnumerator`, `build_retention_resolver`, `sweep_expired_bodies`, `run_worker`;
`tests/conftest.py`'s engine fixtures; `tests/architecture/test_tenant_coverage.py`'s
`GLOBAL_TABLES`/`EXPECTED_ABSENT_SCHEMAS`; `tests/architecture/test_route_table.py`'s exact set
equality over `MANAGEMENT_ACTIONS`; `tests/integration/test_worker_jobs.py`'s `_StopOnFirstSighting`
and `test_a_workspace_the_enumerator_omits_keeps_its_expired_bodies`.

Verified as **created by an earlier phase that executes before this one**, and flagged in every
plan's `<context>` for re-grounding: `property_history.append(session, event) -> str`,
`HistoryEventDraft`, `ActorType`, `install_registry`/`registered_registry`/`reset_registry`, the
31-row `history_action_registry` seed (including all ten access-control event names, with
`user_tombstoned` carrying empty `detail_keys` and `requires_reason = false`),
`truncate_owned_tables`/`LIST_TRUNCATABLE_TABLES`, and
`test_migration_chain.py`'s `SCHEMA_TABLES`/`LIST_OWNED_TABLES`.

Verified as **created by an earlier plan in this phase**: everything under
`src/prope/access_control/` and `tests/access_control/` — all of it by 07-01, with the extension
points each later plan touches named.

**5. No plan hardcodes an Alembic `down_revision`, gates on `ruff format --check`, references a
`gsd-core` path, or puts the whole-suite `uv run pytest -q` in a per-plan verify block.** ✅ Grepped
the phase directory. Both revisions are named `000N_<slug>.py` with an explicit instruction to read
`uv run alembic heads` and wire the head found there. `ruff format --check` appears only in sentences
saying it is **not** a gate. No `gsd-core` path appears anywhere. `uv run pytest -q` appears only in
plan **07-06**, the last plan, in its gate task — every other plan's `<verify><automated>` names its
own targeted tests.

**One thing this self-check cannot do**, stated so it is not mistaken for coverage: it verifies that
the plans are *internally consistent and grounded in the tree as it is today*. It does not verify that
the tree at execution time matches — Phases 3, 4, 5 and 6 all land between this file being written and
plan 07-01 running. Every plan's `<context>` carries the re-grounding instruction and names the exact
symbols most likely to have moved.

---

## 8. `D-NN` range consumed

**D-96 through D-115 — all twenty, none spare.** Numbering is continuous across the project and never
restarts (phase 1: D-01..D-08 · phase 2: D-09..D-25 · phase 3: D-26..D-45 · phase 4: D-46..D-65 ·
phase 5: D-66..D-80 · phase 6: D-81..D-95). **Phase 8 starts at D-116.**

| Plan | Range | Decisions |
|---|---|---|
| 07-01 | D-96 … D-103 | one revision for the whole stack · three definer functions land here · a separate action enum · A-115 wins over INT-001 · the argon2 pin and the cost asserted from the hash · `require_session` reads `app.state` and refreshes nothing · the absent-user hash is minted at import · the matrix seed is excluded from the truncate fixture |
| 07-02 | D-104 … D-107 | `may()` is visibility AND permission · the decision is pure and the read is separate · the vocabulary check is first and never raises · a `consumer_key` actor is denied and counted |
| 07-03 | D-108 … D-109 | the enumerator is bound in the composition root · `ObservedWorkspaces` is deleted and the observation point survives as a callback |
| 07-04 | D-110 … D-111 | A-117 is enforced twice, and the trigger is `SECURITY INVOKER` · removal ends the member's sessions in that workspace |
| 07-05 | D-112 … D-114 | one transaction that moves the tenant marker · the tombstone refuses an active membership and a second run · no `reason` parameter at any layer |
| 07-06 | D-115 | the definer assertion is *sanctioned minus not-yet-built* and stays an equality |
