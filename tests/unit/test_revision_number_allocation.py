"""A-048 — the number is allocated optimistically and the unique constraint arbitrates.

There is no sequence and no advisory lock. ``next_revision_number`` reads
``MAX + 1`` and the INSERT races; ``uq_revision_prompt_id`` decides. That is a
deliberate trade the lock names: a sequence would hand out numbers with holes in
them the first time a save rolled back, and an author looking at *revision 4,
revision 6* has no way to know whether 5 was deleted.

**The retry is the part that needs a savepoint, and that is what most of this
file is about.** A unique violation poisons the enclosing transaction in
PostgreSQL — every subsequent statement on that connection fails with
``current transaction is aborted`` until a rollback. So a retry that simply
re-issued the INSERT would not merely lose the race, it would break the caller's
whole transaction, including the history append that has to share it (ADR-0023).
``begin_nested`` is what makes *the loser retries once automatically*
implementable at all, and a test that only asserted the happy path would not
notice its removal.

The collision is forced by replacing the allocator rather than by racing two
real transactions. A race would assert the same thing on a good day and flake on
a slow one, and what is under test is the response to a collision, not the
scheduler.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.prompt_registry import commands, repository
from prope.prompt_registry.domain import RevisionConflict, RevisionDraft
from prope.prompt_registry.observability import revision_conflict_total
from tests.access_control import ADMIN_ID, seed_user, seed_workspace
from tests.prompt_registry import PROMPT_ID, seed_prompt, seed_revision
from tests.unit import WORKSPACE_A

NOW = datetime(2026, 8, 1, tzinfo=UTC)

COUNT_REVISIONS = text("SELECT count(*) FROM registry.revision WHERE prompt_id = :prompt_id")

READ_NUMBERS = text(
    "SELECT revision_number FROM registry.revision WHERE prompt_id = :prompt_id "
    "ORDER BY revision_number"
)

COUNT_EVENTS = text("SELECT count(*) FROM history.history_event WHERE action = 'revision_created'")


def _draft(summary: str = "a change") -> RevisionDraft:
    return RevisionDraft(body="You are a helpful assistant.", change_summary=summary)


def _conflicts() -> float:
    return revision_conflict_total._value.get()


async def _prompt(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_prompt(migrate_engine)


async def _numbers(migrate_engine) -> list[int]:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        result = await connection.execute(READ_NUMBERS, {"prompt_id": PROMPT_ID})
        return [row[0] for row in result]


async def _save(
    app_sessionmaker: async_sessionmaker[AsyncSession], draft: RevisionDraft
) -> int:
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        created = await commands.create_revision(
            db,
            workspace_id=WORKSPACE_A,
            actor_id=ADMIN_ID,
            prompt_id=PROMPT_ID,
            draft=draft,
            now=NOW,
        )
        return created.revision_number


async def test_the_first_revision_of_a_prompt_is_number_one(
    migrate_engine, app_sessionmaker
) -> None:
    """``COALESCE(MAX, 0) + 1`` over an empty chain, and not a zero.

    A-002 numbers revisions the way a person counts them. The first thing an
    author saves is *revision 1*, not *revision 0*, and the difference shows on
    every screen in the product.
    """
    await _prompt(migrate_engine)

    assert await _save(app_sessionmaker, _draft()) == 1


async def test_numbers_are_consecutive_with_no_holes(migrate_engine, app_sessionmaker) -> None:
    """The property a sequence would give up, asserted directly.

    Each save opens its own transaction, so this is four separately committed
    allocations rather than four rows written at once.
    """
    await _prompt(migrate_engine)

    for index in range(4):
        assert await _save(app_sessionmaker, _draft(f"change {index}")) == index + 1

    assert await _numbers(migrate_engine) == [1, 2, 3, 4]


async def test_the_loser_of_a_collision_retries_once_and_succeeds(
    migrate_engine, app_sessionmaker, monkeypatch
) -> None:
    """The savepoint's whole reason: the transaction survives the violation.

    The allocator is made to hand out a number that is already taken, once. The
    save must still land — at the correct next number — and the history append
    that follows it in the SAME transaction must land too. If the failed INSERT
    were not wrapped in a savepoint, the append would fail with *current
    transaction is aborted* and the trail would be the thing that broke.
    """
    await _prompt(migrate_engine)
    await seed_revision(migrate_engine, revision_number=1)

    honest = repository.next_revision_number
    handed_out: list[int] = []

    async def colliding_once(db: AsyncSession, prompt_id: str) -> int:
        allocated = 1 if not handed_out else await honest(db, prompt_id)
        handed_out.append(allocated)
        return allocated

    monkeypatch.setattr(repository, "next_revision_number", colliding_once)

    before = _conflicts()

    assert await _save(app_sessionmaker, _draft()) == 2

    assert handed_out == [1, 2]
    assert _conflicts() == before + 1
    assert await _numbers(migrate_engine) == [1, 2]

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_EVENTS) == 1


async def test_a_second_collision_is_reported_rather_than_looped(
    migrate_engine, app_sessionmaker, monkeypatch
) -> None:
    """``REVISION_RETRIES = 1``, and the author is told somebody else saved first.

    The number in the exception is the one that collided, so the message can say
    *someone else saved first* rather than *something went wrong* — and the
    editor can reload the chain with the author's text still in the box.

    A longer loop would turn a two-writer race into a queue nobody asked for,
    and would hold the caller's transaction open while it waited.
    """
    await _prompt(migrate_engine)
    await seed_revision(migrate_engine, revision_number=1)

    async def always_colliding(db: AsyncSession, prompt_id: str) -> int:
        return 1

    monkeypatch.setattr(repository, "next_revision_number", always_colliding)

    before = _conflicts()

    with pytest.raises(RevisionConflict) as refused:
        await _save(app_sessionmaker, _draft())

    assert refused.value.revision_number == 1
    assert refused.value.prompt_id == PROMPT_ID
    assert "another transaction" in str(refused.value)

    assert _conflicts() == before + commands.REVISION_RETRIES + 1

    assert await _numbers(migrate_engine) == [1]
    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_EVENTS) == 0


async def test_the_constraint_refuses_a_duplicate_number_written_directly(
    migrate_engine,
) -> None:
    """The arbiter itself, reached without going through the command.

    Everything above proves the command reacts correctly to a collision. This
    proves there is something to react to: ``uq_revision_prompt_id`` refuses the
    second row at the engine, so a future write path that forgot the retry would
    still be unable to hand two authors the same revision number.
    """
    await _prompt(migrate_engine)
    await seed_revision(migrate_engine, revision_number=1)

    with pytest.raises(IntegrityError) as refused:
        await seed_revision(
            migrate_engine,
            version_id="rev_01J000000000000000000REV2",
            revision_number=1,
        )

    assert "uq_revision_prompt_id" in str(refused.value)


async def test_two_prompts_number_their_chains_independently(
    migrate_engine, app_sessionmaker
) -> None:
    """The unique constraint is on ``(prompt_id, revision_number)``, not on the number.

    Worth stating: a workspace-wide counter would make revision numbers a
    meaningless global sequence, and *revision 1* would stop meaning *the first
    thing anyone wrote here*.
    """
    await _prompt(migrate_engine)
    other = await seed_prompt(
        migrate_engine,
        prompt_id="prm_01J0000000000000000OTHER",
        namespace="billing",
        name="dunning",
    )

    assert await _save(app_sessionmaker, _draft()) == 1

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        created = await commands.create_revision(
            db,
            workspace_id=WORKSPACE_A,
            actor_id=ADMIN_ID,
            prompt_id=other,
            draft=_draft(),
            now=NOW,
        )

    assert created.revision_number == 1

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_REVISIONS, {"prompt_id": PROMPT_ID}) == 1
        assert await connection.scalar(COUNT_REVISIONS, {"prompt_id": other}) == 1
