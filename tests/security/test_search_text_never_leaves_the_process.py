"""T-017 — `search_text` is a second copy of the prompt body and must never be returned.

`prompt_property.search_text` holds the latest revision's body, on the table
**every list endpoint reads**. A ``SELECT *`` on the list path returns every body
in a page of titles, to a caller who asked for a column of titles.

**A whole-response scan, not a field allow-list**, and the difference is the
whole point. An allow-list checks the keys somebody thought of; the field a
future endpoint leaks it on is by definition one no allow-list mentions. So these
tests put a KNOWN, UNMISTAKABLE string in a prompt body and then assert it is
absent from the raw bytes of every response the module can produce — which
catches it under any key, at any nesting depth, in any endpoint added later.

Three layers keep it out and each is asserted here: the repository never selects
the column (``PROMPT_COLUMNS`` is written out and it is not in the list), the
domain type has no field that could hold it (``PromptRow``), and the response
models are explicit rather than ``from_attributes`` over a row.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.prompt_registry.domain import PromptRow
from prope.prompt_registry.repository import PROMPT_COLUMNS
from prope.prompt_registry.schemas import PromptRead
from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, registry_api, seed_prompt, seed_revision

SESSION_ID = "ses_registry_leak_0000000001"

#: Unmistakable, and deliberately not a word that could appear in a title, a
#: purpose, an id or an error message. If this string is anywhere in a response,
#: it came from a prompt body.
CANARY = "ZZCANARYZZ-do-not-leak-this-body-text"

#: Every route that reads. A leak needs only one of them, so the list is the
#: assertion rather than a convenience — adding a read route without adding a
#: line here is the gap this file exists to close.
READ_ROUTES = [
    ("GET", "/api/v1/prompts"),
    ("GET", f"/api/v1/prompts/{PROMPT_ID}"),
    ("GET", f"/api/v1/prompts/{PROMPT_ID}/revisions"),
    ("GET", f"/api/v1/prompts/{PROMPT_ID}/activity"),
]


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _a_prompt_whose_body_is_the_canary(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, body=f"You are a helper. {CANARY}")


@pytest.mark.parametrize("method,path", READ_ROUTES, ids=lambda value: str(value))
async def test_no_read_route_returns_the_prompt_body(
    api, migrate_engine, method: str, path: str
) -> None:
    """The scan. Raw bytes, so no key name and no nesting can hide it."""
    await _a_prompt_whose_body_is_the_canary(migrate_engine)

    response = await call(api, method, path, headers=_owner())

    assert response.status_code == 200, response.body
    assert CANARY.encode() not in response.body


@pytest.mark.parametrize("method,path", READ_ROUTES, ids=lambda value: str(value))
async def test_no_read_route_returns_a_field_called_search_text(
    api, migrate_engine, method: str, path: str
) -> None:
    """The narrower assertion beside the broad one.

    Kept because the two fail differently: the canary scan catches the column
    arriving under ANY name, and this catches the name arriving with a value the
    canary happens not to be in — an empty document on a prompt with no
    revisions, say.
    """
    await _a_prompt_whose_body_is_the_canary(migrate_engine)

    response = await call(api, method, path, headers=_owner())

    assert b"search_text" not in response.body


async def test_the_revision_detail_route_returns_the_body_and_that_is_correct(
    api, migrate_engine
) -> None:
    """The positive control, and it is not a hole.

    ``GET /api/v1/revisions/{version_id}`` is the DETAIL shape and the body is
    what it is for — a review screen with no prompt text is not a review screen.
    What T-017 forbids is the body arriving somewhere nobody asked for it, which
    is why the LIST shape (``RevisionSummaryRead``) omits it and this one does
    not.

    Without this test the file could pass by the module returning nothing at all.
    """
    await _a_prompt_whose_body_is_the_canary(migrate_engine)

    response = await call(
        api, "GET", "/api/v1/revisions/rev_01J000000000000000000REV1", headers=_owner()
    )

    assert response.status_code == 200, response.body
    assert CANARY in response.json()["body"]


def test_the_repository_never_selects_the_column() -> None:
    """Layer one: the column is not in the select list any row is built from.

    ``select(prompt_property)`` would have carried it, which is why
    ``PROMPT_COLUMNS`` is written out by hand. Asserted over the actual column
    objects rather than over source text.
    """
    assert "search_text" not in {column.name for column in PROMPT_COLUMNS}


def test_no_type_between_the_query_and_the_wire_can_hold_it() -> None:
    """Layers two and three: neither the domain row nor the response model has a
    field it could arrive in.

    ``PromptRead`` is checked for ``from_attributes`` as well as for its fields —
    a model that read attributes off a row would gain the column the day somebody
    added it back to the select list, silently.
    """
    assert "search_text" not in PromptRow.__slots__
    assert "search_text" not in PromptRead.model_fields
    assert PromptRead.model_config.get("from_attributes") is not True
