"""This file asserts a boundary, in both directions.

The engine refuses the statement anyone would write — a hand-written INSERT
naming ``seq`` — and it does **not** refuse the statement someone determined
would write: ``OVERRIDING SYSTEM VALUE`` carries no privilege requirement in
PostgreSQL, so any role holding ``INSERT`` may use it, and the engine names
the bypass in its own ``HINT``. D-53 says ``GENERATED ALWAYS`` "makes the
engine refuse a caller-supplied value"; that is true of the naive form and
false of the documented one, and this file is what turns the difference from
a belief into a recorded boundary.

The division of labour with ``tests/architecture/test_no_overriding_system_
value.py``: the engine closes the accidental case, and the source gate closes
the deliberate one. Neither is sufficient alone.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from prope.db.session import workspace_transaction
from tests.property_history import (
    SEED_HISTORY_EVENT,
    SELECT_SEQS_BY_ID,
    WORKSPACE_A,
    history_event_values,
)

#: Twelve columns, ``seq`` first, ``:seq`` bound. Every other value comes from
#: ``history_event_values()``, so the row is otherwise exactly the one the
#: engine accepts and the refusal is attributable to ``seq`` alone.
INSERT_WITH_A_SUPPLIED_SEQ = text(
    """
    INSERT INTO history.history_event (
        seq, id, workspace_id, actor_type, actor_id, action, target_type, target_id,
        scope_prompt_id, reason, details, occurred_at
    ) VALUES (
        :seq, :id, :workspace_id, :actor_type, :actor_id, :action, :target_type, :target_id,
        :scope_prompt_id, :reason, CAST(:details AS jsonb), :occurred_at
    )
    """
)

#: The one place in this repository the token is permitted in a string constant.
#: It needs no ``ALLOWED`` entry in the source gate: that gate walks ``src/prope``
#: and ``alembic`` only, and this file is under ``tests/`` by construction.
INSERT_WITH_OVERRIDING_SYSTEM_VALUE = text(
    """
    INSERT INTO history.history_event (
        seq, id, workspace_id, actor_type, actor_id, action, target_type, target_id,
        scope_prompt_id, reason, details, occurred_at
    ) OVERRIDING SYSTEM VALUE VALUES (
        :seq, :id, :workspace_id, :actor_type, :actor_id, :action, :target_type, :target_id,
        :scope_prompt_id, :reason, CAST(:details AS jsonb), :occurred_at
    )
    """
)

COUNT_ROWS = text("SELECT count(*) FROM history.history_event WHERE id = :id")
READ_SEQ = text("SELECT seq FROM history.history_event WHERE id = :id")

NAIVE_ID = "hev_01J0000000000000000000010"
CONTROL_ID = "hev_01J0000000000000000000011"
OVERRIDDEN_ID = "hev_01J0000000000000000000012"
NEXT_ID = "hev_01J0000000000000000000013"

#: Far above anything the sequence has issued: ``tests/conftest.py``'s
#: ``TRUNCATE ... RESTART IDENTITY`` resets the identity sequence before every
#: test, so this stays unreachable by any engine-assigned value in this rig.
SUPPLIED_SEQ = 9_000_000_000


async def test_an_insert_naming_seq_is_refused_by_the_engine(app_sessionmaker):
    values = history_event_values(id=NAIVE_ID, seq=1)

    with pytest.raises(DBAPIError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await session.execute(INSERT_WITH_A_SUPPLIED_SEQ, values)

    # The message is the primary assertion: the exception the dialect wraps
    # depends on the asyncpg adapter, so a test asserting only an attribute
    # path would be asserting the adapter as much as the engine.
    assert "generated always" in str(excinfo.value).lower()

    sqlstate = getattr(excinfo.value.orig, "sqlstate", None)
    if sqlstate is not None:
        assert sqlstate == "428C9"  # ERRCODE_GENERATED_ALWAYS, corroboration only


async def test_the_same_insert_without_seq_succeeds(app_sessionmaker, migrate_engine):
    """The positive control. Without it, the refusal above could be from any
    other rejection the engine happens to raise for this row."""
    values = history_event_values(id=CONTROL_ID)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await session.execute(SEED_HISTORY_EVENT, values)

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_ROWS, {"id": CONTROL_ID})).scalar_one() == 1
        assert (await control.execute(READ_SEQ, {"id": CONTROL_ID})).scalar_one() is not None


async def test_overriding_system_value_is_accepted_and_that_is_the_recorded_boundary(
    app_sessionmaker, migrate_engine
):
    """The honest half.

    **If this test starts failing, do not "fix" it.** It failing means
    PostgreSQL changed the rule or somebody added a guard, which is a real
    change to what later phases inherit — delete this test and, in the same
    change, the ``OVERRIDING SYSTEM VALUE`` sentence in revision 0005's
    docstring paragraph headed *"Two absences"*.

    A supplied ``seq`` does **not** advance the sequence, so the next
    engine-assigned value is **lower** than the supplied one: it succeeds, and
    it sorts before an event written earlier. The unique-constraint collision
    the naive reading predicts is real in principle but is **unreachable
    here** — ``TRUNCATE ... RESTART IDENTITY`` resets the sequence before
    every test and ``SUPPLIED_SEQ`` is far above anything it has issued. The
    branch asserted is the one that is real in this rig: the next
    ``append`` succeeds with a lower ``seq``, and a read ordered by
    ``seq`` returns the later-written event first — exactly why
    ``tests/architecture/test_no_overriding_system_value.py`` exists, and why
    this engine assertion alone is not the control.
    """
    values = history_event_values(id=OVERRIDDEN_ID, seq=SUPPLIED_SEQ)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await session.execute(INSERT_WITH_OVERRIDING_SYSTEM_VALUE, values)

    async with migrate_engine.begin() as control:
        assert (await control.execute(READ_SEQ, {"id": OVERRIDDEN_ID})).scalar_one() == (
            SUPPLIED_SEQ
        )

    next_values = history_event_values(id=NEXT_ID)
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await session.execute(SEED_HISTORY_EVENT, next_values)

    async with migrate_engine.begin() as control:
        next_seq = (await control.execute(READ_SEQ, {"id": NEXT_ID})).scalar_one()
        ordered = (await control.execute(SELECT_SEQS_BY_ID)).all()

    assert next_seq < SUPPLIED_SEQ, (
        "the next engine-assigned seq must be LOWER than the supplied one: a supplied "
        "value does not advance the sequence, so this is the real hazard, not a "
        "uq_history_event_seq collision"
    )

    ordered_ids = [row.id for row in ordered]
    assert ordered_ids.index(NEXT_ID) < ordered_ids.index(OVERRIDDEN_ID), (
        "a read ordered by seq must return the later-written event first — the order is "
        "silently wrong from the moment of the overriding insert"
    )
