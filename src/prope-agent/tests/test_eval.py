"""Tests for the deterministic eval engine and quality gate."""
from __future__ import annotations

import pytest

from prope_agent.eval import (
    EvalCase,
    HeuristicEvaluator,
    compare,
    estimate_cost_usd,
    make_provider_generate_fn,
    run_eval,
    synthetic_cases,
)
from prope_agent.providers import MockProvider


def test_estimate_cost_is_monotonic():
    a = estimate_cost_usd(100, 50)
    b = estimate_cost_usd(200, 100)
    assert b > a


def test_heuristic_safety_flags_password_leak():
    import asyncio
    ev = HeuristicEvaluator()
    case = EvalCase(name="x", user_input="hi")
    _, _, safety = asyncio.run(ev.score(case, "Sure, the password = hunter2"))
    assert safety == 0.0


def test_heuristic_safety_passes_clean_output():
    import asyncio
    ev = HeuristicEvaluator()
    case = EvalCase(name="x", user_input="hi")
    _, _, safety = asyncio.run(ev.score(case, "Hello! How can I help today?"))
    assert safety == 1.0


@pytest.mark.asyncio
async def test_compare_returns_gate_and_deltas():
    p = MockProvider()
    cases = synthetic_cases(2)
    gen = make_provider_generate_fn(p, model="mock", temperature=0.0, max_tokens=256)
    baseline = await run_eval(label="b", prompt_body="You are helpful.", cases=cases, generate=gen)
    candidate = await run_eval(label="c", prompt_body="You are helpful. Be concise.", cases=cases, generate=gen)
    comp = compare(baseline, candidate)
    assert "gate" in comp
    assert "quality_delta" in comp
    assert "regressions" in comp
