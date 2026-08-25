"""AC-3 and BR-01 — a private prompt is absent, and its absence is indistinguishable.

Two claims that look like one and are not:

* **It does not appear.** B searching A's exact title gets nothing back, because
  the visibility filter is in the repository's ``WHERE`` clause and not in a
  per-row check a handler could skip (A-118, T-019).
* **Its absence says nothing.** A direct ``GET`` by its id returns the SAME
  BYTES as a ``GET`` for an id that never existed. A ``403`` would confirm the
  prompt exists, which is the leak BR-01 is about and the one most likely to end
  a pilot — because it is discovered by the person whose prompt leaked.

The second is asserted as byte equality of the two responses rather than as two
separate ``== 404`` checks, because two 404s with different bodies is exactly the
oracle this is meant to close.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.access_control import (
    ADMIN_ID,
    MEMBER_ID,
    seed_grant,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, registry_api, seed_prompt, seed_revision

OWNER_SESSION = "ses_registry_private_owner01"

COLLEAGUE_SESSION = "ses_registry_private_other01"

#: A ``prm_`` id with the right shape that no row carries. The control for every
#: not-found assertion below: whatever the API says about this is what it must
#: also say about a prompt the actor may not see.
NONEXISTENT = "prm_01J000000000000000MISSING"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _colleague() -> dict[str, str]:
    return {"cookie": f"prope_session={COLLEAGUE_SESSION}"}


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={OWNER_SESSION}"}


async def _a_private_prompt_and_a_colleague_with_no_role(migrate_engine) -> None:  # noqa: ANN001
    """The colleague holds a MEMBERSHIP and no role binding.

    That is the shape BR-01 is about: somebody who is legitimately in the
    workspace, authenticated, and entitled to nothing in particular. A colleague
    with the Viewer role would hold ``prompt.read`` workspace-wide and
    ``visible_subject_filter`` would answer ``all`` — which is a different test.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, OWNER_SESSION)

    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_session(migrate_engine, COLLEAGUE_SESSION, user_id=MEMBER_ID)

    await seed_prompt(migrate_engine, title="Refund classifier", access_level="private")
    await seed_revision(migrate_engine, body="A body nobody else may read.")


async def test_a_private_prompt_is_absent_from_a_colleagues_search(
    api, migrate_engine
) -> None:
    """AC-3's first half, searched by its EXACT title."""
    await _a_private_prompt_and_a_colleague_with_no_role(migrate_engine)

    theirs = await call(
        api,
        "GET",
        "/api/v1/prompts",
        params={"q": "Refund classifier"},
        headers=_colleague(),
    )
    assert theirs.status_code == 200
    assert theirs.json() == []

    mine = await call(
        api,
        "GET",
        "/api/v1/prompts",
        params={"q": "Refund classifier"},
        headers=_owner(),
    )
    assert [row["prompt_id"] for row in mine.json()] == [PROMPT_ID]


async def test_a_direct_read_is_byte_identical_to_a_nonexistent_id(
    api, migrate_engine
) -> None:
    """AC-3's second half. Not two 404s — the SAME 404.

    ``request_id`` differs by construction (it is minted per refusal, which is
    the point of it), so the comparison is over the rest of the envelope.
    """
    await _a_private_prompt_and_a_colleague_with_no_role(migrate_engine)

    hidden = await call(api, "GET", f"/api/v1/prompts/{PROMPT_ID}", headers=_colleague())
    missing = await call(api, "GET", f"/api/v1/prompts/{NONEXISTENT}", headers=_colleague())

    assert hidden.status_code == missing.status_code == 404

    def without_request_id(response) -> dict:  # noqa: ANN001
        error = dict(response.json()["error"])
        error.pop("request_id")
        return error

    assert without_request_id(hidden) == without_request_id(missing)
    assert without_request_id(hidden)["code"] == "not_found"


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/api/v1/prompts/{prompt_id}", None),
        ("PATCH", "/api/v1/prompts/{prompt_id}", {"title": "mine now"}),
        ("POST", "/api/v1/prompts/{prompt_id}/retire", None),
        ("GET", "/api/v1/prompts/{prompt_id}/revisions", None),
        # **A canonical body, because an invalid one never reaches the check.**
        # This case sent `{"body": "x"}`, which fails the route's schema and is
        # refused 422 before authorisation runs at all — so the one thing this
        # test exists to assert about `POST /revisions`, that an invisible prompt
        # refuses as not-found rather than forbidden, was not being asserted for
        # this route. The body has to be valid for the request to get far enough
        # to be refused for the right reason.
        (
            "POST",
            "/api/v1/prompts/{prompt_id}/revisions",
            {"body": "<instructions>x</instructions>", "change_summary": "y"},
        ),
        ("GET", "/api/v1/prompts/{prompt_id}/activity", None),
    ],
)
async def test_every_by_id_route_refuses_as_not_found(
    api, migrate_engine, method: str, path: str, body: dict | None
) -> None:
    """The rule holds on EVERY route, not only the read.

    A ``PATCH`` that answered ``403`` would confirm the prompt exists just as
    loudly as a ``GET`` that did — and a write route is the one somebody adds
    later without thinking about the refusal shape. Parametrised so a new route
    is one line here rather than a decision nobody revisits.
    """
    await _a_private_prompt_and_a_colleague_with_no_role(migrate_engine)

    response = await call(
        api, method, path.format(prompt_id=PROMPT_ID), json_body=body, headers=_colleague()
    )

    assert response.status_code == 404, response.body
    assert response.code == "not_found"


async def test_a_revision_of_a_private_prompt_is_not_readable_by_its_own_id(
    api, migrate_engine
) -> None:
    """The route that authorises against a DIFFERENT row than the one in the path.

    ``GET /api/v1/revisions/{version_id}`` has to read the revision before it
    knows which prompt to ask about, so the body exists in memory at the moment
    permission is refused. What must not happen is that it reaches the response —
    and what must also not happen is a distinguishable refusal, since a version
    id is guessable in exactly the way a prompt id is.
    """
    await _a_private_prompt_and_a_colleague_with_no_role(migrate_engine)

    hidden = await call(
        api, "GET", "/api/v1/revisions/rev_01J000000000000000000REV1", headers=_colleague()
    )
    missing = await call(
        api, "GET", "/api/v1/revisions/rev_01J00000000000000MISSING", headers=_colleague()
    )

    assert hidden.status_code == missing.status_code == 404
    assert b"nobody else may read" not in hidden.body


async def test_a_grant_makes_it_visible_on_the_very_next_request(
    api, migrate_engine
) -> None:
    """ADR-0022 through this module's own reads. There is no cache to wait out.

    A-118's ``ids`` mode: the colleague holds no role, so access-control's filter
    answers with the granted ids and this module ORs in the two predicates it can
    evaluate itself. That composition is what the assertion is really about — a
    filter that dropped the ``ids`` disjunct would still pass every test above.
    """
    await _a_private_prompt_and_a_colleague_with_no_role(migrate_engine)

    before = await call(api, "GET", "/api/v1/prompts", headers=_colleague())
    assert before.json() == []

    await seed_grant(migrate_engine, "viewer")

    after = await call(api, "GET", "/api/v1/prompts", headers=_colleague())
    assert [row["prompt_id"] for row in after.json()] == [PROMPT_ID]

    detail = await call(api, "GET", f"/api/v1/prompts/{PROMPT_ID}", headers=_colleague())
    assert detail.status_code == 200


async def test_a_workspace_level_prompt_is_visible_without_a_grant(
    api, migrate_engine
) -> None:
    """BR-01's opt-out, and it is a READ and never more than a read.

    ``access_level = 'workspace'`` is the owner opening the prompt to their
    colleagues. It is one of the two predicates this module evaluates itself,
    because access-control may not read ``prompt_property`` (ADR-0020) — so a
    filter that relied on access-control alone would never surface these.
    """
    await _a_private_prompt_and_a_colleague_with_no_role(migrate_engine)

    opened = await call(
        api,
        "PATCH",
        f"/api/v1/prompts/{PROMPT_ID}",
        json_body={"access_level": "workspace"},
        headers=_owner(),
    )
    assert opened.status_code == 200, opened.body

    listed = await call(api, "GET", "/api/v1/prompts", headers=_colleague())
    assert [row["prompt_id"] for row in listed.json()] == [PROMPT_ID]

    refused = await call(
        api,
        "PATCH",
        f"/api/v1/prompts/{PROMPT_ID}",
        json_body={"title": "mine now"},
        headers=_colleague(),
    )
    assert refused.status_code == 403
    assert refused.code == "permission_denied"
    assert refused.json()["error"]["details"]["permission"] == "prompt.edit"


async def test_a_visible_prompt_refuses_with_the_permission_named(
    api, migrate_engine
) -> None:
    """A-116's other shape, and the reason both exist.

    Once somebody can already SEE the subject, hiding why they cannot act on it
    protects nothing and produces the worst support conversation in the product:
    a button that does nothing, with no way to find out what to ask for. The
    permission name is a machine string from the closed vocabulary, so it is safe
    in ``details`` under A-046 and the SPA can key a catalogue entry on it.
    """
    await _a_private_prompt_and_a_colleague_with_no_role(migrate_engine)
    await seed_grant(migrate_engine, "viewer")

    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/retire",
        headers=_colleague(),
    )

    assert response.status_code == 403
    assert response.json()["error"]["details"] == {
        "permission": "prompt.retire",
        "subject_type": "prompt",
    }


async def test_transferring_ownership_needs_more_than_prompt_edit(
    api, migrate_engine
) -> None:
    """A-007. An owner who could transfer could launder a prompt out of sight.

    The Owner role holds ``prompt.edit`` and deliberately not
    ``prompt.transfer_owner``, which is an Admin permission — and access-control's
    ``OWNER_ACTIONS`` leaves it out for the same reason. So the prompt's own owner
    is refused here, which is the case that proves the check is not
    ownership-shaped.
    """
    await _a_private_prompt_and_a_colleague_with_no_role(migrate_engine)

    response = await call(
        api,
        "PATCH",
        f"/api/v1/prompts/{PROMPT_ID}",
        json_body={"owner_id": MEMBER_ID},
        headers=_owner(),
    )

    assert response.status_code == 403
    assert response.json()["error"]["details"]["permission"] == "prompt.transfer_owner"

    unchanged = await call(api, "GET", f"/api/v1/prompts/{PROMPT_ID}", headers=_owner())
    assert unchanged.json()["owner_id"] == ADMIN_ID
