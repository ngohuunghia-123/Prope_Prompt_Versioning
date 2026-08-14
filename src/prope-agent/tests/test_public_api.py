"""Smoke test for the high-level optimize_text / optimize helpers."""
from __future__ import annotations

from prope_agent import optimize, optimize_text


def test_optimize_text_returns_string():
    out = optimize_text("You are a customer support bot. Answer politely.")
    assert isinstance(out, str)
    assert len(out) > 0
    # Mock provider should have added structure blocks.
    assert "Constraints" in out


def test_optimize_returns_full_state():
    state = optimize("Summarize articles in three bullets.")
    assert state["stage"] == "explained"
    assert "final_prompt" in state
    assert "comparison" in state
    assert "quality_gate" in state
