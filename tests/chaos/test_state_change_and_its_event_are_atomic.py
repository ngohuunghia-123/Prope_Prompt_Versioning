import asyncio
import contextlib

import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from prope.db.engine import build_engine
from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft
from tests.property_history import ACTOR_ID, TARGET_ID, WORKSPACE_A, day

CREATE_PROBE_TABLE = text("CREATE TABLE history.chaos_probe_state (id text PRIMARY KEY)")
DROP_PROBE_TABLE = text("DROP TABLE IF EXISTS history.chaos_probe_state")
GRANT_PROBE_TABLE = text("GRANT SELECT, INSERT ON history.chaos_probe_state TO prope_app")
INSERT_PROBE_ROW = text("INSERT INTO history.chaos_probe_state (id) VALUES (:id)")
COUNT_PROBE_ROW = text("SELECT count(*) FROM history.chaos_probe_state WHERE id = :id")
SET_TENANT = text("SELECT set_config('app.workspace_id', :ws, true)")
BACKEND_PID = text("SELECT pg_backend_pid()")
TERMINATE_BACKEND = text("SELECT pg_terminate_backend(:pid)")
COUNT_EVENT = text("SELECT count(*) FROM history.history_event WHERE target_id = :target_id")

PROBE_ID = "probe-01"

BEFORE_PROBE = "before_probe_insert"
AFTER_PROBE_BEFORE_APPEND = "after_probe_insert_before_append"
AFTER_APPEND_BEFORE_COMMIT = "after_append_before_commit"


@pytest.fixture
async def superuser_engine(postgres_container):
    engine = build_engine(postgres_container.get_connection_url(), poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def probe_table(migrate_engine):
    async with migrate_engine.begin() as connection:
        await connection.execute(DROP_PROBE_TABLE)
        await connection.execute(CREATE_PROBE_TABLE)
        await connection.execute(GRANT_PROBE_TABLE)
    yield
    async with migrate_engine.begin() as connection:
        await connection.execute(DROP_PROBE_TABLE)


def _draft() -> HistoryEventDraft:
    return HistoryEventDraft(
        workspace_id=WORKSPACE_A,
        actor_type=ActorType.USER,
        actor_id=ACTOR_ID,
        action="revision_approved",
        target_type="revision",
        target_id=TARGET_ID,
        occurred_at=day(5),
    )


async def _run_and_kill_at(app_sessionmaker, superuser_engine, interleave: str) -> None:
    ready = asyncio.Event()
    never = asyncio.Event()
    pid_box: list[int] = []

    async def victim() -> None:
        async with app_sessionmaker() as session:
            async with session.begin():
                await session.execute(SET_TENANT, {"ws": WORKSPACE_A})
                pid_box.append((await session.execute(BACKEND_PID)).scalar_one())

                if interleave == BEFORE_PROBE:
                    ready.set()
                    await never.wait()

                await session.execute(INSERT_PROBE_ROW, {"id": PROBE_ID})

                if interleave == AFTER_PROBE_BEFORE_APPEND:
                    ready.set()
                    await never.wait()

                await append(session, _draft())

                if interleave == AFTER_APPEND_BEFORE_COMMIT:
                    ready.set()
                    await never.wait()

    task = asyncio.create_task(victim())
    await ready.wait()

    async with superuser_engine.begin() as connection:
        await connection.execute(TERMINATE_BACKEND, {"pid": pid_box[0]})

    task.cancel()
    with contextlib.suppress(BaseException):
        await task


@pytest.mark.parametrize("interleave", [BEFORE_PROBE, AFTER_PROBE_BEFORE_APPEND, AFTER_APPEND_BEFORE_COMMIT])
async def test_a_killed_backend_leaves_neither_row_nor_the_other(
    app_sessionmaker, migrate_engine, superuser_engine, probe_table, interleave: str
) -> None:
    await _run_and_kill_at(app_sessionmaker, superuser_engine, interleave)

    async with migrate_engine.begin() as connection:
        probe_count = (await connection.execute(COUNT_PROBE_ROW, {"id": PROBE_ID})).scalar_one()
        event_count = (await connection.execute(COUNT_EVENT, {"target_id": TARGET_ID})).scalar_one()

    assert probe_count == 0
    assert event_count == 0


async def test_an_uninterrupted_transaction_commits_both_rows_together(
    app_sessionmaker, migrate_engine, probe_table
) -> None:
    async with app_sessionmaker() as session:
        async with session.begin():
            await session.execute(SET_TENANT, {"ws": WORKSPACE_A})
            await session.execute(INSERT_PROBE_ROW, {"id": PROBE_ID})
            await append(session, _draft())

    async with migrate_engine.begin() as connection:
        probe_count = (await connection.execute(COUNT_PROBE_ROW, {"id": PROBE_ID})).scalar_one()
        event_count = (await connection.execute(COUNT_EVENT, {"target_id": TARGET_ID})).scalar_one()

    assert probe_count == 1
    assert event_count == 1
