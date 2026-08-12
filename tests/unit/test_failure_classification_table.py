"""AC-5 — the table, asserted as a table.

`fallback_eligible` and `retryable` are separate facts (A-095, ADR-0017), and the
gateway's whole fallback branch and evaluation's error-vs-fail distinction both
hang on this mapping. A misclassification is invisible at the point of the
mistake, so the table is exercised directly rather than incidentally.
"""

import httpx
import pytest

from prope.provider_access.domain import ErrorClass, Origin
from prope.provider_access.failures import (
    CLASSIFICATION,
    classify_status,
    classify_transport,
    prope_error,
)

CONTENT_POLICY_BODY = {
    "error": {
        "message": "the request was rejected as a result of our safety system",
        "type": "invalid_request_error",
        "code": "content_policy_violation",
    }
}

BAD_PARAMETER_BODY = {
    "error": {
        "message": "Unsupported value: temperature does not support 2.5",
        "type": "invalid_request_error",
        "code": "unsupported_value",
    }
}

UNKNOWN_MODEL_BODY = {
    "error": {"message": "The model does not exist", "type": "invalid_request_error", "code": "model_not_found"}
}


@pytest.mark.parametrize(
    ("status", "body", "expected", "fallback_eligible", "retryable"),
    [
        (429, None, ErrorClass.RATE_LIMITED, True, True),
        (500, None, ErrorClass.UPSTREAM_UNAVAILABLE, True, True),
        (503, None, ErrorClass.UPSTREAM_UNAVAILABLE, True, True),
        (401, None, ErrorClass.CREDENTIAL_REJECTED, True, False),
        (403, None, ErrorClass.CREDENTIAL_REJECTED, True, False),
        (404, None, ErrorClass.MODEL_UNAVAILABLE, True, False),
        (400, UNKNOWN_MODEL_BODY, ErrorClass.MODEL_UNAVAILABLE, True, False),
        (400, CONTENT_POLICY_BODY, ErrorClass.CONTENT_POLICY, False, False),
        (400, BAD_PARAMETER_BODY, ErrorClass.INVALID_REQUEST, False, False),
        (422, None, ErrorClass.INVALID_REQUEST, False, False),
    ],
)
def test_every_provider_condition_maps_to_its_own_class_and_two_separate_facts(
    status, body, expected, fallback_eligible, retryable
) -> None:
    error = classify_status(status, body)

    assert error.error_class is expected
    assert error.origin is Origin.PROVIDER
    assert error.fallback_eligible is fallback_eligible
    assert error.retryable is retryable
    assert error.upstream_status == status


def test_the_three_named_asymmetries_hold() -> None:
    """AC-5's own sentence: 401 is fallback-eligible and not retryable, 429 is
    both, and the content-policy refusal and the bad parameter are neither."""
    unauthorised = classify_status(401, None)
    limited = classify_status(429, None)
    refused = classify_status(400, CONTENT_POLICY_BODY)
    parameter = classify_status(400, BAD_PARAMETER_BODY)

    assert (unauthorised.fallback_eligible, unauthorised.retryable) == (True, False)
    assert (limited.fallback_eligible, limited.retryable) == (True, True)
    assert (refused.fallback_eligible, refused.retryable) == (False, False)
    assert (parameter.fallback_eligible, parameter.retryable) == (False, False)


def test_a_content_policy_refusal_is_never_covered_by_a_fallback_answer() -> None:
    """Serving a canned answer in place of a safety refusal is the one
    misclassification with a consequence outside the product."""
    assert classify_status(400, CONTENT_POLICY_BODY).fallback_eligible is False
    assert classify_status(200, CONTENT_POLICY_BODY) is not None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ConnectError("refused"), ErrorClass.UPSTREAM_UNAVAILABLE),
        (httpx.ReadTimeout("slow"), ErrorClass.UPSTREAM_TIMEOUT),
        (httpx.ConnectTimeout("slow"), ErrorClass.UPSTREAM_TIMEOUT),
        (TimeoutError(), ErrorClass.UPSTREAM_TIMEOUT),
    ],
)
def test_transport_conditions_are_classified_without_a_status(error, expected) -> None:
    classified = classify_transport(error)

    assert classified.error_class is expected
    assert classified.upstream_status is None
    assert classified.origin is Origin.PROVIDER


@pytest.mark.parametrize(
    "error_class",
    [ErrorClass.BLOCKED_ADDRESS, ErrorClass.KEY_UNAVAILABLE, ErrorClass.CONFIGURATION_UNUSABLE],
)
def test_prope_origin_failures_are_never_blamed_on_the_provider(error_class) -> None:
    """`origin` exists so a limit Prope set is never read as a provider outage."""
    error = prope_error(error_class, "refused here")

    assert error.origin is Origin.PROPE
    assert error.fallback_eligible is False


def test_an_admission_refusal_is_prope_origin_and_still_fallback_eligible() -> None:
    """The one Prope-origin class the gateway may cover, because the caller did
    nothing wrong and the answer would have come from a working provider."""
    error = prope_error(ErrorClass.ADMISSION_REFUSED, "at capacity")

    assert error.origin is Origin.PROPE
    assert (error.fallback_eligible, error.retryable) == (True, True)


def test_the_table_is_total_over_the_vocabulary() -> None:
    """A class with no row would classify as a KeyError at the seam that decides
    whether a customer sees a canned answer."""
    assert set(CLASSIFICATION) == set(ErrorClass)
    for error_class, facts in CLASSIFICATION.items():
        assert facts.error_class is error_class


def test_no_classified_error_carries_the_provider_s_own_message(monkeypatch) -> None:
    """T-026 — a provider that echoes the request back inside its error message
    is the ordinary way a prompt body reaches a log file. The allow-list is
    status, provider error code and error type, and nothing else crosses."""
    echoing = {
        "error": {
            "message": "could not process request: {'messages': [{'content': 'SECRET PROMPT'}]}",
            "type": "invalid_request_error",
            "code": "bad_request",
        }
    }

    error = classify_status(400, echoing)

    assert "SECRET PROMPT" not in error.message
    assert "SECRET PROMPT" not in repr(error)
    assert error.provider_code == "bad_request"
    assert error.provider_type == "invalid_request_error"
