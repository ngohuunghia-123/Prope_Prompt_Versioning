"""`ROUTE_ACTION` is the only place Prope's two action vocabularies meet.

`ManagementAction` enumerates HTTP operations; `Action` enumerates A-115's
permissions. They are coarser and finer on purpose — `price.manage` is one
permission over three call-ledger routes — and the map is what lets Phase 23's
route-table assertion resolve every route in the product to a permission.

Totality is the property that matters: a route declaring a member absent from the
map mounts fine and is then unauthorisable, which is AC-10's failure wearing a
passing test.
"""

from sqlalchemy import text

from prope.access_control.actions import (
    ACTIONS_BY_VALUE,
    ROUTE_ACTION,
    Action,
    NoPermission,
    parse_action,
)
from prope.session_auth import ManagementAction

READ_MATRIX_ACTIONS = text("SELECT DISTINCT action FROM access.role_permission")

READ_ACTION_CHECK = text(
    """
    SELECT pg_get_constraintdef(oid)
    FROM   pg_constraint
    WHERE  conname = 'ck_role_permission_action_values'
    """
)


def test_the_map_is_total_over_the_route_vocabulary() -> None:
    assert set(ROUTE_ACTION) == set(ManagementAction)


def test_every_mapped_value_resolves() -> None:
    for declaration, permission in ROUTE_ACTION.items():
        assert isinstance(permission, Action | NoPermission), declaration


def test_the_permission_vocabulary_holds_a_115s_twenty_six_members() -> None:
    """A-115's twenty-five plus ADR-0061's one, and no twenty-seventh without a migration.

    The number moved on 2026-08-18 and the assertion moved with it, which is the
    whole point of asserting it: `namespace.grant` (A-160) arrived **with**
    migration 0026, which widens `ck_role_permission_action_values` and seeds the
    Admin row in the same revision. `test_the_database_check_mirrors_the_enum`
    below is what makes that a fact rather than a claim — a member added here and
    not there fails against the running database.
    """
    assert len(Action) == 26
    assert len(ACTIONS_BY_VALUE) == 26
    assert Action.NAMESPACE_GRANT.value == "namespace.grant"


def test_parse_action_denies_rather_than_raises() -> None:
    """A-115: an unrecognised action is a deny, never an error and never an allow."""
    for outside in ("prompt.reed", "", "PROMPT.READ", "prompt read"):
        assert parse_action(outside) is None

    assert parse_action("prompt.read") is Action.PROMPT_READ
    assert parse_action(Action.PROMPT_READ) is Action.PROMPT_READ


async def test_the_seeded_matrix_uses_only_vocabulary_members(app_sessionmaker) -> None:
    """The running matrix and this build's enum are the same vocabulary.

    Read on the application role with no tenant set, because
    `access.role_permission` is global and `GET /api/v1/permissions` reads it that
    way. A seeded action outside `Action` would render on that endpoint as a
    string OQ-006's answer could not be compared against.
    """
    async with app_sessionmaker() as session:
        seeded = set((await session.execute(READ_MATRIX_ACTIONS)).scalars().all())

    assert seeded, "the matrix seed did not land, so this comparison proves nothing"
    assert seeded <= {member.value for member in Action}, sorted(seeded - set(ACTIONS_BY_VALUE))


async def test_the_database_check_mirrors_the_enum(migrate_engine) -> None:
    """`ck_role_permission_action_values` is the same twenty-six strings.

    The `CHECK` is what refuses a value that reaches the table from anywhere but
    this enum, so the two drifting apart is the one way a permission could exist
    in code and be unstorable, or exist in the matrix and be unparseable.
    """
    async with migrate_engine.begin() as connection:
        definition = (await connection.execute(READ_ACTION_CHECK)).scalar_one()

    for member in Action:
        assert f"'{member.value}'" in definition, member
