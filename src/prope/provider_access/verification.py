"""A-090 / A-030 — one live probe, one attempt, and no usage object means no admission."""

import asyncio
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import structlog

from prope.provider_access import upstream
from prope.provider_access.addresses import BlockedAddress, ValidatedEndpoint, validate_base_url
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

log = structlog.get_logger(__name__)

PROBE_TIMEOUT_SECONDS = 10.0

PROBE_MESSAGES = ({"role": "user", "content": "ping"},)

#: `temperature` is deliberately absent: the probe's job is to elicit a
#: usage-bearing completion, and the reasoning-model families OpenAI, Gemini and
#: OpenRouter list first refuse the parameter outright — a 400 that says nothing
#: about whether the provider reports usage.
PROBE_PARAMETERS = {"max_tokens": 1}

#: A 400 on the capped probe is ambiguous between "this model is broken" and
#: "this request shape is refused" — and provider-routed variants of the
#: thinking kind 400 any tiny `max_tokens` because it sits below their default
#: reasoning budget. So each candidate gets a second shape: no token cap at
#: all, the provider applying its own default. Each rung is issued exactly
#: once (A-088); the ladder is shapes, not retries.
PROBE_PARAMETER_LADDER: tuple[Mapping[str, Any], ...] = (PROBE_PARAMETERS, {})

#: Server-side diagnostics for a refusal: the provider's own error words,
#: truncated. This is a log line, not the API surface — ADR-0053's catalogue
#: keeps display text, and the probe's `detail` stays a closed token.
REFUSAL_SNIPPET_CHARS = 300

#: How many discovered models the probe will consider at all. Real catalogues
#: open with models that cannot answer a probe — audio, image and embedding
#: entries, preview and routed variants, reasoning families that refuse the
#: request shape — and the probe is not in the business of auditing each one:
#: an erroring model is skipped, and the walk only needs ONE model that
#: completes and reports usage to admit the provider. Forty-eight covers the
#: broken front run of everything seen in practice without turning a
#: registration into a catalogue sweep.
PROBE_MODEL_CANDIDATE_CAP = 48

#: Candidates are probed in parallel waves of this size. Sequential walking
#: made the walk's depth the user's waiting time; waves make a refusal run
#: cost one round trip instead of one round trip per model. Each request is
#: still issued exactly once (A-088) — the concurrency is across candidates,
#: never retries of a failed call.
PROBE_PROBE_CONCURRENCY = 8

#: The wall-clock the completion waves may spend, checked between waves.
#: Refusals return in milliseconds, so the usual walk ends well inside this;
#: the budget exists so a catalogue full of hanging models costs a bounded
#: wait instead of stretching registration into minutes. The worst overshoot
#: is one wave, i.e. one `PROBE_TIMEOUT_SECONDS`.
PROBE_COMPLETION_BUDGET_SECONDS = 30.0

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


def _listed_price(entry: Mapping[str, Any], key: str) -> float | None:
    """A vendor's per-token listing price, on the ledger's per-1k unit.

    OpenRouter publishes ``pricing.prompt`` / ``pricing.completion`` as
    per-token strings (``"0.000000834"``). Values that are missing,
    unreadable, or the ``-1`` "priced on request" sentinel become None — a
    price nobody listed is not a price of zero.
    """
    pricing = entry.get("pricing")
    if not isinstance(pricing, Mapping):
        return None
    raw = pricing.get(key)
    if not isinstance(raw, (str, int, float)) or isinstance(raw, bool):
        return None
    try:
        per_token = float(raw)
    except (TypeError, ValueError):
        return None
    if per_token < 0:
        return None
    return per_token * 1000


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
                input_price_per_1k=_listed_price(item, "prompt"),
                output_price_per_1k=_listed_price(item, "completion"),
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


async def _list_catalogue(
    endpoint: ValidatedEndpoint, secret: str
) -> tuple[upstream.UpstreamCall, bool]:
    """The model listing, plain Bearer first.

    The Anthropic dialect is a fallback, not a default: `anthropic-version`
    makes OpenRouter serve its anthropic-compatible catalogue — ids like
    `anthropic/<slug>[1m]` that its own completions refuse — so the header
    may only be worn after the plain request is refused, and the dialect
    that won the listing is the one the completions must speak. Real
    `api.anthropic.com` refuses a Bearer-only `/models`, which is the case
    the second rung exists for.
    """
    listing = await upstream.call_json(
        endpoint,
        secret,
        path=upstream.MODELS_PATH,
        method="GET",
        timeout_seconds=PROBE_TIMEOUT_SECONDS,
    )
    if listing.status in (401, 403):
        headered = await upstream.call_json(
            endpoint,
            secret,
            path=upstream.MODELS_PATH,
            method="GET",
            timeout_seconds=PROBE_TIMEOUT_SECONDS,
            anthropic_dialect=True,
        )
        return headered, headered.status < 400
    return listing, False


async def discover_models(base_url: str, secret: str) -> Sequence[CatalogueEntry]:
    endpoint = await validate_base_url(base_url)
    call, _ = await _list_catalogue(endpoint, secret)
    if call.status >= 400:
        return ()
    return _entries(call.body)


@dataclass(frozen=True, slots=True)
class _CompletionAttempt:
    """One model's single completion request: a status, or a transport error."""

    model_id: str
    status: int | None
    body: Mapping[str, Any] | None
    error_type: str | None


async def _call_once(
    endpoint: ValidatedEndpoint,
    secret: str,
    model_id: str,
    parameters: Mapping[str, Any],
    *,
    anthropic_dialect: bool,
) -> _CompletionAttempt:
    payload = upstream.compose_request(
        upstream_model=model_id,
        parameters=parameters,
        messages=PROBE_MESSAGES,
        stream=False,
    )
    try:
        call = await upstream.call_json(
            endpoint,
            secret,
            path=upstream.CHAT_COMPLETIONS_PATH,
            payload=payload,
            timeout_seconds=PROBE_TIMEOUT_SECONDS,
            anthropic_dialect=anthropic_dialect,
        )
    except (httpx.HTTPError, TimeoutError) as error:
        return _CompletionAttempt(
            model_id=model_id, status=None, body=None, error_type=type(error).__name__
        )
    return _CompletionAttempt(model_id=model_id, status=call.status, body=call.body, error_type=None)


async def _attempt_completion(
    endpoint: ValidatedEndpoint,
    secret: str,
    model_id: str,
    *,
    anthropic_dialect: bool,
) -> _CompletionAttempt:
    """Runs the parameter ladder for one candidate. A 400 is the one answer a
    different request shape can plausibly cure, so it falls through to the
    next rung; every other outcome ends the attempt."""
    attempt = await _call_once(
        endpoint, secret, model_id, PROBE_PARAMETER_LADDER[0], anthropic_dialect=anthropic_dialect
    )
    for parameters in PROBE_PARAMETER_LADDER[1:]:
        if attempt.status != 400:
            return attempt
        attempt = await _call_once(
            endpoint, secret, model_id, parameters, anthropic_dialect=anthropic_dialect
        )
    return attempt


def _snippet(body: Mapping[str, Any] | None) -> str:
    if not isinstance(body, Mapping):
        return ""
    try:
        return json.dumps(body)[:REFUSAL_SNIPPET_CHARS]
    except (TypeError, ValueError):
        return ""


def _classify(attempt: _CompletionAttempt) -> tuple[str, str] | None:
    """The admission verdict for one model, or None when it answered well.

    A-030's usage requirement is per attempt here: a completion that comes
    back without a usage object is that model's failure to evidence the
    contract, not yet the provider's — the walk keeps looking for a model
    that can carry the evidence.
    """
    if attempt.status in (401, 403):
        return (
            REASON_CREDENTIAL_REJECTED,
            "the provider refused the supplied credential",
        )
    if attempt.status is None:
        return (
            REASON_UNREACHABLE,
            f"the probe completion for {attempt.model_id!r} did not complete: "
            f"{attempt.error_type}",
        )
    if attempt.status >= 400:
        return (
            REASON_UPSTREAM_REFUSED,
            f"the provider answered {attempt.status} to the probe completion "
            f"for {attempt.model_id!r}",
        )
    if read_usage(attempt.body) is None:
        return (
            REASON_USAGE_NOT_REPORTED,
            f"the probe completion for {attempt.model_id!r} carried no usage object, "
            "and A-030 admits only providers that report usage",
        )
    return None


async def verify(base_url: str, secret: str, *, checked_at: datetime) -> Probe:
    try:
        endpoint = await validate_base_url(base_url)
    except BlockedAddress as blocked:
        return _failed(REASON_BLOCKED_ADDRESS, str(blocked), checked_at)

    try:
        listing, dialect = await _list_catalogue(endpoint, secret)
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

    # A-090's one attempt is per dispatch, never a retry: every candidate below
    # is probed exactly once, in parallel waves, and a model that refuses —
    # 400, 5xx, transport error, no usage — is simply skipped. The provider is
    # admitted the moment any one model completes with a usage object; only a
    # credential refusal (which no model can answer for) or every candidate
    # failing ends in a refusal. The completions speak whichever auth dialect
    # won the listing, so the ids being completed are the ones the provider
    # itself advertised to this credential.
    candidates = [entry.model_id for entry in models[:PROBE_MODEL_CANDIDATE_CAP]]
    waves = (
        candidates[at : at + PROBE_PROBE_CONCURRENCY]
        for at in range(0, len(candidates), PROBE_PROBE_CONCURRENCY)
    )
    budget_deadline = time.monotonic() + PROBE_COMPLETION_BUDGET_SECONDS
    last_failure: tuple[str, str] | None = None
    for wave in waves:
        attempts = await asyncio.gather(
            *(
                _attempt_completion(endpoint, secret, model_id, anthropic_dialect=dialect)
                for model_id in wave
            )
        )
        for attempt in attempts:
            verdict = _classify(attempt)
            if verdict is None:
                verification_total.labels(result="pass", reason="none").inc()
                return Probe(
                    outcome=VerificationOutcome(
                        passed=True, reason=None, detail=None, checked_at=checked_at
                    ),
                    models=models,
                )
            if verdict[0] == REASON_CREDENTIAL_REJECTED:
                return _failed(verdict[0], verdict[1], checked_at)
            if verdict[0] == REASON_UPSTREAM_REFUSED:
                log.info(
                    "probe_completion_skipped",
                    base_url_host=endpoint.host,
                    model_id=attempt.model_id,
                    status=attempt.status,
                    body_snippet=_snippet(attempt.body),
                )
            last_failure = verdict
        if time.monotonic() >= budget_deadline:
            break

    return _failed(
        *(last_failure or (REASON_NO_MODEL, "no candidate model could be probed")),
        checked_at,
    )
