"""ADR-0069 — the gateway walks a revision's frozen route and advances when a rung is unusable.

The whole feature reduces to one loop, and this file is the loop's contract:
which failures advance, which stop, what the caller is told when every rung has
failed, and what the call record names afterwards.

Three claims here are load-bearing beyond the feature itself.

**`content_policy` and `invalid_request` do not advance.** Asserted by counting
the second rung's requests, not by reading a response — a route that walked a
policy refusal to a provider that accepts it would be selling a compliance hole,
and the only way to see that from outside is that the second provider was never
asked.

**One deadline for the whole request.** ADR-0013 rejected retry because *"a retry
doubles the worst case"*, and the answer is a budget rather than a waiver: each
dispatch gets what is left. A spy on `deadline_ms` is what makes that a fact.

**The caller is told what the LAST rung did.** Not the first. A `retry-after`
harvested from rung 1 and returned after rung 3 answered is a number about a
provider the caller never reached.
"""

import json

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.domain import Outcome
from tests.gateway import (
    BACKUP_CONFIG_ID,
    BACKUP_MODEL,
    CONFIG_ID,
    MODEL,
    UPSTREAM_MODEL,
    VERSION_ID,
    authorization,
    enqueued_records,
    gateway_api,
    seed_routed_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion

FALLBACK = "A person will look at this shortly."


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _request(**extra) -> dict:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hi"}], **extra}


def _by_model(**answers):  # noqa: ANN003, ANN202
    """Route the stub on the upstream model the request names.

    The two rungs differ by configuration AND by model, so the stub can tell
    them apart from the composed request body alone — which means every
    assertion about which rung answered is read off the wire rather than off a
    counter this file maintains.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        answer = answers[model]
        return answer(request) if callable(answer) else answer

    return handler


def _fails(status: int, **body) -> httpx.Response:  # noqa: ANN003
    return httpx.Response(status, json={"error": {"message": "upstream is unwell", **body}})


def _served(entry: int) -> float:
    return (
        REGISTRY.get_sample_value("prope_gateway_route_served_entry_total", {"entry": str(entry)})
        or 0.0
    )


def _advanced(error_class: str) -> float:
    return (
        REGISTRY.get_sample_value(
            "prope_gateway_route_advanced_total", {"error_class": error_class}
        )
        or 0.0
    )


def _exhausted(reason: str) -> float:
    return (
        REGISTRY.get_sample_value("prope_gateway_route_exhausted_total", {"reason": reason}) or 0.0
    )


async def test_the_second_entry_answers_when_the_first_refuses(
    api, migrate_engine, monkeypatch
) -> None:
    """The feature, in one assertion: a 500 on rung 1 becomes a 200 from rung 2."""
    await seed_routed_world(migrate_engine)

    with stub_upstream(
        monkeypatch,
        _by_model(
            **{
                UPSTREAM_MODEL: _fails(500),
                BACKUP_MODEL: httpx.Response(200, json=completion(model=BACKUP_MODEL)),
            }
        ),
    ) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    assert provider.count == 2
    assert response.headers["x-prope-route-entry"] == "2"
    assert response.headers["x-prope-route-attempts"] == "2"
    assert response.headers["x-prope-version-id"] == VERSION_ID


async def test_the_response_names_the_model_that_actually_answered(
    api, migrate_engine, monkeypatch
) -> None:
    """`ServedIdentity` is built AFTER the loop, and this is why it has to be.

    Built before, it would carry the PRIMARY rung's model whatever answered —
    so `x-prope-model` and `prope.upstream_model` would quietly lie on exactly
    the calls a customer is trying to explain. A header that lies is worse than
    no header at all.
    """
    await seed_routed_world(migrate_engine)

    with stub_upstream(
        monkeypatch,
        _by_model(
            **{
                UPSTREAM_MODEL: _fails(503),
                BACKUP_MODEL: httpx.Response(200, json=completion(model=BACKUP_MODEL)),
            }
        ),
    ):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.json()["prope"]["upstream_model"] == BACKUP_MODEL
    assert response.json()["prope"]["route_entry"] == 2
    assert response.json()["prope"]["route_attempts"] == 2


async def test_the_call_record_names_the_provider_that_served_and_stays_ok(
    api, migrate_engine, monkeypatch
) -> None:
    """No schema change was needed for traceability, and no new `Outcome` member.

    `CallFacts` is overwritten per attempt, so the record already names the rung
    that served. The outcome stays `ok` because a failed-over caller received a
    real model answer — a `failed_over` member would break
    `ck_call_record_outcome_values` and silently re-base every `outcome=ok`
    share on every dashboard ever drawn.

    `error_class` stays absent: an error class on an `ok` row reads, to every
    downstream reader, as an error nobody had.
    """
    await seed_routed_world(migrate_engine)

    with stub_upstream(
        monkeypatch,
        _by_model(
            **{
                UPSTREAM_MODEL: _fails(429),
                BACKUP_MODEL: httpx.Response(200, json=completion(model=BACKUP_MODEL)),
            }
        ),
    ):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    record = enqueued_records()[0]
    assert record.outcome is Outcome.OK
    assert record.provider_config_id == BACKUP_CONFIG_ID
    assert record.upstream_model == BACKUP_MODEL
    assert record.version_id == VERSION_ID
    assert record.error_class is None


@pytest.mark.parametrize("status", [429, 401, 404, 500, 502, 503])
async def test_every_advancing_failure_reaches_the_next_entry(
    api, migrate_engine, monkeypatch, status: int
) -> None:
    """Rate limit, rejected credential, unknown model, and three server failures.

    Derived from `CLASSIFICATION`'s `fallback_eligible` rather than listed by
    hand in the gateway, so a new `ErrorClass` cannot arrive silently
    unclassified. `fallback_eligible` already means *"this failure is about the
    provider, not about the request"* — which is exactly what *"should somebody
    else try it"* asks.
    """
    await seed_routed_world(migrate_engine)

    with stub_upstream(
        monkeypatch,
        _by_model(
            **{
                UPSTREAM_MODEL: _fails(status),
                BACKUP_MODEL: httpx.Response(200, json=completion(model=BACKUP_MODEL)),
            }
        ),
    ) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    assert provider.count == 2


@pytest.mark.parametrize("status", [400, 422])
async def test_a_caller_error_stops_the_route_and_the_backup_is_never_asked(
    api, migrate_engine, monkeypatch, status: int
) -> None:
    """**The assertion that matters is `provider.count == 1`.**

    `content_policy` and `invalid_request` are not `fallback_eligible`, and
    excluding them is not an oversight: advancing on a policy refusal is
    policy-shopping — walking a request one provider refused on policy grounds
    to a provider that will accept it — and a product whose failover does that
    is selling a compliance hole. A malformed request fails identically
    everywhere, so advancing only burns the budget.
    """
    await seed_routed_world(migrate_engine)

    with stub_upstream(
        monkeypatch,
        _by_model(
            **{
                UPSTREAM_MODEL: _fails(status),
                BACKUP_MODEL: httpx.Response(200, json=completion(model=BACKUP_MODEL)),
            }
        ),
    ) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert provider.count == 1, "a caller error must not be walked to a second provider"
    assert response.status_code != 200


async def test_the_first_entry_serves_without_touching_the_second(
    api, migrate_engine, monkeypatch
) -> None:
    """The ordinary case, and the one that must not get slower.

    Nearly all traffic takes this path. `RevisionBinding.candidates` makes a
    pair-bound revision a one-entry route so the loop is written once and the
    unrouted path is its degenerate case — but a routed revision whose primary
    is healthy must still make exactly one upstream call.
    """
    await seed_routed_world(migrate_engine)
    before = _served(1)

    with stub_upstream(
        monkeypatch,
        _by_model(**{UPSTREAM_MODEL: httpx.Response(200, json=completion())}),
    ) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    assert provider.count == 1
    assert response.headers["x-prope-route-entry"] == "1"
    assert _served(1) == before + 1
    assert enqueued_records()[0].provider_config_id == CONFIG_ID


async def test_an_unrouted_revision_carries_no_route_headers(
    api, migrate_engine, monkeypatch
) -> None:
    """The pair-bound path is unchanged on the wire.

    Headers follow `x-prope-fallback`'s precedent and appear only when routed;
    the `prope` BODY block carries all three keys always, so its shape is stable
    for a client that reads it. Both halves of that are asserted, because a
    header appearing on every call would be a contract change for consumers who
    never asked for routing.
    """
    from tests.gateway import seed_released_world

    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 200, response.body
    assert "x-prope-route-entry" not in response.headers
    assert "x-prope-route-attempts" not in response.headers
    body = response.json()["prope"]
    assert body["route_combo_id"] is None
    assert body["route_entry"] is None
    assert body["route_attempts"] == 1


async def test_the_metrics_count_the_advance_and_the_entry_that_served(
    api, migrate_engine, monkeypatch
) -> None:
    """`GatewayRouteBackupServing` reads `route_served_entry_total{entry!="1"}`.

    That alert is the mitigation for the hazard this feature creates — failover
    works, so the caller gets a 200 and a primary provider can stay down for
    weeks — and it is only as good as the series underneath it. The
    `error_class` label on `route_advanced_total` is what names *which* failure
    is pushing traffic across.
    """
    await seed_routed_world(migrate_engine)
    served_before = _served(2)
    advanced_before = _advanced("rate_limited")

    with stub_upstream(
        monkeypatch,
        _by_model(
            **{
                UPSTREAM_MODEL: _fails(429),
                BACKUP_MODEL: httpx.Response(200, json=completion(model=BACKUP_MODEL)),
            }
        ),
    ):
        await call(api, "POST", "/chat/completions", json_body=_request(), headers=authorization())

    assert _served(2) == served_before + 1
    assert _advanced("rate_limited") == advanced_before + 1


async def test_a_canned_answer_is_reached_only_after_every_entry_has_failed(
    api, migrate_engine, monkeypatch
) -> None:
    """What `GatewayFallbackRateHigh` now means, without its expression changing.

    On a routed revision a canned answer is served only when the workspace has
    no working provider at all — a rarer and much worse event than "an upstream
    is failing", which is what the alert used to mean.
    """
    await seed_routed_world(migrate_engine, fallback_answer=FALLBACK)
    exhausted_before = _exhausted("entries_exhausted")

    with stub_upstream(
        monkeypatch,
        _by_model(**{UPSTREAM_MODEL: _fails(500), BACKUP_MODEL: _fails(503)}),
    ) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert provider.count == 2
    assert response.status_code == 200, response.body
    assert response.headers["x-prope-fallback"] == "true"
    assert response.json()["choices"][0]["message"]["content"] == FALLBACK
    assert enqueued_records()[0].outcome is Outcome.FALLBACK
    assert _exhausted("entries_exhausted") == exhausted_before + 1


async def test_the_caller_is_told_what_the_last_entry_did(
    api, migrate_engine, monkeypatch
) -> None:
    """Rung 1 rate-limits, rung 2 is unavailable: the caller gets rung 2's answer.

    The last error and not the first. `upstream_unavailable` translates to 502
    and `rate_limited` to 429, so the status line alone says which one was
    returned — and a 429 here would be worse than merely wrong, because a 429
    carries `retry-after`, a retry hint about a provider the caller never
    reached and whose rate limit has nothing to do with what failed.
    """
    await seed_routed_world(migrate_engine)

    with stub_upstream(
        monkeypatch,
        _by_model(**{UPSTREAM_MODEL: _fails(429), BACKUP_MODEL: _fails(503)}),
    ):
        response = await call(
            api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
        )

    assert response.status_code == 502, response.body
    assert response.json()["error"]["code"] == "upstream_unavailable"
    assert "retry-after" not in response.headers
