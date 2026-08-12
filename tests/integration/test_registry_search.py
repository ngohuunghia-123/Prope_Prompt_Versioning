"""AC-10 and AC-11 — what a match MEANS, asserted end to end.

**This file is the standing answer to "should we optimise this to tsvector".**
ADR-0048 chose a trigram index over a trigger-maintained document on three
specifics rather than on taste, and every one of them is a test below:

* ``tsvector`` cannot match INFIXES, so ``'thentic'`` would miss
  ``authentication``;
* its parser reads ``namespace/name`` as a FILE PATH, so ``'refund'`` would miss
  ``support/refund-classifier`` — the most likely query in this product;
* it needs a stemming dictionary named, and ADR-0053 leaves no bundled
  Vietnamese one to name (A-150).

The last two tests are AC-11, which is the CORPUS decision asserted: the document
holds the LATEST revision's body and EVERY revision's change summary, so a term
that appears only in an older body finds nothing while one in an older summary
finds the prompt. That asymmetry is deliberate — twenty bodies is a 20x index and
twenty 200-character summaries is about 0.6% of it — and it is the kind of thing
that gets "fixed" by somebody who thinks it is a bug.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import registry_api, seed_prompt, seed_revision

SESSION_ID = "ses_registry_search_000000001"

AUTH_PROMPT = "prm_01J00000000000000000AUTH1"

REFUND_PROMPT = "prm_01J000000000000000REFUND1"

VIETNAMESE_PROMPT = "prm_01J0000000000000000VIET1"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _corpus(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, SESSION_ID)

    await seed_prompt(
        migrate_engine,
        prompt_id=AUTH_PROMPT,
        namespace="platform",
        name="login-helper",
        title="Login helper",
        purpose="Explains sign-in problems",
    )
    await seed_revision(
        migrate_engine,
        version_id="rev_01J00000000000000000AUTH",
        prompt_id=AUTH_PROMPT,
        body="Diagnose the user's authentication failure and explain it plainly.",
        change_summary="first draft",
    )

    await seed_prompt(
        migrate_engine,
        prompt_id=REFUND_PROMPT,
        namespace="support",
        name="refund-classifier",
        title="Phân loại hoàn tiền",
        purpose="Decides whether a request is in policy",
    )
    await seed_revision(
        migrate_engine,
        version_id="rev_01J0000000000000000REFU",
        prompt_id=REFUND_PROMPT,
        body="Classify the request.",
        change_summary="first draft",
    )

    await seed_prompt(
        migrate_engine,
        prompt_id=VIETNAMESE_PROMPT,
        namespace="noi-bo",
        name="tom-tat",
        title="Tiêu đề tóm tắt",
        purpose="Tóm tắt nội dung cuộc trò chuyện",
    )


async def _search(api, term: str) -> list[str]:  # noqa: ANN001
    response = await call(
        api, "GET", "/api/v1/prompts", params={"q": term}, headers=_owner()
    )
    assert response.status_code == 200, response.body
    return [row["prompt_id"] for row in response.json()]


async def test_a_substring_of_a_word_in_the_body_matches(api, migrate_engine) -> None:
    """AC-10's first half. ``'thentic'`` is inside ``authentication`` and nowhere else.

    A case ``tsvector`` MISSES: it indexes lexemes, and ``thentic`` is not a
    prefix of one. A-013 says search is substring, and this is what that costs
    and what it buys.
    """
    await _corpus(migrate_engine)

    assert await _search(api, "thentic") == [AUTH_PROMPT]


async def test_a_substring_of_the_model_name_matches(api, migrate_engine) -> None:
    """AC-10's second half, and the most likely query in the product.

    ``tsvector``'s parser reads ``support/refund-classifier`` as a file path and
    emits it as ONE token, so ``'refund'`` would find nothing. The document holds
    the model name in three forms — joined, and each half — precisely so this
    query works from either direction.
    """
    await _corpus(migrate_engine)

    assert await _search(api, "refund") == [REFUND_PROMPT]


async def test_an_unaccented_term_matches_vietnamese_text(api, migrate_engine) -> None:
    """A-150. ``tieu de`` finds ``Tiêu đề``, folded inside the trigger.

    Only the derived ``search_text`` is folded — the title comes back from the
    API with its diacritics intact, which the second assertion is for. Folding at
    read time instead would mean the stored text and the indexed text disagreed
    about what they contain, and the index would win silently.
    """
    await _corpus(migrate_engine)

    assert await _search(api, "tieu de") == [VIETNAMESE_PROMPT]

    response = await call(
        api, "GET", f"/api/v1/prompts/{VIETNAMESE_PROMPT}", headers=_owner()
    )
    assert response.json()["title"] == "Tiêu đề tóm tắt"


async def test_case_is_folded_in_both_directions(api, migrate_engine) -> None:
    """``lower()`` on the document and on the term. Neither alone is enough."""
    await _corpus(migrate_engine)

    assert await _search(api, "AUTHENTICATION") == [AUTH_PROMPT]
    assert await _search(api, "PHÂN LOẠI") == [REFUND_PROMPT]


async def test_a_term_only_in_a_superseded_body_finds_nothing(api, migrate_engine) -> None:
    """AC-11's first half — the corpus decision, asserted.

    Only the LATEST body is in the document. A term that appeared in revision 1
    and was edited out in revision 2 is gone from search, and that is the choice
    ADR-0048 made deliberately: indexing every body is a 20x index at the load
    condition, on the largest column in the product.
    """
    await _corpus(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id="rev_01J0000000000000000AUTH2",
        prompt_id=AUTH_PROMPT,
        revision_number=2,
        body="Diagnose the sign-in problem and explain it plainly.",
        change_summary="reworded",
    )

    assert await _search(api, "thentic") == []
    assert await _search(api, "sign-in") == [AUTH_PROMPT]


async def test_a_term_in_an_older_change_summary_still_finds_the_prompt(
    api, migrate_engine
) -> None:
    """AC-11's second half, and what the corpus decision buys back.

    Every revision's change summary stays in the document, capped at 200
    characters each by A-050 — about 4 KiB for twenty of them, roughly 0.6% of
    what indexing the bodies would cost. What it recovers is the historical
    recall a register actually needs: *which prompt did we change for the refund
    thing*, in human-written text.
    """
    await _corpus(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id="rev_01J0000000000000000AUTH3",
        prompt_id=AUTH_PROMPT,
        revision_number=2,
        body="Nothing memorable here.",
        change_summary="softened the wording after the chargeback incident",
    )

    assert await _search(api, "chargeback") == [AUTH_PROMPT]


async def test_a_prompt_with_no_revisions_is_findable_by_its_title(
    api, migrate_engine
) -> None:
    """The BEFORE INSERT half of the property trigger.

    A prompt is registered before it is written, and a register that could not
    find a freshly registered prompt would fail at the first thing anybody tries.
    """
    await _corpus(migrate_engine)

    assert await _search(api, "tóm tắt") == [VIETNAMESE_PROMPT]
