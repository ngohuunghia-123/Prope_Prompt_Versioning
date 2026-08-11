"""T-003. Every `SECURITY DEFINER` object in the database, enumerated and named.

`tests/architecture/test_schema_invariants.py` asks the same question per schema
and would miss a definer function created in `public` — which is where one would
land if somebody wrote `CREATE FUNCTION lookup_thing(...)` with no schema
qualifier while `search_path` pointed there. This walks the whole cluster.

A `SECURITY DEFINER` function runs as its owner, and the owner here is
`prope_migrate`, which owns every table and can drop every policy. So each of the
three is a hole with a lid on it, and the lid is four properties: it returns
identifiers only, it has an empty `search_path`, it is `REVOKE`d from `PUBLIC`,
and it makes no security decision of its own.
"""

from sqlalchemy import text

#: CLAUDE.md's sanctioned four, minus the one whose module does not exist yet.
#: `evaluation.claim_next_run()` arrives in phase 16 and is added here then — as a
#: literal edit, the same shape `EXPECTED_ABSENT_SCHEMAS` uses.
EXPECTED = {
    "access.list_workspaces",
    "access.lookup_api_key",
    "access.lookup_session",
}

ALL_DEFINER_OBJECTS = text(
    """
    SELECT n.nspname || '.' || p.proname       AS qualified,
           pg_get_userbyid(p.proowner)         AS owner,
           p.proconfig,
           pg_get_function_result(p.oid)       AS result,
           has_function_privilege('public', p.oid, 'EXECUTE') AS public_may_execute
    FROM   pg_proc p
    JOIN   pg_namespace n ON n.oid = p.pronamespace
    WHERE  p.prosecdef
      AND  n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER  BY qualified
    """
)

#: What an identifier-returning function may name. Anything else — a body, a
#: password hash, a name, an email — would make the definer a row reader with the
#: tenant policy switched off, which is the failure ADR-0051 draws the line
#: against. `key_hash` is the one that looks like an exception and is not: the
#: comparison happens in Python precisely so the function stays a lookup.
IDENTIFIER_COLUMNS = frozenset(
    {
        "workspace_id",
        "user_id",
        "key_id",
        "key_hash",
        "scope_model_names",
        "revoked_at",
        "text",
    }
)


async def _definer_objects(migrate_engine) -> list:
    async with migrate_engine.begin() as connection:
        return (await connection.execute(ALL_DEFINER_OBJECTS)).all()


async def test_the_set_is_exactly_the_sanctioned_functions(migrate_engine) -> None:
    """Both directions. A fourth is a designed-in failure, not a fix."""
    rows = await _definer_objects(migrate_engine)

    assert {row.qualified for row in rows} == EXPECTED, (
        "the SECURITY DEFINER set moved. CLAUDE.md sanctions exactly four across the whole "
        "product — access.lookup_session, access.lookup_api_key, access.list_workspaces() and "
        "evaluation.claim_next_run() — and each returns identifiers only, never rows."
    )


async def test_each_one_is_owned_by_migrate_and_locked_down(migrate_engine) -> None:
    for row in await _definer_objects(migrate_engine):
        assert row.owner == "prope_migrate", row.qualified
        assert row.proconfig == ['search_path=""'], (row.qualified, row.proconfig)
        assert not row.public_may_execute, f"{row.qualified} is executable by PUBLIC"


async def test_each_one_returns_identifiers_and_nothing_else(migrate_engine) -> None:
    """ADR-0051's rule, read off the declared return type.

    The reason this is worth asserting mechanically: the tempting change is not
    adding a fourth function, it is adding one column to an existing one.
    `authenticate_session` makes a second round trip for `must_change_password`
    rather than letting it ride along inside the definer, and that second trip is
    what this test protects.
    """
    for row in await _definer_objects(migrate_engine):
        declared = row.result.removeprefix("SETOF ").removeprefix("TABLE(").removesuffix(")")
        named = {part.split()[0].strip().lower() for part in declared.split(",")}
        unexpected = named - IDENTIFIER_COLUMNS
        assert unexpected == set(), f"{row.qualified} returns {sorted(unexpected)}"


async def test_none_of_them_authenticates(migrate_engine) -> None:
    """The lookups look up; the decision is Python's (ADR-0042, A-113).

    A definer function with a security decision inside it is a much worse thing
    than one that finds a row: a defect in its body is an authentication bypass
    with the policy already off. `lookup_api_key` returns the stored hash and
    `revoked_at` and compares neither.
    """
    async with migrate_engine.begin() as connection:
        bodies = dict(
            (
                await connection.execute(
                    text(
                        "SELECT n.nspname || '.' || p.proname, p.prosrc "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                        "WHERE p.prosecdef AND n.nspname = 'access'"
                    )
                )
            ).all()
        )

    for name, body in bodies.items():
        lowered = body.lower()
        assert "crypt" not in lowered, name
        assert "digest" not in lowered, name
        # A comparison against a caller-supplied secret would be the decision
        # moving into the function. `revoked_at` travels out as a column instead.
        assert "revoked_at is null" not in lowered, (
            f"{name} filters on revoked_at; a revoked key must be a DECISION in Python, "
            "counted apart from an absent row, not a row the function hides"
        )
