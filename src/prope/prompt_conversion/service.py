"""App Agent orchestration for converting untrusted source into safe XML.

The pipeline, and which layer is allowed to be wrong:

    normalize_source        deterministic   refuses bad syntax before spending a token
    load_conversion_prompt  human-governed  the instruction a person labelled `production`
    PromptConversionProgram probabilistic   THE ONLY layer allowed to be wrong
    AgentOutput             deterministic   shape: six types, at most one of each
    serialize_agent_output  deterministic   order, escaping, variables, canonical XML

Everything above and below the middle line is code. The agent chooses which
sentence is an instruction and which is a constraint; it does not choose the
order blocks are written in, whether `<` is escaped, or whether the result
parses — and one bounded repair attempt exists precisely so that the
deterministic layers can send a probabilistic layer back to try again rather
than accept what it produced.

Telemetry is fail-open at every site: `get_langfuse()` returns `None` when the
keys are absent, every span is a `nullcontext` in that case, and `_score_trace`
swallows. A conversion that failed because its observability backend was
unreachable would be the worst possible trade of this module's two jobs.
"""

import asyncio
import time
from contextlib import nullcontext
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import structlog
from langfuse import propagate_attributes
from pydantic import ValidationError

from prope.app_agent import APP_AGENT_MODEL
from prope.app_agent.circuit import CircuitBreaker, CircuitOpenError
from prope.prompt_conversion.domain import (
    AgentOutput,
    InvalidAgentOutputError,
    InvalidSourceError,
    NormalizedSource,
    content_coverage,
    normalize_source,
    serialize_agent_output,
)
from prope.prompt_conversion.observability import (
    agent_circuit_open,
    conversion_cost_usd_total,
    conversion_coverage_ratio,
    conversion_duration_seconds,
    conversion_prompt_fallback_total,
    conversion_repair_total,
    conversion_tokens_total,
    conversion_total,
)
from prope.prompt_conversion.prompting import (
    ConversionPrompt,
    load_conversion_prompt,
)
from prope.prompt_conversion.telemetry import get_langfuse

log = structlog.get_logger()

#: The CANONICAL XML contract's version — six block types, no attributes, no
#: nesting — recorded on every revision as `conversion_schema_version`
#: (alembic 0013). It describes the stored artifact, so it does NOT move when
#: the agent behind it changes: swapping a hand-written completion call for a
#: DSPy program produced byte-identical output shapes, and bumping this would
#: have told every reader of an old revision that their XML meant something
#: different than it does.
SCHEMA_VERSION = "2"

__all__ = [
    "SCHEMA_VERSION",
    "AgentUnavailableError",
    "ConversionContext",
    "build_program",
    "convert_source",
    "structured_output_schema",
    "warm_conversion_agent",
]

#: `import dspy` costs ELEVEN SECONDS — it pulls litellm, which pulls tokenizers
#: and the OpenTelemetry SDK — and `app.py` imports this module's router at
#: startup, so a module-scope import would put that on every process start of
#: every service built from the image, including `worker`, which never converts.
#:
#: So the DSPy layer is loaded on first use, in a worker thread, and the lifespan
#: kicks `warm_conversion_agent()` off as a background task so that neither
#: startup nor the first conversion pays it on the critical path. The cost is one
#: level of indirection through `_load_agent()`; the alternative was an
#: eleven-second regression in a healthcheck's budget.
_agent: ModuleType | None = None


def _import_agent() -> ModuleType:
    global _agent

    if _agent is None:
        from prope.prompt_conversion import dspy_program

        _agent = dspy_program

    return _agent


async def _load_agent() -> ModuleType:
    """The DSPy layer, imported off the event loop the first time only."""
    if _agent is not None:
        return _agent

    return await asyncio.to_thread(_import_agent)


async def warm_conversion_agent() -> None:
    """Pay the DSPy import at startup, in a thread, without blocking anything.

    Called as a background task from `app.lifespan`. Failing is not fatal and is
    not even interesting: the next conversion re-attempts the same import and
    surfaces the real error where a caller can see it.
    """
    await _load_agent()


def build_program(instructions: str) -> Any:
    """Indirection over `dspy_program.build_program`.

    Two jobs: it keeps the DSPy import behind `_import_agent()`, and it gives
    the unit tests one attribute to monkeypatch instead of reaching into another
    module's namespace.
    """
    return _import_agent().build_program(instructions)


class AgentUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ConversionContext:
    workspace_id: str
    actor_id: str
    prompt_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class RepairContext:
    validation_error: str
    prior_block_types: tuple[str, ...]


def _set_circuit_metric(is_open: bool) -> None:
    agent_circuit_open.set(1 if is_open else 0)


_breaker = CircuitBreaker(on_state_change=_set_circuit_metric)


def _repair_feedback(repair: RepairContext | None) -> str:
    """The repair turn's input field. Empty string on the first attempt.

    Carries the validation failure and the SHAPE of the previous answer — its
    block types — and never its content. The hand-written call this replaced
    echoed 6,000 characters of the model's prior output back at it, which put a
    second copy of corporate prompt text on the wire for no measured gain; the
    model still has the source in `source_text` and the instruction says to
    regenerate from it rather than patch.
    """
    if repair is None:
        return ""

    previous = ", ".join(repair.prior_block_types) or "none"
    return (
        "The previous attempt failed Prope's deterministic validation and was "
        "discarded. Regenerate the complete result from the source; do not "
        "patch the previous answer.\n"
        f"Previous block types: {previous}\n"
        f"Validation failure: {repair.validation_error}"
    )


async def _request_output(
    source: NormalizedSource,
    conversion_prompt: ConversionPrompt,
    *,
    attempt: int,
    repair: RepairContext | None = None,
) -> AgentOutput:
    """One call to the DSPy program, wrapped in the breaker and one generation span."""
    agent = await _load_agent()
    program = build_program(conversion_prompt.text)
    langfuse = get_langfuse()

    generation_kwargs: dict[str, Any] = {
        "name": "prompt-conversion.llm",
        "as_type": "generation",
        "model": APP_AGENT_MODEL,
    }
    if conversion_prompt.managed_prompt is not None:
        # Links this generation to the Langfuse prompt VERSION that produced it,
        # which is what makes "did the numbers move when we promoted v7?"
        # answerable at all.
        generation_kwargs["prompt"] = conversion_prompt.managed_prompt

    generation_context = (
        langfuse.start_as_current_observation(**generation_kwargs)
        if langfuse is not None
        else nullcontext(None)
    )

    with generation_context as generation:
        if generation is not None:
            generation.update(
                metadata={
                    "attempt": attempt,
                    "repair": repair is not None,
                    "source_format": source.format,
                    "schema_version": SCHEMA_VERSION,
                    "max_output_tokens": agent.MAX_OUTPUT_TOKENS,
                }
            )

        async def invoke() -> Any:
            with agent.usage_tracking():
                return await program.acall(
                    source_format=source.format,
                    source_text=source.text,
                    repair_feedback=_repair_feedback(repair),
                )

        prediction = await _breaker.call(invoke)

        usage = agent.usage_of(prediction)
        if usage:
            spend = agent.cost_usd(usage)
            conversion_tokens_total.labels(direction="input").inc(usage["input"])
            conversion_tokens_total.labels(direction="output").inc(usage["output"])
            conversion_cost_usd_total.inc(spend)

            if generation is not None:
                generation.update(
                    usage_details=usage,
                    cost_details={"total": spend},
                )

        # Deliberately DO NOT generation.update(input=..., output=...), and
        # deliberately no OpenInference auto-instrumentation for DSPy: both would
        # ship the rendered prompt and the completion — corporate prompt bodies
        # under A-020 — to the telemetry backend.

        blocks = agent.blocks_of(prediction)

        if not blocks:
            raise InvalidAgentOutputError("agent returned an empty response")

        try:
            return AgentOutput(blocks=blocks)
        except ValidationError as error:
            raise InvalidAgentOutputError(
                "agent returned an invalid structured response"
            ) from error


def _score_trace(
    span: Any,
    *,
    name: str,
    value: float,
    data_type: str = "BOOLEAN",
) -> None:
    if span is None:
        return

    try:
        span.score_trace(name=name, value=value, data_type=data_type)
    except Exception:
        # Telemetry is deliberately fail-open.
        pass


async def convert_source(
    source_text: str,
    source_format: str,
    *,
    context: ConversionContext | None = None,
) -> tuple[str, str, str]:
    started = time.perf_counter()
    langfuse = get_langfuse()

    root_context = (
        langfuse.start_as_current_observation(
            name="prompt-conversion",
            as_type="span",
        )
        if langfuse is not None
        else nullcontext(None)
    )

    with root_context as root_span:
        attributes_context = nullcontext()

        if langfuse is not None and context is not None:
            attributes_context = propagate_attributes(
                user_id=context.actor_id,
                trace_name="prompt-conversion",
                tags=["prompt-conversion"],
                metadata={
                    "workspace_id": context.workspace_id,
                    "prompt_id": context.prompt_id,
                    "correlation_id": context.correlation_id,
                    # Metadata only. Never source_text.
                    "source_characters": len(source_text),
                    "source_format": source_format,
                    "schema_version": SCHEMA_VERSION,
                },
            )

        with attributes_context:
            try:
                source = normalize_source(
                    source_text,
                    source_format,
                )
            except InvalidSourceError:
                conversion_total.labels(
                    outcome="invalid_source"
                ).inc()
                _score_trace(
                    root_span,
                    name="source_valid",
                    value=0,
                )
                _log_outcome(
                    context,
                    outcome="invalid_source",
                    started=started,
                    source_format=source_format,
                )
                raise

            _score_trace(
                root_span,
                name="source_valid",
                value=1,
            )

            # get_prompt() is synchronous. Avoid blocking FastAPI's event loop
            # on the initial/cache-miss fetch.
            conversion_prompt = await asyncio.to_thread(
                load_conversion_prompt
            )

            if conversion_prompt.is_fallback:
                conversion_prompt_fallback_total.inc()

            if root_span is not None:
                root_span.update(
                    metadata={
                        "conversion_prompt_version":
                            conversion_prompt.version,
                        "conversion_prompt_fallback":
                            conversion_prompt.is_fallback,
                    }
                )

            prior_error: InvalidAgentOutputError | None = None
            prior_block_types: tuple[str, ...] = ()
            repairs = 0
            coverage = 0.0

            try:
                for attempt in range(1, 3):
                    repair = None

                    if prior_error is not None:
                        repairs += 1
                        repair = RepairContext(
                            validation_error=str(prior_error),
                            prior_block_types=prior_block_types,
                        )

                    # The request is INSIDE the retryable block, not above it.
                    # An empty completion, a truncated one, and a completion
                    # that drops a variable are the same event from the
                    # author's side — the model produced nothing usable — and
                    # only the third of them is raised by the serializer. With
                    # the call above this `try`, an empty response spent the
                    # attempt budget without ever using it.
                    output = None

                    try:
                        output = await _request_output(
                            source,
                            conversion_prompt,
                            attempt=attempt,
                            repair=repair,
                        )
                        xml = serialize_agent_output(
                            output,
                            source_text=source.text,
                        )
                        coverage = content_coverage(
                            output,
                            source_text=source.text,
                            source_format=source.format,
                        )
                        break
                    except InvalidAgentOutputError as error:
                        prior_error = error
                        prior_block_types = (
                            tuple(block.type for block in output.blocks)
                            if output is not None
                            else ()
                        )

                        if attempt == 2:
                            raise
                else:  # pragma: no cover
                    raise InvalidAgentOutputError(
                        "agent output could not be repaired"
                    )

            except InvalidAgentOutputError:
                conversion_total.labels(
                    outcome="invalid_output"
                ).inc()
                _score_trace(
                    root_span,
                    name="conversion_valid",
                    value=0,
                )
                _log_outcome(
                    context,
                    outcome="invalid_output",
                    started=started,
                    source_format=source.format,
                )
                raise

            except (CircuitOpenError, TimeoutError) as error:
                conversion_total.labels(
                    outcome="unavailable"
                ).inc()
                _log_outcome(
                    context,
                    outcome="unavailable",
                    started=started,
                    source_format=source.format,
                )
                raise AgentUnavailableError(
                    "prompt conversion service is unavailable"
                ) from error

            except Exception as error:
                conversion_total.labels(
                    outcome="unavailable"
                ).inc()
                _log_outcome(
                    context,
                    outcome="unavailable",
                    started=started,
                    source_format=source.format,
                )
                raise AgentUnavailableError(
                    "prompt conversion service is unavailable"
                ) from error

            finally:
                conversion_duration_seconds.observe(
                    time.perf_counter() - started
                )

            if repairs:
                conversion_repair_total.inc()

            conversion_coverage_ratio.observe(coverage)

            _score_trace(
                root_span,
                name="conversion_valid",
                value=1,
            )
            _score_trace(
                root_span,
                name="repair_used",
                value=1 if repairs else 0,
            )
            _score_trace(
                root_span,
                name="content_coverage",
                value=coverage,
                data_type="NUMERIC",
            )

            conversion_total.labels(
                outcome="success"
            ).inc()

            _log_outcome(
                context,
                outcome="success",
                started=started,
                source_format=source.format,
                attempt=repairs + 1,
                coverage_ratio=round(coverage, 3),
            )

            return xml, APP_AGENT_MODEL, SCHEMA_VERSION


def _log_outcome(
    context: ConversionContext | None,
    *,
    outcome: str,
    started: float,
    source_format: str,
    attempt: int | None = None,
    coverage_ratio: float | None = None,
) -> None:
    """One JSON line per conversion. Identifiers and numbers, never content.

    Every key is in `prope.observability.LOGGABLE_FIELDS` and
    `tests/architecture/test_no_content_reaches_a_log_line_by_construction.py`
    proves it statically. `source_format` is here and `source_text` can never be:
    the first is a four-value closed set, the second is the thing the whole
    module exists to keep out of logs (A-046).
    """
    log.info(
        "prompt_conversion.completed",
        outcome=outcome,
        duration_ms=int((time.perf_counter() - started) * 1000),
        model_name=APP_AGENT_MODEL,
        source_format=source_format,
        workspace_id=context.workspace_id if context else None,
        actor_id=context.actor_id if context else None,
        prompt_id=context.prompt_id if context else None,
        request_id=context.correlation_id if context else None,
        attempt=attempt,
        coverage_ratio=coverage_ratio,
    )


def structured_output_schema() -> dict[str, Any]:
    """Expose the Pydantic-derived schema for documentation/tests."""
    return AgentOutput.model_json_schema()
