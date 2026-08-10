# Phase 5 — Deferred items

Out-of-scope discoveries found while planning, the decisions adopted without confirmation under
`mode: yolo`, the SC → plan and requirement → plan mappings, and the open-question ids this phase
consumed. **Logged, not fixed.** The executor and the verifier append to this file; the planner seeded
it.

Phase 5 runs under the **MINIMAL PROTOCOL** (`.planning/ORCHESTRATION.md` §10a): four plans, no
CONTEXT, no RESEARCH, no PATTERNS, no COVERAGE, and **no critic stage before execution**. The
consequence for this file is that it also carries the planner's own self-check, in §7 — because
nothing else will run it.

---

## 1. Open questions — the allocation, and what each one says

Phase 5's allocated range is **OQ-033 … OQ-036**. **Three are consumed and written; OQ-036 is
allocated, conditional, and expected to stay unwritten.** No id outside the range was touched. The
highest id on disk before this phase was OQ-032.

| id | Raised by | Severity | Conflict, in one line |
|---|---|---|---|
| **OQ-033** | this planner (plan 05-03, D-76) | low | **AC-3 says ten events over a lifecycle that enumerates nine**, and `.planning/ROADMAP.md`'s Phase 5 SC1 repeats the number. Neither names the tenth. Adopted: registration writes **two** events — `property_created` and the `revision_created` of the revision it is registered with — derived from prompt-registry's *"creates the **next** immutable revision"* and from `revision`'s `unique(prompt_id, revision_number)` allocated in the creating transaction. **A derivation, not a reading**: nothing in `docs/` states it |
| **OQ-034** | this planner (plan 05-04, D-80) | low | **Three authorities describe `registered_actions()` three different ways.** `apis.exposes` says three fields and no parameter; INT-008 says four fields and no parameter; ADR-0038's Consequences say it *"continues to read the **table** rather than the cache"* — which needs a connection ADR-0023 forbids the module opening, so **the declared no-parameter signature is not implementable**. Ships as `async def registered_actions(session) -> tuple[RegisteredAction, ...]` with all five columns, a superset of both declared returns |
| **OQ-035** | this planner (plan 05-01, D-66/D-67) | low | **INT-006 declares `append(event) -> void`; what ships is `append(session, event) -> str`.** Three deviations in one seam: the session (forced by ADR-0023 and by INT-006's own transport line), the returned minted `hev_` id (INT-006's *Envelope carries* names ten fields and `id` is not one, and unlike `seq` it is not database-assigned), and the removal of the eleventh draft field Phase 4 added and declared as owed here |
| **OQ-036** | **allocated, not written** | — | Reserved for plan 05-02 Task 3, and **only** if the `EXPLAIN` work finds a declared read shape with no matching index. All three read scopes are expected to match the indexes Phase 4's revision shipped, in which case **the file is not written** and the id returns to the orchestrator for reassignment. An OQ written to use up an allocation is worse than an unused id |

**Two live open questions from earlier phases that Phase 5 leans on and does not resolve.**
`OQ-027` — the vocabulary count written as 30 in six places and 31 in five, **31 adopted** — is the
one number plan 05-04's contract test hardcodes, and the test cites it at the literal. `OQ-032` — the
lock says `bigserial`, the build ships `GENERATED ALWAYS AS IDENTITY` — is untouched: this phase reads
`seq` and never writes it.

---

## 2. Adopted without confirmation — the adjudication list

Three decisions were made on the user's behalf because `mode: yolo` is set and this run does not stop
at blocking checkpoints (`.planning/ORCHESTRATION.md` §6). **Every row belongs in `05-UAT.md` as a
numbered human-verification item and in `.planning/ORCHESTRATION-DECISIONS.md` as one row.**

| # | Decision | Plan | What was adopted, and what was rejected | Reversibility |
|---|---|---|---|---|
| 1 | **D-69** — a registry load failure at process start | 05-01, Task 3 | **The load raises and startup fails**, in both `app`'s lifespan and `worker.run_worker`. Rejected: catching it, logging, and starting without a registry — which converts a transient PostgreSQL outage into a **permanent** one, because ADR-0038 rejects a TTL, a refresh and an invalidation path by name, so every `append()` fails for the life of the process while `/readyz` answers 200. That state pages the module whose alert says every increment is *somebody else's* bug. **Accepted cost: a database that is unreachable at boot becomes a container restart loop rather than a `/readyz` 503**, and the asymmetry against `app.py`'s *"a broker that is not there does not stop this process from serving"* is deliberate | **cheap** — one `try/except` in two files |
| 2 | **D-72** — a scope naming a workspace the session is not in | 05-02, Task 2 | **Refuse, raising `HistoryScopeMismatch`**, and pay for the diagnosis **only on the empty path**: run the page statement first, return rows if there are any, and only when the result is empty read `current_setting('app.workspace_id', true)` to tell a true empty from a mismatch or from a missing tenant. Rejected: returning an empty tuple and letting RLS be the whole answer — an empty Activity is indistinguishable from *nothing has happened to this prompt*, which on the one table A-121 keeps forever is the worst thing a wrong answer can look like, and it leaves the lock's *"cannot construct a cross-workspace read even by supplying the wrong ids"* as a statement about rows rather than about reads. **Accepted cost: a genuinely empty trail pays one extra round trip per render**, and prompt-registry's `/activity` route gains one more exception to translate | **cheap** — one function, one exception class |
| 3 | **D-71** — the cursor's content | 05-02, Task 3 | **The opaque `hev_` event id**, resolved to a `seq` in its own statement, with an unresolvable one raising `HistoryCursorUnknown`. Rejected: `str(seq)` — one fewer round trip, and a cross-tenant volume oracle, because `seq` is a single global identity sequence and a decimal cursor rendered into an Activity URL tells its holder roughly how many events the whole installation has written. Also rejected: resolving it as a scalar subquery inside the page statement, where an unknown id makes the comparison NULL and returns **zero rows silently** | **costly** — the cursor becomes a value in a rendered URL from Phase 15 on |

**None of the three touches a §2 non-negotiable.** All three move toward a named refusal where the
alternative was a silent one, which is the direction ORCHESTRATION §3's *never zero* rule points.

Two further one-way-ish calls were made **without** a checkpoint block, because a checkpoint re-asking
a settled question is not a checkpoint — the posture plan 02-04 took for D-18 and D-20. Both are
recorded here so a reader finds them deliberately: **D-67** (the draft loses `id` and `append()`
returns the minted one — `costly`, five modules are written against it from Phase 7) and **D-68**
(`append()` reads the process cache instead of taking a registry argument — `costly`, same reason).
Both are covered by `OQ-035` and by ADR-0038 respectively, so the record exists in `docs/` as well as
here.

---

## 3. Requirement → plan, and success criterion → plan

Every ROADMAP success criterion for Phase 5 is owned by **exactly one** plan, and every requirement id
appears in **exactly one** plan's `requirements:`.

| ROADMAP SC | Owner | Proven by |
|---|---|---|
| **SC1** — a prompt with a full lifecycle returns all ten of its events in one query in submission order, with nothing from another prompt or another workspace | **05-03** | `tests/integration/test_activity_spans_four_modules_in_one_query.py` — ten events named individually, four decoys each proven present before being proven absent, one statement |
| **SC2** — the registry compared against the union of the five lock files' event lists is the same 31 names, with no extras and no omissions | **05-04** | `tests/contract/test_event_vocabulary_matches_the_locks.py` — derived three ways at run time, compared in both directions and per writing module |
| **SC3** — `read()` is ordered by `seq` descending and never by timestamp, and performs no permission check | **05-02** | `tests/integration/test_history_read_is_ordered_by_seq_not_time.py` (inverted timestamps, and a late-committing lower `seq` across two concurrent transactions) and `tests/architecture/test_property_history_depends_on_nothing.py` (an import walk, so the absent check is structural) |

| Requirement | Owner | Lock-file criterion |
|---|---|---|
| **PH-03** | **05-03** | property-history AC-3 |
| **PH-06** | **05-04** | property-history AC-6 |

**Plan 05-01 owns no success criterion and no requirement, by design.** It is the tracer: it discharges
the seam reshape Phase 4 handed forward (`record_event` → `append`, the eleventh field, the process
cache) and proves one thin end-to-end path. Every criterion in the phase is proven off it, and none of
them is proven *by* it. Plan 05-02 owns SC3 but no requirement id, because `.planning/REQUIREMENTS.md`
maps requirements to lock-file acceptance criteria and SC3 restates a property of the function rather
than one of the module's ACs — the same gap ORCHESTRATION §9a names.

---

## 4. Phase 4's six named obligations — where each one landed

`04-…/deferred-items.md` §5 handed this phase six items. All six are discharged inside the phase.

| Obligation | Discharged by | How |
|---|---|---|
| **`record_event` is a rename target and must not survive as a public name** | 05-01, D-66 | Renamed to `append`, not wrapped. A wrapper was rejected specifically because plan 04-02's own docstring warns that a second call to `check_event` double-counts `append_rejected_total`, and the lock's alert makes every increment a page. `grep -rn "record_event" src/ tests/ alembic/` returning nothing is an acceptance criterion in two plans and at the phase gate |
| **`HistoryEventDraft`'s eleventh field vs INT-006's ten-field envelope** | 05-01, D-67 | The field is dropped; `append()` mints the `hev_` id at the one site that writes and returns it. Raised as `OQ-035` rather than absorbed, with the collision hazard a caller-supplied primary key carries stated in the file |
| **AC-3's arithmetic does not close** | 05-03, D-76 | The tenth event is the `revision_created` registration mints. `OQ-033` carries the derivation, the two rejected readings, and the one-line change if a human rules otherwise |
| **Re-deriving the vocabulary for AC-6 is harder than it reads** | 05-04, D-79 | A structural parse of the leading comma-separated run, not a permissive regex — which both over-extracts (`version_id`, `previous_version_id`, `break_glass`, `set_revision_status`, `scope_prompt_id`, `prompt_grant`, and `access_level_changed`, an action belonging to a different module) and under-extracts (`retired` has no underscore). Verified by the planner against the current files: per-module 5 / 8 / 4 / 4 / 10, union 31, distinct 31. **PyYAML** is pinned in the dev group with its reason (D-78) rather than left to resolve as a transitive of `uvicorn[standard]` |
| **No fixture of the 31 names may be committed** | 05-04 | A prohibition with `verification: command`, plus a grep in the acceptance criteria. The only file in the phase that names individual actions is 05-03's ten-event lifecycle, and it names ten because they are its subject |
| **Assignment order is not commit order** | 05-01 (documented) + 05-02, D-74 (asserted) | `read.py`'s module docstring carries the mechanism and why descending is the safe direction; `tests/integration/test_history_read_is_ordered_by_seq_not_time.py` drives two overlapping transactions through an `AsyncExitStack`, commits the higher `seq` first, and asserts the lower one lands on the next descending page rather than being skipped |

---

## 5. Declared deviations that are **not** raised as open questions

Recorded here so a reviewer finds them deliberately rather than by diff.

- **`read()` returns a bare tuple and the caller derives `next_cursor`.** The lock says
  `read(scope, cursor, limit) -> [event]` and INT-007 says *"cursor-paginated"*, and the two are only
  in tension if the seam computes the cursor. It does not: `src/prope/call_ledger/api.py:528` already
  derives `next_cursor = items[-1].price_row_id if len(items) == page.limit else None` at the HTTP
  edge, and prompt-registry's `/activity` route will do the same with `events[-1].id`. **No deviation
  from the literal return type**, and a page envelope would have been one.
- **`read()` takes the session as its first parameter**, where the lock writes
  `read(scope, cursor, limit)`. Forced by ADR-0023 exactly as `append`'s is, and covered by the same
  reasoning `OQ-035` gives for the write side. Not raised separately, because raising the same forced
  parameter twice would split one question across two files.
- **`ValueError` on a bad `limit`.** D-63's no-`ValueError` rule is about the **append** path, where
  five modules will call from inside code that validates its own request bodies and an
  `except ValueError` around a request body would swallow the audit log's refusal. A read has no such
  hazard, and this repository's value objects already raise `ValueError` from `__post_init__`
  (`seams.EvalUsageRow`, `HistoryEventDraft`). Stated at the guard.
- **`src/prope/property_history/__init__.py`'s "touches neither `app.py` nor `worker.py`" sentence is
  deleted.** Phase 4 wrote it as one of the module's load-bearing absences and D-69 makes it false.
  What replaces it is the absence that survives and is the one PH-07 needs: **no router from this
  package is mounted anywhere**, and both composition roots import exactly two names from it.
  `tests/architecture/test_history_registry_is_installed_at_process_start.py` asserts the imported-name
  set is exactly those two.
- **AC-3's *"in submission order"* against SC3's *"`seq` descending"*.** Both are Phase 5 criteria and
  there is exactly one reading under which both hold: the order **key** is `seq` rather than the clock,
  and the **direction** is descending per INT-007. Plan 05-03's test asserts the returned sequence is
  the exact reverse of the write order, which is equally strong under either reading of the phrase.
  Stated in the test's docstring; **not raised as an OQ**, because the ROADMAP itself contains both
  sentences and a reading that satisfies both is a reading rather than a conflict.
- **`tests/contract/` is a new test package**, created because the lock's AC-6 `test_ref` names
  `tests/contract/test_event_vocabulary_matches_the_locks`. Phase 4 moved AC-5's `test_ref` and recorded
  it; this one is honoured rather than moved.

---

## 6. Handed forward, with a named owner

| Item | Owner | What the owner needs to know |
|---|---|---|
| **Six of the lock's seven metrics do not exist**, including `prope_property_history_read_duration_seconds`, `prope_property_history_events_returned`, `prope_property_history_rows_total` and `prope_property_history_null_scope_prompt_total` | **Phase 6** (the ROADMAP's Phase 6 spec line names `observability_requirements.metrics`) | Two things this phase fixed so Phase 6 does not re-derive them. The **`scope_kind` label vocabulary** is a `KIND` class attribute on each of the three scope dataclasses, with the exact values the lock declares (`prompt`, `target`, `actor`) — read it, do not restate it. And **`prope_property_history_rows_total`'s `workspace_id` label still collides** with the project-wide assertion in `tests/broker/test_publish_confirm_failures.py`; that is `OQ-030`, raised by Phase 4, and it blocks Phase 6 |
| **The behavioural half of `null_scope_prompt`** | **Phase 6** | Plan 05-03's fourth decoy already asserts what the failure *costs*: a `revision_created` whose `target_id` is one of the prompt's own revisions and whose `scope_prompt_id` is null does not appear in the Activity. Phase 6 owns the metric that detects it in production; the behaviour is already pinned |
| **`OQ-033`'s answer has to become a behaviour** | **Phase 13** (prompt-registry) | If registration is built to write only `property_created`, the Activity is short by one from the first prompt onward and plan 05-03's test is wrong in a way nothing else detects. Whichever way `OQ-033` resolves, `POST /api/v1/prompts` must be built to agree with it |
| **The `ActorScope` read has no declared consumer module** | **Phase 6** (AC-9) and whoever adjudicates the module map | INT-007 names three consumers and two of them use `TargetScope`; no module's `outputs` block names *a person's actions* as a screen. It is built because `apis.exposes` declares it and Phase 4 shipped `ix_history_event_workspace_id_actor_id_seq` for it, and because AC-9 — *a removed member's events are still attributed to them* — is unanswerable without it. **An unowned read shape is not a conflict between authorities**, so it is recorded rather than raised |
| **The fourth index has no reader** | **Phase 6 or later** | `ix_history_event_workspace_id_action_seq` is `(workspace_id, action, seq)` **ascending**, shipped for A-126's hand-run Success SQL, and no `read()` scope matches it. That is by design (A-126 says the Success metrics are hand-run at pilot review, not product surfaces) and it is why `OQ-036` is allocated but expected unused |
| **`append(session, event) -> str` is the signature five modules inherit** | **Phases 7, 10, 13, 16, 22** | The registry is **not** a parameter — it comes from the process cache ADR-0038 installs at startup, so a writing module calls `await append(session, HistoryEventDraft(...))` on its own open transaction and holds the returned id if it wants one. Do not thread a registry through a service layer, and do not catch `HistoryAppendRejected` — INT-006 says a caller that catches it has broken the product's central claim |
| **A shared identifier helper for prefixed ULIDs** | **Phase 7** (carried unchanged from Phase 4) | `EVENT_ID_PREFIX = "hev_"` moved from `domain.py` to `append.py` in this phase and is still an inline f-string — the third instance of a pattern written twice before it. Phase 7 adds four prefixes at once. **What it must never become**: a registry mapping types to prefixes, which is the auto-discovery shape D-13 refuses |
| **The A-046 AST gate** | **Phase 6** (carried unchanged from Phase 4) | Still owed, still red on arrival until `request_id` joins `LOGGABLE_FIELDS`, still blind to dynamically-built payloads |
| **Each writing module registers its own `detail_keys`** | **Phases 10, 13, 16, 22** (carried unchanged from Phase 4) | Twenty-nine of thirty-one actions ship with an empty allow-list. `OQ-029` carries the obligation, and Phase 16 writing `eval_run_started` with `details={"version_id": …}` against the current seed is refused with `unknown_detail_key` |
| **`app` and `worker` now fail to start when PostgreSQL is unreachable** | **the deployment work, whichever phase owns it** | D-69's accepted cost. Compose's restart policy is the whole recovery, and `/readyz` is never reached. If the answer to the UAT item is *retry instead*, the change is a bounded retry around one `await` in two files |
| **`pyyaml==6.0.3` joins the dev group** | **the orchestrator, at phase close** | First dependency added since Phase 2. `uv.lock` must show no other pin moving; plan 05-04 asserts the diff |
| **`tests/property_history/load_registry` may be deleted** | **plan 05-01's executor**, reported in its SUMMARY | It exists because Phase 4's `record_event` took a registry argument. After D-68 it may have zero call sites, in which case it is dead code ruff will not flag |

---

## 7. The planner's own self-check

The critic stage is deleted for Phases 5–24 (ORCHESTRATION §10a). These five checks were run by this
planner against its own output, and each is stated here because nothing else will run it. **All five
are agent judgements from reading files and running greps — no detector exists in this environment and
none was fabricated.**

1. **Every ROADMAP success criterion is owned by exactly one plan.** §3's first table. SC1 → 05-03,
   SC2 → 05-04, SC3 → 05-02. 05-01 owns none and says so in its objective.
2. **Every requirement id appears in exactly one plan's `requirements:`.** PH-03 in 05-03, PH-06 in
   05-04; 05-01 and 05-02 carry `requirements: []`. Verified by grep across the four frontmatter
   blocks.
3. **Every file named in a task's `<action>` or `<files>` appears in that plan's `files_modified`.**
   Checked mechanically: every `src/…`, `tests/…`, `alembic/…`, `docs/…`, `pyproject.toml` and
   `uv.lock` token inside an `<action>` or `<files>` block was extracted and diffed against the
   declaration. The residue is **read-only references only** — precedent citations
   (`src/prope/call_ledger/api.py`, `tests/security/test_tenant_isolation.py`,
   `tests/integration/_asgi.py`), forward references to a file a *later* plan in this phase writes,
   and the three OQ files, which are `<reads_only>` by design. **Three files were added to 05-01's
   declaration defensively** — `tests/integration/test_health_and_readiness.py`,
   `tests/integration/test_worker_jobs.py` and `tests/broker/test_handoff_shutdown_drain.py` — because
   D-69 adds a startup step to the two composition paths those three drive. All three are expected to
   stay green untouched; the declaration exists so the executor is never choosing between writing
   outside its declaration and leaving a red test.
4. **Every symbol, fixture, constant and file the plans tell an executor to extend actually exists**,
   or is created by an earlier plan in this phase, or by Phase 4. Verified by reading:
   `workspace_transaction`, `app_sessionmaker`, `app_engine`, `migrate_engine`, `build_sessionmaker`,
   `WORKSPACE_A` / `WORKSPACE_B` / `DAY_1` (`tests/unit/__init__.py:29,30,49`), `LOGGABLE_FIELDS`,
   `reset_handoff`, `supervise`, `declare_topology`, `run_worker`, `lifespan`, `_start_publisher`,
   `ALLOWED` in `test_no_sql_interpolation.py`, `next_cursor` at `call_ledger/api.py:528`,
   `PageRequest`'s 50/200 at `call_ledger/schemas.py:189`, and `tests/unit/test_retention_argument_guards.py`.
   From Phase 4's plans: `HistoryEventDraft`, `RegisteredAction`, `RejectionReason`, `ActorType`,
   `HistoryAppendRejected`, `check_event`, `INSERT_HISTORY_EVENT`, `LOAD_REGISTRY`,
   `load_action_registry`, `history_event_values`, `truncate_owned_tables`, the four index names, and
   `fk_history_event_action`. **Phase 4 has not executed**, so every one of those is a plan-level
   promise rather than a file on disk — which is why each of the four plans opens with a *re-ground
   before you write* instruction naming the tree as the authority when the two disagree.
5. **No plan hardcodes an Alembic `down_revision`** (this phase adds no revision at all, and the phase
   gate asserts `git status --porcelain alembic/` is empty), **none gates on `ruff format --check`**
   (each names it as explicitly not a gate), **none references a `gsd-core` path**, and **the
   whole-suite `uv run pytest -q` appears only in plan 05-04**, which is the phase's last plan and
   carries the gate. Verified by grep across the four files.

**One thing this planner could not check.** Phases 3 and 4 execute before this phase and both were
planned, not built. Every claim in these four plans about `src/prope/property_history/` is a claim
about **Phase 4's plans**, not about code. The compensating control is the *re-ground* paragraph in
each plan's `<context>` and the instruction in 05-01 Task 2 that the output of
`grep -rn "record_event" src/ tests/ alembic/` — and not this phase's `files_modified` list — is the
authority on which call sites exist.

---

## 8. `D-NN` range consumed

**D-66 through D-80**, continuous and fully consumed. Numbering continues across the project and never
restarts (phase 1: D-01…D-08, phase 2: D-09…D-25, phase 3: D-26…D-45, phase 4: D-46…D-65). **Phase 6
starts at D-81.**

| id | Plan | Decision |
|---|---|---|
| D-66 | 05-01 | `record_event` is renamed to `append`, not wrapped by it |
| D-67 | 05-01 | `HistoryEventDraft` loses `id`; `append()` mints and returns it |
| D-68 | 05-01 | `append()` reads the process registry cache; the registry stops being a parameter |
| D-69 | 05-01 | The cache is installed at process start in `app` and `worker`, and a load failure fails startup — **UNCONFIRMED** |
| D-70 | 05-01 | `read()` returns a plain tuple; the caller derives the next cursor |
| D-71 | 05-02 | The cursor is the opaque `hev_` event id, resolved separately, and an unresolvable one raises — **UNCONFIRMED** |
| D-72 | 05-02 | `read()` refuses a scope whose workspace disagrees with the session's tenant, diagnosing only on the empty path — **UNCONFIRMED** |
| D-73 | 05-02 | Three frozen scope dataclasses, one statement each, dispatched with `match` |
| D-74 | 05-02 | The ordering proof is inverted timestamps and interleaved commits, not identical timestamps |
| D-75 | 05-02 | `dependencies: []` becomes an asserted import walk |
| D-76 | 05-03 | AC-3's tenth event is the `revision_created` registration mints |
| D-77 | 05-03 | The decoys are written through `append()`, and one of them is the silent failure |
| D-78 | 05-04 | PyYAML is pinned in the dev group; the lock files are parsed rather than scanned |
| D-79 | 05-04 | The AC-6 derivation is three-way, with the per-module count asserted as well as the set |
| D-80 | 05-04 | `registered_actions()` reads the table, takes a session, and returns all five columns |

---

## 9. Pre-existing, still open, and not this phase's to fix

- **`uv run ruff format --check` fails repo-wide** on the `line-length` disagreement (`ruff.toml` says
  120, the repo is hand-wrapped to ~100). Broken Window #1. Every plan in this phase writes new files
  in the house ~100 style, lists `ruff check` as its gate, and **does not list `ruff format --check`**,
  which is unsatisfiable without a repo-wide decision nobody has made.
- **`request_id` is logged and is not in `LOGGABLE_FIELDS`** (`src/prope/call_ledger/schemas.py:442`).
  Recorded as a Broken Window by Phase 4. This phase adds no log field and reads the allow-list only
  through Phase 4's existing marker test.
- **The root `Dockerfile` and `docker-compose.yml` are boilerplate from another project.** Unchanged
  since Phase 2, and repeated here in one line only so a planner reading this repo finds them known.
  D-69's restart-loop consequence lands on whichever phase eventually owns them.
