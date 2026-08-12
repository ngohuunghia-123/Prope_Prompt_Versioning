# ADR-0033 / ADR-0031: the prope-app image, serving both `app` and `worker`
# (different `command:` in docker-compose.yml, same image). ADR-0026 pins
# Python 3.13.x; ADR-0031 says the host pulls a built image and never builds —
# this Dockerfile is what CI runs through `docker build` to produce it.

FROM python:3.13-slim AS builder

RUN pip install --no-cache-dir uv==0.9.7

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

FROM python:3.13-slim

RUN useradd --create-home --uid 10001 prope
WORKDIR /app

COPY --from=builder --chown=prope:prope /app/.venv /app/.venv
COPY --from=builder --chown=prope:prope /app/src /app/src
COPY --from=builder --chown=prope:prope /app/alembic /app/alembic
COPY --from=builder --chown=prope:prope /app/alembic.ini /app/pyproject.toml /app/uv.lock ./

ENV PATH="/app/.venv/bin:$PATH"

USER prope

EXPOSE 8000

CMD ["uvicorn", "prope.app:app", "--host", "0.0.0.0", "--port", "8000"]
