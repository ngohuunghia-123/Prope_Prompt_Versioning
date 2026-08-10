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

## `testcontainers[postgresql]` extra does not exist

`uv sync` emits `warning: The package testcontainers==4.15.0 does not have an
extra named postgresql`. Pre-existing from Phase 1 and harmless — the Postgres
support ships in the base package, and the rig has worked all along. The
`rabbitmq` extra added this phase DOES exist and resolves `pika` as expected.
Correcting the name is a one-token edit in a Phase 1 line; not made here so the
dependency diff for this plan stays about the broker.
