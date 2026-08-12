"""AC-5 — with no fallback answer set, the provider's error passes through translated.

A-035 makes the fallback OPTIONAL, and this is the case it leaves uncovered: *"a
revision with no fallback has no cover"*. What the consumer gets is the upstream
failure, in the OpenAI error shape their SDK already raises for, and **no canned
content of any kind** — there is nothing to serve, and inventing something would
be putting text in front of a real user that no human wrote and no reviewer
approved.

The translation is a shape change and not a judgement: provider-access has
already classified the failure (ADR-0017), and this module maps its `ErrorClass`
onto an OpenAI status and code so a client SDK raises its normal exception type.
"""

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.domain import Outcome
from tests.gateway import (
    MODEL,
    VERSION_ID,
    authorization,
    enqueued_records,
    gateway_api,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _fallbacks() -> float:
    total = 0.0
    for reason in ("upstream_5xx", "timeout", "rate_limited", "credential_rejected"):
        total += REGISTRY.get_sample_value("prope_gateway_fallback_total", {"reason": reason}) or 0.0
    return total


def _request(**extra) -> dict:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hi"}], **extra}


def _fails(status: int, payload: dict | None = None):  # noqa: ANN202
    return lambda _: httpx.Response(status, json=payload or {"error": {"message": "unwell"}})


async def test_the_upstream_error_passes_through_in_the_openai_shape(
    api, migrate_engine, monkeypatch
) -> None:
    await seed_released_world(migrate_engine, fallback_answer=None)

    with stub_upstream(monkeypatch, _fails(500)):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 502
    payload = response.json()
    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"message", "type", "param", "code"}
    assert payload["error"]["type"] == "api_error"


async def test_no_canned_content_is_returned(api, migrate_engine, monkeypatch) -> None:
    """The clause the acceptance criterion ends on. There is no `choices` array,
    no assistant message, and no 200 — a consumer must be able to tell *the model
    did not answer* from *the model answered*."""
    await seed_released_world(migrate_engine, fallback_answer=None)
    before = _fallbacks()

    with stub_upstream(monkeypatch, _fails(500)):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert "choices" not in response.json()
    assert response.status_code != 200
    assert "x-prope-fallback" not in response.headers
    assert _fallbacks() == before, "a fallback was counted for a revision that has none"


@pytest.mark.parametrize(
    ("upstream_status", "expected_status", "code"),
    [
        (500, 502, "upstream_unavailable"),
        (503, 502, "upstream_unavailable"),
        (429, 429, "rate_limit_exceeded"),
        (401, 502, "upstream_credential_rejected"),
        (404, 502, "upstream_model_unavailable"),
    ],
)
async def test_each_failure_class_is_translated_to_its_own_openai_status(
    api, migrate_engine, monkeypatch, upstream_status: int, expected_status: int, code: str
) -> None:
    """The translation table, driven end to end.

    Two of these are worth stating out loud. A provider's `401` becomes a `502`
    and NOT a `401`: the credential Prope holds was rejected, and answering `401`
    would tell a consuming team their own key is bad and send them to rotate the
    wrong secret. A provider's `429` stays a `429`, because that one IS the
    caller's to back off from.
    """
    await seed_released_world(migrate_engine, fallback_answer=None)

    with stub_upstream(monkeypatch, _fails(upstream_status)):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == code


async def test_the_providers_own_error_body_is_not_forwarded(
    api, migrate_engine, monkeypatch
) -> None:
    """T-026's rule, one module over, holding at this seam too: a provider's own
    words can name an account, a quota, an internal model id or an organisation,
    and none of that is Prope's to hand to a consumer."""
    await seed_released_world(migrate_engine, fallback_answer=None)
    leak = "org-acme-prod quota exceeded for account 4417"

    with stub_upstream(monkeypatch, _fails(500, {"error": {"message": leak}})):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert leak not in response.body.decode()


async def test_the_call_record_says_upstream_error_and_names_the_class(
    api, migrate_engine, monkeypatch
) -> None:
    """`outcome = upstream_error`, distinct from `fallback` and from
    `caller_error`. The vocabulary is closed at five and each member answers a
    different question on the review screen — this one is *the provider broke and
    nothing covered it*."""
    await seed_released_world(migrate_engine, fallback_answer=None)

    with stub_upstream(monkeypatch, _fails(500)):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    record = enqueued_records()[0]
    assert record.outcome is Outcome.UPSTREAM_ERROR
    assert record.version_id == VERSION_ID
    assert record.error_class == "upstream_unavailable"
    assert record.fallback is False


async def test_a_revision_with_an_empty_fallback_has_no_cover_either(
    api, migrate_engine, monkeypatch
) -> None:
    """An empty string is not an answer. Serving it would be a 200 with no
    content — the shape a consumer is least able to detect and most likely to
    render straight into a product."""
    await seed_released_world(migrate_engine, fallback_answer="")

    with stub_upstream(monkeypatch, _fails(500)):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 502
    assert "x-prope-fallback" not in response.headers
