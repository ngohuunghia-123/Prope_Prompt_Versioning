"""A-022's second spelling, end to end — `prope.version` pins the same revision `@n` does.

A bare model name is served by the RELEASED revision and follows every future
release without a redeploy; that is the product's restore-without-redeploy claim
and it is unchanged here. This file is about the opt-out: a caller that names a
revision gets that revision, whichever of the two ways they name it, and gets the
identical refusal when it is not theirs to have.

Driven against the real prompt-registry and access-control with only the provider
stubbed, because the thing worth asserting is that the body dispatched came from
the revision the caller asked for — which no unit test can see.
"""

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.gateway import (
    CONFIG_ID,
    MODEL,
    UPSTREAM_MODEL,
    VERSION_ID,
    authorization,
    gateway_api,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.prompt_registry import approve, seed_revision
from tests.provider_access._stub import completion

SECOND_VERSION = "rev_01J000000000000000000REV2"

SECOND_BODY = "The second body."


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _request(model: str, **prope) -> dict:
    body: dict = {"model": model, "messages": [{"role": "user", "content": "hi"}]}
    if prope:
        body["prope"] = prope
    return body


async def _two_approved_revisions(migrate_engine) -> None:  # noqa: ANN001
    """Revision 1 approved and RELEASED; revision 2 approved and not released.

    The shape the question is actually about: the newest approved revision is not
    the one production serves, because releasing is a separate recorded human
    decision. Both are reachable by pin.
    """
    await seed_released_world(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        body=SECOND_BODY,
        provider_config_id=CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
    )
    await approve(migrate_engine, SECOND_VERSION)


async def test_a_bare_name_is_still_served_by_the_released_revision(
    api, migrate_engine, monkeypatch
) -> None:
    """The unchanged half, asserted because this change must not move it: a newer
    APPROVED revision exists, and production keeps serving the released one until
    a human releases it. Approval is not release (BR-03, and the first of the four
    non-negotiables)."""
    await _two_approved_revisions(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(MODEL), headers=authorization()
        )

    assert response.status_code == 200, response.body
    assert response.headers["x-prope-version-id"] == VERSION_ID
    assert response.headers["x-prope-pinned"] == "false"
    assert provider.body()["messages"][0]["content"] != SECOND_BODY


async def test_a_version_in_the_body_serves_that_revision(api, migrate_engine, monkeypatch) -> None:
    """The request the question asked for, in the spelling it asked for."""
    await _two_approved_revisions(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MODEL, version=2),
            headers=authorization(),
        )

    assert response.status_code == 200, response.body
    assert response.headers["x-prope-version-id"] == SECOND_VERSION
    assert response.json()["prope"]["revision_number"] == 2
    assert provider.body()["messages"][0]["content"] == SECOND_BODY


async def test_the_two_spellings_resolve_to_the_same_revision(
    api, migrate_engine, monkeypatch
) -> None:
    """One lookup, not two. If these ever diverged, an integration would be
    served a different prompt for changing where it wrote the same number."""
    await _two_approved_revisions(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        via_name = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@2"),
            headers=authorization(),
        )
        via_body = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MODEL, version=2),
            headers=authorization(),
        )

    assert via_name.headers["x-prope-version-id"] == via_body.headers["x-prope-version-id"]
    assert via_name.headers["x-prope-pinned"] == via_body.headers["x-prope-pinned"] == "true"


async def test_the_response_echoes_the_model_string_the_caller_sent(
    api, migrate_engine, monkeypatch
) -> None:
    """A-079. The caller wrote a bare name, so `model` comes back bare — the
    version is reported in `prope` and the headers, where it belongs, rather than
    by inventing a string nobody sent."""
    await _two_approved_revisions(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MODEL, version=2),
            headers=authorization(),
        )

    assert response.json()["model"] == MODEL
    assert response.json()["prope"]["pinned"] is True


async def test_a_version_id_works_in_the_body_too(api, migrate_engine, monkeypatch) -> None:
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MODEL, version=VERSION_ID),
            headers=authorization(),
        )

    assert response.status_code == 200, response.body
    assert response.headers["x-prope-version-id"] == VERSION_ID


async def test_a_body_pinned_call_is_counted_as_a_pinned_call(
    api, migrate_engine, monkeypatch
) -> None:
    """`prope_gateway_pinned_call_total` is the restore-blindness signal — a
    prompt with sustained pinned traffic after a release is a consumer the
    release did not reach. A new spelling that did not count would make that
    signal quietly go dark as integrations moved to it."""
    await _two_approved_revisions(migrate_engine)
    before = REGISTRY.get_sample_value("prope_gateway_pinned_call_total", {"prompt": MODEL}) or 0.0

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MODEL, version=2),
            headers=authorization(),
        )

    after = REGISTRY.get_sample_value("prope_gateway_pinned_call_total", {"prompt": MODEL}) or 0.0
    assert after == before + 1


async def test_a_version_at_an_unapproved_revision_is_refused_and_nothing_is_dispatched(
    api, migrate_engine, monkeypatch
) -> None:
    """The rule the whole product rests on, through the new door. BR-03 guards the
    released pointer and A-022 guards the pin; a second spelling of the pin must
    not be a way around either."""
    await seed_released_world(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        body=SECOND_BODY,
        provider_config_id=CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
        status="Draft",
    )

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MODEL, version=2),
            headers=authorization(),
        )

    assert response.status_code == 404
    assert provider.count == 0, "an unapproved revision reached a provider"


async def test_a_version_naming_no_revision_is_the_same_not_found(
    api, migrate_engine, monkeypatch
) -> None:
    """Byte-identical to an unknown model name (A-116). A caller who could tell
    a refusal about a revision from a refusal about a name could enumerate the
    registry one 404 at a time."""
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        unknown_version = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(MODEL, version=99),
            headers=authorization(),
        )
        unknown_name = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request("support/no-such-prompt"),
            headers=authorization(),
        )

    assert unknown_version.status_code == unknown_name.status_code == 404
    assert unknown_version.json()["error"]["code"] == unknown_name.json()["error"]["code"]


async def test_two_different_revisions_in_one_request_is_refused_without_a_lookup(
    api, migrate_engine, monkeypatch
) -> None:
    """A 400, not a 404, and it tells the caller nothing about the registry: the
    contradiction is between two fields they sent themselves, and the answer is
    the same whether the prompt exists or not."""
    await _two_approved_revisions(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@1", version=2),
            headers=authorization(),
        )

    assert response.status_code == 400, response.body
    assert response.json()["error"]["code"] == "version_conflict"
    assert response.json()["error"]["param"] == "prope.version"
    assert provider.count == 0


async def test_the_same_revision_said_twice_is_served_rather_than_refused(
    api, migrate_engine, monkeypatch
) -> None:
    """A client that fills in both places is saying one thing twice."""
    await _two_approved_revisions(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@2", version=2),
            headers=authorization(),
        )

    assert response.status_code == 200, response.body
    assert response.headers["x-prope-version-id"] == SECOND_VERSION
