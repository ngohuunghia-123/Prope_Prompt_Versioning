# Phase 16: Schema, suite versioning, assertions, and the run lifecycle - Context

**Gathered:** 2026-08-11
**Status:** Ready for planning

<domain>
## Phase Boundary

The `evaluation` schema exists as a migration that carries its own guarantees, and the module's central
claim — *a reviewer decides on measured evidence* — becomes a thing the engine can be asked about: the
yardstick cannot be rewritten, the run that used it cannot be re-pointed at another one, and the row a
worker claims cannot be claimed twice.

This is the first module in Prope to run in `worker` **as its own scheduler**. Everything before it
either served a request or consumed a broker message; this one polls a table for its own work across
every tenant, which is why it owns the fourth and last sanctioned `SECURITY DEFINER` function.

**Delivers:**
- The `evaluation` schema, created and owned by `prope_migrate` with `USAGE` to `prope_app` and
  `prope_report` — the ADR-0027 shape `0001` established for `ledger` and `13-01` repeated for `registry`
- `evaluation.eval_suite`, `eval_case`, `eval_run`, `case_result` — four tables, all four tenant-scoped
  under ADR-0045 with a policy and a `WITH CHECK`, **no entry in `GLOBAL_TABLES`** (the lock is explicit:
  *"none of the four belongs in `GLOBAL_TABLES` and none could"*), every vocabulary `text` + a named
  `CHECK`, every intra-schema foreign key carrying `workspace_id` in both halves
- **Suite immutability as a privilege, not a convention**: `prope_app` holds `SELECT, INSERT` on
  `eval_suite` and `eval_case` and holds neither `UPDATE` nor `DELETE`, asserted against the live engine
  with a positive control and a grant/observe/revoke mutation check. Editing a suite is an `INSERT` of
  the next `suite_version`; a sibling suite is untouched because nothing writes it (EVAL-04)
- **The yardstick pin as a grant**: `eval_run.suite_id` appears in no `grant_column_update` list, so
  *"`suite_id` is written onto the run at start and never re-read from the prompt"* is enforced rather
  than reviewed, and an in-flight run keeps reporting against its own suite version (EVAL-04)
- **`case_result` with no `UPDATE` and no `DELETE` for `prope_app`** — A-137's *"the only table in Prope
  with no delete path at all"* carried by the grant matrix rather than by the absence of a `DELETE`
  statement somebody could add
- `evaluation.claim_next_run(p_max_concurrent_runs int)` — **the fourth sanctioned `SECURITY DEFINER`
  function**, emitted through `alembic/ddl.py`'s `security_definer_function`, returning five identifiers
  and no content, with `NOT_YET_BUILT` emptied in
  `tests/security/test_security_definer_set_is_exactly_sanctioned.py` **in the same change**
- **The claim loop as a supervised job** — a name plus a zero-argument coroutine factory (02-03's
  contract), composed by hand into `src/prope/worker.py` (D-13), polling at 1 s, with the claim, the
  admission predicate, the `status = 'running'` write **and** the `eval_run_started` history event in one
  transaction and the row lock released before the run executes
- The run lifecycle `queued → running → completed`, plus `refused` at claim time, as a state machine with
  a named transition function and a `CHECK` over the five statuses
- **Deterministic assertions per modality** — the `text` registry (A-005's nine types) and the
  `structured` registry (A-061's shape-only subset), each evaluator a pure function, regex under the
  `regex` module with `timeout=1.0` and never stdlib `re`, patterns compiled at suite-save time
- **The three withholding rules, applied once**: a dispatch failure is `outcome = 'error'` and never
  `fail` (A-057), any error withholds that suite's cost delta with a stated machine `code`, and a
  comparison across two suite versions is refused naming both (EVAL-02, EVAL-04)
- **The claim-time modality gate** — a run whose declared modality disagrees with the last observed shape
  of its target is written `status = 'refused'` before any dispatch, naming both, with
  `prope_evaluation_modality_mismatch_total` incremented and no usage row submitted (EVAL-09)
- Baseline pairing by identity, not by time: `(released_version_id, suite_id)`, with
  `prope_evaluation_baseline_reused_total{reused|recomputed}` and the reused run's `finished_at`
  surfaced, so a reused baseline is visible and never implied (EVAL-03)
- All ten declared metrics defined at import in `src/prope/evaluation/observability.py`, with closed
  label sets and bucket edges at the numbers this project asserts on (120 s, 1.0 s, 1.20)
- The five rig edits a fourth schema forces: `EXPECTED_ABSENT_SCHEMAS`, the truncate fixture, the
  schema-invariant walk, the migration-chain table map, and the `SECURITY DEFINER` set test

**Fixed out of scope by ROADMAP (do not absorb):**
- **The nine `/api/v1` routes of INT-025 and `get_review_summary()` (INT-017)** — **Phase 17** (EVAL-01,
  EVAL-05, EVAL-08). This phase builds the writers those routes call and proves them from its own tests,
  exactly as Phase 2 proved `enqueue` with no gateway in existence. `src/prope/app.py` is not touched
- **`price_usage` (INT-019), `get_run_totals` (INT-021), `check_spend_ceiling` (INT-020), `may` (INT-001)**
  — **Phase 17**. The claim-time admission gate ships here as an ordered list with **one** member and a
  named insertion point; the ceiling check is inserted there by Phase 17 (D-292)
- The rollup, `requires_acknowledgement`, the cost-warning flag and the +20% threshold — **Phase 17**
  (EVAL-05, EVAL-08). A-057's *per-suite* withholding is here; the rollup's *"withheld whenever any suite
  withheld its own"* is there
- **The sweeper**, the `interrupted` transition, the `eval_run_interrupted` event and the 5-minute
  no-progress rule — **Phase 18** (EVAL-07). This phase ships `interrupted` in the status `CHECK` and
  writes nothing into it
- **Result privacy** — the not-found shape for eval runs and case results of a private prompt — **Phase
  18** (EVAL-06). This phase's RLS policies are the structural half; the refusal *shape* is Phase 18's
- **The concurrency bounds as an asserted property** (owed AC-10's restatement: `max_concurrent_runs` at
  the claim, `batch_concurrency` at the provider seam, independently) and **the regex blast-radius half**
  of owed AC-11 (*"other work in the same `worker` container completes unaffected"*) — **Phase 18**. The
  bound is *implemented* here because it is inside the claim transaction; it is *asserted* there
- The six alerts and `deploy/prometheus/rules/evaluation.rules.yml` — **Phase 18**, in 15-03's shape.
  The metrics exist here so a rules file can be written against a live series
- The React SPA that renders the comparison (PITFALLS §3) and the deployment stack (§4) own no milestone

**Requirements:** EVAL-02, EVAL-03, EVAL-04, EVAL-09.

</domain>

<decisions>
## Implementation Decisions

Numbering continues from Phase 15's D-279. This phase consumes **D-280 through D-299** and no id outside
that range. Open questions: **OQ-086 through OQ-090**, and the range is **fully consumed** — a sixth
deviation is escalated in `deferred-items.md` §1 as owed-and-unallocated (ORCHESTRATION §5), never
borrowed from another phase.

### The fourth schema, and what one revision carries

- **D-280:** The schema, all four tables, their `CHECK`s, indexes, policies, grants, the
  `claim_next_run` function **and the four `history.history_action_registry` `detail_keys` updates** ship
  in **one revision**. This is the shape `0003`, `0004`, `07-01`, `10-01` and `13-01` all use, and the
  argument is unchanged: a tracer's value is proving the stack connects in a single applied migration, and
  a chain of five revisions has four intermediate states in which `eval_case.input_messages` and
  `case_result.output_content` — which hold the same content class as a prompt body (T-011) — exist and
  are readable across tenants.
  **Rejected: one revision per kind** (tables / RLS / grants / function), which RESEARCH Pattern 10
  recommends in general and `alembic/ddl.py`'s own docstring already declines.
  **Rejected: a second revision for the `SECURITY DEFINER` function**, on the grounds that a
  privilege-escalating object deserves its own reviewable diff. It is the opposite: the function and the
  policies it escapes must land together, or there is a deploy state in which the claim loop's target
  table has a policy and the escape does not exist, and the loop returns zero rows while looking healthy.
  **The `down_revision` is not written by the planner.** The executor runs `uv run alembic heads` and
  wires it then (ORCHESTRATION §4).
  — **Reversibility:** one-way. A landed revision is never edited; a change is a new revision.

- **D-281:** **The fourth sanctioned `SECURITY DEFINER` function lands here, and
  `tests/security/test_security_definer_set_is_exactly_sanctioned.py`'s `NOT_YET_BUILT` empties in the
  same change.** Plan 07-06 wrote that file with `SANCTIONED` holding four names and
  `NOT_YET_BUILT = ("evaluation.claim_next_run",)`, carrying the comment *"THIS LIST IS A PER-PHASE
  CONSTANT, NOT A PERMANENT FACT … Phase 16 deletes one line from `NOT_YET_BUILT`, in the change that
  creates the function, or inherits a red test it did not write."* Three things go with it and all three
  are edits to a Phase 7 file, which makes this a **cross-phase edit that must be visible in the plan**:
  the tuple loses its only entry; the function's `pg_get_function_result` pin is added to the per-name
  signature map; and the file's docstring stops describing a four-minus-one set and starts describing
  four. **`OQ-045` is thereby answered in fact** — `.claude/CLAUDE.md`'s *"a test asserts the set is
  exactly these four"* becomes literally true for the first time — and the plan says so rather than
  leaving the question open against a state that no longer holds.
  **Rejected: leaving `NOT_YET_BUILT` alone** and letting the equality fail. **Rejected: a fifth function
  for the queue-depth gauge** — see D-299.
  — **Reversibility:** one-way on the count. A fifth function is never the answer; the set is closed.

- **D-282:** **Five rig files are told about a schema by name and all five change here**, and the plan
  lists them rather than discovering the fourth one at gate time:
  `tests/architecture/test_tenant_coverage.py` (`EXPECTED_ABSENT_SCHEMAS` drops `"evaluation"` and the
  companion sorted-tuple assertion gains it — **two edits, not one**, which is the edit a planner misses,
  per D-47); `tests/conftest.py`'s truncate fixture (whatever plan 04-01 renamed it to on disk) must
  reach `evaluation`; `tests/architecture/test_schema_invariants.py`'s `GENERIC_SCHEMAS` tuple gains
  `"evaluation"`; `tests/integration/test_migration_chain.py`'s `SCHEMA_TABLES` map gains its four table
  names; and D-281's set test. **No `GLOBAL_TABLES` entry is added** — all four tables are workspace
  property and the lock says so in as many words.
  **Nothing in `evaluation` is excluded from the truncate fixture.** Unlike `history_action_registry`
  (D-48), this module seeds no rows in its migration except the four registry `detail_keys` **updates**,
  which are `history`'s rows and are excluded by that phase's own rule.
  — **Reversibility:** cheap.

### Suite versioning is a privilege, not a discipline

- **D-283:** **A new suite version is a new ROW, and `prope_app` cannot write any other kind.**
  `grant_table("evaluation", "eval_suite", app_privileges=["SELECT", "INSERT"])`, same for `eval_case`.
  No `UPDATE`, no `DELETE`, no `grant_column_update` list. `PUT /api/v1/eval-suites/{id}` (Phase 17's
  route) calls a writer that inserts `suite_version + 1` with a fresh `evs_` id and re-inserts its cases;
  the earlier version is not touched because the role that would touch it cannot.
  This is ADR-0025's argument transplanted: *"a log the application can rewrite is a Sheet with better
  indexing"* — and a **yardstick** the application can rewrite is worse, because a comparison measured
  with it still renders, authoritatively, with the wrong number.
  **Rejected: `is_current boolean` with an `UPDATE` that flips the old row.** It needs `UPDATE` on the
  table, which reopens every other column; it makes *"a run's results are only readable if the yardstick
  they were measured with still exists"* (A-004) an application promise; and the flip and the insert are
  two statements that can interleave.
  **Rejected: application-level immutability** — a repository that never emits `UPDATE`. That is the
  word ADR-0025 exists to remove, and the realistic writer here is a repair script, not a route.
  **The consequence, stated rather than discovered:** an author who mistypes a case name creates a
  version rather than fixing one, and every version is permanent. That is A-004's intent and it is what
  the review screen's *"suite version 5"* label is for.
  — **Reversibility:** one-way in D-07's sense — a later widening is blocked by whatever has come to
  depend on the absence, and here the thing depending on it is the comparison's meaning.

- **D-284:** **`eval_run.suite_id` holds no `UPDATE` privilege**, so the failure-mode row's mitigation —
  *"`suite_id` is written onto the run at start and never re-read from the prompt"* — is a grant.
  `prope_app`'s `UPDATE` on `eval_run` is a **column list** through `grant_column_update`, and it is
  exactly: `status`, `finished_at`, `pass_count`, `fail_count`, `error_count`, `input_tokens`,
  `output_tokens`, `cost_amount`, `cost_currency`, `priced_at`. Six columns are deliberately absent —
  `workspace_id`, `prompt_id`, `version_id`, `suite_id`, `role`, `started_by` — and one more,
  **`started_at`, is absent because the claim function writes it as the owner** and nothing else should.
  PostgreSQL checks column-level `UPDATE` against the statement's `SET` list, so an executor that tried
  to re-point a run at the current suite version would meet the engine.
  **Rejected: table-wide `UPDATE`** with the discipline in the repository. Same argument as D-283, one
  table over, and this is the column EVAL-04's third clause rests on.
  — **Reversibility:** costly — Phase 17's and Phase 18's writers are written against the list.

- **D-285:** **`case_count` is written once, in the transaction that creates the version, and a deferred
  constraint trigger asserts it at commit.** The column is declared by the lock and cannot be dropped; it
  is a denormalised count on a table whose rows are immutable, so the only way it can lie is a later
  `INSERT` into `eval_case` — which `prope_app` **can** do, because D-283 grants `INSERT`. The trigger is
  `AFTER INSERT ON evaluation.eval_case DEFERRABLE INITIALLY DEFERRED FOR EACH ROW`, comparing
  `eval_suite.case_count` against `count(*)`, and it is **`SECURITY INVOKER`, explicitly**, in plan
  07-04's shape and for 07-04's reason: a `SECURITY DEFINER` trigger function is a fifth
  privilege-escalating object and the answer is never a fifth.
  **Rejected: dropping the column and computing the count on read.** It is a declared field; removing it
  is the silent narrowing ORCHESTRATION §5 refuses, and `GET /eval-suites` reads it per row.
  **Rejected: a maintenance trigger that recomputes `case_count`.** That makes the count always true and
  therefore never falsifiable, and the failure it guards — *"18 of 20 passed"* with nothing behind it,
  A-137's own sentence — is exactly the kind that must be loud.
  **No `CHECK (case_count BETWEEN 10 AND 20)`.** `scope.in_scope` says *"each 10-20 cases"* and **A-059
  says a prompt may have an empty eval suite**; a range constraint would make A-059 unrepresentable. The
  guidance is an authoring convention, and `CHECK (case_count >= 0)` is the whole of what is true.
  — **Reversibility:** cheap — a trigger body is a new revision.

- **D-286:** **`suite_version` allocation races on `uq_eval_suite_prompt_name_version UNIQUE (prompt_id,
  name, suite_version)` and the writer retries once**, which is A-048's shape for `revision_number` one
  module over (plan 13-02) and is adopted rather than re-derived. The unique key is the lock's literal
  `unique(prompt_id, name, suite_version)` and **does not gain `workspace_id`**: `prompt_id` is a
  globally unique ULID, so widening the key would *weaken* it by permitting the same triple in two
  workspaces. The foreign-key target that D-287's composite keys need is a **separate**
  `uq_eval_suite_workspace_id UNIQUE (workspace_id, id)` — trivially unique, and that is the point
  (13-01's `uq_prompt_property_workspace_id`, same comment).
  — **Reversibility:** cheap.

### The claim loop

- **D-287:** **`evaluation.claim_next_run(p_max_concurrent_runs int)` is one `LANGUAGE sql VOLATILE`
  data-modifying CTE**, emitted through `alembic/ddl.py`'s `security_definer_function` (plan 07-01's
  helper) so that the empty `search_path`, the `REVOKE … FROM PUBLIC` and the `GRANT EXECUTE … TO
  prope_app` cannot be assembled a line short. It returns
  `TABLE (run_id text, workspace_id text, prompt_id text, version_id text, suite_id text)` — ADR-0049's
  five identifiers, no prompt text, no case input, no output — and ADR-0051's rule is the reason:
  *"a function that returns tenant identifiers keeps every subsequent data read under RLS; a function
  that returns rows does not."*
  Three sub-decisions, each with its rejection:
  *`LANGUAGE sql`, not `plpgsql`.* A SQL body cannot contain control flow, so it cannot contain a
  decision — ADR-0042's property, and the one that keeps these four objects lookups rather than
  authorities. The claim's admission predicate is a `WHERE` clause, not an `if`.
  *`p_max_concurrent_runs` is a parameter, not a literal.* A-063 calls the bound *configurable*; baking
  `2` into the function body makes a configuration change a migration. The value lives in
  `src/prope/evaluation/domain.py` beside the other tunables and is passed at every call.
  *`ORDER BY r.id`, not `ORDER BY r.created_at`.* **`eval_run` has no `created_at` column** — the lock's
  field list runs `… suite_id, role, status, started_at, finished_at, …` — while ADR-0049's SQL block
  orders by one. `id` is an `evr_`-prefixed ULID (ADR-0003, A-045) and ULIDs sort lexicographically by
  creation time, so FIFO is available with no column and no deviation from the declared field list.
  **Rejected: adding `created_at`**, which is the undeclared-column deviation 13-01 paid for with OQ-070
  and is not worth paying twice for an ordering the id already carries. The residual difference — two
  runs created in the same millisecond may order by ULID randomness rather than by microsecond timestamp
  — is recorded at the constant and escalated in `deferred-items.md` rather than given an OQ id, because
  the observable end state (FIFO within a workspace's submit) is the same.
  — **Reversibility:** one-way. Four modules' worth of tests pin the return shape, and the set of
  `SECURITY DEFINER` objects is asserted by equality.

- **D-288:** **The claim transaction is the CALLER's, and the `eval_run_started` history event rides
  inside it.** A `LANGUAGE sql` function does not manage transactions, so ADR-0049's
  `BEGIN; SELECT …; UPDATE …; COMMIT;` block describes the *caller's* transaction with the whole claim
  collapsed into one statement. That buys something ADR-0049 does not spell out and A-014 requires: the
  loop opens a session, calls `claim_next_run()` **with no tenant set** (the function is owner-run and
  exempt), then issues `set_config('app.workspace_id', <claimed workspace>, true)` in the same
  transaction, then calls `property_history.append(session, eval_run_started)`, then commits. The status
  change and its event are atomic, the tenant policy covers the append's `WITH CHECK`, and **the row lock
  is still released before the run executes**, which is ADR-0049's other requirement.
  **Rejected: appending after the claim commits.** That is a state change without its event — the exact
  failure PH-01 and ADR-0023 exist to make impossible, arriving through the one path where nobody would
  look for it.
  **Rejected: holding the claim transaction open for the run.** A 120 s transaction pins a connection,
  holds a snapshot against autovacuum and turns every crash into a lock-timeout question — ADR-0049's
  own words.
  **Consequence:** `set_config` is issued *after* a query has already run in the transaction. That is
  legal and transaction-local, and it is the only place in Prope where the tenant is set mid-transaction
  rather than by `workspace_transaction`. It must be written as a named helper in this module with the
  reason at it, not as a bare `execute` at the call site, or the source gate
  (`tests/architecture/test_no_sql_interpolation.py`) and the next reader both lose the thread.
  — **Reversibility:** costly — Phase 17 and Phase 18 write inside this transaction shape.

- **D-289:** **The admission predicate is snapshot-based; it bounds one claim loop and does not bound
  two, and that is stated here rather than found at 2 a.m.** `SKIP LOCKED` guarantees two loops never
  claim the *same* row — which is owed AC-13's assertion and is true. It does **not** serialise two loops
  claiming *different* rows of the same workspace: under `READ COMMITTED` each correlated
  `count(*) WHERE status = 'running'` runs against a snapshot in which the other's uncommitted `UPDATE`
  is invisible, so both can see the last free slot and `max_concurrent_runs = 2` becomes 3.
  ADR-0049's Consequences say the opposite — *"two claim loops each counting running rows would still be
  correct … this bound survives replication and ADR-0046's does not"* — and that sentence is false as
  written. **Raised as `OQ-090`**, never patched.
  **Adopted for this phase:** exactly one claim loop per process, awaited serially (one claim per tick,
  the run started before the next tick claims), and **one `worker` replica**, which is ADR-0033's runtime
  and A-138's recorded scope. Under that composition the bound is exact.
  **Rejected: a per-workspace advisory lock** (`pg_advisory_xact_lock(hashtext(workspace_id))`) inside
  the function. It would close the race and it costs a second escape mechanism inside a
  `SECURITY DEFINER` body, on a hash collision domain, to fix a case the deployment does not have.
  **Rejected: `SERIALIZABLE` for the claim transaction.** It converts the race into a serialisation
  failure the loop must retry, on the one transaction that must be short.
  — **Reversibility:** cheap on the mitigation, one-way on the ADR wording, which is why it is an OQ.

- **D-290:** **Two indexes on `eval_run`, not the lock's one, and the second is argued rather than
  assumed.** The lock declares `(workspace_id, status)` and says the claim loop is the module's
  highest-frequency reader. It is — but the claim's *outer* scan is
  `WHERE status = 'queued' ORDER BY id` **across every workspace**, which `(workspace_id, status)` cannot
  serve at all. So: `ix_eval_run_queued_id` as a **partial** index
  `(id) WHERE status = 'queued'` — which is tiny, because the queue is short by construction and a
  claimed row leaves the index — and `ix_eval_run_workspace_status (workspace_id, status)` for the
  admission count and the queue-depth gauge. A third, `ix_eval_run_baseline_pairing (workspace_id,
  suite_id, version_id, status, finished_at DESC)`, backs EVAL-03's pairing rule and ships with the table
  for D-55's reason: adding an index later means adding it to a table that already holds rows on the one
  table this module polls every second, forever.
  **Rejected: taking the lock's single index literally.** A sequential scan once per second over a table
  that only grows is the kind of defect that is invisible for a pilot and fatal after it.
  — **Reversibility:** cheap — an index is a new revision either way.

- **D-291:** **The claim loop is a supervised job and nothing more exotic** — `JOB_EVAL_CLAIM_LOOP`, a
  zero-argument coroutine factory, composed by hand in `src/prope/worker.py` alongside the three
  call-ledger residents. That file's own docstring already names this arrival: *"evaluation's claim loop
  (ADR-0049, Phase 16) … joins by somebody editing this file. That is D-13's explicit central
  composition."* The 1 s cadence is `supervisor.interval_job(body, 1.0, stopping)`, whose body runs
  **first** and waits after, so a worker starting after an outage drains immediately.
  **Rejected: a broker message per run** — ADR-0049 rejected it and the reason is a bill, not a
  preference: an unacked message redelivered on a crash re-dispatches every case against the workspace's
  own key.
  **Rejected: a scheduler library** — A-012's *debuggable by one person*, and D-14 already paid the
  ninety lines.
  **Rejected: composing it in a new `prope.evaluation.worker` entrypoint.** ADR-0033 fixes the runtime at
  7 services and 2 images; a second worker process is a service.
  **Consequence:** `tests/integration/test_worker_jobs.py`'s
  `test_the_worker_runs_exactly_the_three_jobs_this_file_composes` is a Phase-2 test whose **name moves
  with its assertion** — it becomes four. That is a cross-phase edit and belongs in the plan.
  — **Reversibility:** cheap.

### Where Phase 16 stops and Phase 17 begins

- **D-292:** **The line is drawn at the HTTP edge and the pull, not at the consumed seams.** A reader of
  the two ROADMAP goals would put every consumed module in Phase 17 — its goal names four of them — and
  that reading makes three of this phase's four success criteria unprovable, which ORCHESTRATION §9
  forbids. SC1 asserts about the outcome of a *dispatch*; SC2 asserts that a baseline is **not
  re-dispatched**; SC4 asserts that **no upstream call is billed**. None is observable without a path
  that dispatches. So the split is by capability:
  - **Phase 16 wires INT-011** (`get_revision`, and D-293's `get_released_revision`) **and INT-015**
    (`dispatch(..., priority=batch, stream=False)`), because a run cannot execute without the revision's
    binding or the upstream call, and composes the executor into `worker`.
  - **Phase 16 does not wire INT-019 / INT-020 / INT-021 / INT-001.** The usage rows a run produces are
    held on `case_result` and priced by Phase 17; `eval_run.priced_at` stays NULL and
    `EvalPricingStalled` is Phase 18's alert. The claim-time admission gate is written as an **ordered
    tuple of check callables with exactly one member** (the modality gate) and a `#:` block naming
    `check_spend_ceiling` as the second member Phase 17 inserts — so that insertion is one line rather
    than a re-shaped function.
  - **Phase 17 owns** the nine routes, `get_review_summary`, the rollup, the money seams and the `may()`
    call at every edge.
  **The honest cost, stated plainly:** Phase 16 ships a run that completes with pass/fail counts and
  token counts and a **NULL cost**, and a cost delta that is `None` for the reason *"not priced yet"*
  rather than for A-057's reason. The withholding *machinery* and its machine codes are here and the
  money that flows into it is Phase 17's; a test that asserts a withheld delta in this phase must assert
  the **code**, not the absence.
  **Rejected: pulling pricing forward.** It takes `src/prope/call_ledger/seams.py`'s callers and Phase
  17's declared files into a phase that would then have two reasons to fail.
  — **Reversibility:** cheap — a wiring line.

- **D-293:** **`get_released_revision(prompt_id)` does not exist in any phase's plan, and this phase
  builds it.** INT-011 registers it, `evaluation.lock.yml` `consumes` names it, and
  `prompt-registry.lock.yml`'s `apis.exposes` does **not** list it — phases 13, 14 and 15 built
  `get_revision`, `get_diff`, `resolve`, `list_released` and the three commands, and nothing built this.
  EVAL-03's pairing rule is *"the most recent completed run where `version_id` equals the prompt's
  current `released_version_id`"*, so the baseline cannot be paired without asking the registry what is
  released for a prompt id.
  **Adopted:** Phase 16 adds `get_released_revision(session, prompt_id) -> Revision | None` to
  `src/prope/prompt_registry/revisions.py` in plan 13-02's shape, declared as a cross-module addition in
  `files_modified` and reported in the SUMMARY. **Raised as `OQ-087`.**
  **Rejected: evaluation reading `registry.prompt_property` directly.** `data.reads` says *"through its
  API, never by joining across module tables"*, and a cross-schema join is the edge the module map
  forbids.
  **Rejected: calling `resolve(model_name)`.** It is keyed by model name, not prompt id, it returns a
  `RevisionBinding` with no status and no `finished_at`-bearing identity, and it is the gateway's
  10 ms hot path — a second consumer with different needs is how a hot path acquires a parameter.
  **Rejected: storing `released_version_id` on `eval_run`.** The failure-mode row pins the baseline by
  identity *precisely so* a changed pointer invalidates the pairing; a stored copy is the stale
  comparison that row exists to prevent.
  — **Reversibility:** cheap to move — the function is ten lines and its home is the argument, not the
  code.

- **D-294:** **`outcome = 'error'` is a state, and a withheld delta carries a machine `code`, never a
  bare `None`.** `case_result.outcome` is `pass | fail | error` with a named `CHECK`; the classifier that
  maps a `DispatchError` to `error` is a pure function over provider-access's typed value and **never
  reads a status code** (A-095, ADR-0017 — the two modules that depend on that judgement cannot drift
  apart). The cost delta is a value object whose withheld form carries a `WithheldReason` `StrEnum`
  member — `CASE_ERROR`, `UNPRICED`, `UNKNOWN_USAGE`, `CURRENCY_MISMATCH`, `NO_BASELINE`,
  `NOT_PRICED_YET` — which is ADR-0053's *"the API returns a machine `code` the client translates"* and
  is `CeilingReason`'s precedent (02-04) applied one module over.
  **Rejected: `cost_delta: Decimal | None`.** SC1 requires *"withheld with a stated reason"*; a `None`
  states nothing, and the review screen would have to guess which of six reasons to render.
  **Rejected: folding `error` into `fail` and marking it.** A-057 forbids it and the reason is the
  product's: an unreachable provider is not evidence about a prompt.
  — **Reversibility:** costly — the enum is what Phase 17's summary and the SPA's catalogue key off.

### The assertions

- **D-295:** **Two dependencies are added — `regex` and `jsonschema` — and `uv.lock` moves.**
  ORCHESTRATION §3 forbids this unless a plan says so, so this decision is the saying. `regex` is not a
  taste: A-005 makes the pattern **user-authored code running in `worker`**, stdlib `re` has no timeout
  and holds the GIL in C without yielding, and as of ADR-0049 that container also runs call-ledger's
  drain, call-ledger's retention job and provider-access's batch dispatch — one prompt owner's `(a+)+$`
  is an outage in three other modules. `jsonschema` is named because pydantic v2 **emits** JSON Schema
  and does not validate an arbitrary externally-authored one, so A-005's JSON-schema assertion type had
  no library until step 4 named one.
  **Rejected: stdlib `re` with a length bound only.** The bound is the second line of defence, not the
  first; a catastrophic pattern beats any input length worth allowing.
  **Rejected: `signal.alarm` or a thread watchdog around `re`.** `signal` is POSIX-only (the development
  host is Windows — ORCHESTRATION §3) and a thread cannot interrupt a C-level regex holding the GIL,
  which is the whole failure.
  **Companion assertion:** `tests/architecture/test_no_stdlib_re_on_the_assertion_path.py` walks the AST
  of `src/prope/evaluation/` and fails on `import re` — the lock's own *"a companion test asserts stdlib
  `re` is not imported on the assertion path"*.
  — **Reversibility:** costly — a dependency in `uv.lock` is a supply-chain decision, and removing
  `regex` means re-answering T-009.

- **D-296:** **The assertion registry is CODE keyed by modality, not a database table**, and the contrast
  with `history.history_action_registry` is the argument rather than an inconsistency. An action name is
  *data* another module's validator compares against, so a row is enough and ADR-0038's *"adding an
  action is safe by construction"* holds. An assertion type is bound to an **evaluator function that
  must exist**: a registry row with no evaluator is a case that can never be run, discovered at dispatch
  time, on a run somebody paid for. So the registry is a module-level immutable mapping
  `{Modality: {type_name: Evaluator}}`, the `assertions` payload is validated against it by a pydantic v2
  discriminated union **at suite-save time**, and a type outside the suite's modality is refused where
  its author can fix it.
  **Rejected: an `evaluation.assertion_type` table.** Two provisioning paths for one vocabulary (D-02's
  refusal), and the failure mode is worse than history's.
  **Rejected: validating assertions only at evaluation time.** A-061's *"the authoring UI offers only the
  types valid for the suite's modality"* is an authoring-time promise, and A-124's friction belongs where
  the author is.
  — **Reversibility:** cheap.

- **D-297:** **Nine `text` assertion types ship; the `structured` set ships without its URL-fetch type.**
  Two conflicts, one decision, one OQ.
  *The count.* `eval_case.notes` says *"the eight types in A-005"* and then enumerates **nine** — exact,
  substring, regex, JSON-schema, required phrase, forbidden phrase, max length, max latency, max cost —
  and A-005's Statement enumerates the same nine. Adopt **nine**; the enumeration is the specification
  and the adjective is the typo, which is D-60's disposition of the 30-vs-31 vocabulary count.
  *The egress.* A-061 registers, for `structured`, *"a URL resolving to a fetchable asset of a stated
  content type"*. Fetching that URL is outbound HTTP from `worker`, and this module's `external_services`
  is `[]` with the comment *"No internet egress. Every upstream call goes through provider-access"* —
  which also holds ADR-0047's SSRF guard. A module that fetches an arbitrary model-supplied URL is an
  SSRF sink with no validator, in the container that holds no credential and no address checker.
  **`asset_fetchable` is therefore not registered**, and the `structured` set ships as JSON-schema
  validity, required key, forbidden key, value equality at a path, asset count, max latency, max cost —
  shape and presence only.
  **Both raised as `OQ-088`.** The spec is not edited to agree.
  **Rejected: registering `asset_fetchable` and routing the fetch through provider-access.** `dispatch()`
  is a chat-completions seam; a general fetch on it is a new capability on the module that owns Prope's
  only egress, decided in an eval phase.
  — **Reversibility:** cheap to add a type, one-way once suites are authored against one.

- **D-298:** **The modality gate compares the suite's declared modality against the LAST OBSERVED shape
  of the target, derived and never stored.** AC-9 wants a refusal *"before any case is dispatched"*
  naming *"the returned shape"* — and no authority says where a returned shape comes from before
  anything is returned. `registry.revision` carries no modality column, `get_model_catalogue` (INT-016)
  returns none and is not in this module's `consumes`, and a probe dispatch bills the call AC-9 says is
  not billed.
  **Adopted:** at claim time, classify the `output_content` of the most recent completed `case_result`
  for the same `version_id` through one named pure function `classify_modality(content) -> Modality`
  (JSON object or array, or a bare URL ⇒ `structured`; otherwise `text`), and refuse with
  `status = 'refused'` and reason `SUITE_MODALITY_MISMATCH` when it disagrees with the suite's declared
  modality. Nothing is stored: A-047's *"derived comparisons are computed on demand and never stored"*
  is the house style and a stored `observed_modality` would be an undeclared column that drifts.
  **The gap, named rather than smoothed:** for a binding **nothing has ever observed**, the gate has no
  input. The run proceeds, the first case's response is classified, and a mismatch aborts the run at
  `status = 'refused'` with `prope_evaluation_modality_mismatch_total` incremented — having billed
  **exactly one** upstream call. That is a real deviation from AC-9's *"no upstream call is billed"*,
  bounded at one case, and it applies only to the first run of a binding. **Raised as `OQ-086`.**
  **Rejected: refusing when nothing has been observed.** It refuses every first run of every prompt,
  which is every run in a pilot.
  **Rejected: a declared `output_modality` on the revision.** It is a column in another module's table
  and a question for the prompt owner that no authority asks.
  — **Reversibility:** cheap on the classifier, costly on the gate's placement.

### Observability, and what may be logged

- **D-299:** **All ten declared metrics are defined at import in
  `src/prope/evaluation/observability.py`, and `prope_evaluation_run_queue_depth` is fed by an
  enumerator seam rather than by a widened claim.** The definition rule is D-40 / D-164 / D-228 unchanged:
  a metric that first appears when it goes non-zero has no baseline, and `REGISTRY.get_sample_value`
  returns `None` — not `0.0` — for a metric nothing has touched.
  The gauge is the sharp one and it repeats a trap this project has already been bitten by twice. A
  `prope_app` `SELECT count(*) FROM evaluation.eval_run WHERE status = 'queued'` issued with no tenant
  set returns **zero rows**, so the gauge would read 0 forever and `EvalQueueBacklog` would be a rule
  that never fires — `ObservedWorkspaces`' *"runs cleanly, deletes nothing, and looks healthy"* wearing a
  different hat. So the depth pass takes a `WorkspaceEnumerator` (02-03's seam, filled by ADR-0051's
  `access.list_workspaces()`) and counts per workspace under RLS.
  **Rejected: widening `claim_next_run()`'s return with a depth.** ADR-0051's rule is identifiers only,
  and the enumeration is the generic answer that exists so the set stops growing.
  **Rejected: a fifth `SECURITY DEFINER` counter.** Never the answer (D-281).
  **`LOGGABLE_FIELDS` gains identifiers and closed tokens only**, in Phase 4's adopted one-flat-list
  shape: `prompt_id`, `version_id`, `suite_id`, `suite_version`, `run_id`, `case_id`, `outcome`,
  `error_code`, `attempt_count`, `duration_ms`. **`suite_name` is refused** — it is author-written text
  that may be non-English and may quote whatever the author was looking at, and the allow-list's stated
  discipline is *"every entry is an identifier or a closed-vocabulary token"*. The lock names
  `suite_name` as a log field in as many words, so this is a deviation with an observable difference and
  is **raised as `OQ-089`**; `suite_id` resolves to the name through the row it is on.
  Every metric's label set is closed and `workspace_id` is never a label (ADR-0030's cardinality rule),
  which is why the gauge above is unlabelled and why its threshold is a whole-deployment number.
  — **Reversibility:** cheap on the metrics, costly on `LOGGABLE_FIELDS` (seven modules inherit the
  shape).

### Claude's Discretion

Open, not decided. Resolve from the lock file, INT-025 and the phase's success criteria, and **state the
resolution in the plan**:

- **Where the run executor's per-run concurrency of 5 lives** — an `asyncio.Semaphore` in the executor,
  or a `TaskGroup` with a bounded queue. A-054 fixes the number; the shape is open, and it interacts with
  ADR-0046's `batch_concurrency = 8` semaphore already held in the same process.
- **Whether `assertion_results` is a jsonb list of per-assertion records or a summary.** The lock names
  the column and not its shape; `GET /eval-runs/{id}/cases` (Phase 17) is the only reader.
- **How `input_variables` are substituted and where the composer lives.** A-027 says the eval runner uses
  *the same resolution and dispatch semantics* as the gateway — and gateway is a **forbidden dependency**
  and is being built in parallel (M7, wave 4). See `<risks>`; the duplication is real and the answer must
  be written down for the M7 planners.
- **Whether `case_result.error_code`'s vocabulary is provider-access's seven `DispatchError` classes
  verbatim or a superset with `assertion_timeout`.** It is a metric label, so it must be closed either
  way.
- **The `evs_` / `evc_` / `evr_` / `evcr_` id-assembly site** — Phase 4 left the same question open for
  `hev_` and six more prefixes follow.
- **Whether `eval_run.role` needs a partial unique index** preventing two `queued` baseline runs for one
  `(version_id, suite_id)`. The pairing rule tolerates duplicates; a submit storm may not.
- **`prope_report`'s read grants.** `grant_table`'s `report_select` defaults to true;
  `case_result.output_content` is prompt-body-class content and `prope_report` is a cross-workspace
  full-read credential (ADR-0037). Make the argument rather than taking the default.
- **Test file placement** against the lock's `test_ref` paths, several of which name
  `tests/integration/test_*` without a `.py` suffix and one of which (`tests/chaos/…`) names a directory
  that does not exist and is Phase 18's.

</decisions>

<specs>
## The concrete surface

### Route table

**Zero HTTP routes.** All nine of INT-025's paths are Phase 17's, `src/prope/app.py` is untouched, and
`src/prope/evaluation/__init__.py` imports no FastAPI at any depth — `worker` imports this package and
must not pay for the framework (14-05's rule, one module over). The route-table test
(`tests/architecture/test_route_table.py`) is not edited by this phase.

### `evaluation.eval_suite`

| column | type | why |
|---|---|---|
| `id` | `text NOT NULL` PK | `evs_` + ULID (ADR-0003). A **suite version** is a row, so this id identifies a version, which is why `eval_run.suite_id` pins a yardstick and not a name |
| `workspace_id` | `text NOT NULL` | ADR-0045; `text` compared to `text`, no cast (OQ-A) |
| `prompt_id` | `text NOT NULL` | A **value, not a reference** — `registry.prompt_property` is another schema (D-223's rule, inherited) |
| `name` | `text NOT NULL` | author-chosen, display text, never in an API path, may be non-English (OQ-010). `CHECK (name <> '')` and a length cap in **characters** (ADR-0053: a byte cap is a ~⅓ cap in Vietnamese) |
| `suite_version` | `integer NOT NULL` | `CHECK (suite_version >= 1)`. Allocated in-transaction, arbitrated by the unique key (D-286) |
| `output_modality` | `text NOT NULL` | `CHECK (output_modality IN ('text','structured'))` — **never a native enum** (Pitfall 4). Mirrored byte-identically by a `StrEnum` in `domain.py` |
| `case_count` | `integer NOT NULL` | `CHECK (case_count >= 0)` and D-285's deferred constraint trigger. **No 10–20 range** — A-059 |
| `created_by` | `text NOT NULL` | actor id, a value (A-122's rule) |
| `created_at` | `timestamptz NOT NULL` | A-003 |

Constraints: `uq_eval_suite_prompt_name_version UNIQUE (prompt_id, name, suite_version)` (the lock's, the
race arbiter); `uq_eval_suite_workspace_id UNIQUE (workspace_id, id)` (trivially unique — the FK target).
Grants: `SELECT, INSERT` to `prope_app`. Policy: `enable_tenant_rls`.

### `evaluation.eval_case`

`id` (`evc_`), `workspace_id`, `suite_id`, `ordinal integer NOT NULL`, `name text NOT NULL`,
`input_messages jsonb NOT NULL`, `input_variables jsonb NOT NULL DEFAULT '{}'::jsonb`,
`assertions jsonb NOT NULL`, `created_at timestamptz NOT NULL`.

- `input_messages` / `input_variables` / — **prompt-body-class content** (T-011, A-046). Never logged,
  never a metric label, never in a history event `details` payload.
- `jsonb`, not `text`, for all three, and the reason is 0003's inversion argued forwards: a malformed
  `assertions` payload is *our own* validated structure, so refusing it at the engine is right, where a
  malformed provider body is evidence and refusing it destroys the thing being kept.
- `CHECK (jsonb_typeof(assertions) = 'array')`, `CHECK (jsonb_typeof(input_messages) = 'array')`,
  `CHECK (jsonb_typeof(input_variables) = 'object')` — named, so a test can say which rule refused.
- `uq_eval_case_suite_ordinal UNIQUE (suite_id, ordinal)`.
- `fk_eval_case_suite FOREIGN KEY (workspace_id, suite_id) REFERENCES evaluation.eval_suite
  (workspace_id, id)` — **`workspace_id` in both halves**, because referential-integrity checks bypass row
  security (D-222).
- Grants: `SELECT, INSERT`. No `UPDATE`, no `DELETE`.

### `evaluation.eval_run`

`id` (`evr_`), `workspace_id`, `prompt_id`, `version_id`, `suite_id`, `role`, `status`, `started_at`,
`finished_at`, `pass_count`, `fail_count`, `error_count`, `input_tokens`, `output_tokens`, `cost_amount`,
`cost_currency`, `priced_at`, `started_by`. **No `created_at`** — see D-287.

- `ck_eval_run_role CHECK (role IN ('candidate','baseline'))`
- `ck_eval_run_status CHECK (status IN ('queued','running','completed','interrupted','refused'))` — five
  values, `interrupted` written by Phase 18's sweeper and by nothing here
- `ck_eval_run_queued_has_no_start CHECK (status <> 'queued' OR started_at IS NULL)` — the claim is what
  stamps it
- `ck_eval_run_cost_carries_currency CHECK ((cost_amount IS NULL) = (cost_currency IS NULL))` — the
  ledger's `ck_workspace_spend_total_cost_carries_currency`, one schema over: a number with no unit is
  the shape this project refuses everywhere
- `cost_amount numeric`, **never floating point** — the schema-invariant walk asserts it
- `fk_eval_run_suite (workspace_id, suite_id) -> eval_suite (workspace_id, id)`
- `prompt_id` / `version_id` / `started_by` are values, not references — no foreign key leaves
  `evaluation`
- Grants: `SELECT, INSERT` via `grant_table`, plus `grant_column_update` on **exactly** D-284's ten
  columns. No `DELETE`.
- Indexes: `ix_eval_run_queued_id (id) WHERE status = 'queued'`;
  `ix_eval_run_workspace_status (workspace_id, status)`;
  `ix_eval_run_baseline_pairing (workspace_id, suite_id, version_id, status, finished_at DESC)`.

### `evaluation.case_result`

`id` (`evcr_`), `workspace_id`, `run_id`, `case_id`, `outcome`, `assertion_results jsonb NOT NULL`,
`output_content text`, `latency_ms integer`, `input_tokens integer`, `output_tokens integer`,
`error_code text`, `attempt_count integer NOT NULL`, `created_at timestamptz NOT NULL`.

- `ck_case_result_outcome CHECK (outcome IN ('pass','fail','error'))` — A-057's distinction as an engine
  fact
- `ck_case_result_error_has_code CHECK (outcome <> 'error' OR error_code IS NOT NULL)` — an error with no
  class is not evidence
- `ck_case_result_unknown_usage_is_null` in `call_record`'s spirit: token counts are NULL when the
  provider returned no usage object, **never zero**
- `output_content` is `text`, nullable (an errored case has none). It is the second copy of a model's
  output and the module's largest disk term (A-137) — **no retention, no delete path, and `prope_app`
  holds no `DELETE`**
- `fk_case_result_run (workspace_id, run_id) -> eval_run (workspace_id, id)`;
  `uq_case_result_run_case UNIQUE (run_id, case_id)` — AC-7's *"no case is dispatched twice"* has an
  engine backstop, not only a sweeper rule
- Grants: `SELECT, INSERT`. No `UPDATE`, no `DELETE`.
- Index: `ix_case_result_workspace_run (workspace_id, run_id)`.

### `evaluation.claim_next_run(p_max_concurrent_runs integer)`

```sql
CREATE FUNCTION evaluation.claim_next_run(p_max_concurrent_runs integer)
RETURNS TABLE (run_id text, workspace_id text, prompt_id text, version_id text, suite_id text)
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = ''
AS $$
WITH candidate AS (
    SELECT r.id
    FROM   evaluation.eval_run r
    WHERE  r.status = 'queued'
      AND  (SELECT count(*) FROM evaluation.eval_run r2
             WHERE r2.workspace_id = r.workspace_id AND r2.status = 'running')
           < p_max_concurrent_runs
    ORDER  BY r.id
    FOR UPDATE SKIP LOCKED
    LIMIT  1
)
UPDATE evaluation.eval_run AS u
   SET status = 'running', started_at = now()
  FROM candidate c
 WHERE u.id = c.id
RETURNING u.id, u.workspace_id, u.prompt_id, u.version_id, u.suite_id;
$$;
REVOKE ALL ON FUNCTION evaluation.claim_next_run(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION evaluation.claim_next_run(integer) TO prope_app;
```

Emitted through `security_definer_function(..., volatility="VOLATILE")`, so `grep -c "SECURITY DEFINER"`
over the revision is **0** — 07-01's rule. **Every object is schema-qualified** because `search_path` is
empty. **Every body column is table-qualified**, because the `RETURNS TABLE` output names collide with
column names of the same spelling; if the engine still reports ambiguity, rename the output columns
(`o_run_id`, …) and pin the new signature in the set test — do not drop the qualification.

### Internal function signatures (this phase)

```python
# src/prope/evaluation/suites.py
async def create_suite(session, *, workspace_id, prompt_id, name, output_modality, cases, actor_id) -> str
async def save_next_suite_version(session, *, workspace_id, suite_id, cases, actor_id) -> str   # EVAL-04
async def get_suite(session, suite_id) -> Suite | None

# src/prope/evaluation/runs.py
async def create_queued_runs(session, *, workspace_id, prompt_id, version_id, suite_ids, role, actor_id) -> tuple[str, ...]
async def transition(session, run_id, *, to: RunStatus, ...) -> None      # the only status writer

# src/prope/evaluation/claim.py
CLAIM_NEXT_RUN: sqlalchemy.TextClause                                     # one text() constant, no interpolation
async def claim_one(sessionmaker, *, max_concurrent_runs: int) -> ClaimedRun | None   # D-288's one transaction

# src/prope/evaluation/executor.py
async def execute_run(sessionmaker, claimed: ClaimedRun, *, dispatch: DispatchPort,
                      get_revision, concurrency: int = 5) -> None

# src/prope/evaluation/assertions.py
REGISTRY: Mapping[Modality, Mapping[str, Evaluator]]                      # D-296
def evaluate(assertions, *, content: str, latency_ms: int, cost: Decimal | None) -> tuple[AssertionResult, ...]

# src/prope/evaluation/modality.py
def classify_modality(content: str) -> Modality                           # D-298
async def observed_modality(session, version_id) -> Modality | None

# src/prope/evaluation/comparison.py
def pair_runs(candidate: Run, baseline: Run | None) -> Pairing            # refuses across suite versions
def cost_delta(candidate: RunTotals | None, baseline: RunTotals | None) -> CostDelta   # D-294

# src/prope/prompt_registry/revisions.py   (D-293, cross-module addition)
async def get_released_revision(session, prompt_id) -> Revision | None
```

### Machine codes (ADR-0053 — the client translates; no literal display strings)

`SUITE_MODALITY_MISMATCH` · `CROSS_SUITE_VERSION_COMPARISON` · `SUITE_VERSION_CONFLICT` ·
`ASSERTION_TIMEOUT` · `UNKNOWN_ASSERTION_TYPE` · `ASSERTION_TYPE_NOT_VALID_FOR_MODALITY` — and
`WithheldReason`: `CASE_ERROR` · `UNPRICED` · `UNKNOWN_USAGE` · `CURRENCY_MISMATCH` · `NO_BASELINE` ·
`NOT_PRICED_YET`.

### Metrics — `src/prope/evaluation/observability.py`, all ten at import

| metric | type | labels (closed) | note |
|---|---|---|---|
| `prope_evaluation_run_duration_seconds` | Histogram | `role`∈{candidate,baseline}, `status`∈{completed,interrupted,refused} | **120 must be a bucket edge** — it is the stated success metric, and `histogram_quantile` interpolates inside a bucket |
| `prope_evaluation_case_duration_seconds` | Histogram | none | **1.0 and 60 must be edges** — the regex timeout and the per-case dispatch timeout |
| `prope_evaluation_run_total` | Counter | `status`∈{completed,interrupted,refused} | |
| `prope_evaluation_case_error_total` | Counter | `error_code` (closed superset of INT-015's seven classes) | dispatch errors, never fails |
| `prope_evaluation_case_flip_total` | Counter | none | same revision, same suite, outcome changed |
| `prope_evaluation_baseline_reused_total` | Counter | `outcome`∈{reused,recomputed} | EVAL-03's visible half |
| `prope_evaluation_run_interrupted_total` | Counter | none | defined here, incremented in Phase 18 |
| `prope_evaluation_cost_delta_ratio` | Histogram | none | **1.20 must be an edge** — OQ-009's resolved threshold |
| `prope_evaluation_run_queue_depth` | Gauge | none | D-299's enumerator; `workspace_id` is never a label |
| `prope_evaluation_modality_mismatch_total` | Counter | `declared`∈{text,structured}, `observed`∈{text,structured} | bounded at 4 series |

### The tests that prove each

| Proves | File |
|---|---|
| SC1 / EVAL-02 — error is not fail, delta withheld with a code | `tests/integration/test_error_not_fail.py` |
| SC2 / EVAL-03 — baseline reused, not re-dispatched, timestamp shown | `tests/integration/test_baseline_reuse.py` |
| SC3 / EVAL-04 — version 5 created, in-flight run pinned, sibling untouched, cross-version refused | `tests/integration/test_suite_version_pinning.py` |
| SC4 / EVAL-09 — refused at claim, both shapes named, no dispatch, `status=refused` | `tests/integration/test_modality_mismatch_refused.py` |
| Suite immutability as a privilege (positive control + grant/observe/revoke) | `tests/security/test_suite_append_only_privilege.py` |
| `suite_id` and the five pinned columns hold no UPDATE | `tests/security/test_eval_run_column_grants.py` |
| Owed AC-12 — claim returns identifiers only; a direct `SELECT` with no tenant set returns zero rows | `tests/security/test_claim_returns_identifiers_only.py` |
| Owed AC-13 — two concurrent claims, one winner, the other skips | `tests/integration/test_claim_next_run.py` |
| Claim + `eval_run_started` are one transaction (D-288) | `tests/integration/test_claim_and_event_are_atomic.py` |
| The `SECURITY DEFINER` set is exactly four | `tests/security/test_security_definer_set_is_exactly_sanctioned.py` *(edited)* |
| Four jobs in `worker` | `tests/integration/test_worker_jobs.py` *(edited)* |
| Assertion evaluators, per type, per modality | `tests/unit/test_assertion_evaluators.py` |
| Regex timeout ⇒ `outcome=error` within 1.0 s | `tests/security/test_regex_assertion_timeout.py` |
| stdlib `re` absent from the assertion path (AST walk) | `tests/architecture/test_no_stdlib_re_on_the_assertion_path.py` |
| Cost-delta arithmetic incl. every withheld reason | `tests/unit/test_cost_delta_arithmetic.py` |
| Baseline pairing rule, incl. A-060's no-release case | `tests/unit/test_baseline_pairing.py` |
| `classify_modality` | `tests/unit/test_modality_classifier.py` |
| Tenancy: zero rows with no `app.workspace_id`, all four tables | `tests/security/test_evaluation_tenant_isolation.py` |
| Shared seeding constants and workspace ids | `tests/evaluation/__init__.py` |

### What to read before planning

Authoritative and **read-only**. Per ORCHESTRATION §5 the only permitted `docs/` write is *creating* an
`OQ-NNN` file.

- `docs/modules/evaluation.lock.yml` — `data.owns` (all four tables' `notes` **and** `amended` blocks are
  the actual schema spec), `deployment_target` (the three `worker` residents), `libraries_frameworks`
  (the `regex` / `jsonschema` paragraph), `security_requirements` (T-008…T-011 and the four step-4
  additions), `failure_modes` (rows 2, 4, 6 and 8 are this phase's), `acceptance_criteria` AC-2, AC-3,
  AC-4, AC-9, **and the owed-criteria comment block at lines 651–686** — AC-9's and AC-10's restatements
  and the new AC-11/12/13 are there and nowhere else
- `docs/adr/0049-…` — the claim SQL, the two surviving bounds and their table, §3's whole
  `SECURITY DEFINER` argument, and the Consequences bullet D-289 contradicts
- `docs/adr/0042-…` — the template every one of the four functions is built to, and the two amendment
  blocks that took the count from two to four
- `docs/adr/0004-…` (baseline reuse, one run measures one revision), `docs/adr/0006-…` (named suites),
  `docs/adr/0005-…` (`requires_acknowledgement` is computed once, in Phase 17)
- `docs/adr/0045-…`, `0035-…`, `0027-…`, `0037-…` — tenancy, the coverage walk, the roles
- `docs/architecture/interfaces.md` — **INT-011** (`get_released_revision` is registered here and
  nowhere else — D-293), **INT-015** (the `DispatchError`-is-a-value rule and the per-consumer failure
  table), **INT-025** (Phase 17's routes, read for what this phase must *not* build), INT-017, INT-019,
  INT-020, INT-021, INT-006
- `docs/brainstorm/assumptions/` — `A-004`, `A-005`, `A-053`, `A-054`, `A-057`, `A-059`, `A-060`,
  `A-061`, `A-062`, `A-063`, `A-088`, `A-095`, `A-137`, `A-138`
- `.planning/research/PITFALLS.md` §1 (evaluation owes AC-11, AC-12, AC-13) and §2 (**AC-9 and AC-10 are
  both restated — the plan must use the restated form, not the lock's literal text**)
- `.planning/phases/07-…/07-01-PLAN.md` (the `security_definer_function` helper) and `07-06-PLAN.md`
  (the exact-set test and `NOT_YET_BUILT`); `.planning/phases/13-…/13-01-PLAN.md` (D-220 through D-228 —
  the one-revision shape, the composite-FK rule, the per-module observability module);
  `.planning/phases/02-…/02-CONTEXT.md` D-13 / D-14 (worker composition, the supervised-job contract);
  `.planning/phases/04-…/04-CONTEXT.md` **D-61** (the four `eval_*` actions were seeded with **empty**
  `detail_keys` and Phase 16 is named as the phase that registers its own)
- On disk, before Task 1: `uv run alembic heads`; `alembic/ddl.py`; `tests/conftest.py`;
  `tests/architecture/test_tenant_coverage.py`; `tests/architecture/test_schema_invariants.py`;
  `tests/integration/test_migration_chain.py`; `src/prope/worker.py`; `src/prope/supervisor.py`;
  `src/prope/call_ledger/seams.py` (`EvalUsageRow`, `RunTotals`); `src/prope/property_history/append.py`;
  `src/prope/prompt_registry/revisions.py`; `src/prope/provider_access/` (the real `dispatch` signature
  and `DispatchError` classes)

</specs>

<risks>
## What is most likely to go wrong, and what catches it

- **The four `eval_*` history actions were seeded with EMPTY `detail_keys`, and the first `append` will
  be refused.** Phase 4's D-61 says it outright and names this phase: *"Phase 16 writing
  `eval_run_started` with `details={"version_id": …}` against this seed is refused with
  `unknown_detail_key`."* The lock requires those events to carry `version_id` and `suite_version`
  (`prompt_id` maps to the `scope_prompt_id` column and `actor` to `actor_id`, so only those two are
  `details` keys). **The catch:** this phase's revision `UPDATE`s the four
  `history.history_action_registry` rows — a cross-schema data write by `prope_migrate`, which is the
  only writer that table has — and a test asserts the four rows carry exactly
  `{version_id, suite_version}`. A plan that does not do this discovers it as a rolled-back transaction
  in the middle of the first green-looking run. This is a **cross-module write** and must appear in
  `files_modified` reasoning and in the SUMMARY.

- **The `RETURNS TABLE` output names collide with the columns they select.** `workspace_id`,
  `prompt_id`, `version_id` and `suite_id` are output parameter names *and* column names in the same
  function, under `search_path = ''`. **The catch:** every body reference is table-qualified (`u.`,
  `r.`, `c.`), and the plan's acceptance criteria include *calling the function and asserting the five
  returned names* — not merely that the migration applied.

- **The claim loop looks healthy while claiming nothing.** Three independent ways: `NOT_YET_BUILT` still
  holds the name so the set test is red rather than the loop being wrong (loud, fine); the function
  exists but `GRANT EXECUTE` was not emitted so `prope_app` gets `permission denied` (loud); or the
  partial index is missing and the poll degrades to a seq scan (silent, and only visible under load).
  **The catch:** the claim test asserts a claimed row *and* a positive control — a queued row read back
  through `migrate_engine` — so *"nothing to claim"* and *"could not see anything"* are distinguishable,
  which is `test_append_only_privilege.py`'s standing lesson.

- **`prope_evaluation_run_queue_depth` reads 0 forever.** The single most likely silent defect in this
  phase, because the code is correct-looking and the alert is the control. Covered by D-299, and the
  test asserts the gauge is non-zero for a queued run **in a workspace the reading transaction did not
  set as its tenant** — which is the only version of the assertion that can fail.

- **The eval composer and the gateway's composer drift.** A-027 says the eval runner uses *the same
  resolution and dispatch semantics* as the gateway; `gateway` is a **forbidden dependency**; and M7 is
  being built **in parallel with M6** (both wave 4), so no shared module can be planned into either. Two
  implementations of variable substitution and the system-prompt rule will exist, and the failure mode is
  the worst one this module has: the eval measures something production does not run, silently, and the
  reviewer's evidence is about a different request. **The catch:** the composer lands at
  `src/prope/evaluation/composition.py` with ADR-0011, GATE-07 and GATE-08 named in its docstring as the
  contract it must match, a table of cases (missing variable, literal placeholder, caller-supplied
  system message) it asserts identically, and a `deferred-items.md` entry addressed to the M7 planners so
  Phase 19 mirrors the table rather than inventing a second one. This is a risk that is *bounded*, not
  closed, and the plan should say so.

- **`case_result.output_content` reaches a log line or a `details` payload.** It is prompt-body-class
  content in a module that writes four history events and logs ten fields. **The catch:** D-299's
  allow-list holds identifiers only, and a test walks every log record this module emits and asserts
  every key is in `LOGGABLE_FIELDS` (04-04's shape, *"the first thing in the project that reads
  `LOGGABLE_FIELDS` at all"*).

- **A cross-version comparison passes because both runs happen to carry the same suite *name*.** The
  pairing rule is by `suite_id`, and `suite_id` identifies a *version*. A test that seeds two versions of
  the suite named `"safety"` and asserts the refusal names **both version numbers** is what separates the
  correct implementation from the one that compares names.

- **The suite-version race is invisible in a single-threaded test.** `uq_eval_suite_prompt_name_version`
  is the arbiter and the writer retries once; a test that never runs two savers concurrently proves
  nothing about it. Two concurrent `save_next_suite_version` calls, one winner, one retry that lands
  version *n+2* — asserted, in 13-02's `revision_number` shape.

- **`regex` and `jsonschema` move `uv.lock`.** ORCHESTRATION §3 says no dependency may be added unless a
  plan explicitly says so; D-295 is that saying, and the plan must carry it in `must_haves` so the
  reviewer of the lock diff knows it was decided rather than dragged in. Pin both exactly, in
  `pyproject.toml`'s existing commented style.

- **The phase is graded on four criteria and three of them need a dispatch that Phase 17 owns the wiring
  of.** D-292 resolves it by capability, and the plan must say out loud that Phase 16 ships an executor
  whose money seams are stubs with named insertion points, and that a run completing with a NULL cost is
  the *expected* state at the end of this phase — not a bug Phase 18 will find.

</risks>

---

*Phase: 16-schema-suite-versioning-assertions-and-the-run-lifecycle*
*Decisions consumed: D-280 through D-299 (range fully consumed). Open questions raised: OQ-086, OQ-087,
OQ-088, OQ-089, OQ-090 (range fully consumed — a sixth deviation escalates per ORCHESTRATION §5).*
*Context gathered: 2026-08-11*
