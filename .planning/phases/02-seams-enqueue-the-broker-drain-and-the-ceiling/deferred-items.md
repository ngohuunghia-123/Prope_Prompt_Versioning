# Phase 2 — Deferred items

Out-of-scope discoveries found while executing. Logged, not fixed.

## `ruff format --check` fails repo-wide (pre-existing, Phase 1)

`uv run ruff format --check src/ tests/ alembic/` reports **19 files would be
reformatted, 26 already formatted**. The failures are overwhelmingly Phase 1
files (e.g. `tests/unit/test_write_records.py`), not files this phase created:
`pyproject.toml` declares no `[tool.ruff]` section, so ruff's default
`line-length = 88` applies while the repo is written to roughly 100.

`uv run ruff check` — the linter, which is what CI would gate on today — passes
clean, because `E501` is off by default.

This is a repo-wide formatting-config decision (adopt a `[tool.ruff]`
`line-length`, then reformat once), not a Phase 2 defect. Plan 02-01's
`<verification>` lists `ruff format --check` among its commands; that line is
unsatisfiable without the repo-wide decision, so it is recorded here rather than
silently reformatting 19 files this phase does not own.

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
