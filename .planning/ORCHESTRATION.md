# Orchestration contract — phases 4–24

> This is the run contract every planner, executor, verifier and reviewer reads before it does
> anything. It is referenced by `@.planning/ORCHESTRATION.md` from the plan files.
>
> **This run does NOT use the GSD command workflow.** The user has explicitly opted out for speed.
> Do not invoke `/gsd-*` anything. The artifacts below are the whole process.

## §0 — Estimates and calibration

There is no calibration tool in this environment and this project has no measured plan-execution
samples. Every `estimate.tokens` in every plan equals its `raw_tokens` by construction and carries
`confidence: low`. **Do not treat an estimate as a budget or as permission to stop early.** A plan is
done when its `must_haves` are true, not when its token estimate is spent. If a task overruns, finish
it long rather than splitting it, and say so in the SUMMARY.

## §1 — Roles

| Role | May write | May not |
|---|---|---|
| **Orchestrator** (main session) | `ROADMAP.md`, `STATE.md`, `WINDOWS.md`, `ORCHESTRATION-DECISIONS.md`, `deferred-items.md` | Source code |
| **Planner** | `NN-CONTEXT.md`, `NN-MM-PLAN.md` inside its own phase directory | Source code, other phases' directories |
| **Executor** | Exactly the paths in its plan's `files_modified`, plus its own `NN-MM-SUMMARY.md` | Anything else — see §5 |
| **Verifier** | `NN-VERIFICATION.md` | Source code |
| **Reviewer** | `NN-REVIEW.md` | Source code |

## §2 — Executor protocol

1. **Read the whole plan file first.** These plans run 600–1400 lines. The frontmatter is a contract,
   not a header: `must_haves.truths` are what the phase is graded on, `must_haves.prohibitions` are
   absolute, and `files_modified` is the only thing the orchestrator uses for wave disjointness.
2. **Read every file the plan's `<context>` block `@`-references, and every file its
   `<read_first>` blocks name.** The plans cite line numbers and precedents on purpose. A plan that
   says "copy the import comment from `0003:41-54` verbatim" means verbatim.
3. **Execute the tasks in order.** Do not reorder, do not skip, do not "optimise" a task away.
4. **Run the gate (§3) before writing the SUMMARY.** A plan whose suite is red is not complete.
5. **Write `NN-MM-SUMMARY.md`** in the established format — see any of
   `.planning/phases/03-*/03-0*-SUMMARY.md` for the exact frontmatter shape (`requires` / `provides`
   / `affects`, `actuals`, `tech-stack`, `key-files`, `key-decisions`, `patterns-established`,
   `requirements-completed`). The `key-decisions` block is the highest-value part of the artifact:
   record *what was decided and why*, not what was typed.
6. **Do not commit.** The orchestrator commits at wave boundaries.

### What "done" means

Every entry in `must_haves.truths` is demonstrably true, every `must_haves.artifacts` path exists and
contains what `contains:` names, every `key_links` link is real, and the gate is green. If one is not,
the SUMMARY says which and why — **a SUMMARY that claims a truth the tests do not show is the single
worst outcome available to this run.**

## §3 — The gate, and the environment

```bash
uv run ruff check src/ tests/ alembic/     # lint gate
uv run pytest -q                            # suite gate
```

- **`make check` is NOT the gate** — its `format` target *writes*, and `ruff format --check` fails
  repo-wide on a pre-existing line-length disagreement (Broken Window #1). Do not run it.
- **`pytest-timeout` is not installed.** `--timeout=` is an unrecognised argument; do not pass it.
- **Load tests are behind `PROPE_RUN_LOAD=1`** and are skipped by default (`make load` runs them,
  ~12 min plus container startup). Run them only when a plan asks.
- **Host is Windows 10, shell is PowerShell (Bash also available).** `loop.add_signal_handler` is not
  implemented on Windows — anything that installs a signal handler must have a Windows path.
- **`docker` is NOT on the default bash PATH.** A shell that drives it must first run
  `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`. `testcontainers` reaches the
  Docker Desktop named pipe without PATH help, so `uv run pytest` needs no PATH change.
- **No dependency may be added** unless a plan explicitly says so. `uv.lock` must not move.
- Every test that needs a database uses the existing testcontainers rig in `tests/conftest.py`.

## §4 — Alembic revision numbers

**Never hardcode a revision number.** At execution time run `uv run alembic heads`, use the reported
head as `down_revision`, and take the next integer as `revision`. The chain is linear (D-04) and
`tests/integration/test_migration_chain.py` asserts exactly one head, so a guessed parent is a red
test rather than a merge revision. **Only one plan per wave may create a revision** — the
orchestrator serialises any wave where two would.

## §5 — Deviations, and what is never edited

**Never edit** `docs/modules/*.lock.yml`, `docs/architecture/*`, or any file in `docs/adr/`. These are
locked upstream specs. A plan that disagrees with a spec **raises the disagreement, it does not patch
the spec**:

- Record it as an open question at `docs/brainstorm/open_questions/OQ-NNN.md` **only if the plan
  allocated you an id**. Phase id ranges are allocated in the phase's CONTEXT.
- If the phase's allocated range is consumed, **do not borrow another phase's range.** Write the
  deviation into the artifact's own docstring as *owed and unallocated* and escalate it in the
  SUMMARY's `## Ledger entries owed` section (§7).
- A deviation that is a *spelling* difference with a byte-identical end state owes no OQ. A deviation
  with an *observable behavioural* difference always does.

## §6 — Adopted-unconfirmed decisions (`mode: yolo`)

This run does not stop at `checkpoint:decision` gates; the user has asked for continuous execution.
Every one-way or costly decision made **on the user's behalf** is therefore adopted UNCONFIRMED and
must reach `.planning/ORCHESTRATION-DECISIONS.md` so the user can adjudicate a list instead of
archaeology. Executors do not write that file directly (§7) — they surface the row in the SUMMARY and
the orchestrator merges it.

A decision is reportable if it is **one-way** (expensive or impossible to reverse once data exists —
a grant, a column type on an append-only table, a wire format) or **costly** (a reversal is real
work). A decision the plan already made and argued is *not* a new adoption; re-opening it is
re-asking a settled question.

## §7 — Shared ledger files are ORCHESTRATOR-OWNED

Several waves run plans **in parallel**. These files are touched by many plans and a parallel write
loses data:

- `.planning/phases/*/deferred-items.md`
- `.planning/ORCHESTRATION-DECISIONS.md`
- `.planning/WINDOWS.md`
- `.planning/STATE.md`, `.planning/ROADMAP.md`

**An executor must not edit any of them**, even when its plan's `files_modified` lists one. Instead it
ends its SUMMARY with:

```markdown
## Ledger entries owed

### deferred-items.md
- ...

### ORCHESTRATION-DECISIONS.md
| Phase | Plan | Decision | Rejected alternative | Reversibility |
| ... |

### WINDOWS.md (broken windows)
- kind / file / description
```

The phase's closing agent (or the orchestrator) merges them once, serially.

## §8 — Waves and parallelism

Plans carry `wave:` and `depends_on:`. Plans in the same wave run **concurrently in the same working
tree**, which is safe only because their `files_modified` sets are disjoint. Consequences:

- **Do not write outside `files_modified`.** A stray edit in a parallel wave is a lost update in
  another agent's file, and it will not look like one when it is found.
- If a plan genuinely needs a file it did not declare, **stop and report it in the SUMMARY** rather
  than taking it.
- Do not `git add`, `git commit`, `git stash`, `git checkout` or `git restore`. The tree is shared.

## §9 — Closeout obligations

**§9a — the clause-by-clause audit.** The last plan of each phase audits the module lock file's
`acceptance_criteria` and `test_plan` clause by clause and records, for each, the test that proves it
or the reason it is not proven yet. A clause with no test and no stated reason is a gap, and naming it
is the deliverable.

**§9b — the milestone handoff.** At the end of each milestone (M2 = phases 4–6, M3 = 7–9, M4 = 10–12,
M5 = 13–15, M6 = 16–18, M7 = 19–21, M8 = 22–24) a handoff agent writes
`.planning/phases/<last-phase-dir>/MILESTONE-<Mn>-MANUAL-TEST.md` **for a human to drive by hand**:

1. **What now works** — in plain language, one line per capability.
2. **Every HTTP route that exists after this milestone** — method, path, auth required, request body
   shape, success response shape, and the notable refusals with their status codes. Include routes
   from earlier milestones so the document is cumulative and self-contained.
3. **How to start it** — the exact commands, on Windows, including database and broker.
4. **A copy-pasteable walkthrough** — `curl` (or PowerShell `Invoke-RestMethod`) calls in the order a
   person would actually do them, with the values that must be substituted marked.
5. **What is deliberately NOT working yet**, and which phase turns it on. A reader must not mistake a
   not-yet-built seam for a bug.
6. **What to look at to confirm it worked** — the table, the metric, the log line.

This document is written for the user, not for an agent. Plain, concrete, no planning vocabulary.

## §10 — Verification and review

After a phase's plans are all executed:

- **Verifier** runs the full gate from a clean state, walks the phase's ROADMAP success criteria one
  by one, and names the test that proves each. Writes `NN-VERIFICATION.md`.
- **Reviewer** reads the phase's diff adversarially and writes `NN-REVIEW.md` in the shape of
  `.planning/phases/03-*/03-REVIEW.md` — frontmatter with counts and status, then findings ordered
  critical → warning → info, each with file, line, the failure it produces, and a concrete fix. A
  reviewer that finds nothing says so; a reviewer that pads is worse than none.

## §12 — Comment density (OVERRIDES the plan files)

**This section outranks any comment instruction in any plan file.** Several plans were written with
instructions like *"the module docstring is a deliverable, not decoration"*, followed by a list of
mandatory per-column and per-constraint comments. That produced source files where prose outweighs
code roughly three to one. **That is now wrong. Where a plan's comment instruction conflicts with
this section, this section wins, and the executor notes the override in one line of its SUMMARY.**

**Planners are bound by this too.** A plan you write must not instruct an executor to produce
comments beyond what this section allows, and must not carry sentences like *"the docstring is a
deliverable"* or *"comments that must be present"* followed by a list. Put the argument **in the
plan**, where it belongs and where it costs nothing at runtime; instruct the executor to leave a
pointer (`# ADR-00NN / D-NNN: <=12 words`) in the source. When a plan needs an executor to
understand a subtle decision, that is what the plan's own `<action>` prose is for — not a comment
the executor then has to transcribe into the file.

### The rule

**Comment the surprising, never the visible.** If a competent Python engineer reading the line can
tell what it does, it gets no comment. Budget: **comments and docstrings together should be well
under a third of a file**, and most functions should have none at all.

### Do not write

- Docstrings that restate the signature — `"""Return the workspace id."""` on `def workspace_id()`.
- A comment per column, per constraint, per grant or per index restating what the DDL says.
- Multi-paragraph module docstrings that re-argue an ADR. **Cite it: `# ADR-0025`** and stop.
- Comments that narrate the code below them (`# loop over the records`).
- Restatements of a decision that already lives in a plan, a CONTEXT, an ADR or a SUMMARY. Those
  documents are the record. Source is not a second copy of them.
- Prose explaining what a test asserts when the test's own name already says it.

### Do write, briefly

- **A one-line `# WHY:` where the code looks wrong but is right** — a refused optimisation, a
  deliberate no-op, an ordering that must not be swapped, a workaround for a named platform bug.
- **A one-line pointer for a one-way decision**, in the form `# ADR-0025 / D-53: <=12 words`. The
  argument lives in the ADR or the plan; the source carries the pointer, not the argument.
- **A short docstring on a public seam** — the functions other modules call. One or two lines:
  what it returns and the one constraint a caller must respect. Not a treatise.
- **A note at an assertion that would otherwise look vacuous**, naming why it is not.

### Migrations specifically

A revision gets a **short** module docstring: what it creates, and any deviation from the lock file
in one or two sentences with the OQ id. Per-column comments only where the choice is genuinely
non-obvious (a type that looks wrong, a nullable that looks arbitrary, a constraint that looks
redundant). `GENERATED ALWAYS AS IDENTITY (CACHE 1)` gets one line, not fourteen.

### Rewriting existing files

Do **not** open files outside your `files_modified` to trim their comments. If you are already
editing a file whose comments are far over budget, trimming them is welcome and is not a scope
violation — but never delete a comment recording a **decision, a deviation, or a refused
alternative** without moving that record into your SUMMARY, an OQ, or the plan's `key-decisions`.

### The known backlog, and who owns it

Plans 04-01 and 04-02 executed **before this section existed** and their output is measurably over
budget. Measured 2026-08-11:

| File | Lines | Prose % |
|---|---|---|
| `src/prope/property_history/__init__.py` | 16 | 100% |
| `src/prope/property_history/observability.py` | 29 | 76% |
| `src/prope/property_history/registry.py` | 65 | 55% |
| `src/prope/property_history/append.py` | 149 | 53% |
| `alembic/versions/0005_history_schema_and_vocabulary.py` | 433 | 50% |
| `src/prope/property_history/domain.py` | 193 | 44% |

**Trimming these is assigned work, not optional polish.** It falls to whichever agent next holds the
tree quiet with those files in scope — in practice the phase 4 remediation agent. A reviewer that
sees them still over budget should report it as a **warning with the file named**, and a remediation
agent should treat it as a finding to fix rather than a style preference to weigh.

Target after trimming: prose comfortably under a third, and the migration under 25% — a migration is
mostly DDL, and DDL is self-describing. Move every argument worth keeping into the plan's
`key-decisions`, the phase CONTEXT, or an OQ. **Nothing that records a decision may be lost — only
relocated.**

## §11 — Standing project facts

- **The four non-negotiables** (`.claude/CLAUDE.md`): human approval before production; only
  `Approved` revisions may be released, enforced by a database constraint; edit / review / release are
  separate permissions; prompts are private by default, enforced as *not-found*.
- **Build database-first.** The migration carries the guarantee — constraint, privilege, policy,
  grant, trigger. Application code is what the guarantee protects, never the guarantee itself.
- **Exactly four `SECURITY DEFINER` functions are sanctioned**: `access.lookup_session`,
  `access.lookup_api_key`, `evaluation.claim_next_run()`, `access.list_workspaces()`. A test asserts
  the set is exactly these four.
- **`workspace_id` is `text`**, and every RLS predicate compares text to text with no cast.
- **Never a native PostgreSQL `ENUM`.** Vocabularies are `text` plus a named `CHECK`, or a registry
  row.
- **Refusal shapes carry security weight** — not-found when the actor cannot see the subject,
  forbidden naming the missing permission when they can. These are asserted, not intended.
