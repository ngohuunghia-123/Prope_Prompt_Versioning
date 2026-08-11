# Phase 17: Seams: nine routes, the review summary, and four consumed modules - Context

**Gathered:** 2026-08-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 16 gives evaluation four tables, a suite that versions, an assertion that evaluates, and a run
that moves `queued -> running -> completed` under `worker`'s claim. **None of that is evidence yet.**
A run is evidence when a reviewer can read per-case pass/fail for two revisions side by side with the
token and money delta between them, and when release-control can pull one object that says whether
this decision needs an acknowledgement. That object, and the nine routes that produce and read the
runs behind it, are this phase.

This is also the phase where evaluation stops being self-contained. It is the module with the most
edges in Prope — one exposed in-process seam plus a management API, and **five** consumed modules —
and every one of its four ROADMAP success criteria is a claim about somebody else's answer arriving
correctly: the registry's revision, provider-access's dispatch, call-ledger's totals, access-control's
permission, property-history's append.

**Delivers:**

- `src/prope/evaluation/api.py` — INT-025's **nine `/api/v1` routes**, each declaring
  `require_session` and **exactly one** `ManagementAction` from the four-action set, both readable
  from `assembled_routes()` rather than from source text, so AC-10's cross-module assertion in Phase
  23 finds a declaration rather than a hole
- **`get_review_summary(session, prompt_id, version_id) -> ReviewSummary`** — INT-017, the one thing
  release-control pulls, and **the only place in Prope where `requires_acknowledgement` is computed**.
  Both carve-outs (an error is not a fail, A-057; an empty suite is not a pass, A-059) applied once,
  here, and never restated in release-control (A-042, ADR-0005)
- **The rollup's withholding rule as one fold**: the total cost delta is withheld whenever *any* suite
  withheld its own, and every valid per-suite delta is still returned (SC4, A-062) — with `None` and a
  named reason, never a zero
- **A three-valued cost delta**: `amount` and `currency` both present or both absent, absence implying
  a closed `WithheldReason`. `RunTotals.cost` is already `None`-not-zero one module over; this is that
  rule carried one seam further (EVAL-02's *"withheld with a stated reason"*)
- **The multi-suite submit**: `POST /eval-runs` creates one run per suite the prompt currently has, in
  one transaction, and returns `202` with one run id per suite (EVAL-08, A-062)
- **`check_spend_ceiling` called twice** — advisory at `POST /eval-runs` so an obvious refusal is
  synchronous, authoritative at the claim, and **only the claim-time result writes
  `eval_run.status = 'refused'`** (the lock's own owed restatement of AC-9, applied to the ceiling)
- **`price_usage` once per run**, batched, with a caller-generated `call_id` derived from the case
  result so a re-price is idempotent on `call_id` (A-099, INT-019's upsert), `source = eval`, and no
  body — the field does not exist on `EvalUsageRow` and that is the guarantee
- **`get_run_totals` on both sides of every delta**, with the two counts deciding the withholding
  *before* any subtraction happens (INT-021, A-101)
- **The `+20%` cost warning as a flag with its threshold beside it** — never a display string
  (ADR-0053), never a block, and with **no dormant block branch anywhere in the module** (OQ-009)
- `may()` at every route edge, with the subject carrying `owner_id` and `access_level` read from the
  prompt row this module already read, because access-control may not read the subject it authorises
  (ADR-0020) — and `suite.edit` distinct from `prompt.edit`, which is BR-10 expressed as data
- `append()` for `eval_suite_updated` and `eval_run_started`, on the caller's session inside the
  transaction that makes the state change (ADR-0023, A-014)
- The **refusal shapes**: not-found when the actor cannot see the prompt, forbidden naming the missing
  permission when they can, and a ceiling refusal that states the reason and **no figure** (A-056)
- Increment sites for `prope_evaluation_cost_delta_ratio` and
  `prope_evaluation_run_total{status=refused}` — this phase declares **no eleventh metric**

**Fixed out of scope by ROADMAP (do not absorb):**

- The four tables, `workspace_id` on all four, their RLS policies, suite versioning, the assertion
  registry keyed on `output_modality`, the deterministic evaluators, the modality mismatch refusal,
  the baseline pairing rule, `evaluation.claim_next_run()` and the claim loop, and **the per-case
  `dispatch()` call inside the run executor** — **Phase 16** (EVAL-02, EVAL-03, EVAL-04, EVAL-09).
  D-301 draws that line exactly, because a reader of the two phase goals would draw it somewhere else
- The sweeper that reaps a run whose worker died, the two surviving concurrency bounds asserted
  independently, eval runs and case results answering not-found for a private prompt, and the regex
  timeout's blast radius — **Phase 18** (EVAL-06, EVAL-07, EVAL-10, and the owed AC-11 / AC-12 / AC-13)
- Release-control **enforcing** `requires_acknowledgement`, storing the acknowledgement reason on the
  approval, rendering the review screen, and the degraded-evidence path when this pull raises —
  **Phase 23 and Phase 24** (RC-04, RC-05). This phase owes them a shape and a raise, nothing else
- **The React SPA.** It owns no milestone (PITFALLS §3). ROADMAP SC3 says the warning appears *"above
  the decision buttons"*; there are no buttons. Here it is a boolean and a ratio on a JSON rollup, and
  the plan must say so rather than quietly redefining the criterion
- `/healthz` and `/readyz` — INT-030, shipped in Phase 2 and unchanged by this module
- The cross-module route-table uniqueness assertion. Five modules now mount under
  `/api/v1/prompts/{prompt_id}/…`; the assertion is about the **assembled** table and cannot run
  before Phase 23 (PITFALLS §5)

**A count worth stating rather than inheriting.** The phase title says *four* consumed modules;
`docs/modules/evaluation.lock.yml` `apis.consumes` names **five** — prompt-registry, provider-access,
call-ledger, access-control **and property-history**. The omitted one is the one whose absence is
silent: a missing history append is a hole in the audit trail, not a failed request. Four of the five
are consumed for an answer; the fifth is consumed for a record. No OQ — ROADMAP is orchestrator-owned
— but a plan that builds four and stops has built the wrong four.

**Requirements:** EVAL-01, EVAL-05, EVAL-08.

</domain>

<decisions>
## Implementation Decisions

Phases 4-16 consume D-46 through D-299. This phase consumes **D-300 through D-319** and no id outside
that range. Open questions: **OQ-091 through OQ-095**, and no id outside that range — §5's
owed-and-unallocated rule applies to anything further.

### Where Phase 16 stops and this phase begins

- **D-300: The boundary is money and surface, not dispatch.** Phase 16 owns the run executor
  *including the per-case `dispatch()` call*; this phase owns everything that turns a completed run
  into evidence — the three call-ledger seams, the delta arithmetic, the rollup, the summary, and the
  nine routes.
  The reading a planner would reach for instead is the **Phase 10 / Phase 11 split**: Phase 10 built
  provider-access's failure *classifier* and Phase 11 built the *dispatch* it classifies. By analogy
  Phase 16 would build the executor against an injected `Dispatcher` protocol and Phase 17 would
  substitute the real `provider_access.dispatch`. **Rejected**, on the wording of Phase 16's own
  success criteria: SC1 is *"cases that ended in a dispatch error are recorded as `error` and never as
  `fail`"* — a claim about a `case_result` row written in response to a `DispatchError` **value**, and
  INT-015 returns that value rather than raising, so Phase 16 can and must observe it; SC4 is
  *"refused before any case is dispatched … with no upstream call billed"*, which is an assertion that
  a real dispatch **did not happen** and is strictly weaker against a fake. A protocol seam would also
  put a second indirection in front of INT-015, and A-142 §1 says an in-process seam is a Python call
  in the caller's container — not an interface with two implementations.
  The consequence, stated so it is not discovered: **this phase adds no case-level code path.** It
  wraps the run at both ends and it opens the surface. Its SC1 — a 20-case run under 120 s at p95 with
  the full comparison — is therefore an end-to-end assertion over Phase 16's executor plus this
  phase's pricing and comparison, and it is the first test in the milestone that exercises both.
  **Re-ground before planning:** Phase 16 is being planned in parallel and its plan set is the
  authority on what is on disk. If it drew this line elsewhere, follow disk and say so in the SUMMARY.
  — **Reversibility:** costly — it decides which phase's test file holds the 120 s figure and which
  phase's SUMMARY claims EVAL-01.
- **D-301: The batch admission gate is consumed, never installed.** Plan 11-04 installs
  `AdmissionGate(Priority.BATCH, …)` in `src/prope/worker.py` at the composition root, and
  `installed_gate()` raises `RuntimeError` naming both roots when nothing is installed. This phase
  calls `dispatch(..., priority=Priority.BATCH, stream=False)` — or asserts that Phase 16's executor
  does — and **installs no gate of its own**.
  **Rejected: a second gate scoped to evaluation.** ADR-0046 makes the *processes* the priority
  classes; a second gate in the same process is ADR-0016's defect rebuilt by accident, with the
  workspace's own key paying for it. Plan 11-01 wrote that argument at `install_admission_gate` and it
  is not re-derived here.
  **Rejected: `stream=True` for a long case.** A-054 caps a case at 60 s and the eval stores a
  completed output; streaming buys nothing and puts evaluation on the one code path where a mid-stream
  `DispatchError` has different semantics (INT-015's failure table).
  — **Reversibility:** cheap.
- **D-302: The two advisory checks and the two authoritative checks are the same pair, and only the
  claim-time result writes `status = 'refused'`.** `docs/modules/evaluation.lock.yml`'s owed
  restatement of AC-9 says it in as many words: *"the modality check and A-029's spend-ceiling check
  both run TWICE: advisory at `POST /eval-runs` so an obvious mistake gets a synchronous error, and
  authoritative at claim time, because a queued run may sit behind others that consume the budget
  while it waits."*
  This phase owns the ceiling half of both calls and the **claim-time** call is an edit to Phase 16's
  claim path — a cross-phase edit, and it must be visible in the plan rather than discovered in
  review.
  **Rejected: once, at `POST` only.** INT-020's *"checked once, before the first dispatch"* reads that
  way and is wrong for a queue: a run admitted at `POST` can sit behind two others that spend the
  remaining budget, and the ceiling would then be a check that passed at a moment nobody cares about.
  **Rejected: once, at the claim only.** A reviewer gets a `202` and a `refused` run for something the
  route could have said synchronously, and INT-025's *"refused when a configured spend ceiling is
  reached"* becomes a thing the poll discovers.
  — **Reversibility:** cheap.
- **D-303: `prope_call_ledger_ceiling_check_total{result}` is asserted, not the branch.** The lock's
  `test_plan.security` requires the fail-open path to be *tested explicitly — "a silent fail-open and
  a working check look identical from the outside"*. Phase 2 already ships the branch, the
  `CeilingDecision` type with two fields and no third, and the counter with `allowed | refused |
  failed_open` (`src/prope/observability.py:424`). This phase's obligation is the **caller** half: a
  ledger error lets the run proceed **and** the counter moved. A test that only observes the run
  proceeding cannot tell a fail-open from a workspace under its ceiling.
  — **Reversibility:** cheap.

### The review summary — the one thing release-control pulls

- **D-304: `get_review_summary` takes the caller's `AsyncSession`, not a `sessionmaker`, and takes no
  `workspace_id`.** This inverts call-ledger's D-19 posture on purpose, and the reason inverts with it.
  D-19 gives call-ledger's seams their own transaction because a *write* that raised inside
  evaluation's transaction would take with it the run-error row evaluation is required to write. This
  is a pure read on a rendering path: release-control has already opened a `workspace_transaction` to
  read the revision it is showing, and a second sessionmaker would put the evidence and the revision
  in **two snapshots** — a review screen composed of two instants, which is precisely what A-047's
  *"composed at read time, every time"* is asking not to happen.
  No `workspace_id` parameter, because RLS supplies the tenant: a `prompt_id` from another workspace
  reads **zero rows**, which is not-found, which is A-116's not-found-never-forbidden falling out of
  the policy rather than being implemented. `get_run_totals` had to take one (Phase 2's D-20) because
  it opens its own transaction; this one does not, and that is the whole difference.
  INT-017 registers a two-argument form. Adding `session` in front is **an addition to a registered
  seam**, in the shape plan 11-01 established when `dispatch` gained `workspace_id`: recorded in the
  SUMMARY, not raised as an OQ, because it is structurally forced by ADR-0045 rather than chosen.
  — **Reversibility:** costly — Phase 23 is written against this signature.
- **D-305: `requires_acknowledgement` is one expression over the suite rows, and the carve-outs are
  carried by the arithmetic rather than by guards.** It is true when any row has `fail_count > 0`,
  **or** any row has no completed run for the candidate. `error_count` is a disjoint column and never
  enters the expression, which is A-057 applied by construction; an empty suite has
  `case_count = 0`, therefore `fail_count = 0` and `pass_count = 0`, so A-059's *"never a pass"* is
  carried by a separate `is_empty` flag on the row rather than by a UI reading `0/0` as green.
  The third clause is the one no authority states, and it is adopted **fail-closed**: a suite whose
  candidate has no completed run is missing evidence, and A-070 already fixes the house rule for
  missing evidence — a summary that could not be pulled makes the acknowledgement mandatory. A suite
  that could not be measured is the same fact one row down. It makes approval harder, never easier, so
  it fails in the safe direction, and it is raised as **`OQ-095`** rather than absorbed.
  **Rejected: computing it in release-control.** ADR-0005 and A-042 forbid it, and INT-017 says
  *"computed here and never restated by the consumer"*.
  **Rejected: computing it in both and asserting they agree.** Two implementations of a boolean whose
  false value is *"no human needs to say anything"* is the one place a drift is silent.
  — **Reversibility:** one-way — Phase 23's approve path is written against the field, and a
  workspace's approvals will already carry the reasons it forced.
- **D-306: A summary that cannot be assembled RAISES. There is no degraded `ReviewSummary`.** No
  `except` in this module returns an empty row list, and `ReviewSummary` carries **no `unavailable`
  flag**. INT-017's failure semantics are explicit — *"release-control's response to a summary it
  could not pull is not to proceed silently"* — and the mechanism that makes that true is a raise,
  because a raise cannot be ignored by omission. A boolean field can: a consumer that never reads it
  gets a summary with zero failing suites and `requires_acknowledgement` false, which is an approval
  recorded with no evidence and no statement of why. That is RC-05's failure arriving through the
  wrong door.
  **Rejected: returning a summary with `requires_acknowledgement = True` and empty rows.** It is the
  fail-closed shape and it is still wrong: release-control cannot distinguish *"three suites, all
  clean, one had no run"* from *"evaluation is down"*, and RC-05 requires the screen to say which.
  — **Reversibility:** cheap.
- **D-307: The cost delta is a value object with three fields and an invariant, not a nullable
  `Decimal`.** `CostDelta(amount: Decimal | None, currency: str | None, withheld_reason: WithheldReason
  | None)`, with `__post_init__` refusing every shape that is not *(amount and currency, no reason)* or
  *(no amount, no currency, a reason)*. **Never zero.** The precedent is one seam over and already
  shipped: `RunTotals.cost` is `None` rather than `Decimal(0)` for a run with nothing priced, because
  *"a zero beside a null currency is a number with no unit"*, and the same sentence is true one
  subtraction later.
  `WithheldReason` is a closed `StrEnum` whose members are byte-identical to the wire codes the client
  translates (ADR-0053) — six, each traceable to an authority and no seventh: `case_error` (A-057),
  `unpriced_rows` and `unknown_usage` (A-101, ADR-0019, and they are disjoint — an unknown-usage record
  carries `cost_status = 'not_applicable'`), `no_baseline` (A-060), `currency_mismatch` (A-107, no FX),
  and `suite_withheld`, which the rollup alone may take.
  **Rejected: `amount: Decimal | None` with no reason.** EVAL-02 requires *"withheld with a stated
  reason"*, and a null the screen has to explain is a null the screen will explain wrongly.
  **Rejected: a zero with a `reliable: false` flag.** A number that is then labelled unreliable is
  read as a number.
  — **Reversibility:** costly — the wire shape is INT-017's and Phase 23 renders it.
- **D-308: The rollup withholds the total and never the list.** One fold: if any suite's `CostDelta`
  carries a `withheld_reason`, the rollup's own delta is `withheld_reason = suite_withheld` and the
  per-suite list is returned untouched (SC4, A-062).
  **Rejected: dropping the per-suite deltas too.** A-062 says the valid ones are still returned, and
  they are the only cost information a reviewer gets on a partly-errored submit.
  **Rejected: summing the deltas that are present.** A total over a subset is not a total, it is
  always smaller than the truth, and it makes the candidate look cheaper — the exact direction the
  warning exists to catch.
  — **Reversibility:** cheap.
- **D-309: The cost warning is a flag, a ratio and a threshold; there is no block branch to
  configure.** The rollup carries `cost_warning: bool`, `cost_delta_ratio: Decimal | None` and
  `cost_warning_threshold: Decimal` (default `0.20`, read from configuration). **No literal display
  string crosses the wire** (ADR-0053) — the client renders the flag through its catalogue.
  OQ-009 was resolved by the user as *warn at >= +20%, never block*, and its text says *"the threshold
  and the block flag stay configuration values as FR-08 requires, defaulting to 20% and to off"*. This
  phase ships the threshold as configuration and **does not ship the block flag at all**: a dormant
  branch that refuses an approval on cost is an auto-block one environment variable away, against the
  first non-negotiable's spirit and against OQ-009's own closing sentence that *"nothing about cost can
  refuse a release"*. That is a deviation from a resolved question's literal text, so it is **raised as
  `OQ-093`** and never patched into the spec.
  `prope_evaluation_cost_delta_ratio` is the declared metric that reads the threshold, and it is
  observed **only when the delta is not withheld** — a histogram with no observation is honest about a
  run it could not price; a `0` observation would put a fabricated ratio in the series the alert reads.
  — **Reversibility:** cheap for the number, costly for the absent branch — adding it later means
  re-opening a resolved user decision.

### The nine routes

- **D-310: Nine routes, four actions, and the members are valued from `access_control.vocabulary.Action`
  by reference.** Plan 14-01's D-244 established the pattern for prompt-registry and this follows it:
  `ManagementAction.SUITE_READ = Action.SUITE_READ.value`, never a retyped literal, because the value
  is mirrored by a `CHECK` and a `role_permission` seed in another module's migration.
  The four are exactly the four the lock names — `suite.read`, `suite.edit`, `run.start`, `run.read` —
  and **`suite.edit` is not `prompt.edit`**, which is BR-10 expressed as data rather than as a
  convention (A-115's closed vocabulary of 25, seeded in Phase 7's `role_permission`).
  **Rejected: one action per route.** Nine members means four new rows in another module's seed and a
  vocabulary of 29 where A-115 closes at 25; and `GET /eval-suites/{id}` and
  `GET /prompts/{id}/eval-suites` differ in path and not in authority.
  — **Reversibility:** costly — the strings are in a shipped `CHECK` and a shipped seed.
- **D-311: `may()` is called once per request, after the prompt row is read, and the child-keyed routes
  resolve their parent in the same statement that reads the child.** ADR-0020 forbids access-control
  reading the subject it authorises, so the caller passes `owner_id` and `access_level` from the row it
  already has. Four of the nine routes are keyed on a `suite_id` or a `run_id` rather than a
  `prompt_id`; for those, the `SELECT` joins to `prompt_property` and returns the owner and access
  level with the child, so a not-found and a not-permitted come out of **one** read.
  **Rejected: read the child, then read the parent, then call `may`.** Three round trips on the poll
  endpoint, and a window in which the parent's `access_level` changes between the two reads — the
  TOCTOU shape plan 14-02's D-250 closed for `GET /revisions/{version_id}` by exactly this move.
  **Rejected: pushing visibility into `visible_subject_filter` (INT-002).** The lock's
  `security_requirements` describe it — *"same filter, same repository-layer enforcement as the
  registry"* — and `apis.consumes` names only `may()`. That mismatch was found at BSP step 5, recorded
  in the change_log as *owed to step 6*, and step 6 did not fold it in. It is **not** resolved here:
  the filter matters for *list* endpoints, and this module's list endpoints are all scoped to one
  prompt whose visibility `may()` already decided. Routed to **Phase 18**, which owns EVAL-06, as
  owed-and-unallocated under ORCHESTRATION §5 — this phase's OQ range is spent on five sharper
  conflicts and borrowing another phase's range is forbidden.
  — **Reversibility:** cheap.
- **D-312: Refusal shapes, in the two directions the project asserts.** Not-found when the actor cannot
  see the prompt — and it is **structural**, not written: RLS returns zero rows for a suite or a run in
  another workspace, so *"an id that never existed"* and *"an id in a workspace you cannot see"* are
  the same code path and therefore byte-identical without anybody arranging it. Forbidden when the
  actor can see the prompt and lacks the permission, with the missing permission in
  `details.permission` and **no prose in `message` that a client would render** (ADR-0053).
  Phase 18 owns proving the private-prompt half end to end (EVAL-06); this phase owes the shape and a
  test that the two paths produce one response.
  — **Reversibility:** one-way in the sense every refusal shape in this project is — a refusal that has
  leaked cannot be un-leaked.
- **D-313: `POST /eval-runs` is all-or-nothing, returns `202`, and a prompt with no suites gets `202`
  with an empty list.** One transaction: the advisory checks, then one `eval_run` row per suite the
  prompt currently has, then the `eval_run_started` append, then commit. A partial submit — some suites
  started, others refused — gives the reviewer a screen where they cannot tell which yardsticks were
  applied, which is the failure A-062's *"one run per suite"* exists to prevent.
  Zero suites is `202` with `runs: []` and **not** a `404`: a `404` says the prompt does not exist,
  which is false, and not-found is the one response shape in this project that carries security weight
  (non-negotiable #4). A-059 already says an empty suite is not a pass; saying so is the summary's job,
  not the route's.
  — **Reversibility:** cheap.
- **D-314: There is no `409` for the concurrency bound. A run beyond `max_concurrent_runs` is created
  `queued`.** `docs/architecture/interfaces.md` INT-025 says *"`409` when a run is already in flight
  beyond `max_concurrent_runs = 2` per workspace"*. ADR-0049 makes that bound a **predicate inside the
  claim transaction**, and the lock's own failure_modes say *"runs beyond it stay queued and start as
  slots free; the queue is visible in the run rows rather than looking like a hang"*. A `409` at
  `POST` would refuse work the database is designed to hold, would make
  `prope_evaluation_run_queue_depth` unreachable above 2, and would need the route to read a bound that
  is only correct inside a transaction it does not open.
  Adopt **queued**, follow the ADR and the lock, and raise **`OQ-091`** naming INT-025's line, ADR-0049
  and A-063 as restated. The spec is not edited to agree.
  — **Reversibility:** costly — the SPA's error handling and the `409` contract are INT-025's wire
  promise, and a client written against a `409` will not poll.
- **D-315: `GET /api/v1/prompts/{prompt_id}/eval-suites/{name}/versions` ships with the name in the
  path, URL-encoded, matched case-sensitively — and the contradiction is raised, not smoothed.** The
  lock's `apis.exposes` and INT-025 both write that path. The lock's `data.owns.eval_suite.notes`
  says, of the same column, *"it is display text, **never an identifier in an API path**, so it can be
  renamed and can be non-English (OQ-010)"*. Two blocks of one file, opposite instructions, and the
  disagreement decides whether renaming a suite breaks a bookmarked URL and whether a Vietnamese suite
  name round-trips through a path segment (ADR-0053 ships Vietnamese only).
  Adopt the route list, because two authorities write the path and one note contradicts them, and
  raise **`OQ-092`**. Two consequences stated at the route: the segment is percent-decoded once and
  compared to the stored value byte-for-byte, and a suite rename changes this URL — which is the
  behaviour the note was written to prevent.
  — **Reversibility:** costly — `/api/v1` is frozen (A-142) and a path is a wire promise.
- **D-316: `PUT /eval-suites/{suite_id}` answers `201` with the **new** suite id, never `200`.** It
  creates the next version and mutates nothing (INT-025, A-004), so the resource the caller addressed
  is not the resource that now exists. A `200` echoing the request is the response shape that makes a
  client believe it edited something.
  Cross-version comparison is refused at `GET /prompts/{id}/comparison` with a machine code carrying
  **both** suite versions in `details` — the lock's failure_mode says the refusal *"names both suite
  versions"*, and naming them in `details` rather than in `message` is ADR-0053.
  — **Reversibility:** cheap.

### Money, and the events

- **D-317: `price_usage` is called once per run, at completion, in one batch, with
  `call_id = case_result.id`.** INT-019 takes a `run_id` and a `Sequence[EvalUsageRow]`, and
  `write_records` already batches and already prices at each record's own `created_at`; a per-case call
  would be N transactions per run for no gain.
  The `call_id` is **derived, not minted**: `case_result.id` is already a unique `evcr_`-prefixed ULID
  in the same workspace, so a re-priced run upserts onto the same rows and cannot double-count a
  workspace's spend (A-099, and INT-019 *"idempotent on `call_id`"*, the same upsert INT-018's drain
  uses). The named alternative — **a fresh ULID minted at pricing time and stored in a new `call_id`
  column on `case_result`** — is rejected twice: it re-prices as a double-count unless the column is
  written first, and it is a **schema change to a Phase 16 table** while Phase 16 is being planned in
  parallel, which ORCHESTRATION §8 makes a lost update rather than a design.
  Consequence to state at the call site: `ledger.call_record.call_id` will hold `evcr_`-prefixed values
  for eval traffic and `call_`-prefixed values for gateway traffic. It is a value, not a foreign key
  (`0002_call_record.py`'s own words), so nothing joins on the prefix — but a human reading the table
  will see two shapes and should find the sentence explaining it.
  **Which cases produce a row at all is not stated anywhere, and it is load-bearing.** INT-019 says
  *"one usage row per eval case"*; a case that never reached the provider — an admission shed, an SSRF
  refusal, a KEK outage — has no usage, no upstream model response and cost nothing. Adopt the split
  the `DispatchError` already carries: **`origin = provider` produces a row** (with
  `usage_status = unknown` when the provider returned no usage object), **`origin = prope` produces
  none.** It is the only rule that keeps `unknown_usage_count` meaning *"the provider did not tell us"*
  rather than *"we never asked"* — and that count is what withholds the delta under D-318, so getting
  it wrong withholds every delta on a run Prope itself refused. Raised as **`OQ-094`**, naming INT-019,
  ADR-0017's `origin` column and phase 12's `origin = prope` classes.
  — **Reversibility:** one-way once rows exist — the derivation is stored in an append-only table.
- **D-318: `get_run_totals` is read on both sides and its two counts decide the withholding BEFORE any
  subtraction.** `unpriced_count > 0` or `unknown_usage_count > 0` on **either** side withholds;
  differing `currency` withholds (A-107 — two runs priced in different currencies produce *no* delta,
  not a converted one); a missing baseline withholds with `no_baseline` (A-060). Only then is the
  subtraction performed.
  **Rejected: subtract, then annotate.** INT-021 says the counts *"are part of the answer, not
  diagnostics"*, and a computed figure that is afterwards labelled incomplete is a figure that gets
  quoted.
  — **Reversibility:** cheap.
- **D-319: The four `eval_*` actions' `detail_keys` must be registered in a migration, and this phase
  verifies-then-adds rather than assuming.** Phase 4's D-61 seeded all four `eval_*` rows with an
  **empty** `detail_keys` allow-list deliberately, and its `deferred-items.md` names **Phase 16** as
  the owner of registering `version_id` and `suite_version` — which `evaluation.lock.yml:94-97`
  declares, so they are spec rather than invention. The named consequence, recorded twelve phases
  early, is that appending `eval_run_started` with `details={"version_id": …}` against the current seed
  is **refused with `unknown_detail_key`**, rolling back the caller's transaction.
  This phase is the first appender: `eval_suite_updated` is `PUT /eval-suites/{id}` and
  `eval_run_started` is `POST /eval-runs`. So the plan does what 13-01 Task 2 step 0 did for
  `grant_column_update`: **read the registry on disk; if the four rows still carry empty
  `detail_keys`, add the `UPDATE` as a revision in this phase and say which branch was taken in the
  SUMMARY.** The registry is `SELECT`-only for `prope_app` (ADR-0038, D-51), so the change is a
  migration by construction and there is no application path that could do it.
  `eval_run_started` is appended at the **creation** of the run rows, in `app`, with the reviewer as
  `actor_id` — not at the claim, which happens in `worker` with no actor and would have to write
  `actor_type = 'system'` for an action a person took. `eval_run_completed` is `worker`'s and is
  `system`; `eval_run_interrupted` is Phase 18's.
  **Rejected: shipping `details={}` and recording the loss.** The event would not say which revision or
  which suite version it was about, and A-004's whole argument is that an unrecorded suite edit makes
  past approvals unexplainable.
  — **Reversibility:** cheap to add a key, one-way to remove one — the registry's `detail_keys` is an
  allow-list and rows written against it are never updated.

### Claude's Discretion

Open, not decided. Resolve from the lock file, INT-017, INT-025 and Phase 16's plan set on disk, and
**state the resolution in the plan**:

- **Whether `ReviewSummary` and the nine routes' response models share a module or two.** The summary
  is an in-process type consumed by Python; the routes' are pydantic models consumed by a SPA. Phase
  14 split `schemas.py` from the domain types; whether the per-suite row is one shape or two is open,
  and the argument to make is whether a field added for the screen can reach release-control silently.
- **Where `get_review_summary`'s per-suite rows come from when a suite has several completed runs for
  one revision.** *"Latest completed"* is INT-017's word; whether latest is by `finished_at` or by
  `seq`-like ordering, and what happens to a re-run that completed *before* an earlier run finished, is
  not stated anywhere. `case_flip_total` exists because re-runs of the same revision are expected.
- **How the 120 s p95 is measured and where the test lives.** The lock's `risks` block says the number
  is *"measured against a stubbed provider in load tests and against the real one in the demo, and the
  two numbers are reported separately rather than averaged"*. Load tests are behind `PROPE_RUN_LOAD=1`
  (ORCHESTRATION §3), so a `tests/load/` home means SC1 is not proven by the default gate. Decide, and
  say which run proves the criterion.
- **Whether the four `ManagementAction` members live in `session_auth.py` or wherever Phase 14 moved
  the enum.** 14-01's re-ground list says the home may have moved; follow disk.
- **Whether the advisory ceiling refusal at `POST` is `409` or `402`.** No authority states a status;
  `409` is what INT-025 uses for its (rejected, D-314) concurrency refusal and `402` is the honest one.
  Whichever is chosen, `details` is empty and the response carries no figure (A-056).
- **The error-code names.** They are the client's catalogue keys (ADR-0053) and the set is closed;
  decide whether they extend `call_ledger.schemas.ErrorCode` or evaluation declares its own `StrEnum`,
  and note that `SESSION_REQUIRED` is already valued by reference across module boundaries.
- **How `tests/evaluation/__init__.py` seeds a completed run.** `tests/security/__init__.py` and
  `tests/prompt_registry/__init__.py` are the shape; whether the fixtures drive Phase 16's executor
  against a stub provider or insert `case_result` rows directly changes what SC1 actually proves.

</decisions>

<specs>
## The Concrete Surface

### No new tables. One conditional migration.

This phase owns **no** `evaluation` DDL — Phase 16 creates the four tables, their `workspace_id`
columns, their RLS policies and `evaluation.claim_next_run()`, and shrinks `EXPECTED_ABSENT_SCHEMAS`.

The one migration this phase may create is D-319's, and it is **conditional on disk**:

```sql
-- Only if the four rows still carry an empty detail_keys allow-list.
UPDATE history.history_action_registry
   SET detail_keys = ARRAY['version_id', 'suite_version']
 WHERE action IN ('eval_run_started', 'eval_run_completed', 'eval_run_interrupted');

UPDATE history.history_action_registry
   SET detail_keys = ARRAY['suite_version']
 WHERE action = 'eval_suite_updated';
```

Per-row reasoning: `version_id` and `suite_version` are what `evaluation.lock.yml:94-97` declares the
four events carry; `prompt_id` maps to the `scope_prompt_id` **column** and `actor` to the `actor_id`
**column**, so neither is a details key. `eval_suite_updated` has no `version_id` — a suite edit is not
about a revision, and seeding one would make the allow-list wider than the writer. **Never a
`SECURITY DEFINER` function, never a native enum, and no new table**, so the schema-invariant walk and
ADR-0045's coverage walk both adopt this phase for free.

**Revision numbering:** ORCHESTRATION §4 — run `uv run alembic heads`, use the head as
`down_revision`, take the next integer. Never hardcode. Only one plan per wave may create a revision.

### The nine routes — INT-025

| # | Method | Path | Session | `ManagementAction` | Request | Success | Notable refusals |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/v1/prompts/{prompt_id}/eval-suites` | required | `suite.read` | — | `200` `{suites: [SuiteRead]}` — each at its current version | `404` not-found when the prompt is invisible |
| 2 | POST | `/api/v1/prompts/{prompt_id}/eval-suites` | required | `suite.edit` | `{name, output_modality, cases: [CaseWrite]}` | `201` `SuiteRead` read back, not echoed | `403` naming `suite.edit`; `409` on a duplicate name; `422` on an invalid regex (compiled at save, ADR-0049's security requirement) |
| 3 | GET | `/api/v1/eval-suites/{suite_id}` | required | `suite.read` | — | `200` `SuiteRead` with its cases | `404` when the parent prompt is invisible — resolved in one statement (D-311) |
| 4 | GET | `/api/v1/prompts/{prompt_id}/eval-suites/{name}/versions` | required | `suite.read` | `{name}` percent-decoded once | `200` `{versions: [SuiteVersionRead]}` newest first | `404`; **`OQ-092`** on the path parameter |
| 5 | PUT | `/api/v1/eval-suites/{suite_id}` | required | `suite.edit` | `{output_modality, cases}` | **`201`** `SuiteRead` with the **new** `suite_id` (D-316) | `403`; `422`; never `200` |
| 6 | POST | `/api/v1/prompts/{prompt_id}/eval-runs` | required | `run.start` | `{version_id, suites?: [name]}` | **`202`** `{runs: [{run_id, suite_id, suite_name}]}` — one per suite, `[]` when there are none | ceiling refusal with **no figure** (D-302, status per Discretion); `404`; `403` naming `run.start`. **No `409` for the concurrency bound** (D-314) |
| 7 | GET | `/api/v1/eval-runs/{run_id}` | required | `run.read` | — | `200` `RunRead` — status, the three counts, tokens, cost, `priced_at`. The poll (A-054) | `404` |
| 8 | GET | `/api/v1/eval-runs/{run_id}/cases` | required | `run.read` | cursor page | `200` `{cases: [CaseResultRead], next_cursor}` — outcome, assertion detail, output, usage | `404`. **Phase 18** owns proving no output text leaks for a private prompt |
| 9 | GET | `/api/v1/prompts/{prompt_id}/comparison?candidate={version_id}` | required | `run.read` | query `candidate` | `200` `{suites: [ComparisonBlock], rollup: Rollup}` | `404`; cross-suite-version pairing refused with **both** versions in `details` (D-316) |

Every route: `require_session` as a dependency and `declares_action(...)` as a dependency, both
visible to `assembled_routes(app)`. Every response is an **explicit** pydantic model — never a dict,
never `SELECT *` — which is the habit Phase 15 asserts and a habit with an exception is not one.

### Internal signatures

```python
# src/prope/evaluation/review.py — INT-017, evaluation's only exposed in-process seam.
async def get_review_summary(
    session: AsyncSession, prompt_id: str, version_id: str
) -> ReviewSummary: ...          # raises; never returns a degraded summary (D-306)

def requires_acknowledgement(suites: Sequence[SuiteRow]) -> bool: ...   # pure (D-305)
def roll_up(suites: Sequence[SuiteRow], threshold: Decimal) -> Rollup: ...  # pure (D-308, D-309)

# src/prope/evaluation/cost.py
def compute_cost_delta(candidate: RunTotals | None, baseline: RunTotals | None,
                       had_case_error: bool) -> CostDelta: ...          # pure (D-307, D-318)

# src/prope/evaluation/runs.py
async def submit_runs(session: AsyncSession, *, prompt_id: str, version_id: str,
                      suite_names: Sequence[str] | None, actor_id: str,
                      now: datetime) -> list[StartedRun]: ...           # one transaction (D-313)
async def price_run(sessionmaker, *, run_id: str, workspace_id: str) -> None: ...  # D-317
```

Value objects, all frozen and slotted, in `call_ledger.domain`'s posture:

```python
class WithheldReason(StrEnum):   # closed at six (D-307)
    CASE_ERROR = "case_error"; UNPRICED_ROWS = "unpriced_rows"
    UNKNOWN_USAGE = "unknown_usage"; NO_BASELINE = "no_baseline"
    CURRENCY_MISMATCH = "currency_mismatch"; SUITE_WITHHELD = "suite_withheld"

@dataclass(frozen=True, slots=True)
class CostDelta:
    amount: Decimal | None; currency: str | None; withheld_reason: WithheldReason | None
    # __post_init__ refuses every other combination. Never Decimal(0).

@dataclass(frozen=True, slots=True)
class SuiteRow:
    suite_id: str; suite_name: str; suite_version: int
    pass_count: int; fail_count: int; error_count: int; is_empty: bool
    baseline_run_id: str | None; baseline_completed_at: datetime | None   # shown, never implied
    cost_delta: CostDelta; has_completed_run: bool

@dataclass(frozen=True, slots=True)
class Rollup:
    cost_delta: CostDelta; cost_delta_ratio: Decimal | None
    cost_warning: bool; cost_warning_threshold: Decimal
    requires_acknowledgement: bool

@dataclass(frozen=True, slots=True)
class ReviewSummary:
    prompt_id: str; version_id: str; suites: tuple[SuiteRow, ...]; rollup: Rollup
    # No `unavailable` field. A summary that cannot be assembled raises (D-306).
```

### Consumed seams — the real signatures on disk

| Seam | Call | Notes |
|---|---|---|
| INT-011 | `get_revision(session, version_id) -> Revision \| None` · `get_released_revision(prompt_id)` | Phase 13's `revisions.py`. Frozen dataclass with every column INT-011 names |
| INT-015 | `dispatch(sessionmaker, *, workspace_id, provider_config_id, upstream_model, parameters, messages, stream=False, deadline_ms, priority=Priority.BATCH) -> DispatchResult \| DispatchError` | Returns a **value** on failure, never raises. Gate installed by `worker.py` (D-301) |
| INT-019 | `price_usage(sessionmaker, run_id, usage_rows: Sequence[EvalUsageRow]) -> None` | `EvalUsageRow` has **no body field**; `call_id`, `run_id`, `case_id`, `version_id` all required |
| INT-020 | `check_spend_ceiling(sessionmaker, workspace_id, *, now) -> CeilingDecision` | Two fields, never a figure. Fails open, counted |
| INT-021 | `get_run_totals(sessionmaker, workspace_id, run_id) -> RunTotals` | Takes the workspace (D-20). `cost` is `None`, never `0` |
| INT-001 | `may(session, actor, action, subject) -> bool` | `Subject(type, id, workspace_id, owner_id, access_level)` — supplied by this module |
| INT-006 | `append(session, event: HistoryEventDraft) -> str` | Caller's session, caller's transaction. Raises; the raise is the mechanism |

### Metrics — increment sites only, no eleventh metric

| Metric | Labels | Incremented here |
|---|---|---|
| `prope_evaluation_cost_delta_ratio` | histogram, per suite | **Yes** — only when the delta is not withheld (D-309) |
| `prope_evaluation_run_total` | `status` ∈ `completed\|interrupted\|refused` | **`refused` only** — at the claim-time ceiling refusal (D-302) |
| `prope_call_ledger_ceiling_check_total` | `result` ∈ `allowed\|refused\|failed_open` | call-ledger's; **asserted** here, not incremented (D-303) |
| `prope_evaluation_run_duration_seconds`, `case_duration_seconds`, `case_error_total`, `case_flip_total`, `baseline_reused_total`, `run_interrupted_total`, `run_queue_depth`, `modality_mismatch_total` | — | Phase 16 or Phase 18 |

`suite_name` is author-written text: **a log field, never a metric label** (A-046, ADR-0030's
cardinality rule). Every new log key is added to `LOGGABLE_FIELDS` in `src/prope/observability.py` in
the same change. **Never logged:** prompt body, eval case input, returned content of any modality,
asset URLs, credentials.

### Test files, and what each proves

| File | Proves |
|---|---|
| `tests/integration/test_run_and_compare.py` | **SC1 / EVAL-01 / AC-1** — a 20-case suite run completes and the comparison shows per-case pass/fail for both revisions plus the token and money delta |
| `tests/load/test_suite_run_p95.py` | SC1's **p95 under 120 s** against a stubbed provider with injected latency (`PROPE_RUN_LOAD=1`) |
| `tests/integration/test_multi_suite_submit.py` | **SC2 / EVAL-08 / AC-8** — three suites, three runs, three rows plus a rollup, `requires_acknowledgement` true if any one has a failing case |
| `tests/integration/test_cost_warning_never_blocks.py` | **SC3 / EVAL-05 / AC-5** — `cost_warning` true at `>= +20%`, and no code path anywhere refuses on cost |
| `tests/unit/test_cost_delta_withholding.py` | **SC4** — the rollup withholds its total whenever any suite withheld, and every valid per-suite delta is still returned; and each of the six `WithheldReason`s |
| `tests/unit/test_requires_acknowledgement.py` | D-305 — a failing case, an errored case (not a fail), an empty suite (not a pass), a suite with no completed run (fail-closed) |
| `tests/integration/test_review_summary_contract.py` | INT-017's shape, and that an unassemblable summary **raises** rather than returning empty rows |
| `tests/integration/test_eval_routes_declare_action_and_session.py` | All nine routes appear in `assembled_routes(app)`, each with `declares_session` true and exactly one `declared_action` from the four |
| `tests/security/test_ceiling_refusal_carries_no_figure.py` | The refused branch's **serialized** response and every captured log record contain no spend figure, no limit and no currency (A-056) |
| `tests/security/test_eval_refusals_are_not_found_or_named.py` | D-312 — a nonexistent id and an id in another workspace produce byte-identical responses; a visible prompt with a missing permission produces `403` naming it |
| `tests/integration/test_price_run_is_idempotent.py` | D-317 — pricing a run twice leaves `workspace_spend` unchanged and writes no second `call_record` |
| `tests/integration/test_eval_history_events.py` | D-319 — `eval_suite_updated` and `eval_run_started` land in the same transaction as the state change, carry `version_id` / `suite_version` in `details`, and a rollback leaves neither |

### Canonical references — read before planning

Authoritative and **read-only**. Per ORCHESTRATION §5 and `.planning/BSP-LINK.md`, nothing under
`docs/` may be edited, with the single exception of **creating** an `OQ-NNN` file. Five conflicts are
already known: `OQ-091` through `OQ-095`.

- `docs/modules/evaluation.lock.yml` — `apis.exposes` (the nine routes and `get_review_summary`'s
  paragraph, which is INT-017 in miniature), `apis.consumes` (**five** modules), `inputs` (INT-017 and
  INT-025), `outputs` (the four event names and their declared details), `security_requirements`
  (T-008 through T-011, and the paragraph describing INT-002 that `apis.consumes` does not name),
  `failure_modes` rows 1, 3, 4 and 9, `acceptance_criteria` AC-1, AC-5, AC-8, **and the `OWED TO THE
  STEP-6 SWEEP` comment block, which is where the twice-checked ceiling comes from**
- `docs/architecture/interfaces.md` — **INT-017** (the pull, the two carve-outs, *"never cached"*, and
  the raise-not-degrade failure line), **INT-025** (the nine routes, the `202`, and the `409` D-314
  declines), **INT-011**, **INT-015** (the failure table's evaluation column), **INT-019**, **INT-020**
  (fails open), **INT-021** (the two counts, and no FX)
- `docs/adr/0005-…` — a failing case requires a recorded acknowledgement, not a block; and the split
  that makes `requires_acknowledgement` computed here and enforced there
- `docs/adr/0004-…` — one run measures one revision; the baseline is reused and pinned by identity
- `docs/adr/0006-…` — several named suites per prompt, runs and deltas per suite
- `docs/adr/0019-…` — priced once at write time; why a delta over unpriced rows is not a delta
- `docs/adr/0016-…`, `docs/adr/0046-…` — batch yields to interactive; the caps are per process
- `docs/adr/0049-…` — the claim, `max_concurrent_runs = 2` as a database predicate, and why the broker
  was declined. **D-314's ground**
- `docs/adr/0053-…` — the machine `code` the client translates; no literal display strings
- `docs/brainstorm/open_questions/OQ-009.md` — resolved: warn at `>= +20%`, never block. **D-309's
  ground and `OQ-093`'s subject**
- `.planning/phases/16-*/` — **read the whole plan set on disk before planning.** It is the authority
  on the four tables, the executor, and where D-300's line actually fell
- `.planning/phases/11-*/11-01-PLAN.md`, `11-04-PLAN.md` — `dispatch`'s real signature, `Priority`,
  `DispatchError`, and the batch gate installed in `worker.py`
- `.planning/phases/14-*/14-01-PLAN.md` — D-244 (`ManagementAction` valued from `Action`), D-246 and
  `OQ-078` (the `{prompt_id}` spelling this phase must match), and the route-declaration shape
- `.planning/phases/04-*/deferred-items.md` §5 — the `detail_keys` handover that names this module by
  action, and the `unknown_detail_key` refusal D-319 exists to prevent
- `src/prope/call_ledger/seams.py`, `src/prope/session_auth.py`, `src/prope/observability.py` — the
  three shipped files this phase calls into, in that order of weight

</specs>

<risks>
## What Is Most Likely To Go Wrong

- **Phase 16 draws D-300's line somewhere else, and both phases build the executor or neither does.**
  Phase 16 is planned in parallel and its plan set lands on disk first. **Catch:** every plan in this
  phase opens with a re-ground block that reads `src/prope/evaluation/` and Phase 16's plan set before
  Task 1, and the first plan's Task 1 is an inventory task whose output is a written statement of what
  exists. If the executor already calls `dispatch`, this phase asserts it and says so in the SUMMARY;
  it does not rebuild it. The failure this catches is two implementations of the case loop, which
  would be invisible until `case_flip_total` started moving for no reason.

- **The first `append("eval_run_started", details={"version_id": …})` is refused with
  `unknown_detail_key` and rolls back a submit.** Phase 4 seeded the four `eval_*` rows with an empty
  allow-list *on purpose* and routed the registration to Phase 16 twelve phases in advance. If Phase
  16 did not do it — it appends nothing, so it has no reason to notice — this phase's very first
  integration test fails with a refusal that points at property-history's validator rather than at a
  missing seed row. **Catch:** D-319's verify-then-add contingency, executed **before** the route that
  appends, and a test that asserts the four rows' `detail_keys` are non-empty.

- **A withheld delta is rendered as zero somewhere between the fold and the wire.** `CostDelta.amount`
  is `Decimal | None`; a pydantic response model with `amount: Decimal = 0` or a `or 0` in a serializer
  turns *"we could not price this"* into *"this costs the same"*, which is the single most expensive
  wrong signal this module can produce — it makes an unmeasurable candidate look safe.
  **Catch:** `tests/unit/test_cost_delta_withholding.py` asserts on the **serialized** JSON, not on the
  dataclass, for all six reasons; and `CostDelta.__post_init__` makes the zero-with-no-currency shape
  unconstructible.

- **`requires_acknowledgement` drifts into release-control.** Phase 23 renders the review screen and
  will be tempted to recompute *"does any suite have a failing case"* from the rows it already has,
  because the rows are right there. Two implementations of a boolean whose false value means *no human
  needs to say anything* is the drift nobody sees. **Catch:** INT-017's contract test asserts the field
  is present and non-derivable — the summary carries a suite whose `fail_count` is 0 and whose
  `has_completed_run` is false, so a naive recomputation from the counts gives the opposite answer.
  Recorded for Phase 23 in `deferred-items.md`.

- **Pricing a run twice double-counts a workspace's spend.** `write_records` upserts on `call_id`, so
  the guarantee is entirely in D-317's derivation. A minted-at-pricing-time ULID would make a retry, a
  re-price, or a sweeper's second pass a permanent overstatement on a table nobody may delete from.
  **Catch:** `tests/integration/test_price_run_is_idempotent.py` prices twice and reads
  `ledger.workspace_spend` back through `migrate_engine`, not through the seam that wrote it.

- **The ceiling refusal leaks a figure.** The refusal branch is where the helpful message gets added —
  *"you are over your $200 limit"* — and every part of that sentence is what A-056 withholds. Phase 2
  built `CeilingDecision` with two fields for this reason and asserted the absence over the serialized
  value and the log records. **Catch:** the same test shape, one module further out, over the HTTP
  response body **and** every captured log record on the refusal path.

- **The nine routes collide with prompt-registry's and release-control's under
  `/api/v1/prompts/{prompt_id}/…`.** Five modules now mount there and `OQ-078` records that the path
  parameter is spelled two ways across the authorities. The assertion is about the assembled table and
  cannot run before Phase 23. **Catch:** this phase uses whatever spelling is mounted, records the
  exact nine paths in the SUMMARY, and adds nothing to `OQ-078` beyond a fifth module's worth of rows.

- **SC1's p95 is mostly upstream latency this module does not control**, which the lock names as its
  first risk. A stubbed provider proves the code; a real one proves nothing repeatable. **Catch:** the
  two numbers are measured and reported separately and never averaged, and the plan states which run
  the criterion is ticked against — the Discretion item exists because the honest answer costs a
  decision.

- **A `403` naming a permission is returned where a `404` was owed.** The route-level `may()` call is
  the place the two shapes are chosen, and the choice depends on whether the actor can see the
  *prompt*, not the suite or the run. Getting it backwards on `GET /eval-runs/{run_id}` tells a
  stranger that a run id exists. **Catch:** D-312's test asserts a nonexistent id and a cross-workspace
  id produce byte-identical responses, and D-311's single-statement read makes the correct answer the
  cheap one to write.

</risks>

---

*Phase: 17-seams-nine-routes-the-review-summary-and-four-consumed-modules*
*Decisions consumed: D-300 through D-319. Open questions raised: OQ-091, OQ-092, OQ-093, OQ-094, OQ-095.*
*Context gathered: 2026-08-11*
