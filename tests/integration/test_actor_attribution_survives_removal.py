from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.property_history.domain import ActorScope
from prope.property_history.read import read
from tests.property_history import ACTOR_ID, WORKSPACE_A, history_event_values, seed_history_events

FOREIGN_KEYS = text(
    "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
    "WHERE conrelid = 'history.history_event'::regclass AND contype = 'f'"
)

OTHER_ACTOR_ID = "usr_01J000000000000000000099"


async def test_history_event_carries_no_foreign_key_on_actor_id(migrate_engine) -> None:
    async with migrate_engine.begin() as connection:
        constraints = (await connection.execute(FOREIGN_KEYS)).all()

    names = {name for name, _ in constraints}
    assert names == {"fk_history_event_action"}
    for _, definition in constraints:
        assert "actor_id" not in definition


async def test_an_actors_events_keep_their_actor_id_regardless_of_who_else_wrote(
    app_sessionmaker, migrate_engine
) -> None:
    await seed_history_events(
        migrate_engine,
        [
            history_event_values(id="hev_01J0000000000000000000101"),
            history_event_values(id="hev_01J0000000000000000000102"),
            history_event_values(id="hev_01J0000000000000000000103", actor_id=OTHER_ACTOR_ID),
        ],
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        events = await read(session, ActorScope(WORKSPACE_A, ACTOR_ID))

    assert len(events) == 2
    assert {event.actor_id for event in events} == {ACTOR_ID}
