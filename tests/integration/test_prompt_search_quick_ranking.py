"""``GET /api/v1/prompts/search?type=quick`` — the default search mode, ranked.

Two defects live here, both measured before they were fixed
(`eval/result/*-baseline.json`, and `eval/README.md` for how to re-run it):

**A multi-word query matched nothing.** The whole query string went into one
``LIKE '%…%'``, so it had to appear verbatim in a document. Over the golden set
every multi-word query returned zero results — hit@1, recall and MRR all exactly
0.000, on the mode a person reaches first.

**A single-word query was unranked.** "SQL" returned five prompts in
``prompt_id`` order and the SQL assistant was not among the first three. There
was no scoring step: matching was the whole algorithm.

Driven over the real ASGI stack, against real rows, with the trigger-maintained
``search_text`` doing the matching — no embedding is involved in this path at
all, which is why these tests need no stub.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.errors import install_error_envelope
from prope.prompt_search.api import router as prompt_search_router
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import seed_prompt, seed_revision

SESSION_ID = "ses_search_quick_000000001"
SEARCH = "/api/v1/prompts/search"

KUBERNETES = "prm_01J00000000000000QUICK01"
SQL = "prm_01J00000000000000QUICK02"
WRITER = "prm_01J00000000000000QUICK03"
NOISE = "prm_01J00000000000000QUICK04"


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    from fastapi import FastAPI

    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(prompt_search_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


async def _library(migrate_engine, role: str | None = "Owner") -> None:  # noqa: ANN001
    """Four prompts, workspace-visible, each with a body the trigger indexes.

    Bodies matter: ``search_text`` carries the latest revision's body, and the
    lexical path is the only one under test here.

    ``role=None`` is what makes a visibility assertion mean anything: the Owner
    role grants ``prompt.read`` workspace-wide, so ``visible_subject_filter``
    answers ``all`` and there is no filtering left to observe.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    if role is not None:
        await seed_role(migrate_engine, role)
    await seed_session(migrate_engine, SESSION_ID)

    await seed_prompt(
        migrate_engine,
        KUBERNETES,
        name="kubernetes-specialist",
        title="Kubernetes platform engineer",
        purpose="Imported prompt library entry",
        access_level="workspace",
    )
    await seed_revision(
        migrate_engine,
        version_id="rev_quick_kubernetes",
        prompt_id=KUBERNETES,
        body="You are a Kubernetes specialist. You design clusters, harden workloads and tune orchestration.",
    )

    await seed_prompt(
        migrate_engine,
        SQL,
        name="sql-assistant",
        title="SQL assistant",
        purpose="Imported prompt library entry",
        access_level="workspace",
    )
    await seed_revision(
        migrate_engine,
        version_id="rev_quick_sql",
        prompt_id=SQL,
        body="You are a senior database engineer. You write SQL, design schemas and tune slow queries.",
    )

    # Mentions SQL once, in passing. The ranking question is whether it can
    # outrank the prompt that is ABOUT SQL — under the old code, it could.
    await seed_prompt(
        migrate_engine,
        WRITER,
        name="technical-writer",
        title="Technical writer",
        purpose="Imported prompt library entry",
        access_level="workspace",
    )
    await seed_revision(
        migrate_engine,
        version_id="rev_quick_writer",
        prompt_id=WRITER,
        body="You write developer documentation. Examples may include SQL snippets where relevant.",
    )

    await seed_prompt(
        migrate_engine,
        NOISE,
        name="game-designer",
        title="Game designer",
        purpose="Imported prompt library entry",
        access_level="workspace",
    )
    await seed_revision(
        migrate_engine,
        version_id="rev_quick_noise",
        prompt_id=NOISE,
        body="You design game loops, progression curves and player motivation systems.",
    )


async def test_a_multi_word_query_finds_the_prompt(api, migrate_engine) -> None:
    """The headline defect. 54 characters of question, matched as one substring.

    Nothing in any document contains this phrase verbatim, and under the previous
    implementation that meant zero results — for the search mode that runs by
    default, on every query longer than one word.
    """
    await _library(migrate_engine)

    response = await call(
        api,
        "GET",
        SEARCH,
        params={"q": "kubernetes cluster hardening and workload orchestration", "type": "quick"},
        headers=_owner(),
    )

    assert response.status_code == 200, response.body
    found = [row["prompt_id"] for row in response.json()["prompts"]]
    assert found[:1] == [KUBERNETES]


async def test_the_best_match_is_first_and_not_merely_present(api, migrate_engine) -> None:
    """The second defect: matching without scoring.

    Both the SQL assistant and the technical writer contain "SQL". Only one of
    them is about it, and the difference is how much of the query's distinctive
    weight each accounts for — the technical writer matches one term of two.
    """
    await _library(migrate_engine)

    response = await call(api, "GET", SEARCH, params={"q": "sql schemas", "type": "quick"}, headers=_owner())

    assert response.status_code == 200, response.body
    found = [row["prompt_id"] for row in response.json()["prompts"]]
    assert found[0] == SQL


async def test_a_single_word_query_still_matches_everything_containing_it(
    api, migrate_engine
) -> None:
    """One word is the whole question, so corroboration cannot be required.

    This is the case the keyword path exists for — an identifier, an error code,
    a product name — and the rule that keeps two ordinary words from passing as
    a match must not swallow it.
    """
    await _library(migrate_engine)

    response = await call(api, "GET", SEARCH, params={"q": "sql", "type": "quick"}, headers=_owner())

    assert response.status_code == 200, response.body
    found = {row["prompt_id"] for row in response.json()["prompts"]}
    assert {SQL, WRITER} <= found
    assert NOISE not in found


async def test_a_query_with_no_usable_terms_falls_back_to_the_substring_match(
    api, migrate_engine
) -> None:
    """Two characters is below the shortest term worth probing.

    Tokenising leaves nothing, and the honest fallback is the behaviour this
    route always had rather than an empty list: the person typed something.
    """
    await _library(migrate_engine)

    response = await call(api, "GET", SEARCH, params={"q": "ku", "type": "quick"}, headers=_owner())

    assert response.status_code == 200, response.body
    assert KUBERNETES in {row["prompt_id"] for row in response.json()["prompts"]}


async def test_an_out_of_scope_query_returns_nothing(api, migrate_engine) -> None:
    """Nothing in the corpus is about this, and the honest answer is an empty list."""
    await _library(migrate_engine)

    response = await call(
        api,
        "GET",
        SEARCH,
        params={"q": "knitting a cable sweater in worsted yarn", "type": "quick"},
        headers=_owner(),
    )

    assert response.status_code == 200, response.body
    assert response.json()["prompts"] == []


async def test_a_prompt_the_actor_cannot_see_is_never_ranked(api, migrate_engine) -> None:
    """Ranking changed; the visibility filter it runs behind did not.

    The private prompt is the best lexical match in the workspace, which is what
    makes this worth asserting after a ranking rewrite: the filter is applied in
    the repository, before anything is scored.

    No role binding, deliberately — an Owner reads the whole workspace by design
    (`visible_subject_filter` answers ``all``), so this assertion would pass
    against one without the filter existing at all. The first version of this
    test did seed a role, and passed for that reason.
    """
    await _library(migrate_engine, role=None)
    await seed_prompt(
        migrate_engine,
        "prm_01J00000000000000QUICK05",
        name="secret-kubernetes",
        title="Kubernetes cluster hardening playbook",
        owner_id="usr_someone_else",
        access_level="private",
    )

    response = await call(api, "GET", SEARCH, params={"q": "kubernetes cluster", "type": "quick"}, headers=_owner())

    assert response.status_code == 200, response.body
    found = {row["prompt_id"] for row in response.json()["prompts"]}
    assert "prm_01J00000000000000QUICK05" not in found
