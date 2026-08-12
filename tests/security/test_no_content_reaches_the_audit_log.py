from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.db.session import workspace_transaction
from prope.property_history.append import append
from prope.property_history.domain import (
    NEVER_PROMPT_SCOPED_TARGET_TYPES,
    ActorType,
    HistoryEventDraft,
)
from prope.property_history.registry import registered_actions
from tests.property_history import ACTOR_ID, SCOPE_PROMPT_ID, TARGET_ID, WORKSPACE_A, day

SELECT_ALL_EVENTS = text("SELECT id, action, target_type, reason, details FROM history.history_event")

REASON_LENGTH_CHECK = text(
    "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ck_history_event_reason_length'"
)

MARKER_VALUE = "safe-value"
SAFE_REASON = "da xem xet va chap nhan"


async def _seed_full_corpus(app_sessionmaker, migrate_engine: AsyncEngine) -> int:
    async with app_sessionmaker() as plain_session:
        registry = await registered_actions(plain_session)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        for row in registry:
            details = {key: MARKER_VALUE for key in sorted(row.detail_keys)}
            scope_prompt_id = None if row.target_type in NEVER_PROMPT_SCOPED_TARGET_TYPES else SCOPE_PROMPT_ID
            draft = HistoryEventDraft(
                workspace_id=WORKSPACE_A,
                actor_type=ActorType.USER,
                actor_id=ACTOR_ID,
                action=row.action,
                target_type=row.target_type,
                target_id=TARGET_ID,
                occurred_at=day(5),
                scope_prompt_id=scope_prompt_id,
                reason=SAFE_REASON if row.requires_reason else None,
                details=details,
            )
            await append(session, draft)

    return len(registry)


async def test_every_registered_action_appends_and_every_stored_details_payload_matches_its_allow_list(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    async with app_sessionmaker() as plain_session:
        registry = await registered_actions(plain_session)
    allow_lists = {row.action: row.detail_keys for row in registry}

    expected = await _seed_full_corpus(app_sessionmaker, migrate_engine)

    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(SELECT_ALL_EVENTS)).mappings().all()

    assert len(rows) == expected
    for row in rows:
        assert set(row["details"]) <= allow_lists[row["action"]], row["id"]


async def test_the_reason_length_cap_is_a_live_engine_constraint(migrate_engine: AsyncEngine) -> None:
    async with migrate_engine.begin() as connection:
        definition = (await connection.execute(REASON_LENGTH_CHECK)).scalar_one_or_none()

    assert definition is not None, "ck_history_event_reason_length does not exist on the live table"
    assert "500" in definition
