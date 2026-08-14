"""Tests for LLM provider abstraction."""
from __future__ import annotations

import json

import pytest

from prope_agent.providers import LLMMessage, MockProvider


@pytest.mark.asyncio
async def test_mock_provider_returns_improvement():
    p = MockProvider()
    res = await p.generate(
        [LLMMessage(role="user", content="You answer questions.")],
        json_mode=False,
    )
    assert res.provider == "mock"
    assert res.output_tokens > 0
    assert "Constraints" in res.text


@pytest.mark.asyncio
async def test_mock_provider_json_mode_default_is_optimizer_shape():
    """When json_mode is on and no system message hints otherwise, the
    mock returns an optimizer-shaped JSON envelope."""
    p = MockProvider()
    res = await p.generate(
        [LLMMessage(role="user", content="You answer questions.")],
        json_mode=True,
    )
    obj = json.loads(res.text)
    assert "proposed_prompt" in obj
    assert "changes" in obj
    assert "risks" in obj


@pytest.mark.asyncio
async def test_mock_provider_json_mode_analyst_shape():
    """When the system prompt says 'Prompt Analyst' the mock returns an
    analyst-shaped envelope."""
    p = MockProvider()
    res = await p.generate(
        [
            LLMMessage(
                role="system",
                content="You are the Prompt Analyst. Output strict JSON.",
            ),
            LLMMessage(
                role="user",
                content="# Original prompt\n\nYou answer questions.",
            ),
        ],
        json_mode=True,
    )
    obj = json.loads(res.text)
    assert "strengths" in obj
    assert "issues" in obj
    assert "findings" in obj
    assert "risk_level" in obj


@pytest.mark.asyncio
async def test_mock_provider_extracts_prompt_from_template():
    """The mock should look at `# Original prompt` not the whole template."""
    p = MockProvider()
    template = (
        "# Original prompt\n\nYou are a customer support assistant.\n\n"
        "# Analyst report\n\n{...}\n\n# Output\nJSON only."
    )
    res = await p.generate(
        [
            LLMMessage(
                role="system",
                content="You are the Prompt Optimizer. Output strict JSON.",
            ),
            LLMMessage(role="user", content=template),
        ],
        json_mode=True,
    )
    obj = json.loads(res.text)
    proposed = obj["proposed_prompt"]
    assert "customer support assistant" in proposed
    assert "# Analyst report" not in proposed  # template leak guard
