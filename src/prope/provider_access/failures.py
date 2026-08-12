"""ADR-0017 / A-095 — one closed table from an upstream condition to four facts."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from prope.provider_access.domain import DispatchError, ErrorClass, Origin, Usage
from prope.provider_access.observability import error_total

__all__ = [
    "CLASSIFICATION",
    "Facts",
    "classify_status",
    "classify_transport",
    "prope_error",
    "record",
]


@dataclass(frozen=True, slots=True)
class Facts:
    error_class: ErrorClass
    origin: Origin
    fallback_eligible: bool
    retryable: bool


CLASSIFICATION: dict[ErrorClass, Facts] = {
    ErrorClass.RATE_LIMITED: Facts(ErrorClass.RATE_LIMITED, Origin.PROVIDER, True, True),
    ErrorClass.CREDENTIAL_REJECTED: Facts(
        ErrorClass.CREDENTIAL_REJECTED, Origin.PROVIDER, True, False
    ),
    ErrorClass.MODEL_UNAVAILABLE: Facts(
        ErrorClass.MODEL_UNAVAILABLE, Origin.PROVIDER, True, False
    ),
    ErrorClass.INVALID_REQUEST: Facts(ErrorClass.INVALID_REQUEST, Origin.PROVIDER, False, False),
    ErrorClass.CONTENT_POLICY: Facts(ErrorClass.CONTENT_POLICY, Origin.PROVIDER, False, False),
    ErrorClass.UPSTREAM_UNAVAILABLE: Facts(
        ErrorClass.UPSTREAM_UNAVAILABLE, Origin.PROVIDER, True, True
    ),
    ErrorClass.UPSTREAM_TIMEOUT: Facts(ErrorClass.UPSTREAM_TIMEOUT, Origin.PROVIDER, True, True),
    ErrorClass.CONTRACT_VIOLATION: Facts(
        ErrorClass.CONTRACT_VIOLATION, Origin.PROVIDER, True, False
    ),
    ErrorClass.BLOCKED_ADDRESS: Facts(ErrorClass.BLOCKED_ADDRESS, Origin.PROPE, False, False),
    ErrorClass.KEY_UNAVAILABLE: Facts(ErrorClass.KEY_UNAVAILABLE, Origin.PROPE, False, False),
    ErrorClass.CONFIGURATION_UNUSABLE: Facts(
        ErrorClass.CONFIGURATION_UNUSABLE, Origin.PROPE, False, False
    ),
    ErrorClass.ADMISSION_REFUSED: Facts(ErrorClass.ADMISSION_REFUSED, Origin.PROPE, True, True),
}

CONTENT_POLICY_MARKERS = frozenset(
    {"content_policy_violation", "content_filter", "content_policy"}
)

MODEL_UNAVAILABLE_MARKERS = frozenset(
    {"model_not_found", "model_not_available", "unknown_model", "does_not_exist"}
)


def _provider_fields(body: Mapping[str, Any] | None) -> tuple[str | None, str | None, str]:
    if not isinstance(body, Mapping):
        return None, None, ""
    error = body.get("error")
    if not isinstance(error, Mapping):
        return None, None, ""
    code = error.get("code")
    kind = error.get("type")
    message = error.get("message")
    haystack = " ".join(
        str(value) for value in (code, kind, message) if isinstance(value, str)
    ).lower()
    return (
        code if isinstance(code, str) else None,
        kind if isinstance(kind, str) else None,
        haystack,
    )


def _status_class(status: int, haystack: str) -> ErrorClass:
    if any(marker in haystack for marker in CONTENT_POLICY_MARKERS):
        return ErrorClass.CONTENT_POLICY
    if status in (401, 403):
        return ErrorClass.CREDENTIAL_REJECTED
    if status == 429:
        return ErrorClass.RATE_LIMITED
    if status == 404:
        return ErrorClass.MODEL_UNAVAILABLE
    if status == 408:
        return ErrorClass.UPSTREAM_TIMEOUT
    if status == 400 and any(marker in haystack for marker in MODEL_UNAVAILABLE_MARKERS):
        return ErrorClass.MODEL_UNAVAILABLE
    if 400 <= status < 500:
        return ErrorClass.INVALID_REQUEST
    return ErrorClass.UPSTREAM_UNAVAILABLE


def classify_status(
    status: int, body: Mapping[str, Any] | None, *, usage: Usage | None = None
) -> DispatchError:
    code, kind, haystack = _provider_fields(body)
    facts = CLASSIFICATION[_status_class(status, haystack)]
    return record(
        DispatchError(
            error_class=facts.error_class,
            origin=facts.origin,
            fallback_eligible=facts.fallback_eligible,
            retryable=facts.retryable,
            message=f"the provider answered {status}",
            upstream_status=status,
            provider_code=code,
            provider_type=kind,
            usage=usage,
        )
    )


def classify_transport(error: Exception, *, usage: Usage | None = None) -> DispatchError:
    timed_out = isinstance(error, httpx.TimeoutException | TimeoutError)
    facts = CLASSIFICATION[
        ErrorClass.UPSTREAM_TIMEOUT if timed_out else ErrorClass.UPSTREAM_UNAVAILABLE
    ]
    return record(
        DispatchError(
            error_class=facts.error_class,
            origin=facts.origin,
            fallback_eligible=facts.fallback_eligible,
            retryable=facts.retryable,
            message=f"the upstream call did not complete: {type(error).__name__}",
            usage=usage,
        )
    )


def prope_error(
    error_class: ErrorClass, message: str, *, usage: Usage | None = None
) -> DispatchError:
    facts = CLASSIFICATION[error_class]
    return record(
        DispatchError(
            error_class=facts.error_class,
            origin=facts.origin,
            fallback_eligible=facts.fallback_eligible,
            retryable=facts.retryable,
            message=message,
            usage=usage,
        )
    )


def record(error: DispatchError) -> DispatchError:
    error_total.labels(
        **{
            "class": error.error_class.value,
            "origin": error.origin.value,
            "fallback_eligible": str(error.fallback_eligible).lower(),
            "retryable": str(error.retryable).lower(),
        }
    ).inc()
    return error
