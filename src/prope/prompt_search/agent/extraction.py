"""Metadata extraction for the search index, as a governed agent call.

The pipeline, and which layer is allowed to be wrong:

    truncate_body            deterministic  bounds the input, and SAYS that it did
    load_extraction_prompt   human-governed the instruction a person labelled `production`
    MetadataExtractionProgram probabilistic THE ONLY layer allowed to be wrong
    metadata_of              deterministic  trims, folds, de-duplicates, caps, constrains
    score_extraction         deterministic  grades the result before it is stored

Everything above and below the middle line is code. The agent chooses which
words describe a prompt; it does not choose how many of them there may be, which
language codes are legal, or whether a copied sentence counts as a keyword.

**There is no repair attempt, and that is a decision rather than an omission.**
`prompt_conversion` retries once because its deterministic layer can REJECT an
answer — a malformed block set fails serialization and there is something
specific to send back. Here `metadata_of` never rejects; it cleans. The only
outright failure left is an empty extraction, and the LM runs at temperature 0,
so a second identical request returns the same empty answer at twice the cost.
The job fails, the user retries, and `extraction_total{outcome="invalid_output"}`
counts it.

**Telemetry is fail-open at every site.** `get_langfuse()` returns `None` when
the keys are absent, every span is a `nullcontext` in that case, and `_score`
swallows. A prompt that could not be indexed because its observability backend
was unreachable would be the worst possible trade of this module's two jobs.
"""

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
from prope.prompt_search.agent.evaluation import score_extraction
from prope.prompt_search.agent.prompting import (
    ExtractionPrompt,
    load_extraction_prompt,
)
from prope.prompt_search.domain import ExtractedMetadata
from prope.prompt_search.observability import (
    extraction_body_truncated_total,
    extraction_cost_usd_total,
    extraction_duration_seconds,
    extraction_prompt_fallback_total,
    extraction_quality,
    extraction_tokens_total,
    extraction_total,
)

log = structlog.get_logger(__name__)

__all__ = [
    "APP_AGENT_MODEL",
    "ExtractionContext",
    "ExtractionFailedError",
    "build_program",
    "extract_metadata",
    "preview_extraction",
    "warm_extraction_agent",
]


class ExtractionFailedError(RuntimeError):
    """The agent produced nothing usable, or could not be reached.

    A `RuntimeError` on purpose: `worker.run_indexing_job` maps any exception
    raised while `failure_reason == "agent_error"` onto the job's safe error
    string, and the previous code raised bare `RuntimeError` from the same place.
    Naming it changes nothing for that caller and gives the tests something to
    assert on.
    """


#: `import dspy` costs ELEVEN SECONDS — it pulls litellm, which pulls tokenizers
#: and the OpenTelemetry SDK. `api.py` imports this module at module scope and
#: `app.py` mounts that router at startup, so a module-scope `import dspy` here
#: would put eleven seconds on every process start of every service built from
#: the image, `worker` included.
#:
#: So the DSPy layer loads on first use, in a worker thread, and both entrypoints
#: kick `warm_extraction_agent()` off as a background task so that neither
#: startup nor the first extraction pays it on the critical path.
_agent: ModuleType | None = None


def _import_agent() -> ModuleType:
    global _agent

    if _agent is None:
        from prope.prompt_search.agent import dspy_program

        _agent = dspy_program

    return _agent


async def _load_agent() -> ModuleType:
    """The DSPy layer, imported off the event loop the first time only."""
    if _agent is not None:
        return _agent

    return await asyncio.to_thread(_import_agent)


async def warm_extraction_agent() -> None:
    """Pay the DSPy import at startup, in a thread, without blocking anything.

    Failing is not fatal and is not even interesting: the next extraction
    re-attempts the same import and surfaces the real error where a caller can
    see it.
    """
    await _load_agent()


def build_program(instructions: str) -> Any:
    """Indirection over `dspy_program.build_program`.

    Two jobs: it keeps the DSPy import behind `_import_agent()`, and it gives the
    unit tests one attribute to monkeypatch instead of reaching into another
    module's namespace.
    """
    return _import_agent().build_program(instructions)


@dataclass(frozen=True, slots=True)
class ExtractionContext:
    """Who this extraction is for. Identifiers only — never any of the text."""

    workspace_id: str
    actor_id: str
    prompt_id: str | None = None
    version_id: str | None = None
    job_id: str | None = None
    correlation_id: str | None = None


def _score(span: Any, *, name: str, value: float, data_type: str = "NUMERIC") -> None:
    if span is None:
        return

    try:
        span.score_trace(name=name, value=value, data_type=data_type)
    except Exception:
        # Telemetry is deliberately fail-open.
        pass


async def _request_metadata(
    *,
    title: str,
    purpose: str,
    body: str,
    extraction_prompt: ExtractionPrompt,
    truncated: bool,
) -> ExtractedMetadata:
    """One call to the DSPy program, wrapped in the breaker and one generation span."""
    agent = await _load_agent()
    program = build_program(extraction_prompt.text)
    langfuse = get_langfuse()

    generation_kwargs: dict[str, Any] = {
        "name": "prompt-search.extraction.llm",
        "as_type": "generation",
        "model": APP_AGENT_MODEL,
    }
    if extraction_prompt.managed_prompt is not None:
        # Links this generation to the Langfuse prompt VERSION that produced it,
        # which is what makes "did index quality move when we promoted v4?"
        # answerable at all.
        generation_kwargs["prompt"] = extraction_prompt.managed_prompt

    generation_context = (
        langfuse.start_as_current_observation(**generation_kwargs)
        if langfuse is not None
        else nullcontext(None)
    )

    with generation_context as generation:
        if generation is not None:
            generation.update(
                metadata={
                    "body_characters": len(body),
                    "body_truncated": truncated,
                    "max_output_tokens": agent.MAX_OUTPUT_TOKENS,
                }
            )

        async def invoke() -> Any:
            with agent.usage_tracking():
                return await program.acall(title=title, purpose=purpose, body=body)

        prediction = await call_app_service(invoke)

        usage = agent.usage_of(prediction)
        if usage:
            spend = agent.cost_usd(usage)
            extraction_tokens_total.labels(direction="input").inc(usage["input"])
            extraction_tokens_total.labels(direction="output").inc(usage["output"])
            extraction_cost_usd_total.inc(spend)

            if generation is not None:
                generation.update(usage_details=usage, cost_details={"total": spend})

        # Deliberately DO NOT generation.update(input=..., output=...), and
        # deliberately no OpenInference auto-instrumentation for DSPy: both would
        # ship the prompt body — corporate content under A-020 — and the derived
        # keywords to the telemetry backend. Counts and costs go up; text does not.

        return agent.metadata_of(prediction)


async def _extract(
    *,
    body: str,
    purpose: str,
    title: str,
    context: ExtractionContext | None,
    operation: str,
) -> ExtractedMetadata:
    started = time.perf_counter()
    langfuse = get_langfuse()

    root_context = (
        langfuse.start_as_current_observation(
            name=f"prompt-search.{operation}",
            as_type="span",
        )
        if langfuse is not None
        else nullcontext(None)
    )

    with root_context as root_span:
        attributes_context: Any = nullcontext()

        if langfuse is not None and context is not None:
            attributes_context = propagate_attributes(
                user_id=context.actor_id,
                trace_name=f"prompt-search.{operation}",
                # `operation` separates the request-path preview from the
                # worker's indexing run, which are the same call with different
                # latency budgets and very different traffic shapes.
                tags=["prompt-search", operation],
                metadata={
                    "workspace_id": context.workspace_id,
                    "prompt_id": context.prompt_id,
                    "version_id": context.version_id,
                    "job_id": context.job_id,
                    "correlation_id": context.correlation_id,
                    # Metadata only. Never the body, the purpose or the title.
                    "body_characters": len(body),
                    "purpose_characters": len(purpose),
                },
            )

        with attributes_context:
            agent = await _load_agent()
            trimmed, truncated = agent.truncate_body(body)

            if truncated:
                extraction_body_truncated_total.inc()

            # get_prompt() is synchronous and may fetch. Keep it off the event
            # loop; the worker pays the same thread hop and does not care.
            extraction_prompt = await asyncio.to_thread(load_extraction_prompt)

            if extraction_prompt.is_fallback:
                extraction_prompt_fallback_total.inc()

            if root_span is not None:
                root_span.update(
                    metadata={
                        "extraction_prompt_version": extraction_prompt.version,
                        "extraction_prompt_fallback": extraction_prompt.is_fallback,
                        "body_truncated": truncated,
                    }
                )

            try:
                metadata = await _request_metadata(
                    title=title,
                    purpose=purpose,
                    body=trimmed,
                    extraction_prompt=extraction_prompt,
                    truncated=truncated,
                )
            except Exception as error:
                outcome = "unavailable"
                extraction_total.labels(outcome=outcome).inc()
                extraction_duration_seconds.observe(time.perf_counter() - started)
                _score(root_span, name="extracted", value=0, data_type="BOOLEAN")
                _log(
                    context,
                    operation=operation,
                    outcome=outcome,
                    started=started,
                    error_class=type(error).__name__,
                )
                raise ExtractionFailedError("metadata extraction failed") from error

            extraction_duration_seconds.observe(time.perf_counter() - started)

            if not metadata.keywords:
                # No keywords means the row would be invisible to keyword search
                # and would carry no signal for the hybrid boost. An index row
                # like that is worse than none, because it makes the prompt look
                # indexed while being unfindable.
                outcome = "invalid_output"
                extraction_total.labels(outcome=outcome).inc()
                _score(root_span, name="extracted", value=0, data_type="BOOLEAN")
                _log(
                    context,
                    operation=operation,
                    outcome=outcome,
                    started=started,
                )
                raise ExtractionFailedError("metadata extraction returned no keywords")

            score = score_extraction(
                metadata,
                title=title,
                purpose=purpose,
                body=trimmed,
            )
            extraction_quality.observe(score.total)
            extraction_total.labels(outcome="success").inc()

            _score(root_span, name="extracted", value=1, data_type="BOOLEAN")
            _score(root_span, name="extraction_quality", value=score.total)
            _score(root_span, name="completeness", value=score.completeness)
            _score(root_span, name="groundedness", value=score.groundedness)
            _score(root_span, name="hygiene", value=score.hygiene)

            _log(
                context,
                operation=operation,
                outcome="success",
                started=started,
                quality_score=round(score.total, 3),
                keywords_count=len(metadata.keywords),
                topics_count=len(metadata.topics),
                body_truncated=truncated,
                prompt_version=extraction_prompt.version,
                fallback=extraction_prompt.is_fallback,
            )

            return metadata


def _log(
    context: ExtractionContext | None,
    *,
    operation: str,
    outcome: str,
    started: float,
    error_class: str | None = None,
    quality_score: float | None = None,
    keywords_count: int | None = None,
    topics_count: int | None = None,
    body_truncated: bool | None = None,
    prompt_version: int | None = None,
    fallback: bool | None = None,
) -> None:
    """One JSON line per extraction. Identifiers and numbers, never content.

    Every key is in `prope.observability.LOGGABLE_FIELDS` and
    `tests/architecture/test_no_content_reaches_a_log_line_by_construction.py`
    proves it statically. `keywords_count` is here and `keywords` can never be:
    the lock file is explicit that extracted metadata may carry sensitive terms
    out of the body, so the count is the most this line may say about it.

    **Every optional field is spelled out rather than collected into `**fields`.**
    A starred payload passes type checking and defeats the architecture test
    entirely — the allow-list can only be enforced against keywords a parser can
    see. The verbosity is the mechanism, not an accident of style.
    """
    log.info(
        f"prompt_search.{operation}.completed",
        outcome=outcome,
        duration_ms=int((time.perf_counter() - started) * 1000),
        model_name=APP_AGENT_MODEL,
        workspace_id=context.workspace_id if context else None,
        actor_id=context.actor_id if context else None,
        prompt_id=context.prompt_id if context else None,
        version_id=context.version_id if context else None,
        job_id=context.job_id if context else None,
        request_id=context.correlation_id if context else None,
        error_class=error_class,
        quality_score=quality_score,
        keywords_count=keywords_count,
        topics_count=topics_count,
        body_truncated=body_truncated,
        prompt_version=prompt_version,
        fallback=fallback,
    )


async def extract_metadata(
    body: str,
    purpose: str,
    title: str,
    *,
    context: ExtractionContext | None = None,
) -> ExtractedMetadata:
    """Extract index metadata for a prompt. The worker's path.

    Positional arguments are preserved from the pre-DSPy signature so that
    `worker.run_indexing_job` and the existing tests keep calling it unchanged.
    """
    return await _extract(
        body=body,
        purpose=purpose,
        title=title,
        context=context,
        operation="index-extraction",
    )


async def preview_extraction(
    body: str,
    purpose: str,
    title: str,
    *,
    context: ExtractionContext | None = None,
) -> ExtractedMetadata:
    """Extract without storing. The `GET /index/preview` path.

    Byte-identical work to `extract_metadata`; the difference is the trace name
    and tag, and that difference is the point. Preview runs on the request path
    against a p95 a user is waiting on, indexing runs in the worker against a
    5 s budget nobody watches, and a dashboard that added them together would
    describe neither.
    """
    return await _extract(
        body=body,
        purpose=purpose,
        title=title,
        context=context,
        operation="preview-extraction",
    )
