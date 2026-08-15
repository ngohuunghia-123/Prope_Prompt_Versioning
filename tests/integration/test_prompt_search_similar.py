"""``POST /api/v1/prompts/search/similar`` — the import screen's duplicate check.

Driven over the real ASGI stack rather than against the repository, because what
is under test here is the half the repository cannot answer: the route refuses
without a session, it holds the caller to the 32 KiB body ceiling, and it filters
by what the actor may see rather than by what the workspace contains.

The embedding call is the one thing stubbed. ``semantic_search`` reaches OpenAI
for a vector; the ranking underneath it is pgvector against real rows, and that
is what these tests exercise.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.canonical_prompt import MAX_CANONICAL_CHARACTERS
from prope.errors import install_error_envelope
from prope.prompt_search import repository
from prope.prompt_search.api import router as prompt_search_router
from prope.session_auth import (
    install_session_authenticator,
    reset_session_authenticator,
)
from tests.access_control import (
    ADMIN_ID,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import seed_prompt
from tests.unit import WORKSPACE_A

SESSION_ID = "ses_search_similar_00000001"

CLOSE_PROMPT = "prm_01J0000000000000SIMILAR1"
DISTANT_PROMPT = "prm_01J0000000000000SIMILAR2"
OTHERS_PROMPT = "prm_01J0000000000000SIMILAR3"

SIMILAR = "/api/v1/prompts/search/similar"


def _embedding(head: float) -> list[float]:
    return [head, 1.0 - head, *([0.0] * 1534)]


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    """prompt-search's router with the real session boundary, as `prope.app` mounts it.

    No ``dependency_overrides``: the 401 this file asserts is only meaningful if
    the session it is missing would have come from a live row.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(prompt_search_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


@pytest.fixture
def stub_embedding(monkeypatch: pytest.MonkeyPatch):
    """One vector for whatever text arrives, so the ranking is the only variable.

    Patched on ``repository`` and on the search module's own binding, because
    ``agent.search`` calls ``repository.get_or_create_embedding`` through the
    module and ``get_embedding_client`` by name.
    """
    from prope.prompt_search.agent import search as search_module

    monkeypatch.setattr(search_module, "get_embedding_client", AsyncMock(return_value=object()))
    monkeypatch.setattr(repository, "get_or_create_embedding", AsyncMock(return_value=(_embedding(1.0), False)))


async def _seed_index(migrate_engine, prompt_id: str, version_id: str, embedding: list[float]):  # noqa: ANN001
    vector = "[" + ",".join(str(value) for value in embedding) + "]"
    async with migrate_engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO search.prompt_search_index (
                    id, prompt_id, version_id, workspace_id, keywords, topics, entities,
                    variations, language, role, content_embedding, embedding_model,
                    is_bilingual, indexed_at, indexed_by
                ) VALUES (
                    :id, :prompt_id, :version_id, :workspace_id, ARRAY['refund'],
                    ARRAY['support'], '{}', '{"en": [], "vi": []}'::jsonb,
                    ARRAY['en'], 'released', CAST(:embedding AS vector), 'text-embedding-3-small',
                    false, NOW(), :indexed_by
                )
                """
            ),
            {
                "id": f"psi_{prompt_id}",
                "prompt_id": prompt_id,
                "version_id": version_id,
                "workspace_id": WORKSPACE_A,
                "embedding": vector,
                "indexed_by": ADMIN_ID,
            },
        )


async def _account(migrate_engine, role: str | None = "Owner") -> None:  # noqa: ANN001
    """A signed-in member, with a role binding unless a test asks for none.

    ``role=None`` is what makes the visibility assertion below possible. The
    Owner role grants ``prompt.read`` workspace-wide, so
    ``visible_subject_filter`` answers ``all`` and there is no filtering left to
    observe. An unbound member falls to the ``ids`` mode with an empty grant
    list, where what they see is exactly their own prompts plus the
    workspace-visible ones — which is the boundary worth testing.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    if role is not None:
        await seed_role(migrate_engine, role)
    await seed_session(migrate_engine, SESSION_ID)


async def test_an_unindexed_prompt_is_still_found(api, migrate_engine, stub_embedding) -> None:
    """The index is an accelerator, not a gate.

    Nothing here has ever been indexed, and the prompt is returned anyway —
    matched through the registry's trigram document, which the trigger keeps
    filled with the title, purpose, tags and latest body. The alternative, which
    this route used to do, was to answer with an empty list; on the import screen
    that reads as *no duplicates* and is the one wrong answer a duplicate check
    can give.

    `is_indexed` and `matched_fields` are what keep it honest: found, but not
    found semantically.
    """
    await _account(migrate_engine)
    await seed_prompt(migrate_engine, CLOSE_PROMPT, name="not-indexed")

    response = await call(api, "POST", SIMILAR, json_body={"text": "Classify the refund request."}, headers=_owner())

    assert response.status_code == 200, response.body
    found = response.json()["prompts"]
    assert [row["prompt_id"] for row in found] == [CLOSE_PROMPT]
    assert found[0]["is_indexed"] is False
    assert found[0]["matched_fields"] == ["lexical"]
    # Below what a vector match can score, because it is weaker evidence.
    assert 0 < found[0]["similarity"] <= 0.6


async def test_a_prompt_sharing_nothing_with_the_query_is_absent(
    api, migrate_engine, stub_embedding
) -> None:
    """Reaching every prompt is not the same as returning every prompt.

    The lexical leg needs at least one distinctive term in common. Without this
    the "search everything" change would degrade into "list everything", and a
    dialog offering three arbitrary prompts as near-duplicates is worse than one
    offering none.
    """
    await _account(migrate_engine)
    await seed_prompt(migrate_engine, CLOSE_PROMPT, name="not-indexed")

    response = await call(
        api,
        "POST",
        SIMILAR,
        json_body={"text": "Compose a haiku about migrating seabirds in autumn."},
        headers=_owner(),
    )

    assert response.status_code == 200, response.body
    assert response.json()["prompts"] == []


async def test_indexed_prompts_come_back_ranked_with_a_similarity(api, migrate_engine, stub_embedding) -> None:
    """The nearer vector first, and every row carries the score the dialog shows."""
    await _account(migrate_engine)
    await seed_prompt(migrate_engine, CLOSE_PROMPT, name="close-one", title="Refund classifier")
    await seed_prompt(migrate_engine, DISTANT_PROMPT, name="distant-one", title="Something else")
    await _seed_index(migrate_engine, CLOSE_PROMPT, "rev_close", _embedding(1.0))
    await _seed_index(migrate_engine, DISTANT_PROMPT, "rev_far", _embedding(0.4))

    response = await call(api, "POST", SIMILAR, json_body={"text": "Classify the refund request."}, headers=_owner())

    assert response.status_code == 200, response.body
    body = response.json()
    assert [row["prompt_id"] for row in body["prompts"]] == [CLOSE_PROMPT, DISTANT_PROMPT]
    assert body["prompts"][0]["similarity"] > body["prompts"][1]["similarity"]
    assert body["search_type"] == "ai"
    # A top-N probe feeding a decision dialog, not a page of results.
    assert body["next_cursor"] is None


async def test_the_limit_bounds_what_the_dialog_has_to_render(api, migrate_engine, stub_embedding) -> None:
    """Three is the default because the screen shows at most three."""
    await _account(migrate_engine)
    await seed_prompt(migrate_engine, CLOSE_PROMPT, name="close-one")
    await seed_prompt(migrate_engine, DISTANT_PROMPT, name="distant-one")
    await _seed_index(migrate_engine, CLOSE_PROMPT, "rev_close", _embedding(1.0))
    await _seed_index(migrate_engine, DISTANT_PROMPT, "rev_far", _embedding(0.9))

    response = await call(api, "POST", SIMILAR, json_body={"text": "anything", "limit": 1}, headers=_owner())

    assert response.status_code == 200, response.body
    assert len(response.json()["prompts"]) == 1


async def test_a_prompt_the_actor_cannot_see_is_not_ranked(api, migrate_engine, stub_embedding) -> None:
    """BR-01 survives the duplicate check.

    A private prompt owned by somebody else is indexed and sits at the *nearest*
    vector, so a route that ranked before it filtered would put its title and
    purpose in front of an actor who may not read it — a disclosure wearing a
    convenience's clothes.

    The actor holds no role binding on purpose: an Owner reads the whole
    workspace by design, and asserting the filter against one would assert
    nothing.
    """
    await _account(migrate_engine, role=None)
    await seed_prompt(migrate_engine, CLOSE_PROMPT, name="mine")
    await seed_prompt(migrate_engine, OTHERS_PROMPT, name="theirs", owner_id="usr_someone_else", access_level="private")
    await _seed_index(migrate_engine, CLOSE_PROMPT, "rev_mine", _embedding(0.5))
    await _seed_index(migrate_engine, OTHERS_PROMPT, "rev_theirs", _embedding(1.0))

    response = await call(api, "POST", SIMILAR, json_body={"text": "anything"}, headers=_owner())

    assert response.status_code == 200, response.body
    assert [row["prompt_id"] for row in response.json()["prompts"]] == [CLOSE_PROMPT]


async def test_an_unreachable_embedding_provider_is_a_503_and_never_an_empty_list(
    api, migrate_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one failure mode where answering *"nothing found"* would be a lie.

    An OpenAI-compatible gateway that does not serve ``/embeddings`` answers 404,
    and the client raises. Two wrong ways to handle that: let it become a 500,
    which tells the caller nothing they can act on, or swallow it and return the
    empty list, which the import screen would render as *"no near-matches"* — a
    duplicate check reporting a clean result for a check that never ran.

    So: 503, and the import screen says the check was unavailable.
    """
    from openai import NotFoundError

    await _account(migrate_engine)
    from prope.prompt_search.agent import search as search_module

    monkeypatch.setattr(search_module, "get_embedding_client", AsyncMock(return_value=object()))
    monkeypatch.setattr(
        repository,
        "get_or_create_embedding",
        AsyncMock(
            side_effect=NotFoundError(
                "Not found", response=httpx.Response(404, request=httpx.Request("POST", "http://gateway/v1/embeddings")), body=None
            )
        ),
    )

    response = await call(api, "POST", SIMILAR, json_body={"text": "anything"}, headers=_owner())

    assert response.status_code == 503, response.body
    assert "prompts" not in response.json()


async def test_it_refuses_without_a_session(api, migrate_engine) -> None:
    """401 and the machine code the SPA routes to the sign-in screen on."""
    await _account(migrate_engine)

    response = await call(api, "POST", SIMILAR, json_body={"text": "anything"})

    assert response.status_code == 401
    assert response.code == "session_required"


async def test_it_refuses_a_body_over_the_revision_ceiling(api, migrate_engine) -> None:
    """The same 32 KiB a revision body and a conversion source are held to.

    Refused at the schema rather than truncated: a duplicate check that silently
    embedded the first half of a prompt would answer a question nobody asked.
    """
    await _account(migrate_engine)

    response = await call(
        api,
        "POST",
        SIMILAR,
        json_body={"text": "x" * (MAX_CANONICAL_CHARACTERS + 1)},
        headers=_owner(),
    )

    assert response.status_code == 422, response.body


async def test_it_refuses_an_empty_body(api, migrate_engine) -> None:
    """An embedding of the empty string ranks everything and means nothing."""
    await _account(migrate_engine)

    response = await call(api, "POST", SIMILAR, json_body={"text": ""}, headers=_owner())

    assert response.status_code == 422, response.body
