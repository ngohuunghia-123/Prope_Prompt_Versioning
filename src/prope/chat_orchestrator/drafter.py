"""The drafter: one stored prompt's body, rewritten per an instruction.

A revision request used to need a pasted source — `create_revision` staged
whatever `convert_prompt` had produced. That covers imports and nothing else,
which is why "make the 3d prompt resist prompt injection" had no path at all.
This module is that path: it reads the current revision, drafts the full revised
canonical XML from the person's instruction plus whatever technique notes the
plan's research legs gathered, validates the draft against the canonical
contract, and hands it to the same `create_revision` proposal every other body
change travels in. One HITL gate, unchanged.

**The model call lives behind its own breaker instance**, for the reason
`app_agent.circuit`'s docstring gives: a drafting outage is a different failure
from a routing outage with a different blast radius, and sharing a breaker would
let one silently stop the other.

**Every input is spotlighted untrusted data** (see `dspy_program.DraftRevision`)
because both of them are text written to instruct models. The output is trusted
only after `validate_canonical_xml` accepts it — a drafted body that smuggled a
DOCTYPE or an unknown block would be refused here rather than discovered by the
database after somebody approved it.

Failure has three named shapes, mirroring `run_convert_prompt`'s contract:
`DraftUnavailableError` (breaker open, provider down, instruction missing) and
`DraftInvalidError` (the model broke the canonical contract). Both become
`outcome="error"` tool results upstream; neither ends a turn.
"""

import asyncio
from contextlib import nullcontext
from typing import Any

import structlog

from prope.app_agent.circuit import CircuitBreaker, CircuitOpenError
from prope.app_agent.client import APP_AGENT_MODEL
from prope.app_agent.telemetry import get_langfuse
from prope.canonical_prompt import validate_canonical_xml
from prope.chat_orchestrator import dspy_program, observability
from prope.chat_orchestrator.prompting import load_drafter_prompt

__all__ = [
    "DraftInvalidError",
    "DraftUnavailableError",
    "DraftedRevision",
    "draft_revision",
]

logger = structlog.get_logger(__name__)

#: Research notes ride into the drafter's context. The evidence block the
#: responder sees is already bounded by `EVIDENCE_CHARACTER_LIMIT`; this bounds
#: the drafter's share separately so a fat notes field cannot crowd out a large
#: current body within the model's window.
MAX_RESEARCH_NOTES_CHARACTERS = 2_000

_breaker = CircuitBreaker(on_state_change=lambda _open: None)


class DraftUnavailableError(Exception):
    """The drafter could not run: breaker open, provider down, no instruction."""


class DraftInvalidError(Exception):
    """The drafter ran but its output is not a legal canonical body."""


class DraftedRevision:
    """A validated draft: the new body, why it changed, what it came from."""

    __slots__ = ("body", "change_summary", "based_on_version_id")

    def __init__(self, *, body: str, change_summary: str, based_on_version_id: str) -> None:
        self.body = body
        self.change_summary = change_summary
        self.based_on_version_id = based_on_version_id


def _set_circuit_metric(is_open: bool) -> None:
    if is_open:
        logger.warning("chat_orchestrator.drafter_circuit_open")


async def draft_revision(
    *,
    current_body: str,
    current_version_id: str,
    instruction: str,
    research_notes: str = "",
) -> DraftedRevision:
    """One drafting attempt. Never raises for an expected failure shape."""
    if not instruction.strip():
        raise DraftUnavailableError("no instruction")

    managed = await asyncio.to_thread(load_drafter_prompt)
    if managed.is_fallback:
        observability.prompt_fallback_total.labels(program="drafter").inc()

    program = dspy_program.build_draft_program(managed.text)
    langfuse = get_langfuse()

    def _generation() -> Any:
        if langfuse is None:
            return nullcontext(None)
        return langfuse.start_as_current_observation(
            name="chat.drafter",
            as_type="generation",
            model=APP_AGENT_MODEL,
            prompt=managed.managed_prompt,
        )

    try:

        async def invoke() -> Any:
            return await program.acall(
                current_body=current_body,
                instruction=instruction.strip()[:2_000],
                research_notes=research_notes.strip()[:MAX_RESEARCH_NOTES_CHARACTERS],
            )

        with _generation():
            prediction = await _breaker.call(invoke)
    except CircuitOpenError as exc:
        observability.drafter_total.labels(outcome="unavailable").inc()
        raise DraftUnavailableError("circuit open") from exc
    except Exception as exc:
        observability.drafter_total.labels(outcome="unavailable").inc()
        logger.warning(
            "chat_orchestrator.drafter_failed",
            exception=type(exc).__name__,
        )
        raise DraftUnavailableError("drafter error") from exc

    body, summary = dspy_program.draft_of(prediction)

    # The one gate between model output and a proposal somebody will be asked to
    # approve. A ValueError here is the contract working; wrap it so the caller
    # keeps two failure shapes instead of learning ours.
    try:
        validate_canonical_xml(body)
    except ValueError as exc:
        observability.drafter_total.labels(outcome="invalid").inc()
        raise DraftInvalidError("draft is not canonical") from exc

    observability.drafter_total.labels(outcome="drafted").inc()
    return DraftedRevision(
        body=body,
        change_summary=summary or "Cập nhật qua trợ lý",
        based_on_version_id=current_version_id,
    )
