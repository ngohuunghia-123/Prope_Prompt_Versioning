"""INT-022 — `POST /v1/chat/completions` and `GET /v1/models`, and nothing else."""

import time
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.background import BackgroundTask

from prope.access_control.seams import AuthenticatedKey
from prope.call_ledger.domain import Outcome, Source
from prope.gateway.admission import AdmissionRefused, admit
from prope.gateway.composition import (
    CallerSystemMessage,
    OversizeRequest,
    compose,
)
from prope.gateway.domain import (
    DONE,
    STREAM_HEADERS,
    ModelReference,
    ModelReferenceConflict,
    ModelReferenceInvalid,
    ServedIdentity,
    Stage,
    added_latency_ms,
    elapsed_ms,
    parse_model_reference,
    pinned_at,
    sse,
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
    route_advanced_total,
    route_attempt_total,
    route_exhausted_total,
    route_served_entry_total,
    upstream_error_total,
    usage_missing_total,
)
from prope.gateway.observe import forward
from prope.gateway.records import CallFacts, caller_request_body, new_call_id, record_call, serialise
from prope.gateway.resolution import (
    authenticate,
    is_workspace_namespace,
    released_listings,
    resolve_binding,
)
from prope.gateway.schemas import ChatCompletionRequest
from prope.gateway.templating import MissingVariable, UnfilledPlaceholder, render
from prope.prompt_registry.domain import RevisionBinding
from prope.provider_access.domain import DispatchError, DispatchResult, ErrorClass, Priority, Usage
from prope.provider_access.failures import CLASSIFICATION, prope_error
from prope.provider_access.normalise import read_usage
from prope.provider_access.seams import dispatch

log = structlog.get_logger(__name__)

router = APIRouter()

__all__ = ["DEADLINE_MS", "IMPLEMENTED_PATHS", "MIN_ATTEMPT_MS", "router"]

#: The budget for the WHOLE request, not for one attempt (ADR-0069). Each rung of
#: a route is handed what is left of it, so five rungs and one rung have the same
#: worst case — which is ADR-0013's "a retry doubles the worst case" answered on
#: its own terms rather than waived.
DEADLINE_MS = 60_000

#: The floor under a SUCCESSIVE attempt. Below it an attempt is theatre: the
#: provider cannot answer in the time left, the caller waits anyway, and the error
#: they finally see is a timeout that says nothing about why the route failed. The
#: walk stops instead and reports the last real failure.
MIN_ATTEMPT_MS = 5_000

CHAT_COMPLETIONS_PATH = "/chat/completions"

MODELS_PATH = "/models"

IMPLEMENTED_PATHS = frozenset({CHAT_COMPLETIONS_PATH, MODELS_PATH})

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


@dataclass(frozen=True, slots=True)
class _Served:
    """The rung that answered, and the first stream item already pulled from it.

    ``first`` exists because a streaming dispatch is lazy: the loop has to pull
    one item to learn whether the call failed before any byte, and having pulled
    it, it must hand it on rather than drop it.
    """

    index: int
    result: DispatchResult
    first: Any

    @property
    def entry(self) -> int:
        """1-based, because a route's rungs are ``priority`` and priority starts at 1."""
        return self.index + 1


#: The seven classes that advance, DERIVED from ADR-0017's closed table rather
#: than written out beside it. A class added to ``CLASSIFICATION`` is classified
#: here on the same day, which is the property a hand-copied set does not have.
#:
#: ``fallback_eligible`` already means *this failure is about the provider, not
#: about the request*, and that is precisely the question *should somebody else
#: try it* asks. ``content_policy`` and ``invalid_request`` are False on both
#: counts: the first would make Prope a machine for finding the provider that
#: will say the thing, and the second will be invalid everywhere.
ADVANCING: frozenset[ErrorClass] = frozenset(
    error_class for error_class, facts in CLASSIFICATION.items() if facts.fallback_eligible
)

#: Two prope-origin classes that are NOT fallback-eligible and still advance.
#:
#: **They are a separate set because two different questions have been answered
#: by one flag until now.** `CONFIGURATION_UNUSABLE` is raised when a rung's
#: configuration is missing, DISABLED, or unverified — and "an admin disabled
#: provider A this morning" is the single most likely reason a rung is unusable
#: and the exact case a combo exists for. Not advancing would mean a Settings
#: toggle takes production down while rung two sits healthy.
#:
#: It must nevertheless stay out of `ADVANCING`, because `fallback_eligible`
#: still decides `_pre_first_byte`, and ADR-0013 is right that a Prope-side
#: misconfiguration must not be papered over with canned text. So a route whose
#: every rung is disabled returns the 500 it returns today — never a fallback.
#:
#: `BLOCKED_ADDRESS` joins for the same reason: a fact about one base URL.
#: `KEY_UNAVAILABLE` deliberately does NOT — no key-encryption key in this
#: process means every rung fails identically, so advancing only burns budget.
ADVANCING_CONFIGURATION: frozenset[ErrorClass] = frozenset(
    {ErrorClass.CONFIGURATION_UNUSABLE, ErrorClass.BLOCKED_ADDRESS}
)


def _advances(error: DispatchError) -> bool:
    """Whether another rung could plausibly answer what this one refused."""
    return error.error_class in ADVANCING or error.error_class in ADVANCING_CONFIGURATION


async def _first_byte(result: DispatchResult) -> tuple[DispatchResult | DispatchError, Any]:
    """Pull one stream item so a pre-first-byte failure reaches the route loop.

    Returns ``(error, None)`` or ``(result, first_item_or_None)``.

    ``aclose()`` on the failure path is not tidiness: the abandoned relay holds a
    slot in provider-access's per-configuration admission semaphore, and the next
    rung is about to ask a different pool for one of its own. Leaking here would
    leak under exactly the conditions failover fires — which is to say, when the
    system is already having a bad day.
    """
    upstream = result.stream
    if upstream is None:
        return prope_error(
            ErrorClass.CONTRACT_VIOLATION, "a streaming dispatch produced no stream"
        ), None
    try:
        first = await anext(upstream)
    except StopAsyncIteration:
        return result, None
    if isinstance(first, DispatchError):
        await upstream.aclose()
        return first, None
    return result, first


def _identity(
    reference: ModelReference,
    binding: RevisionBinding,
    call_id: str,
    *,
    fallback: bool,
    entry: int | None = None,
    attempts: int = 1,
) -> ServedIdentity:
    """The response's own account of what served it.

    ``upstream_model`` is read off the rung that answered when there was one, and
    off the binding otherwise. On an unrouted revision the two are the same value;
    on a routed one, reading the binding would name the primary whatever replied.
    """
    served = binding.route[entry - 1] if binding.routed and entry is not None else None
    return ServedIdentity(
        model_name=reference.raw,
        version_id=binding.version_id,
        revision_number=binding.revision_number,
        pinned=reference.pinned,
        fallback=fallback,
        upstream_model=served.upstream_model if served else binding.upstream_model,
        call_id=call_id,
        route_combo_id=binding.route_combo_id,
        route_entry=entry if binding.routed else None,
        route_attempts=attempts,
    )


async def _forwards(
    sessionmaker: async_sessionmaker[AsyncSession], key: AuthenticatedKey, model: str
) -> bool:
    """ADR-0062's entry rule. **Only ever called on an observe-enabled key.**

    Which is what makes AC-17 — *an observe-disabled key is unaffected on every
    path* — true by construction rather than by care: the namespace read behind
    the second branch is never reached for a key with no ``observe_namespace``,
    so no integration that existed before ADR-0059 gained a query.
    """
    try:
        reference = parse_model_reference(model)
    except ModelReferenceInvalid:
        return True
    return not await is_workspace_namespace(sessionmaker, key, reference.name.namespace)


def _observed_facts(
    payload: ChatCompletionRequest, key: AuthenticatedKey, call_id: str, arrived: datetime
) -> CallFacts:
    """The record a forwarded call leaves. ADR-0060's fourth ``source``.

    Five of its columns are NULL by contract rather than by omission —
    ``prompt_id``, ``version_id``, ``revision_number``, ``run_id``, ``case_id`` —
    and ``ck_call_record_observed_calls_name_no_revision`` is where that is
    enforced. ``pinned`` and ``fallback`` are false for the same reason: both are
    properties of a revision, and there is none.

    **``request_body`` is deliberately absent.** The caller's messages are stored
    in ``observation.observation``, which has a reader, a redact route and a
    person who can act on it. Writing them a second time into ``ledger.call_body``
    — which ADR-0018 gives no reader and OQ-148 has not yet given a retention
    rule — would put a customer's production prompt in two places and let only
    one of them be removed. The response body is kept, because that is the
    provider's answer and not the customer's prompt.
    """
    return CallFacts(
        call_id=call_id,
        workspace_id=key.workspace_id,
        consumer_key_id=key.key_id,
        created_at=arrived,
        outcome=Outcome.OK,
        source=Source.OBSERVED,
        model_name=payload.model,
        streaming=payload.stream,
        conversation_id=payload.conversation_id(),
        parent_call_id=payload.parent_call_id(),
        provider_config_id=key.observe_provider_config_id,
        upstream_model=payload.model,
    )


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


def _completion(identity: ServedIdentity, created: int, content: str) -> dict[str, Any]:
    return {
        "id": identity.completion_id(),
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


def _completion_chunk(identity: ServedIdentity, created: int, content: str) -> dict[str, Any]:
    return {
        "id": identity.completion_id(),
        "object": "chat.completion.chunk",
        "created": created,
        "model": identity.model_name,
        "choices": [
            {"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "prope": identity.body(),
    }


def _refuse(facts: CallFacts, error: GatewayError, started: float) -> GatewayError:
    facts.outcome = Outcome.CALLER_ERROR
    facts.added_latency_ms = elapsed_ms(started)
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

    # --- ADR-0059 / ADR-0062: forward, or serve? ------------------------------
    #
    # The entry rule is NAMESPACE-shaped and it is checked here, before
    # `resolve_binding`, because that is the only place it can be. `may_resolve`
    # runs first inside `resolve_binding` and refuses `NOT_PERMITTED`, so a rule
    # written after it would never be reached for the case it exists to catch —
    # which is precisely the defect ADR-0062 was written to fix in A-153.
    #
    # Two ways in, and both mean *Prope is holding nothing under this name*:
    #
    #  1. The model string does not parse as `namespace/name` at all. `gpt-4o` is
    #     the case that matters, because it is what every unmodified product in
    #     the world sends, and on the served path it dies at `parse_model_
    #     reference` before any of this.
    #  2. It parses, and the namespace is one this workspace does not use.
    #
    # A name INSIDE a workspace namespace never forwards, whatever it is. That is
    # A-156, and it is what keeps the forwarded path from becoming a registry
    # enumeration oracle: `support/anything` refuses identically whether the
    # prompt exists and the key cannot see it, or does not exist at all (A-116).
    # A-159 prices what remains — a leaked observe-enabled key learns which
    # namespaces exist, and nothing about which names do.
    if key.observes and await _forwards(sessionmaker, key, payload.model):
        return await forward(
            payload=payload,
            key=key,
            sessionmaker=sessionmaker,
            facts=_observed_facts(payload, key, call_id, arrived),
            started=started,
            arrived=arrived,
            deadline_ms=DEADLINE_MS,
        )

    # Two spellings of one pin, folded into one reference before anything reads
    # it. The `@` form is A-022's and predates the field; `prope.version` is the
    # form a typed SDK can send without assembling the model string, and it has
    # to be the SAME lookup rather than a second path — a version that resolves
    # differently depending on which way it was written would be the one thing a
    # pin exists to rule out.
    try:
        reference = pinned_at(parse_model_reference(payload.model), payload.version())
    except ModelReferenceInvalid as invalid:
        raise model_not_found(invalid.raw) from invalid
    except ModelReferenceConflict as conflict:
        # A 400, not a 404, and it leaks nothing: the caller is being told about
        # the two fields they themselves sent, and the answer is identical
        # whether the prompt exists, is invisible to this key, or was never
        # created. The registry is not consulted to produce it.
        raise GatewayError(
            400,
            ErrorType.INVALID_REQUEST,
            "version_conflict",
            f"The model `{payload.model}` already pins a revision and `prope.version` asks for "
            f"`{conflict.version}`. Send one or the other.",
            param="prope.version",
        ) from conflict

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
        # Read here rather than at the top of `_serve` because this is the first
        # point at which a record exists to carry them. A request refused before
        # this line — an unparseable model name, a key that does not resolve —
        # never builds a `CallFacts` at all, so it contributes no node to any
        # graph. That is correct rather than a gap: nothing was served.
        conversation_id=payload.conversation_id(),
        parent_call_id=payload.parent_call_id(),
        provider_config_id=binding.provider_config_id,
        upstream_model=binding.upstream_model,
        request_body=caller_request_body(caller_messages, variables),
    )

    identity = _identity(reference, binding, call_id, fallback=False)

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

    candidates = binding.candidates
    if not candidates:
        facts.outcome = Outcome.UPSTREAM_ERROR
        facts.error_class = "configuration_unusable"
        facts.added_latency_ms = elapsed_ms(started)
        raise GatewayError(
            500,
            ErrorType.API,
            "provider_configuration_unusable",
            "The released revision binds no provider configuration.",
            background=BackgroundTask(record_call, facts),
        )

    # --- ADR-0069: walk the route ---------------------------------------------
    #
    # One loop, and a revision that binds a single pair is its one-entry case.
    # Writing the unrouted path as a branch beside this would be writing the path
    # that carries almost all the traffic twice — and the copy that drifts is
    # always the one nobody exercises.
    served: _Served | None = None
    last_error: DispatchError | None = None
    attempts = 0

    for index, candidate in enumerate(candidates):
        # `DEADLINE_MS` is the budget for the WHOLE request, not for one attempt,
        # and this line is the whole of ADR-0013's "a retry doubles the worst
        # case" being answered rather than waived: five rungs and one rung have
        # the same worst case. The floor stops the last rung being an attempt
        # nobody can answer in time — a caller who waits out the budget to be
        # told `upstream_timeout` learns less than one told what actually failed.
        remaining = DEADLINE_MS - elapsed_ms(started)
        if index and remaining < MIN_ATTEMPT_MS:
            route_exhausted_total.labels(reason="budget_exhausted").inc()
            break

        attempts = index + 1
        # Re-stamped per attempt, so the record names the rung that ACTUALLY
        # served — or, on an exhausted route, the last one tried. `call_record`
        # stores both as values with no foreign key, so traceability holds here
        # with no ledger change at all.
        facts.provider_config_id = candidate.provider_config_id
        facts.upstream_model = candidate.upstream_model

        outcome = await dispatch(
            sessionmaker,
            workspace_id=key.workspace_id,
            provider_config_id=candidate.provider_config_id,
            upstream_model=candidate.upstream_model,
            parameters=binding.parameters,
            messages=composed,
            stream=payload.stream,
            deadline_ms=max(remaining, 1),
            priority=Priority.INTERACTIVE,
        )

        # A streaming dispatch hands back a LAZY relay: the upstream call has not
        # happened yet, and a pre-first-byte failure only becomes visible when the
        # first item is pulled. Pulling it HERE rather than inside `_stream` is
        # what puts the streaming failover boundary in exactly the same place as
        # the fallback boundary — which is ADR-0013's boundary, unmoved, now
        # governing two recoveries instead of one.
        first: Any = None
        if not isinstance(outcome, DispatchError) and payload.stream:
            outcome, first = await _first_byte(outcome)

        if not isinstance(outcome, DispatchError):
            served = _Served(index=index, result=outcome, first=first)
            route_attempt_total.labels(entry=str(index + 1), outcome="ok").inc()
            break

        last_error = outcome
        route_attempt_total.labels(
            entry=str(index + 1), outcome=outcome.error_class.value
        ).inc()

        if not _advances(outcome):
            route_exhausted_total.labels(reason="not_advancing").inc()
            break
        if index == len(candidates) - 1:
            route_exhausted_total.labels(reason="entries_exhausted").inc()
            break

        route_advanced_total.labels(error_class=outcome.error_class.value).inc()
        log.info(
            "gateway.route_advanced",
            call_id=facts.call_id,
            workspace_id=facts.workspace_id,
            version_id=facts.version_id,
            route_combo_id=binding.route_combo_id,
            from_entry=index + 1,
            to_entry=index + 2,
            error_class=outcome.error_class.value,
            remaining_ms=DEADLINE_MS - elapsed_ms(started),
        )

    if served is None:
        assert last_error is not None
        return _pre_first_byte(
            error=last_error,
            binding=binding,
            reference=reference,
            facts=facts,
            payload=payload,
            started=started,
            arrived=arrived,
            attempts=attempts,
        )

    # Built HERE and not before the compose block, because it carries which rung
    # answered and `ServedIdentity` is frozen. The refusal paths above use the
    # earlier one, which is correct for them: nothing was served.
    identity = _identity(
        reference,
        binding,
        call_id,
        fallback=False,
        entry=served.entry,
        attempts=attempts,
    )
    if binding.routed:
        route_served_entry_total.labels(entry=str(served.entry)).inc()

    if payload.stream:
        return await _stream(
            result=served.result,
            first=served.first,
            identity=identity,
            facts=facts,
            payload=payload,
            started=started,
        )

    return _non_streaming(result=served.result, identity=identity, facts=facts, started=started)


def _pre_first_byte(
    *,
    error: DispatchError,
    binding: RevisionBinding,
    reference: ModelReference,
    facts: CallFacts,
    payload: ChatCompletionRequest,
    started: float,
    arrived: datetime,
    attempts: int = 1,
) -> Any:
    """No rung answered. The canned fallback is the LAST resort, after every one.

    **The error reported is the LAST rung's, not the first's.** The caller has to
    be told what the last thing Prope tried did — and ``retry-after`` on a 429 is
    only meaningful from the final attempt.

    On a routed revision this also means the fallback's meaning has grown: it now
    says *every provider on this route failed*, not *the provider failed*. That
    is the sentence ``GatewayFallbackRateHigh`` now alerts on.
    """
    upstream_error_total.labels(stage=Stage.PRE_FIRST_BYTE.value).inc()
    facts.error_class = error.error_class.value
    facts.upstream_duration_ms = 0

    if not (error.fallback_eligible and binding.fallback_answer):
        facts.outcome = Outcome.UPSTREAM_ERROR
        facts.added_latency_ms = elapsed_ms(started)
        translated = translate_dispatch_error(error)
        facts.response_body = serialise(
            error_payload(
                translated.error_type, translated.code, translated.message, translated.param
            )
        )
        translated.background = BackgroundTask(record_call, facts)
        raise translated

    fallback_total.labels(reason=_fallback_reason(error)).inc()
    # `entry` names the rung whose failure reached for the fallback — the last one
    # tried — so a fallback on a routed revision still says which provider was
    # being asked when Prope gave up.
    identity = _identity(
        reference,
        binding,
        facts.call_id,
        fallback=True,
        entry=attempts if binding.routed else None,
        attempts=attempts,
    )
    created = int(arrived.timestamp())

    facts.outcome = Outcome.FALLBACK
    facts.fallback = True
    facts.input_tokens = None
    facts.output_tokens = None
    facts.added_latency_ms = elapsed_ms(started)
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
        body = _completion(identity, created, binding.fallback_answer)
        return JSONResponse(
            status_code=200,
            content=body,
            headers=identity.headers(),
            background=BackgroundTask(record_call, facts),
        )

    async def stream() -> AsyncIterator[str]:
        yield sse(_completion_chunk(identity, created, binding.fallback_answer))
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
    facts.added_latency_ms = added_latency_ms(started, result.upstream_duration_ms)
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
    first: Any,
    identity: ServedIdentity,
    facts: CallFacts,
    payload: ChatCompletionRequest,
    started: float,
) -> Any:
    """Relay a stream whose first item has already been pulled.

    **The ``anext`` and the pre-first-byte branch used to live here and have moved
    up into the route loop** (ADR-0069). They had to: a pre-first-byte failure is
    the case a route recovers from, and a function that only runs once a rung has
    been chosen cannot choose another. What is left is relay, which is all this
    was ever named for.
    """
    upstream = result.stream
    if upstream is None:
        raise GatewayError(
            500,
            ErrorType.API,
            "internal_error",
            "The server had an error while processing your request.",
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
            # On **every** chunk, not just the first: a client that reads the id
            # off the last chunk it happened to keep must not get the provider's.
            # `prope` and `model` stay first-chunk-only, which is what they have
            # always been and what OpenAI's own streams do with `model`.
            body["id"] = identity.completion_id()
            if not stamped:
                body["prope"] = identity.body()
                body["model"] = identity.model_name
                stamped = True
            yield sse(body)
            chunk_relay_seconds.observe(time.perf_counter() - chunk_started)
            pending = await _next(upstream)

        if terminal is not None:
            upstream_error_total.labels(stage=Stage.MID_STREAM.value).inc()
            translated = translate_dispatch_error(terminal)
            facts.outcome = Outcome.TRUNCATED
            facts.error_class = terminal.error_class.value
            yield sse(
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
        facts.added_latency_ms = added_latency_ms(started, result.upstream_duration_ms)
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
