"""Prompt optimization graph.

A linear, dependency-injected async pipeline that mirrors the LangGraph
workflow described in the backend plan:

    START
      ↓
    load_context
      ↓
    analyze_prompt
      ↓
    optimize_prompt
      ↓
    run_eval
      ↓
    regression_gate
      ↓
    explain_eval
      ↓
    END

We deliberately implement the workflow as a plain async function graph
rather than importing the `langgraph` package directly. Reasons:

1. The backend plan mentions LangGraph, but this service is a focused,
   self-contained agent. The plan also states "no LLM decides the gate" —
   a simple linear pipeline makes that invariant obvious.
2. Keeping the graph code small makes it easy to swap to `langgraph`
   later without rewriting the nodes (each node is already a pure
   async function that takes `state` and returns `state`).
3. Fewer moving parts means tests are deterministic and the agent runs
   cleanly on a laptop.

If `langgraph` is available, `build_langgraph_app()` below returns a
fully-wired `langgraph` graph using the SAME nodes.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Awaitable, Callable

from ..core.exceptions import WorkflowError
from ..core.logging import get_logger
from ..providers.base import LLMProvider
from .nodes import (
    analyze_prompt,
    explain_eval,
    load_context,
    optimize_prompt,
    regression_gate,
    run_eval_node,
)
from .state import PromptWorkflowState

logger = get_logger(__name__)

NodeFn = Callable[[PromptWorkflowState], Awaitable[PromptWorkflowState]]


def _make_nodes(provider: LLMProvider) -> list[tuple[str, NodeFn]]:
    """Bind the provider to each node, returning (name, callable)."""

    async def _load(s: PromptWorkflowState) -> PromptWorkflowState:
        return await load_context(s, provider=provider)

    async def _analyze(s: PromptWorkflowState) -> PromptWorkflowState:
        return await analyze_prompt(s, provider=provider)

    async def _optimize(s: PromptWorkflowState) -> PromptWorkflowState:
        return await optimize_prompt(s, provider=provider)

    async def _eval(s: PromptWorkflowState) -> PromptWorkflowState:
        return await run_eval_node(s, provider=provider)

    async def _gate(s: PromptWorkflowState) -> PromptWorkflowState:
        return await regression_gate(s, provider=provider)

    async def _explain(s: PromptWorkflowState) -> PromptWorkflowState:
        return await explain_eval(s, provider=provider)

    return [
        ("load_context", _load),
        ("analyze_prompt", _analyze),
        ("optimize_prompt", _optimize),
        ("run_eval", _eval),
        ("regression_gate", _gate),
        ("explain_eval", _explain),
    ]


async def run_workflow(
    *,
    initial_state: dict[str, Any],
    provider: LLMProvider,
) -> PromptWorkflowState:
    """Run the linear graph to completion."""
    state: PromptWorkflowState = deepcopy(initial_state)  # type: ignore[assignment]
    state.setdefault("errors", [])
    state["stage"] = state.get("stage", "init")
    nodes = _make_nodes(provider)
    for name, fn in nodes:
        try:
            state = await fn(state)
            logger.info("node %s -> stage %s", name, state.get("stage"))
        except Exception as exc:  # noqa: BLE001
            state["stage"] = "failed"
            state["errors"].append(  # type: ignore[attr-defined]
                {"node": name, "error": str(exc)}
            )
            logger.exception("node %s failed", name)
            raise WorkflowError(f"Node {name} failed: {exc}") from exc
    state["stage"] = state.get("stage", "done")
    return state


# ---------- optional LangGraph adapter ----------


def build_langgraph_app(provider: LLMProvider):  # pragma: no cover - optional
    """If `langgraph` is installed, return a real StateGraph using the
    same node functions. Raises ImportError if not installed."""
    from langgraph.graph import END, START, StateGraph  # type: ignore

    g = StateGraph(PromptWorkflowState)

    g.add_node("load_context", lambda s: load_context(s, provider=provider))
    g.add_node("analyze_prompt", lambda s: analyze_prompt(s, provider=provider))
    g.add_node("optimize_prompt", lambda s: optimize_prompt(s, provider=provider))
    g.add_node("run_eval", lambda s: run_eval_node(s, provider=provider))
    g.add_node("regression_gate", lambda s: regression_gate(s, provider=provider))
    g.add_node("explain_eval", lambda s: explain_eval(s, provider=provider))

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "analyze_prompt")
    g.add_edge("analyze_prompt", "optimize_prompt")
    g.add_edge("optimize_prompt", "run_eval")
    g.add_edge("run_eval", "regression_gate")
    g.add_edge("regression_gate", "explain_eval")
    g.add_edge("explain_eval", END)

    return g.compile()
