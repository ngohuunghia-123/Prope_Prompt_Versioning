"""CL-03: the price in force at the call's OWN timestamp, and nothing else.

ADR-0019: "the writer computes cost when it persists the record, using the price
row in force at the call's own ``created_at`` — not at wall-clock write time,
which differs after a spill replay or a backlog."

The resolver is therefore asked a question about a timestamp that is handed to
it, and the whole of CL-03's guarantee is that the answer does not depend on
when the question is asked. The first test below asks it twice, with a third
price row inserted in between, and asserts the two answers are identical.

The interval is half-open — ``[effective_from, next effective_from)``. A call
landing exactly on an ``effective_from`` resolves to the NEW row, which is what
"effective from" means everywhere else the phrase is used, and it makes the
rows a partition of the timeline with no gap and no overlap.

"Rows exist but every ``effective_from`` is later than the call" resolves to
``None`` on exactly the same footing as "no row at all". The two are
indistinguishable to the caller deliberately: the distinction is one ``if``
away from someone deciding the earliest row is close enough, and ADR-0019
rejects exactly that ("an absent figure asks a question; a wrong figure answers
it").

**Since D-280 the rule has two implementations and this file guards both.**
``resolve_price`` states it in SQL; ``PriceBook.price_at`` states it in Python
over the rows ``load_price_book`` fetched for a whole batch, and it is the one
``write_records`` uses for every record in the system.
``test_the_batch_resolver_and_resolve_price_agree`` runs the two over the same
seeded rows at six instants and requires equal answers — which is what stands in
for the two being one function. A change to either belongs in the same commit as
a change to that test.
"""

from prope.call_ledger.domain import PriceRow
from prope.call_ledger.pricing import load_price_book, resolve_price
from prope.db.session import workspace_transaction
from tests.unit import (
    OTHER_PROVIDER_CONFIG,
    OTHER_UPSTREAM_MODEL,
    PROVIDER_CONFIG,
    UPSTREAM_MODEL,
    WORKSPACE_A,
    WORKSPACE_B,
    day,
    seed_price_row,
)

ROW_X = "prc_01J000000000000000000000X"  # effective from day 1
ROW_Y = "prc_01J000000000000000000000Y"  # effective from day 10
ROW_Z = "prc_01J000000000000000000000Z"  # effective from day 20


async def _resolve(
    app_sessionmaker,
    *,
    at,
    workspace_id: str = WORKSPACE_A,
    provider_config_id: str = PROVIDER_CONFIG,
    upstream_model: str = UPSTREAM_MODEL,
) -> PriceRow | None:
    """Resolve inside a tenant transaction — the only way a session is obtained."""
    async with workspace_transaction(app_sessionmaker, workspace_id) as session:
        return await resolve_price(
            session,
            workspace_id=workspace_id,
            provider_config_id=provider_config_id,
            upstream_model=upstream_model,
            at=at,
        )


async def test_a_day_20_price_row_does_not_move_a_call_made_on_day_5(
    app_sessionmaker, migrate_engine
):
    """AC-3, verbatim: made on day 5, written on day 12, a day-20 price added.

    The day-20 row is inserted BETWEEN the two resolutions, so the second call
    is not a repetition — it is the same question asked of a table that has
    since changed. Both answers must be the day-1 row, and they must be equal
    field for field, not merely equal in ``price_row_id``.
    """
    await seed_price_row(migrate_engine, price_row_id=ROW_X, effective_from=day(1))
    await seed_price_row(migrate_engine, price_row_id=ROW_Y, effective_from=day(10))

    # Written on day 12; priced at the call's own day-5 timestamp.
    before = await _resolve(app_sessionmaker, at=day(5))
    assert before is not None
    assert before.price_row_id == ROW_X

    await seed_price_row(migrate_engine, price_row_id=ROW_Z, effective_from=day(20))

    after = await _resolve(app_sessionmaker, at=day(5))
    assert after == before, (
        "a price row added on day 20 moved the resolution for a day-5 call — "
        "CL-03's entire guarantee is that it cannot"
    )


async def test_a_call_after_the_second_row_resolves_to_the_second_row(
    app_sessionmaker, migrate_engine
):
    """The positive control for the test above: the resolver is not simply
    returning the oldest row it can find."""
    await seed_price_row(migrate_engine, price_row_id=ROW_X, effective_from=day(1))
    await seed_price_row(migrate_engine, price_row_id=ROW_Y, effective_from=day(10))

    resolved = await _resolve(app_sessionmaker, at=day(12))

    assert resolved is not None
    assert resolved.price_row_id == ROW_Y


async def test_the_boundary_instant_belongs_to_the_newer_row(app_sessionmaker, migrate_engine):
    """Half-open ``[effective_from, next effective_from)``, to the microsecond.

    Three assertions, because the boundary is only interesting beside its two
    neighbours: one microsecond before day 10 is the old row, day 10 exactly is
    the NEW row, and one microsecond after is the new row too.
    """
    await seed_price_row(migrate_engine, price_row_id=ROW_X, effective_from=day(1))
    await seed_price_row(migrate_engine, price_row_id=ROW_Y, effective_from=day(10))

    just_before = await _resolve(app_sessionmaker, at=day(10, microseconds=-1))
    exactly_on = await _resolve(app_sessionmaker, at=day(10))
    just_after = await _resolve(app_sessionmaker, at=day(10, microseconds=1))

    assert just_before is not None and just_before.price_row_id == ROW_X
    assert exactly_on is not None and exactly_on.price_row_id == ROW_Y, (
        "the boundary instant resolved to the superseded row — the interval is "
        "half-open, so effective_from is inclusive"
    )
    assert just_after is not None and just_after.price_row_id == ROW_Y


async def test_a_price_row_not_yet_effective_resolves_to_nothing(app_sessionmaker, migrate_engine):
    """A row exists, and it does not apply. There is no price in force."""
    await seed_price_row(migrate_engine, price_row_id=ROW_Y, effective_from=day(10))

    assert await _resolve(app_sessionmaker, at=day(5)) is None


async def test_not_yet_effective_and_no_rows_at_all_are_indistinguishable(
    app_sessionmaker, migrate_engine
):
    """The two shapes of "unpriced" are the same shape.

    Asserted together in one test because the property is the *equality* of the
    two answers, not the value of either. A future conditional that treated
    "rows exist but none applies" as "close enough, use the earliest" would pass
    the previous test's sibling and fail here.
    """
    no_rows_at_all = await _resolve(app_sessionmaker, at=day(5))

    await seed_price_row(migrate_engine, price_row_id=ROW_Y, effective_from=day(10))
    rows_exist_but_none_applies = await _resolve(app_sessionmaker, at=day(5))

    assert no_rows_at_all is None
    assert rows_exist_but_none_applies is None
    assert no_rows_at_all == rows_exist_but_none_applies


async def test_a_price_row_for_another_workspace_is_never_returned(
    app_sessionmaker, migrate_engine
):
    """Refused twice over: by the statement's own ``workspace_id`` predicate and,
    underneath it, by the tenant policy (ADR-0035). Either alone would suffice;
    both is the point."""
    await seed_price_row(migrate_engine, price_row_id=ROW_X, workspace_id=WORKSPACE_B)

    assert await _resolve(app_sessionmaker, at=day(5), workspace_id=WORKSPACE_A) is None

    # Positive control: the row is real, and resolvable by the tenant that owns it.
    owned = await _resolve(app_sessionmaker, at=day(5), workspace_id=WORKSPACE_B)
    assert owned is not None and owned.price_row_id == ROW_X


async def test_a_price_row_for_another_provider_config_is_never_returned(
    app_sessionmaker, migrate_engine
):
    """The same model name under a different provider config is a different price."""
    await seed_price_row(
        migrate_engine, price_row_id=ROW_X, provider_config_id=OTHER_PROVIDER_CONFIG
    )

    assert await _resolve(app_sessionmaker, at=day(5)) is None

    owned = await _resolve(
        app_sessionmaker, at=day(5), provider_config_id=OTHER_PROVIDER_CONFIG
    )
    assert owned is not None and owned.price_row_id == ROW_X


async def test_the_batch_resolver_and_resolve_price_agree(app_sessionmaker, migrate_engine):
    """D-283's control: two implementations of one rule, proven equal.

    ``resolve_price`` states the rule in SQL — ``effective_from <= :at ORDER BY
    effective_from DESC LIMIT 1`` — and is what ``repricing.reprice_unpriced``
    and every test above use. ``PriceBook.price_at`` states it in Python, as a
    bisect over the key's ascending rows, and is what ``write_records`` uses for
    every record it writes. Collapsing the two into one implementation stays
    available and was refused for blast radius (D-280/D-283), so **this test is
    what stands in for having only one.**

    Six instants, chosen so an off-by-one in either direction is visible: before
    every row (both must answer ``None``), on the first row, one microsecond
    before a supersession, exactly on it, one microsecond after, and after the
    last row. Equality is on the whole ``PriceRow`` — field for field, including
    the ``Decimal`` prices — and not on ``price_row_id`` alone.

    **If this test goes red, one of the two resolvers has moved and the other has
    not.** The repair is to make them agree again, never to delete a case.
    """
    await seed_price_row(migrate_engine, price_row_id=ROW_X, effective_from=day(1))
    await seed_price_row(migrate_engine, price_row_id=ROW_Y, effective_from=day(10))
    await seed_price_row(migrate_engine, price_row_id=ROW_Z, effective_from=day(20))

    instants = [
        day(1, microseconds=-1),
        day(1),
        day(10, microseconds=-1),
        day(10),
        day(10, microseconds=1),
        day(25),
    ]

    for at in instants:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            from_sql = await resolve_price(
                session,
                workspace_id=WORKSPACE_A,
                provider_config_id=PROVIDER_CONFIG,
                upstream_model=UPSTREAM_MODEL,
                at=at,
            )
            book = await load_price_book(
                session,
                workspace_id=WORKSPACE_A,
                keys={(PROVIDER_CONFIG, UPSTREAM_MODEL)},
            )
        from_book = book.price_at(
            provider_config_id=PROVIDER_CONFIG,
            upstream_model=UPSTREAM_MODEL,
            at=at,
        )
        assert from_book == from_sql, (
            f"at {at.isoformat()} the SQL resolver answered {from_sql} and the batch resolver "
            f"answered {from_book}; the two state one rule and must not have drifted"
        )

    # Negative and positive controls, so a pair of resolvers that both answered
    # None for everything could not pass this test.
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        book = await load_price_book(
            session, workspace_id=WORKSPACE_A, keys={(PROVIDER_CONFIG, UPSTREAM_MODEL)}
        )
    assert (
        book.price_at(
            provider_config_id=PROVIDER_CONFIG,
            upstream_model=UPSTREAM_MODEL,
            at=day(1, microseconds=-1),
        )
        is None
    )
    resolved = book.price_at(
        provider_config_id=PROVIDER_CONFIG, upstream_model=UPSTREAM_MODEL, at=day(25)
    )
    assert resolved is not None and resolved.price_row_id == ROW_Z


async def test_the_batch_resolver_answers_nothing_for_a_key_it_was_not_given(
    app_sessionmaker, migrate_engine
):
    """A book is scoped to the keys it was loaded for, and says so by answering ``None``.

    The failure this refuses is the one that would be invisible: a book that fell
    back to *some* row when asked about a key nobody loaded would price a call
    from another model's price row, and the stored cost would look entirely
    plausible.
    """
    await seed_price_row(migrate_engine, price_row_id=ROW_X, effective_from=day(1))
    await seed_price_row(
        migrate_engine,
        price_row_id=ROW_Y,
        upstream_model=OTHER_UPSTREAM_MODEL,
        effective_from=day(1),
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        book = await load_price_book(
            session, workspace_id=WORKSPACE_A, keys={(PROVIDER_CONFIG, UPSTREAM_MODEL)}
        )

    assert (
        book.price_at(
            provider_config_id=PROVIDER_CONFIG, upstream_model=OTHER_UPSTREAM_MODEL, at=day(5)
        )
        is None
    )
    # A null half of the key is answered without a lookup at all, the same early
    # return ``resolve_price`` makes.
    assert (
        book.price_at(provider_config_id=None, upstream_model=UPSTREAM_MODEL, at=day(5)) is None
    )
    assert (
        book.price_at(provider_config_id=PROVIDER_CONFIG, upstream_model=None, at=day(5)) is None
    )
    # Positive control: the key it WAS given still resolves.
    owned = book.price_at(
        provider_config_id=PROVIDER_CONFIG, upstream_model=UPSTREAM_MODEL, at=day(5)
    )
    assert owned is not None and owned.price_row_id == ROW_X


async def test_a_price_row_for_another_upstream_model_is_never_returned(
    app_sessionmaker, migrate_engine
):
    """``upstream_model`` is free text and is matched exactly. A near-miss is a
    miss: it becomes an unpriced call on the worklist, which is the direction
    the mistake is meant to surface from."""
    await seed_price_row(migrate_engine, price_row_id=ROW_X, upstream_model=OTHER_UPSTREAM_MODEL)

    assert await _resolve(app_sessionmaker, at=day(5)) is None

    owned = await _resolve(app_sessionmaker, at=day(5), upstream_model=OTHER_UPSTREAM_MODEL)
    assert owned is not None and owned.price_row_id == ROW_X
