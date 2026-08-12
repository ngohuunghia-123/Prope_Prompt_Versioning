"""INT-007's three scope shapes, its cursor, and A-045's bounds.

Rows are seeded through ``seed_history_events`` where the subject is the *shape
of a corpus* and through ``append()`` where the subject is the seam. The
distinction is the same one plan 05-01 draws: a test that seeded a tracer would
prove the statement and not the path.

**Not wrapped in an outer transaction that is rolled back** — ``tests/conftest.py``
refuses that pattern, and it matters here because these tests open their own
transactions and read across two workspaces.
"""

import pytest

from prope.db.session import workspace_transaction
from prope.property_history.domain import (
    ActorScope,
    HistoryCursorUnknown,
    PromptScope,
    TargetScope,
)
from prope.property_history.read import MAX_LIMIT, read
from tests.property_history import (
    ACTOR_ID,
    SCOPE_PROMPT_ID,
    TARGET_ID,
    WORKSPACE_A,
    WORKSPACE_B,
    day,
    history_event_values,
    seed_history_events,
)

OTHER_SCOPE_PROMPT_ID = "prm_01J0000000000000000000002"
OTHER_TARGET_ID = "rev_01J000000000000000000002"
OTHER_ACTOR_ID = "usr_01J000000000000000000002"


def event_id(n: int) -> str:
    return f"hev_01J{n:022d}"


def rows(*specs: dict) -> list[dict]:
    """One row per spec, ids ascending so ``seq`` follows the argument order."""
    return [history_event_values(id=event_id(n), **spec) for n, spec in enumerate(specs, start=1)]


async def seed_prompt_events(migrate_engine, count: int) -> list[str]:
    """``count`` events on one prompt. Returns their ids NEWEST FIRST."""
    ids = [event_id(n) for n in range(1, count + 1)]
    await seed_history_events(
        migrate_engine,
        [history_event_values(id=identifier, occurred_at=day(5)) for identifier in ids],
    )
    return list(reversed(ids))


async def test_each_scope_returns_its_own_events_and_not_the_others(
    app_sessionmaker, migrate_engine
):
    """One event matches all three scopes; the other two match none of them."""
    await seed_history_events(
        migrate_engine,
        rows(
            {},  # the default row: SCOPE_PROMPT_ID / revision / TARGET_ID / ACTOR_ID
            {
                "scope_prompt_id": OTHER_SCOPE_PROMPT_ID,
                "target_id": OTHER_TARGET_ID,
                "actor_id": OTHER_ACTOR_ID,
            },
            # Same target_id and same actor, different target_type and prompt —
            # TargetScope must separate it out and ActorScope must keep it.
            {
                "action": "property_created",
                "target_type": "property",
                "scope_prompt_id": OTHER_SCOPE_PROMPT_ID,
            },
        ),
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        by_prompt = await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID))
        by_target = await read(session, TargetScope(WORKSPACE_A, "revision", TARGET_ID))
        by_actor = await read(session, ActorScope(WORKSPACE_A, ACTOR_ID))

    assert [event.id for event in by_prompt] == [event_id(1)]
    assert [event.id for event in by_target] == [event_id(1)]
    assert [event.id for event in by_actor] == [event_id(3), event_id(1)]


async def test_a_scope_object_of_no_declared_shape_is_a_type_error(app_sessionmaker):
    """A ``dict`` scope is a refusal, not a full-workspace scan."""
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        with pytest.raises(TypeError) as excinfo:
            await read(session, {"workspace_id": WORKSPACE_A})  # type: ignore[arg-type]

    assert "dict" in str(excinfo.value)


@pytest.mark.parametrize("limit", [0, -1, MAX_LIMIT + 1])
async def test_a_limit_outside_a_045s_bound_is_refused(app_sessionmaker, limit):
    """The message names the value supplied and the bound it broke."""
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        with pytest.raises(ValueError) as excinfo:
            await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID), limit=limit)

    message = str(excinfo.value)
    assert str(limit) in message
    assert str(MAX_LIMIT) in message


async def test_the_largest_legal_limit_is_accepted(app_sessionmaker, migrate_engine):
    """The boundary belongs to the accepted side (``test_retention_argument_guards``'s rule)."""
    await seed_prompt_events(migrate_engine, 3)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        events = await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID), limit=MAX_LIMIT)

    assert len(events) == 3


async def test_a_cursorless_page_is_the_newest_events_and_the_next_page_follows_it(
    app_sessionmaker, migrate_engine
):
    """No overlap and no gap across the seam between two pages."""
    newest_first = await seed_prompt_events(migrate_engine, 7)
    scope = PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        first = await read(session, scope, limit=3)
        second = await read(session, scope, cursor=first[-1].id, limit=3)

    assert [event.id for event in first] == newest_first[:3]
    assert [event.id for event in second] == newest_first[3:6]
    assert second[0].seq < first[-1].seq


async def test_paging_with_limit_one_visits_every_event_exactly_once(
    app_sessionmaker, migrate_engine
):
    """The full walk, and the page after the last is empty rather than an error."""
    newest_first = await seed_prompt_events(migrate_engine, 6)
    scope = PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID)

    visited: list[str] = []
    seqs: list[int] = []
    cursor: str | None = None

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        while True:
            page = await read(session, scope, cursor=cursor, limit=1)
            if not page:
                break
            visited.append(page[0].id)
            seqs.append(page[0].seq)
            cursor = page[0].id

    assert visited == newest_first
    assert seqs == sorted(seqs, reverse=True)
    assert len(set(visited)) == len(visited)


async def test_a_cursor_naming_no_event_is_refused(app_sessionmaker, migrate_engine):
    """Never an empty page: an unresolvable cursor reads as *the trail ended here*."""
    await seed_prompt_events(migrate_engine, 3)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        with pytest.raises(HistoryCursorUnknown) as excinfo:
            await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID), cursor=event_id(999))

    assert event_id(999) in str(excinfo.value)


async def test_a_cursor_from_another_workspace_is_refused(app_sessionmaker, migrate_engine):
    """The cursor is not portable across tenants — that is a containment, not an optimisation."""
    await seed_history_events(
        migrate_engine,
        [
            history_event_values(id=event_id(1)),
            history_event_values(id=event_id(2), workspace_id=WORKSPACE_B),
        ],
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        with pytest.raises(HistoryCursorUnknown):
            await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID), cursor=event_id(2))

    # Positive control: the cursor resolves fine inside the workspace that owns it.
    async with workspace_transaction(app_sessionmaker, WORKSPACE_B) as session:
        assert await read(session, PromptScope(WORKSPACE_B, SCOPE_PROMPT_ID), cursor=event_id(2)) == ()


async def test_a_cursor_under_a_different_scope_is_accepted(app_sessionmaker, migrate_engine):
    """A cursor is a position in ``seq``, not a claim about the scope.

    Paging stays correct because the page statement re-applies the scope, so an
    id from a neighbouring prompt can only move the window inside data the
    caller could already read.
    """
    await seed_history_events(
        migrate_engine,
        rows(
            {},
            {"scope_prompt_id": OTHER_SCOPE_PROMPT_ID},
            {},
        ),
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        page = await read(
            session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID), cursor=event_id(2)
        )

    assert [event.id for event in page] == [event_id(1)]
