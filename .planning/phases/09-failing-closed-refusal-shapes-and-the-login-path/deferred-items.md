# Phase 09 — deferred items, mappings, and the planner's own self-check

**Phase:** 09 — Failing closed, refusal shapes, and the login path · **Module:** access-control ·
**Milestone:** M3 (**closes it**) · **Depends on:** Phase 8

Written by the phase planner under the MINIMAL PROTOCOL (ORCHESTRATION §10a). There is no CONTEXT,
RESEARCH, PATTERNS, DISCUSSION-LOG or COVERAGE artifact for this phase, and **no critic reviewed these
plans before execution.** Everything the deleted artifacts carried lives in the plans' `<objective>`
sections; everything the deleted *checks* would have caught is self-checked in §8 below. Every judgement
in this file is an **agent judgement made by reading files** — no deterministic detector exists in this
environment and nothing here is detector output.

**This phase CLOSES milestone M3, so ORCHESTRATION §9a binds it.** Plan **09-06 Task 4** walks
`docs/modules/access-control.lock.yml`'s `acceptance_criteria` and all seven `test_plan` categories
clause by clause and appends the result to this file under `## M3 milestone audit (ORCHESTRATION §9a)`.
That heading is **reserved and empty until the executor writes it** — the planner seeded the list it
starts from (§6 below), not the walk.

Executors append to this file. Do not renumber the sections.

---

## 1. The phase's whole `docs/` footprint

`docs/` is read-only with exactly one exception: **creating** `docs/brainstorm/open_questions/OQ-NNN.md`.
The allocated range was **OQ-050 through OQ-054** and **all five were consumed.** Every one is a real
spec conflict found while planning; none is a placeholder.

| Id | One line | Severity | Named against |
|---|---|---|---|
| **OQ-050** | Four criteria mapped to Phase 9 assert over six modules that do not exist until Phases 12-24 — AC-1's *"any registry, evaluation, or release endpoint … and search"*, AC-2's *"create a revision"*, AC-5's *"the gateway's response"*, AC-11's *"any module … per caller"* | medium | `.planning/REQUIREMENTS.md` traceability rows AC-01/AC-05/AC-11; lock `acceptance_criteria` AC-1, AC-2, AC-5, AC-11; lock `test_plan.e2e` |
| **OQ-051** | A-110 requires a forced password change at first sign-in and **nothing declares what the other routes do while it is pending** — no acceptance criterion, no status code, no `ErrorCode` member, no exemption set | medium | lock `apis.exposes`' `/auth/password` line; A-110; lock `acceptance_criteria` (absence); `interfaces.md` INT-029's failure-semantics line |
| **OQ-052** | AC-15 requires a catalogue key; ADR-0053 §3 requires a `vi` catalogue and a CI check failing the build on a missing key; **neither exists and neither has an owner**, and seven keys are now in code | medium | lock AC-15; ADR-0053 §1/§3/§7; PITFALLS §5 |
| **OQ-053** | Two declared metric labels are unbounded identifier spaces — `key_scope_refusal_total{key_id}` and `admin_count{workspace_id}` — and ADR-0030 plus an existing project-wide test forbid both | medium | lock `observability_requirements.metrics`, the two comment lines; ADR-0030; `tests/broker/test_publish_confirm_failures.py` |
| **OQ-054** | `active_sessions` is a declared gauge and `deployment_target` forbids the only mechanism that could keep it true — expiry is enforced on read, so nothing can decrement, and there is no scheduled job | low | lock `observability_requirements.metrics`; lock `deployment_target`; ADR-0042 |

**Nothing else under `docs/` was written or edited.** No lock file, no ADR, no `interfaces.md` line, no
assumption file. Highest OQ id on disk when this phase was planned was **OQ-049** (Phase 8's range); the
range 050-054 was pre-allocated by the orchestrator and did not collide.

**`.planning/` files this phase's planner did NOT touch and its executors must not:**
`ORCHESTRATION.md`, `ORCHESTRATION-DECISIONS.md`, `WINDOWS.md`, `ROADMAP.md`, `REQUIREMENTS.md`,
`STATE.md`, and every other phase's directory. **`pyproject.toml` is also off-limits** — plan 09-06
reuses Phase 3's `load` marker and asserts `git diff --stat pyproject.toml` is empty.

---

## 2. ROADMAP success criterion → plan. Each owned by exactly one.

| # | Success criterion (ROADMAP, Phase 9) | Owning plan | Requirements | Proven by |
|---|---|---|---|---|
| 1 | A private prompt is not-found on every registry, evaluation and release endpoint and in search, identical in shape and status to an id that never existed; a viewer who lacks a permission instead gets a refusal naming it | **09-01** | AC-01, AC-02 | `tests/security/test_private_prompt_is_not_found_not_forbidden.py` (byte comparison over all three grants routes) · `tests/security/test_visible_subject_refusal_names_the_permission.py` · `tests/unit/test_refusal_shape_matrix.py` (4 + 36 cases) |
| 2 | A key used outside its scope produces a response byte-identical to one for a model name that does not exist, and a revoked key is refused on the very next request with no cached allow anywhere | **09-03** | AC-05, AC-06 | `tests/security/test_key_scope_refusal_cannot_enumerate.py` · `tests/security/test_nothing_caches_an_access_answer.py` · `tests/integration/test_revocation_is_immediate.py` · `tests/chaos/test_revocation_under_load.py` |
| 3 | A created key's plaintext appears in exactly one response and in no log, metric label, or history event, and cannot be reconstructed from the stored row | **09-04** | AC-07 (with AC-15) | `tests/security/test_key_secret_shown_once_only.py` (five enumerations) · `tests/security/test_database_dump_yields_no_working_credential.py` |
| 4 | With the database unreachable, every module refuses every request and none logs an allow — asserted per caller, not only here | **09-05** | AC-11 | `tests/chaos/test_every_caller_fails_closed.py` · `tests/security/test_no_except_manufactures_an_allow.py` |

**Four criteria, four owning plans, none claimed twice and none unclaimed.**

**Three of the four ship as HALVES, and every half is named here rather than implied** — this is the same
posture Phase 2 took for CL-01/CL-02 and Phase 8 for AC-9 and AC-10:

- **SC1's *"every registry, evaluation and release endpoint and in search"*** cannot run: none of those
  three modules exists at Phase 9. 09-01 ships the single decision function, asserts the byte-identity
  over the routes that exist, and routes the census to **Phase 15** (prompt-registry endpoints + search,
  which is PR-03 from the other side), **Phase 18** (EVAL-06) and **Phase 24**. `OQ-050`.
- **SC2's *"byte-identical"*** is a property of the **gateway's** response and the gateway is Phase 19.
  09-03 asserts the three seam-level properties that make it achievable — same value, same type with no
  exception, medians within a factor of two, plus an AST assertion on `may_resolve`'s body — and routes
  the byte comparison to **Phase 20** (GATE-10). `OQ-050`.
- **SC4's *"asserted per caller"*** covers eight modules; two are mounted. 09-05 asserts both plus all
  five seams directly, sweeps every route in `assembled_routes(app)`, and routes the per-caller form to
  **Phases 12, 15, 18, 20, 24**. The route sweep widens automatically as modules mount; the per-caller
  seam assertion does not. `OQ-050`.

**SC3 is the one that completes here**, over the surface that exists, and its walk also widens
automatically — the whole-response scan enumerates `assembled_routes(app)` rather than a list, so
mounting a module adds routes to it with no edit. The census completes at **Phase 23**.

## 2a. Requirement → plan. Each id in exactly one plan's `requirements:`.

| Requirement | Lock AC | Plan | Note |
|---|---|---|---|
| **AC-01** | access-control AC-1 | 09-01 | Mechanism + the routes that exist; census routed (OQ-050) |
| **AC-02** | access-control AC-2 | 09-01 | Asserted on `POST .../grants`; the revision form is Phase 13 |
| **AC-05** | access-control AC-5 | 09-03 | Seam side; the gateway byte comparison is Phase 20 |
| **AC-06** | access-control AC-6 | 09-03 | Complete — key, grant and role binding, serial and under load |
| **AC-07** | access-control AC-7 | 09-04 | Complete over the surface that exists; census at Phase 23 |
| **AC-11** | access-control AC-11 | 09-05 | Two of eight callers; the rest routed |
| **AC-15** | access-control AC-15 | 09-04 | API half complete; four rendering surfaces routed; the catalogue is unowned (OQ-052) |

**Seven requirements, seven appearances, no duplicates and no omissions.**

`requirements:` is `[]` on plans **09-02** and **09-06**, and that is a fact about `REQUIREMENTS.md`
rather than about the work. 09-02 ships A-144's login limiter and closes the third of PITFALLS gap 1's
owed access-control criteria — none of which has a requirement id, because the owed criteria lost their
ids when OQ-017 resolved. 09-06 ships the observability sweep, the load clause and the §9a milestone
audit, none of which any requirement points at. Phases 5, 6, 7 and 8 each recorded the same thing.

---

## 3. Plans, waves and dependencies

| Plan | Wave | depends_on | What it is |
|---|---|---|---|
| **09-01** | 1 | — | **Tracer.** `refusals.py` — one function, two shapes, proved byte-identical on the grants path; plus A-110's forced password change as a declared gate on every route but two |
| **09-02** | 2 | 09-01 | A-144's login limiter: before the row, before the hash, byte- and timing-indistinguishable, with PITFALLS gap 1(c)'s hasher-spy criterion |
| **09-03** | 3 | 09-01 | The key path: a scope refusal that carries nothing, revocation on the very next request, and the project-wide no-cache walk |
| **09-04** | 4 | 09-01, 09-03 | What a response may contain: the secret once (five enumerations + a real `pg_dump`), and no name for a tombstoned actor |
| **09-05** | 5 | 09-01, 09-02, 09-03 | Failing closed: two provocations, the five seams, every mounted route, and the ban on the helpful `except` |
| **09-06** | 6 | all | The milestone close: 17 metrics, 6 alerts, the two label decisions, `test_plan.load`, the §9a walk and the phase gate |

**No two plans in this phase have disjoint `files_modified`.** Every plan after the tracer touches
`src/prope/access_control/__init__.py`, at least one of the two candidate metric modules, and
`tests/access_control/__init__.py`; 09-01, 09-03, 09-04 and 09-05 additionally share
`src/prope/access_control/keys.py` or the routes package. **The orchestrator's disjointness check will
never fan out, which is correct.** Execution is serial regardless (ORCHESTRATION §7); the waves express
correctness ordering only.

Wave 2 and wave 3 both depend only on 09-01 and could in principle interleave — they do not, because
09-02 adds `src/prope/access_control/rate_limit.py` and 09-03's no-cache walk names that module as an
`ALLOWED_CACHES` exemption. Running 09-03 first would give it an exemption pointing at a file that does
not exist, and its own assertion that every exemption key exists on disk would fail.

---

## 4. UNCONFIRMED adoptions — for the phase UAT and `ORCHESTRATION-DECISIONS.md`

`mode: yolo`. Each was decided by the planner on the user's behalf, is written out in full in the owning
plan's `<objective>` with its rejected alternatives, and appears as a `<human-check>` in that plan's
`<verification>`. **None blocks execution. None touches a §2 non-negotiable** — checked row by row: human
approval before production, the Approved-only database constraint, the three separate permissions, and
private-by-default are untouched by every one, and D-131/D-132 *strengthen* the fourth.

| # | Decision | Plan | Reversibility | What the user is being asked |
|---|---|---|---|---|
| **U-09-1** | **D-131** — the refusal shape is decided by **one function**, `refusal_for(visible, allowed, action)`, and every route in every module calls it; no handler chooses a status code for a permission outcome | 09-01 | cheap | Phase 8 shipped the branch inline at three routes, which is right for one plan and wrong for fifteen routes across six modules. Confirm the centralisation, and that call-ledger deliberately imports **nothing** from access-control (ADR-0018) because it renders no permission outcome |
| **U-09-2** | **D-132** — when visibility is unknown the answer is **not-found**; `visible` is a required keyword with no default and there is no third `unknown` state | 09-01 | **one-way in practice** — a 403 already sent has disclosed existence | This is BR-01's direction. Confirm that the fail-closed direction is toward silence, and that a caller who cannot determine visibility passes `False` |
| **U-09-3** | **D-133** — `Session` gains `must_change_password`; `require_usable_session` refuses `403 password_change_required` on **every** route but two enumerated `/auth` routes | 09-01 | costly (`Session` is a parameter in six modules) | The status, the code and the exemption set are all invented — nothing in any authority declares them. `OQ-051` |
| **U-09-4** | **D-134** — `is_visible(...)` is exposed beside `may()` as the one place BR-01's rule is written, taking every input as a parameter | 09-01 | cheap | `may()` is visibility AND permission (Phase 7's D-104) so it cannot tell the two kinds of no apart. Confirm the second function rather than a richer `may()` return |
| **U-09-5** | **D-135** — the limiter is a bounded in-process sliding window on `time.monotonic` with an injected clock, `MAX_TRACKED_KEYS = 20_000` and age eviction | 09-02 | cheap | ADR-0043 fixes *where* the state lives and not its shape. Confirm sliding over fixed-window, and the bound |
| **U-09-6** | **D-136** — the per-source-address key is the **ASGI transport peer** by default; `X-Forwarded-For` is trusted only at `PROPE_TRUSTED_PROXY_HOPS > 0`, counted **from the right** | 09-02 | cheap | Written as a `checkpoint:decision` with both options. **Deployment consequence:** with Caddy in front and the setting unset, twenty failures from anywhere block the login screen for everyone. The alternative fails **silently and totally**; this one fails loudly and partially. Confirm, and set the value when the deploy exists |
| **U-09-7** | **D-137** — the limiter records **failures only**, `is_at_limit` records nothing, and a success clears the **email** bucket alone | 09-02 | cheap | Confirm that a rejected attempt must not extend its own window, and that one valid credential must not reset an attacker's address budget |
| **U-09-8** | **D-138** — `NEVER_CACHED` is a declared tuple in `keys.py` that the no-cache walk reads, and is asserted equal to the lock file's five `internal:` seams | 09-03 | cheap | Confirm the declared-list mechanism over a decorator or an import-linter contract |
| **U-09-9** | **D-139** — indistinguishability is asserted at the seam as *same value, same type/absence of exception, same timing envelope*, plus an AST assertion on `may_resolve`'s body | 09-03 | cheap | Confirm asserting now rather than waiting for Phase 20, and the factor-of-two timing tolerance |
| **U-09-10** | **D-140** — a tombstoned actor renders `display_name=null`, `email=null`, `display_key="actor.tombstoned"`, produced by the projection | 09-04 | **costly** — six modules' renderers will be written against it | Confirm the field shape over a rendered string, an omission, or a fallback to the id. `OQ-052` |
| **U-09-11** | **D-141** — `TOMBSTONED_ACTOR_KEY` lives in `src/prope/management_api.py`, one constant for six modules | 09-04 | cheap for the home, costly for the value once a catalogue exists | Confirm the value `actor.tombstoned` and the home. `OQ-052` |
| **U-09-12** | **D-142** — fail-closed is a **bare re-raise** after counting; an `except` returning `False` is refused as loudly as one returning `True`, and the walk reports them as **distinct finding classes** | 09-05 | cheap in code, one-way in incident history | Confirm that an unevaluable check surfaces as a **5xx**, not as a 403 or a friendly 503. The lock's own position is that there is no degraded mode by design |
| **U-09-13** | **D-143** — two provocations (a closed port, and `pg_terminate_backend` mid-statement); container pause and `REVOKE CONNECT` are **refused** as provocations | 09-05 | cheap | Confirm; both refusals are about not leaking state into a session-scoped container shared by the whole suite |
| **U-09-14** | **D-144** — `admin_count` **keeps** `workspace_id` under one asserted exemption; `key_scope_refusal_total` **drops** `key_id` and the signal moves to the log line | 09-06 | cheap to add a label back; costly to remove a scraped one | A split answer to two lines of the same lock-file block. `OQ-053`. Confirm, and whether the exemption mechanism is the general policy for future declared-but-unbounded labels |
| **U-09-15** | **D-145** — `test_plan.load` runs as a bounded default test **and** a `@pytest.mark.load` ten-minute test, reusing Phase 3's marker | 09-06 | cheap | Confirm the two-test shape and that no benchmarking dependency is added |

Two further one-phase postures that are consequences rather than decisions, and that a human should see:

- **`prope_access_control_active_sessions` ships drifting.** Set at sign-in and sign-out, never
  decremented on expiry, because expiry is enforced on read and the module has no scheduled job by
  decision. Asserted honestly, alerted on by nothing. `OQ-054` carries the four dispositions including
  *delete the metric*.
- **`AccessControlLoginBruteForce` is written on an unlabelled series.** The lock's phrasing is *"for one
  email"* and there is no email label and never will be (A-046, A-146). The rule ships with the gap in a
  YAML comment naming the limiter and `login_rate_limited_total` as the compensating controls; **no
  seventh alert is invented.**

---

## 5. PITFALLS gap 1 — the three owed access-control criteria, now all placed

`.planning/research/PITFALLS.md` gap 1 records three acceptance criteria for this module that BSP step 4
wrote as comments and the step-6 sweep never folded in. They were to be AC-13/14/15 and three *different*
criteria took those ids when OQ-017 resolved the same day, so **no requirement points at them.** With
this phase, all three have a test:

| Owed criterion | Owner | Where |
|---|---|---|
| (a) The `SECURITY DEFINER` set is exactly the sanctioned functions, each REVOKEd from PUBLIC with an empty `search_path` | **Phase 7** | `tests/security/test_security_definer_set_is_exactly_sanctioned.py` (07-06 Task 1), with `NOT_YET_BUILT` holding `evaluation.claim_next_run` until Phase 16 (`OQ-045`) |
| (b) ADR-0035's RLS coverage test extended to reach `prompt_grant` and `workspace`, failing if its second clause is removed | **Phase 7** | 07-06 Task 2, restated for ADR-0045 — `POLICIED_ON_ANOTHER_COLUMN` asserted rather than skipped |
| **(c) The login limiter performs no argon2id verification at threshold even with the correct password, asserted by timing or a hasher spy** | **Phase 9** | **plan 09-02 Task 3** — `tests/security/test_login_responses_are_indistinguishable.py`, asserted **both** ways: a hasher spy showing exactly 0 verifications with a positive control showing exactly 1, **and** a wall-clock median under half the wrong-password median |

Plan 09-06's §9a walk records all three by file and test name.

---

## 6. Routed forward — what M3 leaves, with a named owner

This is the planner's seed for plan 09-06 Task 4's walk. It is the union of Phase 7 §5, Phase 8 §5 and
what Phase 9's own planning found. **The executor's walk supersedes it and appends the real table.**

| Item | Why not in Phase 9 | Owner |
|---|---|---|
| **AC-1's registry / evaluation / release / search census** | Those modules do not exist | **15** (PR-03 + search), **18** (EVAL-06), **24** |
| **AC-2's revision-creation form** | `revision.create` is prompt-registry's | **13** |
| **AC-5's byte comparison of the gateway's two responses** | The gateway is Phase 19 | **20** (GATE-10) |
| **AC-7's whole-system endpoint census** | Two of eight modules are mounted; the walk widens automatically as they mount | **23** |
| **AC-9's second clause** — *the registry's list endpoint returns exactly that set* | Inherited from Phase 8 | **15** |
| **AC-10's cross-module route-table census** | Inherited from Phase 8; PITFALLS §5 | **23** |
| **AC-11's per-caller form** | Six callers do not exist | **12**, **15**, **18**, **20**, **24** |
| **AC-15's four other rendering surfaces** — a prompt's owner, an approval record, a release log, the history feed | No such surfaces exist. The **history feed has no route and will not** (A-123, ADR-0023, PH-07); the nearest real surface is the registry's Activity endpoint | **13**, **23**, **24**, and **15** for Activity |
| **`test_plan.load`'s gateway half** — *the gateway's own added latency p95 stays inside 50 ms with this module's share included* | Needs a gateway | **20** |
| **`test_plan.e2e`'s fourteen-step journey** | Spans prompt-registry and the gateway | **15** + **20** |
| **`test_plan.security` T-001** — the `prope_migrate` / `prope_report` credentials absent from the runtime `env_file`, the startup assertion that refuses to boot, and the compose-file test | **The highest-scoring finding in the whole BSP sweep, and no phase 1-9 has claimed it.** Its mitigation is one line and the artifact it constrains is a deploy file. Plan 09-06 Task 4 greps for it and records it | **Unowned — PITFALLS §4.** Escalated to the user in 09-06's `<human-check>` |
| **ADR-0044's `access.session` dump exclusion** | Surfaced by plan 09-04 Task 3: nothing in this repository configures the exclusion. The claim *"a restore signs everybody out"* rests on a `pg_dump` flag that exists in no artifact | **Unowned — PITFALLS §4** |
| **The i18n catalogue and ADR-0053 §3's CI check** | Seven keys now exist in code and no catalogue does | **Unowned — PITFALLS §5.** `OQ-052` |
| **The post-restore tombstone re-apply runbook** (ADR-0036's 30 days, A-151, A-133) | A runbook, not code | **Unowned — PITFALLS §4** |
| **Prope has no way to create its first workspace or its first user** | Inherited from Phase 8 §6. Phase 9 does not invent a bootstrap route either — it would be Prope's second unauthenticated path, added in the phase that just finished hardening the first | **Unowned.** The orchestrator should allocate an OQ if it wants it on the record; this phase's five ids are spent |
| **`prope_property_history_rows_total`'s setter** | Phase 6 routed it to 8; Phase 8 re-routed it to 23 | **23** (`OQ-037`) |
| **`last_used_at` on `access.api_key`** | Never written; INT-003 calls the side effect outside the contract and its only consumer is the gateway | **19** or later, or never — the lock calls the signal *weak* in its own words |
| **A-130's split doubling the login limiter** | Cannot happen without a deliberate change to ADR-0033's service list. ADR-0043 names the fix — the counter table it rejected | Triggered by the compose file, not by a metric |
| Ticking AC-01, AC-02, AC-05, AC-06, AC-07, AC-11, AC-15 in `.planning/REQUIREMENTS.md`; the ROADMAP checkbox, Plans line and Progress table; `STATE.md`; `WINDOWS.md`; `ORCHESTRATION-DECISIONS.md` | Out of this phase's boundary | **phase bookkeeping.** 09-06's SUMMARY states the exact diffs and makes none of them |

---

## 7. Discoveries an executor or a later phase needs, that are not on any plan's happy path

1. **Two plaintext credentials exist in Prope, not one.** Plan 08-04's `POST /workspaces/{id}/members`
   returns an **initial password** in its response (A-110, *handed over out of band*), and plan 08-03's
   `test_key_secret_shown_once_only.py` asserts *"exactly one property named `secret`"* over the OpenAPI
   schema. **That assertion is likely red before plan 09-04 runs**, and 09-04 Task 1 widens it to name
   both pairs rather than narrowing the walk. Predicted, not a surprise.
2. **`tests/broker/test_publish_confirm_failures.py` is likely red when this phase starts.** Phases 7 and
   8 ship `admin_count{workspace_id}` and `key_scope_refusal_total{key_id}` exactly as the lock declares
   them, and that file's project-wide walk forbids `workspace_id` on any metric. **That redness is plan
   09-06 Task 1's input**, and it is fixed by one asserted exemption plus one dropped label — never by
   narrowing the walk.
3. **`tests/architecture/test_route_table.py` gains a third census.** Plan 09-01 adds
   `require_usable_session` to every route but two, so that file now asserts three things about the
   assembled table (action, session, usable-session), each an exact equality in both directions. Its
   count arithmetic is unchanged — **this phase adds no route.**
4. **`may()` cannot distinguish *invisible* from *unpermitted*.** Phase 7's D-104 made it visibility AND
   permission, so a bare `False` has two causes and A-116 needs to tell them apart. That is the whole
   reason `is_visible` exists beside it. A future refactor that "simplifies" by deleting `is_visible`
   deletes BR-01's enforcement.
5. **The limiter is the second piece of module-level state in the project.** Without the autouse
   `reset_limiter()` fixture plan 09-02 adds to `tests/conftest.py`, the suite's result depends on
   collection order. `enqueue.reset_handoff` is the precedent and is already wired in `purge_queues`.
6. **A timing assertion and a timing-identity requirement look contradictory and are not.** Plan 09-02
   asserts a rate-limited login is *measurably faster* than a wrong password, while T-002 requires the
   three responses to be timing-identical. The reconciliation — an attacker already knows how many
   attempts they have made; what must be indistinguishable is *unknown email* versus *wrong password* —
   is written at the test, and without it a later reader will delete one of the two assertions.
7. **`pg_dump` must be run through the testcontainers container object, not a host shell.** The Windows
   host has no PostgreSQL client on PATH and `docker` is not on the default bash PATH; testcontainers
   reaches the daemon without help. A missing binary must be a **failure, not a skip** (plan 09-04
   Task 3).
8. **Three chaos provocations were considered and two were refused.** Container pause and
   `REVOKE CONNECT FROM prope_app` both leak into the session-scoped container in ways that redden later
   tests as unrelated failures. `pg_terminate_backend` and a closed-port engine do not. The one revoke
   this phase does use — `SELECT` on `history.history_event`, for the `/readyz` clause — is in a
   `try/finally` with `has_table_privilege` asserted afterwards, exactly as plan 06-05 required.
9. **Phase 7 and Phase 8 disagree about where `authenticate_session` lives** (`identity.py` vs
   `sessions.py`), and about whether access-control's metrics are in `src/prope/observability.py` or a
   module-local one. Every plan in this phase declares **both** candidates and instructs the executor to
   edit whichever exists and report which in the SUMMARY. This is the same hedge Phase 8 used and for
   the same reason.
10. **`refusal_for` must not be imported by `src/prope/call_ledger/`.** ADR-0018 is explicit that
    call-ledger has no dependency on access-control, and it renders no permission outcome. What
    call-ledger's five routes **do** change is their session dependency, and
    `require_usable_session` lives in `session_auth`, which is outside every module's package. Plan
    09-01's acceptance criteria assert the absence by grep.

---

## 8. The planner's self-check — because no critic ran

ORCHESTRATION §10a deleted the two plan critiques. These five are the checks `critic-exec` and
`critic-spec` would have made, run by the planner against its own output. **Every one is an agent
judgement from reading files; none is detector output.**

**1. Every ROADMAP success criterion is owned by exactly one plan.** ✅ §2. Four criteria, four owning
plans (09-01, 09-03, 09-04, 09-05), no overlap, no gap. Three ship as halves and every half names its
owning phase in the test module's own docstring, not only here.

**2. Every requirement id in AC-01, AC-02, AC-05, AC-06, AC-07, AC-11, AC-15 appears in exactly one
plan's `requirements:`.** ✅ §2a. 09-01 `[AC-01, AC-02]`, 09-03 `[AC-05, AC-06]`, 09-04 `[AC-07,
AC-15]`, 09-05 `[AC-11]`; 09-02 and 09-06 are `[]` with the reason stated. Verified by reading the six
frontmatters back: seven ids, seven appearances, no duplicates.

**3. Every file named in a task's `<action>` or `<files>` appears in that plan's `files_modified`.** ✅
Extracted mechanically from every `<files>` block and every `<action>` block in all six plans and diffed
against each frontmatter. Zero `<files>` residuals. Every `<action>` residual was checked individually
and is a **read-only** reference — a precedent to copy, an exemption target, an authority quoted, or a
helper imported — and each is now named in a `# READ-ONLY and deliberately NOT declared as modified`
comment in its plan's frontmatter, because *a path listed as modified that the plan forbids writing is a
declaration the orchestrator cannot trust*. The declared read-only set, per plan:

- **09-01** — `tests/integration/_asgi.py`, `tests/architecture/test_no_sql_interpolation.py`,
  `tests/security/test_tenant_isolation.py`, `OQ-050`, `OQ-051`.
- **09-02** — `tests/broker/test_publish_confirm_failures.py`,
  `tests/security/test_tombstoned_email_is_indistinguishable.py`, `tests/integration/_asgi.py`,
  `src/prope/access_control/passwords.py`, and three authorities.
- **09-03** — `src/prope/access_control/rate_limit.py`, `src/prope/property_history/registry.py`,
  `tests/chaos/__init__.py`, `tests/architecture/test_no_sql_interpolation.py`, `pyproject.toml`,
  `OQ-050`.
- **09-04** — none outstanding.
- **09-05** — `tests/contract/test_access_control_seams.py`, `src/prope/access_control/rate_limit.py`,
  `src/prope/access_control/refusals.py`, `tests/chaos/__init__.py`,
  `tests/architecture/test_no_sql_interpolation.py`, `OQ-050`.
- **09-06** — `pyproject.toml`, `tests/architecture/test_route_table.py`,
  `tests/security/test_key_secret_shown_once_only.py`, `tests/contract/test_access_control_seams.py`,
  `tests/architecture/test_tenant_coverage.py`, both existing rules files, `OQ-053`, `OQ-054`.

**One conditional declaration is deliberate**: 09-01 declares
`alembic/versions/000N_session_lookup_carries_the_password_flag.py`, which is created **only if**
`access.lookup_session` does not already return `must_change_password`. Both branches are stated in
Task 3 and the SUMMARY says which was taken. Same posture plan 08-06 used for
`000N_access_list_workspaces.py`.

**4. Every symbol, fixture, constant and file a plan tells an executor to extend actually exists.** ✅
Grepped against the tree as it stands today (Phase 3 executing, Phases 4-8 planned but not yet landed).

*Verified present on disk right now:* `session_auth.py`'s `SESSION_REQUIRED`, `SESSION_COOKIE`,
`ManagementRefusal`, `Session`, `require_session`, `ManagementAction`, `MANAGEMENT_ACTIONS`,
`declares_action`, `assembled_routes`, `_dependencies`, `declared_action`, `declares_session`;
`call_ledger/schemas.py`'s `ErrorCode` (with `NOT_FOUND` and `INTERNAL_ERROR`), `ApiError`,
`ErrorEnvelope`, `PageRequest`; `observability.py`'s `LOGGABLE_FIELDS` and the bucket-edge rule;
`call_ledger/enqueue.py`'s `HANDOFF_MAXSIZE` and `reset_handoff`, and `tests/conftest.py`'s import of the
latter in `purge_queues`; `tests/conftest.py`'s `postgres_container`, `migrate_engine`, `app_engine`,
`app_sessionmaker`, `report_engine`, `truncate_ledger`, `rabbitmq_container`, `amqp_url`,
`management_url`; `tests/integration/_asgi.py`'s `Response`, `Response.code` and `call`;
`tests/integration/test_health_and_readiness.py`'s `UNREACHABLE_DATABASE_URL` and
`unreachable_database_app`; `tests/architecture/test_alert_rules.py`'s `RULES_FILE`, `DECLARED_ALERTS`,
`METRIC_NAME`, `RENDERED_SUFFIXES`; `tests/broker/test_publish_confirm_failures.py`'s
`test_workspace_id_is_never_a_metric_label` and
`test_the_two_extended_label_sets_stayed_closed_at_their_declared_size`;
`tests/architecture/test_no_sql_interpolation.py`; `deploy/prometheus/rules/call_ledger.rules.yml`;
`docs/adr/0012`, `0018`, `0020`, `0021`, `0022`, `0030`, `0033`, `0036`, `0042`, `0043`, `0044`, `0053`,
`0054`; all eight `docs/modules/*.lock.yml`.

*Verified as created by a phase that executes before this one, and flagged in every plan's `<context>`
for re-grounding:* `tests/load/__init__.py` and the `load` pytest marker (**Phase 3**);
`tests/contract/` (**Phase 5**); `tests/chaos/` and `kill_point_child.py`
(**Phase 6**); `deploy/prometheus/rules/property_history.rules.yml` and the alert-rules glob
(**Phase 6**); the whole `access` schema, `may()`, `access.lookup_session`, `access.lookup_api_key`, the
`role_permission` seed, `passwords.py`'s `PASSWORD_HASHER` / `verify_password` / `ABSENT_USER_HASH`,
`identity.py`'s `sign_in` / `sign_out` / `authenticate_session`, all seventeen
`prope_access_control_*` metrics, and `tests/unit/test_argon2id_cost_is_asserted.py` (**Phase 7**);
`src/prope/management_api.py` and everything it holds, `src/prope/access_control/routes/`,
`keys.py`'s `authenticate_api_key` / `may_resolve` / `create_key` / `revoke_key` / `PresentedKey` /
`KeyIdentity`, `visibility.py`'s `visible_subject_filter`, `members.py`, `tombstone.py`,
`tests/access_control/__init__.py` and its seeding helpers, `install_session_authenticator`, and
`tests/contract/test_access_control_seams.py` (**Phase 8**).

*Verified as created by an earlier plan in this phase:* `refusals.py`, `require_usable_session`,
`PASSWORD_CHANGE_EXEMPT_ROUTES`, `ErrorCode.PASSWORD_CHANGE_REQUIRED`, `assert_byte_identical` (09-01);
`rate_limit.py`, `source_address`, `reset_limiter`, the hasher spy and `measure` (09-02); `NEVER_CACHED`
(09-03); `TOMBSTONED_ACTOR_KEY`, `display_key`, `credential_bearing_properties` (09-04).

**5. No plan hardcodes an Alembic `down_revision`, gates on `ruff format --check`, references a
`gsd-core` path, or puts the whole-suite `uv run pytest -q` in a per-plan verify block.** ✅ Grepped the
phase directory. `down_revision` appears twice, both in 09-01 and both saying to read
`uv run alembic heads` and never hardcode it; the migration file is named `000N_<slug>.py`.
`ruff format` appears six times, once per plan, every occurrence in a sentence saying it is **not** a
gate. `gsd-core` appears zero times and no `<execution_context>` block was written. `uv run pytest -q`
as a whole-suite invocation appears in exactly one `<automated>` block — plan **09-06**, the last plan,
Task 4 — and in 09-06's `<verification>`; every other plan's `<verify>` names its own targeted tests.

**One thing this self-check cannot do**, stated so it is not mistaken for coverage: it verifies the plans
are internally consistent and grounded in the tree **as it is today**. Phases 3 through 8 all land
between this file being written and plan 09-01 running, and Phases 7 and 8 were planned *concurrently*
with this phase by different agents. Every plan's `<context>` carries a re-grounding instruction naming
the exact symbols most likely to have moved. **The three live risks are §7 rows 1, 2 and 9.**

---

## 9. `D-NN` range consumed

**D-131 through D-145 — all fifteen, none spare.** Numbering is continuous across the project and never
restarts (phase 1: D-01..D-08 · phase 2: D-09..D-25 · phase 3: D-26..D-45 · phase 4: D-46..D-65 ·
phase 5: D-66..D-80 · phase 6: D-81..D-95 · phase 7: D-96..D-115 · phase 8: D-116..D-130).
**Phase 10 starts at D-146.**

Note for the orchestrator: Phase 8's `deferred-items.md` §3 row 16 records an adoption made **after** its
range was exhausted and asks for a number from the next available range. If the orchestrator assigns it
one, it must come from **D-146 onward** — D-131..D-145 are all consumed here.

| Plan | Range | Decisions |
|---|---|---|
| 09-01 | D-131 … D-134 | one function decides both refusal shapes · unknown visibility means not-found and there is no third state · `Session` carries `must_change_password` and the gate is a declaration · `is_visible` is exposed beside `may()` |
| 09-02 | D-135 … D-137 | a bounded in-process sliding window with an injected clock · the source address is the transport peer unless a hop count says otherwise · failures only, no self-extension, success clears the email bucket alone |
| 09-03 | D-138 … D-139 | `NEVER_CACHED` is a declared tuple the walk reads · indistinguishability is value + type + timing at the seam, with the byte comparison routed to Phase 20 |
| 09-04 | D-140 … D-141 | a tombstoned actor renders null plus a catalogue key from the projection · `TOMBSTONED_ACTOR_KEY` is one constant in `management_api.py` |
| 09-05 | D-142 … D-143 | fail-closed is a bare re-raise and a caught `False` is refused too · two provocations, and the two cheapest ones are refused for leaking into a shared container |
| 09-06 | D-144 … D-145 | the two unbounded labels get opposite answers, one under an asserted exemption · the load clause is a bounded default plus a marked ten-minute run |

---

## M3 milestone audit (ORCHESTRATION §9a)

**Reserved. Written by plan 09-06 Task 4's executor**, one row per clause of
`docs/modules/access-control.lock.yml`'s `acceptance_criteria` and all seven `test_plan` categories, each
`asserted` with a **file and a test name**, `routed` with a **named phase**, or `unowned` with a reason.
§6 above is the seed the walk starts from; it is not the walk.
