"""AC-2 — a pin to a revision that is not Approved is refused, and nothing is dispatched.

BR-03's database constraint guards the released POINTER, and a pin does not go
through it — so the refusal has to exist somewhere, and A-022 puts it in the
registry rather than here: *"The gateway does not re-implement the rule — it asks
the registry, whose database constraint is the authority."* A second check on the
hot path would be a second thing that can disagree with the first, and the weaker
one always wins an argument at 3am.

What this file asserts is therefore the gateway's half: the pin travels, the
refusal arrives, no money is spent upstream, and the counter says which kind of
miss it was.
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


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _miss(reason: str) -> float:
    return REGISTRY.get_sample_value("prope_gateway_resolve_miss_total", {"reason": reason}) or 0.0


def _request(model: str) -> dict:
    return {"model": model, "messages": [{"role": "user", "content": "hi"}]}


async def _two_revisions(migrate_engine, second_status: str) -> None:  # noqa: ANN001
    """Revision 1 approved and released; revision 2 in the state under test."""
    await seed_released_world(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        body="The second body.",
        provider_config_id=CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
        status=second_status,
    )


async def test_a_pin_at_an_approved_revision_is_served_from_that_revision(
    api, migrate_engine, monkeypatch
) -> None:
    """A-022's first half. The pin resolves a specific revision, and the response
    says `pinned` so a consumer can see they have opted out of restores."""
    await _two_revisions(migrate_engine, "Draft")
    await approve(migrate_engine, SECOND_VERSION)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@2"),
            headers=authorization(),
        )

    assert response.status_code == 200, response.body
    assert response.headers["x-prope-version-id"] == SECOND_VERSION
    assert response.headers["x-prope-pinned"] == "true"
    assert response.json()["prope"]["pinned"] is True
    assert provider.body()["messages"][0]["content"] == "The second body."


async def test_a_pin_at_a_draft_revision_is_refused_and_nothing_is_dispatched(
    api, migrate_engine, monkeypatch
) -> None:
    """The acceptance criterion's centre. An unapproved revision is text nobody
    signed off, and serving it through a pin would route around the whole
    approval path — which is the one thing a spreadsheet cannot do and the one
    thing this product must."""
    await _two_revisions(migrate_engine, "Draft")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@2"),
            headers=authorization(),
        )

    assert response.status_code == 404
    assert provider.count == 0, "an unapproved revision reached a provider"


async def test_a_pin_at_a_revision_in_review_is_refused_too(
    api, migrate_engine, monkeypatch
) -> None:
    """`In review` is not `Approved`, and the three-member vocabulary is compared
    literally — a "tidier" lower-case spelling one module over would silently
    make every released pointer unsettable, and this is the same literal."""
    await _two_revisions(migrate_engine, "In review")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())) as provider:
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@2"),
            headers=authorization(),
        )

    assert response.status_code == 404
    assert provider.count == 0


async def test_the_refusal_is_counted_as_a_pin_miss(api, migrate_engine, monkeypatch) -> None:
    """`prope_gateway_resolve_miss_total{reason="pin_not_approved"}`.

    INT-009 renders BOTH pin failures — the revision does not exist, and the
    revision is not Approved — as one `no_release` miss, and
    `tests/contract/test_registry_seams.py` locks that: *"the caller must not be
    able to tell 'that revision exists but you may not have it' from 'nothing is
    released'"*. So the registry cannot hand this module the distinction, and
    this module will not invent it by reading a second time on the hot path.
    Every pinned miss is therefore counted here as `pin_not_approved`, and
    `pin_not_found` is a declared label value nothing increments — recorded as
    `OQ-144` rather than papered over.
    """
    await _two_revisions(migrate_engine, "Draft")
    before = _miss("pin_not_approved")

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@2"),
            headers=authorization(),
        )

    assert _miss("pin_not_approved") == before + 1


async def test_a_pin_by_version_id_resolves_the_same_revision(
    api, migrate_engine, monkeypatch
) -> None:
    """`@<n>` and `@<version_id>` are different columns one module over. Both
    forms are in scope by the user's own words (*"optionally @revision"*)."""
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        response = await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@{VERSION_ID}"),
            headers=authorization(),
        )

    assert response.status_code == 200, response.body
    assert response.headers["x-prope-version-id"] == VERSION_ID
    assert response.headers["x-prope-pinned"] == "true"


async def test_a_pinned_call_is_counted_per_prompt(api, migrate_engine, monkeypatch) -> None:
    """`prope_gateway_pinned_call_total{prompt}` — the restore-blindness signal.

    A prompt with sustained pinned traffic after a release is a consumer the
    release did not reach, and the product's headline claim to the Developer
    persona silently does not apply to them. It is visibility only: pinning is in
    scope by the user's own words, and the counter cannot be surfaced on the
    release screen because release-control may not read traffic data.
    """
    await seed_released_world(migrate_engine)
    before = REGISTRY.get_sample_value("prope_gateway_pinned_call_total", {"prompt": MODEL}) or 0.0

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@1"),
            headers=authorization(),
        )

    after = REGISTRY.get_sample_value("prope_gateway_pinned_call_total", {"prompt": MODEL}) or 0.0
    assert after == before + 1


async def test_the_prompt_label_carries_the_name_and_never_the_pin(
    api, migrate_engine, monkeypatch
) -> None:
    """ADR-0030 bounds label cardinality. `name@7` and `name@8` as two series
    would make a per-prompt counter unbounded in the revision number, which grows
    forever and is exactly the shape a metric label must not have."""
    await seed_released_world(migrate_engine)

    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        await call(
            api,
            "POST",
            "/chat/completions",
            json_body=_request(f"{MODEL}@1"),
            headers=authorization(),
        )

    assert (
        REGISTRY.get_sample_value("prope_gateway_pinned_call_total", {"prompt": f"{MODEL}@1"})
        is None
    )
