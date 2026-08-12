"""AC-6 and AC-7, in their integration form — restore, and withdrawal.

The e2e halves of both criteria measure the GATEWAY (revision 4 served within
five minutes; model-not-found within thirty seconds of a withdrawal), and the
gateway's 30 s resolution cache EXPIRES with nothing invalidating it (ADR-0012).
What is asserted here is everything on this side of that cache: the release row,
the pointer, the events, and the fact that retire is unblocked.

**OQ-002's exemption is narrow and the narrowness is the decision.** A restore to
a revision that was already Approved AND already released at least once is exempt
from a fresh release decision; it carries a mandatory reason and appends a
``revision_restored`` event. A restore to an Approved revision that has NEVER
been released is an ordinary release and still requires the release decision —
and an implementing agent that widened this to *"restores skip approval"* would
have deleted the product's central claim. Both halves are below.

**Withdraw is its own permission and its own route.** It takes a consuming
product's AI feature offline, so it must not be reachable by anyone tidying up a
list (A-069, ADR-0009) — and ``POST /releases`` refuses ``kind=withdraw``
outright rather than accepting it under ``release.create``.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, seed_prompt, seed_revision
from tests.release_control import (
    ADMIN_ID,
    APPROVER_ID,
    passing_summary,
    read_releases,
    release_api,
    releases_without_approval,
    seed_actor,
    stub_summary,
)

AUTHOR_SESSION = "ses_release_restore_author"

APPROVER_SESSION = "ses_release_restore_approver"

ADMIN_SESSION = "ses_release_restore_admin"

ADMIN_ACTOR = "usr_01J000000000000RESTOREADM"

VERSION_4 = "rev_01J00000000000000000REV04"

VERSION_7 = "rev_01J00000000000000000REV07"

RESTORE_REASON = "revision 7 is refusing in-policy refunds; going back to 4"

WITHDRAW_REASON = "the model name is being retired at the customer's request"

POINTER = text(
    """
    SELECT released_version_id, released_at
    FROM   registry.prompt_property
    WHERE  id = :prompt_id
    """
)

HISTORY = text(
    """
    SELECT action, target_id, reason
    FROM   history.history_event
    WHERE  scope_prompt_id = :prompt_id
    ORDER  BY seq
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


def _releases(kind: str) -> float:
    return REGISTRY.get_sample_value("prope_release_total", {"kind": kind}) or 0.0


async def _approve_and_release(api, monkeypatch, version_id: str, expected: str | None) -> None:  # noqa: ANN001
    submitted = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{version_id}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )
    assert submitted.status_code == 201, submitted.body

    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, version_id)):
        approved = await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{version_id}/approve",
            json_body={"comment": "reads well"},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )
    assert approved.status_code == 201, approved.body

    released = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={
            "version_id": version_id,
            "kind": "release",
            "expected_current_version_id": expected,
        },
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )
    assert released.status_code == 201, released.body


async def _revision_seven_released_over_revision_four(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await seed_actor(migrate_engine, AUTHOR_SESSION, roles=("Owner",), user_id=ADMIN_ID)
    await seed_actor(
        migrate_engine,
        APPROVER_SESSION,
        roles=("Reviewer",),
        user_id=APPROVER_ID,
        seed_the_workspace=False,
    )
    await seed_actor(
        migrate_engine,
        ADMIN_SESSION,
        roles=("Admin",),
        user_id=ADMIN_ACTOR,
        seed_the_workspace=False,
    )
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, VERSION_4, revision_number=4, author_id=ADMIN_ID)
    await seed_revision(migrate_engine, VERSION_7, revision_number=7, author_id=ADMIN_ID)

    await _approve_and_release(api, monkeypatch, VERSION_4, None)
    await _approve_and_release(api, monkeypatch, VERSION_7, VERSION_4)


async def _pointer(migrate_engine: AsyncEngine) -> tuple:
    async with migrate_engine.begin() as connection:
        row = (await connection.execute(POINTER, {"prompt_id": PROMPT_ID})).mappings().one()
    return row["released_version_id"], row["released_at"]


async def _history(migrate_engine: AsyncEngine) -> list[tuple]:
    async with migrate_engine.begin() as connection:
        return [tuple(row) for row in (await connection.execute(HISTORY, {"prompt_id": PROMPT_ID})).all()]


async def test_restoring_to_a_previously_released_revision_needs_a_reason_and_no_new_approval(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _revision_seven_released_over_revision_four(api, migrate_engine, monkeypatch)

    before = _releases("restore")
    restored = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={
            "version_id": VERSION_4,
            "kind": "restore",
            "expected_current_version_id": VERSION_7,
            "reason": RESTORE_REASON,
        },
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )

    assert restored.status_code == 201, restored.body
    assert restored.json()["kind"] == "restore"
    assert restored.json()["reason"] == RESTORE_REASON
    assert restored.json()["previous_version_id"] == VERSION_7

    assert (await _pointer(migrate_engine))[0] == VERSION_4
    assert _releases("restore") == before + 1

    rows = await read_releases(migrate_engine)
    assert rows[-1]["approval_id"] is not None, (
        "the exemption is from a fresh DECISION, not from carrying one: the restore points at "
        "the approval the revision already had"
    )
    assert await releases_without_approval(migrate_engine) == []

    actions = [row[0] for row in await _history(migrate_engine)]
    assert "revision_restored" in actions
    assert actions.count("revision_released") == 3


async def test_a_restore_without_a_reason_is_refused(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _revision_seven_released_over_revision_four(api, migrate_engine, monkeypatch)

    refused = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={
            "version_id": VERSION_4,
            "kind": "restore",
            "expected_current_version_id": VERSION_7,
        },
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )

    assert refused.status_code == 422, refused.body
    assert refused.code == "release_reason_required"
    assert (await _pointer(migrate_engine))[0] == VERSION_7


async def test_a_restore_to_a_revision_that_was_never_released_is_refused(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """OQ-002's boundary, and the generalisation an agent would reach for.

    ``restores skip approval`` is the WRONG reading. What is exempt is the
    repetition of a decision, never the decision itself — so a revision that has
    been Approved but never released cannot arrive through the restore door.
    """
    await seed_actor(migrate_engine, AUTHOR_SESSION, roles=("Owner",), user_id=ADMIN_ID)
    await seed_actor(
        migrate_engine,
        APPROVER_SESSION,
        roles=("Reviewer",),
        user_id=APPROVER_ID,
        seed_the_workspace=False,
    )
    await seed_actor(
        migrate_engine,
        ADMIN_SESSION,
        roles=("Admin",),
        user_id=ADMIN_ACTOR,
        seed_the_workspace=False,
    )
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, VERSION_4, revision_number=4, author_id=ADMIN_ID)

    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_4}/submit",
        headers={"cookie": f"prope_session={AUTHOR_SESSION}"},
    )
    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, VERSION_4)):
        await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_4}/approve",
            json_body={"comment": "reads well"},
            headers={"cookie": f"prope_session={APPROVER_SESSION}"},
        )

    refused = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={"version_id": VERSION_4, "kind": "restore", "reason": RESTORE_REASON},
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )

    assert refused.status_code == 409, refused.body
    assert refused.code == "release_not_previously_released"
    assert await read_releases(migrate_engine) == []


async def test_withdrawing_clears_the_pointer_and_unblocks_retire(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """A-052 — withdrawal is what retire is blocked ON, so it is what unblocks it.

    The retire half is read through ``registry.prompt_property``'s own guard
    rather than through this module: ``RETIRE_PROMPT_PROPERTY`` carries
    ``AND released_version_id IS NULL`` in its ``WHERE`` clause, so a cleared
    pointer is the whole of what changes.
    """
    await _revision_seven_released_over_revision_four(api, migrate_engine, monkeypatch)

    before = _releases("withdraw")
    withdrawn = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases/withdraw",
        json_body={"reason": WITHDRAW_REASON},
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )

    assert withdrawn.status_code == 201, withdrawn.body
    assert withdrawn.json()["kind"] == "withdraw"
    assert withdrawn.json()["version_id"] is None
    assert withdrawn.json()["previous_version_id"] == VERSION_7

    version_id, released_at = await _pointer(migrate_engine)
    assert version_id is None
    assert released_at is None

    assert _releases("withdraw") == before + 1
    assert await releases_without_approval(migrate_engine) == []

    trail = await _history(migrate_engine)
    assert (
        "release_withdrawn",
        withdrawn.json()["release_id"],
        WITHDRAW_REASON,
    ) in trail


async def test_withdrawing_nothing_is_refused_rather_than_absorbed(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """A withdrawal of nothing is a caller bug, not a no-op.

    Absorbing it would write a mandatory-reason ``release_withdrawn`` event
    describing an act that did not happen — an entry in the one table the product
    claims never lies.
    """
    await _revision_seven_released_over_revision_four(api, migrate_engine, monkeypatch)

    first = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases/withdraw",
        json_body={"reason": WITHDRAW_REASON},
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )
    assert first.status_code == 201, first.body

    again = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases/withdraw",
        json_body={"reason": WITHDRAW_REASON},
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )

    assert again.status_code == 409, again.body
    assert again.code == "release_nothing_released"
    assert len([row for row in await read_releases(migrate_engine) if row["kind"] == "withdraw"]) == 1


async def test_withdraw_is_refused_for_an_actor_without_that_permission(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """A-069, as far as migration 0006's seeded matrix can express it.

    The lock asks for *withdraw refused for an actor holding plain release*, and
    the shipped matrix cannot produce that actor: ``release.create``,
    ``release.break_glass`` and ``release.withdraw`` all sit on Admin, which is
    OQ-006's to answer rather than this module's. What is asserted is the
    property this module owns — withdraw resolves ``release.withdraw`` as its OWN
    question rather than inheriting an answer — and the Reviewer, who can see the
    prompt and holds none of the three, gets a refusal naming it.
    """
    await _revision_seven_released_over_revision_four(api, migrate_engine, monkeypatch)

    refused = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases/withdraw",
        json_body={"reason": WITHDRAW_REASON},
        headers={"cookie": f"prope_session={APPROVER_SESSION}"},
    )

    assert refused.status_code == 403, refused.body
    assert refused.json()["error"]["details"]["permission"] == "release.withdraw"
    assert (await _pointer(migrate_engine))[0] == VERSION_7


async def test_the_release_route_refuses_a_withdrawal_kind(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """A withdrawal cannot arrive under ``release.create``'s permission.

    Accepting ``kind=withdraw`` here would make ``release.withdraw`` a permission
    with a hole in it — the distinct permission is the control, and one route
    accepting both kinds is how a control becomes a suggestion.
    """
    await _revision_seven_released_over_revision_four(api, migrate_engine, monkeypatch)

    refused = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        json_body={"version_id": VERSION_7, "kind": "withdraw", "reason": WITHDRAW_REASON},
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )

    assert refused.status_code == 422, refused.body
    assert refused.code == "validation_failed"
    assert (await _pointer(migrate_engine))[0] == VERSION_7


async def test_the_release_log_reads_newest_first(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _revision_seven_released_over_revision_four(api, migrate_engine, monkeypatch)
    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/releases/withdraw",
        json_body={"reason": WITHDRAW_REASON},
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )

    log = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/releases",
        headers={"cookie": f"prope_session={ADMIN_SESSION}"},
    )

    assert log.status_code == 200, log.body
    kinds = [row["kind"] for row in log.json()]
    assert kinds[0] == "withdraw"
    assert kinds == ["withdraw", "release", "release"]
