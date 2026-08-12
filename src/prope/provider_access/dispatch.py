"""INT-015 — one attempt, one shape, four separate facts on every failure."""

import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.provider_access import credentials, upstream
from prope.provider_access.addresses import BlockedAddress, validate_base_url
from prope.provider_access.admission import Shed, admit
from prope.provider_access.crypto import KeyUnavailable
from prope.provider_access.domain import (
    ConfigStatus,
    DispatchError,
    DispatchResult,
    ErrorClass,
    Priority,
    ProviderConfig,
    Usage,
    VerificationStatus,
)
from prope.provider_access.failures import classify_status, classify_transport, prope_error
from prope.provider_access.normalise import normalise_chunk, normalise_response, read_usage
from prope.provider_access.observability import (
    credential_rejected_total,
    dispatch_duration_seconds,
    dispatch_overhead_seconds,
    dispatch_total,
    model_unavailable_total,
    upstream_duration_seconds,
    usage_missing_total,
)

log = structlog.get_logger(__name__)

__all__ = ["DEFAULT_DEADLINE_MS", "dispatch"]

DEFAULT_DEADLINE_MS = 60_000


async def dispatch(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace_id: str,
    provider_config_id: str,
    upstream_model: str,
    parameters: Mapping[str, Any],
    messages: Sequence[Mapping[str, Any]],
    stream: bool = False,
    deadline_ms: int = DEFAULT_DEADLINE_MS,
    priority: Priority = Priority.INTERACTIVE,
) -> DispatchResult | DispatchError:
    started = time.perf_counter()
    deadline_seconds = max(deadline_ms, 1) / 1000

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        try:
            prepared = await _prepare(db, provider_config_id, upstream_model)
        except _RefusedError as refusal:
            return _finish_error(refusal.error, priority, stream, started)

    config, secret = prepared

    try:
        endpoint = await validate_base_url(config.base_url)
    except BlockedAddress as blocked:
        return _finish_error(
            prope_error(ErrorClass.BLOCKED_ADDRESS, str(blocked)), priority, stream, started
        )

    payload = upstream.compose_request(
        upstream_model=upstream_model,
        parameters=parameters,
        messages=messages,
        stream=stream,
    )

    if stream:
        return _streaming(
            endpoint,
            secret,
            payload,
            config=config,
            upstream_model=upstream_model,
            priority=priority,
            deadline_seconds=deadline_seconds,
            started=started,
        )

    try:
        async with admit(
            provider_config_id,
            priority,
            config.concurrency_for(priority),
            deadline_seconds=deadline_seconds,
        ):
            return await _once(
                endpoint,
                secret,
                payload,
                config=config,
                upstream_model=upstream_model,
                priority=priority,
                deadline_seconds=deadline_seconds,
                started=started,
            )
    except Shed as shed:
        return _finish_error(
            prope_error(ErrorClass.ADMISSION_REFUSED, str(shed)), priority, False, started
        )


class _RefusedError(Exception):
    def __init__(self, error: DispatchError) -> None:
        super().__init__(error.message)
        self.error = error


async def _prepare(
    db: AsyncSession, provider_config_id: str, upstream_model: str
) -> tuple[ProviderConfig, str]:
    config = await credentials.load_config(db, provider_config_id)
    if config is None:
        raise _RefusedError(
            prope_error(
                ErrorClass.CONFIGURATION_UNUSABLE,
                "no such provider configuration in this workspace",
            )
        )
    if config.status is not ConfigStatus.ACTIVE:
        raise _RefusedError(
            prope_error(
                ErrorClass.CONFIGURATION_UNUSABLE,
                "the provider configuration is disabled",
            )
        )
    if config.verification_status is not VerificationStatus.PASSED:
        raise _RefusedError(
            prope_error(
                ErrorClass.CONFIGURATION_UNUSABLE,
                "the provider configuration has not passed verification",
            )
        )

    try:
        secret = await credentials.resolve_secret(db, provider_config_id)
    except KeyUnavailable as unavailable:
        raise _RefusedError(
            prope_error(ErrorClass.KEY_UNAVAILABLE, str(unavailable))
        ) from unavailable

    return config, secret


async def _once(
    endpoint: Any,
    secret: str,
    payload: Mapping[str, Any],
    *,
    config: ProviderConfig,
    upstream_model: str,
    priority: Priority,
    deadline_seconds: float,
    started: float,
) -> DispatchResult | DispatchError:
    upstream_started = time.perf_counter()
    try:
        call = await upstream.call_json(
            endpoint,
            secret,
            path=upstream.CHAT_COMPLETIONS_PATH,
            payload=payload,
            timeout_seconds=deadline_seconds,
        )
    except (httpx.HTTPError, TimeoutError) as error:
        return _finish_error(classify_transport(error), priority, False, started)

    upstream_seconds = time.perf_counter() - upstream_started
    upstream_duration_seconds.labels(
        provider_config_id=config.id, upstream_model=upstream_model
    ).observe(upstream_seconds)

    if call.status >= 400:
        error = classify_status(call.status, call.body)
        _count_provider_refusal(error, config.id, upstream_model)
        return _finish_error(error, priority, False, started)

    if call.body is None:
        return _finish_error(
            prope_error(
                ErrorClass.CONTRACT_VIOLATION,
                "the provider answered 200 with a body that is not a JSON object",
            ),
            priority,
            False,
            started,
        )

    response = normalise_response(call.body, model=upstream_model)
    usage = read_usage(response)
    if usage is None:
        usage_missing_total.inc()

    _observe(priority, False, "ok", started, upstream_seconds)
    _log(config, upstream_model, priority, streaming=False, usage=usage, error=None)
    return DispatchResult(
        response=response, usage=usage, upstream_duration_ms=upstream_seconds * 1000
    )


def _streaming(
    endpoint: Any,
    secret: str,
    payload: Mapping[str, Any],
    *,
    config: ProviderConfig,
    upstream_model: str,
    priority: Priority,
    deadline_seconds: float,
    started: float,
) -> DispatchResult:
    result = DispatchResult(response=None, usage=None)

    async def relay() -> AsyncIterator[Any]:
        upstream_started = time.perf_counter()
        terminal: DispatchError | None = None
        try:
            async with admit(
                config.id,
                priority,
                config.concurrency_for(priority),
                deadline_seconds=deadline_seconds,
            ):
                upstream_started = time.perf_counter()
                async for item in upstream.stream_completion(
                    endpoint, secret, payload=payload, timeout_seconds=deadline_seconds
                ):
                    if isinstance(item, upstream.UpstreamCall):
                        terminal = classify_status(item.status, item.body, usage=result.usage)
                        _count_provider_refusal(terminal, config.id, upstream_model)
                        break
                    chunk = normalise_chunk(item, model=upstream_model)
                    usage = read_usage(chunk)
                    if usage is not None:
                        result.usage = usage
                    yield chunk
        except Shed as shed:
            terminal = prope_error(ErrorClass.ADMISSION_REFUSED, str(shed), usage=result.usage)
        except (httpx.HTTPError, TimeoutError) as error:
            terminal = classify_transport(error, usage=result.usage)

        upstream_seconds = time.perf_counter() - upstream_started
        upstream_duration_seconds.labels(
            provider_config_id=config.id, upstream_model=upstream_model
        ).observe(upstream_seconds)
        result.upstream_duration_ms = upstream_seconds * 1000

        if terminal is not None:
            result.error = terminal
            _observe(priority, True, terminal.error_class.value, started, upstream_seconds)
            _log(config, upstream_model, priority, streaming=True, usage=result.usage, error=terminal)
            yield terminal
            return

        if result.usage is None:
            usage_missing_total.inc()
        _observe(priority, True, "ok", started, upstream_seconds)
        _log(config, upstream_model, priority, streaming=True, usage=result.usage, error=None)

    result.stream = relay()
    return result


def _count_provider_refusal(
    error: DispatchError, provider_config_id: str, upstream_model: str
) -> None:
    if error.error_class is ErrorClass.CREDENTIAL_REJECTED:
        credential_rejected_total.labels(provider_config_id=provider_config_id).inc()
    elif error.error_class is ErrorClass.MODEL_UNAVAILABLE:
        model_unavailable_total.labels(
            provider_config_id=provider_config_id, upstream_model=upstream_model
        ).inc()


def _observe(
    priority: Priority,
    streaming: bool,
    outcome: str,
    started: float,
    upstream_seconds: float,
) -> None:
    elapsed = time.perf_counter() - started
    label = str(streaming).lower()
    dispatch_duration_seconds.labels(
        priority=priority.value, streaming=label, outcome=outcome
    ).observe(elapsed)
    dispatch_overhead_seconds.labels(priority=priority.value, streaming=label).observe(
        max(0.0, elapsed - upstream_seconds)
    )
    dispatch_total.labels(priority=priority.value, outcome=outcome).inc()


def _finish_error(
    error: DispatchError, priority: Priority, streaming: bool, started: float
) -> DispatchError:
    _observe(priority, streaming, error.error_class.value, started, 0.0)
    log.warning(
        "provider_access.dispatch_failed",
        priority=priority.value,
        streaming=streaming,
        error_class=error.error_class.value,
        origin=error.origin.value,
        fallback_eligible=error.fallback_eligible,
        retryable=error.retryable,
        upstream_status=error.upstream_status,
        attempt=1,
    )
    return error


def _log(
    config: ProviderConfig,
    upstream_model: str,
    priority: Priority,
    *,
    streaming: bool,
    usage: Usage | None,
    error: DispatchError | None,
) -> None:
    log.info(
        "provider_access.dispatched",
        provider_config_id=config.id,
        adapter=config.adapter.value,
        upstream_model=upstream_model,
        priority=priority.value,
        streaming=streaming,
        error_class=error.error_class.value if error is not None else None,
        origin=error.origin.value if error is not None else None,
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        attempt=1,
    )
