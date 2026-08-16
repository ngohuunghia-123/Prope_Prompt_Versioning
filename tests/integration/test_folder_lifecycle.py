"""Folders: create it before it holds anything, open it, name a derived one, delete it.

**The failure this file exists to catch is the one that made folders necessary.**
Before ``registry.folder``, a folder was derived by grouping prompts on
``namespace`` — so a folder with no prompts did not exist, and the registration
flow (create the folder, open it, add the first prompt) landed on a not-found at
step two. ``test_a_folder_with_no_prompts_is_listed`` is that step, asserted.

**Three shapes are load-bearing and none of them is arithmetic.**

*The union.* The list is declared rows FULL OUTER JOINed with observed
namespaces. An inner join loses both halves; dropping either side loses one. Two
tests here hold the two halves apart — a folder with no prompts, and prompts with
no folder row.

*The counts are per-actor.* They run through ``visible_subject_filter``, so a
card cannot report the number of private prompts in a namespace whose contents it
would refuse to list. That is BR-01 in a place nobody would think to look for it,
which is why it is tested through a second actor rather than reasoned about.

*Delete counts without the filter.* Emptiness is a fact about the namespace, not
about the reader — so a caller who cannot see the prompts in a folder still may
not unname it. The two counts deliberately disagree, and
``test_delete_is_refused_while_prompts_carry_the_namespace`` holds the second
half, and ``test_the_counts_do_not_disclose_prompts_the_caller_cannot_see`` the
first.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.prompt_registry.domain import default_folder_color
from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import NAMESPACE, registry_api, seed_prompt, seed_revision

SESSION_ID = "ses_registry_folder_00000001"

COUNT_FOLDER_ROWS = text("SELECT count(*) FROM registry.folder")

READ_FOLDER = text("SELECT name, description, color FROM registry.folder WHERE slug = :slug")


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _signed_in(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, SESSION_ID)


async def _folders(api) -> list[dict]:  # noqa: ANN001
    response = await call(api, "GET", "/api/v1/folders", headers=_owner())
    assert response.status_code == 200, response.body
    return response.json()


def _by_slug(rows: list[dict], slug: str) -> dict:
    matched = [row for row in rows if row["slug"] == slug]
    assert matched, f"{slug!r} is not in {[row['slug'] for row in rows]}"
    return matched[0]


async def test_a_folder_with_no_prompts_is_listed(api, migrate_engine) -> None:
    """Step two of the registration flow: the folder you just made can be opened.

    This is the whole reason the table exists. A derived folder cannot be empty,
    so before this row a freshly created folder 404'd the moment somebody
    navigated into it.
    """
    await _signed_in(migrate_engine)

    created = await call(
        api,
        "POST",
        "/api/v1/folders",
        json_body={"slug": "ho-tro", "name": "Hỗ trợ khách hàng", "description": "Đội CS"},
        headers=_owner(),
    )
    assert created.status_code == 201, created.body
    assert created.json()["prompt_count"] == 0
    assert created.json()["declared"] is True

    listed = _by_slug(await _folders(api), "ho-tro")
    assert listed["name"] == "Hỗ trợ khách hàng"
    assert listed["description"] == "Đội CS"
    # Nobody picked a colour, so the server filled the hash the client would have
    # pre-selected. The two implementations agreeing is what keeps the swatch in
    # the dialog from being a different colour than the card that comes back.
    assert listed["color"] == default_folder_color("ho-tro")


async def test_a_namespace_with_no_row_is_still_a_folder(api, migrate_engine) -> None:
    """The other half of the union: prompts created through the API, never named."""
    await _signed_in(migrate_engine)
    await seed_prompt(migrate_engine)

    observed = _by_slug(await _folders(api), NAMESPACE)
    assert observed["declared"] is False
    assert observed["prompt_count"] == 1
    # Stand-ins, not prose anybody wrote — which is what `declared` lets the
    # client say out loud on the card.
    assert observed["name"] == "Support"
    assert observed["description"] == f"{NAMESPACE}/*"


async def test_create_is_refused_when_a_prompt_already_holds_the_namespace(
    api, migrate_engine
) -> None:
    """One refusal for both kinds of clash, because they are one fact to the author."""
    await _signed_in(migrate_engine)
    await seed_prompt(migrate_engine)

    refused = await call(
        api,
        "POST",
        "/api/v1/folders",
        json_body={"slug": NAMESPACE, "name": "Hỗ trợ"},
        headers=_owner(),
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "registry_folder_slug_taken"

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_FOLDER_ROWS) == 0


async def test_create_is_refused_twice_on_the_same_slug(api, migrate_engine) -> None:
    await _signed_in(migrate_engine)

    first = await call(
        api, "POST", "/api/v1/folders", json_body={"slug": "cs", "name": "CS"}, headers=_owner()
    )
    assert first.status_code == 201

    second = await call(
        api, "POST", "/api/v1/folders", json_body={"slug": "cs", "name": "CS 2"}, headers=_owner()
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "registry_folder_slug_taken"


async def test_patch_declares_an_observed_namespace(api, migrate_engine) -> None:
    """PATCH upserts, which is the only path from a derived folder to a named one.

    POST refuses this slug — the folder already exists to anyone looking at the
    grid — so if PATCH refused too, every namespace created through the API would
    be permanently stuck with a capitalised slug for a name.
    """
    await _signed_in(migrate_engine)
    await seed_prompt(migrate_engine)

    patched = await call(
        api,
        "PATCH",
        f"/api/v1/folders/{NAMESPACE}",
        json_body={"name": "Hỗ trợ khách hàng", "color": "#ef4444"},
        headers=_owner(),
    )
    assert patched.status_code == 200, patched.body
    assert patched.json()["declared"] is True
    assert patched.json()["name"] == "Hỗ trợ khách hàng"
    assert patched.json()["color"] == "#ef4444"
    # The prompt did not move: the folder is the same namespace, now labelled.
    assert patched.json()["prompt_count"] == 1

    async with migrate_engine.begin() as connection:
        row = (await connection.execute(READ_FOLDER, {"slug": NAMESPACE})).mappings().one()
    assert row["name"] == "Hỗ trợ khách hàng"


async def test_patch_leaves_the_fields_it_was_not_given(api, migrate_engine) -> None:
    await _signed_in(migrate_engine)
    await call(
        api,
        "POST",
        "/api/v1/folders",
        json_body={"slug": "cs", "name": "CS", "description": "Đội CS", "color": "#10b981"},
        headers=_owner(),
    )

    patched = await call(
        api, "PATCH", "/api/v1/folders/cs", json_body={"color": "#ec4899"}, headers=_owner()
    )
    assert patched.status_code == 200
    assert patched.json()["color"] == "#ec4899"
    assert patched.json()["name"] == "CS"
    assert patched.json()["description"] == "Đội CS"


async def test_the_slug_cannot_be_patched(api, migrate_engine) -> None:
    """A-021: the slug is half the model name, so nothing may move it.

    ``extra="forbid"`` is what turns the attempt into a 422 rather than a silent
    no-op, and a silent no-op is the shape that would let somebody believe the
    rename worked.
    """
    await _signed_in(migrate_engine)
    await call(api, "POST", "/api/v1/folders", json_body={"slug": "cs", "name": "CS"}, headers=_owner())

    refused = await call(
        api, "PATCH", "/api/v1/folders/cs", json_body={"slug": "support"}, headers=_owner()
    )
    assert refused.status_code == 422


async def test_delete_removes_the_label_and_leaves_the_prompts(api, migrate_engine) -> None:
    """A declared folder emptied of prompts deletes; an occupied one does not."""
    await _signed_in(migrate_engine)
    await call(api, "POST", "/api/v1/folders", json_body={"slug": "cs", "name": "CS"}, headers=_owner())

    deleted = await call(api, "DELETE", "/api/v1/folders/cs", headers=_owner())
    assert deleted.status_code == 204

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_FOLDER_ROWS) == 0
    assert all(row["slug"] != "cs" for row in await _folders(api))


async def test_delete_is_refused_while_prompts_carry_the_namespace(api, migrate_engine) -> None:
    """Refused for a UX reason, not an integrity one — and the count says why."""
    await _signed_in(migrate_engine)
    await seed_prompt(migrate_engine)
    await call(
        api, "PATCH", f"/api/v1/folders/{NAMESPACE}", json_body={"name": "Hỗ trợ"}, headers=_owner()
    )

    refused = await call(api, "DELETE", f"/api/v1/folders/{NAMESPACE}", headers=_owner())
    assert refused.status_code == 409
    body = refused.json()["error"]
    assert body["code"] == "registry_folder_not_empty"
    assert body["details"]["prompt_count"] == 1

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_FOLDER_ROWS) == 1


async def test_delete_of_an_unknown_slug_is_idempotent(api, migrate_engine) -> None:
    """A slug with no row is already in the state the caller asked for.

    Not a 404: nothing distinguishes "never named" from "already deleted", and
    reporting the difference would be reporting one the caller cannot act on.
    """
    await _signed_in(migrate_engine)

    response = await call(api, "DELETE", "/api/v1/folders/never-existed", headers=_owner())
    assert response.status_code == 204


async def test_the_counts_fold_the_latest_revision(api, migrate_engine) -> None:
    """Approved / in review / draft come off the latest revision, released off the pointer.

    Deriving these client-side capped every count at one page of ``GET /prompts``
    and could only ever produce ``draft`` and ``inUse``, so the two middle stat
    cards on the folder screen were permanently zero.
    """
    await _signed_in(migrate_engine)
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, status="In review")

    counts = _by_slug(await _folders(api), NAMESPACE)
    assert counts["prompt_count"] == 1
    assert counts["in_review_count"] == 1
    assert counts["draft_count"] == 0
    assert counts["approved_count"] == 0


async def test_the_folder_writes_append_no_history_event(api, migrate_engine) -> None:
    """The declared exception to ``commands.py``'s opening sentence, asserted.

    A folder holds no revision, cannot be approved and cannot serve a call, so it
    is outside what the history vocabulary carries. If somebody later decides it
    should be recorded, this test is what tells them the omission was a decision.
    """
    await _signed_in(migrate_engine)
    async with migrate_engine.begin() as connection:
        before = await connection.scalar(text("SELECT count(*) FROM history.history_event"))

    await call(api, "POST", "/api/v1/folders", json_body={"slug": "cs", "name": "CS"}, headers=_owner())
    await call(api, "PATCH", "/api/v1/folders/cs", json_body={"name": "CS 2"}, headers=_owner())
    await call(api, "DELETE", "/api/v1/folders/cs", headers=_owner())

    async with migrate_engine.begin() as connection:
        after = await connection.scalar(text("SELECT count(*) FROM history.history_event"))
    assert after == before


async def test_a_malformed_slug_is_refused_at_the_edge(api, migrate_engine) -> None:
    """``NAME_PATTERN`` at the edge as well as in the CHECK, so the author reads the field name."""
    await _signed_in(migrate_engine)

    for slug in ("Hỗ trợ", "-leading", "UPPER", "a" * 64):
        response = await call(
            api, "POST", "/api/v1/folders", json_body={"slug": slug, "name": "x"}, headers=_owner()
        )
        assert response.status_code == 422, slug


async def test_folders_need_a_session(api) -> None:
    for method, path in (
        ("GET", "/api/v1/folders"),
        ("POST", "/api/v1/folders"),
        ("PATCH", "/api/v1/folders/cs"),
        ("DELETE", "/api/v1/folders/cs"),
    ):
        response = await call(api, method, path, json_body={} if method != "GET" else None)
        assert response.status_code == 401, f"{method} {path}"


async def test_the_counts_do_not_disclose_prompts_the_caller_cannot_see(
    api, migrate_engine
) -> None:
    """BR-01, on a folder card. A count is a disclosure if it ignores visibility.

    ``ADMIN_ID`` owns a **private** prompt in ``support``. The second member holds
    no role binding, so ``visible_subject_filter`` hands back an empty set and
    every count they read must be zero — a card saying "1 prompt" over a list
    showing none is exactly the confirmation that not-found exists to withhold.

    Two different absences are asserted, because they are different rows:

    * the *declared* folder is still listed, at zero. Folder names are workspace
      organisation, and an empty folder must be visible or the registration flow
      breaks for everyone but its author;
    * the *undeclared* namespace vanishes entirely. It had no row of its own —
      it existed only as an aggregate over prompts — so with the prompts filtered
      out there is nothing left to render.
    """
    await _signed_in(migrate_engine)
    await seed_prompt(migrate_engine)
    await seed_prompt(
        migrate_engine,
        prompt_id="prm_01J000000000000000HIDDEN",
        namespace="undeclared",
        name="hidden",
    )
    await call(
        api,
        "PATCH",
        f"/api/v1/folders/{NAMESPACE}",
        json_body={"name": "Hỗ trợ"},
        headers=_owner(),
    )

    stranger_session = "ses_registry_folder_00000002"
    stranger = "usr_01J00000000000000STRANGER"
    await seed_user(migrate_engine, user_id=stranger, email="stranger@example.test")
    await seed_member(migrate_engine, user_id=stranger)
    await seed_session(migrate_engine, stranger_session, user_id=stranger)
    headers = {"cookie": f"prope_session={stranger_session}"}

    listed = await call(api, "GET", "/api/v1/folders", headers=headers)
    assert listed.status_code == 200, listed.body
    rows = listed.json()

    assert _by_slug(rows, NAMESPACE)["prompt_count"] == 0
    assert all(row["slug"] != "undeclared" for row in rows)


async def test_a_reviewer_can_read_the_folder_grid(api, migrate_engine) -> None:
    """``FOLDER_LIST`` declares ``prompt.read``, and this is why.

    The folder grid *is* the prompts screen. A Reviewer holds ``prompt.read`` and
    ``revision.approve`` and no authoring permission at all, so mapping the read
    onto ``prompt.create`` alongside the three writes would have handed them a
    blank registry.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Reviewer")
    await seed_session(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)

    listed = await call(api, "GET", "/api/v1/folders", headers=_owner())
    assert listed.status_code == 200, listed.body
    assert _by_slug(listed.json(), NAMESPACE)["prompt_count"] == 1

    refused = await call(
        api, "POST", "/api/v1/folders", json_body={"slug": "cs", "name": "CS"}, headers=_owner()
    )
    assert refused.status_code == 403
    assert refused.json()["error"]["details"]["permission"] == "prompt.create"
