"""Revision 0005's three named CHECKs on ``history_event``, provoked by name.

``tests/architecture/test_schema_invariants.py`` proves no native enum exists and
``test_migration_chain.py`` snapshots the constraint list. Neither provokes one.
Each constraint below is asserted **by name** in the message, in the shape
``test_call_record_guarantees.py`` established for ``ledger.call_record``: a
constraint that is only ever read out of ``pg_constraint`` is a row, not a rule.

Both directions are asserted for the two constraints that have a permitted half —
a CHECK inverted by a later edit would otherwise leave the whole suite green.

Every statement goes through ``migrate_engine``: the subject is the constraint,
and the owner role is the one path where no privilege and no policy can be the
thing that actually refused.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from prope.property_history.domain import MAX_REASON_CHARACTERS
from tests.property_history import (
    OTHER_EVENT_ID,
    SEED_HISTORY_EVENT,
    history_event_values,
)

#: A Vietnamese character costs three bytes in UTF-8, so 500 of them are ~1500
#: bytes. ADR-0053 ships a Vietnamese-only interface, and this literal is the
#: only thing in the suite that tells a character cap from a byte cap.
MULTIBYTE_CHARACTER = "ứ"


async def _insert(migrate_engine, **overrides) -> None:
    async with migrate_engine.begin() as connection:
        await connection.execute(SEED_HISTORY_EVENT, history_event_values(**overrides))


async def test_an_actor_type_outside_the_two_is_refused_by_name(migrate_engine):
    with pytest.raises(IntegrityError) as excinfo:
        await _insert(migrate_engine, actor_type="robot")

    assert "ck_history_event_actor_type_values" in str(excinfo.value)


async def test_a_user_actor_with_no_actor_id_is_refused_by_name(migrate_engine):
    with pytest.raises(IntegrityError) as excinfo:
        await _insert(migrate_engine, actor_type="user", actor_id=None)

    assert "ck_history_event_actor_id_present_unless_system" in str(excinfo.value)


async def test_a_system_actor_may_be_anonymous(migrate_engine):
    """The permitted half. ADR-0054 needs it and nothing else in the suite writes one.

    Were ``actor_id`` ever shipped ``NOT NULL``, or the CHECK inverted, every
    other history test would still pass and this one would not.
    """
    await _insert(migrate_engine, actor_type="system", actor_id=None)


async def test_a_system_actor_with_an_id_is_still_accepted(migrate_engine):
    """The constraint is a floor on the user case, not an exclusion on the system one."""
    await _insert(migrate_engine, actor_type="system")


async def test_the_reason_cap_counts_characters_and_not_bytes(migrate_engine):
    """ADR-0053: a byte cap would be a ~170-character cap for every user the MVP has.

    This is the assertion that distinguishes the shipped
    ``char_length(reason) <= 500`` from the ``varchar(500)`` revision 0005
    refused; both accept 500 ASCII characters and only one accepts 500
    Vietnamese ones.
    """
    await _insert(migrate_engine, reason=MULTIBYTE_CHARACTER * MAX_REASON_CHARACTERS)

    with pytest.raises(IntegrityError) as excinfo:
        await _insert(
            migrate_engine,
            id=OTHER_EVENT_ID,
            reason=MULTIBYTE_CHARACTER * (MAX_REASON_CHARACTERS + 1),
        )

    assert "ck_history_event_reason_length" in str(excinfo.value)
