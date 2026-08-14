"""FastAPI app for prope-agent.

Endpoints:
    POST /optimize          -> start a workflow, return workflow_id
    GET  /workflows         -> list workflows
    GET  /workflows/{id}    -> fetch full state (final_prompt lives here)
    POST /workflows/{id}/approve -> optional HITL hook (always approve in MVP)
    GET  /healthz           -> liveness
    GET  /readyz            -> readiness

The workflow runs as a background asyncio task so the HTTP request returns
fast. The agent workflow itself is idempotent and resumable; for this MVP
we run it once to completion, then expose the result via GET.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException

from ..agents import run_workflow
from ..core.config import get_settings
from ..core.logging import get_logger, setup_logging
from ..providers import build_provider
from ..providers.base import LLMProvider
from ..storage import store
from .schemas import (
    HealthResponse,
    OptimizeRequest,
    OptimizeResponse,
    OptimizeResultResponse,
    WorkflowListItem,
)

logger = get_logger(__name__)


def _create_app(provider: LLMProvider | None = None) -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    p = provider or build_provider(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.provider = p
        logger.info("prope-agent started with provider=%s", p.name)
        yield
        logger.info("prope-agent shutting down")

    app = FastAPI(
        title="prope-agent",
        description=(
            "LangGraph-style system prompt optimization agent. "
            "Input: a system prompt. Output: an improved system prompt "
            "with analysis, comparison, and explanation."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    async def _run_and_store(workflow_id: str, initial: dict[str, Any]) -> None:
        lock = store.lock_for(workflow_id)
        async with lock:
            try:
                final = await run_workflow(initial_state=initial, provider=p)
            except Exception as exc:  # noqa: BLE001
                logger.exception("workflow %s failed", workflow_id)
                initial["stage"] = "failed"
                initial["errors"] = initial.get("errors", []) + [
                    {"node": "graph", "error": str(exc)}
                ]
                store.upsert(workflow_id, initial)
                return
            store.upsert(workflow_id, final)

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(
            status="ok",
            provider=p.name,
            model=getattr(p, "_default_model", "mock"),
        )

    @app.get("/readyz", response_model=HealthResponse)
    async def readyz() -> HealthResponse:
        return HealthResponse(
            status="ready",
            provider=p.name,
            model=getattr(p, "_default_model", "mock"),
        )

    @app.post("/optimize", response_model=OptimizeResponse, status_code=202)
    async def optimize(
        req: OptimizeRequest, background: BackgroundTasks
    ) -> OptimizeResponse:
        workflow_id = str(uuid.uuid4())
        initial: dict[str, Any] = {
            "workflow_id": workflow_id,
            "workspace_id": "default",
            "original_prompt": req.prompt,
            "prompt_metadata": req.metadata,
            "target_use_case": req.target_use_case,
        }
        store.upsert(workflow_id, {**initial, "stage": "queued"})

        background.add_task(_run_and_store, workflow_id, initial)
        return OptimizeResponse(
            workflow_id=workflow_id, status="queued", stage="queued"
        )

    @app.get("/workflows", response_model=list[WorkflowListItem])
    async def list_workflows() -> list[WorkflowListItem]:
        return [WorkflowListItem(**item) for item in store.list()]

    @app.get("/workflows/{workflow_id}", response_model=OptimizeResultResponse)
    async def get_workflow(workflow_id: str) -> OptimizeResultResponse:
        state = store.get(workflow_id)
        if state is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        return _to_result(state)

    @app.post(
        "/workflows/{workflow_id}/approve", response_model=OptimizeResultResponse
    )
    async def approve(workflow_id: str) -> OptimizeResultResponse:
        state = store.get(workflow_id)
        if state is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        # In MVP, the agent has already finished; approval is just a no-op
        # marker. Real impl would resume the LangGraph interrupt.
        state["human_approval"] = True
        store.upsert(workflow_id, state)
        return _to_result(state)

    return app


def _to_result(state: dict[str, Any]) -> OptimizeResultResponse:
    return OptimizeResultResponse(
        workflow_id=state["workflow_id"],
        stage=state.get("stage", "unknown"),
        original_prompt=state.get("original_prompt", ""),
        final_prompt=state.get("final_prompt") or state.get("candidate_prompt") or "",
        candidate_prompt=state.get("candidate_prompt"),
        analysis=state.get("analysis", {}),
        findings=state.get("findings", []),
        changes=state.get("changes", []),
        baseline_metrics=state.get("baseline_metrics"),
        candidate_metrics=state.get("candidate_metrics"),
        comparison=state.get("comparison"),
        quality_gate=state.get("quality_gate"),
        explanation=state.get("explanation"),
        started_at=state.get("started_at"),
        finished_at=state.get("finished_at"),
        errors=state.get("errors", []),
    )


# Module-level app for `uvicorn prope_agent.api.app:app`
app = _create_app()
