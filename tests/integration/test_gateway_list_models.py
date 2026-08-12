"""AC-12 / A-082 — `GET /v1/models` lists released prompts this key may resolve, and no others.

Two filters, and each one dropped is a different disclosure. Without the release
filter a consumer discovers prompts that have never been approved for production.
Without the scope filter a leaked key enumerates the whole workspace in one
request — which is the same enumeration A-116 spends the chat-completions refusal
shape to prevent, through a door that hands over the list directly.

INT-010 exists rather than a management list query with arguments for exactly
this reason: *"Reusing the management query here would leak unreleased and
unpermitted prompts into the gateway's model list through a default argument
nobody reviewed."*
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.gateway import (
    CONFIG_ID,
    MODEL,
    UPSTREAM_MODEL,
    VERSION_ID,
    authorization,
    gateway_api,
    seed_released_world,
)
from tests.integration._asgi import call
from tests.prompt_registry import approve, release, seed_prompt, seed_revision

RELEASED_TWO = "billing/invoice-explainer"

RELEASED_THREE = "ecom/pricing-agent"

UNRELEASED_ONE = "support/draft-helper"

UNRELEASED_TWO = "support/never-approved"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


async def _prompt(
    migrate_engine,  # noqa: ANN001
    model_name: str,
    index: int,
    *,
    released: bool,
) -> None:
    namespace, name = model_name.split("/")
    prompt_id = f"prm_01J0000000000000000LIST{index}"
    version_id = f"rev_01J0000000000000000LIST{index}"

    await seed_prompt(migrate_engine, prompt_id=prompt_id, namespace=namespace, name=name)
    await seed_revision(
        migrate_engine,
        version_id=version_id,
        prompt_id=prompt_id,
        provider_config_id=CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
    )
    if released:
        await approve(migrate_engine, version_id)
        await release(migrate_engine, prompt_id, version_id)


async def _five_prompts(migrate_engine, scope: tuple[str, ...]) -> None:  # noqa: ANN001
    """Three released and two not, with the key scoped to whatever the test needs."""
    await seed_released_world(migrate_engine, scope=scope)
    await _prompt(migrate_engine, RELEASED_TWO, 1, released=True)
    await _prompt(migrate_engine, RELEASED_THREE, 2, released=True)
    await _prompt(migrate_engine, UNRELEASED_ONE, 3, released=False)
    await _prompt(migrate_engine, UNRELEASED_TWO, 4, released=False)


ALL_FIVE = (MODEL, RELEASED_TWO, RELEASED_THREE, UNRELEASED_ONE, UNRELEASED_TWO)


async def test_exactly_the_released_prompts_are_listed(api, migrate_engine) -> None:
    """The acceptance criterion: three released, two without a release, and the
    key may resolve all five."""
    await _five_prompts(migrate_engine, scope=ALL_FIVE)

    response = await call(api, "GET", "/models", headers=authorization())

    assert response.status_code == 200, response.body
    assert sorted(row["id"] for row in response.json()["data"]) == sorted(
        [MODEL, RELEASED_TWO, RELEASED_THREE]
    )


async def test_the_shape_is_openai_s_list_and_the_id_is_the_model_name(
    api, migrate_engine
) -> None:
    """`id` is what a consumer puts in the `model` field of their next request,
    so it has to be the model name and not a `prm_` identifier — a list whose ids
    are not callable is a list nobody can use."""
    await _five_prompts(migrate_engine, scope=ALL_FIVE)

    payload = (await call(api, "GET", "/models", headers=authorization())).json()

    assert payload["object"] == "list"
    entry = next(row for row in payload["data"] if row["id"] == MODEL)
    assert entry["object"] == "model"
    assert entry["prope"]["version_id"] == VERSION_ID
    assert entry["prope"]["revision_number"] == 1


async def test_the_keys_scope_filters_the_list(api, migrate_engine) -> None:
    """A-082's second half. A key that may resolve one of three released prompts
    sees one."""
    await _five_prompts(migrate_engine, scope=(RELEASED_TWO,))

    payload = (await call(api, "GET", "/models", headers=authorization())).json()

    assert [row["id"] for row in payload["data"]] == [RELEASED_TWO]


async def test_an_empty_scope_lists_nothing_at_all(api, migrate_engine) -> None:
    """Default-deny, and the same answer the call path gives. A key with no scope
    is a key that has been issued and not yet granted anything."""
    await _five_prompts(migrate_engine, scope=())

    payload = (await call(api, "GET", "/models", headers=authorization())).json()

    assert payload == {"object": "list", "data": []}


async def test_a_scope_naming_an_unreleased_prompt_does_not_list_it(
    api, migrate_engine
) -> None:
    """The two filters are AND, not OR. A key explicitly granted a prompt that
    has never been released still sees nothing — being granted something is not
    the same as it being in production."""
    await _five_prompts(migrate_engine, scope=(UNRELEASED_ONE, UNRELEASED_TWO))

    payload = (await call(api, "GET", "/models", headers=authorization())).json()

    assert payload["data"] == []


async def test_the_list_carries_no_prompt_body_and_no_owner(api, migrate_engine) -> None:
    """INT-010 returns three fields and this route adds two constants. A body
    here would put the prompt text on an endpoint every consumer polls — and the
    body is the asset the whole product exists to govern."""
    await _five_prompts(migrate_engine, scope=ALL_FIVE)

    body = (await call(api, "GET", "/models", headers=authorization())).body.decode()

    assert "You are a helpful assistant." not in body
    assert "owner" not in body
    assert "usr_" not in body


async def test_an_unknown_key_is_refused_and_reveals_no_names(api, migrate_engine) -> None:
    await _five_prompts(migrate_engine, scope=ALL_FIVE)

    response = await call(
        api,
        "GET",
        "/models",
        headers={"authorization": "Bearer prope_key_01J0000000000000000BOGUS_nope"},
    )

    assert response.status_code == 401
    assert MODEL not in response.body.decode()
