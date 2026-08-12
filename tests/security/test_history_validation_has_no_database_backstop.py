"""D-62's owed pair: the half the engine refuses, and the half it does not.

**Half of what this file asserts is a refusal and half is a success, and both
are deliberate.** The ``(action, target_type)`` pairing is refused by the
engine, through ``fk_history_event_action`` (revision 0005) — real even for
``prope_migrate``, the role a repair script actually runs as. The ``details``
allow-list and ``requires_reason`` are refused only in Python, at
``append.check_event`` (plan 04-02): neither **can** be a ``CHECK`` — a
``CHECK`` cannot reach another table, and the registry is where both rules
live — and the shape that would work is a ``BEFORE INSERT`` trigger doing the
lookup, which ADR-0023 rejects for this module **by name**, on the grounds
that triggers "put the audit vocabulary in migrations rather than in a
module, where the allow-list of ADR-0024 cannot run." Revision ``0004``
refused a trigger once already for A-055, on three numbered grounds, and only
two of the three transfer here — the volume argument does not, because
``history_event`` takes one row per state change rather than one per gateway
call — so the refusal rests on ADR-0023 and on BSP-LINK's rule against
inventing schema the spec did not declare, not on a citation of ``0004``.

**An exception that is merely written down is a belief.** Both halves are
asserted here, so a later phase inherits a recorded boundary rather than a
guess about where the guarantee ends.
"""

import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.db.session import workspace_transaction
from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryAppendRejected, HistoryEventDraft
from tests.property_history import (
    ACTOR_ID,
    COUNT_HISTORY_EVENTS,
    SCOPE_PROMPT_ID,
    TARGET_ID,
    WORKSPACE_A,
    day,
    seed_history_event,
)

#: Written out here rather than reused from ``tests.property_history``'s
#: production-mirroring constant: this file's whole point is that each
#: statement below is deliberately wrong in one specific way, and a shared
#: factory that produced the simplest acceptable row would hide the
#: wrongness one edit later (``test_eval_no_body_boundary.py:48-53``).
INSERT_EVENT_BY_HAND = text(
    """
    INSERT INTO history.history_event (
        id, workspace_id, actor_type, actor_id, action, target_type, target_id,
        scope_prompt_id, reason, details, occurred_at
    ) VALUES (
        :id, :workspace_id, :actor_type, :actor_id, :action, :target_type, :target_id,
        :scope_prompt_id, :reason, CAST(:details AS jsonb), :occurred_at
    )
    """
)

SELECT_REGISTRY_ROW = text(
    "SELECT requires_reason, detail_keys FROM history.history_action_registry WHERE action = :action"
)


def _event_values(**overrides) -> dict:
    values = {
        "id": "hev_01J0000000000000000000101",
        "workspace_id": WORKSPACE_A,
        "actor_type": "user",
        "actor_id": ACTOR_ID,
        "action": "not_a_registered_action",
        "target_type": "revision",
        "target_id": TARGET_ID,
        "scope_prompt_id": SCOPE_PROMPT_ID,
        "reason": None,
        "details": json.dumps({}),
        "occurred_at": day(5),
    }
    values.update(overrides)
    return values


async def test_an_unregistered_action_is_refused_by_the_engine(migrate_engine: AsyncEngine):
    """T-04-26 / ADR-0025's realistic threat: a repair script, running as prope_migrate.

    **The whole point of D-57's composite key.** An action that is not a
    registry row cannot enter the table through the repair-script path, with
    the module not involved at all.
    """
    values = _event_values(id="hev_01J0000000000000000000102")

    with pytest.raises(IntegrityError) as excinfo:
        async with migrate_engine.begin() as connection:
            await connection.execute(INSERT_EVENT_BY_HAND, values)

    assert "fk_history_event_action" in str(excinfo.value)


async def test_a_registered_action_paired_with_the_wrong_target_type_is_refused(
    migrate_engine: AsyncEngine,
):
    """The composite key turns a caller bug a single-column key would accept into a refusal.

    ``revision_released`` is registered for ``target_type='revision'`` and not
    for ``'property'``.
    """
    values = _event_values(
        id="hev_01J0000000000000000000103",
        action="revision_released",
        target_type="property",
    )

    with pytest.raises(IntegrityError) as excinfo:
        async with migrate_engine.begin() as connection:
            await connection.execute(INSERT_EVENT_BY_HAND, values)

    assert "fk_history_event_action" in str(excinfo.value)


async def test_the_same_refusal_holds_for_the_application_role(
    app_sessionmaker, migrate_engine: AsyncEngine
):
    """The same refusal as ``prope_app``, and it names the constraint, not a privilege.

    A valid insert lands first, in a separate transaction, so the refusal
    below is not being read off an empty table — and the message is checked
    to name ``fk_history_event_action`` and **not** ``permission denied``: the
    two refusals are different facts, and a test that accepted either would
    assert neither.
    """
    await seed_history_event(migrate_engine)

    values = _event_values(id="hev_01J0000000000000000000104")

    with pytest.raises(IntegrityError) as excinfo:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            seen = (await session.execute(COUNT_HISTORY_EVENTS)).scalar_one()
            assert seen == 1, (
                "positive control failed: the seeded row is not visible to prope_app, "
                "so a refusal below would be indistinguishable from an empty table"
            )
            await session.execute(INSERT_EVENT_BY_HAND, values)

    message = str(excinfo.value)
    assert "fk_history_event_action" in message
    assert "permission denied" not in message.lower()


async def test_a_hand_written_insert_bypasses_the_python_validations(
    migrate_engine: AsyncEngine,
):
    """The recorded absence, and the point of the file.

    ``revision_break_glass_released`` paired with ``revision`` is a
    **registered** pair, so the engine-enforced half is satisfied. The
    ``reason`` is NULL on an action whose registry row requires one, and
    ``details`` carries a key that action does not register. Neither is
    refused, because neither can be a database guarantee (see the module
    docstring).

    **If this test starts failing, do not "fix" it.** It failing means
    somebody added the database guard, which is a real improvement and a real
    change to what later phases inherit — delete this test, and delete the
    absence recorded in ``alembic/versions/0005_history_schema_and_vocabulary.py``'s
    docstring, in the same change.
    """
    async with migrate_engine.begin() as connection:
        # Positive control: the chosen action really is the case under test.
        # Without this the insert below would prove nothing — a row that
        # violates no rule is allowed by everybody.
        requires_reason, detail_keys = (
            await connection.execute(
                SELECT_REGISTRY_ROW, {"action": "revision_break_glass_released"}
            )
        ).one()
        assert requires_reason is True
        assert detail_keys == []

    values = _event_values(
        id="hev_01J0000000000000000000105",
        action="revision_break_glass_released",
        target_type="revision",
        reason=None,
        details=json.dumps({"not_a_registered_key": "x"}),
    )

    async with migrate_engine.begin() as connection:
        await connection.execute(INSERT_EVENT_BY_HAND, values)

    async with migrate_engine.begin() as connection:
        landed = (
            await connection.execute(
                text("SELECT count(*) FROM history.history_event WHERE id = :id"),
                {"id": values["id"]},
            )
        ).scalar_one()
    assert landed == 1


async def test_the_python_path_refuses_what_the_hand_written_insert_landed(
    app_sessionmaker,
):
    """The closing pair: the SAME payload through ``append`` is refused.

    Two refusals of the same input by two different mechanisms, stated in one
    place rather than inferred from two.
    """
    draft = HistoryEventDraft(
        workspace_id=WORKSPACE_A,
        actor_type=ActorType.USER,
        actor_id=ACTOR_ID,
        action="revision_break_glass_released",
        target_type="revision",
        target_id=TARGET_ID,
        occurred_at=day(5),
        reason=None,
        details={"not_a_registered_key": "x"},
    )

    with pytest.raises(HistoryAppendRejected):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await append(session, draft)
