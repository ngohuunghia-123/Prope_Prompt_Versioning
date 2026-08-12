"""AC-10 — two reviewers release two different revisions of one prompt, at once.

Without the guard the later write silently wins and one reviewer believes they
released something that is not in production — *the worst possible lie for this
module to tell*. So every release carries ``expected_current_version_id``, and
the pointer write is a compare-and-set inside the transaction that writes the
release row (A-072).

**The ``WHERE`` clause is the guard, not an ``if``.** ``set_released_revision``
writes ``released_version_id IS NOT DISTINCT FROM :expected`` — ``IS NOT
DISTINCT FROM`` rather than ``=`` because the expected value is legitimately NULL
on a first release and ``NULL = NULL`` is NULL, which would make every first
release look like a lost race.

**Exactly one release row exists afterwards.** That is the half a
check-then-write would fail: both transactions would pass the check, both would
insert, and only the pointer would disagree with the log.
"""

import asyncio

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
    seed_actor,
    stub_summary,
)

AUTHOR_SESSION = "ses_release_race_author"

APPROVER_SESSION = "ses_release_race_approver"

ADMIN_SESSION = "ses_release_race_admin"

VERSION_A = "rev_01J000000000000000RACE0A"

VERSION_B = "rev_01J000000000000000RACE0B"

RELEASED_POINTER = text(
    "SELECT released_version_id FROM registry.prompt_property WHERE id = :prompt_id"
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


def _conflicts() -> float:
    return REGISTRY.get_sample_value("prope_release_pointer_conflict_total") or 0.0


async def _two_approved_revisions(api, migrate_engine: AsyncEngine, monkeypatch) -> None:  # noqa: ANN001
    """Two revisions carried through the real decision path, not seeded Approved.

    Seeding ``registry.revision.status = 'Approved'`` directly — which is what
    ``tests.prompt_registry.approve`` does, correctly, for tests whose subject is
    the constraint — leaves NO approval row, and this module then refuses the
    release with ``release_no_approval_recorded``. That refusal is right, and it
    is asserted on its own in ``test_release_carries_approval``. Here the subject
    is the race, so both revisions arrive at the starting line the way a real one
    would.
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
        user_id="usr_01J0000000000000RACEADMIN",
        seed_the_workspace=False,
    )
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, VERSION_A, revision_number=1, author_id=ADMIN_ID)
    await seed_revision(migrate_engine, VERSION_B, revision_number=2, author_id=ADMIN_ID)

    for version_id in (VERSION_A, VERSION_B):
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


async def _release(api, version_id: str, expected: str | None) -> object:  # noqa: ANN001
    return await call(
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


async def _pointer(migrate_engine: AsyncEngine) -> str | None:
    async with migrate_engine.begin() as connection:
        return await connection.scalar(RELEASED_POINTER, {"prompt_id": PROMPT_ID})


async def test_exactly_one_of_two_concurrent_releases_wins(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """Both are issued against the same expected pointer — NULL, a first release."""
    await _two_approved_revisions(api, migrate_engine, monkeypatch)

    before = _conflicts()
    first, second = await asyncio.gather(
        _release(api, VERSION_A, None), _release(api, VERSION_B, None)
    )

    outcomes = sorted([first.status_code, second.status_code])
    assert outcomes == [201, 409], (first.body, second.body)

    loser = first if first.status_code == 409 else second
    winner = second if first.status_code == 409 else first

    assert loser.code == "release_pointer_conflict"
    assert loser.json()["error"]["details"]["released_version_id"] == winner.json()["version_id"]

    releases = await read_releases(migrate_engine)
    assert len(releases) == 1
    assert releases[0]["version_id"] == winner.json()["version_id"]

    assert await _pointer(migrate_engine) == winner.json()["version_id"]
    assert _conflicts() == before + 1


async def test_a_stale_expectation_is_refused_and_names_what_is_released_now(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """The sequential form of the same race, and the one a reviewer meets.

    Two people open the release screen; one releases; the other clicks ten
    minutes later against the pointer their screen still shows. The refusal
    carries the version id that IS released, because a reviewer who cannot see
    that cannot re-decide — the message is the whole remedy.
    """
    await _two_approved_revisions(api, migrate_engine, monkeypatch)

    assert (await _release(api, VERSION_A, None)).status_code == 201

    stale = await _release(api, VERSION_B, None)

    assert stale.status_code == 409, stale.body
    assert stale.code == "release_pointer_conflict"
    assert stale.json()["error"]["details"]["expected_current_version_id"] is None
    assert stale.json()["error"]["details"]["released_version_id"] == VERSION_A

    assert len(await read_releases(migrate_engine)) == 1
    assert await _pointer(migrate_engine) == VERSION_A


async def test_a_correct_expectation_moves_the_pointer(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """The positive half. Without it, "the compare-and-set refuses" would be
    satisfied by a build that refused everything."""
    await _two_approved_revisions(api, migrate_engine, monkeypatch)

    assert (await _release(api, VERSION_A, None)).status_code == 201
    second = await _release(api, VERSION_B, VERSION_A)

    assert second.status_code == 201, second.body
    assert await _pointer(migrate_engine) == VERSION_B

    releases = await read_releases(migrate_engine)
    assert len(releases) == 2
    assert releases[1]["previous_version_id"] == VERSION_A


async def test_the_loser_writes_no_release_row_and_no_history_event(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """One transaction, so a refused pointer write takes its release row with it.

    This is the property that makes the reconciliation query's original scenario
    unreachable: the row and the pointer commit together against one database
    (ADR-0026, ADR-0027), so there is no window in which one exists without the
    other.
    """
    await _two_approved_revisions(api, migrate_engine, monkeypatch)

    await _release(api, VERSION_A, None)
    await _release(api, VERSION_B, None)

    releases = await read_releases(migrate_engine)
    assert [row["version_id"] for row in releases] == [VERSION_A]

    async with migrate_engine.begin() as connection:
        events = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM history.history_event "
                    "WHERE scope_prompt_id = :prompt_id AND action = 'revision_released'"
                ),
                {"prompt_id": PROMPT_ID},
            )
        ).scalar_one()

    assert events == 1


async def test_a_stub_summary_is_not_needed_for_a_release(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """The release path pulls no review summary, and that is deliberate.

    Evidence is composed for a DECISION — the approval — and stored on it as
    testimony (A-074). The release reads the recorded decision rather than the
    evidence behind it, so an evaluation outage cannot block a release of an
    already-approved revision.
    """
    await _two_approved_revisions(api, migrate_engine, monkeypatch)

    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, VERSION_A)) as asked:
        released = await _release(api, VERSION_A, None)

    assert released.status_code == 201, released.body
    assert asked == []
