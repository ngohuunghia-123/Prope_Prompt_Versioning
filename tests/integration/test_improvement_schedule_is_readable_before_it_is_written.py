"""INT-050 — the re-probe cadence can be READ, and a workspace that never chose is not a 404.

**The setting was write-only.** ``PUT /workspaces/{id}/improvement-schedule`` had
existed since ADR-0068 and there was no ``GET``, which is not a cosmetic gap: a
toggle cannot render its own state from a write, so the screen the lock asks for
— *the estimated weekly cost shown at the moment somebody enables it* — could not
be built without a client that guessed. A client that guesses ``off`` for a
workspace which had already opted in offers to "enable" what is running, and the
person clicks it, and the workspace pays for a second schedule it already had.

Because ``improvement.schedule.enabled`` defaults to false and nothing rendered
the control, ``probe_leak_appeared`` — the twelfth detector, whose input is two
``readiness.probe_run`` rows for one version — could not fire in the product at
all. It is the detector ADR-0068 calls the reason the opt-in re-probe is worth
its money, and it was unreachable for want of a read route.

**Never-configured answers as the default, not as not-found**, and that is the
assertion this file leads with. *Off, weekly, nothing selected* is a true
description of a workspace that has not opted in; a 404 would make the screen
distinguish *absent* from *disabled*, a difference no reader of it has a use for
and one that every client would then have to handle. ``updated_at`` is null in
exactly that case and only that case, which is how a caller that does care can
still tell.

**The read takes ``spend_ceiling.manage``, the same permission as the write**,
which is not the usual read/write split and is the other property asserted here.
The row states what the workspace has committed to spending every week. Somebody
who cannot change that has no decision the number informs, and gating the read at
``prompt.read`` would publish the workspace's spending posture to every prompt
reader in it.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.prompt_improvement.domain import DEFAULT_CADENCE_DAYS
from tests.access_control import MEMBER_ID, seed_member, seed_role, seed_session, seed_user
from tests.evaluation import WORKSPACE_A, seed_owner
from tests.integration._asgi import call
from tests.prompt_improvement import improvement_api

OWNER_SESSION = "ses_improvement_sched_000001"

MEMBER_SESSION = "ses_improvement_sched_000002"

#: A workspace id that is not this session's. Used to prove the path parameter is
#: not a way to reach another tenant's row.
OTHER_WORKSPACE = "wsp_01J0000000000000000OTHER"

PATH = f"/api/v1/workspaces/{WORKSPACE_A}/improvement-schedule"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    yield from improvement_api(app_sessionmaker)


@pytest.fixture
async def an_admin_and_a_plain_member(migrate_engine: AsyncEngine) -> None:
    """The admin may manage spending; the member holds a membership and nothing else.

    **Admin and not Owner, and the distinction is the point of the route.**
    `spend_ceiling.manage` is bound to Admin in revision 0006 — an Owner runs the
    prompt library and an Admin runs the bill, and this row is the bill. A fixture
    that reached for the usual Owner would have made the refusal test below pass
    for the wrong reason and the positive tests fail for the right one.

    No prompt, no revision, no finding. The schedule is a workspace-level row and
    seeding a prompt here would suggest it hangs off one.
    """
    await seed_owner(migrate_engine, OWNER_SESSION)
    await seed_role(migrate_engine, "Admin")
    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_session(migrate_engine, MEMBER_SESSION, user_id=MEMBER_ID)


async def _read(api: Any, session_id: str, path: str = PATH) -> Any:
    return await call(api, "GET", path, headers={"cookie": f"prope_session={session_id}"})


async def _write(api: Any, session_id: str, **payload: Any) -> Any:
    return await call(
        api,
        "PUT",
        PATH,
        headers={"cookie": f"prope_session={session_id}"},
        json_body={"namespaces": [], "prompt_ids": [], **payload},
    )


async def test_a_workspace_that_never_chose_reads_as_off_rather_than_missing(
    api: Any, an_admin_and_a_plain_member: None
) -> None:
    """The default is a real answer. ``updated_at`` null is what says nobody chose."""
    response = await _read(api, OWNER_SESSION)

    assert response.status_code == 200, response.body
    assert response.json() == {
        "enabled": False,
        "cadence_days": DEFAULT_CADENCE_DAYS,
        "namespaces": [],
        "prompt_ids": [],
        "last_run_at": None,
        "updated_at": None,
    }


async def test_what_was_written_is_what_comes_back(
    api: Any, an_admin_and_a_plain_member: None
) -> None:
    """The round trip, which is the whole point of the route existing.

    Asserted through the API on both sides rather than against the repository:
    a read that agreed with a write only because both called the same helper
    would pass while the serialised shape the screen consumes was wrong.
    """
    written = await _write(api, OWNER_SESSION, enabled=True, cadence_days=14)
    assert written.status_code == 200, written.body

    response = await _read(api, OWNER_SESSION)

    assert response.status_code == 200, response.body
    body = response.json()
    assert body["enabled"] is True
    assert body["cadence_days"] == 14
    assert body["updated_at"] is not None, "a stored row always has an edit time"
    assert body["last_run_at"] is None, "writing a schedule does not run one"


async def test_turning_it_off_again_reads_as_off_and_not_as_never_configured(
    api: Any, an_admin_and_a_plain_member: None
) -> None:
    """**Disabled and never-configured must stay distinguishable in the row.**

    They deliberately answer the same ``enabled: false``, because no screen needs
    to tell them apart — but ``updated_at`` survives, so a decision somebody made
    is not indistinguishable from a decision nobody made. Losing that would make
    the audit question *did anyone ever turn this on?* unanswerable.
    """
    await _write(api, OWNER_SESSION, enabled=True, cadence_days=7)
    await _write(api, OWNER_SESSION, enabled=False, cadence_days=7)

    body = (await _read(api, OWNER_SESSION)).json()

    assert body["enabled"] is False
    assert body["updated_at"] is not None


async def test_a_member_who_cannot_manage_spending_is_refused_by_name(
    api: Any, an_admin_and_a_plain_member: None
) -> None:
    """Forbidden naming the permission, because they CAN see the workspace.

    The refusal asymmetry the whole product uses (A-116, A-076): not-found when
    the actor cannot see the subject, forbidden when they can. A member of the
    workspace can see the workspace, so hiding the route from them would be the
    wrong half of that rule — and would read as a bug rather than as a boundary.
    """
    response = await _read(api, MEMBER_SESSION)

    assert response.status_code == 403, response.body
    assert "spend_ceiling.manage" in response.json()["error"]["message"]


async def test_another_workspace_in_the_path_is_not_a_way_in(
    api: Any, an_admin_and_a_plain_member: None
) -> None:
    """The id is in the path for the route table's sake and answers nothing else.

    Refused here rather than left to RLS. The policy would return no row and the
    caller would get the never-configured default, which is a silently wrong
    answer about a workspace they have no business asking about — so the mismatch
    is a refusal before it is a query.
    """
    response = await _read(
        api, OWNER_SESSION, f"/api/v1/workspaces/{OTHER_WORKSPACE}/improvement-schedule"
    )

    assert response.status_code == 404, response.body
