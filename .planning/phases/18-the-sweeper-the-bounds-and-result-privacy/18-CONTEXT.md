# Phase 18: The sweeper, the bounds, and result privacy - Context

**Gathered:** 2026-08-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 16 built a run that can start. Phase 17 built the evidence a run becomes. **Neither phase built
anything that survives a crash, bounds a workload, or refuses a stranger.** A run whose `worker` died
sits in `running` forever and the reviewer waits on nothing; a submit with five suites spends the
workspace's own bring-your-own key at whatever rate the process happens to allow; and a run row for a
private prompt is readable by anyone who can guess an id, carrying the model's output text with it.
Those three are this phase, and they are the module's last — **Phase 18 closes M6.**

The through-line is one sentence: **every guarantee in this phase is about work nobody is watching.**
The sweeper runs in a process with no request in flight. The bounds hold at a claim nobody is
polling. The privacy rule is asserted on a response nobody legitimate ever asks for. That is also why
each of the three has a failure mode that looks exactly like success — a sweep that enumerates zero
workspaces reaps nothing and exits green, a bound asserted end-to-end passes when either half holds,
and a leak is only visible to the person it leaks to.

**Delivers:**

- **`sweep_interrupted_runs` — a supervised resident in `src/prope/worker.py`** that, on startup and
  on a 60 s timer, moves every `running` run with no `case_result` progress for 5 minutes to
  `interrupted` in **one statement per workspace**, keeping its completed case results readable
  (EVAL-07, AC-7)
- **The cross-tenant half done the sanctioned way**: the sweep enumerates through the
  `WorkspaceEnumerator` seam `src/prope/worker.py:214` already declares and Phase 7 already bound to
  `access.list_workspaces()`, then runs its write under ordinary RLS per workspace. **No fifth
  `SECURITY DEFINER` function** — the set stays exactly four and the test that says so is untouched
- **`eval_run_interrupted` appended in the same transaction as the status change**, `actor_type =
  'system'`, `actor_id` null, `details` carrying `version_id` and `suite_version` — the fourth and
  last of this module's four history events (ADR-0023, A-014)
- **`prope_evaluation_run_interrupted_total` and `prope_evaluation_run_total{status=interrupted}`
  moved by the rows the statement actually returned**, after commit, never before
- **`prope_evaluation_run_queue_depth` set from a cross-tenant pass on the same enumeration** — set
  every pass including to zero, unlabelled, and published by a job that is *not* the claim loop it
  measures (EVAL-10's visible queue)
- **AC-10 in its restated form**: `max_concurrent_runs = 2` per workspace asserted **at the claim**
  as a database predicate, and `batch_concurrency = 8` per provider config asserted **at the provider
  seam** in `worker` — two independent assertions, never the deleted global ten (EVAL-10)
- **The owed AC-13**: two concurrent claim loops against one queued run leave exactly one winner, the
  other skipping to the next candidate — `FOR UPDATE SKIP LOCKED` and the admission predicate in
  **one** transaction asserted as the property, not as an implementation detail
- **The owed AC-12**: `evaluation.claim_next_run()` is the **only** route by which a row is read from
  an unset-tenant context, it returns identifiers and nothing else, and a direct `SELECT` on
  `evaluation.eval_run` as `prope_app` with no `app.workspace_id` returns **zero rows**
- **EVAL-06 proved over the whole surface, three ways**: a nonexistent id, an id in another
  workspace, and — the case row-level security does *not* cover — an id in the **same** workspace on a
  private prompt the actor holds no grant for. All three byte-identical, and no output text in any of
  them, asserted by a **sentinel scan over the whole response**, not a field allow-list
- **The owed AC-11 and its honest restatement**: a catastrophically backtracking regex aborts within
  its timeout and records `outcome = error`, and other work in the same `worker` container — call-
  ledger's drain, provider-access's batch dispatch — **completes, delayed by at most the per-
  evaluation timeout**. The second half is the deliverable; the wording change is `OQ-097`
- **The M6 close**: ORCHESTRATION §9a's clause-by-clause walk of `docs/modules/evaluation.lock.yml` —
  thirteen acceptance criteria including the three that exist only as a YAML comment, nine
  `failure_modes` rows, four STRIDE threats, and all seven `test_plan` categories — appended to this
  phase's `deferred-items.md`

**Fixed out of scope by ROADMAP (do not absorb):**

- The four tables, `workspace_id` on each, their RLS policies, the `status` CHECK that contains the
  literal `interrupted`, `evaluation.claim_next_run()` itself, the claim loop, the run executor, the
  assertion registry and the `regex`-with-timeout evaluator — **Phase 16** (EVAL-02, EVAL-03, EVAL-04,
  EVAL-09). This phase writes `'interrupted'` into a vocabulary another phase closed, and asserts a
  timeout another phase installed. D-334 and D-339 carry the verify-then-build contingencies
- The nine `/api/v1` routes, `get_review_summary()`, the cost delta and its withholding, the rollup,
  the cost warning, `price_usage`, the advisory ceiling check and `may()` at the route edge —
  **Phase 17** (EVAL-01, EVAL-05, EVAL-08). **This phase adds no route and no response model.** It
  drives Phase 17's surface adversarially and asserts what comes back
- Release-control enforcing `requires_acknowledgement`, the review screen, and the degraded-evidence
  path — **Phases 23 and 24**
- The cross-module route-table uniqueness assertion and AC-10's *"every route in every module
  declares an action"* — properties of the **assembled** table, which cannot run before Phase 23
  (PITFALLS §5)
- Retention or deletion of `case_result`. A-137 and A-145 make it Prope's second unbounded table and
  **the only one with no delete path at all**, deliberately; OQ-013 owns the policy. A sweeper that
  reaped rows as well as runs would be inventing that answer
- `MILESTONE-M6-MANUAL-TEST.md`. It lands in **this directory** under ORCHESTRATION §9b, written by
  the milestone handoff agent for a human to drive by hand. It is not a plan's deliverable and no
  plan should write it

**Requirements:** EVAL-06, EVAL-07, EVAL-10.

**The five owed criteria, and where each is absorbed.** `.planning/research/PITFALLS.md` gap 1 owes
this module AC-11, AC-12 and AC-13 — three criteria that exist only as a comment block at
`docs/modules/evaluation.lock.yml:651-686` and are therefore not requirements. Gap 2 owes two
restatements. **They are absorbed in the restated form and never in the lock file's literal text:**

| Owed | Literal text | The form this phase uses |
|---|---|---|
| AC-11 (new) | *"other work … completes unaffected"* | Completes, with added latency bounded by the per-evaluation timeout, nothing lost and nothing dead-lettered (D-335, `OQ-097`) |
| AC-12 (new) | — | Three assertions: the only unset-tenant read, identifiers only, zero rows on a direct `SELECT` (D-331) |
| AC-13 (new) | — | Two claim loops, one winner, the other skipping — the one-transaction property (D-327) |
| AC-10 (restate) | *"at most 10 upstream dispatches in flight"* | Two independent bounds at the two places they are enforced (D-326) |
| AC-9 (restate) | refused *"before any case is dispatched"* | Phase 17 took the ceiling half (its D-302), Phase 16 the modality half. **This phase's residue is the one assertion neither can make alone**: over a full lifecycle, a `status = 'refused'` row is only ever written by the claim-time check (D-329) |

</domain>

<decisions>
## Implementation Decisions

Phases 4-17 consume D-46 through D-319. This phase consumes **D-320 through D-339** and no id outside
that range. Open questions: **OQ-096 through OQ-100**, and no id outside it — ORCHESTRATION §5's
owed-and-unallocated rule applies to anything further, and borrowing another phase's range is
forbidden.

### The sweeper: a resident, an enumeration, and one statement

- **D-320: The sweeper is its own supervised resident, composed by hand in `src/prope/worker.py`, and
  it is not folded into the claim loop.** `src/prope/supervisor.py:83` fixes what a job is — *"a name,
  a zero-argument coroutine factory, and nothing else"* — and its docstring names evaluation's claim
  loop and release-control's sweep as the shapes it was written for. `interval_job` runs the body
  **first** and waits after, which gives A-054's *"on startup and on a 60 s timer"* for free rather
  than as two code paths.
  **Rejected: running the sweep inside the claim loop's tick.** It is the cheaper edit and it is
  precisely backwards. The sweeper exists because a process died; a sweeper hosted inside the loop
  that died dies with it, and the surviving replica's loop would be the only thing that could reap —
  which is a liveness guarantee that depends on there being a second replica, and A-138 says there is
  not. Under `supervise()` each job is wrapped by `run_with_restart` and Trap 1 is already answered:
  a crash in one does not stop the other. Coupling also welds a 1 s interval to a 5-minute rule, so
  the sweep would run three hundred times per window to do nothing.
  **Rejected: a scheduler library.** D-14 and A-012 settled it for the whole project; two interval
  jobs did not pay for APScheduler and a third does not either.
  — **Reversibility:** cheap — a job is a name and a factory in one dict.

- **D-321: The sweep enumerates workspaces through the existing `WorkspaceEnumerator` seam and issues
  `SET LOCAL app.workspace_id` per workspace. It adds no `SECURITY DEFINER` function.**
  `src/prope/worker.py:207-214` declares the type and says in as many words that it is *"the seam
  ADR-0051's `access.list_workspaces()` fills in Phase 7"*; plan 07-03 filled it and deleted the
  `ObservedWorkspaces` stand-in. So this phase **reuses a bound argument**, and the cross-tenant
  problem is solved before it is met.
  Stating why it has to be solved at all, because the failure is green: under ADR-0045 an
  `UPDATE evaluation.eval_run SET status = 'interrupted' WHERE status = 'running' …` issued by
  `prope_app` with no `app.workspace_id` in the session matches **zero rows**. The job runs, reports
  success, reaps nothing, and `prope_evaluation_run_interrupted_total` stays at zero — which is
  indistinguishable from a healthy system on every graph. That is the same shape
  `ObservedWorkspaces`' docstring was written about and the same shape ADR-0051 was written about.
  **Rejected by name: `evaluation.sweep_interrupted_runs()` as a fifth `SECURITY DEFINER` function.**
  It is the closer reading of `claim_next_run()`, and ADR-0051's shape rule refuses it: *"a function
  that returns tenant identifiers keeps every subsequent data read under RLS; a function that returns
  rows does not."* A definer function doing the reap would perform a **write** across every tenant
  with policy disabled, and a defect in its body would have no second line of defence. It would also
  move a number a test asserts is exactly four, and ADR-0042's control stops being a control the
  moment the count tracks feature work.
  **Rejected: extending `claim_next_run()` to reap as well as claim.** Same objection plus one more —
  its return is an identity tuple by design, and a function that also reports what it reaped either
  returns rows or lies by omission.
  **Rejected: `prope_report` credentials.** ADR-0051 already spent that argument: a `BYPASSRLS`
  connection string in `.env` and in a running process, for a job that can be written without one.
  Consequence, recorded rather than discovered: **N+1 transactions per pass, one per workspace,
  unbounded in workspace count** (A-140), and a workspace with no runs costs one statement that
  matches nothing.
  — **Reversibility:** one-way in the direction that matters — a shipped definer function is in the
  enumerated set, in a migration, and in a test.

- **D-322: "No progress" is `greatest(started_at, max(case_result.created_at)) < cut_off`, and the
  cut-off is read once per pass by the caller.** `started_at` is the floor so a run that claimed and
  then died **before its first case landed** is reaped — the exact crash a heartbeat-free design must
  still catch, and the one a `max(case_result.created_at)` alone would leave in `running` forever with
  a null aggregate.
  **Rejected: age since `started_at` alone.** A 20-case suite at concurrency 5 against a 30 s upstream
  is four waves and ~120 s, and `performance_requirements` allows 60 s per case with up to 2 retries —
  so an age rule at any threshold either reaps healthy long runs or never reaps anything. Progress, not
  age, is what A-054 says and what a liveness rule has to say.
  **Rejected: a `heartbeat_at` column on `eval_run`.** Two objections, either sufficient. It is a
  schema change to a **Phase 16 table** while Phase 16 is planned in parallel, which ORCHESTRATION §8
  makes a lost update rather than a design. And it is a second representation of liveness beside the
  case results, which can disagree with them in both directions — the same objection ADR-0049 used to
  refuse a broker message beside `eval_run.status`.
  **The clock is the caller's, passed in, exactly as `sweep_expired_bodies` states for itself**
  (`src/prope/worker.py:352-358`): *"a cut-off that advanced mid-pass would make 'what this pass
  deleted' depend on how long the pass took"*. One `clock()` read per pass, shared by the reap and the
  depth gauge.
  **The margin is thin and is stated rather than assumed.** A single-case suite whose one dispatch
  exhausts its budget — 60 s timeout × 3 attempts plus backoff — produces no `case_result` row for
  roughly three minutes of the five-minute window. The rule holds, with ~40% of the window to spare,
  and it is the tightest case in the module. Raised as **`OQ-098`**, because the five minutes and the
  retry budget come from two different blocks of the same lock file and neither cites the other.
  — **Reversibility:** cheap — the threshold is a constant.

- **D-323: The reap is ONE statement per workspace — `UPDATE … WHERE status = 'running' AND <no
  progress> … RETURNING` — and the returned set is what the history append and the counters are driven
  from.** No `SELECT` first. Two reasons, and the second is the load-bearing one.
  A select-then-update leaves a window in which a run **completes** between the two statements and is
  then overwritten as `interrupted` — a reviewer's finished evidence destroyed by a liveness job,
  which is the worst thing this job could possibly do. The `status = 'running'` predicate inside the
  update closes it at the engine.
  And it makes the job **idempotent by predicate rather than by lock**: a second pass, a restarted
  process, or a second `worker` replica reaping the same run gets **zero rows back**, appends no
  second event, and increments no counter. Exactly one `eval_run_interrupted` event per run falls out
  of the statement rather than out of coordination.
  **Rejected: `SELECT … FOR UPDATE SKIP LOCKED` then `UPDATE`.** It is the claim loop's shape and it is
  the wrong shape here: the claim must hand a specific row to a specific executor, so it needs the
  lock; the sweep needs only that a row is reaped once, which a predicate gives more cheaply and
  without a second statement's window.
  — **Reversibility:** cheap.

- **D-324: The `eval_run_interrupted` append is inside the reap's transaction, `actor_type = 'system'`
  with a null `actor_id`, and the statement returns `suite_version` because the event needs it.**
  ADR-0023 makes the append a call on the caller's session in the caller's transaction, and the whole
  argument for that is this case: a sweep that committed the status change and then failed to append
  would leave an interrupted run with no record of who or what interrupted it — a hole in the audit
  trail rather than a failed request, which is the failure class that never announces itself.
  The null actor is Phase 4's `CHECK (actor_id IS NOT NULL OR actor_type = 'system')` used exactly as
  written (D-54), and it is the first genuinely system-authored event in the module: Phase 17 appends
  `eval_run_started` in `app` with the reviewer as actor, Phase 16 appends `eval_run_completed` in
  `worker` as system, and this one has no human anywhere near it.
  `details` carries `version_id` and `suite_version`, which `docs/modules/evaluation.lock.yml:94-97`
  declares for all four events — so the reap statement joins `evaluation.eval_suite` and returns
  `suite_version` alongside the run's identity, rather than issuing a second read per reaped run.
  **This depends on a registry row Phase 4 deliberately seeded empty.** D-61 seeded all four `eval_*`
  actions with an empty `detail_keys` allow-list and named the consequence twelve phases early: an
  append carrying `version_id` against that seed is **refused with `unknown_detail_key`** and rolls the
  caller's transaction back. Phase 17's D-319 owns the conditional migration that fills it. **This
  phase reads the registry on disk first and only adds the `UPDATE` if the rows are still empty**, and
  says which branch it took in the SUMMARY — the 13-01 Task-2-step-0 shape.
  **Rejected: appending after the commit, or not at all.** The first is the audit hole above; the
  second contradicts `outputs`, which names `eval_run_interrupted` as one of this module's four events.
  — **Reversibility:** cheap to add a `detail_keys` entry, one-way to remove one — the allow-list is
  an allow-list and rows written against it are never updated.

- **D-325: Both declared counters move from the one site, by the returned row count, after the
  transaction commits.** `observability_requirements.metrics` declares
  `prope_evaluation_run_interrupted_total` **and** `prope_evaluation_run_total{status}` with
  `interrupted` among its three values. That is two metrics counting one event, and the redundancy is
  the lock file's rather than this phase's: `EvalRunsInterrupted` alerts on the dedicated counter while
  `run_total` is the lifecycle series. **Both move, from one place, by the same number**, and a test
  asserts that equality — because two counters that can disagree are worse than either alone.
  **Incrementing before the commit is refused**: a rolled-back transaction would leave a counter
  claiming a reap that did not happen, and `EvalRunsInterrupted` fires on `> 0 in 1 h`, so the phantom
  is a page.
  **This phase declares no eleventh metric.** The lock names ten; Phase 17 declared none; this phase
  adds increment sites and a gauge pass, not a series.
  — **Reversibility:** cheap.

### The bounds, asserted where each is actually enforced

- **D-326: AC-10 is split into two assertions that cannot substitute for each other, and the lock
  file's literal text is not used.** The deleted form asserts *"at most 10 upstream dispatches in
  flight"* against a number ADR-0049 removed. The restatement, which PITFALLS §2 and ROADMAP both
  demand:
  1. **`max_concurrent_runs = 2`, per workspace, at the claim.** Asserted by driving
     `evaluation.claim_next_run()` directly against a workspace holding two `running` rows and one
     `queued` row, and observing **no tuple** — while a *second* workspace's queued run is still
     claimable in the same pass. The second half is what proves the predicate is per workspace rather
     than global, and it is the half a single-tenant fixture cannot see.
  2. **`batch_concurrency = 8`, per provider config, at the provider seam.** Asserted in `worker`
     against the admission gate Phase 11 installed, by its in-flight high-water mark — the same shape
     ADR-0046's owed restatement of provider-access AC-6 uses.
  **Rejected: one end-to-end assertion counting dispatches during a five-suite submit.** It measures
  the *composition* of the two bounds, so it passes when either one holds and the other is broken —
  and the broken one is invisible until a workspace's key is rate-limited in production. It is also
  the assertion whose number ADR-0049 deleted, rebuilt with a different number.
  — **Reversibility:** cheap for the tests; one-way for the numbers, which live in a shipped default
  and a shipped gate.

- **D-327: AC-13's two-claim-loop race is asserted against real concurrent sessions, and the property
  asserted is that the claim and the admission decision are ONE transaction.** Two connections call
  `claim_next_run()` against a single queued run; exactly one returns a tuple, the other returns
  empty or the next candidate, and the run's `status` is `running` exactly once. The same test at the
  admission boundary — two loops, one free slot — asserts that both cannot see the last slot.
  This is the assertion `SKIP LOCKED` exists for, and writing it as a unit test over a mocked session
  is refused: the entire property lives in the engine's locking, so a test that does not open two real
  transactions is asserting Python.
  — **Reversibility:** cheap.

- **D-328: `prope_evaluation_run_queue_depth` is set by a pass that rides the sweeper's enumeration,
  is set on every pass including to zero, and carries no workspace label.**
  It is the same cross-tenant trap one metric over: `SELECT count(*) … WHERE status = 'queued'` with no
  tenant set returns zero rows, so the gauge would read `0` forever and `EvalQueueBacklog` would never
  fire — a backlog alert that is structurally incapable of firing. So it walks the same enumeration,
  once per pass, and reduces to a project-wide total.
  **Set every pass, never left unset**, for `observe_oldest_body_age`'s stated reason (D-43): *"an
  absent series and a healthy one are indistinguishable to a rule that compares against a threshold."*
  **Unlabelled** — a per-workspace label is exactly the cardinality ADR-0030's rule and this
  repository's registry walk refuse, and `suite_name` is already forbidden as a label for the same
  reason.
  **Rejected: a fifth resident job of its own.** `read_queue_depths` is its own job for a property that
  does **not** transfer — a broker-depth gauge published by the consumer whose backlog it measures goes
  silent exactly when the backlog matters. Here the gauge is published by the **sweeper** and measures
  the **claim loop**, so a wedged claim loop makes the gauge rise rather than freeze, which is the
  property that argument was protecting. One enumeration serving two readers is what
  `observe_oldest_body_age` already does inside the retention sweep.
  Consequence stated at the constant: `EvalQueueBacklog`'s *"> 10 for 15 min"* was written against a
  bound of ten dispatches, reinterpreted by ADR-0049 as *"submissions arriving faster than
  two-at-a-time drains"*, and is now read against a **project-wide** depth rather than a per-workspace
  one. Same shape as call-ledger's `OQ-022` clause 4.
  — **Reversibility:** cheap.

- **D-329: This phase installs no gate, invents no fourth number, and owns AC-9's residue.**
  The two surviving bounds already exist — `max_concurrent_runs` as a predicate inside Phase 16's
  `claim_next_run()`, `batch_concurrency` inside the gate Phase 11's `worker.py` composition installs —
  and A-138 records that **nothing bounds `worker` across workspaces**, accepted for the pilot.
  **Rejected: a process-local semaphore over concurrent runs in `worker`.** It would be a third bound
  that does not survive replication, which is the exact property ADR-0049 praised `max_concurrent_runs`
  for having; and two bounds on one quantity is ADR-0016's defect rebuilt.
  **Rejected: raising `max_concurrent_runs` so the load test finishes sooner.** The number exists for
  measurement — five interleaved runs each record the whole submit's duration and miss the 120 s target
  on all five — so raising it to speed a test would delete the reason it exists.
  AC-9's residue lands here because it is the only assertion neither Phase 16 nor Phase 17 can make
  alone: over a full lifecycle — advisory refusal at `POST`, admission at the claim, ceiling reached
  while queued — **the only run whose `status` is `refused` is one the claim-time check refused**, and
  `prope_evaluation_run_total{status=refused}` moved exactly once.
  — **Reversibility:** cheap.

### Result privacy: three cases, and the third is the one with the bug in it

- **D-330: EVAL-06 is proved three ways, and the third case is where a defect can actually live.**
  1. **A nonexistent id.** The baseline shape.
  2. **An id in another workspace.** Refused *structurally* — RLS returns zero rows on all four tables,
     so this and case 1 are the same code path and are byte-identical without anyone arranging it.
  3. **An id in the SAME workspace, on a private prompt the actor holds no grant for.** **Row-level
     security does not cover this case.** The tenant predicate passes; visibility is entirely the
     `may()` decision Phase 17 takes on the parent prompt, from `owner_id` and `access_level` read in
     the same statement as the child (its D-311). This is the case a planner skips because the first
     two are so easy, and it is the only one where a route can be wrong.
  All three must produce a byte-identical response — same status, same body, same headers — and the
  test asserts equality between the three serialized responses rather than asserting a status code
  three times. **Not-found, never forbidden**, per non-negotiable #4; a `403` naming `run.read` here
  would tell a stranger that a run id exists.
  **Rejected: asserting (1) against (2) only.** It proves RLS, which Phase 16 already proves, and says
  nothing about the permission decision that is the actual gate.
  — **Reversibility:** one-way in the sense every refusal shape is — a refusal that has leaked cannot
  be un-leaked.

- **D-331: The no-output-text half is a sentinel scan over the whole response, the whole log record and
  the whole metric label set — never a field allow-list.** A unique token is written into
  `case_result.output_content` and into `eval_case.input_messages`, every route on Phase 17's surface
  that could carry either is driven as the non-grantee **and** as the grantee, and the token must be
  absent from every byte of the refusal responses, absent from every captured log record on every path,
  and absent from every metric label — the last closing A-046's clause in the same test rather than in
  a second one that drifts.
  This is Phase 15's `search_text` move, one module over, and it is chosen for the same stated reason:
  a field allow-list passes the first time somebody adds a field. `case_result.output_content` is the
  second copy of provider content in Prope and the module's `security_requirements` put it in the same
  sensitivity class as a prompt body.
  **Rejected: asserting on parsed response fields.** A response model that gains an `output` field in
  Phase 23 escapes it, silently, forever.
  — **Reversibility:** cheap.

- **D-332: `visible_subject_filter` (INT-002) is NOT consumed by this module, and the mismatch Phase 17
  routed here is answered rather than deferred a third time.** The lock's `security_requirements` say
  results are visible to *"exactly the actors who may read the prompt — same filter, same
  repository-layer enforcement as the registry"*, which describes INT-002; `apis.consumes` names only
  `may()`. BSP step 5 found it, recorded it as owed to step 6, and step 6 did not fold it in; Phase 17's
  D-311 routed it here as owed-and-unallocated.
  **Decision: no INT-002 consumption.** Every list this module exposes is scoped to one prompt whose
  visibility `may()` has already decided, so the filter would answer a question nobody asks — and a
  second visibility mechanism beside `may()` is a second answer that can disagree. It would also import
  a **known-open** disagreement: `OQ-080` records that INT-002's `mode: all` and private-by-default
  already contradict each other in the registry, where a colleague with an ordinary `prompt.read` role
  sees another person's private prompt in a list page while the detail route answers `404`. Importing
  that into eval results is importing a defect with a ticket number.
  Raised as **`OQ-096`**, naming the two blocks of `evaluation.lock.yml` and the change_log line that
  says it was owed to step 6.
  — **Reversibility:** cheap — one call site if the answer changes.

- **D-333: No evaluation tripwire counter. The coverage is three named tests and one named gap, and the
  gap is written down rather than papered over.** The registry's
  `prope_registry_unfiltered_query_total` is a tripwire on the module with the widest read surface in
  Prope, and it is registry-owned. An evaluation counterpart would be an **eleventh metric** on a lock
  file that declares ten, which Phase 17 already refused once.
  What carries the guarantee instead: (i) ADR-0045's coverage walk, which already demands all four
  `evaluation` tables be tenant-scoped and fails otherwise; (ii) a per-table zero-rows-with-no-tenant
  assertion including `case_result.output_content` and `eval_case.input_messages`; (iii) D-331's
  sentinel sweep over the assembled surface.
  **The gap, named:** a route added to this module *after* this phase is caught only by Phase 23's
  assembled route-table assertion. That is a real hole and it is smaller than an eleventh metric whose
  increment site is a convention.
  — **Reversibility:** cheap to add later; the argument against it is a spec count, not a design.

### The regex blast radius, and the word "unaffected"

- **D-334: The timeout is Phase 16's mechanism; this phase asserts its blast radius — and carries a
  verify-then-build contingency for the mechanism itself.** The library choice (`regex`, not stdlib
  `re`), `timeout=1.0`, the length bound before the match, and compilation at suite-save time are
  named in `libraries_frameworks` and `security_requirements`, and they belong to the phase that built
  the evaluators. **Every plan in this phase re-grounds first**: read `src/prope/evaluation/` and Phase
  16's plan set; if the assertion path still imports stdlib `re` or has no timeout, this phase installs
  it and says so in the SUMMARY. The companion assertion the lock names — *"a test asserts stdlib `re`
  is not imported on the assertion path"* — lands here either way, because it is an absence and an
  absence belongs with the phase that proves absences.
  — **Reversibility:** cheap.

- **D-335: AC-11's "completes unaffected" is shipped as "completes, delayed by at most the per-
  evaluation timeout", measured, and the gap is raised rather than smoothed.** The lock's own impact
  paragraph is about stdlib `re` having **no timeout** and holding the GIL *in C without yielding* — so
  what the `regex` module buys is a **bound**, converting an unbounded stall into a 1.0 s one. Nothing
  in the lock, the ADRs or the library's contract says the match releases the GIL, and a criterion
  written as *"unaffected"* would be asserted by a test that either measures nothing or measures the
  scheduler's luck.
  So the assertion is a real one-process concurrency test: a pathological pattern against a
  length-bounded input, evaluated while a second job in the same event loop does observable work
  (call-ledger's drain committing and acking a window is the honest co-tenant, because it is the actual
  co-tenant), asserting (a) the case records `outcome = error` within the timeout budget, (b) the other
  job **completes**, with its added latency bounded by the timeout plus slack, and (c) nothing was
  lost, dead-lettered, requeued or timed out as a consequence.
  **Rejected: a `ProcessPoolExecutor` or a subprocess per assertion for true isolation.** It is the
  textbook answer and it is refused on ADR-0033's shape — 4 vCPU on one VM — and on A-012's
  *debuggable by one person*: a process pool, its lifecycle and its failure modes, for a job with a
  1.0 s ceiling that is already bounded.
  **Rejected: `asyncio.to_thread` around the match.** A thread does not help against a GIL that is not
  released; it moves the stall without shortening it, and it adds a thread pool to `worker` for the
  appearance of isolation.
  **Rejected: asserting the property with a stubbed clock or a mocked evaluator.** The claim is about
  one process's scheduling, so a test that does not run two things in one process is asserting nothing.
  Named consequence: the timeout is **per evaluation**, so a suite of twenty pathological assertions
  costs twenty seconds of event loop. Input-length bounding is the first line of defence for exactly
  that reason, and it is why it is *"a second line of defence"* in the lock's phrasing and the first in
  cost.
  Raised as **`OQ-097`**, because *"completes unaffected"* and *"completes, delayed by up to 1 s"* have
  an observable behavioural difference and the owed criterion says the former.
  — **Reversibility:** costly — the wording is what a later reviewer will hold the module to.

### The reap is advisory unless something fences the executor

- **D-336: The executor re-checks that its run is still `running` before each dispatch, and the check
  is a cross-phase edit that must be visible in the plan.** ADR-0049 releases the row lock **at the
  claim**, deliberately — *"a 120 s transaction would pin a connection, hold a snapshot against
  autovacuum, and turn every crash into a lock-timeout question"* — so nothing in the design stops a
  **slow-but-alive** executor from continuing to dispatch cases into a run the sweeper has already
  reaped. AC-7's *"no case is dispatched twice"* stays true (one executor, one dispatch per case) while
  the money keeps being spent on a run whose results nobody will read, which is the precise cost
  ADR-0049 rejected the broker for.
  The guard is one indexed read at the top of each case — the run's `status` — aborting the executor
  when it is no longer `running`. Cheap against a 60 s dispatch, and it makes the sweeper's decision
  authoritative rather than advisory.
  **Rejected: a fencing token / epoch column on `eval_run`.** Stronger and correct, and it is a schema
  change to a Phase 16 table under ORCHESTRATION §8's parallel-planning rule. If Phase 16 has already
  shipped something equivalent, this phase asserts it instead of adding a second mechanism.
  **Rejected: accepting the window and recording it.** Recording is what an unavoidable cost gets; this
  one costs one `SELECT` per case.
  Raised as **`OQ-099`**, because no authority states the check: A-054 gives the sweeper a 5-minute
  rule, ADR-0049 gives away the lock, and nothing joins the two.
  — **Reversibility:** cheap.

### Closing M6

- **D-337: This phase carries ORCHESTRATION §9a's clause-by-clause walk of the whole lock file, and the
  standard is evidence or a named owner — never a judgement.** Thirteen acceptance criteria (AC-1
  through AC-10 as rows, AC-11 through AC-13 as the comment block, read in their restated forms), nine
  `failure_modes` rows, four STRIDE threats T-008 through T-011, ten metrics, six alerts and all seven
  `test_plan` categories. Each row is `asserted` with a **file and a test function**, `routed` with a
  **named phase**, or `unowned` with a reason. Appended to this phase's `deferred-items.md` under
  `## M6 milestone audit (ORCHESTRATION §9a)`, which is orchestrator-owned under §7 — so the last plan
  surfaces it in its SUMMARY and does not write the shared file itself. Plan 12-06 is the shape.
  **The walk is expected to find things.** Two are known before it starts: `test_plan.load` still
  asserts *"in-flight dispatches never exceed the global bound of 10"* (`OQ-100`), and
  `test_plan.integration` names a pricing round-trip that Phase 17 built and this phase must locate
  rather than rebuild.
  — **Reversibility:** cheap.

- **D-338: `LOGGABLE_FIELDS` gains only what this phase's log lines actually carry, verified against
  disk first.** The lock's `log_fields` names `run_id`, `case_id`, `outcome`, `error_code`,
  `attempt_count`, `suite_name`, `suite_version` among others; Phases 16 and 17 will have added most.
  This phase reads `src/prope/observability.py`, adds what is missing for the sweep's own lines, and
  adds nothing speculative — *"an allow-list with a field outside it is an allow-list somebody has
  already stopped believing"* (`observability.py:64-70`). The sweep's own line carries the job name and
  a count; it does not carry a `prompt_id`, because a reaped run's identity belongs in the history event
  and the history event is the record.
  — **Reversibility:** cheap.

- **D-339: `worker.py`'s resident count moves again, and the three places that change together change
  together.** `src/prope/worker.py:102-106` fixes the rule: the job-name constants, the module
  docstring's paragraph, and
  `tests/integration/test_worker_jobs.py::test_the_worker_runs_exactly_the_three_jobs_this_file_composes`
  — *"whose name moves with its assertion"*. Phase 16 adds the claim loop and the executor; this phase
  adds the sweeper. **Re-ground: read the file, count what is there, rename the test in the same
  change.** The docstring's line predicting *"evaluation's claim loop (ADR-0049, Phase 16)"* is a
  prediction that this phase either confirms or corrects.
  — **Reversibility:** cheap.

### Claude's Discretion

Open, not decided. Resolve from the lock file, ADR-0049, ADR-0051 and Phase 16's plan set **on disk**,
and state the resolution in the plan:

- **Whether the depth-gauge pass is a second function riding the sweep's loop or a second enumeration
  inside the same job.** `expired_body_sweep` chose a second enumeration and argued it —
  *"cheaper than a changed signature or a side effect in a pure function"*. The same trade is available
  here and the answer may differ, because the sweep's statement already visits every workspace.
- **Where the interrupted-run sweep's SQL lives** — `src/prope/evaluation/sweeper.py` beside the
  module, or in the run repository Phase 16 built. The constraint is that
  `tests/architecture/test_no_sql_interpolation.py` walks `src/prope/` and requires every `text(...)`
  argument to be a plain string constant, so the statement is a module-level constant either way.
- **How a test makes a run look abandoned.** Backdating `case_result.created_at` through
  `migrate_engine`, injecting the cut-off, or actually killing a task. The chaos entry says *"kill the
  process mid-run"*; decide which of the three proves AC-7 and which prove the statement.
- **Whether the two claim loops in AC-13's test are two sessions or two processes.** Two sessions prove
  the transaction property; two processes prove the deployment one. The lock names neither.
- **The sweep interval and the no-progress threshold as constants versus settings.** `worker.py`'s
  precedent is a module constant with a written argument and *"a tunable judgement, not a repo
  decision, recorded so that changing it is a visible act"*.
- **Whether `EvalRunsInterrupted` and `EvalQueueBacklog` get rule rows in this phase's change**, and
  where the rules file is after Phase 15 wrote registry alerts into it.
- **How the M6 audit's `test_plan.load` row is dispositioned** once `OQ-100` is raised — asserted in the
  restated form, or routed with the OQ named.

</decisions>

<specs>
## The Concrete Surface

### No new tables. No new routes. At most one conditional migration.

Phase 16 owns every `evaluation` DDL object: the four tables, `workspace_id` on each, the RLS policies
and `WITH CHECK`s, the `(workspace_id, status)` index the claim loop reads every second, the `status`
vocabulary as **`text` plus a named CHECK** — never a native PostgreSQL `ENUM` — and
`evaluation.claim_next_run()`. This phase writes the literal `'interrupted'` into that vocabulary and
adds nothing to it.

The only migration this phase may create is D-324's, and it is **conditional on what is on disk**:

```sql
-- ONLY if history.history_action_registry still carries an empty detail_keys for these rows.
-- Phase 4's D-61 seeded them empty on purpose; Phase 17's D-319 owns filling them.
UPDATE history.history_action_registry
   SET detail_keys = ARRAY['version_id', 'suite_version']
 WHERE action = 'eval_run_interrupted'
   AND cardinality(detail_keys) = 0;
```

No new table, no `SECURITY DEFINER` function, no native enum, no foreign key leaving a schema — so
`tests/architecture/test_schema_invariants.py` and ADR-0045's coverage walk both adopt this phase for
free, and `tests/security/test_security_definer_set_is_exactly_sanctioned.py` is **read, not edited**.
Its `NOT_YET_BUILT = ("evaluation.claim_next_run",)` line is **Phase 16's** to delete (plan 07-06 says
so at the constant); if Phase 16 did not, this phase deletes it and reports it, because the phase that
closes M6 cannot leave the module's own definer function declared not-yet-built.

**Revision numbering:** ORCHESTRATION §4 — `uv run alembic heads`, use the head as `down_revision`, take
the next integer, never hardcode. Only one plan per wave may create a revision.

### The reap — one statement, per workspace, per pass

```sql
UPDATE evaluation.eval_run AS r
   SET status      = 'interrupted',
       finished_at = :cut_off_now
  FROM evaluation.eval_suite AS s
 WHERE s.id = r.suite_id
   AND r.status = 'running'
   AND greatest(
         r.started_at,
         coalesce((SELECT max(cr.created_at) FROM evaluation.case_result cr
                    WHERE cr.run_id = r.id), r.started_at)
       ) < :no_progress_before
RETURNING r.id, r.prompt_id, r.version_id, s.suite_version;
```

| Clause | Why it is there |
|---|---|
| `r.status = 'running'` inside the `UPDATE` | D-323 — a run that completed since the pass began is not clobbered; a second pass returns zero rows and appends no second event |
| `greatest(started_at, max(created_at))` | D-322 — `started_at` is the floor, so a run that died before its first case is reaped rather than left with a null aggregate |
| `FROM evaluation.eval_suite` | D-324 — `suite_version` is a `details` key on the event, and joining here avoids a second read per reaped run |
| `:cut_off_now`, `:no_progress_before` | Bound parameters computed **once per pass by the caller** from one `clock()` read, never `now()` inside the statement (`sweep_expired_bodies`' stated rule) |
| `RETURNING` | The counters and the history appends are driven from what the engine actually changed, not from what the job intended |
| no `workspace_id` predicate | The tenant policy is the enforcement; the statement runs inside `workspace_transaction(sessionmaker, workspace_id)` and `workspace_id` is **text compared to text with no cast** |

Under RLS this statement's `WITH CHECK` passes because the row's workspace equals the session's. Issued
with **no** `app.workspace_id` it matches zero rows — which is D-321's whole point and is asserted
directly, not assumed.

### Internal signatures

```python
# src/prope/evaluation/sweeper.py
async def sweep_interrupted_runs(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspaces: WorkspaceEnumerator,
    *,
    now: datetime,
    no_progress_after: timedelta = NO_PROGRESS_AFTER,
) -> int: ...                       # returns rows reaped; appends one event per row, same transaction

async def observe_run_queue_depth(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspaces: WorkspaceEnumerator,
) -> None: ...                      # sets the gauge every pass, including to 0 (D-328)

# src/prope/worker.py — composition only, by hand (D-13, D-320)
JOB_EVAL_INTERRUPTED_SWEEP = "eval_interrupted_sweep"
INTERRUPTED_SWEEP_INTERVAL_SECONDS = 60.0     # A-054's timer; interval_job runs the body first
NO_PROGRESS_AFTER = timedelta(minutes=5)      # A-054's rule; margin argued at D-322 and OQ-098
```

`WorkspaceEnumerator` is `src/prope/worker.py:214`'s existing type — `Callable[[], Awaitable[Sequence[str]]]`
— bound in the composition root to `access.list_workspaces()` by plan 07-03. **This phase passes an
argument; it does not create an enumerator.**

### The surface this phase drives (all of it Phase 17's)

| # | Route | What this phase asserts about it |
|---|---|---|
| 1 / 3 / 4 | the three suite reads | `eval_case.input_messages` never reaches a non-grantee; the sentinel is absent (D-331) |
| 7 | `GET /api/v1/eval-runs/{run_id}` | Three-way not-found equality (D-330); an `interrupted` run polls as `interrupted` with its partial counts, never as an error |
| 8 | `GET /api/v1/eval-runs/{run_id}/cases` | The completed case results of a reaped run **stay readable** to a grantee (AC-7) and are byte-identically not-found to a non-grantee (AC-6); no `output_content` in any refusal |
| 9 | `GET /api/v1/prompts/{id}/comparison` | An `interrupted` candidate does not render as a comparison with a fabricated delta |
| 6 | `POST /api/v1/prompts/{id}/eval-runs` | Runs beyond `max_concurrent_runs` are created `queued` and **not** refused (Phase 17's D-314); the queue is visible in `run_queue_depth` |

**No new error code.** The refusal is the existing envelope with a machine `code` the client translates
(ADR-0053); no literal display string crosses the wire, and the not-found body carries no `details`.

### Metrics — increment sites and one gauge, no eleventh metric

| Metric | Labels | This phase |
|---|---|---|
| `prope_evaluation_run_interrupted_total` | none | **Increments**, by the returned row count, after commit (D-325) |
| `prope_evaluation_run_total` | `status` ∈ `completed\|interrupted\|refused` | **Increments `interrupted`** from the same site, by the same number; asserts `refused` moved only at the claim (D-329) |
| `prope_evaluation_run_queue_depth` | none — deliberately unlabelled | **Sets**, every pass, project-wide (D-328) |
| `prope_evaluation_case_error_total` | `error_code` | Asserted for the regex timeout's `outcome = error` (D-335); declared by Phase 16 |
| the other six | — | Phase 16 or Phase 17 |

Alerts whose inputs this phase creates: `EvalRunsInterrupted` (`> 0 in 1 h`) and `EvalQueueBacklog`
(`> 10 for 15 min`, reinterpreted per D-328 as a project-wide depth). `suite_name` is a **log field,
never a metric label**.

### Test files, and what each proves

| File | Proves |
|---|---|
| `tests/chaos/test_interrupted_run_sweeper.py` | **EVAL-07 / AC-7** — a run whose worker died 6 minutes ago is marked `interrupted`, its completed case results stay readable, and no case is dispatched twice |
| `tests/integration/test_sweeper_is_cross_tenant.py` | D-321 — a run in a workspace **no request has touched since process start** is reaped; and the same pass with an enumerator returning `()` reaps **zero**, which is the failure that otherwise looks healthy |
| `tests/integration/test_sweeper_does_not_clobber_a_completed_run.py` | D-323 — a run that completes between passes stays `completed`; a second pass returns zero rows, appends no event, moves no counter |
| `tests/integration/test_interrupted_event_and_counters.py` | D-324, D-325 — one `eval_run_interrupted` per reaped run with `actor_type='system'`, a null `actor_id` and both `details` keys; a rolled-back sweep leaves neither the status nor the event; both counters move by the same number |
| `tests/integration/test_claim_admission_bound.py` | **EVAL-10 / AC-10 restated (1)** — `claim_next_run()` returns nothing for a workspace with 2 running, while another workspace's queued run is still claimable |
| `tests/integration/test_batch_concurrency_at_the_seam.py` | **AC-10 restated (2)** — `batch_concurrency = 8` per provider config holds in `worker`, measured at the gate |
| `tests/integration/test_two_claim_loops_one_winner.py` | **AC-13 (owed)** — two real transactions, one queued run, exactly one winner, the other skipping |
| `tests/security/test_claim_next_run_is_the_only_unset_tenant_read.py` | **AC-12 (owed)** — the function returns identifiers only; a direct `SELECT` on `eval_run` as `prope_app` with no `app.workspace_id` returns zero rows; the sanctioned definer set is exactly four |
| `tests/security/test_eval_results_private.py` | **EVAL-06 / AC-6** — the three-way byte-identical not-found (D-330), including the same-workspace no-grant case |
| `tests/security/test_eval_output_never_leaves.py` | D-331 — the sentinel is absent from every refusal body, every captured log record and every metric label |
| `tests/security/test_regex_blast_radius.py` | **AC-11 (owed, restated)** — `outcome = error` within the timeout, the co-tenant job completes with latency bounded by it, nothing lost or dead-lettered; and stdlib `re` is not imported on the assertion path |
| `tests/integration/test_worker_jobs.py` (edited) | D-339 — the worker runs exactly the jobs this file composes, the count and the test's own name moved together |

Load tests are behind `PROPE_RUN_LOAD=1` and are **skipped by default** (ORCHESTRATION §3). Any
criterion parked in `tests/load/` is not proven by the gate, and the plan must say which run proves it.

### Canonical references — read before planning

Authoritative and **read-only**. Per ORCHESTRATION §5 and `.planning/BSP-LINK.md`, nothing under
`docs/` may be edited, with the single exception of **creating** an `OQ-NNN` file. Five conflicts are
known: `OQ-096` through `OQ-100`.

- `docs/modules/evaluation.lock.yml` — `data.owns` (all four tables' amendments; `eval_run`'s `status`
  vocabulary and the claim predicate quoted in it), `deployment_target` (**the three `worker`
  residents, of which the sweeper is the third**), `security_requirements` (T-008 through T-011, the
  claim-loop paragraph, the regex paragraph, and the INT-002 sentence `apis.consumes` does not name),
  `failure_modes` rows **2, 7, 8** (the restart, the multi-suite submit, the backtracking regex),
  `observability_requirements`, `acceptance_criteria` AC-6, AC-7, AC-10, **and the `OWED TO THE STEP-6
  SWEEP` comment block at lines 651-686 — AC-11, AC-12, AC-13 and the two restatements live only there**
- `docs/adr/0049-…` — the claim SQL, the released lock, `max_concurrent_runs` as a database predicate,
  the third definer function, the sweeper's startup pass, and *"if `worker` is down entirely nothing
  sweeps and nothing needs to"*. **D-320, D-326, D-336's ground**
- `docs/adr/0051-…` — `access.list_workspaces()`, the identifiers-not-rows shape rule, N+1 per pass
  (A-140), and the three rejected alternatives this phase reuses by name. **D-321's ground**
- `docs/adr/0042-…` — the enumerated bypass set and why it stays enumerable
- `docs/adr/0045-…`, `docs/adr/0035-…` — deny-by-default, the zero-rows consequence the sweep is shaped
  against, `SET LOCAL app.workspace_id`
- `docs/adr/0046-…`, `docs/adr/0016-…` — `batch_concurrency`, the per-process caps, and why the
  processes are the priority classes
- `docs/adr/0023-…`, `docs/adr/0024-…` — the append in the caller's transaction; the twelve-column
  event, `actor_type`, and the registered payload
- `docs/adr/0053-…` — the machine `code` the client translates
- `.planning/research/PITFALLS.md` §1 and §2 — the evaluation rows in both, read in full
- `.planning/phases/16-*/` and `.planning/phases/17-*/` — **read both plan sets on disk before
  planning.** 16 is the authority on the tables, the claim, the executor and the evaluators; 17 on the
  routes, `may()` at the edge, the refusal shapes and D-319's registry migration
- `.planning/phases/04-*/deferred-items.md` §5 — the `detail_keys` handover naming this module's four
  actions, and the `unknown_detail_key` refusal D-324 exists to avoid
- `.planning/phases/07-*/07-03-PLAN.md` — the enumerator this phase reuses, and the prohibition against
  a fifth definer function stated at its own plan
- `.planning/phases/12-*/12-06-PLAN.md` — the §9a milestone-audit shape D-337 follows
- `src/prope/worker.py`, `src/prope/supervisor.py`, `src/prope/observability.py` — the three shipped
  files this phase edits or reads, in that order of weight

</specs>

<risks>
## What Is Most Likely To Go Wrong

- **The sweep is written, runs green, and reaps nothing — forever.** A `prope_app` statement with no
  `app.workspace_id` matches zero rows, so an enumeration bug, a stand-in enumerator, or a fixture that
  forgets `workspace_transaction` all produce a passing job that does nothing. This is the single most
  likely failure in the phase because *every* signal it produces is the signal a healthy system
  produces. **Catch:** `test_sweeper_is_cross_tenant.py` asserts **both halves** — a run in a workspace
  the process has never touched **is** reaped, and a pass with an empty enumerator reaps **zero** —
  which is the positive-control discipline `tests/security/test_append_only_privilege.py` exists to
  teach and the same shape `ObservedWorkspaces` was written about.

- **The sweeper overwrites a run that had just completed.** A select-then-update, or an `UPDATE` whose
  predicate omits `status = 'running'`, destroys finished evidence with a liveness job — the worst
  outcome available to this phase, and it is invisible because the row looks like a legitimately
  interrupted run. **Catch:** D-323's single statement makes the race unrepresentable, and
  `test_sweeper_does_not_clobber_a_completed_run.py` provokes the interleaving directly.

- **The first `eval_run_interrupted` append is refused with `unknown_detail_key` and rolls back the
  reap.** Phase 4 seeded the four `eval_*` rows with an empty allow-list *on purpose*, twelve phases
  early, and routed the fix to a later phase. If Phase 17's D-319 migration did not land — or landed
  for three actions and not the fourth — the sweep's transaction rolls back, the run stays `running`,
  and the failure points at property-history's validator rather than at a missing registry row.
  **Catch:** D-324's verify-then-add contingency executed **before** the append, plus an assertion that
  `eval_run_interrupted`'s `detail_keys` is non-empty.

- **A slow-but-alive executor keeps spending the workspace's key on a reaped run.** ADR-0049 releases
  the lock at the claim on purpose, so the sweeper's decision is advisory until something checks it.
  AC-7 stays green — no case is dispatched twice — while real money goes to a run nobody will read.
  **Catch:** D-336's per-case status re-check, raised as `OQ-099` because no authority states it, and a
  test that reaps a run mid-flight and asserts the executor stops dispatching.

- **AC-10 is asserted end-to-end and passes with one bound broken.** A single test that counts
  dispatches during a five-suite submit is satisfied when either `max_concurrent_runs` or
  `batch_concurrency` holds, and the broken one surfaces as provider 429s in production against a
  workspace's own key. **Catch:** D-326's two independent assertions at the two enforcement points, and
  the second workspace in the claim test that proves the predicate is per tenant.

- **EVAL-06 is proved with two cases and the third has the bug.** RLS makes cases 1 and 2 identical for
  free, which is exactly why they are the ones a planner writes. The same-workspace, no-grant case is
  the one where a route can return `403`, or return a run, or return output text. **Catch:** D-330's
  three-way byte equality asserted between the serialized responses, and D-331's sentinel scan run as
  the non-grantee on every route that could carry content.

- **"Unaffected" gets asserted by a test that measures nothing.** A blast-radius test that mocks the
  co-tenant, stubs the clock, or runs the two pieces of work sequentially will pass under stdlib `re`
  with no timeout at all — which is the one configuration the whole library choice exists to prevent.
  **Catch:** D-335's one-process test with the real drain as the co-tenant, a measured latency bound,
  and the companion assertion that stdlib `re` is not imported on the assertion path.

- **Phase 16 or Phase 17 drew a boundary somewhere else and this phase rebuilds or omits.** Phase 16
  has no CONTEXT on disk at the time this was written; Phase 17's exists and explicitly routes the
  regex blast radius, the two bounds, EVAL-06 and the INT-002 mismatch here. **Catch:** every plan opens
  with a re-ground block that reads `src/prope/evaluation/`, `src/prope/worker.py` and both plan sets
  before Task 1, and the first plan's Task 1 is an inventory whose output is a written statement of what
  exists. Follow disk, and say so in the SUMMARY.

- **The M6 audit is written as a judgement instead of as evidence.** §9a's value is that Phase 3 found
  three unproven clauses because the audit demanded a file and a test function. A walk that records
  "covered" for a criterion nobody can point a test at closes the milestone on a sentence. **Catch:**
  D-337's standard — `asserted` with a file **and** a function name, `routed` with a named phase, or
  `unowned` with a reason — and the two findings already known before it starts (`OQ-100`, and the
  pricing round-trip Phase 17 built).

</risks>

---

*Phase: 18-the-sweeper-the-bounds-and-result-privacy*
*Decisions consumed: D-320 through D-339. Open questions raised: OQ-096, OQ-097, OQ-098, OQ-099, OQ-100.*
*Context gathered: 2026-08-11*
