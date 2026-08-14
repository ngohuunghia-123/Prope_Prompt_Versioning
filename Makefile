.PHONY: run test lint format check load clean dev dev-logs dev-down

# NOT SERVABLE YET. Phase 1 builds the database foundation only; `prope.app`
# arrives with the management surface in phase 2 (D-03). The target is written
# against the real module path so it starts working when that module lands,
# rather than pointing at `src.main:app`, which never existed.
run:
	uv run uvicorn prope.app:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest -q

lint:
	uv run ruff check src/ tests/ alembic/

format:
	uv run ruff format src/ tests/ alembic/

# No `typecheck` target. mypy is deliberately absent from the dependency set,
# and a target that calls a tool nobody installed is a broken target left
# standing for 24 phases.
check: lint format test

# ROADMAP SC5's stated condition, which `test` deliberately does not run:
# 30,000 records over 10 minutes against a live broker and a live database,
# plus the 60 s writer stall and the concurrent retention sweep. Roughly twelve
# minutes plus container startup.
#
# `check` does not depend on this, and that is the trade D-45 argued —
# tests/load/test_enqueue_off_response_path.py asserts the same two properties
# at a duration the pre-commit suite can carry, and a gate nobody runs is a gate
# that has stopped gating.
#
# The inline `VAR=value cmd` prefix is POSIX-shell syntax. GNU Make defaults
# SHELL to /bin/sh where one exists, which it does here (Git Bash), and the
# `clean` target below already assumes `sh` for its `find ... -exec`. So this is
# consistent with the file rather than a new assumption — but the development
# host's primary shell is PowerShell, so it is written down: invoked where no
# `sh` exists this line does not work, and the fallback is the environment
# variable form the skip's own reason string names.
load:
	PROPE_RUN_LOAD=1 uv run pytest -m load -q

# ── Hot-reload development stack ──────────────────────────────────────────────
# docker-compose.dev.yml is a merge layer that swaps in `uvicorn --reload`, the
# watchfiles-wrapped worker, and the Vite dev server, all over bind-mounted
# source. Compose applies it only when the file is *named*: APP_ENV=development
# does not name it, and neither does a plain `docker compose up`, which is why an
# otherwise correct dev .env still gets you the baked, non-watching stack.
#
# These targets name it explicitly. Setting
#
#     COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml
#
# in .env makes plain `docker compose` commands do the same thing everywhere;
# use these when you would rather not make watching the machine-wide default.
DEV_COMPOSE := -f docker-compose.yml -f docker-compose.dev.yml

# `caddy` serves the baked SPA on 8080 in the production-shaped stack and Vite
# claims that port in dev, so the old container has to let go of it first. The
# dev overlay parks caddy behind a profile, so it will not come back on its own.
dev:
	docker compose stop caddy
	docker compose $(DEV_COMPOSE) up -d
	@echo "SPA with HMR + API proxied on http://localhost:8080"
	@echo "First start installs node_modules into a named volume — give it a minute, watch with 'make dev-logs'."

dev-logs:
	docker compose $(DEV_COMPOSE) logs -f app worker web

dev-down:
	docker compose $(DEV_COMPOSE) down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
