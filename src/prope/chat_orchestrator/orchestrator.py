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
import json
import re
import time
from collections.abc import Callable
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
from prope.chat_orchestrator import (
    dspy_program,
    observability,
    tools,
    tools_access,
    tools_evaluation,
    tools_registry,
    tools_research,
)
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
from prope.chat_orchestrator.executors import CONFIRMED_EXECUTORS
from prope.chat_orchestrator.guardrails import (
    RateLimiter,
    RefusalReason,
    sanitise_directives,
    scrub_reply,
)
from prope.chat_orchestrator.prompting import (
    load_drafter_prompt,
    load_responder_prompt,
    load_router_prompt,
)

__all__ = [
    "TurnRequest",
    "TurnResult",
    "confirm_action",
    "decision_message",
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
_EVIDENCE_MARKER: Final = re.compile(r"\[(E\d+)\]")
_CITATION_EXCERPT_CHARACTERS: Final = 700


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
    #: This thread's decided proposals, oldest first. The supervisor reads them
    #  so a follow-up turn continues a task rather than repeating its first half,
    #  and any write that matches an already-confirmed action is dropped here —
    #  deterministically, not by trusting the model to behave.
    decided_actions: list[dict[str, Any]] = field(default_factory=list)
    #: The import source a confirmed proposal in this thread carried forward. A
    #  turn with no attachment of its own resumes from it instead of asking the
    #  person to paste what they already gave.
    carried_attachment: str | None = None
    carried_attachment_format: str = "txt"
    #: Optional, content-free progress sink used by the streaming route. It only
    #: receives catalogue codes and timings; never model or customer text.
    activity: Callable[[str, dict[str, Any]], None] | None = None
    #: `message` for a person's turn; `decision` for the automatic continuation
    #: a confirmed or rejected proposal runs. The trigger is what skips the
    #: input rails — a continuation carries no person's text to inspect — while
    #: routing, execution and the responder run exactly as for any other turn.
    trigger: str = "message"
    #: For `trigger="decision"`: what was settled (`tool`, `approve`, plus the
    #: executor's written ids). Trusted, Prope-written, and the source of both
    #: the router's marker text and the just-decided tool suppression below.
    decision: dict[str, Any] | None = None


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

    def __init__(self, activity: Callable[[str, dict[str, Any]], None] | None = None) -> None:
        self._entries: list[TraceEntry] = []
        self._activity = activity

    @staticmethod
    def _activity_shape(agent: str, action: str) -> tuple[str, str, str]:
        if agent == "guardrail.input":
            return "guardrail.input", "thought", "chat.activity.inspectRequest"
        if agent == "supervisor" and action == "route":
            return "supervisor.route", "thought", "chat.activity.route"
        if agent.startswith("worker."):
            tool = agent.removeprefix("worker.")
            return agent, "action", f"chat.activity.tool.{tool}"
        if agent == "supervisor" and action == "respond":
            return "supervisor.respond", "thought", "chat.activity.compose"
        return "guardrail.output", "thought", "chat.activity.verifySources"

    def begin(self, *, agent: str, action: str) -> None:
        if self._activity is None:
            return
        activity_id, kind, label_code = self._activity_shape(agent, action)
        self._activity(
            "activity.started",
            {
                "id": activity_id,
                "kind": kind,
                "label_code": label_code,
                "status": "running",
            },
        )

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
        entry = TraceEntry(
            agent=agent,
            action=action,
            status=status,
            latency_ms=int((time.perf_counter() - started) * 1000),
            detail=observability.safe_detail(detail),
        )
        self._entries.append(entry)
        if self._activity is not None:
            activity_id, kind, label_code = self._activity_shape(agent, action)
            event_name = "activity.completed" if status == TraceStatus.OK else "activity.warning"
            self._activity(
                event_name,
                {
                    "id": activity_id,
                    "kind": kind,
                    "label_code": label_code,
                    "status": str(status),
                    "latency_ms": entry.latency_ms,
                },
            )

    @property
    def entries(self) -> list[TraceEntry]:
        return list(self._entries)


async def warm_chat_agent() -> None:
    """Resolve all three managed instructions at process start.

    Same reason `warm_extraction_agent` exists: `get_prompt` is synchronous and
    may fetch, and paying that on the first person's first message makes the
    assistant look slow exactly once per deploy, to whoever happens to be first.
    Failures are swallowed — the fallbacks are compiled in.
    """
    try:
        router = await asyncio.to_thread(load_router_prompt)
        responder = await asyncio.to_thread(load_responder_prompt)
        drafter = await asyncio.to_thread(load_drafter_prompt)
        dspy_program.build_router_program(router.text)
        dspy_program.build_reply_program(responder.text)
        dspy_program.build_draft_program(drafter.text)
    except Exception:
        logger.info("chat_orchestrator.warm_failed")


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


def _target_from_evidence(results: list[tools.ToolResult], kinds: tuple[str, ...], reference: str) -> str:
    """The most recent evidence reference of one kind matching what was asked.

    "Revoke the staging key" names a key by its label, not its id — the label is
    all the person ever saw. Matching against the evidence this same turn already
    gathered keeps the target inside what the tools authorised and displayed,
    never a value the model invented. Empty query matches the newest item of the
    kind, which is the right reading of "revoke it".
    """
    wanted = (reference or "").strip().casefold()
    for result in reversed(results):
        for item in reversed(result.evidence):
            if item.kind not in kinds:
                continue
            if not wanted or wanted in item.label.casefold() or wanted in item.reference.casefold():
                return item.reference
    return ""


def _csv(raw: Any) -> list[str] | None:
    """A comma-separated `changes` value as a list, for scope fields."""
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()] or None
    if isinstance(raw, str) and raw.strip():
        return [part.strip() for part in raw.split(",") if part.strip()]
    return None


def _no_target(tool: ToolName) -> tools.ToolResult:
    return tools.ToolResult(tool=tool, outcome="error", reason="chat_tool_no_target_prompt")


async def _step_create_revision(
    context: tools.ToolContext, decision: Any, results: list[tools.ToolResult]
) -> tools.ToolResult:
    """Two bodies, one proposal tool.

    A converted import body stages exactly what was pasted, as always. Without
    one, an instruction-shaped request ("make the 3d prompt resist injection")
    drafts the next revision from the current one — same tool, same HITL card,
    same executor; only where the body came from differs.
    """
    if context.converted_xml:
        # The prompt id is not the router's to invent. Without an earlier hit to
        # attach to, this degrades to an error the supervisor reports rather
        # than a write against a guessed row.
        target = _target_from_evidence(results, ("prompt",), decision.arguments.get("prompt_id", ""))
        if target:
            return tools.propose_create_revision(context, prompt_id=target)
        return _no_target(ToolName.CREATE_REVISION)
    return await tools_registry.propose_drafted_revision(
        context,
        reference=decision.arguments.get("prompt_id") or decision.query,
        instruction=str(decision.arguments.get("instruction") or ""),
        results=results,
    )


async def _step_update_prompt(
    context: tools.ToolContext, decision: Any, results: list[tools.ToolResult]
) -> tools.ToolResult:
    row = await tools_registry.resolve_prompt(context, decision.arguments.get("prompt_id") or decision.query)
    if row is None:
        return _no_target(ToolName.UPDATE_PROMPT)
    tags = _csv(decision.arguments.get("tags"))
    return tools_registry.propose_update_prompt(
        context,
        prompt_id=row.id,
        title=decision.arguments.get("title"),
        purpose=decision.arguments.get("purpose"),
        tags=tags,
    )


async def _step_retire_prompt(
    context: tools.ToolContext, decision: Any, results: list[tools.ToolResult]
) -> tools.ToolResult:
    row = await tools_registry.resolve_prompt(context, decision.arguments.get("prompt_id") or decision.query)
    if row is None:
        return _no_target(ToolName.RETIRE_PROMPT)
    return tools_registry.propose_retire_prompt(context, prompt_id=row.id)


async def _step_start_eval_run(
    context: tools.ToolContext, decision: Any, results: list[tools.ToolResult]
) -> tools.ToolResult:
    row = await tools_registry.resolve_prompt(context, decision.arguments.get("prompt_id") or decision.query)
    if row is None:
        return _no_target(ToolName.START_EVAL_RUN)
    version_id = decision.arguments.get("version_id")
    if not version_id:
        from prope.prompt_registry import repository as registry_repository

        latest = await registry_repository.load_latest_revision(context.db, row.id)
        version_id = latest.version_id if latest else ""
    suite_names = _csv(decision.arguments.get("suite_names"))
    if suite_names is None:
        suite_names = next(
            (
                result.payload.get("suite_names")
                for result in reversed(results)
                if result.tool == ToolName.LIST_SUITES and result.outcome == "ok"
            ),
            None,
        )
    return tools_evaluation.propose_start_eval_run(
        context,
        prompt_id=row.id,
        version_id=str(version_id) if version_id else None,
        suite_names=suite_names,
    )


def _key_step(tool: ToolName, propose: Any) -> Any:
    async def step(context: tools.ToolContext, decision: Any, results: list[tools.ToolResult]) -> tools.ToolResult:
        key_id = _target_from_evidence(results, ("api_key",), decision.arguments.get("key_id", "") or decision.query)
        if not key_id:
            return tools.ToolResult(tool=tool, outcome="error", reason="chat_tool_no_target_key")
        return propose(context, key_id=key_id)

    return step


async def _step_set_api_key_scope(
    context: tools.ToolContext, decision: Any, results: list[tools.ToolResult]
) -> tools.ToolResult:
    key_id = _target_from_evidence(results, ("api_key",), decision.arguments.get("key_id", "") or decision.query)
    if not key_id:
        return tools.ToolResult(tool=ToolName.SET_API_KEY_SCOPE, outcome="error", reason="chat_tool_no_target_key")
    return tools_access.propose_set_api_key_scope(
        context,
        key_id=key_id,
        scope_model_names=_csv(decision.arguments.get("scope_model_names")),
        scope_namespaces=_csv(decision.arguments.get("scope_namespaces")),
    )


async def _step_create_api_key(
    context: tools.ToolContext, decision: Any, results: list[tools.ToolResult]
) -> tools.ToolResult:
    name = decision.arguments.get("name") or decision.query
    return tools_access.propose_create_api_key(
        context,
        name=name,
        scope_model_names=_csv(decision.arguments.get("scope_model_names")),
        scope_namespaces=_csv(decision.arguments.get("scope_namespaces")),
    )


async def _step_update_provider(
    context: tools.ToolContext, decision: Any, results: list[tools.ToolResult]
) -> tools.ToolResult:
    provider_config_id = _target_from_evidence(
        results,
        ("provider",),
        decision.arguments.get("provider_config_id", "") or decision.query,
    )
    if not provider_config_id:
        return tools.ToolResult(tool=ToolName.UPDATE_PROVIDER, outcome="error", reason="chat_tool_no_target_provider")
    return tools_access.propose_update_provider(
        context,
        provider_config_id=provider_config_id,
        display_name=decision.arguments.get("display_name") or decision.arguments.get("name"),
        status=decision.arguments.get("status"),
    )


def _provider_delete_step() -> Any:
    async def step(context: tools.ToolContext, decision: Any, results: list[tools.ToolResult]) -> tools.ToolResult:
        provider_config_id = _target_from_evidence(
            results,
            ("provider",),
            decision.arguments.get("provider_config_id", "") or decision.query,
        )
        if not provider_config_id:
            return tools.ToolResult(
                tool=ToolName.DELETE_PROVIDER, outcome="error", reason="chat_tool_no_target_provider"
            )
        return tools_access.propose_delete_provider(context, provider_config_id=provider_config_id)

    return step


#: One step function per catalogue entry. The table replaces what used to be a
#: twenty-line `match`: adding a tool means adding a `TOOL_STEPS` entry, and the
#: completeness assert below fails at import when the two drift.
_TOOL_STEPS: Final = {
    ToolName.SEARCH_PROMPTS: lambda c, d, r: tools.run_search_prompts(c, query=d.query),
    ToolName.FIND_DUPLICATES: lambda c, d, r: tools.run_find_duplicates(c),
    ToolName.CONVERT_PROMPT: lambda c, d, r: tools.run_convert_prompt(c),
    ToolName.ANSWER_FROM_DOCS: lambda c, d, r: tools.run_answer_from_docs(c, question=d.query),
    ToolName.RESEARCH_TOPIC: lambda c, d, r: tools_research.run_research_topic(c, query=d.query),
    ToolName.CREATE_PROMPT: lambda c, d, r: tools.propose_create_prompt(c, title=d.query or "Prompt đã nhập"),
    ToolName.CREATE_REVISION: _step_create_revision,
    ToolName.GET_PROMPT: lambda c, d, r: tools_registry.run_get_prompt(c, prompt_id=d.query),
    ToolName.LIST_VERSIONS: lambda c, d, r: tools_registry.run_list_versions(c, prompt_id=d.query),
    ToolName.GET_RELEASE_STATUS: lambda c, d, r: tools_registry.run_get_release_status(c, prompt_id=d.query),
    ToolName.LIST_FOLDERS: lambda c, d, r: tools_registry.run_list_folders(c),
    ToolName.UPDATE_PROMPT: _step_update_prompt,
    ToolName.RETIRE_PROMPT: _step_retire_prompt,
    ToolName.CREATE_FOLDER: lambda c, d, r: tools_registry.propose_create_folder(
        c,
        name=d.arguments.get("name") or d.query,
        description=d.arguments.get("description", ""),
    ),
    ToolName.RENAME_FOLDER: lambda c, d, r: tools_registry.propose_rename_folder(
        c,
        slug=d.arguments.get("slug") or d.query,
        name=d.arguments.get("name"),
        description=d.arguments.get("description"),
    ),
    ToolName.DELETE_FOLDER: lambda c, d, r: tools_registry.propose_delete_folder(
        c, slug=d.arguments.get("slug") or d.query
    ),
    ToolName.LIST_API_KEYS: lambda c, d, r: tools_access.run_list_api_keys(c),
    ToolName.CREATE_API_KEY: _step_create_api_key,
    ToolName.REVOKE_API_KEY: _key_step(ToolName.REVOKE_API_KEY, tools_access.propose_revoke_api_key),
    ToolName.SET_API_KEY_SCOPE: _step_set_api_key_scope,
    ToolName.LIST_PROVIDERS: lambda c, d, r: tools_access.run_list_providers(c),
    ToolName.UPDATE_PROVIDER: _step_update_provider,
    ToolName.DELETE_PROVIDER: _provider_delete_step(),
    ToolName.LIST_SUITES: lambda c, d, r: tools_evaluation.run_list_suites(c, prompt_id=d.query),
    ToolName.START_EVAL_RUN: _step_start_eval_run,
    ToolName.GET_EVAL_RESULTS: lambda c, d, r: tools_evaluation.run_get_eval_results(c, prompt_id=d.query),
}

assert set(_TOOL_STEPS) == set(TOOLS), "every catalogue tool needs a plan step"


#: The argument that makes one proposal the same proposal as another. A repeat
#: of "create folder 3D" carries the same name even when the model phrases the
#: rest differently; tools without an entry here compare on their whole payload.
_IDENTITY_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    ToolName.CREATE_FOLDER.value: ("name",),
    ToolName.RENAME_FOLDER.value: ("slug", "name"),
    ToolName.DELETE_FOLDER.value: ("slug",),
    ToolName.CREATE_API_KEY.value: ("name",),
    ToolName.REVOKE_API_KEY.value: ("key_id",),
    ToolName.SET_API_KEY_SCOPE.value: ("key_id",),
    ToolName.UPDATE_PROVIDER.value: ("provider_config_id",),
    ToolName.DELETE_PROVIDER.value: ("provider_config_id",),
}


def _write_signature(tool: str, arguments: dict[str, Any]) -> tuple[Any, ...]:
    """What makes this write this write — or `()` when it cannot be compared."""
    fields = _IDENTITY_FIELDS.get(tool)
    if fields is not None:
        values = tuple(str(arguments.get(name, "")).strip().casefold() for name in fields)
        if all(values):
            return (tool, *values)
        return ()
    return (tool, json.dumps(arguments, sort_keys=True)) if arguments else ()


def _identity_candidates(decision: dspy_program.RoutingDecision, field: str) -> set[str]:
    """Where the person's value can appear at route time.

    The proposal builders fill arguments late — `create_folder` reads its name
    from `changes` *or* falls back to `query` — so a repeat matches on either.
    """
    candidates = {str(decision.arguments.get(field, "")).strip().casefold()}
    query = str(decision.query or "").strip().casefold()
    if query:
        candidates.add(query)
    return candidates


def _drop_confirmed_duplicates(
    decision: dspy_program.RoutingDecision,
    decided_actions: list[dict[str, Any]],
    suppressed_tools: frozenset[str] = frozenset(),
) -> tuple[dspy_program.RoutingDecision, list[str]]:
    """Remove plan steps that repeat a write this thread already decided.

    The router is told what was decided, but a model that repeats itself anyway
    is exactly how "continue" became "create the folder again". This is the
    deterministic backstop: same tool, same identity, already confirmed — gone,
    with the names logged for the trace rather than silently swallowed.

    `suppressed_tools` is the continuation half. A decision continuation runs
    seconds after the person settled one write; a router that answers by
    re-proposing that same tool — confirmed or rejected, and regardless of
    payload, because a drafted body never matches twice — would turn every
    rejection into an argument. Only a fresh user message can re-open the tool.
    """
    suppressed_repeats: list[str] = []
    confirmed: dict[str, list[tuple[str, ...]]] = {}
    for action in decided_actions:
        if action.get("status") != "confirmed":
            continue
        tool = str(action.get("tool", ""))
        signature = _write_signature(tool, dict(action.get("arguments") or {}))
        if len(signature) > 1:
            confirmed.setdefault(tool, []).append(signature)

    kept: list[str] = []
    dropped: list[str] = []
    for name in decision.tools:
        if not TOOLS[name].writes:
            kept.append(name)
            continue
        if name in suppressed_tools:
            suppressed_repeats.append(name)
            continue
        fields = _IDENTITY_FIELDS.get(name)
        if fields is None:
            repeated = bool(decision.arguments) and _write_signature(name, decision.arguments) in {
                s for sigs in confirmed.values() for s in sigs
            }
            if repeated:
                dropped.append(name)
                continue
            kept.append(name)
            continue
        known = confirmed.get(name, [])
        candidates = [_identity_candidates(decision, field) for field in fields]
        repeated = any(
            len(signature) == 1 + len(fields)
            and all(value in candidates[index] for index, value in enumerate(signature[1:]))
            for signature in known
        )
        if repeated:
            dropped.append(name)
        else:
            kept.append(name)
    if not dropped and not suppressed_repeats:
        return decision, []
    logger.info(
        "chat_orchestrator.step_already_done",
        dropped=dropped,
        suppressed=suppressed_repeats,
    )
    return (
        dspy_program.RoutingDecision(
            intent=decision.intent,
            tools=tuple(kept),
            query=decision.query,
            rationale=decision.rationale,
            arguments=decision.arguments,
        ),
        [*dropped, *suppressed_repeats],
    )


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

    **"Survivable" is the `try` below, and it used to be a claim rather than a
    mechanism.** Every executor in `tools` catches its own expected failures and
    returns `outcome="error"`, so the sentence was true for everything anybody
    had thought of. An *unexpected* raise — a driver error, a bad row, an
    `AttributeError` in a branch nobody reached — had no handler between here and
    the route, so it ended the whole turn with a 500 and the person lost the
    answer the other two steps had already earned. It also left no trace entry,
    which made a crashed worker indistinguishable from one the router chose not
    to run: the same absence, two opposite meanings. Both are fixed here, and the
    second is why the trace graph can label a missing node honestly.
    """
    results: list[tools.ToolResult] = []

    for name in decision.tools:
        spec = TOOLS[name]
        started = time.perf_counter()
        trace.begin(agent=f"worker.{name}", action="execute")

        try:
            # Read steps are coroutines; the pure proposal builders are not.
            # `iscoroutine` rather than forcing every entry to be async keeps
            # the table one line per tool.
            outcome = _TOOL_STEPS[name](context, decision, results)
            if asyncio.iscoroutine(outcome):
                outcome = await outcome
            result = outcome
        except CircuitOpenError:
            # Its own code rather than folding into the crash below, because this
            # one is the system working: the breaker opened, the worker never ran,
            # and the right reading is *try again shortly* rather than *this is
            # broken*. `_call` raises it for the model-backed workers.
            logger.warning(
                "chat_orchestrator.worker_circuit_open",
                tool=name,
                actor_id=context.actor_id,
                workspace_id=context.workspace_id,
            )
            result = tools.ToolResult(tool=name, outcome="error", reason="chat_tool_unavailable")
        except Exception as exc:  # noqa: BLE001 - this is the survivability, see the docstring
            # The exception TYPE, never its message. An asyncpg or httpx error
            # routinely quotes the value that broke it, and in this product that
            # value is frequently a prompt body — so `str(exc)` is a payload leak
            # wearing a stack trace. A-020 does not stop at the trace, and a class
            # name is a closed enough vocabulary to log.
            logger.warning(
                "chat_orchestrator.worker_failed",
                tool=name,
                exception=type(exc).__name__,
                actor_id=context.actor_id,
                workspace_id=context.workspace_id,
            )
            result = tools.ToolResult(tool=name, outcome="error", reason="chat_tool_crashed")

        results.append(result)

        observability.tool_total.labels(tool=name, outcome=result.outcome).inc()
        observability.tool_duration_seconds.labels(tool=name).observe(time.perf_counter() - started)
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


def _render_citations(
    reply: str,
    evidence: dict[str, tools.Evidence],
    cited: tuple[str, ...],
) -> tuple[str, tuple[str, ...], tuple[str, ...], list[Citation]]:
    """Validate evidence markers and turn them into safe Markdown source links.

    The model may place ``[E2]`` beside a claim, but it never gets to decide what
    that marker opens. Unknown tags disappear, valid tags map to evidence already
    authorised for this turn, and the citation JSON carries the same mapping for
    history. Tags declared in the structured ``cited`` field but not placed
    inline remain available in the source list without inventing a location.
    """
    inline_tags = tuple(match.group(1) for match in _EVIDENCE_MARKER.finditer(reply))
    declared = tuple(dict.fromkeys((*inline_tags, *cited)))
    valid = tuple(tag for tag in declared if tag in evidence)

    ordered = list(dict.fromkeys(tag for tag in inline_tags if tag in evidence))
    ordered.extend(tag for tag in valid if tag not in ordered)
    indexes = {tag: index for index, tag in enumerate(ordered, start=1)}
    mentions: dict[str, list[int]] = {tag: [] for tag in ordered}

    parts: list[str] = []
    cursor = 0
    rendered_characters = 0
    for match in _EVIDENCE_MARKER.finditer(reply):
        prefix = reply[cursor : match.start()]
        parts.append(prefix)
        rendered_characters += len(prefix)
        tag = match.group(1)
        if tag in indexes:
            marker = f" [{indexes[tag]}](#citation-{indexes[tag]})"
            mentions[tag].append(rendered_characters)
            parts.append(marker)
            rendered_characters += len(marker)
        cursor = match.end()
    parts.append(reply[cursor:])

    citations = []
    for tag in ordered:
        item = evidence[tag]
        excerpt = " ".join(item.text.split())[:_CITATION_EXCERPT_CHARACTERS]
        citations.append(
            Citation(
                kind=item.kind,
                reference=item.reference,
                label=item.label,
                score=item.score,
                index=indexes[tag],
                mentions=tuple(mentions[tag]),
                excerpt=excerpt,
                document=item.document,
                href=f"/app/prompts/{item.reference}" if item.kind == "prompt" else None,
            )
        )

    return "".join(parts), declared, valid, citations


def _situation(
    results: list[tools.ToolResult],
    pending: tools.Proposal | None,
    degraded: list[str],
    decided_actions: list[dict[str, Any]] | None = None,
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
    for action in decided_actions:
        if action.get("status") == "confirmed":
            lines.append(f"already_confirmed={action.get('tool', '?')}")
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


def _first_reference(results: list[tools.ToolResult], kinds: tuple[str, ...]) -> str:
    """The newest evidence reference of one of `kinds`, or ""."""
    for result in reversed(results):
        for item in reversed(result.evidence):
            if item.kind in kinds:
                return item.reference
    return ""


#: `PendingAction.tool -> where the person reviews that act manually`. This is
#: the auto-navigation half of the confirmation card: approving or reading about
#: a key happens on the keys screen, a folder on the registry grid, an eval run
#: on the run page. One entry per write tool, checked against the catalogue by
#: the test that owns `_directives_for`.
_PENDING_NAVIGATION: Final[dict[str, str]] = {
    ToolName.CREATE_PROMPT: "/app/prompts",
    ToolName.UPDATE_PROMPT: "/app/prompts",
    ToolName.RETIRE_PROMPT: "/app/prompts",
    ToolName.CREATE_FOLDER: "/app/prompts",
    ToolName.RENAME_FOLDER: "/app/prompts",
    ToolName.DELETE_FOLDER: "/app/prompts",
    ToolName.CREATE_API_KEY: "/app/settings/keys",
    ToolName.REVOKE_API_KEY: "/app/settings/keys",
    ToolName.SET_API_KEY_SCOPE: "/app/settings/keys",
    ToolName.UPDATE_PROVIDER: "/app/settings/providers",
    ToolName.DELETE_PROVIDER: "/app/settings/providers",
}


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
    nothing; every navigation below lands on the screen where the same action can
    be triggered manually, so the chat is a shortcut to a page the person could
    have driven themselves — never a place the product does not otherwise go.
    """
    by_tool = {result.tool: result for result in results}
    directives: list[dict[str, Any]] = []

    if pending is not None:
        # The confirmation card is the answer. It renders wherever the person
        # already is EXCEPT when the act belongs to another screen entirely —
        # minting a key while chatting about prompts would otherwise show a card
        # about a page nobody has open.
        target = _PENDING_NAVIGATION.get(pending.tool)
        if pending.tool == ToolName.START_EVAL_RUN:
            eval_prompt_id = str(pending.arguments.get("prompt_id") or "")
            if eval_prompt_id:
                directives.append({"kind": "navigate", "to": f"/app/prompts/{eval_prompt_id}/evaluation/run"})
                directives.append({"kind": "highlight", "target": "eval-runs"})
            return directives
        if target is not None and target != "/app/prompts":
            directives.append({"kind": "navigate", "to": target})
            return directives
        if pending.tool in {ToolName.CREATE_PROMPT, ToolName.CREATE_REVISION}:
            directives.append({"kind": "set_step", "step": "save"})
            directives.append({"kind": "highlight", "target": "import-summary"})
        elif target == "/app/prompts":
            prompt_id = _first_reference(results, ("prompt",))
            if prompt_id:
                directives.append({"kind": "navigate", "to": f"/app/prompts/{prompt_id}"})
            else:
                directives.append({"kind": "navigate", "to": "/app/prompts"})
                directives.append({"kind": "highlight", "target": "prompt-table"})
        return directives

    if intent == Intent.IMPORT_PROMPT:
        conversion = by_tool.get(ToolName.CONVERT_PROMPT)
        duplicates = by_tool.get(ToolName.FIND_DUPLICATES)

        if duplicates is not None and duplicates.evidence:
            directives.append({"kind": "set_step", "step": "duplicates"})
            directives.append({"kind": "highlight", "target": "duplicate-card"})
        elif conversion is not None and conversion.outcome == "ok":
            directives.append({"kind": "navigate", "to": "/app/imports/new"})
            directives.append({"kind": "set_step", "step": "review"})
            fields = {"body": conversion.payload.get("xml_body", "")}
            directives.append({"kind": "prefill_form", "form": "import", "fields": fields})
        elif conversion is not None:
            # Binary, archive, spreadsheet, and multi-file imports belong in
            # the durable batch surface rather than a lossy chat attachment.
            directives.append({"kind": "navigate", "to": "/app/imports/new"})
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

    if intent == Intent.MANAGE_PROMPT:
        prompt_id = _first_reference(results, ("prompt",))
        versions = by_tool.get(ToolName.LIST_VERSIONS)
        if versions is not None and versions.outcome == "ok":
            prompt_id = str(versions.payload.get("prompt_id") or prompt_id)
        if prompt_id:
            directives.append({"kind": "navigate", "to": f"/app/prompts/{prompt_id}"})
        return directives

    if intent == Intent.MANAGE_FOLDER:
        folders = by_tool.get(ToolName.LIST_FOLDERS)
        slug = ""
        if folders is not None and folders.evidence:
            slug = _first_reference(results, ("folder",))
        if slug:
            directives.append({"kind": "navigate", "to": f"/app/prompts/folder/{slug}"})
        else:
            directives.append({"kind": "navigate", "to": "/app/prompts"})
            directives.append({"kind": "highlight", "target": "prompt-table"})
        return directives

    if intent == Intent.MANAGE_KEYS:
        directives.append({"kind": "navigate", "to": "/app/settings/keys"})
        directives.append({"kind": "highlight", "target": "keys-list"})
        return directives

    if intent == Intent.MANAGE_PROVIDERS:
        provider_id = _first_reference(results, ("provider",))
        directives.append({"kind": "navigate", "to": "/app/settings/providers"})
        if provider_id:
            directives.append({"kind": "highlight", "target": "providers-list"})
        return directives

    if intent in {Intent.RUN_EVALUATION, Intent.CHECK_STATUS}:
        prompt_id = _first_reference(results, ("prompt",))
        runs = by_tool.get(ToolName.GET_EVAL_RESULTS)
        if runs is not None and runs.outcome == "ok":
            prompt_id = str(runs.payload.get("prompt_id") or prompt_id)
        if prompt_id:
            directives.append({"kind": "navigate", "to": f"/app/prompts/{prompt_id}"})
            directives.append({"kind": "select_tab", "tab": "evaluation"})
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
    trace = _Trace(request.activity)
    trace.begin(agent="guardrail.input", action="inspect")
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

    if request.trigger == "decision":
        # A continuation carries no person's text: its message is the trusted
        # HUMAN_DECISION marker the API layer wrote after settling a proposal.
        # There is nothing for an input rail to inspect, and running one would
        # invite pattern-matching on our own vocabulary. Everything downstream —
        # routing, tools, output rails, grounding — is identical to any turn.
        trace.add(
            agent="guardrail.input",
            action="admit",
            status=TraceStatus.OK,
            started=rails_started,
            detail={"outcome": "decision_continuation"},
        )
    else:
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
    trace.begin(agent="supervisor", action="route")
    router_prompt = await asyncio.to_thread(load_router_prompt)
    if router_prompt.is_fallback:
        observability.prompt_fallback_total.labels(program="router").inc()

    program = dspy_program.build_router_program(router_prompt.text)

    # A turn resumes from what the thread already carries when it brings no
    # body of its own: "continue" after a confirmed folder creation still has
    # the prompt to convert, and the person should not paste it twice.
    attachment = request.attachment or request.carried_attachment
    attachment_format = request.attachment_format if request.attachment else request.carried_attachment_format

    try:
        with _generation("chat.router", router_prompt.managed_prompt) as generation:
            prediction = await _call(
                lambda: program.acall(
                    catalogue=dspy_program.catalogue_text(),
                    history=dspy_program.truncate_history(request.history),
                    message=request.message,
                    has_attachment=bool(attachment),
                    recent_actions=dspy_program.render_decided_actions(request.decided_actions),
                ),
                generation=generation,
                module=dspy_program,
            )
    except CircuitOpenError:
        return _unavailable(trace, route_started, stage="route", reason="circuit_open")
    except Exception:
        logger.warning(
            "chat_orchestrator.router_failed",
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )
        return _unavailable(trace, route_started, stage="route", reason="router_error")

    decision = dspy_program.routing_of(prediction)
    # On a continuation, the write the person *just* decided is suppressed
    # outright — a router that answers an approval by re-proposing the same
    # tool (or a rejection by arguing with it) gets an empty plan instead.
    just_decided = str((request.decision or {}).get("tool", ""))
    suppressed = frozenset({just_decided}) if just_decided else frozenset()
    decision, already_done = _drop_confirmed_duplicates(decision, request.decided_actions, suppressed_tools=suppressed)
    if already_done:
        trace.add(
            agent="supervisor",
            action="deduplicate",
            status=TraceStatus.OK,
            started=route_started,
            detail={"dropped": len(already_done), "reason": "already_decided"},
        )
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
                attachment=attachment,
                attachment_format=attachment_format,
                message_text=request.message,
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
    trace.begin(agent="supervisor", action="respond")
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
                    situation=_situation(results, proposal, degraded, request.decided_actions),
                ),
                generation=generation,
                module=dspy_program,
            )
    except CircuitOpenError:
        return _unavailable(trace, reply_started, stage="respond", reason="circuit_open")
    except Exception:
        logger.warning(
            "chat_orchestrator.responder_failed",
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )
        return _unavailable(trace, reply_started, stage="respond", reason="responder_error")

    reply, cited = dspy_program.reply_of(prediction)

    # The most expensive step in the turn, and until the trace graph went looking
    # for it, the only one that recorded nothing. Two model calls happen here and
    # the trace showed one, so a turn that spent six seconds composing an answer
    # was indistinguishable from one that spent six seconds routing. Counts only,
    # as everywhere else: how many evidence items it was given and how many tags
    # it cited, never the question and never the reply.
    trace.add(
        agent="supervisor",
        action="respond",
        status=TraceStatus.OK,
        started=reply_started,
        detail={
            "intent": decision.intent,
            "evidence_count": len(evidence_index),
            "citation_count": len(cited),
            "prompt_version": responder_prompt.version or 0,
            "fallback": responder_prompt.is_fallback,
        },
    )

    # --- output rails -----------------------------------------------------
    rail_started = time.perf_counter()
    trace.begin(agent="guardrail.output", action="inspect")
    reply, fired = scrub_reply(reply)
    for rail in fired:
        observability.output_rail_total.labels(rail=rail).inc()

    reply, declared, valid, citations = _render_citations(reply, evidence_index, cited)
    grounding = _grounding(decision.intent, evidence_index, declared, valid)
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

    pending = None
    if proposal is not None:
        pending = PendingAction(
            id="",  # assigned by the API layer when the row is written
            tool=proposal.tool,
            summary=proposal.summary,
            preview=proposal.preview,
            arguments=proposal.arguments,
            # Only a body the person supplied *this* turn rides forward. A
            # carried-over one already lives on the row that confirmed first.
            resume_attachment=request.attachment,
            resume_attachment_format=request.attachment_format if request.attachment else None,
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


def _unavailable(trace: _Trace, started: float, *, stage: str, reason: str) -> TurnResult:
    """The supervisor gave up. `stage` says at which of its two turns at bat.

    **`stage` replaced a literal `action="abort"`, and the old value was a real
    hole rather than a cosmetic one.** Both call sites wrote the same entry, so a
    router that never chose a plan and a responder that never wrote an answer
    produced byte-identical traces — two failures with different causes, different
    blast radii and different fixes, wearing one face. `reason` distinguished them
    in principle (`router_error` vs `responder_error`) and not in practice, because
    the circuit-open path writes the same `reason` from both.

    Naming the stage also makes the entry match the pipeline node it belongs to:
    a graph cannot light up the box that failed if the failure does not say which
    box it was.
    """
    trace.add(
        agent="supervisor",
        action=stage,
        status=TraceStatus.ERROR,
        started=started,
        detail={"reason": reason, "outcome": "abort"},
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


def decision_message(*, tool: str, approve: bool, written: dict[str, Any] | None) -> str:
    """The trusted marker a continuation turn routes on, in place of a message.

    Written by Prope after a proposal is settled — never by a person, never by
    a model — which is what makes it safe to hand the router as its `message`
    despite that field's UNTRUSTED label: the label guards against content
    pretending to be commands, and this *is* the command, issued by the system
    that executed the decision. Identifiers only; a proposal's arguments may
    carry a whole prompt body and none of it belongs here.
    """
    status = "confirmed" if approve else "rejected"
    identifiers = [
        f"{key}={written[key]}"
        for key in ("prompt_id", "version_id", "key_id", "folder_slug")
        if isinstance(written, dict) and written.get(key)
    ]
    suffix = f" ({', '.join(identifiers)})" if identifiers else ""
    return f"HUMAN_DECISION {status} {tool}{suffix}. Continue the remaining task with tools, or acknowledge."


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    """What a confirmed or rejected proposal produced.

    `secret_once` is the one channel a minted key's plaintext may travel — here,
    in the confirmation response, and nowhere else. The reply rails redact
    credential-shaped text, so a secret that went through the model's answer
    would arrive as `[đã ẩn]`; this field never touches a model.
    """

    status: str
    code: str | None = None
    prompt_id: str | None = None
    version_id: str | None = None
    secret_once: str | None = None
    directives: list[UiDirective] = field(default_factory=list)


#: `tool -> where the person manages that act manually`. The navigation that
#: follows a confirmed write is derived from this table and never from anything
#: a model said — same rule as `_directives_for`, one layer later.
_CONFIRMED_NAVIGATION: Final[dict[str, Any]] = {
    ToolName.CREATE_PROMPT.value: lambda written: [
        {"kind": "navigate", "to": f"/app/prompts/{written['prompt_id']}"},
        {"kind": "highlight", "target": "version-rail"},
    ],
    ToolName.CREATE_REVISION.value: lambda written: [
        {"kind": "navigate", "to": f"/app/prompts/{written['prompt_id']}"},
        {"kind": "highlight", "target": "version-rail"},
    ],
    ToolName.UPDATE_PROMPT.value: lambda written: [{"kind": "navigate", "to": f"/app/prompts/{written['prompt_id']}"}],
    ToolName.RETIRE_PROMPT.value: lambda written: [{"kind": "navigate", "to": "/app/prompts"}],
    ToolName.CREATE_FOLDER.value: lambda written: [
        {"kind": "navigate", "to": f"/app/prompts/folder/{written.get('folder_slug', '')}"}
    ],
    ToolName.RENAME_FOLDER.value: lambda written: [
        {"kind": "navigate", "to": f"/app/prompts/folder/{written.get('folder_slug', '')}"}
    ],
    ToolName.DELETE_FOLDER.value: lambda written: [
        {"kind": "navigate", "to": "/app/prompts"},
        {"kind": "highlight", "target": "prompt-table"},
    ],
    ToolName.CREATE_API_KEY.value: lambda written: [
        {"kind": "navigate", "to": "/app/settings/keys"},
        {"kind": "highlight", "target": "keys-list"},
    ],
    ToolName.REVOKE_API_KEY.value: lambda written: [
        {"kind": "navigate", "to": "/app/settings/keys"},
        {"kind": "highlight", "target": "keys-list"},
    ],
    ToolName.SET_API_KEY_SCOPE.value: lambda written: [
        {"kind": "navigate", "to": "/app/settings/keys"},
        {"kind": "highlight", "target": "keys-list"},
    ],
    ToolName.UPDATE_PROVIDER.value: lambda written: [
        {"kind": "navigate", "to": "/app/settings/providers"},
        {"kind": "highlight", "target": "providers-list"},
    ],
    ToolName.DELETE_PROVIDER.value: lambda written: [{"kind": "navigate", "to": "/app/settings/providers"}],
}


def _start_eval_run_navigation(written: dict[str, Any]) -> list[dict[str, Any]]:
    prompt_id = str(written.get("prompt_id") or "")
    return (
        [
            {"kind": "navigate", "to": f"/app/prompts/{prompt_id}/evaluation/run"},
            {"kind": "highlight", "target": "eval-runs"},
        ]
        if prompt_id
        else []
    )


_CONFIRMED_NAVIGATION[ToolName.START_EVAL_RUN.value] = _start_eval_run_navigation


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

    executor = CONFIRMED_EXECUTORS.get(action["tool"])
    if executor is None:  # pragma: no cover - the catalogue is closed
        return ConfirmationResult(status="failed", code="chat_tool_unknown")

    context = tools.ToolContext(db=db, workspace_id=workspace_id, actor_id=actor_id, visible=visible)

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
        **{
            key: value
            for key, value in written.items()
            if key in {"prompt_id", "version_id", "key_id", "folder_slug", "run_count"}
            and isinstance(value, (str, int))
        },
    )

    navigation = _CONFIRMED_NAVIGATION.get(action["tool"], lambda _w: [])
    directives = sanitise_directives(navigation(written))

    return ConfirmationResult(
        status="confirmed",
        prompt_id=written.get("prompt_id"),
        version_id=written.get("version_id"),
        secret_once=written.get("secret_once"),
        directives=directives,
    )
