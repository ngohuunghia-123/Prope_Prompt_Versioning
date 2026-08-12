"""ADR-0050 — the gateway is its own ASGI application object, mounted by `prope.app`.

Its exception handlers, its middleware stack and its OpenAPI schema are its own,
so the OpenAI error contract is structural rather than a runtime path comparison.
`uvicorn prope.gateway:app` is the A-130 split, with no code change.
"""

import time

import structlog
from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import Response

from prope.gateway.errors import install_openai_errors
from prope.gateway.observability import request_duration_seconds
from prope.gateway.routes import router

log = structlog.get_logger(__name__)

__all__ = ["ROUTE_LABELS", "app", "bind_sessionmaker", "create_gateway_app"]

ROUTE_LABELS = frozenset({"/chat/completions", "/models"})


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if path in ROUTE_LABELS else "other"


def _outcome(status_code: int) -> str:
    if status_code < 400:
        return "ok"
    if status_code < 500:
        return "caller_error"
    return "upstream_error"


def create_gateway_app() -> FastAPI:
    application = FastAPI(
        title="Prope Gateway",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    install_openai_errors(application)

    @application.middleware("http")
    async def observe(request: Request, call_next) -> Response:  # noqa: ANN001
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        streaming = str(response.headers.get("content-type", "")).startswith("text/event-stream")
        route = _route_label(request)
        outcome = _outcome(response.status_code)

        request_duration_seconds.labels(
            route=route, streaming=str(streaming).lower(), outcome=outcome
        ).observe(elapsed)

        log.info(
            "gateway.request",
            route=route,
            status_code=response.status_code,
            streaming=streaming,
            outcome=outcome,
            duration_ms=int(elapsed * 1000),
            version_id=response.headers.get("x-prope-version-id"),
            model_name=response.headers.get("x-prope-model"),
            pinned=response.headers.get("x-prope-pinned"),
            fallback=response.headers.get("x-prope-fallback"),
        )
        return response

    application.include_router(router)
    return application


app = create_gateway_app()


def bind_sessionmaker(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    app.state.sessionmaker = sessionmaker
