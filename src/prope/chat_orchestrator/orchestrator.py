"""The supervisor. One turn in, one answer out, with the path it took recorded.

Deck 3's supervisor-worker pattern (p17-19), implemented as an explicit function
rather than as a graph library, and the trade is stated rather than assumed:
LangGraph buys a visualisable graph and a checkpointed `interrupt()`, and costs a
dependency A-012's *debuggable by one person* clause has already rejected twice
over. What the deck actually asks for — nodes that are functions over a typed
state, routing that is code and not prose, a `trace` field that is appended and
never overwritten, and a human-in-the-loop point — is all present below, and
`route()` is thirty lines somebody can read in one sitting.

The shape of one turn:

    rails  ->  route  ->  execute plan  ->  respond  ->  rails  ->  directives

* **rails first, before a token is spent.** `guardrails.inspect_message` runs on
  the raw text and a refusal never reaches a model. Deck 5 p43: an output-rail-only
  design pays for every bad input twice.
* **route once.** The plan is fixed before any tool output exists, so nothing a
  retrieved prompt body says can add a step. Deck 5 p40, *Plan-Then-Execute*.
* **execute in order, and survive each step.** A failing worker returns
  `outcome="error"` and the turn continues with less evidence. Deck 3 p51:
  partial failure is summarised, never waited on.
* **respond from evidence only**, and say which leg was down when one was.
* **rails again**, then derive the UI directives *from what actually ran*.

**Nothing here writes.** The two write tools produce a `PendingAction`,
`run_turn` returns it, and `confirm_action` — a different request, carrying a
different person's explicit decision — is the only path to
`tools.CONFIRMED_EXECUTORS`.
"""

import asyncio
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any, Final
from urllib.parse import quote

import structlog
from langfuse import propagate_attributes
from sqlalchemy.ext.asyncio import AsyncSession

from prope.access_control.domain import VisibleFilter
from prope.app_agent.circuit import CircuitBreaker, CircuitOpenError
from prope.app_agent.client import APP_AGENT_MODEL
from prope.app_agent.telemetry import get_langfuse
from prope.chat_orchestrator import dspy_program, observability, tools
from prope.chat_orchestrator.domain import (
    MAX_TRACE_ENTRIES,
    TOOLS,
    Citation,
    Intent,
    PendingAction,
    ToolName,
    TraceEntry,
    TraceStatus,
    UiDirective,
)
from prope.chat_orchestrator.guardrails import (
    RateLimiter,
    RefusalReason,
    sanitise_directives,
    scrub_reply,
)
from prope.chat_orchestrator.prompting import load_responder_prompt, load_router_prompt

__all__ = [
    "TurnRequest",
    "TurnResult",
    "confirm_action",
    "rate_limiter",
    "run_turn",
    "warm_chat_agent",
]

logger = structlog.get_logger(__name__)


def _set_circuit_metric(is_open: bool) -> None:
    observability.agent_circuit_open.set(1 if is_open else 0)


#: This module's own breaker instance, not prompt-search's. Each feature owns one
#: (`app_agent.circuit`'s own docstring says so), because a chat outage and an
#: indexing outage are different failures with different blast radii — sharing
#: one would let a bad indexing hour silently stop the assistant answering
#: documentation questions that need no model at all.
_breaker = CircuitBreaker(on_state_change=_set_circuit_metric)

#: One shared limiter per process. See `guardrails.RateLimiter` for why in-memory
#: is correct here and where it stops being correct.
rate_limiter = RateLimiter()

#: Below this share of cited tags actually existing, the reply is treated as
#: ungrounded and gets a caveat rather than a clean bill of health.
_MIN_GROUNDING: Final = 0.5

#: What the client renders when an output rail replaced the whole reply.
_RAIL_REPLACEMENT_CODE: Final = "chat_reply_withheld"


@dataclass(slots=True)
class TurnRequest:
    """One turn's input. The shared state deck 3 (p22) asks for, at the boundary.

    **`open_db` is a factory, not a session, and the difference is a production
    property.** A turn makes two model calls, each of which can take seconds. A
    session held across them holds a pooled connection across them, and a handful
    of concurrent chats would then starve every other route in the process of
    connections while doing no database work at all. So the transaction is opened
    around the tool phase and closed before the responder call — which is also why
    the tool phase is one contiguous block rather than interleaved with the model.
    """

    open_db: Any
    workspace_id: str
    actor_id: str
    visible: VisibleFilter
    conversation_id: str
    message: str
    history: list[str] = field(default_factory=list)
    #: A whole prompt body the person supplied alongside the message.
    attachment: str | None = None
    attachment_format: str = "txt"


@dataclass(slots=True)
class TurnResult:
    """One turn's output, and everything the API layer needs to answer with.

    `reply` and `code` are alternatives, not a pair. A generated answer sets
    `reply`; a refusal sets `code` and leaves `reply` empty, because ADR-0053
    makes every non-generated display string a catalogue key the client
    translates. A refusal message written here in Vietnamese would be the one
    literal display string in the API.
    """

    intent: str
    reply: str = ""
    code: str | None = None
    trace: list[TraceEntry] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    directives: list[UiDirective] = field(default_factory=list)
    pending: PendingAction | None = None
    outcome: str = "answered"
    #: Named degradations the client may show: `retrieval_lexical_only`,
    #: `tool_failed`. Closed vocabulary; the client translates each.
    degraded: list[str] = field(default_factory=list)


class _Trace:
    """An append-only trace. Deck 3 p59: *append, never overwrite*."""

    def __init__(self) -> None:
        self._entries: list[TraceEntry] = []

    def add(
        self,
        *,
        agent: str,
        action: str,
        status: TraceStatus,
        started: float,
        detail: dict[str, Any] | None = None,
    ) -> None:
        if len(self._entries) >= MAX_TRACE_ENTRIES:
            return
        self._entries.append(
            TraceEntry(
                agent=agent,
                action=action,
                status=status,
                latency_ms=int((time.perf_counter() - started) * 1000),
                detail=observability.safe_detail(detail),
            )
        )

    @property
    def entries(self) -> list[TraceEntry]:
        return list(self._entries)


async def warm_chat_agent() -> None:
    """Resolve both managed instructions at process start.

    Same reason `warm_extraction_agent` exists: `get_prompt` is synchronous and
    may fetch, and paying that on the first person's first message makes the
    assistant look slow exactly once per deploy, to whoever happens to be first.
    Failures are swallowed — the fallbacks are compiled in.
    """
    try:
        router = await asyncio.to_thread(load_router_prompt)
        responder = await asyncio.to_thread(load_responder_prompt)
        dspy_program.build_router_program(router.text)
        dspy_program.build_reply_program(responder.text)
    except Exception:
        logger.info("chat_orchestrator.warm_failed")


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


async def _execute(
    context: tools.ToolContext,
    decision: dspy_program.RoutingDecision,
    trace: _Trace,
) -> list[tools.ToolResult]:
    """Run the plan in order. One worker at a time, and each one survivable.

    Sequential rather than concurrent, and deck 3 (p35) is the argument: async
    workers are the extension once sync is understood, and this plan is at most
    three steps of which two are genuinely ordered — a duplicate check on
    converted XML cannot start before the conversion finishes. Parallelism would
    buy latency on the one unordered case and cost a state-merge nobody needs.
    """
    results: list[tools.ToolResult] = []

    for name in decision.tools:
        spec = TOOLS[name]
        started = time.perf_counter()

        match name:
            case ToolName.SEARCH_PROMPTS:
                result = await tools.run_search_prompts(context, query=decision.query)
            case ToolName.FIND_DUPLICATES:
                result = await tools.run_find_duplicates(context)
            case ToolName.CONVERT_PROMPT:
                result = await tools.run_convert_prompt(context)
            case ToolName.ANSWER_FROM_DOCS:
                result = await tools.run_answer_from_docs(context, question=decision.query)
            case ToolName.CREATE_PROMPT:
                result = tools.propose_create_prompt(
                    context, title=decision.query or "Prompt đã nhập"
                )
            case ToolName.CREATE_REVISION:
                # The prompt id is not the router's to invent. Without a
                # duplicate hit to attach to, this degrades to an error the
                # supervisor reports rather than a write against a guessed row.
                target = next(
                    (
                        item.reference
                        for previous in results
                        for item in previous.evidence
                        if item.kind == "prompt"
                    ),
                    None,
                )
                result = (
                    tools.propose_create_revision(context, prompt_id=target)
                    if target
                    else tools.ToolResult(
                        tool=name, outcome="error", reason="chat_tool_no_target_prompt"
                    )
                )
            case _:  # pragma: no cover - `routing_of` filters to the catalogue
                continue

        results.append(result)

        observability.tool_total.labels(tool=name, outcome=result.outcome).inc()
        observability.tool_duration_seconds.labels(tool=name).observe(
            time.perf_counter() - started
        )
        if result.outcome == "ok" and name == ToolName.ANSWER_FROM_DOCS:
            if not result.payload.get("dense_ran"):
                observability.retrieval_dense_unavailable_total.inc()

        trace.add(
            agent=f"worker.{name}",
            action="execute",
            status=TraceStatus.OK if result.outcome == "ok" else TraceStatus.ERROR,
            started=started,
            detail={**result.detail, "outcome": result.outcome, "reason": result.reason or ""},
        )

        # A write proposal ends the plan: the confirmation card is the answer.
        if spec.writes and result.proposal is not None:
            break

    return results


def _evidence_block(results: list[tools.ToolResult]) -> tuple[str, dict[str, tools.Evidence], bool]:
    """Every result rendered for the responder, and whether it was truncated.

    Each item is delimited and tagged — spotlighting (deck 5, p38) at the payload
    level, on top of DSPy's own field markers. The responder's instruction says
    the block is untrusted data; this is what makes the boundary between one
    item and the next unambiguous, so a prompt body containing `[E2]` cannot
    forge a second citation.
    """
    lines: list[str] = []
    index: dict[str, tools.Evidence] = {}
    used = 0
    truncated = False

    for result in results:
        for item in result.evidence:
            rendered = f"[{item.tag}] ({item.kind}) {item.text}"
            if used + len(rendered) > dspy_program.EVIDENCE_CHARACTER_LIMIT:
                truncated = True
                break
            lines.append(rendered)
            index[item.tag] = item
            used += len(rendered)
        if truncated:
            break

    return "\n\n".join(lines), index, truncated


def _situation(
    results: list[tools.ToolResult], pending: tools.Proposal | None, degraded: list[str]
) -> str:
    """The trusted half of the responder's input: what ran and what did not.

    Written by Prope, never by a model, and kept to tokens rather than prose so
    that no part of it can be mistaken for content. This is what lets the
    responder honour "say which part of the answer is incomplete" — without it,
    a failed tool is indistinguishable from a tool that found nothing.
    """
    lines = [
        f"{result.tool}={result.outcome}"
        + (f"({result.reason})" if result.reason else "")
        + (f" evidence={len(result.evidence)}" if result.evidence else " evidence=0")
        for result in results
    ]
    if not lines:
        lines.append("no_tool_ran")
    if pending is not None:
        lines.append(f"awaiting_confirmation={pending.tool}")
    if degraded:
        lines.append("degraded=" + ",".join(degraded))
    return "\n".join(lines)


def _search_path(search: tools.ToolResult) -> str:
    """`/app/search` carrying the words that found these results, when it can.

    A navigation to a search screen with an empty box is a navigation that undoes
    the search. The query rides in the URL because that is the one piece of state
    the screen already knows how to restore — and it falls back to the bare path
    rather than emitting something the allow-list would drop, so a long query
    costs the person a re-type instead of the whole directive.
    """
    query = str(search.payload.get("query", "")).strip()
    if not query:
        return "/app/search"
    encoded = quote(query, safe="")
    return f"/app/search?q={encoded}" if len(encoded) <= 200 else "/app/search"


def _directives_for(
    intent: str, results: list[tools.ToolResult], pending: tools.Proposal | None
) -> list[dict[str, Any]]:
    """Derive the UI actions from what the plan actually did.

    **Derived, never generated.** A language model that could name a UI action is
    a model that can be talked into naming one by a prompt body it retrieved, and
    the whole point of the closed vocabulary is that the client executes what it
    is told. So the source is this function and the validator downstream is the
    second line rather than the first.

    Deliberately restrained. Deck 5's Trust UX pillars (p59) put *control* beside
    *transparency*: an assistant that reorganises somebody's screen on every turn
    has taken control rather than offered it. A documentation answer moves
    nothing, and a search moves the person only when they asked to go looking.
    """
    by_tool = {result.tool: result for result in results}
    directives: list[dict[str, Any]] = []

    if pending is not None:
        directives.append({"kind": "set_step", "step": "save"})
        directives.append({"kind": "highlight", "target": "import-summary"})
        return directives

    if intent == Intent.IMPORT_PROMPT:
        conversion = by_tool.get(ToolName.CONVERT_PROMPT)
        duplicates = by_tool.get(ToolName.FIND_DUPLICATES)

        if duplicates is not None and duplicates.evidence:
            directives.append({"kind": "set_step", "step": "duplicates"})
            directives.append({"kind": "highlight", "target": "duplicate-card"})
        elif conversion is not None and conversion.outcome == "ok":
            directives.append({"kind": "navigate", "to": "/app/prompts/new"})
            directives.append({"kind": "set_step", "step": "review"})
            fields = {"body": conversion.payload.get("xml_body", "")}
            directives.append({"kind": "prefill_form", "form": "import", "fields": fields})
        return directives

    if intent == Intent.SEARCH:
        search = by_tool.get(ToolName.SEARCH_PROMPTS)
        if search is None or not search.evidence:
            return directives
        # One clear winner opens it; several send the person to the result page.
        # The threshold is the ranker's own tier boundary rather than a number
        # invented here: a single result above it is what "found it" means.
        best = search.evidence[0]
        if len(search.evidence) == 1 and (best.score or 0.0) >= 0.55:
            directives.append({"kind": "navigate", "to": f"/app/prompts/{best.reference}"})
        else:
            directives.append({"kind": "navigate", "to": _search_path(search)})
            directives.append({"kind": "highlight", "target": "search-results"})
        return directives

    if intent == Intent.DUPLICATE_CHECK:
        duplicates = by_tool.get(ToolName.FIND_DUPLICATES)
        if duplicates is not None and duplicates.evidence:
            # Deliberately not `open_dialog: similar-prompts`. That dialog is fed
            # by the import flow's own match list, and the matches for *this*
            # question are the citations already sitting in the reply — opening a
            # dialog the module cannot fill would show an empty one. The highlight
            # points at the evidence where it actually is.
            directives.append({"kind": "highlight", "target": "duplicate-card"})
        return directives

    return directives


# ---------------------------------------------------------------------------
# The model calls
# ---------------------------------------------------------------------------


async def _call(program_call: Any, *, generation: Any, module: Any) -> Any:
    """One DSPy call behind the breaker, with usage accounted and no content sent."""

    async def invoke() -> Any:
        with module.usage_tracking():
            return await program_call()

    prediction = await _breaker.call(invoke)

    usage = module.usage_of(prediction)
    if usage:
        spend = module.cost_usd(usage)
        observability.tokens_total.labels(direction="input").inc(usage["input"])
        observability.tokens_total.labels(direction="output").inc(usage["output"])
        observability.cost_usd_total.inc(spend)
        if generation is not None:
            generation.update(usage_details=usage, cost_details={"total": spend})

    # Deliberately no `generation.update(input=..., output=...)` and deliberately
    # no OpenInference auto-instrumentation: both would ship the person's message
    # and every retrieved prompt title to the telemetry backend, which is exactly
    # what A-020 forbids and what the trace rules in `observability.py` exist to
    # keep out. Counts and costs go up; text does not.
    return prediction


def _generation(name: str, managed_prompt: Any) -> Any:
    langfuse = get_langfuse()
    if langfuse is None:
        return nullcontext(None)

    kwargs: dict[str, Any] = {"name": name, "as_type": "generation", "model": APP_AGENT_MODEL}
    if managed_prompt is not None:
        kwargs["prompt"] = managed_prompt
    return langfuse.start_as_current_observation(**kwargs)


# ---------------------------------------------------------------------------
# The turn
# ---------------------------------------------------------------------------


async def run_turn(request: TurnRequest) -> TurnResult:
    """One chat turn, start to finish. Never raises for an expected failure."""
    started = time.perf_counter()
    trace = _Trace()
    langfuse = get_langfuse()

    root = (
        langfuse.start_as_current_observation(name="chat.turn", as_type="span")
        if langfuse is not None
        else nullcontext(None)
    )

    with root as root_span:
        attributes: Any = nullcontext()
        if langfuse is not None:
            attributes = propagate_attributes(
                user_id=request.actor_id,
                trace_name="chat.turn",
                tags=["chat-orchestrator"],
                metadata={
                    "workspace_id": request.workspace_id,
                    "conversation_id": request.conversation_id,
                    # Metadata only. Never the message, never the attachment.
                    "message_characters": len(request.message),
                    "attachment_characters": len(request.attachment or ""),
                    "history_turns": len(request.history),
                },
            )

        with attributes:
            result = await _run_turn(request, trace, root_span)

    observability.turn_duration_seconds.observe(time.perf_counter() - started)
    observability.turn_total.labels(outcome=result.outcome).inc()
    return result


def _refusal(reason: str, trace: _Trace, started: float) -> TurnResult:
    observability.input_refused_total.labels(reason=reason).inc()
    trace.add(
        agent="guardrail.input",
        action="refuse",
        status=TraceStatus.WARN,
        started=started,
        detail={"reason": reason},
    )
    return TurnResult(
        intent=Intent.REFUSED,
        code=reason,
        trace=trace.entries,
        outcome="refused",
    )


async def _run_turn(request: TurnRequest, trace: _Trace, root_span: Any) -> TurnResult:
    rails_started = time.perf_counter()

    if not rate_limiter.admit(request.actor_id):
        return _refusal(RefusalReason.RATE_LIMITED, trace, rails_started)

    from prope.chat_orchestrator.guardrails import inspect_message

    verdict = inspect_message(request.message)
    if not verdict.admitted:
        logger.info(
            "chat_orchestrator.input_refused",
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
            reason=verdict.reason,
            rule=verdict.matched,
        )
        return _refusal(verdict.reason or RefusalReason.OFF_TOPIC, trace, rails_started)

    trace.add(
        agent="guardrail.input",
        action="admit",
        status=TraceStatus.OK,
        started=rails_started,
        detail={"outcome": "admitted"},
    )

    # --- route ------------------------------------------------------------
    route_started = time.perf_counter()
    router_prompt = await asyncio.to_thread(load_router_prompt)
    if router_prompt.is_fallback:
        observability.prompt_fallback_total.labels(program="router").inc()

    program = dspy_program.build_router_program(router_prompt.text)

    try:
        with _generation("chat.router", router_prompt.managed_prompt) as generation:
            prediction = await _call(
                lambda: program.acall(
                    catalogue=dspy_program.catalogue_text(),
                    history=dspy_program.truncate_history(request.history),
                    message=request.message,
                    has_attachment=bool(request.attachment),
                ),
                generation=generation,
                module=dspy_program,
            )
    except CircuitOpenError:
        return _unavailable(trace, route_started, reason="circuit_open")
    except Exception:
        logger.warning(
            "chat_orchestrator.router_failed",
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )
        return _unavailable(trace, route_started, reason="router_error")

    decision = dspy_program.routing_of(prediction)
    observability.router_total.labels(intent=decision.intent).inc()
    trace.add(
        agent="supervisor",
        action="route",
        status=TraceStatus.OK,
        started=route_started,
        detail={
            "intent": decision.intent,
            "steps": len(decision.tools),
            "prompt_version": router_prompt.version or 0,
            "fallback": router_prompt.is_fallback,
        },
    )
    if root_span is not None:
        _update(root_span, {"intent": decision.intent, "planned_steps": len(decision.tools)})

    # --- execute ----------------------------------------------------------
    #
    # One transaction, opened here and closed before the responder call. See
    # `TurnRequest.open_db`. When the plan is empty — small talk, a refusal — no
    # transaction is opened at all, which is the common case for the cheapest
    # turns and is worth not paying for.
    results: list[tools.ToolResult] = []
    if decision.tools:
        async with request.open_db() as db:
            context = tools.ToolContext(
                db=db,
                workspace_id=request.workspace_id,
                actor_id=request.actor_id,
                visible=request.visible,
                attachment=request.attachment,
                attachment_format=request.attachment_format,
            )
            results = await _execute(context, decision, trace)

    degraded: list[str] = []
    if any(result.outcome != "ok" for result in results):
        degraded.append("tool_failed")
    docs = next((r for r in results if r.tool == ToolName.ANSWER_FROM_DOCS), None)
    if docs is not None and not docs.payload.get("dense_ran"):
        degraded.append("retrieval_lexical_only")

    proposal = next((result.proposal for result in results if result.proposal), None)

    # --- respond ----------------------------------------------------------
    reply_started = time.perf_counter()
    evidence_text, evidence_index, truncated = _evidence_block(results)
    responder_prompt = await asyncio.to_thread(load_responder_prompt)
    if responder_prompt.is_fallback:
        observability.prompt_fallback_total.labels(program="responder").inc()

    responder = dspy_program.build_reply_program(responder_prompt.text)

    try:
        with _generation("chat.responder", responder_prompt.managed_prompt) as generation:
            prediction = await _call(
                lambda: responder.acall(
                    question=request.message,
                    evidence=evidence_text,
                    situation=_situation(results, proposal, degraded),
                ),
                generation=generation,
                module=dspy_program,
            )
    except CircuitOpenError:
        return _unavailable(trace, reply_started, reason="circuit_open")
    except Exception:
        logger.warning(
            "chat_orchestrator.responder_failed",
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )
        return _unavailable(trace, reply_started, reason="responder_error")

    reply, cited = dspy_program.reply_of(prediction)

    # --- output rails -----------------------------------------------------
    rail_started = time.perf_counter()
    reply, fired = scrub_reply(reply)
    for rail in fired:
        observability.output_rail_total.labels(rail=rail).inc()

    valid = tuple(tag for tag in cited if tag in evidence_index)
    grounding = _grounding(decision.intent, evidence_index, cited, valid)
    observability.grounding_score.observe(grounding)

    if evidence_index and grounding < _MIN_GROUNDING:
        observability.output_rail_total.labels(rail="ungrounded").inc()
        degraded.append("answer_ungrounded")

    trace.add(
        agent="guardrail.output",
        action="inspect",
        status=TraceStatus.WARN if fired or "answer_ungrounded" in degraded else TraceStatus.OK,
        started=rail_started,
        detail={
            "rail": fired[0] if fired else "",
            "score": round(grounding, 3),
            "citation_count": len(valid),
            "evidence_count": len(evidence_index),
            "truncated": truncated,
        },
    )

    if not reply and "instruction_leak" in fired:
        return TurnResult(
            intent=decision.intent,
            code=_RAIL_REPLACEMENT_CODE,
            trace=trace.entries,
            outcome="refused",
        )

    # --- directives -------------------------------------------------------
    proposed = _directives_for(decision.intent, results, proposal)
    directives = sanitise_directives(proposed)
    dropped = len(proposed) - len(directives)
    if dropped:
        # Nothing generated these, so a drop means this module and the validator
        # disagree — a bug in one of them, and a counter is how it surfaces.
        observability.directive_dropped_total.inc(dropped)
        logger.warning("chat_orchestrator.directive_dropped", dropped=dropped)

    citations = [
        Citation(
            kind=evidence_index[tag].kind,
            reference=evidence_index[tag].reference,
            label=evidence_index[tag].label,
            score=evidence_index[tag].score,
        )
        for tag in valid
    ]

    pending = None
    if proposal is not None:
        pending = PendingAction(
            id="",  # assigned by the API layer when the row is written
            tool=proposal.tool,
            summary=proposal.summary,
            preview=proposal.preview,
            arguments=proposal.arguments,
        )

    return TurnResult(
        intent=decision.intent,
        reply=reply,
        trace=trace.entries,
        citations=citations,
        directives=directives,
        pending=pending,
        outcome="degraded" if degraded else "answered",
        degraded=degraded,
    )


def _grounding(
    intent: str,
    evidence: dict[str, tools.Evidence],
    cited: tuple[str, ...],
    valid: tuple[str, ...],
) -> float:
    """How much of what the reply claimed to stand on actually exists.

    Deterministic, so it can run on every turn in production without a judge
    model — the same property that lets prompt-search score every extraction.
    Three cases, and the middle one is the interesting one:

    * no evidence was gathered — nothing to be grounded in, so 1.0. A greeting is
      not ungrounded.
    * evidence exists and the reply cited nothing — 0.0. This is the failure the
      metric is for: an answer written from the model's own memory of how some
      other prompt tool works, with the retrieved documentation sitting unused.
    * evidence exists and tags were cited — the share of them that resolve. A
      hallucinated `[E9]` drags the score down rather than being quietly ignored.
    """
    if not evidence:
        return 1.0
    if intent in {Intent.SMALLTALK, Intent.REFUSED}:
        return 1.0
    if not cited:
        return 0.0
    return len(valid) / len(cited)


def _unavailable(trace: _Trace, started: float, *, reason: str) -> TurnResult:
    trace.add(
        agent="supervisor",
        action="abort",
        status=TraceStatus.ERROR,
        started=started,
        detail={"reason": reason},
    )
    return TurnResult(
        intent=Intent.REFUSED,
        code="chat_agent_unavailable",
        trace=trace.entries,
        outcome="unavailable",
    )


def _update(span: Any, metadata: dict[str, Any]) -> None:
    try:
        span.update(metadata=metadata)
    except Exception:
        # Telemetry is fail-open at every site in this project.
        pass


# ---------------------------------------------------------------------------
# The human-in-the-loop half
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    """What a confirmed or rejected proposal produced."""

    status: str
    code: str | None = None
    prompt_id: str | None = None
    version_id: str | None = None
    directives: list[UiDirective] = field(default_factory=list)


async def confirm_action(
    *,
    db: AsyncSession,
    workspace_id: str,
    actor_id: str,
    visible: VisibleFilter,
    action: dict[str, Any],
    approve: bool,
) -> ConfirmationResult:
    """Run — or discard — a proposal a person has decided on.

    **This is the only path in the module that writes**, and it takes no model
    call at all: the arguments were fixed when the proposal was made, so what
    runs is byte-for-byte what the confirmation card showed. Deck 5 (p57) names
    the alternative as the rubber-stamp anti-pattern — a review whose subject can
    change between the showing and the doing.
    """
    if not approve:
        observability.pending_action_total.labels(decision="rejected").inc()
        return ConfirmationResult(status="rejected")

    executor = tools.CONFIRMED_EXECUTORS.get(action["tool"])
    if executor is None:  # pragma: no cover - the catalogue is closed
        return ConfirmationResult(status="failed", code="chat_tool_unknown")

    context = tools.ToolContext(
        db=db, workspace_id=workspace_id, actor_id=actor_id, visible=visible
    )

    try:
        written = await executor(context, action["arguments"])
    except tools.WriteRefused as refusal:
        observability.pending_action_total.labels(decision="rejected").inc()
        return ConfirmationResult(status="failed", code=refusal.code)

    observability.pending_action_total.labels(decision="confirmed").inc()
    logger.info(
        "chat_orchestrator.action_confirmed",
        actor_id=actor_id,
        workspace_id=workspace_id,
        tool=action["tool"],
        prompt_id=written["prompt_id"],
        version_id=written["version_id"],
    )

    return ConfirmationResult(
        status="confirmed",
        prompt_id=written["prompt_id"],
        version_id=written["version_id"],
        # Deliberately no `select_tab: versioning`: in this product the tabs are
        # routes, so the navigation above already lands there. A directive that
        # restates what the previous one did is one the client executes for
        # nothing, and it makes the vocabulary look busier than the flow is.
        directives=sanitise_directives(
            [
                {"kind": "navigate", "to": f"/app/prompts/{written['prompt_id']}"},
                {"kind": "highlight", "target": "version-rail"},
            ]
        ),
    )
