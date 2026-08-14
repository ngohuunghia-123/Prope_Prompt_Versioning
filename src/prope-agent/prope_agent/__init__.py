"""prope_agent — LangGraph-based system prompt optimization agent.

A focused implementation of the LangGraph workflow described in the
backend plan: load context → analyze → optimize → evaluate → explain.

Input: a system prompt.
Output: an improved system prompt, with a structured diff and rationale.

Quick start:
    from prope_agent import optimize_text
    new_prompt = optimize_text("You are a helpful assistant.")
"""

from .api_inline import optimize, optimize_text

__version__ = "0.1.0"

__all__ = ["optimize", "optimize_text", "__version__"]
