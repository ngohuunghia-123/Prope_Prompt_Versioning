"""The playground turn: dispatch a *draft* revision, relay it, record it as internal.

**Why this exists at all, when the gateway already serves revisions.** The gateway
resolves released revisions and pinned-approved ones, enforced under
`release_control` by a database constraint. The prompt a person has just finished
writing is a Draft, so the one surface that could talk to it refuses to — which
would leave "try it" available only after approval, i.e. after the moment it is
useful. This module is the other door: session-authenticated, revision-explicit,
and unable to reach anything a person cannot already read.

**It is not a second gateway and must not grow into one.** No key authenticates
it, no model name is resolved, no released pointer is consulted, and nothing here
is on a consumer's hot path. What it shares with the gateway is
`prope.prompt_composition` — one implementation of ADR-0011, deliberately moved to
a module-neutral home when this file needed it — and the chunk-relay *shape*,
which is duplicated and is the honest cost of streaming here.

**The fallback answer is deliberately NOT served.** The gateway substitutes
`fallback_answer` when a provider fails, because a consumer's product must degrade
rather than break. A trial exists to show what actually happened; masking a
credential rejection with the prompt's own safety net would hide the single most
useful thing the screen could tell somebody. So an upstream failure surfaces as an
error event in the stream, and is recorded as one.

**A-046.** No message content, no rendered body, no variable value reaches a log
line or a metric label from this module.
"""

import json
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from prope.call_ledger.domain import CallBodyDraft, CallRecordDraft, Outcome, Source
from prope.call_ledger.enqueue import enqueue
from prope.call_ledger.pricing import compute_cost, resolve_price
from prope.db.session import workspace_transaction
from prope.prompt_registry.domain import RevisionRead
from prope.provider_access.domain import DispatchError, DispatchResult, Priority, Usage
from prope.provider_access.normalise import read_usage
from prope.provider_access.seams import dispatch

log = structlog.get_logger(__name__)

__all__ = ["TRIAL_DEADLINE_MS", "TrialFacts", "new_trial_call_id", "stream_trial"]

#: A person is watching this one, so it gets the interactive budget rather than
#: the eval executor's. Same figure as the gateway's, for the same reason: it is
#: what a chat client's own timeout tends to be.
TRIAL_DEADLINE_MS = 60_000

#: ``cal_`` like every other call, because these rows sit in the same table and a
#: second prefix would make ``call_id`` mean two things. What distinguishes a
#: trial is ``source``, which is a column, not a naming convention.
CALL_ID_PREFIX = "cal_"

DONE = "data: [DONE]\n\n"


def new_trial_call_id() -> str:
    return f"{CALL_ID_PREFIX}{ULID()}"


def _sse(payload: Mapping[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _serialise(payload: Any) -> str | None:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return None


def _chunk_text(chunk: Mapping[str, Any]) -> str:
    text = ""
    for choice in chunk.get("choices") or ():
        if not isinstance(choice, Mapping):
            continue
        delta = choice.get("delta")
        if isinstance(delta, Mapping) and isinstance(delta.get("content"), str):
            text += delta["content"]
    return text


def _usage_only(chunk: Mapping[str, Any]) -> bool:
    return not chunk.get("choices") and read_usage(chunk) is not None


@dataclass(slots=True)
class TrialFacts:
    """What the ledger row will say, accumulated as the turn happens.

    Mutable and assembled in place, exactly like the gateway's `CallFacts`: the
    outcome and the token counts are not known until the stream ends, and a
    frozen record built at the end would have to carry every intermediate value
    forward as an argument.

    `consumer_key_id` is absent from this class rather than set to `None`, and the
    absence is the point — `ck_call_record_playground_calls_are_internal` refuses
    a playground row that names a key, and a field here would be a field somebody
    could fill.
    """

    call_id: str
    workspace_id: str
    created_at: datetime
    prompt_id: str
    version_id: str
    revision_number: int
    model_name: str
    provider_config_id: str | None
    upstream_model: str | None
    outcome: Outcome = Outcome.OK
    input_tokens: int | None = None
    output_tokens: int | None = None
    added_latency_ms: int | None = None
    upstream_duration_ms: int | None = None
    error_class: str | None = None
    request_body: str | None = None
    response_body: str | None = None

    def draft(self) -> CallRecordDraft:
        return CallRecordDraft(
            call_id=self.call_id,
            workspace_id=self.workspace_id,
            source=Source.PLAYGROUND,
            outcome=self.outcome,
            created_at=self.created_at,
            prompt_id=self.prompt_id,
            version_id=self.version_id,
            revision_number=self.revision_number,
            provider_config_id=self.provider_config_id,
            upstream_model=self.upstream_model,
            streaming=True,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            added_latency_ms=self.added_latency_ms,
            upstream_duration_ms=self.upstream_duration_ms,
            error_class=self.error_class,
            body=CallBodyDraft(
                request_body=self.request_body, response_body=self.response_body
            ),
        )


def record_trial(facts: TrialFacts) -> None:
    """Hand the row to call-ledger. Never raises — `enqueue` is INT-018's contract.

    Called from inside the relay generator after the terminal event has been
    yielded, so the handoff is outside the interval the person is waiting on.
    """
    try:
        enqueue(facts.draft())
    except Exception as error:  # pragma: no cover - enqueue's own contract is never-raise
        log.warning(
            "prompt_registry.trial_record_abandoned",
            call_id=facts.call_id,
            workspace_id=facts.workspace_id,
            reason=type(error).__name__,
        )


def _count_usage(facts: TrialFacts, usage: Usage | None) -> None:
    if usage is None or not usage.reported:
        facts.input_tokens = None
        facts.output_tokens = None
        return
    facts.input_tokens = usage.input_tokens
    facts.output_tokens = usage.output_tokens


def _error_event(error: DispatchError) -> dict[str, Any]:
    """The provider's failure, named. **`message` is the provider's, not a body.**

    `DispatchError.message` is provider-access's own summary of a transport or
    status failure; it never carries request or response content, which is why it
    can cross to a screen. The class is what the screen actually renders — a
    person testing a prompt needs to know whether they hit a rate limit or a
    rejected credential, and those two have completely different next steps.
    """
    return {
        "prope": {
            "error": {
                "class": error.error_class.value,
                "message": error.message,
                "retryable": error.retryable,
            }
        }
    }


async def _priced(
    sessionmaker: async_sessionmaker[AsyncSession], facts: TrialFacts
) -> tuple[Decimal | None, str | None]:
    """What this turn cost, resolved exactly as the ledger will resolve it.

    **The same two functions the writer uses, at the same instant.**
    ``resolve_price`` at ``facts.created_at`` and ``compute_cost`` are CL-03's
    rule; calling them here rather than approximating in the browser is what
    makes the figure on the screen the figure that lands on the row. It can still
    differ in one case — a price row inserted between this turn and the drain —
    and that is the ledger's number, not this one's.

    **``None`` is unpriced and is never a zero**, which is the rule
    ``pricing.resolve_price`` states and the reason the screen has a separate
    "no price configured" state instead of showing ``0.00``.

    **Never raises.** A counter is a nicety on a turn that already succeeded, and
    a failed price lookup must not become a truncated answer.
    """
    if facts.input_tokens is None or facts.output_tokens is None:
        return None, None
    try:
        async with workspace_transaction(sessionmaker, facts.workspace_id) as db:
            price = await resolve_price(
                db,
                workspace_id=facts.workspace_id,
                provider_config_id=facts.provider_config_id,
                upstream_model=facts.upstream_model,
                at=facts.created_at,
            )
        if price is None:
            return None, None
        return compute_cost(facts.input_tokens, facts.output_tokens, price), price.currency
    except Exception as error:
        log.warning(
            "prompt_registry.trial_pricing_unavailable",
            call_id=facts.call_id,
            workspace_id=facts.workspace_id,
            reason=type(error).__name__,
        )
        return None, None


def _usage_event(
    facts: TrialFacts, cost: Decimal | None, currency: str | None
) -> dict[str, Any]:
    """The turn's meter, as the last event before ``[DONE]``.

    **Not a chunk, and shaped so it can never be mistaken for one.** It carries no
    ``choices``, so a client that only reads deltas ignores it entirely — the same
    property that lets the gateway's usage trailer pass through a plain OpenAI
    client. The cost is a **string** because it is a ``Decimal`` at ten places and
    a JSON number would round it in the parser, silently, in the last places that
    a reconciliation against the ledger would compare.
    """
    return {
        "prope": {
            "usage": {
                "call_id": facts.call_id,
                "input_tokens": facts.input_tokens,
                "output_tokens": facts.output_tokens,
                "cost": None if cost is None else str(cost),
                "currency": currency,
                "outcome": facts.outcome.value,
                "upstream_duration_ms": facts.upstream_duration_ms,
                "upstream_model": facts.upstream_model,
            }
        }
    }


async def _next(iterator: AsyncIterator[Any]) -> Any:
    try:
        return await anext(iterator)
    except StopAsyncIteration:
        return None


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


async def stream_trial(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    revision: RevisionRead,
    model_name: str,
    provider_config_id: str,
    upstream_model: str,
    parameters: Mapping[str, Any],
    messages: Sequence[Mapping[str, Any]],
    request_body: str | None,
) -> AsyncIterator[str]:
    """Dispatch and relay. **The generator owns the whole turn, including the record.**

    Returning an iterator rather than a response keeps FastAPI's
    `StreamingResponse` in the route where it is readable, and keeps the two
    things that must happen after the last chunk — the terminal event and the
    ledger row — inside one function so neither can be forgotten by a caller.

    **The binding is a parameter and no longer read off the revision.** The
    playground may try a revision against a different configuration or a different
    upstream model without touching it (``TrialRequest``), so what ran and what the
    revision binds are two facts. This function records the first, because that is
    the one the tokens were spent on; ``version_id`` on the same row records the
    second. The route has already resolved which is which and refuses when neither
    yields a binding — otherwise every turn returns the same configuration error
    and the screen reads as a broken prompt rather than an unconfigured one.
    """
    started = time.perf_counter()
    facts = TrialFacts(
        call_id=new_trial_call_id(),
        workspace_id=revision.workspace_id,
        created_at=datetime.now(UTC),
        prompt_id=revision.prompt_id,
        version_id=revision.version_id,
        revision_number=revision.revision_number,
        model_name=model_name,
        provider_config_id=provider_config_id,
        upstream_model=upstream_model,
        request_body=request_body,
    )

    outcome = await dispatch(
        sessionmaker,
        workspace_id=revision.workspace_id,
        provider_config_id=provider_config_id,
        upstream_model=upstream_model,
        parameters=parameters,
        messages=messages,
        stream=True,
        deadline_ms=TRIAL_DEADLINE_MS,
        priority=Priority.INTERACTIVE,
    )

    if isinstance(outcome, DispatchError):
        facts.outcome = Outcome.UPSTREAM_ERROR
        facts.error_class = outcome.error_class.value
        facts.upstream_duration_ms = 0
        facts.added_latency_ms = _elapsed_ms(started)
        facts.response_body = _serialise(_error_event(outcome))
        yield _sse(_error_event(outcome))
        yield DONE
        record_trial(facts)
        return

    async for event in _relay(sessionmaker, outcome, facts, started):
        yield event


async def _relay(
    sessionmaker: async_sessionmaker[AsyncSession],
    result: DispatchResult,
    facts: TrialFacts,
    started: float,
) -> AsyncIterator[str]:
    upstream = result.stream
    if upstream is None:
        # A streaming dispatch that returned no iterator is a provider-access bug,
        # not a caller's problem. Recorded as an upstream error so the turn is not
        # silently absent from the ledger.
        facts.outcome = Outcome.UPSTREAM_ERROR
        facts.error_class = "no_stream"
        facts.added_latency_ms = _elapsed_ms(started)
        yield _sse({"prope": {"error": {"class": "no_stream", "message": "", "retryable": False}}})
        yield DONE
        record_trial(facts)
        return

    pending: Any = await _next(upstream)
    accumulated: list[str] = []
    terminal: DispatchError | None = None
    stamped = False

    while pending is not None:
        if isinstance(pending, DispatchError):
            terminal = pending
            break

        accumulated.append(_chunk_text(pending))
        usage = read_usage(pending)
        if usage is not None:
            _count_usage(facts, usage)

        # A usage-only trailer carries no text and no choice. The gateway forwards
        # it when the caller asked for usage; nobody asks here, so it is counted
        # and dropped rather than rendered as an empty turn.
        if not _usage_only(pending):
            body = dict(pending)
            if not stamped:
                body["prope"] = {
                    "call_id": facts.call_id,
                    "version_id": facts.version_id,
                    "revision_number": facts.revision_number,
                    "upstream_model": facts.upstream_model,
                }
                stamped = True
            yield _sse(body)

        pending = await _next(upstream)

    if terminal is not None:
        # Mid-stream failure. TRUNCATED rather than UPSTREAM_ERROR, exactly as the
        # gateway classifies it: the provider generated tokens before it broke, and
        # those tokens were charged for.
        facts.outcome = Outcome.TRUNCATED
        facts.error_class = terminal.error_class.value
        yield _sse(_error_event(terminal))
    else:
        facts.outcome = Outcome.OK

    facts.upstream_duration_ms = int(result.upstream_duration_ms)
    facts.added_latency_ms = max(0, _elapsed_ms(started) - int(result.upstream_duration_ms))
    facts.response_body = "".join(accumulated)

    # The meter, before the terminator and after the last delta. A truncated turn
    # gets one too when the provider reported usage before it broke — those tokens
    # are on the row, so leaving them off the screen would make the screen and the
    # invoice disagree about a turn the person watched fail.
    cost, currency = await _priced(sessionmaker, facts)
    yield _sse(_usage_event(facts, cost, currency))
    yield DONE

    record_trial(facts)
