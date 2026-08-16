"""INT-022 — `POST /v1/chat/completions` and `GET /v1/models`, and nothing else."""

import json
import time
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.background import BackgroundTask

from prope.access_control.seams import AuthenticatedKey
from prope.call_ledger.domain import Outcome
from prope.gateway.admission import AdmissionRefused, admit
from prope.gateway.composition import (
    CallerSystemMessage,
    OversizeRequest,
    compose,
)
from prope.gateway.domain import (
    ModelReference,
    ModelReferenceInvalid,
    ServedIdentity,
    Stage,
    parse_model_reference,
)
from prope.gateway.errors import (
    ErrorType,
    GatewayError,
    error_payload,
    model_not_found,
    translate_dispatch_error,
)
from prope.gateway.observability import (
    chunk_relay_seconds,
    fallback_total,
    oversize_request_total,
    rejected_system_message_total,
    upstream_error_total,
    usage_missing_total,
)
from prope.gateway.records import CallFacts, caller_request_body, new_call_id, record_call, serialise
from prope.gateway.resolution import authenticate, released_listings, resolve_binding
from prope.gateway.schemas import ChatCompletionRequest
from prope.gateway.templating import MissingVariable, UnfilledPlaceholder, render
from prope.prompt_registry.domain import RevisionBinding
from prope.provider_access.domain import DispatchError, DispatchResult, ErrorClass, Priority, Usage
from prope.provider_access.normalise import read_usage
from prope.provider_access.seams import dispatch

log = structlog.get_logger(__name__)

router = APIRouter()

__all__ = ["DEADLINE_MS", "IMPLEMENTED_PATHS", "STREAM_HEADERS", "router"]

DEADLINE_MS = 60_000

CHAT_COMPLETIONS_PATH = "/chat/completions"

MODELS_PATH = "/models"

IMPLEMENTED_PATHS = frozenset({CHAT_COMPLETIONS_PATH, MODELS_PATH})

DONE = "data: [DONE]\n\n"

#: Told to every intermediary: **do not hold this response.**
#:
#: A `text/event-stream` is the one response shape whose value is in its timing —
#: INT-022's chunks are useful as they arrive and worthless as a batch. Any CDN or
#: reverse proxy between the gateway and the consumer will happily buffer it into
#: a single write unless told otherwise, and the failure that produces is a lie
#: rather than an error: the whole answer lands at once, the consumer reports no
#: fault, and it reads as a slow model. Nothing in Prope's logs disagrees, because
#: from here the stream went out chunk by chunk.
#:
#: `no-transform` is the directive with teeth. It forbids an intermediary from
#: altering the payload at all — Cloudflare documents it as what disables edge
#: compression and Polish, and compression is the mechanism that buffers, because
#: a compressor cannot emit until it has something to compress. `no-cache` is
#: belt and braces for a response that must never be replayed to a second caller,
#: and `x-accel-buffering: no` is nginx's own switch, which several proxies now
#: honour by convention.
#:
#: Costs nothing when no proxy is in the path, which is why it is unconditional
#: rather than a deployment setting: the gateway does not know what is downstream
#: of it, and a consumer behind their own corporate proxy is not visible here at
#: all.
STREAM_HEADERS = {
    "cache-control": "no-cache, no-transform",
    "x-accel-buffering": "no",
}

FALLBACK_REASONS: dict[ErrorClass, str] = {
    ErrorClass.RATE_LIMITED: "rate_limited",
    ErrorClass.CREDENTIAL_REJECTED: "credential_rejected",
    ErrorClass.UPSTREAM_TIMEOUT: "timeout",
}


def _sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    sessionmaker = getattr(request.app.state, "sessionmaker", None)
    if sessionmaker is None:
        raise GatewayError(
            503,
            ErrorType.API,
            "gateway_not_ready",
            "The gateway has no database sessionmaker; its lifespan has not run.",
        )
    return sessionmaker


def _fallback_reason(error: DispatchError) -> str:
    return FALLBACK_REASONS.get(error.error_class, "upstream_5xx")


def _identity(
    reference: ModelReference, binding: RevisionBinding, *, fallback: bool
) -> ServedIdentity:
    return ServedIdentity(
        model_name=reference.raw,
        version_id=binding.version_id,
        revision_number=binding.revision_number,
        pinned=reference.pinned,
        fallback=fallback,
        upstream_model=binding.upstream_model,
    )


def _sse(payload: Mapping[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _usage_only(chunk: Mapping[str, Any]) -> bool:
    return not chunk.get("choices") and read_usage(chunk) is not None


def _chunk_text(chunk: Mapping[str, Any]) -> str:
    text = ""
    for choice in chunk.get("choices") or ():
        if not isinstance(choice, Mapping):
            continue
        delta = choice.get("delta")
        if isinstance(delta, Mapping) and isinstance(delta.get("content"), str):
            text += delta["content"]
    return text


def _completion(identity: ServedIdentity, call_id: str, created: int, content: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{call_id}",
        "object": "chat.completion",
        "created": created,
        "model": identity.model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "prope": identity.body(),
    }


def _completion_chunk(
    identity: ServedIdentity, call_id: str, created: int, content: str
) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{call_id}",
        "object": "chat.completion.chunk",
        "created": created,
        "model": identity.model_name,
        "choices": [
            {"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "prope": identity.body(),
    }


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _added_latency_ms(started: float, upstream_ms: float) -> int:
    return max(0, _elapsed_ms(started) - int(upstream_ms))


def _refuse(facts: CallFacts, error: GatewayError, started: float) -> GatewayError:
    facts.outcome = Outcome.CALLER_ERROR
    facts.added_latency_ms = _elapsed_ms(started)
    facts.response_body = serialise(
        error_payload(error.error_type, error.code, error.message, error.param)
    )
    error.background = BackgroundTask(record_call, facts)
    return error


@router.post(CHAT_COMPLETIONS_PATH)
async def chat_completions(request: Request, payload: ChatCompletionRequest) -> Any:
    started = time.perf_counter()
    arrived = datetime.now(UTC)
    sessionmaker = _sessionmaker(request)

    key = await authenticate(sessionmaker, request.headers.get("authorization"))

    try:
        with admit(key.key_id):
            return await _serve(
                request=request,
                payload=payload,
                key=key,
                sessionmaker=sessionmaker,
                started=started,
                arrived=arrived,
            )
    except AdmissionRefused as refused:
        log.info(
            "gateway.admission_refused",
            key_id=refused.key_id,
            workspace_id=key.workspace_id,
            reason="in_flight_cap",
        )
        raise GatewayError(
            429,
            ErrorType.RATE_LIMIT,
            "rate_limit_exceeded",
            "Too many concurrent requests for this API key.",
            headers={"retry-after": "1"},
        ) from refused


async def _serve(
    *,
    request: Request,
    payload: ChatCompletionRequest,
    key: AuthenticatedKey,
    sessionmaker: async_sessionmaker[AsyncSession],
    started: float,
    arrived: datetime,
) -> Any:
    call_id = new_call_id()
    caller_messages = payload.caller_messages()
    variables = payload.variables()

    try:
        reference = parse_model_reference(payload.model)
    except ModelReferenceInvalid as invalid:
        raise model_not_found(invalid.raw) from invalid

    binding = await resolve_binding(sessionmaker, key, reference)

    facts = CallFacts(
        call_id=call_id,
        workspace_id=key.workspace_id,
        consumer_key_id=key.key_id,
        created_at=arrived,
        outcome=Outcome.OK,
        model_name=reference.model_name,
        streaming=payload.stream,
        pinned=reference.pinned,
        prompt_id=binding.prompt_id,
        version_id=binding.version_id,
        revision_number=binding.revision_number,
        provider_config_id=binding.provider_config_id,
        upstream_model=binding.upstream_model,
        request_body=caller_request_body(caller_messages, variables),
    )

    identity = _identity(reference, binding, fallback=False)

    try:
        system_prompt = render(binding.body, variables)
        composed = compose(caller_messages, system_prompt)
    except CallerSystemMessage as refusal:
        rejected_system_message_total.inc()
        raise _refuse(
            facts,
            GatewayError(
                400,
                ErrorType.INVALID_REQUEST,
                "system_message_not_allowed",
                f"The model `{reference.raw}` carries its own system prompt. "
                "Remove the message with role `system` from this request.",
                param=f"messages.{refusal.index}.role",
            ),
            started,
        ) from refusal
    except MissingVariable as missing:
        raise _refuse(
            facts,
            GatewayError(
                400,
                ErrorType.INVALID_REQUEST,
                "missing_variable",
                f"The model `{reference.raw}` requires the variable `{missing.name}`. "
                "Supply it in the top-level `prope.variables` object.",
                param=f"prope.variables.{missing.name}",
            ),
            started,
        ) from missing
    except UnfilledPlaceholder as unfilled:
        raise _refuse(
            facts,
            GatewayError(
                400,
                ErrorType.INVALID_REQUEST,
                "missing_variable",
                f"The model `{reference.raw}` has a placeholder no value was supplied for.",
                param="prope.variables",
            ),
            started,
        ) from unfilled
    except OversizeRequest as oversize:
        oversize_request_total.inc()
        raise _refuse(
            facts,
            GatewayError(
                400,
                ErrorType.INVALID_REQUEST,
                "request_too_large",
                "The composed message set is larger than this gateway accepts.",
                param="messages",
            ),
            started,
        ) from oversize

    if binding.provider_config_id is None or binding.upstream_model is None:
        facts.outcome = Outcome.UPSTREAM_ERROR
        facts.error_class = "configuration_unusable"
        facts.added_latency_ms = _elapsed_ms(started)
        raise GatewayError(
            500,
            ErrorType.API,
            "provider_configuration_unusable",
            "The released revision binds no provider configuration.",
            background=BackgroundTask(record_call, facts),
        )

    outcome = await dispatch(
        sessionmaker,
        workspace_id=key.workspace_id,
        provider_config_id=binding.provider_config_id,
        upstream_model=binding.upstream_model,
        parameters=binding.parameters,
        messages=composed,
        stream=payload.stream,
        deadline_ms=DEADLINE_MS,
        priority=Priority.INTERACTIVE,
    )

    if isinstance(outcome, DispatchError):
        return _pre_first_byte(
            error=outcome,
            binding=binding,
            reference=reference,
            facts=facts,
            payload=payload,
            started=started,
            arrived=arrived,
        )

    if payload.stream:
        return await _stream(
            result=outcome,
            binding=binding,
            reference=reference,
            identity=identity,
            facts=facts,
            payload=payload,
            started=started,
            arrived=arrived,
        )

    return _non_streaming(result=outcome, identity=identity, facts=facts, started=started)


def _pre_first_byte(
    *,
    error: DispatchError,
    binding: RevisionBinding,
    reference: ModelReference,
    facts: CallFacts,
    payload: ChatCompletionRequest,
    started: float,
    arrived: datetime,
) -> Any:
    upstream_error_total.labels(stage=Stage.PRE_FIRST_BYTE.value).inc()
    facts.error_class = error.error_class.value
    facts.upstream_duration_ms = 0

    if not (error.fallback_eligible and binding.fallback_answer):
        facts.outcome = Outcome.UPSTREAM_ERROR
        facts.added_latency_ms = _elapsed_ms(started)
        translated = translate_dispatch_error(error)
        facts.response_body = serialise(
            error_payload(
                translated.error_type, translated.code, translated.message, translated.param
            )
        )
        translated.background = BackgroundTask(record_call, facts)
        raise translated

    fallback_total.labels(reason=_fallback_reason(error)).inc()
    identity = _identity(reference, binding, fallback=True)
    created = int(arrived.timestamp())

    facts.outcome = Outcome.FALLBACK
    facts.fallback = True
    facts.input_tokens = None
    facts.output_tokens = None
    facts.added_latency_ms = _elapsed_ms(started)
    facts.response_body = binding.fallback_answer

    log.info(
        "gateway.fallback_served",
        call_id=facts.call_id,
        workspace_id=facts.workspace_id,
        model_name=facts.model_name,
        version_id=facts.version_id,
        error_class=error.error_class.value,
        fallback=True,
    )

    if not payload.stream:
        body = _completion(identity, facts.call_id, created, binding.fallback_answer)
        return JSONResponse(
            status_code=200,
            content=body,
            headers=identity.headers(),
            background=BackgroundTask(record_call, facts),
        )

    async def stream() -> AsyncIterator[str]:
        yield _sse(_completion_chunk(identity, facts.call_id, created, binding.fallback_answer))
        yield DONE
        record_call(facts)

    return StreamingResponse(
        stream(),
        status_code=200,
        media_type="text/event-stream",
        headers=identity.headers() | STREAM_HEADERS,
    )


def _non_streaming(
    *, result: DispatchResult, identity: ServedIdentity, facts: CallFacts, started: float
) -> JSONResponse:
    _count_usage(facts, result.usage)
    facts.outcome = Outcome.OK
    facts.upstream_duration_ms = int(result.upstream_duration_ms)
    facts.added_latency_ms = _added_latency_ms(started, result.upstream_duration_ms)
    facts.response_body = serialise(result.response)

    body = identity.stamp(result.response or {})
    return JSONResponse(
        status_code=200,
        content=body,
        headers=identity.headers(),
        background=BackgroundTask(record_call, facts),
    )


def _count_usage(facts: CallFacts, usage: Usage | None) -> None:
    if usage is None or not usage.reported:
        usage_missing_total.inc()
        facts.input_tokens = None
        facts.output_tokens = None
        return
    facts.input_tokens = usage.input_tokens
    facts.output_tokens = usage.output_tokens


async def _stream(
    *,
    result: DispatchResult,
    binding: RevisionBinding,
    reference: ModelReference,
    identity: ServedIdentity,
    facts: CallFacts,
    payload: ChatCompletionRequest,
    started: float,
    arrived: datetime,
) -> Any:
    upstream = result.stream
    if upstream is None:
        raise GatewayError(
            500,
            ErrorType.API,
            "internal_error",
            "The server had an error while processing your request.",
        )

    first: Any = None
    try:
        first = await anext(upstream)
    except StopAsyncIteration:
        first = None

    if isinstance(first, DispatchError):
        return _pre_first_byte(
            error=first,
            binding=binding,
            reference=reference,
            facts=facts,
            payload=payload,
            started=started,
            arrived=arrived,
        )

    wants_usage = payload.wants_usage()

    async def relay() -> AsyncIterator[str]:
        accumulated: list[str] = []
        terminal: DispatchError | None = None
        stamped = False
        pending: Any = first

        while pending is not None:
            chunk_started = time.perf_counter()
            if isinstance(pending, DispatchError):
                terminal = pending
                break

            accumulated.append(_chunk_text(pending))
            usage = read_usage(pending)
            if usage is not None:
                _count_usage(facts, usage)

            if _usage_only(pending) and not wants_usage:
                pending = await _next(upstream)
                chunk_relay_seconds.observe(time.perf_counter() - chunk_started)
                continue

            body = dict(pending)
            if not stamped:
                body["prope"] = identity.body()
                body["model"] = identity.model_name
                stamped = True
            yield _sse(body)
            chunk_relay_seconds.observe(time.perf_counter() - chunk_started)
            pending = await _next(upstream)

        if terminal is not None:
            upstream_error_total.labels(stage=Stage.MID_STREAM.value).inc()
            translated = translate_dispatch_error(terminal)
            facts.outcome = Outcome.TRUNCATED
            facts.error_class = terminal.error_class.value
            yield _sse(
                error_payload(
                    translated.error_type, translated.code, translated.message, translated.param
                )
            )
        else:
            facts.outcome = Outcome.OK
            if facts.input_tokens is None and facts.output_tokens is None:
                usage_missing_total.inc()

        yield DONE

        facts.upstream_duration_ms = int(result.upstream_duration_ms)
        facts.added_latency_ms = _added_latency_ms(started, result.upstream_duration_ms)
        facts.response_body = "".join(accumulated)
        record_call(facts)

    return StreamingResponse(
        relay(),
        status_code=200,
        media_type="text/event-stream",
        headers=identity.headers() | STREAM_HEADERS,
    )


async def _next(iterator: AsyncIterator[Any]) -> Any:
    try:
        return await anext(iterator)
    except StopAsyncIteration:
        return None


@router.get(MODELS_PATH)
async def models(request: Request) -> JSONResponse:
    sessionmaker = _sessionmaker(request)
    key = await authenticate(sessionmaker, request.headers.get("authorization"))
    listings = await released_listings(sessionmaker, key)

    return JSONResponse(
        status_code=200,
        content={
            "object": "list",
            "data": [
                {
                    "id": listing.model_name,
                    "object": "model",
                    "created": 0,
                    "owned_by": "prope",
                    "prope": {
                        "version_id": listing.version_id,
                        "revision_number": listing.revision_number,
                    },
                }
                for listing in listings
            ],
        },
    )


@router.api_route(
    "/{unimplemented:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def not_implemented(unimplemented: str) -> JSONResponse:
    path = f"/{unimplemented}"
    if path in IMPLEMENTED_PATHS:
        raise GatewayError(
            405,
            ErrorType.INVALID_REQUEST,
            "method_not_allowed",
            "Not allowed on this endpoint.",
        )
    raise GatewayError(
        501,
        ErrorType.INVALID_REQUEST,
        "not_implemented",
        "This gateway implements chat completions and model listing only.",
    )
