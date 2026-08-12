"""AC-1 — a bare model name is served by the released revision, and says so.

The whole product in one request: a consuming product names a prompt by model
name, the released revision's body becomes the system message, provider-access
dispatches it, and the answer carries the identity of what produced it in both
the headers and the body (A-079). The call record carries the same version id,
which is the *"100% of calls record a version ID"* success metric.

Driven against the real prompt-registry, access-control and provider-access, with
only the provider itself stubbed — at the httpx transport rather than at a
socket, because ADR-0047's SSRF guard refuses loopback and a stub bound to
127.0.0.1 is exactly the thing that control exists to refuse.
"""

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.domain import Outcome, Source
from tests.gateway import (
    KEY_ID,
    MODEL,
    PROMPT_ID,
    UPSTREAM_MODEL,
    VERSION_ID,
    WORKSPACE_A,
    authorization,
    enqueued_records,
    gateway_api,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _request(**extra) -> dict:
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Is this refund in policy?"}],
        **extra,
    }


def _resolve_duration(cache: str) -> float:
    return (
        REGISTRY.get_sample_value("prope_gateway_resolve_duration_seconds_count", {"cache": cache})
        or 0.0
    )


async def test_a_bare_name_is_served_by_the_released_revision(
    api, migrate_engine, monkeypatch
) -> None:
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    assert provider.count == 1


async def test_the_identity_of_what_served_it_is_in_the_headers(
    api, migrate_engine, monkeypatch
) -> None:
    """A-079's first half. Headers rather than body alone, because on a streaming
    call the headers are the only place metadata can arrive before content."""
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.headers["x-prope-version-id"] == VERSION_ID
    assert response.headers["x-prope-model"] == MODEL
    assert response.headers["x-prope-revision"] == "1"
    assert response.headers["x-prope-pinned"] == "false"
    assert "x-prope-fallback" not in response.headers


async def test_the_identity_is_in_the_body_and_the_model_field_echoes_the_prope_name(
    api, migrate_engine, monkeypatch
) -> None:
    """A-079: *"The response's own `model` field echoes the Prope model name the
    caller asked for, not the upstream model — clients compare that field, and
    the upstream model is visible in `prope.upstream_model` instead."*

    The stub answers with `model: gpt-4o-mini`, so a gateway that passed the
    provider's response through untouched would tell the consumer their call went
    to a model they never named.
    """
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    body = response.json()
    assert body["model"] == MODEL
    assert body["prope"] == {
        "version_id": VERSION_ID,
        "revision_number": 1,
        "pinned": False,
        "fallback": False,
        "upstream_model": UPSTREAM_MODEL,
    }


async def test_the_revisions_body_is_the_system_message_and_the_only_one(
    api, migrate_engine, monkeypatch
) -> None:
    """ADR-0011, read off the request the production client actually built.

    The composed set is asserted as a WHOLE rather than by checking that the
    first message is the revision's: *"it is always first, and it is the only
    one"*, and a second system message appended anywhere after would pass a
    first-element assertion.
    """
    await seed_released_world(migrate_engine, body="Decide refunds strictly.")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    messages = provider.body()["messages"]
    assert messages == [
        {"role": "system", "content": "Decide refunds strictly."},
        {"role": "user", "content": "Is this refund in policy?"},
    ]
    assert provider.body()["model"] == UPSTREAM_MODEL


async def test_the_call_record_carries_the_version_id_that_served_it(
    api, migrate_engine, monkeypatch
) -> None:
    """The success metric, at the seam where it becomes true.

    `enqueue` is the whole of this module's obligation (A-087): the record is
    handed over after the response is flushed and call-ledger owns everything
    after that. What is asserted is the draft this module handed over.
    """
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    records = enqueued_records()
    assert len(records) == 1

    record = records[0]
    assert record.version_id == VERSION_ID
    assert record.prompt_id == PROMPT_ID
    assert record.revision_number == 1
    assert record.source is Source.GATEWAY
    assert record.outcome is Outcome.OK
    assert record.workspace_id == WORKSPACE_A
    assert record.consumer_key_id == KEY_ID
    assert record.call_id.startswith("cal_")
    assert record.pinned is False
    assert record.fallback is False


async def test_the_usage_the_provider_reported_reaches_the_record(
    api, migrate_engine, monkeypatch
) -> None:
    """A-030: cost is measured from actual runs and never inferred from length,
    so the token counts on the record are the provider's own figures."""
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    record = enqueued_records()[0]
    assert record.input_tokens == 3
    assert record.output_tokens == 1


async def test_the_second_call_is_served_from_the_cache(
    api, migrate_engine, monkeypatch
) -> None:
    """ADR-0012's one surviving argument, observable: the first resolution is a
    miss and the second is a hit, on the same key, inside the TTL.

    The two access-control reads in front of it are NOT cached and never will be
    (A-114, ADR-0022) — a stale pointer serves a previously approved revision one
    TTL late, a stale permission serves a revoked key.
    """
    await seed_released_world(migrate_engine)

    miss_before = _resolve_duration("miss")
    hit_before = _resolve_duration("hit")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    assert _resolve_duration("miss") == miss_before + 1
    assert _resolve_duration("hit") == hit_before + 1


async def test_an_unknown_key_is_refused_before_any_registry_read(
    api, migrate_engine, monkeypatch
) -> None:
    """*"An unknown key returns 401 and reveals nothing about whether the model
    name exists"*, and A-086: an unauthenticated call writes NO call record —
    there is no workspace to attribute one to, and an unauthenticated endpoint
    that writes to durable storage on request is a way to fill somebody's disk.
    """
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(),
            headers={"authorization": "Bearer prope_key_01J0000000000000000BOGUS_nope"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"
    assert provider.count == 0
    assert enqueued_records() == []


async def test_a_request_with_no_authorization_header_is_refused(api, migrate_engine) -> None:
    await seed_released_world(migrate_engine)

    response = await call(api, "POST", "/chat/completions", json_body=_request())

    assert response.status_code == 401
    assert enqueued_records() == []
