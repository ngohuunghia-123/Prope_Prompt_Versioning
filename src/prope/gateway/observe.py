"""ADR-0059 — the path for a call the gateway cannot resolve and forwards anyway.

**Nothing on this path composes, renders, or substitutes anything.** The caller's
messages go upstream byte for byte, including the system message the ordinary
path refuses (``CallerSystemMessage``), because on this path that message is not
a conflict with a revision — it *is* the prompt, and it belongs to the caller.
ADR-0059 rejects fingerprint substitution by name for exactly this reason: a
gateway that quietly served a registered body in place of the one a product sent
would break the product and break the claim that a call is traceable to what
served it.

**The response carries no `prope` block and no `x-prope-version-id`.** Those
fields answer *which revision served this*, and the honest answer here is *none*.
A block with nulls in it would be worse than its absence: an integration checking
for the key's presence would read a forwarded call as a governed one. What it
does carry is ``x-prope-observed: true`` and the call id, which is the pair a
person needs to find the row afterwards.

**There is no fallback.** ``binding.fallback_answer`` is a property of a
revision, and there is no revision. An upstream error on this path is an upstream
error, translated and returned exactly as it arrived.

**Two writes happen after the flush, in one background task**: the call record
(``source=observed``, ADR-0060) and the observation itself. The order matters
only in that the record is the one that costs money if lost, so it goes first and
the observation is best-effort behind it (A-155).
"""

from collections.abc import AsyncIterator, Mapping
from datetime import datetime
from typing import Any

import structlog
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.background import BackgroundTask

from prope.access_control.seams import AuthenticatedKey
from prope.call_ledger.domain import Outcome, Source
from prope.gateway.domain import DONE, STREAM_HEADERS, added_latency_ms, elapsed_ms, sse
from prope.gateway.errors import error_payload, translate_dispatch_error
from prope.gateway.observability import observed_call_total
from prope.gateway.records import CallFacts, record_call, serialise
from prope.gateway.schemas import ChatCompletionRequest
from prope.prompt_observation.seams import ObservationDraft, record_observation
from prope.provider_access.domain import DispatchError, DispatchResult, Priority, Usage
from prope.provider_access.normalise import read_usage
from prope.provider_access.seams import dispatch

log = structlog.get_logger(__name__)

__all__ = ["FORWARDED_HEADER", "forward"]

#: The one header that says what happened. Present and `true` on every forwarded
#: response, absent on every served one — a header a client can branch on without
#: parsing a body, and the only signal a consumer gets that Prope did not govern
#: this call.
FORWARDED_HEADER = "x-prope-observed"

#: Dropped from the parameters passed upstream because `compose_request` sets
#: them itself from its own arguments. Passing them through would let a caller's
#: `messages` key in the extras race the one the gateway assembled.
_GATEWAY_OWNED = frozenset({"model", "messages", "stream", "stream_options", "prope"})


def caller_parameters(payload: ChatCompletionRequest) -> dict[str, Any]:
    """The caller's own sampling parameters, verbatim (A-097).

    ``ChatCompletionRequest`` is ``extra="allow"``, so ``temperature``,
    ``max_tokens``, ``tools`` and everything else a caller sends lands in
    ``model_extra`` untouched. On the ordinary path those are ignored in favour
    of the revision's stored parameters, which is A-097's point — the release is
    what decides how the model is called. Here there is no release, so the
    caller's own settings are the only ones there are, and dropping them would
    change a product's behaviour the day it switched its base URL.
    """
    extra = payload.model_extra or {}
    return {key: value for key, value in extra.items() if key not in _GATEWAY_OWNED}


async def forward(
    *,
    payload: ChatCompletionRequest,
    key: AuthenticatedKey,
    sessionmaker: async_sessionmaker[AsyncSession],
    facts: CallFacts,
    started: float,
    arrived: datetime,
    deadline_ms: int,
) -> Any:
    """Send the caller's request on unchanged, and record what it was.

    The response machinery — the SSE framing, the latency sums, the error
    translation — is imported from ``domain`` and ``errors`` rather than
    reimplemented, and that is load-bearing rather than tidy: a forwarded error
    must be translated by the same function that translates a served one, or the
    two paths drift into two error vocabularies for one gateway. It lives below
    both callers because ``routes`` imports this module and the other direction
    would be a cycle.
    """
    messages = payload.caller_messages()

    outcome = await dispatch(
        sessionmaker,
        workspace_id=key.workspace_id,
        provider_config_id=facts.provider_config_id or "",
        upstream_model=facts.upstream_model or payload.model,
        parameters=caller_parameters(payload),
        messages=messages,
        stream=payload.stream,
        deadline_ms=deadline_ms,
        priority=Priority.INTERACTIVE,
    )

    draft = ObservationDraft(
        workspace_id=key.workspace_id,
        namespace=key.observe_namespace or "",
        call_id=facts.call_id,
        consumer_key_id=key.key_id,
        upstream_model=facts.upstream_model or payload.model,
        occurred_at=arrived,
        messages=messages,
    )

    if isinstance(outcome, DispatchError):
        # No fallback branch, and no `binding` to look one up on. An upstream
        # error here is the provider's answer to the caller's own request, and
        # the caller is the only party who can act on it.
        observed_call_total.labels(outcome=Outcome.UPSTREAM_ERROR.value).inc()
        facts.outcome = Outcome.UPSTREAM_ERROR
        facts.error_class = outcome.error_class.value
        facts.upstream_duration_ms = 0
        facts.added_latency_ms = elapsed_ms(started)
        translated = translate_dispatch_error(outcome)
        facts.response_body = serialise(
            error_payload(translated.error_type, translated.code, translated.message, translated.param)
        )
        # The observation is still written. A prompt that fails upstream is a
        # prompt the workspace is running — arguably the one most worth finding.
        translated.background = _after_flush(sessionmaker, facts, draft)
        raise translated

    if payload.stream:
        return _stream(
            result=outcome,
            facts=facts,
            draft=draft,
            sessionmaker=sessionmaker,
            started=started,
        )

    return _non_streaming(
        result=outcome,
        facts=facts,
        draft=draft,
        sessionmaker=sessionmaker,
        started=started,
    )


def _headers(facts: CallFacts) -> dict[str, str]:
    """What a forwarded response says about itself. Deliberately three lines.

    No ``x-prope-version-id``, no ``x-prope-revision``, no ``x-prope-pinned`` —
    every one of those answers a question about a revision that does not exist,
    and an empty or zero value for them would be a lie in the shape of an answer.
    """
    return {
        FORWARDED_HEADER: "true",
        "x-prope-model": facts.model_name,
        "x-prope-call-id": facts.call_id,
    }


def _non_streaming(
    *,
    result: DispatchResult,
    facts: CallFacts,
    draft: ObservationDraft,
    sessionmaker: async_sessionmaker[AsyncSession],
    started: float,
) -> JSONResponse:
    observed_call_total.labels(outcome=Outcome.OK.value).inc()
    _count_usage(facts, result.usage)
    facts.outcome = Outcome.OK
    facts.upstream_duration_ms = int(result.upstream_duration_ms)
    facts.added_latency_ms = added_latency_ms(started, result.upstream_duration_ms)
    facts.response_body = serialise(result.response)

    # The provider's own body, unaltered — not even the `id`. On the served path
    # the id is overwritten because it is the caller's only handle on Prope's
    # record; here the caller's handle is the header, and rewriting an id on a
    # call Prope did not govern would make a forwarded response harder to debug
    # against the provider's own dashboard for no gain.
    return JSONResponse(
        status_code=200,
        content=dict(result.response or {}),
        headers=_headers(facts),
        background=_after_flush(sessionmaker, facts, draft),
    )


def _count_usage(facts: CallFacts, usage: Usage | None) -> None:
    if usage is None or not usage.reported:
        facts.input_tokens = None
        facts.output_tokens = None
        return
    facts.input_tokens = usage.input_tokens
    facts.output_tokens = usage.output_tokens


def _stream(
    *,
    result: DispatchResult,
    facts: CallFacts,
    draft: ObservationDraft,
    sessionmaker: async_sessionmaker[AsyncSession],
    started: float,
) -> StreamingResponse:
    upstream = result.stream

    async def relay() -> AsyncIterator[str]:
        accumulated: list[str] = []
        terminal: DispatchError | None = None

        if upstream is not None:
            pending: Any = await _next(upstream)
            while pending is not None:
                if isinstance(pending, DispatchError):
                    terminal = pending
                    break
                usage = read_usage(pending)
                if usage is not None:
                    _count_usage(facts, usage)
                for choice in pending.get("choices") or ():
                    if isinstance(choice, Mapping):
                        delta = choice.get("delta")
                        if isinstance(delta, Mapping) and isinstance(delta.get("content"), str):
                            accumulated.append(delta["content"])
                # Relayed as it arrived. No `prope` block on the first chunk, no
                # id rewrite on any of them — see `_non_streaming`.
                yield sse(dict(pending))
                pending = await _next(upstream)

        # The outcome is decided once, in one place, and every branch names one.
        #
        # `upstream is None` means `dispatch` handed back a streaming result with
        # no iterator on it — an internal defect rather than anything the provider
        # did. The served path answers a 500 for it; this one cannot, because the
        # response headers were committed before this generator ran. So it records
        # the truth and closes the stream cleanly. What it must NOT do is fall
        # through to `ok`, which would file an empty forwarded call as a success
        # in the table the ninety-day "N discovered, M governed" number is counted
        # from.
        if upstream is None:
            outcome, error_class = Outcome.UPSTREAM_ERROR, "stream_missing"
        elif terminal is not None:
            outcome, error_class = Outcome.TRUNCATED, terminal.error_class.value
        else:
            outcome, error_class = Outcome.OK, None

        observed_call_total.labels(outcome=outcome.value).inc()
        facts.outcome = outcome
        facts.error_class = error_class

        yield DONE

        facts.upstream_duration_ms = int(result.upstream_duration_ms)
        facts.added_latency_ms = added_latency_ms(started, result.upstream_duration_ms)
        facts.response_body = "".join(accumulated)
        await _record(sessionmaker, facts, draft)

    return StreamingResponse(
        relay(),
        status_code=200,
        media_type="text/event-stream",
        headers=_headers(facts) | STREAM_HEADERS,
    )


async def _next(iterator: AsyncIterator[Any]) -> Any:
    try:
        return await anext(iterator)
    except StopAsyncIteration:
        return None


def _after_flush(
    sessionmaker: async_sessionmaker[AsyncSession],
    facts: CallFacts,
    draft: ObservationDraft,
) -> BackgroundTask:
    return BackgroundTask(_record, sessionmaker, facts, draft)


async def _record(
    sessionmaker: async_sessionmaker[AsyncSession],
    facts: CallFacts,
    draft: ObservationDraft,
) -> None:
    """The two writes, in the order of what it costs to lose them.

    ``record_call`` first: a lost call record is a call that never appears in a
    workspace's spend, and A-098 makes that table the single answer to *what did
    this workspace spend*. The observation second, because losing one costs a
    counter and a row that the next call with the same body re-creates.

    **There is no ``try`` around the second call and there must not be one.**
    INT-034 declares that the seam never raises and the seam is where that is
    kept — with the counter and the log line beside the failure they describe,
    in the module that owns them. A defensive ``except`` here would be a second
    implementation of the same contract, and the one that goes stale is always
    the copy.
    """
    facts.source = Source.OBSERVED
    record_call(facts)
    await record_observation(sessionmaker, draft)
