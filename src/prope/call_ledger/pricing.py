"""CL-03: the price in force at a call's own timestamp, and the exact arithmetic.

Two things live here and they are separate on purpose. ``resolve_price``
answers *which* price applied; ``compute_cost`` answers *what that price makes
of these tokens*. Neither knows what time it is.

**The resolver never reads the server's clock.** ``at`` is a bound parameter and
it is always the call's own ``created_at``. ADR-0019: "the writer computes cost
when it persists the record, using the price row in force at the call's own
``created_at`` — not at wall-clock write time, which differs after a spill
replay or a backlog." The statement below therefore contains no call to the
server's current-timestamp function, and neither does anything that calls it.

**The interval is half-open** — ``[effective_from, next effective_from)``. The
predicate is ``effective_from <= :at``, so a call landing exactly on an
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

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.call_ledger.domain import PriceRow

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
