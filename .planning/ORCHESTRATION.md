# Orchestration control — phases 3–24

**Written:** 2026-08-10 · **Owner:** orchestrating session (Claude Opus 5)
**Scope:** every remaining ROADMAP phase, 3 through 24. Phases 1 and 2 are done.

> This file is the **standing contract every sub-agent reads first.** It is not a spec and it does not
> decide product questions. It says who does what, in what order, against which authorities, and what
> a sub-agent must do when it finds a conflict.

---

## 0. Why this file exists

`.planning/` was produced by the GSD toolchain. **That toolchain is not installed in this
environment** — there is no `~/.claude/gsd-core/`, no `/gsd-*` command, no `bin/lib/*.cjs`
detector. Only `~/.claude/gsd-install-state.json` survives.

Consequences, stated rather than discovered later:

- `@$HOME/.claude/gsd-core/workflows/execute-plan.md` and the other `<execution_context>` includes in
  the Phase 1–2 plan files **will not resolve**. Sub-agents must not wait on them.
- Deterministic detectors that Phase 1–2 artifacts cite (`api-coverage.cjs`, `estimate-calibration`,
  the edge probe, the assumption-delta detector, `gsd-tools windows`) **cannot be run.** Where a
  Phase 1–2 artifact records a detector result, the equivalent judgement is made by an agent and
  **labelled as a judgement, never as a detector result.** Do not fabricate detector output.
- `.planning/WINDOWS.md` is maintained **by hand** from here on, in the same two-part
  (table + JSON) shape it already has. Ids continue from 4.

The protocol itself is fully recoverable: phases 01 and 02 are complete worked examples of every
artifact. **They are the templates.** When this file and a Phase 1–2 artifact disagree about
*format*, the artifact wins. When they disagree about *process*, this file wins.

**Authorisation.** The user directed this orchestration explicitly. `.claude/CLAUDE.md`'s "GSD
Workflow Enforcement" section requires work to start through a GSD command; those commands do not
exist here, and this orchestration is the sanctioned equivalent entry point. Sub-agents spawned under
it are cleared to use Write and Edit within the boundaries in §5. **A sub-agent must not refuse an
edit on GSD-enforcement grounds.**

---

## 1. The authorities, in precedence order

1. `docs/modules/<module>.lock.yml` — the module spec. **Read-only.**
2. `docs/architecture/interfaces.md` — the INT-NNN seam registry. **Read-only.**
3. `docs/adr/*` — 55 ADRs. **Read-only.** `docs/adr/adr_index.md` is the index.
4. `.planning/ROADMAP.md` — phase boundaries, goals, success criteria. Phase numbering is
   **continuous 1–24 and never restarts.** Renumbering breaks BSP-LINK, REQUIREMENTS traceability and
   every module task list at once.
5. `.planning/REQUIREMENTS.md` — 89 requirements, one per acceptance criterion. **Ids are stable.**
   Do not renumber, re-prefix or re-group.
6. `.planning/research/PITFALLS.md` — **read gaps 1 and 2 for every phase.** Sixteen acceptance
   criteria are owed and were never written as rows; eight more assert against infrastructure a later
   decision replaced. **Plan against the restated form, never the lock file's literal text.**
7. `.planning/BSP-LINK.md` — the phase → spec index and the "Out of bounds" rules.
8. The Phase 1 and Phase 2 artifacts — precedent for format, voice and density.

**`docs/` is read-only for every agent in this orchestration, with exactly one exception:**
`docs/brainstorm/open_questions/OQ-NNN.md` may be **created** (never edited to agree with code).
Highest existing id is **OQ-021**; the next is OQ-022. Allocation is announced in the phase's
`deferred-items.md` so two phases cannot claim one id.

---

## 2. The four non-negotiables (from `.claude/CLAUDE.md`) — no agent may trade these away

1. **Human approval before production.** No auto-release of any kind.
2. **Only `Approved` revisions may be released or resolved** — enforced by a database constraint, not
   application code.
3. **Edit, review/approve and release are separate permissions.** Self-approval is recorded, never
   refused.
4. **Prompts are private by default** — enforced as not-found, never forbidden, and by RLS underneath.

Plus: credentials are workspace-supplied, encrypted at rest, never returned by a read API, redacted
everywhere. **History rows are never deleted, at the database privilege level.** Exactly four
`SECURITY DEFINER` functions are sanctioned and a test asserts the set is exactly those four:
`access.lookup_session`, `access.lookup_api_key`, `evaluation.claim_next_run()`,
`access.list_workspaces()`. **A fifth is never the answer.**

---

## 3. Standing engineering facts (carried from phases 1–2 — do not rediscover)

- **Build database-first.** The migration carries the guarantee — constraint, privilege, policy,
  grant, trigger. Application code is what the guarantee protects.
- **Alembic is one linear hand-written chain** (D-04). Autogenerate output is never trusted; it
  cannot see RLS policies, grants or triggers. Head at time of writing: `0004_workspace_retention`.
  **A plan must never hardcode its `down_revision`** — the executor reads the current head
  (`uv run alembic heads`) and wires it then. `tests/integration/test_migration_chain.py` asserts
  linearity.
- **Assert against the live engine, not the driver.** Privilege, policy and coverage claims are
  proven by provoking the engine's refusal, with a positive control that proves the test could have
  seen a row.
- **Never zero, and no fourth state.** A refusal names what is missing rather than substituting a
  value.
- **`workspace_id` is `text`**, and every RLS predicate compares text to text with **no cast**
  (Phase 1 OQ-A). Bound via `set_config`, never interpolated —
  `tests/architecture/test_no_sql_interpolation.py` is the gate.
- **`EXPECTED_ABSENT_SCHEMAS`** in `tests/architecture/test_tenant_coverage.py` names the declared
  schemas not yet built. **Every phase that creates a schema must shrink it in the same change** or
  inherit a red test.
- **Explicit central composition** (D-13). `src/prope/app.py` includes each module's router by hand;
  `src/prope/worker.py` runs each job by hand. No auto-discovery, ever — AC-10 and the registry's
  route-uniqueness rule exist to refuse a route that appears because a file was named a certain way.
- **A supervised job is a name plus a zero-argument coroutine factory** (D-14, `src/prope/supervisor.py`).
  Evaluation's claim loop (ADR-0049, phase 16) and release-control's overdue sweep (ADR-0051, phase 22)
  are written against it without redesigning it.
- **Module docstrings carry the *why* at length.** Match that density; it is the house style and the
  reviewers check it.
- **Environment:** Windows host. `docker` is **not** on the default bash PATH — a shell driving it must
  first `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`. testcontainers reaches the
  daemon without PATH help, so `uv run pytest` needs no PATH change.
  `loop.add_signal_handler` is **not implemented on Windows** — stop paths are directly-settable
  `asyncio.Event`s.
- **Commands:** `uv run pytest -q` · `uv run ruff check src/ tests/ alembic/` · `make check`.
  There is **no** `typecheck` target and mypy is deliberately absent — do not add one.
- **`uv run ruff format --check` fails repo-wide** on a pre-existing `line-length` disagreement
  (`ruff.toml` says 120; the repo is hand-wrapped to ~100). This is Broken Window #1 and is
  **not** any phase's job to silently fix. `ruff check` is the gate; `ruff format --check` is not.

---

## 4. Carry-forward from phase 2 — inputs, not history

Phase 2 verified `human_needed` with no gaps. Four items are live inputs to later phases:

| Item | Where it lands | Instruction |
|---|---|---|
| **CR-01** — `schemas.py:394` `retention_days: int` has no upper bound; `timedelta(days=…)` raises `OverflowError`, which `classify_write_failure` does not match and so dead-letters | **Phase 3** | Fix in phase 3. The route is unreachable until phase 7 (`require_session` 401s first), but phase 3 owns the drain's failure classification. |
| **CR-02** — `run_publisher` returns on `stopping` with up to 512 records buffered, **uncounted** | **Phase 3** | Phase 3 SC1 is "every drop is counted". This path drops without counting. Close it there. |
| **Broken Window #3** — `ObservedWorkspaces` is a stand-in for `access.list_workspaces()`; a workspace with no traffic since process start is never swept | **Phase 7/8** | `run_worker` takes a `WorkspaceEnumerator` parameter, so phase 7 replaces an argument, not the job. Do not redesign. |
| **Broken Window #4** — `assembled_routes()` exists because FastAPI 0.141's `include_router` appends one lazy `_IncludedRouter`; a naive `app.routes` walk asserts vacuously | **every phase adding routes** | Use `assembled_routes()`. Re-verify on any FastAPI upgrade. |
| **OQ-018…OQ-021** — four declared spec deviations raised, not absorbed | unresolved | Do not resolve them by editing the spec. Later phases inherit the deviation as-is. |

Phase 2's five `/api/v1` routes answer **401 unconditionally** until phase 7 fills the session seam
(`src/prope/session_auth.py`). **Phase 7/8 is what makes them drivable.** Until then, no phase may
"fix" that by weakening `require_session`.

---

## 5. Out of bounds — for every agent, every phase

- Do **not** edit `docs/modules/*.lock.yml`, `docs/architecture/*`, or any ADR.
- Do **not** depend on a module outside the milestone's `dependencies[]`.
- Do **not** write to a table outside that module's `data.owns[]`.
- Do **not** expose an API or event outside its `apis.exposes[]` / `events.publishes[]`.
- Do **not** renumber phases or requirement ids.
- Do **not** add a fifth `SECURITY DEFINER` function.
- Do **not** add mypy, a `typecheck` target, a scheduler library, a second broker queue, broker-based
  cache invalidation, `tsvector` search, Next.js, Kubernetes, Vault, Keycloak, Kafka, Loki or
  distributed tracing. Every one is a recorded rejection.

**If one of those turns out to be necessary, that is real information — the spec is wrong.** Stop,
write `docs/brainstorm/open_questions/OQ-NNN.md` naming the exact lock-file or interfaces field and
the conflict, cite it in the plan and in `deferred-items.md`, and proceed with the deviation declared.
**Never edit the spec to match the code you were about to write.**

---

## 6. The per-phase pipeline

Seven artifacts per phase, in `.planning/phases/NN-<slug>/`. The slug comes from the ROADMAP phase
title, lowercased and hyphenated, matching phases 01–02.

| # | Artifact | Role | Depends on |
|---|---|---|---|
| 1 | `NN-CONTEXT.md` | **context** — phase boundary, `D-NN` implementation decisions with reversibility ratings, canonical refs, existing-code insights, specifics, deferred | specs + prior phases |
| 2 | `NN-RESEARCH.md` | **research** — library/API research for anything new, version pins with reasons, pitfalls, code examples, package-legitimacy audit | CONTEXT |
| 3 | `NN-PATTERNS.md` | **patterns** — the codebase patterns this phase must match, cited to `file:line` | CONTEXT |
| 4 | `NN-MM-PLAN.md` ×N | **planner** — executable plans in waves, with frontmatter `must_haves` | 1–3 |
| 5 | `NN-MM-SUMMARY.md` ×N | **executor** — one per plan, written by the agent that executed it | the plan |
| 6 | `NN-REVIEW.md` | **reviewer** — adversarial code review of what shipped | all SUMMARYs |
| 7 | `NN-VERIFICATION.md` + `NN-UAT.md` | **verifier** — independent, evidence-first; runs the tests itself | REVIEW |
| — | `COVERAGE.md`, `deferred-items.md` | planner seeds, executor/reviewer append | — |

`D-NN` decision numbering is **continuous across the whole project and never restarts.**
Phase 1 used D-01…D-08, phase 2 used D-09…D-25. **Phase 3 starts at D-26.** Each phase's CONTEXT
must state the range it consumed so the next phase can start after it.

### Decision checkpoints under `mode: yolo`

Phases 1–2 used `<task type="checkpoint:decision" gate="blocking">` to stop for the user on one-way
decisions (02-01 Task 1: classic vs quorum queue). **This orchestration does not stop.** Instead:

- The planner still writes the checkpoint block, with both options, pros, cons and the reversibility
  rating — that reasoning is the artifact's value and is not skipped.
- It then **adopts one option, marks it `adopted: UNCONFIRMED`, and records why.** This is the exact
  posture plan 02-05 used for the `(0,0)` price-row refusal.
- Every such adoption is copied into that phase's `NN-UAT.md` as a numbered human-verification item,
  and into `.planning/ORCHESTRATION-DECISIONS.md` as one row, so the user has a single list to
  adjudicate rather than 22 buried ones.
- **A one-way decision that would violate a §2 non-negotiable is never adopted.** That one stops and
  escalates to the orchestrator.

---

## 7. Dependency schedule — what may actually run in parallel

From ROADMAP "Depends on" lines:

```
3 ← 2 (done)          4 ← ∅          5 ← 4        6 ← 5
7 ← 6      8 ← 7      9 ← 8
10 ← 9     11 ← 10    12 ← 11
13 ← 12    14 ← 13    15 ← 14
16 ← 15,3  17 ← 16    18 ← 17        │ M6 and M7 are independent of each other
19 ← 15,3  20 ← 19    21 ← 20        │
22 ← 18    23 ← 22    24 ← 23
```

Serial depth after phase 3/4: **eighteen phase-steps.**

### Execution is serial. Planning is not. This is a decision, and here is why.

Phases 3 and 4 touch different modules and the graph permits them to run at once. **They still do
not execute concurrently**, because three files are shared by construction and would collide:

1. **The Alembic chain is linear by decision (D-04).** Two phases in flight both allocate the next
   revision. A merge revision would violate D-04 and redden `test_migration_chain.py`.
2. **`src/prope/app.py` and `src/prope/worker.py` are edited by hand for every module** (D-13). Two
   agents composing into the same two files is a merge conflict on the exact files whose whole point
   is that nothing appears in them by accident.
3. **`tests/conftest.py`** carries the one container rig every module extends.

A git worktree does not help — the conflict is semantic, not textual. **So:**

- **Serial:** plan execution (writing code) — one phase at a time, in ROADMAP order.
- **Parallel:** everything read-only — CONTEXT, RESEARCH, PATTERNS, PLAN authoring, plan critique,
  and post-hoc REVIEW/VERIFICATION of an already-executed phase.
- **Parallel within a phase:** plans in the same declared `wave:` whose `files_modified` are
  provably disjoint. The planner declares the waves; the orchestrator enforces disjointness before
  fanning out.
- **Planning runs ahead of execution** by up to one milestone. Further ahead than that and plans go
  stale against code that does not exist yet. Before any plan executes, its executor **re-grounds it
  against the current tree** and reports drift rather than following a stale instruction.

---

## 8. Batching

| Batch | Phases | Planning | Execution |
|---|---|---|---|
| B1 | 3, 4 | parallel | 3 then 4 |
| B2 | 5, 6 | parallel | 5 then 6 |
| B3 | 7, 8, 9 | parallel | 7 → 8 → 9 |
| B4 | 10, 11, 12 | parallel | 10 → 11 → 12 |
| B5 | 13, 14, 15 | parallel | 13 → 14 → 15 |
| B6 | 16, 17, 18, 19, 20, 21 | parallel | 16 → 17 → 18 → 19 → 20 → 21 |
| B7 | 22, 23, 24 | parallel | 22 → 23 → 24 |

The orchestrator reports at every batch boundary and does not silently continue past a red suite.

---

## 9. Definition of done, per phase

A phase is done when **all** hold:

1. Every ROADMAP success criterion for the phase is proven by a test the **verifier ran itself** in
   its own session — not by reading a SUMMARY.
2. `uv run pytest -q` is green across the whole suite, including every earlier phase's tests.
3. `uv run ruff check src/ tests/ alembic/` exits 0.
4. Every requirement the phase owns per `.planning/REQUIREMENTS.md` is ticked there, or explicitly
   not ticked with the reason recorded (phase 1 did exactly this for CL-08 and CL-11).
5. `NN-VERIFICATION.md` and `NN-UAT.md` exist; `COVERAGE.md` and `deferred-items.md` exist.
6. `.planning/ROADMAP.md` (phase checkbox, Plans line, Progress table) and `.planning/STATE.md`
   (frontmatter, Current Position, Per-Plan Metrics, Accumulated Context) are updated.
7. New Broken Windows are appended to `.planning/WINDOWS.md` in both the table and the JSON block,
   with `open_count` corrected.
8. `.planning/ORCHESTRATION-DECISIONS.md` carries every UNCONFIRMED adoption the phase made.

**A red test is never "expected".** If a test cannot pass in this phase, the plan must have said so
in advance and routed it to a named later phase, the way phase 2 routed CL-01 and CL-02 to phase 3.

### 9a. Satisfying every ROADMAP success criterion is not the same as closing a milestone

Found during phase 3 planning and binding on every **milestone-closing** phase — 3, 6, 9, 12, 15, 18,
21 and 24.

`.planning/REQUIREMENTS.md` maps each requirement to a lock file **acceptance criterion**, not to a
ROADMAP **success criterion**, and the two are not the same set. A ROADMAP SC is a phase-scoped
restatement; a lock file's `acceptance_criteria`, `test_plan.load` and `test_plan.chaos` blocks carry
clauses that no SC restates. A phase can therefore satisfy every SC it was given and still leave the
module's own criteria unasserted — and because the next phase belongs to the next module, nobody
inherits them.

**So: the last phase of a milestone audits its lock file's `acceptance_criteria` and `test_plan`
blocks clause by clause**, and either asserts each one or routes it explicitly with a named owner.
Phase 3 found three this way (`AC-12`'s write-lag p95 < 2 s, `test_plan.load`'s ≥ 500 records/sec
drain and 60 s stall-recovery, and `test_plan.chaos` clause 5) and closed all three inside an existing
paced run rather than deferring them past the milestone that owned them.

## 10. Git

Branch `hina-dev` (never `main`, never a push). One commit per completed **plan**, message in the
repo's existing style, so a bad agent edit costs one plan rather than a milestone. No `--no-verify`,
no amend of a landed commit.

---

## 11. Model and effort tiering — set per role, never inherited by default

Every `agent()` call in this run declares `model` and `effort` deliberately. Inheriting the session's
tier everywhere over-provisions extraction work and under-provisions the two or three roles where a
miss is expensive. The tier is a property of **the job**, not of the run.

| Role | Model | Effort | Why this tier |
|---|---|---|---|
| **context** — phase boundary, `D-NN` decisions, reversibility calls | `opus` | `xhigh` | One-way architectural decisions taken on the user's behalf. The most leveraged artifact in the phase; every later stage reads it. |
| **research** — libraries, version pins, pitfalls, PostgreSQL/asyncio semantics | `opus` | `high` | Retrieval plus synthesis against checkable sources. Judgement-bearing but bounded — `xhigh` buys little over `high` once the sources are in hand. |
| **patterns** — codebase convention map, cited to `file:line` | `sonnet` | `high` | Extraction from files that already exist, with light judgement about what binds. The clearest downgrade in the pipeline; the work is *read and cite accurately*, not *decide*. |
| **planner** — the executable `NN-MM-PLAN.md` set | `opus` | `max` | The single highest-leverage artifact. Everything downstream executes it literally, so a defect here multiplies across a whole phase. Top tier, without apology. |
| **critic-spec** — fidelity against lock files, interfaces, ADRs, PITFALLS | `opus` | `xhigh` | Adversarial reading for subtle spec drift — an undeclared seam deviation, a plan asserting a lock file's literal AC text where PITFALLS demands the restated form. Exactly what a cheaper tier misses. |
| **critic-exec** — does it exist, do wave file-lists overlap, is the command runnable | `sonnet` | `high` | Largely mechanical verification: grep for the symbol, diff two `files_modified` lists, check a command against this host. High recall on concrete checks matters more than depth. |
| **revise** — verify each finding independently, apply surgical edits | `opus` | `high` | Must refute wrong findings as confidently as it fixes right ones, but works from two written critiques rather than from scratch. |
| **executor (tracer plan)** — the first end-to-end slice of a phase | `opus` | `max` | The tracer sets the shape every later plan in the phase expands off. Getting it wrong is discovered three plans later. |
| **executor (subsequent plans)** | `opus` | `xhigh` | Production code in a dense house style against a prescriptive plan. The most numerous role in the run, so the tier has to be sustainable as well as adequate. |
| **reviewer** — `NN-REVIEW.md`, adversarial code review of what shipped | `opus` | `xhigh` | Finds the defects the executor could not see in its own work. |
| **verifier** — `NN-VERIFICATION.md`, runs the tests itself | `opus` | `high` | Heavy on running commands, reading code and scoring truths against evidence. The standard is *evidence-first*, which is discipline rather than depth. |
| **bookkeeping** — ROADMAP table, STATE.md, WINDOWS.md, the decisions ledger | `sonnet` | `low` | Mechanical edits against a diff the orchestrator states exactly. Never given a judgement call. |
| **ledger append** — one row onto an existing table | `haiku` | `low` | Trivial, fully specified, single file. |

Two standing rules that follow from the table:

- **A bookkeeping agent is never asked to decide anything.** If updating `ROADMAP.md` requires
  judgement about whether a phase is actually done, that judgement belongs to the verifier and
  arrives as a stated diff. A cheap tier holding a decision is the failure mode this split exists to
  prevent.
- **`effort` is not a proxy for importance.** `patterns` and `critic-exec` sit at `high` because
  their work is concrete and checkable, not because they matter less — a missing entry in
  `files_modified` is the most damaging single defect available in this run, and `critic-exec` is
  what catches it.

---

*Maintained by the orchestrating session. Sub-agents read it; they do not edit it.*
