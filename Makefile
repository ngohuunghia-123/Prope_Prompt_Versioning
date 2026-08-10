.PHONY: run test lint format check clean

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

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
