"""The comparison agent calls, governed and fail-soft.

Same layering as `extraction.py`, and the same rule about which layer may be
wrong:

    present / truncate          deterministic  bounds the input, and says that it did
    load_*_prompt               human-governed the instruction a person labelled `production`
    Adjudication / Descriptor   probabilistic  THE ONLY layer allowed to be wrong
    judgements_of / descriptor_of  deterministic  drops unknown labels, relations, reasons, values

**Both functions fail soft, and that is a product decision rather than defensive
coding.** A duplicate check is advice, not a gate: the workspace may have nothing
indexed and the app agent may be down, and neither is a reason to refuse somebody
their own prompt. When adjudication is unavailable the pipeline reports its
candidates as *related, unverified* with a coverage finding saying so — which is
the honest answer — instead of either claiming duplicates it never judged or
claiming a clean bill of health nothing established.

**Prompt text does not reach the telemetry backend.** Spans carry counts, costs
and identifiers. Never `input=` / `output=`, and no OpenInference
auto-instrumentation, for the same reason as `extraction.py`: prompt bodies are
corporate content under A-020.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import nullcontext
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import structlog
from langfuse import propagate_attributes

from prope.app_agent import APP_AGENT_MODEL
from prope.app_agent.telemetry import get_langfuse
from prope.prompt_search.agent.base import call_app_service
from prope.prompt_search.agent.comparison_prompting import (
    ManagedPrompt,
    load_adjudication_prompt,
    load_output_contract_prompt,
)
from prope.prompt_search.comparison.output_contract import (
    UNSPECIFIED,
    WHOLE_TEXT,
    OutputDescriptor,
)
from prope.prompt_search.observability import (
    adjudication_cost_usd_total,
    adjudication_duration_seconds,
    adjudication_prompt_fallback_total,
    adjudication_total,
    descriptor_total,
)

log = structlog.get_logger(__name__)

__all__ = [
    "ComparisonContext",
    "adjudicate",
    "extract_output_descriptor",
    "warm_comparison_agent",
]

#: How much of one prompt's DECLARED OUTPUT BLOCK the descriptor extractor reads.
#:
#: **Renamed, because it used to share a name with the adjudicator's budget and
#: they mean different things.** That one is in `comparison.pipeline` and governs
#: how much of a whole prompt the adjudicator sees; this one bounds a single
#: `<output_format>` (or the `<instructions>` fallback) before it is turned into
#: a descriptor. Two constants named `PRESENTATION_CHARACTER_LIMIT` in one module
#: tree is how a measured change to one silently fails to reach the other.
#:
#: 1,200 is generous for its actual job: an output contract that needs more than
#: a thousand characters to state is a readiness finding about the prompt, not a
#: budget problem here.
DECLARED_OUTPUT_CHARACTER_LIMIT = 1_200

#: The same job over a WHOLE unstructured prompt, which is a different budget.
#:
#: A pasted prompt reaches this stage under `output_contract.WHOLE_TEXT`, and
#: 1,200 characters of one is not a generous allowance, it is the opening
#: paragraph — the role sentence and the "when to use this" bullets, which is
#: the genre boilerplate the contract is least likely to be in. Prompts state
#: what they return near the **end**, so a head-only cut removes exactly the
#: part being looked for.
PROSE_CHARACTER_LIMIT = 8_000


def _prose_window(text: str, limit: int) -> str:
    """Head and tail of an over-long body, with the middle marked as removed.

    Head as well as tail because "return JSON" sometimes appears in the opening
    contract statement and the closing reminder is a repeat, and because a
    window that begins mid-sentence reads as a truncated instruction to a model
    that is being asked what the instruction says. The marker is there so the
    extractor can tell a gap from a discontinuity in the author's writing.
    """
    if len(text) <= limit:
        return text
    head = limit // 3
    gap = len(text) - limit
    marker = f"[... {gap} characters omitted ...]"
    return f"{text[:head]}\n\n{marker}\n\n{text[-(limit - head):]}"

#: `import dspy` costs eleven seconds — litellm, tokenizers, the OTel SDK. The
#: API router imports this module's package at startup, so the DSPy layer loads
#: on first use, in a worker thread, and `warm_comparison_agent()` pays it in the
#: background. Identical reasoning to `extraction._agent`; identical shape, so
#: that the two cannot drift.
_agent: ModuleType | None = None


def _import_agent() -> ModuleType:
    global _agent

    if _agent is None:
        from prope.prompt_search.agent import comparison_program

        _agent = comparison_program

    return _agent


async def _load_agent() -> ModuleType:
    if _agent is not None:
        return _agent
    return await asyncio.to_thread(_import_agent)


async def warm_comparison_agent() -> None:
    """Pay the DSPy import at startup, in a thread, without blocking anything."""
    await _load_agent()


@dataclass(frozen=True, slots=True)
class ComparisonContext:
    """Who this comparison is for. Identifiers only — never any of the text."""

    workspace_id: str
    actor_id: str
    correlation_id: str | None = None


def _attributes(context: ComparisonContext | None, *, operation: str, **metadata: Any) -> Any:
    langfuse = get_langfuse()
    if langfuse is None or context is None:
        return nullcontext()
    return propagate_attributes(
        user_id=context.actor_id,
        trace_name=f"prompt-search.{operation}",
        tags=["prompt-search", operation],
        metadata={
            "workspace_id": context.workspace_id,
            "correlation_id": context.correlation_id,
            **metadata,
        },
    )


def _generation(prompt: ManagedPrompt, *, name: str) -> Any:
    langfuse = get_langfuse()
    if langfuse is None:
        return nullcontext(None)
    kwargs: dict[str, Any] = {
        "name": name,
        "as_type": "generation",
        "model": APP_AGENT_MODEL,
    }
    if prompt.managed_prompt is not None:
        # Links this generation to the Langfuse prompt VERSION that produced it,
        # which is what makes "did duplicate detection move when we promoted v3?"
        # answerable at all.
        kwargs["prompt"] = prompt.managed_prompt
    return langfuse.start_as_current_observation(**kwargs)


def _record_usage(agent: ModuleType, prediction: Any, generation: Any) -> None:
    usage = agent.usage_of(prediction)
    if not usage:
        return
    spend = agent.cost_usd(usage)
    adjudication_cost_usd_total.inc(spend)
    if generation is not None:
        generation.update(usage_details=usage, cost_details={"total": spend})


async def adjudicate(
    *,
    incoming_prompt: str,
    candidates: list[tuple[str, str, str]],
    context: ComparisonContext | None = None,
) -> dict[str, tuple[str, tuple[str, ...]]]:
    """Judge up to five candidates against the incoming prompt, in ONE call.

    ``candidates`` is ``(label, title, presentation)`` — the label is positional
    (``C1``…), never a prompt id: an id means nothing to a model, costs tokens in
    every mention, and a hallucinated one would address a prompt that was never
    in the candidate set.

    Returns ``{label: (relation, reasons)}`` for the candidates the model judged
    validly, and **an empty mapping when the agent is unavailable or returned
    nothing usable.** A partial answer is returned as-is: a candidate missing
    from the mapping is reported as unadjudicated rather than guessed at.

    **One joint call, not five.** The adjudicator is already the cross-encoder —
    it scores the candidates against the same incoming prompt in one context,
    which is strictly more capable than a relevance reranker, because the
    question is not relevance but *same job across task, inputs, output
    contract, domain*. A reranker model would mean either an eighth service
    against ADR-0033 or a third-party API with its own credential-ownership
    question, for a marginal gain on a ``20 -> 5`` step.
    """
    if not candidates:
        return {}

    started = time.perf_counter()
    agent = await _load_agent()
    prompt = await asyncio.to_thread(load_adjudication_prompt)
    if prompt.is_fallback:
        adjudication_prompt_fallback_total.inc()

    labels = tuple(label for label, _, _ in candidates)
    briefs = [
        agent.CandidateBrief(label=label, title=title[:200], prompt=presentation)
        for label, title, presentation in candidates
    ]

    with _attributes(context, operation="adjudication", candidate_count=len(briefs)):
        try:
            program = agent.build_adjudication_program(prompt.text)
            with _generation(prompt, name="prompt-search.adjudication.llm") as generation:
                if generation is not None:
                    generation.update(
                        metadata={
                            "candidate_count": len(briefs),
                            "incoming_characters": len(incoming_prompt),
                        }
                    )

                async def invoke() -> Any:
                    with agent.usage_tracking():
                        return await program.acall(
                            incoming_prompt=incoming_prompt, candidates=briefs
                        )

                prediction = await call_app_service(invoke)
                _record_usage(agent, prediction, generation)
                judged = agent.judgements_of(prediction, labels=labels)
        except Exception as error:
            adjudication_total.labels(outcome="unavailable").inc()
            adjudication_duration_seconds.observe(time.perf_counter() - started)
            log.warning(
                "prompt_search.adjudication_unavailable",
                workspace_id=context.workspace_id if context else None,
                actor_id=context.actor_id if context else None,
                candidate_count=len(briefs),
                error_class=type(error).__name__,
            )
            return {}

    outcome = "ok" if len(judged) == len(labels) else ("partial" if judged else "invalid_output")
    adjudication_total.labels(outcome=outcome).inc()
    adjudication_duration_seconds.observe(time.perf_counter() - started)
    log.info(
        "prompt_search.adjudicated",
        workspace_id=context.workspace_id if context else None,
        actor_id=context.actor_id if context else None,
        candidate_count=len(briefs),
        judged_count=len(judged),
        outcome=outcome,
        duration_ms=int((time.perf_counter() - started) * 1000),
        prompt_version=prompt.version,
    )
    return judged


async def extract_output_descriptor(
    *,
    declared_output: str,
    source_block: str,
    context: ComparisonContext | None = None,
) -> OutputDescriptor | None:
    """One revision's declared output contract as a normalized descriptor.

    ``None`` when the agent is unavailable, which stage 2b reports as *not
    established* — distinct from a descriptor that exists and says
    ``unspecified``, which is the prompt itself being silent and is a finding
    about the prompt.

    Cheap and cached upstream: this runs once per revision at index time and once
    per import for the incoming body, never once per pair. An extractor shown two
    blocks at once is drawn toward finding them alike, which is the same
    anchoring problem as judging N pairs holistically.
    """
    text = declared_output.strip()
    if not text or source_block == UNSPECIFIED:
        return None

    agent = await _load_agent()
    prompt = await asyncio.to_thread(load_output_contract_prompt)
    if prompt.is_fallback:
        adjudication_prompt_fallback_total.inc()

    shown = (
        _prose_window(text, PROSE_CHARACTER_LIMIT)
        if source_block == WHOLE_TEXT
        else text[:DECLARED_OUTPUT_CHARACTER_LIMIT]
    )

    with _attributes(context, operation="output-contract", declared_characters=len(shown)):
        try:
            program = agent.build_descriptor_program(prompt.text)
            with _generation(prompt, name="prompt-search.output-contract.llm") as generation:
                if generation is not None:
                    generation.update(metadata={"declared_characters": len(shown)})

                async def invoke() -> Any:
                    with agent.usage_tracking():
                        return await program.acall(declared_output=shown)

                prediction = await call_app_service(invoke)
                _record_usage(agent, prediction, generation)
                descriptor = agent.descriptor_of(prediction, source_block=source_block)
        except Exception as error:
            descriptor_total.labels(outcome="unavailable").inc()
            log.warning(
                "prompt_search.output_contract_unavailable",
                workspace_id=context.workspace_id if context else None,
                error_class=type(error).__name__,
            )
            return None

    descriptor_total.labels(outcome="empty" if descriptor.is_empty else "ok").inc()
    return descriptor
