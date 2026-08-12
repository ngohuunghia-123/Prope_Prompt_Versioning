"""AC-10 and T-014 — a scope refusal is the same not-found as a name that does not exist.

A-081 makes a consumer key default-deny and scoped by model name; A-116 makes the
refusal indistinguishable from an unknown model. The second is the security
property and it is the one asserted byte for byte: a leaked key that could tell
*that prompt exists and you may not have it* from *no such prompt* could
enumerate the registry one guess at a time, and a leaked key's blast radius is
supposed to be what somebody deliberately put on it.

ADR-0050 is what makes it enforceable in ONE place: all three refusals resolve
through the gateway application's own handler set rather than at every call site.
"""

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.access_control import KEY_ID
from tests.gateway import (
    MODEL,
    SECOND_KEY_ID,
    authorization,
    enqueued_records,
    gateway_api,
    seed_key,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion

OTHER_MODEL = "ecom/pricing-agent"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _miss(reason: str) -> float:
    return (
        REGISTRY.get_sample_value("prope_gateway_resolve_miss_total", {"reason": reason}) or 0.0
    )


async def _refusals(api, monkeypatch, migrate_engine) -> dict[str, object]:  # noqa: ANN001
    """The three refusals A-116 requires to be one answer, collected together."""
    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        out_of_scope = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": OTHER_MODEL, "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )
        never_existed = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": "nobody/nothing", "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )
    return {"out_of_scope": out_of_scope, "never_existed": never_existed, "provider": provider}


async def test_a_key_scoped_elsewhere_is_refused(api, migrate_engine, monkeypatch) -> None:
    await seed_released_world(migrate_engine, scope=("support/refund-classifier",))

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": OTHER_MODEL, "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )

    assert response.status_code == 404
    assert provider.count == 0


async def test_the_scope_refusal_is_byte_identical_to_a_name_that_never_existed(
    api, migrate_engine, monkeypatch
) -> None:
    """T-014, and it is asserted on the BYTES rather than on the status code.

    Two 404s carrying different messages are still an oracle. The one thing that
    legitimately differs is the model name the caller themselves sent, which
    tells them nothing they did not already know — so the comparison substitutes
    it out and requires everything else to match exactly.
    """
    await seed_released_world(migrate_engine)
    refusals = await _refusals(api, monkeypatch, migrate_engine)

    out_of_scope = refusals["out_of_scope"]
    never_existed = refusals["never_existed"]

    assert out_of_scope.status_code == never_existed.status_code == 404
    assert out_of_scope.body.replace(OTHER_MODEL.encode(), b"") == never_existed.body.replace(
        b"nobody/nothing", b""
    )


async def test_an_empty_scope_resolves_nothing_at_all(api, migrate_engine, monkeypatch) -> None:
    """A-081: *"A key with an empty scope resolves nothing."* Default-deny means
    a released prompt does not become callable because a key exists in the same
    workspace."""
    await seed_released_world(migrate_engine, scope=())

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )

    assert response.status_code == 404
    assert provider.count == 0


async def test_the_refusal_is_counted_as_not_permitted_and_not_as_a_typo(
    api, migrate_engine, monkeypatch
) -> None:
    """One answer to the caller, three lines in the metric.

    The label is the only place an operator can tell a scope problem from a
    withdrawal from a typo — and the caller cannot, which is the whole
    arrangement. `not_permitted` rising is a consuming team that was never
    granted the prompt; `no_release` rising is ADR-0009's blast-radius signal.
    """
    await seed_released_world(migrate_engine, scope=())
    before = _miss("not_permitted")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )

    assert _miss("not_permitted") == before + 1


async def test_a_revoked_key_stops_working_on_the_very_next_request(
    api, migrate_engine, monkeypatch, app_sessionmaker
) -> None:
    """ADR-0022 and A-114, at the one place a cache would have hidden it.

    The resolution cache beside this call has a 30 s TTL; the two access-control
    reads in front of it have none, on either side of the seam. That divergence
    is deliberate and this is what it buys: a stale pointer would serve a
    previously approved revision one TTL late, and a stale permission would serve
    a REVOKED key.
    """
    from sqlalchemy import text

    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        first = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )
        assert first.status_code == 200, first.body

        async with migrate_engine.begin() as connection:
            await connection.execute(
                text("UPDATE access.api_key SET revoked_at = now() WHERE id = :id"),
                {"id": KEY_ID},
            )

        second = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )

    assert second.status_code == 401


async def test_one_keys_scope_does_not_widen_another_keys(
    api, migrate_engine, monkeypatch
) -> None:
    """Two keys in one workspace, and the answer depends on the key rather than
    on the workspace — which is what makes a leaked key's blast radius what
    somebody put on it."""
    await seed_released_world(migrate_engine, scope=(MODEL,))
    await seed_key(migrate_engine, SECOND_KEY_ID, scope=())

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        permitted = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )
        refused = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(SECOND_KEY_ID),
        )

    assert permitted.status_code == 200, permitted.body
    assert refused.status_code == 404


async def test_a_refusal_before_resolution_writes_no_call_record(
    api, migrate_engine, monkeypatch
) -> None:
    """A-086 says an authenticated refusal writes a record; the database says a
    gateway record must carry a `version_id`
    (`ck_call_record_gateway_calls_carry_version_id`). A scope refusal has no
    revision to name, so the two cannot both hold and the CONSTRAINT wins —
    enqueueing a row the writer must reject would trade a missing record for a
    dead-lettered one. Raised as `OQ-143` rather than resolved by weakening
    either side; the refusal is counted on
    `prope_gateway_resolve_miss_total{reason="not_permitted"}`.
    """
    await seed_released_world(migrate_engine, scope=())

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
            headers=authorization(),
        )

    assert enqueued_records() == []
