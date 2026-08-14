"""End-to-end test: input prompt -> output improved prompt.

This is the headline test. It uses the Mock provider so it is fully
deterministic and runs without an API key.
"""
from __future__ import annotations

import pytest

from prope_agent.agents import run_workflow


@pytest.mark.asyncio
async def test_workflow_input_to_improved(provider):
    original = (
        "You are a customer support assistant. "
        "You answer questions about orders, refunds, and shipping."
    )
    initial = {
        "workflow_id": "t1",
        "workspace_id": "default",
        "original_prompt": original,
        "prompt_metadata": {},
    }
    final = await run_workflow(initial_state=initial, provider=provider)

    assert final["stage"] == "explained"
    assert final["candidate_prompt"], "optimizer produced empty prompt"
    assert final["final_prompt"], "explainer set empty final_prompt"

    # Mock provider is conservative — it adds structure, format, guardrails.
    improved = final["final_prompt"]
    assert "Constraints" in improved
    assert "Output format" in improved
    assert "Examples" in improved

    # Quality gate must be one of the allowed values.
    assert final["quality_gate"] in {"PASS", "PASS_WITH_WARNING", "FAIL"}

    # Comparison must include token + cost delta fields.
    comp = final["comparison"]
    assert "quality_delta" in comp
    assert "token_delta_pct" in comp
    assert "cost_delta_pct" in comp

    # Findings + changes are populated.
    assert isinstance(final["findings"], list)
    assert isinstance(final["changes"], list)


@pytest.mark.asyncio
async def test_workflow_handles_empty_metadata(provider):
    initial = {
        "workflow_id": "t2",
        "workspace_id": "default",
        "original_prompt": "Translate this short sentence into Vietnamese.",
        "prompt_metadata": {},
    }
    final = await run_workflow(initial_state=initial, provider=provider)
    assert final["stage"] == "explained"
    assert final["final_prompt"]


@pytest.mark.asyncio
async def test_workflow_records_token_and_cost_deltas(provider):
    initial = {
        "workflow_id": "t3",
        "workspace_id": "default",
        "original_prompt": "Summarize articles.",
        "prompt_metadata": {},
    }
    final = await run_workflow(initial_state=initial, provider=provider)
    assert final["token_delta_percent"] is not None
    assert final["cost_delta_percent"] is not None
