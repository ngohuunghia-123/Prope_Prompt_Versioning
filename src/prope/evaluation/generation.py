"""Drafting eval cases from a prompt body. The service half of the drafter.

Holds everything about the drafting agent that is not the DSPy program itself:
the lazy import, the circuit breaker, and — the part that matters — the gate
between what a model returned and what enters the library.

**Nothing the model writes is trusted to be valid.** Every drafted assertion is
coerced and then run through :func:`compile_assertions`, the same gate a
hand-written suite goes through. An assertion naming a type that does not exist,
a regex that will not compile, a ``max_length`` that is not a number: each is
dropped, counted, and the case keeps its remaining assertions. A case left with
no assertions at all is dropped too, because an empty case is not a pass
(A-059's reasoning, one level up) — it is a case that cannot fail, which is
worse than no case.

**The result is a dataset, never an attachment.** A drafted set lands in the
library and somebody ticks it, or edits it first. The alternative — generating
straight onto the prompt's yardstick — would mean a model deciding what a prompt
is measured against, which is not a thing this product does.

**Cost lands on Prope's own meter, not the workspace's.** Drafting calls
`APP_OPENAI_*`, the app-owned model, exactly as conversion and search do. It is
not a `ledger.call_record` and must never appear in a cost delta: the delta
compares what two revisions cost to *serve*, and a convenience feature's bill
inside that number would make a revision look more expensive because somebody
pressed a button.
"""

import asyncio
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import structlog

from prope.app_agent.circuit import CircuitBreaker, CircuitOpenError
from prope.app_agent.client import APP_AGENT_MODEL
from prope.evaluation.assertions import compile_assertions
from prope.evaluation.domain import (
    MAX_CASES_PER_SUITE,
    AssertionPatternInvalid,
    AssertionSpec,
    AssertionType,
    CaseDraft,
    OutputModality,
)
from prope.evaluation.observability import (
    drafter_cases_dropped_total,
    drafter_circuit_open,
    drafter_cost_usd_total,
    drafter_total,
)

log = structlog.get_logger(__name__)

__all__ = [
    "DEFAULT_CASE_TARGET",
    "DrafterUnavailableError",
    "DraftOutcome",
    "draft_cases",
]

#: Enough to be worth reading and few enough to be worth editing. The suite cap
#: is twenty; asking for all twenty produces a long tail of near-duplicates that
#: somebody then has to delete one at a time.
DEFAULT_CASE_TARGET = 8

#: Only the types a drafted case may use. The full registry has eleven, but
#: `max_latency`, `max_cost`, `asset_count`, `asset_type` and `json_schema`
#: describe the *deployment* rather than the prompt — a model guessing a latency
#: budget or a cost ceiling is inventing an SLO nobody agreed to, and it would
#: fail runs for reasons that have nothing to do with the prompt. A person can
#: still add them in the editor.
DRAFTABLE_TYPES: frozenset[AssertionType] = frozenset(
    {
        AssertionType.SUBSTRING,
        AssertionType.REQUIRED_PHRASE,
        AssertionType.FORBIDDEN_PHRASE,
        AssertionType.REGEX,
        AssertionType.MAX_LENGTH,
        AssertionType.EXACT,
    }
)


class DrafterUnavailableError(RuntimeError):
    """The agent could not be called. Distinct from "it returned nothing usable"."""


@dataclass(frozen=True, slots=True)
class DraftOutcome:
    cases: tuple[CaseDraft, ...]
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    dropped_cases: int
    dropped_assertions: int


#: `import dspy` costs eleven seconds — it pulls litellm, which pulls tokenizers
#: and the OpenTelemetry SDK — and `app.py` imports this module's router at
#: startup. `prompt_conversion.service` documents this at length and pays the
#: cost in a background task; the drafter deliberately does NOT, because
#: conversion is on the registration path and drafting is a button somebody
#: presses occasionally. `_load_agent` runs the import in a worker thread, so
#: the first draft pays eleven seconds without blocking the event loop, and
#: every draft after it pays nothing.
_agent: ModuleType | None = None


def _import_agent() -> ModuleType:
    global _agent

    if _agent is None:
        from prope.evaluation import dspy_program

        _agent = dspy_program

    return _agent


async def _load_agent() -> ModuleType:
    if _agent is not None:
        return _agent
    return await asyncio.to_thread(_import_agent)


def _set_circuit_metric(is_open: bool) -> None:
    drafter_circuit_open.set(1 if is_open else 0)


_breaker = CircuitBreaker(on_state_change=_set_circuit_metric)


def _coerce_value(assertion_type: AssertionType, raw: str) -> Any:
    """A drafted value is always a string; two types need it not to be."""
    if assertion_type is AssertionType.MAX_LENGTH:
        return int(raw.strip())
    return raw


def _specs(raw_assertions: Any) -> tuple[list[AssertionSpec], int]:
    """Drafted assertions that survive coercion, and how many did not."""
    specs: list[AssertionSpec] = []
    dropped = 0

    for entry in raw_assertions or []:
        raw_type = getattr(entry, "type", None) or (
            entry.get("type") if isinstance(entry, dict) else None
        )
        raw_value = getattr(entry, "value", None)
        if raw_value is None and isinstance(entry, dict):
            raw_value = entry.get("value")

        try:
            assertion_type = AssertionType(str(raw_type))
        except ValueError:
            drafter_cases_dropped_total.labels(reason="unknown_assertion_type").inc()
            dropped += 1
            continue

        if assertion_type not in DRAFTABLE_TYPES:
            drafter_cases_dropped_total.labels(reason="assertion_type_not_draftable").inc()
            dropped += 1
            continue

        try:
            value = _coerce_value(assertion_type, str(raw_value or ""))
        except ValueError:
            drafter_cases_dropped_total.labels(reason="assertion_value_not_coercible").inc()
            dropped += 1
            continue

        if value == "" and assertion_type is not AssertionType.MAX_LENGTH:
            drafter_cases_dropped_total.labels(reason="assertion_value_empty").inc()
            dropped += 1
            continue

        specs.append(AssertionSpec(type=assertion_type, value=value))

    return specs, dropped


def _drafts(raw_cases: Any, modality: OutputModality) -> tuple[list[CaseDraft], int, int]:
    """Everything from one prediction that is fit to store."""
    drafts: list[CaseDraft] = []
    dropped_cases = 0
    dropped_assertions = 0

    for entry in (raw_cases or [])[:MAX_CASES_PER_SUITE]:
        name = str(getattr(entry, "name", "") or "").strip()
        input_text = str(getattr(entry, "input_text", "") or "").strip()
        if not name or not input_text:
            drafter_cases_dropped_total.labels(reason="case_incomplete").inc()
            dropped_cases += 1
            continue

        specs, dropped = _specs(getattr(entry, "assertions", None))
        dropped_assertions += dropped

        # The same gate a hand-written suite goes through. A drafted regex that
        # does not compile is caught here rather than on somebody's first run.
        try:
            compiled = compile_assertions(tuple(specs), modality, len(drafts) + 1)
        except AssertionPatternInvalid:
            drafter_cases_dropped_total.labels(reason="assertion_would_not_compile").inc()
            dropped_assertions += len(specs)
            compiled = ()

        if not compiled:
            # An assertion-less case cannot fail, which is worse than no case:
            # it inflates the pass count with a check nobody made.
            drafter_cases_dropped_total.labels(reason="case_left_without_assertions").inc()
            dropped_cases += 1
            continue

        drafts.append(
            CaseDraft(
                name=name[:200],
                input_messages=({"role": "user", "content": input_text},),
                assertions=tuple(compiled),
            )
        )

    return drafts, dropped_cases, dropped_assertions


async def draft_cases(
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    prompt_title: str,
    prompt_body: str,
    brief: str = "",
    modality: OutputModality = OutputModality.TEXT,
    case_target: int = DEFAULT_CASE_TARGET,
) -> DraftOutcome:
    """One drafting call. Raises :class:`DrafterUnavailableError` when it cannot run.

    Returning zero cases is a *successful* call with nothing usable in it, and
    the caller refuses on that separately — the two are different situations and
    a person can act on only one of them.
    """
    agent = await _load_agent()
    program = agent.build_program()

    async def invoke() -> Any:
        with agent.usage_tracking():
            return await program.aforward(
                prompt_body=prompt_body,
                prompt_title=prompt_title,
                brief=brief,
                case_target=case_target,
            )

    try:
        prediction = await _breaker.call(invoke)
    except CircuitOpenError as error:
        drafter_total.labels(outcome="refused").inc()
        raise DrafterUnavailableError("the drafting agent is in a failing state") from error
    except Exception as error:
        drafter_total.labels(outcome="error").inc()
        raise DrafterUnavailableError(str(error)) from error

    usage = agent.usage_of(prediction)
    cost = agent.cost_usd(usage)
    drafter_cost_usd_total.inc(cost)

    drafts, dropped_cases, dropped_assertions = _drafts(
        getattr(prediction, "cases", None), modality
    )
    drafter_total.labels(outcome="ok" if drafts else "empty").inc()

    # No prompt body, no drafted case text, no assertion values. The counts and
    # the ids are the whole record, for A-046's reason.
    log.info(
        "evaluation.cases_drafted",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        model=APP_AGENT_MODEL,
        case_count=len(drafts),
        dropped_cases=dropped_cases,
        dropped_assertions=dropped_assertions,
        input_tokens=usage.get("input", 0),
        output_tokens=usage.get("output", 0),
    )

    return DraftOutcome(
        cases=tuple(drafts),
        model=APP_AGENT_MODEL,
        input_tokens=usage.get("input", 0),
        output_tokens=usage.get("output", 0),
        cost_usd=cost,
        dropped_cases=dropped_cases,
        dropped_assertions=dropped_assertions,
    )
