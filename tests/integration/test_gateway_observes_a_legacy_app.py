"""The whole adoption ladder's first rung, driven end to end through the gateway.

Everything else about observation is tested one seam at a time:
``tests/integration/test_prompt_observation.py`` calls ``record_observation``
directly, and ``tests/integration/test_gateway_list_models.py`` covers what a
folder-scoped key may see. **Nothing joined them.** The path a real product takes
— ``POST /v1/chat/completions`` with a provider model name and a system message,
through ``_forwards``, ``forward`` and the background task, into
``observation.observation`` — had no test at all, which meant the claim *"point
an unmodified app at Prope and its prompts show up"* rested on reading the code.

That claim is the product's entire answer to *"integration is too expensive"*, so
it is asserted here on the traffic an unmodified app actually sends: a `system`
message the served path refuses outright, a model name that is the provider's
rather than a prompt's, and no ``prope`` block of any kind.

The trap test is the important one. A key granted a FOLDER is not the same thing
as a key that OBSERVES — ``scope_namespaces`` says which prompts a key may
resolve, ``observe_provider_config_id``/``observe_namespace`` say where its
unresolvable calls go, and a key with the first and not the second is refused
exactly as it was before ADR-0059 shipped.
"""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.gateway import (
    CONFIG_ID,
    MODEL,
    SECOND_KEY_ID,
    VERSION_ID,
    WORKSPACE_A,
    authorization,
    gateway_api,
    seed_key,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion

#: The user's own example. An observing key files into ONE folder, and that
#: folder is the access container — nobody without a grant on it sees anything,
#: which is what makes an undiscovered prompt private by default (ADR-0061).
OBSERVE_NAMESPACE = "marketing"

#: A model name at the PROVIDER. No slash, so `parse_model_reference` refuses it
#: and ADR-0062's entry rule takes the first of its two branches — this is the
#: string every unmodified product in the world sends.
PROVIDER_MODEL = "gpt-4o-mini"

#: What a real product hardcodes, with a date interpolated into it. The date is
#: the reason grouping is asserted rather than assumed: a naive group-by-body
#: mints a fresh row every midnight, which turns an inventory into a log.
def _body(day: str) -> str:
    return (
        "You are Acme Support, the first-line assistant for Acme Corp.\n"
        f"Today is {day}.\n"
        "Answer in at most three short paragraphs. Never invent an order number."
    )


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _legacy_request(day: str = "2026-08-19", **extra) -> dict:
    """Exactly what `playgrounds/chatbot-app/index.html` puts on the wire.

    A `system` message first — which the served path answers with
    `system_message_not_allowed`, because a released revision carries its own —
    and no `prope` key anywhere in the body.
    """
    return {
        "model": PROVIDER_MODEL,
        "messages": [
            {"role": "system", "content": _body(day)},
            {"role": "user", "content": "Where is my order?"},
        ],
        **extra,
    }


async def _observing_world(migrate_engine: AsyncEngine, **key_overrides) -> None:
    """A released world plus a SECOND key that forwards instead of refusing.

    A second key rather than a re-seed of the first, because `seed_api_key` is an
    INSERT: the two keys now sit side by side in one workspace, which is also the
    truthful shape — a workspace adopting Prope has its integrated key and its
    observing key at the same time, and they must not interfere.

    The released prompt is left in place on purpose. An observing key must not
    stop serving the prompts it CAN resolve, and a world with no released
    revision would hide a regression that broke exactly that.
    """
    await seed_released_world(migrate_engine)
    await seed_key(
        migrate_engine,
        SECOND_KEY_ID,
        observe_provider_config_id=CONFIG_ID,
        observe_namespace=OBSERVE_NAMESPACE,
        **key_overrides,
    )


async def _observations(migrate_engine: AsyncEngine) -> list[dict]:
    async with migrate_engine.connect() as db:
        rows = await db.execute(
            text(
                """
                SELECT namespace, fingerprint, current_body, sighting_count,
                       inferred_variables, upstream_models
                FROM observation.observation
                WHERE workspace_id = :workspace_id
                ORDER BY first_seen_at
                """
            ),
            {"workspace_id": WORKSPACE_A},
        )
        return [dict(row) for row in rows.mappings()]


async def test_an_unmodified_app_is_answered_and_its_prompt_is_filed(
    api, migrate_engine, monkeypatch
) -> None:
    """The claim, in one request. Answered normally AND recorded.

    Both halves matter and the order they are asserted in is the order they fail
    in: a gateway that recorded the prompt but refused the call would be useless
    to a product that cannot be redeployed, and one that answered without
    recording would be a plain proxy.
    """
    await _observing_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_legacy_request(), headers=authorization(SECOND_KEY_ID)
        )

    assert response.status_code == 200, response.body
    assert provider.count == 1, "the call never reached the provider"
    assert response.json()["choices"][0]["message"]["content"] == "pong"

    filed = await _observations(migrate_engine)
    assert len(filed) == 1, filed
    assert filed[0]["namespace"] == OBSERVE_NAMESPACE
    assert "Acme Support" in filed[0]["current_body"]
    assert filed[0]["upstream_models"] == [PROVIDER_MODEL]


async def test_the_forwarded_answer_carries_no_marker_that_prope_looked(
    api, migrate_engine, monkeypatch
) -> None:
    """A legacy app that could detect observation would behave differently once it knew.

    The served path stamps `x-prope-version-id` and a `prope` block into the body
    (A-079). There is no revision here, so there is nothing honest to stamp — and
    inventing one would tell a product it is calling a governed prompt when it is
    calling the provider directly.
    """
    await _observing_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api, "POST", "/chat/completions", json_body=_legacy_request(), headers=authorization(SECOND_KEY_ID)
        )

    assert "x-prope-version-id" not in response.headers
    assert "x-prope-revision" not in response.headers
    assert "prope" not in response.json()


async def test_a_folder_scoped_key_that_does_not_observe_is_refused_as_before(
    api, migrate_engine, monkeypatch
) -> None:
    """**The trap.** A key assigned to a folder is not a key that observes.

    `scope_namespaces` widens what a key may RESOLVE (ADR-0061 / A-158); the
    `observe_*` pair is what sends an unresolvable call upstream (ADR-0059). They
    are set in different places and a key with only the first looks, in every
    screen, exactly like a key that is ready to observe — and then refuses every
    call with `model_not_found`.

    Asserted as a refusal that is byte-identical to the pre-ADR-0059 one, which is
    AC-17: an observe-disabled key is unaffected on every path.
    """
    await seed_released_world(migrate_engine, scope_namespaces=(OBSERVE_NAMESPACE,))

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api, "POST", "/chat/completions", json_body=_legacy_request(), headers=authorization()
        )

    assert response.status_code == 404, response.body
    assert response.json()["error"]["code"] == "model_not_found"
    assert provider.count == 0, "a non-observing key must not reach the provider"
    assert await _observations(migrate_engine) == []


async def test_a_days_traffic_from_one_persona_is_one_row_and_not_one_per_call(
    api, migrate_engine, monkeypatch
) -> None:
    """A-154 through the gateway rather than through `record_observation` directly.

    Three calls whose system messages differ only in the interpolated date. The
    fingerprint masks the date, so they are one prompt seen three times — and the
    diff proposes the date back as a variable rather than keeping nine tenths of
    it as prompt text.

    This is the property that decides whether the inventory is usable at all: at
    one row per call it is `ledger.call_body` with a nicer name.
    """
    await _observing_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        for day in ("2026-08-17", "2026-08-18", "2026-08-19"):
            response = await call(
                api,
                "POST",
                "/chat/completions",
                json_body=_legacy_request(day),
                headers=authorization(SECOND_KEY_ID),
            )
            assert response.status_code == 200, response.body

    filed = await _observations(migrate_engine)
    assert len(filed) == 1, [row["current_body"] for row in filed]
    assert filed[0]["sighting_count"] == 3


async def test_a_different_persona_is_a_different_observation(
    api, migrate_engine, monkeypatch
) -> None:
    """The grouping assertion above must not be satisfied by a rule that groups everything.

    A second persona — different instructions, no shared masked span — has to land
    as its own row, or the inventory says the product runs one prompt when it runs
    three.
    """
    await _observing_world(migrate_engine)

    billing = (
        "You are Acme Billing, handling invoices, refunds and payment failures.\n"
        "A refund over 500 USD always requires manager approval."
    )

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        for body in (_body("2026-08-19"), billing):
            response = await call(
                api,
                "POST",
                "/chat/completions",
                json_body={
                    "model": PROVIDER_MODEL,
                    "messages": [
                        {"role": "system", "content": body},
                        {"role": "user", "content": "Hello?"},
                    ],
                },
                headers=authorization(SECOND_KEY_ID),
            )
            assert response.status_code == 200, response.body

    filed = await _observations(migrate_engine)
    assert len(filed) == 2, [row["current_body"] for row in filed]
    assert {row["namespace"] for row in filed} == {OBSERVE_NAMESPACE}


async def test_the_prompts_the_key_can_still_resolve_are_still_served(
    api, migrate_engine, monkeypatch
) -> None:
    """Turning observation on must not turn the registry off.

    An observing key calling a name Prope DOES hold goes down the ordinary served
    path — released revision, version headers, no observation. Without this the
    entry rule could swallow the whole gateway and every other test here would
    still pass.
    """
    await _observing_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body={"model": MODEL, "messages": [{"role": "user", "content": "Refund?"}]},
            headers=authorization(SECOND_KEY_ID),
        )

    assert response.status_code == 200, response.body
    assert response.headers["x-prope-version-id"] == VERSION_ID
    assert await _observations(migrate_engine) == []
