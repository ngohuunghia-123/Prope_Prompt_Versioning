# Phase 2 — Deferred items

Out-of-scope discoveries found while executing. Logged, not fixed.

## `ruff format --check` fails repo-wide (pre-existing, Phase 1)

`uv run ruff format --check src/ tests/ alembic/` reports **31 files would be
reformatted, 26 already formatted** as of plan 02-02 (19/26 when 02-01 wrote this
entry; the count grows with every file either plan adds, because the cause is
systemic).

**Correction to this entry as first written (plan 02-02).** It said
`pyproject.toml` declares no `[tool.ruff]` section so ruff's default
`line-length = 88` applies. That is wrong, and the correction matters because it
inverts the direction of the diff: **`ruff.toml` exists at the repo root and sets
`line-length = 120`** (with `[lint] ignore = ["E501"]`). The repo is hand-wrapped
to roughly 100, so the formatter does not want to *break* long lines — it wants
to *join* short ones back up to 120. Every hunk in the `--check` output is a
`-`/`+` pair collapsing a wrapped call onto one line.

`uv run ruff check` — the linter, which is what CI would gate on today — passes
clean, because `E501` is explicitly ignored.

The decision is therefore not "adopt a line-length" but "pick which of the two
line lengths the repo means": set `ruff.toml`'s `line-length` to 100 to match the
prose-wrapped house style every module docstring is written in, or keep 120 and
reformat once. Plan 02-01's and 02-02's `<verification>` blocks both list
`ruff format --check` among their commands; that line is unsatisfiable without
this repo-wide decision, and neither plan reformats files it does not own. New
files in both plans are written in the house ~100 style deliberately, so they
read like their neighbours rather than like the formatter's preference.

## Root `Dockerfile` and `docker-compose.yml` are boilerplate from another project

Named by `02-RESEARCH.md` § State of the Art and routed here by it. The
Dockerfile reads `FROM python:3.11-slim` and `COPY requirements.txt` (a file
that does not exist); the compose file declares a single `backend` service with
a `/health` healthcheck. All three contradict ADR-0026 (Python 3.13), ADR-0033
(7 services, 2 images) and INT-030 (`/healthz`, `/readyz`).

The deployment stack owns no milestone (PITFALLS §3/§4), so no phase owns
fixing these. Recorded so they read as known rather than as the shape to extend.

**Confirmed against the files again by plan 02-03**, which its Task 2 required
before writing `src/prope/worker.py`. Both files are unchanged since 02-01
recorded them and both are still the other project's boilerplate. Two additional
specifics that bear on this phase, now that the second process exists:

- The compose file names **one** service, `backend`, and healthchecks it on
  `/health`. Prope has **two** processes (`app` and `worker`) from **one** image,
  and `worker` deliberately serves no HTTP at all (D-17, derived from ADR-0028),
  so `worker`'s healthcheck must be process-level. A compose file grown from this
  one would give `worker` an HTTP healthcheck by inheritance, which is the exact
  surface D-17 refuses and T-02-15 registers.
- `python:3.11-slim` cannot run this code: `pyproject.toml` pins
  `requires-python = ">=3.13,<3.14"` and `prope.supervisor` uses
  `asyncio.TaskGroup` idioms and `StrEnum` that assume 3.13.

Still not fixed here. Writing a real Dockerfile and compose file is the
deployment stack's work, and this phase does not own it.

## `testcontainers[postgresql]` extra does not exist

`uv sync` emits `warning: The package testcontainers==4.15.0 does not have an
extra named postgresql`. Pre-existing from Phase 1 and harmless — the Postgres
support ships in the base package, and the rig has worked all along. The
`rabbitmq` extra added this phase DOES exist and resolves `pika` as expected.
Correcting the name is a one-token edit in a Phase 1 line; not made here so the
dependency diff for this plan stays about the broker.

## `LOGGABLE_FIELDS` does not yet carry `job` (plan 02-03)

`src/prope/supervisor.py` emits one log line, `supervisor.job_crashed`, carrying
`job` and `reason`. `reason` is on `prope.observability.LOGGABLE_FIELDS`; `job`
is not, because `src/prope/observability.py` belongs to **plan 02-04** and this
plan does not edit a file another plan in the same wave declares.

`job` qualifies on the allow-list's own rule — its values are the job names fixed
in `prope.worker`'s source (`JOB_CALL_RECORD_DRAIN`, `JOB_EXPIRED_BODY_DELETION`),
a closed set of two, and never a body, an identifier or a credential. **Plan
02-04 or Phase 3's T-005 sweep should add `"job"` to the frozenset.** Recorded
rather than silently left, because an allow-list with a field outside it is an
allow-list somebody has already stopped believing.

## The retention sweep's workspace enumerator is a Phase 2 stand-in (plan 02-03)

`prope.worker.ObservedWorkspaces` sweeps only the workspaces the drain has
resolved a retention window for **since this process started**. A workspace that
sends no traffic is not swept, so its already-expired bodies survive.

This is not a shortcut taken for convenience. Under ADR-0045 a `prope_app` query
issued with no `app.workspace_id` returns **zero rows**, so there is no
cross-tenant enumeration available from the ledger at all; ADR-0051's answer,
`access.list_workspaces()`, lives in the `access` schema, which arrives in
**Phase 7**, and call-ledger is forbidden an outbound edge to it. Inventing a
fifth `SECURITY DEFINER` routine here would break the test asserting the
sanctioned set is exactly four. Phase 1's `retention.py` recorded the same
problem as OQ-C and carried it upstream rather than improvising.

`run_worker` takes the enumerator as a parameter, so **Phase 7 replaces an
argument rather than editing the job**. Both halves of the gap are asserted in
`tests/integration/test_worker_jobs.py` — an observed workspace is swept, an
unobserved one is not — so the boundary is fixed in place rather than believed.
Phase 3's `oldest_body_age_seconds` gauge is what measures it in production.
