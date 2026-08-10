# Phase 6 — Deferred items

Out-of-scope discoveries found while planning, the decisions adopted without confirmation under
`mode: yolo`, the coverage mapping, and the open-question ids this phase consumed. **Logged, not
fixed.** The executor and the verifier append to this file; the planner seeded it.

Phase 6 runs under **ORCHESTRATION §10a, the MINIMAL PROTOCOL**: plans, summaries, verification, and
this file. There is no CONTEXT, RESEARCH, PATTERNS, DISCUSSION-LOG, COVERAGE or plan critique, and **no
critic reviewed the plans before execution.** The planner's self-checks are §7 below and are the only
pre-execution check this phase received.

**This phase CLOSES milestone M2**, so ORCHESTRATION §9a applies: the lock file's
`acceptance_criteria` and `test_plan` blocks are walked clause by clause and each is either asserted or
routed with a named owner. Those two tables live in `06-06-PLAN.md`'s `<verification>` section and are
reproduced in §5 below.

---

## 1. Plans, waves, and what each carries

| Plan | Wave | Requirements | Carries |
|---|---|---|---|
| `06-01` | 1 | **PH-01** | Tracer. AC-1 atomicity, proven against a real child process killed from outside at four announced points and twelve jittered instants inside the commit. Builds `tests/chaos/`. |
| `06-02` | 2 | **PH-07** | AC-7. No route resolves to property-history, no history path at any version, no web framework in the package at any depth, plus two mutation controls proving the detectors can fire. |
| `06-03` | 2 | **PH-08** | AC-8. The A-046 AST source gate over all of `src/prope/`, the whole-row corpus scan, the `reason` blast-radius bounds, and the cross-workspace read refusal. Closes the `request_id` Broken Window. |
| `06-04` | 2 | **PH-09**, **PH-10** | AC-9 and AC-10. Attribution survives a tombstone, nothing is deleted, no expiry column exists, no deletion path exists in source and no history job is composed. |
| `06-05` | 3 | — | The seven declared metrics plus an eighth, the `prompt_scoped` registry column, the three alerts. Consumes OQ-030's resolution and raises OQ-037, OQ-038, OQ-039. |
| `06-06` | 4 | — | Milestone close. The two remaining `test_plan.chaos` clauses, the reconciliation query, both load targets, the §9a audit, and the whole-suite gate. |

**Waves express correctness ordering, not concurrency** — execution is serial regardless
(ORCHESTRATION §7). Wave 2's three plans have provably disjoint `files_modified`; the fact is recorded
in `06-03`'s frontmatter because it is the only wave where disjointness could have been violated.

**Two plans carry `requirements: []`, and that is a fact about `REQUIREMENTS.md` rather than about the
work.** The ROADMAP Spec line for this phase names `observability_requirements.metrics` (seven
metrics), `alerts`, `failure_modes` (all seven rows) and `test_plan` explicitly, and **none of the 89
requirements is written against observability, chaos or load** — so there is no id for `06-05` or
`06-06` to claim. Phase 3's plan 03-04 recorded exactly the same thing for exactly the same reason.

---

## 2. ROADMAP success criteria → plan (each owned by exactly one)

| SC | Statement | Owner |
|---|---|---|
| **SC1** | Killing the process between a release row and its history event at several interleavings leaves either both or neither | **06-01** |
| **SC2** | Enumerating the assembled route table finds no route resolving to property-history and no `/api/v1/history` path at any version | **06-02** |
| **SC3** | Inspecting every field of every event in a full pilot dataset finds no prompt body, fallback answer, credential, password hash, eval output or variable value | **06-03** |
| **SC4** | A removed member's `actor_id` is unchanged on every event they wrote, and no expiry job exists | **06-04** |

**Verified: four criteria, four owners, no criterion claimed twice and none unclaimed.**

## Requirement → plan (each in exactly one plan's `requirements:`)

| Requirement | Lock AC | Owner |
|---|---|---|
| **PH-01** | AC-1 | `06-01` |
| **PH-07** | AC-7 | `06-02` |
| **PH-08** | AC-8 | `06-03` |
| **PH-09** | AC-9 | `06-04` |
| **PH-10** | AC-10 | `06-04` |

**Verified: five requirements, five appearances, no duplicates.**

---

## 3. Adopted without confirmation — the adjudication list

`mode: yolo` is set and this orchestration does not stop at blocking checkpoints (ORCHESTRATION §6,
§10a). **Every row belongs in the phase UAT as a numbered human-verification item and in
`.planning/ORCHESTRATION-DECISIONS.md` as one row.**

| # | Decision | Plan | What was adopted, and what was rejected | Reversibility |
|---|---|---|---|---|
| 1 | **D-81** | 06-01 | `ledger.workspace_retention` as the stand-in state-change row for AC-1's release row. Rejected: a second `history_event` row (does not cross a table boundary, so it cannot catch an `append()` that took its own connection while the state change stayed on the caller's), a test-only table (an undeclared table in a walked schema, or a ninth schema `EXPECTED_ABSENT_SCHEMAS` would flag), and `ledger.call_record` (pricing machinery would make the fixture four-fifths about call-ledger) | cheap |
| 2 | **D-82** | 06-01 | A real child process killed from outside at an announced point, via `subprocess.Popen` + `Popen.kill()`. Rejected: `os._exit()` in the child (chooses its own instant, and the instants it can choose are the easy ones), monkeypatching `commit` to raise (asserts the injection, and an exception is catchable where a kill is not), and `pg_terminate_backend` alone (kills the server side; the client survives and gets a handleable error) | cheap |
| 3 | **D-83** | 06-01 | The commit-window interleaving asserted as a **disjunction over twelve jittered repeats** with a fixed seed, rather than at one fixed point with one expected outcome. Rejected: demanding a specific outcome for a kill during `COMMIT` (there is none, and that is the property), and skipping the window (it is the only interleaving where both outcomes are reachable, so the only one where AC-1's "either both or neither" is a claim) | cheap |
| 4 | **D-84** | 06-02 | AC-7 lands in `tests/security/test_property_history_mounts_no_route.py` — the lock's own `test_ref` — and `tests/architecture/test_route_table.py` is **not** edited. Rejected: adding the negative assertions to the route-table module, whose `EXPECTED_ROUTES` literal moves every phase, so the negative assertion's neighbours change under it | cheap |
| 5 | **D-85** | 06-02 | The framework-absence check is an AST walk **plus** a fresh-interpreter subprocess import asserting `fastapi` never enters `sys.modules`. Rejected: the AST walk alone (sees direct imports; the lock's claim is *"at no depth"*), and an in-process `sys.modules` check (`fastapi` is already imported by another test module, so the result depends on collection order) | cheap |
| 6 | **D-86** | 06-03 | `request_id` joins `LOGGABLE_FIELDS`. Rejected: an `ALLOWED` entry for `schemas.py:442` (an exception for a plain identifier is how an allow-list becomes a file of exceptions), and deleting the keyword (that deletes ADR-0003's correlation id, which is the whole usefulness of the envelope carrying one) | cheap |
| 7 | **D-87** | 06-03 | The A-046 gate walks the source and **refuses** the `**splat` form rather than ignoring it. Rejected: a runtime capture alone (Phase 4 already ships that half; it proves what the test happened to call, and the branches that leak are the ones nobody ran), and documenting the blind spot (a documented blind spot is a blind spot; zero call sites use the form today, so refusing it costs nothing now) | cheap |
| 8 | **D-88** | 06-03 | AC-8's *"full pilot dataset"* is read as a **synthetic corpus of one event per registered action with every allowed detail key populated**, plus each forbidden class offered and refused. Rejected: waiting for a real pilot dataset (A-020 forbids real corporate prompts until OQ-006 and OQ-013 are answered, so the literal precondition cannot exist before the pilot), and sampling (31 rows) | cheap |
| 9 | **D-89** | 06-04 | PH-09 asserted as the tombstone's module-side half — *nothing here changes* — plus a source gate. Rejected: deferring to Phase 7 (PH-09 is this phase's requirement), and creating an `access.user` stand-in table (`access` is in `EXPECTED_ABSENT_SCHEMAS`) | cheap |
| 10 | **D-90** | 06-04 | *"No expiry job exists"* asserted as a **source and composition** property. Rejected: running the worker and asserting rows survive (proves only that no job ran during the test window), and relying on the `prope_app` privilege alone (a `DELETE` in a migration or a job running as `prope_migrate` satisfies the privilege and violates AC-10) | cheap |
| 11 | **D-91** | 06-05 | **OQ-030 resolved: `prope_property_history_rows_total` ships UNLABELLED**, against the lock file's declared `labels: workspace_id`. Rejected: keeping the label and narrowing `tests/broker/test_publish_confirm_failures.py`'s project-wide walk, which would amend ADR-0030 from inside a plan and remove the only control keeping the metric set bounded as seven more modules land. This is OQ-030's own recommendation. **Full `checkpoint:decision` block with both options is in `06-05-PLAN.md`'s objective** | **costly** — a metric's label set is its identity to Prometheus; adding one later starts a new series, removing one later discards the per-tenant history that motivated it |
| 12 | **D-92** | 06-05 | `prompt_scoped boolean NOT NULL` added to `history.history_action_registry` by an additive migration, seeded **19 true / 12 false**, default dropped afterwards. Rejected: deriving it in Python from `target_type` (which is literally *"a list in code"*, the thing `failure_modes` row 3's mitigation rejects by name, and would rest on the `target_type` set OQ-029 records as declared-closed-and-enumerated-nowhere), and dropping `null_scope_prompt_total` with its alert | cheap to drop; **a wrong per-action value is silent** — the guard never trips and the counter that would have said so stays at zero |
| 13 | **D-93** | 06-05 | An **eighth** metric, `prope_property_history_append_failed_total`, because `alerts` declares `PropertyHistoryWriteFailure` and `metrics` declares no series that counts an append error. Rejected: dropping the alert, and rewording it against `rate(append_total)` (an audit log stopped because nothing is happening looks identical to one stopped because every write fails, and the two need opposite responses). Same resolution Phase 2 gave OQ-022's DLQ-depth gauge | cheap |
| 14 | **D-94** | 06-06 | The load target ships as a **default-running proxy plus a marked, skipped full-duration run**, reusing Phase 3's registered `load` marker. Rejected: the ten-minute run in the default suite (two hours of wall time across eighteen remaining phases), `addopts = "-m 'not load'"` (redefines what `uv run pytest -q` — literally §9's gate — covers), and no proxy at all (a performance criterion proven only by a test nobody runs) | cheap |
| 15 | **D-95** | 06-06 | The reconciliation query ships **now**, with one writer's stand-in operation and its coverage stated, proven by a deliberately omitted append. Rejected: deferring it to Phase 23 (the lock calls it *"the only automated defence against the silent-omission failure mode"*, and deferring leaves Phases 8, 14 and 17 to invent three versions), and writing it as a generic cross-module query today (it would have to guess four modules' table shapes) | cheap |

**None of the fifteen touches a §2 non-negotiable.** D-91 and D-93 are the two worth a human's
attention: both are deviations from a lock file's `observability_requirements` block, both are recorded
as open questions rather than as spec edits, and **D-91 is the only `costly` reversibility rating in
the phase.**

---

## 4. Open questions consumed

Phase 6's allocated range is **OQ-037 … OQ-040**. **Three consumed, one unused.** Highest id on disk
before this phase was OQ-032; OQ-033 … OQ-036 belong to the four planners running in parallel with this
one.

| id | Raised by | Severity | Conflict, in one line |
|---|---|---|---|
| **OQ-037** | `06-05` planning | medium | `prope_property_history_rows_total` is declared as a gauge that **no role available to the running process can compute**: unlabelled needs a cross-workspace read ADR-0035 refuses `prope_app` (it returns zero rows, so the gauge would read 0 forever), labelled needs an enumerator that arrives with `access.list_workspaces()` in Phase 7, `prope_report` is a hand-run credential not held by a process, and a fifth `SECURITY DEFINER` function is refused. **Independent of OQ-030 and survives either answer to it.** Phase 6 ships the declaration unset and routes the setter to Phase 8 |
| **OQ-038** | `06-05` planning | medium | `failure_modes` row 3's mitigation says *"The registry records which actions are prompt-scoped"*; `data.owns` lists the registry's fields as five and none of them is that one. The metric and alert that detect the module's **only silent-by-nature failure** both depend on it. Phase 6 adds the column and records the INT-008 return-shape widening it implies |
| **OQ-039** | `06-05` planning | medium | `alerts` declares **PropertyHistoryWriteFailure** — *"append errors excluding rejections"* — and `metrics` declares no series that counts them; `append_rejected_total` counts exactly what the alert excludes and its `reason` set is closed at three. **Second instance of OQ-022's shape**, which is itself the finding. Phase 6 ships an eighth metric and notes the ROADMAP's *"7 metrics"* line now reads eight |
| **OQ-040** | — | — | **Unused.** Available to a later phase or to the orchestrator |

**OQ-030 is resolved by this phase, not re-raised.** It was written by Phase 4 planning, says in its own
words that it *blocks Phase 6*, and D-91 adopts its own recommendation. **The file is not edited** —
`docs/` is read-only apart from creating an OQ, and a phase editing another phase's open question to
record its own answer is how a question stops looking open.

---

## 5. The §9a milestone audit — what is asserted and what is routed

Reproduced from `06-06-PLAN.md`'s `<verification>`, because the orchestrator reads this file.

### `acceptance_criteria`

Asserted in Phase 6: **AC-1** (06-01), **AC-7** (06-02), **AC-8** (06-03), **AC-9** and **AC-10**
(06-04). Asserted in Phase 4: **AC-2**, **AC-4**, **AC-5** — with AC-2 re-exercised here for a departed
actor's rows and AC-5 made concurrent in 06-06. Owned by Phase 5: **AC-3** and **AC-6**.

### `test_plan` — the clauses this phase does **not** assert, with named owners

| Clause | Why not here | Owner |
|---|---|---|
| `test_plan.e2e` — one prompt through its whole life across four modules | prompt-registry, evaluation, release-control and the gateway do not exist. This is the module's *"actual acceptance test"* and the only place all four feature modules' outputs are asserted together | **Phase 24** |
| `test_plan.integration` — atomicity of **each** of the five writing modules' state changes with its event | Phase 6 proves the shape with a stand-in (06-01); the five real writers arrive later | **Phases 8, 14, 17, 23** |
| `test_plan.integration` — cursor pagination stable across concurrent appends | `read()`'s cursor is Phase 5's. **If Phase 5 did not assert it, this clause is unowned** and Phase 6 is the last phase in the milestone that could have said so — `06-06`'s SUMMARY is required to state which it is | **Phase 5, verify at the gate** |
| `test_plan.contract` — `append()`, `read()`, `registered_actions()` | The three seams are Phase 5's. The *"append uses the caller's transaction"* half is asserted from outside the process in 06-01 Task 3 | **Phase 5** |
| AC-3's arithmetic — the lock and Phase 5's SC1 both say *"all ten events"* over a lifecycle enumerating **nine** | Handed to Phase 5 by Phase 4's `deferred-items.md`; not this phase's AC | **Phase 5** |
| AC-7's cross-module form — the assembled table with all eight modules mounted | PITFALLS §5: the assembled-table assertions *"cannot actually run until every module is mounted — i.e. not before phase 23"*. Phase 6 ships the single-module form over `assembled_routes` so Phase 23 widens rather than replaces | **Phase 23** |
| AC-9's call site — access-control writing one `user_tombstoned` event per workspace | Phase 8's SC4 already states it. Phase 6 asserts the property of *its own rows* | **Phase 8** |
| `rows_total`'s setter | OQ-037. Needs `access.list_workspaces()` | **Phase 8** |

**PITFALLS gaps 1 and 2 were read and contain no property-history entry.** No acceptance criterion is
owed to this module that was never written as a row, and none of its criteria asserts against
infrastructure a later decision replaced. Recorded because the absence is itself a check.

---

## 6. Declared deviations that are **not** raised as open questions

Recorded so a reviewer finds them deliberately rather than by diff.

- **AC-8's *"full pilot dataset"* is a synthetic corpus** (D-88). Not an OQ, because **A-020 is the
  spec** — no real corporate prompts until OQ-006 and OQ-013 are answered — so the literal reading is
  unsatisfiable by the spec's own choice rather than by a disagreement with it. The corpus covers one
  event per registered action with every allowed detail key populated, which is a larger surface than
  a pilot dataset would contain. **The pilot is where it becomes real.**
- **AC-1's release row is a stand-in** (D-81). Not an OQ: release-control is Phase 22 and the ROADMAP
  says so. The plan and the test both name Phase 23/24.
- **AC-9's and AC-10's operations are stood in for by their registered events.** Same argument;
  `user_tombstoned`, `retired` and `api_key_revoked` are all in the seeded 31-name vocabulary today.
- **`test_plan.load`'s ten-minute duration runs once, not at every gate** (D-94). The proxy that runs
  at every gate reproduces the rate and the concurrent read mix but not the duration or the
  50,000-row table, and the plan says so at the constants rather than letting the proxy imply
  otherwise.
- **The ROADMAP's *"7 metrics"* Spec line now reads eight.** OQ-039 carries it. Flagged here as well
  because an auditor counting metrics against the ROADMAP will find the discrepancy before they find
  the OQ.
- **`registered_actions()` may now return a fifth key.** If Phase 5's implementation returns
  `RegisteredAction` instances or their `asdict`, `prompt_scoped` appears in INT-008's output, whose
  declared return names four. Recorded in OQ-038; **`registered_actions()` must not be narrowed to
  hide it.** Phase 5's AC-6 test compares action *names* and is unaffected.

---

## 7. Planner self-check — the checks the deleted critic stage would have made

No exec-critic and no spec-critic reviewed these plans (ORCHESTRATION §10a). The planner ran the
following itself. **Every one is an agent judgement from reading the files — no detector exists in this
environment and none of this is detector output.**

1. **Every ROADMAP success criterion is owned by exactly one plan.** §2's first table. Four criteria,
   four owners, none doubled, none missing.
2. **Every requirement id appears in exactly one plan's `requirements:`.** §2's second table. PH-01,
   PH-07, PH-08, PH-09, PH-10 — five ids, five appearances. `06-05` and `06-06` carry `[]` deliberately,
   with the reason in §1.
3. **`files_modified` is exhaustive in every plan.** Each plan's task `<files>` lists and every path
   named in a task's `<action>` prose were read back against the frontmatter, line by line. Findings
   corrected during planning: `06-05` declares `tests/integration/test_migration_chain.py` and
   `tests/integration/test_history_schema_ships_its_guarantees.py` as **conditional** edits with the
   condition stated in the frontmatter comment; `06-06` declares `Makefile` and `pyproject.toml` the
   same way; `06-03` declares `.planning/WINDOWS.md` because Task 1 closes a Broken Window there.
   **Read-only references are not declared** — `06-02` names `src/prope/app.py` and
   `tests/architecture/test_route_table.py` and asserts both are untouched, and `06-03` names
   `src/prope/call_ledger/schemas.py` while D-86 explicitly refuses to edit it.
4. **Every symbol, fixture, constant and file the plans tell an executor to extend was grepped for.**
   Confirmed present today: `workspace_transaction`, `SET_TENANT`, `build_engine(url, **kwargs)`,
   `build_sessionmaker`, `LOGGABLE_FIELDS`, `configure_logging`, `assembled_routes`, `declared_action`,
   `declares_session`, `MANAGEMENT_ACTIONS`, `JOB_CALL_RECORD_DRAIN`, `JOB_EXPIRED_BODY_DELETION`,
   `supervise`, `interval_job`, `ObservedWorkspaces`, `delete_expired_bodies`, `migrate_engine`,
   `app_sessionmaker`, `postgres_container`, `_role_url`, `TEST_ROLE_PASSWORDS`,
   `ledger.workspace_retention` and its **four** columns with `prope_app` holding SELECT/INSERT/UPDATE,
   `grant_table`, `enable_tenant_rls`, `assume_migrate_role`, `reset_role`. **Two corrections made
   during planning:** the retention writer is `set_retention_window`, not `write_retention_window`
   (`06-01` corrected); and `ledger.workspace_retention` carries a fourth `NOT NULL` column,
   `updated_by`, which the stand-in `INSERT` must name (`06-01` corrected, with the DDL cited so the
   executor checks rather than trusts the snippet).
   Created by phases that execute first: `tests/load/__init__.py`, the `load` pytest marker,
   the `Makefile` `load` target, `deploy/prometheus/rules/`, `tests/architecture/test_alert_rules.py`
   and `pyyaml==6.0.3` (**Phase 3**); the whole `src/prope/property_history/` package,
   `tests/property_history/__init__.py` and its helpers, both `history` tables and the 31-row seed
   (**Phase 4**).
   **The one live risk is §8's first row: Phase 5's `read()`.**
5. **No plan hardcodes an Alembic `down_revision`** — `06-05`'s migration is named
   `000N_history_registry_prompt_scoped.py` with the placeholder stated in the frontmatter and a
   prohibition against hardcoding. **No plan gates on `ruff format --check`** — grepped, zero
   occurrences. **No plan references a `gsd-core` path** — grepped, zero occurrences. **No per-plan
   `<verify><automated>` block runs the whole suite** — every one names its own targeted tests or a
   single directory; `uv run pytest -q` appears only in `06-06`, the last plan, in its
   `<verification>` section and its final task's acceptance criteria.

---

## 8. Risks the executor must know before it starts

| Risk | Why it matters | What to do |
|---|---|---|
| **Phase 5's `read()` shape is unknown to this planner.** `06-03` Task 4 and `06-05` Task 3 both call it, and `06-05` declares `src/prope/property_history/read.py` in `files_modified` | Phase 5 was being planned **concurrently** with Phase 6 by a different agent. Its module name, its scope-argument shape (dataclass, keyword set, or three functions) and whether it takes an `AsyncSession` are all Phase 5's to decide | **Re-ground against the tree first** (ORCHESTRATION §7). Put the histogram wrapping in whatever module `read()` actually lives in, report the difference as drift in the SUMMARY, and do **not** create a second module to hold a metric |
| **Phase 5 renames or wraps `record_event` as `append()`** (Phase 4 `deferred-items.md` §5, D-64) | Every plan in this phase calls the module's public write path. `06-05` adds counters to it, and instrumenting **both** the wrapper and the inner function would double-count | Use whichever public name Phase 5 left. If both exist, use `append()`, instrument it **once**, and report the pair as drift |
| **`06-05`'s migration moves a Phase 4 table** | `history_action_registry` is seeded by Phase 4 and its column set may be asserted by `test_history_schema_ships_its_guarantees.py` and snapshotted by `test_migration_chain.py`. Phase 4's own `deferred-items.md` §4 records that the chain test goes **blind** rather than red when it is under-scoped | Check both files before assuming neither needs editing, and say which in the SUMMARY |
| **`06-06` Task 1 revokes a privilege on a session-scoped container** | A leaked `REVOKE` reddens every test that runs after it, in other modules' files, with a permission error that reads as unrelated — the hardest failure in this repository to attribute | The re-grant is in a `finally` **and** is asserted with `has_table_privilege` afterwards, and a third test raises inside the block on purpose to exercise that path. Do not simplify any of the three away |
| **`06-01` starts child processes and kills them** | On this Windows host `Popen.kill()` is `TerminateProcess`. The PostgreSQL backend does not notice the dead client until its next read, and a count taken in that window reads the **pre-abort** state | Every assertion waits on `pg_stat_activity` for the child's `application_name` to disappear first. That poll is the single most deletable line in the module and deleting it turns it into a fast, flaky green |
| **`06-03`'s AST gate goes RED ON ARRIVAL** | Phase 4 predicted it: `src/prope/call_ledger/schemas.py:442` logs `request_id=` and the name is not in `LOGGABLE_FIELDS` | Expected. Confirm the red **before** adding the name, so the gate is proven to do something. If it is *not* red, something changed and that is the finding |
| **Phase 3 changes `src/prope/observability.py` and `tests/architecture/test_route_table.py` before this phase runs** | `06-03` edits the first; `06-02` asserts against the second and must not edit it | Phase 3 executes first, so both are settled by then. `06-03` asserts membership and **never the size** of `LOGGABLE_FIELDS`, precisely so Phase 3's and Phase 7's growth do not redden it |
| **`06-05`'s `19 true / 12 false` `prompt_scoped` split is a planner's derivation from A-119** | A wrong value is silent: the guard never trips and `null_scope_prompt_total` stays at zero, which looks identical to healthy | The migration asserts the two counts sum to the registry's total and that the twelve are exactly the workspace / member / role / key / user and provider actions. If the seeded vocabulary has moved, the arithmetic fails rather than passing quietly |

---

## 9. Pre-existing, still open, and not this phase's to fix

- **`uv run ruff format --check` fails repo-wide** on the `line-length` disagreement (`ruff.toml` says
  120, the repo is hand-wrapped to ~100). Broken Window #1. Every plan here writes new files in the
  house ~100 style, lists `ruff check` as its gate, and **does not list `ruff format --check`**, which
  is unsatisfiable without a repo-wide decision nobody has made.
- **The root `Dockerfile` and `docker-compose.yml` are boilerplate from another project.** Recorded in
  Phase 2's `deferred-items.md`, unchanged, and repeated in one line so a planner reading this repo
  finds them known.
- **The deployment stack owns no milestone** (PITFALLS §4), so
  `deploy/prometheus/rules/property_history.rules.yml` will never be wired into a running Prometheus by
  any phase. It is written anyway, on Phase 3's precedent: the rules are where the thresholds and the
  reasons for them live, and the test beside them is what stops the file rotting.
- **OQ-018 … OQ-021, OQ-022 … OQ-032 remain unresolved.** No phase resolves an open question by editing
  a spec; later phases inherit each deviation as declared.
