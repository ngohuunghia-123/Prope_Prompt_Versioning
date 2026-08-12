"""A-090 / A-030 — one live probe, one attempt, and no usage object means no admission."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import httpx

from prope.provider_access import upstream
from prope.provider_access.addresses import BlockedAddress, validate_base_url
from prope.provider_access.domain import CatalogueEntry, CatalogueSource, VerificationOutcome
from prope.provider_access.normalise import read_usage
from prope.provider_access.observability import verification_total

__all__ = [
    "PROBE_MESSAGES",
    "PROBE_TIMEOUT_SECONDS",
    "REASON_BLOCKED_ADDRESS",
    "REASON_CREDENTIAL_REJECTED",
    "REASON_NO_MODEL",
    "REASON_UNREACHABLE",
    "REASON_UPSTREAM_REFUSED",
    "REASON_USAGE_NOT_REPORTED",
    "Probe",
    "discover_models",
    "verify",
]

PROBE_TIMEOUT_SECONDS = 10.0

PROBE_MESSAGES = ({"role": "user", "content": "ping"},)

PROBE_PARAMETERS = {"max_tokens": 1, "temperature": 0}

REASON_BLOCKED_ADDRESS = "blocked_address"
REASON_UNREACHABLE = "unreachable"
REASON_CREDENTIAL_REJECTED = "credential_rejected"
REASON_NO_MODEL = "no_model"
REASON_UPSTREAM_REFUSED = "upstream_refused"
REASON_USAGE_NOT_REPORTED = "usage_not_reported"


@dataclass(frozen=True, slots=True)
class Probe:
    outcome: VerificationOutcome
    models: tuple[CatalogueEntry, ...]


def _entries(body: object) -> tuple[CatalogueEntry, ...]:
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return ()
    entries = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        entries.append(
            CatalogueEntry(
                model_id=model_id,
                display_name=item.get("display_name") if isinstance(
                    item.get("display_name"), str
                ) else None,
                supports_streaming=True,
                available=True,
                source=CatalogueSource.DISCOVERED,
            )
        )
    return tuple(entries)


def _failed(reason: str, detail: str, checked_at: datetime) -> Probe:
    verification_total.labels(result="fail", reason=reason).inc()
    return Probe(
        outcome=VerificationOutcome(
            passed=False, reason=reason, detail=detail, checked_at=checked_at
        ),
        models=(),
    )


async def discover_models(base_url: str, secret: str) -> Sequence[CatalogueEntry]:
    endpoint = await validate_base_url(base_url)
    call = await upstream.call_json(
        endpoint,
        secret,
        path=upstream.MODELS_PATH,
        method="GET",
        timeout_seconds=PROBE_TIMEOUT_SECONDS,
    )
    if call.status >= 400:
        return ()
    return _entries(call.body)


async def verify(base_url: str, secret: str, *, checked_at: datetime) -> Probe:
    try:
        endpoint = await validate_base_url(base_url)
    except BlockedAddress as blocked:
        return _failed(REASON_BLOCKED_ADDRESS, str(blocked), checked_at)

    try:
        listing = await upstream.call_json(
            endpoint,
            secret,
            path=upstream.MODELS_PATH,
            method="GET",
            timeout_seconds=PROBE_TIMEOUT_SECONDS,
        )
    except (httpx.HTTPError, TimeoutError) as error:
        return _failed(
            REASON_UNREACHABLE,
            f"the model list did not complete: {type(error).__name__}",
            checked_at,
        )

    if listing.status in (401, 403):
        return _failed(
            REASON_CREDENTIAL_REJECTED,
            "the provider refused the supplied credential",
            checked_at,
        )

    models = _entries(listing.body)
    if not models:
        return _failed(
            REASON_NO_MODEL,
            "the provider's model list is empty or unreadable, so no completion can be probed",
            checked_at,
        )

    payload = upstream.compose_request(
        upstream_model=models[0].model_id,
        parameters=PROBE_PARAMETERS,
        messages=PROBE_MESSAGES,
        stream=False,
    )
    try:
        completion = await upstream.call_json(
            endpoint,
            secret,
            path=upstream.CHAT_COMPLETIONS_PATH,
            payload=payload,
            timeout_seconds=PROBE_TIMEOUT_SECONDS,
        )
    except (httpx.HTTPError, TimeoutError) as error:
        return _failed(
            REASON_UNREACHABLE,
            f"the probe completion did not complete: {type(error).__name__}",
            checked_at,
        )

    if completion.status in (401, 403):
        return _failed(
            REASON_CREDENTIAL_REJECTED,
            "the provider refused the supplied credential",
            checked_at,
        )
    if completion.status >= 400:
        return _failed(
            REASON_UPSTREAM_REFUSED,
            f"the provider answered {completion.status} to the probe completion",
            checked_at,
        )

    if read_usage(completion.body) is None:
        return _failed(
            REASON_USAGE_NOT_REPORTED,
            "the probe completion carried no usage object, and A-030 admits only providers "
            "that report usage",
            checked_at,
        )

    verification_total.labels(result="pass", reason="none").inc()
    return Probe(
        outcome=VerificationOutcome(
            passed=True, reason=None, detail=None, checked_at=checked_at
        ),
        models=models,
    )
