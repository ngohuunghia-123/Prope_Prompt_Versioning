"""AC-5 / A-081. A scope refusal carries nothing a leaked key could learn from.

`may_resolve` is a bare `bool` on purpose. A result object with a reason would be
a reason somebody eventually puts in a response body, and at the gateway that
turns a leaked key into a directory of the workspace's released prompts: ask for
every plausible model name and watch which ones refuse differently.

**The gateway half of AC-5 is owed to phase 19 and is not asserted here.** This
file proves the seam gives the gateway nothing to leak; that the gateway then
renders an out-of-scope name identically to an unknown one is that phase's test
to write, against a route that does not exist yet.
"""

import pytest
from prometheus_client import REGISTRY, generate_latest

from prope.access_control.keys import mint_key
from prope.access_control.permissions import may_resolve
from prope.access_control.seams import authenticate_api_key
from prope.db.session import workspace_transaction
from tests.access_control import KEY_ID, WORKSPACE_A, seed_api_key, seed_workspace

IN_SCOPE = "prope/greeting"
OUT_OF_SCOPE = "prope/pricing-explainer"
NEVER_EXISTED = "prope/no-such-prompt-at-all"

#: The namespace every name above shares, passed as `may_resolve`'s third
#: argument since ADR-0061. **It is always the same value here, and that is what
#: makes this file still prove what it proves**: the union INT-004 now answers is
#: `name IN scope_model_names OR namespace IN scope_namespaces`, so holding the
#: namespace constant and empty isolates the per-name half, which is the half
#: AC-5 is about. `scope_namespaces` defaults to `'{}'` and every key seeded below
#: leaves it that way, so `= ANY('{}')` is false for every input and the second
#: disjunct contributes nothing — default-deny by the same mechanism as before,
#: with no branch anybody could forget.
#:
#: A-159 prices the disclosure the OTHER half adds, and it is a different one:
#: a key scoped by namespace tells a holder which namespaces exist, never which
#: names do. That is a separate assertion in a separate file, not a weakening of
#: this one.
NAMESPACE = "prope"


async def test_a_key_resolves_only_what_it_was_scoped_for(migrate_engine, app_sessionmaker) -> None:
    await seed_workspace(migrate_engine)
    await seed_api_key(migrate_engine, scope_model_names=(IN_SCOPE,))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await may_resolve(db, KEY_ID, IN_SCOPE, NAMESPACE) is True
        assert await may_resolve(db, KEY_ID, OUT_OF_SCOPE, NAMESPACE) is False


async def test_an_out_of_scope_name_and_an_unknown_one_answer_identically(
    migrate_engine, app_sessionmaker
) -> None:
    """The enumeration oracle, closed at the seam.

    Both are `False`, and `False` is the whole return value — there is no field
    the gateway could branch on to render two different refusals even if it
    wanted to.
    """
    await seed_workspace(migrate_engine)
    await seed_api_key(migrate_engine, scope_model_names=(IN_SCOPE,))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        out_of_scope = await may_resolve(db, KEY_ID, OUT_OF_SCOPE, NAMESPACE)
        unknown = await may_resolve(db, KEY_ID, NEVER_EXISTED, NAMESPACE)

    assert out_of_scope is unknown is False


async def test_an_empty_scope_resolves_nothing(migrate_engine, app_sessionmaker) -> None:
    """A-081's default-deny, by construction rather than by a branch.

    `= ANY('{}')` is false for every name, so a key provisioned before anybody
    decided what it may reach resolves nothing without an `if` somebody could
    forget to write.
    """
    await seed_workspace(migrate_engine)
    await seed_api_key(migrate_engine, scope_model_names=())

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await may_resolve(db, KEY_ID, IN_SCOPE, NAMESPACE) is False


async def test_a_revoked_key_resolves_nothing_on_the_next_request(
    migrate_engine, app_sessionmaker
) -> None:
    """AC-6 at this seam: no TTL, no cache, no window (A-114, ADR-0022)."""
    from sqlalchemy import text

    await seed_workspace(migrate_engine)
    await seed_api_key(migrate_engine, scope_model_names=(IN_SCOPE,))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await may_resolve(db, KEY_ID, IN_SCOPE, NAMESPACE) is True

    async with migrate_engine.begin() as connection:
        await connection.execute(
            text("UPDATE access.api_key SET revoked_at = now() WHERE id = :id"), {"id": KEY_ID}
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await may_resolve(db, KEY_ID, IN_SCOPE, NAMESPACE) is False


@pytest.mark.parametrize(
    "presented",
    [
        None,
        "",
        "not-a-key",
        "prope_key_missing-the-secret",
        "wrong_key_01J0000000000000000KEY1_abcdefgh",
        "prope_usr_01J0000000000000000KEY1_abcdefgh",
    ],
)
async def test_every_malformed_presentation_is_none_and_never_an_exception(
    app_sessionmaker, presented: str | None
) -> None:
    """A garbled `Authorization` header must answer like a key revoked yesterday.

    An exception here would be a `500` among `401`s — which is itself a
    distinguishable response, and therefore the same oracle in a different shape.
    """
    assert await authenticate_api_key(app_sessionmaker, presented) is None


async def test_a_wrong_secret_for_a_live_key_id_is_indistinguishable_from_an_unknown_id(
    migrate_engine, app_sessionmaker
) -> None:
    """Both count as `unknown`. Telling them apart in a dashboard would be an oracle
    for *"this key id is live"* — one of the two halves an attacker would
    otherwise have to guess whole."""
    await seed_workspace(migrate_engine)
    minted = mint_key()
    await seed_api_key(migrate_engine, minted.key_id, key_hash=minted.key_hash)

    forged = f"{minted.key_id.join(('prope_', '_'))}not-the-real-secret"

    assert await authenticate_api_key(app_sessionmaker, forged) is None
    assert await authenticate_api_key(app_sessionmaker, minted.plaintext) is not None


async def test_the_refusal_counter_names_the_key_and_never_the_model(
    migrate_engine, app_sessionmaker
) -> None:
    """`key_scope_refusal_total` carries `key_id` and no model name.

    The label is OQ-135's second entry and it earns its cardinality: without it
    the operator knows refusals are happening and cannot say which consumer to
    call. A `model_name` label would be unbounded *and* would put the enumeration
    answer on a scrape endpoint.
    """
    await seed_workspace(migrate_engine)
    await seed_api_key(migrate_engine, scope_model_names=(IN_SCOPE,))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await may_resolve(db, KEY_ID, OUT_OF_SCOPE, NAMESPACE)

    exposition = generate_latest(REGISTRY).decode()
    refusals = [
        line
        for line in exposition.splitlines()
        if line.startswith("prope_access_control_key_scope_refusal_total{")
    ]

    assert refusals, "the counter was not incremented; this assertion would be vacuous"
    for line in refusals:
        assert OUT_OF_SCOPE not in line
        assert 'key_id="key_' in line
