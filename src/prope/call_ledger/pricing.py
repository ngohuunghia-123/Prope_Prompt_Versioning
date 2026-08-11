"""CL-03: the price in force at a call's own timestamp, and the exact arithmetic.

Three things live here and they are separate on purpose. ``resolve_price``
answers *which* price applied, for one call; ``load_price_book`` answers the
same question for a whole batch in **one** statement, and ``PriceBook.price_at``
then applies the rule per record; ``compute_cost`` answers *what that price makes
of these tokens*. None of them knows what time it is.

**The batch pair exists because the per-call resolver was an N+1 inside the one
write path in the system.** Plan 03-06 measured it: 1.42 ms per round trip, one
round trip per ``reported`` draft, roughly **70% of the cost of writing a priced
500-record window** — and issued whether or not a price row exists, so an
unpriced workspace paid the same. ``write_records`` now loads one book per batch
and resolves each record against that record's own ``created_at``. **The book is
keyed on the ``(provider_config_id, upstream_model)`` pair and never on the
instant**, which is the whole of D-280: a memo keyed on the resolved instant
would look perfect in a load test whose thirty thousand drafts share one
timestamp and would buy nothing in production, where every record has its own.

**The resolver never reads the server's clock.** ``at`` is a bound parameter and
it is always the call's own ``created_at``. ADR-0019: "the writer computes cost
when it persists the record, using the price row in force at the call's own
``created_at`` — not at wall-clock write time, which differs after a spill
replay or a backlog." The statement below therefore contains no call to the
server's current-timestamp function, and neither does anything that calls it.

**The interval is half-open** — ``[effective_from, next effective_from)``. The
predicate is ``effective_from <= :at`` in ``resolve_price`` and
``bisect_right(rows, at) - 1`` in ``PriceBook.price_at``, which select the same
row: a call landing exactly on an
``effective_from`` is priced at the NEW row. Ties within that ordering are not
broken, they are made impossible: ``uq_price_table_workspace_id`` refuses a
second row for the same
``(workspace_id, provider_config_id, upstream_model, effective_from)``, because
a non-deterministic figure ending up on an approval record is the thing ADR-0019
exists to prevent.

**``None`` means unpriced, and it is never turned into a zero.** "No price row
exists" and "rows exist but every ``effective_from`` is later than this call"
both return ``None`` and are indistinguishable to the caller. That is
deliberate: distinguishing them is one conditional away from someone deciding
the earliest row is close enough.

Money is exact decimal end to end, and the quantum is **the column's scale**
(ten places), never a currency's minor unit. A representative call is a few
hundred tokens at a price of order 0.00015 per 1k — about 0.00007. Rounded to
two decimal places that is 0.00, and "no row anywhere records a cost of zero" is
a stated success criterion, enforced by ``ck_call_record_cost_is_never_zero``,
which would turn the rounding decision into a write-path outage.
"""

from bisect import bisect_right
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.call_ledger.domain import PriceRow

#: A ``(provider_config_id, upstream_model)`` pair — the key a price row is
#: effective-dated under, and the key a batch's lookup is grouped by. Both halves
#: are non-null here: ``PriceBook.price_at`` answers a draft carrying either as
#: ``None`` without consulting anything, because no row can match.
PriceKey = tuple[str, str]

#: The effective-dated lookup. Every identifier is schema-qualified and every
#: value is bound. With the column order of ``uq_price_table_workspace_id``
#: matching the predicate, this is a backward index scan terminating on the
#: first entry: no sort, no filter, one heap fetch.
PRICE_IN_FORCE = text(
    """
    SELECT price_row_id, input_price_per_1k, output_price_per_1k, currency, effective_from
    FROM   ledger.price_table
    WHERE  workspace_id       = :workspace_id
      AND  provider_config_id = :provider_config_id
      AND  upstream_model     = :upstream_model
      AND  effective_from    <= :at
    ORDER  BY effective_from DESC
    LIMIT  1
    """
)

#: **D-280: the same question, asked once for a whole batch.** Every price row
#: for the listed keys, ordered so the caller can resolve any instant against any
#: of them without asking again. It is ``PRICE_IN_FORCE`` with the ``LIMIT 1``
#: removed and the single key replaced by a list — which is what turns N round
#: trips into one.
#:
#: **``unnest`` of two arrays, because the match is PAIRWISE.** Two independent
#: ``= ANY(...)`` predicates would be a cross product: they would match provider
#: A's config against provider B's model and return prices for a key nobody
#: asked about. ``unnest(a, b)`` walks the two arrays in step, which is the only
#: shape that expresses *"these exact pairs"*. The corollary is that the arrays
#: must be the same length — unnest pads the shorter one with NULLs, silently —
#: so ``load_price_book`` builds both from one sorted list of pairs and there is
#: no second place they could disagree.
#:
#: **The access path is the same one ``PRICE_IN_FORCE`` uses**, by name:
#: ``uq_price_table_workspace_id`` over ``(workspace_id, provider_config_id,
#: upstream_model, effective_from)``, whose own DDL comment says the column order
#: *is* the lookup order. This is a nested loop over the unnested keys with one
#: index scan each — **M index lookups inside ONE round trip**, rather than M
#: round trips.
#:
#: **``ORDER BY ... effective_from`` is load-bearing and is not tidiness.**
#: ``PriceBook`` bisects each key's list and assumes it ascends; a resolution
#: over an unsorted list would be silently wrong rather than loudly wrong.
#: Removing this clause is the change that looks free and is not.
#:
#: **``workspace_id`` is in the join alongside the tenant policy rather than
#: instead of it** — the posture ``PRICE_IN_FORCE`` and ``api.PRICE_ROWS`` both
#: take. The policy is the enforcement; the explicit column is what makes the
#: scope a property of the statement.
#:
#: **No upper bound on ``effective_from``, deliberately** (D-282). Bounding the
#: fetch by the batch's latest ``created_at`` would be a correct optimisation and
#: would put an instant back into the query — one refactor away from the
#: instant-keyed memo D-280 exists to refuse. ``ledger.price_table`` holds one
#: row per price change and is append-only by privilege (T-006), so the rows the
#: bound would save are a handful.
PRICE_ROWS_FOR_KEYS = text(
    """
    SELECT p.provider_config_id,
           p.upstream_model,
           p.price_row_id,
           p.input_price_per_1k,
           p.output_price_per_1k,
           p.currency,
           p.effective_from
    FROM   unnest(CAST(:provider_config_ids AS text[]),
                  CAST(:upstream_models AS text[]))
           AS wanted(provider_config_id, upstream_model)
    JOIN   ledger.price_table AS p
      ON   p.workspace_id       = :workspace_id
      AND  p.provider_config_id = wanted.provider_config_id
      AND  p.upstream_model     = wanted.upstream_model
    ORDER  BY p.provider_config_id, p.upstream_model, p.effective_from
    """
)

#: Ten decimal places — the scale of ``numeric(20,10)``, which is the type of
#: every money column in ``ledger``. Quantising anywhere else is the defect this
#: constant exists to name.
COST_SCALE = Decimal("0.0000000001")

_PER_1K = Decimal(1000)


async def resolve_price(
    session: AsyncSession,
    *,
    workspace_id: str,
    provider_config_id: str | None,
    upstream_model: str | None,
    at: datetime,
) -> PriceRow | None:
    """The price row in force at ``at`` for this key, or ``None``.

    ``session`` comes from ``workspace_transaction()``, so the tenant policy
    applies underneath the explicit ``workspace_id`` predicate — a row belonging
    to another workspace is refused twice over.

    ``None`` is a complete answer. It means the call is ``unpriced``: real
    tokens, a NULL cost, and a place on the unpriced worklist. It is never a
    zero price, a nearest row, or a default.

    **This is the ONE-call resolver and it is no longer the one the writer
    uses.** ``repricing.reprice_unpriced`` calls it per candidate, and CL-03's
    unit tests assert the rule through it; ``write_records`` resolves a whole
    batch through ``load_price_book`` and ``PriceBook.price_at`` instead, because
    one round trip per record was 70% of the cost of a priced window (D-280).
    The two are two implementations of one rule and
    ``test_the_batch_resolver_and_resolve_price_agree`` is what keeps them
    equal — **a change here belongs in the same commit as a change to that
    test.**
    """
    if provider_config_id is None or upstream_model is None:
        # No key, no lookup. A call with no provider config or no model name
        # cannot match any row, and asking is a round trip for a known answer.
        return None

    row = (
        await session.execute(
            PRICE_IN_FORCE,
            {
                "workspace_id": workspace_id,
                "provider_config_id": provider_config_id,
                "upstream_model": upstream_model,
                "at": at,
            },
        )
    ).mappings().first()

    return PriceRow(**row) if row is not None else None


def _effective_from(price: PriceRow) -> datetime:
    """``bisect_right``'s key. Named rather than a lambda so the bisect reads."""
    return price.effective_from


@dataclass(frozen=True, slots=True)
class PriceBook:
    """Every price row in force for one batch's keys, resolvable per record.

    **This is ``PRICE_IN_FORCE``'s rule expressed over a list, not a second
    rule.** ``bisect_right(rows, at) - 1`` selects the last row whose
    ``effective_from`` is at or before ``at``, which is exactly what
    ``WHERE effective_from <= :at ORDER BY effective_from DESC LIMIT 1`` selects.
    The three properties the module docstring owns are repeated here rather than
    assumed, because this is the second place they now have to hold:

    - **The interval is half-open** — ``[effective_from, next effective_from)``.
      ``bisect_right`` puts an instant landing exactly on an ``effective_from``
      *after* that row, so the ``- 1`` lands on it: a call made at the boundary
      is priced at the NEW row, same as the SQL.
    - **Ties are impossible rather than broken.**
      ``uq_price_table_workspace_id`` refuses a second row for the same
      ``(workspace_id, provider_config_id, upstream_model, effective_from)``, so
      there is never a choice to make between two rows at one instant — which is
      what keeps a stored cost reproducible years later (ADR-0019).
    - **``None`` means unpriced and is never turned into a zero.** A key with no
      rows and a key whose every row is later than ``at`` both answer ``None``,
      indistinguishably, for the reason ``resolve_price`` gives: distinguishing
      them is one conditional away from someone deciding the earliest row is
      close enough.

    **The supersession range is still DERIVED and never stored.** Here it is
    position in an ordered list; in ``api.PRICE_ROWS`` it is
    ``lead(effective_from)``. A stored ``effective_to`` would need the ``UPDATE``
    on ``ledger.price_table`` that A-102 and T-006 forbid, and it would disagree
    with the derived one the first time a row was inserted *between* two others —
    which is CL-05's entire scenario.

    **Delete-together instruction, because this module now contains two
    implementations of one rule.** ``resolve_price`` states it in SQL and is what
    ``repricing.reprice_unpriced`` and CL-03's own unit tests use; ``price_at``
    states it in Python and is what the writer uses.
    ``test_the_batch_resolver_and_resolve_price_agree`` in
    ``tests/unit/test_effective_dated_pricing.py`` is what keeps them equal, and
    a change to either of these two functions belongs in the same commit as a
    change to that test. Collapsing them into one implementation stays available
    and was refused here for blast radius (D-283), not on principle.
    """

    rows: dict[PriceKey, tuple[PriceRow, ...]]

    def price_at(
        self,
        *,
        provider_config_id: str | None,
        upstream_model: str | None,
        at: datetime,
    ) -> PriceRow | None:
        """The price row in force at ``at`` for this key, or ``None``.

        ``at`` is the RECORD's own ``created_at`` at every call site. It is a
        parameter and never a clock read, and never one instant reused across a
        batch: a batch straddling a price change must resolve to two different
        rows, and that is asserted in
        ``tests/integration/test_price_resolution_is_batched.py``.
        """
        if provider_config_id is None or upstream_model is None:
            # No key, no answer — the same early return ``resolve_price`` makes,
            # for the same reason: a call with no provider config or no model
            # name cannot match any row.
            return None

        rows = self.rows.get((provider_config_id, upstream_model))
        if not rows:
            return None

        index = bisect_right(rows, at, key=_effective_from)
        if index == 0:
            # Rows exist and every one of them is later than this call. The call
            # is unpriced, on exactly the same footing as a key with no rows.
            return None
        return rows[index - 1]


async def load_price_book(
    session: AsyncSession,
    *,
    workspace_id: str,
    keys: Collection[PriceKey],
) -> PriceBook:
    """One statement for a whole batch's price history. No clock is read.

    ``session`` comes from ``workspace_transaction()``, so the tenant policy
    applies underneath the explicit ``workspace_id`` predicate — the same
    belt-and-braces ``resolve_price`` has.

    **An empty key set executes nothing** (D-285). A batch in which every record
    has ``usage_status = unknown`` has no price to look up, and it must keep
    costing zero reads — which is what the caller's ``if usage_status is
    UNKNOWN`` branch buys today by never asking. The guard lives here rather than
    at the call site so all three callers of ``write_records`` get it.
    """
    if not keys:
        return PriceBook({})

    # Sorted, so the parameter order is reproducible across runs and two
    # identical batches produce the same plan. De-duplication is the caller's
    # ``set``, and it matters: a repeated pair would multiply the rows returned
    # for it.
    ordered = sorted(set(keys))

    rows = (
        (
            await session.execute(
                PRICE_ROWS_FOR_KEYS,
                {
                    "workspace_id": workspace_id,
                    "provider_config_ids": [key[0] for key in ordered],
                    "upstream_models": [key[1] for key in ordered],
                },
            )
        )
        .mappings()
        .all()
    )

    # Grouped in the order the statement returned them, which is ascending
    # ``effective_from`` within each key — see ``PRICE_ROWS_FOR_KEYS``. Nothing
    # re-sorts here, because a second sort would hide the day the ORDER BY was
    # removed.
    grouped: dict[PriceKey, list[PriceRow]] = {}
    for row in rows:
        key = (row["provider_config_id"], row["upstream_model"])
        grouped.setdefault(key, []).append(
            PriceRow(
                price_row_id=row["price_row_id"],
                input_price_per_1k=row["input_price_per_1k"],
                output_price_per_1k=row["output_price_per_1k"],
                currency=row["currency"],
                effective_from=row["effective_from"],
            )
        )

    return PriceBook({key: tuple(value) for key, value in grouped.items()})


def compute_cost(input_tokens: int, output_tokens: int, price: PriceRow) -> Decimal:
    """``(in/1000)*in_price + (out/1000)*out_price``, exact, quantised at ten places.

    Raises ``TypeError`` rather than coercing if either per-1k price is not a
    ``Decimal``. Coercion is the dangerous branch: it would succeed, produce a
    plausible number, and make the figure disagree with itself in the last
    places between runs — which is exactly the reproducibility ADR-0019 needs
    when someone asks, years later, why a number is that number.
    """
    for name, value in (
        ("input_price_per_1k", price.input_price_per_1k),
        ("output_price_per_1k", price.output_price_per_1k),
    ):
        if not isinstance(value, Decimal):
            raise TypeError(
                f"{name} on price row {price.price_row_id} is {type(value).__name__}, not Decimal; "
                "binary arithmetic on money makes a stored cost non-reproducible"
            )

    cost = (Decimal(input_tokens) / _PER_1K) * price.input_price_per_1k + (
        Decimal(output_tokens) / _PER_1K
    ) * price.output_price_per_1k

    return cost.quantize(COST_SCALE, rounding=ROUND_HALF_EVEN)
