"""Shared factories for the ``history`` schema's tests.

**Placement.** A per-subject package named after the module, mirroring
``tests/broker/``'s precedent of a package created when its subject arrived.
That is the whole argument for the location.

The calendar constants below come from ``tests.unit`` rather than being
restated: a second ``wsp_01J…AAA`` literal in a second file is exactly the drift
these helper modules exist to prevent. Importing ``tests.unit`` executes its
module scope, which imports two call-ledger modules — that is a **test-rig
dependency, not a module edge**. ``docs/modules/property-history.lock.yml``'s
``dependencies: []`` is a statement about ``src/prope/``, and nothing under
``src/prope/property_history/`` imports another module at any depth. Re-homing
``WORKSPACE_A`` / ``DAY_1`` / ``day`` into a neutral ``tests/fixtures.py`` is
the alternative; it is a repo-wide refactor with no requirement asking for it,
and it is recorded rather than done here.

This package holds no test module of its own in Phase 4. Phase 5's contract
tests and Phase 6's chaos tests are where that changes.
"""

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.property_history.domain import RegisteredAction
from prope.property_history.registry import load_action_registry
from tests.unit import DAY_1, WORKSPACE_A, WORKSPACE_B, WORKSPACE_C, day

__all__ = [
    "ACTOR_ID",
    "COUNT_HISTORY_EVENTS",
    "COUNT_REGISTRY_ROWS",
    "DAY_1",
    "EVENT_ID",
    "OTHER_EVENT_ID",
    "SCOPE_PROMPT_ID",
    "SEED_HISTORY_EVENT",
    "SELECT_SEQS_BY_ID",
    "TARGET_ID",
    "THIRD_EVENT_ID",
    "WORKSPACE_A",
    "WORKSPACE_B",
    "WORKSPACE_C",
    "day",
    "history_event_values",
    "load_registry",
    "seed_history_event",
]

#: Distinct literals rather than generated values, so a failure names a row a
#: reader can find in the output.
EVENT_ID = "hev_01J0000000000000000000001"
OTHER_EVENT_ID = "hev_01J0000000000000000000002"
THIRD_EVENT_ID = "hev_01J0000000000000000000003"

ACTOR_ID = "usr_01J000000000000000000001"
TARGET_ID = "rev_01J000000000000000000001"
SCOPE_PROMPT_ID = "prm_01J0000000000000000000001"

#: Eleven columns; ``seq`` is absent, and the omission is deliberate — a column
#: that is not named cannot acquire a value by a one-word edit (D-53).
#:
#: **Deliberately not named ``INSERT_HISTORY_EVENT``.** Plan 04-02 ships a
#: production constant of that name and the same eleven columns in
#: ``src/prope/property_history/append.py``. Two constants sharing one name
#: across ``tests/`` and ``src/`` is a column added in Phase 5 landing in
#: whichever of the two the author had open. They are separate objects on
#: purpose: a test must be able to seed a row *without* the module under test,
#: which is what keeps the PH-02 privilege assertions independent of code plan
#: 04-02 writes. This one retires when Phase 5's ``append()`` becomes the
#: seeding path for tests that are not about the raw insert.
#:
#: ``details`` is bound through ``CAST(... AS jsonb)`` and takes JSON **text**:
#: SQLAlchemy's asyncpg jsonb encoder is ``lambda s: b"\\x01" + s.encode()``, so
#: binding a ``dict`` raises an ``AttributeError`` from inside a codec rather
#: than a type error at the call site.
SEED_HISTORY_EVENT = text(
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

COUNT_HISTORY_EVENTS = text("SELECT count(*) FROM history.history_event")
COUNT_REGISTRY_ROWS = text("SELECT count(*) FROM history.history_action_registry")
SELECT_SEQS_BY_ID = text("SELECT id, seq FROM history.history_event ORDER BY seq")


def history_event_values(**overrides: Any) -> dict[str, Any]:
    """The simplest row the CHECK set and the composite key accept.

    ``action='revision_approved'`` paired with ``target_type='revision'`` is
    **not** an arbitrary default: it is a registered pair, and
    ``fk_history_event_action`` is real even for the owner. A test that
    overrides one half without the other gets a foreign-key refusal that looks
    like the thing under test and is not — the same trap
    ``test_eval_no_body_boundary.py`` records for
    ``ck_call_record_eval_calls_carry_run``.

    ``details`` is JSON text, not a dict; see ``SEED_HISTORY_EVENT``.
    """
    values: dict[str, Any] = {
        "id": EVENT_ID,
        "workspace_id": WORKSPACE_A,
        "actor_type": "user",
        "actor_id": ACTOR_ID,
        "action": "revision_approved",
        "target_type": "revision",
        "target_id": TARGET_ID,
        "scope_prompt_id": SCOPE_PROMPT_ID,
        "reason": None,
        "details": json.dumps({}),
        "occurred_at": day(5),
    }
    values.update(overrides)
    return values


async def load_registry(
    app_sessionmaker: async_sessionmaker[AsyncSession],
) -> Mapping[str, RegisteredAction]:
    """The registry argument every ``record_event`` call in this phase takes.

    **A plain session, never ``workspace_transaction``.** This is the same read
    ADR-0038's process-start cache performs and it carries no tenant context by
    design; any test of the vocabulary that reaches for a tenant is a warning
    sign — if the registry is correct it does not need one, and if it needs one
    the registry is wrong.

    **The mapping is the real seeded vocabulary, not a fixture.**
    ``tests/unit/test_details_allow_list.py`` builds an invented three-row
    registry on purpose; this is deliberately not that, so the integration tests
    exercise the thirty-one rows revision 0005 seeded.
    """
    async with app_sessionmaker() as session:
        return await load_action_registry(session)


async def seed_history_event(migrate_engine: AsyncEngine, **overrides: Any) -> str:
    """Seed one history event as the owner and return its id.

    ``prope_app`` could insert one too, but the owner path keeps the seeding
    independent of the privilege under test.
    """
    values = history_event_values(**overrides)
    async with migrate_engine.begin() as connection:
        await connection.execute(SEED_HISTORY_EVENT, values)
    return str(values["id"])
