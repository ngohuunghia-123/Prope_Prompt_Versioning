"""AC-14 / AC-15 / ADR-0054. The trail is untouched, and nothing resolves the name.

**This is the whole of ADR-0054 and it is the one thing the tombstone must not
do.** No history row is deleted, no `actor_id` is nulled, blanked, re-pointed or
anonymised. `prope_app` could not do it if it tried — revision 0005 withholds
`DELETE` and `UPDATE` on `history.history_event` — but the point of asserting it
here is the *application*: the tempting change is a helpful `UPDATE ... SET
actor_id = 'deleted-user'`, which would fail at the privilege level and is worth
proving nobody even attempts.

AC-15's other half is that no surface resolves a tombstoned actor to a name. The
surfaces that exist today are the member list and the history feed; both are
checked, and the ones that arrive with later modules are owed rather than
silently uncovered.
"""

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.api import router as access_control_router
from prope.access_control.bootstrap import authenticate_session
from prope.errors import install_error_envelope
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    ADMIN_ID,
    WORKSPACE_A,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call

ADMIN_SESSION = "ses_trail_intact_admin_00000001"

COUNT_EVENTS_NAMING = text(
    "SELECT count(*) FROM history.history_event WHERE actor_id = :id OR target_id = :id"
)
SNAPSHOT_EVENTS = text(
    "SELECT id, actor_id, action, target_id, occurred_at FROM history.history_event ORDER BY seq"
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(access_control_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


def _admin() -> dict[str, str]:
    return {"cookie": f"prope_session={ADMIN_SESSION}"}


async def _a_leaver_who_did_things(api, migrate_engine) -> None:
    """A member who acted, so the trail has rows naming them before they go."""
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Admin")
    await seed_session(migrate_engine, ADMIN_SESSION)

    added = await call(
        api,
        "POST",
        f"/api/v1/workspaces/{WORKSPACE_A}/members",
        json_body={
            "email": "leaver@example.test",
            "display_name": "A Leaver",
            "roles": ["Owner"],
        },
        headers=_admin(),
    )
    assert added.status_code == 201, added.body
    leaver = added.json()["user_id"]

    removed = await call(
        api,
        "DELETE",
        f"/api/v1/workspaces/{WORKSPACE_A}/members/{leaver}",
        headers=_admin(),
    )
    assert removed.status_code == 204, removed.body
    return leaver


async def test_the_count_of_rows_naming_the_actor_is_unchanged(api, migrate_engine) -> None:
    """AC-14, stated as the number it is about."""
    leaver = await _a_leaver_who_did_things(api, migrate_engine)

    async with migrate_engine.begin() as connection:
        before = (await connection.execute(COUNT_EVENTS_NAMING, {"id": leaver})).scalar_one()
    # `member_added` and `member_removed`, both with the leaver as `target_id`.
    # `role_assigned` is deliberately not among them: its `target_type` is `role`
    # so its `target_id` is the role name, and the person is in
    # `details.grantee_user_id` — which is exactly why that key was registered.
    assert before >= 2, "member_added and member_removed at least"

    response = await call(api, "POST", f"/api/v1/users/{leaver}/tombstone", headers=_admin())
    assert response.status_code == 204, response.body

    async with migrate_engine.begin() as connection:
        after = (await connection.execute(COUNT_EVENTS_NAMING, {"id": leaver})).scalar_one()

    # +1: the tombstone writes its own `user_tombstoned` event naming them as the
    # target. Nothing that existed before it was removed or rewritten.
    assert after == before + 1


async def test_no_existing_row_is_altered(api, migrate_engine) -> None:
    """Not merely "the count held" — the rows themselves are byte-identical.

    A count assertion alone would pass an `UPDATE ... SET actor_id =
    'deleted-user'`, which is exactly the helpful change ADR-0054 forbids.
    """
    leaver = await _a_leaver_who_did_things(api, migrate_engine)

    async with migrate_engine.begin() as connection:
        before = (await connection.execute(SNAPSHOT_EVENTS)).all()

    await call(api, "POST", f"/api/v1/users/{leaver}/tombstone", headers=_admin())

    async with migrate_engine.begin() as connection:
        after = (await connection.execute(SNAPSHOT_EVENTS)).all()

    assert after[: len(before)] == before
    assert len(after) == len(before) + 1
    assert after[-1].action == "user_tombstoned"


async def test_the_actor_id_survives_as_an_opaque_value(api, migrate_engine) -> None:
    """`actor_id` is a value and not a foreign key, which is what makes this free.

    A foreign key to `access."user"` would have forced a choice between refusing
    the tombstone and cascading it into the audit log. There is none, so the id
    keeps naming a row that still exists and simply has no name any more.
    """
    leaver = await _a_leaver_who_did_things(api, migrate_engine)
    await call(api, "POST", f"/api/v1/users/{leaver}/tombstone", headers=_admin())

    async with migrate_engine.begin() as connection:
        actors = (
            await connection.execute(
                text("SELECT DISTINCT actor_id FROM history.history_event")
            )
        ).scalars().all()
        still_there = (
            await connection.execute(
                text('SELECT status FROM access."user" WHERE id = :id'), {"id": leaver}
            )
        ).scalar_one()

    assert ADMIN_ID in actors
    assert still_there == "tombstoned"


async def test_the_member_list_returns_the_row_with_no_name_and_no_email(
    api, migrate_engine
) -> None:
    """AC-15 over the one surface that resolves an id to a person today.

    The row is **not** filtered out. AC-15 requires that nothing resolves a
    tombstoned actor to a name; it does not require pretending they were never
    here, and hiding the row would leave a workspace's history full of ids the
    member list cannot explain. The client renders the absence through a
    catalogue key rather than the API inventing a string (ADR-0053).
    """
    leaver = await _a_leaver_who_did_things(api, migrate_engine)
    await call(api, "POST", f"/api/v1/users/{leaver}/tombstone", headers=_admin())

    listing = await call(
        api,
        "GET",
        f"/api/v1/workspaces/{WORKSPACE_A}/members",
        params={"status": "all"},
        headers=_admin(),
    )

    assert listing.status_code == 200, listing.body
    row = next(item for item in listing.json()["items"] if item["user_id"] == leaver)
    assert row["email"] is None
    assert row["display_name"] is None
    assert row["status"] == "removed"
    assert "A Leaver" not in listing.body.decode()
    assert "leaver@example.test" not in listing.body.decode()


async def test_the_surfaces_owed_to_later_modules_are_named_rather_than_skipped() -> None:
    """AC-15's remaining halves, stated so they are not mistaken for covered.

    The prompt list, the Activity feed's rendered actor column, the review screen
    and the release history all resolve an actor to a name, and none of them
    exists yet. Each arrives with its module — prompt-registry (phase 10),
    release-control (phase 14), the SPA (phase 21) — and each owes the same
    assertion. This test passes trivially and exists to be read.
    """
    owed = {
        "prompt-registry list and detail": 10,
        "release-control review and history": 14,
        "the SPA's Activity feed": 21,
    }
    assert set(owed) and all(phase > 9 for phase in owed.values())
